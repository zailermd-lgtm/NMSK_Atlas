#!/usr/bin/env python3
"""Q215: before / after of the UNCHANGED Q204 regional audit on the own female page (before = Q214 page, after = Q215 page), read from build/q215_raw (run
`python3 scripts/zanatomy/q215_run.py q204_regions before_f` and `... own_f` first).  Writes data/derived/Q215_regions_before_after.json: per replaced muscle the before / after Q204 row (volume, overlap,
inside bone, islands, flat caps, defects), every other structure whose `overlap_pct` moved by >= 5 points or crossed the Q198 / Q204 line 40 / 60 %, the findings (structure, check, severity) that appear /
disappear on the page, and the counts of findings by region (hip, thigh, abdomen_pelvis, whole page) before / after."""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "build/q215_raw"


def rows(key):
    d = json.loads((RAW / f"Q204_regions_{key}.json").read_text())
    return {r["id"]: r for r in d["rows"]}


def sev(r):
    return max([d["severity"] for d in r.get("defects", [])] or [0])


def findings(R):
    return {(i, d["check"], d["severity"]) for i, r in R.items() for d in r.get("defects", [])}


KEYS = ("vol_cm3", "overlap_pct", "inside_bone_pct", "inside_bone_max_mm", "islands", "flat_caps", "open_edge_frac", "outside_skin_pct", "attach_ends", "length_mm", "region")


def counts(R, region=None):
    S = [r for r in R.values() if (region is None or r.get("region") == region)]
    mus = [r for r in S if r.get("sys") == "muscle"]
    return {"structures": len(S), "defect_sev>=1": sum(1 for r in S if sev(r) >= 1), "defect_sev>=2": sum(1 for r in S if sev(r) >= 2),
            "muscles": len(mus), "muscle_defect_sev>=2": sum(1 for r in mus if sev(r) >= 2),
            "inside_bone_findings": sum(1 for r in S if any(d["check"] == "inside_bone" for d in r.get("defects", []))),
            "muscle_interpenetration_sev>=1": sum(1 for r in S if any(d["check"] == "muscle_interpenetration" for d in r.get("defects", []))),
            "muscle_interpenetration_sev2": sum(1 for r in S if any(d["check"] == "muscle_interpenetration" and d["severity"] >= 2 for d in r.get("defects", []))),
            "flat_cut_findings": sum(1 for r in S if any(d["check"] == "flat_cut_face" for d in r.get("defects", [])))}


def main():
    B, A = rows("before_f"), rows("own_f")
    rep = json.loads((REPO / "data/derived/Q215_report.json").read_text())
    replaced = sorted(rep["replaced"])
    fb, fa = findings(B), findings(A)
    moved, crossed = {}, []
    for i, r in A.items():
        o = B.get(i)
        if not o or i in rep["replaced"] or r.get("overlap_pct") is None or o.get("overlap_pct") is None:
            continue
        if abs(r["overlap_pct"] - o["overlap_pct"]) >= 5.0 and r.get("vol_cm3", 0) > 3:
            moved[i] = dict(before=o["overlap_pct"], after=r["overlap_pct"], vol_cm3=r.get("vol_cm3"), severity_before=sev(o), severity_after=sev(r))
        for line in (40.0, 60.0):
            if (o["overlap_pct"] <= line < r["overlap_pct"]) and r.get("vol_cm3", 0) > 3:
                crossed.append(dict(id=i, line=line, before=o["overlap_pct"], after=r["overlap_pct"], vol_cm3=r.get("vol_cm3")))
    out = dict(
        replaced_rows={i: dict(before={k: B[i].get(k) for k in KEYS} | {"defects": [(d["check"], d["severity"], d["detail"]) for d in B[i].get("defects", [])]},
                               after={k: A[i].get(k) for k in KEYS} | {"defects": [(d["check"], d["severity"], d["detail"]) for d in A[i].get("defects", [])]}) for i in replaced if i in A and i in B},
        other_structures_overlap_moved_ge5=moved, neighbours_crossing_40_or_60=crossed,
        new_findings=[list(x) for x in sorted(fa - fb)], removed_findings=[list(x) for x in sorted(fb - fa)],
        counts_before=counts(B), counts_after=counts(A), by_region={reg: dict(before=counts(B, reg), after=counts(A, reg)) for reg in ("hip", "thigh", "abdomen_pelvis", "knee")},
        replaced_sum=dict(
            inside_bone_findings_before=sum(1 for i in replaced if any(d["check"] == "inside_bone" for d in B[i].get("defects", []))),
            inside_bone_findings_after=sum(1 for i in replaced if any(d["check"] == "inside_bone" for d in A[i].get("defects", []))),
            mean_inside_bone_pct_before=round(sum(B[i].get("inside_bone_pct") or 0 for i in replaced) / max(len(replaced), 1), 2),
            mean_inside_bone_pct_after=round(sum(A[i].get("inside_bone_pct") or 0 for i in replaced) / max(len(replaced), 1), 2),
            mean_overlap_pct_before=round(sum(B[i].get("overlap_pct") or 0 for i in replaced) / max(len(replaced), 1), 2),
            mean_overlap_pct_after=round(sum(A[i].get("overlap_pct") or 0 for i in replaced) / max(len(replaced), 1), 2),
            findings_sev_ge2_before=sum(1 for i in replaced if sev(B[i]) >= 2), findings_sev_ge2_after=sum(1 for i in replaced if sev(A[i]) >= 2)))
    (REPO / "data/derived/Q215_regions_before_after.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print("replaced", len(replaced), "| new findings", len(out["new_findings"]), "| removed", len(out["removed_findings"]), "| crossing 40/60:", [(c["id"], c["line"]) for c in crossed][:12])
    print("   before", out["counts_before"], "\n   after ", out["counts_after"], "\n   replaced sum", out["replaced_sum"])


if __name__ == "__main__":
    main()
