"""Мок Silpo MCP — локальний імітатор MCP «Сільпо» для хакатону AI Factory.

Реалізує набір інструментів, приблизно відповідний реальному Silpo MCP:
пошук товарів, batch-пошук, кошик, слоти доставки, історія покупок,
харчові обмеження, родина, купони, персональні акції та «Власний Рахунок».

ВАЖЛИВО: усі дані фейкові (див. data.py). Оформлення замовлення (checkout)
навмисно НЕ виконується агентом — інструмент лише готує підтвердження, яке
має схвалити людина. Це відповідає правилам хакатону.

Функції нижче — звичайні Python-функції (легко тестувати, викликати одна з
одної та імпортувати з demo.py). Наприкінці файлу вони реєструються як MCP-tools
через ``mcp.add_tool(...)`` — це не залежить від версії SDK.

Запуск (stdio-транспорт):
    python -m silpo_mcp.server
"""

from __future__ import annotations

import copy
import difflib
from typing import Optional

try:
    # mcp 2.x: FastMCP перейменовано на MCPServer
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    try:
        # mcp 1.x: класичний FastMCP
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError as exc:  # pragma: no cover - дружня підказка замість трейсбека
        raise SystemExit(
            "Не знайдено пакет 'mcp'. Встанови залежності:\n"
            "    pip install -r requirements.txt\n"
            "або\n"
            "    pip install \"mcp[cli]\""
        ) from exc

try:
    # звичайний запуск як пакет: python -m silpo_mcp.server
    from . import data
except ImportError:
    # запуск файлу напряму (напр. `mcp dev silpo_mcp/server.py`):
    # пакетного контексту немає, тож додаємо теку файлу в sys.path
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import data  # type: ignore[no-redef]

mcp = _Server(
    "silpo-mock",
    instructions=(
        "Мок MCP «Сільпо». Використовуй ці інструменти, щоб шукати товари, "
        "збирати кошик і персоналізувати рекомендації на основі історії покупок, "
        "купонів та персональних акцій. Оформлення замовлення підтверджує людина — "
        "агент лише готує кошик і викликає prepare_checkout."
    ),
)

# ---------------------------------------------------------------------------
# Стан кошика (у памʼяті процесу): product_id -> quantity
# ---------------------------------------------------------------------------
_cart: dict[str, int] = {}


def _find_product(product_id: str) -> Optional[dict]:
    for p in data.PRODUCTS:
        if p["id"] == product_id:
            return p
    return None


def _token_matches(token: str, haystack: str, words: list[str]) -> bool:
    """Один токен запиту збігається з товаром — толерантно до одруківок.

    Порядок перевірок: точний підрядок → префікс (недодруковане слово) →
    нечіткий збіг за написанням (difflib) для слів довших за 2 символи.
    """
    if token in haystack:
        return True
    if len(token) <= 2:
        return False
    if any(w.startswith(token) or token.startswith(w) for w in words):
        return True
    # одруківка: є слово, близьке за написанням (напр. "карбонора" ~ "карбонара")
    return bool(difflib.get_close_matches(token, words, n=1, cutoff=0.78))


def _matches(product: dict, query: str) -> bool:
    q = query.lower().strip()
    if not q:
        return True
    haystack = " ".join(
        [product["name"], product["brand"], product["category"], *product["tags"]]
    ).lower()
    words = haystack.split()
    return all(_token_matches(token, haystack, words) for token in q.split())


def _public_product(product: dict) -> dict:
    """Копія товару з розрахованою знижкою для видачі клієнту."""
    out = copy.deepcopy(product)
    if product.get("old_price"):
        out["discount_percent"] = round(
            (product["old_price"] - product["price"]) / product["old_price"] * 100
        )
    return out


def _cart_view() -> dict:
    items = []
    total = 0.0
    for pid, qty in _cart.items():
        p = _find_product(pid)
        if not p:
            continue
        line = round(p["price"] * qty, 2)
        total += line
        items.append({
            "product_id": pid, "name": p["name"], "price_uah": p["price"],
            "quantity": qty, "line_total_uah": line, "in_stock": p["in_stock"],
        })
    return {"items": items, "item_count": sum(_cart.values()), "total_uah": round(total, 2)}


# ---------------------------------------------------------------------------
# Пошук товарів
# ---------------------------------------------------------------------------
def search_products(
    query: str,
    limit: int = 10,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    only_in_stock: bool = True,
    tag: Optional[str] = None,
) -> dict:
    """Шукає товари в каталозі «Сільпо».

    Args:
        query: пошуковий запит (напр. "спагеті", "попкорн", "куряче філе").
        limit: максимальна кількість результатів.
        category: фільтр за категорією (напр. "Снеки", "Бакалія").
        max_price: верхня межа ціни, грн.
        only_in_stock: показувати лише товари в наявності.
        tag: фільтр за тегом (напр. "італійська", "кіно", "веганське", "білок").
    """
    results = []
    for p in data.PRODUCTS:
        if not _matches(p, query):
            continue
        if category and p["category"].lower() != category.lower():
            continue
        if tag and tag.lower() not in [t.lower() for t in p["tags"]]:
            continue
        if max_price is not None and p["price"] > max_price:
            continue
        if only_in_stock and not p["in_stock"]:
            continue
        results.append(_public_product(p))
    results.sort(key=lambda x: x["price"])
    return {"query": query, "count": len(results[:limit]), "results": results[:limit]}


def batch_search_products(queries: list[str], limit_per_query: int = 3) -> dict:
    """Виконує кілька пошукових запитів за один виклик (batch-пошук).

    Зручно, коли AI одразу шукає всі інгредієнти страви або набір снеків.

    Args:
        queries: список запитів, напр. ["спагеті", "бекон", "пармезан", "яйця"].
        limit_per_query: скільки результатів повертати на кожен запит.
    """
    out = {}
    for q in queries:
        out[q] = search_products(q, limit=limit_per_query)["results"]
    return {"batches": out}


def get_product(product_id: str) -> dict:
    """Повертає детальну інформацію про товар за його id."""
    p = _find_product(product_id)
    if not p:
        return {"error": f"Товар {product_id} не знайдено"}
    return _public_product(p)


# ---------------------------------------------------------------------------
# Рецепти / страви
# ---------------------------------------------------------------------------
def find_recipe(query: str) -> dict:
    """Знаходить рецепт/страву за назвою чи кухнею та повертає перелік потрібних товарів.

    Приклади query: "карбонара", "мексиканська", "вечір кіно", "суші".
    """
    q = query.lower().strip()
    matches = []
    for r in data.RECIPES:
        hay = f"{r['name']} {r['cuisine']}".lower()
        if any(tok in hay for tok in q.split()):
            products = [_public_product(_find_product(pid))
                        for pid in r["product_ids"] if _find_product(pid)]
            total = round(sum(p["price"] for p in products), 2)
            matches.append({**r, "products": products, "estimated_total_uah": total})
    return {"query": query, "count": len(matches), "recipes": matches}


# ---------------------------------------------------------------------------
# Кошик
# ---------------------------------------------------------------------------
def get_cart() -> dict:
    """Показує поточний вміст кошика та загальну суму."""
    return _cart_view()


def add_to_cart(product_id: str, quantity: int = 1) -> dict:
    """Додає товар до кошика.

    Args:
        product_id: id товару (див. search_products).
        quantity: кількість (за замовчуванням 1).
    """
    p = _find_product(product_id)
    if not p:
        return {"error": f"Товар {product_id} не знайдено"}
    if not p["in_stock"]:
        return {"error": f"Товару «{p['name']}» немає в наявності"}
    if quantity < 1:
        return {"error": "Кількість має бути щонайменше 1"}
    _cart[product_id] = _cart.get(product_id, 0) + quantity
    return {"added": {"product_id": product_id, "name": p["name"], "quantity": quantity},
            "cart": _cart_view()}


def add_many_to_cart(product_ids: list[str]) -> dict:
    """Додає одразу кілька товарів (по 1 шт кожного) — зручно для готового набору/рецепта."""
    added, errors = [], []
    for pid in product_ids:
        res = add_to_cart(pid, 1)
        if "error" in res:
            errors.append({"product_id": pid, "error": res["error"]})
        else:
            added.append(res["added"])
    return {"added": added, "errors": errors, "cart": _cart_view()}


def remove_from_cart(product_id: str) -> dict:
    """Видаляє товар із кошика повністю."""
    if product_id in _cart:
        del _cart[product_id]
        return {"removed": product_id, "cart": _cart_view()}
    return {"error": f"Товару {product_id} немає в кошику"}


def clear_cart() -> dict:
    """Повністю очищає кошик."""
    _cart.clear()
    return {"cleared": True, "cart": _cart_view()}


# ---------------------------------------------------------------------------
# Персоналізація: історія, дієта, родина, купони, акції, рахунок
# ---------------------------------------------------------------------------
def get_purchase_history(channel: str = "all", limit: int = 10) -> dict:
    """Повертає історію покупок користувача (онлайн та офлайн).

    Args:
        channel: "all", "online" або "offline".
        limit: скільки останніх покупок повернути.
    """
    hist = data.PURCHASE_HISTORY
    if channel in ("online", "offline"):
        hist = [h for h in hist if h["channel"] == channel]
    enriched = []
    for h in hist[:limit]:
        items = []
        for it in h["items"]:
            p = _find_product(it["product_id"])
            items.append({"product_id": it["product_id"],
                          "name": p["name"] if p else "?", "qty": it["qty"]})
        enriched.append({**h, "items": items})
    return {"channel": channel, "count": len(enriched), "history": enriched}


def get_frequently_bought(top: int = 5) -> dict:
    """Аналізує історію покупок і повертає товари, які купуються найчастіше.

    Корисно для проактивних підказок («молоко скоро закінчиться»,
    «ти часто береш пасту — зробимо італійський вечір?»).
    """
    counts: dict[str, int] = {}
    for h in data.PURCHASE_HISTORY:
        for it in h["items"]:
            counts[it["product_id"]] = counts.get(it["product_id"], 0) + it["qty"]
    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top]
    out = []
    for pid, qty in ranked:
        p = _find_product(pid)
        out.append({"product_id": pid, "name": p["name"] if p else "?", "times_bought": qty})
    return {"top": out}


def get_dietary_restrictions() -> dict:
    """Повертає харчові обмеження користувача: алергії, дієти, нелюбимі продукти."""
    return data.USER_PROFILE["dietary_restrictions"]


def get_family() -> dict:
    """Повертає склад родини та їхні дієтичні особливості (для сімейного кошика)."""
    return {"family": data.USER_PROFILE["family"]}


def get_coupons() -> dict:
    """Повертає доступні купони користувача."""
    return {"coupons": data.COUPONS}


def get_personal_promotions() -> dict:
    """Повертає персональні акції (персональні ціни на основі поведінки користувача)."""
    promos = []
    for pr in data.PERSONAL_PROMOTIONS:
        p = _find_product(pr["product_id"])
        promos.append({**pr, "name": p["name"] if p else "?"})
    return {"promotions": promos}


def get_own_account() -> dict:
    """Повертає стан «Власного Рахунку» (баланс, рівень, бали лояльності)."""
    return data.USER_PROFILE["own_account"]


# ---------------------------------------------------------------------------
# Доставка та оформлення
# ---------------------------------------------------------------------------
def get_delivery_slots(only_available: bool = True) -> dict:
    """Повертає доступні слоти доставки."""
    slots = data.DELIVERY_SLOTS
    if only_available:
        slots = [s for s in slots if s["available"]]
    return {"slots": slots}


def prepare_checkout(delivery_slot_id: Optional[str] = None,
                     coupon_id: Optional[str] = None) -> dict:
    """Готує оформлення замовлення для ПІДТВЕРДЖЕННЯ ЛЮДИНОЮ.

    ВАЖЛИВО: цей інструмент НЕ виконує покупку і не списує кошти. Він лише
    формує підсумок замовлення (кошик, знижка за купоном, доставка) та повертає
    посилання/токен, за яким користувач сам підтверджує оплату. Так вимагають
    правила хакатону: агент не завершує checkout автоматично.

    Args:
        delivery_slot_id: id обраного слоту доставки (get_delivery_slots).
        coupon_id: id купона для застосування (get_coupons).
    """
    cart = _cart_view()
    if not cart["items"]:
        return {"error": "Кошик порожній — немає що оформлювати"}

    subtotal = cart["total_uah"]
    discount = 0.0
    applied_coupon = None
    if coupon_id:
        coupon = next((c for c in data.COUPONS if c["id"] == coupon_id), None)
        if not coupon:
            return {"error": f"Купон {coupon_id} не знайдено"}
        if subtotal < coupon.get("min_order_uah", 0):
            return {"error": f"Для купона потрібне замовлення від {coupon['min_order_uah']} грн"}
        cats = [c.lower() for c in coupon.get("applies_to_categories", [])]
        eligible = 0.0
        for it in cart["items"]:
            p = _find_product(it["product_id"])
            if p and (not cats or p["category"].lower() in cats):
                eligible += it["line_total_uah"]
        if "discount_percent" in coupon:
            discount = round(eligible * coupon["discount_percent"] / 100, 2)
        elif "discount_uah" in coupon:
            discount = min(coupon["discount_uah"], eligible)
        applied_coupon = coupon["title"]

    delivery = None
    delivery_price = 0.0
    if delivery_slot_id:
        delivery = next((s for s in data.DELIVERY_SLOTS if s["id"] == delivery_slot_id), None)
        if not delivery or not delivery["available"]:
            return {"error": f"Слот {delivery_slot_id} недоступний"}
        delivery_price = delivery["price_uah"]

    total = round(subtotal - discount + delivery_price, 2)
    return {
        "status": "PENDING_HUMAN_CONFIRMATION",
        "message": "Замовлення готове. Підтвердіть оплату вручну за посиланням.",
        "confirmation_url": "https://silpo.ua/checkout/confirm?token=MOCK-DEMO-TOKEN",
        "summary": {
            "items": cart["items"],
            "subtotal_uah": subtotal,
            "coupon": applied_coupon,
            "discount_uah": discount,
            "delivery": delivery["window"] if delivery else None,
            "delivery_price_uah": delivery_price,
            "total_uah": total,
        },
    }


# ---------------------------------------------------------------------------
# Високорівневі інструменти (зручні для невеликих LLM: без роботи з product_id)
# ---------------------------------------------------------------------------
_THEME_QUERIES = [
    (("кіно", "фільм", "movie", "серіал"), ["попкорн", "кола", "шоколад", "начос"]),
    (("італ", "паста", "карбонар"), ["паста", "соус", "сир"]),
    (("мексик", "тако", "буріто"), ["тортилья", "квасоля", "сальса"]),
    (("вечірк", "party", "гост"), ["снеки", "напої", "піца"]),
    (("спорт", "білок", "фітнес", "трену"), ["куряче філе", "йогурт", "протеїн"]),
    (("сніданок", "ранок"), ["йогурт", "кава", "хліб"]),
    (("суші", "япон"), ["рис", "соєвий", "норі"]),
]


def _queries_for(theme: str) -> list[str]:
    t = theme.lower()
    for keys, queries in _THEME_QUERIES:
        if any(k in t for k in keys):
            return queries
    return [theme]


def build_cart(theme: str, max_uah: Optional[float] = None,
               avoid: Optional[list[str]] = None) -> dict:
    """Збирає кошик під тему/подію: пошук → фільтр небажаного → бюджет → додавання.

    ЗАМІНЮЄ поточний вміст кошика. Уся логіка на сервері — LLM не працює з id.

    Args:
        theme: тема/подія, напр. "вечір кіно", "італійський вечір".
        max_uah: бюджет у грн (необовʼязково).
        avoid: список слів для виключення (алергії/несмаки), напр. ["горіхи"].
    """
    avoid_l = [a.lower() for a in (avoid or [])]
    picks: list[dict] = []
    rec = find_recipe(theme)
    if rec["recipes"]:
        picks = list(rec["recipes"][0]["products"])
    else:
        for q in _queries_for(theme):
            res = search_products(q, limit=3)
            if res["results"]:
                picks.append(res["results"][0])

    def blocked(p):
        hay = (p["name"] + " " + " ".join(p.get("tags", []))).lower()
        return any(a and a in hay for a in avoid_l)
    picks = [p for p in picks if not blocked(p)]

    clear_cart()
    total, added = 0.0, []
    for p in picks:
        if max_uah and total + p["price"] > max_uah:
            continue
        add_to_cart(p["id"], 1)
        total += p["price"]
        added.append({"name": p["name"], "price": p["price"]})
    return {"theme": theme, "budget_uah": max_uah, "added": added,
            "total_uah": round(total, 2)}


def get_cart_impact() -> dict:
    """Метрики кошика для панелі Impact: к-сть, сума, заощаджено на акціях, назви."""
    items, total, saved, names = 0, 0.0, 0.0, []
    for pid, qty in _cart.items():
        p = _find_product(pid)
        if not p:
            continue
        items += qty
        total += p["price"] * qty
        if p.get("old_price"):
            saved += (p["old_price"] - p["price"]) * qty
        names.append(p["name"])
    return {"items": items, "total_uah": round(total, 2),
            "saved_uah": round(saved, 2), "names": names}


def add_product(name: str) -> dict:
    """Знаходить ОДИН товар за назвою і додає до поточного кошика (не очищає)."""
    res = search_products(name, limit=1)
    if not res["results"]:
        return {"error": f"Не знайшов «{name}» у каталозі."}
    p = res["results"][0]
    add_to_cart(p["id"], 1)
    return {"added": {"name": p["name"], "price": p["price"]},
            "cart_total_uah": get_cart()["total_uah"]}


# ---------------------------------------------------------------------------
# Реєстрація інструментів як MCP-tools
# ---------------------------------------------------------------------------
for _fn in (
    search_products, batch_search_products, get_product, find_recipe,
    get_cart, add_to_cart, add_many_to_cart, remove_from_cart, clear_cart,
    get_purchase_history, get_frequently_bought, get_dietary_restrictions,
    get_family, get_coupons, get_personal_promotions, get_own_account,
    get_delivery_slots, prepare_checkout,
    build_cart, add_product, get_cart_impact,
):
    mcp.add_tool(_fn)


def main() -> None:
    """Точка входу: запуск MCP-сервера через stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
