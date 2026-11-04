#!/usr/bin/env python3
"""Q223: unchanged Q198 fit-vs-base seam check on the Q223 pages; output under build/q223_raw/fake/data/derived. python3 q223_fitseams.py z_male z_male_fit"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q223_paths  # noqa: F401,E402
from scripts.zanatomy import q198_fitseams as F  # noqa: E402
F.REPO = REPO / "build" / "q223_raw" / "fake"
(F.REPO / "data" / "derived").mkdir(parents=True, exist_ok=True)
if __name__ == "__main__":
    F.main(sys.argv[1], sys.argv[2])
