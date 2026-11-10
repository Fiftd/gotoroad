"""타일·선로·역 그리기, 구·동 이름 표시."""

import math
import os
import pygame

from game import config as C
from game.world.geometry import offset_polyline, segment_edges

BG = (226, 232, 236)
LINE_STYLE = {
    "main":  (14, 10, 0, None),
    "city":  (14, 10, 4, None), 
    "light": (8, 4, 0, None),
    "trunk": (14, 10, 2, (6, 6)),
}
LINE_SCALE = 1.6
CULL = 400
WHITE = (255,255,255)
TILE_CACHE = 48            # 메모리에 들고 있을 지도 조각 수
OVERVIEW_SWITCH = 1.3      # 확대가 (축소 그림 배율 × 이 값)보다 작으면 축소 그림으로 그림

class ManRender:
    def __init__(self, map_data, setting, signs=None):
        self.map = map_data
        self.setting = setting
        self._sets = {}
        self._scaled = {}
        self._scaled_key = None
        self._paths = {}
        self._corr, self._corr_key = {}, None   # 나란히 놓기용 구간 표
        self.signs = signs
        self._tg = {}
        self._loaded = {}                       # 읽어 둔 조각 그림(경로 → Surface)
        self._ov, self._ov_key = None, None

    def set_name(self):
        if not self.setting.districts:
            return "tiles-plain"
        return "tiles-labeled" if self.setting.labels else "tiles"

    def tiles(self):
        """[(x, y, 파일 경로), ...] — 그림은 화면에 보일 때만 읽는다(큰 수도권 지도는 조각이 200개가 넘음)."""
        name = self.set_name()
        if name not in self._sets:
            self._sets.clear()
            self._loaded.clear()
            folder = os.path.join(self.map.dir, name)
            self._sets[name] = [(t["x"], t["y"], os.path.join(folder, t["file"])) for t in self.map.tiles]
        return self._sets[name]

    def _tile(self, path):
        """조각 그림(최근에 쓴 것만 TILE_CACHE 개 보관)."""
        surf = self._loaded.pop(path, None)
        if surf is None:
            surf = pygame.image.load(path).convert_alpha()
        self._loaded[path] = surf
        while len(self._loaded) > TILE_CACHE:
            self._loaded.pop(next(iter(self._loaded)))
        return surf

    def _tile_surface(self, path, zoom):
        key = (self.set_name(), round(zoom, 4))
        if key != self._scaled_key:
            self._scaled, self._scaled_key = {}, key
        if path not in self._scaled:
            surf = self._tile(path)
            w = max(1, math.ceil(surf.get_width() * zoom))
            h = max(1, math.ceil(surf.get_height() * zoom))
            self._scaled[path] = pygame.transform.scale(surf, (w, h))
        return self._scaled[path]

    def _overview(self):
        """전체를 줄인 그림(data.json 의 overview) — 멀리서 볼 때 조각 대신 쓴다. 없으면 None."""
        ov = self.map.overview
        if not ov:
            return None
        name = self.set_name()
        if self._ov_key != name:
            path = os.path.join(self.map.dir, ov["files"][name])
            self._ov = pygame.image.load(path).convert_alpha() if os.path.exists(path) else None
            self._ov_key = name
        return self._ov

    def draw_tiles(self, screen, cam):
        sw, sh = screen.get_size()
        ov = self._overview()
        if ov is not None and cam.zoom < self.map.overview["scale"] * OVERVIEW_SWITCH:
            k = self.map.overview["scale"]
            x0, y0 = cam.to_world(0, 0)
            x1, y1 = cam.to_world(sw, sh)
            r = pygame.Rect(math.floor(x0 * k), math.floor(y0 * k), math.ceil((x1 - x0) * k) + 2, math.ceil((y1 - y0) * k) + 2)
            r = r.clip(ov.get_rect())
            if r.w > 0 and r.h > 0:
                sx, sy = cam.to_screen(r.x / k, r.y / k)
                size = (max(1, round(r.w / k * cam.zoom)), max(1, round(r.h / k * cam.zoom)))
                screen.blit(pygame.transform.scale(ov.subsurface(r), size), (round(sx), round(sy)))
            return
        tw, th = self.map.tile_w * cam.zoom, self.map.tile_h * cam.zoom
        for x, y, path in self.tiles():
            sx, sy = cam.to_screen(x, y)
            if sx > sw or sy > sh or sx + tw < 0 or sy + th < 0:
                continue
            screen.blit(self._tile_surface(path, cam.zoom), (round(sx), round(sy)))

    def draw(self, screen, cam, focus=None , start=None):
        screen.fill(BG)
        self.draw_tiles(screen, cam)

        self.draw_lines(screen, cam, focus)
        stations = self.draw_stations(screen, cam, focus, start)
        self.draw_labels(screen, cam, stations, focus, start)

    def line_paths(self, line):
        """[(역a, 역b, 점 목록, 경계 상자), ...] — 구간(역↔역)마다 한 번씩. 모양은 geometry 가 정한다."""
        if line.id not in self._paths:
            out, seen = [], set()
            for seg in line.segments:
                for a, b, p in segment_edges(seg, self.map.positions):
                    key = tuple(sorted((a, b)))
                    if key in seen:
                        continue
                    seen.add(key)
                    xs, ys = [q[0] for q in p], [q[1] for q in p]
                    out.append((a, b, p, (min(xs), min(ys), max(xs), max(ys))))
            self._paths[line.id] = out
        return self._paths[line.id]

    def corridors(self):
        """{(역a, 역b): ([보이는 호선 id, ...], 기준 곡선)} — 같은 두 역을 잇는 호선들.
        기준 곡선은 그중 첫 호선의 곡선을 이름 순(a→b)으로 맞춘 것. 보이는 호선이 바뀔 때만 다시 계산."""
        vis = tuple(l.id for l in self.map.lines.values() if l.visible)
        if self._corr_key != vis:
            corr = {}
            for lid in vis:
                for a, b, p, _ in self.line_paths(self.map.lines[lid]):
                    key = tuple(sorted((a, b)))
                    if key not in corr:
                        corr[key] = ([], p if (a, b) == key else p[::-1])
                    corr[key][0].append(lid)
            self._corr, self._corr_key = corr, vis
        return self._corr

    def px(self, w, zoom):
        return max(1, round(w * zoom * LINE_SCALE))

    def draw_lines(self, screen, cam, focus=None):
        sw, sh = screen.get_size()
        wx0, wy0 = cam.to_world(-CULL, -CULL)
        wx1, wy1 = cam.to_world(sw + CULL, sh + CULL)
        z = cam.zoom
        corr = self.corridors() if C.LINE_PARALLEL else {}
        gap = self.px(LINE_STYLE["main"][1], z)                # 나란히 놓을 때 호선 사이 간격 = 굵은 선 굵기
        drawn = []                                             # [(line, [화면 점 목록, ...]), ...]
        for line in sorted(self.map.lines.values(), key=lambda l: l.id == focus):   # 타는 호선을 맨 위에
            if not line.visible:
                continue
            paths = []
            for a, b, p, (bx0, by0, bx1, by1) in self.line_paths(line):
                if bx1 < wx0 or bx0 > wx1 or by1 < wy0 or by0 > wy1:
                    continue
                entry = corr.get(tuple(sorted((a, b))))
                if entry and len(entry[0]) > 1:                # 같은 두 역을 잇는 호선이 여럿 → 기준 곡선에서 나란히
                    ids, base = entry
                    shift = (ids.index(line.id) - (len(ids) - 1) / 2) * gap
                    pts = offset_polyline([cam.to_screen(x, y) for x, y in base], shift)
                else:
                    pts = [cam.to_screen(x, y) for x, y in p]
                paths.append(pts)
            if paths:
                drawn.append((line, paths))
        for line, paths in drawn:                              # 층 1: 흰 바탕(모든 호선)
            w = self.px(LINE_STYLE[line.type][0], z)
            for pts in paths:
                pygame.draw.lines(screen, WHITE, False, pts, w)
        for line, paths in drawn:                              # 층 2: 호선 색
            w = self.px(LINE_STYLE[line.type][1], z)
            for pts in paths:
                pygame.draw.lines(screen, line.color, False, pts, w)
        for line, paths in drawn:                              # 층 3: 흰 덧칠(이중선·점선)
            _, _, inner, dash = LINE_STYLE[line.type]
            if not inner:
                continue
            w = self.px(inner, z)
            for pts in paths:
                if dash:
                    self.dashed(screen, pts, WHITE, w, dash[0] * z * LINE_SCALE, dash[1] * z * LINE_SCALE)
                else:
                    pygame.draw.lines(screen, WHITE, False, pts, w)

    def dashed(self, screen, pts, color, w, on, off):
        if on <= 0 or off <= 0:
            return
        drawing, left = True, on                    # 지금 그리는 중인가, 이번 칸에서 남은 길이
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            seg = math.hypot(bx - ax, by - ay)
            pos = 0.0
            while pos < seg:
                step = min(left, seg - pos)
                end = seg if step >= seg - pos else pos + step     # 마지막 조각은 정확히 seg 로 끝냄
                if drawing:
                    t0, t1 = pos / seg, end / seg
                    pygame.draw.line(screen, color,
                                     (ax + (bx - ax) * t0, ay + (by - ay) * t0),
                                     (ax + (bx - ax) * t1, ay + (by - ay) * t1), w)
                left -= end - pos
                pos = end
                if left <= 1e-9:                     # 칸을 다 썼으면 그림 ↔ 띄움 전환
                    drawing = not drawing
                    left = on if drawing else off

    def symbol_k(self,zoom):
        return max(zoom*1.6, 0.5) if zoom < 0.6 else zoom

    def visible_lines_of(self, st):
        return [self.map.lines[i] for i in st.line_id if i in self.map.lines and self.map.lines[i].visible]

    def draw_stations(self, screen, cam, focus=None, start=None):
        sw, sh = screen.get_size()
        k = self.symbol_k(cam.zoom)
        r = max(3, round(11 * k))
        out = []                                              # 그린 역(Step 5에서 간판 붙일 때 씀)
        for st in self.map.stations:
            lines = self.visible_lines_of(st)
            if not lines:
                continue
            sx, sy = cam.to_screen(st.x, st.y)
            if not (-CULL < sx < sw + CULL and -CULL < sy < sh + CULL):
                continue
            c = (round(sx), round(sy))
            if self.signs and self.signs.is_transfer(st.name):           # 환승역: 검은 테두리 + 삼태극
                pygame.draw.circle(screen, (17, 17, 17), c, r + max(1, round(2 * k)))
                d = r * 2
                if d not in self._tg:
                    self._tg[d] = pygame.transform.scale(self.signs.taegeuk("sm"), (d, d))
                screen.blit(self._tg[d], (c[0] - r, c[1] - r))
            else:                                                        # 일반역: 호선 색 원 + 흰 속
                color = next((l.color for l in lines if l.id == focus), lines[0].color)
                pygame.draw.circle(screen, color, c, r)
                pygame.draw.circle(screen, WHITE, c, max(1, r - max(2, round(4 * k))))
            if any(self.map.lines[i].visible for i in st.switch if i in self.map.lines):   # 갈림길: 노란 마름모
                m = max(4, round(6 * k))
                qx, qy = c[0] + r, c[1] - r
                pts = [(qx, qy - m), (qx + m, qy), (qx, qy + m), (qx - m, qy)]
                pygame.draw.polygon(screen, (255, 200, 0), pts)
                pygame.draw.polygon(screen, (60, 60, 60), pts, 1)
            if st.name == start:                                         # 출발역: 노란 고리
                pygame.draw.circle(screen, (255, 196, 0), c, r + max(4, round(7 * k)), 3)
            out.append((st, c, r))
        return out

    def draw_labels(self, screen, cam, stations, focus=None, start=None):
        if not self.signs:
            return
        show_all = cam.zoom > 0.55
        placed = []                                           # 이미 놓은 간판 자리(겹치면 건너뜀)
        order = sorted(stations, key=lambda s: s[0].name != start)   # 출발역을 먼저 놓아 자리를 보장
        for st, (cx, cy), r in order:
            if not (show_all or st.name == start):
                continue
            lid = focus if focus in st.line_id else self.visible_lines_of(st)[0].id
            img = self.signs.for_station("sm", lid, st.name)  # 환승역이면 삼태극 간판
            if img is None:
                continue
            rect = img.get_rect(midbottom=(cx, cy - r - 3))   # 역 바로 위
            if st.name != start and rect.collidelist(placed) != -1:
                continue                                      # 다른 간판과 겹치면 생략
            screen.blit(img, rect)
            placed.append(rect)