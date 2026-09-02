"""Паки — збережені набори реальних товарів «Сільпо».

Пак — центральний обʼєкт продукту: іменований набір, який можна зібрати з
підказкою AI, оптимізувати під власні купони/акції, підмінити в ньому окремий
товар і одним рухом перетворити на справжній кошик.

Тут — лише зберігання й арифметика. Пошук товарів, альтернативи та знижки
живуть у facade.py, бо ходять у реальний MCP.
"""

from __future__ import annotations

import json
import os
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, ".mcp", "packs.json")

# Поля товару в паку. product_id/company_id/branch_id потрібні, щоб покласти
# позицію у справжній кошик через silpo_add_or_update_cart_products.
ITEM_FIELDS = ("product_id", "external_id", "company_id", "branch_id", "slug", "name",
               "price", "old_price", "image", "qty", "query", "note", "swapped_from",
               "weighted", "multibuy")


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _pid() -> str:
    return "pk-" + uuid.uuid4().hex[:6]


def _load() -> dict:
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"packs": []}
    data.setdefault("packs", [])
    return data


def _save(store: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def normalize_item(raw: dict) -> dict:
    item = {k: raw.get(k) for k in ITEM_FIELDS}
    qty = float(raw.get("qty") or 1)
    item["qty"] = int(qty) if qty == int(qty) else round(qty, 3)
    item["price"] = float(raw.get("price") or 0)
    if raw.get("old_price"):
        item["old_price"] = float(raw["old_price"])
    return item


def totals(pack: dict) -> dict:
    """Сума пака, «до знижки» і скільки вже зекономлено на самих цінниках."""
    final = base = 0.0
    for it in pack.get("items", []):
        qty = it.get("qty") or 1
        price = it.get("price") or 0
        final += price * qty
        base += (it.get("old_price") or price) * qty
    return {"item_count": len(pack.get("items", [])),
            "total_uah": round(final, 2),
            "base_uah": round(base, 2),
            "saved_uah": round(base - final, 2)}


def _view(pack: dict) -> dict:
    return {**pack, **totals(pack)}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def create(name: str, items: list[dict], budget_uah: float | None = None,
           tags: list[str] | None = None, source: str = "agent",
           avoid: list[str] | None = None) -> dict:
    store = _load()
    pack = {
        "id": _pid(), "name": name or "Без назви",
        "items": [normalize_item(i) for i in items],
        "budget_uah": budget_uah, "tags": tags or [], "source": source,
        "avoid": avoid or [],
        "created_at": _now(), "updated_at": _now(),
        "saved": False, "published": False, "uses": 0,
        "optimization": None,
    }
    store["packs"].append(pack)
    _save(store)
    return _view(pack)


def get(pack_id: str) -> dict | None:
    for pack in _load()["packs"]:
        if pack["id"] == pack_id:
            return _view(pack)
    return None


def latest() -> dict | None:
    """Останній пак — щоб модель могла не тягати pack_id у кожному виклику."""
    packs = _load()["packs"]
    return _view(packs[-1]) if packs else None


def list_packs(saved_only: bool = False, limit: int = 20) -> list[dict]:
    packs = _load()["packs"]
    if saved_only:
        packs = [p for p in packs if p.get("saved")]
    return [_view(p) for p in packs[-limit:][::-1]]


def _mutate(pack_id: str, fn) -> dict | None:
    store = _load()
    for pack in store["packs"]:
        if pack["id"] == pack_id:
            fn(pack)
            pack["updated_at"] = _now()
            _save(store)
            return _view(pack)
    return None


def update(pack_id: str, **fields) -> dict | None:
    return _mutate(pack_id, lambda p: p.update(
        {k: v for k, v in fields.items() if v is not None}))


def set_items(pack_id: str, items: list[dict]) -> dict | None:
    return _mutate(pack_id, lambda p: p.update(
        {"items": [normalize_item(i) for i in items]}))


def add_item(pack_id: str, item: dict) -> dict | None:
    return _mutate(pack_id, lambda p: p["items"].append(normalize_item(item)))


def remove_item(pack_id: str, product_id: str) -> dict | None:
    return _mutate(pack_id, lambda p: p.update(
        {"items": [i for i in p["items"] if str(i.get("product_id")) != str(product_id)]}))


def replace_item(pack_id: str, product_id: str, new_item: dict) -> dict | None:
    """Підміна товару зі збереженням сліду: swapped_from = стара назва."""
    def _swap(pack: dict) -> None:
        for idx, old in enumerate(pack["items"]):
            if str(old.get("product_id")) == str(product_id):
                fresh = normalize_item(new_item)
                fresh["qty"] = old.get("qty") or 1
                fresh["query"] = old.get("query")
                fresh["swapped_from"] = old.get("name")
                pack["items"][idx] = fresh
                return
    return _mutate(pack_id, _swap)


def delete(pack_id: str) -> bool:
    store = _load()
    before = len(store["packs"])
    store["packs"] = [p for p in store["packs"] if p["id"] != pack_id]
    _save(store)
    return len(store["packs"]) < before


def record_use(pack_id: str) -> dict | None:
    return _mutate(pack_id, lambda p: p.update({"uses": (p.get("uses") or 0) + 1}))
