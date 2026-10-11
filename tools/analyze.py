"""업무일지를 분석해 요약(summary.json)을 만든다. 분석 로직은 백엔드와 같은 코드
(backend/app/services/summary.py)를 쓴다. 이 요약이 AI 시스템 프롬프트에 들어간다.

실행: py tools/analyze.py  →  data/summary.json, data/prompt_preview.txt
"""
import csv, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "backend"))
from app.services.summary import summarize, to_prompt_text  # noqa: E402


def load_csv(name):
    with open(DATA / name, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    s = summarize(load_csv("worklog.csv"), load_csv("backlog.csv"))
    json.dump(s, open(DATA / "summary.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    (DATA / "prompt_preview.txt").write_text(to_prompt_text(s), encoding="utf-8")
    print(to_prompt_text(s))
