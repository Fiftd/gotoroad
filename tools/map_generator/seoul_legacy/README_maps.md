# Maps (pygame)
`pip install pygame` → `python game_map.py`

- `data.json` : 맵 규격, 타일 목록, 호선(선로 점·역 위치 m), 역(좌표·구·동)
- `tiles/` 글자 없는 타일, `tiles-labeled/` 구·동·한강 이름이 얹힌 타일, `tiles-plain/` 행정구역을 숨긴 서울 윤곽+한강 타일 (1080×720, 8×8 중 46장)
- `game_map.py` : `Line`, `Station`(hover/select/pulse), `Game`(카메라·그리기·입력)
- 조작: 드래그 이동 · 휠 확대 · 역 클릭 선택 · ←/→ 인접역 · D 행정구역 · L 지역이름 · F 전체 · 1~9 호선 토글 · ESC
- 호선 추가: `data.json`의 `lines`에 같은 형식으로 항목 추가(생성기 `gen-game-map.cjs` 재실행으로 만들어짐)
