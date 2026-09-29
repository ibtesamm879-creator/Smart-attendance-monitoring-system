"""Central configuration for SmartAttend.

Every tunable setting lives here. Most can also be overridden with
environment variables (e.g. CAMERA_SOURCE, ADMIN_PASSWORD).
"""
import os
from pathlib import Path

# ---------------------------------------------------------------- paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
FACES_DIR = DATA_DIR / "faces"          # enrolment photos
SNAP_DIR = DATA_DIR / "snapshots"       # audit snapshot for every entry/exit
DB_PATH = DATA_DIR / "attendance.db"

# --------------------------------------------------------------- camera
# 0 = default webcam, 1 = second camera, or an IP/RTSP url string
_cam = os.getenv("CAMERA_SOURCE", "0")
CAMERA_SOURCE = int(_cam) if _cam.isdigit() else _cam

# ---------------------------------------------------------- recognition
TOLERANCE = 0.50            # lower = stricter (0.6 is library default)
AMBIGUITY_MARGIN = 0.04     # best match must beat 2nd-best person by this much
DETECT_SCALE = 0.5          # frames are shrunk by this factor for detection
PROCESS_EVERY_N_FRAMES = 2  # skip frames to keep video smooth
MIN_CONFIRM_FRAMES = 3      # same person must be seen this many times in a row
COOLDOWN_SECONDS = 60       # min gap between two events of the same person
TRACK_TIMEOUT = 3.0         # forget a face after this many seconds unseen

# ------------------------------------------------- anti-spoofing (liveness)
REQUIRE_LIVENESS = True     # person must blink -> stops photo/phone proxy
EAR_THRESHOLD = 0.21        # eye-aspect-ratio below this = eye closed
BLINKS_REQUIRED = 1

# --------------------------------------------------------- class timing
LATE_AFTER = "09:15"        # HH:MM, first entry after this = "Late"
LOW_ATTENDANCE_THRESHOLD = 75   # % shown as warning in analytics

# ------------------------------------------------------------ dashboard
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")   # change this!


def ensure_dirs() -> None:
    for d in (DATA_DIR, FACES_DIR, SNAP_DIR):
        d.mkdir(parents=True, exist_ok=True)
