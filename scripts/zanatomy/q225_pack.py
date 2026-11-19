#!/usr/bin/env python3
"""Q225 pack stage: the changed meshes are re-packed into the Q221 / Q222 source page (everything else byte for byte), every changed card carries its before -> after numbers; ship diff (0 unlisted);
the female page gets the clinical_* files of its source page (regenerated afterwards by scripts/clinical/q225_after.sh).   python3 scripts/zanatomy/q225_pack.py male|female [STATE_STAGE]"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q225_core as K5  # noqa: E402

K5.patch_q211()
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.zanatomy import q211_pack as P11  # noqa: E402
from scripts.zanatomy.q211_build import State  # noqa: E402

WHO = {"male": "his", "female": "her"}


def q25(t):
    return t.replace(" Q211:", " Q225:").replace("Q211 final guard", "Q225 final guard")


def pk(d, k):
    """value of a pair-keyed dict in either order of the pair"""
    if k in d:
        return d[k]
    a, b = k.split("|")
    return d.get(f"{b}|{a}")


def js(t):
    sp = t.get("joint_space_p05_mm")
    return f"penetration {t['max_penetration_mm']} mm, " + (f"joint space {sp} mm" if sp is not None else "no contact patch (bones apart)") + f" (closest clearance {t['min_clearance_mm']} mm)"


def note_bone(L, which):
    b = L["bone_report"]
    who = WHO[which]
    def own(k):
        o = pk(L.get("own_gaps") or {}, k)
        return "" if o is None else f", {who} own meshes {o} mm"
    pairs = "; ".join(f"{k.replace('_', ' ').replace('|', ' | ')}: {js(L['joint_before'][k])} -> {js(L['joint_after'][k])} (joint space on the unfitted base model {pk(L['base_gaps'], k)['joint_space_p05_mm']} mm{own(k)}; target {pk(L.get('targets') or {}, k)} mm)" for k in L["joint_after"])
    fe = ""
    if "fit_error_before_zone_whole" in b:
        zb, wb = b["fit_error_before_zone_whole"]
        za, wa = b["fit_error_after_zone_whole"]
        fe = (f" Fit error to {who} own bone (mean surface distance, this bone -> own / own -> this bone): whole bone {wb[0]} / {wb[1]} -> {wa[0]} / {wa[1]} mm, joint end {zb[0]} / {zb[1]} -> {za[0]} / {za[1]} mm.")
    tp = "" if b["taper_length_share"] > 10 else f", fading to zero at {int(round(100 * b['taper_length_share']))} % of the bone length (the far end is not touched)"
    kind = L["kind"]
    if kind == "elbow_reseat":
        why = (f" Q225: the fit placed the three left-arm bones on {who} evidence one bone at a time, so their joint surfaces were not congruent (the unfitted Z model has a normal joint space). This bone's elbow end was re-seated on the "
               f"humerus (local rigid correction: shift {b['translation_mm']} mm, turn {b['rotation_deg']} deg{tp}; max vertex move {b['max_move_mm']} mm, mean {b['mean_move_mm']} mm; volume x{b['volume_ratio']}). ")
    elif kind == "patella_reseat":
        k0 = next(iter(L["joint_before"]))
        why = (f" Q225: the patella had been fitted to {who} own patella (mean surface distance {b['fit_error_before_zone_whole'][1][0]} mm) while the fitted femur's distal end lies {L.get('femur_offset_mm', '5-8')} mm away from {who} own femur "
               f"(behind it), so the patella floated {L['joint_before'][k0]['min_clearance_mm']} mm in front of the femur (unfitted model: {pk(L['base_gaps'], k0)['joint_space_p05_mm']} mm). It was moved "
               f"back onto the femoral trochlea as one rigid piece (shift {b['translation_mm']} mm, turn {b['rotation_deg']} deg; volume x{b['volume_ratio']}). ")
    else:
        why = (f" Q225: the rib was fitted to {who} rib mass without its attachment: its head stood away from the vertebra it articulates with (unfitted model: in contact). The head end was re-seated on the vertebra "
               f"(local rigid correction: shift {b['translation_mm']} mm, turn {b['rotation_deg']} deg{tp}; max vertex move {b['max_move_mm']} mm; volume x{b['volume_ratio']}). ")
    return why + f"Exact bone-bone check (0.5 mm solid) before -> after: {pairs}." + fe + " Rule-based, nothing invented."


def compose(i, st):
    parts = []
    for L in st.log[i]:
        s = L["stage"]
        sup = L.get("superseded")
        if s == "final":
            parts.append(q25(P11.note_final(L)))
        elif s == "bone":
            parts.append(note_bone(L, st.which))
        elif s == "follow":
            t = P11.note_follow(L, WHO[st.which])
            parts.append(q25(P11.strip_after(t) if sup else t))
        elif s == "zone":
            t = P11.note_zone(L, st.reports["zones"][L["zone"]], i)
            parts.append(q25(P11.strip_after(t) if sup else t))
    return "".join(parts)


def run(which, stage=None, out=None, log=print):
    cfg = K5.PAGES[which]
    stage = stage or "final"
    st = State.load(which, stage)
    out = Path(out or cfg["out"])
    own = K5.own_bones(which)
    from scipy.spatial import cKDTree
    for i in st.V:                                         # distal-femur offset fitted -> own (for the patella card text)
        if i.startswith("patella_"):
            fe = "femur_" + i[-1]
            fv, ov = st.pg.v(fe), own[fe][0]
            fd, od = fv[fv[:, 1] < fv[:, 1].min() + 60], ov[ov[:, 1] < ov[:, 1].min() + 60]
            for L in st.log[i]:
                if L["stage"] == "bone":
                    L["femur_offset_mm"] = round(float(np.linalg.norm(fd.mean(0) - od.mean(0))), 1)
    replace, kinds = {}, {}
    for i, v in st.V.items():
        rec = dict(st.pg.S[i]["m"].get("rec") or {})
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + compose(i, st)).strip()
        replace[i] = (v, st.pg.f(i), rec)
        kinds[i] = [L["stage"] + (":" + L.get("zone", "") if L["stage"] == "zone" else "") for L in st.log[i]]
    man2, blob2 = P5.save_page(out, cfg["stem"], st.pg.man, st.pg.blob, replace=replace)
    r = SD.diff(cfg["src"], out, cfg["stem"], sorted(replace))
    r["listed_structures"] = len(replace)
    r["stages"] = kinds
    over5 = {}
    pn = K5.load(which, src=out)
    for i, x in r["geometry_changed"].items():
        if x["max_vertex_change_mm"] is not None and x["max_vertex_change_mm"] > 5.0:
            d = np.linalg.norm(pn.v(i) - st.pg.v(i), axis=1)
            over5[i] = {"sys": st.pg.sys(i), "max_vertex_change_mm": x["max_vertex_change_mm"], "mean_vertex_change_mm": round(float(d.mean()), 2), "share_of_vertices_over_5mm": round(float((d > 5).mean()), 3)}
    r["moved_over_5mm"] = over5
    over_all = {}
    for i, x in r["geometry_changed"].items():
        d = np.linalg.norm(pn.v(i) - st.pg.v(i), axis=1)
        over_all[i] = {"sys": st.pg.sys(i), "max_mm": round(float(d.max()), 2), "mean_mm": round(float(d.mean()), 2)}
    (REPO / "data" / "derived" / f"Q225_moved_{which}.json").write_text(json.dumps(
        {"note": "structures of the page whose displayed mesh changed between the Q221 / Q222 source page and the Q225 page (max / mean vertex move); muscles -> motor points, vessels / nerves -> risk volumes regenerated by scripts/clinical/q225_after.sh (female page)",
         "over_5mm_by_system": {sy: sorted(((i, v["max_vertex_change_mm"], v["mean_vertex_change_mm"]) for i, v in over5.items() if v["sys"] == sy), key=lambda t: -t[1]) for sy in ("muscle", "vessel", "nerve", "fascia", "joint", "bursa", "cartilage", "bone", "lymph", "viscera", "cns", "insertion", "tendon")},
         "all_changed": over_all}, indent=1))
    (REPO / "data" / "derived" / f"Q225_ship_diff_{which}.json").write_text(json.dumps(r, indent=1))
    if which == "female":
        for f in cfg["src"].glob("clinical_*"):
            shutil.copy2(f, out / f.name)
    log(f"page {out}: replaced {len(replace)} meshes; geometry_changed {len(r['geometry_changed'])}, unlisted {len(r['geometry_changed_but_not_listed'])}, added {len(r['added'])}, removed {len(r['removed'])}, "
        f"card_only {len(r['card_only'])}, unchanged {r['unchanged']}; moved > 5 mm: {len(over5)}")
    return r


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
