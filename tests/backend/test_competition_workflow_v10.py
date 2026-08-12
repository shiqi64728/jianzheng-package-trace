from __future__ import annotations

import csv
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.backend.main import create_app
from app.backend.services import MVPService
from app.backend.storage.database import EvidenceDatabase, RC_MIGRATION_ID

try:
    from backend.test_mvp_v02 import (
        ACTIVE_REGISTRY,
        CHANGE_CONFIG,
        FakeDetector,
        textured,
    )
except ModuleNotFoundError:  # direct ``-s tests/backend`` discovery
    from test_mvp_v02 import ACTIVE_REGISTRY, CHANGE_CONFIG, FakeDetector, textured


def logistics_rows():
    return [
        {
            "package_alias": "PKG-DEMO-001",
            "node_id": f"N{i}",
            "node_type": kind,
            "event_time": f"2026-08-12T0{i}:00:00+08:00",
            "location_alias": f"LOC-{i}",
            "device_alias": "DEVICE-DEMO",
            "status": "CAPTURED",
            "notes": "",
        }
        for i, kind in enumerate(("PICKUP", "SORTING", "DELIVERY"), start=1)
    ]


class CompetitionWorkflowApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.config = root / "rc.json"
        self.config.write_text(
            json.dumps(
                {
                    "pipeline_version": "competition-rc-v1.0",
                    "active_model_registry": str(ACTIVE_REGISTRY),
                    "runtime_preference": "registry",
                    "detector_confidence": 0.25,
                    "change_config": str(CHANGE_CONFIG),
                    "database_path": str(root / "runtime" / "evidence.db"),
                    "runtime_root": str(root / "runtime"),
                    "auto_warmup": False,
                    "max_upload_bytes": 2_000_000,
                    "max_video_upload_bytes": 4_000_000,
                    "allowed_extensions": [".png"],
                    "allowed_mime_types": ["image/png"],
                    "cors_origins": ["http://localhost"],
                }
            ),
            encoding="utf-8",
        )
        self.service = MVPService(self.config, detector=FakeDetector())
        self.client = TestClient(create_app(self.config, service=self.service))
        self.case_id = self.client.post(
            "/api/cases", json={"case_name": "RC", "notes": ""}
        ).json()["case_id"]

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def create_order(self, **updates):
        payload = {
            "title": "异常区间复核",
            "assigned_alias": "MEMBER-C",
            "actor_alias": "DEMO-OPERATOR",
            "note": "demo",
        }
        payload.update(updates)
        return self.client.post(f"/api/cases/{self.case_id}/work-orders", json=payload)

    def event(self, order_id, event_type="STATE_CHANGE", **updates):
        payload = {
            "event_type": event_type,
            "actor_alias": "MEMBER-C",
            "new_state": "IN_REVIEW",
            "note": "",
        }
        payload.update(updates)
        return self.client.post(f"/api/work-orders/{order_id}/events", json=payload)

    def analyze(self):
        for node in ("N1", "N2", "N3"):
            changed = node in {"N2", "N3"}
            response = self.client.post(
                f"/api/cases/{self.case_id}/nodes",
                data={"node_id": node, "surface": "left"},
                files={"file": (f"{node}.png", textured(changed), "image/png")},
            )
            self.assertEqual(response.status_code, 200, response.text)
        response = self.client.post(f"/api/cases/{self.case_id}/analyze")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_health_reports_schema_v3(self):
        self.assertEqual(self.client.get("/api/health").json()["schema_version"], 3)

    def test_schema_has_new_tables(self):
        names = self.service.database.table_names(include_v02=True)
        for name in (
            "work_orders",
            "work_order_events",
            "risk_assessments",
            "case_logistics_nodes",
            "video_analyses",
        ):
            self.assertIn(name, names)

    def test_create_work_order_starts_open(self):
        order = self.create_order().json()
        self.assertEqual(order["current_state"], "OPEN")
        self.assertEqual(order["events"][0]["event_type"], "CREATE")

    def test_list_work_orders(self):
        self.create_order()
        self.assertEqual(
            len(
                self.client.get(f"/api/cases/{self.case_id}/work-orders").json()[
                    "work_orders"
                ]
            ),
            1,
        )

    def test_open_in_review_resolved_e2e(self):
        order = self.create_order().json()
        oid = order["work_order_id"]
        self.assertEqual(self.event(oid).json()["current_state"], "IN_REVIEW")
        resolved = self.event(oid, "RESOLVE", new_state=None).json()
        self.assertEqual(resolved["current_state"], "RESOLVED")
        self.assertEqual(len(resolved["events"]), 3)

    def test_invalid_transition_is_rejected(self):
        oid = self.create_order().json()["work_order_id"]
        response = self.event(oid, new_state="CONFIRMED")
        self.assertEqual(
            (response.status_code, response.json()["error"]["code"]),
            (409, "WORK_ORDER_TRANSITION_INVALID"),
        )

    def test_invalid_create_alias_is_rejected(self):
        response = self.create_order(assigned_alias="REAL-PERSON")
        self.assertEqual(response.json()["error"]["code"], "WORK_ORDER_ALIAS_INVALID")

    def test_assign_alias_event(self):
        oid = self.create_order().json()["work_order_id"]
        order = self.event(oid, "ASSIGN", assigned_alias="MEMBER-A").json()
        self.assertEqual(order["assigned_alias"], "MEMBER-A")

    def test_add_note_preserves_state(self):
        oid = self.create_order().json()["work_order_id"]
        order = self.event(oid, "NOTE", note="checked").json()
        self.assertEqual(order["current_state"], "OPEN")
        self.assertEqual(order["events"][-1]["note"], "checked")

    def test_evidence_request_requires_text(self):
        oid = self.create_order().json()["work_order_id"]
        response = self.event(oid, "EVIDENCE_REQUEST", evidence_request="")
        self.assertEqual(response.json()["error"]["code"], "EVIDENCE_REQUEST_EMPTY")

    def test_evidence_request_is_recorded(self):
        oid = self.create_order().json()["work_order_id"]
        order = self.event(
            oid, "EVIDENCE_REQUEST", evidence_request="补充 top 表面"
        ).json()
        self.assertEqual(order["events"][-1]["evidence_request"], "补充 top 表面")

    def test_event_history_rejects_update(self):
        oid = self.create_order().json()["work_order_id"]
        event_id = self.service.database.work_order_history(oid)[0]["event_id"]
        with self.assertRaises(sqlite3.IntegrityError):
            with self.service.database.connect() as connection:
                connection.execute(
                    "UPDATE work_order_events SET note='x' WHERE event_id=?",
                    (event_id,),
                )

    def test_event_history_rejects_delete(self):
        oid = self.create_order().json()["work_order_id"]
        event_id = self.service.database.work_order_history(oid)[0]["event_id"]
        with self.assertRaises(sqlite3.IntegrityError):
            with self.service.database.connect() as connection:
                connection.execute(
                    "DELETE FROM work_order_events WHERE event_id=?", (event_id,)
                )

    def test_json_logistics_import_e2e(self):
        response = self.client.post(
            f"/api/cases/{self.case_id}/logistics/import",
            data={"data_format": "json"},
            files={
                "file": (
                    "nodes.json",
                    json.dumps(logistics_rows()).encode(),
                    "application/json",
                )
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [x["node_id"] for x in response.json()["nodes"]], ["N1", "N2", "N3"]
        )

    def test_csv_logistics_import_e2e(self):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=list(logistics_rows()[0]))
        writer.writeheader()
        writer.writerows(logistics_rows())
        response = self.client.post(
            f"/api/cases/{self.case_id}/logistics/import",
            data={"data_format": "csv"},
            files={"file": ("nodes.csv", stream.getvalue().encode(), "text/csv")},
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["nodes"]), 3)

    def test_logistics_error_is_structured(self):
        response = self.client.post(
            f"/api/cases/{self.case_id}/logistics/import",
            data={"data_format": "json"},
            files={"file": ("bad.json", b"[{}]", "application/json")},
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["details"]["field"], "package_alias")

    def test_case_detail_contains_logistics(self):
        self.service.import_logistics(
            self.case_id, json.dumps(logistics_rows()).encode(), "json"
        )
        detail = self.client.get(f"/api/cases/{self.case_id}").json()
        self.assertEqual(len(detail["logistics_nodes"]), 3)

    def test_case_detail_contains_work_orders(self):
        self.create_order()
        detail = self.client.get(f"/api/cases/{self.case_id}").json()
        self.assertEqual(detail["work_orders"][0]["events"][0]["event_type"], "CREATE")

    def test_dashboard_uses_sqlite_counts(self):
        self.create_order()
        summary = self.client.get("/api/dashboard/summary").json()
        self.assertEqual(summary["source"], "SQLite")
        self.assertEqual(summary["case_count"], 1)
        self.assertEqual(summary["work_order_count"], 1)

    def test_dashboard_resolved_count_changes(self):
        oid = self.create_order().json()["work_order_id"]
        self.event(oid, "RESOLVE", new_state=None)
        summary = self.client.get("/api/dashboard/summary").json()
        self.assertEqual(summary["resolved_work_order_count"], 1)

    def test_dashboard_trends_are_sqlite_series(self):
        payload = self.client.get("/api/dashboard/trends").json()
        self.assertEqual(payload["source"], "SQLite")
        self.assertEqual(payload["cases"][0]["count"], 1)

    def test_risk_endpoint_after_analysis(self):
        self.analyze()
        response = self.client.get(f"/api/cases/{self.case_id}/risk")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["legal_responsibility_conclusion"], "NOT_SUPPORTED"
        )

    def test_analysis_returns_processing_breakdown(self):
        payload = self.analyze()
        self.assertEqual(
            set(payload["processing_breakdown_ms"]),
            {"core_analysis", "database", "risk_engine", "report", "total_request"},
        )

    def test_report_contains_work_order_history(self):
        self.analyze()
        self.create_order()
        text = self.client.get(f"/api/cases/{self.case_id}/report").text
        self.assertIn("工单事件历史", text)
        self.assertIn("CREATE", text)

    def test_report_contains_logistics_timeline(self):
        self.analyze()
        self.service.import_logistics(
            self.case_id, json.dumps(logistics_rows()).encode(), "json"
        )
        text = self.client.get(f"/api/cases/{self.case_id}/report").text
        self.assertIn("PKG-DEMO-001", text)
        self.assertIn("LOC-2", text)


class SchemaMigrationV10Tests(unittest.TestCase):
    def test_v2_database_is_migrated_additively(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "db.sqlite"
            old = EvidenceDatabase(path)
            self.assertEqual(old.schema_version(), 2)
            upgraded = EvidenceDatabase(path, target_schema_version=3)
            self.assertEqual(upgraded.schema_version(), 3)
            self.assertIn(
                RC_MIGRATION_ID, {x["migration_id"] for x in upgraded.migrations()}
            )

    def test_rc_migration_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "db.sqlite"
            EvidenceDatabase(path)
            EvidenceDatabase(path, target_schema_version=3)
            upgraded = EvidenceDatabase(path, target_schema_version=3)
            self.assertEqual(
                sum(
                    x["migration_id"] == RC_MIGRATION_ID for x in upgraded.migrations()
                ),
                1,
            )


if __name__ == "__main__":
    unittest.main()
