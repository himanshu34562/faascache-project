# FaaSCache Project
### Reproducing and Extending Greedy-Dual Keep-Alive Policies for Serverless Cold-Start Mitigation

Course project based on: Fuerst & Sharma, *"FaasCache: Keeping Serverless Computing Alive with Greedy-Dual Caching,"* ASPLOS 2021. [[paper](https://homes.luddy.indiana.edu/prateeks/papers/faascache-asplos21.pdf)]

---

## Repo Structure
```
faascache-project/
├── sim-upstream/         # faascache-sim, pulled in as a git submodule — DO NOT edit directly on main; patches go on the team-patches branch (see below)
├── experiments/
│   ├── policies/         # our new keep-alive policy implementations
│   └── traces/           # trace .pckl files (gitignored — regenerate locally, don't commit)
├── results/
│   ├── baseline/         # reproduced GD/TTL/LRU/etc. results
│   └── extension/        # our new policy's results
├── notebooks/            # analysis notebooks
├── report/                # report drafts, final figures
├── requirements.txt
├── .gitignore
├── README.md             # you are here
├── WORKFLOW.md           # day-to-day commands, team conventions, how to run things
└── PLAN.md               # 4-week task breakdown and role assignments
```

## Setup (do this first, every teammate)

```bash
git clone --recurse-submodules <this-repo-url>
cd faascache-project

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

**If you already cloned without `--recurse-submodules`**, your `sim-upstream/` folder will be empty. Fix with:
```bash
git submodule update --init --recursive
```

**After every `git pull`**, resync the submodule and dependencies:
```bash
git submodule update --init --recursive
pip install -r requirements.txt
```

## Verify your setup works

```bash
cd sim-upstream/code/split
python3 -c "from LambdaScheduler import LambdaScheduler; print('imports OK')"
```
If this prints `imports OK`, you're good to go.

## Important: this codebase needs patches for modern pandas

`sim-upstream` is 2021 code. On pandas 2.0+ (which `pip install pandas` gives you today), three things break: `DataFrame.append()` (removed), `error_bad_lines`/`warn_bad_lines` args to `read_csv` (removed), and uppercase `"S"` resample frequency alias (deprecated). **These patches are already applied on the `team-patches` branch of the submodule** — don't re-patch, just make sure your submodule checkout is on that branch/commit (confirmed via `git submodule status` after cloning). Full details on what was broken and why: see `WORKFLOW.md`.

## Quick links
- Day-to-day commands and conventions → `WORKFLOW.md`
- What we're doing each week, who owns what → `PLAN.md`
- Upstream simulator docs/artifact appendix → see the paper's Appendix A, or `sim-upstream`'s own README