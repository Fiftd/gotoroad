"""경로 찾기 — 지금 위치(역, 호선, 직전 역)에서 목적지까지 가장 짧은 길(다익스트라).

상태 = (역, 호선, 직전 역). 직전 역까지 기억해야 갈림길 규칙(switches)과
'왔던 길로 바로 못 돌아감'을 Session 과 똑같이 따를 수 있다.
  · 같은 호선 이웃 역으로: 비용 = 선로 길이(m)
  · 같은 역에서 다른 호선으로 환승: 비용 = NAV_TRANSFER_COST, 직전 역은 None
  · 종점(갈 곳 없음): 왔던 역으로 되돌아감(Session 과 같음)
"""
import heapq
from itertools import count

from game import config as C
from game.world.track import get_track


def _options(line, cur, prev):
    opts = line.next_option(cur, prev)
    if not opts and prev:
        opts = [prev]
    return opts


def find_route(map_data, cur, line_id, dest, allowed, prev=None):
    """[(역, 호선), ...] 을 돌려준다. 첫 칸은 지금 위치, 마지막 칸은 목적지. 못 가면 None.

    allowed: 탈 수 있는 호선 id 집합(해금 + 운행 중).
    """
    if cur == dest:
        return [(cur, line_id)]
    lines, by_name = map_data.lines, map_data.by_name
    start = (cur, line_id, prev)
    dist, back = {start: 0.0}, {start: None}
    tie = count()                                   # 비용이 같을 때 비교용 순번
    heap = [(0.0, next(tie), start)]
    while heap:
        d, _, node = heapq.heappop(heap)
        if d > dist.get(node, float("inf")):
            continue
        st, lid, pv = node
        if st == dest:
            path = []
            while node:
                path.append((node[0], node[1]))
                node = back[node]
            path.reverse()
            return path
        line = lines[lid]
        nxt = []
        tracks = map_data.tracks(lid)
        for n in _options(line, st, pv):
            t = get_track(tracks, map_data.positions, st, n)
            nxt.append(((n, lid, st), t.length_m))
        if pv is not None or node == start:          # 막 환승한 상태에서 또 환승하지 않음
            for other in by_name[st].line_id:
                if other != lid and other in allowed and other in lines:
                    nxt.append(((st, other, None), C.NAV_TRANSFER_COST))
        for nn, w in nxt:
            nd = d + w
            if nd < dist.get(nn, float("inf")):
                dist[nn], back[nn] = nd, node
                heapq.heappush(heap, (nd, next(tie), nn))
    return None
