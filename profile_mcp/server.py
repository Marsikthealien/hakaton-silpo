"""Profile & Memory MCP — шар персоналізації для AI Food Assistant.

Зберігає профіль користувача (онбординг), памʼять фактів із розмов,
проактивні тригери та нагороди за ігри. Усе персистентно у JSON-файлі
(profile_data.json поруч із проєктом), тож дані переживають перезапуск —
саме тому асистент «наступного разу згадає».

Цей сервер працює ПОРУЧ із silpo / silpo-mock: він не шукає товари сам, а дає
агенту контекст про людину, щоб персоналізувати рекомендації та ігри.

Запуск (stdio):
    python -m profile_mcp.server
    python profile_mcp/server.py   # теж працює (fallback-імпорт не потрібен — self-contained)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Optional

try:
    from mcp.server.mcpserver import MCPServer as _Server  # mcp 2.x
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP as _Server  # mcp 1.x
    except ImportError as exc:  # pragma: no cover
        raise SystemExit(
            "Не знайдено пакет 'mcp'. Встанови: pip install \"mcp[cli]\""
        ) from exc

mcp = _Server(
    "profile",
    instructions=(
        "MCP персоналізації для Food Assistant. Спочатку виклич get_profile: якщо "
        "профіль порожній — проведи онбординг (onboarding_questions) і збережи через "
        "update_profile. Памʼятай важливі факти з розмови через remember_fact "
        "(улюблений фільм, події, уподобання). Перед рекомендаціями враховуй "
        "allergies/dislikes/diets. Періодично виклик check_triggers дає проактивні "
        "підказки (напр. новинка за улюбленим фільмом). Нагороди за ігри — grant_reward. "
        "Товари й ціни бери з сервера silpo; цей сервер лише про людину."
    ),
)

# ---------------------------------------------------------------------------
# Персистентне сховище (JSON поруч із проєктом)
# ---------------------------------------------------------------------------
_STORE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profile_data.json")
)

_DEFAULT_PROFILE = {
    "name": None,
    "likes": [],          # улюблені продукти / страви / кухні
    "dislikes": [],       # не любить
    "allergies": [],      # алергії (жорстке виключення)
    "diets": [],          # напр. "веганське", "без глютену", "вегетаріанське"
    "relationship": None, # "single" / "relationship" / "married"
    "family": [],         # [{"name":..., "role":..., "age":..., "diets":[...]}]
    "hobbies": [],        # напр. "спорт", "кіно", "малювання"
    "interests": [],      # улюблені фільми/ігри/музика — джерело проактивних тригерів
    "budget_pref": None,  # "low" / "medium" / "high" або число (грн на кошик)
    "bonus_first": False, # тумблер: спершу пропонувати те, на що діє знижка чи бонуси
    "equipment": [],      # техніка на кухні: сковорідка, духовка, аерогриль…
}


def _empty_store() -> dict:
    return {"profile": dict(_DEFAULT_PROFILE), "facts": [], "rewards": []}


def _load() -> dict:
    if not os.path.exists(_STORE_PATH):
        return _empty_store()
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return _empty_store()
    # доповнюємо відсутні ключі профілю (сумісність зі старим файлом)
    base = _empty_store()
    base.update({k: v for k, v in data.items() if k in base})
    prof = dict(_DEFAULT_PROFILE)
    prof.update(data.get("profile", {}))
    base["profile"] = prof
    base["facts"] = data.get("facts", [])
    base["rewards"] = data.get("rewards", [])
    return base


def _save(store: dict) -> None:
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _sid() -> str:
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Проактивні тригери (data-driven правила)
# ---------------------------------------------------------------------------
# Кожне правило: якщо у профілі/фактах трапляється одне з keywords —
# формуємо проактивну підказку з готовим запитом до silpo.
_TRIGGER_RULES = [
    {
        "keywords": ["фільм", "кіно", "серіал", "movie", "netflix", "марвел", "comics", "комікс"],
        "kind": "movie_night",
        "message": "Улюблене кіно на радарі — може, вечір перед екраном? Зберемо снеки.",
        "silpo_query": "снеки для кіно попкорн",
    },
    {
        "keywords": ["спорт", "фітнес", "зал", "біг", "тренуванн", "gym", "workout"],
        "kind": "sport",
        "message": "Ти в темі спорту — підкину білкові опції для відновлення.",
        "silpo_query": "протеїн куряче філе йогурт",
    },
    {
        "keywords": ["малюв", "художник", "арт", "draw", "art", "скетч"],
        "kind": "art_game",
        "message": "Ти любиш малювати — є гра «намалюй продукт і отримай знижку».",
        "silpo_query": None,
        "game": "draw_to_discount",
    },
    {
        "keywords": ["кава", "coffee", "еспресо", "лате"],
        "kind": "coffee",
        "message": "Кавоман — глянь персональну ціну на каву.",
        "silpo_query": "кава мелена",
    },
    {
        "keywords": ["вечірк", "party", "друз", "гост"],
        "kind": "party",
        "message": "Схоже, збираєш компанію — підготую набір для вечірки.",
        "silpo_query": "снеки напої вечірка",
    },
]


def _text_pool(store: dict) -> str:
    """Весь текст профілю+фактів у нижньому регістрі — для матчингу тригерів."""
    prof = store["profile"]
    parts = list(prof.get("hobbies", [])) + list(prof.get("interests", [])) + list(prof.get("likes", []))
    parts += [f.get("text", "") for f in store["facts"]]
    return " ".join(parts).lower()


# ---------------------------------------------------------------------------
# Профіль / онбординг
# ---------------------------------------------------------------------------
def get_profile() -> dict:
    """Повертає профіль користувача. Якщо порожній — потрібен онбординг.

    Поле ``is_empty`` = True, коли ще нічого не заповнено (немає імені й уподобань).
    """
    store = _load()
    prof = store["profile"]
    is_empty = not prof.get("name") and not prof.get("likes") and not prof.get("allergies")
    return {"profile": prof, "is_empty": is_empty}


def onboarding_questions() -> dict:
    """Повертає перелік питань для онбордингу — щоб агент провів знайомство в чаті.

    Агент ставить їх по одному, а відповіді зберігає через update_profile.
    """
    return {
        "questions": [
            {"field": "name", "q": "Як тебе звати?"},
            {"field": "likes", "q": "Що любиш їсти? (страви, кухні, продукти)"},
            {"field": "dislikes", "q": "Чого не любиш або уникаєш?"},
            {"field": "allergies", "q": "Чи є алергії або продукти, які тобі не можна?"},
            {"field": "diets", "q": "Чи дотримуєшся дієти? (веганське, без глютену тощо)"},
            {"field": "relationship", "q": "Ти сам/сама, у стосунках чи одружений/на?"},
            {"field": "family", "q": "Чи готуєш на когось ще? (сімʼя, партнер, діти)"},
            {"field": "hobbies", "q": "Чим захоплюєшся у вільний час?"},
            {"field": "interests", "q": "Улюблені фільми, ігри, музика? (для приємних сюрпризів)"},
            {"field": "budget_pref", "q": "Який бюджет на покупки зазвичай? (low/medium/high або сума)"},
        ]
    }


def update_profile(
    name: Optional[str] = None,
    likes: Optional[list[str]] = None,
    dislikes: Optional[list[str]] = None,
    allergies: Optional[list[str]] = None,
    diets: Optional[list[str]] = None,
    relationship: Optional[str] = None,
    family: Optional[list[dict]] = None,
    hobbies: Optional[list[str]] = None,
    interests: Optional[list[str]] = None,
    budget_pref: Optional[str] = None,
    bonus_first: Optional[bool] = None,
    equipment: Optional[list[str]] = None,
    mode: str = "merge",
) -> dict:
    """Оновлює профіль користувача. Передавай лише ті поля, які треба змінити.

    Args:
        mode: "merge" (за замовч.) — списки доповнюються без дублів; "replace" —
            передані поля повністю перезаписують старі значення.
        Інші аргументи — відповідні поля профілю (списки або рядки).
    """
    store = _load()
    prof = store["profile"]
    incoming = {
        "name": name, "likes": likes, "dislikes": dislikes, "allergies": allergies,
        "diets": diets, "relationship": relationship, "family": family,
        "hobbies": hobbies, "interests": interests, "budget_pref": budget_pref,
        "bonus_first": bonus_first, "equipment": equipment,
    }
    for key, val in incoming.items():
        if val is None:
            continue
        if isinstance(prof.get(key), list) and isinstance(val, list) and mode == "merge":
            existing = prof[key]
            for item in val:
                if item not in existing:
                    existing.append(item)
        else:
            prof[key] = val
    _save(store)
    return {"updated": True, "profile": prof}


def reset_profile() -> dict:
    """Повністю скидає профіль, факти й нагороди (для демо/нового користувача)."""
    _save(_empty_store())
    return {"reset": True}


# ---------------------------------------------------------------------------
# Памʼять фактів
# ---------------------------------------------------------------------------
def remember_fact(text: str, category: Optional[str] = None,
                  tags: Optional[list[str]] = None) -> dict:
    """Запамʼятовує факт із розмови для майбутньої персоналізації.

    Приклади: remember_fact("улюблений фільм — Веном", category="movie"),
    remember_fact("день народження дружини 12 травня", category="event").

    Args:
        text: сам факт (короткий).
        category: тип факту (movie/event/preference/work/...), опційно.
        tags: додаткові теги для пошуку, опційно.
    """
    store = _load()
    fact = {"id": _sid(), "text": text, "category": category,
            "tags": tags or [], "created_at": _now()}
    store["facts"].append(fact)
    _save(store)
    return {"remembered": fact, "total_facts": len(store["facts"])}


def get_facts(category: Optional[str] = None, query: Optional[str] = None,
              limit: int = 50) -> dict:
    """Повертає збережені факти. Можна фільтрувати за категорією та підрядком.

    Args:
        category: показати лише факти цієї категорії.
        query: показати факти, у тексті/тегах яких є цей підрядок.
        limit: максимум фактів.
    """
    store = _load()
    facts = store["facts"]
    if category:
        facts = [f for f in facts if (f.get("category") or "").lower() == category.lower()]
    if query:
        q = query.lower()
        facts = [f for f in facts
                 if q in f["text"].lower() or any(q in t.lower() for t in f.get("tags", []))]
    return {"count": len(facts[:limit]), "facts": facts[:limit]}


def forget_fact(fact_id: str) -> dict:
    """Видаляє факт за його id."""
    store = _load()
    before = len(store["facts"])
    store["facts"] = [f for f in store["facts"] if f["id"] != fact_id]
    _save(store)
    return {"removed": before - len(store["facts"]) > 0, "fact_id": fact_id}


# ---------------------------------------------------------------------------
# Проактивні тригери
# ---------------------------------------------------------------------------
def check_triggers() -> dict:
    """Аналізує профіль і факти та повертає проактивні підказки для користувача.

    Кожна підказка містить готове повідомлення й, за наявності, запит до silpo
    (silpo_query) або гру (game). Агент може показати їх як «сьогодні для тебе».
    """
    store = _load()
    pool = _text_pool(store)
    prof = store["profile"]
    suggestions = []
    for rule in _TRIGGER_RULES:
        if any(kw in pool for kw in rule["keywords"]):
            suggestions.append({
                "kind": rule["kind"],
                "message": rule["message"],
                "silpo_query": rule.get("silpo_query"),
                "game": rule.get("game"),
            })
    # сімʼя/стосунки → ідея романтичної або сімейної вечері
    if prof.get("relationship") in ("relationship", "married") or prof.get("family"):
        suggestions.append({
            "kind": "family_dinner",
            "message": "Готуєш не лише на себе — можу зібрати вечерю на двох/сімʼю.",
            "silpo_query": "вечеря паста", "game": None,
        })
    return {"count": len(suggestions), "suggestions": suggestions,
            "note": "Завжди враховуй allergies/dislikes із get_profile перед показом."}


# ---------------------------------------------------------------------------
# Нагороди за ігри
# ---------------------------------------------------------------------------
def grant_reward(title: str, discount: str, code: Optional[str] = None) -> dict:
    """Видає нагороду/знижку за пройдену гру та зберігає її.

    Args:
        title: назва нагороди, напр. "Знижка за малюнок сиру".
        discount: опис знижки, напр. "-15% на сир" або "-30 грн".
        code: промокод; якщо не заданий — згенерується.
    """
    store = _load()
    reward = {"id": _sid(), "title": title, "discount": discount,
              "code": code or f"GAME-{_sid().upper()}", "created_at": _now(), "used": False}
    store["rewards"].append(reward)
    _save(store)
    return {"granted": reward}


def get_rewards(only_active: bool = True) -> dict:
    """Повертає зароблені нагороди/знижки користувача."""
    store = _load()
    rewards = store["rewards"]
    if only_active:
        rewards = [r for r in rewards if not r.get("used")]
    return {"count": len(rewards), "rewards": rewards}


# ---------------------------------------------------------------------------
# Реєстрація інструментів
# ---------------------------------------------------------------------------
for _fn in (
    get_profile, onboarding_questions, update_profile, reset_profile,
    remember_fact, get_facts, forget_fact,
    check_triggers, grant_reward, get_rewards,
):
    mcp.add_tool(_fn)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
