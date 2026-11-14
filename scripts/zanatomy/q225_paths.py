"""Q225: re-point the (unchanged) Q204 / Q198 audit code at the six pages as they are after Q225: the two Z-fitted pages = the Q225 fitted page dirs (build/q225_fit/viewer_zan_vhm, fit_zan_female), the other four = the Q223 pages.
Import BEFORE any q204_* / q198_* module.  Raw output dir = env Q204_RAW (default build/q225_raw)."""
import os
os.environ.setdefault("Q204_RAW", "build/q225_raw")
from scripts.zanatomy import q204_paths as P  # noqa: E402
from scripts.zanatomy import q198_load as L  # noqa: E402

PAGES = {
    "own_m": ("../q221/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (VH reconstruction)"),
    "own_f": ("../q222/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction)"),
    "z_male": ("../q222/viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Z male base"),
    "z_base_f": ("../q222/viewer_base_female", "atlas_viewer_base_female.html", "zan", "Z generic body (female variant)"),
    "z_male_fit": ("../q225_fit/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q225)"),
    "z_female_fit": ("../q225_fit/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction (Q225)"),
}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
