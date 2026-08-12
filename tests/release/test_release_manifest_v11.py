from __future__ import annotations

import unittest

from scripts.release.build_competition_release_v11 import (
    build_manifest,
    release_source_files,
    verify_manifest,
)


class ReleaseManifestV11Tests(unittest.TestCase):
    def test_source_files_include_v11_config(self):
        names = {path.name for path in release_source_files()}
        self.assertIn("competition-rc-v1.1.json", names)

    def test_source_files_exclude_weights(self):
        self.assertFalse(any(path.suffix == ".pt" for path in release_source_files()))

    def test_manifest_truth_fields(self):
        payload = build_manifest(
            git_commit="TEST-COMMIT",
            test_count=366,
            validation_executed=17,
            validation_real_pending=5,
        )
        self.assertEqual(payload["pipeline_version"], "competition-rc-v1.1")
        self.assertEqual(
            payload["real_world_calibration_status"], "PENDING_EXTERNAL_DATA"
        )
        self.assertEqual(payload["test_count"], 366)

    def test_manifest_verifies(self):
        payload = build_manifest(
            git_commit="TEST-COMMIT",
            test_count=366,
            validation_executed=17,
            validation_real_pending=5,
        )
        self.assertEqual(verify_manifest(payload), [])

    def test_tampered_hash_fails(self):
        payload = build_manifest(
            git_commit="TEST-COMMIT",
            test_count=366,
            validation_executed=17,
            validation_real_pending=5,
        )
        payload["release_files"][0]["sha256"] = "0" * 64
        self.assertTrue(verify_manifest(payload))

    def test_no_runtime_artifacts_are_listed(self):
        payload = build_manifest(
            git_commit="TEST-COMMIT",
            test_count=366,
            validation_executed=17,
            validation_real_pending=5,
        )
        self.assertFalse(
            any(
                "JianZhengData/runtime" in item["path"].replace("\\", "/")
                for item in payload["release_files"]
            )
        )


if __name__ == "__main__":
    unittest.main()
