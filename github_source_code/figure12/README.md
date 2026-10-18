# Figure 12: dynamic stream rates

Anonymous, self-contained reproduction of the four-method dynamic-rate figure:
S-KMV, candidate-promotion Elastic S-KMV, Sliding HLL, and timestamped FM (T-FM).
This figure does not include VATE-LC. No external stream or account is required.

## Contents

- `src/sketches.hpp`: the packed estimators, including candidate promotion.
- `src/common.hpp`, `src/stable_alpha.hpp`: hashing and HLL normalization.
- `src/replay.cpp`: one paired stream driver for all four methods.
- `src/validate_baselines.cpp`: wrapped HLL/FM checks against an unwrapped oracle.
- `data/*.csv.gz`: original paired query observations for all workloads.
- `data/curves_*.json`, `data/scores_*.json`: recorded aggregate results.
- `run.py`, `analyze.py`, `plot.py`: build/replay, recompute statistics, and plot.

## Requirements and quick reproduction

Use Python 3.9 or later, a C++17 compiler (GCC or Clang), NumPy, and Matplotlib.
From this folder:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 plot.py
python3 run.py --smoke
```

Plotting saved summaries produces `outputs/figure12.pdf`, `.svg`, and a 400-dpi
`.png`. The smoke test replays the first eight epochs of the original increase
schedule at both memory settings, with seed 4000. It checks all four estimates
and HLL memory counters against the original paired records, then checks HLL and
FM against unwrapped timestamp oracles through multiple wraps and idle periods.
This small test exercises the rate increase but does not replace the full run.

To recompute the summaries from the supplied raw observations:

```sh
python3 analyze.py --memory 1000
python3 analyze.py --memory 50000
python3 plot.py --data outputs --output outputs/recomputed
```

## Full replay

```sh
python3 run.py --full
python3 analyze.py --memory 1000 --data outputs/replay --output outputs/recomputed
python3 analyze.py --memory 50000 --data outputs/replay --output outputs/recomputed
python3 plot.py --data outputs/recomputed --output outputs/recomputed
```

The full experiment processes tens of billions of arrivals and can take hours.
It uses one process by default. Set `CXX` or pass `--cxx` to select the compiler.
Existing raw outputs are never overwritten; choose a fresh `--output` directory
for a repeat run. Binaries and generated outputs are ignored by Git.

## Workloads and layouts

The data contain **60 seeds, 4000--4059**, for each schedule and memory setting.
These are the actual saved runs, not a 100-seed experiment. All methods receive
the same globally distinct integer identifiers and hash streams. Each epoch is
one 100-slot window. High/low rates are 10,000/625 new identifiers per slot, so
steady window cardinalities are 1,000,000 and 62,500.

| Schedule | Epochs | Rate changes |
|---|---:|---|
| Permanent decrease | 512 | 20 high epochs, then 492 low |
| Permanent increase | 128 | 4 low epochs, then 124 high |
| Repeated changes | 512 | 64 high, 64 low; repeated four times |

| Memory | Allocated bits | S-KMV / Elastic k | Buckets | HLL registers / nodes | T-FM registers |
|---|---:|---:|---:|---:|---:|
| 1 kbit | 960 | 22 / 21 | 1 / 1 | 4 / 48 | 3 |
| 50 kbit | 49,984 | 248 / 247 | 5 / 5 | 256 / 1,964 | 173 |

- Memory units are decimal; buffers round down to 64-bit words.
- Hash seed: `mix(20261017 + seed_id)`; independent value salt: `mix(seed+1)`.
- KMV stores 32-bit hash values. HLL ranks use five bits. T-FM has 32 timestamped
  positions per register, each with eight time bits plus a validity bit.
- Timestamps wrap at 256; maintenance runs every 50 slots; query every epoch end.
  State persists across rate changes. No stream sampling is used.
- HLL history pools are fixed, and overflow aborts the run. Counts differ from
  Figure 10 because this longer workload requires more history per register.
- Plot points pool squared relative errors within four-epoch groups; the
  decrease uses four-epoch groups for epochs 1--20, then eight-epoch groups.
  Bands use 2,000 paired whole-seed bootstrap resamples. No outliers are removed.
  All methods use the same grouping. Upward triangles indicate clipped display
  values; the underlying values and intervals are retained in the data.
- The original KMV and baseline runs were paired by schedule, seed, epoch, and
  exact cardinality. This package merges their records and replays all four
  estimators together; each sketch's update/query order remains unchanged.

## Implementation version

Elastic S-KMV here promotes a certified active candidate into a vacant bucket
slot, preserving the occurrence timestamp and restarting candidate history.
This is the promotion version; Figure 10 preserves its earlier Elastic version
for faithful reproduction of that figure's saved measurements.

## Anonymous distribution

Only generic source, synthetic numerical results, and documentation are included.
There are no author names, affiliations, personal paths, repository links,
contact details, compiled binaries, or Git history. An anonymous hosting account
and anonymous commit identity are still necessary when publishing on GitHub.
