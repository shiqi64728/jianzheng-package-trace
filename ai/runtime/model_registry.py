"""Validated access to the external active-detector registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SUPPORTED_CLASSES = {
    0: {"code": "D02", "name": "表面凹陷"},
    1: {"code": "D03", "name": "纸箱破口"},
}
FULL_CLASS_SUPPORT = {
    "D01": "detector_not_supported_yet",
    "D02": "model_supported",
    "D03": "model_supported",
    "D04": "detector_not_supported_yet",
    "D05": "detector_not_supported_yet",
}


class RegistryError(RuntimeError):
    """Raised when the active detector registry is invalid."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class ModelRegistry:
    """Load and validate one immutable active model selection record."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        if not self.path.is_file():
            raise RegistryError(f"活动模型注册表不存在：{self.path}")
        self.data: dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8"))
        self._validate()

    def _validate(self) -> None:
        required = {
            "active_model",
            "model_version",
            "source_pt",
            "sha256",
            "imgsz",
            "classes",
            "selection_basis",
        }
        missing = sorted(required - self.data.keys())
        if missing:
            raise RegistryError(f"活动模型注册表缺少字段：{missing}")
        source = Path(self.data["source_pt"])
        if not source.is_absolute() or not source.is_file():
            raise RegistryError(f"活动PT模型不可用：{source}")
        actual = sha256_file(source)
        if actual != self.data["sha256"]:
            raise RegistryError("活动PT模型SHA-256与注册表不一致。")
        if set(self.data["classes"]) != {"D02", "D03"}:
            raise RegistryError("活动检测器类别边界必须严格为D02/D03。")

    @property
    def model_version(self) -> str:
        return str(self.data["model_version"])

    @property
    def imgsz(self) -> int:
        return int(self.data["imgsz"])

    def runtime_artifact(self) -> tuple[Path, str]:
        preferred = self.data.get("runtime_preferred", "pytorch")
        onnx_path = Path(self.data.get("onnx_path", ""))
        if (
            preferred == "onnx"
            and self.data.get("onnx_status") == "validated"
            and onnx_path.is_file()
        ):
            expected = self.data.get("onnx_sha256")
            if expected and sha256_file(onnx_path) == expected:
                return onnx_path, "onnx"
        return Path(self.data["source_pt"]), "pytorch"

    def public_info(self) -> dict[str, Any]:
        artifact, runtime = self.runtime_artifact()
        return {
            "active_model": self.data["active_model"],
            "model_version": self.model_version,
            "model_sha256": self.data["sha256"],
            "imgsz": self.imgsz,
            "runtime": runtime,
            "runtime_artifact": str(artifact),
            "classes": self.data["classes"],
            "class_support": FULL_CLASS_SUPPORT,
            "selection_basis": self.data["selection_basis"],
            "onnx_status": self.data.get("onnx_status", "not_exported"),
        }
