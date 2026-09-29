"""Face recognition helpers: encoding, matching, blink-based liveness, enrolment."""
import cv2
import numpy as np
import face_recognition

import config
import database as db


# ------------------------------------------------------------ utilities
def to_rgb(img_bgr):
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def _resize_max_width(img, max_w: int = 800):
    h, w = img.shape[:2]
    if w <= max_w:
        return img
    scale = max_w / w
    return cv2.resize(img, (max_w, int(h * scale)))


def distance_to_confidence(distance: float, tolerance: float) -> float:
    """Map a face distance to a 0-100 confidence score."""
    if distance > tolerance:
        return round(max(0.0, (1.0 - distance) / ((1.0 - tolerance) * 2.0)) * 100, 1)
    lin = (1.0 - distance) / ((1.0 - tolerance) * 2.0)
    return round((lin + ((1.0 - lin) * ((lin - 0.5) * 2.0) ** 0.2)) * 100, 1)


# ------------------------------------------------------------- liveness
def _ear(eye_points) -> float:
    p = np.array(eye_points, dtype=float)
    vertical = np.linalg.norm(p[1] - p[5]) + np.linalg.norm(p[2] - p[4])
    horizontal = np.linalg.norm(p[0] - p[3])
    return vertical / (2.0 * horizontal) if horizontal else 0.0


def eye_aspect_ratio(rgb, location):
    """Average eye-aspect-ratio for the face at `location` (None if no landmarks)."""
    marks = face_recognition.face_landmarks(rgb, [location])
    if not marks:
        return None
    m = marks[0]
    return (_ear(m["left_eye"]) + _ear(m["right_eye"])) / 2.0


# ------------------------------------------------------------- matching
class FaceMatcher:
    """Holds all known encodings in memory and identifies faces against them."""

    def __init__(self):
        self.ids, self.encodings, self.people = [], np.empty((0, 128)), {}
        self._signature = None
        self.reload()

    def reload(self) -> None:
        self.ids, self.encodings, self.people = db.load_encodings()
        self._signature = db.encodings_signature()

    def reload_if_changed(self) -> bool:
        sig = db.encodings_signature()
        if sig != self._signature:
            self.reload()
            return True
        return False

    @property
    def is_empty(self) -> bool:
        return len(self.ids) == 0

    def identify(self, encoding):
        """Return (person_id | None, distance)."""
        if self.is_empty:
            return None, 1.0
        dists = face_recognition.face_distance(self.encodings, encoding)
        best = {}
        for pid, d in zip(self.ids, dists):
            if d < best.get(pid, 9.0):
                best[pid] = d
        ranked = sorted(best.items(), key=lambda kv: kv[1])
        pid, dist = ranked[0]
        if dist > config.TOLERANCE:
            return None, float(dist)
        if len(ranked) > 1 and ranked[1][1] - dist < config.AMBIGUITY_MARGIN:
            return None, float(dist)          # too close to someone else -> refuse
        return pid, float(dist)


# ------------------------------------------------------------ enrolment
def encode_single_face(img_bgr):
    """Return a 128-d encoding if the image has exactly one face, else None."""
    rgb = to_rgb(_resize_max_width(img_bgr))
    locs = face_recognition.face_locations(rgb, model="hog")
    if len(locs) != 1:
        return None
    return face_recognition.face_encodings(rgb, locs, num_jitters=5)[0]


def enroll_person(code, name, role, department, images_bgr):
    """Register (or add more samples to) a person from a list of BGR images.

    Returns (person_id, accepted_count, rejected_count).
    """
    encodings, accepted_imgs, rejected = [], [], 0
    for img in images_bgr:
        enc = encode_single_face(img)
        if enc is None:
            rejected += 1
        else:
            encodings.append(enc)
            accepted_imgs.append(img)
    if not encodings:
        raise ValueError("Kisi bhi photo mein exactly ek clear face nahi mili.")

    existing = db.get_person_by_code(code)
    person_id = existing["id"] if existing else db.add_person(code, name, role, department)
    db.add_encodings(person_id, encodings)

    config.ensure_dirs()
    folder = config.FACES_DIR / code.strip()
    folder.mkdir(parents=True, exist_ok=True)
    start = len(list(folder.glob("*.jpg")))
    for i, img in enumerate(accepted_imgs, start=start + 1):
        cv2.imwrite(str(folder / f"{i:02d}.jpg"), _resize_max_width(img))
    return person_id, len(encodings), rejected
