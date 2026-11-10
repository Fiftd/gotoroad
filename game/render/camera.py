"""카메라 — 이동, 확대, 열차 따라가기."""

import math

class Camera:
    def __init__(self):
        self.zoom = 1.0
        self.ox = 0.0
        self.oy = 0.0

    def to_screen(self, x, y):
        return x * self.zoom + self.ox, y * self.zoom + self.oy

    def to_world(self, sx, sy):
        return ( sx - self.ox ) / self.zoom , (sy - self.oy) / self.zoom

    def fit_zoom(self, screen_size, map_w, map_h):
        sw, sh = screen_size
        return min(sw/ map_w, sh / map_h)

    def fit(self, screen_size, map_w, map_h):
        sw, sh = screen_size
        self.zoom = self.fit_zoom(screen_size, map_w, map_h)
        self.ox = (sw - map_w * self.zoom ) / 2 
        self.oy = (sh - map_h * self.zoom ) / 2

    def focus(self, x, y, screen_size):
        sw, sh = screen_size
        self.ox = sw / 2 - x * self.zoom
        self.oy = sh / 2 - y * self.zoom

    def pan(self, dx, dy):
        self.ox += dx
        self.oy += dy

    def zoom_at(self, factor, sx, sy, lo, hi):
        wx, wy = self.to_world(sx, sy)
        self.zoom =max(lo, min(hi, self.zoom * factor))
        self.ox = sx - wx*self.zoom
        self.oy = sy - wy*self.zoom

    def follow(self, x, y, dt, screen_szie, k=7.0):
        sw, sh = screen_szie
        a = 1 - math.exp(-k*dt)
        self.ox += ( sw / 2 - x* self.zoom - self.ox) *a
        self.oy += ( sh / 2 - y * self.zoom - self.oy)*a

    def ease_zoom(self,target, dt, screen_szie, k=6.0):
        sw, sh = screen_szie
        wx, wy = self.to_world(sw/2, sh/2)
        self.zoom += (target - self.zoom) * (1 - math.exp(-k*dt))
        self.ox, self.oy = sw/2 - wx * self.zoom, sh/2 - wy* self.zoom
    