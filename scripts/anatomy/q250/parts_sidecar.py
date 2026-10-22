#!/usr/bin/env python3
"""Q250: the page's parts_data.json (sourced parts + placed markers, Q219 / Q220) for a DEFORMED page. The placements of the Z structures were computed on the old geometry; here every placed point of a moved
structure is carried with the SAME Q250 field (warp.carry; Combined: only placements whose meshes were moved), written to a temporary geometry file, and the unchanged Q220 builder then re-CHECKS every
placement against the new page geometry (those that no longer fit are dropped with the reason recorded).  Base: the Q243 uterus / tube sub-part markers are recomputed with the new pelvis registration.
    python3 scripts/anatomy/q250/parts_sidecar.py base_f|comb_f PAGE_DIR OUT.json"""
from __future__ import annotations
import copy, json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts" / "anatomy")); sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q220"))
import build_parts_sidecar as BPS  # noqa: E402
from scripts.anatomy.q250 import warp as W  # noqa: E402

CFG = {"base_f": dict(body="zbase_f", geo="Q220_parts_zbase_f.json", field="warp_field_her.npz", html="atlas_viewer_base_female.html"),
       "comb_f": dict(body="zan_f", geo="Q219_parts_zan_f.json", field="warp_field_comb_f.npz", html="atlas_viewer_zan_female.html")}


def carried_geo(key):
    c = CFG[key]
    geo = json.loads((REPO / "data/derived" / c["geo"]).read_text())
    f = np.load(REPO / "build/q250_work" / c["field"])
    ctrl, smp = (f["P"], f["U"]), (f["SP"], f["SU"])
    moved = None
    if key == "comb_f":
        moved = set(json.loads((REPO / "data/derived/Q250_comb_f_warp_report.json").read_text())["moved"])
    n = 0
    out = copy.deepcopy(geo)
    for p in out["placed"]:
        if moved is not None and not all(m in moved for m in p["mesh_ids"]):
            continue
        pts = [p["position_mm"]] + (list(p["bbox_mm"]) if p.get("bbox_mm") else [])
        new = W.carry(np.array(pts, float), ctrl, smp)
        p["position_mm"] = [round(float(x), 2) for x in new[0]]
        if p.get("bbox_mm"):
            lo = new[1:].min(0); hi = new[1:].max(0); p["bbox_mm"] = [[round(float(x), 2) for x in lo], [round(float(x), 2) for x in hi]]
        n += 1
    out["source"] = (geo.get("source") or "") + " + Q250 carried (the placed points of moved structures carried with the Q250 field)"
    return out, n


def main(key, page_dir, out):
    c = CFG[key]
    geo, n = carried_geo(key)
    tmp = REPO / "build/q250_work/parts_geo"; tmp.mkdir(parents=True, exist_ok=True)
    (tmp / c["geo"]).write_text(json.dumps(geo))
    html = Path(page_dir) / c["html"]
    D = BPS.build(html, c["body"], geo_dir=tmp, check=True)
    D["geometry"]["note_q250"] = f"{n} placements carried with the Q250 deformation field before the check"
    if key == "base_f":
        # uterus / tube sub-part markers with the NEW pelvis registration (Q250 chain of the Q233 patch)
        from scripts.anatomy.q243 import parts_hra as PH
        rep = json.loads((REPO / "data/derived/Q250_chain_Q233_report_base_f.json").read_text())["registration"]
        T0 = (rep["scale"], np.array(rep["rotation"]), np.array(rep["translation_mm"]))
        from scripts.zanatomy import q205_pages as P5
        man, blob = P5.load_page(Path(page_dir), "atlas_viewer_base_female"); S = P5.decode(man, blob)
        meshes = {i: (S[i]["v"], S[i]["f"]) for i in ("uterus", "uterine_tube_l", "uterine_tube_r") if i in S}
        mk = PH.place("zbase_f", T0, meshes)
        Path(out).write_text(json.dumps(D, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
        tmpd = Path(out).parent
        PH.inject(tmpd, "zbase_f", mk)                               # appends the Q243 rows + the new markers to parts_data.json of that dir (idempotent)
        print("hra parts markers ok", sum(1 for m in mk if m["ok"]), "/", len(mk))
    else:
        Path(out).write_text(json.dumps(D, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")
    g = D["geometry"]
    print(json.dumps({"out": str(out), **D["counts"], "placements_in_file": g["placements_in_file_for_this_page"], "dropped": len(g["dropped"]), "carried": n}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
