"""Track — 선로 위 위치·거리 계산."""

import math
from game import config as C
from game.world.geometry import line_edges

class Track:
    def __init__(self, pts, length_m=None):
        self.pts = []
        for p in pts:
            p = (float(p[0]), float(p[1]))
            if not self.pts or math.dist(p, self.pts[-1]) > 1e-6:
                self.pts.append(p)
        if len(self.pts) < 2:
            self.pts.append(self.pts[0])

        self.cum = [0.0]
        
        for p, q in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.dist(p, q))
        
        self.plen = self.cum[-1] or 1.0
        self.length_m = length_m or self.plen * C.M_PER_PX

    def MovePos(self, s_m):
        t  = max(0.0, min(s_m / self.length_m, 1.0))
        d = t * self.plen
        for i in range(1, len(self.cum)):
            if self.cum[i] >= d:
                p, q = self.pts[i-1], self.pts[i]
                seg = max(self.cum[i] - self.cum[i-1], 1e-9)
                f = (d - self.cum[i-1]) / seg
                x = p[0] + (q[0] - p[0]) * f
                y = p[1] + (q[1] - p[1]) * f
                return x, y, math.atan2(q[1] - p[1], q[0] - p[0])
        p ,q = self.pts[-2], self.pts[-1]
        return q[0], q[1], math.atan2(q[1] - p[1], q[0] - p[0])

def build_track(line, positions):
    """호선의 {(역a, 역b): Track}. 모양은 geometry(LINE_GEOMETRY)가 정하고, 길이는 실제 length_m."""
    lengths = {}
    for seg in line.segments:
        for e in seg.get("edges", []):
            lengths[(e["from"], e["to"])] = lengths[(e["to"], e["from"])] = e["length_m"]
    return {key: Track(pts, lengths.get(key)) for key, pts in line_edges(line, positions).items()}

def get_track(tracks, positions, a, b):
    t = tracks.get((a, b))
    if t is None:
        t = tracks[(a,b)] = Track([positions[a], positions[b]])
    return t