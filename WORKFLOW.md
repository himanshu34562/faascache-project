# Workflow

Verified commands, gotchas we actually hit, and team conventions. Read this before running anything.

---

## Golden rule: always know your working directory

Most errors we've hit so far (submodule nesting, "file not found", path doubling) came from running a command from the wrong directory. Before pasting/running any command block below, run `pwd` and confirm where you are. All commands below assume paths relative to `sim-upstream/code/split/` unless stated otherwise — adjust `cd` first.

---

## Trace file format

A trace is a pickle: `(lambdas, trace)`
- `lambdas`: `dict[func_name] = (func_name, mem_size_mb, cold_time_sec, warm_time_sec)` — **4-tuple**, name repeated as first element
- `trace`: list of `(LambdaData_instance, start_time_ms)`, sorted by `start_time_ms`
- Filename convention: `{num_funcs}-{char}.pckl` (e.g. `20-b.pckl`) — `{char}` is just an arbitrary single-letter trace-variant label

## Generating a synthetic test trace (fast, for pipeline sanity checks)

Script: `experiments/gen_synthetic_trace.py`. Edit `num_funcs` and `sim_duration_ms` at the top to control trace size — smaller = faster to run, but you need the trace's total memory footprint to roughly match whatever memory sweep you test against, or every policy will look identical (see gotcha below).

```bash
cd experiments
python3 gen_synthetic_trace.py
cd ..
```

## Running the simulator pipeline (verified working commands)

From `sim-upstream/code/split/`:

```bash
python3 many_run.py \
  --tracedir ../../../experiments/traces \
  --numfuncs <N> \
  --savedir ../../../results/baseline \
  --logdir ../../../results/baseline/logs \
  --memstep <STEP_MB>

mkdir -p ../../../results/baseline/analyzed
python3 plotting/compute_policy_results.py \
  --pckldir ../../../results/baseline \
  --savedir ../../../results/baseline/analyzed

mkdir -p ../../../results/baseline/figs
python3 plotting/plot_run_across_mem.py \
  --analyzeddir ../../../results/baseline/analyzed \
  --plotdir ../../../results/baseline/figs \
  --numfuncs <N>
python3 plotting/plot_cold_across_mem.py \
  --analyzeddir ../../../results/baseline/analyzed \
  --plotdir ../../../results/baseline/figs \
  --numfuncs <N>
```

Output: PDFs in `results/baseline/figs/` (e.g. `exec_inc_mem-<N>.pdf`, `cold_drop_mem-<N>.pdf`).

### Gotcha: match your memory sweep to your trace's actual scale
`many_run.py`'s default sweep is `range(1000, 80000, memstep)` MB (1–80GB), hardcoded, not a CLI flag — matches the paper's full representative trace (392 functions). If you're running a small synthetic trace (e.g. 20 functions), this range will be wildly overprovisioned relative to your trace's real footprint, and **every policy will look identical** (nothing is ever evicted, so there's no difference to measure). If your plot comes out flat/near-zero across the whole range, this is almost certainly why — not a bug.

Fix: either scale your trace up to match the default 1-80GB range, or edit the hardcoded `mems = [i for i in range(1000, 80000, args.memstep)]` line in `many_run.py` to a range that matches your trace's scale (e.g. `range(200, 5000, args.memstep)` for a small test trace).

## Known pandas 2.0+ compatibility patches (already applied on `team-patches` branch)

| File | Original (breaks on pandas 2.0+) | Patched to |
|---|---|---|
| `plotting/compute_mem_usage.py` | `pd.read_csv(f, error_bad_lines=False, warn_bad_lines=False)` | `pd.read_csv(f, on_bad_lines='skip')` |
| `plotting/compute_mem_usage.py` | `df.append(df2)` | `pd.concat([df, df2], ignore_index=False)` |
| `plotting/compute_mem_usage.py` | `.resample("S").mean().interpolate().resample("1Min")` | `.resample("s").mean(numeric_only=True).interpolate().resample("1min")` |

If you hit a similar `AttributeError`/`TypeError` elsewhere in `sim-upstream` referencing `.append(`, `error_bad_lines`, or resample frequency strings, it's the same root cause (2021 code vs. modern pandas) — same fix pattern applies.

**Also note**: `compute_policy_results.py` and `compute_mem_usage.py` do **not** auto-create their `--savedir` — always `mkdir -p` it first or you'll get a `FileNotFoundError`.

## Dependency management

- `requirements.txt` lives at repo root, tracks exact installed versions (`pip freeze > requirements.txt`)
- **Whoever adds a new package**: `pip install <pkg>`, then `pip freeze > requirements.txt`, commit, and post a one-line note in team chat ("added X, repull requirements before running my branch")
- Everyone else: `pip install -r requirements.txt` after pulling (fast — only installs what's missing)

## Submodule conventions

- Never edit files directly inside `sim-upstream` on your local `main`/`master` — our patches live on the `team-patches` branch inside the submodule, committed there, with the main repo's submodule pointer pinned to that commit
- If upstream (the paper authors) push a fix and you want to pull it in: do this deliberately as a team decision, not silently, since it could reintroduce pandas-incompatible code
- After every `git pull` of the main repo: `git submodule update --init --recursive` to stay in sync

## Viewing PDF plots

```bash
sudo apt-get install -y poppler-utils   # one-time
pdftoppm -png results/baseline/figs/exec_inc_mem-<N>.pdf results/baseline/figs/exec_inc_mem-<N>
```
Produces a `.png` you can open normally or share.

## Git commit conventions (keep it simple)
- Commit messages: short, present tense, what changed (`"Add weighted-priority policy variant"`, not `"updates"`)
- Don't commit raw `.pckl` trace/result files — they're gitignored on purpose (regenerable, large). If you need to share a specific result with the team, mention it in your sync rather than committing the binary.
- Push to your own branch, open a PR into `main` for anything touching shared code (policy implementations, simulator patches) — direct pushes to `main` are fine for docs/report-only changes