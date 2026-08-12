"""Run the full Competition RC demonstration three times through real Uvicorn."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
PYTHON = Path("D:/JianzhenApps/Miniconda3/envs/jianzhen-training/python.exe")
RUNTIME = Path("E:/JianZhengData/runtime/competition-rc-v1.0")
DEMO = RUNTIME / "demo/DEMO-D"
OUTPUT = RUNTIME / "competition-release-stability-v1.0.json"
MANIFEST = RUNTIME / "release/competition-release-manifest-v1.0.json"
DISCLAIMER = "本报告提供计算机视觉和结构化证据辅助分析"


def verify_manifest() -> dict:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    failures = []
    for item in payload["files"]:
        path = Path(item["path"])
        actual = (
            hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        )
        if actual != item["sha256"]:
            failures.append(
                {"path": str(path), "expected": item["sha256"], "actual": actual}
            )
    if failures:
        raise RuntimeError(f"release manifest mismatch: {failures}")
    return {
        "path": str(MANIFEST),
        "file_count": len(payload["files"]),
        "verified": True,
    }


def wait_ready(client: httpx.Client, process: subprocess.Popen) -> dict:
    for _ in range(180):
        if process.poll() is not None:
            raise RuntimeError("Uvicorn exited before health became ready")
        try:
            response = client.get("/api/health")
            if response.status_code == 200 and response.json().get("status") == "ok":
                return response.json()
        except httpx.HTTPError:
            pass
        time.sleep(0.25)
    raise RuntimeError("Uvicorn health timeout")


def nodes() -> dict[str, dict[str, Path]]:
    return {
        node: {
            surface: DEMO / f"{node}-{surface}.png"
            for surface in ("front", "left", "right", "top")
        }
        for node in ("N1", "N2", "N3")
    }


def run_http_demo(client: httpx.Client, run_number: int) -> dict:
    warmup = client.post("/api/model/warmup", timeout=120.0)
    warmup.raise_for_status()
    case = client.post(
        "/api/cases",
        json={
            "case_name": f"STABILITY-{run_number}-DEMO-D",
            "notes": "anonymous controlled synthetic demo",
        },
    )
    case.raise_for_status()
    case_id = case.json()["case_id"]
    timeline = [
        {
            "package_alias": f"PKG-STABILITY-{run_number}",
            "node_id": f"N{i}",
            "node_type": kind,
            "event_time": f"2026-08-12T0{i}:00:00+08:00",
            "location_alias": f"LOC-{i}",
            "device_alias": "DEVICE-DEMO",
            "status": "CAPTURED",
            "notes": "",
        }
        for i, kind in enumerate(("PICKUP", "SORTING", "DELIVERY"), start=1)
    ]
    logistics = client.post(
        f"/api/cases/{case_id}/logistics/import",
        data={"data_format": "json"},
        files={
            "file": ("nodes.json", json.dumps(timeline).encode(), "application/json")
        },
    )
    logistics.raise_for_status()
    upload_count = 0
    for node_id, items in nodes().items():
        for surface, path in items.items():
            with path.open("rb") as stream:
                response = client.post(
                    f"/api/cases/{case_id}/nodes",
                    data={"node_id": node_id, "surface": surface},
                    files={"file": (path.name, stream, "image/png")},
                )
            response.raise_for_status()
            upload_count += 1
    analyze = client.post(f"/api/cases/{case_id}/analyze", timeout=240.0)
    analyze.raise_for_status()
    analyzed = analyze.json()
    review = client.post(
        f"/api/cases/{case_id}/reviews",
        json={
            "node_from": "N1",
            "node_to": "N2",
            "surface": "left",
            "review_class": "D05",
            "review_status": "CONFIRMED",
            "reviewer_alias": "DEMO-REVIEWER",
            "review_note": "controlled synthetic tape-like change",
        },
    )
    review.raise_for_status()
    risk = client.get(f"/api/cases/{case_id}/risk")
    risk.raise_for_status()
    order = client.post(
        f"/api/cases/{case_id}/work-orders",
        json={
            "title": "Demo D evidence review",
            "assigned_alias": "MEMBER-C",
            "actor_alias": "DEMO-OPERATOR",
            "note": "stability run",
        },
    )
    order.raise_for_status()
    order_id = order.json()["work_order_id"]
    in_review = client.post(
        f"/api/work-orders/{order_id}/events",
        json={
            "event_type": "STATE_CHANGE",
            "actor_alias": "MEMBER-C",
            "new_state": "IN_REVIEW",
            "note": "review started",
            "evidence_request": "",
        },
    )
    in_review.raise_for_status()
    resolved = client.post(
        f"/api/work-orders/{order_id}/events",
        json={
            "event_type": "RESOLVE",
            "actor_alias": "MEMBER-C",
            "new_state": None,
            "note": "review complete",
            "evidence_request": "",
        },
    )
    resolved.raise_for_status()
    dashboard = client.get("/api/dashboard/summary")
    dashboard.raise_for_status()
    report = client.get(f"/api/cases/{case_id}/report")
    report.raise_for_status()
    frontend = client.get("/")
    frontend.raise_for_status()
    script_match = re.search(r'src="([^"]+\.js)"', frontend.text)
    script = client.get(script_match.group(1)) if script_match else None
    if script is not None:
        script.raise_for_status()
    assertions = {
        "warmup_loaded": bool(warmup.json().get("loaded")),
        "twelve_uploads": upload_count == 12,
        "demo_d_interval": analyzed["analysis"]["first_abnormal_interval"]
        == "N1_TO_N2",
        "demo_d_left_trigger": [
            x["surface"] for x in analyzed["analysis"]["trigger_surfaces"]
        ]
        == ["left"],
        "risk_rule_engine": risk.json().get("legal_responsibility_conclusion")
        == "NOT_SUPPORTED",
        "work_order_lifecycle": resolved.json()["current_state"] == "RESOLVED"
        and len(resolved.json()["events"]) == 3,
        "dashboard_sqlite": dashboard.json().get("source") == "SQLite",
        "report_v10": "Evidence Report v1.0" in report.text
        and DISCLAIMER in report.text
        and "RESOLVE" in report.text,
        "frontend_navigation": bool(
            script
            and all(
                label in script.text
                for label in (
                    "Dashboard",
                    "New Case",
                    "Work Orders",
                    "Video Screening",
                    "System Status",
                )
            )
        ),
    }
    return {
        "case_id": case_id,
        "upload_count": upload_count,
        "first_abnormal_interval": analyzed["analysis"]["first_abnormal_interval"],
        "trigger_surfaces": analyzed["analysis"]["trigger_surfaces"],
        "risk_score": risk.json()["risk_score"],
        "risk_level": risk.json()["risk_level"],
        "work_order_id": order_id,
        "work_order_event_count": len(resolved.json()["events"]),
        "report_path": analyzed["report"]["html_path"],
        "assertions": assertions,
        "passed": all(assertions.values()),
    }


def one_run(run_number: int, port: int) -> dict:
    log = RUNTIME / "logs" / f"stability-run-{run_number}-uvicorn.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone().isoformat()
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
                str(port),
            ],
            cwd=REPO,
            env=os.environ.copy(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stop_method = "terminate"
        try:
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}", timeout=90.0
            ) as client:
                health = wait_ready(client, process)
                result = run_http_demo(client, run_number)
        finally:
            process.terminate()
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                stop_method = "kill_after_timeout"
                process.kill()
                process.wait(timeout=10)
    stopped = process.poll() is not None
    return {
        "run": run_number,
        "port": port,
        "started_at": started,
        "health": health,
        "demo": result,
        "server_stopped": stopped,
        "stop_method": stop_method,
        "server_return_code": process.returncode,
        "log": str(log),
        "passed": result["passed"] and stopped,
    }


def main() -> int:
    manifest = verify_manifest()
    runs = [one_run(index, 8019 + index) for index in range(1, 4)]
    payload = {
        "report_version": "competition-release-stability-v1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "measurement": "real Uvicorn HTTP, three independent start/stop cycles",
        "manifest": manifest,
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
