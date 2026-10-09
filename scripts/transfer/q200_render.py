#!/usr/bin/env python3
"""Q200: elbow close-ups of an own-model bundle (anterior / posterior / medial / lateral + sagittal / coronal cuts), bones visible,
Z-filled continuations (`*_zfill`, Q200 subjects) in blue.   python3 scripts/transfer/q200_render.py BUNDLE_DIR OUT_DIR own_m|own_f [--no-hl]
Reuses scripts/zanatomy/q198_renders.py (read-only) and the Q198 joint frames of the unmodified bones."""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.zanatomy import q198_renders as R8  # noqa: E402


def to_q198(B):
    out = []
    for it in B.items:
        e = it["e"]
        v, f = B.mesh(it)
        rec = e.get("rec") or {}
        out.append(dict(id=e["id"], name=rec.get("name", e["id"]), sys=e["cat"], side={"right": "r", "left": "l"}.get(e.get("side"), "m"),
                        v=v, f=f, src=e.get("subject", ""), rec=rec))
    return out


def elbow_json(model, side):
    import json
    j = R8.elbow_json(model, side)
    if j is None:
        p = R8.DER / f"Q200_model_{model}_elbow.json"
        if p.exists():
            r = json.loads(p.read_text())
            j = next((x for x in r["junctions"] if x["name"] == "elbow" and x["side"] == side), None)
    return j


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle"); ap.add_argument("out"); ap.add_argument("model")
    ap.add_argument("--no-hl", action="store_true")
    ap.add_argument("--sides", default="lr")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    B = Bundle(a.bundle)
    S = to_q198(B)
    R8.OUT = Path(a.out)
    hl = None if a.no_hl else {s["id"]: (0.15, 0.45, 0.95) for s in S if s["src"].endswith("_q200") and s["sys"] not in ("vessel", "nerve")}
    hlb = {}
    for sd in a.sides:
        j = elbow_json(a.model, sd)
        if j is None:
            continue
        R8.surface_views(a.model, sd, S, j, hl=hl, tag=a.tag)
        for pl in ("sagittal", "coronal"):
            R8.section_view(a.model, sd, S, j, pl, hl=hl, tag=a.tag)
    print("rendered", a.out)


if __name__ == "__main__":
    main()
