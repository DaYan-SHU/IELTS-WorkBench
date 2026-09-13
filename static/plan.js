"use strict";

// 学习计划视图（复用 app.js 里的 $ 和 esc 全局函数）
let planDate = todayStr();
let planInit = false;

const WEEK_LABELS = ["日", "一", "二", "三", "四", "五", "六"];

function toStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
function todayStr() { return toStr(new Date()); }

function shiftDate(n) {
  const d = new Date(planDate + "T00:00:00");
  d.setDate(d.getDate() + n);
  planDate = toStr(d);
  $("#planDate").value = planDate;
  refreshPlan();
}

// ---------- 加载与渲染 ----------
async function loadPlans() {
  const plans = await fetch("/api/plans?date=" + planDate).then((r) => r.json());
  renderPlans(plans);
}

function renderPlans(plans) {
  const list = $("#planList");
  const empty = $("#planEmpty");
  if (!plans.length) { list.innerHTML = ""; empty.hidden = false; return; }
  empty.hidden = true;
  list.innerHTML = plans.map((p) => `
    <div class="plan-item ${p.done ? "done" : ""}" data-id="${p.id}">
      <label class="plan-check"><input type="checkbox" ${p.done ? "checked" : ""}></label>
      <div class="plan-title">${esc(p.title)}</div>
      ${p.subject ? `<span class="badge">${esc(p.subject)}</span>` : ""}
      <button class="plan-del" title="删除">✕</button>
    </div>`).join("");
  list.querySelectorAll(".plan-item").forEach((el) => {
    const id = Number(el.dataset.id);
    el.querySelector("input[type=checkbox]").addEventListener("change", (e) => togglePlan(id, e.target.checked));
    el.querySelector(".plan-del").addEventListener("click", () => removePlan(id));
  });
}

async function loadPlanStats() {
  const s = await fetch("/api/plan/stats").then((r) => r.json());
  renderPlanStats(s);
}

function renderPlanStats(s) {
  $("#planStats").innerHTML = `
    <div class="stat"><b>${s.streak}</b><span>连续打卡(天)</span></div>
    <div class="stat"><b>${s.today_done}/${s.today_total}</b><span>今日完成</span></div>
    <div class="stat"><b>${s.total_done}</b><span>累计完成</span></div>`;
  renderWeekBar(s.days);
}

function renderWeekBar(days) {
  const el = $("#weekBar");
  const today = todayStr();
  el.innerHTML = days.map((d) => {
    const pct = d.total ? Math.round((d.done / d.total) * 100) : 0;
    const h = d.done > 0 ? Math.max(6, pct) : 0;
    const day = new Date(d.date + "T00:00:00").getDay();
    return `<div class="week-day ${d.date === today ? "today" : ""}" title="${d.date} · 完成 ${d.done}/${d.total}">
      <div class="week-bar"><div class="week-fill" style="height:${h}%"></div></div>
      <span class="week-label">${WEEK_LABELS[day]}</span>
    </div>`;
  }).join("");
}

// ---------- 操作 ----------
async function togglePlan(id, done) {
  await fetch(`/api/plans/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done }),
  });
  refreshPlan();
}
async function removePlan(id) {
  await fetch(`/api/plans/${id}`, { method: "DELETE" });
  refreshPlan();
}
async function addPlan() {
  const title = $("#planTitle").value.trim();
  if (!title) { $("#planTitle").focus(); return; }
  const subject = $("#planSubject").value;
  await fetch("/api/plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: planDate, subject, title }),
  });
  $("#planTitle").value = "";
  refreshPlan();
}

function refreshPlan() { loadPlans(); loadPlanStats(); }

// ---------- 初始化（由 app.js 的 switchView 调用） ----------
async function initPlan() {
  if (planInit) { refreshPlan(); return; }
  planInit = true;
  try {
    const cats = await fetch("/api/categories").then((r) => r.json());
    $("#planSubject").innerHTML = `<option value="">科目（可选）</option>` +
      cats.map((c) => `<option value="${esc(c.name)}">${esc(c.name)}</option>`).join("");
  } catch (e) { /* 科目下拉失败不阻塞 */ }
  $("#planDate").value = planDate;
  bindPlanEvents();
  refreshPlan();
}

function bindPlanEvents() {
  $("#prevDay").addEventListener("click", () => shiftDate(-1));
  $("#nextDay").addEventListener("click", () => shiftDate(1));
  $("#planDate").addEventListener("change", (e) => { planDate = e.target.value; refreshPlan(); });
  $("#planAdd").addEventListener("click", addPlan);
  $("#planTitle").addEventListener("keydown", (e) => { if (e.key === "Enter") addPlan(); });
}
