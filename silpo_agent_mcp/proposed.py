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
    """Повертає функцію завершення сліду: `done(note, result)`.

    `result` — це те, що побачить людина в картці виклику. Без нього слід
    запропонованого tool показував «Відповідь: порожньо», і на демо було
    неможливо відповісти на просте питання «а звідки взялись ці смаки?».
    Повертає той самий `result`, щоб писати `return done(note, result)`.
    """
    started = time.perf_counter()

    def done(note: str = "", result=None):
        silpo.log_proposed(name, args, started, note=note, result=result)
        return result
    return done


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
    {"id": "pasta-losos", "title": "Паста з лососем у вершках", "meal": "вечеря",
     "minutes": 25, "equipment": ["каструля", "сковорідка"], "serves": 4,
     # «сир твердий», а не пармезан: у філії пармезан — це головка за 1 499 ₴
     # і попкорн «зі смаком», а лосось без «філе» приносить хребти.
     "items": ["спагеті", "лосось філе", "вершки", "сир твердий", "часник", "масло вершкове"],
     "steps": ["Відвари спагеті до аль денте.",
               "Обсмаж лосось шматочками з часником на маслі 4 хвилини.",
               "Влий вершки, прогрій, змішай із пастою, зверху — тертий пармезан."]},
    # Дві страви нижче існують, щоб їх ВІДХИЛИЛИ: песто — через горіхи, пад тай —
    # через арахіс. Відмова з іменем того, чия алергія, — половина сенсу сценарію.
    {"id": "pasta-pesto", "title": "Паста з песто", "meal": "вечеря", "minutes": 15,
     "equipment": ["каструля"], "serves": 4,
     "items": ["спагеті", "базилік", "кедрові горіхи", "сир пармезан", "олія оливкова"],
     "steps": ["Відвари спагеті.", "Збий базилік, горіхи, пармезан і олію в соус.",
               "Змішай із гарячою пастою."]},
    {"id": "pad-thai", "title": "Пад тай із креветками", "meal": "вечеря", "minutes": 30,
     "equipment": ["сковорідка"], "serves": 2,
     "items": ["локшина рисова", "креветки", "яйця", "арахіс", "соєвий соус", "лайм"],
     "steps": ["Замочи локшину.", "Обсмаж креветки з яйцем.",
               "Додай локшину й соус, посип арахісом."]},
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
    found, rejected = [], []
    for recipe in RECIPES + _load().get("family_recipes", []):
        if meal and recipe["meal"] != meal.lower().strip():
            continue
        if query and query.lower() not in recipe["title"].lower() \
                and not any(query.lower() in i for i in recipe["items"]):
            continue
        if recipe["equipment"] and not any(e in have for e in recipe["equipment"]):
            rejected.append({"title": recipe["title"], "reason": "обладнання",
                             "detail": "потрібно: " + ", ".join(recipe["equipment"])})
            continue
        # Відхилену через алергію страву називаємо разом зі складником і
        # словом, на якому спрацювало: мовчазне зникнення рецепта з видачі
        # нічим не відрізняється від «такого рецепта немає».
        hit = next(((i, _blocked_by(i, terms)) for i in recipe["items"]
                    if _blocked_by(i, terms)), None)
        if hit:
            rejected.append({"title": recipe["title"], "reason": "алергія",
                             "item": hit[0], "term": hit[1]})
            continue
        if serves and recipe["serves"] < serves:
            continue
        found.append(recipe)
    done(f"{len(found)} рецептів, {len(rejected)} відхилено",
         {"count": len(found), "recipes": [r["title"] for r in found[:limit]],
          "rejected": rejected})
    return {"count": len(found), "recipes": found[:limit], "rejected": rejected,
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
def _delivery_label(code: str) -> str:
    from .facade import delivery_label
    return delivery_label(code)


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
                # Українська назва разом із кодом: у відповіді API способи
                # отримання англійські й гостю не кажуть нічого.
                "label": _delivery_label(slot_type),
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
# Родину читаємо один раз на сценарій. Картка «хто вечеряє» й сам підбір
# ідуть один за одним, і другий виклик того самого API просто дублював
# перший у панелі «Що відбувається». Кеш скидає будь-яка правка вподобань.
_FAMILY_CACHE: dict = {"at": 0.0, "value": None}
FAMILY_CACHE_TTL = 300

PET_KINDS = {"cats": "кіт", "dogs": "пес", "birds": "птах", "fish": "рибка",
             "rodents": "гризун"}


async def get_family_preferences(fresh: bool = False) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Смаки та алергії кожного члена родини.

    `silpo_get_my_family` віддає склад родини — імена, вік дітей, тварин. Але
    «Простір вподобань» із зонами «Гастро-зупинка», «Дитяча зона» та «Зоосвіт»
    у MCP не представлений, тож підібрати вечерю на всіх неможливо.

    Тут реальний склад родини доповнюється тим, що гість вказав у нашому
    застосунку — і одразу видно, чиїх даних бракує.
    """
    cached = _FAMILY_CACHE["value"]
    if cached and not fresh and time.time() - _FAMILY_CACHE["at"] < FAMILY_CACHE_TTL:
        return cached
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
            "source": PREFS_SOURCE_GUEST if known else PREFS_SOURCE_DEMO,
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
            "source": PREFS_SOURCE_GUEST if known else PREFS_SOURCE_DEMO,
        })
    pets = [{"id": p.get("id"), "name": p.get("name"), "slug": p.get("slug"),
             "kind": PET_KINDS.get(p.get("slug"), p.get("slug"))}
            for p in family.get("pets", [])]

    result = done(f'{len(members)} людей, {len(pets)} тварин', {
        "members": members, "pets": pets,
        "missing_preferences": [m["name"] for m in members if not m["known"]],
        # Дві різні речі під одним дахом, і в сліді це має бути видно:
        # склад — з API, смаки — з нашого сховища, куди їх записав гість.
        "sources": {"members": "silpo_get_my_family — склад родини з акаунта «Сільпо»",
                    "preferences": "наш шар: .mcp/proposed.json → family_prefs, "
                                   "заповнюється гостем у Профіль → Моя сімʼя → заповнити"},
        "proposed": True,
        "spec": ("Має віддавати для кожного члена родини його «Простір вподобань»: "
                 "улюблені категорії, харчові обмеження та алергії. Сьогодні "
                 "get_my_family дає лише склад родини — смаки лишаються в застосунку "
                 "і не доступні агенту. " + SPEC_URL),
    })
    _FAMILY_CACHE.update({"at": time.time(), "value": result})
    return result


def set_member_preferences(member_id: str, likes: list[str] | None = None,
                           avoid: list[str] | None = None,
                           allergies: list[str] | None = None,
                           name: str | None = None) -> dict:
    """Зберігає вподобання члена родини чи гостя компанії (наш бік).

    `name` тут не примха: `get_my_family` віддає імʼя лише для тих, хто сам
    його заповнив, — у нашому акаунті другий дорослий приходить із
    `"name": null`. Підпис «без імені» перетворює пояснення «без арахісу, бо
    NN» на беззмістовне, тож імʼя для своїх гість дає в нас.
    """
    done = _traced("silpo_set_member_preferences", {"member_id": member_id})
    data = _load()
    prefs = data.setdefault("family_prefs", {})
    entry = prefs.setdefault(member_id, {"likes": [], "avoid": [], "allergies": []})
    for field, value in (("likes", likes), ("avoid", avoid),
                         ("allergies", allergies), ("name", name)):
        if value is not None:
            entry[field] = value
    _save(data)
    _FAMILY_CACHE["value"] = None    # наступне читання піде в API
    return done("записано", {"member_id": member_id, "preferences": entry, "proposed": True})


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
async def select_promos(promo_ids: list[int], limit: dict | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Активувати обрані 1–5 персональних промо.

    `silpo_get_my_promos` віддає десять пропозицій і каже, що активувати можна
    пʼять — але tool на запис немає. Агент рахує найкращу пʼятірку під кошик,
    а натиснути «+» гість мусить руками в застосунку.

    Args:
        promo_ids: які промо активувати.
        limit: `meta` з уже прочитаних промо (minSelect/maxSelect/total) —
            щоб не читати список удруге в тому самому сценарії.
    """
    done = _traced("silpo_select_promos", {"promo_ids": promo_ids})
    meta = dict(limit) if limit else (await silpo.call("silpo_get_my_promos", {})).get("meta", {})
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


def pantry_state() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Що ЗАРАЗ лежить на полиці.

    `pantry_missing` каже, чого бракує, — а побачити сам інвентар не було де.
    Виходило дивно: трекер звітує «5 позицій», а які саме, гість не знає.
    Тут повний список із термінами й позначкою, що вже прострочене.
    """
    done = _traced("silpo_pantry_state", {})
    pantry = _load().get("pantry") or {}
    items = pantry.get("items") or []
    today = time.strftime("%Y-%m-%d")
    rows = sorted(
        ({**i, "expired": bool(i.get("expires") and i["expires"] < today)}
         for i in items),
        key=lambda i: i.get("expires") or "9999")
    done(f"{len(rows)} позицій")
    return {"items": rows, "count": len(rows), "expired": sum(1 for i in rows if i["expired"]),
            "source": pantry.get("source"), "at": pantry.get("at"), "proposed": True,
            "spec": ("Інвентар кухні: що лежить і до якої дати. Джерела такого в "
                     "«Сільпо» немає взагалі — магазин не знає, що вже вдома. " + SPEC_URL)}


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
    hints = [h["query"] for h in wellbeing_hints(data["wellbeing"])]
    return done(f"{len(hints)} підказок", {
        "stored": data["wellbeing"], "suggested_queries": hints,
        "hints": wellbeing_hints(data["wellbeing"]), "proposed": True,
        "spec": ("Приймає сигнали самопочуття із зовнішнього MCP (фітнес-трекер, "
                 "Flo, трекер настрою) і дозволяє агенту врахувати їх у підборі. "
                 "Дані чутливі: потрібна окрема згода й зберігання на боці гостя. "
                 + SPEC_URL)})


# Що саме трекер додає в кошик. Розрахунок живе ОКРЕМО від `wellbeing_sync`,
# бо той самий висновок потрібен сценаріям, які читають уже накопичений стан:
# доки він сидів усередині синхронізації, дані трекера впливали на підбір лише
# в ту мить, коли їх щойно прислали, — а через годину ніби й не існували.
#
# Кожна підказка несе сигнал, який її спричинив. «Куряче філе» без підпису —
# це просто курка в кошику; «куряче філе, бо силове тренування» — причина,
# яку гість може перевірити у власному трекері й скасувати, якщо не згоден.
def wellbeing_hints(state: dict | None) -> list[dict]:
    """Позиції, які додає самопочуття, разом із сигналом-причиною."""
    state = state or {}
    out: list[dict] = []

    def add(queries: list[str], why: str) -> None:
        out.extend({"query": q, "why": why} for q in queries)

    if state.get("workout"):
        # Горіхи тут не випадкові: це стандартна порада після силового — і
        # рівно те, що знімає алергія. Трекер про неї не знає, тож саме на
        # цьому місці видно, хто кому підпорядкований.
        add(["куряче філе", "йогурт грецький", "банан", "горіхи волоські"],
            f"тренування: {state['workout']}")
    if state.get("sleep_hours") is not None and state["sleep_hours"] < 6:
        add(["кава мелена", "вода"], f"сон {state['sleep_hours']} год")
    if state.get("cycle_phase") in ("лютеїнова", "менструація"):
        add(["шоколад чорний", "чай трав'яний"], f"фаза циклу: {state['cycle_phase']}")
    if state.get("mood") in ("сумно", "тривожно", "втомлено"):
        add(["чай"], f"настрій: {state['mood']}")
    return out


def wellbeing_state() -> dict:
    """Останній стан самопочуття, який синхронізували (або демо-дані).

    Трасується як окремий виклик: сценарій «Вечеря на всю сімʼю» читає
    трекери саме звідси, і без сліду в панелі «Що відбувається» їх ніби
    не було — хоча пак на них спирається.
    """
    done = _traced("silpo_wellbeing_state", {})
    data = _load()
    wellbeing = data.get("wellbeing") or {**_DEMO_WELLBEING, "demo": True}
    hints = wellbeing_hints(wellbeing)
    summary = ", ".join(part for part in (
        wellbeing.get("source"),
        f'тренування: {wellbeing["workout"]}' if wellbeing.get("workout") else None,
        f'сон {wellbeing["sleep_hours"]} год' if wellbeing.get("sleep_hours") else None,
    ) if part)
    return done(summary or "трекери не підключені", {
        "wellbeing": wellbeing,
        "hints": hints,
        "suggested_queries": [h["query"] for h in hints],
        "pantry": data.get("pantry") or {"source": "демо-холодильник", "demo": True,
                                         "items": _DEMO_PANTRY},
        "source": "наш шар: .mcp/proposed.json → wellbeing; у живому продукті — MCP трекера",
        "proposed": True})


# ---------------------------------------------------------------------------
# 9. Демо-дані: конектори до зовнішніх застосунків
# ---------------------------------------------------------------------------
# Поки немає справжніх інтеграцій, тримаємо правдоподібні дані з позначкою
# demo=true. Без них сценарії «сімʼя», «холодильник» і «самопочуття» показувати
# нема на чому — а саме вони найкраще пояснюють, навіщо MCP потрібні сусіди.
# `fields` — це і є відповідь на «які саме дані називаються трекерами».
# Кожне поле названо, показано, звідки воно й у якому сценарії застосовується.
# Ховати це в одному рядку «тренування, кроки, сон» нечесно: людина віддає
# доступ до сну й циклу, тож має бачити рівно те, що ми з цього читаємо.
CONNECTORS = [
    {"id": "samsung_fridge", "name": "Samsung Family Hub", "kind": "холодильник",
     "gives": "інвентар полиць і терміни придатності", "icon": "fridge",
     "fields": [
         {"key": "pantry.count", "title": "позицій на полиці", "used": True,
          "used_by": "Що зникло з холодильника · Тижневий закуп сам"},
         # Термін придатності холодильник віддає, але жоден наш сценарій його
         # ще не читає: `pantry_missing` дивиться лише на перелік позицій.
         # Написати сюди «Не забудь» було б обіцянкою, якої код не виконує.
         {"key": "pantry.soonest", "title": "найближчий термін придатності", "used": False,
          "used_by": None},
     ]},
    {"id": "flo", "name": "Flo", "kind": "жіноче здоровʼя",
     "gives": "фаза циклу", "icon": "flower",
     "fields": [
         {"key": "wellbeing.cycle_phase", "title": "фаза циклу", "used": True,
          "used_by": "Після тренування"},
     ]},
    {"id": "google_fit", "name": "Google Fit", "kind": "активність",
     "gives": "тренування, кроки, сон", "icon": "heartbeat",
     "fields": [
         {"key": "wellbeing.sleep_hours", "title": "годин сну", "used": True,
          "used_by": "Після тренування"},
         {"key": "wellbeing.workout", "title": "останнє тренування", "used": True,
          "used_by": "Після тренування"},
         {"key": "wellbeing.steps", "title": "кроків за день", "used": True,
          "used_by": "Після тренування"},
     ]},
    {"id": "daylio", "name": "Daylio", "kind": "настрій",
     "gives": "щоденні позначки настрою", "icon": "spark",
     "fields": [
         {"key": "wellbeing.mood", "title": "настрій", "used": True,
          "used_by": "Настрій із твоїх даних"},
     ]},
    {"id": "google_calendar", "name": "Google Календар", "kind": "плани",
     "gives": "події, гості, дні народження", "icon": "calendar",
     "fields": [
         # Календар підключається, але жоден сценарій його ще не читає — і
         # перемикач для нього нічого не засіває. Лишаємо видимим саме тому:
         # список полів має показувати й те, що ЩЕ не працює.
         {"key": "calendar.events", "title": "найближчі події", "used": False,
          "used_by": None},
     ]},
]

# Підпис джерела вподобань у відповіді get_family_preferences. Гість має
# бачити різницю між «я це заповнив» і «агент підставив за роллю».
PREFS_SOURCE_GUEST = "профіль гостя (Профіль → Моя сімʼя)"
PREFS_SOURCE_DEMO = "демо за роллю — гість ще не заповнив"

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


def _tracker_value(key: str, data: dict):
    """Поточне значення поля трекера — рівно те, що агент справді прочитає."""
    pantry = data.get("pantry") or {}
    items = pantry.get("items") or []
    wb = data.get("wellbeing") or {}
    if key == "pantry.count":
        return f"{len(items)} позицій" if items else None
    if key == "pantry.soonest":
        dates = sorted(i.get("expires") for i in items if i.get("expires"))
        if not dates:
            return None
        soonest = next((i for i in items if i.get("expires") == dates[0]), {})
        return f'{soonest.get("name", "?")} до {dates[0]}'
    if key.startswith("wellbeing."):
        value = wb.get(key.split(".", 1)[1])
        if value in (None, ""):
            return None
        return {"sleep_hours": f"{value} год", "steps": f"{value} кроків"}.get(
            key.split(".", 1)[1], str(value))
    return None


def connectors() -> dict:
    """Зовнішні застосунки, з яких агент може брати контекст.

    Це і є відповідь на питання «навіщо MCP, якщо є застосунок «Сільпо»»:
    магазин не знає, що ти не спав і щойно з залу, а трекер не знає, що
    в тебе алергія на горіхи. Зшиває їх агент.

    Разом зі списком джерел віддаємо ПОІМЕННО кожне поле, яке агент із них
    читає, і його поточне значення. Інакше «трекери» — це слово, під яким
    може ховатись будь-що: людина віддає доступ до сну й циклу, тож має
    бачити рівно те, що з цього береться.
    """
    done = _traced("silpo_list_connectors", {})
    data = _load()
    state = data.get("connectors", {})

    rows, live, used = [], 0, 0
    for c in CONNECTORS:
        on = bool(state.get(c["id"]))
        fields = []
        for f in c.get("fields") or []:
            value = _tracker_value(f["key"], data) if on else None
            if value is not None:
                live += 1
            if f.get("used"):
                used += 1
            fields.append({**f, "value": value})
        rows.append({**c, "connected": on, "fields": fields})

    total = sum(len(c.get("fields") or []) for c in CONNECTORS)
    return done(f"{sum(1 for r in rows if r['connected'])} підключено, "
                f"{live}/{total} полів із даними, {used} читаються сценаріями", {
        "connectors": rows, "proposed": True,
        "fields_total": total, "fields_live": live, "fields_used": used,
        "demo": True,
        "why": ("«Трекери» — це не абстракція: нижче названо кожне поле, яке агент "
                "читає, його поточне значення і сценарій, який його вживає. "
                "Поля, які жоден сценарій ще не читає, підписані окремо — "
                "показувати їх як робочі було б обіцянкою, якої код не виконує."),
        "spec": ("Кожен конектор — окремий MCP-сервер збоку застосунку-джерела. "
                 "«Сільпо» не має їх реалізовувати: достатньо, щоб агент міг "
                 "тримати кілька MCP одночасно. " + SPEC_URL)})


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


# ---------------------------------------------------------------------------
# 13. Компанія — спільна закупівля кількох людей
# ---------------------------------------------------------------------------
# НОВИЙ КОНЦЕПТ. У «Сільпо» цього немає ніде: ані в застосунку, ані в MCP.
#
# «Сімейна група» — це інше й воно вже існує: кілька акаунтів на різних номерах,
# зведених у сталу сутність зі спільними бонусами. Компанія — навпаки, разова:
# зібрались на пікнік, кожен кинув у список своє, поїхали, розрахувались,
# розійшлись. Постійного звʼязку між акаунтами тут не потрібно й не хочеться.
#
# Три речі, яких без цього не буває:
#   1. алергії ВСІХ учасників в одному місці — зараз організатор тримає їх у
#      голові або в чаті, і саме так хтось отримує горіхи в салаті;
#   2. пропозиції кожного — список збирається не однією людиною;
#   3. розрахунок — хто скільки заплатив і хто кому лишився винен.
#
# Третє — свідома цитата з банків: «розділити чек» у Monobank люди вже вміють
# і розуміють. Ми рахуємо суми й перекази; переказ грошей — не наша справа й
# не справа продуктової мережі. Поле `simulated` стоїть скрізь, де це видно.
CREW_DEMO = [
    {"name": "Олександр", "role": "організатор", "allergies": [], "diets": [],
     "suggests": ["ковбаски для гриля", "вугілля деревне"], "paid_uah": 0.0},
    {"name": "Марина", "role": "гість", "allergies": ["горіхи"], "diets": [],
     "suggests": ["овочі для гриля", "лаваш"], "paid_uah": 0.0},
    {"name": "Тарас", "role": "гість", "allergies": [], "diets": ["без лактози"],
     "suggests": ["пиво світле", "чипси"], "paid_uah": 0.0},
    {"name": "Ірина", "role": "гість", "allergies": ["мед"], "diets": ["вегетаріанська"],
     "suggests": ["печериці", "кукурудза"], "paid_uah": 0.0},
    {"name": "Богдан", "role": "гість", "allergies": [], "diets": [],
     "suggests": ["кавун", "вода мінеральна"], "paid_uah": 0.0},
]


def _crews(data: dict) -> dict:
    return data.setdefault("crews", {})


def _crew_or_latest(data: dict, crew_id: str | None) -> dict | None:
    crews = _crews(data)
    if crew_id:
        return crews.get(crew_id)
    return max(crews.values(), key=lambda c: c.get("created_at", ""), default=None)


def find_crew_id(title: str | None) -> str | None:
    """Id компанії за назвою — «Пікнік», як її називає гість у чаті.

    Збіг без регістру й лапок; якщо назв кілька однакових — найсвіжіша.
    """
    low = (title or "").strip().strip("«»\"'").lower()
    if not low:
        return None
    crews = [c for c in _crews(_load()).values()
             if (c.get("title") or "").strip().lower() == low]
    if not crews:
        crews = [c for c in _crews(_load()).values()
                 if low in (c.get("title") or "").lower()]
    crew = max(crews, key=lambda c: c.get("created_at", ""), default=None)
    return crew["id"] if crew else None


def _member(crew: dict, name: str) -> dict | None:
    low = (name or "").strip().lower()
    return next((m for m in crew["members"] if m["name"].lower() == low), None)


def create_crew(title: str, occasion: str = "пікнік", people: int = 0,
                demo: bool = True) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Створити компанію під конкретну подію.

    Args:
        title: як компанія називається — «Пікнік на Трухановому».
        occasion: тема; від неї залежить базовий набір, якщо ніхто нічого не
            запропонував.
        people: скільки людей очікується; впливає лише на кількості в паку.
        demo: засіяти демонстраційних учасників з алергіями й пропозиціями.
            У живому продукті на це місце стає запрошення за посиланням.
    """
    done = _traced("silpo_create_crew", {"title": title, "occasion": occasion})
    data = _load()
    crews = _crews(data)
    crew_id = f"crew-{len(crews) + 1}"
    members = [dict(m) for m in CREW_DEMO] if demo else []
    crew = {
        "id": crew_id, "title": title, "occasion": occasion,
        "people": people or (len(members) or 4),
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
        "members": members, "demo": demo,
    }
    crews[crew_id] = crew
    _save(data)
    done(f'{title}: {len(members)} осіб')
    # Запрошення — посилання, яке організатор кидає в чат компанії або показує
    # QR-кодом: кожен додає себе зі свого телефона. Хост підставляє сторінка.
    crew["join_path"] = f"/join?crew={crew_id}"
    return {"crew": crew, "proposed": True, "simulated": demo,
            "spec": ("Разова компанія під подію: кожен учасник додає свої обмеження "
                     "й свої пропозиції зі свого телефона, а кошик виходить один. "
                     "Це НЕ «сімейна група» — постійного звʼязку акаунтів тут не "
                     "потрібно. У «Сільпо» такого немає ні в застосунку, ні в MCP. "
                     + SPEC_URL)}


def get_crew(crew_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Компанія цілком: учасники, обмеження, пропозиції."""
    done = _traced("silpo_get_crew", {"crew_id": crew_id})
    crew = _crew_or_latest(_load(), crew_id)
    if not crew:
        done("немає жодної")
        return {"crew": None, "proposed": True,
                "hint": "Компанії ще немає — створи через silpo_create_crew."}

    allergies, diets, wishes = [], [], []
    for m in crew["members"]:
        for a in m.get("allergies") or []:
            allergies.append({"term": a, "who": m["name"]})
        for d in m.get("diets") or []:
            diets.append({"term": d, "who": m["name"]})
        for s in m.get("suggests") or []:
            wishes.append({"item": s, "who": m["name"]})

    done(f'{crew["title"]}: {len(crew["members"])} осіб, {len(allergies)} алергій')
    return {
        "crew": crew, "members": crew["members"],
        "allergies": allergies, "diets": diets, "wishes": wishes,
        "blocked_for_everyone": sorted({a["term"] for a in allergies}),
        "proposed": True, "simulated": bool(crew.get("demo")),
        "why": ("Алергія будь-кого блокує товар для ВСЬОГО кошика — на пікніку "
                "немає окремої тарілки. Зараз ці дані живуть у голові організатора."),
    }


def list_crews() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Усі компанії гостя."""
    done = _traced("silpo_list_crews", {})
    crews = list(_crews(_load()).values())
    done(f"{len(crews)}")
    return {"count": len(crews), "crews": crews, "proposed": True}


def crew_join(name: str, crew_id: str | None = None,
              allergies: list[str] | None = None, diets: list[str] | None = None,
              suggests: list[str] | None = None, role: str = "гість") -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Учасник приєднується і одразу каже про себе головне.

    Той самий виклик і додає людину, і оновлює вже додану — щоб «змінив думку»
    не вимагало окремого tool.
    """
    done = _traced("silpo_crew_join", {"crew_id": crew_id, "name": name})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    if not crew:
        done("немає компанії")
        return {"error": "Компанії ще немає — спершу створи її.", "proposed": True}

    member = _member(crew, name)
    if not member:
        member = {"name": name.strip(), "role": role, "allergies": [], "diets": [],
                  "suggests": [], "paid_uah": 0.0}
        crew["members"].append(member)
    for field, value in (("allergies", allergies), ("diets", diets),
                         ("suggests", suggests)):
        if value is not None:
            member[field] = [v.strip() for v in value if str(v).strip()]
    _save(data)
    done(f'{name} → {crew["title"]}')
    return {"crew_id": crew["id"], "member": member,
            "members": len(crew["members"]), "proposed": True}


def crew_suggest(name: str, items: list[str], crew_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Учасник докидає своє в спільний список.

    Не замінює попереднє, а додає — список компанії росте, поки збираються.
    """
    done = _traced("silpo_crew_suggest", {"crew_id": crew_id, "name": name})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    if not crew:
        done("немає компанії")
        return {"error": "Компанії ще немає.", "proposed": True}
    member = _member(crew, name)
    if not member:
        done("немає такого учасника")
        return {"error": f"У компанії немає «{name}». Спершу silpo_crew_join.",
                "proposed": True}
    have = {s.lower() for s in member["suggests"]}
    added = [i.strip() for i in items if i.strip() and i.strip().lower() not in have]
    member["suggests"] += added
    _save(data)
    done(f'{name}: +{len(added)}')
    return {"crew_id": crew["id"], "member": member["name"],
            "added": added, "suggests": member["suggests"], "proposed": True}


def crew_leave(name: str, crew_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Прибрати учасника — разом із його обмеженнями."""
    done = _traced("silpo_crew_leave", {"crew_id": crew_id, "name": name})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    if not crew:
        return {"error": "Компанії ще немає.", "proposed": True}
    before = len(crew["members"])
    crew["members"] = [m for m in crew["members"] if m["name"].lower() != name.lower()]
    _save(data)
    done(f"{before} → {len(crew['members'])}")
    return {"crew_id": crew["id"], "removed": before != len(crew["members"]),
            "members": len(crew["members"]), "proposed": True}


def crew_paid(name: str, amount_uah: float, crew_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Хто скільки вже заплатив — вхід для розрахунку."""
    done = _traced("silpo_crew_paid", {"crew_id": crew_id, "name": name,
                                       "amount_uah": amount_uah})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    if not crew:
        return {"error": "Компанії ще немає.", "proposed": True}
    member = _member(crew, name)
    if not member:
        return {"error": f"У компанії немає «{name}».", "proposed": True}
    member["paid_uah"] = round(float(amount_uah or 0), 2)
    _save(data)
    done(f'{name}: {member["paid_uah"]} ₴')
    return {"crew_id": crew["id"], "member": member["name"],
            "paid_uah": member["paid_uah"], "proposed": True}


def crew_share(name: str, amount_uah: float | None = None, crew_id: str | None = None,
               propose: bool = False, note: str = "") -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Інша частка для учасника — закріпити або запропонувати.

    Організатор закріплює суму («Тарас — 120, він бере лише пиво»); гість зі
    свого телефона лише ПРОПОНУЄ («мені 100, я на годину») — і організатор
    приймає або ні. Рівна частка — типова, але рівна не завжди справедлива.

    Args:
        name: чия частка.
        amount_uah: сума; None — прибрати закріплення (знову порівну).
        propose: True — це пропозиція гостя, не рішення організатора.
        note: чому («беру лише пиво»).
    """
    done = _traced("silpo_crew_share", {"crew_id": crew_id, "name": name,
                                        "amount_uah": amount_uah, "propose": propose})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    if not crew:
        done("немає компанії")
        return {"error": "Компанії ще немає.", "proposed": True}
    member = _member(crew, name)
    if not member:
        done("немає такого учасника")
        return {"error": f"У компанії немає «{name}».", "proposed": True}
    if propose:
        member["share_proposed_uah"] = amount_uah
        member["share_proposal_note"] = (note or "").strip()
    else:
        member["share_fixed_uah"] = amount_uah
        member.pop("share_proposed_uah", None)
        member.pop("share_proposal_note", None)
    _save(data)
    done(f'{name}: {"пропонує" if propose else "закріплено"} {amount_uah}')
    return {"crew_id": crew["id"], "member": member, "proposed": True}


def crew_share_answer(name: str, accept: bool = True, crew_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Прийняти або відхилити пропозицію гостя щодо частки."""
    done = _traced("silpo_crew_share_answer", {"crew_id": crew_id, "name": name, "accept": accept})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    member = _member(crew, name) if crew else None
    if not member:
        done("немає такого учасника")
        return {"error": f"У компанії немає «{name}».", "proposed": True}
    amount = member.pop("share_proposed_uah", None)
    member.pop("share_proposal_note", None)
    if accept and amount is not None:
        member["share_fixed_uah"] = amount
    _save(data)
    done(f'{name}: {"прийнято" if accept else "відхилено"} {amount}')
    return {"crew_id": crew["id"], "member": member, "accepted": bool(accept and amount is not None),
            "proposed": True}


def clear_crews() -> dict:
    """Прибрати всі компанії. Компанія — разова: з кожним запуском сервера
    й з кожним «чистим дублем» починаємо з порожнього списку, і асистент
    знову ПРОПОНУЄ її створити, а не каже «у тебе вже є»."""
    data = _load()
    n = len(_crews(data))
    data["crews"] = {}
    _save(data)
    return {"removed": n}


def delete_crew(crew_id: str) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Прибрати компанію разом з учасниками й пропозиціями.

    Компанія разова за задумом: після події вона має зникати, а не осідати
    списком у профілі назавжди.
    """
    done = _traced("silpo_delete_crew", {"crew_id": crew_id})
    data = _load()
    crews = _crews(data)
    gone = crews.pop(crew_id, None)
    _save(data)
    done(gone["title"] if gone else "не знайдено")
    return {"deleted": bool(gone), "crew_id": crew_id,
            "title": (gone or {}).get("title"), "left": len(crews),
            "proposed": True}


def crew_split(total_uah: float, crew_id: str | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Розділити суму на компанію і звести перекази.

    Рахує рівну частку, віднімає вже сплачене й зводить борги до МІНІМАЛЬНОЇ
    кількості переказів: найбільший боржник платить найбільшому кредитору,
    поки нуль не зійдеться.

    Грошей ми не рухаємо і рухати не будемо: «розділити чек» уміють банки —
    у Monobank ця механіка є, і люди нею вже користуються. Наша частина —
    назвати суми, бо тільки ми знаємо, що саме в кошику й чий це був вибір.
    """
    done = _traced("silpo_crew_split", {"crew_id": crew_id, "total_uah": total_uah})
    data = _load()
    crew = _crew_or_latest(data, crew_id)
    if not crew or not crew["members"]:
        done("немає компанії")
        return {"error": "Компанії ще немає або в ній нікого.", "proposed": True}

    members = crew["members"]
    total = round(float(total_uah or 0), 2)
    # Частка не завжди рівна: організатор може закріпити комусь свою суму
    # («Тарас бере лише пиво — 120»), а гість — запропонувати її сам зі свого
    # телефона. Закріплені суми віднімаємо від чека, решту ділимо порівну
    # між іншими.
    fixed = {m["name"]: round(float(m["share_fixed_uah"]), 2)
             for m in members if m.get("share_fixed_uah") is not None}
    rest_people = [m for m in members if m["name"] not in fixed]
    rest_total = max(0.0, round(total - sum(fixed.values()), 2))
    share = round(rest_total / len(rest_people), 2) if rest_people else 0.0

    rows, balances = [], []
    for m in members:
        paid = round(float(m.get("paid_uah") or 0), 2)
        own = fixed.get(m["name"], share)
        balance = round(paid - own, 2)
        rows.append({"name": m["name"], "share_uah": own, "paid_uah": paid,
                     "balance_uah": balance, "fixed": m["name"] in fixed,
                     "proposed_uah": (round(float(m["share_proposed_uah"]), 2)
                                      if m.get("share_proposed_uah") is not None else None),
                     "proposal_note": m.get("share_proposal_note") or ""})
        balances.append([m["name"], balance])

    # Скільки компанія вже виклала. Якщо це менше за суму кошика — борги в нуль
    # НЕ зійдуться, і це не помилка розрахунку, а факт: решта ще не сплачена.
    # Показати «всі розрахувались», поки в касу не внесено 300 ₴, було б рівно
    # тим вигаданим числом, проти якого побудований весь проєкт.
    paid_total = round(sum(r["paid_uah"] for r in rows), 2)
    unpaid = round(total - paid_total, 2)

    # Зведення: найбільший боржник → найбільшому кредитору. Копійчані залишки
    # (< 1 ₴) не ганяємо — у житті їх ніхто не переказує.
    debtors = sorted([b for b in balances if b[1] < -0.5], key=lambda b: b[1])
    creditors = sorted([b for b in balances if b[1] > 0.5], key=lambda b: -b[1])
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = round(min(-debtors[i][1], creditors[j][1]), 2)
        if amount >= 1:
            transfers.append({"from": debtors[i][0], "to": creditors[j][0],
                              "amount_uah": amount})
        debtors[i][1] += amount
        creditors[j][1] -= amount
        if -debtors[i][1] < 0.5:
            i += 1
        if creditors[j][1] < 0.5:
            j += 1

    done(f"{total} ₴ / {len(members)} = {share} ₴, {len(transfers)} переказів"
         + (f", ще не сплачено {unpaid} ₴" if unpaid > 0.5 else ""))
    return {
        "crew_id": crew["id"], "title": crew["title"],
        "total_uah": total, "people": len(members), "share_uah": share,
        "paid_total_uah": paid_total, "unpaid_uah": max(unpaid, 0.0),
        "rows": rows, "transfers": transfers,
        "settled": not transfers and unpaid <= 0.5,
        "note": (f"Компанія виклала {paid_total} ₴ із {total} ₴ — "
                 f"решта {unpaid} ₴ ще не сплачена, тож частина боргів "
                 "закриється лише на касі." if unpaid > 0.5 else
                 "Сплачено всю суму — лишилось лише зрівняти між своїми."),
        "proposed": True, "simulated": True,
        "handoff": ("Переказ грошей — не наша справа. Суми готові до передачі в "
                    "банківський «розділити чек» (у Monobank така механіка вже є); "
                    "ми жодної платіжної інтеграції не робимо й не імітуємо."),
        "spec": ("Мережа знає склад кошика й чий це був вибір — тільки вона може "
                 "порахувати частки чесно. Сьогодні цього немає ніде. " + SPEC_URL),
    }
