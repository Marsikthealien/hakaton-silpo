"""Чат-агент на локальному Qwen через Ollama, керований по MCP.

Інструменти беруться ДИНАМІЧНО з MCP-серверів (silpo-agent + profile) через
MCPHost, а виклики моделі маршрутизуються назад у ці сервери по протоколу.

Моделі показуємо курований набір: 3B-параметрична модель захлинається на 40
сирих tools «Сільпо» з uuid-аргументами, тому вона працює з фасадом, де в
кожного інструмента один-два зрозумілі аргументи.
"""

from __future__ import annotations

import json
import os
import re

import httpx2

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "")  # порожньо = авто-вибір

_PREFERRED = ["qwen2.5:7b", "qwen2.5:3b", "qwen2.5:3b-instruct",
              "llama3.2:3b", "qwen2.5", "qwen3:4b", "qwen3:1.7b", "qwen3"]

ALLOWED = {
    "who_am_i", "build_pack", "pack_from_receipt", "reorder_pack",
    "mood_pack", "evening_pack", "breakfast_pack",
    "weekly_pack", "budget_pack", "party_pack",
    "optimize_pack", "swap_item", "pack_to_cart", "save_pack",
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

async def _fallback(messages: list[dict], host) -> dict:
    """Без моделі: розбираємо намір правилами й виконуємо сценарій самі."""
    text = next((m.get("content", "") for m in reversed(messages)
                 if m.get("role") == "user"), "")
    intent = route_intent(text)
    if not intent:
        return {"reply": "Не зрозумів. Спробуй сценарій кнопкою — вони працюють без моделі.",
                "tools_used": [], "routed": True}
    profile = (await host.call("get_profile", {})).get("profile", {})
    args = dict(intent["args"])
    if intent["tool"] in ("build_pack", "meal_pack", "mood_pack", "evening_pack",
                          "pack_from_receipt", "reorder_pack", "weekly_pack",
                          "budget_pack", "party_pack"):
        avoid = (profile.get("allergies") or []) + (profile.get("dislikes") or [])
        if avoid:
            args.setdefault("avoid", avoid)
        if profile.get("bonus_first"):
            args.setdefault("prefer_promo", True)
    result = await host.call(intent["tool"], args)
    if result.get("error"):
        return {"reply": result["error"], "tools_used": [{"name": intent["tool"], "args": args}],
                "routed": True}
    # Правка пака повертає {pack, said} — показуємо той самий пак, що й сценарії.
    pack = result.get("pack") or result
    name = pack.get("name") or intent["tool"]
    summary = (result.get("said") or "") + (
        f" {name}: {pack['item_count']} позицій на {pack['total_uah']} ₴"
        if pack.get("item_count") is not None else "")
    return {"reply": f"Модель офлайн, {intent['why']}.\n{summary.strip() or 'Готово.'}",
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


async def chat(messages: list[dict], host, max_steps: int = 6) -> dict:
    """Tool-loop через Ollama; інструменти виконуються по MCP через host."""
    status = await chat_available()
    if not status["available"]:
        return await _fallback(messages, host)

    model = status["model"]
    tools = [t for t in host.tools if t["function"]["name"] in ALLOWED]
    convo = [{"role": "system", "content": SYSTEM}] + messages
    if model.startswith("qwen3") and convo and convo[-1]["role"] == "user":
        convo[-1] = {**convo[-1], "content": convo[-1]["content"] + " /no_think"}

    tools_used = []
    async with httpx2.AsyncClient(timeout=300) as client:
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
    (("сімʼ", "сім'", "родин", "на всіх", "на всю"),
     "silpo_get_family_preferences", {}, "впізнав «на всю родину»"),
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
    (("куди йдуть", "витрат", "аналітик", "скільки я витрача"),
     "spend_report", {}, "впізнав «куди йдуть гроші»"),
    (("плюхс", "підписк"),
     "plus_check", {}, "впізнав «чи вигідний Плюхс»"),
    (("шашлик", "настолк", "пікнік", "на шість", "на всіх нас", "компані"),
     "party_pack", {"theme": "шашлик", "people": 6}, "впізнав «зустріч»"),
    (("на тиждень", "тижнев", "закуп"),
     "weekly_pack", {}, "впізнав «тижневий закуп»"),
    (("лишилось", "бюджет"),
     "budget_pack", {"budget_uah": 800, "days": 7}, "впізнав «розумний бюджет»"),
]

_MEALS = ("сніданок", "обід", "вечеря", "десерт")

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
