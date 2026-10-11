from fastapi import APIRouter, HTTPException

from .. import config
from ..schemas import ChatRequest, ChatResponse
from ..services import ai, conversations, records

router = APIRouter(prefix="/api", tags=["AI 채팅"])


@router.post("/chat", response_model=ChatResponse, summary="AI 대화 (요약 주입 → GPT → 자동 저장)")
def chat(body: ChatRequest):
    history = []
    if body.conversation_id:
        conv = conversations.get_conversation(body.conversation_id)
        if not conv:
            raise HTTPException(404, "대화를 찾을 수 없습니다")
        history = conv["messages"]

    # 1) 데이터 요약 조회  2) 시스템 프롬프트에 주입  3) GPT 호출
    summary = records.build_summary()
    try:
        reply = ai.ask(summary, history, body.message)
    except ai.AIUnavailable as e:
        raise HTTPException(503, str(e))

    # 4) 대화 자동 저장
    new = [{"role": "user", "content": body.message}, {"role": "assistant", "content": reply}]
    if body.conversation_id:
        conv_id = body.conversation_id
        conversations.append_messages(conv_id, new)
    else:
        conv_id = conversations.create_conversation(new)["id"]

    return ChatResponse(
        conversation_id=conv_id,
        reply=reply,
        model=config.OPENAI_MODEL,
        context={"period": summary["period"], "count": summary["count"],
                 "trend": (summary["trend"] or {}).get("label"),
                 "open_tasks": summary["open_tasks"]["count"]},
    )
