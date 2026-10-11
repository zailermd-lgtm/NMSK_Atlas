#!/usr/bin/env python3
"""Q214 launcher: python3 scripts/zanatomy/q214_run.py q204_regions own_m|own_f|before_m|before_f [ARGS]   -- runs the UNCHANGED Q204 script with the Q214 page table (q214_paths.py)."""
import runpy, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q214_paths  # noqa: F401,E402
mod = sys.argv[1]
sys.argv = [mod + ".py"] + sys.argv[2:]
runpy.run_module("scripts.zanatomy." + mod, run_name="__main__")
