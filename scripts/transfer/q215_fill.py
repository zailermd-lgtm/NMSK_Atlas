#!/usr/bin/env python3
"""Q215: replace the male-carried HIP / THIGH target muscles of the own female page by muscles re-bounded on HER OWN evidence, worst first, inside guards.

    python3 scripts/transfer/q215_fill.py --work SCRATCH/q215/work --crops SCRATCH/q215/crops [--dry] [--only id,id] [--out build/viewer_f_hr_q215] [--report data/derived/Q215_report.json]

Input  = the Q214 female bundle (build/viewer_f_hr_q214); output = a NEW bundle (build/viewer_f_hr_q215).  Every entry that is not listed in the report stays byte for byte.
Evidence = her 1 mm colour cryosections registered to her CT femur (Q179 / Q181 registration, `vhf_thigh_refit_q181.py photos`) and her CT bones / own CT and pelvic-floor muscles.
Method = the Q48 marker watershed redone in the registered frame (q215_refit.py): region = her photographed muscle, markers = the previous (Q48) labels moved by the registered offset, her bones and
her own measured muscles are never part of a target muscle; every muscle that is not a target is held at its base voxels.  The muscle SET (identity) is still the male's: Source class stays
TRANSFERRED -- the card says so; what changes is the position, extent and boundaries, which are hers.
Per candidate the guards (all must hold, else the muscle is NOT replaced and the reasons are recorded; a failed muscle is held and the refit re-run, max MAX_ROUNDS):
  skin (every vertex inside, >= 1 mm deep), bone (<= 8 % of the vertices inside bone, deepest embedding <= 5 mm on the Q204 lattice), photographed-muscle share (>= 0.60 and not below the old
  mesh's), photographed-muscle volume (volume x share) >= 0.6 of the old mesh's (her measured compartment: it may not lose photographed muscle), end-to-end length >= 0.75 x the old mesh (or >= 0.6 x the Z reference), <= 60 % of the volume inside the
  other muscles (Q204 lattice measure, final state with all replacements swapped in), one connected piece (>= 0.98 of the vertices or the old mesh's share), new surface <= 25 mm (p95) from the old one, and a
  Z-fill continuation piece welded to the old mesh (if any) must still meet the new mesh within 2.5 mm."""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import nibabel as nib
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402
from scripts.transfer import q215_refit as RF  # noqa: E402
from scripts.transfer.q215_common import *  # noqa: E402,F401,F403
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402

SUBJECT = "xfer_vhm2vhf_sep_q215"
BUDGET = 9000                     # triangles of a muscle of this page (the replaced meshes have 9000)
SMOOTH_SIGMA = 1.5                # Gaussian sigma (voxels) of the label surface (Q48 used 1.0): the strict photographed-muscle rule leaves a ragged label, 1.5 removes the staircase and closes the surface
#                                   (mesh-to-label error median 0.6 -> 0.6 mm, p95 1.0 -> 1.1 mm on vastus intermedius r; volume -1.3 %)
MAX_ROUNDS = 6
# ------------------------------------------------------------------ guards
SKIN_DEPTH_MIN_MM = 1.0
IN_BONE_MAX_PCT = 8.0             # ray-parity share of vertices inside a bone mesh (the Q213 in-bone repair threshold)
BONE_DEPTH_MAX_MM = 5.0           # Q204 lattice depth
MUSC_SHARE_MIN = 0.45             # a thin sheet (obturator internus, gracilis) has a large 2 mm boundary layer that her colour rule does not call muscle: the gate is absolute 0.45 and "not worse than the old mesh"
EVID_LO = 0.60                    # volume vs her measured compartment: (candidate volume x its photographed-muscle share) / (old mesh volume x its share) = how much photographed muscle the new mesh holds vs the
#                                   old one: it must not LOSE photographed muscle; it may gain what the registered frame reveals (an old mesh lying 10 mm off her muscle covers little of it)
COLLAPSE_MIN = 0.25               # and the new mesh keeps at least this share of the old mesh's volume (a bone-filled Q48 label may legitimately lose 60 %)
LEN_LO = 0.75                     # tendinous ends are not photographed muscle: a belly may end 25 % shorter than the old mesh ...
SQUEEZE_MIN = 0.80                # a muscle whose volume fell below this share of what the unconstrained refit (round 0, nothing held) gave it was squeezed by the OLD meshes of held neighbours: not replaced
LEN_Z_LO = 0.60                   # ... or, where the old mesh is known to be wrong (obturator internus 6x the Z size), be at least this share of the Z-Anatomy reference muscle's length (that one includes its tendons)
OVERLAP_MAX = 60.0
OVERLAP_NOTE = 40.0
MAIN_PIECE_MIN = 0.98
MOVE_P95_MAX_MM = 25.0
SEAM_MAX_MM = 2.5                 # a Z-fill continuation welded to the old mesh may be this far (p95) from the new mesh's end face ...
SEAM_WARP_MAX_MM = 8.0            # ... else it is re-welded (warped onto the new end face) when the largest seam distance is <= this; REWELD_P95_MM after the warp
Z_GATE_LO, Z_GATE_HI = 0.25, 4.5  # reported against the Z-Anatomy female reference volume; gated wide (a muscle outside it is not a plausible adult muscle)

ATTRIBUTION = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections via the NCI Imaging Data Commons, registered to her CT femur (Q179); the transferred muscle "
               "set from the male's DU lower-limb release (Andreassen et al. 2023, Sci Data 10:34, doi:10.1038/s41597-022-01905-2, CC BY 4.0). Hip / thigh target muscles re-bounded on her registered "
               "photographs in Q215 (scripts/transfer/q215_refit.py, q215_fill.py). Derived data.")


REWELD_P95_MM = 1.5
REWELD_MAX_MOVE_MM = 8.0

# ------------------------------------------------------------------ small helpers
def vol_cm3(v, f):
    return abs(IB.volume(v, f)) / 1000.0


def principal_axis(v):
    c = v.mean(0)
    return c, np.linalg.svd(v - c, full_matrices=False)[2][0]


def extent_along(v, c, u):
    t = (v - c) @ u
    return float(np.percentile(t, 99) - np.percentile(t, 1))


def main_frac(f):
    mf, _lab, _cnt = R.main_frac(np.asarray(f, np.int64))
    return float(mf)


def label_mesh_smooth(V, A, lab, aid, rules):
    """Q181's label_mesh (convert-equivalent: Q152 bridges / island drops, detached pieces dropped) with the Q215 surface sigma"""
    from engine import volume_ingest as VI
    orig = VI.label_surface
    VI.label_surface = lambda volume, label, step=1, smooth=0.0: orig(volume, label, step=step, smooth=(SMOOTH_SIGMA if smooth > 0 else smooth))
    try:
        return R.label_mesh(V, A, lab, aid, R.ORIGIN, rules)
    finally:
        VI.label_surface = orig


def decimate(v, f, budget=BUDGET):
    from scripts.export_viewer_bundle import decimate_quadric
    out = decimate_quadric(np.asarray(v, float), np.asarray(f, np.int64), budget)
    return (v, f) if out is None else out


def surface_move(v_new, v_old):
    d1 = cKDTree(v_old).query(v_new)[0]
    d0 = cKDTree(v_new).query(v_old)[0]
    a = np.r_[d1, d0]
    return dict(median_mm=round(float(np.median(a)), 2), p95_mm=round(float(np.percentile(a, 95)), 2), max_mm=round(float(a.max()), 2))


def label_boundary_points(V, A, lab, origin):
    """atlas coordinates of the voxel centres on the surface of one label (the segmented compartment that the mesh was cut from)"""
    from engine import volume_ingest as vol
    m = V == lab
    if not m.any():
        return np.zeros((0, 3))
    sh = m & ~ndi.binary_erosion(m)
    ijk = np.argwhere(sh).astype(float)
    return vol.voxels_to_atlas(ijk, A) - np.asarray(origin, float)


def mesh_to_label_error(v, bpts):
    d = cKDTree(bpts).query(v)[0]
    return dict(median_mm=round(float(np.median(d)), 2), p95_mm=round(float(np.percentile(d, 95)), 2), max_mm=round(float(d.max()), 2))


class Evidence:
    """her registered photographs: per label, how much of it lies on her photographed muscle (her Q179 rule: mus == 2), on known non-muscle (fat, fascia, gel: mus == 1) or where the photograph is unknown"""

    def __init__(self, work):
        self.work = Path(work)

    def shares(self, D, labels):
        cnt = np.zeros((256, 3), np.int64)
        for side, (i0, i1) in R.SIDE_I.items():
            meta = json.loads((self.work / f"p1_{side}.json").read_text())
            mus = np.load(self.work / f"p1_{side}_mus.npy", mmap_mode="r")
            for t, k in enumerate(meta["ks"]):
                sub = D[i0:i1, :, k].astype(np.int64)
                m = np.asarray(mus[t]).astype(np.int64)
                sel = sub > 0
                if sel.any():
                    cnt += np.bincount(sub[sel] * 3 + m[sel], minlength=768).reshape(256, 3)
        out = {}
        for aid, l in labels.items():
            n = int(cnt[l].sum())
            out[aid] = dict(voxels=n, musc=round(float(cnt[l, 2] / max(n, 1)), 3), non_muscle=round(float(cnt[l, 1] / max(n, 1)), 3), unknown=round(float(cnt[l, 0] / max(n, 1)), 3))
        return out


# ------------------------------------------------------------------ the page state (guards are measured on the Q214 bundle with replacements swapped in)
class Page:
    def __init__(self, bundle):
        self.B = bundle
        self.ctx = F.Context(bundle)

    def pieces(self, sid):
        """context keys of the base piece and the zfill continuations of a muscle id"""
        base = [k for k in self.ctx.muscles if k.split("#")[0] == sid]
        zf = [k for k in self.ctx.muscles if re.fullmatch(re.escape(sid) + r"_zfill\w*#\d+", k)]
        return base, zf

    def overlap_state(self, replaced):
        """{group id: % of its voxels inside other muscles} for the page with `replaced` = {id: (v, f)} swapped in (Q204 lattice measure, Z-fill pieces merged)"""
        mus = dict(self.ctx.muscles)
        for sid, rv in replaced.items():
            v, f = rv[0], rv[1]
            base, _zf = self.pieces(sid)
            assert len(base) == 1, (sid, base)
            mus[base[0]] = (v, f)
            for key, zn in (rv[2] if len(rv) > 2 else {}).items():          # re-welded Z-fill continuation pieces
                mus[key] = (zn, mus[key][1])
        shim = SimpleNamespace(all_min=self.ctx.all_min, all_max=self.ctx.all_max, muscles=mus, skin=self.ctx.skin)
        of = F.OverlapField(shim)
        out = {}
        for mid, w in of.groups.items():
            out[mid] = round(100.0 * float((of.cnt[tuple(w.T)] > 1).mean()), 1)
        return out

    def metrics(self, v, f, v_ref=None, f_ref=None):
        ctx = self.ctx
        g = {}
        ins, _cp, _dist = ctx.bone_field.inside(v)
        g["in_bone_pct"] = round(100.0 * float(ins.mean()), 1)
        bdp = ctx.bone_depth().depth(v)
        g["bone_depth_max_mm"] = round(float(bdp.max()), 1)
        g["bone_deep_pct"] = round(100.0 * float((bdp > 1.5).mean()), 1)
        sk_in, sk_d = ctx.skin_state(v)
        g["inside_skin_pct"], g["min_skin_depth_mm"] = round(sk_in, 2), round(sk_d, 1)
        g["volume_cm3"] = round(vol_cm3(v, f), 1)
        g["main_piece"] = round(main_frac(f), 4)
        if v_ref is not None:
            c, u = principal_axis(v_ref)
            g["length_mm"] = round(extent_along(v, c, u), 1)
        return g


# ------------------------------------------------------------------ the muscles
def severity_rows(B, evid_base, labels, q213):
    """worst-first order of the candidate muscle-sides: Q213 audit numbers (scale vs the male, overlap, inside bone) + her photographed-muscle share of the Q48 region"""
    rows = {}
    for aid in labels:
        a = q213.get(aid, {})
        vol = a.get("vol_cm3", {})
        vf, vm, vz = vol.get("vhf"), vol.get("vhm"), vol.get("zan_f")
        own = a.get("own_q204", {})
        sc = 0.0
        if vf and vz:
            sc += 3.0 * abs(np.log(max(vf, 1e-3) / max(vz, 1e-3)))
        sc += float(own.get("overlap_pct") or 0.0) / 20.0 + float(own.get("inside_bone_pct") or 0.0) / 10.0 + 5.0 * (1.0 - evid_base[aid]["musc"])
        rows[aid] = dict(score=round(float(sc), 2), vol_own=vf, vol_male=vm, vol_z=vz, scale_vs_male=(round(vf / vm, 2) if vf and vm else None), overlap_pct_q213=own.get("overlap_pct"),
                         inside_bone_pct_q213=own.get("inside_bone_pct"), musc_share_base=evid_base[aid]["musc"])
    return rows


def reweld_piece(zv, zf, seam, targets, lam=20.0):
    """warp a Z-fill continuation piece so that its seam vertices land on the new mesh's surface: smooth displacement field (graph Laplacian), the seam vertices pulled onto `targets`, the 12 % of the
    vertices farthest from the seam held (its free end stays on its bone)"""
    from scipy.sparse import diags, identity
    from scipy.sparse.linalg import spsolve
    n = len(zv)
    Lap = IB.laplacian(n, zf)
    W = np.zeros(n)
    P = np.zeros((n, 3))
    W[seam] = 30.0
    P[seam] = targets - zv[seam]
    ds = cKDTree(zv[seam]).query(zv)[0]
    far = ds >= np.percentile(ds, 88)
    W[far & ~seam] = 5.0
    M = (diags(W) + lam * Lap + 1e-3 * identity(n)).tocsc()
    D = np.column_stack([spsolve(M, W * P[:, k]) for k in range(3)])
    return zv + D


def seam_vertices(v0, f0, zv, tol=0.8):
    """vertices of a Z-fill continuation that sit on the OLD mesh's surface (the weld)"""
    return trimesh.proximity.closest_point(trimesh.Trimesh(v0, f0, process=False), zv)[1] < tol


def evaluate(page, aid, v1, f1, v0, f0, bpts, ev_base, ev_new, zref, zfill_meshes, zlen=None):
    """individual guards of one candidate (the overlap guard is the final-state check)"""
    g1 = page.metrics(v1, f1, v0)
    g0 = page.metrics(v0, f0, v0)
    why = []
    g = dict(before=g0, after=g1)
    g["volume_ratio"] = round(g1["volume_cm3"] / max(g0["volume_cm3"], 1e-6), 3)
    g["length_ratio"] = round(g1["length_mm"] / max(g0["length_mm"], 1e-6), 3)
    g["move"] = surface_move(v1, v0)
    g["move_new_to_old_p95_mm"] = round(float(np.percentile(cKDTree(v0).query(v1)[0], 95)), 2)
    g["evidence_volume_ratio"] = round((g1["volume_cm3"] * ev_new["musc"]) / max(g0["volume_cm3"] * ev_base["musc"], 1e-6), 2)
    if zlen:
        g["length_vs_z"] = round(g1["length_mm"] / zlen, 2)
    g["fit_error_vs_label"] = mesh_to_label_error(v1, bpts)
    g["musc_share"] = [ev_base["musc"], ev_new["musc"]]
    g["non_muscle_share"] = [ev_base["non_muscle"], ev_new["non_muscle"]]
    g["z_ref_cm3"] = zref
    if zref:
        g["volume_vs_z"] = round(g1["volume_cm3"] / zref, 2)
    if g1["inside_skin_pct"] < 100.0 or g1["min_skin_depth_mm"] < SKIN_DEPTH_MIN_MM:
        why.append(f"skin: {g1['inside_skin_pct']} % inside, closest {g1['min_skin_depth_mm']} mm")
    if g1["in_bone_pct"] > IN_BONE_MAX_PCT:
        why.append(f"{g1['in_bone_pct']} % of the vertices inside her bone (gate {IN_BONE_MAX_PCT:g})")
    if g1["bone_depth_max_mm"] > BONE_DEPTH_MAX_MM:
        why.append(f"embedded {g1['bone_depth_max_mm']} mm in bone (gate {BONE_DEPTH_MAX_MM:g})")
    if ev_new["musc"] < MUSC_SHARE_MIN:
        why.append(f"only {ev_new['musc']} of it lies on her photographed muscle (gate {MUSC_SHARE_MIN})")
    elif ev_new["musc"] < ev_base["musc"] - 0.01:
        why.append(f"photographed-muscle share fell {ev_base['musc']} -> {ev_new['musc']}")
    if g["evidence_volume_ratio"] < EVID_LO:
        why.append(f"photographed-muscle volume x{g['evidence_volume_ratio']} of the old mesh's ({g0['volume_cm3']} x {ev_base['musc']} -> {g1['volume_cm3']} x {ev_new['musc']} cm3; gate >= {EVID_LO})")
    if g["volume_ratio"] < COLLAPSE_MIN:
        why.append(f"volume x{g['volume_ratio']} of the old mesh (gate >= {COLLAPSE_MIN})")
    if g["length_ratio"] < LEN_LO and not (zlen and g["length_vs_z"] >= LEN_Z_LO):
        why.append(f"length x{g['length_ratio']} of the old mesh (gate >= {LEN_LO}" + (f", or >= {LEN_Z_LO} of the Z reference: x{g['length_vs_z']}" if zlen else "") + ")")
    if g1["main_piece"] < min(MAIN_PIECE_MIN, g0["main_piece"]) - 1e-9:
        why.append(f"main piece {g1['main_piece']} < {min(MAIN_PIECE_MIN, g0['main_piece'])}")
    if g["move_new_to_old_p95_mm"] > MOVE_P95_MAX_MM:
        why.append(f"the new surface lies {g['move_new_to_old_p95_mm']} mm (p95) from the old mesh (gate {MOVE_P95_MAX_MM:g})")
    if zref and not (Z_GATE_LO <= g["volume_vs_z"] <= Z_GATE_HI):
        why.append(f"volume {g1['volume_cm3']} cm3 is x{g['volume_vs_z']} of the Z-Anatomy female reference ({zref} cm3; gate {Z_GATE_LO}-{Z_GATE_HI})")
    g["zfill_new"] = {}
    for key, zv, zf in (zfill_meshes or []):
        S = seam_vertices(v0, f0, zv)
        if S.sum() < 3:
            continue                                                  # not welded to the old mesh (a continuation that overlaps, or whose weld is a few vertices)
        tm1 = trimesh.Trimesh(v1, f1, process=False)
        cp, dn, _ = trimesh.proximity.closest_point(tm1, zv[S])
        info = dict(piece=key.split("#")[0], seam_vertices=int(S.sum()), before=dict(median=round(float(np.median(dn)), 2), p95=round(float(np.percentile(dn, 95)), 2), max=round(float(dn.max()), 2)))
        g.setdefault("seam_gap_mm", info)
        if info["before"]["p95"] <= SEAM_MAX_MM:
            continue
        if info["before"]["max"] > SEAM_WARP_MAX_MM:
            why.append(f"the Z-fill continuation welded to the old mesh would be {info['before']['p95']} mm (p95), {info['before']['max']} mm (max) off the new mesh at the seam (gate {SEAM_MAX_MM:g} mm, re-weld up to {SEAM_WARP_MAX_MM:g} mm)")
            continue
        zn = reweld_piece(zv, zf, S, cp)
        d2 = trimesh.proximity.closest_point(tm1, zn[S])[1]
        mv = np.linalg.norm(zn - zv, axis=1)
        flipped, stretched = IB.flipped_pct(zv, zn, zf), IB.stretched_pct(zv, zn, zf) - IB.stretched_pct(zv, zv, zf)
        sk_in, sk_d = page.ctx.skin_state(zn)
        ins, _, _ = page.ctx.bone_field.inside(zn)
        ins0, _, _ = page.ctx.bone_field.inside(zv)
        info["after"] = dict(p95=round(float(np.percentile(d2, 95)), 2), max=round(float(d2.max()), 2), move_mean=round(float(mv.mean()), 2), move_max=round(float(mv.max()), 2), flipped_pct=round(flipped, 2),
                             stretched_rise=round(float(stretched), 1), in_bone_pct=[round(100 * float(ins0.mean()), 1), round(100 * float(ins.mean()), 1)], inside_skin_pct=round(sk_in, 1))
        bad = []
        if info["after"]["p95"] > REWELD_P95_MM:
            bad.append(f"re-weld leaves {info['after']['p95']} mm")
        if mv.max() > REWELD_MAX_MOVE_MM:
            bad.append(f"re-weld moves the continuation {round(float(mv.max()), 1)} mm")
        if flipped > 1.0 or stretched > 12.0:
            bad.append(f"re-weld folds {round(flipped, 2)} % / stretches +{round(float(stretched), 1)} points")
        if sk_in < 100.0 or info["after"]["in_bone_pct"][1] > info["after"]["in_bone_pct"][0] + 2.0:
            bad.append("re-weld puts the continuation outside the skin / into her bone")
        if bad:
            why.append("the Z-fill continuation welded to the old mesh cannot be re-welded to the new one: " + "; ".join(bad))
        else:
            g["zfill_new"][key] = zn
            g["seam_gap_mm"] = info
    return g, why


def run_rounds(work, crops, page, targets, only, log=print):
    """refit + guards, auto-hold loop -> (label volume, accepted {id: dict(v, f, guards, bpts, ...)}, failed {id: [reasons]}, rounds)"""
    ids = R.label_ids()
    base_img = nib.load(str(R.Q48_VOL))
    A = base_img.affine
    D0 = np.asarray(base_img.dataobj)
    evd = Evidence(work)
    ev_base = evd.shares(D0, {a: ids[a] for a in targets})
    rules = R.q152_rules()
    q213 = json.loads((REPO / "data/derived/Q213_target_muscle_audit.json").read_text())
    zmeshes = load_z()
    hold_targets, failed, rounds, vol_round0 = set(), {}, [], {}
    sev = severity_rows(page.B, ev_base, targets, q213)
    for rnd in range(MAX_ROUNDS):
        want = [a for a in targets if a not in hold_targets and (not only or a in only)]
        hold = sorted((set(ids) - set(want)) | hold_targets)
        t0 = time.time()
        out, lv, before, after, changed, img, full = RF.refit(work, crops, hold, "her")
        log(f"round {rnd}: refit {time.time() - t0:.0f} s, targets in play {len(want)}")
        ev_new = evd.shares(out, {a: ids[a] for a in want})
        cand, fails_now = {}, {}
        for aid in want:
            t1 = time.time()
            r = label_mesh_smooth(out, A, ids[aid], aid, rules)
            if r is None:
                fails_now[aid] = ["empty label"]
                continue
            v, f, smooth, note = r
            v, f = decimate(v, f)
            v, f = np.asarray(v, float), np.asarray(f, np.int64)
            it = page.B.items[page.B.find(aid)[0]]
            v0, f0 = page.B.mesh(it)
            base_k, zf_k = page.pieces(aid)
            zfm = [(k, page.ctx.muscles[k][0], page.ctx.muscles[k][1]) for k in zf_k]
            bpts = label_boundary_points(out, A, ids[aid], R.ORIGIN)
            zv = zmeshes.get(aid)
            zref = round(vol_cm3(zv["v"], zv["f"]), 1) if zv is not None else None
            zlen = None
            if zv is not None:
                cz, uz = principal_axis(np.asarray(zv["v"], float))
                zlen = extent_along(np.asarray(zv["v"], float), cz, uz)
            g, why = evaluate(page, aid, v, f, v0, f0, bpts, ev_base[aid], ev_new[aid], zref, zfm, zlen)
            br = [[round(R.y_of_k(A, a), 1), round(R.y_of_k(A, b), 1)] for a, b in lv.get("bridged_gaps_k", {}).get(str(ids[aid]), [])]
            zn = g.pop("zfill_new", {})
            cand[aid] = dict(v=v, f=f, guards=g, smooth=smooth, notes=note, why=why, voxels=[before[aid], after[aid]], bridged_y_mm=br, zfill_new=zn)
            if rnd == 0:
                vol_round0[aid] = g["after"]["volume_cm3"]
            elif g["after"]["volume_cm3"] < SQUEEZE_MIN * vol_round0.get(aid, 0.0):
                why.append(f"volume {g['after']['volume_cm3']} cm3 is x{round(g['after']['volume_cm3'] / vol_round0[aid], 2)} of the {vol_round0[aid]} cm3 the unconstrained refit gave it: squeezed by the old meshes of held neighbours (gate >= {SQUEEZE_MIN})")
            if why:
                fails_now[aid] = why
            log(f"   {aid:26s} vol {g['before']['volume_cm3']:6.1f} -> {g['after']['volume_cm3']:6.1f}  musc {ev_base[aid]['musc']:.2f} -> {ev_new[aid]['musc']:.2f}  bone {g['after']['in_bone_pct']:4.1f}% "
                f"len x{g['length_ratio']}  move p95 {g['move']['p95_mm']}  {'FAIL ' + '; '.join(why) if why else 'ok'}  [{time.time() - t1:.0f}s]")
        # final-state overlap with every passing candidate swapped in
        ok = {a: c for a, c in cand.items() if a not in fails_now}
        t2 = time.time()
        ov_before = page.overlap_state({})
        ov_after = page.overlap_state({a: (c["v"], c["f"], c.get("zfill_new", {})) for a, c in ok.items()})
        log(f"   overlap state {time.time() - t2:.0f} s")
        for a, c in ok.items():
            c["guards"]["overlap_vol_pct"] = [ov_before.get(a), ov_after.get(a)]
            if ov_after.get(a, 0.0) > OVERLAP_MAX:
                fails_now[a] = [f"{ov_after[a]} % of its volume inside the other muscles (gate {OVERLAP_MAX:g}; old mesh {ov_before.get(a)} %)"]
        rounds.append(dict(round=rnd, held_in=sorted(hold_targets), failed={a: w for a, w in fails_now.items()}, volumes_cm3={a: c['guards']['after']['volume_cm3'] for a, c in cand.items()}))
        new_fail = [a for a in fails_now if a not in hold_targets]
        if not new_fail:
            accepted = {a: c for a, c in cand.items() if a not in fails_now}
            for a, c in accepted.items():
                c["ev"] = [ev_base[a], ev_new[a]]
                c["neighbour_overlap"] = {m: [ov_before.get(m), ov_after.get(m)] for m in ov_after if ov_before.get(m) is not None and abs(ov_after[m] - ov_before[m]) >= 1.0 and m != a}
            for a in want:
                if a in fails_now:
                    failed[a] = fails_now[a]
            return out, accepted, failed, rounds, sev, ev_base, ov_before, ov_after, A
        for a in new_fail:
            failed[a] = fails_now[a]
            hold_targets.add(a)
        log(f"   held after round {rnd}: {new_fail}")
    raise RuntimeError("did not settle")


def badge(name, aid, c, sev_row):
    g = c["guards"]
    b0, b1 = g["before"], g["after"]
    ev0, ev1 = c["ev"]
    fe = g["fit_error_vs_label"]
    mv = g["move"]
    ov = g.get("overlap_vol_pct", [None, None])
    sc = (f" (the male's {name.lower()} is {sev_row['vol_male']} cm3: x{sev_row['scale_vs_male']})" if sev_row.get("vol_male") else "")
    z = (f" The Z-Anatomy female reference muscle is {g['z_ref_cm3']} cm3 (x{g['volume_vs_z']}; shown for scale only, not used as geometry)." if g.get("z_ref_cm3") else "")
    sg = g.get("seam_gap_mm")
    seam = ""
    if sg:
        seam = (f" Its Z-fill continuation piece (welded to the old flat cut) now meets it within p95 {sg['before']['p95']} mm." if "after" not in sg else
                f" Its Z-fill continuation piece, welded to the old flat cut, was re-welded to the new end face (seam gap p95 {sg['before']['p95']} -> {sg['after']['p95']} mm, the piece moved {sg['after']['move_mean']} mm on average, max {sg['after']['move_max']} mm).")
    br = c.get("bridged_y_mm") or []
    bridged = (f" Levels bridged by interpolation between the bounding sections (empty sections, e.g. her blank / gel-spill photographs at y -127 to -134): {len(br)} run(s), y {br[0][0]} to {br[-1][1]} mm." if br else "")
    return (f"TRANSFERRED, re-bounded on her own evidence (Q215): the muscle SET is still the male's (Q48: his muscle carried onto her bones), so the Source class stays transferred -- but where this muscle "
            f"lies and where it ends are hers. The Q48 boundaries had been drawn on her photographs in a frame that sits 2-14 mm off her CT bones; Q215 redoes the Q48 marker watershed in the frame in which her 1 mm "
            f"colour cryosections are registered to her CT femur (Q179): region = her photographed muscle (colour rule validated on her traced outlines), borders = her intermuscular septa, her bones and her own CT / "
            f"pelvic-floor muscles are never part of it. Volume {b1['volume_cm3']} cm3 (previous mesh {b0['volume_cm3']} cm3){sc}. Fit error: mesh to its segmented compartment median {fe['median_mm']} mm, p95 {fe['p95_mm']} mm, "
            f"max {fe['max_mm']} mm; share of the muscle lying on her photographed muscle {ev0['musc']} -> {ev1['musc']} (on photographed fat / fascia {ev0['non_muscle']} -> {ev1['non_muscle']}); moved from the previous mesh "
            f"median {mv['median_mm']} mm, p95 {mv['p95_mm']} mm. Guards passed: inside her skin (>= {SKIN_DEPTH_MIN_MM:g} mm), {b1['in_bone_pct']} % of the vertices in her bone mesh (was {b0['in_bone_pct']} %), volume x{g['volume_ratio']}, "
            f"length x{g['length_ratio']}, {ov[1]} % of its volume inside her other muscles (was {ov[0]} %; gate {OVERLAP_MAX:g}).{z}{seam}{bridged} The muscle's identity inside her thigh is not measured: the watershed was seeded with "
            f"the male's muscle set. A position and boundary estimate, not a segmentation.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True); ap.add_argument("--crops", required=True)
    ap.add_argument("--src", default=str(SRC_BUNDLE)); ap.add_argument("--out", default=str(OUT_BUNDLE))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q215_report.json"))
    ap.add_argument("--only", default=""); ap.add_argument("--dry", action="store_true")
    ap.add_argument("--save-labels", default="", help="write the final label volume (all labels, Q48 grid) here (scratch; not committed)")
    a = ap.parse_args()
    B = Bundle(a.src)
    n0 = len(B.items)
    page = Page(B)
    targets = RF.target_ids()
    only = [x for x in a.only.split(",") if x]
    t0 = time.time()
    out, accepted, failed, rounds, sev, ev_base, ov_before, ov_after, A = run_rounds(a.work, a.crops, page, targets, only)
    if a.save_labels:
        nib.save(nib.Nifti1Image(out, A, nib.load(str(R.Q48_VOL)).header), a.save_labels)
    rep = dict(source_bundle=str(Path(a.src).relative_to(REPO)), targets=targets, rounds=rounds, severity=sev, replaced={}, rewelded={}, kept={}, piriformis={},
               params=dict(SKIN_DEPTH_MIN_MM=SKIN_DEPTH_MIN_MM, IN_BONE_MAX_PCT=IN_BONE_MAX_PCT, BONE_DEPTH_MAX_MM=BONE_DEPTH_MAX_MM, MUSC_SHARE_MIN=MUSC_SHARE_MIN, EVID_LO=EVID_LO, COLLAPSE_MIN=COLLAPSE_MIN, LEN_LO=LEN_LO, LEN_Z_LO=LEN_Z_LO,
                           OVERLAP_MAX=OVERLAP_MAX, MAIN_PIECE_MIN=MAIN_PIECE_MIN, SMOOTH_SIGMA=SMOOTH_SIGMA, SQUEEZE_MIN=SQUEEZE_MIN, MOVE_P95_MAX_MM=MOVE_P95_MAX_MM, SEAM_MAX_MM=SEAM_MAX_MM, SEAM_WARP_MAX_MM=SEAM_WARP_MAX_MM, REWELD_P95_MM=REWELD_P95_MM, REWELD_MAX_MOVE_MM=REWELD_MAX_MOVE_MM, Z_GATE=[Z_GATE_LO, Z_GATE_HI], BUDGET=BUDGET))
    order = sorted(accepted, key=lambda x: -sev[x]["score"])
    for aid in order:
        c = accepted[aid]
        it = B.items[B.find(aid)[0]]
        name = it["e"]["rec"].get("name", aid)
        bd = badge(name, aid, c, sev[aid])
        rep["replaced"][aid] = dict(severity=sev[aid], guards=c["guards"], bridged_y_mm=c.get("bridged_y_mm"), neighbour_overlap=c["neighbour_overlap"], notes=c["notes"], voxels_before_after=c["voxels"], badge=bd,
                                    subject_before=it["e"]["subject"])
        if not a.dry:
            B.replace(aid, c["v"], c["f"], rec_updates={"procedural_badge": bd}, subject=SUBJECT)
        for key, zn in c.get("zfill_new", {}).items():
            pid = key.split("#")[0]
            zit = B.items[B.find(pid)[0]]
            sg = c["guards"]["seam_gap_mm"]
            note = (f" Q215: re-welded to the re-bounded {name.lower()} (its flat cut moved with the hip / thigh re-fit): seam gap p95 {sg['before']['p95']} -> {sg['after']['p95']} mm, the piece moved {sg['after']['move_mean']} mm "
                    f"on average (max {sg['after']['move_max']} mm), its far end held on its bone; unchanged otherwise.")
            rep["rewelded"][pid] = dict(base=aid, seam=sg, subject=zit["e"]["subject"])
            if not a.dry:
                B.replace(pid, zn, B.mesh(zit)[1], rec_updates={"procedural_badge": ((zit["e"]["rec"].get("procedural_badge") or "") + note).strip()})
    for aid in failed:
        rep["kept"][aid] = dict(severity=sev[aid], why_not=failed[aid])
    rep["piriformis"] = dict(piriformis_r="not in the Q48 septa volume (xfer_vhm2vhf, never refined to her septa) and above the photographed window: left as is",
                             piriformis_l="same")
    if not a.dry:
        n = B.write(a.out, new_subject_attribution={SUBJECT: ATTRIBUTION})
        print(f"wrote {a.out}: {n} bytes, {len(B.items)} entries (was {n0})")
    Path(a.report).write_text(json.dumps(rep, indent=1, default=str) + "\n")
    print(f"replaced {len(rep['replaced'])}, kept {len(rep['kept'])} [{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    main()
