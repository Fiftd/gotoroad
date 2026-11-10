"""InterchangeStation(Station) — 환승역. 키 입력으로 다른 호선으로 갈아탐."""

def transfer_lines(station, lines):
    ids = [
        lid for lid in station.line_id if lid in lines and lines[lid].available
        ]
    return ids if len(ids) > 1 else []

