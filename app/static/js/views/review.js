import { api, esc, toast, renderMarkdown, refreshDueBadge, INTERVALS, $ } from "../util.js";

const days = (n) => (n === 1 ? "내일" : `${n}일 뒤`);

const tabs = (active) => `<div class="toolbar"><div class="tabs">
  <a class="tab" href="#/review" aria-pressed="${active === "due"}">오늘 복습</a>
  <a class="tab" href="#/review?tab=weak" aria-pressed="${active !== "due"}">약점</a></div></div>`;

/** Run a flashcard session. `persist: false` is practice: nothing is sent, the schedule is untouched. */
function session(box, queue, { persist, alive }) {
  const total = queue.length;
  let done = 0;
  let revealed = false;
  let busy = false;

  function draw() {
    const card = queue[0];
    if (!card) {
      box.innerHTML = `<div class="empty"><h3>${persist ? "오늘 복습 끝" : "연습 끝"}</h3><p>${done}장을 ${persist ? "복습" : "다시 확인"}했어요.</p>
        <div class="row"><a class="btn primary" href="#/">홈으로</a><a class="btn" href="#/review?tab=weak">약점 보기</a></div></div>`;
      return;
    }
    const good = INTERVALS[Math.min(card.box + 1, INTERVALS.length - 1)];
    const hard = INTERVALS[Math.min(card.box, INTERVALS.length - 1)];
    const buttons = persist
      ? `<div class="grade-row">
          <button class="btn" data-grade="again">다시 <small>내일 · <kbd>1</kbd></small></button>
          <button class="btn" data-grade="hard">애매함 <small>${days(hard)} · <kbd>2</kbd></small></button>
          <button class="btn primary" data-grade="good">알았음 <small style="color:inherit;opacity:.85">${days(good)} · 3</small></button></div>`
      : `<div class="grade-row" style="grid-template-columns:repeat(2,1fr)">
          <button class="btn" data-grade="again">아직 헷갈림 <small>뒤에 다시 · <kbd>1</kbd></small></button>
          <button class="btn primary" data-grade="good">이제 알겠음 <small style="color:inherit;opacity:.85">3</small></button></div>`;
    box.innerHTML = `
      <div class="progress-line"><span>${done} / ${total}</span><div class="meter"><i style="width:${(done / total) * 100}%"></i></div>
        <span>남은 카드 ${queue.length}장</span></div>
      <div class="card flash-card">
        <a class="small muted" href="#/paper/${card.paper_id}">${esc(card.paper_title)}</a>
        <div class="flash-q" style="margin-top:10px">${esc(card.question)}</div>
        ${revealed ? `<div class="flash-a md">${renderMarkdown(card.answer)}</div>` : ""}
        <div class="flash-foot">${revealed ? buttons : `<button class="btn primary" id="reveal" style="width:100%">답 보기 <kbd>Space</kbd></button>`}</div>
      </div>
      ${persist ? "" : `<p class="small muted" style="text-align:center;margin-top:10px">연습 모드예요. 복습 일정과 기록은 바뀌지 않아요.</p>`}`;
  }

  async function grade(value) {
    const card = queue[0];
    if (!card || busy || !revealed || (!persist && value === "hard")) return;
    busy = true;
    try {
      if (persist) await api(`/api/review/${card.id}`, { method: "POST", body: { grade: value } });
      queue.shift();
      if (value === "again") queue.push({ ...card, box: 0 });  // 틀린 카드는 이번 세션 끝에 한 번 더
      else done++;
      revealed = false;
    } catch (err) {
      toast(err.message, "error");
    }
    busy = false;
    if (!alive()) return;
    draw();
    if (persist) refreshDueBadge();
  }

  box.addEventListener("click", (e) => {
    const t = e.target.closest("[data-grade],#reveal");
    if (!t) return;
    if (t.id === "reveal") { revealed = true; draw(); } else grade(t.dataset.grade);
  });
  const onKey = (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    if (!revealed && (e.key === " " || e.key === "Enter") && queue[0]) { e.preventDefault(); revealed = true; draw(); }
    else if (revealed && ["1", "2", "3"].includes(e.key)) grade(["again", "hard", "good"][Number(e.key) - 1]);
  };
  document.addEventListener("keydown", onKey);
  draw();
  return () => document.removeEventListener("keydown", onKey);
}

async function weakView(root) {
  const { cards, tags } = await api("/api/review/weak");
  const tagRows = tags.map((t) => `
    <div><div class="row" style="justify-content:space-between"><span>${t.tag ? esc(t.tag) : `<span class="muted">태그 없음</span>`}</span>
      <span class="small muted">정답률 ${Math.round(t.accuracy * 100)}% · 복습 ${t.reviews}회 중 ${t.lapses}회 틀림</span></div>
      <div class="meter" style="margin-top:6px" role="img" aria-label="정답률 ${Math.round(t.accuracy * 100)}%"><i style="width:${t.accuracy * 100}%"></i></div></div>`).join("");
  const cardRows = cards.map((c) => `
    <details style="padding:10px 0;border-top:1px solid var(--border)">
      <summary style="cursor:pointer">${esc(c.question)}
        <span class="chip warn" style="margin-left:6px">${c.reviews}번 중 ${c.lapses}번 틀림</span></summary>
      <div class="md" style="margin-top:8px">${renderMarkdown(c.answer)}</div>
      <a class="small" href="#/paper/${c.paper_id}">${esc(c.paper_title)}</a></details>`).join("");

  root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1><p>복습 기록에서 자주 틀리는 부분을 찾아요.</p></div></div>
    ${tabs("weak")}
    ${tags.length ? `
      <div class="card"><div class="card-head"><h2>태그별 정답률</h2><span class="small muted">낮은 순</span></div>
        <div class="stack">${tagRows}</div>
        <p class="small muted" style="margin-top:12px">논문에 태그를 붙여두면 어느 주제가 약한지 보여요.</p></div>
      <div class="card"><div class="card-head"><h2>자주 틀린 카드 ${cards.length ? `${cards.length}장` : ""}</h2>
        ${cards.length ? `<a class="btn sm primary" href="#/review?tab=practice">이 카드들만 연습</a>` : ""}</div>
        ${cardRows || `<p class="muted">틀린 적 있는 카드가 없어요.</p>`}</div>`
    : `<div class="empty"><h3>아직 복습 기록이 없어요</h3><p>카드를 몇 번 복습하고 나면 자주 틀리는 카드와 약한 주제가 여기에 모여요.</p>
        <div class="row"><a class="btn" href="#/review">오늘 복습으로</a></div></div>`}
  </div>`;
}

export async function render(root, { alive, query }) {
  const tab = query.get("tab");
  if (tab === "weak") return weakView(root);

  const practice = tab === "practice";
  const queue = practice ? (await api("/api/review/weak")).cards : await api("/api/review/due");
  if (!queue.length) {
    root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1></div></div>${tabs(practice ? "weak" : "due")}
      <div class="empty"><h3>${practice ? "연습할 카드가 없어요" : "오늘 복습할 카드가 없어요"}</h3>
      <p>노트에 <code>Q: 질문</code> / <code>A: 답</code>을 적으면 카드가 만들어져요.<br>
      맞힌 카드는 1 → 3 → 7 → 14 → 30 → 60일 간격으로 다시 나와요.</p>
      <div class="row"><a class="btn" href="#/library">라이브러리로</a></div></div></div>`;
    return;
  }
  root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1>
    <p>${practice ? "자주 틀린 카드만 모아서 다시 봐요." : "답을 떠올려 본 다음 확인하세요."}</p></div></div>
    ${tabs(practice ? "weak" : "due")}<div class="flash" id="flash"></div></div>`;
  return session($("#flash", root), queue, { persist: !practice, alive });
}
