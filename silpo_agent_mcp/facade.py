"""Фасад над реальним MCP «Сільпо»: операції рівня продукту, а не API.

Навіщо шар: сирі 40 tools вимагають branchId, companyId, timeslot і ланцюжків
викликів — маленька локальна модель на цьому ламається. Тут кожна функція —
один зрозумілий крок сценарію («збери пак», «підміни товар», «поклади в кошик»),
а всередині відпрацьовують справжні silpo_*-tools, видимі у трейсі.

Пак — іменований набір реальних товарів: його можна оптимізувати під власні
купони, підміняти в ньому позиції, зберегти й перетворити на справжній кошик.
"""

from __future__ import annotations

import re

from . import context, packs
from .silpo import SilpoError, silpo

CHECKOUT_URL = "https://silpo.ua/cart"
MAX_BATCH = 30
# Скільки перших результатів пошуку вважаємо релевантними за запитом.
# Три — замало там, де розкид цін великий (сири, вина): найдешевше
# релевантне лежить нижче. Пʼять тримає баланс із точністю.
RELEVANT_HEAD = 5
# Скільки позицій чека максимум перевіряємо на акційний аналог.
PROMO_LOOKUPS = 6

# Розширення небажаного: одне слово → підрядки, що реально трапляються в назвах.
# Це перевірка ЗА НАЗВОЮ: повного складу MCP «Сільпо» не віддає (attributes
# містять лише країну, ТМ, продавця та БЖУ), тому назва — єдине джерело.
_AVOID_EXPAND = {
    "горіх": ["горіх", "арахіс", "фундук", "мигдал", "кеш", "волоськ", "пекан", "фісташ", "nut", "nussini"],
    "арахіс": ["арахіс", "горіх", "peanut"],
    "лактоз": ["молок", "вершк", "сметан", "масло вершк", "йогурт", "сир", "кефір", "ряжан"],
    "глютен": ["пшенич", "борошн", "хліб", "макарон", "сухар"],
    "риб": ["риб", "лосос", "тунець", "оселед", "макрел", "форел", "креветк", "морепродукт"],
    "яйц": ["яйц", "яєчн"],
    "гриб": ["гриб", "печериц", "шампіньйон"],
    "цитрус": ["цитрус", "апельсин", "лимон", "мандарин", "грейпфрут"],
    "цукор": ["цукор", "цукров"],
    "алкогол": ["вино", "пиво", "горілк", "віск", "лікер", "шампан"],
}

_NON_FOOD = ("корм для", "для котів", "для собак", "зубна паста", "шампунь",
             "гель для", "мило", "підгуз", "серветк", "туалетн", "для тварин",
             "освіжувач", "порошок пральн", "кондиціонер для білизни")


def expand_avoid(avoid: list[str] | None) -> list[str]:
    """«горіхи» → також арахіс/фундук/мигдаль тощо."""
    out: set[str] = set()
    for raw in avoid or []:
        term = (raw or "").lower().strip()
        if not term:
            continue
        out.add(term)
        for key, syns in _AVOID_EXPAND.items():
            if key in term or term in key:
                out.update(syns)
    return sorted(out)


def _blocked_by(name: str, avoid_terms: list[str]) -> str | None:
    low = (name or "").lower()
    return next((t for t in avoid_terms if t and t in low), None)


def _is_non_food(name: str) -> bool:
    low = (name or "").lower()
    return any(w in low for w in _NON_FOOD)


def _short_query(name: str, words: int = 3) -> str:
    """Перші кілька слів назви — повна назва з чека для пошуку задовга."""
    return " ".join((name or "").split()[:words])


def _article(product: dict) -> int | None:
    """Артикул товару. У чеках його немає в полі, зате він є хвостом слага."""
    external = product.get("externalProductId")
    if external:
        return int(external)
    tail = (product.get("slug") or "").rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def to_item(product: dict, query: str | None = None, qty: float = 1) -> dict:
    """Товар із пошуку «Сільпо» → позиція пака (усе, що треба для кошика)."""
    return {
        "product_id": product.get("id"),
        "external_id": _article(product),
        "company_id": product.get("companyId"),
        "branch_id": product.get("branchId"),
        "slug": product.get("slug"),
        "name": product.get("name"),
        "price": product.get("price") or 0,
        "old_price": product.get("oldPrice"),
        "image": product.get("image"),
        "qty": qty,
        "query": query,
        "weighted": bool(product.get("weighted")),
        "multibuy": product.get("specialPrices") or None,
    }


# ---------------------------------------------------------------------------
# Пошук
# ---------------------------------------------------------------------------
async def search(queries: list[str], limit: int = 5) -> dict:
    """Пакетний пошук реальних товарів (silpo_find_products_batch, до 30 запитів)."""
    await context.ensure()
    data = await silpo.call("silpo_find_products_batch", {
        **context.search_ctx(), "products": queries[:MAX_BATCH], "limit": limit})
    return {q.get("query"): q.get("products", []) for q in data.get("queries", [])}


def _leads_with(name: str, query: str) -> bool:
    """Чи починається назва товару тим самим словом, що й запит.

    «Виноград Кишмиш» веде запит «виноград», а «Напій Oshee виноград-пітахайя»
    його лише згадує. Правило мʼяке: якщо жоден кандидат не веде запитом
    («кола» → «Напій Pepsi Пепсі-Кола»), беремо всю голову як є.
    """
    first = lambda text: (text or "").lower().split()[:1]
    a, b = first(name), first(query)
    return bool(a and b and a[0][:5] == b[0][:5])


def _has_offer(product: dict) -> bool:
    """Чи є на товарі знижка або мультипакова ціна."""
    return bool(product.get("oldPrice") or product.get("specialPrices"))


def _best(candidates: list[dict], avoid_terms: list[str], budget_left: float | None,
          head: int = RELEVANT_HEAD, query: str = "",
          prefer_promo: bool = False) -> tuple[dict | None, str]:
    """Найкращий кандидат із ГОЛОВИ видачі.

    Пошук «Сільпо» ранжує добре: за запитом «яйця» перші позиції — курячі яйця,
    а шоколадне яйце із сюрпризом лежить шостим. Тому спершу відрізаємо голову
    релевантності, і лише всередині неї шукаємо найдешевше. Якщо сортувати за
    ціною весь список, в омлет потрапляє шоколадне яйце.

    Повертає (товар, причина_відмови_якщо_None).
    """
    reason = "нічого не знайшлось"
    pool = []
    for product in candidates:
        if not product.get("available") or (product.get("stock") or 0) <= 0:
            reason = "немає в наявності"
            continue
        if _is_non_food(product.get("name", "")):
            continue
        hit = _blocked_by(product.get("name", ""), avoid_terms)
        if hit:
            reason = f"пропущено через «{hit}»"
            continue
        pool.append(product)
        if len(pool) >= head:
            break
    if not pool:
        return None, reason
    leading = [p for p in pool if _leads_with(p.get("name", ""), query)]
    pool = leading or pool

    # Ваги смаку: те, що гість бере регулярно, підіймається; те, що він свайпав
    # уліво чи міняв, опускається. Це мʼякий сигнал — на відміну від алергії,
    # він нікого не виключає остаточно.
    from . import weights as tastes
    scored = {id(p): tastes.weight_of(p.get("name", "")) for p in pool}
    disliked = [p for p in pool if scored[id(p)] <= tastes.DISLIKE]
    liked = [p for p in pool if scored[id(p)] > tastes.DISLIKE]
    pool = liked or pool

    if prefer_promo:
        # тумблер «спершу з бонусами»: акційне вперед, і вже серед нього — дешевше
        pool.sort(key=lambda p: (0 if _has_offer(p) else 1,
                                 -scored[id(p)], p.get("price") or 1e9))
    else:
        pool.sort(key=lambda p: (-scored[id(p)], p.get("price") or 1e9))
    if budget_left is not None:
        affordable = [p for p in pool if (p.get("price") or 0) <= budget_left]
        if not affordable:
            return None, f"не влазить у бюджет (найдешевше {pool[0].get('price')} грн)"
        pool = affordable
    return pool[0], ""


async def build_pack(name: str, items: list[str], max_uah: float | None = None,
                     avoid: list[str] | None = None, prefer_promo: bool = False) -> dict:
    """Збирає пак із РЕАЛЬНИХ товарів «Сільпо» за переліком позицій.

    Args:
        name: назва пака, напр. «Вечір кіно на двох».
        items: що шукати — перелік складників чи товарів. Його формує модель,
            а не словник тем: саме тут живе «розуміння» запиту користувача.
        max_uah: бюджет; позиції додаються, поки вкладаються.
        avoid: алергії та несмаки — перевірка за назвою товару.
        prefer_promo: тумблер «пропонувати відразу з бонусами» — серед релевантних
            спершу беремо те, на що діє знижка чи мультипакова ціна.
    """
    if not items:
        raise SilpoError("Порожній перелік позицій — нема чого шукати.")
    avoid_terms = expand_avoid(avoid)
    found = await search(items, limit=8)

    chosen, skipped, total = [], [], 0.0
    for query in items[:MAX_BATCH]:
        candidates = found.get(query) or []
        left = None if max_uah is None else max_uah - total
        product, reason = _best(candidates, avoid_terms, left, query=query,
                                prefer_promo=prefer_promo)
        if not product:
            skipped.append({"query": query, "reason": reason})
            continue
        chosen.append(to_item(product, query))
        total += product.get("price") or 0

    pack = packs.create(name, chosen, budget_uah=max_uah,
                        source="agent", avoid=avoid or [])
    pack["prefer_promo"] = prefer_promo
    pack["weights_used"] = True
    pack["skipped"] = skipped
    pack["avoid_applied"] = avoid_terms
    pack["branch"] = silpo.ctx.get("branchId")
    return pack


# ---------------------------------------------------------------------------
# Пак із чека
# ---------------------------------------------------------------------------
async def receipts(limit: int = 5) -> dict:
    """Реальні чеки з фізичних магазинів (silpo_get_my_offline_orders)."""
    await context.ensure()
    data = await silpo.call("silpo_get_my_offline_orders",
                            {**context.search_ctx(), "limit": min(limit, 10)})
    out = []
    for order in data.get("orders", []):
        out.append({
            "date": (order.get("createdAt") or "")[:10],
            "shop": order.get("filialName"),
            "total_uah": order.get("sumReg"),
            "discount_uah": order.get("sumDiscount"),
            "receipt_url": order.get("receiptUrl"),
            "magic_name": order.get("chequeMagicName"),
            "item_count": len(order.get("products") or []),
            "items": [p.get("name") for p in (order.get("products") or [])][:20],
        })
    return {"count": len(out), "receipts": out, "total": data.get("meta", {}).get("total")}


async def _similar(slug: str, limit: int = 25) -> list[dict]:
    """Схожі товари за slug — у наявності, їстівні, без самого себе."""
    if not slug:
        return []
    data = await silpo.call("silpo_get_similar_products", {
        "branchId": silpo.ctx["branchId"], "slug": slug,
        "deliveryType": silpo.ctx["deliveryType"], "limit": limit})
    return [p for p in (data.get("products") or data.get("items") or [])
            if p.get("available") and (p.get("stock") or 0) > 0
            and p.get("slug") != slug and not _is_non_food(p.get("name", ""))]


async def pack_from_receipt(index: int = 0, name: str | None = None,
                            substitute: bool = True, prefer_promo: bool = False) -> dict:
    """Перетворює РЕАЛЬНИЙ чек на пак — усе, що ти купив, знову в один клік.

    Товар, якого зараз немає в обраному магазині, замінюємо схожим, а не
    мовчки викидаємо: інакше чек на 10 позицій перетворюється на пак із трьох.

    Args:
        index: 0 — останній чек, 1 — попередній і т.д.
        name: назва пака; за замовчуванням — «Як 2026-08-21».
        substitute: чи підбирати заміну відсутнім позиціям.
        prefer_promo: тумблер «спершу з бонусами» — для позицій без знижки
            шукаємо акційний аналог і пропонуємо його замість оригіналу.
    """
    await context.ensure()
    data = await silpo.call("silpo_get_my_offline_orders",
                            {**context.search_ctx(), "limit": 10})
    orders = data.get("orders", [])
    if index >= len(orders):
        raise SilpoError(f"Чека №{index} немає — усього {len(orders)}.")
    order = orders[index]

    chosen, absent, swapped, missing = [], [], [], []
    for line in order.get("products", []):
        catalog = line.get("catalogProduct") or {}
        qty = float(line.get("quantity") or 1)
        if catalog.get("available") and (catalog.get("stock") or 0) > 0:
            chosen.append(to_item(catalog, line.get("name"), qty=qty))
        else:
            absent.append({"name": line.get("name"), "qty": qty,
                           "slug": catalog.get("slug")})

    for line in absent:
        alternative = None
        if substitute:
            # той самий замінник для двох різних позицій — не заміна, а дубль
            used = {str(i["product_id"]) for i in chosen}
            pool = [p for p in await _similar(line["slug"])
                    if str(p.get("id")) not in used]
            if pool:
                pool.sort(key=lambda p: p.get("price") or 1e9)
                alternative = pool[0]
            else:
                found = await search([_short_query(line["name"])], limit=5)
                fresh = [p for p in next(iter(found.values()), [])
                         if str(p.get("id")) not in used]
                alternative, _ = _best(fresh, [], None, query=line["name"])
        if alternative:
            item = to_item(alternative, line["name"], qty=line["qty"])
            item["swapped_from"] = line["name"]
            chosen.append(item)
            swapped.append({"from": line["name"], "to": alternative["name"],
                            "price_uah": alternative.get("price")})
        else:
            missing.append(line["name"])

    promo_swaps = []
    if prefer_promo:
        # «Повтори чек» із тумблером: те, що йде без знижки, міняємо на акційний
        # аналог, якщо він не дорожчий. Ліміт — щоб не робити десять зайвих викликів.
        for item in list(chosen)[:PROMO_LOOKUPS]:
            if _has_offer({"oldPrice": item.get("old_price"), "specialPrices": item.get("multibuy")}):
                continue
            used = {str(i["product_id"]) for i in chosen}
            deals = [p for p in await _similar(item["slug"])
                     if _has_offer(p) and str(p.get("id")) not in used
                     and (p.get("price") or 1e9) <= (item.get("price") or 0)]
            if not deals:
                continue
            deals.sort(key=lambda p: p.get("price") or 1e9)
            fresh = to_item(deals[0], item.get("query"), qty=item.get("qty") or 1)
            fresh["swapped_from"] = item["name"]
            fresh["note"] = "акційна заміна — тумблер «спершу з бонусами»"
            chosen[chosen.index(item)] = fresh
            promo_swaps.append({"from": item["name"], "to": fresh["name"],
                                "saved_uah": round((item.get("price") or 0) - fresh["price"], 2)})

    date = (order.get("createdAt") or "")[:10]
    pack = packs.create(name or f"Як {date}", chosen, source="receipt",
                        tags=["чек", date])
    pack["promo_swaps"] = promo_swaps
    pack["prefer_promo"] = prefer_promo
    pack["receipt"] = {"date": date, "shop": order.get("filialName"),
                       "paid_uah": order.get("sumReg"),
                       "discount_uah": order.get("sumDiscount"),
                       "url": order.get("receiptUrl")}
    pack["substituted"] = swapped
    pack["unavailable"] = missing
    return pack


# ---------------------------------------------------------------------------
# Підміна позиції
# ---------------------------------------------------------------------------
async def swap_item(pack_id: str, product_id: str, prefer: str = "cheaper") -> dict:
    """Міняє позицію пака на альтернативу з «Сільпо» (silpo_get_similar_products).

    Args:
        prefer: "cheaper" — дешевше, "promo" — зі знижкою, "any" — будь-що схоже.
    """
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    current = next((i for i in pack["items"] if str(i["product_id"]) == str(product_id)), None)
    if not current:
        raise SilpoError("Такої позиції в паку немає.")

    await context.ensure()
    pool = [p for p in await _similar(current["slug"])
            if str(p.get("id")) != str(product_id)]
    avoid_terms = expand_avoid(pack.get("avoid"))
    pool = [p for p in pool if not _blocked_by(p.get("name", ""), avoid_terms)]
    if not pool:
        raise SilpoError(f"Альтернатив для «{current['name']}» не знайшлось.")

    price = current.get("price") or 0
    if prefer == "cheaper":
        cheaper = [p for p in pool if (p.get("price") or 0) < price]
        if not cheaper:
            # мовчазний фолбек на дорожче зробив би пак гіршим — краще сказати прямо
            pool.sort(key=lambda p: p.get("price") or 1e9)
            return {"pack": pack, "swapped": None,
                    "note": f"Дешевше за «{current['name']}» ({price} грн) серед схожих немає.",
                    "alternatives": [{"name": p["name"], "price": p.get("price"),
                                      "product_id": p.get("id")} for p in pool[:5]]}
        pool = sorted(cheaper, key=lambda p: p.get("price") or 1e9)
    elif prefer == "promo":
        pool.sort(key=lambda p: (0 if p.get("oldPrice") else 1, p.get("price") or 1e9))
    updated = packs.replace_item(pack_id, product_id, to_item(pool[0], current.get("query")))
    return {"pack": updated, "swapped": {"from": current["name"], "to": pool[0]["name"],
            "was_uah": price, "now_uah": pool[0].get("price"),
            "delta_uah": round((pool[0].get("price") or 0) - price, 2)},
            "alternatives": [{"name": p["name"], "price": p.get("price"),
                              "product_id": p.get("id")} for p in pool[:5]]}


# ---------------------------------------------------------------------------
# Пак → справжній кошик «Сільпо»
# ---------------------------------------------------------------------------
async def pack_to_cart(pack_id: str, replace: bool = True) -> dict:
    """Кладе пак у СПРАВЖНІЙ кошик користувача та повертає посилання на оплату.

    Це те, що агент реально РОБИТЬ, а не радить. Оформлення замовлення лишається
    за людиною — ми доводимо до кнопки «Оформити» і зупиняємось.

    Args:
        pack_id: який пак покласти.
        replace: True — спершу очистити кошик, False — додати до наявного.
    """
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    if not pack["items"]:
        raise SilpoError("Пак порожній.")
    ctx = await context.ensure()

    if replace:
        await silpo.call("silpo_clear_shopping_cart", {"shoppingCartId": ctx["shoppingCartId"]})

    products = [{"productId": i["product_id"], "companyId": i["company_id"],
                 "branchId": i["branch_id"], "quantity": i["qty"]}
                for i in pack["items"] if i.get("product_id")]
    await silpo.call("silpo_add_or_update_cart_products",
                     {"shoppingCartId": ctx["shoppingCartId"], "products": products})

    # success=true означає лише «запит прийнято» — реальний стан читаємо з кошика
    detail = await silpo.call("silpo_get_shopping_cart_by_id",
                              {"shoppingCartId": ctx["shoppingCartId"]})
    cart = detail.get("cart") or detail
    calc = cart.get("calculation") or {}
    in_cart = (cart.get("shipments") or [{}])[0].get("products") or []
    packs.record_use(pack_id)
    from . import weights as tastes
    for line in in_cart:
        tastes.bump(line.get("name", ""), "cart", float(line.get("quantity") or 1))

    # tool сам попереджає: success=true означає лише «запит прийнято».
    # Тому звіряємо, що реально лягло в кошик, і кажемо про розбіжності вголос.
    asked = {str(p["productId"]): p["quantity"] for p in products}
    got = {str(p.get("productId")): p.get("quantity") for p in in_cart}
    mismatched = [{"name": p.get("name"), "asked": asked.get(str(p.get("productId"))),
                   "in_cart": p.get("quantity")}
                  for p in in_cart
                  if asked.get(str(p.get("productId"))) not in (None, p.get("quantity"))]
    dropped = [i["name"] for i in pack["items"]
               if i.get("product_id") and str(i["product_id"]) not in got]

    return {
        "pack": {"id": pack["id"], "name": pack["name"]},
        "requested": len(products), "in_cart": len(in_cart),
        "total_uah": calc.get("total"), "subtotal_uah": calc.get("subTotal"),
        "discount_uah": calc.get("subDiscount"),
        "checkout_url": CHECKOUT_URL,
        "warnings": [v for v in (calc.get("validations") or [])
                     if v.get("level") != "info"],
        "not_added": dropped, "quantity_changed": mismatched,
        "note": "Товари у справжньому кошику «Сільпо». Оформлення підтверджує людина.",
    }


# ---------------------------------------------------------------------------
# Знижки: купони, персональні промо, бонуси
# ---------------------------------------------------------------------------
_STOP = {"для", "від", "при", "над", "під", "або", "усі", "все", "твої", "твій",
         "цей", "яка", "який", "купівлю", "купівля", "пропозиц", "товар", "грн",
         "знижк", "більше", "будь", "яких", "інші", "разом", "тільки"}


def _stems(text: str, size: int = 5) -> set[str]:
    """Огрублені корені слів — щоб «каву мелену» збіглося з «Кава мелена»."""
    words = re.findall(r"[а-яїієґa-z]{4,}", (text or "").lower())
    return {w[:size] for w in words if w[:size] not in _STOP and w not in _STOP}


def _brands(text: str) -> list[str]:
    """Бренди в лапках: «за чипси «Люкс»™» → ['Люкс']."""
    return re.findall(r"[«\"\u2018']([^»\"\u2019']{2,40})[»\"\u2019']", text or "")


def _match(offer_text: str, items: list[dict]) -> list[dict]:
    """Позиції пака, яких стосується пропозиція.

    Самого збігу за категорією замало: «за чипси «Люкс»™» — це не будь-які
    чипси. Якщо в описі є бренд у лапках, він мусить бути й у назві товару,
    і додатково має збігтися хоч одне слово з решти опису.
    """
    brands = _brands(offer_text)
    body = re.sub(r"[«\"\u2018'][^»\"\u2019']*[»\"\u2019']", " ", offer_text or "")
    body_stems = _stems(body)
    hits = []
    for item in items:
        name = item.get("name", "")
        name_stems = _stems(name)
        if brands and not any(_stems(b) & name_stems for b in brands):
            continue
        if body_stems and not (body_stems & name_stems):
            continue
        low = name.lower()
        exact = any(b.lower() in low for b in brands) if brands else False
        hits.append({"name": name, "confidence": "точний" if exact else "імовірний"})
    return hits


async def my_perks() -> dict:
    """Мої купони, персональні промо, бали та преміум — усе реальне."""
    coupons = await silpo.call("silpo_get_my_coupons", {})
    promos = await silpo.call("silpo_get_my_promos", {})
    loyalty = await silpo.call("silpo_get_loyalty_info", {})
    balance = (loyalty.get("loyalty") or {}).get("balance") or {}
    return {
        "coupons": [{"id": c.get("id"), "promo_id": c.get("promoId"),
                     "text": c.get("description"), "reward": c.get("rewardText"),
                     "until": c.get("endDate"), "limit": c.get("rewardLimit"),
                     "conditions": c.get("limitText"), "active": c.get("active")}
                    for c in coupons.get("coupons", [])],
        "promos": [{"id": p.get("promoId"), "text": p.get("description"),
                    "reward": p.get("rewardText"), "value": p.get("rewardValue"),
                    "until": p.get("endDate"), "selected": p.get("selected")}
                   for p in promos.get("promos", [])],
        "promo_limit": promos.get("meta", {}),
        "bonuses_uah": balance.get("total"),
        "card": (loyalty.get("loyalty") or {}).get("card", {}).get("typeName"),
    }


async def savings_report(receipts: int = 10) -> dict:
    """Скільки акції вже заощадили — і скільки згоріло невикористаним.

    Єдиний спосіб виміряти користь у гривнях постфактум: `sumDiscount` із чеків
    проти купонів, що протермінувалися активними. Список купонів не має прапорця
    «використано», тож «згоріло» — оцінка згори за `rewardLimit`.
    """
    import datetime as _dt
    today = _dt.date.today()
    await context.ensure()

    data = await silpo.call("silpo_get_my_offline_orders",
                            {**context.search_ctx(), "limit": min(receipts, 10)})
    orders = data.get("orders", [])
    saved = round(sum(o.get("sumDiscount") or 0 for o in orders), 2)
    spent = round(sum(o.get("sumReg") or 0 for o in orders), 2)
    rewards = []
    for order in orders:
        for reward in order.get("rewards", []) or []:
            rewards.append({
                "text": (reward.get("applyText") or "").replace("\r", " ").split("\n")[0].strip(),
                "uah": reward.get("applyRewardAmount"),
                "promo_id": reward.get("promoId"),
                "date": (order.get("createdAt") or "")[:10]})
    rewards_uah = round(sum(r["uah"] or 0 for r in rewards), 2)

    coupons = await silpo.call("silpo_get_my_coupons", {})
    ready, burning, wasted = [], [], []
    for c in coupons.get("coupons", []):
        if not c.get("active"):
            continue  # неактивний = використаний або відкликаний
        try:
            end = _dt.date.fromisoformat(str(c.get("endDate"))[:10])
        except (TypeError, ValueError):
            end = None
        row = {"text": c.get("description"), "reward": c.get("rewardText"),
               "until": c.get("endDate"), "cap_uah": c.get("rewardLimit"),
               "min_cheque": c.get("warningText")}
        if end and end < today:
            wasted.append(row)
        elif end and (end - today).days <= 2:
            burning.append({**row, "days_left": (end - today).days})
        else:
            ready.append(row)
    wasted_est = round(sum(r["cap_uah"] or 0 for r in wasted), 2)

    promos = await silpo.call("silpo_get_my_promos", {})
    promo_burning = []
    for p in promos.get("promos", []):
        try:
            end = _dt.date.fromisoformat(str(p.get("endDate"))[:10])
        except (TypeError, ValueError):
            continue
        if (end - today).days <= 2:
            promo_burning.append({"text": p.get("description"), "reward": p.get("rewardText"),
                                  "until": p.get("endDate"), "days_left": (end - today).days})

    loyalty = await silpo.call("silpo_get_loyalty_info", {})
    bonuses = ((loyalty.get("loyalty") or {}).get("balance") or {}).get("total")

    verdict = (f"За {len(orders)} чеків заощаджено {saved} ₴"
               + (f"; {len(wasted)} купон(ів) на ~{wasted_est} ₴ згоріли невикористаними"
                  if wasted else "; протермінованих купонів немає")
               + (f"; {len(burning)} згорають за 2 дні" if burning else "") + ".")
    return {
        "receipts": len(orders), "spent_uah": spent, "saved_uah": saved,
        "applied_rewards": {"count": len(rewards), "uah": rewards_uah, "items": rewards[:8]},
        "coupons_ready": ready, "coupons_burning": burning,
        "coupons_wasted": wasted, "coupons_wasted_est_uah": wasted_est,
        "promos_burning": promo_burning, "bonuses_uah": bonuses,
        "verdict": verdict,
        "note": ("«Згоріло» — активні купони з минулою датою: у списку немає прапорця "
                 "«використано», тож це оцінка згори за rewardLimit."),
    }


async def optimize_pack(pack_id: str) -> dict:
    """Підбирає, які з ТВОЇХ купонів і промо спрацюють саме на цей пак.

    Персональних промо у «Сільпо» видають більше, ніж можна активувати
    (зазвичай 10, активувати можна 1–5) — тож головна цінність тут у виборі
    правильної пʼятірки під конкретний пак. Активація лишається в застосунку:
    MCP дає промо тільки на читання.
    """
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    perks = await my_perks()
    items = pack["items"]

    matched_coupons = []
    for coupon in perks["coupons"]:
        hits = _match(coupon["text"], items) if coupon.get("active") else []
        if hits:
            matched_coupons.append({**coupon, "applies_to": hits})

    scored = []
    for promo in perks["promos"]:
        hits = _match(promo["text"], items)
        scored.append({**promo, "applies_to": hits,
                       "score": (len(hits), promo.get("value") or 0)})
    scored.sort(key=lambda p: p["score"], reverse=True)
    limit = int(perks["promo_limit"].get("maxSelect") or 5)
    recommended = [p for p in scored if p["applies_to"]][:limit]
    if not recommended:  # нічого не збіглося — беремо найщедріші
        recommended = scored[:limit]

    multibuy = multibuy_offers(pack)
    return {
        "pack": {"id": pack["id"], "name": pack["name"], "total_uah": pack["total_uah"]},
        "shelf_saving_uah": pack["saved_uah"],
        "multibuy": multibuy,
        "multibuy_saving_uah": round(sum(o["saving_uah"] for o in multibuy), 2),
        "coupons": matched_coupons,
        "activate_promos": [{"id": p["id"], "text": p["text"], "reward": p["reward"],
                             "applies_to": p["applies_to"]} for p in recommended],
        "promo_limit": perks["promo_limit"],
        "bonuses_uah": perks["bonuses_uah"],
        "note": ("Промо активуються в застосунку «Сільпо» — MCP віддає їх лише на "
                 "читання. Купони спрацьовують на касі автоматично."),
    }


# ---------------------------------------------------------------------------
# Хто я — з реальних чеків, а не з анкети
# ---------------------------------------------------------------------------
async def _raw_receipts(limit: int = 10) -> list[dict]:
    await context.ensure()
    data = await silpo.call("silpo_get_my_offline_orders",
                            {**context.search_ctx(), "limit": min(limit, 10)})
    return data.get("orders", [])


def _habits(orders: list[dict]) -> list[dict]:
    """Товари, куплені більше одного разу, та середній інтервал між покупками."""
    seen: dict[int, dict] = {}
    for order in orders:
        date = (order.get("createdAt") or "")[:10]
        for line in order.get("products", []):
            key = line.get("lagerId")
            if not key:
                continue
            entry = seen.setdefault(key, {"name": line.get("name"), "dates": [],
                                          "slug": (line.get("catalogProduct") or {}).get("slug")})
            entry["dates"].append(date)

    import datetime as _dt
    habits = []
    for entry in seen.values():
        dates = sorted({d for d in entry["dates"] if d})
        if len(dates) < 2:
            continue
        parsed = [_dt.date.fromisoformat(d) for d in dates]
        gaps = [(b - a).days for a, b in zip(parsed, parsed[1:]) if (b - a).days > 0]
        if not gaps:
            continue
        cycle = round(sum(gaps) / len(gaps))
        since = (_dt.date.today() - parsed[-1]).days
        cycle = max(cycle, 3)  # дві покупки поспіль не означають «щодня»
        habits.append({"name": entry["name"], "slug": entry["slug"],
                       "times": len(dates), "cycle_days": cycle,
                       "last_bought": dates[-1], "days_since": since,
                       "due": since >= cycle})
        habits[-1]["confidence"] = "низька" if len(dates) < 3 else "висока"
    habits.sort(key=lambda h: (-h["times"], h["cycle_days"]))
    return habits


async def who_am_i() -> dict:
    """Портрет гостя з РЕАЛЬНИХ даних «Сільпо»: профіль, родина, чеки, звички.

    Нічого не питаємо в анкеті — усе вже є в акаунті: хто ти, скільки витрачаєш,
    що береш регулярно і що вже мало б закінчитись.
    """
    profile = await silpo.call("silpo_get_my_profile", {})
    loyalty = await silpo.call("silpo_get_loyalty_info", {})
    family = await silpo.call("silpo_get_my_family", {})
    restrictions = await silpo.call("silpo_get_my_food_restrictions", {})
    orders = await _raw_receipts(10)

    spend = sum(o.get("sumReg") or 0 for o in orders)
    saved = sum(o.get("sumDiscount") or 0 for o in orders)
    shops: dict[str, int] = {}
    for order in orders:
        shops[order.get("filialName") or "—"] = shops.get(order.get("filialName") or "—", 0) + 1
    habits = _habits(orders)
    person = profile.get("profile") or {}
    diets = [r.get("slug") for r in restrictions.get("restrictions", [])
             if r.get("slug") and r.get("slug") != "all-food"]

    return {
        "name": person.get("firstName"),
        "birthday": person.get("birthday"),
        "card": (loyalty.get("loyalty") or {}).get("card", {}).get("typeName"),
        "bonuses_uah": ((loyalty.get("loyalty") or {}).get("balance") or {}).get("total"),
        "children": family.get("children") or [],
        "pets": family.get("pets") or [],
        "diets_from_silpo": diets,
        "receipts": {
            "count": len(orders),
            "spent_uah": round(spend, 2),
            "saved_uah": round(saved, 2),
            "avg_check_uah": round(spend / len(orders), 2) if orders else 0,
            "favourite_shop": max(shops, key=shops.get) if shops else None,
        },
        "habits": habits[:8],
        "due_now": [h for h in habits if h["due"]][:5],
        "note": ("Дієти й родина — з акаунта «Сільпо»; алергії та смаки, яких там "
                 "немає, зберігає наш profile MCP."),
    }


async def reorder_pack(name: str = "Час поповнити") -> dict:
    """Пак із того, що ти купуєш регулярно і що вже мало б закінчитись.

    Проактивний сценарій на реальних чеках: цикл покупки рахуємо самі, тож
    агент може прийти першим, а не чекати запиту.
    """
    orders = await _raw_receipts(10)
    due = [h for h in _habits(orders) if h["due"] and h["slug"]]
    if not due:
        raise SilpoError("За чеками поки нічого не мало б закінчитись.")
    found = await search([_short_query(h["name"], 4) for h in due[:MAX_BATCH]], limit=5)
    chosen = []
    for habit in due:
        product, _ = _best(found.get(_short_query(habit["name"], 4)) or [], [], None,
                           query=habit["name"])
        if product and str(product.get("id")) not in {i["product_id"] for i in chosen}:
            item = to_item(product, habit["name"])
            item["note"] = f"береш кожні ~{habit['cycle_days']} дн., востаннє {habit['last_bought']}"
            chosen.append(item)
    if not chosen:
        raise SilpoError("Нічого зі звичного зараз немає в наявності.")
    pack = packs.create(name, chosen, source="habits", tags=["звички"])
    pack["reason"] = [{"name": h["name"], "cycle_days": h["cycle_days"],
                       "days_since": h["days_since"]} for h in due[:10]]
    return pack


# ---------------------------------------------------------------------------
# Збереження, готові набори «Сільпо», магазин
# ---------------------------------------------------------------------------
async def save_pack(pack_id: str, mirror: bool = True) -> dict:
    """Зберігає пак і (за бажанням) дублює товари в «Обране» справжнього акаунта.

    Пак живе не лише в нашому застосунку: позиції потрапляють в «Обране»
    «Сільпо», тож ними можна користуватись і без нас.
    """
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    mirrored = 0
    if mirror:
        actions = [{"productId": i["product_id"], "externalProductId": int(i["external_id"]),
                    "toDelete": False}
                   for i in pack["items"] if i.get("product_id") and i.get("external_id")]
        for chunk in (actions[i:i + 5] for i in range(0, len(actions), 5)):  # ліміт 5 за виклик
            await silpo.call("silpo_add_or_update_favorite_products", {"actions": chunk})
            mirrored += len(chunk)
    updated = packs.update(pack_id, saved=True)
    return {"pack": updated, "mirrored_to_favorites": mirrored}


def my_packs(saved_only: bool = False, limit: int = 20) -> dict:
    """Мої паки — збережені набори, готові лягти в кошик одним рухом."""
    items = packs.list_packs(saved_only=saved_only, limit=limit)
    return {"count": len(items),
            "packs": [{"id": p["id"], "name": p["name"], "items": p["item_count"],
                       "total_uah": p["total_uah"], "saved_uah": p["saved_uah"],
                       "source": p["source"], "saved": p["saved"], "uses": p["uses"]}
                      for p in items]}


async def browse_sets() -> dict:
    """Готові тематичні набори самого «Сільпо» (silpo_get_product_sets)."""
    await context.ensure()
    data = await silpo.call("silpo_get_product_sets",
                            {"branchId": silpo.ctx["branchId"],
                             "deliveryType": silpo.ctx["deliveryType"]})
    return {"count": len(data.get("sets", [])),
            "sets": [{"slug": s.get("slug"), "title": s.get("title"), "link": s.get("link")}
                     for s in data.get("sets", [])]}


async def pack_from_set(slug: str, name: str | None = None, max_uah: float | None = None,
                        only_promo: bool = True, avoid: list[str] | None = None,
                        limit: int = 12) -> dict:
    """Готовий набір «Сільпо» → персональний пак: лише акційне, без алергенів, у бюджет.

    Args:
        slug: слаг набору з browse_sets.
        only_promo: True — брати з набору лише товари зі знижкою.
    """
    await context.ensure()
    data = await silpo.call("silpo_get_products", {
        **context.search_ctx(), "set": slug, "limit": limit,
        "inStock": True, "mustHavePromotion": only_promo, "sortBy": "promotion"})
    avoid_terms = expand_avoid(avoid)
    pool = data.get("products") or data.get("items") or []
    # бюджет має йти на найвигідніше, тому спершу найбільша знижка
    pool.sort(key=lambda p: -((p.get("oldPrice") or p.get("price") or 0) - (p.get("price") or 0)))
    chosen, total = [], 0.0
    for product in pool:
        if not product.get("available") or _is_non_food(product.get("name", "")):
            continue
        if _blocked_by(product.get("name", ""), avoid_terms):
            continue
        price = product.get("price") or 0
        if max_uah and total + price > max_uah:
            continue
        chosen.append(to_item(product, slug))
        total += price
    if not chosen:
        raise SilpoError(f"У наборі «{slug}» не знайшлось відповідних товарів.")
    pack = packs.create(name or slug, chosen, budget_uah=max_uah,
                        source="silpo_set", tags=[slug], avoid=avoid or [])
    pack["set"] = slug
    return pack


async def set_branch(city: str | None = None, branch_id: str | None = None) -> dict:
    """Змінює магазин: асортимент і ціни рахуються саме для нього."""
    silpo.ctx.clear()
    await context.ensure(city=city, branch_id=branch_id)
    branch = await context.pick_branch(city, silpo.ctx.get("branchId"))
    return {"branchId": silpo.ctx.get("branchId"),
            "shop": f'{branch.get("city", "")}, {branch.get("address", "")}' if branch else None,
            "cart_id": silpo.ctx.get("shoppingCartId")}


def mcp_trace(limit: int = 30) -> dict:
    """Останні виклики РЕАЛЬНИХ silpo_*-tools: що, з чим і скільки мілісекунд."""
    return {"calls": silpo.trace_tail(limit), "total": len(silpo.trace)}


def multibuy_offers(pack: dict) -> list[dict]:
    """«Візьми 2 — по 76.90 замість 89.49»: реальні мультипакові ціни з `specialPrices`.

    Руками таке не рахують — саме тут агент повертає гостю живі гроші.
    """
    offers = []
    for item in pack.get("items", []):
        for special in item.get("multibuy") or []:
            count = special.get("count") or 0
            unit = special.get("price")
            base = item.get("price") or 0
            if count < 2 or not unit or unit >= base:
                continue
            have = item.get("qty") or 1
            offers.append({
                "name": item["name"], "product_id": item["product_id"],
                "now_qty": have, "take_qty": count,
                "unit_price_uah": base, "unit_price_with_offer_uah": unit,
                "extra_cost_uah": round(unit * count - base * have, 2),
                "saving_uah": round((base - unit) * count, 2),
                "text": f"візьми {count} — по {unit} замість {base} грн за шт",
            })
    offers.sort(key=lambda o: -o["saving_uah"])
    return offers


# ---------------------------------------------------------------------------
# Оплата Дольками, дедлайни промо, скринінг алергенів
# ---------------------------------------------------------------------------
async def payment_hint(pack_total_uah: float | None = None) -> dict:
    """Чи доступна «Оплата Дольками» і скільки бракує до порогу.

    MCP не дає обрати спосіб оплати, зате віддає правило машиночитаним:
    у validations приходить `order.payment_types.disabled` з paymentTypes
    ["BNPL"] і minTotal. Тобто агент може довести кошик до порогу — а вибір
    оплати робить людина на чекауті.
    """
    detail = await context.cart_details()
    calc = (detail.get("cart") or detail).get("calculation") or {}
    total = calc.get("total") or 0
    blocked = []
    for rule in calc.get("validations") or []:
        ctx = rule.get("context") or {}
        if not ctx.get("paymentTypes"):
            continue
        blocked.append({"types": ctx["paymentTypes"], "min_uah": ctx.get("minTotal"),
                        "reason": ctx.get("reason")})
    basis = pack_total_uah if pack_total_uah is not None else total
    hint = None
    for rule in blocked:
        if rule["min_uah"] and basis < rule["min_uah"]:
            hint = {"types": rule["types"], "min_uah": rule["min_uah"],
                    "have_uah": round(basis, 2),
                    "missing_uah": round(rule["min_uah"] - basis, 2)}
            break
    return {"available_now": calc.get("payment", {}).get("availableTypes") or [],
            "blocked": blocked, "cart_total_uah": total, "hint": hint,
            "note": "Спосіб оплати обирає людина — MCP лише повідомляє умови."}


async def expiring(days: int = 1) -> dict:
    """Купони й промо, що згорають сьогодні-завтра — щоб не пропали дарма."""
    import datetime as _dt
    limit = _dt.date.today() + _dt.timedelta(days=days)
    perks = await my_perks()

    def soon(items: list[dict]) -> list[dict]:
        out = []
        for item in items:
            raw = item.get("until")
            try:
                end = _dt.date.fromisoformat(str(raw)[:10])
            except (TypeError, ValueError):
                continue
            if end <= limit:
                out.append({**item, "days_left": (end - _dt.date.today()).days})
        return sorted(out, key=lambda x: x["days_left"])

    coupons, promos = soon(perks["coupons"]), soon(perks["promos"])
    return {"coupons": coupons, "promos": promos,
            "count": len(coupons) + len(promos),
            "promo_limit": perks["promo_limit"]}


def screen_pack(pack_id: str, avoid: list[str] | None = None) -> dict:
    """Перевіряє готовий пак на небажані складники за назвою товару.

    Потрібно для паків, зібраних не нами (з чека, з набору «Сільпо»): там
    фільтр на етапі підбору не спрацьовував. Це перевірка ЗА НАЗВОЮ — повного
    складу MCP «Сільпо» не віддає.
    """
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    terms = expand_avoid(avoid or pack.get("avoid"))
    flagged = []
    for item in pack["items"]:
        hit = _blocked_by(item.get("name", ""), terms)
        if hit:
            flagged.append({"product_id": item["product_id"], "name": item["name"],
                            "matched": hit})
    return {"pack": {"id": pack["id"], "name": pack["name"]},
            "checked_for": terms, "flagged": flagged, "clean": not flagged,
            "note": ("Перевірка за назвою товару: склад MCP «Сільпо» не віддає "
                     "(attributes містять лише країну, ТМ, продавця та БЖУ).")}


async def swap_to(pack_id: str, product_id: str, new_product_id: str) -> dict:
    """Замінює позицію пака на конкретно обраний товар."""
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    current = next((i for i in pack["items"] if str(i["product_id"]) == str(product_id)), None)
    if not current:
        raise SilpoError("Такої позиції в паку немає.")
    await context.ensure()
    chosen = next((p for p in await _similar(current["slug"])
                   if str(p.get("id")) == str(new_product_id)), None)
    if not chosen:
        raise SilpoError("Обраного товару вже немає серед доступних альтернатив.")
    from . import weights as tastes
    tastes.bump(current["name"], "swapped_out")
    tastes.bump(chosen.get("name", ""), "swapped_in")
    updated = packs.replace_item(pack_id, product_id, to_item(chosen, current.get("query")))
    return {"pack": updated,
            "swapped": {"from": current["name"], "to": chosen["name"],
                        "was_uah": current.get("price"), "now_uah": chosen.get("price"),
                        "delta_uah": round((chosen.get("price") or 0) - (current.get("price") or 0), 2)}}


# ---------------------------------------------------------------------------
# Сценарні паки: настрій, вечір, сніданок
# ---------------------------------------------------------------------------
# Стартові запити. Модель, якщо вона є, передає власний `items` — і він виграє.
# Ця таблиця потрібна, щоб сценарії працювали й без моделі (демо, офлайн).
_MOODS = {
    "ігривий": ["вино ігристе", "чипси", "цукерки"],
    "святковий": ["вино ігристе", "сир твердий", "торт"],
    "романтичний": ["вино червоне", "сир з пліснявою", "виноград"],
    "втомлений": ["шоколад молочний", "чай", "піца"],
    "спокійний": ["чай трав'яний", "печиво", "мед"],
    "голодний": ["піца", "пельмені", "картопля фрі"],
    "бадьорий": ["кава зернова", "йогурт", "горіхи мікс"],
}

# Жанр вечора → готовий набір «Сільпо» (реальна курація) + що додати пошуком.
_EVENINGS = {
    "футбол": {"set": "lvivske-310", "items": ["чипси", "сухарики", "ковбаски"]},
    "фільм": {"set": "dlia-smachnoi-vecheri", "items": ["попкорн", "кола"]},
    "серіал": {"set": "dlia-smachnoi-vecheri", "items": ["снеки", "морозиво"]},
    "романтична вечеря": {"set": "vyno-vivino", "items": ["сир твердий", "виноград"]},
    "компанія": {"set": "pitsa-sushi-ta-burhery", "items": ["чипси", "кола"]},
}

# Рецепти — наш контент, а не вигадка на льоту. Товари під них шукаються в «Сільпо».
_BREAKFASTS = [
    {"title": "Омлет із сиром", "items": ["яйця", "сир твердий", "молоко", "масло вершкове"],
     "steps": ["Збий 3 яйця з ложкою молока.", "Вилий на розігріту пательню з маслом.",
               "За хвилину додай тертий сир і склади навпіл."]},
    {"title": "Сирники", "items": ["сир кисломолочний", "яйця", "борошно", "сметана"],
     "steps": ["Змішай сир, яйце і 2 ложки борошна.", "Сформуй сирники, обкачай у борошні.",
               "Смаж по 3 хвилини з боку. Подавай зі сметаною."]},
    {"title": "Вівсянка з бананом", "items": ["пластівці вівсяні", "банан", "молоко", "мед"],
     "steps": ["Залий пластівці гарячим молоком на 5 хвилин.",
               "Додай нарізаний банан і ложку меду."]},
    {"title": "Тост з авокадо та яйцем", "items": ["хліб", "авокадо", "яйця"],
     "steps": ["Підсмаж хліб.", "Розімни авокадо виделкою, посоли.",
               "Зверху — яйце пашот або смажене."]},
    {"title": "Йогурт із гранолою", "items": ["йогурт", "гранола", "ягоди"],
     "steps": ["Виклади йогурт у миску.", "Зверху — гранола і ягоди."]},
]


async def mood_pack(mood: str, max_uah: float | None = None,
                    items: list[str] | None = None, avoid: list[str] | None = None) -> dict:
    """Пак під настрій: «ігривий» → ігристе, «втомлений» → шоколад і чай.

    Args:
        mood: слово-настрій (результат міні-тесту або з розмови).
        items: якщо модель сама склала перелік — він має пріоритет.
    """
    key = (mood or "").lower().strip()
    queries = items or _MOODS.get(key) or next(
        (v for k, v in _MOODS.items() if k in key or key in k), None)
    if not queries:
        raise SilpoError(f"Не знаю, що брати під настрій «{mood}». "
                         f"Відомі: {', '.join(_MOODS)}.")
    pack = await build_pack(f"Настрій: {mood}", queries, max_uah=max_uah, avoid=avoid)
    pack["mood"] = key
    pack["from_model"] = bool(items)
    return pack


async def evening_pack(genre: str, max_uah: float | None = None,
                       avoid: list[str] | None = None) -> dict:
    """Пак під вечір удома: футбол → пиво, фільм → снеки, романтика → вино.

    Основа — готові набори самого «Сільпо» (`get_product_sets`), тож підбірку
    курує магазин, а ми лише прибираємо небажане й тримаємо бюджет.
    """
    key = (genre or "").lower().strip()
    rule = _EVENINGS.get(key) or next(
        (v for k, v in _EVENINGS.items() if k in key or key in k), None)
    if not rule:
        raise SilpoError(f"Не знаю жанру «{genre}». Відомі: {', '.join(_EVENINGS)}.")

    # Набір «Сільпо» дає настрій вечора, але не має з'їдати весь бюджет:
    # без цієї межі два вина забирають 728 з 800, і на сир уже не лишається.
    set_budget = None if max_uah is None else round(max_uah * 0.6, 2)
    budget = max_uah
    chosen: list[dict] = []
    try:
        base = await pack_from_set(rule["set"], name=genre, max_uah=set_budget,
                                   only_promo=False, avoid=avoid, limit=6)
        chosen = base["items"][:2]
        packs.delete(base["id"])  # то був чернетковий пак, лишаємо тільки позиції
        budget = None if budget is None else budget - sum(i["price"] for i in chosen)
    except SilpoError:
        pass  # набору може не бути в цьому магазині — доберемо самим пошуком

    extra = await build_pack(f"Вечір: {genre}", rule["items"], max_uah=budget, avoid=avoid)
    packs.set_items(extra["id"], chosen + extra["items"])
    pack = packs.get(extra["id"])
    pack["genre"] = key
    pack["silpo_set"] = rule["set"]
    return pack


async def breakfast_pack(max_uah: float = 300, avoid: list[str] | None = None,
                         prefer: str | None = None) -> dict:
    """Сніданок на суму: рецепт + реальні продукти під нього, без алергенів.

    Рецепт обираємо той, що вкладається в бюджет і не містить нічого з `avoid`.
    Порядок перебору враховує звички з чеків: те, що людина й так бере.
    """
    terms = expand_avoid(avoid)
    options = [r for r in _BREAKFASTS
               if not any(_blocked_by(i, terms) for i in r["items"])]
    if prefer:
        options.sort(key=lambda r: prefer.lower() not in r["title"].lower())
    if not options:
        raise SilpoError("Усі рецепти сніданку містять те, чого тобі не можна.")

    # звички з чеків: рецепт зі знайомих продуктів приємніший за екзотичний
    try:
        habit_words = " ".join(h["name"].lower() for h in _habits(await _raw_receipts(10)))
    except Exception:
        habit_words = ""
    if habit_words:
        options.sort(key=lambda r: -sum(1 for i in r["items"] if i.split()[0] in habit_words))

    last_error = None
    for recipe in options:
        try:
            pack = await build_pack(recipe["title"], recipe["items"],
                                    max_uah=max_uah, avoid=avoid)
        except SilpoError as exc:
            last_error = exc
            continue
        if pack["items"] and pack["total_uah"] <= max_uah:
            pack["recipe"] = {"title": recipe["title"], "steps": recipe["steps"]}
            pack["skipped_recipes"] = [r["title"] for r in options if r is not recipe]
            return pack
        packs.delete(pack["id"])
    raise SilpoError(f"У {max_uah} ₴ жоден сніданок не вклався. {last_error or ''}".strip())


def scenarios() -> dict:
    """Довідник доступних сценаріїв — щоб UI не хардкодив списки."""
    return {"moods": sorted(_MOODS), "evenings": sorted(_EVENINGS),
            "breakfasts": [r["title"] for r in _BREAKFASTS]}


# ---------------------------------------------------------------------------
# Страва на суму — узагальнення «сніданку»
# ---------------------------------------------------------------------------
async def meal_pack(query: str | None = None, meal: str | None = None,
                    max_uah: float | None = None, equipment: list[str] | None = None,
                    avoid: list[str] | None = None, serves: int | None = None,
                    prefer_promo: bool = False) -> dict:
    """Страва → рецепт і реальні продукти під нього.

    Замінює «сніданок на суму»: працює для будь-якого прийому їжі, з бюджетом
    і без нього, а рецепти відсіюються за тим, що є на кухні гостя.

    Args:
        query: назва страви («карбонара») або порожньо — тоді за meal.
        meal: сніданок / обід / вечеря / десерт.
        max_uah: бюджет; без нього беремо перший придатний рецепт.
        equipment: техніка на кухні — рецепт із духовкою не піде тому, у кого її немає.
        serves: на скількох готуємо.
    """
    from . import proposed

    found = proposed.find_recipes(query=query, meal=meal, equipment=equipment,
                                  avoid=avoid, serves=serves, limit=8)
    options = found["recipes"]
    online = None
    if not options and query:
        # Своєї бази не вистачило — не падаємо, а йдемо в інтернет. Повільніше,
        # зате сценарій доводиться до кінця.
        online = await proposed.find_recipe_online(query)
        if online.get("guessed_items"):
            pack = await build_pack(query, online["guessed_items"][:6], max_uah=max_uah,
                                    avoid=avoid, prefer_promo=prefer_promo)
            pack["recipe"] = {"title": query, "meal": meal or "страва", "minutes": None,
                              "equipment": [], "serves": serves or 2,
                              "steps": ["Рецепт узято з інтернету — перевір джерело нижче."]}
            pack["from_web"] = online
            return pack
    if not options:
        raise SilpoError("Під ці умови рецепта не знайшлось — спробуй інший прийом їжі, "
                         "познач більше техніки на кухні або назви страву точніше."
                         + (f" В інтернеті теж порожньо: {online.get('error','')}" if online else ""))

    last_error = None
    for recipe in options:
        try:
            pack = await build_pack(recipe["title"], recipe["items"], max_uah=max_uah,
                                    avoid=avoid, prefer_promo=prefer_promo)
        except SilpoError as exc:
            last_error = exc
            continue
        if pack["items"] and (max_uah is None or pack["total_uah"] <= max_uah):
            pack["recipe"] = {k: recipe[k] for k in
                              ("title", "meal", "minutes", "equipment", "serves", "steps")}
            pack["other_recipes"] = [r["title"] for r in options if r["id"] != recipe["id"]]
            return pack
        packs.delete(pack["id"])
    raise SilpoError(f"У {max_uah} ₴ жодна страва не вклалась. {last_error or ''}".strip())


async def breakfast_pack(max_uah: float = 300, avoid: list[str] | None = None,
                         prefer: str | None = None) -> dict:
    """Сніданок на суму — окремий вхід у meal_pack для звичного сценарію."""
    return await meal_pack(query=prefer, meal="сніданок", max_uah=max_uah, avoid=avoid)


# ---------------------------------------------------------------------------
# Картка товару та розширений вибір заміни
# ---------------------------------------------------------------------------
async def product_card(slug: str, name: str | None = None) -> dict:
    """Повні відомості про товар — щоб гість міг перевірити все сам.

    Обовʼязковий крок перед оформленням: агент може помилитись, тож людина
    мусить мати доступ до атрибутів, БЖУ, складу та посилання на картку.
    """
    await context.ensure()
    raw = await silpo.call("silpo_get_product_details", {
        "branchId": silpo.ctx["branchId"], "slug": slug,
        "deliveryType": silpo.ctx["deliveryType"],
        "timeslotStart": silpo.ctx["timeslotStart"],
        "timeslotEnd": silpo.ctx["timeslotEnd"]})
    product = raw.get("product") or raw
    from . import proposed
    composition = await proposed.get_product_composition(slug, product.get("name") or name)
    return {
        "name": product.get("name"), "slug": slug,
        "price_uah": product.get("price"), "old_price_uah": product.get("oldPrice"),
        "unit": product.get("displayRatio"), "stock": product.get("stock"),
        "images": product.get("images") or ([product.get("image")] if product.get("image") else []),
        "url": product.get("url"),
        "attributes": product.get("attributes") or {},
        "composition": composition,
        "verify_note": ("Склад ШІ виводить із назви — перевір етикетку або картку "
                        "товару на silpo.ua перед покупкою."),
    }


async def alternatives(pack_id: str, product_id: str, prefer: str = "any",
                       limit: int = 8, query: str | None = None,
                       max_price: float | None = None) -> dict:
    """Варіанти заміни позиції — з фото, цінами й фільтрами. БЕЗ самої заміни.

    Args:
        prefer: "cheaper" — дешевше, "promo" — зі знижкою, "any" — усе схоже.
        query: власний пошук замість «схожих» — коли гість знає, чого хоче.
        max_price: стеля ціни.
    """
    pack = packs.get(pack_id)
    if not pack:
        raise SilpoError(f"Пак {pack_id} не знайдено.")
    current = next((i for i in pack["items"] if str(i["product_id"]) == str(product_id)), None)
    if not current:
        raise SilpoError("Такої позиції в паку немає.")
    await context.ensure()

    if query:
        found = await search([query], limit=24)
        pool = [p for p in next(iter(found.values()), []) if p.get("available")]
    else:
        pool = await _similar(current["slug"])
    pool = [p for p in pool if str(p.get("id")) != str(product_id)]

    terms = expand_avoid(pack.get("avoid"))
    blocked = [p for p in pool if _blocked_by(p.get("name", ""), terms)]
    pool = [p for p in pool if p not in blocked]

    price = current.get("price") or 0
    if prefer == "cheaper":
        pool = [p for p in pool if (p.get("price") or 0) < price]
    elif prefer == "promo":
        pool = [p for p in pool if _has_offer(p)]
    if max_price is not None:
        pool = [p for p in pool if (p.get("price") or 0) <= max_price]
    pool.sort(key=lambda p: p.get("price") or 1e9)

    return {
        "pack_id": pack_id,
        "current": {"product_id": current["product_id"], "name": current["name"],
                    "price_uah": price, "image": current.get("image"),
                    "slug": current.get("slug")},
        "filters": {"prefer": prefer, "query": query, "max_price": max_price},
        "hidden_by_allergies": [p.get("name") for p in blocked],
        "options": [{"product_id": p.get("id"), "name": p.get("name"), "slug": p.get("slug"),
                     "price_uah": p.get("price"), "old_price_uah": p.get("oldPrice"),
                     "unit": p.get("displayRatio"), "image": p.get("image"),
                     "in_stock": bool(p.get("available")),
                     "multibuy": p.get("specialPrices") or None,
                     "delta_uah": round((p.get("price") or 0) - price, 2)}
                    for p in pool[:limit]],
        "note": "Нічого не змінено. Обери — і виклич swap_to." if pool
                else "За цими фільтрами нічого не знайшлось.",
    }


async def find_address(address: str) -> dict:
    """Адреса словами → координати (silpo_find_address). Потрібно для порівняння доставок."""
    data = await silpo.call("silpo_find_address", {"address": address})
    return {"addresses": [{"label": a.get("address"), "city": a.get("city"),
                           "district": a.get("district"),
                           "latitude": a.get("latitude"), "longitude": a.get("longitude")}
                          for a in data.get("addresses", [])]}


# ---------------------------------------------------------------------------
# Ваговий ліміт доставки
# ---------------------------------------------------------------------------
# Українські назви способів отримання: в API вони англійські й гостю нічого
# не кажуть.
DELIVERY_UA = {
    "SelfPickup": "Самовивіз",
    "DeliveryHome": "Доставка додому",
    "DeliveryFlat": "Доставка до квартири",
    "DeliveryOffice": "Доставка в офіс",
    "DeliveryExpress": "Експрес-доставка",
    "DeliveryExpressByPromise": "Експрес за обіцянкою",
    "DeliveryExpressFood": "Експрес: готова їжа",
    "DeliveryGlovo": "Доставка Glovo",
    "LongDelivery": "Доставка на завтра",
    "WideAssortDelivery": "Розширений асортимент",
    "NovaPoshta": "Нова Пошта",
    "JustIn": "JustIn",
    "JustInPost": "JustIn Пошта",
    "PreOrder": "Передзамовлення",
    "B2B": "Для бізнесу",
    "Unknown": "Невідомо",
}


def delivery_label(code: str) -> str:
    return DELIVERY_UA.get(code, code)


async def cart_weight_check() -> dict:
    """Чи влізе кошик у доставку за вагою.

    У слотах є `maxWeight` (40 кг для доставки додому), а в кошику —
    `calculation.delivery.totalWeight`. Ніхто їх не звіряє, і про перевищення
    гість дізнається від кур'єра. Це перевірка ДО оформлення.
    """
    ctx = await context.ensure()
    detail = await silpo.call("silpo_get_shopping_cart_by_id",
                              {"shoppingCartId": ctx["shoppingCartId"]})
    cart = detail.get("cart") or detail
    calc = cart.get("calculation") or {}
    weight = (calc.get("delivery") or {}).get("totalWeight") or 0

    # Ліміт ваги живе на доставці, а не на самовивозі — тому питаємо ще й хаб,
    # який обслуговує доставку за координатами магазину.
    branch_ids = {ctx["branchId"]}
    address = cart.get("address") or {}
    lat, lon = address.get("latitude"), address.get("longitude")
    if lat and lon:
        types = await silpo.call("silpo_get_available_delivery_types",
                                 {"latitude": float(lat), "longitude": float(lon)})
        branch_ids |= {o["branchId"] for o in types.get("options", []) if o.get("branchId")}

    limits: dict[str, float] = {}
    for branch_id in branch_ids:
        try:
            slots = await silpo.call("silpo_get_time_slots",
                                     {"branchId": branch_id, "limit": 60})
        except SilpoError:
            continue
        for slot in slots.get("slots", []):
            if not slot.get("available"):
                continue
            code = slot.get("deliveryType", "?")
            limits[code] = max(limits.get(code, 0), slot.get("maxWeight") or 0)

    options = [{"delivery_type": code, "label": delivery_label(code),
                "max_kg": cap or None,
                "fits": (cap == 0) or weight <= cap,
                "over_kg": round(max(0.0, weight - cap), 2) if cap else 0}
               for code, cap in sorted(limits.items())]
    blocked = [o for o in options if not o["fits"]]
    return {"cart_weight_kg": round(weight, 2), "options": options,
            "blocked": blocked,
            "verdict": ("Кошик важчий за ліміт: " +
                        ", ".join(f'{o["label"]} (макс {o["max_kg"]} кг)' for o in blocked)
                        if blocked else "Вага в межах усіх доступних способів."),
            "note": "maxWeight беремо з доступних слотів обраного магазину."}


async def order_risk(pack_id: str | None = None, avoid: list[str] | None = None) -> dict:
    """Ризик збирання: що з набору можуть не зібрати — і чим замінити наперед.

    `silpo_get_replacements` віддає позиції, які комплектувальник ризикує не
    зібрати (це НЕ просто stock:0), і кандидатів на заміну від самого «Сільпо».
    Зараз про заміну гість дізнається дзвінком кур'єра вже після оплати — тут
    рішення переноситься наперед, а кандидати, що порушують алергію, відпадають.

    Джерело позицій: пак (`pack_id`), інакше активне онлайн-замовлення в
    збиранні, інакше поточний кошик.
    """
    ctx = await context.ensure()

    terms = list(expand_avoid(avoid))
    try:
        diets = await silpo.call("silpo_get_my_food_restrictions", {})
        for restriction in diets.get("restrictions", []):
            slug = restriction.get("slug") or ""
            if slug and slug != "all-food":
                terms += expand_avoid([slug.replace("-free", "").replace("-", " ")])
    except SilpoError:
        pass
    terms = sorted(set(t for t in terms if t))

    # --- звідки беремо позиції ------------------------------------------------
    source, lines = "cart", []
    branch_id, company_id = ctx["branchId"], ctx.get("companyId")

    if pack_id:
        pack = packs.get(pack_id)
        if not pack:
            raise SilpoError(f"Пак {pack_id} не знайдено.")
        source = "pack"
        for item in pack["items"]:
            if not item.get("product_id"):
                continue
            lines.append({"product_id": str(item["product_id"]), "name": item.get("name"),
                          "slug": item.get("slug"), "price_uah": item.get("price"),
                          "qty": item.get("qty") or 1})
        first = pack["items"][0] if pack["items"] else {}
        branch_id = first.get("branch_id") or branch_id
        company_id = first.get("company_id") or company_id
    else:
        order = None
        try:
            data = await silpo.call("silpo_get_my_online_orders", {"limit": 5})
            for candidate in data.get("orders", []):
                state = (candidate.get("status") or candidate.get("state") or "").lower()
                if state and not any(k in state for k in
                                     ("deliver", "done", "complete", "cancel", "closed", "issued")):
                    order = candidate
                    break
        except SilpoError:
            pass
        if order:
            source = "online_order"
            for product in order.get("products", []):
                catalog = product.get("catalogProduct") or product
                lines.append({"product_id": str(product.get("productId") or catalog.get("id")),
                              "name": product.get("name") or catalog.get("name"),
                              "slug": catalog.get("slug"),
                              "price_uah": product.get("price") or catalog.get("price"),
                              "qty": float(product.get("quantity") or 1)})
            branch_id = order.get("branchId") or branch_id
            company_id = order.get("companyId") or company_id
        else:
            detail = await silpo.call("silpo_get_shopping_cart_by_id",
                                      {"shoppingCartId": ctx["shoppingCartId"]})
            cart = detail.get("cart") or detail
            shipment = (cart.get("shipments") or [{}])[0]
            branch_id = shipment.get("branchId") or branch_id
            company_id = shipment.get("companyId") or company_id
            for product in shipment.get("products") or []:
                lines.append({"product_id": str(product.get("productId")),
                              "name": product.get("name"), "slug": product.get("slug"),
                              "price_uah": product.get("price"),
                              "qty": product.get("quantity") or 1})

    if not lines:
        return {"source": source, "checked": 0, "checked_for": terms,
                "at_risk": [], "safe_swaps": [], "blocked_by_allergy": [], "clean": True,
                "verdict": "Нема що перевіряти — ні пака, ні кошика, ні замовлення в збиранні."}

    by_id = {line["product_id"]: line for line in lines}

    reply = await silpo.call("silpo_get_replacements", {
        "branchId": branch_id, "companyId": company_id,
        "deliveryType": ctx["deliveryType"], "productIds": list(by_id)})
    flagged = reply.get("items") or reply.get("replacements") or reply.get("results") or []

    at_risk, safe_swaps, blocked = [], [], []
    for entry in flagged:
        pid = str(entry.get("productId") or entry.get("id")
                  or (entry.get("product") or {}).get("id") or "")
        origin = by_id.get(pid) or {
            "name": entry.get("name") or (entry.get("product") or {}).get("name"),
            "price_uah": None, "slug": (entry.get("product") or {}).get("slug")}
        raw = (entry.get("replacements") or entry.get("candidates")
               or entry.get("items") or entry.get("options") or [])
        candidates = []
        for cand in raw:
            body = cand.get("product") if isinstance(cand.get("product"), dict) else cand
            name = body.get("name") or cand.get("name")
            if not name:
                continue
            candidates.append({
                "product_id": body.get("id") or cand.get("productId"),
                "name": name, "slug": body.get("slug"),
                "price_uah": body.get("price") if body.get("price") is not None else cand.get("price"),
                "image": body.get("image"),
                "blocked_by": _blocked_by(name, terms)})

        was = origin.get("price_uah")
        row = {"product_id": pid, "name": origin.get("name"), "price_uah": was,
               "reason": entry.get("reason") or entry.get("risk")
               or "комплектувальник може не зібрати"}
        safe = [c for c in candidates if not c["blocked_by"]]
        if not safe and not candidates:
            # tool не дав кандидатів — пробуємо схожі товари як запасний шлях
            similar = [p for p in await _similar(origin.get("slug") or "")
                       if not _blocked_by(p.get("name", ""), terms)]
            similar.sort(key=lambda p: p.get("price") or 1e9)
            if similar:
                pick = similar[0]
                safe = [{"product_id": pick.get("id"), "name": pick.get("name"),
                         "slug": pick.get("slug"), "price_uah": pick.get("price"),
                         "image": pick.get("image"), "blocked_by": None, "via": "similar_products"}]

        if safe:
            safe.sort(key=lambda c: (c["price_uah"] is None, c["price_uah"] or 0))
            best = safe[0]
            best["delta_uah"] = (round((best["price_uah"] or 0) - (was or 0), 2)
                                 if was is not None and best["price_uah"] is not None else None)
            row["replacement"] = best
            safe_swaps.append({"from": origin.get("name"), "to": best["name"]})
        else:
            row["replacement"] = None
            if candidates:
                row["all_candidates_blocked"] = sorted(
                    {c["blocked_by"] for c in candidates if c["blocked_by"]})
                blocked.append(origin.get("name"))
        at_risk.append(row)

    clean = not at_risk
    if clean:
        verdict = f"Усі {len(lines)} позицій зберуть — ризику заміни не виявлено."
    else:
        manual = [r["name"] for r in at_risk if not r.get("replacement")]
        verdict = (f"{len(at_risk)} позиц. під ризиком; для {len(safe_swaps)} обрано "
                   f"безпечну заміну" + (f", {len(manual)} — вирішити вручну" if manual else "")
                   + ".")
    return {"source": source, "checked": len(lines), "checked_for": terms,
            "at_risk": at_risk, "safe_swaps": safe_swaps,
            "blocked_by_allergy": blocked, "clean": clean, "verdict": verdict,
            "note": ("Ризик — з silpo_get_replacements (не просто stock:0). Заміни, що "
                     "порушують алергію чи дієту, відкинуто за назвою товару.")}


async def set_cart_quantity(product_id: str, quantity: float) -> dict:
    """Змінити кількість позиції у справжньому кошику."""
    ctx = await context.ensure()
    detail = await silpo.call("silpo_get_shopping_cart_by_id",
                              {"shoppingCartId": ctx["shoppingCartId"]})
    cart = detail.get("cart") or detail
    line = next((p for p in (cart.get("shipments") or [{}])[0].get("products") or []
                 if str(p.get("productId")) == str(product_id)), None)
    if not line:
        raise SilpoError("Такої позиції в кошику немає.")
    await silpo.call("silpo_add_or_update_cart_products", {
        "shoppingCartId": ctx["shoppingCartId"],
        "products": [{"productId": line["productId"], "companyId": line["companyId"],
                      "branchId": line["branchId"], "quantity": quantity}]})
    return {"product_id": product_id, "quantity": quantity}


async def remove_from_cart(product_id: str) -> dict:
    """Прибрати позицію зі справжнього кошика."""
    ctx = await context.ensure()
    detail = await silpo.call("silpo_get_shopping_cart_by_id",
                              {"shoppingCartId": ctx["shoppingCartId"]})
    cart = detail.get("cart") or detail
    line = next((p for p in (cart.get("shipments") or [{}])[0].get("products") or []
                 if str(p.get("productId")) == str(product_id)), None)
    if not line:
        raise SilpoError("Такої позиції в кошику немає.")
    await silpo.call("silpo_remove_cart_products", {
        "shoppingCartId": ctx["shoppingCartId"],
        "products": [{"productId": line["productId"]}]})   # схема хоче тільки productId
    return {"removed": line.get("name")}


async def refresh_timeslot() -> dict:
    """Оновлює слот у кошику, коли старий уже минув.

    Кошик живе довше за слот: створив увечері — зранку `timeslot.not_available`,
    і кожна операція тягне за собою це попередження. Тут беремо найближчий
    доступний слот того ж магазину й переписуємо кошик.
    """
    ctx = await context.ensure()
    detail = await silpo.call("silpo_get_shopping_cart_by_id",
                              {"shoppingCartId": ctx["shoppingCartId"]})
    cart = detail.get("cart") or detail
    slot = await context.first_free_slot(ctx["branchId"])
    await silpo.call("silpo_update_shopping_cart", {
        "shoppingCartId": ctx["shoppingCartId"],
        "deliveryType": cart.get("deliveryType") or context.DELIVERY_TYPE,
        "timeslot": {"start": slot["start"], "end": slot["end"]},
        "address": cart.get("address") or {},
        "shipments": [{"companyId": s.get("companyId"), "branchId": s.get("branchId")}
                      for s in (cart.get("shipments") or [])],
    })
    silpo.ctx["timeslotStart"] = slot["start"]
    silpo.ctx["timeslotEnd"] = slot["end"]
    return {"slot": {"start": slot["start"], "end": slot["end"]},
            "note": "Слот оновлено — попередження timeslot.not_available зникне."}
