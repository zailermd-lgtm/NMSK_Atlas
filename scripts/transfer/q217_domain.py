"""Q217: the container of HIS left forearm muscles on a 0.5 mm grid: where his photographs show muscle / tendon (colour classes 3 / 4 / 5), minus his bones, inside his skin.
Everything is atlas mm; the grid is `VoxGrid(lo, hi, 0.5)` of q216_common."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q216_common import VoxGrid  # noqa: E402
from scripts.zanatomy.q198_core import Grid  # noqa: E402

H = 0.5
BOX_LO = np.array([-278.0, 96.0, -88.0])
BOX_HI = np.array([-132.0, 342.0, 142.0])


def new_grid(lo=BOX_LO, hi=BOX_HI, h=H):
    return VoxGrid(lo, hi, h)


def bone_solid(g, v, f, close=2):
    """filled solid of a (possibly open-ended) CT bone mesh on the grid g (surface closed by `close` dilations, as the Q198 / Q204 Grid.solid)"""
    lo = np.maximum(g.idx(v.min(0) - 3.0), 0)
    hi = np.minimum(g.idx(v.max(0) + 3.0) + 1, np.asarray(g.shape))
    out = np.zeros(g.shape, bool)
    if (hi <= lo).any():
        return out
    sub = Grid(g.pos(lo), g.pos(hi - 1), g.h)
    s = sub.solid(np.asarray(v, float), np.asarray(f, np.int64), close=close)
    sl = tuple(slice(int(a), int(a) + s.shape[k]) for k, a in enumerate(lo))
    sl = tuple(slice(sl[k].start, min(sl[k].stop, g.shape[k])) for k in range(3))
    sub_s = tuple(slice(0, sl[k].stop - sl[k].start) for k in range(3))
    out[sl] = s[sub_s]
    return out


def photo_on_grid(cls, photo_lo, g):
    """class volume (1 mm photographs) sampled on the grid g (nearest)"""
    ii = np.arange(g.shape[0])
    X = np.floor(g.lo[0] + ii * g.h - photo_lo[0] + 0.5).astype(int)
    Y = np.floor(g.lo[1] + np.arange(g.shape[1]) * g.h - photo_lo[1] + 0.5).astype(int)
    Z = np.floor(g.lo[2] + np.arange(g.shape[2]) * g.h - photo_lo[2] + 0.5).astype(int)
    okx = (X >= 0) & (X < cls.shape[0])
    oky = (Y >= 0) & (Y < cls.shape[1])
    okz = (Z >= 0) & (Z < cls.shape[2])
    out = np.zeros(g.shape, np.uint8)
    sub = cls[np.ix_(np.clip(X, 0, cls.shape[0] - 1), np.clip(Y, 0, cls.shape[1] - 1), np.clip(Z, 0, cls.shape[2] - 1))]
    sub = sub * (okx[:, None, None] & oky[None, :, None] & okz[None, None, :])
    out[:] = sub
    return out


def muscle_domain(pc, bone, close_mm=2.0, h=H):
    """photographed muscle / tendon voxels (classes 3, 4, 5), closed by `close_mm`, minus the bones"""
    M = (pc == 3) | (pc == 4) | (pc == 5)
    it = int(round(close_mm / h))
    # closing on the 1 mm photographs' resolution: dilate then erode with a ball
    st = ndi.generate_binary_structure(3, 1)
    Mc = ndi.binary_closing(np.pad(M, it), structure=st, iterations=it)[it:-it, it:-it, it:-it] & (pc > 0)
    return Mc & ~bone


def container(pc, bone, fixed, close_mm=2.0, tol_mm=1.0, skin_in_mm=1.5, h=H):
    """voxels where a forearm muscle may be: his photographed muscle / tendon / pale (septum) voxels closed by close_mm and widened by tol_mm (registration error), inside the photographed body outline
    by skin_in_mm, minus his bones and the fixed neighbours"""
    st = ndi.generate_binary_structure(3, 1)
    M = (pc == 3) | (pc == 4) | (pc == 5)
    it = int(round(close_mm / h))
    Mc = ndi.binary_closing(np.pad(M, it), structure=st, iterations=it)[it:-it, it:-it, it:-it]
    Mc = ndi.binary_dilation(Mc, structure=st, iterations=int(round(tol_mm / h)))
    body = ndi.binary_erosion(pc > 0, structure=st, iterations=int(round(skin_in_mm / h)))
    return Mc & body & ~bone & ~fixed
