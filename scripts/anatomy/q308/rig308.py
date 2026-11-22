#!/usr/bin/env python3
"""Q308 pose-rig splice: Q307's, pointed at Q308's page report.

    python3 scripts/anatomy/q308/rig308.py KEY --fresh /dev/shm/q308/rig/KEY.json

`make_pose_rig` derives a structure's skin weights from its vertex positions, so a page that gains 4-10
structures needs a new rig, and the committed file must be touched exactly once -- from a fresh run on the NEW
page -- with every entry this round did not touch left byte-identical. Q308 only APPENDS (no structure is
replaced), which is the case Q304 already handled and Q307 generalised, so the splice itself is reused rather
than rewritten: `replaced_indices` is empty in Q308's report and the replacement branch simply does not run.
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q307"))
import rig307 as R  # noqa: E402

R.REPORT = REPO / "data/derived/Q308_page_report.json"

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("--fresh", required=True)
    a = ap.parse_args()
    R.splice(a.key, a.fresh)
