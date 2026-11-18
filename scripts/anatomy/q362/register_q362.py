"""Q362: bone-landmark registration of a frozen Imaging page's subject (VH male / VH female) onto a Base page body.

Landmark sets = bones BOTH bodies have, paired by name (never closest-any-bone):
  pelvis  : hip bones, sacrum, coccyx, proximal femora (head to 100 mm below the top of the head)
  kidney  : T11-L4 vertebrae, ribs 11 and 12 (both sides)
  abdomen : L1-L5 vertebrae, hip bones, sacrum, ribs 10-12 (both sides)
Method: a SIMILARITY transform (rotation + translation + one uniform scale) by trimmed symmetric ICP over the paired bones (each bone
weighted equally; per pair: source surface samples -> closest target surface sample and target -> source, the worst 10 % of each bone's
pairs dropped each round), Umeyama closed form per round.  Optional low-order warp (`warp`): a smoothed thin-plate spline through at
most N_CTRL control points taken ONLY on those bones (source point -> its closest target bone point after the similarity), with the
displacement of any organ vertex capped at `cap_mm`; the caller decides whether the residual demands it and records it.
Deterministic (fixed sampling seeds)."""
from __future__ import annotations

import re

import numpy as np
import trimesh
from scipy.spatial import cKDTree

SEED = 7
SAMPLE_PER_MM2 = 0.25          # surface samples per mm^2 (about one per 2 mm)
TRIM = 0.10
ITERS = 40
FEMUR_TOP_MM = 100.0


def sample(v, f, per=SAMPLE_PER_MM2, seed=SEED):
    t = trimesh.Trimesh(v, f, process=False)
    n = int(np.clip(t.area * per, 300, 20000))
    p, _ = trimesh.sample.sample_surface_even(t, n, seed=seed) if hasattr(trimesh.sample, "sample_surface_even") else trimesh.sample.sample_surface(t, n, seed=seed)
    if len(p) < 50:
        p, _ = trimesh.sample.sample_surface(t, n, seed=seed)
    return np.asarray(p, float)


def femur_top(v, f):
    top = v[:, 1].max()
    keep = np.all(v[f][:, :, 1] > top - FEMUR_TOP_MM, axis=1)
    return v, f[keep]


def components(v, f):
    t = trimesh.Trimesh(v, f, process=False)
    out = []
    for c in t.split(only_watertight=False):
        out.append((np.asarray(c.vertices), np.asarray(c.faces)))
    return out


# ------------------------------------------------------------------ the bones of each body, by canonical name
def largest(v, f):
    c = components(v, f)
    return max(c, key=lambda x: len(x[1])) if len(c) > 1 else (v, f)


def src_bones(O, region, ribs_all=None):
    """O = srcpage_q362.read_own(...)[0] (all structures).  Returns {name: (v, f)}; every non-rib bone is its largest connected component
    (the source segmentations carry stray pieces: a 49-vertex speck 190 mm lateral in her sacrum mesh, a fragment below his L1)."""
    out = _src_bones(O, region)
    return {k: (largest(*vf) if not k.startswith("rib") else vf) for k, vf in out.items()}


def _src_bones(O, region):
    out = {}
    if region in ("pelvis", "abdomen"):
        out["hip_l"] = (O["hip_bone_l"]["v"], O["hip_bone_l"]["f"]); out["hip_r"] = (O["hip_bone_r"]["v"], O["hip_bone_r"]["f"])
        out["sacrum"] = (O["sacrum"]["v"], O["sacrum"]["f"])
    if region == "pelvis":
        if "coccyx" in O:                                        # (the VH female page has no coccyx mesh)
            out["coccyx"] = (O["coccyx"]["v"], O["coccyx"]["f"])
        for s in "lr":
            out[f"femur_{s}"] = femur_top(O[f"femur_{s}"]["v"], O[f"femur_{s}"]["f"])
    if region in ("kidney", "abdomen"):
        lv = sorted([k for k in O if O[k]["id"] == "lumbar_vertebrae" and not k.endswith("#0") or k == "lumbar_vertebrae#0"],
                    key=lambda k: -O[k]["v"][:, 1].mean())
        lv = sorted({id(O[k]["v"]): k for k in lv}.values(), key=lambda k: -O[k]["v"][:, 1].mean())
        tv = sorted({id(O[k]["v"]): k for k in O if O[k]["id"] == "thoracic_vertebrae"}.values(), key=lambda k: -O[k]["v"][:, 1].mean())
        assert len(lv) >= 5 and len(tv) == 12, (len(lv), len(tv))
        lv = lv[:5]          # counted from T12 down (the VH female page carries a sixth, lowest lumbar-labelled segment: not used)
        lev = {f"T{i + 1}": tv[i] for i in range(12)}; lev.update({f"L{i + 1}": lv[i] for i in range(5)})
        want = ["T11", "T12", "L1", "L2", "L3", "L4"] if region == "kidney" else ["L1", "L2", "L3", "L4", "L5"]
        for w in want:
            out[w] = (O[lev[w]]["v"], O[lev[w]]["f"])
        rib_levels = (11, 12) if region == "kidney" else (10, 11, 12)
        for s in "lr":
            R = ribs_by_level(O[f"ribs_{s}"]["v"], O[f"ribs_{s}"]["f"], {k: O[lev[f"T{k}"]] for k in range(1, 13)})
            assert all(k in R for k in rib_levels), f"ribs_{s}: levels found {sorted(R)}"
            for k in rib_levels:
                out[f"rib{k}_{s}"] = R[k]
    return out


def ribs_by_level(v, f, tvert):
    """split a one-mesh rib cage side into its ribs.  A HEAD piece is a component whose most medial point lies within 50 mm of the spine
    axis; its level is the thoracic vertebra (T1-T12, counted from the top) whose centroid height is nearest that point (ribs 1-12
    articulate with T1-T12 by their heads).  A rib broken into pieces in the source segmentation (her ribs 11 / 12) keeps the pieces
    that chain to its head piece within 12 mm.  Pieces that reach no head (costal cartilage bits) are dropped."""
    comps = [c for c in components(v, f) if len(c[0]) > 4]
    ys = {k: tvert[k]["v"][:, 1].mean() for k in tvert}
    xm = float(np.mean([tvert[k]["v"][:, 0].mean() for k in tvert]))
    heads, rest = {}, []
    for cv, cf in comps:
        i = int(np.argmin(np.abs(cv[:, 0] - xm)))
        k = min(ys, key=lambda kk: abs(ys[kk] - cv[i, 1]))
        if abs(cv[i, 0] - xm) < 50 and abs(ys[k] - cv[i, 1]) < 25 and len(cv) > 60 and (k not in heads or len(cv) > len(heads[k][0][0])):
            if k in heads:
                rest += heads[k]
            heads[k] = [(cv, cf)]
        else:
            rest.append((cv, cf))
    changed = True
    while changed and rest:
        changed = False
        for ci in range(len(rest) - 1, -1, -1):
            c = rest[ci]
            t = cKDTree(c[0]); best = (12.0, None)
            for k, parts in heads.items():
                d = min(float(t.query(p[0])[0].min()) for p in parts)
                if d < best[0]:
                    best = (d, k)
            if best[1] is not None:
                heads[best[1]].append(c); del rest[ci]; changed = True
    out = {}
    for k, parts in heads.items():
        vs, fs, o = [], [], 0
        for pv, pf in parts:
            vs.append(pv); fs.append(pf + o); o += len(pv)
        out[k] = (np.vstack(vs), np.vstack(fs))
    return out


DST = {"hip_l": "hip_bone_l", "hip_r": "hip_bone_r", "sacrum": "sacrum", "coccyx": "coccyx", "femur_l": "femur_l", "femur_r": "femur_r"}
RIBN = {10: "tenth", 11: "eleventh", 12: "twelfth"}


def dst_bones(E, names):
    out = {}
    for n in names:
        if n in DST:
            e = E[DST[n]]; v, f = e["v"], e["f"]
            if n.startswith("femur"):
                v, f = femur_top(v, f)
            out[n] = (v, f)
        elif re.match(r"[TL]\d+$", n):
            e = E[f"zan_vertebra_{n.lower()}"]; out[n] = (e["v"], e["f"])
        elif n.startswith("rib"):
            k, s = re.match(r"rib(\d+)_([lr])", n).groups()
            e = E[f"zan_{RIBN[int(k)]}_rib_{s}"]; out[n] = (e["v"], e["f"])
    return out


# ------------------------------------------------------------------ similarity ICP
def umeyama(A, B, w=None, scale=True):
    w = np.ones(len(A)) if w is None else w
    w = w / w.sum()
    ma, mb = (w[:, None] * A).sum(0), (w[:, None] * B).sum(0)
    a, b = A - ma, B - mb
    C = (w[:, None] * b).T @ a
    U, S, Vt = np.linalg.svd(C)
    D = np.eye(3); D[2, 2] = np.sign(np.linalg.det(U @ Vt))
    R = U @ D @ Vt
    va = (w * (a ** 2).sum(1)).sum()
    s = float((S * np.diag(D)).sum() / va) if scale else 1.0
    t = mb - s * R @ ma
    return s, R, t


def apply(T, P):
    s, R, t = T
    return s * (np.asarray(P) @ R.T) + t


class Pairs:
    def __init__(self, src, dst):
        self.names = sorted(set(src) & set(dst))
        self.S = {n: sample(*src[n]) for n in self.names}
        self.D = {n: sample(*dst[n]) for n in self.names}
        self.Dt = {n: cKDTree(self.D[n]) for n in self.names}

    def fit(self, scale=True, iters=ITERS, T0=None):
        allS = np.vstack([self.S[n] for n in self.names]); allD = np.vstack([self.D[n] for n in self.names])
        T = T0 or (1.0, np.eye(3), allD.mean(0) - allS.mean(0))
        for _ in range(iters):
            A, B, W = [], [], []
            for n in self.names:
                P = apply(T, self.S[n])
                d, i = self.Dt[n].query(P)
                k = d <= np.quantile(d, 1 - TRIM)
                A.append(self.S[n][k]); B.append(self.D[n][i[k]]); W.append(np.full(k.sum(), 0.5 / k.sum()))
                if n.startswith("rib"):              # ribs: source -> target only (a source rib may lack a broken-off piece)
                    W[-1] = W[-1] * 2
                    continue
                St = cKDTree(P)
                d2, j = St.query(self.D[n])
                k2 = d2 <= np.quantile(d2, 1 - TRIM)
                A.append(self.S[n][j[k2]]); B.append(self.D[n][k2]); W.append(np.full(k2.sum(), 0.5 / k2.sum()))
            T = umeyama(np.vstack(A), np.vstack(B), np.concatenate(W), scale=scale)
        return T

    def residual(self, fn):
        """per bone: distance of each transformed source sample to the target bone surface samples (median / p90 mm), and back."""
        out = {}
        for n in self.names:
            P = fn(self.S[n])
            d1, _ = self.Dt[n].query(P)
            d2, _ = cKDTree(P).query(self.D[n])
            d = d1 if n.startswith("rib") else np.concatenate([d1, d2])
            out[n] = dict(median=round(float(np.median(d)), 2), p90=round(float(np.quantile(d, 0.9)), 2))
        allv = np.concatenate([self.Dt[n].query(fn(self.S[n]))[0] if n.startswith("rib") else
                               np.concatenate([self.Dt[n].query(fn(self.S[n]))[0], cKDTree(fn(self.S[n])).query(self.D[n])[0]])
                               for n in self.names])
        out["_all"] = dict(median=round(float(np.median(allv)), 2), p90=round(float(np.quantile(allv, 0.9)), 2))
        return out

    def controls(self, T, n_ctrl=60):
        """bone control points for a warp: farthest-point samples on each source bone (after T) -> closest target bone sample."""
        P, Q = [], []
        per = max(4, n_ctrl // max(1, len(self.names)))
        for n in self.names:
            S = apply(T, self.S[n])
            idx = fps(S, per)
            d, i = self.Dt[n].query(S[idx])
            P.append(S[idx]); Q.append(self.D[n][i])
        return np.vstack(P), np.vstack(Q)


def fps(P, k, seed=0):
    k = min(k, len(P))
    idx = [int(np.argmin(np.linalg.norm(P - P.mean(0), axis=1)))]
    d = np.linalg.norm(P - P[idx[0]], axis=1)
    for _ in range(k - 1):
        j = int(np.argmax(d)); idx.append(j)
        d = np.minimum(d, np.linalg.norm(P - P[j], axis=1))
    return np.array(idx)


def rotation_deg(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


class Warp:
    """smoothed thin-plate spline (scipy RBFInterpolator, kernel thin_plate_spline, degree-1 polynomial) of the bone control
    displacements; organ displacement capped at cap_mm (vectors longer than the cap are scaled down to it)."""
    def __init__(self, P, Q, smoothing=50.0, cap_mm=6.0):
        from scipy.interpolate import RBFInterpolator
        self.f = RBFInterpolator(P, Q - P, kernel="thin_plate_spline", smoothing=smoothing, degree=1)
        self.cap = cap_mm

    def disp(self, X):
        D = self.f(np.asarray(X, float))
        n = np.linalg.norm(D, axis=1)
        k = n > self.cap
        D[k] *= (self.cap / n[k])[:, None]
        return D

    def __call__(self, X):
        return np.asarray(X, float) + self.disp(X)
