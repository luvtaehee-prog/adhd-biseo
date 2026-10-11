"use strict";

const API = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "http://127.0.0.1:8000").replace(/\/$/, "");
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];

const state = {
  convId: null,
  records: [],
  summary: null,
  tasks: [],
  editingId: null,
  filter: "",
  shown: 30,
  busy: false,
};

/* ── 공통 ─────────────────────────────────────────── */
async function api(path, options = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), options.timeout || 70000);
  try {
    const res = await fetch(API + path, {
      method: options.method || "GET",
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
      body: options.body ? JSON.stringify(options.body) : undefined,
      signal: ctrl.signal,
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error(errorText(res.status, data));
    return data;
  } catch (e) {
    if (e.name === "AbortError") throw new Error("서버 응답이 늦어요. 잠시 뒤 다시 시도해 주세요.");
    if (e instanceof TypeError) throw new Error("서버에 연결할 수 없어요.");
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

function errorText(status, data) {
  const d = data && data.detail;
  if (Array.isArray(d)) {
    const names = { date: "날짜", value: "작업 시간", memo: "한 일", project: "프로젝트", category: "분류", message: "메시지" };
    return "입력을 확인해 주세요: " + d.map((x) => {
      const field = names[x.loc && x.loc[x.loc.length - 1]] || "값";
      const ko = {
        less_than_equal: `${x.ctx && x.ctx.le} 이하로 입력`, greater_than_equal: `${x.ctx && x.ctx.ge} 이상으로 입력`,
        string_too_short: "비어 있음", string_too_long: "너무 김", date_from_datetime_parsing: "날짜 형식 오류",
        date_parsing: "날짜 형식 오류", literal_error: "정해진 값만 가능", missing: "필수",
      }[x.type];
      return `${field} (${ko || (x.msg || "").replace("Value error, ", "")})`;
    }).join(", ");
  }
  return d || `오류가 발생했어요 (${status})`;
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.hidden = true), 2600);
}

const fmtH = (min) => {
  const h = Math.floor(min / 60), m = min % 60;
  return h ? (m ? `${h}시간 ${m}분` : `${h}시간`) : `${m}분`;
};
const fmtDate = (iso) => {
  const d = new Date(iso);
  return isNaN(d) ? "" : `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
};
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};

/* ── 서버 깨우기 (Render 무료 티어 콜드스타트) ─────────── */
async function wakeServer() {
  const pill = $("#serverStatus");
  const banner = $("#wakeBanner");
  const started = Date.now();
  const tick = setInterval(() => { $("#wakeSec").textContent = Math.round((Date.now() - started) / 1000); }, 1000);
  const slow = setTimeout(() => (banner.hidden = false), 2500);
  try {
    for (let i = 0; i < 6; i++) {
      try {
        const h = await api("/health", { timeout: 20000 });
        pill.dataset.state = "ok";
        pill.textContent = h.ai ? "연결됨" : "연결됨 · AI 키 없음";
        return true;
      } catch (e) {
        if (Date.now() - started > 90000) break;
      }
    }
    pill.dataset.state = "fail";
    pill.textContent = "서버 연결 실패";
    toast("서버에 연결하지 못했어요. 새로고침해 주세요.");
    return false;
  } finally {
    clearTimeout(slow);
    clearInterval(tick);
    banner.hidden = true;
  }
}

/* ── 요약 ─────────────────────────────────────────── */
async function loadSummary() {
  state.summary = await api("/api/data/summary");
  renderSummary();
}

function renderSummary() {
  const s = state.summary;
  const strip = $("#summaryStrip");
  strip.replaceChildren();
  if (!s || !s.count) {
    strip.append(el("span", "chip", "아직 기록이 없어요"));
    return;
  }
  const t = s.trend || {};
  // 최근 2주에 기록이 없으면 -100% 대신 "기록 없음" (탓하는 숫자를 보여주지 않는다)
  const trendText = !t.recent_min ? "기록 없음"
    : t.label + (t.change_pct != null ? ` ${t.change_pct > 0 ? "+" : ""}${t.change_pct}%` : "");
  const chips = [
    ["기간", s.period.replace(/-/g, ".")],
    ["기록", `${s.count}건`],
    ["총 작업", `${s.metrics.total_hours}시간`],
    ["최근 2주", trendText, !t.recent_min ? "" : t.label === "증가" ? "trend-up" : t.label === "감소" ? "trend-down" : ""],
    ["남은 할 일", `${s.open_tasks.count}개`],
  ];
  const stale = s.by_project.filter((p) => p.stale).length;
  if (stale) chips.push(["멈춘 프로젝트", `${stale}개`, "trend-down"]);
  for (const [label, value, cls] of chips) {
    const c = el("span", "chip " + (cls || ""));
    c.append(label, el("b", null, value));
    strip.append(c);
  }

  // 요약 탭: 숫자 타일
  const m = s.metrics;
  const tiles = [
    ["총 작업 시간", m.total_hours, "시간"],
    ["작업한 날", s.active_days, "일"],
    ["작업한 날 하루 평균", m.average_min_per_active_day, "분"],
    ["가장 많이 일한 날", m.best_day.split(" ")[0].slice(5).replace("-", "/"), m.best_day.match(/\((.+)\)/)?.[1] || ""],
  ];
  $("#statTiles").replaceChildren(...tiles.map(([label, v, unit]) => {
    const box = el("div", "stat");
    const val = el("div", "stat-value", String(v));
    val.append(el("small", null, unit));
    box.append(el("div", "stat-label", label), val);
    return box;
  }));
  renderMonthChart(s.by_month_hours);
  renderProjectBars(s.by_project);
}

function renderMonthChart(byMonth) {
  const entries = Object.entries(byMonth);
  const box = $("#monthChart");
  if (!entries.length) { box.replaceChildren(el("p", "empty", "데이터가 없어요")); return; }
  const W = 360, H = 170, padL = 30, padB = 22, padT = 18;
  const max = Math.max(...entries.map(([, v]) => v));
  const step = max > 40 ? 20 : max > 20 ? 10 : 5;
  const top = Math.ceil(max / step) * step || step;
  const plotH = H - padB - padT;
  const slot = (W - padL) / entries.length;
  const bw = Math.min(28, slot - 8);
  const y = (v) => padT + plotH - (v / top) * plotH;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "월별 작업 시간: " + entries.map(([k, v]) => `${k} ${v}시간`).join(", "));
  const add = (tag, attrs, text) => {
    const n = document.createElementNS(ns, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  };
  for (let v = 0; v <= top; v += step) {
    svg.append(add("line", { class: "grid", x1: padL, x2: W, y1: y(v), y2: y(v) }));
    svg.append(add("text", { class: "axis-label", x: padL - 6, y: y(v) + 4, "text-anchor": "end" }, v));
  }
  const maxIdx = entries.findIndex(([, v]) => v === max);
  entries.forEach(([month, v], i) => {
    const cx = padL + slot * i + slot / 2;
    const x = cx - bw / 2, yt = y(v), h = Math.max(0, padT + plotH - yt), r = Math.min(4, h);
    const g = add("g", {});
    // 위쪽만 둥근 막대 (바닥선에 붙음)
    g.append(add("path", {
      class: "bar",
      d: `M${x},${yt + h} V${yt + r} Q${x},${yt} ${x + r},${yt} H${x + bw - r} Q${x + bw},${yt} ${x + bw},${yt + r} V${yt + h} Z`,
    }));
    g.append(add("rect", { class: "bar-hit", x: padL + slot * i, y: padT, width: slot, height: plotH }));
    g.addEventListener("mousemove", (e) => showTip(e, `${month.replace("-", "년 ")}월 · ${v}시간`));
    g.addEventListener("mouseleave", hideTip);
    svg.append(g);
    svg.append(add("text", { class: "axis-label", x: cx, y: H - 5, "text-anchor": "middle" }, `${Number(month.slice(5))}월`));
    if (i === maxIdx || i === entries.length - 1) {
      svg.append(add("text", { class: "val-label", x: cx, y: yt - 5, "text-anchor": "middle" }, `${v}h`));
    }
  });
  box.replaceChildren(svg);
}

function showTip(e, text) {
  const t = $("#tooltip");
  t.textContent = text;
  t.hidden = false;
  t.style.left = e.clientX + 12 + "px";
  t.style.top = e.clientY - 34 + "px";
}
function hideTip() { $("#tooltip").hidden = true; }

function renderProjectBars(projects) {
  const max = Math.max(...projects.map((p) => p.hours), 1);
  const wrap = el("div", "pbars");
  for (const p of projects) {
    const row = el("div", "pbar" + (p.stale ? " stale" : ""));
    const head = el("div", "pbar-head");
    const name = el("span", "pbar-name", p.project);
    if (p.stale) name.append(el("span", "stale-tag", `⏸ ${p.days_since}일째 멈춤`));
    head.append(name, el("span", "pbar-val", `${p.hours}h · ${p.records}건`));
    const track = el("div", "pbar-track");
    const fill = el("div", "pbar-fill");
    fill.style.width = (p.hours / max) * 100 + "%";
    track.append(fill);
    row.title = `마지막 작업 ${p.last_date}: ${p.last_work}`;
    row.append(head, track);
    wrap.append(row);
  }
  $("#projectChart").replaceChildren(wrap);
}

/* ── 할 일 ────────────────────────────────────────── */
const STATUS_LABEL = { NOW: "지금", NEXT: "다음", WAITING: "보류", DONE: "끝낸 일" };

async function loadTasks() {
  state.tasks = await api("/api/tasks");
  renderTasks();
}

function renderTasks() {
  const box = $("#taskGroups");
  box.replaceChildren();
  for (const status of ["NOW", "NEXT", "WAITING", "DONE"]) {
    const items = state.tasks.filter((t) => t.status === status);
    if (!items.length) continue;
    const group = el("section", "task-group");
    group.dataset.status = status;
    const h = el("h3");
    h.append(el("span", "task-badge", STATUS_LABEL[status]), `${items.length}개`);
    group.append(h);
    for (const t of items) {
      const row = el("label", "task" + (status === "DONE" ? " done" : ""));
      const cb = el("input");
      cb.type = "checkbox";
      cb.checked = status === "DONE";
      cb.addEventListener("change", () => toggleTask(t, cb.checked));
      const text = el("span", "task-text", t.task);
      text.prepend(el("span", "task-proj", t.project));
      row.append(cb, text);
      group.append(row);
    }
    box.append(group);
  }
}

async function toggleTask(task, done) {
  // 체크 해제하면 원래 상태로 되돌린다 (모르면 NOW)
  const prev = JSON.parse(localStorage.getItem("taskPrev") || "{}");
  const status = done ? "DONE" : prev[task.id] || "NOW";
  if (done) prev[task.id] = task.status;
  try {
    await api(`/api/tasks/${task.id}`, { method: "PUT", body: { status } });
    try { localStorage.setItem("taskPrev", JSON.stringify(prev)); } catch (e) {}
    task.status = status;
    renderTasks();
    toast(done ? "잘했어요! 한 가지 끝 ✓" : "다시 할 일로 돌렸어요");
    loadSummary();
  } catch (e) {
    toast(e.message);
    renderTasks();
  }
}

/* ── 데이터 관리 ──────────────────────────────────── */
async function loadRecords() {
  state.records = await api("/api/data");
  renderRecords();
  const projects = [...new Set(state.records.map((r) => r.project))].sort((a, b) => a.localeCompare(b, "ko"));
  $("#projectOptions").replaceChildren(...projects.map((p) => { const o = el("option"); o.value = p; return o; }));
  const sel = $("#projectFilter");
  sel.replaceChildren(el("option", null, "전체 프로젝트"), ...projects.map((p) => el("option", null, p)));
  sel.options[0].value = "";
  sel.value = projects.includes(state.filter) ? state.filter : "";
}

function filtered() {
  return state.filter ? state.records.filter((r) => r.project === state.filter) : state.records;
}

function renderRecords(flashId) {
  const rows = filtered();
  $("#dataCount").textContent = `${rows.length}건`;
  const list = $("#dataList");
  list.replaceChildren();
  for (const r of rows.slice(0, state.shown)) {
    const li = el("li", "drow" + (r.id === flashId ? " flash" : ""));
    const main = el("div", "drow-main");
    main.append(el("div", "drow-memo", r.memo), el("div", "drow-meta", `${r.date} · ${r.project} · ${r.category}`));
    const act = el("div", "drow-act");
    const edit = el("button", null, "수정");
    edit.type = "button";
    edit.addEventListener("click", () => startEdit(r));
    const del = el("button", "del", "삭제");
    del.type = "button";
    del.addEventListener("click", () => removeRecord(r));
    act.append(edit, del);
    li.append(main, el("span", "drow-val", fmtH(r.value)), act);
    list.append(li);
  }
  if (rows.length > state.shown) {
    const more = el("button", "btn btn-sm more", `더 보기 (${rows.length - state.shown}건 남음)`);
    more.type = "button";
    more.addEventListener("click", () => { state.shown += 30; renderRecords(); });
    list.append(more);
  }
  if (!rows.length) list.append(el("li", "empty", "기록이 없어요"));
}

function resetForm() {
  state.editingId = null;
  $("#dataForm").reset();
  $("#dataForm").classList.remove("editing");
  $("#fDate").value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  $("#formTitle").textContent = "새 기록 추가";
  $("#saveBtn").textContent = "추가";
  $("#cancelEdit").hidden = true;
}

function startEdit(r) {
  state.editingId = r.id;
  $("#fDate").value = r.date;
  $("#fValue").value = r.value;
  $("#fProject").value = r.project;
  $("#fCategory").value = r.category;
  $("#fMemo").value = r.memo;
  $("#dataForm").classList.add("editing");
  $("#formTitle").textContent = "기록 수정";
  $("#saveBtn").textContent = "수정 저장";
  $("#cancelEdit").hidden = false;
  $("#dataForm").scrollIntoView({ behavior: "smooth", block: "nearest" });
  $("#fMemo").focus();
}

async function saveRecord(e) {
  e.preventDefault();
  const body = {
    date: $("#fDate").value,
    value: Number($("#fValue").value),
    project: $("#fProject").value.trim(),
    category: $("#fCategory").value,
    memo: $("#fMemo").value.trim(),
  };
  const btn = $("#saveBtn");
  btn.disabled = true;
  try {
    const editing = state.editingId;
    const saved = editing
      ? await api(`/api/data/${editing}`, { method: "PUT", body })
      : await api("/api/data", { method: "POST", body });
    toast(editing ? "수정했어요" : "기록을 추가했어요");
    resetForm();
    await Promise.all([loadRecords(), loadSummary()]);
    renderRecords(saved.id);
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function removeRecord(r) {
  if (!confirm(`이 기록을 삭제할까요?\n\n${r.date} · ${r.memo}`)) return;
  try {
    await api(`/api/data/${r.id}`, { method: "DELETE" });
    if (state.editingId === r.id) resetForm();
    toast("삭제했어요");
    await Promise.all([loadRecords(), loadSummary()]);
  } catch (err) {
    toast(err.message);
  }
}

function download(name, text, type) {
  const blob = new Blob([text], { type });
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function exportCsv() {
  const cols = ["id", "date", "value", "memo", "project", "category", "source"];
  const esc = (v) => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const lines = [cols.join(","), ...filtered().map((r) => cols.map((c) => esc(r[c] ?? "")).join(","))];
  download(`worklog_${today()}.csv`, "﻿" + lines.join("\n"), "text/csv;charset=utf-8");
}
function exportJson() {
  download(`worklog_${today()}.json`, JSON.stringify(filtered(), null, 2), "application/json");
}
const today = () => new Date().toISOString().slice(0, 10);

/* ── 대화 기록 ────────────────────────────────────── */
async function loadConversations() {
  const list = await api("/api/conversations");
  const ul = $("#convList");
  ul.replaceChildren();
  if (!list.length) { ul.append(el("li", "empty", "아직 대화가 없어요")); return; }
  for (const c of list) {
    const li = el("li", "conv-item" + (c.id === state.convId ? " active" : ""));
    li.tabIndex = 0;
    const text = el("div", "conv-text");
    text.append(el("div", "conv-title", c.title), el("div", "conv-meta", `${fmtDate(c.updated_at)} · 메시지 ${c.message_count}개`));
    const del = el("button", "conv-del", "×");
    del.type = "button";
    del.setAttribute("aria-label", "대화 삭제");
    del.addEventListener("click", (e) => { e.stopPropagation(); removeConversation(c); });
    li.append(text, del);
    li.addEventListener("click", () => openConversation(c.id));
    li.addEventListener("keydown", (e) => { if (e.key === "Enter") openConversation(c.id); });
    ul.append(li);
  }
}

async function openConversation(id) {
  try {
    const conv = await api(`/api/conversations/${id}`);
    state.convId = id;
    const box = $("#messages");
    box.replaceChildren();
    conv.messages.forEach((m) => addMessage(m.role, m.content));
    $$(".conv-item").forEach((li) => li.classList.remove("active"));
    loadConversations();
    setView("chat");
    toast("대화를 불러왔어요");
  } catch (e) {
    toast(e.message);
  }
}

async function removeConversation(c) {
  if (!confirm(`"${c.title}" 대화를 삭제할까요?`)) return;
  try {
    await api(`/api/conversations/${c.id}`, { method: "DELETE" });
    if (state.convId === c.id) newChat();
    toast("대화를 삭제했어요");
    loadConversations();
  } catch (e) {
    toast(e.message);
  }
}

function newChat() {
  state.convId = null;
  const box = $("#messages");
  const w = el("div", "welcome");
  w.append(el("h3", null, "무엇부터 할지 같이 정해요"),
    el("p", null, "내 업무 기록을 보고 답해요. 아래 질문을 눌러 바로 시작해 보세요."));
  box.replaceChildren(w);
  $$(".conv-item").forEach((li) => li.classList.remove("active"));
  $("#chatInput").focus();
}

/* ── 채팅 ─────────────────────────────────────────── */
function addMessage(role, content, meta) {
  const box = $("#messages");
  $(".welcome", box)?.remove();
  const div = el("div", "msg " + role);
  if (role === "assistant") {
    // "👉 지금 할 한 가지" 줄은 강조 카드로
    const lines = content.split("\n");
    const idx = lines.findIndex((l) => l.includes("👉"));
    div.textContent = (idx >= 0 ? lines.slice(0, idx) : lines).join("\n").trim();
    if (idx >= 0) div.append(el("span", "next-step", lines.slice(idx).join("\n").trim()));
  } else {
    div.textContent = content;
  }
  if (meta) div.append(el("div", "msg-meta", meta));
  box.append(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

async function sendChat(text) {
  text = text.trim();
  if (!text || state.busy) return;
  state.busy = true;
  $("#sendBtn").disabled = true;
  addMessage("user", text);
  const loading = el("div", "msg assistant loading");
  loading.setAttribute("aria-label", "답변을 만드는 중");
  loading.append(el("span"), el("span"), el("span"));
  $("#messages").append(loading);
  $("#messages").scrollTop = $("#messages").scrollHeight;
  try {
    const res = await api("/api/chat", { method: "POST", body: { message: text, conversation_id: state.convId } });
    loading.remove();
    const c = res.context;
    addMessage("assistant", res.reply, `📊 ${c.period} · ${c.count}건 · 추세 ${c.trend} · 남은 할 일 ${c.open_tasks}개 · ${res.model}`);
    state.convId = res.conversation_id;
    loadConversations();
  } catch (e) {
    loading.remove();
    const err = addMessage("error", e.message);
    err.className = "msg error";
  } finally {
    state.busy = false;
    $("#sendBtn").disabled = false;
  }
}

/* ── 화면 전환 · 테마 ─────────────────────────────── */
function setTab(tab) {
  $$(".side-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $$("[data-tabpane]").forEach((p) => (p.hidden = p.dataset.tabpane !== tab));
}
function setView(view) {
  $(".layout").dataset.view = view;
  $$(".mobile-tabs button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  if (["tasks", "summary", "data"].includes(view)) setTab(view);
}

function initTheme() {
  $("#themeToggle").addEventListener("click", () => {
    const root = document.documentElement;
    const isDark = root.dataset.theme
      ? root.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = isDark ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) {}
  });
}

function bind() {
  initTheme();
  $$(".side-tabs button").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
  $$(".mobile-tabs button").forEach((b) => b.addEventListener("click", () => setView(b.dataset.view)));
  $("#newChat").addEventListener("click", () => { newChat(); setView("chat"); });
  $$("#quick button").forEach((b) => b.addEventListener("click", () => sendChat(b.textContent)));

  const input = $("#chatInput");
  const grow = () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 140) + "px"; };
  input.addEventListener("input", grow);
  input.addEventListener("keydown", (e) => {
    // 한글 조합 중 Enter는 무시 (마지막 글자 중복 방지)
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("#chatForm").requestSubmit();
    }
  });
  $("#chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    grow();
    sendChat(text);
  });

  $("#dataForm").addEventListener("submit", saveRecord);
  $("#cancelEdit").addEventListener("click", resetForm);
  $("#projectFilter").addEventListener("change", (e) => { state.filter = e.target.value; state.shown = 30; renderRecords(); });
  $("#exportCsv").addEventListener("click", exportCsv);
  $("#exportJson").addEventListener("click", exportJson);
}

async function init() {
  bind();
  resetForm();
  newChat();
  if (!(await wakeServer())) return;
  const results = await Promise.allSettled([loadSummary(), loadTasks(), loadRecords(), loadConversations()]);
  const failed = results.find((r) => r.status === "rejected");
  if (failed) toast(failed.reason.message);
}

init();
