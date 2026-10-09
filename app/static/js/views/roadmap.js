import { api, esc, toast, confirmDialog, authorsShort, DEPTH, STATUS, $ } from "../util.js";
import { roadmapTabs } from "./practice.js";

const KINDS = ["기초", "논문", "새 영역"];
const state = { kind: "all", open: null, editingWhy: null };
let showStartHint = false;

function itemRow(track, p, i) {
  const title = p.paper_id
    ? `<a class="paper-title" href="#/paper/${p.paper_id}">${esc(p.title)}</a>`
    : `<a class="paper-title" href="https://arxiv.org/abs/${esc(p.arxiv_id)}" target="_blank" rel="noopener">${esc(p.title)}</a>`;
  const editing = state.editingWhy === `${track.key}|${p.arxiv_id}`;
  const why = editing
    ? `<input class="input why-input" data-track="${esc(track.key)}" data-id="${esc(p.arxiv_id)}" value="${esc(p.why)}" maxlength="300" placeholder="이 논문을 읽는 이유" style="margin-top:4px">`
    : p.why ? `<div class="why">${esc(p.why)}</div>` : "";
  const tools = track.editable ? `<span class="item-tools" data-track="${esc(track.key)}" data-id="${esc(p.arxiv_id)}">
      <button class="icon-btn" data-act="up" aria-label="위로" ${i === 0 ? "disabled" : ""}>↑</button>
      <button class="icon-btn" data-act="down" aria-label="아래로" ${i === track.papers.length - 1 ? "disabled" : ""}>↓</button>
      <button class="icon-btn" data-act="why" aria-label="읽는 이유 수정" title="읽는 이유 수정">✎</button>
      <button class="icon-btn" data-act="remove" aria-label="트랙에서 빼기" title="트랙에서 빼기">✕</button></span>` : "";
  const side = p.paper_id
    ? `${p.depth ? `<span class="chip depth-chip" title="이해 깊이">${p.depth} ${DEPTH[p.depth].short}</span>` : ""}<span class="chip ${esc(p.status)}">${STATUS[p.status]}</span>`
    : `<button class="btn sm" data-add="${esc(p.arxiv_id)}">추가</button>`;
  return `<li><span class="n">${i + 1}</span>
    <div>${title}<div class="paper-meta">${esc([authorsShort(p.authors, 2), p.year].filter(Boolean).join(" · "))}</div>${why}</div>
    <div class="row" style="flex-wrap:nowrap">${tools}${side}</div></li>`;
}

function trackCard(t) {
  const done = t.papers.filter((p) => p.status === "done").length;
  const missing = t.papers.filter((p) => !p.paper_id).length;
  const pct = t.papers.length ? (done / t.papers.length) * 100 : 0;
  const deep = t.papers.filter((p) => p.depth >= 3).length;
  const key = esc(t.key);
  return `<details class="card track" data-key="${key}" ${state.open.has(t.key) ? "open" : ""}>
    <summary><div class="track-head">
      <div><span class="chip">${esc(t.kind)}</span>${t.editable ? ` <span class="chip reading">내 트랙</span>` : ""}${showStartHint && t.start_hint ? ` <span class="chip done">추천 시작</span>` : ""}
        <strong style="font-size:16px;margin-left:4px">${esc(t.name)}</strong>
        ${t.description ? `<div class="small muted" style="margin-top:4px">${esc(t.description)}</div>` : ""}
        ${showStartHint && t.start_hint ? `<div class="small" style="margin-top:4px;color:var(--good)">${esc(t.start_hint)}</div>` : ""}</div>
      <span class="small muted">${done} / ${t.papers.length}편 완독${deep ? ` · 유도 이상 ${deep}편` : ""}</span>
      <div class="meter"><i style="width:${pct}%"></i></div></div></summary>
    ${t.papers.length ? `<ol class="track-list">${t.papers.map((p, i) => itemRow(t, p, i)).join("")}</ol>`
      : `<p class="muted" style="margin-top:14px">아직 논문이 없어요. 아래에서 arXiv ID나 링크로 추가하세요.</p>`}
    ${t.editable ? `<form class="add-paper-form" data-track="${key}">
        <input class="input" name="ref" placeholder="arXiv ID 또는 링크" required maxlength="200" aria-label="arXiv ID 또는 링크">
        <input class="input" name="why" placeholder="읽는 이유 (선택)" maxlength="300" aria-label="읽는 이유">
        <button class="btn" type="submit">트랙에 넣기</button></form>` : ""}
    <div class="row" style="margin-top:10px">
      ${missing ? `<button class="btn sm" data-add-all="${key}">남은 ${missing}편 모두 라이브러리에 추가</button>` : ""}
      ${t.editable ? `<span class="grow"></span><button class="btn sm ghost" data-edit-track="${key}">이름·설명 수정</button>
        <button class="btn sm ghost danger" data-delete-track="${key}">트랙 삭제</button>` : ""}</div>
  </details>`;
}

export async function render(root, { alive }) {
  let tracks = await api("/api/roadmaps");
  const nothingStarted = !tracks.some((t) => t.papers.some((p) => p.paper_id));
  if (state.open === null) {
    const inProgress = tracks.find((t) => t.papers.some((p) => p.paper_id) && t.papers.some((p) => p.status !== "done"));
    // 아직 아무 트랙도 시작하지 않았다면 추천 트랙을 펼쳐 둔다
    state.open = new Set([(inProgress || (nothingStarted && tracks.find((t) => t.start_hint)) || tracks[0])?.key]);
  }
  showStartHint = nothingStarted;

  root.innerHTML = `<div class="page">
    <div class="page-head"><div><h1>로드맵</h1><p>분야별로 읽는 순서를 정리한 목록이에요. 기본 트랙의 논문은 모두 arXiv에서 확인한 것만 넣었어요.</p></div>
      <div class="head-actions"><button class="btn primary" id="new-track">새 트랙</button></div></div>
    ${roadmapTabs("read")}
    <div class="toolbar"><div class="tabs" id="kind-tabs"></div></div>
    <div id="tracks"></div></div>
    <dialog id="track-dialog"><h2 id="track-dialog-title"></h2>
      <form id="track-form" method="dialog">
        <label class="field"><span>이름</span><input class="input" name="name" required maxlength="80" placeholder="예: Open-vocabulary detection"></label>
        <label class="field"><span>종류</span><select class="select" name="kind" style="width:100%">${KINDS.map((k) => `<option>${k}</option>`).join("")}</select></label>
        <label class="field"><span>설명</span><textarea class="textarea" name="description" rows="2" maxlength="300" placeholder="이 트랙으로 무엇을 익히려는지"></textarea></label>
        <div class="dialog-actions"><button class="btn" type="button" id="track-cancel">취소</button><button class="btn primary" type="submit">저장</button></div>
      </form></dialog>`;

  const page = $(".page", root);
  const dialog = $("#track-dialog", root);
  const form = $("#track-form", root);
  let editingKey = null;

  function draw() {
    const kinds = ["all", ...KINDS.filter((k) => tracks.some((t) => t.kind === k))];
    $("#kind-tabs", root).innerHTML = kinds
      .map((k) => `<button class="tab" data-kind="${esc(k)}" aria-pressed="${state.kind === k}">${k === "all" ? "전체" : esc(k)}</button>`).join("");
    $("#tracks", root).innerHTML = tracks.filter((t) => state.kind === "all" || t.kind === state.kind).map(trackCard).join("");
    $(".why-input", root)?.focus();
  }

  async function reload() {
    tracks = await api("/api/roadmaps");
    if (alive()) draw();
  }

  /** Run one change against the API, report failures, then redraw from the server's state. */
  async function change(path, options, okMessage) {
    try {
      const result = await api(path, options);
      if (okMessage) toast(typeof okMessage === "function" ? okMessage(result) : okMessage);
    } catch (err) {
      toast(err.message, "error");
    }
    await reload();
  }

  draw();

  function openDialog(track) {
    editingKey = track ? track.key : null;
    $("#track-dialog-title", root).textContent = track ? "트랙 수정" : "새 트랙";
    form.reset();
    if (track) {
      form.elements.name.value = track.name;
      form.elements.kind.value = track.kind;
      form.elements.description.value = track.description || "";
    }
    dialog.showModal();
  }
  $("#new-track", root).addEventListener("click", () => openDialog(null));
  $("#track-cancel", root).addEventListener("click", () => dialog.close());
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(form));
    try {
      if (editingKey) {
        await api(`/api/roadmaps/${editingKey}`, { method: "PATCH", body });
      } else {
        const created = await api("/api/roadmaps", { method: "POST", body });
        state.open.add(created.key);
        state.kind = "all";
      }
      dialog.close();
      toast(editingKey ? "트랙을 수정했어요." : "트랙을 만들었어요. 논문을 넣어보세요.");
      await reload();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  page.addEventListener("click", async (e) => {
    const t = e.target.closest("[data-kind],[data-add],[data-add-all],[data-act],[data-edit-track],[data-delete-track]");
    if (!t) return;
    const d = t.dataset;
    if (d.kind) {
      state.kind = d.kind;
      draw();
    } else if (d.add || d.addAll) {
      const ids = d.add ? [d.add] : tracks.find((x) => x.key === d.addAll).papers.filter((p) => !p.paper_id).map((p) => p.arxiv_id);
      t.disabled = true;
      t.textContent = "추가하는 중…";
      await change("/api/papers/arxiv", { method: "POST", body: { ids } },
        (r) => (r.failed.length ? `${r.added.length}편 추가, ${r.failed.length}편은 arXiv에서 찾지 못했어요.` : `${r.added.length}편을 라이브러리에 추가했어요.`));
    } else if (d.act) {
      const { track, id } = t.parentElement.dataset;
      const path = `/api/roadmaps/${track}/papers/${id}`;
      if (d.act === "why") { state.editingWhy = `${track}|${id}`; draw(); }
      else if (d.act === "remove") await change(path, { method: "DELETE" }, "트랙에서 뺐어요. 라이브러리에는 그대로 있어요.");
      else await change(path, { method: "PATCH", body: { move: d.act === "up" ? -1 : 1 } });
    } else if (d.editTrack) {
      e.preventDefault();
      openDialog(tracks.find((x) => x.key === d.editTrack));
    } else if (d.deleteTrack) {
      const track = tracks.find((x) => x.key === d.deleteTrack);
      const ok = await confirmDialog({ title: `'${track.name}' 트랙을 삭제할까요?`, text: "트랙 목록만 지워져요. 라이브러리의 논문과 노트는 그대로 있어요.", ok: "삭제" });
      if (ok) await change(`/api/roadmaps/${track.key}`, { method: "DELETE" }, "트랙을 삭제했어요.");
    }
  });

  page.addEventListener("submit", async (e) => {
    if (!e.target.matches(".add-paper-form")) return;
    e.preventDefault();
    const button = e.target.querySelector("button");
    button.disabled = true;
    button.textContent = "찾는 중…";
    await change(`/api/roadmaps/${e.target.dataset.track}/papers`, { method: "POST", body: Object.fromEntries(new FormData(e.target)) }, "트랙에 넣었어요.");
  });

  // 읽는 이유: Enter나 포커스 이동으로 저장, Esc로 취소
  const saveWhy = async (input) => {
    if (state.editingWhy === null) return;
    state.editingWhy = null;
    await change(`/api/roadmaps/${input.dataset.track}/papers/${input.dataset.id}`, { method: "PATCH", body: { why: input.value } });
  };
  page.addEventListener("keydown", (e) => {
    if (!e.target.matches(".why-input")) return;
    if (e.key === "Enter") { e.preventDefault(); saveWhy(e.target); }
    else if (e.key === "Escape") { state.editingWhy = null; draw(); }
  });
  page.addEventListener("focusout", (e) => { if (e.target.matches(".why-input")) saveWhy(e.target); });

  page.addEventListener("toggle", (e) => {
    const key = e.target.dataset?.key;
    if (key) e.target.open ? state.open.add(key) : state.open.delete(key);
  }, true);
}
