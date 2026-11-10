import math
import random
import pygame 

T_ZOOM, T_CRACK, T_FALL, T_BACK = 0.25, 0.40, 0.85, 1.0
SIGN_SCALE = 2
LIFT = 70

class CrashFx:
    def __init__(self, app, station, line_id, impact=True, rng=random):
        self.app = app
        self.station = station                          # Station 객체(좌표용)
        self.impact = impact                            # 충격 효과 설정(번쩍·흔들림·파편)
        self.rng = rng
        self.t = 0.0
        sign = app.signs.for_station("lg", line_id, station.name)
        w, h = sign.get_width() * SIGN_SCALE, sign.get_height() * SIGN_SCALE
        self.sign = pygame.transform.scale(sign, (w, h))
        self.color = app.map.lines[line_id].color
        # 금: 위(0)에서 아래(h)까지 지그재그 점들. 가운데 x 근처에서 좌우로 흔들림
        cx, step = w // 2, 10
        self.crack = [(cx + rng.randint(-8, 8) if 0 < y < h else cx, y) for y in range(0, h + step, step)]
        self.crack[-1] = (self.crack[-1][0], h)
        self.left, self.right = self._split()           # 금을 경계로 자른 두 조각(이음매가 정확히 맞음)
        self.parts = []                                 # 파편 [x, y, vx, vy, 남은 시간, 색]

    # ---------- 준비 ----------
    def _piece(self, poly):
        piece = self.sign.copy()
        mask = pygame.Surface(piece.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255), poly)
        piece.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)   # 다각형 밖은 투명
        return piece

    def _split(self):
        w, h = self.sign.get_size()
        left = [(0, 0)] + self.crack + [(0, h)]
        right = [(w, 0)] + self.crack + [(w, h)]
        return self._piece(left), self._piece(right)
        # ---------- 진행 ----------
    @property
    def done(self):
        return self.t >= T_BACK

    @property
    def zooming(self):
        """장면이 카메라를 ×2.5 로 당겨야 하는 동안."""
        return self.t < T_FALL

    def update(self, dt):
        before = self.t
        self.t += dt
        if before < T_CRACK <= self.t and self.impact:             # 금이 끝까지 간 순간 파편
            w, h = self.sign.get_size()
            for _ in range(18):
                x, y = self.crack[self.rng.randrange(len(self.crack))]
                a = self.rng.uniform(0, math.tau)
                sp = self.rng.uniform(120, 360)
                col = self.rng.choice([(255, 255, 255), self.color, (40, 40, 44)])
                self.parts.append([x - w / 2, y - h / 2, math.cos(a) * sp, math.sin(a) * sp - 120,
                                   self.rng.uniform(0.3, 0.6), col])
        for p in self.parts:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[3] += 900 * dt                                       # 중력
            p[4] -= dt
        self.parts = [p for p in self.parts if p[4] > 0]

    def shake(self):
        """화면 흔들림(px). 금 갈 때 약하게, 번쩍일 때 세게."""
        if not self.impact:
            return 0, 0
        if T_ZOOM <= self.t < T_CRACK:
            a = 2
        elif T_CRACK <= self.t < T_CRACK + 0.25:
            a = 12 * (1 - (self.t - T_CRACK) / 0.25)
        else:
            return 0, 0
        return self.rng.uniform(-a, a), self.rng.uniform(-a, a)
        # ---------- 그리기 ----------
    def draw(self, screen, cam):
        sx, sy = cam.to_screen(self.station.x, self.station.y)
        cx, cy = sx, sy - LIFT                                     # 간판 중심
        w, h = self.sign.get_size()
        t = self.t
        if t < T_CRACK:                                            # ①② 하나로 붙은 간판
            k = min(1.0, t / T_ZOOM)
            grow = 1 + 0.15 * math.sin(k * math.pi)                # 살짝 튀어나왔다 자리 잡음
            sc = (0.5 + 0.5 * k) * grow
            img = self.sign if abs(sc - 1) < 0.01 else pygame.transform.scale(self.sign, (round(w * sc), round(h * sc)))
            jx = self.rng.uniform(-2, 2) if t >= T_ZOOM else 0     # ② 떨림
            r = img.get_rect(center=(round(cx + jx), round(cy)))
            screen.blit(img, r)
            if t >= T_ZOOM:                                        # ② 금이 가운데에서 위아래로 자람
                g = (t - T_ZOOM) / (T_CRACK - T_ZOOM)
                mid = h / 2
                pts = [(r.left + x, r.top + y) for x, y in self.crack if abs(y - mid) <= mid * g]
                if len(pts) >= 2:
                    pygame.draw.lines(screen, (255, 255, 255), False, pts, 5)
                    pygame.draw.lines(screen, (17, 17, 17), False, pts, 3)
        elif t < T_FALL:                                           # ④ 두 조각
            u = t - T_CRACK
            fade = max(0, round(255 * (1 - u / (T_FALL - T_CRACK))))
            for piece, sgn in ((self.left, -1), (self.right, 1)):
                dx = sgn * (160 * u)                               # 서로 반대로 벌어짐
                dy = -90 * u + 0.5 * 1400 * u * u                  # 살짝 튀었다가 떨어짐(중력)
                rot = pygame.transform.rotate(piece, -sgn * 70 * u)   # 바깥쪽으로 기울어짐
                rot.set_alpha(fade)
                screen.blit(rot, rot.get_rect(center=(round(cx + dx), round(cy + dy))))
        for x, y, _, _, life, col in self.parts:                   # 파편
            pygame.draw.rect(screen, col, (round(cx + x) - 3, round(cy + y) - 3, 6, 6))
        if self.impact and T_CRACK <= t < T_CRACK + 0.15:          # ③ 번쩍
            a = round(220 * (1 - (t - T_CRACK) / 0.15))
            flash = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            flash.fill((255, 255, 255, a))
            screen.blit(flash, (0, 0))