import { api, esc, toast, copy, confirmDialog, statusSelect, renderMarkdown, notePrompt, refreshDueBadge, cardForm, submitCardForm, duration, STATUS, $ } from "../util.js";

const AUTOSAVE_MS = 1000;
const POLL_MS = 6000;

export async function render(root, { args, alive }) {
  const id = Number(args[0]);
  let { paper, note, cards, bibtex, tracks, links, timer, recalls } = await api(`/api/papers/${id}`);
  let editingCard = null;
  const md = (text) => renderMarkdown(text, { wiki: links.wiki });
  let content = note.content;
  let mtime = note.mtime;
  let exists = note.exists;
  let editing = false;
  let dirty = false;
  let saving = false;
  let conflict = false;
  let saveTimer = null;

  document.title = `${paper.title} · Paper Study`;
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
          <button class="btn sm" id="timer-btn" title="이 화면을 열어둔 동안의 시간을 재요. 다른 화면으로 가면 멈춰요."></button>
          <span class="small muted" id="timer-total"></span>
          <button class="btn sm" id="bib-btn">BibTeX 복사</button>
          ${paper.arxiv_id ? `<button class="btn sm" id="refresh-btn" title="제목·저자·초록·분류를 arXiv에서 다시 받아요">정보 새로고침</button>` : ""}
          <span class="grow"></span>
          <button class="btn sm ghost danger" id="delete-btn">삭제</button>
        </div>
        ${tracks.map((t) => `<div class="paper-meta" style="margin-top:10px">로드맵 <a href="#/roadmap">${esc(t.name)}</a> ${t.position} / ${t.total}번째${
          t.next ? ` · 다음: <a href="${t.next.paper_id ? `#/paper/${t.next.paper_id}` : `https://arxiv.org/abs/${esc(t.next.arxiv_id)}" target="_blank" rel="noopener`}">${esc(t.next.title)}</a>${t.next.paper_id ? "" : " (아직 라이브러리에 없음)"}` : " · 이 트랙의 마지막 논문"}</div>`).join("")}
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
      <div class="card hidden" id="links-card"></div>
      <div class="card" id="cards-card"></div>
    </div>`;

  const body = $("#note-body", root);
  const extra = $("#note-extra", root);
  const setState = (text) => { $("#save-state", root).textContent = text; };

  function drawNote() {
    $("#edit-btn", root).textContent = editing ? "편집 마치기" : exists || content ? "편집" : "직접 쓰기";
    if (editing) {
      body.innerHTML = `<div class="note-area" style="margin-top:12px">
        <div class="editor-wrap"><textarea class="note-editor" id="editor" spellcheck="false" aria-label="노트 편집 (마크다운)"></textarea>
          <div class="suggest hidden" id="suggest" role="listbox" aria-label="논문 링크 제안"></div></div>
        <div class="note-preview md" id="preview"></div></div>`;
      $("#editor", root).value = content;
      $("#preview", root).innerHTML = md(content);
    } else if (content.trim()) {
      body.innerHTML = `<div class="md" style="margin-top:12px">${md(content)}</div>`;
    } else {
      body.innerHTML = `<div class="empty"><h3>아직 노트가 없어요</h3>
        <p>템플릿으로 직접 쓰거나, Claude Code에 요청해 초안을 받아보세요.<br>어느 쪽이든 같은 파일(${esc(note.path)})에 저장돼요.</p></div>`;
    }
  }

  function drawLinks() {
    const box = $("#links-card", root);
    const list = (items) => `<ul style="margin:4px 0 0;padding-left:18px">${items.map((x) => `<li><a href="#/paper/${x.id}">${esc(x.title)}</a></li>`).join("")}</ul>`;
    box.classList.toggle("hidden", !links.out.length && !links.back.length && !links.surveys.length && !recalls.length);
    box.innerHTML = `<h2>연결과 기록</h2><div class="week-lists" style="margin-top:10px">
      ${links.out.length ? `<div><h3>이 노트가 언급한 논문</h3>${list(links.out)}</div>` : ""}
      ${links.back.length ? `<div><h3>이 논문을 언급한 노트</h3>${list(links.back)}</div>` : ""}
      ${links.surveys.length ? `<div><h3>이 논문이 나온 서베이</h3><ul style="margin:4px 0 0;padding-left:18px">${links.surveys.map((x) => `<li><a href="#/surveys/${esc(x.name)}">${esc(x.title)}</a></li>`).join("")}</ul></div>` : ""}
      ${recalls.length ? `<div><h3>기억으로 다시 쓴 요약</h3><ul style="margin:4px 0 0;padding-left:18px">${recalls.map((r) => `<li>${esc(r.text)} <span class="small muted">· ${esc(r.day.slice(5).replace("-", "/"))} · ${r.grade === "good" ? "기억났음" : "가물가물"}</span></li>`).join("")}</ul></div>` : ""}</div>`;
  }

  function drawCards() {
    const card = $("#cards-card", root);
    const adding = editingCard === "new";
    const row = (c) => (c.id === editingCard
      ? `<div style="padding:12px 0;border-top:1px solid var(--border)">${cardForm(c)}</div>`
      : `<details style="padding:8px 0;border-top:1px solid var(--border)">
        <summary style="cursor:pointer">${esc(c.question)} <span class="small muted">· 다음 복습 ${esc(c.due.slice(5).replace("-", "/"))}${c.reviews ? ` · ${c.reviews}번 복습` : ""}</span></summary>
        <div class="md" style="margin-top:8px">${md(c.answer)}</div>
        <div class="row" style="margin-top:8px"><button class="btn sm" data-card-edit="${c.id}">수정</button>
          <button class="btn sm ghost danger" data-card-delete="${c.id}">카드 삭제</button></div></details>`);
    card.innerHTML = `<div class="card-head"><h2>복습 카드${cards.length ? ` ${cards.length}장` : ""}</h2>
        <div class="row">${adding ? "" : `<button class="btn sm" id="card-add">카드 추가</button>`}
          ${cards.length ? `<a class="btn sm" href="#/review">복습하러 가기</a>` : ""}</div></div>
      ${adding ? `<div style="padding:12px 0;border-top:1px solid var(--border)">${cardForm({ id: "new", question: "", answer: "" }, id)}</div>` : ""}
      ${cards.map(row).join("")}
      ${cards.length || adding ? "" : `<p class="muted">'카드 추가'로 바로 만들거나, 노트에 <code>Q: 질문</code>을 쓰고 바로 다음 줄에 <code>A: 답</code>을 쓰면 복습 카드가 돼요.</p>`}`;
  }

  function showConflict() {
    extra.innerHTML = `<div class="banner error">노트 파일이 다른 곳(예: Claude Code)에서 바뀌어서 저장하지 않았어요.
      <div class="row" style="margin-top:8px"><button class="btn sm" id="take-disk">파일 내용 불러오기</button>
      <button class="btn sm" id="keep-mine">내가 쓴 내용으로 덮어쓰기</button></div></div>`;
    setState("저장 안 됨");
  }

  async function save() {
    clearTimeout(saveTimer);
    if (!dirty || saving || conflict) return;
    saving = true;
    dirty = false;
    setState("저장 중…");
    try {
      const result = await api(`/api/papers/${id}/note`, { method: "PUT", body: { content, base_mtime: mtime } });
      mtime = result.note.mtime;
      exists = true;
      cards = result.cards;
      links = result.links;
      paper.note_requested = 0;
      if (alive()) {
        setState("저장됨"); drawCards(); drawLinks(); refreshDueBadge();
        // 방금 쓴 [[링크]]가 어느 논문인지는 저장 응답으로 알게 되므로 미리보기를 한 번 더 그린다
        const preview = $("#preview", root);
        if (preview) preview.innerHTML = md(content);
      }
    } catch (err) {
      dirty = true;
      if (err.status === 409) { conflict = true; if (alive()) showConflict(); }
      else if (alive()) { setState("저장 실패"); toast(err.message, "error"); }
    } finally {
      saving = false;
      // 저장 도중에 더 입력했다면 이어서 저장한다. 화면을 떠난 뒤라면 기다리지 않고 바로.
      if (dirty && !conflict) alive() ? (saveTimer = setTimeout(save, AUTOSAVE_MS)) : save();
    }
  }

  async function reload(announce) {
    const data = await api(`/api/papers/${id}`);
    if (!alive()) return;
    ({ paper, note, cards, links, recalls } = data);
    content = note.content; mtime = note.mtime; exists = note.exists;
    dirty = false; conflict = false;
    extra.innerHTML = "";
    setState("");
    drawNote();
    drawCards();
    drawLinks();
    if (announce) toast(announce);
  }

  drawNote();
  drawCards();
  drawLinks();

  // 읽기 타이머: 서버에 30초마다 신호를 보내고, 신호가 끊기면 서버가 마지막 신호까지만 센다
  let tick = null;
  let beat = null;
  let shownSince = Date.now();
  const drawTimer = () => {
    const live = timer.running ? timer.session_seconds + Math.floor((Date.now() - shownSince) / 1000) : 0;
    const clock = `${Math.floor(live / 60)}:${String(live % 60).padStart(2, "0")}`;
    $("#timer-btn", root).textContent = timer.running ? `읽기 멈춤 · ${clock}` : "읽기 시작";
    $("#timer-btn", root).classList.toggle("primary", timer.running);
    const total = timer.seconds + (timer.running ? Math.floor((Date.now() - shownSince) / 1000) : 0);
    $("#timer-total", root).textContent = total ? `읽은 시간 ${duration(total)}` : "";
  };
  const timerCall = async (action, keepalive = false) => {
    const res = await fetch(`/api/papers/${id}/timer`, { method: "POST", keepalive, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) });
    if (!res.ok) throw new Error("타이머를 바꾸지 못했어요.");
    timer = await res.json();
    shownSince = Date.now();
  };
  const runClock = () => {
    clearInterval(tick); clearInterval(beat);
    if (!timer.running) return;
    tick = setInterval(drawTimer, 1000);
    beat = setInterval(() => timerCall("ping").then(() => { if (alive()) { runClock(); drawTimer(); } }).catch(() => {}), 30000);
  };
  drawTimer();
  runClock();
  $("#timer-btn", root).addEventListener("click", async () => {
    try {
      const starting = !timer.running;
      await timerCall(starting ? "start" : "stop");
      if (starting && paper.status === "to_read") {
        paper.status = "reading";
        $("#status-slot", root).innerHTML = statusSelect(paper);
      }
      runClock();
      drawTimer();
    } catch (err) {
      toast(err.message, "error");
    }
  });
  const stopOnHide = () => { if (timer.running) timerCall("stop", true).catch(() => {}); };
  window.addEventListener("pagehide", stopOnHide);

  // 카드 수정·삭제는 서버가 노트 파일의 Q/A 줄을 고친다. 편집기에 저장 안 된 내용이 있으면 먼저 저장한다.
  const cardsBox = $("#cards-card", root);
  cardsBox.addEventListener("click", async (e) => {
    const t = e.target;
    if (t.id === "card-add" || t.dataset.cardEdit) {
      editingCard = t.id === "card-add" ? "new" : Number(t.dataset.cardEdit);
      drawCards();
      $(".card-edit input", root)?.focus();
    } else if ("cardCancel" in t.dataset) {
      editingCard = null;
      drawCards();
    } else if (t.dataset.cardDelete) {
      const target = cards.find((c) => c.id === Number(t.dataset.cardDelete));
      const ok = await confirmDialog({ title: "이 카드를 삭제할까요?", text: `"${target.question}" — 노트에서도 이 Q/A 줄이 지워져요.`, ok: "삭제" });
      if (!ok) return;
      try {
        if (dirty) await save();
        await api(`/api/cards/${target.id}`, { method: "DELETE" });
        await reload("카드를 삭제했어요.");
        refreshDueBadge();
      } catch (err) {
        toast(err.message, "error");
      }
    }
  });
  cardsBox.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      if (dirty) await save();
      const created = e.target.dataset.card === "new";
      await submitCardForm(e.target);
      editingCard = null;
      await reload(created ? "카드를 추가했어요." : "카드를 고쳤어요.");
      refreshDueBadge();
    } catch (err) {
      toast(err.message, "error");
    }
  });

  // [[ 를 치면 라이브러리 논문을 제안하고, 고르면 [[arXiv ID]] 가 들어간다
  let library = null;
  let suggestions = [];
  let picked = 0;
  const closeSuggest = () => { suggestions = []; $("#suggest", root)?.classList.add("hidden"); };
  const openQuery = (editor) => /\[\[([^\[\]\n]{0,60})$/.exec(editor.value.slice(0, editor.selectionStart));
  const drawSuggest = () => {
    const box = $("#suggest", root);
    if (!box) return;
    box.classList.toggle("hidden", !suggestions.length);
    box.innerHTML = suggestions.map((p, i) => `<button type="button" role="option" aria-selected="${i === picked}" data-pick="${i}">
      <span>${esc(p.title)}</span><span class="small muted">${esc(p.arxiv_id || p.slug)}</span></button>`).join("")
      + (suggestions.length ? `<div class="small muted" style="padding:4px 10px">↑↓ 이동 · Enter 선택 · Esc 닫기</div>` : "");
  };
  const updateSuggest = async (editor) => {
    const m = openQuery(editor);
    if (!m) return closeSuggest();
    library ??= await api("/api/papers").catch(() => []);
    if (!alive() || !openQuery(editor)) return closeSuggest();
    const q = m[1].trim().toLowerCase();
    suggestions = library.filter((p) => p.id !== id && `${p.title} ${p.arxiv_id || ""} ${p.slug}`.toLowerCase().includes(q)).slice(0, 6);
    picked = 0;
    drawSuggest();
  };
  const pick = (editor, paperToLink) => {
    const m = openQuery(editor);
    if (!m || !paperToLink) return;
    const start = editor.selectionStart - m[0].length;
    const end = editor.selectionStart + (editor.value.startsWith("]]", editor.selectionStart) ? 2 : 0);
    editor.setRangeText(`[[${paperToLink.arxiv_id || paperToLink.slug}]]`, start, end, "end");
    closeSuggest();
    editor.dispatchEvent(new Event("input", { bubbles: true }));
    editor.focus();
  };
  body.addEventListener("mousedown", (e) => {
    const option = e.target.closest("[data-pick]");
    if (!option) return;
    e.preventDefault();  // 편집기 포커스를 잃지 않게
    pick($("#editor", root), suggestions[Number(option.dataset.pick)]);
  });
  body.addEventListener("click", (e) => { if (e.target.id === "editor") updateSuggest(e.target); });
  body.addEventListener("focusout", (e) => { if (e.target.id === "editor") setTimeout(closeSuggest, 150); });

  body.addEventListener("input", (e) => {
    if (e.target.id !== "editor") return;
    updateSuggest(e.target);
    content = e.target.value;
    dirty = true;
    $("#preview", root).innerHTML = md(content);
    if (conflict) return;
    setState("수정 중…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, AUTOSAVE_MS);
  });
  body.addEventListener("keydown", (e) => {
    if (e.target.id !== "editor") return;
    if (suggestions.length) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        picked = (picked + (e.key === "ArrowDown" ? 1 : suggestions.length - 1)) % suggestions.length;
        return drawSuggest();
      }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); return pick(e.target, suggestions[picked]); }
      if (e.key === "Escape") { e.preventDefault(); return closeSuggest(); }
    }
    if (e.key !== "Tab" || e.shiftKey) return;
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

  $("#refresh-btn", root)?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    try {
      await api(`/api/papers/${id}/refresh`, { method: "POST" });
      toast("arXiv에서 최신 정보를 받아왔어요.");
      if (dirty) await save();
      if (alive()) window.dispatchEvent(new HashChangeEvent("hashchange"));
    } catch (err) {
      e.target.disabled = false;
      toast(err.message, "error");
    }
  });

  $("#delete-btn", root).addEventListener("click", async () => {
    const ok = await confirmDialog({
      title: "라이브러리에서 삭제할까요?",
      text: exists ? `복습 카드와 읽기 기록이 지워져요. 노트 파일(${note.path})은 그대로 남겨둬요.` : "복습 카드와 읽기 기록이 지워져요.",
      ok: "삭제",
    });
    if (!ok) return;
    try {
      clearTimeout(saveTimer);
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
    clearInterval(tick);
    clearInterval(beat);
    clearTimeout(saveTimer);
    window.removeEventListener("pagehide", stopOnHide);
    stopOnHide();
    if (dirty && !conflict) save();
  };
}
