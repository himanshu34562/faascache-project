#!/usr/bin/env python3
"""Why does GD-W beat GD? Break the difference down by cold-start cost.

Functions are split into quartiles by cold-start cost (run_time - warm_time, i.e. Azure
Maximum - Average) within each trace seed. For each quartile it compares a variant with GD:
  - change in number of cold starts (%)
  - change in cold-start overhead (%)
and reports how much of GD's total overhead each quartile carries.

Writes to --outdir:
  gdw_mechanism-392.{pdf,png}  (a) change in cold-start count, (b) change in overhead, per quartile
  gdw_mechanism-392.csv        every number per seed / memory / quartile (table view)

Usage (from repo root):
  python experiments/gdw_mechanism.py --resdir results/extension/seeds --outdir results/extension/figs
"""
import argparse
import csv
import os
import pickle
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "sim-upstream/code/split"))
from LambdaData import LambdaData  # noqa: E402,F401  (needed to unpickle results)
from plot_baseline import INK, MUTED, style_axis  # noqa: E402

# Ordinal encoding for memory size: one hue (blue ramp), light -> dark = smaller -> larger.
MEM_SHADES = ["#86b6ef", "#3987e5", "#1c5cab"]
QLABELS = ["Q1\ncheapest", "Q2", "Q3", "Q4\nmost expensive"]


def load(resdir, policy, mem, seed):
    with open(os.path.join(resdir, "{}-392-{}-{}.pckl".format(policy, mem, seed)), "rb") as f:
        _, _, miss_stats, lambdas, _, _ = pickle.load(f)
    return miss_stats, lambdas


def breakdown(resdir, variant, mem, seed):
    gd, lambdas = load(resdir, "GD", mem, seed)
    var, _ = load(resdir, variant, mem, seed)
    keys = sorted(set(gd) | set(var))
    cost = np.array([lambdas[k][2] - lambdas[k][3] for k in keys], float)
    edges = np.quantile(cost, [0.25, 0.5, 0.75])
    q = np.searchsorted(edges, cost, side="right")
    m_gd = np.array([gd.get(k, {"misses": 0})["misses"] for k in keys], float)
    m_var = np.array([var.get(k, {"misses": 0})["misses"] for k in keys], float)
    ovh_gd_total = (m_gd * cost).sum()
    rows = []
    for b in range(4):
        sel = q == b
        cnt_gd, cnt_var = m_gd[sel].sum(), m_var[sel].sum()
        o_gd, o_var = (m_gd[sel] * cost[sel]).sum(), (m_var[sel] * cost[sel]).sum()
        rows.append({
            "quartile": b + 1,
            "cost_lo_ms": float(cost[sel].min()), "cost_hi_ms": float(cost[sel].max()),
            "cold_gd": int(cnt_gd), "cold_var": int(cnt_var),
            "cold_change_pct": 100 * (cnt_var - cnt_gd) / cnt_gd if cnt_gd else 0.0,
            "ovh_gd_h": o_gd / 3.6e6, "ovh_var_h": o_var / 3.6e6,
            "ovh_change_pct": 100 * (o_var - o_gd) / o_gd if o_gd else 0.0,
            "gd_ovh_share_pct": 100 * o_gd / ovh_gd_total if ovh_gd_total else 0.0,
        })
    total = {"cold_change_pct": 100 * (m_var.sum() - m_gd.sum()) / m_gd.sum(),
             "ovh_change_pct": 100 * ((m_var * cost).sum() - ovh_gd_total) / ovh_gd_total}
    return rows, total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resdir", default="results/extension/seeds")
    ap.add_argument("--outdir", default="results/extension/figs")
    ap.add_argument("--variant", default="GDW_a1_b2_c1")
    ap.add_argument("--seeds", nargs="+", default=["a", "b", "c"])
    ap.add_argument("--mems", type=int, nargs="+", default=[4000, 8000, 14000])
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    base = os.path.join(args.outdir, "gdw_mechanism-392")

    res = {}  # (mem, seed) -> (rows, total)
    for m in args.mems:
        for s in args.seeds:
            res[(m, s)] = breakdown(args.resdir, args.variant, m, s)

    with open(base + ".csv", "w", newline="") as fh:
        cols = ["quartile", "cost_lo_ms", "cost_hi_ms", "cold_gd", "cold_var", "cold_change_pct",
                "ovh_gd_h", "ovh_var_h", "ovh_change_pct", "gd_ovh_share_pct"]
        w = csv.writer(fh)
        w.writerow(["variant", "mem_gb", "seed"] + cols)
        for (m, s), (rows, total) in res.items():
            for r in rows:
                w.writerow([args.variant, m / 1000, s] + [("%.2f" % r[c]) if isinstance(r[c], float) else r[c] for c in cols])
            w.writerow([args.variant, m / 1000, s, "all", "", "", "", "", "%.2f" % total["cold_change_pct"],
                        "", "", "%.2f" % total["ovh_change_pct"], "100.00"])

    # summary (mean [min-max] over seeds)
    def stat(vals):
        return "%+6.1f [%+6.1f,%+6.1f]" % (np.mean(vals), min(vals), max(vals))

    print("{} vs GD, change per cost quartile: mean [min,max] over seeds {}".format(args.variant, args.seeds))
    for m in args.mems:
        print("\n%d GB" % (m // 1000))
        print("  {:16s} {:>26s} {:>26s} {:>18s}".format("quartile", "cold starts (%)", "overhead (%)", "GD overhead share"))
        for b in range(4):
            c = [res[(m, s)][0][b]["cold_change_pct"] for s in args.seeds]
            o = [res[(m, s)][0][b]["ovh_change_pct"] for s in args.seeds]
            sh = [res[(m, s)][0][b]["gd_ovh_share_pct"] for s in args.seeds]
            print("  {:16s} {:>26s} {:>26s} {:>17.1f}%".format(QLABELS[b].replace("\n", " "), stat(c), stat(o), np.mean(sh)))
        c = [res[(m, s)][1]["cold_change_pct"] for s in args.seeds]
        o = [res[(m, s)][1]["ovh_change_pct"] for s in args.seeds]
        print("  {:16s} {:>26s} {:>26s}".format("ALL", stat(c), stat(o)))

    plt.rcParams.update({"font.size": 11, "text.color": INK, "axes.labelcolor": INK})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)
    width = 0.8 / len(args.mems)
    x = np.arange(4)
    for ax, key, title in ((axes[0], "cold_change_pct", "(a) Change in number of cold starts"),
                           (axes[1], "ovh_change_pct", "(b) Change in cold-start overhead")):
        for i, m in enumerate(args.mems):
            vals = np.array([[res[(m, s)][0][b][key] for s in args.seeds] for b in range(4)])
            mean, lo, hi = vals.mean(1), vals.min(1), vals.max(1)
            pos = x - 0.4 + width * (i + 0.5)
            ax.bar(pos, mean, width=width - 0.04, color=MEM_SHADES[i % len(MEM_SHADES)],
                   label="%d GB" % (m // 1000), zorder=2)
            ax.errorbar(pos, mean, yerr=[mean - lo, hi - mean], fmt="none", ecolor=INK,
                        elinewidth=1, capsize=2.5, zorder=3)
        ax.axhline(0, color=MUTED, linewidth=1)
        ax.set_xticks(x)
        ax.set_xticklabels(QLABELS)
        ax.set_xlabel("Functions grouped by cold-start cost (quartiles)")
        ax.set_ylabel("GD-W vs GD (%)")
        ax.set_title(title, loc="left")
        style_axis(ax)
        ax.grid(axis="x", visible=False)
    axes[1].legend(frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5),
                   title="memory; bars = mean,\nwhiskers = min–max\nover {} seeds".format(len(args.seeds)),
                   title_fontsize=9)
    fig.tight_layout()
    for ext in ("pdf", "png"):
        fig.savefig(base + "." + ext, dpi=150, bbox_inches="tight")
    print("\nwrote", base + ".{pdf,png,csv}")


if __name__ == "__main__":
    main()
