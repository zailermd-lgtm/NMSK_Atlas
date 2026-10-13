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
HRA = Path("/home/user/z-anatomy/ccfrel/v1.3/models")

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
