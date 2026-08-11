"""Measure one cold and three warm Demo-D analyses through a real Uvicorn API."""

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
DEMO = Path("E:/JianZhengData/runtime/mvp-v0.2/demo/DEMO-D/metadata.json")
OUTPUT = Path("E:/JianZhengData/runtime/mvp-v0.2/logs/performance-v0.2.json")
PORT = 8011


def wait_ready(client: httpx.Client, process: subprocess.Popen) -> None:
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError("performance Uvicorn exited before health became ready")
        try:
            if client.get("/api/health").json().get("status") == "ok":
                return
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError("performance Uvicorn health timeout")


def analyze_demo(client: httpx.Client, label: str, metadata: dict) -> dict:
    case = client.post(
        "/api/cases", json={"case_name": label, "notes": "performance observation"}
    )
    case.raise_for_status()
    case_id = case.json()["case_id"]
    for node_id, surfaces in metadata["nodes"].items():
        for surface, raw_path in surfaces.items():
            path = Path(raw_path)
            with path.open("rb") as stream:
                response = client.post(
                    f"/api/cases/{case_id}/nodes",
                    data={"node_id": node_id, "surface": surface},
                    files={"file": (path.name, stream, "image/png")},
                )
            response.raise_for_status()
    started = time.perf_counter()
    response = client.post(f"/api/cases/{case_id}/analyze")
    elapsed = (time.perf_counter() - started) * 1000.0
    response.raise_for_status()
    payload = response.json()
    return {
        "case_id": case_id,
        "client_analyze_ms": elapsed,
        "internal_timing_ms": payload["analysis"]["timing_ms"],
        "first_abnormal_interval": payload["analysis"]["first_abnormal_interval"],
        "trigger_surfaces": payload["analysis"]["trigger_surfaces"],
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(
            f"performance report exists; refusing to overwrite: {OUTPUT}"
        )
    metadata = json.loads(DEMO.read_text(encoding="utf-8"))
    env = os.environ.copy()
    env["JIANZHENG_DISABLE_AUTO_WARMUP"] = "1"
    log = OUTPUT.parent / "performance-uvicorn.log"
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
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
                base_url=f"http://127.0.0.1:{PORT}", timeout=240.0
            ) as client:
                wait_ready(client, process)
                cold = analyze_demo(client, "PERF-COLD-DEMO-D", metadata)
                warmup = client.post("/api/model/warmup")
                warmup.raise_for_status()
                warm = [
                    analyze_demo(client, f"PERF-WARM-{index}-DEMO-D", metadata)
                    for index in range(1, 4)
                ]
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    durations = [item["client_analyze_ms"] for item in warm]
    payload = {
        "report_version": "mvp-performance-v0.2",
        "generated_at": datetime.now().astimezone().isoformat(),
        "measurement": "real Uvicorn HTTP API on R9000P",
        "auto_warmup_disabled_for_cold_measurement": True,
        "cold": cold,
        "explicit_warmup": warmup.json(),
        "warm_runs": warm,
        "warm_summary_ms": {
            "median": statistics.median(durations),
            "min": min(durations),
            "max": max(durations),
        },
        "warm_median_lower_than_cold": statistics.median(durations)
        < cold["client_analyze_ms"],
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
