"""업로드된 호선 JSON(수도권 18개)을 Maps/data.json 의 lines/stations 로 변환한다.
사용: python build_lines.py <호선JSON 폴더> <dong 데이터 data.js> <Maps/data.json>
"""
import glob, json, math, os, sys
from collections import defaultdict

SRC, DONGJS, OUT = sys.argv[1:4]
ORDER = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "arex", "gyeongui", "gyeongchun", "suinbundang",
         "shinbundang", "sillim", "ui", "gimpo", "seohae"]
# 역 이름 정리: (호선 id, 원래 이름) -> 게임 내 이름
RENAME = {("4", "총신대입구"): "이수",                      # 4·7호선 환승역은 '이수'로 통일
          ("gyeongui", "신촌"): "신촌 경의중앙선"}          # 2호선 신촌과 별개 역
# 호선 색: 겹쳐도 구별되도록 공식 색을 조정(같은 계열은 명도·색상을 벌림)
COLORS = {"1": "#0052A4", "2": "#00A84D", "3": "#EF7C1C", "4": "#29B6F6", "5": "#8E44AD", "6": "#8B4513",
          "7": "#7F8C00", "8": "#E91E63", "9": "#B59A5B", "arex": "#00296B", "gyeongui": "#00C9A7",
          "gyeongchun": "#0B7A75", "suinbundang": "#FFD600", "shinbundang": "#E53935", "sillim": "#7C8CF8",
          "ui": "#B5CC18", "gimpo": "#AD8605", "seohae": "#8FC31F"}
# 단독 운행이 불가능하거나 실존하지 않는 노선: 데이터는 두되 지도에는 그리지 않는다
DISABLED = {"gimpo", "seohae"}

lines_in = {}
for f in glob.glob(os.path.join(SRC, "*.json")):
    d = json.load(open(f, encoding="utf-8"))
    lines_in[d["id"]] = d
assert set(lines_in) == set(ORDER), set(ORDER) ^ set(lines_in)

# ---- 행정동 조회 ----
t = open(DONGJS, encoding="utf-8").read()
D = json.loads(t[t.index("{"): t.rindex("}") + 1])
def inring(x, y, ring):
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c
def dong_at(x, y):
    for dn in D["dongs"]:
        for poly in dn["polys"]:
            if inring(x, y, poly[0]) and not any(inring(x, y, h) for h in poly[1:]):
                return dn["name"], dn["gu"]
    return "", ""

pos_px = defaultdict(list); pos_m = defaultdict(list); in_lines = defaultdict(list)
neigh = defaultdict(lambda: defaultdict(set))
out_lines = []
for lid in ORDER:
    d = lines_in[lid]
    segs = []
    for seg in d["segments"]:
        names = [RENAME.get((lid, n), n) for n in seg["stations"]]
        e = seg["edges"]
        if e:
            ppx = [e[0]["points_px"][0]] + [x["points_px"][-1] for x in e]
            pm = [e[0]["points"][0]] + [x["points"][-1] for x in e]
        else:
            ppx, pm = [seg["points_px"][0]], [seg["points"][0]]
        if len(ppx) != len(names):  # 서울 밖으로 나가는 간선만 있는 단일 역 노선
            assert len(names) == 1, (lid, len(ppx), len(names))
            ppx, pm = ppx[:1], pm[:1]
        for n, a, b in zip(names, ppx, pm):
            if not (lid in DISABLED and n in pos_px):  # 단독 운행 불가 노선의 좌표는 위치 계산에서 제외
                pos_px[n].append(a); pos_m[n].append(b)
            if lid not in in_lines[n]:
                in_lines[n].append(lid)
        core = names[:-1] if seg["closed"] and names[0] == names[-1] else names
        for i, n in enumerate(core):
            if seg["closed"]:
                neigh[lid][n] |= {core[i - 1], core[(i + 1) % len(core)]}
            else:
                if i: neigh[lid][n].add(core[i - 1])
                if i < len(core) - 1: neigh[lid][n].add(core[i + 1])
        segs.append({"stations": names, "points_px": seg["points_px"],
                     "paths_px": seg.get("visible_paths_px") or [seg["points_px"]],
                     "station_at_m": seg["station_at_m"], "length_m": seg["length_m"],
                     "closed": bool(seg["closed"])})
    out_lines.append({"id": lid, "name": d["name"], "color": COLORS[lid], "enabled": lid not in DISABLED, "segments": segs})

stations = []; worst = []
for n, ps in pos_px.items():
    cx = sum(p[0] for p in ps) / len(ps); cy = sum(p[1] for p in ps) / len(ps)
    mx = sum(p[0] for p in pos_m[n]) / len(ps); my = sum(p[1] for p in pos_m[n]) / len(ps)
    if len(ps) > 1: worst.append((max(math.dist(p, (cx, cy)) for p in ps), n))
    dong, gu = dong_at(mx, my)
    ls = [l for l in ORDER if l in in_lines[n]]
    junction = any(len(neigh[l][n]) > 2 for l in ls)
    stations.append({"name": n, "lines": ls, "transfer": len(ls) > 1, "junction": junction,
                     "map_px": [round(cx, 1), round(cy, 1)], "dong": dong, "gu": gu})
# 실제 좌표 평균이 강가·물 위에 놓이는 역은 육지 쪽으로 옮긴다 (map px, 1px≈5.3m)
NUDGE = {"한남": (-46, -42)}
for x in stations:
    if x["name"] in NUDGE:
        x["map_px"] = [round(x["map_px"][0] + NUDGE[x["name"]][0], 1), round(x["map_px"][1] + NUDGE[x["name"]][1], 1)]
worst.sort(reverse=True)
print("환승역 위치 편차(map px, 1px≈5.3m) 상위:", [(round(a), n) for a, n in worst[:6]])
print("역 수", len(stations), "환승", sum(s["transfer"] for s in stations), "분기", [s["name"] for s in stations if s["junction"]])
print("동 미판정:", [s["name"] for s in stations if not s["dong"]])

# ---- 2단계: 1호선부터 호선별로 역과 역을 잇는다 ----
# 1단계에서 모든 호선의 역을 세워 환승역 위치를 확정했다. 각 구간(edge)의 원래 곡선을
# 새 역 위치에 맞도록 호장 비율로 휘어(warp) 끝점이 항상 역 중심에 닿게 한다.
by_name = {x["name"]: x for x in stations}

def rdp(pts, eps):
    if len(pts) < 3: return pts
    (x1, y1), (x2, y2) = pts[0], pts[-1]
    L = math.dist(pts[0], pts[-1]) or 1e-9
    dmax, k = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs((x2 - x1) * (y1 - pts[i][1]) - (x1 - pts[i][0]) * (y2 - y1)) / L
        if d > dmax: dmax, k = d, i
    if dmax <= eps: return [pts[0], pts[-1]]
    return rdp(pts[:k + 1], eps)[:-1] + rdp(pts[k:], eps)

def chaikin(pts, it=3):
    for _ in range(it):
        if len(pts) < 3: break
        out = [pts[0]]
        for p, q in zip(pts, pts[1:]):
            out += [[.75 * p[0] + .25 * q[0], .75 * p[1] + .25 * q[1]], [.25 * p[0] + .75 * q[0], .25 * p[1] + .75 * q[1]]]
        out.append(pts[-1]); pts = out
    return pts

def smooth(path, eps=7.0):
    """실제 지형의 잔 굴곡을 걷어내고 부드러운 곡선으로(끝점은 고정)."""
    return [[round(x, 1), round(y, 1)] for x, y in chaikin(rdp([list(p) for p in path], eps))]

def offset(path, d, taper=0.22):
    """경로를 법선 방향으로 d 만큼 평행 이동. 양 끝은 0으로 줄여 역에서 다시 모이게 한다."""
    n = len(path)
    if n < 2 or d == 0: return path
    cum = [0.0]
    for p, q in zip(path, path[1:]): cum.append(cum[-1] + math.dist(p, q))
    tot = cum[-1] or 1.0
    out = []
    for i, p in enumerate(path):
        a, b = path[max(i - 1, 0)], path[min(i + 1, n - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]; l = math.hypot(tx, ty) or 1.0
        t = cum[i] / tot; w = min(1.0, min(t, 1 - t) / taper); w = w * w * (3 - 2 * w)
        out.append([round(p[0] - ty / l * d * w, 1), round(p[1] + tx / l * d * w, 1)])
    return out

def warp(path, a0, b0, A, B):
    """원래 끝점 a0,b0 → 새 끝점 A,B. 각 점의 호장 비율 t 로 이동량을 선형 보간."""
    cum = [0.0]
    for p, q in zip(path, path[1:]):
        cum.append(cum[-1] + math.dist(p, q))
    tot = cum[-1] or 1.0
    da = (A[0] - a0[0], A[1] - a0[1]); db = (B[0] - b0[0], B[1] - b0[1])
    out = []
    for p in path:
        # 점 p 가 원래 경로의 어디쯤인지(가장 가까운 꼭짓점 기준)
        k = min(range(len(cum)), key=lambda i: 0 if False else math.dist(p, path[i]))
        t = cum[k] / tot
        out.append([round(p[0] + da[0] * (1 - t) + db[0] * t, 1), round(p[1] + da[1] * (1 - t) + db[1] * t, 1)])
    return out

for lid in ORDER:  # 1호선부터 순서대로
    d = lines_in[lid]
    ol = next(l for l in out_lines if l["id"] == lid)
    for seg_in, seg_out in zip(d["segments"], ol["segments"]):
        names = [RENAME.get((lid, n), n) for n in seg_in["stations"]]
        edges, paths = [], []
        for i, e in enumerate(seg_in["edges"]):
            if i + 1 >= len(names): break
            na, nb = names[i], names[i + 1]
            A, B = by_name[na]["map_px"], by_name[nb]["map_px"]
            pts = e["points_px"]
            # 보이는 경로: 원래 edge 곡선의 점들 중 visible 에 속한 점을 같은 방식으로 이동
            vis = []
            for vp in e["visible_paths_px"]:
                cum = [0.0]
                for p, q in zip(pts, pts[1:]):
                    cum.append(cum[-1] + math.dist(p, q))
                tot = cum[-1] or 1.0
                da = (A[0] - pts[0][0], A[1] - pts[0][1]); db = (B[0] - pts[-1][0], B[1] - pts[-1][1])
                one = []
                for p in vp:
                    k = min(range(len(pts)), key=lambda j: math.dist(p, pts[j]))
                    t = cum[k] / tot
                    one.append([round(p[0] + da[0] * (1 - t) + db[0] * t, 1), round(p[1] + da[1] * (1 - t) + db[1] * t, 1)])
                vis.append(smooth(one))
            edges.append({"from": na, "to": nb, "length_m": e["length_m"], "estimated": e["estimated"], "paths_px": vis})
            paths.extend(vis)
        if edges:
            seg_out["edges"] = edges
            seg_out["paths_px"] = paths

# ---- 3단계: 혼잡 구간 정리 ----
# (a) 자기 노선이 아닌 다른 역 위로 지나가는 구간은 그 역을 비껴가게 밀어낸다(실제 선로를 그대로 따르지 않는다)
# (b) 같은 길을 함께 가는 구간(다른 호선끼리 겹침)은 나란히 열을 세워 평행하게 배치한다
GAP = 16.0        # 평행 선 사이 간격(map px). 화면 선 굵기(≈14px)보다 크게
CLEAR = 26.0      # 남의 역과의 최소 거리
# (0) 한 호선이 다른 호선의 역 여러 개를 건너뛰는 구간(공항철도 홍대입구→공덕 등)은 그 호선이 지나는 길을
#     그대로 따라가게 한다 → 두 호선이 한 줄로 나란히 달리고 엉키지 않는다.
st_lines = {x["name"]: set(x["lines"]) for x in stations}
def chain_path(oy, na, nb):
    for seg in oy["segments"]:
        if seg["closed"] or "edges" not in seg: continue
        nm = seg["stations"]
        if na in nm and nb in nm:
            i, j = nm.index(na), nm.index(nb)
            if abs(i - j) < 2: continue
            out = []
            ks = range(i, j) if i < j else range(i - 1, j - 1, -1)
            for k in ks:
                ed = seg["edges"][k]
                if len(ed["paths_px"]) != 1: return None
                p = ed["paths_px"][0] if i < j else ed["paths_px"][0][::-1]
                out += p if not out else p[1:]
            return out
    return None
followed = []
for lid in ORDER:
    ox = next(l for l in out_lines if l["id"] == lid)
    for seg in ox["segments"]:
        for e in seg.get("edges", []):
            if len(e["paths_px"]) != 1: continue
            for oy in out_lines:
                if oy["id"] == lid or not oy["enabled"]: continue
                cp = chain_path(oy, e["from"], e["to"])
                if cp:
                    e["paths_px"] = [smooth(cp, 2.0)]; e["follow"] = oy["id"]
                    followed.append((ox["name"], e["from"], e["to"], oy["name"])); break
print("경로 따라가기:", followed)

units = []        # (노선 순번, 노선 id, edge, 경로 번호)
for oi, lid in enumerate(ORDER):
    ol = next(l for l in out_lines if l["id"] == lid)
    for seg in ol["segments"]:
        for e in seg.get("edges", []):
            for pi in range(len(e["paths_px"])):
                units.append([oi, lid, e, pi])

def seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy)), t

def dense(path, step=4.0):
    out = [path[0]]
    for p, q in zip(path, path[1:]):
        n = max(1, int(math.dist(p, q) / step))
        out += [[p[0] + (q[0] - p[0]) * i / n, p[1] + (q[1] - p[1]) * i / n] for i in range(1, n + 1)]
    return out

all_st = [(x["name"], x["map_px"]) for x in stations]
def bowed_chord(path):
    """우회가 큰 구간은 두 역을 잇는 완만한 호(원 경로의 휜 방향만 반영)로 단순화."""
    A, B = path[0], path[-1]
    L = math.dist(A, B) or 1.0
    nx, ny = -(B[1] - A[1]) / L, (B[0] - A[0]) / L
    dev = sum((p[0] - A[0]) * nx + (p[1] - A[1]) * ny for p in path) / len(path)
    bow = max(-0.14 * L, min(0.14 * L, dev * 0.6))
    n = max(8, int(L / 10))
    return [[round(A[0] + (B[0] - A[0]) * t + nx * bow * 4 * t * (1 - t), 1),
             round(A[1] + (B[1] - A[1]) * t + ny * bow * 4 * t * (1 - t), 1)] for t in (i / n for i in range(n + 1))]

simplified = 0
for oi, lid, e, pi in units:  # 남의 역 근처를 크게 돌아가는 구간은 호로 단순화
    path = dense(e["paths_px"][pi])
    ln = sum(math.dist(p, q) for p, q in zip(path, path[1:])); ch = math.dist(path[0], path[-1])
    if ch < 1 or ln / ch < 1.25 or e.get("follow"): continue
    if any(nm not in (e["from"], e["to"]) and min(math.dist(p, sp) for p in path) < CLEAR * 1.6 for nm, sp in all_st):
        e["paths_px"][pi] = bowed_chord(path); simplified += 1
print("호로 단순화:", simplified)

for it in range(3):  # (a) 남의 역 비껴가기
    for oi, lid, e, pi in units:
        path = dense(e["paths_px"][pi]); 
        ends = (e["from"], e["to"])
        for nm, sp in all_st:
            if nm in ends or (e.get("follow") and e["follow"] in st_lines[nm]): continue
            d, k = min((math.dist(p, sp), i) for i, p in enumerate(path))
            if d >= CLEAR: continue
            push = CLEAR - d
            vx, vy = path[k][0] - sp[0], path[k][1] - sp[1]; l = math.hypot(vx, vy)
            if l < 1e-6:
                a2, b2 = path[max(k - 1, 0)], path[min(k + 1, len(path) - 1)]
                vx, vy = -(b2[1] - a2[1]), b2[0] - a2[0]; l = math.hypot(vx, vy) or 1.0
            vx, vy = vx / l, vy / l
            # 최근접점 주변 ±70px 구간을 부드럽게(코사인 창) 민다
            cum = 0.0; arc = [0.0]
            for p, q in zip(path, path[1:]): arc.append(arc[-1] + math.dist(p, q))
            W = 70.0
            path = [[p[0] + vx * push * (0.5 + 0.5 * math.cos(math.pi * min(1, abs(arc[i] - arc[k]) / W))) if abs(arc[i] - arc[k]) < W else p[0],
                     p[1] + vy * push * (0.5 + 0.5 * math.cos(math.pi * min(1, abs(arc[i] - arc[k]) / W))) if abs(arc[i] - arc[k]) < W else p[1]]
                    for i, p in enumerate(path)]
        e["paths_px"][pi] = smooth(path, 3.0)

# (b) 겹침 판정 → 슬롯 배정 → 평행 이동
samp = [dense(e["paths_px"][pi], 5.0) for oi, lid, e, pi in units]
def bbox(p): return (min(q[0] for q in p), min(q[1] for q in p), max(q[0] for q in p), max(q[1] for q in p))
bb = [bbox(p) for p in samp]
conf = defaultdict(set)
for i in range(len(units)):
    for j in range(i + 1, len(units)):
        if units[i][1] == units[j][1]: continue
        if units[i][2].get("follow") == units[j][1] or units[j][2].get("follow") == units[i][1]: continue  # 따라가는 쌍은 아래에서 직접 배치
        a, b = bb[i], bb[j]
        if a[2] + 12 < b[0] or b[2] + 12 < a[0] or a[3] + 12 < b[1] or b[3] + 12 < a[1]: continue
        for x, y in ((i, j), (j, i)):
            near = 0
            for p in samp[x]:
                if any(seg_dist(p, samp[y][k], samp[y][k + 1])[0] < 12 for k in range(0, len(samp[y]) - 1, 1)):
                    near += 1
            frac, length = near / len(samp[x]), near * 5.0
            if frac >= 0.35 and length >= 30:
                conf[i].add(j); conf[j].add(i)
slot = {}
for i in sorted(range(len(units)), key=lambda i: (units[i][0], i)):
    used = {slot[j] for j in conf[i] if j in slot}
    slot[i] = next(k for k in range(20) if k not in used)
moved = 0
for i, (oi, lid, e, pi) in enumerate(units):
    if not conf[i]: continue
    k = max([slot[i]] + [slot[j] for j in conf[i]]) + 1
    d = (slot[i] - (k - 1) / 2) * GAP
    p = e["paths_px"][pi]
    flip = (p[-1][0] - p[0][0], p[-1][1] - p[0][1]) < (0, 0)  # 방향과 무관하게 같은 쪽에 놓이도록 기준 방향 통일
    e["paths_px"][pi] = offset(p[::-1], d, 0.18)[::-1] if flip else offset(p, d, 0.18)
    moved += 1
# (c) 따라가는 호선: 길잡이 호선의 최종 경로를 한 칸(GAP) 위/옆에 평행하게 얹는다
for lid in ORDER:
    ox = next(l for l in out_lines if l["id"] == lid)
    for seg in ox["segments"]:
        for e in seg.get("edges", []):
            if not e.get("follow"): continue
            oy = next(l for l in out_lines if l["id"] == e["follow"])
            cp = chain_path(oy, e["from"], e["to"])
            if not cp: continue
            cp = smooth(cp, 2.0)
            flip = (cp[-1][0] - cp[0][0], cp[-1][1] - cp[0][1]) < (0, 0)
            e["paths_px"] = [offset(cp[::-1], -GAP, 0.12)[::-1] if flip else offset(cp, -GAP, 0.12)]
for l in out_lines:
    for seg in l["segments"]:
        if "edges" in seg:
            seg["paths_px"] = [p for e in seg["edges"] for p in e["paths_px"]]
print("겹침 정리:", moved, "개 구간 평행 분리 /", len(units))

# ---- 4단계: 역 이름 자리를 먼저 확보하고, 노선이 그 자리를 비껴가게 한다 ----
# 게임 화면(기준 배율 ZREF)에서 역 이름이 놓일 상자를 지도 좌표로 환산해 예약한다.
#  (1) 역마다 둘레 8곳 중 노선·다른 역·다른 이름과 가장 덜 겹치는 자리를 고른다(label_spot 으로 저장 → 게임이 우선 사용)
#  (2) 그래도 상자를 지나는 노선은, 같은 방향으로 달리는 노선 묶음 전체를 같은 만큼 옆으로 밀어(평행 간격 유지) 비껴가게 한다
ZREF = 0.9
MARGIN = 13.5     # 노선 중심선과 글자 상자 사이 최소 거리(흰 테두리 반폭 11.2 + 여유)
PIN = 34.0        # 역 중심에서 이 거리 안쪽은 밀지 않는다(역에 붙어 있어야 하므로)
en_lines = {l["id"] for l in out_lines if l["enabled"]}
def n_act(x): return sum(1 for l in x["lines"] if l in en_lines)
def text_w(s): return sum(16.5 if ord(c) >= 0x2E80 else 9.0 for c in s) * 1.04 + 4
def sym_R(x):  # 역 심볼 반지름(화면 px, ZREF 기준) — game_map.draw_label 과 같은 식
    k = ZREF; n = n_act(x); r = 11 * k
    return r + (3 + 1.2 * min(n - 2, 4)) * k if x["transfer"] and n > 1 else r
SPOTS_NAME = ["up", "down", "right", "left", "ur", "ul", "dr", "dl",
              "ua", "ub", "da", "db", "la", "lb", "ra", "rb", "up2", "down2", "left2", "right2"]
SPOTS_BADGE = ["down", "up", "right", "left", "dr", "dl", "ur", "ul"]
def spot_rect(x, spot, w, h):
    """화면 px 크기 (w,h) 상자를 spot 에 놓았을 때 지도 좌표 (cx,cy,hw,hh). game_map._place 와 같은 식."""
    gap = sym_R(x) + 5 * ZREF + 4; d = .8; g2 = gap + 10
    off = {"up": (0, -gap - h / 2), "down": (0, gap + h / 2), "right": (gap + w / 2, 0), "left": (-gap - w / 2, 0),
           "ur": (gap * d + w / 2, -gap * d - h / 2), "ul": (-gap * d - w / 2, -gap * d - h / 2),
           "dr": (gap * d + w / 2, gap * d + h / 2), "dl": (-gap * d - w / 2, gap * d + h / 2),
           "ua": (-.3 * w, -gap - h / 2), "ub": (.3 * w, -gap - h / 2), "da": (-.3 * w, gap + h / 2), "db": (.3 * w, gap + h / 2),
           "la": (-gap - w / 2, -.8 * h), "lb": (-gap - w / 2, .8 * h), "ra": (gap + w / 2, -.8 * h), "rb": (gap + w / 2, .8 * h),
           "up2": (0, -g2 - h / 2), "down2": (0, g2 + h / 2), "left2": (-g2 - w / 2, 0), "right2": (g2 + w / 2, 0)}[spot]
    return (x["map_px"][0] + off[0] / ZREF, x["map_px"][1] + off[1] / ZREF, w / 2 / ZREF, h / 2 / ZREF)

import numpy as np
vis_units = [u for u in units if u[1] in en_lines]
def flat_build():
    xs, ys, pid, lo, hi, af, at = [], [], [], [], [], [], []
    base = 0
    for i, u in enumerate(vis_units):
        p = dense(u[2]["paths_px"][u[3]], 4.0); n = len(p)
        a = np.concatenate([[0.0], np.cumsum([math.dist(q, r) for q, r in zip(p, p[1:])])])
        xs += [q[0] for q in p]; ys += [q[1] for q in p]; pid += [i] * n
        lo += [base + max(j - 2, 0) for j in range(n)]; hi += [base + min(j + 2, n - 1) for j in range(n)]
        af += list(a); at += list(a[-1] - a); base += n
    return (np.array(xs), np.array(ys), np.array(pid), np.array(lo), np.array(hi), np.array(af), np.array(at))
PX, PY, PID, LO, HI, AF, AT = flat_build()
SX = np.array([x["map_px"][0] for x in stations]); SY = np.array([x["map_px"][1] for x in stations])
SYMR = {x["name"]: sym_R(x) / ZREF for x in stations}
def tangents():
    tx, ty = PX[HI] - PX[LO], PY[HI] - PY[LO]; l = np.hypot(tx, ty); l[l == 0] = 1.0
    return tx / l, ty / l
def box_mask(rc, own, m=MARGIN, X=None, Y=None):
    X = PX if X is None else X; Y = PY if Y is None else Y
    mk = (np.abs(X - rc[0]) <= rc[2] + m) & (np.abs(Y - rc[1]) <= rc[3] + m)
    return mk & (np.hypot(X - own["map_px"][0], Y - own["map_px"][1]) >= SYMR[own["name"]] + 1)
def rect_hit(a, b, m=2.0): return abs(a[0] - b[0]) < a[2] + b[2] + m and abs(a[1] - b[1]) < a[3] + b[3] + m

vis_st = [x for x in stations if n_act(x) > 0]
reserved = []   # (rc, station, kind)
def choose(x, w, h, order, placed):
    best, bs, bspot = None, 1e9, None
    for i, sp in enumerate(order):
        rc = spot_rect(x, sp, w, h)
        sc = int(box_mask(rc, x).sum()) + i * (0.5 if i < 8 else 2.0)
        sc += 60 * sum(1 for o in vis_st if o is not x and abs(o["map_px"][0] - rc[0]) < rc[2] + SYMR[o["name"]] + 3 and abs(o["map_px"][1] - rc[1]) < rc[3] + SYMR[o["name"]] + 3)
        sc += 80 * sum(1 for p in placed if rect_hit(rc, p))
        if sc < bs: best, bs, bspot = rc, sc, sp
    return best, bspot
placed_all = []
def cand_cost(x, rc, i, placed):
    mk_ = box_mask(rc, x)
    sc = float(mk_.sum() + 2 * (mk_ & (np.minimum(AF, AT) < PIN * 2.2)).sum()) + i * (0.5 if i < 8 else 2.0)  # 역에 가까운 점은 밀 수 없으므로 3배
    sc += 60 * sum(1 for o in vis_st if o is not x and abs(o["map_px"][0] - rc[0]) < rc[2] + SYMR[o["name"]] + 3 and abs(o["map_px"][1] - rc[1]) < rc[3] + SYMR[o["name"]] + 3)
    sc += 80 * sum(1 for p in placed if rect_hit(rc, p))
    return sc
for x in sorted(vis_st, key=lambda x: (-n_act(x), x["name"])):
    n = n_act(x); ent = {}
    nw, nh = text_w(x["name"]), 16 * 1.25 + 4
    ncand = [(sp, spot_rect(x, sp, nw, nh), cand_cost(x, spot_rect(x, sp, nw, nh), i, placed_all), False) for i, sp in enumerate(SPOTS_NAME)]
    if len(x["name"]) >= 6:   # 긴 이름은 두 줄로 접은 후보도 낸다(폭이 절반)
        h2 = (len(x["name"]) + 1) // 2
        w2, h2px = text_w(x["name"][:h2]) if len(x["name"][:h2]) >= len(x["name"][h2:]) else text_w(x["name"][h2:]), 2 * 16 * 1.25 + 4
        ncand += [(sp, spot_rect(x, sp, w2, h2px), cand_cost(x, spot_rect(x, sp, w2, h2px), i, placed_all) + 3.0, True) for i, sp in enumerate(SPOTS_NAME)]
    if x["transfer"] and n > 1:   # 배지 줄과 이름을 함께 놓는다(배지가 이름 자리를 빼앗지 않도록 합산 최소를 고른다)
        br = max(6, round(8.5 * max(ZREF, 0.6)))
        bw, bh = n * (2 * br + 2), 2 * br + 4
        best = None
        for bi, bsp in enumerate(SPOTS_BADGE):
            brc = spot_rect(x, bsp, bw, bh); bc = cand_cost(x, brc, bi, placed_all)
            for nsp, nrc, nc, nwr in ncand:
                tot = bc * 0.4 + nc + 80 * rect_hit(brc, nrc, 2.0)
                if best is None or tot < best[0]: best = (tot, bsp, brc, nsp, nrc, nwr)
        _, bsp, brc, nsp, nrc, nwr = best
        ent["badge"] = bsp; placed_all.append(brc); reserved.append((brc, x, "badge"))
    else:
        nsp, nrc, _, nwr = min(ncand, key=lambda c: c[2])
    ent["name"] = nsp; ent["wrap"] = nwr; placed_all.append(nrc); reserved.append((nrc, x, "name"))
    x["label_spot"] = ent

def hits_all(kinds=("name",), X=None, Y=None):
    return sum(int(box_mask(rc, x, X=X, Y=Y).sum()) for rc, x, k in reserved if k in kinds)
h0 = hits_all()
print("이름 자리 예약:", len(reserved), "개 / 노선과 겹친 샘플(밀기 전):", h0)

def ang_ok(tx, ty, tau, deg=35):  # 방향 무시하고 tau 와 deg 이내
    return np.abs(tx * tau[0] + ty * tau[1]) >= math.cos(math.radians(deg))
def exit_t(qx, qy, rc, u, m=MARGIN):
    ts = []
    for ax, q, c, h in ((0, qx, rc[0], rc[2] + m), (1, qy, rc[1], rc[3] + m)):
        if abs(u[ax]) < 1e-9: continue
        ts.append(((h if u[ax] > 0 else -h) - (q - c)) / u[ax])
    return np.maximum(0.0, np.minimum(*ts) if len(ts) == 2 else ts[0])
def smoothstep(v): v = np.clip(v, 0, 1); return v * v * (3 - 2 * v)
TMAX = 30.0
moves = skipped = 0
def local_cost(X, Y, near):
    """near: 이 범위 안 예약 상자들의 (이름·배지) 겹침 샘플 수 + 남의 역에 너무 가까운 점 수"""
    c = 0
    for rc, x, k in near: c += int(box_mask(rc, x, X=X, Y=Y).sum()) * (1.0 if k == "name" else 0.6)
    return c
def push_rect(rc, x):
    global moves, skipped, PX, PY
    tx, ty = tangents()
    mem = np.nonzero(box_mask(rc, x))[0]
    if len(mem) == 0: return
    clusters = []
    for m_ in mem:
        t = (tx[m_], ty[m_])
        for cl in clusters:
            if abs(cl["t"][0] * t[0] + cl["t"][1] * t[1]) > math.cos(math.radians(32)): cl["m"].append(m_); break
        else: clusters.append({"t": t, "m": [m_]})
    for cl in clusters:
        ids = np.array(cl["m"]); ref = cl["t"]
        sg = np.sign(tx[ids] * ref[0] + ty[ids] * ref[1]); sg[sg == 0] = 1
        vx, vy = (tx[ids] * sg).sum(), (ty[ids] * sg).sum(); l = math.hypot(vx, vy) or 1.0
        tau = (vx / l, vy / l); nrm = (-tau[1], tau[0])
        best = None
        for sgn in (1, -1):
            u = (nrm[0] * sgn, nrm[1] * sgn)
            T = float(exit_t(PX[ids], PY[ids], rc, u).max()) + 1.0
            if T > TMAX: continue
            hs = abs(rc[2] * tau[0]) + abs(rc[3] * tau[1]) + MARGIN * 0.5
            hu = abs(rc[2] * u[0]) + abs(rc[3] * u[1]) + MARGIN
            Tp = max(45.0, 3 * T)
            a_all = (PX - rc[0]) * u[0] + (PY - rc[1]) * u[1]; s_all = (PX - rc[0]) * tau[0] + (PY - rc[1]) * tau[1]
            amin = a_all[ids].min() - 1; amax = a_all[ids].max() + 2.5 * GAP
            # 같은 묶음만 밀되, 가장자리에서 값이 끊기지 않도록 모든 조건을 연속 가중치로 만든다
            cosang = np.abs(tx * tau[0] + ty * tau[1])
            fa = smoothstep((cosang - math.cos(math.radians(62))) / (math.cos(math.radians(28)) - math.cos(math.radians(62))))
            fl = smoothstep((a_all - (amin - 7)) / 7.0) * smoothstep(((amax + 7) - a_all) / 7.0)
            w = np.where(np.abs(s_all) <= hs, 1.0, 0.5 * (1 + np.cos(np.pi * np.minimum(1, (np.abs(s_all) - hs) / Tp)))) * smoothstep(np.minimum(AF, AT) / PIN) * fa * fl
            w = np.where(np.abs(s_all) < hs + Tp, w, 0.0)
            NX, NY = PX + u[0] * T * w, PY + u[1] * T * w
            aff = w > 0
            cx, cy = rc[0], rc[1]
            near = [(r_, x_, k_) for r_, x_, k_ in reserved if abs(r_[0] - cx) < hs + Tp + 80 and abs(r_[1] - cy) < hs + Tp + 80]
            # 남의 역 근접 벌점(새로 생긴 것만)
            d0 = np.min(np.hypot(PX[aff][:, None] - SX[None], PY[aff][:, None] - SY[None]), axis=1) if aff.any() else np.array([])
            d1 = np.min(np.hypot(NX[aff][:, None] - SX[None], NY[aff][:, None] - SY[None]), axis=1) if aff.any() else np.array([])
            lim = CLEAR * 0.85
            pen = float(np.sum(np.maximum(0, np.maximum(0, lim - d1) - np.maximum(0, lim - d0)))) if aff.any() else 0.0
            c0 = local_cost(PX, PY, near); c1 = local_cost(NX, NY, near)
            sc = c1 + pen * 0.5 + T * 0.3
            if best is None or sc < best[0]: best = (sc, c0, NX, NY, T)
        if best is None: skipped += 1; continue
        sc, c0, NX, NY, T = best
        if sc < c0:   # 겹침이 줄어드는 경우에만 반영
            PX, PY = NX, NY; moves += 1
        else: skipped += 1
def write_back():
    global PX, PY, PID, LO, HI, AF, AT
    for i, (oi, lid, e, pi) in enumerate(vis_units):
        m_ = PID == i
        pts = [[float(a), float(b)] for a, b in zip(PX[m_], PY[m_])]
        pts[0] = list(e["paths_px"][pi][0]); pts[-1] = list(e["paths_px"][pi][-1])
        e["paths_px"][pi] = [[round(a, 1), round(b, 1)] for a, b in chaikin(rdp(pts, 1.6), 2)]
    PX, PY, PID, LO, HI, AF, AT = flat_build()
for it in range(3):
    for rc, x, kind in sorted(reserved, key=lambda r: (r[2] != "name", r[1]["name"])):
        push_rect(rc, x)
    write_back()
    print(f"  밀기 {it + 1}회차: 누적 {moves}건 반영 / {skipped}건 보류, 남은 겹침 {hits_all()}")
for l in out_lines:
    for seg in l["segments"]:
        if "edges" in seg: seg["paths_px"] = [p for e in seg["edges"] for p in e["paths_px"]]
print("이름 자리 비껴가기: 겹침", h0, "→", hits_all(), "(배지 겹침", hits_all(("badge",)), ")")

# ---- 갈림길(switchstation) 등록 ----
# N호선 위에서 어느 역에 들어왔을 때(prev) 앞으로 갈 수 있는 역이 2개 이상이면 그 역은 그 호선의 switchstation.
# 선택지는 직진에 가까운 순서로 정렬한다(플레이에서 기본 선택 = 맨 앞).
pxy = {x["name"]: x["map_px"] for x in stations}
def heading(a, b): return math.atan2(b[1] - a[1], b[0] - a[0])
def turn(prev, cur, nxt):
    d = heading(pxy[cur], pxy[nxt]) - heading(pxy[prev], pxy[cur])
    return abs((d + math.pi) % (2 * math.pi) - math.pi)
switch_of = defaultdict(list)
for l in out_lines:
    sw = {}
    if l["enabled"]:
        for n, nb in neigh[l["id"]].items():
            opts = {}
            for prev in sorted(nb):
                fwd = sorted(nb - {prev}, key=lambda x: turn(prev, n, x))
                if len(fwd) >= 2: opts[prev] = fwd
            if opts:
                sw[n] = opts; switch_of[n].append(l["id"])
    l["switches"] = sw
for x in stations:
    x["switch"] = switch_of.get(x["name"], [])
print("갈림길 역:", {l["name"]: {n: list(v.values())[0] for n, v in l["switches"].items()} for l in out_lines if l["switches"]})

data = json.load(open(OUT, encoding="utf-8"))
data["lines"], data["stations"] = out_lines, stations
json.dump(data, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("saved", OUT, os.path.getsize(OUT) // 1024, "KB")
