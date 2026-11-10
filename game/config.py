"""게임 수치(조정용 상수)와 에너지↔속도 변환.

원본: gago-road-draft/S_StationConfig.py (상수 이름·값은 docs/SPEC.md 3장 기준)
"""
import os
import random

# ---------------- 경로 ----------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
MAP_DIR = os.path.join(ASSETS, "map")
MAP_DATA = os.path.join(MAP_DIR, "data.json")
LINE_TYPES = os.path.join(MAP_DIR, "line_types.json")
LINE_ICONS = os.path.join(ASSETS, "ui", "line_icons")
TRAIN_SPRITES = os.path.join(ASSETS, "sprites", "trains")
STATION_SIGNS = os.path.join(ASSETS, "ui", "station_signs")
FONT_PATH = os.path.join(ASSETS, "font", "neodgm.ttf")
LOBBY_BG = os.path.join(MAP_DIR, "subway_bg_30s.gif")   # 로비 움직이는 배경
SOUND_DIR = os.path.join(ASSETS, "sound")
SFX_VOLUME = 0.7           # 효과음 크기(0~1)
MUSIC_VOLUME = 0.4         # 배경음악 크기(0~1)
SAVE_FILE = os.path.join(ROOT, "save.json")
SETTINGS_FILE = os.path.join(ROOT, "settings.json")

# ---------------- 창 ----------------
TITLE = "가고 싶은 길"
WINDOW_SIZE = (1280, 800)
FPS = 60
DT_MAX = 0.05               # 프레임이 끊겨도 한 번에 이보다 길게 진행하지 않는다(초)

# ------Font szie------
FONT_TITLE = 48
FONT_BUTTON = 32
FONT_SMALL = 16

# ---------------- 충전 ----------------
CHARGE_MAX = 1000.0                          # 충전 게이지 100% (J)
ENERGY_BAR_SPEED_UNIT = CHARGE_MAX / 1.5 / 1.5   # 바 속도 1.0 = 약 444 J/s
ENERGY_BAR_SPEED_FAST = 1.5                  # 700 J 까지의 바 속도
ENERGY_BAR_FAST_UNTIL = 700.0
ENERGY_BAR_DECREASE = 0.1                    # 700 J 이후 50 J 마다 바 속도 감소량
ENERGY_BAR_SPEED_MIN = 0.3
BONUS_MAX = 1.3                              # MAX 도달 시 ×1.0 ~ 1.3 랜덤 배율

# ---------------- 속도와 에너지 ----------------
SPEED_PER_J = 0.1           # 에너지 1 J 당 기본 속도(km/h)
SPEED_FACTOR_MIN = 0.5      # 출발할 때마다 0.5 ~ 0.8 사이에서 속도 계수를 뽑는다
SPEED_FACTOR_MAX = 0.8      #   → 1000 J = 50 ~ 80 km/h, 1300 J = 65 ~ 104 km/h
V_MAX = 150.0               # 최고 속도(상한) km/h
ENERGY_MIN = 10.0           # 이 이하의 에너지는 속도 0
COST_PER_KM = 60.0          # 1 km 당 소모 에너지
STOP_KMH = 5.0              # 이보다 느려지면 에너지 소진
TIME_SCALE = 200            # 화면 시간 배속(소모량은 실제 거리 기준)

# ---------------- 역 이벤트 ----------------
CRASH_SPEED_MULT = 0.75     # 처음 들어온 역에서 충돌 시 속도 배율
CRASH_TIME = 1.0            # 크래시 연출 전체 시간(초). 0.8 ~ 1.2 사이에서 조절(render/crash.py 의 T_BACK 과 같게)
CRASH_ZOOM = 2.5            # 크래시 클로즈업 배율(평소 배율 × 이 값)
STATION_BONUS_J = 200.0     # 미니게임 성공 보상
PICK_TIME = 1.5             # 갈림길·환승 선택 제한 시간(초)
MINI_KEYS_MIN, MINI_KEYS_MAX = 2, 4
MINI_TIME_BASE = 1.0        # 미니게임 제한 시간 = 기본 + 키 개수 × 키당 시간
MINI_TIME_PER_KEY = 0.8
MINI_ARM = 0.15             # 미니게임 시작 후 입력을 받기 시작하는 시간(초)
MINI_RESULT_TIME = 0.5      # 결과 표시 시간(초) — 끝나고 다시 출발하기까지
TRANSFER_KEYS = "qwerasdf"  # 환승(1~8번째 호선) / 미니게임 키


# ---------------- 카메라 ----------------
ZOOM = 0.9                  # 플레이 기본 확대
ZOOM_MIN, ZOOM_MAX = 0.5, 1.6   # 플레이 중 휠 확대 범위

# ---------------- 선택 연출 ----------------
RISE_TIME = 0.25            # 아이콘이 가운데로 떠오르는 시간
SIGN_HOLD = 0.3             # 출발역 간판을 보여 주는 시간
FLIP_TIME = 0.24            # 환승역 출발: 호선 기호가 삼태극으로 뒤집히는 시간
INTRO_ZOOM = 3.0            # 플레이 시작 직후 확대 배율(여기서 ZOOM 으로 줄어듦)
INTRO_TIME = 0.5            # 줌 아웃 시간
TRANSFER_ZOOM = 2.0         # 환승 선택 중 확대
LOOK_ZOOM_MAX = 2.5         # 맵 둘러보기 최대 확대(최대 축소는 서울 전경)

# ---------------- 6단계 연출 ----------------
SPIN_TIME = 0.4             # 환승·종점: 열차가 제자리에서 한 바퀴 도는 시간(초)
TURN_SPEED = 12.0           # 열차 그림이 진행 방향으로 돌아가는 빠르기(클수록 빨리)
QUAKE_AMP = 1.5             # 미니게임 중 약한 지진 세기(px)
QUAKE_MISS_AMP = 8.0        # 미니게임 실패 순간 흔들림 세기(px)
QUAKE_MISS_TIME = 0.3       # 실패 흔들림이 잦아드는 시간(초)

# ---------------- 로비 배경 ----------------
LOBBY_GRAY = (128, 128, 128)    # 배경 위에 덮는 회색 필터 색
LOBBY_DIM = 0.05                # 로비(메인·지역·호선 선택) 필터 투명도 5%
SETTINGS_DIM = 0.40             # 설정 화면 필터 투명도 40%
LOBBY_BAND = (226, 232, 236)    # 제목·버튼 뒤 세로 반투명 띠 색
LOBBY_BAND_ALPHA = 170         # 띠 투명도(0~255)
LOBBY_BAND_PAD = 0.10          # 띠 폭 = 버튼 폭 + 양옆 10%
ALERT_TIME = 1.0               # 가운데 알림(예: 초기화 완료) 표시 시간(초)
ALERT_DIM = 0.75               # 알림 뒤 검은 배경 투명도 75%
ALERT_BAND_ALPHA = 0.80        # 알림 가로 흰 띠 투명도
LOBBY_FALLBACK = (226, 232, 236)  # 배경 파일을 못 읽으면 이 색으로 채움

# ---------------- 네비게이션 ----------------
NAV_TRANSFER_COST = 1500.0  # 환승 1번을 이만큼(m)의 거리로 친다 → 클수록 환승을 피함
NAV_COLOR = (255, 0, 0)     # 경로 띠·목적지 핀 색
NAV_ALPHA = 255             # 경로 띠 투명도(255 = 불투명, 호선 위를 완전히 덮음)
M_PER_PX = 21.268 / 4       # 맵 1 px = 약 5.3 m

# ---------------- 노선 모양 ----------------
LINE_GEOMETRY = "straight"  # "straight": 역↔역 직선 / "curved": 원래 선로 곡선(가공 없음, 겹침 정리 미완) / "built": 원본 가공 곡선(paths_px)
LINE_PARALLEL = True        # 같은 두 역을 잇는 호선이 여럿이면 한 곡선을 기준으로 나란히 띄워 그림

# ---------------- 포인트 / 해금 ----------------
POINT_FIRST_STATION = 200
POINT_NORMAL_STATION = 20
UNLOCK_BASE_PRICE = 1000    # N번째 구매 가격 = 1000 × N
FREE_LINES = ("1", "2", "3", "4")
SAVE_VERSION = 2

# ---------------- 호선 메뉴 ----------------
# (id, 이름, 출발역). 색은 data.json 값을 쓴다. 출발역이 None 이면 "준비 중".
LINE_MENU = [
    ("1", "1호선", "서울역"),
    ("2", "2호선", "시청"),
    ("3", "3호선", "경복궁"),
    ("4", "4호선", "서울역"),
    ("5", "5호선", "광화문"),
    ("6", "6호선", "공덕"),
    ("7", "7호선", "건대입구"),
    ("8", "8호선", "잠실"),
    ("9", "9호선", "여의도"),
    ("arex", "공항철도", "서울역"),
    ("gyeongui", "경의중앙선", "용산"),
    ("gyeongchun", "경춘선", "청량리"),
    ("suinbundang", "수인분당선", "왕십리"),
    ("shinbundang", "신분당선", "강남"),
    ("sillim", "신림선", "보라매"),
    ("ui", "우이신설선", "신설동")
]
START_STATION = {lid: start for lid, _, start in LINE_MENU}

def roll_charge_bonus(rng=random):
    """에너지 바가 MAX(1000)에 닿을 때 한 번 뽑는 배율: 1.0 ~ 1.3 (0~30% 추가 에너지)."""
    return rng.uniform(1.0, BONUS_MAX)


def charged_energy(charge, mult=1.0):
    """충전량 → 얻는 에너지. MAX 미만이면 그대로, MAX 면 × 배율(1000 ~ 1300 J)."""
    charge = min(charge, CHARGE_MAX)
    return charge * mult if charge >= CHARGE_MAX else charge


def roll_speed_factor(rng=random):
    """역을 떠날 때마다 뽑는 속도 계수: 0.5 ~ 0.8."""
    return rng.uniform(SPEED_FACTOR_MIN, SPEED_FACTOR_MAX)


def speed_from_energy(e, factor):
    """에너지(J) → 속도(km/h) = e × 0.1 × 계수. 10 J 이하는 0, 상한 150."""
    if e <= ENERGY_MIN:
        return 0.0
    return min(V_MAX, e * SPEED_PER_J * factor)


def energy_bar_speed(charge):
    """충전량(J)에서의 바 속도: 700 J 까지 1.5, 이후 50 J 마다 0.1 감소(하한 0.3)."""
    if charge <= ENERGY_BAR_FAST_UNTIL:
        return ENERGY_BAR_SPEED_FAST
    return max(ENERGY_BAR_SPEED_MIN,
               ENERGY_BAR_SPEED_FAST - ENERGY_BAR_DECREASE * (charge - ENERGY_BAR_FAST_UNTIL) / 50.0)
