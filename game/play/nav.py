"""네비게이션 — 목적지까지 길을 기억하고, 서 있을 때마다 다음 할 일을 알려 준다.

pygame 을 쓰지 않는다(그리기는 render/hud.py, scenes/subway_play.py).
"""
from game.world.route import find_route


class Nav:
    def __init__(self, map_data, profile, dest):
        self.map = map_data
        self.profile = profile
        self.dest = dest
        self.path = None            # [(역, 호선), ...] 지금 위치 → 목적지
        self.key = None             # 마지막으로 경로를 찾은 (역, 호선, 직전 역)
        self.arrived = False
        self.fresh = False          # 이번 update 에서 경로를 새로 찾았으면 True
        self.need = []              # 가장 짧은 길에 있는데 아직 잠긴 호선 id 들(해금 필요)

    def allowed(self):
        return {l.id for l in self.map.available_lines() if self.profile.is_unlocked(l.id)}

    def update(self, s):
        """열차가 서 있을 때 위치가 바뀌었으면 경로를 다시 찾는다."""
        self.fresh = False
        if self.arrived or s.train.running:
            return
        key = (s.cur, s.line_id, s.prev)
        if key == self.key:
            return
        self.key = key
        if s.cur == self.dest:
            self.arrived, self.path = True, None
            return
        self.path = find_route(self.map, s.cur, s.line_id, self.dest, self.allowed() | {s.line_id}, s.prev)
        every = {l.id for l in self.map.available_lines()}                 # 잠김 무시하고 찾은 길
        full = find_route(self.map, s.cur, s.line_id, self.dest, every, s.prev) or []
        self.need = []
        for _, lid in full:
            if not self.profile.is_unlocked(lid) and lid not in self.need:
                self.need.append(lid)
        self.fresh = True

    def next_hop(self):
        """("go", 다음 역) / ("transfer", 호선 id) / None"""
        if not self.path or len(self.path) < 2:
            return None
        (a, la), (b, lb) = self.path[0], self.path[1]
        if a == b and la != lb:
            return ("transfer", lb)
        return ("go", b)

    def remaining(self):
        """남은 역 수(환승은 세지 않음)."""
        if not self.path:
            return 0
        return sum(1 for (a, _), (b, _) in zip(self.path, self.path[1:]) if a != b)

    def transfers(self):
        if not self.path:
            return 0
        return sum(1 for (a, _), (b, _) in zip(self.path, self.path[1:]) if a == b)

    def segments(self):
        """지도에 그릴 구간: [(호선, a, b), ...]"""
        if not self.path:
            return []
        return [(la, a, b) for (a, la), (b, lb) in zip(self.path, self.path[1:]) if a != b]
