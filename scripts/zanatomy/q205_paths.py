"""Q205: point the (unchanged) Q198 / Q204 loaders at the Q205 pages as well.  Import AFTER scripts.zanatomy.q204_paths and BEFORE the q198_* / q204_* modules that use MODELS.
keys: q205_m (Z male fitted), q205_f (Z female fitted); q204 keys z_male_fit / z_female_fit stay the published (q202) pages = the 'before' state."""
import scripts.zanatomy.q204_paths  # noqa: F401
from scripts.zanatomy import q198_load as L

L.MODELS.update({
    "q205_m": ("../q205/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Z fitted to his reconstruction (Q205)"),
    "q205_f": ("../q205/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Z fitted to hers (Q205)"),
})
