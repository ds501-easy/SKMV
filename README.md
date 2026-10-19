# Sliding KMV: source code and experiments

This repository contains the code and results for two experiments: the accuracy
comparison in **Figure 10** and the dynamic-rate comparison in **Figure 12**.
Each folder is self-contained, with its own implementations, saved measurements,
and instructions. You can draw either figure from the supplied data or compile
the code and replay the experiment.

## Choose an experiment

| Folder | What it demonstrates | Methods compared |
|---|---|---|
| [figure10](figure10/README.md) | Accuracy across window cardinalities from `10^3` to `10^7`, under six memory allocations from 1 kbit to 5 Mbit. | S-KMV, Elastic S-KMV, Sliding HLL, VATE-LC, and T-FM |
| [figure12](figure12/README.md) | Accuracy after a permanent rate decrease, a permanent increase, and repeated changes, at 1 and 50 kbit. | S-KMV, Elastic S-KMV, Sliding HLL, and T-FM |

Both figures report relative root mean squared error (RRMSE). Memory units are
decimal: 1 kbit is 1,000 bits. The workloads are generated locally, so no external
traffic trace is needed.

## Draw the figures

Use Python 3.9 or later, preferably in a virtual environment. The two folders
use the same Python dependencies. From the repository root, run:

```sh
python3 -m pip install -r figure10/requirements.txt
python3 figure10/plot.py
python3 figure12/plot.py
```

The outputs are `figure10/outputs/figure10.pdf` and
`figure12/outputs/figure12.pdf`, with SVG and PNG copies alongside them.
Figure 10's script recomputes statistics from the saved query measurements;
Figure 12's script draws the saved aggregate curves. Its README also explains
how to recompute those aggregates from the raw measurements.

Drawing the saved figures does not require a C++ compiler or a new stream replay.

## Find the code and data

```text
figure10/                         figure12/
├── README.md                     ├── README.md
├── src/                          ├── src/
│   ├── sketches.hpp               │   ├── sketches.hpp
│   ├── replay.cpp                 │   ├── replay.cpp
│   ├── common.hpp                 │   ├── common.hpp
│   └── stable_alpha.hpp           │   ├── stable_alpha.hpp
├── data/                         │   └── validate_baselines.cpp
├── run.py                        ├── data/
├── plot.py                       ├── run.py
├── requirements.txt              ├── analyze.py
├── VALIDATION.md                 ├── plot.py
└── SHA256SUMS                    ├── requirements.txt
                                 ├── VALIDATION.md
                                 └── SHA256SUMS
```

- **`src/sketches.hpp`** contains the algorithms. `PackedKMV` implements S-KMV
  and Elastic S-KMV; the baseline implementations follow it.
- **`src/replay.cpp`** generates the workload, feeds the methods the same stream,
  and writes their query estimates.
- **`src/common.hpp`** provides shared hashing, and **`src/stable_alpha.hpp`**
  computes HLL's normalization.
- **`data/`** holds the saved measurements and summaries. Figure 10 also includes
  `layouts.csv`, which records its bucket and register allocations.
- **`run.py`** builds and runs an experiment. **`plot.py`** produces the figure.
  Figure 12's **`analyze.py`** computes its statistics separately.
- **`VALIDATION.md`** records the checks performed on each package.
  **`SHA256SUMS`** contains checksums for its supplied files.

Build products go into each folder's `build/` directory, and newly generated
results go into `outputs/`. These directories are created when needed; they are
not required inputs.

## Understand S-KMV and Elastic S-KMV

For the core algorithm, start with
[Figure 10's code walkthrough](figure10/README.md#finding-your-way-around-the-code).
It explains the retained sample, the threshold lock, and how a query counts
entries strictly below the threshold. The corresponding
[implementation](figure10/src/sketches.hpp) includes comments on the packed
fields and each main operation.

For candidate promotion, start with
[Figure 12's walkthrough](figure12/README.md#elastic-s-kmv-recovering-a-missing-successor)
and [implementation](figure12/src/sketches.hpp). Read `update()`, `expire()`,
`discard()`, `promote()`, and `query()` in that order. The comments distinguish
candidate occurrence time from certification history and explain when the
threshold can increase.

The folders preserve the implementations that generated their respective
results. Figure 10 uses the earlier elastic admission rule; Figure 12 uses
candidate promotion. Keep each implementation with its experiment when
reproducing the saved figures. The folder READMEs explain the difference.

## Build and check a small replay

With a C++17 compiler such as GCC or Clang installed, run:

```sh
python3 figure10/run.py --smoke
python3 figure12/run.py --smoke
```

These commands compile the code, replay small subsets of the original workloads,
and compare the estimates with the supplied results. Figure 12 also checks its
wrapped-timestamp baselines against unwrapped reference implementations.
The compiler defaults to `c++`; use `CXX` or `--cxx` to select another compiler.

For the complete experiments, use `--full` instead of `--smoke`. Full replays
process every arrival and take substantially longer than the small checks.
Follow the [Figure 10 instructions](figure10/README.md#run-the-complete-experiment)
or [Figure 12 instructions](figure12/README.md#recompute-the-summaries-or-replay-the-stream)
for the analysis commands that follow a replay. Existing replay CSVs are not
overwritten; use a fresh `--output` directory when repeating a run.

The repository is prepared for anonymous distribution. The source and
instructions contain no author identities or personal paths. Use an anonymous
hosting account and commit identity if publishing it.
