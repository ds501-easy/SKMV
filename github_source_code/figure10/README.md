# Figure 10: cardinality accuracy

Anonymous, self-contained reproduction of the five-method accuracy comparison.
No original project checkout, traffic trace, network access, or account is needed.

## Contents

- `src/sketches.hpp`: packed Sliding KMV, Elastic S-KMV, Sliding HLL, VATE-LC,
  and timestamped FM (T-FM). Shared hashing and numerical HLL normalization are
  in `common.hpp` and `stable_alpha.hpp`.
- `src/replay.cpp`: the synthetic stream and paired query driver.
- `data/raw_*.csv.gz`: the original per-query observations (lossless gzip).
- `data/layouts.csv`: frozen memory layouts and bucket capacities.
- `data/summary.csv`: saved aggregate results, useful for checking regeneration.
- `run.py`: build, smoke-test, or replay all methods.
- `plot.py`: validate observations, recompute RRMSE and intervals, and plot.

## Requirements and quick reproduction

Use Python 3.9 or later, a C++17 compiler (GCC or Clang), NumPy, and Matplotlib.
The compiler defaults to `c++`; override it with `CXX` or `--cxx`.
Run these commands from this folder:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 plot.py
python3 run.py --smoke
```

The first command after installation redraws the complete figure from the saved
observations, with no C++ experiment required. It creates `outputs/figure10.pdf`,
`.svg`, and a 400-dpi `.png`, plus summaries and validation metadata. The smoke
test processes the original `n=1000`, trial-50 stream at all six memory settings
and checks all 270 query estimates against the saved observations. It does not
replace the full experiment.

## Full replay

```sh
python3 run.py --full
python3 plot.py --data outputs/replay --output outputs/recomputed
```

Full replay processes every item, at every cardinality, for every recorded trial.
It is substantially more expensive than plotting or the smoke test and can take
hours. Raw outputs are never overwritten; to repeat, choose a fresh `--output`
directory. Generated files and binaries are excluded by `.gitignore`.

## Exact settings represented by the data

Memory is measured in decimal bits; packed buffers round down to 64-bit words.

| Memory | S-KMV k | Elastic k | S-KMV buckets | Elastic buckets | HLL registers | Trials |
|---|---:|---:|---:|---:|---:|---:|
| 1 kbit | 22 | 21 | 1 | 1 | 6 | 100 |
| 5 kbit | 123 | 122 | 1 | 1 | 32 | 20 |
| 10 kbit | 248 | 247 | 1 | 1 | 64 | 20 |
| 50 kbit | 66 | 66 | 18 | 18 | 320 | 20 |
| 1 Mbit | 90 | 89 | 274 | 273 | 6144 | 20 |
| 5 Mbit | 121 | 119 | 1022 | 1029 | 28672 | 20 |

- 81 cardinalities: `round(10**(3+j/20))`, `j=0,...,80`.
- Each stream has `3*n` distinct integer identifiers over 300 time slots.
  The supplied experiment uses hashed integer identifiers; it does not require
  external traces or generate byte-string duplicates.
- Window width: 100 slots. Queries: slots 99, 124, ..., 299 (nine per trial).
- Trial IDs: 50--149 at 1 kbit, 50--69 elsewhere. These are the actual saved
  counts, not a uniform 100-trial experiment.
- Hash seed: `mix(20261013 + trial_id)`, independent value salt `mix(seed+1)`.
  KMV stores 32 hash bits; HLL stores 5-bit ranks. T-FM uses 32 timestamped
  positions per register, each with eight time bits and one validity bit.
- KMV, HLL, and T-FM timestamps wrap at 256; maintenance occurs every 50 slots.
  VATE-LC uses its staggered modulo-200 clock and invalid sentinel 200, stored
  in eight bits. Saturated VATE-LC queries return `m*log(m)`.
- RRMSE pools squared relative errors across all trials and nine queries.
  Confidence bands use 2,000 whole-trial bootstrap resamples. Curves are not
  smoothed. Triangles mark values outside the visible range.
- Fixed HLL history pools fail explicitly on overflow; they do not truncate
  history. The supplied layouts are frozen experimental settings.

## Implementation version

This folder deliberately preserves the Elastic implementation that generated
Figure 10: expansion admits a new arrival below an expired candidate boundary.
Figure 12 uses the later **candidate-promotion** implementation. These are
separate frozen experiment versions; their Elastic implementations must not be
silently interchanged when reproducing the saved curves. The shared components
and all S-KMV/baseline operations remain local to each folder.

`budget_bits` is the original CSV field name for the memory allocation in bits.
No source selection, capacity tuning, or experiment outside Figure 10 is needed.

## Anonymous distribution

This folder contains only generic source, numerical synthetic-stream results,
and documentation. It contains no author names, affiliations, repository URLs,
contact details, personal paths, compiler binaries, or Git history. Publish it
through an anonymous account/repository if anonymity must also hold on GitHub;
account names, commit authors, and hosting metadata are outside these files.
