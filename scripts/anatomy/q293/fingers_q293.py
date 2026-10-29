#!/usr/bin/env python3
"""Q293: re-articulate the finger bones of the Combined pages (Z-Anatomy fitted onto a Visible Human body) -- the owner's
"the fingers are in a shifted / offset position".

ROOT CAUSE (measured, data/derived/Q293_fingers.json): the Combined pages place every Z-Anatomy hand bone by its OWN similarity fit to
the body's CT (Q168 / Q195 / Q200 / Q211 per-bone chain fits). Nothing tied a phalanx to the joint it belongs to, and the CT hand labels
those fits used are coarse (his `metacarpals` label also holds proximal phalanges, his thumb ray is not segmented, her fingers are one
merged label), so (a) Combined · Male's right index finger was carried 20-45 mm off his own index finger (it curls in the air with the
thumb while his CT index ray is empty), and (b) on Combined · Female the phalanges stand apart from their joints (gaps at the joint
centres up to ~10 mm). The pose rig then rotates each phalanx about a joint centre taken from the PARENT bone, so a detached phalanx
also swings off when the finger is posed.

FIX (rigid transforms of the unchanged Z-Anatomy bone meshes; no re-sculpting):
  1. joint centres from the articulated Z-Anatomy hand itself (Base · Male rig: metacarpal / phalanx head sphere centres), carried
     onto the page by the PARENT bone's own similarity; the child bone (and everything distal to it) is translated so that its own copy
     of the same joint centre coincides -> every joint closed exactly (re-seat);
  2. where the body's own CT shows that finger (his hands, her right hand), the finger's joint angles (MCP flexion + abduction, PIP and
     DIP flexion, about the Z joint axes) are refitted to his / her CT bone surface (truncated nearest distance, label-agnostic, CT
     points already taken by a placed finger excluded), accepted only if the distance falls clearly (>= 30 %) and ends < 3.5 mm median;
     the thumb (no CT thumb on his hands) is re-seated only;
  3. the finger soft tissue (tendons, lumbricals, interossei, ligaments, vessels, nerves, skin) follows by linear-blend skinning with
     weights from the distance to each finger segment's bones (sigma 6 mm, 25 mm reach), the same model the pose rig uses.

    python3 scripts/anatomy/q293/fingers_q293.py build [--keys comb_m,comb_f] [--out /dev/shm/q293/work]
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import minimize

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
REPORT = REPO / "data/derived/Q293_fingers.json"
CT_OF = {"comb_m": "own_m", "comb_f": "own_f"}
SIG, REACH, TRUNC = 6.0, 25.0, 12.0
DEBUG = False


def rot(a, deg):
    a = np.asarray(a, float); a = a / np.linalg.norm(a); x, y, z = a; t = np.radians(deg); c, s = np.cos(t), np.sin(t); u = 1 - c
    return np.array([[c + x * x * u, x * y * u - z * s, x * z * u + y * s], [y * x * u + z * s, c + y * y * u, y * z * u - x * s], [z * x * u - y * s, z * y * u + x * s, c + z * z * u]])


def similarity(a, b):
    ca, cb = a.mean(0), b.mean(0); A, Bm = a - ca, b - cb
    s = np.sqrt((Bm ** 2).sum() / (A ** 2).sum()); U, _, Vt = np.linalg.svd(A.T @ Bm); R = (U @ Vt).T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1; R = (U @ Vt).T
    return s, R, cb - s * R @ ca


def chains(side):
    out = {1: [("thumb_mcp", "mc_1", "ph_hand_1_prox"), ("thumb_ip", "ph_hand_1_prox", "ph_hand_1_dist")]}
    for f in range(2, 6):
        out[f] = [(f"f{f}_mcp", f"mc_{f}", f"ph_hand_{f}_prox"), (f"f{f}_pip", f"ph_hand_{f}_prox", f"ph_hand_{f}_midd"), (f"f{f}_dip", f"ph_hand_{f}_midd", f"ph_hand_{f}_dist")]
    return {f: [(j + "_" + side, p + "_" + side, c + "_" + side) for j, p, c in L] for f, L in out.items()}


def seg_of_bone(b):
    """the pose-rig segment a hand bone belongs to (rig.py names)"""
    p = b.split("_")
    if b.startswith("mc_"):
        return ("th_mc_" if p[1] == "1" else "hand_") + p[-1]
    f, part, s = p[2], p[3], p[-1]
    if f == "1":
        return {"prox": "th_p_", "dist": "th_d_"}[part] + s
    return f"f{f}_{part[0]}_{s}"


def build_key(key, rep, outdir):
    import model as Mo
    Mb, M = Mo.Model("base_m"), Mo.Model(key)
    Bb, B = Mb.bones(), M.bones()
    rigb = {j["id"]: j for j in json.loads((REPO / "data/anatomy/pose_rig_base_m.json").read_text())["rig"]["joints"]}
    ct = Mo.Model(CT_OF[key]).bones()
    S = {k: [v.copy() for v in (M.S[i]["v"] for i in B[k]["idx"])] for k in B if k.startswith(("mc_", "ph_hand_"))}
    T = {k: similarity(np.asarray(Bb[k]["v"], float), np.asarray(B[k]["v"], float)) for k in S if k in Bb}
    X = lambda t, p: t[0] * t[1] @ np.asarray(p, float) + t[2]
    delta = {}                       # bone -> 4x4 rigid delta (page -> corrected page)
    krep = {"joints": {}, "fingers": {}}
    for side in "rl":
        ctp = [ct[k]["v"] for k in ct if k.endswith("_" + side) and (k.startswith("phalanges_hand") or k.startswith(("metacarpal", "mc_")))]
        has_ct_fingers = any(k.startswith("phalanges_hand_" + side) and str(ct[k].get("idx")) for k in ct) and \
            any(len(ct[k]["v"]) > 500 for k in ct if k.startswith("phalanges_hand_" + side) and not any(str(M.S[0]) for _ in ()))
        subj = {k: str(Mo.Model.__name__) for k in ()}
        CT = np.vstack(ctp) if ctp else np.zeros((0, 3))
        own_ct = [k for k in ct if k.startswith("phalanges_hand_" + side)]
        ct_is_own = bool(own_ct) and all("xfer" not in str(Mo.Model(CT_OF[key]).S[i]["src"]) for k in own_ct for i in ct[k]["idx"][:1])
        ch = chains(side)
        # current placement of every bone as 4x4 (page) and the running correction
        def M4(R, t):
            m = np.eye(4); m[:3, :3] = R; m[:3, 3] = t; return m
        D = {k: np.eye(4) for k in S}
        V = lambda k: np.vstack(S[k]) @ D[k][:3, :3].T + D[k][:3, 3]
        def joint_pts(j, p, c):
            cj = np.array(rigb[j]["c"]); a = np.array(rigb[j]["dof"][0]["a"])
            cp = D[p][:3, :3] @ X(T[p], cj) + D[p][:3, 3]; cc = D[c][:3, :3] @ X(T[c], cj) + D[c][:3, 3]
            ap = D[p][:3, :3] @ T[p][1] @ a
            return cp, cc, ap / np.linalg.norm(ap)
        def apply_chain(f, start, m):
            """left-multiply the rigid m onto every bone of finger f from chain index `start` distally"""
            for (_, _, c) in ch[f][start:]:
                D[c] = m @ D[c]
        # 1. re-seat
        for f, L in ch.items():
            for i, (j, p, c) in enumerate(L):
                if p not in T or c not in T:
                    continue
                cp, cc, _ = joint_pts(j, p, c)
                krep["joints"][j] = {"gap_before_mm": round(float(np.linalg.norm(cp - cc)), 2)}
                apply_chain(f, i, M4(np.eye(3), cp - cc))
        # 2. refit angles to the body's own CT
        claimed = np.zeros(len(CT), bool)
        if len(CT) and ct_is_own:
            Tct = cKDTree(CT)
            def score(pts, free, tr=TRUNC):
                d, ii = Tct.query(pts, distance_upper_bound=tr)
                d = np.where(np.isfinite(d) & free[np.minimum(ii, len(CT) - 1)], d, tr)
                return float(np.mean(np.minimum(d, tr))), float(np.median(d))
            order = sorted([f for f in range(2, 6) if all(c in T for (_, _, c) in ch[f])], key=lambda f: score(np.vstack([V(c) for (_, _, c) in ch[f]]), ~claimed)[0])
            for f in order:
                L = ch[f]; D0 = {c: D[c].copy() for (_, _, c) in L}
                pts0 = np.vstack([V(c) for (_, _, c) in L]); s0, m0 = score(pts0, ~claimed)
                def pose(q):
                    """q = MCP flexion, MCP abduction, PIP, DIP flexion RELATIVE to the articulated Z-Anatomy hand (Base · Male rest pose),
                    about the Z joint axes carried by the parent bone: the child bone's similarity is rebuilt from its parent's"""
                    for i, (j, p, c) in enumerate(L):
                        cj = np.array(rigb[j]["c"]); a0 = np.array(rigb[j]["dof"][0]["a"])
                        Rp = (D[p][:3, :3] @ T[p][1]); cp = D[p][:3, :3] @ X(T[p], cj) + D[p][:3, 3]
                        a = Rp @ a0; a /= np.linalg.norm(a)
                        if i == 0:
                            u0 = np.asarray(Bb[c]["v"], float).mean(0) - cj; ab = Rp @ np.cross(a0, u0); ab /= np.linalg.norm(ab)
                            R = rot(a, q[0]) @ rot(ab, q[1])
                        else:
                            R = rot(a, q[i + 1])
                        sc, Rc, tc = T[c]
                        R2 = R @ Rp                                   # the child's new rotation (canonical articulation + the joint angles)
                        t2 = cp - sc * R2 @ cj                        # its joint centre on the parent's
                        m = np.eye(4); m[:3, :3] = R2 @ Rc.T; m[:3, 3] = t2 - R2 @ Rc.T @ tc
                        D[c] = m
                    return np.vstack([V(c) for (_, _, c) in L])
                LO, HI = np.array([-56, -25, -19, -11]), np.array([79, 25, 81, 79])     # the rig's ROM (finger_mcp / pip / dip) about the Z rest angles
                best = (1e9, np.zeros(4))
                # coarse grid with a long truncation (a finger far from its CT ray still sees it), then local refinement
                coarse = sorted(((score(pose([a, b, c, c * 0.6]), ~claimed, 40.0)[0], [a, b, c, c * 0.6]) for a in range(-50, 80, 10)
                                 for b in (-25, -12, 0, 12, 25) for c in (-15, 0, 20, 40, 60, 80)), key=lambda t: t[0])[:4]
                if DEBUG: print("coarse", key, f, side, s0, coarse, int((~claimed).sum()), len(CT))
                for q0 in [c[1] for c in coarse]:
                    r = minimize(lambda q: score(pose(np.clip(q, LO, HI)), ~claimed)[0], np.array(q0, float), method="Powell",
                                 options={"xtol": 0.5, "ftol": 1e-3, "maxfev": 800})
                    if r.fun < best[0]:
                        best = (float(r.fun), np.clip(r.x, LO, HI))
                pts = pose(best[1]); s1, m1 = score(pts, ~claimed)
                ok = s1 <= 0.7 * s0 and m1 < 3.5
                if not ok:
                    for (_, _, c) in L:
                        D[c] = D0[c]
                    pts = pts0
                d, ii = Tct.query(pts, distance_upper_bound=4.0); claimed[ii[np.isfinite(d)]] = True
                krep["fingers"][f"f{f}_{side}"] = {"ct_trunc_mean_mm_before": round(s0, 2), "ct_median_mm_before": round(m0, 2),
                                                  "ct_trunc_mean_mm_after": round(s1 if ok else s0, 2), "ct_median_mm_after": round(m1 if ok else m0, 2),
                                                  "refit_accepted": bool(ok), "deg_vs_z_rest_mcp_flex_abd_pip_dip": [round(float(x), 1) for x in best[1]] if ok else None}
        else:
            krep["fingers"][f"hand_{side}"] = "no own CT finger bones on this side (transferred / absent): joints re-seated only"
        for f, L in ch.items():
            for (j, p, c) in L:
                if p in T and c in T:
                    cp, cc, _ = joint_pts(j, p, c); krep["joints"][j]["gap_after_mm"] = round(float(np.linalg.norm(cp - cc)), 3)
        for k in D:
            if k.endswith("_" + side):
                delta[k] = D[k]
    # 3. carry the soft tissue with the pose rig's own skinning model (scripts/anatomy/q241/skin.py, the same weights the page's rig
    #    gives these structures, prior from the Base page): v' = sum_s w_s(v) D_s v, D_s = the segment's correction (identity off the fingers)
    import rig as RG, skin as SK, make_pose_rig as MPR
    RB = RG.RigBuilder(M); RB.build(); sid = RB.sid
    segD = [np.eye(4) for _ in RB.segs]
    for k, m in delta.items():
        segD[sid[seg_of_bone(k)]] = m
    moved = {i for i, m in enumerate(segD) if np.abs(m - np.eye(4)).max() > 1e-6}
    lo = np.min([np.asarray(B[k]["v"]).min(0) for k in delta], 0) - REACH
    hi = np.max([np.asarray(B[k]["v"]).max(0) for k in delta], 0) + REACH
    bone_idx = {i: k for k in delta for i in B[k]["idx"]}
    cand = {x["idx"] for x in M.S if x["idx"] not in bone_idx and not ((np.asarray(x["v"]).max(0) < lo).any() or (np.asarray(x["v"]).min(0) > hi).any())}
    out, _ = SK.compute(M, RB, verbose=False, only=cand, prior=MPR.get_prior(key))
    newV, smoved = {}, {}
    for i, k in bone_idx.items():
        m = delta[k]
        if np.abs(m - np.eye(4)).max() > 1e-6:
            newV[i] = np.asarray(M.S[i]["v"], float) @ m[:3, :3].T + m[:3, 3]
    for i in cand:
        o = out[i]
        segs = {o["seg"]} if o["kind"] == "rigid" else set(np.unique(o["idx"][o["w"] > 0]).tolist())
        if not segs & moved:
            continue
        v = np.asarray(M.S[i]["v"], float)
        # a vertex follows a corrected finger segment only within REACH of that segment's bones (the Combined bodies rest their hands on the
        # abdomen / thighs: rig weights alone would drag e.g. the inferior epigastric vessels along with an index finger)
        far = np.stack([cKDTree(np.vstack([np.asarray(B[b]["v"], float) for b in delta if sid[seg_of_bone(b)] == sg])).query(v)[0] >= REACH
                        if sg in moved else np.zeros(len(v), bool) for sg in range(len(RB.segs))], 1)
        if o["kind"] == "rigid":
            o = {"kind": "skin", "idx": np.full((len(v), 1), o["seg"], np.int64), "w": np.ones((len(v), 1))}
        w = o["w"].astype(float) * ~np.take_along_axis(far, o["idx"].astype(np.int64), 1)
        idx = np.c_[o["idx"], np.zeros((len(v), 1), np.int64)]; w = np.c_[w, 1.0 - w.sum(1)]     # the removed share stays put (segment 0 = identity)
        oo = {"kind": "skin", "idx": idx, "w": w}
        segD0 = list(segD); segD0[0] = np.eye(4)
        pv = SK.apply_pose([M.S[i]], {i: oo}, segD0)[i]
        if np.abs(pv - v).max() > 1e-4:
            newV[i] = pv; smoved[M.S[i]["id"]] = round(float(np.linalg.norm(pv - v, axis=1).max()), 2)
    krep["moved_bones"] = sorted(M.S[i]["id"] for i in newV if i in bone_idx)
    krep["moved_soft_tissue_max_mm"] = dict(sorted(smoved.items(), key=lambda t: -t[1]))
    krep["n_structures_changed"] = len(newV)
    rep[key] = krep
    np.savez_compressed(Path(outdir) / f"fingers_{key}.npz", **{M.S[i]["id"]: v for i, v in newV.items()})
    return krep


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build"]); ap.add_argument("--keys", default="comb_m,comb_f")
    ap.add_argument("--out", default="/dev/shm/q293/work")
    a = ap.parse_args(); Path(a.out).mkdir(parents=True, exist_ok=True)
    rep = {"_README": ["Q293 finger re-articulation of the Combined pages; scripts/anatomy/q293/fingers_q293.py (method in its docstring)"],
           "sigma_mm": SIG, "reach_mm": REACH}
    for k in a.keys.split(","):
        r = build_key(k, rep, a.out)
        print(k, json.dumps({kk: vv for kk, vv in r.items() if kk != "moved_soft_tissue_max_mm"})[:3000], "soft tissue moved", len(r["moved_soft_tissue_max_mm"]))
    REPORT.write_text(json.dumps(rep, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
