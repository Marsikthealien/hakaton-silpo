"""Клієнт офіційного MCP «Сільпо» (https://mcp.silpo.ua/mcp).

Сеанс живе у ВИДІЛЕНІЙ задачі, а виклики їдуть до неї чергою. Це не примха:
streamable-HTTP клієнт тримає anyio task group, і якщо відкрити його в одній
задачі, а скористатись із іншої, anyio валить процес помилкою про cancel scope.
Одна задача-власник знімає це питання й заразом серіалізує виклики.

Кожен виклик пишеться у трейс — його показує UI, щоб було видно, які РЕАЛЬНІ
silpo_*-tools відпрацювали під капотом агента.

Автентифікація — вбудований OAuth (auth.py), без Claude Desktop.
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import AsyncExitStack
from typing import Any

import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from . import auth

MAX_TRACE = 200
_STOP = object()


class SilpoError(Exception):
    pass


def _content_text(result) -> str:
    return "\n".join(
        getattr(c, "text", "") for c in result.content if getattr(c, "text", None)
    )


def _parse(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"text": text}


class SilpoMCP:
    """MCP-клієнт «Сільпо»: одна задача-власник сеансу + трейс викликів."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue | None = None
        self._task: asyncio.Task | None = None
        self._ready: asyncio.Event | None = None
        self._failure: str | None = None
        self.tools: list[dict] = []
        self.trace: list[dict] = []
        self.ctx: dict = {}  # branchId, companyId, deliveryType, timeslot*, shoppingCartId

    @property
    def connected(self) -> bool:
        return bool(self._task and not self._task.done() and not self._failure)

    # -- задача-власник ----------------------------------------------------
    async def _worker(self) -> None:
        queue, ready = self._queue, self._ready
        assert queue is not None and ready is not None
        try:
            if not auth.has_tokens():
                raise SilpoError("Немає доступу до MCP «Сільпо». "
                                 "Виконай: python -m silpo_agent_mcp.login")
            async with AsyncExitStack() as stack:
                http = await stack.enter_async_context(
                    httpx2.AsyncClient(auth=auth.provider(), timeout=60))
                streams = await stack.enter_async_context(
                    streamable_http_client(auth.SERVER_URL, http_client=http))
                session = await stack.enter_async_context(
                    ClientSession(streams[0], streams[1]))
                await session.initialize()
                listed = await session.list_tools()
                self.tools = [{"name": t.name, "description": t.description or "",
                               "schema": getattr(t, "input_schema", None) or {}}
                              for t in listed.tools]
                self._failure = None
                ready.set()

                while True:
                    item = await queue.get()
                    if item is _STOP:
                        return
                    tool, args, future = item
                    if future.cancelled():
                        continue
                    try:
                        future.set_result(await session.call_tool(tool, args))
                    except Exception as exc:  # noqa: BLE001 — віддаємо тому, хто чекає
                        future.set_exception(exc)
        except Exception as exc:  # noqa: BLE001
            self._failure = str(exc) or type(exc).__name__
        finally:
            ready.set()
            # нікого не лишаємо висіти на майбутньому, яке вже ніхто не виконає
            while queue and not queue.empty():
                item = queue.get_nowait()
                if item is not _STOP and not item[2].done():
                    item[2].set_exception(SilpoError(self._failure or "Сеанс закрито"))

    async def start(self) -> None:
        if self._task and not self._task.done():
            await self._ready.wait()
        else:
            self._queue = asyncio.Queue()
            self._ready = asyncio.Event()
            self._failure = None
            self._task = asyncio.create_task(self._worker(), name="silpo-mcp")
            await self._ready.wait()
        if self._failure:
            raise SilpoError(self._failure)

    async def stop(self) -> None:
        if self._task and not self._task.done():
            await self._queue.put(_STOP)
            try:
                await asyncio.wait_for(self._task, timeout=10)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        self._task = None
        self.ctx.clear()

    # -- виклики -----------------------------------------------------------
    async def call(self, tool: str, args: dict | None = None) -> Any:
        """Викликає реальний silpo_*-tool. Обрив сеансу → одна перепідключка."""
        args = args or {}
        started = time.perf_counter()
        try:
            data = await self._dispatch(tool, args)
            self._log(tool, args, started, ok=True)
            return data
        except SilpoError:
            self._log(tool, args, started, ok=False, note="немає доступу")
            raise
        except Exception as first:
            self._task = None  # змусити підняти новий сеанс
            try:
                data = await self._dispatch(tool, args)
                self._log(tool, args, started, ok=True, note="перепідключення")
                return data
            except Exception as second:
                self._log(tool, args, started, ok=False,
                          note=f"{type(second).__name__}: {second}")
                raise SilpoError(f"{tool}: {second or first}") from second

    async def _dispatch(self, tool: str, args: dict) -> Any:
        await self.start()
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        await self._queue.put((tool, args, future))
        result = await future
        if getattr(result, "isError", False):
            raise SilpoError(f"{tool}: {_content_text(result)[:300]}")
        return _parse(_content_text(result))

    # -- трейс -------------------------------------------------------------
    def _log(self, tool: str, args: dict, started: float, *, ok: bool, note: str = "",
             kind: str = "real") -> None:
        self.trace.append({
            "tool": tool, "kind": kind,
            "args": {k: v for k, v in args.items()
                     if k not in ("timeslotStart", "timeslotEnd", "shoppingCartId")},
            "ms": round((time.perf_counter() - started) * 1000),
            "ok": ok, "note": note, "at": time.strftime("%H:%M:%S"),
        })
        del self.trace[:-MAX_TRACE]

    def log_proposed(self, tool: str, args: dict, started: float, *, ok: bool = True,
                     note: str = "") -> None:
        """Слід виклику ЗАПРОПОНОВАНОГО tool — того, якого в MCP «Сільпо» ще немає.

        Пишемо в той самий трейс, але з kind="proposed": у демо видно, де агент
        працює з реальним API, а де — з тим, що ми просимо Сільпо додати.
        """
        self._log(tool, args, started, ok=ok, note=note, kind="proposed")

    def trace_tail(self, limit: int = 30) -> list[dict]:
        return self.trace[-limit:]

    def clear_trace(self) -> None:
        self.trace.clear()


silpo = SilpoMCP()
