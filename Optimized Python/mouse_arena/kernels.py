"""kernels — port of common/doe_kernel.m (fixture 02_kernel). [Med risk]

doe_kernel(tau_rise, tau_decay, N, Fs=500): t=(0:N-1)/Fs;
k=exp(-t/tau_decay)-exp(-t/tau_rise); kn=(k-min(k))/(max(k)-min(k)). Column
vector in [0,1]. Machine precision.
"""
import numpy as np


def doe_kernel(tau_rise, tau_decay, N, Fs=500.0):
    """Normalized difference-of-exponentials kernel (see doe_kernel.m).

    MATLAB:
        t  = (0:N-1)'/Fs;
        k  = exp(-t/tau_decay) - exp(-t/tau_rise);
        kn = (k - min(k)) ./ (max(k) - min(k));

    Returns an (N,1) column vector rescaled to [0,1].
    """
    N = int(N)
    t = np.arange(N, dtype=np.float64) / Fs
    k = np.exp(-t / tau_decay) - np.exp(-t / tau_rise)
    kn = (k - k.min()) / (k.max() - k.min())
    return kn.reshape(-1, 1)
