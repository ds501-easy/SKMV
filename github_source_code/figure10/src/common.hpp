#pragma once
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <vector>
using u64=uint64_t;
// Deterministic SplitMix64 mixing. Drivers use separate salts for bucket
// assignment and within-bucket hash values, shared across compared methods.
inline u64 mix(u64 x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
// Midpoint embedding for the optional 64-bit KMV specialization. The figure
// experiments instantiate KMV32, whose conversion appears in query().
inline double unit(u64 h){return std::ldexp((double)(h>>11)+0.5,-53);}
