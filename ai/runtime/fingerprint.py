"""Engineering appearance fingerprint for one captured image."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np

FINGERPRINT_LIMITATION = (
    "descriptor_digest是工程级版本标识，不是稳定的跨拍摄视觉身份hash。"
)


def _image_bytes(image: np.ndarray | str | Path) -> tuple[np.ndarray, bytes]:
    if isinstance(image, np.ndarray):
        decoded = image
        ok, encoded = cv2.imencode(".png", decoded)
        if not ok:
            raise ValueError("无法编码图像以计算SHA-256。")
        raw = encoded.tobytes()
    else:
        path = Path(image)
        raw = path.read_bytes()
        decoded = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None or decoded.size == 0:
        raise ValueError("图像无法解码。")
    return decoded, raw


def build_appearance_fingerprint(
    image: np.ndarray | str | Path,
    detections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    decoded, raw = _image_bytes(image)
    gray = cv2.cvtColor(decoded, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=1800)
    keypoints, descriptors = orb.detectAndCompute(gray, None)
    if descriptors is None:
        descriptor_digest = hashlib.sha256(b"").hexdigest()
    else:
        rows = sorted(bytes(row) for row in np.asarray(descriptors, dtype=np.uint8))
        descriptor_digest = hashlib.sha256(b"".join(rows)).hexdigest()
    counts = {"D02": 0, "D03": 0}
    max_confidence = {"D02": 0.0, "D03": 0.0}
    for detection in detections or []:
        code = detection.get("class_code")
        if code in counts:
            counts[code] += 1
            max_confidence[code] = max(
                max_confidence[code], float(detection.get("confidence", 0.0))
            )
    return {
        "fingerprint_version": "appearance_fingerprint_v0.1",
        "image_sha256": hashlib.sha256(raw).hexdigest(),
        "width": int(decoded.shape[1]),
        "height": int(decoded.shape[0]),
        "orb_keypoint_count": len(keypoints),
        "descriptor_digest": descriptor_digest,
        "known_damage_summary": {
            "counts": counts,
            "max_confidence": max_confidence,
        },
        "limitation": FINGERPRINT_LIMITATION,
    }
