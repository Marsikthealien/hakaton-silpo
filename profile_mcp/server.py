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
        "MCP персоналізації: те, чого немає в акаунті «Сільпо» — алергії, "
        "вподобання, техніка на кухні. Спочатку виклич get_profile; правки — "
        "update_profile. Перед рекомендаціями враховуй allergies/dislikes/diets. "
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
    return {"profile": dict(_DEFAULT_PROFILE)}


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
    return base


def _save(store: dict) -> None:
    with open(_STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)




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
# Реєстрація інструментів
# ---------------------------------------------------------------------------
for _fn in (get_profile, update_profile, reset_profile):
    mcp.add_tool(_fn)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
