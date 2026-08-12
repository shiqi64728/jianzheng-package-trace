"""Measure RC cold and five warm Demo-D requests through real Uvicorn."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
PYTHON = Path("D:/JianzhenApps/Miniconda3/envs/jianzhen-training/python.exe")
RUNTIME = Path("E:/JianZhengData/runtime/competition-rc-v1.0")
DEMO = RUNTIME / "demo/DEMO-D"
OUTPUT = RUNTIME / "performance-v1.0.json"
PORT = 8024
V02_WARM_MEDIAN_MS = 1023.0


def ready(client: httpx.Client, process: subprocess.Popen) -> None:
    for _ in range(180):
        if process.poll() is not None:
            raise RuntimeError("performance server exited")
        try:
            if client.get("/api/health").json().get("status") == "ok":
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise RuntimeError("health timeout")


def analyze(client: httpx.Client, label: str) -> dict:
    response = client.post(
        "/api/cases", json={"case_name": label, "notes": "performance measurement"}
    )
    response.raise_for_status()
    case_id = response.json()["case_id"]
    for node in ("N1", "N2", "N3"):
        for surface in ("front", "left", "right", "top"):
            path = DEMO / f"{node}-{surface}.png"
            with path.open("rb") as stream:
                upload = client.post(
                    f"/api/cases/{case_id}/nodes",
                    data={"node_id": node, "surface": surface},
                    files={"file": (path.name, stream, "image/png")},
                )
            upload.raise_for_status()
    started = time.perf_counter()
    response = client.post(f"/api/cases/{case_id}/analyze", timeout=240.0)
    client_ms = (time.perf_counter() - started) * 1000.0
    response.raise_for_status()
    result = response.json()
    return {
        "case_id": case_id,
        "client_total_request_ms": client_ms,
        "processing_breakdown_ms": result["processing_breakdown_ms"],
        "core_detail_ms": result["analysis"]["timing_ms"],
        "first_abnormal_interval": result["analysis"]["first_abnormal_interval"],
    }


def main() -> int:
    env = os.environ.copy()
    env["JIANZHENG_DISABLE_AUTO_WARMUP"] = "1"
    log = RUNTIME / "logs/performance-v1.0-uvicorn.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            [
                str(PYTHON),
                "-m",
                "uvicorn",
                "app.backend.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(PORT),
            ],
            cwd=REPO,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{PORT}", timeout=90.0
            ) as client:
                ready(client, process)
                cold = analyze(client, "RC-PERF-COLD-DEMO-D")
                warmup = client.post("/api/model/warmup", timeout=120.0)
                warmup.raise_for_status()
                warm = [
                    analyze(client, f"RC-PERF-WARM-{index}-DEMO-D")
                    for index in range(1, 6)
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
    payload = {
        "report_version": "competition-performance-v1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "measurement": "real Uvicorn HTTP on R9000P",
        "auto_warmup_disabled_for_cold": True,
        "cold": cold,
        "explicit_warmup": warmup.json(),
        "warm_runs": warm,
        "warm_summary_ms": {
            "median": median,
            "min": min(durations),
            "max": max(durations),
        },
        "v02_reference_warm_median_ms": V02_WARM_MEDIAN_MS,
        "maximum_50_percent_regression_ms": V02_WARM_MEDIAN_MS * 1.5,
        "assertions": {
            "five_warm_runs": len(warm) == 5,
            "warm_median_lte_1500_ms": median <= 1500.0,
            "regression_lte_50_percent": median <= V02_WARM_MEDIAN_MS * 1.5,
            "separate_core_database_risk_report_total": all(
                set(item["processing_breakdown_ms"])
                == {
                    "core_analysis",
                    "database",
                    "risk_engine",
                    "report",
                    "total_request",
                }
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
