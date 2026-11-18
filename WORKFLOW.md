# Workflow

Verified commands, gotchas already hit, and repo conventions. Read this before running anything.

---

## Golden rule: always know your working directory

Most errors so far (submodule nesting, "file not found", path doubling) came from running a command from the wrong directory. Run `pwd` before any command block below. Each block says where it runs from.

All commands use the project venv: `source .venv/bin/activate` (or call `.venv/bin/python` directly).

---

## Trace file format

A trace is a pickle: `(lambdas, trace)`
- `lambdas`: `dict[func_name] = (func_name, mem_size_mb, cold_time_ms, warm_time_ms)`, a **4-tuple** with the name repeated as the first element
- `trace`: list of `(LambdaData_instance, start_time_ms)`, sorted by `start_time_ms`
- Filename convention: `{num_funcs}-{char}.pckl` (e.g. `392-a.pckl`). `{char}` is a single-letter variant label.
- For Azure traces: `cold_time` = the function's **Maximum** duration and `warm_time` = its **Average** duration. The simulator runs a cold start for `cold_time` and a warm hit for `warm_time`.

## Generating a synthetic test trace (fast, for pipeline sanity checks only)

From the repo root:
```bash
python experiments/gen_synthetic_trace.py
```
Edit `num_funcs` and `sim_duration_ms` at the top of the script. Size the memory sweep to the trace (see the gotcha below).

---

## Generating the real Azure trace

Two stages. Both scripts resolve paths relative to the repo root (override with `FAASCACHE_ROOT`), so **run them from the repo root**. No path edits are needed.

**0. Raw data** (one-time, gitignored). Download the tarball linked from the [Azure Functions 2019 dataset page](https://github.com/Azure/AzurePublicDataset/blob/master/AzureFunctionsDataset2019.md) (~140MB compressed) into `azure-raw-data/`, then:
```bash
cd azure-raw-data && tar -xf <downloaded>.tar.xz && cd ..
```
Only the day-1 files are used: `invocations_per_function_md.anon.d01.csv`, `function_durations_percentiles.anon.d01.csv`, `app_memory_percentiles.anon.d01.csv`.

**1. Split into one pickle per function** (~36k files, ~7GB in `experiments/traces/split_funcs/`, roughly an hour):
```bash
SPLIT_WORKERS=2 SPLIT_MAX_INVOCATIONS=10000000 \
  python sim-upstream/code/split/gen/trace_split_funcs.py
```
- **Resumable**: functions that already have a `.pckl` are skipped, so if it dies, rerun the same command. Writes are atomic; a leftover `*.pckl.tmp` is safe to delete.
- `SPLIT_MAX_INVOCATIONS` skips functions above that many invocations/day. The script builds one Python tuple per invocation, so on a 7–8GB machine the 3 giant functions (49M, 84M, 127M calls/day) kill the worker. With the old `Pool.map`, that also silently lost the whole chunk of ~3.5k normal functions. With the cap, those 3 are logged and skipped, and 36,257 of 36,260 functions are written.
- `SPLIT_WORKERS` = parallel workers (default 1; 2 is safe on 8GB).

**2. Build the representative trace** (~25s for 392 functions):
```bash
python sim-upstream/code/split/gen/gen_representative_trace.py --sizes 392 --runs a --two-hour
```
- Samples `size/4` functions from each invocation-frequency quartile, as in the paper. Sampling is **seeded**, so `392-a` is identical on every machine.
- **Footprint filter** (`--max-func-mb 2048`, the default; `0` disables it): excludes functions whose own cold-start burst, *peak rate/s × Maximum duration (s) × memory*, exceeds 2GB. This excludes 1,982 of 36,257 functions. See the next section for why it's needed. **State this in the report's experimental setup.**
- Writes `experiments/traces/representative/392-a.pckl`: full day, 392 functions, 458k invocations, worst-case running footprint ~14GB.
- `--two-hour` also writes the 12:00–14:00 cut to `representative_two_hour/` (only 38k invocations after filtering, so not needed in practice).
- Upstream generated ~290 traces (`range(8, 400, 4)` × a/b/c); this version builds only what you ask for.

### Why the footprint filter exists (the "all policies look identical" failure)
Running containers can't be evicted, and every concurrent request needs its own container. Without the filter, the first `392-a` sweep dropped 87–97% of requests at every memory size, and GD ≈ TTL ≈ LRU:
- one sampled function (51MB, ~20 req/s, ~81s average duration) needed **~80GB of running containers** on its own;
- after filtering on *average* duration, **cold-start cascades** still dropped ~50%: a cold start runs for the *Maximum* duration (e.g. 56s vs a 142ms average), and every arrival during it also goes cold.

Filtering on the cold-start burst fixes both. The excluded functions are only 5.5% of functions but ~93% of all invocations (the giants). Sampling still draws equally from every frequency quartile.

**Debugging tip**: if policies ever look identical, check dropped requests first. That's the 5th field of each result pickle (`capacity_misses`), or `dropped_mem-*.csv`.

---

## Running the baseline sweep

From `sim-upstream/code/split/`:
```bash
R=../../../results/baseline/full_day
python many_run.py \
  --tracedir ../../../experiments/traces/representative \
  --numfuncs 392 --char a \
  --memmin 1000 --memmax 17000 --memstep 1000 \
  --workers 6 \
  --savedir $R --logdir $R/logs
```
- Runs 7 policies (GD, TTL, LRU, LND, HIST, FREQ, SIZE) × 16 memory sizes = 112 simulations, **~25 min** on 6 workers (≈1 min each, ~160MB RAM each).
- Existing result files are skipped, so an interrupted sweep resumes by rerunning the same command.
- Flags added to upstream (defaults reproduce the original hardcoded behaviour): `--char` (default `b`), `--memmin`/`--memmax` (default 1000/80000), `--workers` (default: all cores).

### Gotcha: match the memory sweep to the trace
If the sweep is far above the trace's footprint, nothing is ever evicted and every policy looks identical. If it's far below, memory is pinned by running containers and requests are dropped (see above). For the filtered `392-a`, 1–16GB covers the interesting range: below ~4GB everything thrashes, and by ~16GB cold starts are ~1%.

## Making the figures

From the repo root:
```bash
python experiments/plot_baseline.py --resdir results/baseline/full_day --outdir results/baseline/full_day/figs
```
Writes `.pdf`, `.png` and `.csv` (table view) for each figure:
- `cold_pct_mem-392`: cold starts as % of served invocations. Cross-checked against upstream's `compute_policy_results.py` (identical to < 0.001 pp).
- `overhead_mem-392`: (a) total cold-start overhead in hours, (b) relative to TTL. **This is the main result figure.**
- `dropped_mem-392`: % of invocations dropped.

### Don't use upstream's "% increase in execution time" plot
`plotting/compute_policy_results.py::analyze_timings` treats `warm_time` as the cold-start *penalty* and `run_time − warm_time` as the normal run time, so its per-miss increase is `warm_time / (run_time − warm_time)`. The simulator does the opposite: a hit takes `warm_time`, and a miss takes `run_time`, i.e. `run_time − warm_time` extra. That extra time is also GD's own `cost` term. On the 392-a trace the upstream metric is dominated by a few functions with Maximum ≈ Average, giving a flat ~18% floor and a spurious LND drop. `plot_baseline.py` uses the simulator's definition instead: overhead = Σ misses × (run_time − warm_time).

The upstream plot scripts still work if needed (`plotting/plot_cold_across_mem.py`, `plot_run_across_mem.py`). They now take `--char`, `--memmin` and `--memmax`; the originals only accepted `-b` files at 10–80GB. `compute_policy_results.py` reads *every* file in `--pckldir`, so point it at a folder containing only result `.pckl` files (not `sweep.log`), and `mkdir -p` its `--savedir` first.

---

## Patches on the `sim-upstream` submodule (`patches` branch)

| File | Change |
|---|---|
| `plotting/compute_mem_usage.py` | pandas 2+: `error_bad_lines` → `on_bad_lines='skip'`; `df.append` → `pd.concat`; resample `"S"`/`"1Min"` → `"s"`/`"1min"` with `numeric_only=True` |
| `gen/trace_split_funcs.py` | repo-relative paths; sum only per-minute columns; resumable + atomic writes; `SPLIT_MAX_INVOCATIONS`, `SPLIT_WORKERS` |
| `gen/gen_representative_trace.py` | repo-relative paths; pandas 2+ sum fix; seeded sampling; footprint filter; `--sizes/--runs/--two-hour/--max-func-mb` |
| `many_run.py` | `--char`, `--memmin`, `--memmax`, `--workers` |
| `plotting/plot_{cold,run}_across_mem.py` | `--char`, `--memmin`, `--memmax` |

Similar `AttributeError`/`TypeError` elsewhere mentioning `.append(`, `error_bad_lines`, or resample frequency strings have the same root cause (2021 code vs. modern pandas), and the same fix pattern applies.

## Submodule conventions
- Never edit `sim-upstream` on upstream's `master`. All changes are committed on the `patches` branch, and the main repo's submodule pointer is pinned to that commit.
- **Push order**: push the submodule (`git -C sim-upstream push origin patches`) *before* the main repo, so the pointer never refers to an unpushed commit.
- Pulling a fix from the paper authors' upstream is a deliberate step, not a routine one, since it could reintroduce pandas-incompatible code.
- After cloning or pulling the main repo: `git submodule update --init --recursive`.

## Dependency management
- `requirements.txt` at the repo root pins exact versions (`pip freeze > requirements.txt` after adding a package).
- Fresh setup: `pip install -r requirements.txt`.

## Viewing PDF plots
`plot_baseline.py` already writes PNGs. For upstream PDFs:
```bash
sudo apt-get install -y poppler-utils   # one-time
pdftoppm -png -singlefile <file>.pdf <file>
```

## Git commit conventions
- Messages: short, present tense, say what changed (`"Add weighted-priority policy variant"`, not `"updates"`)
- Don't commit raw `.pckl` traces/results or figures. They're gitignored on purpose (regenerable, large); only the code that produces them belongs in git.
