"""Application orchestration for multisurface evidence and human review."""

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
from ai.runtime.fingerprint import build_node_fingerprint_summary
from ai.runtime.model_registry import ModelRegistry
from ai.runtime.risk_engine import RiskEngine
from ai.runtime.registration import ImageRegistrar
from ai.runtime.sequence_locator import locate_multisurface_first_abnormality
from ai.runtime.surface_analyzer import SurfaceAnalyzer
from ai.runtime.surfaces import SUPPORTED_SURFACES, normalize_surface
from ai.runtime.video_screening import VideoScreeningError, screen_video

from .logistics_adapter import LogisticsValidationError, parse_logistics
from .storage.database import EvidenceDatabase

NODE_ID_PATTERN = re.compile(r"^N[1-9][0-9]*$")
REVIEW_CLASSES = {"D01", "D02", "D03", "D04", "D05", "NORMAL_VARIATION", "UNSURE"}
REVIEW_STATUSES = {"CONFIRMED", "REJECTED", "UNSURE"}
REVIEWER_ALIASES = {"MEMBER-A", "MEMBER-B", "MEMBER-C", "DEMO-REVIEWER"}
WORK_ORDER_ALIASES = {"MEMBER-A", "MEMBER-B", "MEMBER-C", "DEMO-OPERATOR"}
WORK_ORDER_STATES = {
    "OPEN",
    "IN_REVIEW",
    "NEEDS_MORE_EVIDENCE",
    "CONFIRMED",
    "REJECTED",
    "RESOLVED",
}
WORK_ORDER_EVENT_TYPES = {
    "ASSIGN",
    "STATE_CHANGE",
    "NOTE",
    "EVIDENCE_REQUEST",
    "RESOLVE",
}
WORK_ORDER_TRANSITIONS = {
    "OPEN": {"IN_REVIEW", "NEEDS_MORE_EVIDENCE", "REJECTED", "RESOLVED"},
    "IN_REVIEW": {"NEEDS_MORE_EVIDENCE", "CONFIRMED", "REJECTED", "RESOLVED"},
    "NEEDS_MORE_EVIDENCE": {"IN_REVIEW", "REJECTED", "RESOLVED"},
    "CONFIRMED": {"RESOLVED"},
    "REJECTED": {"RESOLVED"},
    "RESOLVED": set(),
}


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
    """Run the v0.2 pipeline and preserve machine/human evidence separately."""

    def __init__(
        self,
        config_path: str | Path = "configs/runtime/competition-rc-v1.0.json",
        detector: Detector | None = None,
        database: EvidenceDatabase | None = None,
    ):
        self.config_path = Path(config_path)
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.runtime_root = Path(self.config["runtime_root"])
        for directory in ("cases", "reports", "logs", "demo", "calibration", "video"):
            (self.runtime_root / directory).mkdir(parents=True, exist_ok=True)
        self.registry = ModelRegistry(self.config["active_model_registry"])
        self.detector = detector or Detector(
            self.registry, confidence=float(self.config["detector_confidence"])
        )
        self.registrar = ImageRegistrar(self.config["change_config"])
        self.change_detector = ChangeDetector(self.registrar)
        self.surface_analyzer = SurfaceAnalyzer(
            self.detector, self.registrar, self.change_detector
        )
        self.database = database or EvidenceDatabase(
            self.config["database_path"],
            bootstrap_from=self.config.get("bootstrap_database_from"),
            target_schema_version=(
                3 if "rc-v1.0" in self.config["pipeline_version"] else 2
            ),
        )
        self.risk_engine = RiskEngine()
        self._warmup_result: dict[str, Any] | None = None

    @staticmethod
    def now() -> str:
        return datetime.now().astimezone().isoformat()

    def health(self) -> dict[str, Any]:
        artifact, runtime = self.registry.runtime_artifact()
        return {
            "status": "ok",
            "pipeline_version": self.config["pipeline_version"],
            "schema_version": self.database.schema_version(),
            "database": str(self.database.path),
            "database_ready": self.database.path.is_file(),
            "model_artifact_ready": artifact.is_file(),
            "runtime": runtime,
            "warmup_completed": self._warmup_result is not None,
        }

    def warmup(self, force: bool = False) -> dict[str, Any]:
        if self._warmup_result is not None and not force:
            return {**self._warmup_result, "cached": True}
        try:
            result = self.detector.warmup()
        except Exception as error:
            result = {
                "loaded": False,
                "runtime": self.detector.runtime,
                "warmup_ms": 0.0,
                "gpu": False,
                "fallback": "lazy",
                "warning": str(error),
            }
        self._warmup_result = {**result, "cached": False}
        return dict(self._warmup_result)

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
            raise MVPError("IMAGE_EXTENSION_INVALID", "只允许 JPG/JPEG/PNG/WEBP。")
        if content_type not in self.config["allowed_mime_types"]:
            raise MVPError("IMAGE_MIME_INVALID", "图片 MIME 类型不受支持。")
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
            raise MVPError("NODE_ID_INVALID", "node_id 必须使用 N1、N2、N3 等格式。")
        try:
            normalized_surface = normalize_surface(surface)
        except ValueError as error:
            raise MVPError(
                "SURFACE_INVALID",
                "surface 不在支持列表中。",
                details={"supported_surfaces": list(SUPPORTED_SURFACES)},
            ) from error
        try:
            self.database.get_case(case_id, include_details=False)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        _decoded, suffix = self.validate_image(content, filename, content_type)
        case_dir = self.runtime_root / "cases" / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        safe_name = (
            f"{node_id.lower()}-{normalized_surface}-{uuid.uuid4().hex[:16]}{suffix}"
        )
        image_path = case_dir / safe_name
        image_path.write_bytes(content)
        record = {
            "case_id": case_id,
            "node_id": node_id,
            "surface": normalized_surface,
            "capture_time": capture_time,
            "image_path": str(image_path),
            "image_sha256": hashlib.sha256(content).hexdigest(),
            "created_at": self.now(),
        }
        try:
            return self.database.add_node(record)
        except sqlite3.IntegrityError as error:
            image_path.unlink(missing_ok=True)
            raise MVPError(
                "NODE_SURFACE_ALREADY_EXISTS",
                "该节点的对应表面已经上传。",
                409,
            ) from error

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
    def _node_number(node_id: str) -> int:
        return int(node_id[1:])

    def analyze_case(self, case_id: str) -> dict[str, Any]:
        try:
            case = self.database.get_case(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        source_nodes = sorted(
            case["nodes"],
            key=lambda item: (self._node_number(item["node_id"]), item["surface"]),
        )
        node_ids = sorted(
            {item["node_id"] for item in source_nodes}, key=self._node_number
        )
        if len(node_ids) < 3:
            raise MVPError("NODES_INCOMPLETE", "分析至少需要 N1/N2/N3 三个节点。")
        expected = [f"N{index}" for index in range(1, len(node_ids) + 1)]
        if node_ids != expected:
            raise MVPError("NODE_SEQUENCE_GAPPED", "节点必须从 N1 开始连续编号。")

        total_started = time.perf_counter()
        capture_ms = 0.0
        registration_ms = 0.0
        change_ms = 0.0
        node_results: list[dict[str, Any]] = []
        images: dict[tuple[str, str], np.ndarray] = {}
        case_dir = self.runtime_root / "cases" / case_id
        for record in source_nodes:
            image = cv2.imread(record["image_path"], cv2.IMREAD_COLOR)
            if image is None:
                raise MVPError(
                    "IMAGE_UNREADABLE",
                    f"{record['node_id']}.{record['surface']} 图片无法解析。",
                )
            images[(record["node_id"], record["surface"])] = image
            result, elapsed = self.surface_analyzer.analyze_capture(
                record, image, case_dir
            )
            capture_ms += elapsed
            node_results.append(result)

        result_by_key = {
            (item["node_id"], item["surface"]): item for item in node_results
        }
        surface_order = {name: index for index, name in enumerate(SUPPORTED_SURFACES)}
        available_surfaces = sorted(
            {item["surface"] for item in node_results},
            key=lambda name: surface_order[name],
        )
        pair_results: list[dict[str, Any]] = []
        for index in range(len(node_ids) - 1):
            reference_id, current_id = node_ids[index], node_ids[index + 1]
            for surface in available_surfaces:
                reference = result_by_key.get((reference_id, surface))
                current = result_by_key.get((current_id, surface))
                if reference is None or current is None:
                    pair_results.append(
                        self.surface_analyzer.missing_pair(
                            reference_id, current_id, surface
                        )
                    )
                    continue
                pair, timing = self.surface_analyzer.analyze_pair(
                    reference,
                    current,
                    images[(reference_id, surface)],
                    images[(current_id, surface)],
                    case_dir,
                )
                pair_results.append(pair)
                registration_ms += timing["registration"]
                change_ms += timing["change_detection"]

        analysis = locate_multisurface_first_abnormality(node_results, pair_results)
        summaries = []
        for node_id in node_ids:
            incoming_unknown = [
                pair["surface"]
                for pair in pair_results
                if pair["current_node_id"] == node_id
                and pair.get("is_significant")
                and pair.get("registration_status") != "FAILED"
                and not result_by_key.get((node_id, pair["surface"]), {}).get(
                    "detections"
                )
            ]
            summaries.append(
                build_node_fingerprint_summary(
                    node_id,
                    [item for item in node_results if item["node_id"] == node_id],
                    incoming_unknown,
                )
            )
        analysis["node_fingerprint_summaries"] = summaries
        analysis["pipeline_version"] = self.config["pipeline_version"]
        analysis["model_version"] = self.registry.model_version
        analysis["model_sha256"] = self.registry.data["sha256"]
        analysis["created_at"] = self.now()
        analysis["timing_ms"] = {
            "surface_capture_analysis": capture_ms,
            "detector": sum(float(item["inference_ms"]) for item in node_results),
            "registration": registration_ms,
            "change_detection": change_ms,
            "total": (time.perf_counter() - total_started) * 1000.0,
        }
        reviews = self.database.list_reviews(case_id)
        risk_started = time.perf_counter()
        risk = self.risk_engine.assess(analysis, pair_results, source_nodes, reviews)
        risk_ms = (time.perf_counter() - risk_started) * 1000.0
        report_started = time.perf_counter()
        report = generate_evidence_report(
            case,
            node_results,
            pair_results,
            analysis,
            self.registry.public_info(),
            self.runtime_root / "reports" / case_id,
            node_summaries=summaries,
            reviews=reviews,
            report_revision=len(reviews),
            logistics_nodes=case.get("logistics_nodes", []),
            risk=risk,
            work_orders=case.get("work_orders", []),
            report_version=(
                "evidence-report-v1.0"
                if "rc-v1.0" in self.config["pipeline_version"]
                else None
            ),
        )
        report_ms = (time.perf_counter() - report_started) * 1000.0
        database_started = time.perf_counter()
        self.database.store_analysis(
            case_id,
            analysis["created_at"],
            node_results,
            pair_results,
            analysis,
            report,
        )
        self.database.store_risk(case_id, self.now(), risk)
        database_ms = (time.perf_counter() - database_started) * 1000.0
        processing_breakdown = {
            "core_analysis": analysis["timing_ms"]["total"],
            "database": database_ms,
            "risk_engine": risk_ms,
            "report": report_ms,
            "total_request": (time.perf_counter() - total_started) * 1000.0,
        }
        return {
            "case_id": case_id,
            "nodes": node_results,
            "node_fingerprint_summaries": summaries,
            "pair_changes": pair_results,
            "analysis": analysis,
            "risk": risk,
            "reviews": reviews,
            "report": report,
            "processing_breakdown_ms": processing_breakdown,
        }

    @staticmethod
    def review_payload_sha256(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _machine_result(
        self, case: dict[str, Any], node_from: str, node_to: str, surface: str
    ) -> str:
        if not case.get("analysis"):
            raise MVPError(
                "CASE_NOT_ANALYZED", "必须先完成机器分析再进行人工复核。", 409
            )
        interval_name = f"{node_from}_TO_{node_to}"
        interval = next(
            (
                item
                for item in case["analysis"]["result"].get("intervals", [])
                if item["interval"] == interval_name
            ),
            None,
        )
        if interval is None:
            raise MVPError("REVIEW_INTERVAL_INVALID", "复核区间不是已分析的相邻节点。")
        state = next(
            (item for item in interval["surface_states"] if item["surface"] == surface),
            None,
        )
        if state is None:
            raise MVPError("REVIEW_SURFACE_NOT_ANALYZED", "该表面没有机器分析记录。")
        mapping = {
            "UNKNOWN_CHANGE": "UNKNOWN_VISUAL_CHANGE",
            "MISSING": "PAIR_SURFACE_MISSING",
        }
        return mapping.get(state["status"], state["status"])

    def add_review(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            case = self.database.get_case(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        try:
            surface = normalize_surface(payload.get("surface"))
        except ValueError as error:
            raise MVPError("SURFACE_INVALID", "surface 不在支持列表中。") from error
        review_class = payload.get("review_class")
        review_status = payload.get("review_status")
        reviewer_alias = payload.get("reviewer_alias")
        if review_class not in REVIEW_CLASSES:
            raise MVPError("REVIEW_CLASS_INVALID", "人工复核类别不受支持。")
        if review_status not in REVIEW_STATUSES:
            raise MVPError("REVIEW_STATUS_INVALID", "人工复核状态不受支持。")
        if reviewer_alias not in REVIEWER_ALIASES:
            raise MVPError("REVIEWER_ALIAS_INVALID", "只能使用预设匿名复核人代号。")
        node_from = str(payload.get("node_from", ""))
        node_to = str(payload.get("node_to", ""))
        machine_result = self._machine_result(case, node_from, node_to, surface)
        supersedes = payload.get("supersedes_review_id") or None
        if supersedes:
            try:
                prior = self.database.review_for(supersedes)
            except KeyError as error:
                raise MVPError(
                    "SUPERSEDED_REVIEW_NOT_FOUND", "被替代的复核事件不存在。"
                ) from error
            if (
                prior["case_id"] != case_id
                or prior["node_from"] != node_from
                or prior["node_to"] != node_to
                or prior["surface"] != surface
            ):
                raise MVPError(
                    "SUPERSEDED_REVIEW_SCOPE_MISMATCH",
                    "新旧复核事件必须属于同一案例、区间和表面。",
                )
        stable_payload = {
            "case_id": case_id,
            "node_from": node_from,
            "node_to": node_to,
            "surface": surface,
            "machine_result": machine_result,
            "review_class": review_class,
            "review_status": review_status,
            "reviewer_alias": reviewer_alias,
            "review_note": str(payload.get("review_note", "")),
            "supersedes_review_id": supersedes,
        }
        record = {
            "review_id": f"review-{uuid.uuid4().hex}",
            **stable_payload,
            "created_at": self.now(),
            "review_payload_sha256": self.review_payload_sha256(stable_payload),
        }
        self.database.add_review(record)
        reviews = self.database.list_reviews(case_id)
        self._regenerate_report(case_id, reviews)
        return record

    def risk_for(self, case_id: str) -> dict[str, Any]:
        try:
            case = self.database.get_case(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        if not case.get("analysis"):
            raise MVPError("CASE_NOT_ANALYZED", "必须先完成机器分析。", 409)
        risk = self.risk_engine.assess(
            case["analysis"]["result"],
            case.get("pair_changes", []),
            case.get("nodes", []),
            case.get("reviews", []),
        )
        return self.database.store_risk(case_id, self.now(), risk)

    def import_logistics(
        self, case_id: str, content: bytes, data_format: str
    ) -> list[dict[str, Any]]:
        try:
            self.database.get_case(case_id, include_details=False)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        try:
            nodes = parse_logistics(content, data_format)
        except LogisticsValidationError as error:
            raise MVPError(
                "LOGISTICS_VALIDATION_FAILED",
                str(error),
                422,
                {"row": error.row, "field": error.field},
            ) from error
        stored = self.database.replace_logistics_nodes(case_id, nodes, self.now())
        case = self.database.get_case(case_id)
        if case.get("analysis"):
            self._regenerate_report(case_id, case.get("reviews", []))
        return stored

    def list_logistics(self, case_id: str) -> list[dict[str, Any]]:
        try:
            return self.database.list_logistics_nodes(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error

    @staticmethod
    def _event_sha(payload: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def create_work_order(
        self, case_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        actor = str(payload.get("actor_alias", "DEMO-OPERATOR"))
        assigned = payload.get("assigned_alias") or None
        if actor not in WORK_ORDER_ALIASES or (
            assigned is not None and assigned not in WORK_ORDER_ALIASES
        ):
            raise MVPError(
                "WORK_ORDER_ALIAS_INVALID", "只能使用预设匿名人员代号。", 422
            )
        title = str(payload.get("title", "")).strip()
        if not title or len(title) > 120:
            raise MVPError(
                "WORK_ORDER_TITLE_INVALID", "工单标题长度必须为 1-120。", 422
            )
        created_at = self.now()
        work_order_id = f"wo-{uuid.uuid4().hex}"
        order = {
            "work_order_id": work_order_id,
            "case_id": case_id,
            "title": title,
            "current_state": "OPEN",
            "assigned_alias": assigned,
            "created_at": created_at,
            "updated_at": created_at,
        }
        stable = {
            "work_order_id": work_order_id,
            "event_type": "CREATE",
            "previous_state": None,
            "current_state": "OPEN",
            "actor_alias": actor,
            "note": str(payload.get("note", "")),
            "evidence_request": "",
            "created_at": created_at,
        }
        event = {
            "event_id": f"woe-{uuid.uuid4().hex}",
            **stable,
            "payload_sha256": self._event_sha(stable),
        }
        try:
            result = self.database.create_work_order(order, event)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
        case = self.database.get_case(case_id)
        if case.get("analysis"):
            self._regenerate_report(case_id, case.get("reviews", []))
        return result

    def add_work_order_event(
        self, work_order_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            order = self.database.work_order_for(work_order_id)
        except KeyError as error:
            raise MVPError("WORK_ORDER_NOT_FOUND", "工单不存在。", 404) from error
        event_type = str(payload.get("event_type", "")).upper()
        actor = str(payload.get("actor_alias", ""))
        if event_type not in WORK_ORDER_EVENT_TYPES:
            raise MVPError("WORK_ORDER_EVENT_INVALID", "工单事件类型不受支持。", 422)
        if actor not in WORK_ORDER_ALIASES:
            raise MVPError(
                "WORK_ORDER_ALIAS_INVALID", "只能使用预设匿名人员代号。", 422
            )
        previous_state = order["current_state"]
        current_state = previous_state
        assigned = order.get("assigned_alias")
        if event_type in {"STATE_CHANGE", "RESOLVE"}:
            current_state = (
                "RESOLVED"
                if event_type == "RESOLVE"
                else str(payload.get("new_state", "")).upper()
            )
            if current_state not in WORK_ORDER_STATES:
                raise MVPError("WORK_ORDER_STATE_INVALID", "工单状态不受支持。", 422)
            if current_state not in WORK_ORDER_TRANSITIONS[previous_state]:
                raise MVPError(
                    "WORK_ORDER_TRANSITION_INVALID",
                    f"不允许 {previous_state} → {current_state}。",
                    409,
                )
        if event_type == "ASSIGN":
            assigned = payload.get("assigned_alias")
            if assigned not in WORK_ORDER_ALIASES:
                raise MVPError(
                    "WORK_ORDER_ALIAS_INVALID", "分派对象不是预设匿名代号。", 422
                )
        note = str(payload.get("note", ""))
        evidence_request = str(payload.get("evidence_request", ""))
        if event_type == "EVIDENCE_REQUEST" and not evidence_request.strip():
            raise MVPError("EVIDENCE_REQUEST_EMPTY", "补证要求不能为空。", 422)
        if len(note) > 500 or len(evidence_request) > 500:
            raise MVPError(
                "WORK_ORDER_TEXT_TOO_LONG", "工单文本不能超过 500 字符。", 422
            )
        created_at = self.now()
        stable = {
            "work_order_id": work_order_id,
            "event_type": event_type,
            "previous_state": previous_state,
            "current_state": current_state,
            "actor_alias": actor,
            "note": note,
            "evidence_request": evidence_request,
            "created_at": created_at,
        }
        event = {
            "event_id": f"woe-{uuid.uuid4().hex}",
            **stable,
            "payload_sha256": self._event_sha(stable),
        }
        result = self.database.add_work_order_event(
            work_order_id,
            event,
            state=current_state,
            assigned_alias=assigned,
            updated_at=created_at,
        )
        case = self.database.get_case(result["case_id"])
        if case.get("analysis"):
            self._regenerate_report(result["case_id"], case.get("reviews", []))
        return result

    def list_work_orders(self, case_id: str) -> list[dict[str, Any]]:
        try:
            return self.database.list_work_orders(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error

    def dashboard_summary(self) -> dict[str, Any]:
        return self.database.dashboard_summary()

    def dashboard_trends(self) -> dict[str, Any]:
        return self.database.dashboard_trends()

    def analyze_video(
        self,
        content: bytes,
        filename: str,
        content_type: str | None,
        sample_interval_frames: int,
        top_k: int,
    ) -> dict[str, Any]:
        if not content:
            raise MVPError("VIDEO_EMPTY", "视频内容为空。", 422)
        if len(content) > int(self.config.get("max_video_upload_bytes", 104_857_600)):
            raise MVPError("VIDEO_TOO_LARGE", "视频超过允许的最大文件大小。", 413)
        if Path(filename or "").suffix.lower() != ".mp4":
            raise MVPError("VIDEO_EXTENSION_INVALID", "仅支持 MP4。", 422)
        if content_type not in {"video/mp4", "application/octet-stream"}:
            raise MVPError("VIDEO_MIME_INVALID", "视频 MIME 类型不受支持。", 422)
        analysis_id = f"video-{uuid.uuid4().hex}"
        root = self.runtime_root / "video" / analysis_id
        root.mkdir(parents=True, exist_ok=False)
        source = root / "source.mp4"
        source.write_bytes(content)
        try:
            result = screen_video(
                source,
                self.detector,
                root / "keyframes",
                sample_interval_frames=sample_interval_frames,
                top_k=top_k,
            )
        except VideoScreeningError as error:
            raise MVPError("VIDEO_DECODE_FAILED", str(error), 422) from error
        result.update(
            {
                "analysis_id": analysis_id,
                "created_at": self.now(),
                "model_version": self.registry.model_version,
                "model_sha256": self.registry.data["sha256"],
            }
        )
        for keyframe in result["top_abnormal_keyframes"]:
            keyframe["url"] = (
                f"/api/video/keyframes/{analysis_id}/{keyframe['filename']}"
            )
        (root / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self.database.store_video_analysis(
            analysis_id,
            result["created_at"],
            result["video_metadata"]["source_sha256"],
            result,
        )
        return result

    def _regenerate_report(
        self, case_id: str, reviews: list[dict[str, Any]]
    ) -> dict[str, str]:
        case = self.database.get_case(case_id)
        node_results = [item["result"] for item in case["surface_analysis"]]
        pair_results = [item["result"] for item in case["pair_changes"]]
        analysis = case["analysis"]["result"]
        risk = self.risk_engine.assess(
            analysis, pair_results, case.get("nodes", []), reviews
        )
        self.database.store_risk(case_id, self.now(), risk)
        # Reload so the current work-order/logistics/risk state is reflected.
        case = self.database.get_case(case_id)
        report = generate_evidence_report(
            case,
            node_results,
            pair_results,
            analysis,
            self.registry.public_info(),
            self.runtime_root / "reports" / case_id,
            node_summaries=analysis.get("node_fingerprint_summaries", []),
            reviews=reviews,
            report_revision=len(reviews),
            logistics_nodes=case.get("logistics_nodes", []),
            risk=risk,
            work_orders=case.get("work_orders", []),
            report_version=(
                "evidence-report-v1.0"
                if "rc-v1.0" in self.config["pipeline_version"]
                else None
            ),
        )
        self.database.update_report(case_id, self.now(), report)
        return report

    def list_reviews(self, case_id: str) -> list[dict[str, Any]]:
        try:
            return self.database.list_reviews(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error
