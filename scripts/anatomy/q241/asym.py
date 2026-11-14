"""Q241 part 1: LEFT vs RIGHT POSE difference of every limb / joint of a model, separated from tissue anatomy.
 - joint angles of the skeleton as built (rig.py: landmark based, left limb reflected into right-limb space, so equal numbers = same anatomical posture)
 - per-segment rigid registration of the mirrored LEFT bones onto the RIGHT bones (ICP, 4 principal-axis initialisations) = the rotation / translation that would match the poses
 - spine / pelvis / head: the bilateral-symmetry plane of every vertebra / of the pelvis / of the skull against the midsagittal plane (axial rotation, lateral tilt)
 - tissue: Q237 pair metrics before, and after a per-bone rigid alignment of the mirrored left soft tissue (skinned with the rig weights)."""
from __future__ import annotations
import json, sys, time, re, math
import numpy as np
from scipy.spatial import cKDTree
from scipy.optimize import minimize
import model as MD, rig as RG, skin as SK
from geom import *  # noqa
import core as C   # scripts/anatomy/q237/core.py


# ------------------------------------------------------------------ registration
def icp(P, Q, R0, t0, iters=25, keep=0.85):
    tq = cKDTree(Q)
    R, t = R0.copy(), t0.copy()
    for _ in range(iters):
        X = P @ R.T + t
        d, i = tq.query(X)
        k = d <= np.quantile(d, keep)
        dR, dt = kabsch(X[k], Q[i[k]])
        R, t = dR @ R, dR @ t + dt
    X = P @ R.T + t
    d = tq.query(X)[0]
    return R, t, float(np.median(d)), float(np.percentile(d, 90))


def register(P, Q):
    """rigid transform of P onto Q (point clouds of the same kind of bone): centroid alignment + identity + the 4 proper sign combinations of the principal axes as initial rotations, ICP each, best median residual"""
    pc, qc = P.mean(0), Q.mean(0)
    _, _, Vp = pca(P); _, _, Vq = pca(Q)
    inits = [np.eye(3)]
    for sg in ((1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1), (-1, -1, -1)):
        R0 = Vq @ np.diag(sg) @ Vp.T
        if np.linalg.det(R0) > 0:
            inits.append(R0)
    best = None
    for R0 in inits:
        t0 = qc - R0 @ pc
        R, t, med, p90 = icp(P, Q, R0, t0)
        if best is None or med < best[2]:
            best = (R, t, med, p90)
    return best


# ------------------------------------------------------------------ plane of one bone / group
def symmetry_plane(v, plane0, E, n_samp=1500, seed=0):
    """best bilateral symmetry plane of a point set (start: the model plane through the set's centroid) -> (normal, d, residual median)"""
    rng = np.random.default_rng(seed)
    P = v[rng.choice(len(v), min(len(v), n_samp), replace=False)]
    tr = cKDTree(P)
    n0 = plane0.n
    d0 = float(P.mean(0) @ n0)
    # parametrise the normal by rotations about up and anterior axes of E starting at n0
    up, ant = E[:, 1], E[:, 2]

    def mk(par):
        d, a, b = par
        n = rot(up, np.degrees(a)) @ rot(ant, np.degrees(b)) @ n0
        return unit(n), d

    def cost(par):
        n, d = mk(par)
        Pm = P - 2.0 * np.outer(P @ n - d, n)
        dd = np.minimum(tr.query(Pm)[0], 40.0)
        return float(0.5 * np.median(dd) + 0.5 * np.percentile(dd, 75))
    best = None
    for off in (0.0, -8.0, 8.0):
        r = minimize(cost, [d0 + off, 0.0, 0.0], method="Nelder-Mead", options=dict(xatol=0.02, fatol=1e-4, maxiter=300,
                     initial_simplex=np.array([[d0 + off, 0, 0], [d0 + off + 3, 0, 0], [d0 + off, 0.04, 0], [d0 + off, 0, 0.04]])))
        if best is None or r.fun < best.fun:
            best = r
    n, d = mk(best.x)
    return n, d, float(best.fun)


def plane_angles(n, E):
    """(axial rotation deg, + = turned to the subject's left; lateral tilt deg, + = right side up) of a symmetry-plane normal relative to the trunk frame E (right, up, anterior)"""
    nr, nu, na = n @ E[:, 0], n @ E[:, 1], n @ E[:, 2]
    return float(np.degrees(np.arctan2(na, nr))), float(np.degrees(np.arctan2(nu, nr)))


# ------------------------------------------------------------------ segment registration
def segment_points(M, RB, n=1500):
    """segment index -> bone surface sample points (rigid bones of the segment)"""
    rng = np.random.default_rng(3)
    pts = {}
    for k, sg in RB.bone_seg.items():
        if sg is None:
            continue
        b = M.bones()[k]
        a = SK.C_area(b["v"], b["f"])
        p = SK.C_samples(b["v"], b["f"], int(np.clip(a / 8.0, 200, 3000)), rng)
        pts.setdefault(RB.sid[sg], []).append(p)
    out = {}
    for i, l in pts.items():
        P = np.vstack(l)
        if len(P) > n * 2:
            P = P[rng.choice(len(P), n * 2, replace=False)]
        out[i] = P
    return out


def segment_registration(M, RB):
    """T[i] (4x4) for every left / midline segment: maps the reflected left (or midline) bones onto the right (or the segment's own) bones"""
    plane = M.plane
    SP = segment_points(M, RB)
    out = {}
    for i, sg in enumerate(RB.segs):
        if i not in SP:
            continue
        sd = sg["side"]
        if sd == "r":
            continue
        if sd == "l":
            j = RB.sid.get(sg["id"][:-2] + "_r")
            if j is None or j not in SP:
                continue
            Q = SP[j]
        else:
            Q = SP[i]
        P = plane.reflect(SP[i])
        R, t, med, p90 = register(P, Q)
        T = np.eye(4); T[:3, :3] = R; T[:3, 3] = t
        pc = P.mean(0)
        out[i] = dict(T=T, rot_deg=rot_angle(R), trans_mm=float(np.linalg.norm(R @ pc + t - pc)), med_mm=med, p90_mm=p90, n=len(P))
    return out


# ------------------------------------------------------------------ joint-angle table
GROUP_THR = {  # |left - right| tolerance in degrees (ASSUMPTIONS, see docs/Q241 text): resting left-right differences of healthy adults are a few degrees
    "shoulder": 5.0, "elbow": 5.0, "forearm": 8.0, "wrist": 5.0, "fingers": 8.0, "hip": 5.0, "knee": 5.0, "ankle": 5.0, "toes": 8.0,
    "pelvis": 3.0, "spine": 3.0, "head": 5.0,
}
ROT_DOFS = ("rot", "sup", "inv")           # rotations about the long axis are poorly defined by landmarks: tolerance x1.6
GROUP_OF = lambda jid: ("shoulder" if jid.startswith("shoulder") else "elbow" if jid.startswith("elbow") else "forearm" if jid.startswith("forearm") else "wrist" if jid.startswith("wrist")
                        else "fingers" if re.match(r"(f\d|thumb)", jid) else "hip" if jid.startswith("hip") else "knee" if jid.startswith("knee") else "ankle" if jid.startswith(("ankle", "subtalar"))
                        else "toes" if jid.startswith("t") else "other")


def angle_table(rig):
    J = {j["id"]: j for j in rig["joints"]}
    rows = []
    for jid, j in J.items():
        if j["side"] != "r" or j.get("driven"):
            continue
        l = J.get(jid[:-1] + "l")
        if l is None:
            continue
        for d, dl in zip(j["dof"], l["dof"]):
            dv = d["q0"] - dl["q0"]
            if j["id"].startswith("forearm"):
                dv = wrap(dv)
            rows.append(dict(joint=jid[:-2], name=j["name"], dof=d["k"], label=d["l"], right=round(d["q0"], 1), left=round(dl["q0"], 1), diff=round(dv, 1),
                             group=GROUP_OF(jid), lo=d["lo"], hi=d["hi"], right_in_range=bool(d["lo"] <= d["q0"] <= d["hi"]), left_in_range=bool(dl["lo"] <= dl["q0"] <= dl["hi"])))
    return rows


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def trunk_table(M, RB):
    """spine / pelvis / head from the symmetry planes of the individual bones against the midsagittal plane"""
    K, E, plane = RB.K, RB.K.E, M.plane
    rows = []
    for v in K.spine:
        n, d, res = symmetry_plane(v["v"], plane, E)
        rot_, tilt = plane_angles(n, E)
        rows.append(dict(item="vertebra " + v["label"], region=v["region"], rotation_deg=round(rot_, 1), tilt_deg=round(tilt, 1), offset_mm=round(float(d - v["c"] @ plane.n + (v["c"] @ plane.n - plane.d) * 0 + (v["c"] @ plane.n - plane.d)), 1), centroid_offset_mm=round(float(plane.signed(v["c"])), 1), residual_mm=round(res, 2)))
    for nm, keys in (("pelvis (hip bones + sacrum)", [k for k in K.B if k.startswith("hip_bone") or k == "sacrum"]),
                     ("skull", [k for k in K.B if k in ("cranium", "frontal", "occipital", "sphenoid", "ethmoid", "vomer") or k.startswith(("temporal", "parietal", "zygomatic", "maxilla"))]),
                     ("thorax (ribs + sternum)", [k for k in K.B if k.startswith(("rib_", "ribs_")) or k == "sternum"])):
        if not keys:
            continue
        v = np.vstack([K.B[k]["v"] for k in keys])
        n, d, res = symmetry_plane(v, plane, E)
        rot_, tilt = plane_angles(n, E)
        rows.append(dict(item=nm, region=nm.split()[0], rotation_deg=round(rot_, 1), tilt_deg=round(tilt, 1), centroid_offset_mm=round(float(plane.signed(v.mean(0))), 1), residual_mm=round(res, 2)))
    return rows


def pelvis_angles(RB):
    E = RB.K.E
    P = RB.pelvis_frame
    R_, U_, A_ = E[:, 0], E[:, 1], E[:, 2]
    D0 = P @ E.T
    a_t = RG.axis_for(U_, A_, R_)       # anterior tilt (+)
    a_o = RG.axis_for(R_, U_, A_)       # right side up (+)
    a_r = RG.axis_for(A_, -R_, U_)      # turned to the subject's left (+)
    q, err = solve_euler([a_t, a_o, a_r], D0)
    return dict(tilt_deg=round(float(q[0]), 1), obliquity_deg=round(float(q[1]), 1), rotation_deg=round(float(q[2]), 1))


def run_angles(key):
    M = MD.Model(key)
    RB = RG.RigBuilder(M)
    rig = RB.build()
    rows = angle_table(rig)
    trunk = trunk_table(M, RB)
    pel = pelvis_angles(RB)
    return M, RB, rig, rows, trunk, pel


# ------------------------------------------------------------------ tissue before / after pose normalisation
G = {}


def aligned_left(v, o, segT, plane):
    """mirrored left vertices after the per-bone rigid alignment: sum_s w_s T_s(reflect(v))"""
    vm = plane.reflect(v)
    if o["kind"] == "rigid":
        T = segT.get(o["seg"])
        return vm if T is None else vm @ T[:3, :3].T + T[:3, 3]
    out = np.zeros_like(vm)
    for j in range(o["idx"].shape[1]):
        w = o["w"][:, j]
        if not w.any():
            continue
        for sg in np.unique(o["idx"][w > 0, j]):
            m = (o["idx"][:, j] == sg) & (w > 0)
            T = segT.get(int(sg))
            out[m] += w[m, None] * (vm[m] if T is None else vm[m] @ T[:3, :3].T + T[:3, 3])
    return out


def unit_job(u):
    """u = Q237 paired unit -> dict(after metrics)"""
    from pairing import voxel_pair            # scripts/anatomy/q237/pairing.py
    S, plane, skin_out, segT = G["S"], G["plane"], G["skin"], G["segT"]
    idr = [S_i for S_i in G["idx"][tuple(u["ids_r"])]]
    idl = [S_i for S_i in G["idx"][tuple(u["ids_l"])]]
    vr, fr = C.merge(S, idr)
    vls, fls, off = [], [], 0
    for i in idl:
        va = aligned_left(S[i]["v"], skin_out[i], segT, plane)
        vls.append(va); fls.append(S[i]["f"][:, ::-1] + off); off += len(va)
    va = np.vstack(vls); fa = np.vstack(fls)
    vm, fm = plane.reflect_mesh(np.vstack([S[i]["v"] for i in idl]), np.vstack([S[i]["f"] + sum(len(S[k]["v"]) for k in idl[:n]) for n, i in enumerate(idl)]))
    rng = np.random.default_rng(1)
    sheet = S[idr[0]]["sys"] in ("fascia", "skin")
    A = C.area_samples(vr, fr, 1500, rng); B = C.area_samples(va, fa, 1500, rng)
    tA, tB = cKDTree(A), cKDTree(B)
    dd = np.concatenate([tB.query(A)[0], tA.query(B)[0]])
    cA, cB = A.mean(0), B.mean(0)
    try:
        iou, kind, pitch, v1, v2 = voxel_pair(vr, fr, va, fa, None, rng, force_shell=sheet)
    except Exception:
        iou, kind = float("nan"), "error"
    return dict(iou_pose=None if iou != iou else round(float(iou), 3), iou_kind=kind, centroid_offset_pose_mm=round(float(np.linalg.norm(cB - cA)), 2), msd_pose_mm=round(float(np.median(dd)), 2),
                hd95_pose_mm=round(float(np.percentile(dd, 95)), 2))


def tissue(key, M, RB, jobs=4, limit=None):
    """pose-normalise every PAIRED unit of the Q237 table of this page -> per unit before / after"""
    import multiprocessing as mp
    pj = json.load(open(MD.REPO / "data/derived/Q237_pairing.json"))["pages"][key]
    units = [u for u in pj["units"] if u["cls"] == "paired" and u.get("metrics")]
    if limit:
        units = units[:limit]
    t0 = time.time()
    import make_pose_rig as MR
    out, st = SK.compute(M, RB, prior=MR.get_prior(key))
    segT = {i: d["T"] for i, d in segment_registration(M, RB).items()}
    G.update(S=M.S, plane=M.plane, skin=out, segT=segT)
    idx = {}
    for x in M.S:
        pass
    byid = {}
    for x in M.S:
        byid.setdefault(x["id"], []).append(x["idx"])
    for u in units:
        idx[tuple(u["ids_r"])] = [i for n in u["ids_r"] for i in byid[n]]
        idx[tuple(u["ids_l"])] = [i for n in u["ids_l"] for i in byid[n]]
    G["idx"] = idx
    res = []
    if jobs > 1:
        with mp.get_context("fork").Pool(jobs) as pool:
            res = pool.map(unit_job, units, chunksize=4)
    else:
        res = [unit_job(u) for u in units]
    rows = []
    for u, r in zip(units, res):
        m = u["metrics"]
        rows.append(dict(sys=u["sys"], canon=u["canon"], ratio=m["ratio_r_over_l"], ratio_basis=m["ratio_basis"], thin=m.get("thin"), iou_before=m["iou_mirror"], iou_icp=m["iou_aligned"], iou_kind_before=m["iou_kind"],
                         centroid_before_mm=m["centroid_offset_mm"], msd_before_mm=m["msd_mm"], tier=u.get("tier"), **r))
    return rows, dict(seconds=round(time.time() - t0, 1), segments_registered=len(segT))
