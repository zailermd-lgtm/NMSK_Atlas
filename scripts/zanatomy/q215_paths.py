"""Q215: re-point the (unchanged) Q204 / Q198 audit code at the Q215 own female page (build/q215/viewer_f_hr) and, as `before`, at the Q214 page (build/q214/viewer_f_hr).  Import BEFORE any q204_* / q198_*
module.  Raw output = build/q215_raw.  Own pages: continuations `*_zfill*` merged into their structure (the Q204 rule); the wrist pieces of HIS CT re-segmentation do not exist on the female page.
Keys: own_f = Q215 page, before_f = Q214 page."""
import os
os.environ["Q204_RAW"] = "build/q215_raw"
os.environ.pop("Q204_MERGE", None)
from scripts.zanatomy import q204_paths as P  # noqa: E402
from scripts.zanatomy import q198_load as L  # noqa: E402

PAGES = {"own_f": ("../q215/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction, Q215)"),
         "before_f": ("../q214/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (Q214, before)")}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
_raw_load = L.load


def _load(key, with_markers=False):
    S = _raw_load(key, with_markers)
    if L.MODELS[key][2] != "own":
        return S
    return P.merge_zfill(S)


L.load = _load
