export const STATUS = { to_read: "읽을 예정", reading: "읽는 중", done: "완료" };
export const INTERVALS = [1, 3, 7, 14, 30, 60];
// 이해 깊이. '완독' 하나로 뭉뚱그리지 않고, 어디까지 했는지를 단계로 남긴다.
export const DEPTH = [
  { label: "아직", short: "–", test: "아직 읽지 않았다." },
  { label: "훑어봄", short: "훑어봄", test: "초록·그림·결론을 보고, 무슨 문제를 어떻게 풀었는지 두 문장으로 말할 수 있다." },
  { label: "정독", short: "정독", test: "노트를 보지 않고 방법과 주요 실험 결과를 설명할 수 있다. 그림과 표를 직접 해석했다." },
  { label: "유도", short: "유도", test: "핵심 식을 손으로 유도했거나, 알고리즘을 텐서 모양까지 적은 의사코드로 썼다." },
  { label: "구현", short: "구현", test: "핵심 부분을 직접 구현해 돌려봤고, 맞게 짰다는 근거(테스트·재현 수치)가 있다." },
];

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

/** 3725 -> "1시간 2분", 240 -> "4분", 20 -> "1분 미만" */
export function duration(seconds) {
  const minutes = Math.floor(seconds / 60);
  if (minutes < 1) return seconds > 0 ? "1분 미만" : "0분";
  return minutes >= 60 ? `${Math.floor(minutes / 60)}시간 ${minutes % 60}분` : `${minutes}분`;
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

const refOf = (paper) => (paper.arxiv_id ? `arXiv:${paper.arxiv_id}` : paper.url || `id ${paper.id}`);

/** 내가 쓴 노트를 논문과 대조해 지적만 받는다. 고쳐 써주지 않는다. */
export function reviewPrompt(paper) {
  return `내가 쓴 노트 notes/${paper.slug}.md 를 논문 "${paper.title}" (${refOf(paper)}) 본문과 대조해서 검토해줘.

- 노트를 고쳐 쓰지 마. 파일은 건드리지 말고 지적만 해줘.
- (1) 논문과 다르게 쓴 곳 (2) 빠뜨린 핵심 (3) 논문 문장을 옮기기만 하고 이해 없이 넘어간 것으로 보이는 곳, 이 세 가지로 나눠서.
- 각 지적에는 논문의 어느 절·식·표를 보면 되는지 붙여줘. 정답 문장을 대신 써주지는 마.
- '유도'와 '비판' 섹션은 특히 엄격하게. 건너뛴 줄이 있으면 어디인지 짚어줘.
- 마지막에 이해 깊이를 훑어봄 / 정독 / 유도 / 구현 중 어디로 보는지와 그 근거를 한 줄로.${backgroundLine()}`;
}

/** 구술시험. 한 번에 하나씩 묻고 채점한다. */
export function examPrompt(paper) {
  return `논문 "${paper.title}" (${refOf(paper)}) 으로 구술시험을 봐줘. 먼저 논문 본문을 읽고 시작해.

- 한 번에 질문 하나만. 내 답을 듣기 전에는 다음으로 넘어가지 마.
- 사실 확인보다 "왜"와 "어떻게"를 물어줘: 설계 선택의 이유, 식의 유도 단계, 가정이 깨지는 경우, 표의 숫자가 뒷받침하는 것과 못 하는 것.
- 내 답이 틀리거나 얕으면 바로 정답을 말하지 말고, 한 번 더 파고드는 질문을 해줘. 두 번 막히면 그때 설명해줘.
- 8문제쯤 한 뒤, 내가 막힌 지점을 정리하고 그 부분을 Q:/A: 카드로 notes/${paper.slug}.md 의 "복습 카드" 섹션에 추가해줘. 카드는 내가 틀린 것만.
- 봐주지 마. 대충 맞는 답은 틀린 걸로 쳐줘.${backgroundLine()}`;
}

/** 구현 과제를 받는다. 코드는 내가 쓴다. */
export function implPrompt(paper) {
  return `논문 "${paper.title}" (${refOf(paper)}) 의 핵심 부분을 내가 직접 구현하려고 해. 과제를 만들어줘.

- 구현 코드는 쓰지 마. 내가 쓴다.
- 논문에서 가장 핵심인 부분 하나를 골라, numpy나 PyTorch로 한두 시간 안에 짤 수 있는 최소 과제로 좁혀줘.
- 줄 것: (1) 함수 이름과 입출력 텐서 모양 (2) 손으로 먼저 풀어볼 유도 문제 2~3개 (3) 내 구현이 맞는지 확인하는 테스트 코드. 테스트는 정답 구현을 베끼지 않고도 검증할 수 있게 수치 기울기, 손으로 계산한 작은 예, 성질(불변성 등)을 써줘.
- exercises/ 폴더의 과제들(README.md, solution_template.py, check.py)과 같은 형식으로 exercises/paper_${paper.slug.replace(/[^A-Za-z0-9]/g, "_")}/ 에 만들어줘.
- 내가 막히면 답 대신 힌트를 달라고 할 거야. 그때도 코드 전체를 주지는 마.${backgroundLine()}`;
}

/** 초안을 대신 받는다. 시간이 없을 때의 지름길이고, 받은 뒤에는 직접 고쳐 써야 남는다. */
export function notePrompt(paper) {
  const ref = refOf(paper);
  return `논문 "${paper.title}" (${ref}) 을 읽고 스터디 노트를 notes/${paper.slug}.md 에 써줘.

- notes/_TEMPLATE_QUICK.md 의 구성을 따르고, 수식은 $...$ / $$...$$ 로 써줘.
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
