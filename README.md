# Мок Silpo MCP 🛒

Локальний імітатор MCP «Сільпо» для хакатону **AI Factory**. Реалізує набір
інструментів, приблизно відповідний реальному Silpo MCP (пошук товарів,
batch-пошук, кошик, доставка, історія покупок, дієта, родина, купони,
персональні акції, «Власний Рахунок»), але **на фейкових даних** — щоб
розробляти й демонструвати ідею агента без доступу до справжнього MCP організаторів.

> Ідея продукту: **AI Food & Lifestyle Assistant** — агент, який за фото їжі,
> настроєм, look-ом, подією, бюджетом та історією покупок збирає
> персональний гейміфікований кошик у «Сільпо». Цей мок = «Сільпо»-частина;
> свою логіку (Vision, настрій, квести) додаєш зверху як окремий шар/агент.

## Інструменти (MCP tools)

| Інструмент | Що робить |
|---|---|
| `search_products` | Пошук товарів (фільтри: категорія, ціна, тег, наявність) |
| `batch_search_products` | Кілька запитів за раз (усі інгредієнти страви) |
| `get_product` | Деталі товару за id |
| `find_recipe` | Страва → перелік потрібних товарів + орієнтовна сума |
| `get_cart` / `add_to_cart` / `add_many_to_cart` / `remove_from_cart` / `clear_cart` | Робота з кошиком |
| `get_purchase_history` | Історія покупок (online / offline) |
| `get_frequently_bought` | Топ товарів за частотою (проактивні підказки) |
| `get_dietary_restrictions` | Алергії, дієти, нелюбимі продукти |
| `get_family` | Склад родини та їхні дієти |
| `get_coupons` | Доступні купони |
| `get_personal_promotions` | Персональні ціни |
| `get_own_account` | «Власний Рахунок»: баланс, рівень, бали |
| `get_delivery_slots` | Слоти доставки |
| `prepare_checkout` | Готує замовлення **для підтвердження людиною** (не купує сам) |

> ⚠️ `prepare_checkout` навмисно **не завершує покупку** — повертає статус
> `PENDING_HUMAN_CONFIRMATION` та посилання. Це відповідає правилам хакатону:
> checkout підтверджує людина, а не агент.

## Встановлення

Потрібен **Python 3.10+**. Перевір: `python --version`
(якщо не встановлено — постав із <https://python.org> або через `winget install Python.Python.3.12`).

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# або bash:
source .venv/Scripts/activate

pip install -r requirements.txt
```

## Перевірка логіки (без MCP-клієнта)

```bash
python demo.py
```

Пройде сценарій «італійський вечір»: пошук → рецепт → кошик → купон → checkout.

## Запуск як MCP-сервер

```bash
python -m silpo_mcp.server
```

Сервер працює через **stdio** — його підхоплює будь-який MCP-клієнт.

### Інспектор (візуальна перевірка інструментів)

```bash
mcp dev silpo_mcp/server.py
```

### Підключення до Claude Desktop / Cursor / іншого клієнта

Додай у конфіг MCP-клієнта (напр. `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "silpo-mock": {
      "command": "python",
      "args": ["-m", "silpo_mcp.server"],
      "cwd": "D:/GAVNO"
    }
  }
}
```

> Якщо використовуєш venv — вкажи повний шлях до `python` з `.venv`, напр.
> `"command": "D:/GAVNO/.venv/Scripts/python.exe"`.

## Структура

```
silpo_mcp/
  __init__.py
  server.py      # FastMCP-сервер + усі інструменти
  data.py        # фейковий каталог, історія, купони, профіль
demo.py          # димовий тест сценарію
requirements.txt
pyproject.toml   # встановлення пакета + команда silpo-mcp
```

## Що додати зверху (свій шар агента)

Мок покриває «Сільпо»-частину. Для повної ідеї додай окремо:

- **Vision** — розпізнавання страви/look-у з фото → перелік запитів для `batch_search_products`;
- **Mood / текст** — з контексту розмови формуй теги (`tag=` у `search_products`);
- **Гейміфікація** — квести/челенджі поверх `find_recipe` + `get_coupons`;
- **Food persona** — комбінуй `get_purchase_history` + `get_frequently_bought`.
