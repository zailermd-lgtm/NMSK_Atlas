#!/usr/bin/env python3
"""Q225 before / after numbers of the two Z-fitted pages: the UNCHANGED Q198 junction audit, Q204 regional pass (13 regions, as Q223), the Q198 fit-vs-base seam check (wrist / shoulder / elbow tears + frame offsets),
the exact bone-pair table (0.5 mm solids), the bone re-seat reports, the soft-tissue zone reports.   before = the Q223 audit of the Q221 / Q222 pages, after = the same code on the Q225 pages.
    python3 scripts/zanatomy/q225_compare.py   -> data/derived/Q225_before_after_{male,female}.json"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
DER = REPO / "data" / "derived"
KEY = {"male": "z_male_fit", "female": "z_female_fit"}
TRUNK = ("oblique", "transversus", "serratus", "latissimus", "iliocostalis", "rectus_abdominis", "pectoralis", "deltoid", "trapezius", "teres", "infraspinatus", "subscapularis", "supraspinatus", "gluteus", "iliopsoas")


def elbow_forearm(raw):
    """Q217-style left / right elbow muscle numbers from a Q198_model_<key>.json (junction audit)"""
    d = json.loads(Path(raw).read_text())
    out = {}
    for j in d["junctions"]:
        if j["name"] != "elbow":
            continue
        s = j["side"]
        soft = [x for x in j["soft"] if x["sys"] == "muscle" and x["id"].endswith("_" + s) and not any(t in x["id"] for t in TRUNK)]
        ov = {i: v["overlap_pct"] for i, v in j["muscle_overlap"].items() if i.endswith("_" + s) and not any(t in i for t in TRUNK)}
        det = [(x["id"], e) for x in soft for e in [(x.get("attach_ends_in_zone") or {})] for end, ee in e.items() if ee.get("min_expected_bone_mm", 0) > 5.0]
        out[s] = dict(n_muscles=len(soft), overlap_mean_pct=round(float(np.mean(list(ov.values()))), 1) if ov else None, overlap_max_pct=max(ov.values()) if ov else None,
                      muscles_over_40=sum(1 for v in ov.values() if v > 40), muscles_over_60=sum(1 for v in ov.values() if v > 60), detached_ends_over_5mm=len(det),
                      bone_surface_gap_mm=j["bones"].get("surface_gap_mm"), bone_max_penetration_mm=j["bones"].get("max_penetration_mm"),
                      tubes_gap_over_5mm=sum(1 for x in j["tubes"] if x["id"].endswith("_" + s) and x.get("max_island_gap_mm", 0) > 5))
    return out


def seams(path):
    d = json.loads(Path(path).read_text())
    out = {}
    for j in d["junctions"]:
        if j["name"] in ("wrist", "shoulder", "elbow"):
            out[f"{j['name']}_{j['side']}"] = {k: j.get(k) for k in ("zone_structures", "adjacent_pairs", "frac_gt3", "frac_gt5", "frac_gt10", "tear_p50_mm", "tear_p99_mm", "tear_max_mm", "n_pair_structures_with_tear_gt5", "n_offset_gt10", "n_offset_gt5")}
    return out


def main():
    for which, k in KEY.items():
        a, b = json.loads((DER / f"Q223_audit_{k}.json").read_text()), json.loads((DER / f"Q225_audit_{k}.json").read_text())
        res = {"task": "Q225 before (Q223 audit of the Q221 / Q222 page) vs after (Q225 page), UNCHANGED Q198 / Q204 / Q209 code and thresholds", "page": which, "page_dir_after": f"build/q225/viewer_zan_{'vhm' if which == 'male' else 'female'}"}
        ja, jb = a["junction_audit_q198"], b["junction_audit_q198"]
        res["q198_junction_audit"] = {"verdict_before_after": [ja["verdict_q209_now"][1], jb["verdict_q209_now"][1]], "verdict_q209": ja["verdict_q209_now"][0],
                                      "severity_major_moderate_minor": {"q209": ja["severity_major_moderate_minor_q209_now"][0], "q223_before": ja["severity_major_moderate_minor_q209_now"][1], "q225_after": jb["severity_major_moderate_minor_q209_now"][1]},
                                      "elbow_L_R_verdict": {"q209": ja["elbow_L_R_q209_now"][0], "q223_before": ja["elbow_L_R_q209_now"][1], "q225_after": jb["elbow_L_R_q209_now"][1]},
                                      "elbow_counts_major_moderate_minor": {"before": ja["elbow_counts_major_moderate_minor"], "after": jb["elbow_counts_major_moderate_minor"]},
                                      "junctions_before": ja["junctions"], "junctions_after": jb["junctions"]}
        res["q204_whole_body_structures_major_moderate_minor"] = {"q209": a["q209_structures_major_moderate_minor"], "q223_before": a["structures_major_moderate_minor_now"], "q225_after": b["structures_major_moderate_minor_now"]}
        res["q204_regions_13_major_moderate_minor_structures"] = {r: {"before": a["regions_13"][r]["structures_major_moderate_minor"], "after": b["regions_13"][r]["structures_major_moderate_minor"]} for r in a["regions_13"]}
        res["q204_findings_by_type_major_moderate_minor"] = {"before": a["findings_by_type_major_moderate_minor_now"], "after": b["findings_by_type_major_moderate_minor_now"]}
        res["q204_bone_penetrating_pairs"] = {"before": a["bone_penetrating_pairs"][:8], "after": b["bone_penetrating_pairs"][:8]}
        res["q204_bone_nn_gaps_gt6mm"] = {"before": a["bone_nn_gaps_gt6mm"], "after": b["bone_nn_gaps_gt6mm"]}
        res["inside_bone_exact"] = {"before": {kk: a["inside_bone_exact_recheck"][kk] for kk in ("n_inside_bone_sev_ge2_q204", "n_real_exact_ge3mm_and_8pct_over_1mm")} if a.get("inside_bone_exact_recheck") else None,
                                    "after": {kk: b["inside_bone_exact_recheck"][kk] for kk in ("n_inside_bone_sev_ge2_q204", "n_real_exact_ge3mm_and_8pct_over_1mm")} if b.get("inside_bone_exact_recheck") else None}
        res["bone_pairs_exact_recheck"] = {"before": a["bone_pairs_exact_recheck"], "after": b["bone_pairs_exact_recheck"]}
        res["skin_seam_totals"] = {"before": a["skin_seam_totals"], "after": b["skin_seam_totals"]}
        res["fit_seams_q198"] = {"before": seams(REPO / f"build/q223_raw/fake/data/derived/Q198_fitseams_{k}.json"), "after": seams(REPO / f"build/q225_raw/fake/data/derived/Q198_fitseams_{k}.json")}
        res["elbow_muscle_numbers_q217_style"] = {"before": elbow_forearm(REPO / f"build/q223_raw/Q198_model_{k}.json"), "after": elbow_forearm(REPO / f"build/q225_raw/Q198_model_{k}.json")}
        res["bone_measures_exact"] = {"before": json.loads((DER / f"Q225_bone_measures_{which}_src.json").read_text()), "after": json.loads((DER / f"Q225_bone_measures_{which}_q225.json").read_text())}
        st = pickle.load(open(REPO / f"build/q225/{which}_final.pkl", "rb"))
        res["bone_reseat_reports"] = st["reports"]["bones"]
        res["soft_tissue_zones"] = {z: {kk: v for kk, v in r.items() if not isinstance(v, (dict, list))} for z, r in st["reports"]["zones"].items()}
        res["structures_changed_by_stage"] = {}
        for i, logs in st["log"].items():
            for L in logs:
                if L.get("superseded"):
                    continue
                res["structures_changed_by_stage"].setdefault(L["stage"], []).append(i)
        res["structures_changed_by_stage"] = {s: len(set(v)) for s, v in res["structures_changed_by_stage"].items()}
        res["final_guards"] = {"island_gap_reverted": list(st["reports"]["final"]["reverted_island_gap"]), "attachment_guard": {i: v["kept_share_of_move"] for i, v in st["reports"]["final"]["attachment_guard"].items()}}
        (DER / f"Q225_before_after_{which}.json").write_text(json.dumps(res, indent=1, default=float))
        print(which, "written", res["q198_junction_audit"]["severity_major_moderate_minor"], res["q204_whole_body_structures_major_moderate_minor"], flush=True)


if __name__ == "__main__":
    main()
