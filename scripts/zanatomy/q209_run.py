#!/usr/bin/env python3
"""Q209 launcher: python3 scripts/zanatomy/q209_run.py q204_junctions|q204_regions|q204_hands|q204_fitseams|q204_rank|q204_renders ARGS...
runs the UNCHANGED Q204 script with the Q209 page table (scripts/zanatomy/q209_paths.py)."""
import runpy, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q209_paths  # noqa: F401,E402
mod = sys.argv[1]
sys.argv = [mod + ".py"] + sys.argv[2:]
runpy.run_module("scripts.zanatomy." + mod, run_name="__main__")
