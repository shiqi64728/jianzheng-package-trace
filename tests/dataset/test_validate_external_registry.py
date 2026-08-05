from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.dataset import validate_external_registry as validator  # noqa: E402
from dataset.external_test_support import SCHEMA, create_external_fixture  # noqa: E402


class ExternalRegistryValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.paths = create_external_fixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def validate(self) -> dict:
        return validator.validate_registry(
            self.paths["registry"],
            self.paths["licenses"],
            self.paths["citations"],
            SCHEMA,
            self.paths["external"],
        )

    def test_valid_registry_passes(self) -> None:
        report = self.validate()
        self.assertTrue(report["summary"]["valid"])
        self.assertEqual(report["summary"]["downloaded_source_count"], 3)

    def test_duplicate_source_id_fails(self) -> None:
        with self.paths["registry"].open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
            fields = list(rows[0])
        rows.append(rows[0].copy())
        with self.paths["registry"].open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        self.assertFalse(self.validate()["summary"]["valid"])

    def test_missing_license_file_fails(self) -> None:
        (self.paths["licenses"] / "CC-BY-4.0-legalcode.txt").unlink()
        report = self.validate()
        self.assertFalse(report["summary"]["valid"])
        self.assertIn(
            "LICENSE_FILE_MISSING", {item["code"] for item in report["issues"]}
        )

    def test_missing_citation_fails_for_downloaded_source(self) -> None:
        next(self.paths["citations"].glob("*.bib")).unlink()
        report = self.validate()
        self.assertFalse(report["summary"]["valid"])
        self.assertIn(
            "CITATION_FILE_MISSING", {item["code"] for item in report["issues"]}
        )

    def test_blocked_downloaded_source_is_rejected(self) -> None:
        text = self.paths["registry"].read_text(encoding="utf-8-sig")
        self.paths["registry"].write_text(
            text.replace("candidate_only", "blocked_unknown", 1), encoding="utf-8-sig"
        )
        report = self.validate()
        self.assertIn(
            "BLOCKED_SOURCE_ACCEPTED", {item["code"] for item in report["issues"]}
        )

    def test_registry_is_not_modified_and_cli_writes_report(self) -> None:
        before = hashlib.sha256(self.paths["registry"].read_bytes()).hexdigest()
        output = self.paths["reports"] / "registry-report.json"
        code = validator.main(
            [
                "--source-registry",
                str(self.paths["registry"]),
                "--licenses-dir",
                str(self.paths["licenses"]),
                "--citations-dir",
                str(self.paths["citations"]),
                "--external-schema",
                str(SCHEMA),
                "--external-root",
                str(self.paths["external"]),
                "--report",
                str(output),
            ]
        )
        after = hashlib.sha256(self.paths["registry"].read_bytes()).hexdigest()
        self.assertEqual(code, 0)
        self.assertEqual(before, after)
        self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["read_only"])


if __name__ == "__main__":
    unittest.main()
