import { api, esc, toast, copy, renderMarkdown, surveyPrompt, slugify, background, STATUS, $ } from "../util.js";

async function detail(root, name) {
  const path = `/api/surveys/${encodeURIComponent(name)}`;
  const [content, links] = await Promise.all([api(path), api(`${path}/links`)]);
  const papers = links.papers.map((p) => `<li><a href="#/paper/${p.id}">${esc(p.title)}</a> <span class="chip ${esc(p.status)}">${STATUS[p.status]}</span></li>`).join("");
  root.innerHTML = `<div class="page"><a class="crumb" href="#/surveys">← 서베이</a>
    <div class="card"><div class="md">${renderMarkdown(content, { wiki: links.wiki })}</div></div>
    ${links.papers.length || links.missing.length ? `<div class="card"><h2>이 서베이에 나온 논문</h2>
      ${links.papers.length ? `<ul style="margin:10px 0 0;padding-left:18px">${papers}</ul>` : ""}
      ${links.missing.length ? `<div class="row" style="margin-top:12px"><span class="muted">아직 라이브러리에 없는 arXiv 논문 ${links.missing.length}편</span>
        <button class="btn sm" id="add-missing">모두 라이브러리에 추가</button></div>` : ""}</div>` : ""}
    <p class="small muted" style="margin-top:10px">surveys/${esc(name)}.md</p></div>`;
  $("#add-missing", root)?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    e.target.textContent = "추가하는 중…";
    try {
      const result = await api("/api/papers/arxiv", { method: "POST", body: { ids: links.missing } });
      toast(result.failed.length ? `${result.added.length}편 추가, ${result.failed.length}편은 arXiv에서 찾지 못했어요.` : `${result.added.length}편을 라이브러리에 추가했어요.`);
    } catch (err) {
      toast(err.message, "error");
    }
    if (root.isConnected) detail(root, name);
  });
}

export async function render(root, { args }) {
  if (args[0]) return detail(root, args[0]);
  const surveys = await api("/api/surveys");

  root.innerHTML = `<div class="page">
    <div class="page-head"><div><h1>서베이</h1><p>새로운 분야를 공부할 때, 주제 하나의 흐름과 읽을 논문을 정리한 문서예요.</p></div></div>
    <div class="card">
      <h2>새 주제 요청하기</h2>
      <p class="muted" style="margin:6px 0 12px">이 앱은 유료 API를 쓰지 않아요. 주제를 적으면 Claude Code에 붙여넣을 프롬프트를 만들어주고,
        Claude Code가 arXiv를 검색해 <code>surveys/</code> 폴더에 문서를 쓰면 아래 목록에 나타나요.</p>
      <form class="row" id="topic-form">
        <input class="input grow" id="topic" placeholder="예: open-vocabulary detection, 3D gaussian splatting SLAM" required>
        <button class="btn primary" type="submit">프롬프트 만들기</button></form>
      <div id="prompt-out" style="margin-top:12px"></div>
      <details style="margin-top:14px"><summary class="small muted" style="cursor:pointer">내 배경 설정 (프롬프트에 함께 들어가요)</summary>
        <textarea class="textarea" id="background" rows="2" style="margin-top:8px"
          placeholder="예: CV 엔지니어. YOLO 시리즈 논문은 전부 읽음. detection에 비유해서 설명해주면 좋음.">${esc(background.get())}</textarea></details>
    </div>
    <h2 style="margin:24px 0 10px">작성된 서베이</h2>
    <div id="survey-list">${surveys.length
      ? surveys.map((s) => `<div class="paper-row"><div><a class="paper-title" href="#/surveys/${esc(s.name)}">${esc(s.title)}</a>
          <div class="paper-meta">surveys/${esc(s.name)}.md · ${esc(s.updated)}</div></div></div>`).join("")
      : `<div class="empty"><h3>아직 서베이가 없어요</h3><p>위에서 주제를 적고 프롬프트를 Claude Code에 붙여넣어 보세요.</p></div>`}</div>
  </div>`;

  $("#background", root).addEventListener("change", (e) => { background.set(e.target.value); toast("저장했어요."); });
  $("#topic-form", root).addEventListener("submit", async (e) => {
    e.preventDefault();
    const topic = $("#topic", root).value.trim();
    if (!topic) return;
    const prompt = surveyPrompt(topic, slugify(topic));
    const copied = await copy(prompt);
    $("#prompt-out", root).innerHTML = `<div class="prompt-box">${esc(prompt)}</div>
      <div class="row" style="margin-top:8px"><button class="btn sm" id="copy-again">복사</button>
      <span class="small muted">${copied ? "복사했어요. " : ""}이 폴더에서 연 Claude Code에 붙여넣으세요.</span></div>`;
    $("#copy-again", root).addEventListener("click", async () => toast((await copy(prompt)) ? "복사했어요." : "복사하지 못했어요. 직접 선택해서 복사해주세요.", ""));
  });
}
