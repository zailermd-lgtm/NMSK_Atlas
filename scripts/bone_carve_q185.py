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

Q185 b/f: the same bounded move, two more references (stages run in this order on one record: bone -> organ -> skin):
  organ push   (Q185f) abdominal-wall muscles (ORGAN_PUSH_RE) with > 5 % of vertices > 1 mm inside that body's own TS
               organ labels (the sweep's ORGANS): pushed out exactly like the bone push (<= 4 mm, surface + 0.5 mm).
  skin pull-in (Q185b) every soft record with > 1 % of its vertices outside that body's own skin mesh (ct_v?_skin, the
               sweep's embree-parity reference): vertices <= 4 mm outside move along the SDF gradient (towards the
               closest skin point) to skin surface - 1 mm; further out stay. His skin is cut flat at the torso-CT
               field-of-view edge (Q185a, x = -233 / +247 mm): outside vertices within 4 mm of / beyond such a cut are
               NOT pulled (the skin there is wrong, not the muscle) and are counted in the badge + report.
  Same fold guard / relax / second pass and hold rules: ship only if <= 5 % still outside (beyond-FOV vertices not
  counted) / in organ, |volume| <= 25 %, and (skin) no new in-bone flag; else the stage's input is kept, hidden_default
  only if > 20 % outside skin / in organ. Bone exclusion of the Q185b subjects is lifted (their bone carve is part of
  Q185b; fascia pushes like muscle). Report sections "organ_push" / "skin_pull".
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
MODE = {"muscle": "push", "vessel": "push", "nerve": "push", "fascia": "push", "tendon": "trim", "ligament": "trim",
        "cartilage": "shell"}
P = {"offset": 0.5, "inside_tol": 0.5, "max_depth": 4.0, "shell_median_max": 3.0, "flag_mm": 1.0, "flag_frac": 0.05,
     "gate_frac": 0.05, "band": 0.5, "smooth_rounds": 0, "gate_vol": 0.25, "hide_frac": 0.20}
# not handled here (stated in the report): label-overlap false positives (Q185 "ref"), Q185b limb transfers (skin +
# bone refit, own queue item), Q185c discs (rebuilt from the endplates)
EXCLUDE_ID_RE = re.compile(r"^(lateral_pterygoid|temporalis)_[lr]$|^intervertebral_disc_")
# Q185b/f: skin pull-in (surface - 1 mm, <= 4 mm outside) and organ push (abdominal wall only; others stay in their queue)
P_SKIN = dict(P, offset=1.0, inside_tol=0.0, band=1.5)
P_ORGAN = dict(P)
ORGAN_PUSH_RE = re.compile(r"^(transversus_abdominis|rectus_abdominis|internal_oblique|external_oblique)_[lr]$")
SKIN_FLAG = 0.01
SKIN_CUT_MIN_VERTS = 1000          # a flat x = const cap of the skin mesh (his torso-CT field-of-view edge)
TAG = "Q185 bone carve"
TAG_ORGAN = "Q185 organ push"
TAG_SKIN = "Q185 skin pull-in"
TAGS = (TAG, TAG_ORGAN, TAG_SKIN)
SCRATCH_BFG = SCRATCH.parent / "q185bfg"
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
    def __init__(self, body: str, bones: list, labels=BONE):
        import trimesh
        from scipy.spatial import cKDTree
        self.body = body; self.O = np.array([float(x) for x in ORIGIN[body].split(",")])
        tot, self.A, self.sp = _nii(TASK / f"{body}_total.nii.gz"); self.shape = tot.shape
        self.mask = np.isin(tot, labels); del tot          # BONE, or the sweep's ORGANS for the organ push
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


# ---------------------------------------------------------------- the body's own skin (Q185b)
class SkinField:
    """that body's own skin mesh (ct_v?_skin -- the Q185 sweep's outside-skin reference, embree ray parity).
    field: signed distance OUTSIDE the skin (> 0 outside), exit direction = towards the closest skin point. Flat x = const
    caps of the mesh (his torso-CT field-of-view edge, Q185a) are detected; outside vertices within max_depth of / beyond
    such a cut are `beyond` -- never pulled (the skin is wrong there, not the structure)"""
    def __init__(self, body: str):
        from scripts.ribs_from_ct_labels import load_skin
        self.skin = load_skin(body)
        v = np.asarray(self.skin.vertices, np.float64); f = np.asarray(self.skin.faces, np.int64)
        sgn = 1.0 if float(np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum()) >= 0 else -1.0
        fn = face_normals(v, f) * sgn; self.fn = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-12)[:, None]
        self.v, self.f, self.fc = v, f, v[f].mean(1)
        lo, hi = float(v[:, 0].min()), float(v[:, 0].max())
        self.cut_lo = lo if (np.abs(v[:, 0] - lo) < 0.5).sum() > SKIN_CUT_MIN_VERTS else None
        self.cut_hi = hi if (np.abs(v[:, 0] - hi) < 0.5).sum() > SKIN_CUT_MIN_VERTS else None

    def outside(self, pts) -> np.ndarray:
        return ~self.skin.contains(np.asarray(pts, np.float64))

    def beyond(self, pts, tol: float = P_SKIN["max_depth"]) -> np.ndarray:
        x = np.asarray(pts)[:, 0]; b = np.zeros(len(x), bool)
        if self.cut_lo is not None:
            b |= x <= self.cut_lo + tol
        if self.cut_hi is not None:
            b |= x >= self.cut_hi - tol
        return b

    def frac(self, v):
        """(outside, outside and pullable [not beyond a FOV cut], outside beyond a cut) fractions -- sweep subsample"""
        rng = np.random.default_rng(185)
        p = v if len(v) <= MAX_PTS else v[rng.choice(len(v), MAX_PTS, replace=False)]
        out = self.outside(p); bey = self.beyond(p)
        return float(out.mean()), float((out & ~bey).mean()), float((out & bey).mean())

    def context(self, lo, hi, margin=8.0, n=15000):
        sel = np.all((self.v >= lo - margin) & (self.v <= hi + margin), 1); P_ = self.v[sel]
        if len(P_) > n:
            P_ = P_[np.random.default_rng(0).choice(len(P_), n, replace=False)]
        return P_.astype(np.float32)

    def local(self, lo, hi, margin=20.0):
        import trimesh
        sel = np.all((self.fc >= lo - margin) & (self.fc <= hi + margin), 1)
        if not sel.any():
            def none(pts):
                return np.full(len(pts), -1e3), np.zeros((len(pts), 3))
            return none
        fi = np.flatnonzero(sel); u, inv = np.unique(self.f[fi], return_inverse=True)
        sub = trimesh.Trimesh(self.v[u], inv.reshape(-1, 3), process=False)

        def field(pts):
            pts = np.asarray(pts, np.float64)
            out = self.outside(pts)
            cp, dist, tri = trimesh.proximity.closest_point(sub, pts)
            d = np.where(out, dist, -dist)
            g = np.where(out[:, None], cp - pts, pts - cp)
            z = dist < 1e-6; g[z] = -self.fn[fi[tri[z]]]
            n = np.linalg.norm(g, axis=1); n[n < 1e-9] = 1; g = g / n[:, None]
            d[self.beyond(pts) & (d > -P_SKIN["band"])] = -1e3   # FOV cut: not pulled, not rim
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
        at = [b.index(t) for t in TAGS if t in b]
        if at:
            b = b[:min(at)].rstrip()
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


def stage(geo, cur, fld_of, frac, mode, p, extra_ok=None):
    """one bounded move (bone carve / organ push / skin pull-in) of one structure's records, starting from `cur` (the
    previous stage's output); fld_of(k) -> field for record k; frac(v_all) -> the gated fraction. Second pass from the
    first result when the gate fails. Returns (new vertex arrays, stats)"""
    v_in = np.concatenate(cur); a0 = frac(v_in)
    new, infos = [], []
    for k, ((_, f), v) in enumerate(zip(geo, cur)):
        x, info = carve(v, f, fld_of(k), mode, p); new.append(x); infos.append(info)
    v1_all = np.concatenate(new); b1 = frac(v1_all)
    if b1 > p["gate_frac"] and mode != "shell" and not any(i.get("refused") for i in infos):
        # second pass from the first result: the fold guard backs off vertices whose neighbours had not moved yet;
        # still the same rule (only vertices <= max_depth inside move)
        new2, inf2 = [], []
        for k, ((_, f), x) in enumerate(zip(geo, new)):
            x2, i2 = carve(x, f, fld_of(k), mode, p); new2.append(x2); inf2.append(i2)
        v2_all = np.concatenate(new2); b2 = frac(v2_all)
        if b2 < b1:
            new, v1_all, b1 = new2, v2_all, b2
            for i, j in zip(infos, inf2):
                i["pass2"] = {k: j[k] for k in ("moved", "backed_off", "reverted", "flipped_faces_left") if k in j}
                i["flipped_faces_left"] = j.get("flipped_faces_left", 0)
    vol0 = sum(volume(v, g[1]) for v, g in zip(cur, geo)); vol1 = sum(volume(x, g[1]) for x, g in zip(new, geo))
    dvol = (vol1 - vol0) / vol0 if vol0 > 0 else 0.0
    mv = np.linalg.norm(v1_all - v_in, axis=1); n_moved = int((mv > 1e-6).sum())
    refused = [i.get("refused") for i in infos if i.get("refused")]
    extra = extra_ok(v1_all) if extra_ok else None
    ok = (not refused and n_moved > 0 and b1 <= p["gate_frac"]
          and (mode == "trim" or abs(dvol) <= p["gate_vol"])
          and all(i.get("flipped_faces_left", 0) == 0 for i in infos) and not extra)
    reason = (refused[0] if refused else f"{100 * b1:.1f} % still flagged" if b1 > p["gate_frac"] else
              f"volume {100 * dvol:+.0f} %" if abs(dvol) > p["gate_vol"] else extra if extra else "fold guard")
    return new, {"before": a0, "after": b1, "dvol": dvol, "moved": n_moved, "max_move": float(mv.max()) if len(mv) else 0.0,
                 "infos": infos, "ok": bool(ok), "reason": None if ok else reason, "v_in": v_in, "v_out": v1_all}


def _save(kind, body, aid, geo, st, m0, m1, ctx):
    SCRATCH_BFG.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(SCRATCH_BFG / f"{kind}_{body}_{aid}.npz", v0=st["v_in"].astype(np.float32),
                        v1=st["v_out"].astype(np.float32), m0=m0, m1=m1, ctx=ctx,
                        f=np.concatenate([g[1] + o for g, o in zip(geo, np.cumsum([0] + [len(g[0]) for g in geo]))]).astype(np.int32))


def run(body: str, subjects: list, excludes: list, report: Path, dry: bool = False, only: str | None = None) -> int:
    import gc
    from scripts.zanatomy.map_names import load_full_atlas
    from scripts.export_viewer_bundle import load_atlas_records
    from scripts.placement_sweep_q185 import ORGANS, label_at
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
    K = SkinField(body)
    print(f"{body}: bone = TS total labels + {len(B.mesh)} own bone meshes; skin FOV cuts x = {K.cut_lo} / {K.cut_hi}", flush=True)
    OF = tot = None
    rows, skipped, rows_o, rows_s = {}, {}, {}, {}
    writes: dict = {}
    pct = lambda x: f"{100 * x:.1f} %"   # noqa: E731
    for aid, (sub, recs) in cl.items():
        c = cat.get(aid) or recs[0].get("category")
        if c == "bone" or aid == "skin" or (only and not re.search(only, aid)):
            continue
        hidden = any(s.get("hidden_default") for s in recs)
        geo = [record(sub, s) for s in recs]
        v_all = np.concatenate([g[0] for g in geo])
        cur = [g[0] for g in geo]; badges = []; hide = False; shipped_any = False
        # ---- stage 1: bone (Q185 d/e/h/i/j; + the Q185b subjects)
        a0 = frac_in(B, v_all) if c in MODE else 0.0
        if a0 > P["flag_frac"]:
            why = ("Q185 exclusion (bone canal)" if aid in BONE_EXCLUDE_IDS else
                   "label-overlap false positive / Q185c disc" if EXCLUDE_ID_RE.search(aid) else
                   "hidden_default" if hidden else None)
            if why:
                skipped[aid] = {"subject": sub, "reason": why, "in_bone_frac": round(a0, 4)}
            else:
                mode = MODE[c]

                def fld_b(k, geo=geo):
                    fl = B.local(geo[k][0].min(0), geo[k][0].max(0)); fl.audit = B.sweep_depth
                    return fl
                new, st = stage(geo, cur, fld_b, lambda x: frac_in(B, x), mode, P)
                b1, dvol, n_moved, mx, ok = st["after"], st["dvol"], st["moved"], st["max_move"], st["ok"]
                row = {"subject": sub, "cat": c, "mode": mode, "nv": int(len(v_all)), "in_bone_before": round(a0, 4),
                       "in_bone_after": round(b1, 4), "volume_change": round(dvol, 4), "moved": n_moved,
                       "max_move_mm": round(mx, 2), "records": st["infos"], "shipped": bool(ok)}
                if ok:
                    badge = (f"{TAG}: {n_moved} vertices moved out of {her} own bone (max {mx:.1f} mm); "
                             f"in-bone {pct(a0)} -> {pct(b1)}" + (" (trimmed at the bone surface)." if mode == "trim" else "."))
                    row["hidden_default"] = False
                else:
                    reason = st["reason"].replace("% still flagged", "% still > 1 mm inside")
                    h = a0 > P["hide_frac"]
                    badge = (f"{TAG} HELD: {pct(a0)} of this mesh lies > 1 mm inside {her} own bone; the bounded carve "
                             f"(<= {P['max_depth']:.0f} mm push / cartilage <= {P['shell_median_max']:.0f} mm median) did not fix it "
                             f"({reason}), so the unmodified mesh is shown" + (" -- hidden by default." if h else "."))
                    row["hidden_default"] = h; row["held_reason"] = reason; hide |= h
                row["badge"] = badge; rows[aid] = row; badges.append(badge)
                SCRATCH.mkdir(parents=True, exist_ok=True)
                np.savez_compressed(SCRATCH / f"carve_{body}_{aid}.npz", v0=v_all.astype(np.float32), v1=st["v_out"].astype(np.float32),
                                    f=np.concatenate([g[1] + o for g, o in zip(geo, np.cumsum([0] + [len(g[0]) for g in geo]))]).astype(np.int32),
                                    d0=B.sweep_depth(v_all).astype(np.float32), d1=B.sweep_depth(st["v_out"]).astype(np.float32),
                                    bone=B.context(v_all.min(0), v_all.max(0)))
                print(f"  {aid} [{sub}] {mode}: in-bone {pct(a0)} -> {pct(b1)}, moved {n_moved}, max {mx:.1f} mm, "
                      f"vol {100 * dvol:+.1f} % -> {'SHIP' if ok else 'HELD' + (' hidden' if row['hidden_default'] else '')}"
                      f" | {[{k: i[k] for k in ('backed_off', 'reverted', 'n_too_deep', 'n_no_exit', 'median_move_mm', 'refused') if k in i} for i in st['infos']]}", flush=True)
                if ok:
                    cur = new; shipped_any = True
        # ---- stage 2: organ push (Q185f; abdominal wall only)
        if c == "muscle" and ORGAN_PUSH_RE.search(aid) and not hidden:
            if OF is None:
                OF = BoneField(body, [], labels=list(ORGANS)); tot = _nii(TASK / f"{body}_total.nii.gz")[0]
            v_cur = np.concatenate(cur); o0 = frac_in(OF, v_cur)
            if o0 > P["flag_frac"]:
                def fld_o(k, geo=geo):
                    fl = OF.local(geo[k][0].min(0), geo[k][0].max(0)); fl.audit = OF.sweep_depth
                    return fl
                new, st = stage(geo, cur, fld_o, lambda x: frac_in(OF, x), "push", P_ORGAN,
                                extra_ok=lambda x: (f"in-bone {pct(frac_in(B, x))}" if frac_in(B, x) > max(P["gate_frac"], frac_in(B, v_cur)) else None))
                dep = OF.sweep_depth(v_cur) > P["flag_mm"]
                labs = label_at(tot, OF.A, OF.O, v_cur[dep]); u, cnt = np.unique(labs[labs > 0], return_counts=True)
                organs = "/".join(ORGANS[int(x)] for x, _ in sorted(zip(u, cnt), key=lambda t: -t[1])[:3] if int(x) in ORGANS) or "organ"
                ok = st["ok"]; h = (not ok) and o0 > P["hide_frac"]
                if ok:
                    badge = (f"{TAG_ORGAN}: {st['moved']} vertices moved out of {her} own {organs} label (max {st['max_move']:.1f} mm); "
                             f"in-organ {pct(o0)} -> {pct(st['after'])}.")
                    cur = new; shipped_any = True
                else:
                    badge = (f"{TAG_ORGAN} HELD: {pct(o0)} of this mesh lies > 1 mm inside {her} own {organs} label; the bounded "
                             f"push (<= {P_ORGAN['max_depth']:.0f} mm) did not fix it ({st['reason'].replace('% still flagged', '% still > 1 mm inside')}), "
                             f"so the mesh is shown without it" + (" -- hidden by default." if h else "."))
                hide |= h; badges.append(badge)
                rows_o[aid] = {"subject": sub, "organs": organs, "in_organ_before": round(o0, 4), "in_organ_after": round(st["after"], 4),
                               "volume_change": round(st["dvol"], 4), "moved": st["moved"], "max_move_mm": round(st["max_move"], 2),
                               "shipped": ok, "hidden_default": h, "held_reason": st["reason"], "badge": badge,
                               "records": [{k: i[k] for k in ("moved", "n_too_deep", "backed_off", "reverted", "flipped_faces_left") if k in i} for i in st["infos"]]}
                _save("organ", body, aid, geo, st, OF.sweep_depth(st["v_in"]) > 1, OF.sweep_depth(st["v_out"]) > 1,
                      OF.context(v_cur.min(0), v_cur.max(0)))
                print(f"  {aid} [{sub}] organ push ({organs}): {pct(o0)} -> {pct(st['after'])}, moved {st['moved']}, "
                      f"vol {100 * st['dvol']:+.1f} % -> {'SHIP' if ok else 'HELD' + (' hidden' if h else '')} {st['reason'] or ''}", flush=True)
        # ---- stage 3: skin pull-in (Q185b; every soft record)
        v_cur = np.concatenate(cur); s_all, s_mov, s_bey = K.frac(v_cur)
        if s_all > SKIN_FLAG:
            if hidden or s_mov <= SKIN_FLAG:
                rows_s[aid] = {"subject": sub, "outside_before": round(s_all, 4), "outside_pullable": round(s_mov, 4),
                               "outside_beyond_fov_cut": round(s_bey, 4),
                               "skipped": "hidden_default" if hidden else "outside part lies at / beyond the skin's CT field-of-view cut (Q185a)"}
            else:
                n_bey = int((K.outside(v_cur) & K.beyond(v_cur)).sum())

                def fld_s(k, geo=geo):
                    return K.local(geo[k][0].min(0), geo[k][0].max(0))
                bone_in = frac_in(B, v_cur)
                new, st = stage(geo, cur, fld_s, lambda x: K.frac(x)[1], "push", P_SKIN,
                                extra_ok=lambda x: (f"in-bone {pct(frac_in(B, x))}" if frac_in(B, x) > max(P["gate_frac"], bone_in) else None))
                ok = st["ok"]; h = (not ok) and s_mov > P_SKIN["hide_frac"]
                s1_all, s1_mov, _ = K.frac(st["v_out"])
                fov = (f"; {n_bey} vertices at / beyond {her} skin's CT field-of-view cut left as they are" if n_bey else "")
                if ok:
                    badge = (f"{TAG_SKIN}: {st['moved']} vertices pulled inside {her} own skin (to 1 mm below it, max "
                             f"{st['max_move']:.1f} mm); outside skin {pct(s_all)} -> {pct(s1_all)}{fov}.")
                    cur = new; shipped_any = True
                else:
                    badge = (f"{TAG_SKIN} HELD: {pct(s_all)} of this mesh lies outside {her} own skin; the bounded pull-in "
                             f"(<= {P_SKIN['max_depth']:.0f} mm) did not fix it ({st['reason'].replace('% still flagged', '% still outside')}), "
                             f"so the mesh is shown without it{fov}" + (" -- hidden by default." if h else "."))
                hide |= h; badges.append(badge)
                rows_s[aid] = {"subject": sub, "cat": c, "outside_before": round(s_all, 4), "outside_pullable": round(s_mov, 4),
                               "outside_beyond_fov_cut": round(s_bey, 4), "n_beyond_fov_cut": n_bey,
                               "outside_after": round(s1_all, 4), "outside_pullable_after": round(s1_mov, 4),
                               "in_bone_before": round(bone_in, 4), "in_bone_after": round(frac_in(B, st["v_out"]), 4),
                               "volume_change": round(st["dvol"], 4), "moved": st["moved"], "max_move_mm": round(st["max_move"], 2),
                               "shipped": ok, "hidden_default": h, "held_reason": st["reason"], "badge": badge,
                               "records": [{k: i[k] for k in ("moved", "n_too_deep", "backed_off", "reverted", "flipped_faces_left") if k in i} for i in st["infos"]]}
                _save("skin", body, aid, geo, st, K.outside(st["v_in"]), K.outside(st["v_out"]),
                      K.context(v_cur.min(0), v_cur.max(0)))
                print(f"  {aid} [{sub}] skin pull-in: {pct(s_all)} (pullable {pct(s_mov)}, beyond FOV cut {n_bey} v) -> "
                      f"{pct(s1_all)}, moved {st['moved']}, max {st['max_move']:.1f} mm, vol {100 * st['dvol']:+.1f} % -> "
                      f"{'SHIP' if ok else 'HELD' + (' hidden' if h else '')} {st['reason'] or ''}", flush=True)
        if badges:
            writes.setdefault(sub, {})[aid] = ({"badge": " ".join(badges), "hidden_default": hide},
                                               [(s, x if shipped_any else None) for s, x in zip(recs, cur)])
        del geo, cur, v_all; gc.collect()
    if body == "vhm":
        orbit_reseat(cl, B, K, writes, her)
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
    summ = lambda rr: {"candidates": len(rr), "shipped": sum(bool(r.get("shipped")) for r in rr.values()),   # noqa: E731
                       "held": sum(r.get("shipped") is False for r in rr.values()),
                       "hidden": sum(bool(r.get("hidden_default")) for r in rr.values())}
    rep = {"_README": __doc__.strip().splitlines(), "params": P, "params_skin": P_SKIN, "params_organ": P_ORGAN, "body": body,
           "subjects": subjects, "excludes": excludes, "skin_fov_cut_x": [K.cut_lo, K.cut_hi],
           "structures": rows, "skipped_flagged": skipped, "organ_push": rows_o, "skin_pull": rows_s,
           "orbit_reseat": ORBIT_ROWS if body == "vhm" else {},
           "summary": summ(rows), "summary_organ": summ(rows_o), "summary_skin": summ({k: v for k, v in rows_s.items() if "skipped" not in v}),
           "summary_orbit": summ({k: v for k, v in ORBIT_ROWS.items() if not k.startswith("_")}) if body == "vhm" else {}}
    if not dry:
        report.write_text(json.dumps(rep, indent=1))
    print(f"{body}: Q185 bone carve {rep['summary']} (skipped {len(skipped)}); organ push {rep['summary_organ']}; "
          f"skin pull-in {rep['summary_skin']}" + (f"; orbit reseat {rep['summary_orbit']}" if body == "vhm" else "")
          + f" -> {report.relative_to(REPO)}")
    return 0


# ---------------------------------------------------------------- Q185g: his transferred orbit vs his own oculomotor labels
ORBIT_SUBJECT = "xfer_vhf2vhm"
ORBIT_OWN_SUBJECT = "ct_vhm_orbit"          # his own label build (ingest_volume_geometry.py convert; rebuilt identically)
ORBIT_VOL = "vhm_oculomotor_muscles.nii.gz"
ORBIT_MAP = REPO / "mappings" / "subjects" / "ct_vhm_orbit_volume_mapping.json"
ORBIT_SIDE = {"r": [2, 3, 4, 5, 6, 8, 9, 16, 19], "l": [7, 10, 11, 12, 13, 14, 15, 17, 18]}   # TS oculomotor labels per orbit
ORBIT_RE = re.compile(r"^(superior|inferior|medial|lateral)_(rectus|oblique)_[lr]$|^levator_palpebrae_superioris_[lr]$|^optic_n$")
# gates: 0 % outside skin, <= 2 % > 1 mm in bone (optic n: canal, n/a), >= 90 % inside that orbit (convex hull of the
# side's own labels incl. the globe, + 3 mm: the fragmentary labels under-fill the cone by about one belly radius);
# anatomy: a label build under half the transferred volume, or in pieces (largest component < 95 % of its vertices),
# is a fragment of the frozen-CT segmentation (Q47 / Q99), not the muscle
P_ORBIT = {"skin_max": 0.0, "bone_max": 0.02, "in_orbit_tol_mm": 3.0, "in_orbit_min": 0.90, "own_vol_min_ratio": 0.5,
           "own_main_component_min": 0.95}
TAG_ORBIT = "Q185 orbit re-seat"
TAGS = TAGS + (TAG_ORBIT,)
ORBIT_ROWS: dict = {}


def in_hull(H, v, tol) -> float:
    return float((np.max(v @ H.equations[:, :3].T + H.equations[:, 3], 1) <= tol).mean()) if len(v) else 0.0


def orbit_reseat(cl: dict, B: BoneField, K: SkinField, writes: dict, her: str) -> None:
    """Q185g: the f2m transfer carries her orbit on ONE cranium-wide affine bone map, which lands his orbits several mm
    off; his own TS oculomotor labels say where they are. Per orbit: rigid offset = label-volume-weighted mean of
    (own label centroid - transferred centroid); every transferred orbit record of that side is moved by it and
    compared with his own label build. Ship the candidate closest to his label among those passing the gates and the
    anatomy check; else keep the shipped record (badged when it was flagged)."""
    from scipy import ndimage as ndi
    from scipy.spatial import ConvexHull, cKDTree
    from engine.volume_ingest import voxels_to_atlas
    ORBIT_ROWS.clear()
    ids = [a for a, (sub, _) in cl.items() if sub == ORBIT_SUBJECT and ORBIT_RE.search(a)]
    if not ids:
        return
    if not (TASK / ORBIT_VOL).exists():
        ORBIT_ROWS["_note"] = f"{ORBIT_VOL} absent locally: nothing re-seated"; return
    V, A, sp = _nii(TASK / ORBIT_VOL); O = B.O; vox = float(np.prod(sp))
    lab: dict = {}
    for e in json.loads(ORBIT_MAP.read_text())["entries"]:
        if e.get("atlas_id"):
            lab.setdefault(e["atlas_id"], []).append(e["label"])

    def surf(labs):
        m = np.isin(V, labs); s = np.argwhere(m & ~ndi.binary_erosion(m))
        return voxels_to_atlas(s.astype(float), A) - O, int(m.sum()) * vox / 1000
    hull = {k: ConvexHull(surf(v)[0]) for k, v in ORBIT_SIDE.items()}
    geo = {a: [record(ORBIT_SUBJECT, s) for s in cl[a][1]] for a in ids}
    om = json.loads((VH / ORBIT_OWN_SUBJECT / "manifest.json").read_text())["structures"] if (VH / ORBIT_OWN_SUBJECT).exists() else []
    T = {}
    for side in "rl":
        w, dd = [], []
        for a in ids:
            if a.endswith("_" + side) and a in lab:
                S, vl = surf(lab[a])
                if vl > 0:
                    idx = np.argwhere(np.isin(V, lab[a])); c = voxels_to_atlas(idx.mean(0, keepdims=True).astype(float), A)[0] - O
                    dd.append(c - np.concatenate([g[0] for g in geo[a]]).mean(0)); w.append(vl)
        T[side] = (np.array(dd) * np.array(w)[:, None]).sum(0) / sum(w) if w else np.zeros(3)
        ORBIT_ROWS[f"_offset_{side}"] = {"t_mm": np.round(T[side], 2).tolist(), "norm_mm": round(float(np.linalg.norm(T[side])), 2),
                                         "residual_mm": np.round(np.linalg.norm(np.array(dd) - T[side], axis=1), 1).tolist() if dd else []}
    T["n"] = (T["r"] + T["l"]) / 2                 # optic n: one record over both orbits + chiasm
    word = {"r": "right", "l": "left", "n": "both"}
    for a in ids:
        side = "n" if a == "optic_n" else a[-1]
        v0 = np.concatenate([g[0] for g in geo[a]]); f0 = np.concatenate([g[1] + o for g, o in zip(geo[a], np.cumsum([0] + [len(g[0]) for g in geo[a]]))])
        own = [record(ORBIT_OWN_SUBJECT, s) for s in om if s["atlas_id"] == a]
        cands = {"as_shipped": (v0, f0), "reseated": (v0 + T[side], f0)}
        if own:
            cands["own_label_build"] = (np.concatenate([g[0] for g in own]),
                                        np.concatenate([g[1] + o for g, o in zip(own, np.cumsum([0] + [len(g[0]) for g in own]))]))
        S = cKDTree(surf(lab[a])[0]) if a in lab else None
        row = {"side": word[side], "offset_mm": np.round(T[side], 2).tolist()}
        for k, (v, f) in cands.items():
            r = {"vol_cm3": round(volume(v, f) / 1000, 3), "outside_skin": round(K.frac(v)[0], 4),
                 "in_bone": None if a in BONE_EXCLUDE_IDS else round(frac_in(B, v), 4),
                 "in_orbit": None if side == "n" else round(in_hull(hull[side], v, P_ORBIT["in_orbit_tol_mm"]), 3),
                 "label_median_mm": round(float(np.median(S.query(v)[0])), 2) if S is not None else None}
            r["gates"] = bool(r["outside_skin"] <= P_ORBIT["skin_max"] and (r["in_bone"] is None or r["in_bone"] <= P_ORBIT["bone_max"])
                              and (r["in_orbit"] is None or r["in_orbit"] >= P_ORBIT["in_orbit_min"]))
            row[k] = r
        vt = row["as_shipped"]["vol_cm3"]
        if "own_label_build" in row:
            from scipy.sparse.csgraph import connected_components
            ov, of = cands["own_label_build"]
            _, cc = connected_components(adjacency(len(ov), of), directed=False)
            big = float(np.bincount(cc).max() / len(ov)); row["own_label_build"]["largest_component_frac"] = round(big, 3)
            row["own_label_build"]["anatomy"] = bool(row["own_label_build"]["vol_cm3"] >= P_ORBIT["own_vol_min_ratio"] * vt
                                                     and big >= P_ORBIT["own_main_component_min"])
        ok = [k for k in ("reseated", "own_label_build", "as_shipped") if k in row and row[k]["gates"]
              and row[k].get("anatomy", True)]
        lm = lambda k: row[k]["label_median_mm"] if row[k]["label_median_mm"] is not None else 0.0   # noqa: E731
        pick = min(ok, key=lambda k: (lm(k), k != "reseated")) if ok else "as_shipped"
        if pick == "own_label_build":   # would need an export exclude of the transfer -- not the case on his data (stated)
            row["note"] = "own label build preferred: ship it by excluding this id from xfer_vhf2vhm"; pick = "as_shipped"
        row["pick"] = pick; row["as_shipped"]["was_flagged"] = bool(lm("as_shipped") > 5.0)
        if pick == "reseated":
            t = T[side]; own_txt = (f"; his own label build ({row['own_label_build']['vol_cm3']:.2f} cm3, "
                                    f"{100 * row['own_label_build']['largest_component_frac']:.0f} % in one piece) is a fragment of the "
                                    f"frozen-CT segmentation, so the transferred shape is kept"
                                    if "own_label_build" in row and not row["own_label_build"]["anatomy"] else "")
            lab_txt = (f"; mesh -> own label median {row['as_shipped']['label_median_mm']:.1f} -> {row['reseated']['label_median_mm']:.1f} mm"
                       if S is not None else " (no usable own label for this muscle: moved with its orbit)")
            badge = (f"{TAG_ORBIT}: moved {np.linalg.norm(t):.1f} mm (x {t[0]:+.1f}, y {t[1]:+.1f}, z {t[2]:+.1f}) onto {her} own "
                     f"TotalSegmentator oculomotor labels -- the per-orbit offset of this transfer's cranium-wide bone map in "
                     f"{her} {word[side]} orbit{'s' if side == 'n' else ''}{lab_txt}{own_txt}.")
            if a in writes.get(ORBIT_SUBJECT, {}):
                row["note"] = "already moved by an earlier stage: not re-seated"; row["pick"] = "as_shipped"
            else:
                x = v0 + T[side]; o = 0; lst = []
                for s, g in zip(cl[a][1], geo[a]):
                    lst.append((s, x[o:o + len(g[0])])); o += len(g[0])
                writes.setdefault(ORBIT_SUBJECT, {})[a] = ({"badge": badge, "hidden_default": False}, lst)
                row["badge"] = badge
        row["shipped"] = row["pick"] == "reseated"
        ORBIT_ROWS[a] = row
        SCRATCH_BFG.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(SCRATCH_BFG / f"orbit_vhm_{a}.npz", v0=v0.astype(np.float32), v1=(v0 + T[side]).astype(np.float32),
                            own=cands["own_label_build"][0].astype(np.float32) if own else np.zeros((0, 3), np.float32),
                            label=(surf(lab[a])[0] if a in lab else np.zeros((0, 3))).astype(np.float32),
                            ctx=np.concatenate([surf(ORBIT_SIDE["r"])[0], surf(ORBIT_SIDE["l"])[0]])[::7].astype(np.float32))
        print(f"  {a} [{ORBIT_SUBJECT}] orbit: shipped med {row['as_shipped']['label_median_mm']} in-orbit {row['as_shipped']['in_orbit']} | "
              f"reseated med {row['reseated']['label_median_mm']} in-orbit {row['reseated']['in_orbit']} bone {row['reseated']['in_bone']} "
              f"gates {row['reseated']['gates']} | own {row.get('own_label_build', {}).get('vol_cm3')} cm3 vs {vt} -> {row['pick']}", flush=True)


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
    fig.tight_layout(rect=(0, 0, 1, 0.985)); out.mkdir(parents=True, exist_ok=True); f = out / "montage_worst6_before_after.png"
    fig.savefig(f, dpi=110); plt.close(fig)
    print(f"montage {f} ({len(rows)} structures)")
    return f


def montage_bfg(out: Path = SCRATCH_BFG, n_skin: int = 4) -> Path:
    """Q185 b/f/g worst cases, before | after (two views each): skin pull-in (red = outside own skin, grey = skin),
    organ push (purple = > 1 mm in own organ label, grey = organ surface), orbit re-seat (black = own label surface)"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    for body in ("vhm", "vhf"):
        rp = REPO / "data" / "derived" / f"Q185_bone_carve_{body}.json"
        if not rp.exists():
            continue
        R_ = json.loads(rp.read_text())
        sk = sorted(((r["outside_before"], a, r) for a, r in R_.get("skin_pull", {}).items() if "skipped" not in r), key=lambda x: -x[0])
        rows += [("skin", body, a, r) for _, a, r in sk[:n_skin // 2]]
        rows += [("organ", body, a, r) for a, r in sorted(R_.get("organ_push", {}).items(), key=lambda x: -x[1]["in_organ_before"])[:1]]
        orb = [(a, r) for a, r in R_.get("orbit_reseat", {}).items() if not a.startswith("_") and r["as_shipped"].get("label_median_mm")]
        rows += [("orbit", body, a, r) for a, r in sorted(orb, key=lambda x: -x[1]["as_shipped"]["label_median_mm"])[:2]]
    fig, ax = plt.subplots(len(rows), 4, figsize=(16, 3.6 * len(rows)))
    ax = np.atleast_2d(ax)
    for i, (kind, body, aid, r) in enumerate(rows):
        z = np.load(SCRATCH_BFG / f"{kind}_{body}_{aid}.npz"); c = z["v0"].mean(0); who = "his" if body == "vhm" else "her"
        if kind == "orbit":
            m0 = m1 = None; ctx = z["label"]; col, bad = "#1f77b4", "#d62728"
            t0 = f"shipped, label med {r['as_shipped']['label_median_mm']} mm, in orbit {r['as_shipped']['in_orbit']}"
            t1 = (f"re-seated{'' if r['shipped'] else ' (NOT shipped)'}, label med {r['reseated']['label_median_mm']} mm, "
                  f"in orbit {r['reseated']['in_orbit']}")
        else:
            m0, m1, ctx = z["m0"], z["m1"], z["ctx"]; col, bad = "#2ca02c", ("#d62728" if kind == "skin" else "#9467bd")
            k0, k1 = (("outside_before", "outside_after") if kind == "skin" else ("in_organ_before", "in_organ_after"))
            t0 = f"before: {kind} flag {100 * r[k0]:.1f} %"
            t1 = f"{'after' if r['shipped'] else 'attempt (HELD)'}: {100 * r[k1]:.1f} %"
        for j, (V, M, tag) in enumerate(((z["v0"], m0, t0), (z["v1"], m1, t1))):
            for k, (u, w, vn) in enumerate(((0, 1, "x-y"), (2, 1, "z-y"))):
                a = ax[i, 2 * j + k]
                a.scatter(ctx[:, u] - c[u], ctx[:, w] - c[w], s=0.4, c="#999999" if kind != "orbit" else "#000000", lw=0)
                if kind == "orbit" and len(z["own"]):
                    a.scatter(z["own"][:, u] - c[u], z["own"][:, w] - c[w], s=0.6, c="#ff7f0e", lw=0)
                M_ = np.zeros(len(V), bool) if M is None else M.astype(bool)
                a.scatter(V[~M_, u] - c[u], V[~M_, w] - c[w], s=1.2, c=col, lw=0)
                a.scatter(V[M_, u] - c[u], V[M_, w] - c[w], s=2.5, c=bad, lw=0)
                lim = np.abs(z["v0"] - c).max() * 1.2 + (12 if kind == "orbit" else 3)
                a.set_xlim(-lim, lim); a.set_ylim(-lim, lim); a.set_aspect("equal"); a.tick_params(labelsize=6)
                a.set_title(f"{who} {aid} [{kind}] ({vn})\n{tag}", fontsize=7)
    fig.suptitle("Q185 b/f/g: skin pull-in (red = outside own skin) / organ push (purple = in own organ) / orbit re-seat "
                 "(black = his own TS label surface, orange = his own label build)", fontsize=9)
    fig.tight_layout(rect=(0, 0, 1, 0.985)); out.mkdir(parents=True, exist_ok=True); f = out / "montage_worst_before_after.png"
    fig.savefig(f, dpi=100); plt.close(fig)
    print(f"montage {f} ({len(rows)} rows)")
    return f


def main(argv=None) -> int:
    if argv is None and sys.argv[1:2] == ["montage_bfg"]:
        montage_bfg(); return 0
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
