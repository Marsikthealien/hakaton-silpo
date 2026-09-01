"""Фейкові дані для мок Silpo MCP.

Усі дані вигадані та потрібні лише для локальної розробки й демо на хакатоні
"Сільпо" AI Factory. Ціни в гривнях (грн). Жодних реальних API не викликається.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Каталог товарів
# ---------------------------------------------------------------------------
# Поля товару:
#   id         — стабільний ідентифікатор
#   name       — назва
#   brand      — бренд
#   category   — категорія
#   price      — поточна ціна, грн
#   old_price  — ціна до знижки (None, якщо без акції)
#   unit       — одиниця (шт, кг, л, ...)
#   in_stock   — наявність
#   tags       — теги для пошуку/рекомендацій (страва, настрій, дієта тощо)
#   nutrition  — коротка харчова довідка на 100 г/мл

PRODUCTS: list[dict] = [
    # --- Італійський вечір / паста ---
    {
        "id": "p-1001", "name": "Спагеті Barilla n.5", "brand": "Barilla",
        "category": "Бакалія", "price": 62.90, "old_price": None, "unit": "500 г",
        "in_stock": True, "tags": ["паста", "спагеті", "італійська", "карбонара", "вегетаріанське"],
        "nutrition": {"kcal": 359, "protein": 12.0, "fat": 2.0, "carbs": 71.0},
    },
    {
        "id": "p-1002", "name": "Бекон панчета нарізка", "brand": "Ферма",
        "category": "Мʼясо та ковбаси", "price": 89.90, "old_price": 109.90, "unit": "150 г",
        "in_stock": True, "tags": ["бекон", "панчета", "карбонара", "мʼясо", "італійська"],
        "nutrition": {"kcal": 458, "protein": 14.0, "fat": 44.0, "carbs": 1.0},
    },
    {
        "id": "p-1003", "name": "Сир Пармезан 40% витриманий", "brand": "Молокія",
        "category": "Сири", "price": 129.90, "old_price": None, "unit": "180 г",
        "in_stock": True, "tags": ["пармезан", "сир", "карбонара", "італійська", "вегетаріанське"],
        "nutrition": {"kcal": 392, "protein": 36.0, "fat": 27.0, "carbs": 3.0},
    },
    {
        "id": "p-1004", "name": "Яйця курячі С0, 10 шт", "brand": "Ясенсвіт",
        "category": "Яйця", "price": 74.90, "old_price": None, "unit": "10 шт",
        "in_stock": True, "tags": ["яйця", "карбонара", "сніданок", "білок"],
        "nutrition": {"kcal": 157, "protein": 12.7, "fat": 11.5, "carbs": 0.7},
    },
    {
        "id": "p-1005", "name": "Соус томатний Napoli базилік", "brand": "Mutti",
        "category": "Соуси", "price": 96.50, "old_price": None, "unit": "400 г",
        "in_stock": True, "tags": ["соус", "томатний", "паста", "італійська", "веганське"],
        "nutrition": {"kcal": 58, "protein": 1.6, "fat": 2.5, "carbs": 7.0},
    },
    {
        "id": "p-1006", "name": "Тірамісу десерт", "brand": "Кухня Сільпо",
        "category": "Готові страви", "price": 84.90, "old_price": None, "unit": "150 г",
        "in_stock": True, "tags": ["десерт", "тірамісу", "італійська", "солодке", "побалувати"],
        "nutrition": {"kcal": 291, "protein": 4.5, "fat": 18.0, "carbs": 27.0},
    },

    # --- Вечір кіно / снеки ---
    {
        "id": "p-2001", "name": "Попкорн для мікрохвильовки солоний", "brand": "Snacky",
        "category": "Снеки", "price": 34.90, "old_price": 44.90, "unit": "90 г",
        "in_stock": True, "tags": ["попкорн", "снек", "кіно", "розважитись", "веганське"],
        "nutrition": {"kcal": 387, "protein": 9.0, "fat": 6.0, "carbs": 74.0},
    },
    {
        "id": "p-2002", "name": "Кока-Кола", "brand": "Coca-Cola",
        "category": "Напої", "price": 39.90, "old_price": None, "unit": "1 л",
        "in_stock": True, "tags": ["напій", "кола", "кіно", "вечірка"],
        "nutrition": {"kcal": 42, "protein": 0.0, "fat": 0.0, "carbs": 10.6},
    },
    {
        "id": "p-2003", "name": "Шоколад молочний з фундуком", "brand": "Milka",
        "category": "Солодощі", "price": 54.90, "old_price": None, "unit": "90 г",
        "in_stock": True, "tags": ["шоколад", "солодке", "кіно", "побалувати", "комфортна їжа"],
        "nutrition": {"kcal": 545, "protein": 7.0, "fat": 32.0, "carbs": 56.0},
    },
    {
        "id": "p-2004", "name": "Піца Pepperoni заморожена", "brand": "Кухня Сільпо",
        "category": "Заморожені продукти", "price": 119.90, "old_price": 149.90, "unit": "400 г",
        "in_stock": True, "tags": ["піца", "кіно", "швидко", "готове", "вечірка"],
        "nutrition": {"kcal": 268, "protein": 11.0, "fat": 12.0, "carbs": 29.0},
    },
    {
        "id": "p-2005", "name": "Начос кукурудзяні", "brand": "Doritos",
        "category": "Снеки", "price": 62.90, "old_price": None, "unit": "100 г",
        "in_stock": True, "tags": ["начос", "снек", "кіно", "мексиканська", "веганське"],
        "nutrition": {"kcal": 498, "protein": 6.5, "fat": 26.0, "carbs": 58.0},
    },

    # --- Комфортна їжа / втома ---
    {
        "id": "p-3001", "name": "Локшина швидкого приготування курка", "brand": "Роллтон",
        "category": "Бакалія", "price": 22.90, "old_price": None, "unit": "90 г",
        "in_stock": True, "tags": ["швидко", "втома", "комфортна їжа", "просте"],
        "nutrition": {"kcal": 448, "protein": 9.0, "fat": 18.0, "carbs": 62.0},
    },
    {
        "id": "p-3002", "name": "Суп-крем гарбузовий готовий", "brand": "Кухня Сільпо",
        "category": "Готові страви", "price": 79.90, "old_price": None, "unit": "400 г",
        "in_stock": True, "tags": ["суп", "тепле", "комфортна їжа", "втома", "вегетаріанське"],
        "nutrition": {"kcal": 71, "protein": 2.0, "fat": 3.5, "carbs": 8.0},
    },
    {
        "id": "p-3003", "name": "Морозиво пломбір ванільний", "brand": "Рудь",
        "category": "Морозиво", "price": 68.90, "old_price": None, "unit": "500 г",
        "in_stock": True, "tags": ["морозиво", "солодке", "побалувати", "комфортна їжа"],
        "nutrition": {"kcal": 227, "protein": 3.5, "fat": 13.0, "carbs": 24.0},
    },

    # --- Здорове / спорт / білок ---
    {
        "id": "p-4001", "name": "Куряче філе охолоджене", "brand": "Наша Ряба",
        "category": "Мʼясо та ковбаси", "price": 149.90, "old_price": None, "unit": "1 кг",
        "in_stock": True, "tags": ["курка", "білок", "спорт", "здорове", "мʼясо"],
        "nutrition": {"kcal": 110, "protein": 23.0, "fat": 1.9, "carbs": 0.0},
    },
    {
        "id": "p-4002", "name": "Йогурт грецький натуральний 10%", "brand": "Галичина",
        "category": "Молочні продукти", "price": 44.90, "old_price": None, "unit": "350 г",
        "in_stock": True, "tags": ["йогурт", "білок", "здорове", "сніданок", "спорт", "вегетаріанське"],
        "nutrition": {"kcal": 97, "protein": 6.0, "fat": 10.0, "carbs": 4.0},
    },
    {
        "id": "p-4003", "name": "Батончик протеїновий шоколад", "brand": "Power Pro",
        "category": "Снеки", "price": 39.90, "old_price": None, "unit": "60 г",
        "in_stock": True, "tags": ["протеїн", "білок", "спорт", "перекус"],
        "nutrition": {"kcal": 360, "protein": 32.0, "fat": 12.0, "carbs": 28.0},
    },
    {
        "id": "p-4004", "name": "Салат мікс рукола-шпинат", "brand": "Ферма",
        "category": "Овочі та фрукти", "price": 54.90, "old_price": None, "unit": "120 г",
        "in_stock": True, "tags": ["салат", "зелень", "здорове", "веганське", "легке"],
        "nutrition": {"kcal": 23, "protein": 2.5, "fat": 0.4, "carbs": 2.0},
    },
    {
        "id": "p-4005", "name": "Авокадо Хасс", "brand": "—",
        "category": "Овочі та фрукти", "price": 42.90, "old_price": None, "unit": "1 шт",
        "in_stock": True, "tags": ["авокадо", "здорове", "веганське", "сніданок"],
        "nutrition": {"kcal": 160, "protein": 2.0, "fat": 15.0, "carbs": 9.0},
    },

    # --- Базове / щоденне ---
    {
        "id": "p-5001", "name": "Молоко 2.5%", "brand": "Яготинське",
        "category": "Молочні продукти", "price": 38.90, "old_price": None, "unit": "900 мл",
        "in_stock": True, "tags": ["молоко", "щоденне", "сніданок", "базове", "вегетаріанське"],
        "nutrition": {"kcal": 53, "protein": 2.8, "fat": 2.5, "carbs": 4.7},
    },
    {
        "id": "p-5002", "name": "Хліб зерновий нарізний", "brand": "Кулиничі",
        "category": "Хліб", "price": 34.90, "old_price": None, "unit": "400 г",
        "in_stock": True, "tags": ["хліб", "щоденне", "базове", "веганське"],
        "nutrition": {"kcal": 247, "protein": 8.5, "fat": 3.5, "carbs": 45.0},
    },
    {
        "id": "p-5003", "name": "Кава мелена еспресо", "brand": "Jacobs",
        "category": "Кава та чай", "price": 189.90, "old_price": 229.90, "unit": "225 г",
        "in_stock": True, "tags": ["кава", "ранок", "бадьорість", "веганське"],
        "nutrition": {"kcal": 2, "protein": 0.2, "fat": 0.0, "carbs": 0.3},
    },
    {
        "id": "p-5004", "name": "Вода мінеральна негазована", "brand": "Моршинська",
        "category": "Напої", "price": 26.90, "old_price": None, "unit": "1.5 л",
        "in_stock": True, "tags": ["вода", "щоденне", "базове", "веганське"],
        "nutrition": {"kcal": 0, "protein": 0.0, "fat": 0.0, "carbs": 0.0},
    },

    # --- Мексиканський вечір ---
    {
        "id": "p-6001", "name": "Тортилья пшенична 6 шт", "brand": "Mission",
        "category": "Бакалія", "price": 64.90, "old_price": None, "unit": "6 шт",
        "in_stock": True, "tags": ["тортилья", "мексиканська", "тако", "буріто", "веганське"],
        "nutrition": {"kcal": 305, "protein": 8.0, "fat": 7.0, "carbs": 51.0},
    },
    {
        "id": "p-6002", "name": "Квасоля червона консервована", "brand": "Bonduelle",
        "category": "Консервація", "price": 44.90, "old_price": None, "unit": "400 г",
        "in_stock": True, "tags": ["квасоля", "мексиканська", "веганське", "білок"],
        "nutrition": {"kcal": 91, "protein": 6.7, "fat": 0.5, "carbs": 14.0},
    },
    {
        "id": "p-6003", "name": "Соус сальса гострий", "brand": "Old El Paso",
        "category": "Соуси", "price": 74.90, "old_price": None, "unit": "226 г",
        "in_stock": True, "tags": ["сальса", "гостре", "мексиканська", "веганське"],
        "nutrition": {"kcal": 36, "protein": 1.5, "fat": 0.2, "carbs": 7.0},
    },

    # --- Японський вечір ---
    {
        "id": "p-7001", "name": "Рис для суші", "brand": "Sen Soy",
        "category": "Бакалія", "price": 98.90, "old_price": None, "unit": "500 г",
        "in_stock": True, "tags": ["рис", "суші", "японська", "веганське"],
        "nutrition": {"kcal": 344, "protein": 6.5, "fat": 0.9, "carbs": 77.0},
    },
    {
        "id": "p-7002", "name": "Норі листи 10 шт", "brand": "Sen Soy",
        "category": "Бакалія", "price": 79.90, "old_price": None, "unit": "10 шт",
        "in_stock": False, "tags": ["норі", "суші", "японська", "веганське"],
        "nutrition": {"kcal": 35, "protein": 6.0, "fat": 0.3, "carbs": 5.0},
    },
    {
        "id": "p-7003", "name": "Соус соєвий класичний", "brand": "Kikkoman",
        "category": "Соуси", "price": 119.90, "old_price": None, "unit": "250 мл",
        "in_stock": True, "tags": ["соєвий соус", "суші", "японська", "веганське"],
        "nutrition": {"kcal": 53, "protein": 8.0, "fat": 0.0, "carbs": 5.0},
    },
]

# ---------------------------------------------------------------------------
# Рецепти (для сценарію "хочу приготувати" — мапить страву на товари)
# ---------------------------------------------------------------------------
RECIPES: list[dict] = [
    {
        "id": "r-carbonara",
        "name": "Паста Карбонара",
        "cuisine": "італійська",
        "servings": 2,
        "product_ids": ["p-1001", "p-1002", "p-1003", "p-1004"],
        "steps": [
            "Відварити спагеті al dente.",
            "Обсмажити панчету до хрусткої скоринки.",
            "Змішати яйця з тертим пармезаном.",
            "Зʼєднати гарячу пасту, панчету та яєчну суміш поза вогнем.",
        ],
    },
    {
        "id": "r-movie-night",
        "name": "Набір для вечора кіно",
        "cuisine": "снеки",
        "servings": 2,
        "product_ids": ["p-2001", "p-2002", "p-2003", "p-2004"],
        "steps": ["Розігріти піцу.", "Приготувати попкорн.", "Охолодити напої."],
    },
    {
        "id": "r-mexican",
        "name": "Мексиканська вечеря",
        "cuisine": "мексиканська",
        "servings": 2,
        "product_ids": ["p-6001", "p-6002", "p-6003", "p-4001"],
        "steps": [
            "Обсмажити куряче філе зі спеціями.",
            "Розігріти тортильї.",
            "Зібрати тако з квасолею, куркою та сальсою.",
        ],
    },
    {
        "id": "r-sushi",
        "name": "Суші вдома",
        "cuisine": "японська",
        "servings": 2,
        "product_ids": ["p-7001", "p-7002", "p-7003"],
        "steps": ["Зварити рис.", "Загорнути начинку в норі.", "Подавати із соєвим соусом."],
    },
]

# ---------------------------------------------------------------------------
# Профіль користувача ("Власний Рахунок", родина, дієта)
# ---------------------------------------------------------------------------
USER_PROFILE: dict = {
    "user_id": "u-42",
    "name": "Арсен",
    "own_account": {  # "Власний Рахунок" — накопичення/бонуси
        "balance_uah": 148.50,
        "level": "Silver",
        "points": 1240,
    },
    "dietary_restrictions": {
        "allergies": ["горіхи"],
        "diets": [],            # напр. "веганське", "без глютену"
        "dislikes": ["гриби"],
    },
    "family": [
        {"name": "Арсен", "role": "власник", "age": 27},
        {"name": "Марія", "role": "партнер", "age": 26, "diets": ["вегетаріанське"]},
    ],
}

# ---------------------------------------------------------------------------
# Історія покупок (онлайн + офлайн)
# ---------------------------------------------------------------------------
PURCHASE_HISTORY: list[dict] = [
    {"date": "2026-08-18", "channel": "offline", "store": "Сільпо, вул. Хрещатик",
     "items": [{"product_id": "p-5001", "qty": 2}, {"product_id": "p-5002", "qty": 1},
               {"product_id": "p-5003", "qty": 1}], "total_uah": 302.60},
    {"date": "2026-08-14", "channel": "online", "store": "Silpo online",
     "items": [{"product_id": "p-1001", "qty": 2}, {"product_id": "p-1005", "qty": 1},
               {"product_id": "p-1003", "qty": 1}], "total_uah": 351.20},
    {"date": "2026-08-10", "channel": "offline", "store": "Сільпо, ТРЦ Ocean Plaza",
     "items": [{"product_id": "p-5001", "qty": 1}, {"product_id": "p-4002", "qty": 2},
               {"product_id": "p-4004", "qty": 1}], "total_uah": 183.60},
    {"date": "2026-08-05", "channel": "online", "store": "Silpo online",
     "items": [{"product_id": "p-4001", "qty": 1}, {"product_id": "p-4004", "qty": 2},
               {"product_id": "p-2002", "qty": 1}], "total_uah": 299.60},
]

# ---------------------------------------------------------------------------
# Купони та персональні акції
# ---------------------------------------------------------------------------
COUPONS: list[dict] = [
    {"id": "c-01", "title": "-15% на італійську бакалію", "discount_percent": 15,
     "applies_to_categories": ["Бакалія", "Соуси"], "min_order_uah": 150,
     "valid_until": "2026-08-31"},
    {"id": "c-02", "title": "-30 грн на снеки для вечора кіно", "discount_uah": 30,
     "applies_to_categories": ["Снеки", "Солодощі"], "min_order_uah": 100,
     "valid_until": "2026-09-05"},
]

PERSONAL_PROMOTIONS: list[dict] = [
    {"id": "pp-01", "product_id": "p-5003", "reason": "Ти регулярно береш каву",
     "personal_price_uah": 169.90, "regular_price_uah": 229.90},
    {"id": "pp-02", "product_id": "p-4002", "reason": "Часто купуєш грецький йогурт",
     "personal_price_uah": 37.90, "regular_price_uah": 44.90},
]

# ---------------------------------------------------------------------------
# Слоти доставки
# ---------------------------------------------------------------------------
DELIVERY_SLOTS: list[dict] = [
    {"id": "slot-1", "date": "2026-08-25", "window": "18:00–20:00", "available": True, "price_uah": 49},
    {"id": "slot-2", "date": "2026-08-25", "window": "20:00–22:00", "available": True, "price_uah": 49},
    {"id": "slot-3", "date": "2026-08-26", "window": "10:00–12:00", "available": True, "price_uah": 39},
    {"id": "slot-4", "date": "2026-08-26", "window": "12:00–14:00", "available": False, "price_uah": 39},
]
