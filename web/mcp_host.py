"""MCP-хост для веб-бекенду: робить його справжнім MCP-клієнтом.

Підключається до наших локальних MCP-серверів (`profile` та `silpo-mock`) як
stdio-клієнт, динамічно зчитує їхні інструменти (tools/list) і дозволяє
викликати їх (tools/call). Саме ці інструменти передаються Qwen — тобто модель
працює з РЕАЛЬНИМИ MCP-серверами по протоколу, а не з хардкодом.

Сесії тримаються відкритими весь час життя застосунку (Starlette lifespan),
тож стан (кошик у silpo-mock) спільний для чату й UI, які обидва ходять сюди.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable  # той самий venv-Python, що запустив uvicorn

SERVERS = {
    "silpo-mock": [os.path.join(ROOT, "silpo_mcp", "server.py")],
    "profile": [os.path.join(ROOT, "profile_mcp", "server.py")],
}


def _to_ollama_tool(t) -> dict:
    schema = getattr(t, "input_schema", None) or {"type": "object", "properties": {}}
    return {"type": "function", "function": {
        "name": t.name, "description": t.description or "", "parameters": schema}}


class MCPHost:
    def __init__(self):
        self._stack = AsyncExitStack()
        self._lock = asyncio.Lock()
        self.sessions: dict[str, ClientSession] = {}
        self.tool_server: dict[str, str] = {}   # tool_name -> server
        self.tools: list[dict] = []             # схеми в форматі Ollama
        self.started = False

    async def start(self) -> None:
        if self.started:
            return
        for name, args in SERVERS.items():
            params = StdioServerParameters(command=PY, args=args, cwd=ROOT)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            sess = await self._stack.enter_async_context(ClientSession(read, write))
            await sess.initialize()
            self.sessions[name] = sess
            listed = await sess.list_tools()
            for t in listed.tools:
                self.tool_server[t.name] = name
                self.tools.append(_to_ollama_tool(t))
        self.started = True

    async def stop(self) -> None:
        await self._stack.aclose()
        self.started = False

    async def call(self, tool_name: str, args: dict) -> dict:
        server = self.tool_server.get(tool_name)
        if not server:
            return {"error": f"Інструмент {tool_name} не знайдено на MCP-серверах"}
        async with self._lock:
            res = await self.sessions[server].call_tool(tool_name, args or {})
        text = "\n".join(getattr(c, "text", "") for c in res.content
                         if getattr(c, "text", None))
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return {"text": text}


host = MCPHost()
