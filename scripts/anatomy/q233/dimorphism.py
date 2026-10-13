"""Q233: skeletal / body dimorphism measured on the actual meshes of the six pages (atlas frame: mm, +X right, +Y sup, +Z ant).
Every function takes the Q233 loader output (list of structures) and returns plain floats; the landmarks are found by simple geometric rules on the
bone meshes (documented in each function), so they are comparable across the six pages but are NOT hand-placed osteometric landmarks."""
from __future__ import annotations
import numpy as np, trimesh
from scipy.spatial import cKDTree


def bone(S, base, side=None):
    """largest connected component of the bone structure(s) whose id (without '#n') equals base; zfill pieces ignored"""
    ms = []
    for x in S:
        b = x["id"].split("#")[0]
        if b == base and x["sys"] == "bone":
            m = trimesh.Trimesh(x["v"], x["f"], process=False)
            cc = m.split(only_watertight=False)
            ms.append(max(cc, key=lambda c: len(c.vertices)))
    if not ms:
        return None
    if base == "sacrum" and len(ms) > 1:       # her page carries the sacrum as two overlapping meshes (sacrum#1 + a 7500-vertex upper block): union
        return trimesh.util.concatenate(ms)
    return max(ms, key=lambda c: len(c.vertices))


def _pts(m, n=60000, seed=0):
    return m.sample(n) if len(m.faces) else m.vertices


def pelvis_landmarks(S):
    hl, hr, sa = bone(S, "hip_bone_l"), bone(S, "hip_bone_r"), bone(S, "sacrum")
    H = [hl, hr]
    out = {}
    # symphysis: the medial faces of the two pubic bones; pubic bones = anterior part of each hip bone
    meds = []
    for h, sgn in ((hl, -1), (hr, +1)):
        v = h.vertices
        zlim = v[:, 2].min() + 0.62 * np.ptp(v[:, 2])
        c = v[(v[:, 2] > zlim) & (v[:, 1] < v[:, 1].min() + 0.55 * np.ptp(v[:, 1]))]
        xmed = (c[:, 0].max() if sgn < 0 else c[:, 0].min())
        face = c[np.abs(c[:, 0] - xmed) < 5.0]
        meds.append(face)
    face = np.vstack(meds)
    out["SU"] = np.array([face[:, 0].mean(), face[:, 1].max(), face[face[:, 1] > face[:, 1].max() - 3, 2].mean()])   # upper symphysis (pubic crest level)
    out["SL"] = np.array([face[:, 0].mean(), face[:, 1].min(), face[face[:, 1] < face[:, 1].min() + 3, 2].mean()])   # lower symphysis
    v = sa.vertices
    hgt = np.ptp(v[:, 1])
    up = v[(v[:, 1] > v[:, 1].max() - 0.28 * hgt) & (np.abs(v[:, 0] - np.median(v[:, 0])) < 14)]
    out["P"] = up[np.argmax(up[:, 2])]                                                        # sacral promontory (most anterior upper-midline point)
    lo = v[(np.abs(v[:, 0] - np.median(v[:, 0])) < 14)]
    out["A"] = lo[np.argmin(lo[:, 1])]                                                        # sacral apex
    return out, hl, hr, sa


def inlet(S):
    """pelvic inlet: plane through promontory P and upper symphysis SU containing the x axis; transverse diameter = widest free interval between the
    inner edges of the bones cut by the plane (+-3 mm slab, hip bones + sacrum); AP = |P-SU| (anatomical conjugate)."""
    L, hl, hr, sa = pelvis_landmarks(S)
    P, SU = L["P"], L["SU"]
    d = SU - P; d[0] = 0.0
    ap = float(np.linalg.norm(d)); es = d / ap
    n = np.cross([1.0, 0, 0], es); n /= np.linalg.norm(n)
    pts = np.vstack([_pts(m, 80000) for m in (hl, hr, sa)])
    rel = pts - P
    sl = np.abs(rel @ n) < 3.0
    u = (rel[sl] @ es) / ap
    xx = pts[sl][:, 0]
    xm = 0.5 * (hl.vertices[:, 0].max() + hr.vertices[:, 0].min()) * 0 + float(np.median(pts[:, 0]))
    best = 0.0; bu = None
    for u0 in np.arange(0.30, 0.80, 0.025):
        m = (u > u0 - 0.0125) & (u < u0 + 0.0125)
        if m.sum() < 5:
            continue
        x = xx[m]
        left = x[(x < xm) & (x > xm - 95)]; right = x[(x >= xm) & (x < xm + 95)]
        if len(left) < 2 or len(right) < 2:
            continue
        w = right.min() - left.max()
        if w > best:
            best, bu = float(w), float(u0)
    return dict(ap_conjugate_mm=round(ap, 1), transverse_mm=round(best, 1), at_u=bu,
                inlet_index_ap_over_transverse_pct=round(100 * ap / best, 1) if best else None,
                inlet_index_transverse_over_ap_pct=round(100 * best / ap, 1) if best else None)


def outlet_and_subpubic(S):
    L, hl, hr, sa = pelvis_landmarks(S)
    res = {}
    # intertuberous distance: lowest points of each hip bone (ischial tuberosities)
    tl = hl.vertices[np.argmin(hl.vertices[:, 1])]; tr = hr.vertices[np.argmin(hr.vertices[:, 1])]
    res["intertuberous_mm"] = round(float(abs(tr[0] - tl[0])), 1)
    res["tuber_l"] = tl.round(1).tolist(); res["tuber_r"] = tr.round(1).tolist()
    # subpubic angle: angle at the lower symphysis point between the axes of the two ischiopubic rami (PCA of the hip-bone points within 8 mm of the
    # segment lower-symphysis -> ischial tuberosity), measured in 3-D; plus the proxy angle of the two segments themselves
    SL = L["SL"]
    dirs = []
    for h, T in ((hl, tl), (hr, tr)):
        a, b = SL, T
        ab = b - a; ln = np.linalg.norm(ab); e = ab / ln
        v = h.vertices
        t = (v - a) @ e
        dist = np.linalg.norm((v - a) - np.outer(t, e), axis=1)
        sel = v[(t > 0.12 * ln) & (t < 0.9 * ln) & (dist < 8.0)]
        if len(sel) < 12:
            dirs.append(e)
            continue
        d = np.linalg.svd(sel - sel.mean(0), full_matrices=False)[2][0]
        if d @ e < 0: d = -d
        dirs.append(d)
    ang = np.degrees(np.arccos(np.clip(dirs[0] @ dirs[1], -1, 1)))
    e1 = (tl - SL) / np.linalg.norm(tl - SL); e2 = (tr - SL) / np.linalg.norm(tr - SL)
    res["subpubic_angle_deg"] = round(float(ang), 1)
    res["subpubic_proxy_symphysis_to_tuberosities_deg"] = round(float(np.degrees(np.arccos(np.clip(e1 @ e2, -1, 1)))), 1)
    return res


def sacrum_metrics(S):
    L, hl, hr, sa = pelvis_landmarks(S)
    P, A = L["P"], L["A"]
    v = sa.vertices
    length = float(np.linalg.norm(P - A))
    upper = v[v[:, 1] > v[:, 1].max() - 0.45 * np.ptp(v[:, 1])]
    breadth = float(np.ptp(upper[:, 0]))
    # curvature: anterior surface of the sagittal strip, distance from the chord P-A
    strip = v[np.abs(v[:, 0] - np.median(v[:, 0])) < 6]
    e = (A - P); e[0] = 0; e /= np.linalg.norm(e); nrm = np.array([0, e[2], -e[1]]) * -1   # anterior-pointing normal in the sagittal plane
    if nrm[2] < 0: nrm = -nrm
    rel = strip - P
    t = rel @ e; dd = rel @ nrm
    ok = (t > 0.05 * length) & (t < 0.95 * length)
    depth = 0.0
    for t0 in np.arange(0.1 * length, 0.92 * length, 4.0):
        m = ok & (t >= t0) & (t < t0 + 4.0)
        if m.sum():
            depth = max(depth, -float(dd[m].max()))   # anterior surface lies posterior to the chord when concave forward
    return dict(sacral_length_straight_mm=round(length, 1), sacral_breadth_mm=round(breadth, 1),
                sacral_index_breadth_over_length_pct=round(100 * breadth / length, 1),
                sacral_curvature_depth_mm=round(depth, 1), sacral_curvature_index_pct=round(100 * depth / length, 1))


def pelvis_size(S):
    L, hl, hr, sa = pelvis_landmarks(S)
    allv = np.vstack([hl.vertices, hr.vertices])
    bib = float(np.ptp(allv[:, 0])); hgt = float(np.ptp(allv[:, 1]))
    return dict(bi_iliac_breadth_mm=round(bib, 1), pelvic_height_mm=round(hgt, 1), breadth_over_height_pct=round(100 * bib / hgt, 1))


def fit_sphere(P, it=6):
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    keep = np.ones(len(P), bool)
    for _ in range(it):
        sol = np.linalg.lstsq(A[keep], b[keep], rcond=None)[0]
        c = sol[:3]; r = np.sqrt(sol[3] + (c ** 2).sum())
        res = np.abs(np.linalg.norm(P - c, axis=1) - r)
        keep = res < max(1.0, np.quantile(res, 0.8))
    return c, r, float(np.sqrt((res[keep] ** 2).mean()))


def femur_metrics(S, side):
    f = bone(S, f"femur_{side}")
    if f is None:
        return {}
    v = f.vertices
    top = v[v[:, 1] > v[:, 1].max() - 32]
    medial = top[(top[:, 0] < np.median(v[:, 0])) if side == "r" else (top[:, 0] > np.median(v[:, 0]))]
    # femoral head = the most medial-superior cap: sphere fit on the 40 % most medial points of the top slab
    xs = medial[:, 0]
    sel = medial[(xs <= np.quantile(xs, 0.45))] if side == "r" else medial[(xs >= np.quantile(xs, 0.55))]
    c, r, rms = fit_sphere(sel)
    # bicondylar breadth: width of the distal 60 mm along the shaft axis in its widest transverse direction
    ax = np.linalg.svd(v - v.mean(0), full_matrices=False)[2][0]
    if ax[1] < 0: ax = -ax
    tt = (v - v.mean(0)) @ ax
    dist = v[tt < tt.min() + 60]
    d2 = dist - dist.mean(0); d2 = d2 - np.outer(d2 @ ax, ax)
    w = np.linalg.svd(d2, full_matrices=False)[2][0]
    bic = float(np.ptp(d2 @ w))
    return dict(femoral_head_diameter_mm=round(2 * r, 1), head_fit_rms_mm=round(rms, 2), bicondylar_breadth_mm=round(bic, 1),
                femur_length_mm=round(float(np.ptp(tt)), 1), head_centre=c.round(1).tolist())


def sternum_metrics(S):
    st = bone(S, "sternum")
    if st is None:
        return {}
    v = st.vertices
    return dict(sternum_length_mm=round(float(np.ptp(v[:, 1])), 1), sternum_width_mm=round(float(np.ptp(v[:, 0])), 1))


def shoulder_hip(S):
    sl, sr = bone(S, "scapula_l"), bone(S, "scapula_r")
    if sl is None or sr is None:
        return {}
    def acro(m, sgn):
        v = m.vertices
        top = v[v[:, 1] > v[:, 1].max() - 0.25 * np.ptp(v[:, 1])]
        return top[np.argmax(top[:, 0] * sgn)]
    ar, al = acro(sr, +1), acro(sl, -1)
    bia = float(ar[0] - al[0])
    pel = pelvis_size(S)["bi_iliac_breadth_mm"]
    return dict(biacromial_mm=round(bia, 1), bi_iliac_mm=pel, shoulder_to_hip_ratio=round(bia / pel, 3))


def q_angle(S, side):
    h, pa, ti = bone(S, f"hip_bone_{side}"), bone(S, f"patella_{side}"), bone(S, f"tibia_{side}")
    if h is None or pa is None or ti is None:
        return {}
    v = h.vertices
    top = v[v[:, 1] > v[:, 1].max() - 45]
    asis = top[np.argmax(top[:, 2])]
    pc = pa.vertices.mean(0)
    tv = ti.vertices
    up = tv[tv[:, 1] > tv[:, 1].max() - 0.22 * np.ptp(tv[:, 1])]
    tt = up[np.argmax(up[:, 2])]
    def ang(a, b):
        a = a[[0, 1]]; b = b[[0, 1]]
        return np.degrees(np.arccos(np.dot(a, b) / np.linalg.norm(a) / np.linalg.norm(b)))
    q = 180.0 - ang(asis - pc, tt - pc)           # angle between the extension of ASIS->patella and patella->tuberosity (coronal projection)
    return dict(q_angle_deg=round(float(q), 1), asis=asis.round(1).tolist(), patella_centre=pc.round(1).tolist(), tibial_tuberosity=tt.round(1).tolist())


def ischiopubic(S):
    """Washburn-type ischiopubic index = pubic length / ischial length x 100, both from the femoral-head centre (proxy for the acetabular centre):
    pubic length = centre -> upper symphysis point; ischial length = centre -> the farthest point of the postero-inferior ischium (tuberosity)."""
    L, hl, hr, sa = pelvis_landmarks(S)
    out = {}
    vals = []
    for side, h in (("l", hl), ("r", hr)):
        fm = femur_metrics(S, side)
        if not fm:
            continue
        c = np.array(fm["head_centre"])
        pub = float(np.linalg.norm(c - L["SU"]))
        v = h.vertices
        sel = v[(v[:, 1] < c[1] - 25) & (v[:, 2] < c[2] - 5)]
        isch = float(np.linalg.norm(sel - c, axis=1).max())
        out[f"pubic_length_{side}_mm"] = round(pub, 1); out[f"ischial_length_{side}_mm"] = round(isch, 1)
        vals.append(100 * pub / isch)
    if vals:
        out["ischiopubic_index"] = round(float(np.mean(vals)), 1)
    return out


def sciatic_notch(S):
    """greater sciatic notch in the lateral (z,y) silhouette of one hip bone: the deepest concavity of the posterior-inferior border relative to the convex
    hull; angle = angle at the notch's deepest point between the two hull-bridge end points (a hull-defect angle, NOT an osteometric notch angle)."""
    from scipy.spatial import ConvexHull
    res = []
    for h in (bone(S, "hip_bone_l"), bone(S, "hip_bone_r")):
        pts = np.c_[h.vertices[:, 2], h.vertices[:, 1]]
        # rasterise the silhouette, keep the posterior border (min z per y row) between 15 % and 55 % of the height
        y0, y1 = pts[:, 1].min(), pts[:, 1].max()
        rows = np.arange(y0 + 0.30 * (y1 - y0), y0 + 0.62 * (y1 - y0), 2.0)
        border = []
        for r in rows:
            m = pts[(pts[:, 1] >= r) & (pts[:, 1] < r + 2.0)]
            if len(m): border.append((m[:, 0].min(), r + 1.0))
        b = np.array(border)
        if len(b) < 8:
            continue
        # notch = largest deviation of the border from the chord joining its posterior-most extremes
        i0 = int(np.argmin(b[:, 0] + 0)); 
        # chord between the highest point (PIIS side) and the lowest (ischial spine side) of the window
        a, c = b[-1], b[0]
        ch = c - a; ch = ch / np.linalg.norm(ch); nn = np.array([-ch[1], ch[0]])
        dd = (b - a) @ nn
        k = int(np.argmax(np.abs(dd)))
        d_ = b[k]
        v1 = a - d_; v2 = c - d_
        ang = np.degrees(np.arccos(np.clip(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1)))
        res.append((float(ang), float(abs(dd[k]))))
    if not res:
        return {}
    return dict(sciatic_notch_hull_angle_deg=round(float(np.mean([r[0] for r in res])), 1), sciatic_notch_depth_mm=round(float(np.mean([r[1] for r in res])), 1))
