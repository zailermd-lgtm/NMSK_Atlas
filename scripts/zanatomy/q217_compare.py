#!/usr/bin/env python3
"""Q217: before / after of the UNCHANGED Q204 regional audit on the two changed pages (own male Q214 -> Q217, Z male fitted Q211 -> Q217), read from build/q217_raw/Q204_regions_<key>.json (run
`python3 scripts/zanatomy/q217_audit.py regions KEY` for own_m own_m_a zan_m zan_m_a first).  Writes data/derived/Q217_regions_before_after.json: counts of findings (structures with a defect of severity >= 1 / >= 2, by region),
findings that appear / disappear, per changed structure the before / after rows."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q215_compare import findings, sev, KEYS  # noqa: E402

RAW = REPO / "build/q217_raw"


def rows(key):
    d = json.loads((RAW / f"Q204_regions_{key}.json").read_text())
    return {r["id"]: r for r in d["rows"]}


def cnt(R, region=None):
    rs = [r for r in R.values() if region is None or r.get("region") == region]
    s = [sev(r) for r in rs]
    return dict(structures=len(rs), sev_ge1=sum(1 for x in s if x >= 1), sev_ge2=sum(1 for x in s if x >= 2), sev3=sum(1 for x in s if x >= 3))


def main():
    out = {}
    for name, kb, ka, changed_file in (("own_male", "own_m", "own_m_a", "Q217_own_report.json"), ("z_male", "zan_m", "zan_m_a", "Q217_ship_diff_zan.json")):
        B, A = rows(kb), rows(ka)
        fb, fa = findings(B), findings(A)
        if name == "own_male":
            rep = json.loads((REPO / "data/derived" / changed_file).read_text())
            changed = sorted(set(rep["replaced"]) | set(rep["added"]))
        else:
            changed = sorted(json.loads((REPO / "data/derived" / changed_file).read_text())["geometry_changed"])
        reg = sorted({r.get("region") for r in A.values()} | {r.get("region") for r in B.values()} - {None})
        out[name] = dict(counts_before=cnt(B), counts_after=cnt(A), by_region={g: dict(before=cnt(B, g), after=cnt(A, g)) for g in reg if g},
                         new_findings=[list(x) for x in sorted(fa - fb)], removed_findings=[list(x) for x in sorted(fb - fa)],
                         changed_rows={i: dict(before={k: B[i].get(k) for k in KEYS}, after={k: A[i].get(k) for k in KEYS}) for i in changed if i in A and i in B})
        print(name, "before", out[name]["counts_before"], "after", out[name]["counts_after"], "| new", len(out[name]["new_findings"]), "removed", len(out[name]["removed_findings"]))
        for g, v in out[name]["by_region"].items():
            if g in ("arm_elbow_forearm", "wrist_hand", "shoulder"):
                print("   ", g, v["before"], "->", v["after"])
    (REPO / "data/derived/Q217_regions_before_after.json").write_text(json.dumps(out, indent=1, default=str) + "\n")


if __name__ == "__main__":
    main()
