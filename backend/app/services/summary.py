"""업무일지 시계열 분석 → 요약. 이 요약이 AI 시스템 프롬프트에 들어간다(컨텍스트 주입)."""
import statistics
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

STALE_DAYS = 30   # 이 기간 동안 손대지 않은 프로젝트 = 멈춤
TREND_DAYS = 14   # 최근 N일 vs 그 전 N일
RECENT_N = 10     # 프롬프트에 넣을 최근 기록 수


def _trend(rows, today):
    cur = sum(r["value"] for r in rows if today - timedelta(TREND_DAYS) < r["_d"] <= today)
    prev = sum(r["value"] for r in rows
               if today - timedelta(TREND_DAYS * 2) < r["_d"] <= today - timedelta(TREND_DAYS))
    if prev == 0:
        return {"label": "증가" if cur else "유지", "recent_min": cur, "previous_min": prev, "change_pct": None}
    pct = round((cur - prev) / prev * 100)
    label = "증가" if pct >= 10 else "감소" if pct <= -10 else "유지"
    return {"label": label, "recent_min": cur, "previous_min": prev, "change_pct": pct}


def summarize(records: list[dict], tasks: list[dict], today: Optional[date] = None) -> dict:
    today = today or date.today()
    open_tasks = [t for t in tasks if t.get("status") != "DONE"]
    task_view = {
        "count": len(open_tasks),
        "now": [f"[{t['project']}] {t['task']}" for t in open_tasks if t["status"] == "NOW"],
        "next": [f"[{t['project']}] {t['task']}" for t in open_tasks if t["status"] == "NEXT"],
        "waiting": [f"[{t['project']}] {t['task']}" for t in open_tasks if t["status"] == "WAITING"],
    }
    if not records:
        return {"period": "기록 없음", "count": 0, "active_days": 0, "metrics": {}, "trend": None,
                "by_category_hours": {}, "by_month_hours": {}, "by_project": [], "recent": [],
                "open_tasks": task_view, "as_of": today.isoformat()}

    rows = sorted(({**r, "_d": date.fromisoformat(r["date"]), "value": int(r["value"])} for r in records),
                  key=lambda r: (r["_d"], r.get("id", "")))
    vals = [r["value"] for r in rows]
    total = sum(vals)

    daily = defaultdict(int)
    by_project = defaultdict(lambda: {"minutes": 0, "count": 0, "last": None, "last_memo": ""})
    by_category, by_month = defaultdict(int), defaultdict(int)
    for r in rows:
        daily[r["_d"]] += r["value"]
        p = by_project[r.get("project", "기타")]
        p["minutes"] += r["value"]
        p["count"] += 1
        p["last"], p["last_memo"] = r["date"], r["memo"]
        by_category[r.get("category", "AXOLVE")] += r["value"]
        by_month[r["date"][:7]] += r["value"]

    best_day = max(daily, key=daily.get)
    top = max(rows, key=lambda r: r["value"])
    projects = sorted(by_project.items(), key=lambda kv: -kv[1]["minutes"])

    return {
        "period": f"{rows[0]['date']} ~ {rows[-1]['date']}",
        "count": len(rows),
        "active_days": len(daily),
        "metrics": {
            "total_hours": round(total / 60, 1),
            "average_min": round(statistics.mean(vals)),
            "median_min": statistics.median(vals),
            "max_min": top["value"],
            "max_record": f"{top['date']} {top['memo']}",
            "min_min": min(vals),
            "average_min_per_active_day": round(total / len(daily)),
            "best_day": f"{best_day} ({daily[best_day]}분)",
        },
        "trend": _trend(rows, today),
        "by_category_hours": {k: round(v / 60, 1) for k, v in sorted(by_category.items(), key=lambda kv: -kv[1])},
        "by_month_hours": {k: round(v / 60, 1) for k, v in sorted(by_month.items())},
        "by_project": [
            {"project": k, "hours": round(v["minutes"] / 60, 1), "records": v["count"],
             "last_date": v["last"], "last_work": v["last_memo"],
             "days_since": (today - date.fromisoformat(v["last"])).days,
             "stale": (today - date.fromisoformat(v["last"])).days > STALE_DAYS}
            for k, v in projects
        ],
        "recent": [f"{r['date']} [{r.get('project', '기타')}] {r['memo']} ({r['value']}분)" for r in rows[-RECENT_N:]],
        "open_tasks": task_view,
        "as_of": today.isoformat(),
    }


def to_prompt_text(s: dict) -> str:
    """요약 dict → 시스템 프롬프트에 넣을 짧은 글."""
    if not s["count"]:
        return "- 아직 업무 기록이 없습니다."
    m, t = s["metrics"], s["trend"]
    trend = f"{t['label']}" + (f" (최근 {TREND_DAYS}일 {t['recent_min']}분, 그 전 {t['previous_min']}분, {t['change_pct']:+d}%)"
                               if t["change_pct"] is not None else "")
    lines = [
        f"- 오늘 날짜: {s['as_of']}",
        f"- 데이터 기간: {s['period']}",
        f"- 총 기록: {s['count']}건 (작업한 날 {s['active_days']}일)",
        f"- 총 작업 시간: {m['total_hours']}시간, 기록당 평균 {m['average_min']}분, 작업한 날 하루 평균 {m['average_min_per_active_day']}분",
        f"- 가장 긴 기록: {m['max_record']} ({m['max_min']}분), 가장 많이 일한 날: {m['best_day']}",
        f"- 최근 추세: {trend}",
        f"- 분류별 시간: " + ", ".join(f"{k} {v}h" for k, v in s["by_category_hours"].items()),
        "",
        "[프로젝트별 현황] (시간 많은 순)",
    ]
    for p in s["by_project"]:
        flag = f" ⚠ {p['days_since']}일째 멈춤" if p["stale"] else ""
        lines.append(f"- {p['project']}: {p['hours']}h / {p['records']}건 / 마지막 {p['last_date']} \"{p['last_work']}\"{flag}")
    stale = sorted((p for p in s["by_project"] if p["stale"]), key=lambda p: -p["days_since"])
    if stale:
        lines += ["", f"[멈춘 프로젝트 {len(stale)}개] ({STALE_DAYS}일 넘게 기록 없음, 오래된 순)"]
        lines += [f"- {p['project']}: {p['days_since']}일째 (마지막 {p['last_date']})" for p in stale]
    lines += ["", "[최근 기록]"] + [f"- {r}" for r in s["recent"]]
    ot = s["open_tasks"]
    lines += ["", f"[남은 할 일 {ot['count']}개]"]
    for label, key in (("NOW", "now"), ("NEXT", "next"), ("WAITING", "waiting")):
        if ot[key]:
            lines.append(f"{label}: " + " / ".join(ot[key]))
    return "\n".join(lines)
