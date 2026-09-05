import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deadlock_perf_lab.storage import LabError, exclusive_lock, read_json
from deadlock_perf_lab.transaction import Transaction


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "gameinfo.gi"
        self.target.write_bytes(b"original\n")
        self.target.chmod(0o640)
        self.journal = self.root / "run/transaction.json"

    def test_round_trip_preserves_content_mode_and_absence(self):
        txn = Transaction(self.journal)
        txn.apply(self.target, b"changed")
        extra = self.root / "autoexec_dpl.cfg"
        txn.apply(extra, b"fps_max 0")
        txn.restore()
        self.assertEqual(self.target.read_bytes(), b"original\n")
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o640)
        self.assertFalse(extra.exists())
        self.assertEqual(read_json(self.journal)["state"], "restored")
        txn.restore()

    def test_new_process_recovers_journal(self):
        Transaction(self.journal).apply(self.target, b"changed")
        Transaction(self.journal).restore()
        self.assertEqual(self.target.read_bytes(), b"original\n")

    def test_unexpected_edits_are_not_overwritten(self):
        txn = Transaction(self.journal)
        txn.apply(self.target, b"changed")
        self.target.write_bytes(b"user edited while running")
        with self.assertRaisesRegex(LabError, "changed outside"):
            txn.restore()
        self.assertEqual(self.target.read_bytes(), b"user edited while running")
        txn.restore(force=True)
        self.assertEqual(next((self.journal.parent / "conflicts").iterdir()).read_bytes(), b"user edited while running")
        self.assertEqual(self.target.read_bytes(), b"original\n")

    def test_corrupt_backup_is_fatal_even_with_force(self):
        txn = Transaction(self.journal)
        txn.apply(self.target, b"changed")
        Path(txn.data["files"][0]["backup"]).write_bytes(b"bad")
        with self.assertRaisesRegex(LabError, "corrupt"):
            txn.restore(force=True)
        self.assertEqual(self.target.read_bytes(), b"changed")

    def test_write_ahead_journal_survives_failed_write(self):
        from deadlock_perf_lab.storage import atomic_write
        def fail_target(path, content, mode=None):
            if path == self.target:
                raise OSError("disk failure")
            atomic_write(path, content, mode)
        with patch("deadlock_perf_lab.transaction.atomic_write", side_effect=fail_target):
            with self.assertRaises(OSError):
                Transaction(self.journal).apply(self.target, b"changed")
        self.assertEqual(read_json(self.journal)["state"], "pending")
        Transaction(self.journal).restore()
        self.assertEqual(self.target.read_bytes(), b"original\n")

    def test_symlink_refused(self):
        link = self.root / "link"
        link.symlink_to(self.target)
        with self.assertRaisesRegex(LabError, "symlink"):
            Transaction(self.journal).apply(link, b"changed")

    @unittest.skipUnless(os.name == "posix", "Linux locking")
    def test_competing_lock_fails_and_releases(self):
        path = self.root / "lock"
        with exclusive_lock(path):
            with self.assertRaises(LabError):
                with exclusive_lock(path):
                    pass
        with exclusive_lock(path):
            pass
