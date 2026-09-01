"""Live-міст до реального Silpo MCP (https://mcp.silpo.ua/mcp).

Пряме підключення до streamable-HTTP ендпоінта MCP «Сільпо» з OAuth-токеном,
який mcp-remote зберіг у ~/.mcp-auth після входу в Claude Desktop. Токен
читається свіжим при кожному підключенні (перелогін підхоплюється сам).

Можливості: реальний пошук товарів (find_products_batch), вибір міста/магазину,
реальні купони/промо/лояльність. Кошик і checkout НЕ чіпаємо (лишаються на моці),
щоб не змінювати справжній кошик користувача.
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
from contextlib import asynccontextmanager

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

URL = "https://mcp.silpo.ua/mcp"
DELIVERY_TYPE = "SelfPickup"

_lock = asyncio.Lock()
_branches: list[dict] = []          # кеш усіх магазинів
_ctx: dict = {}                     # branchId, branch_label, timeslotStart/End
_proposed: list[dict] = []          # пропонований кошик (live) — БЕЗ мутації справжнього


def _proposed_view() -> dict:
    """Пропонований live-кошик у тій самій формі, що й мок-кошик (для UI)."""
    items, total = [], 0.0
    for i, p in enumerate(_proposed):
        price = p.get("price") or 0
        items.append({"product_id": f"live-{i}", "name": p["name"], "price_uah": price,
                      "quantity": 1, "line_total_uah": price, "in_stock": True,
                      "image": p.get("image")})
        total += price
    return {"items": items, "item_count": len(items), "total_uah": round(total, 2),
            "source": "live"}


async def live_cart() -> dict:
    return _proposed_view()


async def live_impact() -> dict:
    items, total, saved, names = 0, 0.0, 0.0, []
    for p in _proposed:
        price = p.get("price") or 0
        total += price
        op = p.get("old_price")
        if op and op > price:
            saved += op - price
        names.append(p["name"])
        items += 1
    return {"items": items, "total_uah": round(total, 2),
            "saved_uah": round(saved, 2), "names": names}


async def live_clear() -> dict:
    _proposed.clear()
    return _proposed_view()


async def live_remove(product_id: str) -> dict:
    try:
        idx = int(str(product_id).split("-")[1])
    except (IndexError, ValueError):
        idx = -1
    if 0 <= idx < len(_proposed):
        _proposed.pop(idx)
    return _proposed_view()


class LiveError(Exception):
    pass


def _token() -> str:
    files = glob.glob(os.path.expanduser("~/.mcp-auth/mcp-remote-*/*_tokens.json"))
    if not files:
        raise LiveError("Немає OAuth-токена. Увійди в silpo через Claude Desktop.")
    data = json.load(open(max(files, key=os.path.getmtime), encoding="utf-8"))
    if not data.get("access_token"):
        raise LiveError("У кеші немає access_token — перелогінься в silpo.")
    return data["access_token"]


def _text(res) -> str:
    return "\n".join(getattr(c, "text", "") for c in res.content if getattr(c, "text", None))


@asynccontextmanager
async def _session():
    headers = {"Authorization": f"Bearer {_token()}"}
    async with httpx2.AsyncClient(headers=headers, timeout=60) as http:
        async with streamable_http_client(URL, http_client=http) as st:
            async with ClientSession(st[0], st[1]) as s:
                await s.initialize()
                yield s


def _branch_label(b: dict) -> str:
    return f'{b.get("city","")}, {b.get("address","")}'.strip(", ")


# ---------------------------------------------------------------------------
# Товари
# ---------------------------------------------------------------------------
def _map_product(p: dict) -> dict:
    price, old = p.get("price"), p.get("oldPrice")
    out = {"id": p.get("id"), "name": p.get("name", "?"), "brand": "",
           "unit": p.get("displayRatio", ""), "category": "Сільпо",
           "price": price, "old_price": old,
           "in_stock": bool(p.get("available", True)), "image": p.get("image")}
    if old and price and old > price:
        out["discount_percent"] = round((old - price) / old * 100)
    return out


async def _load_branches(s: ClientSession) -> None:
    global _branches
    if _branches:
        return
    data = json.loads(_text(await s.call_tool("silpo_list_branches", {})))
    _branches = data.get("branches", [])


async def _set_slot(s: ClientSession) -> None:
    """Оновлює слот у контексті для поточного branchId."""
    slots = json.loads(_text(await s.call_tool(
        "silpo_get_time_slots",
        {"branchId": _ctx["branchId"], "deliveryTypes": [DELIVERY_TYPE], "limit": 5},
    ))).get("slots", [])
    if not slots:
        raise LiveError("Немає слотів для обраного магазину.")
    _ctx["timeslotStart"] = slots[0]["start"]
    _ctx["timeslotEnd"] = slots[0]["end"]


async def _ensure_ctx(s: ClientSession) -> None:
    if _ctx.get("branchId") and _ctx.get("timeslotStart"):
        return
    await _load_branches(s)
    # Пріоритет — великий київський магазин (повніший асортимент для демо)
    branch = (next((b for b in _branches
                    if b.get("city") == "Київ" and b.get("hasPickup") and b.get("open")), None)
              or next((b for b in _branches if b.get("hasPickup") and b.get("open")), None)
              or (_branches[0] if _branches else None))
    if not branch:
        raise LiveError("Не вдалося отримати магазини.")
    _ctx["branchId"] = branch["branchId"]
    _ctx["branch_label"] = _branch_label(branch)
    await _set_slot(s)


# ---------------------------------------------------------------------------
# Публічні функції
# ---------------------------------------------------------------------------
async def live_status() -> dict:
    try:
        _token()
    except LiveError as e:
        return {"available": False, "reason": str(e)}
    return {"available": True, "branch": _ctx.get("branch_label")}


async def live_cities() -> dict:
    """Список міст, де є магазини (для селектора)."""
    async with _lock:
        try:
            async with _session() as s:
                await _load_branches(s)
        except Exception as e:
            return {"error": str(e), "cities": []}
    cities = sorted({b.get("city", "") for b in _branches if b.get("city")})
    return {"cities": cities}


async def live_branches(city: str | None = None, limit: int = 40) -> dict:
    """Магазини (за містом) для селектора."""
    async with _lock:
        try:
            async with _session() as s:
                await _load_branches(s)
        except Exception as e:
            return {"error": str(e), "branches": []}
    items = [b for b in _branches if b.get("hasPickup")]
    if city:
        items = [b for b in items if b.get("city") == city]
    return {"branches": [{"branchId": b["branchId"], "label": _branch_label(b),
                          "address": b.get("address", "")} for b in items[:limit]]}


async def set_branch(branch_id: str) -> dict:
    """Обрати конкретний магазин як контекст пошуку."""
    async with _lock:
        try:
            async with _session() as s:
                await _load_branches(s)
                b = next((x for x in _branches if x["branchId"] == branch_id), None)
                if not b:
                    return {"error": "Магазин не знайдено"}
                _ctx["branchId"] = branch_id
                _ctx["branch_label"] = _branch_label(b)
                await _set_slot(s)
        except Exception as e:
            return {"error": str(e)}
    return {"ok": True, "branch": _ctx["branch_label"]}


async def live_search(query: str, limit: int = 12) -> dict:
    async with _lock:
        try:
            async with _session() as s:
                await _ensure_ctx(s)
                raw = _text(await s.call_tool("silpo_find_products_batch", {
                    "branchId": _ctx["branchId"], "deliveryType": DELIVERY_TYPE,
                    "timeslotStart": _ctx["timeslotStart"], "timeslotEnd": _ctx["timeslotEnd"],
                    "products": [query], "limit": limit}))
            data = json.loads(raw)
            products = [_map_product(p) for q in data.get("queries", []) for p in q.get("products", [])]
            return {"query": query, "count": len(products), "results": products,
                    "source": "live", "branch": _ctx.get("branch_label")}
        except LiveError as e:
            return {"error": str(e), "source": "live", "results": []}
        except Exception as e:
            return {"error": f"Live silpo недоступний ({type(e).__name__}). "
                            f"Можливо, протух токен — зроби запит до silpo у Claude Desktop.",
                    "source": "live", "results": []}


_THEME_QUERIES = [
    (("кіно", "фільм", "movie", "серіал"), ["попкорн", "кока кола", "шоколад молочний", "чіпси"]),
    (("італ", "паста", "карбонар"), ["спагеті", "соус томатний", "пармезан"]),
    (("мексик", "тако", "буріто"), ["тортилья", "квасоля", "сальса"]),
    (("вечірк", "party", "гост"), ["чіпси", "кока кола", "піца"]),
    (("спорт", "білок", "фітнес", "трену"), ["куряче філе", "йогурт", "батончик протеїновий"]),
    (("сніданок", "ранок"), ["йогурт", "кава мелена", "хліб"]),
    (("суші", "япон"), ["рис", "соєвий соус", "норі"]),
]


_NON_FOOD = ["корм для", "котів", "для собак", "зубна паста", "паста зубна",
             "шампунь", "гель для", "мило", "підгуз", "серветк", "туалетн",
             "для тварин", "освіжувач", "порошок пральн"]


def _is_non_food(name: str) -> bool:
    n = name.lower()
    return any(w in n for w in _NON_FOOD)


# Розширення алергій/несмаків: одне слово → усі релевантні підрядки в назвах.
_ALLERGY_EXPAND = {
    "горіх": ["горіх", "арахіс", "фундук", "мигдал", "кеш", "волоськ", "лісов", "пекан", "фісташ", "nut"],
    "арахіс": ["арахіс", "горіх"],
    "лактоз": ["молок", "вершк", "сметан", "масло", "йогурт"],
    "глютен": ["глютен", "пшенич", "борошн"],
    "риб": ["риб", "лосос", "тунець", "оселед", "макрель", "форел", "креветк", "морепродукт"],
    "яйц": ["яйц", "яєчн"],
    "гриб": ["гриб", "печериц"],
    "цитрус": ["цитрус", "апельсин", "лимон", "мандарин", "грейпфрут"],
}


def _expand_avoid(avoid: list[str]) -> list[str]:
    """Розширює перелік небажаного: 'горіхи' → також арахіс/фундук/мигдаль тощо."""
    out = set()
    for a in avoid or []:
        al = a.lower().strip()
        if not al:
            continue
        out.add(al)
        for key, syns in _ALLERGY_EXPAND.items():
            if key in al or al in key:
                out.update(syns)
    return list(out)


def _queries_for(theme: str) -> list[str]:
    t = theme.lower()
    for keys, qs in _THEME_QUERIES:
        if any(k in t for k in keys):
            return qs
    return [theme]


async def live_build_cart(theme: str, max_uah: float | None = None,
                          avoid: list[str] | None = None) -> dict:
    """Збирає ПРОПОНОВАНИЙ кошик із РЕАЛЬНИХ товарів «Сільпо» через офіційний MCP.

    Використовує silpo_find_products_batch (справжній пошук) за темою, враховує
    алергії/несмаки та бюджет. НЕ мутує справжній кошик — повертає пропозицію,
    яку користувач може підтвердити сам.
    """
    avoid_l = _expand_avoid(avoid or [])
    queries = _queries_for(theme)
    async with _lock:
        try:
            async with _session() as s:
                await _ensure_ctx(s)
                raw = _text(await s.call_tool("silpo_find_products_batch", {
                    "branchId": _ctx["branchId"], "deliveryType": DELIVERY_TYPE,
                    "timeslotStart": _ctx["timeslotStart"], "timeslotEnd": _ctx["timeslotEnd"],
                    "products": queries, "limit": 3}))
            data = json.loads(raw)
        except Exception as e:
            return {"error": f"Live silpo недоступний ({type(e).__name__}).", "source": "live"}

    added, total = [], 0.0
    for q in data.get("queries", []):
        query = (q.get("query") or "")
        stem = query.split()[0].lower()[:4] if query else ""
        prods = [_map_product(p) for p in q.get("products", [])]
        # лише товари, назва яких містить корінь запиту (відсіює криві фаззі-збіги
        # реального пошуку). Немає збігу — пропускаємо запит, а не додаємо сміття.
        relevant = [p for p in prods
                    if stem and stem in p["name"].lower() and not _is_non_food(p["name"])]
        if not relevant:
            continue
        relevant.sort(key=lambda x: (x["price"] or 1e9))
        for mp in relevant:
            hay = mp["name"].lower()
            if any(a and a in hay for a in avoid_l):
                continue
            price = mp["price"] or 0
            if max_uah and total + price > max_uah:
                continue
            added.append({"name": mp["name"], "price": price, "image": mp.get("image"),
                          "old_price": mp.get("old_price")})
            total += price
            break
    _proposed[:] = added  # ЗАМІНЮЄ пропонований кошик (UI його покаже)
    return {"theme": theme, "budget_uah": max_uah, "added": added,
            "total_uah": round(total, 2), "source": "live",
            "branch": _ctx.get("branch_label"),
            "note": "Пропонований кошик із реальних товарів Сільпо (без оформлення)."}


async def live_add_product(name: str) -> dict:
    """Знаходить ОДИН реальний товар «Сільпо» за назвою і додає в пропонований кошик."""
    res = await live_search(name, limit=1)
    if res.get("error"):
        return res
    if not res["results"]:
        return {"error": f"Не знайшов «{name}» у Сільпо.", "source": "live"}
    p = res["results"][0]
    item = {"name": p["name"], "price": p["price"], "image": p.get("image"),
            "old_price": p.get("old_price")}
    _proposed.append(item)  # додаємо до пропонованого кошика
    return {"added": item, "source": "live", "cart_total_uah": _proposed_view()["total_uah"],
            "note": "Реальний товар Сільпо додано в пропозицію."}


async def live_coupons() -> dict:
    async with _lock:
        try:
            async with _session() as s:
                data = json.loads(_text(await s.call_tool("silpo_get_my_coupons", {})))
        except Exception as e:
            return {"error": str(e), "coupons": []}
    coupons = [{"id": c.get("id"), "title": c.get("description", ""),
                "period": f'{c.get("beginDate","")}–{c.get("endDate","")}',
                "note": (c.get("warningText") or "").strip(),
                "image": c.get("image"), "active": c.get("active", True)}
               for c in data.get("coupons", [])]
    return {"coupons": coupons}


async def live_promos() -> dict:
    async with _lock:
        try:
            async with _session() as s:
                data = json.loads(_text(await s.call_tool("silpo_get_my_promos", {})))
        except Exception as e:
            return {"error": str(e), "promos": []}
    promos = [{"id": p.get("promoId"), "title": p.get("description", ""),
               "reward": p.get("rewardText", ""),
               "period": f'{p.get("beginDate","")}–{p.get("endDate","")}',
               "image": p.get("image"), "selected": p.get("selected", False)}
              for p in data.get("promos", [])]
    return {"promos": promos}


async def live_loyalty() -> dict:
    async with _lock:
        try:
            async with _session() as s:
                data = json.loads(_text(await s.call_tool("silpo_get_loyalty_info", {})))
        except Exception as e:
            return {"error": str(e)}
    loy = data.get("loyalty", {})
    bal = loy.get("balance", {})
    return {"balance": bal.get("total"), "currency": bal.get("currency", "UAH"),
            "type": loy.get("card", {}).get("typeName")}
