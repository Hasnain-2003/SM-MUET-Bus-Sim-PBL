# MUET Point Bus Scheduling: Discrete Event Simulation

Simulation & Modelling, Problem Based Learning (Department of Software Engineering, MUET Jamshoro).
Author: Hasnain Aijaz Ansari (22SW130). Submitted to Sir Umar Farooque.

A SimPy model of the MUET Point (bus) system during the 08:00-09:00 and 14:00-15:30 peaks. It reproduces the
symptoms of the current static timetable (long queues at STC and Main Gate, over-capacity buses, idle buses
beside waiting students) and compares three dispatch policies on the **same fleet, with no new buses**.

| Key | Policy |
|-----|--------|
| S0 | Static timetable (current practice as modelled): half the fleet per terminal, fixed 6-min slots, loads up to 70 |
| P1 | Load-or-timeout: release a bus when a load is waiting or the head of the line has waited too long; cap 60 |
| P2 | P1 trigger with one pooled fleet, longest-queue-first |
| P3 | PAD, Predictive Adaptive Dispatch: pooled fleet, EWMA-forecast threshold, dead-head-aware assignment |

## Important: inputs are assumptions
There are no measured MUET ridership logs in this project. Demand, round-trip times, capacities and patience in
`src/busqueue/config.py` are realistic assumptions calibrated so the baseline shows the problem described in the
brief. Absolute numbers are indicative; comparisons between policies are the trustworthy part. Replace the values in
`config.py` with counts from the transport office and re-run everything (see the report, Section VI and XI).

## Layout
```
src/busqueue/   config.py (all inputs)  demand.py (NHPP thinning)  model.py (SimPy entities/processes)
                policies.py (S0, P1, P2, PAD)  metrics.py
tests/          test_model.py (6 verification tests)
tune.py         parameter search on training seeds 1000-1029
run_experiments.py   all scenarios, evaluation seeds 0..199 (main) / 0..99 (sensitivity)
analyze.py      figures + results/tables.json
verify_numbers.py    numeric outcome of the Little's-law and analytic checks
build_report.py      builds the Word report from results (needs python-docx and the sample cover file)
diagrams/       Graphviz sources of the conceptual-model figures
figures/ results/    generated outputs (CSV, JSON)
```

## Run it
Python 3.10+ (tested with 3.12).
```bash
pip install -r requirements.txt
export PYTHONPATH=src            # Windows PowerShell:  $env:PYTHONPATH = "src"
pytest -q                        # 6 tests, a few seconds
python tune.py                   # optional: re-tune policies (about 1 min)
python run_experiments.py        # full suite, about 10 min on one core (--quick for a smoke test)
python analyze.py                # figures and tables
```
Graphviz (`dot`) is only needed to redraw the diagrams: `dot -Tpng diagrams/system.dot -o figures/diag_system.png`.

## Quick example
```python
from busqueue import Config, run_once, summarise
from busqueue.policies import StaticTimetable, PAD
cfg = Config(peak="PM")
print(summarise(run_once(cfg, StaticTimetable(), seed=1))["eff_wait"])
print(summarise(run_once(cfg, PAD(theta_full=60, k=0, w_hold=14, th_min=10, w_max=20, gamma=0.25), seed=1))["eff_wait"])
```

## Design notes
* Terminating simulation, no warm-up; every replication ends after the queues drain (window + 150 min).
* Common random numbers: the same students and the same trip "luck" per (bus, trip index) under every policy, so policies are compared with paired differences.
* Effective wait = (sum of boarded waits + sum of (wait + 60 min) for students who gave up) / arrivals.
* Parameters are tuned on seeds 1000-1029 and evaluated on seeds 0.., never on the tuning seeds.

## Publish to GitHub
```bash
git init && git add . && git commit -m "MUET Point bus scheduling simulation"
git branch -M main
git remote add origin https://github.com/<your-username>/muet-bus-sim.git
git push -u origin main
```
