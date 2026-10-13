"""Q233: register the HRA / HuBMAP CCF 'VH_F' reference organs (Visible Human FEMALE, CC BY 4.0) onto THIS atlas's female (her own CT frame) by
rigid+uniform-scale ICP of the HRA VH_F pelvis bones onto her own hip bones + sacrum + coccyx. HRA frame: metres, +x = patient LEFT, +y sup, +z ant;
atlas frame: mm, +X right, +Y sup, +Z ant -> the first step is x -> -x (a change of axis convention, not a mirroring of the anatomy)."""
from __future__ import annotations
import sys, json
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
HRA = REPO / "third_party" / "hra_vh_f"          # copies of the HRA v1.3 VH_F models (CC BY 4.0), see third_party/hra_vh_f/NOTICE.md

def hra_mesh(name):
    """-> list of (node_name, V mm in atlas axis convention, F)"""
    sc = trimesh.load(HRA / f"{name}.glb")
    out = []
    for g in sc.dump():
        v = np.asarray(g.vertices, float) * 1000.0
        v[:, 0] *= -1.0
        f = np.asarray(g.faces)
        f = f[:, ::-1]            # reflection of the axis convention flips winding; flip back so normals stay outward
        out.append(((g.metadata or {}).get("name", name), v, f))
    return out

def umeyama(A, B, scale=True):
    ca, cb = A.mean(0), B.mean(0)
    X, Y = A - ca, B - cb
    U, S, Vt = np.linalg.svd(Y.T @ X / len(A))
    d = np.ones(3); d[-1] = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    R = U @ np.diag(d) @ Vt
    s = (S * d).sum() / ((X ** 2).sum() / len(A)) if scale else 1.0
    t = cb - s * R @ ca
    return s, R, t

def icp(src, dst_tree, dst_pts, s0=1.0, iters=80, trim=0.85, scale=True):
    s, R, t = s0, np.eye(3), np.zeros(3)
    t = dst_pts.mean(0) - s * src.mean(0)
    for _ in range(iters):
        P = s * src @ R.T + t
        d, i = dst_tree.query(P)
        keep = d <= np.quantile(d, trim)
        s, R, t = umeyama(src[keep], dst_pts[i[keep]], scale)
    P = s * src @ R.T + t
    d, _ = dst_tree.query(P)
    return s, R, t, d


def register_to(S_list, ids=("hip_bone_l", "hip_bone_r", "coccyx", "sacrum"), seed=0, n_dst=40000):
    """S_list = Q233 loader output of an own-female style page (her frame). Returns (s, R, t, d) mapping HRA(atlas-axis, mm) -> her frame."""
    rng = np.random.default_rng(seed)
    pts = []
    for x in S_list:
        base = x["id"].split("#")[0]
        if base in ids and x["sys"] == "bone" and "zfill" not in x["id"]:
            m = trimesh.Trimesh(x["v"], x["f"], process=False)
            cc = m.split(only_watertight=False)
            m = max(cc, key=lambda c: len(c.vertices))
            if len(m.vertices) < 1000:
                continue
            pts.append(m.sample(n_dst))
    dst = np.vstack(pts)
    pel = hra_mesh("VH_F_Pelvis")
    sm = []
    for n, v, f in pel:
        m = trimesh.Trimesh(v, f, process=False)
        sm.append(m.sample(max(200, len(f) // 3)))
    src = np.vstack(sm)
    tree = cKDTree(dst)
    return icp(src, tree, dst)

def apply(T, v):
    s, R, t = T[:3]
    return s * v @ R.T + t


# ---------------------------------------------------------------------------------------------------------------- closed surfaces from the HRA parts
from scipy import ndimage as ndi
from skimage.measure import marching_cubes


def parts_world(name, T):
    return [(n, apply(T, v), f) for n, v, f in hra_mesh(name)]


def closed_surface(parts, pitch=0.6, close_it=2, sigma=0.7, pad=5.0, seed=0):
    np.random.seed(seed)                                                       # trimesh surface sampling draws from the global numpy RNG: reproducible builds
    """union of the (open or closed) part surfaces -> voxel shell -> closing -> hole fill -> Gaussian -> marching cubes. -> (V, F, info)"""
    V = np.vstack([v for _, v, _ in parts])
    lo = V.min(0) - pad
    shape = tuple(np.ceil((V.max(0) + pad - lo) / pitch).astype(int))
    g = np.zeros(shape, bool)
    for _, v, f in parts:
        m = trimesh.Trimesh(v, f, process=False)
        pts = m.sample(int(m.area / (pitch * pitch * 0.12)) + 2000)
        idx = np.clip(np.floor((pts - lo) / pitch).astype(int), 0, np.array(shape) - 1)
        g[tuple(idx.T)] = True
    ball = np.ones((3, 3, 3), bool)
    gd = ndi.binary_dilation(g, structure=ball, iterations=1)                  # 26-connected one-voxel thickening: a point-sampled shell may touch only diagonally, 6-connected background would leak
    gc = ndi.binary_closing(gd, iterations=close_it)
    fl = ndi.binary_erosion(ndi.binary_fill_holes(gc), structure=ball, iterations=1)
    lab, k = ndi.label(fl)
    if k > 1:
        sizes = ndi.sum(fl, lab, range(1, k + 1))
        fl = lab == (1 + int(np.argmax(sizes)))
    fld = ndi.gaussian_filter(fl.astype(np.float32), sigma)
    vv, ff, _, _ = marching_cubes(fld, 0.5, spacing=(pitch,) * 3)
    vv = vv + lo
    m = trimesh.Trimesh(vv, ff, process=True)
    trimesh.repair.fix_normals(m)
    # the shell voxels are centred ON the source surface, so the filled solid is one half voxel too large on every side: move the surface back along its normals
    m.vertices = m.vertices - m.vertex_normals * (0.5 * pitch)
    trimesh.repair.fix_normals(m)
    info = dict(volume_cm3=round(float(abs(m.volume)) / 1000, 2), watertight=bool(m.is_watertight), components=int(len(m.split(only_watertight=False))),
                shell_voxel_cm3=round(float(g.sum()) * pitch ** 3 / 1000, 2), pitch_mm=pitch, closing_iterations=close_it)
    # fidelity: every source-surface sample lies within x mm of the closed surface
    t = cKDTree(m.sample(60000))
    src = np.vstack([trimesh.Trimesh(v, f, process=False).sample(8000) for _, v, f in parts])
    d = t.query(src)[0]
    info["source_to_closed_surface_mm"] = dict(median=round(float(np.median(d)), 2), p95=round(float(np.quantile(d, .95)), 2), max=round(float(d.max()), 2),
                                               note="includes inner part surfaces (cavity, os surfaces) that the filled envelope encloses, so p95 / max are not an error")
    ts = cKDTree(np.vstack([trimesh.Trimesh(v, f, process=False).sample(30000) for _, v, f in parts]))
    d2 = ts.query(m.sample(30000))[0]
    info["closed_surface_to_source_mm"] = dict(median=round(float(np.median(d2)), 2), p95=round(float(np.quantile(d2, .95)), 2), max=round(float(d2.max()), 2))
    return np.asarray(m.vertices), np.asarray(m.faces), info
