"""Mesh loading + small geometry helpers for the Q219 parts geometry (reads the published bodies' own meshes)."""
from __future__ import annotations
import base64, json, re
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
BODIES = {
    "vhm": dict(kind="own", label="own male (Visible Human male), Q214 bundle", path=REPO / "build/viewer_m_hr_q214", source_class_default="measured/rule-based/transferred per structure (Q189 subject classes)"),
    "vhf": dict(kind="own", label="own female (Visible Human female), Q216 bundle", path=REPO / "build/viewer_f_hr_q216"),
    "zan_m": dict(kind="zan", label="Z-Anatomy male fitted to the male VH (Q211 page)", path=REPO / "build/q211/viewer_zan_vhm/atlas_viewer_zan_male_fitted.html"),
    "zan_f": dict(kind="zan", label="Z-Anatomy fitted to the female VH (Q213 page)", path=REPO / "build/q213/viewer_zan_female/atlas_viewer_zan_female.html"),
    # Q220: the two UNFITTED Z-Anatomy reference bodies (base male page, base female page). Their meshes are not in the frame of the fitted
    # pages (the fit moves structures by up to ~90 mm), so the fitted placements cannot be used on them; run the same rules on these.
    "zbase_m": dict(kind="zan", label="Z-Anatomy reference body, unfitted (base male page)", path=REPO / "build/q218/viewer_zan_atlas/atlas_viewer_zan_atlas.html"),
    "zbase_f": dict(kind="zan", label="Z-Anatomy generic body, female variant, unfitted (base female page)", path=REPO / "build/q218/viewer_base_female/atlas_viewer_base_female.html"),
}


def _concat(out):
    for d in out.values():
        vs, fs, o = [], [], 0
        for v, f in d.pop("parts"):
            vs.append(v); fs.append(f + o); o += len(v)
        d["v"] = np.vstack(vs); d["f"] = np.vstack(fs)
    return out


def load_own(dirp: Path):
    b = json.loads((dirp / "bundle.json").read_text())
    blob = (dirp / "bundle.bin").read_bytes()
    q = float(b["quantum_mm"]); off = 0; out = {}
    meta = {}
    for e in b["structures"]:
        nv, nf = int(e["nv"]), int(e["nf"])
        v = np.frombuffer(blob, np.int16, nv * 3, off).reshape(-1, 3).astype(np.float64) * q; off += nv * 6
        f = np.frombuffer(blob, np.uint16, nf * 3, off).reshape(-1, 3).astype(np.int64); off += nf * 6
        d = out.setdefault(e["id"], {"cat": e["cat"], "parts": [], "subject": e.get("subject"), "badge": (e.get("rec") or {}).get("procedural_badge") or ""})
        d["parts"].append((v, f))
    return _concat(out)


def load_zan(html: Path):
    h = html.read_text(encoding="utf-8")
    i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man = json.JSONDecoder().raw_decode(h[i:])[0]
    j = h.find("window.__ANATOMY_BIN_FILES__=") + len("window.__ANATOMY_BIN_FILES__=")
    files = json.JSONDecoder().raw_decode(h[j:])[0]
    blob = b"".join(base64.b64decode((html.parent / f["path"]).read_text().strip()) for f in files)
    out = {}
    for m in man["meshes"]:
        qv = np.frombuffer(blob, "<u2", m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
        v = np.array(m["min"]) + qv / 65535.0 * np.array(m["span"])
        f = np.frombuffer(blob, "<u2", m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
        out.setdefault(m["id"], {"cat": m["sys"], "parts": [], "subject": None, "badge": (m.get("rec") or {}).get("procedural_badge") or ""})["parts"].append((v, f))
    return _concat(out)


def load_body(key):
    b = BODIES[key]
    return load_own(b["path"]) if b["kind"] == "own" else load_zan(b["path"])


def winding(points, V, F, chunk=128):
    """Generalised winding number of each point w.r.t. a (possibly open) triangle mesh."""
    A, B, C = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    out = np.empty(len(points))
    for s in range(0, len(points), chunk):
        p = points[s:s + chunk, None, :]
        a, b, c = A[None] - p, B[None] - p, C[None] - p
        la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
        det = np.einsum("ijk,ijk->ij", a, np.cross(b, c))
        den = la * lb * lc + np.einsum("ijk,ijk->ij", a, b) * lc + np.einsum("ijk,ijk->ij", a, c) * lb + np.einsum("ijk,ijk->ij", b, c) * la
        out[s:s + chunk] = np.arctan2(det, den).sum(axis=1) / (2 * np.pi)
    return out


def inside(points, V, F):
    return np.abs(winding(np.atleast_2d(points), V, F)) > 0.5


def surface_dist(points, V, F, tree=None):
    """Approximate distance from points to the triangle surface: nearest of vertices and face centroids (mesh edge length ~1-3 mm)."""
    P = np.vstack([V, V[F].mean(axis=1)])
    t = cKDTree(P)
    d, i = t.query(np.atleast_2d(points))
    return d, P[i]


def tri_nearest(points, V, F, k=12):
    """Exact nearest point on the triangle mesh for each point (candidate triangles from the k nearest vertex/centroids)."""
    P = np.vstack([V, V[F].mean(axis=1)])
    owner = np.concatenate([np.arange(len(V)), np.arange(len(F))])
    # vertex -> incident faces
    vf = [[] for _ in range(len(V))]
    for fi, f in enumerate(F):
        for u in f:
            vf[u].append(fi)
    t = cKDTree(P)
    pts = np.atleast_2d(points)
    _, idx = t.query(pts, k=k)
    best_d = np.full(len(pts), np.inf); best_p = np.zeros_like(pts)
    for n, row in enumerate(np.atleast_2d(idx)):
        cand = set()
        for r in np.atleast_1d(row):
            if r < len(V):
                cand.update(vf[r])
            else:
                cand.add(int(r - len(V)))
        for fi in cand:
            q = _closest_pt_tri(pts[n], V[F[fi, 0]], V[F[fi, 1]], V[F[fi, 2]])
            d = np.linalg.norm(q - pts[n])
            if d < best_d[n]:
                best_d[n], best_p[n] = d, q
    return best_d, best_p


def _closest_pt_tri(p, a, b, c):
    ab, ac, ap = b - a, c - a, p - a
    d1, d2 = ab @ ap, ac @ ap
    if d1 <= 0 and d2 <= 0: return a
    bp = p - b; d3, d4 = ab @ bp, ac @ bp
    if d3 >= 0 and d4 <= d3: return b
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0: return a + ab * (d1 / (d1 - d3))
    cp = p - c; d5, d6 = ab @ cp, ac @ cp
    if d6 >= 0 and d5 <= d6: return c
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0: return a + ac * (d2 / (d2 - d6))
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6)); return b + (c - b) * w
    den = 1.0 / (va + vb + vc); v, w = vb * den, vc * den
    return a + ab * v + ac * w


def union(body, sid):
    """Whole structure = base mesh + its `<sid>_zfill*` continuation pieces (own bodies)."""
    ids = [i for i in body if i == sid or (i.startswith(sid + "_zfill") and body[i]["cat"] == body[sid]["cat"])] if sid in body else []
    if not ids:
        return None
    vs, fs, o = [], [], 0
    for i in ids:
        vs.append(body[i]["v"]); fs.append(body[i]["f"] + o); o += len(body[i]["v"])
    return np.vstack(vs), np.vstack(fs)


def cat_of(body, sid):
    return body[sid]["cat"] if sid in body else None


def unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-9 else v
