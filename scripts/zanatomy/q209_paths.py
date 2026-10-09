"""Q209: re-point the (unchanged) Q204 / Q198 audit code at the six pages published NOW. Import this BEFORE any q204_* / q198_* module.
Raw output dir = env Q204_RAW (default build/q209_raw); Q204_MERGE=1 merges the own pages' *_zfill* continuations as in Q204."""
import os
os.environ.setdefault("Q204_RAW", "build/q209_raw")
from scripts.zanatomy import q204_paths as P  # noqa: E402  (applies the Q204 page table and the optional merge hook)
from scripts.zanatomy import q198_load as L  # noqa: E402

PAGES = {  # key: (dir relative to build/q197, html, kind, label)
    "own_m": ("../q203/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (VH reconstruction)"),
    "own_f": ("../q203/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction)"),
    "z_male": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Z male base"),
    "z_base_f": ("../q202/viewer_base_female", "atlas_viewer_base_female.html", "zan", "Z generic body (female variant)"),
    "z_male_fit": ("../q208/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction"),
    "z_female_fit": ("../q208/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction"),
}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
