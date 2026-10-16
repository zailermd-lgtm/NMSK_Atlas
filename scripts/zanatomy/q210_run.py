#!/usr/bin/env python3
"""Q210 launcher: python3 scripts/zanatomy/q210_run.py q204_hands|q204_fitseams|q204_rank ARGS...   runs the UNCHANGED Q204 script with the Q204 page table + the Q210 keys (q208_m, q210_m)."""
import runpy, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q210_paths  # noqa: F401,E402
mod = sys.argv[1]
sys.argv = [mod + ".py"] + sys.argv[2:]
runpy.run_module("scripts.zanatomy." + mod, run_name="__main__")
