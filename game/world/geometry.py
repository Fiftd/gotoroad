"""노선 모양 — 역과 역 사이 선로의 점 목록(맵 px). 그리기(map_renderer)와 열차 경로(track)가 같은 모양을 쓴다.

LINE_GEOMETRY
  "curved"   : 원래 선로 중심선(segment 의 points_px)을 역 위치(station_at_m)에서 잘라 쓴다. 곡선은 살리고 가공(불룩한 비킴)은 없음.
  "straight" : 역 ↔ 역 직선.
  "built"    : 원본 생성 도구가 가공한 edge 의 paths_px (역 근처에서 꺾임이 생김).
"""
import math

from game import config as C


def _cum(pts):
    cum = [0.0]
    for p, q in zip(pts, pts[1:]):
        cum.append(cum[-1] + math.dist(p, q))
    return cum


def _point_at(pts, cum, d):
    for i in range(1, len(cum)):
        if cum[i] >= d:
            seg = max(cum[i] - cum[i - 1], 1e-9)
            f = (d - cum[i - 1]) / seg
            p, q = pts[i - 1], pts[i]
            return (p[0] + (q[0] - p[0]) * f, p[1] + (q[1] - p[1]) * f)
    return tuple(pts[-1])


def _cut(pts, cum, d0, d1):
    """꺾은선에서 거리 d0 ~ d1(px) 부분만 잘라낸 점 목록."""
    out = [_point_at(pts, cum, d0)]
    out += [tuple(p) for p, c in zip(pts, cum) if d0 < c < d1]
    out.append(_point_at(pts, cum, d1))
    return out


def segment_edges(seg, positions):
    """한 segment 의 [(역a, 역b, 점 목록), ...] — 역 좌표에서 시작·끝나도록 양 끝을 맞춘다."""
    st = seg["stations"]
    out = []
    mode = C.LINE_GEOMETRY
    if mode == "built":
        for e in seg.get("edges", []):
            a, b = e["from"], e["to"]
            out.append((a, b, [positions[a]] + [tuple(p) for path in e["paths_px"] for p in path] + [positions[b]]))
        return out
    pts, at = seg.get("points_px") or [], seg.get("station_at_m") or []
    curved = mode == "curved" and len(pts) >= 2 and len(at) == len(st)
    if curved:
        cum = _cum(pts)
        scale = cum[-1] / (seg.get("length_m") or cum[-1] or 1.0)   # m → px
    for i in range(len(st) - 1):
        a, b = st[i], st[i + 1]
        if a == b:
            continue
        if curved:
            d0, d1 = at[i] * scale, at[i + 1] * scale
            if d1 <= d0:                                   # 순환선의 마지막 구간(끝 → 처음)
                d1 = cum[-1]
            p = _cut(pts, cum, d0, d1)
            p[0], p[-1] = positions[a], positions[b]        # 끝을 역 좌표에 맞춤(차이는 10px 이내)
        else:
            p = [positions[a], positions[b]]
        out.append((a, b, p))
    return out


def line_edges(line, positions):
    """호선의 {(역a, 역b): 점 목록} — 두 방향 모두(반대 방향은 점 순서를 뒤집음)."""
    out = {}
    for seg in line.segments:
        for a, b, p in segment_edges(seg, positions):
            out.setdefault((a, b), p)
            out.setdefault((b, a), p[::-1])
    return out


def offset_polyline(pts, shift):
    """화면 점 목록을 진행 방향의 왼쪽으로 shift 만큼 평행 이동(꼭짓점마다 앞뒤 방향의 평균 법선)."""
    if not shift or len(pts) < 2:
        return pts
    n = len(pts)
    out = []
    for i in range(n):
        p0 = pts[max(0, i - 1)]
        p1 = pts[min(n - 1, i + 1)]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        d = math.hypot(dx, dy) or 1.0
        out.append((pts[i][0] - dy / d * shift, pts[i][1] + dx / d * shift))
    return out
