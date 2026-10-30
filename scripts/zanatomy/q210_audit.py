#!/usr/bin/env python3
"""Q210: the UNCHANGED Q198 / Q204 audits on the Q208 (before) or Q210 (after) male Z-fitted page.   python3 scripts/zanatomy/q210_audit.py junctions|regions|hands KEY [...]    KEY = q208_m q210_m
raw output dir = env Q204_RAW (default build/q210_raw)"""
import os
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
os.environ.setdefault("Q204_RAW", "build/q210_raw")
import scripts.zanatomy.q210_paths  # noqa: F401,E402
import scripts.zanatomy.q204_paths as P4  # noqa: E402

if __name__ == "__main__":
    kind, rest = sys.argv[1], sys.argv[2:]
    if kind == "regions":
        from scripts.zanatomy import q204_regions as R
        R.main(rest[0])
    elif kind == "hands":
        from scripts.zanatomy import q204_hands as Hd
        Hd.main(rest[0])
    elif kind == "junctions":
        from scripts.zanatomy import q198_audit as A
        A.OUT = REPO / P4.RAW_DIR
        sys.argv = ["q198_audit"] + rest
        A.main()
