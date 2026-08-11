"""Class-agnostic visual change detection after image registration."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from .registration import ImageRegistrar, serializable_registration


def _intersection_ratio(a: list[float], b: list[float]) -> float:
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = max(1.0, (a[2] - a[0]) * (a[3] - a[1]))
    return intersection / area


class ChangeDetector:
    """Detect UNKNOWN_VISUAL_CHANGE regions without training another model."""

    def __init__(self, registrar: ImageRegistrar):
        self.registrar = registrar
        self.config = registrar.config

    def detect(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        known_detections: list[dict[str, Any]] | None = None,
        registration: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        registration = registration or self.registrar.register(reference, current)
        aligned = registration["registered_image"]
        gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        gray_cur = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
        kernel = int(self.config["blur_kernel"])
        gray_ref = cv2.GaussianBlur(gray_ref, (kernel, kernel), 0)
        gray_cur = cv2.GaussianBlur(gray_cur, (kernel, kernel), 0)
        difference = cv2.absdiff(gray_ref, gray_cur)
        threshold = int(self.config["pixel_difference_threshold"])
        _, mask = cv2.threshold(difference, threshold, 255, cv2.THRESH_BINARY)
        overlap = registration.get("overlap_mask")
        if overlap is not None and registration["registration_status"] != "FAILED":
            mask = cv2.bitwise_and(mask, overlap)
        morph_size = int(self.config["morphology_kernel"])
        morph = cv2.getStructuringElement(cv2.MORPH_RECT, (morph_size, morph_size))
        iterations = int(self.config["morphology_iterations"])
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, morph, iterations=iterations)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, morph, iterations=iterations)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        height, width = mask.shape
        total = float(width * height)
        regions: list[dict[str, Any]] = []
        visualization = reference.copy()
        known_detections = known_detections or []
        for contour in sorted(contours, key=cv2.contourArea, reverse=True):
            area = float(cv2.contourArea(contour))
            if area < float(self.config["minimum_region_area"]):
                continue
            x, y, w, h = cv2.boundingRect(contour)
            bbox = [float(x), float(y), float(x + w), float(y + h)]
            region_mask = np.zeros_like(mask)
            cv2.drawContours(region_mask, [contour], -1, 255, thickness=-1)
            mean_difference = float(cv2.mean(difference, mask=region_mask)[0])
            matched = [
                detection["class_code"]
                for detection in known_detections
                if _intersection_ratio(bbox, detection["bbox_xyxy"])
                >= float(self.config["known_damage_overlap_ratio"])
            ]
            change_type = matched[0] if matched else "UNKNOWN_VISUAL_CHANGE"
            regions.append(
                {
                    "x1": x,
                    "y1": y,
                    "x2": x + w,
                    "y2": y + h,
                    "area": area,
                    "area_ratio": area / total,
                    "mean_difference": mean_difference,
                    "change_type": change_type,
                    "overlapping_known_damage": matched,
                }
            )
            cv2.rectangle(visualization, (x, y), (x + w, y + h), (42, 65, 255), 2)
        changed_pixel_ratio = float(np.count_nonzero(mask)) / total
        significant = changed_pixel_ratio >= float(
            self.config["significant_change_ratio"]
        ) and bool(regions)
        confidence = float(registration.get("inlier_ratio", 0.0))
        if registration["registration_status"] == "FAILED":
            confidence = min(0.2, confidence)
        return {
            "change_score": min(
                1.0,
                changed_pixel_ratio
                / max(float(self.config["significant_change_ratio"]), 1e-9),
            ),
            "changed_pixel_ratio": changed_pixel_ratio,
            "changed_region_count": len(regions),
            "regions": regions,
            "is_significant": significant,
            "registration_status": registration["registration_status"],
            "registration_confidence": confidence,
            "registration": serializable_registration(registration),
            "change_mask": mask,
            "visualization": visualization,
            "warnings": list(registration.get("warnings", [])),
        }


def serializable_change(result: dict[str, Any]) -> dict[str, Any]:
    """Drop OpenCV arrays so a result can be stored as JSON."""
    return {
        key: value
        for key, value in result.items()
        if key not in {"change_mask", "visualization"}
    }
