import { api, esc, toast, copy, confirmDialog, statusSelect, renderMarkdown, notePrompt, refreshDueBadge, STATUS, $ } from "../util.js";

const AUTOSAVE_MS = 1000;
const POLL_MS = 6000;

export async function render(root, { args, alive }) {
  const id = Number(args[0]);
  let { paper, note, cards, bibtex } = await api(`/api/papers/${id}`);
  let content = note.content;
  let mtime = note.mtime;
  let exists = note.exists;
  let editing = false;
  let dirty = false;
  let saving = false;
  let conflict = false;
  let timer = null;

  const meta = [paper.year, paper.categories, paper.comment].filter(Boolean).map(esc).join(" · ");
  root.innerHTML = `
    <div class="page wide">
      <a class="crumb" href="#/library">← 라이브러리</a>
      <div class="paper-head">
        <h1>${esc(paper.title)}</h1>
        ${paper.authors ? `<div class="paper-meta">${esc(paper.authors)}</div>` : ""}
        ${meta ? `<div class="paper-meta">${meta}</div>` : ""}
        <div class="meta-grid">
          <span id="status-slot">${statusSelect(paper)}</span>
          ${paper.url ? `<a class="btn sm" href="${esc(paper.url)}" target="_blank" rel="noopener">${paper.arxiv_id ? "arXiv" : "원문"} ↗</a>` : ""}
          ${paper.pdf_url ? `<a class="btn sm" href="${esc(paper.pdf_url)}" target="_blank" rel="noopener">PDF ↗</a>` : ""}
          <button class="btn sm" id="bib-btn">BibTeX 복사</button>
          <span class="grow"></span>
          <button class="btn sm ghost danger" id="delete-btn">삭제</button>
        </div>
        <label class="field" style="margin-top:14px;max-width:460px"><span>태그</span>
          <input class="input" id="tags" placeholder="쉼표로 구분 (예: detection, transformer)" value="${esc(paper.tags)}"></label>
      </div>
      ${paper.abstract ? `<details class="card" style="margin-top:18px" ${exists ? "" : "open"}>
        <summary style="cursor:pointer;font-weight:650">초록</summary><p style="margin-top:10px">${esc(paper.abstract)}</p></details>` : ""}
      <div class="card" style="margin-top:12px">
        <div class="card-head">
          <div><h2>노트</h2><span class="small muted">${esc(note.path)}</span></div>
          <div class="row"><span class="save-state" id="save-state"></span>
            <button class="btn sm" id="claude-btn">Claude에게 요청</button>
            <button class="btn sm primary" id="edit-btn"></button></div>
        </div>
        <div id="note-extra" class="stack"></div>
        <div id="note-body"></div>
      </div>
      <div class="card" id="cards-card"></div>
    </div>`;

  const body = $("#note-body", root);
  const extra = $("#note-extra", root);
  const setState = (text) => { $("#save-state", root).textContent = text; };

  function drawNote() {
    $("#edit-btn", root).textContent = editing ? "편집 마치기" : exists || content ? "편집" : "직접 쓰기";
    if (editing) {
      body.innerHTML = `<div class="note-area" style="margin-top:12px">
        <textarea class="note-editor" id="editor" spellcheck="false" aria-label="노트 편집 (마크다운)"></textarea>
        <div class="note-preview md" id="preview"></div></div>`;
      $("#editor", root).value = content;
      $("#preview", root).innerHTML = renderMarkdown(content);
    } else if (content.trim()) {
      body.innerHTML = `<div class="md" style="margin-top:12px">${renderMarkdown(content)}</div>`;
    } else {
      body.innerHTML = `<div class="empty"><h3>아직 노트가 없어요</h3>
        <p>템플릿으로 직접 쓰거나, Claude Code에 요청해 초안을 받아보세요.<br>어느 쪽이든 같은 파일(${esc(note.path)})에 저장돼요.</p></div>`;
    }
  }

  function drawCards() {
    const card = $("#cards-card", root);
    if (!cards.length) {
      card.innerHTML = `<h2>복습 카드</h2><p class="muted" style="margin-top:6px">노트에 <code>Q: 질문</code>을 쓰고 바로 다음 줄에 <code>A: 답</code>을 쓰면 복습 카드가 돼요.</p>`;
      return;
    }
    card.innerHTML = `<div class="card-head"><h2>복습 카드 ${cards.length}장</h2><a class="btn sm" href="#/review">복습하러 가기</a></div>
      ${cards.map((c) => `<details style="padding:8px 0;border-top:1px solid var(--border)">
        <summary style="cursor:pointer">${esc(c.question)} <span class="small muted">· 다음 복습 ${esc(c.due.slice(5).replace("-", "/"))}</span></summary>
        <div class="md" style="margin-top:8px">${renderMarkdown(c.answer)}</div></details>`).join("")}`;
  }

  function showConflict() {
    extra.innerHTML = `<div class="banner error">노트 파일이 다른 곳(예: Claude Code)에서 바뀌어서 저장하지 않았어요.
      <div class="row" style="margin-top:8px"><button class="btn sm" id="take-disk">파일 내용 불러오기</button>
      <button class="btn sm" id="keep-mine">내가 쓴 내용으로 덮어쓰기</button></div></div>`;
    setState("저장 안 됨");
  }

  async function save() {
    clearTimeout(timer);
    if (!dirty || saving || conflict) return;
    saving = true;
    dirty = false;
    setState("저장 중…");
    try {
      const result = await api(`/api/papers/${id}/note`, { method: "PUT", body: { content, base_mtime: mtime } });
      mtime = result.note.mtime;
      exists = true;
      cards = result.cards;
      paper.note_requested = 0;
      if (alive()) { setState("저장됨"); drawCards(); refreshDueBadge(); }
    } catch (err) {
      dirty = true;
      if (err.status === 409) { conflict = true; if (alive()) showConflict(); }
      else if (alive()) { setState("저장 실패"); toast(err.message, "error"); }
    } finally {
      saving = false;
      // 저장 도중에 더 입력했다면 이어서 저장한다. 화면을 떠난 뒤라면 기다리지 않고 바로.
      if (dirty && !conflict) alive() ? (timer = setTimeout(save, AUTOSAVE_MS)) : save();
    }
  }

  async function reload(announce) {
    const data = await api(`/api/papers/${id}`);
    if (!alive()) return;
    ({ paper, note, cards } = data);
    content = note.content; mtime = note.mtime; exists = note.exists;
    dirty = false; conflict = false;
    extra.innerHTML = "";
    setState("");
    drawNote();
    drawCards();
    if (announce) toast(announce);
  }

  drawNote();
  drawCards();

  body.addEventListener("input", (e) => {
    if (e.target.id !== "editor") return;
    content = e.target.value;
    dirty = true;
    $("#preview", root).innerHTML = renderMarkdown(content);
    if (conflict) return;
    setState("수정 중…");
    clearTimeout(timer);
    timer = setTimeout(save, AUTOSAVE_MS);
  });
  body.addEventListener("keydown", (e) => {
    if (e.target.id !== "editor" || e.key !== "Tab" || e.shiftKey) return;
    e.preventDefault();
    e.target.setRangeText("  ", e.target.selectionStart, e.target.selectionEnd, "end");
    e.target.dispatchEvent(new Event("input", { bubbles: true }));
  });

  $("#edit-btn", root).addEventListener("click", async () => {
    if (editing) {
      editing = false;
      await save();
      if (!exists && !dirty) content = "";  // 템플릿만 열어보고 닫은 경우: 파일을 만들지 않는다
    } else {
      editing = true;
      if (!content.trim()) {
        const template = await api("/api/note-template").catch(() => "");
        content = template.replace(/^# .*$/m, () => `# ${paper.title}`);
      }
    }
    if (!alive()) return;
    drawNote();
    if (editing) $("#editor", root).focus();
  });

  $("#claude-btn", root).addEventListener("click", async () => {
    const prompt = notePrompt(paper);
    const copied = await copy(prompt);
    if (!exists && !paper.note_requested) {
      paper = await api(`/api/papers/${id}`, { method: "PATCH", body: { note_requested: true } }).catch(() => paper);
    }
    if (!alive()) return;
    extra.innerHTML = `<div><div class="prompt-box">${esc(prompt)}</div>
      <p class="small muted" style="margin-top:6px">${copied ? "프롬프트를 복사했어요. " : "위 내용을 복사해서 "}이 폴더에서 연 Claude Code에 붙여넣으세요. 노트 파일이 생기면 이 화면에 자동으로 나타나요.</p></div>`;
    toast(copied ? "프롬프트를 복사했어요." : "프롬프트를 표시했어요. 직접 복사해주세요.");
  });

  extra.addEventListener("click", async (e) => {
    if (e.target.id === "take-disk") {
      await reload("파일 내용을 불러왔어요.");
    } else if (e.target.id === "keep-mine") {
      const latest = await api(`/api/papers/${id}`);
      mtime = latest.note.mtime;
      conflict = false;
      extra.innerHTML = "";
      await save();
    }
  });

  $("#status-slot", root).addEventListener("change", async (e) => {
    try {
      paper = await api(`/api/papers/${id}`, { method: "PATCH", body: { status: e.target.value } });
      toast(paper.status === "done" ? "완독으로 표시했어요." : `'${STATUS[paper.status]}'(으)로 바꿨어요.`);
    } catch (err) {
      toast(err.message, "error");
    }
    $("#status-slot", root).innerHTML = statusSelect(paper);
  });

  $("#tags", root).addEventListener("change", async (e) => {
    try {
      paper = await api(`/api/papers/${id}`, { method: "PATCH", body: { tags: e.target.value } });
      e.target.value = paper.tags;
      toast("태그를 저장했어요.");
    } catch (err) {
      toast(err.message, "error");
    }
  });

  $("#bib-btn", root).addEventListener("click", async () => {
    if (await copy(bibtex)) return toast("BibTeX를 복사했어요.");
    extra.innerHTML = `<div class="prompt-box">${esc(bibtex)}</div>`;
  });

  $("#delete-btn", root).addEventListener("click", async () => {
    const ok = await confirmDialog({
      title: "라이브러리에서 삭제할까요?",
      text: exists ? `복습 카드와 읽기 기록이 지워져요. 노트 파일(${note.path})은 그대로 남겨둬요.` : "복습 카드와 읽기 기록이 지워져요.",
      ok: "삭제",
    });
    if (!ok) return;
    try {
      clearTimeout(timer);
      dirty = false;
      await api(`/api/papers/${id}`, { method: "DELETE" });
      toast("삭제했어요.");
      refreshDueBadge();
      location.hash = "#/library";
    } catch (err) {
      toast(err.message, "error");
    }
  });

  // Claude Code가 노트 파일을 쓰면 화면에 반영한다
  const poll = setInterval(async () => {
    if (document.hidden || dirty || saving || conflict) return;
    try {
      const data = await api(`/api/papers/${id}`);
      if (alive() && !dirty && !saving && data.note.mtime !== mtime) {
        const fresh = !exists && data.note.exists;
        await reload(fresh ? "노트가 도착했어요." : "노트 파일이 바뀌어서 다시 불러왔어요.");
        refreshDueBadge();
      }
    } catch { /* 다음 주기에 다시 시도 */ }
  }, POLL_MS);

  return () => {
    clearInterval(poll);
    clearTimeout(timer);
    if (dirty && !conflict) save();
  };
}
