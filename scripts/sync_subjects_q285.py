#!/usr/bin/env python3
"""Q285: SUBJECT_LABELS entry of the own-viewer template for her CT breasts (subject ct_vhf_breast; Source class 'measured' -- the label
must not contain the word that classifySource reads as rule-based).
Idempotent minimal insertion (before the `xfer_hrasculpt2vhf_q234` entry); no other line of the template is touched.
    python3 scripts/sync_subjects_q285.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  ct_vhf_breast: "Visible Human female, CT labels (TotalSegmentator breasts task, Q285) -- measured on this body by automatic segmentation, not hand-drawn: her own breasts from her unfrozen, unenhanced CT, cut at her own midline and kept one voxel beneath her skin surface, surface at the level that keeps the label volume. Supine cadaver; each badge states the volume and the checks.",',
]


def patch(text: str) -> str:
    if all(l.split(":")[0].strip() + ":" in text for l in LINES):
        return text
    assert text.count(ANCHOR) == 1, "anchor line xfer_hrasculpt2vhf_q234 not found exactly once"
    i = text.index(ANCHOR)
    return text[:i] + "\n".join(LINES) + "\n" + text[i:]


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
