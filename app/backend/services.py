"""Application orchestration for detector, visual change, sequence and evidence."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from ai.runtime.change_detector import ChangeDetector, serializable_change
from ai.runtime.detector import Detector
from ai.runtime.evidence_report import generate_evidence_report
from ai.runtime.fingerprint import build_appearance_fingerprint
from ai.runtime.model_registry import ModelRegistry
from ai.runtime.registration import ImageRegistrar
from ai.runtime.sequence_locator import locate_first_abnormality

from .storage.database import EvidenceDatabase

NODE_ID_PATTERN = re.compile(r"^N[1-9][0-9]*$")


class MVPError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class MVPService:
    """Run the competition pipeline and persist its evidence lineage."""

    def __init__(
        self,
        config_path: str | Path = "configs/runtime/mvp-v0.1.json",
        detector: Detector | None = None,
        database: EvidenceDatabase | None = None,
    ):
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.runtime_root = Path(self.config["runtime_root"])
        for directory in ("cases", "reports", "logs", "demo"):
            (self.runtime_root / directory).mkdir(parents=True, exist_ok=True)
        self.registry = ModelRegistry(self.config["active_model_registry"])
        self.detector = detector or Detector(
            self.registry, confidence=float(self.config["detector_confidence"])
        )
        self.registrar = ImageRegistrar(self.config["change_config"])
        self.change_detector = ChangeDetector(self.registrar)
        self.database = database or EvidenceDatabase(self.config["database_path"])

    @staticmethod
    def now() -> str:
        return datetime.now().astimezone().isoformat()

    def health(self) -> dict[str, Any]:
        artifact, runtime = self.registry.runtime_artifact()
        return {
            "status": "ok",
            "pipeline_version": self.config["pipeline_version"],
            "database": str(self.database.path),
            "database_ready": self.database.path.is_file(),
            "model_artifact_ready": artifact.is_file(),
            "runtime": runtime,
        }

    def create_case(self, case_name: str, notes: str = "") -> dict[str, Any]:
        record = {
            "case_id": f"case-{uuid.uuid4().hex}",
            "created_at": self.now(),
            "case_name": case_name,
            "status": "CREATED",
            "pipeline_version": self.config["pipeline_version"],
            "active_model_version": self.registry.model_version,
            "notes": notes,
        }
        return self.database.create_case(record)

    def validate_image(
        self, content: bytes, filename: str, content_type: str | None
    ) -> tuple[np.ndarray, str]:
        if len(content) > int(self.config["max_upload_bytes"]):
            raise MVPError("IMAGE_TOO_LARGE", "图片超过允许的最大文件大小。", 413)
        if not content:
            raise MVPError("IMAGE_EMPTY", "图片内容为空。")
        suffix = Path(filename or "").suffix.lower()
        if suffix not in self.config["allowed_extensions"]:
            raise MVPError("IMAGE_EXTENSION_INVALID", "只允许JPG/JPEG/PNG/WEBP。")
        if content_type not in self.config["allowed_mime_types"]:
            raise MVPError("IMAGE_MIME_INVALID", "图片MIME类型不受支持。")
        decoded = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
        if decoded is None or decoded.ndim != 3:
            raise MVPError("IMAGE_UNREADABLE", "图片无法解析。")
        return decoded, suffix

    def add_node(
        self,
        case_id: str,
        node_id: str,
        surface: str,
        content: bytes,
        filename: str,
        content_type: str | None,
        capture_time: str | None = None,
    ) -> dict[str, Any]:
        if not NODE_ID_PATTERN.fullmatch(node_id):
            raise MVPError("NODE_ID_INVALID", "node_id必须使用N1、N2、N3等格式。")
        try:
            self.database.get_case(case_id, include_details=False)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        _decoded, suffix = self.validate_image(content, filename, content_type)
        case_dir = self.runtime_root / "cases" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{node_id.lower()}-{uuid.uuid4().hex[:16]}{suffix}"
        image_path = case_dir / safe_name
        image_path.write_bytes(content)
        record = {
            "case_id": case_id,
            "node_id": node_id,
            "surface": surface or "PACKAGE_EXTERIOR",
            "capture_time": capture_time,
            "image_path": str(image_path),
            "image_sha256": hashlib.sha256(content).hexdigest(),
            "created_at": self.now(),
        }
        try:
            return self.database.add_node(record)
        except sqlite3.IntegrityError as error:
            image_path.unlink(missing_ok=True)
            raise MVPError("NODE_ALREADY_EXISTS", "该节点已经上传。", 409) from error

    def detect_upload(
        self, content: bytes, filename: str, content_type: str | None
    ) -> dict[str, Any]:
        decoded, _ = self.validate_image(content, filename, content_type)
        return self.detector.predict(decoded)

    def change_upload(
        self,
        reference: tuple[bytes, str, str | None],
        current: tuple[bytes, str, str | None],
    ) -> dict[str, Any]:
        ref_image, _ = self.validate_image(*reference)
        cur_image, _ = self.validate_image(*current)
        return serializable_change(self.change_detector.detect(ref_image, cur_image))

    @staticmethod
    def _node_sort(node: dict[str, Any]) -> int:
        return int(node["node_id"][1:])

    def analyze_case(self, case_id: str) -> dict[str, Any]:
        try:
            case = self.database.get_case(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        source_nodes = sorted(case["nodes"], key=self._node_sort)
        if len(source_nodes) < 3:
            raise MVPError("NODES_INCOMPLETE", "分析至少需要N1/N2/N3三个节点。")
        expected = [f"N{index}" for index in range(1, len(source_nodes) + 1)]
        actual = [node["node_id"] for node in source_nodes]
        if actual != expected:
            raise MVPError("NODE_SEQUENCE_GAPPED", "节点必须从N1开始连续编号。")
        total_started = time.perf_counter()
        detector_ms = 0.0
        node_results: list[dict[str, Any]] = []
        images: list[np.ndarray] = []
        case_dir = self.runtime_root / "cases" / case_id
        for node in source_nodes:
            image = cv2.imread(node["image_path"], cv2.IMREAD_COLOR)
            if image is None:
                raise MVPError("IMAGE_UNREADABLE", f"{node['node_id']}图片无法解析。")
            images.append(image)
            detection = self.detector.predict(image)
            detector_ms += float(detection["inference_ms"])
            fingerprint = build_appearance_fingerprint(
                node["image_path"], detection["detections"]
            )
            visualization = image.copy()
            for item in detection["detections"]:
                x1, y1, x2, y2 = [int(value) for value in item["bbox_xyxy"]]
                cv2.rectangle(visualization, (x1, y1), (x2, y2), (25, 127, 235), 2)
                cv2.putText(
                    visualization,
                    f"{item['class_code']} {item['confidence']:.2f}",
                    (x1, max(20, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (25, 127, 235),
                    2,
                )
            visual_path = case_dir / f"detected-{node['node_id'].lower()}.jpg"
            cv2.imwrite(str(visual_path), visualization)
            node_results.append(
                {
                    **node,
                    **detection,
                    "fingerprint": fingerprint,
                    "visualization_path": str(visual_path),
                }
            )
        registration_ms = 0.0
        change_ms = 0.0
        pair_results: list[dict[str, Any]] = []
        for index in range(len(images) - 1):
            reg_started = time.perf_counter()
            registration = self.registrar.register(images[index], images[index + 1])
            registration_ms += (time.perf_counter() - reg_started) * 1000.0
            change_started = time.perf_counter()
            change = self.change_detector.detect(
                images[index],
                images[index + 1],
                known_detections=node_results[index + 1]["detections"],
                registration=registration,
            )
            change_ms += (time.perf_counter() - change_started) * 1000.0
            reference_id = node_results[index]["node_id"]
            current_id = node_results[index + 1]["node_id"]
            visual_path = (
                case_dir / f"change-{reference_id.lower()}-{current_id.lower()}.jpg"
            )
            cv2.imwrite(str(visual_path), change["visualization"])
            pair_results.append(
                {
                    "reference_node_id": reference_id,
                    "current_node_id": current_id,
                    **serializable_change(change),
                    "visualization_path": str(visual_path),
                }
            )
        analysis = locate_first_abnormality(node_results, pair_results)
        analysis["pipeline_version"] = self.config["pipeline_version"]
        analysis["model_version"] = self.registry.model_version
        analysis["model_sha256"] = self.registry.data["sha256"]
        analysis["created_at"] = self.now()
        analysis["timing_ms"] = {
            "detector": detector_ms,
            "registration": registration_ms,
            "change_detection": change_ms,
            "total": (time.perf_counter() - total_started) * 1000.0,
        }
        report = generate_evidence_report(
            case,
            node_results,
            pair_results,
            analysis,
            self.registry.public_info(),
            self.runtime_root / "reports" / case_id,
        )
        self.database.store_analysis(
            case_id,
            analysis["created_at"],
            node_results,
            pair_results,
            analysis,
            report,
        )
        return {
            "case_id": case_id,
            "nodes": node_results,
            "pair_changes": pair_results,
            "analysis": analysis,
            "report": report,
        }
