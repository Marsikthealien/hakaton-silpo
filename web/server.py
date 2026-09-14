"""Веб-бекенд AI Pack Agent (хакатон «Сільпо» AI Factory) — як MCP-хост.

Starlette не має власної бізнес-логіки: усе, що робить UI, він робить викликами
MCP-tools через MCPHost. Ті самі інструменти бачить і Qwen, тож чат і інтерфейс
працюють з одним станом і одним джерелом правди.

Запуск:  python -m uvicorn web.server:app --port 8000
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from silpo_agent_mcp import voice
from web import chat as chatmod
from web.mcp_host import host

_HERE = os.path.dirname(os.path.abspath(__file__))


# Панель «Що відбувається» опитує трейс постійно — у журналі доступу це
# суцільна стіна з /api/trace, за якою не видно жодного справжнього запиту.
class _QuietTrace(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/trace" not in record.getMessage()


logging.getLogger("uvicorn.access").addFilter(_QuietTrace())


def page(name: str):
    """Статична сторінка з теки web/.

    `no-store` тут не перестраховка, а виправлення реального збою. FileResponse
    віддає лише ETag і Last-Modified, без Cache-Control — і браузер застосовує
    евристичне кешування: бере app.css та app.js зі свого кешу, НЕ перепитуючи
    сервер. Під час роботи над інтерфейсом це дає найгіршу з можливих картин:
    свіжий HTML із застарілими стилями й скриптом. Сторінка розсипається, а в
    консолі порожньо. На демо таке ловити нема коли.
    """
    async def handler(request: Request):
        return FileResponse(os.path.join(_HERE, name),
                            headers={"Cache-Control": "no-store, must-revalidate"})
    handler.__name__ = f"page_{name.split('.')[0]}"
    return handler


def ok(data) -> JSONResponse:
    return JSONResponse(data)


async def qr(request: Request):
    """QR-код як SVG — для запрошення в компанію.

    Текст будь-який, але призначення одне: посилання `/join?crew=…`, яке
    організатор показує з екрана, а гість читає камерою. Генерується тут,
    щоб не тягнути у фронт бібліотеку заради однієї картинки.
    """
    import io

    import segno

    text = (request.query_params.get("text") or "").strip()[:512]
    if not text:
        return Response("порожньо", status_code=400)
    buf = io.BytesIO()
    segno.make(text, error="m").save(buf, kind="svg", scale=6, border=2,
                                     dark="#0F1729", light=None)
    return Response(buf.getvalue(), media_type="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


async def body(request: Request) -> dict:
    try:
        return await request.json()
    except Exception:
        return {}


def tool_route(tool: str, *, from_query: tuple[str, ...] = (), casts: dict | None = None):
    """Маршрут = один MCP-tool. Аргументи беремо з JSON-тіла або з query-рядка."""
    casts = casts or {}

    async def handler(request: Request):
        args = dict(await body(request)) if request.method == "POST" else {}
        for key in from_query:
            value = request.query_params.get(key)
            if value not in (None, ""):
                args[key] = value
        for key, cast in casts.items():
            if args.get(key) not in (None, ""):
                try:
                    args[key] = cast(args[key])
                except (TypeError, ValueError):
                    args.pop(key)
        return ok(await host.call(tool, {k: v for k, v in args.items() if v is not None}))

    handler.__name__ = f"call_{tool}"
    return handler


def scenario_route(tool: str, casts: dict | None = None):
    """Сценарний маршрут: алергії з profile MCP підставляємо самі.

    Забути про них модель або UI не мають права — це не вподобання, а обмеження.
    """
    casts = casts or {}

    async def handler(request: Request):
        args = await body(request)
        for key, cast in casts.items():
            if args.get(key) not in (None, ""):
                try:
                    args[key] = cast(args[key])
                except (TypeError, ValueError):
                    args.pop(key)
        profile = (await host.call("get_profile", {})).get("profile", {})
        if "avoid" not in args:
            avoid = (profile.get("allergies") or []) + (profile.get("dislikes") or [])
            if avoid:
                args["avoid"] = avoid
        # Акційне — завжди спершу: перемикача в профілі більше немає.
        if "prefer_promo" not in args and profile.get("bonus_first", True):
            args["prefer_promo"] = True
        if tool in ("meal_pack", "family_pack") and "equipment" not in args \
                and profile.get("equipment"):
            args["equipment"] = profile["equipment"]
        return ok(await host.call(tool, args))

    handler.__name__ = f"scenario_{tool}"
    return handler


async def auth_status(request: Request):
    """Стан токена «Сільпо» — без розкриття самого токена."""
    from silpo_agent_mcp import auth
    info = auth.token_info()
    info["login_command"] = ".venv/bin/python -m silpo_agent_mcp.login"
    return ok(info)


async def auth_set(request: Request):
    """Підставити свіжий access_token вручну."""
    from silpo_agent_mcp import auth
    payload = await body(request)
    try:
        info = auth.save_access_token(payload.get("access_token", ""),
                                      payload.get("refresh_token"))
    except auth.AuthMissing as exc:
        return ok({"error": str(exc)})
    await host.call("set_branch", {})  # підняти новий сеанс на свіжому токені
    return ok(info)


async def auth_forget(request: Request):
    from silpo_agent_mcp import auth
    return ok(auth.forget_tokens())


async def deck(request: Request):
    """Колода «Департаменту дивинок». Логіка живе в MCP-tool, не тут."""
    limit = int(request.query_params.get("limit", 12))
    return ok(await host.call("silpo_get_swipe_deck", {"limit": limit}))


async def preferences(request: Request):
    """Усе, що впливає на підбір: наші вподобання + дієти з акаунта «Сільпо»."""
    profile = (await host.call("get_profile", {})).get("profile", {})
    return ok({"profile": profile, "scenarios": await host.call("scenarios", {})})


async def search(request: Request):
    query = request.query_params.get("q", "")
    limit = int(request.query_params.get("limit", 8))
    return ok(await host.call("search_products", {"queries": [query], "limit": limit}))


async def status(request: Request):
    """Чи все підключено: MCP-tools, модель, реальний «Сільпо»."""
    chat_status = await chatmod.chat_available()
    trace = await host.call("mcp_trace", {"limit": 1})
    return ok({"mcp_tools": len(host.tools),
               "servers": sorted(set(host.tool_server.values())),
               "silpo_calls": trace.get("total", 0),
               "model": chat_status.get("model"),
               "model_available": chat_status.get("available")})


async def tts_speak(request: Request):
    """Текст → WAV від Respeecher. Без ключа віддаємо 503, і фронт сам
    відкочується на браузерний синтез — демо не має падати через це."""
    payload = await body(request)
    text = (payload.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Порожній текст."}, status_code=400)
    try:
        audio = await voice.say(text, voice=payload.get("voice"))
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc), "fallback": "browser"}, status_code=503)
    except Exception as exc:  # noqa: BLE001 — мережа чи ліміт: фронт має знати текст
        return JSONResponse({"error": f"{type(exc).__name__}: {exc}",
                             "fallback": "browser"}, status_code=502)
    return Response(audio, media_type="audio/wav",
                    headers={"Cache-Control": "no-store"})


async def chat_status_route(request: Request):
    state = await chatmod.chat_available()
    state["mcp_tools"] = len(host.tools)
    return ok(state)


async def chat_narrate(request: Request):
    """Озвучення вже виконаного сценарію. Модель не відповіла → 502, і фронт
    показує помилку замість того, щоб мовчки підсунути шаблонний рядок."""
    payload = await body(request)
    out = await chatmod.narrate(payload.get("phrase", ""),
                                payload.get("result") or {},
                                payload.get("tool"))
    return JSONResponse(out, status_code=502 if out.get("error") else 200)


async def chat_send(request: Request):
    payload = await body(request)
    return ok(await chatmod.chat(payload.get("messages", []), host,
                                 pack_id=payload.get("pack_id") or None))


routes = [
    Route("/", page("index.html")),
    Route("/profile", page("profile.html")),
    Route("/game", page("game.html")),
    Route("/tech", page("tech.html")),
    Route("/join", page("join.html")),
    Route("/qr", qr),
    Route("/app.css", page("app.css")),
    Route("/app.js", page("app.js")),
    Route("/mushroom.png", page("mushroom.png")),
    Route("/mushroom.riv", page("mushroom.riv")),
    Route("/ava.js", page("ava.js")),
    Route("/api/status", status),
    Route("/api/scenarios", tool_route("scenarios")),
    Route("/api/preferences", preferences),
    Route("/api/auth", auth_status),
    Route("/api/auth/token", auth_set, methods=["POST"]),
    Route("/api/auth/forget", auth_forget, methods=["POST"]),

    # --- гість, чеки, знижки (silpo-agent → реальний MCP «Сільпо») ---
    Route("/api/me", tool_route("who_am_i")),
    Route("/api/receipts", tool_route("receipts", from_query=("limit",), casts={"limit": int})),
    Route("/api/perks", tool_route("my_perks")),
    Route("/api/sets", tool_route("browse_sets")),
    Route("/api/search", search),
    Route("/api/cart", tool_route("cart_status")),
    Route("/api/cart/qty", tool_route("set_cart_quantity"), methods=["POST"]),
    Route("/api/cart/remove", tool_route("remove_from_cart"), methods=["POST"]),
    Route("/api/trace", tool_route("mcp_trace", from_query=("limit",), casts={"limit": int})),
    Route("/api/branch", tool_route("set_branch"), methods=["POST"]),

    # --- паки ---
    Route("/api/packs", tool_route("my_packs", from_query=("saved_only",))),
    Route("/api/pack", tool_route("get_pack", from_query=("pack_id",))),
    Route("/api/pack/build", scenario_route("build_pack", {"max_uah": float}), methods=["POST"]),
    Route("/api/pack/from_receipt", scenario_route("pack_from_receipt", {"index": int}), methods=["POST"]),
    Route("/api/pack/from_set", scenario_route("pack_from_set", {"max_uah": float}), methods=["POST"]),
    Route("/api/pack/reorder", tool_route("reorder_pack"), methods=["POST"]),
    Route("/api/pack/mood", scenario_route("mood_pack", {"max_uah": float}), methods=["POST"]),
    Route("/api/pack/meal", scenario_route("meal_pack", {"max_uah": float}), methods=["POST"]),
    Route("/api/product", tool_route("product_card", from_query=("slug",)), methods=["GET", "POST"]),

    # --- запропоновані tools: у трейсі позначені як proposed ---
    Route("/api/recipes", tool_route("silpo_find_recipes", from_query=("meal", "query")), methods=["GET", "POST"]),
    Route("/api/composition", tool_route("silpo_get_product_composition", from_query=("slug",)), methods=["GET", "POST"]),
    Route("/api/also_bought", tool_route("silpo_also_bought", from_query=("product_name",)), methods=["GET", "POST"]),
    Route("/api/address", tool_route("find_address", from_query=("address",))),
    Route("/api/delivery", tool_route("silpo_estimate_delivery",
          casts={"latitude": float, "longitude": float, "cart_total_uah": float}), methods=["POST"]),
    Route("/api/family", tool_route("silpo_get_family_preferences")),
    Route("/api/family/member", tool_route("silpo_set_member_preferences"), methods=["POST"]),
    Route("/api/deck", deck),
    Route("/api/connectors", tool_route("silpo_list_connectors")),
    Route("/api/connect", tool_route("silpo_connect_source"), methods=["POST"]),
    Route("/api/weight", tool_route("cart_weight_check")),
    Route("/api/family/recipes", tool_route("silpo_get_family_recipes")),
    Route("/api/family/recipe", tool_route("silpo_add_family_recipe"), methods=["POST"]),
    Route("/api/swipe", tool_route("silpo_record_swipe"), methods=["POST"]),
    Route("/api/swipes", tool_route("silpo_get_swipes")),
    Route("/api/weights", tool_route("silpo_get_taste_weights")),
    Route("/api/weights/rebuild", tool_route("silpo_rebuild_taste_weights"), methods=["POST"]),
    Route("/api/promos/select", tool_route("silpo_select_promos"), methods=["POST"]),
    Route("/api/pantry", tool_route("silpo_pantry_sync"), methods=["POST"]),
    Route("/api/pantry/missing", tool_route("silpo_pantry_missing")),
    Route("/api/pantry/state", tool_route("silpo_pantry_state")),
    Route("/api/wellbeing", tool_route("silpo_wellbeing_sync"), methods=["POST"]),
    Route("/api/wellbeing/state", tool_route("silpo_wellbeing_state")),
    Route("/api/pack/optimize", tool_route("optimize_pack"), methods=["POST"]),
    Route("/api/pack/swap", tool_route("swap_item"), methods=["POST"]),
    Route("/api/pack/alternatives", tool_route("alternatives"), methods=["POST"]),
    Route("/api/pack/swap_to", tool_route("swap_to"), methods=["POST"]),
    Route("/api/pack/screen", tool_route("screen_pack"), methods=["POST"]),
    Route("/api/pack/precheck", tool_route("precheck_pack", casts={"latitude": float, "longitude": float}), methods=["POST"]),
    Route("/api/payment", tool_route("payment_hint", casts={"pack_total_uah": float}), methods=["POST"]),
    Route("/api/expiring", tool_route("expiring", from_query=("days",), casts={"days": int})),
    Route("/api/pack/add", tool_route("pack_add", casts={"qty": float}), methods=["POST"]),
    Route("/api/pack/remove", tool_route("pack_remove"), methods=["POST"]),
    Route("/api/pack/qty", tool_route("pack_set_qty", casts={"qty": float}), methods=["POST"]),
    Route("/api/pack/swap_named", tool_route("pack_swap_named"), methods=["POST"]),
    Route("/api/pack/save", tool_route("save_pack"), methods=["POST"]),
    Route("/api/pack/delete", tool_route("delete_pack"), methods=["POST"]),
    Route("/api/pack/to_cart", tool_route("pack_to_cart"), methods=["POST"]),

    # --- прозорість: сценарії та демо-дані ---
    Route("/api/flows", tool_route("agent_flows")),
    Route("/api/demo", tool_route("demo_data")),
    Route("/api/demo/set", tool_route("demo_set"), methods=["POST"]),
    Route("/api/demo/reset", tool_route("demo_reset"), methods=["POST"]),
    Route("/api/demo/clear", tool_route("demo_clear"), methods=["POST"]),

    # --- грибниця: рівні, скіни, досягнення ---
    Route("/api/game", tool_route("silpo_get_game_profile")),
    Route("/api/game/achievements", tool_route("silpo_get_achievements")),
    Route("/api/game/themed", tool_route("silpo_get_themed_branches")),
    Route("/api/game/skins", tool_route("silpo_get_skins")),
    Route("/api/game/skin", tool_route("silpo_set_skin"), methods=["POST"]),
    Route("/api/game/claim", tool_route("silpo_claim_level_reward",
          casts={"level": int}), methods=["POST"]),
    Route("/api/game/levels", tool_route("level_table",
          from_query=("upto",), casts={"upto": int})),

    # --- аналітика на наявних 40 tools ---
    Route("/api/coupons/audit", tool_route("coupon_audit")),
    Route("/api/coupons/detail", tool_route("coupon_detail",
          from_query=("business_coupon_id",), casts={"business_coupon_id": int})),
    Route("/api/savings", tool_route("savings_report")),
    Route("/api/spend", tool_route("spend_report",
          from_query=("window_days",), casts={"window_days": int})),
    Route("/api/impulse", tool_route("impulse_check", from_query=("name",)),
          methods=["GET", "POST"]),
    Route("/api/plus", tool_route("plus_check")),
    Route("/api/risk", tool_route("picking_risk", from_query=("pack_id",)),
          methods=["GET", "POST"]),

    # --- нові пак-сценарії ---
    Route("/api/pack/budget", scenario_route("budget_pack",
          {"budget_uah": float, "days": int}), methods=["POST"]),
    Route("/api/pack/weekly", scenario_route("weekly_pack",
          {"budget_uah": float}), methods=["POST"]),
    Route("/api/pack/kids", scenario_route("kids_pack", {"max_uah": float}),
          methods=["POST"]),
    Route("/api/pack/family", scenario_route("family_pack", {"max_uah": float}),
          methods=["POST"]),

    # --- компанія: разова група під подію (новий концепт) ---
    Route("/api/crew", tool_route("silpo_get_crew", from_query=("crew_id",))),
    Route("/api/crews", tool_route("silpo_list_crews")),
    Route("/api/crew/create", tool_route("silpo_create_crew",
          casts={"people": int}), methods=["POST"]),
    Route("/api/crew/join", tool_route("silpo_crew_join"), methods=["POST"]),
    Route("/api/crew/suggest", tool_route("silpo_crew_suggest"), methods=["POST"]),
    Route("/api/crew/leave", tool_route("silpo_crew_leave"), methods=["POST"]),
    Route("/api/crew/paid", tool_route("silpo_crew_paid",
          casts={"amount_uah": float}), methods=["POST"]),
    Route("/api/crew/split", tool_route("silpo_crew_split",
          casts={"total_uah": float}), methods=["POST"]),
    Route("/api/crew/delete", tool_route("silpo_delete_crew"), methods=["POST"]),
    Route("/api/crew/clear", tool_route("silpo_clear_crews"), methods=["POST"]),
    Route("/api/crew/share", tool_route("silpo_crew_share", casts={"amount_uah": float}), methods=["POST"]),
    Route("/api/crew/share/answer", tool_route("silpo_crew_share_answer"), methods=["POST"]),
    Route("/api/pack/crew", scenario_route("crew_pack", {"max_uah": float}),
          methods=["POST"]),

    # --- профіль (profile MCP: те, чого немає в акаунті «Сільпо») ---
    Route("/api/profile", tool_route("get_profile")),
    Route("/api/profile", tool_route("update_profile"), methods=["POST"]),
    Route("/api/profile/reset", tool_route("reset_profile"), methods=["POST"]),

    # --- голос ---
    Route("/api/voice", tool_route("voice_status")),
    Route("/api/voice/voices", tool_route("voice_list")),
    Route("/api/voice/key", tool_route("voice_set_key"), methods=["POST"]),
    Route("/api/tts", tts_speak, methods=["POST"]),

    # --- чат ---
    Route("/api/chat/status", chat_status_route),
    Route("/api/chat", chat_send, methods=["POST"]),
    Route("/api/chat/narrate", chat_narrate, methods=["POST"]),
]


@asynccontextmanager
async def lifespan(app):
    # Компанії разові: після перезапуску їх немає, і сценарій у чаті знову
    # починається з пропозиції створити.
    from silpo_agent_mcp import proposed as _proposed
    _proposed.clear_crews()
    await host.start()
    try:
        yield
    finally:
        try:
            await host.stop()
        except Exception:
            pass  # anyio cancel-scope на shutdown — не критично


app = Starlette(routes=routes, lifespan=lifespan)
