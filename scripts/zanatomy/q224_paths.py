"""Q224: re-point the (unchanged) Q204 / Q198 audit code at the two OWN pages as built by Q224 (build/q224/viewer_{m,f}_hr).  Import BEFORE any q204_* / q198_* module.
Raw output dir = env Q204_RAW (default build/q224_raw); Q204_MERGE=1 merges the own pages' *_zfill* continuations as in Q204 / Q209 / Q223."""
import os
os.environ.setdefault("Q204_RAW", "build/q224_raw")
from scripts.zanatomy import q204_paths as P  # noqa: E402
from scripts.zanatomy import q198_load as L  # noqa: E402

PAGES = {  # key: (dir relative to build/q197, html, kind, label)
    "own_m": ("../q224/viewer_m_hr", "atlas_viewer_male.html", "own", "Own male (VH reconstruction)"),
    "own_f": ("../q224/viewer_f_hr", "atlas_viewer_female.html", "own", "Own female (VH reconstruction)"),
}
P.PAGES.clear(); P.PAGES.update(PAGES)
L.MODELS.clear(); L.MODELS.update(PAGES)
