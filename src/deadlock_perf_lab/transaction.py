"""Write-ahead file transactions with checksum-verified crash recovery."""
from __future__ import annotations

from pathlib import Path
import stat

from .storage import LabError, atomic_write, digest, read_json, write_json


class Transaction:
    def __init__(self, journal: Path):
        self.path = journal
        self.data = read_json(journal) if journal.exists() else {"schema": 1, "state": "new", "files": [], "processes": {}}

    def save(self) -> None:
        write_json(self.path, self.data)

    def apply(self, target: Path, content: bytes) -> None:
        target = target.absolute()
        if target.is_symlink():
            raise LabError(f"Refusing to replace a symlink: {target}")
        if any(item["target"] == str(target) for item in self.data["files"]):
            raise LabError(f"Target already part of this transaction: {target}")
        if target.exists() and not target.is_file():
            raise LabError(f"Not a regular file: {target}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        backup = self.path.parent / "backup" / f"{len(self.data['files']):02d}-{target.name}"
        exists = target.exists()
        before = digest(target) if exists else None
        mode = stat.S_IMODE(target.stat().st_mode) if exists else 0o644
        if exists:
            atomic_write(backup, target.read_bytes(), mode=0o600)
            if digest(backup) != before:
                raise LabError(f"Target changed during backup: {target}")
        import hashlib
        entry = {"target": str(target), "backup": str(backup), "existed": exists,
                 "before_sha256": before, "applied_sha256": hashlib.sha256(content).hexdigest(), "mode": mode}
        self.data["files"].append(entry)
        self.data["state"] = "pending"
        self.save()  # Must reach disk before the live write.
        if (digest(target) if target.is_file() else None) != before:
            raise LabError(f"Target changed before apply: {target}")
        atomic_write(target, content, mode)
        if digest(target) != entry["applied_sha256"]:
            raise LabError(f"Write verification failed: {target}")

    def track_processes(self, processes: dict[int, str]) -> None:
        self.data["processes"] = {str(pid): start for pid, start in processes.items()}
        self.save()

    def restore(self, *, force: bool = False) -> None:
        if self.data["state"] == "restored":
            return
        # Validate ALL entries first so a conflict leaves an actionable journal.
        for entry in self.data["files"]:
            target = Path(entry["target"])
            backup = Path(entry["backup"])
            if target.is_symlink():
                raise LabError(f"Restore blocked by symlink: {target}")
            if entry["existed"] and (not backup.is_file() or digest(backup) != entry["before_sha256"]):
                raise LabError(f"Backup missing or corrupt: {backup}. Restore stopped.")
            current = digest(target) if target.is_file() else None
            if current not in {entry["before_sha256"], entry["applied_sha256"]}:
                if not force:
                    raise LabError(f"{target} changed outside this run. Recovery stopped; inspect it, then use dpl recover --force if appropriate.")
                if target.is_file():
                    atomic_write(self.path.parent / "conflicts" / backup.name, target.read_bytes(), 0o600)
        for entry in reversed(self.data["files"]):
            target = Path(entry["target"])
            if entry["existed"]:
                atomic_write(target, Path(entry["backup"]).read_bytes(), entry["mode"])
            elif target.exists():
                target.unlink()
            current = digest(target) if target.exists() else None
            if current != entry["before_sha256"]:
                raise LabError(f"Restore verification failed: {target}")
        self.data["state"] = "restored"
        self.save()
