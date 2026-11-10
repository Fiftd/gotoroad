"""권역 선택 — 수도권 / 대구권·대전권·부산권(미구현) / 뒤로가기."""
from game.scenes.base import Button, Scene

class RegionSelect(Scene):
    title = "역 선택"

    def __init__(self, app):
        super().__init__(app)
        self.capital = Button("수도권", color=(0, 82, 164))
        self.daegu = Button("대구권", enabled=False, note="준비 중")
        self.daejeon = Button("대전권", enabled=False, note="준비 중")
        self.busan = Button("부산권", enabled=False, note="준비 중")
        self.back = Button("뒤로가기")
        self.buttons = [self.capital, self.daegu, self.daejeon, self.busan, self.back]


    def on_click(self, b):
        if b is self.back:
            return self.on_escape()
        if b is self.capital:
            from game.scenes.line_select import LineSelect
            self.app.go(LineSelect(self.app))

    def on_escape(self):
        from game.scenes.main_menu import MainMenu
        self.app.go(MainMenu(self.app))