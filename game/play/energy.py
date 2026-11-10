"""에너지 충전(SPACE 홀딩)·소모, 속도 계산."""
from game import config as C

def charge_step(charge, dt):
    return min ( C.CHARGE_MAX, charge+C.energy_bar_speed(charge) * C.ENERGY_BAR_SPEED_UNIT * dt)

def distanc_m(speed_kmh, dt):
    return speed_kmh / 3.6 * dt * C.TIME_SCALE

def consume(energy, meters):
    return max(0.0, energy-C.COST_PER_KM*meters /1000.0)