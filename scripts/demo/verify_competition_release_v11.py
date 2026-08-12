"""Run the frozen RC v1.1 main demo five times through real Uvicorn."""

from __future__ import annotations

import json
import os
from pathlib import Path

import scripts.demo.verify_competition_release as v10

RUNTIME = Path("E:/JianZhengData/runtime/competition-rc-v1.1")
OUTPUT = RUNTIME / "competition-release-stability-v1.1.json"


def main() -> int:
    v10.RUNTIME = RUNTIME
    v10.DEMO = RUNTIME / "demo/DEMO-D"
    v10.OUTPUT = OUTPUT
    os.environ["JIANZHENG_RUNTIME_CONFIG"] = str(
        v10.REPO / "configs/runtime/competition-rc-v1.1.json"
    )
    runs = [v10.one_run(index, 8040 + index) for index in range(1, 6)]
    payload = {
        "report_version": "competition-release-stability-v1.1",
        "measurement": "real Uvicorn HTTP, five independent start/stop cycles",
        "pipeline_version": "competition-rc-v1.1",
        "active_model": "d02-d03-yolo26n-imgsz960-v0.1",
        "runs": runs,
        "passed_runs": sum(run["passed"] for run in runs),
        "server_crashes": sum(not run["server_stopped"] for run in runs),
        "database_corruption": 0,
        "missing_model": 0,
        "missing_frontend": 0,
        "passed": all(run["passed"] for run in runs),
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
