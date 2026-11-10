#!/usr/bin/env node
// 가보는 지하철 — 게임용 맵 생성기
// 사용: node gen-game-map.cjs [입력 data.js] [출력 폴더] [lines.config.json]
// 입력(data.js): 행정동 폴리곤·역·선로 (build-map.cjs 결과, 서울시청 기준 웹 메르카토르)
// 출력: 동 격자(JSON, 도트 해상도), 도트 지도 PNG, 1080×720 화면 조각(tiles/), 호선별 경로, network.json, 미리보기
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const assert = require('node:assert/strict');

const here = __dirname;
const inFile = process.argv[2] || path.join(here, '..', 'source', 'data.js');
const outDir = process.argv[3] || path.join(here, '..');
const cfgFile = process.argv[4] || path.join(here, '..', 'lines.config.json');
const cfg = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
const K = Math.cos(37.5665 * Math.PI / 180); // 메르카토르 → 실제 미터 보정

// ---------- 입력 ----------
const window_ = {};
new Function('window', fs.readFileSync(inFile, 'utf8'))(window_);
const D = window_.MAP_DATA;
const m = p => [p[0] * K, p[1] * K]; // 이후 모든 좌표: 서울시청 기준 미터, x=동, y=남(아래)
const dongs = D.dongs.map((d, i) => ({
  i, id: d.id, name: d.name, gu: d.gu,
  polys: d.polys.map(poly => poly.map(r => r.map(m))),
}));
assert.equal(dongs.length, 427, '행정동 수');

// ---------- 1. 동 격자 (도트 해상도) ----------
// 맵 = 화면(1080×720) × screens(8×8) 픽셀. 도트 1개 = dot_px(4) 화면 픽셀.
const [SW, SH] = cfg.map.screen_px, [TC, TR] = cfg.map.screens, DOT = cfg.map.dot_px;
const MAPW = SW * TC, MAPH = SH * TR;           // 8640 × 5760 화면 픽셀
const cols = MAPW / DOT, rows = MAPH / DOT;     // 2160 × 1440 도트
let bx0 = Infinity, by0 = Infinity, bx1 = -Infinity, by1 = -Infinity;
for (const d of dongs) for (const poly of d.polys) for (const p of poly[0]) {
  bx0 = Math.min(bx0, p[0]); by0 = Math.min(by0, p[1]); bx1 = Math.max(bx1, p[0]); by1 = Math.max(by1, p[1]);
}
const MPP = Math.max((bx1 - bx0) / (cols - 2 * cfg.map.margin_dots), (by1 - by0) / (rows - 2 * cfg.map.margin_dots)); // 도트 1개의 실제 길이(m)
const x0 = (bx0 + bx1) / 2 - cols * MPP / 2, y0 = (by0 + by1) / 2 - rows * MPP / 2; // 도트 (0,0) 왼쪽 위의 실제 좌표(m)
const toDot = p => [(p[0] - x0) / MPP, (p[1] - y0) / MPP];
const toMapPx = p => { const q = toDot(p); return [r1(q[0] * DOT), r1(q[1] * DOT)]; };
function r1(v) { return Math.round(v * 10) / 10; }

const grid = new Int16Array(cols * rows).fill(-1);
for (const d of dongs) { // 스캔라인 채우기(짝-홀 규칙, 도트 중심 기준)
  for (const poly of d.polys) {
    const edges = [];
    for (const ring of poly) for (let i = 0; i < ring.length; i++) { const a = toDot(ring[i]), b = toDot(ring[(i + 1) % ring.length]); if (a[1] !== b[1]) edges.push(a[1] < b[1] ? [a, b] : [b, a]); }
    let vmin = Infinity, vmax = -Infinity; for (const [a, b] of edges) { vmin = Math.min(vmin, a[1]); vmax = Math.max(vmax, b[1]); }
    for (let r = Math.max(0, Math.ceil(vmin - .5)); r <= Math.min(rows - 1, Math.floor(vmax - .5)); r++) {
      const yc = r + .5, xs = [];
      for (const [a, b] of edges) if (a[1] <= yc && b[1] > yc) xs.push(a[0] + (yc - a[1]) * (b[0] - a[0]) / (b[1] - a[1]));
      xs.sort((u, v) => u - v);
      for (let k = 0; k + 1 < xs.length; k += 2) for (let c = Math.max(0, Math.ceil(xs[k] - .5)); c <= Math.min(cols - 1, Math.ceil(xs[k + 1] - .5) - 1); c++) grid[r * cols + c] = d.i;
    }
  }
}
let holes = 0; // 경계 반올림으로 생긴 한 칸짜리 틈 메우기
for (let r = 1; r < rows - 1; r++) for (let c = 1; c < cols - 1; c++) {
  const i = r * cols + c; if (grid[i] !== -1) continue;
  const L = grid[i - 1], R = grid[i + 1], U = grid[i - cols], Dn = grid[i + cols];
  if (L >= 0 && L === R) { grid[i] = L; holes++; } else if (U >= 0 && U === Dn) { grid[i] = U; holes++; }
}
const covered = new Set(grid); covered.delete(-1);

// 인접 동 → 그리디 채색(이웃끼리 다른 색)
const adj = dongs.map(() => new Set());
for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
  const a = grid[r * cols + c]; if (a < 0) continue;
  for (const [dc, dr] of [[1, 0], [0, 1]]) {
    if (c + dc >= cols || r + dr >= rows) continue;
    const b = grid[(r + dr) * cols + c + dc];
    if (b >= 0 && b !== a) { adj[a].add(b); adj[b].add(a); }
  }
}
const palette = cfg.dong_palette;
const colorOf = new Array(dongs.length).fill(-1);
[...dongs.keys()].sort((a, b) => adj[b].size - adj[a].size).forEach(i => {
  const used = new Set([...adj[i]].map(j => colorOf[j]));
  let c = 0; while (used.has(c)) c++;
  colorOf[i] = c % palette.length;
  if (c >= palette.length) console.warn('팔레트 부족: ', dongs[i].name);
});
const hex = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const shade = (rgb, f) => rgb.map(v => Math.round(v * f));

// ---------- 2. 호선 경로 ----------
const stationByName = new Map(D.stations.map(s => [s.name, { name: s.name, pos: m(s.point) }]));
const rawTracks = D.tracks.map(t => t.map(m));
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

function buildGraph(tracks) {
  const nodes = [];
  tracks.forEach((t, ti) => {
    for (let i = 0; i < t.length; i++) {
      nodes.push({ p: t[i], t: ti });
      if (i < t.length - 1) {
        const L = dist(t[i], t[i + 1]), n = Math.ceil(L / 20);
        for (let k = 1; k < n; k++) nodes.push({ p: [t[i][0] + (t[i + 1][0] - t[i][0]) * k / n, t[i][1] + (t[i + 1][1] - t[i][1]) * k / n], t: ti });
      }
    }
  });
  // 같은 폴리라인 안에서는 순서대로 이어지고, 서로 다른 선로(복선·분기)는 가까우면 연결
  const edges = nodes.map(() => []);
  const add = (a, b, w) => { edges[a].push([b, w]); edges[b].push([a, w]); };
  for (let i = 1; i < nodes.length; i++) if (nodes[i].t === nodes[i - 1].t) add(i - 1, i, dist(nodes[i].p, nodes[i - 1].p));
  const H = 60, hash = new Map();
  const key = (x, y) => Math.floor(x / H) + ',' + Math.floor(y / H);
  nodes.forEach((n, i) => { const k = key(...n.p); (hash.get(k) || hash.set(k, []).get(k)).push(i); });
  nodes.forEach((n, i) => {
    const cx = Math.floor(n.p[0] / H), cy = Math.floor(n.p[1] / H);
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (const j of hash.get((cx + dx) + ',' + (cy + dy)) || []) {
      if (j <= i || nodes[j].t === n.t) continue;
      const d = dist(n.p, nodes[j].p);
      if (d <= cfg.join_radius_m) add(i, j, d * 1.5 + 5); // 다른 선로로 갈아타는 비용(지그재그 방지)
    }
  });
  // 공개 선형에 빠진 구간: 끊어진 덩어리 사이를 가장 가까운 두 점으로 직선 연결(추정 구간으로 표시)
  const bridges = new Set();
  const par = nodes.map((_, i) => i), find = x => par[x] === x ? x : (par[x] = find(par[x]));
  edges.forEach((es, a) => es.forEach(([b]) => { par[find(a)] = find(b); }));
  for (;;) {
    const comps = new Map(); nodes.forEach((_, i) => { const c = find(i); (comps.get(c) || comps.set(c, []).get(c)).push(i); });
    if (comps.size < 2) break;
    const cs = [...comps.values()]; let best = null;
    for (let i = 0; i < cs.length; i++) for (let j = i + 1; j < cs.length; j++) for (const a of cs[i]) for (const b of cs[j]) {
      const d = dist(nodes[a].p, nodes[b].p); if (!best || d < best[0]) best = [d, a, b];
    }
    if (best[0] > cfg.bridge_max_m) { console.warn(`끊긴 선로 덩어리 ${cs.length}개, 가장 가까운 틈 ${best[0].toFixed(0)}m > bridge_max_m — 연결 안 함`); break; }
    add(best[1], best[2], best[0]); bridges.add(best[1] + '-' + best[2]); bridges.add(best[2] + '-' + best[1]);
    par[find(best[1])] = find(best[2]);
    console.log(`선로 틈 ${best[0].toFixed(0)}m 직선 연결(추정 구간)`);
  }
  return { nodes, edges, bridges };
}
function nearest(g, p) {
  let best = -1, bd = Infinity;
  g.nodes.forEach((n, i) => { const d = dist(n.p, p); if (d < bd) { bd = d; best = i; } });
  return [best, bd];
}
function dijkstra(g, s, t) {
  const D_ = new Float64Array(g.nodes.length).fill(Infinity), prev = new Int32Array(g.nodes.length).fill(-1);
  D_[s] = 0;
  const heap = [[0, s]];
  const push = x => { heap.push(x); let i = heap.length - 1; while (i > 0) { const p = (i - 1) >> 1; if (heap[p][0] <= heap[i][0]) break; [heap[p], heap[i]] = [heap[i], heap[p]]; i = p; } };
  const pop = () => { const top = heap[0], last = heap.pop(); if (heap.length) { heap[0] = last; let i = 0; for (;;) { let l = 2 * i + 1, r = l + 1, s_ = i; if (l < heap.length && heap[l][0] < heap[s_][0]) s_ = l; if (r < heap.length && heap[r][0] < heap[s_][0]) s_ = r; if (s_ === i) break; [heap[s_], heap[i]] = [heap[i], heap[s_]]; i = s_; } } return top; };
  while (heap.length) {
    const [d, u] = pop();
    if (d > D_[u]) continue;
    if (u === t) break;
    for (const [v, w] of g.edges[u]) if (d + w < D_[v]) { D_[v] = d + w; prev[v] = u; push([D_[v], v]); }
  }
  if (!isFinite(D_[t])) return null;
  const out = []; for (let v = t; v !== -1; v = prev[v]) out.push(v);
  return out.reverse();
}
function simplify(pts, tol) { // Douglas-Peucker
  if (pts.length < 3) return pts;
  const [a, b] = [pts[0], pts[pts.length - 1]];
  let md = 0, mi = 0;
  for (let i = 1; i < pts.length - 1; i++) {
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
    const d = Math.abs(dy * (pts[i][0] - a[0]) - dx * (pts[i][1] - a[1])) / L;
    if (d > md) { md = d; mi = i; }
  }
  if (md <= tol) return [a, b];
  return simplify(pts.slice(0, mi + 1), tol).slice(0, -1).concat(simplify(pts.slice(mi), tol));
}
const length = pts => pts.reduce((s, p, i) => i ? s + dist(p, pts[i - 1]) : 0, 0);
const cellOf = p => { const q = toDot(p); return [Math.floor(q[0]), Math.floor(q[1])]; };

const graph = buildGraph(rawTracks);
const report = [];
const lines = [];
for (const L of cfg.lines.filter(l => l.enabled)) {
  assert.equal(L.id, '1', '현재 입력 데이터(data.js)에는 1호선만 있음. 다른 호선은 README의 "호선 추가" 참고');
  const segs = [], stationMap = new Map();
  for (const names of L.segments) {
    const pts = []; const stOut = []; const est = [];
    let travelled = 0, prevSnap = null;
    for (let k = 0; k < names.length; k++) {
      const st = stationByName.get(names[k]); assert.ok(st, '역 없음: ' + names[k]);
      const [ni, snapD] = nearest(graph, st.pos);
      assert.ok(snapD < cfg.max_snap_m, `${names[k]} 선로까지 ${snapD.toFixed(0)}m`);
      if (k > 0) {
        const ridx = dijkstra(graph, prevSnap, ni);
        assert.ok(ridx, `경로 없음: ${names[k - 1]}→${names[k]}`);
        let off = 0;
        for (let q = 1; q < ridx.length; q++) {
          const dd = dist(graph.nodes[ridx[q]].p, graph.nodes[ridx[q - 1]].p);
          if (graph.bridges.has(ridx[q - 1] + '-' + ridx[q])) est.push([r1(travelled + off), r1(travelled + off + dd)]);
          off += dd;
        }
        const s = simplify(ridx.map(v => graph.nodes[v].p), cfg.simplify_m);
        pts.push(...s.slice(1)); travelled += length(s);
      } else pts.push(graph.nodes[ni].p);
      prevSnap = ni;
      stOut.push({ name: names[k], at_m: r1(travelled), snap_m: Math.round(snapD) });
      if (!stationMap.has(names[k])) stationMap.set(names[k], graph.nodes[ni].p);
    }
    segs.push({ stations: names, length_m: r1(travelled), estimated_spans_m: est, points: pts.map(p => [r1(p[0]), r1(p[1])]), points_px: pts.map(toMapPx), station_at_m: stOut.map(s => s.at_m) });
    report.push(`${L.name} [${names[0]}→${names[names.length - 1]}] ${(travelled / 1000).toFixed(1)}km, 역 ${names.length}개, 최대 스냅 ${Math.max(...stOut.map(s => s.snap_m))}m` + (est.length ? `, 추정 구간 ${est.map(e => (e[1] - e[0]).toFixed(0) + 'm').join('+')}` : ''));
  }
  lines.push({ L, segs, stationMap });
}

// ---------- 3. 네트워크(환승·분기) ----------
const net = new Map(); // 역 이름 → {lines, neighbors}
for (const { L, segs, stationMap } of lines) {
  for (const seg of segs) seg.stations.forEach((name, i) => {
    const e = net.get(name) || { name, pos: stationMap.get(name), lines: new Set(), nb: new Map() };
    e.lines.add(L.id);
    const nb = e.nb.get(L.id) || e.nb.set(L.id, new Set()).get(L.id);
    if (i > 0) nb.add(seg.stations[i - 1]);
    if (i < seg.stations.length - 1) nb.add(seg.stations[i + 1]);
    net.set(name, e);
  });
}
const stationsOut = [...net.values()].map(e => {
  const [c, r] = cellOf(e.pos), di = grid[r * cols + c];
  assert.ok(di >= 0, e.name + ' 격자 밖(그림 밖)');
  return {
    name: e.name, lines: [...e.lines], transfer: e.lines.size > 1, // 환승역: 둘 이상의 호선이 같은 역 이름을 공유
    junction: [...e.nb.values()].some(s => s.size > 2),            // 분기점: 한 호선에서 이웃 역이 3개 이상
    dot: [c, r], map_px: toMapPx(e.pos), pos_m: [r1(e.pos[0]), r1(e.pos[1])], dong: dongs[di].name, gu: dongs[di].gu, dong_id: dongs[di].id,
  };
});

// ---------- 구 채색(구 테두리 색) ----------
const guNames = [...new Set(dongs.map(d => d.gu))].sort((a, b) => a.localeCompare(b, 'ko'));
const guOfDong = dongs.map(d => guNames.indexOf(d.gu));
const guAdj = guNames.map(() => new Set());
for (let i = 0; i < dongs.length; i++) for (const j of adj[i]) if (guOfDong[i] !== guOfDong[j]) guAdj[guOfDong[i]].add(guOfDong[j]);
const guPalette = cfg.gu_palette, guColor = new Array(guNames.length).fill(-1);
[...guNames.keys()].sort((a, b) => guAdj[b].size - guAdj[a].size).forEach(i => {
  const used = new Set([...guAdj[i]].map(j => guColor[j])); let c = 0; while (used.has(c)) c++;
  guColor[i] = c % guPalette.length; if (c >= guPalette.length) console.warn('구 팔레트 부족:', guNames[i]);
});
const GUB = cfg.map.gu_border_dots || 1; // 구 테두리 두께(도트, 구 안쪽으로)
const guGrid = new Int16Array(grid.length); for (let i = 0; i < grid.length; i++) guGrid[i] = grid[i] < 0 ? -1 : guOfDong[grid[i]];

// ---------- 한강 ----------
// 행정구역 경계는 강물까지 포함하므로, 한강을 사이에 둔 구끼리 맞닿는 경계(=강 한가운데)를 중앙선으로 삼고
// 일정한 폭(half_width_m)을 줘서 강으로 그린다. 실제 강둑 모양이 아니라 근사치임.
const RV = cfg.river;
const riverPairs = new Set(RV.crossing_pairs.map(([a, b]) => {
  const i = guNames.indexOf(a), j = guNames.indexOf(b); assert.ok(i >= 0 && j >= 0, '구 이름 확인: ' + a + ',' + b);
  return Math.min(i, j) + '-' + Math.max(i, j);
}));
const midline = new Uint8Array(grid.length);
for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
  const i = r * cols + c, g = guGrid[i]; if (g < 0) continue;
  for (const j of [c + 1 < cols ? i + 1 : -1, r + 1 < rows ? i + cols : -1]) {
    if (j < 0) continue; const g2 = guGrid[j];
    if (g2 >= 0 && g2 !== g && riverPairs.has(Math.min(g, g2) + '-' + Math.max(g, g2))) { midline[i] = 1; midline[j] = 1; }
  }
}
// 서울 바깥(고양·김포·하남 등)과 맞닿는 구간: 해당 구의 바깥쪽 경계 도트를 중앙선으로 이어 붙임
for (const ex of RV.outer_extensions || []) {
  const gi = guNames.indexOf(ex.gu); assert.ok(gi >= 0, '구 이름: ' + ex.gu);
  let cEnd = ex.side === 'west' ? Infinity : -Infinity, rEnd = 0;
  for (let i = 0; i < midline.length; i++) if (midline[i]) {
    const c = i % cols, r = (i / cols) | 0;
    if (ex.side === 'west' ? c < cEnd : c > cEnd) { cEnd = c; rEnd = r; }
  }
  // 후보: 서울 밖과 맞닿은 구 경계 도트. 중앙선 끝에서 이어진 줄을 따라가다가 가장 위쪽 끝(강이 서울을 벗어나는 곳)에서 멈춤
  const cand = new Uint8Array(grid.length);
  for (let r = 1; r < rows - 1; r++) for (let c = 1; c < cols - 1; c++) {
    const i = r * cols + c;
    if (guGrid[i] === gi && (grid[i - cols] < 0 || grid[i + cols] < 0 || grid[i - 1] < 0 || grid[i + 1] < 0) && (ex.side === 'west' ? c <= cEnd : c >= cEnd) && r <= rEnd + (ex.max_rows_below || 10)) cand[i] = 1;
  }
  let start = -1, bd = Infinity;
  for (let i = 0; i < cand.length; i++) if (cand[i]) { const d = Math.hypot(i % cols - cEnd, ((i / cols) | 0) - rEnd); if (d < bd) { bd = d; start = i; } }
  assert.ok(start >= 0, '한강 연장 시작점 없음: ' + ex.gu);
  const dist2 = new Int32Array(grid.length).fill(-1), queue = [start]; dist2[start] = 0;
  for (let h = 0; h < queue.length; h++) {
    const i = queue[h], c = i % cols, r = (i / cols) | 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
      const cc = c + dx, rr = r + dy; if (cc < 0 || rr < 0 || cc >= cols || rr >= rows) continue;
      const j = rr * cols + cc; if (cand[j] && dist2[j] < 0) { dist2[j] = dist2[i] + 1; queue.push(j); }
    }
  }
  let tip = start; for (const i of queue) if (((i / cols) | 0) < ((tip / cols) | 0)) tip = i;
  let added = 0; for (const i of queue) if (dist2[i] <= dist2[tip]) { if (!midline[i]) midline[i] = 2; added++; } // 2 = 서울 경계 위 중앙선(안쪽 절반만 보이므로 폭을 키워 그림)
  console.log(`한강 ${ex.side} 끝 연장: ${ex.gu} 바깥 경계 ${added}도트 (후보 ${cand.reduce((n, v) => n + v, 0)}, 이어진 줄 ${queue.length}, 시작 [${start % cols},${(start / cols) | 0}], 끝점 [${tip % cols},${(tip / cols) | 0}], 중앙선 끝 [${cEnd},${rEnd}])`);
}
const RR = RV.half_width_m / MPP, RX = RR * (RV.outer_width_factor || 1.7), RI = Math.ceil(RX);
const river = new Uint8Array(grid.length);
for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
  const mv = midline[r * cols + c]; if (!mv) continue;
  const rad = mv === 2 ? RX : RR;
  for (let dy = -RI; dy <= RI; dy++) for (let dx = -RI; dx <= RI; dx++) {
    if (dx * dx + dy * dy > rad * rad) continue;
    const cc = c + dx, rr = r + dy; if (cc < 0 || rr < 0 || cc >= cols || rr >= rows) continue;
    if (grid[rr * cols + cc] >= 0) river[rr * cols + cc] = 1;
  }
}
const riverDots = river.reduce((n, v) => n + v, 0);
const riverRle = []; for (let i = 0; i < river.length;) { let j = i; while (j < river.length && river[j] === river[i]) j++; riverRle.push([river[i], j - i]); i = j; }

// ---------- 출력 ----------
fs.mkdirSync(path.join(outDir, 'lines'), { recursive: true });
fs.mkdirSync(path.join(outDir, 'tiles'), { recursive: true });
for (const f of fs.readdirSync(path.join(outDir, 'tiles'))) fs.unlinkSync(path.join(outDir, 'tiles', f));
const rle = []; for (let i = 0; i < grid.length;) { let j = i; while (j < grid.length && grid[j] === grid[i]) j++; rle.push([grid[i], j - i]); i = j; }
fs.writeFileSync(path.join(outDir, 'seoul-grid.json'), JSON.stringify({
  note: '행정동 격자(도트 1칸=1셀). cells_rle는 행 우선 RLE [동 인덱스, 연속 칸 수], -1은 서울 밖. 좌표계: 서울시청 기준 미터, x=동쪽, y=남쪽(아래). 실제 좌표 → 도트 = floor((좌표 − origin_m) / m_per_dot).',
  boundary_date: D.boundaryDate, m_per_dot: MPP, dot_px: DOT, cols, rows, origin_m: [x0, y0],
  gus: guNames.map((n, i) => ({ i, name: n, border_color: cfg.map.gu_border_color || guPalette[guColor[i]] })),
  dongs: dongs.map(d => ({ i: d.i, id: d.id, name: d.name, gu: d.gu, gu_i: guOfDong[d.i], color: palette[colorOf[d.i]] })),
  river: { approximate: true, note: '한강: 구 경계(강 중앙선) 기준 근사. 폭 ' + (RV.half_width_m * 2) + 'm', half_width_m: RV.half_width_m, area_km2: Math.round(riverDots * MPP * MPP / 1e4) / 100 },
  river_rle: riverRle,
  cells_rle: rle,
}));
for (const { L, segs } of lines) {
  fs.writeFileSync(path.join(outDir, 'lines', `line${L.id}.json`), JSON.stringify({
    id: L.id, name: L.name, color: L.color,
    coord: 'points: 서울시청 기준 미터(x 동쪽, y 남쪽). points_px: 전체 맵 화면 픽셀(8640×5760 기준). 열차가 따라가는 단선 중심선.',
    rail_date: D.railDate, segments: segs,
  }));
}
fs.writeFileSync(path.join(outDir, 'network.json'), JSON.stringify({
  note: '호선들을 합친 역 정보. transfer=환승역, junction=분기점. 종단역은 다루지 않음(서울 안쪽만 표현). map_px=전체 맵 화면 픽셀.',
  stations: stationsOut,
}, null, 1));

// ---------- PNG ----------
const crcT = new Uint32Array(256).map((_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
const crc = b => { let c = ~0; for (const v of b) c = crcT[(c ^ v) & 255] ^ (c >>> 8); return ~c >>> 0; };
function png(w, h, rgba) {
  const raw = Buffer.alloc((w * 4 + 1) * h);
  for (let y = 0; y < h; y++) { raw[y * (w * 4 + 1)] = 0; Buffer.from(rgba.buffer, rgba.byteOffset + y * w * 4, w * 4).copy(raw, y * (w * 4 + 1) + 1); }
  const chunk = (t, d) => { const l = Buffer.alloc(4); l.writeUInt32BE(d.length); const td = Buffer.concat([Buffer.from(t), d]); const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([l, td, c]); };
  const ih = Buffer.alloc(13); ih.writeUInt32BE(w, 0); ih.writeUInt32BE(h, 4); ih[8] = 8; ih[9] = 6;
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), chunk('IHDR', ih), chunk('IDAT', zlib.deflateSync(raw, { level: 6 })), chunk('IEND', Buffer.alloc(0))]);
}
// 도트 지도: 1도트 = 1픽셀. 동 경계 = 연한 선, 구 경계 = 구별 색의 굵은 테두리(각 구의 안쪽에 그림)
const base = new Uint8ClampedArray(cols * rows * 4);
const guBorder = (c, r, g) => { // 구 안쪽 GUB도트 이내에 다른 구/서울 밖이 있으면 구 테두리
  for (let k = 1; k <= GUB; k++) for (const [dc, dr] of [[k, 0], [-k, 0], [0, k], [0, -k]]) {
    const cc = c + dc, rr = r + dr;
    if (cc < 0 || rr < 0 || cc >= cols || rr >= rows || guGrid[rr * cols + cc] !== g) return true;
  }
  return false;
};
for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
  const i = r * cols + c, d = grid[i]; if (d < 0) continue;
  let rgb;
  if (river[i]) {
    const edge = [i - 1, i + 1, i - cols, i + cols].some(j => j >= 0 && j < grid.length && !river[j] && grid[j] >= 0);
    rgb = hex(edge ? RV.edge_color : RV.color);
  }
  else if (guBorder(c, r, guGrid[i])) rgb = hex(cfg.map.gu_border_color || '#111111');
  else {
    const dongEdge = (c + 1 < cols && grid[i + 1] !== d) || (r + 1 < rows && grid[i + cols] !== d);
    rgb = dongEdge ? shade(hex(palette[colorOf[d]]), .8) : hex(palette[colorOf[d]]);
  }
  base.set([...rgb, 255], i * 4);
}
fs.writeFileSync(path.join(outDir, 'seoul-dong-map.png'), png(cols, rows, base));

// 화면 조각: 1080×720, 도트를 4×4로 확대(nearest). 서울이 없는 조각은 만들지 않음
const dw = SW / DOT, dh = SH / DOT; // 조각 하나 = 270×180 도트
const tilesOut = [], emptyTiles = [];
for (let tr = 0; tr < TR; tr++) for (let tc = 0; tc < TC; tc++) {
  const t = new Uint8ClampedArray(SW * SH * 4); let any = false;
  for (let y = 0; y < dh; y++) for (let x = 0; x < dw; x++) {
    const o = ((tr * dh + y) * cols + tc * dw + x) * 4;
    if (base[o + 3] === 0) continue; any = true;
    for (let yy = 0; yy < DOT; yy++) for (let xx = 0; xx < DOT; xx++) t.set(base.subarray(o, o + 4), ((y * DOT + yy) * SW + x * DOT + xx) * 4);
  }
  if (!any) { emptyTiles.push([tc, tr]); continue; }
  const file = `tiles/t${tc}_${tr}.png`;
  fs.writeFileSync(path.join(outDir, file), png(SW, SH, t));
  tilesOut.push({ col: tc, row: tr, file, x: tc * SW, y: tr * SH });
}
fs.writeFileSync(path.join(outDir, 'tiles.json'), JSON.stringify({
  note: '화면 조각 매니페스트. map_px = (실제좌표_m − origin_m) / m_per_dot × dot_px. 조각 (col,row)의 왼쪽 위 = (col×1080, row×720) 맵 픽셀. 목록에 없는 조각은 서울 밖(빈 칸).',
  screen_px: [SW, SH], screens: [TC, TR], dot_px: DOT, map_px: [MAPW, MAPH], dots: [cols, rows],
  m_per_dot: MPP, origin_m: [x0, y0], boundary_date: D.boundaryDate, tiles: tilesOut, empty: emptyTiles,
}, null, 1));

// 미리보기: 도트 해상도에 선로·역을 그린 합성 이미지
const comp = new Uint8ClampedArray(base);
for (let i = 0; i < comp.length; i += 4) if (comp[i + 3] === 0) comp.set([226, 232, 236, 255], i);
const put = (x, y, rgb) => { x = Math.round(x); y = Math.round(y); if (x >= 0 && y >= 0 && x < cols && y < rows) comp.set([...rgb, 255], (y * cols + x) * 4); };
const disc = (cx, cy, rad, rgb) => { for (let y = -rad; y <= rad; y++) for (let x = -rad; x <= rad; x++) if (x * x + y * y <= rad * rad + 1) put(cx + x, cy + y, rgb); };
const sq = (cx, cy, h, rgb) => { for (let y = -h; y <= h; y++) for (let x = -h; x <= h; x++) put(cx + x, cy + y, rgb); };
const polyDots = pts => { const out = []; for (let i = 1; i < pts.length; i++) { const a = toDot(pts[i - 1]), b = toDot(pts[i]), n = Math.ceil(Math.hypot(b[0] - a[0], b[1] - a[1])); for (let k = 0; k <= n; k++) out.push([a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n]); } return out; };
for (const { L, segs } of lines) for (const seg of segs) {
  const dots = polyDots(seg.points);
  for (const [x, y] of dots) disc(x, y, 2, shade(hex(L.color), .45));
  for (const [x, y] of dots) disc(x, y, 1, hex(L.color));
}
for (const st of stationsOut) {
  const [x, y] = toDot(st.pos_m);
  if (st.transfer) { sq(x, y, 4, [20, 20, 20]); sq(x, y, 3, [255, 255, 255]); sq(x, y, 1, [20, 20, 20]); }
  else { sq(x, y, 3, [20, 20, 20]); sq(x, y, 2, [255, 255, 255]); }
  if (st.junction) { for (let k = -5; k <= 5; k++) { put(x + k, y - 6, [220, 40, 40]); put(x + k, y + 6, [220, 40, 40]); put(x - 6, y + k, [220, 40, 40]); put(x + 6, y + k, [220, 40, 40]); } }
}
fs.writeFileSync(path.join(outDir, 'preview-full.png'), png(cols, rows, comp));
// 서울역 주변을 게임 화면(1080×720)과 같은 배율로 잘라서 확인
{
  const sc = stationsOut.find(s => s.name === '서울역') || stationsOut[0], [cx, cy] = toDot(sc.pos_m);
  const ox = Math.max(0, Math.min(cols - dw, Math.round(cx - dw / 2))), oy = Math.max(0, Math.min(rows - dh, Math.round(cy - dh / 2)));
  const z = new Uint8ClampedArray(SW * SH * 4);
  for (let y = 0; y < dh; y++) for (let x = 0; x < dw; x++) { const o = ((oy + y) * cols + ox + x) * 4; for (let yy = 0; yy < DOT; yy++) for (let xx = 0; xx < DOT; xx++) z.set(comp.subarray(o, o + 4), ((y * DOT + yy) * SW + x * DOT + xx) * 4); }
  fs.writeFileSync(path.join(outDir, 'preview-screen-seoulstation.png'), png(SW, SH, z));
}

// ---------- 검증 요약 ----------
const lineTiles = new Set(); for (const { segs } of lines) for (const sg of segs) for (const q of sg.points_px) lineTiles.add(Math.floor(q[0] / SW) + ',' + Math.floor(q[1] / SH));
console.log(`맵 ${MAPW}×${MAPH}px = 화면 ${TC}×${TR}개, 도트 ${cols}×${rows} (1도트=${DOT}px=${MPP.toFixed(2)}m), 틈 메움 ${holes}칸`);
console.log(`동 ${covered.size}/427 배정, 비어 있는 동: ${dongs.filter(d => !covered.has(d.i)).map(d => d.name).join(',') || '없음'}`);
const cnt = new Int32Array(dongs.length); for (const v of grid) if (v >= 0) cnt[v]++;
console.log('가장 작은 동(도트 수):', dongs.map(d => [d.name, cnt[d.i]]).sort((a, b) => a[1] - b[1]).slice(0, 4).map(t => t.join(' ')).join(', '));
console.log(`한강: 중앙선 ${midline.reduce((n, v) => n + (v ? 1 : 0), 0)}도트, 폭 ${RV.half_width_m * 2}m, 면적 ${(riverDots * MPP * MPP / 1e6).toFixed(1)}㎢`);
console.log(`조각 ${tilesOut.length}개 생성, 빈 칸 ${emptyTiles.length}개, 1호선 통과 조각 ${lineTiles.size}개`);
report.forEach(r => console.log(r));
console.log('역', stationsOut.length, '개, 환승', stationsOut.filter(s => s.transfer).length, ', 분기점', stationsOut.filter(s => s.junction).map(s => s.name).join(',') || '없음');
