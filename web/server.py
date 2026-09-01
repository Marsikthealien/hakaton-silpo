"""Веб-фронт для AI Food Assistant (хакатон Silpo) — тепер як MCP-хост.

Бекенд Starlette підключається до наших MCP-серверів (profile + silpo-mock) через
MCPHost і виконує ВСІ операції (пошук, кошик, профіль, чат) по MCP-протоколу.
Так і чат (Qwen), і UI ходять в один і той самий silpo-mock процес → спільний кошик.

Live-режим (реальний silpo) лишається окремо у web/silpo_live.py.

Запуск (з D:\\GAVNO):  python -m uvicorn web.server:app --port 8000
"""

from __future__ import annotations

import os

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from web.mcp_host import host
from web import silpo_live
from web import chat as chatmod

_HERE = os.path.dirname(os.path.abspath(__file__))
_INDEX = os.path.join(_HERE, "index.html")


def ok(data) -> JSONResponse:
    return JSONResponse(data)


async def index(request: Request):
    return FileResponse(_INDEX)


# --- Профіль / памʼять / тригери / нагороди (MCP: profile) -----------------
async def get_profile(request: Request):
    return ok(await host.call("get_profile", {}))


async def update_profile(request: Request):
    return ok(await host.call("update_profile", await request.json()))


async def reset_profile(request: Request):
    return ok(await host.call("reset_profile", {}))


async def remember_fact(request: Request):
    b = await request.json()
    return ok(await host.call("remember_fact", {"text": b["text"], "category": b.get("category")}))


async def get_facts(request: Request):
    return ok(await host.call("get_facts", {}))


async def triggers(request: Request):
    return ok(await host.call("check_triggers", {}))


async def rewards(request: Request):
    return ok(await host.call("get_rewards", {}))


async def grant_reward(request: Request):
    b = await request.json()
    return ok(await host.call("grant_reward",
                              {"title": b["title"], "discount": b["discount"]}))


# --- Товари / кошик (MCP: silpo-mock) або live -----------------------------
async def search(request: Request):
    q = request.query_params.get("q", "")
    if request.query_params.get("source") == "live":
        return ok(await silpo_live.live_search(q, limit=12))
    args = {"query": q, "limit": 12}
    tag = request.query_params.get("tag")
    mp = request.query_params.get("max_price")
    if tag:
        args["tag"] = tag
    if mp:
        args["max_price"] = float(mp)
    return ok(await host.call("search_products", args))


async def recipe(request: Request):
    return ok(await host.call("find_recipe", {"query": request.query_params.get("q", "")}))


async def cart(request: Request):
    if request.query_params.get("source") == "live":
        return ok(await silpo_live.live_cart())
    return ok(await host.call("get_cart", {}))


async def cart_add(request: Request):
    b = await request.json()
    return ok(await host.call("add_to_cart",
                              {"product_id": b["product_id"], "quantity": int(b.get("quantity", 1))}))


async def cart_add_many(request: Request):
    b = await request.json()
    return ok(await host.call("add_many_to_cart", {"product_ids": b["product_ids"]}))


async def cart_remove(request: Request):
    b = await request.json()
    if b.get("source") == "live":
        return ok(await silpo_live.live_remove(b["product_id"]))
    return ok(await host.call("remove_from_cart", {"product_id": b["product_id"]}))


async def cart_clear(request: Request):
    b = {}
    try:
        b = await request.json()
    except Exception:
        pass
    if b.get("source") == "live":
        return ok(await silpo_live.live_clear())
    return ok(await host.call("clear_cart", {}))


async def coupons(request: Request):
    if request.query_params.get("source") == "live":
        return ok(await silpo_live.live_coupons())
    return ok(await host.call("get_coupons", {}))


async def promos(request: Request):
    if request.query_params.get("source") == "live":
        return ok(await silpo_live.live_promos())
    return ok(await host.call("get_personal_promotions", {}))


async def slots(request: Request):
    return ok(await host.call("get_delivery_slots", {}))


async def checkout(request: Request):
    b = await request.json()
    return ok(await host.call("prepare_checkout",
                              {"coupon_id": b.get("coupon_id"),
                               "delivery_slot_id": b.get("delivery_slot_id")}))


# --- Live silpo (реальний) -------------------------------------------------
async def live_status(request: Request):
    return ok(await silpo_live.live_status())


async def live_cities(request: Request):
    return ok(await silpo_live.live_cities())


async def live_branches(request: Request):
    return ok(await silpo_live.live_branches(request.query_params.get("city") or None))


async def live_set_branch(request: Request):
    return ok(await silpo_live.set_branch((await request.json())["branchId"]))


async def live_loyalty(request: Request):
    return ok(await silpo_live.live_loyalty())


async def impact(request: Request):
    """Метрики для панелі Impact: товари, сума, заощаджено, алергени в кошику, нагороди."""
    source = request.query_params.get("source", "mock")
    if source == "live":
        base = await silpo_live.live_impact()
    else:
        base = await host.call("get_cart_impact", {})
    prof = (await host.call("get_profile", {})).get("profile", {})
    allergies = (prof.get("allergies", []) or []) + (prof.get("dislikes", []) or [])
    expanded = silpo_live._expand_avoid(allergies)
    names = base.get("names", [])
    allergens = sum(1 for n in names if any(a in n.lower() for a in expanded))
    rewards = (await host.call("get_rewards", {})).get("count", 0)
    return ok({"items": base.get("items", 0), "total_uah": base.get("total_uah", 0),
               "saved_uah": base.get("saved_uah", 0), "allergens": allergens,
               "rewards": rewards, "source": source})


# --- Чат (Qwen через MCP-хост) ---------------------------------------------
async def chat_status(request: Request):
    st = await chatmod.chat_available()
    st["mcp_tools"] = len(host.tools)
    return ok(st)


async def chat_send(request: Request):
    b = await request.json()
    return ok(await chatmod.chat(b.get("messages", []), host, b.get("source", "mock")))


routes = [
    Route("/", index),
    Route("/api/profile", get_profile, methods=["GET"]),
    Route("/api/profile", update_profile, methods=["POST"]),
    Route("/api/profile/reset", reset_profile, methods=["POST"]),
    Route("/api/fact", remember_fact, methods=["POST"]),
    Route("/api/facts", get_facts, methods=["GET"]),
    Route("/api/triggers", triggers, methods=["GET"]),
    Route("/api/rewards", rewards, methods=["GET"]),
    Route("/api/reward", grant_reward, methods=["POST"]),
    Route("/api/search", search, methods=["GET"]),
    Route("/api/recipe", recipe, methods=["GET"]),
    Route("/api/cart", cart, methods=["GET"]),
    Route("/api/cart/add", cart_add, methods=["POST"]),
    Route("/api/cart/add_many", cart_add_many, methods=["POST"]),
    Route("/api/cart/remove", cart_remove, methods=["POST"]),
    Route("/api/cart/clear", cart_clear, methods=["POST"]),
    Route("/api/coupons", coupons, methods=["GET"]),
    Route("/api/promos", promos, methods=["GET"]),
    Route("/api/slots", slots, methods=["GET"]),
    Route("/api/checkout", checkout, methods=["POST"]),
    Route("/api/live/status", live_status, methods=["GET"]),
    Route("/api/live/cities", live_cities, methods=["GET"]),
    Route("/api/live/branches", live_branches, methods=["GET"]),
    Route("/api/live/set_branch", live_set_branch, methods=["POST"]),
    Route("/api/live/loyalty", live_loyalty, methods=["GET"]),
    Route("/api/impact", impact, methods=["GET"]),
    Route("/api/chat/status", chat_status, methods=["GET"]),
    Route("/api/chat", chat_send, methods=["POST"]),
]


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    await host.start()
    try:
        yield
    finally:
        try:
            await host.stop()
        except Exception:
            pass  # anyio cancel-scope на shutdown — не критично


app = Starlette(routes=routes, lifespan=lifespan)
