"""ADHD를 위한 업무 비서 — FastAPI 진입점.

로컬 실행:  uvicorn main:app --reload   →  http://127.0.0.1:8000/docs
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.db import get_store
from app.routers import chat, conversations, data

app = FastAPI(
    title="ADHD를 위한 업무 비서 API",
    description="여러 일을 동시에 벌이는 사람을 위한 업무 비서. 업무일지(시계열)를 분석한 요약을 GPT 시스템 프롬프트에 주입해 내 기록 기준으로 답한다.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(data.router)
app.include_router(conversations.router)
app.include_router(chat.router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    # 내부 오류 내용(키·경로 등)은 밖으로 내보내지 않는다
    return JSONResponse(status_code=500, content={"detail": "서버 오류가 발생했습니다"})


@app.get("/", tags=["상태"], summary="서비스 안내")
def root():
    return {"service": "ADHD를 위한 업무 비서", "docs": "/docs", "health": "/health"}


@app.get("/health", tags=["상태"], summary="헬스체크 (콜드스타트 깨우기용)")
def health():
    k = config.OPENAI_API_KEY
    return {
        "status": "ok",
        "store": get_store().kind,
        "ai": bool(k),
        "version": os.getenv("RENDER_GIT_COMMIT", "local")[:7],
        # 키 값은 내보내지 않고 형식만 점검한다
        "ai_key_format": {"length": len(k), "prefix_ok": k.startswith("sk-"),
                          "ascii_only": k.isascii(), "inner_space": any(c.isspace() for c in k)},
    }
