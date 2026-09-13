"use strict";

// 单词卡片练习（复用 app.js 的 $ 和 esc 全局函数）
let words = [];
let wordPos = 0;
let practiceInit = false;
let roundDone = false;
// 全词库掌握统计（不随范围筛选变化）：{total, known, unknown, fresh}
let wStats = { total: 0, known: 0, unknown: 0, fresh: 0 };

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function initPractice() {
  if (practiceInit) { loadWordSources(); return; }
  practiceInit = true;
  bindPracticeEvents();
  await loadWordSources();
}

async function loadWordSources() {
  const sources = await fetch("/api/word/sources").then((r) => r.json());
  const total = sources.reduce((a, s) => a + s.count, 0);
  const sel = $("#wordSource");
  const cur = sel.value;
  sel.innerHTML = `<option value="">全部词库（${total} 词）</option>` +
    sources.map((s) => `<option value="${esc(s.source)}">${esc(s.source)}（${s.count}）</option>`).join("");
  sel.value = cur && sources.some((s) => s.source === cur) ? cur : "";
  await loadWords();
}

async function loadWords() {
  const source = $("#wordSource").value;
  const mode = $("#wordFilter").value;
  const p = new URLSearchParams();
  if (source) p.set("source", source);
  if (mode) p.set("mode", mode);
  const [list, stats] = await Promise.all([
    fetch("/api/words?" + p.toString()).then((r) => r.json()),
    fetch("/api/word/stats?" + (source ? "source=" + encodeURIComponent(source) : "")).then((r) => r.json()),
  ]);
  words = list;
  wStats = stats;
  wordPos = 0;
  roundDone = false;
  showCard();
}

function showCard() {
  const card = $("#flashcard");
  const empty = $("#wordEmpty");
  renderWordStats();
  if (!words.length) {
    $("#cardFront").textContent = "";
    $("#cardBack").textContent = "";
    $("#wordPos").textContent = "0 / 0";
    $("#wordProgressFill").style.width = "0%";
    empty.hidden = false;
    card.style.display = "none";
    return;
  }
  empty.hidden = true;
  card.style.display = "";
  if (roundDone) {
    $("#cardFront").textContent = "本轮完成";
    $("#cardBack").textContent = `共过 ${words.length} 个词。按「认识 / 不认识」再来一轮，或切换范围继续。`;
    $("#wordPos").textContent = `完成 ${words.length} / ${words.length}`;
    $("#wordProgressFill").style.width = "100%";
    card.classList.remove("flipped");
    return;
  }
  const w = words[wordPos];
  $("#cardFront").textContent = w.word;
  $("#cardBack").textContent = w.meaning;
  $("#wordPos").textContent = `${wordPos + 1} / ${words.length}`;
  $("#wordProgressFill").style.width = `${((wordPos + 1) / words.length) * 100}%`;
  card.classList.remove("flipped");
}

function renderWordStats() {
  if (!wStats.total) { $("#wordStats").innerHTML = ""; return; }
  $("#wordStats").innerHTML = `
    <div class="stat"><b>${wStats.known}</b><span>认识</span></div>
    <div class="stat"><b>${wStats.unknown}</b><span>不认识</span></div>
    <div class="stat"><b>${wStats.fresh}</b><span>未学</span></div>`;
}

function advance(known) {
  if (!words.length) return;
  if (roundDone) { wordPos = 0; roundDone = false; showCard(); return; }
  const w = words[wordPos];
  fetch(`/api/word/${w.id}/mark`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ known }),
  });
  // 本地同步统计：旧状态减一、新状态加一
  if (w.known === 1) wStats.known--; else if (w.known === 2) wStats.unknown--; else wStats.fresh--;
  if (known === 1) wStats.known++; else if (known === 2) wStats.unknown++; else wStats.fresh++;
  w.known = known;
  if (wordPos + 1 >= words.length) roundDone = true;
  else wordPos++;
  showCard();
}

function bindPracticeEvents() {
  $("#flashcard").addEventListener("click", () => $("#flashcard").classList.toggle("flipped"));
  $("#wordKnown").addEventListener("click", () => advance(1));
  $("#wordUnknown").addEventListener("click", () => advance(2));
  $("#wordShuffle").addEventListener("click", () => { shuffle(words); wordPos = 0; roundDone = false; showCard(); });
  $("#wordSource").addEventListener("change", loadWords);
  $("#wordFilter").addEventListener("change", loadWords);
  document.addEventListener("keydown", (e) => {
    if (document.querySelector("#practiceView").hidden) return;
    if (e.key === " " || e.key === "Enter") { e.preventDefault(); $("#flashcard").classList.toggle("flipped"); }
    else if (e.key === "ArrowLeft") advance(2);
    else if (e.key === "ArrowRight") advance(1);
  });
}
