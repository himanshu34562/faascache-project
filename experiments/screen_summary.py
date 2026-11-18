#!/usr/bin/env python3
"""Rank extension variants by cold-start overhead relative to GD.

Reads raw many_run.py results from one or more directories (later directories don't
override earlier ones), and prints, per variant, overhead as % of GD's at each memory
size plus the mean across sizes. < 100% means the variant beats GD.

Usage (from repo root):
  python experiments/screen_summary.py results/extension/screen results/baseline/full_day
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_baseline import load  # noqa: E402


def main():
    dirs = sys.argv[1:] or ["results/extension/screen", "results/baseline/full_day"]
    rows = {}
    for d in dirs:
        for mem, pols in load(d, 392, "a").items():
            for p, r in pols.items():
                rows.setdefault(mem, {}).setdefault(p, r)

    # only memory sizes where GD and at least one extension variant both ran
    mems = sorted(m for m in rows if "GD" in rows[m]
                  and any(p.startswith(("GDW", "GDD", "GDX", "GDH")) for p in rows[m]))
    variants = sorted({p for m in mems for p in rows[m]
                       if p.startswith(("GDW", "GDD", "GDX", "GDH")) or p in ("FREQ", "TTL")})
    hdr = "{:22s}".format("policy (% of GD overhead)") + "".join("{:>9s}".format("%dGB" % (m // 1000)) for m in mems) + "{:>9s}".format("mean")
    print(hdr)
    print("-" * len(hdr))
    out = []
    for p in variants:
        vals = [100 * rows[m][p]["overhead_h"] / rows[m]["GD"]["overhead_h"] if p in rows[m] else None for m in mems]
        have = [v for v in vals if v is not None]
        out.append((sum(have) / len(have) if have else float("inf"), p, vals))
    for mean, p, vals in sorted(out):
        print("{:22s}".format(p) + "".join("{:>9s}".format("-" if v is None else "%.1f" % v) for v in vals) + "{:>9.1f}".format(mean))
    print("\nGD overhead (hours):  " + "  ".join("%dGB %.1f" % (m // 1000, rows[m]["GD"]["overhead_h"]) for m in mems))


if __name__ == "__main__":
    main()
