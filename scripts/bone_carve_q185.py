"""Q185 d/e/h/i/j: generic bone-carve post-process -- soft structures sitting inside their OWN body's bone.

    python3 scripts/bone_carve_q185.py --body vhm|vhf --subject S1 --subject S2 ... [--exclude SUBJECT:GLOB ...]

Run by both rebuild scripts right before export_viewer_bundle.py with the SAME --subject / --exclude list, so the
records it looks at are exactly the ones the exporter ships (first subject providing an id wins). Works on the
build/vh/<subject> records IN PLACE: the untouched file is kept as vertices.preq185.f32 and every run starts from it
(idempotent; a subject rebuilt by its own script is detected by checksum and becomes the new original).

Bone = that body's own bone, the same reference the Q185 sweep uses (scripts/placement_sweep_q185.py): TotalSegmentator
`total` bone labels inside the CT field of view OR the body's own bone meshes for bones TS does not label / that leave
the FOV (femur, hip). Signed distance: label part = EDT inside minus EDT outside (voxel-face surface, trilinear), mesh
part = exact closest point on the bone surface, side by the sweep's nearest-vertex pseudo-normal test.

Candidates: every shipped muscle / tendon / ligament / cartilage / vessel / nerve record with > 5 % of its vertices
> 1 mm inside bone (the Q185 flag), minus EXCLUDED (bones, canal passengers, label-overlap false positives, other
queue items, hidden_default records). Per mode (MODE):
  push   (muscle, vessel, nerve): vertices > 0.5 mm inside and <= 4 mm deep move along the SDF gradient to the bone
         surface + 0.5 mm; deeper ones stay (bounded, like the project's earlier snaps)
  trim   (tendon, ligament): an insertion ends at the bone -- every in-bone vertex slides along the mesh path towards its
         nearest outside vertex to the bone surface + 0.5 mm (= the part inside bone is cut at the surface)
  shell  (cartilage): sits ON bone -- projected out (displacement diffused to the neighbours, thickness kept) only when
         the median move <= 3 mm; otherwise held + hidden by default (no new cartilage is invented)
Exit direction = the SDF gradient (label SDF Gaussian-smoothed by one voxel; mesh: towards the closest surface point)
averaged over the moved patch's mesh neighbours, so a patch moves coherently; the rim just below surface + 0.5 mm follows.
Every mode: fold guard -- faces next to moved vertices must not flip or collapse: the move of a folded face's vertices is
first relaxed (local Laplacian of the displacement, moved vertices only), what still folds is backed off (half, quarter)
and finally reverted; the shipped mesh has 0 flipped faces. A second pass runs from the first result when the gate fails. GATE: ship only if <= 5 % of vertices remain > 1 mm inside bone
and (push / shell) the enclosed volume changed by <= 25 %; else the original is kept, hidden_default set when it is
> 20 % inside bone, and the badge gives its numbers. Report: data/derived/Q185_bone_carve_<body>.json.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.placement_sweep_q185 import (BONE_EXCLUDE_IDS, MAX_PTS, MESH_BONE_EXTRA, TS_BONE_IDS, _nii,  # noqa: E402
                                          depth_map, edt_inside, sample_depth)
from scripts.ribs_from_ct_labels import ORIGIN, TASK, to_vox  # noqa: E402
from scripts.costal_cartilage_from_ct_labels import BONE  # noqa: E402

VH = REPO / "build" / "vh"
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/q185bone")
MODE = {"muscle": "push", "vessel": "push", "nerve": "push", "tendon": "trim", "ligament": "trim", "cartilage": "shell"}
P = {"offset": 0.5, "inside_tol": 0.5, "max_depth": 4.0, "shell_median_max": 3.0, "flag_mm": 1.0, "flag_frac": 0.05,
     "gate_frac": 0.05, "band": 0.5, "smooth_rounds": 0, "gate_vol": 0.25, "hide_frac": 0.20}
# not handled here (stated in the report): label-overlap false positives (Q185 "ref"), Q185b limb transfers (skin +
# bone refit, own queue item), Q185c discs (rebuilt from the endplates)
EXCLUDE_ID_RE = re.compile(r"^(lateral_pterygoid|temporalis)_[lr]$|^intervertebral_disc_")
EXCLUDE_SUBJECT_RE = re.compile(r"^(xfer_zan2vh[mf]_limb|xfer_zan2vhf_foot)")
TAG = "Q185 bone carve"
STATE = "q185_carve_state.json"
BACKUP = "vertices.preq185.f32"


# ---------------------------------------------------------------- mesh helpers (pure, tested)
def adjacency(nv: int, f: np.ndarray):
    from scipy import sparse
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    e = np.r_[e, e[:, ::-1]]
    a = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)).tocsr()
    a.data[:] = 1.0
    return a


def with_rim(A, core, band):
    """core + the band vertices connected to it: the rim just below surface + offset follows the moved core,
    else its faces fold over the moved ones"""
    sel = core.copy()
    for _ in range(50):
        grow = band & ~sel & (np.asarray(A @ sel.astype(float)).ravel() > 0)
        if not grow.any():
            break
        sel |= grow
    return sel


def face_normals(v, f):
    return np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])


def volume(v, f) -> float:
    return float(abs(np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum()) / 6.0)


def relax(v, A, idx, lam=0.5, iters=2):
    deg = np.asarray(A.sum(1)).ravel(); deg[deg == 0] = 1
    for _ in range(iters):
        mean = (A @ v) / deg[:, None]
        v[idx] = (1 - lam) * v[idx] + lam * mean[idx]
    return v


def fold_guard(v0, v1, f, moved, A=None, untangle=40):
    """faces next to moved vertices must not flip (or collapse): first untangle -- the displacement of a flipped face's
    moved vertices is replaced by its neighbourhood mean (local Laplacian of the move) --, then back off what is left:
    half, quarter, then revert"""
    n0 = face_normals(v0, f); a0 = np.linalg.norm(n0, axis=1)
    disp = v1 - v0; scale = np.ones(len(v0)); backed = 0; smoothed = set()
    if A is not None:
        deg = np.asarray(A.sum(1)).ravel() + 1.0
        for _ in range(untangle):
            n1 = face_normals(v0 + disp, f)
            bad = ((np.einsum("ij,ij->i", n0, n1) <= 0) | (np.linalg.norm(n1, axis=1) < 1e-3 * np.maximum(a0, 1e-12)))
            bad &= (a0 > 1e-12) & moved[f].any(1)
            if not bad.any():
                break
            bv = np.unique(f[bad].ravel()); bv = bv[moved[bv]]
            ring = np.unique(np.r_[bv, A[bv].indices]); ring = ring[moved[ring]]
            mean = (A[ring] @ disp + disp[ring]) / deg[ring][:, None]
            disp[ring] = mean; smoothed.update(ring.tolist())
    for step in range(40):
        n1 = face_normals(v0 + disp * scale[:, None], f)
        bad = (np.einsum("ij,ij->i", n0, n1) <= 0) | (np.linalg.norm(n1, axis=1) < 1e-3 * np.maximum(a0, 1e-12))
        bad &= a0 > 1e-12
        bad &= moved[f].any(1)
        if not bad.any():
            break
        bv = np.unique(f[bad].ravel()); bv = bv[moved[bv] & (scale[bv] > 0)]
        if not len(bv):
            break
        backed += len(bv)
        scale[bv] = np.where(step < 2, scale[bv] * 0.5, 0.0)
    n1 = face_normals(v0 + disp * scale[:, None], f)
    flips = int(((np.einsum("ij,ij->i", n0, n1) <= 0) & (a0 > 1e-12)).sum())
    return v0 + disp * scale[:, None], {"untangled": len(smoothed), "backed_off": int(backed),
                                        "reverted": int(((scale == 0) & moved).sum()),
                                        "flipped_faces_left": flips}


def coherent(g, idx, A, iters=6):
    """exit directions of the vertices idx smoothed over the mesh (neighbours within idx only): a patch straddling a
    thin bone's mid-plane otherwise splits to both sides and folds"""
    if A is None or len(idx) < 2:
        return g
    S = A[idx][:, idx]; deg = np.asarray(S.sum(1)).ravel() + 1.0
    G = g.copy()
    for _ in range(iters):
        G = (S @ G + G) / deg[:, None]
    n = np.linalg.norm(G, axis=1); keep = n > 0.3          # no consensus: keep the vertex's own direction
    G[keep] /= n[keep][:, None]; G[~keep] = g[~keep]
    return G


def _push(v, field, idx, tgt, cap, v0, A=None):
    """move v[idx] along the (mesh-smoothed) exit direction until it lies tgt mm outside bone (scalar or per vertex);
    3 Newton-like passes, total move <= cap"""
    tgt = np.broadcast_to(np.asarray(tgt, float), (len(idx),)) if np.ndim(tgt) == 0 else np.asarray(tgt, float)
    for _ in range(3):
        if not len(idx):
            break
        d, g = field(v[idx])
        g = coherent(g, idx, A)
        need = d > -tgt + 0.05
        if not need.any():
            break
        i = idx[need]
        v[i] = v[i] + g[need] * (d[need] + tgt[need])[:, None]
        mv = v[i] - v0[i]; L = np.linalg.norm(mv, axis=1); over = L > cap
        if over.any():
            v[i[over]] = v0[i[over]] + mv[over] * (cap / L[over])[:, None]
    return v


def band_target(d, p):
    """outside distance each vertex ends at: depth max_depth -> surface + offset, the surface itself -> a little
    further, band mm outside -> unchanged (linear, decreasing in depth: order along the exit direction is kept, so a
    sheet lying in the bone with both faces compresses onto the surface instead of turning inside out)"""
    B = p["band"]; dc = np.clip(d, -B, p["max_depth"])
    return B - (dc + B) * (B - p["offset"]) / (p["max_depth"] + B)


def carve(v, f, field, mode: str, p: dict = P) -> tuple[np.ndarray, dict]:
    """carve one record out of bone. field(pts) -> (signed depth inside bone mm [>0 inside], unit exit direction)."""
    v0 = np.asarray(v, np.float64); v1 = v0.copy(); nv = len(v0)
    d, g = field(v0)
    ins = d > p["inside_tol"]
    audit = getattr(field, "audit", None)     # the external in-bone measure (Q185 sweep): what it counts must move too
    if audit is not None and nv:
        ins |= (audit(v0) > p["flag_mm"]) & (d > 0)
    info = {"mode": mode, "n_in_tol": int(ins.sum()), "depth_max_mm": round(float(d.max()), 2) if nv else 0.0}
    if not ins.any():
        info["moved"] = 0
        return v1, info
    A = adjacency(nv, f)
    if mode == "push":
        core = ins & (d <= p["max_depth"])
        sel = with_rim(A, core, (d > -p["band"]) & (d <= p["max_depth"]))
        info["n_rim"] = int((sel & ~core).sum())
        idx = np.flatnonzero(sel); tgt_all = band_target(d, p)
        info["n_too_deep"] = int((ins & (d > p["max_depth"])).sum())
        cap = p["max_depth"] + p["band"] + 0.5
        v1 = _push(v1, field, idx, tgt_all[idx], cap, v0, A)
    elif mode == "shell":
        from scipy.spatial import cKDTree
        idx = np.flatnonzero(ins)
        info["median_move_mm"] = round(float(np.median(d[idx] + p["offset"])), 2)
        if info["median_move_mm"] > p["shell_median_max"]:
            info["moved"] = 0; info["refused"] = "median move > %.1f mm" % p["shell_median_max"]
            return v1, info
        ureq = g[idx] * (d[idx] + p["offset"])[:, None]
        # carry the move across the shell's thickness (spatial Gaussian, sigma 1.5 mm, <= 4.5 mm): the outer face
        # follows the inner one instead of the cartilage being squashed flat
        # the whole local thickness moves as one: each vertex takes the LARGEST required move of the in-bone vertices
        # within 4 mm (Gaussian falloff, sigma 2 mm) along their mean exit direction -- the shell is lifted off the
        # bone instead of its two faces being squashed onto the surface
        sig = 2.0; T = cKDTree(v0[idx]); mag = d[idx] + p["offset"]; u = np.zeros_like(v0)
        for j, nb in enumerate(T.query_ball_point(v0, 2 * sig)):
            if nb:
                w = np.exp(-np.sum((v0[idx[nb]] - v0[j]) ** 2, 1) / (2 * sig * sig))
                gd = (w[:, None] * g[idx[nb]]).sum(0); gn = np.linalg.norm(gd)
                if gn > 1e-9:
                    u[j] = gd / gn * float((w * mag[nb]).max())
        u[idx] = np.where(np.linalg.norm(u[idx], axis=1)[:, None] >= mag[:, None], u[idx], g[idx] * mag[:, None])
        v1 = v0 + u
        v1 = _push(v1, field, idx, p["offset"], np.inf, v0)
    elif mode == "trim":
        # an insertion ends at the bone: slide each in-bone vertex along the structure's long axis (PCA), towards its
        # outside part, to the bone surface + offset -- a clean cut across the tendon (ring radius kept)
        sel = with_rim(A, ins, d > -p["offset"]); info["n_rim"] = int((sel & ~ins).sum())
        idx = np.flatnonzero(sel); out = np.flatnonzero(d <= -p["offset"])
        if not len(out):
            out = np.flatnonzero(d <= 0)
        if not len(out):
            info["moved"] = 0; info["refused"] = "no vertex outside bone"
            return v1, info
        c = v0.mean(0); ax = np.linalg.svd(v0 - c, full_matrices=False)[2][0]
        if np.dot(v0[out].mean(0) - v0[idx].mean(0), ax) < 0:
            ax = -ax
        span = float(np.ptp((v0 - c) @ ax)) + 1.0
        ts = np.arange(0.25, span + 0.25, 0.25)
        smp = (v0[idx][:, None, :] + ts[None, :, None] * ax).reshape(-1, 3)
        dm, _ = field(smp)
        ok_ = dm <= -p["offset"]
        if audit is not None:         # also outside by the external measure (its coarse-mesh side test can disagree)
            ok_ &= audit(smp) <= 0.0
        outside = ok_.reshape(len(idx), len(ts))
        reach = outside.any(1)
        info["n_no_exit"] = int((~reach).sum()); idx = idx[reach]
        k = outside[reach].argmax(1)                  # first sample along the axis that is outside
        hi = ts[k]; lo = np.where(k > 0, ts[np.maximum(k - 1, 0)], 0.0)
        for _ in range(8):            # refine between the last inside and the first outside sample
            mid = (lo + hi) / 2
            pm = v0[idx] + ax * mid[:, None]; dm, _ = field(pm)
            o = dm <= -p["offset"]
            if audit is not None:
                o &= audit(pm) <= 0.0
            hi = np.where(o, mid, hi); lo = np.where(o, lo, mid)
        v1[idx] = v0[idx] + ax * hi[:, None]
    else:
        raise ValueError(mode)
    moved = np.linalg.norm(v1 - v0, axis=1) > 1e-9
    if mode != "trim" and moved.any():
        mi = np.flatnonzero(moved)
        cap = np.inf if mode == "shell" else p["max_depth"] + p["band"] + 0.5
        tq = np.full(nv, p["offset"]) if mode == "shell" else band_target(d, p)
        for _ in range(p["smooth_rounds"]):   # project + smooth: relax the DISPLACEMENT of the moved vertices (shape
            u = relax(v1 - v0, A, mi, lam=0.5, iters=3)   # detail kept, folds ironed out), then back to their target
            v1 = v0 + u
            dd, _ = field(v1[mi]); back = mi[dd > -tq[mi] + 0.05]
            v1 = _push(v1, field, back, tq[back], cap, v0, A)
    moved = np.linalg.norm(v1 - v0, axis=1) > 1e-9
    v1, fg = fold_guard(v0, v1, f, moved, A)
    mv = np.linalg.norm(v1 - v0, axis=1)
    info.update(fg); info["moved"] = int((mv > 1e-9).sum()); info["max_move_mm"] = round(float(mv.max()), 2)
    return v1, info


# ---------------------------------------------------------------- the body's own bone
class BoneField:
    def __init__(self, body: str, bones: list):
        import trimesh
        from scipy.spatial import cKDTree
        self.body = body; self.O = np.array([float(x) for x in ORIGIN[body].split(",")])
        tot, self.A, self.sp = _nii(TASK / f"{body}_total.nii.gz"); self.shape = tot.shape
        self.mask = np.isin(tot, BONE); del tot
        self.depth = depth_map(self.mask, self.sp)          # the sweep's B.bone (same numbers)
        self.mesh = []
        for aid, v, f in bones:
            t = trimesh.Trimesh(v, f, process=False)
            sgn = 1.0 if float(np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum()) >= 0 else -1.0
            n = np.asarray(t.vertex_normals, np.float64) * sgn          # inward-wound mesh: flip so normals point out
            fn = np.asarray(t.face_normals, np.float64) * sgn
            self.mesh.append({"id": aid, "t": t, "v": v, "n": n, "fn": fn, "tree": cKDTree(v), "lo": v.min(0) - 2, "hi": v.max(0) + 2})

    # sweep-consistent depth (> 1 mm = the Q185 in-bone flag)
    def sweep_depth(self, pts):
        ts = np.nan_to_num(sample_depth(self.depth, self.A, self.O, pts, self.shape))
        md = np.zeros(len(pts))
        for b in self.mesh:
            sel = np.flatnonzero(np.all((pts >= b["lo"]) & (pts <= b["hi"]), 1))
            if not len(sel):
                continue
            dd, j = b["tree"].query(pts[sel])
            ins = np.einsum("ij,ij->i", pts[sel] - b["v"][j], b["n"][j]) < 0
            md[sel[ins]] = np.maximum(md[sel[ins]], dd[ins])
        return np.maximum(ts, md)

    def context(self, lo, hi, margin=8.0, n=15000):
        """bone surface points around [lo, hi] (TS label surface voxels + own bone mesh vertices) for the montage"""
        from scipy import ndimage as ndi
        from engine.volume_ingest import voxels_to_atlas
        c = np.array([[x, y, z] for x in (lo[0] - margin, hi[0] + margin) for y in (lo[1] - margin, hi[1] + margin)
                      for z in (lo[2] - margin, hi[2] + margin)])
        iv = to_vox(c, self.A, self.O)
        a = np.clip(np.floor(iv.min(0)).astype(int), 0, self.shape); b = np.clip(np.ceil(iv.max(0)).astype(int) + 1, 0, self.shape)
        pts = [np.zeros((0, 3))]
        if np.all(b - a > 2):
            m = self.mask[a[0]:b[0], a[1]:b[1], a[2]:b[2]]
            sv = np.argwhere(m & ~ndi.binary_erosion(m)) + a
            if len(sv):
                pts.append(voxels_to_atlas(sv.astype(float), self.A) - self.O)
        for x in self.mesh:
            pts.append(x["v"][np.all((x["v"] >= lo - margin) & (x["v"] <= hi + margin), 1)])
        P_ = np.concatenate(pts)
        if len(P_) > n:
            P_ = P_[np.random.default_rng(0).choice(len(P_), n, replace=False)]
        return P_.astype(np.float32)

    def local(self, lo, hi, margin=20.0):
        """signed-distance field (callable) valid around the atlas box [lo, hi]"""
        from scipy import ndimage as ndi
        c = np.array([[x, y, z] for x in (lo[0] - margin, hi[0] + margin) for y in (lo[1] - margin, hi[1] + margin)
                      for z in (lo[2] - margin, hi[2] + margin)])
        iv = to_vox(c, self.A, self.O)
        a = np.clip(np.floor(iv.min(0)).astype(int) - 1, 0, self.shape); b = np.clip(np.ceil(iv.max(0)).astype(int) + 2, 0, self.shape)
        sd = None
        if np.all(b - a > 1):
            m = self.mask[a[0]:b[0], a[1]:b[1], a[2]:b[2]]
            if m.any():
                sd = ndi.gaussian_filter(edt_inside(m, self.sp) - edt_inside(~m, self.sp), 1.0)   # smooth gradient (EDT is piecewise flat)
        bones = [x for x in self.mesh if np.all(x["hi"] + 5 >= lo - margin) and np.all(x["lo"] - 5 <= hi + margin)]
        shape = np.asarray(self.shape)

        def ts_sd(pts):
            out = np.full(len(pts), -np.inf)
            if sd is None:
                return out
            iv = to_vox(pts, self.A, self.O)
            ok = np.all((iv >= a) & (iv <= b - 1), 1) & np.all((iv >= -0.5) & (iv <= shape - 0.5), 1)
            if ok.any():
                out[ok] = ndi.map_coordinates(sd, (iv[ok] - a).T, order=1, mode="nearest")
            return out

        def field(pts):
            pts = np.asarray(pts, np.float64)
            d = ts_sd(pts); g = np.zeros_like(pts); fin = np.isfinite(d)
            if fin.any():
                h = 0.5; q = pts[fin]
                for k in range(3):
                    e = np.zeros(3); e[k] = h
                    g[fin, k] = -(ts_sd(q + e) - ts_sd(q - e)) / (2 * h)   # exit = down the inside depth
                g = np.nan_to_num(g, nan=0.0, posinf=0.0, neginf=0.0)
                n = np.linalg.norm(g[fin], axis=1); n[n < 1e-9] = 1
                g[fin] /= n[:, None]
            for bb in bones:
                sel = np.flatnonzero(np.all((pts >= bb["lo"] - 3) & (pts <= bb["hi"] + 3), 1))
                if not len(sel):
                    continue
                dd, j = bb["tree"].query(pts[sel])
                ins = np.einsum("ij,ij->i", pts[sel] - bb["v"][j], bb["n"][j]) < 0   # far: pseudo-normal side
                sdm = np.where(ins, dd, -dd); gm = np.where(ins[:, None], bb["v"][j] - pts[sel], pts[sel] - bb["v"][j])
                near = dd < 6.0               # near the surface: exact closest point, side by that face's normal
                if near.any():
                    q = pts[sel][near]
                    cp, dist, tri = __import__("trimesh").proximity.closest_point(bb["t"], q)
                    fn = bb["fn"][tri]; inside = np.einsum("ij,ij->i", q - cp, fn) < 0
                    sdm[near] = np.where(inside, dist, -dist)
                    gm[near] = np.where(inside[:, None], cp - q, q - cp)
                    z = dist < 1e-6; gm[np.flatnonzero(near)[z]] = fn[z]
                nn = np.linalg.norm(gm, axis=1); nn[nn < 1e-9] = 1; gm = gm / nn[:, None]
                take = sdm > d[sel]
                d[sel[take]] = sdm[take]; g[sel[take]] = gm[take]
            d[~np.isfinite(d)] = -1e3
            return d, g
        return field


# ---------------------------------------------------------------- subjects (exporter's claim order)
def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def restore(sub: str) -> None:
    """undo a previous run on this subject (vertices from the backup, badge suffix, hidden_default set here)"""
    d = VH / sub; st = d / STATE
    if not st.exists():
        return
    s = json.loads(st.read_text()); vf = d / "vertices.f32"
    if (d / BACKUP).exists() and _sha(vf) == s.get("carved_sha"):
        shutil.copyfile(d / BACKUP, vf)
    else:                         # rebuilt by its own script since: that is the new original
        (d / BACKUP).unlink(missing_ok=True)
    m = json.loads((d / "manifest.json").read_text())
    for r in m["structures"]:
        o = s["manifest_orig"].get(r["atlas_id"])
        if o is None:
            continue
        b = r.get("procedural_badge", "")
        if TAG in b:
            b = b[:b.index(TAG)].rstrip()
            if b and b != o.get("base_badge_from_entity"):
                r["procedural_badge"] = b
            else:
                r.pop("procedural_badge", None)
        if o.get("set_hidden"):
            r.pop("hidden_default", None)
    (d / "manifest.json").write_text(json.dumps(m, indent=2)); st.unlink()


def claimed(subjects: list, excludes: list) -> dict:
    """atlas id -> (subject, [manifest record]) exactly as export_viewer_bundle.py picks them"""
    excl = [e.split(":", 1) for e in excludes]
    out, prior = {}, set()
    for sub in subjects:
        mf = VH / sub / "manifest.json"
        if not mf.exists():
            continue
        here = set()
        for s in json.loads(mf.read_text())["structures"]:
            aid = s["atlas_id"]
            if aid in prior or any(sub == a and fnmatch.fnmatchcase(aid, g) for a, g in excl):
                continue
            here.add(aid); out.setdefault(aid, (sub, []))[1].append(s)
        prior |= here
    return out


def record(sub: str, s: dict):
    d = VH / sub
    V = np.memmap(d / "vertices.f32", np.float32, "r").reshape(-1, 3); F = np.memmap(d / "faces.u32", np.uint32, "r").reshape(-1, 3)
    v = np.array(V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]], np.float64)
    f = np.array(F[s["face_offset"]:s["face_offset"] + s["triangle_count"]]).astype(np.int64) - s["vertex_offset"]
    return v, f


def frac_in(B: BoneField, v: np.ndarray) -> float:
    rng = np.random.default_rng(185)
    p = v if len(v) <= MAX_PTS else v[rng.choice(len(v), MAX_PTS, replace=False)]
    return float((B.sweep_depth(p) > P["flag_mm"]).mean())


def run(body: str, subjects: list, excludes: list, report: Path, dry: bool = False, only: str | None = None) -> int:
    import gc
    from scripts.zanatomy.map_names import load_full_atlas
    from scripts.export_viewer_bundle import load_atlas_records
    if not dry:
        for sub in subjects:
            restore(sub)
    cat = {e.entity_id: e.category for e in load_full_atlas()}
    atlas = load_atlas_records()
    cl = claimed(subjects, excludes)
    her = {"vhm": "his", "vhf": "her"}[body]
    bones = []
    for aid, (sub, recs) in cl.items():
        c = cat.get(aid) or recs[0].get("category")
        if c != "bone" or sub.startswith(("xfer_", "ct_s1159")) or (aid in TS_BONE_IDS and aid not in MESH_BONE_EXTRA):
            continue
        vs, fs, n = [], [], 0
        for s in recs:
            v, f = record(sub, s); vs.append(v); fs.append(f + n); n += len(v)
        bones.append((aid, np.concatenate(vs), np.concatenate(fs)))
    B = BoneField(body, bones); del bones; gc.collect()
    print(f"{body}: bone = TS total labels + {len(B.mesh)} own bone meshes", flush=True)
    rows, skipped = {}, {}
    writes: dict = {}
    for aid, (sub, recs) in cl.items():
        c = cat.get(aid) or recs[0].get("category")
        if c not in MODE or (only and not re.search(only, aid)):
            continue
        why = ("Q185 exclusion (bone canal)" if aid in BONE_EXCLUDE_IDS else
               "label-overlap false positive / Q185c disc" if EXCLUDE_ID_RE.search(aid) else
               "Q185b subject (own queue item)" if EXCLUDE_SUBJECT_RE.search(sub) else
               "hidden_default" if any(s.get("hidden_default") for s in recs) else None)
        geo = [record(sub, s) for s in recs]
        v_all = np.concatenate([g[0] for g in geo])
        a0 = frac_in(B, v_all)
        if a0 <= P["flag_frac"]:
            continue
        if why:
            skipped[aid] = {"subject": sub, "reason": why, "in_bone_frac": round(a0, 4)}; continue
        mode = MODE[c]; new, infos = [], []
        for v, f in geo:
            fld = B.local(v.min(0), v.max(0)); fld.audit = B.sweep_depth
            v1, info = carve(v, f, fld, mode); new.append(v1); infos.append(info)
        v1_all = np.concatenate(new); b1 = frac_in(B, v1_all)
        if b1 > P["gate_frac"] and mode != "shell" and not any(i.get("refused") for i in infos):
            # second pass from the first result: the fold guard backs off vertices whose neighbours had not moved yet;
            # still the same rule (only vertices <= max_depth inside move)
            new2, inf2 = [], []
            for (v, f), x in zip(geo, new):
                fld = B.local(v.min(0), v.max(0)); fld.audit = B.sweep_depth
                x2, i2 = carve(x, f, fld, mode); new2.append(x2); inf2.append(i2)
            v2_all = np.concatenate(new2); b2 = frac_in(B, v2_all)
            if b2 < b1:
                new, v1_all, b1 = new2, v2_all, b2
                for i, j in zip(infos, inf2):
                    i["pass2"] = {k: j[k] for k in ("moved", "backed_off", "reverted", "flipped_faces_left") if k in j}
                    i["flipped_faces_left"] = j.get("flipped_faces_left", 0)
        vol0 = sum(volume(v, f) for v, f in geo); vol1 = sum(volume(x, g[1]) for x, g in zip(new, geo))
        dvol = (vol1 - vol0) / vol0 if vol0 > 0 else 0.0
        mv = np.linalg.norm(v1_all - v_all, axis=1); n_moved = int((mv > 1e-6).sum())
        refused = [i.get("refused") for i in infos if i.get("refused")]
        ok = (not refused and n_moved > 0 and b1 <= P["gate_frac"]
              and (mode == "trim" or abs(dvol) <= P["gate_vol"])
              and all(i.get("flipped_faces_left", 0) == 0 for i in infos))
        row = {"subject": sub, "cat": c, "mode": mode, "nv": int(len(v_all)), "in_bone_before": round(a0, 4),
               "in_bone_after": round(b1, 4), "volume_change": round(dvol, 4), "moved": n_moved,
               "max_move_mm": round(float(mv.max()), 2), "records": infos, "shipped": bool(ok)}
        pct = lambda x: f"{100 * x:.1f} %"   # noqa: E731
        if ok:
            badge = (f"{TAG}: {n_moved} vertices moved out of {her} own bone (max {mv.max():.1f} mm); "
                     f"in-bone {pct(a0)} -> {pct(b1)}" + (" (trimmed at the bone surface)." if mode == "trim" else "."))
            row["hidden_default"] = False
        else:
            reason = refused[0] if refused else (f"{pct(b1)} still > 1 mm inside" if b1 > P["gate_frac"] else
                                                 f"volume {100 * dvol:+.0f} %" if abs(dvol) > P["gate_vol"] else "fold guard")
            hide = a0 > P["hide_frac"]
            badge = (f"{TAG} HELD: {pct(a0)} of this mesh lies > 1 mm inside {her} own bone; the bounded carve "
                     f"(<= {P['max_depth']:.0f} mm push / cartilage <= {P['shell_median_max']:.0f} mm median) did not fix it "
                     f"({reason}), so the unmodified mesh is shown" + (" -- hidden by default." if hide else "."))
            row["hidden_default"] = hide; row["held_reason"] = reason
        row["badge"] = badge; rows[aid] = row
        SCRATCH.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(SCRATCH / f"carve_{body}_{aid}.npz", v0=v_all.astype(np.float32), v1=v1_all.astype(np.float32),
                            f=np.concatenate([g[1] + o for g, o in zip(geo, np.cumsum([0] + [len(g[0]) for g in geo]))]).astype(np.int32),
                            d0=B.sweep_depth(v_all).astype(np.float32), d1=B.sweep_depth(v1_all).astype(np.float32),
                            bone=B.context(v_all.min(0), v_all.max(0)))
        w = writes.setdefault(sub, {})
        w[aid] = (row, [(s, x) for s, x in zip(recs, new)] if ok else [(s, None) for s in recs])
        print(f"  {aid} [{sub}] {mode}: in-bone {pct(a0)} -> {pct(b1)}, moved {n_moved}, max {mv.max():.1f} mm, "
              f"vol {100 * dvol:+.1f} % -> {'SHIP' if ok else 'HELD' + (' hidden' if row['hidden_default'] else '')}"
              f" | {[{k: i[k] for k in ('backed_off', 'reverted', 'n_too_deep', 'n_no_exit', 'median_move_mm', 'refused') if k in i} for i in infos]}", flush=True)
        del geo, new, v_all, v1_all; gc.collect()
    for sub, items in ({} if dry else writes).items():
        d = VH / sub; vf = d / "vertices.f32"
        m = json.loads((d / "manifest.json").read_text()); orig = {}
        need_v = any(x is not None for _, (_, lst) in items.items() for _, x in lst)
        if need_v:
            if not (d / BACKUP).exists():
                shutil.copyfile(vf, d / BACKUP)
            V = np.fromfile(vf, np.float32).reshape(-1, 3)
        byoff = {(r["vertex_offset"], r["atlas_id"]): r for r in m["structures"]}
        for aid, (row, lst) in items.items():
            for s, x in lst:
                r = byoff[(s["vertex_offset"], aid)]
                if x is not None:
                    V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]] = x.astype(np.float32)
                ent = (atlas.get(aid, (None, None))[1] or {})
                ent_badge = (ent.get("procedural_geometry") or {}).get("badge")
                base = r.get("procedural_badge") or ent_badge or ""
                orig.setdefault(aid, {"base_badge_from_entity": ent_badge if not r.get("procedural_badge") else None,
                                      "set_hidden": bool(row["hidden_default"] and not r.get("hidden_default"))})
                r["procedural_badge"] = (base + " " if base else "") + row["badge"]
                if row["hidden_default"]:
                    r["hidden_default"] = True
        if need_v:
            V.tofile(vf)
        (d / "manifest.json").write_text(json.dumps(m, indent=2))
        (d / STATE).write_text(json.dumps({"carved_sha": _sha(vf), "manifest_orig": orig}, indent=1))
    rep = {"_README": __doc__.strip().splitlines(), "params": P, "body": body, "subjects": subjects, "excludes": excludes,
           "structures": rows, "skipped_flagged": skipped,
           "summary": {"candidates": len(rows), "shipped": sum(r["shipped"] for r in rows.values()),
                       "held": sum(not r["shipped"] for r in rows.values()),
                       "hidden": sum(bool(r["hidden_default"]) for r in rows.values())}}
    if not dry:
        report.write_text(json.dumps(rep, indent=1))
    print(f"{body}: Q185 bone carve {rep['summary']} (skipped {len(skipped)}) -> {report.relative_to(REPO)}")
    return 0


def montage(out: Path, n: int = 6) -> Path:
    """the n structures most inside bone before the carve (both bodies): before | after, two views each"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    for body in ("vhm", "vhf"):
        rp = REPO / "data" / "derived" / f"Q185_bone_carve_{body}.json"
        if rp.exists():
            for aid, r in json.loads(rp.read_text())["structures"].items():
                rows.append((r["in_bone_before"], body, aid, r))
    rows = sorted(rows, key=lambda x: -x[0])[:n]
    fig, ax = plt.subplots(len(rows), 4, figsize=(16, 3.6 * len(rows)))
    ax = np.atleast_2d(ax)
    for i, (_, body, aid, r) in enumerate(rows):
        z = np.load(SCRATCH / f"carve_{body}_{aid}.npz")
        c = z["v0"].mean(0); bone = z["bone"]
        for j, (key, dk, tag) in enumerate((("v0", "d0", "before"), ("v1", "d1", "after" if r["shipped"] else "attempt (HELD: original ships)"))):
            V = z[key]; D = z[dk]
            for k, (u, w, vn) in enumerate(((0, 1, "x-y"), (2, 1, "z-y"))):
                a = ax[i, 2 * j + k]
                a.scatter(bone[:, u] - c[u], bone[:, w] - c[w], s=0.3, c="#bbbbbb", lw=0)
                ok = D <= 1.0
                a.scatter(V[ok, u] - c[u], V[ok, w] - c[w], s=1.5, c="#2ca02c", lw=0)
                a.scatter(V[~ok, u] - c[u], V[~ok, w] - c[w], s=2.5, c="#ff7f0e", lw=0)
                lim = np.abs(z["v0"] - c).max() * 1.15 + 3
                a.set_xlim(-lim, lim); a.set_ylim(-lim, lim); a.set_aspect("equal"); a.tick_params(labelsize=6)
                pct = r["in_bone_before"] if key == "v0" else r["in_bone_after"]
                a.set_title(f"{'his' if body == 'vhm' else 'her'} {aid} -- {tag} ({vn})\n> 1 mm in bone {100 * pct:.1f} %",
                            fontsize=7)
    fig.suptitle("Q185 bone carve: orange = vertex > 1 mm inside own bone, green = ok, grey = bone surface", fontsize=10)
    fig.tight_layout(); out.mkdir(parents=True, exist_ok=True); f = out / "montage_worst6_before_after.png"
    fig.savefig(f, dpi=110); plt.close(fig)
    print(f"montage {f} ({len(rows)} structures)")
    return f


def main(argv=None) -> int:
    if argv is None and sys.argv[1:2] == ["montage"]:
        montage(SCRATCH); return 0
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", choices=["vhm", "vhf"], required=True)
    ap.add_argument("--subject", action="append", default=[])
    ap.add_argument("--exclude", action="append", default=[], metavar="SUBJECT:GLOB")
    ap.add_argument("--report", default=None)
    ap.add_argument("--dry-run", action="store_true", help="measure + carve, write nothing (development)")
    ap.add_argument("--only", default=None, help="only ids matching this regex (development; implies --dry-run)")
    ap.add_argument("--restore-only", action="store_true", help="undo every previous carve on these subjects and stop")
    a = ap.parse_args(argv)
    if a.restore_only:
        for s in a.subject:
            restore(s)
        return 0
    rep = Path(a.report) if a.report else REPO / "data" / "derived" / f"Q185_bone_carve_{a.body}.json"
    return run(a.body, a.subject, a.exclude, rep, dry=a.dry_run or bool(a.only), only=a.only)


if __name__ == "__main__":
    sys.exit(main())
