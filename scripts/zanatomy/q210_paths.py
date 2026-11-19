"""Q210: point the (unchanged) Q198 / Q204 loaders at the published Q208 male page (before) and the Q210 male page (after).  Import AFTER scripts.zanatomy.q204_paths and BEFORE the q198_* / q204_* modules.
keys: q208_m (published Q208 male Z fit = 'before'), q210_m (this task)."""
import scripts.zanatomy.q204_paths  # noqa: F401
from scripts.zanatomy import q198_load as L

L.MODELS.update({
    "q208_m": ("../q208/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q208)"),
    "q210_m": ("../q210/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q210)"),
})
