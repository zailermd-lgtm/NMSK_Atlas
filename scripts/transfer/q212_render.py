#!/usr/bin/env python3
"""Q212: close-ups of the new Q212 continuations (blue) against their measured structure (pink), neighbouring bones / muscles muted, and, for the wrist work, of the re-segmented bones.

    python3 scripts/transfer/q212_render.py BUNDLE_DIR OUT_DIR TAG [--ids a,b,c] [--r 110] [--half 90] [--black-old a,b]
Without --ids every `*_zfill212` entry is rendered (anterior / posterior / lateral views around its centroid)."""
from __future__ import annotations
import argparse
import re
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402

SKIP = re.compile(r"intercostal|^skin$|fascia|bursa|capsule|lung|heart|liver|vessel|_n_|artery|vein")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bundle"); ap.add_argument("out"); ap.add_argument("tag")
    ap.add_argument("--ids", default=""); ap.add_argument("--r", type=float, default=110.0); ap.add_argument("--half", type=float, default=90.0)
    ap.add_argument("--hide", default="", help="comma list of entry ids not drawn (e.g. a superseded measured entry)")
    ap.add_argument("--all-muscles", action="store_true")
    ap.add_argument("--suffix", default="_q212", help="subject suffix of the entries drawn blue")
    a = ap.parse_args()
    B = Bundle(a.bundle)
    hide = set(x for x in a.hide.split(",") if x)
    ents = [(it, *B.mesh(it)) for it in B.items]
    new = [(it, v, f) for it, v, f in ents if it["e"].get("subject", "").endswith(a.suffix)]
    want = [i for i in a.ids.split(",") if i] or [it["e"]["id"] for it, v, f in new]
    byid = {it["e"]["id"]: (it, v, f) for it, v, f in ents}
    for wid in want:
        if wid not in byid:
            print("missing", wid); continue
        it0, v0, f0 = byid[wid]
        c = v0.mean(0)
        scene = []
        for it, v, f in ents:
            e = it["e"]
            if e["id"] in hide or e["cat"] not in ("bone", "muscle", "tendon", "ligament") or SKIP.search(e["id"]) or len(f) == 0:
                continue
            if np.linalg.norm(v - c, axis=1).min() > a.r:
                continue
            base = re.sub(r"_zfill\d*s?$", "", wid)
            if e["cat"] != "bone" and not a.all_muscles and re.sub(r"_zfill\d*s?$", "", e["id"]) != base:
                continue
            if e.get("subject", "").endswith(a.suffix):
                col = (0.10, 0.40, 0.95)
            elif e["id"] == re.sub(r"_zfill\d*s?$", "", wid):
                col = (0.95, 0.35, 0.45)
            elif e["cat"] == "bone":
                col = (0.93, 0.91, 0.80)
            else:
                h = (zlib.crc32(e["id"].encode()) % 1000) / 1000.0
                col = (0.55 + 0.1 * h, 0.40 + 0.1 * h, 0.38 + 0.1 * h)
            scene.append({"v": v, "f": f, "color": col})
        views = [dict(name=f"{wid}_{a.tag}_{n}", az=az, el=el, target=c, half=a.half) for n, az, el in (("ant", 0, 10), ("post", 180, 10), ("lat", 90, 10), ("sup", 0, 70))]
        R.render(scene, views, Path(a.out), size=(480, 480))
    print("rendered", len(want), "->", a.out)


if __name__ == "__main__":
    main()
