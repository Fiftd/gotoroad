"""SignBook — 역 간판 이미지(lg/sm)를 필요할 때 읽어 저장해 둔다."""
import json
import os

import pygame

from game import config as C


class SignBook:
    def __init__(self, root=C.STATION_SIGNS):
        self.root = root                         # 지역마다 간판 폴더가 따로 있음(서울 = station_signs/, 대구 = station_signs/daegu/)
        with open(os.path.join(root, "signs.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        self._cache = {}                         # {(크기, 호선, 역): Surface 또는 None}

    def get(self, size, lid, name):
        """size = "lg" 또는 "sm". 그 호선에 없는 역이면 None."""
        key = (size, lid, name)
        if key not in self._cache:
            path = os.path.join(self.root, size, lid, f"{name}.png")
            self._cache[key] = pygame.image.load(path).convert_alpha() if os.path.exists(path) else None
        return self._cache[key]

    def is_transfer(self, name):
        """운행 호선이 2개 이상인 환승역인가(signs.json 의 transfer 목록)."""
        return name in self.meta.get("transfer", {})

    def for_station(self, size, lid, name):
        """역에 맞는 간판: 환승역이면 삼태극 간판(transfer), 아니면 그 호선 간판."""
        if self.is_transfer(name):
            return self.get(size, "transfer", name)
        return self.get(size, lid, name)

    def taegeuk(self, size):
        """삼태극 기호만 따로(size = "lg" 64px / "sm" 18px)."""
        key = ("taegeuk", size)
        if key not in self._cache:
            path = os.path.join(self.root, f"taegeuk_{size}.png")
            self._cache[key] = pygame.image.load(path).convert_alpha()
        return self._cache[key]

    def badge_center(self, size):
        """간판 안 호선 기호의 중심 (x, y) — 1배 기준. lg = (68, 40)"""
        return tuple(self.meta[size]["badge_center"])
