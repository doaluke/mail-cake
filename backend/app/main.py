"""
MailCake - FastAPI 主程式
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api.v1 import auth, emails, settings as settings_router, topics

settings_config = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 啟動時建立資料表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 關閉時清理
    await engine.dispose()


app = FastAPI(
    title="MailCake API",
    description="AI-powered email summarization service",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings_config.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(emails.router, prefix="/api/v1", tags=["emails"])
app.include_router(settings_router.router, prefix="/api/v1", tags=["settings"])
app.include_router(topics.router, prefix="/api/v1", tags=["topics"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mailcake-api"}


@app.get("/")
async def root():
    return {
        "name": "MailCake API",
        "version": "0.1.0",
        "docs": "/docs",
    }
