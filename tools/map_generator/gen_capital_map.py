#!/usr/bin/env python3
"""수도권 확장 지도 생성기 — 서울 지도(기존 data.json)는 그대로 두고, 서울 밖 구간을 OpenStreetMap 으로 이어 붙인다.

사용:  python tools/map_generator/gen_capital_map.py tools/map_generator/capital.config.json
출력:  assets/map/capital/  (data.json, tiles/, tiles-labeled/, tiles-plain/, overview-*.png)
       확인용 docs/previews/map_capital.png, map_capital_labels.json

방식
  1. 좌표 맞추기: 기존 서울 역(map_px)과 OSM 역(위경도→웹 메르카토르×cos37.5665°)의 차이 중앙값으로 평행 이동만 구한다.
     (축척은 서울 지도와 같음, 1도트 = 21.27 m = 4 px)
  2. 범위: 서울시청 기준 extent_km. 기존 서울 지도(8×8 조각)가 정확히 조각 단위로 밀리도록 맞춘다
     → 기존 서울 좌표는 (왼쪽에 붙인 조각 수×1080, 위에 붙인 조각 수×720) 만큼만 평행 이동.
  3. 행정동 지도: 서울·인천·경기 행정동으로 다시 그림(조각 3종 + 라벨 + 한강).
  4. 노선: OSM 선로를 그래프로 만들고 역 사이 이웃 관계를 구한다. 기존 서울 역은 그대로 쓰고(가까운 역으로 대응),
     서울 밖 새 역과 그 구간만 새 segment 로 붙인다. 갈림길은 선로 각도로 '갈 수 있는 방향'(switches)을 만든다.
필요: pip install pillow numpy scipy  /  라벨 글꼴 Noto Sans CJK
"""
import heapq
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

CFG_PATH = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "capital.config.json"))
HERE = os.path.dirname(CFG_PATH)
ROOT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.abspath(os.path.join(HERE, "..", ".."))
cfg = json.load(open(CFG_PATH, encoding="utf-8"))
OUT = os.path.join(ROOT, "assets", "map", cfg["out"])
PREVIEW = os.path.join(ROOT, "docs", "previews")          # 확인용 미리보기·라벨 목록(게임은 안 씀)
os.makedirs(PREVIEW, exist_ok=True)

base = json.load(open(os.path.join(HERE, cfg["base_data"]), encoding="utf-8"))
MPP, DOT = base["m_per_dot"], base["dot_px"]
SW, SH = base["screen_px"]
DW, DH = SW // DOT, SH // DOT
TW_M, TH_M = DW * MPP, DH * MPP                       # 조각 하나의 실제 크기(m)
R_EARTH = 6378137
K = math.cos(math.radians(37.5665))


def merc(ll):
    lon, lat = ll
    return (R_EARTH * math.radians(lon) * K, -R_EARTH * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * K)


def r1(v):
    return round(v * 10) / 10


def load(name):
    return json.load(open(os.path.join(HERE, cfg[name]), encoding="utf-8"))["features"]


line_feats = {f["properties"]["id"]: f for f in load("lines_geojson")}
station_feats = load("stations_geojson")
dong_feats = load("dongs")

# ---------------- 1. 좌표 맞추기 (기존 서울 프레임: 서울 지도 왼쪽 위 = (0, 0) m) ----------------
old_st = {s["name"]: s for s in base["stations"]}
old_m = {n: (s["map_px"][0] / DOT * MPP, s["map_px"][1] / DOT * MPP) for n, s in old_st.items()}
osm_by_name = defaultdict(list)
for f in station_feats:
    osm_by_name[f["properties"]["name_ko"]].append(merc(f["geometry"]["coordinates"]))
d0 = [np.subtract(old_m[n], osm_by_name[n.split(" ")[0]][0]) for n in old_m if n.split(" ")[0] in osm_by_name]
t0 = np.median(d0, 0)
d1 = []
for n in old_m:
    c = osm_by_name.get(n.split(" ")[0])
    if c:
        k = int(np.argmin([math.dist(np.add(p, t0), old_m[n]) for p in c]))
        d1.append(np.subtract(old_m[n], c[k]))
T = np.median(d1, 0)
resid = [math.dist(np.add(p, T), old_m[n]) for n in old_m for p in osm_by_name.get(n.split(" ")[0], [])[:1]]


def to_m(ll):
    p = merc(ll)
    return (p[0] + T[0], p[1] + T[1])


# ---------------- 2. 범위 ----------------
ax, ay = old_m[cfg["anchor_station"]]
E = cfg["extent_km"]
OX = max(0, math.ceil((E["w"] * 1000 - ax) / TW_M))                  # 왼쪽에 붙일 조각 수
OY = max(0, math.ceil((E["n"] * 1000 - ay) / TH_M))                  # 위에 붙일 조각 수
old_w_t, old_h_t = base["map_px"][0] // SW, base["map_px"][1] // SH
TC = OX + max(old_w_t, math.ceil((ax + E["e"] * 1000) / TW_M))
TR = OY + max(old_h_t, math.ceil((ay + E["s"] * 1000) / TH_M))
cols, rows = TC * DW, TR * DH
X0, Y0 = -OX * TW_M, -OY * TH_M                                       # 새 지도 왼쪽 위(기존 프레임 m)
SHIFT = (OX * SW, OY * SH)                                            # 기존 서울 map_px 에 더할 값


def to_dot(p):
    return ((p[0] - X0) / MPP, (p[1] - Y0) / MPP)


def to_px(p):
    q = to_dot(p)
    return [r1(q[0] * DOT), r1(q[1] * DOT)]


def px_to_m(px):
    return (px[0] / DOT * MPP + X0, px[1] / DOT * MPP + Y0)


def inside_px(px, margin=0):
    return margin <= px[0] <= cols * DOT - margin and margin <= px[1] <= rows * DOT - margin


def shift(px):
    return [r1(px[0] + SHIFT[0]), r1(px[1] + SHIFT[1])]


# ---------------- 3. 행정동 격자 ----------------
def polys_of(geom):
    return [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]


dongs = []
for f in dong_feats:
    p = f["properties"]
    dongs.append({"name": p["adm_nm"].split(" ")[-1], "gu": p["sggnm"], "sido": p["sidonm"],
                  "polys": [[[to_dot(to_m(c)) for c in ring] for ring in poly] for poly in polys_of(f["geometry"])]})
grid = np.full((rows, cols), -1, dtype=np.int16)
for i, d in enumerate(dongs):
    for poly in d["polys"]:
        ext = poly[0]
        c0, c1 = max(0, int(min(q[0] for q in ext)) - 1), min(cols, int(max(q[0] for q in ext)) + 2)
        r0, rr1 = max(0, int(min(q[1] for q in ext)) - 1), min(rows, int(max(q[1] for q in ext)) + 2)
        if c0 >= c1 or r0 >= rr1:
            continue
        im = Image.new("1", (c1 - c0, rr1 - r0), 0)
        dr = ImageDraw.Draw(im)
        dr.polygon([(q[0] - c0 - .5, q[1] - r0 - .5) for q in ext], fill=1)
        for hole in poly[1:]:
            dr.polygon([(q[0] - c0 - .5, q[1] - r0 - .5) for q in hole], fill=0)
        grid[r0:rr1, c0:c1][np.array(im, dtype=bool)] = i
for _ in range(2):                                   # 한 칸 틈 메우기
    L_, R_ = np.roll(grid, 1, 1), np.roll(grid, -1, 1)
    grid = np.where((grid == -1) & (L_ >= 0) & (L_ == R_), L_, grid)
    U_, D_ = np.roll(grid, 1, 0), np.roll(grid, -1, 0)
    grid = np.where((grid == -1) & (U_ >= 0) & (U_ == D_), U_, grid)
used = sorted(set(int(v) for v in np.unique(grid)) - {-1})
land = grid >= 0

adj = defaultdict(set)
for a, b in ((grid[:, :-1], grid[:, 1:]), (grid[:-1, :], grid[1:, :])):
    m = (a >= 0) & (b >= 0) & (a != b)
    for u, v in set(zip(a[m].tolist(), b[m].tolist())):
        adj[u].add(v)
        adj[v].add(u)
palette = cfg["dong_palette"]
color_of = {}
for i in sorted(used, key=lambda k: -len(adj[k])):
    taken = {color_of.get(j) for j in adj[i]}
    c = 0
    while c in taken:
        c += 1
    color_of[i] = c % len(palette)

gu_names = sorted({dongs[i]["gu"] for i in used})
gu_of = np.array([gu_names.index(d["gu"]) if d["gu"] in gu_names else -1 for d in dongs] + [-1], dtype=np.int16)
gu_grid = gu_of[grid]

# ---------------- 한강(구 경계 = 강 중앙선, 폭 근사) ----------------
RV = cfg["river"]
pairs = set()
for a, b in RV["crossing_pairs"]:
    if a in gu_names and b in gu_names:
        i, j = gu_names.index(a), gu_names.index(b)
        pairs.add((min(i, j), max(i, j)))
mid = np.zeros_like(land)
for (a, b, sa, sb) in ((gu_grid[:, :-1], gu_grid[:, 1:], (slice(None), slice(0, -1)), (slice(None), slice(1, None))),
                       (gu_grid[:-1, :], gu_grid[1:, :], (slice(0, -1), slice(None)), (slice(1, None), slice(None)))):
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    hit = np.zeros(a.shape, dtype=bool)
    for (i, j) in pairs:
        hit |= (lo == i) & (hi == j)
    mid[sa] |= hit
    mid[sb] |= hit
river = land & (distance_transform_edt(~mid) <= RV["half_width_m"] / MPP) if mid.any() else np.zeros_like(land)


def hex2rgb(h):
    return [int(h[k:k + 2], 16) for k in (1, 3, 5)]


# ---------------- 조각 그림 ----------------
pal = np.array([hex2rgb(palette[color_of.get(i, 0)]) for i in range(len(dongs))] + [[0, 0, 0]], dtype=np.float32)
img = pal[grid]
dong_edge = np.zeros_like(land)
dong_edge[:, :-1] |= grid[:, :-1] != grid[:, 1:]
dong_edge[:-1, :] |= grid[:-1, :] != grid[1:, :]
img[dong_edge & land] *= .8
gpad = np.pad(gu_grid, 1, constant_values=-1)
gu_edge = land & ((gpad[1:-1, :-2] != gu_grid) | (gpad[1:-1, 2:] != gu_grid) | (gpad[:-2, 1:-1] != gu_grid) | (gpad[2:, 1:-1] != gu_grid))
img[gu_edge] = hex2rgb(cfg["gu_border_color"])
rpad = np.pad(river, 1)
r_edge = river & ~(rpad[1:-1, :-2] & rpad[1:-1, 2:] & rpad[:-2, 1:-1] & rpad[2:, 1:-1])
img[river] = hex2rgb(RV["color"])
img[r_edge] = hex2rgb(RV["edge_color"])
rgba = np.zeros((rows, cols, 4), dtype=np.uint8)
rgba[..., :3] = img.clip(0, 255).astype(np.uint8)
rgba[..., 3] = np.where(land, 255, 0)
lpad = np.pad(land, 1)
outer = land & ~(lpad[1:-1, :-2] & lpad[1:-1, 2:] & lpad[:-2, 1:-1] & lpad[2:, 1:-1])
plain = np.zeros_like(rgba)
plain[land] = [*cfg["plain_fill"], 255]
plain[river] = [*hex2rgb(RV["color"]), 255]
plain[outer] = [*cfg["plain_edge"], 255]

# ---------------- 라벨 ----------------
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc"


def font(weight, px):
    return ImageFont.truetype(FONT % weight, px, index=1)


def gu_display(n):
    i = n.find("시")
    return n[:i + 1] + " " + n[i + 1:] if 0 < i < len(n) - 1 and n.endswith("구") else n


GU_A, DONG_A, RIV_A, GU_DOTS = .40, .15, .45, 15
INK = np.array([38, 54, 75], dtype=np.float32)
RIV_INK = np.array([30, 78, 140], dtype=np.float32)
gu_mask = Image.new("L", (cols, rows), 0)
gd = ImageDraw.Draw(gu_mask)
f_gu = font("Bold", GU_DOTS)
gu_labels = []


def put_dot_text(draw, cx, cy, text, fnt):
    w = sum(fnt.getlength(c) + 1 for c in text) - 1
    x = cx - w / 2
    for c in text:
        if c != " ":
            draw.text((x, cy), c, font=fnt, fill=255, anchor="lm")
        x += fnt.getlength(c) + 1


for gi, gu in enumerate(gu_names):
    sel = (gu_grid == gi) & ~river
    yy, xx = np.nonzero(sel)
    if len(xx) < 400:
        continue
    cx, cy = xx.mean(), yy.mean()
    if not sel[int(cy), int(cx)]:
        k = np.argmin((xx - cx) ** 2 + (yy - cy) ** 2)
        cx, cy = xx[k], yy[k]
    name = gu_display(gu)
    gu_labels.append({"name": name, "dot": [int(cx), int(cy)], "map_px": [int(cx * DOT), int(cy * DOT)], "size_px": GU_DOTS * DOT, "alpha": GU_A})
    put_dot_text(gd, cx, cy, name, f_gu)
gu_big_small = np.array(gu_mask) >= 110


def integral(m):
    return np.pad(m.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))


def cover(ii, a0, b0, a1, b1):
    if a0 < 0 or b0 < 0 or a1 > ii.shape[1] - 1 or b1 > ii.shape[0] - 1:
        return 0.0
    return (ii[b1, a1] - ii[b0, a1] - ii[b1, a0] + ii[b0, a0]) / max(1, (a1 - a0) * (b1 - b0))


def split2(name):
    if len(name) <= 3:
        return None
    dots = [i for i, ch in enumerate(name) if ch == "·"]
    if dots:
        k = min(dots, key=lambda i: abs(i + 1 - len(name) / 2))
        return name[:k + 1] + "\n" + name[k + 1:]
    h = (len(name) + 1) // 2
    return name[:h] + "\n" + name[h:]


fcache = {}


def F(px):
    if px not in fcache:
        fcache[px] = font("Medium", px)
    return fcache[px]


dummy = ImageDraw.Draw(Image.new("L", (4, 4)))


def box_dots(text, px):
    l, t, r, b = dummy.multiline_textbbox((0, 0), text, font=F(px), spacing=2, align="center")
    return (r - l) / DOT + 1.2, (b - t) / DOT + 1.2


SIZES = list(range(24, 9, -1))
dong_text = []                                  # (X, Y, text, px) 맵 px — 조각마다 따로 그림(큰 지도라 한 장으로 못 만듦)
dong_labels = []
for i in used:
    m = (grid == i) & ~river
    yy, xx = np.nonzero(m)
    if len(xx) < 30:
        continue
    ya, yb, xa, xb = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
    edt = distance_transform_edt(np.pad(m[ya:yb, xa:xb], 1))[1:-1, 1:-1]
    ii = integral(m[ya:yb, xa:xb])
    cy_, cx_ = np.nonzero(edt >= edt.max() * .55)
    order = np.argsort(-edt[cy_, cx_])[::max(1, len(cy_) // 80)]
    cand = [(cx_[k], cy_[k]) for k in order]
    name = dongs[i]["name"]
    layouts = [name] + ([split2(name)] if split2(name) else [])
    best = {}
    for li, text in enumerate(layouts):
        for px in SIZES:
            w, h = box_dots(text, px)
            hit = next(((cx, cy) for cx, cy in cand
                        if cover(ii, int(round(cx - w / 2)), int(round(cy - h / 2)), int(round(cx + w / 2)), int(round(cy + h / 2))) >= .94), None)
            if hit:
                best[li] = (px, hit, text)
                break
    if 0 in best and (1 not in best or best[0][0] >= best[1][0] * .85):
        px, (cx, cy), text = best[0]
    elif 1 in best:
        px, (cx, cy), text = best[1]
    else:
        text, px = layouts[-1], SIZES[-1]
        cy, cx = divmod(int(np.argmax(edt)), edt.shape[1])
    X, Y = (xa + cx + .5) * DOT, (ya + cy + .5) * DOT
    dong_text.append((X, Y, text, px))
    dong_labels.append({"name": name, "gu": gu_display(dongs[i]["gu"]), "map_px": [int(X), int(Y)], "size_px": px, "lines": text.split("\n"), "alpha": DONG_A})

rv_mask = Image.new("L", (cols, rows), 0)
river_labels = []
if river.any():
    rd = ImageDraw.Draw(rv_mask)
    rv_ii = integral(river)
    redt = distance_transform_edt(np.pad(river, 1))[1:-1, 1:-1]
    ry, rx = np.nonzero(redt >= redt.max() * .6)
    tw = f_gu.getlength(RV["name"]) + 1
    for q in (.12, .35, .6, .85):
        tx = np.quantile(rx, q)
        ok = [(abs(x - tx), x, y) for x, y in zip(rx, ry)
              if cover(rv_ii, int(x - tw / 2 - 2), int(y - GU_DOTS / 2 - 2), int(x + tw / 2 + 2), int(y + GU_DOTS / 2 + 2)) >= .99]
        if not ok:
            continue
        _, x, y = min(ok)
        river_labels.append({"name": RV["name"], "dot": [int(x), int(y)], "map_px": [int(x * DOT), int(y * DOT)], "size_px": GU_DOTS * DOT, "alpha": RIV_A})
        put_dot_text(rd, x, y, RV["name"], f_gu)
rv_small = np.array(rv_mask) >= 110

# ---------------- 4. 노선 ----------------
def cumlen(pts):
    c = [0.0]
    for a, b in zip(pts, pts[1:]):
        c.append(c[-1] + math.dist(a, b))
    return c


def simplify(pts, tol=8):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1
    md, mi = 0, 0
    for k in range(1, len(pts) - 1):
        d = abs(dy * (pts[k][0] - a[0]) - dx * (pts[k][1] - a[1])) / L
        if d > md:
            md, mi = d, k
    if md <= tol:
        return [a, b]
    return simplify(pts[:mi + 1], tol)[:-1] + simplify(pts[mi:], tol)


def track_graph(geom):
    parts = geom["coordinates"] if geom["type"] == "MultiLineString" else [geom["coordinates"]]
    nodes, part_of = [], []
    edges = defaultdict(list)
    for pi, part in enumerate(parts):
        pts = [to_m(p) for p in part]
        start = len(nodes)
        for k, p in enumerate(pts):
            if k:
                q = pts[k - 1]
                n = max(1, math.ceil(math.dist(p, q) / 20))
                for s in range(1, n):
                    nodes.append((q[0] + (p[0] - q[0]) * s / n, q[1] + (p[1] - q[1]) * s / n))
                    part_of.append(pi)
            nodes.append(p)
            part_of.append(pi)
        for k in range(start + 1, len(nodes)):
            w = math.dist(nodes[k], nodes[k - 1])
            edges[k].append((k - 1, w))
            edges[k - 1].append((k, w))
    H = 60
    bucket = defaultdict(list)
    for k, p in enumerate(nodes):
        bucket[(int(p[0] // H), int(p[1] // H))].append(k)
    JR = cfg["join_radius_m"]
    for k, p in enumerate(nodes):
        cx, cy = int(p[0] // H), int(p[1] // H)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in bucket[(cx + dx, cy + dy)]:
                    if j > k and part_of[j] != part_of[k]:
                        d = math.dist(p, nodes[j])
                        if d <= JR:
                            edges[k].append((j, d * 1.5 + 5))
                            edges[j].append((k, d * 1.5 + 5))
    # 끊긴 선로 잇기: 조각 끝점 → 다른 조각의 가장 가까운 점(bridge_m 이내)
    BR = cfg.get("bridge_m", 600)
    ends = []
    k0 = 0
    for pi in range(len(parts)):
        ks = [k for k in range(k0, len(nodes)) if part_of[k] == pi]
        if ks:
            ends += [ks[0], ks[-1]]
            k0 = ks[-1] + 1
    for e in ends:
        p = nodes[e]
        best = (1e18, -1)
        for k, q in enumerate(nodes):
            if part_of[k] != part_of[e]:
                d = math.dist(p, q)
                if d < best[0]:
                    best = (d, k)
        if JR < best[0] <= BR:
            edges[e].append((best[1], best[0] * 1.2))
            edges[best[1]].append((e, best[0] * 1.2))
    return nodes, edges, bucket, H


def nearest(nodes, bucket, H, q):
    cx, cy = int(q[0] // H), int(q[1] // H)
    best = (1e18, -1)
    for rad in range(0, 6):
        for dx in range(-rad, rad + 1):
            for dy in range(-rad, rad + 1):
                if max(abs(dx), abs(dy)) != rad:
                    continue
                for j in bucket.get((cx + dx, cy + dy), []):
                    d = math.dist(q, nodes[j])
                    if d < best[0]:
                        best = (d, j)
        if best[1] >= 0 and best[0] < rad * H:
            break
    return best


def neighbors_from(starts, edges, owner, me):
    """me 역의 선로 노드들(starts)에서 선로를 따라가다 처음 만나는 다른 역들 {역: (거리, 경로 노드들)}.
    역 근처 노드는 모두 그 역 소속(owner)이라 나란한 급행 선로도 역을 건너뛰지 못한다."""
    dist, prev = {}, {}
    heap = []
    for k, d0 in starts:
        dist[k], prev[k] = d0, -1
        heap.append((d0, k))
    heapq.heapify(heap)
    found = {}
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist.get(u, 1e18):
            continue
        o = owner.get(u)
        if o is not None and o != me:
            if o not in found:
                path = []
                v = u
                while v != -1:
                    path.append(v)
                    v = prev[v]
                found[o] = (d, path[::-1])
            continue
        if d > 15000:
            continue
        for v, w in edges[u]:
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(heap, (nd, v))
    return found


# 기존 서울 역: 기존 프레임 m 좌표, 호선
OSM_ONLY = cfg.get("seoul_source") == "osm"          # 서울도 OSM 으로 새로 그림(기존 서울 역·선로는 좌표 맞춤에만 씀)
old_pos = {} if OSM_ONLY else {n: old_m[n] for n in old_st}
old_lines_of = {} if OSM_ONLY else {n: set(s["lines"]) for n, s in old_st.items()}
new_st = {}                      # 이름 → {"pos": m, "lines": set}
lines_by_id = {l["id"]: l for l in base["lines"]}
report = []


def pos_of_any(n):
    return new_st[n]["pos"] if n in new_st else old_pos[n]


added_edges = {}                 # lid → [(a, b, length_m, path_m)]
for Lc in cfg["lines"]:
    lid = Lc["id"]
    g = line_feats[Lc["src"]]["geometry"]
    nodes, edges, bucket, H = track_graph(g)
    # 이 호선의 OSM 역 → 이름 결정(기존 서울 역에 대응 / 새 역)
    st_pos = {}
    for f in station_feats:
        if Lc["src"] not in f["properties"]["lines"]:
            continue
        q = to_m(f["geometry"]["coordinates"])
        d, k = nearest(nodes, bucket, H, q)
        if k < 0 or d > cfg["max_snap_m"]:
            continue
        osm_name = f["properties"]["name_ko"]
        # 1) 같은 호선의 기존 역 중 가까운 역  2) 다른 호선이라도 같은 이름의 가까운 기존 역
        cand = [(math.dist(q, p), n) for n, p in old_pos.items() if lid in old_lines_of[n]]
        cand = [c for c in cand if c[0] <= cfg["match_existing_m"]]
        if not cand:
            cand = [(math.dist(q, p), n) for n, p in old_pos.items() if n.split(" ")[0] == osm_name and math.dist(q, p) <= cfg["same_station_m"]]
        if cand:
            name = min(cand)[1]
        else:
            name = osm_name
            if name in old_pos or (name in new_st and math.dist(new_st[name]["pos"], q) > cfg["same_station_m"]):
                name = f"{osm_name} {Lc.get('name') or lines_by_id[lid]['name']}"
            e = new_st.setdefault(name, {"pos": q, "lines": set()})
            e["lines"].add(lid)
        dup = [n for n, p in st_pos.items() if math.dist(p, nodes[k]) < cfg.get("alias_m", 300) and n != name]
        if dup:                                      # 같은 역의 다른 이름(예: 총신대입구(이수) / 이수)
            if name in new_st and name not in dup and len(new_st[name]["lines"]) == 1 and new_st[name]["pos"] == q:
                del new_st[name]
            continue
        st_pos.setdefault(name, nodes[k])          # 이 호선 선로 위로 붙인 위치(환승역은 OSM 점이 다른 호선 승강장에 있음)
    for n, p in old_pos.items():                     # 이 호선의 기존 서울 역(OSM 역에 이 호선 표시가 없어도)
        if lid in old_lines_of[n] and n not in st_pos:
            d, k = nearest(nodes, bucket, H, p)
            if k >= 0 and d <= cfg["max_snap_m"]:
                st_pos[n] = nodes[k]
    # 역마다 선로를 따라 다른 역까지 거리(최단 경로)를 구하고, 사이에 다른 역이 끼지 않는 쌍만 이웃으로 본다.
    snap = {n: nearest(nodes, bucket, H, q)[1] for n, q in st_pos.items()}
    node_st = defaultdict(list)
    for n, k in snap.items():
        node_st[k].append(n)
    LIM = cfg.get("max_edge_m", 20000)
    D, P = {}, {}
    for a, ka in snap.items():
        dist, prev = {ka: 0.0}, {ka: -1}
        heap = [(0.0, ka)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, 1e18) or d > LIM:
                continue
            for v, w in edges[u]:
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v], prev[v] = nd, u
                    heapq.heappush(heap, (nd, v))
        for b, kb in snap.items():
            if b != a and kb in dist:
                D[(a, b)] = dist[kb]
                P[(a, b)] = (prev, kb)
    TOL = cfg.get("between_tol_m", 250)
    out = []
    names = list(st_pos)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dab = D.get((a, b))
            if dab is None:
                continue
            if any(D.get((a, c), 1e18) + D.get((c, b), 1e18) <= dab * 1.15 + TOL for c in names if c not in (a, b)):
                continue                             # 사이에 다른 역이 있음(또는 갈림목을 거쳐 돌아가는 쌍)
            pa, pb = pos_of_any(a), pos_of_any(b)
            if not (inside_px(to_px(pa), 40) and inside_px(to_px(pb), 40)):
                continue                             # 지도 밖으로 나가는 구간
            if a in old_pos and b in old_pos:
                continue                             # 서울 안 구간은 기존 데이터 그대로
            prev, v = P[(a, b)]
            path = []
            while v != -1:
                path.append(v)
                v = prev[v]
            pts = [pa] + [nodes[v] for v in path[::-1]] + [pb]
            out.append((a, b, dab, pts))
    # 세 역 a-b-c 가 서로 다 이어졌으면(역이 아닌 갈림목을 거쳐 가지끼리 이어진 쌍) 가장 긴 구간을 버림
    L_of = {frozenset((a, b)): d for a, b, d, _ in out}
    nbr = defaultdict(set)
    for a, b, _, _ in out:
        nbr[a].add(b)
        nbr[b].add(a)
    drop = {frozenset(x) for x in cfg.get("drop_edges", {}).get(lid, [])}   # 직접 정한 예외(실제 운행이 없는 갈림 방향)
    for key, dab in L_of.items():
        if drop & {frozenset((x, y)) for x in key for y in nbr[x] & nbr[next(iter(key - {x}))]}:
            continue
        a, b = tuple(key)
        for c in nbr[a] & nbr[b]:
            if dab >= max(L_of[frozenset((a, c))], L_of[frozenset((c, b))]):   # 세 역이 서로 이어지면 가장 긴 쪽이 갈림목 우회
                drop.add(key)
                if os.environ.get("DBG"):
                    print("  삼각", lid, a, b, "via", c)
    out = [e for e in out if frozenset(e[:2]) not in drop]
    added_edges[lid] = out
    report.append(f"{lid}: 새 구간 {len(out)}개")

# 새 역 확정(지도 안 + 구간이 있는 역만)
linked = defaultdict(set)
for lid, es in added_edges.items():
    for a, b, _, _ in es:
        linked[a].add(lid)
        linked[b].add(lid)


def pos_of(n):
    return new_st[n]["pos"] if n in new_st else old_pos[n]


# ---------------- segments 만들기 ----------------
def chains(es):
    """간선 목록 → 갈림·끝 역에서 끊은 경로들 [[역...], ...]"""
    nb = defaultdict(list)
    for a, b, _, _ in es:
        nb[a].append(b)
        nb[b].append(a)
    used_e, out = set(), []
    ends = [n for n in nb if len(nb[n]) != 2]
    for s in ends + list(nb):
        for t in nb[s]:
            if frozenset((s, t)) in used_e:
                continue
            path = [s, t]
            used_e.add(frozenset((s, t)))
            while len(nb[path[-1]]) == 2:
                nxt = [x for x in nb[path[-1]] if frozenset((path[-1], x)) not in used_e]
                if not nxt:
                    break
                used_e.add(frozenset((path[-1], nxt[0])))
                path.append(nxt[0])
            out.append(path)
    return out


def seg_of(path, emap):
    edges_out, pts_all, at = [], [], [0.0]
    for a, b in zip(path, path[1:]):
        L, pts = emap[frozenset((a, b))]
        if math.dist(pts[0], pos_of(a)) > math.dist(pts[-1], pos_of(a)):
            pts = pts[::-1]
        pts = simplify([pos_of(a)] + pts[1:-1] + [pos_of(b)])
        edges_out.append({"from": a, "to": b, "length_m": r1(L), "estimated": False, "paths_px": [[to_px(p) for p in pts]]})
        pts_all += pts if not pts_all else pts[1:]
        at.append(at[-1] + L)
    return {"stations": path, "points_px": [to_px(p) for p in pts_all], "paths_px": [e["paths_px"][0] for e in edges_out],
            "station_at_m": [r1(a) for a in at], "length_m": r1(at[-1]), "closed": False, "edges": edges_out}


lines_out = []
for Lc in cfg["lines"]:
    lid = Lc["id"]
    if lid in lines_by_id and not OSM_ONLY:
        L = json.loads(json.dumps(lines_by_id[lid]))
        for s in L["segments"]:
            s["points_px"] = [shift(p) for p in s.get("points_px", [])]
            s["paths_px"] = [[shift(p) for p in path] for path in s.get("paths_px", [])]
            for e in s.get("edges", []):
                e["paths_px"] = [[shift(p) for p in path] for path in e["paths_px"]]
        L["segments"] = [s for s in L["segments"] if len(s["stations"]) > 1]
    else:
        meta = lines_by_id.get(lid, {})
        L = {"id": lid, "name": Lc.get("name") or meta["name"], "color": Lc.get("color") or meta["color"], "enabled": True, "switches": {}, "segments": []}
    es = added_edges.get(lid, [])
    emap = {frozenset((a, b)): (d, pts) for a, b, d, pts in es}
    for path in chains(es):
        L["segments"].append(seg_of(path, emap))
    L["enabled"] = bool(L["segments"])
    lines_out.append(L)

# 갈림길: 한 호선에서 이웃 역이 3개 이상인 역 → 선로 각도로 갈 수 있는 방향
junction = defaultdict(set)
for L in lines_out:
    nb = defaultdict(set)
    for s in L["segments"]:
        st = s["stations"]
        for a, b in zip(st, st[1:]):
            if a != b:
                nb[a].add(b)
                nb[b].add(a)
    for n, ns in nb.items():
        if len(ns) < 3:
            continue
        junction[n].add(L["id"])
        if n in L["switches"]:
            continue
        p = pos_of(n)
        sw = {}
        for prev in ns:
            q = pos_of(prev)
            din = math.atan2(p[1] - q[1], p[0] - q[0])
            ok = []
            for nx in ns:
                if nx == prev:
                    continue
                r = pos_of(nx)
                dout = math.atan2(r[1] - p[1], r[0] - p[0])
                diff = abs((dout - din + math.pi) % (2 * math.pi) - math.pi)
                if diff < math.radians(100):
                    ok.append(nx)
            sw[prev] = ok or [x for x in ns if x != prev]
        L["switches"][n] = sw

# ---------------- 역 목록 ----------------
def dong_at(p):
    c, r = to_dot(p)
    c, r = int(min(max(c, 0), cols - 1)), int(min(max(r, 0), rows - 1))
    i = int(grid[r, c])
    return (dongs[i]["name"], gu_display(dongs[i]["gu"])) if i >= 0 else ("", "")


line_ids_of = defaultdict(list)
for L in lines_out:
    for s in L["segments"]:
        for n in s["stations"]:
            if L["id"] not in line_ids_of[n]:
                line_ids_of[n].append(L["id"])
stations_out = []
for s in ([] if OSM_ONLY else base["stations"]):
    s = dict(s)
    s["map_px"] = shift(s["map_px"])
    s["lines"] = list(dict.fromkeys(list(s["lines"]) + line_ids_of.get(s["name"], [])))
    s["transfer"] = len(s["lines"]) > 1
    s["switch"] = sorted(set(s.get("switch", [])) | junction.get(s["name"], set()))
    s["junction"] = bool(s["switch"]) or s.get("junction", False)
    stations_out.append(s)
for n, e in new_st.items():
    if n not in linked:
        continue
    dn, gu = dong_at(e["pos"])
    lids = line_ids_of[n]
    stations_out.append({"name": n, "lines": lids, "transfer": len(lids) > 1, "junction": bool(junction.get(n)),
                         "map_px": to_px(e["pos"]), "dong": dn, "gu": gu,
                         "label_spot": {"badge": "left", "name": "up", "wrap": False}, "switch": sorted(junction.get(n, set()))})

# ---------------- 5. 저장 ----------------
for sub in ("tiles", "tiles-labeled", "tiles-plain"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    for fn in os.listdir(os.path.join(OUT, sub)):
        os.remove(os.path.join(OUT, sub, fn))


def big(a):
    return a.repeat(DOT, 0).repeat(DOT, 1)


OV = 4                                                   # 전체 축소 그림 배율(1/4)
ov = {k: Image.new("RGBA", (cols * DOT // OV, rows * DOT // OV), (0, 0, 0, 0)) for k in ("tiles", "tiles-labeled", "tiles-plain")}
tiles_out = []
for tr in range(TR):
    for tc in range(TC):
        ys_, xs_ = slice(tr * DH, (tr + 1) * DH), slice(tc * DW, (tc + 1) * DW)
        if not land[ys_, xs_].any():
            continue
        fn = f"t{tc}_{tr}.png"
        t = big(rgba[ys_, xs_])
        pl = big(plain[ys_, xs_])
        # 라벨: 이 조각에 걸친 동 이름만 그림
        lab = Image.new("L", (SW, SH), 0)
        ld = ImageDraw.Draw(lab)
        for X, Y, text, px in dong_text:
            if tc * SW - 200 < X < (tc + 1) * SW + 200 and tr * SH - 120 < Y < (tr + 1) * SH + 120:
                ld.multiline_text((X - tc * SW, Y - tr * SH), text, font=F(px), fill=255, anchor="mm", align="center", spacing=2)
        dong_a = np.array(lab).astype(np.float32) / 255
        im = t.astype(np.float32)
        lnd = im[..., 3] > 0
        for a, ink in ((np.where(lnd, dong_a * DONG_A, 0), INK),
                       (np.where(lnd & big(gu_big_small[ys_, xs_]), GU_A, 0), INK),
                       (np.where(lnd & big(rv_small[ys_, xs_]), RIV_A, 0), RIV_INK)):
            for ch in range(3):
                im[..., ch] = im[..., ch] * (1 - a) + ink[ch] * a
        lb = im.astype(np.uint8)
        for key, arr in (("tiles", t), ("tiles-labeled", lb), ("tiles-plain", pl)):
            pim = Image.fromarray(arr)
            pim.save(os.path.join(OUT, key, fn))
            small = pim.resize((SW // OV, SH // OV), Image.BOX)
            ov[key].paste(small, (tc * SW // OV, tr * SH // OV))
        tiles_out.append({"col": tc, "row": tr, "x": tc * SW, "y": tr * SH, "file": fn})
for key, im in ov.items():
    im.save(os.path.join(OUT, f"overview-{key}.png"))

data = {
    "_source": "서울 안: 기존 지도(선로 Esri Korea 공개 서비스, 행정동 SGIS/vuski admdongkor). "
               "서울 밖 선로·역: © OpenStreetMap contributors (ODbL), plazalabs/kr-rail-map 정리본. "
               "행정동: vuski/admdongkor ver20261001 (CC BY 4.0, 원자료 통계청 SGIS). 한강은 구 경계 기준 근사.",
    "region": "capital", "name": "수도권",
    "screen_px": [SW, SH], "map_px": [cols * DOT, rows * DOT], "m_per_dot": MPP, "dot_px": DOT,
    "seoul_shift_px": list(SHIFT), "overview": {"scale": 1 / OV, "files": {k: f"overview-{k}.png" for k in ov}},
    "tiles": tiles_out, "lines": lines_out, "stations": stations_out,
}
json.dump(data, open(os.path.join(OUT, "data.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"districts": gu_labels, "dongs": dong_labels, "river": river_labels},
          open(os.path.join(PREVIEW, f"map_{cfg['out']}_labels.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 미리보기(1/4): 라벨 지도 + 선로 + 역
pv = ov["tiles-labeled"].convert("RGB")
dr = ImageDraw.Draw(pv)
for L in lines_out:
    col = tuple(hex2rgb(L["color"]))
    for s in L["segments"]:
        st = s["stations"]
        P = {x["name"]: x["map_px"] for x in stations_out}
        dr.line([(P[n][0] / OV, P[n][1] / OV) for n in st], fill=col, width=4)
for s in stations_out:
    x, y = s["map_px"][0] / OV, s["map_px"][1] / OV
    r = 4 if s["transfer"] else 3
    dr.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255), outline=(20, 20, 20))
pv.save(os.path.join(PREVIEW, f"map_{cfg['out']}.png"))

print(f"좌표 맞춤: 이동 {T.round(1)} m, 기존 역과 OSM 역 차이 중앙값 {np.median(resid):.0f} m")
print(f"맵 {cols * DOT}×{rows * DOT}px = 화면 {TC}×{TR}개, 조각 {len(tiles_out)}개, 서울 이동 {SHIFT}")
print(f"동 {len(used)}개, 구·시 {len(gu_names)}개, 한강 {int(river.sum())}도트")
print("; ".join(report))
print("역", len(stations_out), f"(새 역 {sum(1 for n in new_st if n in linked)})", "갈림길", sorted(junction))
