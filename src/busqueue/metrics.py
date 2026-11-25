import numpy as np
from .config import PEAKS


def jain(x):
    x = np.asarray(x, float)
    return float(x.sum() ** 2 / (len(x) * (x ** 2).sum())) if (x ** 2).sum() > 0 else 1.0


def summarise(res):
    cfg = res.cfg
    T = cfg.window
    w_all = np.array(res.waits[0] + res.waits[1])
    ab = len(res.aband_wait[0]) + len(res.aband_wait[1])
    n_arr = sum(res.n_arr)
    loads = np.array([t[2] for t in res.trips]) if res.trips else np.array([0])
    # time-average queue length (window only)
    q = np.array(res.qlen)
    q = q[q[:, 0] <= T + 1e-9]
    # busy fraction inside the window
    busy = 0.0
    for a, b in res.busy_intervals:
        busy += max(0.0, min(b, T) - max(a, 0.0))
    # 'effective wait': a student who gives up counts as their wait plus a 60 min penalty
    LOSS = 60.0
    ab_w = np.array(res.aband_wait[0] + res.aband_wait[1])
    eff = (w_all.sum() + (ab_w + LOSS).sum()) / max(n_arr, 1)
    out = dict(
        eff_wait=float(eff),
        arrivals=n_arr,
        boarded=len(w_all),
        abandoned=ab,
        abandon_pct=100 * ab / max(n_arr, 1),
        mean_wait=float(w_all.mean()) if len(w_all) else np.nan,
        p90_wait=float(np.percentile(w_all, 90)) if len(w_all) else np.nan,
        max_wait=float(w_all.max()) if len(w_all) else np.nan,
        mean_wait_stc=float(np.mean(res.waits[0])) if res.waits[0] else np.nan,
        mean_wait_mg=float(np.mean(res.waits[1])) if res.waits[1] else np.nan,
        trips=len(res.trips),
        mean_load=float(loads.mean()),
        load_factor=float(loads.mean() / cfg.rated_cap),
        over_pct=100 * float((loads > cfg.rated_cap).mean()),
        crowd_pax_pct=100 * float(loads[loads > cfg.rated_cap].sum() - cfg.rated_cap * (loads > cfg.rated_cap).sum()) / max(loads.sum(), 1),
        fleet_busy_pct=100 * busy / (cfg.n_buses * T),
        idle_with_queue_busmin=res.idle_with_queue,
        mean_queue=float(q[:, 1:].sum(axis=1).mean()) if len(q) else np.nan,
        max_queue=float(q[:, 1:].sum(axis=1).max()) if len(q) else np.nan,
        remaining=res.remaining,
    )
    out["jain_wait"] = jain([out["mean_wait_stc"], out["mean_wait_mg"]])
    return out
