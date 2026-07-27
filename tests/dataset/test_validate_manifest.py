from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.dataset import validate_manifest as validator  # noqa: E402


class ManifestValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.data_root = self.root / "data"
        self.images_root = self.data_root / "images"
        self.images_root.mkdir(parents=True)
        self.manifest = self.root / "manifest.csv"
        self.report_path = self.root / "validation-report.json"
        self.schema_path = (
            REPO_ROOT / "configs" / "training" / "manifest-schema-v0.1.json"
        )
        self.schema = validator.load_schema(self.schema_path)
        self.fields = list(self.schema["fields"])
        image = np.zeros((8, 8, 3), dtype=np.uint8)
        self.assertTrue(cv2.imwrite(str(self.images_root / "valid.png"), image))

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def valid_record(self, **changes: str) -> dict[str, str]:
        record = {
            "schema_version": "0.1",
            "record_id": "REC-001",
            "package_id": "PKG-001",
            "batch_id": "BATCH-001",
            "sequence_id": "",
            "source_type": "field_normal",
            "image_relpath": "images/valid.png",
            "surface": "FRONT",
            "node_id": "NA",
            "capture_time": "2026-07-01T09:00:00+08:00",
            "device_id": "DEVICE-01",
            "status": "normal",
            "damage_type": "NONE",
            "severity": "none",
            "first_abnormal_node": "NONE",
            "privacy_status": "masked",
            "annotation_status": "reviewed",
            "split": "train",
            "collector": "C",
            "reviewer": "A",
            "notes": "TEST_ONLY",
        }
        record.update(changes)
        return record

    def valid_sequence(self, split: str = "train") -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for index, node in enumerate(("N1", "N2", "N3"), 1):
            status = "abnormal" if node == "N3" else "normal"
            rows.append(
                self.valid_record(
                    record_id=f"REC-SEQ-{index:03d}",
                    package_id="PKG-SEQ-001",
                    batch_id="BATCH-SEQ-001",
                    sequence_id="SEQ-001",
                    source_type="continuous_node",
                    image_relpath=f"images/seq_{node}.png",
                    node_id=node,
                    status=status,
                    damage_type="D02" if status == "abnormal" else "NONE",
                    severity="medium" if status == "abnormal" else "none",
                    first_abnormal_node="N3",
                    privacy_status="not_applicable",
                    split=split,
                )
            )
        return rows

    def write_manifest(
        self,
        rows: list[dict[str, str]],
        *,
        fieldnames: list[str] | None = None,
        encoding: str = "utf-8",
    ) -> None:
        selected_fields = fieldnames or self.fields
        with self.manifest.open("w", encoding=encoding, newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=selected_fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {field: row.get(field, "") for field in selected_fields}
                )

    def validate(
        self, rows: list[dict[str, str]], *, check_files: bool = False
    ) -> validator.ValidationReport:
        self.write_manifest(rows)
        return validator.validate_manifest(
            self.manifest,
            self.data_root,
            self.schema_path,
            check_files=check_files,
        )

    def assert_issue(
        self, report: validator.ValidationReport, code: str
    ) -> validator.Issue:
        for issue in report.issues:
            if issue.code == code:
                return issue
        self.fail(
            f"未找到错误代码 {code}；实际为 {[item.code for item in report.issues]}"
        )

    def test_valid_manifest_passes(self) -> None:
        report = self.validate([self.valid_record()], check_files=True)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.passed_records, 1)
        self.assertEqual(report.failed_records, 0)

    def test_valid_continuous_sequence_passes(self) -> None:
        report = self.validate(self.valid_sequence())
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.passed_records, 3)

    def test_missing_required_column_fails(self) -> None:
        fields = [field for field in self.fields if field != "package_id"]
        self.write_manifest([self.valid_record()], fieldnames=fields)
        report = validator.validate_manifest(
            self.manifest, self.data_root, self.schema_path
        )
        self.assert_issue(report, "MISSING_COLUMN")
        self.assertGreater(report.error_count, 0)

    def test_duplicate_record_id_fails(self) -> None:
        rows = [
            self.valid_record(),
            self.valid_record(
                package_id="PKG-002",
                image_relpath="images/second.png",
            ),
        ]
        report = self.validate(rows)
        self.assert_issue(report, "DUPLICATE_RECORD_ID")

    def test_duplicate_image_path_fails(self) -> None:
        rows = [
            self.valid_record(),
            self.valid_record(record_id="REC-002", package_id="PKG-002"),
        ]
        report = self.validate(rows)
        self.assert_issue(report, "DUPLICATE_IMAGE_RELPATH")

    def test_normal_record_with_damage_type_fails(self) -> None:
        report = self.validate([self.valid_record(damage_type="D01")])
        self.assert_issue(report, "NORMAL_WITH_DAMAGE_TYPE")

    def test_abnormal_record_without_severity_fails(self) -> None:
        report = self.validate(
            [
                self.valid_record(
                    status="abnormal",
                    damage_type="D02",
                    severity="none",
                    first_abnormal_node="UNKNOWN",
                )
            ]
        )
        self.assert_issue(report, "ABNORMAL_WITHOUT_SEVERITY")

    def test_continuous_record_without_sequence_id_fails(self) -> None:
        report = self.validate(
            [
                self.valid_record(
                    source_type="continuous_node",
                    node_id="N1",
                    sequence_id="",
                )
            ]
        )
        self.assert_issue(report, "CONTINUOUS_MISSING_SEQUENCE_ID")

    def test_package_crossing_train_and_test_fails(self) -> None:
        rows = [
            self.valid_record(),
            self.valid_record(
                record_id="REC-002",
                image_relpath="images/second.png",
                split="test",
            ),
        ]
        report = self.validate(rows)
        self.assert_issue(report, "PACKAGE_SPLIT_LEAKAGE")

    def test_sequence_crossing_splits_fails(self) -> None:
        rows = self.valid_sequence()
        rows[2]["split"] = "test"
        report = self.validate(rows)
        self.assert_issue(report, "SEQUENCE_SPLIT_LEAKAGE")

    def test_absolute_path_fails(self) -> None:
        report = self.validate(
            [self.valid_record(image_relpath="C:/private/parcel.jpg")]
        )
        self.assert_issue(report, "ABSOLUTE_IMAGE_PATH")

    def test_parent_traversal_fails(self) -> None:
        report = self.validate([self.valid_record(image_relpath="../parcel.jpg")])
        self.assert_issue(report, "PARENT_PATH_TRAVERSAL")

    def test_missing_image_fails_when_checking_files(self) -> None:
        report = self.validate(
            [self.valid_record(image_relpath="images/missing.png")],
            check_files=True,
        )
        self.assert_issue(report, "IMAGE_NOT_FOUND")

    def test_non_image_file_fails_when_checking_files(self) -> None:
        bad_image = self.images_root / "not-image.jpg"
        bad_image.write_text("not an image", encoding="utf-8")
        report = self.validate(
            [self.valid_record(image_relpath="images/not-image.jpg")],
            check_files=True,
        )
        self.assert_issue(report, "IMAGE_UNREADABLE")

    def test_utf8_bom_manifest_is_readable(self) -> None:
        self.write_manifest([self.valid_record()], encoding="utf-8-sig")
        report = validator.validate_manifest(
            self.manifest,
            self.data_root,
            self.schema_path,
            check_files=True,
        )
        self.assertEqual(report.error_count, 0)

    def test_json_report_is_generated(self) -> None:
        report = self.validate([self.valid_record()])
        validator.write_report(report, self.report_path)
        payload = json.loads(self.report_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["error_count"], 0)
        self.assertEqual(payload["summary"]["passed_records"], 1)
        self.assertEqual(payload["schema_version"], "0.1")

    def test_extra_column_produces_warning(self) -> None:
        fields = [*self.fields, "unexpected"]
        row = self.valid_record()
        row["unexpected"] = "value"
        self.write_manifest([row], fieldnames=fields)
        report = validator.validate_manifest(
            self.manifest, self.data_root, self.schema_path
        )
        self.assertEqual(report.error_count, 0)
        self.assert_issue(report, "EXTRA_COLUMN")

    def test_package_id_reuse_across_batches_fails(self) -> None:
        rows = [
            self.valid_record(),
            self.valid_record(
                record_id="REC-002",
                batch_id="BATCH-002",
                image_relpath="images/second.png",
            ),
        ]
        report = self.validate(rows)
        self.assert_issue(report, "PACKAGE_ID_BATCH_CONFLICT")

    def test_rejected_privacy_status_fails(self) -> None:
        report = self.validate([self.valid_record(privacy_status="rejected")])
        self.assert_issue(report, "PRIVACY_NOT_APPROVED")

    def test_empty_manifest_fails(self) -> None:
        self.write_manifest([])
        report = validator.validate_manifest(
            self.manifest, self.data_root, self.schema_path
        )
        self.assert_issue(report, "EMPTY_MANIFEST")

    def test_cli_exit_codes_distinguish_data_and_usage_errors(self) -> None:
        self.write_manifest([self.valid_record(damage_type="D01")])
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            invalid_exit = validator.main(
                [
                    "--manifest",
                    str(self.manifest),
                    "--data-root",
                    str(self.data_root),
                    "--schema",
                    str(self.schema_path),
                ]
            )
            usage_exit = validator.main(
                [
                    "--manifest",
                    str(self.root / "missing.csv"),
                    "--data-root",
                    str(self.data_root),
                    "--schema",
                    str(self.schema_path),
                ]
            )
        self.assertEqual(invalid_exit, validator.EXIT_DATA_INVALID)
        self.assertEqual(usage_exit, validator.EXIT_USAGE_ERROR)


if __name__ == "__main__":
    unittest.main()
