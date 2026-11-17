#!/usr/bin/env python3
"""Q367: the injection mode's Safety panel needs a size class (large / medium / small) for every artery and vein of the page.
This writes the PRIVATE sibling `clinical_vessel_calibre.json` (Base pages only) from the page's OWN current meshes -- the
geometry as built now (after the Q357 conforms etc.), not the older pages data/anatomy/calibre.json was measured on.

Which structures: every mesh the needle tool classes as an artery or a vein (the RISK_TABLE rule table in
clinical/needle_tool.js, parsed by scripts/clinical/risk_structures_q188.py -- so the browser and this script agree).

Method (the Q240 tube estimator, scripts/anatomy/q240/calibre.py, unchanged): all pieces sharing an id are merged; the vertices are
ordered along the principal axis and cut into slabs about one tube diameter thick; per slab, the median perpendicular distance of
its vertices to the LOCAL axis (through the neighbouring slab centres); diameter = 2 x the median over slabs. Cross-check: lateral
area / (pi x centreline length); when the two disagree by more than a factor 2 the smaller is kept. Medians of medians: a branch
stub, a cap or a few stray vertices do not move it (robust). Decimated viewing meshes: approximate.

`p` = 1 marks a named main trunk (Q240's TRUNKS_A list in scripts/anatomy/q240/make_calibre.py); the page treats it as a large
vessel whatever its mesh calibre, the same promotion the page's nerve calibre table (#nmsk-calibre) carries for nerves.

    python3 scripts/clinical/build_vessel_calibre_q367.py base_m <page dir>    # writes <page dir>/clinical_vessel_calibre.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
for p in ("scripts", "scripts/anatomy/q220", "scripts/anatomy/q240", "scripts/anatomy/q236", "scripts/clinical", ""):
    sys.path.insert(0, str(REPO / p))
from calibre import tube_diameter  # noqa: E402
import make_calibre as mc  # noqa: E402
import risk_structures_q188 as rq  # noqa: E402
import build_parts_sidecar as sc  # noqa: E402

NAME = "clinical_vessel_calibre.json"
PAGES = ("base_m", "base_f")
LICENCE = ("PRIVATE -- owner's clinical layer (see clinical/LICENSE_PRIVATE.md). Not CC BY-SA, not for redistribution. "
           "Holds measurements about the anatomy model, not the model.")
METHOD = ("Per artery / vein id (class by the needle tool's RISK_TABLE): all pieces merged; Q240 tube estimator "
          "(scripts/anatomy/q240/calibre.py) -- slabs ~1 diameter thick along the principal axis, per slab the median "
          "perpendicular vertex distance to the local axis, diameter = 2 x median over slabs; cross-check lateral area / "
          "(pi x centreline length), the smaller kept when they disagree > 2x. p = 1: a named main trunk (Q240 TRUNKS_A), "
          "large whatever its mesh calibre. Decimated viewing meshes of this page, measured at build time: approximate.")


def page_html(d: Path) -> Path:
    c = sorted(p for p in d.glob("atlas_viewer_*.html") if p.suffix == ".html")
    if not c:
        sys.exit(f"no atlas_viewer_*.html in {d}")
    return c[0]


def build(page: str, d: Path) -> dict:
    table = rq.load_risk_table()
    _, out = sc.load_page(page_html(d))
    by: dict[str, list] = {}
    for sid, sd, cat, V, F in out:
        k = rq.classify({"id": sid, "name": sid.replace("_", " "), "cat": cat, "vt": None}, table)
        if k not in ("artery", "vein"):
            continue
        e = by.setdefault(sid, [k, [], [], 0])
        e[1].append(V); e[2].append(F + e[3]); e[3] += len(V)
    c = {}
    for sid, (k, Vs, Fs, _) in sorted(by.items()):
        r = tube_diameter(np.vstack(Vs), np.vstack(Fs))
        d_mm = r["diameter_mm"]
        p = 1 if mc.TRUNKS_A.match(mc.norm(sid)) else 0
        c[sid] = [round(float(d_mm), 2) if d_mm is not None else None, p]
    return {"schema": "nmsk.vessel_calibre.v1", "page": page, "licence": LICENCE, "method": METHOD, "n": len(c), "c": c}


def main(argv=None) -> int:
    a = sys.argv[1:] if argv is None else argv
    if len(a) != 2 or a[0] not in PAGES:
        print(__doc__)
        return 2
    d = Path(a[1])
    doc = build(a[0], d)
    (d / NAME).write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    none = sum(1 for v in doc["c"].values() if v[0] is None)
    print(f"{a[0]}: wrote {d / NAME} ({doc['n']} vessels, {none} without a diameter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
