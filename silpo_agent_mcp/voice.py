"""Голос агента: Respeecher Space API, українська модель.

Браузерний `speechSynthesis` лишається запасним шляхом — він безкоштовний і
працює завжди, але голос бере системний, і українського в системі часто просто
немає. Respeecher дає справжній український голос і, головне, **наголоси**: у
моделі `ua-rt` можна поставити `+` перед голосною, і «йог+урт» більше не
звучить як «йогурт» з наголосом навмання.

Контракт (space.respeecher.com/docs):
    GET  {base}/voices        → [{id, gender, accent, sampling_params}]
    POST {base}/tts/bytes     → WAV; тіло {"transcript": ..., "voice": {"id": ...}}
    заголовок X-API-Key
    base = https://api.respeecher.com/v1/public/tts/ua-rt

Ключ береться зі змінної RESPEECHER_API_KEY або з `.mcp/respeecher.json` —
у git не потрапляє ні перше, ні друге.
"""

from __future__ import annotations

import json
import os
import re

import httpx2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY_PATH = os.path.join(ROOT, ".mcp", "respeecher.json")

BASE_UA = "https://api.respeecher.com/v1/public/tts/ua-rt"
# Ліміт Bytes — близько 5000 символів і 120 с на запит. Репліка агента коротка,
# але обрізаємо явно: краще недоговорити, ніж отримати таймаут посеред демо.
MAX_CHARS = 900
TIMEOUT = 60


def _key() -> str | None:
    env = os.environ.get("RESPEECHER_API_KEY")
    if env:
        return env.strip()
    try:
        with open(KEY_PATH, encoding="utf-8") as f:
            return (json.load(f).get("api_key") or "").strip() or None
    except (OSError, json.JSONDecodeError):
        return None


def _cfg() -> dict:
    try:
        with open(KEY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cfg(data: dict) -> None:
    os.makedirs(os.path.dirname(KEY_PATH), exist_ok=True)
    with open(KEY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Текст для вимови
# ---------------------------------------------------------------------------
# Порада від Respeecher: числа, час і дати вимовляти словами, абревіатури — по
# літерах, а URL, шляхи та ідентифікатори не читати взагалі. Модель цього не
# гарантує, тож готуємо текст самі — так само, як готували б його для диктора.
_ONES = ["нуль", "один", "дві", "три", "чотири", "п'ять", "шість", "сім",
         "вісім", "дев'ять", "десять", "одинадцять", "дванадцять", "тринадцять",
         "чотирнадцять", "п'ятнадцять", "шістнадцять", "сімнадцять",
         "вісімнадцять", "дев'ятнадцять"]
_TENS = {2: "двадцять", 3: "тридцять", 4: "сорок", 5: "п'ятдесят", 6: "шістдесят",
         7: "сімдесят", 8: "вісімдесят", 9: "дев'яносто"}
_HUNDREDS = {1: "сто", 2: "двісті", 3: "триста", 4: "чотириста", 5: "п'ятсот",
             6: "шістсот", 7: "сімсот", 8: "вісімсот", 9: "дев'ятсот"}


def _under_1000(n: int) -> list[str]:
    out = []
    if n >= 100:
        out.append(_HUNDREDS[n // 100])
        n %= 100
    if n >= 20:
        out.append(_TENS[n // 10])
        n %= 10
    if n:
        out.append(_ONES[n])
    return out


def number_to_words(n: int) -> str:
    """Число словами. Далі за мільйон не йдемо — у чеках такого не буває."""
    if n == 0:
        return "нуль"
    if n < 0:
        return "мінус " + number_to_words(-n)
    parts = []
    if n >= 1000:
        th = n // 1000
        if th == 1:
            parts.append("одна тисяча")
        elif th in (2, 3, 4):
            parts += _under_1000(th)[:-1] + [{2: "дві тисячі", 3: "три тисячі",
                                              4: "чотири тисячі"}[th % 10]
                                             if th % 10 in (2, 3, 4) and th < 10
                                             else _ONES[th % 10] + " тисячі"]
        else:
            parts += _under_1000(th) + ["тисяч"]
        n %= 1000
    if n:
        parts += _under_1000(n)
    return " ".join(parts)


_MONTHS = ["січня", "лютого", "березня", "квітня", "травня", "червня", "липня",
           "серпня", "вересня", "жовтня", "листопада", "грудня"]


def _money(uah: int) -> str:
    """Гроші вголос — цілими гривнями. «Сто сорок чотири гривні» замість
    «сто сорок три кома дев'яносто чотири»: копійки в розмові не вимовляють."""
    tail = uah % 100
    if 11 <= tail <= 14:
        form = "гривень"
    else:
        form = {1: "гривня", 2: "гривні", 3: "гривні", 4: "гривні"}.get(uah % 10, "гривень")
    return f"{number_to_words(uah)} {form}"


def for_speech(text: str) -> str:
    """Текст, готовий до вимови. Правила — з поради Respeecher у каналі хакатону:
    числа словами, абревіатури по літерах, URL та ідентифікатори не читати."""
    s = str(text or "")

    # 1. Того, що не читають уголос, не має бути взагалі.
    s = re.sub(r"https?://\S+|\b[\w-]+\.(?:ua|com|net|org)\b\S*", " ", s)
    s = re.sub(r"[/\\][\w./\\-]{4,}", " ", s)                # шляхи
    s = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{20,}\b", " ", s)     # uuid
    s = re.sub(r"\b(?:pk|pack)-[\w]+\b", " ", s)              # id пака
    s = re.sub(r"\b[a-z_]+_[a-z_]+\b", " ", s)                # імена tools
    s = re.sub(r"`[^`]*`|\{[^}]*\}", " ", s)                  # код і JSON
    s = re.sub(r"[*_#>|]+", " ", s)                           # розмітка

    # 2. Роздільники — у крапку, інакше речення злипаються в одне дихання.
    s = re.sub(r"\s*[·•]\s*", ". ", s)
    s = re.sub(r"\s*[→↑↗]\s*", " ", s)

    # 3. Дати й час — словами.
    s = re.sub(r"\b(\d{4})-(\d{2})-(\d{2})\b",
               lambda m: f"{number_to_words(int(m.group(3)))} "
                         f"{_MONTHS[int(m.group(2)) - 1]}", s)
    s = re.sub(r"\b(\d{1,2}):(\d{2})\b",
               lambda m: f"{number_to_words(int(m.group(1)))} "
                         + (f"{number_to_words(int(m.group(2)))}"
                            if m.group(2) != "00" else "рівно"), s)

    # 4. Гроші: округлюємо до гривні ще ДО загального правила про числа.
    s = re.sub(r"(\d+)(?:[.,](\d+))?\s*₴",
               lambda m: _money(round(float(m.group(1) + "." + (m.group(2) or "0")))), s)
    s = re.sub(r"(\d+)[.,](\d+)",
               lambda m: f"{number_to_words(int(m.group(1)))} кома "
                         f"{number_to_words(int(m.group(2)))}", s)
    s = s.replace("%", " відсотків").replace("₴", " гривень")
    s = re.sub(r"\d+", lambda m: number_to_words(int(m.group(0)))
               if len(m.group(0)) <= 6 else " ".join(_ONES[int(d)] for d in m.group(0)), s)

    # 5. Лапки геть, апостроф усередині слова лишається — без нього «п'ять»
    #    розпадається на «п ять».
    s = re.sub(r"[«»\"]", " ", s)
    s = re.sub(r"(?<![а-яіїєґА-ЯІЇЄҐ])['\u2019](?![а-яіїєґА-ЯІЇЄҐ])", " ", s)
    s = re.sub(r"\s+([.,!?])", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()[:MAX_CHARS]


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
async def voices() -> dict:
    """Українські голоси Respeecher. Без ключа чесно каже, що ключа немає."""
    key = _key()
    if not key:
        return {"available": False, "voices": [],
                "hint": ("Ключа немає. Створити: space.respeecher.com/api-keys, "
                         "далі покласти в RESPEECHER_API_KEY або через "
                         "POST /api/voice/key."),
                "fallback": "Поки що озвучує браузер — голос системний."}
    async with httpx2.AsyncClient(timeout=TIMEOUT) as http:
        r = await http.get(f"{BASE_UA}/voices", headers={"X-API-Key": key})
    if r.status_code != 200:
        return {"available": False, "voices": [],
                "error": f"Respeecher {r.status_code}: {r.text[:200]}"}
    rows = r.json()
    cfg = _cfg()
    return {"available": True, "count": len(rows),
            "voices": [{"id": v.get("id"), "gender": v.get("gender"),
                        "accent": v.get("accent")} for v in rows],
            "chosen": cfg.get("voice") or (rows[0]["id"] if rows else None),
            "model": BASE_UA,
            "note": ("Українська модель підтримує наголоси: «йог+урт» ставить "
                     "наголос на «у». Саме тому вона краща за системний голос.")}


async def say(text: str, voice: str | None = None, prepare: bool = True) -> bytes:
    """Синтез. Повертає WAV. Кидає RuntimeError, якщо ключа чи голосу немає."""
    key = _key()
    if not key:
        raise RuntimeError("Немає ключа Respeecher.")
    cfg = _cfg()
    voice_id = voice or cfg.get("voice")
    if not voice_id:
        listed = await voices()
        voice_id = listed.get("chosen")
    if not voice_id:
        raise RuntimeError("Не вдалося обрати голос.")
    transcript = for_speech(text) if prepare else str(text)[:MAX_CHARS]
    if not transcript:
        raise RuntimeError("Порожній текст.")
    async with httpx2.AsyncClient(timeout=TIMEOUT) as http:
        r = await http.post(f"{BASE_UA}/tts/bytes",
                            headers={"X-API-Key": key, "Content-Type": "application/json"},
                            json={"transcript": transcript, "voice": {"id": voice_id}})
    if r.status_code != 200:
        raise RuntimeError(f"Respeecher {r.status_code}: {r.text[:200]}")
    return r.content


def set_key(api_key: str = "", voice: str = "") -> dict:
    """Зберегти ключ і обраний голос у `.mcp/respeecher.json` (поза git)."""
    cfg = _cfg()
    if api_key:
        cfg["api_key"] = api_key.strip()
    if voice:
        cfg["voice"] = voice.strip()
    _save_cfg(cfg)
    return {"saved": True, "has_key": bool(_key()), "voice": cfg.get("voice")}


def status() -> dict:
    cfg = _cfg()
    key = _key()
    return {"has_key": bool(key), "voice": cfg.get("voice"), "model": BASE_UA,
            "source": ("змінна RESPEECHER_API_KEY" if os.environ.get("RESPEECHER_API_KEY")
                       else ".mcp/respeecher.json" if key else None),
            "max_chars": MAX_CHARS}
