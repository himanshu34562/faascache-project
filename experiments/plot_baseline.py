#!/usr/bin/env python3
"""Report figures for a policy x memory sweep, in one consistent style.

Figures (each with a .csv table view of the same numbers):
  cold_pct_mem-{n}   -- % of served invocations that were cold starts (same metric as
                        upstream plot_cold_across_mem.py; dropped requests excluded)
  overhead_mem-{n}   -- (a) total cold-start overhead (hours), (b) relative to TTL
  dropped_mem-{n}    -- % of invocations dropped (no memory even after eviction)

Use these instead of upstream's exec_inc_mem plot -- see below.

Why this exists (alongside upstream's plot_run_across_mem.py):
the simulator runs a warm hit for `warm_time` (Azure Average) and a cold start for
`run_time` (Azure Maximum), so each miss costs `run_time - warm_time` extra -- the same
`cost` GD's priority uses. Upstream's analyze_timings() instead treats `warm_time` as the
cold penalty and `run_time - warm_time` as the base run time (ratio inverted), which on this
trace is dominated by a few functions with Maximum ~= Average. See WORKFLOW.md.

Reads raw many_run.py outputs ({policy}-{n}-{mem}-{char}.pckl).
"""
import argparse
import csv
import os
import pickle
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "sim-upstream/code/split"))
from LambdaData import LambdaData  # noqa: F401  (needed to unpickle results)

# Fixed policy -> colour/marker mapping (colour follows the entity, never its rank).
# Categorical slots 1-7 of the dataviz reference palette, in documented order.
STYLE = {
    "GD":   ("#2a78d6", "o"),
    "TTL":  ("#eb6834", "s"),
    "LRU":  ("#1baf7a", "^"),
    "LND":  ("#eda100", "D"),
    "HIST": ("#e87ba4", "v"),
    "FREQ": ("#008300", "P"),
    "SIZE": ("#6250d6", "X"),
}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3de"


def load(resdir, numfuncs, char):
    rows = defaultdict(dict)  # mem_mb -> policy -> metrics
    for f in os.listdir(resdir):
        if not f.endswith("-{}.pckl".format(char)):
            continue
        parts = f[:-5].split("-")
        if len(parts) != 4 or int(parts[1]) != numfuncs:
            continue
        policy, mem = parts[0], int(parts[2])
        with open(os.path.join(resdir, f), "rb") as fh:
            _, _, miss_stats, lambdas, cap, n = pickle.load(fh)
        misses = sum(v["misses"] for v in miss_stats.values())
        hits = sum(v["hits"] for v in miss_stats.values())
        overhead_ms = sum(v["misses"] * (lambdas[k][2] - lambdas[k][3]) for k, v in miss_stats.items())
        warm_ms = sum((v["misses"] + v["hits"]) * lambdas[k][3] for k, v in miss_stats.items())
        rows[mem][policy] = {
            "cold_pct": 100.0 * misses / max(misses + hits, 1),
            "overhead_h": overhead_ms / 3.6e6,
            "exec_increase_pct": 100.0 * overhead_ms / max(warm_ms, 1),
            "dropped_pct": 100.0 * sum(cap.values()) / n,
        }
    return rows


def style_axis(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resdir", required=True, help="dir with raw many_run.py .pckl outputs")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--numfuncs", type=int, default=392)
    ap.add_argument("--char", default="a")
    ap.add_argument("--policies", nargs="+", default=list(STYLE))
    args = ap.parse_args()

    rows = load(args.resdir, args.numfuncs, args.char)
    mems = sorted(rows)
    policies = [p for p in args.policies if any(p in rows[m] for m in mems)]
    os.makedirs(args.outdir, exist_ok=True)
    n = args.numfuncs
    plt.rcParams.update({"font.size": 11, "text.color": INK, "axes.labelcolor": INK})

    def series(p, fn):
        pts = [(m / 1000, fn(rows[m])) for m in mems if p in rows[m]]
        return [x for x, y in pts if y is not None], [y for x, y in pts if y is not None]

    def draw(ax, fn):
        for p in policies:
            color, marker = STYLE.get(p, (MUTED, "."))
            xs, ys = series(p, lambda r, p=p: fn(r, p))
            if xs:
                ax.plot(xs, ys, color=color, marker=marker, markersize=5, linewidth=2, label=p)
        ax.set_xlabel("Server memory (GB)")
        style_axis(ax)

    def save(fig, ax_legend, name, cols):
        ax_legend.legend(frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
        fig.tight_layout()
        base = os.path.join(args.outdir, "{}-{}".format(name, n))
        for ext in ("pdf", "png"):
            fig.savefig(base + "." + ext, dpi=150, bbox_inches="tight")
        plt.close(fig)
        with open(base + ".csv", "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["mem_gb", "policy"] + cols)
            for m in mems:
                for p in policies:
                    if p in rows[m]:
                        w.writerow([m / 1000, p] + ["%.3f" % rows[m][p][c] for c in cols])
        print("wrote", base + ".{pdf,png,csv}")

    # 1. cold-start percentage
    fig, ax = plt.subplots(figsize=(6, 4))
    draw(ax, lambda r, p: r[p]["cold_pct"])
    ax.set_ylabel("Cold starts (% of served invocations)")
    ax.set_ylim(bottom=0)
    save(fig, ax, "cold_pct_mem", ["cold_pct"])

    # 2. cold-start overhead: absolute + relative to TTL
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    draw(a1, lambda r, p: r[p]["overhead_h"])
    a1.set_yscale("log")
    a1.set_ylabel("Total cold-start overhead (hours, log)")
    a1.set_title("(a) Cold-start overhead", loc="left")
    draw(a2, lambda r, p: 100 * r[p]["overhead_h"] / r["TTL"]["overhead_h"]
         if "TTL" in r and r["TTL"]["overhead_h"] > 0 else None)
    a2.axhline(100, color=MUTED, linewidth=1, linestyle="--")
    a2.set_ylabel("Overhead relative to TTL (%)")
    a2.set_title("(b) Relative to TTL (lower is better)", loc="left")
    save(fig, a2, "overhead_mem", ["overhead_h", "exec_increase_pct"])

    # 3. dropped requests
    fig, ax = plt.subplots(figsize=(6, 4))
    draw(ax, lambda r, p: r[p]["dropped_pct"])
    ax.set_ylabel("Dropped invocations (%)")
    ax.set_ylim(bottom=0)
    save(fig, ax, "dropped_mem", ["dropped_pct"])


if __name__ == "__main__":
    main()
