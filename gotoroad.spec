# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 설정 — build_exe.bat 이 이 파일로 빌드한다.
# 결과: dist/가고싶은길/가고싶은길.exe (+ _internal/ 안에 assets). 폴더째 압축해서 나눠 주면 된다.
import os

NAME = "가고싶은길"
ROOT = os.path.abspath(SPECPATH)

# 게임에 필요 없는 것(선 무늬·범례 견본 — 생성기가 만들지만 게임은 안 씀)은 뺀다
SKIP_DIRS = {os.path.join("assets", "map", "line_patterns"), os.path.join("assets", "ui", "line_types")}
SKIP_FILES = set()
SKIP_NAMES = set()

datas = []
for dp, dirs, files in os.walk(os.path.join(ROOT, "assets")):
    rel = os.path.relpath(dp, ROOT)
    dirs[:] = [d for d in dirs if os.path.join(rel, d) not in SKIP_DIRS and d != "__pycache__"]
    for f in files:
        if f in SKIP_NAMES or os.path.join(rel, f) in SKIP_FILES:
            continue
        datas.append((os.path.join(dp, f), rel))

a = Analysis(
    ["main.py"],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=["PIL.Image", "PIL.GifImagePlugin"],   # 로비 GIF 배경(game/render/lobby_bg.py 안에서 import)
    excludes=["tkinter", "numpy", "scipy", "matplotlib"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    console=False,              # 검은 콘솔 창 없이. 오류는 exe 옆 error.log
    icon=os.path.join(ROOT, "assets", "ui", "app.ico") if os.path.exists(os.path.join(ROOT, "assets", "ui", "app.ico")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME)
