from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.backend.main import create_app
from app.backend.services import MVPService
from app.backend.storage.database import EvidenceDatabase, MIGRATION_ID

ACTIVE_REGISTRY = Path("E:/JianZhengData/models/active/detector-v0.1.json")
CHANGE_CONFIG = Path("configs/runtime/change-detection-v0.2.json").resolve()


def now() -> str:
    return datetime.now().astimezone().isoformat()


def case_record(case_id="case-v02"):
    return {
        "case_id": case_id,
        "created_at": now(),
        "case_name": "匿名 v0.2",
        "status": "CREATED",
        "pipeline_version": "competition-mvp-v0.2",
        "active_model_version": "fixture",
        "notes": "",
    }


class FakeDetector:
    runtime = "pytorch"

    def predict(self, image):
        height, width = image.shape[:2]
        return {
            "image_width": width,
            "image_height": height,
            "model_version": "fake-v0.2",
            "model_sha256": "f" * 64,
            "runtime": "pytorch",
            "inference_ms": 0.1,
            "detections": [],
        }

    def warmup(self):
        return {
            "loaded": True,
            "runtime": "pytorch",
            "warmup_ms": 1.25,
            "gpu": True,
        }


def textured(changed=False) -> bytes:
    image = np.full((300, 420, 3), (210, 195, 160), dtype=np.uint8)
    cv2.rectangle(image, (15, 15), (405, 285), (90, 70, 48), 5)
    for x in range(30, 400, 25):
        cv2.line(image, (x, 30), (x, 275), (160, 140, 105), 1)
    for y in range(30, 280, 24):
        cv2.line(image, (25, y), (395, y), (160, 140, 105), 1)
    cv2.putText(
        image, "JZ-V02", (105, 135), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (45, 38, 30), 3
    )
    if changed:
        cv2.rectangle(image, (260, 175), (375, 260), (45, 37, 31), -1)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


class DatabaseMigrationTests(unittest.TestCase):
    def test_empty_database_reaches_schema_v02(self):
        with tempfile.TemporaryDirectory() as temp:
            db = EvidenceDatabase(Path(temp) / "empty.db")
            self.assertEqual(db.schema_version(), 2)
            names = set(db.table_names(include_v02=True))
            self.assertTrue(
                {
                    "schema_version",
                    "database_migrations",
                    "review_events",
                    "surface_analysis",
                }
                <= names
            )

    def test_surface_unique_key_allows_same_node_different_surfaces(self):
        with tempfile.TemporaryDirectory() as temp:
            db = EvidenceDatabase(Path(temp) / "surface.db")
            db.create_case(case_record())
            base = {
                "case_id": "case-v02",
                "node_id": "N1",
                "capture_time": None,
                "image_path": "x",
                "image_sha256": "a" * 64,
                "created_at": now(),
            }
            db.add_node({**base, "surface": "front"})
            db.add_node({**base, "surface": "left", "image_path": "y"})
            self.assertEqual(len(db.get_case("case-v02")["nodes"]), 2)

    def test_surface_unique_key_rejects_duplicate_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            db = EvidenceDatabase(Path(temp) / "surface.db")
            db.create_case(case_record())
            record = {
                "case_id": "case-v02",
                "node_id": "N1",
                "surface": "front",
                "capture_time": None,
                "image_path": "x",
                "image_sha256": "a" * 64,
                "created_at": now(),
            }
            db.add_node(record)
            with self.assertRaises(sqlite3.IntegrityError):
                db.add_node(record)

    @staticmethod
    def make_v01(path: Path) -> None:
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE cases(case_id TEXT PRIMARY KEY,created_at TEXT NOT NULL,case_name TEXT NOT NULL,status TEXT NOT NULL,pipeline_version TEXT NOT NULL,active_model_version TEXT NOT NULL,notes TEXT NOT NULL DEFAULT '');
            CREATE TABLE case_nodes(case_id TEXT NOT NULL,node_id TEXT NOT NULL,surface TEXT NOT NULL,capture_time TEXT,image_path TEXT NOT NULL,image_sha256 TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(case_id,node_id));
            INSERT INTO cases VALUES('old-case','2026-01-01','old','ANALYZED','competition-mvp-v0.1','old-model','');
            INSERT INTO case_nodes VALUES('old-case','N1','PACKAGE_EXTERIOR',NULL,'old.png','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','2026-01-01');
            """
        )
        connection.commit()
        connection.close()

    def test_v01_database_migrates_and_preserves_case(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "old.db"
            self.make_v01(path)
            db = EvidenceDatabase(path)
            case = db.get_case("old-case")
            self.assertEqual(case["nodes"][0]["surface"], "front")
            self.assertIn("case_nodes_v01_backup", db.table_names(include_v02=True))
            self.assertEqual(db.migrations()[0]["migration_id"], MIGRATION_ID)

    def test_repeated_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "old.db"
            self.make_v01(path)
            EvidenceDatabase(path)
            second = EvidenceDatabase(path)
            self.assertEqual(len(second.migrations()), 1)
            self.assertEqual(len(second.get_case("old-case")["nodes"]), 1)

    def test_bootstrap_copy_does_not_modify_v01_source(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.db"
            target = Path(temp) / "target.db"
            self.make_v01(source)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            copied = EvidenceDatabase(target, bootstrap_from=source)
            after = hashlib.sha256(source.read_bytes()).hexdigest()
            self.assertEqual(before, after)
            self.assertEqual(
                copied.get_case("old-case")["nodes"][0]["surface"], "front"
            )

    def test_review_table_rejects_update_and_delete(self):
        with tempfile.TemporaryDirectory() as temp:
            db = EvidenceDatabase(Path(temp) / "review.db")
            db.create_case(case_record())
            record = {
                "review_id": "review-1",
                "case_id": "case-v02",
                "node_from": "N1",
                "node_to": "N2",
                "surface": "left",
                "machine_result": "UNKNOWN_VISUAL_CHANGE",
                "review_class": "D05",
                "review_status": "CONFIRMED",
                "reviewer_alias": "MEMBER-A",
                "review_note": "",
                "created_at": now(),
                "supersedes_review_id": None,
                "review_payload_sha256": "b" * 64,
            }
            db.add_review(record)
            with self.assertRaises(sqlite3.IntegrityError):
                with db.connect() as connection:
                    connection.execute(
                        "UPDATE review_events SET review_note='x' WHERE review_id='review-1'"
                    )
            with self.assertRaises(sqlite3.IntegrityError):
                with db.connect() as connection:
                    connection.execute(
                        "DELETE FROM review_events WHERE review_id='review-1'"
                    )


class V02ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        config = root / "mvp.json"
        config.write_text(
            json.dumps(
                {
                    "pipeline_version": "competition-mvp-v0.2",
                    "active_model_registry": str(ACTIVE_REGISTRY),
                    "runtime_preference": "registry",
                    "detector_confidence": 0.25,
                    "change_config": str(CHANGE_CONFIG),
                    "database_path": str(root / "runtime" / "evidence.db"),
                    "runtime_root": str(root / "runtime"),
                    "auto_warmup": False,
                    "max_upload_bytes": 2_000_000,
                    "allowed_extensions": [".png"],
                    "allowed_mime_types": ["image/png"],
                    "cors_origins": ["http://localhost"],
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
            "/api/cases", json={"case_name": "v0.2", "notes": ""}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["case_id"]

    def upload(self, case_id: str, node: str, surface: str, changed=False):
        return self.client.post(
            f"/api/cases/{case_id}/nodes",
            data={"node_id": node, "surface": surface},
            files={"file": (f"{node}-{surface}.png", textured(changed), "image/png")},
        )

    def analyzed_case(self, surfaces=("left",)):
        case_id = self.create_case()
        for node in ("N1", "N2", "N3"):
            for surface in surfaces:
                changed = surface == "left" and node in {"N2", "N3"}
                self.assertEqual(
                    self.upload(case_id, node, surface, changed).status_code, 200
                )
        response = self.client.post(f"/api/cases/{case_id}/analyze")
        self.assertEqual(response.status_code, 200, response.text)
        return case_id, response.json()

    def review_payload(self, review_class="D05", **updates):
        payload = {
            "node_from": "N1",
            "node_to": "N2",
            "surface": "left",
            "review_class": review_class,
            "review_status": "CONFIRMED",
            "reviewer_alias": "MEMBER-A",
            "review_note": "人工复核候选",
        }
        payload.update(updates)
        return payload

    def test_health_reports_schema_v02(self):
        payload = self.client.get("/api/health").json()
        self.assertEqual(payload["pipeline_version"], "competition-mvp-v0.2")
        self.assertEqual(payload["schema_version"], 2)

    def test_warmup_endpoint(self):
        first = self.client.post("/api/model/warmup").json()
        second = self.client.post("/api/model/warmup").json()
        self.assertTrue(first["loaded"])
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])

    def test_single_surface_legacy_upload_defaults_front(self):
        case_id = self.create_case()
        response = self.client.post(
            f"/api/cases/{case_id}/nodes",
            data={"node_id": "N1", "surface": "PACKAGE_EXTERIOR"},
            files={"file": ("n1.png", textured(), "image/png")},
        )
        self.assertEqual(response.json()["surface"], "front")

    def test_same_node_accepts_multiple_surfaces(self):
        case_id = self.create_case()
        self.assertEqual(self.upload(case_id, "N1", "front").status_code, 200)
        self.assertEqual(self.upload(case_id, "N1", "left").status_code, 200)

    def test_duplicate_node_surface_is_rejected(self):
        case_id = self.create_case()
        self.upload(case_id, "N1", "left")
        response = self.upload(case_id, "N1", "left")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "NODE_SURFACE_ALREADY_EXISTS"
        )

    def test_invalid_surface_is_rejected(self):
        case_id = self.create_case()
        response = self.upload(case_id, "N1", "inside")
        self.assertEqual(response.json()["error"]["code"], "SURFACE_INVALID")

    def test_multisurface_analyze_triggers_only_left(self):
        _case_id, result = self.analyzed_case(("front", "left"))
        self.assertEqual(result["analysis"]["first_abnormal_interval"], "N1_TO_N2")
        self.assertEqual(
            [item["surface"] for item in result["analysis"]["trigger_surfaces"]],
            ["left"],
        )
        self.assertTrue(
            all(pair["surface"] in {"front", "left"} for pair in result["pair_changes"])
        )

    def test_missing_surface_is_recorded(self):
        case_id = self.create_case()
        for node in ("N1", "N2", "N3"):
            self.upload(case_id, node, "front")
        self.upload(case_id, "N1", "top")
        self.upload(case_id, "N3", "top")
        result = self.client.post(f"/api/cases/{case_id}/analyze").json()
        missing = [
            x
            for x in result["pair_changes"]
            if x["pair_status"] == "PAIR_SURFACE_MISSING"
        ]
        self.assertEqual(len(missing), 2)
        self.assertFalse(any(x["is_significant"] for x in missing))

    def test_review_post_and_get(self):
        case_id, _ = self.analyzed_case()
        created = self.client.post(
            f"/api/cases/{case_id}/reviews", json=self.review_payload()
        )
        self.assertEqual(created.status_code, 200)
        reviews = self.client.get(f"/api/cases/{case_id}/reviews").json()["reviews"]
        self.assertEqual(len(reviews), 1)

    def test_review_d01(self):
        case_id, _ = self.analyzed_case()
        self.assertEqual(
            self.client.post(
                f"/api/cases/{case_id}/reviews", json=self.review_payload("D01")
            ).json()["review_class"],
            "D01",
        )

    def test_review_d04(self):
        case_id, _ = self.analyzed_case()
        self.assertEqual(
            self.client.post(
                f"/api/cases/{case_id}/reviews", json=self.review_payload("D04")
            ).json()["review_class"],
            "D04",
        )

    def test_review_d05(self):
        case_id, _ = self.analyzed_case()
        self.assertEqual(
            self.client.post(
                f"/api/cases/{case_id}/reviews", json=self.review_payload("D05")
            ).json()["review_class"],
            "D05",
        )

    def test_review_normal_variation(self):
        case_id, _ = self.analyzed_case()
        self.assertEqual(
            self.client.post(
                f"/api/cases/{case_id}/reviews",
                json=self.review_payload("NORMAL_VARIATION"),
            ).json()["review_class"],
            "NORMAL_VARIATION",
        )

    def test_review_unsure(self):
        case_id, _ = self.analyzed_case()
        payload = self.review_payload("UNSURE", review_status="UNSURE")
        self.assertEqual(
            self.client.post(f"/api/cases/{case_id}/reviews", json=payload).json()[
                "review_status"
            ],
            "UNSURE",
        )

    def test_machine_result_is_not_overwritten(self):
        case_id, analysis = self.analyzed_case()
        created = self.client.post(
            f"/api/cases/{case_id}/reviews", json=self.review_payload("D05")
        ).json()
        self.assertEqual(created["machine_result"], "UNKNOWN_VISUAL_CHANGE")
        case = self.client.get(f"/api/cases/{case_id}").json()
        self.assertEqual(
            case["analysis"]["result"]["conclusion_code"],
            analysis["analysis"]["conclusion_code"],
        )

    def test_reviews_are_append_only(self):
        case_id, _ = self.analyzed_case()
        first = self.client.post(
            f"/api/cases/{case_id}/reviews", json=self.review_payload()
        ).json()
        second = self.client.post(
            f"/api/cases/{case_id}/reviews", json=self.review_payload("D04")
        ).json()
        self.assertNotEqual(first["review_id"], second["review_id"])
        self.assertEqual(
            len(self.client.get(f"/api/cases/{case_id}/reviews").json()["reviews"]), 2
        )

    def test_supersede_creates_audit_link(self):
        case_id, _ = self.analyzed_case()
        first = self.client.post(
            f"/api/cases/{case_id}/reviews", json=self.review_payload()
        ).json()
        payload = self.review_payload("D04", supersedes_review_id=first["review_id"])
        second = self.client.post(f"/api/cases/{case_id}/reviews", json=payload).json()
        self.assertEqual(second["supersedes_review_id"], first["review_id"])

    def test_missing_superseded_review_is_rejected(self):
        case_id, _ = self.analyzed_case()
        response = self.client.post(
            f"/api/cases/{case_id}/reviews",
            json=self.review_payload(supersedes_review_id="review-missing"),
        )
        self.assertEqual(
            response.json()["error"]["code"], "SUPERSEDED_REVIEW_NOT_FOUND"
        )

    def test_review_payload_hash_is_stable(self):
        payload = {"a": 1, "b": "中文"}
        self.assertEqual(
            self.service.review_payload_sha256(payload),
            self.service.review_payload_sha256({"b": "中文", "a": 1}),
        )

    def test_invalid_reviewer_alias_is_rejected(self):
        case_id, _ = self.analyzed_case()
        response = self.client.post(
            f"/api/cases/{case_id}/reviews",
            json=self.review_payload(reviewer_alias="REAL-NAME"),
        )
        self.assertEqual(response.json()["error"]["code"], "REVIEWER_ALIAS_INVALID")

    def test_review_is_rendered_in_versioned_report(self):
        case_id, _ = self.analyzed_case()
        self.client.post(
            f"/api/cases/{case_id}/reviews", json=self.review_payload("D05")
        )
        case = self.client.get(f"/api/cases/{case_id}").json()
        html_path = Path(case["report"]["html_path"])
        content = html_path.read_text(encoding="utf-8")
        self.assertIn("人工复核", content)
        self.assertIn("D05", content)
        self.assertIn("UNKNOWN_VISUAL_CHANGE", content)
        self.assertTrue(html_path.name.endswith("r001.html"))


if __name__ == "__main__":
    unittest.main()
