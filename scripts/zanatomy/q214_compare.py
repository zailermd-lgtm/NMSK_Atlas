#!/usr/bin/env python3
"""Q214: before / after of the UNCHANGED Q204 regional audit on the two own pages (before = Q212 male / Q213 female, after = Q214), read from build/q214_raw (python3 scripts/zanatomy/q214_run.py q204_regions
before_m|own_m|before_f|own_f first).  Writes data/derived/Q214_regions_before_after.json: per body the rows of the added muscles (overlap, inside bone, flat caps, defects), the neighbours named in the task
(trapezius, semispinalis, longissimus, SCM / fibularis longus, EDL, soleus, ...) before -> after, every neighbour whose `overlap_pct` crossed the Q198 / Q204 line 40 / 60 %, and the findings
(structure, check, severity) that appear / disappear on the page."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "build/q214_raw"
NAMED = re.compile(r"^(trapezius|semispinalis_capitis|semispinalis_cervicis|longissimus|sternocleidomastoid|levator_scapulae|spinalis|multifidus|splenius|fibularis_longus|extensor_digitorum_longus|soleus|flexor_hallucis_longus|extensor_digitorum_brevis)_(r|l)$")


def rows(key):
    d = json.loads((RAW / f"Q204_regions_{key}.json").read_text())
    return {r["id"]: r for r in d["rows"]}


def sev(r):
    return max([d["severity"] for d in r.get("defects", [])] or [0])


def findings(R):
    return {(i, d["check"], d["severity"]) for i, r in R.items() for d in r.get("defects", [])}


def main():
    out = {}
    for body, kb, ka, rep in (("vhm", "before_m", "own_m", "Q214_vhm_report.json"), ("vhf", "before_f", "own_f", "Q214_vhf_report.json")):
        B, A = rows(kb), rows(ka)
        added = sorted(set(A) - set(B))
        fb, fa = findings(B), findings(A)
        new_f, gone_f = sorted(fa - fb), sorted(fb - fa)
        named = {}
        crossed = []
        for i, r in A.items():
            o = B.get(i)
            if not o or r.get("overlap_pct") is None or o.get("overlap_pct") is None:
                continue
            if NAMED.match(i):
                named[i] = dict(overlap_before=o["overlap_pct"], overlap_after=r["overlap_pct"], vol_cm3=r.get("vol_cm3"), severity_before=sev(o), severity_after=sev(r))
            for line in (40.0, 60.0):
                if (o["overlap_pct"] <= line < r["overlap_pct"]) and r.get("vol_cm3", 0) > 3:
                    crossed.append(dict(id=i, line=line, before=o["overlap_pct"], after=r["overlap_pct"], vol_cm3=r.get("vol_cm3")))
        def counts(R):
            c = {"structures": len(R), "defect_sev>=1": sum(1 for r in R.values() if sev(r) >= 1), "defect_sev>=2": sum(1 for r in R.values() if sev(r) >= 2)}
            c["muscle_interpenetration_sev>=1"] = sum(1 for r in R.values() if any(d["check"] == "muscle_interpenetration" for d in r.get("defects", [])))
            c["muscle_interpenetration_sev2"] = sum(1 for r in R.values() if any(d["check"] == "muscle_interpenetration" and d["severity"] >= 2 for d in r.get("defects", [])))
            c["inside_bone_findings"] = sum(1 for r in R.values() if any(d["check"] == "inside_bone" for d in r.get("defects", [])))
            return c
        out[body] = dict(
            added_rows={i: {k: A[i].get(k) for k in ("vol_cm3", "overlap_pct", "inside_bone_pct", "inside_bone_max_mm", "flat_caps", "outside_skin_pct", "attach_ends", "open_edge_frac")} | {"defects": A[i].get("defects", [])} for i in added},
            named_neighbours=named, neighbours_crossing_40_or_60=crossed, new_findings=[list(x) for x in new_f], removed_findings=[list(x) for x in gone_f],
            counts_before=counts(B), counts_after=counts(A))
        print(body, "added rows", added, "| new findings", len(new_f), "| neighbours crossing 40/60:", [(c["id"], c["line"]) for c in crossed][:12])
        print("   before", counts(B), "\n   after ", counts(A))
    (REPO / "data/derived/Q214_regions_before_after.json").write_text(json.dumps(out, indent=1) + "\n")


if __name__ == "__main__":
    main()
