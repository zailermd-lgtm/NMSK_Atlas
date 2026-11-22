#!/usr/bin/env python3
"""Q206: before (Q205 page) -> after (Q206 page) numbers of one Z page -> data/derived/Q206_summary_<male|female>.json (+ Q206_summary.json merged)
needs build/q204_raw/{Q198_model_<key>_*.json, Q204_regions_<key>.json}, data/derived/Q198_fitseams fake for the fit keys, Q206_continuity.json, the carry dump.
    python3 scripts/zanatomy/q206_summary.py male|female"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
RAW = REPO / "build" / "q204_raw"
KEYS = {"male": dict(before="q205_m", after="q206_m", pre="z_male_fit", base="z_male", fit="z_male_fit", ref="z_male"),
        "female": dict(before="q205_f", after="q206_f", pre="z_female_fit", base="z_base_f", fit="z_female_fit", ref="z_base_f")}


def ranked(key, fitkey, basekey, fs):
    import scripts.zanatomy.q206_paths  # noqa: F401
    from scripts.zanatomy import q198_rank as R
    files = sorted(RAW.glob(f"Q198_model_{key}_*.json"), key=lambda p: p.stat().st_size)
    res = json.loads(files[-1].read_text())
    base = json.loads((RAW / f"Q198_model_{basekey}.json").read_text())
    D, _ = R.build_model(fitkey, "zan", res, json.loads(Path(fs).read_text()), base)
    return D, res


def counts(D):
    out = {}
    for reg in ("shoulder", "elbow", "wrist"):
        for sd in "lr":
            c = Counter(d["severity"] for d in D if d["region"] == reg and d.get("side") == sd)
            out[f"{reg}_{sd}"] = [c[3], c[2], c[1]]
    return out


NONSOFT = ("muscle", "bone", "skin")


def soft_findings(D, res):
    """wrist-zone findings (severity >= 2) on non-bone / non-muscle structures, by check"""
    sysof = {}
    for j in res["junctions"]:
        for s in j.get("soft", []) + j.get("tubes", []):
            if "id" in s:
                sysof[s["id"]] = s.get("sys")
    rows = [d for d in D if d["region"] == "wrist" and d["severity"] >= 2 and d.get("structure") and sysof.get(d["structure"]) not in NONSOFT]
    return {"n": len(rows), "by_check": dict(Counter(d["check"] for d in rows)), "items": [[d["side"], d["structure"], d["check"], d["severity"], d["value"]] for d in sorted(rows, key=lambda d: (d["side"], -d["severity"], d["structure"]))]}


def zone_stats(res):
    """structures (non-muscle) of the wrist zone with the Q198 inside-bone / outside-skin measures"""
    out = {}
    for j in res["junctions"]:
        if j["name"] != "wrist":
            continue
        seen = {}
        for s in j.get("soft", []) + j.get("tubes", []):
            if "id" not in s or s.get("sys") in NONSOFT:
                continue
            seen[s["id"]] = s
        ib = [i for i, s in seen.items() if s.get("inside_bone_pct", 0) > 8 and s.get("inside_bone_max_mm", 0) > 3]
        osk = [i for i, s in seen.items() if s.get("outside_skin_max_mm", 0) > 5 and s.get("outside_skin_pct", 0) > 5]
        out[j["side"]] = {"structures": len(seen), "inside_bone_gt8pct_depth_gt3mm": len(ib), "outside_skin_gt5pct_excursion_gt5mm": len(osk),
                          "inside_bone_ids": sorted(ib), "outside_skin_ids": sorted(osk),
                          "mean_inside_bone_pct": round(float(np.mean([s.get("inside_bone_pct", 0) for s in seen.values()])), 2), "mean_outside_skin_pct": round(float(np.mean([s.get("outside_skin_pct", 0) for s in seen.values()])), 2)}
    return out


def regions(key):
    d = json.loads((RAW / f"Q204_regions_{key}.json").read_text())
    sv = lambda r: max([x["severity"] for x in r["defects"]] or [0])
    out = {}
    for reg in ("wrist_hand", "arm_elbow_forearm", "shoulder"):
        rows = [r for r in d["rows"] if r["region"] == reg]
        c = Counter(sv(r) for r in rows)
        soft = [r for r in rows if r["sys"] not in NONSOFT]
        ib = [r["id"] for r in soft if any(x["check"] == "inside_bone" and x["severity"] >= 2 for x in r["defects"])]
        os_ = [r["id"] for r in soft if any(x["check"] == "outside_skin" and x["severity"] >= 2 for x in r["defects"])]
        out[reg] = {"major": c[3], "moderate": c[2], "minor": c[1], "n": len(rows), "soft_inside_bone_sev2plus": len(ib), "soft_outside_skin_sev2plus": len(os_)}
    return out


def main(which):
    k = KEYS[which]
    out = {"keys": k}
    fsb = REPO / "build" / "q204_raw" / "fake" / "data" / "derived" / f"Q198_fitseams_{k['before']}.json"
    fsa = REPO / "build" / "q204_raw" / "fake" / "data" / "derived" / f"Q198_fitseams_{k['after']}.json"
    Db, rb = ranked(k["before"], k["fit"], k["base"], fsb)
    Da, ra = ranked(k["after"], k["fit"], k["base"], fsa)
    out["wrist_junction_major_moderate_minor"] = {"before": counts(Db), "after": counts(Da)}
    out["wrist_structures_findings_ge_moderate"] = {"before": soft_findings(Db, rb), "after": soft_findings(Da, ra)}
    out["wrist_zone_soft_stats"] = {"before": zone_stats(rb), "after": zone_stats(ra)}
    out["regions"] = {"before": regions(k["before"]), "after": regions(k["after"])}
    cont = json.loads((REPO / "data" / "derived" / "Q206_continuity.json").read_text())
    out["continuity_gap_mm"] = {n: cont.get(key) for n, key in (("unfitted_base", k["ref"]), ("q202_page", k["pre"]), ("q205_page", k["before"]), ("q206_page", k["after"]))}
    z = np.load(REPO / "build" / "q206" / f"{which}_state.npz", allow_pickle=False)
    rep = json.loads(str(z["report"]))
    moved = {}
    for sd, r in rep.items():
        for i, x in r["structures"].items():
            moved[i] = {k_: x.get(k_) for k_ in ("cat", "ladder", "mean_move_mm", "max_move_mm", "before", "after")}
    out["moved_structures"] = moved
    (REPO / "data" / "derived" / f"Q206_summary_{which}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k_: out[k_] for k_ in ("wrist_junction_major_moderate_minor",)}, default=float)[:1500])


if __name__ == "__main__":
    main(sys.argv[1])
