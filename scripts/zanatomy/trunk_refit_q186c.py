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
     (continuous in position, so neighbouring patches / muscles never tear); non-skin tissue follows the outline only
     as far as it lies away from bone (skin_share: 0 within 15 mm of a trunk bone, 1 beyond 60 mm) and every closed
     structure is kept within 0.65-1.5 x its Z-Anatomy volume at her body scale (the skin share is cut back if not).
     Fold guard, as measured (data/derived/Q186c_trunk_refit.json): the field's own Jacobian determinant is REPORTED
     (it does NOT reach the >= 0.25 target even at the largest smoothing tried: 5 % of sampled points below 0.25, min -3.9;
     anchors from different bones conflict locally), so the guard that is actually met is the mesh-level one: faces
     flipped against the Z-Anatomy source normal 2.2 % -> 1.3 % (skin), 8.3 % -> 6.9 % (muscle p90).
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
SUPPORT_MM = 5.0
VOLUME_RATIO = (0.65, 1.5)               # per closed structure: volume after / (Z-Anatomy source volume x BODY_SCALE^3)
BODY_SCALE = 0.932                       # Q168 body scale (data/derived/Q168_zan_to_vhf.json)
TRUNK_BONE_RE = ("rib", "sternum", "xiphoid", "vertebra", "sacrum", "coccyx", "hip_bone", "clavicle", "scapula")
W0_MM, W1_MM = 150.0, 230.0               # weight 1 within W0 of a trunk bone, 0 beyond W1
RBF_SMOOTH = 3000.0
BASE_SMOOTH = 300.0                  # bone-only field: bones reproduced to ~1 mm median, fewer conflicts than the exact interpolant
CHART_SMOOTH_CELLS = 1.5             # Gaussian smoothing (5 mm x 2 deg cells) of the outline offsets
SKIN_INSET_MM = 1.0                  # skin anchors aim this far inside her CT skin (the smoothed field leaves a few mm of residual)
CLAMP_MARGIN_MM, CLAMP_MAX_MM = 0.5, 30.0
CLAMP_SMOOTH_ITERS = 4
CLAMP_SKIP_REGIONS = ("forearm_hand", "foot")
RBF_KERNEL = "thin_plate_spline"      # Q186c v2: far fewer fold-over points than "cubic" (3.6 % vs 5.3 % of samples < 0.25, min det -0.55 vs -3.9)
ANCHOR_REACH_MM = 90.0               # limb bones anchor the field only within this raw distance of a trunk bone (humeral/femoral heads)
GRID_MM = 8.0                        # the field is evaluated on this lattice and interpolated trilinearly (checked against direct evaluation)
OUT_JSON = REPO / "data" / "derived" / "Q186c_trunk_refit.json"
SKIN_ANTERIOR_DEG, SKIN_POSTERIOR_DEG, SKIN_POSTERIOR_LOW_DEG = 62.0, 122.0, 95.0
SHOULDER_Y_MM = 545.0               # above this her torso + shoulder contour is ONE outline (arms hang below it): all sectors usable   # trusted sectors of her outline: |theta| < 62 (front), > 122 (back)


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


# ----------------------------------------------------------------------------------- bone refit
VERTEBRAE = [f"t{i}" for i in range(1, 13)] + [f"l{i}" for i in range(1, 6)]


def bone_targets() -> dict:
    """{zan mesh id: TotalSegmentator `total` label id of HER CT}: ribs 1-12 l/r, vertebrae T1-L5"""
    out = {}
    for side in "lr":
        for i in range(12):
            out[rib_id(i, side)] = RIB_LABEL0[side] + i
    ids = {v: int(k) for k, v in json.loads((REPO / "mappings" / "totalsegmentator_labels.json").read_text())["labels"].items()}
    for v in VERTEBRAE:
        out[f"zan_vertebra_{v}"] = ids[f"vertebrae_{v.upper()}"]
    return out


def refit_bones(pending: list[dict], vol=None, log=print) -> dict:
    """per-bone similarity ICP of each (Q168-placed) Z-Anatomy rib / thoracic + lumbar vertebra onto its own CT
    label (partial-aware: every label point pairs with the nearest Z-Anatomy point); moves p["v"] in place.
    A bone is only moved when both one-sided medians improve."""
    from scripts.transfer.zan_to_vhf_whole_body import apply_sim, trimmed_icp, sim_scale, surface_distance
    by_id = {p["mesh_id"]: p for p in pending}
    vol = vol or load_her_vol()
    rep = {}
    for mid, lab in bone_targets().items():
        p = by_id.get(mid)
        if p is None:
            continue
        dst = rib_label_points(lab, vol)
        if len(dst) < 200:
            rep[mid] = {"status": "no label"}
            continue
        v0 = p["v"]
        rng = np.random.default_rng(lab)
        src = v0[rng.choice(len(v0), min(len(v0), 4000), replace=False)]
        dsub = dst[rng.choice(len(dst), min(len(dst), 6000), replace=False)]
        before = surface_distance(src, dst)
        best = None
        for scale_free in (True, False):
            A, t = trimmed_icp(src, dsub, np.eye(3), np.zeros(3), scale=scale_free, corr="dst", iters=60, trim=0.85)
            s = sim_scale(A)
            shift = float(np.linalg.norm(apply_sim(A, t, v0).mean(0) - v0.mean(0)))
            d = surface_distance(apply_sim(A, t, src), dst)
            ok = (RIB_SCALE_BOUNDS[0] <= s <= RIB_SCALE_BOUNDS[1] and shift <= RIB_SHIFT_MAX_MM
                  and d["b_to_a"] < before["b_to_a"] and d["a_to_b"] < before["a_to_b"])
            if ok and (best is None or d["b_to_a"] < best["d"]["b_to_a"]):
                best = {"A": A, "t": t, "scale": s, "shift": shift, "d": d, "scale_free": scale_free}
        if best is None:
            rep[mid] = {"status": "held (no bounded improvement)", "her_label_to_Z_mm": round(before["b_to_a"], 2),
                        "Z_to_her_label_mm": round(before["a_to_b"], 2)}
            continue
        p["v"] = apply_sim(best["A"], best["t"], v0)
        # vertices her label actually supports (<= SUPPORT_MM from it) may anchor the field; the unlabelled
        # ends (rib ends towards the costal cartilage) were only carried by the rigid fit
        p["anchor_mask"] = cKDTree(dst).query(p["v"])[0] <= SUPPORT_MM
        rep[mid] = {"status": "refit", "scale": round(best["scale"], 3), "shift_mm": round(best["shift"], 1),
                    "her_label_to_Z_mm_before": round(before["b_to_a"], 2), "her_label_to_Z_mm_after": round(best["d"]["b_to_a"], 2),
                    "Z_to_her_label_mm_before": round(before["a_to_b"], 2), "Z_to_her_label_mm_after": round(best["d"]["a_to_b"], 2)}
        log(f"  {mid}: {rep[mid]}")
    return rep


def refit_cartilage(pending: list[dict], log=print) -> dict:
    """Her own costal-cartilage meshes (ct_vhf `costal_cartilage_l/r`, from her CT cartilage label) as anchors: each Z-Anatomy
    costal cartilage is moved by a bounded rigid ICP onto her side mesh (a single cartilage is PART of her mesh: Z -> her
    pairing only); its vertices within SUPPORT_MM of her mesh then become field anchors (p["anchor_target"]), the cartilage
    itself is carried by the field like the other soft tissue, so its ends stay with the ribs and the sternum."""
    from scripts.transfer.zan_to_vhf_whole_body import apply_sim, trimmed_icp, sim_scale, surface_distance, load_her_meshes
    her = load_her_meshes()
    rep = {}
    for p in pending:
        mid = p["mesh_id"]
        if p["cat"] != "cartilage" or "costal_cartilage" not in mid or mid[-2:] not in ("_l", "_r"):
            continue
        hv = her.get("costal_cartilage_" + mid[-1])
        if hv is None:
            continue
        dst = hv["v"]
        v0 = p["v"]
        part = mid.startswith("zan_costal_cartilage_of")
        rng = np.random.default_rng(len(v0))
        src = v0[rng.choice(len(v0), min(len(v0), 3000), replace=False)]
        dsub = dst[rng.choice(len(dst), min(len(dst), 8000), replace=False)]
        tree = cKDTree(dst)
        before = float(np.median(tree.query(src)[0]))
        A, t = trimmed_icp(src, dsub, np.eye(3), np.zeros(3), scale=False, corr="src" if part else "sym", iters=50, trim=0.8)
        new = apply_sim(A, t, v0)
        shift = float(np.linalg.norm(new.mean(0) - v0.mean(0)))
        after = float(np.median(tree.query(new[rng.choice(len(new), min(len(new), 3000), replace=False)])[0]))
        if shift > 30.0 or after >= before:
            rep[mid] = {"status": "held", "to_her_mesh_mm": round(before, 2), "shift_mm": round(shift, 1)}
            continue
        mask = tree.query(new)[0] <= SUPPORT_MM
        if mask.sum() < 10:
            rep[mid] = {"status": "held (no supported vertices)", "to_her_mesh_mm": round(before, 2)}
            continue
        p["anchor_target"], p["anchor_mask"] = new, mask
        rep[mid] = {"status": "anchors", "to_her_mesh_mm_before": round(before, 2), "after": round(after, 2), "shift_mm": round(shift, 1),
                    "supported_vertex_fraction": round(float(mask.mean()), 2)}
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
    odd = (nh % 2 == 1) & ~np.isnan(R)               # a ray from inside leaves the body an odd number of times
    # smoothness: a fused arm / hand shows up as a jump of the first-exit radius against its neighbourhood
    Rf = np.where(np.isnan(R), np.nanmedian(R), R)
    Rp = np.pad(Rf, ((0, 0), (4, 4)), mode="wrap")
    smooth = (np.abs(Rf - ndi.median_filter(Rp, size=(5, 9), mode="nearest")[:, 4:-4]) < 18.0)
    # anterior: her hands hang in front of the hips -> keep away from multi-crossing cells; posterior (no hand behind her
    # hips/back, y < 190 from 95 deg, higher up from 122 deg): odd crossing count is enough; shoulder level: every sector
    post = np.where(Y < 190.0, SKIN_POSTERIOR_LOW_DEG, np.where(Y < 230.0, SKIN_POSTERIOR_LOW_DEG + (SKIN_POSTERIOR_DEG - SKIN_POSTERIOR_LOW_DEG) * (Y - 190.0) / 40.0, SKIN_POSTERIOR_DEG))
    multi = ndi.binary_dilation(nh != 1, structure=np.ones((5, 5), bool), iterations=2)
    trusted = ((adeg < SKIN_ANTERIOR_DEG) & ~multi & odd) | ((adeg > post) & odd & smooth) | ((Y >= SHOULDER_Y_MM) & ~multi & odd & smooth)
    return R, nh, trusted


def inpaint_theta(grid: np.ndarray, ths: np.ndarray, max_gap_deg: float = 130.0):
    """fill the NaN cells of grid[y, theta] by periodic linear interpolation along theta (her lateral outline is hidden by
    her arms: there the skin follows the offsets measured in front and behind); rows with < 8 usable cells take the
    nearest filled row.  Returns (filled grid, fraction of cells that were interpolated)"""
    out = grid.copy()
    step = np.degrees(ths[1] - ths[0])
    n = len(ths)
    for i in range(len(out)):
        ok = ~np.isnan(out[i])
        if ok.sum() < 8:
            continue
        idx = np.flatnonzero(ok)
        gaps = np.diff(np.r_[idx, idx[0] + n]) * step
        x = np.arange(n)
        filled = np.interp(x, np.r_[idx - n, idx, idx + n], np.r_[out[i, idx], out[i, idx], out[i, idx]])
        # do not bridge gaps wider than max_gap_deg
        big = np.zeros(n, bool)
        for a_, g_ in zip(idx, gaps):
            if g_ > max_gap_deg:
                big[(np.arange(a_ + 1, a_ + int(g_ / step)) % n)] = True
        out[i] = np.where(ok, out[i], np.where(big, np.nan, filled))
    rows = np.flatnonzero((~np.isnan(out)).sum(1) >= 8)
    for i in np.flatnonzero((~np.isnan(out)).sum(1) < 8):
        if len(rows):
            out[i] = out[rows[np.argmin(np.abs(rows - i))]]
    frac = float((np.isnan(grid) & ~np.isnan(out)).mean())
    return out, frac


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
    -110..560 mm in y, fading to 0 by 215 mm / 170 mm below / 640 mm above.  Continuous in position -> neighbouring
    patches and muscles never tear."""
    xc, zc = axis(q[:, 1])
    rho = np.hypot(q[:, 0] - xc, q[:, 2] - zc)
    rho1 = 215.0 + 80.0 * smoothstep((q[:, 1] - 430.0) / 90.0)      # the shoulder girdle (|x| up to ~270 mm) is inside the field's reach
    wr = smoothstep((rho1 - rho) / 50.0)
    wy = np.minimum(smoothstep((q[:, 1] + 170.0) / 60.0), smoothstep((640.0 - q[:, 1]) / 80.0))
    return wr * wy


LAMBDA_D0_MM, LAMBDA_D1_MM = 15.0, 60.0   # skin-outline share of the field: 0 within 15 mm of a trunk bone, 1 beyond 60 mm


def skin_share(d_bone: np.ndarray) -> np.ndarray:
    """share (0..1) of the skin-outline anchors in the field a non-skin vertex follows: tissue lying on a bone stays
    with the bone-only field (it conforms to her ribs/pelvis/spine and keeps its thickness, e.g. gluteus medius, serratus),
    tissue far from every bone (the abdominal wall, the fat-covered chest wall) follows her outline."""
    return smoothstep((d_bone - LAMBDA_D0_MM) / (LAMBDA_D1_MM - LAMBDA_D0_MM))


def rbf(src: np.ndarray, dst: np.ndarray, smoothing: float):
    from scipy.interpolate import RBFInterpolator
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return RBFInterpolator(src, dst - src, kernel=RBF_KERNEL, smoothing=smoothing, degree=1)


class ChartCorrection:
    """radial shift Delta(y, theta) (mm, outward positive) around her trunk axis, bilinear in the chart; call -> displacement"""

    def __init__(self, delta: np.ndarray, ys: np.ndarray, ths: np.ndarray, axis):
        self.delta, self.ys, self.ths, self.axis = delta, ys, ths, axis

    def __call__(self, p: np.ndarray) -> np.ndarray:
        xc, zc = self.axis(p[:, 1])
        th = np.arctan2(p[:, 0] - xc, p[:, 2] - zc)
        d = bilinear(self.delta, self.ys, self.ths, p[:, 1], th)
        out = np.zeros_like(p)
        out[:, 0], out[:, 2] = d * np.sin(th), d * np.cos(th)
        return out


class Composite:
    """p -> base displacement + chart correction evaluated at the base-moved point (displacement from the raw point)"""

    def __init__(self, base, corr):
        self.base, self.corr = base, corr

    def __call__(self, p: np.ndarray) -> np.ndarray:
        b = self.base(p)
        return b + self.corr(p + b)


class GridField:
    """`f` evaluated on a GRID_MM lattice over the cells that hold the given points, trilinear in between (the fields are
    smooth: checked against direct evaluation in the report). Call with the same points."""

    def __init__(self, f, pts: np.ndarray, step: float = GRID_MM):
        self.f, self.step = f, step
        self.lo = np.floor(pts.min(0) / step).astype(int) - 1
        cells = np.unique(np.floor(pts / step).astype(int) - self.lo, axis=0)
        off = np.array([[a, b, c] for a in (0, 1) for b in (0, 1) for c in (0, 1)])
        nodes = np.unique((cells[:, None, :] + off[None]).reshape(-1, 3), axis=0)
        self.shape = tuple(nodes.max(0) + 2)
        self.val = np.full(self.shape + (3,), np.nan)
        pos = (nodes + self.lo) * step
        self.val[tuple(nodes.T)] = np.vstack([f(pos[i:i + 20000]) for i in range(0, len(pos), 20000)])
        self.n_nodes = len(nodes)

    def __call__(self, p: np.ndarray) -> np.ndarray:
        g = p / self.step - self.lo
        i0 = np.floor(g).astype(int); t = g - i0
        out = np.zeros_like(p)
        for a in (0, 1):
            for b in (0, 1):
                for c in (0, 1):
                    w = (t[:, 0] if a else 1 - t[:, 0]) * (t[:, 1] if b else 1 - t[:, 1]) * (t[:, 2] if c else 1 - t[:, 2])
                    out += w[:, None] * self.val[i0[:, 0] + a, i0[:, 1] + b, i0[:, 2] + c]
        return out


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
             "border_of_forearm", "foveola", "sternocleido", "muscular_triangle", "anal", "gluteal_fold")
SKIN_HAND = ("forearm", "wrist", "hand", "digits", "palm", "nail", "perionyx", "radial_foveola")   # never moved by the field
FIELD_SKIP_REGIONS = ("forearm_hand", "foot")                                                      # Q168 regions never moved


def trunk_skin_ids(pending: list[dict]) -> list[str]:
    """Z-Anatomy skin patches of the trunk (by name + position in her frame): thorax, abdomen, back, flanks, groin"""
    out = []
    for p in pending:
        if p["cat"] != "skin":
            continue
        c = p["v"].mean(0)
        if (-30 < c[1] < 600 and (abs(c[0]) < 160 or "hip_region" in p["mesh_id"] or "deltoid_region" in p["mesh_id"])
                and not any(s in p["mesh_id"] for s in SKIN_LIMB)):
            out.append(p["mesh_id"])
    return out


# ----------------------------------------------------------------------------------- the refit
def _sample_bones(pending, raw, step=16.0, reach=ANCHOR_REACH_MM):
    """one anchor per `step` mm voxel of every bone near the trunk (raw Z-Anatomy position -> final position), plus the
    label-supported costal cartilage vertices (p["anchor_target"]).  Limb bones (humerus, femur, hand, foot ...) enter only
    within `reach` mm (raw) of a trunk bone: their raw pose differs from hers by up to 300 mm and would shear the field."""
    core = [raw[p["mesh_id"]][::4] for p in pending if p["cat"] == "bone" and any(t in p["mesh_id"] for t in TRUNK_BONE_RE)
            and "phalanx" not in p["mesh_id"] and "metacarpal" not in p["mesh_id"]]
    core_tree = cKDTree(np.vstack(core))
    src, dst, ids = [], [], []
    for p in pending:
        tgt = p.get("anchor_target")
        if (p["cat"] != "bone" and tgt is None) or p["mesh_id"] not in raw:
            continue
        if p["cat"] == "bone" and not (-320 < p["v"][:, 1].mean() < 780):
            continue
        ok = p.get("anchor_mask")
        r = raw[p["mesh_id"]]
        vv = p["v"] if tgt is None else tgt
        if ok is not None:
            r, vv = r[ok], vv[ok]
        if p["cat"] == "bone" and not any(t in p["mesh_id"] for t in TRUNK_BONE_RE) and len(r):
            near = core_tree.query(r)[0] <= reach
            r, vv = r[near], vv[near]
        if len(r) < 3:
            continue
        _, j = np.unique(np.floor(r / step).astype(int), axis=0, return_index=True)
        src.append(r[j]); dst.append(vv[j]); ids += [p["mesh_id"]] * len(j)
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
    base = rbf(bs, bd, BASE_SMOOTH)
    rep["rbf"]["bone_anchors"] = int(len(bs))
    rep["bone_anchor_residual_mm"] = _res(base, bs, bd)

    # 2. skin anchors: base position of each trunk-skin vertex -> her outline along the horizontal ray from her axis
    ys = np.arange(-140.0, 641.0, 5.0); ths = np.radians(np.arange(-180.0, 180.0, 2.0))
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
    delta_grid, interp_frac = inpaint_theta(delta_grid, ths)     # her hidden lateral outline: interpolate the neighbouring offsets
    d = bilinear(delta_grid, ys, ths, allS[:, 1], th)
    trust_v = ~np.isnan(d)
    # cap the single-vertex shift (bounded displacement): |delta| <= 90 mm
    cap = np.abs(d) <= 90.0
    use = trust_v & cap
    t_pts = allS.copy()
    t_pts[use, 0] += (d[use] - SKIN_INSET_MM) * np.sin(th[use]); t_pts[use, 2] += (d[use] - SKIN_INSET_MM) * np.cos(th[use])
    raw_all = np.vstack([raw[k] for k in sk_ids])
    # one anchor per 5 mm voxel (the shells are dense)
    key = np.floor(raw_all[use] / 5.0).astype(int)
    _, first = np.unique(key, axis=0, return_index=True)
    sk_src, sk_dst = raw_all[use][first], t_pts[use][first]
    rep["skin_anchors"] = {"patches": len(sk_ids), "vertices": int(len(raw_all)), "with_her_outline": int(use.sum()),
                           "anchors_used": int(len(first)),
                           "outline_shift_mm": {"median": round(float(np.median(d[use])), 1), "p10": round(float(np.percentile(d[use], 10)), 1),
                                                "p90": round(float(np.percentile(d[use], 90)), 1)},
                           "trusted_cell_fraction": round(float(trusted.mean()), 3), "interpolated_cell_fraction": round(float(interp_frac), 3)}
    log(f"  trunk skin: {len(sk_ids)} patches, {use.sum()} of {len(raw_all)} vertices carry her outline, shift {rep['skin_anchors']['outline_shift_mm']}")

    # 3. final field = bone-only field + radial outline correction in her trunk chart (no 3-D interpolant over the
    #    skin anchors: those conflicted with the bone anchors in the lateral band and folded; the chart shift is a smooth
    #    function of (height, angle) only, so it cannot fold while |grad| < 1)
    dg = np.nan_to_num(delta_grid, nan=0.0)
    dg = ndi.gaussian_filter(dg, sigma=(CHART_SMOOTH_CELLS, CHART_SMOOTH_CELLS), mode=("nearest", "wrap")) - SKIN_INSET_MM
    dg = np.clip(dg, -90.0, 90.0)
    corr = ChartCorrection(dg, ys, ths, axis)
    direct_base = base
    field = Composite(direct_base, corr)
    grid_pts = _jac_grid(pending, raw, axis)
    jac = jacobian_stats(field, grid_pts)
    rep["jacobian"] = {**jac}
    log(f"  field (bone TPS + chart correction): Jacobian {jac}")
    slope = np.hypot(np.gradient(dg, 5.0, axis=0), np.gradient(dg, np.degrees(ths[1] - ths[0]) * np.pi / 180 * 150.0, axis=1))
    rep["chart_correction"] = {"smooth_cells": CHART_SMOOTH_CELLS, "inset_mm": SKIN_INSET_MM, "max_slope": round(float(slope.max()), 2),
                               "p99_slope": round(float(np.percentile(slope, 99)), 2)}
    rep["layer_rule"] = {"skin_share_d0_mm": LAMBDA_D0_MM, "skin_share_d1_mm": LAMBDA_D1_MM}
    rep["bone_anchor_residual_final_mm"] = _res(direct_base, bs, bd)
    rep["skin_anchor_residual_mm"] = _res(field, sk_src, sk_dst)
    A_src, A_dst = np.vstack([bs, sk_src]), np.vstack([bd, sk_dst])

    # 4. apply to every non-bone vertex with the position weight
    moved, stat = 0, {}
    vol_ratios, guarded = [], {}
    tb = [p["v"] for p in pending if p["cat"] == "bone" and any(t in p["mesh_id"] for t in TRUNK_BONE_RE)]
    bone_tree = cKDTree(np.vstack([b[::3] for b in tb]))
    regions = json.loads((REPO / "data" / "derived" / "Q168_zan_to_vhf.json").read_text())["region_of_structure"]
    todo = []
    for p in pending:
        if p["cat"] == "bone" or regions.get(p["mesh_id"]) in FIELD_SKIP_REGIONS or (p["cat"] == "skin" and any(s in p["mesh_id"] for s in SKIN_HAND)):
            continue
        w = trunk_weight(p["v"], axis)
        if (w > 1e-3).any():
            todo.append((p, w))
    pts_all = np.vstack([raw[p["mesh_id"]][w > 1e-3] for p, w in todo])
    direct_field = field
    field, base = GridField(direct_field, pts_all), GridField(direct_base, pts_all)
    chk = pts_all[np.random.default_rng(0).choice(len(pts_all), 3000, replace=False)]
    err = np.linalg.norm(field(chk) - direct_field(chk), axis=1)
    rep["grid_interpolation_error_mm"] = {"nodes": int(field.n_nodes), "step_mm": GRID_MM, "median": round(float(np.median(err)), 3), "max": round(float(err.max()), 2)}
    log(f"  grid field {field.n_nodes} nodes, error vs direct {rep['grid_interpolation_error_mm']}")
    for p, w in todo:
        q = p["v"]
        sel = w > 1e-3
        r_sel = raw[p["mesh_id"]][sel]
        f_full = apply_rbf(field, r_sel)
        if p["cat"] == "skin":
            cands = [("field", 1.0, f_full)]
        else:
            f_base = apply_rbf(base, r_sel)
            lam = skin_share(bone_tree.query(q[sel])[0])
            cands = [("field", g, f_base + g * lam[:, None] * (f_full - f_base)) for g in (1.0, 0.5, 0.0)]
        closed = _closed(p["f"]) and _vol(raw[p["mesh_id"]], p["f"]) > 1000.0
        ref = BODY_SCALE ** 3 * _vol(raw[p["mesh_id"]], p["f"]) if closed else None
        best = None
        options = []
        for n, g, f_new in cands:   # volume guard: closed structures keep 0.65-1.5 x the Z-Anatomy volume at her body scale
            new = q.copy(); new[sel] = q[sel] + w[sel, None] * (f_new - q[sel]); options.append((n, g, new))
        if p.get("anchor_target") is not None:
            options.append(("rigid onto her cartilage mesh", 0.0, p["anchor_target"].copy()))
        options.append(("Q168 position", 0.0, q.copy()))
        for n, gain, new in options:
            ratio = _vol(new, p["f"]) / ref if closed else None
            dev = abs(np.log(ratio)) if closed else 0.0
            if best is None or dev < best[0] - 1e-9:
                best = (dev, gain, new, ratio, n)
            if not closed or VOLUME_RATIO[0] <= ratio <= VOLUME_RATIO[1]:
                best = (dev, gain, new, ratio, n)
                break
        _, gain, new, ratio, how = best
        if closed:
            vol_ratios.append(ratio)
            if gain < 1.0 or how != "field":
                guarded[p["mesh_id"]] = {"carried_by": how, "skin_gain": gain, "volume_ratio_vs_source": round(float(ratio), 2)}
        stat[p["mesh_id"]] = {"w_mean": float(w.mean()), "shift_med": float(np.median(np.linalg.norm(new - q, axis=1)[sel])),
                              "shift_max": float(np.linalg.norm(new - q, axis=1).max())}
        p["v"] = new
        moved += 1
    rep["structures_moved"] = moved
    vr = np.asarray(vol_ratios)
    rep["volume_guard"] = {"bounds": list(VOLUME_RATIO), "closed_structures": int(len(vr)),
                           "ratio_median": round(float(np.median(vr)), 3), "ratio_p10": round(float(np.percentile(vr, 10)), 3),
                           "ratio_p90": round(float(np.percentile(vr, 90)), 3), "ratio_max": round(float(vr.max()), 3),
                           "structures_with_reduced_skin_share": guarded}
    rep["shift_vs_q168_mm"] = {"median_of_structure_medians": round(float(np.median([s["shift_med"] for s in stat.values()])), 1),
                               "max": round(float(max(s["shift_max"] for s in stat.values())), 1)}
    rep["_per_structure_shift"] = stat
    rep["_field"], rep["_grid"], rep["_anchors"], rep["_axis"], rep["_base"] = field, grid_pts, (A_src, A_dst), axis, base
    rep["_parts"] = dict(bs=bs, bd=bd, sk_src=sk_src, sk_dst=sk_dst, direct_base=direct_base)
    return rep


def _smooth_clamp(v: np.ndarray, new: np.ndarray, f: np.ndarray, skin_mesh) -> np.ndarray:
    """spread the clamp displacement over the mesh neighbours (CLAMP_SMOOTH_ITERS Laplacian passes, moving vertices keep
    at least their own clamp), then re-clamp whatever is still outside her skin: no facets where a patch crosses her skin"""
    from scipy import sparse
    D = new - v
    moved = np.linalg.norm(D, axis=1) > 0
    if not moved.any():
        return new
    n = len(v)
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    deg = np.asarray(A.sum(1)).ravel()
    Ds = D.copy()
    for _ in range(CLAMP_SMOOTH_ITERS):
        Ds = np.where(deg[:, None] > 0, (A @ Ds) / np.maximum(deg, 1)[:, None], Ds)
        Ds[moved] = np.where(np.linalg.norm(Ds[moved], axis=1)[:, None] > np.linalg.norm(D[moved], axis=1)[:, None], Ds[moved], D[moved])
    cand = v + Ds
    near = np.flatnonzero(np.linalg.norm(Ds, axis=1) > 1e-6)
    still = near[~skin_mesh.contains(cand[near])] if len(near) else near
    cand[still] = new[still]
    return cand


def clamp_inside_skin(pending: list[dict], skin_mesh=None, log=print) -> dict:
    """Last guard (gate: 0 % outside her skin): every non-bone vertex that still lies outside her CT skin is moved to the
    nearest point of her skin surface, CLAMP_MARGIN_MM inside it; moves above CLAMP_MAX_MM are left (reported).
    Forearm/hand and foot regions (no usable outline) are skipped."""
    from scripts.ribs_from_ct_labels import load_skin
    skin_mesh = skin_mesh or load_skin("vhf")
    regions = json.loads((REPO / "data" / "derived" / "Q168_zan_to_vhf.json").read_text())["region_of_structure"]
    tree = cKDTree(np.asarray(skin_mesh.vertices, np.float64))
    from trimesh.proximity import closest_point
    rep_, n_out, n_tot, left = {}, 0, 0, {}
    for p in pending:
        if p["cat"] == "bone" or regions.get(p["mesh_id"]) in CLAMP_SKIP_REGIONS or any(s in p["mesh_id"] for s in SKIN_HAND):
            continue
        v = p["v"]
        n_tot += len(v)
        near = tree.query(v)[0] < 45.0                     # farther than this from her skin = deep inside
        idx = np.flatnonzero(near)
        if not len(idx):
            continue
        out = idx[~skin_mesh.contains(v[idx])]
        if not len(out):
            continue
        cp, _, tri = closest_point(skin_mesh, v[out])
        nrm = skin_mesh.face_normals[tri]
        tgt = cp - CLAMP_MARGIN_MM * nrm
        mv = np.linalg.norm(tgt - v[out], axis=1)
        ok = mv <= CLAMP_MAX_MM
        new = v.copy(); new[out[ok]] = tgt[ok]
        new = _smooth_clamp(v, new, p["f"], skin_mesh)
        p["v_unclamped"] = v
        p["v"] = new
        n_out += int(ok.sum())
        rep_[p["mesh_id"]] = {"vertices_moved": int(ok.sum()), "fraction": round(float(ok.sum() / len(v)), 4), "median_mm": round(float(np.median(mv[ok])), 1) if ok.any() else 0.0,
                              "max_mm": round(float(mv[ok].max()), 1) if ok.any() else 0.0}
        if (~ok).any():
            left[p["mesh_id"]] = int((~ok).sum())
    log(f"  clamp inside her skin: {n_out} of {n_tot} vertices in {len(rep_)} structures; left (> {CLAMP_MAX_MM} mm): {sum(left.values())}")
    return {"margin_mm": CLAMP_MARGIN_MM, "max_move_mm": CLAMP_MAX_MM, "vertices_moved": n_out, "vertices_total": n_tot,
            "structures": len(rep_), "left_over_max": left, "per_structure": rep_}


def _flip_frac(v_raw: np.ndarray, v_new: np.ndarray, f: np.ndarray) -> float:
    """share of faces whose normal turned against the Z-Anatomy source normal (fold-over indicator)"""
    def nrm(v):
        n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        a = np.linalg.norm(n, axis=1)
        return n / np.maximum(a[:, None], 1e-12), a
    n0, a0 = nrm(v_raw)
    n1, _ = nrm(v_new)
    ok = a0 > 1e-6
    return float((np.einsum("ij,ij->i", n0, n1)[ok] < 0).mean())


def mesh_flip_stats(pending: list[dict], raw: dict, before: dict) -> dict:
    """fold-over of the moved structures against their raw source: Q168 position (`before`) vs the refit; skin by faces,
    muscles per structure (median / p90)"""
    out = {}
    trunk_sk = set(trunk_skin_ids(pending))
    for name, sel in (("skin_all_patches", lambda p: p["cat"] == "skin"), ("skin_trunk_patches", lambda p: p["mesh_id"] in trunk_sk),
                      ("muscle", lambda p: p["cat"] == "muscle")):
        ps = [p for p in pending if sel(p) and p["mesh_id"] in before]
        fb = np.array([_flip_frac(raw[p["mesh_id"]], before[p["mesh_id"]], p["f"]) for p in ps])
        fa = np.array([_flip_frac(raw[p["mesh_id"]], p["v"], p["f"]) for p in ps])
        nf = np.array([len(p["f"]) for p in ps], float)
        out[name] = {"structures": len(ps), "face_weighted_before": round(float((fb * nf).sum() / nf.sum()), 4),
                     "face_weighted_after": round(float((fa * nf).sum() / nf.sum()), 4),
                     "median_before": round(float(np.median(fb)), 4), "median_after": round(float(np.median(fa)), 4),
                     "p90_before": round(float(np.percentile(fb, 90)), 4), "p90_after": round(float(np.percentile(fa, 90)), 4)}
    return out


def _vol(v: np.ndarray, f: np.ndarray) -> float:
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum())) / 6.0


def _closed(f: np.ndarray) -> bool:
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    return bool((np.unique(e, axis=0, return_counts=True)[1] == 2).all())


def _res(f, src, dst) -> dict:
    e = np.linalg.norm(apply_rbf(f, src) - dst, axis=1)
    return {"median": round(float(np.median(e)), 2), "p90": round(float(np.percentile(e, 90)), 2), "max": round(float(e.max()), 2)}


def _jac_grid(pending, raw, axis, step=16.0):
    """raw-space grid cells holding trunk-weighted (w > 0.05) non-bone vertices: the places the field is used"""
    pts = []
    for p in pending:
        if p["cat"] == "bone" or p["mesh_id"] not in raw:
            continue
        w = trunk_weight(p["v"], axis)
        pts.append(raw[p["mesh_id"]][w > 0.05][::5])
    pts = np.vstack(pts)
    key = np.unique(np.floor(pts / step).astype(int), axis=0)
    return (key + 0.5) * step
