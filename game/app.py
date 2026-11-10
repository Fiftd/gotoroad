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

        self.map = MapData()
        self.profile = Profile()
        self.setting = Settings()
        self.icon = self.load_icons()
        self.signs = SignBook()          # 역 간판(필요할 때 읽음)
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

    def load_icons(self):
        icons = {}
        for lid in self.map.lines:
            on = pygame.image.load(os.path.join(C.LINE_ICONS, f"{lid}.png")).convert_alpha()
            off = pygame.image.load(os.path.join(C.LINE_ICONS, f"{lid}_locked.png")).convert_alpha()
            icons[lid] = (on, off)
        return icons