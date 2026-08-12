from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai.runtime.evidence_report import DISCLAIMER, generate_evidence_report
from ai.runtime.video_screening import (
    VIDEO_CAPABILITY,
    VideoScreeningError,
    screen_video,
)


class BrightDetector:
    def predict(self, image):
        detections = []
        if float(image.mean()) > 100:
            detections = [
                {
                    "class_code": "D03",
                    "class_name": "hole",
                    "confidence": 0.9,
                    "bbox_xyxy": [5, 5, 20, 20],
                }
            ]
        return {"detections": detections, "inference_ms": 0.1, "model_version": "fake"}


def build_video(path: Path):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 48))
    if not writer.isOpened():
        raise unittest.SkipTest("MP4 writer unavailable")
    for index in range(10):
        writer.write(np.full((48, 64, 3), 220 if index >= 4 else 20, np.uint8))
    writer.release()


class VideoScreeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / "demo.mp4"
        build_video(self.video)

    def tearDown(self):
        self.temp.cleanup()

    def screen(self, **kwargs):
        return screen_video(
            self.video, BrightDetector(), self.root / "frames", **kwargs
        )

    def test_capability_label(self):
        self.assertEqual(self.screen()["capability"], VIDEO_CAPABILITY)

    def test_decodes_metadata(self):
        metadata = self.screen()["video_metadata"]
        self.assertEqual(
            (metadata["frame_count_decoded"], metadata["width"], metadata["height"]),
            (10, 64, 48),
        )

    def test_fixed_interval_sampling_count(self):
        self.assertEqual(
            self.screen(sample_interval_frames=2)["sampled_frame_count"], 5
        )

    def test_outputs_abnormal_keyframe(self):
        result = self.screen(sample_interval_frames=2)
        self.assertGreaterEqual(result["abnormal_frame_count"], 1)
        self.assertGreaterEqual(len(result["top_abnormal_keyframes"]), 1)

    def test_keyframe_timestamp_is_frame_over_fps(self):
        keyframe = self.screen(sample_interval_frames=2)["top_abnormal_keyframes"][0]
        self.assertAlmostEqual(
            keyframe["timestamp_seconds"], keyframe["frame_index"] / 10.0, places=4
        )

    def test_keyframe_file_and_sha_are_valid(self):
        keyframe = self.screen(sample_interval_frames=2)["top_abnormal_keyframes"][0]
        path = Path(keyframe["image_path"])
        self.assertTrue(path.is_file())
        self.assertEqual(
            keyframe["image_sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
        )

    def test_top_k_is_enforced(self):
        self.assertLessEqual(
            len(
                self.screen(sample_interval_frames=1, top_k=2)["top_abnormal_keyframes"]
            ),
            2,
        )

    def test_behavior_recognition_boundary(self):
        self.assertEqual(self.screen()["behavior_recognition"], "NOT_SUPPORTED_FUTURE")

    def test_non_mp4_is_rejected(self):
        bad = self.root / "video.avi"
        bad.write_bytes(b"x")
        with self.assertRaises(VideoScreeningError):
            screen_video(bad, BrightDetector(), self.root / "x")

    def test_invalid_sampling_interval_is_rejected(self):
        with self.assertRaises(VideoScreeningError):
            self.screen(sample_interval_frames=0)


class EvidenceReportV10Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "n1.png"
        cv2.imwrite(str(self.image), np.full((20, 20, 3), 100, np.uint8))
        sha = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.case = {
            "case_id": "case-report",
            "case_name": "demo",
            "status": "ANALYZED",
            "pipeline_version": "competition-rc-v1.0",
            "notes": "",
        }
        self.nodes = [
            {
                "node_id": "N1",
                "surface": "front",
                "image_path": str(self.image),
                "fingerprint": {"image_sha256": sha},
                "detections": [],
            }
        ]
        self.analysis = {
            "conclusion_code": "FIRST_OBSERVED_ABNORMAL_AT_N1",
            "first_abnormal_interval": None,
            "evidence_level": "E2",
            "trigger_surfaces": [{"surface": "front", "reason": "KNOWN_DAMAGE"}],
            "evidence_completeness": {
                "available_capture_count": 1,
                "expected_matrix_cells": 1,
            },
        }
        self.risk = {
            "risk_score": 20,
            "risk_level": "INSUFFICIENT_EVIDENCE",
            "score_breakdown": [
                {
                    "component": "first_abnormal_interval",
                    "points": 10,
                    "max_points": 18,
                    "reason": "N1",
                }
            ],
            "missing_evidence": [{"type": "PRE_N1_REFERENCE"}],
            "manual_review_required": True,
        }

    def tearDown(self):
        self.temp.cleanup()

    def report(self):
        return generate_evidence_report(
            self.case,
            self.nodes,
            [],
            self.analysis,
            {"model_version": "m1", "sha256": "a" * 64},
            self.root / "report",
            report_revision=0,
            risk=self.risk,
            logistics_nodes=[
                {
                    "node_id": "N1",
                    "node_type": "PICKUP",
                    "event_time": "2026-08-12T01:00:00+08:00",
                    "location_alias": "LOC-1",
                    "device_alias": "DEV-1",
                    "status": "OK",
                    "notes": "",
                }
            ],
            work_orders=[
                {
                    "work_order_id": "wo-1",
                    "title": "demo",
                    "current_state": "OPEN",
                    "events": [{"event_type": "CREATE", "current_state": "OPEN"}],
                }
            ],
            report_version="evidence-report-v1.0",
        )

    def test_json_contains_required_v1_fields(self):
        data = json.loads(Path(self.report()["json_path"]).read_text(encoding="utf-8"))
        required = {
            "case_summary",
            "node_surface_matrix",
            "timeline",
            "machine_detections",
            "unknown_changes",
            "registration_evidence",
            "appearance_fingerprints",
            "first_abnormal_interval",
            "trigger_surfaces",
            "risk_score",
            "risk_score_breakdown",
            "human_reviews",
            "work_order_history",
            "missing_evidence",
            "model_version",
            "model_sha256",
            "image_sha256_records",
            "pipeline_version",
            "generated_at",
            "limitations",
        }
        self.assertTrue(required <= set(data))

    def test_fixed_disclaimer_is_exact(self):
        data = json.loads(Path(self.report()["json_path"]).read_text(encoding="utf-8"))
        self.assertEqual(data["disclaimer"], DISCLAIMER)

    def test_html_is_utf8_and_references_existing_image(self):
        html = Path(self.report()["html_path"]).read_text(encoding="utf-8")
        self.assertIn("件证结构化证据辅助分析报告", html)
        self.assertIn("n1.png", html)
        self.assertTrue(self.image.is_file())

    def test_html_contains_timeline_risk_and_work_order(self):
        html = Path(self.report()["html_path"]).read_text(encoding="utf-8")
        self.assertIn("LOC-1", html)
        self.assertIn("20 / 100", html)
        self.assertIn("CREATE", html)


if __name__ == "__main__":
    unittest.main()
