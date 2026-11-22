"""Q202 geometry helpers: thin-slab skin patches (closed shell = outer sheet + inner sheet + rim wall) -> sheet split, free borders, hole filling."""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def face_normals(v, f):
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None]


def face_components(f, nv, cut_edges=None, nf=None):
    """face components under edge adjacency, not crossing `cut_edges` (set of (a,b) sorted tuples)"""
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    fi = np.tile(np.arange(len(f)), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, fi = key[order], fi[order]
    same = np.all(key[1:] == key[:-1], axis=1)
    a, b = fi[:-1][same], fi[1:][same]
    ek = key[:-1][same]
    if cut_edges is not None and len(cut_edges):
        cs = cut_edges
        keep = np.array([(int(x), int(y)) not in cs for x, y in ek])
        a, b = a[keep], b[keep]
    A = coo_matrix((np.ones(len(a)), (a, b)), shape=(len(f), len(f)))
    return connected_components(A, directed=False)


def sharp_edges(v, f, ang_deg=55.0):
    n = face_normals(v, f)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    fi = np.tile(np.arange(len(f)), 3)
    key = np.sort(e, axis=1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    key, fi = key[order], fi[order]
    same = np.all(key[1:] == key[:-1], axis=1)
    a, b = fi[:-1][same], fi[1:][same]
    ek = key[:-1][same]
    cosang = np.einsum("ij,ij->i", n[a], n[b])
    sel = cosang < np.cos(np.radians(ang_deg))
    return {(int(x), int(y)) for x, y in ek[sel]}


def split_slab(v, f, bone_tree=None, ang=55.0):
    """split a closed thin slab (outer sheet + inner sheet + rim band) into (outer_faces, inner_faces, rim_faces) boolean masks over f.
    The two biggest face components after cutting at sharp edges are the sheets; the one farther from the bone cloud is the outer sheet (skin surface), the rest is rim band."""
    se = sharp_edges(v, f, ang)
    nc, lab = face_components(f, len(v), se)
    sizes = np.bincount(lab, minlength=nc)
    order = np.argsort(-sizes)
    a, b = order[0], order[1] if nc > 1 else order[0]
    out = {}
    cent = v[f].mean(1)
    if bone_tree is not None:
        da = bone_tree.query(cent[lab == a])[0].mean()
        db = bone_tree.query(cent[lab == b])[0].mean()
        outer, inner = (a, b) if da >= db else (b, a)
    else:
        outer, inner = a, b
    mo, mi = lab == outer, lab == inner
    return mo, mi, ~(mo | mi), sizes[order[:3]]


def boundary_edges(f, mask):
    """edges used by exactly one face of f[mask] -> (k,2) array"""
    g = f[mask]
    e = np.concatenate([g[:, [0, 1]], g[:, [1, 2]], g[:, [2, 0]]])
    key = np.sort(e, axis=1)
    u, c = np.unique(key, axis=0, return_counts=True)
    return u[c == 1]
