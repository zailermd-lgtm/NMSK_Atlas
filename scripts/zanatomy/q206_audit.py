#!/usr/bin/env python3
"""Q206: the UNCHANGED Q198 / Q204 audits on a Q206 (or Q205) page.
    python3 scripts/zanatomy/q206_audit.py junctions|regions|hands|fitseams KEY [...]     KEY = q205_m q205_f q206_m q206_f
    junctions KEY [--joints wrist,elbow,shoulder] ; fitseams BASEKEY KEY"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q206_paths  # noqa: F401,E402
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
    elif kind == "fitseams":
        from scripts.zanatomy import q198_fitseams as F
        F.REPO = REPO / "build" / "q204_raw" / "fake"
        F.main(rest[0], rest[1])
