from fastapi import APIRouter, HTTPException

from ..schemas import Conversation, ConversationCreate, ConversationSummary
from ..services import conversations as svc

router = APIRouter(prefix="/api/conversations", tags=["대화 기록"])


@router.post("", response_model=Conversation, status_code=201, summary="대화 저장")
def create_conversation(body: ConversationCreate):
    return svc.create_conversation([m.model_dump() for m in body.messages], body.title)


@router.get("", response_model=list[ConversationSummary],
            summary="대화 목록 (최근 순, messages 제외 — 전체 메시지는 /{id})")
def list_conversations():
    return svc.list_conversations()


@router.get("/{conv_id}", response_model=Conversation, summary="대화 불러오기 (전체 메시지)")
def get_conversation(conv_id: str):
    doc = svc.get_conversation(conv_id)
    if not doc:
        raise HTTPException(404, "대화를 찾을 수 없습니다")
    return doc


@router.delete("/{conv_id}", status_code=204, summary="대화 삭제")
def delete_conversation(conv_id: str):
    if not svc.delete_conversation(conv_id):
        raise HTTPException(404, "대화를 찾을 수 없습니다")
