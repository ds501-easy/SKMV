# Figure 12: accuracy when the stream rate changes

This experiment compares S-KMV and Elastic S-KMV with Sliding HLL and timestamped
FM (T-FM) under three rate schedules: a permanent decrease, a permanent increase,
and repeated changes. It includes the candidate-promotion version of Elastic
S-KMV, the measurements behind the figure, and everything needed to replay or
plot them. VATE-LC is not part of this experiment.

For a quick look, draw the saved figure first. To understand how Elastic S-KMV
recovers after a rate decrease, follow the code walkthrough below.

## Draw the saved results

With Python 3.9 or later, run these commands from this folder:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 plot.py
```

The plot appears in `outputs/figure12.pdf`, with SVG and 400-dpi PNG versions
beside it. This uses the saved summaries and does not require a C++ compiler.

To compile and run a small verification, use a C++17 compiler (GCC or Clang):

```sh
python3 run.py --smoke
```

The smoke test replays eight epochs of the increase schedule at both memory
allocations, using seed 4000. It compares the four estimates and HLL memory
counters against the saved records. It also runs wrapped HLL/FM checks against
unwrapped timestamp oracles. A successful run ends with `PASS`. The compiler
defaults to `c++`; override it with `CXX` or `--cxx` if needed.

## Where to start reading

The methods are in [src/sketches.hpp](src/sketches.hpp). `PackedKMV` implements
S-KMV and Elastic S-KMV together; the constructor's `elastic` argument enables
the additional candidate state. Both experiments instantiate `KMV32`, which
stores 32-bit hash values.

Read `update()` for the overall recording path, `expire()` for sliding-window
maintenance, then `discard()` and `promote()` for the elastic extension.
`query()` combines the bucket estimates. Comments next to these routines explain
why each condition is needed, as well as the packed field offsets.

The other useful entry points are:

| File | Role |
|---|---|
| [src/replay.cpp](src/replay.cpp) | Generates each schedule and feeds all four methods the same arrivals. |
| [src/common.hpp](src/common.hpp) | Shared hashing. |
| [src/stable_alpha.hpp](src/stable_alpha.hpp) | HLL normalization computed outside the arrival loop. |
| [src/validate_baselines.cpp](src/validate_baselines.cpp) | Baseline checks across wraps, rate changes, and idle periods. |
| [run.py](run.py) | Builds the C++ driver and chooses replay settings. |
| [analyze.py](analyze.py) | Recomputes error curves and confidence intervals from query records. |
| [plot.py](plot.py) | Draws those curves with the shared rate diagram. |

## S-KMV: what is retained, and why the threshold stays fixed

Each bucket has `k` ordinary slots. A slot holds a hash value and the timestamp
of its latest occurrence. The bucket also stores its admission threshold,
last-arrival timestamp, occupancy, and a `bounded` bit. The storage buffer `a`
is bit-packed; `stride` is bits per bucket and `m` is the number of buckets
that fit in the memory allocation.

The entries are an **unsorted** array. After expiration, `count(i)==k` means
k-complete; fewer entries means k-partial. The `bounded` bit says whether a
sampling threshold has been established. It is not the paper's lock bit:
it remains true in both complete and partial sampled buckets.

An arrival first triggers expiration if this is the bucket's first arrival
in the slot. A repeated retained hash refreshes its timestamp. A new hash at
or below the threshold fills a vacancy or replaces the maximum hash in a full
bucket. A larger hash cannot enter through this ordinary path.

When an entry expires, S-KMV keeps the threshold. It cannot simply raise it to
fill the vacancy, because smaller active hashes might have been discarded
without a record. A full window with no arrivals permits a reset, but an empty
retained sample alone does not. Rejected arrivals therefore refresh the
last-arrival timestamp too.

## Elastic S-KMV: recovering a missing successor

Elastic S-KMV adds one candidate outside the ordinary bucket. This gives it a
way to establish which omitted active hash may safely enter next.

| Candidate field | What it answers |
|---|---|
| `c` | Which hash is currently being considered as the successor? |
| `tau` | When was that item last observed? |
| `g` | When did the history supporting this candidate begin? |
| `present` bit | Does a candidate exist? |
| `expired` bit | Has its latest occurrence expired? |
| History-complete bit | Has the history beginning at `g` spanned a full window? |

In the code, the last three bits are at offsets `c+HB+16`, `c+HB+17`, and
`c+HB+18`, where the local variable `c` is the candidate's **bit address**.
The hash value stored at that address is the mathematical candidate value.
`HB` is the hash width, and 16 accounts for the two eight-bit timestamps.

### Maintaining the candidate: `discard()`

Despite its name, this routine does not simply throw an item away. It considers
an active pair that is outside the ordinary retained sample: a rejected arrival
or an active pair evicted from a full bucket. An evicted pair keeps its original
occurrence timestamp. Expiration removes inactive pairs without passing them
here.

The three cases are:

1. **No candidate:** store the pair and start its history at the current time.
2. **Smaller or equal hash:** keep `g` and its history-complete status. A smaller
   hash replaces the candidate; an equal hash keeps the later occurrence time.
3. **Larger hash:** replace only an expired candidate, and restart the history.
   Otherwise, retain the current candidate.

A smaller replacement can inherit history because a previously observed hash
below the new value would also have been below the old value. A larger
replacement cannot make that claim: values between the two may have been
ignored. This is why `tau` and `g` are separate.

### Expanding the threshold: `promote()`

Promotion requires all three of these conditions:

- The ordinary bucket has a vacant slot.
- The candidate is active.
- Its history has covered a full window.

The routine copies the candidate pair into the vacant slot, preserves its
occurrence timestamp, and raises the threshold to its hash value. It then clears
the candidate state. The next candidate starts a new history.

For example, suppose a partial bucket has threshold 0.20, while its candidate
has hash 0.35, history start 10, and latest occurrence 80. With a 100-slot
window at time 110, the history is old enough and the item is still active.
Promotion inserts `(0.35, 80)` and sets the threshold to 0.35. It does not write
110 as the occurrence time: moving an entry is not a new stream observation.
The numbers illustrate the rule; they are not an additional experimental run.

### Why recording can check promotion twice

Expiration/maintenance may make a candidate eligible before an arrival is
processed. An above-threshold arrival can also refresh an expired candidate
whose history is already complete, so `update()` checks again after candidate
maintenance. Successful promotion clears the candidate; a newly started
history cannot span a window in the same slot. Thus these checks do not promote
two candidates on one arrival.

This is different from the earlier elastic rule preserved in the
[Figure 10 folder](../figure10/README.md). Use this folder to study candidate
promotion, and keep each folder's implementation when reproducing its figure.

## Querying and the wrapped clock

`query()` first performs maintenance, including eligible promotion. It counts
ordinary retained hashes **strictly below** the query boundary and divides by
that normalized boundary. A certified active candidate that remains outside
the bucket can supply the boundary; the candidate itself is excluded from the
count. Otherwise, the query uses the bucket threshold. In the exact-counting
initial/reset state, it returns the retained count directly.

The numerator is not always occupancy minus one: the item that established the
threshold might have expired. Bucket estimates are summed, because buckets
cover disjoint populations. Stored 32-bit hashes use midpoint conversion
`(hash + 0.5) / 2^32`; collisions within a bucket are treated as duplicate hashes,
without an additional collision correction.

All four methods use timestamps modulo 256 with a 100-slot window. The driver
runs maintenance every 50 slots, including for idle buckets. Candidate expiry
and history completion are latched in bits, so another clock wrap cannot undo
them. Calls to `update()` alone are not a replacement for scheduled maintenance.

## Workloads and memory layouts

Every schedule uses 60 seeds, numbered 4000–4059. An epoch contains 100 slots.
The high rate is 10,000 new identifiers per slot and the low rate is 625, giving
window cardinalities of 1,000,000 and 62,500 at the queried epoch boundaries.
All arrivals in this workload have distinct integer identifiers. The sketches
remain alive across rate changes; there is no reset at a phase boundary.

| Schedule | Epochs | Rate changes |
|---|---:|---|
| Permanent decrease | 512 | 20 high epochs, then 492 low |
| Permanent increase | 128 | 4 low epochs, then 124 high |
| Repeated changes | 512 | 64 high, then 64 low; repeated four times |

Memory uses decimal units and rounds down to whole 64-bit words. The allocation
counts packed algorithm state, including timestamps, metadata, candidate bits,
and HLL histories. Host object/vector overhead and diagnostic counters are
outside that accounting.

| Memory | Allocated bits | S-KMV / Elastic k | Buckets | HLL registers / nodes | T-FM registers |
|---|---:|---:|---:|---:|---:|
| 1 kbit | 960 | 22 / 21 | 1 / 1 | 4 / 48 | 3 |
| 50 kbit | 49,984 | 248 / 247 | 5 / 5 | 256 / 1,964 | 173 |

The hash seed is `mix(20261017 + seed_id)`, with value-hash salt `mix(seed+1)`.
HLL uses five-bit ranks and a fixed history pool; pool exhaustion aborts the
run. Each T-FM register has 32 positions, each with eight timestamp bits and one
validity bit. The HLL layouts differ from Figure 10 because the longer dynamic
workloads need more history per register.

The figure reports RRMSE, pooling squared relative errors before taking the
square root. Plot points group four epochs, except that the decrease uses
eight-epoch groups after epoch 20. Bands use 2,000 paired whole-seed bootstrap
resamples. No outliers are removed or curves fitted. Triangles mark values
outside the displayed range.

## Recompute the summaries or replay the stream

To check the analysis using the supplied raw measurements:

```sh
python3 analyze.py --memory 1000
python3 analyze.py --memory 50000
python3 plot.py --data outputs --output outputs/recomputed
```

To rerun the complete stream experiment instead:

```sh
python3 run.py --full
python3 analyze.py --memory 1000 --data outputs/replay --output outputs/recomputed
python3 analyze.py --memory 50000 --data outputs/replay --output outputs/recomputed
python3 plot.py --data outputs/recomputed --output outputs/recomputed
```

Full replay processes tens of billions of arrivals sequentially and can take
hours. It leaves `data/` unchanged. Existing replay CSVs are never overwritten;
choose a fresh `--output` directory for another run and use its `replay/`
subdirectory as the analysis input.

The compressed `data/*.csv.gz` files contain the original measurements, paired
by schedule, seed, epoch, and true cardinality. The original KMV and baseline
runs were separate; the packaged driver feeds all four methods together while
preserving each sketch's update/query order. The `curves_*.json` and
`scores_*.json` files are saved aggregates. `VALIDATION.md` records the checks
performed, and `SHA256SUMS` verifies the supplied files.

This package contains no personal paths, author identities, or Git history.
Build products and outputs are ignored by Git. An anonymous repository and
commit identity are also needed if publishing the package.
