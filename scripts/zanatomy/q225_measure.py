#!/usr/bin/env python3
"""Q225 measurements on a page (exact 0.5 mm solids, Q223 rule): left-elbow bone pairs, patella | femur, floating-rib | vertebra, per-bone fit error against the person's OWN bone meshes.
    python3 scripts/zanatomy/q225_measure.py male|female PAGE_DIR LABEL      -> data/derived/Q225_bone_measures_<which>_<LABEL>.json
LABEL: base | q222 (the source page) | q225 (the result)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q225_core as K5  # noqa: E402
from scripts.zanatomy import q225_elbow as EL  # noqa: E402


def pairs_for(which):
    P = [("humerus_l", "ulna_l"), ("humerus_l", "radius_l"), ("radius_l", "ulna_l"), ("femur_l", "patella_l"), ("femur_r", "patella_r")]
    for s in "lr":
        P += [(f"zan_vertebra_t11", f"zan_eleventh_rib_{s}"), (f"zan_vertebra_t12", f"zan_twelfth_rib_{s}")]
    if which == "female":
        P.append(("zan_vertebra_t2", "zan_second_rib_l"))
    return P


def measure(which, pg, with_own=True):
    P = pairs_for(which)
    names = {x for p in P for x in p}
    out = {"pairs": EL.pair_table({n: pg.v(n) for n in names}, {n: pg.f(n) for n in names}, P)}
    if with_own:
        own = K5.own_bones(which)
        fe = {}
        for n, ok in (("ulna_l", "ulna_l"), ("radius_l", "radius_l"), ("humerus_l", "humerus_l"), ("patella_l", "patella_l"), ("patella_r", "patella_r"), ("femur_l", "femur_l"), ("femur_r", "femur_r"),
                      ("zan_eleventh_rib_l", "ribs_l"), ("zan_eleventh_rib_r", "ribs_r"), ("zan_twelfth_rib_l", "ribs_l"), ("zan_twelfth_rib_r", "ribs_r"), ("zan_second_rib_l", "ribs_l")):
            if n in pg.S and ok in own:
                fe[n] = dict(zip(("fit_to_own_mean_mm", "own_to_fit_mean_mm"), EL.evidence_error(pg.v(n), pg.f(n), own[ok])))
        out["fit_error_vs_own_bone"] = fe
    return out


if __name__ == "__main__":
    which, d, label = sys.argv[1:4]
    c = K5.PAGES[which]
    pg = K5.load(which, base=True) if label == "base" else K5.load(which, src=Path(d))
    r = measure(which, pg, with_own=label != "base")
    (REPO / "data" / "derived" / f"Q225_bone_measures_{which}_{label}.json").write_text(json.dumps(r, indent=1))
    print(json.dumps(r["pairs"], indent=0)[:3000])
