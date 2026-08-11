"""SQLite evidence-chain persistence without personal logistics fields."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    case_name TEXT NOT NULL,
    status TEXT NOT NULL,
    pipeline_version TEXT NOT NULL,
    active_model_version TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS case_nodes (
    case_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    surface TEXT NOT NULL,
    capture_time TEXT,
    image_path TEXT NOT NULL,
    image_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (case_id, node_id),
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    class_code TEXT NOT NULL,
    class_name TEXT NOT NULL,
    confidence REAL NOT NULL,
    bbox_json TEXT NOT NULL,
    model_version TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS pair_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    reference_node_id TEXT NOT NULL,
    current_node_id TEXT NOT NULL,
    registration_status TEXT NOT NULL,
    change_score REAL NOT NULL,
    changed_pixel_ratio REAL NOT NULL,
    result_json TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS analysis_results (
    case_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    conclusion_code TEXT NOT NULL,
    first_abnormal_interval TEXT,
    evidence_level TEXT NOT NULL,
    result_json TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS reports (
    case_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    json_path TEXT NOT NULL,
    html_path TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
"""


class EvidenceDatabase:
    """Small, thread-safe-by-connection SQLite repository."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)

    def table_names(self) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        return [str(row["name"]) for row in rows if row["name"] != "sqlite_sequence"]

    def create_case(self, record: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "case_id",
            "created_at",
            "case_name",
            "status",
            "pipeline_version",
            "active_model_version",
            "notes",
        )
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO cases ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                [record.get(field, "") for field in fields],
            )
        return self.get_case(record["case_id"], include_details=False)

    def add_node(self, record: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "case_id",
            "node_id",
            "surface",
            "capture_time",
            "image_path",
            "image_sha256",
            "created_at",
        )
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO case_nodes ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                [record.get(field) for field in fields],
            )
            connection.execute(
                "UPDATE cases SET status='COLLECTING' WHERE case_id=?",
                (record["case_id"],),
            )
        return dict(record)

    def list_cases(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cases ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_case(self, case_id: str, include_details: bool = True) -> dict[str, Any]:
        with self.connect() as connection:
            case = connection.execute(
                "SELECT * FROM cases WHERE case_id=?", (case_id,)
            ).fetchone()
            if case is None:
                raise KeyError(case_id)
            result = dict(case)
            if not include_details:
                return result
            nodes = connection.execute(
                "SELECT * FROM case_nodes WHERE case_id=? ORDER BY node_id", (case_id,)
            ).fetchall()
            detections = connection.execute(
                "SELECT * FROM detections WHERE case_id=? ORDER BY node_id,id",
                (case_id,),
            ).fetchall()
            pairs = connection.execute(
                "SELECT * FROM pair_changes WHERE case_id=? ORDER BY id", (case_id,)
            ).fetchall()
            analysis = connection.execute(
                "SELECT * FROM analysis_results WHERE case_id=?", (case_id,)
            ).fetchone()
            report = connection.execute(
                "SELECT * FROM reports WHERE case_id=?", (case_id,)
            ).fetchone()
        result["nodes"] = [dict(row) for row in nodes]
        result["detections"] = [
            {**dict(row), "bbox": json.loads(row["bbox_json"])} for row in detections
        ]
        result["pair_changes"] = [
            {**dict(row), "result": json.loads(row["result_json"])} for row in pairs
        ]
        result["analysis"] = (
            {**dict(analysis), "result": json.loads(analysis["result_json"])}
            if analysis
            else None
        )
        result["report"] = dict(report) if report else None
        return result

    def store_analysis(
        self,
        case_id: str,
        created_at: str,
        node_results: list[dict[str, Any]],
        pair_results: list[dict[str, Any]],
        analysis: dict[str, Any],
        report: dict[str, str],
    ) -> None:
        with self.connect() as connection:
            connection.execute("DELETE FROM detections WHERE case_id=?", (case_id,))
            connection.execute("DELETE FROM pair_changes WHERE case_id=?", (case_id,))
            for node in node_results:
                for detection in node.get("detections", []):
                    connection.execute(
                        """INSERT INTO detections
                        (case_id,node_id,class_code,class_name,confidence,bbox_json,model_version)
                        VALUES (?,?,?,?,?,?,?)""",
                        (
                            case_id,
                            node["node_id"],
                            detection["class_code"],
                            detection["class_name"],
                            detection["confidence"],
                            json.dumps(detection["bbox_xyxy"]),
                            node["model_version"],
                        ),
                    )
            for pair in pair_results:
                connection.execute(
                    """INSERT INTO pair_changes
                    (case_id,reference_node_id,current_node_id,registration_status,
                     change_score,changed_pixel_ratio,result_json)
                    VALUES (?,?,?,?,?,?,?)""",
                    (
                        case_id,
                        pair["reference_node_id"],
                        pair["current_node_id"],
                        pair["registration_status"],
                        pair["change_score"],
                        pair["changed_pixel_ratio"],
                        json.dumps(pair, ensure_ascii=False),
                    ),
                )
            connection.execute(
                """INSERT OR REPLACE INTO analysis_results
                (case_id,created_at,conclusion_code,first_abnormal_interval,
                 evidence_level,result_json) VALUES (?,?,?,?,?,?)""",
                (
                    case_id,
                    created_at,
                    analysis["conclusion_code"],
                    analysis.get("first_abnormal_interval"),
                    analysis["evidence_level"],
                    json.dumps(analysis, ensure_ascii=False),
                ),
            )
            connection.execute(
                """INSERT OR REPLACE INTO reports
                (case_id,created_at,json_path,html_path) VALUES (?,?,?,?)""",
                (
                    case_id,
                    created_at,
                    report["json_path"],
                    report["html_path"],
                ),
            )
            connection.execute(
                "UPDATE cases SET status='ANALYZED' WHERE case_id=?", (case_id,)
            )

    def report_for(self, case_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reports WHERE case_id=?", (case_id,)
            ).fetchone()
        if row is None:
            raise KeyError(case_id)
        return dict(row)
