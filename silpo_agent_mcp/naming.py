"""Українські назви викликів — щоб стрічка «Що відбувається» читалась людиною.

`silpo_get_my_offline_orders` каже все розробникові й нічого гостю. У демо
дивиться друге: важливо, щоб було видно, що агент справді пішов по чеки, а не
вигадав числа. Технічна назва лишається — вона стоїть у картці виклику.

Одне джерело на всі місця: стрічка на головній, «Під капотом», трейс у API.
"""

from __future__ import annotations

# 40 офіційних tools mcp.silpo.ua
OFFICIAL = {
    "silpo_get_my_profile": "читаю профіль акаунта",
    "silpo_get_loyalty_info": "дивлюсь картку й балобонуси",
    "silpo_get_my_offline_orders": "піднімаю чеки з магазинів",
    "silpo_get_my_online_orders": "піднімаю онлайн-замовлення",
    "silpo_get_my_family": "дивлюсь склад родини",
    "silpo_get_my_food_restrictions": "читаю харчові обмеження з акаунта",
    "silpo_get_my_favorites": "дивлюсь «Обране»",
    "silpo_add_or_update_favorite_products": "додаю в «Обране»",
    "silpo_get_my_coupons": "перебираю купони",
    "silpo_get_coupon_details": "розкриваю купон",
    "silpo_get_my_promos": "перебираю персональні промо",
    "silpo_get_promotions": "дивлюсь акції мережі",
    "silpo_get_promo_codes": "перевіряю промокоди",
    "silpo_get_my_certificates": "перевіряю сертифікати",
    "silpo_add_or_update_certificates": "кладу сертифікат у кошик",
    "silpo_get_my_premium_subscription": "перевіряю підписку «Плюхс»",
    "silpo_find_products_batch": "шукаю товари в каталозі",
    "silpo_get_product_details": "розкриваю картку товару",
    "silpo_get_similar_products": "шукаю заміну",
    "silpo_get_replacements": "питаю, що можуть не зібрати",
    "silpo_get_products": "беру товари набору",
    "silpo_get_product_sets": "дивлюсь куратовані набори",
    "silpo_get_categories": "читаю розділи",
    "silpo_get_categories_tree": "читаю дерево розділів",
    "silpo_get_category": "розкриваю розділ",
    "silpo_get_popular_categories": "дивлюсь, що беруть у цій філії",
    "silpo_get_my_shopping_cart": "відкриваю кошик акаунта",
    "silpo_get_shopping_cart_by_id": "перечитую кошик після запису",
    "silpo_create_shopping_cart": "створюю кошик",
    "silpo_update_shopping_cart": "оновлюю кошик",
    "silpo_add_or_update_cart_products": "кладу товари в справжній кошик",
    "silpo_remove_cart_products": "прибираю з кошика",
    "silpo_clear_shopping_cart": "чищу кошик перед збіркою",
    "silpo_list_branches": "беру перелік магазинів із координатами",
    "silpo_get_available_delivery_types": "питаю доступні способи отримання",
    "silpo_get_time_slots": "дивлюсь слоти, ціни й пороги доставки",
    "silpo_get_my_delivery_addresses": "читаю збережені адреси",
    "silpo_find_address": "шукаю адресу",
    "silpo_find_nova_poshta_settlements": "шукаю місто «Нової пошти»",
    "silpo_find_nova_poshta_offices": "шукаю відділення",
}

# Те, чого в MCP немає — ми це пропонуємо
PROPOSED = {
    "silpo_get_product_composition": "читаю склад товару",
    "silpo_find_recipes": "шукаю рецепт",
    "silpo_find_recipes_online": "шукаю рецепт в інтернеті",
    "silpo_also_bought": "дивлюсь, що беруть разом",
    "silpo_estimate_delivery": "рахую способи отримання одним викликом",
    "silpo_payment_options": "питаю способи оплати",
    "silpo_place_order": "оформлюю замовлення",
    "silpo_check_availability": "перевіряю наявність із причиною",
    "silpo_precalculate_prices": "звіряю ціну з касою",
    "silpo_get_purchase_habits": "піднімаю звички покупок",
    "silpo_get_family_preferences": "читаю смаки й алергії родини",
    "silpo_set_member_preferences": "зберігаю вподобання учасника",
    "silpo_get_family_recipes": "відкриваю книгу сімейних рецептів",
    "silpo_add_family_recipe": "додаю сімейний рецепт",
    "silpo_record_swipe": "запамʼятовую свайп",
    "silpo_get_swipes": "піднімаю історію свайпів",
    "silpo_get_swipe_deck": "збираю колоду дивинок",
    "silpo_get_taste_weights": "читаю ваги смаку",
    "silpo_bump_taste_weight": "рухаю вагу смаку",
    "silpo_rebuild_taste_weights": "перераховую ваги з чеків",
    "silpo_select_promos": "активую обрані промо",
    "silpo_pantry_sync": "синхронізую комору",
    "silpo_pantry_missing": "звіряю комору зі звичками",
    "silpo_pantry_state": "дивлюсь, що лежить удома",
    "silpo_wellbeing_sync": "приймаю дані трекера",
    "silpo_wellbeing_state": "читаю самопочуття",
    "silpo_list_connectors": "перебираю трекери",
    "silpo_connect_source": "підключаю джерело",
    "silpo_get_game_profile": "рахую рівень із чеків",
    "silpo_get_achievements": "перевіряю досягнення",
    "silpo_get_themed_branches": "дивлюсь дизайнерські магазини",
    "silpo_claim_level_reward": "відкриваю нагороду за рівень",
    "silpo_get_skins": "перебираю скіни",
    "silpo_set_skin": "міняю скін",
    "silpo_get_store_layout": "читаю порядок відділів",
    "silpo_save_store_layout": "зберігаю порядок відділів",
    "silpo_create_crew": "створюю компанію",
    "silpo_get_crew": "відкриваю компанію",
    "silpo_list_crews": "перебираю компанії",
    "silpo_crew_join": "додаю учасника з його обмеженнями",
    "silpo_crew_suggest": "приймаю пропозицію учасника",
    "silpo_crew_leave": "прибираю учасника",
    "silpo_crew_paid": "записую, хто скільки заплатив",
    "silpo_crew_split": "ділю суму на компанію",
    "silpo_delete_crew": "прибираю компанію",
    "silpo_get_household": "читаю домогосподарство",
    "silpo_share_cart": "ділюсь кошиком за посиланням",
}

TOOL_UA = {**OFFICIAL, **PROPOSED}


def tool_title(tool: str) -> str:
    """Людською мовою. Якщо назви немає — віддаємо технічну, без вигадок."""
    return TOOL_UA.get(tool) or tool.replace("silpo_", "").replace("_", " ")
