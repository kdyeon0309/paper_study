const results = document.getElementById("results");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const searchBtn = document.getElementById("search-btn");
const paperList = document.getElementById("paper-list");

const STATUS_LABELS = { to_read: "읽을 예정", reading: "읽는 중", done: "완료" };
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let lastResults = [];

searchForm.onsubmit = async (e) => {
  e.preventDefault();
  const q = searchInput.value.trim();
  if (!q) return;
  searchBtn.disabled = true;
  results.innerHTML = `<p class="empty">arXiv 검색 중…</p>`;
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    if (!res.ok) throw new Error((await res.json()).detail || res.status);
    lastResults = await res.json();
    results.innerHTML = lastResults.map((p, i) => `
      <div class="result-card">
        <div class="paper-title"><a href="${esc(p.url)}" target="_blank">${esc(p.title)}</a></div>
        <div class="paper-meta">${esc(p.authors)} · ${p.year}</div>
        <div class="abstract">${esc(p.abstract)}</div>
        <button class="save-btn" data-i="${i}">라이브러리에 저장</button>
      </div>`).join("") || `<p class="empty">결과 없음</p>`;
  } catch (err) {
    results.innerHTML = `<p class="error">검색 실패: ${esc(err.message)}</p>`;
  } finally {
    searchBtn.disabled = false;
  }
};

results.onclick = async (e) => {
  if (!e.target.matches(".save-btn")) return;
  const p = lastResults[e.target.dataset.i];
  await fetch("/api/papers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: p.title, authors: p.authors, year: p.year, url: p.url, summary: p.abstract.slice(0, 200) }),
  });
  e.target.textContent = "저장됨 ✓";
  e.target.disabled = true;
  loadPapers();
};

async function loadPapers() {
  const papers = await (await fetch("/api/papers")).json();
  paperList.innerHTML = papers.map((p) => `
    <div class="paper-card">
      <div class="paper-title">${p.url ? `<a href="${esc(p.url)}" target="_blank">${esc(p.title)}</a>` : esc(p.title)}</div>
      <div class="paper-meta">${esc([p.authors, p.year].filter(Boolean).join(" · "))}</div>
      ${p.summary ? `<div class="paper-summary">${esc(p.summary)}</div>` : ""}
      <div class="paper-footer">
        <span class="tags">${esc(p.tags)}</span>
        ${p.has_note
          ? `<button class="note-btn" data-id="${p.id}">노트 📝</button>`
          : `<span class="no-note" title="Claude Code에서: '논문 ${p.id}번 노트 써줘' → notes/${p.id}.md">노트 없음</span>`}
        <select data-id="${p.id}" class="status-select">
          ${Object.entries(STATUS_LABELS).map(([v, l]) =>
            `<option value="${v}" ${p.status === v ? "selected" : ""}>${l}</option>`).join("")}
        </select>
        <button class="del-btn" data-id="${p.id}">삭제</button>
      </div>
    </div>`).join("") || `<p class="empty">아직 저장된 논문이 없어요.<br>왼쪽에서 검색해 저장하거나 ＋로 추가하세요.</p>`;
}

const noteDialog = document.getElementById("note-dialog");
document.getElementById("note-close").onclick = () => noteDialog.close();

paperList.onclick = async (e) => {
  const id = e.target.dataset.id;
  if (e.target.matches(".del-btn")) {
    await fetch(`/api/papers/${id}`, { method: "DELETE" });
    loadPapers();
  } else if (e.target.matches(".note-btn")) {
    const md = await (await fetch(`/api/notes/${id}`)).text();
    document.getElementById("note-content").innerHTML = marked.parse(md);
    noteDialog.showModal();
  }
};

paperList.onchange = async (e) => {
  if (!e.target.matches(".status-select")) return;
  await fetch(`/api/papers/${e.target.dataset.id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status: e.target.value }),
  });
};

// 수동 추가 다이얼로그
const dialog = document.getElementById("paper-dialog");
const paperForm = document.getElementById("paper-form");
document.getElementById("add-paper-btn").onclick = () => dialog.showModal();
document.getElementById("paper-cancel").onclick = () => dialog.close();
paperForm.onsubmit = async () => {
  const data = Object.fromEntries(new FormData(paperForm));
  data.year = data.year ? Number(data.year) : null;
  await fetch("/api/papers", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  paperForm.reset();
  loadPapers();
};

loadPapers();
