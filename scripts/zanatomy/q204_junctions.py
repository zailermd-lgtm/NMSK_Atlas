#!/usr/bin/env python3
"""Q204: run the UNCHANGED Q198 junction audit (q198_audit.main) on one currently published page. python3 scripts/zanatomy/q204_junctions.py MODEL
raw output build/q204_raw/Q198_model_<MODEL>.json (git-ignored; data/derived/Q204_anatomy_audit.json is the compact result)."""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q204_paths  # noqa: F401,E402  (patches the loader's page table)
from scripts.zanatomy import q198_audit as A  # noqa: E402
A.OUT = REPO / scripts.zanatomy.q204_paths.RAW_DIR
if __name__ == "__main__":
    A.main()
