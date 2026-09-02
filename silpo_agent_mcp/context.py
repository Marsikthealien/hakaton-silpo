"""Контекст кошика — ключ до більшості tools «Сільпо».

22 з 40 інструментів (пошук, деталі товару, акції, набори, історія чеків)
вимагають branchId + deliveryType + timeslot. Джерело правди для них —
активний кошик користувача, тому тут ми його знаходимо або створюємо один раз
і далі роздаємо контекст усім іншим модулям.
"""

from __future__ import annotations

from .silpo import SilpoError, silpo

DELIVERY_TYPE = "SelfPickup"
DEFAULT_CITY = "Київ"


async def pick_branch(city: str | None = None, branch_id: str | None = None) -> dict:
    """Обирає магазин: за id, або перший відкритий із самовивозом у місті."""
    data = await silpo.call("silpo_list_branches", {"hasPickup": True})
    branches = data.get("branches", [])
    if branch_id:
        found = next((b for b in branches if b["branchId"] == branch_id), None)
        if found:
            return found
    target = city or DEFAULT_CITY
    return (next((b for b in branches if b.get("city") == target and b.get("open")), None)
            or next((b for b in branches if b.get("open")), None)
            or (branches[0] if branches else None))


async def first_free_slot(branch_id: str) -> dict:
    """Перший доступний слот самовивозу.

    Параметр start не передаємо: ISO з мікросекундами повертає порожній список,
    а без нього сервер сам віддає найближчі 81 слот.
    """
    data = await silpo.call("silpo_get_time_slots", {
        "branchId": branch_id, "deliveryTypes": [DELIVERY_TYPE], "limit": 100})
    free = [s for s in data.get("slots", []) if s.get("available")]
    if not free:
        raise SilpoError(f"Немає доступних слотів самовивозу для магазину {branch_id}")
    return free[0]


def _from_cart(cart: dict) -> dict:
    """Витягує контекст із відповіді silpo_get_shopping_cart_by_id."""
    shipment = (cart.get("shipments") or [{}])[0]
    slot = cart.get("timeslot") or {}
    return {
        "shoppingCartId": cart.get("id") or cart.get("shoppingCartId"),
        "branchId": shipment.get("branchId") or cart.get("branchId"),
        "companyId": shipment.get("companyId"),
        "deliveryType": cart.get("deliveryType") or DELIVERY_TYPE,
        "timeslotStart": slot.get("start"),
        "timeslotEnd": slot.get("end"),
    }


async def ensure(city: str | None = None, branch_id: str | None = None) -> dict:
    """Повертає готовий контекст, створивши кошик за потреби. Кешується в silpo.ctx."""
    if silpo.ctx.get("shoppingCartId") and silpo.ctx.get("timeslotStart") and not branch_id:
        return silpo.ctx

    existing = await silpo.call("silpo_get_my_shopping_cart", {})
    cart_id = existing.get("shoppingCartId") if existing.get("exists") else None

    if cart_id:
        detail = await silpo.call("silpo_get_shopping_cart_by_id", {"shoppingCartId": cart_id})
        ctx = _from_cart(detail.get("cart") or detail)
        ctx["shoppingCartId"] = ctx["shoppingCartId"] or cart_id
    else:
        branch = await pick_branch(city, branch_id)
        if not branch:
            raise SilpoError("Не вдалося отримати список магазинів.")
        slot = await first_free_slot(branch["branchId"])
        created = await silpo.call("silpo_create_shopping_cart", {
            "addressType": "self-pickup",
            "latitude": float(branch["latitude"]),
            "longitude": float(branch["longitude"]),
            "city": branch.get("city"),
            "deliveryType": DELIVERY_TYPE,
            "timeslot": {"start": slot["start"], "end": slot["end"]},
            "branchId": branch["branchId"],
        })
        ctx = {
            "shoppingCartId": created.get("shoppingCartId") or created.get("id"),
            "branchId": branch["branchId"],
            "companyId": branch["companyId"],
            "deliveryType": DELIVERY_TYPE,
            "timeslotStart": slot["start"],
            "timeslotEnd": slot["end"],
        }

    if not ctx.get("shoppingCartId"):
        raise SilpoError("Не вдалося отримати shoppingCartId.")
    silpo.ctx.update(ctx)
    return silpo.ctx


def search_ctx() -> dict:
    """Чотири поля, яких вимагають пошукові tools."""
    return {k: silpo.ctx[k] for k in
            ("branchId", "deliveryType", "timeslotStart", "timeslotEnd")}


async def cart_details(fix_slot: bool = True) -> dict:
    """Деталі кошика. Протухлий слот лагодимо на місці, а не показуємо гостю.

    Кошик живе довше за слот: створений увечері, зранку він уже має
    `timeslot.not_available` — і це попередження тягнеться в кожен екран.
    """
    ctx = await ensure()
    detail = await silpo.call("silpo_get_shopping_cart_by_id",
                              {"shoppingCartId": ctx["shoppingCartId"]})
    if not fix_slot:
        return detail
    cart = detail.get("cart") or detail
    stale = any((v.get("message") or "").startswith("timeslot")
                for v in ((cart.get("calculation") or {}).get("validations") or []))
    if stale:
        from . import facade
        try:
            await facade.refresh_timeslot()
        except SilpoError:
            return detail
        detail = await silpo.call("silpo_get_shopping_cart_by_id",
                                  {"shoppingCartId": ctx["shoppingCartId"]})
    return detail
