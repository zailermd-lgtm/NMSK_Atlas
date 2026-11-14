#!/usr/bin/env python3
"""Q225 summariser (READ-ONLY): raw Q204 regional rows (build/q225_raw[_merged]/Q204_regions_<key>.json, UNCHANGED Q204 code + Q198 thresholds) -> per page, per 13 regions
(head_neck, shoulder, arm, elbow, forearm, wrist_hand, thorax, abdomen_pelvis, hip, thigh, knee, leg, ankle_foot) counts of findings by severity and TYPE, plus Q209 'before' columns.
Writes data/derived/Q225_audit_<page>.json (compact) and build/q225_agg/candidates.json (all sev>=2 findings with magnitudes, for the top-15 ranking).   python3 scripts/zanatomy/q223_summary.py"""
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q204_regions import structure_defects  # noqa: E402

DER = REPO / "data" / "derived"
KEYS = ["own_m", "own_f", "z_male", "z_base_f", "z_male_fit", "z_female_fit"]
PAGEDIR = {"own_m": "build/q221/viewer_m_hr (bundle build/viewer_m_hr_q217)", "own_f": "build/q222/viewer_f_hr (bundle build/viewer_f_hr_q216)", "z_male_fit": "build/q225_fit/viewer_zan_vhm",
           "z_female_fit": "build/q225_fit/viewer_zan_female", "z_base_f": "build/q222/viewer_base_female", "z_male": "build/q222/viewer_zan_atlas"}
LABEL = {"own_m": "Own male", "own_f": "Own female", "z_male": "Base male (Z-Anatomy)", "z_base_f": "Base female (Z-Anatomy generic)", "z_male_fit": "Z fitted to his reconstruction", "z_female_fit": "Z fitted to her reconstruction"}
REG13 = ["head_neck", "shoulder", "arm", "elbow", "forearm", "wrist_hand", "thorax", "abdomen_pelvis", "hip", "thigh", "knee", "leg", "ankle_foot"]
TYPE = {"bone_gap": "gap", "axial_gap": "gap", "tube_gap": "gap", "disconnected_island": "detached_piece", "bone_island": "detached_piece", "end_off_bone": "detached_end",
        "flat_cut_face": "flat_cut", "bone_flat_cut": "flat_cut", "outside_skin": "outside_skin", "bone_penetration": "bone_penetration", "inside_bone": "soft_in_bone",
        "muscle_interpenetration": "muscle_in_muscle", "ragged_open_boundary": "ragged_boundary"}
TYPES = ["gap", "detached_piece", "detached_end", "flat_cut", "outside_skin", "bone_penetration", "soft_in_bone", "muscle_in_muscle", "ragged_boundary"]
BASE = {"z_male_fit": "z_male", "z_female_fit": "z_base_f", "own_m": "z_male", "own_f": "z_base_f"}
ELBOW_R = 45.0


def reg13(r, jc):
    g = r["region"]
    if g == "ankle" or g == "foot":
        return "ankle_foot"
    if g != "arm_elbow_forearm":
        return g
    sd = r["side"]
    if sd not in ("l", "r"):
        sd = "l" if r["centroid"][0] < 0 else "r"
    try:
        sh, el = np.asarray(jc[f"shoulder_{sd}"]), np.asarray(jc[f"elbow_{sd}"])
    except KeyError:
        return "forearm" if r["centroid"][1] < 0 else "arm"
    c = np.asarray(r["centroid"])
    if np.linalg.norm(c - el) < ELBOW_R:
        return "elbow"
    ax = el - sh; t = float((c - sh) @ ax) / float(ax @ ax)
    return "arm" if t < 1 else "forearm"


def load_rows(k):
    p = REPO / "build" / ("q225_raw_merged" if k.startswith("own") else "q225_raw") / f"Q204_regions_{k}.json"
    R = json.loads(p.read_text())
    for r in R["rows"]:
        r["defects"] = structure_defects(r)
        r["r13"] = reg13(r, R["joint_centres"])
    return R


def norm_id(i):
    i = re.sub(r"_zfill\w*$", "", i); i = re.sub(r"#\d+$", "", i)
    return i[4:] if i.startswith("zan_") else i


def main():
    q209 = json.loads((DER / "Q209_anatomy_audit.json").read_text())
    RAW = {k: load_rows(k) for k in KEYS}
    AG = json.loads((REPO / "build/q225_agg/Q204_anatomy_audit.json").read_text())
    Q = {k: json.loads((REPO / "build" / ("q225_raw_merged" if k.startswith("own") else "q225_raw") / "Q198_anatomy_audit.json").read_text())["models"][k] for k in KEYS}
    QA = {k: json.loads((REPO / "build/q225_raw/Q198_anatomy_audit.json").read_text())["models"][k] for k in KEYS}
    JA, ABS = {}, {}
    for k in KEYS:
        a, q9 = AG["pages"][k]["q198_vs_now"], q209["pages"][k]["q198_vs_now"]
        JA[k] = {"verdict_q209_now": [q9["verdict"][1], a["verdict"][1]], "severity_major_moderate_minor_q209_now": [q9["severity_major_moderate_minor"][1], a["severity_major_moderate_minor"][1]],
                 "elbow_L_R_q209_now": [q9["elbow_L_R"][1], a["elbow_L_R"][1]], "elbow_statement": {sd: Q[k]["elbow"][sd]["statement"] for sd in ("l", "r")},
                 "elbow_counts_major_moderate_minor": {sd: [Q[k]["elbow"][sd]["n_major"], Q[k]["elbow"][sd]["n_moderate"], Q[k]["elbow"][sd]["n_minor"]] for sd in ("l", "r")},
                 "elbow_angles": {sd: Q[k]["elbow"][sd].get("angles") for sd in ("l", "r")}, "cause_groups_sev_ge2": [q9["cause_groups_sev_ge2"][1], a["cause_groups_sev_ge2"][1]],
                 "block_seam_planes_q209_now": [q9["block_seam_planes"][1], a["block_seam_planes"][1]], "missing_joints": a["missing_joints"][1],
                 "junctions": [{"junction": j["junction"], "side": j["side"], "bone_gap_mm_now": j["bone_gap_mm"][1], "bone_penetration_mm_now": j["bone_penetration_mm"][1], "major_moderate_minor_now": j["major_moderate_minor"][1]} for j in a["junctions"]],
                 "top_issues_now": a["top_issues_now"]}
        ABS[k] = [{"junction": f"{x['junction']}_{x['side']}", "absent_by_kind_counts": {kk: len(vv) for kk, vv in x["absent_by_kind"].items()}} for x in QA[k].get("absent_vs_z_reference", [])] if k.startswith("own") else []
    cands = {}
    for k in KEYS:
        R = RAW[k]; rows = R["rows"]
        base_def = set()
        if k in ("z_male_fit", "z_female_fit"):
            for r in RAW[BASE[k]]["rows"]:
                for d in r["defects"]:
                    if d["severity"] >= 2: base_def.add((r["id"], d["check"]))
        reg = {g: {"n_structures": 0, "structures_major_moderate_minor": [0, 0, 0], "findings_by_type": {t: [0, 0, 0] for t in TYPES}} for g in REG13}
        cl = []
        for r in rows:
            e = reg[r["r13"]]; e["n_structures"] += 1
            ms = max([d["severity"] for d in r["defects"]], default=0)
            if ms:
                e["structures_major_moderate_minor"][3 - ms] += 1
            for d in r["defects"]:
                e["findings_by_type"][TYPE[d["check"]]][3 - d["severity"]] += 1
                if d["severity"] >= 2:
                    cl.append({"page": k, "id": r["id"], "sys": r["sys"], "side": r["side"], "region": r["r13"], "check": d["check"], "type": TYPE[d["check"]], "sev": d["severity"], "value": d["value"], "unit": d["unit"],
                               "detail": d["detail"], "centroid_mm": r["centroid"], "vol_cm3": r.get("vol_cm3"), "in_unfitted_base": (r["id"], d["check"]) in base_def, "src": r.get("cls") or r.get("src")})
        cands[k] = cl
        # missing expected neighbours: structures present in the matching Z base (same sys, normalised id) but absent on this page; and mirror-side missing
        miss_base = defaultdict(list)
        if k in BASE:
            have = {norm_id(r["id"]) for r in rows}
            for r in RAW[BASE[k]]["rows"]:
                if r["sys"] != "muscle" or r["id"].startswith("zan_"):      # named muscles only (own pages hold bones grouped: ribs, metacarpals, phalanges, skull)
                    continue
                if norm_id(r["id"]) not in have:
                    miss_base[reg13(r, RAW[BASE[k]]["joint_centres"])].append((r["sys"], r["id"]))
        mirror = defaultdict(list)
        ids = {(norm_id(r["id"]), r["sys"]) for r in rows}
        for r in rows:
            m = re.match(r"^(.*)_([lr])$", norm_id(r["id"]))
            if m and r["sys"] in ("muscle", "bone", "tendon", "ligament", "nerve", "vessel", "artery", "vein"):
                o = f"{m.group(1)}_{'r' if m.group(2) == 'l' else 'l'}"
                if (o, r["sys"]) not in ids:
                    mirror[r["r13"]].append(r["id"])
        for g in REG13:
            ms_ = miss_base.get(g, [])
            reg[g]["missing_expected_neighbours"] = {"vs_z_base_absent": len(ms_), "by_sys": dict(Counter(s for s, _ in ms_)), "examples": [i for _, i in ms_[:5]], "mirror_side_absent": len(mirror.get(g, [])),
                                                      "mirror_examples": mirror.get(g, [])[:4]}
        # Q209 before
        old = q209["pages"][k]; ob = {}
        for g in ["head_neck", "shoulder", "arm_elbow_forearm", "wrist_hand", "thorax", "abdomen_pelvis", "hip", "thigh", "knee", "leg", "ankle", "foot"]:
            o = old["regions"][g]["structures_major_moderate_minor"]; ob[g] = {"n": old["regions"][g]["n_structures"], "major_moderate_minor": o}
        def comb(names):
            return [sum(reg[g]["structures_major_moderate_minor"][i] for g in names) for i in range(3)]
        now12 = {"head_neck": comb(["head_neck"]), "shoulder": comb(["shoulder"]), "arm_elbow_forearm": comb(["arm", "elbow", "forearm"]), "wrist_hand": comb(["wrist_hand"]), "thorax": comb(["thorax"]),
                 "abdomen_pelvis": comb(["abdomen_pelvis"]), "hip": comb(["hip"]), "thigh": comb(["thigh"]), "knee": comb(["knee"]), "leg": comb(["leg"]), "ankle_foot": comb(["ankle_foot"])}
        before = {g: ob[g]["major_moderate_minor"] for g in ob if g not in ("ankle", "foot")}
        before["ankle_foot"] = [ob["ankle"]["major_moderate_minor"][i] + ob["foot"]["major_moderate_minor"][i] for i in range(3)]
        totals = {t: [sum(reg[g]["findings_by_type"][t][i] for g in REG13) for i in range(3)] for t in TYPES}
        otot = {t: [0, 0] for t in TYPES}
        GR = {"bone_gaps": "gap", "islands": None, "muscle_ends_off_bone": "detached_end", "flat_caps": "flat_cut", "structures_outside_skin": "outside_skin", "inside_bone": "soft_in_bone", "muscle_overlap": "muscle_in_muscle"}
        sev = {"major": sum(1 for r in rows if max([d["severity"] for d in r["defects"]], default=0) == 3), "moderate": sum(1 for r in rows if max([d["severity"] for d in r["defects"]], default=0) == 2),
               "minor": sum(1 for r in rows if max([d["severity"] for d in r["defects"]], default=0) == 1)}
        COLS = ["bone_gaps", "bone_penetrations", "flat_caps", "inside_bone", "islands", "muscle_ends_off_bone", "muscle_overlap", "structures_outside_skin", "ragged_open_boundary"]
        cn = {c: [sum(AG["pages"][k]["regions"][g][c]["n_major"] for g in AG["pages"][k]["regions"]), sum(AG["pages"][k]["regions"][g][c]["n_moderate"] for g in AG["pages"][k]["regions"])] for c in COLS}
        co = {c: [sum(old["regions"][g][c]["n_major"] for g in old["regions"]), sum(old["regions"][g][c]["n_moderate"] for g in old["regions"])] for c in COLS}
        ex = None
        ep = REPO / "build" / "q225_agg" / f"inbone_exact_{k}.json"
        if ep.exists():
            E = json.loads(ep.read_text())
            real = {i: e for i, e in E.items() if e["exact_depth_max_mm"] >= 3 and e["exact_pct_over_1mm"] >= 8}
            ex = {"n_inside_bone_sev_ge2_q204": len(E), "n_real_exact_ge3mm_and_8pct_over_1mm": len(real), "n_artefact_of_2mm_solid": len(E) - len(real),
                  "real_top": {i: {kk: e[kk] for kk in ("q204_pct", "exact_depth_max_mm", "exact_pct_over_1mm", "exact_pct_over_3mm")} for i, e in sorted(real.items(), key=lambda t: -t[1]["exact_pct_over_1mm"] * t[1]["exact_depth_max_mm"])[:8]}}
        PX = json.loads((REPO / "build/q225_agg/pairs_exact.json").read_text()) if (REPO / "build/q225_agg/pairs_exact.json").exists() else {}
        out = {"task": "Q225 read-only whole-body regional junction audit (Q204/Q209 code, Q198 thresholds unchanged)", "page_key": k, "label": LABEL[k], "page": PAGEDIR[k], "n_rows": len(rows),
               "regions_13": reg, "structures_major_moderate_minor_now": [sev["major"], sev["moderate"], sev["minor"]], "findings_by_type_major_moderate_minor_now": totals,
               "q209_structures_major_moderate_minor": old["structure_severity_counts"], "q209_regions_12_major_moderate_minor": before, "now_regions_12_major_moderate_minor": now12,
               "q209_page": old["page"], "sev_ge2_structures_by_q209_column_major_moderate": {"now": cn, "q209": co}, "inside_bone_exact_recheck": ex,
               "bone_pairs_exact_recheck": {kk.split(":", 1)[1]: v for kk, v in PX.items() if kk.startswith(k + ":")}, "skin_seam_totals": R["skin_seam_totals"], "skin_segments": {s: {kk: v.get(kk) for kk in ("valid", "open_or_missing_sections", "merged_with_trunk_sections", "max_radius_step_mm_per_3mm", "steps_gt3mm")} for s, v in R["skin_segments"].items() if isinstance(v, dict)},
               "skin_seams_by_region": R["skin_seams_by_region"], "junction_audit_q198": JA[k], "junction_zone_absent_vs_z_reference": ABS[k],
               "bone_penetrating_pairs": R["bone_penetrating_pairs"][:12], "bone_nn_gaps_gt6mm": {kk: v for kk, v in R["bone_nn"].items() if v[0] > 6},
               "symmetry_outliers_n": len(R["symmetry"]), "symmetry_top": [{kk: s[kk] for kk in ("structure", "region", "why")} for s in R["symmetry"][:6]]}
        (REPO / "build" / "q225_agg").mkdir(exist_ok=True)
        (DER / f"Q225_audit_{k}.json").write_text(json.dumps(out, separators=(",", ":")))
        print(k, out["structures_major_moderate_minor_now"], "was", old["structure_severity_counts"], flush=True)
    (REPO / "build" / "q225_agg" / "candidates.json").write_text(json.dumps(cands, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


if __name__ == "__main__":
    main()
