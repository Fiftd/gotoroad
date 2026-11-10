"""열차 — 선로 위 이동, 역 도착 처리."""

class Train:
    def __init__(self):
        self.trk =None
        self.target=None
        self.pos = (0.0, 0.0)
        self.angle = 0.0

    @property
    def running(self):
        return self.trk is not None

    def place(self, x, y):
        self.trk, self.target, self.s = None, None, 0.0
        self.pos = (x, y)

    def depart(self, track, target):
        self.trk, self.target, self.s = track, target, 0.0
        x, y, self.angle = track.MovePos(0.0)
        self.pos = (x, y)

    def advance(self, meters):
        self.s+=meters
        x, y, self.angle = self.trk.MovePos(self.s)
        self.pos = (x, y)
        return self.s >= self.trk.length_m
    
