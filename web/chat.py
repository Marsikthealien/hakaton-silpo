"""Чат-агент на локальному Qwen через Ollama, керований по MCP.

Інструменти беруться ДИНАМІЧНО з MCP-серверів (silpo-agent + profile) через
MCPHost, а виклики моделі маршрутизуються назад у ці сервери по протоколу.

Моделі показуємо курований набір: 3B-параметрична модель захлинається на 40
сирих tools «Сільпо» з uuid-аргументами, тому вона працює з фасадом, де в
кожного інструмента один-два зрозумілі аргументи.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time

import httpx2

log = logging.getLogger("packagent.ai")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "")  # порожньо = авто-вибір

# Ліміт на ОДИН крок tool-loop. Було 300 с — при шести кроках це до півгодини
# «…» у бульбашці, тобто демо, яке ніколи не завершується. Перевищив — крок
# кидає помилку, і гість бачить її, а не мовчання.
CHAT_TIMEOUT = float(os.environ.get("CHAT_TIMEOUT", "120"))
# Скільки чекати на озвучення вже готового результату. Довше — частіше доходить
# до тексту моделі; коротше — швидше кидає помилку.
# 60 с вистачало, поки модель була на відеокарті. На процесорі 7B видає ~2.6
# токена за секунду, і два речення разом із чергою за CPU в це не влазять.
NARRATE_TIMEOUT = float(os.environ.get("NARRATE_TIMEOUT", "120"))

_PREFERRED = ["qwen2.5:7b", "qwen2.5:3b", "qwen2.5:3b-instruct",
              "llama3.2:3b", "qwen2.5", "qwen3:4b", "qwen3:1.7b", "qwen3"]

ALLOWED = {
    "who_am_i", "build_pack", "pack_from_receipt", "reorder_pack",
    "mood_pack", "evening_pack", "breakfast_pack",
    "weekly_pack", "budget_pack", "party_pack",
    "optimize_pack", "swap_item", "pack_to_cart", "save_pack", "precheck_pack",
    # правка поточного пака словами
    "pack_add", "pack_remove", "pack_set_qty", "pack_swap_named", "get_pack",
    "my_packs", "my_perks",
    # аналітика: відповідь — число з чеків, і модель має вміти її дістати
    "coupon_audit", "savings_report", "spend_report", "impulse_check",
    "plus_check", "reminders",
    # грибниця
    "silpo_get_game_profile", "silpo_get_achievements",
    "get_profile", "update_profile", "remember_fact",
}

# Стиль мовлення — за порадою Respeecher із каналу хакатону. Це не косметика:
# те, що добре читається очима, у голосі розсипається. Списки звучать як
# автовідповідач, «10:30» вимовляється як «десять двокрапка тридцять», а
# «pack_from_receipt» уголос — просто шум.
VOICE_STYLE = (
    "ГОЛОС. Твої відповіді озвучуються вголос, тож пиши так, як говорять:\n"
    "• Тільки українською. Ніколи іншою мовою, навіть якщо гість пише нею.\n"
    "• Звичайний текст. Жодних зірочок, підкреслень, списків, заголовків, "
    "зворотних лапок. Просять виділити жирним — усе одно відповідай текстом.\n"
    "• Максимум ДВА пункти в одному реченні. Назви два й запропонуй продовжити.\n"
    "• Числа, час і дати — словами: «половина одинадцятої», а не «10:30»; "
    "«п'ятнадцяте травня», а не «15.05».\n"
    "• Абревіатури по літерах: «ем, це, пе».\n"
    "• Ніколи не читай посилання, шляхи, JSON і технічні назви tools.\n"
    "• Короткі речення. Одне-два. Три — лише якщо без цього ніяк. Чотири — ніколи.\n"
    "• ПЕРЕД викликом tool скажи коротку фразу очікування: «Секунду.», "
    "«Дай перевірю.», «Хвилинку.» Чергуй їх, не повторюй ту саму двічі поспіль "
    "і не став дві поруч. Після виклику мовчанку заповнювати не треба.\n"
    "• «Мм», «ну», «так», «зрозуміло» — зрідка й лише там, де це природно.\n"
    "• Не кажи «я — ШІ» чи «у мене немає вподобань», щоб ухилитися від питання "
    "про смак. Назви вподобання.\n"
    "• Перечитай відповідь. Якщо якесь речення прозвучало б штучно живим "
    "голосом — перепиши його, і тільки тоді відповідай."
)

SYSTEM = (
    "Ти — агент паків «Сільпо». Ти не радиш, а РОБИШ: збираєш набори з реальних "
    "товарів і кладеш їх у справжній кошик.\n"
    "• Хто перед тобою, що людина купує і що вже мало б закінчитись — who_am_i.\n"
    "• Новий набір під подію ('вечір кіно до 400 грн') — build_pack: name, "
    "items (перелік того, що шукати — вигадай його сам), max_uah.\n"
    "• 'Як минулого разу', 'повтори покупку' — pack_from_receipt.\n"
    "• Настрій ('мені грайливо', 'втомився') — mood_pack.\n"
    "• Вечір удома ('футбол', 'фільм', 'романтична вечеря') — evening_pack.\n"
    "• 'Сніданок на 200 грн' — breakfast_pack (поверне ще й рецепт).\n"
    "• 'Не їм гриби', 'алергія на горіхи', 'люблю пасту' — update_profile.\n"
    "• 'Що зазвичай беру', 'закінчилось' — reorder_pack.\n"
    "• Перед покупкою — optimize_pack: покаже, які купони й промо спрацюють і "
    "де вигідно взяти дві штуки замість однієї.\n"
    "• 'Заміни/дешевше/інше' — swap_item.\n"
    "• Правка ЗІБРАНОГО пака словами — pack_id не потрібен, береться останній:\n"
    "  'прибери пакет' — pack_remove(query='пакет');\n"
    "  'додай молоко' — pack_add(query='молоко');\n"
    "  'зроби три пляшки води' — pack_set_qty(query='вода', qty=3);\n"
    "  'заміни чипси на дешевше' — pack_swap_named(query='чипси', prefer='cheaper').\n"
    "  Позицію шукай за фрагментом назви, як людина очима в списку.\n"
    "• 'Збережи' — save_pack.\n"
    "• 'Поклади в кошик', 'беру' — pack_to_cart.\n"
    "• Кошик на тиждень — weekly_pack. 'Лишилось N грн' — budget_pack.\n"
    "• 'Шашлик на шістьох', 'настолки на чотирьох' — party_pack: theme, people.\n"
    "• 'Скільки я зекономив' — savings_report. 'Куди йдуть гроші' — spend_report.\n"
    "• 'Купони', 'що згорає' — coupon_audit. 'Чи вигідний Плюхс' — plus_check.\n"
    "• 'Чи варто брати X' — impulse_check: іноді правильна відповідь «не бери».\n"
    "• 'Що скінчилось', 'нагадай' — reminders.\n"
    "• 'Мій рівень', 'грибниця', 'досягнення' — silpo_get_game_profile.\n"
    "• Важливі факти про людину (алергія, улюблений фільм) — remember_fact.\n"
    "ВАЖЛИВО про новизну: перш ніж збирати вечерю, страву чи набір під подію, "
    "спитай одним реченням — хочеться чогось ЗНАЙОМОГО чи чогось НОВОГО. "
    "Далі передай novelty='familiar' або novelty='new' у той самий tool. "
    "Без відповіді не вгадуй: це різні кошики.\n"
    "Після дії скажи, що зібрав і на яку суму. Замовлення оформлює людина, не ти.\n\n"
    + VOICE_STYLE
)

async def _fallback(messages: list[dict], host, pack_id: str | None = None) -> dict:
    """Без моделі: розбираємо намір правилами й виконуємо сценарій самі."""
    text = next((m.get("content", "") for m in reversed(messages)
                 if m.get("role") == "user"), "")
    intent = route_intent(text)
    if not intent:
        return {"reply": "Не зрозумів. Спробуй сценарій кнопкою — вони працюють без моделі.",
                "tools_used": [], "routed": True}
    profile = (await host.call("get_profile", {})).get("profile", {})
    args = dict(intent["args"])
    # «Прибери каву» або «перевір перед оформленням» — про ТОЙ пак, що на
    # екрані, а не про останній створений: телефон надсилає його id.
    if pack_id and intent["tool"] in ("pack_add", "pack_remove", "pack_set_qty",
                                      "pack_swap_named", "precheck_pack"):
        args.setdefault("pack_id", pack_id)
    # «Топати чи замовити» — пороги доставки рахуємо під суму пака на екрані.
    if pack_id and intent["tool"] == "silpo_estimate_delivery":
        pack = (await host.call("get_pack", {"pack_id": pack_id})) or {}
        if pack.get("total_uah"):
            args["cart_total_uah"] = float(pack["total_uah"])
    if intent["tool"] in ("build_pack", "meal_pack", "mood_pack", "evening_pack",
                          "pack_from_receipt", "reorder_pack", "weekly_pack",
                          "budget_pack", "party_pack", "family_pack"):
        avoid = (profile.get("allergies") or []) + (profile.get("dislikes") or [])
        if avoid:
            args.setdefault("avoid", avoid)
        if profile.get("bonus_first", True):     # акційне спершу — типово
            args.setdefault("prefer_promo", True)
    log.info("fallback: %r → правило %s %s", text[:60], intent["tool"], args)
    if intent["tool"] == "crew_propose":
        # Нічого не створюємо без згоди — лише пропонуємо. Компанія разова,
        # тож завжди нова: «у тебе вже є» тут не буває.
        title = args["title"]
        proposal = {"title": title, "occasion": args["occasion"]}
        reply = (f"Зберемо компанію «{title}»? Кожен додасть свої алергії й побажання "
                 "зі свого телефона — за посиланням або QR — а кошик буде один.")
        return {"reply": reply, "why": intent["why"], "tools_used": [],
                "routed": True, "result": {"proposal": proposal}}
    result = await host.call(intent["tool"], args)
    if result.get("error"):
        return {"reply": result["error"], "tools_used": [{"name": intent["tool"], "args": args}],
                "routed": True}
    # Перевірка перед оформленням — не пак, а картка з чотирма рядками:
    # відповідь — вердикт, у телефон іде весь результат.
    if result.get("checks"):
        return {"reply": result.get("verdict") or "Готово.", "why": intent["why"],
                "tools_used": [{"name": intent["tool"], "args": args}],
                "routed": True, "result": result}
    # Правка пака повертає {pack, said} — показуємо той самий пак, що й сценарії.
    pack = result.get("pack") or result
    name = pack.get("name") or intent["tool"]
    summary = (result.get("said") or "") + (
        f" {name}: {pack['item_count']} позицій на {pack['total_uah']} ₴"
        if pack.get("item_count") is not None else "")
    # Аналітика й вердикти паків не мають: відповідь — їхній заголовок.
    if not summary.strip():
        summary = result.get("headline") or result.get("verdict") or ""
    return {"reply": summary.strip() or "Готово.", "why": intent["why"],
            "tools_used": [{"name": intent["tool"], "args": args}],
            "routed": True, "result": pack}


def _pick_model(models: list[str]) -> str:
    if MODEL:
        return MODEL
    for preferred in _PREFERRED:
        for name in models:
            if name == preferred or name.split(":")[0] == preferred.split(":")[0]:
                return name
    return models[0] if models else "qwen2.5:3b"


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    return text.replace("<think>", "").replace("</think>", "").strip()


async def runtime_hint() -> str | None:
    """Чому модель повільна — читаємо в самої Ollama, а не здогадуємось.

    `/api/ps` каже, скільки ваг лягло у відеопамʼять. `size_vram: 0` означає,
    що 7B-модель рахується на процесорі: це ~2-3 токени за секунду, і будь-яка
    відповідь у два речення впирається в таймаут. Гостю треба показати саме це,
    а не голе «ReadTimeout» — інакше він шукатиме проблему в мережі.
    """
    try:
        async with httpx2.AsyncClient(timeout=3) as client:
            loaded = (await client.get(f"{OLLAMA_URL}/api/ps")).json().get("models") or []
    except Exception:  # noqa: BLE001 — підказка не критична
        return None
    if not loaded:
        return ("Модель не тримається в памʼяті — кожен запит починається з "
                "її завантаження. Спробуй ще раз одразу після цього.")
    row = loaded[0]
    total, vram = row.get("size") or 0, row.get("size_vram") or 0
    if total and vram / total < 0.5:
        where = "цілком на процесорі" if not vram else f"на процесорі на {100 - vram*100//total}%"
        return (f"Модель {row.get('name')} рахується {where} — це кілька токенів "
                "за секунду. Постав відеокарту під Ollama або візьми меншу "
                "модель (qwen2.5:3b), інакше відповідь не встигає.")
    return None


async def chat_available() -> dict:
    try:
        async with httpx2.AsyncClient(timeout=3) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m.get("name", "") for m in response.json().get("models", [])]
        return {"available": True, "model": _pick_model(models),
                "has_model": bool(models), "models": models}
    except Exception:
        return {"available": False, "model": "qwen2.5:3b",
                "hint": "Запусти Ollama та `ollama pull qwen2.5:3b`."}


def _digest(result: dict) -> str:
    """Стислий зліпок результату для промпта.

    Моделі потрібні числа, а не три кілобайти slug'ів, картинок і branch_id:
    локальна 3B на такому вході не встигає навіть прочитати запит.
    """
    if not isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)[:400]
    keep = {k: result[k] for k in
            ("name", "item_count", "total_uah", "saved_uah", "source", "verdict")
            if result.get(k) is not None}
    first = [i.get("name") for i in (result.get("items") or [])[:4] if i.get("name")]
    if first:
        keep["перші_товари"] = first
    return json.dumps(keep, ensure_ascii=False)


async def narrate(phrase: str, result: dict, tool: str | None = None) -> dict:
    """Озвучити ВЖЕ виконаний сценарій справжнім викликом моделі.

    Сам результат рахує сценарій — тим самим MCP-викликом, що й кнопка
    «Напряму». Тому режим «Через модель» дає РІВНО той самий пак, а не свій.
    Модель тут лише формулює підсумок людською мовою; інструментів їй не даємо.

    Підсумок віддаємо ТІЛЬКИ якщо модель справді відповіла. Немає Ollama,
    таймаут, HTTP-помилка, порожня відповідь → {"error": ...}, а не тихий
    детермінований рядок: бульбашка «…» обіцяє гостю, що ШІ викликано, і
    підсунути замість нього шаблон означало б збрехати.
    """
    # Модель озвучує лише ПАК: там є склад, сума, знижка. У вердикт-екранів
    # (вага, ризик збирання, доставка) сум і позицій немає взагалі, і модель
    # їх вигадує — «у кошику нуль гривень». Для них віддаємо вердикт як є.
    is_pack = isinstance(result, dict) and (
        result.get("item_count") is not None or result.get("items"))
    if not is_pack:
        verdict = result.get("verdict") if isinstance(result, dict) else None
        return {"reply": verdict or "Готово — дивись картку нижче.",
                "narrated": False, "model": None}

    status = await chat_available()
    if not status["available"]:
        log.warning("narrate FAIL | Ollama офлайн (%s)", OLLAMA_URL)
        return {"error": f"ШІ недоступний: {status.get('hint', 'Ollama не відповідає')}",
                "offline": True}

    model = status["model"]
    payload = _digest(result)
    # Той самий голосовий стиль, що й у чаті: підсумок піде в озвучення, тож
    # списки й «143.94» тут зіпсували б звук так само.
    prompt = (f"Пак «Сільпо» ({tool or 'пак'}) на фразу «{phrase}» дав "
              f"результат: {payload}\n\n"
              "Перекажи це ОДНИМ коротким реченням українською: що зібрано, "
              "скільки позицій і на яку суму. Товари НЕ перелічуй — вони й так "
              "будуть на екрані. Суму пиши гривнями. Тільки з цих даних, нічого "
              "не додавай. Звичайний текст без списків і зірочок.")
    convo = [{"role": "user", "content": prompt
              + (" /no_think" if model.startswith("qwen3") else "")}]

    log.info("narrate >> %s | model=%s tool=%s phrase=%r payload=%dc",
             OLLAMA_URL, model, tool, phrase[:80], len(payload))
    t0 = time.perf_counter()
    try:
        async with httpx2.AsyncClient(timeout=NARRATE_TIMEOUT) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "messages": convo, "stream": False,
                "think": False, "keep_alive": "15m",
                # Кожен зайвий токен на процесорі — це ще ~0.4 с, тож стеля
                # низька. Але не НАДТО: обрізане на півслові речення гірше за
                # трохи повільніше ціле, а 48 різало саме так.
                "options": {"temperature": 0.2, "num_predict": 64}})
    except Exception as exc:  # noqa: BLE001 — гість має побачити причину
        ms = (time.perf_counter() - t0) * 1000
        log.warning("narrate FAIL %.0f ms | %s: %s",
                    ms, type(exc).__name__, str(exc)[:160])
        timed_out = "Timeout" in type(exc).__name__
        return {"error": (f"ШІ не встиг за {NARRATE_TIMEOUT:.0f} с" if timed_out
                          else f"ШІ не відповів: {type(exc).__name__}"),
                "hint": await runtime_hint() if timed_out else None,
                "model": model}

    ms = (time.perf_counter() - t0) * 1000
    if response.status_code != 200:
        log.warning("narrate FAIL HTTP %s | %.0f ms | %s",
                    response.status_code, ms, response.text[:160])
        return {"error": f"ШІ помилка HTTP {response.status_code}", "model": model}
    reply = _strip_think(response.json().get("message", {}).get("content"))
    if not reply:
        log.warning("narrate FAIL | %.0f ms | порожня відповідь", ms)
        return {"error": "ШІ повернув порожню відповідь", "model": model}
    log.info("narrate << %.0f ms | model=%s | reply=%r", ms, model, reply[:120])
    return {"reply": reply, "narrated": True, "model": model}


async def chat(messages: list[dict], host, max_steps: int = 6,
               pack_id: str | None = None) -> dict:
    """Tool-loop через Ollama; інструменти виконуються по MCP через host."""
    status = await chat_available()
    if not status["available"]:
        return await _fallback(messages, host, pack_id)

    model = status["model"]
    tools = [t for t in host.tools if t["function"]["name"] in ALLOWED]
    convo = [{"role": "system", "content": SYSTEM}] + messages
    if model.startswith("qwen3") and convo and convo[-1]["role"] == "user":
        convo[-1] = {**convo[-1], "content": convo[-1]["content"] + " /no_think"}

    tools_used = []
    async with httpx2.AsyncClient(timeout=CHAT_TIMEOUT) as client:
        for _ in range(max_steps):
            response = await client.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "messages": convo, "tools": tools,
                "stream": False, "think": False, "keep_alive": "15m",
                "options": {"temperature": 0.2, "num_predict": 512}})
            if response.status_code != 200:
                return {"reply": None, "tools_used": tools_used,
                        "error": f"Ollama {response.status_code}: {response.text[:200]}"}
            message = response.json().get("message", {})
            calls = message.get("tool_calls") or []
            log.info("chat step | model=%s | tools=%s", model,
                     [c["function"]["name"] for c in calls] or "—")
            if not calls:
                return {"reply": _strip_think(message.get("content")),
                        "tools_used": tools_used}
            convo.append({"role": "assistant", "content": message.get("content", ""),
                          "tool_calls": calls})
            for call in calls:
                name = call["function"]["name"]
                raw = call["function"].get("arguments")
                args = raw if isinstance(raw, dict) else json.loads(raw or "{}")
                # алергії та несмаки модель забувати не має права — підставляємо самі
                if name in ("build_pack", "pack_from_set") and "avoid" not in args:
                    profile = (await host.call("get_profile", {})).get("profile", {})
                    avoid = (profile.get("allergies") or []) + (profile.get("dislikes") or [])
                    if avoid:
                        args["avoid"] = avoid
                result = await host.call(name, args)
                tools_used.append({"name": name, "args": args})
                convo.append({"role": "tool", "tool_name": name,
                              "content": json.dumps(result, ensure_ascii=False)[:4000]})
    return {"reply": "(перевищено ліміт кроків)", "tools_used": tools_used}


# ---------------------------------------------------------------------------
# Розбір наміру без моделі
# ---------------------------------------------------------------------------
# Коли Ollama не піднята, вимикати поле вводу — погане рішення: гість пише,
# а йому мовчать. Тут простий роутер за ключовими словами доводить фразу до
# того самого сценарію. Він гірший за модель, але чесніший за німоту.
_INTENTS = [
    # Правка пака йде першою: «додай молоко» не має впасти в «збери пак зі слів»,
    # а «прибери пакет» — у сценарій «що в мене закінчилось».
    (("прибери", "видали", "прибрати", "не треба", "забери"),
     "pack_remove", {}, "прибираю з пака"),
    (("додай", "докинь", "ще й", "додати"),
     "pack_add", {}, "додаю в пак"),
    (("заміни", "замінити", "інший варіант", "щось дешевше", "дешевший"),
     "pack_swap_named", {"prefer": "cheaper"}, "міняю позицію"),

    (("повтори", "минул", "як тоді", "як завжди", "той самий чек"),
     "pack_from_receipt", {"index": 0}, "впізнав «повтори чек»"),
    (("закінч", "поповни", "звичн", "що я зазвичай", "докупи"),
     "reorder_pack", {}, "впізнав «поповнити звичне»"),
    (("холодильник", "вдома нема", "що є вдома", "полиц"),
     "silpo_pantry_missing", {}, "впізнав «перевір холодильник»"),
    # Стоїть після «холодильник»: «перевір холодильник» — це комора, а
    # «перевір перед оформленням» / «все гаразд?» — зведення чотирьох перевірок
    # (доставка, вага, купон, промо) одним кроком перед касою.
    (("оформ", "перевір", "до каси", "перед касою", "на касі", "сюрприз", "все гаразд"),
     "precheck_pack", {}, "впізнав «перевірка перед оформленням»"),
    # Стоїть ПЕРЕД «вечер» → meal_pack: «збери вечерю, щоб усім підійшло» —
    # це фраза сценарію з пітчу, і вона має вести в родинну вечерю, а не в
    # «страву на суму». Бюджет той самий, що на кнопці, — інакше з чату й
    # з картки виходять різні паки.
    (("сімʼ", "сім'", "родин", "на всіх", "на всю", "усім", "всім"),
     "family_pack", {"theme": "вечеря", "max_uah": 1500}, "впізнав «на всю родину»"),
    (("тренуванн", "зал", "спав", "втомивс", "самопочутт"),
     "silpo_wellbeing_state", {}, "впізнав «за самопочуттям»"),
    (("влізе", "вага", "важк", "кілограм", "не влізе"),
     "cart_weight_check", {}, "впізнав «чи влізе кошик»"),
    (("доставк", "топати", "дійти", "найближч", "магазин поруч"),
     "silpo_estimate_delivery", {"latitude": 50.5187, "longitude": 30.4986,
                                 "cart_total_uah": 700}, "впізнав «топати чи замовити»"),
    (("маршрут", "по залу", "де шукати", "обхід"),
     "silpo_get_store_layout", {}, "впізнав «маршрут по залу»"),
    (("футбол", "фільм", "серіал", "телевізор", "залипнут"),
     "evening_pack", {"genre": "фільм", "max_uah": 700}, "впізнав «вечір удома»"),
    (("сніданок", "обід", "вечер", "десерт", "приготув", "рецепт"),
     "meal_pack", {}, "впізнав «страва на суму»"),
    (("настрій", "фрукт", "сумно", "весело"),
     "mood_pack", {"mood": "ігривий", "max_uah": 600}, "впізнав «настрій»"),
    (("не забудь", "нагада", "скінчи"),
     "reminders", {}, "впізнав «не забудь»"),
    # «скін» стоїть після «скінчи»: «скінчилось» містить «скін», і без цього
    # порядку нагадування їхали у профіль грибниці
    (("рівен", "грибниц", "досвід", "скіни", "машрум"),
     "silpo_get_game_profile", {}, "впізнав «мій рівень»"),
    (("досягнен", "ачівк", "тематичн"),
     "silpo_get_achievements", {}, "впізнав «досягнення»"),
    (("купон", "згорає", "згорять", "промо"),
     "coupon_audit", {}, "впізнав «чек-детектив»"),
    (("зекономи", "економі", "знижок за"),
     "savings_report", {}, "впізнав «скільки зекономив»"),
    (("куди йдуть", "йдуть гроші", "куди гроші", "витрат", "аналітик", "скільки я витрача"),
     "spend_report", {}, "впізнав «куди йдуть гроші»"),
    (("плюхс", "підписк"),
     "plus_check", {}, "впізнав «чи вигідний Плюхс»"),
    # Компанія — ПЕРЕД «зустріччю»: «компанією на пікнік» — це люди, а не
    # набір на шістьох. «Запропонуй в компанію «Пікнік» закупку» — кошик із
    # пропозицій усіх; «зберемось компанією» — пропозиція створити компанію
    # й покликати людей за посиланням.
    (("закупк", "запропонуй в компані", "запропонуй компані", "кошик компані"),
     "crew_pack", {"max_uah": 1500}, "впізнав «закупка на компанію»"),
    (("компанією", "компанію на", "зберемось", "зберемося", "збираємось", "збираємося",
      "створи компані", "нова компані"),
     "crew_propose", {}, "впізнав «зберемось компанією»"),
    (("шашлик", "настолк", "пікнік", "на шість", "на всіх нас", "компані"),
     "party_pack", {"theme": "шашлик", "people": 6}, "впізнав «зустріч»"),
    (("на тиждень", "тижнев", "закуп"),
     "weekly_pack", {}, "впізнав «тижневий закуп»"),
    (("лишилось", "бюджет"),
     "budget_pack", {"budget_uah": 800, "days": 7}, "впізнав «розумний бюджет»"),
]

_MEALS = ("сніданок", "обід", "вечеря", "десерт")

# Відмінок після «на» → називний для назви компанії: «на пікнік» → «пікнік».
_OCCASIONS = {"пікнік": "пікнік", "вечір": "вечір", "вечірку": "вечірка", "шашлики": "шашлики",
              "шашлик": "шашлик", "дачу": "дача", "день народження": "день народження",
              "новий рік": "новий рік", "гриль": "гриль", "футбол": "футбол",
              "настолки": "настолки", "вихідні": "вихідні"}

# Службові слова, які не є предметом правки: «прибери звідти пакет, будь ласка».
_STOP = {"будь", "ласка", "мені", "звідти", "звідси", "пака", "паку", "пак",
         "кошика", "кошик", "цей", "цю", "це", "той", "там", "штук", "штуки",
         "шматки", "його", "їх", "все", "усе", "щось", "який", "яку", "туди",
         "натомість", "замість", "дешевше", "дешевший", "дорожче", "акційне"}


def route_intent(text: str) -> dict:
    """Фраза → сценарій. Повертає {tool, args, why} або None, якщо не впізнав."""
    low = (text or "").lower()
    amount = None
    for token in re.findall(r"\d+", low):
        if 30 <= int(token) <= 100000:
            amount = float(token)
            break

    for keys, tool, args, why in _INTENTS:
        hit = next((k for k in keys if k in low), None)
        if hit is None:
            continue
        args = dict(args)
        if tool in ("pack_remove", "pack_add", "pack_swap_named"):
            # «прибери пакет із пака» → query = «пакет». Беремо те, що після
            # дієслова, і відкидаємо службові слова.
            tail = low.split(hit, 1)[1]
            # «додай воду і хліб» — беремо лише до сполучника: інакше з двох
            # товарів вийде один безглуздий запит «воду хліб».
            tail = re.split(r"\s+(?:і|та|й|,)\s+", tail)[0]
            words = [w for w in re.findall(r"[а-яіїєґa-z'\-]{3,}", tail)
                     if w not in _STOP][:3]
            if not words:
                continue          # «прибери» без предмета — не наш випадок
            args["query"] = " ".join(words[:2])
            if tool == "pack_swap_named" and any(
                    x in low for x in ("акці", "знижк", "промо")):
                args["prefer"] = "promo"
            return {"tool": tool, "args": args, "why": f"{why} — «{args['query']}»"}
        if tool == "crew_propose":
            # «зберемось компанією на пікнік у суботу» → привід «пікнік»,
            # назва — те саме слово з великої: «Пікнік».
            m = re.search(r"\bна\s+([а-яіїєґ'ʼ\-]+(?:\s+народження)?)", low)
            occasion = _OCCASIONS.get((m.group(1) if m else "").strip(), None) \
                or (m.group(1).strip() if m else "пікнік")
            args["occasion"] = occasion
            args["title"] = occasion[:1].upper() + occasion[1:]
        if tool == "crew_pack":
            # «в компанію з імʼям Пікнік закупку…» / «в компанію «Пікнік»»
            m = (re.search(r"з\s+ім[’'ʼ]?ям\s+(.+?)\s+закупк", text or "", re.I)
                 or re.search(r"«([^»]+)»", text or "")
                 or re.search(r"компані[юї]\s+(.+?)\s+закупк", text or "", re.I))
            if m:
                args["crew_title"] = m.group(1).strip().strip("«»\"'")
        if tool == "meal_pack":
            for meal in _MEALS:
                if meal[:5] in low:
                    args["meal"] = meal
                    break
            if amount:
                args["max_uah"] = amount
        elif amount and "max_uah" in args:
            args["max_uah"] = amount
        elif amount and "budget_uah" in args:
            args["budget_uah"] = amount
        return {"tool": tool, "args": args, "why": why}

    # нічого не впізнали — збираємо пак із самих слів
    words = [w for w in re.findall(r"[А-ЯІЇЄҐа-яіїєґa-z]{4,}", low)
             if w not in ("хочу", "треба", "купити", "знайди", "будь", "ласка", "мені")]
    if words:
        return {"tool": "build_pack",
                "args": {"name": text[:40], "items": words[:6],
                         **({"max_uah": amount} if amount else {})},
                "why": "не впізнав сценарій — шукаю за словами з фрази"}
    return None
