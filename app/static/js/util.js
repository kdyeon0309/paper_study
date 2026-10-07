export const STATUS = { to_read: "읽을 예정", reading: "읽는 중", done: "완료" };
export const INTERVALS = [1, 3, 7, 14, 30, 60];

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

function detailOf(data) {
  const d = data && data.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg).join(", ");
  return "";
}

export async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("서버에 연결하지 못했어요. 서버가 실행 중인지 확인해주세요.");
  }
  const isJson = (res.headers.get("content-type") || "").includes("json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const err = new Error(detailOf(data) || `요청에 실패했어요 (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export function toast(message, kind = "") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = message;
  $("#toasts").appendChild(el);
  setTimeout(() => el.remove(), kind === "error" ? 6000 : 3200);
}

export function confirmDialog({ title, text = "", ok = "확인" }) {
  const dialog = $("#confirm-dialog");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  $("#confirm-ok").textContent = ok;
  return new Promise((resolve) => {
    const done = (answer) => {
      dialog.removeEventListener("click", onClick);
      dialog.removeEventListener("cancel", onCancel);
      dialog.close();
      resolve(answer);
    };
    const onClick = (e) => e.target.dataset.answer && done(e.target.dataset.answer === "yes");
    const onCancel = () => done(false);
    dialog.addEventListener("click", onClick);
    dialog.addEventListener("cancel", onCancel);
    dialog.showModal();
  });
}

export async function copy(text) {
  // 권한 창이 뜨면 writeText가 끝나지 않을 수 있어서 기다리는 시간을 제한한다
  const viaApi = navigator.clipboard
    ? navigator.clipboard.writeText(text).then(() => true, () => false)
    : Promise.resolve(false);
  if (await Promise.race([viaApi, new Promise((r) => setTimeout(() => r(false), 700))])) return true;
  const area = document.createElement("textarea");
  area.value = text;
  area.style.cssText = "position:fixed;opacity:0;top:0;left:0";
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try { ok = document.execCommand("copy"); } catch { /* 복사 실패는 호출한 쪽에서 안내한다 */ }
  area.remove();
  return ok;
}

export function authorsShort(authors, max = 3) {
  const list = String(authors || "").split(",").map((s) => s.trim()).filter(Boolean);
  return list.length > max ? `${list.slice(0, max).join(", ")} 외 ${list.length - max}명` : list.join(", ");
}

export const tagsOf = (paper) => String(paper.tags || "").split(",").map((s) => s.trim()).filter(Boolean);

export function statusSelect(paper) {
  const options = Object.entries(STATUS)
    .map(([value, label]) => `<option value="${value}" ${paper.status === value ? "selected" : ""}>${label}</option>`)
    .join("");
  return `<select class="status-select ${esc(paper.status)}" data-id="${paper.id}" aria-label="읽기 상태">${options}</select>`;
}

export async function refreshDueBadge() {
  try {
    const due = await api("/api/review/due");
    const badge = $("#due-badge");
    badge.textContent = due.length;
    badge.classList.toggle("hidden", due.length === 0);
  } catch { /* 배지는 없어도 된다 */ }
}

/**
 * Ask, one saved search at a time, how many papers appeared since it was last viewed.
 * arXiv asks for about 3 seconds between requests, so we pause after any answer that did not come from the cache.
 */
export async function checkSavedSearches(searches, onResult, stopped = () => false) {
  for (const item of searches) {
    if (stopped()) return;
    let result;
    try {
      result = await api(`/api/searches/${item.id}/new`);
    } catch {
      return;  // arXiv가 막혔으면 조용히 그만둔다
    }
    if (stopped()) return;
    onResult(item, result);
    if (!result.cached) await new Promise((r) => setTimeout(r, 3000));
  }
}

/* ---------- markdown + math ---------- */

let purifyReady = false;
function setupPurify() {
  if (purifyReady) return;
  purifyReady = true;
  window.DOMPurify.addHook("afterSanitizeAttributes", (node) => {
    if (node.tagName === "A" && /^https?:/i.test(node.getAttribute("href") || "")) {
      node.setAttribute("target", "_blank");
      node.setAttribute("rel", "noopener noreferrer");
    }
  });
}

const CODE = /(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)/g;
// 인라인 수식은 공백으로 시작하거나 끝나지 않는다($5 와 $10 같은 금액과 구분). 구형 Safari를 위해 lookbehind는 쓰지 않는다.
const MATH = /\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]|\$(?!\s)((?:\\.|[^$\\\n])*?(?:\\.|[^\s$\\]))\$(?!\d)/g;

function renderMath({ tex, display }) {
  if (!window.katex) return `<code>${esc(tex)}</code>`;
  try {
    return window.katex.renderToString(tex, { displayMode: display, throwOnError: true });
  } catch {
    return `<span class="math-error" title="수식을 해석하지 못했어요">${esc(tex)}</span>`;
  }
}

/** Markdown -> sanitized HTML. Math is lifted out first so `_` and `*` inside it survive the parser. */
export function renderMarkdown(source, { wiki = {} } = {}) {
  source = String(source || "");
  if (!window.marked || !window.DOMPurify) return `<pre>${esc(source)}</pre>`;
  setupPurify();
  const math = [];
  const text = source
    .split(CODE)
    .map((part, i) => (i % 2 ? part : part
      // [[arXiv ID 또는 제목]] 은 라이브러리에 있는 논문이면 그 논문으로 가는 링크가 된다
      .replace(/\[\[([^\[\]\n]{1,200})\]\]/g, (whole, inner) => (wiki[inner]
        ? `[${wiki[inner].title.replace(/[\[\]]/g, "")}](#/paper/${wiki[inner].id})` : whole))
      .replace(MATH, (_, block, bracket, inline) => {
      const tex = block ?? bracket ?? inline;
      math.push({ tex: tex.trim(), display: inline === undefined });
      return `@@MATH${math.length - 1}@@`;
    })))
    .join("");
  const html = window.DOMPurify.sanitize(window.marked.parse(text, { gfm: true, breaks: true }));
  return html.replace(/@@MATH(\d+)@@/g, (_, i) => renderMath(math[Number(i)]));
}

/* ---------- 복습 카드 편집 폼 (논문 화면과 복습 화면이 같이 쓴다) ---------- */

/** `card.id` 가 "new" 이면 새 카드 폼이고, 그때는 `paperId` 가 필요하다. */
export function cardForm(card, paperId = "") {
  return `<form class="card-edit stack" data-card="${card.id}" data-paper="${paperId}" style="gap:8px">
    <label class="field"><span>질문</span><input class="input" name="question" value="${esc(card.question)}" required maxlength="500"></label>
    <label class="field"><span>답</span><textarea class="textarea" name="answer" rows="3" required maxlength="5000">${esc(card.answer)}</textarea></label>
    <div class="row"><button class="btn sm primary" type="submit">저장</button>
      <button class="btn sm" type="button" data-card-cancel>취소</button>
      <span class="small muted">${card.id === "new" ? "노트의 '복습 카드' 섹션에 Q/A 줄로 추가돼요." : "노트 파일의 Q/A 줄이 함께 바뀌고, 복습 진도는 유지돼요."}</span></div></form>`;
}

export async function submitCardForm(form) {
  const body = Object.fromEntries(new FormData(form));
  if (form.dataset.card === "new") return api(`/api/papers/${form.dataset.paper}/cards`, { method: "POST", body });
  return api(`/api/cards/${form.dataset.card}`, { method: "PATCH", body });
}

/* ---------- Claude Code 프롬프트 ---------- */

export const background = {
  get: () => { try { return localStorage.getItem("ps.background") || ""; } catch { return ""; } },
  set: (value) => { try { localStorage.setItem("ps.background", value); } catch { /* 저장 못 해도 동작에는 지장 없음 */ } },
};

const backgroundLine = () => (background.get().trim() ? `\n\n내 배경: ${background.get().trim()}` : "");

export function notePrompt(paper) {
  const ref = paper.arxiv_id ? `arXiv:${paper.arxiv_id}` : paper.url || `id ${paper.id}`;
  return `논문 "${paper.title}" (${ref}) 을 읽고 스터디 노트를 notes/${paper.slug}.md 에 써줘.

- notes/_TEMPLATE.md 의 구성을 따르고, 수식은 $...$ / $$...$$ 로 써줘.
- 논문에서 확인한 내용만 쓰고, 확인하지 못한 수치는 쓰지 말아줘.
- 마지막 "복습 카드" 섹션에 Q: / A: 형식 카드를 5개 이상 넣어줘.
- 내 라이브러리에 있는 다른 논문을 언급할 때는 [[arXiv ID]] 로 써줘 (목록: \`python -m app.cli list\`).
- 논문 정보는 \`python -m app.cli show ${paper.slug}\` 로 볼 수 있어.${backgroundLine()}`;
}

export function surveyPrompt(topic, slug) {
  return `"${topic}" 주제로 서베이를 써서 surveys/${slug}.md 에 저장해줘.

- 첫 줄은 "# 제목" 으로 시작하고, 이 분야가 어떤 문제를 풀려는지, 접근법이 어떻게 바뀌어 왔는지(계보) 설명해줘.
- 핵심 논문 5~10편을 읽는 순서대로 고르고, 각각 arXiv 링크와 두세 문장 요약을 붙여줘.
- arXiv에서 실제로 확인한 논문만 넣어줘. 검색은 \`python -m app.cli search "키워드" --cat cs.CV\` 로 할 수 있어.
- 고른 논문은 \`python -m app.cli add <arXiv ID> ...\` 로 내 라이브러리에 추가해줘.${backgroundLine()}`;
}

export function slugify(topic) {
  const ascii = topic.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 50);
  if (ascii.length >= 3) return ascii;
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `survey-${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
}
