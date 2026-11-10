"""저장 — Profile(Point, 해금 호선)과 Settings(표시 설정) 읽기/쓰기.

파일이 없거나 깨져 있어도 기본값으로 시작하고, 저장에 실패해도 게임은 계속된다.
"""
import json

from game import config as C


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


class Profile:
    """Point 와 해금한 호선. 원본: S_StationPlay.py › Profile"""

    def __init__(self, path=C.SAVE_FILE):
        self.path = path
        self.points = 0
        self.unlocked = set(C.FREE_LINES)
        self.load()

    def load(self):
        if not self.path:
            return
        d = _read_json(self.path)
        try:
            self.points = max(0, int(d.get("points", 0)))
        except (TypeError, ValueError):
            self.points = 0
        if d.get("version") == C.SAVE_VERSION and isinstance(d.get("unlocked"), list):
            self.unlocked = {str(x) for x in d["unlocked"]} | set(C.FREE_LINES)
        # 버전이 다르면 Point 만 살리고 해금 목록은 무료 호선으로 되돌린다

    def save(self):
        if not self.path:
            return False
        return _write_json(self.path, {"version": C.SAVE_VERSION, "points": self.points,
                                       "unlocked": sorted(self.unlocked)})

    def add(self, n):
        self.points = max(0, self.points + int(n))
        self.save()

    def reset(self):
        """초기화: Point 0, 해금은 무료 호선만 남기고 저장."""
        self.points = 0
        self.unlocked = set(C.FREE_LINES)
        self.save()

    def is_unlocked(self, lid):
        return lid in self.unlocked

    def next_price(self):
        """다음 해금 가격: 1000, 2000, 3000 ... (무료가 아닌 해금 수에 따라 오른다)."""
        bought = len(self.unlocked - set(C.FREE_LINES))
        return C.UNLOCK_BASE_PRICE * (bought + 1)

    def can_afford(self):
        return self.points >= self.next_price()

    def buy(self, lid):
        """성공(또는 이미 해금)이면 True. Point 가 모자라면 아무것도 바꾸지 않고 False."""
        if lid in self.unlocked:
            return True
        price = self.next_price()
        if self.points < price:
            return False
        self.points -= price
        self.unlocked.add(lid)
        self.save()
        return True


class Settings:
    """표시 설정. 원본: main.py › App.load_settings / save_settings"""

    BOOL_KEYS = ("districts", "labels", "sound", "impact")
    DEFAULTS = {"districts": True, "labels": True, "sound": True, "impact": True}

    def __init__(self, path=C.SETTINGS_FILE):
        self.path = path
        self.values = dict(self.DEFAULTS)
        self.lines = {}          # {호선 id: 표시 여부}. 없는 키는 표시(True)
        self.load()

    def load(self):
        if not self.path:
            return
        d = _read_json(self.path)
        for k in self.BOOL_KEYS:
            if isinstance(d.get(k), bool):
                self.values[k] = d[k]
        if isinstance(d.get("lines"), dict):
            self.lines = {str(k): bool(v) for k, v in d["lines"].items()}

    def save(self):
        if not self.path:
            return False
        return _write_json(self.path, {**self.values, "lines": self.lines})

    # --- 읽기 ---
    def __getitem__(self, key):
        return self.values[key]

    @property
    def districts(self):
        return self.values["districts"]

    @property
    def labels(self):
        """지역 이름은 행정구역이 꺼져 있으면 자동으로 꺼진다."""
        return self.values["labels"] and self.values["districts"]

    def line_visible(self, lid):
        return self.lines.get(lid, True)

    def hidden_lines(self):
        return {k for k, v in self.lines.items() if not v}

    # --- 바꾸기(바로 저장) ---
    def toggle(self, key):
        self.values[key] = not self.values[key]
        self.save()
        return self.values[key]

    def toggle_line(self, lid):
        self.lines[lid] = not self.line_visible(lid)
        self.save()
        return self.lines[lid]
