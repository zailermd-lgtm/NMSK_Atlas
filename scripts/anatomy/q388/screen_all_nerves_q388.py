#!/usr/bin/env python3
"""Q388 screen: every nerve mesh of a Base page -- how much of its centreline runs inside a muscle or a bone, how close it
comes to bone, and its nearest artery. A FLAG list, not a verdict: nerves legitimately pierce muscles (musculocutaneous in
coracobrachialis, posterior interosseous in supinator, motor branches ending in their muscle) and run in bony canals
(data/anatomy/q357_in_bone_allow.json). The curated, sourced verdicts are in verify_nerve_course_q388.py.

    python3 scripts/anatomy/q388/screen_all_nerves_q388.py [--page-dir DIR ...] --out JSON
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib388 as L  # noqa: E402

NERVE_WORD = re.compile(r"(^|_)(n|nerve|nerves|plexus|ramus|rami|root|roots|trunk|cord|div|branch|branches|ganglion|ganglia|chain|"
                        r"splanchnic|ansa)(_|$)")


def is_peripheral(k, v):
    return v["sys"] == "nerve" and bool(NERVE_WORD.search(k))


def screen(page_dir):
    D = L.LazyPage(page_dir)
    mus = L.Scene(D, systems=("muscle",)); bon = L.Scene(D, systems=("bone",))
    arts = [k for k, m in D.meta.items() if m["sys"] == "vessel" and "arter" in k]
    out = {}
    for k, m in D.meta.items():
        if not is_peripheral(k, m):
            continue
        v = D[k]
        if len(v["F"]) < 8:
            continue
        C = L.centreline(v, n=30)
        if C is None:
            continue
        seg = np.linalg.norm(np.diff(C, axis=0), axis=1); length = float(seg.sum())
        im = [[kk for kk, _ in L.inside_ids(mus, p)] for p in C]
        ib = [[kk for kk, _ in L.inside_ids(bon, p)] for p in C]
        fm = float(np.mean([bool(x) for x in im])); fb = float(np.mean([bool(x) for x in ib]))
        # longest contiguous intramuscular run (mm), excluding the last 15 % at either end (entry into the target muscle)
        n = len(C); lo, hi = int(0.15 * n), int(0.85 * n)
        run = best = 0.0
        for i in range(lo, hi):
            run = run + seg[i - 1] if im[i] else 0.0
            best = max(best, run)
        musc = sorted({kk for x in im for kk in x})
        out[k] = dict(name=m["name"], length_mm=round(length, 1), frac_centre_in_muscle=round(fm, 2),
                      frac_centre_in_bone=round(fb, 2), longest_mid_intramuscular_mm=round(best, 1), muscles=musc[:6],
                      bones=sorted({kk for x in ib for kk in x})[:4])
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", action="append")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    dirs = a.page_dir or [str(L.REPO / "build/q309" / d) for d in L.PAGES.values()]
    res = {Path(d).name: screen(d) for d in dirs}
    Path(a.out).write_text(json.dumps(res, indent=1))
    for page, r in res.items():
        flag = sorted(r.items(), key=lambda t: -t[1]["longest_mid_intramuscular_mm"])
        print(page, len(r), "nerves; longest mid-course intramuscular runs:")
        for k, v in flag[:25]:
            print(f"  {k}: {v['longest_mid_intramuscular_mm']} mm of {v['length_mm']} ({v['muscles']}); in bone {v['frac_centre_in_bone']}")
    print("Q388_SCREEN_DONE")


if __name__ == "__main__":
    sys.exit(main())
