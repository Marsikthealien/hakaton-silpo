# Сільпо Pack Agent 🧾

Агент, який збирає **паки** — іменовані набори справжніх товарів «Сільпо» — з
твоїх реальних чеків, купонів і акцій, а тоді кладе їх у **справжній кошик**
твого акаунта. Проєкт для хакатону **«Сільпо» AI Factory**.

Все, що бачиш нижче, працює на офіційному MCP `https://mcp.silpo.ua/mcp`.
Моків у репозиторії немає.

## Що агент реально робить

| Дія | Реальні tools «Сільпо» під капотом |
|---|---|
| Розпізнає гостя за чеками, а не за анкетою | `get_my_profile`, `get_my_family`, `get_my_food_restrictions`, `get_my_offline_orders`, `get_loyalty_info` |
| Збирає пак під подію | `find_products_batch` |
| Відтворює пак із чека, підмінюючи те, чого немає | `get_my_offline_orders`, `get_similar_products` |
| Поповнює звичне за циклом покупок | `get_my_offline_orders` + власний розрахунок циклу |
| Бере готовий набір «Сільпо» й лишає тільки акційне | `get_product_sets`, `get_products` |
| Показує, які купони й промо спрацюють саме на цей пак | `get_my_coupons`, `get_my_promos`, `get_loyalty_info` |
| Знаходить, де вигідно взяти дві штуки замість однієї | `specialPrices` у результатах пошуку |
| Міняє позицію на дешевшу або акційну | `get_similar_products` |
| Зберігає пак і дублює його в «Обране» акаунта | `add_or_update_favorite_products` |
| **Кладе пак у справжній кошик** і доводить до оплати | `get_my_shopping_cart`, `create_shopping_cart`, `add_or_update_cart_products`, `get_shopping_cart_by_id` |

Оформлення замовлення агент **не виконує** — доводить до кнопки «Оформити»
й зупиняється. Підтверджує людина.

## Архітектура

```
Qwen (Ollama)
   ↓ MCP
web/  ← Starlette як MCP-хост, власної бізнес-логіки не має
   ↓ MCP (stdio)
silpo_agent_mcp/  ← 19 tools рівня сценарію
profile_mcp/      ← те, чого немає в акаунті «Сільпо»: алергії, факти, нагороди
   ↓ MCP (streamable HTTP + OAuth)
mcp.silpo.ua  ← офіційні 40 tools
```

Навіщо шар `silpo_agent_mcp`: сирі 40 tools вимагають `branchId`, `companyId`,
`timeslot` і довгих ланцюжків викликів — 3B-модель на цьому ламається. Тут вона
дістає 19 інструментів з одним-двома зрозумілими аргументами, а всі справжні
`silpo_*` виклики видно у трейсі (панель «MCP-стрічка» в UI, tool `mcp_trace`).

## Документація

| Документ | Про що |
|---|---|
| [`docs/LOCAL_LLM.md`](docs/LOCAL_LLM.md) | Як підняти проєкт і локальну модель на **Windows**, покроково |
| [`docs/scenarios.html`](docs/scenarios.html) | Усі end-to-end сценарії: що працює, що додаємо, яких tools бракує |
| [`docs/research/`](docs/research/) | Схеми 40 tools MCP і розбір застосунку «Сільпо» — 228 ендпоінтів |

## Запуск

Потрібен **Python 3.10+**.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m silpo_agent_mcp.login          # OAuth у браузері, один раз
python -m uvicorn web.server:app --port 8000
```

Токени лягають у `.mcp/silpo_tokens.json` і далі оновлюються самі через
`refresh_token`. Claude Desktop і `mcp-remote` **не потрібні**.

Чат вимагає локальної моделі:

```bash
ollama pull qwen2.5:3b     # 7b помітно надійніша в tool-calling
```

Без Ollama працює все, крім вільного тексту: паки з чека, поповнення звичного,
набори «Сільпо», оптимізація та кошик — це кнопки, не модель.

## Корисні команди

```bash
python -m silpo_agent_mcp.probe probe_out   # схеми 40 tools + зразки (тільки читання)
python -m silpo_agent_mcp.server            # фасад як окремий stdio MCP-сервер
```

`probe` нічого не змінює: жоден write-tool не викликається.

## Що MCP «Сільпо» не віддає

- **Склад товару.** `get_product_details.attributes` містить країну, ТМ,
  продавця та БЖУ — інгредієнтів немає. Тому алергени ми ловимо за назвою
  («Вафлі Milka Nussini **з фундуком**»), і це чесно позначено в коді.
- **Активацію персональних промо.** `get_my_promos` лише читає, тож агент
  радить, які 1–5 із 10 обрати, а активує людина в застосунку.
- **Оформлення замовлення.** Такого tool немає — і це правильно.

## Структура

```
silpo_agent_mcp/
  auth.py     OAuth 2.1 + PKCE, локальний callback, сховище токенів
  login.py    одноразовий вхід
  silpo.py    клієнт mcp.silpo.ua: сеанс у виділеній задачі + трейс
  context.py  контекст кошика — ключ до 22 з 40 tools
  facade.py   операції рівня продукту
  packs.py    сховище паків
  server.py   MCP-сервер: те, що бачить модель
  probe.py    розвідка схем і форматів
profile_mcp/  профіль, памʼять фактів, тригери, нагороди
web/          MCP-хост (Starlette), tool-loop на Qwen, UI
```
