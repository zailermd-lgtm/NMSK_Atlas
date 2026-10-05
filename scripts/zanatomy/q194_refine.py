"""Q194 build hook (--q194-refine): bounded post-gap-closure refinements of the female Z-Anatomy viewer.  Everything not listed in the returned report stays bit-identical.

  1. LEFT FOREARM structures placed with her photograph-fitted left radius / ulna and her left-forearm cryosection photographs (scripts/zanatomy/q194_forearm.py)
  (2./3. hand and trunk leftovers: see q194_hand_trunk.py, added below when present)
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
LEFT_FIT = REPO / "data" / "derived" / "Q192_left_hand_fit.json"


def refine_pending(pending: list[dict], raw: dict, log=print) -> dict:
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    from scripts.zanatomy import q194_forearm as F
    by = {p["mesh_id"]: p for p in pending}
    rawd = {k: np.asarray(v, float) for k, v in raw.items()}
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    rep = {"rule": "scripts/zanatomy/q194_refine.py"}
    rep["left_forearm"] = F.refine_left_forearm(by, rawd, json.loads(LEFT_FIT.read_text()), regions, log=log)
    try:
        from scripts.zanatomy import q194_hand_trunk as HT
    except ImportError:
        HT = None
    if HT is not None:
        rep.update(HT.refine(by, rawd, regions, log=log))
    return rep
