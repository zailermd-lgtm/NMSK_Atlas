#!/usr/bin/env python3
"""Q212: the Q198 audit (q198_audit, unedited) on the Q212 page, exactly as q203_audit.py (continuations `_zfill`, `_zfill203`, `_zfill203s`, `_zfill212` merged into their structure) plus the
HIS-wrist pieces: the hidden superseded entries (`carpals_r/l`, `ulna_r_zfill203s`) are dropped, `carpals_?_q212` takes the id `carpals_?`, and `<radius|ulna>_?_distal_q212` is merged into its
bone (the cap of the measured bone it abuts is interior).
    python3 scripts/transfer/q212_audit.py own_m|own_f --pages build/q212 --tag after212 [--joints ...]  ->  data/derived/Q212_model_<key>_<tag>.json"""
import json
import sys
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
SUFFIXES = ("_zfill", "_zfill203", "_zfill203s", "_zfill212")
HIDE = {"carpals_r", "carpals_l", "ulna_r_zfill203s"}


def base_of(i):
    for s in SUFFIXES:
        if i.endswith(s):
            return i[: -len(s)]
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    key = args[0]
    opt = {"--pages": "build/q212", "--tag": "after212", "--joints": ""}
    for k in list(opt):
        if k in args:
            opt[k] = args[args.index(k) + 1]
    from scripts.zanatomy import q198_load as L
    L.Q = REPO / opt["--pages"]
    from scripts.zanatomy import q198_audit as A
    from scripts.transfer.q200_merge import merge_structure
    from scripts.transfer.q200_continue import find_caps
    body = "vhm" if key == "own_m" else "vhf"
    seams = {}
    for p in (f"Q200_seams_{body}.json", f"Q203_seams_{body}.json", f"Q212_seams_{body}.json"):
        if (REPO / "data/derived" / p).exists():
            seams.update(json.loads((REPO / "data/derived" / p).read_text()))
    _orig_load = A.load

    def load_merged(k):
        S = _orig_load(k)
        has_wrist = any(s["id"].endswith("_q212") for s in S)
        if has_wrist:
            S = [s for s in S if s["id"] not in HIDE]
            for s in S:
                if s["id"] in ("carpals_r_q212", "carpals_l_q212"):
                    s["id"] = s["id"][:-5]
        by = {}
        for s in S:
            by.setdefault(s["id"], s)
        out, n = [], 0
        for s in S:
            b = base_of(s["id"])
            if b and b in by:
                m = by[b]
                v, f, info = merge_structure(m["v"], m["f"], s["v"], s["f"], seams.get(s["id"], []), weld=True)
                m["v"], m["f"] = v, f
                n += 1
                continue
            if s["id"].endswith("_distal_q212"):
                m = by.get(s["id"][: -len("_distal_q212")])
                caps = find_caps(m["v"], m["f"], minarea=20.0, at_end=2.5)
                cen = s["v"].mean(0)
                near = [c for c in caps if np.linalg.norm(m["v"][np.unique(m["f"][c["faces"]])].mean(0) - cen) < 30.0]
                cov = [dict(axis=c["axis"], pos=c["pos"], polys=[np.asarray(p.exterior.coords)[:-1].tolist() for p in c["polys"]]) for c in near]   # none: the old label cut is not a flat plane
                v, f, info = merge_structure(m["v"], m["f"], s["v"], s["f"], cov, weld=True)
                m["v"], m["f"] = v, f
                n += 1
                print("wrist piece merged", s["id"], info, flush=True)
                continue
            out.append(s)
        print("merged continuations:", n, flush=True)
        return out
    A.load = load_merged
    tmp = REPO / "data" / "derived" / f"_q212_tmp_{key}_{opt['--tag']}"
    tmp.mkdir(parents=True, exist_ok=True)
    A.OUT = tmp
    sys.argv = [sys.argv[0], key] + (["--joints", opt["--joints"]] if opt["--joints"] else [])
    A.main()
    for p in tmp.glob("Q198_model_*.json"):
        p.rename(REPO / "data" / "derived" / f"Q212_model_{key}_{opt['--tag']}.json")
    try:
        tmp.rmdir()
    except OSError:
        pass
