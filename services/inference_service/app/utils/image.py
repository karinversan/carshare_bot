import base64
import hashlib
import io
import random
from typing import Tuple

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None
import numpy as np
from PIL import Image, ImageDraw

def pil_from_bytes(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")

def np_from_pil(image: Image.Image) -> np.ndarray:
    rgb = np.array(image)
    if cv2 is None:
        return rgb
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def _laplacian_variance_fallback(gray: np.ndarray) -> float:
    padded = np.pad(gray, 1, mode="edge")
    laplacian = (
        padded[:-2, 1:-1]
        + padded[2:, 1:-1]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
        - 4.0 * padded[1:-1, 1:-1]
    )
    return float(laplacian.var())

def blur_score(image: Image.Image) -> float:
    if cv2 is not None:
        gray = cv2.cvtColor(np_from_pil(image), cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray, cv2.CV_64F).var())
    gray = np.array(image.convert("L"), dtype=np.float32)
    return _laplacian_variance_fallback(gray)

def brightness_score(image: Image.Image) -> float:
    arr = np.array(image)
    return float(arr.mean())


def bilateral_symmetry_score(image: Image.Image) -> float:
    gray = np.array(image.convert("L").resize((256, 256)), dtype=np.float32) / 255.0
    h, w = gray.shape
    y1, y2 = int(h * 0.12), int(h * 0.92)
    x1, x2 = int(w * 0.08), int(w * 0.92)
    crop = gray[y1:y2, x1:x2]
    half = crop.shape[1] // 2
    left = crop[:, :half]
    right = crop[:, -half:][:, ::-1]
    diff = np.abs(left - right).mean()
    score = 1.0 - float(diff)
    return max(0.0, min(score, 1.0))

def bbox_center(bbox: dict) -> Tuple[float, float]:
    return ((bbox["x1"] + bbox["x2"]) / 2, (bbox["y1"] + bbox["y2"]) / 2)

def render_overlay(image: Image.Image, damages: list[dict]) -> bytes:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    colors = {
        "scratch": (255, 193, 7, 120),
        "dent": (59, 130, 246, 120),
        "crack": (239, 68, 68, 120),
        "broken_part": (249, 115, 22, 120),
    }
    for d in damages:
        color = colors.get(d["damage_type"], (99, 102, 241, 120))
        polygon = d.get("polygon_json") or [
            [d["bbox_norm"]["x1"], d["bbox_norm"]["y1"]],
            [d["bbox_norm"]["x2"], d["bbox_norm"]["y1"]],
            [d["bbox_norm"]["x2"], d["bbox_norm"]["y2"]],
            [d["bbox_norm"]["x1"], d["bbox_norm"]["y2"]],
        ]
        pts = [(int(x * image.width), int(y * image.height)) for x, y in polygon]
        draw.polygon(pts, fill=color, outline=color[:3] + (255,))
    buf = io.BytesIO()
    overlay.save(buf, format="PNG")
    return buf.getvalue()

def overlay_png_b64(image: Image.Image, damages: list[dict]) -> str:
    return base64.b64encode(render_overlay(image, damages)).decode("utf-8")

def seeded_rng(image_bytes: bytes) -> random.Random:
    digest = hashlib.sha256(image_bytes).hexdigest()
    seed = int(digest[:16], 16)
    return random.Random(seed)
