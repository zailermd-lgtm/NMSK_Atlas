"""Q214: re-point the (unchanged) Q204 / Q198 audit code at the two Q214 own pages (build/q214/viewer_{m,f}_hr) and, for the female, at the Q213 page (before). Import BEFORE any q204_* / q198_* module.
Raw output = build/q214_raw.  Own pages: continuations `*_zfill*` merged into their structure (the Q204 rule); the wrist pieces of HIS CT re-segmentation handled as in q212_paths.py (hidden
superseded entries dropped, `carpals_?_q212` takes the id `carpals_?`, `*_distal_q212` appended to its bone).  Keys: own_m / own_f = Q214 pages, before_m (Q212) / before_f (Q213)."""
import os
os.environ["Q204_RAW"] = "build/q214_raw"
os.environ.pop("Q204_MERGE", None)
from scripts.zanatomy import q204_paths as P  # noqa: E402
from scripts.zanatomy import q198_load as L  # noqa: E402
import numpy as np  # noqa: E402

PAGES = {"own_m": ("../q214/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (VH reconstruction, Q214)"),
         "own_f": ("../q214/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction, Q214)"),
         "before_m": ("../q212/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (Q212, before)"),
         "before_f": ("../q213/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (Q213, before)")}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
HIDE = {"carpals_r", "carpals_l", "ulna_r_zfill203s"}
_raw_load = L.load


def _load(key, with_markers=False):
    S = _raw_load(key, with_markers)
    if L.MODELS[key][2] != "own":
        return S
    if any(s["id"].endswith("_q212") for s in S):
        S = [s for s in S if s["id"] not in HIDE]
        by = {s["id"]: s for s in S}
        out = []
        for s in S:
            if s["id"] in ("carpals_r_q212", "carpals_l_q212"):
                s = dict(s); s["id"] = s["id"][:-5]
            elif s["id"].endswith("_distal_q212"):
                m = by[s["id"][: -len("_distal_q212")]]
                m["f"] = np.concatenate([m["f"], s["f"] + len(m["v"])]); m["v"] = np.concatenate([m["v"], s["v"]])
                continue
            out.append(s)
        S = out
    return P.merge_zfill(S)


L.load = _load
