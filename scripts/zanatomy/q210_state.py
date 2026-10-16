#!/usr/bin/env python3
"""Q210: print the numbers of the PROJECT_STATE.md Q210 section from the data/derived/Q210_* files (so the text cannot drift from the data).   python3 scripts/zanatomy/q210_state.py"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "derived"


def load(n):
    p = D / n
    return json.loads(p.read_text()) if p.exists() else None


def main():
    r, sd = load("Q210_report_male.json"), load("Q210_ship_diff_male.json")
    m0, m1 = load("Q208_metrics_after_male.json"), load("Q210_metrics_after_male.json")
    ft0, ft1 = load("Q209_forearm_trunk.json"), load("Q210_forearm_trunk.json")
    print(f"ship diff: geometry_changed {len(sd['geometry_changed'])} listed {sd['listed_structures']} unlisted {sd['geometry_changed_but_not_listed']} added {sd['added']} removed {sd['removed']} card_only {len(sd['card_only'])} unchanged {sd['unchanged']}")
    g = r["genital"]
    print("genital target", g["target_volume_mm3"], "refit", g["refit"], "search", g["search"])
    print("volumes", g["volume_mm3"], "midline", g["across_midline_plane_mm_before"], "->", g["across_midline_plane_mm_after"], "envelope", g["envelope_L"], g["envelope_L_final"])
    for i, x in g["structures"].items():
        f = g["structures_final_state"][i]
        b = x["before"]
        if i in g["structures_final_state"] and (b["audit_gt3_pct"] > 0 or f["audit_gt3_pct"] > 0):
            print(f"  {i}: audit > 3 mm {b['audit_gt3_pct']} % (max {b['audit_max_mm']}) -> {f['audit_gt3_pct']} % (max {f['audit_max_mm']}); fine > 0.5 mm {b['fine_gt0.5_pct']} -> {f['fine_gt0.5_pct']} % (max {b['fine_max_mm']} -> {f['fine_max_mm']})")
    print("fit scale", g["structure_fit_scale"])
    print("alt warp", {k[4:]: (v["move_mean_mm"], v["move_max_mm"], v["axis_extent_mm"]) for k, v in g["alternative_move_structures_with_skin_warp"].items()})
    print("own skin pct", g["structures_outside_own_skin_pct"])
    c = r["contact"]
    print("contact before", c["before"])
    print("contact after", c["after"])
    print("tube", c["tube_view"], "rho", c["rho"])
    print("history", [h for h in c["history"] if h.get("phase") in ("start", "after_partition", "absorb")])
    print("margins min", {i[9:]: m["min_margin_mm"] for i, m in c["margins"].items()})
    for i, m in r["moved"].items():
        print(f"  {i[9:]}: mean {m['mean_move_mm']} max {m['max_move_mm']} moved {m['vertices_moved_gt0_3mm']}/{m['vertices']} thickness {m['thickness_median_mm']} step {m['seam_step_max_mm']} own>2 {m['outside_own_skin_gt2mm_pct']}")
    print("seams", r["seams"]["q208"]["steps_gt_3mm"], r["seams"]["q208"]["max_step_mm"], "->", r["seams"]["q210"]["steps_gt_3mm"], r["seams"]["q210"]["max_step_mm"])
    print("forearm sections", r.get("forearm_sections"))
    print("escape", {t: {k: v["escape_dirs"] for k, v in e.items()} for t, e in r.get("escape", {}).items()})
    print("palmaris", r.get("palmaris"))
    if m0 and m1:
        print("envelope", m0["envelope"], "->", m1["envelope"], "| open", m0["open"]["open_boundary_edges_total"], "->", m1["open"]["open_boundary_edges_total"])
        print("contacts", m0["contact"]["gap_gt_3mm"], m0["contact"]["gap_gt_5mm"], m0["contact"]["gap_max_mm"], "->", m1["contact"]["gap_gt_3mm"], m1["contact"]["gap_gt_5mm"], m1["contact"]["gap_max_mm"])
        print("seams (Q202)", {k: m0["seams"][k] for k in ("steps_gt_3mm", "max_step_mm", "surface_gap_max_mm")}, "->", {k: m1["seams"][k] for k in ("steps_gt_3mm", "max_step_mm", "surface_gap_max_mm")})
        print("escape (Q202)", {k: v["escape_dirs"] for k, v in m0["escape"].items()}, "->", {k: v["escape_dirs"] for k, v in m1["escape"].items()})
        print("sections", m0["sections_summary"], "->", m1["sections_summary"])
    if ft0 and ft1:
        print("Q209 measure before", ft0["forearm_vs_trunk"], ft0["crossings_page_decode"])
        print("Q209 measure after", ft1["forearm_vs_trunk"], ft1["crossings_page_decode"])
        print("deep tissue before", ft0["deep_tissue_by_side"])
        print("deep tissue after", ft1["deep_tissue_by_side"])


if __name__ == "__main__":
    main()
