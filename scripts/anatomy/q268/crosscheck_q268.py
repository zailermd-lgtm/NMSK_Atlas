#!/usr/bin/env python3
"""Q268 (item 2) cross-check: recompute the needle tool's live vessel / nerve distances INDEPENDENTLY in Python
(trimesh closest_point on a densely sampled segment -- an upper bound on the true segment-to-surface distance, tight to
half the sample step) on the SAME rebuilt page geometry, and compare with the live JS readout recorded by
scripts/anatomy/q268/verify_ui_q268.py --out.

    python3 scripts/anatomy/q268/crosscheck_q268.py placements.json --own-dir DIR --zan-dir DIR [--step 0.05]

Prints, per placement, every structure the page reported with the JS and the Python distance and their difference, plus
any vessel / nerve structure Python finds within R that the page did not list (a miss) or vice versa. The Python side
classifies vessel / nerve with scripts/clinical/risk_structures_q188.py (the same JSON rule table the add-on carries),
so the comparison also checks that the JS listed the right set."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q237"))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
KEY_OF = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f",
          "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
CORR = {"artery", "vein", "nerve"}


def load_page(page_dir: Path):
    key = KEY_OF[page_dir.name]
    os.environ["Q237_SRC_" + key] = str(page_dir)
    import core as C
    import risk_structures_q188 as risk
    table = risk.load_risk_table()
    S = C.load(key)
    out = []
    for x in S:
        rec = {"id": x["id"], "name": x.get("name") or x["id"], "cat": x["sys"]}
        r = x.get("rec") or {}
        if isinstance(r, dict) and r.get("vt"):
            rec["vt"] = r["vt"]
        cls = risk.classify(rec, table)
        if cls in CORR:
            v = np.asarray(x["v"], dtype=np.float64); f = np.asarray(x["f"], dtype=np.int64)
            out.append({"id": x["id"], "name": rec["name"], "cls": cls, "v": v, "f": f, "bmin": v.min(0), "bmax": v.max(0)})
    return out


def seg_samples(E, T, step):
    E = np.asarray(E, float); T = np.asarray(T, float)
    L = float(np.linalg.norm(T - E))
    n = max(1, int(np.ceil(L / step)))
    t = np.linspace(0, 1, n + 1)[:, None]
    return E + t * (T - E), L / n if n else 0.0


def box_dist(pts, bmin, bmax):
    d = np.maximum(np.maximum(bmin - pts, 0), pts - bmax)
    return float(np.sqrt((d * d).sum(1)).min())


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("placements"); ap.add_argument("--own-dir", required=True); ap.add_argument("--zan-dir", required=True)
    ap.add_argument("--step", type=float, default=0.05)
    a = ap.parse_args(argv)
    P = json.loads(Path(a.placements).read_text())
    dirs = {Path(a.own_dir).name: Path(a.own_dir), Path(a.zan_dir).name: Path(a.zan_dir)}
    cache = {}
    worst = 0.0; n_cmp = 0; misses = 0; extras = 0
    seen = set()
    for pl in P:
        key = (pl["page"], pl["label"], tuple(pl["target"]), tuple(pl["entry"] or []))
        if key in seen:        # the same harness placement is made at both viewports: one cross-check is enough
            continue
        seen.add(key)
        page = pl["page"]
        if page not in cache:
            print(f"loading {dirs[page]} ...", flush=True)
            cache[page] = load_page(dirs[page])
        structs = cache[page]
        E = pl["entry"] if pl["entry"] else pl["target"]
        pts, step = seg_samples(E, pl["target"], a.step)
        R = pl["R"]
        py = {}
        for s in structs:
            if s["id"] == pl["target_id"]:
                continue
            if box_dist(pts, s["bmin"], s["bmax"]) > R + 1.0:
                continue
            mesh = trimesh.Trimesh(vertices=s["v"], faces=s["f"], process=False)
            _, d, _ = trimesh.proximity.closest_point(mesh, pts)
            dm = float(d.min())
            if dm <= R:
                py[s["id"]] = min(dm, py.get(s["id"], np.inf))
        js = {it["id"]: it["d_mm"] for it in pl["items"]}
        print(f"\n=== {page} / {pl['label']} (entry {E}, target {pl['target']}, R = {R} mm, JS measured {pl['n_measured']} meshes in {pl['ms']} ms; "
              f"Python sampled every {step:.3f} mm) ===")
        print(f"  {'structure':44s} {'JS mm':>8s} {'Py mm':>8s} {'diff':>7s}")
        for sid, djs in sorted(js.items(), key=lambda kv: kv[1]):
            if sid in py:
                diff = djs - py[sid]; worst = max(worst, abs(diff)); n_cmp += 1
                flag = "" if abs(diff) <= step / 2 + 0.05 else "   <-- DIFFERS"
                print(f"  {sid[:44]:44s} {djs:8.3f} {py[sid]:8.3f} {diff:+7.3f}{flag}")
            else:
                extras += 1
                print(f"  {sid[:44]:44s} {djs:8.3f} {'--':>8s}         <-- listed by JS, not within R for Python")
        for sid, dpy in sorted(py.items(), key=lambda kv: kv[1]):
            if sid not in js:
                misses += 1
                print(f"  {sid[:44]:44s} {'--':>8s} {dpy:8.3f}         <-- found by Python within R, missing from the JS list")
    print(f"\nSUMMARY: {n_cmp} structure distances compared, worst |JS - Python| = {worst:.3f} mm "
          f"(Python is an upper bound tight to {a.step / 2:.3f} mm); {misses} missing from JS, {extras} extra in JS")
    return 0 if (misses == 0 and extras == 0 and worst <= a.step / 2 + 0.05) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
