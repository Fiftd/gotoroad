"""App — pygame 초기화, 메인 루프, 장면(scene) 전환."""

import pygame
import os

from game import config as C
from game.save import Profile, Settings
from game.world.map_data import MapData
from game.render.signs import SignBook

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_mode(C.WINDOW_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption(C.TITLE)

        self.font = lambda size: pygame.font.Font(C.FONT_PATH, size)
        self.f_title = self.font(C.FONT_TITLE)
        self.f_button = self.font(C.FONT_BUTTON)
        self.f_small = self.font(C.FONT_SMALL)

        self._regions = {}               # {지역: (MapData, SignBook)} 한 번 읽으면 재사용
        self.set_region("seoul")
        self.profile = Profile()
        self.setting = Settings()
        self.icon = self.load_icons()
        from game.render.lobby_bg import LobbyBg
        self.lobby_bg = LobbyBg()        # 로비 움직이는 배경(장면이 바뀌어도 이어짐)
        from game.scenes.main_menu import MainMenu

        from game.sound import Sound
        self.sound = Sound(self.setting)      # 효과음·배경음악
        self.scene = None
        self.go(MainMenu(self))
        self.running = True

    def go(self, scene):
        self.scene = scene
        self.sound.stop("charging")
        self.sound.music(getattr(scene, "music", "lobby"))   # 장면마다 배경음악(같은 곡이면 이어짐)

    def quit(self):
        self.running = False

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            dt = min(clock.tick(C.FPS) /1000, C.DT_MAX)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    self.running = False
                else:
                    self.scene.handle(e)
            self.scene.update(dt)
            self.scene.draw(pygame.display.get_surface())
            pygame.display.flip()
        pygame.quit()

    def set_region(self, rid):
        """지역을 바꾼다: 지도(app.map)·역 간판(app.signs)·호선 메뉴(app.line_menu)."""
        r = C.REGIONS[rid]
        self.region = rid
        self.map, self.signs = self.region_data(rid)
        self.line_menu = r["menu"]

    def region_data(self, rid):
        """(MapData, SignBook) — 지역을 바꾸지 않고 읽기만(설정 화면에서 다른 지역 호선 보기). 한 번 읽으면 재사용."""
        if rid not in self._regions:
            r = C.REGIONS[rid]
            self._regions[rid] = (MapData(r["map"]), SignBook(r["signs"]))
        return self._regions[rid]

    def load_icons(self):
        icons = {}
        for lid in {lid for r in C.REGIONS.values() for lid, _, _ in r["menu"]}:
            if not os.path.exists(os.path.join(C.LINE_ICONS, f"{lid}.png")):
                continue
            on = pygame.image.load(os.path.join(C.LINE_ICONS, f"{lid}.png")).convert_alpha()
            off = pygame.image.load(os.path.join(C.LINE_ICONS, f"{lid}_locked.png")).convert_alpha()
            icons[lid] = (on, off)
        return icons