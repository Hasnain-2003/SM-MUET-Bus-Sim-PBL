"""
Runs every experiment reported in the paper.  Results are written to ./results.

    PYTHONPATH=src python run_experiments.py            # full run (about 10 minutes)
    PYTHONPATH=src python run_experiments.py --quick    # 20 replications, smoke test
"""
import json, pickle, sys, time
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import pandas as pd
from busqueue import Config, run_once, summarise
from busqueue.policies import StaticTimetable, LoadOrTimeout, PooledLQF, PAD

TUNED = json.load(open("results/tuned_params.json"))
QUICK = "--quick" in sys.argv
N_MAIN = 20 if QUICK else 200
N_SENS = 10 if QUICK else 100


def make_policy(key, H=6):
    return {
        "S0": lambda: StaticTimetable(H),
        "P1": lambda: LoadOrTimeout(**TUNED["P1"]),
        "P2": lambda: PooledLQF(**TUNED["P2"]),
        "P3": lambda: PAD(**TUNED["P3"]),
    }[key]()


def job(a):
    cfg, key, seed, H, keep = a
    res = run_once(cfg, make_policy(key, H), seed)
    out = summarise(res)
    if keep:
        out["_q"] = np.array(res.qlen)
        out["_waits"] = (np.array(res.waits[0]), np.array(res.waits[1]))
        out["_loads"] = np.array([t[2] for t in res.trips])
        out["_trips"] = np.array([(t[0], t[1], t[2], t[3]) for t in res.trips])
    return out


def batch(ex, cfg, key, n, H=6, keep=False, tag=None):
    rows = list(ex.map(job, [(cfg, key, s, H, keep) for s in range(n)], chunksize=5))
    return rows


def tidy(rows, **meta):
    df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
    df["seed"] = range(len(df))
    for k, v in meta.items():
        df[k] = v
    return df


if __name__ == "__main__":
    t0 = time.time()
    ex = ProcessPoolExecutor()
    keys = ["S0", "P1", "P2", "P3"]

    # ---- E1/E2: main comparison, both peaks, common random numbers ----
    main, keep = [], {}
    for peak in ("PM", "AM"):
        cfg = Config(peak=peak)
        for k in keys:
            rows = batch(ex, cfg, k, N_MAIN, keep=True)
            keep[(peak, k)] = dict(
                q=[r["_q"] for r in rows],
                waits=[r["_waits"] for r in rows],
                loads=np.concatenate([r["_loads"] for r in rows]),
                trips=[r["_trips"] for r in rows],
            )
            main.append(tidy(rows, peak=peak, policy=k))
        print("main", peak, round(time.time() - t0), "s", flush=True)
    pd.concat(main).to_csv("results/main_replications.csv", index=False)
    pickle.dump(keep, open("results/main_series.pkl", "wb"))

    # ---- E3: fleet size ----
    fl = []
    for peak in ("PM", "AM"):
        for n in (16, 18, 20, 22, 24, 26, 28):
            for k in ("S0", "P1", "P3"):
                fl.append(tidy(batch(ex, Config(peak=peak, n_buses=n), k, N_SENS), peak=peak, policy=k, n_buses=n))
    pd.concat(fl).to_csv("results/sens_fleet.csv", index=False)
    print("fleet", round(time.time() - t0), flush=True)

    # ---- E4: demand level ----
    dm = []
    for sc in (0.6, 0.8, 1.0, 1.2, 1.4):
        for k in ("S0", "P1", "P3"):
            dm.append(tidy(batch(ex, Config(peak="PM", demand_scale=sc), k, N_SENS), policy=k, demand_scale=sc))
    pd.concat(dm).to_csv("results/sens_demand.csv", index=False)

    # ---- E5: traffic incidents ----
    ic = []
    for p in (0.0, 0.12, 0.25, 0.40):
        for k in ("S0", "P1", "P3"):
            ic.append(tidy(batch(ex, Config(peak="PM", incident_p=p), k, N_SENS), policy=k, incident_p=p))
    pd.concat(ic).to_csv("results/sens_incidents.csv", index=False)

    # ---- E6: how good can a static timetable get? ----
    hd = []
    for H in (2, 3, 4, 5, 6, 8):
        for peak in ("PM", "AM"):
            hd.append(tidy(batch(ex, Config(peak=peak), "S0", N_SENS, H=H), peak=peak, policy="S0", H=H))
    pd.concat(hd).to_csv("results/sens_headway.csv", index=False)

    # ---- E7: demand split between the terminals (does pooling pay off?) ----
    sp = []
    for share in (0.35, 0.45, 0.57, 0.70, 0.80):
        for k in ("S0", "P1", "P2", "P3"):
            sp.append(tidy(batch(ex, Config(peak="PM", stc_share=share), k, N_SENS), policy=k, stc_share=share))
    pd.concat(sp).to_csv("results/sens_split.csv", index=False)

    print("done in", round(time.time() - t0), "s")
