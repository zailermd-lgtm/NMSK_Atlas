#!/usr/bin/env python3
"""Q216 launcher: python3 scripts/zanatomy/q216_run.py q204_regions own_f|before_f [ARGS]   -- runs the UNCHANGED Q204 script with the Q216 page table (q216_paths.py)."""
import runpy, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q216_paths  # noqa: F401,E402
mod = sys.argv[1]
sys.argv = [mod + ".py"] + sys.argv[2:]
runpy.run_module("scripts.zanatomy." + mod, run_name="__main__")
