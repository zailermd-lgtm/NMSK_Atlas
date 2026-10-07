#!/usr/bin/env python3
"""Q198 READ-ONLY: Z-Anatomy fitted page vs its own unfitted base (same ids, same vertex order where the page was not decimated differently):
adjacency tears (vertex pairs <= 2 mm apart in the base, same pair in the fitted page), per-structure rigid frame offsets and stretch around every junction.
    python3 scripts/zanatomy/q198_fitseams.py z_male z_male_fit   |   z_base_f z_female_fit      -> data/derived/Q198_fitseams_<fit>.json"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy.q198_joints import find_joints  # noqa: E402


def umeyama(P, Q):
    pc, qc = P.mean(0), Q.mean(0)
    H = (P - pc).T @ (Q - qc) / len(P)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T)); D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    s = (S * np.diag(D)).sum() / (((P - pc) ** 2).sum() / len(P))
    t = qc - s * R @ pc
    return s, R, t


def rot_angle(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def main(bk, fk):
    B = load(bk); F = load(fk)
    bi = {b["id"]: b for b in B}; fi = {f["id"]: f for f in F}
    matched = [i for i in bi if i in fi and len(bi[i]["v"]) == len(fi[i]["v"]) and np.array_equal(bi[i]["f"], fi[i]["f"])]
    cov = {}
    for sysn in sorted({b["sys"] for b in B}):
        ids = [i for i in bi if bi[i]["sys"] == sysn]
        cov[sysn] = {"n": len(ids), "matched": sum(1 for i in ids if i in set(matched))}
    JB, BB, _ = find_joints(B)
    JF, BF, _ = find_joints(F)
    jf = {(j["name"], j["side"]): j for j in JF}
    out = {"base": bk, "fit": fk, "matched_structures": len(matched), "coverage_by_system": cov, "junctions": []}
    mset = set(matched)
    for jb in JB:
        key = (jb["name"], jb["side"])
        c, R = jb["centre"], jb["R"] + 25
        # restrict to structures with vertices in zone
        ids = []
        for i in matched:
            d = np.linalg.norm(bi[i]["v"] - c, axis=1)
            if (d < R).any():
                ids.append(i)
        V, W, L, ID = [], [], [], []
        for n, i in enumerate(ids):
            m = np.linalg.norm(bi[i]["v"] - c, axis=1) < R
            V.append(bi[i]["v"][m]); W.append(fi[i]["v"][m]); L.append(np.full(m.sum(), n))
        V = np.concatenate(V); W = np.concatenate(W); L = np.concatenate(L)
        tr = cKDTree(V)
        pr = tr.query_pairs(2.0, output_type="ndarray")
        pr = pr[L[pr[:, 0]] != L[pr[:, 1]]]
        dB = np.linalg.norm(V[pr[:, 0]] - V[pr[:, 1]], axis=1); dF = np.linalg.norm(W[pr[:, 0]] - W[pr[:, 1]], axis=1)
        rec = {"name": jb["name"], "side": jb["side"], "zone_structures": len(ids), "adjacent_pairs": int(len(pr))}
        if len(pr):
            rec.update({"tear_p50_mm": round(float(np.percentile(dF, 50)), 2), "tear_p90_mm": round(float(np.percentile(dF, 90)), 2), "tear_p99_mm": round(float(np.percentile(dF, 99)), 2),
                        "tear_max_mm": round(float(dF.max()), 1), "frac_gt3": round(float((dF > 3).mean()), 4), "frac_gt5": round(float((dF > 5).mean()), 4), "frac_gt10": round(float((dF > 10).mean()), 4)})
            # worst structure pairs
            pa = {}
            for (a, b), d in zip(pr, dF):
                k = (ids[L[a]], ids[L[b]]) if ids[L[a]] < ids[L[b]] else (ids[L[b]], ids[L[a]])
                x = pa.setdefault(k, [0, 0.0, 0]); x[0] += 1; x[1] = max(x[1], float(d)); x[2] += int(d > 5)
            top = sorted(((k, v) for k, v in pa.items() if v[2] >= 2), key=lambda kv: -kv[1][1])[:15]
            rec["worst_pairs"] = [{"a": k[0], "b": k[1], "pairs": v[0], "max_tear_mm": round(v[1], 1), "pairs_gt5": v[2]} for k, v in top]
            rec["n_pair_structures_with_tear_gt5"] = int(sum(1 for v in pa.values() if v[2] >= 2))
        # frame offsets: rigid similarity base->fit per structure over its zone vertices; offset of the joint centre under it
        jfit = jf.get(key)
        tf = {}
        for n, i in enumerate(ids):
            m = L == n
            if m.sum() < 25:
                continue
            Pz, Qz = V[m], W[m]
            s, Rm, t = umeyama(Pz, Qz)
            res = np.sqrt((((s * (Pz @ Rm.T) + t) - Qz) ** 2).sum(1).mean())
            tf[i] = {"s": s, "R": Rm, "t": t, "rms": float(res), "n": int(m.sum()), "c_img": s * Rm @ c + t, "sys": bi[i]["sys"]}
        bones = [x for x in (jb["prox"] + jb["dist"]) if x in tf]
        rec["frame_bones"] = bones
        offs = []
        for i, T in tf.items():
            if T["sys"] == "bone":
                continue
            dd = {b: float(np.linalg.norm(T["c_img"] - tf[b]["c_img"])) for b in bones}
            if not dd:
                continue
            bnear = min(dd, key=dd.get)
            relR = rot_angle(T["R"].T @ tf[bnear]["R"])
            offs.append({"id": i, "sys": T["sys"], "frame_offset_mm": round(dd[bnear], 1), "nearest_bone_frame": bnear, "rot_vs_bone_deg": round(relR, 1), "rigid_rms_mm": round(T["rms"], 2), "scale": round(T["s"], 3)})
        offs.sort(key=lambda x: -x["frame_offset_mm"])
        rec["structure_frame_offsets"] = offs[:40]
        rec["n_offset_gt10"] = int(sum(1 for o in offs if o["frame_offset_mm"] > 10)); rec["n_offset_gt5"] = int(sum(1 for o in offs if o["frame_offset_mm"] > 5))
        # bones relative frames: how much the distal bone moved relative to the proximal one (articulation change vs base)
        if len(bones) >= 2:
            pb = [b for b in bones if b in jb["prox"]]; db = [b for b in bones if b in jb["dist"]]
            if pb and db:
                Rrel = tf[pb[0]]["R"].T @ tf[db[0]]["R"]
                rec["articulation_change_deg"] = round(rot_angle(Rrel), 1)
                rec["bone_frame_rigid_rms_mm"] = {b: round(tf[b]["rms"], 2) for b in bones}
        # stretch of structures in zone (fit edge / base edge relative to own median)
        st = []
        for i in ids:
            if bi[i]["sys"] == "skin" or len(bi[i]["f"]) < 20:
                continue
            f = bi[i]["f"]; e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), 1), axis=0)
            lb = np.linalg.norm(bi[i]["v"][e[:, 0]] - bi[i]["v"][e[:, 1]], axis=1); lf = np.linalg.norm(fi[i]["v"][e[:, 0]] - fi[i]["v"][e[:, 1]], axis=1)
            ok = lb > 0.3
            if ok.sum() < 20:
                continue
            r = lf[ok] / lb[ok]; r = r / np.median(r)
            near = (np.linalg.norm(bi[i]["v"][e[ok, 0]] - c, axis=1) < R)
            if near.sum() < 10:
                continue
            rz = r[near]
            st.append({"id": i, "sys": bi[i]["sys"], "edge_ratio_p99": round(float(np.percentile(rz, 99)), 2), "edge_frac_gt1.5": round(float((rz > 1.5).mean()), 3), "edge_frac_lt0.67": round(float((rz < 0.67).mean()), 3)})
        st.sort(key=lambda x: -(x["edge_frac_gt1.5"] + x["edge_frac_lt0.67"]))
        rec["stretch_worst"] = st[:12]
        out["junctions"].append(rec)
        print(bk, fk, jb["name"], jb["side"], "pairs", len(pr), "tear max", rec.get("tear_max_mm"), "off>10", rec["n_offset_gt10"], flush=True)
    (REPO / "data" / "derived" / f"Q198_fitseams_{fk}.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
