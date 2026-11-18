# Plan

**Status (2026-11-18)**: baseline reproduced. GD beats TTL by ~3× on cold-start overhead at 8 GB on a real Azure trace. Next: the extension. Deadline: ~2026-11-21.

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

### Day 2 — Extension
- [ ] Implement **GD-W** and **GD-D** (below) in `calc_priority` in `LambdaScheduler.py`
- [ ] Sanity-test each on a tiny trace before any sweep
- [ ] Screen variants at 4 / 8 / 12 GB (~1 min/run)
- [ ] Full 1–16 GB sweep of the best 1–2 variants next to GD/TTL/LRU/FREQ
- [ ] Figures into `results/extension/figs/` via `experiments/plot_baseline.py`

### Day 3 — Write-up
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

**Success criterion**: a variant cuts cold-start overhead vs. GD by a clear margin (≥10% relative) over part of the memory range. A well-explained negative result ("GD's weighting is already near-optimal because…") is also a valid outcome.

**Fallback**: if GD-D shows nothing by mid-Day 2, ship GD-W alone. It's a complete extension by itself.

---

## Decision rules
- Iterate on 3 memory sizes, never the full grid, until a variant is worth a full sweep
- If policies ever look identical again, check dropped requests (`capacity_misses`) before suspecting policy code
- Anything that would take > 1 hour of compute needs a reason to exist before the deadline

## Deliverables
- [x] Reproduced baseline figures (GD/TTL/LRU/LND/HIST/FREQ/SIZE, real Azure trace)
- [ ] Extension implemented and tested
- [ ] Extension sweep run and plotted
- [ ] Report (all sections)
- [ ] Slides / demo script
