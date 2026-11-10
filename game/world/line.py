"""Line — 호선(이름, 색, 구간, 역 순서)."""

SHORT = {"arex": "공", "gyeongui": "경", "gyeongchun": "춘", "suinbundang": "분",
         "shinbundang": "신", "sillim": "림", "ui": "우", "gimpo": "김", "seohae": "서",
         "incheon1": "인", "incheon2": "인", "bgl": "김"}

def hexToRGB(h):
    return tuple(int(h[i:i+2], 16) for i in (1, 3, 5))

class Line:
    def __init__(self, d, line_type="main"):
        self.id = d["id"]
        self.name = d["name"]
        self.color = hexToRGB(d["color"])
        self.available = d["enabled"]
        self.visible = self.available
        self.segments = d["segments"]
        self.switches = d.get("switches", {})
        self.type = line_type 
        self.short = SHORT.get(self.id, self.id)

    
    def neighbor_station(self, name):
        out = []
        for seg in self.segments:
            st = seg["stations"]
            closed = seg.get("closed") and len(st) > 2 and st[0] == st[-1]
            if closed:
                st = st[:-1]
            if name not in st:
                continue
            i = st.index(name)
            for j in (i-1, i+1):
                if closed:
                    j %= len(st)
                if 0 <= j < len(st) and st[j] not in out and st[j] != name:
                    out.append(st[j])
        return out

    def next_option(self, cur, prev=None):
        if prev is None:
            return self.neighbor_station(cur)
        sw = self.switches.get(cur, {}).get(prev)
        if sw:
            return list(sw)
        return [n for n in self.neighbor_station(cur) if n != prev]

    def is_switch(self, name):
        return name in self.switches

    def station_names(self):
        seen = [] 
        for seg in self.segments:
            for n in seg["stations"]:
                if n not in seen:
                    seen.append(n)
        return seen

    def has (self, name):
        return any(name in seg["stations"] for seg in self.segments)

    def __repr__(self):
        return f"<Line {self.id} {self.name} {self.type}>" 
        