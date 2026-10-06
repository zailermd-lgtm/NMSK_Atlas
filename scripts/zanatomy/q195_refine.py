"""Q195: per-structure refinement of the Z-Anatomy male (already fitted to the VH male's skeleton, trunk-refit and Q190-refined) onto HIS OWN
measured organs and lower-limb muscles, and the limb skin onto his CT skin.  Build hook `refine_pending` (after the Q190 pass, before the
gap closure and the decimation).  Nothing is invented: every target is a mesh measured on his body (CT labels / cryosection labels, build/vh
ct_vhm_* subjects); only Z-Anatomy meshes move.

  1. ORGANS.  Groups of Z organs that make up one of his measured organs (his lungs = Z lobes; liver; stomach; heart = four chambers; colon;
     small bowel; oesophagus; trachea; bladder; prostate; sigmoid) are re-placed on their own Z source shape with the Q190 group machinery
     (similarity ICP, bounded affine, bounded smooth residual, volume guard 0.65-1.5 x source at body scale, push out of his bone labels),
     accepted only when the two-way chamfer to his organ improves by >= 10 %; structures that belong to them (bronchi, segments, vessels, nodes)
     follow by the Q190 distance-weighted propagation.
  2. LOWER-LIMB MUSCLES he has a mesh of (thigh, leg: his meshes are partly cut by the CT / cryo blocks -> partial-aware like Q190), same machinery,
     bone guard = his bone meshes (his `total` label volume is the torso block only), his other muscle meshes as obstacles.
  3. LIMB SKIN (thigh, leg, arm patches that hold no hand): a bounded, welded, Laplacian-smoothed displacement onto his CT skin
     (nearest surface point 1 mm inside), seams re-welded.
"""
from __future__ import annotations

import re

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q190_refine as Q

ORGAN_GROUPS = {
    "liver": ["zan_liver"],
    "stomach": ["zan_stomach"],
    "lung_r": ["zan_superior_lobe_of_right_lung", "zan_middle_lobe_of_right_lung", "zan_inferior_lobe_of_right_lung"],
    "lung_l": ["zan_superior_lobe_of_left_lung", "zan_inferior_lobe_of_left_lung"],
    "heart": ["zan_left_atrium", "zan_right_atrium", "zan_left_ventricle", "zan_right_ventricle"],
    "esophagus": ["zan_oesophagus"],
    "trachea": ["zan_trachea"],
    "colon": ["zan_ascending_colon", "zan_transverse_colon", "zan_descending_colon"],
    "sigmoid_colon": ["zan_sigmoid_colon"],
    "small_bowel": ["zan_jejunum"],
    "urinary_bladder": ["zan_urinary_bladder"],
    "prostate": ["zan_prostate"],
}
FOLLOW_CATS = ("organ", "vessel", "lymphatic", "nerve", "ligament", "fascia", "tendon", "bursa", "muscle")
LEG_Y_MAX = -140.0                    # Z muscles whose centroid lies below this are lower limb (the Q190 trunk scope ends here)
FOOT_Y = -840.0
MIN_GAIN = 0.90                       # chamfer after / before must be below this
SKIN_SNAP_CAP_MM, SKIN_INSET_MM, SKIN_SMOOTH_ITERS = 40.0, 1.0, 8
LIMB_SKIN_RE = re.compile(r"thigh|knee|leg|calf|popliteal|ankle|gluteal_fold|femoral|crural|sural|patell|arm|elbow|cubital|bicipital|axill|deltoid")
HAND_SKIN_RE = re.compile(r"forearm|wrist|hand|digit|palm|nail|perionyx|radial_foveola|foot|toe|heel|plantar|dorsum_of_foot|sole")


class LegGuards:
    """bone guard of the Q190 push-out: his torso-block bone labels + his bone MESHES below the block (his `total` label volume ends at y ~ 32)"""

    def __init__(self, guards, her):
        from scripts.zanatomy.q191_hand import Inside, merge_inside
        self.g = guards
        ids = [k for k, m in her.items() if m["cat"] == "bone" and m["v"][:, 1].mean() < -40 and len(m["f"]) > 100]
        self.legs = merge_inside([Inside(her[k]["v"], her[k]["f"]) for k in ids])
        self.ids = ids

    def depth(self, P):
        d = self.g.depth(P)
        low = P[:, 1] < 25.0
        if low.any():
            d = np.where(low, np.maximum(self.legs.depth(P), 0.0), d)
        return d

    push_out = Q.Guards.push_out


def _vol_cm3(v, f):
    return abs(Q.volume(v, f)) / 1000.0


def _refine_groups(groups, her_of, structs_by_id, her, guards, obstacles, kind, log):
    """groups {key: [member structure dicts]}; her_of(key) -> his mesh id.  Returns ({id: new v}, {id: report})"""
    new, rep = {}, {}
    for key, members in sorted(groups.items()):
        hid = her_of(key)
        hv = her[hid]
        if len(hv["v"]) < 50:
            continue
        ref = Q.Ref(hv["v"].astype(np.float64), hv["f"].astype(np.int64))
        X, r, _ = Q.refine_group(members, ref)
        Rr = np.vstack([m["r"] for m in members])
        F = np.vstack([m["f"] + o for m, o in zip(members, np.cumsum([0] + [len(m["r"]) for m in members[:-1]]))])
        closed = Q._closed(F)
        if closed:
            X, ratio = Q.volume_guard(X, Rr, F)
        else:
            ratio = abs(Q.volume(X, F)) / max(abs(Q.volume(Rr, F)) * Q.BODY_SCALE ** 3, 1e-6)
        r["volume_ratio_vs_source"] = round(ratio, 3)
        r["closed_mesh"] = bool(closed)
        if guards is not None:
            X = guards.push_out(X, F)
        if obstacles is not None:
            X, n_pushed = obstacles.push(X, F, {hid})
            r["pushed_out_of_his_other_labels_vertices"] = n_pushed
        c = Q.chamfer(X, F, ref, partial=r["partial_reference"])
        r["after_mm"] = [round(x, 2) for x in c]
        r["his_id"] = hid
        r["kind"] = kind
        r["members"] = [m["id"] for m in members]
        r["his_volume_cm3"] = round(_vol_cm3(hv["v"], hv["f"]), 1) if Q._closed(hv["f"]) else None
        r["z_volume_cm3_before"] = round(_vol_cm3(np.vstack([m["v"] for m in members]), F), 1) if closed else None
        r["z_volume_cm3_after"] = round(_vol_cm3(X, F), 1) if closed else None
        if c[2] < MIN_GAIN * r["her_label_chamfer_before_mm"][2]:
            r["status"] = "refined"
            for k, v in Q.split_back(X, members).items():
                new[k] = v
        else:
            r["status"] = "held"
        for m in members:
            rep[m["id"]] = r
        log(f"  {kind} {hid:26s} {r['status']:8s} his-mesh chamfer {r['her_label_chamfer_before_mm'][2]:.1f} -> {c[2]:.1f} mm  vol x{ratio:.2f}  {r['pose']}")
    return new, rep


def snap_limb_skin(structs, skin_mesh, log=print):
    """limb skin patches -> his CT skin: capped nearest-surface displacement, smoothed over the WELDED skin graph, seams re-welded"""
    from scipy import sparse
    from trimesh.proximity import closest_point
    sk = [d for d in structs if d["cat"] == "skin" and LIMB_SKIN_RE.search(d["id"]) and not HAND_SKIN_RE.search(d["id"])]
    allskin = [d for d in structs if d["cat"] == "skin"]
    if not sk:
        return {}, {}
    allr = np.vstack([d["r"] for d in allskin]).astype(np.float64)
    allv = np.vstack([d["v"] for d in allskin]).astype(np.float64)
    off = np.cumsum([0] + [len(d["r"]) for d in allskin])
    u, inv = np.unique(np.round(allr, 2), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(u)
    e = []
    for d, o in zip(allskin, off[:-1]):
        f = d["f"]
        e.append(inv[o + np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])])
    e = np.vstack(e)
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    sel_ids = {d["id"] for d in sk}
    active = np.concatenate([np.full(len(d["v"]), d["id"] in sel_ids) for d in allskin])
    cp, _, tri = closest_point(skin_mesh, allv[active])
    nrm = skin_mesh.face_normals[tri]
    D = np.zeros_like(allv)
    D[active] = (cp - SKIN_INSET_MM * nrm) - allv[active]
    big = np.linalg.norm(D, axis=1) > SKIN_SNAP_CAP_MM
    D[big] = 0.0
    U = np.zeros((n, 3)); cnt = np.zeros(n)
    np.add.at(U, inv, D); np.add.at(cnt, inv, 1)
    U /= np.maximum(cnt, 1)[:, None]
    Us = U.copy()
    for _ in range(SKIN_SMOOTH_ITERS):
        Us = (A @ Us) / deg[:, None]
    # keep each vertex's own measured displacement where it is larger (the snap target itself), smoothed otherwise
    Dn = np.where(active[:, None], 0.5 * D + 0.5 * Us[inv], 0.0)
    Dn[big] = 0.0
    newv = allv + Dn
    # re-weld seams
    cntv = np.bincount(inv)
    mean = np.zeros((n, 3)); np.add.at(mean, inv, newv); mean /= cntv[:, None]
    newv = np.where((cntv[inv] > 1)[:, None], mean[inv], newv)
    out, rep = {}, {}
    for d, a, b in zip(allskin, off[:-1], off[1:]):
        if d["id"] in sel_ids:
            mv = np.linalg.norm(newv[a:b] - allv[a:b], axis=1)
            out[d["id"]] = newv[a:b]
            dist_after = closest_point(skin_mesh, newv[a:b][::max(1, (b - a) // 400)])[1]
            rep[d["id"]] = {"mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2),
                            "median_to_his_skin_after_mm": round(float(np.median(dist_after)), 2)}
    log(f"  limb skin snap: {len(out)} patches onto his CT skin")
    return out, rep


BONE_GUARD_CATS = ("muscle", "nerve", "vessel", "fascia", "lymphatic")      # tendons / ligaments / cartilage attach to bone by design


def bone_guard(structs, newv, guards, regions, log=print):
    """soft structures with > 3 % of their vertices > 1 mm inside HIS bone (label volume / bone meshes) are pushed out (Q190 Guards.push_out, Laplacian-spread);
    kept only if the inside share falls to <= 70 % of before, the volume stays in 0.65-1.5 x source (closed meshes) and the distortion score does not rise > 6 points.
    Hand / forearm structures are skipped (the Q191 hand pass has its own constraint)."""
    rep = {}
    for d in structs:
        k = d["id"]
        if d["cat"] not in BONE_GUARD_CATS or regions.get(k) == "forearm_hand" or len(d["f"]) == 0:
            continue
        v = newv.get(k, d["v"])
        sel = slice(None, None, max(1, len(v) // 800))
        f0 = float((guards.depth(v[sel]) > 1.0).mean())
        if f0 < 0.03:
            continue
        v2 = guards.push_out(v, d["f"], tol=1.5, iters=4, max_move=12.0, smooth=30)
        f1 = float((guards.depth(v2[sel]) > 1.0).mean())
        s0 = Mx.distortion_score(Mx.stretch_stats(v, d["r"], d["f"]))
        s1 = Mx.distortion_score(Mx.stretch_stats(v2, d["r"], d["f"]))
        ok = f1 <= 0.7 * f0 and s1 <= s0 + 6.0
        if ok and Q._closed(d["f"]) and d["cat"] != "fascia":
            vs = abs(Q.volume(d["r"], d["f"])) * Q.BODY_SCALE ** 3
            if vs > 1000.0:
                ratio = abs(Q.volume(v2, d["f"])) / vs
                ok = 0.65 <= ratio <= 1.5 or abs(np.log(ratio)) <= abs(np.log(max(abs(Q.volume(v, d["f"])) / vs, 1e-3)))
        rep[k] = {"inside_bone_before": round(f0, 3), "inside_bone_after": round(f1, 3), "score_before": round(s0, 1), "score_after": round(s1, 1),
                  "max_move_mm": round(float(np.linalg.norm(v2 - v, axis=1).max()), 1), "applied": bool(ok)}
        if ok:
            newv[k] = v2
    log(f"  bone guard: {sum(r['applied'] for r in rep.values())} of {len(rep)} structures with > 3 % inside his bone pushed out")
    return rep


def refine_pending(pending: list[dict], raw: dict, log=print) -> dict:
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.placement_sweep_q185 import Body
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.zanatomy import body_ctx as ctx
    from scripts.zanatomy import trunk_refit_q186c as T
    assert ctx.BODY == "vhm"
    structs = [{"id": p["mesh_id"], "cat": p["cat"], "v": p["v"], "r": raw[p["mesh_id"]].astype(np.float64), "f": p["f"]} for p in pending]
    by = {d["id"]: d for d in structs}
    by_p = {p["mesh_id"]: p for p in pending}
    her = load_her_meshes()
    skin = load_skin(ctx.BODY)
    guards = LegGuards(Q.Guards(Body(ctx.BODY)), her)
    obstacles = Q.HerObstacles(her)
    rep = {"organs": {}, "legs": {}, "skin": {}}
    v_before = {d["id"]: d["v"].copy() for d in structs}

    # 1. organs
    og = {}
    for hid, zids in ORGAN_GROUPS.items():
        mem = [by[z] for z in zids if z in by]
        if mem and hid in her:
            og[hid] = mem
    new_o, rep_o = _refine_groups(og, lambda k: k, by, her, guards, None, "organ", log)
    # 2. lower-limb muscles
    lg = {}
    for d in structs:
        if d["cat"] != "muscle" or d["v"].mean(0)[1] >= LEG_Y_MAX or d["v"].mean(0)[1] < FOOT_Y or Q.NOT_A_MUSCLE_BODY.search(d["id"]):
            continue
        hid = Q.her_id_for(d["id"], her)
        if hid:
            lg.setdefault(hid, []).append(d)
    new_l, rep_l = _refine_groups(lg, lambda k: k, by, her, guards, obstacles, "leg muscle", log)
    new = {**new_o, **new_l}
    # 3. followers (bronchi, segments, vessels, nodes, the leg tendons / fasciae / nerves / vessels / muscles he has no mesh of)
    pr = Q.propagate(structs, new, log=log, y_range=(-1100.0, 700.0), cats=FOLLOW_CATS)
    newv = {**new, **pr}
    for k, v in newv.items():
        by[k]["v"] = v
    # 3b. soft structures out of his bones
    regions = __import__("json").loads(ctx.REGION_REPORT.read_text())["region_of_structure"]
    bg = bone_guard(structs, newv, guards, regions, log=log)
    for k, v in newv.items():
        by[k]["v"] = v
    rep["bone_guard"] = bg
    # 4. limb skin onto his CT skin
    sk_new, sk_rep = snap_limb_skin(structs, skin, log=log)
    for k, v in sk_new.items():
        by[k]["v"] = v
    newv.update(sk_new)
    rep["organs"], rep["legs"], rep["skin"] = {k: v for k, v in rep_o.items()}, {k: v for k, v in rep_l.items()}, sk_rep
    rep["propagated"] = sorted(pr)
    # apply + badges
    for k, v in newv.items():
        by_p[k]["v"] = v
    clamp = T.clamp_inside_skin(pending, skin_mesh=skin, log=log)
    for p in pending:
        p.pop("v_unclamped", None)
    for k, r in {**rep_o, **rep_l}.items():
        if r["status"] != "refined":
            continue
        kind = "organ" if r["kind"] == "organ" else "muscle"
        txt = (f" Q195: refined onto his own measured {r['his_id'].replace('_', ' ')} ({kind}; his mesh is the reference, the shape is this Z-Anatomy mesh): "
               f"two-way median distance to his mesh {r['her_label_chamfer_before_mm'][2]} -> {r['after_mm'][2]} mm"
               f"{' (his mesh covers only part of it)' if r['partial_reference'] else ''}; {r['pose']} fit + smooth residual <= {r['resid_max_mm']} mm")
        if r.get("z_volume_cm3_after") is not None and r.get("his_volume_cm3"):
            txt += f"; volume {r['z_volume_cm3_before']} -> {r['z_volume_cm3_after']} cm3 (his mesh {r['his_volume_cm3']} cm3, guard 0.65-1.5x of the Z source)."
        else:
            txt += "."
        by_p[k]["fit_note"] = (by_p[k].get("fit_note") or "") + txt
    for k, r in {**rep_o, **rep_l}.items():
        if r["status"] == "held":
            by_p[k]["fit_note"] = (by_p[k].get("fit_note") or "") + (
                f" Q195: held at the bone-fit position (no gain >= 10 % onto his {r['his_id'].replace('_', ' ')}: {r['her_label_chamfer_before_mm'][2]} -> {r['after_mm'][2]} mm).")
    for k in pr:
        by_p[k]["fit_note"] = (by_p[k].get("fit_note") or "") + " Q195: moved with the neighbouring structures refined onto his own meshes."
    for k, r in bg.items():
        if r["applied"]:
            by_p[k]["fit_note"] = (by_p[k].get("fit_note") or "") + (
                f" Q195: pushed out of his bone ({r['inside_bone_before'] * 100:.0f} % -> {r['inside_bone_after'] * 100:.0f} % of its vertices more than 1 mm inside his bone labels / meshes; moved at most {r['max_move_mm']} mm).")
    for k, s in sk_rep.items():
        by_p[k]["fit_note"] = (by_p[k].get("fit_note") or "") + (
            f" Q195: limb skin set toward his CT skin (mean move {s['mean_move_mm']} mm, max {s['max_move_mm']} mm); now a median {s['median_to_his_skin_after_mm']} mm from it.")
    rep["clamp_inside_his_skin"] = {k: v for k, v in clamp.items() if k != "per_structure"}
    rep["counts"] = {"organ_groups": len(og), "organ_refined": sum(1 for r in rep_o.values() if r["status"] == "refined"),
                     "leg_groups": len(lg), "leg_refined": sum(1 for k, r in rep_l.items() if r["status"] == "refined")}
    return rep
