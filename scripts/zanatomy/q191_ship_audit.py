"""Q191 no-regression check on the SHIPPED geometry: every structure of build/viewer_zan_female_q191 vs v7 (build/viewer_zan_female), vertex by vertex.

    python3 scripts/zanatomy/q191_ship_audit.py [--before DIR] [--after DIR] [--out data/derived/Q191_ship_diff.json]
A structure counts as unchanged when it has the same vertex count and its largest vertex displacement is <= 0.05 mm (16-bit quantisation of
a mesh whose bounding box did not move is bit-identical).  The changed set must lie in the hand / wrist scope (scripts/zanatomy/q191_hand.scope)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q191_hand as H  # noqa: E402
from scripts.zanatomy import trunk_refit_q186c_audit as A186  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=str(REPO / "build" / "viewer_zan_female"))
    ap.add_argument("--after", default=str(REPO / "build" / "viewer_zan_female_q191"))
    ap.add_argument("--out", default=str(REPO / "data" / "derived" / "Q191_ship_diff.json"))
    a = ap.parse_args(argv)
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    Mb, Ma = A186.load_viewer(Path(a.before)), A186.load_viewer(Path(a.after))
    assert set(Mb) == set(Ma), "structure sets differ"
    pend = [{"mesh_id": k, "cat": m["sys"]} for k, m in Mb.items()]
    in_scope = set(H.scope(pend, regions, "r")) | set(H.scope(pend, regions, "l")) | {i for s in "rl" for i in sum(H.bone_ids(s).values(), [])}
    changed, unchanged, bad = {}, 0, []
    for k, mb in Mb.items():
        ma = Ma[k]
        if len(mb["v"]) != len(ma["v"]) or len(mb["f"]) != len(ma["f"]):
            d = float("inf")
        else:
            d = float(np.abs(mb["v"] - ma["v"]).max())
        if d > 0.05 and np.isfinite(d):          # decimation may renumber the vertices of a moved mesh: compare as point sets (max nearest-vertex distance, both ways)
            from scipy.spatial import cKDTree
            d = float(max(cKDTree(mb["v"]).query(ma["v"])[0].max(), cKDTree(ma["v"]).query(mb["v"])[0].max()))
        if d <= 0.05:
            unchanged += 1
        else:
            changed[k] = round(d, 2) if np.isfinite(d) else "topology changed"
            if k not in in_scope:
                bad.append(k)
    # regional summary of what did NOT change
    reg = {}
    for k, m in Mb.items():
        r = regions.get(k, "other")
        reg.setdefault(r, [0, 0])
        reg[r][0] += 1
        reg[r][1] += int(k not in changed)
    out = {"structures": len(Mb), "unchanged_within_0.05mm": unchanged, "changed": len(changed), "changed_outside_hand_scope": bad,
           "changed_ids": changed, "unchanged_by_q168_region": {k: {"total": v[0], "unchanged": v[1]} for k, v in reg.items()}}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print({k: v for k, v in out.items() if k not in ("changed_ids", "unchanged_by_q168_region")})
    print(out["unchanged_by_q168_region"])


if __name__ == "__main__":
    main()
