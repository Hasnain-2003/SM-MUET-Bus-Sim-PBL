"""
Dispatch policies.  Every policy exposes
    pooled : may any bus serve any terminal?
    cap    : maximum boarding load
    decide(sim) : looks at the state and calls sim.dispatch(bus, terminal)
"""
import math
from .config import STC, MG


class Policy:
    name = "base"
    pooled = False
    cap = 60

    def bind(self, sim):
        self.sim = sim
        self.cfg = sim.cfg

    def decide(self, sim):
        raise NotImplementedError


# ---------------------------------------------------------------------------
class StaticTimetable(Policy):
    """S0 - the current practice as we model it.

    Each terminal owns half the fleet and may release one bus at fixed slots
    (every H minutes).  A slot is lost if no bus is parked at that moment, and
    a parked bus never leaves between slots.  The bus takes whoever fits up to
    the hard physical limit.
    """
    name = "S0 Static timetable"

    def __init__(self, headway=6):
        self.H = headway

    def bind(self, sim):
        super().bind(sim)
        self.cap = sim.cfg.hard_cap

    def decide(self, sim):
        slot = (sim.now % self.H) < 1e-9 or abs((sim.now % self.H) - self.H) < 1e-9
        if not slot:
            return
        for j in (STC, MG):
            if sim.pool[j] and sim.qeff(j) > 0:
                sim.dispatch(sim.pool[j][0], j)


# ---------------------------------------------------------------------------
class LoadOrTimeout(Policy):
    """P1 - demand triggered dispatch, still one half-fleet per terminal.

    A parked bus leaves as soon as (a) a bus-load is waiting or (b) somebody
    has waited longer than W_max and at least q_min students are there.
    """
    name = "P1 Load-or-timeout"

    def __init__(self, theta=54, w_max=10.0, q_min=8):
        self.theta, self.w_max, self.q_min = theta, w_max, q_min

    def bind(self, sim):
        super().bind(sim)
        self.cap = sim.cfg.rated_cap

    def eligible(self, sim, j):
        q = sim.qeff(j)
        if q <= 0:
            return False
        return q >= self.threshold(sim, j) or (q >= self.q_min and sim.oldest_wait(j) >= self.w_max)

    def threshold(self, sim, j):
        return self.theta

    def decide(self, sim):
        for j in (STC, MG):
            if sim.pool[j] and self.eligible(sim, j):
                sim.dispatch(sim.pool[j][0], j)


# ---------------------------------------------------------------------------
class PooledLQF(LoadOrTimeout):
    """P2 - same trigger as P1 but the fleet is one shared pool.

    A free bus goes to whichever terminal has the longest queue (even if that
    means dead-heading across campus).
    """
    name = "P2 Pooled longest-queue-first"
    pooled = True

    def score(self, sim, bus, j):
        return sim.qeff(j)

    def decide(self, sim):
        served = set()
        free = sorted([b for dq in sim.pool for b in dq], key=lambda b: b.ready_since)
        for bus in free:
            cands = [j for j in (STC, MG) if j not in served and self.eligible(sim, j)]
            if not cands:
                continue
            j = max(cands, key=lambda k: self.score(sim, bus, k))
            served.add(j)
            sim.dispatch(bus, j)


# ---------------------------------------------------------------------------
class PAD(PooledLQF):
    """P3 - Predictive Adaptive Dispatch (our proposal).

    Pooled fleet like P2, plus two adaptive ideas.

    1. Scarcity-aware load threshold.  With R buses parked, a bus is released
       once the queue reaches
            theta_j = clip( min(theta_full - k (R - 1),  lambda_hat_j * w_hold), th_min, cap )
       - when many buses are free (R large) the first term is small, so buses
         leave early instead of idling next to a queue;
       - when the fleet is nearly exhausted (R = 1) the first term is
         theta_full, so the last buses are filled properly;
       - lambda_hat is an EWMA of the observed arrival rate (seeded with the
         historical average), so in a lull we do not wait for a load that
         will take forever to build.
    2. Cost-aware assignment.  A free bus goes to the terminal with the best
       score = queue/cap + beta * head-of-line wait / W_max - gamma * dead-head,
       so a bus is only moved across campus when it is worth the 4 minutes.
    """
    name = "P3 PAD (predictive adaptive)"

    def __init__(self, theta_full=54, k=2.0, w_hold=6.0, th_min=12, w_max=10.0,
                 q_min=8, beta=1.0, gamma=0.5):
        super().__init__(theta=theta_full, w_max=w_max, q_min=q_min)
        self.theta_full, self.k, self.w_hold = theta_full, k, w_hold
        self.th_min, self.beta, self.gamma = th_min, beta, gamma

    def threshold(self, sim, j):
        R = len(sim.pool[STC]) + len(sim.pool[MG])
        th = min(self.theta_full - self.k * max(R - 1, 0), sim.lam_hat[j] * self.w_hold)
        return max(self.th_min, min(self.cap, math.ceil(th)))

    def score(self, sim, bus, j):
        move = self.cfg.repos_min if bus.loc != j else 0.0
        return (sim.qeff(j) / self.cap
                + self.beta * sim.oldest_wait(j) / self.w_max
                - self.gamma * move / self.cfg.repos_min)
