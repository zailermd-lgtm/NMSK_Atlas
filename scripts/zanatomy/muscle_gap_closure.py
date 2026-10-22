"""Q162: close the artificial gaps between neighbouring Z-Anatomy muscles.

Owner (2026-09-28): the limb muscles run in parallel but the model shows gaps between them -- "look
on the contralateral side and other accurate models and medical articles to solve this".

Measured before (Q160): median ~2.8 mm between neighbouring limb-muscle surfaces in the Z-Anatomy
source. Real interfaces are thinner:
  - deep fascia of the limbs: mean ~1 mm (Stecco et al. 2008, J Bodyw Mov Ther 12:225,
    doi:10.1016/j.jbmt.2008.04.041); fascia lata 944 +/- 102 um, epimysium 48 um, the two separated by
    loose connective tissue (Stecco et al. 2009, Surg Radiol Anat 31:35, doi:10.1007/s00276-008-0395-5);
  - thigh deep fascia 557-1112 um on histology, 1.64 +/- 0.85 mm on ultrasound (Pirri et al. 2021,
    J Anat 238:999, doi:10.1111/joa.13360).
So a muscle-to-muscle interface (two epimysia + loose areolar tissue, or an intermuscular septum) is
taken as TARGET_GAP_MM = 1.0 mm: gaps wider than that are closed down to it, never below it.

Rule (per vertex, a ray cast along the outward vertex normal; applied only to muscle-layer meshes):
  1. gap d = distance along the ray to the first surface hit, if that surface is ANOTHER muscle (or a
     tendon) being entered from outside; a hit on a surface being exited means this vertex already lies
     inside that structure (source overlap) -> no move;
  2. wanted shift = (d - target) / 2 toward another muscle (it moves the other half), (d - target)
     toward a tendon (tendons do not move), capped at MAX_SHIFT_MM;
  3. never toward or into bone, nerve, vessel, fascia/septum, ligament, bursa or its own surface: if
     the first hit is one of those, shift <= (its distance) - OBSTACLE_MARGIN_MM -- so neurovascular
     bundles keep the fat-filled space they run in;
  4. the shift field is smoothed over the mesh (no spikes), re-capped by rules 2-3, and the whole
     thing repeated for N_PASSES (neighbours move at the same time).
Nothing is added or removed: vertices only move outward along their normals, and each moved muscle
gets a procedural badge with its own measured shift and volume change.
"""
from __future__ import annotations

import gc

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.spatial import cKDTree

TARGET_GAP_MM = 1.0
MAX_SHIFT_MM = 3.0
SEARCH_MM = 2 * MAX_SHIFT_MM + TARGET_GAP_MM
OBSTACLE_MARGIN_MM = 0.5
N_PASSES = 6
STEP = 0.7            # fraction of this side's half of the excess gap moved per pass (re-measured each pass)
DILATE_ITERS = 1
SMOOTH_ITERS = 4
REVERT_ITERS = 6
TILT_RAYS = False
NO_HIT_ROOM_MM = 0.5
MOVABLE, TENDON, OBSTACLE = 0, 1, 2

CITATIONS = ("deep fascia of the limbs ~1 mm, epimysium 48 um (Stecco et al. 2008, "
             "doi:10.1016/j.jbmt.2008.04.041; doi:10.1007/s00276-008-0395-5; Pirri et al. 2021, "
             "doi:10.1111/joa.13360)")


def vertex_normals(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])  # area-weighted
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(ln < 1e-12, 1.0, ln)


def _avg_matrix(f: np.ndarray, nv: int):
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e = np.concatenate([e, e[:, ::-1]])
    a = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)).tocsr()
    a.data[:] = 1.0
    deg = np.asarray(a.sum(1)).ravel()
    return diags(1.0 / np.where(deg == 0, 1, deg)) @ a


def _ring_max(a, w):
    """max of w over each vertex and its 1-ring (a: CSR adjacency/averaging matrix)."""
    out = w.copy()
    nz = np.diff(a.indptr) > 0
    if a.indices.size:
        out[nz] = np.maximum(out[nz], np.maximum.reduceat(w[a.indices], a.indptr[:-1][nz]))
    return out


def signed_volume(v: np.ndarray, f: np.ndarray) -> float:
    return float(np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum() / 6.0)


class _Scene:
    """Every structure in one triangle soup + a first-hit ray intersector (Embree when installed,
    trimesh's rtree intersector otherwise). Per triangle: owner index and kind."""

    def __init__(self, parts):
        import trimesh
        vs, fs, own, kind, off = [], [], [], [], 0
        for i, (v, f, kd) in enumerate(parts):
            vs.append(v); fs.append(f + off); off += len(v)
            own.append(np.full(len(f), i)); kind.append(np.full(len(f), kd))
        self.tm = trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False)
        self.owner = np.concatenate(own); self.kind = np.concatenate(kind)
        self.fn = self.tm.face_normals
        try:
            from trimesh.ray.ray_pyembree import RayMeshIntersector
        except Exception:  # pragma: no cover - fallback without embreex
            from trimesh.ray.ray_triangle import RayMeshIntersector
        self.rays = RayMeshIntersector(self.tm)

    def first_hit(self, p, n):
        """-> (t, owner, kind, entering) per ray; t = inf when nothing within SEARCH_MM."""
        tri = self.rays.intersects_first(p + 1e-3 * n, n)
        t = np.full(len(p), np.inf); own = np.full(len(p), -1); kd = np.full(len(p), -1)
        ent = np.zeros(len(p), bool)
        h = tri >= 0
        if h.any():
            tv = self.tm.triangles[tri[h]]
            # ray/plane distance of the hit triangle
            nn = self.fn[tri[h]]
            den = np.einsum("ij,ij->i", n[h], nn)
            dist = np.einsum("ij,ij->i", tv[:, 0] - p[h], nn) / np.where(np.abs(den) < 1e-12, 1e-12, den)
            t[h] = np.abs(dist); own[h] = self.owner[tri[h]]; kd[h] = self.kind[tri[h]]
            ent[h] = den < 0
        far = t > SEARCH_MM
        t[far] = np.inf; own[far] = -1; kd[far] = -1; ent[far] = False
        return t, own, kd, ent


def _probe(scene, i, p, n):
    """want / room for one movable mesh (index i in the scene)."""
    t, own, kd, ent = scene.first_hit(p, n)
    hit = np.isfinite(t)
    # nothing ahead within SEARCH_MM: only the smoothed taper of a neighbouring contact patch may
    # spill here, and only a little (these rims converge on neighbours at an angle)
    want = np.zeros(len(p)); room = np.where(hit, MAX_SHIFT_MM, NO_HIT_ROOM_MM)
    other_m = hit & (kd == MOVABLE) & (own != i)
    ten = hit & (kd == TENDON)
    inside = hit & ~ent & (own != i)                     # exiting another structure: already inside it
    want[other_m & ent] = STEP * (t[other_m & ent] - TARGET_GAP_MM) / 2
    want[ten & ent] = STEP * (t[ten & ent] - TARGET_GAP_MM)
    room[other_m] = np.maximum(0, (t[other_m] - TARGET_GAP_MM) / 2)
    room[ten] = np.maximum(0, t[ten] - TARGET_GAP_MM)
    ob = hit & (kd == OBSTACLE)                          # never toward bone/NV/fascia/ligament
    room[ob] = np.maximum(0, np.minimum(room[ob], t[ob] - OBSTACLE_MARGIN_MM))
    own_s = hit & (own == i)                             # nor into its own folded surface (moves too)
    room[own_s] = np.maximum(0, np.minimum(room[own_s], (t[own_s] - OBSTACLE_MARGIN_MM) / 2))
    room[inside] = 0.0
    # oblique neighbours: 4 rays tilted 45 deg around the normal only limit the room
    for d in (_tilted(n) if TILT_RAYS else []):
        t2, own2, kd2, _e2 = scene.first_hit(p, d)
        c = np.einsum("ij,ij->i", d, n)
        h2 = np.isfinite(t2)
        lim = np.full(len(p), np.inf)
        m = h2 & (kd2 == MOVABLE)
        lim[m] = np.maximum(0, (t2[m] * c[m] - TARGET_GAP_MM) / 2)
        m = h2 & (kd2 == TENDON)
        lim[m] = np.maximum(0, t2[m] * c[m] - TARGET_GAP_MM)
        m = h2 & (kd2 == OBSTACLE)
        lim[m] = np.maximum(0, t2[m] * c[m] - OBSTACLE_MARGIN_MM)
        room = np.minimum(room, lim)
    want = np.clip(np.minimum(want, room), 0, None)
    return want, room, dict(t=t, own=own, kd=kd, ent=ent)


def _tilted(n):
    """4 unit directions at 45 degrees from each normal."""
    a = np.where(np.abs(n[:, :1]) < 0.9, np.array([[1.0, 0, 0]]), np.array([[0, 1.0, 0]]))
    u = np.cross(n, a); u /= np.maximum(np.linalg.norm(u, axis=1, keepdims=True), 1e-12)
    w = np.cross(n, u)
    r = np.sqrt(0.5)
    return [r * n + r * u, r * n - r * u, r * n + r * w, r * n - r * w]


def close_gaps(movable: dict, fixed_neighbours: dict, obstacles: dict, log=None):
    """movable: {id: (v, f)} muscles (welded, outward-oriented); fixed_neighbours: {id: (v, f)} tendons
    (closed onto, never moved); obstacles: {id: (v, f)} bone/nerve/vessel/fascia/ligament/bursa.
    Returns {id: (v_new, stats)} for every movable id."""
    ids = list(movable)
    V = {k: np.asarray(movable[k][0], np.float64).copy() for k in ids}
    F = {k: np.asarray(movable[k][1], np.int64) for k in ids}
    avg = {k: _avg_matrix(F[k], len(V[k])) for k in ids}
    total = {k: np.zeros(len(V[k])) for k in ids}
    fixed = [(np.asarray(v, np.float64), np.asarray(f, np.int64), TENDON) for v, f in fixed_neighbours.values()]
    fixed += [(np.asarray(v, np.float64), np.asarray(f, np.int64), OBSTACLE) for v, f in obstacles.values()]

    for it in range(N_PASSES):
        scene = _Scene([(V[k], F[k], MOVABLE) for k in ids] + fixed)
        shift = {}
        for i, k in enumerate(ids):
            n = vertex_normals(V[k], F[k])
            want, room, _ = _probe(scene, i, V[k], n)
            w = want
            for _ in range(DILATE_ITERS):  # fill single-vertex holes before smoothing
                w = _ring_max(avg[k], w)
            for _ in range(SMOOTH_ITERS):
                w = 0.5 * w + 0.5 * (avg[k] @ w)
            # smoothing may spread a little shift into neighbouring free surface, never beyond the room
            shift[k] = (np.clip(np.minimum(w, room), 0, MAX_SHIFT_MM - total[k]), n)
        del scene
        gc.collect()
        for k in ids:
            s, n = shift[k]
            V[k] = V[k] + s[:, None] * n
            total[k] += s
        if log:
            allw = np.concatenate([shift[k][0] for k in ids])
            mv = allw > 0.05
            log(f"gap closure pass {it + 1}: moved {mv.mean():.1%} of muscle vertices, "
                f"mean {allw[mv].mean() if mv.any() else 0:.2f} mm")

    # safety: wherever a vertex ended up inside another muscle it was not inside before, halve the
    # shift of both surfaces there (the vertex's 1-ring and the neighbour's vertices within 4 mm),
    # repeating until no new overlap remains (the last round reverts fully)
    V0 = {k: np.asarray(movable[k][0], np.float64) for k in ids}
    before = _inside_flags(ids, V0, F, fixed)[0]
    for it in range(REVERT_ITERS):
        flags, hit_owner = _inside_flags(ids, V, F, fixed)
        factor = 0.0 if it == REVERT_ITERS - 1 else 0.5
        marks = {k: np.zeros(len(V[k]), bool) for k in ids}
        n_new = 0
        for i, k in enumerate(ids):
            bad = flags[k] & ~before[k]
            if not bad.any():
                continue
            n_new += int(bad.sum())
            marks[k] |= _ring_max(avg[k], bad.astype(float)) > 0
            for o in np.unique(hit_owner[k][bad]):
                ko = ids[o]
                pts = V[k][bad & (hit_owner[k] == o)]
                d, _ = cKDTree(pts).query(V[ko], distance_upper_bound=4.0)
                marks[ko] |= np.isfinite(d)
        if log:
            log(f"overlap guard {it + 1}: {n_new} vertices newly inside a neighbour")
        if not n_new:
            break
        for k in ids:
            if not marks[k].any():
                continue
            keep = np.where(marks[k], factor, 1.0)
            for _ in range(2):
                keep = np.minimum(keep, 0.5 * keep + 0.5 * (avg[k] @ keep))
            total[k] *= keep
            V[k] = V0[k] + (V[k] - V0[k]) * keep[:, None]

    out = {}
    for k in ids:
        v0, f = np.asarray(movable[k][0], np.float64), F[k]
        t = total[k]
        vol0, vol1 = abs(signed_volume(v0, f)), abs(signed_volume(V[k], f))
        moved = t > 0.05
        out[k] = (V[k], {
            "moved_frac": round(float(moved.mean()), 3),
            "shift_median_mm": round(float(np.median(t[moved])), 2) if moved.any() else 0.0,
            "shift_max_mm": round(float(t.max()), 2),
            "volume_cm3_before": round(vol0 / 1000, 2),
            "volume_cm3_after": round(vol1 / 1000, 2),
        })
    return out


def _inside_flags(ids, V, F, fixed):
    scene = _Scene([(V[k], F[k], MOVABLE) for k in ids] + fixed)
    res, owners = {}, {}
    for i, k in enumerate(ids):
        t, own, kd, ent = scene.first_hit(V[k], vertex_normals(V[k], F[k]))
        res[k] = np.isfinite(t) & (kd == MOVABLE) & (own != i) & ~ent
        owners[k] = own
    del scene
    gc.collect()
    return res, owners


def audit(movable: dict, fixed_neighbours: dict | None = None, obstacles: dict | None = None):
    """Ray audit from every muscle vertex along its normal: gap to the next muscle entered (within
    SEARCH_MM) and whether the vertex lies inside another muscle (first hit is an exit)."""
    ids = list(movable)
    parts = [(np.asarray(v, np.float64), np.asarray(f, np.int64), MOVABLE) for v, f in movable.values()]
    parts += [(np.asarray(v, np.float64), np.asarray(f, np.int64), TENDON) for v, f in (fixed_neighbours or {}).values()]
    parts += [(np.asarray(v, np.float64), np.asarray(f, np.int64), OBSTACLE) for v, f in (obstacles or {}).values()]
    scene = _Scene(parts)
    per = {}
    for i, k in enumerate(ids):
        v, f, _ = parts[i]
        t, own, kd, ent = scene.first_hit(v, vertex_normals(v, f))
        g = np.isfinite(t) & (kd == MOVABLE) & (own != i) & ent
        ins = np.isfinite(t) & (kd == MOVABLE) & (own != i) & ~ent
        per[k] = {"n": int(len(v)), "gaps": t[g], "inside": int(ins.sum())}
    return per
