#!/usr/bin/env python3
"""Q200: before (Q198_model_*.json, unedited pages) -> after (Q200_model_*_elbow.json, same audit code on the Q200 pages) at every own-model elbow.
Writes data/derived/Q200_before_after.json and prints the table."""
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "derived"


def metrics(j):
    if j is None:
        return None
    soft = [s for s in j["soft"] if "error" not in s]
    mus = [s for s in soft if s["sys"] in ("muscle", "tendon")]
    flat = [s["id"] for s in mus if any(c["area_mm2"] >= 40 for c in s.get("flat_caps", []))]
    flat_area = sum(c["area_mm2"] for s in mus for c in s.get("flat_caps", []) if c["area_mm2"] >= 40)
    det = []
    for s in soft:
        for end, ent in (s.get("attach_ends_in_zone") or {}).items():
            d = ent.get("min_expected_bone_mm")
            if d is not None and d > 5.0:
                det.append((s["id"], end, d))
    mo = j.get("muscle_overlap") or {}
    buried = [k for k, v in mo.items() if v and v.get("overlap_pct", 0) > 60]
    isl = [s["id"] for s in soft if s.get("max_island_gap_mm", 0) > 5 and s.get("max_island_share_gt5mm", 0) > 0.02]
    bd = j.get("bones_detail") or []
    return dict(bone_gap_mm=j["bones"].get("surface_gap_mm"), max_penetration_mm=j["bones"].get("max_penetration_mm"),
                bones_present=[b["id"] for b in bd], bones_with_flat_cap=[b["id"] for b in bd if b.get("flat_caps")],
                n_muscles_zone=len(mus), muscles_cut_flat=len(flat), flat_cap_area_mm2=round(flat_area),
                ends_over_5mm=len(det), worst_end_mm=round(max([d for _, _, d in det], default=0.0), 1), ends_list=[(a, b, round(c, 1)) for a, b, c in det][:30],
                buried_over_60pct=len(buried), disconnected=len(isl),
                flexion=j["elbow_angles"].get("flexion_deg"), carrying=j["elbow_angles"].get("carrying_deg_lateral_positive"), twist=j["elbow_angles"].get("ulna_vs_epicondylar_twist_deg"))


def main():
    out = {}
    for key, name in (("own_m", "own male"), ("own_f", "own female")):
        old = json.loads((D / f"Q198_model_{key}.json").read_text())
        new = json.loads((D / f"Q200_model_{key}_elbow.json").read_text())
        for side in "lr":
            jo = next((j for j in old["junctions"] if j["name"] == "elbow" and j["side"] == side), None)
            jn = next((j for j in new["junctions"] if j["name"] == "elbow" and j["side"] == side), None)
            out[f"{key}_{side}"] = dict(before=metrics(jo), after=metrics(jn))
    (D / "Q200_before_after.json").write_text(json.dumps(out, indent=1))
    for k, v in out.items():
        b, a = v["before"], v["after"]
        print(f"== {k}")
        for m in ("bones_present", "bone_gap_mm", "bones_with_flat_cap", "n_muscles_zone", "muscles_cut_flat", "flat_cap_area_mm2", "ends_over_5mm", "worst_end_mm", "buried_over_60pct", "disconnected", "twist"):
            print(f"  {m:22s} {str((b or {}).get(m))[:60]:62s} -> {str((a or {}).get(m))[:60]}")


if __name__ == "__main__":
    main()
