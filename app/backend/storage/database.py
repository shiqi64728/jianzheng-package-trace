"""Versioned SQLite persistence for the competition evidence chain.

The v0.2 migration deliberately keeps the original v0.1 ``case_nodes`` table
under a backup name.  Existing databases are copied with SQLite's backup API
before they are migrated when ``bootstrap_from`` is supplied, so the v0.1
runtime remains byte-for-byte outside the v0.2 write path.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
MIGRATION_ID = "001-v01-case-nodes-to-multisurface-v02"

BASE_SCHEMA = """
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
    surface TEXT NOT NULL DEFAULT 'front',
    capture_time TEXT,
    image_path TEXT NOT NULL,
    image_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (case_id, node_id, surface),
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    surface TEXT NOT NULL DEFAULT 'front',
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
    surface TEXT NOT NULL DEFAULT 'front',
    pair_status TEXT NOT NULL DEFAULT 'AVAILABLE',
    registration_status TEXT NOT NULL,
    change_score REAL NOT NULL,
    changed_pixel_ratio REAL NOT NULL,
    result_json TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS surface_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    surface TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE (case_id, node_id, surface),
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
CREATE TABLE IF NOT EXISTS review_events (
    review_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    node_from TEXT NOT NULL,
    node_to TEXT NOT NULL,
    surface TEXT NOT NULL,
    machine_result TEXT NOT NULL,
    review_class TEXT NOT NULL,
    review_status TEXT NOT NULL,
    reviewer_alias TEXT NOT NULL,
    review_note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    supersedes_review_id TEXT,
    review_payload_sha256 TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE,
    FOREIGN KEY (supersedes_review_id) REFERENCES review_events(review_id)
);
CREATE TABLE IF NOT EXISTS schema_version (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    version INTEGER NOT NULL,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS database_migrations (
    migration_id TEXT PRIMARY KEY,
    from_version INTEGER NOT NULL,
    to_version INTEGER NOT NULL,
    applied_at TEXT NOT NULL,
    details_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_review_events_case_created
    ON review_events(case_id, created_at, review_id);
CREATE TRIGGER IF NOT EXISTS review_events_append_only_update
BEFORE UPDATE ON review_events
BEGIN
    SELECT RAISE(ABORT, 'review_events are append-only');
END;
CREATE TRIGGER IF NOT EXISTS review_events_append_only_delete
BEFORE DELETE ON review_events
BEGIN
    SELECT RAISE(ABORT, 'review_events are append-only');
END;
"""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


class EvidenceDatabase:
    """Thread-safe-by-connection evidence repository with idempotent migration."""

    def __init__(
        self,
        path: str | Path,
        bootstrap_from: str | Path | None = None,
    ):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists() and bootstrap_from:
            source = Path(bootstrap_from)
            if source.is_file() and source.resolve() != self.path.resolve():
                self._copy_database(source)
        self.initialize()

    def _copy_database(self, source: Path) -> None:
        """Copy a source database consistently without opening it for writes."""
        source_connection = sqlite3.connect(
            f"file:{source.as_posix()}?mode=ro", uri=True, timeout=30.0
        )
        destination = sqlite3.connect(self.path, timeout=30.0)
        try:
            source_connection.backup(destination)
        finally:
            destination.close()
            source_connection.close()

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

    @staticmethod
    def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
        return {
            str(row[1])
            for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        }

    @staticmethod
    def _primary_key(connection: sqlite3.Connection, table: str) -> list[str]:
        rows = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [
            str(row[1]) for row in sorted(rows, key=lambda row: int(row[5])) if row[5]
        ]

    def initialize(self) -> None:
        with self.connect() as connection:
            existing = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='case_nodes'"
            ).fetchone()
            if existing and self._primary_key(connection, "case_nodes") != [
                "case_id",
                "node_id",
                "surface",
            ]:
                self._migrate_case_nodes_v01(connection)
            connection.executescript(BASE_SCHEMA)
            self._add_v02_columns(connection)
            connection.executescript(
                """CREATE INDEX IF NOT EXISTS idx_case_nodes_case_node
                       ON case_nodes(case_id,node_id,surface);
                   CREATE INDEX IF NOT EXISTS idx_pair_changes_case_interval
                       ON pair_changes(case_id,reference_node_id,current_node_id,surface);"""
            )
            prior = connection.execute(
                "SELECT version FROM schema_version WHERE singleton=1"
            ).fetchone()
            if prior is None:
                connection.execute(
                    "INSERT INTO schema_version(singleton,version,applied_at) VALUES(1,?,?)",
                    (SCHEMA_VERSION, _now()),
                )
            elif int(prior["version"]) < SCHEMA_VERSION:
                connection.execute(
                    "UPDATE schema_version SET version=?,applied_at=? WHERE singleton=1",
                    (SCHEMA_VERSION, _now()),
                )

    def _migrate_case_nodes_v01(self, connection: sqlite3.Connection) -> None:
        backup = "case_nodes_v01_backup"
        backup_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (backup,)
        ).fetchone()
        if backup_exists:
            raise RuntimeError(
                "v0.1 backup table already exists but migration is incomplete"
            )
        connection.execute("ALTER TABLE case_nodes RENAME TO case_nodes_v01_backup")
        connection.execute(
            """CREATE TABLE case_nodes (
                case_id TEXT NOT NULL,
                node_id TEXT NOT NULL,
                surface TEXT NOT NULL DEFAULT 'front',
                capture_time TEXT,
                image_path TEXT NOT NULL,
                image_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (case_id,node_id,surface),
                FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
            )"""
        )
        connection.execute(
            """INSERT INTO case_nodes
            (case_id,node_id,surface,capture_time,image_path,image_sha256,created_at)
            SELECT case_id,node_id,
                   CASE WHEN lower(surface) IN ('package_exterior','') THEN 'front'
                        ELSE lower(surface) END,
                   capture_time,image_path,image_sha256,created_at
            FROM case_nodes_v01_backup"""
        )
        connection.executescript(
            """CREATE TABLE IF NOT EXISTS database_migrations (
                migration_id TEXT PRIMARY KEY,
                from_version INTEGER NOT NULL,
                to_version INTEGER NOT NULL,
                applied_at TEXT NOT NULL,
                details_json TEXT NOT NULL
            );"""
        )
        connection.execute(
            """INSERT OR IGNORE INTO database_migrations
            (migration_id,from_version,to_version,applied_at,details_json)
            VALUES(?,?,?,?,?)""",
            (
                MIGRATION_ID,
                1,
                SCHEMA_VERSION,
                _now(),
                json.dumps(
                    {
                        "strategy": "rename-copy-preserve",
                        "backup_table": backup,
                        "primary_key": ["case_id", "node_id", "surface"],
                        "compatibility_surface": "front",
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            ),
        )

    def _add_v02_columns(self, connection: sqlite3.Connection) -> None:
        additions = {
            "detections": {
                "surface": "TEXT NOT NULL DEFAULT 'front'",
            },
            "pair_changes": {
                "surface": "TEXT NOT NULL DEFAULT 'front'",
                "pair_status": "TEXT NOT NULL DEFAULT 'AVAILABLE'",
            },
        }
        for table, columns in additions.items():
            existing = self._columns(connection, table)
            for name, declaration in columns.items():
                if name not in existing:
                    connection.execute(
                        f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}'
                    )

    def schema_version(self) -> int:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT version FROM schema_version WHERE singleton=1"
            ).fetchone()
        return int(row["version"])

    def migrations(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM database_migrations ORDER BY applied_at,migration_id"
            ).fetchall()
        return [
            {**dict(row), "details": json.loads(row["details_json"])} for row in rows
        ]

    def table_names(self, include_v02: bool = False) -> list[str]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        names = [str(row["name"]) for row in rows if row["name"] != "sqlite_sequence"]
        if include_v02:
            return names
        # Keep the v0.1 introspection contract for callers that used this helper.
        legacy = {
            "cases",
            "case_nodes",
            "detections",
            "pair_changes",
            "analysis_results",
            "reports",
        }
        return [name for name in names if name in legacy]

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
                "SELECT * FROM case_nodes WHERE case_id=? ORDER BY node_id,surface",
                (case_id,),
            ).fetchall()
            detections = connection.execute(
                "SELECT * FROM detections WHERE case_id=? ORDER BY node_id,surface,id",
                (case_id,),
            ).fetchall()
            pairs = connection.execute(
                "SELECT * FROM pair_changes WHERE case_id=? ORDER BY reference_node_id,current_node_id,surface,id",
                (case_id,),
            ).fetchall()
            surfaces = connection.execute(
                "SELECT * FROM surface_analysis WHERE case_id=? ORDER BY node_id,surface",
                (case_id,),
            ).fetchall()
            analysis = connection.execute(
                "SELECT * FROM analysis_results WHERE case_id=?", (case_id,)
            ).fetchone()
            report = connection.execute(
                "SELECT * FROM reports WHERE case_id=?", (case_id,)
            ).fetchone()
            reviews = connection.execute(
                "SELECT * FROM review_events WHERE case_id=? ORDER BY created_at,review_id",
                (case_id,),
            ).fetchall()
        result["nodes"] = [dict(row) for row in nodes]
        result["detections"] = [
            {**dict(row), "bbox": json.loads(row["bbox_json"])} for row in detections
        ]
        result["pair_changes"] = [
            {**dict(row), "result": json.loads(row["result_json"])} for row in pairs
        ]
        result["surface_analysis"] = [
            {**dict(row), "result": json.loads(row["result_json"])} for row in surfaces
        ]
        result["analysis"] = (
            {**dict(analysis), "result": json.loads(analysis["result_json"])}
            if analysis
            else None
        )
        result["report"] = dict(report) if report else None
        result["reviews"] = [dict(row) for row in reviews]
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
            connection.execute(
                "DELETE FROM surface_analysis WHERE case_id=?", (case_id,)
            )
            for node in node_results:
                surface = node.get("surface", "front")
                for detection in node.get("detections", []):
                    connection.execute(
                        """INSERT INTO detections
                        (case_id,node_id,surface,class_code,class_name,confidence,bbox_json,model_version)
                        VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            case_id,
                            node["node_id"],
                            surface,
                            detection["class_code"],
                            detection["class_name"],
                            detection["confidence"],
                            json.dumps(detection["bbox_xyxy"]),
                            node["model_version"],
                        ),
                    )
                connection.execute(
                    """INSERT INTO surface_analysis
                    (case_id,node_id,surface,result_json,created_at) VALUES(?,?,?,?,?)""",
                    (
                        case_id,
                        node["node_id"],
                        surface,
                        json.dumps(node, ensure_ascii=False),
                        created_at,
                    ),
                )
            for pair in pair_results:
                connection.execute(
                    """INSERT INTO pair_changes
                    (case_id,reference_node_id,current_node_id,surface,pair_status,
                     registration_status,change_score,changed_pixel_ratio,result_json)
                    VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        case_id,
                        pair["reference_node_id"],
                        pair["current_node_id"],
                        pair.get("surface", "front"),
                        pair.get("pair_status", "AVAILABLE"),
                        pair["registration_status"],
                        pair.get("change_score", 0.0),
                        pair.get("changed_pixel_ratio", 0.0),
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
                (case_id, created_at, report["json_path"], report["html_path"]),
            )
            connection.execute(
                "UPDATE cases SET status='ANALYZED' WHERE case_id=?", (case_id,)
            )

    def add_review(self, record: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "review_id",
            "case_id",
            "node_from",
            "node_to",
            "surface",
            "machine_result",
            "review_class",
            "review_status",
            "reviewer_alias",
            "review_note",
            "created_at",
            "supersedes_review_id",
            "review_payload_sha256",
        )
        with self.connect() as connection:
            connection.execute(
                f"INSERT INTO review_events ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                [record.get(field) for field in fields],
            )
        return dict(record)

    def review_for(self, review_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_events WHERE review_id=?", (review_id,)
            ).fetchone()
        if row is None:
            raise KeyError(review_id)
        return dict(row)

    def list_reviews(self, case_id: str) -> list[dict[str, Any]]:
        with self.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM cases WHERE case_id=?", (case_id,)
            ).fetchone()
            if exists is None:
                raise KeyError(case_id)
            rows = connection.execute(
                "SELECT * FROM review_events WHERE case_id=? ORDER BY created_at,review_id",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_report(
        self, case_id: str, created_at: str, report: dict[str, str]
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """INSERT OR REPLACE INTO reports
                (case_id,created_at,json_path,html_path) VALUES (?,?,?,?)""",
                (case_id, created_at, report["json_path"], report["html_path"]),
            )

    def report_for(self, case_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reports WHERE case_id=?", (case_id,)
            ).fetchone()
        if row is None:
            raise KeyError(case_id)
        return dict(row)
