"""Чат-агент на локальному Qwen через Ollama, керований по MCP.

Інструменти БЕРУТЬСЯ ДИНАМІЧНО з MCP-серверів (profile + silpo-mock) через
MCPHost, і виклики моделі маршрутизуються назад у ці сервери по MCP-протоколу.
Тобто це справжній «Qwen + MCP».

Для стабільності маленької моделі показуємо їй КУРОВАНИЙ набір інструментів
(високорівневі build_cart/add_product + ключові), а не всі ~30.
"""

from __future__ import annotations

import json
import os
import re

import httpx2

from web import silpo_live

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "")  # порожньо = авто-вибір

_PREFERRED = ["qwen2.5:3b", "qwen2.5:7b", "qwen2.5:3b-instruct",
              "llama3.2:3b", "qwen2.5", "qwen3:4b", "qwen3:1.7b", "qwen3"]

# Інструменти MCP, які показуємо моделі (щоб не перевантажувати 3B усіма 30).
ALLOWED = {
    "build_cart", "add_product", "get_cart", "prepare_checkout",
    "find_recipe", "get_coupons",
    "get_profile", "update_profile", "remember_fact", "check_triggers", "get_rewards",
}

SYSTEM = (
    "Ти — AI Food Assistant «Сільпо». Твоя мета — ДІЯТИ інструментами, а не розмовляти. "
    "Відповідай коротко, українською.\n"
    "• Зібрати НОВИЙ набір під подію/бюджет ('вечір кіно до 300 грн', 'італійський "
    "вечір') — build_cart (theme + max_uah). Він ЗАМІНЮЄ вміст кошика.\n"
    "• Додати ОДИН конкретний товар ('додай каву', 'ще молоко') — add_product (name). "
    "Він НЕ очищає кошик.\n"
    "• Проактивні ідеї 'що сьогодні' — check_triggers. Профіль — get_profile.\n"
    "• Важливі факти (улюблений фільм тощо) — remember_fact.\n"
    "Після дії коротко підсумуй результат (що зібрав і на яку суму). "
    "prepare_checkout лише готує замовлення — покупку підтверджує людина."
)


def _pick_model(models: list[str]) -> str:
    if MODEL:
        return MODEL
    for pref in _PREFERRED:
        for m in models:
            if m == pref or m.split(":")[0] == pref.split(":")[0]:
                return m
    return models[0] if models else "qwen2.5:3b"


def _strip_think(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    return text.replace("<think>", "").replace("</think>", "").strip()


async def chat_available() -> dict:
    try:
        async with httpx2.AsyncClient(timeout=3) as c:
            r = await c.get(f"{OLLAMA_URL}/api/tags")
            models = [m.get("name", "") for m in r.json().get("models", [])]
        return {"available": True, "model": _pick_model(models),
                "has_model": bool(models), "models": models}
    except Exception:
        return {"available": False, "model": "qwen2.5:3b",
                "hint": "Запусти Ollama та `ollama pull qwen2.5:3b`."}


async def _run_tool(fn: str, args: dict, host, source: str):
    """Виконати інструмент: у live-режимі build_cart/add_product ідуть у РЕАЛЬНИЙ
    Silpo MCP (через silpo_live), решта — у mock/profile через MCP-хост."""
    if source == "live" and fn == "build_cart":
        return await silpo_live.live_build_cart(
            args.get("theme", ""), args.get("max_uah"), args.get("avoid"))
    if source == "live" and fn == "add_product":
        return await silpo_live.live_add_product(args.get("name", ""))
    return await host.call(fn, args)


async def chat(messages: list[dict], host, source: str = "mock", max_steps: int = 6) -> dict:
    """Tool-loop через Ollama; інструменти по MCP через host.

    source='live' → build_cart/add_product виконуються реальним Silpo MCP.
    """
    status = await chat_available()
    if not status["available"]:
        return {"reply": None, "error":
                "Локальна модель недоступна. Встанови Ollama (https://ollama.com), "
                "виконай `ollama pull qwen2.5:3b` — і чат запрацює.", "tools_used": []}

    model = status["model"]
    tools = [t for t in host.tools if t["function"]["name"] in ALLOWED]

    convo = [{"role": "system", "content": SYSTEM}] + messages
    if model.startswith("qwen3") and convo and convo[-1]["role"] == "user":
        convo[-1] = {**convo[-1], "content": convo[-1]["content"] + " /no_think"}

    tools_used = []
    async with httpx2.AsyncClient(timeout=180) as c:
        for _ in range(max_steps):
            resp = await c.post(f"{OLLAMA_URL}/api/chat", json={
                "model": model, "messages": convo, "tools": tools,
                "stream": False, "think": False, "keep_alive": "15m",
                "options": {"temperature": 0.2, "num_predict": 512}})
            if resp.status_code != 200:
                return {"reply": None, "error": f"Ollama {resp.status_code}: {resp.text[:200]}",
                        "tools_used": tools_used}
            msg = resp.json().get("message", {})
            calls = msg.get("tool_calls") or []
            if not calls:
                return {"reply": _strip_think(msg.get("content")), "tools_used": tools_used}
            convo.append({"role": "assistant", "content": msg.get("content", ""),
                          "tool_calls": calls})
            for tc in calls:
                fn = tc["function"]["name"]
                raw = tc["function"].get("arguments")
                args = raw if isinstance(raw, dict) else json.loads(raw or "{}")
                # для build_cart автоматично підставляємо алергії/несмаки з профілю
                if fn == "build_cart" and "avoid" not in args:
                    prof = (await host.call("get_profile", {})).get("profile", {})
                    args["avoid"] = (prof.get("allergies", []) or []) + (prof.get("dislikes", []) or [])
                result = await _run_tool(fn, args, host, source)
                tools_used.append({"name": fn, "args": args,
                                   "source": source if fn in ("build_cart", "add_product") else "mcp"})
                convo.append({"role": "tool", "tool_name": fn,
                              "content": json.dumps(result, ensure_ascii=False)})
    return {"reply": "(перевищено ліміт кроків)", "tools_used": tools_used}
