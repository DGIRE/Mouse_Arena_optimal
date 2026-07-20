# Optimization Report — Mouse Arena (Python)

Optimization run following `Python optimization - Claude - update 1.docx` (the
project-agnostic blueprint). Accuracy anchor = the golden MATLAB fixtures + the
original MATLAB source; the frozen Python port is used only for convenience
diffs. Reference: Tariq et al. (2021), eNeuro 8(1) ENEURO.0285-20.2020.

**Bottom line.** Four optimizations delivered. Three are **byte-identical**
(Level-1/2 with max|Δ| = 0.0 vs the original per-trial code) and default ON; one
(`rfft`) is a Level-2 numeric option, default OFF. The golden-fixture suite is
unchanged — **22 passed / 1 skipped** (17 original + 5 new equivalence tests; the
skip is the 48-trial Fig8 population, which needs the 232 MB `DATA_MAT.mat` not
transferable to the cloud). Only 4 source files carry optimization logic; the
figure/optimize call sites were rewired to a byte-identical batched helper.

---

## 1. What was measured (profiling → hot set)

The pipeline deconvolves one raw ethanol trace per trial, in **per-trial Python
loops**, in figs 1–5, in `optimize_kernel` (a τ-grid search), and in `s1e`'s
114-trial behavior import. Each `deconvolve_eth` call re-ran
`design_lowpass_fir(Fs)` — a Kaiser-window design with a `kaiserord` estimate and
a numtaps-growth loop that evaluates `freqz(worN=8192)` several times — even
though the design depends only on `Fs` (≈500 for every trial). Measured on a real
35 679-sample trace: `design_lowpass_fir` = 3.2 ms/call = **13 %** of a
`deconvolve_eth` call, repeated `nT` times per figure (≈0.37 s of pure redundancy
at nT = 114).

Two secondary hot spots: `schmitt_trigger` (make_fig7) ran a per-sample Python
loop (≈5 ms per full trace); the figure deconvolution loops paid Python
per-iteration overhead on top of the redundant FIR design.

`find_contacts` was profiled and **left untouched**: its cost is in
`scipy.signal.peak_prominences` (C), not the tiny greedy-distance Python step, so
it is not a real bottleneck (blueprint: do not optimize unprofiled code).

## 2. Optimizations, acceptance levels, and gates

| ID | Change | File(s) | Level | Gate result |
|----|--------|---------|-------|-------------|
| E1 | **Cache the Kaiser FIR design** by `Fs` (`lru_cache`) | `deconvolution.py` | 1 — exact | cached vs uncached taps **max\|Δ\| = 0.0**; fixture 03 unchanged |
| E2 | **Vectorize `schmitt_trigger`** (O(N) event forward-fill) | `detection.py` | 1 — exact | vec vs loop **0 mismatches** on 100+ fuzz + edge cases + fixture 04 |
| E3 | **Batch the per-trial deconvolution** (`deconvolve_eth_batch`) + rewire figs 1–5, `optimize_kernel` | `deconvolution.py`, `figures/make_fig1–5.py`, `optimize.py` | 1 — exact | batched vs per-row loop **max\|Δ\| = 0.0** (dec + norm), invariant to chunk size |
| E5 | **rfft FFT backend** (opt-in, default OFF) | `deconvolution.py` | 2 — numeric | rfft vs complex ≤ **6.3e-12** (deconv tol 1e-4) |

All switches live in `mouse_arena/optconfig.py`. `optconfig.set_baseline()` is
the one-switch revert (blueprint R7): it forces every path back to the original,
reproducing the pre-optimization output **bit-for-bit** (E1–E3) and the exact
complex FFT (E5). Defaults are the optimized paths.

### Gate summary (blueprint §7)
- **G1 Baseline integrity** — baseline frozen (`../Python`), fixtures + MATLAB
  reference resolved, tolerances/hazards from `HAZARD_CATALOG.md` ingested. ✅
- **G2 Bottleneck evidence** — FIR redundancy and the per-trial loops quantified
  by profiling (above). ✅
- **G3 Isolated implementation** — each change is one coherent component with a
  config switch and a preserved baseline path. ✅
- **G4 Numerical equivalence** — E1–E3 byte-identical (max|Δ| = 0.0); E5 inside
  the fixed 1e-4 tolerance. Tolerances were fixed before implementation. ✅
- **G5 Scientific equivalence** — no statistic, threshold, inclusion rule,
  randomization, or reported number changes on the default paths. The Fig8 KS
  decision, contact counts, and all fixture outputs are unchanged. E5 is opt-in
  and does not alter any decision within tolerance. ✅
- **G6 Performance benefit** — measurable and holds across workload sizes (§3). ✅
- **G7 Code quality** — optimized + fallback paths both tested
  (`tests/test_10_opt_equivalence.py`); memory bound documented. ✅
- **G8 Integration** — full suite green (22/1); fixture-equivalence re-asserted. ✅

## 3. Performance (medians; `benchmarks/bench_deconv.py`)

| Benchmark | Baseline | Optimized | Speedup |
|-----------|----------|-----------|---------|
| B1 Kaiser FIR design / call | 3.2 ms | 0.3 µs (cached) | ~10 000× on that call |
| B2 `schmitt_trigger`, N = 35 679 | 5.2 ms | 0.57 ms | ~9× |
| B3 figure deconv loop, nT = 24 | 422 ms | 173 ms | **2.44×** |
| B3 figure deconv loop, nT = 60 | 1063 ms | 491 ms | **2.16×** |
| B3 figure deconv loop, nT = 114 | 2030 ms | 831 ms | **2.44×** |
| End-to-end golden-fixture suite | 5.70 s | 4.56 s | 1.25× (identical results) |
| B5 rfft vs complex, N = 356 790 | 179 ms | 168 ms | 1.07× (opt-in) |

The batched deconvolution (E3) is the headline end-to-end win: it removes the
per-trial Python overhead **and** the redundant FIR design (E1), so the
sensor-characterization figures (1–5), `optimize_kernel`, and `s1e` all run
~2.2–2.4× faster with byte-identical output.

## 4. Memory (R2/R8)

`deconvolve_eth_batch` processes rows in chunks of `OPT.batch_rows` (default 64).
Peak extra memory ≈ `batch_rows × N × 8 bytes` for the float working set plus a
same-size complex FFT temporary (×2 for `complex`, ×1 for `rfft`). The result is
**identical for any chunk size ≥ 1**, so `batch_rows` is a pure memory/throughput
dial — lower it for very long recordings or very wide trial matrices, raise it
for maximum throughput. Cost-vs-size table for a single chunk:

| batch_rows | N = 40 k, complex | N = 300 k, complex |
|------------|-------------------|--------------------|
| 8  | ~5 MB  | ~38 MB |
| 64 | ~40 MB | ~300 MB |
| 256| ~160 MB| ~1.2 GB |

## 5. Scientific notes / caveats

- E1–E3 change **no numbers** — they are refactors proven byte-identical, so
  there is no scientific-equivalence risk on the default paths.
- E5 (`rfft`) is a genuine numeric change (≤ ~1e-11, far inside the 1e-4
  deconvolution tolerance). It is OFF by default; turn it on only if the extra
  FFT throughput matters, and note its speedup is workload-dependent (≈1.5× on
  awkward composite lengths, ≈1.07× when pocketfft already handles the length
  well). No pipeline decision changes within tolerance.
- The hazard catalog (H1–H11) was treated as do-not-touch: the FIR taps,
  filtfilt padlen, FFT length `N` (never padded to a "fast" length — that would
  change the result), findpeaks order, and KS formula are all unchanged.

## 6. Local certification (what still needs David's machine)

The cloud environment cannot hold three large fixture inputs (Fig1 262 MB,
Fig5 87 MB, `DATA_MAT` 232 MB), so figs 1/5 end-to-end and the Fig8 **population**
test are validated here by (a) the byte-identical equivalence gates above and
(b) the unchanged small-fixture suite. To certify at full scale, run locally in
`Optimized Python`:

```bash
pip install -r requirements.txt
MA_FIXTURES="<Gold Fixtures>/fixtures"  python -m pytest tests/ -q
python -m benchmarks.bench_deconv
```

With `DATA_MAT.mat` present under `fixtures/06_data_mat/data_mat/outputs/`, the
population test un-skips and must still report n_contacts = 60, n_trials = 48,
head_p = 0.0126, body_p = 0.0644 (unchanged from baseline).
