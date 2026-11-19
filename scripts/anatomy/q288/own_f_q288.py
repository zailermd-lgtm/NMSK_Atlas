#!/usr/bin/env python3
"""Q288: her uterus (from her colour cryosections, scripts/anatomy/q288/uterus_q288.py) onto Imaging-based Female.

    python3 scripts/anatomy/q288/own_f_q288.py baseline [--out /dev/shm/q288/base]  # rebuild the CURRENT own_f page from build/q287_pre/bundle_own_f, prove geo == build/q287/viewer_f_hr
    python3 scripts/anatomy/q288/own_f_q288.py build [--out /dev/shm/q288/pre]      # baseline + uterus_cryo_vhf, HRA `uterus` hidden_default
    python3 scripts/anatomy/q288/own_f_q288.py rig --fresh FRESH.json               # splice the new rig entry into data/anatomy/pose_rig_own_f.json

The HRA reference uterus (subject xfer_hra2vhf_q233, same donor's reference organ) stays listed, hidden by default (Q184 hidden_default:
picking it from the list shows it); every other entry unchanged.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO, REPO / "scripts/anatomy/q286", REPO / "scripts/anatomy/q287"):
    sys.path.insert(0, str(p))
import build_pages_286 as Q286          # noqa: E402

KEY = "own_f"
BASE = "build/q287_pre/bundle_own_f"
LIVE = "build/q287/viewer_f_hr"
SUBJ = "ct_vhf_uterus"
NEW = ["uterus_cryo_vhf"]
HIDE = ["uterus"]
ATTR = ("Her uterus (Q288): segmented on her own colour cryosections (NLM Visible Human Project female, public domain) by a 3-D random "
        "walker from operator-placed interior seeds (data/derived/Q288_seeds.json), re-registered to her CT; not a reference organ, not "
        "drawn from an atlas.")


def item_rec(it):
    return {"name": it["name"], "latin": it["latin"], "folder": "viscera", "region": "pelvis",
            "source": "Her own colour cryosections (NLM Visible Human Project female, public domain), photo-segmented with operator seeds, registered to her CT",
            "procedural_badge": it["badge"]}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["baseline", "build", "rig"]); ap.add_argument("--fresh")
    ap.add_argument("--out", default="/dev/shm/q288/pre")
    a = ap.parse_args()
    Q286.LIVE[KEY] = LIVE
    if a.cmd == "rig":
        import comb_f_q287 as C
        B = json.loads((Path(a.out) / f"bundle_{KEY}" / "bundle.json").read_text())["structures"]
        order = [e["id"] for e in B]
        rig = REPO / f"data/anatomy/pose_rig_{KEY}.json"
        print(C.splice_rig(rig, a.fresh, sorted(order.index(i) for i in NEW), rig,
                           "; Q288: +1 structure (her uterus from her cryosections) spliced in, every other entry as committed"))
        return
    from scripts.transfer.q200_bundle import Bundle
    B = Bundle(REPO / BASE)
    if a.cmd == "baseline":
        d = Q286.write_page(KEY, B, {}, a.out)
        live, mine = Q286.geo_digest(KEY, REPO / LIVE), Q286.geo_digest(KEY, d)
        print("geo files identical to the live page:", live == mine, len(live), "files")
        return
    import trimesh
    items = json.loads((REPO / "build/vh" / SUBJ / "items.json").read_text())
    assert [it["id"] for it in items] == NEW
    for it in items:
        m = trimesh.load(REPO / "build/vh" / SUBJ / it["obj"], process=False)
        B.add(it["id"], "organ", it["side"], SUBJ, item_rec(it), m.vertices, m.faces)
    n = 0
    for x in B.items:
        if x["e"]["id"] in HIDE:
            assert x["e"]["subject"] == "xfer_hra2vhf_q233"
            x["e"]["hidden_default"] = True; n += 1
    assert n == len(HIDE)
    d = Q286.write_page(KEY, B, {SUBJ: ATTR}, a.out)
    print("wrote", d, "added", NEW, "hidden_default", HIDE)


if __name__ == "__main__":
    main()
