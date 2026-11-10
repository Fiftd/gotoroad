from game.world.map_data import MapData
from game.save import Settings

m = MapData()
print(m.w, m.h, len(m.tiles), len(m.lines), len(m.stations))
print(len(m.available_lines()), [l.id for l in m.available_lines()][-3:])

from collections import Counter
print(Counter(l.type for l in m.lines.values()))

print(m.by_name["서울역"].pos == m.positions["서울역"])
print([l.name for l in m.lines_of(m.by_name["김포공항"])])

T = m.tracks("1")
print(len(T), m.tracks("1") is T, len(m._tracks))       # 두 번째 호출은 같은 객체, 저장된 호선 1개

m.apply_visibility({"1", "2"}, keep="1")
print(m.lines["1"].visible, m.lines["2"].visible, m.lines["gimpo"].visible)