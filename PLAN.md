# Plan — 4 Weeks, 4 People

**Status as of kickoff**: environment + submodule + pandas patches verified working. Pipeline runs end-to-end on synthetic data. Real Azure trace not yet pulled.

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

**Goal**: one working, meaningful plot (GD visibly beating TTL) by end of week.

- [x] Repo + submodule + patches set up and verified (done pre-kickoff)
- [ ] Pull real Azure Functions trace data (or use a properly-scaled synthetic trace as an interim check — see `WORKFLOW.md` gotcha on matching memory sweep to trace scale)
- [ ] Reproduce paper Fig. 5a / Fig. 6a equivalent (representative trace, GD vs TTL vs LRU etc. across memory sweep)
- [ ] Sanity-check: does GD show meaningfully lower cold-start % / execution-time-increase than TTL, matching the paper's ~3× claim (order of magnitude, not exact numbers)?

## Week 2 — Validate + Lock Extension

- [ ] Run RARE and RANDOM trace variants too, confirm LRU catches up to/beats GD on more homogeneous workloads (paper's reported nuance)
- [ ] As a group, pick ONE extension (write it down, one paragraph, in this file under "Our Extension" below)

### Extension options (pick one)
1. **Weighted/tunable priority variant** (recommended — most tractable): modify `Priority = Clock + (Freq × Cost) / Size` with tunable weights, sweep to see if a variant beats plain GD on specific trace types
2. **Generalization test**: run existing GD policy against a new/different workload trace (newer Azure release, or custom-skewed synthetic) — no new algorithm, tests robustness instead
3. **Provisioning policy variant** (stretch, higher difficulty): experiment with the dynamic vertical-scaling controller's deadband/control approach

### Our Extension
> _(fill in once decided — what we're changing, why, what result counts as success)_

## Week 3 — Build + Run

- [ ] Implement the extension in the simulator (new policy class alongside existing GD/LND/FREQ, or new trace, or new controller)
- [ ] Run the full experiment matrix: new approach vs. GD/TTL/LRU, across trace types and a properly-scaled memory sweep
- [ ] Generate comparison plots

## Week 4 — Polish + Present

- [ ] Finalize figures (consistent labels/legends/captions)
- [ ] Write report: Motivation → Background → Our Extension → Setup → Results → Discussion/Limitations
- [ ] Rehearse demo (live simulator run + plot, or walkthrough of pre-generated results if live run is too slow)

---

## Decision Rules (avoid thrash)

- If the chosen extension isn't working by **mid-week 3**, fall back to a simpler version rather than risk having nothing for week 4
- Trace generation: default to a properly-scaled approach (real data or scaled synthetic) — don't re-waste time on a mismatched memory-sweep/trace-size plot like our first test run
- Real-system OpenWhisk track (paper Appendix A.3.2) is an explicit "only if everything else is done early" stretch goal — do not let it eat into core timeline

## Deliverables Checklist

- [ ] Reproduced baseline plots (GD/TTL/LRU across ≥2 trace types, properly scaled)
- [ ] Extension implemented and tested
- [ ] Full experiment sweep run and plotted
- [ ] Report draft (all sections)
- [ ] Slides / demo script
- [ ] Final read-through + rehearsal

## Weekly Rhythm
- **Monday** (15 min): confirm this week's tasks, surface blockers from last week
- **Wed/Thu** (async): quick progress check-in in team chat
- **Friday** (30 min): show what you have, even rough — decide if on track for next week