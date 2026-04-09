import cv2
import numpy as np
from PIL import Image
import os

# Locate the Haar Cascade XML provided by opencv-python
CV2_BASE = os.path.dirname(cv2.__file__)
FACE_CASCADE_PATH = os.path.join(CV2_BASE, "data", "haarcascade_frontalface_default.xml")

def get_face_landmarks(pil_img: Image.Image):
    """
    Detects a face using OpenCV and returns a normalized (0-1000)
    center-point crop box for passport/ID-style framing.
    Returns (cx, cy, width, height) or None if no face is found.
    """
    cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)

    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    faces = face_cascade.detectMultiScale(gray, 1.2, 6)

    if len(faces) == 0:
        return None

    # Pick the largest face
    (fx, fy, fw, fh) = sorted(
        faces, key=lambda f: f[2] * f[3], reverse=True
    )[0]

    img_h, img_w = gray.shape[:2]

    # --- Passport-Standard Crop Math ---
    # Haar gives: fy = top of forehead, fy+fh = chin
    # Face center = (fx + fw/2, fy + fh/2)
    face_center_x = fx + fw / 2
    face_center_y = fy + fh / 2

    # Crop box = 1.5x face height (tight head + shoulders)
    crop_size = fh * 1.5

    # Vertical placement: We want ~12% headroom above the hair.
    # Hair top ≈ fy (top of detection box).
    # Desired crop_top = fy - (0.12 * crop_size)
    # Therefore crop_center_y = crop_top + crop_size/2
    crop_top = fy - (0.12 * crop_size)
    crop_center_y = crop_top + crop_size / 2

    # Horizontal: perfectly centered on face
    crop_center_x = face_center_x

    # Normalize to 0-1000
    nx = int((crop_center_x / img_w) * 1000)
    ny = int((crop_center_y / img_h) * 1000)
    nw = int((crop_size / img_w) * 1000)
    nh = int((crop_size / img_h) * 1000)

    return (nx, ny, nw, nh)
