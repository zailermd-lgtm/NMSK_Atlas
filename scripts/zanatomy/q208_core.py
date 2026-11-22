"""Q208 core: pages (Q207 = before, Q208 = after), side groups, and the shared state paths."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402

PAGES = {
    "male": dict(src=REPO / "build/q207/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", out=REPO / "build/q208/viewer_zan_vhm", raw_src=REPO / "build/q197/viewer_zan_atlas", raw_stem="atlas_viewer_zan_atlas"),
    "female": dict(src=REPO / "build/q207/viewer_zan_female", stem="atlas_viewer_zan_female", out=REPO / "build/q208/viewer_zan_female", raw_src=REPO / "build/q197/viewer_base_female", raw_stem="atlas_viewer_base_female"),
}
BUILD = REPO / "build" / "q208"

TUBE = ("anterior_region_of_forearm", "posterior_region_of_forearm", "lateral_border_of_forearm", "medial_border_of_forearm", "anterior_region_of_wrist", "posterior_region_of_wrist")
ELBOW = ("anterior_region_of_elbow", "posterior_region_of_elbow", "cubital_fossa")
WRIST_NB = ("palm", "dorsum_of_hand", "radial_foveola")
ARM_NB = ("anterior_region_of_arm", "posterior_region_of_arm")


def load(which, src=None):
    cfg = PAGES[which]
    pg = C7.Page(which, src=src or cfg["src"], stem=cfg["stem"])
    raw = C7.Page(which, src=cfg["raw_src"], stem=cfg["raw_stem"])
    return pg, raw


def pid(name, side):
    return f"zan_skin_{name}_{side}"


def state_path(which, stage):
    BUILD.mkdir(parents=True, exist_ok=True)
    return BUILD / f"{which}_{stage}.pkl"


def side_bones(page, side):
    """vertices of the bones of the arm / forearm / hand of one side (for the outer-sheet test of the skin slabs)"""
    s = "_" + side
    ids = [i for i in page.ids if page.sys(i) == "bone" and i.endswith(s) and any(k in i for k in ("humerus", "radius", "ulna", "carpal", "scaphoid", "lunate", "triquetrum", "pisiform", "trapezi", "capitate", "hamate", "metacarpal", "phalan", "finger_of_hand", "scapula", "clavicle"))]
    return np.vstack([page.v(i) for i in ids])
