#!/usr/bin/env python3
"""Q249: SUBJECT_LABELS entries of the own-viewer template for the subjects of the rule-based pelvic / perineal nerves (the Source class comes from classifySource: a label containing 'rule' -> rule_based).
Idempotent minimal insertion (before the `xfer_hrasculpt2vhf_q234` entry); no other line of the template is touched.
    python3 scripts/sync_subjects_q249.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  ct_vhf_rule_nerve_q249: "Rule-based on her bones and neighbouring structures (Q249): pelvic, perineal and a few other tier-1 nerves (sacral rami S1-S4, lumbosacral trunk, pudendal nerve and its branches, inferior gluteal, nerves to obturator internus / quadratus femoris / levator ani / coccygeus, coccygeal plexus, hypogastric and pelvic splanchnic nerves, posterior femoral cutaneous, iliohypogastric / ilioinguinal / genitofemoral, lumbar medial branches) drawn as round tubes of the published calibre along splines through documented waypoints. Not segmented, not dissected; each card states the waypoints, the calibre source and the error bound.",',
    '  ct_vhm_rule_nerve_q249: "Rule-based on his bones and neighbouring structures (Q249): pelvic, perineal and a few other tier-1 nerves (sacral rami S1-S4, lumbosacral trunk, pudendal nerve and its branches, inferior gluteal, nerves to obturator internus / quadratus femoris / levator ani / coccygeus, coccygeal plexus, hypogastric and pelvic splanchnic nerves, posterior femoral cutaneous, iliohypogastric / ilioinguinal / genitofemoral, lumbar medial branches) drawn as round tubes of the published calibre along splines through documented waypoints. Not segmented, not dissected; each card states the waypoints, the calibre source and the error bound.",',
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
