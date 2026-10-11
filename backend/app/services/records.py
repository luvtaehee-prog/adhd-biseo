"""업무일지·할 일 비즈니스 로직. 라우터는 이 함수들만 부른다."""
from typing import Optional

from ..db import get_store
from ..schemas import RecordCreate, RecordUpdate
from . import summary as summary_svc

DATA, TASKS = "data", "tasks"


def list_records(project: Optional[str] = None, start: Optional[str] = None, end: Optional[str] = None) -> list[dict]:
    rows = get_store().list(DATA)
    if project:
        rows = [r for r in rows if r.get("project") == project]
    if start:
        rows = [r for r in rows if r["date"] >= start]
    if end:
        rows = [r for r in rows if r["date"] <= end]
    return sorted(rows, key=lambda r: (r["date"], r["id"]), reverse=True)


def create_record(body: RecordCreate) -> dict:
    data = body.model_dump()
    data["date"] = body.date.isoformat()
    return get_store().create(DATA, data)


def update_record(record_id: str, body: RecordUpdate) -> Optional[dict]:
    data = body.model_dump(exclude_none=True)
    if "date" in data:
        data["date"] = data["date"].isoformat()
    if not data:
        return get_store().get(DATA, record_id)
    return get_store().update(DATA, record_id, data)


def delete_record(record_id: str) -> bool:
    return get_store().delete(DATA, record_id)


def list_tasks() -> list[dict]:
    order = {"NOW": 0, "NEXT": 1, "WAITING": 2, "DONE": 3}
    return sorted(get_store().list(TASKS), key=lambda t: (order.get(t["status"], 9), t["id"]))


def update_task(task_id: str, status: str) -> Optional[dict]:
    return get_store().update(TASKS, task_id, {"status": status})


def build_summary() -> dict:
    store = get_store()
    return summary_svc.summarize(store.list(DATA), store.list(TASKS))
