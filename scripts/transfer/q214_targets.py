"""Q214: the four muscles (7 sides) that the own pages still lack, their Z-Anatomy sources and their attachment landmark sets on the person's OWN bones."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import motor_points_q187 as MP  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402

BODY = {
    "vhm": dict(src=REPO / "build/viewer_m_hr_q212", out=REPO / "build/viewer_m_hr_q214", page=REPO / "build/q214/viewer_m_hr", stem="atlas_viewer_male",
                z_page=REPO / "build/q211/viewer_zan_vhm/atlas_viewer_zan_male_fitted.html", pron="his", Pron="His", subject="xfer_zan2vhm_q214", mp_key="vhm"),
    "vhf": dict(src=REPO / "build/viewer_f_hr_q213", out=REPO / "build/viewer_f_hr_q214", page=REPO / "build/q214/viewer_f_hr", stem="atlas_viewer_female",
                z_page=REPO / "build/q213/viewer_zan_female/atlas_viewer_zan_female.html", pron="her", Pron="Her", subject="xfer_zan2vhf_q214", mp_key="vhf"),
}
SIDES = ("r", "l")
# own id stem -> (Z id pattern, kind).  kind: "z" = transfer-fit of the Z muscle
MUSCLES = {
    "splenius_capitis": "splenius_capitis_{s}",
    "splenius_cervicis": "zan_splenius_colli_muscle_{s}",        # Terminologia Anatomica: M. splenius cervicis = Z-Anatomy "splenius colli"
    "fibularis_brevis": "fibularis_brevis_{s}",
    "flexor_pollicis_brevis": "flexor_pollicis_brevis_{s}",
}
# sides wanted per muscle: the task = both sides of splenius capitis / cervicis and fibularis brevis, the RIGHT flexor pollicis brevis
WANT = {"splenius_capitis": "rl", "splenius_cervicis": "rl", "fibularis_brevis": "rl", "flexor_pollicis_brevis": "r"}
LANDMARK_TEXT = {
    "splenius_capitis": ("spinous processes C7-T3 of the person's own vertebrae", "mastoid process of the person's own cranium (landmark of the sternocleidomastoid rule, Q213)"),
    "splenius_cervicis": ("spinous processes T3-T6 of the person's own vertebrae", "transverse processes C1-C3 of the person's own cervical vertebrae"),
    "fibularis_brevis": ("lateral surface of the person's own fibula (distal two thirds)", "tuberosity of the base of the person's own 5th metatarsal"),
    "flexor_pollicis_brevis": ("the person's own carpal bones (trapezium / flexor retinaculum region)", "the person's own thumb proximal phalanx base"),
}


def z_id(stem, s):
    return MUSCLES[stem].format(s=s)


def own_id(stem, s):
    return f"{stem}_{s}"


def body_for_landmarks(bundle, vk):
    meshes = {}
    for it in bundle.items:
        e = it["e"]
        if e["cat"] in ("bone", "muscle") and e["id"] not in meshes:
            v, f = bundle.mesh(it)
            meshes[e["id"]] = {"cat": e["cat"], "v": v, "f": f}
    return MP.Body(vk, meshes)


def targets(ctx, lmbody, stem, s):
    """(origin cloud, insertion cloud, landmark description) on the person's own bones"""
    sx = 1 if s == "r" else -1
    if stem == "splenius_capitis":
        A = np.vstack([F.spinous_pts(ctx, "cervical_vertebrae", 7, 7), F.spinous_pts(ctx, "thoracic_vertebrae", 1, 3)])
        cr = ctx.bone_pts(r"^(cranium|occipital)$")
        try:
            mast = lmbody.lm("mastoid", s)
            info = {"mastoid_landmark_mm": [round(float(x), 1) for x in mast]}
        except MP.LandmarkMissing as e:       # the skull mesh has no surface within 20 mm of the SCM insertion on this side: the cranium vertex nearest to the SCM insertion stands in
            scm = lmbody.mv(f"sternocleidomastoid_{s}")
            top = scm[scm[:, 1] >= np.percentile(scm[:, 1], 98)].mean(axis=0)
            d, i = cKDTree(cr).query(top)
            near = cr[np.linalg.norm(cr - cr[i], axis=1) < 20]
            mast = near[np.argmin(near[:, 1])]
            info = {"mastoid_landmark_mm": [round(float(x), 1) for x in mast], "mastoid_landmark_note": f"Q213 landmark rule refused ({e}); lowest cranium vertex within 20 mm of the cranium point nearest the SCM insertion ({d:.0f} mm) used"}
        B = cr[np.linalg.norm(cr - mast, axis=1) < 25.0]
        return A, B, info
    if stem == "splenius_cervicis":
        A = F.spinous_pts(ctx, "thoracic_vertebrae", 3, 6)
        B = F.transverse_pts(ctx, "cervical_vertebrae", 1, 3, s)
        return A, B, {}
    if stem == "fibularis_brevis":
        fb = ctx.bone_pts(rf"^fibula_{s}$")
        y0, y1 = fb[:, 1].min(), fb[:, 1].max()
        A = fb[fb[:, 1] <= y0 + 0.67 * (y1 - y0)]
        mt = ctx.bone_pts(rf"^metatarsals_{s}$")
        ca = ctx.bone_pts(rf"^calcaneus_{s}$")
        ax = mt.mean(0) - ca.mean(0)
        ax /= np.linalg.norm(ax)                                      # foot axis: calcaneus -> metatarsals
        lat = mt[sx * mt[:, 0] >= np.percentile(sx * mt[:, 0], 70)]       # the lateral metatarsal ray = the 5th metatarsal (merged mesh of the five)
        t = (lat - mt.mean(0)) @ ax
        base = lat[t <= t.min() + 14.0]                                   # its proximal 14 mm = the base with the tuberosity
        tub = base[np.argmax(sx * base[:, 0])]
        B = base[np.linalg.norm(base - tub, axis=1) < 18.0]
        return A, B, {"mt5_tuberosity_landmark_mm": [round(float(x), 1) for x in tub]}
    if stem == "flexor_pollicis_brevis":
        A = ctx.bone_pts(rf"^carpals_{s}(_q212)?$")
        B = ctx.bone_pts(rf"^phalanges_hand_{s}$")
        return A, B, {}
    raise KeyError(stem)
