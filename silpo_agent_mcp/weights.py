"""Ваги смаку: наскільки гість любить конкретний товар і цілу категорію.

Ідея проста й чесніша за «рекомендаційний движок»: кожна дія гостя рухає вагу.
Купив — вага росте. Свайпнув уліво в «Департаменті дивинок» — падає. Замінив
позицію в паку — те, що прибрав, важить менше, те, що обрав, більше.

Вага буває відʼємною, і це не те саме, що алергія. Алергія — жорстке
виключення, її не обходить ніщо. Відʼємна вага — мʼяка нелюбов: якщо кращого
немає, товар усе одно можна запропонувати, просто останнім.

Категорія отримує вагу від своїх товарів. Тому агент, який бачить «−6 у
солодощах і +9 у рибі», підбирає інакше вже на рівні цілої полиці.

У «Сільпо» щось подібне є всередині (`/v1/profile/my/segments`,
`/v1/behavior-event`), але гість цього не бачить і не керує цим. Тут — бачить.
"""

from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, ".mcp", "weights.json")

# Скільки важить кожна дія. Свайп сильніший за покупку: покупка буває
# випадковою («треба було щось до чаю»), а свайп — це прямо висловлений смак.
EVENTS = {
    "purchase": 1.0,        # позиція у чеку
    "cart": 1.0,            # покладено в кошик агентом
    "swipe_right": 2.0,     # «Департамент дивинок»: подобається
    "swipe_left": -2.0,     # не показувати більше
    "swapped_out": -1.0,    # гість замінив цей товар на інший
    "swapped_in": 1.0,      # гість обрав цей замість запропонованого
    "removed": -1.0,        # прибрав із кошика
}

# Нижче цього товар вважаємо небажаним і ставимо в кінець черги.
DISLIKE = -3.0
CATEGORY_SHARE = 0.3        # частка ваги категорії у підсумковій вазі товару


def _key(name: str) -> str:
    """Ключ товару — перші два слова назви у нижньому регістрі.

    Повна назва не годиться: «Молоко «Галичина» 2,5% 870г» і «Молоко
    «Галичина» «Українське» 2,5%» — це для гостя те саме молоко.
    """
    import re
    clean = re.sub(r"[«»\"'`®™,.()]+", " ", (name or "").lower())
    return " ".join(clean.split()[:2])


# Сховище читається на КОЖЕН товар у видачі — без кешу це сотні читань файлу
# на один пак. Кеш скидається за mtime, тож зовнішня правка файлу помітна.
_CACHE: dict = {"mtime": None, "data": None}


def _load() -> dict:
    try:
        mtime = os.path.getmtime(STORE_PATH)
    except OSError:
        mtime = None
    if _CACHE["data"] is not None and _CACHE["mtime"] == mtime:
        return _CACHE["data"]
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("products", {})
    data.setdefault("categories", {})
    data.setdefault("log", [])
    _CACHE.update({"mtime": mtime, "data": data})
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    data["log"] = data["log"][-300:]
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        _CACHE.update({"mtime": os.path.getmtime(STORE_PATH), "data": data})
    except OSError:
        _CACHE.update({"mtime": None, "data": data})


def bump(name: str, event: str = "purchase", times: float = 1,
         category: str | None = None) -> dict:
    """Зсуває вагу товару й категорії за подією."""
    from .proposed import _aisle_of

    delta = EVENTS.get(event, 0) * times
    if not name or not delta:
        return {"skipped": True}
    data = _load()
    key = _key(name)
    slug = category or _aisle_of(name)[0]

    product = data["products"].setdefault(
        key, {"name": name, "weight": 0.0, "category": slug, "events": {}})
    product["weight"] = round(product["weight"] + delta, 2)
    product["name"] = name
    product["category"] = slug
    product["events"][event] = product["events"].get(event, 0) + times

    category_row = data["categories"].setdefault(slug, {"weight": 0.0})
    category_row["weight"] = round(category_row["weight"] + delta, 2)

    data["log"].append({"name": name, "event": event, "delta": delta,
                        "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    _save(data)
    return {"product": key, "weight": product["weight"], "category": slug,
            "category_weight": category_row["weight"], "event": event}


def weight_of(name: str) -> float:
    """Підсумкова вага товару: власна плюс частка ваги його категорії."""
    from .proposed import _aisle_of

    data = _load()
    own = (data["products"].get(_key(name)) or {}).get("weight", 0.0)
    slug = (data["products"].get(_key(name)) or {}).get("category") or _aisle_of(name)[0]
    category = (data["categories"].get(slug) or {}).get("weight", 0.0)
    return round(own + CATEGORY_SHARE * category, 2)


def known(name: str) -> bool:
    """Чи стикався гість із цим товаром узагалі — купував, свайпав, міняв.

    Це не те саме, що «любить»: свайп уліво теж робить товар знайомим. Саме
    тому «щось нове» і «щось знайоме» — різні осі, а не два кінці однієї.
    """
    return _key(name) in _load()["products"]


def category_weight_of(name: str) -> float:
    """Вага полиці, до якої належить товар.

    Потрібна для «щось нове»: серед незнайомого спершу показуємо те, що лежить
    на полиці, яку гість і так любить. Інакше «нове» вироджується у випадкове.
    """
    from .proposed import _aisle_of

    data = _load()
    row = data["products"].get(_key(name)) or {}
    slug = row.get("category") or _aisle_of(name)[0]
    return (data["categories"].get(slug) or {}).get("weight", 0.0)


def novelty_note(novelty: str) -> str:
    return {"new": "шукаю те, чого ти ще не брав — але з полиць, які ти любиш",
            "familiar": "беру перевірене: те, що вже було в чеках і сподобалось",
            }.get(novelty, "без обмежень за новизною")


def snapshot(limit: int = 12) -> dict:
    """Що агент знає про смаки — у вигляді, зрозумілому людині."""
    data = _load()
    from .proposed import SILPO_CATEGORIES
    titles = {c[0]: c[1] for c in SILPO_CATEGORIES}
    titles["inshe"] = "Інше"

    products = sorted(data["products"].values(), key=lambda p: -p["weight"])
    categories = sorted(
        ({"slug": k, "title": titles.get(k, k), "weight": v["weight"]}
         for k, v in data["categories"].items()),
        key=lambda c: -c["weight"])
    return {
        "loved": [{"name": p["name"], "weight": p["weight"]}
                  for p in products[:limit] if p["weight"] > 0],
        "disliked": [{"name": p["name"], "weight": p["weight"]}
                     for p in products[::-1][:limit] if p["weight"] < 0],
        "categories": categories,
        "tracked_products": len(products),
        "recent": data["log"][-10:][::-1],
        "note": ("Вага росте від покупок і свайпів вправо, падає від замін і свайпів "
                 "уліво. Відʼємна вага — мʼяка нелюбов, не алергія: якщо кращого немає, "
                 "товар усе одно запропонується, але останнім."),
    }


def reset() -> dict:
    _save({"products": {}, "categories": {}, "log": []})
    return {"reset": True}


async def rebuild_from_receipts(limit: int = 0) -> dict:
    """Будує ваги з нуля за реальними чеками — щоб профіль не був порожнім.

    Беремо ВСЮ історію, а не перші 10 чеків: `get_my_offline_orders` віддає
    десять за виклик, зате приймає `offset`. На десяти чеках профіль виходив
    сліпим — цілих полиць у ньому просто не було.
    """
    from .game import all_receipts

    reset()
    orders = await all_receipts()
    if limit:
        orders = orders[:limit]
    counted = 0
    for order in orders:
        for line in order.get("products", []):
            bump(line.get("name", ""), "purchase", float(line.get("quantity") or 1))
            counted += 1
    result = snapshot()
    result["built_from"] = {"receipts": len(orders), "lines": counted}
    return result
