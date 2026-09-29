"""Live camera attendance.

Usage:
    python attendance_app.py                 # one camera, auto ENTRY/EXIT toggle
    python attendance_app.py --mode entry    # entrance camera (ENTRY only)
    python attendance_app.py --mode exit     # exit camera (EXIT only)
    python attendance_app.py --no-liveness   # disable blink check (testing only)

Keys: q = quit, r = reload face database.
"""
import argparse
import time
from dataclasses import dataclass
from datetime import datetime

import cv2
import face_recognition

import config
import database as db
from face_engine import FaceMatcher, distance_to_confidence, eye_aspect_ratio, to_rgb

FONT = cv2.FONT_HERSHEY_SIMPLEX
GREEN, RED, ORANGE, YELLOW = (0, 200, 0), (0, 0, 255), (0, 165, 255), (0, 215, 255)


@dataclass
class Track:
    last_seen: float
    streak: int = 0
    blinks: int = 0
    eyes_closed: bool = False
    flash_text: str = ""
    flash_until: float = 0.0


def save_snapshot(frame, loc, code, event_ts):
    top, right, bottom, left = loc
    pad = 40
    h, w = frame.shape[:2]
    crop = frame[max(top - pad, 0):min(bottom + pad, h), max(left - pad, 0):min(right + pad, w)]
    safe_ts = event_ts.replace(":", "-").replace(" ", "_")
    path = config.SNAP_DIR / f"{code}_{safe_ts}.jpg"
    cv2.imwrite(str(path), crop)
    return str(path.relative_to(config.BASE_DIR))


def process_frame(frame, matcher, tracks, mode, liveness):
    now = time.time()

    # forget faces that left the frame (liveness state resets for them)
    for pid in [p for p, t in tracks.items() if now - t.last_seen > config.TRACK_TIMEOUT]:
        del tracks[pid]

    small = cv2.resize(frame, (0, 0), fx=config.DETECT_SCALE, fy=config.DETECT_SCALE)
    small_locs = face_recognition.face_locations(to_rgb(small), model="hog")
    if not small_locs:
        return []

    inv = 1.0 / config.DETECT_SCALE
    locs = [tuple(int(v * inv) for v in loc) for loc in small_locs]
    rgb = to_rgb(frame)
    encodings = face_recognition.face_encodings(rgb, locs)

    results = []
    for loc, enc in zip(locs, encodings):
        pid, dist = matcher.identify(enc)
        if pid is None:
            results.append({"loc": loc, "label": "Unknown", "color": RED})
            continue

        person = matcher.people[pid]
        t = tracks.setdefault(pid, Track(last_seen=now))
        t.last_seen = now
        t.streak += 1

        # --- liveness: eye must close and re-open (blink) ---
        if liveness:
            ear = eye_aspect_ratio(rgb, loc)
            if ear is not None:
                if ear < config.EAR_THRESHOLD:
                    t.eyes_closed = True
                elif t.eyes_closed:
                    t.blinks += 1
                    t.eyes_closed = False
            live = t.blinks >= config.BLINKS_REQUIRED
        else:
            live = True

        if now < t.flash_until:                       # recently marked
            results.append({"loc": loc, "label": t.flash_text, "color": GREEN})
            continue

        if t.streak >= config.MIN_CONFIRM_FRAMES and live:
            conf = distance_to_confidence(dist, config.TOLERANCE)
            outcome = db.record_event(pid, confidence=conf, mode=mode)
            t.streak, t.blinks = 0, 0                 # next event needs a new blink
            if outcome:
                snap = save_snapshot(frame, loc, person["code"], outcome["timestamp"])
                db.set_snapshot(outcome["event_id"], snap)
                hhmm = outcome["timestamp"][11:16]
                t.flash_text = f'{person["name"]} - {outcome["event"]} {hhmm}'
            else:
                t.flash_text = f'{person["name"]} - already recorded'
            t.flash_until = now + 3
            results.append({"loc": loc, "label": t.flash_text, "color": GREEN})
        elif not live:
            results.append({"loc": loc, "label": f'{person["name"]} - blink karo', "color": ORANGE})
        else:
            results.append({"loc": loc, "label": f'{person["name"]} - verifying...', "color": YELLOW})
    return results


def draw(frame, results, mode, fps):
    for r in results:
        top, right, bottom, left = r["loc"]
        cv2.rectangle(frame, (left, top), (right, bottom), r["color"], 2)
        cv2.rectangle(frame, (left, bottom), (right, bottom + 26), r["color"], cv2.FILLED)
        cv2.putText(frame, r["label"], (left + 5, bottom + 18), FONT, 0.55,
                    (255, 255, 255), 1, cv2.LINE_AA)
    header = f"SmartAttend | mode: {mode} | {datetime.now():%H:%M:%S} | {fps:.0f} fps"
    cv2.putText(frame, header, (10, 22), FONT, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, "q: quit   r: reload", (10, frame.shape[0] - 10), FONT, 0.5,
                (200, 200, 200), 1, cv2.LINE_AA)


def run(mode: str, liveness: bool) -> None:
    db.init_db()
    matcher = FaceMatcher()
    if matcher.is_empty:
        print("Database mein koi face nahi hai. Pehle `python enroll.py` chalao.")
        return

    cap = cv2.VideoCapture(config.CAMERA_SOURCE)
    if not cap.isOpened():
        print("Camera open nahi hua. CAMERA_SOURCE check karo.")
        return

    tracks, results = {}, []
    frame_no, last_check, last_time, fps = 0, time.time(), time.time(), 0.0
    print(f"Started | mode={mode} | liveness={'ON' if liveness else 'OFF'} | q se band karo")

    while True:
        ok, frame = cap.read()
        if not ok:
            print("Camera se frame nahi mila.")
            break
        frame_no += 1

        if frame_no % config.PROCESS_EVERY_N_FRAMES == 0:
            results = process_frame(frame, matcher, tracks, mode, liveness)

        if time.time() - last_check > 5:              # pick up new enrolments
            if matcher.reload_if_changed():
                print("Face database reload ho gayi.")
            last_check = time.time()

        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / max(now - last_time, 1e-6))
        last_time = now

        draw(frame, results, mode, fps)
        cv2.imshow("SmartAttend", frame)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord("r"):
            matcher.reload()

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SmartAttend live camera")
    ap.add_argument("--mode", choices=["auto", "entry", "exit"], default="auto")
    ap.add_argument("--no-liveness", action="store_true", help="disable blink check")
    args = ap.parse_args()
    run(args.mode, liveness=config.REQUIRE_LIVENESS and not args.no_liveness)
