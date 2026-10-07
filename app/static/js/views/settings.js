import { api, esc, toast, background, $ } from "../util.js";

export const SHORTCUTS = [
  ["/", "검색으로 이동"],
  ["?", "단축키 보기"],
  ["g 다음 h", "홈"],
  ["g 다음 s", "검색"],
  ["g 다음 l", "라이브러리"],
  ["g 다음 r", "복습"],
  ["g 다음 m", "로드맵"],
  ["g 다음 v", "서베이"],
  ["g 다음 c", "연결 지도"],
  ["Space · 1 · 2 · 3", "복습: 답 보기 · 다시 · 애매함 · 알았음"],
  ["[[", "노트 편집 중: 라이브러리 논문 링크 넣기"],
];

export const shortcutTable = () => `<table class="activity"><tbody>${SHORTCUTS.map(([keys, what]) => `<tr>
  <td>${keys.split(" ").map((k) => (/^(다음|·)$/.test(k) ? k : `<kbd>${esc(k)}</kbd>`)).join(" ")}</td><td></td><td>${esc(what)}</td></tr>`).join("")}</tbody></table>`;

const currentTheme = () => { try { return localStorage.getItem("ps.theme") || "system"; } catch { return "system"; } };

export function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme; else root.dataset.theme = theme;
  try { theme === "system" ? localStorage.removeItem("ps.theme") : localStorage.setItem("ps.theme", theme); } catch { /* 기억 못 해도 적용은 된다 */ }
}

export async function render(root) {
  const [about, goals] = await Promise.all([api("/api/about"), api("/api/goals")]);
  const theme = currentTheme();
  const themeOption = (value, label) => `<label class="row" style="gap:6px"><input type="radio" name="theme" value="${value}" ${theme === value ? "checked" : ""}>${label}</label>`;

  root.innerHTML = `<div class="page">
    <div class="page-head"><div><h1>설정</h1><p>Paper Study ${esc(about.version)}</p></div></div>

    <div class="card"><h2>화면</h2>
      <div class="row" style="gap:18px;margin-top:10px" id="theme-options">
        ${themeOption("system", "시스템 설정 따르기")}${themeOption("light", "밝게")}${themeOption("dark", "어둡게")}</div></div>

    <div class="card"><h2>주간 목표</h2>
      <p class="muted small" style="margin:4px 0 12px">월요일부터 일요일까지 한 주 기준이에요. 0으로 두면 그 목표는 꺼져요.</p>
      <form class="row" id="goal-form" style="align-items:flex-end">
        <label class="field" style="width:150px"><span>공부한 날 (일)</span><input class="input" name="goal_days" type="number" min="0" max="7" required value="${goals.goal_days}"></label>
        <label class="field" style="width:150px"><span>완독 (편)</span><input class="input" name="goal_papers" type="number" min="0" max="50" required value="${goals.goal_papers}"></label>
        <button class="btn primary" type="submit">저장</button></form></div>

    <div class="card"><h2>내 배경</h2>
      <p class="muted small" style="margin:4px 0 10px">Claude Code에 노트나 서베이를 요청하는 프롬프트에 함께 들어가요. 이 브라우저에만 저장돼요.</p>
      <textarea class="textarea" id="background" rows="3" placeholder="예: CV 엔지니어. YOLO 시리즈 논문은 전부 읽음. detection에 비유해서 설명해주면 좋음.">${esc(background.get())}</textarea></div>

    <div class="card"><h2>데이터</h2>
      <p class="muted small" style="margin:4px 0 12px">논문 ${about.counts.papers}편 · 서베이 ${about.counts.surveys}개 · 내 트랙 ${about.counts.tracks}개 · 저장한 검색 ${about.counts.searches}개</p>
      <div class="row">
        <a class="btn" href="/api/export.json" download>백업 받기</a>
        <button class="btn" id="import-btn">백업 가져오기</button>
        <a class="btn" href="/api/export.bib" download>BibTeX 받기</a>
        <input type="file" id="import-file" accept="application/json,.json" class="hidden"></div>
      <p class="small muted" style="margin-top:12px">백업에는 논문 목록, 노트, 내 트랙, 저장한 검색이 들어가요. 복습 진도와 학습 기록은 <code>${esc(about.files.db)}</code> 파일에 있어요.<br>
        저장 위치: <code>${esc(about.home)}</code> (노트는 <code>${esc(about.files.notes)}/</code>, 서베이는 <code>${esc(about.files.surveys)}/</code>)<br>
        자동 백업: 서버를 켤 때 하루 한 번 <code>${esc(about.files.backups)}/</code> 폴더에 DB를 복사하고 최근 7개를 남겨요.
        ${about.backups.length ? `지금 ${about.backups.length}개, 가장 최근은 ${esc(about.backups.at(-1).replace(/^papers-|\.db$/g, ""))}.` : "아직 복사본이 없어요."}</p></div>

    <div class="card"><h2>단축키</h2><div style="margin-top:8px">${shortcutTable()}</div></div>
  </div>`;

  $("#theme-options", root).addEventListener("change", (e) => applyTheme(e.target.value));
  $("#background", root).addEventListener("change", (e) => { background.set(e.target.value); toast("저장했어요."); });
  $("#goal-form", root).addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    try {
      await api("/api/goals", { method: "PUT", body: { goal_days: Number(data.goal_days), goal_papers: Number(data.goal_papers) } });
      toast("목표를 저장했어요.");
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
    } catch (err) {
      toast(err instanceof SyntaxError ? "JSON 파일을 읽지 못했어요." : err.message, "error");
    }
    file.value = "";
  });
}
