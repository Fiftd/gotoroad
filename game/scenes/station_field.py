"""StationField — 역 입력칸(호선 선택 화면의 하단 탭에서 출발역·도착역에 씀).

  · 마우스를 올리면 칸 위쪽으로 역 목록이 펼쳐진다. 항목을 클릭하면 그 역으로 정해진다.
  · 칸을 클릭하거나(또는 Tab 으로) 고르면 키보드 입력: 글자를 치면 목록이 걸러지고(한글 조합 중 글자도 보임),
    ↑↓ 로 고르고 Enter 로 정한다. Backspace 로 지우고, ESC 로 입력을 그만둔다.
  · allow_none=True 면 목록 맨 위에 "(없음)" 이 있다(도착역용).
"""
import pygame

INK = (20, 24, 34)
GRAY = (150, 156, 164)
ORANGE = (255, 170, 40)
ROW_H = 30          # 목록 한 줄 높이
ROWS = 8            # 목록에 한 번에 보이는 줄 수


def display_name(name):
    """'신촌 경의중앙선' → '신촌' (같은 이름 역 구분용 꼬리는 화면에 안 씀)."""
    return name.split(" ")[0]


class StationField:
    def __init__(self, app, label, items_fn, sign_line_fn, allow_none=False, placeholder="역 이름 입력"):
        self.app = app
        self.label = label                    # "출발역" / "도착역"
        self.items_fn = items_fn              # () -> [역 이름, ...]  목록에 보일 역
        self.sign_line_fn = sign_line_fn      # (역 이름) -> 간판에 쓸 호선 id
        self.allow_none = allow_none
        self.placeholder = placeholder
        self.value = None                     # 정해진 역 이름(없으면 None)
        self.query = ""                       # 입력 중인 글자
        self.composing = ""                   # 한글 조합 중인 글자(아직 확정 전)
        self.open = False                     # 목록이 펼쳐져 있는가
        self.focus = False                    # 키보드 입력 중인가
        self.hi = 0                           # 목록에서 강조된 줄
        self.scroll = 0                       # 목록 맨 위 줄 번호
        self.rect = pygame.Rect(0, 0, 0, 0)   # 칸 위치(장면이 layout 에서 정함)

    # ---------- 목록 ----------
    def options(self):
        """걸러진 목록. 입력이 앞에서 맞는 역 먼저, 그다음 중간에 들어 있는 역."""
        names = self.items_fn()
        q = (self.query + self.composing).strip()
        if q:
            head = [n for n in names if display_name(n).startswith(q)]
            mid = [n for n in names if q in display_name(n) and n not in head]
            names = head + mid
        return ([None] if self.allow_none and not q else []) + names

    def list_rect(self):
        n = min(ROWS, len(self.options()))
        h = max(1, n) * ROW_H + 12
        return pygame.Rect(self.rect.left, self.rect.top - 6 - h, self.rect.width, h)

    def keep_visible(self):
        if self.hi < self.scroll:
            self.scroll = self.hi
        elif self.hi >= self.scroll + ROWS:
            self.scroll = self.hi - ROWS + 1

    # ---------- 상태 바꾸기 ----------
    def set_focus(self, on):
        self.focus = on
        self.open = on or self.open
        if on:
            self.query, self.composing, self.hi, self.scroll = "", "", 0, 0
            pygame.key.start_text_input()
            pygame.key.set_text_input_rect(self.rect)      # 한글 입력 후보창 위치
        else:
            self.query, self.composing = "", ""
            pygame.key.stop_text_input()                   # 입력 모드 끄기(플레이 중 한글 입력기가 키를 가로채지 않게)

    def choose(self, name):
        self.value = name
        self.set_focus(False)
        self.open = False

    # ---------- 입력 ----------
    def handle(self, e):
        """이 칸이 처리한 이벤트면 True(장면은 더 처리하지 않음)."""
        if e.type == pygame.MOUSEMOTION:
            over_field = self.rect.collidepoint(e.pos)
            over_list = self.open and self.list_rect().collidepoint(e.pos)
            if over_field:
                self.open = True                           # 마우스를 올리면 목록이 펼쳐짐
            elif not over_list and not self.focus:
                self.open = False
            if over_list:
                i = self.scroll + (e.pos[1] - self.list_rect().top - 6) // ROW_H
                if 0 <= i < len(self.options()):
                    self.hi = i
            return False
        if e.type == pygame.MOUSEWHEEL and self.open:
            if self.list_rect().collidepoint(pygame.mouse.get_pos()):
                self.scroll = max(0, min(max(0, len(self.options()) - ROWS), self.scroll - e.y))
                return True
            return False
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            if self.open and self.list_rect().collidepoint(e.pos):
                i = self.scroll + (e.pos[1] - self.list_rect().top - 6) // ROW_H
                opts = self.options()
                if 0 <= i < len(opts):
                    self.choose(opts[i])
                return True
            if self.rect.collidepoint(e.pos):
                self.set_focus(True)
                return True
            if self.focus:
                self.set_focus(False)                       # 다른 곳을 누르면 입력 그만
                self.open = False
            return False
        if not self.focus:
            return False
        if e.type == pygame.TEXTINPUT:                      # 확정된 글자
            self.query += e.text
            self.composing = ""
            self.hi, self.scroll, self.open = 0, 0, True
            return True
        if e.type == pygame.TEXTEDITING:                    # 조합 중인 한글
            self.composing = e.text
            self.hi, self.scroll = 0, 0
            return True
        if e.type == pygame.KEYDOWN:
            opts = self.options()
            if e.key == pygame.K_ESCAPE:
                self.set_focus(False)
                self.open = False
            elif e.key == pygame.K_BACKSPACE:
                if not self.composing:
                    self.query = self.query[:-1]
                self.hi, self.scroll = 0, 0
            elif e.key == pygame.K_UP:
                self.hi = max(0, self.hi - 1)
                self.keep_visible()
            elif e.key == pygame.K_DOWN:
                self.hi = min(len(opts) - 1, self.hi + 1)
                self.keep_visible()
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if opts:
                    self.choose(opts[min(self.hi, len(opts) - 1)])
            elif e.key == pygame.K_TAB:
                return False                                # Tab 은 장면이 칸을 옮기는 데 씀
            return True                                     # 입력 중 다른 키는 장면으로 보내지 않음
        return False

    # ---------- 그리기 ----------
    def item_image(self, name):
        if name is None:
            return None
        return self.app.signs.for_station("sm", self.sign_line_fn(name), name)

    def draw(self, screen):
        f = self.app.f_small
        r = self.rect
        pygame.draw.rect(screen, (255, 255, 255), r, border_radius=10)
        pygame.draw.rect(screen, ORANGE if self.focus else (110, 120, 132), r, 3, border_radius=10)
        lab = f.render(self.label, False, INK)
        screen.blit(lab, lab.get_rect(midleft=(r.left + 14, r.centery)))
        x = r.left + 14 + 64
        if self.focus:                                      # 입력 중: 글자 + 조합 중 글자(밑줄) + 커서
            q = f.render(self.query, False, INK)
            screen.blit(q, q.get_rect(midleft=(x, r.centery)))
            cx = x + q.get_width()
            if self.composing:
                c = f.render(self.composing, False, (40, 90, 200))
                screen.blit(c, c.get_rect(midleft=(cx, r.centery)))
                pygame.draw.line(screen, (40, 90, 200), (cx, r.centery + 10), (cx + c.get_width(), r.centery + 10), 2)
                cx += c.get_width()
            if (pygame.time.get_ticks() // 500) % 2 == 0:
                pygame.draw.line(screen, INK, (cx + 2, r.centery - 9), (cx + 2, r.centery + 9), 2)
            if not self.query and not self.composing:
                ph = f.render(self.placeholder, False, GRAY)
                screen.blit(ph, ph.get_rect(midleft=(x + 8, r.centery)))
        else:
            img = self.item_image(self.value)
            if img:
                screen.blit(img, img.get_rect(midleft=(x, r.centery)))
            else:
                t = f.render("(없음)" if self.allow_none else self.placeholder, False, GRAY)
                screen.blit(t, t.get_rect(midleft=(x, r.centery)))
        if self.open:
            self.draw_list(screen)

    def draw_list(self, screen):
        f = self.app.f_small
        lr = self.list_rect()
        pygame.draw.rect(screen, (255, 255, 255), lr, border_radius=10)
        pygame.draw.rect(screen, (110, 120, 132), lr, 2, border_radius=10)
        opts = self.options()
        if not opts:
            t = f.render("맞는 역이 없어요", False, GRAY)
            screen.blit(t, t.get_rect(center=lr.center))
            return
        for row in range(min(ROWS, len(opts) - self.scroll)):
            i = self.scroll + row
            name = opts[i]
            ir = pygame.Rect(lr.left + 6, lr.top + 6 + row * ROW_H, lr.width - 12, ROW_H)
            if i == self.hi:
                pygame.draw.rect(screen, (235, 243, 255), ir, border_radius=6)
            if name == self.value:
                pygame.draw.rect(screen, ORANGE, ir, 2, border_radius=6)
            img = self.item_image(name)
            if img:
                screen.blit(img, img.get_rect(midleft=(ir.left + 6, ir.centery)))
            else:
                t = f.render("(없음)", False, GRAY)
                screen.blit(t, t.get_rect(midleft=(ir.left + 10, ir.centery)))
        if len(opts) > ROWS:                                 # 스크롤 막대
            track = pygame.Rect(lr.right - 8, lr.top + 6, 4, lr.height - 12)
            th = max(16, track.height * ROWS // len(opts))
            ty = track.top + (track.height - th) * self.scroll // max(1, len(opts) - ROWS)
            pygame.draw.rect(screen, (200, 205, 215), (track.left, ty, 4, th), border_radius=2)
