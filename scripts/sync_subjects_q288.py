#!/usr/bin/env python3
"""Q288: SUBJECT_LABELS entry of the own-viewer template for her uterus, segmented on her own colour cryosections (Source class
'measured': the label must NOT carry the word classifySource reads as rule-based). Idempotent minimal insertion (before the
`xfer_hrasculpt2vhf_q234` entry, after Q287's line); no other line of the template is touched.
    python3 scripts/sync_subjects_q288.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  ct_vhf_uterus: "Visible Human female, colour cryosections (Q288) -- her own uterus, segmented on her photographs by a 3-D random walker from interior seeds placed by eye (data/derived/Q288_seeds.json), registered to her CT; the badge states its volume against a cited postmenopausal value and its checks.",',
]


def patch(text: str) -> str:
    if all(l.split(":")[0].strip() + ":" in text for l in LINES):
        return text
    assert text.count(ANCHOR) == 1, "anchor line xfer_hrasculpt2vhf_q234 not found exactly once"
    i = text.index(ANCHOR)
    return text[:i] + "\n".join(l for l in LINES if l.split(":")[0].strip() + ":" not in text) + "\n" + text[i:]


def main(argv):
    check = "--check" in argv
    argv = [a for a in argv if a != "--check"]
    if argv[:1] == ["--dir"]:
        files = [Path(argv[1]) / "atlas_viewer.template.html"]
    else:
        files = [Path(a) for a in argv] or [REPO / "viewer" / "atlas_viewer.template.html"]
    bad = 0
    for f in files:
        s = f.read_text(encoding="utf-8"); n = patch(s)
        if n != s:
            if check:
                print("out of date:", f); bad = 1
            else:
                f.write_text(n, encoding="utf-8"); print("patched", f)
        else:
            print("up to date", f)
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
