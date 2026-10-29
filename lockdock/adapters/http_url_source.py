"""UrlSource over a minimal HTTP/1.1 server on 127.0.0.1, fed by the browser extension."""
from __future__ import annotations

import asyncio
import hmac
import json
from collections.abc import Callable

MAX_HEADER_BYTES = 16 * 1024
MAX_BODY_BYTES = 64 * 1024
READ_TIMEOUT_S = 5.0
REASONS = {200: "OK", 204: "No Content", 400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
           404: "Not Found", 405: "Method Not Allowed", 413: "Payload Too Large", 431: "Header Too Large"}
EXTENSION_SCHEMES = ("chrome-extension://", "moz-extension://")


class HttpUrlSource:
    """Serves POST /url (JSON {url, title, browser}), GET /health and CORS preflights.

    Implements the UrlSource port: `watch(on_url)` serves until cancelled and calls
    `on_url(browser, url)` per accepted report. Requests from ordinary web pages (an Origin
    that is not a browser extension) are refused, and an optional bearer token is enforced.
    """

    def __init__(self, port: int = 47231, token: str = "", host: str = "127.0.0.1") -> None:
        self.port = port
        self.token = token
        self.host = host
        self.listening = False
        self.started = asyncio.Event()
        self._on_url: Callable[[str, str], None] = lambda browser, url: None

    async def watch(self, on_url: Callable[[str, str], None]) -> None:
        """Bind and serve forever. Raises OSError if the port is taken."""
        self._on_url = on_url
        server = await asyncio.start_server(self._handle, self.host, self.port, limit=MAX_HEADER_BYTES)
        self.port = server.sockets[0].getsockname()[1]  # resolves port 0
        self.listening = True
        self.started.set()
        try:
            async with server:
                await server.serve_forever()
        finally:
            self.listening = False

    # ---------- protocol ----------
    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            status, body, origin = await asyncio.wait_for(self._respond(reader), READ_TIMEOUT_S)
        except Exception:  # timeouts, resets, oversize or garbage input: never take the server down
            status, body, origin = 400, b"", ""
        head = [f"HTTP/1.1 {status} {REASONS.get(status, 'Error')}", f"Content-Length: {len(body)}",
                "Connection: close", "Access-Control-Allow-Methods: POST, GET, OPTIONS",
                "Access-Control-Allow-Headers: Content-Type, Authorization",
                "Access-Control-Allow-Private-Network: true", "Access-Control-Max-Age: 600"]
        if origin:
            head += [f"Access-Control-Allow-Origin: {origin}", "Vary: Origin"]
        if body:
            head.append("Content-Type: application/json")
        try:
            writer.write(("\r\n".join(head) + "\r\n\r\n").encode() + body)
            await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()

    async def _respond(self, reader: asyncio.StreamReader) -> tuple[int, bytes, str]:
        raw = await reader.readuntil(b"\r\n\r\n")
        lines = raw.decode("latin-1").split("\r\n")
        parts = lines[0].split(" ")
        if len(parts) != 3 or not parts[2].startswith("HTTP/1."):
            return 400, b"", ""
        method, target = parts[0], parts[1].split("?", 1)[0]
        headers: dict[str, str] = {}
        for ln in lines[1:]:
            if ":" in ln:
                k, v = ln.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        origin = headers.get("origin", "")
        if origin and not origin.startswith(EXTENSION_SCHEMES):
            return 403, b"", ""
        if method == "OPTIONS":
            return 204, b"", origin
        if target == "/health" and method == "GET":
            return 200, b'{"ok":true}', origin
        if target != "/url":
            return 404, b"", origin
        if method != "POST":
            return 405, b"", origin
        if self.token and not hmac.compare_digest(
                headers.get("authorization", "").encode(), f"Bearer {self.token}".encode()):
            return 401, b"", origin
        try:
            length = int(headers.get("content-length", ""))
        except ValueError:
            return 400, b"", origin
        if length < 0 or length > MAX_BODY_BYTES:
            return 413, b"", origin
        data = await reader.readexactly(length)
        try:
            msg = json.loads(data)
            url, browser = msg["url"], str(msg.get("browser") or "")
        except (ValueError, KeyError, TypeError):
            return 400, b"", origin
        if not isinstance(url, str) or not url:
            return 400, b"", origin
        self._on_url(browser, url)
        return 204, b"", origin
