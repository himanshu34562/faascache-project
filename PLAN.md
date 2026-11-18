# Plan

**Status (2026-11-19)**: experiments complete.
- **Baseline reproduced:** GD has ~3× lower cold-start overhead than TTL at 8 GB on the real Azure trace, and this holds on 3 trace seeds.
- **Extension result:** GD-W (cost weighted more, b=2) cuts cold-start overhead a further **~9–17% vs GD**. It beats GD on every seed at every memory size ≥ 4 GB (21/21).

Next: the write-up. Deadline: ~2026-11-21.

See `README.md` for what the project is and the folder layout, and `WORKFLOW.md` for exact commands.

---

## What this project does

The FaaSCache paper shows that deciding which function containers to keep warm is a caching problem. Its Greedy-Dual policy (GD) beats the fixed-timeout approach (TTL) that real platforms use by ~3× on cold-start overhead. This project (1) **reproduces** that result with the paper's own simulator on the real Azure Functions trace, and (2) **extends** GD with one concrete new idea, evaluated the same way.

## Why this is a good project (report motivation)
- Cold starts are a real, still-open problem in production serverless systems
- The paper's code and data are public, so the reproduction rests on the authors' own artifacts
- GD's priority formula is simple enough to extend in days, but its terms (frequency, cost, size, recency) interact enough that the extension is a real design question rather than parameter tuning

---

## Scope decisions (compute-limited: 8-core / 7 GB VM)

- **Trace**: the paper's representative sampling method (392 functions, equal draws from each invocation-frequency quartile, seeded) over the **full 24 h** of Azure day 1. That's 458k invocations, ~1 min per simulation.
- **Excluded functions**: any function whose own cold-start burst (peak rate × cold time × memory) exceeds 2 GB, 1,982 of 36,257 in all. Without this, one sampled function needed ~80 GB of non-evictable running containers and every policy looked identical. Must be stated in the report's setup section; details in `WORKFLOW.md`.
- **Memory sweep**: 1–16 GB in 1 GB steps (the trace's worst-case footprint is ~14 GB).
- **Metric**: cold-start % and **cold-start overhead** (Σ misses × (run_time − warm_time)), the latency the simulator actually charges. Upstream's `% increase in execution time` plot is not used: its analysis reads the two timing fields the opposite way from the simulator (see `WORKFLOW.md`).
- **Cut**: whole-dataset simulation (infeasible; the paper samples too), RARE/RANDOM trace variants, OpenWhisk real-system track. Each becomes one line in Limitations / Future Work.

---

## Status

### Day 1 — Reproduce ✅
- [x] Environment, submodule, pandas 2+ patches
- [x] Raw Azure 2019 data → per-function split (36,257 functions) → representative `392-a` trace
- [x] Trace footprint filter (fixes the "all policies identical" failure)
- [x] Baseline sweep: 7 policies × 16 memory sizes on the full-day trace
- [x] Figures: `cold_pct_mem`, `overhead_mem`, `dropped_mem` in `results/baseline/full_day/figs/`

**Baseline findings** (become the report's Results section):
- GD has the lowest cold-start overhead at every memory size ≥ 3 GB: **2.9× lower than TTL at 8 GB**, 6.7× at 10 GB. That's the paper's headline result.
- Ordering GD < FREQ < LND/SIZE < LRU < TTL < HIST on overhead.
- **FREQ (GD without the size term) is nearly as good as GD**: cost × frequency does most of the work on this trace.
- **SIZE has the fewest cold starts but much higher overhead than GD.** Fewer cold starts ≠ less cold-start time, which is why GD weights by cost.
- HIST is worse than TTL (125–170% of TTL's overhead). Its histogram prewarming doesn't suit this trace.
- Below ~4 GB every policy drops 5–45% of requests and they converge.

### Day 2 — Extension ✅
- [x] Implement **GD-W**, **GD-D** and **GD-H** (below) in `LambdaScheduler.calc_priority`
- [x] Sanity tests (`experiments/test_gd_variants.py`):
  - `GDW_a1_b1_c1` and GD-D with τ→∞ reproduce GD *exactly*
  - GD-H's count equals every served invocation across evictions
  - bonus: `GDW_a1_b1_c0` reproduces the paper's FREQ exactly
- [x] Screen 16 variants at 4 / 8 / 12 GB on seed `a` (`results/extension/screen/`)
- [x] Best of each family × GD/TTL/LRU/FREQ × 2–16 GB × **3 trace seeds** (`392-a/b/c`, `results/extension/seeds/`)
- [x] Figures: `ext_vs_gd-392`, `baseline_vs_gd-392` (+ CSV) in `results/extension/figs/`

**Extension findings** (become the report's Extension Results section):
- **GD-W, b=2** (`Clock + Freq × Cost² / Size`): overhead **89% of GD at 8 GB, 83% at 14 GB**; 82.6–98.2% (mean over seeds) at 4–16 GB. It **beats GD on 3/3 seeds at every size ≥ 4 GB.** At 2 GB everything thrashes and it ties.
- **Screening, all GD-W variants:** more weight on cost (b=2) or less on frequency (a=0.5) helps slightly. More weight on frequency (a=2) hurts by 15–20%. Removing size (c=0, i.e. FREQ) hurts most at high memory. **The paper's equal weighting is close to, but not at, the optimum.**
- **GD-H** (frequency survives eviction): +2–4% on seed `a` did *not* replicate. It lands at 97–103% of GD, on both sides depending on seed and size: no reliable effect. (Good example of why multiple seeds matter.)
- **GD-D** (decayed frequency): neutral to slightly worse (99–102%). Shorter τ is worse (t5 > t30 > t120). Same for decayed GD-H. **On this trace, old popularity is still informative; forgetting it doesn't help.**
- **FREQ** (= GD-W c=0): 106–124% of GD at every size. Re-weighting a term helps; removing one hurts.
- **Reproduction across seeds:** TTL ≈ 3× GD's overhead at 8 GB on all 3 seeds, up to ~9× at 16 GB. LRU tracks TTL to 10 GB, then partly recovers (2× at 16 GB). Only exception: at 4 GB on seed `b`, TTL/LRU are ~6% better than GD.

**Why GD-W works** (`experiments/gdw_mechanism.py`, figure `gdw_mechanism-392`; functions split into quartiles by cold-start cost, 3 seeds):
- **The most expensive quartile (Q4) carries 80–90% of GD's total cold-start overhead.** Q1, the cheapest, carries < 2%.
- GD-W **cuts Q4's cold starts** by 2% / 7.5% / 20% at 4 / 8 / 14 GB, and **Q4's overhead by 3% / 16% / 25%**, on every seed.
- It pays with **more cold starts on cheap functions** (Q1–Q3: +6% to +26%), so **total cold starts go *up*** (+7% / +12% / +19%).
- Net: **overhead falls 2% / 11% / 17%**, because the cold starts it saves are the expensive ones.
- **Interpretation:** squaring the cost term makes GD protect expensive-to-start functions much more strongly. GD-W trades cold-start *count* for cold-start *time*. That's the right trade when the goal is total latency (the paper's metric and ours). It's the wrong one if the goal is the cold-start *rate* or cheap functions' tail latency, so it's a **policy knob, not a free win**. This belongs in the report's Discussion.

### Day 3 — Write-up
- [x] GD-W mechanism analysis (above)
- [ ] Report: Motivation → Background (caching analogy, GD formula) → Reproduction (setup, filter, metric note) → Extension → Results → Discussion / Limitations
- [ ] Slides + demo script (one simulation run + figure generation, < 2 min)

---

## The extension

GD's priority is `Clock + Freq × Cost / Size` (`LambdaScheduler.calc_priority`). The paper's own FREQ and SIZE baselines are GD with one term switched off, so they are fixed points of one generalised formula.

**GD-W (weighted exponents)**
`Priority = Clock + Freq^a × Cost^b / Size^c`
GD = (1,1,1), FREQ = (1,1,0), SIZE = (1,0,1). Sweep a small grid (e.g. a ∈ {0.5, 1, 2}, c ∈ {0, 0.5, 1}). The baseline already shows that size contributes little (FREQ ≈ GD), so this asks whether the paper's equal weighting is actually the best one.

**GD-D (frequency decay)**
GD's `freq` is a running count that never decays while a container stays warm, so a function that was hot hours ago keeps a high priority. Replace it with an exponentially decayed count, `freq ← freq·e^(−Δt/τ) + 1`, and sweep τ (e.g. 5 / 30 / 120 min). The full-day trace has strong time-of-day shifts, which is exactly where stale frequency should hurt.

**GD-H (frequency that survives eviction)**
GD's `freq` only counts accesses while a function has warm containers, so it resets to 0 when they are all evicted. GD-H keeps a per-function count in the scheduler instead (`GDH`, optionally decayed: `GDH_t<min>`). This is the classic in-cache vs. global frequency question from caching (cf. TinyLFU).

Together the three variants each change one part of GD's frequency term:

| Variant | Part of GD it changes |
|---|---|
| GD-W | how the terms are weighted |
| GD-D | how old the frequency information is |
| GD-H | where the frequency information is kept |

**Success criterion**: a variant cuts cold-start overhead vs. GD by a clear margin (≥10% relative) over part of the memory range, **on every trace seed**. ✅ Met by GD-W (b=2).

**Ideas not pursued (Future Work)**: clone-aware eviction (evict surplus idle copies of a bursty function first); admission control / doorkeeper (don't keep one-off containers).

---

## Decision rules
- Iterate on 3 memory sizes, never the full grid, until a variant is worth a full sweep
- If policies ever look identical again, check dropped requests (`capacity_misses`) before suspecting policy code
- Anything that would take > 1 hour of compute needs a reason to exist before the deadline

## Deliverables
- [x] Reproduced baseline figures (GD/TTL/LRU/LND/HIST/FREQ/SIZE, real Azure trace)
- [x] Extension implemented and tested
- [x] Extension sweep run and plotted (3 seeds)
- [ ] Report (all sections)
- [ ] Slides / demo script
