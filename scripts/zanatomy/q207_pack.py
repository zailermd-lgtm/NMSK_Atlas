#!/usr/bin/env python3
"""Q207 pack stage: the changed skin patches are re-packed into the published Q206 page (everything else byte for byte), every changed card carries its before -> after numbers; the female page gets the
clinical_* files copied unchanged except clinical_risk.json (the main session regenerates it).   python3 scripts/zanatomy/q207_pack.py male|female"""
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
from scripts.zanatomy import q207_core as C  # noqa: E402
from scripts.zanatomy import q207_build as B  # noqa: E402

SIDE_NAME = {"l": "left", "r": "right"}


def zone_sentence(rep, side, who):
    z = rep["zone"][side]
    a, b = z["before"], z["after"]
    parts = []
    ca, cb = a["classes"], b["classes"]
    bn_a, bn_b = a["bones"], b["bones"]
    nb = len(bn_a)
    worst_a = max(bn_a.items(), key=lambda kv: kv[1]["audit_max_mm"])
    worst_b = max(bn_b.items(), key=lambda kv: kv[1]["audit_max_mm"])
    parts.append(f"hand / wrist / forearm bones with > 5 % of their vertices more than 3 mm outside the skin {ca['bone']['audit_gt5pct']} -> {cb['bone']['audit_gt5pct']} of {nb} (largest overhang {worst_a[1]['audit_max_mm']} mm [{worst_a[0].replace('zan_', '')}] -> {worst_b[1]['audit_max_mm']} mm [{worst_b[0].replace('zan_', '')}]; on the 1 mm envelope the share of bone vertices outside > 0.5 mm {ca['bone']['fine_mean_gt0.5_pct']} -> {cb['bone']['fine_mean_gt0.5_pct']} % on average)")
    soft_a = sum(ca[c]["audit_gt5pct"] for c in ("vessel", "nerve", "joint", "bursa") if c in ca)
    soft_b = sum(cb[c]["audit_gt5pct"] for c in ("vessel", "nerve", "joint", "bursa") if c in cb)
    soft_n = sum(ca[c]["structures"] for c in ("vessel", "nerve", "joint", "bursa") if c in ca)
    fa = sum(ca[c]["fine_gt5pct"] for c in ("vessel", "nerve", "joint", "bursa") if c in ca)
    fb = sum(cb[c]["fine_gt5pct"] for c in ("vessel", "nerve", "joint", "bursa") if c in cb)
    parts.append(f"vessels / nerves / ligaments / sheaths with > 5 % outside {soft_a} -> {soft_b} of {soft_n} (1 mm envelope {fa} -> {fb})")
    return "; ".join(parts)


def note_wrap(i, rep, which):
    side = i[-1]
    mp = rep["moved_patches"][i]
    who = "his" if which == "male" else "her"
    t0, t1 = mp["thickness_median_mm"]
    er = mp.get("edge_ratio_p5_p95")
    own = mp.get("outside_own_skin_gt2mm_pct")
    s = (f" Q207: the evidence-fit {SIDE_NAME[side]} wrist / hand bones and soft tissue had come to lie outside this skin (the Z skin is thinner than the evidence bones), so the patch was cleared outward locally: "
         f"a bone-anchored displacement field, outward along the skin normal only, each vertex raised just enough for the faces around it to clear every structure poking out (class margin 0.3-0.5 mm), "
         f"mean move {mp['mean_move_mm']} mm over the patch, max {mp['max_move_mm']} mm ({mp['moved_vertices_gt0.3mm']} of {mp['vertices']} vertices moved > 0.3 mm); both sheets of the slab move together "
         f"(median thickness {t0} -> {t1} mm); ")
    if er:
        s += f"edge-length ratio to the Z source p5 / p95 {er[0][0]} / {er[0][1]} -> {er[1][0]} / {er[1][1]}; "
    if own:
        s += f"stays inside {who} own CT / cryosection skin (vertices > 2 mm outside it {own[0]} -> {own[1]} %); "
    s += f"seam step to the neighbouring patches (max) {mp['seam_step_max_mm'][0]} -> {mp['seam_step_max_mm'][1]} mm. Zone result on this page ({SIDE_NAME[side]} side): {zone_sentence(rep, side, who)}. Rule-based, nothing invented; no structure was moved."
    return s


def note_uro(i, rep):
    u = rep["urogenital"]
    k = i[-1]
    v0, v1, vs = u["volume_mm3"][k]
    xb, xa = u["across_midline_plane_mm_before"], u["across_midline_plane_mm_after"]
    mp = rep["moved_patches"][i]
    return (f" Q207: this male-only urogenital patch (scrotal bag and perineal strip, left and right half) had been volume-distorted by the per-patch fit (volume {v0} mm3 against {vs} mm3 in the Z source) and its two halves overlapped across the midline "
            f"(the left half reached {xb['l_reaches_into_r_side']} mm and the right half {xb['r_reaches_into_l_side']} mm across the midline plane -> {xa['l_reaches_into_r_side']} / {xa['r_reaches_into_l_side']} mm). Refit to the Z source: every vertex is the source vertex placed by ONE similarity transform shared by both halves (rotation + translation + scale {u.get('scale', '')}, the scale chosen so that each half has the source volume) plus a smooth "
            f"harmonic residual that pulls the border and contact vertices onto the welded positions of the neighbouring skin patches (anal, hypogastric, inguinal, femoral triangle, thigh; these do not move); the seam vertices of the two halves and the strip / bag contact vertices are one node, so the halves meet along the midline. "
            f"Volume {v0} -> {v1} mm3 (source {vs} mm3); mean move {mp['mean_move_mm']} mm, max {mp['max_move_mm']} mm. Nothing invented.")


def note_nail(i, rep, nd):
    mp = rep["moved_patches"][i]
    er = mp.get("edge_ratio_p5_p95")
    t0, t1 = mp["thickness_median_mm"]
    s = (f" Q207: this overlay patch lies on the dorsal digit skin; after the earlier hand re-fits {nd['degenerate_edge_share'][0] * 100:.1f} % of its edges had collapsed to < 0.05 mm (Z source 0 %). The collapsed part ({nd.get('vertices_reseated', '')} of {nd.get('vertices', '')} vertices: the vertices of the collapsed edges and two rings of neighbours) was re-seated on the cleared dorsal digit sheet: "
         f"each such vertex keeps its source place relative to that sheet (face, barycentric position, offset along the face normal) and is recomputed from the sheet's current position, the other vertices follow the sheet's movement: collapsed edges {nd['degenerate_edge_share'][0] * 100:.1f} -> {nd['degenerate_edge_share'][1] * 100:.1f} %")
    if er:
        s += f", edge-length ratio to the Z source p5 / p95 {er[0][0]} / {er[0][1]} -> {er[1][0]} / {er[1][1]}"
    s += f", median thickness {t0} -> {t1} mm; mean move {mp['mean_move_mm']} mm, max {mp['max_move_mm']} mm. Rule-based, nothing invented."
    return s


def note_seam(i, rep, mv):
    items = rep["contacts_true_gap"]
    before = [x for x in items["before"] if i[9:] in (x["A"], x["B"])]
    after = [x for x in items["after"] if i[9:] in (x["A"], x["B"])]
    b = max([x["true_gap"] for x in before] or [0])
    a = max([x["true_gap"] for x in after] or [0])
    return (f" Q207: contact weld. A vertex of this patch (or of its neighbour) that touches the surface of the neighbouring patch in the Z source had been left {b} mm away from it by the per-patch fits; "
            f"one sparse least-squares solve (contact gaps + shared-border welds + smoothness over the slab + minimal movement) closed it: largest remaining true gap {b} -> {a} mm; this patch mean move {mv['mean_mm']} mm, max {mv['max_mm']} mm. Rule-based, nothing invented.")


def run(which, out=None, log=print):
    cfg = C.PAGES[which]
    out = Path(out or cfg["out"])
    pg = C.Page(which)
    rep = pickle.load(open(B.state_path(which, "report"), "rb"))
    Vw, _ = pickle.load(open(B.state_path(which, "wrap"), "rb"))
    Vu, ur = pickle.load(open(B.state_path(which, "uro"), "rb"))
    Vn, nr = pickle.load(open(B.state_path(which, "nails"), "rb"))
    V1, sr = pickle.load(open(B.state_path(which, "seams"), "rb"))
    nails = nr.get("nails", {})
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    if which == "male":
        rep["urogenital"]["scale"] = ur.get("scale")
    replace = {}
    stages = {}
    for i in sorted(rep["moved_patches"]):
        ent = pg.S[i]["m"]
        rec = dict(ent.get("rec") or {})
        badge = rec.get("procedural_badge") or ""
        notes = []
        st = []
        if i in nails:
            notes.append(note_nail(i, rep, nails[i])); st.append("overlay re-seated")
        elif np.linalg.norm(Vw[i] - V0[i], axis=1).max() > 0.05:
            notes.append(note_wrap(i, rep, which)); st.append("clearing")
        if which == "male" and i in ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r"):
            notes.append(note_uro(i, rep)); st.append("urogenital refit")
        if i in sr.get("moved", {}):
            notes.append(note_seam(i, rep, sr["moved"][i])); st.append("contact weld")
        if not notes:      # moved only through the other stages' tail (should not happen)
            notes.append(f" Q207: moved {rep['moved_patches'][i]['max_move_mm']} mm (max) by the skin repair of this task."); st.append("other")
        rec["procedural_badge"] = (badge + "".join(notes)).strip()
        replace[i] = (V1[i], pg.f(i), rec)
        stages[i] = st
    man2, blob2 = P5.save_page(out, cfg["stem"], pg.man, pg.blob, replace=replace)
    if which == "female":
        for f in (REPO / "build" / "q206" / "viewer_zan_female").glob("clinical_*"):
            if f.name == "clinical_risk.json":
                continue
            shutil.copy2(f, out / f.name)
    r = SD.diff(cfg["src"], out, cfg["stem"], sorted(replace))
    r["listed_structures"] = len(replace)
    r["stages"] = stages
    full = {i: rep["moved_patches"][i]["max_move_mm"] for i in replace}
    for i, x in r["geometry_changed"].items():
        x["max_move_mm"] = full.get(i)
    (REPO / "data" / "derived" / f"Q207_ship_diff_{which}.json").write_text(json.dumps(r, indent=1))
    log(f"[{which}] page {out}: replaced {len(replace)} skin patches; ship diff: " + str({k: (len(v) if hasattr(v, '__len__') else v) for k, v in r.items() if k != 'stages'}))
    return r


if __name__ == "__main__":
    run(sys.argv[1])
