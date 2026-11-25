"""
Discrete event model of the MUET Point system, written with SimPy.

Entities
    Passenger : arrives at a terminal, waits FIFO, boards or gives up (reneges)
    Bus       : cycles  ready -> (dead-head) -> boarding -> round trip -> ready
    Controller: wakes every `tick` minutes, purges impatient students, logs the
                queues and asks the active policy which buses to release.

Randomness is pre-drawn per replication (`make_draws`) so every policy sees
exactly the same students and the same bus-trip luck (common random numbers).
"""
from collections import deque
from dataclasses import dataclass, field
import heapq
import numpy as np
import simpy

from .config import Config, PEAKS, STC, MG
from .demand import nhpp_arrivals

K_TRIPS = 12          # max trips a single bus can make in one replication


# ----------------------------------------------------------------------------
# random draws
# ----------------------------------------------------------------------------
@dataclass
class Draws:
    arrivals: list          # [array STC, array MG] arrival times
    patience: list          # [array, array]
    z: np.ndarray           # (N, K) standard normals for trip duration
    inc_u: np.ndarray       # (N, K) uniforms deciding incident
    inc_len: np.ndarray     # (N, K) incident lengths
    init_ready: np.ndarray  # (N,) time each bus first becomes available


def make_draws(cfg: Config, seed: int, n_max: int = 40) -> Draws:
    ss = np.random.SeedSequence(seed)
    s_arr, s_pat, s_trip, s_init = ss.spawn(4)
    ra, rp, rt, ri = (np.random.default_rng(s) for s in (s_arr, s_pat, s_trip, s_init))
    arrivals = [nhpp_arrivals(cfg, j, ra) for j in (STC, MG)]
    patience = [cfg.patience_min + rp.exponential(cfg.patience_mean, size=len(a)) for a in arrivals]
    z = rt.standard_normal((n_max, K_TRIPS))
    inc_u = rt.random((n_max, K_TRIPS))
    inc_len = rt.exponential(cfg.incident_mean, size=(n_max, K_TRIPS))
    if cfg.peak == "PM":
        init_ready = np.zeros(n_max)               # all Points are parked after the morning run
    else:
        # morning: buses are somewhere in their previous cycle, spread over the first hour
        init_ready = ri.permutation(np.linspace(0, 60, n_max, endpoint=False))
    return Draws(arrivals, patience, z, inc_u, inc_len, init_ready)


# ----------------------------------------------------------------------------
# entities
# ----------------------------------------------------------------------------
class Passenger:
    __slots__ = ("t", "deadline", "term", "state")      # state: 0 waiting 1 boarded 2 abandoned

    def __init__(self, t, patience, term):
        self.t, self.deadline, self.term, self.state = t, t + patience, term, 0


class Bus:
    __slots__ = ("id", "home", "loc", "ready_since", "trips")

    def __init__(self, i, home):
        self.id, self.home, self.loc, self.ready_since, self.trips = i, home, home, 0.0, 0


@dataclass
class Result:
    cfg: Config
    waits: list = field(default_factory=lambda: [[], []])       # boarded passengers
    aband_wait: list = field(default_factory=lambda: [[], []])  # waiting time of those who left
    n_arr: list = field(default_factory=lambda: [0, 0])
    trips: list = field(default_factory=list)                   # (t_order, term, load, bus)
    qlen: list = field(default_factory=list)                    # (t, q_stc, q_mg)
    busy_intervals: list = field(default_factory=list)          # (start, end)
    idle_with_queue: float = 0.0                                # bus-minutes idle while students wait
    remaining: int = 0


# ----------------------------------------------------------------------------
# simulator
# ----------------------------------------------------------------------------
class Sim:
    def __init__(self, cfg: Config, policy, draws: Draws):
        self.cfg, self.policy, self.d = cfg, policy, draws
        self.env = simpy.Environment()
        self.q = [deque(), deque()]                  # FIFO of Passenger
        self.nq = [0, 0]                             # waiting (non-abandoned) counts
        self.heap = []                               # (deadline, tiebreak, Passenger)
        self.pool = [deque(), deque()]               # ready buses by location
        self.arr_tick = [0, 0]
        self.reserved = [0, 0]                       # seats already promised to buses en route
        spec = PEAKS[cfg.peak]
        # historical-average prior for the EWMA forecaster (the planner's long-run belief,
        # deliberately NOT updated when we run a what-if with a different demand split)
        self.lam_hat = [spec["demand"][j] * cfg.demand_scale / spec["window"] for j in (STC, MG)]
        self.res = Result(cfg)
        self._ctr = 0
        self.buses = [Bus(i, i % 2) for i in range(cfg.n_buses)]   # even -> STC, odd -> Main Gate
        policy.bind(self)

    # ---- helpers used by policies ----
    @property
    def now(self):
        return self.env.now

    def qeff(self, j):
        """Students still waiting once the buses already on their way have loaded."""
        return self.nq[j] - self.reserved[j]

    def dispatch(self, bus, j):
        """Release `bus` (taken from the ready pool) to terminal j."""
        self.pool[bus.loc].remove(bus)
        res = max(0, min(self.policy.cap, self.qeff(j)))
        self.reserved[j] += res
        self.env.process(self.run_trip(bus, j, self.now, self.policy.cap, res))

    def oldest_wait(self, j):
        dq = self.q[j]
        while dq and dq[0].state != 0:
            dq.popleft()
        return (self.now - dq[0].t) if dq else 0.0

    def trip_time(self, bus, t):
        c = self.cfg
        s2 = np.log(1 + c.rt_cv ** 2)
        mu = np.log(c.rt_mean) - s2 / 2
        k = min(bus.trips, K_TRIPS - 1)
        base = np.exp(mu + np.sqrt(s2) * self.d.z[bus.id, k]) * PEAKS[c.peak]["congestion"]
        if self.d.inc_u[bus.id, k] < c.incident_p:
            base += self.d.inc_len[bus.id, k]
        return float(base)

    # ---- processes ----
    def arrivals(self, j):
        env = self.env
        for t, pat in zip(self.d.arrivals[j], self.d.patience[j]):
            yield env.timeout(t - env.now)
            p = Passenger(env.now, pat, j)
            self.q[j].append(p)
            self.nq[j] += 1
            self.arr_tick[j] += 1
            self.res.n_arr[j] += 1
            self._ctr += 1
            heapq.heappush(self.heap, (p.deadline, self._ctr, p))

    def purge(self):
        while self.heap and self.heap[0][0] <= self.now:
            dl, _, p = heapq.heappop(self.heap)
            if p.state == 0:
                p.state = 2
                self.nq[p.term] -= 1
                self.res.aband_wait[p.term].append(dl - p.t)

    def bus_arrive_ready(self, bus):
        bus.ready_since = self.now
        self.pool[bus.loc].append(bus)

    def bus_init(self, bus):
        env = self.env
        t0 = float(self.d.init_ready[bus.id])
        if t0 > 0:
            self.res.busy_intervals.append((0.0, t0))
            yield env.timeout(t0)
            if self.policy.pooled:
                bus.loc = MG
            else:
                if bus.home == STC:
                    yield env.timeout(self.cfg.repos_min)
                bus.loc = bus.home
        self.bus_arrive_ready(bus)

    def run_trip(self, bus, j, t_order, cap, res):
        env, c = self.env, self.cfg
        if bus.loc != j:                               # dead-head to the other terminal
            yield env.timeout(c.repos_min)
            bus.loc = j
        self.reserved[j] -= res
        self.purge()
        load = []
        dq = self.q[j]
        while dq and len(load) < cap:
            p = dq.popleft()
            if p.state == 0:
                p.state = 1
                self.nq[j] -= 1
                load.append(p)
        n = len(load)
        if n == 0:                                     # everyone gave up while we dead-headed
            self.res.busy_intervals.append((t_order, env.now))
            self.bus_arrive_ready(bus)
            return
        for p in load:
            self.res.waits[j].append(env.now - p.t)
        self.res.trips.append((env.now, j, n, bus.id))
        yield env.timeout(c.dwell_fixed + c.dwell_per_pax * n)
        yield env.timeout(self.trip_time(bus, env.now))
        bus.trips += 1
        self.res.busy_intervals.append((t_order, env.now))
        if self.policy.pooled:
            bus.loc = MG                               # route enters campus at the Main Gate
        else:
            if bus.home == STC:
                yield env.timeout(c.repos_min)
            bus.loc = bus.home
        self.bus_arrive_ready(bus)

    def controller(self):
        env, c = self.env, self.cfg
        a = 0.2
        while True:
            self.purge()
            for j in (STC, MG):
                self.lam_hat[j] = (1 - a) * self.lam_hat[j] + a * self.arr_tick[j] / c.tick
                self.arr_tick[j] = 0
            self.res.qlen.append((env.now, self.nq[STC], self.nq[MG]))
            if env.now <= c.window + 1e-9:
                for j in (STC, MG):
                    if self.nq[j] > 0:
                        self.res.idle_with_queue += len(self.pool[j]) * c.tick
            self.policy.decide(self)
            yield env.timeout(c.tick)

    def run(self):
        env = self.env
        for j in (STC, MG):
            env.process(self.arrivals(j))
        for b in self.buses:
            env.process(self.bus_init(b))
        env.process(self.controller())
        env.run(until=self.cfg.horizon)
        self.res.remaining = sum(1 for dq in self.q for p in dq if p.state == 0)
        return self.res


def run_once(cfg: Config, policy, seed: int, draws: Draws = None) -> Result:
    d = draws if draws is not None else make_draws(cfg, seed)
    return Sim(cfg, policy, d).run()
