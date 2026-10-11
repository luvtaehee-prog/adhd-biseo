"""저장소. Firestore 키가 있으면 Firestore, 없으면 로컬 JSON 파일(개발·테스트용)을 쓴다.

컬렉션
- data          : 업무일지 (date, value, memo, project, category, source)
- tasks         : 할 일 (project, task, status, as_of, source)
- conversations : 대화 (title, created_at, updated_at, messages[])
"""
import json
import threading
import uuid
from pathlib import Path
from typing import Optional

from . import config


class Store:
    kind = "base"

    def list(self, col: str) -> list[dict]: ...
    def get(self, col: str, doc_id: str) -> Optional[dict]: ...
    def create(self, col: str, data: dict, doc_id: Optional[str] = None) -> dict: ...
    def update(self, col: str, doc_id: str, data: dict) -> Optional[dict]: ...
    def delete(self, col: str, doc_id: str) -> bool: ...


class FirestoreStore(Store):
    kind = "firestore"

    def __init__(self):
        import firebase_admin
        from firebase_admin import credentials, firestore

        if config.FIREBASE_SERVICE_ACCOUNT_JSON:
            cred = credentials.Certificate(json.loads(config.FIREBASE_SERVICE_ACCOUNT_JSON))
        else:
            cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def list(self, col):
        return [{"id": d.id, **d.to_dict()} for d in self.db.collection(col).stream()]

    def get(self, col, doc_id):
        snap = self.db.collection(col).document(doc_id).get()
        return {"id": snap.id, **snap.to_dict()} if snap.exists else None

    def create(self, col, data, doc_id=None):
        ref = self.db.collection(col).document(doc_id) if doc_id else self.db.collection(col).document()
        ref.set(data)
        return {"id": ref.id, **data}

    def update(self, col, doc_id, data):
        ref = self.db.collection(col).document(doc_id)
        if not ref.get().exists:
            return None
        ref.update(data)
        return self.get(col, doc_id)

    def delete(self, col, doc_id):
        ref = self.db.collection(col).document(doc_id)
        if not ref.get().exists:
            return False
        ref.delete()
        return True


class JsonStore(Store):
    """Firestore 키 없이 로컬에서 돌려볼 때 쓰는 파일 저장소."""
    kind = "local-json"

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, col):
        return self.root / f"{col}.json"

    def _read(self, col) -> dict:
        p = self._path(col)
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def _write(self, col, docs: dict):
        self._path(col).write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")

    def list(self, col):
        return [{"id": k, **v} for k, v in self._read(col).items()]

    def get(self, col, doc_id):
        v = self._read(col).get(doc_id)
        return {"id": doc_id, **v} if v is not None else None

    def create(self, col, data, doc_id=None):
        with self.lock:
            docs = self._read(col)
            doc_id = doc_id or uuid.uuid4().hex[:20]
            docs[doc_id] = data
            self._write(col, docs)
        return {"id": doc_id, **data}

    def update(self, col, doc_id, data):
        with self.lock:
            docs = self._read(col)
            if doc_id not in docs:
                return None
            docs[doc_id].update(data)
            self._write(col, docs)
        return {"id": doc_id, **docs[doc_id]}

    def delete(self, col, doc_id):
        with self.lock:
            docs = self._read(col)
            if doc_id not in docs:
                return False
            del docs[doc_id]
            self._write(col, docs)
        return True


_store: Optional[Store] = None


def get_store() -> Store:
    global _store
    if _store is None:
        if config.FIREBASE_SERVICE_ACCOUNT_JSON or config.FIREBASE_CREDENTIALS_PATH:
            _store = FirestoreStore()
        else:
            _store = JsonStore(config.BACKEND_DIR / ".localdb")
    return _store
