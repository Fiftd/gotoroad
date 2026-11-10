import random
from game.world.map_data import MapData
from game.save import Profile
from game.play.session import Session

m = MapData()
s = Session(m, "1", Profile(None), rng=random.Random(1))
print(s.cur, s.opts, s.choice, s.state)
s.move_choice(-1); print("choice ->", s.opts[s.choice])
s.press_space()
for _ in range(200): s.update(1 / 60)                        # 약 3.3초 충전 → MAX
print(s.state, round(s.charge), round(s.charge_mult, 3))
s.release_space()
print(s.state, round(s.E), round(s.speed_factor, 3), round(s.speed, 1))
for i in range(3000):
    s.update(1 / 60)
    if s.state != "run":
        print("t=%.2fs" % (i / 60), s.state, s.cur, round(s.E), s.events[-1]); break
for _ in range(60): s.update(1 / 60)                          # 충돌 0.9초 → 자동 출발
print(s.state, s.cur, "→", s.train.target, round(s.speed, 1))

s2 = Session(m, "1", Profile(None), rng=random.Random(2))
s2.press_space(); s2.update(0.3); s2.release_space()           # 짧게 충전
print("short:", s2.state, round(s2.E), round(s2.speed, 1))
for _ in range(5000):
    s2.update(1 / 60)
    if ("burnout",) in s2.events: break
print("burnout:", s2.cur, s2.state, s2.visited, s2.events[-3:])