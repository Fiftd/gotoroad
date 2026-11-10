"""Station — 최초 진입 여부, 역 이름, 방향(<-, ->)."""

class Station:
    RADIUS = 11

    def __init__(self, d):
        self.name = d["name"]
        self.line_id = d["lines"]
        self.transfer = d["transfer"]
        self.junction = d["junction"]
        self.switch = d.get("switch", [])
        self.x , self.y = d["map_px"]
        self.gu = d["gu"]
        self.dong = d["dong"]
        self.label_spot = d.get("label_spot", {})

        self.visited = False

        self.hover = False
        self.selected = False
        self.pulse = 0.0

    @property
    def pos(self):
        return self.x, self.y

    def hit(self, wx, wy, zoom):
        r = max(self.RADIUS + 4, 12/zoom)
        return (wx - self.x) ** 2 + (wy - self.y) ** 2 <= r * r

    def __repr__(self):
        return f"<Station {self.name} {self.line_id}>"
