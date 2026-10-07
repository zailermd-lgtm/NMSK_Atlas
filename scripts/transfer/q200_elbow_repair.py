#!/usr/bin/env python3
"""Q200: continuity at the elbow (and the CT-block seams of the arm) in the two OWN reconstructed models.

    python3 scripts/transfer/q200_elbow_repair.py --body vhm|vhf [--out build/viewer_m_hr_q200] [--report FILE]

Stage 1 (muscles / tendons / fascia): every flat cap (axis-aligned cut face at the end of a structure = data-block seam) of
an arm structure is continued by its fitted Z-Anatomy counterpart (Q168/Q195 per-bone transform, warped onto the cap outline,
far end pulled to its bone anchor). The measured entries are never edited; the continuation is a NEW entry (`<id>_zfill`,
subject xfer_zan2<body>_elbow_q200, class 'Filled from Z-Anatomy')."""
from __future__ import annotations
import argparse
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q200_geom import sample_surface, align_rigid_local  # noqa: E402
from scripts.transfer.q200_continue import find_caps, continue_cap2 as continue_cap, AX, section_area_inside  # noqa: E402
from scripts.zanatomy.q198_soft import expected_bones  # noqa: E402

BODY = {
    "vhm": dict(src=REPO / "build/viewer_m_hr_q193", out=REPO / "build/viewer_m_hr_q200", rep=REPO / "data/derived/Q195_zan_to_vhm.json",
                subject="xfer_zan2vhm_elbow_q200", he="his", sex="m"),
    "vhf": dict(src=REPO / "build/viewer_f_hr_q193", out=REPO / "build/viewer_f_hr_q200", rep=REPO / "data/derived/Q168_zan_to_vhf.json",
                subject="xfer_zan2vhf_elbow_q200", he="her", sex="f"),
}
TRICEPS = ["zan_long_head_of_triceps_brachii", "zan_lateral_head_of_triceps_brachii", "zan_medial_head_of_triceps_brachii"]
# structures of the arm that may carry seam caps (ids without side suffix)
ARM_STEMS = ["biceps_brachii", "brachialis", "triceps_brachii", "coracobrachialis", "brachioradialis", "anconeus", "pronator_teres",
             "supinator", "extensor_carpi_radialis_longus", "extensor_carpi_radialis_brevis", "extensor_carpi_ulnaris",
             "extensor_digitorum", "extensor_digiti_minimi", "extensor_pollicis_longus", "extensor_pollicis_brevis", "extensor_indicis",
             "abductor_pollicis_longus", "flexor_carpi_radialis", "flexor_carpi_ulnaris", "flexor_digitorum_superficialis",
             "flexor_digitorum_profundus", "flexor_pollicis_longus", "pronator_quadratus", "palmaris_longus"]
SIDE = {"l": "left", "r": "right"}


def z_ids(own_id):
    m = re.match(r"^(.*)_(l|r)$", own_id)
    if not m:
        return [own_id]
    st, sd = m.groups()
    if st == "triceps_brachii":
        return [f"{h}_{sd}" for h in TRICEPS]
    return [own_id]


def load_z(body, ids, cache):
    if cache.exists():
        return pickle.load(open(cache, "rb"))
    from scripts.transfer.zan_to_vhf_whole_body import collect_zan
    want = set()
    for i in ids:
        want.update(z_ids(i))
    items = {it["mesh_id"]: it for it in collect_zan(want, contralateral=False)}
    pickle.dump(items, open(cache, "wb"))
    return items


def anchors_of(rec):
    out = []
    for k in ("origin_point_mm", "insertion_point_mm"):
        p = rec.get(k)
        if p and len(p) == 3:
            out.append(np.asarray(p, float))
    return out


HAND = ["carpals", "metacarpal", "phalanges_hand"]
# stem -> (proximal-end bones, distal-end bones); "hand" = every hand bone of the side
ATTACH = {
    "biceps_brachii": (["scapula"], ["radius", "ulna"]), "brachialis": (["humerus"], ["ulna"]),
    "triceps_brachii": (["scapula", "humerus"], ["ulna"]), "coracobrachialis": (["scapula"], ["humerus"]),
    "brachioradialis": (["humerus"], ["radius"]), "anconeus": (["humerus"], ["ulna"]),
    "pronator_teres": (["humerus", "ulna"], ["radius"]), "supinator": (["humerus", "ulna"], ["radius"]),
    "extensor_carpi_radialis_longus": (["humerus"], ["hand"]), "extensor_carpi_radialis_brevis": (["humerus"], ["hand"]),
    "extensor_carpi_ulnaris": (["humerus", "ulna"], ["hand"]), "extensor_digitorum": (["humerus"], ["hand"]),
    "extensor_digiti_minimi": (["humerus"], ["hand"]), "flexor_carpi_radialis": (["humerus"], ["hand"]),
    "flexor_carpi_ulnaris": (["humerus", "ulna"], ["hand"]), "flexor_digitorum_superficialis": (["humerus", "ulna", "radius"], ["hand"]),
    "palmaris_longus": (["humerus"], ["hand"]), "flexor_digitorum_profundus": (["ulna", "radius"], ["hand"]),
    "flexor_pollicis_longus": (["radius", "ulna"], ["hand"]), "extensor_pollicis_longus": (["ulna", "radius"], ["hand"]),
    "extensor_pollicis_brevis": (["radius", "ulna"], ["hand"]), "extensor_indicis": (["ulna"], ["hand"]),
    "abductor_pollicis_longus": (["radius", "ulna"], ["hand"]), "pronator_quadratus": (["ulna"], ["radius"]),
}
SEAM_MATCH_MM = 6.0
FIT_ERR_MAX_MM = 25.0
SEAM_MIN_RATIO = 0.45     # cap area / area of M projected on the cap plane: below this the flat face is a facet, not the end of the structure


def seam_planes(B, min_struct=3, tol=1.0):
    """axis-aligned planes at which >= 3 structures of the body end in a flat cap = data-block seams: [(axis, pos, n_structures)]"""
    allc = []
    for it in B.items:
        e = it["e"]
        if e["id"] == "skin" or e["cat"] == "organ":
            continue
        v, f = B.mesh(it)
        for c in find_caps(v, f, minarea=40):
            allc.append((c["axis"], c["pos"], e["id"]))
    out = []
    for ax in "xyz":
        lst = sorted([a for a in allc if a[0] == ax], key=lambda x: x[1])
        if not lst:
            continue
        cl = [[lst[0]]]
        for a in lst[1:]:
            (cl[-1].append(a) if a[1] - cl[-1][-1][1] <= tol else cl.append([a]))
        for c in cl:
            ids = {x[2] for x in c}
            if len(ids) >= min_struct:
                out.append((ax, float(np.mean([x[1] for x in c])), len(ids)))
    return out


def bone_ids(own, names, side):
    out = []
    for n in names:
        if n == "hand":
            out += [i for i in own if own[i]["e"]["cat"] == "bone" and any(i.startswith(h) for h in HAND) and i.endswith("_" + side)]
        else:
            out += [i for i in own if own[i]["e"]["cat"] == "bone" and re.match(rf"^{n}_{side}(#\d+)?$", i)]
    return out


def pull_end(cv, axis, pos, sign, anchors, bone_tree, max_pull=35.0, reach_mm=1.5, touch_mm=2.5):
    """smooth, bounded translation of the far part of the continuation onto the bone it attaches to (ramp 0 at the seam plane).
    The vertex of the far half that comes closest to the expected bones is the attachment; if it is farther than touch_mm it is
    carried to 1.5 mm from the bone surface point nearest to it (or to the rec anchor when that lies within 20 mm of the bones)."""
    k = AX[axis]
    s = sign * (cv[:, k] - pos)
    smax = float(s.max())
    if bone_tree is None:
        return cv, dict(pulled=False, note="no expected bone")
    tree, pts = bone_tree
    far = np.where(s >= 0.4 * smax)[0]
    d, jj = tree.query(cv[far])
    m = int(np.argmin(d)); jv = far[m]
    d0 = float(d[m]); target = pts[jj[m]]
    for a in anchors:
        da, ja = tree.query(a)
        if da <= 20.0 and np.linalg.norm(pts[ja] - cv[jv]) < d0 + 25.0:
            target = pts[ja]; break
    info = dict(closest_to_bone_mm=round(d0, 1))
    if d0 <= touch_mm:
        info.update(pulled=False, note="attached (closest vertex within %.1f mm of the bone)" % touch_mm)
        return cv, info
    u = target - cv[jv]
    n = float(np.linalg.norm(u))
    info["pull_mm"] = round(n, 1)
    if n > max_pull:
        info.update(pulled=False, note=f"closest vertex {n:.0f} mm from the bone > {max_pull:g} mm bound")
        return cv, info
    u = u * max(0.0, 1 - reach_mm / max(n, 1e-6))
    t = np.clip((s - 0.25 * smax) / max(0.75 * smax, 1e-6), 0, 1)
    w = t * t * (3 - 2 * t)
    info["pulled"] = True
    return cv + w[:, None] * u, info


def constrain(cv, axis, pos, sign, skin_mesh, bone_meshes, ramp_mm=8.0):
    """continuation inside the skin and out of the bones (Q147 rules), faded to 0 at the seam plane so the weld stays exact."""
    from scripts.transfer.limb_per_bone_transfer import clip_to_skin_mesh, push_off_bones
    k = AX[axis]
    s = np.maximum(sign * (cv[:, k] - pos), 0)
    w = np.clip(s / ramp_mm, 0, 1)[:, None]
    v1, n_skin = clip_to_skin_mesh(cv.copy(), skin_mesh)
    v2, n_bone = push_off_bones(v1, bone_meshes)
    return cv + w * (v2 - cv), dict(skin_clipped=int(n_skin), bone_pushed=int(n_bone))


def run(body, only=None, log=print):
    import trimesh
    cfg = BODY[body]
    B = Bundle(cfg["src"])
    own = {}
    for it in B.items:
        e = it["e"]
        if e["id"] not in own:
            v, f = B.mesh(it)
            own[e["id"]] = dict(e=e, v=v, f=f)
    sk = own["skin"]
    skin_mesh = trimesh.Trimesh(sk["v"], sk["f"], process=False)
    scratch = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
    targets = [i for i in own if re.match(r"^(" + "|".join(ARM_STEMS) + r")_(l|r)$", i) and own[i]["e"]["cat"] in ("muscle", "tendon")]
    if only:
        targets = [t for t in targets if t in only]
    zit = load_z(body, targets, scratch / f"zarm_{body}.pkl")
    from scripts.transfer import zan_to_vhf_whole_body as Q
    xf = Q.load_zan_to_vhf(report_path=cfg["rep"])
    bone_cache = {}

    def bone_pts(ids):
        key = tuple(ids)
        if key not in bone_cache:
            pts = np.vstack([sample_surface(own[i]["v"], own[i]["f"], 5000, 11) for i in ids])
            bone_cache[key] = (cKDTree(pts), pts)
        return bone_cache[key]

    bone_meshes_cache = {}

    def bone_meshes(side):
        if side not in bone_meshes_cache:
            ids = bone_ids(own, ["humerus", "radius", "ulna", "scapula", "clavicle", "hand"], side)
            bone_meshes_cache[side] = [trimesh.Trimesh(own[i]["v"], own[i]["f"], process=False) for i in ids]
        return bone_meshes_cache[side]

    seams = seam_planes(B)
    rows, adds = [], {}
    for tid in targets:
        o = own[tid]
        caps = find_caps(o["v"], o["f"])
        if not caps:
            continue
        zs = [zit.get(z) for z in z_ids(tid)]
        zs = [z for z in zs if z is not None]
        if not zs:
            rows.append(dict(id=tid, status="held: no Z-Anatomy counterpart mesh", caps=len(caps)))
            continue
        zv, zf, off = [], [], 0
        for z in zs:
            zv.append(xf(z["mesh_id"], "muscle", z["v"])); zf.append(z["f"] + off); off += len(z["v"])
        ZV, ZF = np.vstack(zv), np.vstack(zf)
        side = tid[-1]; stem = tid[:-2]
        prox_b, dist_b = ATTACH.get(stem, ([], []))
        anch = anchors_of(o["e"]["rec"])
        cen_y = o["v"][:, 1].mean()
        pieces = []
        for cap in caps:
            row = dict(id=tid, axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
            sm = sorted([x for x in seams if x[0] == cap["axis"] and abs(x[1] - cap["pos"]) <= SEAM_MATCH_MM], key=lambda x: abs(x[1] - cap["pos"]))
            row["seam_structures"] = sm[0][2] if sm else 0
            if not sm:
                row["status"] = "skipped: flat facet shared with fewer than 3 structures (not a data-block seam)"
                rows.append(row); continue
            ZVa, ainfo = align_rigid_local(ZV, ZF, o["v"], o["f"], AX[cap["axis"]], cap["pos"], cap["sign"])
            row["align"] = {k_: (round(v_, 1) if isinstance(v_, float) else v_) for k_, v_ in ainfo.items()}
            r = continue_cap(o["v"], cap, ZVa, ZF)
            if "v" not in r:
                row["status"] = "held: " + r["reason"]; rows.append(row); continue
            # which end is it: proximal (towards the shoulder) or distal
            tip_y = r["v"][np.argmax(cap["sign"] * (r["v"][:, AX[cap["axis"]]] - cap["pos"]))][1]
            toward_prox = tip_y > cen_y
            names = prox_b if toward_prox else dist_b
            ids = bone_ids(own, names, side)
            bt = bone_pts(ids) if ids else None
            cv, pinfo = pull_end(r["v"], cap["axis"], cap["pos"], cap["sign"], anch if toward_prox is not None else [], bt)
            cv, cinfo = constrain(cv, cap["axis"], cap["pos"], cap["sign"], skin_mesh, bone_meshes(side))
            kax = AX[cap["axis"]]
            near = (cap["sign"] * (ZVa[:, kax] - cap["pos"]) > -25.0) & (cap["sign"] * (ZVa[:, kax] - cap["pos"]) < 0)
            if near.sum() > 20:
                dd = cKDTree(sample_surface(o["v"], o["f"], 8000, 5)).query(ZVa[near])[0]
                row["fit_err_median_mm"] = round(float(np.median(dd)), 1); row["fit_err_max_mm"] = round(float(np.quantile(dd, 0.95)), 1)
            if row.get("fit_err_median_mm", 0) > FIT_ERR_MAX_MM:
                row["status"] = (f"held: the Z-Anatomy counterpart does not coincide with the measured structure near the seam "
                                 f"(median {row['fit_err_median_mm']} mm > {FIT_ERR_MAX_MM:g} mm)")
                rows.append(row); continue
            r["v"] = cv
            r["info"] = row
            row.update(status="continued", end="proximal" if toward_prox else "distal", beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1), shift_mm=round(r["sh"], 1),
                       z_to_cap_area=round(r["area_ratio"], 3), pull=pinfo, constraints=cinfo, nv=len(cv), nf=len(r["f"]))
            rows.append(row)
            pieces.append(r)
        if pieces:
            adds[tid] = pieces
    return B, own, adds, rows


def badge_text(cfg, tid, pieces, name):
    meds = [p["info"].get("fit_err_median_mm") for p in pieces if p["info"].get("fit_err_median_mm") is not None]
    maxs = [p["info"].get("fit_err_max_mm") for p in pieces if p["info"].get("fit_err_max_mm") is not None]
    ends = ", ".join(sorted({f"{p['info']['end']} end at the {p['info']['axis']}={p['info']['pos']} mm data-block seam" for p in pieces}))
    att = []
    for p in pieces:
        pl = p["info"].get("pull") or {}
        att.append(pl.get("note", "pulled %.1f mm onto the bone" % pl.get("pull_mm", 0)) if not pl.get("pulled") else "far end carried %.1f mm onto its bone" % pl["pull_mm"])
    return (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) continuation of the measured {name} beyond its flat cut ({ends}): the fitted Z-Anatomy "
            f"counterpart (Q168 per-bone transform onto {cfg['he']} own bones), clipped at the seam plane, warped onto the measured end face and closed there; "
            f"{'; '.join(att)}; held inside {cfg['he']} skin and out of {cfg['he']} bones. The measured structure is not edited. "
            f"Q200 validation median error {np.median(meds):.1f} mm, max {max(maxs):.1f} mm (Z fit vs the measured part within 25 mm of the seam).")


def assemble(body, B, own, adds):
    cfg = BODY[body]
    out = []
    for tid, pieces in adds.items():
        V, F, off = [], [], 0
        for r in pieces:
            V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
        V, F = np.vstack(V), np.vstack(F)
        e = own[tid]["e"]; rec = e["rec"]
        name = rec.get("name", tid)
        newrec = {k: rec[k] for k in ("latin", "folder", "region", "origin", "insertion") if k in rec}
        newrec.update(name=f"{name} (continuation beyond the data-block seam, filled from Z-Anatomy)",
                      source="Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge",
                      procedural_badge=badge_text(cfg, tid, pieces, name))
        B.add(f"{tid}_zfill", e["cat"], e["side"], cfg["subject"], newrec, V, F)
        out.append(f"{tid}_zfill")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["vhm", "vhf"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    t = time.time()
    B, own, adds, rows = run(a.body, only=a.only)
    for r in rows:
        print(r)
    if not a.only:
        assemble(a.body, B, own, adds)
        att = {BODY[a.body]["subject"]: ["Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): continuations of structures cut flat at CT data-block seams, "
               "fitted onto this body's own bones (Q200); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by "
               "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike)."]}
        n = B.write(Path(a.out) if a.out else Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/stage1_" + a.body), new_subject_attribution=att)
        print("bundle bytes", n)
    print("done", round(time.time() - t, 1))
