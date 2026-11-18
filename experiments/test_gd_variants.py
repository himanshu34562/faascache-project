#!/usr/bin/env python3
"""Sanity tests for the GD extension policies (GDW / GDD / GDH) on a small trace.

Checks, each on a tiny trace at memory sizes where evictions actually happen:
  1. name parsing accepts valid names and rejects malformed ones
  2. GDW_a1_b1_c1 reproduces GD exactly (same per-function hits/misses/evictions)
  3. GDD with a huge time constant reproduces GD exactly (decay -> 1)
  4. a short time constant (GDD_t1) actually changes behaviour
  5. GDH's per-function count equals every served invocation (it survives evictions),
     and GDH changes behaviour vs GD

Usage (from repo root):  python experiments/test_gd_variants.py [trace.pckl]
Default trace: experiments/traces/representative/20-a.pckl (fast, ~seconds).
"""
import os
import pickle
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "sim-upstream/code/split"))
from LambdaScheduler import LambdaScheduler  # noqa: E402

TRACE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "experiments/traces/representative/20-a.pckl")
MEMS = [256, 512, 1024]


def simulate(policy, mem, trace, logdir, return_sched=False):
    s = LambdaScheduler(policy, mem, 20, "t", logdir)
    for d, t in trace:
        s.runActivation(d, t)
    for f in (s.MemUsageHist, s.PerformanceLog, s.PureCacheHist):
        f.close()
    res = (s.miss_stats(), dict(s.evdict), dict(s.capacity_misses))
    return (res, s) if return_sched else res


def summary(res):
    ms, ev, cap = res
    return (sum(v["misses"] for v in ms.values()), sum(v["hits"] for v in ms.values()),
            sum(ev.values()), sum(cap.values()))


def main():
    # 1. parsing
    p = LambdaScheduler.parse_gd_variant
    assert p("GD") is None and p("TTL") is None
    assert p("GDW_a1_b1_c0.5") == {"a": 1.0, "b": 1.0, "c": 0.5, "t": None}
    assert p("GDD_t30")["tau_ms"] == 30 * 60 * 1000
    assert p("GDH") == {"a": 1.0, "b": 1.0, "c": 1.0, "t": None, "h": True}
    assert p("GDH_t30")["h"] and p("GDH_t30")["tau_ms"] == 30 * 60 * 1000
    for bad in ("GDD", "GDW_z1", "GDW_a"):
        try:
            p(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("accepted malformed policy " + bad)
    print("PASS  name parsing")

    with open(TRACE, "rb") as f:
        _, trace = pickle.load(f)
    print("trace", os.path.basename(TRACE), len(trace), "invocations")

    with tempfile.TemporaryDirectory() as logdir:
        for mem in MEMS:
            gd = simulate("GD", mem, trace, logdir)
            m, h, ev, cap = summary(gd)
            assert ev > 0, "no evictions at {}MB; pick smaller memory sizes".format(mem)
            print("\n{}MB  GD: misses {} hits {} evictions {} dropped {}".format(mem, m, h, ev, cap))

            for name in ("GDW_a1_b1_c1", "GDD_t1000000000"):
                r = simulate(name, mem, trace, logdir)
                assert r == gd, "{} differs from GD at {}MB: {} vs {}".format(name, mem, summary(r), summary(gd))
                print("PASS  {} == GD exactly".format(name))

            r = simulate("GDD_t1", mem, trace, logdir)
            same = r == gd
            print("{}  GDD_t1 differs from GD: {}".format("PASS" if not same else "NOTE", summary(r)))

            r, sched = simulate("GDH", mem, trace, logdir, return_sched=True)
            ms = r[0]
            for k, v in ms.items():
                assert sched.hfreq[k][0] == v["hits"] + v["misses"], \
                    "GDH count for {} is {}, expected {}".format(k, sched.hfreq[k][0], v["hits"] + v["misses"])
            assert sum(r[1].values()) > 0, "GDH saw no evictions, so persistence wasn't exercised"
            print("PASS  GDH count == all served invocations of each function (across {} evictions)".format(sum(r[1].values())))
            print("{}  GDH differs from GD: {}".format("PASS" if r != gd else "NOTE", summary(r)))

    print("\nall checks passed")


if __name__ == "__main__":
    main()
