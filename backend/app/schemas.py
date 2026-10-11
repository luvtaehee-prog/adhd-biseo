"""요청·응답 모델. Pydantic이 잘못된 입력을 422 오류로 막는다."""
from datetime import date as Date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Category = Literal["AXOLVE", "교육콘텐츠", "학습", "개인"]
Source = Literal["측정", "추정", "문서", "직접입력"]
TaskStatus = Literal["NOW", "NEXT", "WAITING", "DONE"]


# ── 업무일지 (data) ──────────────────────────────────────────
class RecordCreate(BaseModel):
    date: Date = Field(description="작업 날짜 (YYYY-MM-DD)")
    value: int = Field(ge=1, le=1440, description="작업 시간(분), 하루 최대 1440분")
    memo: str = Field(min_length=1, max_length=200, description="한 일")
    project: str = Field(default="기타", min_length=1, max_length=30)
    category: Category = "AXOLVE"
    source: Source = "직접입력"

    @field_validator("date")
    @classmethod
    def not_future(cls, v: Date) -> Date:
        if v > Date.today():
            raise ValueError("미래 날짜는 기록할 수 없습니다")
        return v

    @field_validator("memo", "project")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("빈 문자열은 안 됩니다")
        return v


class RecordUpdate(BaseModel):
    """바꿀 필드만 보낸다."""
    date: Optional[Date] = None
    value: Optional[int] = Field(default=None, ge=1, le=1440)
    memo: Optional[str] = Field(default=None, min_length=1, max_length=200)
    project: Optional[str] = Field(default=None, min_length=1, max_length=30)
    category: Optional[Category] = None

    @field_validator("date")
    @classmethod
    def not_future(cls, v):
        if v and v > Date.today():
            raise ValueError("미래 날짜는 기록할 수 없습니다")
        return v


class Record(BaseModel):
    id: str
    date: str
    value: int
    memo: str
    project: str
    category: str
    source: str


# ── 할 일 (tasks) ────────────────────────────────────────────
class Task(BaseModel):
    id: str
    project: str
    task: str
    status: TaskStatus
    as_of: str
    source: str


class TaskUpdate(BaseModel):
    status: TaskStatus


# ── 대화 (conversations) ─────────────────────────────────────
class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default=None, max_length=60)
    messages: list[Message] = Field(min_length=1)


class ConversationSummary(BaseModel):
    """목록용: messages는 넣지 않는다. 전체 메시지는 GET /api/conversations/{id}."""
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class Conversation(ConversationSummary):
    messages: list[Message]


# ── 채팅 ────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(default=None, description="이어서 대화할 때만 보낸다")

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("메시지를 입력하세요")
        return v


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    model: str
    context: dict = Field(description="답변에 쓴 요약 (기간·건수·추세)")
