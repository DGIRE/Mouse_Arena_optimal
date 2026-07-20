"""tracking_dmd — port of common/track_body_head_dmd.m (DMD body/head tracker skeleton).

Faithful skeleton: temporal-median background, dark-pixel body centroid,
bright-pixel head centroid. No fixture (no video in archive); parity with the
MATLAB skeleton behaviour only.
"""
import numpy as np


def _rgb2gray_frame(im):
    """See rgb2gray_frame() nested function in track_body_head_dmd.m.

    MATLAB:
        function g = rgb2gray_frame(im)
            if size(im,3)==3; g = im(:,:,1); else; g = im; end
    """
    im = np.asarray(im)
    if im.ndim == 3 and im.shape[2] == 3:
        return im[:, :, 0]
    return im


def _centroid(w):
    """See centroid() nested function in track_body_head_dmd.m.

    MATLAB:
        function c = centroid(w)
            [yy,xx] = find(w>0);
            if isempty(xx); c=[NaN NaN]; else; c=[mean(xx) mean(yy)]; end

    ``find`` returns 1-based row/column indices; mirrored here by adding 1 to
    the 0-based numpy indices.
    """
    w = np.asarray(w)
    yy, xx = np.nonzero(w > 0)
    if xx.size == 0:
        return np.array([np.nan, np.nan])
    return np.array([xx.mean() + 1.0, yy.mean() + 1.0])


def track_body_head_dmd(vid, opts=None):
    """Body/head tracking from arena video (see track_body_head_dmd.m).

    MATLAB:
        if nargin<2; opts = struct(); end
        if ~isfield(opts,'bodyThresh'); opts.bodyThresh = 40;  end
        if ~isfield(opts,'headThresh'); opts.headThresh = 220; end
        if ~isfield(opts,'mask');       opts.mask = [];        end

        % Pull frames into a grayscale stack
        if isa(vid,'VideoReader')
            nF = vid.NumberOfFrames;
            fr1 = rgb2gray_frame(read(vid,1));
            F = zeros([size(fr1) nF],'like',fr1);
            for k=1:nF; F(:,:,k) = rgb2gray_frame(read(vid,k)); end
        else
            F = vid;
        end
        [H,W,nF] = size(F);
        if isempty(opts.mask); opts.mask = true(H,W); end

        % --- DMD background estimate (low-rank) ---
        X   = double(reshape(F, H*W, nF));
        bg  = median(X, 2);
        FG  = reshape(abs(X - bg), H, W, nF);

        body = nan(nF,2); head = nan(nF,2);
        for k=1:nF
            fk  = double(F(:,:,k)); fgk = FG(:,:,k);
            bmask = (fk < opts.bodyThresh) & opts.mask;
            head_mask = (fk > opts.headThresh) & opts.mask;
            body(k,:) = centroid(bmask .* (fgk+1));
            head(k,:) = centroid(head_mask);
        end

    VID is a VideoReader-like object exposing ``NumberOfFrames`` and
    ``read(k)`` (1-based), or an [H x W x nFrames] array. Returns
    (body, head), each [nFrames x 2] pixel coordinates.
    """
    if opts is None:
        opts = {}
    body_thresh = opts.get("bodyThresh", 40)
    head_thresh = opts.get("headThresh", 220)
    mask = opts.get("mask", None)

    if hasattr(vid, "NumberOfFrames") and hasattr(vid, "read"):
        nF = int(vid.NumberOfFrames)
        fr1 = _rgb2gray_frame(vid.read(1))
        H, W = fr1.shape[0], fr1.shape[1]
        F = np.zeros((H, W, nF), dtype=fr1.dtype)
        F[:, :, 0] = fr1
        for k in range(2, nF + 1):
            F[:, :, k - 1] = _rgb2gray_frame(vid.read(k))
    else:
        F = np.asarray(vid)

    H, W, nF = F.shape

    if mask is None:
        mask = np.ones((H, W), dtype=bool)
    else:
        mask = np.asarray(mask, dtype=bool)

    # --- DMD background estimate (low-rank) --------------------------------
    # Flatten to [pixels x frames]; the near-constant background is the mode
    # with ~zero temporal frequency. A robust static estimate is the temporal
    # median.
    X = F.reshape(H * W, nF).astype(np.float64)
    bg = np.median(X, axis=1)  # TODO: replace with true DMD mode if desired
    FG = np.abs(X - bg[:, None]).reshape(H, W, nF)

    body = np.full((nF, 2), np.nan)
    head = np.full((nF, 2), np.nan)

    for k in range(nF):
        fk = F[:, :, k].astype(np.float64)
        fgk = FG[:, :, k]
        bmask = (fk < body_thresh) & mask
        head_mask = (fk > head_thresh) & mask
        body[k, :] = _centroid(bmask * (fgk + 1))
        head[k, :] = _centroid(head_mask)

    return body, head
