# SmartAttend — Camera-Based Smart Attendance System

An AI-powered attendance system that uses face detection and recognition to mark
students and teachers automatically as they enter and leave a classroom, with
anti-spoofing, a secure database, and an admin analytics dashboard.

## 1. What's new compared to the basic version

| Basic idea | This version |
|---|---|
| CSV file storage | SQLite database (people, encodings, events, daily attendance) |
| Face match only | Match + **blink liveness check** (photo / phone-screen proxy is blocked) |
| Simple nearest match | Per-person best match + **ambiguity margin** (refuses look-alike confusion) |
| One-time mark | **Entry/Exit toggle**, cooldown, per-day duration, Late status |
| No proof | **Snapshot saved for every event** (audit trail) |
| Console only | **Streamlit dashboard**: live log, daily report, analytics, enrolment |
| Manual | Two-camera mode (`--mode entry` / `--mode exit`) |
| Untested | Unit tests for all attendance logic |

## 2. Objectives
- **Automation** – no manual roll call.
- **Accuracy** – multi-sample enrolment, strict tolerance, ambiguity check.
- **Anti-proxy** – liveness (blink) verification + snapshot audit trail.
- **Efficiency** – real-time logs, reports, Excel/CSV export.
- **Security** – local database, password-protected admin dashboard.

## 3. Functional requirements
- FR1 Face detection in real time (HOG, on a downscaled frame for speed).
- FR2 Face recognition against the enrolled database (128-d encodings).
- FR3 Automatic "Present" / "Late" marking on first entry of the day.
- FR4 Exact ENTRY / EXIT timestamps.
- FR5 Total time in class per day.
- FR6 Profile + multi-photo management (CLI and dashboard).
- FR7 Live logs and snapshots for the administrator.
- FR8 Daily report, date-range analytics, low-attendance warnings, CSV/Excel export.

## 4. Non-functional requirements
- Accuracy target: 90%+ on well-lit frontal faces (depends on enrolment quality).
- Response: recognition within 1–2 s on a normal laptop CPU.
- Usability: one-command enrolment, browser dashboard.
- Scalability: hundreds of people (encodings held in memory; SQLite storage).
- Low cost: 100% open source (OpenCV, dlib / face_recognition, Streamlit, SQLite).

## 5. Architecture

```
Camera ──► attendance_app.py ──► face_engine.py (detect → encode → match → blink check)
                │                                   │
                └────────────► database.py (SQLite) ◄┘
                                      ▲
enroll.py / dashboard.py ─────────────┘
```

| File | Purpose |
|---|---|
| `config.py` | All settings (tolerance, cooldown, late time, camera…) |
| `database.py` | SQLite schema + attendance logic |
| `face_engine.py` | Encoding, matching, liveness, enrolment |
| `attendance_app.py` | Live camera recognition |
| `enroll.py` | Register people from webcam or photo folder |
| `dashboard.py` | Admin web dashboard |
| `demo_data.py` | Fake data for demos without a camera |
| `tests/` | Unit tests |

## 6. Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
```

**If `dlib` fails to install** (common on Windows):
- Install CMake and *Visual Studio Build Tools (C++)*, then retry, **or**
- Try prebuilt wheels: `pip install dlib-bin` then `pip install face-recognition --no-deps`.

## 7. Usage

```bash
# 1. Register people (webcam: press SPACE for each sample)
python enroll.py --code 21-CS-01 --name "Ali Khan" --role student --dept CS
python enroll.py --code T-01 --name "Dr. Kamran" --role teacher --images ./photos/kamran

# 2. Start the live camera
python attendance_app.py                 # single camera, auto toggle
python attendance_app.py --mode entry    # entrance camera
python attendance_app.py --mode exit     # exit camera (second terminal)

# 3. Admin dashboard (default password: admin123)
set ADMIN_PASSWORD=YourStrongPassword    # Windows  (Linux/Mac: export ...)
streamlit run dashboard.py

# Demo dashboard without camera / faces
python demo_data.py
streamlit run dashboard.py
```

Press **q** in the camera window to quit, **r** to reload the face database.
New people enrolled from the dashboard are picked up automatically within ~5 s.

## 8. Tips for best accuracy
- Enrol 5–6 photos: straight, slightly left/right/up/down, with normal lighting.
- Put the camera at face height, facing the door, with light in front of people (not behind).
- Tune `TOLERANCE` in `config.py` (lower = stricter, fewer false matches).
- Set `LATE_AFTER` and `COOLDOWN_SECONDS` to match your class timing.

## 9. Testing
```bash
python -m unittest discover tests -v
```

## 10. Limitations & future work
- Blink liveness stops photos and most screens, but not a determined 3D-mask attack;
  a depth camera or a trained anti-spoof model would be the next step.
- Use only with consent of enrolled people and store data securely (face data is sensitive).
- Possible extensions: email/WhatsApp alerts for absentees, mask-aware recognition,
  GPU model (InsightFace/ArcFace), multi-classroom timetable integration.
