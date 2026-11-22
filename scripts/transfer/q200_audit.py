#!/usr/bin/env python3
"""Q200: the Q198 elbow audit (scripts/zanatomy/q198_audit.py, reused unedited) on the Q200 own-model pages.
    python3 scripts/transfer/q200_audit.py own_m|own_f [--joints elbow] [--pages build/q200]  ->  data/derived/Q200_model_<key>_elbow.json
The pages are decoded from their own geo files exactly as for Q198, so before (Q198_model_*.json) and after use identical metrics."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

if __name__ == "__main__":
    pages = REPO / "build" / "q200"
    if "--pages" in sys.argv:
        i = sys.argv.index("--pages"); pages = (REPO / sys.argv[i + 1]); del sys.argv[i:i + 2]
    from scripts.zanatomy import q198_load as L
    L.Q = pages
    from scripts.zanatomy import q198_audit as A
    from scripts.transfer.q200_merge import merge_structure
    import json
    body = "vhm" if sys.argv[1] == "own_m" else "vhf"
    seams = json.loads((REPO / f"data/derived/Q200_seams_{body}.json").read_text())
    _orig_load = A.load

    def load_merged(key):
        S = _orig_load(key)
        by = {}
        for s in S:
            by.setdefault(s["id"], s)
        out, rep = [], {}
        for s in S:
            if s["id"].endswith("_zfill") and s["id"][:-6] in by:
                m = by[s["id"][:-6]]
                v, f, info = merge_structure(m["v"], m["f"], s["v"], s["f"], seams.get(s["id"], []))
                if "_orig" not in m:
                    m["_orig"] = (m["v"], m["f"])
                m["v"], m["f"] = v, f
                rep[m["id"]] = info
                continue
            out.append(s)
        print("merged continuations:", len(rep), flush=True)
        return out
    A.load = load_merged
    A.OUT = REPO / "data" / "derived" / "_q200_tmp"
    A.OUT.mkdir(parents=True, exist_ok=True)
    if "--joints" not in sys.argv:
        sys.argv += ["--joints", "elbow"]
    A.main()
    key = sys.argv[1]
    for p in A.OUT.glob("Q198_model_*.json"):
        p.rename(REPO / "data" / "derived" / p.name.replace("Q198_", "Q200_"))
    try:
        A.OUT.rmdir()
    except OSError:
        pass
