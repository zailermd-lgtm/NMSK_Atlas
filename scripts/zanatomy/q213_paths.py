"""Q213: re-point the (unchanged) Q204 / Q198 audit code at the two Q213 pages (own female build/q213/viewer_f_hr, Z fitted to her build/q213/viewer_zan_female). Import BEFORE any
q204_* / q198_* module. Raw output = build/q213_raw.  Own page: continuations `*_zfill*` merged into their structure (the Q204 rule); the wrist pieces of HIS CT re-segmentation do not exist on the
female page, so nothing else is needed."""
import os
os.environ["Q204_RAW"] = "build/q213_raw"
os.environ.pop("Q204_MERGE", None)
from scripts.zanatomy import q204_paths as P  # noqa: E402
from scripts.zanatomy import q198_load as L  # noqa: E402

PAGES = {"own_f": ("../q213/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction, Q213)"),
         "q213_f": ("../q213/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction (Q213)")}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
_raw_load = L.load


def _load(key, with_markers=False):
    S = _raw_load(key, with_markers)
    if L.MODELS[key][2] != "own":
        return S
    return P.merge_zfill(S)


L.load = _load
