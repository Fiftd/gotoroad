# 가보는 지하철 — 게임용 맵

서울 안쪽만 표현. 종단역은 다루지 않음. 재생성: `node tools/gen-game-map.cjs` (이 폴더에서, 외부 패키지 없음)

## 규격
- 화면 1080×720 × 8×8개 = 전체 맵 8640×5760 픽셀
- 도트 1개 = 화면 4픽셀 = 실제 약 21.3m → 도트 격자 2160×1440
- 서울이 걸친 화면 조각 46개(나머지 18개는 서울 밖이라 만들지 않음). 한 화면 ≈ 5.7×3.8km

## 파일
| 파일 | 내용 |
|---|---|
| `tiles/t{열}_{행}.png` | 1080×720 화면 조각(46개). 왼쪽 위 = (열×1080, 행×720) |
| `tiles.json` | 조각 목록·좌표 변환 정보 |
| `seoul-dong-map.png` | 전체 도트 지도(2160×1440, 1도트=1픽셀, 서울 밖 투명) |
| `seoul-grid.json` | 도트마다 동 번호(RLE). 그림과 같은 해상도라 판정이 어긋나지 않음 |
| `lines/line1.json` | 1호선 단선 중심선(본선, 구로→온수, 구로→금천구청). `points`(미터), `points_px`(맵 픽셀) |
| `network.json` | 역 목록: `transfer`(환승), `junction`(분기점), `map_px`, 소속 동·구 |
| `lines.config.json` | 맵 규격, 팔레트, 호선별 색·구간·`enabled` |
| `preview-full.png`, `preview-screen-seoulstation.png` | 확인용(선로·역 합성) |

좌표: 서울시청 기준 미터(x 동쪽, y 남쪽). `map_px = (좌표_m − origin_m) / m_per_dot × dot_px`.
선로와 역은 조각에 그려져 있지 않음 — 게임에서 `line*.json`을 읽어 호선별로 그림(선택한 호선만 표시 가능).

## 주의
- 동 경계: SGIS/vuski admdongkor 2026-10-01. 서울시 지도 서비스 경계와의 일치는 미검증.
- 선로: Esri Korea 공개 서비스(2026-04-30)에서 복선을 하나로 합친 중심선.
- **추정 구간:** 회기~청량리 사이 약 961m는 공개 선형이 끊겨 직선으로 이었음(`estimated_spans_m`). 실제 선로 형상 아님.
- 환승 판정은 같은 이름의 역이 둘 이상의 호선에 있을 때 자동. 지금은 1호선뿐이라 환승역 0개.

## 호선 추가
1. 해당 호선의 역·선로 데이터를 `data.js`와 같은 형식으로 준비(생성기는 현재 1호선만 읽으므로 입력 로더를 호선별로 확장해야 함).
2. `lines.config.json`의 `lines`에 `id`, `name`, `color`, `segments`(역 이름 순서 배열, 분기마다 구간 추가) 항목을 넣고 `enabled: true`.
3. 재생성하면 환승역·분기점이 `network.json`에 자동 반영.

## 라벨 (구·동·한강)
- `python3 tools/add-district-labels.py` → `tiles-labeled/`(글자가 얹힌 조각 46개)와 `labels.json`(`districts`, `dongs`, `river` 라벨 위치) 생성.
- 투명도 환경변수: `GU_ALPHA`(구 이름, 기본 0.40), `DONG_ALPHA`(동 이름, 기본 0.15), `RIVER_ALPHA`(한강, 기본 0.45), `GU_DOTS`(구 글자 크기, 기본 15도트).
- 동 이름은 각 동 안쪽에 맞춰 글자 크기(24→10px)와 줄바꿈(`·` 또는 중간)을 자동 조절. 아주 작은 동은 일부 넘칠 수 있음.
- `tiles/`는 라벨 없는 원본. 게임에서 직접 글자를 그리려면 `tiles/` + `labels.json`을 쓰면 됨.

## 구·동 경계, 한강
- 동 경계: 각 동 색보다 살짝 진한 연한 1도트 선.
- 구 경계: 검정(`map.gu_border_color`, 기본 `#111111`) 선, 구마다 안쪽으로 `map.gu_border_dots`(기본 1도트) → 경계에서 약 8px. `gu_palette`는 더 이상 쓰지 않음.
- **한강(근사):** 행정구역 경계가 강 수면을 포함하므로, `river.crossing_pairs`에 적은 구 쌍의 경계선을 강 중심선으로 삼고 `river.half_width_m`(420m → 폭 약 840m)로 칠함. 서울 서쪽(강서구)·동쪽(강동구) 끝은 서울 외곽선을 따라 `outer_extensions`로 연장하고 `outer_width_factor`(1.7)만큼 넓힘. 실제 강둑 폴리곤이 아니므로 폭·모양은 근사. 실제 하천 폴리곤을 구하면 교체 가능.
- `seoul-grid.json`: `gus`, `dongs[].gu_i`, `river_rle`(한강 도트) 포함.
- 바꾼 뒤에는 `node tools/gen-game-map.cjs` → `python3 tools/add-district-labels.py` 순서로 실행.
