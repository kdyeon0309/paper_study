import { api, esc, toast, renderMarkdown, refreshDueBadge, cardForm, submitCardForm, INTERVALS, $ } from "../util.js";

const days = (n) => (n === 1 ? "내일" : `${n}일 뒤`);
const SESSION = 20;  // 한 번에 보는 카드 수. 밀린 카드가 많아도 끝이 보이게 나눈다

const tabs = (active) => `<div class="toolbar"><div class="tabs">
  <a class="tab" href="#/review" aria-pressed="${active === "due"}">오늘 복습</a>
  <a class="tab" href="#/review?tab=recall" aria-pressed="${active === "recall"}">논문 회상</a>
  <a class="tab" href="#/review?tab=weak" aria-pressed="${active === "weak"}">약점</a></div></div>`;

/** Finished papers, one at a time: write the gist from memory, then compare with the note's own summary. */
async function recallView(root, alive) {
  const queue = await api("/api/recall/due");
  const total = queue.length;
  let mine = "";
  let reference = null;

  root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1>
    <p>완독한 논문을 시간이 지난 뒤 기억만으로 다시 요약해봐요. 카드가 세부를 묻는다면, 이건 큰 그림을 묻는 거예요.</p></div></div>
    ${tabs("recall")}<div class="flash" id="recall"></div></div>`;
  const box = $("#recall", root);

  const draw = () => {
    const paper = queue[0];
    if (!paper) {
      box.innerHTML = `<div class="empty"><h3>${total ? "회상 끝" : "지금 회상할 논문이 없어요"}</h3>
        <p>논문을 완독으로 표시하면 7일 뒤에 여기서 다시 물어봐요.<br>기억났으면 30일 뒤, 가물가물했으면 7일 뒤에 한 번 더 물어요.</p>
        <div class="row"><a class="btn" href="#/">홈으로</a></div></div>`;
      return;
    }
    box.innerHTML = `<div class="progress-line"><span>남은 논문 ${queue.length}편</span></div>
      <div class="card flash-card">
        <div class="small muted">완독 ${esc(paper.finished_at || "")}</div>
        <div class="flash-q" style="margin-top:8px">${esc(paper.title)}</div>
        ${reference ? `
          <div class="flash-a"><h3>내가 쓴 것</h3><p style="margin-top:4px">${esc(mine)}</p>
            <h3 style="margin-top:14px">${reference.source === "note" ? "노트의 한 문장 요약" : "논문 초록 (노트에 요약 줄이 없어요)"}</h3>
            <div class="md" style="margin-top:4px">${renderMarkdown(reference.text || "비교할 내용이 없어요.")}</div></div>
          <div class="flash-foot"><div class="grade-row" style="grid-template-columns:repeat(2,1fr)">
            <button class="btn" data-recall="hazy">가물가물했음 <small>7일 뒤 다시</small></button>
            <button class="btn primary" data-recall="good">핵심은 기억났음 <small style="color:inherit;opacity:.85">30일 뒤 다시</small></button></div>
            <p class="small muted" style="margin-top:10px;text-align:center"><a href="#/paper/${paper.id}">노트 열어보기</a></p></div>`
        : `<form id="recall-form" class="stack" style="margin-top:16px">
            <label class="field"><span>노트를 보지 않고, 이 논문이 무엇을 어떻게 해서 어떤 결과를 얻었는지</span>
              <textarea class="textarea" name="text" rows="4" required maxlength="2000" placeholder="기억나는 만큼만 적어도 돼요."></textarea></label>
            <button class="btn primary" type="submit">노트와 비교하기</button></form>`}
      </div>`;
    box.querySelector("textarea")?.focus();
  };

  box.addEventListener("submit", async (e) => {
    e.preventDefault();
    mine = new FormData(e.target).get("text").trim();
    if (!mine) return;
    try {
      reference = await api(`/api/recall/${queue[0].id}/reference`);
    } catch (err) {
      toast(err.message, "error");
    }
    if (alive()) draw();
  });
  box.addEventListener("click", async (e) => {
    const grade = e.target.closest("[data-recall]")?.dataset.recall;
    if (!grade) return;
    try {
      await api(`/api/recall/${queue[0].id}`, { method: "POST", body: { text: mine, grade } });
      queue.shift();
      mine = "";
      reference = null;
    } catch (err) {
      toast(err.message, "error");
    }
    if (alive()) draw();
  });
  draw();
}

/** Run a flashcard session. `persist: false` is practice: nothing is sent, the schedule is untouched. */
function session(box, queue, { persist, alive, waiting = 0 }) {
  const total = queue.length;
  let done = 0;
  let revealed = false;
  let busy = false;
  let fixing = false;
  let last = null;  // 방금 평가한 카드 (되돌리기용)

  function draw() {
    const card = queue[0];
    if (card && fixing) {
      box.innerHTML = `<div class="card flash-card"><div class="small muted" style="margin-bottom:10px">${esc(card.paper_title)}</div>${cardForm(card)}</div>`;
      box.querySelector("input").focus();
      return;
    }
    if (!card) {
      box.innerHTML = `<div class="empty"><h3>${waiting ? "이번 묶음 끝" : persist ? "오늘 복습 끝" : "연습 끝"}</h3>
        <p>${done}장을 ${persist ? "복습" : "다시 확인"}했어요.${waiting ? ` 아직 ${waiting}장이 남아 있어요. 여기서 멈춰도 내일 다시 나와요.` : ""}</p>
        <div class="row">${waiting ? `<button class="btn primary" id="next-batch">다음 ${Math.min(waiting, SESSION)}장 계속</button>` : ""}
          <a class="btn ${waiting ? "" : "primary"}" href="#/">홈으로</a><a class="btn" href="#/review?tab=weak">약점 보기</a>
          ${persist && last ? `<button class="btn ghost" id="undo-grade">마지막 평가 되돌리기</button>` : ""}</div></div>`;
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
        <span>남은 카드 ${queue.length}장</span>
        ${persist && last ? `<button class="linkish" id="undo-grade" title="방금 한 평가를 취소하고 그 카드를 다시 봐요">방금 평가 되돌리기 <kbd>u</kbd></button>` : ""}</div>
      <div class="card flash-card">
        <a class="small muted" href="#/paper/${card.paper_id}">${esc(card.paper_title)}</a>
        <div class="flash-q" style="margin-top:10px">${esc(card.question)}</div>
        ${revealed ? `<div class="flash-a md">${renderMarkdown(card.answer)}</div>` : ""}
        <div class="flash-foot">${revealed ? buttons : `<button class="btn primary" id="reveal" style="width:100%">답 보기 <kbd>Space</kbd></button>`}</div>
      </div>
      ${revealed ? `<p style="text-align:center;margin-top:10px"><button class="linkish" id="fix-card">카드 내용이 틀렸거나 어색한가요? 고치기</button></p>` : ""}
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
      last = { id: card.id, grade: value };
      revealed = false;
    } catch (err) {
      toast(err.message, "error");
    }
    busy = false;
    if (!alive()) return;
    draw();
    if (persist) refreshDueBadge();
  }

  async function undo() {
    if (!persist || !last || busy) return;
    busy = true;
    try {
      const card = await api("/api/review/undo", { method: "POST" });
      if (last.grade === "again") {
        const requeued = queue.findIndex((c) => c.id === last.id);
        if (requeued >= 0) queue.splice(requeued, 1);
      } else done--;
      queue.unshift(card);
      last = null;
      revealed = true;  // 답은 이미 본 카드다. 바로 다시 평가할 수 있게 한다
      toast("평가를 되돌렸어요.");
    } catch (err) {
      last = null;
      toast(err.message, "error");
    }
    busy = false;
    if (!alive()) return;
    draw();
    refreshDueBadge();
  }

  box.addEventListener("click", (e) => {
    if (e.target.closest("#next-batch")) return window.dispatchEvent(new HashChangeEvent("hashchange"));
    if (e.target.closest("#undo-grade")) return undo();
    const t = e.target.closest("[data-grade],#reveal,#fix-card,[data-card-cancel]");
    if (!t) return;
    if (t.id === "reveal") { revealed = true; draw(); }
    else if (t.id === "fix-card") { fixing = true; draw(); }
    else if ("cardCancel" in t.dataset) { fixing = false; draw(); }
    else grade(t.dataset.grade);
  });
  box.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const { card } = await submitCardForm(e.target);
      Object.assign(queue[0], { question: card.question, answer: card.answer });
      fixing = false;
      toast("카드를 고쳤어요.");
    } catch (err) {
      toast(err.message, "error");
    }
    if (alive()) draw();
  });
  const onKey = (e) => {
    if (fixing || e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    if (e.key === "u" && last) return undo();
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
  if (tab === "recall") return recallView(root, alive);

  const practice = tab === "practice";
  const all = practice ? (await api("/api/review/weak")).cards : await api("/api/review/due");
  const queue = practice ? all : all.slice(0, SESSION);
  const waiting = all.length - queue.length;
  if (!queue.length) {
    root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1></div></div>${tabs(practice ? "weak" : "due")}
      <div class="empty"><h3>${practice ? "연습할 카드가 없어요" : "오늘 복습할 카드가 없어요"}</h3>
      <p>노트에 <code>Q: 질문</code> / <code>A: 답</code>을 적으면 카드가 만들어져요.<br>
      맞힌 카드는 1 → 3 → 7 → 14 → 30 → 60일 간격으로 다시 나와요.</p>
      <div class="row"><a class="btn" href="#/library">라이브러리로</a></div></div></div>`;
    return;
  }
  root.innerHTML = `<div class="page"><div class="page-head"><div><h1>복습</h1>
    <p>${practice ? "자주 틀린 카드만 모아서 다시 봐요." : waiting ? `밀린 카드 ${all.length}장 중 ${queue.length}장을 먼저 봐요. 한 번에 다 하지 않아도 돼요.` : "답을 떠올려 본 다음 확인하세요."}</p></div></div>
    ${tabs(practice ? "weak" : "due")}<div class="flash" id="flash"></div></div>`;
  return session($("#flash", root), queue, { persist: !practice, alive, waiting });
}
