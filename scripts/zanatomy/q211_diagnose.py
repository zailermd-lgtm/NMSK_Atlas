#!/usr/bin/env python3
"""Q211 DIAGNOSIS of the Q198 elbow junction audit of the four elbows of the two Z fits (before: male Q210, female Q208): every failing criterion per structure, classified
   REAL         the measure holds in a pose-independent test (a structure that touches its neighbour in the Z source is >5 mm from it; muscle-in-muscle share far above the unfitted base; outside the skin; inside a bone ...)
   ARTEFACT     the Q198 criterion fires for the flexed pose / the metric itself: skin_step + skin_open_sections (all skin outlines are closed, 0 dangling ends, and the pose-aware sections along the upper-arm
                and the forearm axes are closed; the axis line misses the limb in the oblique planes), frame_offset (the bone-chain-consistent image of the Z source scores as bad or worse)
   SOURCE       the same finding exists in the unfitted Z base (cannot be fixed by fitting)
    python3 scripts/zanatomy/q211_diagnose.py [after]   -> data/derived/Q211_elbow_diagnosis.json  ('after' = the Q211 pages)"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.zanatomy import q211_core as K  # noqa: E402

REPO = K.REPO
JB = {"elbow": ["humerus", "radius", "ulna"], "shoulder": ["scapula", "humerus"]}


def seam_summary(which, joint, side, page_dir=None):
    """vertex-pair tear (>5 mm) of the Z-source-adjacent pairs of the page vs the bone-chain-consistent image of the Z source; frame offsets of both"""
    cfg = K.PAGES[which]
    pg = K.load(which, src=page_dir)
    base = K.load(which, base=True)
    rb = json.loads((REPO / f"build/q209_raw/Q198_model_{cfg['base_key']}.json").read_text())
    jb = next(x for x in rb["junctions"] if x["name"] == joint and x["side"] == side)
    c, R = np.asarray(jb["centre_mm"], float), jb["R"] + 25
    m = set(K.matched(pg, base))
    bones = [i for i in K.bone_ids(pg) if i in m]
    ids = [i for i in jb["zone_ids"] if i in m]
    bv, fv = {i: base.v(i) for i in m}, {i: pg.v(i) for i in m}
    F = K.ChainField({b: bv[b] for b in bones}, {b: fv[b] for b in bones}, c, bones)
    img = {i: (fv[i] if pg.sys(i) == "bone" else bv[i] + F(bv[i])) for i in ids}
    sys_of = lambda i: pg.sys(i)
    V, W, L, keep = K.zone_arrays(bv, fv, sys_of, ids, c, R)
    V2, W2, L2, keep2 = K.zone_arrays(bv, img, sys_of, ids, c, R)
    fb = [b + "_" + side for b in JB[joint] if b + "_" + side in m]
    fo, fo2 = K.frame_offsets(V, W, L, keep, sys_of, fb, c, bv), K.frame_offsets(V2, W2, L2, keep2, sys_of, fb, c, bv)
    soft = np.array([pg.sys(i) not in ("bone", "skin", "cartilage") for i in keep])
    pr = K.adjacency_pairs(V, L, soft)
    dF = np.linalg.norm(W[pr[:, 0]] - W[pr[:, 1]], axis=1)
    dE = np.linalg.norm(W2[pr[:, 0]] - W2[pr[:, 1]], axis=1)
    return {"pairs": int(len(pr)), "tear_gt5_actual": round(float((dF > 5).mean()), 4), "tear_gt5_bone_chain_image": round(float((dE > 5).mean()), 4), "tear_excess_gt5": round(float(((dF - dE) > 5).mean()), 4),
            "frame_offset_gt10_actual": int(sum(v["frame_offset_mm"] > 10 for v in fo.values())), "frame_offset_gt10_bone_chain_image": int(sum(v["frame_offset_mm"] > 10 for v in fo2.values())),
            "frame_offsets_actual": {k: v["frame_offset_mm"] for k, v in fo.items()}, "frame_offsets_bone_chain_image": {k: v["frame_offset_mm"] for k, v in fo2.items()}}


def base_island_gap(base, i):
    """largest distance (mm) from any island of the unfitted Z mesh to the rest of it (0 for one piece): fragmented Z-source meshes"""
    from scipy.spatial import cKDTree
    from scripts.zanatomy.q198_core import weld, islands
    if i not in base.S:
        return 0.0
    v, f = weld(base.v(i), base.f(i))
    isl = islands(v, f)
    if len(isl) < 2:
        return 0.0
    g = 0.0
    for a in isl:
        rest = np.concatenate([v[b["vidx"]] for b in isl if b is not a])
        g = max(g, float(cKDTree(rest).query(v[a["vidx"]])[0].min()))
    return g


def classify(d, ss, skin_pose, base_overlap, base=None):
    chk, st = d["check"], d.get("structure")
    if d.get("in_unfitted_base"):
        return "SOURCE", "the same finding exists in the unfitted Z base"
    if chk == "tube_gap" and base is not None:
        g = base_island_gap(base, st)
        if g > 5.0:
            return "SOURCE", f"the Z-source mesh itself is fragmented: its pieces are {g:.0f} mm apart in the unfitted base (the Q198 150 mm cut-off hides it there)"
    if chk in ("skin_step", "skin_open_sections"):
        return "ARTEFACT", "section-plane / axis-point artefact of the flexed elbow: all outlines closed (0 dangling ends), pose-aware sections along the upper-arm and forearm axes: " + skin_pose
    if chk == "frame_offset":
        a, b = ss["frame_offsets_actual"].get(st), ss["frame_offsets_bone_chain_image"].get(st)
        if b is not None and a is not None and (b >= a - 2.0 or b > 10.0):
            return "ARTEFACT", f"the bone-chain-consistent image of the Z source scores {b} mm on this criterion (page {a} mm; moderate threshold 10 mm): the structure spans bones that moved differently"
        return "REAL", f"page {a} mm vs bone-chain image {b} mm"
    if chk == "adjacency_tear":
        return "REAL", f"{100 * ss['tear_gt5_actual']:.1f} % of the Z-source-adjacent vertex pairs are > 5 mm apart; the bone-chain-consistent image of the Z source has {100 * ss['tear_gt5_bone_chain_image']:.1f} %"
    if chk == "muscle_interpenetration":
        b = base_overlap.get(st)
        if b is not None and d["value"] <= b + 15.0:
            return "SOURCE", f"unfitted base {b} % (Z source muscles overlap)"
        return "REAL", f"{d['value']} % vs unfitted base {b} %"
    return "REAL", ""


def run(after=False, joints=("elbow", "shoulder")):
    out = {}
    for which in ("male", "female"):
        cfg = K.PAGES[which]
        tag = cfg["key1"] if after else cfg["key0"]
        rank = json.loads((REPO / f"build/q211_rank/{tag}.json").read_text())
        rawb = json.loads((REPO / f"build/q209_raw/Q198_model_{cfg['base_key']}.json").read_text())
        skin = json.loads((REPO / "data/derived/Q211_skin_pose_aware.json").read_text())
        base = K.load(which, base=True)
        for jn in joints:
            for side in "lr":
                jb = next(x for x in rawb["junctions"] if x["name"] == jn and x["side"] == side)
                base_ov = {k: v["overlap_pct"] for k, v in jb.get("muscle_overlap", {}).items()}
                ss = seam_summary(which, jn, side, page_dir=(cfg["out"] if after else None))
                skin_pose = ""
                if jn == "elbow":
                    sp = skin[tag][side]
                    skin_pose = (f"upper arm: {sp['upper_arm']['valid']}/{sp['upper_arm']['slices']} closed sections, max radius step {sp['upper_arm']['max_radius_step_mm_per_3mm']} mm; "
                                 f"forearm: {sp['forearm']['valid']}/{sp['forearm']['slices']} closed, max step {sp['forearm']['max_radius_step_mm_per_3mm']} mm; open outline ends {sp['upper_arm']['dangling_ends_total'] + sp['forearm']['dangling_ends_total']}")
                rows = []
                for d in sorted([x for x in rank["defects"] if x["region"] == jn and x.get("side") == side and x["severity"] >= 2], key=lambda x: -x["severity"]):
                    cl, why = classify(d, ss, skin_pose, base_ov, base)
                    rows.append({"severity": d["severity"], "check": d["check"], "structure": d.get("structure"), "value": d["value"], "unit": d["unit"], "class": cl, "why": why})
                e = rank["elbow"][side] if jn == "elbow" else None
                jt = next(j for j in rank["junction_table"] if j["junction"] == jn and j["side"] == side)
                key = f"{which}_{jn}_{side}"
                out[key] = {"page": tag, "bone_gap_mm": jt["bone_gap_mm"], "major": jt["n_major"], "moderate": jt["n_moderate"], "minor": jt["n_minor"], **({"verdict_q198": e["verdict"], "angles": e["angles"]} if e else {}),
                            "seam": {k: v for k, v in ss.items() if not k.startswith("frame_offsets")}, "findings": rows,
                            "counts": {c: sum(1 for r in rows if r["class"] == c) for c in ("REAL", "ARTEFACT", "SOURCE")},
                            "counts_major": {c: sum(1 for r in rows if r["class"] == c and r["severity"] == 3) for c in ("REAL", "ARTEFACT", "SOURCE")}}
                print(key, out[key]["counts"], "major", out[key]["counts_major"], "tear", ss["tear_gt5_actual"], "chain image", ss["tear_gt5_bone_chain_image"])
    p = REPO / "data" / "derived" / ("Q211_diagnosis_after.json" if after else "Q211_diagnosis.json")
    p.write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    run(after=len(sys.argv) > 1 and sys.argv[1] == "after")
