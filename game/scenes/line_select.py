"""호선 선택 — 호선 아이콘, Point 해금, 선택한 호선의 출발역·도착역 지정(하단 탭), 선택 연출."""
import pygame

from game import config as C
from game.scenes.base import BG, GRAY, INK, Button, Scene
from game.scenes.station_field import StationField

COLS = 4
CELL_W, CELL_H = 160, 88
ICON = 64
HEADER_H = 110
ICON_GAP = 28
ICON_W, ICON_H = 240, 44
TAB_W, TAB_H = 640, 126       # 하단 탭(출발역·도착역·출발 버튼)
TAB_MARGIN = 16               # 화면 아래와 탭 사이
FIELD_H, FIELD_GAP = 44, 10
SELECT_RING = (255, 170, 40)  # 선택된 호선 표시


class LineSelect(Scene):
    title = "호선 선택"

    def __init__(self, app):
        super().__init__(app)
        self.names = {lid: name for lid, name, _ in C.LINE_MENU}
        self.starts = {lid: start for lid, _, start in C.LINE_MENU}
        self.rows = self.make_rows()
        self.cells = {}
        self.back = Button("뒤로가기")
        self.buttons = [self.back] 
        self.msg, self.msg_left = "", 0.0
        self.anim = None
        self.selected = None                    # 고른 호선(아직 출발 전)
        m = app.map
        self.f_start = StationField(app, "출발역", self.start_items, lambda name: self.selected or self.open_line_at(name),
                                    placeholder="출발역 입력")
        self.f_dest = StationField(app, "도착역", lambda: sorted(m.by_name), self.first_line,
                                   allow_none=True, placeholder="도착역 입력(선택)")
        self.fields = [self.f_start, self.f_dest]
        self.go_btn = Button("출발", color=(0, 82, 164))

    def start_items(self):
        """출발역 목록: 호선을 골랐으면 그 호선의 역(노선 순서), 아니면 탈 수 있는 모든 역(가나다순)."""
        m = self.app.map
        if self.selected:
            return m.lines[self.selected].station_names()
        return sorted(n for n, st in m.by_name.items() if self.open_line_at(n))

    def open_line_at(self, name):
        """그 역을 지나는 호선 중 지금 탈 수 있는(해금·표시) 첫 호선. 없으면 None."""
        st = self.app.map.by_name[name]
        return next((lid for lid in st.line_id if lid in self.names and self.state(lid)[0] == "open"), None)

    def first_line(self, name):
        """도착역 목록의 간판에 쓸 호선: 그 역을 지나는 첫 번째 운행 호선."""
        st = self.app.map.by_name[name]
        lines = self.app.map.lines
        return next((i for i in st.line_id if i in lines and lines[i].available), st.line_id[0])

    def make_rows(self):
        lines = self.app.map.lines
        rows = []
        
        ids = [lid for lid, _, _ in C.LINE_MENU ]
        for i in range(0, len(ids), COLS):
            chunk = ids[i:i + COLS]
            rows.append(chunk+ [None] * (COLS - len(chunk)))
        return rows

    def layout(self, screen):
        sw, sh = screen.get_size()
        grid_w = COLS * CELL_W
        grid_h = len(self.rows) * CELL_H
        block_h = grid_h + ICON_GAP + ICON_H                 # 격자 + 간격 + 뒤로 버튼
        x0 = (sw - grid_w) // 2                              # 가로 가운데
        room = sh - TAB_H - TAB_MARGIN - 20                 # 하단 탭을 뺀 높이
        y0 = max(HEADER_H, (room - block_h) // 2)            # 세로 가운데(제목 아래로는 안 올라감)
        self.cells = {}
        for r, row in enumerate(self.rows):
            for c, lid in enumerate(row):
                if lid is None:
                    continue
                cx = x0 + c * CELL_W + CELL_W // 2           # 칸의 가운데
                top = y0 + r * CELL_H
                self.cells[lid] = pygame.Rect(cx - ICON // 2, top, ICON, ICON)
        self.back.rect = pygame.Rect((sw - ICON_W) // 2, y0 + grid_h + ICON_GAP, ICON_W, ICON_H)
        self.tab = pygame.Rect((sw - TAB_W) // 2, sh - TAB_H - TAB_MARGIN, TAB_W, TAB_H)
        fx, fy = self.tab.left + 14, self.tab.top + 14
        fw = TAB_W - 14 * 3 - 112
        self.f_start.rect = pygame.Rect(fx, fy, fw, FIELD_H)
        self.f_dest.rect = pygame.Rect(fx, fy + FIELD_H + FIELD_GAP, fw, FIELD_H)
        self.go_btn.rect = pygame.Rect(self.tab.right - 14 - 112, fy, 112, FIELD_H * 2 + FIELD_GAP)

    def state(self,lid):
        line = self.app.map.lines[lid]
        prof = self.app.profile
        if not line.available or self.starts.get(lid) is None:
            return "None", "Ready" , GRAY
        if not self.app.setting.line_visible(lid):
            return "off", "설정에서 꺼짐", GRAY
        if prof.is_unlocked(lid):
            return "open", self.names[lid], INK
        price =  prof.next_price()
        color = (30, 140, 70) if prof.points >= price else (176,110, 20)
        return "locked", f"구매 :{price:,}P", color

    def draw(self,screen):
        self.draw_bg(screen)
        self.layout(screen)
        self.draw_band(screen, list(self.cells.values()) + [self.back.rect, self.tab])
        sw, sh = screen.get_size()
        f, small = self.app.f_button, self.app.f_small

        t= self.app.f_title.render(self.title, False, INK)
        screen.blit(t, t.get_rect(center=(sw // 2, 40)))
        p = f.render(f"보유 Point  {self.app.profile.points:,} P", False, (176, 110, 20))
        screen.blit(p, p.get_rect(center=(sw // 2, 86)))

        mp = pygame.mouse.get_pos()
        for lid, rect in self.cells.items():
            if self.anim and self.anim["lid"] == lid:
                continue
            kind, text, color = self.state(lid)
            on, off = self.app.icon[lid]
            img= on if kind == "open" else off
            hover = kind in ("open", "locked") and rect.collidepoint(mp) and not self.anim
            if hover:
                size = round(ICON *1.5)
                img  = pygame.transform.scale(img, (size, size))
                pygame.draw.circle(screen, (255,255,255), rect.center, size //2 + 3, 2)
            screen.blit(img, img.get_rect(center=rect.center))
            if lid == self.selected:                         # 선택된 호선: 주황 고리
                pygame.draw.circle(screen, SELECT_RING, rect.center, ICON // 2 + 7, 4)
            label = small.render(text, False, color)
            screen.blit(label, label.get_rect(midtop=(rect.centerx, rect.bottom + 4)))

        self.back.draw(screen, f, small, self.back.rect.collidepoint(mp) and not self.anim)
        self.draw_tab(screen, mp)
        self.draw_message(screen)
        self.draw_anim(screen)

    def draw_tab(self, screen, mp):
        """하단 탭(늘 보임): 출발역 / 도착역 칸 + 출발 버튼. 목록은 칸 위로 펼쳐짐.
        호선을 안 골랐으면 출발역 목록은 탈 수 있는 모든 역이고, 출발역을 고르면 호선이 자동 선택된다."""
        if self.anim:
            return
        f, small = self.app.f_button, self.app.f_small
        pygame.draw.rect(screen, (245, 247, 250), self.tab, border_radius=14)
        edge = self.app.map.lines[self.selected].color if self.selected else GRAY
        pygame.draw.rect(screen, edge, self.tab, 3, border_radius=14)
        self.go_btn.enabled = bool(self.selected and self.f_start.value)
        self.go_btn.draw(screen, f, small, self.go_btn.rect.collidepoint(mp))
        hint = small.render("Tab: 칸 이동   Enter: 출발", False, GRAY)
        screen.blit(hint, hint.get_rect(midbottom=(self.tab.centerx, self.tab.top - 4)))
        for fld in sorted(self.fields, key=lambda x: x.open):  # 펼쳐진 칸을 나중에(목록이 위에 오게)
            fld.draw(screen)

    def draw_message(self, screen):
        if self.msg_left <= 0:
            return
        sw, sh = screen.get_size()
        m = self.app.f_button.render(self.msg, False, INK)
        r = m.get_rect(center=(sw // 2, sh - TAB_H - TAB_MARGIN - 40)).inflate(28,14)   # 하단 탭 위
        pygame.draw.rect(screen, (255, 255, 255), r, border_radius=10)
        pygame.draw.rect(screen, (176, 110, 20), r, 2, border_radius=10)
        screen.blit(m, m.get_rect(center=r.center))

    def handle(self, e):
        if self.anim:
            return
        for fld in self.fields:                              # 입력칸이 먼저(목록 클릭·키보드 입력). 탭은 늘 열려 있음
            if fld.handle(e):
                self.sync_line()
                return
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_TAB:                        # Tab: 출발역 → 도착역 → (없음) 순으로 칸 이동
                i = next((k for k, fld in enumerate(self.fields) if fld.focus), -1)
                for fld in self.fields:
                    fld.set_focus(False)
                    fld.open = False
                if i + 1 < len(self.fields):
                    self.fields[i + 1].set_focus(True)
                return
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return self.begin()
            if e.key == pygame.K_ESCAPE and self.selected:   # ESC: 호선 선택 취소(한 번 더 누르면 뒤로)
                self.selected = None
                self.f_start.value = None
                return
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1 and self.go_btn.rect.collidepoint(e.pos):
            return self.begin()
        if e.type == pygame.MOUSEBUTTONUP and e.button ==1:
            for lid, rect in self.cells.items():
                if rect.collidepoint(e.pos):
                    return self.click_icon(lid)
        super().handle(e)

    def sync_line(self):
        """호선을 안 고른 채 출발역을 정하면 그 역의 탈 수 있는 호선을 자동으로 고른다."""
        if not self.selected and self.f_start.value:
            self.selected = self.open_line_at(self.f_start.value)

    def click_icon(self, lid):
        kind, _, _ = self.state(lid)
        if kind in ("open", "locked") and not (kind == "open" and self.selected == lid):
            self.app.sound.play("button_click")              # 같은 아이콘 재클릭(출발)은 start 소리
        if kind == "open":
            if self.selected == lid:
                self.begin()                                 # 같은 아이콘을 한 번 더: 출발
            else:
                self.selected = lid                          # 호선 선택 → 하단 탭 열림, 출발역은 기본값
                self.f_start.value = self.starts[lid]
        elif kind == 'locked':
            prof = self.app.profile
            price = prof.next_price()
            if prof.buy(lid):
                self.say(f"{self.names[lid]} 해금!  (-{price:,} P)")
            else:
                self.say(f"Point 부족  (보유 {prof.points:,} / 필요 {price:,})")

    def begin(self):
        """선택 연출 시작(고른 출발역·도착역을 함께 넘김)."""
        lid = self.selected
        if not lid or not self.f_start.value:
            return
        for fld in self.fields:
            fld.set_focus(False)
            fld.open = False
        self.app.sound.play("start")
        self.anim = {"lid": lid, "t": 0.0, "from": self.cells[lid].center,
                     "start": self.f_start.value, "dest": self.f_dest.value}

    def say(self, text):
        self.msg, self.msg_left= text, 2.5

    def update(self, dt):
        self.msg_left = max(0.0, self.msg_left-dt)
        if self.anim:
            self.anim["t"]+=dt
            if self.anim["t"] >= self.anim_total(self.anim["start"]):   # 떠오름 + (뒤집기) + 간판
                self.start_play(self.anim["lid"])

    def on_click(self, b):
        if b is self.back:
            self.on_escape()

    def on_escape(self):
        from game.scenes.region_select import RegionSelect
        self.app.go(RegionSelect(self.app))

    def anim_total(self, start):
        """연출 전체 시간: 떠오름 0.25 + (출발역이 환승역이면 뒤집기 0.24) + 멈춤 0.3"""
        flip = C.FLIP_TIME if self.app.signs.is_transfer(start) else 0.0
        return C.RISE_TIME + flip + C.SIGN_HOLD

    def draw_anim(self,screen):
        if not self.anim:
            return
        sw, sh = screen.get_size()
        lid = self.anim["lid"]
        t = min(1.0, self.anim["t"] / C.RISE_TIME)
        k = 1 - (1-t)**3

        Shade = pygame.Surface((sw, sh), pygame.SRCALPHA)
        Shade.fill((10,14,24,int(140*k)))
        screen.blit(Shade, (0, 0))

        start = self.anim["start"]                               # 하단 탭에서 고른 출발역
        transfer = self.app.signs.is_transfer(start)
        sign = self.app.signs.for_station("lg", lid, start)      # 환승역이면 삼태극 간판
        if self.anim["t"] < C.RISE_TIME or sign is None:
            # ① 떠오름: 아이콘이 가운데로 이동하며 64 → 128
            fx, fy = self.anim["from"]
            x = fx + (sw /2 -fx)*k
            y = fy + (sh /2 -fy)*k
            size = round(ICON+ICON*k)
            img = pygame.transform.scale(self.app.icon[lid][0], (size, size))
            screen.blit(img, img.get_rect(center=(round(x), round(y))))
        else:
            # ② 출발역 간판 ×2 — 간판 속 기호(64→128)가 떠오른 아이콘 자리에 정확히 겹치게
            big = pygame.transform.scale(sign, (sign.get_width() * 2, sign.get_height() * 2))
            bx, by = self.app.signs.badge_center("lg")
            screen.blit(big, (sw // 2 - bx * 2, sh // 2 - by * 2))
            t2 = self.anim["t"] - C.RISE_TIME
            if transfer and t2 < C.FLIP_TIME:
                # ③ 환승역: 호선 기호 ① 이 동전처럼 뒤집혀 삼태극으로 (가로 폭만 128 → 0 → 128)
                pygame.draw.circle(screen, (255, 255, 255), (sw // 2, sh // 2), ICON + 1)   # 간판 속 삼태극 가리기
                half = C.FLIP_TIME / 2
                if t2 < half:
                    face, w = self.app.icon[lid][0], 1 - t2 / half              # 앞면 ① 이 납작해짐
                else:
                    face, w = self.app.signs.taegeuk("lg"), (t2 - half) / half  # 뒷면 삼태극이 펼쳐짐
                w = max(2, round(ICON * 2 * w))
                img = pygame.transform.scale(face, (w, ICON * 2))
                screen.blit(img, img.get_rect(center=(sw // 2, sh // 2)))

    def start_play(self, lid):
        start, dest = self.anim["start"], self.anim["dest"]
        self.anim = None
        from game.scenes.subway_play import SubwayPlay
        self.app.go(SubwayPlay(self.app, lid, start=start, dest=dest))