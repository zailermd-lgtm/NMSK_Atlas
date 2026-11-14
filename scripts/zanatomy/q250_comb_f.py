#!/usr/bin/env python3
"""Q250 (item 5): Combined · Female with HER OWN pelvis. The Z-Anatomy pelvic bones of the page (hip bones, sacrum, coccyx: male-derived shape, similarity-fitted to her; subpubic angle 62.7 deg) are
deformed (landmark thin-plate pre-warp + non-rigid coherent point drift) onto her own pelvis (her CT hip bones + the HRA sacrum / coccyx of the same donor), and the Z soft structures near the pelvis are carried
with them (bone-anchored thin-plate spline, scripts/anatomy/q250/warp.py). NOT carried (they already sit on HER pelvis or on her skin): the HRA / CVH structures (organs, vagina, ligaments, vessels, perineal
structures, breasts) and the skin; guards (bone penetration, skin) are still reported for them.
    python3 scripts/zanatomy/q250_comb_f.py [--src build/q244/viewer_zan_female] [--out build/q250_pre/viewer_zan_female]"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.anatomy.q250 import lib as L, pelvis_reg as PR, warp as W, her_pelvis as HP  # noqa: E402

STEM = "atlas_viewer_zan_female"
WORK = REPO / "build" / "q250_work"
RING = ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx")
MIN_MOVE_MM = 0.05


def added_ids(src, base="build/q225/viewer_zan_female"):
    a = {m["id"] for m in P5.load_page(REPO / src, STEM)[0]["meshes"]}
    b = {m["id"] for m in P5.load_page(REPO / base, STEM)[0]["meshes"]}
    return sorted(i for i in a - b if not i.startswith("zan_"))


def run(src, out):
    t0 = time.time(); WORK.mkdir(parents=True, exist_ok=True)
    man, blob = P5.load_page(REPO / src, STEM)
    Z = P5.decode(man, blob)
    exempt = set(added_ids(src)) | {i for i, e in Z.items() if e["m"]["sys"] == "skin"}
    her = HP.her_ring()
    cache = WORK / "ring_comb_f.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True); ring = {k: z[k] for k in RING}; rrep = json.loads(str(z["report"]))
    else:
        pts = np.vstack([L.sample(v, f, 20000)[0] for v, f in her.values()])
        res = PR.register({k: (Z[k]["v"], Z[k]["f"]) for k in RING}, pts, target_ring=her)
        ring, rrep = res["v"], res["report"]
        np.savez(cache, report=json.dumps(rrep), **ring)
    tgt = {i: e["v"] for i, e in Z.items() if e["m"]["sys"] == "bone"}
    for k in RING:
        tgt[k] = ring[k]
    A = W.apply(Z, tgt, exempt=exempt)
    rep = A["report"]
    repl, moved = {}, []
    for i, e in Z.items():
        v1 = A["v"][i]
        if not len(v1) or np.abs(v1 - e["v"]).max() < 1e-6 or (i not in RING and rep["structures"][i]["mean_move_mm"] < MIN_MOVE_MM and not rep["structures"][i].get("newly_in_bone")):
            continue
        st = rep["structures"][i]
        rec = dict(e["m"].get("rec") or {"name": e["m"]["name"]}); old = rec.get("procedural_badge")
        if i in RING:
            r = rrep.get(i, {})
            old = None if old and old.startswith("Q233 sex audit") else old
            txt = ("Q250 own pelvis: this pelvic bone was a Z-Anatomy bone (male-derived shape) similarity-fitted to her; it is now DEFORMED (landmark thin-plate warp + non-rigid coherent point drift) onto HER OWN "
                   f"pelvis (her CT hip bones; HRA sacrum / coccyx of the same donor): distance to her pelvis median {r.get('median_mm')} mm, p90 {r.get('p90_mm')} mm. Anatomy, vertex order and muscle "
                   "attachments are Z-Anatomy's.")
        else:
            txt = (f"Q250 own pelvis: carried with the deformation of the pelvic bones onto her own pelvis (bone-anchored thin-plate spline; within 1.5 mm of a bone it moves with that bone): mean displacement "
                   f"{st['mean_move_mm']} mm, max {st['max_move_mm']} mm; surface area x{st['area_ratio']:.3f}")
            if st.get("signed_volume_ratio") is not None and st["signed_volume_before_mm3"] > 50:
                txt += f", enclosed volume x{st['signed_volume_ratio']:.3f}"
            if st.get("newly_in_bone"):
                txt += f"; {st['newly_in_bone']} vertices pushed out of a bone (0.4 mm)"
            if st.get("newly_outside_skin"):
                txt += f"; {st['newly_outside_skin']} vertices pulled back inside her skin"
            txt += "."
        rec["procedural_badge"] = (old + " || " if old else "") + txt
        repl[i] = (v1, e["f"], rec); moved.append(i)
    man = dict(man); man["attribution"] = (man.get("attribution") or "").rstrip() + (
        " Q250: the pelvic bones of this page (hip bones, sacrum, coccyx) are Z-Anatomy bones deformed onto the Visible Human female's OWN pelvis (her CT hip bones; HuBMAP HRA sacrum / coccyx of the same donor, "
        "CC BY 4.0), the Z soft structures around the pelvis follow; her skin and the HRA / CVH structures are unchanged.")
    P5.save_page(REPO / out, STEM, man, blob, replace=repl)
    import shutil
    for f in (REPO / src).glob("clinical_*"):
        shutil.copy2(f, REPO / out / f.name)
    np.savez_compressed(WORK / "warp_field_comb_f.npz", P=A["control"][0], U=A["control"][1], SP=A["samples"][0].astype(np.float32), SU=A["samples"][1].astype(np.float32))
    R = dict(source=src, pelvis_registration=rrep, exempt=sorted(exempt), moved=sorted(moved), warp={k: v for k, v in rep.items() if k != "structures"}, structures=rep["structures"], seconds=round(time.time() - t0))
    (REPO / "data/derived/Q250_comb_f_warp_report.json").write_text(json.dumps(R, indent=1, default=float) + "\n")
    print("done", R["seconds"], "s; moved", len(moved), "newly in bone", rep["newly_in_bone_vertices"], "outside skin", rep["newly_outside_skin_vertices"], rep.get("attachment_distance_after_mm"))
    return R


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default="build/q244/viewer_zan_female"); ap.add_argument("--out", default="build/q250_pre/viewer_zan_female")
    a = ap.parse_args(); run(a.src, a.out)
