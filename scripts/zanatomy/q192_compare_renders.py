"""Q192: LEFT hand / wrist renders, Q191 build (before) vs Q192 build (after): palmar, dorsal, radial, ulnar close-ups (Z tissue + bones; bones; Z skin over her skin) and the
transverse cuts through the palm and the wrist / carpal tunnel.  Reuses scripts/zanatomy/q191_compare_renders.py (labels / sides parameters).

    PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers python3 scripts/zanatomy/q192_compare_renders.py [--before build/viewer_zan_female_q191] [--after build/viewer_zan_female_q192]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q191_compare_renders as C  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female_q191"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q192"))
    ap.add_argument("--out", default=str(REPO / "build" / "viewer_zan_female_q192" / "renders"))
    ap.add_argument("--sides", default="l")
    a = ap.parse_args(argv)
    C.run(a.before, a.after, a.out, labels=("q191", "q192"), sides=a.sides)


if __name__ == "__main__":
    main()
