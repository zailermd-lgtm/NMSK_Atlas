#!/usr/bin/env python3
"""Q224 before / after audit numbers of the two OWN pages (READ-ONLY on the pages): the UNCHANGED Q198 / Q204 audit code (scripts/zanatomy/q204_regions.py, q204_junctions.py, q204_rank.py, thresholds of q198_rank)
run on the Q224 pages (build/q224/viewer_{m,f}_hr via q224_paths / q224_run, raw output build/q224_raw_merged) against the same code's output on the Q223 pages (build/q223_raw_merged) and the Q209 numbers.

    python3 scripts/zanatomy/q224_audit_summary.py            -> data/derived/Q224_audit_before_after.json   (+ Q224_audit_own_<m|f>.json = the same compact numbers per page)
Columns: Q198 junction audit (severity major/moderate/minor, verdict, elbow L/R), Q204 whole-body structures major/moderate/minor, findings by type x severity, 13 regions, and the TARGETED counts of this task
(tube gaps, grouped / duplicate bone penetrations, flat cut faces > 100 mm2, detached pieces)."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q204_regions import structure_defects  # noqa: E402
from scripts.zanatomy.q223_summary import reg13, TYPE, TYPES, REG13  # noqa: E402

DER = REPO / "data" / "derived"
KEYS = {"own_m": "m", "own_f": "f"}
BEFORE = REPO / "build" / "q223_raw_merged"
AFTER = REPO / "build" / "q224_raw_merged"
DUP_BONES = re.compile(r"^(tarsals|carpals)_[lr]$|_q212$|^(calcaneus|talus|cuboid|navicular|cuneiform_\w+|carpals_[lr]_q212|radius_[lr]_distal_q212|ulna_[lr]_distal_q212)")


def summarize(raw: Path, k: str):
    R = json.loads((raw / f"Q204_regions_{k}.json").read_text())
    rows = R["rows"]
    for r in rows:
        r["defects"] = structure_defects(r)
        r["r13"] = reg13(r, R["joint_centres"])
    sev = Counter(max([d["severity"] for d in r["defects"]], default=0) for r in rows)
    ftype = {t: [0, 0, 0] for t in TYPES}
    reg = {g: [0, 0, 0] for g in REG13}
    tube, flat100, isl = [], 0, []
    for r in rows:
        ms = max([d["severity"] for d in r["defects"]], default=0)
        if ms:
            reg[r["r13"]][3 - ms] += 1
        for d in r["defects"]:
            ftype[TYPE[d["check"]]][3 - d["severity"]] += 1
            if d["check"] == "tube_gap":
                tube.append(dict(id=r["id"], gap_mm=d["value"], sev=d["severity"]))
            if d["check"] == "disconnected_island":
                isl.append(dict(id=r["id"], area_share=d["value"], sev=d["severity"]))
        flat100 += sum(1 for c in (r.get("flat_caps") or []) if c["area_mm2"] > 100 and r["sys"] in ("muscle", "tendon"))
    pen = [p for p in R["bone_penetrating_pairs"] if p["max_depth_mm"] >= 3.0]
    dup_pairs = [p for p in pen if (re.match(r"^(tarsals|carpals)_[lr]$", p["a"]) or re.match(r"^(tarsals|carpals)_[lr]$", p["b"]))]
    j = None
    qa = raw / "Q198_anatomy_audit.json"
    if qa.exists():
        M = json.loads(qa.read_text())["models"].get(k)
        if M:
            j = dict(severity_major_moderate_minor=[M["severity_counts"][x] for x in ("major", "moderate", "minor")], verdict=M["verdict_continuous_and_in_place"],
                     elbow_L_R=[M["elbow"]["l"]["verdict"], M["elbow"]["r"]["verdict"]], elbow_counts={sd: [M["elbow"][sd]["n_major"], M["elbow"][sd]["n_moderate"], M["elbow"][sd]["n_minor"]] for sd in ("l", "r")},
                     n_structures=M.get("n_structures"))
    return dict(rows=len(rows), q198_junction_audit=j, q204_structures_major_moderate_minor=[sev[3], sev[2], sev[1]], findings_by_type_major_moderate_minor=ftype, regions_13_structures_major_moderate_minor=reg,
                targeted=dict(tube_gap_findings=tube, flat_cut_faces_over_100mm2_muscles=flat100, detached_piece_findings_sev_ge1=len(isl), detached_piece_findings=isl,
                              bone_pairs_penetrating_ge3mm=len(pen), duplicate_group_mesh_pairs_ge3mm=[dict(a=p["a"], b=p["b"], max_depth_mm=p["max_depth_mm"]) for p in dup_pairs],
                              bone_pairs_top=[dict(a=p["a"], b=p["b"], max_depth_mm=p["max_depth_mm"]) for p in sorted(pen, key=lambda p: -p["max_depth_mm"])[:8]]))


def main():
    q209 = json.loads((DER / "Q209_anatomy_audit.json").read_text())
    out = {"task": "Q224 before / after audit numbers of the own pages (Q198 / Q204 code and thresholds unchanged)", "before_pages": {"own_m": "build/q221/viewer_m_hr (bundle build/viewer_m_hr_q217)", "own_f": "build/q222/viewer_f_hr (bundle build/viewer_f_hr_q216)"},
           "after_pages": {"own_m": "build/q224/viewer_m_hr (bundle build/viewer_m_hr_q224)", "own_f": "build/q224/viewer_f_hr (bundle build/viewer_f_hr_q224)"}}
    for k in KEYS:
        b = summarize(BEFORE, k)
        a = summarize(AFTER, k)
        o9 = q209["pages"][k]
        out[k] = dict(q209=dict(structures_major_moderate_minor=o9["structure_severity_counts"], q198_junction_severity_major_moderate_minor=o9["q198_vs_now"]["severity_major_moderate_minor"][1],
                                elbow_L_R=o9["q198_vs_now"]["elbow_L_R"][1], verdict=o9["q198_vs_now"]["verdict"][1]),
                      q223_before=b, q224_after=a)
        (DER / f"Q224_audit_{KEYS[k]}.json").write_text(json.dumps(dict(page=k, q209=out[k]["q209"], before=b, after=a), indent=1) + "\n")
        print(k, "Q198 junction", b["q198_junction_audit"] and b["q198_junction_audit"]["severity_major_moderate_minor"], "->", a["q198_junction_audit"] and a["q198_junction_audit"]["severity_major_moderate_minor"],
              "| Q204 structures", b["q204_structures_major_moderate_minor"], "->", a["q204_structures_major_moderate_minor"], "| tube gaps", len(b["targeted"]["tube_gap_findings"]), "->", len(a["targeted"]["tube_gap_findings"]),
              "| flat>100", b["targeted"]["flat_cut_faces_over_100mm2_muscles"], "->", a["targeted"]["flat_cut_faces_over_100mm2_muscles"])
    (DER / "Q224_audit_before_after.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
