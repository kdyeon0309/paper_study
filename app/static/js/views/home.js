import { api, esc, toast, copy, checkSavedSearches, duration, STATUS } from "../util.js";

const DAY = ["일", "월", "화", "수", "목", "금", "토"];
const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parse = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const level = (n) => (n >= 7 ? 4 : n >= 4 ? 3 : n >= 2 ? 2 : n >= 1 ? 1 : 0);

function heatmap({ start, end, days }) {
  const cells = [];
  const months = [];
  let prevMonth = -1;
  for (let d = parse(start), i = 0; d <= parse(end); d.setDate(d.getDate() + 1), i++) {
    if (i % 7 === 0) {
      months.push(d.getMonth() !== prevMonth ? `<span>${d.getMonth() + 1}월</span>` : "<span></span>");
      prevMonth = d.getMonth();
    }
    const key = iso(d);
    const n = days[key] || 0;
    const label = `${d.getMonth() + 1}월 ${d.getDate()}일 (${DAY[d.getDay()]}) · ${n ? `활동 ${n}건` : "활동 없음"}`;
    cells.push(`<div class="heat-cell${key === end ? " today" : ""}" data-level="${level(n)}" data-tip="${label}" role="img" aria-label="${label}"></div>`);
  }
  return `
    <div class="heatmap-wrap"><div class="heatmap">
      <div class="heat-months">${months.join("")}</div>
      <div class="heat-days">${DAY.map((d, i) => `<span>${i % 2 ? d : ""}</span>`).join("")}</div>
      <div class="heat-grid">${cells.join("")}</div>
    </div></div>
    <div class="heat-legend" aria-hidden="true">적음 ${[0, 1, 2, 3, 4].map((l) => `<div class="heat-cell" data-level="${l}"></div>`).join("")} 많음
      <span style="margin-left:10px">하루 활동 수: 1 · 2–3 · 4–6 · 7 이상</span></div>`;
}

const md = (s) => { const d = parse(s); return `${d.getMonth() + 1}/${d.getDate()}`; };

/** This week against the one before it, with arrows to look further back. */
function weeklyCard(box) {
  let offset = 0;
  let week = null;

  const summary = () => {
    const c = week.current;
    const acc = c.accuracy === null ? "" : ` (정답률 ${Math.round(c.accuracy * 100)}%)`;
    const list = (title, items) => (items.length ? `\n### ${title}\n${items.map((p) => `- ${p.title}`).join("\n")}\n` : "");
    const g = week.goals;
    const goal = (value, target, unit) => (target ? ` (목표 ${target}${unit}${value >= target ? " 달성" : ""})` : "");
    return `## 주간 회고 (${md(week.start)} – ${md(week.end)})\n\n- 공부한 날: ${c.active_days}일${goal(c.active_days, g.goal_days, "일")}\n- 완독: ${c.finished}편${goal(c.finished, g.goal_papers, "편")}\n- 노트 쓴 논문: ${c.notes}편\n- 읽은 시간: ${duration(c.minutes * 60)}\n- 복습한 카드: ${c.reviews}장${acc}\n${list("완독한 논문", week.finished)}${list("노트를 쓴 논문", week.noted)}`;
  };

  const draw = () => {
    const c = week.current;
    const p = week.previous;
    const diff = (a, b, unit) => (a === b ? "전주와 같음" : `전주보다 ${a > b ? "+" : "−"}${Math.abs(a - b)}${unit}`);
    const pct = (x) => Math.round(x * 100);
    const accuracyNote = c.accuracy === null ? "복습 기록 없음" : p.accuracy === null ? "전주 기록 없음" : diff(pct(c.accuracy), pct(p.accuracy), "%p");
    const stats = [
      ["공부한 날", c.active_days, "일", diff(c.active_days, p.active_days, "일")],
      ["완독", c.finished, "편", diff(c.finished, p.finished, "편")],
      ["노트 쓴 논문", c.notes, "편", diff(c.notes, p.notes, "편")],
      ["읽은 시간", duration(c.minutes * 60), "", diff(c.minutes, p.minutes, "분")],
      ["복습한 카드", c.reviews, "장", diff(c.reviews, p.reviews, "장")],
      ["복습 정답률", c.accuracy === null ? "–" : pct(c.accuracy), c.accuracy === null ? "" : "%", accuracyNote],
    ];
    const todayKey = iso(new Date());
    const title = offset === 0 ? "이번 주" : offset === -1 ? "지난주" : `${-offset}주 전`;
    const links = (items) => items.map((x) => `<li><a href="#/paper/${x.id}">${esc(x.title)}</a></li>`).join("");
    const quiet = !c.active_days && !c.finished;
    const g = week.goals;
    const goalRow = (label, value, target, met, unit) => (target ? `<div>
      <div class="row" style="justify-content:space-between"><span>${label}</span>
        <span class="small muted">${value} / ${target}${unit}${met ? ` <span class="chip done">달성</span>` : ""}</span></div>
      <div class="meter" style="margin-top:6px" role="img" aria-label="${label} ${value} / ${target}${unit}"><i style="width:${Math.min(100, (value / target) * 100)}%"></i></div></div>` : "");
    const streak = offset === 0 && week.goal_streak > 1
      ? `<p class="small muted" style="margin-top:8px">${week.goal_streak}주 연속으로 목표를 달성하고 있어요.</p>` : "";
    const goalsHtml = g.goal_days || g.goal_papers
      ? `<div class="week-lists" style="margin-top:18px">${goalRow("목표: 공부한 날", c.active_days, g.goal_days, g.days_met, "일")}${goalRow("목표: 완독", c.finished, g.goal_papers, g.papers_met, "편")}</div>${streak}`
      : `<p class="small muted" style="margin-top:14px">주간 목표가 꺼져 있어요. '목표'에서 정할 수 있어요.</p>`;
    box.innerHTML = `
      <div class="card-head"><div><h2>${title}</h2><span class="small muted">${md(week.start)} – ${md(week.end)} · 월요일 시작</span></div>
        <div class="row"><button class="btn sm" id="week-goal">목표</button>
          <button class="btn sm" id="week-copy" ${quiet ? "disabled" : ""}>회고 복사</button>
          <button class="btn sm" id="week-prev" aria-label="이전 주">‹</button>
          <button class="btn sm" id="week-next" aria-label="다음 주" ${offset === 0 ? "disabled" : ""}>›</button></div></div>
      <div class="week-stats">${stats.map(([label, value, unit, note]) => `<div><div class="label">${label}</div>
        <div class="value">${value}<small>${unit}</small></div><div class="delta">${note}</div></div>`).join("")}</div>
      ${goalsHtml}
      <div class="week-strip">${week.days.map((d, i) => `<div class="week-day${d.day > todayKey ? " future" : ""}">
        <div class="heat-cell" data-level="${d.day > todayKey ? 0 : level(d.count)}" role="img" aria-label="${DAY[(i + 1) % 7]}요일 활동 ${d.count}건"></div>
        ${DAY[(i + 1) % 7]} <b>${d.day > todayKey ? "" : d.count || ""}</b></div>`).join("")}</div>
      ${week.finished.length || week.noted.length ? `<div class="week-lists">
        ${week.finished.length ? `<div><h3>완독한 논문</h3><ul>${links(week.finished)}</ul></div>` : ""}
        ${week.noted.length ? `<div><h3>노트를 쓴 논문</h3><ul>${links(week.noted)}</ul></div>` : ""}</div>` : ""}
      ${quiet ? `<p class="muted small" style="margin-top:12px">이 주에는 기록이 없어요.</p>` : ""}
      <dialog id="goal-dialog"><h2>주간 목표</h2>
        <p class="muted small" style="margin-bottom:10px">월요일부터 일요일까지 한 주 기준이에요. 0으로 두면 그 목표는 꺼져요.</p>
        <form id="goal-form" method="dialog">
          <label class="field"><span>공부한 날 (일)</span><input class="input" name="goal_days" type="number" min="0" max="7" required value="${g.goal_days}"></label>
          <label class="field"><span>완독 (편)</span><input class="input" name="goal_papers" type="number" min="0" max="50" required value="${g.goal_papers}"></label>
          <div class="dialog-actions"><button class="btn" type="button" id="goal-cancel">취소</button><button class="btn primary" type="submit">저장</button></div>
        </form></dialog>`;
  };

  const load = async () => {
    const data = await api(`/api/weekly?offset=${offset}`);
    if (!box.isConnected) return;
    week = data;
    draw();
  };
  box.addEventListener("click", async (e) => {
    if (e.target.id === "week-prev") { offset -= 1; load(); }
    else if (e.target.id === "week-next" && offset < 0) { offset += 1; load(); }
    else if (e.target.id === "week-copy") toast((await copy(summary())) ? "회고를 마크다운으로 복사했어요." : "복사하지 못했어요.");
    else if (e.target.id === "week-goal") box.querySelector("#goal-dialog").showModal();
    else if (e.target.id === "goal-cancel") box.querySelector("#goal-dialog").close();
  });
  box.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target));
    try {
      await api("/api/goals", { method: "PUT", body: { goal_days: Number(data.goal_days), goal_papers: Number(data.goal_papers) } });
      toast("목표를 저장했어요.");
      await load();
    } catch (err) {
      toast(err.message, "error");
    }
  });
  return load();
}

function activityText(a) {
  if (a.kind === "added") return "라이브러리에 추가";
  if (a.kind === "status") return `상태: ${STATUS[a.detail] || a.detail}`;
  if (a.kind === "note") return "노트 작성";
  if (a.kind === "review") return "카드 복습";
  if (a.kind === "read") return "읽기";
  if (a.kind === "recall") return a.detail === "good" ? "회상: 기억났음" : "회상: 가물가물";
  return a.kind;
}

function onboarding() {
  return `
    <div class="page">
      <div class="page-head"><div><h1>Paper Study</h1><p>논문을 찾고, 읽고, 잊지 않게 복습하는 개인 스터디 공간이에요.</p></div>
        <div class="head-actions"><a class="btn ghost sm" href="#/settings">설정</a></div></div>
      <div class="card"><div class="steps">
        <div class="step"><h3>읽을 논문 고르기</h3><p>분야별 필독 논문을 순서대로 정리한 로드맵에서 시작하거나, arXiv를 직접 검색하세요.</p>
          <div class="row"><a class="btn primary" href="#/roadmap">로드맵 보기</a><a class="btn" href="#/search">arXiv 검색</a></div></div>
        <div class="step"><h3>노트 쓰기</h3><p>논문 페이지에서 직접 쓰거나, Claude Code에 요청하면 notes/ 폴더에 써준 노트가 바로 보여요. API 키는 필요 없어요.</p></div>
        <div class="step"><h3>복습하기</h3><p>노트에 <code>Q:</code> / <code>A:</code> 를 적어두면 복습 카드가 되고, 간격을 늘려가며 다시 물어봐요.</p></div>
      </div></div>
    </div>`;
}

export async function render(root) {
  const [stats, papers, tracks] = await Promise.all([api("/api/stats"), api("/api/papers"), api("/api/roadmaps")]);
  if (!stats.total) {
    root.innerHTML = onboarding();
    return;
  }

  const reading = papers.filter((p) => p.status === "reading").slice(0, 3);
  const requested = papers.filter((p) => p.note_requested);
  const next = papers.filter((p) => p.status === "to_read").at(-1);
  const todos = [];
  if (stats.cards_due) {
    todos.push(`<div class="todo"><div class="grow"><div>복습 카드 ${stats.cards_due}장</div><div class="small muted">오늘 다시 볼 차례예요</div></div><a class="btn primary sm" href="#/review">복습 시작</a></div>`);
  }
  if (stats.recalls_due) {
    todos.push(`<div class="todo"><div class="grow"><div>다시 요약해볼 논문 ${stats.recalls_due}편</div><div class="small muted">완독한 지 시간이 지났어요. 기억만으로 한 문장</div></div><a class="btn sm" href="#/review?tab=recall">회상하기</a></div>`);
  }
  for (const p of reading) {
    todos.push(`<div class="todo"><div class="grow"><div>${esc(p.title)}</div><div class="small muted">읽는 중${p.has_note ? "" : " · 노트 없음"}</div></div><a class="btn sm" href="#/paper/${p.id}">이어 읽기</a></div>`);
  }
  for (const p of requested.slice(0, 3)) {
    todos.push(`<div class="todo"><div class="grow"><div>${esc(p.title)}</div><div class="small muted">Claude Code에 노트를 요청해둔 논문</div></div><a class="btn sm" href="#/paper/${p.id}">열기</a></div>`);
  }
  // 읽는 중인 논문이 없으면, 진행 중인 로드맵 트랙에서 다음 차례를 권한다
  const upNext = tracks
    .filter((t) => t.papers.some((p) => p.paper_id))
    .map((t) => ({ track: t, paper: t.papers.find((p) => p.status !== "done") }))
    .find((x) => x.paper);
  if (!reading.length && upNext) {
    const { track, paper } = upNext;
    todos.push(`<div class="todo"><div class="grow"><div>${esc(paper.title)}</div><div class="small muted">'${esc(track.name)}' 트랙의 다음 논문</div></div>
      <a class="btn sm" href="${paper.paper_id ? `#/paper/${paper.paper_id}` : "#/roadmap"}">${paper.paper_id ? "읽기 시작" : "로드맵에서 추가"}</a></div>`);
  } else if (!reading.length && next) {
    todos.push(`<div class="todo"><div class="grow"><div>${esc(next.title)}</div><div class="small muted">읽을 예정 목록에서 가장 오래된 논문</div></div><a class="btn sm" href="#/paper/${next.id}">읽기 시작</a></div>`);
  }

  const started = tracks
    .map((t) => ({ ...t, saved: t.papers.filter((p) => p.paper_id).length, done: t.papers.filter((p) => p.status === "done").length }))
    .filter((t) => t.saved);
  const trackRows = started.map((t) => `
    <div><div class="row" style="justify-content:space-between"><span>${esc(t.name)}</span>
      <span class="small muted">${t.done} / ${t.papers.length}편 완독</span></div>
      <div class="meter" style="margin-top:6px"><i style="width:${(t.done / t.papers.length) * 100}%"></i></div></div>`).join("");

  const recent = stats.recent.map((a) => `
    <tr><td>${esc(a.day.slice(5).replace("-", "/"))}</td><td>${esc(activityText(a))}</td>
      <td>${a.paper_id ? `<a href="#/paper/${a.paper_id}">${esc(a.title)}</a>` : esc(a.title || a.detail || "")}</td></tr>`).join("");

  const today = new Date();
  root.innerHTML = `
    <div class="page">
      <div class="page-head"><div><h1>오늘의 공부</h1>
        <p>${today.getMonth() + 1}월 ${today.getDate()}일 ${DAY[today.getDay()]}요일</p></div>
        <div class="head-actions"><a class="btn ghost sm" href="#/settings">설정</a></div></div>
      <div class="tiles">
        <div class="tile"><div class="label">연속 학습</div><div class="value">${stats.streak}<small>일</small></div><div class="sub">지금까지 ${stats.active_days}일 공부</div></div>
        <div class="tile"><div class="label">이번 달 완독</div><div class="value">${stats.month_done}<small>편</small></div><div class="sub">전체 완독 ${stats.by_status.done}편</div></div>
        <div class="tile"><div class="label">읽는 중</div><div class="value">${stats.by_status.reading}<small>편</small></div><div class="sub">읽을 예정 ${stats.by_status.to_read}편</div></div>
        <div class="tile"><div class="label">노트</div><div class="value">${stats.notes}<small>개</small></div><div class="sub">논문 ${stats.total}편 중</div></div>
        <div class="tile"><div class="label">복습 대기</div><div class="value">${stats.cards_due}<small>장</small></div><div class="sub">전체 카드 ${stats.cards_total}장</div></div>
      </div>
      <div class="card" id="weekly" style="margin-top:12px"></div>
      <div class="two-col" style="margin-top:12px">
        <div class="card"><div class="card-head"><h2>학습 기록</h2><span class="small muted">최근 20주</span></div>${heatmap(stats.heatmap)}</div>
        <div class="card"><div class="card-head"><h2>오늘 할 일</h2></div>
          <div id="todos">${todos.join("") || `<p class="muted" id="no-todos">밀린 일이 없어요. <a href="#/roadmap">로드맵</a>에서 다음 논문을 골라보세요.</p>`}</div></div>
      </div>
      <div class="two-col" style="margin-top:12px">
        <div class="card"><div class="card-head"><h2>최근 활동</h2></div>
          <table class="activity"><tbody>${recent}</tbody></table></div>
        <div class="card"><div class="card-head"><h2>로드맵 진행</h2><a class="small" href="#/roadmap">전체 보기</a></div>
          <div class="stack">${trackRows || `<p class="muted">아직 시작한 트랙이 없어요. <a href="#/roadmap">로드맵</a>에서 트랙을 골라 추가해보세요.</p>`}</div></div>
      </div>
    </div>`;

  await weeklyCard(root.querySelector("#weekly"));

  // 저장한 검색에 새 논문이 있으면 할 일에 덧붙인다. 화면을 먼저 그린 뒤 뒤에서 확인한다.
  let left = false;
  api("/api/searches").then((searches) => checkSavedSearches(searches, (item, result) => {
    if (!result.new) return;
    const box = root.querySelector("#todos");
    box.querySelector("#no-todos")?.remove();
    box.insertAdjacentHTML("beforeend", `<div class="todo"><div class="grow"><div>새 논문 ${result.new}${result.more ? "편 이상" : "편"}</div>
      <div class="small muted">저장한 검색: ${esc(item.q)}${item.cat ? ` · ${esc(item.cat)}` : ""}</div></div>
      <a class="btn sm" href="#/search?saved=${item.id}">보기</a></div>`);
  }, () => left)).catch(() => {});

  const tip = document.createElement("div");
  tip.className = "tooltip hidden";
  document.body.appendChild(tip);
  const grid = root.querySelector(".heat-grid");
  grid.addEventListener("mouseover", (e) => {
    if (!e.target.dataset.tip) return;
    const box = e.target.getBoundingClientRect();
    tip.textContent = e.target.dataset.tip;
    tip.style.left = `${box.left + box.width / 2}px`;
    tip.style.top = `${box.top}px`;
    tip.classList.remove("hidden");
  });
  grid.addEventListener("mouseleave", () => tip.classList.add("hidden"));
  const wrap = root.querySelector(".heatmap-wrap");
  wrap.scrollLeft = wrap.scrollWidth;
  return () => { left = true; tip.remove(); };
}
