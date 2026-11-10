# gotoroad — 가고 싶은 길

서울 지하철 노선을 여행하는 Python/Pygame 게임입니다.

## 실행

프로젝트 폴더에서 다음 명령을 실행하세요.

```sh
python -m pip install pygame Pillow
python main.py
```

저장 데이터(`save.json`)와 개인 설정(`settings.json`)은 실행 중 생성되며 Git에 포함하지 않습니다.

## 문서

- [프로젝트 명세](docs/SPEC.md)
- [작성 가이드](docs/GUIDE.md)
- [지도 도구](tools/map_generator/README.md)

## 폴더 구조
| 폴더 | 내용 |
|---|---|
| `game/` | 게임 코드 (`py main.py`) |
| `assets/map/capital·daegu·busan/` | 지역 지도(data.json + 지도 조각). 수도권은 축소 그림(overview)도 |
| `assets/ui/`, `assets/sprites/`, `assets/sound/`, `assets/font/` | 아이콘·역 간판, 열차, 소리, 글꼴 |
| `tools/gen_line_assets.py` | 호선 아이콘·열차·역 간판 생성 |
| `tools/map_generator/` | 지도 생성기, 설정(`*.config.json`), 원본 데이터(`sources/`), 예전 서울 도구(`seoul_legacy/`) |
| `docs/` | SPEC·GUIDE·기획, 확인용 미리보기(`previews/`), 참고 그림(`reference/`) |
| `tests/` | 확인 스크립트 (`set PYTHONPATH=.` 후 `py tests\check_track.py` 등) |
| `gotoroad.spec`, `build_exe.bat` | exe 빌드 → `dist/` |
| `save.json`, `settings.json` | 실행하면 생기는 저장 파일 |
