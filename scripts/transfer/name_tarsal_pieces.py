"""Name the seven tarsal pieces the male bundle carries as `tarsals_r/l` (the DU release ships each bone separately;
`mappings/du_vh_overrides.json` folded them into the composite, and the recovered bundle kept them as seven pieces
per side under one id).

    python3 scripts/transfer/name_tarsal_pieces.py data/derived/viewer_bundles/vhm_v25 -o mappings/subjects/vhm_both_piece_names.json

Rule, per side (x lateral = sign of the side; y up; z anterior):
  calcaneus = the largest piece;  talus = the second largest;
  cuboid    = of the rest, the lowest (it floors the lateral column, under the lateral cuneiform);
  navicular = of the rest, the widest across (largest x extent) -- it spans the three cuneiforms behind them;
  cuneiforms: the remaining three by x, medial -> intermediate -> lateral.
Checks printed: the calcaneus is the most posterior and the talus the highest piece; the medial cuneiform is larger
than the lateral, the intermediate the smallest. Output: {"tarsals_r": {"<piece order>": "<atlas id>", ...}, ...}
for `bundle_to_subjects.py --rename`. A KEY, not geometry.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_dir, read_bundle_html, decode, mesh_volume_cm3  # noqa: E402


def name_side(pieces, sign):
    """pieces: list of (order, v, f). Returns {order: id_stem}, and check messages."""
    info = []
    for o, v, f in pieces:
        c = v.mean(0); ext = v.max(0) - v.min(0)
        info.append({"o": o, "vol": mesh_volume_cm3(v, f), "c": c, "ext": ext})
    info.sort(key=lambda d: -d["vol"])
    names = {}; msgs = []
    calc, tal = info[0], info[1]; names[calc["o"]] = "calcaneus"; names[tal["o"]] = "talus"
    rest = info[2:]
    cub = min(rest, key=lambda d: d["c"][1]); names[cub["o"]] = "cuboid"; rest = [d for d in rest if d is not cub]   # the lowest: the cuboid sits on the floor of the lateral column
    nav = max(rest, key=lambda d: d["ext"][0]); names[nav["o"]] = "navicular"; rest = [d for d in rest if d is not nav]
    rest.sort(key=lambda d: sign * d["c"][0])             # medial first (smallest lateral coordinate)
    for d, nm in zip(rest, ("cuneiform_medial", "cuneiform_intermediate", "cuneiform_lateral")):
        names[d["o"]] = nm
    allp = {names[d["o"]]: d for d in info}
    msgs.append(f"calcaneus most posterior: {allp['calcaneus']['c'][2] <= min(d['c'][2] for d in info) + 1e-6}")
    msgs.append(f"talus highest: {allp['talus']['c'][1] >= max(d['c'][1] for d in info) - 1e-6}")
    msgs.append(f"cuneiform volumes medial {allp['cuneiform_medial']['vol']:.1f} > lateral {allp['cuneiform_lateral']['vol']:.1f} > "
                f"intermediate {allp['cuneiform_intermediate']['vol']:.1f}: "
                f"{allp['cuneiform_medial']['vol'] > allp['cuneiform_lateral']['vol'] > allp['cuneiform_intermediate']['vol']}")
    return names, msgs, {names[d["o"]]: round(d["vol"], 1) for d in info}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle"); ap.add_argument("-o", "--out", default="mappings/subjects/vhm_both_piece_names.json")
    a = ap.parse_args()
    p = Path(a.bundle); bm, blob = read_bundle_dir(p) if p.is_dir() else read_bundle_html(p)
    pieces = {"tarsals_r": [], "tarsals_l": []}; order = {"tarsals_r": 0, "tarsals_l": 0}
    for e, v, f in decode(bm, blob):
        if e["id"] in pieces:
            pieces[e["id"]].append((order[e["id"]], v, f)); order[e["id"]] += 1
    out = {"_README": [__doc__.strip().splitlines()[0], "piece order = the position among the pieces of that id in the bundle's structure list"],
           "source": "Andreassen et al. 2023, Sci Data 10:34, doi:10.1038/s41597-022-01905-2 (CC BY 4.0), Visible Human male lower-limb release; "
                     "named by the geometric rule in scripts/transfer/name_tarsal_pieces.py", "rename": {}, "volumes_cm3": {}}
    for sid, sign, sfx in (("tarsals_r", 1, "_r"), ("tarsals_l", -1, "_l")):
        if len(pieces[sid]) != 7:
            print(f"{sid}: {len(pieces[sid])} pieces, expected 7 -- not renamed"); continue
        names, msgs, vols = name_side(pieces[sid], sign)
        out["rename"][sid] = {str(o): nm + sfx for o, nm in names.items()}; out["volumes_cm3"][sid] = vols
        print(sid, {o: nm for o, nm in sorted(names.items())}); [print("  ", m) for m in msgs]
    Path(a.out).write_text(json.dumps(out, indent=1)); print("wrote", a.out)


if __name__ == "__main__":
    main()
