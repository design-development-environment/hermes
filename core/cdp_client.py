#!/usr/bin/env python3
"""Small standard-library Chrome DevTools Protocol client for Hermes."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import socket
import struct
import urllib.parse
import urllib.request


class CDPError(RuntimeError):
    pass


def _read_exact(stream: socket.socket, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = stream.recv(remaining)
        if not chunk:
            raise CDPError("Chrome closed the debugging connection")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class CDPConnection:
    """One synchronous WebSocket connection to a CDP target."""

    def __init__(self, websocket_url: str, timeout: int = 20):
        parsed = urllib.parse.urlparse(websocket_url)
        if parsed.scheme != "ws" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise CDPError("Hermes only connects to the local Chrome debugger")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        self.timeout = timeout
        self.stream: socket.socket | None = None
        self.counter = 0

    def __enter__(self):
        self.stream = socket.create_connection((self.host, self.port), timeout=self.timeout)
        key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"Origin: http://{self.host}:{self.port}\r\n\r\n"
        )
        self.stream.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.stream.recv(4096)
            if len(response) > 32_768:
                raise CDPError("Invalid Chrome WebSocket handshake")
        headers = response.split(b"\r\n\r\n", 1)[0].decode("latin-1")
        if " 101 " not in headers.splitlines()[0]:
            raise CDPError(f"Chrome rejected the debugging connection: {headers.splitlines()[0]}")
        expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
        received = ""
        for line in headers.splitlines()[1:]:
            name, separator, value = line.partition(":")
            if separator and name.casefold() == "sec-websocket-accept":
                received = value.strip()
                break
        if not secrets.compare_digest(received, expected):
            raise CDPError("Chrome returned an invalid WebSocket handshake")
        return self

    def __exit__(self, *_):
        if self.stream:
            try:
                self._send_frame(b"", opcode=8)
            except OSError:
                pass
            self.stream.close()
            self.stream = None

    def _send_frame(self, payload: bytes, opcode: int = 1):
        if not self.stream:
            raise CDPError("Debugging connection is not open")
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x80 | opcode])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65_536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
        self.stream.sendall(bytes(header) + masked)

    def _receive_message(self) -> str:
        if not self.stream:
            raise CDPError("Debugging connection is not open")
        parts = []
        message_opcode = None
        while True:
            first, second = _read_exact(self.stream, 2)
            finished = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", _read_exact(self.stream, 2))[0]
            elif length == 127:
                length = struct.unpack("!Q", _read_exact(self.stream, 8))[0]
            if length > 20_000_000:
                raise CDPError("Chrome debugging response is too large")
            mask = _read_exact(self.stream, 4) if masked else b""
            payload = _read_exact(self.stream, length)
            if masked:
                payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))
            if opcode == 8:
                raise CDPError("Chrome closed the debugging target")
            if opcode == 9:
                self._send_frame(payload, opcode=10)
                continue
            if opcode == 10:
                continue
            if opcode in (1, 2):
                message_opcode = opcode
            elif opcode != 0:
                continue
            parts.append(payload)
            if finished:
                if message_opcode != 1:
                    raise CDPError("Unexpected binary Chrome debugging response")
                return b"".join(parts).decode("utf-8")

    def call(self, method: str, params: dict | None = None) -> dict:
        self.counter += 1
        request_id = self.counter
        message = {"id": request_id, "method": method}
        if params:
            message["params"] = params
        self._send_frame(json.dumps(message, separators=(",", ":")).encode("utf-8"))
        while True:
            response = json.loads(self._receive_message())
            if response.get("id") != request_id:
                continue
            if "error" in response:
                error = response["error"]
                raise CDPError(f"{method}: {error.get('message', error)}")
            return response.get("result", {})


def debugger_json(path: str = "/json/list", *, method: str = "GET", timeout: int = 5):
    request = urllib.request.Request(f"http://127.0.0.1:9222{path}", method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def page_targets() -> list[dict]:
    return [target for target in debugger_json() if target.get("type") == "page"]


def page_target(page_id: str) -> dict:
    for target in page_targets():
        if target.get("id") == page_id:
            return target
    raise CDPError("Managed browser page was not found")


def call_page(page_id: str, method: str, params: dict | None = None, timeout: int = 20) -> dict:
    target = page_target(page_id)
    with CDPConnection(target["webSocketDebuggerUrl"], timeout=timeout) as connection:
        return connection.call(method, params)


def evaluate(page_id: str, expression: str, timeout: int = 20):
    result = call_page(page_id, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True,
        "userGesture": True,
    }, timeout=timeout)
    remote = result.get("result", {})
    if remote.get("subtype") == "error":
        raise CDPError(remote.get("description", "Browser script failed"))
    if result.get("exceptionDetails"):
        details = result["exceptionDetails"]
        raise CDPError(details.get("text", "Browser script failed"))
    return remote.get("value")
