import { $, $$, esc, refreshDueBadge } from "./util.js";
import * as home from "./views/home.js";
import * as search from "./views/search.js";
import * as library from "./views/library.js";
import * as paper from "./views/paper.js";
import * as review from "./views/review.js";
import * as roadmap from "./views/roadmap.js";
import * as surveys from "./views/surveys.js";
import * as map from "./views/map.js";
import * as settings from "./views/settings.js";

const ROUTES = [
  [/^\/?$/, "home", home],
  [/^\/search$/, "search", search],
  [/^\/library$/, "library", library],
  [/^\/paper\/(\d+)$/, "library", paper],
  [/^\/map$/, "library", map],
  [/^\/settings$/, "settings", settings],
  [/^\/review$/, "review", review],
  [/^\/roadmap$/, "roadmap", roadmap],
  [/^\/surveys$/, "surveys", surveys],
  [/^\/surveys\/([\w.-]+)$/, "surveys", surveys],
];

const TITLES = { home: "홈", search: "검색", library: "라이브러리", review: "복습", roadmap: "로드맵", surveys: "서베이", settings: "설정" };
const view = $("#view");
let cleanup = null;
let renderToken = 0;

async function route() {
  const [path, queryString = ""] = location.hash.replace(/^#/, "").split("?");
  const token = ++renderToken;
  if (typeof cleanup === "function") cleanup();
  cleanup = null;

  const match = ROUTES.map(([re, name, mod]) => [re.exec(path || "/"), name, mod]).find(([m]) => m);
  if (!match) {
    view.innerHTML = `<div class="page"><div class="empty"><h3>없는 페이지예요</h3><div class="row"><a class="btn" href="#/">홈으로</a></div></div></div>`;
    return;
  }
  const [m, name, mod] = match;
  $$("#nav a").forEach((a) => a.toggleAttribute("aria-current", a.dataset.route === name));
  $$("#nav a[aria-current]").forEach((a) => a.setAttribute("aria-current", "page"));
  view.innerHTML = `<div class="page"><div class="skeleton">불러오는 중…</div></div>`;
  window.scrollTo(0, 0);
  document.title = `${TITLES[name]} · Paper Study`;
  // 화면이 바뀌면 키보드와 화면 낭독기의 위치를 본문 처음으로 옮긴다 (입력창이 있는 화면은 스스로 다시 옮긴다)
  view.focus({ preventScroll: true });
  try {
    const result = await mod.render(view, { args: m.slice(1), query: new URLSearchParams(queryString), alive: () => token === renderToken });
    if (token === renderToken) cleanup = result;
    else if (typeof result === "function") result();
  } catch (err) {
    if (token !== renderToken) return;
    console.error(err);
    view.innerHTML = `<div class="page"><div class="banner error">${esc(err.message || "화면을 그리지 못했어요.")}</div></div>`;
  }
}

window.addEventListener("hashchange", route);

const GO = { h: "#/", s: "#/search", l: "#/library", r: "#/review", m: "#/roadmap", v: "#/surveys", c: "#/map" };
let goUntil = 0;  // g 를 누른 뒤 이 시각까지 다음 키를 기다린다

document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
  if (typing || e.metaKey || e.ctrlKey || e.altKey || $("dialog[open]")) return;
  if (e.key === "/") {
    e.preventDefault();
    if (location.hash === "#/search") $("#search-input")?.focus();
    else location.hash = "#/search";
  } else if (e.key === "?") {
    e.preventDefault();
    $("#shortcut-list").innerHTML = settings.shortcutTable();
    $("#shortcut-dialog").showModal();
  } else if (e.key === "g") {
    goUntil = Date.now() + 1200;
  } else if (Date.now() < goUntil && GO[e.key]) {
    e.preventDefault();
    goUntil = 0;
    location.hash = GO[e.key];
  }
});
$("#shortcut-close").addEventListener("click", () => $("#shortcut-dialog").close());
$("#skip-link").addEventListener("click", () => view.focus());

route();
refreshDueBadge();
