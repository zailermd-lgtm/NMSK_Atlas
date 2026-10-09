"""Q206: point the (unchanged) Q198 / Q204 loaders at the Q205 pages (before) and the Q206 pages (after).  Import AFTER scripts.zanatomy.q204_paths and BEFORE the q198_* / q204_* modules.
keys: q205_m / q205_f (published Q205 pages = 'before'), q206_m / q206_f (this task)."""
import scripts.zanatomy.q205_paths  # noqa: F401
from scripts.zanatomy import q198_load as L

L.MODELS.update({
    "q206_m": ("../q206/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q206)"),
    "q206_f": ("../q206/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to hers (Q206)"),
})
