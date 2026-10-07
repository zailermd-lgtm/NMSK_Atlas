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


Q192_FIT = REPO / "data/derived/Q192_left_hand_fit.json"
Q194_DIR = REPO / "build/viewer_zan_female_q194"


def load_q194_left():
    """left-arm structures of the Q194 Z-Anatomy-female build (READ-ONLY reference geometry: left forearm placed on her photographs, her atlas frame)"""
    import base64
    html = (Q194_DIR / "atlas_viewer_zan_female.html").read_text(encoding="utf-8")
    files = json.loads(re.search(r"BIN_FILES(?:__)?\s*=\s*(\[.*?\])\s*;?\s*$", html, re.M).group(1))
    blob = b"".join(base64.b64decode((Q194_DIR / f["path"]).read_text().strip()) for f in files)
    man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", html, re.M).group(1))
    out = {}
    for r in man["meshes"]:
        if r["side"] != "l" or r["sys"] not in ("muscle", "tendon", "fascia", "joint", "ligament", "vessel", "nerve"):
            continue
        vc, ic = r["vc"], r["ic"]
        q = np.frombuffer(blob, np.uint16, vc * 3, r["vo"]).reshape(-1, 3).astype(np.float64)
        f = np.frombuffer(blob, np.uint16, ic * 3, r["io"]).reshape(-1, 3).astype(np.int64)
        v = np.asarray(r["min"]) + q / 65535.0 * np.asarray(r["span"])
        out[r["id"]] = dict(v=v, f=f, sys=r["sys"], name=r["name"], rec=r.get("rec") or {})
    return out


ARM_VESSELS = ["zan_brachial_artery", "zan_brachial_veins", "median_n_lateral_root", "ulnar_n", "radial_n", "musculocutaneous_n",
               "zan_ulnar_artery", "zan_ulnar_veins", "zan_radial_veins", "zan_basilic_vein", "zan_cephalic_vein", "zan_median_cubital_vein",
               "posterior_interosseous_n", "anterior_interosseous_n", "zan_radial_collateral_artery", "zan_middle_collateral_artery",
               "zan_superior_ulnar_collateral_artery", "zan_inferior_ulnar_collateral_artery", "zan_deep_brachial_artery"]
VESSEL_SUBJECT = {"vhm": "xfer_zan2vhm_armvessels_q200", "vhf": "xfer_zan2vhf_armvessels_q200"}


def z_ids(own_id):
    m = re.match(r"^(.*)_(l|r)$", own_id)
    if not m:
        return [own_id]
    st, sd = m.groups()
    if st == "triceps_brachii":
        return [f"{h}_{sd}" for h in TRICEPS]
    return [own_id]


def load_z(body, ids, cache):
    import hashlib
    want = set()
    for i in ids:
        want.update(z_ids(i))
    cache = cache.with_name(cache.stem + "_" + hashlib.md5("|".join(sorted(want)).encode()).hexdigest()[:8] + ".pkl")
    if cache.exists():
        return pickle.load(open(cache, "rb"))
    from scripts.transfer.zan_to_vhf_whole_body import collect_zan
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


ZONE_MM = 150.0     # only seams within this distance of the elbow joint centre are repaired here (shoulder / wrist seams: queue)


def elbow_centre(body, side, own):
    key = "own_m" if body == "vhm" else "own_f"
    r = json.loads((REPO / f"data/derived/Q198_model_{key}.json").read_text())
    for j in r["junctions"]:
        if j["name"] == "elbow" and j["side"] == side:
            return np.asarray(j["centre_mm"], float)
    h = own[f"humerus_{side}"]["v"]
    return h[h[:, 1] < h[:, 1].min() + 8].mean(0)


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


def fit_error(mv, mf, zv, zf, cap, window=30.0):
    """distance from the measured structure's surface within `window` mm of the seam plane (M's side) to the fitted Z surface"""
    k = AX[cap["axis"]]
    P = sample_surface(mv, mf, 12000, 5)
    P = P[(cap["sign"] * (P[:, k] - cap["pos"]) > -window) & (cap["sign"] * (P[:, k] - cap["pos"]) < 1.0)]
    if len(P) < 30:
        return np.array([0.0])
    return cKDTree(sample_surface(zv, zf, 12000, 6)).query(P)[0]


class Ctx:
    """everything the two stages share for one body"""

    def __init__(self, body):
        import trimesh
        self.body, self.cfg = body, BODY[body]
        self.B = Bundle(self.cfg["src"])
        self.own = {}
        for it in self.B.items:
            e = it["e"]
            if e["id"] not in self.own:
                v, f = self.B.mesh(it)
                self.own[e["id"]] = dict(e=e, v=v, f=f)
        sk = self.own["skin"]
        self.skin_mesh = trimesh.Trimesh(sk["v"], sk["f"], process=False)
        self.scratch = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
        self.muscles = [i for i in self.own if re.match(r"^(" + "|".join(ARM_STEMS) + r")_(l|r)$", i) and self.own[i]["e"]["cat"] in ("muscle", "tendon")]
        want = list(self.muscles) + [f"{b}_{s}" for b in ("humerus", "radius", "ulna") for s in "lr"] + [f"{v}_{s}" for v in ARM_VESSELS for s in "lr"]
        self.q192 = None
        if body == "vhf":
            self.q192 = json.loads(Q192_FIT.read_text())["transforms_from_Z_source_frame"]
            want += [k for k in self.q192 if k not in ("radius_l", "ulna_l")]
        self.zit = load_z(body, want, self.scratch / f"zarm_{body}.pkl")
        self.q194 = load_q194_left() if body == "vhf" else {}
        from scripts.transfer import zan_to_vhf_whole_body as Q
        self.xf = Q.load_zan_to_vhf(report_path=self.cfg["rep"])
        self.seams = seam_planes(self.B)
        self.zbone = {}          # bone id -> Z mesh vertices in the body frame (after the Q168 transform and the joint correction)
        self.corr = {}           # bone id -> (pre-correction vertices in the body frame, correction fn)
        self.pieces = {}         # new entry id -> dict(v, f, cat, side, rec, rows)
        self.rows = []
        self.cbone = {}          # bone id -> (v, f) measured + continuation, for attachment / constraints
        self._bt = {}

    def side_bones(self, side):
        return [self.cbone.get(i, (self.own[i]["v"], self.own[i]["f"])) for i in
                bone_ids(self.own, ["humerus", "radius", "ulna", "scapula", "clavicle", "hand"], side)]

    def bone_tree(self, ids):
        key = tuple(ids)
        if key not in self._bt:
            pts = np.vstack([sample_surface(*self.cbone.get(i, (self.own[i]["v"], self.own[i]["f"])), 5000, 11) for i in ids])
            self._bt[key] = (cKDTree(pts), pts)
        return self._bt[key]

    def bone_meshes(self, side):
        import trimesh
        return [trimesh.Trimesh(v, f, process=False) for v, f in self.side_bones(side)]


def zbone_in_body(ctx, bid):
    z = ctx.zit[bid]
    return ctx.xf(bid, "bone", z["v"])


def stage_bones(ctx, sides="lr", log=print):
    """Z-Anatomy completion of the elbow bones: (i) the Z forearm bones get the bounded joint correction (q200_chain),
    (ii) every flat cap of a humerus / radius / ulna within the elbow zone is continued by its Z counterpart."""
    from scripts.transfer.q200_chain import refine_to_joint
    own = ctx.own
    for side in sides:
        hid = f"humerus_{side}"
        if hid not in own:
            continue
        Zh = zbone_in_body(ctx, hid)
        ctx.zbone[hid] = Zh
        # the joint partner is the measured distal humerus together with its Z completion (the measured piece decides where the joint is)
        Ht = cKDTree(np.vstack([sample_surface(own[hid]["v"], own[hid]["f"], 20000, 9), sample_surface(Zh, ctx.zit[hid]["f"], 15000, 8)]))
        for b in ("ulna", "radius"):
            bid = f"{b}_{side}"
            if bid not in own or bid not in ctx.zit:
                continue
            Zb = zbone_in_body(ctx, bid)
            info = dict(id=bid, stage="bone", action="joint correction")
            from scripts.transfer.q200_geom import sample_surface as ss
            gap = cKDTree(Ht.data).query(ss(Zb, ctx.zit[bid]["f"], 4000, 3))[0].min()
            if gap <= 3.0:
                ctx.zbone[bid] = Zb; info.update(status="not needed: joint already closed", gap_mm=round(float(gap), 2))
            else:
                Zc, ci, fn = refine_to_joint(Zb, ctx.zit[bid]["f"], own[bid]["v"], own[bid]["f"], Ht, +1)
                ctx.zbone[bid] = Zc; ctx.corr[bid] = (Zb, fn)
                info.update(status="corrected", **{k: round(float(v), 2) for k, v in ci.items()})
            ctx.rows.append(info)
        # continuation of the cut ends
        ec = elbow_centre(ctx.body, side, own)
        for b in ("humerus", "ulna", "radius"):
            bid = f"{b}_{side}"
            if bid not in own or bid not in ctx.zbone:
                continue
            o = own[bid]
            caps = [c for c in find_caps(o["v"], o["f"], minarea=60.0, at_end=2.5)
                    if np.linalg.norm(o["v"][np.unique(o["f"][c["faces"]])].mean(0) - ec) <= ZONE_MM]
            keep_caps = []
            for c in caps:
                if any(k_["axis"] == c["axis"] and k_["sign"] == c["sign"] and abs(k_["pos"] - c["pos"]) < 4.0 for k_ in keep_caps):
                    continue
                keep_caps.append(c)
            caps = keep_caps
            pcs = []
            for cap in caps:
                row = dict(id=bid, stage="bone", axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
                r = continue_cap(o["v"], cap, ctx.zbone[bid], ctx.zit[bid]["f"], min_beyond=3.0)
                if "v" not in r:
                    row["status"] = "held: " + r["reason"]; ctx.rows.append(row); continue
                dd = fit_error(o["v"], o["f"], ctx.zbone[bid], ctx.zit[bid]["f"], cap)
                row.update(status="continued", beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1), shift_mm=round(r["sh"], 1), mode=r["mode"], cap_covered=round(r["cap_covered"], 2),
                           fit_err_median_mm=round(float(np.median(dd)), 1), fit_err_max_mm=round(float(np.quantile(dd, .95)), 1), nv=len(r["v"]), nf=len(r["f"]))
                r["info"] = row
                ctx.rows.append(row); pcs.append(r)
            if pcs:
                V, F, off = [], [], 0
                for r in pcs:
                    V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
                ctx.pieces[f"{bid}_zfill"] = dict(v=np.vstack(V), f=np.vstack(F), base=bid, cat="bone", pieces=pcs, kind="bone")
                ctx.cbone[bid] = (np.vstack([o["v"], np.vstack(V)]), np.vstack([o["f"], np.vstack(F) + len(o["v"])]))


LEFT_SUBJECT = "xfer_zan2vhf_leftforearm_q200"
LEFT_ADD = ["anconeus_l", "brachioradialis_l", "extensor_carpi_radialis_brevis_l", "extensor_carpi_radialis_longus_l", "extensor_carpi_ulnaris_l",
            "extensor_indicis_l", "flexor_carpi_radialis_l", "flexor_carpi_ulnaris_l", "flexor_digitorum_profundus_l", "flexor_digitorum_superficialis_l",
            "flexor_pollicis_longus_l", "pronator_quadratus_l", "pronator_teres_l", "supinator_l",
            "zan_humero_ulnar_head_of_flexor_digitorum_superficialis_l", "zan_palmaris_longus_muscle_l"]
HAND_L = {"carpals_l": ["scaphoid", "lunate", "triquetrum", "pisiform", "trapezium", "trapezoid", "capitate", "hamate"],
          "metacarpal_1_l": ["first_metacarpal"], "metacarpal_2_l": ["second_metacarpal"], "metacarpal_3_l": ["third_metacarpal"],
          "metacarpal_4_l": ["fourth_metacarpal"], "metacarpal_5_l": ["fifth_metacarpal"]}


def q192_apply(T, k, v):
    t = T[k]
    return v @ (t["s"] * np.array(t["R"])).T + np.array(t["t"])


def stage_left_bones(ctx):
    """Her LEFT radius / ulna / carpals / metacarpals / phalanges (absent from the own model): the Z-Anatomy bones on the Q192 per-bone
    similarities (placed on her left-hand / forearm cryosection photographs), radius + ulna then joint-corrected (bounded) against her
    own humerus_l."""
    from scripts.transfer.q200_chain import refine_to_joint
    own, T = ctx.own, ctx.q192
    Zh = zbone_in_body(ctx, "humerus_l")
    ctx.zbone["humerus_l"] = Zh
    hs = np.vstack([sample_surface(own["humerus_l"]["v"], own["humerus_l"]["f"], 20000, 9), sample_surface(Zh, ctx.zit["humerus_l"]["f"], 15000, 8)])
    Ht = cKDTree(hs)
    for b in ("ulna", "radius"):
        bid = f"{b}_l"
        zf = ctx.zit[bid]["f"]
        Zb = q192_apply(T, bid, ctx.zit[bid]["v"])
        d0 = cKDTree(hs).query(sample_surface(Zb, zf, 4000, 3))[0].min()
        Zc, ci, fn = refine_to_joint(Zb, zf, Zb, zf, Ht, +1, scale_rng=(0.98, 1.02), max_trans=15.0)
        ctx.zbone[bid] = Zc; ctx.corr[bid] = (Zb, fn)
        ctx.rows.append(dict(id=bid, stage="bone", action="Z bone on the Q192 photograph placement + joint correction", status="added",
                             **{k: round(float(v), 2) for k, v in ci.items()}))
        rr = ctx.own["radius_r"]["e"]["rec"] if b == "radius" else ctx.own["ulna_r"]["e"]["rec"]
        ctx.pieces[bid] = dict(v=Zc, f=zf, base=bid, cat="bone", kind="left_bone", rec=rr, side="left", subject=LEFT_SUBJECT,
                               info=ci, n_ref=bid)
        ctx.cbone[bid] = (Zc, zf)
        own[bid] = dict(e=dict(id=bid, cat="bone", side="left", rec=rr), v=Zc, f=zf)
    for nid, zn in HAND_L.items():
        V, F, off = [], [], 0
        for n in zn:
            zid = [k for k in T if k.startswith(f"zan_{n}") and k.endswith("_l")]
            for k in zid:
                v = q192_apply(T, k, ctx.zit[k]["v"])
                V.append(v); F.append(ctx.zit[k]["f"] + off); off += len(v)
        if V:
            rr = ctx.own.get(nid.replace("_l", "_r"), {}).get("e", {}).get("rec", {"name": nid})
            ctx.pieces[nid] = dict(v=np.vstack(V), f=np.vstack(F), base=nid, cat="bone", kind="left_bone", rec=rr, side="left", subject=LEFT_SUBJECT, info={}, n_ref=nid)
            ctx.cbone[nid] = (np.vstack(V), np.vstack(F))
            own[nid] = dict(e=dict(id=nid, cat="bone", side="left", rec=rr), v=np.vstack(V), f=np.vstack(F))
    ph = [k for k in T if "phalanx" in k]
    V, F, off = [], [], 0
    for k in ph:
        v = q192_apply(T, k, ctx.zit[k]["v"]); V.append(v); F.append(ctx.zit[k]["f"] + off); off += len(v)
    rr = ctx.own["phalanges_hand_r"]["e"]["rec"]
    ctx.pieces["phalanges_hand_l"] = dict(v=np.vstack(V), f=np.vstack(F), base="phalanges_hand_l", cat="bone", kind="left_bone", rec=rr, side="left",
                                          subject=LEFT_SUBJECT, info={}, n_ref="phalanges_hand_l")
    ctx.cbone["phalanges_hand_l"] = (np.vstack(V), np.vstack(F))
    own["phalanges_hand_l"] = dict(e=dict(id="phalanges_hand_l", cat="bone", side="left", rec=rr), v=np.vstack(V), f=np.vstack(F))


def stage_left_muscles(ctx):
    """Z-Anatomy left forearm muscles absent from her own model, taken from the Q194 build (left forearm driven onto her photographed muscle
    compartment, read-only reference), carried with the joint correction and kept out of the bones / inside her skin."""
    import trimesh
    own = ctx.own
    bm = ctx.bone_meshes("l")
    for mid in LEFT_ADD:
        q = ctx.q194.get(mid)
        if q is None or mid in own:
            ctx.rows.append(dict(id=mid, stage="left muscle", status="held: " + ("already in the model" if mid in own else "not in the Q194 build")))
            continue
        v0 = q["v"]
        v1 = corrected_zf(ctx, mid, v0)
        v2, n_skin = None, 0
        from scripts.transfer.limb_per_bone_transfer import clip_to_skin_mesh, push_off_bones
        v2, n_skin = clip_to_skin_mesh(v1.copy(), ctx.skin_mesh)
        v3, n_bone = push_off_bones(v2, bm)
        ctx.rows.append(dict(id=mid, stage="left muscle", status="added", nv=len(v3), moved_by_joint_correction_mm=round(float(np.median(np.linalg.norm(v1 - v0, axis=1))), 1),
                             skin_clipped=int(n_skin), bone_pushed=int(n_bone)))
        rec = dict(q["rec"]); rec.setdefault("name", q["name"])
        ctx.pieces[mid] = dict(v=v3, f=q["f"], base=mid, cat=q["sys"], kind="left_muscle", rec=rec, side="left", subject=LEFT_SUBJECT, info={}, n_ref=mid)


def corrected_zf(ctx, tid, ZV):
    """Z muscle (already in the body frame) carried with the bones' joint corrections: weights = inverse-square distances to the
    Z bones' pre-correction positions, the humerus (uncorrected) holds the rest."""
    side = tid[-1]
    cb = [b for b in (f"ulna_{side}", f"radius_{side}") if b in ctx.corr]
    if not cb:
        return ZV
    names = [f"humerus_{side}"] + cb
    pre = {}
    for n in names:
        pre[n] = ctx.corr[n][0] if n in ctx.corr else ctx.zbone[n]
    D = np.stack([cKDTree(sample_surface(pre[n], ctx.zit[n]["f"], 3000, 1)).query(ZV)[0] for n in names], 1)
    W = 1.0 / (D + 8.0) ** 2
    W /= W.sum(1, keepdims=True)
    out = ZV.copy()
    for k, n in enumerate(names):
        if n in ctx.corr:
            out += W[:, [k]] * (ctx.corr[n][1](ZV) - ZV)
    return out


def stage_muscles(ctx, only=None, log=print):
    own = ctx.own
    targets = [t for t in ctx.muscles if (not only or t in only)]
    for tid in targets:
        o = own[tid]
        caps = find_caps(o["v"], o["f"])
        if not caps:
            continue
        left_q194 = ctx.body == "vhf" and tid.endswith("_l") and all(z in ctx.q194 for z in z_ids(tid))
        if left_q194:
            zs = [dict(mesh_id=z, v=ctx.q194[z]["v"], f=ctx.q194[z]["f"]) for z in z_ids(tid)]
        else:
            zs = [ctx.zit.get(z) for z in z_ids(tid)]
            zs = [z for z in zs if z is not None]
        if not zs:
            ctx.rows.append(dict(id=tid, stage="muscle", status="held: no Z-Anatomy counterpart mesh", caps=len(caps)))
            continue
        zv, zf, off = [], [], 0
        for z in zs:
            zv.append(z["v"] if left_q194 else ctx.xf(z["mesh_id"], "muscle", z["v"])); zf.append(z["f"] + off); off += len(z["v"])
        ZV, ZF = corrected_zf(ctx, tid, np.vstack(zv)), np.vstack(zf)
        side = tid[-1]; stem = tid[:-2]
        prox_b, dist_b = ATTACH.get(stem, ([], []))
        anch = anchors_of(o["e"]["rec"])
        cen_y = o["v"][:, 1].mean()
        ec = elbow_centre(ctx.body, side, own)
        pieces = []
        for cap in caps:
            ccen = o["v"][np.unique(o["f"][cap["faces"]])].mean(0)
            if np.linalg.norm(ccen - ec) > ZONE_MM:
                continue
            row = dict(id=tid, stage="muscle", axis=cap["axis"], pos=round(cap["pos"], 1), sign=cap["sign"], area=round(cap["area"]), n_frag=cap["n_comp"])
            sm = sorted([x for x in ctx.seams if x[0] == cap["axis"] and abs(x[1] - cap["pos"]) <= SEAM_MATCH_MM], key=lambda x: abs(x[1] - cap["pos"]))
            row["seam_structures"] = sm[0][2] if sm else 0
            if not sm:
                # a lone flat end that stops short of the bone the muscle attaches to is a cut end as well (her left-forearm extensors)
                allb = bone_ids(own, prox_b + dist_b, side)
                gap_b = float(ctx.bone_tree(allb)[0].query(ccen)[0]) if allb else 0.0
                row["end_to_expected_bone_mm"] = round(gap_b, 1)
                if not (cap["area"] >= 60.0 and gap_b > 8.0):
                    row["status"] = "skipped: flat facet shared with fewer than 3 structures (not a data-block seam)"
                    ctx.rows.append(row); continue
            ZVa, ainfo = align_rigid_local(ZV, ZF, o["v"], o["f"], AX[cap["axis"]], cap["pos"], cap["sign"])
            row["align"] = {k_: (round(v_, 1) if isinstance(v_, float) else v_) for k_, v_ in ainfo.items()}
            ax_m = np.linalg.svd(o["v"] - o["v"].mean(0), full_matrices=False)[2][0]
            nrm = np.zeros(3); nrm[AX[cap["axis"]]] = 1.0
            section_like = abs(float(ax_m @ nrm)) >= 0.6          # the cap closes the muscle across its length (not a face along it)
            r = continue_cap(o["v"], cap, ZVa, ZF, min_beyond=10.0, loft=True if section_like else False)
            if "v" not in r:
                row["status"] = "held: " + r["reason"]; ctx.rows.append(row); continue
            kax = AX[cap["axis"]]
            dd = fit_error(o["v"], o["f"], ZVa, ZF, cap)
            row["fit_err_median_mm"] = round(float(np.median(dd)), 1); row["fit_err_max_mm"] = round(float(np.quantile(dd, 0.95)), 1)
            if row.get("fit_err_median_mm", 0) > FIT_ERR_MAX_MM:
                row["status"] = (f"held: the Z-Anatomy counterpart does not coincide with the measured structure near the seam "
                                 f"(median {row['fit_err_median_mm']} mm > {FIT_ERR_MAX_MM:g} mm)")
                ctx.rows.append(row); continue
            tip_y = r["v"][np.argmax(cap["sign"] * (r["v"][:, kax] - cap["pos"]))][1]
            toward_prox = tip_y > cen_y
            ids = bone_ids(own, prox_b if toward_prox else dist_b, side)
            bt = ctx.bone_tree(ids) if ids else None
            cv, pinfo = pull_end(r["v"], cap["axis"], cap["pos"], cap["sign"], anch, bt)
            cv, cinfo = constrain(cv, cap["axis"], cap["pos"], cap["sign"], ctx.skin_mesh, ctx.bone_meshes(side))
            r["v"] = cv
            r["info"] = row
            row.update(status="continued", end="proximal" if toward_prox else "distal", beyond_mm=round(r["beyond_mm"], 1), L=round(r["Lt"], 1),
                       shift_mm=round(r["sh"], 1), mode=r["mode"], section_like=bool(section_like), cap_covered=round(r["cap_covered"], 2), z_to_cap_area=round(r["area_ratio"], 3), pull=pinfo, constraints=cinfo, nv=len(cv), nf=len(r["f"]))
            ctx.rows.append(row)
            pieces.append(r)
        if pieces:
            V, F, off = [], [], 0
            for r in pieces:
                V.append(r["v"]); F.append(r["f"] + off); off += len(r["v"])
            ctx.pieces[f"{tid}_zfill"] = dict(v=np.vstack(V), f=np.vstack(F), base=tid, cat=o["e"]["cat"], pieces=pieces, kind="muscle")


def stage_vessels(ctx, sides="lr"):
    """Z-Anatomy arm vessels / nerves through the elbow (the own models have none there): carried by the Q168/Q195 transform (her left arm: the
    Q194 build's left-forearm placement), kept inside the skin and out of the bones; every number in the card."""
    from scripts.transfer.limb_per_bone_transfer import clip_to_skin_mesh, push_off_bones
    own = ctx.own
    for side in sides:
        bm = ctx.bone_meshes(side)
        for base in ARM_VESSELS:
            zid = f"{base}_{side}"
            if zid in own:
                ctx.rows.append(dict(id=zid, stage="vessel", status="held: already in the model")); continue
            if ctx.body == "vhf" and side == "l":
                q = ctx.q194.get(zid)
                if q is None:
                    ctx.rows.append(dict(id=zid, stage="vessel", status="held: not in the Q194 build")); continue
                v0, f, sysn, name, rec0 = q["v"], q["f"], q["sys"], q["name"], q["rec"]
                v0 = corrected_zf(ctx, zid, v0)
            else:
                z = ctx.zit.get(zid)
                if z is None:
                    ctx.rows.append(dict(id=zid, stage="vessel", status="held: no Z-Anatomy counterpart mesh")); continue
                v0 = ctx.xf(zid, z["cat"], z["v"]); f = z["f"]; sysn = z["cat"]; name = z["name"]; rec0 = {}
                v0 = corrected_zf(ctx, zid, v0)
            out_before = float((~ctx.skin_mesh.contains(v0)).mean())
            v1, n_skin = clip_to_skin_mesh(v0.copy(), ctx.skin_mesh)
            v2, n_bone = push_off_bones(v1, bm)
            import trimesh
            inb = 0.0
            for m in bm:
                inb = max(inb, float(m.contains(v2).mean()))
            row = dict(id=zid, stage="vessel", status="added", nv=len(v2), outside_skin_before_pct=round(100 * out_before, 1), skin_clipped=int(n_skin),
                       bone_pushed=int(n_bone), inside_bone_after_pct=round(100 * inb, 2))
            if inb > 0.05:
                row["status"] = f"held: {100 * inb:.1f} % of the vertices stay inside a bone (> 5 %)"
                ctx.rows.append(row); continue
            ctx.rows.append(row)
            rec = {"name": name, "latin": rec0.get("latin", name), "folder": "upper_limb", "region": "upper_limb"}
            ctx.pieces[zid] = dict(v=v2, f=f, base=zid, cat="nerve" if sysn == "nerve" else "vessel", kind="arm_vessel", rec=rec,
                                   side="left" if side == "l" else "right", subject=VESSEL_SUBJECT[ctx.body], info=row, n_ref=zid)


def stage_attach(ctx, log=print):
    """Z-filled / Z-transferred muscles (never the measured ones) whose end in the elbow zone stops 5-40 mm short of the bone it attaches
    to: smooth bounded translation of that end (weight 0 at 60 % of the length from the end), then skin / bone constraints."""
    from scripts.transfer.limb_per_bone_transfer import clip_to_skin_mesh, push_off_bones
    own = ctx.own
    replaced = {}
    for side in "lr":
        if f"humerus_{side}" not in own:
            continue
        ec = elbow_centre(ctx.body, side, own)
        bm = ctx.bone_meshes(side)
        items = []
        for nid, pc in ctx.pieces.items():
            if pc["kind"] == "left_muscle" and nid.endswith("_" + side):
                items.append(("piece", nid, pc["v"], pc["f"], pc, nid))
        for i in ctx.muscles:
            o = own[i]
            if i.endswith("_" + side) and str(o["e"].get("subject", "")).startswith("xfer_zan2"):
                items.append(("entry", i, o["v"], o["f"], None, i))
        for kind, i, v, f, pc, base in items:
            stem = re.sub(r"_(l|r)$", "", base)
            prox_b, dist_b = ATTACH.get(stem, ([], []))
            if not prox_b:
                continue
            vv = v[np.unique(f)]
            c0, V = vv.mean(0), np.linalg.svd(vv - vv.mean(0), full_matrices=False)[2]
            ax = V[0] if V[0][1] > 0 else -V[0]              # towards the shoulder
            t = (v - c0) @ ax
            lo, hi = float(t.min()), float(t.max()); L = hi - lo
            cur = v.copy(); did = []
            for end, names, sgn in (("proximal", prox_b, +1), ("distal", dist_b, -1)):
                ids = bone_ids(own, names, side)
                if not ids or L < 30:
                    continue
                tt = (cur - c0) @ ax
                near_end = tt >= hi - 0.08 * L if sgn > 0 else tt <= lo + 0.08 * L
                tip = cur[near_end]
                if np.linalg.norm(tip.mean(0) - ec) > 110:
                    continue
                tree, pts = ctx.bone_tree(ids)
                d, jj = tree.query(tip)
                m = int(np.argmin(d)); d0 = float(d[m])
                if not (5.0 < d0 <= 40.0):
                    continue
                u = (pts[jj[m]] - tip[m]); u = u * (1 - 1.5 / max(np.linalg.norm(u), 1e-6))
                dist_from_end = (hi - tt) if sgn > 0 else (tt - lo)
                w = np.clip(1.0 - dist_from_end / (0.6 * L), 0, 1); w = w * w * (3 - 2 * w)
                cur = cur + w[:, None] * u
                did.append((end, round(d0, 1)))
            if did:
                v1, _ = clip_to_skin_mesh(cur.copy(), ctx.skin_mesh)
                v2, _ = push_off_bones(v1, bm)
                ctx.rows.append(dict(id=i, stage="attach", kind=kind, ends_pulled=did, move_max=round(float(np.linalg.norm(v2 - v, axis=1).max()), 1)))
                if kind == "piece":
                    pc["v"] = v2
                else:
                    replaced[i] = (v2, f, dict(attach=did))
    return replaced


def stage_separate(ctx, log=print):
    """Bounded separation (q200_overlap) of every Z-filled / Z-transferred muscle of the elbow zone from the MEASURED muscles it sits inside.
    Measured entries are never moved. Returns {id: (v, f, info)} for the existing xfer entries; the new pieces are updated in place."""
    import trimesh
    from scripts.transfer.limb_per_bone_transfer import clip_to_skin_mesh, push_off_bones
    from scripts.transfer.q200_overlap import separate, inside_fraction
    own = ctx.own
    replaced = {}
    for side in "lr":
        if side not in ("l", "r") or f"humerus_{side}" not in own:
            continue
        ec = elbow_centre(ctx.body, side, own)
        fixed, fixed_ids = [], []
        for i, o in own.items():
            e = o["e"]
            if e["cat"] not in ("muscle", "tendon") or str(e.get("subject", "")).startswith("xfer_zan2") or not i.endswith("_" + side):
                continue
            if "subject" not in e or np.linalg.norm(o["v"].mean(0) - ec) > 220:
                continue
            fixed.append(trimesh.Trimesh(o["v"], o["f"], process=False)); fixed_ids.append(i)
        bm = ctx.bone_meshes(side)

        def constrain(v):
            v1, _ = clip_to_skin_mesh(v.copy(), ctx.skin_mesh)
            v2, _ = push_off_bones(v1, bm)
            return v2
        movers = []
        for nid, pc in ctx.pieces.items():
            if pc["kind"] in ("muscle", "left_muscle") and nid.replace("_zfill", "").endswith("_" + side):
                movers.append(("piece", nid, pc["v"], pc["f"], pc))
        for i in ctx.muscles:
            o = own[i]
            if i.endswith("_" + side) and str(o["e"].get("subject", "")).startswith("xfer_zan2") and np.linalg.norm(o["v"].mean(0) - ec) <= 150:
                movers.append(("entry", i, o["v"], o["f"], None))
        cur_m = {i: (v, f) for kind, i, v, f, pc in movers}
        for kind, i, v, f, pc in movers:
            others = [m for m, fid in zip(fixed, fixed_ids) if fid != i.split("_zfill")[0]]
            # the other Z-filled / Z-transferred muscles of this arm are obstacles too (their current positions); the measured ones stay fixed
            for j_, (vj, fj) in cur_m.items():
                if j_ != i and j_.split("_zfill")[0] != i.split("_zfill")[0] and len(fj) > 3:
                    others.append(trimesh.Trimesh(vj, fj, process=False))
            pin = None
            if kind == "piece" and pc["kind"] == "muscle":
                pin = np.zeros(len(v), bool); off = 0
                for r in pc["pieces"]:
                    pin[off + r["ring0"]] = True; off += len(r["v"])
            if len(f) < 4:
                continue
            nv, info = separate(v, f, others, constrain=constrain, pin=pin)
            row = dict(id=i, stage="overlap", kind=kind, **{k: round(float(x), 3) for k, x in info.items()})
            ctx.rows.append(row)
            if info["rounds"] > 0:
                cur_m[i] = (nv, f)
                if kind == "piece":
                    pc["v"] = nv
                else:
                    replaced[i] = (nv, f, info)
    return replaced


def badge_text(cfg, tid, pieces, name, kind):
    meds = [p["info"].get("fit_err_median_mm") for p in pieces if p["info"].get("fit_err_median_mm") is not None]
    maxs = [p["info"].get("fit_err_max_mm") for p in pieces if p["info"].get("fit_err_max_mm") is not None]
    ends = ", ".join(sorted({f"{p['info']['axis']}={p['info']['pos']} mm" for p in pieces}))
    att = []
    for p in pieces:
        pl = p["info"].get("pull") or {}
        if pl.get("pulled"):
            att.append("far end carried %.1f mm onto its bone" % pl["pull_mm"])
        elif pl.get("note"):
            att.append(pl["note"])
    s = (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) continuation of the measured {name} beyond its flat cut at the data-block seam ({ends}): "
         f"the fitted Z-Anatomy counterpart (Q168 per-bone transform onto {cfg['he']} own bones{', joint-corrected' if kind == 'bone' else ''}), "
         f"clipped at the seam plane and joined to the measured end face by a short loft; ")
    if att:
        s += "; ".join(att) + "; "
    if kind == "muscle":
        s += f"held inside {cfg['he']} skin and out of {cfg['he']} bones; "
    s += "the measured structure is not edited. "
    if meds:
        s += f"Q200 validation median error {np.median(meds):.1f} mm, max {max(maxs):.1f} mm (Z fit vs the measured part within 25-30 mm of the seam)."
    return s


def left_badge(pc):
    i = pc["info"]
    if pc["kind"] == "left_bone":
        t = ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) bone placed on her LEFT forearm / hand cryosection photographs (Q192: per-bone similarity fitted to the "
             "bone-coloured tissue of her left-hand photographs, evidence fit median 0.5-1.1 mm)")
        if i:
            t += (f"; joint-corrected against her own humerus (gap {i['gap_before_mm']:.1f} -> {i['gap_after_mm']:.1f} mm, scale {i['scale']:.2f}, rotation "
                  f"{i['rot_deg']:.1f} deg, shift {i['trans_mm']:.1f} mm)")
        return t + ". Not measured on her: her CT has no left forearm or hand bones."
    return ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) muscle placed on her LEFT forearm: the Q194 fit onto her photographed muscle compartment "
            "(Q192 bones + her left-forearm cryosections), carried with the Q200 joint correction, kept inside her skin and out of the bones. "
            "An estimate: the photographs show the muscle mass, not the individual muscle borders.")


def assemble(ctx):
    cfg = ctx.cfg
    out = []
    for nid, pc in ctx.pieces.items():
        if pc["kind"] == "arm_vessel":
            rec = dict(pc["rec"]); i = pc["info"]
            rec["source"] = "Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge"
            rec["procedural_badge"] = (f"Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) {pc['cat']} through the elbow: not measured on {cfg['he']} body (the CT / "
                f"photographs show no resolvable {pc['cat']} here), carried by the per-bone Z-Anatomy transform onto {cfg['he']} own humerus / radius / ulna, "
                f"{i['skin_clipped']} vertices pulled inside the skin ({i['outside_skin_before_pct']} % were outside), {i['bone_pushed']} pushed out of bone "
                f"({i['inside_bone_after_pct']} % inside a bone after). A position estimate (generic course), not a dissection.")
            ctx.B.add(nid, pc["cat"], pc["side"], pc["subject"], rec, pc["v"], pc["f"])
            out.append(nid); continue
        if pc["kind"].startswith("left_"):
            rec = {k: pc["rec"][k] for k in ("name", "latin", "folder", "region", "origin", "insertion") if k in pc["rec"]}
            rec["source"] = "Z-Anatomy (CC BY-SA 4.0), placed on her left-forearm / hand cryosection photographs (Q192 / Q194); see the badge"
            rec["procedural_badge"] = left_badge(pc)
            ctx.B.add(nid, pc["cat"], pc["side"], pc["subject"], rec, pc["v"], pc["f"])
            out.append(nid); continue
        e = ctx.own[pc["base"]]["e"]; rec = e["rec"]
        name = rec.get("name", pc["base"])
        newrec = {k: rec[k] for k in ("latin", "folder", "region", "origin", "insertion") if k in rec}
        newrec.update(name=f"{name} (continuation beyond the data-block seam, filled from Z-Anatomy)",
                      source="Z-Anatomy (CC BY-SA 4.0), fitted to this body; see the badge",
                      procedural_badge=badge_text(cfg, pc["base"], pc["pieces"], name, pc["kind"]))
        ctx.B.add(nid, pc["cat"], e["side"], cfg["subject"], newrec, pc["v"], pc["f"])
        out.append(nid)
    return out


def write_bundle(ctx, out):
    att = {ctx.cfg["subject"]: ["Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D): continuations of structures cut flat at CT data-block seams, "
           "fitted onto this body's own bones (Q200); the measured structures are not edited. Z-Anatomy: models by the Z-Anatomy project, app by "
           "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. Licensed CC BY-SA 4.0; this derivative remains CC BY-SA 4.0 (ShareAlike)."]}
    return ctx.B.write(out, new_subject_attribution=att)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["vhm", "vhf"])
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out", default=None)
    ap.add_argument("--rows", default=None)
    a = ap.parse_args()
    t = time.time()
    ctx = Ctx(a.body)
    stage_bones(ctx, sides="lr" if a.body == "vhm" else "r")
    if a.body == "vhf":
        stage_left_bones(ctx)
        stage_left_muscles(ctx)
    print("bones done", round(time.time() - t, 1))
    stage_muscles(ctx, only=a.only)
    replaced = {}
    if not a.only:
        stage_vessels(ctx)
        rep_att = stage_attach(ctx)
        # the attach-moved entries are the input of the separation
        for i, (nv, nf, info) in rep_att.items():
            ctx.own[i] = dict(ctx.own[i], v=nv)
        replaced = stage_separate(ctx)
        for i, (nv, nf, info) in rep_att.items():
            if i not in replaced:
                replaced[i] = (nv, nf, dict(attach=info["attach"], inside_before=0.0, inside_after=0.0, move_max=0.0, volume_ratio=1.0, rounds=0))
            else:
                replaced[i][2]["attach"] = info["attach"]
    for r in ctx.rows:
        print(r)
    if not a.only:
        for i, (nv, nf, info) in replaced.items():
            old = ctx.own[i]["e"]["rec"].get("procedural_badge", "")
            ctx.B.replace(i, nv, nf, rec_updates={"procedural_badge": (old + " " if old else "") + (
                (f"Q200: end carried onto its bone ({', '.join(f'{e} end was {d} mm short' for e, d in info['attach'])}); " if info.get("attach") else "Q200: ") +
                (f"separated from the measured muscles it sat inside (inside them {100 * info['inside_before']:.1f} % -> {100 * info['inside_after']:.1f} % of "
                 f"the vertices, moved at most {info['move_max']:.1f} mm, volume {info['volume_ratio']:.2f}x; the measured muscles were not moved)." if info.get("rounds") else "no overlap with the measured muscles to resolve."))})
        assemble(ctx)
        out = Path(a.out) if a.out else ctx.cfg["out"]
        print("bundle bytes", write_bundle(ctx, out))
    if a.rows:
        Path(a.rows).write_text(json.dumps(ctx.rows, indent=1, default=str))
    seams = {nid: [dict(axis=r["axis"], pos=r["pos"], polys=r["covered"]) for r in pc["pieces"] if "covered" in r]
             for nid, pc in ctx.pieces.items() if pc["kind"] in ("muscle", "bone") and "pieces" in pc}
    (REPO / f"data/derived/Q200_seams_{a.body}.json").write_text(json.dumps(seams))
    print("done", round(time.time() - t, 1))
