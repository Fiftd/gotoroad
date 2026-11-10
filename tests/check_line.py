import json
from game import config as C
from game.world.line import Line

D = json.load(open(C.MAP_DATA, encoding="utf-8"))
lines = {d["id"]: Line(d) for d in D["lines"]}
print(len(lines), lines["1"].name, lines["1"].color, lines["gimpo"].available)

T = json.load(open(C.LINE_TYPES, encoding="utf-8"))["lines"]
lines = {d["id"]: Line(d, T.get(d["id"], {}).get("type", "main")) for d in D["lines"]}
print(lines["1"].type, lines["arex"].type, lines["arex"].short, lines["7"].short)

L = lines
print(L["2"].neighbor_station("시청"))   # 순환 처리
print(L["2"].neighbor_station("성수"))   # 본선 + 성수지선
print(L["1"].neighbor_station("구로"))   # 갈림길
print(L["1"].neighbor_station("도봉산")) # 종점(이 데이터의 1호선 시작)

print(L["1"].next_option("구로", "신도림"))   # 갈림길 표 사용
print(L["2"].next_option("성수", "뚝섬"))     # 2호선 갈림길
print(L["1"].next_option("서울역", "시청"))   # 일반 역: 온 길 빼기
print(L["1"].next_option("도봉산", "도봉"))   # 종점: 빈 리스트
print(L["1"].next_option("서울역"))           # 출발: 양쪽

print(L["1"].is_switch("구로"), L["1"].is_switch("서울역"))
print(len(L["2"].station_names()), L["2"].has("까치산"), L["1"].has("강남"))


print(L["gyeongui"])