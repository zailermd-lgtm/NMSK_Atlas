#!/usr/bin/env python3
"""Q204: unchanged Q198 fit-vs-base seam check on the currently published pages. python3 scripts/zanatomy/q204_fitseams.py z_male z_male_fit | z_base_f z_female_fit"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q204_paths  # noqa: F401,E402
from scripts.zanatomy import q198_fitseams as F  # noqa: E402
F.REPO = REPO / "build" / "q204_raw" / "fake"      # output dir only (data/derived under it)
if __name__ == "__main__":
    F.main(sys.argv[1], sys.argv[2])
