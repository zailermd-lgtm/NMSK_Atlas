#!/usr/bin/env python3
"""Q205: shared-border skin weld on a packed Q205 page (the Q202 / Q201 machinery: q202_build.weld_skin = q199_elbow.weld_borders over the skin patches, border = vertices < 1.5 mm apart in the
Z source = the unfitted base page).  Only patches with a shared-border step > 2 mm (and their neighbours) may move; every other patch stays byte for byte.
    python3 scripts/zanatomy/q205_skinweld.py male|female [--page DIR] [--out DIR] [--gt 2.0]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_pages as P2  # noqa: E402
from scripts.zanatomy import q202_build as B2  # noqa: E402
from scripts.zanatomy import q205_pages as P  # noqa: E402
from scripts.zanatomy import q205_pack as PK  # noqa: E402


def weld(which, page_dir=None, out=None, gt=2.0, components=False, log=print):
    cfg = PK.PAGES[which]
    page_dir = Path(page_dir or cfg["out"])
    out = Path(out or page_dir)
    stem = cfg["stem"]
    base_key = {"male": "base_m", "female": "base_f"}[which]
    key = f"q205_{which}"
    P2.PAGES[key] = (str(page_dir), stem)
    replace, rep, by, (man, blob, S) = B2.weld_skin(key, base_key, only_bad_gt=gt, components=components, log=log)
    rep_out = {}
    fixed = {}
    for i, (v, f, rec) in replace.items():
        r = dict(rec or {})
        b = r.get("procedural_badge") or ""
        b = b.replace(" Q202: rule-based seam weld", " Q205: rule-based seam weld (after the hand / shoulder re-fit)")
        r["procedural_badge"] = b
        fixed[i] = (v, f, r)
    man2, blob2 = P.save_page(out, stem, man, blob, replace=fixed)
    rep_out = {k: v for k, v in rep.items() if k != "moved"}
    rep_out["patches"] = sorted(fixed)
    return rep_out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=["male", "female"])
    ap.add_argument("--page")
    ap.add_argument("--out")
    ap.add_argument("--gt", type=float, default=2.0)
    a = ap.parse_args(argv)
    rep = weld(a.which, a.page, a.out, a.gt)
    p = REPO / "data" / "derived" / f"Q205_skinweld_{a.which}.json"
    p.write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: v for k, v in rep.items() if k != "patches"}, default=float)[:1500])


if __name__ == "__main__":
    main()
