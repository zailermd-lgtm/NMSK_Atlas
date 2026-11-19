"""Q217: put the carried Z-base muscle (the forearm part, A) and the page's own distal part (tendon into the hand, B) together as ONE structure.

A = the base mesh carried by the twisted-tube map (q217_twist.TwistMap), clipped to y >= y_m - OVER.  B = the page's mesh (his hand-side fit, untouched there), clipped to y <= y_m + OVER, warped so that its cross-section loops
at the plane y = y_m land on A's loops there (per-loop translation, inverse-distance blended, decaying to 0 over DECAY mm below the seam).  The two pieces overlap coaxially by 2 OVER mm: no gap, no flat cap."""
from __future__ import annotations

import numpy as np
import trimesh
from scipy.optimize import linear_sum_assignment
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

OVER = 4.0
DECAY = 45.0


def loops_at(v, f, y):
    """centroids (and vertex-free) of the cross-section components of a mesh at plane y -> (k, 3) array, areas-free"""
    tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
    seg = trimesh.intersections.mesh_plane(tm, [0, 1, 0], [0, float(y), 0])
    if seg is None or len(seg) == 0:
        return np.zeros((0, 3))
    P = seg.reshape(-1, 3)
    key = np.round(P / 0.05).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 2)
    n = inv.max() + 1
    A = coo_matrix((np.ones(len(inv)), (inv[:, 0], inv[:, 1])), shape=(n, n))
    nc, lab = connected_components(A, directed=False)
    mid = seg.mean(1)
    out = []
    for c in range(nc):
        m = lab[inv[:, 0]] == c
        if m.sum() >= 3:
            out.append(mid[m].mean(0))
    return np.array(out) if out else np.zeros((0, 3))


def clip(v, f, keep_face):
    f2 = f[keep_face]
    used = np.unique(f2)
    remap = -np.ones(len(v), np.int64)
    remap[used] = np.arange(len(used))
    return v[used], remap[f2], used


def join(a_v, a_f, b_v, b_f, y_m, log=None):
    """-> (v, f, info).  a_* = carried base mesh (whole), b_* = the page mesh (whole)"""
    info = {}
    cA = loops_at(a_v, a_f, y_m)
    cB = loops_at(b_v, b_f, y_m)
    info["loops_A"], info["loops_B"] = len(cA), len(cB)
    # A: keep faces with centroid y >= y_m - OVER
    ca = a_v[a_f].mean(1)[:, 1]
    av, af, _ = clip(a_v, a_f, ca >= y_m - OVER)
    if not len(cB) or not len(cA) or len(af) == 0:
        info["note"] = "no seam (A or B has no section at the seam plane)"
        if len(cA) == 0 and len(cB) == 0:
            return av, af, info
        # base ends above the seam: A is the whole muscle
        return av, af, info
    cb = b_v[b_f].mean(1)[:, 1]
    bv, bf, _ = clip(b_v, b_f, cb <= y_m + OVER)
    if len(bf) == 0:
        return av, af, info
    D = np.linalg.norm(cA[:, None, :] - cB[None, :, :], axis=2)
    ri, ci = linear_sum_assignment(D)
    pair = {int(j): int(i) for i, j in zip(ri, ci)}
    for j in range(len(cB)):
        if j not in pair:
            pair[j] = int(D[:, j].argmin())
    t = np.array([cA[pair[j]] - cB[j] for j in range(len(cB))])
    t[:, 1] = 0.0                                                   # slide within the plane only
    w = 1.0 / (np.linalg.norm(bv[:, None, :] - cB[None, :, :], axis=2) + 3.0) ** 2
    w /= w.sum(1, keepdims=True)
    u = w @ t
    dec = np.clip((bv[:, 1] - (y_m + OVER - DECAY)) / DECAY, 0.0, 1.0)
    dec = 3 * dec ** 2 - 2 * dec ** 3
    bv = bv + u * dec[:, None]
    info.update(seam_shift_mm=[round(float(np.linalg.norm(x)), 1) for x in t], b_faces=int(len(bf)), a_faces=int(len(af)))
    v = np.concatenate([av, bv])
    f = np.concatenate([af, bf + len(av)])
    return v, f, info


def slice_keep(v, f, y, above=True):
    tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
    sl = tm.slice_plane([0, float(y), 0], [0, 1.0 if above else -1.0, 0], cap=False)
    sl.merge_vertices(merge_tex=True, merge_norm=True)
    sl.update_faces(sl.nondegenerate_faces())
    return np.asarray(sl.vertices, float), np.asarray(sl.faces, np.int64)


def rim_loops(v, f, y, tol=2e-3):
    """ordered closed loops of boundary edges that lie in the plane y = const -> list of vertex index arrays"""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    es = np.sort(e, axis=1)
    u, inv, cnt = np.unique(es, axis=0, return_inverse=True, return_counts=True)
    b = u[cnt == 1]
    b = b[(np.abs(v[b[:, 0], 1] - y) < tol) & (np.abs(v[b[:, 1], 1] - y) < tol)]
    adj = {}
    for a, c in b:
        adj.setdefault(int(a), []).append(int(c))
        adj.setdefault(int(c), []).append(int(a))
    seen, loops = set(), []
    for st in adj:
        if st in seen:
            continue
        loop, cur, prev = [st], st, None
        seen.add(st)
        while True:
            nxt = [x for x in adj[cur] if x != prev and x not in seen]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            loop.append(cur)
            seen.add(cur)
        if len(loop) >= 3:
            loops.append(np.array(loop))
    return loops


def _area_sign(v, loop):
    p = v[loop][:, [0, 2]]
    x, z = p[:, 0], p[:, 1]
    return np.sign(np.sum(x * np.roll(z, -1) - np.roll(x, -1) * z))


def zip_loops(v, la, lb):
    """triangles that close the band between two ordered loops (vertex indices into v), shorter diagonal first"""
    if _area_sign(v, la) != _area_sign(v, lb):
        lb = lb[::-1]
    j0 = int(np.argmin(np.linalg.norm(v[lb] - v[la[0]], axis=1)))
    lb = np.roll(lb, -j0)
    na, nb = len(la), len(lb)
    i = j = 0
    tris = []
    while i < na or j < nb:
        a0, a1 = la[i % na], la[(i + 1) % na]
        b0, b1 = lb[j % nb], lb[(j + 1) % nb]
        if i >= na:
            adv_a = False
        elif j >= nb:
            adv_a = True
        else:
            adv_a = np.linalg.norm(v[a1] - v[b0]) <= np.linalg.norm(v[a0] - v[b1])
        if adv_a:
            tris.append([a0, a1, b0])
            i += 1
        else:
            tris.append([a0, b1, b0])
            j += 1
    return np.array(tris, np.int64)


def join_closed(a_v, a_f, b_v, b_f, y_m, decay=DECAY, a_above=True):
    """A (carried base) and B (page) cut at the plane y = y_m (a_above: A keeps y >= y_m, B y <= y_m = the wrist seam; else the reverse = the upper-arm seam), B warped so that its rim loops land on A's (per-loop
    translation within the plane, decaying over `decay` mm away from the seam), the rims zipped = ONE surface.  -> (v, f, info); a muscle that has no section at the plane on both sides is returned as A (whole)"""
    info = {}
    cA = loops_at(a_v, a_f, y_m)
    cB = loops_at(b_v, b_f, y_m)
    info["loops_A"], info["loops_B"] = len(cA), len(cB)
    if len(cA) == 0 or len(cB) == 0:
        info["note"] = "no seam"
        return np.asarray(a_v, float), np.asarray(a_f, np.int64), info
    av, af = slice_keep(a_v, a_f, y_m, a_above)
    bv, bf = slice_keep(b_v, b_f, y_m, not a_above)
    D = np.linalg.norm(cA[:, None, :] - cB[None, :, :], axis=2)
    ri, ci = linear_sum_assignment(D)
    pair = {int(j): int(i) for i, j in zip(ri, ci)}
    for j in range(len(cB)):
        if j not in pair:
            pair[j] = int(D[:, j].argmin())
    t = np.array([cA[pair[j]] - cB[j] for j in range(len(cB))])
    t[:, 1] = 0.0
    w = 1.0 / (np.linalg.norm(bv[:, None, :] - cB[None, :, :], axis=2) + 3.0) ** 2
    w /= w.sum(1, keepdims=True)
    u = w @ t
    away = (y_m - bv[:, 1]) if a_above else (bv[:, 1] - y_m)
    dec = np.clip(1.0 - away / decay, 0.0, 1.0)
    dec = 3 * dec ** 2 - 2 * dec ** 3
    bv = bv + u * dec[:, None]
    v = np.concatenate([av, bv])
    f = np.concatenate([af, bf + len(av)])
    LA = rim_loops(v, f, y_m)
    LA_a = [l for l in LA if l.max() < len(av)]
    LB_b = [l for l in LA if l.min() >= len(av)]
    info.update(seam_shift_mm=[round(float(np.linalg.norm(x)), 1) for x in t], rim_loops=[len(LA_a), len(LB_b)])
    if not LA_a or not LB_b:
        return v, f, info
    ca = np.array([v[l].mean(0) for l in LA_a])
    cb = np.array([v[l].mean(0) for l in LB_b])
    Dm = np.linalg.norm(ca[:, None, :] - cb[None, :, :], axis=2)
    ri, ci = linear_sum_assignment(Dm)
    strips = [zip_loops(v, LA_a[i], LB_b[j]) for i, j in zip(ri, ci)]
    base = f
    for orient in (1, -1):
        f2 = np.concatenate([base] + [s[:, ::orient] for s in strips])
        tm = trimesh.Trimesh(v, f2, process=False)
        if tm.is_watertight:
            info["watertight"] = True
            return v, f2, info
    f2 = np.concatenate([base] + strips)
    info["watertight"] = False
    return v, f2, info
