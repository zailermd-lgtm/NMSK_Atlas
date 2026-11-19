#!/usr/bin/env python3
"""Q205: the UNCHANGED Q198 junction audit on a Q205 page.  python3 scripts/zanatomy/q205_junctions.py q205_m|q205_f [--joints shoulder,wrist]"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q205_paths  # noqa: F401,E402
from scripts.zanatomy import q198_audit as A  # noqa: E402
A.OUT = REPO / scripts.zanatomy.q204_paths.RAW_DIR
if __name__ == "__main__":
    A.main()
