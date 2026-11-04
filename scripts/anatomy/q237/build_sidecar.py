#!/usr/bin/env python3
"""Q237: the Symmetric-view sidecar symmetry_q237.json of one page: the model's midsagittal plane + the left/right twins that are classified PAIRED (not lateralised, not midline).
    python3 scripts/anatomy/q237/build_sidecar.py PAGE_KEY [PAGE_DIR] -o OUT.json
The page is read from PAGE_DIR (default: core.PAGES[PAGE_KEY]); nothing else is touched. Twins whose sides differ much in size are still twins (they stay in; the view shows the mirror image of the chosen side)."""
from __future__ import annotations
import argparse, json, os, sys, datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C  # noqa: E402
import pairing as P  # noqa: E402


def build(key, page_dir=None):
    if page_dir:
        os.environ["Q237_SRC_" + key] = str(page_dir)
    S = C.load(key); C.groups_of(S)
    plane, q = C.fit_midsagittal(S)
    units, _ = P.classify(S, plane)
    # a twin whose two sides share a mesh id (own pages: both optic nerves are `optic_n`) cannot be told apart by id: left out of the mirror list (the id-based hide would hide the source too)
    pairs = [[u["ids_r"], u["ids_l"]] for u in units if u["cls"] == "paired" and not (set(u["ids_r"]) & set(u["ids_l"]))]
    lat = sum(1 for u in units if u["cls"] == "lateralised")
    return dict(version=1, page=key, label=C.PAGES[key][3], generated=datetime.date.today().isoformat(),
                note="Display only. Midsagittal plane fitted to the axial skeleton (scripts/anatomy/q237/core.py); pairs = L/R twins classified paired (data/derived/Q237_pairing.json). Lateralised organs are not in this list.",
                plane=dict(n=[round(float(x), 6) for x in plane.n], d=round(plane.d, 3), tilt_deg=round(plane.tilt_deg()["total_deg"], 3), tilt=plane.tilt_deg(), reflection_residual_median_mm=round(q["refl_median_mm"], 2)),
                n_pairs=len(pairs), n_lateralised_excluded=lat, n_ambiguous_ids_excluded=sum(1 for u in units if u["cls"] == "paired" and (set(u["ids_r"]) & set(u["ids_l"]))), pairs=pairs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key"); ap.add_argument("page_dir", nargs="?"); ap.add_argument("-o", "--out", required=True); a = ap.parse_args()
    d = build(a.key, a.page_dir)
    Path(a.out).write_text(json.dumps(d, separators=(",", ":")) + "\n")
    print(a.key, "pairs", d["n_pairs"], "plane", d["plane"]["n"], d["plane"]["d"], "->", a.out, os.path.getsize(a.out), "bytes")
