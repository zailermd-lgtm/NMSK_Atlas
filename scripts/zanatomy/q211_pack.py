#!/usr/bin/env python3
"""Q211 pack stage: the changed meshes are re-packed into the published page (everything else byte for byte), every changed card carries its before -> after numbers; the female page gets the clinical_* files
copied UNCHANGED from build/q208/viewer_zan_female.   python3 scripts/zanatomy/q211_pack.py male|female [STATE_STAGE]"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.zanatomy import q211_core as K  # noqa: E402
from scripts.zanatomy.q211_build import State  # noqa: E402

WHO = {"male": "his", "female": "her"}
SIDE = {"l": "left", "r": "right"}


def fm(m):
    return (f"outside the displayed skin {m['outside_skin_pct']} % (max {m['outside_skin_max_mm']} mm), inside the displayed bones {m['inside_bone_pct']} % (max {m['inside_bone_max_mm']} mm), "
            f"stretched triangles {m['stretched_pct']} %, folded edges {m['folded_pct']} %")


def note_bone(L, which):
    if L["kind"] == "axial_extension" and which == "male":
        return (f" Q211: the {L.get('nm', 'distal end')} of this bone was too SHORT: the fitted tibia / fibula are {L['own_length'] - L['z_length']:.1f} mm shorter than his own measured bone (proximal ends equal, distal ends "
                f"5.8 mm apart) and the left ankle joint space was 5.8 mm (his own 2.4 mm, the Z source 0.8 mm). The distal part (below 30 % of the length) was displaced along the shaft by up to {L['delta_mm']} mm (smoothstep, the proximal end "
                f"and the knee are untouched; the Z mesh is bent, not replaced). Ankle gap tibia / fibula | talus 5.77 -> 2.22 mm (his own 2.36). Chamfer distance Z -> his bone {L['chamfer_z_to_own'][0]} -> {L['chamfer_z_to_own'][1]} mm, "
                f"his bone -> Z {L['chamfer_own_to_z'][0]} -> {L['chamfer_own_to_z'][1]} mm. Rule-based, nothing invented.")
    return (f" Q211: this vertebra stands for her TWO rib-free lumbar bodies L1 + L1B (Q185k: she has six lumbar vertebrae, the Z source five) but its top stopped {L['gap_t12_l1_mm'][0] - L['gap_t12_l1_mm'][1]:.1f} mm below "
            f"the T12 disc space: T12 | L1 bone gap {L['gap_t12_l1_mm'][0]} mm (her own meshes {L['gap_own_t12_l1_mm']} mm, the Z source 1.1 mm). It was stretched along y about its lower end by up to {L['delta_mm']} mm (linear, "
            f"height {L['height_mm'][0]} -> {L['height_mm'][1]} mm; her L1 + L1B bodies span 63 mm) until the gap equals the L1 | L2 level's: T12 | L1 {L['gap_t12_l1_mm'][0]} -> {L['gap_t12_l1_mm'][1]} mm, "
            f"L1 | L2 {L['gap_l1_l2_mm'][0]} -> {L['gap_l1_l2_mm'][1]} mm; chamfer to her L1 + L1B union Z -> union {L['chamfer_z_to_own_union'][0]} -> {L['chamfer_z_to_own_union'][1]} mm. Rule-based, nothing invented.")


def note_follow(L, who):
    return (f" Q211: followed the moved {' and '.join(L['bones'])} (bone-anchored field of the bone displacement, 6 mm softening, other bones fixed; field up to {L['field_max_mm']} mm here, mean move {L['mean_move_mm']} mm, "
            f"max {L['max_move_mm']} mm). Before -> after: {fm(L['before'])} -> {fm(L['after'])}.")


def note_zone(L, rep, i):
    z = L["zone"]
    jn = z.split("_")[0]
    tb = rep["tear_gt5_by_structure"]
    pb, pa = tb["before"].get(i), tb["after"].get(i)
    return (f" Q211: {jn} junction repair ({z}): structures that touch in the unfitted Z source (vertex pairs <= 2 mm apart) but lay > 5 mm apart on the fitted page were drawn back together by one sparse least-squares "
            f"displacement field over the zone (smooth over each mesh, attachments to bone held, pushed out of the displayed bones / back inside the displayed skin, kept only if not worse). Zone: base-adjacent vertex pairs > 5 mm apart "
            f"{100 * rep['tear_gt5_before']:.1f} -> {100 * rep['tear_gt5_after']:.1f} % ({rep['pairs']} pairs, {rep['moved']} structures moved); this structure's own pairs {pb} -> {pa} (share > 5 mm). "
            f"Mean move {L['mean_move_mm']} mm, max {L['max_move_mm']} mm. Before -> after: {fm(L['before'])} -> {fm(L['after'])}.")


def note_inbone(L):
    return (f" Q211: the fit had left this structure inside a displayed bone (it is not inside bone in the unfitted Z source); pushed out of the displayed bones (guard ladder: tolerance 1-3 mm, volume +-10 %, "
            f"folds and stretch bounded; mean move {L['mean_move_mm']} mm, max {L['max_move_mm']} mm). Before -> after: {fm(L['before'])} -> {fm(L['after'])}.")


def compose(i, st):
    logs = st.log[i]
    parts = []
    for L in logs:
        if L["stage"] == "bone":
            parts.append(note_bone(L, st.which))
        elif L["stage"] == "follow":
            parts.append(note_follow(L, WHO[st.which]))
        elif L["stage"] == "zone":
            parts.append(note_zone(L, st.reports["zones"][L["zone"]], i))
        elif L["stage"] == "inbone":
            parts.append(note_inbone(L))
    return "".join(parts)


def run(which, stage=None, out=None, log=print):
    cfg = K.PAGES[which]
    stage = stage or "final"
    st = State.load(which, stage)
    out = Path(out or cfg["out"])
    replace, kinds = {}, {}
    for i, v in st.V.items():
        rec = dict(st.pg.S[i]["m"].get("rec") or {})
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + compose(i, st)).strip()
        replace[i] = (v, st.pg.f(i), rec)
        kinds[i] = [L["stage"] + (":" + L.get("zone", "") if L["stage"] in ("zone", "inbone") else "") for L in st.log[i]]
    man2, blob2 = P5.save_page(out, cfg["stem"], st.pg.man, st.pg.blob, replace=replace)
    r = SD.diff(cfg["src"], out, cfg["stem"], sorted(replace))
    r["listed_structures"] = len(replace)
    r["stages"] = kinds
    over5 = {}
    for i, x in r["geometry_changed"].items():
        if x["max_vertex_change_mm"] is not None and x["max_vertex_change_mm"] > 5.0:
            over5[i] = {"sys": st.pg.sys(i), "max_vertex_change_mm": x["max_vertex_change_mm"]}
    r["moved_over_5mm"] = over5
    (REPO / "data" / "derived" / f"Q211_ship_diff_{which}.json").write_text(json.dumps(r, indent=1))
    if which == "female":
        for f in cfg["src"].glob("clinical_*"):
            shutil.copy2(f, out / f.name)
    log(f"page {out}: replaced {len(replace)} meshes; geometry_changed {len(r['geometry_changed'])}, unlisted {len(r['geometry_changed_but_not_listed'])}, added {len(r['added'])}, removed {len(r['removed'])}, "
        f"card_only {len(r['card_only'])}, unchanged {r['unchanged']}; moved > 5 mm: {len(over5)}")
    return r


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
