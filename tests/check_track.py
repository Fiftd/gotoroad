import json, math
from game import config as C
from game.world.line import Line
from game.world.track import Track, build_track, get_track

D = json.load(open(C.MAP_DATA, encoding="utf-8"))
lines = {d["id"]: Line(d) for d in D["lines"]}
pos = {s["name"]: tuple(s["map_px"]) for s in D["stations"]}
deg = lambda r: round(math.degrees(r), 1)
show = lambda v: (round(v[0], 1), round(v[1], 1), deg(v[2]))

T = build_track(lines["1"], pos)
t = T[("서울역", "남영")]
print(len(T), len(t.pts), round(t.plen, 1), t.length_m)
print(show(t.MovePos(0)), show(t.MovePos(t.length_m / 2)), show(t.MovePos(t.length_m)))
print(show(t.MovePos(-5)), show(t.MovePos(99999)))                 # 범위 밖 → 끝점에 붙음
r = T[("남영", "서울역")]
print(show(r.MovePos(0)), show(r.MovePos(r.length_m)))              # 반대 방향
T2 = build_track(lines["2"], pos)
print(len(T2), ("충정로", "시청") in T2)                   # 순환선의 이음매 구간
print(len(build_track(lines["gimpo"], pos)))             # edges 없는 호선
print(get_track(T, pos, "서울역", "강남").length_m > 0)    # 없는 구간 → 직선