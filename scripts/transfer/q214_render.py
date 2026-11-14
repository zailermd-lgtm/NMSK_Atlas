#!/usr/bin/env python3
"""Q214 before / after renders (build/q214_renders, git-ignored): for every muscle Q214 added, the region around it from the source bundle (BEFORE) and the Q214 bundle (AFTER, the new muscle blue,
neighbouring muscles muted, bones pale, skin not drawn), posterior and lateral views side by side.

    python3 scripts/transfer/q214_render.py vhm|vhf [OUT_DIR]"""
from __future__ import annotations
import re
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_targets as T  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402

SKIP = re.compile(r"intercostal|^skin$|fascia|bursa|capsule|lung|heart|liver|vessel|_n_|artery|vein|retinaculum|aponeurosis")


SUPERFICIAL = re.compile(r"^(trapezius|latissimus_dorsi|deltoid|rhomboid_(major|minor)|pectoralis_major|serratus_posterior)")


def scene_of(B, c, r, new_ids, hide_superficial=False):
    sc = []
    for it in B.items:
        e = it["e"]
        if e.get("hidden_default") or e["cat"] not in ("bone", "muscle") or SKIP.search(e["id"]):
            continue
        if hide_superficial and SUPERFICIAL.match(e["id"]):          # the layer above the splenius is not drawn so that its own layer is visible (both before and after)
            continue
        v, f = B.mesh(it)
        if len(f) == 0 or np.linalg.norm(v - c, axis=1).min() > r:
            continue
        if e["id"] in new_ids:
            col = (0.10, 0.40, 0.95)
        elif e["cat"] == "bone":
            col = (0.93, 0.91, 0.80)
        else:
            h = (zlib.crc32(e["id"].encode()) % 1000) / 1000.0
            col = (0.62 + 0.1 * h, 0.42 + 0.1 * h, 0.40 + 0.1 * h)
        sc.append({"v": v, "f": f, "color": col})
    return sc


def main():
    body = sys.argv[1]
    out = Path(sys.argv[2] if len(sys.argv) > 2 else REPO / "build/q214_renders")
    cfg = T.BODY[body]
    A, N = Bundle(cfg["src"]), Bundle(cfg["out"])
    new = [it["e"]["id"] for it in N.items[len(A.items):] if it["e"]["cat"] == "muscle"]
    groups = {}
    for nid in new:
        stem = re.sub(r"_(r|l)$", "", nid)
        groups.setdefault(stem, []).append(nid)
    for stem, ids in groups.items():
        for s in sorted({i[-1] for i in ids}):
            nid = f"{stem}_{s}"
            g = N.get(nid)
            c = g["v"].mean(0)
            half = 70.0 if stem.startswith("splenius") else (110.0 if stem == "fibularis_brevis" else 45.0)
            r = half * 1.6
            for tag, bun, ids_new in (("before", A, set()), ("after", N, {nid})):
                sc = scene_of(bun, c, r, ids_new, hide_superficial=stem.startswith('splenius'))
                views = [dict(name=f"{nid}_{tag}_{n}", az=az, el=el, target=c, half=half) for n, az, el in (("post", 180, 10), ("lat", 90 if s == "r" else -90, 10), ("sup", 0, 75))]
                R.render(sc, views, out, size=(520, 520), prefix=f"{body}_")
            try:
                from PIL import Image
                rows = []
                for n in ("post", "lat", "sup"):
                    ims = [Image.open(out / f"{body}_{nid}_{t}_{n}.png") for t in ("before", "after")]
                    rows.append(np.hstack([np.asarray(i.convert("RGB")) for i in ims]))
                Image.fromarray(np.vstack(rows)).save(out / f"{body}_{nid}_before_after.png")
            except ImportError:
                pass
            print("rendered", nid)


if __name__ == "__main__":
    main()
