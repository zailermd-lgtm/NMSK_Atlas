"""Q217: point the (unchanged) Q198 / Q204 loaders at the four pages of the elbow task, BEFORE (current published) and AFTER (Q217).  Import BEFORE any q198_* / q204_* module.
Raw output = build/q217_raw (env Q204_RAW overrides).  Own pages: continuations `*_zfill*` merged into their structure (the Q204 rule).
keys: own_m (Q214 male page), own_f (Q216 female page), zan_m (Q211 Z male fitted), zan_f (Q213 Z female fitted)  =  BEFORE;  *_a = after (Q217; own_f / zan_f are unchanged and have no _a page unless built)."""
import os
os.environ.setdefault("Q204_RAW", "build/q217_raw")
os.environ.pop("Q204_MERGE", None)
from scripts.zanatomy import q204_paths as P  # noqa: E402
from scripts.zanatomy import q198_load as L  # noqa: E402

PAGES = {
    "own_m": ("../q214/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (Q214)"),
    "own_f": ("../q216/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (Q216)"),
    "zan_m": ("../q211/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q211)"),
    "zan_f": ("../q213/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction (Q213)"),
    "z_male": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Z male base"),
    "own_m_a": ("../q217/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (Q217)"),
    "zan_m_a": ("../q217/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q217)"),
}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
_raw_load = L.load


def _load(key, with_markers=False):
    S = _raw_load(key, with_markers)
    if L.MODELS[key][2] != "own":
        return S
    return P.merge_zfill(S)


L.load = _load
