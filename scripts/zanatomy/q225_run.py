#!/usr/bin/env python3
"""Q225 launcher: python3 scripts/zanatomy/q223_run.py q204_junctions|q204_regions|q204_hands|q204_fitseams|q204_rank ARGS...  (UNCHANGED Q204 script, Q225 page table)."""
import runpy, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q225_paths  # noqa: F401,E402
mod = sys.argv[1]
sys.argv = [mod + ".py"] + sys.argv[2:]
runpy.run_module("scripts.zanatomy." + mod, run_name="__main__")
