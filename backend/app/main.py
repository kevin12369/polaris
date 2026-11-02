"""FastAPI 应用入口。"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import APP_NAME, APP_VERSION, CORS_ORIGINS, LLM_ENABLED, LLM_MODEL
from .db import init_db
from .migrations import run_migrations
from .routers import assistant, auth, dashboard, kb, settings, tickets


def create_app() -> FastAPI:
    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description="Polaris 北极星 —— 给中小企业的轻量级工单系统：工单 / 知识库 / AI 排障助手 / 仪表盘",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def _startup() -> None:
        init_db()
        # 补齐新增字段（SQLite 的 create_all 不会改已有表）
        applied = run_migrations()
        if applied:
            print(f"[migrate] 已补齐字段: {', '.join(applied)}")

    @app.get("/api/health", tags=["system"])
    def health():
        return {
            "status": "ok",
            "app": APP_NAME,
            "version": APP_VERSION,
            "llm_enabled": LLM_ENABLED,
            "llm_model": LLM_MODEL if LLM_ENABLED else None,
        }

    @app.get("/", include_in_schema=False)
    def root():
        return JSONResponse(
            {
                "app": APP_NAME,
                "version": APP_VERSION,
                "docs": "/docs",
                "modules": ["工单", "知识库", "AI 排障助手", "仪表盘"],
            }
        )

    app.include_router(auth.router)
    app.include_router(settings.router)
    app.include_router(tickets.router)
    app.include_router(kb.router)
    app.include_router(assistant.router)
    app.include_router(dashboard.router)

    return app


app = create_app()
