#!/usr/bin/env python3
"""Q205: unchanged Q198 fit-vs-base seam / frame-offset check on a Q205 page.  python3 scripts/zanatomy/q205_fitseams.py z_male q205_m | z_base_f q205_f  -> build/q204_raw/fake/data/derived/Q198_fitseams_<fit>.json"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q205_paths  # noqa: F401,E402
from scripts.zanatomy import q198_fitseams as F  # noqa: E402
F.REPO = REPO / "build" / "q204_raw" / "fake"
if __name__ == "__main__":
    F.main(sys.argv[1], sys.argv[2])
