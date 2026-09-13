"use strict";

// pageSize：一次显示多少条；visible：当前已渲染的条数
const state = { q: "", category: "", kind: "", folder: "", sort: "kind", pageSize: 20, visible: 20 };

const KIND_LABELS = {
  document: "文档", spreadsheet: "表格", text: "文本",
  audio: "音频", video: "视频", image: "图片",
  archive: "压缩包", other: "其他",
};
const KIND_ORDER = ["audio", "video", "document", "image", "spreadsheet", "text", "archive", "other"];
// kind -> 短标签（卡片左侧色块用）
const KIND_TAG = {
  document: "DOC", spreadsheet: "XLS", text: "TXT",
  audio: "MP3", video: "MP4", image: "IMG",
  archive: "ZIP", other: "FILE",
};
const PREVIEW_EXTS = new Set([
  "pdf", "jpg", "jpeg", "png", "gif", "webp",
  "mp3", "m4a", "wav", "wma", "mp4", "mov", "mkv",
  "txt", "md", "csv",
]);
const IMAGE_EXTS = new Set(["jpg", "jpeg", "png", "gif", "webp"]);
const AUDIO_EXTS = new Set(["mp3", "m4a", "wav", "wma"]);
const VIDEO_EXTS = new Set(["mp4", "mov", "mkv", "avi"]);

let allItems = [];      // 当前筛选条件下的全部结果
let itemMap = new Map();

function $(sel) { return document.querySelector(sel); }

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
function tagFor(it) { return KIND_TAG[it.kind] || "FILE"; }
function fmtSize(n) {
  if (n == null || n === 0) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return (i === 0 ? n : n.toFixed(1)) + " " + u[i];
}
function fmtDate(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// ---------- 侧边栏抽屉折叠 ----------
function togglePanel(head) {
  const panel = head.closest(".panel");
  if (!panel) return;
  panel.classList.toggle("collapsed");
}

// ---------- 侧边栏列表项 ----------
function makeCatItem(name, label, icon, color) {
  const li = document.createElement("li");
  li.className = "cat";
  li.dataset.name = name;
  li.innerHTML = `<span class="dot" style="background:${color}"></span><span class="cat-name">${esc(label)}</span><span class="count">0</span>`;
  li.onclick = () => { state.category = name; state.visible = state.pageSize; syncActive(); applyFilters(); };
  return li;
}
function makeKindItem(name, label, color) {
  const li = document.createElement("li");
  li.className = "cat";
  li.dataset.name = name;
  const dotColor = color || "#8c7d63";
  li.innerHTML = `<span class="dot" style="background:${dotColor}"></span><span class="cat-name">${esc(label)}</span><span class="count">0</span>`;
  li.onclick = () => { state.kind = name; state.visible = state.pageSize; syncActive(); applyFilters(); };
  return li;
}
// kind -> 配色（侧边栏色块用）
const KIND_COLORS = {
  audio: "#2f6b4f", video: "#a04040", document: "#6b5d4a",
  image: "#8c6d3f", spreadsheet: "#5a6d8c", text: "#7a6d5a",
  archive: "#6b4a6d", other: "#8c7d63",
};
function buildCategories(cats) {
  const ul = $("#categories");
  ul.innerHTML = "";
  ul.appendChild(makeCatItem("", "全部", "", "#607d8b"));
  cats.forEach((c) => ul.appendChild(makeCatItem(c.name, c.name, c.icon, c.color)));
}
function buildKinds(byKind) {
  const ul = $("#kinds");
  ul.innerHTML = "";
  ul.appendChild(makeKindItem("", "全部", "#607d8b"));
  KIND_ORDER.forEach((k) => { if (byKind && byKind[k]) ul.appendChild(makeKindItem(k, KIND_LABELS[k], KIND_COLORS[k])); });
}
function syncActive() {
  document.querySelectorAll("#categories .cat").forEach((li) => li.classList.toggle("active", li.dataset.name === state.category));
  document.querySelectorAll("#kinds .cat").forEach((li) => li.classList.toggle("active", li.dataset.name === state.kind));
}

// ---------- 联动计数 ----------
async function loadFacets() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.folder) p.set("folder", state.folder);
  if (state.category) p.set("category", state.category);
  if (state.kind) p.set("kind", state.kind);
  const f = await fetch("/api/facets?" + p.toString()).then((r) => r.json());
  updateFacetCounts(f);
}
function updateFacetCounts(f) {
  const catCounts = new Map((f.categories || []).map((c) => [c.name, c.count]));
  const catTotal = [...catCounts.values()].reduce((a, b) => a + b, 0);
  document.querySelectorAll("#categories .cat").forEach((li) => {
    li.querySelector(".count").textContent = li.dataset.name === "" ? catTotal : (catCounts.get(li.dataset.name) || 0);
  });
  const kindCounts = new Map((f.kinds || []).map((k) => [k.name, k.count]));
  const kindTotal = [...kindCounts.values()].reduce((a, b) => a + b, 0);
  document.querySelectorAll("#kinds .cat").forEach((li) => {
    li.querySelector(".count").textContent = li.dataset.name === "" ? kindTotal : (kindCounts.get(li.dataset.name) || 0);
  });
}

// ---------- 顶部统计 ----------
async function loadStats() {
  const s = await fetch("/api/stats").then((r) => r.json());
  const el = $("#stats");
  if (!s.root_exists) {
    el.innerHTML = `<div class="banner warn">未找到资料目录 <code>${esc(s.root)}</code>，请确认后点「刷新索引」。</div>`;
    return s;
  }
  el.innerHTML = `
    <div class="stat"><b>${s.total}</b><span>个文件</span></div>
    <div class="stat"><b>${fmtSize(s.total_size)}</b><span>总大小</span></div>
    <div class="stat"><b>${Object.keys(s.by_category).length}</b><span>个科目</span></div>
    <div class="stat"><b>${Object.keys(s.by_ext).length}</b><span>种格式</span></div>`;
  return s;
}

async function loadFolders() {
  const folders = await fetch("/api/folders").then((r) => r.json());
  const sel = $("#folder");
  const current = state.folder;
  sel.innerHTML = `<option value="">选择文件夹</option>` +
    folders.map((f) => `<option value="${esc(f.name)}">${esc(f.name)} (${f.count})</option>`).join("");
  sel.value = current;
}

// ---------- 文件列表（带分页） ----------
async function loadItems() {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.category) p.set("category", state.category);
  if (state.kind) p.set("kind", state.kind);
  if (state.folder) p.set("folder", state.folder);
  p.set("sort", state.sort === "kind" ? "name" : state.sort);

  allItems = await fetch("/api/items?" + p.toString()).then((r) => r.json());
  itemMap = new Map(allItems.map((it) => [it.id, it]));
  state.visible = state.pageSize;
  renderGrid();
}

function renderGrid() {
  const grid = $("#grid");
  const empty = $("#empty");
  $("#count").textContent = `${allItems.length} 个结果`;

  if (!allItems.length) {
    grid.innerHTML = ""; empty.hidden = false;
    $("#loadMore").style.display = "none";
    return;
  }
  empty.hidden = true;

  const shown = allItems.slice(0, state.visible);
  grid.innerHTML = state.sort === "kind"
    ? renderGrouped(shown)
    : `<div class="grid">${shown.map(cardHTML).join("")}</div>`;
  bindCards();

  const more = allItems.length - state.visible;
  const loadMore = $("#loadMore");
  if (more > 0) {
    loadMore.style.display = "";
    loadMore.textContent = `加载更多（剩余 ${more} 条）`;
  } else {
    loadMore.style.display = "none";
  }
}

function cardHTML(it) {
  return `<div class="card" data-id="${it.id}">
    <div class="card-tag" data-kind="${it.kind}">${esc(tagFor(it))}</div>
    <div class="card-main">
      <div class="card-name">${esc(it.name)}</div>
      <div class="card-meta">${esc(it.folder)} · ${fmtSize(it.size)} · ${fmtDate(it.mtime)}</div>
    </div>
    <span class="badge">${esc(it.category)}</span>
  </div>`;
}

function renderGrouped(items) {
  const groups = [];
  KIND_ORDER.forEach((k) => {
    const subset = items.filter((it) => it.kind === k);
    if (subset.length) {
      groups.push(`<section class="type-group">
        <h2 class="group-head">${esc(KIND_LABELS[k])} <span class="group-count">${subset.length}</span></h2>
        <div class="grid">${subset.map(cardHTML).join("")}</div>
      </section>`);
    }
  });
  return groups.join("");
}

function bindCards() {
  document.querySelectorAll("#grid .card").forEach((card) => {
    const it = itemMap.get(Number(card.dataset.id));
    if (!it) return;
    card.addEventListener("click", () => openItem(it));
    card.addEventListener("mouseenter", (e) => showTooltip(it, e));
    card.addEventListener("mousemove", moveTooltip);
    card.addEventListener("mouseleave", hideTooltip);
  });
}

// ---------- 打开 / 预览 ----------
function openItem(item) {
  if (PREVIEW_EXTS.has(item.ext)) openPreview(item);
  else openExternal(item);
}
function openExternal(item) {
  fetch("/api/open?path=" + encodeURIComponent(item.path))
    .then((r) => r.json())
    .then((d) => { if (!d.ok) showToast("打开失败"); })
    .catch(() => showToast("打开失败"));
}
function openPreview(item) {
  const modal = $("#modal");
  $("#modalTitle").textContent = item.name;
  const url = "/api/raw?path=" + encodeURIComponent(item.path);
  let html;
  if (item.ext === "pdf") html = `<iframe src="${url}" class="preview-frame"></iframe>`;
  else if (IMAGE_EXTS.has(item.ext)) html = `<img src="${url}" class="preview-img" alt="">`;
  else if (AUDIO_EXTS.has(item.ext)) html = `<div class="preview-center"><audio src="${url}" controls autoplay></audio></div>`;
  else if (VIDEO_EXTS.has(item.ext)) html = `<video src="${url}" controls autoplay class="preview-frame"></video>`;
  else html = `<iframe src="${url}" class="preview-frame"></iframe>`;
  $("#modalBody").innerHTML = html;
  modal.dataset.path = item.path;
  modal.hidden = false;
}
function closePreview() {
  const modal = $("#modal");
  modal.hidden = true;
  modal.dataset.path = "";
  $("#modalBody").innerHTML = "";
}

// ---------- 悬停提示 ----------
function getTooltip() {
  let t = document.getElementById("tooltip");
  if (!t) { t = document.createElement("div"); t.id = "tooltip"; document.body.appendChild(t); }
  return t;
}
function showTooltip(it, e) {
  const t = getTooltip();
  t.innerHTML = `<div class="tip-name">${esc(it.name)}</div><div class="tip-type">${esc(KIND_LABELS[it.kind] || it.kind)} · ${esc(it.ext)} · ${fmtSize(it.size)}</div>`;
  t.style.display = "block";
  moveTooltip(e);
}
function moveTooltip(e) {
  const t = getTooltip();
  const pad = 16;
  let x = e.clientX + pad;
  let y = e.clientY + pad;
  const rect = t.getBoundingClientRect();
  if (x + rect.width > window.innerWidth - 8) x = e.clientX - rect.width - pad;
  if (y + rect.height > window.innerHeight - 8) y = e.clientY - rect.height - pad;
  t.style.left = x + "px";
  t.style.top = y + "px";
}
function hideTooltip() { getTooltip().style.display = "none"; }

// ---------- 提示 ----------
function showToast(msg) {
  let t = document.getElementById("toast");
  if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._timer);
  t._timer = setTimeout(() => t.classList.remove("show"), 1800);
}

// ---------- 每页显示下拉抽屉 ----------
function togglePageDropdown() {
  const dd = $("#pageDropdown");
  const tg = $("#pageToggle");
  const open = dd.classList.toggle("open");
  tg.classList.toggle("open", open);
}
function choosePageSize(n) {
  state.pageSize = n;
  state.visible = n;
  $("#pageToggle").textContent = `${n} 条/页`;
  renderGrid();
  $("#pageDropdown").classList.remove("open");
  $("#pageToggle").classList.remove("open");
}

// ---------- 重置到初始状态 ----------
function resetAll() {
  state.q = "";
  state.category = "";
  state.kind = "";
  state.folder = "";
  state.sort = "kind";
  state.pageSize = 20;
  state.visible = 20;
  $("#q").value = "";
  $("#sort").value = "kind";
  $("#folder").value = "";
  $("#pageToggle").textContent = "20 条/页";
  switchView("library");
  syncActive();
  applyFilters();
}

// ---------- 侧栏折叠 ----------
function toggleRail() {
  const collapsed = document.documentElement.classList.toggle("rail-collapsed");
  const tg = $("#railToggle");
  tg.textContent = collapsed ? "\u00bb" : "\u00ab";
  tg.title = collapsed ? "展开侧栏" : "收起侧栏";
  if (collapsed) closeFsPop();
  try { localStorage.setItem("ielts.rail", collapsed ? "1" : "0"); } catch (e) {}
}

// ---------- 字体大小设置（每次步进 0.1） ----------
const FS_MIN = 0.7, FS_MAX = 1.6, FS_STEP = 0.1;
function getFontScale() {
  const v = parseFloat(localStorage.getItem("ielts.fs"));
  return v >= FS_MIN && v <= FS_MAX ? Math.round(v * 10) / 10 : 1;
}
function applyFontScale(v) {
  v = Math.min(FS_MAX, Math.max(FS_MIN, Math.round(v * 10) / 10));
  document.documentElement.style.setProperty("--fs", v);
  $("#fsVal").textContent = v.toFixed(1) + "×";
  $("#fsMinus").disabled = v <= FS_MIN;
  $("#fsPlus").disabled = v >= FS_MAX;
  try { localStorage.setItem("ielts.fs", String(v)); } catch (e) {}
}
function stepFont(dir) { applyFontScale(getFontScale() + dir * FS_STEP); }
function toggleFsPop(open) {
  const pop = $("#fsPop");
  const willOpen = typeof open === "boolean" ? open : pop.hidden;
  pop.hidden = !willOpen;
  $("#settingsBtn").classList.toggle("open", willOpen);
}
function closeFsPop() { toggleFsPop(false); }

// ---------- 初始化侧栏状态（字体倍率 / 折叠按钮） ----------
function setupChrome() {
  applyFontScale(getFontScale());
  const collapsed = document.documentElement.classList.contains("rail-collapsed");
  const tg = $("#railToggle");
  tg.textContent = collapsed ? "\u00bb" : "\u00ab";
  tg.title = collapsed ? "展开侧栏" : "收起侧栏";
}

// ---------- 事件 ----------
function applyFilters() { loadFacets(); loadItems(); }

function switchView(view) {
  document.querySelectorAll(".nav-item").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
  const isLibrary = view === "library";
  document.querySelector(".search").style.display = isLibrary ? "" : "none";
  document.querySelector("#refresh").style.display = isLibrary ? "" : "none";
  document.querySelector("#railFilters").style.display = isLibrary ? "" : "none";
  document.querySelector("#viewLibrary").hidden = !isLibrary;
  document.querySelector("#planView").hidden = view !== "plan";
  document.querySelector("#practiceView").hidden = view !== "practice";
  if (view === "plan" && typeof initPlan === "function") initPlan();
  if (view === "practice" && typeof initPractice === "function") initPractice();
}

function bindEvents() {
  // 侧栏导航切换
  document.querySelectorAll(".nav-item").forEach((t) => t.addEventListener("click", () => switchView(t.dataset.view)));
  // 侧栏折叠
  $("#railToggle").addEventListener("click", toggleRail);
  // 设置：字体大小（折叠时先展开侧栏再弹出）
  $("#settingsBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    if (document.documentElement.classList.contains("rail-collapsed")) toggleRail();
    toggleFsPop();
  });
  $("#fsMinus").addEventListener("click", () => stepFont(-1));
  $("#fsPlus").addEventListener("click", () => stepFont(1));
  document.addEventListener("click", (e) => {
    const pop = $("#fsPop");
    if (!pop.hidden && !pop.contains(e.target) && !$("#settingsBtn").contains(e.target)) closeFsPop();
  });
  let debounce;
  $("#q").addEventListener("input", (e) => {
    clearTimeout(debounce);
    debounce = setTimeout(() => { state.q = e.target.value.trim(); state.visible = state.pageSize; applyFilters(); }, 200);
  });
  $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; state.visible = state.pageSize; loadItems(); });
  $("#folder").addEventListener("change", (e) => { state.folder = e.target.value; state.visible = state.pageSize; applyFilters(); });
  $("#refresh").addEventListener("click", async () => {
    const btn = $("#refresh");
    btn.disabled = true; btn.textContent = "扫描中…";
    try {
      const resp = await fetch("/api/refresh", { method: "POST" });
      const r = await resp.json();
      showToast(resp.ok ? `已索引 ${r.total} 个文件（${r.seconds}s）` : (r.detail || "刷新失败"));
    } catch {
      showToast("刷新失败，服务无响应");
    } finally {
      btn.disabled = false; btn.textContent = "刷新索引";
      await init();
    }
  });
  $("#openBtn").addEventListener("click", () => {
    const p = $("#modal").dataset.path;
    if (p) openExternal({ path: p });
  });
  $("#closeBtn").addEventListener("click", closePreview);
  $("#modal").addEventListener("click", (e) => { if (e.target === e.currentTarget) closePreview(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closePreview(); });

  // 抽屉折叠
  document.querySelectorAll(".panel-head").forEach((h) => h.addEventListener("click", () => togglePanel(h)));
  // 每页下拉
  $("#pageToggle").addEventListener("click", (e) => { e.stopPropagation(); togglePageDropdown(); });
  document.querySelectorAll("#pageDropdown .dd-option").forEach((o) => o.addEventListener("click", () => choosePageSize(Number(o.dataset.n))));
  document.addEventListener("click", (e) => {
    const dd = $("#pageDropdown");
    const tg = $("#pageToggle");
    if (dd.classList.contains("open") && !dd.contains(e.target) && e.target.id !== "pageToggle") {
      dd.classList.remove("open");
      tg.classList.remove("open");
    }
  });
  // 加载更多
  $("#loadMore").addEventListener("click", () => {
    state.visible += state.pageSize;
    renderGrid();
  });
  // brand 重置
  $(".brand").addEventListener("click", resetAll);
}

// ---------- 初始化 ----------
async function init() {
  const stats = await loadStats();
  const cats = await fetch("/api/categories").then((r) => r.json());
  buildCategories(cats);
  buildKinds(stats.by_kind || {});
  syncActive();
  await Promise.all([loadFacets(), loadItems(), loadFolders()]);
}

document.addEventListener("DOMContentLoaded", () => { setupChrome(); bindEvents(); init(); });
