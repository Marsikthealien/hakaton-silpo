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
    "лактоз": ["молок", "молочн", "вершк", "сметан", "йогурт", "сир", "кефір", "ряжан"],
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


# Скільки літер може «доростити» до слова українське закінчення. «мак» +
# «овий» — це мак; «мак» + «арони» — це вже не мак.
_ENDING_MAX = 4

# Гість пише «сметана», а на етикетці «зі смаком сметани» — і збігу немає.
# Тому шукаємо за основою: у слів від шести літер відкидаємо кінцеву голосну.
# Поріг саме шість, бо «кава» → «кав» знайшло б «кавун», а «риба» → «риб» —
# «рибалку». Коротким словам закінчення не ріжемо.
_STEM_MIN = 6
_ENDINGS = "аяиіїуюеоь"


def _stem(term: str) -> str:
    return term[:-1] if len(term) >= _STEM_MIN and term[-1] in _ENDINGS else term


def _blocked_by(name: str, avoid_terms: list[str]) -> str | None:
    """Чи містить назва щось із заборонених термінів — по КОРЕНЮ, не по підрядку.

    Наївний пошук підрядка дає абсурдні збіги: алерген «мак» блокував
    «Вермішель зі смаком курки», а «сир» — «ковбасу сирокопчену». Тому термін
    має починати слово, а хвіст після нього — бути схожим на закінчення, а не
    на другий корінь.

    Перевірка все одно наближена: складу товару MCP не віддає, і ми про це
    кажемо прямо. Помилятись вона має в бік «краще пропустити повз кошик».
    """
    import re

    low = (name or "").lower()
    for term in avoid_terms:
        if not term:
            continue
        root = _stem(term)
        for match in re.finditer(r"(?<![0-9a-zа-яіїєґ'’-])" + re.escape(root), low):
            tail = re.match(r"[а-яіїєґa-z']*", low[match.end():]).group(0)
            if len(tail) <= _ENDING_MAX:
                return term
    return None


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
          prefer_promo: bool = False, novelty: str = "any",
          dropped: list[dict] | None = None,
          taken: set | None = None) -> tuple[dict | None, str]:
    """Найкращий кандидат із ГОЛОВИ видачі.

    Пошук «Сільпо» ранжує добре: за запитом «яйця» перші позиції — курячі яйця,
    а шоколадне яйце із сюрпризом лежить шостим. Тому спершу відрізаємо голову
    релевантності, і лише всередині неї шукаємо найдешевше. Якщо сортувати за
    ціною весь список, в омлет потрапляє шоколадне яйце.

    `dropped` — куди складати те, що зняла алергія. Доти це було видно лише
    тоді, коли ПІД ЗАБОРОНУ потрапляв увесь запит; товар, відсіяний тихо на
    користь сусіднього, не лишав сліду взагалі. А перевірка за назвою
    наближена, тож гість має бачити, на якому слові вона спрацювала.

    Повертає (товар, причина_відмови_якщо_None).
    """
    reason = "нічого не знайшлось"
    pool = []
    for product in candidates:
        if not product.get("available") or (product.get("stock") or 0) <= 0:
            reason = "немає в наявності"
            continue
        # Той самий товар годиться одразу кільком запитам: «вода» від трекера
        # і «вода мінеральна» від ваг смаку знаходять одну пляшку. У паку вона
        # має бути один раз, інакше гість бачить дубль і не довіряє решті.
        if taken and product.get("id") in taken:
            reason = "вже є в цьому паку"
            continue
        # Нехарчове відсіюємо, ЯКЩО його не просили: «шампунь» у вечері зайвий.
        # Але коли сам запит нехарчовий — «корм для котів», — цей же фільтр
        # вигрібав усю видачу, і кіт лишався без вечері.
        if _is_non_food(product.get("name", "")) and not _is_non_food(query):
            continue
        hit = _blocked_by(product.get("name", ""), avoid_terms)
        if hit:
            reason = f"пропущено через «{hit}»"
            if dropped is not None:
                dropped.append({"query": query, "name": product.get("name"), "term": hit})
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
    liked = [p for p in pool if scored[id(p)] > tastes.DISLIKE]
    pool = liked or pool

    # Новизна — окрема вісь від симпатії. «Знайоме» — те, що вже було в чеках
    # чи в свайпах; «нове» — те, чого гість не бачив. Серед нового сортуємо за
    # вагою ПОЛИЦІ, а не товару: інакше «нове» вироджується у випадкове.
    wide = list(pool)
    rank = scored
    if novelty == "new":
        fresh = [p for p in pool if not tastes.known(p.get("name", ""))]
        if fresh:
            pool = fresh
            rank = {id(p): tastes.category_weight_of(p.get("name", "")) for p in pool}
    elif novelty == "familiar":
        pool = [p for p in pool if tastes.known(p.get("name", "")) and scored[id(p)] > 0] or wide

    def _pick(bucket: list[dict], scores: dict) -> dict | None:
        if prefer_promo:
            # тумблер «спершу з бонусами»: акційне вперед, і вже серед нього — дешевше
            bucket.sort(key=lambda p: (0 if _has_offer(p) else 1,
                                       -scores[id(p)], p.get("price") or 1e9))
        else:
            bucket.sort(key=lambda p: (-scores[id(p)], p.get("price") or 1e9))
        if budget_left is None:
            return bucket[0] if bucket else None
        fits = [p for p in bucket if (p.get("price") or 0) <= budget_left]
        return fits[0] if fits else None

    picked = _pick(pool, rank)
    if picked is None and pool is not wide:
        # Новизна — побажання, а не обмеження: якщо єдиний знайомий сир коштує
        # 689 ₴ і не влазить, краще взяти незнайомий, ніж лишити рядок порожнім.
        picked = _pick(wide, scored)
        if picked is not None:
            picked["_novelty_relaxed"] = True
    if picked is None:
        cheapest = min((p.get("price") or 0) for p in wide) if wide else 0
        return None, f"не влазить у бюджет (найдешевше {cheapest} грн)"
    return picked, ""


async def build_pack(name: str, items: list[str], max_uah: float | None = None,
                     avoid: list[str] | None = None, prefer_promo: bool = False,
                     novelty: str = "any") -> dict:
    """Збирає пак із РЕАЛЬНИХ товарів «Сільпо» за переліком позицій.

    Args:
        name: назва пака, напр. «Вечір кіно на двох».
        items: що шукати — перелік складників чи товарів. Його формує модель,
            а не словник тем: саме тут живе «розуміння» запиту користувача.
        max_uah: бюджет; позиції додаються, поки вкладаються.
        avoid: алергії та несмаки — перевірка за назвою товару.
        prefer_promo: тумблер «пропонувати відразу з бонусами» — серед релевантних
            спершу беремо те, на що діє знижка чи мультипакова ціна.
        novelty: «familiar» — лише перевірене з чеків і свайпів, «new» — лише те,
            чого гість ще не брав, «any» — без обмежень. Це питання, яке агент
            має ставити ПЕРЕД підбором, а не вирішувати за гостя.
    """
    from . import weights as tastes

    if not items:
        raise SilpoError("Порожній перелік позицій — нема чого шукати.")
    avoid_terms = expand_avoid(avoid)
    found = await search(items, limit=8)

    chosen, skipped, total = [], [], 0.0
    dropped: list[dict] = []
    picked_ids: set = set()
    for query in items[:MAX_BATCH]:
        candidates = found.get(query) or []
        left = None if max_uah is None else max_uah - total
        product, reason = _best(candidates, avoid_terms, left, query=query,
                                prefer_promo=prefer_promo, novelty=novelty,
                                dropped=dropped, taken=picked_ids)
        if not product:
            skipped.append({"query": query, "reason": reason})
            continue
        picked_ids.add(product.get("id"))
        item = to_item(product, query)
        if product.pop("_novelty_relaxed", False):
            item["novelty_relaxed"] = True
        chosen.append(item)
        total += product.get("price") or 0

    pack = packs.create(name, chosen, budget_uah=max_uah,
                        source="agent", avoid=avoid or [])
    pack["prefer_promo"] = prefer_promo
    pack["novelty"] = novelty
    pack["novelty_note"] = tastes.novelty_note(novelty)
    pack["weights_used"] = True
    pack["skipped"] = skipped
    pack["avoid_applied"] = avoid_terms
    # Однакові товари трапляються в кількох запитах — у переліку виключень
    # вони потрібні один раз, і сотня рядків тут нічого не пояснює.
    seen: set[tuple] = set()
    excluded: list[dict] = []
    for row in dropped:
        key = (row["name"], row["term"])
        if key not in seen and len(excluded) < 12:
            seen.add(key)
            excluded.append(row)
    pack["excluded"] = excluded
    pack["branch"] = silpo.ctx.get("branchId")
    return pack


# ---------------------------------------------------------------------------
# Пак із чека
# ---------------------------------------------------------------------------
async def receipts(limit: int = 5) -> dict:
    """Реальні чеки з фізичних магазинів (silpo_get_my_offline_orders)."""
    orders = await _raw_receipts()
    out = []
    for order in orders[:limit]:
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
    return {"count": len(out), "receipts": out, "total": len(orders)}


async def _similar(slug: str, limit: int = 25) -> list[dict]:
    """Схожі товари за slug — у наявності, їстівні, без самого себе."""
    if not slug:
        return []
    # З релізу MCP 1.110.1 точний stock «схожих» вимагає слоту доставки —
    # без нього наявність неточна (у changelog це позначено як breaking change).
    data = await silpo.call("silpo_get_similar_products", {
        "branchId": silpo.ctx["branchId"], "slug": slug,
        "deliveryType": silpo.ctx["deliveryType"],
        "timeslotStart": silpo.ctx.get("timeslotStart"),
        "timeslotEnd": silpo.ctx.get("timeslotEnd"), "limit": limit})
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
    if not pool:
        # «Схожі» в API — не для кожного товару: для пакетів для сміття
        # відповідь буває порожньою. Тоді шукаємо за назвою — так само, як
        # під час збирання пака, — щоб «Обрати інший» не впирався в стіну.
        found = await search([_short_query(current["name"], 3)], limit=8)
        pool = [p for p in next(iter(found.values()), [])
                if str(p.get("id")) != str(product_id)
                and p.get("available") and (p.get("stock") or 0) > 0]
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
    # Вагу рухає лише те, що ЩОЙНО поклали. Доти bump ішов по всьому кошику,
    # і три натискання «У кошик» робили «регулярним» усе, що в ньому лежало,
    # включно з тим, що гість узагалі не обирав.
    just_added = {str(p["productId"]) for p in products}
    for line in in_cart:
        if str(line.get("productId")) in just_added:
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
        # Платить гість `totalAfterDiscounts`, а не `total`: у релізі 1.110.0
        # «Сільпо» це прописали окремо — «always show this to the user, not
        # total». Ми показували `total`, тобто суму ДО знижок: число більше за
        # те, що спишеться з картки.
        "total_uah": calc.get("totalAfterDiscounts", calc.get("total")),
        "total_before_discount_uah": calc.get("total"),
        "subtotal_uah": calc.get("subTotal"),
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


ORDER_WIDE = ("чек", "замовлен", "онлайн", "покупк")


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

    matched_coupons, ineligible = [], []
    seen_promos: set = set()
    for coupon in perks["coupons"]:
        # Один і той самий купон видають двічі (два id, один promoId) —
        # показуємо раз, бо й спрацює він раз.
        if coupon.get("promo_id") in seen_promos:
            continue
        hits = _match(coupon["text"], items) if coupon.get("active") else []
        # Купон «на онлайн чек» не про товар, а про все замовлення — за
        # назвами товарів він не збігається ні з чим, хоча саме він на
        # цьому акаунті найвагоміший. Такі перевіряємо окремо.
        order_wide = (not hits and bool(coupon.get("active"))
                      and any(k in (coupon.get("text") or "").lower() for k in ORDER_WIDE))
        if not hits and not order_wide:
            continue
        # `active` — лише перемикач гостя. Чи купон узагалі можна застосувати
        # зараз, каже canBeAppliedToOrder із деталей (у MCP з 1.110.0, учора):
        # він враховує ще й стан життєвого циклу. Читаємо його для тих, що
        # лягли на кошик, — по одному купону за виклик, тож лише для них.
        try:
            detail = await silpo.call("silpo_get_coupon_details",
                                      {"businessCouponId": coupon["id"]})
            info = detail.get("coupon") or detail
            eligible = info.get("canBeAppliedToOrder")
            state = info.get("state")
            warning = info.get("warningText")
            limit_text = info.get("limitText") or ""
        except SilpoError:
            eligible, state, warning, limit_text = None, None, None, ""
        row = {**coupon, "applies_to": hits, "eligible": eligible, "state": state,
               "order_wide": order_wide, "warning": warning,
               # «Діє лише при замовленні доставки» — з самовивозом не спрацює,
               # і про це гість дізнається на касі. Читаємо з limitText.
               "delivery_only": "доставк" in limit_text.lower()}
        if order_wide:
            row["applies_to"] = [{"name": "усе онлайн-замовлення", "confidence": "точний"}]
        if coupon.get("promo_id") is not None:
            seen_promos.add(coupon["promo_id"])
        (matched_coupons if eligible is not False else ineligible).append(row)

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
        "coupons_ineligible": ineligible,
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
async def _raw_receipts(limit: int = 0) -> list[dict]:
    """Чеки гостя — за замовчуванням УСІ, а не перші десять.

    `get_my_offline_orders` віддає максимум 10 за виклик, тож історію гортає
    `game.all_receipts` (і кешує на дві хвилини). Портрет гостя, звички й
    грибниця мають рахуватись з однієї вибірки: інакше на одному екрані
    «3 107 ₴ за 10 чеків», а на сусідньому «8 966 ₴ за 32».
    """
    from .game import all_receipts

    orders = await all_receipts()
    return orders[:limit] if limit else orders


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
    orders = await _raw_receipts()

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
    orders = await _raw_receipts()
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
    total = calc.get("totalAfterDiscounts", calc.get("total")) or 0
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


# Демо-адреса гостя: Оболонь, звідки до найближчого «Сільпо» 0,8 км. У продукті
# на це місце стає адреса з профілю або геолокація телефона — у MCP адреси
# гостя немає, а кошик її зберігає лише після першого оформлення.
HOME_LAT, HOME_LON = 50.5187, 30.4986


def _fmt_uah(value) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    text = f"{v:,.0f}" if v == int(v) else f"{v:,.2f}"
    return text.replace(",", " ") + " ₴"


async def precheck_pack(pack_id: str | None = None, latitude: float | None = None,
                        longitude: float | None = None) -> dict:
    """Перевірка перед «Оформити»: доставка, вага, купон, промо — однією карткою.

    Це ті самі чотири речі, які асистент «Сільпо» має в API і не читає перед
    оплатою: поріг безкоштовної доставки й відстань до магазину, ліміт ваги
    слоту, чи ляже купон на кошик (canBeAppliedToOrder) і які промо варто
    активувати. Жодного нового джерела даних — лише зведення в один крок,
    бо гість питає «чи все гаразд?» один раз, а не чотири.

    Args:
        pack_id: який пак перевіряти; без id — останній зібраний.
        latitude, longitude: звідки гість; без них — адреса кошика або демо-адреса.
    """
    from . import proposed

    pack = _pack_or_last(pack_id)
    total = float(pack.get("total_uah") or 0)
    checks: list[dict] = []

    # 1. Топати чи замовити — по координатах гостя. Адресу кошика не беремо:
    # кошик самовивозу зберігає координати МАГАЗИНУ, а не дому.
    lat = float(latitude if latitude is not None else HOME_LAT)
    lon = float(longitude if longitude is not None else HOME_LON)
    try:
        delivery = await proposed.estimate_delivery(lat, lon, cart_total_uah=total)
        options = delivery.get("options") or []
        pickup = next((o for o in options if o["delivery_type"] == "SelfPickup"), None)
        # Порівнюємо зі звичайною доставкою додому; B2B і розширений
        # асортимент — окремі історії, гостю вони не про «замовити чи топати».
        home = (next((o for o in options if o["delivery_type"] == "DeliveryHome"), None)
                or next((o for o in options
                         if o["delivery_type"] not in ("SelfPickup", "B2B")), None))
        parts = []
        if pickup:
            km = pickup.get("distance_km")
            parts.append(f"самовивіз{f' за {km:.1f} км' if km is not None else ''} — "
                         f"{_fmt_uah(pickup['cost_uah'])}")
        if home:
            parts.append(f"{home['label'].lower()} {_fmt_uah(home['cost_uah'])}")
            tier = home.get("next_tier")
            if tier and tier.get("from_uah"):
                parts.append(f"від {_fmt_uah(tier['from_uah'])} — {_fmt_uah(tier['cost_uah'])}")
        below = [o for o in (pickup, home) if o and not o.get("meets_minimum")]
        # Гаразд, якщо хоч один зі способів приймає кошик такої суми.
        ok = (any(o.get("meets_minimum") for o in (pickup, home) if o)
              if (pickup or home) else None)
        checks.append({
            "id": "delivery", "title": "Топати чи замовити", "ok": ok,
            "summary": " · ".join(parts) or "способів отримання не знайдено",
            "detail": (f"пак {_fmt_uah(total)} нижче мінімуму для: "
                       + ", ".join(o["label"].lower() for o in below)
                       if below and not ok else None),
            "tools": ["silpo_list_branches", "silpo_get_time_slots", "silpo_estimate_delivery⁺"],
        })
    except SilpoError as exc:
        checks.append({"id": "delivery", "title": "Топати чи замовити", "ok": None,
                       "summary": str(exc), "tools": ["silpo_estimate_delivery⁺"]})

    # 2. Вага — по справжньому кошику: ліміт лежить у слоті, а не в товарі.
    #    Кошик читаємо один раз — і для ваги, і для «чи пак уже в ньому».
    try:
        ctx = await context.ensure()
        detail = await silpo.call("silpo_get_shopping_cart_by_id",
                                  {"shoppingCartId": ctx["shoppingCartId"]})
        cart = detail.get("cart") or detail
        weight = await cart_weight_check(cart)
        caps = sorted([o for o in weight.get("options") or [] if o.get("max_kg")],
                      key=lambda o: o["delivery_type"] != "DeliveryHome")
        cap_text = ", ".join(f"{o['label'].lower()} до {o['max_kg']:.0f} кг" for o in caps[:2])
        lines = (cart.get("shipments") or [{}])[0].get("products") or []
        ids = {str(p.get("productId")) for p in lines}
        in_cart = sum(1 for i in pack["items"] if str(i.get("product_id")) in ids)
        not_yet = in_cart == 0 and bool(pack["items"])
        checks.append({
            "id": "weight", "title": "Вага кошика",
            "ok": None if not_yet else not weight.get("blocked"),
            "summary": (f"кошик {weight['cart_weight_kg']} кг"
                        + (f" · {cap_text}" if cap_text else "")),
            "detail": ("пак ще не в кошику — вага рахується по тому, що в ньому є"
                       if not_yet else (weight.get("verdict") if weight.get("blocked") else None)),
            "in_cart": in_cart,
            "tools": ["silpo_get_shopping_cart_by_id", "silpo_get_time_slots"],
        })
    except SilpoError as exc:
        checks.append({"id": "weight", "title": "Вага кошика", "ok": None,
                       "summary": str(exc), "tools": ["silpo_get_shopping_cart_by_id"]})

    # 3–4. Купон і промо — одним проходом по перках, звіреним із паком.
    try:
        offers = await optimize_pack(pack["id"])
        coupons = offers.get("coupons") or []
        dead = offers.get("coupons_ineligible") or []
        if coupons:
            c = coupons[0]
            summary = (f"«{(c.get('text') or '')[:48]}» {c.get('reward') or ''} ляже на "
                       f"{'замовлення' if c.get('order_wide') else 'кошик'} — canBeAppliedToOrder")
            ok = True
        elif dead:
            c = dead[0]
            summary = f"«{(c.get('text') or '')[:48]}» на цей кошик не ляже — canBeAppliedToOrder: false"
            ok = False
        else:
            summary = "жоден із купонів не про цей кошик"
            ok = None
        fine = []
        if coupons and coupons[0].get("delivery_only"):
            fine.append("лише з доставкою, не самовивозом")
        if coupons and coupons[0].get("warning"):
            fine.append(str(coupons[0]["warning"]).lower())
        if len(coupons) > 1:
            fine.append(f"ще {len(coupons) - 1} підходить")
        checks.append({
            "id": "coupon", "title": "Купон", "ok": ok, "summary": summary,
            "detail": " · ".join(fine) or None,
            "coupons": coupons, "coupons_ineligible": dead,
            "tools": ["silpo_get_my_coupons", "silpo_get_coupon_details"],
        })
        promos = offers.get("activate_promos") or []
        fits = [p for p in promos if p.get("applies_to")]
        limit = int((offers.get("promo_limit") or {}).get("maxSelect") or 5)
        checks.append({
            "id": "promo", "title": "Промо",
            "ok": True if fits else None,
            "summary": (f"обрано {len(fits)} із {limit}, що лягають на кошик"
                        if fits else "жодне з персональних промо не про цей кошик"),
            "detail": ("; ".join((p.get("text") or "")[:40] for p in fits[:2]) if fits else None),
            "promos": fits, "promo_limit": offers.get("promo_limit"),
            "tools": ["silpo_get_my_promos", "silpo_select_promos⁺"],
        })
    except SilpoError as exc:
        checks.append({"id": "coupon", "title": "Купон", "ok": None, "summary": str(exc),
                       "tools": ["silpo_get_my_coupons"]})
        checks.append({"id": "promo", "title": "Промо", "ok": None, "summary": str(exc),
                       "tools": ["silpo_get_my_promos"]})

    failed = [c["title"].lower() for c in checks if c["ok"] is False]
    verdict = ("Разом — без сюрпризів на касі." if not failed
               else "Перед оформленням варто глянути: " + ", ".join(failed) + ".")
    return {
        "pack": {"id": pack["id"], "name": pack["name"], "total_uah": pack.get("total_uah"),
                 "item_count": len(pack["items"])},
        "checks": checks, "verdict": verdict, "all_clear": not failed,
        "checkout_url": CHECKOUT_URL,
        "note": ("Чотири перевірки — на тих самих tools, що вже є в MCP «Сільпо». "
                 "Оформлення підтверджує людина."),
    }


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

async def mood_pack(mood: str, max_uah: float | None = None,
                    items: list[str] | None = None, avoid: list[str] | None = None,
                    novelty: str = "any", prefer_promo: bool = False) -> dict:
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
    pack = await build_pack(f"Настрій: {mood}", queries, max_uah=max_uah, avoid=avoid,
                            novelty=novelty, prefer_promo=prefer_promo)
    pack["mood"] = key
    pack["from_model"] = bool(items)
    return pack


def scenarios() -> dict:
    """Довідник доступних сценаріїв — щоб UI не хардкодив списки."""
    return {"moods": sorted(_MOODS)}


# ---------------------------------------------------------------------------
# Страва на суму — узагальнення «сніданку»
# ---------------------------------------------------------------------------
async def meal_pack(query: str | None = None, meal: str | None = None,
                    max_uah: float | None = None, equipment: list[str] | None = None,
                    avoid: list[str] | None = None, serves: int | None = None,
                    prefer_promo: bool = False, novelty: str = "any") -> dict:
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
                                    avoid=avoid, prefer_promo=prefer_promo, novelty=novelty)
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
                                    avoid=avoid, prefer_promo=prefer_promo, novelty=novelty)
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
                       max_price: float | None = None, same_brand: bool = False,
                       keep: list[str] | None = None) -> dict:
    """Варіанти заміни позиції — з фото, цінами й фільтрами. БЕЗ самої заміни.

    Args:
        prefer: "cheaper" — дешевше, "promo" — зі знижкою, "any" — усе схоже.
        query: власний пошук замість «схожих» — коли гість знає, чого хоче.
        max_price: стеля ціни.
        same_brand: лишити лише той самий бренд — «те саме, тільки дешевше».
        keep: ознаки, які не можна втрачати при заміні: «2,5%», «без лактози».
            Саме це відрізняє розумну заміну від «ось щось схоже».
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

    # Розумна заміна: не «щось схоже», а «та сама жирність, той самий бренд».
    # Ознаку беремо з назви поточного товару — інших даних MCP не дає.
    lost: list[str] = []
    if same_brand:
        brands = _brands(current.get("name", ""))
        if brands:
            kept = [p for p in pool if any(b in (p.get("name") or "").lower() for b in brands)]
            lost += [] if kept else [f"бренд «{brands[0]}»"]
            pool = kept or pool
    for mark in (keep or []):
        low = mark.lower()
        kept = [p for p in pool if low in (p.get("name") or "").lower()]
        if kept:
            pool = kept
        else:
            lost.append(mark)
    pool.sort(key=lambda p: p.get("price") or 1e9)

    return {
        "pack_id": pack_id,
        "current": {"product_id": current["product_id"], "name": current["name"],
                    "price_uah": price, "image": current.get("image"),
                    "slug": current.get("slug")},
        "filters": {"prefer": prefer, "query": query, "max_price": max_price,
                    "same_brand": same_brand, "keep": keep or []},
        "could_not_keep": lost,
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


async def cart_weight_check(cart: dict | None = None) -> dict:
    """Чи влізе кошик у доставку за вагою.

    У слотах є `maxWeight` (40 кг для доставки додому), а в кошику —
    `calculation.delivery.totalWeight`. Ніхто їх не звіряє, і про перевищення
    гість дізнається від кур'єра. Це перевірка ДО оформлення.

    Args:
        cart: уже прочитаний кошик — щоб у зведеній перевірці не читати його вдруге.
    """
    ctx = await context.ensure()
    if cart is None:
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


# ---------------------------------------------------------------------------
# Розумний бюджет: «лишилось 840 ₴ на тиждень»
# ---------------------------------------------------------------------------
async def budget_pack(budget_uah: float, days: int = 7, novelty: str = "any",
                      avoid: list[str] | None = None, prefer_promo: bool = False) -> dict:
    """Кошик рівно під залишок бюджету, зібраний із власних звичок гостя.

    Порядок не випадковий: спершу те, що вже мало б закінчитись (цикл покупки з
    чеків), потім те, що людина бере найчастіше. Бюджет — жорстка стеля, і те,
    що не влізло, названо поіменно, а не мовчки викинуто.
    """
    from .game import all_receipts

    orders = await all_receipts()
    habits = _habits(orders)
    if not habits:
        raise SilpoError("У чеках замало повторів, щоб зрозуміти звички.")

    # Скільки з кожної звички випадає на цей період: береш воду раз на 17 днів,
    # плануємо 7 — це 0.4 пляшки, тобто одна, але з нижчим пріоритетом.
    ranked = []
    for habit in habits:
        due_first = 0 if habit["due"] else 1
        rate = days / max(habit["cycle_days"], 1)
        ranked.append((due_first, -habit["times"] * rate, habit))
    ranked.sort(key=lambda r: (r[0], r[1]))
    queries = [_short_query(h["name"], 4) for _, _, h in ranked[:MAX_BATCH]]

    found = await search(queries, limit=6)
    avoid_terms = expand_avoid(avoid)
    chosen, skipped, total = [], [], 0.0
    for query in queries:
        left = budget_uah - total
        if left <= 0:
            skipped.append({"query": query, "reason": "бюджет вичерпано"})
            continue
        product, reason = _best(found.get(query) or [], avoid_terms, left, query=query,
                                novelty=novelty, prefer_promo=prefer_promo)
        if not product:
            skipped.append({"query": query, "reason": reason})
            continue
        chosen.append(to_item(product, query))
        total += product.get("price") or 0

    pack = packs.create(f"Бюджет {round(budget_uah)} ₴ на {days} дн.", chosen,
                        budget_uah=budget_uah, source="budget", avoid=avoid or [])
    pack["days"] = days
    pack["budget_uah"] = budget_uah
    pack["left_uah"] = round(budget_uah - pack["total_uah"], 2)
    pack["skipped"] = skipped
    pack["novelty"] = novelty
    pack["why"] = ("Порядок — від того, що вже мало б закінчитись, до того, що береш "
                   "найчастіше. Цикл покупки рахується з чеків, а не питається.")
    return pack


# ---------------------------------------------------------------------------
# Автоматичний тижневий закуп
# ---------------------------------------------------------------------------
async def weekly_pack(budget_uah: float | None = None, novelty: str = "any",
                      avoid: list[str] | None = None, prefer_promo: bool = True) -> dict:
    """Найагентніший сценарій: кошик на тиждень збирається сам.

    Складається з трьох джерел, і кожна позиція знає, звідки вона:
    комора (чого немає вдома), звички (що мало б закінчитись) і акції (те, що
    гість любить і на що зараз знижка). Людині лишається натиснути «Підтвердити».
    """
    from . import proposed, weights as tastes
    from .game import all_receipts

    reasons: dict[str, str] = {}
    queries: list[str] = []

    try:
        missing = await proposed.pantry_missing()
        for row in (missing.get("missing") or [])[:8]:
            name = row.get("name") or row.get("query")
            if name and name not in queries:
                queries.append(name)
                reasons[name] = "немає вдома"
    except Exception:  # noqa: BLE001 — комора порожня чи не підключена, це не привід падати
        missing = {"missing": []}

    orders = await all_receipts()
    for habit in [h for h in _habits(orders) if h["due"]][:10]:
        name = _short_query(habit["name"], 4)
        if name not in queries:
            queries.append(name)
            reasons[name] = f"цикл {habit['cycle_days']} дн., минуло {habit['days_since']}"

    for row in tastes.snapshot(limit=30)["loved"][:6]:
        name = _short_query(row["name"], 3)
        if name not in queries:
            queries.append(name)
            reasons[name] = f"любиш це (вага {row['weight']})"

    if not queries:
        raise SilpoError("Ні комори, ні звичок — нема з чого зібрати тиждень.")

    pack = await build_pack("Тиждень", queries[:MAX_BATCH], max_uah=budget_uah,
                            avoid=avoid, prefer_promo=prefer_promo, novelty=novelty)
    for item in pack["items"]:
        item["because"] = reasons.get(item.get("query"), "звичка з чеків")
    pack["sources"] = {"pantry": len(missing.get("missing") or []),
                       "habits_due": sum(1 for r in reasons.values() if r.startswith("цикл")),
                       "loved": sum(1 for r in reasons.values() if r.startswith("любиш"))}
    pack["confirm_required"] = True
    pack["why"] = ("Комора + цикли покупок + акції на улюблене. Кожна позиція "
                   "пояснює себе — інакше автоматичний кошик неможливо довірити.")
    return pack


# ---------------------------------------------------------------------------
# Shopping Mission: «шашлик на шістьох»
# ---------------------------------------------------------------------------
# Тема зустрічі лягає або на реальний набір «Сільпо», або на перелік позицій.
# `once` — те, що не множиться на людей: мішок вугілля лишається одним і на
# трьох, і на шістьох. Без цього «шашлик на шістьох» дає три мішки вугілля.
_MISSIONS = {
    "шашлик": {"items": ["шия свиняча", "цибуля ріпчаста", "лаваш", "соус томатний",
                         "вугілля деревне", "пиво світле", "вода мінеральна"],
               "per_person": 0.45, "once": ["вугілля", "соус"]},
    "настолки": {"items": ["чипси", "сухарики", "кола", "піца заморожена", "цукерки"],
                 "per_person": 0.35, "once": []},
    "пікнік": {"items": ["багет", "сир твердий", "ковбаса сирокопчена", "помідор",
                         "вино біле", "серветки"], "per_person": 0.4,
               "once": ["серветки"]},
    "день народження": {"items": ["торт", "вино ігристе", "сік", "виноград", "свічки"],
                        "per_person": 0.5, "once": ["торт", "свічки"]},
    "сніданок на всіх": {"items": ["яйця", "бекон", "хліб", "кава", "сік апельсиновий"],
                         "per_person": 0.35, "once": ["кава"]},
}


# ---------------------------------------------------------------------------
# Не забудь: нагадування за циклом покупок
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Вечеря на всю родину
# ---------------------------------------------------------------------------
# Що вважаємо білком «після залу»: трекер каже про тренування, а страва з
# таким складником отримує перевагу. Список короткий і навмисно очевидний.
_PROTEIN = ("куряче філе", "лосось", "стейк", "креветки", "яйця", "фарш", "індич", "тунець")
# Те, що «до столу» береться зі смаків учасника, лише коли це напій: якщо Назар
# любить піцу, а на вечерю паста, друга страва на столі — не «його своє».
_DRINKS = ("кола", "сік", "вино", "пиво", "вода", "лимонад", "чай", "кава", "напій",
           "квас", "морс", "смузі", "компот")


def _promo_fits(promo: dict) -> bool:
    """Чи промо стосується ТИПУ товару, а не випадкового слова в назві."""
    stems = _stems(promo.get("text", ""))
    for hit in promo.get("applies_to") or []:
        first = ((hit.get("name") or "").split() or [""])[0].lower()[:3]
        if len(first) >= 3 and any(stem.startswith(first) for stem in stems):
            return True
    return False


def _stems_match(a: str, b: str) -> bool:
    """«масло вершкове» ↔ «Масло вершкове 82%»: збіг за коренем першого слова."""
    ra, rb = _stem((a or "").lower().split()[0]), _stem((b or "").lower().split()[0])
    return bool(ra) and len(ra) >= 4 and (ra in rb or rb in ra)


async def family_pack(theme: str = "вечеря", max_uah: float | None = None,
                      novelty: str = "any", prefer_promo: bool = False,
                      avoid: list[str] | None = None,
                      equipment: list[str] | None = None,
                      dish: str | None = None) -> dict:
    """Вечеря на всю родину: спершу СТРАВА, потім кошик під неї.

    «Збери вечерю» — це не список продуктів, а відповідь на «що готуємо».
    Тому агент спочатку обирає страву, і обирає її з усіх персональних даних
    одразу: алергії кожного відхиляють рецепти (з іменем того, чия алергія),
    смаки родини й трекер ранжують решту, ваги з чеків тримають звичне вище.
    Далі кошик: складники страви мінус те, що вже є вдома (комора), плюс
    «до столу» — напій кожному, корм улюбленцю, підказки трекера. Наприкінці
    знижки: купони й промо під цей кошик застосовуються самі, без кнопки.

    Порядок джерел і є правилом. Алергія ВИКЛЮЧАЄ й не обходиться нічим:
    трекер може радити горіхи після залу скільки завгодно — у кошик вони не
    потраплять. Решта лише додає й ранжує.

    Смаки учасників MCP «Сільпо» не віддає («Простір вподобань» живе в
    застосунку, в API його немає), тож їх тримає наш шар — і саме цього ми
    просимо в «Сільпо».
    """
    from . import game, proposed, weights as tastes

    prefs = await proposed.get_family_preferences()
    members = prefs.get("members") or []
    pets = prefs.get("pets") or []
    people = max(1, len(members))

    # ── 1. Алергії: терміни й ЛЮДИ за ними ─────────────────────────────────
    blocked: list[str] = []
    who: dict[str, list[str]] = {}
    owner: dict[str, set[str]] = {}
    direct: dict[str, set[str]] = {}

    def forbid(allergen: str, name: str) -> None:
        blocked.append(allergen)
        who.setdefault(allergen, []).append(name)
        # «арахіс» розгортається й у «горіх» — це правильно для фільтра, але
        # підпис «кедрові горіхи — Оля» збив би з пантелику: у Олі арахіс.
        # Тому автором терміна вважаємо того, чий алерген він і є, а решту
        # згадуємо лише коли прямого власника немає.
        direct.setdefault(_stem(allergen.lower()), set()).add(name)
        for term in expand_avoid([allergen]):
            owner.setdefault(term, set()).add(name)

    def whose(term: str) -> list[str]:
        return sorted(direct.get(term) or owner.get(term) or ())

    for member in members:
        for allergen in member.get("allergies") or []:
            forbid(allergen, member.get("name") or "хтось із рідних")
    for allergen in avoid or []:
        if allergen not in who:
            forbid(allergen, "профіль гостя")
    avoid_all = list(dict.fromkeys((avoid or []) + blocked))
    considered = [{"term": term, "who": sorted(set(names))} for term, names in sorted(who.items())]

    # ── 2. Контекст: трекери, ваги, комора ─────────────────────────────────
    wellbeing = proposed.wellbeing_state().get("wellbeing") or {}
    hints = proposed.wellbeing_hints(wellbeing)
    snapshot = tastes.snapshot(limit=20)
    pantry = proposed.pantry_state()
    at_home = [row for row in pantry.get("items") or [] if not row.get("expired")]
    spoiled = [row for row in pantry.get("items") or [] if row.get("expired")]

    # ── 3. Страва ──────────────────────────────────────────────────────────
    found = proposed.find_recipes(meal="вечеря", equipment=equipment, avoid=avoid_all, limit=20)
    rejected = []
    for row in found.get("rejected") or []:
        names = whose(row.get("term")) if row.get("reason") == "алергія" else []
        rejected.append({**row, "who": names,
                         "said": (f'{row["title"]} — {row.get("item")}: '
                                  + (", ".join(names) or "алергія") if row.get("reason") == "алергія"
                                  else f'{row["title"]} — {row.get("detail")}')})

    def score(recipe: dict) -> tuple[float, list[str]]:
        points, notes = 0.0, []
        text = " ".join([recipe["title"], *recipe["items"]]).lower()
        for member in members:
            hits = [like for like in member.get("likes") or [] if _stem(like.lower()) in text]
            if hits:
                points += 2 * len(hits)
                notes.append(f'{member.get("name")} любить {", ".join(hits)}')
        if wellbeing.get("workout") and any(p in text for p in _PROTEIN):
            points += 1.5
            notes.append(f'трекер: тренування ({wellbeing["workout"]}) — страва з білком')
        taste = sum(max(0.0, tastes.weight_of(i)) for i in recipe["items"])
        if taste >= 3:
            points += min(1.0, taste / 10)
            notes.append(f"звичне з чеків: вага складників +{round(taste, 1)}")
        if recipe.get("serves", 2) >= people:
            points += 0.5
        return points, notes

    ranked = sorted(((score(r), r) for r in found.get("recipes") or []),
                    key=lambda pair: -pair[0][0])
    if not ranked:
        raise SilpoError("Під алергії й техніку родини не знайшлось жодної вечері — "
                         "спробуй позначити більше техніки в профілі.")
    # `dish` — гість натиснув «або: Курка з овочами». Вибір із того самого
    # відібраного списку: страва з алергеном не стане доступною і за проханням.
    pick = next((pair for pair in ranked
                 if dish and pair[1]["title"].lower() == dish.strip().lower()), ranked[0])
    (best_points, best_notes), dish = pick
    alternatives = [{"title": r["title"], "why": notes[:2], "points": pts}
                    for (pts, notes), r in ranked if r is not dish][:2]
    scale = 1 if dish.get("serves", 2) >= people else -(-people // max(1, dish.get("serves", 2)))

    # ── 4. Черга запитів ───────────────────────────────────────────────────
    queries: list[str] = []
    reasons: dict[str, dict] = {}
    skipped_home: list[dict] = []

    def want(query: str, source: str, why: str) -> bool:
        query = (query or "").strip().lower()
        if not query or query in reasons:
            return False
        queries.append(query)
        reasons[query] = {"source": source, "why": why}
        return True

    for item in dish["items"]:
        home = next((row for row in at_home if _stems_match(item, row.get("name", ""))), None)
        if home:
            skipped_home.append({"query": item, "have": home.get("name"),
                                 "expires": home.get("expires")})
            continue
        want(item, "dish", f'для страви «{dish["title"]}»')
    for pet in pets:
        kind = "котів" if "cat" in str(pet.get("slug") or pet.get("kind") or "").lower() else "собак"
        want(f"корм для {kind}", "family", f"у родині {pet.get('name')}")
    covered = " ".join(dish["items"] + [dish["title"]]).lower()
    for member in members:
        likes = member.get("likes") or []
        if any(_stem(like.lower()) in covered for like in likes):
            continue    # страва вже його — окремого «свого» до столу не треба
        drink = next((like for like in likes if any(d in like.lower() for d in _DRINKS)), None)
        if drink:
            want(drink, "family", f"{member.get('name')} це любить")
    # З трекера — по кілька підказок на сигнал, не всі підряд: білок уже в
    # страві, а «чай» від настрою поруч із кавою від недосипу — це два чайники.
    per_signal: dict[str, int] = {}
    for hint in hints:
        if any(p in hint["query"] for p in _PROTEIN) or per_signal.get(hint["why"], 0) >= 3:
            continue
        if sum(per_signal.values()) >= 4:
            break
        if want(hint["query"], "tracker", f"трекер · {hint['why']}"):
            per_signal[hint["why"]] = per_signal.get(hint["why"], 0) + 1

    pack = await build_pack(f'Вечеря: {dish["title"]}', queries[:MAX_BATCH], max_uah=max_uah,
                            avoid=avoid_all, prefer_promo=prefer_promo, novelty=novelty)

    # ── 5. Підписи на рядках ───────────────────────────────────────────────
    for row in pack.get("excluded") or []:
        row["who"] = ", ".join(whose(row["term"])) or None
    used = {"dish": 0, "family": 0, "tracker": 0}
    extras: dict[str, list[str]] = {"family": [], "tracker": []}
    lifted: list[str] = []
    for item in pack["items"]:
        row = reasons.get(item.get("query")) or {"source": "dish", "why": "до вечері"}
        item["because"] = row["why"]
        used[row["source"]] = used.get(row["source"], 0) + 1
        if row["source"] in extras:
            # Якщо запитане зняла алергія і в кошик лягло сусіднє — у підсумку
            # має стояти те, що ЛЯГЛО: «кунжут замість горіхів», а не «горіхи».
            swapped = [d for d in pack.get("excluded") or [] if d["query"] == item.get("query")]
            extras[row["source"]].append(
                f'{_short_query(item.get("name", ""), 2).lower()} замість «{item.get("query")}»'
                if swapped else (item.get("query") or ""))
        if row["source"] == "dish" and scale > 1 and not item.get("weighted"):
            item["qty"] = (item.get("qty") or 1) * scale
            item["scaled"] = f'× {scale} — рецепт на {dish.get("serves")}, вас {people}'
        weight = tastes.own_weight_of(item.get("name", ""))
        if weight >= 2:
            item["because"] += f" · береш регулярно (вага +{round(weight, 1)})"
            lifted.append(item.get("query") or _short_query(item.get("name", ""), 2))
        cut = [d for d in pack.get("excluded") or [] if d["query"] == item.get("query")]
        if cut:
            names = ", ".join(sorted({n for d in cut for n in whose(d["term"])}))
            item["note"] = (f'з «{item.get("query")}» {len(cut)} поз. зняла алергія'
                            + (f" — {names}" if names else ""))
    for row in pack.get("skipped") or []:
        if (row.get("reason") or "").startswith("пропущено через"):
            names = sorted({n for d in pack.get("excluded") or []
                            if d["query"] == row["query"] for n in whose(d["term"])})
            if names:
                row["because"] = "алергія: " + ", ".join(names)
                row["reason"] = "зняла алергія — " + ", ".join(names)
    pack["skipped"] = (pack.get("skipped") or []) + [
        {"query": h["query"], "reason": f'є вдома: {h["have"]}', "home": True} for h in skipped_home]
    if scale > 1:
        packs.set_items(pack["id"], pack["items"])

    # ── 6. Знижки — самі, без кнопки ───────────────────────────────────────
    offers = await optimize_pack(pack["id"])
    # Обираємо самі лише промо, які справді лягають на пак. Збіг за одним
    # коренем («мелен» у «каву мелену» й «часник мелений») — це не збіг.
    promo_ids = [p["id"] for p in offers.get("activate_promos") or [] if _promo_fits(p)]
    for promo in offers.get("activate_promos") or []:
        promo["selected"] = promo["id"] in promo_ids
    if promo_ids:
        offers["selected"] = await proposed.select_promos(promo_ids, offers.get("promo_limit"))
    pack["offers"] = offers

    # ── 7. Вихід ───────────────────────────────────────────────────────────
    pack["dish"] = {**{k: dish.get(k) for k in ("id", "title", "minutes", "serves", "steps",
                                                  "equipment", "items")},
                    "why": best_notes, "for_people": people, "scale": scale}
    pack["dishes_rejected"] = rejected
    pack["dishes_other"] = alternatives
    pack["family"] = {"members": members, "pets": pets}
    pack["blocked_for_everyone"] = sorted(set(blocked))
    pack["considered_allergies"] = considered
    pack["blocked_by"] = considered
    pack["because"] = [f'без «{c["term"]}», бо {", ".join(c["who"])}' for c in considered]

    cut_total = len(pack.get("excluded") or [])
    label = {q: r["why"].replace(" це любить", "").replace("у родині ", "")
             for q, r in reasons.items()}
    family_extras = [f'{q} — {label[q]}' for q in extras["family"]]
    tracker_extras = [q for q in extras["tracker"]]
    tracker_cut = [f'{row["query"]} — {row["reason"]}' for row in pack.get("skipped") or []
                   if reasons.get(row["query"], {}).get("source") == "tracker"
                   and (row.get("reason") or "").startswith("зняла алергія")]
    promo_line = []
    if offers.get("coupons"):
        promo_line.append(f'{len(offers["coupons"])} купон(и) спрацюють на касі')
    if promo_ids:
        promo_line.append(f'промо обрано {len(promo_ids)} із ліміту '
                          f'{offers.get("promo_limit", {}).get("maxSelect") or 5}')
    if offers.get("multibuy"):
        promo_line.append(f'мультипак −{offers.get("multibuy_saving_uah")} ₴')
    # `short` — рядок у стовпчик під кошиком; `did` — повне пояснення для
    # панелі «Що відбувається» й моделі.
    short_tracker = " · ".join(part for part in (
        f'{wellbeing["workout"]}' if wellbeing.get("workout") else None,
        f'сон {str(wellbeing["sleep_hours"]).replace(".", ",")} год'
        if wellbeing.get("sleep_hours") else None) if part)
    short_promo = " · ".join(part for part in (
        f'{len(offers["coupons"])} купон' if offers.get("coupons") else None,
        f'{len(promo_ids)} промо' if promo_ids else None) if part)
    pack["sources"] = [
        {"id": "family", "title": "Сімейна група",
         "short": ", ".join([m.get("name") or "?" for m in members] + [p.get("name") or p.get("kind") or "?" for p in pets]),
         "tool": "silpo_get_my_family + silpo_get_family_preferences",
         "did": (", ".join(f'{m.get("name")}' + (f' ({m["age"]} р.)' if m.get("age") else "")
                           for m in members)
                 + (", " + ", ".join(f'{p.get("kind")} {p.get("name")}' for p in pets) if pets else "")
                 + f'. Страва — бо {best_notes[0] if best_notes else "підходить усім"}'
                 + (f'. До столу: {"; ".join(family_extras)}' if family_extras else ""))},
        {"id": "allergy", "title": "Алергії",
         "short": (", ".join(f'{c["term"]} ({", ".join(c["who"])})' for c in considered)
                   if considered else "не вказано"),
         "tool": "silpo_get_family_preferences + silpo_find_recipes",
         "did": ("враховано: " + "; ".join(f'{c["term"]} — {", ".join(c["who"])}' for c in considered)
                 + (". Відхилено страви: " + ", ".join(
                        r["title"] for r in rejected if r.get("reason") == "алергія")
                    if any(r.get("reason") == "алергія" for r in rejected) else "")
                 + (f'. На підборі знято товарів: {cut_total}' if cut_total else ""))
                if considered else "ніхто не вказав обмежень"},
        {"id": "tracker", "title": "Трекери", "short": short_tracker or "не підключені",
         "tool": "silpo_wellbeing_state",
         "did": (", ".join(part for part in (
                     wellbeing.get("source"),
                     f'тренування: {wellbeing["workout"]}' if wellbeing.get("workout") else None,
                     f'сон {wellbeing["sleep_hours"]} год' if wellbeing.get("sleep_hours") else None,
                 ) if part)
                 + (" → страва з білком" if any("білком" in n for n in best_notes) else "")
                 + (f'; до столу: {", ".join(tracker_extras)}' if tracker_extras else "")
                 + (f'; просив {"; ".join(tracker_cut)}' if tracker_cut else ""))
                or "трекери не підключені"},
        {"id": "taste", "title": "Ваги смаку", "short": f'{snapshot["tracked_products"]} товарів із чеків',
         "tool": "silpo_get_taste_weights",
         "did": f'{snapshot["tracked_products"]} товарів із чеків і свайпів'
                + (f'; підняли: {", ".join(lifted[:3])}' if lifted else "; у цьому паку нічого не змінили")},
        {"id": "pantry", "title": "Комора",
         "short": (f'вдома є {", ".join(h["have"].lower() for h in skipped_home[:2])}' if skipped_home
                   else "вдома нічого зі страви"),
         "tool": "silpo_pantry_state",
         "did": ((f'вдома є {", ".join(h["have"] for h in skipped_home)} — не купуємо'
                  if skipped_home else "зі складників страви вдома немає нічого")
                 + (f'; прострочено: {", ".join(r.get("name", "") for r in spoiled)}' if spoiled else ""))},
        {"id": "promo", "title": "Знижки", "short": short_promo or "нічого не лягло",
         "tool": "silpo_get_my_coupons + silpo_get_my_promos + silpo_select_promos",
         "did": "; ".join(promo_line) or "під цей кошик купонів і промо немає"},
    ]
    pack["why"] = ("Страва обрана з усіх персональних даних одразу, кошик — під неї. "
                   "Алергія будь-кого виключає і рецепт, і товар для ВСЬОГО столу.")
    game.mark("family_pack")
    return pack


# ---------------------------------------------------------------------------
# Компанія: спільна закупівля кількох людей під одну подію
# ---------------------------------------------------------------------------
async def crew_pack(crew_id: str | None = None, max_uah: float | None = None,
                    novelty: str = "any", prefer_promo: bool = False,
                    avoid: list[str] | None = None, crew_title: str | None = None) -> dict:
    """Кошик компанії: пропозиції всіх учасників, обмеження всіх учасників.

    Args:
        crew_id: яка компанія; без id — за назвою `crew_title`, а без обох —
            остання створена. У чаті кажуть «в компанію «Пікнік»», не id.

    Відрізняється від `family_pack` двома речами. По-перше, склад тут разовий і
    не привʼязаний до акаунтів — зібрались на пікнік і розійшлись. По-друге,
    список формує не організатор: кожна позиція приходить від конкретної людини
    і так і підписана. Кошик, зібраний однією людиною за всіх, завжди когось
    забуває.

    Алергія будь-кого блокує товар для ВСЬОГО кошика: на пікніку немає окремої
    тарілки, а є один мангал і один стіл.
    """
    from . import game, proposed

    if not crew_id and crew_title:
        crew_id = proposed.find_crew_id(crew_title)
        if not crew_id:
            raise SilpoError(f"Компанії «{crew_title}» немає — є лише ті, що в профілі.")
    crew_info = proposed.get_crew(crew_id)
    crew = crew_info.get("crew")
    if not crew:
        raise SilpoError("Компанії ще немає — створи її й поклич людей.")

    people = max(1, len(crew.get("members") or []) or int(crew.get("people") or 4))
    # Алергія й дієта — різні речі, і плутати їх нечесно. Алергія блокує товар
    # для ВСІХ: спільний мангал, спільна дошка, кросконтамінація. Дієта нікого
    # ні до чого не зобовʼязує — вегетаріанець не робить вечерю вегетаріанською
    # для шістьох. Тому дієти ми показуємо, але у фільтр не ставимо.
    blocked = [a["term"] for a in crew_info.get("allergies") or []]
    because = [f'виключено «{a["term"]}» для всіх, бо {a["who"]}'
               for a in crew_info.get("allergies") or []]
    diet_notes = [f'{d["who"]} — {d["term"]}: врахувати окремою позицією'
                  for d in crew_info.get("diets") or []]

    # Хто що запропонував. Порядок «по колу», а не «спершу весь список
    # організатора»: інакше на бюджеті першими відсікаються ті, хто мовчазніший.
    wishes = crew_info.get("wishes") or []
    by_person: dict[str, list[str]] = {}
    for w in wishes:
        by_person.setdefault(w["who"], []).append(w["item"])
    queries, owner = [], {}
    while any(by_person.values()):
        for name, items in by_person.items():
            if items:
                item = items.pop(0)
                queries.append(item)
                owner[item.lower()] = name
    if not queries:
        raise SilpoError("Ніхто ще нічого не запропонував — список компанії порожній.")

    pack = await build_pack(crew["title"], queries[:MAX_BATCH], max_uah=max_uah,
                            avoid=(avoid or []) + blocked, prefer_promo=prefer_promo,
                            novelty=novelty)

    # Кількості на компанію. Те, що не ділиться (вугілля, запальничка), лишається
    # одним — та сама логіка, що в «Шашлику на шістьох».
    once = ("вугілля", "запальнич", "мангал", "решітк", "пакет", "серветк", "фольг")
    for item in pack["items"]:
        query = (item.get("query") or "").lower()
        item["from_member"] = owner.get(query)
        if item["from_member"]:
            item["because"] = f'запропонував(ла) {item["from_member"]}'
        if any(word in query for word in once):
            item["qty"] = 1
            item["scaled"] = "одна на компанію"
        elif item.get("weighted"):
            item["qty"] = round(max(0.25 * people, 0.5), 1)
            item["scaled"] = f"×{item['qty']} кг на {people} осіб"
        else:
            item["qty"] = max(1, round(people / 2))
            item["scaled"] = f"×{item['qty']} на {people} осіб"

    skipped = pack.get("skipped") or []
    packs.set_items(pack["id"], pack["items"])
    pack = packs.get(pack["id"])
    pack["skipped"] = skipped
    pack["crew"] = {"id": crew["id"], "title": crew["title"],
                    "occasion": crew.get("occasion"),
                    "members": crew.get("members") or []}
    pack["people"] = people
    pack["because"] = because
    pack["blocked_for_everyone"] = sorted(set(blocked))
    # Та сама розмітка «Враховано алергії: горіхи (Марина)», що й у родини.
    by_term: dict[str, list[str]] = {}
    for a in crew_info.get("allergies") or []:
        by_term.setdefault(a["term"], []).append(a["who"])
    pack["considered_allergies"] = [{"term": t, "who": who} for t, who in by_term.items()]
    pack["diets"] = [d["term"] for d in crew_info.get("diets") or []]
    pack["diet_notes"] = diet_notes
    pack["proposed"] = True
    pack["simulated"] = bool(crew.get("demo"))
    pack["why"] = (f"Список зібрали {len(by_person)} людей, а не одна. Алергія "
                   "будь-кого виключає товар для всього кошика. Компанія — "
                   "новий концепт: у «Сільпо» такого немає ні в застосунку, "
                   "ні в MCP, тож учасники й пропозиції живуть у нас.")
    game.mark("crew_pack")
    return pack


# ---------------------------------------------------------------------------
# Правка пака словами
# ---------------------------------------------------------------------------
# У чаті людина каже «прибери пакет», а не «видали 1ee3d49d-7fc0-6ad2». Тому
# кожна операція шукає позицію за фрагментом назви — так само, як шукала б її
# людина очима в списку.
def _pack_or_last(pack_id: str | None) -> dict:
    """Пак за id, або останній зібраний. У чаті id ніхто не називає."""
    pack = (packs.get(pack_id) if pack_id else None) or packs.latest()
    if not pack:
        raise SilpoError("Пака ще немає — спершу збери набір.")
    return pack


def _find_item(pack: dict, query: str) -> dict:
    """Позиція пака за фрагментом назви. «чипси» → «Чипси Люкс зі смаком краба»."""
    low = (query or "").lower().strip()
    if not low:
        raise SilpoError("Не зрозумів, яку саме позицію.")
    items = pack.get("items") or []
    hit = ([i for i in items if low in (i.get("name") or "").lower()]
           or [i for i in items if low in (i.get("query") or "").lower()]
           # останній шанс: збіг за першим словом, бо «пакети» ≠ «пакет»
           or [i for i in items if low[:5] in (i.get("name") or "").lower()])
    if not hit:
        names = ", ".join((i.get("name") or "")[:26] for i in items[:6])
        raise SilpoError(f"У паку немає нічого схожого на «{query}». Є: {names}.")
    return hit[0]


async def pack_remove(query: str, pack_id: str | None = None) -> dict:
    """Прибирає позицію з пака за назвою: «прибери пакет»."""
    pack = _pack_or_last(pack_id)
    item = _find_item(pack, query)
    updated = packs.remove_item(pack["id"], item["product_id"])
    return {"pack": updated, "removed": item.get("name"),
            "said": f"Прибрав «{item.get('name')}»."}


async def pack_add(query: str, pack_id: str | None = None, qty: float = 1) -> dict:
    """Додає товар у пак за назвою: «додай молоко».

    Шукає в «Сільпо» так само, як під час збирання пака: з урахуванням алергій
    пака й ваг смаку. Тобто «додай сир» дасть той сир, який агент обрав би сам.
    """
    pack = _pack_or_last(pack_id)
    found = (await search([query], limit=8)).get(query) or []
    product, reason = _best(found, expand_avoid(pack.get("avoid")), None, query=query,
                            prefer_promo=bool(pack.get("prefer_promo")))
    if not product:
        raise SilpoError(f"Не знайшов «{query}»: {reason}.")
    item = to_item(product, query, qty=qty)
    updated = packs.add_item(pack["id"], item)
    return {"pack": updated, "added": item["name"], "price_uah": item["price"],
            "said": f"Додав «{item['name']}» за {item['price']} ₴."}


async def pack_set_qty(query: str, qty: float, pack_id: str | None = None) -> dict:
    """Змінює кількість позиції: «зроби три пляшки води»."""
    pack = _pack_or_last(pack_id)
    item = _find_item(pack, query)
    if qty <= 0:
        return await pack_remove(query, pack["id"])
    items = [{**i, "qty": qty} if i["product_id"] == item["product_id"] else i
             for i in pack["items"]]
    updated = packs.set_items(pack["id"], items)
    return {"pack": updated, "item": item.get("name"), "qty": qty,
            "said": f"«{item.get('name')}» — тепер {qty} шт."}


async def pack_swap_named(query: str, prefer: str = "cheaper",
                          pack_id: str | None = None) -> dict:
    """Міняє позицію за назвою: «заміни чипси на щось дешевше»."""
    pack = _pack_or_last(pack_id)
    item = _find_item(pack, query)
    result = await swap_item(pack["id"], item["product_id"], prefer=prefer)
    swapped = result.get("swapped")
    result["said"] = (f"Замінив «{swapped['from']}» на «{swapped['to']}» — "
                      f"{swapped['now_uah']} ₴ замість {swapped['was_uah']} ₴."
                      if swapped else result.get("note", "Заміни не знайшлось."))
    return result
