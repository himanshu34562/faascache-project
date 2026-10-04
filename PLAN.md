# Plan — 4 Weeks, 4 People

**Status as of kickoff**: environment + submodule + pandas patches verified working. Pipeline runs end-to-end on synthetic data. Real Azure trace not yet pulled. See `README.md` for what the project is and folder layout; `WORKFLOW.md` for exact commands.

---

## The one-paragraph version of what we're doing

The FaaSCache paper shows that treating "which function containers to keep warm" as a caching problem (their Greedy-Dual policy, "GD") beats the naive fixed-timeout approach (TTL) that real platforms use — by 3× on cold-start overhead. We're going to (1) **reproduce** that specific result ourselves, using their own open-sourced simulator, on both a quick synthetic trace and the real Azure Functions trace they used, and (2) **extend** their work with one concrete new idea (see "Our Extension" below) — implement it, test it the same way they tested GD, and report whether it helps, hurts, or doesn't matter.

## Why this is a good project (for our own reference / for the report's motivation section)
- Cold-starts are a real, unsolved-enough problem in production serverless systems — not a toy issue
- The paper's own code and data are public, so we're not reproducing from scratch — de-risks the "nothing works" failure mode
- The core algorithm (Greedy-Dual priority formula) is simple enough to meaningfully extend in a few weeks, but has enough real depth (frequency, cost, size, recency all interacting) that an extension is a genuine design decision, not just parameter-tuning

---

## Roles (fixed for the whole project — ownership, not silos)

| Role | Person | Owns |
|---|---|---|
| **Simulator & Infra Lead** | _TBD_ | Environment, submodule/patches, trace generation (synthetic + real), keeping the pipeline runnable for everyone |
| **Algorithm Lead** | _TBD_ | Designing + implementing the new keep-alive policy (the actual research contribution) |
| **Experiments & Eval Lead** | _TBD_ | Experiment matrix design, running comparisons, producing plots |
| **Writing & Integration Lead** | _TBD_ | Report skeleton, keeping figures/results organized, slides, demo script |

Everyone reads the full paper. These are ownership lanes for debugging/decisions, not strict silos — pair up when stuck (Infra+Algorithm on simulator internals, Eval+Writing on analysis/report).

---

## Week 1 — Reproduce

**Goal**: one working, *meaningful* plot (GD visibly beating TTL, roughly matching the paper's reported magnitude) by end of week.

- [x] Repo + submodule + patches set up and verified (done pre-kickoff)
- [x] Pipeline confirmed working end-to-end on a quick synthetic trace (done pre-kickoff — though first attempt's memory sweep didn't match trace scale, see `WORKFLOW.md` gotcha)
- [ ] Pull real Azure Functions trace data (Infra Lead) — this is the actual Week 1 deliverable's data source, not the synthetic trace
- [ ] Reproduce paper Fig. 5a / Fig. 6a equivalent: representative trace, GD vs TTL vs LRU vs others, across a properly-scaled memory sweep
- [ ] Sanity-check: does GD show meaningfully lower cold-start % / execution-time-increase than TTL, matching the paper's ~3× claim (order of magnitude, not exact numbers — our hardware/trace sampling will differ)?
- [ ] Everyone: read paper Sections 3-4 (keep-alive tradeoffs, Greedy-Dual policy) deeply enough to explain the `Priority = Clock + (Freq × Cost) / Size` formula to a stranger

**What "done" looks like**: a PDF plot in `results/baseline/figs/` showing GD's curve clearly below TTL's, committed nowhere in git (per `.gitignore`) but screenshotted/shared in team chat and referenced in the report draft.

## Week 2 — Validate + Lock Extension

- [ ] Run RARE and RANDOM trace variants too (not just REPRESENTATIVE), confirm LRU catches up to/beats GD on more homogeneous workloads — this is the paper's own reported nuance, good material for our report's discussion
- [ ] As a group, pick ONE extension (write it down, one paragraph, in "Our Extension" below) — this is a hard deadline, don't let week 3 start without this locked

### Extension options (pick one)
1. **Weighted/tunable priority variant** (recommended — most tractable): modify `Priority = Clock + (Freq × Cost) / Size` with tunable weights (e.g. `Clock + w1*(Freq×Cost)/Size^w2`), sweep weights to see if a variant beats plain GD on specific trace types
2. **Generalization test**: run the existing GD policy against a new/different workload trace (newer Azure release, or custom-skewed synthetic) — no new algorithm, tests robustness instead; lower implementation risk, slightly less "novel"
3. **Provisioning policy variant** (stretch, higher difficulty): experiment with the dynamic vertical-scaling controller's deadband/control approach (paper Section 5.2) instead of the keep-alive policy itself

### Our Extension
> _(fill in once decided — one paragraph: what we're changing, why, and what result would count as success. This paragraph becomes the seed of the report's "Our Extension" section.)_

## Week 3 — Build + Run

- [ ] Implement the extension in the simulator (new policy class alongside existing GD/LND/FREQ in `LambdaScheduler.py`, or new trace in `experiments/traces/`, or new controller logic)
- [ ] Unit-test the new policy on a tiny trace before running the full sweep (catch bugs cheap, not after a 20-minute run)
- [ ] Run the full experiment matrix: new approach vs. GD/TTL/LRU, across trace types (REPRESENTATIVE/RARE/RANDOM) and a properly-scaled memory sweep
- [ ] Generate comparison plots, save to `results/extension/figs/`

## Week 4 — Polish + Present

- [ ] Finalize figures (consistent labels/legends/captions, exported at report quality)
- [ ] Write report: Motivation → Background (caching analogy, GDSF formula) → Our Extension → Experimental Setup → Results → Discussion/Limitations
- [ ] Rehearse demo: live simulator run + plot generation (fast, deterministic, low-risk) is the safest demo format — rehearse it to run in under 2 minutes

---

## Decision Rules (avoid thrash — read this when stuck, don't just push through blindly)

- If the chosen extension isn't working by **mid-week 3**, fall back to a simpler version (e.g. drop a predictive/ML idea for a simpler weighted-priority tweak) rather than risk having nothing for week 4
- Trace generation: default to a properly-scaled approach (real Azure data, or a synthetic trace sized to match your memory sweep) — don't repeat the mismatched memory-sweep/trace-size mistake from our first pipeline test
- Real-system OpenWhisk track (paper Appendix A.3.2 — an actual deployed FaaS platform, not just the simulator) is an explicit "only if everything else is done early" stretch goal — do not let it eat into core timeline; the simulator alone is a complete, legitimate project
- If real Azure data processing (Week 1) is taking too long, don't block the whole team — synthetic trace work (extension implementation, policy design) can proceed in parallel while data processing runs in the background

## Deliverables Checklist

- [ ] Reproduced baseline plots (GD/TTL/LRU across ≥2 trace types, properly scaled, real Azure data)
- [ ] Extension implemented and tested
- [ ] Full experiment sweep run and plotted
- [ ] Report draft (all sections)
- [ ] Slides / demo script
- [ ] Final read-through + rehearsal

## Weekly Rhythm
- **Monday** (15 min): confirm this week's tasks from this doc, surface blockers from last week
- **Wed/Thu** (async, team chat): quick progress check-in — "did / doing / blocked on"
- **Friday** (30 min): show what you have, even rough — decide as a group if on track for next week's milestone, update this file's checkboxes