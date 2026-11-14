#!/usr/bin/env python3
"""Q208: print the numbers of the PROJECT_STATE.md Q208 section from the data/derived/Q208_* files (so the text cannot drift from the data).   python3 scripts/zanatomy/q208_state.py"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "derived"


def load(n):
    p = D / n
    return json.loads(p.read_text()) if p.exists() else None


def main():
    for w in ("male", "female"):
        r, m, z = load(f"Q208_report_{w}.json"), load(f"Q208_metrics_after_{w}.json"), load(f"Q208_zone_{w}.json")
        q7 = load(f"Q207_metrics_after_{w}.json")
        sd = load(f"Q208_ship_diff_{w}.json")
        print(f"== {w}: {len(r['moved'])} patches changed; ship diff unlisted {sd['geometry_changed_but_not_listed']} added {sd['added']}")
        c = r["crossings"]
        for t in ("z_source", "q207", "q208"):
            print("  crossings", t, c[t]["depth_gt_2mm"], c[t]["depth_gt_4mm"], c[t]["deep_pairs_by_category"])
        for s in "lr":
            print("  forearm sections", s, {k: (v["closed"], v["slices"], v["segment_crossings"], v["radius_step_max_mm_per_3mm"]) for k, v in r["forearm_sections"][s].items()})
        print("  seams", r["seams"]["q207"]["steps_gt_3mm"], r["seams"]["q207"]["max_step_mm"], "->", r["seams"]["q208"]["steps_gt_3mm"], r["seams"]["q208"]["max_step_mm"])
        print("  bones not enclosed (elbow region)", r["bones_not_enclosed_elbow_region"])
        if m and q7:
            print("  envelope", q7["envelope"], "->", m["envelope"], "| open edges", q7["open"]["open_boundary_edges_total"], "->", m["open"]["open_boundary_edges_total"])
            print("  sections summary", q7["sections_summary"], "->", m["sections_summary"])
            print("  escape", {k: v["escape_fraction"] for k, v in m["escape"].items()})
            print("  contact gt3/gt5", q7["contact"]["gap_gt_3mm"], q7["contact"]["gap_gt_5mm"], "->", m["contact"]["gap_gt_3mm"], m["contact"]["gap_gt_5mm"], "| seams", q7["seams"]["steps_gt_3mm"], q7["seams"]["max_step_mm"], q7["seams"]["surface_gap_max_mm"], "->", m["seams"]["steps_gt_3mm"], m["seams"]["max_step_mm"], m["seams"]["surface_gap_max_mm"])
        if z:
            for s in "lr":
                zz = z["sides"][s]
                print("  zone", s, {k: (zz["before"][k]["audit_gt5pct"], zz["after"][k]["audit_gt5pct"], zz["before"][k]["fine_gt5pct"], zz["after"][k]["fine_gt5pct"]) for k in zz["before"] if k in ("bone", "vessel", "nerve", "joint", "muscle")},
                      "muscles >5% outside displayed skin", zz["muscles_gt5pct_outside_displayed_skin_audit"], "outside own skin", zz["muscles_gt5pct_outside_own_skin"], "worst mm", zz["worst_muscle_outside_displayed_skin_mm"])
        g = {}
        for i, x in r["moved"].items():
            g.setdefault(x["group"], []).append(x)
        for k, xs in g.items():
            print("  group", k, len(xs), "mean move %.2f max %.2f" % (sum(x["mean_move_mm"] for x in xs) / len(xs), max(x["max_move_mm"] for x in xs)))
        print("  outer-sheet move (needle skin depth):", {k: (v["mean_move_mm"], v["max_move_mm"]) for k, v in r["outer_sheet_move"].items() if v["mean_move_mm"] > 0.3})


if __name__ == "__main__":
    main()
