"""Q295 registration Base page -> Combined page (= the Visible Human body's atlas frame).
Base M / Base F are the unfitted Z-Anatomy bodies; Combined M / F are the same Z-Anatomy meshes fitted per bone onto the VH skeleton (Q168 / Q217)
with the soft tissue carried. So every structure present on both pages with identical triangles gives vertex-to-vertex correspondences
(bones, muscles, organs, skin patches): a thin-plate spline (Q292's lib292.Map: similarity + TPS, uniform 8 mm control-point subsample)."""
from __future__ import annotations
import pickle, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q292"))
import lib292 as L  # noqa: E402

PAIR = {"base_m": "comb_m", "base_f": "comb_f"}
CACHE = Path("/dev/shm/q295")


def pairs(base, comb, cats=("bone", "cartilage", "muscle", "skin", "viscera", "joint"), step=4):
    X, Y, n = [], [], {}
    bmap = {}
    for s, k in enumerate(base.ids):
        bmap.setdefault(k, s)
    for k, sb in bmap.items():
        if base.cats[sb] not in cats or k not in comb.idmap:
            continue
        sc = comb.idmap[k]
        fb = base.F[base.fs == sb]; fc = comb.F[comb.fs == sc]
        if fb.shape != fc.shape:
            continue
        ub = np.unique(fb); uc = np.unique(fc)
        if len(ub) != len(uc) or not np.array_equal(fb - fb.min(), fc - fc.min()):
            continue
        vb = base.V[ub[::step]]; vc = comb.V[uc[::step]]
        X.append(vb); Y.append(vc); n[base.cats[sb]] = n.get(base.cats[sb], 0) + 1
    return np.vstack(X).astype(np.float64), np.vstack(Y).astype(np.float64), n


def build(key, base, comb, smoothing=10.0, ncp=4000):
    p = CACHE / f"reg_{key}.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    X, Y, n = pairs(base, comb)
    # robust: drop pairs whose displacement is far from the local trend (structures moved independently, e.g. Q292 / Q250 edits)
    M0 = L.Map(X, Y, smoothing=200.0, ncp=1500)
    r = np.linalg.norm(M0(X) - Y, axis=1); keep = r < max(8.0, np.percentile(r, 95))
    M = L.Map(X[keep], Y[keep], smoothing=smoothing, ncp=ncp)
    M.info = {"pairs": int(len(X)), "kept": int(keep.sum()), "structures_by_cat": n, "scale": float(M.s),
              "resid_median_mm": float(np.median(M.resid)), "resid_p95_mm": float(np.percentile(M.resid, 95))}
    p.write_bytes(pickle.dumps(M))
    return M


class Grid:
    """the registration sampled on a regular 3-D lattice (6 mm) over the page's skin box and trilinearly interpolated:
    the TPS is smooth, so the lattice error is far below the registration's own residual (p99 on 20,000 random points in .err)"""
    def __init__(self, M, lo, hi, step=6.0):
        self.lo = np.asarray(lo, float) - 2 * step; self.step = step
        n = np.ceil((np.asarray(hi, float) + 2 * step - self.lo) / step).astype(int) + 1
        ax = [self.lo[k] + np.arange(n[k]) * step for k in range(3)]
        G = np.stack(np.meshgrid(*ax, indexing="ij"), -1).reshape(-1, 3)
        self.D = M(G).reshape(*n, 3)
        rng = np.random.default_rng(1)
        Q = self.lo + rng.random((20000, 3)) * (n - 1) * step
        self.err = float(np.percentile(np.linalg.norm(self(Q) - M(Q), axis=1), 99))
        self.info = getattr(M, "info", {})

    def __call__(self, P):
        P = np.asarray(P, float); c = ((P - self.lo) / self.step).T
        from scipy import ndimage as ndi
        return np.stack([ndi.map_coordinates(self.D[..., k], c, order=1, mode="nearest") for k in range(3)], 1)


def fast(key, pg, M):
    import pickle
    p = CACHE / f"regrid_{key}.pkl"
    if p.exists():
        return pickle.loads(p.read_bytes())
    skin = pg.sid_where(lambda k, c, n: c == 'skin'); lo, hi = pg.bbox(skin)
    G = Grid(M, lo, hi)
    p.write_bytes(pickle.dumps(G))
    return G
