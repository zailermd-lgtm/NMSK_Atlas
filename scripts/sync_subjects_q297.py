#!/usr/bin/env python3
"""Q297: the two MISSING SUBJECT_LABELS entries of the own-viewer template, for the rule-built brachial plexus (Q258).

The defect this fixes, found by the Q297 provenance audit (scripts/anatomy/q297/audit297.py): the 34 brachial-plexus
meshes per Imaging page carry the subject `ct_vh{m,f}_rule_nerve_q258` and `rec.method = "rule-based"`, but that subject
had NO entry here. classifySource() then fell through all of its branches and returned "measured", so every one of those
68 cards printed the green source line "Measured on this body -- segmented from its own CT or cryosections." for
geometry that is a rule-built spline. Neither `method` nor `error_band_mm` is rendered by either viewer, so nothing on
the card contradicted it.

Adding the label is the whole fix: classifySource() reads /rule/i in the label and returns `rule_based`, so the card
prints the orange "Rule-based on this body's own data -- derived by rule from its CT or cryosections, not read off a
segmentation." instead, and the structure is counted as rule-based everywhere the source classes are counted.

Idempotent minimal insertion (before the Q249 rule-nerve entries, which are the nearest kin); no other line is touched.
    python3 scripts/sync_subjects_q297.py [--check] [--dir DIR | FILE ...]   default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  ct_vhf_rule_nerve_q249:"
_TXT = ("Rule-based on {poss} bones and neighbouring structures (Q258): the brachial plexus -- the C5-T1 roots, the "
        "superior / middle / inferior trunks, their anterior and posterior divisions and the lateral / medial / posterior "
        "cords -- drawn as round tubes of the published calibre along splines through documented waypoints "
        "(Gray's Anatomy for Students, 4th ed. ch.7; Moore, Clinically Oriented Anatomy, 8th ed.). NOT segmented from "
        "{poss2} imaging and not dissected: no imaging this atlas holds resolves the plexus. Each card states the course "
        "and the error band (8-15 mm). Added in Q297, which found these 34 structures per page had no entry here and were "
        "therefore being shown as \\\"Measured on this body\\\".")
LINES = [
    '  ct_vhf_rule_nerve_q258: "' + _TXT.format(poss="her", poss2="her") + '",',
    '  ct_vhm_rule_nerve_q258: "' + _TXT.format(poss="his", poss2="his") + '",',
]


def patch(text: str) -> str:
    if all(l.split(":")[0].strip() + ":" in text for l in LINES):
        return text
    assert text.count(ANCHOR) == 1, "anchor line ct_vhf_rule_nerve_q249 not found exactly once"
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
