#!/usr/bin/env python3
"""Q295: SUBJECT_LABELS entries of the own-viewer template for the fat / unlabelled soft tissue measured from each body's own imaging
(Source class 'measured': CT HU on her, cryosection colour on him, in the space no segmented structure covers). Idempotent minimal
insertion (before the `xfer_hrasculpt2vhf_q234` entry); no other line of the template is touched.
    python3 scripts/sync_subjects_q295.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  img_vhf_fat_q295: "Visible Human female, CT (Q295) -- her fat and unlabelled soft tissue, measured on her own CT (fat HU -190 to -30, soft tissue -29 to +200) in the space no segmented structure of this page covers; meshed, not hand-drawn; the badge states the volume and the triangles",',
    '  img_vhm_fat_q295: "Visible Human male, colour cryosections (Q295) -- his fat and unlabelled soft tissue, measured on his own photographs (fat colour class) in the space no segmented structure of this page covers; meshed, not hand-drawn; the badge states the volume and the triangles",',
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
