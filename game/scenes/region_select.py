"""권역 선택 — 수도권 / 대구권 / 부산권 / 뒤로가기."""
from game.scenes.base import Button, Scene

class RegionSelect(Scene):
    title = "역 선택"

    def __init__(self, app):
        super().__init__(app)
        self.capital = Button("수도권", color=(0, 82, 164))
        self.daegu = Button("대구권", color=(217, 63, 92))
        self.busan = Button("부산권", color=(240, 106, 0))
        self.back = Button("뒤로가기")
        self.buttons = [self.capital, self.daegu, self.busan, self.back]


    def on_click(self, b):
        if b is self.back:
            return self.on_escape()
        rid = {self.capital: "seoul", self.daegu: "daegu", self.busan: "busan"}.get(b)
        if rid:
            self.app.set_region(rid)
            from game.scenes.line_select import LineSelect
            self.app.go(LineSelect(self.app))

    def on_escape(self):
        from game.scenes.main_menu import MainMenu
        self.app.go(MainMenu(self.app))