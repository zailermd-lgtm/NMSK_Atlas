#!/usr/bin/env python3
"""Q212: Q204 regional pass (unchanged code) on the Q203 pages (build/q209_raw_merged, from Q209) vs the Q212 pages (build/q212_raw): per own page the structures with a
major (sev 3) / moderate (sev 2) finding in total and per defect kind (cause groups of q204_aggregate), flat cut faces, ends off bone, bone-bone penetration volume.
    python3 scripts/zanatomy/q212_regions_compare.py  ->  data/derived/Q212_regional_before_after.json"""
import json
from collections import Counter
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
CAUSE = {"flat_cut_face": "block_seam_or_cut", "bone_flat_cut": "block_seam_or_cut", "end_off_bone": "attachment_off_bone", "disconnected_island": "fragmented_mesh", "bone_island": "fragmented_mesh",
         "muscle_interpenetration": "muscle_overlap", "inside_bone": "soft_inside_bone", "bone_penetration": "bone_overlap"}


def summarize(path):
    d = json.loads(Path(path).read_text())
    rows = d["rows"]
    sev = Counter(); kinds = Counter(); reg = {}
    flat = 0; flat_area = 0.0; flat_struct = 0; ends = 0
    for r in rows:
        m = max([x["severity"] for x in r.get("defects", [])], default=0)
        sev[m] += 1
        for x in r.get("defects", []):
            if x["severity"] >= 2:
                kinds[CAUSE.get(x["check"], x["check"])] += 1
        reg.setdefault(r.get("region", "?"), Counter())[m] += 1
        if r.get("flat_caps"):
            flat_struct += 1; flat += len(r.get("flat_caps", [])); flat_area += sum(c.get("area_mm2", 0) for c in r.get("flat_caps", []))
        ends += sum(1 for k, a in (r.get("attach_ends") or {}).items() if a.get("min_any_bone_mm", 0) > 5.0)
    pen = d["bone_penetrating_pairs"]
    return dict(structures=len(rows), major=sev[3], moderate=sev[2], minor=sev[1], clean=sev[0], defects_sev_ge2_by_kind=dict(kinds), structures_with_flat_cap=flat_struct, flat_caps=flat,
                flat_cap_area_mm2=round(flat_area), muscle_ends_gt5mm_from_bone=ends, bone_pairs_penetrating=len(pen), bone_penetration_mm3=round(sum(p["vol_mm3"] for p in pen)),
                region_major_plus_moderate={k: v[3] + v[2] for k, v in reg.items()})


out = {}
for key in ("own_m", "own_f"):
    a = summarize(REPO / f"build/q209_raw_merged/Q204_regions_{key}.json"); b = summarize(REPO / f"build/q212_raw/Q204_regions_{key}.json")
    out[key] = dict(q203_page=a, q212_page=b)
    print(key)
    for k in a:
        if a[k] != b[k]:
            print("  ", k, a[k], "->", b[k])
(REPO / "data/derived/Q212_regional_before_after.json").write_text(json.dumps(out, indent=1))
