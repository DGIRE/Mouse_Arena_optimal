# MATLAB → SciPy Hazard Catalog (Mouse Arena)

Numerical divergence hazards and their **verified** resolutions. Each recipe below
was confirmed to reproduce the golden fixture to the stated precision. Translators
MUST use these; the Auditor checks against them on any failure.

## H1 — LabView `.dat` indexing (io_labview) [confirmed to exact]
- Read `np.fromfile(fn, dtype='>f8')` (big-endian float64).
- Sentinel positions: `pos = np.flatnonzero(data == sentinel)` are **0-based**; MATLAB
  `find` is 1-based. The fixture stores `n_ten` as **1-based** MATLAB indices, so
  `n_ten_matlab = pos + 1`.
- Skip: MATLAB `n_ten(skipRecords:end)` with skipRecords=20 keeps from the 20th, i.e.
  `n_ten_matlab[19:]`.
- End guard: keep sentinels where `n_ten_matlab + max(offset) <= N`.
- Channel extract (MATLAB `data(n_ten + offset)`, 1-based): in 0-based Python that is
  `data[(n_ten_matlab - 1) + offset]`. ETH offset = **3** for the 2019 5-ch map.
- `Fs = 1/(median(diff(time))/1000)`. Store `n_ten` output as the 1-based indices.
- Verified: n_ten[:3] = 115,121,127; Fs=500; ETH matches fixture bit-for-bit.

## H2 — doe_kernel (kernels) [machine precision]
`t=np.arange(N)/Fs; k=exp(-t/tau_decay)-exp(-t/tau_rise); kn=(k-k.min())/(k.max()-k.min())`.
Return column vector (N,1). Straightforward; rtol 1e-10.

## H3 — kaiser FIR design (deconvolution) [confirmed to 2.8e-17]
MATLAB `designfilt('lowpassfir','kaiserwin', PassbandFrequency=0.001,
StopbandFrequency=40, PassbandRipple=0.5, StopbandAttenuation=65, SampleRate=Fs)`.
Reproduce exactly:
- `beta = 0.1102*(Astop-8.7)` for Astop>50  → beta=6.204260 at Astop=65.
- `cutoff = (Fpass+Fstop)/2 / (Fs/2)` → 0.08000200 at Fs=500.
- numtaps: start from `scipy.signal.kaiserord` estimate (51), **grow numtaps until the
  realized response meets the spec** (stopband attenuation ≥ Astop AND passband ripple
  ≤ Apass). This lands on **58** — matching MATLAB designfilt — a principled rule, not a
  magic constant. `taps = scipy.signal.firwin(numtaps, cutoff, window=('kaiser',beta))`.
- Verified: taps match fixture `fir_coeffs` (58) to max |Δ| = 2.8e-17.
- Then `eth_filt = scipy.signal.filtfilt(taps, [1.0], eth)` (FIR → a=1).

## H4 — FFT deconvolution + polarity + normalize (deconvolution) [rtol 1e-4]
`N=len(eth_filt); dec = np.real(np.fft.ifft(np.fft.fft(eth_filt) / np.fft.fft(kn, N)))`.
- `edge = min(500, N//4)`; `idx = slice(edge, N-edge)`.
- Polarity: `a=dec[idx]-dec[idx].mean(); b=eth_filt[idx]-eth_filt[idx].mean();
  if np.dot(a,b) < 0: dec = -dec`.
- `core = np.abs(dec[idx]); norm = (dec - core.min())/(core.max()-core.min())`.
  NOTE: numerator uses the **full** dec, denominator the **core** abs-range (this is why
  eth_deconv_norm ranges ~±17). Return `(dec, norm)` as (N,1).
- `np.fft.fft(kn, N)` = zero-pad/truncate kn to N (matches MATLAB `fft(kn,N)`).

## H5 — Butterworth filtfilt (tracking) [rtol 1e-6]
MATLAB `filtfilt(butter(3,0.1,'low'), xy)` per column. Use
`b,a = scipy.signal.butter(3, 0.1, 'low'); scipy.signal.filtfilt(b,a,xy,axis=0)`.
MATLAB filtfilt default padding = `3*(max(len(a),len(b))-1)` odd reflection; SciPy default
`padtype='odd', padlen=3*max(len(a),len(b))` differs by 1 → set `padlen=3*(max(len(a),len(b))-1)`
to match MATLAB exactly. Verify against fixture 05; adjust padlen/method if edges diverge.

## H6 — fillmissing linear (tracking.clean_track) [exact-ish]
MATLAB `fillmissing(x,'linear','EndValues','nearest')` per column: linear-interp interior
NaNs by index; fill leading/trailing NaNs with nearest finite value. Implement with
`np.interp` over finite indices (interior) then edge-fill with first/last finite value.
Out-of-arena test: `x<xmin | x>xmax | y<ymin | y>ymax | ~isfinite → NaN`.

## H7 — Schmitt trigger (detection) [exact]
Sequential hysteresis, boolean out: `state False; for xi: if not state and xi>=hi: state=True;
elif state and xi<lo: state=False; y.append(state)`. lo defaults hi-0.02. Output logical.

## H8 — findpeaks contact detection (detection / make_fig8) [confirmed against fixture 07]
MATLAB `findpeaks(seg,'MinPeakHeight'=thr,'MinPeakDistance'=round(min_sep_s*Fs_b),
'MinPeakProminence'=thr*prominence_mult)` on `rescale([0,1])` of RAW ethanol on the
body-time base, restricted to entry→reward (`dist<reward_px`), kept if `>min_dist_px`
from source. `rescale([0,1]) = (x-min)/(max-min)`.
Replicate MATLAB's filter ORDER (height → prominence → distance), not SciPy's single-call
order (distance → prominence): (1) all local maxima; (2) keep `seg>=thr`; (3) keep
`peak_prominences(seg,cand) > Pmin` on the full segment; (4) greedy MinPeakDistance,
survivors sorted by DESCENDING height, drop any within `D=max(1,floor(min_sep_s*Fs_b+0.5))`
of an already-accepted taller peak. See `detection.find_contacts`.
**RESOLVED tie-break (the +1 contact):** MinPeakProminence must be **strict `>`**, not `>=`.
MATLAB `findpeaks` rejects a peak whose prominence exactly TIES the floor; SciPy's `>=` keeps
it. Fixture 07: trial 110's peak is the rescaled global max, so `prom == Pmin == 1.0` exactly
(thr=0.25, prominence_mult=4) — `>=` yields 61 contacts, `>` yields the correct 60. Verified
end-to-end: 60 contacts / 48 trials / head_p 0.012613 / body_p 0.064391 vs `fig8_ks_result`.
(MinPeakHeight kept as `>=`; only the prominence tie was observed against the fixture.)
`DATA_MAT.mat` loads via the format-agnostic `dataio.load_data_mat_struct` (h5py for v7.3,
scipy.io for the Level-5 gold `DATA_MAT.mat`).

## H9 — kstest2 two-sample p-value (make_fig8) [confirmed to 3e-16]
SciPy `ks_2samp` reproduces the KS **statistic** exactly but its p-value omits MATLAB's
Stephens continuity correction. Reproduce MATLAB `kstest2` asymptotic p exactly:
```
D = scipy.stats.ks_2samp(a, b).statistic
ne = n1*n2/(n1+n2)
lam = max((sqrt(ne) + 0.12 + 0.11/sqrt(ne)) * D, 0.0)
p = 2*sum_{j=1..∞} (-1)^(j-1) exp(-2 lam^2 j^2)   # ~100 terms; clamp to [0,1]
```
Verified: head_p=0.0126127339, body_p=0.0643908757 to <1e-15.
Contact KS is deterministic; the **random control** (`randi`) is statistical — compare
distributions/verdict, not exact p (fixture random_seed=0 recorded but treat as non-exact).

## H10 — Orientation (everywhere) [#1 false-failure source]
Per-trial `.mat` store `cr_body/cr_head` as `[2 x N]` (h5py reads (N,2) after .T → careful).
Orient to `[N x 2]`: transpose only when rows==2 and cols!=2. `array_specs.orientation`
in each manifest is authoritative. Assert shape/dtype before comparing values.

## H11 — 1-based ↔ 0-based indices
`n_ten`, findpeaks `locs`, and any stored index arrays are 1-based (MATLAB). Keep outputs
1-based where the fixture stores them 1-based; convert only for internal indexing.
