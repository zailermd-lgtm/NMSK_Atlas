#!/usr/bin/env python3
"""Q297: the measured volume of EVERY class (c) rule-based structure on all six pages.

The brief requires that a rule-based structure be badged rule-based in the UI and have its volume recorded. Most already
state a volume in their own badge; the generated connectors (tendon / ligament bridges, Q118 / Q122 / Q172 / Q248) and
the rule-tracked vessels and nerves state the landmarks, the calibre and the length that DEFINE the solid instead, which
is the same information in a different form but is not the number the brief asks for. Rather than rewrite those cards,
this script measures the enclosed volume of each of them straight off the shipped page geometry and records it here, so
every rule-based structure has a volume on file and `tests/test_q297.py` can assert 100 % coverage.

    python3 scripts/anatomy/q297/volumes297.py [--src BUILD_DIR] [--json data/derived/Q297_rule_based_volumes.json]"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import prov297 as P      # noqa: E402
import geo as G          # noqa: E402
import audit297 as A     # noqa: E402

OUT = REPO / "data/derived/Q297_rule_based_volumes.json"


def enclosed_cm3(v, f):
    vv = v[f]
    return float(np.einsum("ij,ij->i", vv[:, 0], np.cross(vv[:, 1], vv[:, 2])).sum() / 6.0 / 1000.0)



# Q308: the baseline is ASKED FOR, never written down here. `scripts/anatomy/q241/model.SRC` is the one place
# in this repository that declares which build the six pages come from, and `model.build_root()` reads it. A
# second copy of the literal goes stale silently the moment a round lands -- which is exactly what happened to
# this module: its default stayed `build/q296`, where the provenance audit reports d_unaccounted = 2, so every
# run without an explicit --src kept auditing the PRE-Q297 state and reporting it as today's.
def _baseline():
    import sys as _s
    _p = str(REPO / "scripts/anatomy/q241")
    if _p not in _s.path:
        _s.path.insert(0, _p)
    import model as _m
    return _m.build_root()


def run(src=None):
    src = src or _baseline()   # Q308: the current baseline, not a stale literal
    out = {"src": src, "note": ("signed enclosed volume of the shipped mesh, cm3; abs() because a few generated "
                                "connectors are wound inside-out, which does not change the solid they occupy"),
           "pages": {}}
    for key in P.KEYS:
        h, d, kind = P.page_html(key, src)
        L = P.subject_labels(h) if kind == "own" else {}
        rows = {}
        meshes = None
        if kind == "zan":
            b, me = G.zan_meshes(key, src)
            meshes = {}
            for r in me:
                q = np.frombuffer(b, np.uint16, r["vc"] * 3, r["vo"]).reshape(-1, 3).astype(np.float64)
                ff = np.frombuffer(b, np.uint16, r["ic"] * 3, r["io"]).reshape(-1, 3).astype(np.int64)
                meshes[r["id"]] = (np.asarray(r["min"]) + q / 65535.0 * np.asarray(r["span"]), ff)
        else:
            bj, b, decode = G.own_structures(key, src)
            meshes = {}
            for e, v, ff in decode(bj, b):
                meshes[e["id"]] = (np.asarray(v, float), np.asarray(ff, np.int64))
        for st in P.structures(key, src):
            cls, _, _ = A.classify(st, kind, L)
            if cls != "c_rule_based":
                continue
            g = meshes.get(st["id"])
            if g is None:
                rows[st["id"]] = None
                continue
            rows[st["id"]] = round(abs(enclosed_cm3(*g)), 5)
        out["pages"][key] = rows
        got = sum(1 for v in rows.values() if v is not None)
        print(f"  {P.LABEL[key]:12s} rule-based {len(rows):5d}  volumes measured {got:5d}  "
              f"total {sum(v for v in rows.values() if v):.2f} cm3")
    return out


def main(argv):
    src = argv[argv.index("--src") + 1] if "--src" in argv else _baseline()
    out = Path(argv[argv.index("--json") + 1]) if "--json" in argv else OUT
    rep = run(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print("written", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
