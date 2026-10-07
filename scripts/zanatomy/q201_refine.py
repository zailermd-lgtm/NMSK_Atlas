"""Q201 build hook (--q201-refine): the ELBOW, FOREARM and WRIST of both arms of the Z-Anatomy model fitted to the VISIBLE HUMAN MALE (his evidence: scripts/cryo/q201_arm_evidence.py,
chain in q201_chain.py; the soft-tissue machinery is the Q199 one, q199_elbow.refine_side, aimed at his meshes), plus the skin seams of the whole skin.

Runs AFTER the Q195 refinement + final volume guard, BEFORE the decimation, in a CHILD process (like q199_refine / q194_refine: the build process holds ~10 GB at this point).  Everything not
listed in the returned report stays bit-identical.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
TUBE_CLOSE = (25.0, 25.0, 35.0)     # vessel / nerve pairs: closure step cap, Gaussian sigma, distance cap from the field result (mm); muscles keep the Q199 12 / 15 / 10 mm
HAND_ZONE_MM = 110.0            # arm structures within this distance of the Z-source hand (metacarpal centroid) are movable by the gap closure
WRIST_ZONE_MM = 90.0            # arm structures with a Z-source vertex this close to the Z-source wrist are in scope (the forearm bones' distal ends move onto the carpals)


def make_scope(jc_by_side: dict, wc_by_side: dict, hc_by_side: dict | None = None):
    """the Q201 scope: ARM structures (Q168 region upper_limb / forearm_hand) that reach the elbow zone (ELBOW_ZONE + 40 mm of the Z-source joint) or the wrist zone, plus merged Z meshes (not
    trunk / head-neck) that hold an arm part there.  The shoulder girdle and the trunk muscles are NOT in scope (the humerus head does not move beyond the Q195 fit)."""
    from scripts.zanatomy import q199_elbow as E

    def scope(side, i, raw_i, region, jc, hum_tree, humerus_moved=True):
        wc = wc_by_side[side]
        d_e = np.linalg.norm(raw_i - jc_by_side[side], axis=1)
        d_w = np.linalg.norm(raw_i - wc, axis=1)
        d_h = np.linalg.norm(raw_i - hc_by_side[side], axis=1) if hc_by_side else np.full(len(raw_i), 1e9)
        near = bool((d_e < E.ELBOW_ZONE_MM + 40.0).any() or (d_w < WRIST_ZONE_MM).any() or (d_h < HAND_ZONE_MM).any())
        n_near = int((d_e < E.ELBOW_ZONE_MM + 40.0).sum() + (d_w < WRIST_ZONE_MM).sum() + (d_h < HAND_ZONE_MM).sum())
        merged = region not in ("trunk", "head_neck") and n_near >= 100
        return (region in E.ARM_REGIONS and near) or merged
    return scope


def zone_centres(by, raw, side, wc=None):
    """(elbow joint centre, hand centre) in the Z-source frame: the Z-source humerus - radius / ulna contact patch, the mean of the five Z metacarpals"""
    from scripts.zanatomy import q199_elbow as E
    s = "_" + side
    jsmp, jsel, _, _ = E.joint_pairs(raw, side, by)
    jc = E.at(raw["humerus" + s], jsmp["humerus"])[jsel].mean(0)
    hc = np.vstack([raw[k] for k in raw if k.startswith("zan_") and "_metacarpal_bone" in k and k.endswith(s)]).mean(0)
    return jc, hc


def weld_all_skin(by, raw, log=print, rounds=8, cap=14.0):
    """the skin patches tile ONE surface in the Z source but were fitted to his CT skin patch by patch (Q195): shared-border vertices (< 1.5 mm apart in the Z source) end up 3-26 mm apart.
    Both patches go to the common border (weld_borders, spread over the patch by the mesh smoother), every patch of both sides"""
    from scripts.zanatomy import q199_elbow as E
    rep = {}
    for side in ("l", "r"):
        s = "_" + side
        ids = [i for i, d in by.items() if d["cat"] == "skin" and i.endswith(s)]
        before = E.skin_seam_rows(by, raw, side, ids)
        v0 = {i: by[i]["v"].copy() for i in ids}
        E.weld_borders(by, raw, ids, set(ids), rounds=rounds, cap=cap)
        after = E.skin_seam_rows(by, raw, side, ids)
        moved = {}
        for i in ids:
            mv = np.linalg.norm(by[i]["v"] - v0[i], axis=1)
            if mv.max() < 0.05:
                continue
            sb = max([r["step_mm_max"] for r in before if i in (r["a"], r["b"])] or [0])
            sa = max([r["step_mm_max"] for r in after if i in (r["a"], r["b"])] or [0])
            moved[i] = {"max_correction_mm": round(float(mv.max()), 2), "mean_correction_mm": round(float(mv.mean()), 2), "seam_step_max_before_mm": sb, "seam_step_max_after_mm": sa}
            by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
                f" Q201: skin patch welded to its neighbours (largest shared-border step {sb} -> {sa} mm; mean move {mv.mean():.1f} mm, max {mv.max():.1f} mm).")
        summ = lambda rows: {"seams": len(rows), "steps_gt_3mm": int(sum(r["step_mm_max"] > 3 for r in rows)), "max_step_mm": round(max([r["step_mm_max"] for r in rows] or [0]), 2)}
        elbow = lambda rows: [r for r in rows if E.SKIN_ELBOW_RE.search(r["a"]) or E.SKIN_ELBOW_RE.search(r["b"])]
        rep[side] = {"moved": moved, "before": summ(before), "after": summ(after), "arm_forearm_elbow_before": summ(elbow(before)), "arm_forearm_elbow_after": summ(elbow(after)),
                     "seams_after_gt3mm": [r for r in after if r["step_mm_max"] > 3]}
        log(f"  Q201 skin seams {side}: {rep[side]['before']} -> {rep[side]['after']}")
    return rep


def fmt_m(m):
    keys = (("outside_her_skin_pct", "outside his skin %"), ("inside_z_bone_pct", "inside the displayed bones %"), ("stretch_area_outside_0.67_1.5_pct", "stretched triangles %"),
            ("folded_edges_pct", "folded edges %"), ("volume_ratio_vs_source", "volume vs source"))
    return ", ".join(f"{lb} {m[k]}" for k, lb in keys if m.get(k) is not None)


def note(side, i, cat, q, m1, mv, cont):
    how = {"not moved by the field": "its origin / insertion footprint brought back to the bone", "gap closure only": "closed up against the structures it touches in the Z source"}.get(q["name"])
    txt = (f" Q201: {'adjusted' if how else 'moved'} at the {'left' if side == 'l' else 'right'} elbow / forearm / wrist ("
           + (how if how else f"humerus - radius - ulna refitted to HIS bone labels and cryosection photographs as one chain, tissue carried by the bone-anchored field: {q['name']}")
           + f"; mean {mv.mean():.1f} mm, max {mv.max():.1f} mm). Before -> after: " + fmt_m(q["m0"]) + " -> " + fmt_m(m1) + ".")
    a0, a1 = q["att0"], q["att1"]
    if a0 and a1:
        txt += " Origin / insertion footprint to the bone (source / before / after, mm): " + "; ".join(f"{b.rsplit('_', 1)[0]} {a1[b]['source_mm']} / {a0[b]['now_mm']} / {a1[b]['now_mm']}" for b in a1 if b in a0) + "."
    if cont:
        txt += f" Gap to {cont['neighbours']} neighbour structure(s) it touches in the Z source: {cont['before_mm']} -> {cont['after_mm']} mm."
    return txt


def bone_notes(by, side, rc, mv):
    s = "_" + side
    a, b_ = rc["before"], rc["after"]
    sa = rc["stage_a"]["stats"]
    tail = (f" Against his labels (surface distance, median): label -> Z {a['label_surface_to_Z_mm_median']} -> {b_['label_surface_to_Z_mm_median']} mm, Z -> label {a['Z_to_label_mm_median']} -> {b_['Z_to_label_mm_median']} mm; "
            f"the Z bones of the elbow zone outside the bone mass of his photographs {a['union_Z_outside_solid_pct']} -> {b_['union_Z_outside_solid_pct']} % of the surface; the bone mass boundary to the Z bones "
            f"{a['union_boundary_to_Z_mm_median']} -> {b_['union_boundary_to_Z_mm_median']} mm (median); elbow joint (nearest-surface gap at the Z-source contact patch) {a['joint']['nearest_surface_gap_mm_median']} -> "
            f"{b_['joint']['nearest_surface_gap_mm_median']} mm (Z source {b_['joint']['source_gap_mm_median']}); wrist (radius / ulna against the carpals, Z-source contacts) off by "
            f"{a['wrist_gap_change_mm_mean_abs']} -> {b_['wrist_gap_change_mm_mean_abs']} mm.")
    for n in ("humerus", "radius", "ulna"):
        k = n + s
        if mv.get(k, {}).get("max_move_mm", 0) <= 0.05:
            continue
        p = rc["params"][n]
        if n == "humerus":
            what = (f" Q201: this humerus was rolled about its shaft in the Q195 fit (his head + shaft labels ask for {rc['humerus_roll_deg']['shaft_labels']} deg, the epicondyle flare in his photographs "
                    f"{rc['humerus_roll_deg']['elbow_flare']} deg, i.e. the two independent measurements agree). Refit to his labels + the photographed elbow bone mass: rotation {p['rot_deg']} deg, scale x{p['scale_vs_q195']}")
        else:
            what = (f" Q201: refit to his {n} label (shaft + wrist, CT) and to the photographed bone mass of the elbow, seated on his carpals: rotation {p['rot_deg']} deg (the Q168 fit of this bone sat in the wrong "
                    f"roll / position: the {n} was off his carpals), scale x{p['scale_vs_q195']}")
        what += f", elbow-end bend {p['bend_mm']} mm (shape difference between his bone and the Z bone)."
        by[k]["fit_note"] = (by[k].get("fit_note") or "") + what + tail + f" Max move {mv[k]['max_move_mm']} mm, mean {mv[k]['mean_move_mm']} mm."


def refine_core(by: dict, raw: dict, log=print, skin=None, his=None, decimate_fn=None, ev=None, regions=None, sides=("l", "r"), do_separate=True) -> dict:
    """by: {id: {"v","f","cat","fit_note"?,"pre_decimated"?}} (mutated), raw: {id: Z source vertices}.  body_ctx must be configured for the male"""
    from scipy.spatial import cKDTree
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.zanatomy import body_ctx
    from scripts.zanatomy import q199_elbow as E
    from scripts.zanatomy import q201_chain as C
    assert body_ctx.BODY == "vhm", "Q201 is the male hook: body_ctx.configure('vhm') first"
    skin = skin if skin is not None else load_skin("vhm")
    skin_tree = cKDTree(np.asarray(skin.vertices, float))
    his = his if his is not None else load_her_meshes()               # body_ctx-aware: HIS own meshes (the muscles with a mesh of his guard the field)
    if regions is None:
        regions = json.loads(body_ctx.REGION_REPORT.read_text())["region_of_structure"]
    ev = ev if ev is not None else C.load_evidence()
    rep = {"rule": "scripts/zanatomy/q201_chain.py + q199_elbow.py (his evidence)", "chain": {}, "structures": {}, "bones": {}, "moved_ids": []}
    chains, jcs, wcs, hcs = {}, {}, {}, {}
    for side in sides:
        ch, rc = C.fit_male(side, by, raw, ev, log=log)
        chains[side] = ch
        rep["chain"][side] = rc
        wcs[side] = np.asarray(rc["wrist_centre_raw"], float)
        jcs[side], hcs[side] = zone_centres(by, raw, side)
    from scripts.zanatomy import q201_field as FLD
    DF = FLD.DeltaField(FLD.load_xf(raw), chains)
    scope = make_scope(jcs, wcs, hcs)
    for side in sides:
        s = "_" + side
        r = E.refine_side(side, by, raw, chains[side], skin, skin_tree, regions=regions, log=log, her=his, label_sides=("l", "r"), scope=scope, extra_centres=[wcs[side], hcs[side]], allow_unchanged=True, note_fn=note, tube_close=TUBE_CLOSE, close_rounds=10,
                         field_fn=lambda i, v0: DF.delta(i, raw[i]))
        rep["bones"].update(r["bones"])
        bone_notes(by, side, rep["chain"][side], r["bones"])
        rep["structures"].update(r["structures"])
        rep.setdefault("continuity", {})[side] = r["continuity"]
        if decimate_fn is not None and do_separate:
            rep.setdefault("separation", {})[side] = E.separate_elbow(side, by, raw, skin, skin_tree, decimate_fn, log=log, radius=240.0)
            rep["moved_ids"] = sorted(set(rep["moved_ids"]) | {k for k, m in rep["separation"][side]["moved"].items() if m["max_move_mm"] >= 0.3})
        log(f"  Q201 {side}: {len(r['structures'])} structures moved")
    rep["skin_seams"] = weld_all_skin(by, raw, log=log)
    for side in rep["skin_seams"]:
        rep["moved_ids"] = sorted(set(rep["moved_ids"]) | set(rep["skin_seams"][side]["moved"]))
    rep["moved_ids"] = sorted(set(rep["moved_ids"]) | set(rep["structures"]) | {b for b, m in rep["bones"].items() if m["max_move_mm"] > 0.05})
    return rep


def refine_pending(pending: list[dict], raw: dict, budget_scale=1.0, category_scale=None, log=print) -> dict:
    """build hook: moves / annotates the pending meshes in place; returns the report"""
    import ctypes
    import gc
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="q201_"))
    ids = [p["mesh_id"] for p in pending]
    arrs = {"ids": np.array(json.dumps(ids)), "cats": np.array(json.dumps([p["cat"] for p in pending])),
            "notes": np.array(json.dumps({p["mesh_id"]: p.get("fit_note") or "" for p in pending}))}
    for k, p in enumerate(pending):
        arrs[f"v{k}"] = np.asarray(p["v"], np.float64)
        arrs[f"f{k}"] = np.asarray(p["f"], np.int32)
        arrs[f"r{k}"] = np.asarray(raw[p["mesh_id"]], np.float64)
        if p.get("pre_decimated") is not None:
            arrs[f"pv{k}"] = np.asarray(p["pre_decimated"][0], np.float64)
            arrs[f"pf{k}"] = np.asarray(p["pre_decimated"][1], np.int32)
    np.savez(tmp / "in.npz", **arrs)
    del arrs
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", str(tmp / "in.npz"), str(tmp / "out.npz"), "--budget-scale", str(budget_scale),
           "--category-scale", json.dumps(category_scale or {})]
    log(f"  Q201: running the elbow / forearm / wrist refinement in a child process ({tmp})")
    env = {**__import__("os").environ, "PYTHONPATH": str(REPO)}
    r = subprocess.run(cmd, cwd=str(REPO), env=env)
    if r.returncode != 0:                    # e.g. a pyembree segfault in the child: once more with the pure-numpy ray tester (slow, cannot crash)
        log(f"  Q201: child exited with {r.returncode}; repeating with --safe")
        subprocess.run(cmd + ["--safe"], check=True, cwd=str(REPO), env=env)
    z = np.load(tmp / "out.npz", allow_pickle=False)
    rep = json.loads(str(z["report"]))
    by = {p["mesh_id"]: p for p in pending}
    notes = json.loads(str(z["notes"]))
    for i in json.loads(str(z["changed"])):
        k = ids.index(i)
        if f"nv{k}" in z.files:
            by[i]["v"] = z[f"nv{k}"]
        if f"pv{k}" in z.files:
            by[i]["pre_decimated"] = (z[f"pv{k}"], z[f"pf{k}"].astype(np.int64))
        if i in notes:
            by[i]["fit_note"] = notes[i]
    for f_ in tmp.iterdir():
        f_.unlink()
    tmp.rmdir()
    return rep


def child(a):
    import faulthandler
    faulthandler.enable()
    from scripts.zanatomy import body_ctx
    body_ctx.configure("vhm")                  # BEFORE the refit modules are imported (they copy BODY_SCALE at import)
    z = np.load(a.inp, allow_pickle=False)
    ids, cats = json.loads(str(z["ids"])), json.loads(str(z["cats"]))
    notes0 = json.loads(str(z["notes"]))
    by = {i: {"v": z[f"v{k}"], "f": z[f"f{k}"].astype(np.int64), "cat": c, "fit_note": notes0.get(i, "")} for k, (i, c) in enumerate(zip(ids, cats))}
    for k, i in enumerate(ids):
        if f"pv{k}" in z.files:
            by[i]["pre_decimated"] = (z[f"pv{k}"], z[f"pf{k}"].astype(np.int64))
    raw = {i: z[f"r{k}"] for k, i in enumerate(ids)}
    v0 = {i: d["v"].copy() for i, d in by.items()}
    p0 = {i: d["pre_decimated"][0].copy() for i, d in by.items() if d.get("pre_decimated") is not None}
    from scripts.zanatomy import build_zan_atlas_viewer as B
    B.TARGET["body"] = "vhm"
    sc = json.loads(a.category_scale)

    def dec(v, f, i, c):                       # exactly what finish() ships (decimation + outward winding), so the separation works on the shipped mesh
        dv, df = B.decimate(v, f, i, c, sc.get(c, a.budget_scale), prepped=True)
        return dv, B.outward_if_closed(dv, df)
    rep = refine_core(by, raw, decimate_fn=dec)
    out = {"report": np.array(json.dumps(rep, default=float))}
    changed, notes = [], {}
    for k, i in enumerate(ids):
        d = by[i]
        moved = not np.array_equal(d["v"], v0[i])
        pre = d.get("pre_decimated")
        pmoved = pre is not None and (i not in p0 or not np.array_equal(pre[0], p0[i]))
        if moved or pmoved or d.get("fit_note") != notes0.get(i, ""):
            changed.append(i)
            if moved:
                out[f"nv{k}"] = np.asarray(d["v"], np.float64)
            if pmoved:
                out[f"pv{k}"] = np.asarray(pre[0], np.float64)
                out[f"pf{k}"] = np.asarray(pre[1], np.int32)
            notes[i] = d.get("fit_note") or ""
    out["changed"] = np.array(json.dumps(changed))
    out["notes"] = np.array(json.dumps(notes))
    np.savez(a.out, **out)
    print("q201 child: changed", len(changed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--child", nargs=2, metavar=("IN", "OUT"), required=True)
    ap.add_argument("--budget-scale", type=float, default=1.0)
    ap.add_argument("--category-scale", default="{}")
    ap.add_argument("--safe", action="store_true")
    args = ap.parse_args()
    if args.safe:
        from scripts.zanatomy import q194_separate as _S
        _S.Skel.SAFE = True
    args.inp, args.out = args.child
    child(args)
