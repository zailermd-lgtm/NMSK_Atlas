#!/usr/bin/env python3
"""Q224: top defects of the OWN pages from the Q223 audit -> new own bundles (his Q217 -> build/viewer_m_hr_q224, her Q216 -> build/viewer_f_hr_q224).

    python3 scripts/transfer/q224_fix.py --body m|f --phase stage1      veins (q224_veins) + duplicate bone meshes (q224_dups)  -> SCRATCH/stage1_<body>  + stage-1 report
    python3 scripts/transfer/q224_muscles.py --body m|f --src SCRATCH/stage1_<body>   [--shard i/n]   (per-muscle cache)
    python3 scripts/transfer/q224_fix.py --body m|f --phase final       stage 1 + the accepted muscles (final-state overlap check) -> build/viewer_<body>_hr_q224, data/derived/Q224_report_<body>.json

Everything the report does not list stays byte for byte (checked by q224_vertex_diff.py, by position: ids are duplicated in the male bundle).  Source class: the vein entries get a procedural badge that STARTS with
'Rule-based bridge' (the viewer's classify() then puts the entry in 'Rule-based on this body's data'; an `xfer` subject keeps 'Transferred'); muscles / bones keep their subject and class."""
from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402
from scripts.transfer import q216_common as C216  # noqa: E402
from scripts.transfer import q224_veins as V  # noqa: E402
from scripts.transfer import q224_dups as D  # noqa: E402
from scripts.transfer.q224_common import BODIES, SCRATCH, jdump, DERIVED  # noqa: E402

VEINS = {"m": ["femoral_v_r", "femoral_v_l", "internal_jugular_v_r", "internal_jugular_v_l"], "f": ["internal_jugular_v_r", "internal_jugular_v_l"]}
TARGET_TRACE_MIN_MM = 0.5
VEIN_EXTRA = {("m", "femoral_v_r"): "Checked on his 1 mm cryosection photographs (data/derived/Q224_photo_check_femoral_v_r.png): the stump sections at y -34 and y -100 sit on the clotted vessel, between them the bridge runs through the neurovascular bundle of the adductor canal; the Q174 tracker found no usable lumen in y -36..-97, so nothing there is measured."}


def position(B, sid):
    i = B.find(sid)
    assert len(i) == 1, (sid, i)
    return i[0]


def replace_at(B, k, v, f, badge=None, prepend=False):
    it = B.items[k]
    B._set(it, v, f)
    if badge:
        old = it["e"]["rec"].get("procedural_badge")
        it["e"]["rec"] = {**it["e"]["rec"], "procedural_badge": ((badge + " " + (old or "")) if prepend else ((old or "") + " " + badge)).strip()}


def vein_badge(name, info, subject="", extra=""):
    links = info["links"]
    gaps = "; ".join(f"{l['nearest_vertex_gap_mm']} mm gap, bridge {l['new_part_mm']} mm long (centreline {l['centreline_mm']} mm), radius {l['radius_mm']['start']} -> {l['radius_mm']['end']} mm" for l in links)
    tails = sum(info.get("tails_removed_mm3", {}).values())
    return (f"Rule-based bridge (Q224, NOT measured): the Q223 audit found this vein in {len(info['pieces'])} separate pieces (the label / tracked outline stops, the gaps are not anatomical). The measured stumps are joined: "
            f"{gaps}. Method: a smooth centreline (cubic Hermite from stump to stump, leaving each stump along its own direction"
            f"{', routed around bone' if any(l.get('bone_route') for l in links) else ''}), an elliptical section that morphs from the one stump's section to the other's (calibre continuous at both ends), "
            f"embedded 2.5 mm into each stump; the rounded tips of the stumps (label / tracker end caps, {tails / 1000.0:.2f} cm3) are replaced by the bridge, {len(info['specks'])} label speck(s) (<= 17 vertices, a few mm3, no lumen) that were separate pieces were dropped (listed in data/derived/Q224_report). "
            f"Bridge volume {info['volume_mm3']['bridge_new'] / 1000.0:.2f} cm3 of {info['volume_mm3']['result'] / 1000.0:.2f} cm3; the measured surface elsewhere moves <= {info['old_to_new_mm']['max_outside_bridge']} mm "
            f"(p95 {info['old_to_new_mm']['p95_outside_bridge']} mm, re-meshing). Inside the skin and clear of bone (guards). "
            + (f"The vein itself is the other Visible Human's, carried onto this body (subject {subject}: Source class stays Transferred). " if str(subject).startswith("xfer") else "")
            + (extra + " " if extra else "") + "Rule-based interpolation, not a segmentation.")


def stage1(body):
    cfg = BODIES[body]
    t0 = time.time()
    B = Bundle(cfg["src_bundle"])
    n0 = len(B.items)
    ctx = F.Context(B)
    tree, _names = C216.bone_surface_tree(B)
    log = lambda *x: print(*x, flush=True)
    rep = dict(body=body, label=cfg["label"], source=str(cfg["src_bundle"].relative_to(REPO)), veins={}, duplicates={}, removed=[], replaced=[])
    for sid in VEINS[body]:
        k = position(B, sid)
        g = B.get(sid)
        log(f"vein {sid}")
        v1, f1, info = V.bridge_vein(sid, g["v"], g["f"], ctx, tree, log)
        info.pop("_bridges", None)
        rep["veins"][sid] = info
        if v1 is None:
            log(f"   NOT bridged: {info['why']}")
            continue
        replace_at(B, k, v1, f1, vein_badge(g["e"]["rec"].get("name", sid), info, g["e"]["subject"], VEIN_EXTRA.get((body, sid), "")), prepend=True)
        rep["replaced"].append(sid)
        log(f"   bridged: {[ (l['nearest_vertex_gap_mm'], l['new_part_mm']) for l in info['links']]} mm, pieces {len(info['pieces'])} -> 1")
    removals = []
    if body == "f":
        for side in ("r", "l"):
            r = D.female_composite(B, side, log)
            rep["duplicates"][f"tarsals_{side}"] = r
            log(f"dup tarsals_{side}: remove={r['remove']}  {r['reason']}")
            if r["remove"]:
                removals.append(f"tarsals_{side}")
    else:
        for side in ("r", "l"):
            r = D.male_carpals(B, side, log)
            rep["duplicates"][f"carpals_{side}"] = r
            log(f"dup carpals_{side}: remove={r['remove']}  {r['reason']}")
            if r["remove"]:
                removals.append(f"carpals_{side}")
        for sid in ("cuneiform_medial_l", "cuneiform_intermediate_l"):
            v1, f1, inf = D.trim_by(B, sid, "metatarsals_l", log=log, min_vol=0.75)
            rep["duplicates"][sid] = inf
            log(f"trim {sid}: {inf}")
            if v1 is not None:
                txt = (f"Q224: trimmed by his CT-label metatarsal mesh `metatarsals_l` (subject ct_vhm_foot), which it overlapped by {inf['overlap_volume_cm3']} cm3 (up to 7 mm, Q223 bone-pair check): the CT label wins, this bone (DU release shape) "
                       f"loses the overlapping volume ({inf['volume_cm3'][0]} -> {inf['volume_cm3'][1]} cm3, x{inf['volume_ratio']}) and is re-meshed (exact 0.5 mm voxel boolean + 0.2 mm clearance). Source class unchanged.")
                replace_at(B, position(B, sid), v1, f1, txt)
                rep["replaced"].append(sid)
    for sid in removals:
        k = position(B, sid)
        e = B.items[k]["e"]
        rep["removed"].append(dict(id=sid, subject=e["subject"], nv=e["nv"], nf=e["nf"], hidden_default=bool(e.get("hidden_default")), reason=rep["duplicates"][sid]["reason"]))
        del B.items[k]
    out = SCRATCH / f"stage1_{body}"
    B.write(out)
    rep["entries"] = [n0, len(B.items)]
    rep["triangles"] = B.j["triangles"] if False else int(sum(it["e"]["nf"] for it in B.items))
    jdump(rep, SCRATCH / f"stage1_{body}_report.json")
    log(f"stage 1 written: {out}, entries {n0} -> {len(B.items)}  [{time.time() - t0:.0f} s]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["m", "f"])
    ap.add_argument("--phase", required=True, choices=["stage1", "final"])
    a = ap.parse_args()
    if a.phase == "stage1":
        stage1(a.body)
    else:
        from scripts.transfer import q224_final
        q224_final.final(a.body)


if __name__ == "__main__":
    main()
