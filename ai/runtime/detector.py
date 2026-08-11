"""Unified D02/D03 detector interface for PyTorch and ONNX artifacts."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import cv2
import numpy as np

from .model_registry import ModelRegistry, SUPPORTED_CLASSES


class DetectorError(RuntimeError):
    """Raised when a detector input or result is invalid."""


class Detector:
    """Lazy-load an Ultralytics model selected by the active registry."""

    def __init__(
        self,
        registry: ModelRegistry | str | Path,
        confidence: float = 0.25,
        model_factory: Callable[[str], Any] | None = None,
    ):
        self.registry = (
            registry if isinstance(registry, ModelRegistry) else ModelRegistry(registry)
        )
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("confidence必须位于0到1之间。")
        self.confidence = confidence
        self._model_factory = model_factory
        self._model: Any | None = None
        self._artifact, self.runtime = self.registry.runtime_artifact()

    def _load(self) -> Any:
        if self._model is None:
            if self._model_factory is None:
                from ultralytics import YOLO

                self._model = YOLO(str(self._artifact))
            else:
                self._model = self._model_factory(str(self._artifact))
        return self._model

    @staticmethod
    def _decode(image: np.ndarray | str | Path) -> np.ndarray:
        if isinstance(image, np.ndarray):
            decoded = image
        else:
            decoded = cv2.imread(str(image), cv2.IMREAD_COLOR)
        if decoded is None or decoded.ndim != 3 or decoded.shape[2] != 3:
            raise DetectorError("图片无法解析为BGR三通道图像。")
        return decoded

    def predict(self, image: np.ndarray | str | Path) -> dict[str, Any]:
        decoded = self._decode(image)
        height, width = decoded.shape[:2]
        started = time.perf_counter()
        result = self._load().predict(
            source=decoded,
            imgsz=self.registry.imgsz,
            conf=self.confidence,
            verbose=False,
            device=0 if self.runtime == "pytorch" else "cpu",
        )[0]
        inference_ms = (time.perf_counter() - started) * 1000.0
        detections: list[dict[str, Any]] = []
        boxes = getattr(result, "boxes", None)
        if boxes is not None and len(boxes):
            xyxy = boxes.xyxy.detach().cpu().numpy()
            classes = boxes.cls.detach().cpu().numpy().astype(int)
            confidences = boxes.conf.detach().cpu().numpy()
            for coords, class_id, score in zip(xyxy, classes, confidences, strict=True):
                if int(class_id) not in SUPPORTED_CLASSES:
                    raise DetectorError(f"模型返回未支持类别ID：{class_id}")
                x1, y1, x2, y2 = [float(value) for value in coords]
                meta = SUPPORTED_CLASSES[int(class_id)]
                detections.append(
                    {
                        "class_id": int(class_id),
                        "class_code": meta["code"],
                        "class_name": meta["name"],
                        "confidence": float(score),
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "bbox_normalized": [
                            x1 / width,
                            y1 / height,
                            x2 / width,
                            y2 / height,
                        ],
                    }
                )
        return {
            "image_width": width,
            "image_height": height,
            "model_version": self.registry.model_version,
            "model_sha256": self.registry.data["sha256"],
            "runtime": self.runtime,
            "inference_ms": inference_ms,
            "detections": detections,
        }
