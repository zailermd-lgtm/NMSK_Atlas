#!/usr/bin/env python3
"""Q388 verifier: nerve courses on the Base pages against published anatomy (offline, on the page data; no browser).

    python3 scripts/anatomy/q388/verify_nerve_course_q388.py                         # both Base pages in build/q309
    python3 scripts/anatomy/q388/verify_nerve_course_q388.py --page-dir DIR [--page-dir DIR2] [--json OUT] [--only sciatic]

One line per (page, nerve, side, check):  Q388_NERVES_OK | Q388_NERVES_FAIL | Q388_NERVES_NA  <page> <nerve>_<side> <check>:
<measured> (literature tolerance; source). NA = the page has no mesh to measure (said, never passed). The last line is
Q388_NERVES_OK when no check FAILs, else Q388_NERVES_FAIL with the count. Frame: mm, +y up, +z anterior, +x body right.
Tolerances are the cited mean +/- 2 SD, or the cited range, or (relations) a stated geometric rule; every one names its
source. Books are cited as knowledge only (facts + page), PubMed sources by DOI.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib388 as L  # noqa: E402
from reroute_sciatic_q388 import occupancy, GRID  # noqa: E402

REPO = L.REPO
SRC = {
    "miller": "Miller SL et al. 2007, J Bone Joint Surg Am 89:44-48, doi:10.2106/JBJS.F.00094 (SN 12 +/- 2 mm from the most lateral aspect of the ischial tuberosity, 14 cadavers)",
    "leite": "Leite MJ et al. 2022, Hip Int 32:510-515, doi:10.1177/1120700020966255 (ischiofemoral space: SN-IT 15 +/- 6 mm, SN-LT 11 +/- 7 mm, 24 hemipelves)",
    "wan": "Wan-Ae-Loh P et al. 2020, Folia Morphol 79:681-689, doi:10.5603/FM.a2019.0140 (SN crosses the IT-GT line at 37.87 +/- 8.27 % from IT, 204 sides)",
    "vloka": "Vloka JD et al. 2001, Anesth Analg 92:215-217, doi:10.1097/00000539-200101000-00041 (division 60.5 +/- 27.0 mm, range 0-115, above the popliteal crease); Saleh HA et al. 2009, Folia Morphol 68:256-259 (range 50-180 mm)",
    "bruhn": "Bruhn J et al. 2009, Acta Anaesthesiol Scand 53:921-925, doi:10.1111/j.1399-6576.2009.01982.x (infragluteal SN at the ventral end of the medial-border tendon of the long head of biceps)",
    "mannan_glut": "Mannan, Regional Dissection and Surface Anatomy, p. 228-229 (gluteal region: SN below piriformis, over the gemelli / obturator internus and quadratus femoris; on adductor magnus in the thigh) -- knowledge only",
    "mannan_surf": "Mannan, Regional Dissection and Surface Anatomy, p. 539 (surface lines: SN, tibial n. midway between medial malleolus and tendo calcaneus; common peroneal n. behind the head of the fibula, rolled against the bone) -- knowledge only",
    "teo": "Teo HLT et al. 2020, Knee Surg Relat Res 32:23, doi:10.1186/s43019-020-00039-2 (CPN crosses the posterior border of the fibular neck 20.7 +/- 1.0 mm from the fibular head tip); corroborating range 14-50 mm: Baruah 2018 doi:10.1016/j.jcot.2018.05.002, Dearden 2015 doi:10.1007/s11751-015-0225-3, Fongsri 2026 doi:10.1097/GOX.0000000000007589",
    "carlan": "Carlan D et al. 2007, J Hand Surg Am 32:1177-1182, doi:10.1016/j.jhsa.2006.07.001 (radial n. in direct contact with the posterior humerus from 17.1 +/- 1.6 to 10.9 +/- 1.5 cm proximal to the lateral epicondyle)",
    "macchi": "Macchi V et al. 2007, Clin Anat 20:400-406, doi:10.1002/ca.20402 (MCN enters coracobrachialis 7.7 +/- 2.5 cm from the coracoid); Clavert P et al. 2009, Surg Radiol Anat 31:49-53, doi:10.1007/s00276-008-0426-2 (55.7 mm from the coracoid tip)",
    "cetik": "Cetik O et al. 2006, J Bone Joint Surg Am 88:2395-2399, doi:10.2106/JBJS.E.01375 (axillary n. in deltoid 6.08 cm (anterior) / 4.87 cm (posterior) below the acromion); Samart 2014 J Med Assoc Thai 97 S8:S27 (57.9 mm, arm adducted 30 deg)",
    "punja": "Punja R et al. 2022, Ann Med Surg 74:103259, doi:10.1016/j.amsu.2022.103259 (ulnar n. divides 8.9 +/- 2.5 mm from the pisiform)",
    "gray_rel": "Gray's Anatomy (relations; knowledge only): ulnar n. behind the medial epicondyle; femoral n. lateral to the femoral artery under the inguinal ligament; tibial n. superficial (posterior) to the popliteal vessels; deep fibular n. with the anterior tibial artery; trunks of the brachial plexus between scalenus anterior and medius; saphenous n. with the femoral artery in the adductor canal",
}


def sid(b, s):
    return f"{b}_{s}"


def depth_in(sc, p, near=12.0):
    """depth (mm) of point p inside the muscle / bone occupancy of its horizontal slice (0 = outside)."""
    ids = sc.near_ids(p, near)
    if not ids:
        return 0.0, []
    xs, zs, occ = occupancy(sc, p[1], p[0], p[2], ids)
    dep = distance_transform_edt(occ) * GRID
    c = occ.shape[0] // 2, occ.shape[1] // 2
    return float(dep[c]), [k for k, _ in L.inside_ids(sc, p)] if dep[c] > 0 else []


class Ctx:
    def __init__(self, D, sc, s):
        self.D, self.sc, self.s, self.sg = D, sc, s, L.SG[s]
        self._c = {}

    def C(self, base, n=120):
        k = sid(base, self.s)
        if k not in self._c:
            self._c[k] = L.centreline(self.D[k], n=n) if k in self.D else None
            if self._c[k] is not None:
                from scipy.ndimage import gaussian_filter1d
                self._c[k] = gaussian_filter1d(self._c[k], 1.5, axis=0, mode="nearest")
        return self._c[k]

    def V(self, base):
        k = sid(base, self.s)
        return self.D[k]["V"].astype(float) if k in self.D else None


def res(check, measured, tol, ok, src, note=""):
    return dict(check=check, measured=measured, tol=tol, ok=ok, src=src, note=note)


# ------------------------------------------------------------------------------------------------ sciatic
def it_blob(hip):
    lo = hip[np.argmin(hip[:, 1])]
    return lo, hip[(np.linalg.norm(hip - lo, axis=1) < 55) & (hip[:, 1] < lo[1] + 40)]


def sciatic(cx):
    out = []
    C = cx.C("sciatic_n", 160); N = cx.V("sciatic_n"); hip = cx.V("hip_bone"); fem = cx.V("femur")
    if C is None:
        return [res("present", None, None, None, "", "no sciatic mesh")]
    sg = cx.sg
    lo, blob = it_blob(hip)
    # (1) IT lateral gap over the tuberosity's lower 2/3 (where the hamstrings arise and Miller measured)
    gaps = []
    for y in np.arange(lo[1] + 4, lo[1] + 28, 3.0):
        hs = L.slab(blob, y, 1.5); ns = L.slab(N, y, 1.5)
        if len(hs) and len(ns):
            gaps.append(float((sg * ns[:, 0]).min() - (sg * hs[:, 0]).max()))
    g = float(np.median(gaps)) if gaps else None
    out.append(res("IT_gap_mm", g, [8, 16], g is not None and 8 <= g <= 16, SRC["miller"],
                   "nerve medial edge minus the tuberosity's lateral margin, median over the tuberosity's lower 24 mm; "
                   "negative = nerve medial of the margin, i.e. behind the tuberosity"))
    # (1b) 3-D distance nerve surface - hip bone at the tuberosity
    ns = N[(N[:, 1] > lo[1]) & (N[:, 1] < lo[1] + 30)]
    dmin = float(cKDTree(hip).query(ns)[0].min()) if len(ns) else None
    out.append(res("IT_3d_min_mm", dmin, [3, 27], dmin is not None and 3 <= dmin <= 27, SRC["leite"],
                   "minimum nerve-surface to hip-bone distance over the tuberosity (Leite mean +/- 2 SD)"))
    # (2) on quadratus femoris: anterior first hit at the QF mid-level is QF (not the hamstring origin / bone)
    qf = cx.V("quadratus_femoris")
    yq = float(np.median(qf[:, 1])); i = int(np.argmin(np.abs(C[:, 1] - yq)))
    (k, dd), = cx.sc.rays(C[i], [[0, 0, 1]], rad=60)[0][:1]
    out.append(res("on_QF", k, "quadratus_femoris_<s> first muscle anterior", k == sid("quadratus_femoris", cx.s),
                   SRC["mannan_glut"], f"first structure anterior to the centre at y {yq:.0f}: {k} at {dd if dd is None else round(dd, 1)} mm"))
    # (3) IT-GT line crossing, posterior (x-y) projection, Q146 landmark convention
    top = fem[fem[:, 1] > fem[:, 1].max() - 40]; gt = top[np.argmax(sg * top[:, 0])]
    a2, b2 = lo[[0, 1]], gt[[0, 1]]
    u = b2 - a2; Lu = np.linalg.norm(u); u /= Lu; nrm = np.array([-u[1], u[0]])
    P2 = C[:, [0, 1]]; sd = (P2 - a2) @ nrm
    j = np.where(np.sign(sd[:-1]) != np.sign(sd[1:]))[0]
    pct = None
    if len(j):
        j = j[0]; t = sd[j] / (sd[j] - sd[j + 1]); X = P2[j] + t * (P2[j + 1] - P2[j])
        pct = float((X - a2) @ u / Lu * 100)
    out.append(res("ITGT_pct", pct, [21.3, 54.4], pct is not None and 21.3 <= pct <= 54.4, SRC["wan"] + "; " + SRC["mannan_surf"],
                   f"posterior-view crossing of the line from the lowest hip-bone vertex to the most lateral GT vertex (line {Lu:.0f} mm)"))
    # (4) thigh: centre not inside a muscle (IT level -> division)
    S = L.arclen(C); bad = []
    for i in range(len(C)):
        if C[i, 1] < lo[1] + 10 and S[-1] - S[i] > 12 and i % 2 == 0:
            dep, ins = depth_in(cx.sc, C[i])
            if dep > 1.5:
                bad.append((round(float(C[i, 1])), ins, round(dep, 1)))
    out.append(res("thigh_centre_in_muscle_stations", len(bad), "<= 1 station deeper than 1.5 mm", len(bad) <= 1,
                   SRC["mannan_glut"] + "; " + SRC["bruhn"], f"{bad[:6]}"))
    # (5) division height above the knee joint line (lowest femur vertex; the crease is taken at the joint line -- convention)
    h = float(C[-1, 1] - fem[:, 1].min())
    out.append(res("division_above_joint_mm", h, [0, 180], 0 <= h <= 180, SRC["vloka"],
                   "end of the sciatic mesh (tibial / common fibular start) above the femur's lowest point"))
    # (6) distance to the femur at the lesser trochanter level (ischiofemoral space)
    ftop = fem[:, 1].max(); w = fem[(fem[:, 1] < ftop - 45) & (fem[:, 1] > ftop - 95)]
    lt = w[np.argmin(sg * w[:, 0])]
    ns = L.slab(N, lt[1], 10)
    dlt = float(cKDTree(fem).query(ns)[0].min()) if len(ns) else None
    out.append(res("LT_level_femur_mm", dlt, [0, 25], dlt is not None and dlt <= 25, SRC["leite"],
                   f"nerve surface to femur within 10 mm of the lesser-trochanter level (y {lt[1]:.0f})"))
    return out


# ------------------------------------------------------------------------------------------------ other nerves
def common_fibular(cx):
    C = cx.C("common_fibular_n"); fib = cx.V("fibula")
    if C is None or fib is None:
        return [res("present", None, None, None, "", "missing mesh")]
    tip = fib[np.argmax(fib[:, 1])]
    N = cx.V("common_fibular_n")
    w = N[(N[:, 1] < tip[1]) & (N[:, 1] > tip[1] - 60)]
    d, _ = cKDTree(fib).query(w)
    p = w[np.argmin(d)]
    dy = float(tip[1] - p[1])
    return [res("neck_crossing_below_tip_mm", dy, [14, 50], 14 <= dy <= 50, SRC["teo"],
                f"closest nerve-to-fibula point {d.min():.1f} mm from bone, {dy:.0f} mm below the head tip"),
            res("neck_contact_mm", float(d.min()), [0, 5], d.min() <= 5, SRC["mannan_surf"], "nerve against the fibular neck")]


def epicondyles(hum, sg):
    lo = hum[:, 1].min(); dist = hum[hum[:, 1] < lo + 40]
    le = dist[np.argmax(sg * dist[:, 0])]; me = dist[np.argmin(sg * dist[:, 0])]
    return le, me


def radial(cx):
    N = cx.V("radial_n"); hum = cx.V("humerus")
    if N is None:
        return [res("present", None, None, None, "", "missing mesh")]
    le, me = epicondyles(hum, cx.sg)
    t = cKDTree(hum); d, _ = t.query(N)
    win = (N[:, 1] > le[1] + 109) & (N[:, 1] < le[1] + 171)
    dmin = float(d[win].min()) if win.any() else None
    contact = N[d <= 3.0]
    span = (float(contact[:, 1].max() - le[1]), float(contact[:, 1].min() - le[1])) if len(contact) else None
    return [res("groove_contact_mm", dmin, [0, 3], dmin is not None and dmin <= 3, SRC["carlan"],
                f"min nerve-humerus distance 10.9-17.1 cm above the lateral epicondyle; contact (<=3 mm) span above LE: {span}")]


def ulnar(cx):
    out = []
    N = cx.V("ulnar_n"); hum = cx.V("humerus")
    if N is None:
        return [res("present", None, None, None, "", "missing mesh")]
    le, me = epicondyles(hum, cx.sg)
    s = L.slab(N, me[1], 6)
    if len(s):
        c = s.mean(0)
        d = float(cKDTree(hum).query(s)[0].min())
        ok = c[2] < me[2] and d <= 8
        out.append(res("behind_medial_epicondyle", {"z_nerve_minus_ME": round(float(c[2] - me[2]), 1), "bone_mm": round(d, 1)},
                       "posterior to ME and <= 8 mm from the humerus", ok, SRC["gray_rel"]))
    deep = cx.V("ulnar_n_deep_branch"); pis = cx.V("zan_pisiform_bone") if sid("zan_pisiform_bone", cx.s) in cx.D else None
    if deep is not None and pis is not None:
        st = deep[np.argmax(deep[:, 1])]
        dd = float(np.linalg.norm(st - pis.mean(0)))
        out.append(res("division_from_pisiform_mm", dd, [3.9, 13.9], 3.9 <= dd <= 13.9, SRC["punja"],
                       "top of the deep-branch mesh to the pisiform centroid"))
    return out


def coracoid_tip(scap, sg):
    a = scap[scap[:, 2] > np.percentile(scap[:, 2], 97)]
    return a[np.argmax(a[:, 2])]


def musculocutaneous(cx):
    C = cx.C("musculocutaneous_n"); cb = sid("coracobrachialis", cx.s)
    if C is None or cb not in cx.D:
        return [res("present", None, None, None, "", "missing mesh")]
    w = np.abs(L.winding(cx.D[cb]["V"], cx.D[cb]["F"], C)) > 0.5
    tip = coracoid_tip(cx.V("scapula"), cx.sg)
    if not w.any():
        dmin = float(cKDTree(cx.D[cb]["V"]).query(C)[0].min())
        return [res("pierces_coracobrachialis", False, "enters CB", False, SRC["macchi"], f"never inside CB; closest {dmin:.1f} mm")]
    i = int(np.argmax(w)); dd = float(np.linalg.norm(C[i] - tip))
    return [res("CB_entry_from_coracoid_mm", dd, [27, 127], 27 <= dd <= 127, SRC["macchi"],
                f"first centreline point inside coracobrachialis, 3-D distance to the coracoid tip (most anterior scapula vertex)")]


def axillary(cx):
    N = cx.V("axillary_n"); scap = cx.V("scapula")
    if N is None:
        return [res("present", None, None, None, "", "missing mesh")]
    parts = [sid(b, cx.s) for b in ("zan_acromial_part_of_deltoid_muscle", "zan_scapular_spinal_part_of_deltoid_muscle",
                                    "zan_clavicular_part_of_deltoid_muscle") if sid(b, cx.s) in cx.D]
    acr = scap[np.argmax(cx.sg * scap[:, 0])]
    ins = np.zeros(len(N), bool)
    for k in parts:
        ins |= np.abs(L.winding(cx.D[k]["V"], cx.D[k]["F"], N[::4])).repeat(4)[:len(N)] > 0.5
    if not ins.any():
        return [res("in_deltoid_below_acromion_mm", None, [40, 70], False, SRC["cetik"], "no axillary-nerve vertex inside the deltoid parts")]
    dy = float(acr[1] - np.median(N[ins, 1]))
    return [res("in_deltoid_below_acromion_mm", dy, [40, 70], 40 <= dy <= 70, SRC["cetik"],
                "median height of the nerve's intra-deltoid part below the most lateral acromion vertex (+/- 10 mm around 49-61)")]


def femoral(cx):
    N = cx.V("femoral_n"); A = cx.V("zan_femoral_artery")
    if N is None or A is None:
        return [res("present", None, None, None, "", "missing mesh")]
    # level: the top of the femoral artery = where the external iliac artery passes under the inguinal ligament (definition)
    y = float(A[:, 1].max()) - 3
    a = L.slab(A, y, 3).mean(0); ns = L.slab(N, y, 3)
    if not len(ns):
        return [res("lateral_to_artery_mm", None, None, False, SRC["gray_rel"], f"no femoral-nerve section at y {y:.0f}")]
    n = ns.mean(0); dx = float(cx.sg * (n[0] - a[0]))
    return [res("lateral_to_artery_mm", dx, "> 0 (nerve lateral), centre-to-centre <= 30", 0 < dx <= 30, SRC["gray_rel"],
                f"3 mm below the top of the femoral artery (its passage under the inguinal ligament), y {y:.0f}")]


def tibial(cx):
    out = []
    N = cx.V("tibial_n"); pa = cx.V("zan_popliteal_artery"); fem = cx.V("femur")
    if N is None:
        return [res("present", None, None, None, "", "missing mesh")]
    if pa is not None:
        y = fem[:, 1].min() + 10
        ns, ps = L.slab(N, y, 3), L.slab(pa, y, 3)
        if len(ns) and len(ps):
            dz = float(ns[:, 2].mean() - ps[:, 2].mean())
            out.append(res("popliteal_posterior_to_artery_mm", dz, "< 0 (nerve posterior)", dz < 0, SRC["gray_rel"], f"y {y:.0f}"))
    tib = cx.V("tibia"); ct = cx.V("zan_calcaneal_tendon"); pta = cx.V("zan_posterior_tibial_artery")
    if tib is not None and ct is not None:
        bot = tib[tib[:, 1] < tib[:, 1].min() + 25]; mm = bot[np.argmin(cx.sg * bot[:, 0])]
        y = mm[1] + 15
        ns, cs = L.slab(N, y, 3), L.slab(ct, y, 3)
        if len(ns) and len(cs):
            n2, c2, m2 = ns.mean(0)[[0, 2]], cs.mean(0)[[0, 2]], mm[[0, 2]]
            u = c2 - m2; t = float((n2 - m2) @ u / (u @ u))
            out.append(res("ankle_MM_to_tendon_fraction", t, [0.25, 0.75], 0.25 <= t <= 0.75, SRC["mannan_surf"],
                           f"projection of the nerve between the medial-malleolus tip and the calcaneal tendon, y {y:.0f}"))
            if pta is not None and len(L.slab(pta, y, 3)):
                dz = float(ns[:, 2].mean() - L.slab(pta, y, 3)[:, 2].mean())
                out.append(res("ankle_posterior_to_PT_artery_mm", dz, "< 0", dz < 0, SRC["gray_rel"], f"y {y:.0f}"))
    return out


def near_dist(N, A, y, h=15.0):
    ns = N[np.abs(N[:, 1] - y) < h]
    return float(cKDTree(A).query(ns)[0].min()) if len(ns) else None


def deep_fibular(cx):
    N = cx.V("deep_fibular_n"); A = cx.V("zan_anterior_tibial_artery"); tib = cx.V("tibia")
    if N is None or A is None:
        return [res("present", None, None, None, "", "missing mesh")]
    y = 0.5 * (tib[:, 1].max() + tib[:, 1].min())
    d = near_dist(N, A, y)
    return [res("with_ant_tibial_artery_mm", d, "<= 6 (surface to surface, mid-leg +/- 15 mm)", d is not None and d <= 6,
                SRC["gray_rel"], f"y {y:.0f}; 6 mm is our convention for 'accompanies'")]


def saphenous(cx):
    N = cx.V("saphenous_n"); fem = cx.V("femur")
    arts = [v for v in (cx.V("zan_femoral_artery"), cx.V("zan_popliteal_artery")) if v is not None]
    if N is None or not arts:
        return [res("present", None, None, None, "", "missing mesh")]
    A = np.vstack(arts)
    y = fem[:, 1].max() - 0.6 * (fem[:, 1].max() - fem[:, 1].min())
    d = near_dist(N, A, y)
    return [res("with_femoral_artery_mm", d, "<= 10 (surface to surface, 60 % femur length +/- 15 mm)", d is not None and d <= 10,
                SRC["gray_rel"], f"y {y:.0f}; 10 mm is our convention for 'in the adductor canal with the artery'")]


def brachial_roots(cx):
    """roots of the plexus in the interscalene groove: at each 3 mm level where scalenus anterior, scalenus medius and the
    roots mesh all have a section, the roots (lateral of the scalenes' medial edge) come within 8 mm of BOTH muscles and
    their centroid is inside neither (a stated geometric rule for 'between')."""
    R = cx.V("zan_roots_of_brachial_plexus"); SA = cx.V("scalenus_anterior"); SM = cx.V("scalenus_medius")
    if R is None or SA is None or SM is None:
        return [res("roots_interscalene", None, None, None, "", "missing mesh")]
    ok = n = 0; bad = []
    for y in np.arange(max(R[:, 1].min(), SA[:, 1].min()), min(R[:, 1].max(), SA[:, 1].max()), 3.0):
        r, a, m = L.slab(R, y, 1.5), L.slab(SA, y, 1.5), L.slab(SM, y, 1.5)
        if not (len(r) and len(a) and len(m)):
            continue
        # only the part of the roots that lies within the scalenes' lateral extent (the groove), not the medial foramina
        xr = cx.sg * r[:, 0]; lo_x = min((cx.sg * a[:, 0]).min(), (cx.sg * m[:, 0]).min())
        r = r[xr >= lo_x]
        if not len(r):
            continue
        n += 1
        c = r.mean(0)
        ins = [k for k, _ in L.inside_ids(cx.sc, c) if "scalen" in k or "rib" in k]
        da = float(cKDTree(a).query(r)[0].min()); dm = float(cKDTree(m).query(r)[0].min())
        if da <= 8 and dm <= 8 and not ins:          # roots touch both scalenes = they lie in the groove between them
            ok += 1
        else:
            bad.append((round(float(y)), round(da, 1), round(dm, 1), ins))
    f = ok / n if n else None
    return [res("roots_between_SA_and_SM_fraction", f, ">= 0.7 of levels", f is not None and f >= 0.7, SRC["gray_rel"],
                f"{ok}/{n} levels; failing (y, to SA mm, to SM mm, inside): {bad[:8]}")]


def median(cx):
    """Base pages have no separate median trunk; the 'lateral root of the median nerve' mesh runs on to the hand (588 / 525
    mm) and is measured as the trunk's proxy (said on every line)."""
    k = sid("median_n", cx.s)
    proxy = sid("median_n_lateral_root", cx.s)
    if k not in cx.D and proxy not in cx.D:
        return [res("trunk_present", None, None, None, "", "no median mesh")]
    base = "median_n" if k in cx.D else "median_n_lateral_root"
    N = cx.V(base); hum = cx.V("humerus"); pt = cx.V("pronator_teres")
    le, me = epicondyles(hum, cx.sg)
    yie = 0.5 * (le[1] + me[1])
    d, _ = cKDTree(pt).query(N)
    near = N[(d <= 3.0) & (N[:, 1] < yie)]
    out = []
    if len(near):
        dd = float(yie - np.median(near[:, 1]))
        out.append(res("pronator_teres_passage_below_IE_mm", dd, [29.0, 71.8], 29.0 <= dd <= 71.8,
                       "Gurses IA et al. 2016, Orthop Traumatol Surg Res 102:1005-1008, doi:10.1016/j.otsr.2016.08.016 (50.4 +/- 10.7 mm from the interepicondylar line)",
                       f"{base} used as the trunk; median height of the nerve's stretch within 3 mm of pronator teres"))
    bb = sid("biceps_brachii", cx.s)
    C = cx.C(base, 120)
    arm = C[(C[:, 1] > yie + 40) & (C[:, 1] < hum[:, 1].max() - 40)]
    w = np.abs(L.winding(cx.D[bb]["V"], cx.D[bb]["F"], arm)) > 0.5
    seg = float(np.linalg.norm(np.diff(arm, axis=0), axis=1).mean()) if len(arm) > 1 else 0
    out.append(res("arm_centre_inside_biceps_mm", round(w.sum() * seg, 1), "0 (medial bicipital groove, outside the muscle)", w.sum() <= 1,
                   SRC["gray_rel"], f"{base}; the brachial artery mesh is also partly inside biceps on both pages (the muscle mesh overlaps the bundle)"))
    return out


NERVES = {"sciatic": sciatic, "common_fibular": common_fibular, "radial": radial, "ulnar": ulnar,
          "musculocutaneous": musculocutaneous, "axillary": axillary, "femoral": femoral, "tibial": tibial,
          "deep_fibular": deep_fibular, "saphenous": saphenous, "brachial_plexus_roots": brachial_roots, "median": median}


def run(page_dir, only=None):
    D = L.LazyPage(page_dir)
    sc = L.Scene(D)
    rows = []
    for s in "rl":
        cx = Ctx(D, sc, s)
        for name, fn in NERVES.items():
            if only and name not in only:
                continue
            try:
                rs = fn(cx)
            except Exception as e:  # a missing landmark is reported, not hidden
                rs = [res("error", None, None, False, "", f"{type(e).__name__}: {e}")]
            for r in rs:
                r.update(page=Path(page_dir).name, nerve=name, side=s)
                rows.append(r)
    return rows


def fmt(v):
    if isinstance(v, float):
        return f"{v:.1f}"
    return json.dumps(v) if isinstance(v, (dict, list)) else str(v)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", action="append")
    ap.add_argument("--json")
    ap.add_argument("--only", action="append")
    a = ap.parse_args(argv)
    dirs = a.page_dir or [str(REPO / "build/q309" / d) for d in L.PAGES.values()]
    rows, nfail = [], 0
    for d in dirs:
        for r in run(d, a.only):
            rows.append(r)
            tag = "Q388_NERVES_NA" if r["ok"] is None else ("Q388_NERVES_OK" if r["ok"] else "Q388_NERVES_FAIL")
            nfail += r["ok"] is False
            print(f"{tag} {r['page']} {r['nerve']}_{r['side']} {r['check']}: {fmt(r['measured'])} (tol {fmt(r['tol'])}) "
                  f"{r['note']}".rstrip())
    if a.json:
        Path(a.json).write_text(json.dumps(dict(rows=rows, sources=SRC), indent=1, default=float))
    print("Q388_NERVES_OK" if nfail == 0 else f"Q388_NERVES_FAIL {nfail} checks")
    return 0 if nfail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
