"""Q207: point the (unchanged) Q198 / Q204 loaders at the Q206 pages (before) and the Q207 pages (after).  keys: q206_m / q206_f, q207_m / q207_f."""
import scripts.zanatomy.q206_paths  # noqa: F401
from scripts.zanatomy import q198_load as L

L.MODELS.update({
    "q207_m": ("../q207/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q207)"),
    "q207_f": ("../q207/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to hers (Q207)"),
})
