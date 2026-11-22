"""Q338: positional audit of the wrist / hand / fingers of a Base page at rest, and of how the hand's soft tissue
follows its bones under the page's own pose rig (Python replica of viewer/pose/pose.js: the page's NMSK-POSE-RIG block,
weights decoded as pose.js buildSkin does, FK as scripts/anatomy/q241/fk.py).  Reads the page dir, never writes it.

Rules (rest) -- each one is anatomy that every textbook states, measured in the finger frames of hand_frame.py:
  digital    proper palmar digital arteries / nerves / veins: on the PALMAR half of the phalanx (palmar offset > 0 from
             the bone's own centre line), lateral to it (|radial| >= 2.5 mm), within 15 mm of the bone axis, a radial
             and an ulnar strand on every finger 2-5; dorsal digital arteries / nerves / veins: dorsal half (offset < 0)
  tendons    flexor tendons, digital synovial sheaths, fibrous sheath (annular / cruciform parts) on the palmar side of
             the phalanges; extensor tendons on the dorsal side
  skin       nothing of the hand lies outside the hand's skin (> 2 mm out along the skin normal)
  bone       no soft tissue passes through a hand bone (> 1.5 mm deep inside a watertight bone mesh)
  mirror     the left structure, mirrored on the page's midsagittal plane, lies on the right one (mean distance)
  side       a structure named _l / _r lies on that side of the midsagittal plane
"""
from __future__ import annotations
import collections, json, os, re, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hand_frame as HF  # noqa: E402
import rig_io_q338 as RIO  # noqa: E402
sys.path.insert(0, str(HF.Q241))
import fk as FK  # noqa: E402
import make_pose_rig as MR  # noqa: E402

DIGITAL_PALMAR = re.compile(r"proper_palmar_digital|palmar_digital_veins")
DIGITAL_DORSAL = re.compile(r"dorsal_digital_(arteries|branches|veins)_of_hand|dorsal_digital_branches_of_(radial|ulnar)_nerve")
FLEXOR = re.compile(r"(flexor_digitorum_(superficialis|profundus)|flexor_pollicis_longus|synovial_sheaths_of_digits|fibrous_sheath_of_digit)")
EXTENSOR = re.compile(r"(^|_)(extensor_digitorum|extensor_indicis|extensor_digiti_minimi|extensor_pollicis_longus|extensor_pollicis_brevis)_(l|r)$")
FOOT = re.compile(r"foot|plantar|toe|hallu|tars|fibul|tibia|leg|ankle|digitorum_longus|digitorum_brevis")


def key_of(page_dir):
    return "base_f" if "female" in Path(page_dir).name else "base_m"


class Page:
    def __init__(self, page_dir, rig_json=None):
        """rig_json: read the rig from a data/anatomy/pose_rig_<key>.json file instead of the page's own block (to test a rebuilt rig before it is injected)"""
        self.dir = Path(page_dir).resolve()
        self.key = key_of(page_dir)
        os.environ["Q241_SRC_" + self.key] = str(self.dir)
        self.M = HF.MD.Model(self.key)
        if rig_json:
            import base64, zlib
            src = json.loads(Path(rig_json).read_text(encoding="utf-8"))
            self.rig = src["rig"]; self.blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
        else:
            self.rig = RIO.page_rig(self.dir)
            self.blob = RIO.page_weights(self.dir)
        self.H = {s: HF.Hand(self.M, self.rig, s) for s in "rl"}
        self.byid = {x["id"]: x for x in self.M.S}
        self.sid = {sg[0]: n for n, sg in enumerate(self.rig["segs"])}
        self._w = {}
        self._rigid = {}
        for sg, ids in self.rig["rigid"]:
            for i in ids:
                self._rigid[i] = sg
        self._skin = {e[0]: e for e in self.rig["skin"]}
        self._wrist = {j["side"]: j["c"] for j in self.rig["joints"] if j["id"].startswith("wrist_")}

    # ------------------------------------------------------------------ which structures are the hand's
    def hand_structs(self, s, min_frac=0.25):
        """structure indices of side s with >= min_frac of their vertices distal to the wrist and within 30 mm of a hand bone"""
        B = self.M.bones()
        hb = [k for k in B if k.endswith("_" + s) and re.match(r"(mc_|ph_hand_|carpal_)", k)]
        P = np.vstack([B[k]["v"] for k in hb])
        tr = cKDTree(P)
        J = {j["id"]: j for j in self.rig["joints"]}
        w = np.array(J["wrist_" + s]["c"])
        d_h = HF.unit(np.vstack([B["mc_%d_%s" % (f, s)]["v"] for f in range(2, 6)]).mean(0) - w)
        out = []
        for x in self.M.S:
            if x["sys"] == "bone" or FOOT.search(x["id"]):
                continue
            v = x["v"]
            if x["side"] not in (s, "m") and not x["id"].endswith("_" + s):
                continue
            q = v[:: max(1, len(v) // 400)]
            if ((q - w) @ d_h > 0).mean() < min_frac:
                continue
            d, _ = tr.query(q, k=1, distance_upper_bound=30.0)
            m = np.isfinite(d) & ((q - w) @ d_h > -5)
            if m.mean() >= min_frac:
                out.append(x["idx"])
        return out, w, d_h

    # ------------------------------------------------------------------ weights as the viewer decodes them
    def weights(self, i):
        """-> (seg (nv,3) segment indices, w (nv,3)) for a skinned structure; rigid -> (nv,1) of its segment, weight 1"""
        if i in self._w:
            return self._w[i]
        nv = len(self.M.S[i]["v"])
        if i in self._rigid:
            r = (np.full((nv, 1), self._rigid[i], np.int32), np.ones((nv, 1)))
        else:
            _, nv_, K, pal, off, nc = self._skin[i]
            nb = (nv + 7) // 8
            b = np.frombuffer(self.blob, np.uint8, count=nb + K * nc + (K - 1) * nc, offset=off)
            ctrl = np.unpackbits(b[:nb])[:nv].astype(bool)
            pi = np.stack([b[nb + k * nc: nb + (k + 1) * nc] for k in range(K)], 1).astype(np.int64)
            q = np.zeros((nc, K))
            for k in range(1, K):
                q[:, k] = b[nb + K * nc + (k - 1) * nc: nb + K * nc + k * nc]
            q[:, 0] = 255 - q[:, 1:].sum(1)
            sg, w = MR.decode_weights(self.M.S[i]["v"], ctrl, pal, pi, q)
            r = (sg, w)
        self._w[i] = r
        return r

    def fk(self, pose=None):
        P = pose or FK.default_pose(self.rig)
        return FK.fk(self._rig_for_fk(), P)

    def _rig_for_fk(self):
        if not hasattr(self, "_rfk"):
            segs = [dict(id=s[0], par=s[1]) for s in self.rig["segs"]]
            self._rfk = dict(segments=segs, joints=self.rig["joints"], regions=self.rig["regions"])
        return self._rfk

    def posed(self, i, Ms):
        v = self.M.S[i]["v"]
        sg, w = self.weights(i)
        out = np.zeros_like(v)
        for k in range(sg.shape[1]):
            for s_ in np.unique(sg[:, k]):
                m = (sg[:, k] == s_) & (w[:, k] > 0)
                if m.any():
                    T = Ms[s_]
                    out[m] += w[m, k, None] * (v[m] @ T[:3, :3].T + T[:3, 3])
        return out


# ---------------------------------------------------------------------- rest rules
def skin_shell(pg, s):
    """the hand + wrist + distal forearm skin of side s as one trimesh, normals made outward per patch (checked against the bones)"""
    import trimesh
    pat = re.compile(r"zan_skin_(palm|palmar_surfaces_of_digits_of_hand|dorsal_surfaces_of_digits_of_hand|dorsum_of_hand|nail_plate|anterior_region_of_wrist|posterior_region_of_wrist|anterior_region_of_forearm|posterior_region_of_forearm|lateral_border_of_forearm|medial_border_of_forearm)_%s$" % s)
    B = pg.M.bones()
    bp = np.vstack([B[k]["v"] for k in B if k.endswith("_" + s) and re.match(r"(mc_|ph_hand_|carpal_|radius|ulna)", k)])
    btr = cKDTree(bp)
    vs, fs, off, names = [], [], 0, []
    for x in pg.M.S:
        if pat.match(x["id"]):
            v, f = x["v"], x["f"].copy()
            t = trimesh.Trimesh(v, f, process=False)
            c = t.triangles_center; n = t.face_normals
            _, j = btr.query(c)
            if (np.einsum("ij,ij->i", c - bp[j], n) < 0).mean() > 0.5:      # normals point toward the bones: flip the patch
                f = f[:, ::-1]
            vs.append(v); fs.append(f + off); off += len(v); names.append(x["id"])
    return trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False), names


def outside_skin(shell, P):
    """signed distance of P along the nearest skin face's outward normal (> 0 = outside)"""
    import trimesh
    Q, dist, tri = trimesh.proximity.closest_point(shell, P)
    n = shell.face_normals[tri]
    return np.einsum("ij,ij->i", P - Q, n)


def bones_of_hand(pg, s):
    import trimesh
    B = pg.M.bones()
    return {k: trimesh.Trimesh(B[k]["v"], B[k]["f"], process=False) for k in B if k.endswith("_" + s) and re.match(r"(mc_|ph_hand_|carpal_)", k)}


def inside_bone(bones, P, depth=1.5):
    """per point: name of the hand bone it lies inside by more than `depth` mm, else ''"""
    import trimesh
    out = np.array([""] * len(P), dtype=object)
    for k, t in bones.items():
        lo, hi = t.bounds
        m = np.all((P > lo - 1) & (P < hi + 1), axis=1)
        if not m.any():
            continue
        idx = np.where(m)[0]
        ins = t.contains(P[idx])
        if ins.any():
            ii = idx[ins]
            _, d, _ = trimesh.proximity.closest_point(t, P[ii])
            deep = ii[d > depth]
            out[deep] = k
    return out


def digital_components(pg, s, x):
    """components of a multi-digit vessel / nerve mesh, located on the fingers -> list of dict"""
    H = pg.H[s]
    v = x["v"]
    rows = []
    for comp in HF.mesh_parts(x, 6):
        L = H.locate(v[comp])
        # in-finger points only: on a phalanx (not the thumb metacarpal), not clamped at its ends
        fing = np.array([(f != 1 or sg_ > 0) for f, sg_ in zip(L["finger"], L["seg"])])
        m = fing & (L["t"] > 0.02) & (L["t"] < 0.98) & (L["dist"] < 25)
        if m.sum() < 5:
            rows.append(dict(n=len(comp), in_finger=int(m.sum()), comp=comp))
            continue
        fs, cnt = np.unique(L["finger"][m], return_counts=True)
        f = int(fs[cnt.argmax()])
        mm = m & (L["finger"] == f)
        rows.append(dict(n=len(comp), in_finger=int(m.sum()), finger=f, share=float(cnt.max() / m.sum()),
                         palmar_med=float(np.median(L["palmar"][mm])), palmar_min=float(L["palmar"][mm].min()), palmar_max=float(L["palmar"][mm].max()),
                         radial_med=float(np.median(L["radial"][mm])), dist_med=float(np.median(L["dist"][mm])), dist_max=float(L["dist"][mm].max()),
                         segs=sorted(set(L["seg"][mm].tolist())), comp=comp, L=L, m=mm))
    return rows


def mirror_dist(pg, xl, xr):
    """mean distance of the mirrored left vertices to the right mesh's vertices and back (mm)"""
    a = pg.M.plane.reflect(xl["v"]); b = xr["v"]
    d1, _ = cKDTree(b).query(a); d2, _ = cKDTree(a).query(b)
    return float(0.5 * (d1.mean() + d2.mean())), float(max(np.percentile(d1, 95), np.percentile(d2, 95)))


# ---------------------------------------------------------------------- posed: does the soft tissue follow its own bone?
FINGER_SEGS = {f: ["f%d_p_%%s" % f, "f%d_m_%%s" % f, "f%d_d_%%s" % f] for f in range(2, 6)}
FINGER_SEGS[1] = ["th_mc_%s", "th_p_%s", "th_d_%s"]
BONE_OF_SEG = {"p": "prox", "m": "midd", "d": "dist"}


def bone_segments(pg, s):
    """hand + forearm bone vertices of side s labelled with their rig segment index -> (pts, seg, tree)"""
    B = pg.M.bones()
    pts, lab = [], []
    for k in B:
        if not k.endswith("_" + s) or not re.match(r"(mc_|ph_hand_|carpal_|radius_|ulna_)", k):
            continue
        m = re.match(r"ph_hand_(\d)_(prox|midd|dist)_", k)
        if k.startswith(("radius_", "ulna_")):          # the forearm bones too: a vertex lying on the radius styloid follows the radius
            sg = "rad_" if k.startswith("radius_") else "uln_"
        elif m:
            f, ph = int(m.group(1)), m.group(2)
            if f == 1:
                sg = "th_p_" if ph == "prox" else "th_d_"
            else:
                sg = "f%d_%s_" % (f, ph[0])
        elif k.startswith("mc_1_"):
            sg = "th_mc_"
        else:
            sg = "hand_"
        sid = pg.sid.get(sg + s)
        if sid is None:
            continue
        v = B[k]["v"]
        pts.append(v); lab.append(np.full(len(v), sid))
    P = np.vstack(pts); L = np.concatenate(lab)
    return P, L, cKDTree(P)


def joint_list(pg, s):
    """finger / thumb / wrist joints of side s with their flexion dof range: [(id, k, lo, hi, q0)]"""
    out = []
    for j in pg.rig["joints"]:
        if j["side"] != s or not re.match(r"(f\d_(mcp|pip|dip)|thumb_(cmc|mcp|ip)|wrist)_", j["id"]):
            continue
        for d in j["dof"]:
            out.append((j["id"], d["k"], d["lo"], d["hi"], d["q0"]))
    return out


JOINT_SCALE = {"wrist": 20.0 / 7.0, "mcp": 12.0 / 7.0, "cmc": 12.0 / 7.0, "pip": 9.0 / 7.0, "ip": 9.0 / 7.0, "dip": 1.0}   # joint zone radius: wrist 20 (the carpus), MCP / CMC 12, PIP / IP 9, DIP 7 mm


def own_segment(pg, s, P, tree_pack, joint_mm=7.0, faces=None, iters=3):
    """per vertex: the segment of its nearest hand bone (then, with `faces`, the majority of its mesh neighbours for `iters` rounds: a vertex of
    finger 3's skin tube lying in the narrow gap against finger 4 belongs to finger 3), and whether it is 'mid-shaft' (outside every joint zone
    of that side, JOINT_SCALE) -- only those have one unambiguous segment to follow"""
    BP, BL, tr = tree_pack
    d, i = tr.query(P)
    seg = BL[i]
    if faces is not None and len(faces):
        from scipy import sparse
        e = np.r_[faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]
        A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(P), len(P))).tocsr()
        A = ((A + A.T) > 0).astype(np.float32)
        near = d < 15
        for _ in range(iters):
            ids, inv = np.unique(seg, return_inverse=True)
            oh = np.zeros((len(P), len(ids)), np.float32); oh[np.arange(len(P)), inv] = near
            cnt = A @ oh + oh
            seg = np.where(near & (cnt.max(1) > 0), ids[cnt.argmax(1)], seg)
    js = [j for j in pg.rig["joints"] if j["side"] == s and re.match(r"(f\d_(mcp|pip|dip)|thumb_(cmc|mcp|ip)|wrist)_", j["id"])]
    J = np.array([j["c"] for j in js])
    R = np.array([joint_mm * JOINT_SCALE.get(re.sub(r"^(f\d_|thumb_)?(\w+?)_[lr]$", r"\2", j["id"]), 1.0) for j in js])
    D = np.linalg.norm(P[:, None, :] - J[None, :, :], axis=2)
    dj = np.min(D, axis=1)
    return seg, d, (D > R[None, :]).all(1), dj


def pose_for(pg, moves):
    """moves: {(joint id, dof k): value} -> FK pose dict (everything else at the model pose)"""
    P = FK.default_pose(pg.rig)
    J = {j["id"]: j for j in pg.rig["joints"]}
    for (jid, k), val in moves.items():
        j = J[jid]
        for n, d in enumerate(j["dof"]):
            if d["k"] == k:
                P["joints"][jid][n] = float(min(max(val, d["lo"]), d["hi"]))
    return P


def follow(pg, s, idx, moves, tol=2.0, joint_mm=7.0, pack=None, wrist_mm=None, band_mm=None, own_in=None, own_out=None, over=15.0):
    """Pose `moves`, then per structure: for its vertices that lie on a finger bone's shaft (nearest bone within 12 mm, farther than joint_mm
    from every hand joint centre), the distance between where the pose puts them and where their own bone segment takes them (rigidly).
    -> list of dict(id, n, bad (> tol mm), max, p95, worst [(own segment, dominant segment) counts])"""
    Ms = pg.fk(pose_for(pg, moves))
    pack = pack or bone_segments(pg, s)
    segname = [g[0] for g in pg.rig["segs"]]
    out = []
    for i in idx:
        x = pg.M.S[i]
        if x["sys"] == "bone":
            continue
        v = x["v"]
        own, dbone, mid, dj = own_segment(pg, s, v, pack, joint_mm, faces=x["f"])
        seam = digit_seam(own, x["f"], segname) | digit_gap(pg, s, v, own, pack, segname)
        m = mid & (dbone < 12) & ~seam
        if own_in is not None:                       # only vertices whose own bone is one of these segments (ids)
            m = m & np.isin(own, [pg.sid[x] for x in own_in if x in pg.sid])
        if own_out is not None:
            m = m & ~np.isin(own, [pg.sid[x] for x in own_out if x in pg.sid])
        if wrist_mm is not None:                     # the wrist tests: a wider wrist zone, mm distal to the wrist centre along the hand (the carpus + the CMC joints); band_mm: ONLY that band
            c = np.array(pg._wrist[s]); B = pg.M.bones()
            dh = np.vstack([B["mc_%d_%s" % (f_, s)]["v"] for f_ in range(2, 6)]).mean(0) - c; dh /= np.linalg.norm(dh)
            dw = (v - c) @ dh
            m = m & (dw > wrist_mm) & ((dw <= band_mm) if band_mm else True)
        if not m.any():
            continue
        moved_own = np.array([Ms[o][:3, :3] @ p + Ms[o][:3, 3] for o, p in zip(own[m], v[m])])
        if np.abs(moved_own - v[m]).max() < 1e-6:          # nothing on this structure's bones moved
            continue
        P = pg.posed(i, Ms)[m]
        dev = np.linalg.norm(P - moved_own, axis=1)
        travel = np.linalg.norm(moved_own - v[m], axis=1)
        sg, w = pg.weights(i)
        dom = sg[np.where(m)[0], w[m].argmax(1)]
        bad = dev > tol
        worst = collections.Counter((segname[a], segname[b]) for a, b in zip(own[m][bad], dom[bad])).most_common(3)
        od = [digit_of(segname[a]) for a in own[m]]; dd = [digit_of(segname[b]) for b in dom]
        cross = int(sum(1 for a, b in zip(od, dd) if a and b and a != b))
        out.append(dict(id=x["id"], sys=x["sys"], n=int(m.sum()), seam=int((seam & mid & (dbone < 12)).sum()), moved=int((travel > tol).sum()), bad=int(bad.sum()), n_over=int((dev > over).sum()), max=float(dev.max()), p95=float(np.percentile(dev, 95)), cross=cross, worst=worst))
    return out


def digit_of(name):
    m = re.match(r"^(f\d|th)_", name)
    return m.group(1) if m else None


def digit_seam(own, faces, segname):
    """vertices with a mesh neighbour on ANOTHER digit: where one source mesh joins two fingers (the fingers touch at rest and the Z skin /
    vessel sheet runs across the gap). Moving one finger alone has to stretch those triangles; they are reported apart, not counted as lag."""
    dg = np.array([digit_of(segname[o]) or "" for o in own], dtype=object)
    e = np.r_[faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]
    a, b = dg[e[:, 0]], dg[e[:, 1]]
    x = (a != "") & (b != "") & (a != b)
    out = np.zeros(len(own), bool)
    out[e[x, 0]] = True; out[e[x, 1]] = True
    return out


GAP_MM = 2.0


def digit_gap(pg, s, v, own, pack, segname):
    """vertices of a digit lying in the narrow gap against ANOTHER digit: the other digit's bone is less than GAP_MM farther than its own
    digit's bone (the fingers touch at rest). Which finger such a point belongs to is not decided by the geometry; reported apart."""
    BP, BL, tr = pack
    key = ("_gap_trees", s)
    trees = pg.__dict__.setdefault("_gap", {}).get(key)
    if trees is None:
        trees = {}
        for dgt in ["th"] + ["f%d" % f for f in range(2, 6)]:
            ids = [pg.sid[q] for q in pg.sid if q.startswith(dgt + "_") and q.endswith("_" + s)]
            sel = np.isin(BL, ids)
            if sel.any():
                trees[dgt] = cKDTree(BP[sel])
        pg._gap[key] = trees
    od = np.array([digit_of(segname[o]) or "" for o in own], dtype=object)
    out = np.zeros(len(v), bool)
    for dgt, t in trees.items():
        r = np.where(od == dgt)[0]
        if not len(r):
            continue
        da, _ = t.query(v[r])
        do = np.full(len(r), np.inf)
        for d2, t2 in trees.items():
            if d2 != dgt:
                do = np.minimum(do, t2.query(v[r])[0])
        out[r] = (do - da) < GAP_MM
    return out
