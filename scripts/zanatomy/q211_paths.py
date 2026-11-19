"""Q211: point the (unchanged) Q198 / Q204 loaders at the Z-fitted pages BEFORE (male Q210, female Q208) and AFTER (Q211).  Import AFTER scripts.zanatomy.q204_paths, BEFORE the q198_* / q204_* modules.
keys: q210_m, q208_f (before), q211_m, q211_f (after)."""
import scripts.zanatomy.q204_paths  # noqa: F401
from scripts.zanatomy import q198_load as L

L.MODELS.update({
    "q210_m": ("../q210/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q210)"),
    "q208_f": ("../q208/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction (Q208)"),
    "q211_m": ("../q211/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q211)"),
    "q211_f": ("../q211/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to her reconstruction (Q211)"),
})
