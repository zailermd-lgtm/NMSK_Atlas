"""Q186c: smooth, fold-guarded refit of the female Z-Anatomy TRUNK (thorax + abdomen) onto HER OWN CT.

Owner: "error in the chest/abdomen area of the FEMALE Z-Anatomy model"; second report: a step at the thorax/abdomen
transition (T10-L1), thorax too narrow all round.  Measured causes (data/derived/Q186c_trunk_refit.json):
  1. RIBS.  Q168 fitted the Z-Anatomy ribs (one similarity per side) onto the old bundle ribs, which were dilated
     10-16 mm; against her TotalSegmentator rib labels the shipped ribs lie 13 mm median (p90 27) away: 6-8 mm too
     narrow per side (12-16 mm of width) and 25-40 mm too deep (AP) in the mid thorax.  Pelvis, sternum, scapula and
     clavicle fits are 1.3-2.2 mm from her labels -> only the ribs are wrong.  Fix: per-rib similarity ICP onto HER
     rib label i (partial-aware, dst->src pairing), start = the Q168 position, scale and shift bounded.
  2. SOFT TISSUE.  Q168 carries each soft vertex by an inverse-distance blend of per-bone similarities that taper to 0
     at 40 mm past the nearest bone.  Between the ribcage (scale 0.84-0.89), the pelvis (0.93) and the spine the
     blend of different rotations/scales shears and folds (V-shaped pleats below the breasts, step at the costal
     margin) and the front/back skin ends 20-50 mm inside her CT skin.
     Fix: ONE smooth displacement field (cubic RBF, smoothed) from the RAW Z-Anatomy coordinates, anchored on
       - every Z-Anatomy bone (target = its Q168 position; ribs = the refit above), and
       - the trunk skin: each skin vertex -> her CT skin outline along the horizontal ray from her trunk axis
         (anterior + posterior sectors only; the lateral band is hidden by her arms, which are fused with her skin
         there, so it is interpolated by the field, never measured).
     applied to every non-bone vertex with a smooth weight w = 1 within W0 mm of the trunk bones, 0 beyond W1 mm
     (continuous in position, so neighbouring patches / muscles never tear).  Fold guard: Jacobian determinant of
     the whole map sampled on a grid, plus the share of faces whose normal flips against the Q168 result.
Nothing is invented: all targets are her own CT labels / CT skin; the soft tissue's mutual arrangement is Z-Anatomy's.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

RIB_NAMES = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
             "eleventh", "twelfth"]
RIB_LABEL0 = {"l": 92, "r": 104}          # TotalSegmentator total: rib_left_1 = 92 ... rib_right_1 = 104
RIB_SCALE_BOUNDS = (0.85, 1.20)
RIB_SHIFT_MAX_MM = 45.0
TRUNK_BONE_RE = ("rib", "sternum", "xiphoid", "vertebra", "sacrum", "coccyx", "hip_bone", "clavicle", "scapula")
W0_MM, W1_MM = 150.0, 230.0               # weight 1 within W0 of a trunk bone, 0 beyond W1
RBF_SMOOTH = 30.0
RBF_KERNEL = "cubic"
OUT_JSON = REPO / "data" / "derived" / "Q186c_trunk_refit.json"
SKIN_ANTERIOR_DEG, SKIN_POSTERIOR_DEG = 62.0, 122.0   # trusted sectors of her outline: |theta| < 62 (front), > 122 (back)


# ----------------------------------------------------------------------------------- her labels
def rib_label_points(label: int, vol=None):
    """surface voxel centres (atlas mm, her frame) of one TotalSegmentator total label of her CT"""
    import nibabel as nib
    from scipy import ndimage as ndi
    from engine.volume_ingest import voxels_to_atlas
    from scripts.ribs_from_ct_labels import ORIGIN, TASK
    if vol is None:
        img = nib.load(TASK / "vhf_total.nii.gz")
        vol = (np.asarray(img.dataobj).astype(np.uint8), img.affine)
    V, A = vol
    O = np.array([float(x) for x in ORIGIN["vhf"].split(",")])
    objs = ndi.find_objects((V == label).astype(np.uint8))
    sl = objs[0]
    if sl is None:
        return np.zeros((0, 3))
    lo = [max(s.start - 1, 0) for s in sl]
    sub = V[tuple(slice(l, min(s.stop + 1, n)) for l, s, n in zip(lo, sl, V.shape))] == label
    surf = sub & ~ndi.binary_erosion(sub)
    return voxels_to_atlas((np.argwhere(surf) + lo).astype(float), A) - O


def load_her_vol():
    import nibabel as nib
    from scripts.ribs_from_ct_labels import TASK
    img = nib.load(TASK / "vhf_total.nii.gz")
    return np.asarray(img.dataobj).astype(np.uint8), img.affine


def rib_id(i: int, side: str) -> str:
    return f"zan_{RIB_NAMES[i]}_rib_{side}"


# ----------------------------------------------------------------------------------- rib refit
def refit_ribs(pending: list[dict], vol=None, log=print) -> dict:
    """per-rib similarity ICP of the (Q168-placed) Z-Anatomy rib onto her label rib; moves p["v"] in place."""
    from scripts.transfer.zan_to_vhf_whole_body import apply_sim, trimmed_icp, sim_scale, surface_distance
    by_id = {p["mesh_id"]: p for p in pending}
    vol = vol or load_her_vol()
    rep = {}
    for side in "lr":
        for i in range(12):
            mid = rib_id(i, side)
            p = by_id.get(mid)
            if p is None:
                continue
            dst = rib_label_points(RIB_LABEL0[side] + i, vol)
            if len(dst) < 200:
                rep[mid] = {"status": "no label"}
                continue
            v0 = p["v"]
            rng = np.random.default_rng(i)
            src = v0[rng.choice(len(v0), min(len(v0), 4000), replace=False)]
            dsub = dst[rng.choice(len(dst), min(len(dst), 6000), replace=False)]
            before = surface_distance(src, dst)
            best = None
            for scale_free in (True, False):
                A, t = trimmed_icp(src, dsub, np.eye(3), np.zeros(3), scale=scale_free, corr="dst", iters=60, trim=0.85)
                s = sim_scale(A)
                shift = float(np.linalg.norm(apply_sim(A, t, v0).mean(0) - v0.mean(0)))
                ok = RIB_SCALE_BOUNDS[0] <= s <= RIB_SCALE_BOUNDS[1] and shift <= RIB_SHIFT_MAX_MM
                d = surface_distance(apply_sim(A, t, src), dst)
                cand = {"A": A, "t": t, "scale": s, "shift": shift, "ok": ok, "d": d, "scale_free": scale_free}
                if ok and (best is None or d["b_to_a"] < best["d"]["b_to_a"]):
                    best = cand
            if best is None:
                rep[mid] = {"status": "held (scale/shift out of bounds)"}
                continue
            p["v"] = apply_sim(best["A"], best["t"], v0)
            rep[mid] = {"status": "refit", "scale": round(best["scale"], 3), "shift_mm": round(best["shift"], 1),
                        "scale_free": best["scale_free"],
                        "her_label_to_Z_mm_before": round(before["b_to_a"], 2), "her_label_to_Z_mm_after": round(best["d"]["b_to_a"], 2),
                        "Z_to_her_label_mm_before": round(before["a_to_b"], 2), "Z_to_her_label_mm_after": round(best["d"]["a_to_b"], 2)}
            log(f"  {mid}: {rep[mid]}")
    return rep


# ----------------------------------------------------------------------------------- her outline chart
def trunk_axis(sv: np.ndarray):
    """her trunk axis (x(y), z(y)): centre of the skin slab between |x| < 110 (arms excluded), smoothed"""
    cy = np.arange(-120.0, 700.0, 10.0)
    cx, cz = np.full(len(cy), np.nan), np.full(len(cy), np.nan)
    for i, y in enumerate(cy):
        m = (np.abs(sv[:, 1] - y) < 5) & (np.abs(sv[:, 0]) < 110)
        if m.sum() > 20:
            cx[i] = 0.5 * (sv[m, 0].min() + sv[m, 0].max()); cz[i] = 0.5 * (sv[m, 2].min() + sv[m, 2].max())
    ok = ~np.isnan(cx)
    cx = np.interp(cy, cy[ok], cx[ok]); cz = np.interp(cy, cy[ok], cz[ok])
    k = np.ones(5) / 5
    cx = np.convolve(np.pad(cx, 2, mode="edge"), k, mode="valid"); cz = np.convolve(np.pad(cz, 2, mode="edge"), k, mode="valid")
    return lambda y: (np.interp(y, cy, cx), np.interp(y, cy, cz))


def her_outline_chart(skin_mesh, axis, ys, ths):
    """R[y, theta] = first-exit radius of the horizontal ray from the axis; nh = number of surface crossings.
    Returns R, trusted mask (front/back sectors, one crossing, not next to a multi-crossing cell = hand/arm contact)."""
    from scipy import ndimage as ndi
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    ri = RayMeshIntersector(skin_mesh)
    Y, Th = np.meshgrid(ys, ths, indexing="ij")
    xc, zc = axis(Y.ravel())
    org = np.stack([xc, Y.ravel(), zc], 1)
    d = np.stack([np.sin(Th.ravel()), np.zeros(Th.size), np.cos(Th.ravel())], 1)
    loc, ir, _ = ri.intersects_location(org, d, multiple_hits=True)
    t = np.linalg.norm(loc - org[ir], axis=1)
    first = np.full(Th.size, np.inf); nh = np.zeros(Th.size, int)
    np.minimum.at(first, ir, t); np.add.at(nh, ir, 1)
    first[~np.isfinite(first)] = np.nan
    R, nh = first.reshape(Y.shape), nh.reshape(Y.shape)
    adeg = np.abs(np.degrees(Th))
    sector = (adeg < SKIN_ANTERIOR_DEG) | (adeg > SKIN_POSTERIOR_DEG)
    multi = ndi.binary_dilation(nh != 1, structure=np.ones((5, 5), bool), iterations=2)
    trusted = sector & ~multi & ~np.isnan(R)
    return R, nh, trusted


def bilinear(grid, ys, ths, y, th):
    """grid[y, theta] sampled at (y, theta) with theta wrapping; nan-propagating"""
    fy = np.clip((y - ys[0]) / (ys[1] - ys[0]), 0, len(ys) - 1.000001)
    ft = ((th - ths[0]) / (ths[1] - ths[0])) % len(ths)
    i0, j0 = np.floor(fy).astype(int), np.floor(ft).astype(int)
    a, b = fy - i0, ft - j0
    j1 = (j0 + 1) % len(ths)
    return ((1 - a) * (1 - b) * grid[i0, j0] + (1 - a) * b * grid[i0, j1] + a * (1 - b) * grid[i0 + 1, j0] + a * b * grid[i0 + 1, j1])


# ----------------------------------------------------------------------------------- field
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def trunk_weight(q: np.ndarray, axis) -> np.ndarray:
    """position-only weight of the refit at her-frame points q: 1 within 165 mm (horizontal) of her trunk axis and
    -110..600 mm in y, fading to 0 by 215 mm / 170 mm below / 660 mm above.  Continuous in position -> neighbouring
    patches and muscles never tear."""
    xc, zc = axis(q[:, 1])
    rho = np.hypot(q[:, 0] - xc, q[:, 2] - zc)
    wr = smoothstep((215.0 - rho) / 50.0)
    wy = np.minimum(smoothstep((q[:, 1] + 170.0) / 60.0), smoothstep((660.0 - q[:, 1]) / 60.0))
    return wr * wy


def rbf(src: np.ndarray, dst: np.ndarray, smoothing: float):
    from scipy.interpolate import RBFInterpolator
    return RBFInterpolator(src, dst - src, kernel=RBF_KERNEL, smoothing=smoothing, degree=1)


def apply_rbf(f, p: np.ndarray, chunk: int = 8000) -> np.ndarray:
    out = np.empty_like(p)
    for i in range(0, len(p), chunk):
        out[i:i + chunk] = p[i:i + chunk] + f(p[i:i + chunk])
    return out


def jacobian_stats(f, pts: np.ndarray, h: float = 4.0) -> dict:
    """det(I + d disp/dp) by central differences at pts (field only, before the position weight)"""
    J = np.empty((len(pts), 3, 3))
    for k in range(3):
        e = np.zeros(3); e[k] = h
        J[:, :, k] = (f(pts + e) - f(pts - e)) / (2 * h)
    det = np.linalg.det(np.eye(3)[None] + J)
    return {"n": int(len(det)), "min": round(float(det.min()), 3), "p01": round(float(np.percentile(det, 1)), 3),
            "median": round(float(np.median(det)), 3), "p99": round(float(np.percentile(det, 99)), 3),
            "max": round(float(det.max()), 3), "frac_below_0.25": round(float((det < 0.25).mean()), 5)}


SKIN_LIMB = ("arm", "forearm", "wrist", "hand", "digits", "palm", "nail", "perionyx", "thigh", "radial", "bicipital",
             "border_of_forearm", "deltoid_region", "foveola", "sternocleido", "supraclavicular", "muscular_triangle",
             "anal", "gluteal_fold", "femoral_triangle")


def trunk_skin_ids(pending: list[dict]) -> list[str]:
    """Z-Anatomy skin patches of the trunk (by name + position in her frame): thorax, abdomen, back, flanks, groin"""
    out = []
    for p in pending:
        if p["cat"] != "skin":
            continue
        c = p["v"].mean(0)
        if -30 < c[1] < 600 and abs(c[0]) < 160 and not any(s in p["mesh_id"] for s in SKIN_LIMB):
            out.append(p["mesh_id"])
    return out


# ----------------------------------------------------------------------------------- the refit
def _sample_bones(pending, raw, per_bone=120, seed=3):
    rng = np.random.default_rng(seed)
    src, dst, ids = [], [], []
    for p in pending:
        if p["cat"] != "bone" or p["mesh_id"] not in raw:
            continue
        c = p["v"].mean(0)
        if not (-320 < c[1] < 780):
            continue
        n = len(p["v"]); k = min(n, per_bone * (3 if any(s in p["mesh_id"] for s in TRUNK_BONE_RE) else 1))
        j = rng.choice(n, k, replace=False)
        src.append(raw[p["mesh_id"]][j]); dst.append(p["v"][j]); ids += [p["mesh_id"]] * k
    return np.vstack(src), np.vstack(dst), ids


def refit_trunk(pending: list[dict], raw: dict, skin_mesh=None, log=print, smoothing: float = RBF_SMOOTH) -> dict:
    """Move every non-bone vertex of `pending` (already Q168-placed, bones + ribs final) by the smooth field.
    raw = {mesh_id: vertices before the Q168 fit}.  Returns the report dict."""
    from scripts.ribs_from_ct_labels import load_skin
    skin_mesh = skin_mesh or load_skin("vhf")
    sv = np.asarray(skin_mesh.vertices, np.float64)
    axis = trunk_axis(sv)
    by_id = {p["mesh_id"]: p for p in pending}
    rep = {"rbf": {"kernel": RBF_KERNEL, "smoothing": smoothing}, "weight": {"rho0_mm": 165, "rho1_mm": 215}}

    # 1. bone anchors -> base field (bones only): smooth replacement of the Q168 blend
    bs, bd, _ = _sample_bones(pending, raw)
    base = rbf(bs, bd, smoothing)
    rep["rbf"]["bone_anchors"] = int(len(bs))
    rep["bone_anchor_residual_mm"] = _res(base, bs, bd)

    # 2. skin anchors: base position of each trunk-skin vertex -> her outline along the horizontal ray from her axis
    ys = np.arange(-60.0, 641.0, 5.0); ths = np.radians(np.arange(-180.0, 180.0, 2.0))
    R, nh, trusted = her_outline_chart(skin_mesh, axis, ys, ths)
    sk_ids = trunk_skin_ids(pending)
    S = {k: apply_rbf(base, raw[k]) for k in sk_ids}
    allS = np.vstack(list(S.values()))
    xc, zc = axis(allS[:, 1])
    th = np.arctan2(allS[:, 0] - xc, allS[:, 2] - zc); r = np.hypot(allS[:, 0] - xc, allS[:, 2] - zc)
    # outer radius of the base-positioned Z-Anatomy skin per (y, theta) cell: max over its vertices, then dilated/smoothed
    from scipy import ndimage as ndi
    Rz = np.full(R.shape, np.nan)
    iy = np.clip(np.round((allS[:, 1] - ys[0]) / 5.0).astype(int), 0, len(ys) - 1)
    it = np.round((th - ths[0]) / (ths[1] - ths[0])).astype(int) % len(ths)
    np.fmax.at(Rz, (iy, it), r)
    filled = ~np.isnan(Rz)
    # fill empty cells with the nearest filled one, then smooth (the outer surface is smooth; patches overlap and abut)
    idx = ndi.distance_transform_edt(~filled, return_distances=False, return_indices=True)
    Rz = Rz[tuple(idx)]
    Rz = ndi.gaussian_filter(Rz, sigma=(2.0, 2.0), mode=("nearest", "wrap"))
    Rz_max = ndi.maximum_filter(Rz, size=(3, 5), mode=("nearest", "wrap"))     # outer envelope
    delta_grid = np.where(trusted, R - Rz_max, np.nan)
    d = bilinear(delta_grid, ys, ths, allS[:, 1], th)
    trust_v = ~np.isnan(d)
    # cap the single-vertex shift (bounded displacement): |delta| <= 90 mm
    cap = np.abs(d) <= 90.0
    use = trust_v & cap
    t_pts = allS.copy()
    t_pts[use, 0] += d[use] * np.sin(th[use]); t_pts[use, 2] += d[use] * np.cos(th[use])
    raw_all = np.vstack([raw[k] for k in sk_ids])
    # one anchor per 5 mm voxel (the shells are dense)
    key = np.floor(raw_all[use] / 5.0).astype(int)
    _, first = np.unique(key, axis=0, return_index=True)
    sk_src, sk_dst = raw_all[use][first], t_pts[use][first]
    rep["skin_anchors"] = {"patches": len(sk_ids), "vertices": int(len(raw_all)), "with_her_outline": int(use.sum()),
                           "anchors_used": int(len(first)),
                           "outline_shift_mm": {"median": round(float(np.median(d[use])), 1), "p10": round(float(np.percentile(d[use], 10)), 1),
                                                "p90": round(float(np.percentile(d[use], 90)), 1)},
                           "trusted_cell_fraction": round(float(trusted.mean()), 3)}
    log(f"  trunk skin: {len(sk_ids)} patches, {use.sum()} of {len(raw_all)} vertices carry her outline, shift {rep['skin_anchors']['outline_shift_mm']}")

    # 3. final field, fold-guarded: raise the smoothing until the Jacobian determinant stays >= 0.25
    A_src, A_dst = np.vstack([bs, sk_src]), np.vstack([bd, sk_dst])
    grid_pts = _jac_grid(pending, raw)
    sm = smoothing
    for attempt in range(4):
        field = rbf(A_src, A_dst, sm)
        jac = jacobian_stats(field, grid_pts)
        rep["jacobian"] = {**jac, "smoothing": sm, "attempt": attempt}
        log(f"  field smoothing {sm}: Jacobian {jac}")
        if jac["min"] >= 0.25:
            break
        sm *= 4
    rep["rbf"]["final_smoothing"] = sm
    rep["bone_anchor_residual_final_mm"] = _res(field, bs, bd)
    rep["skin_anchor_residual_mm"] = _res(field, sk_src, sk_dst)

    # 4. apply to every non-bone vertex with the position weight
    moved, stat = 0, {}
    for p in pending:
        if p["cat"] == "bone":
            continue
        q = p["v"]
        w = trunk_weight(q, axis)
        sel = w > 1e-3
        if not sel.any():
            continue
        f_new = apply_rbf(field, raw[p["mesh_id"]][sel])
        new = q.copy()
        new[sel] = q[sel] + w[sel, None] * (f_new - q[sel])
        stat[p["mesh_id"]] = {"w_mean": float(w.mean()), "shift_med": float(np.median(np.linalg.norm(new - q, axis=1)[sel])),
                              "shift_max": float(np.linalg.norm(new - q, axis=1).max())}
        p["v_q168"] = q
        p["v"] = new
        moved += 1
    rep["structures_moved"] = moved
    rep["shift_vs_q168_mm"] = {"median_of_structure_medians": round(float(np.median([s["shift_med"] for s in stat.values()])), 1),
                               "max": round(float(max(s["shift_max"] for s in stat.values())), 1)}
    rep["_per_structure_shift"] = stat
    return rep


def _res(f, src, dst) -> dict:
    e = np.linalg.norm(apply_rbf(f, src) - dst, axis=1)
    return {"median": round(float(np.median(e)), 2), "p90": round(float(np.percentile(e, 90)), 2), "max": round(float(e.max()), 2)}


def _jac_grid(pending, raw, step=16.0, near=18.0):
    """raw-space grid points within `near` mm of any trunk-structure vertex (the places the field is used)"""
    pts = np.vstack([raw[p["mesh_id"]][::7] for p in pending if p["cat"] != "bone" and p["mesh_id"] in raw])
    key = np.unique(np.floor(pts / step).astype(int), axis=0)
    return (key + 0.5) * step
