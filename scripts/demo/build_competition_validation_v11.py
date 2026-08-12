"""Freeze RC v1.1 system behavior validation without calling synthetic data real."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

V10 = Path(
    "E:/JianZhengData/runtime/competition-validation-v1.0/competition-validation-summary-v1.0.json"
)
OUTPUT_DIR = Path("E:/JianZhengData/runtime/competition-validation-v1.1")
OUTPUT = OUTPUT_DIR / "competition-validation-summary-v1.1.json"

REAL_SCENARIOS = (
    "REAL-NORMAL",
    "REAL-N1-N2",
    "REAL-N2-N3",
    "REAL-MULTISURFACE",
    "REAL-LIGHTING-VARIATION",
)


def main() -> int:
    base = json.loads(V10.read_text(encoding="utf-8"))
    inherited = []
    for item in base["scenarios"]:
        record = dict(item)
        record["source_version"] = "competition-validation-v1.0"
        record["source_type"] = (
            "PUBLIC_DATA_PROXY"
            if item["scenario_id"]
            in {"SBV-02-KNOWN-D02", "SBV-03-KNOWN-D03", "SBV-17-VIDEO-KEYFRAME"}
            else "SYNTHETIC_CONTROLLED_RULE"
        )
        inherited.append(record)
    real = [
        {
            "scenario_id": scenario,
            "source_type": "REAL_DATA",
            "expected_behavior": "Run only after an authorized privacy-cleared capture is supplied.",
            "actual_behavior": None,
            "status": "PENDING_EXTERNAL_DATA",
            "pass": None,
            "evidence": "E:/JianZhengData/runtime/competition-rc-v1.1/evidence/real-sequence-discovery-v1.1.json",
        }
        for scenario in REAL_SCENARIOS
    ]
    payload = {
        "report_version": "system-behavior-validation-v1.1",
        "validation_label": "SYSTEM BEHAVIOR VALIDATION",
        "not_model_accuracy": True,
        "generated_at": datetime.now().astimezone().isoformat(),
        "executed_scenario_count": len(inherited),
        "executed_passed_count": sum(x["pass"] is True for x in inherited),
        "real_scenario_count": len(real),
        "real_scenario_status": "PENDING_EXTERNAL_DATA",
        "synthetic_or_public_scenario_count": len(inherited),
        "scenarios": inherited + real,
        "passed": all(x["pass"] is True for x in inherited),
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                **{
                    key: payload[key]
                    for key in (
                        "executed_scenario_count",
                        "executed_passed_count",
                        "real_scenario_count",
                        "real_scenario_status",
                        "passed",
                    )
                },
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
