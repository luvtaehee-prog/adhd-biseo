from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..schemas import Record, RecordCreate, RecordUpdate, Task, TaskUpdate
from ..services import records as svc

router = APIRouter(prefix="/api", tags=["업무일지 · 할 일"])


# /summary 는 /{record_id} 보다 먼저 선언해야 id로 잘못 잡히지 않는다
@router.get("/data/summary", summary="데이터 요약 (프롬프트 주입용)")
def get_summary():
    return svc.build_summary()


@router.get("/data", response_model=list[Record], summary="업무일지 목록 (최신순)")
def list_data(
    project: Optional[str] = Query(None, description="프로젝트 이름으로 거르기"),
    start: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="시작일 YYYY-MM-DD"),
    end: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="종료일 YYYY-MM-DD"),
):
    return svc.list_records(project, start, end)


@router.post("/data", response_model=Record, status_code=201, summary="업무 기록 추가")
def create_data(body: RecordCreate):
    return svc.create_record(body)


@router.put("/data/{record_id}", response_model=Record, summary="업무 기록 수정 (바꿀 필드만)")
def update_data(record_id: str, body: RecordUpdate):
    doc = svc.update_record(record_id, body)
    if not doc:
        raise HTTPException(404, "기록을 찾을 수 없습니다")
    return doc


@router.delete("/data/{record_id}", status_code=204, summary="업무 기록 삭제")
def delete_data(record_id: str):
    if not svc.delete_record(record_id):
        raise HTTPException(404, "기록을 찾을 수 없습니다")


@router.get("/tasks", response_model=list[Task], summary="할 일 목록 (NOW → NEXT → WAITING → DONE)")
def list_tasks():
    return svc.list_tasks()


@router.put("/tasks/{task_id}", response_model=Task, summary="할 일 상태 변경 (완료 체크 등)")
def update_task(task_id: str, body: TaskUpdate):
    doc = svc.update_task(task_id, body.status)
    if not doc:
        raise HTTPException(404, "할 일을 찾을 수 없습니다")
    return doc
