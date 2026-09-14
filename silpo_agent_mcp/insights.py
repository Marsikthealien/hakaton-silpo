"""Сценарії, які нічого не додають до MCP — просто нарешті користуються ним.

Тут немає жодного `proposed`-tool: усе рахується з тих 40 інструментів, що вже
працюють. Причина, чому цього досі ніхто не робив, одна — ці сценарії живуть на
СТИКУ двох викликів. `get_my_coupons` знає, які купони видані;
`get_my_offline_orders.rewards[].promoId` знає, які спрацювали. Кожен окремо —
довідка. Разом — «за півроку ти не використав купонів на N гривень», і це вже
розмова.

Правило модуля: не вигадувати. Якщо число не виводиться з відповіді API, ми
його не показуємо, а називаємо, чого бракує.
"""

from __future__ import annotations

import datetime as dt

from . import context
from .silpo import SilpoError, silpo


def _today() -> dt.date:
    return dt.date.today()


def _date(value: str | None) -> dt.date | None:
    try:
        return dt.date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# 1. Чек-детектив: скільки купонів згоріло невикористаними
# ---------------------------------------------------------------------------
async def coupon_audit() -> dict:
    """Скільки купонів спрацювало, скільки згоріло і на яку суму.

    Звʼязок, на який вказує сама документація MCP: `promoId` у купоні — той
    самий, що в `rewards[]` чека. Тобто «купон спрацював» не треба вигадувати,
    це перевіряється точним збігом.
    """
    from .game import all_receipts

    coupons = (await silpo.call("silpo_get_my_coupons", {})).get("coupons") or []
    orders = await all_receipts()

    fired: dict[int, dict] = {}
    for order in orders:
        for reward in order.get("rewards") or []:
            promo = reward.get("promoId")
            if promo is None:
                continue
            row = fired.setdefault(promo, {"times": 0, "uah": 0.0, "last": None,
                                           "text": reward.get("applyText")})
            row["times"] += 1
            row["uah"] += reward.get("applyRewardAmount") or 0
            row["last"] = max(row["last"] or "", (order.get("createdAt") or "")[:10])

    today = _today()
    used, burning, dead = [], [], []
    for coupon in coupons:
        promo = coupon.get("promoId")
        ends = _date(coupon.get("endDate"))
        left = (ends - today).days if ends else None
        row = {
            "id": coupon.get("id"), "promo_id": promo,
            "about": coupon.get("description"),
            "reward": coupon.get("rewardText"),
            "value": coupon.get("rewardValue"),
            "unit": coupon.get("rewardUnit"),
            "ends": coupon.get("endDate"), "days_left": left,
            "image": coupon.get("image"),
            "activated": bool(coupon.get("active")),
        }
        if promo in fired:
            used.append({**row, **fired[promo]})
        elif left is not None and left < 0:
            dead.append(row)
        else:
            burning.append(row)

    burning.sort(key=lambda c: (c["days_left"] if c["days_left"] is not None else 99))
    saved = round(sum(f["uah"] for f in fired.values()), 2)
    # Ціну втрачених балобонусів рахуємо як гривні: 1 балобонус = 1 ₴.
    at_risk = round(sum((c["value"] or 0) for c in burning
                        if (c["unit"] or "").startswith("балобонус")), 2)

    return {
        "coupons_total": len(coupons),
        "used": used, "used_count": len(used), "saved_uah": saved,
        "burning": burning, "burning_count": len(burning), "at_risk_bonuses": at_risk,
        "expired_unused": dead, "expired_count": len(dead),
        "not_activated": [c for c in burning if not c["activated"]],
        "receipts_checked": len(orders),
        "headline": (f"Спрацювало {len(used)} купонів на {saved} ₴. "
                     f"Зараз згорає {len(burning)} — це ще {at_risk} балобонусів."),
        "how": ("coupon.promoId ↔ order.rewards[].promoId — точний збіг, не здогадка. "
                "На цей звʼязок вказує сама дока MCP «Сільпо»."),
        "gap": ("`get_my_coupons` не віддає `usedCount` — він є лише в "
                "`get_coupon_details`, тобто по одному купону за виклик. "
                "Історію ми відновлюємо з чеків, і це працює, але поле в списку "
                "було б дешевшим за 12 додаткових викликів."),
    }


async def coupon_detail(business_coupon_id: int) -> dict:
    """Деталі купона — тут живе `usedCount`, якого немає в списку."""
    data = await silpo.call("silpo_get_coupon_details",
                            {"businessCouponId": int(business_coupon_id)})
    coupon = data.get("coupon") or data
    return {"id": coupon.get("id"), "state": coupon.get("state"),
            "used_count": coupon.get("usedCount"),
            "about": coupon.get("description"), "reward": coupon.get("rewardText"),
            "ends": coupon.get("endDate"), "promo_id": coupon.get("promoId"),
            "limit_text": coupon.get("limitText")}


# ---------------------------------------------------------------------------
# 2. Доказ користі в гривнях
# ---------------------------------------------------------------------------
async def savings_report() -> dict:
    """Скільки гість зекономив насправді — по кожному чеку, з розкладкою.

    Єдина метрика, яку не треба вигадувати: `sumDiscount` у чеку каже, скільки
    зняли на касі, а `rewards[]` — за що саме.
    """
    from .game import all_receipts

    orders = await all_receipts()
    rows, by_promo = [], {}
    for order in orders:
        rewards = order.get("rewards") or []
        for reward in rewards:
            key = reward.get("promoId")
            row = by_promo.setdefault(key, {"promo_id": key, "times": 0, "uah": 0.0,
                                            "text": reward.get("applyText"),
                                            "group": reward.get("rewardGroupCodeName")})
            row["times"] += 1
            row["uah"] += reward.get("applyRewardAmount") or 0
        rows.append({
            "date": (order.get("createdAt") or "")[:10],
            "shop": order.get("filialName"),
            "paid_uah": order.get("sumReg"),
            "saved_uah": order.get("sumDiscount"),
            "bonuses": order.get("accruedBalaBonusesSum"),
            "rewards": [r.get("applyText") for r in rewards],
            "receipt_url": order.get("receiptUrl"),
            "magic_name": order.get("chequeMagicName"),
        })

    paid = round(sum(r["paid_uah"] or 0 for r in rows), 2)
    saved = round(sum(r["saved_uah"] or 0 for r in rows), 2)
    for row in by_promo.values():
        row["uah"] = round(row["uah"], 2)
    return {
        "receipts": rows[:20], "receipts_total": len(rows),
        "paid_uah": paid, "saved_uah": saved,
        "saved_share": round(saved / (paid + saved) * 100, 1) if paid else 0,
        "bonuses_uah": round(sum(r["bonuses"] or 0 for r in rows), 2),
        "by_promo": sorted(by_promo.values(), key=lambda r: -r["uah"]),
        "period": {"from": min((r["date"] for r in rows), default=None),
                   "to": max((r["date"] for r in rows), default=None)},
        "headline": f"За {len(rows)} чеків: сплачено {paid} ₴, знижок {saved} ₴.",
    }


# ---------------------------------------------------------------------------
# 3. Куди йдуть гроші
# ---------------------------------------------------------------------------
async def spend_report(window_days: int = 180, top_items: int = 5) -> dict:
    """Витрати по розділах каталогу — і що саме в кожному розділі.

    Банківська аналітика, але про їжу: «солодощі — 1 381 ₴, і це три
    Парі-Брести» видно лише тоді, коли позиції чека розкласти по 28 розділах
    «Сільпо» і в кожному лишити товари. Прив'язки товару до розділу в API
    немає, тож розділ визначаємо за назвою — це названо чесно.

    Args:
        window_days: вікно, за яке рахуємо (типово пів року — портрет, а не
            «цього місяця»); попереднє таке саме вікно йде для порівняння,
            якщо в ньому є чеки.
        top_items: скільки товарів показати в кожному розділі.
    """
    from .game import all_receipts
    from .proposed import _aisle_of

    orders = await all_receipts()
    today = _today()
    now: dict[str, float] = {}
    before: dict[str, float] = {}
    items: dict[str, dict[str, dict]] = {}
    counted = 0
    receipts_now = 0
    for order in orders:
        day = _date(order.get("createdAt"))
        if not day:
            continue
        age = (today - day).days
        bucket = now if age < window_days else (before if age < window_days * 2 else None)
        if bucket is None:
            continue
        if bucket is now:
            receipts_now += 1
        for line in order.get("products") or []:
            name = line.get("name") or ""
            _, title = _aisle_of(name)
            qty = line.get("quantity") or 1
            uah = round((line.get("price") or 0) * qty, 2)
            bucket[title] = round(bucket.get(title, 0) + uah, 2)
            counted += 1
            if bucket is now:
                row = items.setdefault(title, {}).setdefault(
                    name, {"name": name, "uah": 0.0, "times": 0, "qty": 0.0})
                row["uah"] = round(row["uah"] + uah, 2)
                row["times"] += 1
                row["qty"] = round(row["qty"] + qty, 2)

    rows = []
    for title in sorted(set(now) | set(before), key=lambda t: -now.get(t, 0)):
        a, b = now.get(title, 0), before.get(title, 0)
        top = sorted(items.get(title, {}).values(), key=lambda r: -r["uah"])[:top_items]
        rows.append({"category": title, "now_uah": round(a, 2), "before_uah": round(b, 2),
                     "delta_uah": round(a - b, 2),
                     "delta_percent": round((a - b) / b * 100) if b else None,
                     "items": top,
                     "distinct": len(items.get(title, {}))})
    total_now = round(sum(now.values()), 2)
    total_before = round(sum(before.values()), 2)
    grew = [r for r in rows if r["delta_percent"] is not None and r["delta_percent"] >= 25]
    span = ("пів року" if window_days == 180 else f"{window_days} днів")
    fmt = lambda v: f"{v:,.0f}".replace(",", "\u202f")   # 8 402, а не 8402
    headline = (f"За {span} — {fmt(total_now)} ₴ по {receipts_now} чеках"
                if not total_before else
                f"За {span} — {fmt(total_now)} ₴ проти {fmt(total_before)} ₴ у попередні {span}")
    return {
        "window_days": window_days,
        "total_now_uah": total_now, "total_before_uah": total_before,
        "receipts_now": receipts_now,
        "delta_percent": (round((total_now - total_before) / total_before * 100)
                          if total_before else None),
        "categories": rows, "lines_counted": counted,
        "grew": sorted(grew, key=lambda r: -r["delta_percent"])[:3],
        "headline": headline + ".",
        "gap": ("Розділ товару визначено за назвою: `categoryId` немає в картці "
                "товару навіть тоді, коли товар дістали запитом ПО КАТЕГОРІЇ."),
    }


# ---------------------------------------------------------------------------
# 4. Антиімпульсивна покупка
# ---------------------------------------------------------------------------
async def impulse_check(name: str) -> dict:
    """Агент, який ВІДМОВЛЯЄ купувати — якщо цифри проти покупки.

    Рахуємо три речі з реальних даних: як часто гість це бере, скільки платив
    раніше і скільки коштує зараз. Якщо береш учетверте за місяць і зараз
    дорожче за власну середню — це варто сказати вголос.
    """
    from .facade import search
    from .game import all_receipts

    orders = await all_receipts()
    key = (name or "").lower().split()
    key = " ".join(key[:2])
    hits = []
    for order in orders:
        for line in order.get("products") or []:
            if key and key in (line.get("name") or "").lower():
                hits.append({"date": (order.get("createdAt") or "")[:10],
                             "name": line.get("name"),
                             "price": line.get("price"),
                             "qty": line.get("quantity")})
    found = (await search([name], limit=5)).get(name) or []
    now_price = next((p.get("price") for p in found if p.get("available")), None)
    prices = [h["price"] for h in hits if h["price"]]
    avg = round(sum(prices) / len(prices), 2) if prices else None

    today = _today()
    last30 = [h for h in hits if (d := _date(h["date"])) and (today - d).days <= 30]
    verdict, reasons = "бери", []
    if avg and now_price and now_price > avg * 1.1:
        verdict = "почекай"
        reasons.append(f"зараз {now_price} ₴ — на {round((now_price / avg - 1) * 100)}% "
                       f"дорожче за твою середню {avg} ₴")
    if len(last30) >= 4:
        verdict = "почекай"
        reasons.append(f"брав {len(last30)} рази за 30 днів")
    if not hits:
        reasons.append("раніше не брав — порівняти нема з чим")
    if verdict == "бери" and now_price and avg and now_price < avg * 0.9:
        reasons.append(f"зараз {now_price} ₴ — дешевше за твою середню {avg} ₴, вдалий момент")

    return {"query": name, "verdict": verdict, "reasons": reasons,
            "times_bought": len(hits), "times_last_30d": len(last30),
            "avg_paid_uah": avg, "price_now_uah": now_price,
            "history": hits[:8],
            "candidate": ({"name": found[0].get("name"), "slug": found[0].get("slug"),
                           "image": found[0].get("image"), "price": found[0].get("price"),
                           "old_price": found[0].get("oldPrice")} if found else None),
            "note": "Агент, який лише продає, — не помічник. Іноді правильна відповідь «не бери»."}


# ---------------------------------------------------------------------------
# 6. Чи вигідний «Плюхс»
# ---------------------------------------------------------------------------
# Умови підписки беремо з публічної сторінки silpo.ua/subscription: MCP віддає
# лише «є вона в тебе чи ні». Живуть у demo.py — правляться з «Під капотом».
def _plus() -> dict:
    from . import demo
    return demo.get("plus")


async def plus_check() -> dict:
    """Порахувати «Плюхс» на власних чеках, а не на обіцянках із банера."""
    from .game import all_receipts

    sub = await silpo.call("silpo_get_my_premium_subscription", {})
    orders = await all_receipts()
    if not orders:
        return {"active": False, "reason": "немає чеків для розрахунку"}

    cfg = _plus()
    days = max(((_date(orders[0].get("createdAt")) or _today())
                - (_date(orders[-1].get("createdAt")) or _today())).days, 1)
    months = max(days / 30.0, 1.0)
    spent = sum(o.get("sumReg") or 0 for o in orders)
    per_month = spent / months
    cashback = per_month * cfg["cashback"]
    verdict = "вигідно" if cashback > cfg["price_uah"] else "поки ні"
    breakeven = round(cfg["price_uah"] / cfg["cashback"], 2)

    return {
        "active": bool(sub.get("subscription")),
        "summary_from_silpo": sub.get("summary"),
        "link": sub.get("webLink"),
        "months_counted": round(months, 1),
        "spent_uah": round(spent, 2),
        "per_month_uah": round(per_month, 2),
        "cashback_per_month_uah": round(cashback, 2),
        "price_uah": cfg["price_uah"],
        "net_per_month_uah": round(cashback - cfg["price_uah"], 2),
        "breakeven_uah": breakeven,
        "verdict": verdict,
        "headline": (f"Береш на {round(per_month)} ₴ на місяць. Підписка окупається "
                     f"від {round(breakeven)} ₴ — зараз це {verdict}."),
        "gap": ("MCP каже лише «є підписка чи немає». Ані ціни, ані відсотка кешбеку, "
                "ані порогу доставки в tool немає — умови довелось узяти зі сторінки "
                "silpo.ua/subscription і винести в константи."),
    }


# ---------------------------------------------------------------------------
# 7. Сезонність: що беруть у цьому магазині
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 8. Ризик збирання замовлення
# ---------------------------------------------------------------------------
async def picking_risk(pack_id: str | None = None,
                       avoid: list[str] | None = None) -> dict:
    """Попередити ДО оплати, що позицію можуть не зібрати, і дати заміну.

    `silpo_get_replacements` віддає саме позиції з ризиком збирання — це НЕ
    просто `stock: 0` — і кандидатів на заміну від самого «Сільпо». Tool
    створений рівно для цього і не використовується ніде: зараз про заміну
    гість дізнається дзвінком кур'єра вже після оплати.

    Джерело позицій: пак, інакше активне онлайн-замовлення в збиранні, інакше
    поточний кошик. Кандидати, що порушують алергію або дієту, відпадають —
    інакше «заміна наперед» підсунула б те, чого людині не можна.
    """
    from . import packs
    from .facade import _blocked_by, expand_avoid

    ctx = await context.ensure()

    # Обмеження: наші алергії плюс дієти з акаунта «Сільпо».
    terms = list(expand_avoid(avoid))
    try:
        diets = await silpo.call("silpo_get_my_food_restrictions", {})
        for restriction in diets.get("restrictions", []):
            slug = restriction.get("slug") or ""
            if slug and slug != "all-food":
                terms += expand_avoid([slug.replace("-free", "").replace("-", " ")])
    except SilpoError:
        pass
    terms = sorted({t for t in terms if t})

    source, names, ids = "cart", {}, []
    branch_id, company_id = ctx["branchId"], ctx.get("companyId")

    if pack_id:
        pack = packs.get(pack_id)
        if not pack:
            raise SilpoError(f"Пак {pack_id} не знайдено.")
        source = "pack"
        rows = pack.get("items") or []
        first = rows[0] if rows else {}
        branch_id = first.get("branch_id") or branch_id
        company_id = first.get("company_id") or company_id
    else:
        rows = []
        try:
            data = await silpo.call("silpo_get_my_online_orders", {"limit": 5})
            for candidate in data.get("orders", []):
                state = (candidate.get("status") or candidate.get("state") or "").lower()
                if state and not any(k in state for k in
                                     ("deliver", "done", "complete", "cancel",
                                      "closed", "issued")):
                    rows = [{"product_id": p.get("productId") or p.get("id"),
                             "name": p.get("name")}
                            for p in (candidate.get("products") or [])]
                    source = "order"
                    break
        except SilpoError:
            pass
        if not rows:
            detail = await context.cart_details()
            cart = detail.get("cart") or detail
            rows = [{"product_id": i.get("productId"), "name": i.get("name")}
                    for i in ((cart.get("shipments") or [{}])[0].get("products") or [])]

    for row in rows:
        pid = row.get("product_id")
        if pid:
            ids.append(str(pid))
            names[str(pid)] = row.get("name")
    if not ids:
        return {"checked": 0, "risky": [], "source": source,
                "note": "Порожньо — нічого перевіряти."}

    data = await silpo.call("silpo_get_replacements", {
        "branchId": branch_id, "companyId": company_id,
        "deliveryType": ctx["deliveryType"], "productIds": ids[:30]})

    risky, dropped = [], []
    for entry in (data.get("replacements") or data.get("items") or []):
        pid = str(entry.get("productId") or entry.get("id") or "")
        options = []
        for opt in (entry.get("replacements") or entry.get("products") or []):
            hit = _blocked_by(opt.get("name", ""), terms)
            if hit:
                dropped.append({"name": opt.get("name"), "because": hit})
                continue
            options.append({"name": opt.get("name"), "slug": opt.get("slug"),
                            "price": opt.get("price"), "image": opt.get("image")})
        risky.append({"product_id": pid, "name": names.get(pid) or entry.get("name"),
                      "risk": entry.get("risk") or entry.get("assemblyRisk"),
                      "options": options[:4]})

    risky = [r for r in risky if r["options"] or r["risk"]]
    return {
        "checked": len(ids), "source": source, "risky": risky,
        "risky_count": len(risky), "checked_for": terms,
        "hidden_by_restrictions": dropped,
        "verdict": (f"{len(risky)} з {len(ids)} позицій можуть не зібрати — "
                    "заміни підібрані наперед." if risky
                    else "Ризикових позицій немає — збереться як є."),
        "headline": (f"{len(risky)} з {len(ids)} позицій можуть не зібрати."
                     if risky else "Ризикових позицій немає — збереться як є."),
        "why": ("Попередження до оплати замість дзвінка кур'єра після. Заміни, "
                "що порушують алергію чи дієту, відсіяні: інакше «рішення "
                "наперед» підсунуло б те, чого не можна."),
    }


# ---------------------------------------------------------------------------
# 9. Де вигідніше: ціни в кількох магазинах
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 10. Відправ батькам в інше місто
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 11. Дитяча зона за віком, а не «дитина = пюре»
# ---------------------------------------------------------------------------
_AGE_BANDS = [
    (0, 1, ["пюре фруктове", "каша дитяча", "вода дитяча", "підгузки"]),
    (2, 5, ["йогурт дитячий", "сік дитячий", "печиво дитяче", "макарони фігурні"]),
    (6, 11, ["какао", "батончик злаковий", "сирок глазурований", "хлібці"]),
    (12, 17, ["енергетик безалкогольний", "чипси", "піца заморожена", "газована вода"]),
]


async def kids_pack(max_uah: float | None = None, avoid: list[str] | None = None,
                    prefer_promo: bool = False, novelty: str = "any") -> dict:
    """Пак для дітей із РЕАЛЬНИМИ віками з акаунта «Сільпо».

    `get_my_family.children[].dateOfBirth` є в API і не використовується ніде.
    Назару 16 — «дитяча зона» для нього це вже не пюре.
    """
    from .facade import build_pack

    family = await silpo.call("silpo_get_my_family", {})
    children = family.get("children") or []
    if not children:
        return {"children": [], "error": "У профілі «Сільпо» немає дітей."}

    today = _today()
    plan, queries = [], []
    for child in children:
        born = _date(child.get("dateOfBirth"))
        age = (today - born).days // 365 if born else None
        band = next((b for b in _AGE_BANDS if age is not None and b[0] <= age <= b[1]), None)
        picks = list(band[2]) if band else ["сік", "печиво"]
        plan.append({"name": child.get("name"), "age": age,
                     "gender": child.get("gender"), "picks": picks})
        queries += picks
    pack = await build_pack("Дитяча зона за віком", queries[:12], max_uah=max_uah,
                            avoid=avoid, prefer_promo=prefer_promo, novelty=novelty)
    pack["children"] = plan
    pack["why"] = ("Вік беремо з `get_my_family.children[].dateOfBirth` — поле є в API "
                   "й не використовується ніде. Підлітку 16 років «дитячі товари» "
                   "означають зовсім інше, ніж однорічному.")
    return pack


# ---------------------------------------------------------------------------
# 12. Закупівля для офісу
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# 13. Подарункові сертифікати
# ---------------------------------------------------------------------------