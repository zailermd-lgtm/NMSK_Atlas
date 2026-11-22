#!/usr/bin/env python3
"""Q250: the structures that the Q248 agent added to a Z page (rule-based pelvic-floor / patellar ligaments, CVH anococcygeal ligament, ...) were placed relative to the OLD (male-derived) bones.
Carry them with the SAME Q250 bone-anchored field (scripts/anatomy/q250/warp.carry) and add them to the Q250 pre-page.
    python3 scripts/zanatomy/q250_carry_q248.py base_f|comb_f [--q248 build/q248/<dir>] [--q244 build/q244/<dir>] [--pre build/q250_pre/<dir>] [--field build/q250_work/warp_field_<x>.npz]
Only ids present in the Q248 page and absent from the Q244 page are carried; structures already on the pre-page are skipped (re-run safe)."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
from scripts.anatomy.q250 import warp as W  # noqa: E402

CFG = {"base_f": dict(dir="viewer_base_female", stem="atlas_viewer_base_female", field="warp_field_{pelvis}.npz", moved=True),
       "comb_f": dict(dir="viewer_zan_female", stem="atlas_viewer_zan_female", field="warp_field_comb_f.npz", moved=True)}
GEOM = {"vo", "vc", "io", "ic", "min", "span"}


def run(which, q248, q244, pre, field, pelvis="her"):
    c = CFG[which]; stem = c["stem"]
    q248, q244, pre = (REPO / x for x in (q248, q244, pre))
    f = np.load(Path(field))
    m8, b8 = P5.load_page(q248, stem); m4, _ = P5.load_page(q244, stem); mp, bp = P5.load_page(pre, stem)
    have = {m["id"] for m in mp["meshes"]}
    new_ids = [m["id"] for m in m8["meshes"] if m["id"] not in {x["id"] for x in m4["meshes"]} and m["id"] not in have]
    S8 = P5.decode(m8, b8, only=lambda m: m["id"] in new_ids)
    add, rep = [], {}
    for i in new_ids:
        e = S8[i]; V1 = W.carry(e["v"], (f["P"], f["U"]), (f["SP"], f["SU"]))
        ent = {k: v for k, v in e["m"].items() if k not in GEOM}
        rec = dict(ent.get("rec") or {"name": ent["name"]})
        d = np.linalg.norm(V1 - e["v"], axis=1)
        rec["procedural_badge"] = ((rec.get("procedural_badge") + " || ") if rec.get("procedural_badge") else "") + (
            f"Q250: placed by the Q248 rule on the Z-Anatomy pelvis / bones of this page, then carried with the Q250 female-skeleton deformation (bone-anchored thin-plate spline): mean displacement "
            f"{d.mean():.1f} mm, max {d.max():.1f} mm.")
        ent["rec"] = rec
        add.append((ent, V1, e["f"])); rep[i] = dict(mean_move_mm=round(float(d.mean()), 2), max_move_mm=round(float(d.max()), 1), vertices=int(len(V1)))
    if add:
        P5.save_page(pre, stem, mp, bp, add=add)
    (REPO / f"data/derived/Q250_carry_q248_{which}.json").write_text(json.dumps(dict(page=which, q248=str(q248), carried=rep), indent=1) + "\n")
    print(which, "carried", len(add), sorted(rep))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("which", choices=list(CFG)); ap.add_argument("--q248"); ap.add_argument("--q244"); ap.add_argument("--pre"); ap.add_argument("--field")
    ap.add_argument("--pelvis", default="her"); a = ap.parse_args()
    c = CFG[a.which]
    run(a.which, a.q248 or f"build/q248/{c['dir']}", a.q244 or f"build/q244/{c['dir']}", a.pre or f"build/q250_pre/{c['dir']}", a.field or str(REPO / "build/q250_work" / c["field"].format(pelvis=a.pelvis)), a.pelvis)
