#!/usr/bin/env python3
"""라벨을 얹은 화면 조각을 tiles-labeled/ 에 만든다. 사용: python3 tools/add-district-labels.py
입력: tiles.json, seoul-grid.json, tiles/ (gen-game-map.cjs 결과)
라벨: 구 이름(도트 글꼴, 40%) / 동 이름(15%, 각 동 안에 들어가도록 크기·줄바꿈 자동) / 한강(도트 글꼴)
출력: tiles-labeled/, labels.json (게임에서 글자를 직접 그릴 때 쓰는 위치·크기)
환경변수: GU_ALPHA(0.40) DONG_ALPHA(0.15) RIVER_ALPHA(0.45) GU_DOTS(15)"""

import json, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
T = json.load(open(f'{root}/tiles.json')); G = json.load(open(f'{root}/seoul-grid.json'))
GU_A = float(os.environ.get('GU_ALPHA', .40)); DONG_A = float(os.environ.get('DONG_ALPHA', .15)); RIV_A = float(os.environ.get('RIVER_ALPHA', .45))
GU_DOTS = int(os.environ.get('GU_DOTS', 15))
INK = (38, 54, 75); RIV_INK = (30, 78, 140)
DOT = T['dot_px']; cols, rows = G['cols'], G['rows']; SW, SH = T['screen_px']; MAPW, MAPH = T['map_px']
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-%s.ttc'
def font(weight, px): return ImageFont.truetype(FONT % weight, px, index=1)  # index 1 = KR

def unrle(rle, dtype):
    a = np.empty(cols * rows, dtype=dtype); p = 0
    for v, n in rle: a[p:p+n] = v; p += n
    return a.reshape(rows, cols)
cells = unrle(G['cells_rle'], np.int16); river = unrle(G['river_rle'], np.uint8).astype(bool)
land = (cells >= 0) & ~river
gu_of = np.array([d['gu'] for d in G['dongs']])

def integral(m): return np.pad(m.astype(np.int32).cumsum(0).cumsum(1), ((1, 0), (1, 0)))
def cover(ii, x0, y0, x1, y1):  # 박스 안 마스크 비율 (도트 좌표, 범위 밖이면 0)
    if x0 < 0 or y0 < 0 or x1 > ii.shape[1] - 1 or y1 > ii.shape[0] - 1: return 0.0
    return (ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]) / max(1, (x1 - x0) * (y1 - y0))

# ---------- 구 라벨(도트 글꼴) ----------
gu_mask = Image.new('L', (cols, rows), 0); gd = ImageDraw.Draw(gu_mask); f_gu = font('Bold', GU_DOTS)
gu_labels = []
for gu in sorted(set(gu_of)):
    sel = np.isin(cells, np.where(gu_of == gu)[0]) & ~river
    ys, xs = np.nonzero(sel); cx, cy = xs.mean(), ys.mean()
    if not sel[int(cy), int(cx)]:
        k = np.argmin((xs - cx) ** 2 + (ys - cy) ** 2); cx, cy = xs[k], ys[k]
    gu_labels.append({'name': gu, 'dot': [int(cx), int(cy)], 'map_px': [int(cx * DOT), int(cy * DOT)], 'size_px': GU_DOTS * DOT, 'alpha': GU_A})
    w = sum(f_gu.getlength(c) + 1 for c in gu) - 1; x = cx - w / 2
    for c in gu: gd.text((x, cy), c, font=f_gu, fill=255, anchor='lm'); x += f_gu.getlength(c) + 1
gu_big = np.kron(np.array(gu_mask) >= 110, np.ones((DOT, DOT), dtype=bool))

# ---------- 동 라벨(각 동 안에 맞춤) ----------
def split2(name):
    if len(name) <= 3: return None
    dots = [i for i, ch in enumerate(name) if ch == '·']
    if dots:
        k = min(dots, key=lambda i: abs(i + 1 - len(name) / 2)); return name[:k + 1] + '\n' + name[k + 1:]
    h = (len(name) + 1) // 2; return name[:h] + '\n' + name[h:]
fcache = {}
def F(px):
    if px not in fcache: fcache[px] = font('Medium', px)
    return fcache[px]
dummy = ImageDraw.Draw(Image.new('L', (4, 4)))
def box_dots(text, px):
    l, t, r, b = dummy.multiline_textbbox((0, 0), text, font=F(px), spacing=2, align='center')
    return (r - l) / DOT + 1.2, (b - t) / DOT + 1.2   # 여유 약 0.6도트씩
SIZES = list(range(24, 9, -1)); MIN_COVER = .94
dong_mask = Image.new('L', (MAPW, MAPH), 0); dd = ImageDraw.Draw(dong_mask)
dong_labels = []; tight = []
for d in G['dongs']:
    m = (cells == d['i']) & ~river
    ys, xs = np.nonzero(m)
    if len(xs) == 0: m = cells == d['i']; ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    sub = np.pad(m[y0:y1, x0:x1], 1); edt = distance_transform_edt(sub)[1:-1, 1:-1]; ii = integral(m[y0:y1, x0:x1])
    thr = edt.max() * .55; cy_, cx_ = np.nonzero(edt >= thr)
    order = np.argsort(-edt[cy_, cx_])[:: max(1, len(cy_) // 80)]
    cand = [(cx_[k], cy_[k]) for k in order]  # 크롭 좌표, 안쪽(edt 큰) 순
    name = d['name']; layouts = [name] + ([split2(name)] if split2(name) else [])
    best = {}
    for li, text in enumerate(layouts):
        for px in SIZES:
            w, h = box_dots(text, px); hit = None
            for (cx, cy) in cand:
                if cover(ii, int(round(cx - w / 2)), int(round(cy - h / 2)), int(round(cx + w / 2)), int(round(cy + h / 2))) >= MIN_COVER: hit = (cx, cy); break
            if hit: best[li] = (px, hit, text); break
    if 0 in best and (1 not in best or best[0][0] >= best[1][0] * .85): px, (cx, cy), text = best[0]
    elif 1 in best: px, (cx, cy), text = best[1]
    else:  # 어디에도 안 들어감: 가장 안쪽에 최소 크기로(이웃 동으로 약간 넘칠 수 있음)
        text = layouts[-1]; px = SIZES[-1]; k = np.argmax(edt); cy, cx = divmod(k, edt.shape[1]); tight.append(name)
    X, Y = (x0 + cx + .5) * DOT, (y0 + cy + .5) * DOT
    dd.multiline_text((X, Y), text, font=F(px), fill=255, anchor='mm', align='center', spacing=2)
    dong_labels.append({'name': name, 'gu': d['gu'], 'map_px': [int(X), int(Y)], 'size_px': px, 'lines': text.split('\n'), 'alpha': DONG_A})
dong_arr = np.array(dong_mask).astype(np.float32) / 255

# ---------- 한강 라벨(도트 글꼴, 강 안에 들어가는 자리) ----------
rv_mask = Image.new('L', (cols, rows), 0); rd = ImageDraw.Draw(rv_mask); f_rv = font('Bold', GU_DOTS); rv_ii = integral(river)
redt = distance_transform_edt(np.pad(river, 1))[1:-1, 1:-1]
ry, rx = np.nonzero(redt >= redt.max() * .6)
tw = f_rv.getlength('한강') + 1; river_labels = []
for q in (.2, .5, .82):
    tx = np.quantile(rx, q); ok = [(abs(x - tx), x, y) for x, y in zip(rx, ry)
          if cover(rv_ii, int(x - tw / 2 - 2), int(y - GU_DOTS / 2 - 2), int(x + tw / 2 + 2), int(y + GU_DOTS / 2 + 2)) >= .99]
    if not ok: continue
    _, x, y = min(ok); river_labels.append({'name': '한강', 'dot': [int(x), int(y)], 'map_px': [int(x * DOT), int(y * DOT)], 'size_px': GU_DOTS * DOT, 'alpha': RIV_A})
    xx = x - tw / 2
    for c in '한강': rd.text((xx, y), c, font=f_rv, fill=255, anchor='lm'); xx += f_rv.getlength(c) + 1
rv_big = np.kron(np.array(rv_mask) >= 110, np.ones((DOT, DOT), dtype=bool))

json.dump({'note': '라벨 위치(맵 픽셀)와 글자 크기(px). 게임에서 글자를 직접 그릴 때 사용. 알파는 기본 투명도.',
           'districts': gu_labels, 'dongs': dong_labels, 'river': river_labels},
          open(f'{root}/labels.json', 'w'), ensure_ascii=False, indent=1)

# ---------- 조각에 합성 ----------
os.makedirs(f'{root}/tiles-labeled', exist_ok=True)
for f in os.listdir(f'{root}/tiles-labeled'): os.remove(f'{root}/tiles-labeled/{f}')
def blend(im, a, ink):  # a: 픽셀별 알파(0~1)
    for i, ch in enumerate(ink): im[..., i] = im[..., i] * (1 - a) + ch * a
for t in T['tiles']:
    im = np.array(Image.open(f"{root}/{t['file']}").convert('RGBA')).astype(np.float32); seoul = im[..., 3] > 0
    ys, xs = slice(t['y'], t['y'] + SH), slice(t['x'], t['x'] + SW)
    blend(im, np.where(seoul, dong_arr[ys, xs] * DONG_A, 0), INK)
    blend(im, np.where(seoul & gu_big[ys, xs], GU_A, 0), INK)
    blend(im, np.where(seoul & rv_big[ys, xs], RIV_A, 0), RIV_INK)
    Image.fromarray(im.astype(np.uint8)).save(f"{root}/tiles-labeled/{os.path.basename(t['file'])}")
sizes = [l['size_px'] for l in dong_labels]
print(f"구 {len(gu_labels)}개({int(GU_A*100)}%) · 동 {len(dong_labels)}개({int(DONG_A*100)}%, 글자 {min(sizes)}~{max(sizes)}px, 2줄 {sum(len(l['lines'])>1 for l in dong_labels)}개) · 한강 {len(river_labels)}곳 · 조각 {len(T['tiles'])}개")
print('최소 크기로도 안 들어간 동:', ', '.join(tight) or '없음')
