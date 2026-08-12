"""Measure RC v1.1 cold once and warm ten times through real Uvicorn."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
from datetime import datetime
from pathlib import Path

import httpx

import scripts.demo.measure_competition_rc_performance as v10

RUNTIME = Path("E:/JianZhengData/runtime/competition-rc-v1.1")
OUTPUT = RUNTIME / "performance-v1.1.json"
PORT = 8048


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(values)
    rank = max(1, int(len(ordered) * percentile + 0.999999999))
    return ordered[min(rank, len(ordered)) - 1]


def main() -> int:
    v10.RUNTIME = RUNTIME
    v10.DEMO = RUNTIME / "demo/DEMO-D"
    env = os.environ.copy()
    env["JIANZHENG_DISABLE_AUTO_WARMUP"] = "1"
    env["JIANZHENG_RUNTIME_CONFIG"] = str(
        v10.REPO / "configs/runtime/competition-rc-v1.1.json"
    )
    log = RUNTIME / "logs/performance-v1.1-uvicorn.log"
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            [
                str(v10.PYTHON),
                "-m",
                "uvicorn",
                "app.backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(PORT),
            ],
            cwd=v10.REPO,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{PORT}", timeout=240.0
            ) as client:
                v10.ready(client, process)
                cold = v10.analyze(client, "RC-V11-PERF-COLD-DEMO-D")
                warmup = client.post("/api/model/warmup", timeout=120.0)
                warmup.raise_for_status()
                warm = [
                    v10.analyze(client, f"RC-V11-PERF-WARM-{index}-DEMO-D")
                    for index in range(1, 11)
                ]
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    durations = [item["client_total_request_ms"] for item in warm]
    median = statistics.median(durations)
    p90 = percentile_nearest_rank(durations, 0.9)
    payload = {
        "report_version": "competition-performance-v1.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "measurement": "real Uvicorn HTTP on R9000P",
        "active_detector": "d02-d03-yolo26n-imgsz960-v0.1",
        "cold": cold,
        "explicit_warmup": warmup.json(),
        "warm_runs": warm,
        "warm_summary_ms": {
            "median": median,
            "p90_nearest_rank": p90,
            "min": min(durations),
            "max": max(durations),
        },
        "assertions": {
            "ten_warm_runs": len(warm) == 10,
            "warm_median_lte_1500_ms": median <= 1500.0,
            "warm_p90_lte_2000_ms": p90 <= 2000.0,
            "detector_and_whole_pipeline_reported": all(
                "detector" in item["core_detail_ms"]
                and "total_request" in item["processing_breakdown_ms"]
                for item in [cold, *warm]
            ),
        },
    }
    payload["passed"] = all(payload["assertions"].values())
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
