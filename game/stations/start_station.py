"""StartStation(Station) — 플레이어가 시작하는 역."""

from game import config as C

def start_station(line_id, by_name):
    name = C.START_STATION.get(line_id)
    return by_name.get(name) if name else None