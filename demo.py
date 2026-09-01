"""Швидкий димовий тест логіки мок Silpo MCP — без запуску MCP-клієнта.

Запуск:  python demo.py

Проганяє типовий сценарій хакатону: "хочу італійський вечір до 500 грн" →
знайти рецепт → додати товари → застосувати купон → підготувати checkout.
"""

import json

from silpo_mcp import server as s


def show(title, obj):
    print(f"\n=== {title} ===")
    print(json.dumps(obj, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    s._cart.clear()

    show("Пошук: паста", s.search_products("паста", limit=3))
    show("Batch-пошук інгредієнтів карбонари",
         s.batch_search_products(["спагеті", "бекон", "пармезан", "яйця"], limit_per_query=1))
    show("Рецепт карбонари", s.find_recipe("карбонара"))

    # Збираємо італійський вечір: карбонара + тірамісу
    s.add_many_to_cart(["p-1001", "p-1002", "p-1003", "p-1004", "p-1006"])
    show("Кошик", s.get_cart())

    show("Купони", s.get_coupons())
    show("Персональні акції", s.get_personal_promotions())
    show("Часто купує", s.get_frequently_bought())
    show("Слоти доставки", s.get_delivery_slots())

    show("Підготовка checkout (купон c-01 + слот slot-1)",
         s.prepare_checkout(delivery_slot_id="slot-1", coupon_id="c-01"))
