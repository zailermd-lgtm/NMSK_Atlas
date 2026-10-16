#!/usr/bin/env python3
"""Q204 aggregator (READ-ONLY): Q198-unchanged junction audit (build/q204_raw/Q198_*), Q204 whole-body regional pass (Q204_regions_*), hands (Q204_hands_*)
-> data/derived/Q204_anatomy_audit.json (compact) and the PROJECT_STATE markdown table (stdout with --md)."""
from __future__ import annotations
import json, re, sys
from collections import Counter, defaultdict
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "build" / "q204_raw"
RAWM = REPO / "build" / "q204_raw_merged"      # own pages: Z-completion entries (*_zfill*) merged into their base structure before the unchanged audit
DER = REPO / "data" / "derived"
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q198_rank import THRESH  # noqa: E402
from scripts.zanatomy.q204_paths import PAGES  # noqa: E402
from scripts.zanatomy.q204_regions import structure_defects, symmetry  # noqa: E402

KEYS = ["own_m", "own_f", "z_male", "z_base_f", "z_male_fit", "z_female_fit"]
BASE = {"z_male_fit": "z_male", "z_female_fit": "z_base_f"}
PAGE_DIR = {"own_m": "build/q203/viewer_m_hr (+build/viewer_m_hr_q203)", "own_f": "build/q203/viewer_f_hr (+build/viewer_f_hr_q203)", "z_male": "build/q197/viewer_zan_atlas",
            "z_base_f": "build/q202/viewer_base_female", "z_male_fit": "build/q202/viewer_zan_vhm", "z_female_fit": "build/q202/viewer_zan_female"}
REGIONS = ["head_neck", "shoulder", "arm_elbow_forearm", "wrist_hand", "thorax", "abdomen_pelvis", "hip", "thigh", "knee", "leg", "ankle", "foot"]
JREG = {"shoulder": "shoulder", "elbow": "arm_elbow_forearm", "wrist": "wrist_hand", "hip": "hip", "knee": "knee", "ankle": "ankle", "cervico_thoracic": "head_neck",
        "thoraco_lumbar": "abdomen_pelvis", "head_neck": "head_neck"}
GROUPS = {  # check -> report column
    "bone_gap": "bone_gaps", "bone_penetration": "bone_penetrations", "bone_flat_cut": "flat_caps", "flat_cut_face": "flat_caps", "end_off_bone": "muscle_ends_off_bone",
    "outside_skin": "structures_outside_skin", "disconnected_island": "islands", "bone_island": "islands", "tube_gap": "islands", "axial_gap": "islands", "inside_bone": "inside_bone",
    "muscle_interpenetration": "muscle_overlap", "ragged_open_boundary": "ragged_open_boundary"}
W = {1: 1, 2: 3, 3: 10}
CAUSE = {"flat_cut_face": "block_seam_or_cut", "bone_flat_cut": "block_seam_or_cut", "end_off_bone": "attachment_off_bone", "disconnected_island": "fragmented_mesh", "bone_island": "fragmented_mesh",
         "tube_gap": "fragmented_mesh", "axial_gap": "fragmented_mesh", "outside_skin": "soft_outside_skin", "inside_bone": "soft_inside_bone", "bone_penetration": "bone_overlap",
         "bone_gap": "bone_chain_gap", "muscle_interpenetration": "muscle_overlap", "ragged_open_boundary": "ragged_boundary"}


def jl(p):
    return json.loads(Path(p).read_text())


def top(items, key, n=4):
    return sorted(items, key=key, reverse=True)[:n]


def main():
    old = jl(DER / "Q198_anatomy_audit.json")
    new_asis = jl(RAW / "Q198_anatomy_audit.json")
    new_m = jl(RAWM / "Q198_anatomy_audit.json")
    new = {"models": {k: (new_m if k.startswith("own") else new_asis)["models"][k] for k in KEYS}}
    out = {"meta": {"task": "Q204 read-only fresh anatomy continuity / in-place audit of the six CURRENTLY PUBLISHED pages", "pages": PAGE_DIR, "regions": REGIONS,
                    "method": ("(1) Q198 audit code UNCHANGED (q198_audit/q198_rank/q198_fitseams via thin wrappers q204_junctions/q204_rank/q204_fitseams that only re-point the page table): "
                               "junction zones shoulder/elbow/wrist/hip/knee/ankle/cervico-thoracic/thoraco-lumbar/head-neck, same thresholds -> 'q198_vs_now'. "
                               "(2) NEW whole-body regional pass (q204_regions.py): every structure through the Q198 analysers (islands, flat caps, open edges, end-to-bone, outside skin, inside bone) "
                               "with Q198 severity thresholds, 2 mm voxel field for bone-bone penetration and muscle-in-muscle overlap, nearest-bone gap, patch-border skin gaps, "
                               "limb-segment skin sections, mirrored L/R pairs; regions = nearest-bone label + joint proximity."),
                    "q198_thresholds": THRESH,
                    "q204_additions": {"bone_nn_gap_mm": "nearest other bone > 6 mm (1), > 12 (2), > 25 (3); vertebra-vertebra/sacrum pairs allow 10 mm disc space", "voxel_pitch_mm": 2.0,
                                       "end_off_bone": "muscle end > 6/10/20 mm from nearest bone AND > 5 mm from any tendon/ligament/fascia/cartilage/joint/insertion/bursa/skin; capped moderate (as Q198 generic)",
                                       "symmetry_outlier": "mirrored centroid offset > 25 mm, volume ratio outside 0.6..1.66 (> 5 cm3), length ratio outside 0.7..1.43, or defect severity differing by >= 2",
                                       "group_bone_overlap": "grouped meshes (tarsals, carpals, metatarsals, ribs, ...) overlapping their component bones are capped at minor",
                                       "skin_patch_border_gap": "Z: border vertex of a skin patch whose nearest border vertex of ANOTHER patch is >= 2 mm away (hole/tear border); own: open boundary loops"},
                    "caveats": ["thresholds are Q198's (mine); regional pass voxel pitch 2 mm vs Q198 junction zones 1.5 mm, so regional inside-bone/overlap numbers are not comparable to Q198 zone numbers",
                                "broad flat muscles (trapezius, latissimus, obliques, diaphragm) have PCA ends that are not origin/insertion: end_off_bone is noisy there (moderate cap)",
                                "Z multi-piece vessels/nerves are partly by design (PLURAL names exempt); source defects of the unfitted Z base are tagged in_base"]}, "pages": {}}
    regs = {k: jl((RAWM if k.startswith("own") else RAW) / f"Q204_regions_{k}.json") for k in KEYS}
    for k in KEYS:
        for r in regs[k]["rows"]:
            r["defects"] = structure_defects(r)
        regs[k]["symmetry"] = symmetry(regs[k]["rows"])[1]
    hands = {k: jl(RAW / f"Q204_hands_{k}.json") for k in ("z_male", "z_base_f", "z_male_fit", "z_female_fit") if (RAW / f"Q204_hands_{k}.json").exists()}
    raw_j = {k: jl((RAWM if k.startswith("own") else RAW) / f"Q198_model_{k}.json") for k in KEYS}
    base_ids = {}
    for k, b in BASE.items():
        base_ids[k] = {(r["id"], d["check"]) for r in regs[b]["rows"] for d in r["defects"] if d["severity"] >= 2}
    for k in KEYS:
        R = regs[k]; rows = R["rows"]; om, nm = old["models"][k], new["models"][k]
        P = {"label": new["models"][k]["label"], "page": PAGE_DIR[k], "n_structures": nm["n_structures"], "regional_rows": len(rows)}
        # ---- Q198 vs now
        jt_old = {(j["junction"], j["side"]): j for j in om["junction_table"]}
        jt_new = {(j["junction"], j["side"]): j for j in nm["junction_table"]}
        P["q198_vs_now"] = {
            "verdict": [om["verdict_continuous_and_in_place"], nm["verdict_continuous_and_in_place"]],
            "severity_major_moderate_minor": [[om["severity_counts"][x] for x in ("major", "moderate", "minor")], [nm["severity_counts"][x] for x in ("major", "moderate", "minor")]],
            "elbow_L_R": [[om["elbow"]["l"]["verdict"], om["elbow"]["r"]["verdict"]], [nm["elbow"]["l"]["verdict"], nm["elbow"]["r"]["verdict"]]],
            "cause_groups_sev_ge2": [om["cause_groups_sev_ge2"], nm["cause_groups_sev_ge2"]],
            "missing_joints": [len(om["missing_joints"]), len(nm["missing_joints"])],
            "junctions": [{"junction": j, "side": s, "bone_gap_mm": [jt_old.get((j, s), {}).get("bone_gap_mm"), jt_new[(j, s)]["bone_gap_mm"]],
                           "bone_penetration_mm": [jt_old.get((j, s), {}).get("bone_penetration_mm"), jt_new[(j, s)]["bone_penetration_mm"]],
                           "major_moderate_minor": [[jt_old[(j, s)][x] for x in ("n_major", "n_moderate", "n_minor")] if (j, s) in jt_old else None, [jt_new[(j, s)][x] for x in ("n_major", "n_moderate", "n_minor")]]}
                          for (j, s) in sorted(jt_new)],
            "block_seam_planes": [len(om.get("seams", [])), len(nm.get("seams", []))],
            "top_issues_now": [{"sev": g["severity"], "region": g["region"], "side": g.get("side"), "text": g["headline"][:170], "cause": g["cause"]} for g in nm["issues"][:6]],
            "skin_mesh": [om.get("skin_mesh"), nm.get("skin_mesh")]}
        if k.startswith("own"):
            am = new_asis["models"][k]
            ja = {(j["junction"], j["side"]): j for j in am["junction_table"]}
            P["q198_vs_now"]["as_is_unmerged_strict_q198"] = {"verdict": am["verdict_continuous_and_in_place"], "severity_major_moderate_minor": [am["severity_counts"][x] for x in ("major", "moderate", "minor")],
                                                               "elbow_L_R": [am["elbow"]["l"]["verdict"], am["elbow"]["r"]["verdict"]], "missing_joints": len(am["missing_joints"]),
                                                               "bone_gap_mm_by_junction": {f"{j}_{s}": ja[(j, s)]["bone_gap_mm"] for (j, s) in sorted(ja) if ja[(j, s)]["bone_gap_mm"] and ja[(j, s)]["bone_gap_mm"] > 3},
                                                               "note": "strict Q198 on the raw page: '*_zfill*' continuation entries are separate meshes, so bone sets / flat cuts are measured without them; the 'now' numbers above merge each continuation into its structure first"}
        # ---- regions
        sev_struct = {}
        by_reg = defaultdict(lambda: {"n_structures": 0, "by_side": Counter(), "n_major": 0, "n_moderate": 0, "n_minor": 0, "cols": defaultdict(list)})
        for r in rows:
            e = by_reg[r["region"]]
            e["n_structures"] += 1; e["by_side"][r["side"]] += 1
            ms = max([d["severity"] for d in r["defects"]], default=0)
            sev_struct[r["id"]] = ms
            if ms == 3: e["n_major"] += 1
            elif ms == 2: e["n_moderate"] += 1
            elif ms == 1: e["n_minor"] += 1
            for d in r["defects"]:
                inb = bool(k in BASE and (r["id"], d["check"]) in base_ids[k])
                e["cols"][GROUPS[d["check"]]].append({"id": r["id"], "sys": r["sys"], "side": r["side"], "check": d["check"], "sev": d["severity"], "value": d["value"], "unit": d["unit"],
                                                       "detail": d["detail"][:140], "in_base": inb, "src": r.get("cls") or r.get("src")})
        P["regions"] = {}
        sk = R["skin_seams_by_region"]; skb = regs[BASE[k]]["skin_seams_by_region"] if k in BASE else {}
        seg_reg = {"thigh_l": "thigh", "thigh_r": "thigh", "leg_l": "leg", "leg_r": "leg", "upper_arm_l": "arm_elbow_forearm", "upper_arm_r": "arm_elbow_forearm", "forearm_l": "arm_elbow_forearm",
                   "forearm_r": "arm_elbow_forearm", "neck": "head_neck"}
        for reg in REGIONS:
            e = by_reg.get(reg)
            rr = {"n_structures": e["n_structures"] if e else 0, "by_side": dict(e["by_side"]) if e else {}, "structures_major_moderate_minor": [e["n_major"], e["n_moderate"], e["n_minor"]] if e else [0, 0, 0]}
            for col in sorted(set(GROUPS.values())):
                items = e["cols"].get(col, []) if e else []
                rr[col] = {"n_structures": len({(i["id"]) for i in items}), "n_major": len({i["id"] for i in items if i["sev"] == 3}), "n_moderate": len({i["id"] for i in items if i["sev"] == 2}),
                           "n_in_unfitted_base": len({i["id"] for i in items if i["in_base"] and i["sev"] >= 2}) if k in BASE else None,
                           "worst": [{kk: i[kk] for kk in ("id", "side", "sev", "value", "unit", "detail", "in_base")} for i in top(items, lambda i: (i["sev"], i["value"] if isinstance(i["value"], (int, float)) else 0), 3)]}
            if reg in ("head_neck",) and False:
                pass
            # Q198 junction-level bone gap / penetration in this region
            rr["junction_bones"] = [{"junction": j, "side": s, "bone_gap_mm": jt_new[(j, s)]["bone_gap_mm"], "bone_penetration_mm": jt_new[(j, s)]["bone_penetration_mm"]}
                                    for (j, s) in sorted(jt_new) if JREG.get(j) == reg]
            pen = [p for p in R["bone_penetrating_pairs"] if any(rw["id"] == p["a"] and rw["region"] == reg for rw in rows)]
            rr["bone_pair_penetrations"] = {"n_pairs": len(pen), "max_mm": max([p["max_depth_mm"] for p in pen], default=0),
                                            "worst": [f"{p['a']} / {p['b']} {p['max_depth_mm']} mm" for p in pen[:3]]}
            rr["skin_seams"] = sk.get(reg) if sk else None
            if k in BASE and sk:
                rr["skin_seams_unfitted_base"] = skb.get(reg)
            rr["skin_segments"] = {s_: R["skin_segments"][s_] for s_ in R["skin_segments"] if seg_reg.get(s_) == reg and R["skin_segments"][s_].get("valid")}
            so = [s_ for s_ in R["symmetry"] if s_["region"] == reg]
            rr["symmetry_outliers"] = {"n": len(so), "worst": [{"structure": s_["structure"], "why": s_["why"]} for s_ in so[:3]]}
            P["regions"][reg] = rr
        P["skin"] = {"seam_totals": R["skin_seam_totals"], "segments": R["skin_segments"], "block_seam_planes": raw_j[k].get("seam_planes", [])[:8]}
        P["symmetry_total_outliers"] = len(R["symmetry"])
        # ---- worst 10 structures
        sc = []
        for r in rows:
            if not r["defects"]:
                continue
            ms = max(d["severity"] for d in r["defects"])
            score = sum(W[d["severity"]] for d in r["defects"])
            sc.append((ms, score, r))
        sc.sort(key=lambda t: (t[0], t[1]), reverse=True)
        P["worst10"] = []
        for ms, score, r in sc[:10]:
            ds = sorted(r["defects"], key=lambda d: -d["severity"])
            P["worst10"].append({"id": r["id"], "region": r["region"], "side": r["side"], "sys": r["sys"], "src": r.get("cls") or r.get("src"), "max_severity": ms, "score": score,
                                 "centroid_mm": r["centroid"], "findings": [f"[{d['severity']}] {d['check']}: {d['detail'][:110]}" for d in ds[:3]],
                                 "in_unfitted_base": bool(k in BASE and any((r["id"], d["check"]) in base_ids[k] for d in ds if d["severity"] >= 2))})
        # cause tally (sev >= 2)
        ct = Counter(); ctb = Counter()
        for r in rows:
            for d in r["defects"]:
                if d["severity"] >= 2:
                    ct[CAUSE[d["check"]]] += 1
                    if k in BASE and (r["id"], d["check"]) in base_ids[k]:
                        ctb[CAUSE[d["check"]]] += 1
        P["defects_sev_ge2_by_kind"] = dict(ct)
        if k in BASE:
            P["defects_sev_ge2_already_in_unfitted_base"] = dict(ctb)
        P["structure_severity_counts"] = {"major": sum(1 for v in sev_struct.values() if v == 3), "moderate": sum(1 for v in sev_struct.values() if v == 2), "minor": sum(1 for v in sev_struct.values() if v == 1),
                                          "clean": sum(1 for v in sev_struct.values() if v == 0)}
        P["symmetry_top"] = [{kk: s_[kk] for kk in ("structure", "region", "why")} for s_ in R["symmetry"][:8]]
        # ---- Z fitted extras
        if k in BASE:
            P["z_fit_extras"] = zextras(k, regs, hands)
        out["pages"][k] = P
    (DER / "Q204_anatomy_audit.json").write_text(json.dumps(out, separators=(",", ":")))
    print("wrote", (DER / "Q204_anatomy_audit.json").stat().st_size, "bytes")


def zextras(k, regs, hands):
    R = regs[k]; Rb = regs[BASE[k]]
    ex = {}
    # hands / fingers
    if k in hands and BASE[k] in hands:
        h, hb = hands[k], hands[BASE[k]]
        rec = {}
        for sd in ("l", "r"):
            a, b = h["sides"][sd], hb["sides"][sd]
            links = []
            for f in a["fingers"]:
                for la, lb in zip(a["fingers"][f]["links"], b["fingers"][f]["links"]):
                    links.append({"link": f"{f}: {la['link']}", "gap_fit_mm": la["gap_mm"], "gap_base_mm": lb["gap_mm"]})
            wr = [{"link": x["link"], "gap_fit_mm": x["gap_mm"], "gap_base_mm": next((y["gap_mm"] for y in b["links"] if y["link"] == x["link"]), None)} for x in a["links"]]
            bend = []
            for f in a["fingers"]:
                for i_, (x, y) in enumerate(zip(a["fingers"][f]["bend_deg"], b["fingers"][f]["bend_deg"])):
                    bend.append(abs(x - y))
            out_sk = [(bn["id"], bn["outside_skin_pct"], bn["outside_skin_max_mm"]) for f in a["fingers"] for bn in a["fingers"][f]["bones"] if bn["outside_skin_pct"] > 5 and bn["outside_skin_max_mm"] > 3]
            out_sk_b = [(bn["id"], bn["outside_skin_pct"], bn["outside_skin_max_mm"]) for f in b["fingers"] for bn in b["fingers"][f]["bones"] if bn["outside_skin_pct"] > 5 and bn["outside_skin_max_mm"] > 3]
            lenr = [bn["length_mm"] / bb["length_mm"] for f in a["fingers"] for bn, bb in zip(a["fingers"][f]["bones"], b["fingers"][f]["bones"]) if bb["length_mm"] > 5]
            rec[sd] = {"chain_links": len(links), "links_gap_gt3mm_fit": [x for x in links if x["gap_fit_mm"] > 3][:8], "n_links_gap_gt3mm_fit": sum(x["gap_fit_mm"] > 3 for x in links),
                       "n_links_gap_gt3mm_base": sum(x["gap_base_mm"] > 3 for x in links), "max_link_gap_fit_mm": max(x["gap_fit_mm"] for x in links), "max_link_gap_base_mm": max(x["gap_base_mm"] for x in links),
                       "wrist_carpal_links": wr, "max_joint_bend_change_vs_base_deg": round(max(bend), 1) if bend else None,
                       "finger_bone_length_ratio_fit_over_base_min_max": [round(min(lenr), 2), round(max(lenr), 2)],
                       "finger_bones_outside_skin_fit": out_sk[:6], "n_finger_bones_outside_skin_fit": len(out_sk), "n_finger_bones_outside_skin_base": len(out_sk_b)}
        ex["fingers_hands"] = rec
    rows = {r["id"]: r for r in R["rows"]}
    ex["hand_region_structures"] = {sd: {"n": sum(1 for r in R["rows"] if r["region"] == "wrist_hand" and r["side"] == sd),
                                         "n_major_moderate": sum(1 for r in R["rows"] if r["region"] == "wrist_hand" and r["side"] == sd and any(d["severity"] >= 2 for d in r["defects"])),
                                         "n_major_moderate_base": sum(1 for r in Rb["rows"] if r["region"] == "wrist_hand" and r["side"] == sd and any(d["severity"] >= 2 for d in r["defects"]))} for sd in ("l", "r")}
    # left vs right upper arm (muscles between shoulder and elbow)
    ua = {}
    for sd in ("l", "r"):
        sh = np.asarray(R["joint_centres"].get(f"shoulder_{sd}")); el = np.asarray(R["joint_centres"].get(f"elbow_{sd}"))
        ax = el - sh; Lx = np.linalg.norm(ax); ax = ax / Lx
        lst = []
        for r in R["rows"]:
            if r["sys"] != "muscle" or r["side"] not in (sd, "m"):
                continue
            c = np.asarray(r["centroid"]); t = float((c - sh) @ ax) / Lx; rad = float(np.linalg.norm((c - sh) - ((c - sh) @ ax) * ax))
            if 0.08 < t < 0.95 and rad < 75 and r.get("vol_cm3", 0) and r["vol_cm3"] > 3:
                lst.append({"id": r["id"], "overlap_pct": r.get("overlap_pct"), "vol_cm3": r.get("vol_cm3"), "outside_skin_pct": r.get("outside_skin_pct"), "outside_skin_max_mm": r.get("outside_skin_max_mm"),
                            "inside_bone_pct": r.get("inside_bone_pct"), "sev": max([d["severity"] for d in r["defects"]], default=0)})
        ua[sd] = lst
    def agg(l):
        ov = [x["overlap_pct"] for x in l if x["overlap_pct"] is not None]
        return {"n_muscles": len(l), "mean_overlap_pct": round(float(np.mean(ov)), 1) if ov else None, "n_overlap_gt40": sum(o > 40 for o in ov), "n_outside_skin_gt5pct": sum((x["outside_skin_pct"] or 0) > 5 and (x["outside_skin_max_mm"] or 0) > 5 for x in l),
                "worst_overlap": sorted([(x["id"], x["overlap_pct"]) for x in l if x["overlap_pct"] is not None], key=lambda t: -t[1])[:5], "n_sev_ge2": sum(x["sev"] >= 2 for x in l)}
    ex["upper_arm_left_vs_right"] = {sd: agg(ua[sd]) for sd in ("l", "r")}
    # base for comparison
    uab = {}
    for sd in ("l", "r"):
        sh = np.asarray(Rb["joint_centres"].get(f"shoulder_{sd}")); el = np.asarray(Rb["joint_centres"].get(f"elbow_{sd}"))
        ax = el - sh; Lx = np.linalg.norm(ax); ax = ax / Lx; l = []
        for r in Rb["rows"]:
            if r["sys"] != "muscle" or r["side"] not in (sd, "m"):
                continue
            c = np.asarray(r["centroid"]); t = float((c - sh) @ ax) / Lx; rad = float(np.linalg.norm((c - sh) - ((c - sh) @ ax) * ax))
            if 0.08 < t < 0.95 and rad < 75 and r.get("vol_cm3", 0) and r["vol_cm3"] > 3:
                l.append({"id": r["id"], "overlap_pct": r.get("overlap_pct"), "vol_cm3": r.get("vol_cm3"), "outside_skin_pct": r.get("outside_skin_pct"), "outside_skin_max_mm": r.get("outside_skin_max_mm"),
                          "inside_bone_pct": r.get("inside_bone_pct"), "sev": max([d["severity"] for d in r["defects"]], default=0)})
        uab[sd] = l
    ex["upper_arm_unfitted_base"] = {sd: agg(uab[sd]) for sd in ("l", "r")}
    return ex


if __name__ == "__main__":
    main()
