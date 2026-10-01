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

BODY / AIR RULE: red over blue, r > b + 15 and max(RGB) > 40 (cryo_classes' tissue test with the brightness floor lowered
from 60: the gelatin is blue / cyan, the outside-block background ~(13, 15, 12), the specimen red / cream / white; at 60
the dark skin line where an arm lies against the black mould wall dropped out), opened 2 px, closed 2 px, holes filled
per photograph (scripts/cryo/skin_from_cryo.py's rule + the closing); only the connected pieces that hold that arm's
photographed bones are kept (drops the paper level labels / grey card).

REGISTRATION (no new method): the Q151 / Q164 male-arm registration -- per photograph and per arm, TRANSLATION ONLY at the
fixed photograph scale (here 0.99 mm/px; Q164 0.33 mm/px at full resolution), photographed bone cross-sections laid on his
CT/cryo-completed arm bones at the same z (data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz: humerus 1/5,
radius 2/6, ulna 3/7 right/left; x = 350 - i, y = 240 - j, z = -1113 + k). Photo bones = the bright (fat / pale / white:
classes 2, 4, 5) discs inside the arm (refine_transfer_photo_watershed.bone_disc_centroid's classes), matched per CT bone
to the nearest disc of comparable area; reliable levels = every bone matched and (>= 2 bones) the photographed bone-to-bone
distances within 3 mm of the CT's; median-filtered over 21 reliable levels and interpolated between them
(vhm_forearm_muscles_fullres.smooth_translation's rule).

OVERLAP (measured, `gates`): photo vs CT outline per level, in bands inside the FOV plane over the cap's y / z range:
signed median within +-2.2 mm, |offset| median 2-3.5 mm in every band 1..45 mm (no extra erosion of the CT rim), i.e. the
frozen-block arm and the CT arm differ by a few mm level by level (posture / registration), not systematically.
SURFACE: per side, a 1 mm grid beyond (and 30 mm inside) the FOV plane; occupancy = the registered photograph mask up to
2 mm inside the plane, his CT skin inside (the existing mesh, ray parity) from 12 mm inside, linear blend of the two
SIGNED DISTANCE fields between (the outline morphs, no shelf where they disagree), and only
over the cap's own y range (+3 mm, fading to pure CT 11 mm beyond it);
the photo correction smoothed sigma 1 voxel in-plane / 3 across levels (softens registration ledges), the CT
base sigma 0.7, marching cubes (step 2 = the CT skin's own ~2 mm edges). The CT skin
is cut at a wall plane 20 mm inside the FOV plane (where the grid is pure CT) and the photo-derived part is zipped
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
INST_RANGE = (1230, 1800)                       # photographs used (caps at atlas y 164..588 = instances 1293..1717; the arm piece cut
                                                # off at the wall spans atlas y ~95..630 = instances 1250..1785)
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
WALL_MM, BLEND = 20.0, (2.0, 12.0)              # wall inside the FOV plane; photo weight 1 at <= 2 mm inside, 0 at >= 12 mm
GRID_IN_MM = 30.0                               # how far inside the plane the local grid reaches


def fov_planes_atlas() -> tuple[float, float]:
    """the CT skin's own x extent (= the FOV caps), atlas mm, from the CT-only skin"""
    v, _ = ct_skin()
    return float(v[:, 0].min()), float(v[:, 0].max())


# ------------------------------------------------------------------------------------------------ photographs
def body_mask(cls: np.ndarray, im: np.ndarray | None = None) -> np.ndarray:
    """specimen vs frozen block: red over blue (r > b + 15) and max(RGB) > 40 (classify's > 60 drops the dark skin line
    where the arm lies against the black mould wall; the gel is blue / cyan, the outside-block background ~(13, 15, 12):
    neither has r > b + 15), opened 2 px, closed 2 px, holes filled"""
    from scipy import ndimage as ndi
    t = cls > 0
    if im is not None:
        im = im.astype(np.int16); t = (im[..., 0] > im[..., 2] + 15) & (im.max(-1) > 40)
    t = ndi.binary_closing(ndi.binary_opening(t, iterations=2), iterations=2)
    return ndi.binary_fill_holes(t)


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
            im = np.asarray(vol[inst - 1001]); cls = classify(im); body = body_mask(cls, im)
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
    edge_touch = {"right": [], "left": []}
    for zi, inst in enumerate(insts):
        if inst in cache:
            cls, body, _ = cache[inst]
        else:
            im = np.asarray(vol[inst - 1001]); cls = classify(im); body = body_mask(cls, im)
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
            if piece[:, :2].any() or piece[:, -2:].any() or piece[:2].any() or piece[-2:].any():
                edge_touch[side].append(inst)        # the arm leaves the photograph here: its outline is not complete
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
                           "photo_edge_levels": edge_touch[s], "levels": rows}
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


def side_grid(side: str, planes: tuple, mask, maff, box=None, grid_in=None):
    """atlas-mm grid of one side: x from GRID_IN_MM inside the plane outward to the mask's extent; levels / z limited to
    box = ((y0, y1), (z0, z1)) atlas mm when given. Returns ax, ay, az, plane, sx, level indices"""
    lo, hi = planes
    sx = -1.0 if side == "left" else 1.0
    plane = lo if side == "left" else hi
    xin = plane - sx * (grid_in or GRID_IN_MM)
    cols = np.nonzero(mask.any(axis=(1, 2)))[0]
    xs = GX[cols] - ORIGIN[0]
    xs = xs[xs < 0] if side == "left" else xs[xs > 0]
    xout = (xs.min() - 6) if side == "left" else (xs.max() + 6)
    ax = np.arange(min(xin, xout), max(xin, xout) + 0.5, 1.0)
    ras_z = maff[2, 3] + maff[2, 2] * np.arange(mask.shape[2])
    ay = ras_z - ORIGIN[1]                         # atlas y (superior), decreasing with index
    az = GY - ORIGIN[2]                           # atlas z (anterior) = RAS y - 4.787
    ks = np.arange(len(ay)); js = np.arange(len(az))
    if box is not None:
        (y0, y1), (z0, z1) = box
        ks = np.nonzero((ay >= y0) & (ay <= y1))[0]; js = np.nonzero((az >= z0) & (az <= z1))[0]
        if ay[ks].max() < y1 - 1.0 or ay[ks].min() > y0 + 1.0:
            raise SystemExit(f"Q185a2: photo mask levels {ay.min():.0f}..{ay.max():.0f} do not cover atlas y {y0:.0f}..{y1:.0f}")
    return ax, ay[ks], az[js], plane, sx, ks, js


def cap_y_range(V, plane, tol=0.5):
    """atlas-y extent of the flat FOV cap of the CT skin on that plane"""
    c = V[np.abs(V[:, 0] - plane) < tol]
    return float(c[:, 1].min()), float(c[:, 1].max())


def occupancy(side, planes, skin_mesh, mask, maff, log=print, ct_everywhere=False, box=None, cap_y=None, grid_in=None):
    """photo weight w = w_x (1 at <= BLEND[0] inside the plane, 0 at >= BLEND[1]) x w_y (1 over the cap's y range + 3 mm,
    0 from 11 mm beyond it); occupancy = w * photo + (1 - w) * CT inside"""
    ax, ay, az, plane, sx, ks, js = side_grid(side, planes, mask, maff, box, grid_in)
    from scipy import ndimage as ndi
    gi = (ax + ORIGIN[0] - GX[0])
    P = np.stack([ndi.map_coordinates(mask[:, js, k].astype(np.float32), np.meshgrid(gi, np.arange(len(js)), indexing="ij"),
                                      order=1) for k in ks], 1)          # axes (ax, ay, az)
    d_in = sx * (plane - ax)                       # mm inside the FOV plane (> 0 inside)
    wx = np.clip((BLEND[1] - d_in) / (BLEND[1] - BLEND[0]), 0, 1)
    if cap_y is None:
        wy = np.ones(len(ay))
    else:
        dy = np.maximum(cap_y[0] - ay, ay - cap_y[1])            # mm outside the cap's y range
        wy = np.clip((11.0 - dy) / 8.0, 0, 1)
    W = wx[:, None] * wy[None, :]                                 # (ax, ay)
    C = np.zeros_like(P)
    need = np.argwhere((W < 1) | ct_everywhere)
    if len(need):
        pts = np.stack([np.repeat(ax[need[:, 0]], len(az)), np.repeat(ay[need[:, 1]], len(az)), np.tile(az, len(need))], 1)
        inside = np.zeros(len(pts), bool)
        bb0, bb1 = skin_mesh.bounds
        cand = np.all((pts >= bb0) & (pts <= bb1), 1)
        inside[cand] = skin_mesh.contains(pts[cand])
        C[need[:, 0], need[:, 1]] = inside.reshape(len(need), len(az))
    # blend SIGNED DISTANCES (mm, > 0 inside), not occupancies: the surface then morphs from the CT outline to the photo
    # outline across the band instead of forming a flat shelf where the two masks disagree
    base = sdf(C > 0.5)
    F = (base, W[:, :, None] * (sdf(P > 0.5) - base))       # surface() smooths the photo correction more than the CT base
    log(f"{side}: grid {base.shape}, photo voxels {int((P > 0.5).sum())}, CT voxels {int((C > 0.5).sum())}")
    return F, ax, ay, az, plane, sx, P, C


def sdf(m: np.ndarray, cap: float = 15.0) -> np.ndarray:
    """signed distance (1 mm grid, > 0 inside), clipped to +-cap"""
    from scipy import ndimage as ndi
    if not m.any():
        return np.full(m.shape, -cap, np.float32)
    d = ndi.distance_transform_edt(m) - ndi.distance_transform_edt(~m) + 0.5 * np.where(m, -1, 1)
    return np.clip(d, -cap, cap).astype(np.float32)


def surface(F, ax, ay, az, sigma=(1.0, 3.0, 1.0), sigma_base=0.7, step=2):
    """F = (CT signed distance, weighted photo correction). The correction is smoothed with sigma (x, level, z) voxels --
    3 along the levels softens the 2-5 mm per-level registration jumps (ledges) --, the CT base only lightly, so the
    surface at the wall (correction 0) stays on the CT skin"""
    from scipy import ndimage as ndi
    from skimage.measure import marching_cubes
    base, corr = F
    G = ndi.gaussian_filter(np.pad(base, 2, constant_values=-15.0), sigma_base) + ndi.gaussian_filter(np.pad(corr, 2), sigma)
    v, f, _, _ = marching_cubes(G, 0.0, step_size=step, allow_degenerate=False)
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
    V, F = np.asarray(s.vertices, float), np.asarray(s.faces, np.int64)
    # weld only the new on-plane vertices (one per crossing edge per triangle); the rest of the mesh is left as it was
    on = np.nonzero(np.abs(V[:, 0] - x0) < 1e-6)[0]
    key = {}
    remap = np.arange(len(V))
    for i in on:
        k = (round(V[i, 1], 5), round(V[i, 2], 5))
        remap[i] = key.setdefault(k, i)
    F = remap[F]
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    used = np.unique(F); new = -np.ones(len(V), np.int64); new[used] = np.arange(len(used))
    return V[used], new[F]


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


def weld_plane(V, F, x0):
    """merge coincident on-plane vertices (x = x0) of a mesh assembled from slices; nothing else is touched"""
    on = np.nonzero(np.abs(V[:, 0] - x0) < 1e-6)[0]
    key, remap = {}, np.arange(len(V))
    for i in on:
        remap[i] = key.setdefault((round(V[i, 1], 4), round(V[i, 2], 4)), i)
    F = remap[F]
    F = F[(F[:, 0] != F[:, 1]) & (F[:, 1] != F[:, 2]) & (F[:, 0] != F[:, 2])]
    used = np.unique(F); new = -np.ones(len(V), np.int64); new[used] = np.arange(len(used))
    return V[used], new[F]


def split_ct_at_wall(V, F, xw, plane, ct_keep_ge: bool, cap_tol=1.0):
    """CT skin cut at the wall: (CT with the arm piece beyond the wall removed -- every other piece beyond the wall, e.g. a
    hand or a leg, welded back on --, the removed arm pieces). The arm piece = the beyond-wall component touching the cap."""
    import trimesh
    Vi, Fi = slice_keep(V, F, xw, keep_ge=ct_keep_ge)
    Vo, Fo = slice_keep(V, F, xw, keep_ge=not ct_keep_ge)
    comps = trimesh.Trimesh(Vo, Fo, process=False).split(only_watertight=False)
    arm = [c for c in comps if (np.abs(c.vertices[:, 0] - plane) < cap_tol).sum() > 50]
    rest = [c for c in comps if not any(c is a for a in arm)]
    Vs, Fs, off = [Vi], [Fi], len(Vi)
    for c in rest:
        Vs.append(np.asarray(c.vertices)); Fs.append(np.asarray(c.faces) + off); off += len(c.vertices)
    Vk, Fk = weld_plane(np.concatenate(Vs), np.concatenate(Fs), xw)
    return Vk, Fk, arm


def join_at_wall(V, F, vn, fn, xw, ct_keep_ge: bool):
    """(V, F): the CT skin with the arm piece beyond the wall removed (open loops on the wall); (vn, fn): the closed
    photo-derived surface of the local grid. Keep its part beyond the wall that reaches the wall, zip each CT loop to the
    nearest photo loop: one closed surface"""
    import trimesh
    from scipy.spatial import cKDTree
    vp, fp = slice_keep(vn, fn, xw, keep_ge=not ct_keep_ge)
    comps = trimesh.Trimesh(vp, fp, process=False).split(only_watertight=False)
    keep = [c for c in comps if (np.abs(c.vertices[:, 0] - xw) < 1e-6).sum() >= 3]
    vs, fs, o = [], [], 0
    for c in keep:
        vs.append(np.asarray(c.vertices)); fs.append(np.asarray(c.faces) + o); o += len(c.vertices)
    vp, fp = np.concatenate(vs), np.concatenate(fs)
    la, oa = boundary_loops(V, F, xw); lb, ob = boundary_loops(vp, fp, xw)
    if len(la) != len(lb):
        raise SystemExit(f"Q185a2 join: {len(la)} CT loops vs {len(lb)} photo loops at x = {xw:.1f}")
    ca = [V[l][:, 1:].mean(0) for l in la]; cb = [vp[l][:, 1:].mean(0) for l in lb]
    tris, gaps = [], []
    for ia, l in enumerate(la):
        jb = int(np.argmin([np.linalg.norm(c - ca[ia]) for c in cb]))
        tris += zipper(l, lb[jb], V, vp)
        gaps += list(cKDTree(vp[lb[jb]][:, 1:]).query(V[l][:, 1:])[0])
    off = len(V)
    T = np.array([[t if t >= 0 else off + (-t - 1) for t in tri] for tri in tris], np.int64)
    st = {"loops_ct": len(la), "loops_photo": len(lb), "open_edges_ct": oa, "open_edges_photo": ob, "zip_triangles": len(T),
          "wall_gap_mm_median": round(float(np.median(gaps)), 2) if gaps else None,
          "wall_gap_mm_max": round(float(np.max(gaps)), 2) if gaps else None,
          "photo_part_vertices": len(vp), "photo_part_triangles": len(fp)}
    return np.concatenate([V, vp]), np.concatenate([F, fp + off, T]), st


def merge(log=print):
    import trimesh
    V0, F0 = ct_skin()
    lo, hi = float(V0[:, 0].min()), float(V0[:, 0].max())
    skin_mesh = trimesh.Trimesh(V0, F0, process=False)
    mask, maff = mask_volume()
    V, F = V0, F0; info = {"fov_planes_atlas_mm": [round(lo, 2), round(hi, 2)], "sides": {}}
    for side in ("left", "right"):
        plane = lo if side == "left" else hi; sx = -1.0 if side == "left" else 1.0
        xw = plane - sx * WALL_MM
        cap = cap_y_range(V0, plane)
        V, F, arm = split_ct_at_wall(V, F, xw, plane, ct_keep_ge=(side == "left"))
        av = np.concatenate([np.asarray(c.vertices) for c in arm])
        box = ((float(av[:, 1].min()) - 8, float(av[:, 1].max()) + 8), (float(av[:, 2].min()) - 25, float(av[:, 2].max()) + 25))
        Fo, ax, ay, az, plane, sx, P, C = occupancy(side, (lo, hi), skin_mesh, mask, maff, log, box=box, cap_y=cap)
        vn, fn = surface(Fo, ax, ay, az)
        V, F, st = join_at_wall(V, F, vn, oriented_outward(vn, fn), xw, ct_keep_ge=(side == "left"))
        info["sides"][side] = {"wall_x_mm": round(xw, 2), "cap_y_mm": [round(cap[0], 1), round(cap[1], 1)],
                               "grid_y_mm": [round(box[0][0], 1), round(box[0][1], 1)], "ct_arm_pieces_replaced": len(arm), **st}
        log(f"{side}: {info['sides'][side]}")
    m = trimesh.Trimesh(V, F, process=False)
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

# ------------------------------------------------------------------------------------------------ gates
def load_skin_mesh(ct_only: bool):
    import trimesh
    if ct_only:
        V, F = ct_skin()
    else:
        V = np.fromfile(SKIN / "vertices.f32", np.float32).reshape(-1, 3).astype(np.float64)
        F = np.fromfile(SKIN / "faces.u32", np.uint32).reshape(-1, 3).astype(np.int64)
    return trimesh.Trimesh(V, F, process=False)


def arm_records(bundle: Path, planes, wall=WALL_MM):
    """bundle records (bone / muscle / fascia) with vertices in the arm region beyond a wall plane"""
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    M = meshes_by_id(*read_bundle_dir(str(bundle))); out = {}
    for aid, r in M.items():
        if aid == "skin" or r.get("cat") not in ("bone", "muscle", "fascia"):
            continue
        v = np.asarray(r["v"], float)
        arm = ((v[:, 0] <= planes[0] + wall) | (v[:, 0] >= planes[1] - wall)) & (v[:, 1] > 120) & (v[:, 1] < 640)
        if arm.sum() >= 20:
            out[aid] = (r["cat"], v)
    return out


BANDS = ((1.0, 8.0), (2.0, 12.0), (8.0, 15.0), (15.0, 30.0), (30.0, 45.0))


def overlap_agreement(planes, skin_ct, mask, maff, bands=BANDS):
    """photo outline vs CT skin in bands inside the FOV plane, per level: signed boundary offset (photo outside CT > 0)"""
    from scipy import ndimage as ndi
    res = {}
    for side in ("left", "right"):
        pl = planes[0] if side == "left" else planes[1]
        V0 = np.asarray(skin_ct.vertices); cy = cap_y_range(V0, pl); cz = V0[np.abs(V0[:, 0] - pl) < 0.5][:, 2]
        box = (cy, (float(cz.min()) - 30, float(cz.max()) + 30))
        F, ax, ay, az, plane, sx, P, C = occupancy(side, planes, skin_ct, mask, maff, log=lambda *a: None, ct_everywhere=True,
                                                   box=box, grid_in=47.0)
        d_in = sx * (plane - ax); res[side] = {}
        for band in bands:
            cols = (d_in >= band[0]) & (d_in <= band[1]); rows = []
            for k in range(len(ay)):
                p = P[cols, k] > 0.5; c = C[cols, k] > 0.5
                if c.sum() < 30 or p.sum() < 30:
                    continue
                pb = p & ~ndi.binary_erosion(p, border_value=1); cb = c & ~ndi.binary_erosion(c, border_value=1)
                pb[0] = pb[-1] = False; cb[0] = cb[-1] = False          # not the band's own x walls
                if not pb.any() or not cb.any():
                    continue
                dist = ndi.distance_transform_edt(~cb)[pb]; sgn = np.where(c[pb], -1.0, 1.0)
                rows.append((float(ay[k]), float(np.median(sgn * dist)), float(np.median(dist)), float(p.sum()), float(c.sum())))
            R = np.array(rows)
            res[side][f"{band[0]:.0f}-{band[1]:.0f}mm"] = {
                "levels": len(R), "signed_offset_mm_median": round(float(np.median(R[:, 1])), 2),
                "abs_offset_mm_median": round(float(np.median(R[:, 2])), 2),
                "abs_offset_mm_p95_of_levels": round(float(np.percentile(R[:, 2], 95)), 2),
                "volume_cm3_photo": round(float(R[:, 3].sum()) / 1e3, 1), "volume_cm3_ct": round(float(R[:, 4].sum()) / 1e3, 1),
                "area_ratio_median": round(float(np.median(R[:, 3] / R[:, 4])), 3)}
    return res


def fold_check(m, region, min_area=0.2):
    """self-intersection / fold proxy on the new part: centroids of faces >= min_area mm2 moved 0.3 mm against / along the
    face normal must test inside / outside (ray parity); a fold or self-crossing breaks that. Slivers (< min_area, from the
    exact plane slices at the wall) have no reliable normal and are only counted."""
    ok = region[m.area_faces[region] >= min_area]
    fc = m.triangles_center[ok]; fn = m.face_normals[ok]
    rng = np.random.default_rng(0); sel = rng.choice(len(fc), min(20000, len(fc)), replace=False)
    ins = m.contains(fc[sel] - 0.3 * fn[sel]); outs = ~m.contains(fc[sel] + 0.3 * fn[sel])
    return {"faces_tested": int(len(sel)), "inside_ok_frac": round(float(ins.mean()), 4), "outside_ok_frac": round(float(outs.mean()), 4),
            "sliver_faces_lt_0p2mm2": int(len(region) - len(ok)), "region_faces": int(len(region))}


def cmd_gates(a) -> int:
    from scipy import ndimage as ndi  # noqa: F401
    skin_ct = load_skin_mesh(True); skin_new = load_skin_mesh(False)
    lo, hi = float(skin_ct.vertices[:, 0].min()), float(skin_ct.vertices[:, 0].max())
    mask, maff = mask_volume()
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    rep["_README"] = (__doc__ or "").strip().splitlines()
    rep["registration"] = {s: {k: v for k, v in d.items() if k != "levels"}
                           for s, d in json.loads(REG.read_text())["sides"].items()}
    ov = overlap_agreement((lo, hi), skin_ct, mask, maff); rep["overlap_photo_vs_ct"] = ov
    bk = f"{BLEND[0]:.0f}-{BLEND[1]:.0f}mm"
    rep["seam_step_mm"] = {"blend_band": bk,
                           "blend_band_signed_offset_mm": max((ov[s][bk]["signed_offset_mm_median"] for s in ov), key=abs),
                           "blend_band_abs_offset_mm_median": max(ov[s][bk]["abs_offset_mm_median"] for s in ov),
                           "blend_band_abs_offset_mm_p95": max(ov[s][bk]["abs_offset_mm_p95_of_levels"] for s in ov),
                           "rim_1_8mm_signed_offset_mm": max((ov[s]["1-8mm"]["signed_offset_mm_median"] for s in ov), key=abs),
                           "zip_strip_gap_median": max((rep.get("merge", {}).get("sides", {}).get(s, {}).get("wall_gap_mm_median") or 0) for s in ("left", "right")),
                           "zip_strip_gap_max": max((rep.get("merge", {}).get("sides", {}).get(s, {}).get("wall_gap_mm_max") or 0) for s in ("left", "right"))}
    # enclosure
    recs = arm_records(Path(a.bundle), (lo, hi)); enc = {}
    for aid, (cat, v) in sorted(recs.items()):
        beyond = (v[:, 0] <= lo + 1) | (v[:, 0] >= hi - 1)
        i_new = skin_new.contains(v); i_old = skin_ct.contains(v)
        enc[aid] = {"cat": cat, "n": int(len(v)), "beyond_fov": int(beyond.sum()),
                    "inside_new_frac": round(float(i_new.mean()), 4), "inside_ct_skin_frac": round(float(i_old.mean()), 4),
                    "beyond_inside_new_frac": round(float(i_new[beyond].mean()), 4) if beyond.any() else None,
                    "outside_new_max_mm": round(float(skin_new.nearest.signed_distance(v[~i_new]).__neg__().max()), 1) if (~i_new).any() else 0.0}
    rep["enclosure"] = enc
    for cat in ("bone", "muscle", "fascia"):
        sub = [r for r in enc.values() if r["cat"] == cat]
        if sub:
            n = sum(r["n"] for r in sub); nb = sum(r["beyond_fov"] for r in sub)
            rep.setdefault("enclosure_summary", {})[cat] = {
                "records": len(sub), "vertices": n,
                "inside_new_frac": round(sum(r["inside_new_frac"] * r["n"] for r in sub) / n, 4),
                "inside_ct_skin_frac": round(sum(r["inside_ct_skin_frac"] * r["n"] for r in sub) / n, 4),
                "beyond_fov_vertices": nb,
                "beyond_inside_new_frac": round(sum((r["beyond_inside_new_frac"] or 0) * r["beyond_fov"] for r in sub) / max(nb, 1), 4)}
    # continuity / folds / volume
    region = np.nonzero((skin_new.triangles_center[:, 0] <= lo + WALL_MM + 1) | (skin_new.triangles_center[:, 0] >= hi - WALL_MM - 1))[0]
    rep["folds"] = fold_check(skin_new, region)
    rep["watertight"] = bool(skin_new.is_watertight)
    rep["volume_cm3"] = {"ct_skin": round(float(skin_ct.volume) / 1e3, 1), "merged": round(float(skin_new.volume) / 1e3, 1)}
    # coverage: photo levels exist for every cap level; open = levels whose arm left the photograph (none expected)
    R = json.loads(REG.read_text())["sides"]
    open_ = [{"side": "lo" if s == "left" else "hi", "y_mm": [round(1880.476 - i - 0.5, 1), round(1880.476 - i + 0.5, 1)]}
             for s in R for i in R[s]["photo_edge_levels"]]
    rep["fov_skin_open"] = open_
    REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: rep[k] for k in ("seam_step_mm", "enclosure_summary", "folds", "watertight", "volume_cm3")}, indent=1))
    for s, d in ov.items():
        print(s, d)
    return 0


def badge_text(rep: dict) -> str:
    st = rep["seam_step_mm"]; es = rep.get("enclosure_summary", {})
    lo, hi = rep["merge"]["fov_planes_atlas_mm"]
    enc = "; ".join(f"{k} {100 * v['inside_new_frac']:.1f} % of vertices inside (beyond the planes {100 * v['beyond_inside_new_frac']:.1f} %)"
                    for k, v in es.items())
    op = rep.get("fov_skin_open") or []
    return (f"CT SKIN + CRYOSECTION ARM SKIN (Q185a2): surfaced from his CT inside its field of view; beyond x = {lo:.0f} / "
            f"+{hi:.0f} mm (lateral upper arms, elbows, proximal forearms) the surface comes from HIS OWN cryosection photographs "
            "(Visible Human male, 1 mm levels, body/gelatin colour rule), each photograph registered per arm by translation onto "
            "his arm bones (the Q151/Q164 bone-centroid registration, median-filtered over 21 levels), stacked into a 1 mm grid, "
            f"blended into the CT skin from {BLEND[0]:.0f} to {BLEND[1]:.0f} mm inside the cut and zipped onto it {WALL_MM:.0f} mm inside (one closed surface). "
            f"Photo vs CT outline in the blend band: signed median {st['blend_band_signed_offset_mm']:+.1f} mm (per-level |offset| median "
            f"{st['blend_band_abs_offset_mm_median']:.1f}, p95 {st['blend_band_abs_offset_mm_p95']:.1f} mm); join strip gap max {st['zip_strip_gap_max']:.1f} mm. "
            f"Arm records: {enc}. " + ("Still open: " + ", ".join(f"{o['side']} y {o['y_mm']}" for o in op) + "." if op else
                                        "No part of the cut is left open."))


def cmd_stamp(a) -> int:
    if not REPORT.exists() or not (SKIN / "vertices.ctonly.f32").exists():
        print("Q185a2: nothing to stamp"); return 0
    rep = json.loads(REPORT.read_text())
    if "seam_step_mm" not in rep or "merge" not in rep:
        print("Q185a2: run gates before stamp"); return 0
    m = json.loads((SKIN / "manifest.json").read_text())
    for s in m["structures"]:
        if s["atlas_id"] == "skin":
            s["procedural_badge"] = badge_text(rep)
            s["fov_skin_open"] = rep.get("fov_skin_open", [])
            s["source_note_q185a2"] = ("CT skin + cryosection-derived arm skin beyond the CT field-of-view planes; "
                                       "data/derived/Q185a2_arm_skin_vhm.json")
    (SKIN / "manifest.json").write_text(json.dumps(m, indent=2))
    print("stamped ct_vhm_skin (Q185a2)")
    return 0


# ------------------------------------------------------------------------------------------------ montage
def _render(m, view: str, box, outside_pts=None, px=1.0):
    """orthographic splat render of a mesh inside an atlas box; view: 'ant' (from the front), 'lat_l' / 'lat_r'"""
    import trimesh
    lo_, hi_ = box
    sel = np.all((m.triangles_center >= lo_) & (m.triangles_center <= hi_), 1)
    sub = trimesh.Trimesh(m.vertices, m.faces[sel], process=False)
    pts, fi = trimesh.sample.sample_surface(sub, int(sub.area / (0.35 * px) ** 2 / 1.0) + 1, seed=0)
    n = sub.face_normals[fi]
    if view == "ant":
        u, w, d, dn = -pts[:, 0], pts[:, 1], pts[:, 2], n[:, 2]       # viewer at +Z (anterior); his right on the image left
    elif view == "lat_l":
        u, w, d, dn = pts[:, 2], pts[:, 1], -pts[:, 0], -n[:, 0]     # viewer at -X (his left side)
    else:
        u, w, d, dn = -pts[:, 2], pts[:, 1], pts[:, 0], n[:, 0]
    u0, w0 = u.min(), w.max(); W = int((u.max() - u0) / px) + 2; H = int((w0 - w.min()) / px) + 2
    iu = ((u - u0) / px).astype(int); iw = ((w0 - w) / px).astype(int)
    zb = np.full((H, W), -1e9); sh = np.zeros((H, W))
    order = np.argsort(d)
    zb[iw[order], iu[order]] = d[order]; sh[iw[order], iu[order]] = np.clip(dn[order], 0, 1)
    img = np.where(zb > -1e9, 60 + 180 * sh, 255).astype(np.uint8)
    rgb = np.stack([img] * 3, -1)
    if outside_pts is not None and len(outside_pts):
        P = outside_pts
        if view == "ant":
            ou, ow = -P[:, 0], P[:, 1]
        elif view == "lat_l":
            ou, ow = P[:, 2], P[:, 1]
        else:
            ou, ow = -P[:, 2], P[:, 1]
        a = ((ou - u0) / px).astype(int); b = ((w0 - ow) / px).astype(int)
        ok = (a >= 0) & (a < W) & (b >= 0) & (b < H); rgb[b[ok], a[ok]] = [220, 30, 30]
    return rgb, (u0, w0)


def cmd_montage(a) -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(a.out or "."); out.mkdir(parents=True, exist_ok=True)
    skin_ct = load_skin_mesh(True); skin_new = load_skin_mesh(False)
    lo, hi = float(skin_ct.vertices[:, 0].min()), float(skin_ct.vertices[:, 0].max())
    recs = arm_records(Path(a.bundle), (lo, hi))
    allv = np.concatenate([v for c, v in recs.values()])
    o_ct = allv[~skin_ct.contains(allv)]; o_new = allv[~skin_new.contains(allv)]
    fig, axs = plt.subplots(2, 4, figsize=(22, 13))
    boxes = {"left": (np.array([-330, 100, -200.0]), np.array([lo + 70, 650, 250.0])),
             "right": (np.array([hi - 70, 100, -200.0]), np.array([330, 650, 250.0]))}
    for r, (nm, m, o) in enumerate((("before: CT skin (FOV cut)", skin_ct, o_ct), ("after: CT + cryosection arm skin", skin_new, o_new))):
        c = 0
        for side in ("right", "left"):
            for view in ("ant", "lat_l" if side == "left" else "lat_r"):
                b0, b1 = boxes[side]
                oo = o[np.all((o >= b0) & (o <= b1), 1)]
                img, (u0, w0) = _render(m, view, (b0, b1), oo)
                ax = axs[r, c]; ax.imshow(img); ax.set_axis_off()
                ax.set_title(f"{nm}\n{side} arm, {'anterior' if view == 'ant' else 'lateral'} (red: arm bone/muscle vertices outside skin, {len(oo)})", fontsize=9)
                if view == "ant":
                    xp = (-(lo if side == "left" else hi) - u0) / 1.0
                    ax.axvline(xp, color="orange", ls="--", lw=0.8)
                c += 1
    plt.tight_layout(); plt.savefig(out / "q185a2_arms_before_after.png", dpi=80); plt.close()
    # axial levels: photograph with the registered photo outline, the CT skin section and the merged section
    from cryo_classes import classify
    vol = np.load(Path(a.cryo) / "cryo_1mm.npy", mmap_mode="r")
    R = json.loads(REG.read_text())["sides"]
    fig, axs = plt.subplots(3, 2, figsize=(14, 18))
    for r, inst in enumerate((1360, 1560, 1660)):
        ay_ = 1880.476 - inst
        im = np.asarray(vol[inst - 1001]); body = body_mask(classify(im), im)
        for c, side in enumerate(("right", "left")):
            T = R[side]["levels"].get(str(inst), {}).get("T")
            ax = axs[r, c]
            if T is None:
                ax.set_axis_off(); continue
            plane = hi if side == "right" else lo

            def px_of(P):
                x = P[:, 0] + ORIGIN[0]; y = P[:, 2] + ORIGIN[2]
                return (y - T[1]) / PX, (T[0] - x) / PX
            ax.imshow(im); ax.contour(body, [0.5], colors="lime", linewidths=0.8)
            for m, col, lab in ((skin_ct, "cyan", "CT skin"), (skin_new, "red", "merged skin")):
                s = m.section(plane_origin=[0, ay_, 0], plane_normal=[0, 1, 0])
                if s is None:
                    continue
                for e in s.entities:
                    rr, cc = px_of(s.vertices[e.points]); ax.plot(cc, rr, "-", color=col, lw=0.9 if col == "red" else 1.6, label=lab)
                    lab = None
            xp = (T[0] - (plane + ORIGIN[0])) / PX; ax.axvline(xp, color="orange", ls="--", lw=0.8)
            rr, cc = px_of(np.array([[plane, ay_, 0.0]]))
            ax.set_xlim(cc[0] - 110, cc[0] + 90) if side == "right" else ax.set_xlim(cc[0] - 90, cc[0] + 110)
            ax.set_ylim(330, 0)
            ax.set_title(f"instance {inst} (atlas y {ay_:.0f}), his {side} arm", fontsize=9)
            ax.legend(loc="lower left", fontsize=7)
    fig.suptitle("lime = photo body outline (registered), cyan = CT skin (flat FOV cap), red = merged skin, orange = FOV plane",
                 fontsize=10)
    plt.tight_layout(rect=(0, 0, 1, 0.98)); plt.savefig(out / "q185a2_axial_levels.png", dpi=80); plt.close()
    print("wrote", out / "q185a2_arms_before_after.png", out / "q185a2_axial_levels.png")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["segment", "merge", "gates", "stamp", "montage"])
    ap.add_argument("--cryo", default=str(REPO / "SCRATCH" / "vh_cryo")); ap.add_argument("--out", default=None)
    ap.add_argument("--bundle", default=str(REPO / "build" / "viewer_m_hr"))
    a = ap.parse_args(argv)
    return {"segment": cmd_segment, "merge": cmd_merge, "gates": cmd_gates, "stamp": cmd_stamp, "montage": cmd_montage}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
