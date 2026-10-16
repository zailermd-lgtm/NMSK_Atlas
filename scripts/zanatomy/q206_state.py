"""Q206 state loader: the full-resolution state behind the published Q205 pages.
male   : build/q201/after_q201.npz (= the Q202 page's soft tissue) + the Q205 dumps (hands, shoulder)  -> Q205 state
female : build/q205/after_q199.npz (= the Q202 page's soft tissue) + build/q205/female_state.npz       -> Q205 state
`pre` = the state before Q205 (same topology), `cur` = the Q205 state, `raw` = Z source vertices.  Pages: build/q205/viewer_zan_{vhm,female}."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

CFG = {
    "male": dict(state=REPO / "build/q201/after_q201.npz", dumps=[REPO / "build/q205/male_state_hands.npz", REPO / "build/q205/male_state_shoulder.npz"],
                 page=REPO / "build/q205/viewer_zan_vhm", stem="atlas_viewer_zan_male_fitted", out=REPO / "build/q206/viewer_zan_vhm", key="q205_m", key6="q206_m", body="vhm"),
    "female": dict(state=REPO / "build/q205/after_q199.npz", dumps=[REPO / "build/q205/female_state.npz"],
                   page=REPO / "build/q205/viewer_zan_female", stem="atlas_viewer_zan_female", out=REPO / "build/q206/viewer_zan_female", key="q205_f", key6="q206_f", body="vhf"),
}


def load(which):
    """-> by_cur {id: {v,f,cat,r}}, v_pre {id: v}, notes {id: fit_note of the Q205 dumps}"""
    cfg = CFG[which]
    if which == "male":
        from scripts.zanatomy import q205_male as M
        by, raw = M.load_all(str(cfg["state"]))
    else:
        from scripts.zanatomy import q205_female as F
        by, raw = F.load_all(str(cfg["state"]))
    v_pre = {i: d["v"].copy() for i, d in by.items()}
    for p in cfg["dumps"]:
        z = np.load(p, allow_pickle=False)
        ids = json.loads(str(z["ids"]))
        for k, i in enumerate(ids):
            if i in by:
                by[i]["v"] = z[f"v{k}"].astype(float)
    return by, v_pre, raw
