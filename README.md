# FaaSCache Project
### Reproducing and Extending Greedy-Dual Keep-Alive Policies for Serverless Cold-Start Mitigation

A course project (Cloud Computing, IIT Delhi) building on: Fuerst & Sharma, *"FaasCache: Keeping Serverless Computing Alive with Greedy-Dual Caching,"* ASPLOS 2021. [[paper PDF](https://homes.luddy.indiana.edu/prateeks/papers/faascache-asplos21.pdf)] [[upstream code](https://github.com/aFuerst/faascache-sim)]

---

## What this project is

Serverless (FaaS) platforms suffer from **cold-start latency**: every time a function's container isn't already warm, the platform pays a real startup cost (loading the runtime, dependencies, etc.) before your code even runs. Keeping containers "warm" avoids this, but warm containers eat server memory — so platforms need a **keep-alive policy** to decide which containers to evict when memory is tight.

The FaaSCache paper's core insight: **keep-alive is equivalent to object caching**. They adapt a caching algorithm (Greedy-Dual-Size-Frequency, "GD") into a keep-alive policy, and show it cuts cold-start overhead by 3× and application latency by 6× compared to the naive fixed-timeout (TTL) policy most real platforms use.

**Our project**: (1) reproduce their core result using their own open-sourced simulator, (2) extend it with our own variation — see `PLAN.md` for exactly what we're changing and why.

---

## Folder-by-folder guide

```
faascache-project/
├── sim-upstream/              # The paper's own simulator code (git submodule, see below)
├── experiments/
│   ├── gen_synthetic_trace.py # Generates a small synthetic FaaS workload trace — use this for fast pipeline sanity-checks, NOT for final results
│   ├── policies/               # [WE WRITE THIS] Our new/extended keep-alive policy implementation goes here
│   └── traces/                 # Trace .pckl files live here (gitignored — regenerate locally; see "How to get trace data" below)
├── results/
│   ├── baseline/                # Reproduced GD/TTL/LRU/etc. results — simulator output + analyzed stats + figures
│   └── extension/               # Results from our new policy, same structure as baseline/
├── notebooks/                  # Scratch analysis / exploratory plotting (Jupyter)
├── report/                      # Final report drafts, polished figures, slides
├── requirements.txt             # Exact Python package versions — see WORKFLOW.md for how this is maintained
├── .gitignore
├── README.md                    # you are here — what the project is, folder guide, how to reproduce
├── WORKFLOW.md                   # HOW: exact verified commands, known bugs/patches, gotchas, git conventions
└── PLAN.md                       # WHAT/WHO: week-by-week tasks, role assignments, our specific extension
```

### What's inside `sim-upstream/` (the submodule)
This is the paper authors' own code, pulled in unmodified except for a small set of pandas-compatibility patches we needed (documented in `WORKFLOW.md`). Key pieces:
- `code/split/LambdaScheduler.py`, `Container.py`, `LambdaData.py` — the actual discrete-event simulator logic (this is where a new keep-alive policy gets added)
- `code/split/many_run.py` — driver script: runs the simulator across multiple policies × memory sizes in parallel
- `code/split/gen/` — scripts to turn the raw Azure Functions trace dataset into a usable trace file
- `code/split/plotting/` — scripts that turn raw simulation output into the paper's actual figures (cold-start %, execution-time-increase %, vs. memory size)

We never edit this folder's `main` branch directly — our patches live on a `team-patches` branch inside the submodule (see `WORKFLOW.md` for why and how to stay in sync).

### What's inside `experiments/`
This is **our** code, separate from the paper's. `gen_synthetic_trace.py` builds a small fake workload so you can test that the whole pipeline runs without waiting on real data. `policies/` is where our actual research contribution — the new/modified keep-alive policy — will live once Week 2's extension is locked in (see `PLAN.md`).

### What's inside `results/`
Simulator output, split into `baseline/` (reproducing the paper's existing policies) and `extension/` (our new policy's results). Each has the same sub-structure: raw `.pckl` simulation output → `analyzed/` (processed stats) → `figs/` (actual plots). Raw data and figures are gitignored (regenerable, often large) — only the code that produces them is tracked.

---

## Setup (every teammate, first time)

```bash
git clone --recurse-submodules <this-repo-url>
cd faascache-project

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

If you forgot `--recurse-submodules` when cloning, `sim-upstream/` will be empty — fix with:
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

## How to reproduce a result (quick version)

Full verified command sequence, known gotchas, and the pandas-compatibility patches we needed are all in **`WORKFLOW.md`** — read that before running anything for real. Short version of the pipeline:

1. Get a trace (`experiments/gen_synthetic_trace.py` for a fast fake one, or real Azure data — see below)
2. Run the simulator sweep: `many_run.py` (policy × memory-size grid, runs in parallel)
3. Analyze: `compute_policy_results.py` turns raw output into stats
4. Plot: `plot_run_across_mem.py` / `plot_cold_across_mem.py` produce the actual comparison figures

**Important gotcha** (bit us already): the memory sweep range must roughly match your trace's actual memory footprint, or every policy looks identical (nothing ever gets evicted). Details + fix in `WORKFLOW.md`.

## How to get real trace data
The paper uses the [Azure Functions 2019 trace dataset](https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md). This is the "real deal" data needed for results actually comparable to the paper (vs. our synthetic trace, which is just for pipeline sanity-checks). Processing it is a two-stage pipeline (`sim-upstream/code/split/gen/trace_split_funcs.py` then `gen_representative_trace.py`) — slower than synthetic, budget real time for this (see `PLAN.md` Week 1).

---

## How to work fast (tips from what we've already hit)

- **Always confirm `pwd` before running a command block** — most of our early setup errors were path-related, not logic errors
- **Use a small synthetic trace + small memory sweep for iteration/debugging** of new policy code — don't run the full 1-80GB sweep every time you tweak something; save the full sweep for final results
- **`many_run.py` parallelizes across your CPU cores automatically** (it uses `multiprocessing.Pool`) — this is good, but means a laptop will take meaningfully longer than the paper's 48-core server; budget accordingly, don't panic if a full sweep takes tens of minutes
- **Don't commit raw `.pckl` result files or `.pdf` figures** — they're gitignored on purpose; only the code that generates them belongs in git
- See `WORKFLOW.md` for the exact patches/fixes already applied, so you don't waste time re-debugging something already solved

---

## Quick links
- **What exactly we're doing, who owns what, weekly tasks** → `PLAN.md`
- **Exact verified commands, known bugs + fixes, git/submodule conventions** → `WORKFLOW.md`
- Paper's own setup instructions (Artifact Appendix, Section A) — useful but some paths differ from reality; `WORKFLOW.md` has the corrections