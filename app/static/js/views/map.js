import { api, esc, STATUS, $ } from "../util.js";

const W = 900;
const H = 560;
const R = 9;
const PAD = 40;

const shortTitle = (title) => {
  const head = title.split(":")[0].trim();
  const base = head.length >= 3 && head.length <= 28 ? head : title;
  return base.length > 28 ? `${base.slice(0, 26)}…` : base;
};

/** Fruchterman-Reingold force layout. Starts from a circle, so the same graph always lands the same way. */
function layout(nodes, edges) {
  const n = nodes.length;
  const byId = new Map(nodes.map((d) => [d.id, d]));
  nodes.forEach((d, i) => {
    const a = (2 * Math.PI * i) / n;
    d.x = W / 2 + Math.cos(a) * H * 0.3;
    d.y = H / 2 + Math.sin(a) * H * 0.3;
  });
  const k = Math.sqrt(((W - 2 * PAD) * (H - 2 * PAD)) / n) * 0.75;
  const STEPS = 300;
  for (let step = 0; step < STEPS; step++) {
    const temp = (W / 8) * (1 - step / STEPS);
    nodes.forEach((d) => { d.dx = (W / 2 - d.x) * 0.02; d.dy = (H / 2 - d.y) * 0.02; });  // 가운데로 살짝 당김
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = nodes[i];
        const b = nodes[j];
        const dx = a.x - b.x || 0.01;
        const dy = a.y - b.y || 0.01;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const force = (k * k) / dist;
        a.dx += (dx / dist) * force; a.dy += (dy / dist) * force;
        b.dx -= (dx / dist) * force; b.dy -= (dy / dist) * force;
      }
    }
    for (const e of edges) {
      const a = byId.get(e.from);
      const b = byId.get(e.to);
      const dx = a.x - b.x;
      const dy = a.y - b.y;
      const dist = Math.max(1, Math.hypot(dx, dy));
      const force = (dist * dist) / k;
      a.dx -= (dx / dist) * force; a.dy -= (dy / dist) * force;
      b.dx += (dx / dist) * force; b.dy += (dy / dist) * force;
    }
    for (const d of nodes) {
      const move = Math.max(1, Math.hypot(d.dx, d.dy));
      d.x = Math.min(W - PAD * 3, Math.max(PAD, d.x + (d.dx / move) * Math.min(move, temp)));  // 오른쪽은 라벨 자리
      d.y = Math.min(H - PAD, Math.max(PAD, d.y + (d.dy / move) * Math.min(move, temp)));
    }
  }
  return byId;
}

export async function render(root) {
  const graph = await api("/api/graph");
  const head = `<a class="crumb" href="#/library">← 라이브러리</a>
    <div class="page-head"><div><h1>연결 지도</h1><p>노트에서 서로 언급한 논문들이에요. 화살표는 "이 노트가 저 논문을 언급했다"는 뜻이에요.</p></div></div>`;

  if (!graph.edges.length) {
    root.innerHTML = `<div class="page">${head}<div class="empty"><h3>아직 연결된 논문이 없어요</h3>
      <p>노트에서 다른 논문을 <code>[[arXiv ID]]</code>로 언급하면 여기에 선으로 이어져요.<br>편집기에서 <code>[[</code>를 치면 라이브러리 논문을 골라 넣을 수 있어요.</p>
      <div class="row"><a class="btn" href="#/library">라이브러리로</a></div></div></div>`;
    return;
  }

  const byId = layout(graph.nodes, graph.edges);
  const near = new Map(graph.nodes.map((d) => [d.id, new Set([d.id])]));
  graph.edges.forEach((e) => { near.get(e.from).add(e.to); near.get(e.to).add(e.from); });

  const edgeSvg = graph.edges.map((e) => {
    const a = byId.get(e.from);
    const b = byId.get(e.to);
    const dist = Math.max(1, Math.hypot(b.x - a.x, b.y - a.y));
    const ux = (b.x - a.x) / dist;
    const uy = (b.y - a.y) / dist;
    // 양방향 언급은 선이 겹치지 않게 살짝 휘게 그린다
    const mx = (a.x + b.x) / 2 - uy * 14;
    const my = (a.y + b.y) / 2 + ux * 14;
    return `<path class="map-edge" data-from="${e.from}" data-to="${e.to}" marker-end="url(#arrow)"
      d="M${(a.x + ux * R).toFixed(1)},${(a.y + uy * R).toFixed(1)} Q${mx.toFixed(1)},${my.toFixed(1)} ${(b.x - ux * (R + 6)).toFixed(1)},${(b.y - uy * (R + 6)).toFixed(1)}"/>`;
  }).join("");
  const nodeSvg = graph.nodes.map((d) => {
    const label = `${d.title}${d.year ? ` (${d.year})` : ""} · ${STATUS[d.status]} · 연결 ${near.get(d.id).size - 1}개`;
    return `<a class="map-node ${d.status === "done" ? "done" : ""}" href="#/paper/${d.id}" data-id="${d.id}" data-tip="${esc(label)}" aria-label="${esc(label)}">
      <circle cx="${d.x.toFixed(1)}" cy="${d.y.toFixed(1)}" r="${R}"/>
      <text x="${(d.x + R + 5).toFixed(1)}" y="${(d.y + 4).toFixed(1)}">${esc(shortTitle(d.title))}</text></a>`;
  }).join("");
  const title = (id) => esc(byId.get(id).title);
  const rows = graph.edges.map((e) => `<tr><td><a href="#/paper/${e.from}">${title(e.from)}</a></td><td>→</td><td><a href="#/paper/${e.to}">${title(e.to)}</a></td></tr>`).join("");

  root.innerHTML = `<div class="page wide">${head}
    <div class="map-wrap">
      <svg class="map-svg" id="map" viewBox="0 0 ${W} ${H}" role="group" aria-label="논문 ${graph.nodes.length}편, 연결 ${graph.edges.length}개">
        <defs><marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path class="map-arrow" d="M0,1 L10,5 L0,9 z"/></marker></defs>
        ${edgeSvg}${nodeSvg}</svg>
      <div class="map-legend">
        <span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="var(--accent)" stroke="var(--accent)" stroke-width="2"/></svg>완독</span>
        <span><svg width="14" height="14"><circle cx="7" cy="7" r="5" fill="var(--surface)" stroke="var(--accent)" stroke-width="2"/></svg>읽을 예정 · 읽는 중</span>
        <span>논문 ${graph.nodes.length}편 · 연결 ${graph.edges.length}개${graph.isolated ? ` · 연결 없는 논문 ${graph.isolated}편은 표시하지 않음` : ""}</span>
      </div>
    </div>
    <details class="card" style="margin-top:12px"><summary style="cursor:pointer;font-weight:650">표로 보기</summary>
      <table class="activity" style="margin-top:10px"><tbody>${rows}</tbody></table></details>
  </div>`;

  const svg = $("#map", root);
  const tip = document.createElement("div");
  tip.className = "tooltip hidden";
  document.body.appendChild(tip);
  const focus = (node) => {
    const group = near.get(Number(node.dataset.id));
    svg.classList.add("focusing");
    svg.querySelectorAll(".map-node").forEach((el) => el.classList.toggle("near", group.has(Number(el.dataset.id))));
    svg.querySelectorAll(".map-edge").forEach((el) => el.classList.toggle("near", el.dataset.from === node.dataset.id || el.dataset.to === node.dataset.id));
    const box = node.querySelector("circle").getBoundingClientRect();
    tip.textContent = node.dataset.tip;
    tip.style.left = `${Math.min(window.innerWidth - 20, Math.max(20, box.left + box.width / 2))}px`;
    tip.style.top = `${box.top}px`;
    tip.classList.remove("hidden");
  };
  const blur = () => { svg.classList.remove("focusing"); tip.classList.add("hidden"); };
  svg.addEventListener("mouseover", (e) => { const node = e.target.closest(".map-node"); if (node) focus(node); });
  svg.addEventListener("mouseout", (e) => { if (e.target.closest(".map-node")) blur(); });
  svg.addEventListener("focusin", (e) => { const node = e.target.closest(".map-node"); if (node) focus(node); });
  svg.addEventListener("focusout", blur);
  return () => tip.remove();
}
