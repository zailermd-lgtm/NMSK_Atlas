#!/usr/bin/env python3
"""Q208 pack stage: the changed skin patches are re-packed into the published Q207 page (everything else byte for byte), every changed card carries its before -> after numbers; the female page gets the
clinical_* files copied UNCHANGED from build/q207/viewer_zan_female (including clinical_risk.json).   python3 scripts/zanatomy/q208_pack.py male|female"""
from __future__ import annotations

import json
import pickle
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.zanatomy import q208_core as K  # noqa: E402

SIDE = {"l": "left", "r": "right"}


def f2(x):
    return f"{x[0]} -> {x[1]}"


def note_tube(i, m, tr, who):
    side = SIDE[i[-1]]
    r = tr["roll"] if tr else {}
    er = m["edge_ratio_p5_p95"]
    return (f" Q208: the earlier fits had collapsed and self-crossed the {side} forearm / wrist skin slabs (median slab thickness {f2(m['thickness_median_mm'])} mm, thinnest 5 % {f2(m['thickness_p5_mm'])} mm, "
            f"edge-length ratio to the Z source p5 / p95 {er[0][0]} / {er[0][1]} -> {er[1][0]} / {er[1][1]}, largest {f2(m['edge_ratio_max'])}). This patch was re-warped from the Z source patch, not stretched: "
            f"its vertices are written in cylindrical coordinates (position along the forearm, angle, radius) about the radius / ulna bone-pair axis of the Z source and re-placed at the same coordinates about {who} fitted bone pair "
            f"(position by the bone correspondences; roll corrected by {r.get('roll_elbow_deg', '?')} deg at the elbow end and {r.get('roll_wrist_deg', '?')} deg at the wrist end so that the slab meets the fixed arm and hand skin); "
            f"the outer sheet lies on {who} own CT / cryosection skin (1 mm inside it), the inner sheet keeps the source twin offset of 3 mm in the local cylindrical frame; vertices that two patches share in the source are one position function (welds kept); "
            f"the rim at the hand skin is pulled onto it (harmonic decay). Numbers for this patch: vertex move mean {m['mean_move_mm']} mm, max {m['max_move_mm']} mm; slab twin distance median {f2(m['twin_distance_mm']['median'])} mm; "
            f"vertices > 2 mm outside {who} own skin {f2(m['outside_own_skin_gt2mm_pct'])} %; largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. No structure was moved. Rule-based, nothing invented.")


def note_elbow(i, m, er, who):
    side = SIDE[i[-1]]
    er_ = m["edge_ratio_p5_p95"]
    if er["kept"] == "S":
        how = ("refit between the fixed arm skin and the refitted forearm skin: the outer sheet is laid on the person's own skin (spring relaxation of the source layout with the rim vertices fixed, every node projected onto the own skin 1 mm inside), "
               "the inner sheet is the outer sheet 3 mm behind along the own-skin normals")
        rl = er.get("relief") or {}
        if rl.get("vertices_thinned"):
            how += f"; where the slabs of the crease still cut through each other the inner sheet was thinned ({rl['vertices_thinned']} inner vertices of the {side} elbow, down to {round(rl['min_mm'], 1)} mm)"
    else:
        how = "kept its Q207 shape; the rims that touch the refitted forearm skin follow it (harmonic displacement that decays into the patch), the rims at the arm skin stay"
    return (f" Q208: {side} elbow / cubital slab {how}. Deep face-pair crossings of this elbow's slabs {er['elbow_deep_crossings']}; bone vertices of the elbow region not enclosed by the displayed skin {er['bones_not_enclosed']} (candidate S = laid on the own skin, R = rim-following; kept: {er['kept']}). "
            f"This patch: edge-length ratio to the Z source p5 / p95 {er_[0][0]} / {er_[0][1]} -> {er_[1][0]} / {er_[1][1]}, slab twin distance median {f2(m['twin_distance_mm']['median'])} mm, vertex move mean {m['mean_move_mm']} mm, max {m['max_move_mm']} mm, "
            f"largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. No structure was moved. Rule-based, nothing invented.")


def note_uro(i, m, rep):
    return (f" Q208: urogenital rim weld. After the Q207 refit this male-only patch's rim still disagreed with the fitted anal and thigh patches (vertex steps 4-5 mm, the left | right seam open 7.6 mm at the anal end). "
            f"One sparse least-squares solve over the urogenital, anal, anterior thigh, hypogastric and inguinal patches (shared-border constraints, smoothness over the slab, minimal movement; every other patch that touches them is fixed) closed it: "
            f"largest border step of the whole skin {f2([rep['seams']['q207']['max_step_mm'], rep['seams']['q208']['max_step_mm']])} mm. This patch: vertex move mean {m['mean_move_mm']} mm, max {m['max_move_mm']} mm; largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. "
            f"No structure was moved. Rule-based, nothing invented.")


def note_neighbour(i, m, why):
    return (f" Q208: neighbour weld. This patch moved only where it shares vertices with a Q208 refitted patch ({why}): vertex move mean {m['mean_move_mm']} mm, max {m['max_move_mm']} mm "
            f"({m['vertices_moved_gt0_3mm']} of {m['vertices']} vertices moved > 0.3 mm); largest border step to a neighbour {f2(m['seam_step_max_mm'])} mm. No structure was moved. Rule-based, nothing invented.")


def run(which, out=None, log=print):
    cfg = K.PAGES[which]
    out = Path(out or cfg["out"])
    pg, raw = K.load(which)
    rep = pickle.load(open(K.state_path(which, "report"), "rb"))
    V1 = pickle.load(open(K.state_path(which, "uro"), "rb"))[0]
    tinfo = pickle.load(open(K.state_path(which, "tube"), "rb"))[1]
    einfo = pickle.load(open(K.state_path(which, "elbow"), "rb"))[1]
    who = "his" if which == "male" else "her"
    replace, stages = {}, {}
    for i in sorted(rep["moved"]):
        m = rep["moved"][i]
        n = i[len("zan_skin_"):-2]
        side = i[-1]
        rec = dict(pg.S[i]["m"].get("rec") or {})
        badge = rec.get("procedural_badge") or ""
        if n in K.TUBE:
            note = note_tube(i, m, tinfo.get(side), who)
            st = "forearm / wrist re-warp"
        elif n in K.ELBOW:
            note = note_elbow(i, m, einfo[side], who)
            st = "elbow refit"
        elif i in ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r"):
            note = note_uro(i, m, rep)
            st = "urogenital rim weld"
        else:
            why = "forearm / wrist / elbow skin" if n in K.WRIST_NB + K.ARM_NB else "the urogenital patch"
            note = note_neighbour(i, m, why)
            st = "neighbour weld"
        rec["procedural_badge"] = (badge + note).strip()
        replace[i] = (V1[i], pg.f(i), rec)
        stages[i] = st
    man2, blob2 = P5.save_page(out, cfg["stem"], pg.man, pg.blob, replace=replace)
    if which == "female":
        for f in (REPO / "build" / "q207" / "viewer_zan_female").glob("clinical_*"):
            shutil.copy2(f, out / f.name)
    r = SD.diff(cfg["src"], out, cfg["stem"], sorted(replace))
    r["listed_structures"] = len(replace)
    r["stages"] = stages
    for i, x in r["geometry_changed"].items():
        x["max_move_mm"] = rep["moved"][i]["max_move_mm"] if i in rep["moved"] else None
    (REPO / "data" / "derived" / f"Q208_ship_diff_{which}.json").write_text(json.dumps(r, indent=1))
    log(f"[{which}] page {out}: replaced {len(replace)} skin patches; ship diff: " + str({k: (len(v) if hasattr(v, '__len__') else v) for k, v in r.items() if k != 'stages'}))
    return r


if __name__ == "__main__":
    run(sys.argv[1])
