"""API 테스트. 임시 로컬 저장소를 쓰고 GPT 호출은 가짜로 바꾼다 (키·비용 없이 실행).

실행 (backend 폴더에서):  python -m pytest -q
"""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import db  # noqa: E402
from app.services import ai  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    store = db.JsonStore(tmp_path)
    store.create("data", {"date": "2026-09-01", "value": 60, "memo": "웹사이트 시안", "project": "웹사이트",
                          "category": "AXOLVE", "source": "측정"}, doc_id="w001")
    store.create("tasks", {"project": "웹사이트", "task": "모바일 점검", "status": "NOW",
                           "as_of": "2026-09-01", "source": "테스트"}, doc_id="t01")
    monkeypatch.setattr(db, "_store", store)
    return TestClient(app)


def test_data_crud(client):
    r = client.post("/api/data", json={"date": "2026-09-02", "value": 30, "memo": "릴스 1화", "project": "인스타 릴스"})
    assert r.status_code == 201
    new_id = r.json()["id"]

    rows = client.get("/api/data").json()
    assert [x["id"] for x in rows] == [new_id, "w001"]  # 최신순

    r = client.put(f"/api/data/{new_id}", json={"value": 45})
    assert r.status_code == 200 and r.json()["value"] == 45 and r.json()["memo"] == "릴스 1화"

    assert client.delete(f"/api/data/{new_id}").status_code == 204
    assert client.delete(f"/api/data/{new_id}").status_code == 404
    assert len(client.get("/api/data").json()) == 1


@pytest.mark.parametrize("body", [
    {"date": "2026-09-02", "value": 0, "memo": "x"},                 # 0분
    {"date": "2026-09-02", "value": 2000, "memo": "x"},              # 하루 초과
    {"date": "2026-09-02", "value": 30, "memo": "   "},              # 빈 메모
    {"date": "2026-13-40", "value": 30, "memo": "x"},                # 잘못된 날짜
    {"date": (date.today() + timedelta(days=1)).isoformat(), "value": 30, "memo": "x"},  # 미래
    {"date": "2026-09-02", "value": 30, "memo": "x", "category": "없는분류"},
])
def test_data_validation(client, body):
    assert client.post("/api/data", json=body).status_code == 422


def test_summary_route_not_taken_as_id(client):
    s = client.get("/api/data/summary").json()
    assert s["count"] == 1 and s["metrics"]["total_hours"] == 1.0
    assert s["open_tasks"]["now"] == ["[웹사이트] 모바일 점검"]


def test_tasks(client):
    assert client.put("/api/tasks/t01", json={"status": "DONE"}).json()["status"] == "DONE"
    assert client.get("/api/data/summary").json()["open_tasks"]["count"] == 0
    assert client.put("/api/tasks/t01", json={"status": "끝"}).status_code == 422


def test_conversations(client):
    r = client.post("/api/conversations", json={"messages": [
        {"role": "user", "content": "오늘 뭐 해?"}, {"role": "assistant", "content": "모바일 점검이요"}]})
    assert r.status_code == 201
    cid = r.json()["id"]
    lst = client.get("/api/conversations").json()
    assert lst[0]["id"] == cid and lst[0]["message_count"] == 2 and "messages" not in lst[0]
    assert len(client.get(f"/api/conversations/{cid}").json()["messages"]) == 2
    assert client.delete(f"/api/conversations/{cid}").status_code == 204
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_chat_injects_summary_and_saves(client, monkeypatch):
    seen = {}

    def fake_ask(summary, history, message):
        seen["prompt"] = ai.build_system_prompt(summary)
        seen["history"] = history
        return "웹사이트 모바일 점검부터 해요."

    monkeypatch.setattr(ai, "ask", fake_ask)
    r = client.post("/api/chat", json={"message": "뭐부터 할까?"})
    assert r.status_code == 200
    cid = r.json()["conversation_id"]
    assert "웹사이트: 1.0h" in seen["prompt"] and "모바일 점검" in seen["prompt"]

    r = client.post("/api/chat", json={"message": "그다음은?", "conversation_id": cid})
    assert len(seen["history"]) == 2  # 이전 대화가 함께 전달됨
    assert client.get(f"/api/conversations/{cid}").json()["message_count"] == 4


def test_chat_without_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(ai.config, "OPENAI_API_KEY", "")
    r = client.post("/api/chat", json={"message": "안녕"})
    assert r.status_code == 503
    assert client.get("/api/conversations").json() == []  # 실패한 대화는 저장 안 함
