#!/usr/bin/env python3
"""Q231: unified artifact / page names (owner request): <kind> · <sex>, kind = Base | Imaging-based | Combined.

    python3 scripts/set_titles_q231.py PAGE_DIR [PAGE_DIR ...]

Rewrites, in the page html of each dir (atlas_viewer_<variant>.html and index.html if present), the <title>, the visible <h1> and the
loading-screen <h2> to the unified name. Data literals are untouched. Run it on the page dir right before publishing; the builders
(build_viewer_html.py / build_zan_atlas_viewer.py / regen_cut_q218.sh) still write the old wording."""
import re
import sys
from pathlib import Path

NAMES = {
    "atlas_viewer_male.html": "Imaging-based · Male",
    "atlas_viewer_female.html": "Imaging-based · Female",
    "atlas_viewer_zan_atlas.html": "Base · Male",
    "atlas_viewer_base_female.html": "Base · Female",   # Q250: Z-Anatomy deformed onto a female skeleton (the page intro and every card say how); until Q250 the name carried "(male-derived body)"
    "atlas_viewer_zan_male_fitted.html": "Combined · Male",
    "atlas_viewer_zan_female.html": "Combined · Female",
}
PREFIX = "NMSK Atlas — "


def retitle(path: Path, name: str) -> dict:
    s = path.read_text(encoding="utf-8")
    full = PREFIX + name
    n = {}
    s, n["title"] = re.subn(r"<title>[^<]*</title>", f"<title>{full}</title>", s, count=1)
    s, n["h1"] = re.subn(r"(<h1[^>]*>)NMSK Atlas[^<]*(</h1>)", rf"\g<1>{full}\g<2>", s, count=1)
    s, n["h2"] = re.subn(r"(<h2[^>]*>)NMSK Atlas[^<]*(</h2>)", rf"\g<1>{full}\g<2>", s, count=1)
    path.write_text(s, encoding="utf-8")
    return n


def main(dirs):
    for d in map(Path, dirs):
        for fn, name in NAMES.items():
            for f in (d / fn, d / "index.html"):
                if f.exists() and (f.name == fn or (d / fn).exists()):
                    print(f, name, retitle(f, name))


if __name__ == "__main__":
    main(sys.argv[1:])
