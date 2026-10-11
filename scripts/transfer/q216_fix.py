#!/usr/bin/env python3
"""Q216: clean up the side effects of Q215 on the OWN FEMALE page (bundle build/viewer_f_hr_q215 -> build/viewer_f_hr_q216).

    python3 scripts/transfer/q216_fix.py [--only id,id] [--phases A,B,C,D,P,W,R] [--dry] [--cache DIR]

  A  NERVE CORRIDOR.  Her photo-traced tibial / sciatic nerve (and the other Q53 / Q55 / Q56 traced tubes) is measured evidence and is NOT moved.  Every Q215 muscle that contains traced-nerve
     vertices (or lies closer than CLEAR_MIN_MM to them) is carved: the muscle solid (exact voxel raster at 0.5 mm of the closed mesh) minus the corridor (nerve + CLEAR_MM) minus the way out of it
     (steepest descent of the muscle's depth field from every corridor voxel to the nearest surface = a groove, not a tunnel), re-meshed (marching cubes of the Gaussian-smoothed solid, one piece, quadric
     decimation to the page's 9000-triangle budget).  Guards: no nerve vertex inside, clearance >= CLEAR_MIN_MM, volume >= VOL_CARVE_MIN of the Q215 mesh, inside skin, bone, one piece.
  B  ISLANDS.  sartorius r = two closed pieces 10.5 mm apart (21 % of the area): the dropped part is far above 2 %, so the pieces are RECONNECTED (convex-hull loft of the two facing 3 mm sections,
     union, re-mesh).  sartorius l = Z-fill continuation pieces whose seam vertices no longer coincide with the re-bounded base (0.25 mm): welded by snapping the seam vertices (W phase).
  C  ENDS.  A muscle end that lies > END_GOAL_MM from every bone (Q204 end test: extreme 8 % along the principal axis of the main piece) is pulled onto the bone its card names as origin / insertion with
     the Q214 attachment-pull code (q214_fit.pull_ends: end zone translated so the closest 10 % of its vertices land on that bone, smooth displacement field), then pushed out of bone, kept inside the skin.
     Cap ATTACH_CAP_MM; farther = not done, reason recorded.
  D  FLAT CUTS.  A planar facet (all vertices within 0.3 mm of an axis-aligned plane at an extreme of the muscle, > 100 mm2) is replaced by a shallow dome (amplitude <= DOME_MAX_MM, profile 1 - (r/rho)^2 over
     the facet, outward where the skin leaves >= 1.2 mm, else inward), checked with the audit's own flat_caps function.
  P  PIRIFORMIS.  No label of her own exists (q216_piriformis.py); the male-carried mesh sits partly off her photographed muscle (share 0.54 r / 0.31 l), so q216_piriformis_refit.py re-bounds it with the Q215
     machinery (markers = the male mesh, region = her photographed muscle, bones / own muscles excluded) and the Q215 guards; candidates that pass (--piriformis PKL) replace the male-carried mesh (Source class unchanged).
  W  WELD.  A Z-fill continuation whose seam vertices no longer coincide with the re-bounded base (sartorius l: 0.25 mm) is snapped onto the base's vertices (<= 1 mm moves) = one connected surface again.
  Guards (all must hold per muscle, else the muscle keeps its Q215 mesh and the reasons are recorded): every vertex inside her skin >= 1 mm; <= 8 % of the vertices inside bone and deepest embedding <= 5 mm on the
  Q204 lattice (or not deeper than the Q215 mesh); volume / length within the bounds of the operation; one connected piece; <= 60 % of the volume inside other muscles (final state, all replacements swapped in)
  and not more than OVERLAP_RISE_MAX points above the Q215 mesh; new surface <= MOVE_P95_MAX_MM (p95) from the Q215 one.
Everything the report does not list stays byte for byte; the Source class (subject key) of every muscle stays as it is."""
from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402
from scripts.transfer import q215_fill as Q15  # noqa: E402
from scripts.transfer import q216_common as C  # noqa: E402
from scripts.transfer.q216_common import SRC_BUNDLE, OUT_BUNDLE  # noqa: E402

CLEAR_MM = 1.0                  # corridor = traced tube + this (mm)
SLOT_EXTRA_MM = 0.8             # the groove is this much wider than the corridor (decimation / smoothing keep the clearance)
CLEAR_MIN_MM = 0.5              # guard: closest nerve vertex to the new muscle surface
VOL_CARVE_MIN = 0.85
BRIDGE_VOL_MAX = 1.35
END_GOAL_MM = 6.0               # Q204: end_off_bone starts above this (distance of the extreme 8 % of the main piece to the nearest bone)
END_PULL_BELOW_MM = 4.5         # an end zone is pulled when its audit distance is above END_GOAL_MM; the pull lands it on the bone (<= 1.5 mm)
ATTACH_CAP_MM = F.ATTACH_CAP_MM
ANY_BONE_FALLBACK_MM = 16.0     # the named bone is out of reach (e.g. an iliotibial tract that ends on the tibia 200 mm away): the nearest bone of any kind within this reach is used and the card says so
END_VOL = (0.88, 1.25)
END_LEN = (0.92, 1.30)
FLAT_AREA_MAX = 90.0            # mm2 per plane key after the dome (the audit's finding threshold is 100)
DOME_MAX_MM = 3.0
FLAT_VOL = (0.96, 1.04)
OVERLAP_MAX = 60.0
OVERLAP_RISE_MAX = 8.0
OVERLAP_LINE = 40.0             # the Q198 / Q204 severity-1 line for muscle_interpenetration: a muscle may not cross it by this operation
MOVE_P95_MAX_MM = 25.0
IN_BONE_MAX_PCT = 8.0
BONE_DEPTH_MAX_MM = 5.0
BONE_DEPTH_TOL_MM = 0.5         # re-meshing (0.5 mm grid, smoothing, decimation) may deepen a seam embedding that the Q215 mesh already had by this much (the Q204 lattice is 2 mm)
SKIN_DEPTH_MIN_MM = 1.0
SEAM_MAX_MM = 2.5

NERVE_TARGETS = None            # filled from the Q215 report (the 27 re-bounded muscles)
# audit names of the ends of the Q215 findings (end_off_bone: 'prox' = low end along the principal axis, as the Q204 audit labels it)
ENDS_TARGETS = {"adductor_longus_l": ["prox"], "adductor_longus_r": ["prox", "dist"], "obturator_internus_l": ["prox"], "sartorius_l": ["prox", "dist"], "tensor_fasciae_latae_l": ["dist"], "vastus_lateralis_l": ["dist"]}
FLAT_TARGETS = ["rectus_femoris_r", "semimembranosus_l", "semitendinosus_l", "tensor_fasciae_latae_r"]
BRIDGE_TARGETS = ["sartorius_r"]
WELD_TARGETS = {"sartorius_l": "sartorius_l_zfill203s"}


# ------------------------------------------------------------------------------------------ helpers
def surf_pts(v, f, spacing=1.0):
    from scripts.zanatomy.q198_core import surf_points
    return surf_points(np.asarray(v, float), np.asarray(f, np.int64), spacing, cap=400000)


def match_ends(ends_a, ends_b):
    """{label in b: label in a} by the closest end centres: the audit's prox / dist names follow the sign of a principal axis, which can flip when a mesh is re-meshed"""
    out = {}
    for eb, xb in ends_b.items():
        out[eb] = min(ends_a, key=lambda ea: float(np.linalg.norm(np.asarray(ends_a[ea]["centre"]) - np.asarray(xb["centre"]))))
    return out


def surface_move(v1, f1, v0, f0):
    """symmetric surface-to-surface distance between two meshes (dense surface samples both ways): median / p95 / max (mm)"""
    p1, p0 = surf_pts(v1, f1, 1.0), surf_pts(v0, f0, 1.0)
    a = cKDTree(p0).query(p1)[0]
    b = cKDTree(p1).query(p0)[0]
    return dict(new_to_old_median_mm=round(float(np.median(a)), 2), new_to_old_p95_mm=round(float(np.percentile(a, 95)), 2), old_to_new_p95_mm=round(float(np.percentile(b, 95)), 2),
                max_mm=round(float(max(a.max(), b.max())), 2))


def nerve_state(nerves, v, f, clear_search=3.0):
    """per traced tube: share of its vertices inside the muscle (ray parity) and the closest approach (mm) of the outside ones to the muscle surface"""
    tm = trimesh.Trimesh(v, f, process=False)
    lo, hi = tm.bounds[0] - clear_search, tm.bounds[1] + clear_search
    out = {}
    pts = surf_pts(v, f, 0.6)
    tree = cKDTree(pts)
    for nid, (nv, _nf) in nerves.items():
        sel = np.flatnonzero(np.all((nv >= lo) & (nv <= hi), axis=1))
        if not len(sel):
            out[nid] = dict(inside=0, inside_pct=0.0, closest_mm=None, n=int(len(nv)))
            continue
        ins = tm.contains(nv[sel])
        d = tree.query(nv[sel])[0]
        out[nid] = dict(inside=int(ins.sum()), inside_pct=round(100.0 * float(ins.sum()) / len(nv), 1), closest_mm=round(float(d[~ins].min()), 2) if (~ins).any() else 0.0, n=int(len(nv)))
    return out


def named_bones(rec):
    out = []
    for key in ("origin", "insertion"):
        m = re.match(r"\s*([a-z0-9_]+)\s*:", rec.get(key) or "")
        out.append(m.group(1) if m else None)
    return out


class Env:
    """Q215 page + everything the operations measure against"""

    def __init__(self, B):
        self.B = B
        self.page = Q15.Page(B)
        self.ctx = self.page.ctx
        self.bone_tree, self.bone_names = C.bone_surface_tree(B)
        self.nerves = {tid: (B.get(tid)["v"], B.get(tid)["f"]) for tid in C.TRACED if B.get(tid) is not None}

    def merged(self, sid, v=None, f=None, weld=True):
        """the Q204 view of a muscle: base + its Z-fill continuation pieces merged (flat base faces under the continuation dropped)"""
        from scripts.zanatomy.q204_paths import merge_zfill
        d = self.B.get(sid)
        bv = d["v"] if v is None else v
        bf = d["f"] if f is None else f
        S = [dict(id=sid, v=bv, f=bf, sys="muscle")]
        for it in self.B.items:
            if re.fullmatch(re.escape(sid) + r"_zfill\w*", it["e"]["id"]):
                vv, ff = self.B.mesh(it)
                if weld and WELD_TARGETS.get(sid) == it["e"]["id"]:            # the weld of the continuation (W phase) is part of the state the ends are measured on
                    vv = snap_zfill(bv, bf, vv, ff)
                S.append(dict(id=it["e"]["id"], v=vv, f=ff, sys="muscle"))
        m = merge_zfill(S)[0]
        return m["v"], m["f"]

    def audit_state(self, sid, v=None, f=None, weld=True):
        mv, mf = self.merged(sid, v, f, weld)
        ends, _ax, _cc = C.audit_ends(mv, mf, self.bone_tree)
        return dict(ends=ends, flat_caps=[dict(axis=c["axis"], plane_mm=c["plane_mm"], area_mm2=c["area_mm2"]) for c in C.flat_cap_rows(mv, mf) if c["area_mm2"] > 40.0],
                    islands=C.island_rows(mv, mf))

    def guards(self, sid, v1, f1, v0, f0, vol_bounds, len_bounds=None, seam=True):
        """metrics + reasons of one candidate against its Q215 mesh"""
        pg = self.page
        g1, g0 = pg.metrics(v1, f1, v0), pg.metrics(v0, f0, v0)
        why = []
        g = dict(before=g0, after=g1)
        g["volume_ratio"] = round(g1["volume_cm3"] / max(g0["volume_cm3"], 1e-6), 3)
        g["length_ratio"] = round(g1["length_mm"] / max(g0["length_mm"], 1e-6), 3)
        g["move"] = surface_move(v1, f1, v0, f0)
        if g1["inside_skin_pct"] < 100.0 or g1["min_skin_depth_mm"] < SKIN_DEPTH_MIN_MM:
            why.append(f"skin: {g1['inside_skin_pct']} % inside, closest {g1['min_skin_depth_mm']} mm")
        if g1["in_bone_pct"] > max(IN_BONE_MAX_PCT, g0["in_bone_pct"]):
            why.append(f"{g1['in_bone_pct']} % of the vertices inside her bone (gate {IN_BONE_MAX_PCT:g} %, Q215 mesh {g0['in_bone_pct']} %)")
        if g1["bone_depth_max_mm"] > max(BONE_DEPTH_MAX_MM, g0["bone_depth_max_mm"] + BONE_DEPTH_TOL_MM):
            why.append(f"embedded {g1['bone_depth_max_mm']} mm in bone (gate {BONE_DEPTH_MAX_MM:g} mm or the Q215 mesh's {g0['bone_depth_max_mm']} mm + {BONE_DEPTH_TOL_MM:g})")
        if not (vol_bounds[0] <= g["volume_ratio"] <= vol_bounds[1]):
            why.append(f"volume x{g['volume_ratio']} of the Q215 mesh (gate {vol_bounds[0]}-{vol_bounds[1]})")
        if len_bounds and not (len_bounds[0] <= g["length_ratio"] <= len_bounds[1]):
            why.append(f"length x{g['length_ratio']} of the Q215 mesh (gate {len_bounds[0]}-{len_bounds[1]})")
        if g1["main_piece"] < min(0.98, g0["main_piece"]) - 1e-9:
            why.append(f"main piece {g1['main_piece']} < {min(0.98, g0['main_piece'])}")
        if g["move"]["new_to_old_p95_mm"] > MOVE_P95_MAX_MM:
            why.append(f"new surface {g['move']['new_to_old_p95_mm']} mm (p95) from the Q215 mesh (gate {MOVE_P95_MAX_MM:g})")
        sg = self.seam_gap(sid, v0, f0, v1, f1) if seam else {}
        if sg:
            g["seam_gap_mm"] = sg
            for zid, x in sg.items():
                if x["p95"] > max(SEAM_MAX_MM, x["p95_before"] + 0.5):
                    why.append(f"the Z-fill continuation {zid} (welded to the Q215 mesh) would be {x['p95']} mm (p95) off the new mesh at the seam (gate {SEAM_MAX_MM:g} mm)")
        return g, why

    def seam_gap(self, sid, v0, f0, v1, f1):
        """gap (mm, p95 / max) between the seam vertices of the Z-fill continuation pieces of `sid` (those lying on the Q215 mesh's surface) and the surface of the new mesh"""
        out = {}
        tm0 = trimesh.Trimesh(v0, f0, process=False)
        tm1 = trimesh.Trimesh(v1, f1, process=False)
        for it in self.B.items:
            zid = it["e"]["id"]
            if re.fullmatch(re.escape(sid) + r"_zfill\w*", zid):
                zv, _zf = self.B.mesh(it)
                S = Q15.seam_vertices(v0, f0, zv)
                if S.sum() < 3:
                    continue
                d1 = trimesh.proximity.closest_point(tm1, zv[S])[1]
                d0 = trimesh.proximity.closest_point(tm0, zv[S])[1]
                out[zid] = dict(seam_vertices=int(S.sum()), p95=round(float(np.percentile(d1, 95)), 2), max=round(float(d1.max()), 2), p95_before=round(float(np.percentile(d0, 95)), 2))
        return out

    def reweld(self, sid, zid, v0, f0, v1, f1):
        """warp a Z-fill continuation piece so that its seam vertices land on the new mesh (Q215's reweld_piece: smooth displacement, far end held) -> (new vertices or None, info, reasons)"""
        zit = self.B.items[self.B.find(zid)[0]]
        zv, zf = self.B.mesh(zit)
        S = Q15.seam_vertices(v0, f0, zv)
        tm1 = trimesh.Trimesh(v1, f1, process=False)
        cp, dn, _ = trimesh.proximity.closest_point(tm1, zv[S])
        zn = Q15.reweld_piece(zv, zf, S, cp)
        d2 = trimesh.proximity.closest_point(tm1, zn[S])[1]
        mv = np.linalg.norm(zn - zv, axis=1)
        flipped, stretched = IB.flipped_pct(zv, zn, zf), IB.stretched_pct(zv, zn, zf) - IB.stretched_pct(zv, zv, zf)
        sk_in, _sk_d = self.ctx.skin_state(zn)
        ins, _, _ = self.ctx.bone_field.inside(zn)
        ins0, _, _ = self.ctx.bone_field.inside(zv)
        info = dict(op="reweld", piece=zid, seam_vertices=int(S.sum()), gap_before=dict(p95=round(float(np.percentile(dn, 95)), 2), max=round(float(dn.max()), 2)),
                    gap_after=dict(p95=round(float(np.percentile(d2, 95)), 2), max=round(float(d2.max()), 2)), move_mean_mm=round(float(mv.mean()), 2), move_max_mm=round(float(mv.max()), 2),
                    flipped_pct=round(flipped, 2), stretched_rise=round(float(stretched), 1), in_bone_pct=[round(100 * float(ins0.mean()), 1), round(100 * float(ins.mean()), 1)], inside_skin_pct=round(sk_in, 1))
        bad = []
        if info["gap_after"]["p95"] > Q15.REWELD_P95_MM:
            bad.append(f"re-weld leaves {info['gap_after']['p95']} mm")
        if info["move_max_mm"] > Q15.REWELD_MAX_MOVE_MM:
            bad.append(f"re-weld moves the continuation {info['move_max_mm']} mm")
        if flipped > 1.0 or stretched > 12.0:
            bad.append(f"re-weld folds {round(flipped, 2)} % / stretches +{round(float(stretched), 1)} points")
        if sk_in < 100.0 or info["in_bone_pct"][1] > info["in_bone_pct"][0] + 2.0:
            bad.append("re-weld puts the continuation outside the skin / into her bone")
        return (zn if not bad else None), info, bad

    def neighbour_crossing(self, ofield, v0, f0, v1, f1):
        """neighbours whose volume overlap crosses the Q198 / Q204 lines 40 / 60 % when the mesh (v0, f0) is replaced by (v1, f1): [(id, before, after)]"""
        base = {}
        for mid, w in ofield.groups.items():
            base[mid] = round(100.0 * float((ofield.cnt[tuple(w.T)] > 1).mean()), 1)
        h0 = {m: a for m, _b, a in ofield.harm(v0, f0)}
        h1 = {m: a for m, _b, a in ofield.harm(v1, f1)}
        out = []
        for m in base:
            a0, a1 = h0.get(m, base[m]), h1.get(m, base[m])
            for line in (OVERLAP_LINE, OVERLAP_MAX):
                if a1 > line >= a0:
                    out.append((m, a0, a1))
                    break
        return out


# ------------------------------------------------------------------------------------------ A: nerve corridor
def op_carve(env, sid, v0, f0, log=print):
    B = env.B
    nmeshes = list(env.nerves.values())
    grid = C.VoxGrid(v0.min(0) - 4.0, v0.max(0) + 4.0, C.H)
    mask = C.VoxGrid.solid(grid, v0, f0)
    cor = C.corridor_mask(grid, nmeshes, CLEAR_MM)
    inside = int((cor & mask).sum())
    new, ch, dropped = C.carve_channel(mask, grid, cor, SLOT_EXTRA_MM)
    vol_mask = C.mask_volume_cm3(mask)
    v1, f1 = C.mask_to_mesh(new, grid, sigma_vox=0.8, budget=Q15.BUDGET)
    info = dict(op="nerve_corridor", corridor_voxels_in_muscle_cm3=round(inside * C.H ** 3 / 1000.0, 2), removed_cm3=round(vol_mask - C.mask_volume_cm3(new), 2), dropped_fragment_fraction=round(dropped, 4),
                clearance_mm=CLEAR_MM, groove_extra_mm=SLOT_EXTRA_MM)
    return v1, f1, info


def nerve_need(env, sid, v0, f0):
    st = nerve_state(env.nerves, v0, f0)
    need = [k for k, x in st.items() if x["inside"] > 0 or (x["closest_mm"] is not None and x["closest_mm"] < CLEAR_MIN_MM)]
    return st, need


# ------------------------------------------------------------------------------------------ B: bridge
def op_bridge(env, sid, v0, f0, log=print):
    tm = trimesh.Trimesh(v0, f0, process=False)
    parts = sorted(tm.split(only_watertight=False), key=lambda p: -len(p.faces))
    assert len(parts) == 2, len(parts)
    big, small = parts
    # facing end of each part: the vertices of one part nearest to the other part
    d, i = cKDTree(big.vertices).query(small.vertices)
    j = int(np.argmin(d))
    a_pt, b_pt = small.vertices[j], big.vertices[i[j]]
    ax = (b_pt - a_pt) / np.linalg.norm(b_pt - a_pt)
    ta = (small.vertices - a_pt) @ ax
    tb = (big.vertices - b_pt) @ ax
    sec_a = small.vertices[ta >= -3.0]                     # the small part's end section (3 mm) facing the big one
    sec_b = big.vertices[tb <= 3.0]                       # and the big part's
    hull = trimesh.convex.convex_hull(np.vstack([sec_a, sec_b]))
    grid = C.VoxGrid(v0.min(0) - 4.0, v0.max(0) + 4.0, C.H)
    m = C.VoxGrid.solid(grid, v0, f0)
    ii = np.argwhere(np.ones(tuple(np.minimum(grid.idx(hull.bounds[1] + 1) + 1, grid.shape) - np.maximum(grid.idx(hull.bounds[0] - 1), 0)), bool)) + np.maximum(grid.idx(hull.bounds[0] - 1), 0)
    hm = np.zeros(grid.shape, bool)
    hm[tuple(ii[hull.contains(grid.pos(ii))].T)] = True
    new = m | hm
    from scipy import ndimage as ndi
    lab, n = ndi.label(new, structure=np.ones((3, 3, 3)))
    v1, f1 = C.mask_to_mesh(new, grid, sigma_vox=0.8, budget=Q15.BUDGET)
    info = dict(op="bridge", gap_mm=round(float(d.min()), 2), pieces_before=2, bridge_added_cm3=round(C.mask_volume_cm3(new) - C.mask_volume_cm3(m), 2), small_part_cm3=round(abs(parts[1].volume) / 1000.0, 2),
                small_part_area_share=round(float(small.area / (small.area + big.area)), 3), connected_components_voxels=int(n))
    return v1, f1, info


# ------------------------------------------------------------------------------------------ C: ends
def pull_anchored(v, f, pulls, anchors, lam=8.0, w=30.0, w_anchor=300.0):
    """q214_fit.pull_ends with (a) the other end zones ANCHORED (zero displacement, weight w_anchor): the muscle is stretched between them instead of translated, and (b) an optional stop-short distance for a
    pull towards 'the nearest bone of any kind' (the end is brought to within `short` mm of it, not onto it).  pulls = [(zone mask, target points, short_mm)] -> (new vertices or None, per-zone info)"""
    from scipy.sparse import diags, identity
    from scipy.sparse.linalg import spsolve
    n = len(v)
    Lap = IB.laplacian(n, f)
    W = np.zeros(n)
    P = np.zeros((n, 3))
    info = []
    for zone, tgt, short in pulls:
        tree = cKDTree(tgt)
        d0 = tree.query(v[zone])[0]
        idx = np.argsort(d0)[: max(3, int(0.10 * len(d0)))]
        vz = v[zone]
        step = (tgt[tree.query(vz[idx])[1]] - vz[idx]).mean(axis=0)
        L = float(np.linalg.norm(step))
        inf = dict(dist_before_p5=float(np.percentile(d0, 5)), step_mm=L, stop_short_mm=short)
        if L > ATTACH_CAP_MM:
            inf["refused"] = True
            info.append(inf)
            return None, info
        if short > 0:
            step = step * (max(L - short, 0.0) / max(L, 1e-9))
        elif float(np.percentile(d0, 5)) <= 1.5:
            step = np.zeros(3)
        inf["applied_mm"] = float(np.linalg.norm(step))
        info.append(inf)
        W[zone] = w
        P[zone] = step
    for z in anchors:
        W[z & (W == 0)] = w_anchor
    M = (diags(W) + lam * Lap + 1e-3 * identity(n)).tocsc()
    D = np.column_stack([spsolve(M, W * P[:, k]) for k in range(3)])
    return v + D, info


def zones_of(v0, mode):
    """end zones of a muscle mesh: 'count12' = the 12 % of the vertices at each end of the principal axis (q214_fit.axis_and_zones); 'len10' = the vertices within 10 % of the LENGTH from each extreme (what the audit's end
    test looks at: a thin tail has few vertices, so the count rule puts most of the belly into the zone)"""
    if mode == "count12":
        u, t, z_lo, z_hi = F.axis_and_zones(v0)
        return {"lo": z_lo, "hi": z_hi}
    c = v0.mean(0)
    u = np.linalg.svd(v0 - c, full_matrices=False)[2][0]
    t = (v0 - c) @ u
    L = float(t.max() - t.min())
    lo, hi = t <= t.min() + 0.10 * L, t >= t.max() - 0.10 * L
    if lo.sum() < 12:
        lo = t <= np.sort(t)[11]
    if hi.sum() < 12:
        hi = t >= np.sort(t)[-12]
    return {"lo": lo, "hi": hi}


def op_ends(env, sid, which, v0, f0, log=print, modes=("count12", "len10")):
    """pull the listed ends onto their bones: end zones by vertex count first (Q214's rule), by length second; the first mode whose best variant passes every guard wins"""
    best = None
    for mode in modes:
        r = _op_ends(env, sid, which, v0, f0, log, mode)
        v1, _f1, inf = r
        inf["zone_mode"] = mode
        if v1 is not None and not inf.get("why"):
            return r
        if best is None or (v1 is not None and (best[0] is None or len(inf.get("why", [])) < len(best[2].get("why", [])))):
            best = r
    return best


def _op_ends(env, sid, which, v0, f0, log, zone_mode):
    ctx, B = env.ctx, env.B
    rec = B.get(sid)["e"]["rec"]
    nb = named_bones(rec)
    st = env.audit_state(sid, v0, f0)
    info = dict(op="ends", before=st["ends"], named_bones=nb, pulled={}, skipped={}, which=list(which))
    zones = zones_of(v0, zone_mode)

    def zone_of(centre):
        return min(zones, key=lambda k: np.linalg.norm(v0[zones[k]].mean(0) - np.asarray(centre)))
    todo = [(zone_of(a["centre"]), en, a) for en, a in st["ends"].items() if en in which and a["min_any_bone_mm"] > END_GOAL_MM]
    if not todo:
        info["skipped"]["all"] = "no listed end above the gate"
        return None, None, info
    zt, pulled_en = [], set()
    for zk, en, a in todo:
        best = None
        for bid in [b for b in nb if b]:
            Pb = ctx.bone_pts(rf"^{re.escape(bid)}$")
            if not len(Pb):
                continue
            dd = cKDTree(Pb).query(v0[zones[zk]])[0]
            if best is None or np.percentile(dd, 5) < best[0]:
                best = (float(np.percentile(dd, 5)), bid, Pb)
        used = None
        if best is not None:
            pv, inf = pull_anchored(v0, f0, [(zones[zk], best[2], 0.0)], [])
            if pv is not None:
                used = (best[1], best[2], 0.0, inf[0], True)
            else:
                info["skipped"][en] = f"the named bone {best[1]} is {inf[0]['step_mm']:.0f} mm away (cap {ATTACH_CAP_MM:g} mm)"
        if used is None:
            Pall = np.vstack([vb for vb, _f in ctx.bones.values()])
            pv, inf = pull_anchored(v0, f0, [(zones[zk], Pall, 4.0)], [])
            if pv is not None and inf[0]["step_mm"] <= ANY_BONE_FALLBACK_MM:
                used = ("nearest bone of any kind (to within 4 mm; the named insertion is not on a bone within reach)", Pall, 4.0, inf[0], False)
                info["skipped"].pop(en, None)
            else:
                info["skipped"].setdefault(en, f"no bone within reach (nearest {inf[0]['step_mm']:.0f} mm)")
        if used is not None:
            zt.append((zones[zk], used[1], used[2], used[4]))
            pulled_en.add(en)
            info["pulled"][en] = dict(bone=used[0], step_mm=round(used[3]["step_mm"], 2), applied_mm=round(used[3].get("applied_mm", 0.0), 2), dist_before_p5_mm=round(used[3]["dist_before_p5"], 2), audit_before_mm=a["min_any_bone_mm"])
    if not zt:
        return None, None, info
    ends = np.zeros(len(v0), bool)
    for z, _t, _s, _n in zt:
        ends |= z
    anchors = [z for k, z in zones.items() if not any((z == zz).all() for zz, _t, _s, _n in zt)]
    # the seam vertices of a Z-fill continuation (base vertices within 1.5 mm of one of its vertices) are anchored too: the continuation stays welded
    for it in B.items:
        if re.fullmatch(re.escape(sid) + r"_zfill\w*", it["e"]["id"]):
            zv_, _zf_ = B.mesh(it)
            seam = cKDTree(zv_).query(v0)[0] <= 1.5
            if seam.any():
                anchors.append(seam)
    from scripts.transfer.q200_overlap import separate
    skip = [sid] + [it["e"]["id"] for it in B.items if re.fullmatch(re.escape(sid) + r"_zfill\w*", it["e"]["id"])]
    ends_all = ends.copy()                              # pulled zones + the other end + the seam of a continuation: held on / in their bone by the bone push (an embedding that the Q215 mesh has by design stays)
    for z in anchors:
        ends_all |= z
    depth0 = float(ctx.bone_depth().depth(v0).max())
    ofield = F.OverlapField(ctx, skip_ids=skip)
    o_old = ofield.pct(v0, f0)
    info["overlap_old_pct"] = round(o_old, 1)
    lo_b, hi_b = v0.min(0) - 14.0, v0.max(0) + 14.0
    others = [m for k, m in ctx.muscle_overlap.tm.items() if k.split("#")[0] not in set(skip) and not ((m.bounds[1] < lo_b).any() or (m.bounds[0] > hi_b).any())]
    best = None
    variants = [(short, lam, lams, sep) for short in (0.0, 3.0, 5.0) for lam in (8.0, 40.0) for lams in F.LAMS[:1] for sep in (None, (3, 4.0), (6, 6.0), F.SEPARATION[0])]
    for short, lam, lams, sep in variants:
        # a pull onto the NAMED bone lands on it (short = 0); when that crowds a neighbour the end is brought to within `short` mm of it instead (still inside the audit's 6 mm)
        zt_v = [(z, t, (max(s0, short) if named else s0)) for z, t, s0, named in zt]
        if short > 0 and not any(named for _z, _t, _s, named in zt):
            continue
        cur = v0
        for _pass in range(3):                           # a second / third pass pulls what the first one left (the zone moves by the mean step of its closest vertices, a thin tail needs more)
            pv, _ = pull_anchored(cur, f0, zt_v, anchors, lam=lam)
            nxt = F.bone_push(v0, f0, ctx, pv, ends_all, lams)
            if sep is not None:
                constrain = lambda x, lams=lams: F.bone_push(v0, f0, ctx, x, ends_all, lams)
                nxt, _si = separate(nxt, f0, others, constrain=constrain, pin=ends_all, rounds=sep[0], step=0.7, per_round=3.0, total=sep[1], vol=(0.75, 1.3))
            nxt = F.smooth_displacement(v0, nxt, f0, 8)
            nxt = ctx.skin_inset(nxt)
            nxt = F.bone_push(v0, f0, ctx, nxt, ends_all, lams)
            if depth0 <= F.BONE_CLAMP_MM:
                nxt = F.shallow_bone_clamp(v0, f0, ctx, nxt)
            cur = nxt
            stc = env.audit_state(sid, cur, f0)["ends"]
            mtc = match_ends(stc, st["ends"])
            if max(stc[mtc[en]]["min_any_bone_mm"] for en in pulled_en) <= END_GOAL_MM - 1.0:
                break
        g, why = env.guards(sid, cur, f0, v0, f0, END_VOL, END_LEN, seam=False)
        st1 = env.audit_state(sid, cur, f0)
        mt0 = match_ends(st1["ends"], st["ends"])                      # pulled ends: their labels in the new state
        worst = max(st1["ends"][mt0[en]]["min_any_bone_mm"] for en in pulled_en)
        if worst > END_GOAL_MM:
            why = why + [f"an end is still {worst} mm from bone after the pull (gate {END_GOAL_MM:g})"]
        mt = match_ends(st["ends"], st1["ends"])
        for en, a in st1["ends"].items():                 # an end that was not pulled must not leave its bone
            b0 = st["ends"][mt[en]]["min_any_bone_mm"]
            if mt[en] not in pulled_en and a["min_any_bone_mm"] > max(b0 + 1.0, END_GOAL_MM):
                why = why + [f"the {en} end moved off its bone ({b0} -> {a['min_any_bone_mm']} mm)"]
        o_new = ofield.pct(cur, f0)
        g["overlap_field_pct"] = [round(o_old, 1), round(o_new, 1)]
        if o_new > OVERLAP_MAX or (o_new > OVERLAP_LINE and o_new > o_old + OVERLAP_RISE_MAX):
            why = why + [f"{round(o_new, 1)} % of its volume inside the other muscles (Q215 mesh {round(o_old, 1)} %)"]
        cross = env.neighbour_crossing(ofield, v0, f0, cur, f0)
        if cross:
            why = why + [f"it pushes {', '.join(f'{m} {a0} -> {a1} %' for m, a0, a1 in cross)} across the {OVERLAP_LINE:g} / {OVERLAP_MAX:g} % overlap line"]
        g["neighbours_crossing_line"] = [list(x) for x in cross]
        zfill_new = {}
        for zid, x in env.seam_gap(sid, v0, f0, cur, f0).items():
            if x["p95"] > max(SEAM_MAX_MM, x["p95_before"] + 0.5):
                zn, rinfo, bad = env.reweld(sid, zid, v0, f0, cur, f0)
                if bad:
                    why = why + [f"the Z-fill continuation {zid} would be {x['p95']} mm off the new mesh at the seam and cannot be re-welded: {'; '.join(bad)}"]
                else:
                    zfill_new[zid] = (zn, rinfo)
            g.setdefault("seam_gap_mm", {})[zid] = x
        key = (len(why), worst, o_new)
        log(f"      [{zone_mode}] pull short {short} lam {lam} sep {sep}: ends {[(e, a['min_any_bone_mm']) for e, a in st1['ends'].items()]}, vol x{g['volume_ratio']}, len x{g['length_ratio']}, overlap {round(o_old, 1)} -> {round(o_new, 1)}, bone {g['after']['in_bone_pct']} %, {why or 'ok'}")
        if best is None or key < best[0]:
            best = (key, cur, g, why, st1, lam, lams, sep, zfill_new, short)
        if not why:
            break
    _, cur, g, why, st1, lam, lams, sep, zfill_new, short = best
    info.update(after=st1["ends"], variant=dict(pull_lam=lam, bone_chain=list(lams), separation=list(sep) if sep else None, stop_short_mm=short), zfill_reweld={z: ri for z, (zn, ri) in zfill_new.items()})
    return cur, f0, dict(info, guards=g, why=why, zfill_new=zfill_new)


# ------------------------------------------------------------------------------------------ D: flat caps
def cap_triangles(v, f, tol=0.3):
    """axis-aligned flat triangles grouped by plane key, as the audit's flat_caps groups them -> {(axis, key): (triangle indices, plane pos, outward sign)}"""
    vf = v[f]
    nrm = np.cross(vf[:, 1] - vf[:, 0], vf[:, 2] - vf[:, 0])
    ar = 0.5 * np.linalg.norm(nrm, axis=1)
    nrm /= np.maximum(2 * ar[:, None], 1e-9)
    out = {}
    for k in range(3):
        fk = (np.abs(nrm[:, k]) > 0.95) & ((vf[:, :, k].max(1) - vf[:, :, k].min(1)) < tol)
        if not fk.any():
            continue
        pc = vf[fk][:, :, k].mean(1)
        key = np.round(pc / 0.5).astype(int)
        idx = np.flatnonzero(fk)
        for kk in np.unique(key):
            m = key == kk
            out[(k, int(kk))] = (idx[m], float(pc[m].mean()), float(np.sign(nrm[idx[m]][:, k]).mean()), float(ar[idx[m]].sum()))
    return out


def op_flat(env, sid, v0, f0, log=print):
    ctx = env.ctx
    st = env.audit_state(sid, v0, f0)
    caps = [c for c in st["flat_caps"] if c["area_mm2"] > FLAT_AREA_MAX]
    info = dict(op="flat_cut", before=st["flat_caps"], dome=[])
    if not caps:
        return None, None, dict(info, why=["no cap above the threshold"])
    groups = cap_triangles(v0, f0)
    best = None
    for amp in (1.2, 1.6, 2.0, 2.5, DOME_MAX_MM):
        cur = v0.copy()
        dome = []
        ext = (v0.min(0), v0.max(0))
        for (k, kk), (tri, pos, sgn, area) in groups.items():
            # only what the audit calls a flat CUT face: a facet whose plane lies at an extreme of the muscle along its axis (q198_core.flat_caps: within 1.5 mm; the x = 0 midline is not a cut)
            if area <= 40.0 or not (abs(pos - ext[0][k]) < 1.5 or abs(pos - ext[1][k]) < 1.5) or ("xyz"[k] == "x" and abs(pos) < 15.0):
                continue
            vi = np.unique(f0[tri])
            c = v0[vi].mean(0)
            o = [a for a in range(3) if a != k]
            r = np.linalg.norm(v0[vi][:, o] - c[o], axis=1)
            rho = max(1.25 * float(r.max()), 4.0)
            prof = np.clip(1.0 - (r / rho) ** 2, 0.0, None)
            # outward (sgn) where the skin leaves room, else inward
            trial = v0[vi].copy()
            trial[:, k] += sgn * amp * prof
            sk_in, sk_d = ctx.skin_state(trial)
            direction = sgn if (sk_in >= 100.0 and sk_d >= 1.2 + 0.2) else -sgn
            cur[vi, k] += direction * amp * prof
            dome.append(dict(axis="xyz"[k], plane_mm=round(pos, 1), area_mm2=round(area, 1), amplitude_mm=amp, outward=bool(direction == sgn), vertices=int(len(vi)), radius_mm=round(rho, 1)))
        cur = F.smooth_displacement(v0, cur, f0, 2)
        cur = ctx.skin_inset(cur)
        g, why = env.guards(sid, cur, f0, v0, f0, FLAT_VOL)
        st1 = env.audit_state(sid, cur, f0)
        left = [c for c in st1["flat_caps"] if c["area_mm2"] > FLAT_AREA_MAX]
        if left:
            why = why + [f"{len(left)} flat cap(s) still above {FLAT_AREA_MAX:g} mm2 at amplitude {amp}"]
        log(f"      dome amp {amp}: caps left {[c['area_mm2'] for c in st1['flat_caps']]}, vol x{g['volume_ratio']}, {why or 'ok'}")
        if best is None or (len(why), amp) < (len(best[3]), best[4]):
            best = (cur, g, dome, why, amp, st1)
        if not why:
            break
    cur, g, dome, why, amp, st1 = best
    return cur, f0, dict(info, dome=dome, after=st1["flat_caps"], amplitude_mm=amp, guards=g, why=why)


# ------------------------------------------------------------------------------------------ W: weld of a Z-fill continuation
def snap_zfill(bv, bf, zv, zfc, info=None):
    """snap the vertices of a Z-fill continuation that lie within 1 mm of the base's vertices onto them, then chain its sub-pieces onto the connected component (vertices within 0.6 mm of it) -> new vertices"""
    from scripts.zanatomy.q198_core import weld, islands
    zv = zv.copy()
    tb = cKDTree(bv)
    d, i = tb.query(zv)
    sel = d <= 1.0
    zv[sel] = bv[i[sel]]
    n_piece = 0
    for _ in range(3):
        vw, fw = weld(np.vstack([bv, zv]), np.vstack([bf, zfc + len(bv)]))
        isl = islands(vw, fw)
        if len(isl) == 1:
            break
        main = vw[isl[0]["vidx"]]
        dd, ii = cKDTree(main).query(zv)
        m2 = (dd > 0.02) & (dd <= 0.6)
        zv[m2] = main[ii[m2]]
        n_piece += int(m2.sum())
    if info is not None:
        info["snapped_to_base"] = int(sel.sum())
        info["snap_mean_mm"] = round(float(d[sel].mean()), 2) if sel.any() else None
        info["snapped_to_piece"] = n_piece
    return zv


def op_weld(env, sid, zid, base_vf=None, log=print):
    B = env.B
    base = B.get(sid)
    bv, bf = (base["v"], base["f"]) if base_vf is None else base_vf
    zf = B.get(zid)
    info = dict(op="weld", piece=zid)
    zv = snap_zfill(bv, bf, zf["v"], zf["f"], info)
    return zv, zf["f"], info


# ------------------------------------------------------------------------------------------ the run
def badge_add(old, text):
    return ((old or "").rstrip() + " " + text).strip()


def fmt_nerve(st):
    return ", ".join(f"{k} {x['inside_pct']} %" for k, x in st.items() if x["inside"] > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC_BUNDLE))
    ap.add_argument("--out", default=str(OUT_BUNDLE))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q216_report.json"))
    ap.add_argument("--only", default="")
    ap.add_argument("--phases", default="A,B,C,D,P,W,R")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--cache", default="")
    ap.add_argument("--piriformis", default="", help="pickle written by q216_piriformis_refit.py (candidate meshes of piriformis r / l re-bounded on her registered photographs)")
    a = ap.parse_args()
    only = [x for x in a.only.split(",") if x]
    phases = a.phases.split(",")
    t0 = time.time()
    B = Bundle(a.src)
    n0 = len(B.items)
    env = Env(B)
    log = lambda *x: print(*x, flush=True)
    log(f"context ready [{time.time() - t0:.0f} s]")
    q15 = json.loads((REPO / "data/derived/Q215_report.json").read_text())
    targets = sorted(q15["replaced"])
    cache = Path(a.cache) if a.cache else None
    if cache:
        cache.mkdir(parents=True, exist_ok=True)
    cand = {}          # sid -> dict(v, f, ops: [info...], badge: [text...])
    rep = dict(source_bundle=str(Path(a.src).relative_to(REPO)), nerve={}, ops={}, kept={}, attempts={}, residual={}, welded={}, piriformis={}, params=dict(
        CLEAR_MM=CLEAR_MM, SLOT_EXTRA_MM=SLOT_EXTRA_MM, CLEAR_MIN_MM=CLEAR_MIN_MM, VOL_CARVE_MIN=VOL_CARVE_MIN, END_GOAL_MM=END_GOAL_MM, ATTACH_CAP_MM=ATTACH_CAP_MM, ANY_BONE_FALLBACK_MM=ANY_BONE_FALLBACK_MM,
        END_VOL=END_VOL, END_LEN=END_LEN, FLAT_AREA_MAX=FLAT_AREA_MAX, DOME_MAX_MM=DOME_MAX_MM, FLAT_VOL=FLAT_VOL, OVERLAP_MAX=OVERLAP_MAX, OVERLAP_RISE_MAX=OVERLAP_RISE_MAX, MOVE_P95_MAX_MM=MOVE_P95_MAX_MM,
        IN_BONE_MAX_PCT=IN_BONE_MAX_PCT, BONE_DEPTH_MAX_MM=BONE_DEPTH_MAX_MM, BONE_DEPTH_TOL_MM=BONE_DEPTH_TOL_MM, SKIN_DEPTH_MIN_MM=SKIN_DEPTH_MIN_MM, H=C.H))

    def cur_mesh(sid):
        return (cand[sid]["v"], cand[sid]["f"]) if sid in cand else B.mesh(B.items[B.find(sid)[0]])

    def want(sid):
        return not only or sid in only

    def record(sid, v, f, info, kind):
        c = cand.setdefault(sid, dict(ops=[], v=None, f=None))
        c["v"], c["f"] = v, f
        c["ops"].append(dict(info, kind=kind))

    def cached(key, fn):
        if cache and (cache / f"{key}.pkl").exists():
            return pickle.loads((cache / f"{key}.pkl").read_bytes())
        r = fn()
        if cache:
            (cache / f"{key}.pkl").write_bytes(pickle.dumps(r))
        return r

    # ---- A
    if "A" in phases:
        for sid in targets:
            if not want(sid):
                continue
            v0, f0 = cur_mesh(sid)
            st, need = nerve_need(env, sid, v0, f0)
            rep["nerve"][sid] = dict(before=st, needs=need)
            if not need:
                continue
            log(f"A {sid}: nerve overlap {fmt_nerve(st)} (closest outside: { {k: x['closest_mm'] for k, x in st.items() if x['closest_mm'] is not None and x['closest_mm'] < 3} })")
            t1 = time.time()
            v1, f1, inf = cached(f"A_{sid}", lambda: op_carve(env, sid, v0, f0, log))
            g, why = env.guards(sid, v1, f1, v0, f0, (VOL_CARVE_MIN, 1.0 + 0.01))
            st1 = nerve_state(env.nerves, v1, f1)
            inside_after = sum(x["inside"] for x in st1.values())
            closest = min([x["closest_mm"] for x in st1.values() if x["closest_mm"] is not None] or [99.0])
            if inside_after:
                why.append(f"{inside_after} nerve vertices still inside")
            if closest < CLEAR_MIN_MM:
                why.append(f"closest nerve vertex {closest} mm from the surface (gate {CLEAR_MIN_MM})")
            rep["nerve"][sid].update(after=st1, closest_after_mm=closest)
            log(f"   -> vol {g['before']['volume_cm3']} -> {g['after']['volume_cm3']} cm3 (x{g['volume_ratio']}), nerve inside after {inside_after}, closest {closest} mm, move p95 {g['move']['new_to_old_p95_mm']}, {why or 'ok'}  [{time.time() - t1:.0f} s]")
            if why:
                rep["kept"].setdefault(sid, {})["nerve_corridor"] = why
            else:
                record(sid, v1, f1, dict(inf, guards=g, nerve_before=st, nerve_after=st1, closest_nerve_mm=closest), "A")
    # ---- B
    if "B" in phases:
        for sid in BRIDGE_TARGETS:
            if not want(sid):
                continue
            v0, f0 = cur_mesh(sid)
            log(f"B {sid}")
            v1, f1, inf = cached(f"B_{sid}", lambda: op_bridge(env, sid, v0, f0, log))
            g, why = env.guards(sid, v1, f1, v0, f0, (1.0, BRIDGE_VOL_MAX))
            st1 = env.audit_state(sid, v1, f1)
            if st1["islands"] and max(i["gap_mm"] for i in st1["islands"]) > 5.0:
                why.append(f"still an island {max(i['gap_mm'] for i in st1['islands'])} mm away")
            tm1 = trimesh.Trimesh(v1, f1, process=False)
            if len(tm1.split(only_watertight=False)) != 1:
                why.append("more than one surface piece")
            log(f"   -> vol {g['before']['volume_cm3']} -> {g['after']['volume_cm3']}, islands after {st1['islands']}, {why or 'ok'}")
            if why:
                rep["kept"].setdefault(sid, {})["bridge"] = why
            else:
                record(sid, v1, f1, dict(inf, guards=g, after=st1), "B")
    # ---- C
    if "C" in phases:
        for sid in ENDS_TARGETS:
            if not want(sid):
                continue
            v0, f0 = cur_mesh(sid)
            log(f"C {sid}")
            v1, f1, inf = cached(f"C_{sid}", lambda: op_ends(env, sid, ENDS_TARGETS[sid], v0, f0, log))
            if v1 is None:
                rep["kept"].setdefault(sid, {})["ends"] = inf.get("skipped") or inf.get("why")
                rep["attempts"].setdefault(sid, []).append(inf)
                continue
            why = inf.pop("why", [])
            zfn = inf.pop("zfill_new", {})
            log(f"   -> pulled {inf['pulled']} skipped {inf['skipped']} -> ends now {inf['after']} {why or 'ok'}")
            if why:
                rep["kept"].setdefault(sid, {})["ends"] = why
                rep["attempts"].setdefault(sid, []).append(dict(inf, why=why))
            else:
                record(sid, v1, f1, inf, "C")
                cand[sid]["zfill_new"] = zfn
    # ---- D
    if "D" in phases:
        for sid in FLAT_TARGETS:
            if not want(sid):
                continue
            v0, f0 = cur_mesh(sid)
            log(f"D {sid}")
            v1, f1, inf = cached(f"D_{sid}_{'carved' if sid in cand else 'plain'}", lambda: op_flat(env, sid, v0, f0, log))
            if v1 is None:
                rep["kept"].setdefault(sid, {})["flat_cut"] = inf.get("why")
                continue
            why = inf.pop("why", [])
            if why:
                rep["kept"].setdefault(sid, {})["flat_cut"] = why
                rep["attempts"].setdefault(sid, []).append(dict(inf, why=why))
            else:
                record(sid, v1, f1, inf, "D")
    # ---- P: piriformis (re-bounded on her registered photographs by q216_piriformis_refit.py with the Q215 machinery and guards)
    pir_sides = {}
    if "P" in phases and a.piriformis:
        res = pickle.loads(Path(a.piriformis).read_bytes())
        for sid, r in res.items():
            if not want(sid):
                continue
            v0, f0 = cur_mesh(sid)
            why = list(r.get("why") or [])
            if "v" not in r:
                pir_sides[sid] = dict(decision="left", reasons=why or ["empty label"], ev_base=r.get("ev_base"), ev_new=r.get("ev_new"))
                rep["kept"].setdefault(sid, {})["piriformis_refit"] = why or ["empty label"]
                continue
            g2, why2 = env.guards(sid, r["v"], r["f"], v0, f0, (0.25, 1.01), (0.7, 1.3))
            why = [w for w in why] + [w for w in why2 if not w.startswith("volume") and not w.startswith("length")]
            q15g = {k: v for k, v in r["guards"].items() if k not in ("before", "after", "zfill_new")}
            pir_sides[sid] = dict(decision="left" if why else "refit", reasons=why, ev_base=r["ev_base"], ev_new=r["ev_new"], q215_guards=q15g, voxels=r.get("voxels"), notes=r.get("notes"))
            log(f"P {sid}: {'KEPT ' + str(why) if why else 'refit ok'}  vol {g2['before']['volume_cm3']} -> {g2['after']['volume_cm3']}")
            if why:
                rep["kept"].setdefault(sid, {})["piriformis_refit"] = why
            else:
                record(sid, r["v"], r["f"], dict(op="piriformis_refit", guards=g2, ev=[r["ev_base"], r["ev_new"]], q215_guards=q15g, voxels=r.get("voxels"), notes=r.get("notes")), "P")
    # ---- W
    welds = {}
    if "W" in phases:
        for sid, zid in WELD_TARGETS.items():
            if not want(sid):
                continue
            log(f"W {zid}")
            bv_, bf_ = cur_mesh(sid)
            zv, zf_, inf = op_weld(env, sid, zid, (bv_, bf_), log)
            st0 = env.audit_state(sid, bv_, bf_, weld=False)
            # state after: merged view with the welded continuation
            from scripts.zanatomy.q204_paths import merge_zfill
            S = [dict(id=sid, v=bv_, f=bf_, sys="muscle"), dict(id=zid, v=zv, f=zf_, sys="muscle")]
            m = merge_zfill(S)[0]
            ends, _ax, _cc = C.audit_ends(m["v"], m["f"], env.bone_tree)
            isl = C.island_rows(m["v"], m["f"])
            inf.update(islands_before=st0["islands"], islands_after=isl, ends_before=st0["ends"], ends_after=ends)
            mv = np.linalg.norm(zv - B.get(zid)["v"], axis=1)
            inf["moved_vertices"] = int((mv > 0).sum())
            inf["move_max_mm"] = round(float(mv.max()), 2)
            sk_in, sk_d = env.ctx.skin_state(zv)
            inf["inside_skin_pct"] = round(sk_in, 2)
            why = []
            if isl:
                why.append(f"{len(isl)} islands remain after the weld: {isl}")
            if inf["move_max_mm"] > 1.0:
                why.append(f"a continuation vertex moved {inf['move_max_mm']} mm (gate 1.0)")
            log(f"   -> islands {st0['islands']} -> {isl}; ends {st0['ends']} -> {ends}; max move {inf['move_max_mm']} {why or 'ok'}")
            if why:
                rep["kept"].setdefault(zid, {})["weld"] = why
            else:
                welds[zid] = (zv, zf_, inf, sid)
    # ---- R: side effects of the operations themselves (a carve / re-mesh can shorten a thin tail, decimation can leave a planar facet): an end that crossed the 6 mm line or a flat facet that was not there before is
    # repaired with the same code (C / D); what cannot be repaired is recorded as residual, the candidate is kept (the nerve fix has priority over a severity-1 end finding)
    if "R" in phases:
        for sid in list(cand):
            if not want(sid):
                continue
            it0 = B.items[B.find(sid)[0]]
            v0, f0 = B.mesh(it0)
            st0 = env.audit_state(sid, v0, f0)
            v1, f1 = cur_mesh(sid)
            st1 = env.audit_state(sid, v1, f1)
            mt = match_ends(st0["ends"], st1["ends"])
            worse = [en for en, a in st1["ends"].items() if a["min_any_bone_mm"] > END_GOAL_MM and st0["ends"][mt[en]]["min_any_bone_mm"] <= END_GOAL_MM]
            if worse:
                log(f"R {sid}: end(s) {worse} crossed the {END_GOAL_MM:g} mm line ({ {en: (st0['ends'][mt[en]]['min_any_bone_mm'], st1['ends'][en]['min_any_bone_mm']) for en in worse} })")
                v2, f2, inf = op_ends(env, sid, worse, v1, f1, log, modes=("len10", "count12"))
                if v2 is not None and not inf.get("why"):
                    zfn = inf.pop("zfill_new", {})
                    inf.pop("why", None)
                    record(sid, v2, f2, dict(inf, repair=True), "C")
                    cand[sid]["zfill_new"] = {**cand[sid].get("zfill_new", {}), **zfn}
                    v1, f1 = v2, f2
                else:
                    rep["residual"].setdefault(sid, []).append(dict(what="end_off_bone", ends=worse, why=(inf or {}).get("why") or (inf or {}).get("skipped")))
            caps0 = [c for c in st0["flat_caps"] if c["area_mm2"] > FLAT_AREA_MAX]
            st1 = env.audit_state(sid, v1, f1)
            new_caps = [c for c in st1["flat_caps"] if c["area_mm2"] > FLAT_AREA_MAX and not any(c["axis"] == o["axis"] and abs(c["plane_mm"] - o["plane_mm"]) < 3.0 for o in caps0)]
            if new_caps:
                log(f"R {sid}: new flat facet(s) {new_caps}")
                v2, f2, inf = op_flat(env, sid, v1, f1, log)
                if v2 is not None and not inf.get("why"):
                    inf.pop("why", None)
                    record(sid, v2, f2, dict(inf, repair=True), "D")
                else:
                    rep["residual"].setdefault(sid, []).append(dict(what="flat_cut_face", caps=new_caps, why=(inf or {}).get("why")))
    # cumulative guards of every candidate against its Q215 mesh (all operations together)
    for sid, c in cand.items():
        it0 = B.items[B.find(sid)[0]]
        v0, f0 = B.mesh(it0)
        pir = any(o["kind"] == "P" for o in c["ops"])             # a re-bounded piriformis may lose volume (the Q215 gates: >= 0.25 of the old mesh, evidence volume >= 0.6) and length
        g, why = env.guards(sid, c["v"], c["f"], v0, f0, (0.25, 1.01) if pir else (0.84, 1.26), (0.7, 1.3) if pir else (0.88, 1.3), seam=False)
        c["cumulative_guards"] = g
        if why:
            rep["residual"].setdefault(sid, []).append(dict(what="cumulative_guard", why=why))
    # ---- final-state overlap with everything swapped in
    page = env.page
    accepted = dict(cand)
    for rnd in range(4):
        ov0 = page.overlap_state({})
        ov1 = page.overlap_state({sid: (c["v"], c["f"]) for sid, c in accepted.items()})
        bad = []
        for sid in accepted:
            o0, o1 = ov0.get(sid, 0.0), ov1.get(sid, 0.0)
            if o1 > OVERLAP_MAX or (o1 > o0 + OVERLAP_RISE_MAX and o1 > 40.0):
                bad.append((sid, o0, o1))
        log(f"overlap round {rnd}: {len(accepted)} candidates, bad {bad}")
        if not bad:
            break
        for sid, o0, o1 in bad:
            rep["kept"].setdefault(sid, {})["overlap"] = [f"{o1} % of its volume inside the other muscles (Q215 mesh {o0} %; gate {OVERLAP_MAX:g}, rise <= {OVERLAP_RISE_MAX:g} points above 40 %)"]
            accepted.pop(sid)
    for sid, c in accepted.items():
        c["overlap_vol_pct"] = [ov0.get(sid), ov1.get(sid)]
        c["neighbour_overlap"] = {m: [ov0.get(m), ov1.get(m)] for m in ov1 if ov0.get(m) is not None and abs(ov1[m] - ov0[m]) >= 1.0 and m != sid}
    # ---- write
    n_changed = 0
    for sid, c in accepted.items():
        it = B.items[B.find(sid)[0]]
        old_badge = it["e"]["rec"].get("procedural_badge")
        v0, f0 = B.mesh(it)
        vol0, vol1 = C.volume_cm3(v0, f0), C.volume_cm3(c["v"], c["f"])
        mv = surface_move(c["v"], c["f"], v0, f0)
        txt = badge_q216(it["e"]["rec"].get("name", sid), c, vol0, vol1, mv)
        rep["ops"][sid] = dict(volume_cm3=[round(vol0, 1), round(vol1, 1)], move=mv, overlap_vol_pct=c.get("overlap_vol_pct"), neighbour_overlap=c.get("neighbour_overlap"), operations=c["ops"], cumulative_guards=c.get("cumulative_guards"), badge_added=txt,
                               subject=it["e"]["subject"])
        if not a.dry:
            B.replace(sid, c["v"], c["f"], rec_updates={"procedural_badge": badge_add(old_badge, txt)})
        n_changed += 1
    welds = {z: w for z, w in welds.items() if w[3] in accepted or w[3] not in cand}          # a weld made against a candidate base that was not accepted is dropped
    for sid, c in accepted.items():                 # Z-fill continuations re-welded to a muscle whose end was pulled
        for zid, (zn, rinfo) in c.get("zfill_new", {}).items():
            zf_ = B.mesh(B.items[B.find(zid)[0]])[1]
            welds[zid] = (zn, zf_, rinfo, sid)
    for zid, (zv, zf_, inf, base_sid) in welds.items():
        zit = B.items[B.find(zid)[0]]
        if inf.get("op") == "reweld":
            txt = (f"Q216: re-welded to the muscle whose end was pulled onto its bone (the seam moved with it): seam gap p95 {inf['gap_before']['p95']} -> {inf['gap_after']['p95']} mm, the piece moved {inf['move_mean_mm']} mm on "
                   f"average (max {inf['move_max_mm']} mm), its far end held on its bone; unchanged otherwise.")
        else:
            txt = ("Q216: the vertices of this Z-Anatomy continuation that lay within 1 mm of the re-bounded sartorius (Q215 moved the base by 0.25-1 mm, so the seam vertices no longer coincided) were snapped onto the base's vertices "
                   f"(max move {inf['move_max_mm']} mm, {inf['snapped_to_base']} vertices to the base, {inf['snapped_to_piece']} to the continuation's own lower piece): the muscle and its continuation are one connected surface again (islands "
                   f"{len(inf['islands_before'])} -> {len(inf['islands_after'])}). Unchanged otherwise.")
        rep["welded"][zid] = dict(base=base_sid, info=inf, subject=zit["e"]["subject"], badge_added=txt)
        if not a.dry:
            B.replace(zid, zv, zf_, rec_updates={"procedural_badge": badge_add(zit["e"]["rec"].get("procedural_badge"), txt)})
    ev = REPO / "data/derived/Q216_piriformis_evidence.json"
    rf = REPO / "data/derived/Q216_piriformis_refit.json"
    rep["piriformis"] = dict(evidence=json.loads(ev.read_text()) if ev.exists() else None, sides=pir_sides, refit_attempted=bool(a.piriformis))
    for sid in ("piriformis_r", "piriformis_l"):
        if sid in accepted:
            rep["piriformis"]["sides"][sid]["decision"] = "refit"
        else:
            rep["piriformis"]["sides"].setdefault(sid, dict(decision="left", reasons=["not attempted"] if not a.piriformis else ["reverted by the final-state overlap check"]))
            rep["piriformis"]["sides"][sid]["decision"] = "left"
    if not a.dry:
        n = B.write(a.out)
        log(f"wrote {a.out}: {n} bytes, {len(B.items)} entries (was {n0})")
    Path(a.report).write_text(json.dumps(rep, indent=1, default=str) + "\n")
    log(f"changed {n_changed} muscles, welded {len(welds)}, kept {len(rep['kept'])} [{time.time() - t0:.0f} s]")


def badge_q216(name, c, vol0, vol1, mv):
    parts = []
    for op in c["ops"]:
        k = op["kind"]
        if k == "A":
            nb = op["nerve_before"]
            ins = ", ".join(f"{t} {x['inside_pct']} % of its vertices" for t, x in nb.items() if x["inside"] > 0)
            parts.append(f"Nerve corridor: her photo-traced nerve / vessel tubes ({ins}) lay inside this muscle after Q215; the muscle was carved away from them (corridor = tube + {CLEAR_MM:g} mm, a groove open towards the nearest surface, "
                         f"{op['removed_cm3']} cm3 removed), the traced structures were NOT moved; closest nerve vertex to the surface now {op['closest_nerve_mm']} mm, none inside.")
        elif k == "B":
            parts.append(f"Reconnected: the muscle consisted of two closed pieces {op['gap_mm']} mm apart (the smaller one {op['small_part_cm3']} cm3 = {100 * op['small_part_area_share']:.0f} % of the surface area); "
                         f"a loft of the two facing 3 mm sections ({op['bridge_added_cm3']} cm3) joins them.")
        elif k == "C":
            pl = "; ".join(f"{en} end {p['audit_before_mm']} mm from bone -> pulled {p['applied_mm']} mm towards {p['bone']}" for en, p in op["pulled"].items())
            aft = ", ".join(f"{e} {x['min_any_bone_mm']} mm" for e, x in op["after"].items())
            parts.append(f"Attachment: {pl} (Q214 attachment pull; ends from the Q204 end test now: {aft}).")
        elif k == "P":
            e0, e1 = op["ev"]
            parts.append(f"Re-bounded on her registered photographs with the Q215 method (no label of her own exists for the piriformis: its identity is still the male's; markers = the male-carried mesh, region = her photographed muscle, "
                         f"her bones and own muscles excluded): share of the muscle on her photographed muscle {e0['musc']} -> {e1['musc']}.")
        elif k == "D":
            dm = "; ".join(f"{d['axis']}={d['plane_mm']} plane {d['area_mm2']} mm2" for d in op["dome"])
            parts.append(f"Flat facet(s) ({dm}) replaced by a shallow dome (amplitude {op['amplitude_mm']} mm); the flat face was a raster/table-flattened plane of the Q215 label, not an anatomical cut.")
    return (f"Q216 clean-up of the Q215 re-bounded muscle (Source class unchanged: the muscle set is still the male's, position and extent hers): " + " ".join(parts) +
            f" Volume {round(vol1, 1)} cm3 (Q215 mesh {round(vol0, 1)} cm3); surface moved from the Q215 mesh median {mv['new_to_old_median_mm']} mm, p95 {mv['new_to_old_p95_mm']} mm, max {mv['max_mm']} mm "
            f"({c.get('overlap_vol_pct', [None, None])[1]} % of its volume inside her other muscles, was {c.get('overlap_vol_pct', [None, None])[0]} %). A position and boundary estimate, not a segmentation.")


if __name__ == "__main__":
    main()
