"""Q199 build hook (--q199-refine): the elbow of the female Z-Anatomy viewer, both arms (scripts/zanatomy/q199_elbow.py).  Everything not listed in the returned report stays bit-identical.

Runs AFTER the Q194 hook and the gap closure, BEFORE the decimation, in a CHILD process (the build process holds ~10 GB at this point; the child needs only the pending meshes: they go
through an npz, the results come back the same way, like q194_refine).  The shipped (pre-decimated) meshes the Q194 neighbour separation produced travel with them (`pv<k>`, `pf<k>`):
the field is a function of position only, so it moves them exactly as it moves the full-resolution mesh.
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


def refine_core(by: dict, raw: dict, log=print, skin=None, her=None, decimate_fn=None) -> dict:
    """by: {id: {"v","f","cat","fit_note"?,"pre_decimated"?}} (mutated), raw: {id: Z source vertices}"""
    from scipy.spatial import cKDTree
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.zanatomy import q199_elbow as E
    skin = skin if skin is not None else load_skin("vhf")
    skin_tree = cKDTree(np.asarray(skin.vertices, float))
    her = her if her is not None else load_her_meshes()
    rep = {"rule": "scripts/zanatomy/q199_elbow.py", "chain": {}, "structures": {}, "bones": {}}
    ch_l, rl = E.fit_left(by, raw, log=log)
    rep["chain"]["left"] = rl
    ch_r, rr = E.fit_right(by, raw, her, log=log)
    rep["chain"]["right"] = rr
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    for side, ch in (("l", ch_l), ("r", ch_r)):
        r = E.refine_side(side, by, raw, ch, skin, skin_tree, regions=regions, log=log)
        rep["bones"].update(r["bones"])
        _bone_notes(by, side, rep["chain"]["left" if side == "l" else "right"], r["bones"])
        rep["structures"].update(r["structures"])
        rep.setdefault("continuity", {})[side] = r["continuity"]
        rep.setdefault("skin_seams", {})[side] = E.weld_elbow_skin(side, by, raw, log=log)
        if decimate_fn is not None:
            rep.setdefault("separation", {})[side] = E.separate_elbow(side, by, raw, skin, skin_tree, decimate_fn, log=log)
            rep["moved_ids"] = sorted(set(rep.get("moved_ids", [])) | {k for k, m in rep["separation"][side]["moved"].items() if m["max_move_mm"] >= 0.3})
        rep["moved_ids"] = sorted(set(rep.get("moved_ids", [])) | set(rep["skin_seams"][side]["moved"]))
        log(f"  Q199 {side}: {len(r['structures'])} structures moved")
    rep["moved_ids"] = sorted(set(rep["moved_ids"]) | set(rep["structures"]) | {b for b, m in rep["bones"].items() if m["max_move_mm"] > 0.05})
    return rep


def _bone_notes(by, side, ch, mv):
    """card notes of the three elbow bones: what was fitted, with which reference, before -> after of the joint"""
    s = "_" + side
    jb, ja = ch["joint_before"], ch["joint_after"]
    jt = (f" Elbow joint (the Z-source contact patch of the humerus with the radius / ulna, nearest-surface gap median): {jb['nearest_surface_gap_mm_median']} -> {ja['nearest_surface_gap_mm_median']} mm "
          f"(Z source {ja['source_gap_mm_median']} mm); pair distances off the Z source by {jb['pair_distance_change_mm_mean']} -> {ja['pair_distance_change_mm_mean']} mm (mean).")
    p = ch["params"]
    if side == "l":
        sc = ch["shaft_centre_residual_mm"]
        hum = (f" Q199: this humerus lay in the CT frame, 16-20 mm from her humerus in her cryosection photographs (the frame of her skin, left forearm and hand). Fitted as ONE rigid motion + scale "
               f"about her CT humeral head (head moved {p['head_shift_mm']} mm, rotation {p['humerus_rot_deg']} deg, scale {p['humerus_scale']}) onto the humerus disc centres of her photographs "
               f"(centre residual {sc['before_mean']} -> {sc['after_mean']} mm mean, max {sc['after_max']} mm) and her elbow bone blobs." + jt)
        rad = f" Q199: forearm bone swung {p['radius_swing_deg']} deg about the wrist (the wrist and hand stay; pronation is Q192's); elbow end moved {p['elbow_end_move_mm']['radius']} mm so the elbow joint closes." + jt
        uln = f" Q199: forearm bone swung {p['ulna_swing_deg']} deg about the wrist (the wrist and hand stay; pronation is Q192's); elbow end moved {p['elbow_end_move_mm']['ulna']} mm so the elbow joint closes." + jt
    else:
        hum = " Q199: stays on her CT humerus label (the right arm is one CT-frame chain from the shoulder to the hand); the forearm bones were swung to it." + jt
        rad = f" Q199: forearm bone swung {p['radius_swing_deg']} deg about the wrist (it stays on her label: the label coverage of the radius is in the report); elbow end moved {p['elbow_end_move_mm']['radius']} mm." + jt
        uln = f" Q199: forearm bone swung {p['ulna_swing_deg']} deg about the wrist; elbow end moved {p['elbow_end_move_mm']['ulna']} mm (her ulna label ends at the mid-forearm, the proximal part is the Z shape)." + jt
    for n, t in (("humerus", hum), ("radius", rad), ("ulna", uln)):
        if mv.get(n + s, {}).get("max_move_mm", 0) > 0.05:
            by[n + s]["fit_note"] = (by[n + s].get("fit_note") or "") + t + f" Max move {mv[n + s]['max_move_mm']} mm, mean {mv[n + s]['mean_move_mm']} mm."


def refine_pending(pending: list[dict], raw: dict, budget_scale=1.0, category_scale=None, log=print) -> dict:
    """build hook: moves / annotates the pending meshes in place; returns the report"""
    import ctypes
    import gc
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except OSError:
        pass
    tmp = Path(tempfile.mkdtemp(prefix="q199_"))
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
    log(f"  Q199: running the elbow refinement in a child process ({tmp})")
    env = {**__import__("os").environ, "PYTHONPATH": str(REPO)}
    r = subprocess.run(cmd, cwd=str(REPO), env=env)
    if r.returncode != 0:                    # e.g. a pyembree segfault in the child: once more with the pure-numpy ray tester (slow, cannot crash)
        log(f"  Q199: child exited with {r.returncode}; repeating with --safe")
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
    print("q199 child: changed", len(changed))


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
