"""Validate v0.2 through HTTP, SQLite, report and the built frontend."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
RUNTIME = Path("E:/JianZhengData/runtime/mvp-v0.2")
OUTPUT = RUNTIME / "logs/mvp-e2e-report-v0.2-final.json"
OLD_DEMOS = {
    "DEMO-A": Path(
        "E:/JianZhengData/runtime/mvp-v0.1/demo/demo-a-synthetic/metadata.json"
    ),
    "DEMO-B": Path(
        "E:/JianZhengData/runtime/mvp-v0.1/demo/demo-b-tampar/metadata.json"
    ),
}
DEMO_C = RUNTIME / "demo/DEMO-C/metadata.json"
DEMO_D = RUNTIME / "demo/DEMO-D/metadata.json"


def normalized_nodes(metadata: dict) -> dict[str, dict[str, str]]:
    result = {}
    for node_id, value in metadata["nodes"].items():
        result[node_id] = value if isinstance(value, dict) else {"front": value}
    return result


def run_case(client: httpx.Client, demo_id: str, metadata: dict) -> dict:
    response = client.post(
        "/api/cases",
        json={"case_name": f"{demo_id}-E2E", "notes": "anonymous competition demo"},
    )
    response.raise_for_status()
    case_id = response.json()["case_id"]
    upload_count = 0
    for node_id, surfaces in normalized_nodes(metadata).items():
        for surface, raw_path in surfaces.items():
            path = Path(raw_path)
            mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            with path.open("rb") as stream:
                upload = client.post(
                    f"/api/cases/{case_id}/nodes",
                    data={"node_id": node_id, "surface": surface},
                    files={"file": (path.name, stream, mime)},
                )
            upload.raise_for_status()
            upload_count += 1
    analysis_response = client.post(f"/api/cases/{case_id}/analyze")
    analysis_response.raise_for_status()
    result = analysis_response.json()
    report_response = client.get(f"/api/cases/{case_id}/report")
    report_response.raise_for_status()
    return {
        "case_id": case_id,
        "upload_count": upload_count,
        "first_abnormal_interval": result["analysis"]["first_abnormal_interval"],
        "conclusion_code": result["analysis"]["conclusion_code"],
        "evidence_level": result["analysis"]["evidence_level"],
        "trigger_surfaces": result["analysis"]["trigger_surfaces"],
        "pair_count": len(result["pair_changes"]),
        "report_status": report_response.status_code,
        "report_path": result["report"]["html_path"],
    }


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(f"E2E report exists; refusing to overwrite: {OUTPUT}")
    checks = {}
    with httpx.Client(base_url=BASE_URL, timeout=240.0) as client:
        health = client.get("/api/health")
        health.raise_for_status()
        model = client.get("/api/model/info")
        model.raise_for_status()
        warmup = client.post("/api/model/warmup")
        warmup.raise_for_status()
        frontend = client.get("/")
        frontend.raise_for_status()
        javascript_match = re.search(r'src="([^"]+\.js)"', frontend.text)
        frontend_javascript = (
            client.get(javascript_match.group(1)) if javascript_match else None
        )
        if frontend_javascript is not None:
            frontend_javascript.raise_for_status()
        demos = {}
        for demo_id, path in OLD_DEMOS.items():
            demos[demo_id] = run_case(
                client, demo_id, json.loads(path.read_text(encoding="utf-8"))
            )
        demo_c_meta = json.loads(DEMO_C.read_text(encoding="utf-8"))
        image_path = Path(demo_c_meta["copied_image"])
        with image_path.open("rb") as stream:
            detection = client.post(
                "/api/detect",
                files={"file": (image_path.name, stream, "image/jpeg")},
            )
        detection.raise_for_status()
        demos["DEMO-C"] = {
            "detection_count": len(detection.json()["detections"]),
            "labels": demo_c_meta["labels"],
            "source_split": demo_c_meta["source_split"],
            "prediction_boxes_edited": demo_c_meta["prediction_boxes_edited"],
        }
        demo_d_meta = json.loads(DEMO_D.read_text(encoding="utf-8"))
        demos["DEMO-D"] = run_case(client, "DEMO-D", demo_d_meta)
        demo_d_case = demos["DEMO-D"]["case_id"]
        review = client.post(
            f"/api/cases/{demo_d_case}/reviews",
            json={
                "node_from": "N1",
                "node_to": "N2",
                "surface": "left",
                "review_class": "D05",
                "review_status": "CONFIRMED",
                "reviewer_alias": "DEMO-REVIEWER",
                "review_note": "synthetic tape-like visual change demo",
            },
        )
        review.raise_for_status()
        reviews = client.get(f"/api/cases/{demo_d_case}/reviews")
        reviews.raise_for_status()
        report_after_review = client.get(f"/api/cases/{demo_d_case}/report")
        report_after_review.raise_for_status()
        checks = {
            "health": health.json(),
            "model": model.json(),
            "warmup": warmup.json(),
            "frontend_status": frontend.status_code,
            "frontend_has_v02": bool(
                frontend_javascript
                and "COMPETITION MVP v0.2" in frontend_javascript.text
            ),
            "demos": demos,
            "review": review.json(),
            "review_count": len(reviews.json()["reviews"]),
            "report_after_review_status": report_after_review.status_code,
            "report_separates_machine_human": (
                "机器分析" in report_after_review.text
                and "人工复核" in report_after_review.text
                and "UNKNOWN_VISUAL_CHANGE" in report_after_review.text
                and "D05" in report_after_review.text
            ),
        }
    database_path = Path(checks["health"]["database"])
    connection = sqlite3.connect(database_path)
    try:
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        demo_d_case = checks["demos"]["DEMO-D"]["case_id"]
        row_counts = {
            table: connection.execute(
                f'SELECT COUNT(*) FROM "{table}" WHERE case_id=?', (demo_d_case,)
            ).fetchone()[0]
            for table in (
                "case_nodes",
                "detections",
                "pair_changes",
                "surface_analysis",
                "analysis_results",
                "reports",
                "review_events",
            )
        }
        schema_version = connection.execute(
            "SELECT version FROM schema_version WHERE singleton=1"
        ).fetchone()[0]
    finally:
        connection.close()
    expected = {
        "demo_a_regression": checks["demos"]["DEMO-A"]["first_abnormal_interval"]
        == "N1_TO_N2",
        "demo_b_regression": checks["demos"]["DEMO-B"]["first_abnormal_interval"]
        == "N1_TO_N2",
        "demo_c_detection": checks["demos"]["DEMO-C"]["detection_count"] >= 1,
        "demo_d_interval": checks["demos"]["DEMO-D"]["first_abnormal_interval"]
        == "N1_TO_N2",
        "demo_d_left_trigger": [
            item["surface"] for item in checks["demos"]["DEMO-D"]["trigger_surfaces"]
        ]
        == ["left"],
        "demo_d_twelve_uploads": checks["demos"]["DEMO-D"]["upload_count"] == 12,
        "review_persisted": checks["review_count"] == 1
        and row_counts["review_events"] == 1,
        "report_review_visible": checks["report_separates_machine_human"],
        "frontend": checks["frontend_status"] == 200 and checks["frontend_has_v02"],
        "schema_v02": schema_version == 2,
    }
    payload = {
        "report_version": "mvp-e2e-report-v0.2",
        "generated_at": datetime.now().astimezone().isoformat(),
        "checks": checks,
        "sqlite": {
            "path": str(database_path),
            "schema_version": schema_version,
            "tables": tables,
            "demo_d_row_counts": row_counts,
        },
        "assertions": expected,
        "passed": all(expected.values()),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
