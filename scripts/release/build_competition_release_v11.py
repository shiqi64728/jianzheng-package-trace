"""Build and verify the Competition RC v1.1 release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RUNTIME = Path("E:/JianZhengData/runtime/competition-rc-v1.1")
OUTPUT = RUNTIME / "release/competition-release-manifest-v1.1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def release_source_files(repo: Path = REPO) -> list[Path]:
    fixed = [
        repo / "configs/runtime/competition-rc-v1.1.json",
        repo / "configs/runtime/change-detection-v0.2.json",
        repo / "frontend/package.json",
        repo / "frontend/package-lock.json",
        repo / "frontend/vite.config.js",
    ]
    folders = [
        (repo / "ai/runtime", {".py"}),
        (repo / "app/backend", {".py"}),
        (repo / "scripts/demo", {".py", ".ps1"}),
        (repo / "scripts/calibration", {".py"}),
        (repo / "scripts/release", {".py"}),
        (repo / "frontend/src", {".vue", ".js", ".css"}),
    ]
    files = [path for path in fixed if path.is_file()]
    for folder, suffixes in folders:
        files.extend(
            path
            for path in folder.rglob("*")
            if path.is_file() and path.suffix.lower() in suffixes
        )
    dist = repo / "frontend/dist"
    if dist.is_dir():
        files.extend(path for path in dist.rglob("*") if path.is_file())
    return sorted(set(files), key=lambda path: str(path).casefold())


def build_manifest(
    *,
    git_commit: str,
    test_count: int,
    validation_executed: int,
    validation_real_pending: int,
) -> dict[str, Any]:
    registry_path = Path("E:/JianZhengData/models/active/detector-v0.1.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    config_path = REPO / "configs/runtime/competition-rc-v1.1.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    frontend = json.loads((REPO / "frontend/package.json").read_text(encoding="utf-8"))
    files = [
        {
            "path": str(path),
            "repository_relative_path": path.relative_to(REPO).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in release_source_files()
    ]
    return {
        "release_version": "competition-rc-v1.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "pipeline_version": config["pipeline_version"],
        "git_commit": git_commit,
        "active_model": registry["model_version"],
        "active_model_sha256": registry["sha256"],
        "active_model_path": registry["source_pt"],
        "runtime": registry["runtime_preferred"],
        "config_versions": {
            "runtime": "competition-rc-v1.1",
            "change_detection": Path(config["change_config"]).stem,
            "active_registry": registry["registry_version"],
        },
        "database_schema": 3,
        "frontend_version": frontend["version"],
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "node": subprocess.check_output(["node", "--version"], text=True).strip(),
        "npm": subprocess.check_output(["npm.cmd", "--version"], text=True).strip(),
        "test_count": test_count,
        "validation_scenarios": {
            "executed": validation_executed,
            "real_pending": validation_real_pending,
        },
        "real_world_calibration_status": config["real_world_calibration_status"],
        "offline_core_runtime": True,
        "release_files": files,
    }


def verify_manifest(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures = []
    for item in payload["release_files"]:
        path = Path(item["path"])
        actual = sha256(path) if path.is_file() else None
        if (
            actual != item["sha256"]
            or (path.stat().st_size if path.is_file() else None) != item["bytes"]
        ):
            failures.append({"path": str(path), "actual_sha256": actual})
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-commit", required=True)
    parser.add_argument("--test-count", type=int, required=True)
    parser.add_argument("--validation-executed", type=int, default=17)
    parser.add_argument("--validation-real-pending", type=int, default=5)
    args = parser.parse_args()
    payload = build_manifest(
        git_commit=args.git_commit,
        test_count=args.test_count,
        validation_executed=args.validation_executed,
        validation_real_pending=args.validation_real_pending,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    failures = verify_manifest(payload)
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "file_count": len(payload["release_files"]),
                "verification_failures": failures,
                "passed": not failures,
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
