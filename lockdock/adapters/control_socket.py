"""The control socket: one newline-terminated JSON request {"cmd", "arg"} per connection.
A command may return an awaitable (e.g. `classify`); it is awaited before the reply."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

from ..core.ports import CommandHandler


def handle_line(handler: CommandHandler, line: bytes) -> dict:
    """Decode one request line and dispatch it; returns the response object."""
    try:
        req = json.loads(line or b"{}")
        return {"ok": True, "result": handler.handle(req.get("cmd"), req.get("arg"))}
    except (ValueError, OSError) as e:
        return {"ok": False, "error": str(e)}


class UnixSocketControl:
    """Serves CommandHandler over a unix socket at `path`."""

    def __init__(self, path: Path, handler: CommandHandler) -> None:
        self.path = path
        self.handler = handler

    async def _client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await reader.readline()
            res = handle_line(self.handler, line)
            if inspect.isawaitable(res.get("result")):
                try:
                    res = {"ok": True, "result": await res["result"]}
                except (ValueError, OSError) as e:
                    res = {"ok": False, "error": str(e)}
            writer.write((json.dumps(res) + "\n").encode())
        except OSError as e:
            writer.write((json.dumps({"ok": False, "error": str(e)}) + "\n").encode())
        finally:
            await writer.drain()
            writer.close()

    async def serve(self) -> None:
        if self.path.exists():
            self.path.unlink()
        server = await asyncio.start_unix_server(self._client, path=str(self.path))
        async with server:
            await server.serve_forever()
