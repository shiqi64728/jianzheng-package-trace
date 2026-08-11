from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.backend.main import create_app
from app.backend.services import MVPService
from app.backend.storage.database import EvidenceDatabase


def now():
    return datetime.now().astimezone().isoformat()


def case_record(case_id="case-test"):
    return {
        "case_id": case_id,
        "created_at": now(),
        "case_name": "匿名测试",
        "status": "CREATED",
        "pipeline_version": "test-v0.1",
        "active_model_version": "fixture-v0.1",
        "notes": "",
    }


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = EvidenceDatabase(Path(self.temp.name) / "evidence.db")

    def tearDown(self):
        self.temp.cleanup()

    def test_required_tables_exist(self):
        self.assertEqual(
            set(self.db.table_names()),
            {
                "cases",
                "case_nodes",
                "detections",
                "pair_changes",
                "analysis_results",
                "reports",
            },
        )

    def test_create_and_retrieve_case(self):
        self.db.create_case(case_record())
        self.assertEqual(self.db.get_case("case-test")["case_name"], "匿名测试")

    def test_list_cases(self):
        self.db.create_case(case_record("case-one"))
        self.db.create_case(case_record("case-two"))
        self.assertEqual(len(self.db.list_cases()), 2)

    def test_add_node(self):
        self.db.create_case(case_record())
        record = {
            "case_id": "case-test",
            "node_id": "N1",
            "surface": "PACKAGE_EXTERIOR",
            "capture_time": None,
            "image_path": "E:/fixture.png",
            "image_sha256": "a" * 64,
            "created_at": now(),
        }
        self.db.add_node(record)
        self.assertEqual(self.db.get_case("case-test")["nodes"][0]["node_id"], "N1")

    def test_missing_case_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.db.get_case("missing")

    def test_store_detection_pair_analysis_and_report(self):
        self.db.create_case(case_record())
        nodes = [
            {
                "node_id": "N1",
                "model_version": "fixture-v0.1",
                "detections": [
                    {
                        "class_code": "D02",
                        "class_name": "表面凹陷",
                        "confidence": 0.8,
                        "bbox_xyxy": [1, 2, 3, 4],
                    }
                ],
            }
        ]
        pairs = [
            {
                "reference_node_id": "N1",
                "current_node_id": "N2",
                "registration_status": "SUCCESS",
                "change_score": 0.9,
                "changed_pixel_ratio": 0.1,
            }
        ]
        analysis = {
            "conclusion_code": "FIRST_ABNORMAL_INTERVAL",
            "first_abnormal_interval": "N1_TO_N2",
            "evidence_level": "E1",
        }
        report = {"json_path": "E:/report.json", "html_path": "E:/report.html"}
        self.db.store_analysis("case-test", now(), nodes, pairs, analysis, report)
        result = self.db.get_case("case-test")
        self.assertEqual(len(result["detections"]), 1)
        self.assertEqual(len(result["pair_changes"]), 1)
        self.assertEqual(result["analysis"]["evidence_level"], "E1")
        self.assertEqual(result["report"]["html_path"], "E:/report.html")

    def test_store_analysis_is_replaceable(self):
        self.db.create_case(case_record())
        analysis = {
            "conclusion_code": "NO_ABNORMALITY_OBSERVED",
            "first_abnormal_interval": None,
            "evidence_level": "E0",
        }
        report = {"json_path": "a", "html_path": "b"}
        self.db.store_analysis("case-test", now(), [], [], analysis, report)
        self.db.store_analysis("case-test", now(), [], [], analysis, report)
        self.assertEqual(self.db.get_case("case-test")["status"], "ANALYZED")

    def test_report_for_missing_case_raises(self):
        with self.assertRaises(KeyError):
            self.db.report_for("missing")


class FakeDetector:
    def predict(self, image):
        return {
            "image_width": int(image.shape[1]),
            "image_height": int(image.shape[0]),
            "model_version": "fixture-v0.1",
            "model_sha256": "f" * 64,
            "runtime": "pytorch",
            "inference_ms": 1.25,
            "detections": [],
        }


def make_image(changed=False):
    rng = np.random.default_rng(11)
    image = np.full((360, 480, 3), 210, dtype=np.uint8)
    for index in range(90):
        x, y = rng.integers([10, 10], [470, 350])
        cv2.circle(image, (int(x), int(y)), 3, (30 + index, 80, 100), -1)
    cv2.putText(
        image, "PACKAGE", (100, 180), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (20, 20, 20), 3
    )
    if changed:
        cv2.rectangle(image, (290, 230), (410, 310), (0, 0, 0), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        model = root / "fixture.pt"
        model.write_bytes(b"fixture")
        registry = root / "registry.json"
        registry.write_text(
            json.dumps(
                {
                    "active_model": "fixture",
                    "model_version": "fixture-v0.1",
                    "source_pt": str(model),
                    "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
                    "imgsz": 640,
                    "classes": ["D02", "D03"],
                    "selection_basis": "test",
                    "runtime_preferred": "pytorch",
                }
            ),
            encoding="utf-8",
        )
        change = root / "change.json"
        change.write_text(
            json.dumps(
                {
                    "orb_nfeatures": 1200,
                    "orb_scale_factor": 1.2,
                    "orb_nlevels": 8,
                    "match_ratio": 0.8,
                    "ransac_reprojection_threshold": 5.0,
                    "minimum_good_matches": 8,
                    "minimum_inlier_ratio": 0.15,
                    "success_inlier_ratio": 0.35,
                    "minimum_overlap_ratio": 0.35,
                    "blur_kernel": 5,
                    "pixel_difference_threshold": 30,
                    "morphology_kernel": 3,
                    "morphology_iterations": 1,
                    "minimum_region_area": 80,
                    "significant_change_ratio": 0.004,
                    "known_damage_overlap_ratio": 0.1,
                }
            ),
            encoding="utf-8",
        )
        config = root / "mvp.json"
        config.write_text(
            json.dumps(
                {
                    "pipeline_version": "test-v0.1",
                    "active_model_registry": str(registry),
                    "detector_confidence": 0.25,
                    "change_config": str(change),
                    "database_path": str(root / "runtime/evidence.db"),
                    "runtime_root": str(root / "runtime"),
                    "max_upload_bytes": 1024 * 1024,
                    "allowed_extensions": [".jpg", ".jpeg", ".png", ".webp"],
                    "allowed_mime_types": ["image/jpeg", "image/png", "image/webp"],
                    "cors_origins": [],
                }
            ),
            encoding="utf-8",
        )
        self.service = MVPService(config, detector=FakeDetector())
        self.client = TestClient(create_app(config, service=self.service))

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def create_case(self):
        response = self.client.post(
            "/api/cases", json={"case_name": "API匿名案例", "notes": ""}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["case_id"]

    def upload(self, case_id, node_id, content=None):
        return self.client.post(
            f"/api/cases/{case_id}/nodes",
            data={"node_id": node_id, "surface": "PACKAGE_EXTERIOR"},
            files={"file": (f"{node_id}.png", content or make_image(), "image/png")},
        )

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["database_ready"])

    def test_model_info_discloses_support(self):
        payload = self.client.get("/api/model/info").json()
        self.assertEqual(payload["classes"], ["D02", "D03"])
        self.assertEqual(payload["class_support"]["D05"], "detector_not_supported_yet")

    def test_create_and_list_case(self):
        case_id = self.create_case()
        cases = self.client.get("/api/cases").json()["cases"]
        self.assertEqual(cases[0]["case_id"], case_id)

    def test_detect_valid_image(self):
        response = self.client.post(
            "/api/detect", files={"file": ("box.png", make_image(), "image/png")}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("detections", response.json())

    def test_rejects_invalid_extension(self):
        response = self.client.post(
            "/api/detect", files={"file": ("box.txt", make_image(), "image/png")}
        )
        self.assertEqual(response.json()["error"]["code"], "IMAGE_EXTENSION_INVALID")

    def test_rejects_invalid_mime(self):
        response = self.client.post(
            "/api/detect", files={"file": ("box.png", make_image(), "text/plain")}
        )
        self.assertEqual(response.json()["error"]["code"], "IMAGE_MIME_INVALID")

    def test_rejects_unreadable_image(self):
        response = self.client.post(
            "/api/detect", files={"file": ("box.png", b"not-image", "image/png")}
        )
        self.assertEqual(response.json()["error"]["code"], "IMAGE_UNREADABLE")

    def test_add_node_uses_generated_filename(self):
        case_id = self.create_case()
        response = self.client.post(
            f"/api/cases/{case_id}/nodes",
            data={"node_id": "N1", "surface": "PACKAGE_EXTERIOR"},
            files={"file": ("../../evil.png", make_image(), "image/png")},
        )
        path = Path(response.json()["image_path"])
        self.assertTrue(path.is_file())
        self.assertNotIn("evil", path.name)

    def test_missing_case_error_is_unified(self):
        response = self.upload("missing", "N1")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "CASE_NOT_FOUND")

    def test_analyze_requires_three_nodes(self):
        case_id = self.create_case()
        self.upload(case_id, "N1")
        response = self.client.post(f"/api/cases/{case_id}/analyze")
        self.assertEqual(response.json()["error"]["code"], "NODES_INCOMPLETE")

    def test_duplicate_node_is_rejected(self):
        case_id = self.create_case()
        self.upload(case_id, "N1")
        response = self.upload(case_id, "N1")
        self.assertEqual(response.status_code, 409)

    def test_change_endpoint(self):
        response = self.client.post(
            "/api/change",
            files={
                "reference": ("n1.png", make_image(), "image/png"),
                "current": ("n2.png", make_image(True), "image/png"),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("change_score", response.json())

    def test_full_case_analysis_and_report(self):
        case_id = self.create_case()
        self.upload(case_id, "N1", make_image())
        self.upload(case_id, "N2", make_image(True))
        self.upload(case_id, "N3", make_image(True))
        response = self.client.post(f"/api/cases/{case_id}/analyze")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["analysis"]["first_abnormal_interval"], "N1_TO_N2"
        )
        report = self.client.get(f"/api/cases/{case_id}/report")
        self.assertEqual(report.status_code, 200)
        self.assertIn("不能单独作为法律责任认定结论", report.text)
