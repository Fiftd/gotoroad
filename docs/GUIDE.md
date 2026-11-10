# gotoroad 작성 가이드 (2단계부터)

SPEC.md가 "무엇을" 만들지 정한 문서라면, 이 문서는 "어떤 순서로, 어떻게 확인하며" 쓸지 정리한 문서다.
각 단계는 **작성할 것 → 핵심 포인트 → 확인 방법 → 완료 기준** 순서로 되어 있다.
코드 뼈대의 이름은 제안이므로, 바꿔도 된다. 바꾼 경우에는 SPEC에도 반영해 둔다.

- 이미 된 것(1단계): `game/config.py`, `game/save.py`, 자산 이전
- 원본 참고 위치: `D:\gago-road-draft` (읽기 전용)

---

## 공통 규칙

- **실행 위치:** 항상 `D:\gotoroad`에서 `py main.py` 또는 `py -m ...`로 실행한다. 그래야 `from game import config as C`가 동작한다.
- **import:** 원본처럼 `sys.path.insert`를 쓰지 말고 패키지 경로로 import한다(`from game.world.line import Line`).
- **파일 읽기:** JSON은 항상 `encoding="utf-8"`로 연다. 역 이름이 한글이기 때문이다.
- **pygame 이미지:** `convert_alpha()`는 `pygame.display.set_mode()`를 호출한 뒤에만 쓸 수 있다. 그래서 world 단계에서는 데이터만 읽고, 이미지는 render 단계에서 읽는다.
- **픽셀 유지:** 확대·축소는 `pygame.transform.scale`(nearest)을 쓴다. `smoothscale`은 쓰지 않는다.
- **폰트:** `assets/font/neodgm.ttf`는 크기가 16의 배수(16, 32, 48)일 때 가장 선명하다.
- **한 단계 = 한 번 실행 확인:** 단계마다 아래 "확인 방법"을 직접 돌려 보고 넘어간다.

---

## 2단계. 맵 데이터와 역 — `game/world/`, `game/stations/`

pygame 없이 동작하는 순수 데이터 계층이다. 여기서 틀리면 이후 단계가 모두 흔들리니 꼼꼼히 확인한다.

### 작성할 것

**`world/line.py`** — SPEC 6장 `line.py`, 원본 `Maps/game_map.py › Line`
```python
class Line:
    def __init__(self, d, line_type="main"):
        # d = data.json 의 lines[i]
        # 필드: id, name, color(문자열 "#RRGGBB" → (r,g,b) 튜플로 변환), segments, switches,
        #       available(=d["enabled"]), visible, type, short
    def neighbor_names(self, name): ...     # 순환 구간(closed) 처리 주의
    def next_options(self, cur, prev=None): ...
    def is_switch(self, name): return name in self.switches
```
- 색은 pygame 없이 쓸 수 있게 튜플로 둔다. 예: `tuple(int(h[i:i+2], 16) for i in (1, 3, 5))`

**`world/track.py`** — SPEC 6장 `track.py`, 원본 `S_StationPlay.py › Track`
```python
class Track:
    def __init__(self, pts, length_m=None): ...   # pts = [(x,y), ...] 맵 px
    def at(self, s_m): ...                        # → (x, y, angle)

def build_tracks(line, by_name):
    """line.segments[*].edges 로 {(a,b): Track, (b,a): Track} 를 만든다."""
```
- 점 목록 = `[A역 좌표] + edge["paths_px"]의 모든 점 + [B역 좌표]`
- `(b, a)` 방향은 점 순서를 뒤집어서 만든다.

**`stations/station.py`** — SPEC 7장
```python
class Station:
    RADIUS = 11
    def __init__(self, d):
        # name, gu, dong, line_ids(=d["lines"]), transfer, junction, switch, x, y(=d["map_px"]), label_spot
        # 플레이 상태: visited=False / 화면 상태: hover, selected, pulse
    def hit(self, wx, wy, zoom): ...
```

**역할 판정: `start_station.py` / `switch_station.py` / `interchange_station.py`**
SPEC 7장대로 상속 대신 **역할 함수**로 쓰기를 권한다. 한 역이 환승역이면서 갈림길일 수 있기 때문이다. 각 파일에 함수를 하나씩 둔다.
```python
# switch_station.py
def is_switch(station, line, prev=None):
    """이 호선에서 다음 후보가 2개 이상인가."""
    return len(line.next_options(station.name, prev)) > 1

# interchange_station.py
def transfer_lines(station, lines):
    """갈아탈 수 있는 호선 id 목록(데이터 순서). 2개 미만이면 []."""

# start_station.py
def start_station(line_id, by_name):
    """config.START_STATION 에서 출발역 Station 을 찾는다. 없으면 None."""
```
- 클래스로 나누고 싶다면 그것도 괜찮다. 다만 `map_data`가 역을 만들 때 어떤 클래스로 만들지 정해야 하고, 시작역은 플레이할 때마다 달라진다는 점을 고려해야 한다.

**`world/map_data.py`** — SPEC 6장
```python
class MapData:
    def __init__(self, path=C.MAP_DATA, types_path=C.LINE_TYPES):
        # W, H = data["map_px"]
        # tiles = data["tiles"]   (파일 이름만. 이미지는 render 에서 읽음)
        # lines = {id: Line}      (line_types.json 의 type 을 넣어서)
        # stations = [Station], by_name = {name: Station}
    def available_lines(self): ...   # enabled 인 호선만
```

### 핵심 포인트
- **순환선:** 2호선 본선이 `closed: true`이고 처음과 끝이 같은 역(시청…시청)이다. 끝 역을 하나 빼고 인덱스를 `% len`으로 돌린다.
- **갈림길:** `switches` 값의 순서는 "직진 우선"이다. 첫 번째 값이 기본 진행 방향이다.
- **같은 이름의 역:** 데이터에서 "신촌"(2호선)과 "신촌 경의중앙선"은 서로 다른 역이다. 역은 항상 이름으로 찾는다.

### 확인 방법
`D:\gotoroad`에서 실행한다.
```
py -c "from game.world.map_data import MapData; m=MapData(); print(len(m.stations), len(m.lines))"
```
→ `308 18`이 나와야 한다.

조금 더 자세한 확인은 `tests/check_world.py`로 만들어 두고 계속 돌려 본다.
```python
from game import config as C
from game.world.map_data import MapData
from game.world.track import build_tracks
from game.stations.interchange_station import transfer_lines

m = MapData()
L = m.lines
print(L["2"].neighbor_names("시청"))            # 2호선 순환(시청→…→시청, 43역): 을지로입구, 충정로
print(L["1"].next_options("구로", "신도림"))      # 1호선 갈림길: 구일, 가산디지털단지
print(transfer_lines(m.by_name["서울역"], L))    # ['1', '4', 'arex', 'gyeongui']
t = build_tracks(L["1"], m.by_name)[("서울역", "남영")]
print(round(t.length_m), t.at(0), t.at(t.length_m))  # 시작점 ≈ 서울역, 끝점 ≈ 남영
for lid, start in C.START_STATION.items():
    assert start is None or start in m.by_name, lid
print("OK")
```

### 완료 기준
- 위 확인이 모두 맞게 나온다.
- 원본 `game_map.py`의 `Line.next_options`와 같은 입력에 같은 결과가 나온다(몇 개 역을 골라 비교).

---

## 3단계. 앱과 메뉴 화면 — `game/app.py`, `game/scenes/`

맵 없이 화면만 오가는 단계다. 여기까지 되면 처음으로 "게임 창"이 뜬다.

### 작성할 것

**`app.py`** — SPEC 2장
```python
class App:
    def __init__(self):
        # pygame.init(), set_mode(C.WINDOW_SIZE, RESIZABLE), set_caption(C.TITLE)
        # self.font = lambda size: pygame.font.Font(C.FONT_PATH, size)
        # self.map = MapData(); self.profile = Profile(); self.settings = Settings()
        # self.scene = MainMenu(self)
    def go(self, scene): self.scene = scene
    def run(self):
        # while running: dt = min(clock.tick(C.FPS)/1000, C.DT_MAX)
        #   for e in events: QUIT → 종료 / 아니면 scene.handle(e)
        #   scene.update(dt); scene.draw(screen); pygame.display.flip()
```
`main.py`에서는 `from game.app import App; App().run()`만 한다.

**`scenes/base.py`** — Scene, Button (SPEC 5장 `base.py`)
- Scene 인터페이스: `handle(e)`, `update(dt)`, `draw(screen)`, `on_click(button)`, `on_escape()`
- 원본과 다른 점: `draw`가 `flip`을 하지 않는다(App이 한 번만 함). 화면 크기가 바뀔 수 있으니 레이아웃은 `draw`할 때마다 계산한다.

**작성 순서:** `main_menu.py` → `settings.py`(설정 › 지하철 하위 화면 포함) → `region_select.py` → `line_select.py`
- `line_select.py`는 아이콘 격자(SPEC 5장)라서 가장 손이 많이 간다.
  1. 처음에는 아이콘을 그냥 격자로 그리기만 한다.
  2. 다음에 상태 판정(준비 중 / 꺼짐 / 해금 / 미구매)을 넣는다.
  3. 구매 기능을 넣는다.
  4. 선택 연출(중앙으로 2배)은 마지막에 넣는다.
- 아이콘 격자 칸 계산 예시:
```python
ORDER = ["main", "city", "light", "trunk"]
rows = []   # [[lid, lid, None, None], ...]
for t in ORDER:
    ids = [lid for lid, _, _ in C.LINE_MENU if lines[lid].type == t]
    for i in range(0, len(ids), 4):
        rows.append((ids[i:i+4] + [None] * 4)[:4])   # 모자란 칸은 None(empty)
```
- 플레이 장면이 아직 없으니, 해금된 아이콘을 클릭하면 임시로 `print(line_id, start)`만 하거나 빈 장면으로 보낸다.

### 핵심 포인트
- 이미지(`line_icons/*.png`)는 `set_mode` 이후에 읽는다. App에서 한 번 읽어 dict로 들고 있으면 장면마다 다시 읽지 않아도 된다.
- 설정을 바꾸면 `Settings.toggle()`이 바로 저장하므로, 장면에서는 다시 그리기만 하면 된다.
- 지역 이름 표시는 행정구역이 꺼지면 비활성이다(`Settings.labels`가 이미 처리한다).

### 확인 방법
- `py main.py`로 실행해 메인 → 지하철 → 수도권 → 호선 선택, 설정 → 지하철 › 화면을 모두 오가 본다. ESC로 한 단계씩 뒤로 가는지 확인한다.
- `save.json`의 points를 손으로 1500으로 고친 뒤 5호선을 구매해 본다. 500이 남고, 다음 가격이 2000이 되어야 한다.
- 창 크기를 바꿔도 버튼과 격자가 가운데에 유지되는지 본다.

### 완료 기준
- 기획서 화면 흐름(SPEC 0장 그림)대로 모든 화면이 연결된다.
- 미구현 항목(버스, 기차, 대구·대전·부산권)은 회색이고 눌러도 반응하지 않는다.

---

## 4단계. 맵 보기 — `game/render/camera.py`, `game/render/map_renderer.py`

SPEC 추가 기능의 "게임 시작 전 맵 살펴보기"가 이 단계의 결과물이다. 플레이 없이 맵만 띄워 드래그와 확대로 둘러볼 수 있게 만든다.

### 작성할 것
**`camera.py`**
```python
class Camera:
    def __init__(self, map_w, map_h): self.zoom, self.ox, self.oy = 1.0, 0.0, 0.0
    def to_screen(self, x, y): ...
    def to_world(self, sx, sy): ...
    def fit(self, screen_size): ...                    # 서울 전체가 들어오게
    def focus(self, x, y, screen_size): ...
    def zoom_at(self, factor, sx, sy, lo, hi): ...     # 마우스 위치 기준 확대
    def follow(self, x, y, dt, screen_size, k=7): ...  # 플레이용(5단계)
```
- SPEC 추가 기능 기준으로, 살펴보기 모드의 최대 축소 범위 = `fit()`의 배율(서울 전경)이다.

**`map_renderer.py`** — 아래 순서로 조금씩 늘린다.
1. **타일만 그리기.** 화면 밖 타일은 건너뛴다. `(타일 세트, round(zoom, 3))`별로 확대 결과를 캐시한다.
2. **노선 그리기.** 처음에는 원본처럼 흰 테두리 + 색만 그린다. 그다음 SPEC의 "노선 종류별 그리기 A안"(겹쳐 그리기 표)으로 바꾼다.
3. **역 심볼.** 일반 역, 환승역(⇄), 갈림길 마름모
4. **역 이름과 배지.** 원본 `_place`가 가장 복잡하다. 처음에는 이름을 항상 역 위쪽에 두고, 동작을 확인한 뒤 자리 고르기를 옮긴다.

임시 확인용 장면으로 `scenes/map_view.py`(새 파일)를 만들면 편하다. 호선 선택이나 메인 메뉴에서 들어갈 수 있게 한다.

### 핵심 포인트
- **메모리:** 원본은 타일 세트 3종(46장씩)을 처음에 모두 읽었다. 1080×720 RGBA 한 장이 약 3MB라서 세 세트면 400MB가 넘는다. 지금 설정에 해당하는 세트만 읽고, 설정이 바뀔 때 다시 읽는 방식(지연 로딩)을 권한다.
- **성능:** 노선 경로와 경계 상자는 호선마다 한 번만 계산한다(원본 `_line_paths`). 화면 밖(여유 400px)의 노선과 역은 계산하지 않는다.
- **그리기 순서:** 타일 → 이름 → 흰 테두리(모든 호선) → 색(모든 호선) → 역 심볼. 순서를 바꾸면 한 호선의 테두리가 다른 호선을 가린다.
- **선 굵기:** 줌에 따라 `max(2, round(굵기 × zoom × 1.6))`

### 확인 방법
- 전경(fit)에서 시작해 드래그, 휠 확대, 최대 확대, 최대 축소를 해 본다. 타일 이음새에 틈이 보이면 위치를 `round`하고 크기는 `ceil`했는지 확인한다.
- 설정에서 행정구역과 지역 이름을 바꾸고 들어가면 타일 세트가 바뀌어야 한다.
- 2호선(순환), 1호선 구로 갈림길, 서울역(환승) 부근을 확대해서 원본 맵 화면(복사본에서 `py Maps/game_map.py`)과 비교한다.

### 완료 기준
- 원본 맵 화면과 같은 정보가 보이고, 끊김 없이 움직인다(60 FPS 근처).

---

## 5단계. 지하철 플레이 — `game/play/` → `scenes/subway_play.py` → `render/hud.py`

가장 큰 단계다. **규칙(play)과 그리기(render)를 섞지 않는 것**이 이번 리빌딩의 핵심이다.

### 작성할 것
**`play/session.py`** — 상태 기계(SPEC 8장 그림). pygame을 import하지 않는다.
```python
class Session:
    def __init__(self, map_data, line_id, profile, rng=random):
        # cur, prev, line_id, home_line_id, E, state, charge, charge_mult, speed_factor,
        # trk, s, target, pos, angle, opts, choice, tlines, visited(list+set), timer, mini
        # events = []   ← 화면 연출용 신호(아래 참고)
    # 입력(장면이 키를 해석해서 호출)
    def press_space(self): ...
    def release_space(self): ...
    def move_choice(self, d): ...
    def transfer(self, index): ...
    def mini_key(self, ch): ...
    # 진행
    def update(self, dt): getattr(self, "_t_" + self.state)(dt)
```
- `energy.py`, `train.py`, `minigame.py`로 나눈 부분은 Session이 부르는 함수나 작은 클래스로 만든다.
  - 예: `energy.charge_step(charge, dt)`, `MiniGame(rng)`
- **연출 신호:** Session은 그리지 않는다. 대신 `self.events.append(("crash", 역이름))`처럼 이벤트를 남긴다. 장면이 이를 꺼내 흔들림, 플래시, 불꽃, 토스트로 바꾼다. SPEC의 지진 효과(미니게임), 회전 효과(환승·종점)도 이 방식으로 붙이면 규칙 코드를 건드리지 않아도 된다.
- **랜덤:** `rng`를 인자로 받는다. 테스트에서 `random.Random(1)`을 넘기면 결과가 매번 같다.

**`scenes/subway_play.py`**
- 입력을 SPEC 5장 표의 순서대로 Session 메서드로 바꾼다.
- `update(dt)`: Session 진행 → 이벤트 처리 → 카메라 따라가기
- 카메라는 SPEC 추가 기능 기준으로 "진행 방향에 따라 이동"한다. 처음에는 원본처럼 열차를 중앙에 둔다. 그다음 진행 방향 앞쪽으로 조금 당겨 보이게(lookahead) 개선한다.

**`render/hud.py`** — 열차(이미지), 패널, 방향 칩, 환승 링, 충전 게이지, 미니게임 패널, 토스트

### 핵심 포인트
- **속도:** `C.speed_from_energy(E, speed_factor)`. 역을 떠날 때마다 `speed_factor = C.roll_speed_factor(rng)`를 뽑는다. 출발 경로는 두 군데다: SPACE를 뗄 때, 그리고 역에서 자동으로 떠날 때(`_leave_station`).
- **충전:** 바가 1000에 처음 닿는 순간 한 번만 `mult = C.roll_charge_bonus(rng)`를 뽑는다. 뗄 때 `E += C.charged_energy(charge, mult)`
- **충돌:** `E *= C.CRASH_SPEED_MULT`
- **이동:** `m = speed / 3.6 * dt * C.TIME_SCALE`, `E -= C.COST_PER_KM * m / 1000`
- **소진:** 속도가 `STOP_KMH` 미만이면 시작 호선, 시작역으로 돌아간다. 지나간 역 기록은 유지한다.
- **Point 저장 빈도:** 역에 도착할 때마다 `profile.add()`가 파일을 쓴다. 느리게 느껴지면 add는 메모리에서만 하고, 장면을 나갈 때 한 번 저장하도록 바꾼다.

### 확인 방법
1. **Session만 먼저 테스트한다**(화면 없이). `tests/check_session.py`
```python
import random
from game.world.map_data import MapData
from game.save import Profile
from game.play.session import Session

s = Session(MapData(), "1", Profile(None), rng=random.Random(1))
s.move_choice(-1)                      # 서울역에서 ← 방향(남영 쪽). 후보는 화면 x좌표 순서라 남영이 왼쪽
s.press_space()
for _ in range(200): s.update(1/60)    # 약 3.3초 충전 → MAX
s.release_space()
print(s.state, round(s.E), round(s.speed_factor, 2))
for _ in range(2000):
    s.update(1/60)
    if s.state != "run": print(s.state, s.cur); break
```
   → `run 1000~1300 0.5~0.8`이 나오고, 이어서 `crash 남영`이 나와야 한다.
2. 그다음 화면을 붙여 실제로 플레이한다. 확인할 장면:
   - 첫 도착 충돌
   - 재방문 미니게임(성공/실패)
   - 구로 갈림길
   - 서울역 환승(잠긴 호선 포함)
   - 에너지 소진 후 복귀
   - 종점에서 되돌아오기

### 완료 기준
- 원본에서 되던 플레이가 모두 된다.
- `play/` 폴더 안에 `import pygame`이 하나도 없다.

---

## 6단계. 기획서 추가 기능

SPEC 0장 "결정 필요" 표와 SPEC 끝의 "추가 기능", "네비게이션"을 하나씩 넣는다.
- **설정 항목:** 소리, 충격 on/off. 충격이 꺼지면 shake, flash, 불꽃을 생략한다.
- **연출:** 미니게임 약한 지진, 환승·종점 회전 효과(5단계의 이벤트 방식으로)
- **네비게이션:** 출발역과 도착역을 고르면 경로를 안내한다.
  - 역과 역 사이 이웃 관계(모든 호선)로 그래프를 만든다.
  - 가중치는 edge의 `length_m`, 환승할 때 벌점을 더한다.
  - 다익스트라로 경로를 구한다.
  - `world/` 아래에 `route.py`처럼 순수 함수로 두면 테스트하기 쉽다.

---

## 막혔을 때
- 원본 동작이 궁금하면 원본 폴더를 다른 곳에 **복사한 뒤** 그 복사본에서 `py main.py`를 실행해 비교한다. 원본 폴더에서 바로 실행하면 save.json, settings.json, `__pycache__`가 바뀌어 '읽기만' 원칙이 깨진다.
- 단계별 확인 스크립트(`tests/`)는 지우지 말고 남겨 둔다. 뒤 단계에서 앞 단계를 고쳤을 때 다시 돌려 보면 된다.
