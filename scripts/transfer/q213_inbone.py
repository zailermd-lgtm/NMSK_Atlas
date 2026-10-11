"""Q213: push a soft structure out of the OWN bones it sits in (bone meshes = the evidence), bounded and guarded.

Used for the target (motor-point) muscles of the own female page.  Method (per structure):
  1. vertices inside a displayed bone (ray parity, embree) -> the closest point on that bone's surface; the vertex moves there plus MARGIN mm
     along the in-to-out direction (independent of the bone's face winding); a move > CAP_MM is not made (that part stays);
  2. the displacement of the free neighbours follows by diffusion over the mesh edges (decay per ring), so a patch moves coherently;
  3. up to 3 passes (a pushed vertex may land in the next bone);
  4. guards -- the structure is kept ONLY IF: share of vertices still inside a bone <= GATE_PCT and it fell; volume ratio within VOL_LO..VOL_HI; flipped faces
     <= 0.5 %; stretched triangles (area ratio outside 0.5-2) not up by more than 12 points.  Otherwise the published mesh is kept (reported).
"""
from __future__ import annotations

import numpy as np
import trimesh
from scipy.sparse import coo_matrix

MARGIN = 2.0      # mm outside the bone surface after the push: the Q204 audit counts a vertex as inside bone when its 2 mm voxel is solid (depth >= 2 mm > 1.5 mm), i.e. up to ~1.7 mm outside the true surface; 2.0 mm clears both measures
CAP_MM = 16.0
GATE_PCT = 5.0
SMOOTH_IT = 6
VOL_LO, VOL_HI = 0.88, 1.20


class BoneField:
    def __init__(self, bones):
        """bones: {id: (v, f)}"""
        self.tm = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in bones.items() if len(f) > 20}
        self.box = {k: (m.bounds[0] - 1.0, m.bounds[1] + 1.0) for k, m in self.tm.items()}

    def inside(self, V):
        """(bool mask, closest surface point, owning bone key) for each vertex"""
        ins = np.zeros(len(V), bool)
        cp = np.zeros_like(V)
        dist = np.full(len(V), np.inf)
        for k, m in self.tm.items():
            lo, hi = self.box[k]
            sel = np.flatnonzero(np.all((V >= lo) & (V <= hi), axis=1))
            if not len(sel):
                continue
            c = m.contains(V[sel])
            idx = sel[c]
            if not len(idx):
                continue
            p, d, _ = trimesh.proximity.closest_point(m, V[idx])
            better = d < dist[idx]
            idx2 = idx[better]
            cp[idx2] = p[better]
            dist[idx2] = d[better]
            ins[idx] = True
        return ins, cp, dist


def adjacency(n, f):
    a = np.concatenate([f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]])
    b = np.concatenate([f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])
    A = coo_matrix((np.ones(len(a)), (a, b)), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    return A


def volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def tri_area(v, f):
    return 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)


def stretched_pct(v0, v1, f):
    a0, a1 = tri_area(v0, f), tri_area(v1, f)
    ok = a0 > 1e-9
    r = a1[ok] / a0[ok]
    return float(100.0 * ((r < 0.5) | (r > 2.0)).mean())


def flipped_pct(v0, v1, f):
    def nrm(v):
        return np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n0, n1 = nrm(v0), nrm(v1)
    ok = (np.linalg.norm(n0, axis=1) > 1e-9) & (np.linalg.norm(n1, axis=1) > 1e-9)
    return float(100.0 * ((n0[ok] * n1[ok]).sum(1) < 0).mean())


def laplacian(n, f):
    A = adjacency(n, f)
    deg = np.asarray(A.sum(1)).ravel()
    from scipy.sparse import diags
    return diags(deg) - A


def ends_mask(v, frac=0.12):
    """vertices in the two end zones (extreme `frac` along the principal axis): a muscle's origin / insertion sits ON its bone, so these are neither pushed out nor allowed to leave the bone"""
    c = v.mean(0)
    u = np.linalg.svd(v - c, full_matrices=False)[2][0]
    t = (v - c) @ u
    lo, hi = np.percentile(t, [100 * frac, 100 * (1 - frac)])
    return (t <= lo) | (t >= hi)


W_SEAM, W_END = 200.0, 6.0


def push_out(v, f, field, lam=10.0, passes=6, tether=1e-3, start=None, anchors=None, ends=None):
    """-> (new vertices, report).  Per pass: minimise  sum_inside |d - p|^2 + lam * sum_edges |d_i - d_j|^2 + tether |d|^2  (p = vector to the bone
    surface + MARGIN); lam sets how rigidly the whole structure shifts (large = nearly a translation, small = a local push)."""
    from scipy.sparse import diags, identity
    from scipy.sparse.linalg import spsolve
    n = len(v)
    Lap = laplacian(n, f)
    cur = (v if start is None else start).copy()
    in0, _, _ = field.inside(v)
    rep = {"lam": lam, "inside_before_pct": round(100.0 * float(in0.mean()), 1)}
    for _ in range(passes):
        ins, cp, dist = field.inside(cur)
        if not ins.any():
            break
        P = np.zeros_like(cur)
        dirn = cp[ins] - cur[ins]
        Ld = np.linalg.norm(dirn, axis=1, keepdims=True)
        P[ins] = np.where(Ld > 1e-9, dirn / np.maximum(Ld, 1e-9), 0.0) * (Ld + MARGIN)
        w = np.where(ins & (np.linalg.norm(P, axis=1) <= CAP_MM), 1.0, 0.0)
        if ends is not None:
            w = np.where(ends, 0.0, w)
        if not w.any():
            break
        wa = np.zeros(n)
        if anchors is not None:
            wa = np.maximum(wa, W_SEAM * anchors.astype(float))   # seam vertices (shared with a sibling piece) stay put
        if ends is not None:
            wa = np.maximum(wa, W_END * ends.astype(float))        # origin / insertion zones stay on their bone
        Mx = (diags(w + wa) + lam * Lap + tether * identity(n)).tocsc()
        D = np.column_stack([spsolve(Mx, w * P[:, k]) for k in range(3)])
        cur = cur + D
    ins1, _, dist1 = field.inside(cur)
    _, _, dist0 = field.inside(v)
    rep["deep_before_pct"] = round(100.0 * float((np.isfinite(dist0) & (dist0 > 1.5)).mean()), 1)       # vertices > 1.5 mm inside a bone: the Q204 inside-bone measure
    rep["deep_after_pct"] = round(100.0 * float((np.isfinite(dist1) & (dist1 > 1.5)).mean()), 1)
    mv = np.linalg.norm(cur - v, axis=1)
    if ends is not None:
        rep["inside_before_belly_pct"] = round(100.0 * float(in0[~ends].mean()), 1)
        rep["inside_after_belly_pct"] = round(100.0 * float(ins1[~ends].mean()), 1)
    rep.update(inside_after_pct=round(100.0 * float(ins1.mean()), 1), mean_move_mm=round(float(mv.mean()), 2), max_move_mm=round(float(mv.max()), 2),
               volume_ratio=round(volume(cur, f) / max(volume(v, f), 1e-9), 3), flipped_pct=round(flipped_pct(v, cur, f), 2),
               stretched_before=round(stretched_pct(v, v, f), 1), stretched_after=round(stretched_pct(v, cur, f), 1))
    return cur, rep


CHAINS = ((160.0, 40.0, 10.0), (40.0, 10.0, 3.0), (10.0, 3.0, 1.0), (3.0, 1.0, 0.3))


def chain(v, f, field, lams, anchors=None, ends=None):
    cur = None
    for lam in lams:
        cur, rep = push_out(v, f, field, lam=lam, start=cur, anchors=anchors, ends=ends)
    rep["lam"] = list(lams)
    return cur, rep


def repair(v, f, field, chains=CHAINS, anchors=None, end_tree=None, use_ends=True, overlap=None):
    """every chain (stiffest = most rigid shift first, then more local) is tried; of the results that pass accept() the one with the smallest in-bone share of the belly is returned
    (ties: smaller mean move); if none passes, the best-gain result is returned with its reasons.  -> (vertices or None, report)"""
    best, ok_best = None, None
    ends = ends_mask(v) if use_ends else None
    o0 = overlap(v) if overlap is not None else None
    key = lambda r: r.get("inside_after_belly_pct", r["inside_after_pct"])
    for lams in chains:
        nv, rep = chain(v, f, field, lams, anchors, ends)
        ok, why = accept(rep)
        if ok and end_tree is not None:
            d0, d1 = end_dist(v, end_tree), end_dist(nv, end_tree)
            rep["end_dist_mm"] = [[round(x, 1) for x in d0], [round(x, 1) for x in d1]]
            if any(b > max(a + 1.5, 4.5) for a, b in zip(d0, d1)):
                ok = False
                why = why + ["an attachment end moved off its bone"]
        if overlap is not None:
            o1 = overlap(nv)
            rep["overlap_before_pct"], rep["overlap_after_pct"] = round(o0, 1), round(o1, 1)
            if o1 > o0 + OVERLAP_RISE_MAX:
                ok = False
                why = why + [f"muscle overlap {o0:.1f} -> {o1:.1f} %"]
        rep["accepted"], rep["why_not"] = ok, why
        if ok and (ok_best is None or (key(rep), rep["mean_move_mm"]) < (key(ok_best[1]), ok_best[1]["mean_move_mm"])):
            ok_best = (nv, rep)
        if best is None or key(rep) < key(best[1]):
            best = (nv, rep)
    if ok_best is not None:
        return ok_best
    return None, best[1]


def end_dist(v, tree, frac=0.1):
    """distance of the two ends (extreme 10 % along the principal axis) of a muscle mesh to the nearest bone vertex (KD-tree of all displayed bones)"""
    c = v.mean(0)
    u = np.linalg.svd(v - c, full_matrices=False)[2][0]
    t = (v - c) @ u
    lo, hi = np.percentile(t, [100 * frac, 100 * (1 - frac)])
    return [float(np.median(tree.query(v[t <= lo])[0])), float(np.median(tree.query(v[t >= hi])[0]))]


MEAN_MOVE_MAX, MAX_MOVE_MAX = 4.0, 16.0
OVERLAP_RISE_MAX = 6.0     # points: the share of vertices inside OTHER muscles may not rise by more than this (Q211 muscle-overlap guard)


class MuscleOverlap:
    """share (%) of the vertices of a mesh that lie inside other muscle meshes (ray parity); `others` = {id: (v, f)}, `skip` = ids that do not count (the muscle's own pieces)"""

    def __init__(self, others):
        self.tm = {k: trimesh.Trimesh(v, f, process=False) for k, (v, f) in others.items() if len(f) > 20}
        self.box = {k: (m.bounds[0] - 1.0, m.bounds[1] + 1.0) for k, m in self.tm.items()}

    def pct(self, V, skip=()):
        inm = np.zeros(len(V), bool)
        for k, m in self.tm.items():
            if k in skip:
                continue
            lo, hi = self.box[k]
            sel = np.flatnonzero(np.all((V >= lo) & (V <= hi), axis=1) & ~inm)
            if len(sel):
                inm[sel] = m.contains(V[sel])
        return 100.0 * float(inm.mean())


def accept(rep):
    why = []
    if rep["mean_move_mm"] > MEAN_MOVE_MAX or rep["max_move_mm"] > MAX_MOVE_MAX:
        why.append(f"move mean {rep['mean_move_mm']} / max {rep['max_move_mm']} mm")
    a = rep.get("inside_after_belly_pct", rep["inside_after_pct"])
    b = rep.get("inside_before_belly_pct", rep["inside_before_pct"])
    if not (a <= GATE_PCT or a <= 0.4 * b):
        why.append(f"still {a} % of the belly inside bone")
    if a >= b:
        why.append("no gain")
    if not (VOL_LO <= rep["volume_ratio"] <= VOL_HI):
        why.append(f"volume x{rep['volume_ratio']}")
    if rep["flipped_pct"] > 0.5:
        why.append(f"{rep['flipped_pct']} % faces flipped")
    if rep["stretched_after"] > rep["stretched_before"] + 12.0:
        why.append(f"stretched {rep['stretched_before']} -> {rep['stretched_after']} %")
    return (not why), why
