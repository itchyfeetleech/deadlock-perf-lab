"""Create one-cvar GameInfo variants from a reviewed CSV matrix."""
from __future__ import annotations

import csv
from pathlib import Path
import re

from .profiles import catalog, validate, validate_autoexec, validate_gameinfo
from .storage import LabError, digest, write_json

TOKEN = re.compile(r'//[^\n]*|"(?:\\.|[^"\\])*"|[{}]|[^\s{}"]+')


def convar_spans(content: str) -> tuple[dict[str, list[tuple[int, int, str]]], int]:
    """Locate direct ConVars leaf values; do not regex-replace other sections."""
    tokens = [m for m in TOKEN.finditer(content) if not m[0].startswith("//")]
    entries: dict[str, list[tuple[int, int, str]]] = {}
    closes = []
    index = 0

    def parse(path: list[str], nested: bool = False):
        nonlocal index
        while index < len(tokens):
            key = tokens[index]
            if key[0] == "}":
                if not nested:
                    raise LabError("Unexpected closing brace in GameInfo.")
                if path and path[-1].lower() == "convars":
                    closes.append(key.start())
                index += 1
                return
            name = key[0].strip('"')
            index += 1
            if index >= len(tokens):
                raise LabError("GameInfo has a key without a value.")
            value = tokens[index]
            index += 1
            if value[0] == "{":
                parse(path + [name], True)
            elif value[0] == "}":
                raise LabError("GameInfo key has no value before closing brace.")
            elif path and path[-1].lower() == "convars":
                entries.setdefault(name.lower(), []).append((value.start(), value.end(), value[0].strip('"')))
        if nested:
            raise LabError("Unclosed GameInfo block.")

    parse([])
    if len(closes) != 1:
        raise LabError("Sweep generation requires exactly one ConVars block.")
    return entries, closes[0]


def same_value(a: str, b: str) -> bool:
    aliases = {"true": "1", "false": "0"}
    a, b = aliases.get(a.lower(), a), aliases.get(b.lower(), b)
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def variants(base: str, rows: list[dict]) -> list[dict]:
    validate_gameinfo(base)
    spans, closing = convar_spans(base)
    output = []
    ids = set()
    for row in rows:
        case, cvar, value = (row.get(k, "").strip() for k in ("id", "cvar", "value"))
        validate_autoexec(f'{cvar} "{value}"')
        if not value:
            raise LabError(f"{case}: value cannot be empty.")
        matches = spans.get(cvar.lower(), [])
        if len(matches) > 1:
            raise LabError(f"{case}: {cvar} occurs multiple times; resolve duplicate definitions first.")
        if case in ids:
            raise LabError(f"Duplicate matrix ID: {case}")
        ids.add(case)
        before = matches[0][2] if matches else None
        if before is not None and same_value(before, value):
            raise LabError(f"{case}: {cvar} already equals {value}; this would benchmark an unchanged config.")
        if matches:
            start, end, _ = matches[0]
            content = base[:start] + f'"{value}"' + base[end:]
        else:
            content = base[:closing] + f'\n        {cvar} "{value}"\n    ' + base[closing:]
        profile = {"id": case, "name": row.get("name") or case, "kind": "gameinfo", "category": "custom",
                   "status": "experimental", "description": f"Change only {cvar}: {before if before is not None else 'unset'} → {value}.",
                   "content": content, "cvar": cvar, "requested_value": value, "base_value": before}
        output.append(validate(profile))
    if not output:
        raise LabError("Matrix has no rows.")
    return output


def create_sweep(workspace: Path, base_path: Path, matrix_path: Path) -> list[Path]:
    with matrix_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not {"id", "cvar", "value"}.issubset(reader.fieldnames or []):
            raise LabError("Matrix needs id,cvar,value columns; name is optional.")
        rows = list(reader)
    profiles = variants(base_path.read_text(encoding="utf-8"), rows)
    existing = catalog(workspace)
    if any(p["id"] in existing for p in profiles):
        raise LabError("A matrix ID already exists. Use distinct IDs; existing profiles are not overwritten.")
    base_hash = digest(base_path)
    written = []
    try:
        for profile in profiles:
            profile["base_sha256"] = base_hash
            path = workspace / "profiles" / f"{profile['id']}.json"
            write_json(path, profile)
            written.append(path)
    except OSError:
        for path in written:
            path.unlink()
        raise
    return written
