"""Q250: carry ALL non-bone structures of a Z-Anatomy page with the deformation of its bones (bone surfaces -> target bone surfaces), smooth and bone-anchored.

  field u(x) = w(d) * u_bone(nearest bone surface sample) + (1 - w(d)) * TPS(x)
    TPS   thin-plate spline (degree-1 polynomial, small smoothing) through ~5000 control points taken on the bone surfaces (displacement of the bone vertex there);
    w(d)  1 within 1.5 mm of a bone surface (origins / insertions follow the bone exactly), smoothly 0 beyond 10 mm;
  bones themselves are placed exactly on their targets.
Guards (all reported per structure): newly penetrating bone (pushed out 0.4 mm), newly leaving the skin (pulled in), volume / area change, flipped triangles, bone-attachment distance after.
"""
from __future__ import annotations
import numpy as np, trimesh
from scipy.spatial import cKDTree
from scripts.anatomy.q250 import lib as L

W_IN, W_OUT = 1.5, 10.0


def smooth_w(d):
    t = np.clip((W_OUT - d) / (W_OUT - W_IN), 0, 1)
    return t * t * (3 - 2 * t)


def surface_samples(Z, tgt, bone_ids, n_total=260000, seed=0):
    """area-proportional samples on the Z bones: position, outward normal (Z), displacement (bone target - Z), new position, new normal, owner id"""
    rng = np.random.default_rng(seed)
    areas = {}
    ms = {}
    for i in bone_ids:
        m0 = trimesh.Trimesh(Z[i]["v"], Z[i]["f"], process=False)
        m1 = trimesh.Trimesh(tgt[i], Z[i]["f"], process=False)
        ms[i] = (m0, m1); areas[i] = m0.area
    tot = sum(areas.values())
    P, N, U, P1, N1, own = [], [], [], [], [], []
    for k, i in enumerate(bone_ids):
        m0, m1 = ms[i]
        n = max(60, int(n_total * areas[i] / tot))
        p, fi = trimesh.sample.sample_surface(m0, n, seed=int(rng.integers(1 << 30)))
        tri0 = m0.vertices[m0.faces[fi]]; tri1 = m1.vertices[m1.faces[fi]]
        bc = trimesh.triangles.points_to_barycentric(tri0, p)
        p1 = (tri1 * bc[:, :, None]).sum(1)
        P.append(p); N.append(m0.face_normals[fi]); P1.append(p1); N1.append(m1.face_normals[fi]); U.append(p1 - p); own += [k] * len(p)
    return dict(P=np.vstack(P), N=np.vstack(N), U=np.vstack(U), P1=np.vstack(P1), N1=np.vstack(N1), own=np.array(own), ids=list(bone_ids))


def partner(i):
    if i.endswith("_l"):
        return i[:-2] + "_r"
    if i.endswith("_r"):
        return i[:-2] + "_l"
    return i


def surface_samples_sym(Z, tgt, bone_ids, n_total=260000, seed=0):
    """exactly mirror-symmetric bone-surface samples: sample the left bones and the midline bones (half the count, plus the mirror image of those samples), mirror the left samples onto the right bones
    (positions, displacements with the x component flipped, normals); valid when the targets of paired bones are mirror images (skel_target symmetrises them)."""
    ids = [i for i in bone_ids if not i.endswith("_r")]
    SS = surface_samples(Z, tgt, ids, n_total=n_total // 2, seed=seed)
    flip = np.array([-1.0, 1.0, 1.0])
    mid = np.array([not i.endswith("_l") for i in ids])[SS["own"]]                 # samples of midline bones (their mirror image is added too)
    P, N, U, P1, N1 = (SS[k] for k in ("P", "N", "U", "P1", "N1"))
    return dict(P=np.vstack([P, P * flip]), N=np.vstack([N, N * flip]), U=np.vstack([U, U * flip]), P1=np.vstack([P1, P1 * flip]), N1=np.vstack([N1, N1 * flip]),
                own=np.concatenate([SS["own"], SS["own"]]), ids=ids)


def control_points_sym(Z, tgt, bone_ids, n_total=5200, seed=0):
    """mirror-closed control set: random vertices of the left / midline bones, each with its mirror partner vertex (same bone for midline bones, the paired bone otherwise) and the partner's target"""
    rng = np.random.default_rng(seed)
    P, U = [], []
    ids = [i for i in bone_ids if not i.endswith("_r")]
    tot = sum(len(Z[i]["v"]) for i in ids)
    for i in ids:
        n = len(Z[i]["v"]); k = int(np.clip(round(n_total / 2 * n / tot), 8, 100)); k = min(k, n)
        idx = rng.choice(n, k, replace=False)
        P.append(Z[i]["v"][idx]); U.append(tgt[i][idx] - Z[i]["v"][idx])
        pj = partner(i)
        if pj in Z and pj in tgt:
            j = cKDTree(Z[pj]["v"]).query(L.mirror(Z[i]["v"][idx]))[1]
            P.append(Z[pj]["v"][j]); U.append(tgt[pj][j] - Z[pj]["v"][j])
    return np.vstack(P), np.vstack(U)


def control_points(Z, tgt, bone_ids, n_per=None, n_total=5200, seed=0):
    rng = np.random.default_rng(seed)
    P, U = [], []
    tot = sum(len(Z[i]["v"]) for i in bone_ids)
    for i in bone_ids:
        n = len(Z[i]["v"]); k = int(np.clip(round(n_total * n / tot), 14, 160)); k = min(k, n)
        idx = rng.choice(n, k, replace=False)
        P.append(Z[i]["v"][idx]); U.append(tgt[i][idx] - Z[i]["v"][idx])
    return np.vstack(P), np.vstack(U)


def orient_skin_normals(skin_P, skin_N, inner_pts):
    d, j = cKDTree(skin_P).query(inner_pts)
    frac = float((((inner_pts - skin_P[j]) * skin_N[j]).sum(1) < 0).mean())
    return (skin_N if frac >= 0.5 else -skin_N), frac


def tri_stats(v0, v1, f, closed=None):
    a0 = np.cross(v0[f[:, 1]] - v0[f[:, 0]], v0[f[:, 2]] - v0[f[:, 0]]); a1 = np.cross(v1[f[:, 1]] - v1[f[:, 0]], v1[f[:, 2]] - v1[f[:, 0]])
    A0 = np.linalg.norm(a0, axis=1) / 2; A1 = np.linalg.norm(a1, axis=1) / 2
    flip = float(((a0 * a1).sum(1) < 0).mean()) if len(f) else 0.0
    sv0 = float(np.einsum("ij,ij->i", v0[f[:, 0]], np.cross(v0[f[:, 1]], v0[f[:, 2]])).sum() / 6)
    sv1 = float(np.einsum("ij,ij->i", v1[f[:, 0]], np.cross(v1[f[:, 1]], v1[f[:, 2]])).sum() / 6)
    e0 = np.linalg.norm(v0[f[:, [0, 1, 2]]] - v0[f[:, [1, 2, 0]]], axis=2).ravel(); e1 = np.linalg.norm(v1[f[:, [0, 1, 2]]] - v1[f[:, [1, 2, 0]]], axis=2).ravel()
    ok = e0 > 1e-6
    st = e1[ok] / e0[ok]
    if closed is None and len(f):
        closed = trimesh.Trimesh(v0, f, process=False).is_watertight
    return dict(area_ratio=float(A1.sum() / max(A0.sum(), 1e-9)), flipped_fraction=flip, closed=bool(closed), signed_volume_ratio=float(sv1 / sv0) if (closed and abs(sv0) > 1e-6) else None,
                signed_volume_before_mm3=sv0, edge_stretch_p99=float(np.quantile(st, .99)) if len(st) else 1.0, edge_stretch_min=float(st.min()) if len(st) else 1.0)


def apply(Z, tgt, bone_ids=None, seed=0, verbose=True, exempt=(), symmetric=False):
    """Z: decoded page {id: dict(m, v, f)}; tgt: {bone id: target vertices}; exempt: ids of non-bone structures that are NOT carried. Returns dict(v={id: new vertices}, report, control=(P, U))"""
    bone_ids = [i for i in (bone_ids or tgt) if Z[i]["m"]["sys"] == "bone" and i in tgt]
    soft = [i for i in Z if i not in bone_ids]
    SS = surface_samples_sym(Z, tgt, bone_ids, seed=seed) if symmetric else surface_samples(Z, tgt, bone_ids, seed=seed)
    Pc, Uc = control_points_sym(Z, tgt, bone_ids, seed=seed) if symmetric else control_points(Z, tgt, bone_ids, seed=seed)
    tps = L.TPS(Pc, Uc, smoothing=0.5)
    tree = cKDTree(SS["P"]); tree1 = cKDTree(SS["P1"])
    # skin samples (Z and new) for the envelope guard
    skin_ids = [i for i in Z if Z[i]["m"]["sys"] == "skin" and len(Z[i]["f"])]
    new = {i: tgt[i] for i in bone_ids}
    rep = dict(structures={}, control_points=int(len(Pc)), bone_samples=int(len(SS["P"])))
    for k, i in enumerate(soft):
        V = Z[i]["v"]
        if not len(V) or i in exempt:               # exempt: structures that already sit correctly (measured / registered on the target) are not moved; guards still run
            new[i] = V.copy(); continue
        dk, jk = tree.query(V, k=8)
        d = dk[:, 0]
        wk = 1.0 / (dk ** 4 + 0.5 ** 4)                                  # inverse-distance (power 4) mean of the 8 nearest bone-surface samples: no jump where two bones are equally near
        Ub = (wk[:, :, None] * SS["U"][jk]).sum(1) / wk.sum(1)[:, None]
        a_ = np.clip((d - 1.0) / 0.5, 0, 1)[:, None]                     # within 1 mm of a bone surface: exactly the displacement of the nearest bone sample (attachment distance can only stay <= before)
        Ub = (1 - a_) * SS["U"][jk[:, 0]] + a_ * Ub
        u = tps(V)
        w = smooth_w(d)[:, None]
        U = w * Ub + (1 - w) * u
        new[i] = V + U
        if verbose and k % 400 == 0:
            print("warp", k, "/", len(soft), flush=True)
    # skin: envelope samples before / after
    def skin_samples(vs):
        P, N = [], []
        for i in skin_ids:
            m = trimesh.Trimesh(vs[i], Z[i]["f"], process=False)
            p, fi = trimesh.sample.sample_surface(m, max(30, int(m.area / 4.0)), seed=1)
            P.append(p); N.append(m.face_normals[fi])
        return np.vstack(P), np.vstack(N)
    sp0, sn0 = skin_samples({i: Z[i]["v"] for i in skin_ids}); sp1, sn1 = skin_samples({i: new[i] for i in skin_ids})
    bone_inner = np.vstack([Z[i]["v"][::40] for i in bone_ids[:80]])
    sn0, fr = orient_skin_normals(sp0, sn0, bone_inner)
    sn1 = sn1 if (((sn1 * sn0[cKDTree(sp0).query(sp1)[1]]).sum(1)) > 0).mean() > 0.5 else -sn1
    rep["skin_normal_inside_fraction_check"] = round(fr, 3)
    skin_t0 = cKDTree(sp0); skin_t1 = cKDTree(sp1)
    pen_total, pen_fixed, skin_total, unfixed_total = 0, 0, 0, 0
    attach = []
    for i in soft:
        V0, V1, F = Z[i]["v"], new[i], Z[i]["f"]
        if not len(V0):
            continue
        st = tri_stats(V0, V1, F) if len(F) else dict(area_ratio=1.0, flipped_fraction=0.0, signed_volume_ratio=None, signed_volume_before_mm3=0.0, edge_stretch_p99=1.0, edge_stretch_min=1.0)
        # bone penetration (soft structures only): inside-before vs inside-after by the nearest bone sample normal
        d0, j0 = tree.query(V0); in0 = (d0 < 6.0) & (((V0 - SS["P"][j0]) * SS["N"][j0]).sum(1) < 0)
        d1, j1 = tree1.query(V1); in1 = (d1 < 6.0) & (((V1 - SS["P1"][j1]) * SS["N1"][j1]).sum(1) < 0)
        newly = in1 & ~in0
        n_new = int(newly.sum())
        if n_new:
            V1 = V1.copy()
            V1[newly] = SS["P1"][j1[newly]] + SS["N1"][j1[newly]] * 0.4
            new[i] = V1
        # attachments: vertices within 1 mm of a Z bone surface -> distance to the NEW bone surface
        near = (d0 <= 1.0) & (i not in exempt)                       # exempt structures (registered on the target by their own scripts) have no attachment to preserve
        if near.any():
            da = tree1.query(new[i][near])[0]
            attach.append(da)
        # skin envelope (not for skin / bones)
        sk = Z[i]["m"]["sys"] != "skin"
        n_sk = 0; n_unfixed = 0
        if sk:
            dd0, jj0 = skin_t0.query(V0); out0 = ((V0 - sp0[jj0]) * sn0[jj0]).sum(1) > 0
            dd1, jj1 = skin_t1.query(new[i]); sg1 = ((new[i] - sp1[jj1]) * sn1[jj1]).sum(1)
            leave = (sg1 > 0) & ~out0
            fix = leave & (sg1 < 6.0)                                  # small violations only (a bone-anchored vertex under thin skin): pulled back 1 mm inside along the skin normal; larger ones are
            n_sk = int(fix.sum())                                      # ambiguous (nearest skin of another body part, e.g. arm against torso) and are only counted
            n_unfixed = int((leave & ~fix).sum())
            if n_sk:
                nv = new[i].copy(); nv[fix] -= sn1[jj1[fix]] * (sg1[fix] + 1.0)[:, None]; new[i] = nv
        st.update(vertices=int(len(V0)), newly_in_bone=n_new, newly_outside_skin=n_sk, outside_skin_not_corrected=n_unfixed, mean_move_mm=round(float(np.linalg.norm(new[i] - V0, axis=1).mean()), 2),
                  max_move_mm=round(float(np.linalg.norm(new[i] - V0, axis=1).max()), 1), sys=Z[i]["m"]["sys"])
        pen_total += n_new; skin_total += n_sk; unfixed_total += n_unfixed
        rep["structures"][i] = st
    rep["newly_in_bone_vertices"] = pen_total; rep["newly_outside_skin_vertices"] = skin_total; rep["outside_skin_not_corrected_vertices"] = unfixed_total
    if attach:
        a = np.concatenate(attach)
        rep["attachment_distance_after_mm"] = dict(n=int(len(a)), median=round(float(np.median(a)), 3), p95=round(float(np.quantile(a, .95)), 3), max=round(float(a.max()), 3),
                                                   fraction_le_1mm=round(float((a <= 1.0).mean()), 4))
    # bones: target vs Z
    for i in bone_ids:
        st = tri_stats(Z[i]["v"], tgt[i], Z[i]["f"]); st.update(vertices=int(len(Z[i]["v"])), sys="bone", mean_move_mm=round(float(np.linalg.norm(tgt[i] - Z[i]["v"], axis=1).mean()), 2))
        rep["structures"][i] = st
    return dict(v=new, report=rep, control=(Pc, Uc), samples=(SS["P"], SS["U"]))


def carry(V, control, samples):
    """displacement of arbitrary points V (n, 3) of ANOTHER structure with the SAME field as `apply` (TPS through the control points + inverse-distance bone anchoring within 10 mm of the bones),
    e.g. the ligaments that a later agent adds to the page in the Z frame.  control = (P, U); samples = (bone surface sample positions, their displacements)."""
    tps = L.TPS(*control, smoothing=0.5)
    tree = cKDTree(samples[0])
    dk, jk = tree.query(V, k=8)
    d = dk[:, 0]
    wk = 1.0 / (dk ** 4 + 0.5 ** 4)
    Ub = (wk[:, :, None] * samples[1][jk]).sum(1) / wk.sum(1)[:, None]
    a_ = np.clip((d - 1.0) / 0.5, 0, 1)[:, None]
    Ub = (1 - a_) * samples[1][jk[:, 0]] + a_ * Ub
    w = smooth_w(d)[:, None]
    return V + w * Ub + (1 - w) * tps(V)
