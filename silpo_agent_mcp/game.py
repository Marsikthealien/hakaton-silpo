"""Грибниця Машрума: рівні, скіни й досягнення з РЕАЛЬНИХ чеків.

Досвід не вигадується й не нараховується за «активність у застосунку» — це
округлені суми чеків із `silpo_get_my_offline_orders`. Тому прогрес не можна
накрутити, і він означає рівно те, що означає: скільки гість витратив.

Відстань між рівнями росте геометрично, як у Minecraft: перший рівень коштує
100 досвіду, кожен наступний на 16% дорожчий. Через це 20-й рівень — це не
вдвічі більше за 10-й, а вшестеро. Рівень перестає бути лічильником і стає
відзнакою.

Грибниця — візуалізація цього прогресу: кожен рівень додає вузол, кожна
категорія з додатною вагою смаку — гілку, кожне досягнення — світну спору.
Тобто картинка малюється з тих самих даних, що й усе інше, а не окремо.

Чого немає в MCP: у застосунку «Сільпо» гейміфікація вже частково є —
`/v1/gamification/balance`, `/v1/achievements/`, `/v1/journeys/reward-instances/`,
колесо фортуни й «Ковбаса фортуни». Але це разові кампанії (`summer_promo_2026`),
а не наскрізний прогрес, і жодного з цих ендпоінтів у 40 tools MCP немає.
Тож наш шар — не дубль застосунку, а те, чого агент не бачить узагалі.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import time

from . import context
from .silpo import SilpoError, silpo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, ".mcp", "game.json")

SPEC_URL = "запропоновано командою Pack Agent для «Сільпо» AI Factory"

# Крива рівнів. 100 досвіду за перший, +16% за кожен наступний.
# 8 966 ₴ за три місяці (реальний акаунт) — це 19-й рівень.
# Значення живуть у demo.py і правляться з вкладки «Під капотом».
def _curve() -> dict:
    from . import demo
    return demo.get("curve")


def _traced(name: str, args: dict):
    started = time.perf_counter()
    return lambda note="": silpo.log_proposed(name, args, started, note=note)


def _load() -> dict:
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("skin", "pecherytsia")
    data.setdefault("claimed", {})       # level -> reward
    data.setdefault("unlocked_at", {})   # achievement id -> ISO
    data.setdefault("flags", {})         # ручні позначки (сімейний пак тощо)
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Крива рівнів
# ---------------------------------------------------------------------------
def need_for(level: int) -> int:
    """Скільки досвіду коштує перехід із `level` на `level + 1`."""
    c = _curve()
    return round(c["base"] * c["growth"] ** (level - 1))


def total_for(level: int) -> int:
    """Скільки досвіду треба всього, щоб опинитись на рівні `level`."""
    return sum(need_for(l) for l in range(1, max(level, 1)))


def level_of(xp: int) -> dict:
    """Рівень за досвідом плюс усе, що потрібно для смужки прогресу."""
    top = _curve()["max_level"]
    level = 1
    while level < top and xp >= total_for(level + 1):
        level += 1
    floor_xp = total_for(level)
    ceil_xp = total_for(level + 1)
    span = max(ceil_xp - floor_xp, 1)
    return {
        "level": level,
        "xp": xp,
        "level_floor_xp": floor_xp,
        "level_ceil_xp": ceil_xp,
        "into_level": xp - floor_xp,
        "need_for_next": max(ceil_xp - xp, 0),
        "progress": round(min((xp - floor_xp) / span, 1.0), 3),
    }


# ---------------------------------------------------------------------------
# Скіни
# ---------------------------------------------------------------------------
# Кожні 10 рівнів — новий вигляд Машрума. Плюс два скіни за досягнення:
# їх не можна купити витратами, лише зробити щось конкретне.
SKINS = [
    {"id": "pecherytsia", "title": "Печериця", "level": 1,
     "cap": "#E8D8C4", "stem": "#F5EFE6",
     "about": "Базовий Машрум. Усі починають звідси."},
    {"id": "lysychka", "title": "Лисичка", "level": 10,
     "cap": "#F0A03C", "stem": "#FBE3C2",
     "about": "Руда шапка. Видно здалеку."},
    {"id": "borovyk", "title": "Боровик у краватці", "level": 20,
     "cap": "#8B5A2B", "stem": "#EBD9C3",
     "about": "Статусний гриб. Краватка не знімається."},
    {"id": "tryufel", "title": "Трюфель", "level": 30,
     "cap": "#3A2E2A", "stem": "#6E5B52",
     "about": "Дорого, темно, пахне лісом."},
    {"id": "veselka", "title": "Веселка", "level": 40,
     "cap": "#7A46D6", "stem": "#D9C6F7",
     "about": "Світиться в темряві складу."},
    {"id": "grybnytsia", "title": "Грибниця", "level": 50,
     "cap": "#12805A", "stem": "#8FD9BE",
     "about": "Уже не гриб, а вся мережа."},
    {"id": "turyst", "title": "Сільпо-турист", "level": None,
     "cap": "#2B5CE6", "stem": "#C9D8FB", "achievement": "themed_all",
     "about": "За обхід усіх тематичних «Сільпо». Витратами не купується."},
    {"id": "kuponnyk", "title": "Купонний детектив", "level": None,
     "cap": "#D01C3C", "stem": "#F7C3CE", "achievement": "coupon_hunter",
     "about": "За десять спрацьованих купонів."},
]


def _skin(skin_id: str) -> dict:
    return next((s for s in SKINS if s["id"] == skin_id), SKINS[0])


# ---------------------------------------------------------------------------
# Нагороди за рівні
# ---------------------------------------------------------------------------
# Що вищий рівень — то кращий промокод. Кожні 5 рівнів.
# Коди генеруємо ми: у MCP «Сільпо» є `silpo_get_promo_codes` лише на читання,
# tool на видачу немає — саме його ми й пропонуємо. Перелік редагується
# з «Під капотом» (silpo_agent_mcp/demo.py).
def _rewards() -> list[dict]:
    from . import demo
    return demo.get("rewards")


def _reward_for(level: int) -> dict | None:
    return next((r for r in _rewards() if r["level"] == level), None)


def _code_for(level: int) -> str:
    return f"MUSHROOM-L{level:02d}"


# ---------------------------------------------------------------------------
# Тематичні «Сільпо»
# ---------------------------------------------------------------------------
# Магазини й теми СПРАВЖНІ: узяті з пресрелізів мережі, `external_id` звірено
# з `silpo_list_branches` (він же `filId` у чеках). Немає в API лише самої
# прив'язки «філія → концепція», і зібрати її руками для 60+ дизайнерських
# супермаркетів неможливо — тому й потрібен `silpo_get_themed_branches`.
def _themed() -> list[dict]:
    from . import demo
    return demo.get("themed")


# ---------------------------------------------------------------------------
# Чеки — джерело досвіду
# ---------------------------------------------------------------------------
_CACHE: dict = {"at": 0.0, "orders": []}
CACHE_TTL = 120


async def all_receipts(force: bool = False) -> list[dict]:
    """Усі чеки гостя, а не перші 10: досвід рахується за всю історію.

    `silpo_get_my_offline_orders` віддає максимум 10 за виклик, зате приймає
    `offset` — тож гортаємо до кінця й тримаємо результат у памʼяті дві хвилини,
    щоб кожна вкладка UI не смикала API по шість разів.
    """
    if not force and _CACHE["orders"] and time.time() - _CACHE["at"] < CACHE_TTL:
        return _CACHE["orders"]
    await context.ensure()
    ctx = context.search_ctx()
    orders: list[dict] = []
    for offset in range(0, 200, 10):
        page = await silpo.call("silpo_get_my_offline_orders",
                                {**ctx, "limit": 10, "offset": offset})
        chunk = page.get("orders") or []
        orders += chunk
        if len(chunk) < 10:
            break
    _CACHE.update({"at": time.time(), "orders": orders})
    return orders


def xp_of(orders: list[dict]) -> int:
    """Досвід = сума округлених чеків. Гривня = очко, без коефіцієнтів."""
    return int(sum(round(o.get("sumReg") or 0) for o in orders))


# ---------------------------------------------------------------------------
# Досягнення
# ---------------------------------------------------------------------------
def _stats(orders: list[dict]) -> dict:
    """Усе, що потрібно досягненням, — одним проходом по чеках."""
    from .proposed import _aisle_of

    filials, categories, weeks = set(), set(), set()
    night = early = bagless = big = 0
    rewards = 0
    reward_uah = 0.0
    discount = 0.0
    lines = 0
    for order in orders:
        filials.add(str(order.get("filId")))
        stamp = order.get("createdAt") or ""
        if len(stamp) >= 13:
            hour = int(stamp[11:13])
            night += hour >= 22 or hour < 5
            early += 5 <= hour < 9
        if len(stamp) >= 10:
            day = dt.date.fromisoformat(stamp[:10])
            weeks.add(day.isocalendar()[:2])
        products = order.get("products") or []
        lines += len(products)
        if not any("пакет" in (p.get("name") or "").lower() for p in products):
            bagless += 1
        if (order.get("sumReg") or 0) >= 1000:
            big += 1
        for line in products:
            categories.add(_aisle_of(line.get("name") or "")[0])
        for reward in order.get("rewards") or []:
            rewards += 1
            reward_uah += reward.get("applyRewardAmount") or 0
        discount += order.get("sumDiscount") or 0

    # найдовша серія тижнів поспіль
    ordered = sorted(weeks)
    streak = best = 0
    previous = None
    for week in ordered:
        monday = dt.date.fromisocalendar(week[0], week[1], 1)
        streak = streak + 1 if previous and (monday - previous).days == 7 else 1
        best = max(best, streak)
        previous = monday

    return {"orders": len(orders), "filials": filials, "categories": categories,
            "night": night, "early": early, "bagless": bagless, "big": big,
            "rewards": rewards, "reward_uah": round(reward_uah, 2),
            "discount": round(discount, 2), "lines": lines, "week_streak": best}


# (id, назва, пояснення, ціль, як рахувати) — прогрес завжди число/число,
# щоб UI малював смужку, а не «так/ні».
def _achievement_rows(stats: dict, level: int, extra: dict) -> list[dict]:
    themed_hit = extra["themed_visited"]
    return [
        {"id": "first_cheque", "title": "Перша ходка",
         "about": "Один чек у «Сільпо» — і грибниця проросла.",
         "have": min(stats["orders"], 1), "target": 1, "icon": "sprout"},
        {"id": "themed_all", "title": "Відвідати всі тематичні «Сільпо»",
         "about": "Магазини-концепції по всій країні. За повний обхід — скін «Сільпо-турист».",
         "have": len(themed_hit), "target": len(_themed()), "icon": "compass",
         "reward": "скін «Сільпо-турист» + закрита дегустація"},
        {"id": "wanderer", "title": "Мандрівник",
         "about": "Пʼять різних філій. Не всі ходять далі свого дому.",
         "have": len(stats["filials"]), "target": 5, "icon": "map"},
        {"id": "omnivore", "title": "Всеїдний",
         "about": "Покупки з 15 різних розділів каталогу.",
         "have": len(stats["categories"]), "target": 15, "icon": "pan"},
        {"id": "thousandaire", "title": "Тисячник",
         "about": "Чек на 1000 ₴ і більше.",
         "have": min(stats["big"], 1), "target": 1, "icon": "wallet"},
        {"id": "night_shift", "title": "Нічна зміна",
         "about": "Покупка після 22:00. Машрум не спить теж.",
         "have": min(stats["night"], 1), "target": 1, "icon": "moon"},
        {"id": "early_bird", "title": "Рання пташка",
         "about": "Покупка до 9:00.",
         "have": min(stats["early"], 1), "target": 1, "icon": "sun"},
        {"id": "zero_waste", "title": "Без пакета",
         "about": "Три чеки, у яких немає жодного пакета.",
         "have": stats["bagless"], "target": 3, "icon": "leaf"},
        {"id": "coupon_hunter", "title": "Купонний детектив",
         "about": "Десять спрацьованих купонів. За це — скін «Купонний детектив».",
         "have": stats["rewards"], "target": 10, "icon": "ticket",
         "reward": "скін «Купонний детектив»"},
        {"id": "saver", "title": "Ощадливий",
         "about": "Тисяча гривень знижок сумарно.",
         "have": int(stats["discount"]), "target": 1000, "icon": "tag"},
        {"id": "streak_4", "title": "Постійник",
         "about": "Чотири тижні поспіль із покупкою.",
         "have": stats["week_streak"], "target": 4, "icon": "calendar"},
        {"id": "taster", "title": "Дегустатор",
         "about": "Двадцять свайпів у «Департаменті дивинок».",
         "have": extra["swipes"], "target": 20, "icon": "swipe"},
        {"id": "mycologist", "title": "Міколог",
         "about": "Двадцятий рівень грибниці.",
         "have": level, "target": 20, "icon": "mushroom"},
        {"id": "family_table", "title": "Родинний стіл",
         "about": "Зібрати пак, у якому враховано смаки всієї родини.",
         "have": int(bool(extra["flags"].get("family_pack"))), "target": 1, "icon": "family"},
    ]


def _themed_visited(orders: list[dict]) -> list[dict]:
    seen = {str(o.get("filId")) for o in orders}
    return [t for t in _themed() if t["external_id"] in seen]


def mycelium(level: int, achievements_done: int) -> dict:
    """Дані для картинки грибниці — рахуються, а не малюються навмання.

    Вузол на кожен рівень, гілка на кожну категорію з додатною вагою смаку,
    спора на кожне закрите досягнення. Одна й та сама історія покупок дає одну
    й ту саму грибницю — вона впізнавана, як обличчя.
    """
    from . import weights as tastes

    snapshot = tastes.snapshot(limit=40)
    strands = [{"title": c["title"], "weight": c["weight"], "slug": c["slug"]}
               for c in snapshot["categories"] if c["weight"] > 0][:8]
    return {
        "nodes": level,
        "strands": strands,
        "spores": achievements_done,
        "vigour": round(min(level / _curve()["max_level"], 1.0), 3),
        "note": ("Вузол на рівень, гілка на улюблену категорію, спора на "
                 "досягнення. Грибниця росте лише від реальних чеків."),
    }


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
async def game_profile() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Рівень, досвід, скін і грибниця гостя.

    Досвід — округлені суми РЕАЛЬНИХ чеків, тож накрутити його не можна.
    Крива рівнів геометрична: кожен наступний рівень на 16% дорожчий за
    попередній, як у Minecraft.
    """
    done = _traced("silpo_get_game_profile", {})
    orders = await all_receipts()
    xp = xp_of(orders)
    state = level_of(xp)
    data = _load()
    stats = _stats(orders)
    themed_hit = _themed_visited(orders)

    from .proposed import _load as proposed_load
    swipes = len((proposed_load().get("swipes") or {}))
    rows = _achievement_rows(stats, state["level"], {
        "themed_visited": themed_hit, "swipes": swipes, "flags": data["flags"]})
    done_ids = {r["id"] for r in rows if r["have"] >= r["target"]}

    unlocked = [s for s in SKINS
                if (s.get("level") is not None and state["level"] >= s["level"])
                or (s.get("achievement") in done_ids)]
    current = _skin(data["skin"])
    if current["id"] not in {s["id"] for s in unlocked}:
        current = SKINS[0]

    tiers = _rewards()
    pending = [t for t in tiers
               if t["level"] <= state["level"] and str(t["level"]) not in data["claimed"]]
    next_tier = next((t for t in tiers if t["level"] > state["level"]), None)

    done(f"рівень {state['level']}, {xp} XP")
    return {
        **state,
        "receipts_counted": len(orders),
        "spent_uah": round(sum(o.get("sumReg") or 0 for o in orders), 2),
        "skin": current,
        "skins_unlocked": [s["id"] for s in unlocked],
        "skins_total": len(SKINS),
        "next_skin": next((s for s in SKINS
                           if s.get("level") and s["level"] > state["level"]), None),
        "achievements_done": len(done_ids),
        "achievements_total": len(rows),
        "mycelium": mycelium(state["level"], len(done_ids)),
        "rewards_ready": [{**t, "code": _code_for(t["level"])} for t in pending],
        "next_reward": ({**next_tier, "levels_away": next_tier["level"] - state["level"]}
                        if next_tier else None),
        "claimed": data["claimed"],
        "curve": {**_curve(), "need_for_next": state["need_for_next"],
                  "explain": f"кожен рівень на {round((_curve()['growth'] - 1) * 100)}% дорожчий"},
        "proposed": True,
        "silpo_native": ("У застосунку вже є /v1/gamification/balance, /v1/achievements/ "
                         "та /v1/journeys/reward-instances/ — але це разові кампанії "
                         "(summer_promo_2026), і жодного з них немає в 40 tools MCP."),
        "spec": ("Наскрізний прогрес за чеками: досвід, рівні, скіни, досягнення. "
                 "«Сільпо» вже має і дані (чеки), і механіку (ачівки кампаній) — "
                 "бракує лише постійної шкали й доступу до неї агентові. " + SPEC_URL),
    }


async def achievements() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Досягнення гостя — усі, з прогресом по кожному.

    Рахуються з чеків, а не зі спеціальних подій: «Мандрівник» — це різні
    `filId` у чеках, «Всеїдний» — різні розділи каталогу серед куплених позицій.
    """
    done = _traced("silpo_get_achievements", {})
    orders = await all_receipts()
    data = _load()
    state = level_of(xp_of(orders))
    stats = _stats(orders)
    themed_hit = _themed_visited(orders)
    from .proposed import _load as proposed_load
    swipes = len((proposed_load().get("swipes") or {}))

    rows = _achievement_rows(stats, state["level"], {
        "themed_visited": themed_hit, "swipes": swipes, "flags": data["flags"]})
    now = dt.datetime.now().isoformat(timespec="seconds")
    changed = False
    for row in rows:
        row["done"] = row["have"] >= row["target"]
        row["progress"] = round(min(row["have"] / max(row["target"], 1), 1.0), 3)
        row["have"] = min(row["have"], row["target"])
        if row["done"] and row["id"] not in data["unlocked_at"]:
            data["unlocked_at"][row["id"]] = now
            changed = True
        row["unlocked_at"] = data["unlocked_at"].get(row["id"])
    if changed:
        _save(data)

    rows.sort(key=lambda r: (r["done"], -r["progress"]))
    done(f"{sum(r['done'] for r in rows)}/{len(rows)}")
    return {
        "done": sum(r["done"] for r in rows), "total": len(rows),
        "achievements": rows,
        "themed": {"visited": themed_hit, "total": len(_themed()),
                   "left": [t for t in _themed() if t not in themed_hit]},
        "proposed": True,
        "spec": ("Ачівки в застосунку прив'язані до кампанії (summer_promo_2026) і "
                 "згорають разом із нею. Постійні досягнення рахуються з тих самих "
                 "чеків і не потребують жодних нових даних. " + SPEC_URL),
    }


async def themed_branches() -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Тематичні «Сільпо» й де гість уже був.

    `silpo_list_branches` віддає місто, адресу й координати — концепції магазину
    там немає. Філії тут справжні (externalId звіряється з `filId` у чеках),
    а теми — наші демо-дані: саме їх і мав би віддавати «Сільпо».
    """
    done = _traced("silpo_get_themed_branches", {})
    orders = await all_receipts()
    seen = {str(o.get("filId")) for o in orders}
    rows = [{**t, "visited": t["external_id"] in seen} for t in _themed()]
    done(f"{sum(r['visited'] for r in rows)}/{len(rows)}")
    return {
        "total": len(rows), "visited": sum(r["visited"] for r in rows),
        "branches": rows, "proposed": True, "themes_are_demo": True,
        "spec": ("Концепція магазину — поле, якого немає ні в списку філій, ні в "
                 "картці магазину. Без нього агент не може ані побудувати обхід "
                 "тематичних «Сільпо», ані пояснити, чим цей магазин особливий. "
                 "Філії справжні, теми — наші демо-дані. " + SPEC_URL),
    }


async def claim_level_reward(level: int | None = None) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Забрати промокод за досягнутий рівень.

    Що вищий рівень, то кращий код. `silpo_get_promo_codes` уміє лише читати —
    tool на видачу коду за прогрес і є те, чого бракує.
    """
    done = _traced("silpo_claim_level_reward", {"level": level})
    orders = await all_receipts()
    state = level_of(xp_of(orders))
    data = _load()
    ready = [t["level"] for t in _rewards()
             if t["level"] <= state["level"] and str(t["level"]) not in data["claimed"]]
    target = level if level in ready else (ready[0] if ready else None)
    if target is None:
        next_tier = next((t for t in _rewards() if t["level"] > state["level"]), None)
        done("нема чого забирати")
        return {"granted": None, "level": state["level"],
                "reason": ("усі нагороди за досягнуті рівні вже забрані"
                           if ready == [] else "цей рівень ще не досягнуто"),
                "next": next_tier, "proposed": True}
    reward = {**_reward_for(target), "code": _code_for(target),
              "granted_at": dt.datetime.now().isoformat(timespec="seconds")}
    data["claimed"][str(target)] = reward
    _save(data)
    done(f"L{target}: {reward['title']}")
    return {"granted": reward, "level": state["level"], "proposed": True,
            "note": "Код наш: у MCP «Сільпо» немає tool на видачу промокоду за прогрес.",
            "spec": SPEC_URL}


async def set_skin(skin_id: str) -> dict:
    """ЗАПРОПОНОВАНИЙ tool. Обрати вигляд Машрума серед відкритих."""
    done = _traced("silpo_set_skin", {"skin_id": skin_id})
    profile = await game_profile()
    if skin_id not in profile["skins_unlocked"]:
        done("заблоковано")
        return {"error": f"Скін «{_skin(skin_id)['title']}» ще не відкрито.",
                "unlocked": profile["skins_unlocked"]}
    data = _load()
    data["skin"] = skin_id
    _save(data)
    done(_skin(skin_id)["title"])
    return {"skin": _skin(skin_id), "proposed": True}


async def skins() -> dict:
    """Усі скіни Машрума: які відкриті, які ні й що для цього треба."""
    profile = await game_profile()
    unlocked = set(profile["skins_unlocked"])
    rows = []
    for skin in SKINS:
        how = (f"рівень {skin['level']}" if skin.get("level")
               else f"досягнення «{skin.get('achievement')}»")
        rows.append({**skin, "unlocked": skin["id"] in unlocked,
                     "current": skin["id"] == profile["skin"]["id"], "how": how})
    return {"skins": rows, "level": profile["level"], "proposed": True}


def mark(flag: str, value: bool = True) -> dict:
    """Позначка для досягнень, які не видно з чеків (напр. сімейний пак)."""
    data = _load()
    data["flags"][flag] = value
    _save(data)
    return {"flag": flag, "value": value}


def level_table(upto: int = 30) -> dict:
    """Таблиця рівнів — щоб криву було видно, а не тільки обіцяно."""
    return {"levels": [{"level": l, "need": need_for(l), "total": total_for(l),
                        "reward": _reward_for(l),
                        "skin": next((s["title"] for s in SKINS
                                      if s.get("level") == l), None)}
                       for l in range(1, upto + 1)],
            **_curve()}
