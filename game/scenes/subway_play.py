"""지하철 플레이 장면 — Session(규칙) + ManRender(지도) + 열차 그리기 + 입력·카메라.

화면 위 정보는 render/hud.py, 첫 도착 크래시 연출은 render/crash.py.
"""
import math
import os

import pygame

from game import config as C
from game.play.session import Session
from game.render.camera import Camera
from game.render.map_renderer import ManRender
from game.render.hud import Hud
from game.render.crash import CrashFx
from game.play.nav import Nav
from game.scenes.base import Button
from game.world.track import get_track

LETTER_KEYS = set(C.TRANSFER_KEYS)          # q w e r a s d f


class SubwayPlay:
    music = "play"                              # 배경음악(로비 장면은 "lobby")
    def __init__(self, app, line_id, start=None, dest=None):
        self.app = app
        self.session = Session(app.map, line_id, app.profile, start=start)
        self.dest = dest if dest in app.map.by_name else None     # 도착역(없으면 None)
        self.nav = Nav(app.map, app.profile, self.dest) if self.dest and self.dest != self.session.start else None
        self.t_start = pygame.time.get_ticks()  # 시작 시각(ms). 걸린 시간은 실제 시계로 잰다(dt 합은 끊김 때 덜 셈)
        self.trip = [self.session.start]        # 실제로 지나온 역 순서(같은 역 다시 지나도 기록)
        self.arriving = None                    # 목적지에 막 도착: 크래시 연출이 끝나길 기다리는 결과
        self.result = None                      # 목적지 도착 결과 {dest, time, trip}. 있으면 도착 화면
        self.btn_retry = Button("다시하기", color=C.NAV_COLOR)
        self.btn_menu = Button("호선 선택")
        self.look = None                        # 맵 둘러보기 중이면 시작 시각(ms). 게임·UI 멈춤
        self.drag = None                        # 둘러보기 드래그 중 마지막 마우스 위치
        self.nav_sig = None                     # 마지막으로 추천 방향을 골라 준 (역, 호선, 직전 역, 선택지)
        app.map.apply_visibility(app.setting.hidden_lines(), keep=line_id)
        self.renderer = ManRender(app.map, app.setting, app.signs)
        self.hud =Hud(app)
        self.cam = Camera()
        self.base_zoom = C.ZOOM                 # 휠로 바꾸는 평소 배율
        self.trains = {}                        # {호선: 열차 원본 이미지}
        self._train_cache = {}                  # {(호선, 배율, 각도): 돌린 이미지}
        self.toasts = []                        # [[글, 색, 남은 시간], ...]
        screen = pygame.display.get_surface()
        st = app.map.by_name[self.session.start]
        self.cam.zoom = C.INTRO_ZOOM            # 호선 선택에서 이어지는 줌 아웃 연출
        self.cam.focus(st.x, st.y, screen.get_size())
        self.intro = 0.0
        self.crash = None
        self.draw_angle = 0.0                   # 화면에 그리는 열차 각도(실제 진행각을 부드럽게 따라감)
        self.spin = 0.0                         # 남은 '한 바퀴' 회전량(라디안). 환승·종점에서 2π 로 채움
        self.quake_t = 0.0                      # 미니게임 지진 시간
        self.quake_hit = 0.0                    # 미니게임 실패 흔들림 남은 시간

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            from game.scenes.line_select import LineSelect
            return self.app.go(LineSelect(self.app))
        if self.result:                                     # 도착 화면: 버튼 / Enter·R 다시하기
            if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                if self.btn_retry.rect.collidepoint(e.pos):
                    self.app.sound.play("start")
                    self.restart()
                elif self.btn_menu.rect.collidepoint(e.pos):
                    self.app.sound.play("button_click")
                    from game.scenes.line_select import LineSelect
                    self.app.go(LineSelect(self.app))
            elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_r):
                self.app.sound.play("start")
                self.restart()
            return
        if self.intro is not None:
            return                                          # 연출 중 입력 무시
        if self.look is not None:
            return self.handle_look(e)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            return self.start_look(e.pos)                   # 왼쪽 클릭: 맵 둘러보기
        s = self.session
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_SPACE:
                s.press_space()
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                if not s.train.running and s.state in ("idle", "pick") and len(s.opts) > 1:
                    self.app.sound.play("qwer_sound")         # 방향을 실제로 바꿀 수 있을 때만
                s.move_choice(-1 if e.key == pygame.K_LEFT else 1)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and s.state == "pick":
                s.leave()
            else:
                name = pygame.key.name(e.key)               # 한글 입력 상태여도 'q' 같은 키 이름이 나옴
                if name in LETTER_KEYS:
                    if s.state == "mini" or s.can_transfer:     # 미니게임·환승 입력을 받을 때만
                        self.app.sound.play("qwer_sound")
                    s.key(name)
        elif e.type == pygame.KEYUP and e.key == pygame.K_SPACE:
            s.release_space()
        elif e.type == pygame.MOUSEWHEEL:
            self.base_zoom = max(C.ZOOM_MIN, min(C.ZOOM_MAX, self.base_zoom * math.exp(e.y * 0.1)))

    # ---------- 맵 둘러보기 ----------
    def start_look(self, pos):
        """UI 를 숨기고 게임을 멈춘 채 지도를 자유롭게 본다(드래그 이동, 휠 확대·축소)."""
        s = self.session
        if s.state == "charging":                           # 충전 중이었으면 취소(출발하지 않음)
            s.state, s.charge, s.charge_mult = "idle", 0.0, 1.0
        s.space = False
        self.look = pygame.time.get_ticks()
        self.drag = pos

    def end_look(self):
        """SPACE: 원래 화면으로. 멈춰 있던 시간은 걸린 시간에서 뺀다. 카메라는 update 에서 열차로 부드럽게 돌아감."""
        self.t_start += pygame.time.get_ticks() - self.look
        self.look, self.drag = None, None

    def handle_look(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE:
            self.end_look()
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.drag = e.pos
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.drag = None
        elif e.type == pygame.MOUSEMOTION and self.drag:
            self.cam.pan(e.pos[0] - self.drag[0], e.pos[1] - self.drag[1])
            self.drag = e.pos
        elif e.type == pygame.MOUSEWHEEL:
            size = pygame.display.get_surface().get_size()
            lo = self.cam.fit_zoom(size, self.app.map.w, self.app.map.h)     # 최대 축소 = 서울 전경
            mx, my = pygame.mouse.get_pos()
            self.cam.zoom_at(math.exp(e.y * 0.15), mx, my, lo, C.LOOK_ZOOM_MAX)
            if self.cam.zoom <= lo + 1e-6:
                self.cam.fit(size, self.app.map.w, self.app.map.h)    # 끝까지 줄이면 전경을 가운데로

    def update(self, dt):
        size = pygame.display.get_surface().get_size()
        s = self.session
        if s.state == "charging" and self.look is None and not self.result:
            self.app.sound.loop("charging")                 # 충전 바 차는 동안 반복
        else:
            self.app.sound.stop("charging")
        if self.intro is not None:                          # 3.0 → 0.9 줌 아웃
            self.intro += dt
            t = min(1.0, self.intro / C.INTRO_TIME)
            k = 1 - (1 - t) ** 3
            self.cam.zoom = C.INTRO_ZOOM + (C.ZOOM - C.INTRO_ZOOM) * k
            self.cam.focus(*s.train.pos, size)
            if t >= 1.0:
                self.intro = None
            return
        if self.result or self.look is not None:
            return                                          # 도착 화면·둘러보기 중에는 멈춤
        if not self.arriving:                               # 도착 뒤에는 규칙을 멈추고 연출만 마저 진행
            s.update(dt)
            if s.cur != self.trip[-1]:
                self.trip.append(s.cur)
            self.take_events()
            self.update_nav()
        self.turn_train(dt)
        self.update_quake(dt)
        picking = s.state == "pick" and len(s.tlines) > 1
        target = C.TRANSFER_ZOOM if picking else self.base_zoom      # 환승역에 도착해 고르는 동안만 확대
        if self.crash:
            self.crash.update(dt)
            if self.crash.zooming:
                target = self.base_zoom * C.CRASH_ZOOM               # 크래시 클로즈업
            if self.crash.done:
                self.crash = None
        fast = 14.0 if self.crash else 6.0                          # 클로즈업은 빠르게
        self.cam.ease_zoom(target, dt, size, k=fast)
        self.cam.follow(*s.train.pos, dt, size, k=fast + 1)
        for t in self.toasts:                                       # 토스트 수명 줄이기(다 되면 지움)
            t[2] -= dt
        self.toasts = [t for t in self.toasts if t[2] > 0]
        if self.arriving and not self.crash:                       # 크래시 연출까지 끝나면 도착 화면
            self.result, self.arriving = self.arriving, None

    def take_events(self):
        """Session 이 남긴 신호를 화면 표시로 바꾼다(5-4 에서 흔들림·간판 등 추가)."""
        lines = self.app.map.lines
        for ev in self.session.events:
            kind = ev[0]
            if kind == "point":                              # 역 도착(지나감)마다 생김
                self.toast(f"+{ev[1]} P", (255, 214, 90))
                self.app.sound.play("jump")
            elif kind == "crash":
                self.app.sound.play("crash")
                self.crash = CrashFx(self.app, self.app.map.by_name[ev[1]], self.session.line_id,
                                     impact=self.app.setting["impact"])
            elif kind == "mini":
                self.toast(f"+{int(C.STATION_BONUS_J)} J" if ev[1] else "MISS",
                           (120, 230, 150) if ev[1] else (255, 120, 120))
                if not ev[1]:
                    self.quake_hit = C.QUAKE_MISS_TIME          # 실패: 한 번 크게 흔들림
                    self.app.sound.play("fail")
            elif kind == "transfer":
                self.app.map.apply_visibility(self.app.setting.hidden_lines(), keep=ev[1])
                self.toast(f"환승: {lines[ev[1]].name}", lines[ev[1]].color)
                self.spin = math.tau                             # 제자리 한 바퀴
            elif kind == "terminal":
                self.toast("종점! 되돌아갑니다", (200, 210, 230))
                self.spin = math.tau
            elif kind == "locked":
                self.toast(f"잠긴 호선: {lines[ev[1]].name}", (255, 150, 140))
            elif kind == "riding":
                self.toast(f"{lines[ev[1]].name} 탑승 중", (200, 210, 230))
            elif kind == "burnout":
                self.toast("에너지 소진! 시작역으로", (255, 120, 110))
                self.trip = [self.session.start]            # 새 시도: 지나온 역만 처음부터(시간은 계속 셈)
        self.session.events.clear()                         # 처리한 신호는 비움

    def update_nav(self):
        """경로를 갱신하고, 서 있는 역의 선택지가 새로 생기면 경로 쪽 방향을 미리 골라 둔다."""
        nav, s = self.nav, self.session
        if not nav:
            return
        nav.update(s)
        if nav.fresh and not nav.path and not nav.arrived:
            self.app.sound.play("error")                    # 갈 수 있는 길이 없음(새로 찾았을 때 한 번)
        if nav.arrived:
            self.arriving = {"dest": nav.dest, "time": (pygame.time.get_ticks() - self.t_start) / 1000, "trip": list(self.trip)}
            s.state, s.mini = "arrived", None               # 미니게임·선택 안내를 끄고 세션은 멈춤
            self.nav = None
            return
        if s.train.running or s.state not in ("idle", "pick"):
            return
        sig = (s.cur, s.line_id, s.prev, tuple(s.opts))
        if sig == self.nav_sig:
            return                                      # 같은 자리에서는 한 번만(그 뒤엔 플레이어 선택 존중)
        self.nav_sig = sig
        hop = nav.next_hop()
        if hop and hop[0] == "go" and hop[1] in s.opts:
            s.choice = s.opts.index(hop[1])

    def nav_hint(self):
        """HUD 용: (종류, 값). 종류 = "go" / "transfer" / "none"(길 없음). 네비 없으면 None."""
        if not self.nav:
            return None
        hop = self.nav.next_hop()
        return hop if hop else ("none", None)

    def turn_train(self, dt):
        """그리는 각도를 '지금 볼 방향'으로 부드럽게 돌리고, 한 바퀴 회전이 남았으면 더 돌린다."""
        s = self.session
        if s.train.running or not s.opts:
            target = s.train.angle                                   # 달리는 중: 선로 방향
        else:                                                        # 서 있을 때: 고른 다음 역 쪽
            a, b = s.map.by_name[s.cur], s.map.by_name[s.opts[s.choice]]
            target = math.atan2(b.y - a.y, b.x - a.x)
        diff = (target - self.draw_angle + math.pi) % math.tau - math.pi   # 가까운 쪽으로(-π ~ π)
        self.draw_angle += diff * (1 - math.exp(-C.TURN_SPEED * dt))
        if self.spin > 0:                                            # 환승·종점: 한 바퀴
            step = min(self.spin, math.tau / C.SPIN_TIME * dt)
            self.spin -= step
            self.draw_angle += step

    def update_quake(self, dt):
        if self.session.state == "mini":
            self.quake_t += dt
        self.quake_hit = max(0.0, self.quake_hit - dt)

    def quake_offset(self):
        """미니게임 중 약한 지진 + 실패 순간 큰 흔들림(px). 충격 효과가 꺼져 있으면 없음."""
        if not self.app.setting["impact"]:
            return 0.0, 0.0
        dx = dy = 0.0
        if self.session.state == "mini":
            t = self.quake_t
            dx += math.sin(t * 41) * C.QUAKE_AMP                     # 서로 다른 빠르기의 sin 두 개 → 불규칙해 보임
            dy += math.cos(t * 33) * C.QUAKE_AMP * 0.8
        if self.quake_hit > 0:
            a = C.QUAKE_MISS_AMP * self.quake_hit / C.QUAKE_MISS_TIME
            dx += math.sin(self.quake_hit * 90) * a
            dy += math.cos(self.quake_hit * 70) * a
        return dx, dy

    def toast(self, text, color, life=1.4):
        self.toasts.append([text, color, life])

    def draw(self, screen):
        s = self.session
        if self.look is not None:                                    # 둘러보기: 지도·경로·열차만
            self.renderer.draw(screen, self.cam, focus=s.line_id, start=s.start)
            self.draw_route(screen)
            self.draw_train(screen)
            self.hud.text(screen, "드래그: 이동  휠: 확대·축소  SPACE: 돌아가기", self.app.f_small,
                          (screen.get_width() // 2, screen.get_height() - 24), center=True, outline=True)
            return
        dx, dy = self.crash.shake() if self.crash else (0, 0)       # 크래시 흔들림: 지도·열차만 잠깐 밀어 그림
        qx, qy = self.quake_offset()                                 # 미니게임 지진
        dx, dy = dx + qx, dy + qy
        self.cam.ox += dx; self.cam.oy += dy
        self.renderer.draw(screen, self.cam, focus=s.line_id, start=s.start)
        self.draw_route(screen)
        self.draw_train(screen)
        self.cam.ox -= dx; self.cam.oy -= dy
        self.draw_intro_sign(screen)
        if self.crash:
            self.crash.draw(screen, self.cam)
        self.hud.draw(screen, self)
        if self.result:
            self.draw_result(screen)

    def draw_route(self, screen):
        """네비 경로를 반투명 노란 띠로, 목적지에 핀을 그린다."""
        if not self.nav:
            return
        m, cam = self.app.map, self.cam
        segs = self.nav.segments()
        if segs:
            layer = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            w = max(6, round(16 * cam.zoom))
            col = (*C.NAV_COLOR, 255)
            for lid, a, b in segs:
                t = get_track(m.tracks(lid), m.positions, a, b)
                pts = [cam.to_screen(x, y) for x, y in t.pts]
                pygame.draw.lines(layer, col, False, pts, w)
                for p in pts:                                   # 꺾이는 곳 이음새 메우기
                    pygame.draw.circle(layer, col, p, w // 2)
            layer.set_alpha(C.NAV_ALPHA)
            screen.blit(layer, (0, 0))
        st = m.by_name[self.nav.dest]
        x, y = cam.to_screen(st.x, st.y)
        x, y = round(x), round(y)
        pygame.draw.polygon(screen, (20, 24, 34), [(x - 11, y - 30), (x + 11, y - 30), (x, y - 2)])
        pygame.draw.polygon(screen, C.NAV_COLOR, [(x - 8, y - 30), (x + 8, y - 30), (x, y - 6)])
        pygame.draw.circle(screen, (20, 24, 34), (x, y - 34), 14)
        pygame.draw.circle(screen, C.NAV_COLOR, (x, y - 34), 11)
        pygame.draw.circle(screen, (20, 24, 34), (x, y - 34), 4)

    def restart(self):
        """같은 호선·출발역·도착역으로 처음부터."""
        s = self.session
        self.app.go(SubwayPlay(self.app, s.home_line_id, start=s.start, dest=self.dest))

    def draw_result(self, screen):
        """도착 화면: '도착', 걸린 시간, 지나온 역, 다시하기 / 호선 선택 버튼."""
        sw, sh = screen.get_size()
        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((10, 12, 18, 170))
        screen.blit(dim, (0, 0))
        f16, f32, f48 = self.app.f_small, self.app.f_button, self.app.f_title
        R = self.result
        W = 720
        names = [n.split(" ")[0] for n in R["trip"]]
        rows = self.wrap(" > ".join(names), f16, W - 60, 8)
        H = 300 + 22 * len(rows)
        box = pygame.Rect(0, 0, W, H)
        box.center = (sw // 2, sh // 2)
        pygame.draw.rect(screen, (18, 22, 32), box, border_radius=16)
        pygame.draw.rect(screen, C.NAV_COLOR, box, 4, border_radius=16)

        def put(msg, font, y, color=(255, 255, 255)):
            img = font.render(msg, False, color)
            screen.blit(img, img.get_rect(center=(box.centerx, y)))

        t = int(R["time"])                             # 실제로 흐른 초(정수)
        put("도착", f48, box.top + 44, C.NAV_COLOR)
        put(R["dest"].split(" ")[0], f32, box.top + 96)
        put(f"{t // 60}분 {t % 60:02d}초", f16, box.top + 136, (200, 205, 215))
        put(f"지나온 역 {len(names) - 1}개", f16, box.top + 164, (200, 205, 215))
        y = box.top + 192
        for row in rows:
            img = f16.render(row, False, (235, 238, 245))
            screen.blit(img, (box.left + 30, y))
            y += 22
        bw, bh = 220, 60
        self.btn_retry.rect = pygame.Rect(box.centerx - bw - 10, box.bottom - bh - 24, bw, bh)
        self.btn_menu.rect = pygame.Rect(box.centerx + 10, box.bottom - bh - 24, bw, bh)
        mp = pygame.mouse.get_pos()
        for b in (self.btn_retry, self.btn_menu):
            b.draw(screen, f32, f16, b.rect.collidepoint(mp))

    @staticmethod
    def wrap(text, font, width, max_rows):
        """폭에 맞춰 줄바꿈(" > " 단위). 줄이 넘치면 앞쪽을 '...' 로 줄인다."""
        rows, cur = [], ""
        for part in text.split(" > "):
            cand = part if not cur else cur + " > " + part
            if font.size(cand)[0] <= width or not cur:
                cur = cand
            else:
                rows.append(cur + " >")
                cur = part
        if cur:
            rows.append(cur)
        if len(rows) > max_rows:
            rows = ["..."] + rows[-(max_rows - 1):]
        return rows

    def train_image(self, lid):
        if lid not in self.trains:
            self.trains[lid] = pygame.image.load(os.path.join(C.TRAIN_SPRITES, f"{lid}.png")).convert_alpha()
        return self.trains[lid]

    def draw_train(self, screen):
        s = self.session
        sc = round(max(0.6, min(1.5, self.cam.zoom * 1.1)), 1)     # 배율은 0.1 단위
        deg = round(-math.degrees(self.draw_angle) / 3) * 3         # 그리는 각도(부드럽게 도는 각도), 3° 단위
        key = (s.line_id, sc, deg)
        img = self._train_cache.get(key)
        if img is None:
            base = self.train_image(s.line_id)
            big = pygame.transform.scale(base, (round(base.get_width() * sc), round(base.get_height() * sc)))
            img = self._train_cache[key] = pygame.transform.rotate(big, deg)   # 먼저 키우고(nearest) 돌린다
            if len(self._train_cache) > 300:
                self._train_cache.clear()
        x, y = self.cam.to_screen(*s.train.pos)
        screen.blit(img, img.get_rect(center=(round(x), round(y))))

    def draw_intro_sign(self, screen):
        """줌 아웃 동안: 큰 간판이 출발역으로 줄어들며 사라짐(호선 선택 연출에서 이어짐)."""
        if self.intro is None:
            return
        s = self.session
        k = min(1.0, self.intro / C.INTRO_TIME)
        lg = self.app.signs.for_station("lg", s.home_line_id, s.start)
        if not lg:
            return
        sx, sy = self.cam.to_screen(*s.train.pos)
        scale = 2 * (1 - k) + 0.3 * k
        img = pygame.transform.scale(lg, (max(1, round(lg.get_width() * scale)), max(1, round(lg.get_height() * scale))))
        img.set_alpha(round(255 * (1 - k)))
        bx, by = self.app.signs.badge_center("lg")
        screen.blit(img, (round(sx - bx * scale), round(sy - by * scale)))
