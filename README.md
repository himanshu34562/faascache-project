# FaaSCache Project
### Reproducing and Extending Greedy-Dual Keep-Alive Policies for Serverless Cold-Start Mitigation

A course project (Cloud Computing, IIT Delhi) building on: Fuerst & Sharma, *"FaasCache: Keeping Serverless Computing Alive with Greedy-Dual Caching,"* ASPLOS 2021. [[paper PDF](https://homes.luddy.indiana.edu/prateeks/papers/faascache-asplos21.pdf)] [[upstream code](https://github.com/aFuerst/faascache-sim)]

---

## What this project is

Serverless (FaaS) platforms suffer from **cold-start latency**: every time a function's container isn't already warm, the platform pays a real startup cost (loading the runtime, dependencies, etc.) before your code even runs. Keeping containers "warm" avoids this, but warm containers eat server memory — so platforms need a **keep-alive policy** to decide which containers to evict when memory is tight.

The FaaSCache paper's core insight: **keep-alive is equivalent to object caching**. They adapt a caching algorithm (Greedy-Dual-Size-Frequency, "GD") into a keep-alive policy, and show it cuts cold-start overhead by 3× and application latency by 6× compared to the naive fixed-timeout (TTL) policy most real platforms use.

**This project**: (1) reproduce their core result using their own open-sourced simulator on the real Azure trace, (2) extend GD with a new variation. See `PLAN.md` for exactly what changes and why.

---

## Folder-by-folder guide

```
faascache-project/
├── sim-upstream/              # The paper's own simulator code (git submodule, see below)
├── experiments/
│   ├── gen_synthetic_trace.py # Generates a small synthetic FaaS workload trace — use this for fast pipeline sanity-checks, NOT for final results
│   ├── plot_baseline.py        # Report figures (cold-start %, cold-start overhead, dropped requests) from a sweep's raw results
│   ├── test_gd_variants.py     # Sanity tests for the extension policies (GD-W / GD-D / GD-H)
│   ├── screen_summary.py       # Ranks extension variants by overhead relative to GD
│   ├── seed_summary.py         # Robustness across trace seeds: figures + table vs GD
│   ├── policies/               # Placeholder (the extension policies live in LambdaScheduler.py)
│   └── traces/                 # Trace .pckl files live here (gitignored — regenerate locally; see "How to get trace data" below)
├── results/
│   ├── baseline/full_day/       # Reproduced GD/TTL/LRU/etc. results on the full-day 392-a trace — raw output + analyzed/ + figs/
│   └── extension/               # screen/ (variant screening), seeds/ (3-seed sweep), figs/ (extension figures)
├── notebooks/                  # Scratch analysis / exploratory plotting (Jupyter)
├── report/                      # Final report drafts, polished figures, slides
├── requirements.txt             # Exact Python package versions
├── .gitignore
├── README.md                    # you are here — what the project is, folder guide, how to reproduce
├── WORKFLOW.md                   # HOW: exact verified commands, known bugs/patches, gotchas, git conventions
└── PLAN.md                       # WHAT: status, scope decisions, baseline findings, the extension
```

### What's inside `sim-upstream/` (the submodule)
This is the paper authors' own code, unmodified except for a small set of patches (pandas 2+ compatibility, portable paths, CLI flags, a trace footprint filter — all documented in `WORKFLOW.md`). Key pieces:
- `code/split/LambdaScheduler.py`, `Container.py`, `LambdaData.py` — the actual discrete-event simulator logic (this is where a new keep-alive policy gets added)
- `code/split/many_run.py` — driver script: runs the simulator across multiple policies × memory sizes in parallel
- `code/split/gen/` — scripts to turn the raw Azure Functions trace dataset into a usable trace file
- `code/split/plotting/` — scripts that turn raw simulation output into the paper's actual figures (cold-start %, execution-time-increase %, vs. memory size)

The upstream `master` branch is never edited directly. All patches live on the `patches` branch inside the submodule (see `WORKFLOW.md`).

### What's inside `experiments/`
This is the project's own code, separate from the paper's. `gen_synthetic_trace.py` builds a small fake workload for quick pipeline tests. `plot_baseline.py` produces all report figures from a sweep. The extension policy (see `PLAN.md`) is added next to GD in `LambdaScheduler.py`.

### What's inside `results/`
Simulator output, split into `baseline/` (reproducing the paper's existing policies) and `extension/` (the new policy's results). Each has the same sub-structure: raw `.pckl` simulation output → `analyzed/` (processed stats) → `figs/` (actual plots). Raw data and figures are gitignored (regenerable, often large) — only the code that produces them is tracked.

---

## Setup (first time)

```bash
git clone --recurse-submodules <this-repo-url>
cd faascache-project

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

If `--recurse-submodules` was forgotten when cloning, `sim-upstream/` will be empty — fix with:
```bash
git submodule update --init --recursive
```

**After every `git pull`**, resync:
```bash
git submodule update --init --recursive
pip install -r requirements.txt
```

Verify your setup:
```bash
cd sim-upstream/code/split
python3 -c "from LambdaScheduler import LambdaScheduler; print('imports OK')"
```

---

## How to reproduce the baseline (quick version)

Full verified commands, gotchas and patches are in **`WORKFLOW.md`**. Read that before running anything for real. The pipeline:

1. **Trace**: Azure raw data → `trace_split_funcs.py` (one pickle per function) → `gen_representative_trace.py --sizes 392 --runs a` (the 392-function representative trace)
2. **Sweep**: `many_run.py --char a --memmin 1000 --memmax 17000 --memstep 1000` (7 policies × 16 memory sizes, ~25 min on 6 cores)
3. **Figures**: `experiments/plot_baseline.py` (cold-start %, cold-start overhead, dropped requests, each with a CSV)

**Key results**:
- GD's cold-start overhead is ~3× lower than TTL's at 8 GB, matching the paper (holds on 3 trace seeds).
- The extension GD-W (`Clock + Freq × Cost² / Size`) cuts overhead a further ~9–17% vs GD, on every seed at every memory size ≥ 4 GB.

Details in `PLAN.md`; extension commands in `WORKFLOW.md`.

## How to get real trace data
The paper uses the [Azure Functions 2019 trace dataset](https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md). This is the data needed for results comparable to the paper; the synthetic trace is only for pipeline sanity checks. Processing takes roughly an hour for stage 1 and under a minute for stage 2 (see `WORKFLOW.md`).

---

## Lessons learned (read before changing anything)

- **Always confirm `pwd` before running a command block.** Most early setup errors were path-related, not logic errors.
- **If every policy looks identical, check dropped requests first.** It means memory is pinned by running containers (or nothing is ever evicted), not that the policies are broken. See the footprint filter in `WORKFLOW.md`.
- **Iterate on a few memory sizes, not the full grid.** One simulation is ~1 min; the full grid is ~25 min.
- **Don't trust upstream's `% increase in execution time` plot.** Its analysis reads the timing fields the opposite way from the simulator. Use `experiments/plot_baseline.py`.
- **Don't commit raw `.pckl` results, traces or figures.** They're gitignored on purpose; only the code that generates them belongs in git.

---

## Quick links
- **Status, scope decisions, baseline findings, the extension** → `PLAN.md`
- **Exact verified commands, known bugs + fixes, git/submodule conventions** → `WORKFLOW.md`
- Paper's own setup instructions (Artifact Appendix, Section A): useful, but some paths differ from reality; `WORKFLOW.md` has the corrections
