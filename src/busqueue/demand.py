"""Non-homogeneous Poisson arrivals by thinning (Lewis & Shedler, 1979)."""
import numpy as np
from .config import rate


def nhpp_arrivals(cfg, term, rng):
    grid = np.linspace(0, cfg.window, 721)
    lam_max = float(rate(cfg, term, grid).max()) * 1.02
    t, out = 0.0, []
    while True:
        t += rng.exponential(1.0 / lam_max)
        if t > cfg.window:
            break
        if rng.random() <= float(rate(cfg, term, t)) / lam_max:
            out.append(t)
    return np.array(out)
