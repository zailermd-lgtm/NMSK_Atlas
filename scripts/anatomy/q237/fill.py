"""Q237 step 3: FILL a missing / defective side as the MIRROR of the opposite (measured, good) side about the midsagittal plane, fitted to this side's own bones.
Never touches a structure that is validly measured (that is only ever a recommendation).
Pipeline per structure: mirror (plane reflection, winding reversed) -> rigid + uniform scale from the NEIGHBOURING bones (the same bones, mirrored side onto this side; symmetric trimmed ICP,
scripts/anatomy/q235/register.py) -> bounded conform (out of bones, inside the skin) -> guards (signed distances): inside the skin >= SKIN_MIN_MM, bones (muscle: <= BELLY_IN_BONE_MAX % of the
vertices and <= BONE_DEPTH_MAX_MM inside bone, as the Q214/Q216 pipeline; vessels / nerves / organs: no vertex inside bone and >= BONE_CLEAR_MM from it), overlap with other muscles <= OVERLAP_MAX % of
the volume (2 mm voxels, as the Q204 audit), bone-registration error, scale / rotation bounds. A candidate that fails ANY guard is held with its reasons."""
from __future__ import annotations
import re, sys
from pathlib import Path
import numpy as np
import trimesh
from scipy.spatial import cKDTree
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C  # noqa: E402
REPO = C.REPO
from scripts.anatomy.q235 import register as R  # noqa: E402

SKIN_MIN_MM = 1.0           # every vertex inside the skin and at least this deep (Q214 SKIN_DEPTH_MIN_MM)
BELLY_IN_BONE_MAX = 8.0     # muscle: % of vertices inside any bone (Q216 gate)
BONE_DEPTH_MAX_MM = 5.0     # muscle: deepest embedding (Q204 regional pass counts > 5 mm as a defect)
ATTACH_LIKE = ("muscle", "fascia", "ligament", "tendon", "joint", "cartilage", "insertion", "bursa")     # attach to bone by design: embedding rule instead of the clearance rule
BONE_CLEAR_MM = 1.0         # vessel / nerve / organ / ligament: no vertex inside bone, >= this from it
OVERLAP_MAX = 60.0          # muscle: % of the volume inside other muscles (Q214 gate; the Q198 / Q204 severity-1 line is 40 %)
BONE_REG_MEDIAN_MAX = 4.0   # registration of the mirrored neighbouring bones onto this side's: median residual (mm)
BONE_REG_P90_MAX = 9.0
SCALE_RANGE = (0.85, 1.18)
ROT_MAX_DEG = 30.0
CONFORM_MAX_MM = 6.0        # largest vertex displacement of the conform step
MIN_NEIGH_FRACTION = 0.08   # a bone is a neighbour when >= this share of the structure lies within NEIGH_MM of it
NEIGH_MM = 30.0


def _wt(v, f):
    return trimesh.Trimesh(v, f, process=False)


class Page:
    """a page's structures + the signed-distance contexts (skin, bones, muscles)"""
    def __init__(self, key, plane=None):
        self.key = key
        self.S = C.load(key); self.G = C.groups_of(self.S)
        if plane is None:
            plane, self.q = C.fit_midsagittal(self.S)
        else:
            self.q = None
        self.plane = plane
        self.by_id = {}
        for x in self.S: self.by_id.setdefault(x["id"], []).append(x["idx"])
        sk = [x["idx"] for x in self.S if x["sys"] == "skin" or x["id"] == "skin"]
        v, f = C.merge(self.S, sk)
        self.skin = _wt(v, f)
        self.skin_pts = C.area_samples(v, f, 400000, np.random.default_rng(3))
        self.skin_tree = cKDTree(self.skin_pts)
        self._bone_cache = {}
        self._sol = {}
        self._rays = None

    # ---------------- bones
    def bone_group(self, canon, side):
        k = ("bone", canon, side)
        return self.G.get(k)

    def bone_pts(self, canon, side, n=3500):
        k = (canon, side)
        if k not in self._bone_cache:
            ids = self.bone_group(canon, side)
            v, f = C.merge(self.S, ids)
            self._bone_cache[k] = C.area_samples(v, f, n, np.random.default_rng(5))
        return self._bone_cache[k]

    def all_bone_mesh(self, lo, hi, margin=12.0):
        """merged bones whose bounding box meets [lo,hi]+margin (for the in-bone test)"""
        idx = []
        for x in self.S:
            if x["sys"] != "bone" or len(x["v"]) == 0: continue
            if (x["v"].max(0) < lo - margin).any() or (x["v"].min(0) > hi + margin).any(): continue
            idx.append(x["idx"])
        if not idx: return None, None
        v, f = C.merge(self.S, idx)
        pts = C.area_samples(v, f, int(min(80000, 400 + 0.5 * len(f))), np.random.default_rng(7))
        return _wt(v, f), cKDTree(pts)


# ---------------- inside tests: majority parity of 6 axis rays (robust to small holes)
def inside(mesh, pts):
    if mesh is None or len(pts) == 0:
        return np.zeros(len(pts), bool)
    dirs = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    votes = np.zeros(len(pts), int)
    for d in dirs:
        o = pts + d * 1e-3
        loc, ir, _ = mesh.ray.intersects_location(o, np.tile(d, (len(pts), 1)), multiple_hits=True)
        cnt = np.bincount(ir, minlength=len(pts)) if len(ir) else np.zeros(len(pts), int)
        votes += (cnt % 2 == 1)
    return votes >= 4


def enclosed(mesh, pts):
    """inside the body envelope: the skin surface is hit along ALL six axis rays (the Z skin regions are open / double-walled patches, so crossing parity is meaningless there)"""
    dirs = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], float)
    hit = np.zeros(len(pts), int)
    for d in dirs:
        o = pts + d * 1e-3
        ok = mesh.ray.intersects_any(o, np.tile(d, (len(pts), 1)))
        hit += ok.astype(int)
    return hit == 6


def guards(P, V, F, sys_, exclude_ids=(), side_note=""):
    """signed-distance guards of one structure on a page -> dict(pass, fails, numbers)"""
    lo, hi = V.min(0), V.max(0)
    g = {}
    ins = enclosed(P.skin, V)
    d_skin = P.skin_tree.query(V)[0]
    g["inside_skin_pct"] = round(100 * float(ins.mean()), 1)
    g["skin_depth_min_mm"] = round(float(d_skin[ins].min()), 2) if ins.any() else 0.0
    g["skin_outside_max_mm"] = round(float(d_skin[~ins].max()), 2) if (~ins).any() else 0.0
    bm, bt = P.all_bone_mesh(lo, hi)
    if bm is not None:
        ib = inside(bm, V)
        db = bt.query(V)[0]
        g["in_bone_pct"] = round(100 * float(ib.mean()), 2)
        g["bone_deepest_mm"] = round(float(db[ib].max()), 2) if ib.any() else 0.0
        g["bone_min_clear_mm"] = round(float(db[~ib].min()), 2) if (~ib).any() else 0.0
    else:
        g["in_bone_pct"] = 0.0; g["bone_deepest_mm"] = 0.0; g["bone_min_clear_mm"] = 99.0
    fails = []
    if g["inside_skin_pct"] < 100.0 or g["skin_depth_min_mm"] < SKIN_MIN_MM:
        fails.append(f"skin: {g['inside_skin_pct']} % of the vertices inside, shallowest {g['skin_depth_min_mm']} mm (gate: all inside, >= {SKIN_MIN_MM} mm)")
    if sys_ in ATTACH_LIKE:
        if g["in_bone_pct"] > BELLY_IN_BONE_MAX or g["bone_deepest_mm"] > BONE_DEPTH_MAX_MM:
            fails.append(f"bone: {g['in_bone_pct']} % of the vertices inside bone, deepest {g['bone_deepest_mm']} mm (gate: <= {BELLY_IN_BONE_MAX} %, <= {BONE_DEPTH_MAX_MM} mm)")
    else:
        if g["in_bone_pct"] > 0 or g["bone_min_clear_mm"] < BONE_CLEAR_MM:
            fails.append(f"bone: {g['in_bone_pct']} % of the vertices inside bone, nearest {g['bone_min_clear_mm']} mm (gate: none inside, >= {BONE_CLEAR_MM} mm clear)")
    if sys_ == "muscle":
        g["overlap_other_muscles_pct"] = overlap_pct(P, V, F, exclude_ids)
        if g["overlap_other_muscles_pct"] > OVERLAP_MAX:
            fails.append(f"overlap: {g['overlap_other_muscles_pct']} % of its volume inside other muscles (gate: <= {OVERLAP_MAX} %)")
    g["fails"] = fails; g["pass"] = not fails
    return g


def _vox(v, f, lo, shape, pitch):
    """voxel solid of a surface (shell from dense samples, sealed by one voxel, exterior flood-filled, eroded back) + validity: it must enclose something (solid >= 35 % of the shell voxel count)"""
    A = C.area(v, f)
    n = int(min(max(4.0 * A / pitch ** 2, 3000), 250000))
    p = C.area_samples(v, f, n, np.random.default_rng(11))
    ix = np.clip(np.floor((p - lo) / pitch).astype(int), 0, np.array(shape) - 1)
    sh = np.zeros(shape, bool); sh[ix[:, 0], ix[:, 1], ix[:, 2]] = True
    sd = ndi.binary_dilation(sh, iterations=1)
    lab, _ = ndi.label(~sd)
    sol = ndi.binary_erosion(lab != lab[0, 0, 0], iterations=1)
    return sol, bool(sol.sum() >= 8 and sol.sum() >= 0.35 * sh.sum()), sh


def lattice_solid(v, f, pitch=2.0):
    """solid on a lattice aligned to multiples of `pitch` (so grids of different structures line up): (lo index, solid, ok, shell)"""
    lo = np.floor((v.min(0) - 4) / pitch).astype(int); hi = np.ceil((v.max(0) + 4) / pitch).astype(int)
    shape = tuple((hi - lo + 1).tolist())
    sol, ok, sh = _vox(v, f, lo * pitch, shape, pitch)
    return lo, sol, ok, sh


def _paste(canvas, lo_c, arr, lo_a):
    """OR `arr` (lattice origin lo_a) into `canvas` (origin lo_c) where they overlap"""
    a0 = np.maximum(lo_c, lo_a); a1 = np.minimum(lo_c + np.array(canvas.shape), lo_a + np.array(arr.shape))
    if (a1 <= a0).any(): return
    c = tuple(slice(int(a0[i] - lo_c[i]), int(a1[i] - lo_c[i])) for i in range(3)); r = tuple(slice(int(a0[i] - lo_a[i]), int(a1[i] - lo_a[i])) for i in range(3))
    canvas[c] |= arr[r]


def overlap_pct(P, V, F, exclude_ids=(), pitch=2.0):
    """share of the structure inside OTHER muscles (2 mm voxels, as the Q204 audit): volume share when its surface encloses a solid, else the share of its surface voxels"""
    lo, me, ok, shell = lattice_solid(V, F, pitch)
    other = np.zeros(me.shape, bool)
    vmin, vmax = V.min(0) - 4, V.max(0) + 4
    for x in P.S:
        if x["sys"] != "muscle" or x["id"] in exclude_ids: continue
        if (x["v"].max(0) < vmin).any() or (x["v"].min(0) > vmax).any(): continue
        c = P._sol.get(x["idx"])
        if c is None:
            c = P._sol[x["idx"]] = lattice_solid(x["v"], x["f"], pitch)
        _paste(other, lo, c[1], c[0])
    if ok:
        return round(100 * float((me & other).sum() / me.sum()), 1)
    return round(100 * float((shell & other).sum() / max(shell.sum(), 1)), 1)


# ---------------- neighbouring bones and the similarity fit
def neighbour_bones(P, X, src_side, tgt_side):
    """bone groups near the source structure X: [(canon, src_side_used, tgt_side_used, fraction)]"""
    rng = np.random.default_rng(1)
    Xs = X[rng.choice(len(X), size=min(len(X), 800), replace=False)]
    out = []
    for (sy, cn, sd), ids in P.G.items():
        if sy != "bone" or sd not in (src_side, "m"): continue
        d = cKDTree(P.bone_pts(cn, sd, 3500)).query(Xs)[0]
        fr = float((d <= NEIGH_MM).mean())
        if fr >= MIN_NEIGH_FRACTION:
            tsd = tgt_side if sd == src_side else "m"
            if ("bone", cn, tsd) in P.G:
                out.append((cn, sd, tsd, fr))
    out.sort(key=lambda t: -t[3])
    return out[:3]


def fit_to_bones(P, Xm, neigh):
    """similarity T = (s, R, t) mapping the MIRRORED source bones onto this side's bones (symmetric trimmed ICP, several starts). Xm = mirrored structure vertices (for the start)."""
    A = np.vstack([P.plane.reflect(P.bone_pts(cn, sd)) if sd != "m" else P.plane.reflect(P.bone_pts(cn, sd)) for cn, sd, tsd, fr in neigh])
    B = np.vstack([P.bone_pts(cn, tsd) for cn, sd, tsd, fr in neigh])
    best = None
    for pitch, yaw in ((0, 0), (12, 0), (-12, 0), (0, 12), (0, -12)):
        R0 = R.rot(pitch, yaw)
        t0 = B.mean(0) - R0 @ A.mean(0)
        T, dd = R.sym_icp(A, B, (1.0, R0, t0), iters=50, margin=15.0)
        sc = float(np.median(dd))
        if best is None or sc < best[0]:
            best = (sc, T, dd)
    T = best[1]
    P_ = R.apply(T, A)
    d_ab = cKDTree(B).query(P_)[0]; d_ba = cKDTree(P_).query(B)[0]
    dd = np.concatenate([d_ab, d_ba])
    s, Rm, t = T
    ang = float(np.degrees(np.arccos(np.clip((np.trace(Rm) - 1) / 2, -1, 1))))
    return T, dict(bone_residual_median_mm=round(float(np.median(dd)), 2), bone_residual_p90_mm=round(float(np.percentile(dd, 90)), 2), scale=round(float(s), 4), rotation_deg=round(ang, 1),
                   translation_mm=round(float(np.linalg.norm(t)), 1), n_points=int(len(A)))


def _conform_once(P, V, F, sys_):
    """bounded corrections: vertices inside a bone pushed out to 1 mm clear (<= CONFORM_MAX_MM), vertices outside / too close to the skin pulled to SKIN_MIN_MM + 0.3 mm inside; the displacement
    field is smoothed. Returns V2 and the displacement statistics."""
    V0 = V.copy(); V = V.copy()
    lo, hi = V.min(0), V.max(0)
    cen = V.mean(0)
    disp = np.zeros_like(V)
    bm, bt = P.all_bone_mesh(lo, hi)
    if bm is not None:
        ib = inside(bm, V)
        if ib.any():
            _, q = None, None
            cp, _, _ = trimesh.proximity.closest_point(bm, V[ib])
            vec = cp - V[ib]; n = np.linalg.norm(vec, axis=1, keepdims=True) + 1e-9
            disp[ib] += vec + vec / n * (1.0 if sys_ not in ATTACH_LIKE else 0.0)         # out of the bone (non-muscle: and 1 mm clear)
        if sys_ not in ATTACH_LIKE:
            db = bt.query(V)[0]; near = (~ib) & (db < BONE_CLEAR_MM + 0.3)
            if near.any():
                cp, _, _ = trimesh.proximity.closest_point(bm, V[near]); vec = V[near] - cp; n = np.linalg.norm(vec, axis=1, keepdims=True) + 1e-9
                disp[near] += vec / n * (BONE_CLEAR_MM + 0.3 - db[near])[:, None]
    ins = enclosed(P.skin, V); dsk, isk = P.skin_tree.query(V)
    bad = (~ins) | (dsk < SKIN_MIN_MM + 0.3)
    if bad.any():
        q = P.skin_pts[isk[bad]]
        inward = cen - q; inward /= (np.linalg.norm(inward, axis=1, keepdims=True) + 1e-9)
        target = q + inward * (SKIN_MIN_MM + 0.5)
        disp[bad] += target - V[bad]
    # smooth the displacement field over the mesh (a few neighbour-averaging passes), bounded
    nz = np.linalg.norm(disp, axis=1) > 0
    if nz.any():
        e = np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
        for _ in range(4):
            acc = np.zeros_like(disp); cnt = np.zeros(len(V))
            np.add.at(acc, e[:, 0], disp[e[:, 1]]); np.add.at(acc, e[:, 1], disp[e[:, 0]])
            np.add.at(cnt, e[:, 0], 1); np.add.at(cnt, e[:, 1], 1)
            sm = acc / np.maximum(cnt, 1)[:, None]
            disp = np.where(nz[:, None], np.maximum(np.abs(disp), 0) * 0 + disp, 0.5 * disp + 0.5 * sm)
            # vertices that needed a correction keep it; the rest follow their neighbours
    mag = np.linalg.norm(disp, axis=1)
    scale = np.minimum(1.0, CONFORM_MAX_MM / np.maximum(mag, 1e-9))
    V2 = V + disp * scale[:, None]
    m = np.linalg.norm(V2 - V0, axis=1)
    return V2, dict(conform_mean_mm=round(float(m.mean()), 2), conform_max_mm=round(float(m.max()), 2), conform_moved_pct=round(100 * float((m > 0.05).mean()), 1))


def conform(P, V, F, sys_, passes=3):
    """_conform_once repeated (each pass re-measures the signed distances) until nothing moves; the total displacement stays bounded by CONFORM_MAX_MM"""
    V0 = V.copy(); cur = V.copy(); st = None
    for _ in range(passes):
        nxt, st = _conform_once(P, cur, F, sys_)
        if st["conform_moved_pct"] == 0.0: break
        cur = nxt
    tot = np.linalg.norm(cur - V0, axis=1)
    if tot.max() > CONFORM_MAX_MM:
        cur = V0 + (cur - V0) * np.minimum(1.0, CONFORM_MAX_MM / np.maximum(tot, 1e-9))[:, None]; tot = np.linalg.norm(cur - V0, axis=1)
    return cur, dict(conform_mean_mm=round(float(tot.mean()), 2), conform_max_mm=round(float(tot.max()), 2), conform_moved_pct=round(100 * float((tot > 0.05).mean()), 1))


def volume_info(v, f):
    """(volume cm3 or None, basis): exact for a closed mesh, the voxel solid (2 mm) of a sealed open mesh, None for a sheet (the card then states the area)"""
    m = trimesh.Trimesh(v, f, process=True)
    if m.is_watertight:
        return round(abs(float(m.volume)) / 1000, 3), "closed mesh"
    lo, sol, ok, sh = lattice_solid(v, f, 2.0)
    if ok:
        return round(float(sol.sum()) * 8.0 / 1000, 3), "voxel solid (2 mm)"
    return None, "open sheet"


def mirror_fit(P, ids_src, src_side, tgt_side, sys_, exclude_ids=()):
    """-> dict(ok, V, F, report) for one structure group (ids of the source side)"""
    v, f = C.merge(P.S, ids_src)
    vm, fm = P.plane.reflect_mesh(v, f)
    neigh = neighbour_bones(P, v, src_side, tgt_side)
    rep = dict(neighbour_bones=[dict(bone=cn, source_side=sd, target_side=tsd, share=round(fr, 2)) for cn, sd, tsd, fr in neigh])
    if not neigh:
        rep["fails"] = ["no neighbouring bone with a counterpart on the target side"]; return dict(ok=False, report=rep)
    T, fr = fit_to_bones(P, vm, neigh)
    rep["fit"] = fr
    f_ = []
    if fr["bone_residual_median_mm"] > BONE_REG_MEDIAN_MAX or fr["bone_residual_p90_mm"] > BONE_REG_P90_MAX:
        f_.append(f"bone registration: median {fr['bone_residual_median_mm']} mm / p90 {fr['bone_residual_p90_mm']} mm (gate {BONE_REG_MEDIAN_MAX} / {BONE_REG_P90_MAX})")
    if not (SCALE_RANGE[0] <= fr["scale"] <= SCALE_RANGE[1]): f_.append(f"scale {fr['scale']} outside {SCALE_RANGE}")
    if fr["rotation_deg"] > ROT_MAX_DEG: f_.append(f"rotation {fr['rotation_deg']} deg > {ROT_MAX_DEG}")
    V1 = R.apply(T, vm)
    g0 = guards(P, V1, fm, sys_, exclude_ids)
    rep["guards_after_fit"] = {k: v_ for k, v_ in g0.items() if k not in ("fails", "pass")}
    V2, cs = conform(P, V1, fm, sys_)
    rep["conform"] = cs
    g1 = guards(P, V2, fm, sys_, exclude_ids)
    rep["guards"] = {k: v_ for k, v_ in g1.items() if k not in ("fails", "pass")}
    f_ += g1["fails"]
    if cs["conform_max_mm"] > CONFORM_MAX_MM - 0.01 and g1["fails"]: f_.append("the bounded conform step reached its limit")
    vol_src, basis = volume_info(v, f); vol_new, _ = volume_info(V2, fm)
    rep["volume_source_cm3"] = vol_src; rep["volume_new_cm3"] = vol_new; rep["volume_basis"] = basis
    rep["area_source_cm2"] = round(C.area(v, f) / 100, 2); rep["area_new_cm2"] = round(C.area(V2, fm) / 100, 2)
    rep["fails"] = f_
    return dict(ok=not f_, V=V2, F=fm, report=rep)
