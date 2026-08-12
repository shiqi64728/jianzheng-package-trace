"""One complete real-Uvicorn HTTP E2E including MP4 and both logistics formats."""

from __future__ import annotations

import csv
import io
import json
import os
import subprocess
from datetime import datetime

import httpx

from verify_competition_release import PYTHON, REPO, RUNTIME, run_http_demo, wait_ready

OUTPUT = RUNTIME / "competition-e2e-v1.0.json"
VIDEO = RUNTIME / "demo/SYNTHETIC-VIDEO-DEMO/damage-keyframe-screening.mp4"
PORT = 8026


def main() -> int:
    log = RUNTIME / "logs/competition-e2e-v1.0-uvicorn.log"
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
                base_url=f"http://127.0.0.1:{PORT}", timeout=120.0
            ) as client:
                health = wait_ready(client, process)
                model = client.get("/api/model/info")
                model.raise_for_status()
                warmup = client.post("/api/model/warmup")
                warmup.raise_for_status()
                demo = run_http_demo(client, 100)

                case = client.post(
                    "/api/cases",
                    json={"case_name": "CSV-LOGISTICS-E2E", "notes": "anonymous"},
                )
                case.raise_for_status()
                csv_case_id = case.json()["case_id"]
                rows = [
                    {
                        "package_alias": "PKG-CSV-E2E",
                        "node_id": f"N{i}",
                        "node_type": kind,
                        "event_time": f"2026-08-12T0{i}:00:00+08:00",
                        "location_alias": f"CSV-LOC-{i}",
                        "device_alias": "DEVICE-DEMO",
                        "status": "CAPTURED",
                        "notes": "",
                    }
                    for i, kind in enumerate(("PICKUP", "SORTING", "DELIVERY"), start=1)
                ]
                csv_stream = io.StringIO(newline="")
                writer = csv.DictWriter(csv_stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
                csv_import = client.post(
                    f"/api/cases/{csv_case_id}/logistics/import",
                    data={"data_format": "csv"},
                    files={
                        "file": (
                            "nodes.csv",
                            csv_stream.getvalue().encode(),
                            "text/csv",
                        )
                    },
                )
                csv_import.raise_for_status()

                with VIDEO.open("rb") as video_stream:
                    video = client.post(
                        "/api/video/analyze",
                        data={"sample_interval_frames": "5", "top_k": "5"},
                        files={"file": (VIDEO.name, video_stream, "video/mp4")},
                        timeout=240.0,
                    )
                video.raise_for_status()
                video_payload = video.json()
                keyframe_status = None
                if video_payload["top_abnormal_keyframes"]:
                    keyframe = client.get(
                        video_payload["top_abnormal_keyframes"][0]["url"]
                    )
                    keyframe.raise_for_status()
                    keyframe_status = keyframe.status_code
                dashboard = client.get("/api/dashboard/trends")
                dashboard.raise_for_status()
                frontend = client.get("/")
                frontend.raise_for_status()
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    assertions = {
        "health": health["status"] == "ok"
        and health["pipeline_version"] == "competition-rc-v1.0",
        "model": model.json()["model_version"] == "d02-d03-yolo26n-imgsz960-v0.1",
        "warmup": bool(warmup.json()["loaded"]),
        "demo_d_full": demo["passed"],
        "json_logistics": True,  # run_http_demo imports and checks JSON nodes
        "csv_logistics": len(csv_import.json()["nodes"]) == 3,
        "video_capability": video_payload["capability"]
        == "VIDEO_DAMAGE_KEYFRAME_SCREENING",
        "video_abnormal_keyframe": video_payload["abnormal_frame_count"] >= 1
        and keyframe_status == 200,
        "dashboard": dashboard.json()["source"] == "SQLite",
        "frontend": frontend.status_code == 200,
        "server_stopped": process.poll() is not None,
    }
    payload = {
        "report_version": "competition-e2e-v1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "transport": "real Uvicorn HTTP",
        "health": health,
        "demo": demo,
        "csv_case_id": csv_case_id,
        "video": video_payload,
        "assertions": assertions,
        "passed": all(assertions.values()),
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "passed": payload["passed"],
                "video_abnormal_frames": video_payload["abnormal_frame_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
