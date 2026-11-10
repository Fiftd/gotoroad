"""한 판의 상태 — 지나간 역, Point 획득, 에너지 소진 시 초기화."""

import math
import random

from game import config as C
from game.play import energy
from game.play.train import Train
from game.play.minigame import QWERgame
from game.stations.interchange_station import transfer_lines
from game.stations.start_station import start_station

class Session:
    def __init__(self, map_data, line_id, profile, rng=random, start=None):
        self.map = map_data
        self.profile = profile
        self.rng = rng
        self.home_line_id = line_id
        self.start = start or start_station(line_id, map_data.by_name).name   # 고른 출발역(없으면 호선 기본 출발역)
        self.events = []
        self.train = Train()
        self.visited, self.visited_set = [], set()
        self.reset(keep_visited=False)

    @property
    def line(self):
        return self.map.lines[self.line_id]

    @property
    def speed(self):
        return C.speed_from_energy(self.E, self.speed_factor)

    def reset(self, keep_visited=True):
        self.line_id = self.home_line_id
        self.cur, self.prev = self.start, None
        if not keep_visited:
            self.visited, self.visited_set = [self.start], {self.start}
        self.E = 0.0
        self.state = "idle"
        self.space = False
        self.charge, self.charge_mult = 0.0, 1.0
        self.speed_factor = C.SPEED_FACTOR_MIN
        self.timer = 0.0
        self.heading = None
        self.just_transferred = False
        self.mini = None
        st = self.map.by_name[self.cur]
        self.train.place(st.x, st.y)
        self.set_options()

    def set_options(self):
        opts = self.line.next_option(self.cur, self.prev)
        if not opts and self.prev:
            opts = [self.prev]                         # 종점: 되돌아감
            self.events.append(("terminal", self.cur))  # 회전 연출용 신호
        self.opts = sorted(opts, key=lambda n: self.map.by_name[n].x)
        if len(self.opts) <= 1:
            self.choice = 0
        elif self.just_transferred and self.heading is not None:
            self.choice = self.closest_to_heading()
        else:
            self.choice = len(self.opts)-1
        self.tlines = transfer_lines(self.map.by_name[self.cur], self.map.lines)

    def move_choice(self, d):
        if self.train.running or self.state not in ("idle", "pick") or len(self.opts) < 2:
            return
        self.choice = max(0, min(len(self.opts)-1 , self.choice + d))

    def press_space(self):
        if self.space:
            return
        self.space = True
        if self.state == "idle":
            self.state, self.charge, self.charge_mult = "charging", 0.0, 1.0
        elif self.state == "pick":
            self.leave()

    def release_space(self):
        self.space = False
        if self.state != "charging":
            return
        self.E += C.charged_energy(self.charge, self.charge_mult)
        self.charge = 0.0
        self.leave()

    def update(self,dt):
        getattr(self, "_t_" + self.state)(dt)

    def _t_idle(self, dt):
        pass

    def _t_charging(self, dt):
        before = self.charge
        self.charge = energy.charge_step(self.charge, dt)
        if before < C.CHARGE_MAX <= self.charge:
            self.charge_mult = C.roll_charge_bonus(self.rng)
            self.events.append(("max", self.charge_mult))

    def _t_run(self, dt):
        if self.speed < C.STOP_KMH:
            return self.burnout()
        m = energy.distanc_m(self.speed, dt)
        self.E = energy.consume(self.E, m)
        if self.train.advance(m):
            self.arrive()

    def _t_crash(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.after_station()

    def leave(self):
        self.speed_factor = C.roll_speed_factor(self.rng)
        if self.speed < C.STOP_KMH:
            if self.state == "charging":
                self.state = "idle"
                return
            return self.burnout()
        target = self.opts[self.choice]
        self.train.depart(self.map.tracks(self.line_id)[(self.cur, target)], target)
        self.state = "run"
        self.just_transferred = False

    def arrive(self):
        self.heading = self.train.angle
        self.prev, self.cur = self.cur, self.train.target
        st = self.map.by_name[self.cur]
        self.train.place(st.x, st.y)
        first = self.cur not in self.visited_set
        gain = C.POINT_FIRST_STATION if first else C.POINT_NORMAL_STATION
        self.profile.add(gain)
        self.events.append(("point", gain))

        if first:
            self.visited.append(self.cur)
            self.visited_set.add(self.cur)
            self.E *= C.CRASH_SPEED_MULT
            self.state, self.timer = "crash", C.CRASH_TIME
            self.events.append(("crash", self.cur))
        else:
            self.mini = QWERgame(self.rng)
            self.state = "mini"
            self.events.append(("mini_start", self.cur))

    def after_station(self):
        self.set_options()
        if len(self.opts) > 1 or self.tlines:
            self.state, self.timer = "pick", C.PICK_TIME
            self.events.append(("pick", self.cur))
        else:
            self.leave()

    def burnout(self):
        self.events.append(("burnout",))
        self.reset(keep_visited=True)

    def closest_to_heading(self):
        cur = self.map.by_name[self.cur]
        def diff(name):
            o = self.map.by_name[name]
            a = math.atan2(o.y - cur.y, o.x - cur.x)
            return abs((a-self.heading + math.pi)% math.tau - math.pi)
        return min (range(len(self.opts)), key=lambda i: diff(self.opts[i]))

    def key(self, ch):
        if self.state == "mini":
            self.mini.key(ch)
            self.mini_result()
        elif ch in C.TRANSFER_KEYS:
            self.transfer(C.TRANSFER_KEYS.index(ch))

    @property
    def can_transfer(self):
        return not self.train.running and self.state in ("idle", "pick") and len(self.tlines)

    def transfer(self, i):
        if not self.can_transfer or i >= len(self.tlines):
            return
        lid = self.tlines[i]
        if lid == self.line_id:
            return self.events.append(("riding", lid))
        if not self.profile.is_unlocked(lid):
            return self.events.append(("locked" ,lid))
        self.line_id = lid
        self.prev = None
        self.just_transferred = True
        self.set_options ()
        self.events.append(("transfer", lid))
        if self.state =="pick":
            self.timer = C.PICK_TIME

    def mini_result(self):
        mg = self.mini
        if mg.result is None or mg.paid:
            return
        mg.paid = True
        ok = mg.result == "ok"
        if ok:
            self.E += C.STATION_BONUS_J
        self.events.append(("mini", ok))

    def _t_mini(self, dt):
        self.mini.update(dt)
        self.mini_result()
        if self.mini.done:
            self.mini=None
            self.after_station()

    def _t_pick(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.leave()

     