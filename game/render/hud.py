"""에너지 게이지, 속도, Point, 역 이름 강조, 환승·갈림길 안내."""

import math
import pygame

from game import config as C

PANEL = (18, 22, 32)
WHITE = (255, 255, 255)
SOFT = (200, 205, 215)
YELLOW = (255, 214, 90)
GREEN = (90, 220, 130)
ORANGE = (255, 190, 60)
RED = (255, 110, 100)
DIM = (90, 98, 115)
INK = (20, 24, 34)

class Hud:
    def __init__(self, app):
        self.app = app
        self.f16 = app.f_small
        self.f32 = app.f_button
        self.f48 = app.f_title

    def panel(self, screen, rect, alpha=180):
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(s, (*PANEL, alpha), s.get_rect(), border_radius=10)
        screen.blit(s, rect.topleft)

    def text(self, screen, msg, font, pos, color=WHITE, center=False, outline=False):
        img = font.render(msg, False, color)
        r = img.get_rect(center=pos) if center else img.get_rect(topleft=pos)
        if outline:
            if font is self.f16:
                bg = r.inflate(14, 6)
                self.panel(screen, bg, 200)
            else:
                halo = font.render(msg, False, INK)
                for dx, dy in ((-2, 0), (2,0), (0, -2), (0, 2)):
                    screen.blit(halo, r.move(dx,dy))
        screen.blit(img,r)
        return r

    def draw(self,screen, scene):
        s = scene.session
        sw, sh = screen.get_size()
        self.draw_status(screen, s)
        self.draw_recent(screen, s, sw)
        self.draw_nav(screen, scene, s, sw)
        if s.state =="mini" and s.mini:
            self.draw_mini(screen, s, sw, sh)
        else:
            ring = s.can_transfer
            if ring:
                self.draw_ring(screen, scene, s)
            if not s.train.running and s.state in ("idle", "charging", "pick") and s.opts:
                self.draw_choice(screen, s, sw, sh, below=ring)
            self.draw_charge(screen, s,sw,sh)
        self.draw_toasts(screen, scene, sw, sh)

    def draw_status(self, screen, s):
        line = s.line
        self.panel(screen, pygame.Rect(12, 12, 280, 150))
        pygame.draw.rect(screen, line.color, (26, 22, 12, 12), border_radius=3)     # 호선 색 표시
        self.text(screen, line.name, self.f16, (44, 20))
        speed = s.speed if s.train.running else 0.0                  # 서 있을 때는 0
        self.text(screen, f"{speed:5.1f}", self.f48, (22, 38))
        self.text(screen, "km/h", self.f16, (176, 66), SOFT)
        bar = pygame.Rect(26, 96, 252, 12)
        pygame.draw.rect(screen, (60, 66, 80), bar, border_radius=6)
        fill = bar.copy()
        fill.width = int(bar.width * min(1.0, s.E / C.CHARGE_MAX))      # 0~1000 J 만 바로 표시
        if fill.width:
            pygame.draw.rect(screen, GREEN, fill, border_radius=6)
        self.text(screen, f"에너지 {s.E:5.0f} J", self.f16, (26, 112), SOFT)
        self.text(screen, f"지나간 역 {len(s.visited)}", self.f16, (170, 112), SOFT)
        self.text(screen, f"Point {self.app.profile.points:,} P", self.f16, (26, 134), YELLOW)

    # ---------- 오른쪽 위: 최근 지나간 역 ----------
    def draw_recent(self, screen, s, sw):
        rec = s.visited[-6:][::-1]
        r = pygame.Rect(sw - 200, 12, 188, 34 + 20 * len(rec))
        self.panel(screen, r, 140)
        self.text(screen, "지나간 역", self.f16, (r.left + 12, r.top + 8), (170, 180, 200))
        for i, n in enumerate(rec):
            self.text(screen, ("● " if i == 0 else "· ") + n.split(" ")[0], self.f16,
                      (r.left + 12, r.top + 30 + 20 * i), WHITE if i == 0 else SOFT)

    # ---------- 위 가운데: 네비게이션 ----------
    def draw_nav(self, screen, scene, s, sw):
        hint = scene.nav_hint()
        if hint is None:
            return
        nav = scene.nav
        kind, val = hint
        dest = nav.dest.split(" ")[0]
        if kind == "go":
            msg, col = f"다음: {val.split(' ')[0]} 방향", WHITE
        elif kind == "transfer":
            ln = s.map.lines[val]
            key = C.TRANSFER_KEYS[s.tlines.index(val)].upper() if val in s.tlines and s.can_transfer else None
            msg, col = f"환승: {ln.name}" + (f"  ({key} 키)" if key else ""), ln.color
        else:
            msg, col = ("잠긴 호선 때문에 갈 수 없어요" if nav.need else "갈 수 있는 길이 없어요"), RED
        sub = f"남은 역 {nav.remaining()}  ·  환승 {nav.transfers()}번" if kind != "none" else ""
        w = max(self.f32.size(msg)[0], self.f16.size(f"목적지 {dest}")[0], self.f16.size(sub)[0]) + 40
        r = pygame.Rect(0, 12, max(300, w), 108 if sub else 84)
        r.centerx = sw // 2
        self.panel(screen, r, 190)
        pygame.draw.rect(screen, C.NAV_COLOR, r, 2, border_radius=10)
        self.text(screen, f"목적지 {dest}", self.f16, (r.centerx, r.top + 17), SOFT, center=True)
        self.text(screen, msg, self.f32, (r.centerx, r.top + 52), col, center=True, outline=True)
        if sub:
            self.text(screen, sub, self.f16, (r.centerx, r.top + 90), SOFT, center=True)
        if nav.need:
            self.draw_need(screen, s, nav.need, 12, 172)     # 왼쪽 상태 패널 바로 아래

    def draw_need(self, screen, s, need, left, top):
        """네비 패널 아래: 가장 짧은 길에 잠긴 호선이 있으면 '해금이 필요해요' + 호선 목록."""
        head = "해금이 필요해요"
        names = [s.map.lines[l].name for l in need]
        w = max([self.f16.size(head)[0]] + [self.f16.size(n)[0] + 30 for n in names]) + 40
        r = pygame.Rect(left, top, max(280, w), 38 + 22 * len(names))
        self.panel(screen, r, 210)
        pygame.draw.rect(screen, RED, r, 2, border_radius=10)
        self.text(screen, head, self.f16, (r.left + 14, r.top + 8), RED)
        for i, (lid, n) in enumerate(zip(need, names)):
            y = r.top + 32 + 22 * i
            x = r.left + 16
            pygame.draw.rect(screen, s.map.lines[lid].color, (x, y + 3, 12, 12), border_radius=3)
            self.text(screen, n, self.f16, (x + 22, y), WHITE)

    def draw_choice(self, screen, s, sw, sh, below=False):
        by = s.map.by_name
        cur = by[s.cur]
        items = [("<- " if by[n].x < cur.x else "-> ") + n.split(" ")[0] for n in s.opts]
        widths = [self.f32.size(t)[0] + 36 for t in items]
        total = sum(widths) + 16 * (len(widths) - 1)
        x = sw // 2 - total // 2
        y = sh - 160 if below else sh // 2 + 70          # 환승 링이 있으면 화면 아래쪽으로 비켜 놓음
        if s.state == "pick":
            sw_ = len(s.opts) > 1
            kind = "환승·갈림길!" if (sw_ and s.tlines) else ("갈림길!" if sw_ else "환승역!")
            head = f"{kind}  {max(0.0, s.timer):.1f}초  (SPACE 바로 출발)"
        elif len(s.opts) > 1:
            head = "방향 선택: 좌우 방향키"
        else:
            head = "진행 방향"
        self.text(screen, head, self.f16, (sw // 2, y - 16), WHITE, center=True, outline=True)
        for i, (t, w) in enumerate(zip(items, widths)):
            r = pygame.Rect(x, y, w, 44)
            sel = i == s.choice
            pygame.draw.rect(screen, INK, r, border_radius=10)
            pygame.draw.rect(screen, ORANGE if sel else DIM, r, 3, border_radius=10)
            self.text(screen, t, self.f32, r.center, WHITE if sel else (170, 176, 190), center=True)
            x += w + 16

    # ---------- 환승 링 ----------
    def draw_ring(self, screen, scene, s):
        """역 둘레(타원)에 Q W E … 칩(2.5배 크기). 지금 호선은 색을 채우고, 잠긴 호선은 흐리게."""
        st = s.map.by_name[s.cur]
        cx, cy = scene.cam.to_screen(st.x, st.y)
        n = len(s.tlines)
        hint = scene.nav_hint()
        rec = hint[1] if hint and hint[0] == "transfer" else None   # 네비가 추천하는 환승 호선
        rx, ry = 320, 190                                         # 칩이 커진 만큼 링도 넓힘
        chip_h, cap_s = 80, 60                                    # 칩 높이 32 → 80, 키캡 24 → 60 (2.5배)
        self.text(screen, "환승: 키를 눌러 호선 변경", self.f16, (cx, cy - ry - chip_h // 2 - 22), WHITE, center=True, outline=True)
        for i, lid in enumerate(s.tlines):
            ln = s.map.lines[lid]
            a = -math.pi / 2 + math.tau * i / n                       # 12시 방향부터 시계 방향
            px, py = cx + rx * math.cos(a), cy + ry * math.sin(a)
            cur = lid == s.line_id
            locked = not self.app.profile.is_unlocked(lid)
            label = ln.name + (" 잠김" if locked else "")
            r = pygame.Rect(0, 0, cap_s + 24 + self.f32.size(label)[0] + 20, chip_h)
            r.center = (round(px), round(py))
            pygame.draw.rect(screen, ln.color if cur else INK, r, border_radius=16)
            pygame.draw.rect(screen, DIM if locked else ln.color, r, 6, border_radius=16)
            if lid == rec:
                pygame.draw.rect(screen, C.NAV_COLOR, r.inflate(16, 16), 4, border_radius=22)   # 추천 칩
            cap = pygame.Rect(r.left + 10, r.top + (chip_h - cap_s) // 2, cap_s, cap_s)
            pygame.draw.rect(screen, (245, 245, 250), cap, border_radius=12)
            self.text(screen, C.TRANSFER_KEYS[i].upper(), self.f48, cap.center, INK, center=True)
            self.text(screen, label, self.f32, (cap.right + 14 + self.f32.size(label)[0] // 2, r.centery),
                      WHITE if cur else ((130, 136, 150) if locked else (225, 230, 240)), center=True)

    # ---------- 아래: 안내 + 충전 게이지 ----------
    def draw_charge(self, screen, s, sw, sh):
        W, H = 460, 24
        r = pygame.Rect(sw // 2 - W // 2, sh - 70, W, H)
        hint = {"idle": "SPACE 길게 눌러 충전, 떼면 출발",
                "charging": "충전 중... 떼면 출발!",
                "run": "달리는 중  (ESC: 나가기)"}.get(s.state, "")
        if hint:
            self.text(screen, hint, self.f16, (sw // 2, r.top - 18), WHITE, center=True, outline=True)
        if s.state not in ("idle", "charging"):
            return
        self.panel(screen, r.inflate(10, 10), 170)
        pygame.draw.rect(screen, (60, 66, 80), r, border_radius=8)
        c = s.charge if s.state == "charging" else 0.0
        fill = pygame.Rect(r.left, r.top, int(W * min(1.0, c / C.CHARGE_MAX)), H)
        if fill.width:
            pygame.draw.rect(screen, GREEN if c < C.CHARGE_MAX else ORANGE, fill, border_radius=8)
        if c >= C.CHARGE_MAX:                                         # MAX: 보너스 배율 표시
            self.text(screen, f"MAX  x{s.charge_mult:.2f}", self.f16, r.center, INK, center=True)

    # ---------- 미니게임 ----------
    def draw_mini(self, screen, s, sw, sh):
        """미니게임 패널 — 위에서부터 ① 역판(그 역 간판) ② 누를 키 ③ 프로그레스(남은 시간·결과)."""
        m = s.mini
        shade = pygame.Surface((sw, sh), pygame.SRCALPHA)
        shade.fill((10, 14, 24, 130))
        screen.blit(shade, (0, 0))

        sign = self.app.signs.for_station("lg", s.line_id, s.cur)      # ① 역판(환승역이면 삼태극 간판)
        size, gap = 88, 20                                             # ② 키 칸 크기·간격
        keys_w = len(m.keys) * size + (len(m.keys) - 1) * gap
        bar_h = 26                                                     # ③ 프로그레스 높이
        pad = 28
        sign_h = sign.get_height() if sign else 0
        p_w = max(560, keys_w + 2 * pad + 40, (sign.get_width() if sign else 0) + 2 * pad)
        p_h = pad + sign_h + 24 + size + 28 + bar_h + pad
        p = pygame.Rect(0, 0, p_w, p_h)
        p.center = (sw // 2, sh // 2)
        self.panel(screen, p, 235)

        y = p.top + pad
        if sign:                                                       # ① 역판
            screen.blit(sign, sign.get_rect(midtop=(p.centerx, y)))
            y += sign_h + 24

        x0 = p.centerx - keys_w // 2                                   # ② 키
        for i, k in enumerate(m.keys):
            r = pygame.Rect(x0 + i * (size + gap), y, size, size)
            done, now = i < m.idx, i == m.idx and m.result is None
            pygame.draw.rect(screen, GREEN if done else (WHITE if now else (70, 78, 96)), r, border_radius=14)
            pygame.draw.rect(screen, ORANGE if now else INK, r, 5 if now else 2, border_radius=14)
            self.text(screen, k.upper(), self.f48, r.center, WHITE if done else INK, center=True)
        y += size + 28

        bar = pygame.Rect(p.left + pad + 20, y, p.width - 2 * (pad + 20), bar_h)   # ③ 프로그레스
        pygame.draw.rect(screen, (52, 58, 74), bar, border_radius=8)
        frac = max(0.0, m.left / m.total)
        if m.result == "ok":
            fill_col, msg, msg_col = GREEN, f"성공!  +{int(C.STATION_BONUS_J)} J", INK
        elif m.result == "miss":
            fill_col, msg, msg_col = RED, ("실패..." if m.left > 0 else "시간 초과..."), WHITE
        else:
            fill_col, msg, msg_col = (ORANGE if frac > 0.3 else RED), f"{m.left:.1f}초", INK
        if m.result:
            frac = 1.0                                                 # 결과가 나오면 바 전체를 결과 색으로
        if frac > 0:
            pygame.draw.rect(screen, fill_col, (bar.left, bar.top, int(bar.width * frac), bar.height), border_radius=8)
        pygame.draw.rect(screen, WHITE, bar, 2, border_radius=8)
        self.text(screen, msg, self.f16, bar.center, msg_col, center=True)   # 남은 시간 또는 결과를 바 위에

    def draw_toasts(self, screen, scene, sw, sh):
        for i, (text, color, life) in enumerate(scene.toasts):
            y = sh // 2 - 150 - 36 * i - int((1.4 - life) * 30)          # 위로 떠오르며 사라짐
            self.text(screen, text, self.f32, (sw // 2, y), color, center=True, outline=True)
            