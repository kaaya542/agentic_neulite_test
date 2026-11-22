"""Independent equations transcribed from the pinned Kv43.mod, never from the C flavor."""
import math

TEMPERATURE_C = 34.0
EK_MV = -107.0
GBAR_S_CM2 = 0.0032


def sigm(x, y):
    return 1 / (math.exp(x / y) + 1)


def rates(v):
    """Return a_inf, tau_a (ms), b_inf, tau_b (ms) as in PROCEDURE rate, without TABLE."""
    q10 = 3 ** ((TEMPERATURE_C - 25.5) / 10)
    alp_a = q10 * 0.8147 * sigm(v - -9.17203, -23.32708)
    bet_a = q10 * 0.1655 / math.exp((v - -18.27914) / 19.47175)
    alp_b = q10 * 0.0368 * sigm(v - -111.33209, 12.8433)
    bet_b = q10 * 0.0345 * sigm(v - -49.9537, -8.90123)
    return sigm(v - -38, -17), 1 / (alp_a + bet_a), sigm(v - -78.8, 8.4), 1 / (alp_b + bet_b)


def implicit_gates(step, dt, hold, voltage):
    """Closed form of backward Euler (derivimplicit) after `step` updates at constant voltage."""
    a0, _, b0, _ = rates(hold)
    a_inf, tau_a, b_inf, tau_b = rates(voltage)
    return (a_inf + (a0 - a_inf) * (1 + dt / tau_a) ** -step,
            b_inf + (b0 - b_inf) * (1 + dt / tau_b) ** -step)


def exact_gates(t, hold, voltage):
    """Continuous-time solution of the MOD ODE at constant voltage."""
    a0, _, b0, _ = rates(hold)
    a_inf, tau_a, b_inf, tau_b = rates(voltage)
    return (a_inf + (a0 - a_inf) * math.exp(-t / tau_a),
            b_inf + (b0 - b_inf) * math.exp(-t / tau_b))


def current(a, b, voltage, density=GBAR_S_CM2):
    return density * a ** 3 * b * (voltage - EK_MV)  # mA/cm²
