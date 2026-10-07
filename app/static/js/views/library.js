import { api, esc, toast, authorsShort, tagsOf, statusSelect, STATUS, $ } from "../util.js";

const PAGE = 100;
const state = { status: "all", q: "", tag: "", sort: "updated" };
const SORTS = {
  updated: ["최근 수정순", (a, b) => (b.updated_at || "").localeCompare(a.updated_at || "")],
  added: ["추가한 순", (a, b) => b.id - a.id],
  year: ["발표 연도순", (a, b) => (b.year || 0) - (a.year || 0)],
  title: ["제목순", (a, b) => a.title.localeCompare(b.title)],
};

function row(p) {
  const tags = tagsOf(p).map((t) => `<button class="chip tag ${state.tag === t ? "on" : ""}" data-tag="${esc(t)}">${esc(t)}</button>`).join(" ");
  const note = p.has_note ? `<span class="chip">노트</span>` : p.note_requested ? `<span class="chip warn">노트 요청됨</span>` : "";
  return `
    <div class="paper-row">
      <div><a class="paper-title" href="#/paper/${p.id}">${esc(p.title)}</a>
        <div class="paper-meta">${esc([authorsShort(p.authors), p.year].filter(Boolean).join(" · "))}</div>
        ${tags ? `<div class="row" style="margin-top:6px;gap:4px">${tags}</div>` : ""}</div>
      <div class="paper-side">${note}${statusSelect(p)}</div>
    </div>`;
}

export async function render(root) {
  let papers = await api("/api/papers");

  root.innerHTML = `
    <div class="page">
      <div class="page-head"><div><h1>라이브러리</h1><p id="lib-sub"></p></div>
        <div class="head-actions">
          <button class="btn" id="add-btn">직접 추가</button>
          <a class="btn" href="/api/export.bib" download>BibTeX</a>
          <a class="btn" href="/api/export.json" download>백업</a>
          <button class="btn" id="import-btn">가져오기</button>
          <input type="file" id="import-file" accept="application/json,.json" class="hidden">
        </div></div>
      <div class="toolbar">
        <div class="tabs" id="status-tabs"></div>
        <div class="grow"></div>
        <input class="input" id="lib-q" placeholder="제목, 저자, 태그, 노트 본문" style="max-width:260px" value="${esc(state.q)}">
        <select class="select" id="lib-sort" aria-label="정렬">${Object.entries(SORTS).map(([k, [label]]) => `<option value="${k}" ${state.sort === k ? "selected" : ""}>${label}</option>`).join("")}</select>
      </div>
      <div id="lib-list"></div>
      <div id="note-hits"></div>
    </div>
    <dialog id="add-dialog"><h2>논문 직접 추가</h2>
      <p class="muted small" style="margin-bottom:10px">arXiv 논문은 검색 화면에서 ID나 링크를 붙여넣는 편이 빨라요. 책·블로그·arXiv에 없는 논문은 여기서 추가하세요.</p>
      <form id="add-form" method="dialog">
        <label class="field"><span>제목</span><input class="input" name="title" required maxlength="500"></label>
        <label class="field"><span>저자</span><input class="input" name="authors" placeholder="쉼표로 구분"></label>
        <div class="row"><label class="field" style="width:110px"><span>연도</span><input class="input" name="year" type="number" min="1900" max="2100"></label>
          <label class="field grow"><span>링크</span><input class="input" name="url" type="url" placeholder="https://"></label></div>
        <label class="field"><span>태그</span><input class="input" name="tags" placeholder="쉼표로 구분"></label>
        <div class="dialog-actions"><button class="btn" type="button" id="add-cancel">취소</button><button class="btn primary" type="submit">추가</button></div>
      </form></dialog>`;

  const page = $(".page", root);  // #view는 화면이 바뀌어도 남으므로 리스너는 교체되는 노드에 건다
  const draw = () => {
    const counts = { all: papers.length, to_read: 0, reading: 0, done: 0 };
    papers.forEach((p) => counts[p.status]++);
    $("#lib-sub", root).textContent = `논문 ${papers.length}편 · 완독 ${counts.done}편`;
    $("#status-tabs", root).innerHTML = [["all", "전체"], ...Object.entries(STATUS)]
      .map(([k, label]) => `<button class="tab" data-status="${k}" aria-pressed="${state.status === k}">${label}<span class="n">${counts[k]}</span></button>`).join("")
      + (state.tag ? `<button class="tab" data-tag="" aria-pressed="true">태그: ${esc(state.tag)} ✕</button>` : "");

    const q = state.q.toLowerCase();
    const shown = papers
      .filter((p) => state.status === "all" || p.status === state.status)
      .filter((p) => !state.tag || tagsOf(p).includes(state.tag))
      .filter((p) => !q || `${p.title} ${p.authors} ${p.tags} ${p.arxiv_id || ""}`.toLowerCase().includes(q))
      .sort(SORTS[state.sort][1]);

    const list = $("#lib-list", root);
    if (!papers.length) {
      list.innerHTML = `<div class="empty"><h3>아직 저장한 논문이 없어요</h3><p>로드맵에서 트랙을 고르거나 arXiv에서 검색해 저장하세요.</p>
        <div class="row"><a class="btn primary" href="#/roadmap">로드맵 보기</a><a class="btn" href="#/search">arXiv 검색</a></div></div>`;
    } else if (!shown.length) {
      list.innerHTML = `<div class="empty" style="padding:24px"><h3>제목·저자·태그가 맞는 논문이 없어요</h3><div class="row"><button class="btn" id="clear-filters">필터 지우기</button></div></div>`;
    } else {
      // 한 번에 PAGE편만 그리고, 목록 끝이 화면에 들어오면 다음 묶음을 붙인다
      let drawn = 0;
      watcher.disconnect();
      list.innerHTML = "";
      const more = () => {
        list.querySelector("#lib-more")?.remove();
        list.insertAdjacentHTML("beforeend", shown.slice(drawn, drawn + PAGE).map(row).join(""));
        drawn = Math.min(drawn + PAGE, shown.length);
        if (drawn < shown.length) {
          list.insertAdjacentHTML("beforeend", `<div class="row" id="lib-more" style="justify-content:center;margin-top:12px">
            <button class="btn">${shown.length - drawn}편 더 보기</button></div>`);
          watcher.observe(list.querySelector("#lib-more"));
        }
      };
      nextChunk = more;
      more();
    }
  };
  let nextChunk = () => {};
  const watcher = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) nextChunk(); }, { rootMargin: "600px" });
  draw();

  page.addEventListener("click", (e) => {
    if (e.target.closest("#lib-more")) return nextChunk();
    const t = e.target.closest("[data-status],[data-tag],#clear-filters");
    if (!t) return;
    if (t.id === "clear-filters") { Object.assign(state, { status: "all", q: "", tag: "" }); $("#lib-q", root).value = ""; searchNotes(); }
    else if (t.dataset.status) state.status = t.dataset.status;
    else state.tag = state.tag === t.dataset.tag ? "" : t.dataset.tag;
    draw();
  });
  // 노트·서베이 본문 검색: 입력이 멈춘 뒤에 한 번만 요청한다
  let searchTimer = null;
  let searchSeq = 0;
  const mark = (text, q) => {
    const i = text.toLowerCase().indexOf(q.toLowerCase());
    return i < 0 ? esc(text) : `${esc(text.slice(0, i))}<mark>${esc(text.slice(i, i + q.length))}</mark>${esc(text.slice(i + q.length))}`;
  };
  const searchNotes = () => {
    clearTimeout(searchTimer);
    const box = $("#note-hits", root);
    const q = state.q;
    const seq = ++searchSeq;
    if (q.length < 2) { box.innerHTML = ""; return; }
    searchTimer = setTimeout(async () => {
      const hits = await api(`/api/notes/search?q=${encodeURIComponent(q)}`).catch(() => []);
      if (seq !== searchSeq || !box.isConnected) return;
      box.innerHTML = hits.length ? `<h2 style="margin:24px 0 10px">노트 본문에서 찾음 <span class="small muted">${hits.length}건</span></h2>
        ${hits.map((h) => `<div class="paper-row"><div>
          <a class="paper-title" href="${h.kind === "note" ? `#/paper/${h.paper_id}` : `#/surveys/${esc(h.name)}`}">${esc(h.title)}</a>
          ${h.kind === "survey" ? ` <span class="chip">서베이</span>` : ""}
          ${h.snippets.map((line) => `<div class="abstract" style="margin-top:4px">${mark(line, q)}</div>`).join("")}</div></div>`).join("")}` : "";
    }, 250);
  };
  $("#lib-q", root).addEventListener("input", (e) => { state.q = e.target.value.trim(); draw(); searchNotes(); });
  searchNotes();
  $("#lib-sort", root).addEventListener("change", (e) => { state.sort = e.target.value; draw(); });

  page.addEventListener("change", async (e) => {
    if (!e.target.matches(".status-select")) return;
    const id = Number(e.target.dataset.id);
    try {
      const updated = await api(`/api/papers/${id}`, { method: "PATCH", body: { status: e.target.value } });
      papers = papers.map((p) => (p.id === id ? updated : p));
      toast(updated.status === "done" ? "완독으로 표시했어요." : `'${STATUS[updated.status]}'(으)로 바꿨어요.`);
    } catch (err) {
      toast(err.message, "error");
    }
    draw();
  });

  const dialog = $("#add-dialog", root);
  const form = $("#add-form", root);
  $("#add-btn", root).addEventListener("click", () => dialog.showModal());
  $("#add-cancel", root).addEventListener("click", () => dialog.close());
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    data.year = data.year ? Number(data.year) : null;
    try {
      const { paper, created } = await api("/api/papers", { method: "POST", body: data });
      dialog.close();
      form.reset();
      toast(created ? "추가했어요." : "이미 라이브러리에 있는 논문이에요.");
      location.hash = `#/paper/${paper.id}`;
    } catch (err) {
      toast(err.message, "error");
    }
  });

  const file = $("#import-file", root);
  $("#import-btn", root).addEventListener("click", () => file.click());
  file.addEventListener("change", async () => {
    if (!file.files[0]) return;
    try {
      const result = await api("/api/import", { method: "POST", body: JSON.parse(await file.files[0].text()) });
      toast(`${result.added}편 추가, ${result.skipped}편은 이미 있어서 건너뛰었어요.${result.tracks_added ? ` 내 트랙 ${result.tracks_added}개도 복원했어요.` : ""}`);
      papers = await api("/api/papers");
      draw();
    } catch (err) {
      toast(err instanceof SyntaxError ? "JSON 파일을 읽지 못했어요." : err.message, "error");
    }
    file.value = "";
  });
  return () => watcher.disconnect();
}
