#!/usr/bin/env python3
"""Q202: scoped skin repairs on the four Z-Anatomy pages (no full rebuild: the shipped geometry bundle is patched, every other structure stays byte-identical).

  base_f   closure of the perineal opening (rule-based hole fill, badged 'surface closure, not anatomy')
  fit_f    (a) all skin patches welded to their neighbours (cross-side too), (b) the same perineal closure on the welded loop
  fit_m    residual seams of the whole skin (cross-side pairs, anal / gluteal / wrist)
  base_m   unchanged (audited: no skin hole; ankle skin_step = the section cutting through the toes; quadratus femoris flat end = insertion face)

    python3 scripts/zanatomy/q202_build.py base_f|fit_f|fit_m [--out build/q202/<name>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_pages as P  # noqa: E402
from scripts.zanatomy import q202_closure as C  # noqa: E402

CLOSURE_ID = "zan_skin_perineal_closure"
LOOP = REPO / "data" / "derived" / "Q202_perineal_loop.json"


def skin_of(page_key):
    d, s = P.PAGES[page_key]
    man, blob = P.load_page(REPO / d, s)
    S = P.decode(man, blob, only=lambda m: m["sys"] == "skin")
    return man, blob, S


def loop_positions(S, spec):
    """loop vertices (the neighbours' own vertices, averaged over the patches that share the position) and their inner rim partners, on page skin S"""
    L1, L2 = [], []
    for n in spec["loop"]:
        L1.append(np.mean([S[p]["v"][i] for p, i in n["members"]], axis=0))
        L2.append(np.mean([S[p]["v"][i] for p, i in n["partner_members"]], axis=0))
    return np.array(L1), np.array(L2)


def closure_badge(info, extra=""):
    return (f"Q202: SURFACE CLOSURE, NOT ANATOMY. Z-Anatomy has no female perineal skin: its two male-only urogenital skin patches (penile, scrotal and perineal skin) are removed for this body "
            f"(Q196), which left the neighbouring skin patches (anal, hypogastric, inguinal, femoral triangle, thigh) with a free rim loop of {info['loop_vertices']} vertices "
            f"(perimeter {info['loop_perimeter_mm']} mm) and an opening between the thighs. This patch is rule-based hole fill: the outer sheet is the smooth minimal surface "
            f"(Pinkall-Polthier iteration, cotangent weights) spanning that loop, area {info['outer_area_mm2']} mm2, max displacement of the surface from the harmonic start map "
            f"{info['max_displacement_from_harmonic_mm']} mm (surface to loop best-fit plane {info['max_sag_from_plane_mm']} mm), thickness up to 3.0 mm like every Z skin patch, boundary vertices = the neighbouring patches' own rim vertices (welded seam, step 0). "
            f"No vulva, labia, clitoris or vaginal opening is modelled and nothing here is a measurement of a body.{extra}")


def make_closure(L1, L2):
    r = C.build_slab(L1, L2, target_edge=4.0)
    X = r["outer"]
    c = L1.mean(0)
    u, s, vt = np.linalg.svd(L1 - c)
    sag = float(np.abs((X - c) @ vt[2]).max())
    per = float(np.linalg.norm(np.diff(np.vstack([L1, L1[:1]]), axis=0), axis=1).sum())
    info = dict(r["info"])
    info.update({"loop_vertices": len(L1), "loop_perimeter_mm": round(per, 1), "max_sag_from_plane_mm": round(sag, 1)})
    return r, info


def add_closure(page_key, S, spec, out_dir, extra_replace=None, extra_note=""):
    man, blob, _ = skin_of(page_key)
    L1, L2 = loop_positions(S, spec)
    r, info = make_closure(L1, L2)
    entry = {"name": "Perineal surface closure (skin)", "id": CLOSURE_ID, "side": "m", "sys": "skin", "rec": {"procedural_badge": closure_badge(info, extra_note)}}
    d, stem = P.PAGES[page_key]
    P.save_page(out_dir, stem, man, blob, replace=extra_replace or {}, add=[(entry, r["v"], r["f"])])
    return info


def weld_skin(page_key, raw_key, only_bad_gt=None, log=print):
    """shared-border weld of the skin patches (cross-side pairs too) with the Q199 / Q201 machinery; returns (replace dict, report, by)"""
    from scripts.zanatomy import q199_elbow as E
    man, blob, S = skin_of(page_key)
    _, _, R = skin_of(raw_key)
    raw = {i: R[i]["v"] for i in S if i in R}
    by = {i: {"v": S[i]["v"].copy(), "f": S[i]["f"], "cat": "skin"} for i in S if i in raw}
    ids = sorted(by)
    before = E.skin_seam_rows(by, raw, None, ids)
    movable = set(ids) if only_bad_gt is None else {x for r in before if r["step_mm_max"] > only_bad_gt for x in (r["a"], r["b"])}
    log(f"  {len(before)} adjacent patch pairs; steps > 3 mm: {sum(r['step_mm_max'] > 3 for r in before)}; movable patches {len(movable)}")
    v0 = {i: by[i]["v"].copy() for i in ids}
    E.weld_borders(by, raw, ids, movable, rounds=8, cap=14.0)
    after = E.skin_seam_rows(by, raw, None, ids)
    replace, moved = {}, {}
    for i in ids:
        mv = np.linalg.norm(by[i]["v"] - v0[i], axis=1)
        if mv.max() < 0.05:
            continue
        sb = max([r["step_mm_max"] for r in before if i in (r["a"], r["b"])] or [0])
        sa = max([r["step_mm_max"] for r in after if i in (r["a"], r["b"])] or [0])
        moved[i] = {"max_displacement_mm": round(float(mv.max()), 2), "mean_displacement_mm": round(float(mv.mean()), 2), "seam_step_max_before_mm": sb, "seam_step_max_after_mm": sa}
        rec = dict(S[i]["m"].get("rec") or {})
        rec["procedural_badge"] = ((rec.get("procedural_badge") or "") + f" Q202: rule-based seam weld of this skin patch to its neighbours (largest shared-border step {sb} -> {sa} mm; mean move {mv.mean():.1f} mm, max {mv.max():.1f} mm); not a measurement.").strip()
        replace[i] = (by[i]["v"], S[i]["f"], rec)
    summ = lambda rows: {"pairs": len(rows), "steps_gt_3mm": int(sum(r["step_mm_max"] > 3 for r in rows)), "max_step_mm": round(max([r["step_mm_max"] for r in rows] or [0]), 2)}
    rep = {"before": summ(before), "after": summ(after), "patches_moved": len(moved), "max_displacement_mm": max([m["max_displacement_mm"] for m in moved.values()] or [0]), "moved": moved,
           "worst_after": sorted([(r["a"], r["b"], r["step_mm_max"]) for r in after], key=lambda t: -t[2])[:6]}
    log(f"  seams {rep['before']} -> {rep['after']}; {len(moved)} patches moved, max {rep['max_displacement_mm']} mm")
    return replace, rep, by, (man, blob, S)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("page", choices=["base_f", "fit_f", "fit_m"])
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    spec = json.loads(LOOP.read_text())
    name = {"base_f": "viewer_base_female", "fit_f": "viewer_zan_female", "fit_m": "viewer_zan_vhm"}[a.page]
    out = Path(a.out or REPO / "build" / "q202" / name)
    rep_path = REPO / "data" / "derived" / f"Q202_{a.page}_report.json"
    if a.page == "base_f":
        man, blob, S = skin_of("base_f")
        info = add_closure("base_f", S, spec, out)
        rep = {"closure": info}
    elif a.page == "fit_m":
        replace, rep, by, (man, blob, S) = weld_skin("fit_m", "base_m", only_bad_gt=1.0)
        P.save_page(out, P.PAGES["fit_m"][1], man, blob, replace=replace)
    else:
        replace, rep, by, (man, blob, S) = weld_skin("fit_f", "base_f")
        S2 = {i: {"v": by[i]["v"] if i in by else S[i]["v"], "f": S[i]["f"]} for i in S}
        info = add_closure("fit_f", S2, spec, out, extra_replace=replace, extra_note=" The loop is the Q202-welded rim of the fitted neighbouring patches.")
        rep["closure"] = info
    rep_path.write_text(json.dumps(rep, indent=1, default=float))
    print(json.dumps({k: v for k, v in rep.items() if k != "moved"}, default=float)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
