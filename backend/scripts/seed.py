"""data/worklog.json · data/backlog.csv 를 저장소(Firestore 또는 로컬 JSON)에 넣는다.

같은 id(w001, t01 …)로 덮어쓰므로 여러 번 실행해도 중복되지 않는다.
실행 (backend 폴더에서):  python -m scripts.seed
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.db import get_store  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def main():
    store = get_store()
    records = json.loads((DATA_DIR / "worklog.json").read_text(encoding="utf-8"))
    for r in records:
        doc_id = r.pop("id")
        store.create("data", r, doc_id=doc_id)
    with open(DATA_DIR / "backlog.csv", encoding="utf-8-sig") as f:
        tasks = list(csv.DictReader(f))
    for t in tasks:
        doc_id = t.pop("id")
        store.create("tasks", t, doc_id=doc_id)
    print(f"[{store.kind}] data {len(records)}건, tasks {len(tasks)}건 저장")


if __name__ == "__main__":
    main()
