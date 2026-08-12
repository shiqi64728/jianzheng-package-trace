"""MP4 damage-keyframe screening using the active D02/D03 detector."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

import cv2

VIDEO_CAPABILITY = "VIDEO_DAMAGE_KEYFRAME_SCREENING"


class VideoScreeningError(ValueError):
    pass


def screen_video(
    video_path: str | Path,
    detector: Any,
    output_dir: str | Path,
    *,
    sample_interval_frames: int = 5,
    top_k: int = 5,
) -> dict[str, Any]:
    """Decode, sample, detect, rank, and extract abnormal MP4 keyframes."""
    source = Path(video_path)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() != ".mp4":
        raise VideoScreeningError("only MP4 video is supported")
    if sample_interval_frames < 1 or sample_interval_frames > 10_000:
        raise VideoScreeningError("sample_interval_frames must be between 1 and 10000")
    if top_k < 1 or top_k > 50:
        raise VideoScreeningError("top_k must be between 1 and 50")

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise VideoScreeningError("video could not be decoded")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if not math.isfinite(fps) or fps <= 0:
        capture.release()
        raise VideoScreeningError("video FPS metadata is invalid")

    sampled: list[dict[str, Any]] = []
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % sample_interval_frames == 0:
            prediction = detector.predict(frame)
            detections = prediction.get("detections", [])
            maximum_confidence = max(
                (float(item.get("confidence", 0.0)) for item in detections),
                default=0.0,
            )
            sampled.append(
                {
                    "frame_index": frame_index,
                    "timestamp_seconds": round(frame_index / fps, 6),
                    "detections": detections,
                    "detection_count": len(detections),
                    "max_confidence": maximum_confidence,
                    "abnormal_rank_score": round(
                        len(detections) * 10 + maximum_confidence * 100, 6
                    ),
                    "frame": frame.copy(),
                }
            )
        frame_index += 1
    capture.release()
    if frame_index == 0:
        raise VideoScreeningError("video contains no decodable frames")

    abnormal = [item for item in sampled if item["detection_count"] > 0]
    abnormal.sort(
        key=lambda item: (
            -item["abnormal_rank_score"],
            item["frame_index"],
        )
    )
    keyframes = []
    for rank, item in enumerate(abnormal[:top_k], start=1):
        filename = f"keyframe-{rank:02d}-frame-{item['frame_index']:06d}.jpg"
        path = output / filename
        if not cv2.imwrite(
            str(path), item.pop("frame"), [cv2.IMWRITE_JPEG_QUALITY, 92]
        ):
            raise VideoScreeningError(f"failed to write keyframe {filename}")
        keyframes.append(
            {
                **item,
                "rank": rank,
                "filename": filename,
                "image_path": str(path),
                "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    # Drop OpenCV arrays held by non-top samples before returning.
    for item in sampled:
        item.pop("frame", None)

    return {
        "capability": VIDEO_CAPABILITY,
        "video_metadata": {
            "filename": source.name,
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "fps": fps,
            "frame_count_reported": frame_count,
            "frame_count_decoded": frame_index,
            "width": width,
            "height": height,
            "duration_seconds": round(frame_index / fps, 6),
        },
        "sampling": {
            "strategy": "FIXED_FRAME_INTERVAL",
            "sample_interval_frames": sample_interval_frames,
            "sampled_frame_count": len(sampled),
        },
        "sampled_frame_count": len(sampled),
        "abnormal_frame_count": len(abnormal),
        "top_abnormal_keyframes": keyframes,
        "supported_damage_classes": ["D02", "D03"],
        "behavior_recognition": "NOT_SUPPORTED_FUTURE",
    }
