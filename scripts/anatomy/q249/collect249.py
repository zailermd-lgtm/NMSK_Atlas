"""Q249: what ships on which page.  collect(key) -> list of dict(id, name, latin, side, z_sys, cat, V, F, rec, report, subject) from data/derived/Q249_rule_<key>.{json,npz}."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
D = REPO / "data/derived"
SUBJ = {"own_f": "ct_vhf_rule_nerve_q249", "own_m": "ct_vhm_rule_nerve_q249"}


def collect(key):
    j = json.loads((D / f"Q249_rule_{key}.json").read_text()); z = np.load(D / f"Q249_rule_{key}.npz")
    items = []
    for sid, c in j["cards"].items():
        if f"{sid}__v" not in z.files:
            continue
        rep = j["structures"][sid]["report"]
        items.append(dict(id=sid, name=c["name"], latin=c["latin"], side=c["side"], z_sys="nerve", cat="nerve", V=z[f"{sid}__v"].astype(np.float64), F=z[f"{sid}__f"].astype(np.int64), rec=c["rec"],
                          kind="rule", report=rep, subject=SUBJ.get(key)))
    return items
