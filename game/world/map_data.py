"""지역 지도(assets/map/<지역>/data.json) 로드, 좌표 변환."""

import json
import os

from game import config as C
from game.world.line import Line
from game.world.track import build_track
from game.stations.station import Station

def _load_json (path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

class MapData:
    def __init__(self, path=C.MAP_DATA, types_path=C.LINE_TYPES):
        D = _load_json(path)
        self.dir = os.path.dirname(path)            # 지도 조각 폴더(tiles, tiles-labeled, tiles-plain)가 있는 곳

        self.w, self.h = D["map_px"]
        self.tile_w, self.tile_h = D["screen_px"]
        self.tiles = D["tiles"]
        self.overview = D.get("overview")          # 전체 축소 그림(큰 지도만)

        types = _load_json(types_path).get("lines", {})
        self.lines = {}
        for d in D["lines"]:
            t = types.get(d["id"], {}).get("type", "main")
            self.lines[d["id"]] = Line(d, t)

        self.stations = [Station(s) for s in D["stations"]]
        self.by_name = {s.name: s for s in self.stations}   
        self.positions = {s.name : s.pos for s in self.stations}
        self._tracks = {}

    def tracks(self, line_id):
        if line_id not in self._tracks:
            self._tracks[line_id] = build_track(self.lines[line_id], self.positions)
        return self._tracks[line_id]

    def available_lines(self):
        return [l for l in self.lines.values() if l.available]

    def lines_of(self, station):
        return [self.lines[l] for l in station.line_id if l in self.lines]

    def apply_visibility(self, hidden, keep=None):
        for l in self.lines.values():
            l.visible = l.available and (l.id not in hidden or l.id == keep)