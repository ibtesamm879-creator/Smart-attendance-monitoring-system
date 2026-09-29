"""Run:  python -m unittest discover tests -v"""
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import database as db


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        config.DATA_DIR = root
        config.FACES_DIR = root / "faces"
        config.SNAP_DIR = root / "snaps"
        config.DB_PATH = root / "test.db"
        db.init_db()
        self.pid = db.add_person("T-1", "Test Student", "student", "CS")

    def tearDown(self):
        self.tmp.cleanup()

    def test_entry_then_exit_and_duration(self):
        e = db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 0))
        x = db.record_event(self.pid, now=datetime(2026, 3, 2, 11, 30))
        self.assertEqual(e["event"], "ENTRY")
        self.assertEqual(x["event"], "EXIT")
        row = db.daily_report("2026-03-02")[0]
        self.assertEqual(row["status"], "Present")
        self.assertEqual(row["minutes_in_class"], 150.0)

    def test_late_status(self):
        db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 40))
        self.assertEqual(db.daily_report("2026-03-02")[0]["status"], "Late")

    def test_cooldown_blocks_double_scan(self):
        self.assertIsNotNone(db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 0, 0)))
        self.assertIsNone(db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 0, 20)))

    def test_forced_modes(self):
        self.assertIsNone(db.record_event(self.pid, mode="exit", now=datetime(2026, 3, 2, 9, 0)))
        self.assertIsNotNone(db.record_event(self.pid, mode="entry", now=datetime(2026, 3, 2, 9, 5)))
        self.assertIsNone(db.record_event(self.pid, mode="entry", now=datetime(2026, 3, 2, 9, 30)))
        self.assertIsNotNone(db.record_event(self.pid, mode="exit", now=datetime(2026, 3, 2, 10, 0)))

    def test_absent_person_in_report(self):
        other = db.add_person("T-2", "Absent Guy", "student")
        db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 0))
        statuses = {r["code"]: r["status"] for r in db.daily_report("2026-03-02")}
        self.assertEqual(statuses["T-2"], "Absent")
        self.assertEqual(statuses["T-1"], "Present")
        self.assertIsNotNone(other)

    def test_new_day_starts_with_entry(self):
        db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 0))      # forgot to exit
        nxt = db.record_event(self.pid, now=datetime(2026, 3, 3, 9, 0))
        self.assertEqual(nxt["event"], "ENTRY")

    def test_summary_and_class_days(self):
        db.record_event(self.pid, now=datetime(2026, 3, 2, 9, 0))
        db.record_event(self.pid, now=datetime(2026, 3, 3, 9, 30))
        self.assertEqual(db.class_days("2026-03-01", "2026-03-31"), 2)
        s = db.attendance_summary("2026-03-01", "2026-03-31")[0]
        self.assertEqual((s["days_present"], s["days_late"]), (2, 1))


if __name__ == "__main__":
    unittest.main()
