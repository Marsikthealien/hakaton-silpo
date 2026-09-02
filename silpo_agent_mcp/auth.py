"""OAuth 2.1 (PKCE) до офіційного MCP «Сільпо» — вбудований у застосунок.

Раніше токен підбирався з ~/.mcp-auth, тобто проєкт залежав від встановленого
Claude Desktop + mcp-remote. Тут ми проходимо OAuth самі, один раз:

    python -m silpo_agent_mcp.login

Токени лягають у .mcp/silpo_tokens.json (у .gitignore) і далі оновлюються
автоматично через refresh_token — застосунок працює без участі людини.
"""

from __future__ import annotations

import json
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import anyio
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)
from pydantic import AnyUrl

SERVER_URL = "https://mcp.silpo.ua/mcp"
CALLBACK_PORT = int(os.environ.get("SILPO_OAUTH_PORT", "41765"))
REDIRECT_URI = f"http://127.0.0.1:{CALLBACK_PORT}/callback"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, ".mcp", "silpo_tokens.json")


class AuthMissing(Exception):
    """Немає збережених токенів — треба пройти `python -m silpo_agent_mcp.login`."""


# ---------------------------------------------------------------------------
# Сховище токенів (файл поруч із проєктом)
# ---------------------------------------------------------------------------
class FileTokenStorage(TokenStorage):
    """Персистентне сховище токенів і зареєстрованого OAuth-клієнта."""

    def __init__(self, path: str = STORE_PATH):
        self.path = path

    def _read(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(self.path, 0o600)  # токен — секрет
        except OSError:
            pass

    async def get_tokens(self) -> OAuthToken | None:
        raw = self._read().get("tokens")
        return OAuthToken.model_validate(raw) if raw else None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        data = self._read()
        data["tokens"] = tokens.model_dump(mode="json", exclude_none=True)
        data["saved_at"] = int(time.time())
        self._write(data)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        raw = self._read().get("client")
        return OAuthClientInformationFull.model_validate(raw) if raw else None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        data = self._read()
        data["client"] = client_info.model_dump(mode="json", exclude_none=True)
        self._write(data)


def token_info(path: str = STORE_PATH) -> dict:
    """Стан токена без його розкриття — для екрана налаштувань."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"present": False, "path": path,
                "hint": "Виконай: python -m silpo_agent_mcp.login"}
    token = (data.get("tokens") or {}).get("access_token") or ""
    saved = data.get("saved_at")
    return {
        "present": bool(token),
        "tail": token[-6:] if token else None,
        "has_refresh": bool((data.get("tokens") or {}).get("refresh_token")),
        "saved_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(saved)) if saved else None,
        "age_hours": round((time.time() - saved) / 3600, 1) if saved else None,
        "client_registered": bool(data.get("client")),
        "path": path,
    }


def save_access_token(token: str, refresh_token: str | None = None,
                      path: str = STORE_PATH) -> dict:
    """Вручну підставити свіжий токен — коли зручніше вставити його, ніж логінитись."""
    token = (token or "").strip()
    if not token:
        raise AuthMissing("Порожній токен.")
    storage = FileTokenStorage(path)
    data = storage._read()
    tokens = data.get("tokens") or {}
    tokens["access_token"] = token
    tokens.setdefault("token_type", "Bearer")
    if refresh_token:
        tokens["refresh_token"] = refresh_token
    data["tokens"] = tokens
    data["saved_at"] = int(time.time())
    storage._write(data)
    return token_info(path)


def forget_tokens(path: str = STORE_PATH) -> dict:
    """Видаляє збережені токени — наступний запуск попросить увійти знову."""
    try:
        os.remove(path)
    except OSError:
        pass
    return token_info(path)


def has_tokens(path: str = STORE_PATH) -> bool:
    """Чи вже проходили логін (без розкриття самого токена)."""
    try:
        with open(path, encoding="utf-8") as f:
            return bool(json.load(f).get("tokens", {}).get("access_token"))
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


# ---------------------------------------------------------------------------
# Інтерактивна частина: браузер + локальний callback
# ---------------------------------------------------------------------------
class _CallbackHandler(BaseHTTPRequestHandler):
    result: dict = {}

    def do_GET(self):  # noqa: N802 — ім'я диктує BaseHTTPRequestHandler
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/callback"):
            self.send_response(404)
            self.end_headers()
            return
        query = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        _CallbackHandler.result = query
        ok = "code" in query
        body = (
            "<meta charset='utf-8'><body style='font:16px system-ui;padding:40px'>"
            + ("<h2>Готово ✅</h2><p>Повертайся в термінал — вікно можна закрити.</p>"
               if ok else f"<h2>Не вдалося ❌</h2><pre>{query}</pre>")
            + "</body>"
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args):  # тиша замість логів у stdout
        pass


async def _redirect_handler(url: str) -> None:
    # ВАЖЛИВО: пишемо у stderr — stdout зайнятий MCP-протоколом, якщо нас
    # запустили як stdio-сервер.
    print(f"\n🔐 Увійди в «Сільпо» за посиланням:\n{url}\n", file=sys.stderr, flush=True)
    try:
        webbrowser.open(url)
    except Exception:
        pass


async def _callback_handler() -> AuthorizationCodeResult:
    def _serve() -> dict:
        _CallbackHandler.result = {}
        deadline = time.time() + 300
        with HTTPServer(("127.0.0.1", CALLBACK_PORT), _CallbackHandler) as httpd:
            httpd.timeout = 5
            # браузер може смикнути /favicon.ico — чекаємо саме на /callback
            while not _CallbackHandler.result and time.time() < deadline:
                httpd.handle_request()
        return _CallbackHandler.result

    result = await anyio.to_thread.run_sync(_serve)
    if "code" not in result:
        raise AuthMissing(
            f"OAuth не завершився: {result or 'таймаут очікування 5 хв'}"
        )
    return AuthorizationCodeResult(
        code=result["code"], state=result.get("state"), iss=result.get("iss")
    )


# ---------------------------------------------------------------------------
# Провайдер для httpx2
# ---------------------------------------------------------------------------
def provider(interactive: bool = False) -> OAuthClientProvider:
    """OAuth-провайдер для httpx2.AsyncClient(auth=...).

    Args:
        interactive: True — дозволено відкрити браузер і чекати на редірект
            (тільки для `python -m silpo_agent_mcp.login`). False — сервер
            працює мовчки на збережених токенах і сам їх оновлює.
    """
    metadata = OAuthClientMetadata(
        client_name="Silpo Pack Agent",
        redirect_uris=[AnyUrl(REDIRECT_URI)],
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
        token_endpoint_auth_method="none",
    )
    return OAuthClientProvider(
        server_url=SERVER_URL,
        client_metadata=metadata,
        storage=FileTokenStorage(),
        redirect_handler=_redirect_handler if interactive else None,
        callback_handler=_callback_handler if interactive else None,
    )
