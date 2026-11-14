#!/usr/bin/env python3
"""Q248: SUBJECT_LABELS entries of the own-viewer template for the subjects of the new ligaments (Source classes come from classifySource: `xfer_zan2*` -> filled_zan, `xfer_cvh2*` -> registered_other_person,
a label containing 'rule' -> rule_based).  Idempotent minimal insertion (before the `xfer_hrasculpt2vhf_q234` entry); no other line of the template is touched.
    python3 scripts/sync_subjects_q248.py [--check] [--dir DIR | FILE ...]      default FILE = viewer/atlas_viewer.template.html"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ANCHOR = "  xfer_hrasculpt2vhf_q234:"
LINES = [
    '  xfer_zan2vhf_lig_q248: "FILLED from Z-Anatomy (CC BY-SA 4.0 reference model), not measured on her: ligaments, capsules, retinacula and membranes her page lacked, taken from the Z-Anatomy structure of the Combined page and carried onto her own bones by local per-bone fits, attachment vertices snapped onto her bone surface; the badge states the carrier-fit error, the attachment gaps and the guards",',
    '  xfer_zan2vhm_lig_q248: "FILLED from Z-Anatomy (CC BY-SA 4.0 reference model), not measured on him: ligaments, capsules, retinacula and membranes his page lacked, taken from the Z-Anatomy structure of the Combined page and carried onto his own bones by local per-bone fits, attachment vertices snapped onto his bone surface; the badge states the carrier-fit error, the attachment gaps and the guards",',
    '  xfer_cvh2vhf_q248: "REGISTERED from the Chinese Visible Human female (Wu et al. 2015, CC BY 4.0), another person, not segmented on this scan: the anococcygeal ligament carried onto her pelvis with the Q235 bone registration; the badge states the guards",',
    '  ct_vhf_rule_lig_q248: "Rule-based on her bones (Q248): ligaments (tendinous arch of levator ani, arcus tendineus fasciae pelvis, transverse perineal, pubovesical, anococcygeal, patellar) built as bands between attachment points found by geometric rules on her own hip bones, coccyx, patella and tibia; cross-sections are stated on each card (published length ranges, modelling-choice calibres); rule-based, an estimate of position",',
    '  ct_vhm_rule_lig_q248: "Rule-based on his bones (Q248): ligaments (tendinous arch of levator ani, arcus tendineus fasciae pelvis, transverse perineal, puboprostatic, anococcygeal, patellar) built as bands between attachment points found by geometric rules on his own hip bones, coccyx, patella and tibia; cross-sections are stated on each card (published length ranges, modelling-choice calibres); rule-based, an estimate of position",',
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
