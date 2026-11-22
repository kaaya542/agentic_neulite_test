"""Independent equations transcribed from the pinned MOD, never from the C flavor."""
import math

TEMPERATURE_C = 34.0
EK_MV = -107.0
GBAR_S_CM2 = 0.004


def rates(v):
    # Separate algebra from the C implementation: inf as a logistic ratio.
    log_ratio = -(v + 45) / 12.42101 - (v + 45) / 33.90877
    n_inf = 1 / (1 + math.exp(log_ratio))
    alpha = 0.12889 * math.exp((v + 45) / 33.90877)
    beta = 0.12889 * math.exp(-(v + 45) / 12.42101)
    tau = math.exp(-(TEMPERATURE_C - 22) * math.log(2.7) / 10) / (alpha + beta)
    return n_inf, tau


def gate(t, hold, voltage):
    n0, _ = rates(hold)
    inf, tau = rates(voltage)
    return inf + (n0 - inf) * math.exp(-t / tau)


def current(n, voltage, density=GBAR_S_CM2):
    return density * n ** 4 * (voltage - EK_MV)  # mA/cm²
