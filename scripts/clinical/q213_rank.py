#!/usr/bin/env python3
"""Q213: rank the TARGET MUSCLES of the two female needle-layer pages by defect severity (before Q213 = pages Q212 / Q211; the audit is data/derived/Q213_target_muscle_audit.json).

Score per muscle = sum over both sides and both pages of
  5  no mesh on the page at all (own page)                       3  merged / mis-named Z id (opponens digiti minimi)      4  hidden by default (own page)
  3 / 2 / 1  Q204 inside-bone severity 3 / 2 / (sev 1 not counted)   2  muscle interpenetration (> 60 % inside other muscles, Q204 sev 2)
  1  flat cut face (Q204 sev 2)     1  detached island (sev >= 2)    1  motor-point rule FAILED / not placed (per rule and side, max 4 per page)
  1  muscle carried from the MALE and not scaled (own / male volume >= 0.9, own page)   1  no motor-point rule for this muscle (Q187 list)
    python3 scripts/clinical/q213_rank.py [--out data/derived/Q213_target_ranking.json]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "data/derived/Q213_target_ranking.json"))
    a = ap.parse_args()
    aud = json.loads((REPO / "data/derived/Q213_target_muscle_audit.json").read_text())
    cov = json.loads((REPO / "data/derived/Q213_motor_points_coverage_before.json").read_text())["viewers"]
    h = (REPO / "build/q212/viewer_f_hr/atlas_viewer_female.html").read_text(encoding="utf-8")
    b = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
    hidden = {e["id"] for e in b["structures"] if e.get("hidden_default")}
    notcovered = set(json.loads((REPO / "data/derived/Q187_motor_points_coverage.json").read_text())["muscles_without_usable_source"])
    fails = {"vhf": {}, "zan_f": {}}
    for vk in fails:
        for kind in ("failed", "not_placed"):
            for x in cov[vk][kind]:
                mu = re.sub(r"_(r|l)$", "", x["rule"].split()[0])
                fails[vk][mu] = fails[vk].get(mu, 0) + 1
    rows = {}
    for key, e in aud.items():
        mu, s = e["muscle"], e["side"]
        r = rows.setdefault(mu, {"muscle": mu, "score": 0, "items": []})
        add = lambda pts, why: (r.__setitem__("score", r["score"] + pts), r["items"].append(f"{why} (+{pts}, {s})"))
        if not e["ids"]["vhf"]:
            add(5, "no mesh on her own page")
        if any(i in hidden for i in e["ids"]["vhf"]):
            add(4, "hidden by default on her own page")
        for page, dkey in (("own", "own_defects"), ("Z", "zfit_defects")):
            for chk, sev, det in e.get(dkey, []):
                if chk == "inside_bone":
                    add(3 if sev >= 3 else 2, f"{page}: {det}")
                elif chk == "muscle_interpenetration":
                    add(2, f"{page}: {det}")
                elif chk == "flat_cut_face":
                    add(1, f"{page}: flat cut face")
                elif chk == "disconnected_island":
                    add(1, f"{page}: {det}")
        v = e["vox_cm3"]
        if e["ids"]["vhf"] and e.get("own_cls") == "transferred" and v["vhm"] and v["vhf"] / v["vhm"] >= 0.9:
            add(1, f"carried from the male, not scaled (own / male volume {v['vhf'] / v['vhm']:.2f})")
        if mu in notcovered:
            add(1, "no motor-point rule")
    for mu, r in rows.items():
        for vk, nm in (("vhf", "own"), ("zan_f", "Z")):
            n = min(4, fails[vk].get(mu, 0))
            if n:
                r["score"] += n
                r["items"].append(f"{nm}: {fails[vk][mu]} motor-point rule(s) failed / not placed (+{n})")
        if mu == "opponens_digiti_minimi":
            r["score"] += 6
            r["items"].append("Z: one mesh merges the hand muscle with a foot piece (+3 per side)")
    ranked = sorted(rows.values(), key=lambda r: -r["score"])
    Path(a.out).write_text(json.dumps(ranked, indent=1) + "\n")
    for r in ranked[:30]:
        print(f"{r['score']:3d} {r['muscle']:36s} " + "; ".join(r["items"])[:200])


if __name__ == "__main__":
    main()
