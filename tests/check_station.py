import json
from game import config as C
from game.world.line import Line
from game.stations.station import Station
from game.stations.interchange_station import transfer_lines
from game.stations.switch_station import is_switch, switch_lines
from game.stations.start_station import start_station

D = json.load(open(C.MAP_DATA, encoding="utf-8"))
lines = {d["id"]: Line(d) for d in D["lines"]}
stations = [Station(s) for s in D["stations"]]
by_name = {s.name: s for s in stations}

print(len(stations), sum(s.transfer for s in stations), by_name["서울역"], by_name["서울역"].pos)
s = by_name["서울역"]
print(s.hit(4280, 3100, 1.0), s.hit(4300, 3100, 1.0), s.hit(4295, 3099, 0.5))   # 반경 15 / 15 / 24
print(transfer_lines(s, lines), transfer_lines(by_name["김포공항"], lines), transfer_lines(by_name["남영"], lines))
print(is_switch(by_name["구로"], lines["1"], "신도림"), is_switch(by_name["구로"], lines["1"], "구일"),
      is_switch(s, lines["1"], "시청"), is_switch(s, lines["1"]))
print([l.id for l in switch_lines(by_name["구로"], lines)], switch_lines(s, lines))
print(start_station("1", by_name), start_station("2", by_name).name, start_station("gimpo", by_name))