"""Q202: the footprint loop of the two male-only urogenital skin patches (zan_skin_urogenital_region_l / _r) on their neighbours, from the Z-Anatomy base page.

The Z skin patches are closed thin slabs (outer sheet + inner sheet 3.0 mm behind it + rim wall).  The urogenital patches touch the neighbouring slabs (anal, hypogastric, inguinal,
femoral triangle, anterior / posterior thigh) in a ladder of shared vertices: one rail of vertices per sheet, rungs = the 3.0 mm rim edge.  This finds both rails and orders the
rail that is complete (36 vertices) into a closed loop; it is the boundary the female variants are left with when the patches are deleted (Q196).

    python3 scripts/zanatomy/q202_loop.py  -> data/derived/Q202_perineal_loop.json  (vertices as (patch id, vertex index) of the base page = same indices on every fitted page)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_pages as P  # noqa: E402
from scripts.zanatomy import q202_geom as G  # noqa: E402

UROGENITAL = ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")
THICK = 3.0


def extract(S):
    """S = decoded skin patches of the MALE base page -> dict(loop=[node,...]) ; node = {pos, members:[(pid,idx)], partner_pos, partner_members}"""
    U = np.vstack([S[i]["v"] for i in UROGENITAL])
    tU = cKDTree(U)
    matched = {}
    for i, m in S.items():
        if i in UROGENITAL:
            continue
        dd, _ = tU.query(m["v"])
        for k in np.where(dd < 1.6)[0]:
            matched[(i, int(k))] = m["v"][k]
    partner = {}
    for (pid, idx) in matched:
        v, f = S[pid]["v"], S[pid]["f"]
        nb = set(f[(f == idx).any(1)].ravel()) - {idx}
        part = [j for j in nb if abs(np.linalg.norm(v[j] - v[idx]) - THICK) < 0.2]
        if len(part) != 1:
            raise RuntimeError(f"vertex {pid}:{idx} has {len(part)} rim partners")
        partner[(pid, idx)] = part[0]
    nodes = {}
    for k in matched:
        nodes[k] = matched[k]
        nodes[(k[0], partner[k])] = S[k[0]]["v"][partner[k]]
    keys = list(nodes)
    pos = np.array([nodes[k] for k in keys])
    pr = np.array(list(cKDTree(pos).query_pairs(0.15)))
    A = sp.coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(keys), len(keys)))
    nc, lab = connected_components(A, directed=False)
    UP = np.array([pos[lab == c].mean(0) for c in range(nc)])
    kl = {k: int(lab[i]) for i, k in enumerate(keys)}
    members = {}
    for k, c in kl.items():
        members.setdefault(c, []).append(k)
    # sheet labels (sharp-edge components) -> same-sheet constraints; rim partners -> opposite sheet
    CG = nx.Graph()
    CG.add_nodes_from(range(nc))
    for k in matched:
        CG.add_edge(kl[k], kl[(k[0], partner[k])], flip=1)
    bylab = {}
    for pid in sorted({k[0] for k in nodes}):
        v, f = S[pid]["v"], S[pid]["f"]
        se = G.sharp_edges(v, f, 55.0)
        ncomp, fl = G.face_components(f, len(v), se)
        sz = np.bincount(fl)
        big = set(np.argsort(-sz)[:2])
        for k in nodes:
            if k[0] != pid:
                continue
            b = [c for c in set(fl[(f == k[1]).any(1)]) if c in big and sz[c] >= 10]
            if len(b) == 1:
                bylab.setdefault((pid, int(b[0])), []).append(kl[k])
    for ns in bylab.values():
        for a, b in zip(ns[:-1], ns[1:]):
            if a != b:
                if CG.has_edge(a, b) and CG[a][b]["flip"] == 1:
                    raise RuntimeError("sheet constraint conflict")
                CG.add_edge(a, b, flip=0)
    colour = {}
    for comp in nx.connected_components(CG):
        s = next(iter(comp))
        colour[s] = 0
        st = [s]
        while st:
            u = st.pop()
            for v_, d in CG[u].items():
                c = colour[u] ^ d["flip"]
                if v_ not in colour:
                    colour[v_] = c
                    st.append(v_)
                elif colour[v_] != c:
                    raise RuntimeError("two-colouring conflict")
    chain = {0: set(), 1: set()}
    for pid in sorted({k[0] for k in nodes}):
        f = S[pid]["f"]
        for a, b in np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]):
            ka, kb = (pid, int(a)), (pid, int(b))
            if ka in nodes and kb in nodes:
                u, v_ = kl[ka], kl[kb]
                if u != v_ and colour[u] == colour[v_]:
                    chain[colour[u]].add((min(u, v_), max(u, v_)))
    best = None
    for c in (0, 1):
        H = nx.Graph()
        H.add_nodes_from([n for n in colour if colour[n] == c])
        H.add_edges_from(chain[c])
        if nx.number_connected_components(H) == 1 and (best is None or H.number_of_nodes() > best[1].number_of_nodes()):
            best = (c, H)
    if best is None:
        raise RuntimeError("no single rail found")
    c0, H = best
    N = H.number_of_nodes()
    start = min(H.nodes(), key=lambda n: UP[n][1])
    sys.setrecursionlimit(10000)

    def dfs(path, vis):
        if len(path) == N:
            return path if H.has_edge(path[-1], path[0]) else None
        for m in sorted(H[path[-1]], key=lambda m: np.linalg.norm(UP[m] - UP[path[-1]])):
            if m not in vis:
                r = dfs(path + [m], vis | {m})
                if r:
                    return r
        return None

    cyc = dfs([start], {start})
    if cyc is None:
        raise RuntimeError("no closed loop through the rail")
    out = []
    for n in cyc:
        mem = members[n]
        par = {}
        for (pid, idx) in mem:
            if (pid, idx) in partner:
                par[(pid, partner[(pid, idx)])] = True
        pm = sorted(par)
        ppos = np.mean([S[p][ "v"][j] for p, j in pm], axis=0) if pm else None
        out.append({"pos": UP[n].round(4).tolist(), "members": [[a, int(b)] for a, b in sorted(mem)], "partner_members": [[a, int(b)] for a, b in pm], "partner_pos": None if ppos is None else ppos.round(4).tolist()})
    return {"loop": out, "rail_colour": int(c0)}


def main():
    d, s = P.PAGES["base_m"]
    man, blob = P.load_page(REPO / d, s)
    S = P.decode(man, blob, only=lambda m: m["sys"] == "skin")
    res = extract(S)
    res["note"] = "closed rail of shared vertices between the male-only urogenital skin patches and their neighbours in the Z-Anatomy base page; vertices are (patch id, index) of that page"
    res["n"] = len(res["loop"])
    (REPO / "data" / "derived" / "Q202_perineal_loop.json").write_text(json.dumps(res, indent=0))
    L = np.array([n["pos"] for n in res["loop"]])
    seg = np.linalg.norm(np.diff(np.vstack([L, L[:1]]), axis=0), axis=1)
    print("loop nodes", len(L), "perimeter mm", seg.sum().round(1), "partners", sum(n["partner_pos"] is not None for n in res["loop"]))


if __name__ == "__main__":
    main()
