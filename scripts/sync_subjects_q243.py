#!/usr/bin/env python3
"""Q243: the SUBJECT_LABELS entries of the own-viewer template for the subjects of the HRA v1.10 structures (Source class `reference_same_donor` comes from classifySource: xfer_hra2* prefix, Q233).
Idempotent minimal insertion (two lines before the `xfer_hrasculpt2vhf_q234` entry); no other line of the template is touched.
    python3 scripts/sync_subjects_q243.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  xfer_hra2vhf_q243: "REFERENCE STRUCTURES OF THE SAME DONOR, not segmented on this scan: the female pelvic vessels (uterine arteries and veins, internal iliac and internal pudendal veins, middle / inferior / superior rectal veins, median sacral vein, superior rectal artery) from the HuBMAP Human Reference Atlas 3D library (blood-vasculature-female, CC BY 4.0), registered onto her CT pelvis with the uterus transform; the card gives tube length, calibre, the registration error and the guards",',
    '  xfer_hra2vhf_spine_q243: "REFERENCE STRUCTURES OF THE SAME DONOR, not segmented on this scan: the nucleus pulposus of the intervertebral disks and the spinal cord segments C1-S4 from the HuBMAP Human Reference Atlas 3D library (CC BY 4.0), each fitted to her vertebra of the same rank (HRA numbers her six lumbar vertebrae L1-L6; this page names the extra one L1B, open item Q185k2); the card gives the per-level fit error and the guards",',
]


def patch(text: str) -> str:
    if "xfer_hra2vhf_q243:" in text and "xfer_hra2vhf_spine_q243:" in text:
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
