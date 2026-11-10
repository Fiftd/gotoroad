"""호선 아이콘·노선 종류 패턴 이미지 생성기 (개선 노선도 스타일, 픽셀).

실행: py tools/gen_line_assets.py      (pip install pillow)

입력
  assets/map/line_types.json   노선 종류와 호선별 종류·아이콘 글자
  assets/map/data.json         호선 색 (없으면 아래 FALLBACK_COLORS 사용)
  assets/font/neodgm.ttf       픽셀 폰트

출력
  assets/ui/line_icons/{id}.png          호선 아이콘 64×64 (구매함)
  assets/ui/line_icons/{id}_locked.png   회색 아이콘 (미구매 / 준비 중)
  assets/map/line_patterns/{type}.png    선 무늬 타일. 가로로 반복해서 선을 따라 찍는다.
                                         검정(0,0,0) = 호선 색으로 바꿀 자리, 흰색 = 흰색 그대로, 투명 = 비움
  assets/ui/line_types/{type}.png        범례용 선 견본 (종류 대표색, 160×28)
  docs/line_assets_preview.png           확인용 한 장 요약
"""
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = lambda *a: os.path.join(ROOT, *a)

FALLBACK_COLORS = {"1": "#0052A4", "2": "#00A84D", "3": "#EF7C1C", "4": "#29B6F6", "5": "#8E44AD", "6": "#8B4513",
                   "7": "#7F8C00", "8": "#E91E63", "9": "#B59A5B", "arex": "#00296B", "gyeongui": "#00C9A7",
                   "gyeongchun": "#0B7A75", "suinbundang": "#FFD600", "shinbundang": "#E53935", "sillim": "#7C8CF8",
                   "ui": "#B5CC18", "gimpo": "#AD8605", "seohae": "#8FC31F"}

ICON = 64
NUM_SIZE, NUM_SCALE = 32, 1.4   # 숫자(1~9) 글자 크기 = 32 × 1.4
KO_SIZE, KO_SCALE = 16, 1.2     # 한글 글자 크기 = 16 × 1.2
LOCK_FILL, LOCK_TEXT = (160, 164, 170), (228, 230, 233)
WHITE, COLOR, CLEAR = (255, 255, 255, 255), (0, 0, 0, 255), (0, 0, 0, 0)

# 선 무늬 정의 (세로 단면, 위→아래 행). 'W' 흰색, 'C' 호선 색, '.' 투명. 높이 = 흰 테두리 포함 전체 굵기.
# dash: (길이, 간격, 행 범위) — 이 행들은 길이만큼 흰색, 간격만큼 원래 무늬. 타일 폭 = 길이 + 간격.
PATTERNS = {
    "main":  {"rows": "WW" + "C" * 10 + "WW", "dash": None},              # 굵은 단색
    "city":  {"rows": "WW" + "CCC" + "WWWW" + "CCC" + "WW", "dash": None},  # 이중선
    "light": {"rows": "WW" + "CCCC" + "WW", "dash": None},                 # 가는 단색
    "trunk": {"rows": "WW" + "C" * 10 + "WW", "dash": (6, 6, (6, 8))},     # 굵은 선 + 흰 점선(철로)
}


def hex2rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def load_colors():
    try:
        with open(P("assets", "map", "data.json"), encoding="utf-8") as f:
            return {l["id"]: l["color"] for l in json.load(f)["lines"]}
    except OSError:
        return dict(FALLBACK_COLORS)


def font(size):
    return ImageFont.truetype(P("assets", "font", "neodgm.ttf"), size)


def text_size(fnt, s):
    x0, y0, x1, y1 = fnt.getbbox(s)
    return x1 - x0, y1 - y0, x0, y0


def make_icon(label, fill, text_col, shadow):
    im = Image.new("RGBA", (ICON, ICON), CLEAR)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"                                   # 안티에일리어싱 끔(픽셀 유지)
    d.ellipse((0, 0, ICON - 1, ICON - 1), fill=fill)
    lines = label.split("\n")
    is_num = len(lines) == 1 and label.isdigit()
    size = round(NUM_SIZE * NUM_SCALE) if is_num else round(KO_SIZE * KO_SCALE)
    fnt = font(size)
    # 글자를 따로 그린 뒤, 실제 잉크 영역(bbox)을 원 중앙에 맞춘다(가로·세로 모두)
    B = ICON * 2
    layer = Image.new("L", (B, B), 0)
    ld = ImageDraw.Draw(layer)
    ld.fontmode = "1"
    y = 0
    for ln in lines:
        w = ld.textlength(ln, font=fnt)
        ld.text(((B - w) // 2, y), ln, font=fnt, fill=255)
        y += size
    x0, y0, x1, y1 = layer.getbbox()
    ox = (ICON - (x1 - x0)) // 2 - x0
    oy = (ICON - (y1 - y0)) // 2 - y0
    if shadow:
        im.paste(Image.new("RGBA", (B, B), shadow), (ox + 1, oy + 1), layer)
    im.paste(Image.new("RGBA", (B, B), text_col), (ox, oy), layer)
    # 원 밖으로 나간 픽셀(그림자 포함)은 잘라 낸다
    mask = Image.new("L", (ICON, ICON), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, ICON - 1, ICON - 1), fill=255)
    im.putalpha(mask)
    return im


def make_pattern(spec):
    rows = spec["rows"]
    dash = spec["dash"]
    w = (dash[0] + dash[1]) if dash else 4
    im = Image.new("RGBA", (w, len(rows)), CLEAR)
    px = im.load()
    for y, ch in enumerate(rows):
        for x in range(w):
            c = {"W": WHITE, "C": COLOR, ".": CLEAR}[ch]
            if dash and dash[2][0] <= y < dash[2][1] and x < dash[0]:
                c = WHITE
            px[x, y] = c
    return im


# ---------------- 열차 ----------------
# 앞(진행 방향) = 오른쪽. 기본 픽셀 40×14 를 TRAIN_SCALE 배로 키워 저장한다.
# 바탕(trains/base.png)의 색 키: 검정(0,0,0)=호선 색, (64,0,64)=호선 색의 어두운 톤(×0.55), (160,0,160)=밝은 톤
TRAIN_SCALE = 2
BODY, DARK, LIGHT = (0, 0, 0, 255), (64, 0, 64, 255), (160, 0, 160, 255)
TRAIN_ART = [
    # 0         1         2         3
    # 0123456789012345678901234567890123456789
    "..WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW...",  # 0
    ".WDLLLLLLLLLLLLLLLLLDLLLLLLLLLLLLLLLLWW.",  # 1
    "WDBBBBBBBBBBBBBBBBBBDBBBBBBBBBBBBBBBBBW.",  # 2
    "WDBBGGGBBGGGBBGGGBBBDBBGGGBBGGGBBGGGBKYW",  # 3
    "WDBBGGGBBGGGBBGGGBBBDBBGGGBBGGGBBGGGBKKW",  # 4
    "WDBBGGGBBGGGBBGGGBBBDBBGGGBBGGGBBGGGBKKW",  # 5
    "WDBBBBBBBBBBBBBBBBBBDBBBBBBBBBBBBBBBBKKW",  # 6
    "WDBBBBBBBBBBBBBBBBBBDBBBBBBBBBBBBBBBBKKW",  # 7
    "WDBWWWWWWWWWWWWWWWWBDBWWWWWWWWWWWWWWWBKW",  # 8
    "WDBBBBBBBBBBBBBBBBBBDBBBBBBBBBBBBBBBBBYW",  # 9
    "WDBBBBBBBBBBBBBBBBBBDBBBBBBBBBBBBBBBBBYW",  # 10
    "WDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDW.",  # 11
    ".WWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWWW..",  # 12
]
TRAIN_KEYS = {".": CLEAR, "W": WHITE, "B": BODY, "D": DARK, "L": LIGHT,
              "G": (214, 238, 255, 255), "K": (40, 48, 60, 255), "Y": (255, 236, 120, 255)}


def make_train_base():
    h, w = len(TRAIN_ART), len(TRAIN_ART[0])
    im = Image.new("RGBA", (w, h), CLEAR)
    px = im.load()
    for y, row in enumerate(TRAIN_ART):
        assert len(row) == w, (y, len(row))
        for x, ch in enumerate(row):
            px[x, y] = TRAIN_KEYS[ch]
    return im.resize((w * TRAIN_SCALE, h * TRAIN_SCALE), Image.NEAREST)


def color_train(base, rgb):
    """바탕 열차에 호선 색을 입힌다. 게임에서 직접 칠할 때도 같은 규칙을 쓰면 된다."""
    dark = tuple(int(c * 0.55) for c in rgb)
    light = tuple(min(255, int(c + (255 - c) * 0.35)) for c in rgb)
    t = base.copy()
    px = t.load()
    for y in range(t.height):
        for x in range(t.width):
            p = px[x, y]
            if p == BODY:
                px[x, y] = (*rgb, 255)
            elif p == DARK:
                px[x, y] = (*dark, 255)
            elif p == LIGHT:
                px[x, y] = (*light, 255)
    return t


def tint(tile, rgb):
    t = tile.copy()
    px = t.load()
    for y in range(t.height):
        for x in range(t.width):
            if px[x, y] == COLOR:
                px[x, y] = (*rgb, 255)
    return t


def strip(tile, rgb, length):
    t = tint(tile, rgb)
    im = Image.new("RGBA", (length, t.height), CLEAR)
    for x in range(0, length, t.width):
        im.paste(t, (x, 0))
    return im


def make_trains(cfg, colors, icons):
    out = P("assets", "sprites", "trains")
    os.makedirs(out, exist_ok=True)
    base = make_train_base()
    base.save(os.path.join(out, "base.png"))
    trains = {}
    for lid in cfg["lines"]:
        rgb = hex2rgb(colors.get(lid, FALLBACK_COLORS[lid]))
        t = color_train(base, rgb)
        t.save(os.path.join(out, f"{lid}.png"))
        trains[lid] = t
    # 확인용: 아이콘 + 열차, 2열
    ids = list(cfg["lines"])
    cw, ch = 32 + 8 + base.width + 24, 40
    rows = (len(ids) + 1) // 2
    pv = Image.new("RGBA", (16 + 2 * cw, 16 + rows * ch + 120), (226, 232, 236, 255))
    for i, lid in enumerate(ids):
        x, y = 16 + (i % 2) * cw, 12 + (i // 2) * ch
        ic = icons[lid][0].resize((32, 32), Image.NEAREST)
        pv.paste(ic, (x, y), ic)
        pv.paste(trains[lid], (x + 40, y + 16 - base.height // 2), trains[lid])
    y = 16 + rows * ch
    d = ImageDraw.Draw(pv)
    d.fontmode = "1"
    d.text((16, y + 4), "바탕(base) / 회전 예시", font=font(16), fill=(30, 34, 40))
    pv.paste(base, (16, y + 28), base)
    for k, ang in enumerate((-45, 90)):
        r = trains["2"].rotate(ang, resample=Image.NEAREST, expand=True)
        pv.paste(r, (36 + base.width + k * 90, y + 28), r)
    pv = pv.resize((pv.width * 2, pv.height * 2), Image.NEAREST)
    pv.save(P("docs", "train_preview.png"))


# ---------------- 역 간판 ----------------
# 서울 지하철 역 간판 스타일(호선 색 테두리 알약 + 왼쪽 호선 기호 + 역명)을 픽셀로.
#   lg: 호선 아이콘(64)을 그대로 기호로 씀. 선택 연출·첫 도착 강조용. 양옆에 호선 색 띠(선로).
#   sm: 높이 24. 지도 위 역 이름 자리용. 띠 없음.
SHORT = {"arex": "공", "gyeongui": "경", "gyeongchun": "춘", "suinbundang": "분", "shinbundang": "신",
         "sillim": "림", "ui": "우", "gimpo": "김", "seohae": "서"}
SIGN_LG = {"h": 80, "border": 6, "bar_len": 28, "bar_h": 24, "pad": 2, "gap": 14, "right": 22}
SIGN_SM = {"h": 24, "border": 2, "badge": 18, "pad": 1, "gap": 4, "right": 7}


def display_name(name):
    """'신촌 경의중앙선' → '신촌' (같은 이름 역을 구분하려고 붙인 꼬리는 간판에 안 씀)."""
    return name.split(" ")[0]


def make_sign_lg(name, line_name, rgb, icon):
    S = SIGN_LG
    H, B = S["h"], S["border"]
    f_name, f_sub = font(32), font(16)
    text = display_name(name)
    tw = max(int(f_name.getlength(text)), int(f_sub.getlength(line_name)))
    pill_w = B + S["pad"] + ICON + S["gap"] + tw + S["right"] + B
    W = S["bar_len"] * 2 + pill_w
    im = Image.new("RGBA", (W, H), CLEAR)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    bar = tuple(int(c * 0.78) for c in rgb)
    d.rectangle((0, (H - S["bar_h"]) // 2, W - 1, (H + S["bar_h"]) // 2 - 1), fill=bar)   # 선로 띠
    x0, x1 = S["bar_len"], S["bar_len"] + pill_w - 1
    d.rounded_rectangle((x0, 0, x1, H - 1), radius=H // 2, fill=rgb)                      # 테두리
    d.rounded_rectangle((x0 + B, B, x1 - B, H - 1 - B), radius=H // 2 - B, fill=(255, 255, 255))
    bx = x0 + B + S["pad"]
    im.paste(icon, (bx, (H - ICON) // 2), icon)                                         # 호선 기호
    tx = bx + ICON + S["gap"]
    nh, sh_ = 32, 16
    ty = (H - (nh + 4 + sh_)) // 2
    d.text((tx + (tw - f_name.getlength(text)) // 2, ty), text, font=f_name, fill=(17, 17, 17))
    d.text((tx + (tw - f_sub.getlength(line_name)) // 2, ty + nh + 4), line_name, font=f_sub, fill=(120, 124, 130))
    return im, (bx + ICON // 2, H // 2)


def make_sign_sm(name, lid, label, rgb):
    S = SIGN_SM
    H, B, D_ = S["h"], S["border"], S["badge"]
    f = font(16)
    text = display_name(name)
    tw = int(f.getlength(text))
    W = B + S["pad"] + D_ + S["gap"] + tw + S["right"] + B
    im = Image.new("RGBA", (W, H), CLEAR)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=H // 2, fill=rgb)
    d.rounded_rectangle((B, B, W - 1 - B, H - 1 - B), radius=H // 2 - B, fill=(255, 255, 255))
    bx, by = B + S["pad"], (H - D_) // 2
    d.ellipse((bx, by, bx + D_ - 1, by + D_ - 1), fill=rgb)
    ch = label if label.isdigit() else SHORT.get(lid, lid[:1])
    layer = Image.new("L", (D_ * 2, D_ * 2), 0)                  # 기호 글자를 원 중앙에 정확히
    ld = ImageDraw.Draw(layer)
    ld.fontmode = "1"
    ld.text((0, 0), ch, font=f, fill=255)
    gx0, gy0, gx1, gy1 = layer.getbbox()
    ox = bx + (D_ - (gx1 - gx0)) // 2 - gx0
    oy = by + (D_ - (gy1 - gy0)) // 2 - gy0
    im.paste(Image.new("RGBA", layer.size, (255, 255, 255, 255)), (ox, oy), layer)
    tx = bx + D_ + S["gap"]
    gb = f.getbbox(text)
    d.text((tx, (H - (gb[3] - gb[1])) // 2 - gb[1]), text, font=f, fill=(17, 17, 17))
    return im, (bx + D_ // 2, by + D_ // 2)


# ---------------- 환승역 간판 ----------------
# 환승역: 호선 기호 자리에 삼태극(빨강·노랑·파랑), 테두리는 검정. 큰 간판 아래에는 지나는 호선 기호를 작게 나열.
TG_RED, TG_YEL, TG_BLU = (205, 46, 58), (255, 194, 32), (0, 71, 160)
SIGN_BLACK = (17, 17, 17)
SIGN_BAR_BLACK = (52, 52, 56)


def make_taegeuk(d, swirl, rot):
    """지름 d 픽셀의 삼태극. 빨강 위·노랑 오른쪽·파랑 왼쪽 아래가 되도록 rot 로 돌린다."""
    im = Image.new("RGBA", (d, d), CLEAR)
    px = im.load()
    c, R = (d - 1) / 2, d / 2
    for y in range(d):
        for x in range(d):
            r = math.hypot(x - c, y - c)
            if r > R - 0.5:
                continue
            th = math.atan2(y - c, x - c) - swirl * (r / R) + rot
            k = int(((th % math.tau) / math.tau) * 3) % 3
            px[x, y] = (*(TG_RED, TG_YEL, TG_BLU)[k], 255)
    return im


def draw_mini_badge(im, x, y, d, lid, label, rgb):
    """지름 d 의 호선 기호(원 + 흰 글자 한 자)를 im 의 (x, y)에 그린다."""
    dr = ImageDraw.Draw(im)
    dr.ellipse((x, y, x + d - 1, y + d - 1), fill=rgb)
    ch = label if label.isdigit() else SHORT.get(lid, lid[:1])
    f = font(16)
    layer = Image.new("L", (d * 2, d * 2), 0)
    ld = ImageDraw.Draw(layer)
    ld.fontmode = "1"
    ld.text((0, 0), ch, font=f, fill=255)
    gx0, gy0, gx1, gy1 = layer.getbbox()
    im.paste(Image.new("RGBA", layer.size, (255, 255, 255, 255)),
             (x + (d - (gx1 - gx0)) // 2 - gx0, y + (d - (gy1 - gy0)) // 2 - gy0), layer)


def make_sign_lg_transfer(name, line_list, tg):
    """line_list = [(lid, label, rgb), ...] — 이 역을 지나는 운행 호선."""
    S = SIGN_LG
    H, B = S["h"], S["border"]
    f_name = font(32)
    text = display_name(name)
    md, mg = 18, 3
    row_w = len(line_list) * md + (len(line_list) - 1) * mg
    tw = max(int(f_name.getlength(text)), row_w)
    pill_w = B + S["pad"] + ICON + S["gap"] + tw + S["right"] + B
    W = S["bar_len"] * 2 + pill_w
    im = Image.new("RGBA", (W, H), CLEAR)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.rectangle((0, (H - S["bar_h"]) // 2, W - 1, (H + S["bar_h"]) // 2 - 1), fill=SIGN_BAR_BLACK)
    x0, x1 = S["bar_len"], S["bar_len"] + pill_w - 1
    d.rounded_rectangle((x0, 0, x1, H - 1), radius=H // 2, fill=SIGN_BLACK)
    d.rounded_rectangle((x0 + B, B, x1 - B, H - 1 - B), radius=H // 2 - B, fill=(255, 255, 255))
    bx = x0 + B + S["pad"]
    im.paste(tg, (bx, (H - ICON) // 2), tg)
    tx = bx + ICON + S["gap"]
    ty = (H - (32 + 4 + md)) // 2
    d.text((tx + (tw - f_name.getlength(text)) // 2, ty), text, font=f_name, fill=(17, 17, 17))
    rx = tx + (tw - row_w) // 2
    for lid, label, rgb in line_list:
        draw_mini_badge(im, rx, ty + 32 + 4, md, lid, label, rgb)
        rx += md + mg
    return im, (bx + ICON // 2, H // 2)


def make_sign_sm_transfer(name, tg):
    S = SIGN_SM
    H, B, D_ = S["h"], S["border"], S["badge"]
    f = font(16)
    text = display_name(name)
    W = B + S["pad"] + D_ + S["gap"] + int(f.getlength(text)) + S["right"] + B
    im = Image.new("RGBA", (W, H), CLEAR)
    d = ImageDraw.Draw(im)
    d.fontmode = "1"
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=H // 2, fill=SIGN_BLACK)
    d.rounded_rectangle((B, B, W - 1 - B, H - 1 - B), radius=H // 2 - B, fill=(255, 255, 255))
    bx, by = B + S["pad"], (H - D_) // 2
    im.paste(tg, (bx, by), tg)
    gb = f.getbbox(text)
    d.text((bx + D_ + S["gap"], (H - (gb[3] - gb[1])) // 2 - gb[1]), text, font=f, fill=(17, 17, 17))
    return im, (bx + D_ // 2, by + D_ // 2)


def make_transfer_signs(cfg, colors, D):
    """운행 호선이 2개 이상인 역 → station_signs/{lg,sm}/transfer/{역}.png"""
    enabled = {l["id"] for l in D["lines"] if l["enabled"]}
    tg_lg = make_taegeuk(ICON, 2.2, 4.82)
    tg_sm = make_taegeuk(SIGN_SM["badge"], 1.6, 4.22)
    os.makedirs(P("assets", "ui", "station_signs"), exist_ok=True)
    tg_lg.save(P("assets", "ui", "station_signs", "taegeuk_lg.png"))     # 선택 연출(① → 삼태극)용
    tg_sm.save(P("assets", "ui", "station_signs", "taegeuk_sm.png"))
    for size in ("lg", "sm"):
        os.makedirs(P("assets", "ui", "station_signs", size, "transfer"), exist_ok=True)
    out = {}
    for st in D["stations"]:
        ids = [i for i in st["lines"] if i in enabled]
        if len(ids) < 2:
            continue
        line_list = [(i, cfg["lines"][i]["label"], hex2rgb(colors.get(i, FALLBACK_COLORS[i]))) for i in ids]
        lg, _ = make_sign_lg_transfer(st["name"], line_list, tg_lg)
        sm, _ = make_sign_sm_transfer(st["name"], tg_sm)
        lg.save(P("assets", "ui", "station_signs", "lg", "transfer", f"{st['name']}.png"))
        sm.save(P("assets", "ui", "station_signs", "sm", "transfer", f"{st['name']}.png"))
        out[st["name"]] = (lg, sm, ids)
    return out


def make_signs(cfg, colors, icons):
    try:
        with open(P("assets", "map", "data.json"), encoding="utf-8") as f:
            D = json.load(f)
    except OSError:
        print("data.json 없음 — 역 간판은 건너뜀")
        return
    names = {l["id"]: l["name"] for l in D["lines"]}
    meta = {"lg": None, "sm": None, "lines": {}}
    samples = {}
    for l in D["lines"]:
        lid = l["id"]
        rgb = hex2rgb(colors.get(lid, FALLBACK_COLORS[lid]))
        label = cfg["lines"][lid]["label"]
        stations = []
        for seg in l["segments"]:
            for n in seg["stations"]:
                if n not in stations:
                    stations.append(n)
        for size in ("lg", "sm"):
            os.makedirs(P("assets", "ui", "station_signs", size, lid), exist_ok=True)
        for n in stations:
            lg, lg_c = make_sign_lg(n, names[lid], rgb, icons[lid][0])
            sm, sm_c = make_sign_sm(n, lid, label, rgb)
            lg.save(P("assets", "ui", "station_signs", "lg", lid, f"{n}.png"))
            sm.save(P("assets", "ui", "station_signs", "sm", lid, f"{n}.png"))
            meta["lg"] = {"badge_center": list(lg_c), "badge_size": ICON, "h": lg.height}
            meta["sm"] = {"badge_center": list(sm_c), "badge_size": SIGN_SM["badge"], "h": sm.height}
            samples[(lid, n)] = (lg, sm)
        meta["lines"][lid] = stations
    transfers = make_transfer_signs(cfg, colors, D)
    meta["transfer"] = {n: ids for n, (_, _, ids) in transfers.items()}    # {환승역: [운행 호선]}
    with open(P("assets", "ui", "station_signs", "signs.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)

    # 확인용
    pick_lg = [("1", "서울역"), ("2", "시청"), ("arex", "서울역"), ("gyeongui", "신촌 경의중앙선"),
               ("suinbundang", "왕십리"), ("sillim", "보라매"), ("9", "여의도"), ("ui", "신설동")]
    pick_sm = [(lid, n) for lid in ("1", "4", "shinbundang", "gyeongchun", "ui") for n in meta["lines"][lid][:4]]
    rows_lg = [samples[k][0] for k in pick_lg if k in samples]
    W = max(max(i.width for i in rows_lg) * 2 + 48, 900)
    H = 20 + sum(rows_lg[i].height + 10 for i in range(0, len(rows_lg), 2)) + 30 + 6 * 32 + 30 + 200 + 160
    pv = Image.new("RGBA", (W, H), (226, 232, 236, 255))
    d = ImageDraw.Draw(pv)
    d.fontmode = "1"
    y = 12
    for i, im in enumerate(rows_lg):
        x = 16 + (i % 2) * (W // 2)
        pv.paste(im, (x, y), im)
        if i % 2:
            y += im.height + 10
    y += 14
    d.text((16, y), "sm (지도 위 역 이름)", font=font(16), fill=(30, 34, 40)); y += 26
    x, row_h = 16, 32
    for k in pick_sm:
        im = samples[k][1]
        if x + im.width > W - 16:
            x, y = 16, y + row_h
        pv.paste(im, (x, y), im)
        x += im.width + 10
    y += row_h + 16
    d.text((16, y), "선택 연출: 아이콘 x2 (128) -> 간판 lg x2 (기호 128)", font=font(16), fill=(30, 34, 40)); y += 24
    ic = icons["1"][0].resize((128, 128), Image.NEAREST)
    pv.paste(ic, (16, y), ic)
    big = samples[("1", "서울역")][0]
    big = big.resize((big.width * 2, big.height * 2), Image.NEAREST)
    pv.paste(big, (170, y), big)
    y += 175
    d.text((16, y), "환승역 (삼태극 + 검은 테두리)", font=font(16), fill=(30, 34, 40)); y += 24
    x = 16
    for n in ("서울역", "김포공항", "왕십리"):
        if n in transfers:
            lg = transfers[n][0]
            pv.paste(lg, (x, y), lg)
            x += lg.width + 16
    y += 90
    x = 16
    for n in ("서울역", "김포공항", "왕십리", "신도림", "종로3가", "고속터미널"):
        if n in transfers:
            sm = transfers[n][1]
            pv.paste(sm, (x, y), sm)
            x += sm.width + 10
    pv = pv.crop((0, 0, W, y + 34))
    pv.save(P("docs", "sign_preview.png"))
    print("signs:", len(samples), "pairs,", len(transfers), "transfer stations")


def main():
    with open(P("assets", "map", "line_types.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    colors = load_colors()
    for d in ("assets/ui/line_icons", "assets/map/line_patterns", "assets/ui/line_types"):
        os.makedirs(P(*d.split("/")), exist_ok=True)

    icons = {}
    for lid, info in cfg["lines"].items():
        rgb = hex2rgb(colors.get(lid, FALLBACK_COLORS[lid]))
        dark = tuple(int(c * 0.55) for c in rgb)
        on = make_icon(info["label"], rgb, (255, 255, 255), dark)
        off = make_icon(info["label"], LOCK_FILL, LOCK_TEXT, None)
        on.save(P("assets", "ui", "line_icons", f"{lid}.png"))
        off.save(P("assets", "ui", "line_icons", f"{lid}_locked.png"))
        icons[lid] = (on, off)

    tiles = {}
    for tid, t in cfg["types"].items():
        tile = make_pattern(PATTERNS[t["pattern"]])
        tile.save(P("assets", "map", "line_patterns", f"{tid}.png"))
        tiles[tid] = tile
        sw = strip(tile, hex2rgb(t["legend_color"]), 160)
        legend = Image.new("RGBA", (160, 28), CLEAR)
        legend.paste(sw, (0, (28 - sw.height) // 2), sw)
        legend.save(P("assets", "ui", "line_types", f"{tid}.png"))

    # ---- 확인용 요약 ----
    S = 2
    W = 4 * (ICON + 16) + 16
    groups = [(tid, t, [l for l, i in cfg["lines"].items() if i["type"] == tid]) for tid, t in cfg["types"].items()]
    H = 24 + sum(28 + ((len(ls) + 3) // 4) * (ICON + 12) for _, _, ls in groups) + 30 + 34 * len(groups) + 16 + ICON + 40
    pv = Image.new("RGBA", (W, H), (226, 232, 236, 255))
    d = ImageDraw.Draw(pv)
    d.fontmode = "1"
    f16 = font(16)
    y = 12
    for tid, t, ls in groups:
        d.text((16, y), t["name"], font=f16, fill=(30, 34, 40)); y += 28
        for i, lid in enumerate(ls):
            pv.paste(icons[lid][0], (16 + (i % 4) * (ICON + 16), y + (i // 4) * (ICON + 12)), icons[lid][0])
        y += ((len(ls) + 3) // 4) * (ICON + 12)
    y += 6
    d.text((16, y), "노선 종류 (지도 선 무늬)", font=f16, fill=(30, 34, 40)); y += 26
    for tid, t in cfg["types"].items():
        d.text((16, y + 6), t["name"], font=f16, fill=(30, 34, 40))
        sw = strip(tiles[tid], hex2rgb(t["legend_color"]), W - 140)
        sw = sw.resize((sw.width, sw.height * S // S), Image.NEAREST)
        pv.paste(sw, (120, y + (28 - sw.height) // 2), sw)
        y += 34
    y += 6
    d.text((16, y), "미구매", font=f16, fill=(30, 34, 40))
    pv.paste(icons["5"][1], (96, y - 4), icons["5"][1])
    pv.paste(icons["arex"][1], (96 + ICON + 16, y - 4), icons["arex"][1])
    pv = pv.crop((0, 0, W, y + ICON + 8))
    make_trains(cfg, colors, icons)
    make_signs(cfg, colors, icons)
    pv = pv.resize((pv.width * S, pv.height * S), Image.NEAREST)
    os.makedirs(P("docs"), exist_ok=True)
    pv.save(P("docs", "line_assets_preview.png"))
    print("done:", len(icons), "icons,", len(tiles), "patterns")


if __name__ == "__main__":
    main()
