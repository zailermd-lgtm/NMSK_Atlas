#!/usr/bin/env python3
"""Q206: which structures moved more than 5 mm (max vertex) between the Q205 and the Q206 page -> data/derived/Q206_moved_over_5mm.json, for the main session to regenerate motor points / risk
(clinical/ is read-only here).  Muscles: none are in the Q206 scope.   python3 scripts/zanatomy/q206_clinical.py"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P  # noqa: E402
from scripts.zanatomy import q206_state as ST  # noqa: E402


def main():
    out = {"threshold_mm": 5.0, "note": "max vertex change between the Q205 page and the Q206 page of the same structure; no bone, muscle or skin patch is in the Q206 scope"}
    for which in ("male", "female"):
        cfg = ST.CFG[which]
        diff = json.loads((REPO / "data" / "derived" / f"Q206_ship_diff_{which}.json").read_text())
        man, _ = P.load_page(cfg["out"], cfg["stem"])
        sysof = {m["id"]: m["sys"] for m in man["meshes"]}
        risk = set()
        rf = cfg["page"] / "clinical_risk.json"
        if rf.exists():
            risk = {s.get("id") for s in json.loads(rf.read_text())["structures"]}
        rows = {"vessel": [], "nerve": [], "muscle": [], "other": []}
        for i, x in diff["geometry_changed"].items():
            mv = x["max_vertex_change_mm"]
            if mv is None or mv <= 5.0:
                continue
            k = sysof[i] if sysof[i] in rows else "other"
            rows[k].append({"id": i, "sys": sysof[i], "max_vertex_change_mm": mv, "in_clinical_risk_file": i in risk})
        for k in rows:
            rows[k].sort(key=lambda r: -r["max_vertex_change_mm"])
        out[which] = {"counts_over_5mm": {k: len(v) for k, v in rows.items()}, "structures": rows}
    (REPO / "data" / "derived" / "Q206_moved_over_5mm.json").write_text(json.dumps(out, indent=1))
    for w in ("male", "female"):
        print(w, out[w]["counts_over_5mm"])


if __name__ == "__main__":
    main()
