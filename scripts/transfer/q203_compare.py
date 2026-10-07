#!/usr/bin/env python3
"""Q203: Q198 metrics before / after per junction from two audit JSONs (data/derived/Q203_model_<key>_<tag>.json).
    python3 scripts/transfer/q203_compare.py own_m BEFORE_TAG AFTER_TAG [--joints shoulder,elbow,...] [--json OUT]
Metrics per junction side: structures with a flat cap (axis-aligned planar end face >= 40 mm2, Q198 definition) / caps / cap area, bone caps,
muscle/tendon ends in the zone > 5 mm from any bone (attach_ends_in_zone), disconnected islands (structures with a small island > 5 mm away),
open loops, bone-bone gap / penetration, mean muscle overlap."""
import json
import sys
from pathlib import Path

D = Path(__file__).resolve().parents[2] / "data/derived"


def metrics(j):
    soft, bd = j.get("soft", []), j.get("bones_detail", [])
    caps = [(s["id"], c) for s in soft for c in s.get("flat_caps", [])]
    bcaps = [(s["id"], c) for s in bd for c in s.get("flat_caps", [])]
    ends = []
    for s in soft:
        for k, a in (s.get("attach_ends_in_zone") or {}).items():
            if a.get("min_any_bone_mm", 0) > 5.0:
                ends.append((s["id"], k, a["min_any_bone_mm"]))
    isl = [s["id"] for s in soft if s.get("max_island_gap_mm", 0) > 5.0 or s.get("max_island_share_gt5mm", 0) > 0]
    isl_b = [s["id"] for s in bd if s.get("max_island_gap_mm", 0) > 5.0]
    ov = j.get("muscle_overlap") or {}
    ovs = [v["overlap_pct"] for v in ov.values() if isinstance(v, dict) and "overlap_pct" in v]
    b = j.get("bones") or {}
    return dict(
        structs_with_flat_cap=len({i for i, _ in caps}), flat_caps=len(caps), flat_cap_area_mm2=round(sum(c["area_mm2"] for _, c in caps)),
        bone_flat_caps=len(bcaps), bone_flat_cap_area_mm2=round(sum(c["area_mm2"] for _, c in bcaps)),
        muscle_ends_gt5mm_from_bone=len(ends), worst_end_mm=round(max([e[2] for e in ends], default=0.0), 1),
        islands_gt5mm=len(isl) + len(isl_b), open_loops_in_zone=sum(s.get("open_loops_in_zone", 0) for s in soft),
        bone_gap_mm=b.get("surface_gap_mm"), bone_penetration_mm3=b.get("penetration_vol_mm3"),
        mean_muscle_overlap_pct=round(sum(ovs) / len(ovs), 1) if ovs else None, n_muscle_structs=len(soft))


def main():
    key, t0, t1 = sys.argv[1:4]
    joints = None
    if "--joints" in sys.argv:
        joints = sys.argv[sys.argv.index("--joints") + 1].split(",")
    A = json.loads((D / f"Q203_model_{key}_{t0}.json").read_text())
    B = json.loads((D / f"Q203_model_{key}_{t1}.json").read_text())
    ja = {(j["name"], j["side"]): j for j in A["junctions"]}
    jb = {(j["name"], j["side"]): j for j in B["junctions"]}
    out = {}
    for k in sorted(set(ja) & set(jb)):
        if joints and k[0] not in joints:
            continue
        ma, mb = metrics(ja[k]), metrics(jb[k])
        out[f"{k[0]}_{k[1]}"] = dict(before=ma, after=mb)
        print(f"{key} {k[0]}/{k[1]}:")
        for m in ma:
            if ma[m] != mb[m]:
                print(f"   {m}: {ma[m]} -> {mb[m]}")
    if "--json" in sys.argv:
        Path(sys.argv[sys.argv.index("--json") + 1]).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
