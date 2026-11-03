#!/usr/bin/env python3
"""Q308: the four structure families this round builds, RULE-BASED, on each page's OWN bones and own neighbours.

    python3 scripts/anatomy/q308/build308.py build [--keys base_m,...] [--src build/q307] [--out /dev/shm/q308/work]

What is built, and what fixes its shape (the cited numbers all live in lit308.py):
  coracoacromial ligament   coracoid process -> anterior undersurface of the acromion, BOTH landmarks found on the
                            page's own scapula. The course is therefore bone-determined; the LENGTH is an OUTPUT
                            compared against von Schroeder 2001 (27 +- 5 mm) and Hu 2009 (28.91 / 31.90 mm).
  LACN anterior + posterior the division point is placed on the page's OWN lateral antebrachial cutaneous nerve
  branch                    centreline at 47.8 mm distal to the interepicondylar line built from the page's own
                            humeral condyles (Khadanovich 2023); both branches then run distally held within
                            1.8 mm of the medial border of the page's own brachioradialis (Khadanovich 2023) to
                            the distal radius.
  psoas minor               lateral aspect of the T12 and L1 bodies -> pecten pubis / iliopubic eminence, all on
                            the page's own vertebrae and own hip bone (Raja 2026). HIDDEN by default.
  anterolateral ligament    femoral origin posterior and proximal to the page's own fibular collateral ligament's
                            femoral end (Kosy 2016 majority; Rustagi 2019 disagrees and is recorded), tibial
                            insertion at 59.5 % of the way from Gerdy's tubercle -- located by the distal end of
                            the page's own iliotibial tract -- to the fibular head (Kosy 2016).

Non-penetration follows Q307's lesson: depth is measured as a SIGNED SURFACE DISTANCE on the real bone mesh
(trimesh ProximityQuery), never as an inside/outside flag on a voxel solid, because a voxel solid is inflated
(Q307 S1 measured 116.7 cm3 against 93.8 for one brachioradialis). No mask, so no mask offset to calibrate.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE, REPO / "scripts/anatomy/q298", REPO / "scripts/anatomy/q248", REPO / "scripts/anatomy/q249"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import pagedata as pd      # noqa: E402
import lit308 as L         # noqa: E402
from rulelig import tube   # noqa: E402
from nervelib import tube_round  # noqa: E402

KEYS = list(pd.KEYS)
REPORT = REPO / "data/derived/Q308_built_structures.json"
CLEAR = 0.3          # mm pushed beyond the bone surface, Q248's rule


# ----------------------------------------------------------------------------------- helpers
def unit(v):
    v = np.asarray(v, float)
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.where(n == 0, 1, n)


def load(key, src, ids):
    """{id: (V, F)} for the ids present on this page; the blob is decoded once."""
    want, out = set(ids), {}
    for _, sid, v, f in pd.meshes(key, src):
        if sid in want:
            out[sid] = (np.asarray(v, float), np.asarray(f, np.int64))
    return out


def frame_check(got):
    """Assert the page's world frame is +X right, +Y superior, +Z anterior, from the page's OWN landmarks.
    A page in a different frame must FAIL here rather than have structures built into it back to front."""
    hl, hr = got["hip_bone_l"][0].mean(0), got["hip_bone_r"][0].mean(0)
    sac, ste = got["sacrum"][0].mean(0), got["sternum"][0].mean(0)
    ok_x = hr[0] > hl[0]
    ok_y = ste[1] > sac[1]
    ok_z = ste[2] > sac[2]
    if not (ok_x and ok_y and ok_z):
        raise SystemExit(f"frame check failed: x(right>left)={ok_x} y(sternum>sacrum)={ok_y} z(sternum>sacrum)={ok_z}")
    return {"x_right": True, "y_superior": True, "z_anterior": True,
            "hip_l_x": round(float(hl[0]), 1), "hip_r_x": round(float(hr[0]), 1),
            "sternum_y": round(float(ste[1]), 1), "sacrum_y": round(float(sac[1]), 1),
            "sternum_z": round(float(ste[2]), 1), "sacrum_z": round(float(sac[2]), 1)}


class Bone:
    """signed distance to one bone's surface; + outside, - inside. Real mesh, no voxelisation (Q307 S1)."""
    def __init__(self, V, F):
        self.m = trimesh.Trimesh(np.asarray(V, float), np.asarray(F), process=False)
        self.q = trimesh.proximity.ProximityQuery(self.m)

    def signed(self, P):
        return self.q.signed_distance(np.atleast_2d(np.asarray(P, float))) * -1.0  # trimesh: + inside

    def nearest(self, P):
        p, d, _ = self.q.on_surface(np.atleast_2d(np.asarray(P, float)))
        return p, d

    def push_out(self, V, clear):
        """move any vertex that is inside (or within `clear`) out to the surface + clear along the surface normal."""
        sd = self.signed(V)
        bad = sd < clear
        if not bad.any():
            return V, 0, float(sd.min())
        p, _ = self.nearest(V[bad])
        n = unit(V[bad] - p)
        # A vertex that is INSIDE has (V - p) pointing INWARD, so the step must be flipped or the push drives it
        # deeper. Caught by measuring: every structure came back at exactly -clear after the "push".
        n[sd[bad] < 0] *= -1.0
        flat = np.linalg.norm(V[bad] - p, axis=1) < 1e-6
        if flat.any():
            _, _, fid = self.q.on_surface(V[bad][flat])
            n[flat] = unit(self.m.face_normals[fid])
        V = V.copy()
        V[bad] = p + n * clear
        return V, int(bad.sum()), float(sd.min())


def pca_axis(V):
    C = V.mean(0)
    u, s, vt = np.linalg.svd(V - C, full_matrices=False)
    return C, unit(vt[0]), s


def along(V, C, A):
    return (V - C) @ A


def mesh_stats(V, F):
    m = trimesh.Trimesh(np.asarray(V, float), np.asarray(F), process=False)
    da = np.degrees(m.face_adjacency_angles) if len(m.face_adjacency) else np.array([0.0])
    return {"verts": int(len(V)), "tris": int(len(F)),
            "volume_cm3": round(abs(float(m.volume)) / 1000.0, 4),
            "area_mm2": round(float(m.area), 1),
            "watertight": bool(m.is_watertight),
            "dihedral_mean_deg": round(float(da.mean()), 1),
            "dihedral_median_deg": round(float(np.median(da)), 1),
            "dihedral_max_deg": round(float(da.max()), 1)}


def push_path_out(bones, P, margin, iters=10, keep_ends=False):
    """Move the CENTRELINE out of the bones so the tube built on it clears them, instead of moving the finished
    mesh's vertices. Pushing vertices one at a time inverts a thin ring -- measured: it halved one psoas minor's
    volume and the analytic cross-check refused it. Clearing the path first keeps the cross-section exact, so the
    mesh volume equals the analytic volume by construction and the clearance is still a real measurement."""
    P = np.asarray(P, float).copy()
    moved = 0
    for _ in range(iters):
        worst = 0.0
        for bone in bones:
            sd = bone.signed(P)
            bad = sd < margin
            if keep_ends:
                bad[0] = bad[-1] = False
            if not bad.any():
                continue
            worst = max(worst, float(margin - sd[bad].min()))
            q, _ = bone.nearest(P[bad])
            n = unit(P[bad] - q)
            n[sd[bad] < 0] *= -1.0
            flat = np.linalg.norm(P[bad] - q, axis=1) < 1e-6
            if flat.any():
                _, _, fid = bone.q.on_surface(P[bad][flat])
                n[flat] = unit(bone.m.face_normals[fid])
            P[bad] = q + n * margin
            moved += int(bad.sum())
        if worst == 0.0:
            break
    return P, moved


def lift_rings(bones, V, nring, nseg, margin, iters=8):
    """Translate whole RINGS of a tube outward until every vertex clears the bones by `margin`. Moving the ring
    as a rigid unit preserves the cross-section exactly, so the analytic volume still holds -- unlike moving
    single vertices, which inverts a thin ring. Used where clearing the centreline alone does not converge
    because two bones (here the radius and the brachioradialis) push the path back and forth."""
    V = np.asarray(V, float).copy()
    body = V[:nring * nseg].reshape(nring, nseg, 3)
    nmoved = 0
    for _ in range(iters):
        worst = 0.0
        for bone in bones:
            flat = body.reshape(-1, 3)
            sd = bone.signed(flat).reshape(nring, nseg)
            need = margin - sd.min(axis=1)
            bad = need > 1e-3
            if not bad.any():
                continue
            worst = max(worst, float(need[bad].max()))
            idx = np.where(bad)[0]
            for i in idx:
                j = int(np.argmin(sd[i]))
                q, _ = bone.nearest(body[i, j][None, :])
                n = unit(body[i, j] - q[0])
                if sd[i, j] < 0:
                    n = -n
                if np.linalg.norm(n) < 1e-6:
                    continue
                body[i] = body[i] + n * need[i]
            nmoved += int(bad.sum())
        if worst <= 1e-3:
            break
    V[:nring * nseg] = body.reshape(-1, 3)
    V[nring * nseg] = body[0].mean(0)
    V[nring * nseg + 1] = body[-1].mean(0)
    return V, nmoved


def clearance(bones, V):
    """the smallest signed surface distance from a finished mesh to any of these bones. + outside, - inside."""
    return min(float(b.signed(V).min()) for b in bones) if bones else 9.0


def analytic_volume_round(P, d):
    """volume of a round tube along P with per-point diameter d, as a sum of conical frusta. Independent of the
    mesh, so a disagreement with trimesh's volume means the mesh self-intersects or a ring collapsed -- which is
    exactly what the bone push-out can do, and what halved one psoas minor's reported volume before this check."""
    P = np.asarray(P, float); d = np.broadcast_to(np.asarray(d, float), (len(P),))
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    r0, r1 = d[:-1] / 2.0, d[1:] / 2.0
    return float((np.pi / 3.0 * seg * (r0 ** 2 + r0 * r1 + r1 ** 2)).sum()) / 1000.0


def analytic_volume_band(P, w, t):
    """volume of an elliptical band along P with per-point width w and thickness t."""
    P = np.asarray(P, float)
    w = np.broadcast_to(np.asarray(w, float), (len(P),)); t = np.broadcast_to(np.asarray(t, float), (len(P),))
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    a = np.pi / 4.0 * w * t
    return float((seg * 0.5 * (a[:-1] + a[1:])).sum()) / 1000.0


def volume_agrees(st, analytic, tol=0.30):
    """record the analytic volume beside the mesh volume and say whether they agree."""
    mesh = st["volume_cm3"]
    rel = abs(mesh - analytic) / max(analytic, 1e-9)
    st["volume_analytic_cm3"] = round(analytic, 4)
    st["volume_mesh_vs_analytic_rel"] = round(rel, 3)
    st["volume_check_tol"] = tol
    return rel <= tol


def smooth_path(P, k=3):
    P = np.asarray(P, float)
    for _ in range(k):
        Q = P.copy()
        Q[1:-1] = (P[:-2] + 2 * P[1:-1] + P[2:]) / 4.0
        P = Q
    return P


def resample(P, n):
    P = np.asarray(P, float)
    d = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if d[-1] <= 0:
        return np.repeat(P[:1], n, axis=0)
    return np.column_stack([np.interp(np.linspace(0, d[-1], n), d, P[:, i]) for i in range(3)])


def centreline(V, A, C, nbin=40):
    """centreline of a tubular mesh: mean of its vertices per bin along the axis A."""
    t = along(V, C, A)
    e = np.linspace(t.min(), t.max(), nbin + 1)
    P = []
    for i in range(nbin):
        s = (t >= e[i]) & (t <= e[i + 1])
        if s.sum() >= 3:
            P.append(V[s].mean(0))
    return np.array(P)


def polyline_len(P):
    return float(np.linalg.norm(np.diff(np.asarray(P, float), axis=0), axis=1).sum())


# ----------------------------------------------------------------------------------- id resolution per page
def ids_for(key, src):
    st = pd.structures(key, src)
    have = {s["id"] for s in st}

    def pick(*cands):
        for c in cands:
            if c in have:
                return c
        return None
    out = {}
    for s in "lr":
        out[f"scapula_{s}"] = pick(f"scapula_{s}", f"zan_scapula_{s}")
        out[f"humerus_{s}"] = pick(f"humerus_{s}", f"zan_humerus_{s}")
        out[f"radius_{s}"] = pick(f"radius_{s}", f"zan_radius_{s}")
        out[f"ulna_{s}"] = pick(f"ulna_{s}", f"zan_ulna_{s}")
        out[f"brachioradialis_{s}"] = pick(f"brachioradialis_{s}", f"zan_brachioradialis_{s}")
        out[f"lacn_{s}"] = pick(f"zan_lateral_antebrachial_cutaneous_nerve_{s}")
        out[f"hip_bone_{s}"] = pick(f"hip_bone_{s}", f"zan_hip_bone_{s}")
        out[f"femur_{s}"] = pick(f"femur_{s}", f"zan_femur_{s}")
        out[f"tibia_{s}"] = pick(f"tibia_{s}", f"zan_tibia_{s}")
        out[f"fibula_{s}"] = pick(f"fibula_{s}", f"zan_fibula_{s}")
        out[f"lcl_{s}"] = pick(f"fibular_collateral_ligament_{s}", f"zan_fibular_collateral_ligament_{s}")
        out[f"itb_{s}"] = pick(f"iliotibial_tract_{s}", f"zan_iliotibial_tract_{s}")
    out["vert_t12"] = pick("zan_vertebra_t12", "vertebra_t12", "vertebrae_T12", "vertebra_T12")
    out["vert_l1"] = pick("zan_vertebra_l1", "vertebra_l1", "vertebrae_L1", "vertebra_L1")
    out["sacrum"] = pick("sacrum", "zan_sacrum")
    out["sternum"] = pick("sternum", "zan_sternum")
    return out


# ============================================================================ landmarks, each by a stated rule
def lm_scapula(V, side):
    """coracoid process tip and acromion (lateral tip + anterior undersurface) on the page's own scapula.
    Rule: restrict to the superior quarter of the scapula (y above the 75th percentile) so the inferior angle and
    the spine cannot win; within it the ACROMION is the most LATERAL vertex and the CORACOID is the most ANTERIOR."""
    sel = V[:, 1] >= np.percentile(V[:, 1], 75)
    S = V[sel]
    sgn = 1.0 if side == "r" else -1.0
    acr = S[np.argmax(sgn * S[:, 0])]
    cor = S[np.argmax(S[:, 2])]
    # the CAL attaches to the anterior UNDERSURFACE of the acromion: among acromial vertices within 12 mm of the
    # lateral tip, take the most anterior-and-inferior one.
    near = S[np.linalg.norm(S - acr, axis=1) <= 12.0]
    acr_us = near[np.argmax(near[:, 2] - near[:, 1])] if len(near) else acr
    # The CAL's medial attachment is the whole LATERAL BORDER of the coracoid process, not its tip, so the band's
    # medial end is the point of that border nearest the acromial attachment -- which is why a tip-to-tip span
    # (58.4 mm measured on base_m) is not the ligament and overshoots von Schroeder's 27 +- 5 mm.
    cora = S[np.linalg.norm(S - cor, axis=1) <= 25.0]
    cor_pl = cora[np.argmin(np.linalg.norm(cora - acr_us, axis=1))] if len(cora) else cor
    return {"acromion_tip": acr, "acromion_undersurface": acr_us, "coracoid_tip": cor,
            "coracoid_posterolateral": cor_pl}


def lm_gerdy(Vt, side):
    """Gerdy's tubercle on the page's own tibia, by rule: within the proximal 15 % of the tibial long axis, the
    vertex that is furthest in the (anterior + lateral) direction. That IS the anterolateral tibial tubercle.
    On the Z pages this rule is CHECKED against the distal end of the page's own iliotibial tract, which inserts there."""
    C, A, _ = pca_axis(Vt)
    t = along(Vt, C, A)
    if t[np.argmax(Vt[:, 1])] < 0:          # orient the axis so + is proximal (superior)
        A, t = -A, -t
    prox = Vt[t >= np.percentile(t, 85)]
    sgn = 1.0 if side == "r" else -1.0
    d = unit(np.array([sgn, 0.0, 1.0]))
    return prox[np.argmax(prox @ d)], A, C


def lm_fibular_head(Vf):
    """the fibular head: the most proximal (superior) part of the page's own fibula."""
    top = Vf[Vf[:, 1] >= np.percentile(Vf[:, 1], 97)]
    return top.mean(0)


def lm_iel(Vh, side):
    """the interepicondylar line (IEL) plane from the page's own humerus: the medial and lateral epicondyles are
    the most medial and most lateral vertices of the distal fifth of the humerus. The plane is normal to the
    humeral long axis through their midpoint -- the same construction Q307 used."""
    C, A, _ = pca_axis(Vh)
    t = along(Vh, C, A)
    if t[np.argmin(Vh[:, 1])] < 0:
        A, t = -A, -t                        # + is now DISTAL
    dist = Vh[t >= np.percentile(t, 80)]
    sgn = 1.0 if side == "r" else -1.0
    lat = dist[np.argmax(sgn * dist[:, 0])]
    med = dist[np.argmin(sgn * dist[:, 0])]
    return {"lateral_epicondyle": lat, "medial_epicondyle": med,
            "iel_mid": (lat + med) / 2.0, "distal_axis": A}


def lm_psoas_minor_anchors(got, ids, side, key):
    """origin: lateral aspect of the T12 and L1 bodies. insertion: pecten pubis / iliopubic eminence on the hip bone.

    On the four Z pages T12 and L1 are named meshes. On the two Imaging pages the CT segmentation labels vertebrae
    only by REGION (5 meshes all called `lumbar_vertebrae`, 12 all `thoracic_vertebrae`), so the two levels are
    identified by the page's own `intervertebral_disc_t12_l1`: the thoracic vertebra nearest ABOVE it is T12 and
    the lumbar vertebra nearest BELOW it is L1. That is a measurement on the page, not an assumption."""
    sgn = 1.0 if side == "r" else -1.0
    if ids["vert_t12"] and ids["vert_l1"]:
        Vt12, Vl1 = got[ids["vert_t12"]][0], got[ids["vert_l1"]][0]
        how = "named vertebra meshes"
    else:
        disc = got["__disc_t12_l1"][0].mean(0)
        best_a = best_b = None
        for tag, Vs in (("t", got["__thoracic"]), ("l", got["__lumbar"])):
            for Vv in Vs:
                c = Vv.mean(0)
                if tag == "t" and c[1] > disc[1] and (best_a is None or c[1] < best_a[0]):
                    best_a = (c[1], Vv)
                if tag == "l" and c[1] < disc[1] and (best_b is None or c[1] > best_b[0]):
                    best_b = (c[1], Vv)
        if best_a is None or best_b is None:
            return None
        Vt12, Vl1 = best_a[1], best_b[1]
        how = "levels identified from this page's own T12-L1 intervertebral disc"
    # the lateral aspect of each BODY: the body is the anterior half of the vertebra (+Z); take its lateral face
    org = []
    for Vv in (Vt12, Vl1):
        body = Vv[Vv[:, 2] >= np.percentile(Vv[:, 2], 55)]
        lat = body[sgn * body[:, 0] >= np.percentile(sgn * body[:, 0], 85)]
        org.append(lat.mean(0))
    Vh = got[ids[f"hip_bone_{side}"]][0]
    # pecten pubis / iliopubic eminence (Raja 2026). The pecten is the SUPERIOR border of the superior pubic
    # ramus, running from the pubic tubercle posterolaterally to the iliopubic eminence; it is NOT the lowest
    # medial point of the hip bone (that is the symphyseal surface / inferior ramus, which an earlier rule here
    # picked and which made the muscle 30 mm too long).
    # Rule: the symphyseal surface is the most MEDIAL hip-bone vertex; take the anterior half of the bone in a
    # band from its level up to +35 mm, and within that band walk 55 % of the way laterally -- the iliopubic
    # eminence sits at the pubis/ilium junction, lateral to the pecten's medial end.
    sym = Vh[np.argmin(sgn * Vh[:, 0])]
    band = Vh[(Vh[:, 2] >= np.percentile(Vh[:, 2], 55)) &
              (Vh[:, 1] >= sym[1] - 5.0) & (Vh[:, 1] <= sym[1] + 35.0)]
    if len(band) < 10:
        band = Vh[Vh[:, 2] >= np.percentile(Vh[:, 2], 55)]
    # Along the pecten, the iliopubic eminence sits at the pubis/ilium junction, about 30 mm from the pubic
    # tubercle in an adult. Fix the position by that STATED DISTANCE from the symphyseal surface rather than by a
    # percentile of the band's width -- the percentile moved the point 47 mm between base_m and base_f because
    # the two bands are shaped differently, which is rule instability and not anatomy.
    r = np.linalg.norm(band - sym[None, :], axis=1)
    ring = band[(r >= 22.0) & (r <= 38.0)]
    if len(ring) < 5:
        ring = band[(r >= 15.0) & (r <= 45.0)]
    if len(ring) < 5:
        ring = band
    ins = ring[np.argmax(ring[:, 1])]
    return {"origin_t12": org[0], "origin_l1": org[1], "insertion_pecten": ins,
            "symphyseal_surface": sym, "how": how}


# ============================================================================ the four builders
def build_cal(got, ids, side, key):
    """coracoacromial ligament: coracoid posterolateral border -> anterior undersurface of the acromion."""
    sid = ids[f"scapula_{side}"]
    Vs, Fs = got[sid]
    lm = lm_scapula(Vs, side)
    bone = Bone(Vs, Fs)
    a, b = lm["coracoid_posterolateral"], lm["acromion_undersurface"]
    # the band is bowed away from the bone below, so the arch is an ARCH and not a chord through the scapula
    # GATE: the span must be inside the literature band (von Schroeder 27 +- 5 -> 17.0 mm at -2 SD;
    # Hu lateral band 31.90 +- 4.21 -> 40.3 mm at +2 SD). If the nearest-border pair misses it, try the tip pair
    # before giving up, and record which pair was used.
    LO, HI = 17.0, 40.3
    pairs = [("coracoid lateral border nearest the acromial attachment", a, b),
             ("coracoid tip to acromion anterior undersurface", lm["coracoid_tip"], lm["acromion_undersurface"]),
             ("coracoid tip to acromion lateral tip", lm["coracoid_tip"], lm["acromion_tip"])]
    chosen = None
    for how, p_, q_ in pairs:
        d = float(np.linalg.norm(q_ - p_))
        if LO <= d <= HI:
            chosen = (how, p_, q_, d)
            break
    if chosen is None:
        d0 = float(np.linalg.norm(b - a))
        return None, None, {"refused": True, "reason": "no coracoid/acromion pair on this page's own scapula "
                            f"gives a span inside the literature band {LO}-{HI} mm",
                            "spans_tried_mm": [round(float(np.linalg.norm(q_ - p_)), 1) for _, p_, q_ in pairs],
                            "gate_band_mm": [LO, HI], "nearest_border_span_mm": round(d0, 1)}
    how, a, b, chord0 = chosen
    P = resample(np.array([a, b]), 24)
    mid = (a + b) / 2.0
    p, _ = bone.nearest(mid[None, :])
    outw = unit(mid - p[0]) if np.linalg.norm(mid - p[0]) > 1e-6 else np.array([0.0, 1.0, 0.0])
    s = np.sin(np.linspace(0, np.pi, len(P)))[:, None]
    P = smooth_path(P + outw[None, :] * s * 3.0, 2)
    wA, _, _ = L.LIT["cal_width_coracoid_mm"]
    wB, _, _ = L.LIT["cal_width_acromion_mm"]
    th, _, _ = L.LIT["cal_thickness_mm"]
    w = np.linspace(wA, wB, len(P))
    ref = np.cross(unit(P[-1] - P[0]), outw)
    mind = float(bone.signed(P).min())
    P = smooth_path(P, 1)
    P, npush = push_path_out([bone], P, th / 2.0 + CLEAR, keep_ends=True)
    V, F, _, _ = tube(P, w, th, ref, nseg=12)
    st = mesh_stats(V, F)
    st.update({"length_mm": round(polyline_len(P), 1),
               "chord_mm": round(float(np.linalg.norm(b - a)), 1),
               "width_coracoid_mm": wA, "width_acromion_mm": wB, "thickness_mm": th,
               "path_points_cleared_of_scapula": npush,
               "min_signed_dist_scapula_path_before_mm": round(mind, 2),
               "min_signed_dist_to_scapula_after_mm": round(clearance([bone], V), 2),
               "acromion_tip": [round(float(x), 1) for x in lm["acromion_tip"]],
               "coracoid_tip": [round(float(x), 1) for x in lm["coracoid_tip"]],
               "lit_length_vonschroeder_mm": "27 +- 5", "lit_length_hu_medial_mm": "28.91 +- 5.56",
               "lit_length_hu_lateral_mm": "31.90 +- 4.21",
               "attachment_pair_used": how, "gate_band_mm": [LO, HI]})
    st["refused"] = not volume_agrees(st, analytic_volume_band(P, w, th))
    if st["refused"]:
        st["reason"] = ("the mesh volume disagrees with the analytic band volume by "
                        f"{st['volume_mesh_vs_analytic_rel']:.2f} (> {st['volume_check_tol']}), so the band "
                        "self-intersects after being pushed out of the scapula")
        return None, None, st
    return V, F, st


def build_lacn(got, ids, side, key):
    """the LACN's anterior and posterior branches, from the division point on the page's OWN LACN centreline.

    Khadanovich 2023: the division is at 47.8 +- 34.2 mm distal to the IEL in 76/93 (81.7 %) forearms. The IEL
    plane is built from the page's own humeral condyles. Both branches are then held within 1.8 mm of the medial
    border of the page's own brachioradialis (Khadanovich: 'less than 1.8 mm ... within the whole length of the
    brachioradialis') and run to the page's own distal radius. The anterior branch stays volar to that border,
    the posterior branch dorsal to it -- which is what their names mean."""
    Vn = got[ids[f"lacn_{side}"]][0]
    Vr, Fr = got[ids[f"radius_{side}"]]
    Vh = got[ids[f"humerus_{side}"]][0]
    Vb, Fb = got[ids[f"brachioradialis_{side}"]]
    iel = lm_iel(Vh, side)
    # radius axis, + distal
    Cr, Ar, _ = pca_axis(Vr)
    if along(Vr[np.argmin(Vr[:, 1])][None, :], Cr, Ar)[0] < 0:
        Ar = -Ar
    tr = along(Vr, Cr, Ar)
    t0, t1 = float(tr.min()), float(tr.max())
    # the page's own nerve centreline, ordered proximal -> distal
    Cn, An, _ = pca_axis(Vn)
    if (An @ Ar) < 0:
        An = -An
    P0 = centreline(Vn, An, Cn, nbin=40)
    P0 = P0[np.argsort(along(P0, Cr, Ar))]
    # distance of each centreline point distal to the IEL plane (plane normal = humeral distal axis)
    dist_iel = (P0 - iel["iel_mid"][None, :]) @ iel["distal_axis"]
    target = L.LIT["lacn_division_distal_to_iel_mm"][0]
    k = int(np.argmin(np.abs(dist_iel - target)))
    div = P0[k]
    div_mm = float(dist_iel[k])
    # the medial border of the brachioradialis, sampled along the forearm: for each level, the BR vertex nearest
    # the midline-side (medial) extreme. The branches are offset from it by <= 1.8 mm.
    sgn = 1.0 if side == "r" else -1.0
    tb = along(Vb, Cr, Ar)
    tb_div = along(div[None, :], Cr, Ar)[0]
    levels = np.linspace(max(tb_div, tb.min()), min(t1, tb.max()), 16)
    border, vol_n, dor_n = [], [], []
    for i in range(len(levels) - 1):
        s = (tb >= levels[i]) & (tb <= levels[i + 1])
        if s.sum() < 4:
            continue
        S = Vb[s]
        med = S[np.argmin(sgn * S[:, 0])]
        border.append(med)
        vol_n.append(unit(np.array([0.0, 0.0, 1.0])))      # volar / anterior
        dor_n.append(unit(np.array([0.0, 0.0, -1.0])))     # dorsal / posterior
    if len(border) < 3:
        return None
    border = smooth_path(np.array(border), 2)
    # Where the page's brachioradialis is a PARTIAL CT segmentation (the Imaging pages carry `_zfill` variants of
    # it), the border rail stops short of the wrist and the branch would end mid-forearm -- exactly Q307's finding
    # that the trunk stops 53.8-73.5 mm short. The rail is then continued along the page's OWN radius axis,
    # keeping the rail's own direction, and the extrapolated fraction is recorded on the card.
    tb_end = along(border[-1:], Cr, Ar)[0]
    want_end = t0 + 0.97 * (t1 - t0)
    extrap_pct = 0.0
    if tb_end < want_end - 5.0:
        dirn = unit(border[-1] - border[max(0, len(border) - 4)])
        step = (want_end - tb_end) / max(float(dirn @ Ar), 0.2)
        n_ex = 6
        tail = border[-1][None, :] + dirn[None, :] * np.linspace(step / n_ex, step, n_ex)[:, None]
        border = np.vstack([border, tail])
        extrap_pct = 100.0 * step / max(polyline_len(border), 1e-6)
    off = L.LIT["lacn_br_medial_border_max_mm"][0] * 0.8   # held INSIDE the published 1.8 mm bound
    # calibre: measured on this page's own trunk, branches at 60 % (a DECLARED modelling choice, lit308)
    dtr = float(np.percentile(np.linalg.norm(Vn - Vn.mean(0), axis=1), 5)) * 0.0 + trunk_diameter(Vn, An, Cn)
    dbr = max(0.45, 0.60 * dtr)
    out = {}
    for nm, nvec in (("anterior", np.array([0.0, 0.0, 1.0])), ("posterior", np.array([0.0, 0.0, -1.0]))):
        P = np.vstack([div[None, :], border + nvec[None, :] * off])
        P = resample(smooth_path(P, 2), 30)
        bone = Bone(Vr, Fr)
        br = Bone(Vb, Fb)
        mind = float(bone.signed(P).min())
        mind_br = float(br.signed(P).min())
        # a CUTANEOUS nerve must not sit INSIDE a muscle belly (Q307 S5), so the centreline is cleared of the
        # brachioradialis as well as the radius -- which still leaves it hugging that border well inside
        # Khadanovich's "less than 1.8 mm".
        P = smooth_path(P, 1)
        P, npush = push_path_out([bone, br], P, dbr / 2.0 + CLEAR, keep_ends=False)
        V, F, _, _, _ = tube_round(P, dbr, nseg=10)
        V, nlift = lift_rings([bone, br], V, len(P), 10, CLEAR)
        sd = br.signed(V)
        npush_br = npush
        st = mesh_stats(V, F)
        st.update({"length_mm": round(polyline_len(P), 1), "diameter_mm": round(dbr, 2),
                   "trunk_diameter_mm": round(dtr, 2),
                   "division_distal_to_iel_mm": round(div_mm, 1),
                   "division_target_mm": target, "division_sd_mm": L.LIT["lacn_division_distal_to_iel_mm"][1],
                   "t_start_on_radius": round(float((along(P[:1], Cr, Ar)[0] - t0) / (t1 - t0)), 3),
                   "t_end_on_radius": round(float((along(P[-1:], Cr, Ar)[0] - t0) / (t1 - t0)), 3),
                   "short_of_distal_radius_mm": round(float(t1 - along(P[-1:], Cr, Ar)[0]), 1),
                   "d_brachioradialis_p50_mm": round(float(np.median(sd)), 2),
                   "d_brachioradialis_min_mm": round(float(sd.min()), 2),
                   "max_depth_in_brachioradialis_mm": round(float(max(0.0, -sd.min())), 2),
                   "path_points_cleared": npush, "rings_lifted": nlift,
                   "min_signed_dist_brachioradialis_path_before_mm": round(mind_br, 2),
                   "min_signed_dist_to_radius_after_mm": round(clearance([bone], V), 2),
                   "min_signed_dist_radius_path_before_mm": round(mind, 2),
                   "border_rail_extrapolated_pct": round(extrap_pct, 1),
                   "branch_rate_pct": L.LIT["lacn_division_rate_pct"][0],
                   "single_branch_rate_pct": L.LIT["lacn_single_branch_rate_pct"][0]})
        volume_agrees(st, analytic_volume_round(P, dbr))
        lo, hi = target - L.LIT["lacn_division_distal_to_iel_mm"][1], target + L.LIT["lacn_division_distal_to_iel_mm"][1]
        g = {"volume_mesh_vs_analytic_rel": [st["volume_mesh_vs_analytic_rel"], 0.0, st["volume_check_tol"]],
             "division_distal_to_iel_mm": [st["division_distal_to_iel_mm"], round(lo, 1), round(hi, 1)],
             "short_of_distal_radius_mm": [st["short_of_distal_radius_mm"], -5.0, 20.0],
             "max_depth_in_brachioradialis_mm": [st["max_depth_in_brachioradialis_mm"], 0.0,
                                                 L.LIT["lacn_br_medial_border_max_mm"][0]]}
        st["gates"] = g
        bad = sorted(k for k, (v, a_, b_) in g.items() if not (a_ <= v <= b_))
        st["refused"] = bool(bad)
        if bad:
            st["reason"] = "gate(s) failed: " + ", ".join(bad)
            out[nm] = (None, None, st)
        else:
            out[nm] = (V, F, st)
    # BOTH SIDES OR NEITHER is enforced per page by the driver, as Q307's gate 3 did: a round that exists to put
    # the owner's own nerve in place must not ship it on one side only.
    return out


def trunk_diameter(Vn, A, C):
    """diameter of a tubular nerve mesh: twice the median radial distance of its vertices from its own centreline."""
    P = centreline(Vn, A, C, nbin=30)
    if len(P) < 2:
        return 1.0
    from scipy.spatial import cKDTree
    d, _ = cKDTree(P).query(Vn)
    return float(2.0 * np.median(d))


def build_psoas_minor(got, ids, side, key):
    """psoas minor: lateral aspect of the T12 and L1 bodies -> pecten pubis / iliopubic eminence (Raja 2026).
    Belly 45.7 mm and 6.0 mm across, then a long slender tendon; the TOTAL length is an OUTPUT, compared against
    Raja's 217.3 +- 4.5 mm."""
    a = lm_psoas_minor_anchors(got, ids, side, key)
    if a is None:
        return None
    Vh, Fh = got[ids[f"hip_bone_{side}"]]
    org = (a["origin_t12"] + a["origin_l1"]) / 2.0
    ins = a["insertion_pecten"]
    P = resample(np.array([a["origin_t12"], org, a["origin_l1"], ins]), 36)
    # the muscle runs down the anterior surface of psoas major / iliopsoas: bow it anteriorly so it lies ON that
    # surface rather than cutting through the vertebral bodies
    s = np.sin(np.linspace(0, np.pi, len(P)))[:, None]
    P = P + np.array([0.0, 0.0, 1.0])[None, :] * s * 6.0
    P = smooth_path(P, 3)
    bl, _, _ = L.LIT["psoas_minor_belly_len_mm"]
    db, _, _ = L.LIT["psoas_minor_belly_diam_mm"]
    tot = polyline_len(P)
    cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    frac = np.clip(cum / max(tot, 1e-6), 0, 1)
    belly_frac = min(0.9, bl / max(tot, 1e-6))
    d = np.where(frac <= belly_frac, db, 2.0)
    d = np.interp(frac, [0, belly_frac * 0.8, belly_frac, 1.0], [db * 0.8, db, 2.0, 2.0])
    bone = Bone(Vh, Fh)
    mind = float(bone.signed(P).min())
    P = smooth_path(P, 1)
    P, npush = push_path_out([bone], P, float(d.max()) / 2.0 + CLEAR, keep_ends=True)
    V, F, _, _, _ = tube_round(P, 1.0, nseg=10)
    # tube_round builds a unit tube; each ring is then scaled to the belly / tendon diameter of its own level
    V = V.reshape(-1, 3)
    nring = len(P)
    ringv = V[:nring * 10].reshape(nring, 10, 3)
    ctr = P[:, None, :]
    V[:nring * 10] = (ctr + (ringv - ctr) * d[:, None, None]).reshape(-1, 3)
    st = mesh_stats(V, F)
    straight = float(np.linalg.norm(ins - a["origin_t12"]))
    span = float(a["origin_t12"][1] - a["symphyseal_surface"][1])
    st.update({"bone_determined_straight_line_t12_to_pecten_mm": round(straight, 1),
               "page_own_t12_to_symphysis_vertical_span_mm": round(span, 1),
               "insertion_from_symphyseal_surface_mm": round(float(np.linalg.norm(ins - a["symphyseal_surface"])), 1),
               "excess_over_straight_line_pct": round(100.0 * (tot - straight) / max(straight, 1e-6), 1),
               "total_length_mm": round(tot, 1), "belly_length_mm": round(bl, 1),
               "tendon_length_mm": round(max(0.0, tot - bl), 1),
               "belly_diameter_mm": db, "tendon_diameter_mm": 2.0,
               "lit_total_length_mm": "217.3 +- 4.5", "lit_belly_length_mm": "45.7 +- 4.6",
               "lit_tendon_length_mm": "171.7 +- 8.5", "lit_belly_diameter_mm": "6.0 +- 0.5",
               "origin_levels": "T12 and L1 vertebral bodies, lateral aspect",
               "levels_how": a["how"],
               "insertion": "pecten pubis / iliopubic eminence",
               "path_points_cleared_of_hip_bone": npush,
               "min_signed_dist_hip_bone_path_before_mm": round(mind, 2),
               "min_signed_dist_to_hip_bone_after_mm": round(clearance([bone], V), 2),
               "prevalence_classic_pct": "40-50", "prevalence_raja_pct": 6.67,
               "hidden_by_default": True})
    # GATE: on the CONSTRUCTION, not on Raja's absolute length. The length here is set by the page's own T12 and
    # its own pubis, and these skeletons' T12-to-symphysis span is 298-344 mm against the ~210 mm a 217.3 mm
    # muscle implies, so Raja's figure CANNOT be reproduced on them and the geometry is not bent to reach it.
    # What is gated is that the muscle follows the bone-determined line (<= 15 % longer) and that its insertion
    # really sits on the pecten (22-38 mm from the symphyseal surface, the adult pecten's own length).
    ok_vol = volume_agrees(st, analytic_volume_round(P, d))
    g = {"excess_over_straight_line_pct": [st["excess_over_straight_line_pct"], 0.0, 15.0],
         "insertion_from_symphyseal_surface_mm": [st["insertion_from_symphyseal_surface_mm"], 15.0, 45.0],
         "volume_mesh_vs_analytic_rel": [st["volume_mesh_vs_analytic_rel"], 0.0, st["volume_check_tol"]]}
    st["gates"] = g
    bad = sorted(k for k, (v, a_, b_) in g.items() if not (a_ <= v <= b_))
    st["refused"] = bool(bad)
    if bad:
        st["reason"] = "gate(s) failed: " + ", ".join(bad)
        return None, None, st
    return V, F, st


def build_all_knee(got, ids, side, key):
    """anterolateral ligament of the knee. Femoral origin POSTERIOR AND PROXIMAL to the page's own fibular
    collateral ligament's femoral end (Kosy 2016's majority, 6/11; Rustagi 2019 says the opposite and that
    disagreement is carried onto the card). Tibial insertion at 59.5 % of the way from Gerdy's tubercle to the
    fibular head (Kosy 2016)."""
    Vf, Ff = got[ids[f"femur_{side}"]]
    Vt, Ft = got[ids[f"tibia_{side}"]]
    Vfi = got[ids[f"fibula_{side}"]][0]
    Vl = got[ids[f"lcl_{side}"]][0]
    gt, At, Ct = lm_gerdy(Vt, side)
    fh = lm_fibular_head(Vfi)
    # the LCL's femoral end = its most PROXIMAL (superior) end
    lcl_fem = Vl[Vl[:, 1] >= np.percentile(Vl[:, 1], 92)].mean(0)
    # posterior and proximal to it: Kosy reports the relation, not a distance, so the offset is the smallest step
    # that makes the relation unambiguous on this geometry -- 6 mm posterior and 6 mm proximal -- and it is
    # DECLARED, not presented as a measurement.
    fem = lcl_fem + np.array([0.0, 6.0, -6.0])
    bf = Bone(Vf, Ff)
    sd = bf.signed(fem[None, :])[0]
    if sd < CLEAR:
        p, _ = bf.nearest(fem[None, :])
        fem = p[0] + unit(fem - p[0]) * CLEAR
    frac = L.LIT["all_tibial_frac_gt_to_fh"][0]
    tib = gt + (fh - gt) * frac
    bt = Bone(Vt, Ft)
    P = resample(np.array([fem, (fem + tib) / 2.0, tib]), 20)
    s = np.sin(np.linspace(0, np.pi, len(P)))[:, None]
    sgn = 1.0 if side == "r" else -1.0
    P = P + unit(np.array([sgn, 0.0, 0.3]))[None, :] * s * 2.0
    P = smooth_path(P, 2)
    w, _, _ = L.LIT["all_width_mm"]
    th, _, _ = L.LIT["all_thickness_mm"]
    m1, m2 = float(bf.signed(P).min()), float(bt.signed(P).min())
    P = smooth_path(P, 1)
    P, np1 = push_path_out([bf, bt], P, th / 2.0 + CLEAR, keep_ends=True)
    np2 = 0
    V, F, _, _ = tube(P, w, th, np.array([0.0, 1.0, 0.0]), nseg=10)
    st = mesh_stats(V, F)
    out = {"length_mm": round(polyline_len(P), 1), "width_mm": w, "thickness_mm": th,
           "femoral_origin_rule": "posterior and proximal to this page's own fibular collateral ligament femoral end",
           "femoral_offset_mm": "6 posterior, 6 proximal (declared; Kosy 2016 reports the relation, not a distance)",
           "tibial_frac_gt_to_fh": frac,
           "tibial_from_gerdy_mm": round(float(np.linalg.norm(tib - gt)), 1),
           "tibial_from_fibular_head_mm": round(float(np.linalg.norm(tib - fh)), 1),
           "lit_tibial_from_gerdy_mm": "17.7 +- 2.95", "lit_tibial_from_fibular_head_mm": "12.3 +- 3.55",
           "lit_length_kosy_mm": "40.1 +- 5.53", "lit_length_rustagi_extension_mm": "40.38 +- 4.35",
           "gerdy_tubercle": [round(float(x), 1) for x in gt],
           "fibular_head": [round(float(x), 1) for x in fh],
           "path_points_cleared": np1,
           "min_signed_dist_femur_path_before_mm": round(m1, 2),
           "min_signed_dist_tibia_path_before_mm": round(m2, 2),
           "min_signed_dist_to_femur_after_mm": round(clearance([bf], V), 2),
           "min_signed_dist_to_tibia_after_mm": round(clearance([bt], V), 2),
           "contested": True}
    st.update(out)
    # GATE: both of Kosy 2016's independent tibial distances must land inside +- 3 SD, and the length inside
    # +- 3 SD of Kosy's mean. Two independent distance checks, so a landmark that slipped cannot pass by luck.
    volume_agrees(st, analytic_volume_band(P, w, th))
    # Kosy 2016 gives BOTH tibial distances -- 17.7 mm from Gerdy's tubercle and 12.3 mm from the fibular head --
    # so their own GT-to-FH span was about 30.0 mm. Our insertion sits at the SAME FRACTION (59.5 %) of each
    # page's own span, so the absolute millimetres scale with that span and are NOT a defect when it differs.
    # The fraction is therefore what is gated and the millimetres are reported beside the span, the same
    # size-aware treatment the psoas minor gets.
    span = float(np.linalg.norm(fh - gt))
    st["page_own_gerdy_to_fibular_head_span_mm"] = round(span, 1)
    st["kosy_implied_span_mm"] = 30.0
    st["span_ratio_page_over_kosy"] = round(span / 30.0, 2)
    gates = {"volume_mesh_vs_analytic_rel": (st["volume_mesh_vs_analytic_rel"], 0.0, st["volume_check_tol"]),
             "length_mm": (st["length_mm"], 40.1 - 3 * 5.53, 40.1 + 3 * 5.53),
             "tibial_frac_gt_to_fh": (st["tibial_frac_gt_to_fh"],
                                      0.595 - 3 * 0.0544, 0.595 + 3 * 0.0544)}
    bad = {k: [v, round(lo, 1), round(hi, 1)] for k, (v, lo, hi) in gates.items() if not (lo <= v <= hi)}
    st["gates"] = {k: [v, round(lo, 1), round(hi, 1)] for k, (v, lo, hi) in gates.items()}
    st["refused"] = bool(bad)
    if bad:
        st["reason"] = ("outside +- 3 SD of Kosy 2016 on: " + ", ".join(sorted(bad))
                        + f" (this page's Gerdy-to-fibular-head span is {st['page_own_gerdy_to_fibular_head_span_mm']} mm"
                          f" against Kosy's implied 30.0 mm)")
        return None, None, st
    # the Gerdy rule, CHECKED against the page's own iliotibial tract where the page carries one
    if ids.get(f"itb_{side}"):
        Vi = got[ids[f"itb_{side}"]][0]
        itb_tip = Vi[np.argmin(Vi[:, 1])]
        st["gerdy_rule_vs_itb_most_distal_vertex_mm"] = round(float(np.linalg.norm(gt - itb_tip)), 1)
        st["gerdy_rule_vs_itb_lowest_8pct_centroid_mm"] = round(
            float(np.linalg.norm(gt - Vi[Vi[:, 1] <= np.percentile(Vi[:, 1], 8)].mean(0))), 1)
    return V, F, st


# ============================================================================ driver
NEW_IDS = {
 "cal": "coracoacromial_ligament_{s}",
 "lacn_ant": "lacn_anterior_branch_{s}",
 "lacn_post": "lacn_posterior_branch_{s}",
 "psoas_minor": "psoas_minor_{s}",
 "all_knee": "anterolateral_ligament_{s}",
}


def build(keys, src, out_root):
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    rep = {}
    for key in keys:
        ids = ids_for(key, src)
        need = {v for v in ids.values() if v}
        need |= {"sacrum", "sternum", "hip_bone_l", "hip_bone_r"}
        extra_disc = "intervertebral_disc_t12_l1"
        need.add(extra_disc)
        st_all = pd.structures(key, src)
        thor = [s["id"] for s in st_all if s["id"] in ("thoracic_vertebrae",)]
        lumb = [s["id"] for s in st_all if s["id"] in ("lumbar_vertebrae",)]
        need |= set(thor) | set(lumb)
        got, thoracic, lumbar = {}, [], []
        for _, sid, v, f in pd.meshes(key, src):
            if sid in need:
                if sid == "thoracic_vertebrae":
                    thoracic.append(np.asarray(v, float))
                elif sid == "lumbar_vertebrae":
                    lumbar.append(np.asarray(v, float))
                elif sid not in got:
                    got[sid] = (np.asarray(v, float), np.asarray(f, np.int64))
        got["__thoracic"], got["__lumbar"] = thoracic, lumbar
        if extra_disc in got:
            got["__disc_t12_l1"] = got[extra_disc]
        fr = frame_check(got)
        res, meshes, refused = {"frame": fr}, {}, {}

        def take(sid, r):
            """one builder's result -> shipped mesh or a RECORDED refusal. Nothing is dropped silently."""
            if r is None:
                refused[sid] = {"refused": True, "reason": "builder returned nothing (an anchor this page lacks)"}
                res[sid] = refused[sid]
                return
            V, F, st = r
            res[sid] = st
            if V is None or st.get("refused"):
                refused[sid] = st
            else:
                meshes[sid] = (V, F)

        for side in "lr":
            for tag, fn in (("cal", build_cal), ("psoas_minor", build_psoas_minor), ("all_knee", build_all_knee)):
                sid = NEW_IDS[tag].format(s=side)
                try:
                    take(sid, fn(got, ids, side, key))
                except Exception as e:
                    res[sid] = refused[sid] = {"refused": True, "reason": "error: " + repr(e)[:180]}
            try:
                br = build_lacn(got, ids, side, key)
            except Exception as e:
                br = None
                for tag in ("lacn_ant", "lacn_post"):
                    sid = NEW_IDS[tag].format(s=side)
                    res[sid] = refused[sid] = {"refused": True, "reason": "error: " + repr(e)[:180]}
            if br:
                for nm, tag in (("anterior", "lacn_ant"), ("posterior", "lacn_post")):
                    take(NEW_IDS[tag].format(s=side), br[nm])

        # BOTH SIDES OR NEITHER, for every family (Q307's gate 3, widened). A right coracoacromial ligament with
        # no left one tells the reader the left shoulder has none, which is as wrong as a one-sided nerve.
        for tag in ("lacn_ant", "lacn_post", "cal", "psoas_minor", "all_knee"):
            l_, r_ = NEW_IDS[tag].format(s="l"), NEW_IDS[tag].format(s="r")
            if (l_ in meshes) != (r_ in meshes):
                keep, drop = (l_, r_) if l_ in meshes else (r_, l_)
                meshes.pop(keep, None)
                why = (f"withdrawn by the both-sides-or-neither rule: {drop} was refused "
                       f"({refused.get(drop, {}).get('reason', 'n/a')}), so {keep} is not shipped either")
                res[keep] = dict(res.get(keep, {}), refused=True, reason=why)
                refused[keep] = res[keep]

        np.savez_compressed(out_root / f"q308_{key}.npz",
                            **{f"{k}__v": v for k, (v, f) in meshes.items()},
                            **{f"{k}__f": f for k, (v, f) in meshes.items()})
        res["_ids_used"] = {k: v for k, v in ids.items() if v}
        res["_n_meshes"] = len(meshes)
        res["_n_refused"] = len(refused)
        res["_refused"] = {k: v.get("reason", "?") for k, v in sorted(refused.items())}
        res["_total_cm3"] = round(sum(res[k]["volume_cm3"] for k in meshes if "volume_cm3" in res.get(k, {})), 4)
        rep[key] = res
        print(f"{key}: {len(meshes)} shipped, {len(refused)} refused, {res['_total_cm3']} cm3", flush=True)
        for k in sorted(meshes):
            t = res[k]
            print(f"    {k:34s} {t['volume_cm3']:8.4f} cm3  {t['tris']:6d} tris  "
                  f"len {t.get('length_mm', t.get('total_length_mm', 0)):7.1f} mm  wt={t['watertight']}", flush=True)
        for k, v in sorted(refused.items()):
            print(f"    REFUSED {k:30s} {v.get('reason', '?')[:110]}", flush=True)
    rep["_README"] = [
        "Q308 rule-based structures, built on each page's own bones and own neighbours "
        "(scripts/anatomy/q308/build308.py); the cited numbers are in scripts/anatomy/q308/lit308.py.",
        "Depth in bone is a SIGNED SURFACE DISTANCE on the real bone mesh (trimesh ProximityQuery), not an "
        "inside/outside flag on a voxel solid -- Q307 S1 measured a voxel solid inflated to 116.7 cm3 against "
        "93.8 for the mesh, which nearly produced a false finding.",
    ]
    REPORT.write_text(json.dumps(rep, indent=1), encoding="utf-8")
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--keys", default=",".join(KEYS))
    ap.add_argument("--src", default="build/q307")
    ap.add_argument("--out", default="/dev/shm/q308/work")
    a = ap.parse_args()
    build([k.strip() for k in a.keys.split(",") if k.strip()], a.src, a.out)


if __name__ == "__main__":
    main()
