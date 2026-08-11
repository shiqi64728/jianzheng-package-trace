"""One-surface orchestration for detector, registration, change and fingerprint."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .change_detector import ChangeDetector, serializable_change
from .detector import Detector
from .fingerprint import build_surface_fingerprint
from .registration import ImageRegistrar


class SurfaceAnalyzer:
    """Keep node/surface mechanics out of the application service layer."""

    def __init__(
        self,
        detector: Detector,
        registrar: ImageRegistrar,
        change_detector: ChangeDetector | None = None,
    ):
        self.detector = detector
        self.registrar = registrar
        self.change_detector = change_detector or ChangeDetector(registrar)

    @staticmethod
    def _capture_stem(node_id: str, surface: str) -> str:
        return f"{node_id.lower()}-{surface}"

    def analyze_capture(
        self,
        record: dict[str, Any],
        image: np.ndarray,
        case_dir: str | Path,
    ) -> tuple[dict[str, Any], float]:
        started = time.perf_counter()
        detection = self.detector.predict(image)
        fingerprint = build_surface_fingerprint(
            record["image_path"], detection["detections"], record["surface"]
        )
        visualization = image.copy()
        for item in detection["detections"]:
            x1, y1, x2, y2 = [int(value) for value in item["bbox_xyxy"]]
            cv2.rectangle(visualization, (x1, y1), (x2, y2), (25, 127, 235), 2)
            cv2.putText(
                visualization,
                f"{item['class_code']} {item['confidence']:.2f}",
                (x1, max(20, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (25, 127, 235),
                2,
            )
        visual_path = (
            Path(case_dir)
            / f"detected-{self._capture_stem(record['node_id'], record['surface'])}.jpg"
        )
        cv2.imwrite(str(visual_path), visualization)
        result = {
            **record,
            **detection,
            "fingerprint": fingerprint,
            "visualization_path": str(visual_path),
        }
        return result, (time.perf_counter() - started) * 1000.0

    def analyze_pair(
        self,
        reference_result: dict[str, Any],
        current_result: dict[str, Any],
        reference_image: np.ndarray,
        current_image: np.ndarray,
        case_dir: str | Path,
    ) -> tuple[dict[str, Any], dict[str, float]]:
        if reference_result["surface"] != current_result["surface"]:
            raise ValueError("cross-surface comparison is forbidden")
        registration_started = time.perf_counter()
        registration = self.registrar.register(reference_image, current_image)
        registration_ms = (time.perf_counter() - registration_started) * 1000.0
        change_started = time.perf_counter()
        change = self.change_detector.detect(
            reference_image,
            current_image,
            known_detections=current_result["detections"],
            registration=registration,
        )
        change_ms = (time.perf_counter() - change_started) * 1000.0
        surface = reference_result["surface"]
        stem = (
            f"{reference_result['node_id'].lower()}-"
            f"{current_result['node_id'].lower()}-{surface}"
        )
        visual_path = Path(case_dir) / f"change-{stem}.jpg"
        cv2.imwrite(str(visual_path), change["visualization"])
        result = {
            "reference_node_id": reference_result["node_id"],
            "current_node_id": current_result["node_id"],
            "surface": surface,
            "pair_status": "AVAILABLE",
            **serializable_change(change),
            "visualization_path": str(visual_path),
        }
        return result, {
            "registration": registration_ms,
            "change_detection": change_ms,
        }

    @staticmethod
    def missing_pair(reference_node_id: str, current_node_id: str, surface: str):
        return {
            "reference_node_id": reference_node_id,
            "current_node_id": current_node_id,
            "surface": surface,
            "pair_status": "PAIR_SURFACE_MISSING",
            "registration_status": "NOT_RUN",
            "registration_confidence": 0.0,
            "registration": None,
            "change_score": 0.0,
            "changed_pixel_ratio": 0.0,
            "changed_region_count": 0,
            "regions": [],
            "is_significant": False,
            "visualization_path": None,
            "warnings": ["corresponding surface is missing; no comparison was run"],
        }
