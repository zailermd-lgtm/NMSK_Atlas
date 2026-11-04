"""Q217: quick slice views of voxel label volumes (y = const planes) on the 0.5 mm grid"""
from __future__ import annotations

import colorsys
import zlib

import numpy as np


def colour(name):
    h = (zlib.crc32(name.encode()) % 1000) / 1000.0
    return np.array(colorsys.hsv_to_rgb(h, 0.8, 0.85))


def slice_image(g, y, layers, photo=None):
    """layers: list of (name, bool volume or int label volume with names dict) painted in order; returns RGB float image [z, x]"""
    j = int(round((y - g.lo[1]) / g.h))
    shape = (g.shape[2], g.shape[0])
    img = np.zeros(shape + (3,))
    if photo is not None:
        pal = {0: (0.05, 0.05, 0.05), 1: (0.35, 0.35, 0.35), 2: (0.93, 0.85, 0.5), 3: (0.55, 0.15, 0.1), 4: (0.8, 0.8, 0.95), 5: (1, 1, 1)}
        p = photo[:, j, :].T
        for k, c in pal.items():
            img[p == k] = c
    for name, vol, col in layers:
        s = vol[:, j, :].T
        if col is None:
            for lab in np.unique(s[s > 0]):
                img[s == lab] = colour(str(lab))
        else:
            img[s] = 0.5 * img[s] + 0.5 * np.asarray(col)
    return img[::1]


def save_levels(path, g, levels, layers, photo=None, xwin=None, zwin=None, ncol=3, title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    n = len(levels)
    nr = int(np.ceil(n / ncol))
    fig, axs = plt.subplots(nr, ncol, figsize=(5.2 * ncol, 4.6 * nr), squeeze=False)
    ext = [g.lo[0], g.lo[0] + g.shape[0] * g.h, g.lo[2], g.lo[2] + g.shape[2] * g.h]
    for k, y in enumerate(levels):
        a = axs[k // ncol, k % ncol]
        a.imshow(slice_image(g, y, layers, photo), origin="lower", extent=ext, interpolation="nearest")
        a.set_title(f"{title} y={y}", fontsize=8)
        if xwin:
            a.set_xlim(*xwin)
        if zwin:
            a.set_ylim(*zwin)
    for k in range(n, nr * ncol):
        axs[k // ncol, k % ncol].axis("off")
    plt.tight_layout()
    plt.savefig(path, dpi=70)
    plt.close(fig)
