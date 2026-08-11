"""ORB/RANSAC image registration with explicit low-confidence fallbacks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def _load_config(config: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(config, dict):
        return dict(config)
    return json.loads(Path(config).read_text(encoding="utf-8"))


class ImageRegistrar:
    """Align a current capture to a reference capture."""

    def __init__(self, config: dict[str, Any] | str | Path):
        self.config = _load_config(config)

    def _failed(
        self,
        reference: np.ndarray,
        current: np.ndarray,
        warning: str,
        keypoints_reference: int = 0,
        keypoints_current: int = 0,
        match_count: int = 0,
        good_match_count: int = 0,
    ) -> dict[str, Any]:
        height, width = reference.shape[:2]
        fallback = cv2.resize(current, (width, height), interpolation=cv2.INTER_AREA)
        return {
            "registered_image": fallback,
            "overlap_mask": np.full((height, width), 255, dtype=np.uint8),
            "homography": None,
            "keypoint_count_reference": keypoints_reference,
            "keypoint_count_current": keypoints_current,
            "match_count": match_count,
            "good_match_count": good_match_count,
            "inlier_count": 0,
            "inlier_ratio": 0.0,
            "overlap_ratio": 1.0,
            "registration_status": "FAILED",
            "fallback_visual_change": True,
            "warnings": [warning, "仅使用resize fallback，证据置信度已降低。"],
        }

    def register(self, reference: np.ndarray, current: np.ndarray) -> dict[str, Any]:
        if (
            reference is None
            or current is None
            or reference.size == 0
            or current.size == 0
        ):
            raise ValueError("配准输入不能为空。")
        gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        gray_cur = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        orb = cv2.ORB_create(
            nfeatures=int(self.config["orb_nfeatures"]),
            scaleFactor=float(self.config["orb_scale_factor"]),
            nlevels=int(self.config["orb_nlevels"]),
        )
        kp_ref, desc_ref = orb.detectAndCompute(gray_ref, None)
        kp_cur, desc_cur = orb.detectAndCompute(gray_cur, None)
        ref_count, cur_count = len(kp_ref), len(kp_cur)
        if desc_ref is None or desc_cur is None or min(ref_count, cur_count) < 4:
            return self._failed(
                reference, current, "关键点或描述子不足。", ref_count, cur_count
            )
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        pairs = matcher.knnMatch(desc_cur, desc_ref, k=2)
        ratio = float(self.config["match_ratio"])
        good = [
            pair[0]
            for pair in pairs
            if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance
        ]
        minimum = int(self.config["minimum_good_matches"])
        if len(good) < minimum:
            return self._failed(
                reference,
                current,
                "通过ratio test的匹配点不足。",
                ref_count,
                cur_count,
                len(pairs),
                len(good),
            )
        src = np.float32([kp_cur[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kp_ref[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        homography, mask = cv2.findHomography(
            src,
            dst,
            cv2.RANSAC,
            float(self.config["ransac_reprojection_threshold"]),
        )
        if homography is None or mask is None or not np.isfinite(homography).all():
            return self._failed(
                reference,
                current,
                "Homography求解失败或矩阵异常。",
                ref_count,
                cur_count,
                len(pairs),
                len(good),
            )
        inliers = int(mask.ravel().sum())
        inlier_ratio = inliers / len(good)
        height, width = reference.shape[:2]
        registered = cv2.warpPerspective(current, homography, (width, height))
        current_mask = np.full(current.shape[:2], 255, dtype=np.uint8)
        overlap = cv2.warpPerspective(current_mask, homography, (width, height))
        overlap_ratio = float(np.count_nonzero(overlap)) / float(width * height)
        if inlier_ratio < float(
            self.config["minimum_inlier_ratio"]
        ) or overlap_ratio < float(self.config["minimum_overlap_ratio"]):
            return self._failed(
                reference,
                current,
                "RANSAC内点比例或有效重叠区域不足。",
                ref_count,
                cur_count,
                len(pairs),
                len(good),
            )
        status = (
            "SUCCESS"
            if inlier_ratio >= float(self.config["success_inlier_ratio"])
            else "LOW_CONFIDENCE"
        )
        warnings = [] if status == "SUCCESS" else ["配准内点比例偏低，建议人工复核。"]
        return {
            "registered_image": registered,
            "overlap_mask": overlap,
            "homography": homography.tolist(),
            "keypoint_count_reference": ref_count,
            "keypoint_count_current": cur_count,
            "match_count": len(pairs),
            "good_match_count": len(good),
            "inlier_count": inliers,
            "inlier_ratio": inlier_ratio,
            "overlap_ratio": overlap_ratio,
            "registration_status": status,
            "fallback_visual_change": False,
            "warnings": warnings,
        }


def serializable_registration(result: dict[str, Any]) -> dict[str, Any]:
    """Drop in-memory image arrays from a registration result."""
    return {
        key: value
        for key, value in result.items()
        if key not in {"registered_image", "overlap_mask"}
    }
