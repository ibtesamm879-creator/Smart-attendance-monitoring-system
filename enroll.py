"""Register a student/teacher.

From webcam (captures several samples):
    python enroll.py --code 21-CS-01 --name "Ali Khan" --role student --dept CS

From existing photos in a folder:
    python enroll.py --code 21-CS-01 --name "Ali Khan" --role student --images ./ali_photos

Running it again with the same --code adds more samples (better accuracy).
"""
import argparse
from pathlib import Path

import cv2

import config
import database as db
from face_engine import encode_single_face, enroll_person

SAMPLES_WANTED = 6
PROMPTS = ["seedha dekho", "thoda left", "thoda right", "thoda upar", "thoda neeche", "smile karo"]


def capture_from_camera(n: int):
    cap = cv2.VideoCapture(config.CAMERA_SOURCE)
    if not cap.isOpened():
        raise SystemExit("Camera open nahi hua.")
    frames = []
    print("SPACE = photo lo | q = band karo")
    while len(frames) < n:
        ok, frame = cap.read()
        if not ok:
            break
        view = frame.copy()
        prompt = PROMPTS[len(frames) % len(PROMPTS)]
        cv2.putText(view, f"Sample {len(frames) + 1}/{n}: {prompt}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.imshow("Enroll", view)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" "):
            if encode_single_face(frame) is None:
                print("  ✗ Exactly ek clear face nahi mili, dobara try karo.")
            else:
                frames.append(frame)
                print(f"  ✓ Sample {len(frames)} captured")
    cap.release()
    cv2.destroyAllWindows()
    return frames


def load_from_folder(folder: str):
    imgs = []
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            img = cv2.imread(str(p))
            if img is not None:
                imgs.append(img)
    return imgs


def main():
    ap = argparse.ArgumentParser(description="Enroll a person")
    ap.add_argument("--code", required=True, help="roll no / employee id (unique)")
    ap.add_argument("--name", required=True)
    ap.add_argument("--role", choices=["student", "teacher"], default="student")
    ap.add_argument("--dept", default="")
    ap.add_argument("--images", help="folder of photos instead of webcam")
    ap.add_argument("--samples", type=int, default=SAMPLES_WANTED)
    args = ap.parse_args()

    db.init_db()
    images = load_from_folder(args.images) if args.images else capture_from_camera(args.samples)
    if not images:
        raise SystemExit("Koi image nahi mili.")

    pid, ok, bad = enroll_person(args.code, args.name, args.role, args.dept, images)
    print(f"Done: {args.name} (id={pid}) | accepted={ok} rejected={bad}")


if __name__ == "__main__":
    main()
