#!/usr/bin/env python3
"""Q204: the UNCHANGED Q198 aggregator (thresholds, severity, causes, verdicts) over the Q204 raw junction JSONs -> build/q204_raw/Q198_anatomy_audit.json"""
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.zanatomy import q198_rank as R  # noqa: E402
import scripts.zanatomy.q204_paths as P4  # noqa: E402
R.DER = REPO / P4.RAW_DIR
for k, v in list(R.FIT_SEAMS.items()):
    R.FIT_SEAMS[k] = "fake/data/derived/" + v
if __name__ == "__main__":
    R.main()
