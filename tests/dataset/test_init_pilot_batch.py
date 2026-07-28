from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.dataset import init_pilot_batch as initializer  # noqa: E402


class PilotBatchInitializerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.output_root = self.root / "incoming"
        self.output_root.mkdir()
        self.schema_path = (
            REPO_ROOT / "configs" / "training" / "manifest-schema-v0.1.json"
        )
        self.template_path = (
            REPO_ROOT
            / "dataset"
            / "manifests"
            / "templates"
            / "manifest-v0.1.template.csv"
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def initialize(self, **changes: object) -> Path:
        arguments: dict[str, object] = {
            "output_root": self.output_root,
            "batch_id": "BATCH-PILOT-001",
            "source_type": "field_normal",
            "collector": "MEMBER-C",
            "device_id": "PHONE-C-001",
            "schema_path": self.schema_path,
            "template_path": self.template_path,
        }
        arguments.update(changes)
        return initializer.initialize_pilot_batch(**arguments)  # type: ignore[arg-type]

    def test_legal_batch_initialization_succeeds(self) -> None:
        batch_dir = self.initialize()
        self.assertEqual(batch_dir, self.output_root / "BATCH-PILOT-001")
        self.assertTrue(batch_dir.is_dir())

    def test_standard_directory_structure_is_created(self) -> None:
        batch_dir = self.initialize()
        expected = {
            "images",
            "annotations",
            "setup_photos",
            "reports",
            "manifest.csv",
            "batch-info.json",
            "README-COLLECTION.txt",
            "SHA256SUMS.txt",
        }
        self.assertEqual({path.name for path in batch_dir.iterdir()}, expected)
        for name in initializer.SUBDIRECTORIES:
            self.assertTrue((batch_dir / name).is_dir())

    def test_manifest_header_matches_template_and_has_bom(self) -> None:
        batch_dir = self.initialize()
        manifest = batch_dir / "manifest.csv"
        self.assertTrue(manifest.read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertEqual(manifest.read_bytes(), self.template_path.read_bytes())
        with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        self.assertEqual(len(rows), 1)
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        self.assertEqual(rows[0], schema["fields"])

    def test_batch_info_contains_complete_stable_fields(self) -> None:
        batch_dir = self.initialize(
            camera_or_phone_model="TEST-PHONE",
            lens="rear-main-1x",
            resolution_setting="original",
            aspect_ratio_setting="4:3",
        )
        payload = json.loads(
            (batch_dir / "batch-info.json").read_text(encoding="utf-8")
        )
        self.assertEqual(tuple(payload), initializer.BATCH_INFO_FIELDS)
        self.assertEqual(payload["manifest_schema_version"], "0.1")
        self.assertEqual(payload["batch_schema_version"], "0.1")
        self.assertEqual(payload["camera_or_phone_model"], "TEST-PHONE")

    def test_permission_defaults_to_pending_and_timestamp_has_timezone(self) -> None:
        batch_dir = self.initialize()
        payload = json.loads(
            (batch_dir / "batch-info.json").read_text(encoding="utf-8")
        )
        self.assertEqual(payload["permission_status"], "pending")
        created_at = datetime.fromisoformat(payload["created_at"])
        self.assertIsNotNone(created_at.tzinfo)
        self.assertIsNotNone(created_at.utcoffset())

    def test_sha256sums_covers_only_initial_files(self) -> None:
        batch_dir = self.initialize()
        lines = (batch_dir / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
        expected_names = {
            "manifest.csv",
            "batch-info.json",
            "README-COLLECTION.txt",
        }
        actual_names: set[str] = set()
        for line in lines:
            digest, name = line.split(" *", 1)
            actual_names.add(name)
            self.assertEqual(
                digest,
                hashlib.sha256((batch_dir / name).read_bytes()).hexdigest(),
            )
        self.assertEqual(actual_names, expected_names)

    def test_same_batch_is_rejected_without_overwriting(self) -> None:
        batch_dir = self.initialize()
        marker = batch_dir / "existing-marker.txt"
        marker.write_text("KEEP", encoding="utf-8")
        with self.assertRaises(initializer.BatchInputError):
            self.initialize()
        self.assertEqual(marker.read_text(encoding="utf-8"), "KEEP")

    def test_invalid_batch_ids_are_rejected(self) -> None:
        invalid_ids = (
            "..",
            "BATCH..001",
            "../BATCH",
            r"..\BATCH",
            "A/B",
            r"A\B",
            "C:batch",
            "//server/share",
            r"\\server\share",
        )
        for batch_id in invalid_ids:
            with self.subTest(batch_id=batch_id):
                with self.assertRaises(initializer.BatchInputError):
                    self.initialize(batch_id=batch_id)
        self.assertEqual(list(self.output_root.iterdir()), [])

    def test_missing_first_round_template_is_config_error(self) -> None:
        missing = self.root / "missing-template.csv"
        with self.assertRaises(initializer.BatchConfigError):
            self.initialize(template_path=missing)
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = initializer.main(
                [
                    "--output-root",
                    str(self.output_root),
                    "--batch-id",
                    "BATCH-PILOT-001",
                    "--source-type",
                    "field_normal",
                    "--collector",
                    "MEMBER-C",
                    "--device-id",
                    "PHONE-C-001",
                    "--template",
                    str(missing),
                ]
            )
        self.assertEqual(exit_code, initializer.EXIT_CONFIG_ERROR)

    def test_failure_cleans_only_newly_created_structure(self) -> None:
        existing = self.output_root / "preexisting"
        existing.mkdir()
        marker = existing / "marker.txt"
        marker.write_text("KEEP", encoding="utf-8")
        with patch.object(initializer, "_write_bytes", side_effect=OSError("TEST")):
            with self.assertRaises(OSError):
                self.initialize()
        self.assertFalse((self.output_root / "BATCH-PILOT-001").exists())
        self.assertEqual(marker.read_text(encoding="utf-8"), "KEEP")

    def test_invalid_source_type_is_rejected_before_creation(self) -> None:
        with self.assertRaises(initializer.BatchInputError):
            self.initialize(source_type="unknown_source")
        self.assertEqual(list(self.output_root.iterdir()), [])

    def test_relative_output_root_is_rejected(self) -> None:
        with self.assertRaises(initializer.BatchInputError):
            self.initialize(output_root=Path("relative"))


if __name__ == "__main__":
    unittest.main()
