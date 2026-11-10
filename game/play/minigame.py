"""이미 지난 역의 키 입력 미니게임."""

from game import config as C

class QWERgame:
    def __init__(self, rng):
        n = rng.randint(C.MINI_KEYS_MIN, C.MINI_KEYS_MAX)
        self.keys = rng.sample(C.TRANSFER_KEYS, n)
        self.idx = 0
        self.total = C.MINI_TIME_BASE +  C.MINI_TIME_PER_KEY *n
        self.left = self.total
        self.arm = C.MINI_ARM
        self.result = None
        self.result_left = 0.0
        self.paid = False

    @property
    def done(self):
        return self.result is not None and self.result_left <= 0

    def key(self, ch):
        if self.result is not None or self.arm > 0 or ch not in C.TRANSFER_KEYS:
            return
        if ch == self.keys[self.idx]:
            self.idx+=1
            if self.idx >= len(self.keys):
                self.finish(True)
        else:
            self.finish(False)

    def update(self, dt):
        if self.result is not None:
            self.result_left -= dt
        elif self.arm > 0:
            self.arm -= dt
        else:
            self.left -= dt
            if self.left <= 0:
                self.left = 0.0
                self.finish(False)

    def finish(self, ok):
        self.result = "ok" if ok else "miss"
        self.result_left = C.MINI_RESULT_TIME

        