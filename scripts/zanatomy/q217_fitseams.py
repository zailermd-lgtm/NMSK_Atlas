#!/usr/bin/env python3
"""Q217: unchanged Q198 fit-vs-base seam check (adjacency tears, frame offsets) of a Z-fitted page KEY against the unfitted Z male base.  python3 scripts/zanatomy/q217_fitseams.py KEY (zan_m | zan_m_a)
-> build/q217_raw/fake/data/derived/Q198_fitseams_<KEY>.json"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q217_paths  # noqa: F401,E402
from scripts.zanatomy import q198_fitseams as F  # noqa: E402
(REPO / "build/q217_raw/fake/data/derived").mkdir(parents=True, exist_ok=True)
F.REPO = REPO / "build" / "q217_raw" / "fake"
if __name__ == "__main__":
    F.main("z_male", sys.argv[1])
