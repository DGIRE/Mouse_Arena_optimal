"""optimize — port of common/optimize_kernel.m (grid-search tau_rise/tau_decay by deconv-vs-PID RMSE)."""
import numpy as np

from .deconvolution import deconvolve_eth, deconvolve_eth_batch
from .kernels import doe_kernel


def optimize_kernel(eth_trials, pid_trials, taus_rise, taus_decay, Fs=500.0):
    """Grid-search tau_rise/tau_decay for the deconvolution kernel (see optimize_kernel.m).

    MATLAB:
        function [RMSE, taus_rise, taus_decay] = optimize_kernel(ETH_trials, PID_trials, ...
                taus_rise, taus_decay, Fs)
        if nargin<5||isempty(Fs); Fs=500; end
        nT = size(ETH_trials,1); N = size(ETH_trials,2);
        RMSE = zeros(nT, numel(taus_rise)*numel(taus_decay));
        for it = 1:nT
            ci = 0;
            for ir = 1:numel(taus_rise)
                for id = 1:numel(taus_decay)
                    ci = ci+1;
                    kn = doe_kernel(taus_rise(ir), taus_decay(id), N, Fs);
                    d  = deconvolve_eth(ETH_trials(it,:), kn, Fs);
                    dn = (d-min(abs(d)))./(max(abs(d))-min(abs(d)));
                    pn = PID_trials(it,:)'; pn = (pn-min(pn))./(max(pn)-min(pn));
                    seg = 500:numel(dn)-500;
                    RMSE(it,ci) = sqrt(mean((dn(seg)-pn(seg)).^2));
                end
            end
        end
        end

    ETH_TRIALS, PID_TRIALS: [nTrials x nSamples], normalized.
    Returns (RMSE, taus_rise, taus_decay) where RMSE is [nTrials x (nRise*nDecay)].
    """
    if Fs is None:
        Fs = 500.0

    eth_trials = np.asarray(eth_trials, dtype=np.float64)
    pid_trials = np.asarray(pid_trials, dtype=np.float64)
    taus_rise = np.asarray(taus_rise, dtype=np.float64).reshape(-1)
    taus_decay = np.asarray(taus_decay, dtype=np.float64).reshape(-1)

    nT = eth_trials.shape[0]
    N = eth_trials.shape[1]
    RMSE = np.zeros((nT, taus_rise.size * taus_decay.size), dtype=np.float64)

    # OPTIMIZED: the kernel depends only on (ir, idc), not the trial, so loop over
    # kernels and deconvolve ALL trials at once (byte-identical to the original
    # trial-outer / kernel-inner loop). PID normalization is trial-only -> hoist.
    seg = slice(499, N - 500)
    PN = pid_trials - pid_trials.min(axis=1, keepdims=True)
    PN = PN / (pid_trials.max(axis=1, keepdims=True) - pid_trials.min(axis=1, keepdims=True))

    ci = -1
    for ir in range(taus_rise.size):
        for idc in range(taus_decay.size):
            ci += 1
            kn = doe_kernel(taus_rise[ir], taus_decay[idc], N, Fs)
            DEC, _ = deconvolve_eth_batch(eth_trials, kn, Fs)   # (nT, N)
            ad = np.abs(DEC)
            admin = ad.min(axis=1, keepdims=True)
            DN = (DEC - admin) / (ad.max(axis=1, keepdims=True) - admin)
            RMSE[:, ci] = np.sqrt(np.mean((DN[:, seg] - PN[:, seg]) ** 2, axis=1))

    return RMSE, taus_rise, taus_decay
