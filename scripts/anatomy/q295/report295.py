#!/usr/bin/env python3
"""Q295: one report from the audit / voxel / mesh / thickness outputs -> data/derived/Q295_fat_report.json (+ the Phase-1 audit table)."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
W = Path("/dev/shm/q295")
KEYS = ["own_f", "own_m", "base_f", "base_m", "comb_f", "comb_m"]
PAGE = {"own_f": "Imaging-based Female", "own_m": "Imaging-based Male", "base_f": "Base Female", "base_m": "Base Male",
        "comb_f": "Combined Female", "comb_m": "Combined Male"}
CVH = {"22_Bartholin_s_gland": 31.7, "37_Bulbospongiosus_muscle": 27.6, "24_Perineal_body": 29.5}


def j(p):
    p = Path(p); return json.loads(p.read_text()) if p.exists() else None


def main():
    out = {"_README": ["Q295 fat and voids audit (scripts/anatomy/q295/): per page and region, the area inside the skin that no structure covers "
                       "(void), before (the Q293 pages) and after (with the Q295 fat / unlabelled-soft-tissue meshes); what the body's own imaging "
                       "shows in the voids; the shipped meshes (volume, triangles, mesh defects, mean dihedral vs CVH references); fat penetration "
                       "into other structures (share of the fat's section area that another non-fat structure also covers)."],
           "method": {"levels_per_region": 30, "pixel_mm": 1.0, "skin_layer_mm": 1.5,
                      "regions": "head, neck, thorax, abdomen, pelvis, thigh, knee, leg, foot, upper arm, forearm, hand (by the page's own bone landmarks)",
                      "fill": "nonzero winding per structure; open meshes outline + fill-holes; sheets (fascia, joint, bursa, insertion) outline only; hidden-by-default structures not counted"},
           "cvh_reference_dihedral_deg": CVH, "pages": {}}
    for k in KEYS:
        b, a = j(W / f"audit/{k}_before.json"), j(W / f"audit/{k}_after.json")
        fat, vox, th = j(W / f"fat/{k}_fat.json"), j(W / f"fat/{k}_vox.json"), j(W / f"fat/{k}_thick.json")
        P = {"page": PAGE[k]}
        if b:
            P["regions"] = {}
            for r, v in b["regions"].items():
                e = {"y_range": v["y_range"], "void_before": v["void_frac"], "void_sub_before": v["void_sub_frac"], "void_deep_before": v["void_deep_frac"],
                     "overlap_before": v["overlap_frac"], "holes_gt5mm_before": v["holes_gt5mm"], "max_hole_mm_before": v["max_hole_diam_mm"],
                     "deep_spaces_before_cm2": dict(list(v["deep_spaces_cm2"].items())[:6]),
                     "imaging_in_sub_void_before": v["imaging_in_sub_void"], "imaging_in_deep_void_before": v["imaging_in_deep_void"]}
                if a and r in a["regions"]:
                    w = a["regions"][r]
                    e.update({"void_after": w["void_frac"], "void_sub_after": w["void_sub_frac"], "void_deep_after": w["void_deep_frac"],
                              "holes_gt5mm_after": w["holes_gt5mm"], "max_hole_mm_after": w["max_hole_diam_mm"],
                              "fat_area_frac_after": w.get("fat_area_frac"), "fat_penetration_frac": w.get("fat_overlapping_other_frac"),
                              "overlap_nonfat_after": w.get("overlap_nonfat_frac"), "imaging_in_deep_void_after": w["imaging_in_deep_void"]})
                P["regions"][r] = e
        if vox:
            P["voxels_L"] = {x: round(vox[x] / 1e6, 2) for x in ("body", "void", "fat", "soft", "gas", "unknown", "propagated")}
            P["soft_void_identified_by_imaging_page_cm3"] = vox.get("soft_void_identified_by_imaging_page_cm3")
        if fat:
            agg = {}
            for u, d in fat.items():
                g = agg.setdefault(d["kind"], {"meshes": 0, "mesh_cm3": 0, "tris": 0, "defect_edges": 0, "edges": 0, "_dw": 0, "watertight": 0})
                g["meshes"] += 1; g["mesh_cm3"] += d["mesh_cm3"]; g["tris"] += d["tris"]; g["defect_edges"] += d["boundary_edges"] + d["nonmanifold_edges"]
                g["edges"] += d["edges"]; g["_dw"] += d["dihedral_mean_deg"] * d["tris"]; g["watertight"] += int(d["watertight"])
            for g in agg.values():
                g["dihedral_mean_deg"] = round(g.pop("_dw") / max(g["tris"], 1), 1); g["mesh_cm3"] = round(g["mesh_cm3"], 1)
                g["defect_edge_frac"] = round(g["defect_edges"] / max(g["edges"], 1), 4)
            P["shipped"] = agg; P["triangles_total"] = sum(g["tris"] for g in agg.values())
            P["meshes"] = {u: {x: d[x] for x in ("name", "kind", "mesh_cm3", "tris", "mc_step_mm", "dihedral_mean_deg", "watertight")} for u, d in fat.items()}
        if th:
            P["left_out"] = th
        out["pages"][k] = P
    (Path(__import__("os").environ.get("Q295_FAT_REPORT", str(REPO / "data/derived/Q295_fat_report.json")))).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, P in out["pages"].items():
        if "regions" in P:
            print(k, " ".join(f"{r}:{e['void_before']:.2f}->{e.get('void_after', float('nan')):.2f}" for r, e in P["regions"].items()))
        if "shipped" in P:
            print("   ", {kk: (v["mesh_cm3"], v["tris"], v["dihedral_mean_deg"]) for kk, v in P["shipped"].items()})


if __name__ == "__main__":
    main()
