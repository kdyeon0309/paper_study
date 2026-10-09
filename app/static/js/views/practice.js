import { api, esc, toast, copy, renderMarkdown, $ } from "../util.js";

const LABEL = { todo: "시작 전", doing: "하는 중", done: "통과" };
const state = { open: null };

export const roadmapTabs = (active) => `<div class="toolbar"><div class="tabs">
  <a class="tab" href="#/roadmap" aria-pressed="${active === "read"}">읽기 순서</a>
  <a class="tab" href="#/practice" aria-pressed="${active === "practice"}">구현 과제</a></div></div>`;

export async function render(root, { alive }) {
  let items = await api("/api/exercises");
  const readmes = {};

  root.innerHTML = `<div class="page">
    <div class="page-head"><div><h1>구현 과제</h1>
      <p>읽기만으로는 채워지지 않는 기초를 손으로 채워요. numpy로 직접 짜고, 채점 스크립트로 확인해요.</p></div></div>
    ${roadmapTabs("practice")}
    <div class="card"><h2>하는 법</h2>
      <ol style="margin:8px 0 0;padding-left:20px;line-height:1.9">
        <li>과제를 펼쳐 <strong>'손으로 먼저'</strong>를 종이에 푼다. 여기를 건너뛰면 구현이 베끼기가 된다.</li>
        <li><code>solution_template.py</code>를 <code>solution.py</code>로 복사해 함수를 채운다.</li>
        <li>터미널에서 <code>check.py</code>를 돌린다. 모두 통과하면 여기서 '통과'로 표시한다.</li>
      </ol>
      <p class="small muted" style="margin-top:10px">채점기는 정답 코드를 보여주지 않아요. 손으로 계산한 값, 느리지만 명백히 맞는 구현, 수치 기울기와 비교해요.
        막히면 Claude Code에 답 대신 "힌트만" 또는 "내 코드에서 틀린 줄만"을 요청하세요. <code>pip install numpy</code>가 필요해요.</p></div>
    <div id="exercise-list" style="margin-top:12px"></div></div>`;

  const draw = () => {
    const done = items.filter((x) => x.status === "done").length;
    $("#exercise-list", root).innerHTML = `
      <div class="progress-line"><span>${done} / ${items.length} 통과</span><div class="meter"><i style="width:${(done / items.length) * 100}%"></i></div></div>
      ${items.map((x) => {
        const related = x.related.map((r) => (r.paper_id
          ? `<a href="#/paper/${r.paper_id}">${esc(r.title)}</a>`
          : `<a href="https://arxiv.org/abs/${esc(r.arxiv_id)}" target="_blank" rel="noopener">arXiv:${esc(r.arxiv_id)}</a>`)).join(", ");
        const open = state.open === x.key;
        return `<div class="card exercise" data-key="${esc(x.key)}">
          <div class="track-head">
            <div><span class="chip">${esc(x.kind)}</span> <span class="chip ${x.status === "done" ? "done" : x.status === "doing" ? "reading" : ""}">${LABEL[x.status]}</span>
              <strong style="font-size:16px;margin-left:4px">${esc(x.title)}</strong>
              <div class="small muted" style="margin-top:4px">${esc(x.summary)}</div>
              ${related ? `<div class="small muted" style="margin-top:2px">관련 논문: ${related}</div>` : ""}</div>
            <span class="small muted">약 ${x.minutes}분</span></div>
          <div class="row" style="margin-top:12px">
            <button class="btn sm" data-toggle>${open ? "문제 접기" : "문제 보기"}</button>
            <button class="btn sm" data-copy="cp ${esc(x.folder)}/solution_template.py ${esc(x.folder)}/solution.py">틀 복사 명령</button>
            <button class="btn sm" data-copy="python ${esc(x.folder)}/check.py">채점 명령</button>
            <span class="grow"></span>
            <select class="select" data-status aria-label="진행 상태" style="padding-top:4px;padding-bottom:4px">
              ${Object.entries(LABEL).map(([v, l]) => `<option value="${v}" ${x.status === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
          ${open ? `<div class="md" style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">${renderMarkdown(readmes[x.key] || "불러오는 중…")}</div>` : ""}
        </div>`;
      }).join("")}`;
  };
  draw();

  const list = $("#exercise-list", root);
  list.addEventListener("click", async (e) => {
    const key = e.target.closest(".exercise")?.dataset.key;
    if (!key) return;
    if (e.target.dataset.copy) {
      toast((await copy(e.target.dataset.copy)) ? `복사했어요: ${e.target.dataset.copy}` : "복사하지 못했어요.");
    } else if ("toggle" in e.target.dataset) {
      state.open = state.open === key ? null : key;
      draw();
      if (state.open && !readmes[key]) {
        readmes[key] = await api(`/api/exercises/${key}/readme`).catch(() => "문제를 불러오지 못했어요.");
        if (alive()) draw();
      }
    }
  });
  list.addEventListener("change", async (e) => {
    const key = e.target.closest(".exercise")?.dataset.key;
    if (!key || !("status" in e.target.dataset)) return;
    try {
      await api(`/api/exercises/${key}`, { method: "PATCH", body: { status: e.target.value } });
      if (e.target.value === "done") toast("통과로 표시했어요. 관련 논문의 이해 깊이도 올려보세요.");
      items = await api("/api/exercises");
    } catch (err) {
      toast(err.message, "error");
    }
    if (alive()) draw();
  });
  if (state.open && !readmes[state.open]) {
    readmes[state.open] = await api(`/api/exercises/${state.open}/readme`).catch(() => "");
    if (alive()) draw();
  }
}
