"""MCP-сервер агента: те, що бачить модель.

Сирі 40 tools «Сільпо» вимагають branchId, companyId, timeslot і довгих
ланцюжків — маленька локальна модель на цьому ламається. Тут вона отримує
16 інструментів рівня сценарію з простими аргументами, а всередині кожного
відпрацьовують справжні silpo_*-tools (їх видно через mcp_trace).

Запуск (stdio):  python -m silpo_agent_mcp.server
"""

from __future__ import annotations

import functools
import inspect
from typing import Optional

try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp 2.x
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP as _Server      # mcp 1.x

from . import facade, packs, proposed, weights
from .silpo import SilpoError, silpo

mcp = _Server(
    "silpo-agent",
    instructions=(
        "Агент паків «Сільпо» поверх офіційного MCP. Пак — іменований набір "
        "реальних товарів: збери (build_pack), відтвори з чека (pack_from_receipt), "
        "візьми готовий набір «Сільпо» (browse_sets → pack_from_set) або поповни "
        "звичне (reorder_pack). Далі optimize_pack покаже, які купони й промо "
        "спрацюють і де вигідно взяти більше, swap_item підмінить позицію, "
        "save_pack збереже, pack_to_cart покладе у СПРАВЖНІЙ кошик. "
        "Хто перед тобою — who_am_i (реальні чеки, а не анкета). "
        "Оформлення замовлення завжди підтверджує людина."
    ),
)


def _safe(fn):
    """Помилку віддаємо даними, а не винятком: інакше модель губить нитку діалогу."""
    if inspect.iscoroutinefunction(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except SilpoError as exc:
                return {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001 — модель має отримати текст, а не трейсбек
                return {"error": f"{type(exc).__name__}: {exc}"}
    else:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except SilpoError as exc:
                return {"error": str(exc)}
            except Exception as exc:  # noqa: BLE001
                return {"error": f"{type(exc).__name__}: {exc}"}
    return wrapper


# ---------------------------------------------------------------------------
# Пошук — тонка обгортка, щоб модель отримувала короткий результат
# ---------------------------------------------------------------------------
async def search_products(queries: list[str], limit: int = 5) -> dict:
    """Шукає реальні товари «Сільпо» за переліком запитів (до 30 за раз).

    Args:
        queries: що шукати, напр. ["попкорн", "кола"].
        limit: скільки варіантів на кожен запит.
    """
    found = await facade.search(queries, limit=limit)
    return {"results": {
        query: [{"product_id": p.get("id"), "name": p.get("name"),
                 "price_uah": p.get("price"), "old_price_uah": p.get("oldPrice"),
                 "in_stock": bool(p.get("available")), "unit": p.get("displayRatio")}
                for p in products]
        for query, products in found.items()}}


async def get_pack(pack_id: str) -> dict:
    """Повний вміст пака за id."""
    pack = packs.get(pack_id)
    return pack or {"error": f"Пак {pack_id} не знайдено."}


async def delete_pack(pack_id: str) -> dict:
    """Видаляє пак."""
    return {"deleted": packs.delete(pack_id)}


async def cart_status() -> dict:
    """Що зараз у справжньому кошику «Сільпо» — з розкладкою як на чекауті."""
    detail = await facade.context.cart_details()
    cart = detail.get("cart") or detail
    calc = cart.get("calculation") or {}
    delivery = calc.get("delivery") or {}
    products = (cart.get("shipments") or [{}])[0].get("products") or []
    goods = calc.get("productsTotal") or 0
    total = calc.get("total") or 0
    service = round(total - goods - (delivery.get("total") or 0), 2)
    return {
        "items": [{"product_id": p.get("productId"), "slug": p.get("slug"),
                   "name": p.get("name"), "image": p.get("image"),
                   "unit": p.get("ratio"), "qty": p.get("quantity"),
                   "step": p.get("addToBasketStep") or 1,
                   "price_uah": p.get("price"), "old_price_uah": p.get("oldPrice"),
                   "line_total_uah": p.get("total"),
                   "discount_percent": (round((p["oldPrice"] - p["price"]) / p["oldPrice"] * 100)
                                        if p.get("oldPrice") and p.get("price") else None)}
                  for p in products],
        "goods_uah": goods, "service_uah": service if service > 0 else 0,
        "delivery_uah": delivery.get("total") or 0,
        "weight_kg": delivery.get("totalWeight"),
        "discount_uah": calc.get("subDiscount"), "total_uah": total,
        "delivery_type": facade.delivery_label(cart.get("deliveryType") or ""),
        "slot": ((cart.get("timeslot") or {}).get("start") or "")[11:16],
        "warnings": [v for v in (calc.get("validations") or []) if v.get("level") != "info"],
        "checkout_url": facade.CHECKOUT_URL,
    }


def _named(name: str, fn):
    """Реєструє функцію під імʼям майбутнього офіційного tool «Сільпо»."""
    wrapped = _safe(fn)
    wrapped.__name__ = name
    return wrapped


# Те, чого в MCP «Сільпо» ще немає. Назви — такі, якими вони мали б бути;
# у трейсі позначені як proposed, щоб демо не видавало бажане за наявне.
PROPOSED = (
    ("silpo_find_recipes", proposed.find_recipes),
    ("silpo_get_product_composition", proposed.get_product_composition),
    ("silpo_also_bought", proposed.also_bought),
    ("silpo_estimate_delivery", proposed.estimate_delivery),
    ("silpo_get_family_preferences", proposed.get_family_preferences),
    ("silpo_set_member_preferences", proposed.set_member_preferences),
    ("silpo_record_swipe", proposed.record_swipe),
    ("silpo_get_swipes", proposed.get_swipes),
    ("silpo_select_promos", proposed.select_promos),
    ("silpo_pantry_sync", proposed.pantry_sync),
    ("silpo_pantry_missing", proposed.pantry_missing),
    ("silpo_wellbeing_sync", proposed.wellbeing_sync),
    ("silpo_wellbeing_state", proposed.wellbeing_state),
    ("silpo_list_connectors", proposed.connectors),
    ("silpo_connect_source", proposed.connect),
    ("silpo_get_store_layout", proposed.store_route),
    ("silpo_save_store_layout", proposed.save_store_route),
    ("silpo_add_family_recipe", proposed.add_family_recipe),
    ("silpo_get_family_recipes", proposed.family_recipes),
    ("silpo_find_recipes_online", proposed.find_recipe_online),
    ("silpo_get_taste_weights", weights.snapshot),
    ("silpo_bump_taste_weight", weights.bump),
    ("silpo_rebuild_taste_weights", weights.rebuild_from_receipts),
)

TOOLS = (
    facade.who_am_i, facade.receipts,
    search_products, facade.browse_sets,
    facade.build_pack, facade.pack_from_receipt, facade.pack_from_set,
    facade.reorder_pack, facade.mood_pack, facade.evening_pack,
    facade.meal_pack, facade.breakfast_pack, facade.scenarios,
    facade.product_card, facade.cart_weight_check, facade.order_risk,
    facade.savings_report,
    facade.optimize_pack, facade.swap_item,
    facade.alternatives, facade.swap_to,
    facade.save_pack, facade.my_packs, get_pack, delete_pack,
    facade.pack_to_cart, cart_status,
    facade.set_cart_quantity, facade.remove_from_cart, facade.refresh_timeslot,
    facade.find_address, facade.my_perks, facade.expiring, facade.payment_hint, facade.screen_pack,
    facade.set_branch, facade.mcp_trace,
)

for _fn in TOOLS:
    mcp.add_tool(_safe(_fn))

for _name, _impl in PROPOSED:
    mcp.add_tool(_named(_name, _impl))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
