"""맵 살펴보기 — 드래그로 이동, 휠로 확대·축소(최대 축소 = 서울 전경)."""
import math
import pygame

from game import config as C

from game.render.camera import Camera
from game.render.map_renderer import ManRender

ZOOM_IN_MAX = 2.5        # 최대 확대
WHEEL_STEP = 0.15        # 휠 한 칸 배율(exp)


class MapView:
    def __init__(self, app, line_id=None, start=None):
        self.app = app
        self.line_id = line_id
        self.start = start                   # 출발역 이름(호선 선택에서 왔을 때)
        self.intro = None                    # 줌 아웃 연출 진행 시간(None = 연출 없음)
        self.renderer = ManRender(app.map, app.setting, app.signs)        
        self.cam = Camera()
        self.drag = None                 # 드래그 중이면 마지막 마우스 위치
        screen = pygame.display.get_surface()
        self.cam.fit(screen.get_size(), app.map.w, app.map.h)   # 서울 전경에서 시작
        if start:                                                 # 호선 선택에서 왔으면: 출발역 확대 → 줌 아웃
            st = app.map.by_name[start]
            self.cam.zoom = C.INTRO_ZOOM          # 최대 확대(2.5)보다 커도 연출이라 직접 넣음
            self.cam.focus(st.x, st.y, screen.get_size())
            self.intro = 0.0

        app.map.apply_visibility(app.setting.hidden_lines(), keep=line_id)

    def zoom_min(self):
        size = pygame.display.get_surface().get_size()
        return self.cam.fit_zoom(size, self.app.map.w, self.app.map.h)

    def handle(self, e):
        if self.intro is not None:
            return                               # 연출 중 입력 무시
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.drag = e.pos
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.drag = None
        elif e.type == pygame.MOUSEMOTION and self.drag:
            self.cam.pan(e.pos[0] - self.drag[0], e.pos[1] - self.drag[1])
            self.drag = e.pos
        elif e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            self.cam.zoom_at(math.exp(e.y * WHEEL_STEP), mx, my, self.zoom_min(), ZOOM_IN_MAX)
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                from game.scenes.line_select import LineSelect
                self.app.go(LineSelect(self.app))
            elif e.key == pygame.K_f:                 # F: 전경으로 되돌리기
                self.cam.fit(pygame.display.get_surface().get_size(), self.app.map.w, self.app.map.h)

    def update(self, dt):
        if self.intro is None:
            return
        self.intro += dt
        t = min(1.0, self.intro / C.INTRO_TIME)
        k = 1 - (1 - t) ** 3                                       # ease-out
        st = self.app.map.by_name[self.start]
        self.cam.zoom = C.INTRO_ZOOM + (C.ZOOM - C.INTRO_ZOOM) * k  # 3.0 → 0.9
        self.cam.focus(st.x, st.y, pygame.display.get_surface().get_size())
        if t >= 1.0:
            self.intro = None

    def draw(self, screen):
        self.renderer.draw(screen, self.cam, focus=self.line_id, start=self.start)
        if not self.start:
            return
        st = self.app.map.by_name[self.start]
        sx, sy = self.cam.to_screen(st.x, st.y)

        if self.intro is not None:                                   # 큰 간판이 출발역으로 줄어들며 사라짐
            k = min(1.0, self.intro / C.INTRO_TIME)
            lg = self.app.signs.for_station("lg", self.line_id, self.start)
            if lg:
                scale = 2 * (1 - k) + 0.3 * k
                img = pygame.transform.scale(lg, (max(1, round(lg.get_width() * scale)),
                                                  max(1, round(lg.get_height() * scale))))
                img.set_alpha(round(255 * (1 - k)))
                bx, by = self.app.signs.badge_center("lg")
                screen.blit(img, (round(sx - bx * scale), round(sy - by * scale)))