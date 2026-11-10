#!/usr/bin/env python3
"""지역 지도 생성기 (서울 이외 지역용, gen-game-map.cjs + add-district-labels.py 를 파이썬으로 옮김).

사용:  python tools/map_generator/gen_region_map.py tools/map_generator/daegu.config.json
출력:  assets/map/<region>/
         data.json        게임이 읽는 지도(서울 data.json 과 같은 형식)
         tiles/           행정동 색 지도 조각(1080×720)
         tiles-labeled/   + 구·동 이름
         tiles-plain/     행정구역 끔(단색)
         (확인용) docs/previews/map_<region>.png, map_<region>_labels.json — 선로·역 합성 미리보기, 라벨 위치

입력(설정 파일 기준 상대 경로)
  dongs             행정동 경계 GeoJSON (vuski/admdongkor, CC BY 4.0 / 원자료 SGIS)
  lines_geojson     선로 중심선 GeoJSON (OpenStreetMap, ODbL)
  stations_geojson  역 위치 GeoJSON (OpenStreetMap, ODbL)

좌표: 기준점(origin_lonlat) 기준 미터, x=동쪽, y=남쪽. 축척은 서울과 같음(1도트 = 21.27 m = 4 px).
필요: pip install pillow numpy scipy  /  글꼴 Noto Sans CJK (라벨)
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

CFG_PATH = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "daegu.config.json"))
HERE = os.path.dirname(CFG_PATH)
ROOT = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.abspath(os.path.join(HERE, "..", ".."))
cfg = json.load(open(CFG_PATH, encoding="utf-8"))
OUT = os.path.join(ROOT, "assets", "map", cfg["region"])
PREVIEW = os.path.join(ROOT, "docs", "previews")          # 확인용 미리보기·라벨 목록(게임은 안 씀)
os.makedirs(PREVIEW, exist_ok=True)

LON0, LAT0 = cfg["origin_lonlat"]
KX = 111320 * math.cos(math.radians(LAT0))
KY = 110574
MPP, DOT = cfg["m_per_dot"], cfg["dot_px"]
SW, SH = cfg["screen_px"]
DW, DH = SW // DOT, SH // DOT          # 조각 하나 = 270×180 도트


def to_m(lonlat):
    return ((lonlat[0] - LON0) * KX, -(lonlat[1] - LAT0) * KY)


def r1(v):
    return round(v * 10) / 10


# ---------------- 입력 ----------------
def load(name):
    return json.load(open(os.path.join(HERE, cfg[name]), encoding="utf-8"))["features"]


line_feats = {f["properties"]["id"]: f for f in load("lines_geojson")}
station_feats = load("stations_geojson")
dong_feats = load("dongs")


def polys_of(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    return geom["coordinates"]


def chain_parts(P, gap_max=3000, dup=40):
    """여러 조각으로 끊긴 선로 → 끝점끼리 이어 한 줄(빈 곳은 직선). 이미 넣은 선로와 겹치는 조각(복선 등)은 버림."""
    P = sorted((p for p in P if len(p) >= 2), key=lambda p: -sum(math.dist(a, b) for a, b in zip(p, p[1:])))
    chain, rest = list(P[0]), P[1:]
    while rest:
        best = None
        for i, p in enumerate(rest):
            for pp in (p, p[::-1]):
                for at_end in (True, False):
                    g = math.dist(chain[-1], pp[0]) if at_end else math.dist(chain[0], pp[-1])
                    if best is None or g < best[0]:
                        best = (g, i, pp, at_end)
        g, i, pp, at_end = best
        rest.pop(i)
        if g > gap_max or min(math.dist(pp[len(pp) // 2], c) for c in chain) < dup:
            continue
        chain = chain + pp if at_end else pp + chain
    return chain


# 선로(미터) — 한 호선은 한 줄. 조각으로 끊겨 있으면 끝점끼리 잇는다(부산 2·3호선).
tracks = {}
for L in cfg["lines"]:
    g = line_feats[L["src"]]["geometry"]
    parts = g["coordinates"] if g["type"] == "MultiLineString" else [g["coordinates"]]
    tracks[L["id"]] = chain_parts([[to_m(p) for p in part] for part in parts])

# ---------------- 지도 범위 ----------------
xs = [p[0] for t in tracks.values() for p in t]
ys = [p[1] for t in tracks.values() for p in t]
M = cfg["margin_m"]
bx0, bx1, by0, by1 = min(xs) - M, max(xs) + M, min(ys) - M, max(ys) + M
TC = math.ceil((bx1 - bx0) / MPP / DW)
TR = math.ceil((by1 - by0) / MPP / DH)
cols, rows = TC * DW, TR * DH
x0 = (bx0 + bx1) / 2 - cols * MPP / 2
y0 = (by0 + by1) / 2 - rows * MPP / 2


def to_dot(p):
    return ((p[0] - x0) / MPP, (p[1] - y0) / MPP)


def to_px(p):
    q = to_dot(p)
    return [r1(q[0] * DOT), r1(q[1] * DOT)]


# ---------------- 1. 행정동 격자 ----------------
dongs = []
for f in dong_feats:
    p = f["properties"]
    parts = p["adm_nm"].split(" ")
    gu = p["sggnm"] if p["sidonm"] == "대구광역시" else parts[1]        # 경산시는 시 이름을 구 자리에
    dongs.append({"id": p["adm_cd2"], "name": parts[-1], "gu": gu,
                  "polys": [[[to_dot(to_m(c)) for c in ring] for ring in poly] for poly in polys_of(f["geometry"])]})

grid = np.full((rows, cols), -1, dtype=np.int16)
for i, d in enumerate(dongs):
    for poly in d["polys"]:
        ext = poly[0]
        ex = [q[0] for q in ext]
        ey = [q[1] for q in ext]
        c0, c1 = max(0, int(min(ex)) - 1), min(cols, int(max(ex)) + 2)
        rr0, rr1 = max(0, int(min(ey)) - 1), min(rows, int(max(ey)) + 2)
        if c0 >= c1 or rr0 >= rr1:
            continue
        im = Image.new("1", (c1 - c0, rr1 - rr0), 0)
        dr = ImageDraw.Draw(im)
        dr.polygon([(q[0] - c0 - .5, q[1] - rr0 - .5) for q in ext], fill=1)
        for hole in poly[1:]:
            dr.polygon([(q[0] - c0 - .5, q[1] - rr0 - .5) for q in hole], fill=0)
        mask = np.array(im, dtype=bool)
        grid[rr0:rr1, c0:c1][mask] = i

# 한 칸 틈 메우기
holes = 0
for _ in range(2):
    g = grid
    L_, R_ = np.roll(g, 1, 1), np.roll(g, -1, 1)
    U_, D_ = np.roll(g, 1, 0), np.roll(g, -1, 0)
    fill = (g == -1) & (L_ >= 0) & (L_ == R_)
    grid = np.where(fill, L_, grid)
    fill2 = (grid == -1) & (U_ >= 0) & (U_ == D_)
    grid = np.where(fill2, U_, grid)
    holes += int(fill.sum() + fill2.sum())

used = sorted(set(int(v) for v in np.unique(grid)) - {-1})

# 이웃 동 → 그리디 채색
adj = {i: set() for i in range(len(dongs))}
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
gu_grid = gu_of[grid]                      # grid == -1 → 마지막 원소(-1)


def hex2rgb(h):
    return [int(h[k:k + 2], 16) for k in (1, 3, 5)]


# ---------------- 2. 조각 그림 ----------------
land = grid >= 0
pal = np.array([hex2rgb(palette[color_of.get(i, 0)]) for i in range(len(dongs))] + [[0, 0, 0]], dtype=np.float32)
base = pal[grid]
dong_edge = np.zeros_like(land)
dong_edge[:, :-1] |= grid[:, :-1] != grid[:, 1:]
dong_edge[:-1, :] |= grid[:-1, :] != grid[1:, :]
base[dong_edge & land] *= .8
gpad = np.pad(gu_grid, 1, constant_values=-1)
gu_edge = land & ((gpad[1:-1, :-2] != gu_grid) | (gpad[1:-1, 2:] != gu_grid) | (gpad[:-2, 1:-1] != gu_grid) | (gpad[2:, 1:-1] != gu_grid))
base[gu_edge] = hex2rgb(cfg["gu_border_color"])
rgba = np.zeros((rows, cols, 4), dtype=np.uint8)
rgba[..., :3] = base.clip(0, 255).astype(np.uint8)
rgba[..., 3] = np.where(land, 255, 0)

lpad = np.pad(land, 1)
outer = land & ~(lpad[1:-1, :-2] & lpad[1:-1, 2:] & lpad[:-2, 1:-1] & lpad[2:, 1:-1])
plain = np.zeros_like(rgba)
plain[land] = [*cfg["plain_fill"], 255]
plain[outer] = [*cfg["plain_edge"], 255]

# ---------------- 3. 라벨 (add-district-labels.py 와 같은 규칙) ----------------
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc"


def font(weight, px):
    return ImageFont.truetype(FONT % weight, px, index=1)


GU_A, DONG_A, GU_DOTS = .40, .15, 15
INK = np.array([38, 54, 75], dtype=np.float32)
gu_mask = Image.new("L", (cols, rows), 0)
gd = ImageDraw.Draw(gu_mask)
f_gu = font("Bold", GU_DOTS)
gu_labels = []
for gi, gu in enumerate(gu_names):
    sel = gu_grid == gi
    yy, xx = np.nonzero(sel)
    # 지도에 보이는 부분이 큰 구만(가장자리에 살짝 걸친 구는 이름 생략)
    if len(xx) < 400:
        continue
    cx, cy = xx.mean(), yy.mean()
    if not sel[int(cy), int(cx)]:
        k = np.argmin((xx - cx) ** 2 + (yy - cy) ** 2)
        cx, cy = xx[k], yy[k]
    gu_labels.append({"name": gu, "dot": [int(cx), int(cy)], "map_px": [int(cx * DOT), int(cy * DOT)], "size_px": GU_DOTS * DOT, "alpha": GU_A})
    w = sum(f_gu.getlength(c) + 1 for c in gu) - 1
    x = cx - w / 2
    for c in gu:
        gd.text((x, cy), c, font=f_gu, fill=255, anchor="lm")
        x += f_gu.getlength(c) + 1
gu_big = np.kron(np.array(gu_mask) >= 110, np.ones((DOT, DOT), dtype=bool))


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
dong_mask = Image.new("L", (cols * DOT, rows * DOT), 0)
dd = ImageDraw.Draw(dong_mask)
dong_labels, tight = [], []
for i in used:
    m = grid == i
    yy, xx = np.nonzero(m)
    if len(xx) < 30:                       # 지도 가장자리에 아주 조금 걸친 동은 이름 생략
        continue
    ya, yb, xa, xb = yy.min(), yy.max() + 1, xx.min(), xx.max() + 1
    sub = np.pad(m[ya:yb, xa:xb], 1)
    edt = distance_transform_edt(sub)[1:-1, 1:-1]
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
            hit = None
            for (cx, cy) in cand:
                if cover(ii, int(round(cx - w / 2)), int(round(cy - h / 2)), int(round(cx + w / 2)), int(round(cy + h / 2))) >= .94:
                    hit = (cx, cy)
                    break
            if hit:
                best[li] = (px, hit, text)
                break
    if 0 in best and (1 not in best or best[0][0] >= best[1][0] * .85):
        px, (cx, cy), text = best[0]
    elif 1 in best:
        px, (cx, cy), text = best[1]
    else:
        text, px = layouts[-1], SIZES[-1]
        k = np.argmax(edt)
        cy, cx = divmod(k, edt.shape[1])
        tight.append(name)
    X, Y = (xa + cx + .5) * DOT, (ya + cy + .5) * DOT
    dd.multiline_text((X, Y), text, font=F(px), fill=255, anchor="mm", align="center", spacing=2)
    dong_labels.append({"name": name, "gu": dongs[i]["gu"], "map_px": [int(X), int(Y)], "size_px": px, "lines": text.split("\n"), "alpha": DONG_A})
dong_arr = np.array(dong_mask).astype(np.float32) / 255

# ---------------- 4. 호선·역 ----------------
def cumlen(pts):
    c = [0.0]
    for a, b in zip(pts, pts[1:]):
        c.append(c[-1] + math.dist(a, b))
    return c


def project(pts, cum, q):
    best = (1e18, 0.0)
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L2 = dx * dx + dy * dy or 1e-9
        t = max(0.0, min(1.0, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / L2))
        p = (a[0] + t * dx, a[1] + t * dy)
        d = math.dist(q, p)
        if d < best[0]:
            best = (d, cum[k] + t * math.sqrt(L2))
    return best


def point_at(pts, cum, s):
    for k in range(1, len(cum)):
        if cum[k] >= s:
            f = (s - cum[k - 1]) / max(cum[k] - cum[k - 1], 1e-9)
            a, b = pts[k - 1], pts[k]
            return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
    return pts[-1]


def cut(pts, cum, s0, s1):
    return [point_at(pts, cum, s0)] + [p for p, c in zip(pts, cum) if s0 < c < s1] + [point_at(pts, cum, s1)]


def simplify(pts, tol):
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


lines_out, st_pos, st_lines = [], {}, {}
report = []
for L in cfg["lines"]:
    pts = tracks[L["id"]]
    cum = cumlen(pts)
    sts = []
    for f in station_feats:
        if L["src"] not in f["properties"]["lines"]:
            continue
        name = f["properties"]["name_ko"]
        if name in cfg.get("exclude_stations", []):      # 승객이 타지 않는 정차점(차량기지 등)
            continue
        d, s = project(pts, cum, to_m(f["geometry"]["coordinates"]))
        assert d < cfg["max_snap_m"], f"{name}: 선로까지 {d:.0f} m"
        sts.append((s, name, d))
    sts.sort()
    names = [n for _, n, _ in sts]
    assert len(names) == len(set(names)), "같은 이름 역이 한 호선에 둘"
    s0, s1 = sts[0][0], sts[-1][0]
    line_pts = simplify(cut(pts, cum, s0, s1), cfg["simplify_m"])
    lcum = cumlen(line_pts)
    at = [s - s0 for s, _, _ in sts]
    edges = []
    for k in range(len(sts) - 1):
        a, b = sts[k], sts[k + 1]
        path = simplify(cut(pts, cum, a[0], b[0]), cfg["simplify_m"])
        edges.append({"from": a[1], "to": b[1], "length_m": r1(b[0] - a[0]), "estimated": False,
                      "paths_px": [[to_px(p) for p in path]]})
    for s, n, _ in sts:
        st_pos.setdefault(n, point_at(pts, cum, s))
        st_lines.setdefault(n, []).append(L["id"])
    lines_out.append({
        "id": L["id"], "name": L["name"], "color": L["color"], "enabled": True, "switches": {},
        "segments": [{"stations": names, "points_px": [to_px(p) for p in line_pts],
                      "paths_px": [e["paths_px"][0] for e in edges],
                      "station_at_m": [r1(a) for a in at], "length_m": r1(s1 - s0),
                      "closed": False, "edges": edges}],
    })
    report.append(f"{L['name']} {names[0]}→{names[-1]} {(s1 - s0) / 1000:.1f} km, 역 {len(names)}개, 최대 스냅 {max(d for _, _, d in sts):.0f} m")

stations_out = []
for n, p in st_pos.items():
    c, r = to_dot(p)
    di = int(grid[int(r), int(c)])
    assert di >= 0, n + " 지도 밖"
    stations_out.append({"name": n, "lines": st_lines[n], "transfer": len(st_lines[n]) > 1, "junction": False,
                         "map_px": to_px(p), "dong": dongs[di]["name"], "gu": dongs[di]["gu"],
                         "label_spot": {"badge": "left", "name": "up", "wrap": False}, "switch": []})

# ---------------- 5. 저장 ----------------
for sub in ("tiles", "tiles-labeled", "tiles-plain"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    for fn in os.listdir(os.path.join(OUT, sub)):
        os.remove(os.path.join(OUT, sub, fn))


def big(a):
    return a.repeat(DOT, 0).repeat(DOT, 1)


tiles_out = []
for tr in range(TR):
    for tc in range(TC):
        ys_, xs_ = slice(tr * DH, (tr + 1) * DH), slice(tc * DW, (tc + 1) * DW)
        if not land[ys_, xs_].any():
            continue
        fn = f"t{tc}_{tr}.png"
        t = big(rgba[ys_, xs_])
        Image.fromarray(t).save(os.path.join(OUT, "tiles", fn))
        Image.fromarray(big(plain[ys_, xs_])).save(os.path.join(OUT, "tiles-plain", fn))
        im = t.astype(np.float32)
        lnd = im[..., 3] > 0
        Ys, Xs = slice(tr * SH, (tr + 1) * SH), slice(tc * SW, (tc + 1) * SW)
        for a in (np.where(lnd, dong_arr[Ys, Xs] * DONG_A, 0), np.where(lnd & gu_big[Ys, Xs], GU_A, 0)):
            for ch in range(3):
                im[..., ch] = im[..., ch] * (1 - a) + INK[ch] * a
        Image.fromarray(im.astype(np.uint8)).save(os.path.join(OUT, "tiles-labeled", fn))
        tiles_out.append({"col": tc, "row": tr, "x": tc * SW, "y": tr * SH, "file": fn})

data = {
    "_source": "행정동 경계: vuski/admdongkor ver20261001 (CC BY 4.0, 원자료 통계청 SGIS). "
               "선로·역: © OpenStreetMap contributors (ODbL), plazalabs/kr-rail-map 정리본. "
               "구간 길이는 OSM 선로 중심선에서 계산한 값.",
    "region": cfg["region"], "name": cfg["name"],
    "screen_px": [SW, SH], "map_px": [cols * DOT, rows * DOT], "m_per_dot": MPP, "dot_px": DOT,
    "origin_lonlat": [LON0, LAT0], "origin_m": [x0, y0],
    "tiles": tiles_out, "lines": lines_out, "stations": stations_out,
}
json.dump(data, open(os.path.join(OUT, "data.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"districts": gu_labels, "dongs": dong_labels, "river": []},
          open(os.path.join(PREVIEW, f"map_{cfg['region']}_labels.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 확인용 미리보기(1/2 크기): 라벨 지도 + 선로 + 역
pv = Image.new("RGB", (cols * 2, rows * 2), (226, 232, 236))
for t in tiles_out:
    im = Image.open(os.path.join(OUT, "tiles-labeled", t["file"])).convert("RGBA").resize((SW // 2, SH // 2), Image.NEAREST)
    pv.paste(im, (t["x"] // 2, t["y"] // 2), im)
dr = ImageDraw.Draw(pv)
for l in lines_out:
    for e in l["segments"][0]["edges"]:
        dr.line([(p[0] / 2, p[1] / 2) for p in e["paths_px"][0]], fill=tuple(hex2rgb(l["color"])), width=6)
for s in stations_out:
    x, y = s["map_px"][0] / 2, s["map_px"][1] / 2
    r = 7 if s["transfer"] else 5
    dr.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255), outline=(20, 20, 20), width=2)
pv.save(os.path.join(PREVIEW, f"map_{cfg['region']}.png"))

print(f"맵 {cols * DOT}×{rows * DOT}px = 화면 {TC}×{TR}개, 조각 {len(tiles_out)}개, 도트 {cols}×{rows}, 틈 메움 {holes}칸")
print(f"동 {len(used)}개 표시, 구·시·군 {len(gu_names)}개({', '.join(gu_names)}), 동 이름 못 넣은 곳: {', '.join(tight) or '없음'}")
for r in report:
    print(r)
print("역", len(stations_out), "개, 환승", [s["name"] for s in stations_out if s["transfer"]])
