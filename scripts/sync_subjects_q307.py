#!/usr/bin/env python3
"""Q307: SUBJECT_LABELS entries of the own-viewer template for the UPPER-limb nerves carried onto the two Imaging
pages from the Combined page of the same body, and for the three lower-limb nerves whose one-sided mirrored stub
this round replaced.

The id is what decides the source class the card prints (`classifySource` in the template, and Q297's audit reads
the same ids): `xfer_zan2*` prints "Filled from Z-Anatomy (reference model), fitted to this body -- not measured
here", and a label whose text contains "rule" prints the rule-based class. Neither can print "Measured on this
body", which is the thing this round must not be able to do.

Idempotent minimal insertion (before the `xfer_hrasculpt2vhf_q234` entry); no other line of the template is touched.
    python3 scripts/sync_subjects_q304.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_zan2vhm_nerves_q304:"
LINES = [
    '  xfer_zan2vhm_nerves_q307: "FILLED from Z-Anatomy (CC BY-SA 4.0 reference model), not measured on him: the UPPER-limb and shoulder-girdle nerves his cryosections and CT do not resolve -- the lateral and medial antebrachial cutaneous nerves (the one the owner reported as out of place), the brachial cutaneous nerves, the axillary, suprascapular, long thoracic, pectoral, subscapular and thoracodorsal nerves, the posterior interosseous nerve and the palmar and dorsal digital nerves -- taken from the Combined \\u00b7 Male page, where they were already fitted to HIS own skeleton (Q195), and carried onto this page by the Q307 bone-point registration; plus the right tibial nerve, whose mirrored 40 mm stub this round replaced with the full nerve. Each card states its own error band and the gate it had to pass",',
    '  xfer_zan2vhf_nerves_q307: "FILLED from Z-Anatomy (CC BY-SA 4.0 reference model), not measured on her: the UPPER-limb and shoulder-girdle nerves her CT does not resolve -- the lateral and medial antebrachial cutaneous nerves (the one the owner reported as out of place), the brachial cutaneous nerves, the axillary, suprascapular, long thoracic, pectoral, subscapular and thoracodorsal nerves, the posterior interosseous nerve and the palmar and dorsal digital nerves -- taken from the Combined \\u00b7 Female page, where they were already fitted to HER own skeleton (Q195), and carried onto this page by the Q307 bone-point registration; plus the left femoral and left tibial nerves, whose mirrored 29 / 37 mm stubs this round replaced with the full nerves. Each card states its own error band and the gate it had to pass",',
    '  ct_vhm_rule_nerve_q307: "Rule-based on the Combined \\u00b7 Male page\'s own bones and muscles, then carried onto this page by the Q307 bone-point registration: round tubes of the cited calibre along splines through documented waypoints. NOT measured on him and NOT re-derived from this page\'s own landmarks; each card states the rule, its waypoint bound and the registration error",',
    '  ct_vhf_rule_nerve_q307: "Rule-based on the Combined \\u00b7 Female page\'s own bones and muscles, then carried onto this page by the Q307 bone-point registration: round tubes of the cited calibre along splines through documented waypoints. NOT measured on her and NOT re-derived from this page\'s own landmarks; each card states the rule, its waypoint bound and the registration error",',
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
