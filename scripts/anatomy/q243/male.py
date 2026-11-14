"""Q243 (4): the prostate zones, anterior fibromuscular stroma and seminal colliculus (verumontanum) of the HRA United Male v1.10 (Visible Human MALE = the donor of the male pages, CC BY 4.0)
registered with the HRA male pelvis (`pelvis-male` v1.3) onto the page's pelvic bones (rigid + uniform scale ICP, the Q233 procedure for the female) and guarded."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q243 import hra, spine as SP  # noqa: E402
from scripts.anatomy.q234 import place as PL  # noqa: E402
from scripts.transfer.q233_own_f import mask_of  # noqa: E402

# id, display name, Terminologia, HRA node, side, ontology (from the object crosswalk), closed envelope?
ZONES = [
    ("prostate_peripheral_zone_l", "Prostate: peripheral zone (left)", "Zona peripherica prostatae sinistra", "VH_M_peripheral_zone_of_prostate_L", "left"),
    ("prostate_peripheral_zone_r", "Prostate: peripheral zone (right)", "Zona peripherica prostatae dextra", "VH_M_peripheral_zone_of_prostate_R", "right"),
    ("prostate_transition_zone_l", "Prostate: transition zone (left)", "Zona transitionalis prostatae sinistra", "VH_M_transition_zone__of_prostate_L", "left"),
    ("prostate_transition_zone_r", "Prostate: transition zone (right)", "Zona transitionalis prostatae dextra", "VH_M_transition_zone_of_prostate_R", "right"),
    ("prostate_central_zone_l", "Prostate: central zone (left)", "Zona centralis prostatae sinistra", "VH_M_central_zone_of_prostate_L", "left"),
    ("prostate_central_zone_r", "Prostate: central zone (right)", "Zona centralis prostatae dextra", "VH_M_central_zone_of_prostate_R", "right"),
    ("prostate_afms_l", "Prostate: anterior fibromuscular stroma (left)", "Stroma fibromusculare anterius prostatae sinistrum", "VH_M_anterior_fibromuscular_stroma_L", "left"),
    ("prostate_afms_r", "Prostate: anterior fibromuscular stroma (right)", "Stroma fibromusculare anterius prostatae dextrum", "VH_M_anterior_fibromuscular_stroma_R", "right"),
    ("seminal_colliculus", "Seminal colliculus (verumontanum)", "Colliculus seminalis", "VH_M_seminal_colliculus", None),
]
PELVIS_OBJ = "pelvis-male"
ZONE_TRI = {"prostate_afms": 900, "prostate_peripheral": 1500, "prostate_transition": 700, "prostate_central": 1200, "seminal_colliculus": 240}


def load_hra_zones():
    N = hra.load_nodes("united-male", "|".join(f"^{z[3]}$" for z in ZONES) + "|^VH_M_base_of_prostate$|^VH_M_apex_of_prostate$")
    out = {z[0]: N[z[3]] for z in ZONES}
    out["_base"] = N["VH_M_base_of_prostate"]; out["_apex"] = N["VH_M_apex_of_prostate"]
    return out


def register_pelvis(bone_meshes, seed=0):
    """HRA male pelvis (atlas axis) -> the page's pelvic bones (hip bones, sacrum, coccyx): rigid + uniform scale ICP. -> (T=(s,R,t), residual dict)"""
    np.random.seed(seed)
    N = hra.load_nodes(PELVIS_OBJ)
    src = np.vstack([trimesh.Trimesh(v, f, process=False).sample(max(200, len(f) // 3)) for v, f in N.values()])
    dst = np.vstack([m.sample(40000) for m in bone_meshes])
    tree = cKDTree(dst)
    s, R, t, d = SP._icp(src, tree, dst, s0=1.0, iters=100, trim=0.85, scale_lim=(0.6, 1.4))
    dd = tree.query(s * src @ R.T + t)[0]
    res = dict(scale=round(float(s), 4), rotation=R.round(5).tolist(), translation_mm=t.round(2).tolist(), n_source=int(len(src)), n_target=int(len(dst)),
               residual_mm=dict(median=round(float(np.median(dd)), 2), p90=round(float(np.quantile(dd, .9)), 2), rms=round(float(np.sqrt((dd ** 2).mean())), 2)), det_R=round(float(np.linalg.det(R)), 4))
    return (s, R, t), res


def volume_cm3(V, F):
    m = trimesh.Trimesh(V, F, process=True)
    return round(abs(float(m.volume)) / 1000, 2) if m.is_watertight else None


def guard_zones(T, reg, ev, bones, skin_fn, min_inside_pct=60.0, max_centroid_offset_mm=8.0):
    """the HRA zones with the pelvis registration T against the page's CT prostate `ev['prostate']`. A zone may be shipped only when the page HAS a prostate there: the centroid of the HRA prostate (union of
    the zones) lies within `max_centroid_offset_mm` of the page prostate's and every zone has at least `min_inside_pct` % of its vertices inside the page prostate. -> report dict (`ships` False/True)"""
    Z = load_hra_zones()
    W = {k: hra.to_world(T, v) for k, (v, f) in Z.items()}
    pr = ev["prostate"]
    pm = trimesh.Trimesh(*pr, process=False)
    zones = [k for k in W if not k.startswith("_")]
    union = np.vstack([W[k] for k in zones if not k.startswith("seminal")])
    lo = np.minimum(pr[0].min(0), union.min(0)) - 3; hi = np.maximum(pr[0].max(0), union.max(0)) + 3
    pitch = 0.5; shape = tuple(np.ceil((hi - lo) / pitch).astype(int))
    masks = {k: mask_of(v, f, lo, shape, pitch) for k, (v, f) in ev.items()}
    rows = {}
    for k in zones + ["_base", "_apex"]:
        V = W[k]; idx = np.floor((V - lo) / pitch).astype(int)
        ok = np.all((idx >= 0) & (idx < np.array(shape)), axis=1)
        ins = {n: round(100 * float(m[tuple(idx[ok].T)].sum()) / len(V), 1) for n, m in masks.items()}
        db = PL.bone_signed(bones, V)[0]
        rows[k] = dict(vertices=int(len(V)), inside_page_organ_pct=ins, bone_min_mm=round(float(db.min()), 2), skin_distance_min_mm=skin_fn(V), centroid=[round(float(x), 1) for x in V.mean(0)])
    cen_h = union.mean(0); cen_p = pm.vertices.mean(0)
    # HRA prostate volume (union of the closed zones): sum of the closed zone volumes, reported next to the page's
    vol_hra = {k: volume_cm3(*Z[k]) for k in zones}
    off = float(np.linalg.norm(cen_h - cen_p))
    min_in = min(rows[k]["inside_page_organ_pct"]["prostate"] for k in zones)
    mean_in = float(np.mean([rows[k]["inside_page_organ_pct"]["prostate"] for k in zones]))
    ships = bool(off <= max_centroid_offset_mm and min_in >= min_inside_pct)
    return dict(registration=reg, page_prostate=dict(volume_cm3=round(abs(float(pm.volume)) / 1000, 2), bounds=pm.bounds.round(1).tolist(), centroid=cen_p.round(1).tolist(), triangles=int(len(pm.faces))),
                hra_zone_union=dict(centroid=cen_h.round(1).tolist(), bounds=[union.min(0).round(1).tolist(), union.max(0).round(1).tolist()], closed_zone_volumes_cm3=vol_hra),
                centroid_offset_mm=round(off, 1), centroid_offset_vector_mm=(cen_h - cen_p).round(1).tolist(), mean_inside_page_prostate_pct=round(mean_in, 1), min_inside_page_prostate_pct=round(min_in, 1),
                rule=dict(max_centroid_offset_mm=max_centroid_offset_mm, min_inside_pct=min_inside_pct), zones=rows, ships=ships,
                reason=None if ships else (f"the registered HRA prostate lies {off:.1f} mm from this page's prostate (centroid) and only {mean_in:.1f} % of the zone vertices fall inside it: the zones would float outside the page's prostate; "
                                          f"the bone registration (median {reg['residual_mm']['median']} mm, p90 {reg['residual_mm']['p90']} mm) cannot explain the offset"))
