"""Scene 기본 클래스와 공용 UI(Button 등)."""

import pygame

from game import config as C

BG = (226, 232, 236)
INK = (30, 34, 40)
GRAY = (150, 156, 164)

class Button:
    def __init__(self, label, enabled=True, color=(110,120,132), note="", note_color=None):
        self.label = label
        self.enabled = enabled
        self.color = color
        self.note = note
        self.note_color = note_color
        self.rect = pygame.Rect(0, 0, 0, 0)

    def draw(self, screen, font, small, hover):
        face = (255,255,255) if self.enabled else (214, 218, 222)
        if self.enabled and hover:
            face = (235, 243, 255)
        pygame.draw.rect(screen, face, self.rect, border_radius=10)
        pygame.draw.rect(screen, self.color if self.enabled else GRAY, self.rect, 3, border_radius=10)
        img = font.render(self.label, False, INK if self.enabled else GRAY)   # ① False
        screen.blit(img, img.get_rect(center=self.rect.center))
        if self.note:
            n = small.render(self.note, False, self.note_color or GRAY)
            screen.blit(n, n.get_rect(midright=(self.rect.right - 16, self.rect.centery)))

class Scene:
    """버튼을 화면 가운데에 세로로 쌓는 기본 화면. 화면마다 상속해서 쓴다."""
    title = ""
    bw, bh, gap = 420, 64, 16          # 버튼 폭·높이·간격
    bg_dim = C.LOBBY_DIM               # 로비 배경 회색 필터 투명도(설정 화면은 40%)

    def __init__(self, app):
        self.app = app
        self.buttons = []

    # --- 배치 ---
    def layout(self, screen):
        sw, sh = screen.get_size()
        total = len(self.buttons) * self.bh + (len(self.buttons) - 1) * self.gap
        y = (sh - total) // 2 + 20
        for b in self.buttons:
            b.rect = pygame.Rect((sw - self.bw) // 2, y, self.bw, self.bh)
            y += self.bh + self.gap

    # --- 앱이 매 프레임 부르는 세 가지 ---
    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            for b in self.buttons:
                if b.enabled and b.rect.collidepoint(e.pos):
                    self.app.sound.play(self.sound_for(b))
                    self.on_click(b)
                    return
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.on_escape()

    def update(self, dt):
        pass

    def draw(self, screen):
        self.draw_bg(screen)
        self.layout(screen)                                    # ② 창 크기가 바뀌어도 가운데 유지
        self.draw_band(screen, [b.rect for b in self.buttons])
        if self.buttons:
            t = self.app.f_title.render(self.title, False, INK)
            screen.blit(t, t.get_rect(center=(screen.get_width() // 2, self.buttons[0].rect.top - 70)))
        mp = pygame.mouse.get_pos()
        for b in self.buttons:
            b.draw(screen, self.app.f_button, self.app.f_small, b.enabled and b.rect.collidepoint(mp))
        self.draw_extra(screen)
        # ③ flip 은 하지 않는다 — App 이 한 번만 한다

    def draw_band(self, screen, rects):
        """제목·버튼 뒤 세로 반투명 띠: 버튼들이 차지한 폭에 양옆 10% 를 더해 화면 위~아래로."""
        rects = [r for r in rects if r.width]
        if not rects or not getattr(self.app, "lobby_bg", None):
            return
        u = rects[0].unionall(rects[1:])
        pad = round(u.width * C.LOBBY_BAND_PAD)
        band = pygame.Surface((u.width + 2 * pad, screen.get_height()))
        band.fill(C.LOBBY_BAND)
        band.set_alpha(C.LOBBY_BAND_ALPHA)
        screen.blit(band, (u.left - pad, 0))

    def draw_bg(self, screen):
        """로비 배경(GIF) + 회색 필터. 배경이 없으면 단색."""
        bg = getattr(self.app, "lobby_bg", None)
        if bg:
            bg.draw(screen, self.bg_dim)
        else:
            screen.fill(BG)

    # --- 자식 장면이 바꿔 쓰는 것들 ---
    def draw_extra(self, screen): pass
    def on_click(self, b): pass
    def sound_for(self, b): return "button_click"      # 버튼 소리(설정 화면은 on_off / reset)
    def on_escape(self): pass