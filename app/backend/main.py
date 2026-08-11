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

from .schemas import CaseCreate, ReviewCreate
from .services import MVPError, MVPService

LOGGER = logging.getLogger("jianzheng.mvp")


def error_response(code: str, message: str, details: dict[str, Any], status: int):
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


def create_app(
    config_path: str | Path = "configs/runtime/mvp-v0.2.json",
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
        title="件证 Competition MVP",
        version="0.2.0",
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

    @app.get("/api/cases")
    def list_cases():
        return {"cases": app.state.service.database.list_cases()}

    frontend_dist = Path("frontend/dist")
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
    return app


app = create_app()
