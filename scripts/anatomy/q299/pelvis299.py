"""Q299 Part A: pelvis proportions on all six pages, measured on the shipped meshes.

    python3 scripts/anatomy/q299/pelvis299.py all            -> data/derived/Q299_pelvis.json

Frame: mm, +X subject right, +Y superior, +Z anterior.  Landmarks are geometric rules on each page's own bone
meshes (same rules on all six pages so the numbers are comparable), not hand-placed osteometric points.

Literature used for the female ranges (read in Q292, docs/research/Q292_female_breast_pelvis_sources.md):
  MR pelvimetry, vaginal-delivery group (doi:10.1016/j.ejrad.2018.03.024):
      inlet transverse 134.7 +- 7.5, obstetric conjugate 126.9 +- 8.3, interspinous 113.4 +- 8.2, intertuberous 127.1 +- 10.4 mm
  subpubic angle female 87.4 +- 6.5 deg, male 64.8 +- 6.0 deg (PMID 32274246)
Extra literature added in Q299 (see docs/research/Q299_pelvis_containment_crosssection.md for the full list).
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q241")); sys.path.insert(0, str(REPO / "scripts/anatomy/q237"))
from scripts.anatomy.q233 import dimorphism as DM  # noqa: E402
import core as C  # noqa: E402

OUT = REPO / "data/derived/Q299_pelvis.json"
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]


def load(key):
    # the CURRENT page dir, from the single place the project keeps it (scripts/anatomy/q241/model.py SRC), unless
    # Q237_SRC_<key> is already set -- a hard-coded build dir here is how the first Q299 after-audit silently
    # re-measured the pages it was meant to be checking the fix against.
    if "Q237_SRC_" + key not in os.environ:
        sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
        import model as _MD
        os.environ["Q237_SRC_" + key] = str(_MD.page_dir(key))
    return C.load(key)


def fit_plane(P):
    c = P.mean(0)
    n = np.linalg.svd(P - c, full_matrices=False)[2][2]
    return c, n / np.linalg.norm(n)


def app_frame(S):
    """The anterior pelvic plane (Lewinnek): the plane through the two anterior superior iliac spines and the pubic
    symphysis.  Acetabular version and inclination in the literature are measured in THIS frame, not in the scanner /
    atlas frame, so they are comparable between a standing atlas and a supine cadaver.
    Returns (origin, ex, ey, ez): ex = towards the subject's right, ez = the anterior normal, ey = superior."""
    L, hl, hr, _ = DM.pelvis_landmarks(S)
    asis = []
    for h in (hl, hr):
        v = h.vertices; top = v[v[:, 1] > v[:, 1].max() - 45]
        asis.append(top[np.argmax(top[:, 2])])
    A, B = np.asarray(asis[0], float), np.asarray(asis[1], float)       # left, right
    P = np.asarray(L["SU"], float)                                      # upper pubic symphysis
    ex = B - A; ex /= np.linalg.norm(ex)
    nz = np.cross(ex, P - A)                                            # normal of the APP
    nz /= np.linalg.norm(nz)
    if nz[2] < 0:
        nz = -nz                                                        # point anteriorly
    ey = np.cross(nz, ex); ey /= np.linalg.norm(ey)
    if ey[1] < 0:
        ey = -ey; ex = np.cross(ey, nz)
    return (A + B + P) / 3.0, ex, ey, nz


def acetabulum_app(S, side, frame):
    """Acetabular orientation and size in the anterior pelvic plane.
    Rule: c = the femoral-head sphere centre (DM.femur_metrics); the SOCKET = the hip-bone vertices whose distance to c
    is between 0.55 r and 1.20 r and whose direction from c is not beyond the rim (the lateral free surface is dropped);
    the socket AXIS = the mean unit direction from c over the socket (for a hemisphere that mean is the axis);
    anteversion = the angle of the axis from the sagittal plane measured in the APP transverse plane;
    inclination  = the angle of the axis from the transverse axis measured in the APP coronal plane;
    diameter = twice the 90th percentile radius of the socket about its own axis.
    Literature (adults, CT, measured in the anterior pelvic plane): anteversion 15.3 +- 5.7 deg overall, female
    17.5 +- 5.6 / male 13.2 +- 4.9, inclination 37.5 +- 3.9 (female 36.7 +- 3.7 / male 38.3 +- 3.9), left-right
    asymmetry not significant -- Kim et al. 2021, Medicine 100(15):e25445, doi:10.1097/MD.0000000000025445, 200
    acetabula of 100 healthy young adults; anatomic anteversion female 23.4 (11.5-34.5) / male 20.0 (7.5-34.5) deg --
    Sautet et al. 2017, Orthop Traumatol Surg Res 104(3):347-351, doi:10.1016/j.otsr.2017.10.006, 150 healthy pelvises;
    anteversion 23 +- 5 (90 % central range 14-31), abduction 39 +- 4 deg -- Stem et al. 2006, Skeletal Radiol
    35(6):385-9, doi:10.1007/s00256-006-0086-4, 100 pelvic CT.  (All read from PubMed in Q299.)"""
    o, ex, ey, ez = frame
    h = DM.bone(S, f"hip_bone_{side}")
    fm = DM.femur_metrics(S, side)
    if h is None or not fm:
        return {}
    c = np.array(fm["head_centre"], float); r = fm["femoral_head_diameter_mm"] / 2.0
    lat = ex if side == "r" else -ex                                     # outward direction on this side
    v = h.vertices
    rel = v - c; d = np.linalg.norm(rel, axis=1)
    m = (d > 0.50 * r) & (d < 1.70 * r)      # wide enough to still find the socket when the head is not seated in it
    if m.sum() < 40:
        return {"socket_points": int(m.sum()),
                "note": "the acetabular surface could not be isolated on this page: fewer than 40 hip-bone vertices lie in the shell around the femoral-head centre"}
    dirs = rel[m] / d[m][:, None]
    cup = dirs[dirs @ lat < 0.60]                                        # drop the free lateral surface beyond the rim
    if len(cup) < 40:
        cup = dirs
    n = -cup.mean(0); n /= np.linalg.norm(n)   # the cup SURFACE faces medially; the acetabular axis is the opposite
    nl, ns, na = float(n @ lat), float(n @ ey), float(n @ ez)
    ante = float(np.degrees(np.arctan2(na, abs(nl))))
    incl = float(np.degrees(np.arctan2(-ns, abs(nl))))
    sock = v[m][dirs @ lat < 0.60] if len(cup) != len(dirs) else v[m]
    rr = np.linalg.norm(np.cross(sock - c, n), axis=1)
    return dict(acetabular_anteversion_app_deg=round(ante, 1), acetabular_inclination_app_deg=round(incl, 1),
                acetabular_diameter_mm=round(2 * float(np.quantile(rr, 0.90)), 1),
                socket_axis=np.round(n, 3).tolist(), socket_points=int(len(sock)),
                precision_note="Comparable with the literature for ORIENTATION only. Measured in the anterior pelvic plane of this page, the inclination of all six pages lands within 2 SD of 37.5 +- 3.9 deg (Kim 2021) and the anteversion of five of the six within 2 SD of the sex-specific value, which is what makes the rule credible for orientation. The acetabular DIAMETER from this rule is an OVER-estimate and carries no verdict: the selection shell reaches to 1.7 x the femoral-head radius so that an unseated head can still find its socket, and it therefore includes peri-acetabular bone. The same applies to the socket sphere fit in `seating_*` (fitted radius 30-35 mm against a femoral-head radius near 23 mm, fit rms 2.3-4.3 mm): it is recorded, not claimed. Q250 found the same about the greater sciatic notch on the 1.9 k-vertex Z hip meshes.",
                femoral_head_diameter_mm=fm["femoral_head_diameter_mm"], head_centre=fm["head_centre"])


def acetabulum(S, side):
    """acetabular rim + centre: the lunate surface is the concave lateral socket of the hip bone around the femoral head.
    Rule: take the femoral-head sphere centre c (DM.femur_metrics), keep hip-bone vertices within r+8 mm of c whose outward
    normal from c points laterally; fit a plane to the subset at radius > 0.9*(r+4) -> rim plane.  Diameter = 2x the rms
    radius of those rim points about their centroid.  Version = angle of the rim normal to the sagittal plane, measured in
    the transverse plane (anteversion positive = rim faces anteriorly)."""
    h = DM.bone(S, f"hip_bone_{side}")
    fm = DM.femur_metrics(S, side)
    if h is None or not fm:
        return {}
    c = np.array(fm["head_centre"]); r = fm["femoral_head_diameter_mm"] / 2.0
    v = h.vertices
    d = np.linalg.norm(v - c, axis=1)
    near = v[(d > r * 0.55) & (d < r + 12.0)]
    if len(near) < 60:
        return {}
    sgn = 1.0 if side == "r" else -1.0
    # keep the socket wall: points whose direction from c is lateral-ish or within the cup
    dirs = (near - c) / np.linalg.norm(near - c, axis=1)[:, None]
    cup = near[dirs[:, 0] * sgn < 0.45]        # exclude the lateral free surface beyond the rim
    if len(cup) < 60:
        cup = near
    dc = np.linalg.norm(cup - c, axis=1)
    rim = cup[dc > np.quantile(dc, 0.80)]
    rc, rn = fit_plane(rim)
    if rn[0] * sgn < 0:
        rn = -rn
    rad = np.linalg.norm(rim - rc, axis=1)
    diam = 2.0 * float(np.sqrt((rad ** 2).mean()))
    # anteversion: project the rim normal on the transverse (x,z) plane, angle from the +-x (lateral) direction
    t = np.array([rn[0], 0.0, rn[2]])
    ver = float(np.degrees(np.arctan2(rn[2], abs(rn[0]))))
    inc = float(np.degrees(np.arctan2(abs(rn[1]), np.linalg.norm(t)))) if np.linalg.norm(t) else None
    return dict(acetabular_diameter_mm=round(diam, 1), acetabular_version_deg=round(ver, 1),
                acetabular_inclination_from_transverse_deg=round(inc, 1) if inc is not None else None,
                centre=rc.round(1).tolist(), femoral_head_diameter_mm=fm["femoral_head_diameter_mm"])


def iliac_crest(S):
    """bi-iliac (bicristal) breadth = the widest transverse distance between the two iliac crests, each crest being the
    top 12 % of its hip bone in y; ASIS breadth = the two most anterior points of that top-45 mm slab."""
    hl, hr = DM.bone(S, "hip_bone_l"), DM.bone(S, "hip_bone_r")
    out = {}
    xs = []
    asis = []
    for h, sgn in ((hl, -1), (hr, +1)):
        v = h.vertices
        crest = v[v[:, 1] > v[:, 1].max() - 0.12 * np.ptp(v[:, 1])]
        xs.append(crest[:, 0].min() if sgn < 0 else crest[:, 0].max())
        top = v[v[:, 1] > v[:, 1].max() - 45]
        asis.append(top[np.argmax(top[:, 2])])
    out["bicristal_mm"] = round(float(xs[1] - xs[0]), 1)
    out["asis_breadth_mm"] = round(float(abs(asis[1][0] - asis[0][0])), 1)
    out["asis_l"] = np.round(asis[0], 1).tolist(); out["asis_r"] = np.round(asis[1], 1).tolist()
    return out


def symphysis(S):
    L, hl, hr, sa = DM.pelvis_landmarks(S)
    SU, SL = L["SU"], L["SL"]
    h = float(np.linalg.norm(SU - SL))
    # width of the symphyseal gap: nearest-point distance between the two medial pubic faces
    from scipy.spatial import cKDTree
    gaps = []
    for a, b in ((hl, hr), (hr, hl)):
        va = a.vertices; vb = b.vertices
        sel = va[(np.abs(va[:, 1] - 0.5 * (SU[1] + SL[1])) < 0.6 * h) & (np.abs(va[:, 2] - 0.5 * (SU[2] + SL[2])) < 25) & (np.abs(va[:, 0]) < 14)]
        if len(sel) < 5:
            continue
        gaps.append(float(np.median(cKDTree(vb).query(sel)[0])))
    return dict(symphysis_height_mm=round(h, 1), symphyseal_gap_mm=round(float(np.mean(gaps)), 1) if gaps else None,
                SU=SU.round(1).tolist(), SL=SL.round(1).tolist())


def interspinous(S):
    L, hl, hr, sa = DM.pelvis_landmarks(S)
    sp = []
    for h in (hl, hr):
        v = h.vertices; ty = v[:, 1].min(); zmid = np.median(v[:, 2])
        m = (v[:, 1] > ty + 20) & (v[:, 1] < ty + 70) & (v[:, 2] < zmid)
        c = v[m]
        sp.append(c[np.argmin(np.abs(c[:, 0]))])
    return dict(interspinous_mm=round(float(abs(sp[0][0] - sp[1][0])), 1),
                spine_l=np.round(sp[0], 1).tolist(), spine_r=np.round(sp[1], 1).tolist())


def obstetric_conjugate(S):
    L, hl, hr, sa = DM.pelvis_landmarks(S)
    P = L["P"]
    pub = np.vstack([hl.vertices, hr.vertices])
    near = pub[np.abs(pub[:, 0]) < 12]
    return dict(obstetric_conjugate_mm=round(float(np.linalg.norm(near - P, axis=1).min()), 1), promontory=P.round(1).tolist())


def whole_body(S):
    """stature proxy and the pelvis-to-body proportions the owner would see."""
    sk = [x for x in S if x["sys"] == "skin" or x["id"] == "skin"]
    out = {}
    if sk:
        V = np.vstack([x["v"] for x in sk])
        out["skin_bbox_mm"] = np.round(np.ptp(V, 0), 1).tolist()
        out["skin_y_range"] = [round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)]
    allb = [x for x in S if x["sys"] == "bone"]
    if allb:
        V = np.vstack([x["v"] for x in allb])
        out["skeleton_height_mm"] = round(float(np.ptp(V[:, 1])), 1)
    return out


def measure(key):
    S = load(key)
    res = {"page": key, "label": C.PAGES[key][3], "n_structures": len(S)}
    res.update(DM.inlet(S))
    res.update(DM.outlet_and_subpubic(S))
    res.update(DM.sacrum_metrics(S))
    res.update(DM.pelvis_size(S))
    res.update(DM.shoulder_hip(S))
    res.update(DM.ischiopubic(S))
    res.update(DM.sciatic_notch(S))
    res.update(interspinous(S))
    res.update(obstetric_conjugate(S))
    res.update(iliac_crest(S))
    res["symphysis"] = symphysis(S)
    fr = app_frame(S)
    res["app_frame"] = dict(origin=np.round(fr[0], 1).tolist(), ex=np.round(fr[1], 3).tolist(),
                            ey=np.round(fr[2], 3).tolist(), ez=np.round(fr[3], 3).tolist())
    for s in "lr":
        res["acetabulum_" + s] = acetabulum(S, s)
        res["acetabulum_app_" + s] = acetabulum_app(S, s, fr)
        res["femur_" + s] = DM.femur_metrics(S, s)
    # how well is each femoral head seated in its own acetabulum?  (Q250 left the Combined pages' femora unseated)
    for s in "lr":
        a = res.get("acetabulum_app_" + s) or {}
        if a.get("head_centre") and a.get("acetabular_diameter_mm"):
            ac = DM.bone(S, f"hip_bone_{s}")
            c = np.array(a["head_centre"], float)
            vv = ac.vertices; dd = np.linalg.norm(vv - c, axis=1)
            rr = a["femoral_head_diameter_mm"] / 2.0
            sock = vv[(dd > 0.50 * rr) & (dd < 1.70 * rr)]
            if len(sock) > 20:
                # the socket's own sphere centre: least squares on the cup points
                cc, rad, rms = DM.fit_sphere(sock)
                res["seating_" + s] = dict(socket_centre=np.round(cc, 1).tolist(), socket_radius_mm=round(float(rad), 1),
                                           socket_fit_rms_mm=round(rms, 2),
                                           head_to_socket_centre_mm=round(float(np.linalg.norm(c - cc)), 2),
                                           head_lateral_offset_mm=round(float((c - cc) @ (fr[1] if s == "r" else -fr[1])), 2))
    # femoral-head separation and its ratio to pelvis width
    try:
        cl = np.array(res["femur_l"]["head_centre"]); cr = np.array(res["femur_r"]["head_centre"])
        res["interfemoral_head_mm"] = round(float(abs(cr[0] - cl[0])), 1)
        res["bicristal_over_interfemoral"] = round(res["bicristal_mm"] / res["interfemoral_head_mm"], 3)
    except Exception:
        pass
    bia = res.get("biacromial_mm")
    if bia:
        res["bicristal_over_biacromial"] = round(res["bicristal_mm"] / bia, 3)
    res.update(whole_body(S))
    if res.get("skeleton_height_mm"):
        res["bicristal_over_skeleton_height_pct"] = round(100 * res["bicristal_mm"] / res["skeleton_height_mm"], 2)
        res["pelvic_height_over_skeleton_height_pct"] = round(100 * res["pelvic_height_mm"] / res["skeleton_height_mm"], 2)
    return res


if __name__ == "__main__":
    keys = KEYS if sys.argv[1:] == ["all"] else sys.argv[1:]
    out = {}
    if OUT.exists():
        try:
            out = json.loads(OUT.read_text())
        except Exception:
            out = {}
    out.setdefault("_README", ["Q299 pelvis proportions on the shipped meshes; scripts/anatomy/q299/pelvis299.py"])
    out.setdefault("pages", {})
    for k in keys:
        print("==", k, flush=True)
        out["pages"][k] = measure(k)
        print(json.dumps(out["pages"][k], indent=1, default=float)[:2500], flush=True)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
