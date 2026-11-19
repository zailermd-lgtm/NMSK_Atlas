"""Q195: which Visible Human body the Z-Anatomy fitting code is currently aimed at.

The female modules (Q168 transfer, Q186c trunk refit, Q190 refinement, Q191 hand) were written for the VH female.  Everything
body-specific they read (bundle of own meshes, skin, CT label volume, Q168 report with the per-structure regions, body scale,
height scale of the hard-coded trunk heights) goes through this one context.  Default = "vhf" (values exactly the old constants,
so the female build is unchanged); `configure("vhm")` aims the same code at the VH male (build.py --target-body vhm).
Call configure() BEFORE the refit modules are imported (they copy BODY_SCALE at import)."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BODY = "vhf"
BODY_SCALE = 0.932        # Q168 female body scale
Y_SCALE = 1.0             # hard-coded female trunk heights (mm, atlas y) x this = the same landmark on the target body
BUNDLE_JSON = REPO / "build" / "viewer_f_hr" / "bundle.json"
REGION_REPORT = REPO / "data" / "derived" / "Q168_zan_to_vhf.json"


def configure(body: str) -> None:
    global BODY, BODY_SCALE, Y_SCALE, BUNDLE_JSON, REGION_REPORT
    if body == "vhf":
        BODY, BODY_SCALE, Y_SCALE = "vhf", 0.932, 1.0
        BUNDLE_JSON = REPO / "build" / "viewer_f_hr" / "bundle.json"
        REGION_REPORT = REPO / "data" / "derived" / "Q168_zan_to_vhf.json"
    elif body == "vhm":
        from scripts.transfer import zan_to_vhm_whole_body as M
        M.apply_male_units()
        from scripts.transfer import zan_to_vhf_whole_body as Q
        Q.TARGETS["vhm"] = (M.BUNDLE, M.REPORT)
        BODY, BUNDLE_JSON, REGION_REPORT = "vhm", M.BUNDLE, M.REPORT
        BODY_SCALE = float(json.loads(M.REPORT.read_text())["body_scale"])
        Y_SCALE = 1.0          # measured: his sternum/clavicle/cranium-base heights are 1.01-1.04 x hers (the body scale 1.058 is leg-driven), so the hard-coded trunk heights stay
    else:
        raise ValueError(body)
