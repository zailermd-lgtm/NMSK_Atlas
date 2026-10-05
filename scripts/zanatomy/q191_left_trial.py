"""Q191 left-hand trial (NOT used in the build): can the left Z hand be placed from her CT SKIN envelope alone?

Her CT has no left hand bones.  Protocol: rigid rotation of the whole Z hand about the wrist + small shift, bones inside her skin 3-16 mm deep,
Z dorsal skin on her skin, Z palmar skin inside it; then per-finger joint rotations.  VALIDATION on the right hand (where her CT bones exist):
the skin-only rigid fit lands 3.9 mm (two-way median) from her CT bones, Q168 is 2.3 mm.  On the LEFT hand the best score is 2.5x the right
hand's floor (36.6 vs 14.7), the best pose turns the hand 88 deg and a competing optimum lies 46 mm away, so no pose was adopted (see data/derived/Q191_left_hand_trial.json).

    python3 scripts/zanatomy/q191_left_trial.py  [dump.npz]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q190_metrics as Mx  # noqa: E402
from scripts.zanatomy.q191_hand import apply_T, bone_ids, chamfer2, surf_pts, ORD, Q  # noqa: E402,F401


class SkinSDF:
    """signed distance to her CT skin (>0 inside, mm) on a regular grid around one hand: nearest skin vertex distance, sign by ray parity.
    Used to place a hand whose bones she has no CT of: the hand must lie inside her skin and its dorsal skin must lie on hers."""

    def __init__(self, skin, tree, box_lo, box_hi, h=2.0):
        self.lo, self.h = np.asarray(box_lo, float), h
        n = np.ceil((np.asarray(box_hi, float) - self.lo) / h).astype(int) + 1
        self.shape = tuple(n)
        g = np.stack(np.meshgrid(*[self.lo[k] + h * np.arange(n[k]) for k in range(3)], indexing="ij"), -1).reshape(-1, 3)
        d = tree.query(g)[0]
        sgn = np.ones(len(g))
        near = d < 60.0
        ins = np.zeros(len(g), bool)
        idx = np.flatnonzero(near)
        for a in range(0, len(idx), 200000):
            ii = idx[a:a + 200000]
            ins[ii] = skin.contains(g[ii])
        sgn = np.where(ins, 1.0, -1.0)
        sgn[~near] = -1.0                                  # far from the skin: outside unless proven inside (a hand box lies mostly outside the body)
        self.f = (sgn * d).reshape(self.shape)

    def __call__(self, P):
        u = (np.asarray(P, float) - self.lo) / self.h
        i0 = np.floor(u).astype(int)
        i0 = np.clip(i0, 0, np.array(self.shape) - 2)
        w = np.clip(u - i0, 0, 1)
        out = 0.0
        for dx in (0, 1):
            for dy in (0, 1):
                for dz in (0, 1):
                    wt = (w[:, 0] if dx else 1 - w[:, 0]) * (w[:, 1] if dy else 1 - w[:, 1]) * (w[:, 2] if dz else 1 - w[:, 2])
                    out = out + wt * self.f[i0[:, 0] + dx, i0[:, 1] + dy, i0[:, 2] + dz]
        return out


def rotvec_apply(rv, P, c):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_rotvec(rv).apply(P - c) + c


T_REG = 0.01


def skin_pose_objective(x, c, P_bone, P_dorsal, P_volar, sdf, dmax=None, depth_min=3.0, reg=2e-4):
    rv, t = x[:3], x[3:]
    Pb = rotvec_apply(rv, P_bone, c) + t
    Pd = rotvec_apply(rv, P_dorsal, c) + t
    Pv = rotvec_apply(rv, P_volar, c) + t
    sb = sdf(Pb)
    jb = np.mean(np.maximum(0.0, depth_min - sb) ** 2)
    if dmax is not None:         # a hand bone lies a few mm under her skin, not deep in the fused arm / trunk volume
        jb = jb + np.mean(np.maximum(0.0, sb - dmax) ** 2)
    jd = np.mean(np.minimum(sdf(Pd) ** 2, 100.0))
    jv = np.mean(np.maximum(0.0, -sdf(Pv)) ** 2)
    return jb + 0.5 * jd + jv + reg * (np.degrees(np.linalg.norm(rv)) ** 2) + T_REG * float(t @ t)


_POSE_ARGS = None


def _pose_job(x0):
    from scipy.optimize import minimize
    r = minimize(skin_pose_objective, x0, args=_POSE_ARGS, method="Powell", options={"xtol": 1e-2, "ftol": 1e-4, "maxiter": 4000})
    return r.x, float(r.fun)


def skin_pose_fit(c, P_bone, P_dorsal, P_volar, sdf, dmax=None, starts=24, seed=0, max_deg=75.0, workers=4, log=print):
    """rigid rotation about the wrist point `c` (+ a small translation) minimising the skin-envelope objective; best of several random starts
    (run in parallel).  Returns (rotvec, t, J, info)"""
    global _POSE_ARGS
    import multiprocessing as mp
    rng = np.random.default_rng(seed)
    x0s = [np.zeros(6)] + [np.r_[rng.normal(size=3) * np.radians(rng.uniform(10, max_deg)) / 1.7, rng.normal(size=3) * 4.0] for _ in range(starts - 1)]
    _POSE_ARGS = (c, P_bone, P_dorsal, P_volar, sdf, dmax)
    try:
        with mp.get_context("fork").Pool(workers) as pool:
            res = pool.map(_pose_job, x0s)
    except Exception:                                   # no fork / pool trouble: serial
        res = [_pose_job(x0) for x0 in x0s]
    order = np.argsort([r[1] for r in res])
    bx, bf = res[order[0]]
    info = {"J_best": float(bf), "J_start_pose": float(skin_pose_objective(np.zeros(6), *_POSE_ARGS)),
            "J_all_starts_sorted": [round(res[k][1], 2) for k in order[:6]], "rot_deg": round(float(np.degrees(np.linalg.norm(bx[:3]))), 1),
            "shift_mm": round(float(np.linalg.norm(bx[3:])), 1)}
    # how much the next best distinct solutions differ (mean point shift of the bone points between the best and the 2nd..5th best poses)
    Pb = rotvec_apply(bx[:3], P_bone, c) + bx[3:]
    info["alt_solution_shift_mm"] = [round(float(np.linalg.norm((rotvec_apply(res[k][0][:3], P_bone, c) + res[k][0][3:]) - Pb, axis=1).mean()), 1) for k in order[1:5]]
    return bx[:3], bx[3:], bf, info


def finger_rays(side):
    """{ray: [Z phalanx ids, proximal -> distal]}"""
    ids = bone_ids(side)
    out = {}
    for k, o in enumerate(ORD):
        out[o] = [i for i in ids["phal"] if f"_of_{o}_finger" in i]
        out[o].sort(key=lambda i: ("proximal", "middle", "distal").index(i.split("_phalanx")[0].split("zan_")[1]))
    return out


def joint_point(seg_v, prev_centroid, frac=0.12):
    """joint centre = mean of the `frac` of the segment's vertices nearest to the previous (proximal) segment's centroid"""
    d = np.linalg.norm(seg_v - prev_centroid, axis=1)
    return seg_v[np.argsort(d)[:max(8, int(frac * len(seg_v)))]].mean(0)


def articulate_fingers(side, verts, sdf, max_deg=40.0, depth_min=3.0, reg=3e-4, log=print):
    """per finger: rotations about MCP / PIP / DIP (bounded) so the phalanges lie inside her skin envelope.  verts {id: (n,3)} current positions
    (after the rigid hand fit); returns new verts and a report"""
    from scipy.optimize import minimize
    ids = bone_ids(side)
    mc = {o: verts[ids["mc"][k]] for k, o in enumerate(ORD)}
    out = {i: v.copy() for i, v in verts.items()}
    rep = {}
    for o, segs in finger_rays(side).items():
        segs = [s for s in segs if s in verts]
        prev_c = mc[o].mean(0)
        joints = []
        cen = prev_c
        for s in segs:
            joints.append(joint_point(verts[s], cen))
            cen = verts[s].mean(0)
        P = [verts[s][::2] for s in segs]

        def pose(x, pts=P):
            res = []
            for a in range(len(segs)):
                Q_ = pts[a]
                for j in range(a, -1, -1):          # segment a moves with every joint proximal to it (distal-most rotation applied first)
                    Q_ = rotvec_apply(x[3 * j:3 * j + 3], Q_, joints_cur[j])
                res.append(Q_)
            return res

        # joint positions move with the proximal rotations: first-order, rotate the joint centres with the proximal ones
        def obj(x):
            global_j = [joints[0]]
            for j in range(1, len(segs)):
                p = joints[j]
                for jj in range(j - 1, -1, -1):
                    p = rotvec_apply(x[3 * jj:3 * jj + 3], p[None], joints[jj])[0]
                global_j.append(p)
            res = []
            for a in range(len(segs)):
                Q_ = P[a]
                for j in range(a, -1, -1):
                    c = joints[j]
                    for jj in range(j - 1, -1, -1):
                        c = rotvec_apply(x[3 * jj:3 * jj + 3], c[None], joints[jj])[0]
                    Q_ = rotvec_apply(x[3 * j:3 * j + 3], Q_, c)
                res.append(Q_)
            Pn = np.vstack(res)
            ang = [np.degrees(np.linalg.norm(x[3 * j:3 * j + 3])) for j in range(len(segs))]
            return np.mean(np.maximum(0.0, depth_min - sdf(Pn)) ** 2) + reg * sum(a * a for a in ang) + 5.0 * sum(max(0.0, a - max_deg) ** 2 for a in ang)

        joints_cur = joints
        best = None
        rng = np.random.default_rng(1)
        for st in range(6):
            x0 = np.zeros(3 * len(segs)) if st == 0 else rng.normal(size=3 * len(segs)) * np.radians(15)
            r = minimize(obj, x0, method="Powell", options={"xtol": 1e-2, "ftol": 1e-5, "maxiter": 3000})
            if best is None or r.fun < best.fun:
                best = r
        x = best.x
        for a, s in enumerate(segs):
            Q_ = verts[s]
            for j in range(a, -1, -1):
                c = joints[j]
                for jj in range(j - 1, -1, -1):
                    c = rotvec_apply(x[3 * jj:3 * jj + 3], c[None], joints[jj])[0]
                Q_ = rotvec_apply(x[3 * j:3 * j + 3], Q_, c)
            out[s] = Q_
        rep[o] = {"J0": round(float(obj(np.zeros_like(x))), 3), "J": round(float(best.fun), 3), "angles_deg": [round(float(np.degrees(np.linalg.norm(x[3 * j:3 * j + 3]))), 1) for j in range(len(segs))]}
    return out, rep


def trial(dump, her, skin, tree, side):
    by = {d["id"]: d for d in Mx.load_dump(dump)}
    box = {"r": ((60, -10, 20), (270, 200, 200)), "l": ((-270, -10, 20), (-40, 260, 230))}[side]
    sdf = SkinSDF(skin, tree, *box)
    ids = bone_ids(side)
    hb = sum(ids.values(), [])
    Pb = np.vstack([by[i]["v"][::2] for i in hb])
    dmax = np.concatenate([np.full(len(by[i]["v"][::2]), 30.0 if i in ids["carpals"] else 16.0) for i in hb])
    names = [i for i in by if i.startswith("zan_skin_") and i.endswith("_" + side)]
    Pd = np.vstack([by[i]["v"] for i in names if any(k in i for k in ("dorsum_of_hand", "dorsal_surfaces_of_digits", "nail_plate", "perionyx"))])
    Pv = np.vstack([by[i]["v"] for i in names if any(k in i for k in ("palm_", "palmar_surfaces"))])
    rad = by["radius_" + side]["v"]
    c = rad[np.argsort(rad[:, 1])[:15]].mean(0)
    rv, t, J, info = skin_pose_fit(c, Pb, Pd, Pv, sdf, dmax=dmax, starts=64)
    Pn = rotvec_apply(rv, Pb, c) + t
    out = {"side": side, **info, "bones_inside_skin_pct_q168": round(100 * float((sdf(Pb) > 0).mean()), 1),
           "bones_inside_skin_pct_fit": round(100 * float((sdf(Pn) > 0).mean()), 1)}
    if side == "r":
        ref = np.vstack([surf_pts(her[k]["v"].astype(float), her[k]["f"], 3000) for k in ["carpals_r", "phalanges_hand_r"] + [f"metacarpal_{i}_r" for i in range(1, 6)]])
        out["two_way_median_mm_vs_her_ct_bones"] = {"q168_pose": [round(x, 2) for x in chamfer2(Pb, ref)], "skin_only_fit": [round(x, 2) for x in chamfer2(Pn, ref)]}
    return out


def main(argv=None):
    import pickle
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    dump = (argv or sys.argv[1:] or ["/tmp/q191/after_q190.npz"])[0]
    her, skin = load_her_meshes(), load_skin("vhf")
    tree = cKDTree(np.asarray(skin.vertices))
    res = {s: trial(dump, her, skin, tree, s) for s in "rl"}
    (REPO / "data" / "derived" / "Q191_left_hand_trial.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
