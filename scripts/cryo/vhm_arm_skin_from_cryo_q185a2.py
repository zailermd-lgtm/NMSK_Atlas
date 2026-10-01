"""Q185a2: HIS arm skin beyond the torso-CT field of view, from his OWN cryosection photographs.

    python3 scripts/cryo/vhm_arm_skin_from_cryo_q185a2.py segment [--cryo SCRATCH/vh_cryo]   # photos -> registered body mask (task_outputs)
    python3 scripts/cryo/vhm_arm_skin_from_cryo_q185a2.py merge      # CT skin + photo mask -> build/vh/ct_vhm_skin (rebuild step, idempotent)
    python3 scripts/cryo/vhm_arm_skin_from_cryo_q185a2.py gates      # enclosure / continuity / circumference gates -> report
    python3 scripts/cryo/vhm_arm_skin_from_cryo_q185a2.py stamp      # badge the skin record (rebuild step)
    python3 scripts/cryo/vhm_arm_skin_from_cryo_q185a2.py montage --out DIR

His skin (ct_vhm_skin) is surfaced from his CT, whose field of view ends at atlas x = -233.4 / +246.6 mm (flat caps there,
atlas y 164..588: lateral upper arms, elbows, proximal forearms; Q185a). His cryosection photographs (IDC series
4aaf9181-..., 3x downsampled to 0.99 mm/px, every 1 mm level, both arms in frame; torso RAS z = 985 - instance) show the
whole cross-section against the blue frozen block.

BODY / AIR RULE: cryo_classes.classify tissue (r > b + 15 and max(RGB) > 60; the gelatin is blue, the specimen red /
cream / white), opened 2 px, holes filled per photograph (= scripts/cryo/skin_from_cryo.py's rule); only the connected
pieces that hold that arm's photographed bones are kept (drops the paper level labels / grey card).

REGISTRATION (no new method): the Q151 / Q164 male-arm registration -- per photograph and per arm, TRANSLATION ONLY at the
fixed photograph scale (here 0.99 mm/px; Q164 0.33 mm/px at full resolution), photographed bone cross-sections laid on his
CT/cryo-completed arm bones at the same z (data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz: humerus 1/5,
radius 2/6, ulna 3/7 right/left; x = 350 - i, y = 240 - j, z = -1113 + k). Photo bones = the bright (fat / pale / white:
classes 2, 4, 5) discs inside the arm (refine_transfer_photo_watershed.bone_disc_centroid's classes), matched per CT bone
to the nearest disc of comparable area; reliable levels = every bone matched and (>= 2 bones) the photographed bone-to-bone
distances within 3 mm of the CT's; median-filtered over 21 reliable levels and interpolated between them
(vhm_forearm_muscles_fullres.smooth_translation's rule).

SURFACE: per side, a 1 mm grid beyond (and 25 mm inside) the FOV plane; occupancy = his CT skin inside (the existing
mesh, ray parity) inside the FOV, the registered photograph mask beyond it, linear blend over the 7 mm band inside the
plane (plane + 1 .. + 8 mm); Gaussian sigma 1 voxel, marching cubes (step 2 = the CT skin's own ~2 mm edges). The CT skin
is cut at a wall plane 15 mm inside the FOV plane (where the grid is still pure CT) and the photo-derived part is zipped
onto it there (exact plane slices, loops matched, one triangle strip), so the skin stays one closed surface.
The CT-only skin is kept as build/vh/ct_vhm_skin/{vertices,faces}.ctonly.* and `merge` always starts from it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "cryo"))

PX = 0.99                                       # mm per pixel of the 3x-downsampled photographs
ORIGIN = np.array([-6.035, -895.476, 4.787])    # atlas = (x, z, y)_RAS - ORIGIN (every ct_vhm_* subject)
Z_OF_INST = 985.0                               # torso RAS z = 985 - instance
INST_RANGE = (1270, 1740)                       # photographs used (caps at atlas y 164..588 = instances 1293..1717, +-20)
BONES = REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"
BONES_AFF = (350.0, 240.0, -1113.0)
SIDE_BONES = {"right": {"humerus": 1, "radius": 2, "ulna": 3}, "left": {"humerus": 5, "radius": 6, "ulna": 7}}
MASK = REPO / "data/ct_sources/task_outputs/vhm_arm_skin_cryo_q185a2.nii.gz"
REG = REPO / "data/derived/Q185a2_arm_skin_registration_vhm.json"
REPORT = REPO / "data/derived/Q185a2_arm_skin_vhm.json"
SKIN = REPO / "build/vh/ct_vhm_skin"
INIT = (338.0, -159.96)                         # skin_from_cryo.py's whole-series affine: x = 338 - 0.99 c, y = -159.96 + 0.99 r
# mask grid (torso RAS, 1 mm): x -350..350, y -200..200, z of the instances
GX = np.arange(-350, 351, dtype=float); GY = np.arange(-200, 201, dtype=float)
WALL_MM, BLEND = 15.0, (1.0, 8.0)               # wall inside the FOV plane; photo weight 1 at <= 1 mm inside, 0 at >= 8 mm
GRID_IN_MM = 25.0                               # how far inside the plane the local grid reaches


def fov_planes_atlas() -> tuple[float, float]:
    """the CT skin's own x extent (= the FOV caps), atlas mm, from the CT-only skin"""
    v, _ = ct_skin()
    return float(v[:, 0].min()), float(v[:, 0].max())


# ------------------------------------------------------------------------------------------------ photographs
def body_mask(cls: np.ndarray) -> np.ndarray:
    from scipy import ndimage as ndi
    return ndi.binary_fill_holes(ndi.binary_opening(cls > 0, iterations=2))


def ct_bones_at(bones: np.ndarray, z: float, side: str, min_px: int = 30) -> dict:
    k = int(round(z - BONES_AFF[2])); out = {}
    if not 0 <= k < bones.shape[2]:
        return out
    sl = bones[:, :, k]
    for name, lab in SIDE_BONES[side].items():
        ii, jj = np.nonzero(sl == lab)
        if len(ii) >= min_px:
            out[name] = (float((BONES_AFF[0] - ii).mean()), float((BONES_AFF[1] - jj).mean()), int(len(ii)))
    return out


def photo_discs(cls: np.ndarray, body: np.ndarray):
    """bright (fat / pale / white) discs inside the body, >= 4 px from its edge: (labels, [(row, col, area)])"""
    from scipy import ndimage as ndi
    bright = np.isin(cls, (2, 4, 5)) & ndi.binary_erosion(body, iterations=4)
    bright = ndi.binary_opening(ndi.binary_closing(bright, iterations=1), iterations=1)
    lab, n = ndi.label(bright)
    if n == 0:
        return lab, []
    idx = np.arange(1, n + 1); area = ndi.sum(bright, lab, idx); com = ndi.center_of_mass(bright, lab, idx)
    return lab, [(c[0], c[1], int(a)) for c, a in zip(com, area)]


def to_px(x, y, T):
    X0, Y0 = T
    return (np.asarray(y) - Y0) / PX, (X0 - np.asarray(x)) / PX


def match_level(discs, ct: dict, T, radius_px: float):
    """per CT bone: nearest disc (centroid within radius of the prediction) with area 0.4..2.5x the CT section"""
    m = {}
    for name, (x, y, a) in ct.items():
        pr, pc = to_px(x, y, T); best = None
        for r, c, ar in discs:
            d = np.hypot(r - pr, c - pc)
            if d <= radius_px and 0.4 <= ar * PX * PX / a <= 2.5 and (best is None or d < best[0]):
                best = (d, r, c, ar)
        if best:
            m[name] = best[1:]
    return m


def level_translation(m: dict, ct: dict):
    """(X0, Y0) that lays the matched photo bone centroids on the CT ones (translation only, mean over bones)"""
    X0 = [ct[b][0] + PX * m[b][1] for b in m]; Y0 = [ct[b][1] - PX * m[b][0] for b in m]
    return float(np.mean(X0)), float(np.mean(Y0))


def reliable(m: dict, ct: dict, tol=3.0) -> bool:
    """Q164's rule: two (or more) bones found and their photographed distances agree with the CT's; a single-bone level
    (humerus shaft) counts when that bone is the only one in the CT section"""
    if not m or (len(m) < 2 and len(ct) > 1):
        return False
    names = sorted(m)
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            dp = np.hypot(m[a][0] - m[b][0], m[a][1] - m[b][1]) * PX
            dc = np.hypot(ct[a][0] - ct[b][0], ct[a][1] - ct[b][1])
            if abs(dp - dc) > tol:
                return False
    return True


def smooth(raw: dict, insts: list, size=21):
    from scipy import ndimage as ndi
    rel = sorted(i for i, r in raw.items() if r["reliable"])
    arr = np.array([raw[i]["T_raw"] for i in rel], float); k = min(size, len(rel))
    sm = np.stack([ndi.median_filter(arr[:, q], size=k, mode="nearest") for q in range(2)], 1)
    return {i: (float(np.interp(i, rel, sm[:, 0])), float(np.interp(i, rel, sm[:, 1]))) for i in insts}, rel


def register(vol, bones, insts, log=print):
    """per side: raw per-level translations, tracked from the mid-arm level outward"""
    from cryo_classes import classify
    cache = {}

    def level(inst):
        if inst not in cache:
            cls = classify(np.asarray(vol[inst - 1001])); body = body_mask(cls)
            cache[inst] = (cls, body, photo_discs(cls, body)[1])
        return cache[inst]
    out = {}
    for side in ("right", "left"):
        raw = {}
        start = 1500
        for direction in (range(start, insts[-1] + 1), range(start - 1, insts[0] - 1, -1)):
            hist = []
            for inst in direction:
                ct = ct_bones_at(bones, Z_OF_INST - inst, side)
                if not ct:
                    continue
                prior = tuple(np.median(np.array(hist[-5:]), 0)) if hist else (raw[start]["T_s"] if inst != start and start in raw else INIT)
                rad = 12.0 if hist else 30.0
                _, _, discs = level(inst)
                m = match_level(discs, ct, prior, rad)
                rec = {"ct": {b: [round(v, 2) for v in ct[b][:2]] for b in ct}, "matched": sorted(m), "T_raw": None, "reliable": False}
                if m:
                    T = level_translation(m, ct); rec["T_raw"] = [round(T[0], 2), round(T[1], 2)]
                    rec["reliable"] = reliable(m, ct)
                    if rec["reliable"]:
                        hist.append(T)
                if inst == start:
                    rec["T_s"] = tuple(np.median(np.array(hist), 0)) if hist else INIT
                raw[inst] = rec
        out[side] = raw
        nrel = sum(r["reliable"] for r in raw.values())
        log(f"{side}: {len(raw)} levels with CT bone, {nrel} reliable")
    return out, cache


def cmd_segment(a) -> int:
    import nibabel as nib
    from scipy import ndimage as ndi
    cryo = Path(a.cryo)
    vol = np.load(cryo / "cryo_1mm.npy", mmap_mode="r")
    bones = np.asanyarray(nib.load(str(BONES)).dataobj)
    insts = list(range(INST_RANGE[0], INST_RANGE[1] + 1))
    raw, cache = register(vol, bones, insts)
    from cryo_classes import classify
    T, rel = {}, {}
    for side in raw:
        T[side], rel[side] = smooth(raw[side], insts)
    # residual of the smoothed translation at the reliable levels (bone centroid distance, mm)
    resid = {s: [float(np.hypot(*(np.array(raw[s][i]["T_raw"]) - np.array(T[s][i])))) for i in rel[s]] for s in raw}
    # registered body masks on the RAS grid, each side from its own translation; only pieces holding that arm's bones
    Z = len(insts); M = np.zeros((len(GX), len(GY), Z), np.uint8)
    xx, yy = np.meshgrid(GX, GY, indexing="ij")
    side_x = {"right": xx > 150, "left": xx < -150}
    for zi, inst in enumerate(insts):
        if inst in cache:
            cls, body, _ = cache[inst]
        else:
            cls = classify(np.asarray(vol[inst - 1001])); body = body_mask(cls)
        lab, n = ndi.label(body)
        for side in ("right", "left"):
            t = T[side][inst]
            ct = ct_bones_at(bones, Z_OF_INST - inst, side)
            keep = set()
            for b, (x, y, _) in ct.items():
                r, c = to_px(x, y, t); r, c = int(round(float(r))), int(round(float(c)))
                if 0 <= r < lab.shape[0] and 0 <= c < lab.shape[1] and lab[r, c]:
                    keep.add(int(lab[r, c]))
            if not keep:   # no CT bone at this level for this side: keep pieces reaching the side's half of the grid
                continue
            piece = np.isin(lab, list(keep))
            r, c = to_px(xx, yy, t)
            v = ndi.map_coordinates(piece.astype(np.float32), [r, c], order=1, mode="constant", cval=0.0) >= 0.5
            M[:, :, zi][v & side_x[side]] = 1
    aff = np.array([[1.0, 0, 0, GX[0]], [0, 1.0, 0, GY[0]], [0, 0, -1.0, Z_OF_INST - insts[0]], [0, 0, 0, 1]])
    MASK.parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(M, aff), str(MASK))
    rep = {"_README": (__doc__ or "").strip().splitlines()[:3], "instances": [insts[0], insts[-1]], "px_mm": PX,
           "sides": {}}
    for s in raw:
        rows = {str(i): {**{k: v for k, v in raw[s][i].items() if k != "T_s"}, "T": [round(T[s][i][0], 2), round(T[s][i][1], 2)]}
                for i in sorted(raw[s])}
        ts = np.array([T[s][i] for i in insts])
        rep["sides"][s] = {"levels_with_ct_bone": len(raw[s]), "reliable_levels": len(rel[s]),
                           "residual_mm_median": round(float(np.median(resid[s])), 2),
                           "residual_mm_p95": round(float(np.percentile(resid[s], 95)), 2),
                           "translation_range_X0": [round(float(ts[:, 0].min()), 1), round(float(ts[:, 0].max()), 1)],
                           "translation_range_Y0": [round(float(ts[:, 1].min()), 1), round(float(ts[:, 1].max()), 1)],
                           "levels": rows}
    REG.write_text(json.dumps(rep, indent=1))
    print(f"wrote {MASK.relative_to(REPO)} ({int(M.sum())} voxels) and {REG.relative_to(REPO)}")
    for s in raw:
        d = rep["sides"][s]; print(s, {k: v for k, v in d.items() if k != "levels"})
    return 0


# ------------------------------------------------------------------------------------------------ CT skin + merge
def ct_skin():
    """(V, F) of the CT-only skin: the .ctonly backup if present, else the current subject files"""
    v = SKIN / "vertices.ctonly.f32"; f = SKIN / "faces.ctonly.u32"
    if not v.exists():
        v, f = SKIN / "vertices.f32", SKIN / "faces.u32"
    V = np.fromfile(v, np.float32).reshape(-1, 3).astype(np.float64)
    F = np.fromfile(f, np.uint32).reshape(-1, 3).astype(np.int64)
    return V, F


def mask_volume():
    import nibabel as nib
    img = nib.load(str(MASK)); return np.asanyarray(img.dataobj), img.affine


def side_grid(side: str, planes: tuple, mask, maff):
    """atlas-mm grid of one side: x from GRID_IN_MM inside the plane outward to the mask's extent, every photo level"""
    lo, hi = planes
    sx = -1.0 if side == "left" else 1.0
    plane = lo if side == "left" else hi
    xin = plane - sx * GRID_IN_MM
    # outward extent of the photo mask on this side (+ 6 mm)
    ras_x = GX
    cols = np.nonzero(mask.any(axis=(1, 2)))[0]
    xs = ras_x[cols] - ORIGIN[0]
    xs = xs[xs < 0] if side == "left" else xs[xs > 0]
    xout = (xs.min() - 6) if side == "left" else (xs.max() + 6)
    ax = np.arange(min(xin, xout), max(xin, xout) + 0.5, 1.0)
    nz = mask.shape[2]
    ras_z = maff[2, 3] + maff[2, 2] * np.arange(nz)
    ay = ras_z - ORIGIN[1]                         # atlas y (superior), decreasing with index
    az = GY - ORIGIN[2]                           # atlas z (anterior) = RAS y - 4.787
    return ax, ay, az, plane, sx


def occupancy(side, planes, skin_mesh, mask, maff, log=print):
    ax, ay, az, plane, sx = side_grid(side, planes, mask, maff)
    # photo mask resampled to atlas x (RAS x = ax + ORIGIN[0]); exact 1 mm shift (ORIGIN x not integer -> linear)
    from scipy import ndimage as ndi
    gi = (ax + ORIGIN[0] - GX[0])
    sub = mask.astype(np.float32)
    P = np.stack([ndi.map_coordinates(sub[:, :, k], np.meshgrid(gi, np.arange(len(GY)), indexing="ij"), order=1)
                  for k in range(mask.shape[2])], 1)        # (nx, nz_levels, ny) -> axes (ax, ay, az)
    # CT skin inside, only where the photo weight < 1
    d_in = sx * (plane - ax)                       # mm inside the FOV plane (> 0 inside)
    w = np.clip((BLEND[1] - d_in) / (BLEND[1] - BLEND[0]), 0, 1)
    C = np.zeros_like(P)
    need = np.nonzero(w < 1)[0]
    if len(need):
        XX, YY, ZZ = np.meshgrid(ax[need], ay, az, indexing="ij")
        pts = np.stack([XX.ravel(), YY.ravel(), ZZ.ravel()], 1)
        # only points near the CT skin's bbox can be inside
        inside = np.zeros(len(pts), bool)
        bb0, bb1 = skin_mesh.bounds
        cand = np.all((pts >= bb0) & (pts <= bb1), 1)
        inside[cand] = skin_mesh.contains(pts[cand])
        C[need] = inside.reshape(len(need), len(ay), len(az))
    F = w[:, None, None] * P + (1 - w[:, None, None]) * C
    log(f"{side}: grid {F.shape}, photo voxels {int((P > 0.5).sum())}, CT voxels {int((C > 0.5).sum())}")
    return F, ax, ay, az, plane, sx, P, C


def surface(F, ax, ay, az, sigma=1.0, step=2):
    from scipy import ndimage as ndi
    from skimage.measure import marching_cubes
    G = ndi.gaussian_filter(np.pad(F, 2), sigma)
    v, f, _, _ = marching_cubes(G, 0.5, step_size=step, allow_degenerate=False)
    v = v - 2
    out = np.stack([np.interp(v[:, 0], np.arange(len(ax)), ax), np.interp(v[:, 1], np.arange(len(ay)), ay),
                    np.interp(v[:, 2], np.arange(len(az)), az)], 1)
    return out, f.astype(np.int64)


def oriented_outward(v, f):
    vol = np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum() / 6
    return f if vol > 0 else f[:, ::-1]


def slice_keep(v, f, x0, keep_ge: bool):
    """keep the part with x >= x0 (keep_ge) or x <= x0; crossing triangles split exactly on the plane"""
    import trimesh
    m = trimesh.Trimesh(v, f, process=False)
    n = np.array([1.0, 0, 0]) if keep_ge else np.array([-1.0, 0, 0])
    s = trimesh.intersections.slice_mesh_plane(m, n, [x0, 0, 0], cap=False)
    s.merge_vertices(digits_vertex=6)
    return np.asarray(s.vertices, float), np.asarray(s.faces, np.int64)


def boundary_loops(v, f, x0, tol=1e-4):
    """directed boundary loops (as traversed by their faces) whose vertices lie on the plane x = x0"""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = {tuple(r) for r in e.tolist()}
    bnd = [(a, b) for a, b in e.tolist() if (b, a) not in key]
    nxt = {}
    for a, b in bnd:
        if abs(v[a, 0] - x0) < tol and abs(v[b, 0] - x0) < tol:
            nxt[a] = b
    loops, seen = [], set()
    for s in list(nxt):
        if s in seen:
            continue
        loop = [s]; seen.add(s); c = nxt[s]
        while c != s and c in nxt and c not in seen:
            loop.append(c); seen.add(c); c = nxt[c]
        if c == s and len(loop) >= 3:
            loops.append(loop)
    open_edges = len(bnd) - sum(len(l) for l in loops)
    return loops, open_edges


def zipper(A, B, va, vb):
    """triangles joining loop A (CT part, its face direction) and loop B (photo part, its face direction).
    A reversed rotates like B; greedy shortest-diagonal advance. Returns faces with A indices as-is and B indices tagged
    (negative - 1) for the caller to offset."""
    Ar = A[::-1]
    pa = va[Ar][:, 1:]; pb = vb[B][:, 1:]
    j0 = int(np.argmin(np.linalg.norm(pb - pa[0], axis=1)))
    Bs = B[j0:] + B[:j0]; pb = vb[Bs][:, 1:]
    n, m = len(Ar), len(Bs); i = j = 0; tris = []
    while i < n or j < m:
        ai, ai1 = Ar[i % n], Ar[(i + 1) % n]; bj, bj1 = Bs[j % m], Bs[(j + 1) % m]
        if i >= n:
            adv_a = False
        elif j >= m:
            adv_a = True
        else:
            da = np.linalg.norm(pa[(i + 1) % n] - pb[j % m]); db = np.linalg.norm(pb[(j + 1) % m] - pa[i % n])
            adv_a = da <= db
        if adv_a:
            tris.append((ai, ai1, -bj - 1)); i += 1
        else:
            tris.append((ai, -bj1 - 1, -bj - 1)); j += 1
    return tris


def merge(log=print):
    import trimesh
    V0, F0 = ct_skin()
    lo, hi = float(V0[:, 0].min()), float(V0[:, 0].max())
    skin_mesh = trimesh.Trimesh(V0, F0, process=False)
    mask, maff = mask_volume()
    V, F = V0, F0; info = {"fov_planes_atlas_mm": [round(lo, 2), round(hi, 2)], "sides": {}}
    for side in ("left", "right"):
        Fo, ax, ay, az, plane, sx, P, C = occupancy(side, (lo, hi), skin_mesh, mask, maff, log)
        vn, fn = surface(Fo, ax, ay, az)
        fn = oriented_outward(vn, fn) if side else fn
        xw = plane - sx * WALL_MM
        # photo part: outward of the wall; CT part: inward of it
        vp, fp = slice_keep(vn, fn, xw, keep_ge=(side == "right"))
        V, F = slice_keep(V, F, xw, keep_ge=(side == "left"))
        la, oa = boundary_loops(V, F, xw); lb, ob = boundary_loops(vp, fp, xw)
        ca = [V[l][:, 1:].mean(0) for l in la]; cb = [vp[l][:, 1:].mean(0) for l in lb]
        used, tris_all = set(), []
        for ia, l in enumerate(la):
            if not cb:
                break
            jb = int(np.argmin([np.linalg.norm(c - ca[ia]) for c in cb]))
            used.add(jb); tris_all += zipper(l, lb[jb], V, vp)
        off = len(V)
        T = np.array([[t if t >= 0 else off + (-t - 1) for t in tri] for tri in tris_all], np.int64)
        V = np.concatenate([V, vp]); F = np.concatenate([F, fp + off, T])
        # seam step: per CT-loop vertex, distance to the matched photo loop (in the wall plane)
        steps = []
        for ia, l in enumerate(la):
            jb = int(np.argmin([np.linalg.norm(c - ca[ia]) for c in cb])) if cb else None
            if jb is not None:
                from scipy.spatial import cKDTree
                steps += list(cKDTree(vp[lb[jb]][:, 1:]).query(V[l][:, 1:])[0])
        info["sides"][side] = {"wall_x_mm": round(xw, 2), "loops_ct": len(la), "loops_photo": len(lb),
                               "open_edges_ct": oa, "open_edges_photo": ob, "zip_triangles": len(T),
                               "wall_gap_mm_median": round(float(np.median(steps)), 2) if steps else None,
                               "wall_gap_mm_max": round(float(np.max(steps)), 2) if steps else None,
                               "photo_part_vertices": len(vp), "photo_part_triangles": len(fp)}
        log(f"{side}: {info['sides'][side]}")
    m = trimesh.Trimesh(V, F, process=False)
    m.merge_vertices(digits_vertex=5)
    m.remove_unreferenced_vertices()
    info["watertight"] = bool(m.is_watertight); info["vertices"] = len(m.vertices); info["triangles"] = len(m.faces)
    info["volume_cm3_ct"] = round(float(skin_mesh.volume) / 1e3, 1); info["volume_cm3_merged"] = round(float(m.volume) / 1e3, 1)
    return m, info


def write_skin(m, info):
    """CT-only backup (once), then the merged mesh into the subject files + manifest counts"""
    import shutil
    for a, b in (("vertices.f32", "vertices.ctonly.f32"), ("faces.u32", "faces.ctonly.u32"), ("manifest.json", "manifest.ctonly.json")):
        if not (SKIN / b).exists():
            shutil.copy2(SKIN / a, SKIN / b)
    man = json.loads((SKIN / "manifest.ctonly.json").read_text())
    s = man["structures"][0]; assert s["atlas_id"] == "skin" and len(man["structures"]) == 1
    v = np.asarray(m.vertices, np.float32); f = np.asarray(m.faces, np.uint32)
    v.tofile(SKIN / "vertices.f32"); f.tofile(SKIN / "faces.u32")
    bmin = [round(float(x), 4) for x in v.min(0)]; bmax = [round(float(x), 4) for x in v.max(0)]
    s.update(vertex_count=len(v), triangle_count=len(f), bbox_min_mm=bmin, bbox_max_mm=bmax)
    man.update(vertex_count=len(v), triangle_count=len(f), bbox_min_mm=bmin, bbox_max_mm=bmax)
    s["fov_cut_mm"] = [round(info["fov_planes_atlas_mm"][0] + 1, 1), round(info["fov_planes_atlas_mm"][1] - 1, 1)]
    s["fov_skin_open"] = info.get("fov_skin_open", [])
    s["q185a2"] = {k: info[k] for k in ("watertight", "seam_step_mm") if k in info}
    (SKIN / "manifest.json").write_text(json.dumps(man, indent=2))


def cmd_merge(a) -> int:
    if not MASK.exists():
        print("Q185a2: no photo mask (run segment) -- skin left as is"); return 0
    m, info = merge()
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    info["fov_skin_open"] = rep.get("fov_skin_open", [])
    info["seam_step_mm"] = rep.get("seam_step_mm")
    write_skin(m, info)
    rep["merge"] = info
    REPORT.write_text(json.dumps(rep, indent=1))
    print(f"Q185a2 merged skin: {info['vertices']} v / {info['triangles']} t, watertight {info['watertight']}, "
          f"volume {info['volume_cm3_ct']} -> {info['volume_cm3_merged']} cm3")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["segment", "merge", "gates", "stamp", "montage"])
    ap.add_argument("--cryo", default=str(REPO / "SCRATCH" / "vh_cryo")); ap.add_argument("--out", default=None)
    ap.add_argument("--bundle", default=str(REPO / "build" / "viewer_m_hr"))
    a = ap.parse_args(argv)
    return {"segment": cmd_segment, "merge": cmd_merge}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
