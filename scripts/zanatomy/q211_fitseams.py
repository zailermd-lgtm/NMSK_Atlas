#!/usr/bin/env python3
"""Q211: unchanged Q198 fit-vs-base seam check for a Z-fitted page KEY (q210_m q208_f q211_m q211_f) against its unfitted base.  python3 scripts/zanatomy/q211_fitseams.py KEY"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q211_paths  # noqa: F401,E402
from scripts.zanatomy import q198_fitseams as F  # noqa: E402
F.REPO = REPO / "build" / "q204_raw" / "fake"
BASE = {"q210_m": "z_male", "q211_m": "z_male", "q208_f": "z_base_f", "q211_f": "z_base_f"}
if __name__ == "__main__":
    F.main(BASE[sys.argv[1]], sys.argv[1])
