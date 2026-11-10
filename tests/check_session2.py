import math, random
from game.world.map_data import MapData
from game.save import Profile
from game.play.session import Session
m = MapData()
def run_until(s, cond, limit=6000):
    for i in range(limit):
        s.update(1 / 60)
        if cond(s): return i / 60

# 1) 환승역 도착 → pick, 2) 경의중앙선으로 환승(규칙 2)
p1 = Profile(None); p1.unlocked.add("gyeongui")
s = Session(m, "1", p1, rng=random.Random(1))
s.move_choice(-1); s.press_space(); [s.update(1/60) for _ in range(200)]; s.release_space()
run_until(s, lambda s: s.state == "crash"); run_until(s, lambda s: s.state != "crash")
run_until(s, lambda s: s.state == "pick")
print("pick at", s.cur, s.tlines, "opts", s.opts, "choice", s.opts[s.choice], "timer", s.timer)
i = s.tlines.index("gyeongui")
print("heading(deg)", round(math.degrees(s.heading)), "key", "qwerasdf"[i])
s.key("qwerasdf"[i])
print("after transfer:", s.line_id, s.opts, "choice ->", s.opts[s.choice], s.events[-1], "timer", s.timer)
# 3) 잠긴 호선 / 시작역 환승
s3 = Session(m, "1", Profile(None), rng=random.Random(3))
print("서울역 tlines", s3.tlines); s3.key("e"); print("locked:", s3.events[-1], s3.line_id)
s3.key("w"); print("to 4:", s3.line_id, s3.opts, s3.opts[s3.choice], "(heading None → 오른쪽)")
# 4) 미니게임 성공
s4 = Session(m, "1", Profile(None), rng=random.Random(4)); s4.visited_set.add("남영")
s4.move_choice(-1); s4.press_space(); [s4.update(1/60) for _ in range(200)]; s4.release_space()
run_until(s4, lambda s: s.state == "mini")
mg = s4.mini; print("mini at", s4.cur, mg.keys, "time", round(mg.total, 2)); E0 = s4.E
s4.key(mg.keys[0]); print("arm 중 입력 무시 idx", mg.idx)
[s4.update(1/60) for _ in range(12)]
for k in mg.keys: s4.key(k)
print("result", mg.result, "E +", round(s4.E - E0), s4.events[-1])
run_until(s4, lambda s: s.state != "mini"); print("after mini:", s4.state, s4.cur, "→", s4.train.target)
# 5) 틀린 키, 6) 시간 초과
s5 = Session(m, "1", Profile(None), rng=random.Random(5)); s5.visited_set.add("남영")
s5.move_choice(-1); s5.press_space(); [s5.update(1/60) for _ in range(200)]; s5.release_space()
run_until(s5, lambda s: s.state == "mini"); [s5.update(1/60) for _ in range(12)]
wrong = next(k for k in "qwerasdf" if k != s5.mini.keys[0]); s5.key(wrong); print("wrong:", s5.mini.result, s5.events[-1])
s6 = Session(m, "1", Profile(None), rng=random.Random(6)); s6.visited_set.add("남영")
s6.move_choice(-1); s6.press_space(); [s6.update(1/60) for _ in range(200)]; s6.release_space()
run_until(s6, lambda s: s.state == "mini"); E0 = s6.E
run_until(s6, lambda s: s.mini.result is not None); print("timeout:", s6.mini.result, round(s6.mini.left, 2), s6.events[-1], "E +", round(s6.E - E0))