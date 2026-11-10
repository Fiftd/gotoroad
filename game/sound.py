"""소리 — 효과음과 배경음악. 설정의 '소리'가 꺼져 있으면 아무것도 내지 않는다.

파일: assets/sound/{이름}.mp3. 오디오 장치가 없거나 파일이 없어도 게임은 계속된다(소리만 안 남).
"""
import os

import pygame

from game import config as C

EFFECTS = ("button_click", "reset", "on_off", "start", "qwer_sound", "crash",
           "error", "charging", "fail", "jump")
MUSIC = {"lobby": "play_bg_piexlfunk", "play": "lobby_bg"}   # 파일 이름이 서로 바뀌어 있어 반대로 연결


class Sound:
    def __init__(self, setting):
        self.setting = setting
        self.fx = {}
        self.loops = {}             # {이름: 반복 재생 중인 Channel}
        self.track = None           # 지금 고른 배경음악 이름("lobby"/"play")
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.ok = True
        except pygame.error:
            return
        for name in EFFECTS:
            try:
                self.fx[name] = pygame.mixer.Sound(os.path.join(C.SOUND_DIR, name + ".mp3"))
                self.fx[name].set_volume(C.SFX_VOLUME)
            except (pygame.error, FileNotFoundError):
                pass

    @property
    def on(self):
        return self.ok and self.setting["sound"]

    # ---------- 효과음 ----------
    def play(self, name):
        if self.on and name in self.fx:
            self.fx[name].play()

    def loop(self, name):
        """끌 때까지 반복(충전 소리). 이미 돌고 있으면 그대로."""
        if not self.on or name not in self.fx:
            return
        ch = self.loops.get(name)
        if ch and ch.get_busy():
            return
        self.loops[name] = self.fx[name].play(loops=-1)

    def stop(self, name):
        ch = self.loops.pop(name, None)
        if ch:
            ch.stop()

    # ---------- 배경음악 ----------
    def music(self, track):
        """장면이 바뀔 때 부름. 같은 곡이면 끊지 않고 이어서 튼다."""
        if track == self.track and (pygame.mixer.get_init() and pygame.mixer.music.get_busy() or not self.on):
            return
        self.track = track
        if not self.ok:
            return
        pygame.mixer.music.stop()
        if not self.on or track not in MUSIC:
            return
        try:
            pygame.mixer.music.load(os.path.join(C.SOUND_DIR, MUSIC[track] + ".mp3"))
            pygame.mixer.music.set_volume(C.MUSIC_VOLUME)
            pygame.mixer.music.play(-1)
        except pygame.error:
            pass

    def refresh(self):
        """설정에서 소리를 켜고 끈 직후: 끄면 전부 멈추고, 켜면 배경음악 다시."""
        if not self.ok:
            return
        if self.on:
            t, self.track = self.track, None
            self.music(t)
        else:
            pygame.mixer.music.stop()
            pygame.mixer.stop()
            self.loops.clear()
