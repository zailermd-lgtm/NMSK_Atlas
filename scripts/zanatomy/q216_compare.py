#!/usr/bin/env python3
"""Q216: before / after of the UNCHANGED Q204 regional audit on the own female page (before = Q215 page, after = Q216 page), read from build/q216_raw (run
`python3 scripts/zanatomy/q216_run.py q204_regions before_f` and `... own_f` first).  Writes data/derived/Q216_regions_before_after.json: per changed muscle the before / after Q204 row, the 14 findings that
Q215 added (Q215_regions_before_after.json `new_findings`) with their status now, every finding that appears / disappears on the page, the counts of findings by region and for the whole page, and every other
structure whose `overlap_pct` moved by >= 5 points or crossed the Q198 / Q204 line 40 / 60 %."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q215_compare import counts, findings, sev, KEYS  # noqa: E402

RAW = REPO / "build/q216_raw"


def rows(key):
    d = json.loads((RAW / f"Q204_regions_{key}.json").read_text())
    return {r["id"]: r for r in d["rows"]}


def main():
    B, A = rows("before_f"), rows("own_f")
    rep = json.loads((REPO / "data/derived/Q216_report.json").read_text())
    q15 = json.loads((REPO / "data/derived/Q215_regions_before_after.json").read_text())
    changed = sorted(set(rep["ops"]) | {z.replace("_zfill203s", "") for z in rep["welded"]})
    fb, fa = findings(B), findings(A)
    targeted = [tuple(x) for x in q15["new_findings"]]
    still = [list(x) for x in targeted if tuple(x) in fa]
    resolved = [list(x) for x in targeted if tuple(x) not in fa]
    kept_structs = set(rep["kept"])
    allowed = [list(x) for x in targeted if x[0] in kept_structs or x[0] in ("levator_ani_l",)]
    moved, crossed = {}, []
    for i, r in A.items():
        o = B.get(i)
        if not o or i in changed or r.get("overlap_pct") is None or o.get("overlap_pct") is None:
            continue
        if abs(r["overlap_pct"] - o["overlap_pct"]) >= 5.0 and r.get("vol_cm3", 0) > 3:
            moved[i] = dict(before=o["overlap_pct"], after=r["overlap_pct"], vol_cm3=r.get("vol_cm3"), severity_before=sev(o), severity_after=sev(r))
        for line in (40.0, 60.0):
            if (o["overlap_pct"] <= line < r["overlap_pct"]) and r.get("vol_cm3", 0) > 3:
                crossed.append(dict(id=i, line=line, before=o["overlap_pct"], after=r["overlap_pct"], vol_cm3=r.get("vol_cm3")))
    out = dict(
        changed_rows={i: dict(before={k: B[i].get(k) for k in KEYS} | {"defects": [(d["check"], d["severity"], d["detail"]) for d in B[i].get("defects", [])]},
                              after={k: A[i].get(k) for k in KEYS} | {"defects": [(d["check"], d["severity"], d["detail"]) for d in A[i].get("defects", [])]}) for i in changed if i in A and i in B},
        other_structures_overlap_moved_ge5=moved, neighbours_crossing_40_or_60=crossed,
        q215_new_findings_targeted=[list(x) for x in targeted], q215_findings_resolved=resolved, q215_findings_still_present=still, q215_findings_kept_with_reason=allowed,
        new_findings=[list(x) for x in sorted(fa - fb)], removed_findings=[list(x) for x in sorted(fb - fa)],
        counts_before=counts(B), counts_after=counts(A), by_region={reg: dict(before=counts(B, reg), after=counts(A, reg)) for reg in ("hip", "thigh", "abdomen_pelvis", "knee")})
    (REPO / "data/derived/Q216_regions_before_after.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print("changed", len(changed), "| Q215's 14 findings: resolved", len(resolved), "still present", still, "| new findings", out["new_findings"], "| removed", len(out["removed_findings"]), "| crossing 40/60:", [(c["id"], c["line"]) for c in crossed][:12])
    print("   before", out["counts_before"], "\n   after ", out["counts_after"])


if __name__ == "__main__":
    main()
