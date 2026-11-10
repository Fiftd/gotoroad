"""로비 배경 — assets 의 GIF 를 움직이는 배경으로 그리고, 위에 회색 필터를 덮는다.

GIF 는 600장(30초)이라 전부 메모리에 올리면 1 GB 가 넘는다 → Pillow 로 지금 필요한 한 장만 풀어 쓴다.
Pillow 가 없으면 첫 장만 멈춘 그림으로 보여 준다(설치: py -m pip install pillow).
장면이 바뀌어도 App 이 하나만 들고 있으므로 영상이 끊기지 않고 이어진다.
"""
import pygame

from game import config as C


class LobbyBg:
    def __init__(self, path=C.LOBBY_BG):
        self.im = None              # Pillow 이미지(움직이는 배경)
        self.still = None           # Pillow 가 없을 때 첫 장
        self.n, self.dur = 1, 50    # 장 수, 한 장 시간(ms)
        self.idx = -1               # 지금 풀어 둔 장 번호
        self.raw = None             # 풀어 둔 장(원본 크기)
        self.scaled = None          # (화면 크기, 장 번호, 늘린 그림)
        self._dim = {}              # {(화면 크기, 알파): 회색 필터}
        self.t0 = pygame.time.get_ticks()
        try:
            from PIL import Image
            self.im = Image.open(path)
            self.n = getattr(self.im, "n_frames", 1)
            self.dur = self.im.info.get("duration") or 50
        except ImportError:
            try:
                self.still = pygame.image.load(path).convert()
            except (pygame.error, OSError):
                pass
        except OSError:
            pass

    def frame(self):
        """시간에 맞는 장(원본 크기 Surface). 없으면 None."""
        if self.im is None:
            return self.still
        idx = (pygame.time.get_ticks() - self.t0) // self.dur % self.n
        if idx != self.idx:
            if idx < self.idx:                       # 한 바퀴 돌았으면 처음부터(GIF 는 앞으로만 풀기 쉬움)
                self.im.seek(0)
            self.im.seek(idx)
            rgb = self.im.convert("RGB")
            self.raw = pygame.image.frombuffer(rgb.tobytes(), rgb.size, "RGB")
            self.idx = idx
        return self.raw

    def draw(self, screen, dim):
        """화면을 꽉 채우게(비율 유지, 넘치는 쪽은 가운데 기준 잘림) 그리고 회색 필터(dim = 0~1)를 덮는다."""
        img = self.frame()
        size = screen.get_size()
        if img is None:
            screen.fill(C.LOBBY_FALLBACK)
        else:
            key = (size, self.idx)
            if not self.scaled or self.scaled[0] != key:
                k = max(size[0] / img.get_width(), size[1] / img.get_height())
                big = pygame.transform.scale(img, (round(img.get_width() * k), round(img.get_height() * k)))  # 픽셀 그림이라 nearest
                self.scaled = (key, big)
            big = self.scaled[1]
            screen.blit(big, big.get_rect(center=(size[0] // 2, size[1] // 2)))
        a = round(255 * dim)
        if a:
            f = self._dim.get((size, a))
            if f is None:
                f = self._dim[(size, a)] = pygame.Surface(size)
                f.fill(C.LOBBY_GRAY)
                f.set_alpha(a)
            screen.blit(f, (0, 0))
