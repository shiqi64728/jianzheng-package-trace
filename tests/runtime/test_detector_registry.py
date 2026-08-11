from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from ai.runtime.detector import Detector, DetectorError
from ai.runtime.model_registry import FULL_CLASS_SUPPORT, ModelRegistry, RegistryError


class FakeBoxes:
    def __init__(self, classes=(0, 1)):
        self.xyxy = torch.tensor([[10, 20, 60, 80], [100, 40, 180, 120]])[
            : len(classes)
        ]
        self.cls = torch.tensor(classes)
        self.conf = torch.tensor([0.9, 0.6])[: len(classes)]

    def __len__(self):
        return len(self.cls)


class FakeModel:
    def __init__(self, classes=(0, 1)):
        self.classes = classes
        self.calls = []

    def predict(self, **kwargs):
        self.calls.append(kwargs)
        return [type("Result", (), {"boxes": FakeBoxes(self.classes)})()]


class DetectorRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pt = self.root / "best.pt"
        self.pt.write_bytes(b"fixture-model")
        self.payload = {
            "active_model": "fixture",
            "model_version": "fixture-v0.1",
            "source_pt": str(self.pt),
            "sha256": hashlib.sha256(self.pt.read_bytes()).hexdigest(),
            "imgsz": 640,
            "classes": ["D02", "D03"],
            "selection_basis": "unit-test",
            "runtime_preferred": "pytorch",
        }
        self.registry_path = self.root / "registry.json"
        self.registry_path.write_text(json.dumps(self.payload), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_registry_loads_active_model(self):
        registry = ModelRegistry(self.registry_path)
        self.assertEqual(registry.model_version, "fixture-v0.1")
        self.assertEqual(registry.imgsz, 640)

    def test_registry_rejects_hash_drift(self):
        self.pt.write_bytes(b"changed")
        with self.assertRaises(RegistryError):
            ModelRegistry(self.registry_path)

    def test_registry_rejects_unsupported_class_schema(self):
        self.payload["classes"] = ["D01", "D02", "D03"]
        self.registry_path.write_text(json.dumps(self.payload), encoding="utf-8")
        with self.assertRaises(RegistryError):
            ModelRegistry(self.registry_path)

    def test_registry_falls_back_when_onnx_missing(self):
        self.payload.update(
            {
                "runtime_preferred": "onnx",
                "onnx_status": "validated",
                "onnx_path": str(self.root / "missing.onnx"),
            }
        )
        self.registry_path.write_text(json.dumps(self.payload), encoding="utf-8")
        path, runtime = ModelRegistry(self.registry_path).runtime_artifact()
        self.assertEqual((path, runtime), (self.pt, "pytorch"))

    def test_public_support_discloses_three_unsupported_classes(self):
        info = ModelRegistry(self.registry_path).public_info()
        self.assertEqual(info["class_support"], FULL_CLASS_SUPPORT)
        self.assertEqual(
            sum("not_supported" in item for item in info["class_support"].values()), 3
        )

    def test_detector_returns_bbox_schema(self):
        model = FakeModel()
        detector = Detector(self.registry_path, model_factory=lambda _path: model)
        result = detector.predict(np.zeros((200, 300, 3), dtype=np.uint8))
        self.assertEqual(result["image_width"], 300)
        self.assertEqual(result["detections"][0]["class_code"], "D02")
        self.assertEqual(len(result["detections"][0]["bbox_normalized"]), 4)

    def test_detector_maps_d03(self):
        model = FakeModel(classes=(1,))
        result = Detector(
            self.registry_path, model_factory=lambda _path: model
        ).predict(np.zeros((200, 300, 3), dtype=np.uint8))
        self.assertEqual(result["detections"][0]["class_name"], "纸箱破口")

    def test_detector_rejects_unknown_class_id(self):
        model = FakeModel(classes=(4,))
        detector = Detector(self.registry_path, model_factory=lambda _path: model)
        with self.assertRaises(DetectorError):
            detector.predict(np.zeros((200, 300, 3), dtype=np.uint8))

    def test_detector_rejects_invalid_image(self):
        detector = Detector(self.registry_path, model_factory=lambda _path: FakeModel())
        with self.assertRaises(DetectorError):
            detector.predict(np.zeros((20, 20), dtype=np.uint8))

    def test_detector_passes_registry_imgsz_and_confidence(self):
        model = FakeModel(classes=())
        detector = Detector(
            self.registry_path, confidence=0.37, model_factory=lambda _path: model
        )
        detector.predict(np.zeros((100, 100, 3), dtype=np.uint8))
        self.assertEqual(model.calls[0]["imgsz"], 640)
        self.assertEqual(model.calls[0]["conf"], 0.37)
