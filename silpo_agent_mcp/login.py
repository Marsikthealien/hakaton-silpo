"""Одноразовий вхід у «Сільпо» через OAuth: python -m silpo_agent_mcp.login

Відкриває браузер, приймає редірект на 127.0.0.1 і зберігає токени у
.mcp/silpo_tokens.json. Далі застосунок оновлює їх сам через refresh_token.
"""

from __future__ import annotations

import sys

import anyio
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from . import auth


async def _login() -> int:
    print("→ підключаюся до", auth.SERVER_URL, file=sys.stderr)
    async with httpx2.AsyncClient(auth=auth.provider(interactive=True), timeout=120) as http:
        async with streamable_http_client(auth.SERVER_URL, http_client=http) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                info = await session.initialize()
                tools = await session.list_tools()
    print(f"\n✅ Вхід виконано. Сервер: {info.server_info.name} "
          f"{info.server_info.version}, tools: {len(tools.tools)}")
    print(f"   Токени: {auth.STORE_PATH}")
    return 0


def main() -> int:
    if auth.has_tokens():
        print(f"ℹ️  Токени вже є ({auth.STORE_PATH}). Перевіряю, чи живі…", file=sys.stderr)
    try:
        return anyio.run(_login)
    except Exception as exc:
        print(f"\n❌ Не вдалося: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
