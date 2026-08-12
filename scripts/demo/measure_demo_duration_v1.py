"""Time one complete on-stage main demo through a real HTTP server."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime

import httpx

from verify_competition_release import PYTHON, REPO, RUNTIME, run_http_demo, wait_ready

OUTPUT = RUNTIME / "demo-duration-v1.0.json"
PORT = 8025


def main() -> int:
    log = RUNTIME / "logs/demo-duration-v1.0-uvicorn.log"
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
            env=os.environ.copy(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{PORT}", timeout=90.0
            ) as client:
                wait_ready(client, process)
                client.post("/api/model/warmup", timeout=120.0).raise_for_status()
                started = time.perf_counter()
                opening_dashboard = client.get("/api/dashboard/summary")
                opening_dashboard.raise_for_status()
                demo = run_http_demo(client, 99)
                closing_dashboard = client.get("/api/dashboard/summary")
                closing_dashboard.raise_for_status()
                elapsed = time.perf_counter() - started
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    payload = {
        "report_version": "demo-duration-v1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "measurement": "real Uvicorn HTTP, warmed detector, full main demo",
        "steps": [
            "Dashboard",
            "create case",
            "N1/N2/N3 four-surface upload",
            "analyze",
            "first abnormal interval",
            "machine evidence",
            "D05 human review",
            "risk re-score",
            "work order OPEN→IN_REVIEW→RESOLVED",
            "Evidence Report v1.0",
            "Dashboard",
        ],
        "duration_seconds": elapsed,
        "target_seconds": 180,
        "demo": demo,
        "passed": demo["passed"] and elapsed <= 180,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
