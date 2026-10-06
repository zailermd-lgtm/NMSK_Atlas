"""Q194: bounded per-vertex separation of overlapping neighbour muscles along the contact normal.

Q190 resolved muscle-muscle overlap with a push-apart that collapsed the muscles (volume lost, folds); the neighbour overlap then rose 8.0 -> 9.7 % of the vertices.
Here each round: for every pair of (closed) neighbour meshes A, B, a vertex of A that lies > 0.3 mm inside B is moved along B's outward surface normal by HALF its
depth (+ 0.4 mm margin, the other half is B's own move), capped at MAX_MOVE_MM; every mesh's displacement is smoothed over its own surface (so no spikes) and the
result per mesh is accepted only if (i) volume stays in 0.65-1.5 x the Z source, (ii) the share of folded edges does not grow, (iii) it stays out of the displayed
bones and inside her skin where the caller says so (`keep`), else that mesh keeps its previous round.  Nothing moves that does not overlap.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_refine as Q

MAX_MOVE_MM = 4.0
MARGIN_MM = 0.3
MIN_DEPTH_MM = 0.1
STATS = {'tried': 0, 'vol_rej': 0, 'fold_rej': 0}
FOLD_TOL = 0.003
MAX_TOTAL_MM = 6.0         # cumulative bound over all rounds


class Skel:
    """closed mesh: query(P) -> (depth, normal): depth > 0 inside (distance to the surface), < 0 outside; normal = outward face normal of the nearest triangle.
    Inside = ray parity (embree through trimesh: fast).  The first full build died with a SEGFAULT inside pyembree on a mesh state reached after several separation rounds, so every
    parallel round is run in forked workers and, if one dies, repeated with SAFE = True (trimesh's pure-numpy ray tester: ~20x slower, cannot crash)."""
    SAFE = False

    def __init__(self, v, f, spacing=0.8):
        import trimesh
        self.m = trimesh.Trimesh(v, f, process=False)
        if self.m.volume < 0:
            self.m.invert()
        self.lo, self.hi = v.min(0), v.max(0)
        self._ray = None

    def contains(self, P):
        if not Skel.SAFE:
            return self.m.contains(P)
        if self._ray is None:
            from trimesh.ray.ray_triangle import RayMeshIntersector
            self._ray = RayMeshIntersector(self.m)
        return self._ray.contains_points(P)

    def query(self, P):
        from trimesh.proximity import closest_point
        depth = np.full(len(P), -1e9)
        nrm = np.zeros((len(P), 3))
        sel = np.flatnonzero(np.all(np.isfinite(P), axis=1) & np.all((P >= self.lo - 1.0) & (P <= self.hi + 1.0), axis=1))
        if not len(sel):
            return depth, nrm
        c = self.contains(P[sel])
        depth[sel] = -1.0
        ins = sel[c]
        if len(ins):
            cp, d, tri = closest_point(self.m, P[ins])
            depth[ins] = np.maximum(d, 1e-3)
            nrm[ins] = self.m.face_normals[tri]
        return depth, nrm

    def depth(self, P):
        return self.query(P)[0]


_SK = {}
_MESHES = {}


def _run(jobs, fn, workers, log):
    """map fn over jobs in forked workers (the module globals _SK / _MESHES are inherited); a worker that dies (segfault) -> the whole map is repeated with the safe ray tester"""
    import concurrent.futures as cf
    import multiprocessing as mp
    if workers > 1 and len(jobs) > 8:
        try:
            with cf.ProcessPoolExecutor(workers, mp_context=mp.get_context("fork")) as ex:
                return list(ex.map(fn, jobs, chunksize=4))
        except Exception as e:               # BrokenProcessPool: a worker crashed
            log(f"    worker died ({type(e).__name__}); repeating with the safe ray tester")
            Skel.SAFE = True
    return [fn(j) for j in jobs] if Skel.SAFE else list(map(fn, jobs))


def _contact(args):
    """worker: raw contact push of mesh i against every other mesh (module globals _SK / _MESHES are inherited through fork)"""
    i, cur_v, share, max_move = args
    f = _MESHES[i][1]
    D = np.zeros_like(cur_v)
    hit = np.zeros(len(cur_v), bool)
    for j, s in _SK.items():
        if j == i:
            continue
        d, nall = s.query(cur_v)
        m = d > MIN_DEPTH_MM
        if m.any():
            n = nall[m]
            step = np.minimum(share * (d[m] + MARGIN_MM), max_move)
            cand = n * step[:, None]
            idx = np.flatnonzero(m)
            bigger = np.linalg.norm(cand, axis=1) > np.linalg.norm(D[idx], axis=1)
            D[idx[bigger]] = cand[bigger]
            hit[idx] = True
    return i, D, hit


def _overlap_one(args):
    i, P = args
    inside = np.zeros(len(P), bool)
    for j, s in _SK.items():
        if j != i:
            inside |= s.depth(P) > MIN_DEPTH_MM
    return i, 100.0 * float(inside.mean())


def overlap_pct(meshes: dict, ids=None, nmax=3000, seed=0, workers=4):
    """{id: % of its vertices (sampled) lying > MIN_DEPTH_MM inside another mesh of the set}"""
    rng = np.random.default_rng(seed)
    _SK.clear()
    _SK.update({i: Skel(v, f) for i, (v, f) in meshes.items()})
    jobs = [(i, v[rng.choice(len(v), min(len(v), nmax), replace=False)]) for i, (v, f) in meshes.items() if ids is None or i in ids]
    return dict(_run(jobs, _overlap_one, workers, print))


def _volume(v, f):
    return abs(Q.volume(v, f))


def new_folds(v0, v1, f):
    """share of interior edges that were smooth in v0 (dihedral < 60 deg) and are folded over in v1 (> 100 deg): needs no source correspondence, so it works on decimated meshes"""
    def fn(x):
        n = np.cross(x[f[:, 1]] - x[f[:, 0]], x[f[:, 2]] - x[f[:, 0]])
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    n0, n1 = fn(v0), fn(v1)
    e = np.vstack([np.c_[f[:, 0], f[:, 1], np.arange(len(f))], np.c_[f[:, 1], f[:, 2], np.arange(len(f))], np.c_[f[:, 2], f[:, 0], np.arange(len(f))]])
    key = np.sort(e[:, :2], 1)
    o = np.lexsort((key[:, 1], key[:, 0]))
    k, fi = key[o], e[o, 2]
    same = (k[1:] == k[:-1]).all(1)
    a, b = fi[:-1][same], fi[1:][same]
    if not len(a):
        return 0.0
    sel = (n0[a] * n0[b]).sum(1) > 0.5
    return float(((n1[a] * n1[b]).sum(1) < -0.17)[sel].mean()) if sel.any() else 0.0


def separate(meshes: dict, vol_ref: dict, movable: set, rounds=6, max_move=MAX_MOVE_MM, smooth=6, share=0.7, keep=None, log=print, workers=4):
    """meshes: {id: (v, f)} closed neighbour muscles (the shipped, decimated meshes); vol_ref: {id: source volume x scale^3 or None}; movable: ids that may move.
    keep(id, v_new) -> bool: extra acceptance test (containment).  The contact search of one round runs in `workers` forked processes.  Returns ({id: v_new}, report)"""
    import multiprocessing as mp
    cur = {i: v.copy() for i, (v, f) in meshes.items()}
    rep = {}
    _MESHES.clear()
    _MESHES.update(meshes)
    for rd in range(rounds):
        _SK.clear()
        _SK.update({i: Skel(cur[i], meshes[i][1]) for i in meshes})
        order = sorted(movable)
        res = _run([(i, cur[i], share, max_move) for i in order], _contact, workers, log)
        new = {}
        for i, D, hit in res:
            v, f = cur[i], meshes[i][1]
            if not hit.any():
                continue
            D = np.nan_to_num(Q._smooth_push(f, np.nan_to_num(D), smooth))
            D *= np.minimum(1.0, max_move / np.maximum(np.linalg.norm(D, axis=1), 1e-9))[:, None]
            ref = vol_ref.get(i)
            for alpha in (1.0, 0.6, 0.35):                      # back-tracking: a smaller step is kept when the full one would fold / shrink / leave her skin
                v2 = cur[i] + alpha * D
                if not np.isfinite(v2).all():
                    continue
                tot = v2 - meshes[i][0]
                v2 = meshes[i][0] + tot * np.minimum(1.0, MAX_TOTAL_MM / np.maximum(np.linalg.norm(tot, axis=1), 1e-9))[:, None]
                ok = True
                STATS['tried'] += 1
                if ref:
                    r0, r1 = _volume(v, f) / ref, _volume(v2, f) / ref
                    ok = (0.65 <= r1 <= 1.5) or abs(r1 - 1.0) <= abs(r0 - 1.0)
                STATS['vol_rej'] += int(not ok)
                nf = new_folds(v, v2, f)
                STATS['fold_rej'] += int(nf > FOLD_TOL)
                ok = ok and nf <= FOLD_TOL and (keep is None or keep(i, v2))
                if ok:
                    new[i] = v2
                    break
        for i, v2 in new.items():
            cur[i] = v2
        log(f"    separation round {rd}: {len(new)} of {len(movable)} meshes moved")
    for i in movable:
        d = np.linalg.norm(cur[i] - meshes[i][0], axis=1)
        if d.max() > 1e-6:
            rep[i] = {"max_move_mm": round(float(d.max()), 2), "mean_move_mm": round(float(d.mean()), 2)}
    return cur, rep
