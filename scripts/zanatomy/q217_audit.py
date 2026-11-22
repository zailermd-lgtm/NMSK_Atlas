#!/usr/bin/env python3
"""Q217: the UNCHANGED Q198 / Q204 audits on one of the Q217 pages.   python3 scripts/zanatomy/q217_audit.py junctions|regions|hands KEY [--joints elbow]
KEY = own_m own_f zan_m zan_f (before)  own_m_a zan_m_a (after).  Raw output dir = env Q204_RAW (default build/q217_raw)."""
import os
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q217_paths  # noqa: F401,E402
import scripts.zanatomy.q204_paths as P4  # noqa: E402

if __name__ == "__main__":
    kind, rest = sys.argv[1], sys.argv[2:]
    if kind == "regions":
        from scripts.zanatomy import q204_regions as R
        R.main(rest[0])
    elif kind == "junctions":
        from scripts.zanatomy import q198_audit as A
        A.OUT = REPO / P4.RAW_DIR
        sys.argv = ["q198_audit"] + rest
        A.main()
