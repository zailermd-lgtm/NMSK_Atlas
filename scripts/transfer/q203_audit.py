#!/usr/bin/env python3
"""Q203: the Q198 audit (scripts/zanatomy/q198_audit.py, reused unedited) on a page set, continuations merged into the structure they continue.
    python3 scripts/transfer/q203_audit.py own_m|own_f --pages build/q203 --tag after [--joints shoulder,elbow,...]  ->  data/derived/Q203_model_<key>_<tag>.json
Continuation entries `<id>_zfill` (Q200) and `<id>_zfill203` (Q203) are merged into `<id>` for the metrics (the planar closure of the continuation lies on
the measured cap, so the covered cap faces are dropped); the viewer keeps them as separate, badged entries."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

SUFFIXES = ("_zfill", "_zfill203")


def base_of(i):
    for s in SUFFIXES:
        if i.endswith(s):
            return i[: -len(s)]
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    key = args[0]
    opt = {"--pages": "build/q203", "--tag": "after", "--joints": ""}
    for k in list(opt):
        if k in args:
            opt[k] = args[args.index(k) + 1]
    pages = REPO / opt["--pages"]
    from scripts.zanatomy import q198_load as L
    L.Q = pages
    from scripts.zanatomy import q198_audit as A
    from scripts.transfer.q200_merge import merge_structure
    body = "vhm" if key == "own_m" else "vhf"
    seams = {}
    for p in (f"Q200_seams_{body}.json", f"Q203_seams_{body}.json"):
        if (REPO / "data/derived" / p).exists():
            seams.update(json.loads((REPO / "data/derived" / p).read_text()))
    _orig_load = A.load

    def load_merged(k):
        S = _orig_load(k)
        by = {}
        for s in S:
            by.setdefault(s["id"], s)
        out = []
        n = 0
        for s in S:
            b = base_of(s["id"])
            if b and b in by:
                m = by[b]
                v, f, info = merge_structure(m["v"], m["f"], s["v"], s["f"], seams.get(s["id"], []), weld=True)
                m["v"], m["f"] = v, f
                n += 1
                continue
            out.append(s)
        print("merged continuations:", n, flush=True)
        return out
    A.load = load_merged
    tmp = REPO / "data" / "derived" / f"_q203_tmp_{key}_{opt['--tag']}"
    tmp.mkdir(parents=True, exist_ok=True)
    A.OUT = tmp
    sys.argv = [sys.argv[0], key] + (["--joints", opt["--joints"]] if opt["--joints"] else [])
    A.main()
    for p in tmp.glob("Q198_model_*.json"):
        p.rename(REPO / "data" / "derived" / f"Q203_model_{key}_{opt['--tag']}.json")
    try:
        tmp.rmdir()
    except OSError:
        pass
