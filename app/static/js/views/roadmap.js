import { api, esc, toast, authorsShort, STATUS, $ } from "../util.js";

const state = { kind: "all", open: null };

export async function render(root, { alive }) {
  let tracks = await api("/api/roadmaps");
  if (state.open === null) {
    const inProgress = tracks.find((t) => t.papers.some((p) => p.paper_id) && t.papers.some((p) => p.status !== "done"));
    state.open = new Set([(inProgress || tracks[0])?.key]);
  }
  const kinds = ["all", ...new Set(tracks.map((t) => t.kind))];

  root.innerHTML = `<div class="page">
    <div class="page-head"><div><h1>로드맵</h1><p>분야별로 읽는 순서를 정리한 목록이에요. 논문은 모두 arXiv에서 확인한 것만 넣었어요.</p></div></div>
    <div class="toolbar"><div class="tabs" id="kind-tabs"></div></div>
    <div id="tracks"></div></div>`;

  function draw() {
    $("#kind-tabs", root).innerHTML = kinds
      .map((k) => `<button class="tab" data-kind="${esc(k)}" aria-pressed="${state.kind === k}">${k === "all" ? "전체" : esc(k)}</button>`).join("");
    $("#tracks", root).innerHTML = tracks.filter((t) => state.kind === "all" || t.kind === state.kind).map((t) => {
      const done = t.papers.filter((p) => p.status === "done").length;
      const missing = t.papers.filter((p) => !p.paper_id).length;
      const items = t.papers.map((p, i) => `
        <li><span class="n">${i + 1}</span>
          <div>${p.paper_id
            ? `<a class="paper-title" href="#/paper/${p.paper_id}">${esc(p.title)}</a>`
            : `<a class="paper-title" href="https://arxiv.org/abs/${esc(p.arxiv_id)}" target="_blank" rel="noopener">${esc(p.title)}</a>`}
            <div class="paper-meta">${esc(authorsShort(p.authors, 2))} · ${p.year}</div>
            <div class="why">${esc(p.why)}</div></div>
          <div>${p.paper_id
            ? `<span class="chip ${esc(p.status)}">${STATUS[p.status]}</span>`
            : `<button class="btn sm" data-add="${esc(p.arxiv_id)}">추가</button>`}</div></li>`).join("");
      return `<details class="card track" data-key="${esc(t.key)}" ${state.open.has(t.key) ? "open" : ""}>
        <summary><div class="track-head">
          <div><span class="chip">${esc(t.kind)}</span> <strong style="font-size:16px;margin-left:4px">${esc(t.name)}</strong>
            <div class="small muted" style="margin-top:4px">${esc(t.description)}</div></div>
          <span class="small muted">${done} / ${t.papers.length}편 완독</span>
          <div class="meter"><i style="width:${(done / t.papers.length) * 100}%"></i></div></div></summary>
        <ol class="track-list">${items}</ol>
        ${missing ? `<div class="row" style="margin-top:8px"><button class="btn sm" data-add-all="${esc(t.key)}">남은 ${missing}편 모두 라이브러리에 추가</button></div>` : ""}
      </details>`;
    }).join("");
  }
  draw();

  async function add(ids, button) {
    button.disabled = true;
    button.textContent = "추가하는 중…";
    try {
      const result = await api("/api/papers/arxiv", { method: "POST", body: { ids } });
      toast(result.failed.length ? `${result.added.length}편 추가, ${result.failed.length}편은 arXiv에서 찾지 못했어요.` : `${result.added.length}편을 라이브러리에 추가했어요.`);
    } catch (err) {
      toast(err.message, "error");
    }
    tracks = await api("/api/roadmaps");
    if (alive()) draw();
  }

  const page = $(".page", root);
  page.addEventListener("click", (e) => {
    const t = e.target.closest("[data-kind],[data-add],[data-add-all]");
    if (!t) return;
    if (t.dataset.kind) { state.kind = t.dataset.kind; draw(); }
    else if (t.dataset.add) add([t.dataset.add], t);
    else add(tracks.find((x) => x.key === t.dataset.addAll).papers.filter((p) => !p.paper_id).map((p) => p.arxiv_id), t);
  });
  page.addEventListener("toggle", (e) => {
    const key = e.target.dataset?.key;
    if (key) e.target.open ? state.open.add(key) : state.open.delete(key);
  }, true);
}
