"""
Parameter tuning on TRAINING seeds (1000-1029).  The evaluation in
run_experiments.py uses seeds 0..N-1, so tuned values are never judged on the
same random numbers they were fitted to.

    PYTHONPATH=src python tune.py
"""
import itertools, json
import numpy as np
from busqueue import Config, run_once, summarise, make_draws
from busqueue.policies import LoadOrTimeout, PooledLQF, PAD

TRAIN = range(1000, 1030)
CFGS = [Config(peak="PM"), Config(peak="AM")]
DRAWS = {(c.peak, s): make_draws(c, s) for c in CFGS for s in TRAIN}


def score(P, kw):
    sc = [np.mean([summarise(run_once(c, P(**kw), s, DRAWS[(c.peak, s)]))["eff_wait"] for s in TRAIN]) for c in CFGS]
    return float(np.mean(sc)), [float(x) for x in sc]


def search(P, grid):
    rows = []
    for vals in itertools.product(*grid.values()):
        kw = dict(zip(grid.keys(), vals))
        tot, per = score(P, kw)
        rows.append(dict(score=tot, pm=per[0], am=per[1], **kw))
    rows.sort(key=lambda r: r["score"])
    return rows


if __name__ == "__main__":
    res = {}
    res["P1"] = search(LoadOrTimeout, dict(theta=[48, 54, 60], w_max=[10, 15, 20], q_min=[8]))
    res["P2"] = search(PooledLQF, dict(theta=[48, 54, 60], w_max=[10, 15, 20], q_min=[8]))
    res["P3"] = search(PAD, dict(theta_full=[48, 54, 60], k=[0, 1], w_hold=[8, 10, 14],
                                 th_min=[10], w_max=[10, 14, 20], gamma=[0.25, 0.5, 1.0]))
    best = {}
    for name, rows in res.items():
        r = dict(rows[0]); r.pop("score"); r.pop("pm"); r.pop("am")
        best[name] = r
        print(name, "best", rows[0])
    json.dump(res, open("results/tuning_all.json", "w"), indent=1)
    json.dump(best, open("results/tuned_params.json", "w"), indent=1)
