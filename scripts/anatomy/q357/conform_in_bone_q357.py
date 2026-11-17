#!/usr/bin/env python3
"""Q357: Base pages -- vessels and nerves that the source registration left inside a bone.

    python3 scripts/anatomy/q357/conform_in_bone_q357.py --page-dir DIR             # dry run: measure, report, write nothing
    python3 scripts/anatomy/q357/conform_in_bone_q357.py --page-dir DIR --write     # and write the page files in DIR
    python3 scripts/anatomy/q357/conform_in_bone_q357.py --page-dir DIR --screen    # only the Q337 containment screen (counts)

Finding (Q337 QA sweep, item 14): vessel / nerve vertices more than 1 mm inside a bone mesh, confirmed by containment, on 266
structures of Base·M and 268 of Base·F (testicular veins 8.7 mm in the hip bone, posterior circumflex humeral vessels 7.9 mm in the
humerus, calcaneal branches of the fibular artery wholly in the calcaneus, internal thoracic vessels 6.9 mm in the sternum).

Anatomy first: a structure that really passes through bone (canal, foramen, groove or notch the bone mesh does not model) is NOT
moved.  data/anatomy/q357_in_bone_allow.json lists, per (structure id pattern, bone), the passage with book and printed page
(owner's books, knowledge only), the 'unsure' pairs (left and listed) and the brain / ear parts filed on the nerve layer (out of
scope).  Every other in-bone pair is a registration error and is conformed:

  move     the structure's vertices inside a non-allowed bone (or closer than CLEAR mm to it) are grouped into patches (per bone,
           linked within LINK mm and with outward normals within NORMAL_DEG degrees); a patch moves along ONE direction u, the
           depth-weighted mean outward normal of the bone at its vertices, by the line-searched distance that puts every vertex
           CLEAR mm outside every non-allowed bone.  The move is a column field over the plane normal to u (conform_palm_q340.field2d:
           every point of a column along u moves alike, so a cross-section of the tube moves rigidly and keeps its radius; Lipschitz
           GRAD per mm and decayed around the requirement, so the move fades along the tube), faded out along u over FALL mm beyond
           the patch.  Up to ROUNDS rounds.  Bone inside / outside during the move: dense surface samples with outward normals
           (meshes oriented by their signed volume); the guards re-check with the generalised winding number.
  guards   (a structure failing any is left as it is and listed; sides are separate meshes and are handled independently, never
           mirrored): move <= CAP mm; no vertex inside any non-allowed bone afterwards (winding > 0.5 and deeper than END_TOL mm) and
           no new entrant into an allowed bone; no new vertex outside the skin (voxel body, as the Q337 screen); no new vertex more
           than DEEP_MUSCLE mm inside a muscle (or a brain part) that was not there before; flipped triangles <= FLIP_MAX % of the
           moved faces, stretched triangles <= before + STRETCH_ADD %; total edge length (tube length) within LEN_TOL %; moved
           cross-sections keep their radius (p95 change <= RAD_TOL mm); needle triangles (rest altitude < NEEDLE mm) flipped <=
           FLIP_NEEDLE_MAX % of the moved faces.
  write    vertex / triangle counts and order unchanged (pose rig contract); every replaced file is first copied beside itself as
           `<name>.q357` (never overwriting); each changed structure's card gets a "Q357: ..." note; a page that already carries a
           Q357 note is refused (idempotent).  Deterministic.
"""
from __future__ import annotations

import argparse, base64, json, re, shutil, sys, time
from pathlib import Path

import numpy as np
import trimesh
from scipy import sparse
from scipy.sparse import csgraph
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE.parent / "q340", HERE.parent / "q349", HERE.parent / "q241"):
    sys.path.insert(0, str(p))
import conform_palm_q340 as C340      # noqa: E402  page I/O, repack, badge_add, field2d
import conform_fingers_q349 as C349   # noqa: E402  winding number, edge helpers
import model as MD                    # noqa: E402  scripts/anatomy/q241 model (structures, bones)
from scripts.transfer.q213_inbone import flipped_pct, stretched_pct  # noqa: E402

OUT = REPO / "data/derived/Q357_in_bone_report.json"
ALLOW = REPO / "data/anatomy/q357_in_bone_allow.json"
TAG = "Q357:"
SUFFIX = ".q357"

CLEAR = 0.5          # mm outside the bone surface after the move
CAP = 10.0           # mm, per-vertex move cap (worst source depth 8.7 mm + CLEAR + line-search step)
FALL = 8.0           # mm, fade-out along u beyond a patch
LINK = 3.0           # mm, violators linked into one patch
NORMAL_DEG = 50.0    # a patch never mixes outward normals more than this apart (a vessel wrapping round a bone gets several patches)
ROUNDS = 4
ROUNDS2 = 8         # vector-field rounds
SMOOTH = 6          # Jacobi smoothing steps of the move field per round
GRAD = 0.8           # field Lipschitz slope (mm of move per mm along the tube)
END_TOL = 0.1        # mm, deepest tolerated end position inside a non-allowed bone
DEEP = 1.0           # mm, the Q337 screen threshold
DEEP_MUSCLE = 2.0    # mm, "deep" inside a muscle belly / brain part (a 1-1.5 mm radius vessel lying on a muscle is not "deep")
FLIP_MAX = 0.5       # % of moved faces (regular triangles)
NEEDLE = 0.5         # mm, rest altitude below which a triangle is a needle
FLIP_NEEDLE_MAX = 2.0  # % of moved faces (needle triangles)
STRETCH_ADD = 12.0   # % points over before (Q213 / Q340 convention)
LEN_TOL = 5.0        # % change of the total edge length ("a few %")
RAD_TOL = 0.5        # mm, p95 change of the cross-section radius of moved vertices
XS = 2.5             # mm, cross-section ball
METHODS = ("hybrid", "hybrid_xs", "columns", "field")   # tried in order, the first that passes every guard ships: hybrid = columns (the Q340
                                            # column move, push_out) then the vector field (push_field) for what it left short


def strip_id(i):
    return re.sub(r"_(l|r)$", "", re.sub(r"^zan_", "", i))


def strip_bone(b):
    return re.sub(r"_(l|r)$", "", b)


def bone_label(b):
    s = strip_bone(b)
    side = {"l": "left ", "r": "right "}.get(b[-1], "") if re.search(r"_(l|r)$", b) else ""
    ORD = {1: "1st", 2: "2nd", 3: "3rd"}
    o = lambda n: ORD.get(int(n), "%sth" % n)  # noqa: E731
    m = re.match(r"vert_([ctl])(\d+)$", s)
    if m:
        return "%s%s vertebra" % (m.group(1).upper(), m.group(2))
    m = re.match(r"rib_(\d+)$", s)
    if m:
        return "%s%s rib" % (side, o(m.group(1)))
    m = re.match(r"(mc|mt)_(\d+)$", s)
    if m:
        return "%s%s %s" % (side, o(m.group(2)), "metacarpal" if m.group(1) == "mc" else "metatarsal")
    m = re.match(r"ph_(hand|foot)_(\d+)_(prox|midd|dist)$", s)
    if m:
        part = {"prox": "proximal", "midd": "middle", "dist": "distal"}[m.group(3)]
        return "%s%s phalanx of the %s %s" % (side, part, o(m.group(2)), "finger" if m.group(1) == "hand" else "toe")
    s = re.sub(r"^(carpal|head_misc)_", "", s)
    m = re.match(r"cuneiform_(\w+)$", s)
    if m:
        s = m.group(1) + " cuneiform"
    return side + s.replace("_", " ")


# ------------------------------------------------------------------ allow-list
class Allow:
    def __init__(self, path=ALLOW):
        self.d = json.loads(Path(path).read_text(encoding="utf-8"))
        self.allow = [(e, re.compile(e["ids"]), re.compile(e["bones"])) for e in self.d["allow"]]
        self.unsure = [(e, re.compile(e["ids"]), re.compile(e["bones"])) for e in self.d["unsure"]]
        self.oos = re.compile(self.d["out_of_scope"]["ids"])

    def out_of_scope(self, sid, sys_):
        return sys_ == "nerve" and bool(self.oos.fullmatch(strip_id(sid)))

    def classify(self, sid, bone):
        """-> ('allow' | 'unsure' | 'conform', entry or None)"""
        i, b = strip_id(sid), strip_bone(bone)
        for e, ri, rb in self.allow:
            if ri.fullmatch(i) and rb.fullmatch(b):
                return "allow", e
        for e, ri, rb in self.unsure:
            if ri.fullmatch(i) and rb.fullmatch(b):
                return "unsure", e
        return "conform", None


def cite_text(allow, e):
    return "; ".join("%s p. %s" % ({"Y": "Sontakke 2023", "M": "Mannan 2017", "G": "Gray's Atlas"}[b], p) for b, p in e["cite"]) or "-"


# ------------------------------------------------------------------ bones
class Bones:
    """bone meshes oriented outward; dense surface samples with normals for a fast signed distance (+ inside); winding for checks"""

    def __init__(self, M, density=2.0):
        self.T, P, N, O = {}, [], [], []
        for k, b in M.bones().items():
            if k.startswith("oa_") or not len(b["f"]):
                continue
            v, f = b["v"], b["f"]
            t = trimesh.Trimesh(v, f, process=False)
            if t.volume < 0:
                f = f[:, ::-1]
                t = trimesh.Trimesh(v, f, process=False)
            self.T[k] = t
        self.names = sorted(self.T)
        for j, k in enumerate(self.names):
            t = self.T[k]
            n = int(max(400, t.area * density))
            p, fi = trimesh.sample.sample_surface(t, n, seed=7)
            P.append(np.vstack([p, t.vertices]).astype(np.float32)); N.append(np.vstack([t.face_normals[fi], t.vertex_normals]).astype(np.float32))
            O.append(np.full(len(p) + len(t.vertices), j, np.int32))
        self.P = np.vstack(P); self.N = np.vstack(N); self.O = np.concatenate(O)
        self.nameof = np.array(self.names, dtype=object)

    def subset(self, keep, lo=None, hi=None, margin=25.0):
        """a view restricted to the bones in `keep` (and near the box lo..hi)"""
        m = np.isin(self.O, [self.names.index(k) for k in keep])
        if lo is not None:
            m &= np.all((self.P > lo - margin) & (self.P < hi + margin), axis=1)
        return BoneView(self, np.where(m)[0])

    def inside(self, P, keys, tol=0.0):
        """generalised winding number > 0.5 and deeper than tol mm, per point, over the bones `keys` -> (bool mask, bone name, depth)"""
        P = np.atleast_2d(P)
        ins = np.zeros(len(P), bool); name = np.array([""] * len(P), dtype=object); dep = np.zeros(len(P))
        for k in keys:
            t = self.T[k]
            lo, hi = t.bounds
            m = np.all((P > lo - 0.5) & (P < hi + 0.5), axis=1) & ~ins
            if not m.any():
                continue
            idx = np.where(m)[0]
            w = np.abs(C349.winding(P[idx], t.vertices, t.faces))
            j = idx[w > 0.5]
            if not len(j):
                continue
            _, d, _ = trimesh.proximity.closest_point(t, P[j])
            ok = d > tol
            ins[j[ok]] = True; name[j[ok]] = k; dep[j[ok]] = d[ok]
        return ins, name, dep


class BoneView:
    def __init__(self, B, idx):
        self.B, self.idx = B, idx
        self.tree = cKDTree(B.P[idx]) if len(idx) else None

    def signed(self, P, k=6):
        """signed distance (+ inside) to the nearest sampled bone surface (point-to-plane at the nearest samples), outward normal, bone"""
        P = np.atleast_2d(P)
        if self.tree is None:
            return np.full(len(P), -np.inf), np.zeros_like(P), np.array([""] * len(P), dtype=object)
        kk = min(k, len(self.idx))
        d, j = self.tree.query(P, k=kk)
        if kk == 1:
            d, j = d[:, None], j[:, None]
        g = self.idx[j]
        n = self.B.N[g].astype(np.float64)
        # the nearest sample decides the bone and normal; the plane distance is averaged over the nearest samples of that bone
        own = self.B.O[g]
        same = own == own[:, :1]
        pl = -np.einsum("ijk,ijk->ij", P[:, None, :] - self.B.P[g], n)
        s = (pl * same).sum(1) / same.sum(1)
        far = (d[:, 0] > 6.0) & (s < 0)          # far outside: the plane distance can under-read; the point distance is the bound
        s[far] = -d[far, 0]
        return s, n[:, 0], self.B.nameof[own[:, 0]]


# ------------------------------------------------------------------ move (as conform_palm_q340.push_out_of_bone; patches split by normal)
def push_out(V, bs, clear=CLEAR, rounds=ROUNDS, step=0.1, fall=FALL):
    D = np.zeros_like(V); patches = []
    cosn = np.cos(np.radians(NORMAL_DEG))
    s0, _, _ = bs.signed(V)
    cand = np.where(s0 > -3.0 - XS)[0]
    for r in range(rounds):
        P = V + D
        s = np.full(len(V), -np.inf); nrm = np.zeros_like(V); nm = np.array([""] * len(V), dtype=object)
        if len(cand):
            s[cand], nrm[cand], nm[cand] = bs.signed(P[cand])
        viol = np.where(s > -clear)[0]
        if not len(viol):
            break
        for bone in sorted(set(nm[viol])):
            vb = viol[nm[viol] == bone]
            pairs = cKDTree(P[vb]).query_pairs(LINK, output_type="ndarray")
            if len(pairs):
                pairs = pairs[(nrm[vb[pairs[:, 0]]] * nrm[vb[pairs[:, 1]]]).sum(1) > cosn]
            Gp = sparse.coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])) if len(pairs) else ([], ([], [])), shape=(len(vb), len(vb)))
            nc, lab = sparse.csgraph.connected_components(Gp, directed=False)
            for c in range(nc):
                vi = vb[lab == c]
                depth = s[vi] + clear
                u = (nrm[vi] * np.maximum(depth, 0.05)[:, None]).sum(0)
                if not np.all(np.isfinite(u)) or np.linalg.norm(u) < 1e-9:
                    continue
                u /= np.linalg.norm(u)
                need = np.zeros(len(vi))
                for _ in range(int((depth.max() + 6.0) / step) + 1):
                    q, _, _ = bs.signed(P[vi] + np.outer(need, u))
                    go = q > -clear
                    if not go.any():
                        break
                    need[go] += step
                e1 = np.cross(u, [1.0, 0, 0] if abs(u[0]) < 0.9 else [0, 1.0, 0]); e1 /= np.linalg.norm(e1); e2 = np.cross(u, e1)
                cc = P[vi].mean(0)
                z = (P - cc) @ u; zr = np.abs(z[vi]).max()
                ab = np.c_[(P - cc) @ e1, (P - cc) @ e2]
                rad = np.linalg.norm(ab[vi] - ab[vi].mean(0), axis=1).max() + 12.0
                near = np.where((np.abs(z) < zr + fall) & (np.linalg.norm(ab - ab[vi].mean(0), axis=1) < rad))[0]
                if not len(near):
                    continue
                req = np.zeros(len(V)); req[vi] = need
                Lf = C340.field2d(ab[near], req[near], decay=0.9, mask_mm=4.0, sigma=2.0, iters=300, grad=GRAD)
                g = C340.smoothstep(1.0 - (np.abs(z[near]) - zr) / fall)
                D[near] += np.outer(Lf * g, u)
                patches.append(dict(round=r, bone=bone, vertices=int(len(vi)), direction=[round(float(x), 3) for x in u],
                                    move_mm=round(float(need.max()), 2)))
    return V + D, patches


def mesh_graph(V, F):
    e = C349.edges_of(F)
    w = np.linalg.norm(V[e[:, 1]] - V[e[:, 0]], axis=1) + 1e-6
    n = len(V)
    return sparse.coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(n, n)).tocsr()


def push_field(V, F, bs, clear=CLEAR, rounds=ROUNDS2, grad=GRAD):
    """vector-field move: per round, every vertex inside a non-allowed bone or closer than `clear` to it needs r = (depth + clear +
    0.05) n (n the bone's outward normal there).  The field is the Lipschitz upper envelope of those requirements in space: at a point
    p, magnitude max_j (|r_j| - grad * max(0, |p - p_j| - 2 rad_j)) (rad_j the tube radius at j, so the whole cross-section takes the
    full move and the move then fades along the tube at `grad` mm per mm), direction the envelope-weighted mean of the r_j; then
    SMOOTH Jacobi steps over the mesh (never below the requirement).  Re-measured each round until no vertex is inside."""
    G = mesh_graph(V, F)
    A = G.copy(); A.data = np.ones_like(A.data)
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    nb = cKDTree(V).query_ball_point(V, XS)
    rad = np.array([np.linalg.norm(V[i] - V[n].mean(0)) for i, n in enumerate(nb)])
    P = V.copy(); log = []
    s0, _, _ = bs.signed(V)
    cand = np.where(s0 > -3.0 - XS)[0]
    for r in range(rounds):
        s = np.full(len(V), -np.inf); nrm = np.zeros_like(V)
        if len(cand):
            s[cand], nrm[cand], _ = bs.signed(P[cand])
        viol = np.where(s > -clear)[0]
        if not len(viol):
            break
        req = (s[viol] + clear + 0.05)[:, None] * nrm[viol]
        mag = np.linalg.norm(req, axis=1)
        unit = req / np.maximum(mag, 1e-9)[:, None]
        reach = mag / grad + 2 * rad[viol]
        tr = cKDTree(P)
        m = np.zeros(len(V)); acc = np.zeros_like(V)
        for jj, j in enumerate(viol):
            idx = np.array(tr.query_ball_point(P[j], reach[jj]))
            if not len(idx):
                continue
            dd = np.linalg.norm(P[idx] - P[j], axis=1)
            e = mag[jj] - grad * np.maximum(dd - 2 * rad[j], 0.0)
            ok = e > 0
            idx, e = idx[ok], e[ok]
            m[idx] = np.maximum(m[idx], e)
            acc[idx] += e[:, None] * unit[jj]
        u = acc / np.maximum(np.linalg.norm(acc, axis=1), 1e-12)[:, None]
        D = m[:, None] * u
        for _ in range(SMOOTH):
            D = 0.5 * D + 0.5 * (A @ D) / deg[:, None]
            short = np.einsum("ij,ij->i", D[viol], unit) < mag
            if short.any():
                k = viol[short]
                D[k] += (mag[short] - np.einsum("ij,ij->i", D[k], unit[short]))[:, None] * unit[short]
        P = P + D
        log.append(dict(round=r, violators=int(len(viol)), max_requirement_mm=round(float(mag.max()), 2)))
    return P, log


# ------------------------------------------------------------------ context: skin voxel body, muscles, brain
class Context:
    def __init__(self, M, allow):
        from scipy import ndimage
        S = M.S
        self.S = S
        sk = [x for x in S if x["sys"] == "skin"]
        v, f = MD.C.merge(S, [x["idx"] for x in sk])
        # the skin as a filled voxel body, as the Q337 skin screen (geo_skin3): sampled shell, dilated 2, filled per axial slice
        # (the 3-D fill leaks through the open perineal ring), eroded back, | shell
        P_, K = 1.5, 2
        lo = v.min(0) - 12; hi = v.max(0) + 12
        shp = np.ceil((hi - lo) / P_).astype(int) + 1
        occ = np.zeros(shp, bool)
        t = trimesh.Trimesh(v, f, process=False)
        sp, _ = trimesh.sample.sample_surface(t, int(t.area * 4), seed=2)
        ijk = np.floor((sp - lo) / P_).astype(int)
        occ[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
        st = ndimage.generate_binary_structure(3, 1)
        dl = ndimage.binary_dilation(occ, st, iterations=K)
        body = np.zeros_like(dl)
        for j in range(shp[1]):
            if dl[:, j, :].any():
                body[:, j, :] = ndimage.binary_fill_holes(dl[:, j, :])
        del dl
        self.body = ndimage.binary_erosion(body, st, iterations=K) | occ
        del body, occ
        self.lo, self.pitch, self.shp = lo, P_, shp
        self.soft = {}
        for x in S:
            if x["sys"] == "muscle":
                self.soft[x["id"]] = ("muscle", x)
            elif x["sys"] == "cns" or allow.out_of_scope(x["id"], x["sys"]):
                if not re.search(r"tympanic|auditory_tube|cochlea|labyrinth|eyeball|lens|cornea|retina|vitreous|chamber", x["id"]):
                    self.soft[x["id"]] = ("brain", x)
        self.box = {k: (x["v"].min(0), x["v"].max(0)) for k, (_, x) in self.soft.items()}

    def outside_skin(self, P):
        q = np.floor((P - self.lo) / self.pitch).astype(int)
        ok = np.all((q >= 0) & (q < self.shp), 1)
        out = np.full(len(P), 99.0)
        out[ok] = np.where(self.body[q[ok, 0], q[ok, 1], q[ok, 2]], 0.0, self.pitch)
        return out

    def deep_soft(self, P):
        """per point: depth inside a muscle / brain part (0 outside) and which -> (depth, which)"""
        lo, hi = P.min(0) - 2, P.max(0) + 2
        dep = np.zeros(len(P)); which = np.array([""] * len(P), dtype=object)
        for k, (kind, x) in self.soft.items():
            a, b = self.box[k]
            if np.any(a > hi) or np.any(b < lo):
                continue
            m = np.all((P > a - 0.5) & (P < b + 0.5), axis=1)
            if not m.any():
                continue
            idx = np.where(m)[0]
            w = np.abs(C349.winding(P[idx], x["v"], x["f"]))
            j = idx[w > 0.5]
            if not len(j):
                continue
            t = trimesh.Trimesh(x["v"], x["f"], process=False)
            _, d, _ = trimesh.proximity.closest_point(t, P[j])
            better = d > dep[j]
            dep[j[better]] = d[better]; which[j[better]] = kind + ":" + k
        return dep, which


# ------------------------------------------------------------------ screen (identical to the Q337 geo_screen vn_in_bone)
def screen(M, override=None):
    import core as CC  # scripts/anatomy/q237/core.py (on sys.path through model)
    override = override or {}
    B = M.bones()
    bp, bn, bowner, bmesh = [], [], [], {}
    for k, b in B.items():
        if k.startswith("oa_"):
            continue
        v, f = b["v"], b["f"]
        if len(f) == 0:
            continue
        if CC.signed_volume(v, f) < 0:
            f = f[:, ::-1]
        m = trimesh.Trimesh(v, f, process=False)
        n = int(max(200, m.area * 1.5))
        pts, fi = trimesh.sample.sample_surface(m, n, seed=1)
        bp.append(pts); bn.append(m.face_normals[fi]); bowner += [k] * len(pts)
        bmesh[k] = m
    bp = np.vstack(bp); bn = np.vstack(bn); bowner = np.array(bowner)
    bt = cKDTree(bp)
    rows = {}
    for x in M.S:
        if x["sys"] not in ("vessel", "nerve"):
            continue
        V = override.get(x["id"], x["v"])
        d, i = bt.query(V, k=1)
        depth = -np.einsum("ij,ij->i", V - bp[i], bn[i])
        m = depth > DEEP
        if m.sum() == 0:
            continue
        own = bowner[i[m]]
        conf = 0
        for k in set(own):
            mk = own == k
            bm = bmesh[k]
            conf += int(bm.contains(V[m][mk]).sum()) if bm.is_watertight else int(mk.sum())
        if conf == 0:
            continue
        top = max(set(own), key=lambda k: (own == k).sum())
        rows[x["id"]] = dict(n=int(conf), maxdepth=round(float(depth[m].max()), 1), bone=top)
    return rows


def screen_summary(rows):
    if not rows:
        return dict(structures=0, vertices=0, worst_mm=0.0, worst=None)
    w = max(rows, key=lambda k: rows[k]["maxdepth"])
    return dict(structures=len(rows), vertices=int(sum(r["n"] for r in rows.values())), worst_mm=rows[w]["maxdepth"], worst=w)


# ------------------------------------------------------------------ per structure
def edge_len(v, f):
    e = C349.edges_of(f)
    return float(np.linalg.norm(v[e[:, 1]] - v[e[:, 0]], axis=1).sum())


def xs_radius(v, nb):
    return np.array([np.linalg.norm(v[i] - v[n].mean(0)) for i, n in enumerate(nb)])


def stats(d):
    n = np.linalg.norm(d, axis=1)
    m = n > 0.25
    return dict(max_mm=round(float(n.max()), 2), mean_moved_mm=round(float(n[m].mean()), 2) if m.any() else 0.0, moved_gt0_25mm=int(m.sum()))


def xs_average(V0, V1, passes=2):
    """each vertex takes the mean move of its cross-section (ball XS mm, at rest): the tube's cross-sections move whole"""
    nb = cKDTree(V0).query_ball_point(V0, XS)
    D = V1 - V0
    for _ in range(passes):
        D = np.array([D[n].mean(0) for n in nb])
    return V0 + D


def move(meth, V0, F, bs):
    if meth == "hybrid_xs":                   # hybrid, cross-sections averaged, then the field again for any residual
        V1, p1 = move("hybrid", V0, F, bs)
        V1 = xs_average(V0, V1)
        V1, p2 = push_field(V1, F, bs)
        return V1, p1 + p2
    if meth == "field":
        return push_field(V0, F, bs)
    if meth == "columns":
        return push_out(V0, bs)
    V1, p1 = push_out(V0, bs)                 # hybrid: columns, then the field for what the column smoothing left short
    V1, p2 = push_field(V1, F, bs)
    return V1, p1 + p2


def guards(V0, V1, F, B, ctx, near, ins0, allowed_b):
    D = V1 - V0
    mv = np.linalg.norm(D, axis=1) > 0.25
    moved_any = np.linalg.norm(D, axis=1) > 1e-6
    g = {}
    g["cap"] = dict(max_mm=round(float(np.linalg.norm(D, axis=1).max()), 2), cap_mm=CAP, ok=bool(np.linalg.norm(D, axis=1).max() <= CAP))
    ins1, nm1, dep1 = B.inside(V1, near, tol=0.0)
    bad_end = ins1 & ~np.isin(nm1, list(allowed_b)) & (dep1 > END_TOL)
    new_allowed = ins1 & np.isin(nm1, list(allowed_b)) & ~ins0 & mv
    g["end_in_bone"] = dict(vertices=int(bad_end.sum()), deepest_mm=round(float(dep1[bad_end].max()), 2) if bad_end.any() else 0.0,
                            new_into_allowed=int(new_allowed.sum()), ok=bool(not bad_end.any() and not new_allowed.any()))
    o0, o1 = ctx.outside_skin(V0), ctx.outside_skin(V1)
    new_out = (o1 > 0) & (o0 == 0) & mv
    g["skin"] = dict(new_outside=int(new_out.sum()), ok=bool(not new_out.any()))
    if mv.any():
        e0, _ = ctx.deep_soft(V0); e1, w1 = ctx.deep_soft(V1[mv])
        allow_d = max(DEEP_MUSCLE, float(e0.max()))          # "beyond what existed": the structure's own deepest soft-tissue overlap before
        d0 = e0[mv] > DEEP_MUSCLE; d1 = e1 > DEEP_MUSCLE
        newd = d1 & ~d0 & (e1 > allow_d)
        g["soft"] = dict(deep_before=int(d0.sum()), deep_after=int(d1.sum()), deepest_before_mm=round(float(e0.max()), 2),
                         deepest_new_mm=round(float(e1[d1 & ~d0].max()), 2) if (d1 & ~d0).any() else 0.0, new_beyond=int(newd.sum()),
                         where=sorted(set(w1[newd]))[:6], ok=bool(not newd.any()))
    else:
        g["soft"] = dict(deep_before=0, deep_after=0, deepest_before_mm=0.0, deepest_new_mm=0.0, new_beyond=0, where=[], ok=True)
    fm = F[moved_any[F].any(1)]
    # needle triangles (rest altitude < NEEDLE mm: the long slivers of a low-polygon tube) flip under sub-mm differential moves without
    # a visible fold; they are counted apart with their own (looser) limit
    if len(fm):
        n0 = np.cross(V0[fm[:, 1]] - V0[fm[:, 0]], V0[fm[:, 2]] - V0[fm[:, 0]])
        n1 = np.cross(V1[fm[:, 1]] - V1[fm[:, 0]], V1[fm[:, 2]] - V1[fm[:, 0]])
        emax = np.linalg.norm(V0[fm] - V0[fm[:, [1, 2, 0]]], axis=2).max(1)
        needle = np.linalg.norm(n0, axis=1) / np.maximum(emax, 1e-9) < NEEDLE
        flip = (n0 * n1).sum(1) < 0
        fl = round(100.0 * (flip & ~needle).sum() / len(fm), 2); fln = round(100.0 * (flip & needle).sum() / len(fm), 2)
    else:
        fl = fln = 0.0
    st = [round(stretched_pct(V0, V0, F), 1), round(stretched_pct(V0, V1, F), 1)]
    g["triangles"] = dict(flipped_pct_moved_faces=fl, flipped_needle_pct_moved_faces=fln, stretched_pct=st,
                          ok=bool(fl <= FLIP_MAX and fln <= FLIP_NEEDLE_MAX and st[1] <= st[0] + STRETCH_ADD))
    L0, L1 = edge_len(V0, F), edge_len(V1, F)
    g["length"] = dict(change_pct=round(100 * (L1 - L0) / L0, 2), tol_pct=LEN_TOL, ok=bool(abs(L1 - L0) / L0 * 100 <= LEN_TOL))
    if mv.any():
        nb = cKDTree(V0).query_ball_point(V0[mv], XS)
        r0 = np.array([np.linalg.norm(V0[i] - V0[n].mean(0)) for i, n in zip(np.where(mv)[0], nb)])
        r1 = np.array([np.linalg.norm(V1[i] - V1[n].mean(0)) for i, n in zip(np.where(mv)[0], nb)])
        dr = np.abs(r1 - r0)
        g["radius"] = dict(p50_change_mm=round(float(np.median(dr)), 2), p95_change_mm=round(float(np.percentile(dr, 95)), 2), tol_mm=RAD_TOL,
                           ok=bool(np.percentile(dr, 95) <= RAD_TOL))
    else:
        g["radius"] = dict(p50_change_mm=0.0, p95_change_mm=0.0, tol_mm=RAD_TOL, ok=True)
    g["kink_max_edge_rotation_deg"] = round(C349.edge_rotation(V0, V1, F, moved_any), 1)
    return g, ins1, nm1, dep1, D


def do_structure(x, B, ctx, allow):
    sid, V0, F = x["id"], x["v"], x["f"]
    lo, hi = V0.min(0), V0.max(0)
    near = [k for k in B.names if np.all(B.T[k].bounds[0] < hi + 1) and np.all(B.T[k].bounds[1] > lo - 1)]
    ins0, nm0, dep0 = B.inside(V0, near)
    rep = dict(vertices=len(V0), sys=x["sys"], bones={})
    if allow.out_of_scope(sid, x["sys"]):
        rep["decision"] = "left: out of scope (brain / ear part filed on the nerve layer)"
        return rep, None
    cls = {}
    for b in sorted(set(nm0[ins0])):
        c, e = allow.classify(sid, b)
        mb = ins0 & (nm0 == b)
        cls[b] = c
        rep["bones"][b] = dict(inside_before=int(mb.sum()), deep_before=int((mb & (dep0 > DEEP)).sum()), max_depth_mm=round(float(dep0[mb].max()), 2),
                               decision=c, entry=e["key"] if e else None, passage=(e.get("passage") or e.get("reason")) if e else None,
                               cite=cite_text(allow, e) if e else None)
    conf = [b for b, c in cls.items() if c == "conform"]
    if not conf:
        kinds = sorted(set(cls.values()))
        rep["decision"] = ("left: anatomical passage" if kinds == ["allow"] else "left: unsure" if kinds == ["unsure"] else
                           "left: anatomical passage / unsure" if kinds else "left: nothing inside a bone by winding number")
        return rep, None
    keep = set(B.names) - {b for b, c in cls.items() if c != "conform"}
    bs = B.subset(keep, lo, hi)
    allowed_b = {b for b, c in cls.items() if c != "conform"}
    tries = []
    for meth in METHODS:
        try:
            V1, patches = move(meth, V0, F, bs)
        except Exception as ex:          # recorded; the next method is tried
            tries.append(dict(method=meth, fails=["error: %s" % ex], V1=V0.copy(), g=None))
            continue
        g, ins1, nm1, dep1, D = guards(V0, V1, F, B, ctx, near, ins0, allowed_b)
        fails = sorted(k for k, v in g.items() if isinstance(v, dict) and not v["ok"])
        tries.append(dict(method=meth, fails=fails, V1=V1, g=g, ins1=ins1, nm1=nm1, dep1=dep1, D=D, patches=patches))
        if not fails:
            break
    ok_t = [t for t in tries if t["g"] is not None]
    if not ok_t:
        rep["decision"] = "left: move failed (%s)" % "; ".join(x["fails"][0] for x in tries)
        return rep, None
    t = min(ok_t, key=lambda t: (len(t["fails"]), t["g"]["cap"]["max_mm"]))
    V1, g, ins1, nm1, dep1, D, patches, fails = t["V1"], t["g"], t["ins1"], t["nm1"], t["dep1"], t["D"], t["patches"], t["fails"]
    rep["method"] = t["method"]
    rep["tries"] = [dict(method=x["method"], fails=x["fails"]) for x in tries]
    for b in conf:
        mb1 = ins1 & (nm1 == b)
        rep["bones"][b].update(inside_after=int(mb1.sum()), deep_after=int((mb1 & (dep1 > DEEP)).sum()))
    rep["patches"] = len(patches)
    rep["displacement"] = stats(D)
    rep["guards"] = g
    rep["fails"] = fails
    if fails:
        rep["decision"] = "left: guard failed (%s)" % ", ".join(fails)
        return rep, None
    rep["decision"] = "conformed" + (" (allowed / unsure bones kept)" if allowed_b else "")
    rep["conformed_bones"] = conf
    return rep, V1


def note_for(sid, rep):
    bones = [b for b in rep["conformed_bones"]]
    lab = ", ".join(bone_label(b) for b in bones)
    n = sum(rep["bones"][b]["inside_before"] for b in bones)
    dmax = max(rep["bones"][b]["max_depth_mm"] for b in bones)
    kept = [b for b, r in rep["bones"].items() if r["decision"] != "conform"]
    who = "nerve" if rep["sys"] == "nerve" else "vessel"
    st = rep["displacement"]
    tail = (" Its passage through the %s is anatomical and was kept." % ", ".join(bone_label(b) for b in kept)) if kept else ""
    return (f"{TAG} moved out of bone ({dmax:.1f} mm deep: a registration error, not a passage). Bones: the {lab}; the source registration "
            f"had left {n} of its vertices inside; each part moved along the bone's outward normal to {CLEAR:g} mm outside "
            f"the surface, cross-sections moved whole and the move fades along the {who} over about {FALL:g} mm; max {st['max_mm']} mm "
            f"(cap {CAP:g} mm), mean {st['mean_moved_mm']} mm; the shape and mesh are the source's (vertex / triangle counts unchanged).{tail}")


# ------------------------------------------------------------------ write (as conform_fingers_q349.write_page, originals kept as *.q357)
def write_page(d: Path, stem, man_old, man_new, blob_new, old_files):
    B = C340.B
    pages = C340.pages_of(d, stem)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, stem)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + SUFFIX)
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + SUFFIX)
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def key_of(d: Path):
    return "base_f" if "female" in d.name else "base_m"


def load_model(d: Path):
    import os
    key = key_of(d)
    os.environ["Q241_SRC_" + key] = str(d)
    return MD.Model(key)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--screen", action="store_true", help="only the Q337 containment screen (counts), nothing else")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/q309 (the main thread's apply step)")
    ap.add_argument("--only", default=None, help="regex on structure ids (development; never with --write)")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    if "/build/q309/" in str(d) + "/" and a.write and not a.allow_build:
        print("refused: never write into build/q309 (apply on a copy, the main thread copies the files over)")
        return 2
    if a.only and a.write:
        print("refused: --only is for development runs")
        return 2
    M = load_model(d)
    if a.screen:
        s = screen_summary(screen(M))
        print("Q357 SCREEN %s: %d structures / %d vertices > %g mm inside a bone, worst %.1f mm (%s)" % (
            d.name, s["structures"], s["vertices"], DEEP, s["worst_mm"], s["worst"]))
        return 0
    stem = C340.stem_of(d)
    man, blob, files = C340.read_page(d, stem)
    done = [m["id"] for m in man["meshes"] if TAG in ((m.get("rec") or {}).get("procedural_badge") or "")]
    if done:
        print(f"Q357 already applied to this page ({len(done)} structures carry the Q357 note, e.g. {done[0]}); nothing done")
        return 0
    V = {m["id"]: C340.dec(m, blob) for m in man["meshes"]}
    for x in M.S:
        if x["id"] in V and len(x["v"]) == len(V[x["id"]][0]):
            assert np.abs(x["v"] - V[x["id"]][0]).max() < 1e-3, x["id"]
    allow = Allow()
    t0 = time.time()
    rows0 = screen(M)
    print("screen before: %s (%.0f s)" % (screen_summary(rows0), time.time() - t0), flush=True)
    B = Bones(M)
    ctx = Context(M, allow)
    byid = {x["id"]: x for x in M.S}
    todo = sorted(k for k in rows0 if (not a.only or re.search(a.only, k)))
    structs, new = {}, {}
    for k in todo:
        x = byid[k]
        r, v1 = do_structure(x, B, ctx, allow)
        r["screen_before"] = rows0[k]
        structs[k] = r
        if v1 is not None:
            new[k] = v1
        print("  %-70s %s%s" % (k, r["decision"], ("  max %.2f mm" % r["displacement"]["max_mm"]) if "displacement" in r else ""), flush=True)
    rows1 = screen(M, override=new)
    for k, r in structs.items():
        r["screen_after"] = rows1.get(k, dict(n=0, maxdepth=0.0, bone=None))
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    replace = {}
    for k, v1 in new.items():
        note = note_for(k, structs[k])
        replace[k] = (v1, V[k][1], C340.badge_add(recs[k], note))
        structs[k]["card"] = note
    rep = {"schema": "nmsk.q357.in_bone.v1", "round": "Q357", "generated": time.strftime("%Y-%m-%d"), "page": stem, "written": bool(a.write),
           "parameters": dict(clear_mm=CLEAR, cap_mm=CAP, fall_mm=FALL, link_mm=LINK, patch_normal_deg=NORMAL_DEG, rounds=ROUNDS, grad=GRAD,
                              end_tolerance_mm=END_TOL, needle_mm=NEEDLE, flip_needle_max_pct=FLIP_NEEDLE_MAX, methods=list(METHODS), screen_depth_mm=DEEP, deep_muscle_mm=DEEP_MUSCLE, flip_max_pct=FLIP_MAX,
                              stretch_add_pct=STRETCH_ADD, length_tol_pct=LEN_TOL, radius_tol_mm=RAD_TOL, cross_section_ball_mm=XS),
           "allow_list": str(ALLOW.relative_to(REPO)),
           "screen_before": screen_summary(rows0), "screen_after": screen_summary(rows1),
           "screen_after_by_decision": {}, "structures": structs}
    byd = {}
    for k, r in structs.items():
        dkey = r["decision"].split(" (")[0]
        e = byd.setdefault(dkey, dict(structures=0, vertices_after=0))
        e["structures"] += 1; e["vertices_after"] += r["screen_after"]["n"]
    rep["screen_after_by_decision"] = byd
    rep["left_as_is"] = {k: r["decision"] for k, r in structs.items() if not r["decision"].startswith("conformed")}
    rep["geometry_changed"] = sorted(replace)
    if replace:
        man2, blob2 = C340.repack(man, blob, replace)
        for m0, m1 in zip(man["meshes"], man2["meshes"]):
            assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
        assert len(blob2) == len(blob)
        if a.write:
            rep["files_changed"] = write_page(d, stem, man, man2, blob2, files)
            print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *%s)" % SUFFIX)
    if not a.only:
        jp = Path(a.json)
        allr = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
        if allr.get("schema") != "nmsk.q357.in_bone_report.v1":
            allr = {"schema": "nmsk.q357.in_bone_report.v1", "allow_list_file": str(ALLOW.relative_to(REPO)), "pages": {}}
        allr["allow_list"] = {"sources": allow.d["sources"], "allow": allow.d["allow"], "unsure": allow.d["unsure"], "out_of_scope": allow.d["out_of_scope"]}
        allr["pages"][stem] = rep
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(allr, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (float(o) if isinstance(o, np.floating) else (int(o) if isinstance(o, np.integer) else str(o)))),
                      encoding="utf-8")
    sb, sa = rep["screen_before"], rep["screen_after"]
    print(f"Q357 {'WRITTEN' if a.write else 'DRY RUN'} {stem}: {len(replace)} structures changed; screen {sb['structures']} / {sb['vertices']} / "
          f"{sb['worst_mm']} mm -> {sa['structures']} / {sa['vertices']} / {sa['worst_mm']} mm" + ("" if a.only else f" -> {a.json}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
