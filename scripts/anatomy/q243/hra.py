"""Q243: HRA 3D Reference Object Library v1.10 (CDN, CC BY 4.0) loader + shared helpers.

The GLBs (1.2 GB) are NOT in the repo: scripts/anatomy/q243/hra.py finds them in $Q243_HRA_DIR (default: the Q242 session scratchpad `hra110/files`), else downloads the
object from the CDN URL in data/derived/Q242_hra_manifest.json and checks its sha256. Frame of every GLB: metres, +x = subject LEFT, +y up, +z anterior; converted here to the
atlas convention (mm, +X right) exactly as scripts/anatomy/q233/hra_register.py does (x -> -x, winding flipped back).
"""
from __future__ import annotations
import hashlib, json, os, urllib.request
from pathlib import Path
import numpy as np, trimesh

REPO = Path(__file__).resolve().parents[3]
MANIFEST = REPO / "data/derived/Q242_hra_manifest.json"
DEFAULT_DIR = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/hra110/files"


def local_dir() -> Path:
    return Path(os.environ.get("Q243_HRA_DIR", DEFAULT_DIR))


def object_info(obj: str) -> dict:
    for o in json.loads(MANIFEST.read_text())["objects"]:
        if o["object"] == obj:
            return o
    raise KeyError(obj)


def glb_path(obj: str) -> Path:
    """local path of the GLB of library object `obj` (e.g. 'united-female'); downloaded + sha256-checked if missing"""
    o = object_info(obj)
    f = next(x for x in o["files"] if x["file"].endswith(".glb"))
    p = local_dir() / obj / f["file"]
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(f["url"], timeout=600) as r:
        data = r.read()
    if hashlib.sha256(data).hexdigest() != f["sha256"]:
        raise RuntimeError(f"sha256 mismatch for {f['url']}")
    p.write_bytes(data)
    return p


def load_nodes(obj: str, pattern: str | None = None) -> dict:
    """{node name: (V mm atlas axis convention, F; coincident vertices merged)} for the mesh nodes of the object (optionally those whose name contains/regex-matches `pattern`)"""
    import re
    sc = trimesh.load(glb_path(obj))
    out = {}
    for n in sc.graph.nodes_geometry:
        if pattern and not re.search(pattern, n):
            continue
        T, gn = sc.graph[n]
        g = sc.geometry[gn]
        v = (np.c_[np.asarray(g.vertices, float), np.ones(len(g.vertices))] @ T.T)[:, :3] * 1000.0
        v[:, 0] *= -1.0
        m = trimesh.Trimesh(v, np.asarray(g.faces)[:, ::-1].copy(), process=True)       # glTF primitives repeat vertices at UV / normal seams: merge them (else a mesh is never watertight and decimation tears it)
        out[n] = (np.asarray(m.vertices), np.asarray(m.faces))
    return out


def to_world(T, v):
    s, R, t = T[:3]
    return s * np.asarray(v) @ R.T + t


def cap_open_ends(V, F):
    """close every boundary loop of an open tube with a triangle fan to the loop centroid. -> (V', F', info). A loop is capped only when the fan is a flat disc (the loop's best-fit plane
    deviation <= 50 % of its radius) -- a ragged or folded end stays open."""
    import collections
    m = trimesh.Trimesh(np.asarray(V, float), np.asarray(F), process=True)
    V, F = np.asarray(m.vertices), np.asarray(m.faces)
    cnt = {}
    for f in F:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            k = (min(a, b), max(a, b)); cnt[k] = cnt.get(k, 0) + 1
    dir_edges = {}
    for f in F:
        for a, b in ((f[0], f[1]), (f[1], f[2]), (f[2], f[0])):
            if cnt[(min(a, b), max(a, b))] == 1:
                dir_edges[a] = b
    loops, seen = [], set()
    for s in list(dir_edges):
        if s in seen:
            continue
        loop, x = [], s
        while x not in seen and x in dir_edges:
            seen.add(x); loop.append(x); x = dir_edges[x]
        if x == s and len(loop) >= 3:
            loops.append(loop)
    newV, newF, capped, open_left = [V], [F], 0, 0
    nv = len(V)
    for lp in loops:
        P = V[lp]; c0 = P.mean(0)
        u_, s_, vt = np.linalg.svd(P - c0)
        flat = float(np.abs((P - c0) @ vt[2]).max())
        rad = float(np.linalg.norm(P - c0, axis=1).mean())
        if flat > 0.5 * rad:
            open_left += 1
            continue
        newV.append(c0[None]); k = nv; nv += 1
        # boundary edge a->b belongs to a face traversed a->b; the cap must traverse b->a
        newF.append(np.array([[lp[(i + 1) % len(lp)], lp[i], k] for i in range(len(lp))]))
        capped += 1
    Vn, Fn = np.vstack(newV), np.vstack(newF)
    mm = trimesh.Trimesh(Vn, Fn, process=False)
    trimesh.repair.fix_normals(mm)
    return np.asarray(mm.vertices), np.asarray(mm.faces), dict(boundary_loops=len(loops), capped=capped, left_open=open_left, watertight=bool(mm.is_watertight))
