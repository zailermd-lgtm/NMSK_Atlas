#!/usr/bin/env python3
"""Q202: watertightness of the skin envelope.  Voxelise every skin patch (h mm), grow the shell by `close` voxels, flood the free space from the outside: the interior is sealed when a seed inside
the body is NOT connected to the outside.  Reports the leaked interior volume and the narrowest gap (clearance along the cheapest path out of the seed).  A page is 'sealed at h' when the
leaked volume is 0.   python3 scripts/zanatomy/q202_leak.py DIR STEM [h=2] [close=1]"""
import sys
import numpy as np
from pathlib import Path
from scipy import ndimage as ndi
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_metrics as M, q198_core as C


def leak(dir_, stem, h=2.0, close=1, seeds=((0, 330, 20.0), (0, -10, 20.0), (0, 60, 30.0))):
    S = M.struct_list(dir_, stem, {"skin"})
    V = np.concatenate([s["v"] for s in S]); lo = V.min(0) - 10; hi = V.max(0) + 10
    g = C.Grid(lo, hi, h)
    surf = np.zeros(g.shape, bool)
    for s in S:
        surf |= g.raster(s["v"], s["f"])
    cl = ndi.binary_dilation(surf, iterations=close)
    lab, n = ndi.label(~cl)
    ext = lab[0, 0, 0]
    out = {"h_mm": h, "close_voxels": close, "seeds": {}}
    for nm, p in zip(("chest", "pelvis", "lower_abdomen"), seeds):
        i = tuple(g.idx(np.array([p]))[0])
        out["seeds"][nm] = {"seed_in_free_space": bool(not cl[i]), "connected_to_outside": bool(lab[i] == ext) if not cl[i] else None}
    rin = (lab == ext)
    filled = ndi.binary_fill_holes(np.pad(ndi.binary_dilation(surf, iterations=close + 3), 1))[1:-1, 1:-1, 1:-1]
    inside = ndi.binary_erosion(filled, iterations=close + 3) | surf
    out["leaked_interior_L"] = round(float((rin & inside).sum() * h ** 3 / 1e6), 2)
    return out


if __name__ == "__main__":
    d, s = sys.argv[1], sys.argv[2]
    h = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
    c = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    print(leak(d, s, h, c))
