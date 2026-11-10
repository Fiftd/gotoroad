# 지도 생성기

게임 지도(`assets/map/<지역>/`)를 만드는 도구. 실행은 프로젝트 폴더에서. 필요: `pip install pillow numpy scipy`, 라벨 글꼴 Noto Sans CJK.

| 지역 | 실행 | 설정 | 원본 데이터 |
|---|---|---|---|
| 수도권 | `py tools/map_generator/gen_capital_map.py tools/map_generator/capital.config.json` | `capital.config.json` | `sources/capital/` |
| 대구권 | `py tools/map_generator/gen_region_map.py tools/map_generator/daegu.config.json` | `daegu.config.json` | `sources/daegu/` |
| 부산권 | `py tools/map_generator/gen_region_map.py tools/map_generator/busan.config.json` | `busan.config.json` | `sources/busan/` |

- 결과: `assets/map/<지역>/` (data.json, tiles/, tiles-labeled/, tiles-plain/, 수도권은 overview-*.png).
- 확인용 미리보기·라벨 위치: `docs/previews/map_<지역>.png`, `map_<지역>_labels.json` (게임은 안 씀).
- 지도를 바꾼 뒤에는 `py tools/gen_line_assets.py` 로 호선 아이콘·역 간판을 다시 만든다.
- `seoul_legacy/`: 처음 서울 지도를 만든 예전 도구(기록용).

## 대구권 지도 (gen_region_map.py)
예전 서울 생성기(seoul_legacy/ 의 gen-game-map.cjs + add-district-labels.py)를 파이썬 하나로 옮긴 지역용 생성기. 축척·팔레트·라벨 규칙은 서울과 같음.

- 실행: `py tools/map_generator/gen_region_map.py tools/map_generator/daegu.config.json` (pip install pillow numpy scipy, 라벨 글꼴 Noto Sans CJK)
  → `assets/map/daegu/` (data.json, tiles/, tiles-labeled/, tiles-plain/)
- 그다음 `py tools/gen_line_assets.py` → 대구 호선 아이콘(d1~d3)·열차·역 간판(`assets/ui/station_signs/daegu/`)
- 범위: 대구 도시철도 1·2·3호선 선로 바깥으로 2.6 km 여유. 화면 7×6개(7560×4320 px), 조각 41개.
- 호선 id: d1(1호선, 설화명곡~하양 37.5 km, 36역), d2(2호선, 문양~영남대 31.4 km, 29역), d3(3호선 모노레일, 칠곡경대병원~용지 23.0 km, 30역). 환승역: 반월당·명덕·청라언덕.
- 구간 길이: OSM 선로 중심선을 따라 계산한 값(공식 역간 거리와 조금 다를 수 있음).
- 한강처럼 강을 따로 그리지 않음(금호강·신천 없음).

### 출처 (대구권)
| 자료 | 파일 | 출처 · 라이선스 |
|---|---|---|
| 행정동 경계 | `sources/daegu/daegu_dongs.geojson` (대구광역시, 군위군 제외 + 경상북도 경산시) | [vuski/admdongkor](https://github.com/vuski/admdongkor) ver20261001, CC BY 4.0 · 원자료 통계청 SGIS(공공누리 제1유형) |
| 선로 중심선·역 위치 | `sources/daegu/daegu_lines.geojson`, `daegu_stations.geojson` | © OpenStreetMap contributors, ODbL — [plazalabs/kr-rail-map](https://github.com/plazalabs/kr-rail-map) 정리본(Geofabrik 2026-10-09 추출) |

## 수도권 지도 (gen_capital_map.py)
예전 서울 지도(`sources/capital/seoul_base_data.json`)는 그대로 두고, 서울 밖 인천·경기 근교 구간을 OpenStreetMap 선로·역으로 이어 붙인 큰 지도.

- 실행: `py tools/map_generator/gen_capital_map.py tools/map_generator/capital.config.json` (pip install pillow numpy scipy, 라벨 글꼴 Noto Sans CJK)
  → `assets/map/capital/` (data.json, tiles/, tiles-labeled/, tiles-plain/, overview-*.png)
- 그다음 `py tools/gen_line_assets.py` → 새 역 간판(서울 간판 폴더에 함께), 인천1·2호선 아이콘.
- 게임의 수도권 지도(`config.MAP_DATA`). 예전 서울만 있던 지도는 지웠다.
- 범위: 서울시청 기준 서 33 km · 동 30 km · 북 30 km · 남 40 km. 화면 12×19개(12960×13680 px), 조각 227개.
  기존 서울 지도가 조각 단위로 그대로 밀리도록 맞춤 → 서울 좌표는 (+2160, +2880) px 평행 이동만.
- 좌표 맞추기: OSM 역(웹 메르카토르 × cos 37.5665°)과 기존 서울 역의 차이 중앙값으로 평행 이동(축척 같음). 차이 중앙값 25 m.
- 노선 잇기: 호선마다 OSM 선로를 20 m 간격 그래프로 만들고(끊긴 곳은 600 m 이내 이음), 역을 선로 위로 붙인 뒤
  선로를 따라 잰 거리로 '사이에 다른 역이 없는' 역 쌍만 이웃으로 삼는다. 서울 안 구간(두 역 다 기존 역)은 기존 데이터를 그대로 쓴다.
  세 역이 서로 다 이어지면 가장 긴 쪽(역이 아닌 갈림목을 거친 쌍)을 버린다. 예외는 config `drop_edges`(1호선 석수–광명).
- 갈림길(switches): 새로 생긴 갈림역은 선로 각도(100° 미만)로 갈 수 있는 방향을 정함(금천구청: 광명 ↔ 독산만).
- 서울 밖 노선: 1호선(덕계·서동탄·인천·광명), 3호선(대화), 4호선(진접·오이도), 5호선(하남검단산), 7호선(장암·석남), 8호선(별내·모란),
  공항철도(청라국제도시), 경의중앙선(파주·양수), 경춘선(마석), 수인분당선(인천), 신분당선(광교), 김포골드라인(양촌), 서해선(일산~원시),
  인천1호선(검단호수공원~송도달빛축제공원), 인천2호선(검단오류~운연). 범위 밖으로 나가는 구간은 경계 안쪽 마지막 역에서 끊음.
- 한강: 구 경계를 강 중앙선으로 보고 폭 840 m 로 근사(서울 + 고양·김포·구리·하남·남양주 경계). 임진강·안양천 등은 없음.
- 큰 지도라 게임은 조각을 화면에 보일 때만 읽고(최근 48개만 메모리에), 멀리서 볼 때는 1/4 축소 그림(overview-*.png)으로 그린다.
- 서울 안을 OSM 으로 새로 그리는 설정(`seoul_source: "osm"`)도 있지만, OSM 선로가 서울 안에서 수 km 씩 끊겨 있어(예: 2호선) 쓰지 않는다.

### 출처 (수도권)
| 자료 | 파일 | 출처 · 라이선스 |
|---|---|---|
| 서울 안 선로·역 | `sources/capital/seoul_base_data.json` (= 예전 `assets/map/data.json`) | 기존 서울 지도(Esri Korea 공개 서비스 선로, 행정동 SGIS/vuski) |
| 서울 밖 선로 중심선·역 위치 | `sources/capital/capital_lines.geojson`, `capital_stations.geojson` | © OpenStreetMap contributors, ODbL — [plazalabs/kr-rail-map](https://github.com/plazalabs/kr-rail-map) 정리본(Geofabrik 2026-10-09 추출) |
| 행정동 경계 | `sources/capital/capital_dongs.geojson` (서울특별시·인천광역시·경기도 중 범위 안) | [vuski/admdongkor](https://github.com/vuski/admdongkor) ver20261001, CC BY 4.0 · 원자료 통계청 SGIS(공공누리 제1유형) |

## 부산권 지도 (gen_region_map.py)
대구와 같은 생성기. 한 호선이 여러 조각으로 끊겨 있으면 끝점끼리 이어 한 줄로 만든다(빈 곳은 직선, 부산 2·3호선).
`exclude_stations` 로 승객이 타지 않는 정차점을 뺀다(부산 4호선 안평기지간이).

- 실행: `py tools/map_generator/gen_region_map.py tools/map_generator/busan.config.json` → `assets/map/busan/`
- 그다음 `py tools/gen_line_assets.py` → 아이콘(b1~b4, bgl)·역 간판(`assets/ui/station_signs/busan/`)
- 부산권: 화면 6×10개(6480×7200 px), 조각 57개. 범위는 부산광역시 + 경남 양산시·김해시.
  b1(1호선, 노포~다대포해수욕장 39.6 km, 40역), b2(2호선, 양산~장산 48.7 km, 43역), b3(3호선, 대저~수영 18.1 km, 17역),
  b4(4호선, 미남~안평 11.8 km, 14역), bgl(부산김해경전철, 사상~가야대 22.5 km, 21역).
  환승역: 서면·연산·동래·덕천·사상·수영·대저·미남. 동해선(광역전철)은 넣지 않음.
- 구간 길이: OSM 선로를 따라 잰 값. 선로가 끊긴 곳은 직선으로 이어서 공식 거리와 조금 다를 수 있음(부산 2호선 공식 45.2 km).

### 출처 (부산권)
| 자료 | 파일 | 출처 · 라이선스 |
|---|---|---|
| 행정동 경계 | `sources/busan/busan_dongs.geojson` (부산광역시 + 경남 양산시·김해시) | [vuski/admdongkor](https://github.com/vuski/admdongkor) ver20261001, CC BY 4.0 · 원자료 통계청 SGIS(공공누리 제1유형) |
| 선로 중심선·역 위치 | `sources/busan/busan_lines.geojson`, `busan_stations.geojson` | © OpenStreetMap contributors, ODbL — [plazalabs/kr-rail-map](https://github.com/plazalabs/kr-rail-map) 정리본(Geofabrik 2026-10-09 추출) |
