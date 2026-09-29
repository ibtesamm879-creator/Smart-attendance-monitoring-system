"""SQLite storage layer: people, face encodings, raw events, daily attendance."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, time as dtime

import numpy as np

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS people (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('student', 'teacher')),
    department  TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS encodings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    encoding   BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    event_type  TEXT NOT NULL CHECK (event_type IN ('ENTRY', 'EXIT')),
    timestamp   TEXT NOT NULL,
    confidence  REAL,
    snapshot    TEXT
);
CREATE TABLE IF NOT EXISTS attendance (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id      INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    date           TEXT NOT NULL,
    first_entry    TEXT,
    last_exit      TEXT,
    total_seconds  INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL CHECK (status IN ('Present', 'Late')),
    UNIQUE (person_id, date)
);
CREATE INDEX IF NOT EXISTS idx_events_person ON events (person_id, id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events (timestamp);
CREATE INDEX IF NOT EXISTS idx_att_date ON attendance (date);
"""


@contextmanager
def get_conn():
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.execute("PRAGMA journal_mode = WAL")  # camera + dashboard together
        conn.executescript(SCHEMA)


def _rows(cur) -> list:
    return [dict(r) for r in cur.fetchall()]


def _late_time() -> dtime:
    h, m = (int(x) for x in config.LATE_AFTER.split(":"))
    return dtime(h, m)


# ================================================================ people
def add_person(code: str, name: str, role: str, department: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO people (code, name, role, department, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (code.strip(), name.strip(), role, department.strip(),
             datetime.now().isoformat(sep=" ", timespec="seconds")),
        )
        return cur.lastrowid


def get_person_by_code(code: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM people WHERE code = ?", (code.strip(),)).fetchone()
        return dict(row) if row else None


def list_people() -> list:
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT p.id, p.code, p.name, p.role, p.department, p.created_at, "
            "(SELECT COUNT(*) FROM encodings e WHERE e.person_id = p.id) AS face_samples "
            "FROM people p ORDER BY p.role, p.name"))


def delete_person(person_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM people WHERE id = ?", (person_id,))


# ============================================================== encodings
def add_encodings(person_id: int, encodings) -> None:
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO encodings (person_id, encoding) VALUES (?, ?)",
            [(person_id, np.asarray(e, dtype=np.float64).tobytes()) for e in encodings],
        )


def load_encodings():
    """Return (person_ids, encodings[N,128], {id: {name, code, role}})."""
    with get_conn() as conn:
        rows = conn.execute("SELECT person_id, encoding FROM encodings").fetchall()
        people = {r["id"]: {"name": r["name"], "code": r["code"], "role": r["role"]}
                  for r in conn.execute("SELECT id, name, code, role FROM people")}
    ids = [r["person_id"] for r in rows]
    encs = (np.array([np.frombuffer(r["encoding"], dtype=np.float64) for r in rows])
            if rows else np.empty((0, 128)))
    return ids, encs, people


def encodings_signature():
    """Cheap fingerprint so the camera app can notice new enrolments."""
    with get_conn() as conn:
        r = conn.execute("SELECT COUNT(*) AS n, COALESCE(MAX(id), 0) AS m FROM encodings").fetchone()
        return (r["n"], r["m"])


# ================================================================ events
def record_event(person_id: int, confidence=None, snapshot=None, now=None, mode="auto"):
    """Record an ENTRY or EXIT for a person and update the daily attendance row.

    mode: "auto"  -> toggles ENTRY/EXIT (single camera)
          "entry" -> only ENTRY allowed (entrance camera)
          "exit"  -> only EXIT allowed (exit camera)

    Returns a dict describing the event, or None if it was ignored
    (cooldown, duplicate, or EXIT without a matching ENTRY).
    """
    now = (now or datetime.now()).replace(microsecond=0)
    ts = now.isoformat(sep=" ")
    day = now.date().isoformat()

    with get_conn() as conn:
        last = conn.execute(
            "SELECT event_type, timestamp FROM events WHERE person_id = ? "
            "ORDER BY id DESC LIMIT 1", (person_id,)).fetchone()

        last_type = None
        if last:
            last_ts = datetime.fromisoformat(last["timestamp"])
            if 0 <= (now - last_ts).total_seconds() < config.COOLDOWN_SECONDS:
                return None
            if last_ts.date() == now.date():
                last_type = last["event_type"]

        if mode == "entry":
            event = "ENTRY"
        elif mode == "exit":
            event = "EXIT"
        else:
            event = "EXIT" if last_type == "ENTRY" else "ENTRY"

        if event == last_type:                       # already inside / outside
            return None
        if event == "EXIT" and last_type != "ENTRY":  # exit with no entry today
            return None

        cur = conn.execute(
            "INSERT INTO events (person_id, event_type, timestamp, confidence, snapshot) "
            "VALUES (?, ?, ?, ?, ?)", (person_id, event, ts, confidence, snapshot))
        event_id = cur.lastrowid

        if event == "ENTRY":
            status = "Late" if now.time() > _late_time() else "Present"
            conn.execute(
                "INSERT OR IGNORE INTO attendance "
                "(person_id, date, first_entry, total_seconds, status) VALUES (?, ?, ?, 0, ?)",
                (person_id, day, ts, status))
        else:
            entry = conn.execute(
                "SELECT timestamp FROM events WHERE person_id = ? AND event_type = 'ENTRY' "
                "AND date(timestamp) = ? ORDER BY id DESC LIMIT 1", (person_id, day)).fetchone()
            stay = int((now - datetime.fromisoformat(entry["timestamp"])).total_seconds())
            conn.execute(
                "UPDATE attendance SET total_seconds = total_seconds + ?, last_exit = ? "
                "WHERE person_id = ? AND date = ?", (max(stay, 0), ts, person_id, day))

    return {"event_id": event_id, "event": event, "timestamp": ts, "person_id": person_id}


def set_snapshot(event_id: int, path: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE events SET snapshot = ? WHERE id = ?", (path, event_id))


def recent_events(limit: int = 50) -> list:
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT e.timestamp, p.name, p.code, p.role, e.event_type, e.confidence, e.snapshot "
            "FROM events e JOIN people p ON p.id = e.person_id "
            "ORDER BY e.id DESC LIMIT ?", (limit,)))


def currently_inside(day: str) -> list:
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT p.name, p.code, e.timestamp FROM people p "
            "JOIN events e ON e.id = (SELECT id FROM events WHERE person_id = p.id "
            "                         ORDER BY id DESC LIMIT 1) "
            "WHERE e.event_type = 'ENTRY' AND date(e.timestamp) = ?", (day,)))


# ============================================================== reporting
def daily_report(day: str) -> list:
    """One row per registered person, including those who were Absent."""
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT p.code, p.name, p.role, p.department, "
            "  COALESCE(a.status, 'Absent') AS status, "
            "  substr(a.first_entry, 12, 8) AS first_entry, "
            "  substr(a.last_exit, 12, 8) AS last_exit, "
            "  ROUND(COALESCE(a.total_seconds, 0) / 60.0, 1) AS minutes_in_class "
            "FROM people p LEFT JOIN attendance a ON a.person_id = p.id AND a.date = ? "
            "ORDER BY p.role, p.name", (day,)))


def attendance_records(start: str, end: str) -> list:
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT a.date, p.code, p.name, p.role, a.status, "
            "  substr(a.first_entry, 12, 8) AS first_entry, "
            "  substr(a.last_exit, 12, 8) AS last_exit, "
            "  ROUND(a.total_seconds / 60.0, 1) AS minutes_in_class "
            "FROM attendance a JOIN people p ON p.id = a.person_id "
            "WHERE a.date BETWEEN ? AND ? ORDER BY a.date, p.name", (start, end)))


def class_days(start: str, end: str) -> int:
    """Days in range on which at least one person was marked."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(DISTINCT date) FROM attendance WHERE date BETWEEN ? AND ?",
            (start, end)).fetchone()[0]


def attendance_summary(start: str, end: str) -> list:
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT p.code, p.name, p.role, COUNT(a.id) AS days_present, "
            "  COALESCE(SUM(a.status = 'Late'), 0) AS days_late, "
            "  ROUND(COALESCE(SUM(a.total_seconds), 0) / 3600.0, 1) AS hours_in_class "
            "FROM people p LEFT JOIN attendance a "
            "  ON a.person_id = p.id AND a.date BETWEEN ? AND ? "
            "GROUP BY p.id ORDER BY p.name", (start, end)))


def daily_counts(start: str, end: str) -> list:
    with get_conn() as conn:
        return _rows(conn.execute(
            "SELECT date, COUNT(*) AS present, "
            "  COALESCE(SUM(status = 'Late'), 0) AS late "
            "FROM attendance WHERE date BETWEEN ? AND ? GROUP BY date ORDER BY date",
            (start, end)))
