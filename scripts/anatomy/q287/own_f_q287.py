#!/usr/bin/env python3
"""Q287: the fibroglandular tissue inside her CT breasts (scripts/anatomy/q287/breast_fgt_q287.py) onto Imaging-based Female too.

    python3 scripts/anatomy/q287/own_f_q287.py baseline   # rebuild the CURRENT own_f page from build/q286_pre/bundle_own_f, prove geo == build/q286/viewer_f_hr
    python3 scripts/anatomy/q287/own_f_q287.py build      # baseline + breast_fgt_ct_r / _l -> build/q287_pre/viewer_f_hr
    python3 scripts/anatomy/q287/own_f_q287.py rig --fresh FRESH.json   # splice the 2 new rig entries into data/anatomy/pose_rig_own_f.json

Same structure, same frame (her own CT, her atlas frame) as on Combined · Female; every other entry unchanged.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q286"):
    sys.path.insert(0, str(p))
import build_pages_286 as Q286          # noqa: E402

KEY = "own_f"
BASE = "build/q286_pre/bundle_own_f"
SUBJ = "ct_vhf_breast_fgt"
ATTR = ("Fibroglandular tissue of her breasts (Q287): voxels at HU >= -30 inside her Q285 breasts on her own CT (NLM Visible Human "
        "Project female CT, public domain), skin rim and her pectoral muscle labels excluded; a stated threshold rule, not hand-drawn.")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["baseline", "build", "rig"]); ap.add_argument("--fresh")
    ap.add_argument("--out", default="build/q287_pre")
    a = ap.parse_args()
    Q286.LIVE[KEY] = "build/q286/viewer_f_hr"
    if a.cmd == "rig":
        import comb_f_q287 as C
        B = json.loads((REPO / a.out / f"bundle_{KEY}" / "bundle.json").read_text())["structures"]
        order = [e["id"] for e in B]
        new = [order.index(i) for i in ("breast_fgt_ct_r", "breast_fgt_ct_l")]
        rig = REPO / f"data/anatomy/pose_rig_{KEY}.json"
        print(C.splice_rig(rig, a.fresh, sorted(new), rig, "; Q287: +2 structures (fibroglandular tissue of her CT breasts) spliced in, "
                                                          "every other entry as committed"))
        return
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(REPO / BASE)
    if a.cmd == "baseline":
        d = Q286.write_page(KEY, B, {}, "build/q287_base")
        live, mine = Q286.geo_digest(KEY, REPO / Q286.LIVE[KEY]), Q286.geo_digest(KEY, d)
        print("geo files identical to the live page:", live == mine, len(live), "files")
        return
    import trimesh
    items = json.loads((REPO / "build/vh" / SUBJ / "items.json").read_text())
    for it in items:
        m = trimesh.load(REPO / "build/vh" / SUBJ / it["obj"], process=False)
        rec = {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "breast",
               "source": "Her own CT (NLM Visible Human Project, public domain); rule-based HU threshold inside her Q285 breast",
               "procedural_badge": it["badge"]}
        B.add(it["id"], "organ", it["side"], SUBJ, rec, m.vertices, m.faces)
    d = Q286.write_page(KEY, B, {SUBJ: ATTR}, a.out)
    print("wrote", d, "added", [i["id"] for i in items])


if __name__ == "__main__":
    main()
