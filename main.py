"""가고 싶은 길 — 실행 진입점.

실행: py main.py  (pip install pygame pillow 필요)
exe: build_exe.bat → dist/가고싶은길/가고싶은길.exe
"""
import os
import sys
import traceback


def main():
    from game.app import App
    App().run()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        if not getattr(sys, "frozen", False):
            raise
        # exe 는 콘솔 창이 없어서 오류가 안 보임 → exe 옆 error.log 에 남김
        with open(os.path.join(os.path.dirname(sys.executable), "error.log"), "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
