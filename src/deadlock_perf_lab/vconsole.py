"""Minimal, local-only Source 2 VConsole transport with bounded reads.

Wire framing follows the public CS2RemoteConsole libvconsole protocol:
4-byte tag, BE uint32 version, BE uint16 total size, BE uint16 handle.
"""
from __future__ import annotations

import select
import socket
import struct
import time
from pathlib import Path

from .storage import LabError

HEADER = struct.Struct(">4sIHH")


class VConsole:
    def __init__(self, log: Path, timeout: float = 90):
        self.log = log
        self.buffer = bytearray()
        self.messages: list[str] = []
        deadline = time.monotonic() + timeout
        while True:
            try:
                self.socket = socket.create_connection(("127.0.0.1", 29000), timeout=2)
                self.socket.setblocking(False)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise LabError("No VConsole on localhost:29000. Check Steam launch options and steam.log.") from exc
                time.sleep(.5)

    def close(self) -> None:
        self.socket.close()

    def send(self, command: str) -> None:
        if any(c in command for c in "\r\n\0;"):
            raise LabError("VConsole commands must be single commands without control characters.")
        payload = command.encode() + b"\0"
        if len(payload) + HEADER.size > 65535:
            raise LabError("VConsole command is too long.")
        self.socket.settimeout(3)
        try:
            self.socket.sendall(HEADER.pack(b"CMND", 0x00D40000, HEADER.size + len(payload), 0) + payload)
        except OSError as exc:
            raise LabError(f"VConsole send failed: {exc}") from exc
        finally:
            self.socket.setblocking(False)
        with self.log.open("a", encoding="utf-8") as f:
            f.write(f"> {command}\n")

    def read(self, timeout: float = .1) -> list[str]:
        try:
            if not select.select([self.socket], [], [], timeout)[0]:
                return []
            chunk = self.socket.recv(65536)
        except OSError as exc:
            raise LabError(f"VConsole receive failed: {exc}") from exc
        if not chunk:
            raise LabError("Game closed the VConsole connection.")
        self.buffer.extend(chunk)
        lines = []
        while len(self.buffer) >= HEADER.size:
            tag, _, size, _ = HEADER.unpack_from(self.buffer)
            if size < HEADER.size:
                raise LabError("Invalid VConsole packet size.")
            if len(self.buffer) < size:
                break
            body = bytes(self.buffer[HEADER.size:size])
            del self.buffer[:size]
            if tag == b"PRNT" and len(body) >= 28:
                message = body[28:].split(b"\0", 1)[0].decode("utf-8", errors="replace").strip()
                lines.append(message)
        if lines:
            with self.log.open("a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            self.messages.extend(lines)
            self.messages = self.messages[-2000:]
        return lines

    def drain(self) -> None:
        # Bound work even when the game streams debug output continuously.
        for _ in range(100):
            if not select.select([self.socket], [], [], 0)[0]:
                break
            self.read(0)
        self.messages.clear()

    def wait_for(self, phrase: str, timeout: float = 120) -> str:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for message in self.messages:
                if phrase.lower() in message.lower():
                    return message
            self.read(.2)
        raise LabError(f"Game did not confirm {phrase!r} within {timeout:g}s. See vconsole.log.")

    def command_wait(self, command: str, phrase: str, timeout: float = 120) -> str:
        self.drain()
        self.send(command)
        return self.wait_for(phrase, timeout)
