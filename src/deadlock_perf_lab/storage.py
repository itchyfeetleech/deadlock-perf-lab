"""Small, durable JSON storage and exclusive workspace locks."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Iterator


class LabError(Exception):
    """Actionable failure, printed without a traceback by the CLI."""


def read_json(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            value = json.load(f)
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (OSError, ValueError) as exc:
        raise LabError(f"Cannot read {path}: {exc}") from exc


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            os.chmod(name, mode)
        os.replace(name, path)
        # Persist rename before recording the next journal state.
        if hasattr(os, "O_DIRECTORY"):
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def write_json(path: Path, value: dict) -> None:
    atomic_write(path, (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode())


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


@contextlib.contextmanager
def exclusive_lock(path: Path) -> Iterator[None]:
    """flock releases on process death; the lock file must never be unlinked."""
    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise LabError(f"Another operation holds {path}. Let it finish or cancel it first.") from exc
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
