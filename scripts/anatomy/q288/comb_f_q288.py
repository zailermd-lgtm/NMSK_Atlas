#!/usr/bin/env python3
"""Q288: Combined · Female gets HER OWN uterus (segmented on her colour cryosections, scripts/anatomy/q288/uterus_q288.py).

    python3 scripts/anatomy/q288/comb_f_q288.py build [--out /dev/shm/q288/pre]   # page dir + data/derived/Q288_comb_f_report.json
    python3 scripts/anatomy/q288/comb_f_q288.py rig --fresh FILE                   # splice the new entry into data/anatomy/pose_rig_comb_f.json

No transfer: Combined · Female is in her CT frame (Q168 / Q287), and the uterus was registered to her CT, so it drops in unchanged.
Changes (everything else byte-identical to the live page build/q287/viewer_zan_female):
  + uterus_cryo_vhf   her uterus, body + cervix (subject ct_vhf_uterus);
  + hd (hidden by default, still listed, 'unhide' on the card) on the HRA reference uterus `uterus` (same donor's reference organ, Q233).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q287")); sys.path.insert(0, str(REPO / "scripts/anatomy/q288"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
import scripts.anatomy.q249.build_pages as BP  # noqa: E402
import comb_f_q287 as C287  # noqa: E402
import own_f_q288 as OWN  # noqa: E402

KEY, DIR = "comb_f", "viewer_zan_female"
STEM = BP.STEM[KEY]
LIVE = "build/q287/viewer_zan_female"
SUBJ = "ct_vhf_uterus"
HIDE = ["uterus"]
ATTR = (" Combined · Female, Q288: her own uterus (body + cervix), segmented on her colour cryosections (NLM Visible Human Project "
        "female, public domain) and registered to her CT, shown in the frame this page's Z-Anatomy structures are fitted to; the HRA "
        "reference uterus is kept, hidden by default.")


def build(out_root):
    import trimesh
    from trimesh.proximity import signed_distance
    src = REPO / LIVE
    man, blob = P5.load_page(src, STEM)
    ids = {m["id"] for m in man["meshes"]}
    items = json.loads((REPO / "build/vh" / SUBJ / "items.json").read_text())
    assert not ({it["id"] for it in items} & ids) and set(HIDE) <= ids
    rep = {"_README": ["Q288: Combined · Female + her cryosection uterus; scripts/anatomy/q288/comb_f_q288.py."]}
    G = C287.decode_all(man, blob)
    add = []
    for it in items:
        mm = trimesh.load(REPO / "build/vh" / SUBJ / it["obj"], process=False)
        P = trimesh.sample.sample_surface(mm, 4000, seed=288)[0]
        # overlap with this page's own pelvic structures (watertight ones only: signed distance needs a closed surface)
        ov = []
        c = mm.centroid
        for m in man["meshes"]:
            if m["id"] in HIDE or m["sys"] == "skin":
                continue
            v, f = G[m["id"]]
            if np.linalg.norm(v.mean(0) - c) > 120:
                continue
            t = trimesh.Trimesh(v, f, process=False)
            if not t.is_watertight:
                continue
            ins = float((signed_distance(t, P) > 1.0).mean())
            if ins > 0.01:
                ov.append({"id": m["id"], "sys": m["sys"], "surface_inside_gt1mm_pct": round(100 * ins, 1)})
        ov.sort(key=lambda r: -r["surface_inside_gt1mm_pct"])
        rep[it["id"]] = {"volume_cm3": round(float(mm.volume) / 1000, 1), "page_structures_it_crosses": ov}
        b = it["badge"] + (" On Combined · Female (Q288): unchanged mesh, in this page's frame (its Z-Anatomy structures are fitted to her "
                           "skeleton). The HRA reference uterus is hidden by default ('unhide' on its card).")
        if ov:
            b += (" Overlap reported, not corrected: " + ", ".join(f"{r['id']} {r['surface_inside_gt1mm_pct']} %" for r in ov[:4]) +
                  " of its surface lies > 1 mm inside these page structures (fitted or reference shapes, not her own).")
        add.append(({"name": it["name"], "id": it["id"], "side": "m", "sys": "viscera",
                     "rec": {**OWN.item_rec(it), "procedural_badge": b}}, np.asarray(mm.vertices), np.asarray(mm.faces)))
    man2 = json.loads(json.dumps(man))
    for m in man2["meshes"]:
        if m["id"] in HIDE:
            m["hd"] = 1
    man2["attribution"] = man["attribution"] + ATTR
    out = Path(out_root) / DIR
    P5.save_page(out, STEM, man2, blob, add=add)
    for f in list(src.glob("clinical_*")) + [src / "parts_data.json", src / "symmetry_q237.json", src / "plexus_groups.json"]:
        if f.exists():
            shutil.copy2(f, out / f.name)
    rep["added"] = [a[0]["id"] for a in add]; rep["hidden_default"] = HIDE
    rep["new_indices"] = list(range(len(man["meshes"]), len(man["meshes"]) + len(add)))
    (REPO / "data/derived/Q288_comb_f_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep, indent=1)[:1500])
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "rig"]); ap.add_argument("--out", default="/dev/shm/q288/pre")
    ap.add_argument("--fresh"); ap.add_argument("--committed", default=str(REPO / "data/anatomy/pose_rig_comb_f.json"))
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.out)
    else:
        rep = json.loads((REPO / "data/derived/Q288_comb_f_report.json").read_text())
        print(C287.splice_rig(a.committed, a.fresh, rep["new_indices"], a.committed,
                              f"; Q288: +{len(rep['new_indices'])} structure (her uterus from her cryosections) spliced in, every other entry as committed"))


if __name__ == "__main__":
    main()
