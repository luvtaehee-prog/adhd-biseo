"""대화 기록 저장·조회."""
from datetime import datetime, timezone
from typing import Optional

from ..db import get_store

COL = "conversations"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _brief(doc: dict) -> dict:
    return {"id": doc["id"], "title": doc["title"], "created_at": doc["created_at"],
            "updated_at": doc["updated_at"], "message_count": len(doc.get("messages", []))}


def make_title(text: str) -> str:
    text = " ".join(text.split())
    return text[:30] + ("…" if len(text) > 30 else "")


def list_conversations() -> list[dict]:
    docs = get_store().list(COL)
    return [_brief(d) for d in sorted(docs, key=lambda d: d["updated_at"], reverse=True)]


def get_conversation(conv_id: str) -> Optional[dict]:
    doc = get_store().get(COL, conv_id)
    return {**_brief(doc), "messages": doc.get("messages", [])} if doc else None


def create_conversation(messages: list[dict], title: Optional[str] = None) -> dict:
    now = _now()
    first_user = next((m["content"] for m in messages if m["role"] == "user"), messages[0]["content"])
    doc = get_store().create(COL, {"title": title or make_title(first_user), "created_at": now,
                                   "updated_at": now, "messages": messages})
    return {**_brief(doc), "messages": doc["messages"]}


def append_messages(conv_id: str, new_messages: list[dict]) -> Optional[dict]:
    doc = get_store().get(COL, conv_id)
    if not doc:
        return None
    messages = doc.get("messages", []) + new_messages
    get_store().update(COL, conv_id, {"messages": messages, "updated_at": _now()})
    return get_conversation(conv_id)


def delete_conversation(conv_id: str) -> bool:
    return get_store().delete(COL, conv_id)
