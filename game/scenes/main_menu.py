"""메인 메뉴 — 지하철 / 버스(미구현) / 기차(미구현) / 설정."""

from game import config as C
from game.scenes.base import Button, Scene

class MainMenu(Scene):
    title = C.TITLE

    def __init__(self, app):
        super().__init__(app)
        self.subway = Button("지하철", color=(0,12,162))
        self.bus = Button("버스", enabled=False, note="준비 중")
        self.train = Button("기차", enabled=False, note="준비 중")
        self.settings = Button("설정")
        self.buttons = [self.subway, self.bus, self.train, self.settings]

    def on_click(self, b):
        
        if b is self.subway:
            from game.scenes.region_select import RegionSelect
            self.app.go(RegionSelect(self.app))
        elif b is self.settings:
            from game.scenes.settings import SettingsMenu
            self.app.go(SettingsMenu(self.app))

    def on_escape(self):
        self.app.quit()