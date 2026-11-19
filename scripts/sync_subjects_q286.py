#!/usr/bin/env python3
"""Q286: SUBJECT_LABELS entries of the own-viewer template for the structures from TotalSegmentator's open `head_glands_cavities` and
`vertebrae_body` tasks on the Visible Human bodies' own CT (Source class 'measured' -- the labels must not contain the word that
classifySource reads as rule-based). Idempotent minimal insertion (before the `xfer_hrasculpt2vhf_q234` entry, after Q285's line);
no other line of the template is touched.
    python3 scripts/sync_subjects_q286.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  ct_vhm_hgc: "Visible Human male, frozen CT (TotalSegmentator head_glands_cavities task, Q286) -- measured on this body by automatic segmentation, not hand-drawn; only the structures that passed the Q286 checks are shipped (each badge states its volume and checks).",',
    '  ct_vhf_hgc: "Visible Human female, CT (TotalSegmentator head_glands_cavities task, Q286) -- measured on this body by automatic segmentation, not hand-drawn; only the structures that passed the Q286 checks are shipped (each badge states its volume and checks).",',
    '  ct_vhm_disc_ts: "Visible Human male, frozen CT (TotalSegmentator vertebrae_body task, Q286) -- measured on this body by automatic segmentation, not hand-drawn: intervertebral discs at the levels the Q185c endplate rebuild held, split by level between his own vertebrae.",',
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
