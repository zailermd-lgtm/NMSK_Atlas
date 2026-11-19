"""Q200: separate a movable (Z-filled / transferred) muscle from the measured muscles it sits inside.

Bounded displacement of the movable mesh only: every vertex inside a fixed neighbour is moved toward that neighbour's nearest surface
point (0.7 x (depth + 0.3 mm) per round, <= 4 mm per round, <= 8 mm in total, smoothed over the mesh), then the volume guard (0.65-1.5 x
of the starting volume), the skin and the bones are re-applied; a round that breaks a guard is dropped."""
from __future__ import annotations
import numpy as np
import trimesh
from scipy.sparse import coo_matrix


def _lap(v, f, d, iters=3):
    n = len(v)
    A = coo_matrix((np.ones(len(f) * 6), (np.r_[f[:, 0], f[:, 1], f[:, 2], f[:, 1], f[:, 2], f[:, 0]], np.r_[f[:, 1], f[:, 2], f[:, 0], f[:, 0], f[:, 1], f[:, 2]])), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    deg = np.asarray(A.sum(1)).ravel()
    out = d.copy()
    for _ in range(iters):
        out = 0.5 * out + 0.5 * (A @ out) / np.maximum(deg, 1)[:, None]
    return out


def mesh_volume(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def inside_fraction(v, others):
    """fraction of v (vertices) inside any of the closed-ish `others` meshes (trimesh list) and the deepest penetration (mm)"""
    inside = np.zeros(len(v), bool)
    depth = np.zeros(len(v))
    for m in others:
        lo, hi = m.bounds
        sel = np.where(np.all((v >= lo - 1) & (v <= hi + 1), axis=1))[0]
        if not len(sel):
            continue
        ins = m.contains(v[sel])
        if ins.any():
            idx = sel[ins]
            _, d, _ = m.nearest.on_surface(v[idx])
            inside[idx] = True
            depth[idx] = np.maximum(depth[idx], d)
    return float(inside.mean()), float(depth.max() if inside.any() else 0.0), inside, depth


def separate(v, f, others, constrain=None, rounds=5, step=0.7, per_round=4.0, total=8.0, vol=(0.65, 1.5), pin=None):
    """returns (v_new, info). others: list of trimesh.Trimesh (fixed). constrain(v) -> v (skin / bone constraints)."""
    v0 = v.copy()
    vol0 = mesh_volume(v0, f)
    frac0, dmax0, _, _ = inside_fraction(v0, others)
    cur = v0.copy()
    used = 0
    for r in range(rounds):
        frac, dmax, ins, depth = inside_fraction(cur, others)
        if frac < 0.005:
            break
        disp = np.zeros_like(cur)
        for m in others:
            lo, hi = m.bounds
            sel = np.where(ins & np.all((cur >= lo - 1) & (cur <= hi + 1), axis=1))[0]
            if not len(sel):
                continue
            inm = m.contains(cur[sel])
            idx = sel[inm]
            if not len(idx):
                continue
            cl, d, _ = m.nearest.on_surface(cur[idx])
            dirv = cl - cur[idx]
            nn = np.linalg.norm(dirv, axis=1, keepdims=True)
            dirv = dirv / np.maximum(nn, 1e-9)
            amt = np.minimum(step * (d + 0.3), per_round)
            cand = dirv * amt[:, None]
            better = np.linalg.norm(cand, axis=1) > np.linalg.norm(disp[idx], axis=1)
            disp[idx[better]] = cand[better]
        disp = _lap(cur, f, disp)
        if pin is not None:
            disp[pin] = 0.0
        nxt = cur + disp
        tot = nxt - v0
        n = np.linalg.norm(tot, axis=1)
        sc = np.minimum(1.0, total / np.maximum(n, 1e-9))
        nxt = v0 + tot * sc[:, None]
        if constrain is not None:
            nxt = constrain(nxt)
            if pin is not None:
                nxt[pin] = v0[pin]
        vr = mesh_volume(nxt, f) / max(vol0, 1e-9)
        if not (vol[0] <= vr <= vol[1]):
            break
        cur = nxt; used += 1
    frac1, dmax1, _, _ = inside_fraction(cur, others)
    mv = np.linalg.norm(cur - v0, axis=1)
    return cur, dict(rounds=used, inside_before=frac0, inside_after=frac1, depth_before=dmax0, depth_after=dmax1,
                     move_max=float(mv.max()), move_median=float(np.median(mv)), volume_ratio=mesh_volume(cur, f) / max(vol0, 1e-9))
