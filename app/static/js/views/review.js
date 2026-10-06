import { api, esc, toast, renderMarkdown, refreshDueBadge, INTERVALS, $ } from "../util.js";

const days = (n) => (n === 1 ? "내일" : `${n}일 뒤`);

export async function render(root, { alive }) {
  const queue = await api("/api/review/due");
  const total = queue.length;
  let done = 0;
  let revealed = false;
  let busy = false;

  if (!total) {
    root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1></div></div>
      <div class="empty"><h3>오늘 복습할 카드가 없어요</h3>
      <p>노트에 <code>Q: 질문</code> / <code>A: 답</code>을 적으면 카드가 만들어져요.<br>
      맞힌 카드는 1 → 3 → 7 → 14 → 30 → 60일 간격으로 다시 나와요.</p>
      <div class="row"><a class="btn" href="#/library">라이브러리로</a></div></div></div>`;
    return;
  }

  root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1><p>답을 떠올려 본 다음 확인하세요.</p></div></div>
    <div class="flash" id="flash"></div></div>`;
  const box = $("#flash", root);

  function draw() {
    const card = queue[0];
    if (!card) {
      box.innerHTML = `<div class="empty"><h3>오늘 복습 끝</h3><p>${done}장을 복습했어요.</p>
        <div class="row"><a class="btn primary" href="#/">홈으로</a></div></div>`;
      return;
    }
    const good = INTERVALS[Math.min(card.box + 1, INTERVALS.length - 1)];
    const hard = INTERVALS[Math.min(card.box, INTERVALS.length - 1)];
    box.innerHTML = `
      <div class="progress-line"><span>${done} / ${total}</span><div class="meter"><i style="width:${(done / total) * 100}%"></i></div>
        <span>남은 카드 ${queue.length}장</span></div>
      <div class="card flash-card">
        <a class="small muted" href="#/paper/${card.paper_id}">${esc(card.paper_title)}</a>
        <div class="flash-q" style="margin-top:10px">${esc(card.question)}</div>
        ${revealed ? `<div class="flash-a md">${renderMarkdown(card.answer)}</div>` : ""}
        <div class="flash-foot">${revealed
          ? `<div class="grade-row">
              <button class="btn" data-grade="again">다시 <small>내일 · <kbd>1</kbd></small></button>
              <button class="btn" data-grade="hard">애매함 <small>${days(hard)} · <kbd>2</kbd></small></button>
              <button class="btn primary" data-grade="good">알았음 <small style="color:inherit;opacity:.85">${days(good)} · 3</small></button></div>`
          : `<button class="btn primary" id="reveal" style="width:100%">답 보기 <kbd>Space</kbd></button>`}</div>
      </div>`;
  }

  async function grade(value) {
    const card = queue[0];
    if (!card || busy || !revealed) return;
    busy = true;
    try {
      await api(`/api/review/${card.id}`, { method: "POST", body: { grade: value } });
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
    refreshDueBadge();
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
