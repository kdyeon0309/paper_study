import { api, esc, toast, authorsShort, $ } from "../util.js";

const CATEGORIES = [
  ["", "전체 분야"],
  ["cs.CV", "cs.CV · 컴퓨터 비전"],
  ["cs.LG", "cs.LG · 머신러닝"],
  ["cs.AI", "cs.AI · 인공지능"],
  ["cs.CL", "cs.CL · 자연어 처리"],
  ["cs.RO", "cs.RO · 로보틱스"],
  ["eess.IV", "eess.IV · 영상 처리"],
];
const EXAMPLES = ["open vocabulary detection", "\"gaussian splatting\" slam", "vision language model grounding", "2304.08069"];

// 다른 화면에 다녀와도 검색 결과가 남아 있도록 모듈에 보관
const state = { q: "", sort: "relevance", cat: "cs.CV", items: [], total: 0, pageSize: 20, searched: false, error: "" };

function resultRow(item, i) {
  const meta = [authorsShort(item.authors), item.published, item.categories.split(",")[0], item.comment].filter(Boolean);
  const side = item.saved_id
    ? `<a class="chip done" href="#/paper/${item.saved_id}">저장됨 · 열기</a>`
    : `<button class="btn sm primary" data-save="${i}">저장</button>`;
  return `
    <div class="paper-row">
      <div><a class="paper-title" href="${esc(item.url)}" target="_blank" rel="noopener">${esc(item.title)}</a>
        <div class="paper-meta">${meta.map(esc).join(" · ")}</div></div>
      <div class="paper-side">${side}</div>
      <div class="abstract clamp" id="abs-${i}">${esc(item.abstract)}</div>
      <div><button class="linkish" data-more="${i}">초록 펼치기</button></div>
    </div>`;
}

function draw(root) {
  const list = $("#results", root);
  if (state.error) {
    list.innerHTML = `<div class="banner error">${esc(state.error)}</div>`;
  } else if (!state.searched) {
    list.innerHTML = `<div class="empty"><h3>arXiv에서 논문 찾기</h3>
      <p>키워드로 검색하거나, arXiv ID·링크를 붙여넣으면 그 논문을 바로 가져와요.<br>여러 단어는 모두 포함하는 논문을 찾고, 따옴표로 묶으면 구문으로 찾아요.</p>
      <div class="row">${EXAMPLES.map((q) => `<button class="tab" data-example="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>`;
  } else if (!state.items.length) {
    list.innerHTML = `<div class="empty"><h3>결과가 없어요</h3><p>단어를 줄이거나 분야를 '전체 분야'로 바꿔보세요.</p></div>`;
  } else {
    const more = state.items.length < state.total
      ? `<div class="row" style="justify-content:center;margin-top:16px"><button class="btn" id="more-btn">결과 더 보기</button></div>` : "";
    list.innerHTML = `<p class="small muted" style="margin:4px 2px 10px">${state.total.toLocaleString()}건 중 ${state.items.length}건</p>
      ${state.items.map(resultRow).join("")}${more}`;
  }
}

async function run(root, append = false) {
  const btn = $("#search-btn", root);
  btn.disabled = true;
  btn.textContent = "검색 중…";
  state.error = "";
  try {
    const params = new URLSearchParams({ q: state.q, sort: state.sort, cat: state.cat, start: append ? state.items.length : 0 });
    const data = await api(`/api/search?${params}`);
    state.items = append ? state.items.concat(data.items) : data.items;
    state.total = Math.max(data.total, state.items.length);
    state.searched = true;
  } catch (err) {
    state.error = err.message;
    if (!append) state.items = [];
  }
  if (!root.isConnected) return;
  btn.disabled = false;
  btn.textContent = "검색";
  draw(root);
}

export async function render(root, { query }) {
  root.innerHTML = `
    <div class="page">
      <div class="page-head"><div><h1>검색</h1><p>arXiv 공개 API를 사용해요. 비용도 API 키도 없어요.</p></div></div>
      <form class="search-form" id="search-form">
        <input class="input" id="search-input" placeholder="키워드, arXiv ID 또는 링크" value="${esc(state.q)}" autocomplete="off">
        <select class="select" id="search-cat" aria-label="분야">${CATEGORIES.map(([v, l]) => `<option value="${v}" ${state.cat === v ? "selected" : ""}>${l}</option>`).join("")}</select>
        <select class="select" id="search-sort" aria-label="정렬">
          <option value="relevance" ${state.sort === "relevance" ? "selected" : ""}>관련도순</option>
          <option value="recent" ${state.sort === "recent" ? "selected" : ""}>최신순</option></select>
        <button class="btn primary" id="search-btn" type="submit">검색</button>
      </form>
      <div id="results"></div>
    </div>`;
  draw(root);
  const input = $("#search-input", root);
  input.focus();

  const submit = () => {
    state.q = input.value.trim();
    state.cat = $("#search-cat", root).value;
    state.sort = $("#search-sort", root).value;
    if (state.q) run(root);
  };
  $("#search-form", root).addEventListener("submit", (e) => { e.preventDefault(); submit(); });
  $("#search-cat", root).addEventListener("change", submit);
  $("#search-sort", root).addEventListener("change", submit);

  $("#results", root).addEventListener("click", async (e) => {
    const t = e.target;
    if (t.dataset.example) {
      input.value = t.dataset.example;
      submit();
    } else if (t.id === "more-btn") {
      t.disabled = true;
      t.textContent = "불러오는 중…";
      run(root, true);
    } else if (t.dataset.more) {
      const clamped = $(`#abs-${t.dataset.more}`, root).classList.toggle("clamp");
      t.textContent = clamped ? "초록 펼치기" : "초록 접기";
    } else if (t.dataset.save) {
      const item = state.items[t.dataset.save];
      t.disabled = true;
      try {
        const { paper } = await api("/api/papers", { method: "POST", body: item });
        item.saved_id = paper.id;
        toast("라이브러리에 저장했어요.");
        t.outerHTML = `<a class="chip done" href="#/paper/${paper.id}">저장됨 · 열기</a>`;
      } catch (err) {
        t.disabled = false;
        toast(err.message, "error");
      }
    }
  });

  if (query.get("q") && query.get("q") !== state.q) {
    input.value = query.get("q");
    submit();
  }
}
