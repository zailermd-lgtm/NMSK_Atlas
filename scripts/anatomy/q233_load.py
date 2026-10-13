"""Q233 loader: the six CURRENT pages -> structures {id,name,sys,side,v,f,src,rec} in the atlas frame (mm; +X right, +Y sup, +Z ant).
Thin wrapper over scripts/zanatomy/q198_load.py with the Q233 source dirs (override with env Q233_SRC_<key>)."""
from __future__ import annotations
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
import q198_load as L

PAGES = {  # key: (dir relative to repo, html, kind, label)
    "own_m": ("build/q224/viewer_m_hr", "atlas_viewer_male.html", "own", "Imaging-based · Male"),
    "own_f": ("build/q224/viewer_f_hr", "atlas_viewer_female.html", "own", "Imaging-based · Female"),
    "base_m": ("build/q222/viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan", "Base · Male"),
    "base_f": ("build/q222/viewer_base_female", "atlas_viewer_base_female.html", "zan", "Base · Female"),
    "comb_m": ("build/q225/viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan", "Combined · Male"),
    "comb_f": ("build/q225/viewer_zan_female", "atlas_viewer_zan_female.html", "zan", "Combined · Female"),
}

def load(key: str):
    d, html, kind, label = PAGES[key]
    d = os.environ.get("Q233_SRC_" + key, d)
    p = Path(d) if os.path.isabs(d) else REPO / d
    L.Q = p.parent
    L.MODELS["_q233"] = (p.name, html, kind, label)
    return L.load("_q233")

if __name__ == "__main__":
    for k in PAGES:
        s = load(k); print(k, len(s), sum(len(x["v"]) for x in s))
