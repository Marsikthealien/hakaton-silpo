"""Реєстр end-to-end сценаріїв: назва, фраза гостя і ЩО відбувається всередині.

Один опис на обидва вжитки. Картки сценаріїв в інтерфейсі беруть звідси назву,
фразу й перелік tools; вкладка «Під капотом» — покроковий ланцюг. Доки це лежало
у двох місцях, назви розходились.

`kind` у кроці:
    real      — офіційний tool mcp.silpo.ua
    proposed  — tool, якого в MCP немає; ми його реалізували й пропонуємо додати
    ours      — наш розрахунок, не виклик API (цикл покупки, ваги смаку, маршрут)
"""

from __future__ import annotations

GROUPS = [
    {"id": "chek", "title": "Із твоїх чеків", "about": "усе будується на історії покупок"},
    {"id": "podiia", "title": "Під подію і компанію", "about": "страва, настрій, вечір, зустріч, родина"},
    {"id": "shop", "title": "Магазин і логістика", "about": "відстань, вага, маршрут, «Нова пошта»"},
    {"id": "money", "title": "Гроші та звички", "about": "відповідь — одне число з чеків"},
]


def _s(tool, note, kind="real"):
    return {"tool": tool, "note": note, "kind": kind}


FLOWS = [
    # ---------------------------------------------------------------- чеки --
    {"id": "repeat", "group": "chek", "title": "Повтори останній чек",
     "phrase": "Повтори мою минулу покупку",
     "result": "10 із 10 позицій відновлено, відсутні замінено схожими",
     "steps": [
         _s("silpo_get_my_offline_orders", "чек фізичного магазину: позиції, ціни, lagerId, catalogProduct"),
         _s("silpo_get_similar_products", "лише тим позиціям, у яких stock: 0 у цьому магазині"),
         _s("silpo_clear_shopping_cart", "кошик збирається з нуля, щоб не змішати зі старим"),
         _s("silpo_add_or_update_cart_products", "запис у СПРАВЖНІЙ кошик акаунта"),
         _s("silpo_get_shopping_cart_by_id", "звірка факту: success:true ще не означає «поклалось»"),
     ]},
    {"id": "reorder", "group": "chek", "title": "Що в мене закінчилось",
     "phrase": "Збери те, що я зазвичай беру і що вже мало б закінчитись",
     "result": "17 звичок розпізнано, 8 із них «пора»",
     "steps": [
         _s("silpo_get_my_offline_orders", "уся історія через offset, а не перші 10"),
         _s("цикл покупки", "інтервали між датами тієї самої позиції в різних чеках", "ours"),
         _s("silpo_find_products_batch", "поточні ціни й наявність для того, що вже пора"),
     ]},
    {"id": "pantry", "group": "chek", "title": "Що зникло з холодильника",
     "phrase": "Подивись, чого немає вдома, і збери список",
     "result": "полиці холодильника проти звичок із чеків",
     "steps": [
         _s("silpo_pantry_missing", "інвентар кухні; джерела такого в «Сільпо» немає взагалі", "proposed"),
         _s("silpo_get_my_offline_orders", "звички, з якими звіряємо полиці"),
         _s("silpo_find_products_batch", "того, чого бракує"),
     ]},
    {"id": "wellbeing", "group": "chek", "title": "Після тренування",
     "phrase": "Я щойно з залу і спав 5 годин",
     "result": "сон і навантаження змінюють кошик",
     "steps": [
         _s("silpo_wellbeing_sync", "сон, тренування, настрій — дані чутливі, потрібна окрема згода", "proposed"),
         _s("silpo_find_products_batch", "підбір під стан"),
     ]},
    {"id": "weekly", "group": "chek", "title": "Тижневий закуп сам",
     "phrase": "Збери мені кошик на тиждень",
     "result": "кожна позиція пояснює, чому вона тут",
     "steps": [
         _s("silpo_pantry_missing", "джерело 1: чого немає вдома", "proposed"),
         _s("silpo_get_my_offline_orders", "джерело 2: що мало б закінчитись за циклом"),
         _s("ваги смаку", "джерело 3: улюблене, на що зараз діє знижка", "ours"),
         _s("silpo_find_products_batch", "усе трьома групами одним запитом"),
     ]},
    {"id": "budget", "group": "chek", "title": "Розумний бюджет",
     "phrase": "Лишилось 840 грн на тиждень — збери кошик",
     "result": "кошик рівно під залишок, що не влізло — поіменно з причиною",
     "steps": [
         _s("silpo_get_my_offline_orders", "звички і їх частота"),
         _s("пріоритет", "спершу прострочене за циклом, потім найчастіше", "ours"),
         _s("silpo_find_products_batch", "ціни; бюджет — жорстка стеля"),
     ]},

    # --------------------------------------------------------------- подія --
    {"id": "meal", "group": "podiia", "title": "Страва на суму",
     "phrase": "Хочу вечерю на 500 грн",
     "result": "рецепт із кроками + реальні продукти під нього",
     "steps": [
         _s("silpo_find_recipes", "у «Сільпо» рецепти вже є на silpo.ua/recipes, але не в MCP", "proposed"),
         _s("silpo_get_my_offline_orders", "рецепт зі знайомих продуктів приємніший за екзотичний"),
         _s("silpo_find_products_batch", "усі складники одним запитом, до 30 за раз"),
     ]},
    {"id": "mood", "group": "podiia", "title": "Вгадай мій настрій",
     "phrase": "Підбери щось під мій настрій",
     "result": "тест на 3 питання → полиця під настрій",
     "steps": [_s("silpo_find_products_batch", "полиця, що відповідає настрою")]},
    {"id": "evening", "group": "podiia", "title": "Залипнути в телевізор",
     "phrase": "Хочу залипнути ввечері",
     "result": "жанр вечора лягає на реальну курацію «Сільпо»",
     "steps": [
         _s("silpo_get_product_sets", "футбол → lvivske-310, кіно → dlia-smachnoi-vecheri"),
         _s("silpo_get_products", "товари набору, фільтр mustHavePromotion"),
         _s("silpo_find_products_batch", "добірка того, чого в наборі немає"),
         _s("silpo_get_similar_products", "на «Обрати інший» — картки з фото й дельтою ціни"),
     ]},
    {"id": "party", "group": "podiia", "title": "Шашлик на шістьох",
     "phrase": "Шашлик на шістьох",
     "result": "цибуля 2.7 кг, лаваш ×3, вугілля — один мішок",
     "steps": [
         _s("silpo_find_products_batch", "позиції теми"),
         _s("масштаб на людей", "вагове в кілограмах, штучне в штуках; що не ділиться — лишається одним", "ours"),
     ]},
    {"id": "kids", "group": "podiia", "title": "Дитяча зона за віком",
     "phrase": "Збери щось дитині",
     "result": "Назару 16 — і це вже не пюре",
     "steps": [
         _s("silpo_get_my_family", "children[].dateOfBirth є в API і не використовується ніде"),
         _s("silpo_find_products_batch", "підбір під вікову смугу"),
     ]},
    {"id": "family", "group": "podiia", "title": "Вечеря на всю сімʼю",
     "phrase": "Збери вечерю, щоб усім підійшло",
     "result": "алергія будь-кого блокує товар для ВСЬОГО кошика",
     "steps": [
         _s("silpo_get_my_family", "склад родини справжній: діти й улюбленці"),
         _s("silpo_get_family_preferences", "смаки й алергії учасників: «Простір вподобань» у MCP немає", "proposed"),
         _s("silpo_find_products_batch", "підбір із виключенням усіх алергенів родини"),
     ]},
    {"id": "heirloom", "group": "podiia", "title": "Спадкова кухня",
     "phrase": "Приготуй те, що готувала бабуся",
     "result": "рецепт родини → кошик із реальних товарів",
     "steps": [
         _s("silpo_get_family_recipes", "спільна книга в межах «Сімейного доступу»", "proposed"),
         _s("silpo_find_products_batch", "складники → артикули магазину"),
     ]},

    # ------------------------------------------------------------- магазин --
    {"id": "geo", "group": "shop", "title": "Топати чи замовити",
     "phrase": "Дійти до Сільпо чи замовити доставку?",
     "result": "поріг безкоштовної доставки — рахований наперед",
     "steps": [
         _s("silpo_list_branches", "latitude/longitude кожної з 455 філій"),
         _s("гаверсинус", "відстань рахуємо самі, без зовнішніх геосервісів", "ours"),
         _s("silpo_get_available_delivery_types", "які способи доступні за координатами"),
         _s("silpo_get_time_slots", "deliveryCost, minOrderCost, maxWeight, deliveryCostMap"),
         _s("silpo_estimate_delivery", "усе одним викликом замість 1+5", "proposed"),
     ]},
    {"id": "weight", "group": "shop", "title": "Чи влізе кошик",
     "phrase": "Кошик не заважкий для доставки?",
     "result": "maxWeight лежить у кожному слоті й не використовується ніде",
     "steps": [
         _s("silpo_get_shopping_cart_by_id", "calculation.delivery.totalWeight"),
         _s("silpo_get_available_delivery_types", "ліміт живе на доставці, а не на самовивозі"),
         _s("silpo_get_time_slots", "доставка додому 40 кг, бізнес 500 кг, самовивіз без ліміту"),
     ]},
    {"id": "route", "group": "shop", "title": "Маршрут по залу",
     "phrase": "Скажи, в якому порядку обходити магазин",
     "result": "28 реальних розділів у порядку обходу",
     "steps": [
         _s("silpo_get_categories_tree", "28 розділів у порядку самого «Сільпо»"),
         _s("розділ за назвою", "categoryId у картці товару немає — доводиться вгадувати", "ours"),
         _s("silpo_get_store_layout", "порядок відділів конкретного магазину", "proposed"),
     ]},
    {"id": "send", "group": "shop", "title": "Відправ батькам у Полтаву",
     "phrase": "Відправ батькам у Полтаву продуктів",
     "result": "пак + 25 відділень «Нової пошти»",
     "steps": [
         _s("silpo_find_products_batch", "пак у наявному магазині"),
         _s("silpo_find_nova_poshta_settlements", "місто словами → id населеного пункту"),
         _s("silpo_find_nova_poshta_offices", "відділення в цьому місті"),
     ]},

    # --------------------------------------------------------------- гроші --
    {"id": "coupons", "group": "money", "title": "Чек-детектив",
     "phrase": "Які купони в мене згорають?",
     "result": "спрацював 1 купон на 3 144 ₴, зараз згорає 11",
     "steps": [
         _s("silpo_get_my_coupons", "видані купони: promoId, endDate, rewardValue"),
         _s("silpo_get_my_offline_orders", "rewards[].promoId — які насправді спрацювали"),
         _s("звірка за promoId", "точний збіг, не здогадка. На звʼязок вказує сама дока MCP", "ours"),
     ]},
    {"id": "savings", "group": "money", "title": "Скільки я зекономив",
     "phrase": "Скільки я зекономив за цей час?",
     "result": "2 973 ₴ знижок за 32 чеки, 24.9% від суми",
     "steps": [
         _s("silpo_get_my_offline_orders", "sumDiscount і rewards[] по кожному чеку"),
         _s("групування за промо", "скільки разів спрацювало й на яку суму", "ours"),
     ]},
    {"id": "spend", "group": "money", "title": "Куди йдуть гроші",
     "phrase": "Куди в мене йдуть гроші?",
     "result": "3 346 ₴ проти 2 118 ₴ у попередні 30 днів",
     "steps": [
         _s("silpo_get_my_offline_orders", "позиції двох періодів"),
         _s("класифікатор 28 розділів", "categoryId немає в API — розділ визначаємо за назвою", "ours"),
     ]},
    {"id": "plus", "group": "money", "title": "Чи вигідний «Плюхс»",
     "phrase": "Чи вигідна мені підписка?",
     "result": "3 057 ₴/міс проти порогу 1 990 ₴ — вигідно",
     "steps": [
         _s("silpo_get_my_premium_subscription", "tool каже лише «є підписка чи ні»"),
         _s("silpo_get_my_offline_orders", "скільки насправді витрачаєш на місяць"),
         _s("умови підписки", "ціна й кешбек — зі сторінки silpo.ua, у MCP їх немає", "ours"),
     ]},
    {"id": "reminders", "group": "money", "title": "Не забудь",
     "phrase": "Нагадай, що скінчилось",
     "result": "7 прострочено, 1 скінчиться за 5 днів",
     "steps": [
         _s("silpo_get_my_offline_orders", "дати покупок кожної позиції"),
         _s("цикл покупки", "нагадування без того, щоб гість щось заводив руками", "ours"),
         _s("silpo_get_my_family", "окремий рядок про улюбленця, якщо корм є в чеках"),
     ]},
    {"id": "popular", "group": "money", "title": "Що беруть у моєму магазині",
     "phrase": "Що зараз беруть у моєму магазині?",
     "result": "соціальний доказ на живих даних філії",
     "steps": [_s("silpo_get_popular_categories", "перелік розділів; чисел tool не віддає")]},
    {"id": "risk", "group": "money", "title": "Ризик збирання",
     "phrase": "Що можуть не зібрати?",
     "result": "попередження до оплати замість дзвінка кур'єра після",
     "steps": [
         _s("silpo_get_shopping_cart_by_id", "що зараз у кошику"),
         _s("silpo_get_replacements", "tool створений рівно для цього і не використовується ніде"),
     ]},
    {"id": "eco", "group": "money", "title": "Екослід кошика",
     "phrase": "Наскільки екологічний мій кошик?",
     "result": "оцінка з ваги й частки вагового",
     "steps": [
         _s("silpo_get_shopping_cart_by_id", "totalWeight і склад кошика"),
         _s("оцінка", "пакування в картці товару немає — це оцінка, а не вимір", "ours"),
     ]},
    {"id": "impulse", "group": "money", "title": "Чи варто це брати",
     "phrase": "Чи варто мені брати чипси?",
     "result": "«зараз на 26% дорожче за твою середню»",
     "steps": [
         _s("silpo_get_my_offline_orders", "скільки разів брав і по чому"),
         _s("silpo_find_products_batch", "скільки коштує зараз"),
         _s("вердикт", "іноді правильна відповідь — «не бери»", "ours"),
     ]},
    {"id": "certs", "group": "money", "title": "Сертифікат як оплата",
     "phrase": "Чи можу я заплатити сертифікатом?",
     "result": "tool вважали зламаним — виявилось, збій плаваючий",
     "steps": [
         _s("silpo_get_my_certificates", "номінал, штрихкод, термін дії. 2 вересня падав із 500, 8-го — 12 викликів поспіль без помилки"),
         _s("silpo_get_shopping_cart_by_id", "скільки лишиться доплатити"),
         _s("silpo_add_or_update_certificates", "кладе сертифікат у СПРАВЖНІЙ кошик; потрібен shoppingCartId"),
         _s("підбір під суму", "зібрати кошик рівно під номінал агент не може: у пошуку немає ані бюджету, ані сортування під ціль", "ours"),
     ]},
    {"id": "compare", "group": "money", "title": "Де вигідніше",
     "phrase": "Де цей список дешевший?",
     "result": "різниця між філіями Києва — 40 ₴ на двох позиціях",
     "steps": [
         _s("silpo_list_branches", "магазини міста"),
         _s("silpo_find_products_batch", "той самий список із іншим branchId — ціни різні"),
     ]},

    # ------------------------------------------------------------- окремі --
    {"id": "game", "group": "money", "title": "Грибниця",
     "phrase": "Який у мене рівень?",
     "result": "8 966 ₴ за 32 чеки → 19 рівень, 9 із 14 досягнень",
     "steps": [
         _s("silpo_get_my_offline_orders", "×4 через offset: досвід рахується з УСІЄЇ історії"),
         _s("silpo_get_game_profile", "рівень, скін, грибниця", "proposed"),
         _s("silpo_get_achievements", "«Мандрівник» — це різні filId, «Всеїдний» — різні розділи", "proposed"),
         _s("silpo_get_themed_branches", "дизайнерські магазини: концепції в API немає", "proposed"),
     ]},
    {"id": "swipe", "group": "money", "title": "Департамент дивинок",
     "phrase": "Покажи мені щось нове",
     "result": "свайп рухає вагу товару І його полиці",
     "steps": [
         _s("silpo_get_swipe_deck", "колода з полиць, які гість любить, плюс одна «на виріст»", "proposed"),
         _s("silpo_add_or_update_favorite_products", "свайп вправо → справжнє «Обране» акаунта"),
         _s("silpo_record_swipe", "свайп уліво лишається в нас: місця для відмови в API немає", "proposed"),
     ]},
]


def flows() -> dict:
    """Усі end-to-end сценарії з покроковим ланцюгом усередині."""
    counts = {"real": 0, "proposed": 0, "ours": 0}
    for flow in FLOWS:
        for step in flow["steps"]:
            counts[step["kind"]] = counts.get(step["kind"], 0) + 1
    return {
        "groups": GROUPS, "flows": FLOWS,
        "total": len(FLOWS), "steps": counts,
        "legend": {"real": "офіційний tool mcp.silpo.ua",
                   "proposed": "tool, якого в MCP немає — ми його пропонуємо",
                   "ours": "наш розрахунок, не виклик API"},
    }
