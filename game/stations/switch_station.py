"""SwitchStation(Station) — 같은 호선 안의 분기점. 화살표로 방향 선택."""

def is_switch(station, line, prev=None):
    if prev is None:
        return False
    return len(line.next_option(station.name, prev)) > 1

def switch_lines(station, lines):
    return [
        lines[i] for i in station.switch if i in lines and lines[i].visible
    ]