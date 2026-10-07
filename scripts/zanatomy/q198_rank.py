#!/usr/bin/env python3
"""Q198 aggregator (READ-ONLY): per-model junction JSONs (+ Z-fit seam JSONs) -> data/derived/Q198_anatomy_audit.json
(all numbers + ranked defect list per model, root causes, elbow narrative, left-right symmetry, seams, verdicts)."""
from __future__ import annotations
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
DER = REPO / "data" / "derived"
MODELS = {"own_m": "Own male (VH reconstruction)", "own_f": "Own female (VH reconstruction)", "z_male": "Z-Anatomy male base",
          "z_base_f": "Z generic body, female variant (base)", "z_male_fit": "Z fitted to his reconstruction", "z_female_fit": "Z fitted to her reconstruction"}
BASELINE = {"z_male_fit": "z_male", "z_female_fit": "z_base_f"}
FIT_SEAMS = {"z_male_fit": "Q198_fitseams_z_male_fit.json", "z_female_fit": "Q198_fitseams_z_female_fit.json"}
THRESH = {  # documented in the output
    "bone_gap_mm": [3, 6, 12], "bone_penetration_mm": [3, 5, 10], "carrying_angle_deg_ok_range": [-12, 32], "ulna_twist_deg": [30, 45, 60], "axis_offset_mm": [20, 25, 35],
    "attachment_distance_mm": [6, 10, 20], "flat_cut_cap_mm2": [100, 400], "island_gap_mm": 5, "island_area_share": [0.02, 0.1, 0.3], "axial_gap_mm": [8, 15],
    "outside_skin_pct_with_>5mm_excursion": [5, 15, 35], "inside_bone_pct_with_>3mm_depth": [8, 20, 40], "muscle_overlap_pct": [40, 60], "open_edge_frac": [0.08, 0.2],
    "skin_open_sections": [3, 10], "skin_radius_step_mm_per_3mm": [3, 10], "seam_plane_min_structures": 3, "chain_gap_mm": [5, 12, 25],
    "fit_adjacency_tear_frac_gt5": [0.02, 0.08], "fit_frame_offset_mm": [10, 15, 25]}
STEP = lambda v, th: sum(v > t for t in th)          # number of thresholds exceeded -> severity 0..len
CAUSE_FIX = {
    "ct_block_seam": ("CT block seam: a measured structure is cut flat where its data block ends", "re-segment across the seam from the cryosection photographs / extend the measured structure with Z-Anatomy tendon+origin snapped to the model's own bones"),
    "bone_block_truncation": ("source block does not contain the whole bone (cut at the CT block edge)", "re-measure the missing bone ends from the cryosection photographs, or complete the bone from the Z bone fitted to the surviving part"),
    "registration_mismatch": ("registration mismatch: structure transferred from another body is not tied to this body's own bones", "re-register the structure bone-driven (per-bone similarity + non-rigid refinement, Q194 method) and snap origins/insertions to the bone footprints"),
    "held_unrefined": ("held / unrefined structure: carried rigidly by a coarse transform, forearm/hand not refined", "run the forearm/hand refinement (per-bone chain fit, Q195 hand/forearm queue)"),
    "blend_zone": ("blend zone between two frames (CT frame vs photograph frame) bridged by a long smooth blend", "refit the photographed arm into one frame (bones first, then soft tissue) instead of blending 100 mm"),
    "source_defect": ("source defect: already present in the unfitted Z-Anatomy original", "cannot be fixed by fitting; local mesh repair of the Z object or accept as a known source limitation"),
    "not_modelled": ("structure not modelled in this reconstruction", "add from Z-Anatomy fitted to the bones, or segment from labels"),
    "skin_envelope": ("skin patches torn / removed (envelope not closed)", "close the skin patches (shared-vertex weld after fitting) / re-add the deleted urogenital patches as a female surface"),
    "soft_vs_envelope": ("soft tissue not consistent with skin/bones of the same frame (different sources or frames)", "re-register the soft tissue to the skin/bones of the model; check the frame of each source block"),
}


def sev_name(s):
    return {0: "ok", 1: "minor", 2: "moderate", 3: "major"}[s]


def nrm(i):
    return re.sub(r"^zan_|(_l|_r)$", "", i)


PLURAL = re.compile(r"(nerves|arteries|veins|branches|roots|rami|nodes|vessels|digital|perforating|intercostal|lumbar_arteries|ligaments|bursae|tendons|muscles|plexus)")
EARLARYNX = re.compile(r"tympan|stapes|stapedius|malleus|incus|arytenoid|cricoarytenoid|auric|cochlea|ossicle|tensor_tympani|vocal")


def junction_defects(key, kind, res, fit):
    D = []
    def add(region, side, structure, check, value, unit, sev, detail, src=None, cls=None, extra=None):
        if sev <= 0:
            return
        D.append({"region": region, "side": side, "structure": structure, "check": check, "value": value, "unit": unit, "severity": int(sev), "detail": detail,
                  "src": src, "cls": cls, **(extra or {})})
    for m in res.get("missing_joints", []):
        what = [] if m["proximal_bones_present"] else ["proximal bones"]
        what += [] if m["distal_bones_present"] else ["distal bones"]
        add(m["name"], m["side"], None, "joint_bones_absent", ", ".join(what), "", 3, f"{m['name']} {m['side']}: {' and '.join(what)} absent from the model (not modelled / outside the data block)", extra={"cause": "not_modelled"})
    for j in res["junctions"]:
        jn, sd, R = j["name"], j["side"], j["R"]
        b = j["bones"]
        s = STEP(b["surface_gap_mm"], THRESH["bone_gap_mm"])
        add(jn, sd, None, "bone_gap", b["surface_gap_mm"], "mm", s,
            f"closest approach of the two bone sets {b['surface_gap_mm']} mm (articular surfaces should touch)")
        s = STEP(b["max_penetration_mm"], THRESH["bone_penetration_mm"])
        add(jn, sd, None, "bone_penetration", b["max_penetration_mm"], "mm", s, f"bones interpenetrate up to {b['max_penetration_mm']} mm ({b['penetration_vol_mm3']} mm3)")
        ea = j.get("elbow_angles")
        trunc = any((bd.get("id") or "").startswith(("humerus", "radius", "ulna")) and any(c["dist_to_joint_mm"] <= R + 60 and c["area_mm2"] > 150 for c in (bd.get("flat_caps") or [])) for bd in j.get("bones_detail", []))
        if ea and "error" not in ea and not trunc:
            ca = ea["carrying_deg_lateral_positive"]; lo, hi = THRESH["carrying_angle_deg_ok_range"]
            ex = max(lo - ca, ca - hi, 0)
            add(jn, sd, None, "carrying_angle", ca, "deg", 3 if ex > 25 else 2 if ex > 10 else 1 if ex > 0 else 0, f"carrying angle {ca} deg (physiological about 5-15 deg valgus; tolerated {lo}..{hi})")
            add(jn, sd, None, "ulna_twist", ea["ulna_vs_epicondylar_twist_deg"], "deg", STEP(ea["ulna_vs_epicondylar_twist_deg"], THRESH["ulna_twist_deg"]),
                f"ulna transverse axis vs humeral epicondylar axis differ by {ea['ulna_vs_epicondylar_twist_deg']} deg (axial twist of the forearm bones)")
            add(jn, sd, None, "axis_offset", ea["humerus_forearm_axis_offset_mm"], "mm", STEP(ea["humerus_forearm_axis_offset_mm"], THRESH["axis_offset_mm"]),
                f"upper-arm axis and forearm axis are {ea['humerus_forearm_axis_offset_mm']} mm apart at the joint plane")
            if ea["flexion_deg"] > 140:
                add(jn, sd, None, "flexion", ea["flexion_deg"], "deg", 2, f"flexion {ea['flexion_deg']} deg implausible for a standing specimen")
        sk = j.get("skin") or {}
        if sk and kind == "zan" and jn in ("elbow", "wrist", "knee", "ankle"):
            no = sk.get("open_or_missing_sections", 0)
            add(jn, sd, None, "skin_open_sections", no, "slices of 57", STEP(no, THRESH["skin_open_sections"]) + (1 if no >= 3 else 0), f"skin outline not closed in {no}/57 cross-sections (patches torn apart >2 mm)", extra={"cause": "skin_envelope"})
            st = sk.get("max_radius_step_mm_per_3mm", 0)
            add(jn, sd, None, "skin_step", st, "mm per 3 mm", 3 if st > 10 else 2 if st > 3 else 0, f"skin cross-section radius jumps {st} mm between neighbouring 3 mm slices at t={sk.get('at_t_mm')} mm from the joint", extra={"cause": "skin_envelope"})
        for bd in j.get("bones_detail", []):
            for cp in bd.get("flat_caps") or []:
                if cp["dist_to_joint_mm"] <= R + 60:
                    add(jn, sd, bd["id"], "bone_flat_cut", cp["area_mm2"], "mm2", 3 if cp["area_mm2"] > 500 else 2 if cp["area_mm2"] > 150 else 0,
                        f"bone cut flat in the {cp['axis']}={cp['plane_mm']} plane ({cp['area_mm2']} mm2 cut face, {cp['dist_to_joint_mm']} mm from the joint centre)", bd.get("src"), bd.get("cls"),
                        {"cause": "bone_block_truncation", "plane": f"{cp['axis']}={cp['plane_mm']}"})
            if bd.get("max_island_gap_mm", 0) > 5 and bd.get("main_area_share", 1) < 0.99:
                add(jn, sd, bd["id"], "bone_island", bd["max_island_gap_mm"], "mm", 1, f"bone has a detached piece {bd['max_island_gap_mm']} mm from the main body", bd.get("src"), bd.get("cls"))
        for s_ in j["soft"]:
            if "error" in s_ or s_.get("note"):
                continue
            nm, src, cls = s_["id"], s_.get("src"), s_.get("cls")
            for end, a in (s_.get("attach_ends_in_zone") or {}).items():
                d = a.get("min_expected_bone_mm")
                generic = d is None
                if generic:
                    d = a["min_any_bone_mm"]
                    if a["to_joint_mm"] > 0.7 * R or s_["sys"] not in ("muscle", "joint"):
                        continue
                sv = STEP(d, THRESH["attachment_distance_mm"])
                if generic:
                    sv = min(sv, 2)
                add(jn, sd, nm, "end_detached_from_bone", d, "mm", sv, f"{end} end of {nm} lies {d} mm from {'its expected origin/insertion bone' if not generic else 'the nearest bone'} (end {a['to_joint_mm']} mm from the joint centre)", src, cls)
            for cp in s_.get("flat_caps") or []:
                if cp["dist_to_joint_mm"] <= R + 60:
                    add(jn, sd, nm, "flat_cut_face", cp["area_mm2"], "mm2", 3 if cp["area_mm2"] > THRESH["flat_cut_cap_mm2"][1] else 2 if cp["area_mm2"] > THRESH["flat_cut_cap_mm2"][0] else 0,
                        f"{nm} is cut flat in the {cp['axis']}={cp['plane_mm']} plane (closed cut face {cp['area_mm2']} mm2, {cp['dist_to_joint_mm']} mm from the joint centre)", src, cls,
                        {"plane": f"{cp['axis']}={cp['plane_mm']}"})
            if s_.get("open_edge_frac", 0) > THRESH["open_edge_frac"][0] and s_["sys"] in ("muscle",):
                add(jn, sd, nm, "ragged_open_boundary", s_["open_edge_frac"], "frac of edges", 2 if s_["open_edge_frac"] > THRESH["open_edge_frac"][1] else 1, f"{nm}: {s_['open_edges']} open boundary edges ({100*s_['open_edge_frac']:.1f}% of edges; {s_['open_loops_in_zone']} loops in zone)", src, cls)
            if s_["sys"] in ("muscle", "tendon") and 5 < s_.get("max_island_gap_mm", 0) <= 60 and s_.get("max_island_share_gt5mm", 0) > THRESH["island_area_share"][0] and not PLURAL.search(nm):
                add(jn, sd, nm, "disconnected_island", s_["max_island_share_gt5mm"], "area share", STEP(s_["max_island_share_gt5mm"], THRESH["island_area_share"]),
                    f"{nm}: detached piece with {100*s_['max_island_share_gt5mm']:.1f}% of its area, {s_['max_island_gap_mm']} mm from the main belly", src, cls)
            if s_["sys"] in ("muscle", "tendon") and s_.get("max_axial_gap_mm", 0) > THRESH["axial_gap_mm"][0] and s_.get("max_axial_gap_mm", 0) < 150:
                add(jn, sd, nm, "axial_gap", s_["max_axial_gap_mm"], "mm", STEP(s_["max_axial_gap_mm"], THRESH["axial_gap_mm"]), f"{nm}: empty stretch {s_['max_axial_gap_mm']} mm along its axis", src, cls)
            o, ox = s_.get("outside_skin_pct", 0), s_.get("outside_skin_max_mm", 0)
            if ox > 5:
                add(jn, sd, nm, "outside_skin", o, "% of vertices", STEP(o, THRESH["outside_skin_pct_with_>5mm_excursion"]), f"{o}% of {nm} lies outside the skin (up to {ox} mm)", src, cls, {"cause_hint": "soft_vs_envelope"})
            ib, ibx = s_.get("inside_bone_pct", 0), s_.get("inside_bone_max_mm", 0)
            if ibx > 3 and s_["sys"] in ("muscle", "tendon") and not EARLARYNX.search(nm):
                add(jn, sd, nm, "inside_bone", ib, "% of vertices", STEP(ib, THRESH["inside_bone_pct_with_>3mm_depth"]), f"{ib}% of {nm} inside bone (up to {ibx} mm)", src, cls)
        for nm, ov in (j.get("muscle_overlap") or {}).items():
            if isinstance(ov, dict) and ov.get("overlap_pct", 0) > THRESH["muscle_overlap_pct"][0] and ov.get("vol_cm3", 0) > 3:
                add(jn, sd, nm, "muscle_interpenetration", ov["overlap_pct"], "% of volume", 2 if ov["overlap_pct"] > THRESH["muscle_overlap_pct"][1] else 1, f"{ov['overlap_pct']}% of {nm} ({ov['vol_cm3']} cm3) lies inside other muscles")
        for t in j["tubes"]:
            if "error" in t or not t.get("near_zone"):
                continue
            nm = t["id"]
            if 5 < t.get("max_island_gap_mm", 0) <= 150 and not PLURAL.search(nm):
                add(jn, sd, nm, "tube_gap", t["max_island_gap_mm"], "mm", STEP(t["max_island_gap_mm"], [5, 12, 25]), f"{nm}: separate pieces {t['max_island_gap_mm']} mm apart (not continuous)", t.get("src"), t.get("cls"))
            o, ox = t.get("outside_skin_pct", 0), t.get("outside_skin_max_mm", 0)
            if ox > 5 and o > 5:
                add(jn, sd, nm, "outside_skin", o, "% of vertices", STEP(o, THRESH["outside_skin_pct_with_>5mm_excursion"]), f"{o}% of {nm} lies outside the skin (up to {ox} mm)", t.get("src"), t.get("cls"), {"cause_hint": "soft_vs_envelope"})
            ib, ibx = t.get("inside_bone_pct", 0), t.get("inside_bone_max_mm", 0)
            if ibx > 3 and ib > 8 and not EARLARYNX.search(nm) and jn in ("shoulder", "elbow", "wrist", "hip", "knee", "ankle") and not PLURAL.search(nm):
                add(jn, sd, nm, "inside_bone", ib, "% of vertices", STEP(ib, THRESH["inside_bone_pct_with_>3mm_depth"]), f"{ib}% of {nm} inside bone (up to {ibx} mm)", t.get("src"), t.get("cls"))
        for c in j.get("chains") or []:
            if "min_surface_vertex_mm" not in c:
                continue
            gp = c["min_surface_vertex_mm"]
            add(jn, sd, c["child"], "chain_gap", gp, "mm", min(STEP(gp, THRESH["chain_gap_mm"]), 2 if "_n_" in c["child"] or "nerve" in c["child"] or c["child"].endswith("_n_l") or c["child"].endswith("_n_r") else 3), f"{c['parent']} -> {c['child']}: the two vessel/nerve meshes are {gp} mm apart (end-to-end {c.get('end_to_end_mm')} mm)")
    # seams (global)
    for sp in res.get("seam_planes", []):
        add("seam", None, None, "block_seam_plane", sp["n_structures"], "structures cut in one plane", 3 if sp["total_area_mm2"] > 3000 else 2,
            f"{sp['n_structures']} structures ({', '.join(sp['ids'][:6])}...) are cut flat in the plane {sp['axis']}={sp['plane_mm']} (total cut area {sp['total_area_mm2']} mm2, centre {sp['centre_mm']})",
            extra={"cause": "ct_block_seam", "plane": f"{sp['axis']}={sp['plane_mm']}", "centre_mm": sp["centre_mm"]})
    # fit seams
    if fit:
        for fj in fit["junctions"]:
            jn, sd = fj["name"], fj["side"]
            if fj.get("adjacent_pairs", 0) > 50:
                fr = fj.get("frac_gt5", 0)
                add(jn, sd, None, "adjacency_tear", fr, "frac of base-adjacent pairs >5 mm apart", STEP(fr, THRESH["fit_adjacency_tear_frac_gt5"]) + (1 if fj.get("tear_max_mm", 0) > 20 and fr > 0.02 else 0),
                    f"{100*fr:.1f}% of structure pairs that touch in the Z base are >5 mm apart after fitting (max {fj.get('tear_max_mm')} mm); worst: " + "; ".join(f"{w['a']}|{w['b']} {w['max_tear_mm']}mm" for w in fj.get("worst_pairs", [])[:3]),
                    extra={"cause_hint": "registration_mismatch", "fit": True})
            for o in fj.get("structure_frame_offsets", []):
                if o["frame_offset_mm"] > THRESH["fit_frame_offset_mm"][0]:
                    add(jn, sd, o["id"], "frame_offset", o["frame_offset_mm"], "mm", STEP(o["frame_offset_mm"], THRESH["fit_frame_offset_mm"]),
                        f"{o['id']} sits in a different frame from the {jn} bones: the joint centre maps {o['frame_offset_mm']} mm from where the nearest bone ({o['nearest_bone_frame']}) puts it (rotation difference {o['rot_vs_bone_deg']} deg)",
                        extra={"cause_hint": "registration_mismatch", "fit": True})
    return D


def assign_cause(key, kind, d, base_idx, byid_src):
    """root-cause group for one defect"""
    if d.get("cause"):
        return d["cause"]
    chk = d["check"]; reg = d["region"]; sd = d.get("side"); src = (d.get("src") or "") + " " + str(d.get("cls") or "")
    if kind == "zan":
        if key in ("z_male", "z_base_f"):
            return "source_defect"
        k = (reg, sd, d.get("structure"), chk)
        bv = base_idx.get(k)
        if bv is not None and bv >= 0.6 * float(d["value"] if isinstance(d["value"], (int, float)) else 0):
            return "source_defect"
        if d.get("fit"):
            return "registration_mismatch"
        if key == "z_male_fit" and reg in ("elbow", "wrist") and d.get("structure") and re.search(r"forearm|carpi|digit|pollicis|flexor|extensor|pronator|supinator|interosse|radial|ulnar|median|hand|palm", d["structure"]):
            return "held_unrefined"
        if key == "z_female_fit" and sd == "l" and reg in ("elbow", "shoulder", "wrist"):
            return "blend_zone"
        if d.get("cause_hint"):
            return d["cause_hint"]
        return "registration_mismatch"
    # own models
    if "filled" in src or "transferred" in src or "xfer" in src:
        return "registration_mismatch"
    if chk in ("bone_gap", "bone_penetration", "carrying_angle", "ulna_twist", "axis_offset"):
        return "bone_block_truncation" if chk == "bone_gap" else "registration_mismatch"
    if chk in ("flat_cut_face",):
        return "ct_block_seam"
    if d.get("cause_hint"):
        return d["cause_hint"]
    return "registration_mismatch"


def build_model(key, kind, res, fit, base_res):
    D = junction_defects(key, kind, res, fit)
    # presence vs Z reference (own models only): structures the Z base has in each junction zone but the model lacks
    absent = []
    if kind == "own" and base_res:
        for bj in base_res["junctions"]:
            mj = next((j for j in res["junctions"] if j["name"] == bj["name"] and j["side"] == bj["side"]), None)
            if not mj:
                continue
            have = {nrm(i) for i in mj["zone_ids"]}
            miss = defaultdict(list)
            for i in bj["zone_ids"]:
                n = nrm(i)
                if n in have or any((n in h or h in n) for h in have if len(h) > 6 and len(n) > 6):
                    continue
                sysn = "vessel" if re.search(r"artery|vein|_a$|_v$|_a_|_v_|arter|vena|venous", n) else "nerve" if re.search(r"nerve|_n$|_n_", n) else "muscle" if re.search(r"muscle|ceps|brachi|flexor|extensor|pronator|supinator|abductor|adductor|glute|gastroc|soleus|tibialis|peroneus|fibularis|psoas|iliacus|quadriceps|vastus|rectus|sartorius|gracilis|pectineus|semi|trapezius|deltoid|supraspinatus|infraspinatus|teres|subscapularis|latissimus|rhomboid|levator|scalene|sternocleido" , n) else "other"
                miss[sysn].append(n)
            if any(miss.values()):
                absent.append({"junction": bj["name"], "side": bj["side"], "absent_by_kind": {k: sorted(set(v)) for k, v in miss.items()}})
                nv, nn, nm = len(set(miss.get("vessel", []))), len(set(miss.get("nerve", []))), len(set(miss.get("muscle", [])))
                if bj["name"] in ("elbow", "shoulder", "wrist", "knee", "hip", "ankle"):
                    sv = 2 if (nv + nn >= 6 or nm >= 4) else 1
                    D.append({"region": bj["name"], "side": bj["side"], "structure": None, "check": "structures_not_modelled", "value": nv + nn + nm, "unit": "structures", "severity": sv,
                              "detail": f"{bj['name']} {bj['side']}: the Z reference has {nv} vessels, {nn} nerves, {nm} muscles in this zone that the model does not contain", "src": None, "cls": None, "cause": "not_modelled"})
    base_idx = {}
    if base_res:
        for d in junction_defects(BASELINE_KEY[key], "zan", base_res, None) if key in BASELINE_KEY else []:
            base_idx[(d["region"], d.get("side"), d.get("structure"), d["check"])] = float(d["value"]) if isinstance(d["value"], (int, float)) else 0.0
    for d in D:
        d["cause"] = assign_cause(key, kind, d, base_idx, None)
        d["cause_text"] = CAUSE_FIX[d["cause"]][0]; d["fix_approach"] = CAUSE_FIX[d["cause"]][1]
        d["in_unfitted_base"] = bool(d["cause"] == "source_defect" and key in BASELINE_KEY)
    # dedupe (same structure + check + plane): keep the worst
    best = {}
    for d in D:
        k = (d.get("structure"), d["check"], d.get("plane"), d["region"] if d.get("structure") is None else None, d.get("side"))
        if k not in best or (d["severity"], float(d["value"]) if isinstance(d["value"], (int, float)) else 0) > (best[k]["severity"], float(best[k]["value"]) if isinstance(best[k]["value"], (int, float)) else 0):
            best[k] = d
    D = list(best.values())
    D.sort(key=lambda d: (-d["severity"], d["cause"] == "source_defect", -(float(d["value"]) if isinstance(d["value"], (int, float)) else 0)))
    for n, d in enumerate(D, 1):
        d["rank"] = n
    return D, absent


BASELINE_KEY = {"z_male_fit": "z_male", "z_female_fit": "z_base_f"}


def sym_report(res):
    """left-right symmetry of each paired junction + mirrored-structure comparison"""
    out = []
    by = defaultdict(dict)
    for j in res["junctions"]:
        by[j["name"]][j["side"]] = j
    for name, d in by.items():
        if "l" not in d or "r" not in d:
            out.append({"junction": name, "note": "only one side present: " + ",".join(d)})
            continue
        L, Rr = d["l"], d["r"]
        r = {"junction": name, "bone_gap_l_r_mm": [L["bones"]["surface_gap_mm"], Rr["bones"]["surface_gap_mm"]], "bone_penetration_l_r_mm": [L["bones"]["max_penetration_mm"], Rr["bones"]["max_penetration_mm"]]}
        if name == "elbow":
            la, ra = L.get("elbow_angles") or {}, Rr.get("elbow_angles") or {}
            for k in ("flexion_deg", "carrying_deg_lateral_positive", "ulna_vs_epicondylar_twist_deg", "humerus_forearm_axis_offset_mm"):
                if k in la and k in ra:
                    r[k + "_l_r"] = [la[k], ra[k]]
        # mirrored structures: same normalised id; compare attachment distance / outside-skin / flat caps
        def idx(j):
            return {nrm(s["id"]): s for s in j["soft"] if "error" not in s}
        li, ri = idx(L), idx(Rr)
        asym = []
        for n in set(li) & set(ri):
            a, b = li[n], ri[n]
            def att(s):
                v = [x.get("min_expected_bone_mm", x["min_any_bone_mm"]) for x in (s.get("attach_ends_in_zone") or {}).values()]
                return max(v) if v else None
            fa, fb = (a.get("flat_caps") or []), (b.get("flat_caps") or [])
            row = {"structure": n, "attach_l_r_mm": [att(a), att(b)], "outside_skin_l_r_pct": [a.get("outside_skin_pct"), b.get("outside_skin_pct")], "flat_cut_l_r": [bool(fa), bool(fb)]}
            sl = (att(a) or 0) > 10 or a.get("outside_skin_pct", 0) > 15 or bool(fa)
            sr = (att(b) or 0) > 10 or b.get("outside_skin_pct", 0) > 15 or bool(fb)
            if sl != sr:
                asym.append(row)
        r["asymmetric_defects"] = asym[:25]; r["n_asymmetric_defects"] = len(asym)
        vl, vr = L.get("muscle_overlap") or {}, Rr.get("muscle_overlap") or {}
        vr_ratio = []
        for n in {nrm(k) for k in vl} & {nrm(k) for k in vr}:
            kl = next(k for k in vl if nrm(k) == n); kr = next(k for k in vr if nrm(k) == n)
            if isinstance(vl[kl], dict) and isinstance(vr[kr], dict) and min(vl[kl]["vol_cm3"], vr[kr]["vol_cm3"]) > 5:
                q = vl[kl]["vol_cm3"] / vr[kr]["vol_cm3"]
                if q < 0.6 or q > 1.66:
                    vr_ratio.append({"structure": n, "vol_l_r_cm3": [vl[kl]["vol_cm3"], vr[kr]["vol_cm3"]], "ratio": round(q, 2)})
        r["muscle_volume_asymmetry_outside_0.6_1.66"] = vr_ratio
        out.append(r)
    return out


def elbow_summary(res, D, side):
    j = next((x for x in res["junctions"] if x["name"] == "elbow" and x["side"] == side), None)
    miss = [m for m in res.get("missing_joints", []) if m["name"] == "elbow" and m["side"] == side]
    if j is None:
        return {"side": side, "verdict": "DEFECT", "reason": "elbow bones absent from the model: " + (json.dumps(miss) if miss else "")}
    dd = [d for d in D if d["region"] == "elbow" and d.get("side") == side]
    core = [d for d in dd if d["check"] not in ("chain_gap", "tube_gap")]
    n3, n2 = sum(d["severity"] == 3 for d in core) + sum(d["severity"] == 3 and d["check"] == "chain_gap" for d in dd), sum(d["severity"] == 2 for d in core)
    soft = [s for s in j["soft"] if "error" not in s]
    det = []
    for s in soft:
        for end, a in (s.get("attach_ends_in_zone") or {}).items():
            if "min_expected_bone_mm" in a and a["min_expected_bone_mm"] > 6:
                det.append((s["id"], end, a["min_expected_bone_mm"]))
    caps = [(s["id"], c["axis"] + "=" + str(c["plane_mm"]), c["area_mm2"], c["dist_to_joint_mm"]) for s in soft for c in (s.get("flat_caps") or []) if c["dist_to_joint_mm"] <= j["R"] + 60 and c["area_mm2"] > 100]
    return {"side": side, "verdict": "DEFECT" if (n3 >= 1 or n2 >= 3) else "OK", "n_major": n3, "n_moderate": n2, "n_minor": sum(d["severity"] == 1 for d in dd),
            "bone_gap_mm": j["bones"]["surface_gap_mm"], "bone_penetration_mm": j["bones"]["max_penetration_mm"], "angles": {k: v for k, v in (j.get("elbow_angles") or {}).items() if "axis" not in k},
            "skin": j.get("skin"), "muscles_end_detached_gt6mm": sorted(det, key=lambda x: -x[2])[:12], "flat_cut_muscles": sorted(caps, key=lambda x: -x[2])[:12],
            "n_soft_structures_in_zone": len(soft), "n_tubes_in_zone": sum(1 for t in j["tubes"] if t.get("near_zone")),
            "chains": j.get("chains"), "bones_detail": [{k: b.get(k) for k in ("id", "src", "flat_caps", "end_prox_mm", "end_dist_mm", "length_mm")} for b in j.get("bones_detail", [])]}


REGION_W = {"elbow": 1.5}
GROUP_OF = {"flat_cut_face": "flat_cut", "bone_flat_cut": "flat_cut", "block_seam_plane": "flat_cut"}


def group_issues(D):
    G = {}
    for d in D:
        grp = GROUP_OF.get(d["check"], d["check"])
        key = (d["region"] if d["check"] != "block_seam_plane" else "seam", d.get("side") if d["check"] != "block_seam_plane" else None, grp, d.get("plane") if grp == "flat_cut" else None,
               d.get("structure") if grp in ("flat_cut",) and not d.get("plane") else None)
        G.setdefault(key, []).append(d)
    out = []
    for (reg, sd, grp, plane, _), ms in G.items():
        sv = max(m["severity"] for m in ms)
        score = sum(m["severity"] ** 2 for m in ms) * REGION_W.get(reg, 1.0)
        cc = Counter(m["cause"] for m in ms).most_common(1)[0][0]
        top = max(ms, key=lambda m: (m["severity"], float(m["value"]) if isinstance(m["value"], (int, float)) else 0))
        structs = []
        for m in ms:
            if m.get("structure") and m["structure"] not in structs:
                structs.append(m["structure"])
        out.append({"region": reg, "side": sd, "check": grp, "plane": plane, "severity": sv, "score": round(score, 1), "n_members": len(ms), "structures": structs[:14], "cause": cc,
                    "cause_text": CAUSE_FIX[cc][0], "fix_approach": CAUSE_FIX[cc][1], "headline": top["detail"] + (f"  (+{len(ms)-1} more of the same kind)" if len(ms) > 1 else ""),
                    "worst_value": top["value"], "unit": top["unit"]})
    out.sort(key=lambda g: (-g["severity"], -g["score"]))
    for n, g in enumerate(out, 1):
        g["rank"] = n
    return out


def elbow_statement(key, side, res, D):
    """plain-language, number-driven statement of what is wrong (or not) at one elbow"""
    sn = "left" if side == "l" else "right"
    j = next((x for x in res["junctions"] if x["name"] == "elbow" and x["side"] == side), None)
    miss = [m for m in res.get("missing_joints", []) if m["name"] == "elbow" and m["side"] == side]
    if j is None:
        return f"{sn} elbow: the radius, ulna, carpals and hand bones are not in the model at all (only the humerus and the arm muscles reach the elbow), so no elbow joint exists. Verdict DEFECT."
    dd = [d for d in D if d["region"] == "elbow" and d.get("side") == side]
    parts = []
    b = j["bones"]
    trunc = [bd for bd in j.get("bones_detail", []) if any(c["dist_to_joint_mm"] <= j["R"] + 60 and c["area_mm2"] > 150 for c in (bd.get("flat_caps") or []))]
    if trunc:
        parts.append("bones cut flat at a data-block edge: " + ", ".join(sorted({bd["id"] for bd in trunc})) + f" (planes {', '.join(sorted({c['axis']+'='+str(c['plane_mm']) for bd in trunc for c in bd['flat_caps'] if c['area_mm2']>150}))})")
    if b["surface_gap_mm"] > 3:
        parts.append(f"bones not articulated: closest approach {b['surface_gap_mm']} mm")
    if b["max_penetration_mm"] > 3:
        parts.append(f"bones interpenetrate {b['max_penetration_mm']} mm")
    ea = j.get("elbow_angles") or {}
    if ea and "error" not in ea and not trunc:
        if ea["ulna_vs_epicondylar_twist_deg"] > 30:
            parts.append(f"forearm bones twisted {ea['ulna_vs_epicondylar_twist_deg']} deg about the shaft relative to the humeral epicondylar axis")
        if not (-12 <= ea["carrying_deg_lateral_positive"] <= 32):
            parts.append(f"forearm leaves the hinge plane by {ea['carrying_deg_lateral_positive']} deg")
    fl = [d for d in dd if d["check"] == "flat_cut_face" and d["severity"] >= 2]
    if fl:
        parts.append(f"{len({d['structure'] for d in fl})} muscles cut flat ({', '.join(sorted({d['structure'] for d in fl})[:6])}; planes {', '.join(sorted({d.get('plane','') for d in fl})[:4])})")
    det = sorted([d for d in dd if d["check"] == "end_detached_from_bone" and d["severity"] >= 1], key=lambda d: -float(d["value"]))
    if det:
        parts.append(f"{len(det)} muscle/ligament ends detached from their bone (worst {det[0]['structure']} {det[0]['value']} mm)")
    isl = [d for d in dd if d["check"] in ("disconnected_island", "axial_gap")]
    if isl:
        parts.append(f"{len(isl)} muscles with disconnected pieces / empty stretches")
    ch = [d for d in dd if d["check"] in ("chain_gap", "tube_gap") and d["severity"] >= 2]
    if ch:
        parts.append(f"{len(ch)} vessel/nerve continuity gaps (worst {max(float(d['value']) for d in ch)} mm)")
    sk = [d for d in dd if d["check"] in ("skin_open_sections", "skin_step") and d["severity"] >= 2]
    if sk:
        parts.append("skin torn / stepped: " + "; ".join(d["detail"] for d in sk[:2]))
    osk = [d for d in dd if d["check"] == "outside_skin" and d["severity"] >= 2]
    if osk:
        parts.append(f"{len(osk)} structures partly outside the skin (worst {max(float(d['value']) for d in osk)}%)")
    ibn = [d for d in dd if d["check"] == "inside_bone" and d["severity"] >= 2]
    if ibn:
        parts.append(f"{len(ibn)} structures inside bone")
    ov = [d for d in dd if d["check"] == "muscle_interpenetration" and d["severity"] >= 2]
    if ov:
        parts.append(f"{len(ov)} muscles buried >{THRESH['muscle_overlap_pct'][1]}% inside other muscles (transferred / Z-filled muscles do not tile)")
    nm = [d for d in dd if d["check"] == "structures_not_modelled"]
    if nm:
        parts.append(nm[0]["detail"])
    if not parts:
        return f"{sn} elbow: no moderate or major defect found (bones articulate, muscle ends reach their bones, vessels/nerves continuous, skin closed)."
    return f"{sn} elbow: " + "; ".join(parts) + "."


def verdict(D, elbows):
    n3 = sum(d["severity"] == 3 and d["cause"] != "source_defect" for d in D); n2 = sum(d["severity"] == 2 and d["cause"] != "source_defect" for d in D)
    if n3 == 0 and n2 <= 4:
        return "yes"
    if n3 <= 4 and not all(e["verdict"] == "DEFECT" for e in elbows):
        return "partly"
    return "no" if n3 > 12 else "partly"


def main():
    out = {"meta": {"task": "Q198 read-only anatomy continuity / in-place audit of the six q197 pages", "thresholds": THRESH, "cause_groups": {k: {"text": v[0], "fix": v[1]} for k, v in CAUSE_FIX.items()}, "models": MODELS}, "models": {}}
    R = {}
    for k in MODELS:
        p = DER / f"Q198_model_{k}.json"
        if p.exists():
            R[k] = json.loads(p.read_text())
    for k, res in R.items():
        kind = res["kind"]
        fit = json.loads((DER / FIT_SEAMS[k]).read_text()) if k in FIT_SEAMS and (DER / FIT_SEAMS[k]).exists() else None
        base_res = R.get(BASELINE_KEY.get(k)) if k in BASELINE_KEY else (R.get("z_male") if kind == "own" else None)
        D, absent = build_model(k, kind, res, fit, base_res)
        # female variants: the two deleted skin patches
        if k in ("z_base_f", "z_female_fit"):
            D.append({"rank": len(D) + 1, "severity": 2, "region": "perineum", "side": "m", "structure": "zan_skin_urogenital_region_l/r", "check": "skin_patches_deleted", "value": 2, "unit": "patches",
                      "detail": "the two urogenital skin patches of Z-Anatomy were deleted for the female variant (Q196): the skin envelope is open between the thighs (no replacement surface)", "src": None, "cls": None,
                      "cause": "skin_envelope", "cause_text": CAUSE_FIX["skin_envelope"][0], "fix_approach": CAUSE_FIX["skin_envelope"][1], "in_unfitted_base": k == "z_female_fit"})
        el = [elbow_summary(res, D, s) for s in ("l", "r")]
        for e_ in el:
            e_["statement"] = elbow_statement(k, e_["side"], res, D)
        D.sort(key=lambda d: (-d["severity"], d["cause"] == "source_defect"))
        for n, d in enumerate(D, 1):
            d["rank"] = n
        cnt = Counter(d["severity"] for d in D); cg = Counter(d["cause"] for d in D if d["severity"] >= 2)
        jt = []
        for j in res["junctions"]:
            dd = [d for d in D if d["region"] == j["name"] and d.get("side") == j["side"]]
            jt.append({"junction": j["name"], "side": j["side"], "bone_gap_mm": j["bones"]["surface_gap_mm"], "bone_penetration_mm": j["bones"]["max_penetration_mm"],
                       "n_major": sum(d["severity"] == 3 for d in dd), "n_moderate": sum(d["severity"] == 2 for d in dd), "n_minor": sum(d["severity"] == 1 for d in dd),
                       "skin": j.get("skin") or None})
        out["models"][k] = {"label": MODELS[k], "kind": kind, "n_structures": res["n_structures"], "skin_volume_L": res["skin_volume_L"], "missing_joints": res["missing_joints"],
                            "severity_counts": {"major": cnt[3], "moderate": cnt[2], "minor": cnt[1]}, "cause_groups_sev_ge2": dict(cg),
                            "verdict_continuous_and_in_place": verdict(D, el), "elbow": {e["side"]: e for e in el}, "junction_table": jt, "seams": res.get("seam_planes", []),
                            "symmetry": sym_report(res), "absent_vs_z_reference": absent, "issues": group_issues(D), "defects": D,
                            "skin_mesh": res.get("skin_mesh"),
                            "fit_vs_base": ({"coverage": fit["coverage_by_system"], "matched_structures": fit["matched_structures"]} if fit else None)}
    (DER / "Q198_anatomy_audit.json").write_text(json.dumps(out, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))
    for k, m in out["models"].items():
        print(k, m["verdict_continuous_and_in_place"], m["severity_counts"], {s: e["verdict"] for s, e in m["elbow"].items()}, m["cause_groups_sev_ge2"])


if __name__ == "__main__":
    main()
