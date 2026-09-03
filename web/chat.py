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
# Скільки чекати на озвучення сценарію. Довше — бульбашка «…» висить довше,
# але частіше доходить до реального тексту ШІ; коротше — швидше кидає помилку.
NARRATE_TIMEOUT = float(os.environ.get("NARRATE_TIMEOUT", "60"))
# Ліміт на один крок tool-loop у вільному чаті. Було 300 с — це «вічне …»
# при 6 кроках. Перевищив — крок кидає помилку, а не висить.
CHAT_TIMEOUT = float(os.environ.get("CHAT_TIMEOUT", "120"))

_PREFERRED = ["qwen2.5:7b", "qwen2.5:3b", "qwen2.5:3b-instruct",
              "llama3.2:3b", "qwen2.5", "qwen3:4b", "qwen3:1.7b", "qwen3"]

ALLOWED = {
    "who_am_i", "build_pack", "pack_from_receipt", "reorder_pack",
    "mood_pack", "evening_pack", "breakfast_pack",
    "optimize_pack", "swap_item", "pack_to_cart", "save_pack",
    "my_packs", "my_perks",
    "get_profile", "update_profile", "remember_fact",
}

SYSTEM = (
    "Ти — агент паків «Сільпо». Ти не радиш, а РОБИШ: збираєш набори з реальних "
    "товарів і кладеш їх у справжній кошик. Відповідай коротко, українською.\n"
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
    "• 'Заміни/дешевше/інше' — swap_item. 'Збережи' — save_pack.\n"
    "• 'Поклади в кошик', 'беру' — pack_to_cart.\n"
    "• Важливі факти про людину (алергія, улюблений фільм) — remember_fact.\n"
    "Після дії коротко скажи, що зібрав, на яку суму і скільки зекономлено. "
    "Замовлення оформлює людина, не ти."
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
                          "pack_from_receipt", "reorder_pack"):
        avoid = (profile.get("allergies") or []) + (profile.get("dislikes") or [])
        if avoid:
            args.setdefault("avoid", avoid)
        if profile.get("bonus_first"):
            args.setdefault("prefer_promo", True)
    log.info("fallback: '%s' → правило %s %s", text[:60], intent["tool"], args)
    result = await host.call(intent["tool"], args)
    name = result.get("name") or intent["tool"]
    summary = (f"{name}: {result['item_count']} позицій на {result['total_uah']} ₴"
               if result.get("item_count") is not None
               else "Готово — дивись картку праворуч.")
    return {"reply": f"Модель офлайн, {intent['why']}.\n{summary}",
            "tools_used": [{"name": intent["tool"], "args": args}],
            "routed": True, "result": result}


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


def _digest(result: dict) -> str:
    """Стислий зліпок результату для промпта: моделі треба числа, а не 3 КБ
    slug'ів, картинок і branch_id — інакше повільна локалка не встигає навіть
    прочитати вхід. Перелік товарів для переказу теж зайвий."""
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
    """Озвучити вже виконаний сценарій РЕАЛЬНИМ викликом моделі.

    Сам результат сценарій рахує напряму (той самий MCP-виклик, що й кнопка
    «Напряму»), тож режим «Через модель» дає РІВНО той самий пак. Модель тут
    лише формулює підсумок людською мовою — інструментів їй не даємо.

    Підсумок віддаємо ТІЛЬКИ якщо модель справді відповіла. Немає Ollama,
    таймаут, HTTP-помилка, порожня відповідь → {"error": ...}, а не тихий
    детермінований рядок: у режимі «Через модель» бульбашка «…» означає, що
    ШІ викликано, тож брехати їй нема сенсу.
    """
    status = await chat_available()
    if not status["available"]:
        msg = status.get("hint", "Ollama недоступна")
        log.warning("narrate FAIL | Ollama офлайн (%s)", OLLAMA_URL)
        return {"error": f"ШІ недоступний: {msg}", "offline": True}

    model = status["model"]
    payload = _digest(result)
    convo = [
        {"role": "user", "content":
            f"Сценарій «Сільпо» ({tool or 'пак'}) на фразу «{phrase}» дав "
            f"результат: {payload}\n\n"
            "Перекажи це одним-двома короткими реченнями українською: що "
            "зібрано, скільки позицій, на яку суму, скільки зекономлено. "
            "Тільки з цих даних, нічого не додавай."},
    ]
    if model.startswith("qwen3"):
        convo[-1]["content"] += " /no_think"
    log.info("narrate >> POST %s/api/chat | model=%s tool=%s phrase=%r payload=%dc",
             OLLAMA_URL, model, tool, phrase[:80], len(payload))
    t0 = time.perf_counter()
    try:
        async with httpx2.AsyncClient(timeout=NARRATE_TIMEOUT) as client:
            response = await client.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "messages": convo, "stream": False,
                "think": False, "keep_alive": "15m",
                "options": {"temperature": 0.2, "num_predict": 80}})
    except Exception as exc:
        log.warning("narrate FAIL %.0f ms | %s: %s", (time.perf_counter() - t0) * 1000,
                    exc.__class__.__name__, str(exc)[:160])
        return {"error": f"ШІ не відповів: {exc.__class__.__name__}", "model": model}

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


async def chat_available() -> dict:
    try:
        async with httpx2.AsyncClient(timeout=3) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m.get("name", "") for m in response.json().get("models", [])]
        return {"available": True, "model": _pick_model(models),
                "has_model": bool(models), "models": models}
    except Exception as exc:
        log.warning("Ollama недоступна (%s): %s", OLLAMA_URL, exc.__class__.__name__)
        return {"available": False, "model": "qwen2.5:3b",
                "hint": "Запусти Ollama та `ollama pull qwen2.5:3b`."}


async def chat(messages: list[dict], host, max_steps: int = 6) -> dict:
    """Tool-loop через Ollama; інструменти виконуються по MCP через host."""
    status = await chat_available()
    if not status["available"]:
        log.info("chat: Ollama офлайн → fallback за правилами (%d повідомл.)", len(messages))
        return await _fallback(messages, host)

    model = status["model"]
    tools = [t for t in host.tools if t["function"]["name"] in ALLOWED]
    convo = [{"role": "system", "content": SYSTEM}] + messages
    if model.startswith("qwen3") and convo and convo[-1]["role"] == "user":
        convo[-1] = {**convo[-1], "content": convo[-1]["content"] + " /no_think"}

    last_user = next((m.get("content", "") for m in reversed(messages)
                      if m.get("role") == "user"), "")
    log.info("chat >> model=%s | tools=%d | повідомл.=%d | '%s'",
             model, len(tools), len(messages), last_user[:80])

    tools_used = []
    async with httpx2.AsyncClient(timeout=CHAT_TIMEOUT) as client:
        for step in range(1, max_steps + 1):
            t0 = time.perf_counter()
            try:
                response = await client.post(f"{OLLAMA_URL}/api/chat", json={
                    "model": model, "messages": convo, "tools": tools,
                    "stream": False, "think": False, "keep_alive": "15m",
                    "options": {"temperature": 0.2, "num_predict": 512}})
            except Exception as exc:
                log.warning("chat FAIL крок %d | %.0f ms | %s: %s", step,
                            (time.perf_counter() - t0) * 1000,
                            exc.__class__.__name__, str(exc)[:160])
                return {"reply": None, "tools_used": tools_used,
                        "error": f"ШІ не відповів за {CHAT_TIMEOUT:.0f} с "
                                 f"({exc.__class__.__name__})"}
            ms = (time.perf_counter() - t0) * 1000
            if response.status_code != 200:
                log.warning("chat FAIL крок %d | HTTP %s | %.0f ms | %s",
                            step, response.status_code, ms, response.text[:160])
                return {"reply": None, "tools_used": tools_used,
                        "error": f"Ollama {response.status_code}: {response.text[:200]}"}
            message = response.json().get("message", {})
            calls = message.get("tool_calls") or []
            if not calls:
                log.info("chat << крок %d | %.0f ms | фінал %dc | всього tools=%s",
                         step, ms, len(message.get("content") or ""),
                         [t["name"] for t in tools_used])
                return {"reply": _strip_think(message.get("content")),
                        "tools_used": tools_used}
            log.info("chat << крок %d | %.0f ms | модель просить: %s",
                     step, ms, [c["function"]["name"] for c in calls])
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
                log.info("chat: MCP %s %s", name,
                         json.dumps(args, ensure_ascii=False)[:200])
                mt0 = time.perf_counter()
                result = await host.call(name, args)
                log.info("chat: MCP %s ← %.0f ms | %s", name,
                         (time.perf_counter() - mt0) * 1000,
                         "error" if isinstance(result, dict) and result.get("error")
                         else "ok")
                tools_used.append({"name": name, "args": args})
                convo.append({"role": "tool", "tool_name": name,
                              "content": json.dumps(result, ensure_ascii=False)[:4000]})
    log.warning("chat: перевищено ліміт кроків (%d)", max_steps)
    return {"reply": "(перевищено ліміт кроків)", "tools_used": tools_used}


# ---------------------------------------------------------------------------
# Розбір наміру без моделі
# ---------------------------------------------------------------------------
# Коли Ollama не піднята, вимикати поле вводу — погане рішення: гість пише,
# а йому мовчать. Тут простий роутер за ключовими словами доводить фразу до
# того самого сценарію. Він гірший за модель, але чесніший за німоту.
_INTENTS = [
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
]

_MEALS = ("сніданок", "обід", "вечеря", "десерт")


def route_intent(text: str) -> dict:
    """Фраза → сценарій. Повертає {tool, args, why} або None, якщо не впізнав."""
    low = (text or "").lower()
    amount = None
    for token in re.findall(r"\d+", low):
        if 30 <= int(token) <= 100000:
            amount = float(token)
            break

    for keys, tool, args, why in _INTENTS:
        if not any(k in low for k in keys):
            continue
        args = dict(args)
        if tool == "meal_pack":
            for meal in _MEALS:
                if meal[:5] in low:
                    args["meal"] = meal
                    break
            if amount:
                args["max_uah"] = amount
        elif amount and "max_uah" in args:
            args["max_uah"] = amount
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
