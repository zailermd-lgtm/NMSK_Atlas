"""Q211 core: the Z-fitted pages (male Q210 = before, female Q208 = before), their unfitted Z bases, the bone-anchored chain field between a base (or an earlier pose) and the fitted bones,
and the 'is this structure where the bone chain says' test that separates pose-driven metric artefacts from real defects of the Q198 elbow / shoulder junction audit.
Everything works on the DECODED shipped geometry of a page (q207_core.Page)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q211_paths  # noqa: F401,E402  (the Q198 loader's page table: unfitted bases + the Z fits before / after)
from scripts.zanatomy import q207_core as C7  # noqa: E402
from scripts.zanatomy import q199_elbow as E  # noqa: E402

PAGES = {
    "male": dict(src=REPO / "build/q210/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", out=REPO / "build/q211/viewer_zan_vhm", base=REPO / "build/q197/viewer_zan_atlas", base_stem="atlas_viewer_zan_atlas",
                 key0="q210_m", key1="q211_m", base_key="z_male", fit_key="z_male_fit"),
    "female": dict(src=REPO / "build/q208/viewer_zan_female", stem="atlas_viewer_zan_female", out=REPO / "build/q211/viewer_zan_female", base=REPO / "build/q202/viewer_base_female", base_stem="atlas_viewer_base_female",
                   key0="q208_f", key1="q211_f", base_key="z_base_f", fit_key="z_female_fit"),
}
C7.PAGES["male"]["src"], C7.PAGES["female"]["src"] = PAGES["male"]["src"], PAGES["female"]["src"]
BUILD = REPO / "build" / "q211"


def load(which, src=None, base=False):
    c = PAGES[which]
    if base:
        return C7.Page(which, src=c["base"], stem=c["base_stem"])
    return C7.Page(which, src=src or c["src"], stem=c["stem"])


def state_path(which, stage):
    BUILD.mkdir(parents=True, exist_ok=True)
    return BUILD / f"{which}_{stage}.pkl"


def matched(pg, base):
    """ids present on both pages with the same vertex count and faces"""
    out = []
    for i in pg.ids:
        if i in base.S and len(pg.v(i)) == len(base.v(i)) and np.array_equal(pg.f(i), base.f(i)):
            out.append(i)
    return out


class ChainField:
    """D(x) = sum_b w_b(x) D_b(x) / sum w: the displacement of the BONES between two poses (`v0`: id -> vertices before, `v1`: id -> vertices after) interpolated to a point: moving bones
    (max vertex displacement > moved_mm) carry their nearest-vertex displacement (k = 3, inverse distance), every other bone within 450 mm of `centre` is a fixed anchor (D = 0), plus a null anchor
    (the Q199 / Q206 field, weights 1 / (d + 6 mm)^2)."""

    def __init__(self, v0, v1, centre, bone_ids, moved_mm=0.3, reach=450.0, only=None):
        self.moving, fixed = {}, []
        for i in bone_ids:
            a, b = np.asarray(v0[i], float), np.asarray(v1[i], float)
            if np.linalg.norm(a.mean(0) - centre) > reach:
                continue
            dv = b - a
            if np.linalg.norm(dv, axis=1).max() > moved_mm and (only is None or i in only):
                self.moving[i] = (cKDTree(a), dv)
            else:
                fixed.append(a)
        self.fixed = cKDTree(np.vstack(fixed)) if fixed else None
        self.bone_dv = {i: float(np.linalg.norm(m[1], axis=1).max()) for i, m in self.moving.items()}

    def __call__(self, X, gated=False):
        X = np.asarray(X, float)
        W, D = [], []
        for i, (tree, dv) in self.moving.items():
            d, j = tree.query(X, k=3)
            w = 1.0 / (d + 0.5)
            w /= w.sum(1, keepdims=True)
            D.append((dv[j] * w[:, :, None]).sum(1))
            W.append(1.0 / (d[:, 0] + E.W_SOFT_MM) ** E.W_POWER)
        if self.fixed is not None:
            W.append(1.0 / (self.fixed.query(X)[0] + E.W_SOFT_MM) ** E.W_POWER)
            D.append(np.zeros_like(X))
        W.append(np.full(len(X), 1.0 / (E.W_NULL_MM + E.W_SOFT_MM) ** E.W_POWER))
        D.append(np.zeros_like(X))
        W = np.array(W)
        W /= W.sum(0)
        R = (W[:, :, None] * np.array(D)).sum(0)
        return E.gated(R) if gated else R


def bone_ids(pg, side=None):
    return [i for i in pg.ids if pg.sys(i) == "bone" and (side is None or i.endswith("_" + side))]


# ---------------------------------------------------------------------------------------------------------- Q198 fit-seam measures on arrays (frame offsets, adjacency tears)
def umeyama(P, Q):
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc) / len(P)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    s = (S * np.diag(D)).sum() / (((P - pc) ** 2).sum() / len(P))
    return s, R, qc - s * R @ pc


def rot_angle(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def zone_arrays(base_v, fit_v, sys_of, ids, centre, R):
    """vertex arrays of the structures with a vertex within R of `centre` (base frame), vertices inside R only: V (base), W (fit), L (structure index)"""
    V, W, L, keep = [], [], [], []
    for i in ids:
        m = np.linalg.norm(base_v[i] - centre, axis=1) < R
        if not m.any():
            continue
        V.append(base_v[i][m])
        W.append(fit_v[i][m])
        L.append(np.full(m.sum(), len(keep)))
        keep.append(i)
    return np.concatenate(V), np.concatenate(W), np.concatenate(L), keep


def frame_offsets(V, W, L, ids, sys_of, bones, centre, base_v):
    """the Q198 fit-seam 'frame offset' of each soft structure hugging the joint's own bones: offset (mm) of its centroid under its own similarity (base -> fit, Umeyama over its zone vertices) from the
    image under the nearest of `bones`' similarities; rotation difference"""
    tf = {}
    for n, i in enumerate(ids):
        m = L == n
        if m.sum() < 25:
            continue
        s, Rm, t = umeyama(V[m], W[m])
        tf[i] = dict(s=s, R=Rm, t=t, pc=V[m].mean(0), sys=sys_of(i))
    bs = [b for b in bones if b in tf]
    if not bs:
        return {}
    btree = cKDTree(np.concatenate([base_v[b] for b in bs]))
    out = {}
    for i, T in tf.items():
        if T["sys"] in ("bone", "skin", "lymph", "viscera", "cns", "bursa", "cartilage"):
            continue
        if btree.query(T["pc"])[0] > 25:
            continue
        pcs = T["pc"]
        dd = {b: float(np.linalg.norm((T["s"] * T["R"] @ pcs + T["t"]) - (tf[b]["s"] * tf[b]["R"] @ pcs + tf[b]["t"]))) for b in bs}
        bn = min(dd, key=dd.get)
        out[i] = {"frame_offset_mm": round(dd[bn], 1), "nearest_bone_frame": bn, "rot_vs_bone_deg": round(rot_angle(T["R"].T @ tf[bn]["R"]), 1), "scale": round(T["s"], 3)}
    return out


def adjacency_pairs(V, L, soft, dist=2.0):
    tr = cKDTree(V)
    pr = tr.query_pairs(dist, output_type="ndarray")
    pr = pr[L[pr[:, 0]] != L[pr[:, 1]]]
    return pr[soft[L[pr[:, 0]]] & soft[L[pr[:, 1]]]]
