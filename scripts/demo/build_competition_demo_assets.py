"""Build deterministic RC demo assets outside Git, including the MP4 demo."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import cv2

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ai.runtime.detector import Detector  # noqa: E402
from ai.runtime.model_registry import ModelRegistry  # noqa: E402
from ai.runtime.video_screening import screen_video  # noqa: E402
from scripts.demo import build_demo_cases  # noqa: E402

RC_ROOT = Path("E:/JianZhengData/runtime/competition-rc-v1.0")
V02_DEMO = Path("E:/JianZhengData/runtime/mvp-v0.2/demo")
REGISTRY = Path("E:/JianZhengData/models/active/detector-v0.1.json")


def _ensure_v02_demo() -> None:
    summary = V02_DEMO / "demo-cases-v0.2.json"
    if not summary.is_file():
        build_demo_cases.main()


def _copy_demo(name: str) -> Path:
    source = V02_DEMO / name
    destination = RC_ROOT / "demo" / name
    if not source.is_dir():
        raise RuntimeError(f"missing source demo: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def _create_video(source_image: Path, destination: Path) -> dict:
    image = cv2.imread(str(source_image), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"cannot decode video source image: {source_image}")
    image = cv2.resize(image, (960, 720), interpolation=cv2.INTER_AREA)
    quiet = build_demo_cases.base_carton(2026, "front")
    quiet = cv2.resize(quiet, (960, 720), interpolation=cv2.INTER_AREA)
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(destination), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (960, 720)
    )
    if not writer.isOpened():
        raise RuntimeError("OpenCV MP4 writer is unavailable")
    try:
        for index in range(30):
            frame = quiet if index < 10 else image
            writer.write(frame)
    finally:
        writer.release()
    return {
        "label": "SYNTHETIC_VIDEO_DEMO",
        "construction": "10 synthetic quiet frames followed by 20 repeated legal public-val frames",
        "fps": 10.0,
        "frame_count": 30,
        "expected_abnormal_start_seconds": 1.0,
        "source_image": str(source_image),
        "video_path": str(destination),
    }


def main() -> int:
    _ensure_v02_demo()
    demo_c = _copy_demo("DEMO-C")
    demo_d = _copy_demo("DEMO-D")
    metadata = json.loads((demo_c / "metadata.json").read_text(encoding="utf-8"))
    source = Path(metadata["copied_image"])
    if not source.is_file():
        source = next(demo_c.glob("public-val-sample.*"))
    video_dir = RC_ROOT / "demo" / "SYNTHETIC-VIDEO-DEMO"
    video = video_dir / "damage-keyframe-screening.mp4"
    construction = _create_video(source, video)
    detector = Detector(ModelRegistry(REGISTRY), confidence=0.25)
    validation = screen_video(
        video,
        detector,
        video_dir / "validation-keyframes",
        sample_interval_frames=5,
        top_k=5,
    )
    if validation["abnormal_frame_count"] < 1:
        raise RuntimeError(
            "synthetic video did not produce a deterministic abnormal keyframe"
        )
    summary = {
        "label": "COMPETITION_RC_DEMO_ASSETS",
        "generated_at": datetime.now().astimezone().isoformat(),
        "demo_c": str(demo_c),
        "demo_d": str(demo_d),
        "synthetic_video": construction,
        "video_validation": validation,
    }
    output = RC_ROOT / "demo" / "competition-demo-assets-v1.0.json"
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "abnormal_frames": validation["abnormal_frame_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
