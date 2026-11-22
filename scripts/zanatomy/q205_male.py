#!/usr/bin/env python3
"""Q205: the Z-Anatomy model fitted to the VISIBLE HUMAN MALE -- hands (per-bone chain fit on his CT + photographs, soft tissue re-carried), wrist, shoulders (follow the Q201 humerus),
metadata (card names / atlas facts), skin welds.  In-process patch of the published Q202 page (no full build): the Q201 full-resolution state (build/q201/after_q201.npz) is the starting
point of the structures that move, every other structure of the page is copied byte for byte.

    python3 scripts/zanatomy/q205_male.py [--out build/q205/viewer_zan_vhm] [--steps hands,shoulder,skin] [--state build/q201/after_q201.npz]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
STEM = "atlas_viewer_zan_male_fitted"
SRC_PAGE = REPO / "build" / "q202" / "viewer_zan_vhm"
BASE_PAGE = (REPO / "build" / "q197" / "viewer_zan_atlas", "atlas_viewer_zan_atlas")
TUBE_CLOSE = (25.0, 25.0, 35.0)


def load_all(state):
    from scripts.zanatomy import body_ctx
    body_ctx.configure("vhm")
    from scripts.zanatomy import q190_metrics as Mx
    L = Mx.load_dump(state)
    by = {d["id"]: {"v": d["v"].copy(), "f": d["f"], "cat": d["cat"], "r": d["r"]} for d in L}
    raw = {i: d["r"] for i, d in by.items()}
    return by, raw


def hands(by, raw, ctx, log=print):
    from scripts.zanatomy import q205_hand as Q5
    from scripts.zanatomy import q191_hand as H191
    from scripts.zanatomy import q199_elbow as E
    skin, skin_tree, skin_vn, regions, his = ctx["skin"], ctx["skin_tree"], ctx["skin_vn"], ctx["regions"], ctx["his"]
    out = {}
    for side in ("r", "l"):
        z = np.load(REPO / "data" / "derived" / f"Q205_hand_bones_{side}.npz")
        bone_v = {k[2:]: z[k].astype(float) for k in z.files}
        fit = json.loads((REPO / "data" / "derived" / f"Q205_hand_fit_{side}.json").read_text())
        v_before = {i: by[i]["v"].copy() for i in by if i.endswith("_" + side) or ("_" + side + "_") in i}
        rep = Q5.refine_soft(by, raw, side, bone_v, skin, skin_tree, skin_vn, regions, his, log=log)
        ids = list(rep["structures"])
        for i in ids:
            if by[i]["cat"] != "bone":
                by[i]["fit_note"] = (by[i].get("fit_note") or "") + Q5.hand_note(i, rep["structures"][i])
        # continuity of the hand zone: pairs that touch in the Z source and are further apart now (Q199 closure, vessel / nerve steps 25 mm), then the inside-skin clamp
        s = "_" + side
        hb = [b for b in bone_v] + ["radius" + s, "ulna" + s]
        zb = [H191.Inside(by[b]["v"], by[b]["f"]) for b in hb]
        hc = np.vstack([raw[b] for b in bone_v if "metacarpal" in b]).mean(0)
        v_field = {i: by[i]["v"].copy() for i in by if i in v_before}
        cont = E.close_gaps(side, by, raw, set(ids) - set(bone_v), skin, skin_tree, zb, np.atleast_2d(hc), v_field, log=log, rounds=8, tube_close=TUBE_CLOSE)
        for i in by:
            if i in ids and by[i]["cat"] not in ("bone", "skin", "ligament", "bursa", "cartilage") and i not in bone_v:
                v1 = by[i]["v"]
                v2 = E.cap_to(H191.clamp_inside_skin(v1.copy(), by[i]["f"], np.ones(len(v1), bool), skin, skin_tree), v1, 12.0)
                if not np.array_equal(v1, v2):
                    by[i]["v"] = v2
        for b in bone_v:
            m = np.linalg.norm(by[b]["v"] - v_before[b], axis=1)
            fr = fit["evidence_after"]["hand"]
            by[b]["fit_note"] = (by[b].get("fit_note") or "") + (
                f" Q205: this {'left' if side == 'l' else 'right'} hand bone re-fitted on HIS evidence as part of a per-bone chain (frozen CT bone voxels HU >= 250 for the torso block, the label volume below y = 34 for the fingers; "
                f"checked on his full-resolution cryosection photographs): the hand = the Z-source arrangement on his forearm, carpals + metacarpals turned about the wrist ({fit['hand_block']['turn_deg']} deg, global search), "
                f"each ray as hinge / articulated chain, the thumb re-seated on its metacarpal (Q195 left the thumb phalanges {fit['reseat_thumb']['gap_before_mm']} mm from it) and searched over CMC / MCP / IP. "
                f"Mean move {m.mean():.1f} mm, max {m.max():.1f} mm. Hand-bone evidence agreement (share of his bone voxels within 1.5 mm of a Z hand bone) {fit['evidence_before']['hand']['evidence_within_1.5mm_of_a_Z_bone_pct']} -> "
                f"{fr['evidence_within_1.5mm_of_a_Z_bone_pct']} %; this bone's mean distance to his bone voxels {fit['bone_evidence_score_before'][b[4:]]} -> {fit['bone_evidence_score_after'][b[4:]]} mm.")
        out[side] = {"structures": {k: v for k, v in rep["structures"].items()}, "continuity": {k: v for k, v in cont.items() if k != "rows"}, "bones": sorted(bone_v)}
    return out


def shoulders(by, raw, ctx, before_state, moved_q201, log=print):
    from scripts.zanatomy import q205_shoulder as Sh
    out = {}
    for side in ("l", "r"):
        r = Sh.refine_shoulder(by, raw, before_state["humerus_" + side]["v"], side, ctx["skin"], ctx["skin_tree"], ctx["regions"], ctx["his"], moved_q201, log=log)
        out[side] = {"structures": r["structures"], "continuity": {k: v for k, v in r["continuity"].items() if k != "rows"}, "reverted_outside_skin": r.get("reverted_outside_skin", {})}
    return out


def context():
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.zanatomy import body_ctx
    from scripts.zanatomy import q191_hand as H191
    skin = load_skin("vhm")
    return {"skin": skin, "skin_tree": cKDTree(np.asarray(skin.vertices, float)), "skin_vn": H191.skin_normals(skin), "his": load_her_meshes(),
            "regions": json.loads(body_ctx.REGION_REPORT.read_text())["region_of_structure"]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=str(REPO / "build" / "q201" / "after_q201.npz"))
    ap.add_argument("--before", default=str(REPO / "build" / "q201" / "before_q201.npz"))
    ap.add_argument("--steps", default="hands,shoulder")
    ap.add_argument("--dump", default=str(REPO / "build" / "q205" / "male_state.npz"))
    a = ap.parse_args(argv)
    t0 = time.time()
    by, raw = load_all(a.state)
    from scripts.zanatomy import q190_metrics as Mx
    before = {d["id"]: {"v": d["v"]} for d in Mx.load_dump(a.before)}
    ctx = context()
    v0 = {i: d["v"].copy() for i, d in by.items()}
    moved_q201 = set(json.loads((REPO / "data" / "derived" / "Q201_zan_vhm_q201_build.json").read_text())["q201"]["moved_ids"])
    rep = {}
    steps = a.steps.split(",")
    if "hands" in steps:
        rep["hands"] = hands(by, raw, ctx)
        print("hands done", round(time.time() - t0), flush=True)
    if "shoulder" in steps:
        rep["shoulder"] = shoulders(by, raw, ctx, before, moved_q201)
        print("shoulder done", round(time.time() - t0), flush=True)
    changed = [i for i in by if not np.array_equal(by[i]["v"], v0[i]) or by[i].get("fit_note")]
    arrs = {"ids": np.array(json.dumps(changed)), "notes": np.array(json.dumps({i: by[i].get("fit_note", "") for i in changed})), "report": np.array(json.dumps(rep, default=float))}
    for k, i in enumerate(changed):
        arrs[f"v{k}"] = by[i]["v"].astype(np.float64)
    np.savez(a.dump, **arrs)
    print("changed", len(changed), "->", a.dump, round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
