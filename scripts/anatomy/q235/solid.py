"""Q235: closed solids from the CVH meshes. Finding (Q235): the README / structures.json of third_party/cvh_wu2015 count a mesh as 'open' when a DIRECTED edge has no opposite edge; for most of the 47 meshes the surface is
edge-manifold and closed (every undirected edge shared by exactly two triangles, vertices NOT welded) but the triangle winding is not consistent between neighbouring triangles. Re-orienting the triangles
(trimesh.repair.fix_winding + fix_inversion: only the vertex ORDER of triangles is changed, no vertex moves) gives oriented closed surfaces with a defined volume. Components that stay non-manifold are reported, not repaired."""
from __future__ import annotations
import numpy as np, trimesh
from scripts.anatomy.q235 import cvh


def components(V, F):
    """connected components of the RAW (unwelded) triangle soup by shared vertex index -> list of (V, F) with compact indices"""
    m = trimesh.Trimesh(V, F, process=False)
    out = []
    for idx in trimesh.graph.connected_components(m.face_adjacency, nodes=np.arange(len(F)), min_len=1):
        f = F[idx]
        u, inv = np.unique(f, return_inverse=True)
        out.append((V[u], inv.reshape(-1, 3)))
    return out


def edge_stats(F):
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    u, c = np.unique(e, axis=0, return_counts=True)
    return int((c == 1).sum()), int((c > 2).sum())


def orient(V, F):
    """-> (F', info). F' = F with consistent winding and outward normals if the component is closed + edge-manifold, else F unchanged"""
    nb, nn = edge_stats(F)
    info = dict(faces=int(len(F)), open_edges=nb, nonmanifold_edges=nn)
    m = trimesh.Trimesh(V, F, process=False)
    info["winding_consistent_before"] = bool(m.is_winding_consistent)
    if nb == 0 and nn == 0:
        trimesh.repair.fix_winding(m)
        trimesh.repair.fix_inversion(m, multibody=False)
        info.update(closed=bool(m.is_watertight and m.is_winding_consistent), volume_cm3=round(float(m.volume) / 1000, 4), euler=int(m.euler_number), reoriented=not info["winding_consistent_before"])
        return np.asarray(m.faces), info
    info.update(closed=False, volume_cm3=None)
    return F, info


def orient_bfs(V, F):
    """consistent triangle orientation by propagation over MANIFOLD edges (two triangles per edge); edges shared by 4 triangles (two surfaces kissing along an edge) do not carry the propagation. The whole component is then
    flipped if its signed volume is negative. Only the vertex order of triangles changes. -> F'"""
    import collections
    F = F.copy()
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    fid = np.tile(np.arange(len(F)), 3)
    u, inv, c = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    order = np.argsort(inv, kind="stable")
    starts = np.r_[0, np.cumsum(c)]
    adj = collections.defaultdict(list)
    for k in np.where(c == 2)[0]:
        a, b = fid[order[starts[k]:starts[k + 1]]]
        adj[a].append(b); adj[b].append(a)
    seen = np.zeros(len(F), bool)
    for s0 in range(len(F)):
        if seen[s0]:
            continue
        seen[s0] = True; st = [s0]; members = [s0]
        while st:
            x = st.pop()
            for y in adj[x]:
                if seen[y]:
                    continue
                shared = set(F[x]) & set(F[y])
                a, b = sorted(shared)
                # edge direction in x and in y must be opposite
                def dirn(face):
                    for j in range(3):
                        p, q = face[j], face[(j + 1) % 3]
                        if {p, q} == {a, b}:
                            return (p, q)
                if dirn(F[x]) == dirn(F[y]):
                    F[y] = F[y][::-1]
                seen[y] = True; st.append(y); members.append(y)
        vol = float(np.einsum("ij,ij->i", V[F[members, 0]], np.cross(V[F[members, 1]], V[F[members, 2]])).sum() / 6.0)
        if vol < 0:
            F[members] = F[members][:, ::-1]
    return F


def signed_volume_cm3(V, F):
    return float(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6.0) / 1000.0


def voxel_volume_cm3(V, F, pitch=0.35):
    """volume enclosed by the triangle soup (flood fill from outside; works for edge-non-manifold closed soups too)"""
    from scipy import ndimage as ndi
    lo = V.min(0) - 2 * pitch; shape = tuple(np.ceil((V.max(0) + 2 * pitch - lo) / pitch).astype(int))
    g = np.zeros(shape, bool)
    m = trimesh.Trimesh(V, F, process=False)
    pts = m.sample(int(m.area / (pitch * pitch * 0.08)) + 5000)
    idx = np.floor((pts - lo) / pitch).astype(int)
    g[tuple(idx.T)] = True
    g = ndi.binary_dilation(g, iterations=1)
    lab, k = ndi.label(~g)
    outside = lab == lab[0, 0, 0]
    inside = ~outside & ~g
    inside = ndi.binary_dilation(inside, iterations=1) & ~outside    # give the one voxel shell back to the inside (the dilation of the shell ate half a voxel each side)
    return float(inside.sum()) * pitch ** 3 / 1000.0


def split_nonmanifold(V, F):
    """Edges shared by 4 triangles (two surfaces touching along an edge) are made manifold by pairing the four triangles by the flattest dihedral angle (each surface continues smoothly through the edge) and un-welding
    the vertex fans of the edge's endpoints. Only vertex INDICES are duplicated; no vertex moves. -> (V', F', n_edges_split)"""
    F = F.copy(); V = V.copy()
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    fid = np.tile(np.arange(len(F)), 3)
    u, inv, c = np.unique(e, axis=0, return_inverse=True, return_counts=True)
    bad = np.where(c == 4)[0]
    if len(bad) == 0:
        return V, F, 0
    tri_n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]); tri_n /= np.linalg.norm(tri_n, axis=1, keepdims=True) + 1e-18
    # adjacency over MANIFOLD edges and the chosen pairs
    pair = {}
    for b in bad:
        fs = fid[inv.ravel() == b]
        a, bb = u[b]
        ev = V[bb] - V[a]; ev /= np.linalg.norm(ev) + 1e-18
        # unfolded angle of each face around the edge: direction of the face's opposite vertex perpendicular to the edge
        ang = []
        for f in fs:
            w = [x for x in F[f] if x != a and x != bb][0]
            p = V[w] - V[a]; p -= ev * (p @ ev); p /= np.linalg.norm(p) + 1e-18
            ang.append(p)
        ang = np.array(ang)
        best = None
        for part in ((0, 1, 2, 3), (0, 2, 1, 3), (0, 3, 1, 2)):
            s = 0.0
            for i, j in ((part[0], part[1]), (part[2], part[3])):
                s += float(np.arccos(np.clip(ang[i] @ ang[j], -1, 1)))      # angle between the two faces' half-planes: pi = flat continuation
            if best is None or s > best[0]:
                best = (s, part)
        part = best[1]
        pair[(a, bb)] = [(fs[part[0]], fs[part[1]]), (fs[part[2]], fs[part[3]])]
    # local vertex fans: for every endpoint v of a 4-face edge, the faces around v are grouped into fans that are connected through manifold edges containing v and through the chosen pairs; one vertex copy per fan
    import collections
    inc = collections.defaultdict(list)
    for fi in range(len(F)):
        for j in range(3):
            inc[F[fi, j]].append(fi)
    emap = collections.defaultdict(list)
    for k in range(len(inv)):
        emap[inv[k]].append(fid[k])
    chosen = {}
    for (a, bb), pairs in pair.items():
        for x, y in pairs:
            chosen[(x, y)] = chosen[(y, x)] = True
    badset = set(map(int, bad))
    ends = set()
    for b in bad:
        ends.update(map(int, u[b]))
    extra = []; nv = len(V)
    newF = F.copy()
    for v in sorted(ends):
        fs = inc[v]
        nbr = collections.defaultdict(set)
        for ei in set(inv[k] for k in range(0)):   # placeholder (never executed)
            pass
        idx = {f: n for n, f in enumerate(fs)}
        parent = list(range(len(fs)))
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x
        for f in fs:
            for g in fs:
                if f >= g:
                    continue
                shared = set(F[f]) & set(F[g])
                if len(shared) < 2 or v not in shared:
                    continue
                w = [x for x in shared if x != v][0]
                ek = (min(v, w), max(v, w))
                # edge multiplicity
                mult = len(emap[np.where((u[:, 0] == ek[0]) & (u[:, 1] == ek[1]))[0][0]])
                if mult == 2 or (mult == 4 and (f, g) in chosen):
                    parent[find(idx[f])] = find(idx[g])
        groups = collections.defaultdict(list)
        for f in fs:
            groups[find(idx[f])].append(f)
        gl = list(groups.values())
        for grp in gl[1:]:
            for f in grp:
                for j in range(3):
                    if newF[f, j] == v:
                        newF[f, j] = nv
            extra.append(V[v]); nv += 1
    V2 = np.vstack([V, np.array(extra)]) if extra else V
    return V2, newF, int(len(bad))
