#!/usr/bin/env python3
"""Q237: classification counts of the FINAL pages (build/q237/<page dir>, after the fill) -> data/derived/Q237_after_counts.json
    python3 scripts/anatomy/q237/after_counts.py [build/q237]"""
from __future__ import annotations
import collections, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C, pairing as P  # noqa: E402
root = sys.argv[1] if len(sys.argv) > 1 else "build/q237"
out = {}
for k in C.KEYS:
    os.environ["Q237_SRC_" + k] = str(C.REPO / root / C.PAGES[k][4])
    r = P.run_page(k, 1, False)
    c = collections.Counter(u["cls"] for u in r["units"]); ck = collections.Counter(u.get("kind") for u in r["units"] if u["cls"] == "unmatched")
    out[k] = dict(dir=root + "/" + C.PAGES[k][4], meshes=r["n_structures"], paired=c["paired"], midline=c["midline"], lateralised=c["lateralised"], unmatched=c["unmatched"], missing_side=ck["missing_side"])
    print(k, out[k], flush=True)
(C.REPO / "data/derived/Q237_after_counts.json").write_text(json.dumps(out, indent=1) + "\n")
