"""설정 — 행정구·동 이름 표시, 소리, 충격 이펙트."""

import pygame

from game import config as C
from game.scenes.base import Button, Scene

def onoff(v):
    return "On" if v else "OFF"

class SettingsMenu(Scene):
    title = "설정"
    bg_dim = C.SETTINGS_DIM            # 설정 화면은 배경을 40% 회색으로 덮음
    bh, gap = 56, 12

    def __init__(self, app):
        super().__init__(app)
        self.districts = Button("")
        self.labels = Button("")
        self.sound = Button("")
        self.impact = Button("")
        self.full = Button("")
        self.subway = Button("Subway")
        self.back = Button("뒤로가기")
        self.buttons = [self.districts, self.labels, self.sound, self.impact, self.full, self.subway, self.back]
        self.refresh()

    def refresh(self):
        st = self.app.setting
        self.districts.label = "행정구 표시:" + onoff(st.districts)
        self.labels.enabled = st.districts
        self.labels.label = "지역구 표시:" + onoff(st.labels)
        self.labels.note = "" if st.districts else "행정구 꺼짐"
        self.sound.label = "소리: " + onoff(st["sound"])
        self.impact.label = "충격 효과:" + onoff(st["impact"])
        self.full.label = "전체 화면:" + onoff(pygame.display.is_fullscreen())

    def sound_for(self, b):
        return "button_click" if b in (self.subway, self.back) else "on_off"

    def on_click(self, b):
        st = self.app.setting
        if b is self.back:
            return self.on_escape()
        if b is self.subway:
            return self.app.go(SubwaySettingsMenu(self.app))
        if b is self.districts:
            st.toggle("districts")
        elif b is self.labels:
            st.toggle("labels")
        elif b is self.sound:
            st.toggle("sound")
            self.app.sound.refresh()                 # 끄면 바로 조용히, 켜면 배경음악 다시
            self.app.sound.play("on_off")            # 켰을 때만 들림
        elif b is self.impact:
            st.toggle("impact")
        elif b is self.full:
            pygame.display.toggle_fullscreen()
        self.refresh()

    def on_escape(self):
        from game.scenes.main_menu import MainMenu
        self.app.go(MainMenu(self.app))

class SubwaySettingsMenu(Scene):
    title = "설정 > 지하철"           # 실제 제목은 build() 에서 지역 이름을 붙임
    bg_dim = C.SETTINGS_DIM
    cw, ch, cgap = 300, 40, 10

    def __init__(self, app, region=None):
        super().__init__(app)
        self.rid = region or app.region                   # 지금 보는 지역(< > 로 바꿈, 게임 지역은 그대로)
        self.prev = Button("<")
        self.next = Button(">")
        self.reset = Button("", color=(200, 40, 40))     # 해금·Point 초기화(두 번 눌러야 실행)
        self.confirm = False
        self.reset_note = ""
        self.alert = 0.0                                  # 가운데 알림 남은 시간(초)
        self.back = Button("뒤로가기")
        self.build()

    def build(self):
        """지금 지역(self.rid)의 호선 on/off 버튼을 만든다."""
        r = C.REGIONS[self.rid]
        lines = self.app.region_data(self.rid)[0].lines
        self.menu = r["menu"]
        self.title = f"설정 > 지하철 ({r['name']})"
        self.line_btns = {}
        self.buttons = []
        for lid, name, start in self.menu:
            ok = lid in lines and lines[lid].available and start is not None
            b = Button(name, enabled=ok, color=lines[lid].color if lid in lines else (110, 120, 132))
            self.line_btns[b] = lid
            self.buttons.append(b)
        self.buttons += [self.reset, self.back, self.prev, self.next]   # 첫 버튼(호선) 위에 제목
        self.refresh()

    def switch(self, step):
        ids = list(C.REGIONS)
        self.rid = ids[(ids.index(self.rid) + step) % len(ids)]
        self.confirm = False
        self.build()

    def handle(self, e):
        if e.type == pygame.KEYDOWN and e.key in (pygame.K_LEFT, pygame.K_RIGHT):
            self.app.sound.play("button_click")
            return self.switch(-1 if e.key == pygame.K_LEFT else 1)
        super().handle(e)

    def refresh(self):
        st = self.app.setting
        for b, lid in self.line_btns.items():
            name = next(n for i, n, _ in self.menu if i == lid)
            if b.enabled:
                b.label = f"{name}: "+ onoff(st.line_visible(lid))
            else:
                b.label, b.note = name, "준비중"
        if self.confirm:
            self.reset.label, self.reset.note = "정말 초기화할까요? 한 번 더 누르기", ""
        else:
            self.reset.label = "초기화 (해금 호선 잠금, Point 0)"
            self.reset.note = self.reset_note

    def layout(self, screen):
        sw, sh = screen.get_size()
        items = list(self.line_btns)
        rows = (len(items) +1 )//2 
        total_h = rows * (self.ch + self.cgap) + 2 * self.ch + self.cgap     # 초기화 + 뒤로가기
        x0 = sw // 2- self.cw - self.cgap // 2
        y0 = (sh - total_h)//2 + 30
        for i,b in enumerate(items):
            col, row = i % 2, i // 2
            b.rect = pygame.Rect(x0 + col * (self.cw+self.cgap), y0 + row * (self.ch + self.cgap), self.cw, self.ch)
        y = y0 + rows * (self.ch + self.cgap) + self.cgap
        self.reset.rect = pygame.Rect(x0, y, 2 * self.cw + self.cgap, self.ch)
        self.back.rect = pygame.Rect(x0, y + self.ch + self.cgap, 2 * self.cw + self.cgap, self.ch)
        ty = y0 - 70                                                  # 제목 줄(Scene.draw 와 같은 높이)
        half = self.app.f_title.size(self.title)[0] // 2 + 24
        self.prev.rect = pygame.Rect(0, 0, 52, 48)
        self.next.rect = pygame.Rect(0, 0, 52, 48)
        self.prev.rect.midright = (sw // 2 - half, ty)
        self.next.rect.midleft = (sw // 2 + half, ty)

    def sound_for(self, b):
        if b in (self.back, self.prev, self.next):
            return "button_click"
        if b is self.reset:
            return "reset" if self.confirm else "button_click"   # 실제로 지울 때 reset 소리
        return "on_off"

    def on_click(self, b):
        if b is self.back:
            return self.on_escape()
        if b in (self.prev, self.next):
            return self.switch(-1 if b is self.prev else 1)
        if b is self.reset:
            if self.confirm:                                 # 두 번째 클릭: 실행
                self.app.profile.reset()
                self.confirm = False
                self.alert = C.ALERT_TIME                    # 화면 가운데 "초기화 완료" 1초
            else:                                            # 첫 클릭: 확인 요청
                self.confirm, self.reset_note = True, ""
            return self.refresh()
        self.confirm = False                                 # 다른 버튼을 누르면 확인 취소
        self.app.setting.toggle_line(self.line_btns[b])
        self.refresh()

    def update(self, dt):
        self.alert = max(0.0, self.alert - dt)

    def draw_extra(self, screen):
        """초기화 완료 알림: 화면 전체 검은색 75% + 가운데 가로 흰 띠 + 글씨."""
        if self.alert <= 0:
            return
        sw, sh = screen.get_size()
        dim = pygame.Surface((sw, sh))
        dim.fill((0, 0, 0))
        dim.set_alpha(round(255 * C.ALERT_DIM))
        screen.blit(dim, (0, 0))
        band = pygame.Surface((sw, 110))
        band.fill((255, 255, 255))
        band.set_alpha(round(255 * C.ALERT_BAND_ALPHA))
        screen.blit(band, band.get_rect(center=(sw // 2, sh // 2)))
        t = self.app.f_title.render("초기화 완료", False, (30, 34, 40))
        screen.blit(t, t.get_rect(center=(sw // 2, sh // 2)))

    def on_escape(self):
        self.app.go(SettingsMenu(self.app))