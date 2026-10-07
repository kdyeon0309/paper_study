import { $, $$, esc, refreshDueBadge } from "./util.js";
import * as home from "./views/home.js";
import * as search from "./views/search.js";
import * as library from "./views/library.js";
import * as paper from "./views/paper.js";
import * as review from "./views/review.js";
import * as roadmap from "./views/roadmap.js";
import * as surveys from "./views/surveys.js";
import * as map from "./views/map.js";

const ROUTES = [
  [/^\/?$/, "home", home],
  [/^\/search$/, "search", search],
  [/^\/library$/, "library", library],
  [/^\/paper\/(\d+)$/, "library", paper],
  [/^\/map$/, "library", map],
  [/^\/review$/, "review", review],
  [/^\/roadmap$/, "roadmap", roadmap],
  [/^\/surveys$/, "surveys", surveys],
  [/^\/surveys\/([\w.-]+)$/, "surveys", surveys],
];

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

document.addEventListener("keydown", (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
  if (e.key === "/" && !typing && !e.metaKey && !e.ctrlKey && !$("dialog[open]")) {
    e.preventDefault();
    if (location.hash === "#/search") $("#search-input")?.focus();
    else location.hash = "#/search";
  }
});

$("#theme-btn").addEventListener("click", () => {
  const root = document.documentElement;
  const dark = root.dataset.theme ? root.dataset.theme === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
  try { localStorage.setItem("ps.theme", root.dataset.theme); } catch { /* 테마 기억은 선택 사항 */ }
});

route();
refreshDueBadge();
