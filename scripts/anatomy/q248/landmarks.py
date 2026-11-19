"""Q248: pelvic / knee landmarks used by the rule-based ligaments.
On the Z pages (Combined, Base) they are the CONTACT PATCHES of the Z-Anatomy ligaments with the page's own bones (the attachments the Z-Anatomy modellers drew): ischial spine = sacrospinous ligament on the hip bone,
ischial tuberosity = sacrotuberous ligament on the hip bone, pubic tubercle / ASIS = the two ends of the inguinal ligament, subpubic angle = arcuate pubic ligament, symphysis = interpubic disc.
On the own pages they are carried from the Combined page by the local hip-bone fit of transfer.Carrier and snapped to the own bone (so they lie ON the own bone surface).
Knee: patellar apex = lowest point of the patella; tibial tuberosity = anterior-most point of the proximal tibia below the tibial plateau (rule, measured on the page's own bones)."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree
import lig_pages as PG


def patch(bf, ent, bone_id, tol=1.6, slack=2.5, dmax=7.0):
    """vertices of the ligament entry in contact with the bone: within max(tol, dmin + slack) mm of its surface, if the closest vertex is within dmax mm (a Combined-page fit can leave the ligament a few mm off the bone)"""
    d = np.abs(bf.signed(ent["v"], [bone_id])[0])
    if d.min() > dmax:
        return ent["v"][:0]
    return ent["v"][d <= max(tol, d.min() + slack)]


def snap(bf, P, bone_id):
    d, a, n, p = bf.signed(np.atleast_2d(P), [bone_id])
    return p[0], float(d[0])


def z_pelvis_landmarks(E, bf):
    """E = page entries (Z page). -> {name: point}, report"""
    L, rep = {}, {}
    def get(*ids):
        for i in ids:
            if i in E: return E[i]
        return None
    for s in "lr":
        hip = f"hip_bone_{s}"
        if hip not in E:
            continue
        sp = get(f"sacrospinous_ligament_{s}", f"zan_sacrospinous_ligament_{s}")
        if sp is not None:
            pa = patch(bf, sp, hip)
            if len(pa):
                L[f"ischial_spine_{s}"] = snap(bf, pa.mean(0), hip)[0]
        st = get(f"sacrotuberous_ligament_{s}", f"zan_sacrotuberous_ligament_{s}")
        if st is not None:
            pa = patch(bf, st, hip)
            if len(pa):
                L[f"ischial_tuberosity_{s}"] = snap(bf, pa.mean(0), hip)[0]
        ing = get(f"inguinal_ligament_{s}", f"zan_inguinal_ligament_{s}")
        if ing is not None:
            pa = patch(bf, ing, hip, 2.0)
            if len(pa) >= 4:
                # two ends: split by the principal axis of the whole ligament
                v = ing["v"]; c = v.mean(0); ax = np.linalg.svd(v - c, full_matrices=False)[2][0]
                t = (pa - c) @ ax
                med = pa[t < 0] if (v[:, 0].mean() * 0 + 1) else pa
                end_a, end_b = pa[t < np.median(t)], pa[t >= np.median(t)]
                # ASIS is the more lateral and higher end, the pubic tubercle the more medial / lower one
                ca, cb = end_a.mean(0), end_b.mean(0)
                asis, tub = (ca, cb) if ca[1] > cb[1] else (cb, ca)
                L[f"asis_{s}"] = snap(bf, asis, hip)[0]; L[f"pubic_tubercle_{s}"] = snap(bf, tub, hip)[0]
    ar = get("arcuate_pubic_ligament", "zan_arcuate_pubic_ligament")
    if ar is not None:
        for s in "lr":
            hip = f"hip_bone_{s}"
            if hip in E:
                pa = patch(bf, ar, hip, 2.0)
                if len(pa):
                    L[f"subpubic_{s}"] = snap(bf, pa.mean(0), hip)[0]
    sy = get("pubic_symphysis_disc", "zan_pubic_symphysis_disc", "zan_interpubic_disc")
    if sy is not None:
        L["symphysis_center"] = sy["v"].mean(0)
    return L


def pubis_frame(E):
    """symphysial face of the two hip bones measured on the page's OWN hip bone meshes (all six pages): midline x, upper / lower end of the face (pubic crest, subpubic angle), anterior face z.
    face = hip-bone vertices within FACE_MM of the plane x = x_mid in the anterior third of the pelvis (x_mid = mean of the innermost anterior vertices of both sides)."""
    hl, hr = E["hip_bone_l"]["v"], E["hip_bone_r"]["v"]
    zmax = max(hl[:, 2].max(), hr[:, 2].max())
    ant = lambda v: v[v[:, 2] > zmax - 45]                      # noqa: E731
    al, ar = ant(hl), ant(hr)
    x_mid = 0.5 * (np.percentile(al[:, 0], 99.5) + np.percentile(ar[:, 0], 0.5))
    il, ir = np.percentile(al[:, 0], 99.5), np.percentile(ar[:, 0], 0.5)
    face = np.vstack([al[al[:, 0] > il - 4], ar[ar[:, 0] < ir + 4]])
    return dict(x_mid=float(x_mid), half_gap=float((ir - il) / 2), y_top=float(np.percentile(face[:, 1], 98)), y_bot=float(np.percentile(face[:, 1], 2)), z_front=float(np.percentile(face[:, 2], 90)), n=int(len(face)), zmax=float(zmax))
