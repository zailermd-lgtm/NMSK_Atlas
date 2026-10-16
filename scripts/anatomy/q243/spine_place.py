"""Q243 (3): place the HRA nucleus pulposus (24) and spinal cord segments (29) on a page whose vertebrae were fitted (spine.fit_levels) and apply the guards."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree, Delaunay

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q243 import spine as SP, hra  # noqa: E402
from scripts.anatomy.q234 import place as PL  # noqa: E402
from scripts.anatomy.q243.fastbone import Bones  # noqa: E402
from scripts.transfer.q233_own_f import mask_of  # noqa: E402

NUC_TRI, CORD_TRI = 2400, 1500
BONE_MARGIN = 1.2
MIN_VOLUME_RATIO = 0.25


def tangents_of(pv):
    lv = SP.LEVELS
    C = np.array([pv[l].vertices.mean(0) for l in lv])
    out = {}
    for i, l in enumerate(lv):
        a, b = C[max(i - 1, 0)], C[min(i + 1, len(lv) - 1)]
        t = a - b                                    # C1 first: pointing up (+y)
        out[l] = t / np.linalg.norm(t)
    return out


def volume_of(V, F):
    m = trimesh.Trimesh(V, F, process=False)
    return round(abs(float(m.volume)) / 1000, 3) if m.is_watertight else None


_BC = {}


def _bones(meshes):
    key = tuple(id(m) for m in meshes)
    if key not in _BC:
        _BC[key] = Bones(meshes)
    return _BC[key]


def bones_near(V, bones_by_level, fallback, pad=12.0):
    """the page's bone meshes whose bounding box lies within `pad` mm of the vertices V (a handful of vertebrae instead of the whole column)"""
    if not bones_by_level:
        return fallback
    lo, hi = V.min(0) - pad, V.max(0) + pad
    out = [m for m in bones_by_level.values() if not ((m.bounds[1] < lo).any() or (m.bounds[0] > hi).any())]
    return out or fallback


def place_nuclei(blend, disc_meshes, bone_meshes, skin_fn, fits, page_disc_for, bones_by_level=None):
    """page_disc_for[(upper, lower)] -> page disc id (or None when the page has no disc there). disc_meshes {disc id: (v, f)}"""
    H0, nodes = SP.load_nucleus()
    out = {}
    allp = []
    for key, (v, f) in H0.items():
        V0, F0, ok = SP.decimated_closed(v, f, NUC_TRI)
        out[key] = dict(V0=V0, F0=F0, hra_triangles=len(f), closed=ok, node=nodes[key], volume_hra_cm3=volume_of(*(np.asarray(v), np.asarray(f))))
    pitch = 0.5
    masks, origin = {}, {}
    res = {}
    for key, o in out.items():
        u, l = key
        V = blend.disc(o["V0"], u, l)
        near_b = _bones([bones_by_level[x] for x in (u, l) if bones_by_level and x in bones_by_level] or bone_meshes)
        V, n_moved, max_move = near_b.rest_on(V, margin=BONE_MARGIN, iters=6)
        squeeze = 1.0
        if near_b.signed(V)[0].min() < 1.0 - 1e-6:
            # her disc space is thinner than the HRA nucleus: scale the nucleus along the spine axis about its centroid (the footprint is kept) until it clears both endplates, then push again
            ax = fits[u]["page_centroid"] - fits[l]["page_centroid"]; ax = ax / np.linalg.norm(ax)
            c0 = V.mean(0); P = np.eye(3) - np.outer(ax, ax)
            V0s = V.copy()
            for k in (0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2):
                Vk = c0 + (V0s - c0) @ (P + k * np.outer(ax, ax)).T
                Vk, nm, mm = near_b.rest_on(Vk, margin=BONE_MARGIN, iters=4)
                if near_b.signed(Vk)[0].min() >= 1.0 - 1e-6:
                    V, n_moved, max_move, squeeze = Vk, nm, mm, k
                    break
            else:
                V, n_moved, max_move, squeeze = Vk, nm, mm, k
        did = page_disc_for.get(key)
        g = dict(vertices=int(len(V)), triangles=int(len(o["F0"])), watertight=bool(o["closed"]), page_disc=did, volume_cm3=volume_of(V, o["F0"]), volume_hra_cm3=o["volume_hra_cm3"],
                 hra_node=o["node"], fit_upper=dict(scale=fits[u]["scale"], residual_median_mm=fits[u]["residual_median_mm"], residual_p90_mm=fits[u]["residual_p90_mm"]),
                 fit_lower=dict(scale=fits[l]["scale"], residual_median_mm=fits[l]["residual_median_mm"], residual_p90_mm=fits[l]["residual_p90_mm"]),
                 skin_distance_min_mm=skin_fn(V), height_mm=round(float(np.ptp(V[:, 1])), 1), vertices_moved_out_of_bone=int(n_moved), moved_fraction_pct=round(100 * n_moved / len(V), 1),
                 max_move_out_of_bone_mm=round(float(max_move), 2), axial_scale=squeeze)
        g["volume_ratio_to_hra"] = round(g["volume_cm3"] / g["volume_hra_cm3"], 3) if g["volume_cm3"] and g["volume_hra_cm3"] else None
        db = near_b.signed(V)[0]
        g["bone_min_mm"] = round(float(db.min()), 2)
        if did is None or did not in disc_meshes:
            g["inside_disc_pct"] = None
            g["pass"] = False; g["held_reason"] = "no intervertebral disc of this page lies at this level (her supernumerary lumbar disc is not an atlas entity, Q185k2): a nucleus would float between two vertebrae"
        else:
            dv, df = disc_meshes[did]
            hull = Delaunay(dv)
            g["inside_disc_pct"] = round(100 * float((hull.find_simplex(V) >= 0).mean()), 1)
            g["page_disc_triangles"] = int(len(df)); g["page_disc_volume_cm3"] = volume_of(dv, df)
            g["page_disc_placeholder"] = bool(len(df) <= 200)
            g["pass"] = bool(g["bone_min_mm"] >= 1.0 - 1e-6 and g["inside_disc_pct"] >= 95.0 and o["closed"] and g["max_move_out_of_bone_mm"] <= 4.0
                             and (g["volume_ratio_to_hra"] or 0) >= MIN_VOLUME_RATIO)
            if not g["pass"]:
                g["held_reason"] = (f"bone clearance {g['bone_min_mm']} mm / inside her disc {g['inside_disc_pct']} % / max move {g['max_move_out_of_bone_mm']} mm / "
                                    f"volume after the fit {g['volume_ratio_to_hra']} of the HRA nucleus (her disc space is thinner than the HRA disk; minimum {MIN_VOLUME_RATIO})")
        res[key] = dict(V=V, F=o["F0"], gates=g)
    return res


def place_cord(blend, pv, bone_meshes, skin_fn, fits, bones_by_level=None):
    cord = SP.load_cord()
    tg = tangents_of(pv)
    canal = SP.canal_slices(pv, tg)
    res = {}
    for lv, ((v, f), node) in cord.items():
        Vc, Fc, info = hra.cap_open_ends(v, f)
        V0, F0, ok = SP.decimated_closed(Vc, Fc, CORD_TRI)
        V = blend(V0)
        near_b = _bones(bones_near(V, bones_by_level, bone_meshes))
        V, n_moved, max_move = near_b.rest_on(V, margin=BONE_MARGIN, iters=6)
        m = trimesh.Trimesh(V, F0, process=False)
        db = near_b.signed(V)[0]
        ins, tested = SP.in_canal(V, canal)
        t = tested.sum()
        g = dict(vertices=int(len(V)), triangles=int(len(F0)), hra_triangles=int(len(f)), watertight=bool(ok and m.is_watertight), hra_node=node, caps=info,
                 volume_cm3=volume_of(V, F0), length_mm=round(float(np.ptp(V[:, 1])), 1), bone_min_mm=round(float(db.min()), 2), skin_distance_min_mm=skin_fn(V),
                 canal_inside_pct=round(100 * float(ins[tested].mean()), 1) if t else None, canal_tested_pct=round(100 * float(t) / len(V), 1),
                 y_range_mm=[round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)], centroid=[round(float(x), 1) for x in V.mean(0)],
                 vertices_moved_out_of_bone=int(n_moved), moved_fraction_pct=round(100 * n_moved / len(V), 1), max_move_out_of_bone_mm=round(float(max_move), 2))
        g["pass"] = bool(g["bone_min_mm"] >= 1.0 - 1e-6 and g["canal_inside_pct"] is not None and g["canal_inside_pct"] >= 98.0 and g["canal_tested_pct"] >= 80 and g["watertight"]
                         and g["max_move_out_of_bone_mm"] <= 4.0)
        if not g["pass"]:
            g["held_reason"] = f"bone clearance {g['bone_min_mm']} mm / inside the vertebral canal {g['canal_inside_pct']} % (tested {g['canal_tested_pct']} %) / max move {g['max_move_out_of_bone_mm']} mm"
        res[lv] = dict(V=V, F=F0, gates=g)
    return res, canal
