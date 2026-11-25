"""Prints the numerical outcome of the verification checks (same logic as tests/test_model.py)."""
import json, numpy as np
from busqueue import Config, run_once, config
from busqueue.policies import PAD, LoadOrTimeout
errs = []
for seed in range(10):
    cfg = Config(peak="PM"); res = run_once(cfg, PAD(), seed)
    q = np.array(res.qlen); area = (q[:, 1] + q[:, 2]).sum() * cfg.tick
    tw = sum(map(sum, res.waits)) + sum(map(sum, res.aband_wait)); errs.append(abs(area - tw) / tw)
config.PEAKS["TEST"] = dict(window=600.0, demand=(1800, 1), bumps=[(300.0, 1e7, 1.0)], congestion=1.0, start="00:00")
cfg = Config(peak="TEST", n_buses=40, tick=0.02, rt_mean=60, drain=60)
w = []
for s in range(6):
    w += run_once(cfg, LoadOrTimeout(theta=30, w_max=1e9, q_min=10**9), s).waits[0]
out = dict(little_mean_err_pct=100*float(np.mean(errs)), little_max_err_pct=100*float(np.max(errs)),
           batch_sim=float(np.mean(w)), batch_theory=29/6, batch_n=len(w))
print(out); json.dump(out, open("results/verification.json", "w"), indent=1)
