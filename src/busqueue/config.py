"""
All tunable numbers live here so that nothing is buried inside the model code.

Units: minutes for time, passengers for demand.  t = 0 is the start of the
peak window (08:00 for the AM peak, 14:00 for the PM peak).
"""
from dataclasses import dataclass, replace
import numpy as np

STC, MG = 0, 1
TERMINALS = ("STC", "Main Gate")

# --- demand profiles -------------------------------------------------------
# Each peak is a mixture of Gaussian "bumps" (centre, sd, weight).  The shape
# is normalised so that the integral over the window equals the demand
# D_j assigned to terminal j.
PEAKS = {
    "AM": dict(
        window=60.0,
        demand=(980, 730),                      # passengers in the window (STC, MG)
        bumps=[(30.0, 13.0, 1.0)],              # students rushing for the 09:00 lecture
        congestion=1.10,                        # road slow-down in the morning rush
        start="08:00",
    ),
    "PM": dict(
        window=90.0,
        demand=(1400, 1050),
        bumps=[(8.0, 9.0, 0.55), (62.0, 10.0, 0.45)],   # 14:00 and 15:00 class ends
        congestion=1.05,
        start="14:00",
    ),
}


@dataclass(frozen=True)
class Config:
    peak: str = "PM"
    demand_scale: float = 1.0
    stc_share: float = None        # override the STC share of total demand (what-if); None = profile default

    # fleet
    n_buses: int = 24
    seated: int = 45
    rated_cap: int = 60        # seats + permitted standing room
    hard_cap: int = 70         # what actually gets squeezed in under the static regime

    # campus geometry / boarding
    repos_min: float = 4.0     # Main Gate <-> STC dead-heading time
    dwell_fixed: float = 0.5
    dwell_per_pax: float = 0.04    # about 2.4 s per boarding passenger

    # round trip (dispatch -> back at the Main Gate)
    rt_mean: float = 72.0
    rt_cv: float = 0.18
    incident_p: float = 0.12       # chance a trip hits an incident / breakdown / jam
    incident_mean: float = 18.0

    # passengers
    patience_min: float = 20.0     # nobody abandons before this
    patience_mean: float = 30.0    # exponential tail on top (total mean 50 min) before a student takes a rickshaw

    # simulation control
    tick: float = 1.0              # dispatcher wake-up interval
    drain: float = 150.0           # extra time after the window so queues can clear

    @property
    def window(self):
        return PEAKS[self.peak]["window"]

    @property
    def horizon(self):
        return self.window + self.drain

    def with_(self, **kw):
        return replace(self, **kw)


def _bumps(cfg, t):
    spec = PEAKS[cfg.peak]
    out = np.zeros_like(np.asarray(t, dtype=float))
    for c, s, w in spec["bumps"]:
        out = out + w * np.exp(-0.5 * ((np.asarray(t, dtype=float) - c) / s) ** 2) / (s * np.sqrt(2 * np.pi))
    return out


_NORM = {}


def profile(cfg: Config, t):
    """Normalised arrival-shape f(t) (integrates to 1 over the window)."""
    spec = PEAKS[cfg.peak]
    if cfg.peak not in _NORM:
        grid = np.linspace(0, spec["window"], 4001)
        _NORM[cfg.peak] = np.trapezoid(_bumps(cfg, grid), grid)
    t = np.asarray(t, dtype=float)
    return np.where((t >= 0) & (t <= spec["window"]), _bumps(cfg, t) / _NORM[cfg.peak], 0.0)


def rate(cfg: Config, term: int, t):
    """Arrival rate (passengers / min) at terminal `term`."""
    dem = PEAKS[cfg.peak]["demand"]
    if cfg.stc_share is None:
        D = dem[term]
    else:
        D = sum(dem) * (cfg.stc_share if term == STC else 1 - cfg.stc_share)
    return D * cfg.demand_scale * profile(cfg, t)
