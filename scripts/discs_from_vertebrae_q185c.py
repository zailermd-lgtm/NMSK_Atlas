"""Q185c: intervertebral discs of BOTH own-model bundles rebuilt from that body's OWN adjacent vertebral endplates.

    python3 scripts/discs_from_vertebrae_q185c.py build --body vhm|vhf     # -> build/vh/ct_v{m,f}_discs + data/derived/Q185c_discs_<body>.json
    python3 scripts/discs_from_vertebrae_q185c.py montage                  # before/after spine montage (scratch q185c/)

The discs shipped until Q185c were Q104's procedural cylinders (generate_intervertebral_discs.py: 80 mm wide, at
bounding-box midpoints; Q185 found thoracic ones 15-44 % inside lung). RULE (per adjacent vertebra pair, TS `total`
labels of the body's own CT, vertebrae_C2 49 ... vertebrae_S1 26):
 1. local frame: e3 = upper minus lower vertebral-BODY centroid (the local spine axis), e1 = atlas anterior
    orthogonalised to e3, e2 = e3 x e1 (right); refined once after the body cut.
 2. body vs posterior elements: the vertebra's voxels are projected along e3; the vertebral foramen is the largest
    hole of that projection (2-D fill-holes). The BODY is every voxel of the vertebra anterior to the canal's anterior
    border + 1 mm (the anterior column), largest connected piece. If no hole is found the spinal-cord label (79)
    inside the vertebra's height + 3 mm is used instead (method recorded per level).
 3. both bodies resampled (nearest) on a 0.5 mm grid in that frame, covering the half of each body that faces the
    gap; per column the lower endplate height h_L (top of the lower body) and upper endplate height h_U (bottom of
    the upper body); each endplate outline = the columns whose endplate lies within 3 mm of the central (5 mm
    radius) endplate height, largest piece.
 4. the disc fills h_L < z < h_U in each column, the cross-section at fraction t of the gap being the signed-distance
    interpolation (1-t) d_L + t d_U <= 0 of the two outlines (each opened by a disk of 0.15 x its equivalent diameter; heights outside a footprint: nearest-column
    extrapolation); columns whose gap exceeds the central median + max(4 mm, 0.75 x median) are dropped (processes,
    not endplates); only voxels the CT labels leave unlabelled are kept (never bone, lung, organ, cord).
 5. surface: marching cubes at 0.5 mm (Gaussian 0.5 mm) -> atlas mm.
Gates per disc: 0 % > 1 mm in lung; <= 2 % > 1 mm inside TS bone; min distance <= 1 mm to each endplate (body
surface); 0 % outside the body's own skin mesh; width / depth / height within the published adult band (REF) +-25 % (height: -37 %, Kunkel 2011's
radiographic-vs-anatomical shortfall).
A disc that fails is HELD: its Q104 geometry is carried unchanged into the new subject, badged with its Q185 numbers.
C1/C2 has no intervertebral disc (atlanto-axial joints); Q104 shipped one anyway -- it is not rebuilt and is excluded
at export. C7/T1, T12/L1 and L5/S1 are built and measured but have no atlas entity (Q104 never made those ids), so they
are reported, not shipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.ribs_from_ct_labels import LUNG, ORIGIN, TASK, load_skin, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE  # noqa: E402
from scripts.vhf_vertebra_relabel_q185k import L1B, total_volume  # noqa: E402

SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/q185c")
VERT = {"C1": 50, "C2": 49, "C3": 48, "C4": 47, "C5": 46, "C6": 45, "C7": 44, "T1": 43, "T2": 42, "T3": 41, "T4": 40,
        "T5": 39, "T6": 38, "T7": 37, "T8": 36, "T9": 35, "T10": 34, "T11": 33, "T12": 32, "L1": 31, "L2": 30, "L3": 29,
        "L4": 28, "L5": 27, "S1": 26}
ORDER = list(VERT)
PAIRS = [(ORDER[i], ORDER[i + 1]) for i in range(1, len(ORDER) - 1)]          # C2/C3 ... L5/S1 (no C1/C2 disc)
# Q185k: her spine has 6 rib-free presacral vertebrae; TS named the upper two both L1, the relabel split them into L1 (31,
# below the rib-12-bearing T12) and L1B (118). Her pairs: ... T12/L1, L1/L1B (no atlas entity: reported, not shipped),
# L1B/L2 (= her intervertebral_disc_l1_l2, the disc above her sacrum-anchored L2), L2/L3 ...
VERT["L1B"] = L1B
ORDER_BODY = {"vhm": ORDER, "vhf": ORDER[:ORDER.index("L1") + 1] + ["L1B"] + ORDER[ORDER.index("L2"):]}
PAIRS_BODY = {b: [(o[i], o[i + 1]) for i in range(1, len(o) - 1)] for b, o in ORDER_BODY.items()}
AID_ALIAS = {("vhf", "L1B", "L2"): "intervertebral_disc_l1_l2"}
CORD = 79
GRID = 0.5
# published adult reference bands (width = LR, depth = AP of the endplate; height = disc height)
REF = {
    "cervical": {"width": (15.0, 24.0), "depth": (14.0, 19.0), "height": (4.0, 7.0)},
    "thoracic": {"width": (25.0, 46.0), "depth": (16.0, 34.0), "height": (4.5, 7.2)},
    "lumbar": {"width": (40.0, 52.0), "depth": (32.0, 38.0), "height": (8.0, 14.0)},
}
REF_TOL = 0.25
# a CT-label gap is a radiographic-type measurement: Kunkel 2011 found radiographic disc heights 9 % (anterior) to 37 %
# (posterior) shorter than anatomical ones, so the HEIGHT band's lower edge allows -37 %
REF_TOL_HEIGHT_LOW = 0.37
REF_SOURCES = [
    "Panjabi MM et al. Cervical human vertebrae. Quantitative three-dimensional anatomy of the middle and lower regions. "
    "Spine 1991;16(8):861-9. doi:10.1097/00007632-199108000-00001 (C2-C7 endplate width / depth)",
    "Panjabi MM et al. Thoracic human vertebrae. Quantitative three-dimensional anatomy. Spine 1991;16(8):888-901. "
    "doi:10.1097/00007632-199108000-00006 (T1-T12 endplate width / depth)",
    "Panjabi MM et al. Human lumbar vertebrae. Quantitative three-dimensional anatomy. Spine 1992;17(3):299-306. "
    "doi:10.1097/00007632-199203000-00010 (L1-L5 endplate width / depth)",
    "Kunkel ME et al. Morphometric analysis of the relationships between intervertebral disc and vertebral body heights: "
    "thoracic spine. J Anat 2011;219(3):375-87. doi:10.1111/j.1469-7580.2011.01397.x (thoracic disc 4.5-7.2 mm)",
    "Gilad I, Nissan M. A study of vertebra and disc geometric relations of the human cervical and lumbar spine. "
    "Spine 1986;11(2):154-7. doi:10.1097/00007632-198603000-00010 (cervical / lumbar disc heights)",
    "Pfirrmann CWA et al. Effect of aging and degeneration on disc volume and shape. J Orthop Res 2006;24(5):1086-94. "
    "doi:10.1002/jor.20113 (lumbar disc height / volume)",
]
Q185C2 = {"intervertebral_disc_c7_t1", "intervertebral_disc_t12_l1", "intervertebral_disc_l5_s1"}   # entities added Q185c2
GATES = {"lung_gt1mm_frac": 0.0, "bone_gt1mm_frac": 0.02, "endplate_min_mm": 1.0, "outside_skin_frac": 0.0}
PRONOUN = {"vhm": "his", "vhf": "her"}


def aid(u: str, l: str, body: str = "vhm") -> str:
    return AID_ALIAS.get((body, u, l), f"intervertebral_disc_{u.lower()}_{l.lower()}")


def region(u: str) -> str:
    return {"C": "cervical", "T": "thoracic", "L": "lumbar"}[u[0]]


def subject(body: str) -> str:
    return f"ct_{body}_discs"


def shipped_ids() -> set:
    return {e["id"] for e in json.loads((REPO / "data" / "cartilage" / "intervertebral_disc_levels.json").read_text())}


def ref_check(u: str, w: float, d: float, h: float) -> dict:
    out = {}
    for k, v in (("width", w), ("depth", d), ("height", h)):
        lo, hi = REF[region(u)][k]
        lo_t = REF_TOL_HEIGHT_LOW if k == "height" else REF_TOL
        out[k] = {"mm": round(v, 1), "ref": [lo, hi], "ok": bool(lo * (1 - lo_t) <= v <= hi * (1 + REF_TOL))}
    return out


# ---------------------------------------------------------------- geometry (pure numpy, tested)
def frame(c_up: np.ndarray, c_lo: np.ndarray) -> np.ndarray:
    """rows e1 (anterior), e2 (right), e3 (up the local spine axis), right-handed"""
    e3 = (c_up - c_lo) / np.linalg.norm(c_up - c_lo)
    e1 = np.array([0.0, 0.0, 1.0]) - e3[2] * e3; e1 /= np.linalg.norm(e1)
    e2 = np.cross(e3, e1)
    return np.stack([e1, e2, e3])


def canal_anterior(loc: np.ndarray, cord_loc: np.ndarray | None) -> tuple[float | None, str]:
    """anterior (e1) border of the vertebral canal from local points (n,3); None if not found"""
    from scipy import ndimage as ndi
    lo = loc[:, :2].min(0) - 3; ij = np.floor((loc[:, :2] - lo) / 1.0).astype(int)
    img = np.zeros(ij.max(0) + 4, bool); img[ij[:, 0], ij[:, 1]] = True
    img = ndi.binary_closing(img, iterations=1)
    hole = ndi.binary_fill_holes(img) & ~img
    lab, n = ndi.label(hole)
    if n:
        sz = ndi.sum(hole, lab, range(1, n + 1)); k = int(np.argmax(sz)) + 1
        if sz[k - 1] >= 20:
            ii = np.argwhere(lab == k)[:, 0]
            return float(lo[0] + ii.max() + 1.0), "foramen"
    if cord_loc is not None and len(cord_loc) >= 10:
        return float(cord_loc[:, 0].max() + 3.0), "spinal_cord_label"
    return None, "none"


def fill_gap(up: np.ndarray, lo_: np.ndarray, free: np.ndarray) -> tuple[np.ndarray, dict]:
    """up / lo_ / free: bool (nx, ny, nz) grids (z up, GRID mm). Returns the disc mask + per-column stats."""
    from scipy import ndimage as ndi
    nz = up.shape[2]; z = np.arange(nz)
    hU = np.where(up.any(2), np.argmax(up, 2), -1).astype(float)
    hL = np.where(lo_.any(2), nz - 1 - np.argmax(lo_[:, :, ::-1], 2), -1).astype(float)
    def outline(m):
        # the endplate outline: open with a disk of 0.15 x the footprint's equivalent diameter (cuts transverse-process /
        # costal-element bars and pedicle stubs narrower than ~0.3 diameters, keeps the near-convex body), largest piece
        r = max(3, int(round(0.15 * np.sqrt(4 * m.sum() / np.pi))))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        m = ndi.binary_opening(m, structure=(xx ** 2 + yy ** 2) <= r * r)
        lab, n = ndi.label(m)
        return lab == (int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))) + 1) if n else m
    def band(h, sign):
        # endplate band: columns whose endplate lies within 3 mm of the central endplate height (processes and
        # pedicles hanging higher / lower than the endplate are not endplate)
        m = h >= 0
        if not m.any():
            return m
        c = np.argwhere(m).mean(0); ii = np.argwhere(m); near = np.hypot(*(ii - c).T) * GRID <= 5.0
        ref = np.median(h[tuple(ii[near].T)]) if near.any() else np.median(h[m])
        return m & (sign * (h - ref) <= 3.0 / GRID)
    FU, FL = outline(band(hU, 1)), outline(band(hL, -1))
    if not FU.any() or not FL.any():
        return np.zeros_like(up), {"error": "no endplate footprint"}
    def sdf(m):
        return (ndi.distance_transform_edt(~m) - ndi.distance_transform_edt(m)) * GRID
    dU, dL = sdf(FU), sdf(FL)
    def extrap(h, m):
        _, ind = ndi.distance_transform_edt(~m, return_indices=True)
        return h[ind[0], ind[1]]
    hU, hL = extrap(hU, FU), extrap(hL, FL)
    G = hU - hL
    both = FU & FL
    g0 = float(np.median(G[both])) if both.any() else float(np.median(G[FU | FL]))
    valid = (G > 1) & (G <= g0 + max(4.0 / GRID, 0.75 * g0))
    t = (z[None, None, :] - hL[..., None]) / np.maximum(G[..., None], 1e-6)
    D = (z[None, None, :] > hL[..., None]) & (z[None, None, :] < hU[..., None]) & valid[..., None]
    D &= ((1 - t) * dL[..., None] + t * dU[..., None]) <= 0
    D &= free
    lab, n = ndi.label(D)
    if n:
        D = lab == (int(np.argmax(ndi.sum(D, lab, range(1, n + 1)))) + 1)
    D = ndi.binary_fill_holes(D)
    return D, {"median_gap_mm": round(g0 * GRID, 2), "footprint_up_mm2": float(FU.sum() * GRID ** 2),
               "footprint_lo_mm2": float(FL.sum() * GRID ** 2)}


def run_len(line: np.ndarray, i: int) -> int:
    """length of the True run of a 1-D bool array that contains index i (0 if line[i] is False)"""
    if not line[i]:
        return 0
    a = i
    while a > 0 and line[a - 1]:
        a -= 1
    b = i
    while b < len(line) - 1 and line[b + 1]:
        b += 1
    return b - a + 1


# ---------------------------------------------------------------- per body
class Vol:
    def __init__(self, body: str):
        import nibabel as nib
        from scipy import ndimage as ndi
        img = nib.load(total_volume(body)); self.A = img.affine                # hers: Q185k-corrected labels
        self.v = np.asarray(img.dataobj).astype(np.uint8); self.sp = np.sqrt((self.A[:3, :3] ** 2).sum(0))
        self.O = np.array([float(x) for x in ORIGIN[body].split(",")]); self.objs = ndi.find_objects(self.v)

    def atlas(self, ijk: np.ndarray) -> np.ndarray:
        r = (self.A @ np.c_[ijk, np.ones(len(ijk))].T)[:3].T
        return np.c_[r[:, 0], r[:, 2], r[:, 1]] - self.O

    def points(self, lab: int) -> tuple[np.ndarray, np.ndarray]:
        sl = self.objs[lab - 1]
        ijk = np.argwhere(self.v[sl] == lab) + [s.start for s in sl]
        return ijk, self.atlas(ijk)


def body_points(V: Vol, lab: int, F: np.ndarray, c0: np.ndarray) -> tuple[np.ndarray, str]:
    """atlas points of the vertebral BODY of label `lab` (see module doc, step 2)"""
    from scipy import ndimage as ndi
    ijk, P = V.points(lab)
    loc = (P - c0) @ F.T
    cord = None
    if V.objs[CORD - 1] is not None:
        _, C = V.points(CORD); cl = (C - c0) @ F.T
        cord = cl[(cl[:, 2] >= loc[:, 2].min()) & (cl[:, 2] <= loc[:, 2].max())]
    a, how = canal_anterior(loc, cord)
    if a is None:
        return P, how
    keep = loc[:, 0] > a + 1.0
    sub = ijk[keep]; lo = sub.min(0); m = np.zeros(sub.max(0) - lo + 1, bool); m[tuple((sub - lo).T)] = True
    labm, n = ndi.label(m)
    if n > 1:
        big = int(np.argmax(ndi.sum(m, labm, range(1, n + 1)))) + 1
        sub = sub[labm[tuple((sub - lo).T)] == big]
    return V.atlas(sub), how


def build_level(V: Vol, u: str, l: str, skin) -> dict:
    from scipy import ndimage as ndi
    from scipy.spatial import cKDTree
    from skimage import measure
    import trimesh
    lu, ll = VERT[u], VERT[l]
    if V.objs[lu - 1] is None or V.objs[ll - 1] is None:
        return {"status": "absent", "reason": "vertebra label missing"}
    _, Pu = V.points(lu); _, Pl = V.points(ll)
    F = frame(Pu.mean(0), Pl.mean(0)); c0 = (Pu.mean(0) + Pl.mean(0)) / 2
    for _ in range(2):                                                     # cut, then refine the frame on the bodies
        Bu, hu = body_points(V, lu, F, c0); Bl, hl = body_points(V, ll, F, c0)
        cu, cl = Bu.mean(0), Bl.mean(0); F = frame(cu, cl); c0 = (cu + cl) / 2
    half = float(np.linalg.norm(cu - cl) / 2)
    R = 40.0; nx = ny = int(2 * R / GRID); nz = int(2 * half / GRID) + 1
    gx = (np.arange(nx) - nx / 2 + 0.5) * GRID; gz = (np.arange(nz) - (nz - 1) / 2) * GRID
    X, Y, Z = np.meshgrid(gx, gx, gz, indexing="ij")                       # X = e1 (ant), Y = e2 (right), Z = e3
    pts = c0 + X.reshape(-1, 1) * F[0] + Y.reshape(-1, 1) * F[1] + Z.reshape(-1, 1) * F[2]
    iv = np.rint(to_vox(pts, V.A, V.O)).astype(int)
    ok = np.all((iv >= 0) & (iv < V.v.shape), 1)
    labs = np.zeros(len(pts), np.uint8); labs[ok] = V.v[tuple(iv[ok].T)]
    bi = [np.rint(to_vox(B, V.A, V.O)).astype(int) for B in (Bu, Bl)]
    blo = np.minimum(bi[0].min(0), bi[1].min(0)); bhi = np.maximum(bi[0].max(0), bi[1].max(0)) + 1
    bvol = np.zeros(bhi - blo, np.uint8); bvol[tuple((bi[1] - blo).T)] = 2; bvol[tuple((bi[0] - blo).T)] = 1
    inb = np.zeros(len(pts), np.uint8); r_ = iv - blo; okb = ok & np.all((r_ >= 0) & (r_ < bvol.shape), 1)
    inb[okb] = bvol[tuple(r_[okb].T)]
    shp = (nx, ny, nz)
    up = (inb == 1).reshape(shp); lo_ = (inb == 2).reshape(shp); free = (ok & (labs == 0)).reshape(shp)
    D, st = fill_gap(up, lo_, free)
    if "error" in st or D.sum() < 50:
        return {"status": "held", "reason": st.get("error", "empty gap"), "body_method": [hu, hl]}
    vol_mm3 = float(D.sum() * GRID ** 3)
    cols = D.sum(2) * GRID
    loc_pts = np.argwhere(D) * GRID
    ext_w = float(np.ptp(loc_pts[:, 1]) + GRID); ext_d = float(np.ptp(loc_pts[:, 0]) + GRID)
    # Q185c2: chords on the hole-filled outline -- a pinhole column (dropped gap / labelled voxel) on the centre line
    # cut her L5/S1 depth chord to 8.5 mm of a 40.5 mm endplate; the mesh itself is unchanged
    fp0 = ndi.binary_fill_holes(cols > 0); ccx, ccy = np.argwhere(fp0).mean(0).round().astype(int)
    # morphometric convention (Panjabi): width = transverse chord at mid-depth, depth = mid-sagittal chord, both
    # through the footprint centroid
    width = float(run_len(fp0[ccx, :], ccy) * GRID); depth = float(run_len(fp0[:, ccy], ccx) * GRID)
    fp = cols > 0; inner = ndi.distance_transform_edt(fp) * GRID >= 3.0           # central columns, >= 3 mm from the rim
    height = float(np.median(cols[inner] if inner.any() else cols[fp])); height_rim = float(np.median(cols[fp & ~inner]))
    cx, cy = np.argwhere(cols > 0).mean(0).round().astype(int); height_c = float(cols[cx, cy])
    sm = ndi.gaussian_filter(np.pad(D.astype(np.float32), 2), 1.0)
    vv, ff, _, _ = measure.marching_cubes(sm, 0.5)
    vv = (vv - 2) * GRID; vv[:, 0] += gx[0]; vv[:, 1] += gx[0]; vv[:, 2] += gz[0]
    va = c0 + vv[:, :1] * F[0] + vv[:, 1:2] * F[1] + vv[:, 2:3] * F[2]
    mesh = trimesh.Trimesh(va, ff, process=True)
    if mesh.volume < 0:
        mesh.invert()
    m = measure_gates(V, mesh.vertices, Bu, Bl, skin, cKDTree)
    return {"status": "built", "verts": mesh.vertices.astype(np.float32), "faces": mesh.faces.astype(np.int64),
            "body_method": [hu, hl], "volume_cm3": round(vol_mm3 / 1000, 2), "mesh_volume_cm3": round(abs(mesh.volume) / 1000, 2),
            "height_median_mm": round(height, 1), "height_centre_mm": round(height_c, 1), "height_rim_mm": round(height_rim, 1), "width_mm": round(width, 1),
            "depth_mm": round(depth, 1), "extent_width_mm": round(ext_w, 1), "extent_depth_mm": round(ext_d, 1), "axis": [round(float(x), 3) for x in F[2]],
            "centre_mm": [round(float(x), 1) for x in c0], **st, **m}


def measure_gates(V: Vol, p: np.ndarray, Bu, Bl, skin, cKDTree) -> dict:
    from scipy import ndimage as ndi
    iv = to_vox(p, V.A, V.O); lo = np.maximum(np.floor(iv.min(0)).astype(int) - 12, 0)
    hi = np.minimum(np.ceil(iv.max(0)).astype(int) + 13, V.v.shape); crop = V.v[tuple(slice(a, b) for a, b in zip(lo, hi))]
    def depth(mask):
        d = ndi.distance_transform_edt(mask, sampling=V.sp).astype(np.float32) - 0.5 * float(V.sp.min())
        d = np.clip(d, 0, None); d[~mask] = 0
        return ndi.map_coordinates(d, (iv - lo).T, order=1, mode="constant", cval=0.0)
    lung = depth(np.isin(crop, LUNG)); bone = depth(np.isin(crop, BONE))
    other = depth(~np.isin(crop, [0] + list(BONE) + list(LUNG)))
    du = cKDTree(Bu).query(p)[0].min() - 0.5 * float(V.sp.min()); dl = cKDTree(Bl).query(p)[0].min() - 0.5 * float(V.sp.min())
    outside = ~skin.contains(p)
    return {"lung_gt1mm_frac": round(float((lung > 1).mean()), 4), "bone_gt1mm_frac": round(float((bone > 1).mean()), 4),
            "other_label_gt1mm_frac": round(float((other > 1).mean()), 4),
            "upper_endplate_min_mm": round(float(max(du, 0)), 2), "lower_endplate_min_mm": round(float(max(dl, 0)), 2),
            "outside_skin_frac": round(float(outside.mean()), 4), "n_vertices": int(len(p))}


def gate(r: dict) -> list[str]:
    fails = [k for k in ("lung_gt1mm_frac", "bone_gt1mm_frac", "outside_skin_frac") if r[k] > GATES[k]]
    fails += [k for k in ("upper_endplate_min_mm", "lower_endplate_min_mm") if r[k] > GATES["endplate_min_mm"]]
    fails += [f"size_{k}" for k, v in r["size_vs_published"].items() if not v["ok"]]
    return fails


def badge(body: str, u: str, l: str, r: dict) -> str:
    p = PRONOUN[body]
    return (f"RULE-BASED (Q185c, 2026-10-01): from {p} own adjacent vertebral endplates -- the gap between {p} {u} and {l} "
            f"vertebral-body endplates (TotalSegmentator labels of {p} own CT; body = the vertebra anterior to the canal), "
            f"filled per slice along the local spine axis by interpolating the two endplate outlines. Measured: "
            f"{r['width_mm']} mm wide x {r['depth_mm']} mm deep (chords through its centre), {r['height_median_mm']} mm high (median of the central columns), "
            f"{r['volume_cm3']} cm3. CT does not show disc tissue: shape follows the bone, not a disc segmentation."
            + (Q185K_NOTE if body == "vhf" and {u, l} & {"L1", "L1B"} else ""))


Q185K_NOTE = (" VARIANT (Q185k): her spine has 6 rib-free presacral vertebrae (7 C + 12 T + 6 L; rib 12 on T12, none below); "
              "TotalSegmentator named the first two both L1, the Q185k relabel (scripts/vhf_vertebra_relabel_q185k.py) split "
              "them -- L1 = the one under T12, L1B = the extra one; L2-L5 keep the sacrum-anchored numbering, so her "
              "'L1/L2' disc is the one between L1B and L2 and her L1/L1B disc has no atlas entity (not shown).")


def held_badge(body: str, q185: dict | None, why: list) -> str:
    q = q185 or {}
    return (f"PROCEDURAL/RULE-BASED (Q104 cylinder, HELD in Q185c: the endplate rebuild failed {', '.join(why)}). "
            f"Q185 sweep of this mesh: {round(100 * (q.get('in_lung_gt1mm_frac') or 0), 1)} % in lung, "
            f"{round(100 * (q.get('in_bone_gt1mm_frac') or 0), 1)} % in bone, {round(100 * (q.get('in_organ_gt1mm_frac') or 0), 1)} % "
            "in organs; ~80 mm wide, not fitted to the vertebrae. Hidden by default.")


def old_record(body: str, a: str):
    d = REPO / "build" / "vh" / f"ct_{body}"; m = json.loads((d / "manifest.json").read_text())
    s = next((x for x in m["structures"] if x["atlas_id"] == a), None)
    if s is None:                       # Q185c2: entity added later, no Q104 cylinder exists -> nothing to carry
        return None, None
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3); Fc = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    return (V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]],
            Fc[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"])


def build(body: str) -> int:
    import gc
    skin = load_skin(body); V = Vol(body); ids = shipped_ids()
    q185p = REPO / "data" / "derived" / "Q185_placement_sweep.json"
    q185 = json.loads(q185p.read_text())[body]["structures"] if q185p.exists() else {}
    rows, verts, faces, structs = {}, [], [], []; nv = nf = 0
    for u, l in PAIRS_BODY[body]:
        a = aid(u, l, body); r = build_level(V, u, l, skin); gc.collect()
        if r["status"] == "built":
            r["size_vs_published"] = ref_check(u, r["width_mm"], r["depth_mm"], r["height_median_mm"])
            r["gate_fails"] = gate(r); r["status"] = "pass" if not r["gate_fails"] else "held"
        v, f = r.pop("verts", None), r.pop("faces", None)
        r["atlas_id"] = a; r["has_atlas_entity"] = a in ids
        r["shipped"] = "new" if (r["status"] == "pass" and a in ids) else ("old_q104_held" if a in ids else "not_shipped_no_entity")
        if a in ids and r["status"] != "pass" and old_record(body, a)[0] is None:
            v = None; r["shipped"] = "held_not_shipped"          # Q185c2 ids: no Q104 mesh to fall back on
        elif a in ids and r["status"] != "pass":
            v, f = old_record(body, a); bd = held_badge(body, q185.get(a), r.get("gate_fails") or [r.get("reason", "?")])
            src = "Q104 geometry carried from ct_" + body
        elif a in ids:
            bd = badge(body, u, l, r); src = f"Q185c endplate fill {u}/{l}"
        else:
            v = None
        if v is not None:
            v = np.asarray(v, np.float32)
            structs.append({"atlas_id": a, "source_structure": a, "side": None,
                            "source_file": f"scripts/discs_from_vertebrae_q185c.py#{a}", "vertex_offset": nv,
                            "face_offset": nf, "vertex_count": int(len(v)), "triangle_count": int(len(f)),
                            "bbox_min_mm": [round(float(x), 4) for x in v.min(0)],
                            "bbox_max_mm": [round(float(x), 4) for x in v.max(0)], "tris_full_at_source": int(len(f)),
                            "procedural_badge": bd, "geometry_source": src,
                            **({"hidden_default": True} if src.startswith("Q104") else {})})   # held ~80 mm cylinders start hidden (Q184 flag)
            verts.append(v); faces.append(np.asarray(f, np.int64) + nv); nv += len(v); nf += len(f)
        rows[a] = r
        print(f"{body} {u}/{l}: {r['status']} {r.get('gate_fails', r.get('reason', ''))} "
              f"w{r.get('width_mm')} d{r.get('depth_mm')} h{r.get('height_median_mm')} lung{r.get('lung_gt1mm_frac')} "
              f"bone{r.get('bone_gt1mm_frac')} ep{r.get('upper_endplate_min_mm')}/{r.get('lower_endplate_min_mm')} "
              f"skin{r.get('outside_skin_frac')} -> {r['shipped']}", flush=True)
    out = REPO / "build" / "vh" / subject(body); out.mkdir(parents=True, exist_ok=True)
    Va = np.concatenate(verts).astype(np.float32); Fa = np.concatenate(faces).astype(np.uint32)
    Va.tofile(out / "vertices.f32"); Fa.tofile(out / "faces.u32")
    man = {"subject": subject(body), "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
           "source_volume": str(total_volume(body).relative_to(REPO)), "source_kind": "rule_based_from_ct_labels",
           "vertex_count": int(len(Va)), "triangle_count": int(len(Fa)),
           "bbox_min_mm": [round(float(x), 4) for x in Va.min(0)], "bbox_max_mm": [round(float(x), 4) for x in Va.max(0)],
           "attribution": ["Q185c: intervertebral discs filled between this body's own TotalSegmentator vertebral-body "
                           "endplates (scripts/discs_from_vertebrae_q185c.py); replaces the Q104 procedural cylinders."],
           "structures": structs}
    (out / "manifest.json").write_text(json.dumps(man, indent=2))
    rep = {"_README": (__doc__ or "").strip().splitlines(), "body": body, "gates": GATES, "reference_bands": REF,
           "reference_tolerance": REF_TOL, "reference_tolerance_height_low": REF_TOL_HEIGHT_LOW, "references": REF_SOURCES,
           "c1_c2": "no intervertebral disc exists at C1/C2 (atlanto-axial joints); Q104 shipped intervertebral_disc_c1_c2 "
                    "-- excluded at export from Q185c on", "levels": rows}
    (REPO / "data" / "derived" / f"Q185c_discs_{body}.json").write_text(json.dumps(rep, indent=1))
    print(f"wrote {out}: {len(structs)} records ({sum(r['shipped'] == 'new' for r in rows.values())} new, "
          f"{sum(r['shipped'] == 'old_q104_held' for r in rows.values())} held)")
    return 0


# ---------------------------------------------------------------- montage
def montage(out: Path) -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(2, 4, figsize=(20, 22))
    for row, body in enumerate(("vhm", "vhf")):
        V = Vol(body)
        spine = np.concatenate([V.points(VERT[k])[1] for k in ORDER if V.objs[VERT[k] - 1] is not None])
        lung = V.atlas(np.argwhere(np.isin(V.v[::3, ::3, ::3], LUNG)) * 3)
        old = [o for o in (old_record(body, a) for a in sorted(shipped_ids())) if o[0] is not None]   # Q185c2 ids: none
        d = REPO / "build" / "vh" / subject(body); m = json.loads((d / "manifest.json").read_text())
        Vn = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3)
        new = [Vn[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]] for s in m["structures"]]
        held = [("Q104" if s["geometry_source"].startswith("Q104") else "Q185c2" if s["atlas_id"] in Q185C2 else "")
                for s in m["structures"]]
        rng = np.random.default_rng(0); sp = spine[rng.choice(len(spine), min(len(spine), 60000), replace=False)]
        for col, (title, discs, hl) in enumerate((("before (Q104)", [o[0] for o in old], [True] * len(old)),
                                                    ("after (Q185c)", new, held))):
            for k, (ia, ib, lab) in enumerate(((2, 1, "sagittal (Z ant -> right)"), (0, 1, "coronal (X right -> right)"))):
                a = ax[row, col * 2 + k]
                if k == 0:
                    sel = np.abs(lung[:, 0] - np.median(sp[:, 0])) < 25
                else:
                    sel = np.abs(lung[:, 2] - np.median(sp[:, 2])) < 15
                a.scatter(lung[sel, ia], lung[sel, ib], s=0.3, c="#9ecae1", alpha=0.3, lw=0)
                a.scatter(sp[:, ia], sp[:, ib], s=0.2, c="0.55", alpha=0.4, lw=0)
                for dv, h in zip(discs, hl):
                    c = {"": "#2ca02c", "Q185c2": "#9467bd"}.get(h, "#d62728") if h is not True else "#d62728"
                    a.scatter(dv[:, ia], dv[:, ib], s=1.0 if h != "Q104" and h is not True else 3, c=c, lw=0)
                a.set_aspect("equal"); a.set_title(f"{body} {title}: {lab}", fontsize=10)
                a.set_xlim(np.median(sp[:, ia]) - 90, np.median(sp[:, ia]) + 90)
        del V
    fig.suptitle("Q185c intervertebral discs: grey = TS vertebrae, blue = lung, red = Q104 cylinder / held, green = Q185c endplate fill, purple = Q185c2 new ids (C7/T1, T12/L1, L5/S1)")
    fig.tight_layout(rect=(0, 0, 1, 0.98)); p = out / "montage_spine_before_after.png"; fig.savefig(p, dpi=70); print("wrote", p)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build", "montage"])
    ap.add_argument("--body", choices=["vhm", "vhf"]); ap.add_argument("--out", default=str(SCRATCH))
    a = ap.parse_args(argv)
    if a.cmd == "build":
        return build(a.body)
    return montage(Path(a.out))


if __name__ == "__main__":
    sys.exit(main())
