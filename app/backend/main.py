"""FastAPI entrypoint for the single-address competition MVP."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .schemas import CaseCreate, ReviewCreate, WorkOrderCreate, WorkOrderEventCreate
from .services import MVPError, MVPService

LOGGER = logging.getLogger("jianzheng.mvp")


def error_response(code: str, message: str, details: dict[str, Any], status: int):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app(
    config_path: str | Path = "configs/runtime/competition-rc-v1.0.json",
    service: MVPService | None = None,
) -> FastAPI:
    active_service = service or MVPService(config_path)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        disabled = os.environ.get("JIANZHENG_DISABLE_AUTO_WARMUP") == "1"
        if active_service.config.get("auto_warmup", False) and not disabled:
            result = active_service.warmup()
            if not result.get("loaded"):
                LOGGER.warning("Detector warmup fell back to lazy load: %s", result)
        yield

    app = FastAPI(
        title="件证 Competition Release Candidate",
        version="1.0.0-rc.1",
        lifespan=lifespan,
    )
    app.state.service = active_service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.service.config["cors_origins"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(MVPError)
    async def handle_mvp_error(_request, error: MVPError):
        return error_response(
            error.code, error.message, error.details, error.status_code
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request, error: RequestValidationError):
        return error_response(
            "REQUEST_INVALID",
            "请求参数不符合接口约束。",
            {"errors": error.errors()},
            422,
        )

    @app.exception_handler(HTTPException)
    async def handle_http(_request, error: HTTPException):
        return error_response("HTTP_ERROR", str(error.detail), {}, error.status_code)

    @app.exception_handler(Exception)
    async def handle_unexpected(_request, error: Exception):
        LOGGER.exception("Unhandled MVP error", exc_info=error)
        return error_response("INTERNAL_ERROR", "服务发生内部错误。", {}, 500)

    @app.get("/api/health")
    def health():
        return app.state.service.health()

    @app.get("/api/model/info")
    def model_info():
        return app.state.service.registry.public_info()

    @app.post("/api/model/warmup")
    def model_warmup():
        return app.state.service.warmup()

    @app.post("/api/detect")
    async def detect(file: Annotated[UploadFile, File(...)]):
        content = await file.read()
        return app.state.service.detect_upload(
            content, file.filename or "", file.content_type
        )

    @app.post("/api/change")
    async def change(
        reference: Annotated[UploadFile, File(...)],
        current: Annotated[UploadFile, File(...)],
    ):
        return app.state.service.change_upload(
            (
                await reference.read(),
                reference.filename or "",
                reference.content_type,
            ),
            (await current.read(), current.filename or "", current.content_type),
        )

    @app.post("/api/cases")
    def create_case(payload: CaseCreate):
        return app.state.service.create_case(payload.case_name, payload.notes)

    @app.post("/api/cases/{case_id}/nodes")
    async def add_node(
        case_id: str,
        node_id: Annotated[str, Form(...)],
        surface: Annotated[str, Form()] = "front",
        capture_time: Annotated[str | None, Form()] = None,
        file: Annotated[UploadFile, File(...)] = None,
    ):
        if file is None:
            raise MVPError("IMAGE_REQUIRED", "必须上传图片。")
        return app.state.service.add_node(
            case_id,
            node_id,
            surface,
            await file.read(),
            file.filename or "",
            file.content_type,
            capture_time,
        )

    @app.post("/api/cases/{case_id}/analyze")
    def analyze(case_id: str):
        return app.state.service.analyze_case(case_id)

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: str):
        try:
            return app.state.service.database.get_case(case_id)
        except KeyError as error:
            raise MVPError("CASE_NOT_FOUND", "案例不存在。", 404) from error

    @app.get("/api/cases/{case_id}/report")
    def get_report(case_id: str):
        try:
            report = app.state.service.database.report_for(case_id)
        except KeyError as error:
            raise MVPError("REPORT_NOT_FOUND", "报告尚不存在。", 404) from error
        path = Path(report["html_path"])
        if not path.is_file():
            raise MVPError("REPORT_FILE_MISSING", "报告文件不存在。", 404)
        return FileResponse(path, media_type="text/html; charset=utf-8")

    @app.post("/api/cases/{case_id}/reviews")
    def create_review(case_id: str, payload: ReviewCreate):
        return app.state.service.add_review(case_id, payload.model_dump())

    @app.get("/api/cases/{case_id}/reviews")
    def list_reviews(case_id: str):
        return {"reviews": app.state.service.list_reviews(case_id)}

    @app.get("/api/cases/{case_id}/risk")
    def case_risk(case_id: str):
        return app.state.service.risk_for(case_id)

    @app.post("/api/cases/{case_id}/logistics/import")
    async def import_logistics(
        case_id: str,
        data_format: Annotated[str, Form(...)],
        file: Annotated[UploadFile, File(...)],
    ):
        nodes = app.state.service.import_logistics(
            case_id, await file.read(), data_format
        )
        return {"case_id": case_id, "format": data_format.lower(), "nodes": nodes}

    @app.get("/api/cases/{case_id}/logistics")
    def list_logistics(case_id: str):
        return {"case_id": case_id, "nodes": app.state.service.list_logistics(case_id)}

    @app.post("/api/cases/{case_id}/work-orders")
    def create_work_order(case_id: str, payload: WorkOrderCreate):
        return app.state.service.create_work_order(case_id, payload.model_dump())

    @app.get("/api/cases/{case_id}/work-orders")
    def list_work_orders(case_id: str):
        return {"work_orders": app.state.service.list_work_orders(case_id)}

    @app.post("/api/work-orders/{work_order_id}/events")
    def create_work_order_event(work_order_id: str, payload: WorkOrderEventCreate):
        return app.state.service.add_work_order_event(
            work_order_id, payload.model_dump()
        )

    @app.get("/api/dashboard/summary")
    def dashboard_summary():
        return app.state.service.dashboard_summary()

    @app.get("/api/dashboard/trends")
    def dashboard_trends():
        return app.state.service.dashboard_trends()

    @app.post("/api/video/analyze")
    async def analyze_video(
        file: Annotated[UploadFile, File(...)],
        sample_interval_frames: Annotated[int, Form()] = 5,
        top_k: Annotated[int, Form()] = 5,
    ):
        return app.state.service.analyze_video(
            await file.read(),
            file.filename or "",
            file.content_type,
            sample_interval_frames,
            top_k,
        )

    @app.get("/api/video/keyframes/{analysis_id}/{filename}")
    def video_keyframe(analysis_id: str, filename: str):
        if not analysis_id.startswith("video-") or Path(filename).name != filename:
            raise MVPError("VIDEO_KEYFRAME_INVALID", "关键帧路径无效。", 404)
        root = (
            app.state.service.runtime_root / "video" / analysis_id / "keyframes"
        ).resolve()
        path = (root / filename).resolve()
        if path.parent != root or not path.is_file() or path.suffix.lower() != ".jpg":
            raise MVPError("VIDEO_KEYFRAME_NOT_FOUND", "关键帧不存在。", 404)
        return FileResponse(path, media_type="image/jpeg")

    @app.get("/api/cases")
    def list_cases():
        return {"cases": app.state.service.database.list_cases()}

    frontend_dist = Path("frontend/dist")
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


app = create_app()
