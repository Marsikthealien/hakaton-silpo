"""Демо-дані в одному місці — і редаговані з інтерфейсу.

Частина фіч агента імітує те, чого MCP «Сільпо» не віддає: концепції магазинів,
промокоди за прогрес, умови «Плюхс». Ховати це нечесно, а зашивати в код —
незручно: на демо часто треба поміняти число за півхвилини до показу.

Тому кожен такий набір живе тут: має типізовану схему, значення за замовчуванням
і файл у `.mcp/demo.json`, який можна правити з вкладки «Під капотом».
Значення за замовчуванням лишаються в коді — «Скинути» повертає їх завжди.
"""

from __future__ import annotations

import copy
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, ".mcp", "demo.json")


# ---------------------------------------------------------------------------
# Дизайнерські «Сільпо»
# ---------------------------------------------------------------------------
# Це РЕАЛЬНІ магазини: тема й адреса — з пресрелізів мережі, `external_id`
# звірено з `silpo_list_branches` (він же `filId` у чеках). У мережі понад 60
# дизайнерських супермаркетів; зіставити всі вручну неможливо — саме тому
# потрібен `silpo_get_themed_branches`. Тут — ті, які вдалось підтвердити
# джерелом і знайти серед 455 філій.
THEMED_DEFAULT = [
    {"external_id": "2734", "city": "Київ", "address": "просп. Оболонський, 1Б",
     "theme": "Спортивний Dream Town",
     "about": "Блок А оновленого Dream Town, оформлений у спортивній стилістиці",
     "source": "https://rau.ua/novyni/silpo-dream-town/"},
    {"external_id": "3361", "city": "Київ", "address": "вул. Березнева, 12А",
     "theme": "S.T.A.L.K.E.R.",
     "about": "Зона біля ЖК «Комфорт Таун»: концепт за грою GSC Game World",
     "source": "https://bzh.life/ua/mesta-i-veshi/silpo-stalker-komfort-taun/"},
    {"external_id": "2000", "city": "Київ", "address": "вул. Закревського Миколи, 61/2",
     "theme": "Тихоокеанська тики",
     "about": "ТРЦ ZakrevSky, цілодобово: культура тики й тропічна різьба",
     "source": "https://www.ucsc.org.ua/tyhookeanska-kultura-tyky-ta-myakyj-kvilt-silpo-vidkryv-dva-novi-dyzajnerski-supermarkety/"},
    {"external_id": "3252", "city": "Київ", "address": "вул. Олеся Бердника, 1-Г",
     "theme": "Світ Задзеркалля",
     "about": "Авангард: закільцьований лабіринт із декоративними проходами й нішами",
     "source": "https://www.ucsc.org.ua/u-kyyevi-vidkryvsya-dyzajnerskyj-silpo-u-styli-svit-zadzerkallya-foto/"},
    {"external_id": "4162", "city": "Київ", "address": "вул. Верхогляда, 24",
     "theme": "Спогади про Печерськ",
     "about": "Новопечерські Липки: кожен куточок — тепла згадка про Печерськ",
     "source": "https://rau.ua/news/merezha-silpo-vidkrila-novij-dizajnerskij-supermarket-v-kiievi-nathnenij-istoriieju-pecherska/"},
    {"external_id": "2941", "city": "Київ", "address": "вул. Глибочицька, 32Б",
     "theme": "Муркотиковий",
     "about": "Концептуальний котячий супермаркет",
     "source": "https://rau.ua/novyni/vidkrittya/murkotykovyj-market-silpo/"},
    {"external_id": "3190", "city": "Бориспіль", "address": "вул. Київський Шлях, 67",
     "theme": "Квілт",
     "about": "ТРЦ Park Town: клаптикове шиття як тема всього залу",
     "source": "https://www.ucsc.org.ua/tyhookeanska-kultura-tyky-ta-myakyj-kvilt-silpo-vidkryv-dva-novi-dyzajnerski-supermarkety/"},
    {"external_id": "3117", "city": "Львів", "address": "вул. Антоновича, 122",
     "theme": "Кіберкультура з NAVI",
     "about": "ТРЦ «Вертикаль»: від перших компʼютерів до кіберкору, у колаборації з NAVI",
     "source": "https://www.ucsc.org.ua/u-kolaboracziyi-z-navi-u-lvovi-vidkryvsya-dyzajnerskyj-silpo-v-styli-kibersportu-foto/"},
    {"external_id": "3949", "city": "Полтава", "address": "пл. Павленківська, 3",
     "theme": "Петрогліфи",
     "about": "Новий блок ТРК «Київ»: наскельний живопис на стінах залу",
     "source": "https://www.ucsc.org.ua/dyzajnerskyj-silpo-vidkryvsya-u-novomu-bloczi-poltavskogo-trcz-kyyiv/"},
]

# Нагороди за рівні. Коди наші: `silpo_get_promo_codes` уміє лише читати.
REWARDS_DEFAULT = [
    {"level": 5,  "title": "-5% на будь-який пак",                 "kind": "знижка"},
    {"level": 10, "title": "-7% + безкоштовна доставка від 500 ₴",  "kind": "знижка"},
    {"level": 15, "title": "-10% на «Власний Рахунок»",             "kind": "знижка"},
    {"level": 20, "title": "x2 балобонуси на тиждень",              "kind": "балобонуси"},
    {"level": 25, "title": "-12% на будь-який пак",                 "kind": "знижка"},
    {"level": 30, "title": "x3 балобонуси на тиждень",              "kind": "балобонуси"},
    {"level": 35, "title": "-15% на будь-який пак",                 "kind": "знижка"},
    {"level": 40, "title": "місяць «Плюхс» у подарунок",            "kind": "підписка"},
    {"level": 45, "title": "-15% + доставка за 1 ₴",                "kind": "знижка"},
    {"level": 50, "title": "Ексклюзив: закрита дегустація",         "kind": "ексклюзив"},
]

# Умови «Плюхс» — зі сторінки silpo.ua/subscription. У MCP їх немає взагалі:
# tool каже лише «є підписка чи ні».
PLUS_DEFAULT = {"price_uah": 199.0, "cashback": 0.10, "free_delivery_from_uah": 500.0}

# Крива рівнів. Тримаємо тут, бо це головна ручка налаштування балансу.
CURVE_DEFAULT = {"base": 100, "growth": 1.16, "max_level": 60}


SETS: dict[str, dict] = {
    "themed": {
        "title": "Дизайнерські «Сільпо»",
        "why": ("Магазини й адреси справжні, звірені з `silpo_list_branches`. "
                "Але концепції магазину в API немає ЖОДНОЇ — ми зібрали ці "
                "дев'ять руками з пресрелізів, а в мережі їх понад 60."),
        "default": THEMED_DEFAULT,
    },
    "rewards": {
        "title": "Нагороди за рівні",
        "why": ("Промокоди генеруємо ми. `silpo_get_promo_codes` уміє лише "
                "читати — tool на видачу коду за прогрес і є те, чого бракує."),
        "default": REWARDS_DEFAULT,
    },
    "plus": {
        "title": "Умови «Плюхс»",
        "why": ("MCP каже лише «є підписка чи ні». Ані ціни, ані відсотка "
                "кешбеку, ані порогу доставки tool не віддає."),
        "default": PLUS_DEFAULT,
    },
    "curve": {
        "title": "Крива рівнів грибниці",
        "why": ("Наша механіка. `base` — ціна першого рівня в гривнях чеків, "
                "`growth` — у скільки разів дорожчає кожен наступний."),
        "default": CURVE_DEFAULT,
    },
}

# Файли, які агент наповнює сам під час роботи. Їх теж видно й можна чистити,
# але схеми в них немає — це накопичений стан, а не налаштування.
STATE_FILES = {
    "proposed": ("Стан запропонованих tools", "proposed.json",
                 "комора, самопочуття, свайпи, вподобання родини, сімейні рецепти"),
    "weights": ("Ваги смаку", "weights.json",
                "накопичуються з чеків і свайпів; «Перерахувати» будує заново"),
    "game": ("Стан грибниці", "game.json",
             "обраний скін, забрані нагороди, дати відкриття досягнень"),
    "packs": ("Збережені паки", "packs.json", "усе, що зібрав агент"),
}


# Крива рівнів читається на КОЖЕН рівень у total_for(), тож без кешу один показ
# грибниці — це сотні читань файлу. Кеш скидається за mtime.
_CACHE: dict = {"mtime": None, "data": None}


def _load() -> dict:
    try:
        mtime = os.path.getmtime(STORE_PATH)
    except OSError:
        mtime = None
    if _CACHE["data"] is not None and _CACHE["mtime"] == mtime:
        return _CACHE["data"]
    try:
        with open(STORE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    _CACHE.update({"mtime": mtime, "data": data})
    return data


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE_PATH), exist_ok=True)
    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        _CACHE.update({"mtime": os.path.getmtime(STORE_PATH), "data": data})
    except OSError:
        _CACHE.update({"mtime": None, "data": data})


def get(name: str):
    """Поточне значення набору: правлене з UI або з коду."""
    if name not in SETS:
        raise KeyError(name)
    stored = _load().get(name)
    return copy.deepcopy(stored if stored is not None else SETS[name]["default"])


def put(name: str, value) -> dict:
    """Записати нове значення набору. Повертає його ж — уже застосоване."""
    if name not in SETS:
        return {"error": f"Немає набору «{name}». Є: {', '.join(SETS)}."}
    data = _load()
    data[name] = value
    _save(data)
    return {"set": name, "value": value, "edited": True}


def reset(name: str) -> dict:
    """Повернути значення з коду."""
    if name not in SETS:
        return {"error": f"Немає набору «{name}»."}
    data = _load()
    data.pop(name, None)
    _save(data)
    return {"set": name, "value": get(name), "edited": False}


def catalogue() -> dict:
    """Усі демо-дані: що це, чому вони наші й чи їх уже правили."""
    edited = _load()
    return {
        "sets": [{"name": name, "title": meta["title"], "why": meta["why"],
                  "edited": name in edited, "value": get(name)}
                 for name, meta in SETS.items()],
        "state_files": [{"name": key, "title": title, "file": f".mcp/{fname}",
                         "about": about,
                         "exists": os.path.exists(os.path.join(ROOT, ".mcp", fname)),
                         "size": (os.path.getsize(os.path.join(ROOT, ".mcp", fname))
                                  if os.path.exists(os.path.join(ROOT, ".mcp", fname)) else 0)}
                        for key, (title, fname, about) in STATE_FILES.items()],
        "note": ("Це ВСІ демо-дані проєкту. Решта — справжні відповіді "
                 "mcp.silpo.ua. Значення за замовчуванням лежать у коді "
                 "(silpo_agent_mcp/demo.py), тож «Скинути» працює завжди."),
    }


def clear_state(name: str) -> dict:
    """Видалити накопичений стан — щоб перевірити сценарій «з нуля»."""
    if name not in STATE_FILES:
        return {"error": f"Немає стану «{name}»."}
    path = os.path.join(ROOT, ".mcp", STATE_FILES[name][1])
    existed = os.path.exists(path)
    if existed:
        os.remove(path)
    return {"state": name, "removed": existed}
