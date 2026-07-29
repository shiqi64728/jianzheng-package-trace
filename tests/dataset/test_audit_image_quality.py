from __future__ import annotations

import csv
import hashlib
import json
import shutil
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

from scripts.dataset import audit_image_quality as auditor  # noqa: E402
from scripts.dataset import validate_manifest as validator  # noqa: E402


class ImageQualityAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.data_root = self.root / "batch"
        self.images_root = self.data_root / "images"
        self.reports_root = self.data_root / "reports"
        self.images_root.mkdir(parents=True)
        self.reports_root.mkdir()
        self.manifest = self.data_root / "manifest.csv"
        self.report_json = self.reports_root / "quality-report.json"
        self.report_csv = self.reports_root / "quality-report.csv"
        self.schema_path = (
            REPO_ROOT / "configs" / "training" / "manifest-schema-v0.1.json"
        )
        self.quality_config_path = (
            REPO_ROOT / "configs" / "training" / "image-quality-v0.1.json"
        )
        self.schema = validator.load_schema(self.schema_path)
        self.fields = list(self.schema["fields"])
        self.write_batch_info()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def valid_record(self, index: int = 1, **changes: str) -> dict[str, str]:
        record = {
            "schema_version": "0.1",
            "record_id": f"REC-{index:03d}",
            "package_id": f"PKG-{index:03d}",
            "batch_id": "BATCH-PILOT-001",
            "sequence_id": "",
            "source_type": "field_normal",
            "image_relpath": f"images/image-{index:03d}.png",
            "surface": "FRONT",
            "node_id": "NA",
            "capture_time": "2026-07-01T09:00:00+08:00",
            "device_id": "PHONE-C-001",
            "status": "normal",
            "damage_type": "NONE",
            "severity": "none",
            "first_abnormal_node": "NONE",
            "privacy_status": "masked",
            "annotation_status": "unlabelled",
            "split": "unassigned",
            "collector": "MEMBER-C",
            "reviewer": "",
            "notes": "SYNTHETIC_TEST_ONLY",
        }
        record.update(changes)
        return record

    def write_batch_info(self, **changes: str) -> None:
        payload = {
            "batch_schema_version": "0.1",
            "manifest_schema_version": "0.1",
            "batch_id": "BATCH-PILOT-001",
            "source_type": "field_normal",
            "collector": "MEMBER-C",
            "device_id": "PHONE-C-001",
            "created_at": "2026-07-28T12:00:00+08:00",
            "purpose": "SYNTHETIC_TEST_ONLY",
            "location_type": "self_controlled_non_station",
            "permission_status": "not_required",
            "privacy_method": "manual_not_applicable",
            "camera_or_phone_model": "TEST-PHONE",
            "lens": "rear-main-1x",
            "resolution_setting": "original",
            "aspect_ratio_setting": "4:3",
            "hdr_status": "off",
            "filter_status": "off",
            "lighting": "controlled",
            "background": "plain",
            "notes": "SYNTHETIC_TEST_ONLY",
        }
        payload.update(changes)
        (self.data_root / "batch-info.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def write_manifest(self, rows: list[dict[str, str]]) -> None:
        with self.manifest.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=self.fields)
            writer.writeheader()
            writer.writerows(rows)

    def texture(self, width: int = 800, height: int = 600, seed: int = 0) -> np.ndarray:
        y, x = np.indices((height, width))
        base = ((x // 8 + y // 8 + seed) % 2 * 190 + 30).astype(np.uint8)
        image = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
        cv2.circle(
            image,
            (40 + seed % max(1, width - 80), 40),
            12,
            (0, 80 + seed % 100, 255),
            -1,
        )
        return image

    def write_image(
        self,
        index: int,
        image: np.ndarray,
        *,
        name: str | None = None,
    ) -> Path:
        path = self.images_root / (name or f"image-{index:03d}.png")
        self.assertTrue(cv2.imwrite(str(path), image))
        return path

    def audit(
        self,
        rows: list[dict[str, str]],
        *,
        config_path: Path | None = None,
    ) -> auditor.QualityReport:
        self.write_manifest(rows)
        return auditor.audit_manifest_images(
            manifest_path=self.manifest,
            data_root=self.data_root,
            schema_path=self.schema_path,
            quality_config_path=config_path or self.quality_config_path,
            check_files=True,
        )

    def record_by_id(
        self, report: auditor.QualityReport, record_id: str
    ) -> auditor.QualityRecord:
        for record in report.records:
            if record.record_id == record_id:
                return record
        self.fail(f"未找到记录 {record_id}")

    def custom_config(self, **changes: object) -> Path:
        payload = json.loads(self.quality_config_path.read_text(encoding="utf-8"))
        payload.update(changes)
        path = self.root / f"quality-config-{len(list(self.root.glob('*.json')))}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def test_normal_synthetic_image_passes_with_metrics(self) -> None:
        self.write_image(1, self.texture())
        report = self.audit([self.valid_record()])
        record = report.records[0]
        self.assertEqual(record.quality_status, "PASS")
        self.assertTrue(record.readable)
        self.assertEqual((record.width, record.height, record.channels), (800, 600, 3))
        self.assertIsNotNone(record.sha256)
        self.assertIsNotNone(record.laplacian_variance)
        self.assertEqual(report.batch_status, "PASS")

    def test_missing_image_fails(self) -> None:
        report = self.audit([self.valid_record()])
        record = report.records[0]
        self.assertEqual(record.quality_status, "FAIL")
        self.assertIn("UNREADABLE_IMAGE", record.quality_flags or [])
        self.assertEqual(report.batch_status, "FAIL")

    def test_undecodable_file_fails_without_crashing(self) -> None:
        bad = self.images_root / "image-001.png"
        bad.write_text("not-an-image", encoding="utf-8")
        report = self.audit([self.valid_record()])
        self.assertIn("UNREADABLE_IMAGE", report.records[0].quality_flags or [])
        self.assertEqual(report.unreadable_count, 1)

    def test_zero_byte_file_fails(self) -> None:
        (self.images_root / "image-001.png").write_bytes(b"")
        report = self.audit([self.valid_record()])
        self.assertIn("UNREADABLE_IMAGE", report.records[0].quality_flags or [])
        self.assertEqual(report.records[0].file_size_bytes, 0)

    def test_low_resolution_image_fails(self) -> None:
        self.write_image(1, self.texture(width=320, height=240))
        report = self.audit([self.valid_record()])
        record = report.records[0]
        self.assertIn("LOW_RESOLUTION", record.quality_flags or [])
        self.assertEqual(record.quality_status, "FAIL")

    def test_extreme_aspect_ratio_is_flagged(self) -> None:
        self.write_image(1, self.texture(width=1800, height=600))
        report = self.audit([self.valid_record()])
        record = report.records[0]
        self.assertIn("EXTREME_ASPECT_RATIO", record.quality_flags or [])
        self.assertEqual(record.quality_status, "WARN")

    def test_black_image_triggers_underexposure_warning(self) -> None:
        self.write_image(1, np.zeros((600, 800, 3), dtype=np.uint8))
        report = self.audit([self.valid_record()])
        self.assertIn("POSSIBLE_UNDEREXPOSURE", report.records[0].quality_flags or [])

    def test_white_image_triggers_overexposure_warning(self) -> None:
        self.write_image(1, np.full((600, 800, 3), 255, dtype=np.uint8))
        report = self.audit([self.valid_record()])
        self.assertIn("POSSIBLE_OVEREXPOSURE", report.records[0].quality_flags or [])

    def test_gaussian_blur_triggers_blur_flag(self) -> None:
        blurred = cv2.GaussianBlur(self.texture(), (41, 41), 0)
        self.write_image(1, blurred)
        report = self.audit([self.valid_record()])
        flags = report.records[0].quality_flags or []
        self.assertTrue({"POSSIBLE_BLUR", "SEVERE_BLUR"} & set(flags))

    def test_clear_texture_is_not_severe_blur(self) -> None:
        self.write_image(1, self.texture())
        report = self.audit([self.valid_record()])
        self.assertNotIn("SEVERE_BLUR", report.records[0].quality_flags or [])

    def test_duplicate_content_different_names_is_grouped(self) -> None:
        first = self.write_image(1, self.texture())
        second = self.images_root / "image-002.png"
        shutil.copyfile(first, second)
        rows = [self.valid_record(1), self.valid_record(2)]
        report = self.audit(rows)
        self.assertEqual(report.duplicate_group_count, 1)
        group = report.duplicate_groups[0]
        self.assertEqual(group.record_ids, ["REC-001", "REC-002"])
        self.assertEqual(
            group.sha256,
            hashlib.sha256(first.read_bytes()).hexdigest(),
        )
        for record in report.records:
            self.assertIn("DUPLICATE_CONTENT", record.quality_flags or [])

    def test_multiple_quality_flags_coexist(self) -> None:
        self.write_image(1, np.zeros((100, 100, 3), dtype=np.uint8))
        report = self.audit([self.valid_record()])
        flags = report.records[0].quality_flags or []
        self.assertIn("LOW_RESOLUTION", flags)
        self.assertIn("SEVERE_BLUR", flags)
        self.assertIn("POSSIBLE_UNDEREXPOSURE", flags)

    def test_json_report_is_generated_without_base64(self) -> None:
        self.write_image(1, self.texture())
        report = self.audit([self.valid_record()])
        auditor.write_json_report(report, self.report_json)
        payload_text = self.report_json.read_text(encoding="utf-8")
        payload = json.loads(payload_text)
        self.assertEqual(payload["record_count"], 1)
        self.assertEqual(payload["tool_version"], "0.1.0")
        self.assertNotIn("base64", payload_text.casefold())
        self.assertNotIn(str(self.data_root), payload_text)

    def test_csv_report_has_utf8_bom_and_relative_paths_only(self) -> None:
        self.write_image(1, self.texture())
        report = self.audit([self.valid_record()])
        auditor.write_csv_report(report, self.report_csv)
        self.assertTrue(self.report_csv.read_bytes().startswith(b"\xef\xbb\xbf"))
        text = self.report_csv.read_text(encoding="utf-8-sig")
        self.assertIn("images/image-001.png", text)
        self.assertNotIn(str(self.data_root), text)

    def test_cli_returns_one_when_any_record_fails(self) -> None:
        self.write_manifest([self.valid_record()])
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = auditor.main(
                [
                    "--manifest",
                    str(self.manifest),
                    "--data-root",
                    str(self.data_root),
                    "--schema",
                    str(self.schema_path),
                    "--quality-config",
                    str(self.quality_config_path),
                    "--report-json",
                    str(self.report_json),
                    "--report-csv",
                    str(self.report_csv),
                    "--check-files",
                ]
            )
        self.assertEqual(exit_code, auditor.EXIT_DATA_INVALID)

    def test_warn_only_batch_returns_zero(self) -> None:
        self.write_image(1, self.texture())
        config = self.custom_config(
            blur_warn_below=1_000_000_000.0,
            blur_fail_below=0.0,
        )
        self.write_manifest([self.valid_record()])
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = auditor.main(
                [
                    "--manifest",
                    str(self.manifest),
                    "--data-root",
                    str(self.data_root),
                    "--schema",
                    str(self.schema_path),
                    "--quality-config",
                    str(config),
                    "--report-json",
                    str(self.report_json),
                    "--report-csv",
                    str(self.report_csv),
                    "--check-files",
                ]
            )
        self.assertEqual(exit_code, auditor.EXIT_VALID)
        payload = json.loads(self.report_json.read_text(encoding="utf-8"))
        self.assertEqual(payload["batch_status"], "PASS_WITH_WARNINGS")

    def test_same_path_duplicate_remains_first_round_error(self) -> None:
        self.write_image(1, self.texture())
        rows = [
            self.valid_record(1),
            self.valid_record(
                2,
                image_relpath="images/image-001.png",
            ),
        ]
        report = self.audit(rows)
        codes = {issue.code for issue in report.manifest_issues}
        self.assertIn("DUPLICATE_IMAGE_RELPATH", codes)
        self.assertEqual(report.batch_status, "FAIL")
        self.assertEqual(report.records, [])

    def test_first_round_legal_example_still_passes(self) -> None:
        example = (
            REPO_ROOT
            / "dataset"
            / "manifests"
            / "templates"
            / "manifest-v0.1.example.csv"
        )
        report = validator.validate_manifest(example, REPO_ROOT, self.schema_path)
        self.assertEqual(report.error_count, 0)
        self.assertEqual(report.passed_records, 6)

    def test_first_round_cli_exit_codes_remain_compatible(self) -> None:
        self.write_image(1, self.texture())
        self.write_manifest([self.valid_record()])
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            valid_exit = validator.main(
                [
                    "--manifest",
                    str(self.manifest),
                    "--data-root",
                    str(self.data_root),
                    "--schema",
                    str(self.schema_path),
                    "--check-files",
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
        self.assertEqual(valid_exit, validator.EXIT_VALID)
        self.assertEqual(usage_exit, validator.EXIT_USAGE_ERROR)

    def test_audit_does_not_modify_original_image(self) -> None:
        image_path = self.write_image(1, self.texture())
        before_bytes = image_path.read_bytes()
        before_stat = image_path.stat()
        self.audit([self.valid_record()])
        after_stat = image_path.stat()
        self.assertEqual(image_path.read_bytes(), before_bytes)
        self.assertEqual(after_stat.st_mtime_ns, before_stat.st_mtime_ns)

    def test_resolution_outlier_is_warned_for_minority_size(self) -> None:
        rows: list[dict[str, str]] = []
        for index in range(1, 5):
            size = (900, 700) if index == 4 else (800, 600)
            self.write_image(
                index,
                self.texture(width=size[0], height=size[1], seed=index),
            )
            rows.append(self.valid_record(index))
        report = self.audit(rows)
        outlier = self.record_by_id(report, "REC-004")
        self.assertIn("RESOLUTION_OUTLIER", outlier.quality_flags or [])
        self.assertEqual(report.resolution_groups[0]["count"], 3)

    def test_invalid_quality_config_is_usage_error(self) -> None:
        config = self.custom_config(min_width=0)
        with self.assertRaises(auditor.AuditUsageError):
            auditor.load_quality_config(config)
        self.write_image(1, self.texture())
        self.write_manifest([self.valid_record()])
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = auditor.main(
                [
                    "--manifest",
                    str(self.manifest),
                    "--data-root",
                    str(self.data_root),
                    "--schema",
                    str(self.schema_path),
                    "--quality-config",
                    str(config),
                    "--report-json",
                    str(self.report_json),
                    "--report-csv",
                    str(self.report_csv),
                    "--check-files",
                ]
            )
        self.assertEqual(exit_code, auditor.EXIT_USAGE_ERROR)

    def test_check_files_must_be_explicit(self) -> None:
        self.write_image(1, self.texture())
        self.write_manifest([self.valid_record()])
        with self.assertRaises(auditor.AuditUsageError):
            auditor.audit_manifest_images(
                manifest_path=self.manifest,
                data_root=self.data_root,
                schema_path=self.schema_path,
                quality_config_path=self.quality_config_path,
                check_files=False,
            )

    def test_report_paths_cannot_overwrite_manifest_or_image(self) -> None:
        image = self.write_image(1, self.texture())
        with self.assertRaises(auditor.AuditUsageError):
            auditor._validate_report_paths(
                report_json=self.manifest,
                report_csv=self.report_csv,
                protected_paths=[self.manifest, image],
            )
        with self.assertRaises(auditor.AuditUsageError):
            auditor._validate_report_paths(
                report_json=self.report_json,
                report_csv=image,
                protected_paths=[self.manifest, image],
            )

    def test_incomplete_batch_capture_metadata_produces_warning(self) -> None:
        self.write_batch_info(camera_or_phone_model="", hdr_status="unknown")
        self.write_image(1, self.texture())
        report = self.audit([self.valid_record()])
        codes = {issue.code for issue in report.batch_info_issues}
        self.assertIn("BATCH_CAPTURE_METADATA_INCOMPLETE", codes)
        self.assertEqual(report.batch_info_status, "WARN")
        self.assertEqual(report.batch_status, "PASS_WITH_WARNINGS")

    def test_manifest_and_batch_info_mismatch_fails_batch(self) -> None:
        self.write_batch_info(device_id="PHONE-OTHER")
        self.write_image(1, self.texture())
        report = self.audit([self.valid_record()])
        codes = {issue.code for issue in report.batch_info_issues}
        self.assertIn("BATCH_MANIFEST_METADATA_MISMATCH", codes)
        self.assertEqual(report.batch_info_status, "FAIL")
        self.assertEqual(report.batch_status, "FAIL")


if __name__ == "__main__":
    unittest.main()
