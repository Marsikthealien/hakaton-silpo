# Розвідка

Матеріали, зібрані під час аналізу — щоб не перепроходити той самий шлях двічі.

| Файл | Що це |
|---|---|
| `silpo_mcp_tools.json` | Повні схеми всіх 40 tools офіційного MCP «Сільпо». Знято через `python -m silpo_agent_mcp.probe` |
| `app_endpoints.txt` | 228 HTTP-ендпоінтів, які використовує застосунок «Сільпо». Витягнуто з `libapp.so` (Flutter) |
| `app_features.txt` | 79 розділів інтерфейсу застосунку з кількістю рядків у кожному — фактично перелік усіх його можливостей |

## Головний висновок

MCP віддає 40 інструментів. Застосунок ходить у 228 ендпоінтів. Сім речей, яких
нам бракувало, у «Сільпо» **вже написані** — просто не відкриті через MCP:

```
/v1/my/promos/select                       активація персональних промо
/v1/delivery-calculator/branches/          калькулятор доставки
/v1/recipes/                               рецепти
/v1/uk/recommendations/basket/sets         «що беруть із цим»
/v1/configs/cheque-department-priorities   порядок відділів у чеку
/v1/loyalty/my/cheque-info-for-repeat-order повтор замовлення з чека
/v1/profile/my/segments                    сегменти гостя
```

Тому наш запит до «Сільпо» — не «побудуйте», а «відкрийте».

## Як оновити

```bash
python -m silpo_agent_mcp.probe probe_out     # схеми tools + зразки відповідей
```

Розбір APK робився вручну: `unzip base.apk`, далі `strings libapp.so` для
ендпоінтів і `assets/flutter_assets/assets/translations/uk.json` для інтерфейсу.
Сам файл перекладів у репозиторій не кладемо — це чужий ресурс.
