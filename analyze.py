"""Turns ./results/*.csv into figures (./figures) and a numbers file (results/tables.json).
    PYTHONPATH=src python analyze.py
"""
import json, pickle
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats
from busqueue import Config
from busqueue.config import rate, PEAKS

plt.rcParams.update({"font.family": "serif", "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
                     "font.size": 10, "axes.grid": True, "grid.alpha": .25, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight"})
COL = {"S0": "#7F7F7F", "P1": "#1F77B4", "P2": "#2CA02C", "P3": "#D9531E"}
NAME = {"S0": "S0 static", "P1": "P1 load/timeout", "P2": "P2 pooled", "P3": "P3 PAD"}
KEYS = ["S0", "P1", "P2", "P3"]
main = pd.read_csv("results/main_replications.csv")
series = pickle.load(open("results/main_series.pkl", "rb"))
T = {}


def ci(x):
    x = np.asarray(x, float)
    h = stats.sem(x) * stats.t.ppf(.975, len(x) - 1)
    return float(x.mean()), float(h)


# ---------------------------------------------------------------- tables
METRICS = ["eff_wait", "mean_wait", "p90_wait", "max_wait", "abandon_pct", "over_pct", "load_factor",
           "fleet_busy_pct", "idle_with_queue_busmin", "mean_queue", "max_queue", "jain_wait",
           "mean_wait_stc", "mean_wait_mg", "trips", "boarded", "arrivals"]
T["main"] = {pk: {k: {m: ci(main[(main.peak == pk) & (main.policy == k)][m]) for m in METRICS} for k in KEYS} for pk in ("PM", "AM")}
T["paired"] = {}
for pk in ("PM", "AM"):
    b = main[(main.peak == pk) & (main.policy == "S0")].set_index("seed")
    for k in KEYS[1:]:
        o = main[(main.peak == pk) & (main.policy == k)].set_index("seed")
        T["paired"][f"{pk}_{k}"] = {m: dict(zip(("diff", "half"), ci(o[m] - b[m])), rel=100 * float((o[m] - b[m]).mean() / b[m].mean()))
                                    for m in ("eff_wait", "mean_wait", "abandon_pct", "p90_wait")}
fl = pd.read_csv("results/sens_fleet.csv")
T["fleet"] = {pk: fl[fl.peak == pk].groupby(["policy", "n_buses"])["eff_wait"].mean().unstack(0).round(2).to_dict() for pk in ("PM", "AM")}
T["fleet_ab"] = {pk: fl[fl.peak == pk].groupby(["policy", "n_buses"])["abandon_pct"].mean().unstack(0).round(2).to_dict() for pk in ("PM", "AM")}
for n, idx in (("demand", "demand_scale"), ("incidents", "incident_p"), ("split", "stc_share")):
    d = pd.read_csv(f"results/sens_{n}.csv")
    T[n] = d.groupby([idx, "policy"])[["eff_wait", "jain_wait", "abandon_pct"]].mean().round(2).reset_index().to_dict("records")
hd = pd.read_csv("results/sens_headway.csv")
T["headway"] = hd.groupby(["peak", "H"])[["eff_wait", "over_pct", "fleet_busy_pct", "abandon_pct"]].mean().round(2).reset_index().to_dict("records")
json.dump(T, open("results/tables.json", "w"), indent=1)


# ---------------------------------------------------------------- figures
def save(name):
    plt.savefig(f"figures/{name}.png"); plt.close()


# 1 demand profile
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.7))
for a, pk in zip(ax, ("AM", "PM")):
    cfg = Config(peak=pk); t = np.linspace(0, cfg.window, 400)
    h0 = 8 if pk == "AM" else 14
    for j, (lab, c) in enumerate((("STC", "#1F4E79"), ("Main Gate", "#BF9000"))):
        a.plot(t, rate(cfg, j, t), label=lab, color=c, lw=1.8)
    a.set_title(f"{pk} peak ({h0:02d}:00 start)"); a.set_xlabel("minutes after window start"); a.set_ylabel("arrivals / min")
    a.legend(frameon=False)
save("fig_demand")

# 2 baseline queues
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
for a, pk in zip(ax, ("AM", "PM")):
    qs = np.array([q[:, 1:] for q in series[(pk, "S0")]["q"]])
    t = series[(pk, "S0")]["q"][0][:, 0]
    for j, (lab, c) in enumerate((("STC", "#1F4E79"), ("Main Gate", "#BF9000"))):
        m = qs[:, :, j].mean(0); lo, hi = np.percentile(qs[:, :, j], [10, 90], axis=0)
        a.plot(t, m, color=c, label=lab, lw=1.8); a.fill_between(t, lo, hi, color=c, alpha=.15)
    a.set_xlim(0, PEAKS[pk]["window"] + 60); a.set_title(f"S0 baseline, {pk} peak"); a.set_xlabel("minutes after window start"); a.legend(frameon=False)
ax[0].set_ylabel("students waiting")
save("fig_baseline_queue")

# 3 baseline diagnostics
fig, ax = plt.subplots(1, 3, figsize=(7.2, 2.6))
for a, (m, ttl, u) in zip(ax, (("over_pct", "trips over rated capacity", "%"), ("fleet_busy_pct", "fleet busy time", "%"),
                               ("idle_with_queue_busmin", "idle bus-min with queue", "bus-min"))):
    v = [T["main"][pk]["S0"][m][0] for pk in ("AM", "PM")]
    e = [T["main"][pk]["S0"][m][1] for pk in ("AM", "PM")]
    a.bar(["AM", "PM"], v, yerr=e, color=["#9DB7D5", "#1F4E79"], capsize=3); a.set_title(ttl, fontsize=9); a.set_ylabel(u)
    for i, x in enumerate(v): a.text(i, x, f"{x:.0f}", ha="center", va="bottom", fontsize=8)
save("fig_baseline_diag")

# 4 wait CDFs
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
for a, pk in zip(ax, ("AM", "PM")):
    for k in KEYS:
        w = np.sort(np.concatenate([np.concatenate(x) for x in series[(pk, k)]["waits"]]))
        a.plot(w, np.arange(1, len(w) + 1) / len(w), label=NAME[k], color=COL[k], lw=1.6)
    a.set_title(f"{pk} peak (boarded students)"); a.set_xlabel("waiting time (min)"); a.set_xlim(0, 60)
ax[0].set_ylabel("cumulative probability"); ax[1].legend(frameon=False, fontsize=8, loc="lower right")
save("fig_wait_cdf")

# 5 comparison bars
fig, ax = plt.subplots(1, 4, figsize=(7.4, 2.7))
for a, (m, ttl) in zip(ax, (("eff_wait", "effective wait (min)"), ("abandon_pct", "students lost (%)"),
                            ("fleet_busy_pct", "fleet busy (%)"), ("over_pct", "trips > 60 pax (%)"))):
    x = np.arange(2)
    for i, k in enumerate(KEYS):
        v = [T["main"][pk][k][m] for pk in ("AM", "PM")]
        a.bar(x + (i - 1.5) * .2, [z[0] for z in v], .19, yerr=[z[1] for z in v], color=COL[k], label=NAME[k], capsize=1.5)
    a.set_xticks(x); a.set_xticklabels(["AM", "PM"]); a.set_title(ttl, fontsize=9)
fig.legend(*ax[0].get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(.5, -.08), fontsize=8)
save("fig_compare")

# 6 queue S0 vs P3 (PM total)
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
for a, pk in zip(ax, ("AM", "PM")):
    for k in ("S0", "P3"):
        qs = np.array([q[:, 1] + q[:, 2] for q in series[(pk, k)]["q"]]); t = series[(pk, k)]["q"][0][:, 0]
        a.plot(t, qs.mean(0), color=COL[k], label=NAME[k], lw=1.8); a.fill_between(t, *np.percentile(qs, [10, 90], axis=0), color=COL[k], alpha=.15)
    a.set_xlim(0, PEAKS[pk]["window"] + 60); a.set_title(f"total queue, {pk} peak"); a.set_xlabel("minutes after window start")
ax[0].set_ylabel("students waiting"); ax[0].legend(frameon=False)
save("fig_queue_s0_p3")

# 7 load histogram
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=False)
for a, k in zip(ax, ("S0", "P3")):
    ld = series[("PM", k)]["loads"]
    a.hist(ld, bins=np.arange(0, 76, 5), color=COL[k], edgecolor="white"); a.axvline(60, color="k", ls="--", lw=1)
    a.set_title(f"passengers per trip, {NAME[k]} (PM)", fontsize=9); a.set_xlabel("load at departure")
ax[0].set_ylabel("trips (all replications)")
save("fig_loads")

# 8 fleet size
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.9), sharey=True)
for a, pk in zip(ax, ("AM", "PM")):
    for k in ("S0", "P1", "P3"):
        d = T["fleet"][pk][k]; xs = sorted(map(int, d)); a.plot(xs, [d[x if x in d else str(x)] for x in xs], "o-", color=COL[k], label=NAME[k], ms=4)
    base = T["fleet"][pk]["S0"][24]
    a.axhline(base, color=COL["S0"], ls=":", lw=1); a.set_title(f"{pk} peak"); a.set_xlabel("buses in fleet"); a.set_xticks(range(16, 29, 2))
ax[0].set_ylabel("effective wait (min)"); ax[0].legend(frameon=False, fontsize=8)
save("fig_fleet")

# 9 demand split
sp = pd.DataFrame(T["split"])
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.8))
for k in KEYS:
    d = sp[sp.policy == k]
    ax[0].plot(d.stc_share * 100, d.eff_wait, "o-", color=COL[k], label=NAME[k], ms=4)
    ax[1].plot(d.stc_share * 100, d.jain_wait, "o-", color=COL[k], ms=4)
ax[0].set_ylabel("effective wait (min)"); ax[1].set_ylabel("Jain fairness of terminal waits")
for a in ax: a.set_xlabel("STC share of demand (%)")
ax[0].legend(frameon=False, fontsize=8)
save("fig_split")

# 10 headway scan vs P3
hdf = pd.DataFrame(T["headway"])
fig, ax = plt.subplots(1, 2, figsize=(7.2, 2.8))
for a, pk in zip(ax, ("AM", "PM")):
    d = hdf[hdf.peak == pk]
    a.plot(d.H, d.eff_wait, "o-", color=COL["S0"], label="S0 with headway H", ms=4)
    a.axhline(T["main"][pk]["P3"]["eff_wait"][0], color=COL["P3"], label="P3 PAD", lw=1.6)
    a.set_title(f"{pk} peak"); a.set_xlabel("static headway H (min)")
ax[0].set_ylabel("effective wait (min)"); ax[0].legend(frameon=False, fontsize=8)
save("fig_headway")
print("ok")
