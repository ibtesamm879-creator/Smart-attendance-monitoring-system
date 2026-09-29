"""Fill the database with fake people + 3 weeks of attendance so you can
demo the dashboard without a camera.   Run:  python demo_data.py
"""
import random
from datetime import date, datetime, timedelta

import database as db

PEOPLE = [
    ("21-CS-01", "Ali Khan", "student"), ("21-CS-02", "Fatima Noor", "student"),
    ("21-CS-03", "Hamza Iqbal", "student"), ("21-CS-04", "Ayesha Malik", "student"),
    ("21-CS-05", "Usman Tariq", "student"), ("21-CS-06", "Sana Riaz", "student"),
    ("21-CS-07", "Bilal Ahmed", "student"), ("21-CS-08", "Hira Shah", "student"),
    ("T-01", "Dr. Kamran Butt", "teacher"), ("T-02", "Ms. Rabia Saleem", "teacher"),
]


def main(days_back: int = 21) -> None:
    random.seed(7)
    db.init_db()
    ids = {}
    for code, name, role in PEOPLE:
        p = db.get_person_by_code(code)
        ids[code] = p["id"] if p else db.add_person(code, name, role, "Computer Science")

    reliability = {code: random.uniform(0.6, 0.98) for code in ids}   # some skip more
    today = date.today()
    count = 0
    for offset in range(days_back, 0, -1):
        day = today - timedelta(days=offset)
        if day.weekday() >= 5:                       # skip Sat/Sun
            continue
        for code, pid in ids.items():
            if random.random() > reliability[code]:
                continue                             # absent
            entry = datetime(day.year, day.month, day.day, 8, 45) + timedelta(
                minutes=random.randint(0, 45))
            leave = datetime(day.year, day.month, day.day, 13, 0) + timedelta(
                minutes=random.randint(0, 150))
            db.record_event(pid, confidence=round(random.uniform(75, 98), 1), now=entry)
            db.record_event(pid, confidence=round(random.uniform(75, 98), 1), now=leave)
            count += 1
    print(f"Demo data ready: {len(ids)} people, {count} attendance days.")


if __name__ == "__main__":
    main()
