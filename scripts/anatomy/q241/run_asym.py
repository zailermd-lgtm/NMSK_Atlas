#!/usr/bin/env python3
"""Q241 part 1 driver: LEFT vs RIGHT pose difference + tissue asymmetry before / after pose normalisation, six pages
-> data/derived/Q241_pose_asymmetry.json (+ Q241_pose_asymmetry.md by report_md.py).   python3 scripts/anatomy/q241/run_asym.py [--pages base_m,...] [--jobs 4] [--no-tissue]"""
from __future__ import annotations
import argparse, datetime, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import asym as A, model as MD, rig as RG
from geom import rot_angle

OUT = MD.REPO / "data/derived/Q241_pose_asymmetry.json"
RATIO_LO, RATIO_HI, IOU_MIN = 0.8, 1.25, 0.6


def summarise_tissue(rows):
    def med(k, rs):
        v = [r[k] for r in rs if r.get(k) is not None]
        return round(float(np.median(v)), 3) if v else None

    def block(rs):
        vol = [r for r in rs if r["iou_kind"] == "volume" and not r.get("thin")]
        return dict(n=len(rs), centroid_mm_before=med("centroid_before_mm", rs), centroid_mm_after=med("centroid_offset_pose_mm", rs),
                    msd_mm_before=med("msd_before_mm", rs), msd_mm_after=med("msd_pose_mm", rs),
                    iou_mirror_median=med("iou_before", vol or rs), iou_pose_median=med("iou_pose", vol or rs), iou_icp_median=med("iou_icp", vol or rs), n_iou_volume=len(vol),
                    iou_ge_06_before=sum(1 for r in vol if (r["iou_before"] or 0) >= IOU_MIN), iou_ge_06_after=sum(1 for r in vol if (r["iou_pose"] or 0) >= IOU_MIN),
                    iou_ge_06_icp=sum(1 for r in vol if (r["iou_icp"] or 0) >= IOU_MIN))
    out = dict(all=block(rows), muscle=block([r for r in rows if r["sys"] == "muscle"]))
    for sy in sorted({r["sys"] for r in rows}):
        out["sys_" + sy] = block([r for r in rows if r["sys"] == sy])
    # classification of every pair
    cls = {"symmetric_already": 0, "explained_by_pose": 0, "anatomical_size": 0, "residual_shape_or_position": 0, "thin_or_not_assessable": 0}
    lists = {k: [] for k in cls}
    for r in rows:
        ratio = r["ratio"]
        size_off = ratio is not None and (ratio < RATIO_LO or ratio > RATIO_HI)
        vol_ok = r["iou_kind"] == "volume" and not r.get("thin")
        if size_off:
            k = "anatomical_size"
        elif not vol_ok and r["iou_pose"] is None:
            k = "thin_or_not_assessable"
        else:
            b, a = (r["iou_before"] or 0), (r["iou_pose"] or 0)
            if not vol_ok:
                b, a = (r["iou_before"] or 0), (r["iou_pose"] or 0)
            if b >= IOU_MIN:
                k = "symmetric_already"
            elif a >= IOU_MIN:
                k = "explained_by_pose"
            else:
                k = "residual_shape_or_position"
        cls[k] += 1
        if len(lists[k]) < 400:
            lists[k].append(dict(sys=r["sys"], canon=r["canon"], ratio=ratio, iou_before=r["iou_before"], iou_pose=r["iou_pose"], iou_icp=r["iou_icp"], centroid_before_mm=r["centroid_before_mm"], centroid_after_mm=r["centroid_offset_pose_mm"]))
    out["classification"] = cls
    return out, lists


def verdict(rows, trunk, pel, key):
    exceed = []
    for r in rows:
        thr = A.GROUP_THR.get(r["group"], 5.0)
        if r["dof"] in A.ROT_DOFS:
            thr *= 1.6
        if r["group"] in ("fingers", "toes"):
            continue                                              # judged on the group mean below
        if abs(r["diff"]) > thr:
            exceed.append(dict(joint=r["joint"], dof=r["dof"], diff=r["diff"], tolerance=round(thr, 1)))
    for g in ("fingers", "toes"):
        v = [abs(r["diff"]) for r in rows if r["group"] == g]
        if v and np.mean(v) > A.GROUP_THR[g]:
            exceed.append(dict(joint=g + " (mean of %d joints)" % len(v), dof="flex", diff=round(float(np.mean(v)), 1), tolerance=A.GROUP_THR[g]))
    for t in trunk:
        if t["item"].startswith("vertebra"):
            continue
        thr = A.GROUP_THR["pelvis"] if t["item"].startswith("pelvis") else A.GROUP_THR["head"] if t["item"].startswith("skull") else A.GROUP_THR["spine"]
        for k in ("rotation_deg", "tilt_deg"):
            if abs(t[k]) > thr:
                exceed.append(dict(joint=t["item"], dof=k, diff=t[k], tolerance=thr))
    for reg in ("cervical", "thoracic", "lumbar"):
        vv = [t for t in trunk if t.get("region") == reg and t["item"].startswith("vertebra")]
        if vv:
            for k in ("rotation_deg", "tilt_deg"):
                m = float(np.mean([t[k] for t in vv]))
                if abs(m) > A.GROUP_THR["spine"]:
                    exceed.append(dict(joint="%s spine mean" % reg, dof=k, diff=round(m, 1), tolerance=A.GROUP_THR["spine"]))
    for k in ("obliquity_deg", "rotation_deg"):
        if abs(pel[k]) > A.GROUP_THR["pelvis"]:
            exceed.append(dict(joint="pelvis vs trunk", dof=k, diff=pel[k], tolerance=A.GROUP_THR["pelvis"]))
    return exceed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", default=",".join(MD.KEYS))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--no-tissue", action="store_true")
    ap.add_argument("-o", default=str(OUT))
    a = ap.parse_args()
    res = {}
    if Path(a.o).exists():
        res = json.load(open(a.o)).get("pages", {})
    for key in a.pages.split(","):
        t0 = time.time()
        M, RB, rig, rows, trunk, pel = A.run_angles(key)
        sr = A.segment_registration(M, RB)
        segs = [dict(seg=RB.segs[i]["id"], rot_deg=round(d["rot_deg"], 1), trans_mm=round(d["trans_mm"], 1), residual_mm=round(d["med_mm"], 2), n=d["n"]) for i, d in sr.items()]
        # joint-relative (child vs parent) difference of the bone-registration rotations
        rel = []
        for i, d in sr.items():
            sg = RB.segs[i]
            if sg["side"] != "l" or sg["par"] not in sr:
                continue
            Rp = sr[sg["par"]]["T"][:3, :3]; Rc = d["T"][:3, :3]
            rel.append(dict(seg=sg["id"], parent=RB.segs[sg["par"]]["id"], joint_diff_deg=round(rot_angle(Rp.T @ Rc), 1)))
        pj = json.load(open(MD.REPO / "data/derived/Q237_pairing.json"))["pages"][key]
        bone_msd = [u["metrics"]["msd_mm"] for u in pj["units"] if u["cls"] == "paired" and u["sys"] == "bone" and u.get("metrics") and u["metrics"].get("msd_mm") is not None]
        ex = verdict(rows, trunk, pel, key)
        entry = dict(label=MD.LABEL[key], plane=dict(n=[round(float(x), 5) for x in M.plane.n], d_mm=round(M.plane.d, 2)), pelvis_vs_trunk=pel, angles=rows, trunk=trunk, segment_registration=segs, joint_registration=rel,
                     bone_pairs_median_msd_mm=round(float(np.median(bone_msd)), 2), bone_pairs_p95_msd_mm=round(float(np.percentile(bone_msd, 95)), 2), exceed=ex,
                     rig_notes={k: v for k, v in RB.info.items() if not k.startswith("asis")}, landmark_errors={k: v["err"] for k, v in RB.K.notes.items() if v.get("err")})
        if not a.no_tissue:
            trows, info = A.tissue(key, M, RB, jobs=a.jobs)
            summ, lists = summarise_tissue(trows)
            entry.update(tissue=summ, tissue_lists=lists, tissue_rows=trows, tissue_run=info)
        if a.no_tissue and key in res:
            for k in ("tissue", "tissue_lists", "tissue_rows", "tissue_run"):
                if k in res[key]:
                    entry[k] = res[key][k]
        res[key] = entry
        print(key, "exceed:", len(ex), "seconds", round(time.time() - t0), flush=True)
        Path(a.o).write_text(json.dumps(dict(generated=datetime.date.today().isoformat(), thresholds=dict(group_deg=A.GROUP_THR, rotation_factor=1.6, iou_min=IOU_MIN, ratio=[RATIO_LO, RATIO_HI]), pages=res), separators=(",", ":"), default=float))


if __name__ == "__main__":
    main()
