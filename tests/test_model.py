"""
Verification tests for the simulator.   Run with:  PYTHONPATH=src pytest -q

1. conservation        every student is boarded, abandoned or still waiting
2. Little's law        integral of queue length = sum of individual waits
3. analytic batch wait mean wait = (K-1)/(2*lambda) when buses are plentiful
4. deterministic trace hand-computed loads and dispatch times
5. capacity limits     policies never exceed their cap
6. reproducibility     same seed -> same numbers; CRN across policies
"""
import numpy as np
import pytest
from busqueue import Config, run_once, summarise, make_draws, config
from busqueue.model import Draws, Sim
from busqueue.policies import StaticTimetable, LoadOrTimeout, PooledLQF, PAD


def test_conservation():
    for P in (StaticTimetable, LoadOrTimeout, PooledLQF, PAD):
        for peak in ("AM", "PM"):
            res = run_once(Config(peak=peak), P(), seed=3)
            n = sum(res.n_arr)
            got = len(res.waits[0]) + len(res.waits[1]) + len(res.aband_wait[0]) + len(res.aband_wait[1]) + res.remaining
            assert n == got, (P.name, peak, n, got)


def test_littles_law():
    errs = []
    for seed in range(10):
        cfg = Config(peak="PM")
        res = run_once(cfg, PAD(), seed)
        q = np.array(res.qlen)
        area = (q[:, 1] + q[:, 2]).sum() * cfg.tick
        total_wait = sum(map(sum, res.waits)) + sum(map(sum, res.aband_wait))
        total_wait += 0  # students still waiting at the horizon are ~0
        errs.append(abs(area - total_wait) / total_wait)
    assert np.mean(errs) < 0.03, errs


def test_analytic_batch_wait():
    config.PEAKS["TEST"] = dict(window=600.0, demand=(1800, 1), bumps=[(300.0, 1e7, 1.0)],
                                congestion=1.0, start="00:00")
    K, lam = 30, 3.0
    cfg = Config(peak="TEST", n_buses=40, tick=0.02, rt_mean=60, drain=60)
    waits = []
    for seed in range(6):
        res = run_once(cfg, LoadOrTimeout(theta=K, w_max=1e9, q_min=10 ** 9), seed)
        waits += res.waits[0]
    expected = (K - 1) / (2 * lam)
    assert abs(np.mean(waits) - expected) / expected < 0.06, (np.mean(waits), expected)


def test_deterministic_trace():
    cfg = Config(peak="PM", n_buses=2, rt_cv=0.0, incident_p=0.0)
    d = Draws(arrivals=[np.full(130, 0.5), np.array([])],
              patience=[np.full(130, 1e9), np.array([])],
              z=np.zeros((40, 12)), inc_u=np.ones((40, 12)), inc_len=np.zeros((40, 12)),
              init_ready=np.zeros(40))
    res = Sim(cfg, LoadOrTimeout(theta=60, w_max=5, q_min=8), d).run()
    loads = [t[2] for t in res.trips]
    times = [t[0] for t in res.trips]
    assert loads == [60, 60, 10]
    # trip 1 leaves at the first tick after arrival (t=1); the bus is back after
    # dwell 0.5+0.04*60 + trip 72*1.05 + 4 min dead-head, i.e. ready at 83.5 -> tick 84
    assert times[:2] == [1.0, 84.0]


def test_capacity_limits():
    for seed in range(5):
        cfg = Config()
        assert max(t[2] for t in run_once(cfg, PAD(), seed).trips) <= cfg.rated_cap
        assert max(t[2] for t in run_once(cfg, LoadOrTimeout(), seed).trips) <= cfg.rated_cap
        assert max(t[2] for t in run_once(cfg, StaticTimetable(), seed).trips) <= cfg.hard_cap


def test_reproducible_and_crn():
    cfg = Config()
    a = summarise(run_once(cfg, PAD(), 7))
    b = summarise(run_once(cfg, PAD(), 7))
    assert a == b
    arr = {P.name: summarise(run_once(cfg, P(), 7))["arrivals"] for P in (StaticTimetable, PAD)}
    assert len(set(arr.values())) == 1
