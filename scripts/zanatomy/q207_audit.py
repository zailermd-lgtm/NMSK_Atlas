#!/usr/bin/env python3
"""Q207: the UNCHANGED Q198 / Q204 audits on a Q206 (before) or Q207 (after) page.
    python3 scripts/zanatomy/q207_audit.py junctions|regions|hands KEY [...]     KEY = q206_m q206_f q207_m q207_f"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q207_paths  # noqa: F401,E402
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
