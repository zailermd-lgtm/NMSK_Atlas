#!/usr/bin/env python3
"""Q241 validation of the pose rig of one page (python side, with the DECODED weights the viewer uses): every joint DOF to both ends of its normal range (all other joints at the model pose),
spine / head regions to both ends.  Per pose:
  * bone-bone interpenetration at the joint: child-segment bone surface samples inside the parent-segment bones (ray parity), depth = distance to the parent's surface; reported as the largest depth
    and the change against the model pose (a joint whose bones already overlap at rest keeps that overlap);
  * soft-tissue attachment: for every muscle the two ends (the 8% of vertices at each end of its principal axis) are tied to the nearest bone sample; the end must keep its distance to that bone
    point (|d_posed - d_rest|), i.e. origin / insertion stay attached to their bones and the muscle stretches in between;
  * exploding vertices: every soft-tissue vertex keeps its distance to ITS nearest bone sample (|d_posed - d_rest|); the largest values and the structures causing them are listed.
    python3 scripts/anatomy/q241/validate_pose.py KEY [--poses N] [--out data/derived/Q241_pose_validation_KEY.json]"""
from __future__ import annotations
import argparse, copy, json, sys, time
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model as MD, rig as RG, skin as SK, fk as FK, make_pose_rig as MR
from geom import *  # noqa


def posed_all(M, out, decoded, rig_d, Ms, only=None):
    """posed vertices of structures (decoded weights for skinned ones)"""
    res = {}
    for x in M.S:
        i = x["idx"]
        if only is not None and i not in only:
            continue
        o = out[i]
        v = x["v"]
        if o["kind"] == "rigid":
            M_ = Ms[o["seg"]]; res[i] = v @ M_[:3, :3].T + M_[:3, 3]
        else:
            sg, w = decoded[i]
            acc = np.zeros_like(v)
            for k in range(sg.shape[1]):
                for s in np.unique(sg[w[:, k] > 0, k]):
                    m = (sg[:, k] == s) & (w[:, k] > 0)
                    M_ = Ms[s]; acc[m] += w[m, k, None] * (v[m] @ M_[:3, :3].T + M_[:3, 3])
            res[i] = acc
    return res


def segments_used(out, decoded):
    """structure index -> set of segment indices it depends on"""
    dep = {}
    for i, o in enumerate(out):
        if o is None:
            continue
        if o["kind"] == "rigid":
            dep[i] = {o["seg"]}
        else:
            sg, w = decoded[i]
            dep[i] = {int(s) for s in np.unique(sg[w > 0])}
    return dep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--out")
    ap.add_argument("--max-dofs", type=int, default=0)
    a = ap.parse_args()
    t0 = time.time()
    payload, blob, report, (M, RB, rig, out, decoded) = MR.build(a.key)
    S = M.S
    nseg = len(RB.segs)
    dep = segments_used(out, decoded)
    seg_to_struct = {}
    for i, d in dep.items():
        for s in d:
            seg_to_struct.setdefault(s, set()).add(i)
    # ----- reference data: bone samples (with their segment), soft tissue nearest bone sample, muscle ends
    P, lab = SK.bone_samples(M, RB)
    tree = cKDTree(P)
    bone_idx = {i for b in M.bones().values() for i in b["idx"]}
    soft = [x for x in S if x["idx"] not in bone_idx and x["sys"] != "bone"]
    rest_d, near = {}, {}
    for x in soft:
        v = x["v"][:: max(1, len(x["v"]) // 400)]
        d, ii = tree.query(v)
        rest_d[x["idx"]] = (d, ii, np.arange(len(x["v"]))[:: max(1, len(x["v"]) // 400)])
    # muscle ends
    mus = [x for x in soft if x["sys"] == "muscle"]
    ends = {}
    for x in mus:
        v = x["v"]
        if len(v) < 40:
            continue
        c, w, V = pca(v)
        t = (v - c) @ V[:, 0]
        k = max(5, int(0.08 * len(v)))
        o = np.argsort(t)
        ends[x["idx"]] = (o[:k], o[-k:])
    # bone surface meshes for the interpenetration test
    import trimesh
    seg_bones = {}
    for k, sg in RB.bone_seg.items():
        if sg is not None:
            seg_bones.setdefault(RB.sid[sg], []).append(k)
    B = M.bones()
    bone_samples = {}
    rng = np.random.default_rng(2)
    for s, ks in seg_bones.items():
        pts = [SK.C_samples(B[k]["v"], B[k]["f"], int(np.clip(SK.C_area(B[k]["v"], B[k]["f"]) / 25.0, 60, 800)), rng) for k in ks]
        bone_samples[s] = np.vstack(pts)
    pairs = []                       # (joint id, child seg, parent seg)
    for j in rig["joints"]:
        if j.get("driven"):
            continue
        pairs.append((j["id"], j["seg"], j["par"]))
    for r in rig["regions"]:
        for L in r["levels"]:
            pairs.append((r["id"] + ":" + str(L["label"]), L["seg"], L["par"]))
    pair_by_seg = {}
    for jid, c, p in pairs:
        pair_by_seg.setdefault(c, []).append((jid, p))

    def parent_mesh(s, Ms):
        ks = seg_bones.get(s, [])
        if not ks:
            return None
        V, F, off = [], [], 0
        Mx = Ms[s]
        for k in ks:
            v = B[k]["v"] @ Mx[:3, :3].T + Mx[:3, 3]
            V.append(v); F.append(B[k]["f"] + off); off += len(v)
        return trimesh.Trimesh(np.vstack(V), np.vstack(F), process=False)

    def penetration(c, p, Ms):
        """largest depth (mm) of child samples inside the parent's bones, and the count deeper than 2 mm"""
        if c not in bone_samples or p not in seg_bones:
            return None
        pm = parent_mesh(p, Ms)
        Mc = Ms[c]
        pts = bone_samples[c] @ Mc[:3, :3].T + Mc[:3, 3]
        # bounding box prefilter
        lo, hi = pm.vertices.min(0) - 1, pm.vertices.max(0) + 1
        m = np.all((pts > lo) & (pts < hi), axis=1)
        if not m.any():
            return dict(depth_mm=0.0, n_deep=0)
        q = pts[m]
        try:
            inside = pm.contains(q)
        except Exception:
            return None
        if not inside.any():
            return dict(depth_mm=0.0, n_deep=0)
        surf = pm.sample(6000)
        d = cKDTree(surf).query(q[inside])[0]
        return dict(depth_mm=float(d.max()), n_deep=int((d > 2.0).sum()))

    base_pose = FK.default_pose(rig)
    rest_pen = {}
    Ms0 = FK.fk(rig, base_pose)
    for jid, c, p in pairs:
        rest_pen[jid] = penetration(c, p, Ms0)
    # ----- the poses
    todo = []
    for j in rig["joints"]:
        if j.get("driven"):
            continue
        for xi, d in enumerate(j["dof"]):
            todo.append(("j", j["id"], xi, d["k"], d["lo"], d["hi"]))
    for r in rig["regions"]:
        for xi, d in enumerate(r["dof"]):
            todo.append(("r", r["id"], xi, d["k"], d["lo"], d["hi"]))
    if a.max_dofs:
        todo = todo[: a.max_dofs]
    rows = []
    worst_attach, worst_vert = [], []
    expl = []
    for kind, jid, xi, dk, lo, hi in todo:
        for tag, val in (("lo", lo), ("hi", hi)):
            pose = copy.deepcopy(base_pose)
            (pose["joints"] if kind == "j" else pose["regions"])[jid][xi] = val
            Ms = FK.fk(rig, pose)
            moved = {s for s in range(nseg) if not np.allclose(Ms[s], np.eye(4), atol=1e-9)}
            only = set()
            for s in moved:
                only |= seg_to_struct.get(s, set())
            pv = posed_all(M, out, decoded, rig, Ms, only)
            # exploding vertices: a soft-tissue vertex is a blend of segment transforms, so it cannot travel farther than the farthest-moving bone point plus a margin (the displacement grows with the distance
            # from the joint); also its distance to the bone sample that was nearest at rest must stay close (reported as drift)
            bp_all = np.empty_like(P)
            for s in range(nseg):
                m = lab == s
                if m.any():
                    bp_all[m] = P[m] @ Ms[s][:3, :3].T + Ms[s][:3, 3]
            bound = float(np.linalg.norm(bp_all - P, axis=1).max()) + 80.0
            dv = []
            nexp = 0
            for x in soft:
                i = x["idx"]
                if i not in only:
                    continue
                d0, ii, vi = rest_d[i]
                bpp = bp_all[ii]
                d1 = np.linalg.norm(pv[i][vi] - bpp, axis=1)
                e = np.abs(d1 - d0)
                dv.append((float(e.max()), i))
                disp = float(np.linalg.norm(pv[i] - x["v"], axis=1).max())
                if disp > bound:
                    nexp += 1
                    expl.append((disp - bound, i, jid, dk, tag))
            dv.sort(reverse=True)
            att = []
            for i, (e1, e2) in ends.items():
                if i not in only:
                    continue
                d0, ii, vi = None, None, None
                v0 = S[i]["v"]; vp = pv[i]
                err = 0.0
                for e in (e1, e2):
                    q0 = v0[e].mean(0); qp = vp[e].mean(0)
                    dd, k = tree.query(q0)
                    b0 = P[k]; s = lab[k]; bp_ = b0 @ Ms[s][:3, :3].T + Ms[s][:3, 3]
                    err = max(err, abs(np.linalg.norm(qp - bp_) - dd))
                att.append((err, i))
            att.sort(reverse=True)
            pens = {}
            for jj, c, p in pairs:
                if c in moved or p in moved:
                    pe = penetration(c, p, Ms)
                    if pe is not None:
                        pens[jj] = pe
            row = dict(kind=kind, joint=jid, dof=dk, end=tag, value=val, moved_structures=len(only),
                       max_vertex_drift_mm=round(dv[0][0], 1) if dv else 0.0, worst_vertex=S[dv[0][1]]["id"] if dv else None,
                       p99_vertex_drift_mm=round(float(np.percentile([d[0] for d in dv], 99)), 1) if dv else 0.0,
                       muscle_end_drift_max_mm=round(att[0][0], 1) if att else 0.0, worst_muscle=S[att[0][1]]["id"] if att else None,
                       muscle_end_drift_median_mm=round(float(np.median([d[0] for d in att])), 2) if att else 0.0, n_muscles=len(att),
                       exploding_structures=nexp, displacement_bound_mm=round(bound, 1),
                       penetration={k: dict(depth_mm=round(v["depth_mm"], 1), rest_mm=round((rest_pen.get(k) or {"depth_mm": 0.0})["depth_mm"], 1), n_deep=v["n_deep"]) for k, v in pens.items() if v["depth_mm"] > 0.0})
            rows.append(row)
            print(a.key, jid, dk, tag, val, "vertex drift max", row["max_vertex_drift_mm"], "(%s)" % row["worst_vertex"], "muscle end drift max", row["muscle_end_drift_max_mm"], "(%s)" % row["worst_muscle"],
                  "pen", max([v["depth_mm"] - v["rest_mm"] for v in row["penetration"].values()] or [0.0]), flush=True)
    summ = dict(poses=len(rows), seconds=round(time.time() - t0), exploding_structure_poses=sum(1 for r in rows if r["exploding_structures"]), exploding_worst=[(S[i]["id"], round(e, 1), jid_, dk_, tg_) for e, i, jid_, dk_, tg_ in sorted(expl, reverse=True)[:8]],
                vertex_drift_max_mm=max(r["max_vertex_drift_mm"] for r in rows), vertex_drift_p99_median_mm=round(float(np.median([r["p99_vertex_drift_mm"] for r in rows])), 1),
                muscle_end_drift_max_mm=max(r["muscle_end_drift_max_mm"] for r in rows), muscle_end_drift_median_of_medians_mm=round(float(np.median([r["muscle_end_drift_median_mm"] for r in rows])), 2),
                penetration_increase_max_mm=max([max([v["depth_mm"] - v["rest_mm"] for v in r["penetration"].values()] or [0.0]) for r in rows]),
                penetration_gt_2mm_poses=sum(1 for r in rows if any(v["depth_mm"] - v["rest_mm"] > 2.0 for v in r["penetration"].values())))
    res = dict(key=a.key, label=MD.LABEL[a.key], summary=summ, rest_penetration={k: v for k, v in rest_pen.items() if v and v["depth_mm"] > 0}, rows=rows)
    f = Path(a.out) if a.out else MD.REPO / "data/derived" / ("Q241_pose_validation_%s.json" % a.key)
    f.write_text(json.dumps(res, separators=(",", ":"), default=float))
    print(a.key, "SUMMARY", json.dumps(summ))


if __name__ == "__main__":
    main()
