"""Tools, яких у MCP «Сільпо» ще немає — з робочою реалізацією.

Кожна функція тут названа так, як мав би зватися майбутній офіційний tool, і
пише слід у спільний трейс із позначкою ``kind="proposed"``. У демо видно, де
агент спирається на справжній API, а де — на те, що ми пропонуємо додати.

Реалізації не бутафорські: `also_bought` рахується зі справжніх чеків гостя,
`estimate_delivery` — з реальних магазинів і слотів, `family_preferences`
доповнює справжній склад родини нашими даними. Симуляція чесно позначена
полем ``simulated`` там, де інакше не вийде — насамперед у складі товару.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

from . import context
from .silpo import SilpoError, silpo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, ".mcp", "proposed.json")

SPEC_URL = "запропоновано командою Pack Agent для «Сільпо» AI Factory"


def _load() -> dict:
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _traced(name: str, args: dict):
    """Контекст-менеджер-подібний хелпер: повертає функцію завершення сліду."""
    started = time.perf_counter()
    return lambda note="": silpo.log_proposed(name, args, started, note=note)


# ---------------------------------------------------------------------------
# 1. Рецепти
# ---------------------------------------------------------------------------
# Обладнання, яке рецепт вимагає. Гість позначає своє в профілі — і рецепт із
# духовкою не пропонується тому, у кого лише плитка.
EQUIPMENT = ["сковорідка", "каструля", "духовка", "аерогриль", "мікрохвильовка",
             "блендер", "тостер", "мультиварка", "гриль"]

RECIPES = [
    {"id": "omlet", "title": "Омлет із сиром", "meal": "сніданок", "minutes": 10,
     "equipment": ["сковорідка"], "serves": 2,
     "items": ["яйця", "сир твердий", "молоко", "масло вершкове"],
     "steps": ["Збий 3 яйця з ложкою молока.", "Вилий на розігріту пательню з маслом.",
               "За хвилину додай тертий сир і склади навпіл."]},
    {"id": "syrnyky", "title": "Сирники", "meal": "сніданок", "minutes": 20,
     "equipment": ["сковорідка"], "serves": 2,
     "items": ["сир кисломолочний", "яйця", "борошно", "сметана"],
     "steps": ["Змішай сир, яйце і 2 ложки борошна.", "Сформуй сирники, обкачай у борошні.",
               "Смаж по 3 хвилини з боку. Подавай зі сметаною."]},
    {"id": "vivsyanka", "title": "Вівсянка з бананом", "meal": "сніданок", "minutes": 7,
     "equipment": ["каструля", "мікрохвильовка"], "serves": 1,
     "items": ["пластівці вівсяні", "банан", "молоко", "мед"],
     "steps": ["Залий пластівці гарячим молоком на 5 хвилин.",
               "Додай нарізаний банан і ложку меду."]},
    {"id": "tost", "title": "Тост з авокадо та яйцем", "meal": "сніданок", "minutes": 10,
     "equipment": ["тостер", "сковорідка"], "serves": 1,
     "items": ["хліб", "авокадо", "яйця"],
     "steps": ["Підсмаж хліб.", "Розімни авокадо виделкою, посоли.",
               "Зверху — яйце пашот або смажене."]},
    {"id": "granola", "title": "Йогурт із гранолою", "meal": "сніданок", "minutes": 3,
     "equipment": [], "serves": 1,
     "items": ["йогурт", "гранола", "ягоди"],
     "steps": ["Виклади йогурт у миску.", "Зверху — гранола і ягоди."]},
    {"id": "shakshuka", "title": "Шакшука", "meal": "сніданок", "minutes": 20,
     "equipment": ["сковорідка"], "serves": 2,
     "items": ["яйця", "томати консервовані", "цибуля", "перець солодкий", "паприка"],
     "steps": ["Обсмаж цибулю з перцем.", "Додай томати, туши 10 хвилин.",
               "Розбий яйця зверху, накрий кришкою на 5 хвилин."]},

    {"id": "karbonara", "title": "Паста карбонара", "meal": "обід", "minutes": 25,
     "equipment": ["каструля", "сковорідка"], "serves": 2,
     "items": ["спагеті", "бекон", "яйця", "сир пармезан"],
     "steps": ["Відвари спагеті до аль денте.", "Обсмаж бекон до хрусткого.",
               "Змішай жовтки з тертим сиром, з'єднай із гарячою пастою поза вогнем."]},
    {"id": "harbuz", "title": "Гарбузовий суп-пюре", "meal": "обід", "minutes": 35,
     "equipment": ["каструля", "блендер"], "serves": 4,
     "items": ["гарбуз", "картопля", "вершки", "цибуля"],
     "steps": ["Звари гарбуз із картоплею та цибулею.", "Збий блендером до пюре.",
               "Влий вершки, прогрій, не доводячи до кипіння."]},
    {"id": "tsezar", "title": "Салат Цезар", "meal": "обід", "minutes": 20,
     "equipment": ["сковорідка"], "serves": 2,
     "items": ["куряче філе", "салат ромен", "сухарики", "сир пармезан", "соус цезар"],
     "steps": ["Обсмаж філе, наріж смужками.", "Порви салат руками, додай сухарики.",
               "Заправ соусом, зверху — тертий пармезан."]},
    {"id": "burito", "title": "Буріто", "meal": "обід", "minutes": 25,
     "equipment": ["сковорідка"], "serves": 2,
     "items": ["тортилья", "фарш", "квасоля консервована", "сир твердий", "соус сальса"],
     "steps": ["Обсмаж фарш, додай квасолю й сальсу.", "Виклади на тортилью, посип сиром.",
               "Загорни конвертом і підрум'янь на сухій пательні."]},

    {"id": "kurka-duhovka", "title": "Курка з овочами", "meal": "вечеря", "minutes": 45,
     "equipment": ["духовка", "аерогриль"], "serves": 4,
     "items": ["куряче філе", "картопля", "морква", "олія оливкова", "спеції"],
     "steps": ["Наріж овочі великими шматками.", "Змішай із олією та спеціями.",
               "Запікай 40 хвилин при 190 °C разом із куркою."]},
    {"id": "ryz-krevetky", "title": "Рис із креветками", "meal": "вечеря", "minutes": 25,
     "equipment": ["сковорідка", "каструля"], "serves": 2,
     "items": ["рис", "креветки", "часник", "соєвий соус", "лимон"],
     "steps": ["Звари рис.", "Обсмаж креветки з часником 3 хвилини.",
               "З'єднай, влий соєвий соус і сік лимона."]},
    {"id": "pitsa-lavash", "title": "Піца на лаваші", "meal": "вечеря", "minutes": 15,
     "equipment": ["духовка", "аерогриль"], "serves": 2,
     "items": ["лаваш", "соус томатний", "сир моцарела", "салямі", "оливки"],
     "steps": ["Змасти лаваш соусом.", "Виклади начинку, засип сиром.",
               "Запікай 10 хвилин при 200 °C."]},
    {"id": "steik", "title": "Стейк із гарніром", "meal": "вечеря", "minutes": 30,
     "equipment": ["сковорідка", "гриль"], "serves": 2,
     "items": ["стейк яловичий", "картопля", "масло вершкове", "розмарин"],
     "steps": ["Дай мʼясу дійти до кімнатної температури.",
               "Смаж по 3 хвилини з боку, полий маслом із розмарином.",
               "Дай відпочити 5 хвилин під фольгою."]},

    {"id": "panakota", "title": "Панакота", "meal": "десерт", "minutes": 20,
     "equipment": ["каструля"], "serves": 4,
     "items": ["вершки", "цукор", "желатин", "ваніль", "ягоди"],
     "steps": ["Прогрій вершки з цукром і ваніллю.", "Розчини желатин, з'єднай.",
               "Розлий по формах, у холодильник на 4 години."]},
    {"id": "yabluka", "title": "Печені яблука", "meal": "десерт", "minutes": 30,
     "equipment": ["духовка", "аерогриль", "мікрохвильовка"], "serves": 4,
     "items": ["яблука", "мед", "горіхи волоські", "кориця"],
     "steps": ["Вийми серцевину з яблук.", "Начини медом, горіхами й корицею.",
               "Запікай 25 хвилин при 180 °C."]},
]


def find_recipes(query: str | None = None, meal: str | None = None,
                 equipment: list[str] | None = None, avoid: list[str] | None = None,
                 serves: int | None = None, limit: int = 5) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Страва → складники, кроки, час і потрібне обладнання.

    Чому це має бути в «Сільпо», а не в кожного окремо: рецепт корисний лише
    тоді, коли складники одразу лягають в артикули магазину. Зараз кожен
    учасник вигадує власну базу — і жодна не звʼязана з каталогом.

    Args:
        query: назва страви або її частина.
        meal: сніданок / обід / вечеря / десерт.
        equipment: що є на кухні; рецепти, які вимагають іншого, відсіюються.
        avoid: алергії та несмаки — рецепт із таким складником не пропонується.
        serves: на скількох.
    """
    done = _traced("silpo_find_recipes",
                   {"query": query, "meal": meal, "equipment": equipment})
    from .facade import _blocked_by, expand_avoid  # локально: уникаємо циклу імпорту

    terms = expand_avoid(avoid)
    have = [e.lower() for e in (equipment or EQUIPMENT)]
    found = []
    for recipe in RECIPES + _load().get("family_recipes", []):
        if meal and recipe["meal"] != meal.lower().strip():
            continue
        if query and query.lower() not in recipe["title"].lower() \
                and not any(query.lower() in i for i in recipe["items"]):
            continue
        if recipe["equipment"] and not any(e in have for e in recipe["equipment"]):
            continue
        if any(_blocked_by(i, terms) for i in recipe["items"]):
            continue
        if serves and recipe["serves"] < serves:
            continue
        found.append(recipe)
    done(f"{len(found)} рецептів")
    return {"count": len(found), "recipes": found[:limit],
            "equipment_known": EQUIPMENT, "proposed": True,
            "spec": ("Повертає страви з переліком складників у вигляді пошукових запитів "
                     "або артикулів, кроками, часом і потрібним обладнанням. "
                     "Ідеально — з externalProductId для кожного складника, щоб "
                     "find_products_batch не вгадував. " + SPEC_URL)}


# ---------------------------------------------------------------------------
# 2. Склад товару
# ---------------------------------------------------------------------------
# Поки MCP не віддає інгредієнти, виводимо їх із назви та категорії. Це чесно
# позначено simulated=true — на такому не можна будувати медичні рішення.
_ALLERGEN_HINTS = {
    "горіхи": ["горіх", "арахіс", "фундук", "мигдал", "кеш", "волоськ", "пекан", "фісташ", "nut"],
    "молоко": ["молок", "вершк", "сметан", "сир", "йогурт", "кефір", "ряжан", "масло вершк"],
    "глютен": ["пшенич", "борошн", "хліб", "макарон", "сухар", "лаваш", "тортилья", "печиво"],
    "яйця": ["яйц", "яєчн", "майонез"],
    "риба і морепродукти": ["риб", "лосос", "тунець", "оселед", "креветк", "мідії", "кальмар"],
    "соя": ["соєв", "соя", "тофу"],
    "кунжут": ["кунжут", "тахін"],
}


async def get_product_composition(slug: str, name: str | None = None,
                                  force: bool = False) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Склад товару та алергени — зчитані з етикетки.

    Головна знахідка проєкту: склад у MCP «Сільпо» Є. Просто не текстом, а
    фотографією упаковки в `get_product_details.images`. На сайті людина його
    читає очима; агент читає розпізнаванням.

    Тут ми качаємо ці фото, збільшуємо втричі, проганяємо через Tesseract
    (українська) і витягуємо все після слова «Склад». Працює — перевірено на
    маслі «Ферма»: «Склад: вершки з коров'ячого молока».

    Це не заміна нормальному полю: OCR помиляється, фото буває розмите або
    його немає взагалі. Тому повертаємо ще й посилання на саму етикетку, щоб
    людина перевірила очима. Запит до «Сільпо» — віддавати той самий текст
    полем, бо він у них уже є.
    """
    done = _traced("silpo_get_product_composition", {"slug": slug})
    cached = (_load().get("compositions") or {}).get(slug)
    if cached and not force:
        done("з кешу")
        return cached

    await context.ensure()
    images, attributes, title = [], {}, name or slug
    try:
        raw = await silpo.call("silpo_get_product_details", {
            "branchId": silpo.ctx["branchId"], "slug": slug,
            "deliveryType": silpo.ctx["deliveryType"],
            "timeslotStart": silpo.ctx["timeslotStart"],
            "timeslotEnd": silpo.ctx["timeslotEnd"]})
        product = raw.get("product") or raw
        images = product.get("images") or []
        attributes = product.get("attributes") or {}
        title = product.get("name") or title
    except SilpoError as exc:
        done(f"деталі недоступні: {exc}")

    text, label_url = "", None
    for url in images[1:]:              # перше зображення — рендер товару, не етикетка
        got = await _ocr(url)
        if "склад" in got.lower():
            text, label_url = got, url
            break
        if got and not text:
            text, label_url = got, url

    ingredients = _ingredients_from(text)
    low = ((ingredients or "") + " " + title).lower()
    allergens = [group for group, words in _ALLERGEN_HINTS.items()
                 if any(w in low for w in words)]

    result = {
        "slug": slug, "name": title, "attributes": attributes,
        "ingredients": ingredients,
        "ocr_text": text[:600] or None,
        "label_image": label_url,
        "all_images": images,
        "allergens": allergens,
        "source": "етикетка (OCR)" if ingredients else "назва товару",
        "confidence": "середня" if ingredients else "низька",
        "simulated": not ingredients,
        "warning": ("Склад розпізнано з фотографії етикетки — літери могли зчитатись "
                    "неточно. Відкрий фото й перевір сам."
                    if ingredients else
                    "Етикетку розпізнати не вдалось: алергени вгадані з назви. "
                    "Обовʼязково перевір упаковку."),
        "proposed": True,
        "spec": ("Склад уже є в MCP — фотографією в images[]. Треба віддавати його "
                 "текстом: ingredients, allergens (за регламентом ЄС №1169/2011) і "
                 "may_contain. Дані в «Сільпо» вже зібрані — на етикетці. " + SPEC_URL),
    }
    data = _load()
    data.setdefault("compositions", {})[slug] = result
    _save(data)
    done("розпізнано з етикетки" if ingredients else "етикетку не знайдено")
    return result


async def _ocr(url: str) -> str:
    """Качає зображення, збільшує втричі й проганяє через Tesseract (ukr).

    Без збільшення дрібний шрифт етикетки не розпізнається взагалі — перевірено.
    """
    import subprocess
    import tempfile
    import httpx2
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return ""
    try:
        async with httpx2.AsyncClient(timeout=20) as http:
            data = (await http.get(url)).content
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "in")
            open(src, "wb").write(data)
            image = Image.open(src).convert("L")
            image = image.resize((image.width * 3, image.height * 3), Image.LANCZOS)
            image = ImageOps.autocontrast(image)
            big = os.path.join(tmp, "big.png")
            image.save(big)
            out = subprocess.run(["tesseract", big, "-", "-l", "ukr", "--psm", "3"],
                                 capture_output=True, timeout=60)
            return out.stdout.decode("utf-8", "replace")
    except Exception:
        return ""


def _ingredients_from(text: str) -> str | None:
    """Витягує все після «Склад» до кінця речення."""
    import re
    match = re.search(r"[Сс]клад\s*[:：]?\s*(.{5,400}?)(?:\.\s|$)", text or "", re.S)
    if not match:
        return None
    value = " ".join(match.group(1).split())
    return value if len(value) > 4 else None


# ---------------------------------------------------------------------------
# 3. Що беруть разом
# ---------------------------------------------------------------------------
async def also_bought(product_name: str, limit: int = 5) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Що беруть разом із цим товаром.

    Рахується з РЕАЛЬНИХ чеків гостя: якщо товар траплявся в чеку, дивимось,
    що лежало поруч. Справжній tool мав би рахувати це по всій мережі, а не по
    десяти чеках однієї людини — тоді працювало б і для новачків.
    """
    done = _traced("silpo_also_bought", {"product_name": product_name})
    from .facade import _raw_receipts

    orders = await _raw_receipts(10)
    key = (product_name or "").lower()[:6]
    together: dict[str, int] = {}
    hits = 0
    for order in orders:
        names = [p.get("name", "") for p in order.get("products", [])]
        if not any(key in n.lower() for n in names):
            continue
        hits += 1
        for other in names:
            if key in other.lower():
                continue
            together[other] = together.get(other, 0) + 1
    ranked = sorted(together.items(), key=lambda kv: -kv[1])[:limit]
    done(f"{hits} чеків із цим товаром")
    return {
        "product": product_name, "receipts_with_it": hits,
        "also_bought": [{"name": n, "times": c} for n, c in ranked],
        "source": "власні чеки гостя",
        "proposed": True,
        "spec": ("Має повертати товари, що найчастіше трапляються в одному чеку з "
                 "даним, по всій мережі та з урахуванням магазину й сезону. "
                 "Зараз агрегації по мережі немає — рахуємо лише по чеках гостя, "
                 "тож новому користувачу порадити нічого. " + SPEC_URL),
    }


# ---------------------------------------------------------------------------
# 4. Вартість доставки без кошика
# ---------------------------------------------------------------------------
def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


async def estimate_delivery(latitude: float, longitude: float,
                            cart_total_uah: float = 0, radius_km: float = 1.5,
                            limit: int = 4) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Порівняння способів отримання за координатами.

    Реалізовано на справжніх даних: координати магазинів беремо з
    `silpo_list_branches`, ціни й пороги — з `silpo_get_time_slots`. Окремий
    tool потрібен, бо зараз, щоб порівняти пʼять магазинів, треба пʼять разів
    тягнути слоти — а це секунди затримки в діалозі.
    """
    done = _traced("silpo_estimate_delivery",
                   {"latitude": latitude, "longitude": longitude,
                    "cart_total_uah": cart_total_uah})
    data = await silpo.call("silpo_list_branches", {"hasPickup": True})
    branches = []
    for b in data.get("branches", []):
        try:
            km = _haversine(latitude, longitude, float(b["latitude"]), float(b["longitude"]))
        except (TypeError, ValueError, KeyError):
            continue
        branches.append({**b, "distance_km": km})
    branches.sort(key=lambda b: b["distance_km"])
    walkable = [b for b in branches if b["distance_km"] <= radius_km]
    by_id = {b["branchId"]: b for b in branches}

    # Самовивіз обслуговують магазини поруч, а доставку — окремий хаб зі своїм
    # branchId. Питати лише найближчі магазини замало: доставки в списку не буде.
    targets: list[tuple[str, str | None, dict | None]] = [
        (b["branchId"], "SelfPickup", b) for b in (walkable or branches)[:limit]]
    types = await silpo.call("silpo_get_available_delivery_types",
                             {"latitude": latitude, "longitude": longitude})
    for option in types.get("options", []):
        branch_id = option.get("branchId")
        if branch_id and not any(t[0] == branch_id and t[1] == option["deliveryType"]
                                 for t in targets):
            targets.append((branch_id, option["deliveryType"], by_id.get(branch_id)))

    options = []
    for branch_id, delivery_type, branch in targets:
        try:
            slots = await silpo.call("silpo_get_time_slots", {
                "branchId": branch_id,
                **({"deliveryTypes": [delivery_type]} if delivery_type else {}),
                "limit": 60})
        except SilpoError:
            continue
        free = [s for s in slots.get("slots", []) if s.get("available")]
        by_type: dict[str, dict] = {}
        for slot in free:
            by_type.setdefault(slot.get("deliveryType", delivery_type or "?"), slot)
        for slot_type, slot in by_type.items():
            cost = slot.get("deliveryCost") or 0
            cheaper = None
            for tier in slot.get("deliveryCostMap") or []:
                if cart_total_uah >= (tier.get("fromOrderCost") or 0):
                    cost = tier.get("cost", cost)
                elif cheaper is None:
                    cheaper = {"cost_uah": tier.get("cost"),
                               "from_uah": tier.get("fromOrderCost"),
                               "need_more_uah": round((tier.get("fromOrderCost") or 0)
                                                      - cart_total_uah, 2)}
            distance = branch["distance_km"] if branch else None
            options.append({
                "branch": (f'{branch.get("city","")}, {branch.get("address","")}'
                           if branch else "хаб доставки"),
                "branchId": branch_id,
                "distance_km": distance,
                "walk_minutes": round(distance / 5 * 60) if distance is not None else None,
                "delivery_type": slot_type,
                "cost_uah": cost,
                "min_order_uah": slot.get("minOrderCost"),
                "meets_minimum": cart_total_uah >= (slot.get("minOrderCost") or 0),
                "slot": f'{slot.get("start","")[11:16]}–{slot.get("end","")[11:16]}',
                "next_tier": cheaper,
            })
    options.sort(key=lambda o: (o["cost_uah"], o["distance_km"] or 99))
    done(f"{len(options)} варіантів")
    return {
        "within_radius": len(walkable), "radius_km": radius_km,
        "options": options,
        "proposed": True,
        "spec": ("Один виклик замість list_branches + N×get_time_slots. Має приймати "
                 "координати й суму кошика та повертати всі способи отримання з "
                 "вартістю, порогом безкоштовності й найближчим слотом. " + SPEC_URL),
    }


# ---------------------------------------------------------------------------
# 5. Вподобання родини та компанії
# ---------------------------------------------------------------------------
async def get_family_preferences() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Смаки та алергії кожного члена родини.

    `silpo_get_my_family` віддає склад родини — імена, вік дітей, тварин. Але
    «Простір вподобань» із зонами «Гастро-зупинка», «Дитяча зона» та «Зоосвіт»
    у MCP не представлений, тож підібрати вечерю на всіх неможливо.

    Тут реальний склад родини доповнюється тим, що гість вказав у нашому
    застосунку — і одразу видно, чиїх даних бракує.
    """
    done = _traced("silpo_get_family_preferences", {})
    family = await silpo.call("silpo_get_my_family", {})
    stored = _load().get("family_prefs", {})

    members = []
    for member in family.get("members", []):
        key = member.get("profileId") or member.get("phone")
        role = "я" if member.get("itsMe") else "дорослий"
        known = key in stored and isinstance(stored.get(key), dict)
        members.append({
            "id": key, "name": member.get("name") or "без імені", "role": role,
            **(stored[key] if known else _demo_prefs_for(role)),
            "known": known, "demo": not known,
        })
    for child in family.get("children", []):
        key = child.get("id")
        birth = child.get("dateOfBirth") or ""
        age = None
        if len(birth) == 10:
            import datetime as dt
            born = dt.date.fromisoformat(birth)
            today = dt.date.today()
            age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        known = key in stored and isinstance(stored.get(key), dict)
        members.append({
            "id": key, "name": child.get("name"), "role": "дитина", "age": age,
            **(stored[key] if known else _demo_prefs_for("дитина")),
            "known": known, "demo": not known,
        })
    pets = [{"id": p.get("id"), "name": p.get("name"), "kind": p.get("slug")}
            for p in family.get("pets", [])]

    done(f'{len(members)} людей, {len(pets)} тварин')
    return {
        "members": members, "pets": pets,
        "missing_preferences": [m["name"] for m in members if not m["known"]],
        "proposed": True,
        "spec": ("Має віддавати для кожного члена родини його «Простір вподобань»: "
                 "улюблені категорії, харчові обмеження та алергії. Сьогодні "
                 "get_my_family дає лише склад родини — смаки лишаються в застосунку "
                 "і не доступні агенту. " + SPEC_URL),
    }


def set_member_preferences(member_id: str, likes: list[str] | None = None,
                           avoid: list[str] | None = None,
                           allergies: list[str] | None = None) -> dict:
    """Зберігає вподобання члена родини чи гостя компанії (наш бік)."""
    done = _traced("silpo_set_member_preferences", {"member_id": member_id})
    data = _load()
    prefs = data.setdefault("family_prefs", {})
    entry = prefs.setdefault(member_id, {"likes": [], "avoid": [], "allergies": []})
    for field, value in (("likes", likes), ("avoid", avoid), ("allergies", allergies)):
        if value is not None:
            entry[field] = value
    _save(data)
    done()
    return {"member_id": member_id, "preferences": entry, "proposed": True}


# ---------------------------------------------------------------------------
# 6. Свайпи (Департамент дивинок)
# ---------------------------------------------------------------------------
async def record_swipe(product_id: str, external_id: int | None = None,
                       liked: bool = True, name: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Памʼять про свайп — і «так», і «ні».

    «Обране» зберігає лише «так»: `add_or_update_favorite_products` туди пише,
    а відмову подіти нікуди. Через це агент повторно показує те, що гість уже
    відхилив. Свайп вправо тут іде у справжнє «Обране», свайп уліво лишається
    в нас — і саме його бракує в API.
    """
    done = _traced("silpo_record_swipe", {"product_id": product_id, "liked": liked})
    data = _load()
    swipes = data.setdefault("swipes", {})
    swipes[str(product_id)] = {"liked": bool(liked), "name": name,
                               "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    _save(data)
    mirrored = False
    if liked and external_id:
        try:
            await silpo.call("silpo_add_or_update_favorite_products", {
                "actions": [{"productId": product_id, "externalProductId": int(external_id),
                             "toDelete": False}]})
            mirrored = True
        except SilpoError:
            pass
    from . import weights as tastes
    moved = tastes.bump(name or str(product_id), "swipe_right" if liked else "swipe_left")
    done("вправо → «Обране»" if mirrored else "вліво → лише в нас")
    return {"product_id": product_id, "liked": liked, "name": name,
            "mirrored_to_favorites": mirrored,
            # Свайп зсуває вагу і товару, і його полиці — тож наступна підбірка
            # змінюється не лише для цього товару. Показуємо це одразу.
            "weight": moved.get("weight"),
            "category": moved.get("category"),
            "category_weight": moved.get("category_weight"),
            "effect": (f"{'+' if liked else '−'}2 до «{name}» і до полиці "
                       f"«{_aisle_of(name or '')[1]}»"),
            "total_swipes": len(swipes), "proposed": True,
            "spec": ("Має зберігати обидва напрямки свайпу з «Департаменту дивинок». "
                     "Відмова — половина сигналу для рекомендацій, і зараз вона "
                     "втрачається. " + SPEC_URL)}


async def swipe_deck(limit: int = 12) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Колода карток для «Департаменту дивинок».

    Картки не випадкові й не однакові для всіх. Беремо акційні товари з полиць,
    які гість уже любить (додатна вага категорії), плюс одну полицю «на виріст» —
    інакше підбірка замикається на тому самому. Усе, що вже свайпнули, зникає:
    саме памʼяті про відмови в API й немає.
    """
    from . import weights as tastes
    from .facade import search, to_item

    done = _traced("silpo_get_swipe_deck", {"limit": limit})
    swiped = {str(k) for k in (_load().get("swipes") or {})}
    snapshot = tastes.snapshot(limit=40)
    liked_shelves = [c for c in snapshot["categories"] if c["weight"] > 0][:4]
    # Одна полиця «на виріст» обовʼязково: якщо всі ваги додатні, беремо
    # найслабшу. Колода лише з улюбленого перестає бути відкриттям.
    cold = ([c for c in snapshot["categories"] if c["weight"] <= 0]
            or snapshot["categories"][-1:])[:1]

    queries, source = [], {}
    for shelf in liked_shelves + cold:
        query = shelf["title"].split(",")[0].split(" та ")[0].lower()
        queries.append(query)
        source[query] = shelf
    if not queries:
        queries, source = ["новинки", "десерт", "снеки"], {}

    found = await search(queries, limit=8)
    cards, shown = [], set()
    for query, products in found.items():
        shelf = source.get(query) or {}
        for product in products:
            pid = str(product.get("id"))
            if pid in swiped or not product.get("available"):
                continue
            if tastes.known(product.get("name", "")):
                continue  # те, що вже куповане, оцінювати нецікаво
            if tastes._key(product.get("name", "")) in shown:
                continue  # два смаки одного шоколаду — це одна картка, не дві
            shown.add(tastes._key(product.get("name", "")))
            card = to_item(product, query)
            card["product_id"] = pid
            card["shelf"] = shelf.get("title") or query
            card["shelf_weight"] = shelf.get("weight")
            card["on_promo"] = bool(product.get("oldPrice") or product.get("specialPrices"))
            card["why"] = (f"з полиці «{shelf.get('title')}», яку ти любиш (вага "
                           f"{shelf.get('weight')})" if (shelf.get("weight") or 0) > 0
                          else "полиця, яку ти майже не береш — раптом зайде")
            cards.append(card)
    cards.sort(key=lambda c: (not c["on_promo"], -(c.get("shelf_weight") or 0)))
    done(f"{len(cards[:limit])} карток")
    return {"cards": cards[:limit], "already_swiped": len(swiped),
            "shelves": [{"title": s["title"], "weight": s["weight"]} for s in liked_shelves],
            "exploring": [c["title"] for c in cold],
            "proposed": True,
            "spec": ("Колода будується з ваг, які накопичують самі свайпи. Щоб це "
                     "працювало, потрібна памʼять про ВІДМОВИ: «Обране» зберігає "
                     "лише «так», і половина сигналу зникає. " + SPEC_URL)}


def get_swipes(liked: bool | None = None) -> dict:
    """Свайпи гостя. liked=False — те, що показувати більше не варто."""
    done = _traced("silpo_get_swipes", {"liked": liked})
    swipes = _load().get("swipes", {})
    items = [{"product_id": k, **v} for k, v in swipes.items()
             if liked is None or v.get("liked") is liked]
    done(f"{len(items)}")
    return {"count": len(items), "swipes": items, "proposed": True}


# ---------------------------------------------------------------------------
# 7. Активація персональних промо
# ---------------------------------------------------------------------------
async def select_promos(promo_ids: list[int]) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Активувати обрані 1–5 персональних промо.

    `silpo_get_my_promos` віддає десять пропозицій і каже, що активувати можна
    пʼять — але tool на запис немає. Агент рахує найкращу пʼятірку під кошик,
    а натиснути «+» гість мусить руками в застосунку.
    """
    done = _traced("silpo_select_promos", {"promo_ids": promo_ids})
    promos = await silpo.call("silpo_get_my_promos", {})
    meta = promos.get("meta", {})
    limit = int(meta.get("maxSelect") or 5)
    chosen = list(promo_ids)[:limit]
    data = _load()
    data["selected_promos"] = chosen
    _save(data)
    done(f"{len(chosen)} із ліміту {limit}")
    return {"selected": chosen, "limit": limit, "available": meta.get("total"),
            "applied": False,
            "deep_link": "https://link.silpo.ua/promos",
            "note": ("Активацію записано в нас. У «Сільпо» вона поки не передається — "
                     "натисни «+» у застосунку."),
            "proposed": True,
            "spec": ("POST зі списком promoId, ідемпотентний, з валідацією ліміту "
                     "minSelect/maxSelect і терміну дії. " + SPEC_URL)}


# ---------------------------------------------------------------------------
# 8. Холодильник і самопочуття — зовнішні джерела
# ---------------------------------------------------------------------------
def pantry_sync(items: list[dict] | None = None, source: str = "manual") -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Що зараз є вдома.

    Джерело — розумний холодильник, сканування чека або ручний список. Далі
    `pantry_missing` звіряє це зі звичками з чеків і каже, чого бракує.
    """
    done = _traced("silpo_pantry_sync", {"source": source, "count": len(items or [])})
    data = _load()
    data["pantry"] = {"source": source, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "items": items or []}
    _save(data)
    done()
    return {"stored": len(items or []), "source": source, "proposed": True,
            "spec": ("Приймає інвентар кухні (назва, кількість, термін придатності) "
                     "з зовнішнього джерела — холодильника, сканера чеків, ручного "
                     "списку. " + SPEC_URL)}


async def pantry_missing() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Чого немає вдома з того, що гість зазвичай бере."""
    done = _traced("silpo_pantry_missing", {})
    from .facade import _habits, _raw_receipts

    store = _load()
    pantry = store.get("pantry") or {"source": "демо-холодильник", "demo": True,
                                     "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                     "items": _DEMO_PANTRY}
    have = " ".join(str(i.get("name", "")).lower() for i in pantry.get("items", []))
    habits = _habits(await _raw_receipts(10))
    missing = [h for h in habits if h["name"].lower().split()[0][:5] not in have]
    done(f"{len(missing)} із {len(habits)}")
    return {"pantry_source": pantry.get("source"), "pantry_at": pantry.get("at"),
            "demo": bool(pantry.get("demo")), "on_shelf": pantry.get("items", []),
            "missing": [{"name": h["name"], "cycle_days": h["cycle_days"],
                         "days_since": h["days_since"]} for h in missing],
            "proposed": True,
            "spec": ("Звіряє інвентар кухні з історією покупок і повертає перелік "
                     "того, що скінчилось або скінчиться найближчими днями. " + SPEC_URL)}


def wellbeing_sync(source: str, mood: str | None = None, sleep_hours: float | None = None,
                   workout: str | None = None, cycle_phase: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Дані самопочуття із зовнішнього застосунку.

    Джерела — трекер тренувань, Flo, трекер настрою. Це саме той випадок, коли
    MCP «Сільпо» поєднується з чужим MCP: сон 5 годин і силове тренування
    ввечері — різні кошики.
    """
    done = _traced("silpo_wellbeing_sync",
                   {"source": source, "mood": mood, "workout": workout})
    data = _load()
    data["wellbeing"] = {"source": source, "mood": mood, "sleep_hours": sleep_hours,
                         "workout": workout, "cycle_phase": cycle_phase,
                         "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    _save(data)
    hints = []
    if workout:
        hints += ["куряче філе", "йогурт грецький", "банан"]
    if sleep_hours is not None and sleep_hours < 6:
        hints += ["кава мелена", "вода"]
    if cycle_phase in ("лютеїнова", "менструація"):
        hints += ["шоколад чорний", "чай трав'яний", "горіхи"]
    if mood in ("сумно", "тривожно"):
        hints += ["чай", "печиво"]
    done()
    return {"stored": data["wellbeing"], "suggested_queries": hints, "proposed": True,
            "spec": ("Приймає сигнали самопочуття із зовнішнього MCP (фітнес-трекер, "
                     "Flo, трекер настрою) і дозволяє агенту врахувати їх у підборі. "
                     "Дані чутливі: потрібна окрема згода й зберігання на боці гостя. "
                     + SPEC_URL)}


def wellbeing_state() -> dict:
    """Останній стан самопочуття, який синхронізували (або демо-дані)."""
    data = _load()
    return {"wellbeing": data.get("wellbeing") or {**_DEMO_WELLBEING, "demo": True},
            "pantry": data.get("pantry") or {"source": "демо-холодильник", "demo": True,
                                             "items": _DEMO_PANTRY},
            "proposed": True}


# ---------------------------------------------------------------------------
# 9. Демо-дані: конектори до зовнішніх застосунків
# ---------------------------------------------------------------------------
# Поки немає справжніх інтеграцій, тримаємо правдоподібні дані з позначкою
# demo=true. Без них сценарії «сімʼя», «холодильник» і «самопочуття» показувати
# нема на чому — а саме вони найкраще пояснюють, навіщо MCP потрібні сусіди.
CONNECTORS = [
    {"id": "samsung_fridge", "name": "Samsung Family Hub", "kind": "холодильник",
     "gives": "інвентар полиць і терміни придатності", "icon": "fridge"},
    {"id": "flo", "name": "Flo", "kind": "жіноче здоровʼя",
     "gives": "фаза циклу, самопочуття", "icon": "flower"},
    {"id": "google_fit", "name": "Google Fit", "kind": "активність",
     "gives": "тренування, кроки, сон", "icon": "heartbeat"},
    {"id": "daylio", "name": "Daylio", "kind": "настрій",
     "gives": "щоденні позначки настрою", "icon": "spark"},
    {"id": "google_calendar", "name": "Google Календар", "kind": "плани",
     "gives": "події, гості, дні народження", "icon": "calendar"},
]

_DEMO_FAMILY = {
    "дитина": {"likes": ["піца", "кола", "морозиво", "чипси"],
               "avoid": ["броколі", "печінка"], "allergies": []},
    "дорослий": {"likes": ["суші", "вино червоне", "сир з пліснявою"],
                 "avoid": ["гостре"], "allergies": ["арахіс"]},
    "я": {"likes": ["паста", "кава", "стейк"], "avoid": ["гриби"], "allergies": ["горіхи"]},
}

_DEMO_PANTRY = [
    {"name": "Молоко «Галичина» 2,5%", "qty": 1, "expires": "2026-09-05"},
    {"name": "Яйця курячі С1", "qty": 4, "expires": "2026-09-18"},
    {"name": "Масло вершкове", "qty": 1, "expires": "2026-09-30"},
    {"name": "Кетчуп", "qty": 1, "expires": "2027-01-12"},
    {"name": "Гірчиця", "qty": 1, "expires": "2027-03-02"},
]

_DEMO_WELLBEING = {"source": "Google Fit + Daylio", "mood": "втомлено",
                   "sleep_hours": 5.5, "workout": "силове", "cycle_phase": None,
                   "steps": 11420}


def connectors() -> dict:
    """Зовнішні застосунки, з яких агент може брати контекст.

    Це і є відповідь на питання «навіщо MCP, якщо є застосунок «Сільпо»»:
    магазин не знає, що ти не спав і щойно з залу, а трекер не знає, що
    в тебе алергія на горіхи. Зшиває їх агент.
    """
    done = _traced("silpo_list_connectors", {})
    state = _load().get("connectors", {})
    done()
    return {"connectors": [{**c, "connected": bool(state.get(c["id"]))}
                           for c in CONNECTORS], "proposed": True,
            "spec": ("Кожен конектор — окремий MCP-сервер збоку застосунку-джерела. "
                     "«Сільпо» не має їх реалізовувати: достатньо, щоб агент міг "
                     "тримати кілька MCP одночасно. " + SPEC_URL)}


def connect(source: str, on: bool = True) -> dict:
    """Увімкнути демо-конектор і засіяти правдоподібні дані."""
    done = _traced("silpo_connect_source", {"source": source, "on": on})
    data = _load()
    state = data.setdefault("connectors", {})
    state[source] = bool(on)
    if on and source == "samsung_fridge":
        data["pantry"] = {"source": "Samsung Family Hub", "demo": True,
                          "at": time.strftime("%Y-%m-%d %H:%M:%S"), "items": _DEMO_PANTRY}
    if on and source in ("google_fit", "daylio", "flo"):
        wb = dict(data.get("wellbeing") or {})
        wb.update(_DEMO_WELLBEING, demo=True, at=time.strftime("%Y-%m-%d %H:%M:%S"))
        if source == "flo":
            wb["cycle_phase"] = "лютеїнова"
        data["wellbeing"] = wb
    _save(data)
    done("демо-дані засіяно" if on else "вимкнено")
    return {"source": source, "connected": bool(on), "demo": True, "proposed": True}


def seed_family_demo() -> dict:
    """Заповнює вподобання членів родини демо-даними — щоб сценарій було видно."""
    done = _traced("silpo_seed_family_demo", {})
    data = _load()
    prefs = data.setdefault("family_prefs", {})
    prefs.update({"__demo__": True})
    _save(data)
    done()
    return {"seeded": True, "note": "Вподобання підставляються за роллю учасника.",
            "proposed": True}


def _demo_prefs_for(role: str) -> dict:
    return dict(_DEMO_FAMILY.get(role, _DEMO_FAMILY["дорослий"]))


# ---------------------------------------------------------------------------
# 10. Маршрут по залу
# ---------------------------------------------------------------------------
# Розділи — СПРАВЖНІ, з silpo_get_categories_tree, у порядку, який віддає сам
# «Сільпо» (перевірено 2 вересня 2026). Чого бракує — прив'язки товару до
# категорії: у відповіді про товар немає жодного поля з категорією, навіть коли
# товар щойно дістали ЗАПИТОМ ПО КАТЕГОРІЇ. Тому відділ доводиться вгадувати
# за назвою, і саме це має полагодити `categoryId` у картці товару.
SILPO_CATEGORIES = [
    ("frukty-ovochi-4788", "Фрукти, овочі",
     ["яблук", "банан", "виноград", "морква", "картопл", "цибул", "салат", "зелен",
      "помідор", "огірк", "авокадо", "лимон", "ягод", "гарбуз", "буряк", "капуст", "часник",
      "баклажан", "батат", "перець", "кабач", "редис", "селер", "імбир", "груш", "слив",
      "персик", "нектарин", "черешн", "диня", "кавун", "ківі", "мандарин", "апельсин", "томат",
      "печериц", "гриб", "кріп", "петрушк", "базилік", "руккол", "шпинат", "броколі",
      "спарж", "кукурудза", "хурма", "гранат", "манго", "ананас"]),
    ("m-iaso-4411", "М'ясо",
     ["філе", "стейк", "фарш", "курк", "свинин", "яловичин", "індич"]),
    ("ryba-4430", "Риба",
     ["риб", "лосос", "тунець", "оселед", "креветк", "форел", "морепродукт", "норі"]),
    ("kovbasni-vyroby-i-m-iasni-delikatesy-4731", "Ковбаси і м'ясні делікатеси",
     ["ковбас", "бекон", "салямі", "кабанос", "шинк", "сосиск", "паштет", "підчеревин", "балик"]),
    ("syry-1468", "Сири",
     ["сир", "пармезан", "камамбер", "моцарел", "брі", "фета"]),
    ("khlib-ta-vypichka-5121", "Хліб та випічка",
     ["хліб", "багет", "лаваш", "булоч", "плетінк", "завиванец", "пампух", "ріжок",
      "тортилья", "сухар", "круасан", "чіабат", "фокач", "коржі", "батон", "паляниц",
      "штрудель", "ромова баба", "тісто", "піта"]),
    ("gotovi-stravy-i-kulinariia-4761", "Готові страви і кулінарія",
     ["готова", "олів'є", "суші сет"]),
    ("molochni-produkty-ta-iaitsia-234", "Молочні продукти та яйця",
     ["молок", "сметан", "йогурт", "кефір", "ряжан", "масло вершк", "вершк", "яйц",
      "сир кисломолочн", "творог"]),
    ("zdorove-kharchuvannia-4864", "Здорове харчування",
     ["гранол", "пластівц", "протеїн", "сніданок", "мюслі", "хлібц", "батончик злаков"]),
    ("bakaliia-i-konservy-4870", "Бакалія і консерви",
     ["рис", "гречк", "макарон", "спагет", "борошн", "цукор", "олі", "консерв",
      "квасол", "мед", "желатин", "вермішель", "локшин", "паста", "крупа", "пшон",
      "сочевиц", "булгур", "кус-кус", "горох", "оцет", "сухофрукт", "рамен"]),
    ("sousy-i-spetsii-4938", "Соуси і спеції",
     ["соус", "кетчуп", "майонез", "гірчиц", "спеці", "паприк", "приправ", "сіль"]),
    ("solodoshchi-498", "Солодощі",
     ["шоколад", "цукерк", "печив", "вафл", "торт", "десерт", "батончик", "roshen",
      "карамель", "донат", "пончик", "мармелад", "зефір", "халва", "джем", "варення",
      "рулет", "маршмеллоу", "нуга", "пастил", "кекс", "мафін", "тістечк"]),
    ("sneky-ta-chypsy-5016", "Снеки та чипси",
     ["чипси", "снек", "попкорн", "сухарик", "крекер", "грінк", "фісташк", "арахіс",
      "горіх", "мигдал", "кешʼю", "кеш'ю", "насінн", "паличк кукурудзян", "начос"]),
    ("kava-chai-359", "Кава, чай", ["кава", "чай"]),
    ("napoi-52", "Напої", ["вод", "сік", "кола", "напій", "нектар", "лимонад",
                            "морс", "квас", "смузі", "енергетик", "тонік"]),
    ("zamorozhena-produktsiia-264", "Заморожена продукція",
     ["заморож", "пельмен", "варен", "морозиво", "піца", "нагетс", "картопля фрі",
      "млинц", "хінкал", "чебурек"]),
    ("alkogol-22", "Алкоголь",
     ["вино", "пиво", "горілк", "віскі", "лікер", "шампан", "просекко", "ігрист"]),
    ("dytiachi-tovary-449", "Дитячі товари", ["підгуз", "дитяч"]),
    ("gigiiena-ta-krasa-4519", "Гігієна та краса",
     ["мило", "шампун", "гель для", "паста зубн", "дезодорант", "крем для", "бальзам",
      "лосьйон", "зубн", "прокладк", "пінка", "маска для"]),
    ("dlia-domu-567", "Для дому",
     ["пакет", "рушник", "серветк", "порошок", "губк", "освіжувач", "дошок", "дошка",
      "контейнер", "фольг", "плівк", "свічк", "батарейк", "лампа", "мішк", "н-р "]),
    ("dlia-tvaryn-653", "Для тварин", ["корм", "котів", "собак", "наповнювач"]),
]

# Порядок перевірки ≠ порядок обходу: «Пакет Сільпо» містить «сіль», а
# «сир кисломолочний» — «сир». Вужчі категорії дивимось першими.
_MATCH_FIRST = ("dlia-domu-567", "dlia-tvaryn-653", "dytiachi-tovary-449",
                "zamorozhena-produktsiia-264", "alkogol-22", "napoi-52",
                "gigiiena-ta-krasa-4519", "syry-1468")

# «Сир» — це і полиця сирів, і кисломолочний сир із молочного відділу.
_EXCLUDE = {
    "syry-1468": ["кисломолочн", "сирок", "сироват", "сирник", "творож", "плавлен"],
    "napoi-52": ["вода мінеральна для", "водка"],
}


def _aisle_of(name: str) -> tuple[str, str]:
    """Відділ за назвою товару. Два правила, обидва — з розбору назв «Сільпо».

    Перше: тип товару в назві стоїть ПЕРШИМ («Чипси Люкс зі смаком сметани та
    зелені»), тож спершу дивимось лише на початок назви, і аж потім на решту.
    Без цього чипси зі смаком зелені їдуть у «Фрукти, овочі».

    Друге: серед збігів виграє найдовше слово. «Сухарики» — це і «сухар»
    (хліб), і «сухарик» (снеки); довше слово точніше.
    """
    low = (name or "").lower()
    head = " ".join(low.split()[:2])
    ordered = ([c for c in SILPO_CATEGORIES if c[0] in _MATCH_FIRST]
               + [c for c in SILPO_CATEGORIES if c[0] not in _MATCH_FIRST])
    for scope in (head, low):
        best = None
        for slug, title, words in ordered:
            if any(x in low for x in _EXCLUDE.get(slug, ())):
                continue
            hit = max((w for w in words if w in scope), key=len, default=None)
            if hit and (best is None or len(hit) > best[0]):
                best = (len(hit), slug, title)
        if best:
            return best[1], best[2]
    return "inshe", "Інше"


def store_route(items: list[dict], branch_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Порядок обходу залу під конкретний кошик.

    Розділи справжні — з `silpo_get_categories_tree`, у порядку самого «Сільпо».
    Прив'язку товару до розділу доводиться вгадувати за назвою: у відповіді про
    товар немає категорії навіть тоді, коли товар дістали запитом по категорії.

    Порядок відділів у конкретному магазині свій, тож його можна переставити —
    і ми запамʼятаємо його для цього branchId.
    """
    done = _traced("silpo_get_store_layout", {"branchId": branch_id,
                                              "items": len(items or [])})
    data = _load()
    saved = (data.get("layouts") or {}).get(branch_id or "default")
    default_order = [c[0] for c in SILPO_CATEGORIES] + ["inshe"]
    order = saved or default_order

    titles = {c[0]: c[1] for c in SILPO_CATEGORIES}
    titles["inshe"] = "Інше"
    grouped: dict[str, list] = {}
    guessed = 0
    for item in items or []:
        slug, _ = _aisle_of(item.get("name", ""))
        grouped.setdefault(slug, []).append(item.get("name"))
        guessed += 1
    route = [{"slug": slug, "aisle": titles.get(slug, slug), "items": grouped[slug]}
             for slug in order if slug in grouped]
    done(f"{len(route)} відділів")
    return {
        "branch_id": branch_id, "custom_order": bool(saved),
        "route": route, "steps": len(route),
        "categories_source": "silpo_get_categories_tree · 28 розділів",
        "guessed_by_name": guessed,
        "proposed": True,
        "spec": ("Каталог-дерево «Сільпо» вже віддає 28 розділів у своєму порядку — "
                 "цього достатньо для маршруту. Бракує одного поля: categoryId у "
                 "картці товару. Зараз його немає навіть у відповіді на запит ПО "
                 "КАТЕГОРІЇ, тож відділ доводиться вгадувати за назвою. "
                 "Друга частина — порядок відділів у конкретному магазині: "
                 "планування різне, і його знає лише сам магазин. " + SPEC_URL),
    }


def save_store_route(branch_id: str, order: list[str]) -> dict:
    """Запамʼятати порядок відділів для цього магазину.

    Планування різне, і ніхто, крім самого магазину, його не знає. Тож даємо
    гостю переставити один раз — і більше не питаємо.
    """
    done = _traced("silpo_save_store_layout", {"branchId": branch_id})
    data = _load()
    data.setdefault("layouts", {})[branch_id or "default"] = order
    _save(data)
    done()
    return {"branch_id": branch_id, "order": order, "proposed": True}


# ---------------------------------------------------------------------------
# 11. Спадкова кухня — сімейні рецепти
# ---------------------------------------------------------------------------
def add_family_recipe(title: str, items: list[str], steps: list[str],
                      author: str = "", meal: str = "вечеря",
                      equipment: list[str] | None = None, note: str = "") -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Сімейний рецепт, який стає паком для будь-кого з рідних.

    Бабусин борщ живе в зошиті або в голові. Тут він стає структурою, яку агент
    перетворює на кошик — з поправкою на чиїсь алергії.
    """
    done = _traced("silpo_add_family_recipe", {"title": title})
    data = _load()
    book = data.setdefault("family_recipes", [])
    recipe = {"id": f"fam-{len(book)+1}", "title": title, "author": author,
              "meal": meal, "items": items, "steps": steps,
              "equipment": equipment or [], "note": note,
              "serves": 4, "minutes": 60,
              "added_at": time.strftime("%Y-%m-%d")}
    book.append(recipe)
    _save(data)
    done()
    return {"recipe": recipe, "total": len(book), "proposed": True,
            "spec": ("Спільна книга рецептів у межах «Сімейного доступу»: хто завгодно "
                     "з родини додає, будь-хто перетворює на кошик. " + SPEC_URL)}


def family_recipes() -> dict:
    """Сімейні рецепти. Якщо порожньо — засіваємо один, щоб сценарій було видно."""
    done = _traced("silpo_get_family_recipes", {})
    data = _load()
    book = data.get("family_recipes")
    if not book:
        book = [{"id": "fam-1", "title": "Бабусин борщ", "author": "Бабуся Ніна",
                 "meal": "обід", "serves": 6, "minutes": 120,
                 "equipment": ["каструля"],
                 "items": ["буряк", "капуста", "картопля", "морква", "цибуля",
                           "томатна паста", "яловичина", "сметана"],
                 "steps": ["Звари бульйон на яловичині — не менше години.",
                           "Буряк туши окремо з томатною пастою і ложкою оцту.",
                           "Картоплю й капусту — у бульйон, за 10 хвилин додай засмажку.",
                           "Дай настоятись годину. Подавай зі сметаною."],
                 "note": "Оцет — щоб борщ лишився червоним.",
                 "added_at": "2026-09-02", "demo": True}]
        data["family_recipes"] = book
        _save(data)
    done(f"{len(book)}")
    return {"count": len(book), "recipes": book, "proposed": True}


# ---------------------------------------------------------------------------
# 12. Рецепт із інтернету — коли своєї бази не вистачило
# ---------------------------------------------------------------------------
async def find_recipe_online(query: str, limit: int = 4) -> dict:
    """Пошук рецепта в інтернеті, коли ні база, ні MCP нічого не дали.

    Повільніше за локальну базу, зате сценарій не падає на «нічого не знайшов».
    Складники витягуємо з тексту сторінки простим розбором і чесно кажемо, що
    це здогадка — гість бачить джерело й може відкрити оригінал.
    """
    done = _traced("silpo_find_recipes_online", {"query": query})
    import re
    import httpx2
    try:
        async with httpx2.AsyncClient(timeout=15, follow_redirects=True,
                                      headers={"User-Agent": "Mozilla/5.0"}) as http:
            page = await http.get("https://html.duckduckgo.com/html/",
                                  params={"q": f"{query} рецепт склад інгредієнти"})
            html = page.text
    except Exception as exc:
        done(f"недоступно: {type(exc).__name__}")
        return {"query": query, "results": [], "proposed": True,
                "error": f"Пошук в інтернеті недоступний ({type(exc).__name__})."}

    results = []
    for match in re.finditer(
            r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        url, title = match.group(1), re.sub(r"<[^>]+>", "", match.group(2)).strip()
        if not title:
            continue
        results.append({"title": title, "url": url})
        if len(results) >= limit:
            break

    # грубий добір складників зі сніпетів — щоб було що подати у find_products_batch
    text = re.sub(r"<[^>]+>", " ", html)
    words = re.findall(r"[А-ЯІЇЄҐа-яіїєґ]{4,}", text)
    stop = {"рецепт", "приготування", "страва", "хвилин", "порці", "смачн", "домашн"}
    counts: dict[str, int] = {}
    for w in words:
        low = w.lower()
        if any(low.startswith(s) for s in stop):
            continue
        counts[low] = counts.get(low, 0) + 1
    guessed = [w for w, _ in sorted(counts.items(), key=lambda kv: -kv[1])[:8]]

    done(f"{len(results)} джерел")
    return {"query": query, "results": results, "guessed_items": guessed,
            "source": "web", "confidence": "низька", "proposed": True,
            "note": ("Складники вгадані з тексту сторінок. Відкрий джерело й перевір — "
                     "або попроси модель скласти перелік точніше."),
            "spec": ("Показує, чого бракує: якби «Сільпо» віддавало рецепти з "
                     "артикулами, цей обхідний шлях був би не потрібен. " + SPEC_URL)}
