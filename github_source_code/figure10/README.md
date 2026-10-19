# Figure 10: accuracy under a fixed memory allocation

This folder reproduces the accuracy comparison between Sliding KMV (S-KMV),
Elastic S-KMV, Sliding HLL, VATE-LC, and timestamped FM (T-FM). It includes the
C++ implementations, the measurements used for the figure, and the scripts
that turn those measurements into the plot. Everything needed is local to this
folder; no traffic trace or access to the original project is required.

If you want to see the figure, start with the saved results. If you want to
understand the methods, the code walkthrough below is the best starting point.

## Draw the figure first

Use Python 3.9 or later. From this folder, run:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 plot.py
```

The figure is written to `outputs/figure10.pdf`, along with an SVG and a
400-dpi PNG. The script reads the compressed query results, checks their
settings, and recomputes the statistics. You do not need a C++ compiler for
this step.

To build the implementation and check a small replay, install a C++17 compiler
(GCC or Clang) and run:

```sh
python3 run.py --smoke
```

This replays one original trial at cardinality 1,000 for all six memory
allocations. It compares all 270 query estimates with the saved results and
prints `PASS` if they agree. Compilation uses `c++` by default; set `CXX` or
use `--cxx` to choose another compiler.

## A note about the two Elastic versions

**This folder preserves the earlier Elastic implementation used for Figure 10.**
It can admit an above-threshold arrival when a vacant slot and an expired
candidate boundary allow it. The Figure 12 folder contains the later version,
which expands the threshold by promoting a certified active candidate.

For understanding the candidate-promotion design, start with
[Figure 12's walkthrough](../figure12/README.md). Keep the two implementations
separate when reproducing the saved figures: substituting one for the other
changes the experiment. Each folder can still be built and run independently.

## Finding your way around the code

| File | What to look for |
|---|---|
| [src/sketches.hpp](src/sketches.hpp) | `PackedKMV` contains both KMV variants. Baselines follow it in the same file. |
| [src/replay.cpp](src/replay.cpp) | Builds the stream, feeds every method the same hashes, and records queries. |
| [src/common.hpp](src/common.hpp) | Shared deterministic hashing and hash-to-fraction conversion. |
| [src/stable_alpha.hpp](src/stable_alpha.hpp) | HLL normalization, computed before the stream is replayed. |
| [run.py](run.py) | Builds the driver and selects smoke or full replay settings. |
| [plot.py](plot.py) | Checks raw results, computes RRMSE and intervals, and draws the figure. |
| [data/layouts.csv](data/layouts.csv) | The fixed bucket/register counts used by the experiment. |

Start in `PackedKMV::update()`, then read `expire()` and `query()`. The comments
explain the bit layout, why expiration preserves the threshold, and how the
elastic path differs. The array operations are low-level because the experiment
counts the actual packed state rather than allocating a C++ struct per entry.

### What one KMV bucket stores

`KMV32(memory_bits, false, k)` creates S-KMV. Passing `true` enables the elastic
candidate. Here `k` is capacity per bucket, `m` is the number of buckets that
fit, `stride` is bits per bucket, and `a` is the packed storage buffer.

| State | Meaning in this implementation |
|---|---|
| `theta` | Largest hash currently admissible through ordinary recording. |
| Last-arrival timestamp | Time of the last item assigned to this bucket, including rejected items. |
| `count(i)` | Number of occupied ordinary slots; expiration compacts active entries into this prefix. |
| `bounded(i)` | Whether a sampling threshold has been established; false means exact counting. |
| `k` entry slots | Each stores a hash value and its latest occurrence timestamp. |
| Optional candidate | Hash `c`, occurrence time `tau`, history start `g`, and three status bits. |

The `bounded` bit is **not** the paper's partial-state lock bit. It stays true
in both complete and partial sampled buckets. After expiration, `count(i)==k`
is k-complete, and a smaller count is k-partial. The entries are unsorted:
duplicate lookup and maximum selection scan the occupied slots.

### Following an arrival through S-KMV

1. The bucket hash selects `i`. For the first arrival in a new time slot,
   `expire()` removes inactive entries and compacts the survivors.
2. The last-arrival timestamp is refreshed even if this item will be rejected.
   Only a whole window without arrivals allows a reset to exact counting.
3. A hash above `theta` is rejected. A repeated retained hash refreshes its
   timestamp without increasing occupancy.
4. An admissible new hash fills a vacancy or replaces the largest retained
   hash. Once the bucket is full, its maximum becomes the new threshold.

The important point is step 1: losing an entry does not reveal the next smallest
active hash that was discarded earlier. S-KMV therefore preserves its threshold
when expiration creates a vacancy. A vacancy alone does not allow a larger
hash to enter.

### What the earlier elastic path changes

The `discard()` routine considers a rejected arrival or an active evicted entry
for the candidate. A smaller or equal hash preserves the candidate's history
start. A larger hash replaces an expired candidate and starts a new history.
The occurrence timestamp and history-start timestamp have different purposes;
`candidate_age()` maintains separate status bits for them.

In this Figure 10 version, `update()` sets `lift` when the bucket has room, the
candidate is present and expired, and the incoming hash does not exceed its
boundary. That arrival can enter and raise the threshold. This path does not
move the candidate into the bucket or test the history-complete bit. The code
marks this distinction explicitly to avoid confusing it with Figure 12.

### How querying works

`query()` first performs maintenance. It then counts retained hash values
**strictly below** the chosen boundary and divides that count by the boundary's
normalized value. This is not always `count(i)-1`: the entry that defined the
threshold may already have expired. An initial or reset bucket with no sampling
threshold returns its exact retained count.

A present, active candidate whose history covers a full window can supply the
query boundary. The candidate is excluded from the numerator; the ordinary
retained entries below it are counted. Finally, the local estimates are summed
because the buckets represent disjoint identifier populations.

Stored 32-bit hashes are mapped to `(hash + 0.5) / 2^32`. Equal stored hashes
within a bucket are treated as the same identifier; the experiment does not
apply a finite-hash collision correction.

### Why scheduled maintenance matters

The window spans 100 slots. KMV, HLL, and T-FM use an eight-bit clock that wraps
at 256. The driver visits all buckets every 50 slots, including idle buckets,
so stale timestamps cannot become apparently recent after a full wrap. For
candidates, latched bits remember expiration and completed history. VATE-LC
instead uses its staggered modulo-200 clock with sentinel 200.

## Experiment settings

The sweep contains 81 logarithmically spaced cardinalities from `10^3` to
`10^7`. Each trial feeds `3*n` distinct integer identifiers over three windows.
Queries occur at slots 99, 124, ..., 299. There are no repeated identifiers in
this saved workload, although the sketch implements duplicate refresh.

Memory is in decimal bits (`1 kbit = 1,000 bits`). Packed storage rounds down
to whole 64-bit words. The allocation counts algorithm state, including
metadata and histories; host object/vector overhead and diagnostic counters
are not part of that packed-state accounting.

| Memory | S-KMV k | Elastic k | S-KMV buckets | Elastic buckets | HLL registers |
|---|---:|---:|---:|---:|---:|
| 1 kbit | 22 | 21 | 1 | 1 | 6 |
| 5 kbit | 123 | 122 | 1 | 1 | 32 |
| 10 kbit | 248 | 247 | 1 | 1 | 64 |
| 50 kbit | 66 | 66 | 18 | 18 | 320 |
| 1 Mbit | 90 | 89 | 274 | 273 | 6144 |
| 5 Mbit | 121 | 119 | 1022 | 1029 | 28672 |

Each trial uses the seed
`mix(20261013 + trial_id)`, with a separate value-hash salt `mix(seed+1)`.
KMV stores 32-bit hashes; HLL uses 5-bit ranks. Each T-FM register contains 32
positions, each with an eight-bit timestamp and a validity bit. VATE-LC returns
`m*log(m)` when saturated. HLL uses a fixed history pool and stops explicitly
if that pool is exhausted.

The plotted metric is RRMSE: the square root of the average squared relative
error across trials and queries. Bands use 2,000 whole-trial bootstrap
resamples. No curve smoothing is applied; triangles mark curves outside the
visible y range.

## Run the complete experiment

```sh
python3 run.py --full
python3 plot.py --data outputs/replay --output outputs/recomputed
```

Full replay processes every arrival at every cardinality and trial, so it takes
much longer than drawing the saved figure. The scripts leave `data/` unchanged
and put new measurements in `outputs/replay/`. They refuse to overwrite existing
replay CSVs. For another run, choose a new directory with `--output`, then pass
its `replay/` subdirectory to `plot.py --data`.

Saved query records are in `data/raw_*.csv.gz`; `data/summary.csv` contains the
original aggregate results. The legacy CSV field `budget_bits` means memory
allocation in bits. `VALIDATION.md` describes the checks performed on this
release, and `SHA256SUMS` lets you verify its files.

This is an anonymous source package: it includes no personal paths, author
identities, or Git history. Generated files are ignored by Git. If publishing
it, use an anonymous repository and commit identity as well.
