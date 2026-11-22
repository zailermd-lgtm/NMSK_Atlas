"""Q243 (1): the FEMALE pelvic vessels of the HRA 3D Reference Object Library `blood-vasculature-female` v1.3 (Visible Human FEMALE frame, CC BY 4.0) registered with the Q233 pelvis
transform (HRA VH_F pelvis -> the page's pelvic bones), as capped tubes, with the guards of scripts/anatomy/q234/place.py (bones >= 1 mm, inside the skin) plus tube length / calibre,
left / right checks (name vs world x vs nearest same-side hip bone) and course checks. Page evidence: scripts/anatomy/q243/evidence.py."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q243 import hra  # noqa: E402
from scripts.anatomy.q234 import place as PL  # noqa: E402
from scripts.anatomy.q240.calibre import tube_diameter  # noqa: E402
from scripts.transfer.q233_own_f import mask_of  # noqa: E402

OBJ = "blood-vasculature-female"
BODY_MARGIN = 1.2          # push out of bone to this signed distance (gate: >= 1.0)
# id, display name, Terminologia name, HRA node, side, kind (a artery / v vein), course group
VESSELS = [
    ("uterine_a_l", "Uterine artery (left)", "Arteria uterina sinistra", "VH_F_left_uterine_artery", "left", "a", "uterine"),
    ("uterine_a_r", "Uterine artery (right)", "Arteria uterina dextra", "VH_F_right_uterine_artery", "right", "a", "uterine"),
    ("uterine_v_l", "Uterine vein (left)", "Vena uterina sinistra", "VH_F_left_uterine_vein", "left", "v", "uterine"),
    ("uterine_v_r", "Uterine vein (right)", "Vena uterina dextra", "VH_F_right_uterine_vein", "right", "v", "uterine"),
    ("internal_iliac_v_l", "Internal iliac vein (left)", "Vena iliaca interna sinistra", "VH_F_internal_iliac_vein_L", "left", "v", "iliac"),
    ("internal_iliac_v_r", "Internal iliac vein (right)", "Vena iliaca interna dextra", "VH_F_internal_iliac_vein_R", "right", "v", "iliac"),
    ("internal_pudendal_v_l", "Internal pudendal vein (left)", "Vena pudenda interna sinistra", "VH_F_internal_pudendal_vein_L", "left", "v", "pudendal"),
    ("internal_pudendal_v_r", "Internal pudendal vein (right)", "Vena pudenda interna dextra", "VH_F_internal_pudendal_vein_R", "right", "v", "pudendal"),
    ("middle_rectal_v_l", "Middle rectal vein (left)", "Vena rectalis media sinistra", "VH_F_middle_rectal_vein_L", "left", "v", "rectal_mid"),
    ("middle_rectal_v_r", "Middle rectal vein (right)", "Vena rectalis media dextra", "VH_F_middle_rectal_vein_R", "right", "v", "rectal_mid"),
    ("inferior_rectal_v_l", "Inferior rectal vein (left)", "Vena rectalis inferior sinistra", "VH_F_inferior_rectal_vein_L", "left", "v", "rectal_inf"),
    ("inferior_rectal_v_r", "Inferior rectal vein (right)", "Vena rectalis inferior dextra", "VH_F_inferior_rectal_vein_R", "right", "v", "rectal_inf"),
    ("superior_rectal_v", "Superior rectal vein", "Vena rectalis superior", "VH_F_superior_rectal_vein", None, "v", "rectal_sup"),
    ("median_sacral_v", "Median sacral vein", "Vena sacralis mediana", "VH_F_median_sacral_vein", None, "v", "sacral"),
    ("superior_rectal_a", "Superior rectal artery", "Arteria rectalis superior", "VH_F_superior_rectal_artery", None, "a", "rectal_sup"),
]
ONTO = {"VH_F_left_uterine_artery": "FMA:18831", "VH_F_right_uterine_artery": "FMA:18830", "VH_F_left_uterine_vein": "FMA:18898", "VH_F_right_uterine_vein": "FMA:18897",
        "VH_F_internal_iliac_vein_L": "UBERON:0001317", "VH_F_internal_iliac_vein_R": "UBERON:0001317", "VH_F_internal_pudendal_vein_L": "UBERON:0018252",
        "VH_F_internal_pudendal_vein_R": "UBERON:0018252", "VH_F_middle_rectal_vein_L": "FMA:18895", "VH_F_middle_rectal_vein_R": "FMA:18894", "VH_F_inferior_rectal_vein_L": "FMA:21242",
        "VH_F_inferior_rectal_vein_R": "FMA:21242", "VH_F_superior_rectal_vein": "UBERON:0035040 (the crosswalk label of this VEIN node reads 'superior rectal artery': a library label error)",
        "VH_F_median_sacral_vein": "UBERON:0006687", "VH_F_superior_rectal_artery": "UBERON:0035040"}


def load_hra():
    """-> {id: (V_hra (atlas axis, mm), F, cap_info)}: the HRA tubes, end loops capped (flat discs only)"""
    N = hra.load_nodes(OBJ, "|".join(v[3] + "$" for v in VESSELS))
    out = {}
    for sid, name, latin, node, side, kind, grp in VESSELS:
        v, f = N[node]
        V, F, info = hra.cap_open_ends(v, f)
        out[sid] = (V, F, info)
    return out


def _clean_tube(V, F):
    m = trimesh.Trimesh(V, F, process=False)
    return m


def tube_metrics(V, F):
    t = tube_diameter(V, F)
    m = trimesh.Trimesh(V, F, process=False)
    t["volume_cm3"] = round(abs(float(m.volume)) / 1000, 3) if m.is_watertight else None
    t["area_cm2"] = round(float(m.area) / 100, 2)
    return t


def place(M, T0, ev, bone_meshes, hips, skin_dist_fn, soft_gate=True, extra_ref=None):
    """M = load_hra(); T0 = (s, R, t) HRA -> page; ev = {key: (v, f)} page organs (urinary_bladder, rectum, sigmoid_colon, uterus, vagina, ovary_l/r, levator_ani_l/r, common_iliac_v_l/r);
    hips = {'l': Trimesh, 'r': Trimesh}. -> {sid: dict(V, F, gates, metrics)}"""
    Wall = {s: hra.to_world(T0, M[s][0]) for s in M}
    allv = np.vstack(list(Wall.values()))
    lo = allv.min(0) - 14; hi = allv.max(0) + 14
    pitch = 1.0; shape = tuple(np.ceil((hi - lo) / pitch).astype(int))
    masks = {k: mask_of(v, f, lo, shape, pitch) for k, (v, f) in ev.items() if k in ("urinary_bladder", "rectum", "sigmoid_colon", "uterus", "vagina", "ovary_l", "ovary_r", "levator_ani_l", "levator_ani_r")}
    deep = {k: ndi.binary_erosion(g, iterations=3) for k, g in masks.items()}
    hip_tree = {k: cKDTree(h.sample(60000)) for k, h in hips.items()}
    ischium = {k: h.vertices[h.vertices[:, 1] < h.vertices[:, 1].min() + 25] for k, h in hips.items()}
    uterus_tree = cKDTree(trimesh.Trimesh(*ev["uterus"], process=False).sample(30000)) if "uterus" in ev else None
    out = {}
    for sid, name, latin, node, side, kind, grp in VESSELS:
        F = M[sid][1]
        W = Wall[sid]
        V, n_moved, max_move = PL.rest_on_bone(W, bone_meshes, margin=BODY_MARGIN, iters=8)
        db = PL.bone_signed(bone_meshes, V)[0]
        idx = np.floor((V - lo) / pitch).astype(int)
        inside = {k: round(100 * float(g[tuple(idx.T)].mean()), 1) for k, g in masks.items() if g[tuple(idx.T)].any()}
        deepin = {k: round(100 * float(g[tuple(idx.T)].mean()), 1) for k, g in deep.items() if g[tuple(idx.T)].any()}
        m = trimesh.Trimesh(V, F, process=False)
        met = tube_metrics(V, F)
        cx = float(V[:, 0].mean())
        g = dict(vertices=int(len(V)), triangles=int(len(F)), bone_min_mm=round(float(db.min()), 2), vertices_moved_out_of_bone=int(n_moved), moved_fraction_pct=round(100 * n_moved / len(V), 1),
                 max_move_out_of_bone_mm=round(max_move, 2), skin_distance_min_mm=skin_dist_fn(V), vertices_inside_page_organ_pct=inside, vertices_deeper_3mm_in_organ_pct=deepin,
                 watertight=bool(m.is_watertight), centroid_x_mm=round(cx, 1), x_range_mm=[round(float(V[:, 0].min()), 1), round(float(V[:, 0].max()), 1)],
                 y_range_mm=[round(float(V[:, 1].min()), 1), round(float(V[:, 1].max()), 1)], z_range_mm=[round(float(V[:, 2].min()), 1), round(float(V[:, 2].max()), 1)])
        g.update(length_mm=met["length_mm"], calibre_mm=met["diameter_mm"], calibre_area_mm=met.get("area_diameter_mm"), volume_cm3=met["volume_cm3"], area_cm2=met["area_cm2"])
        # ---- left / right: name vs world x (atlas +X = subject right) and the nearest hip bone
        dist_hip = {k: round(float(trimesh.proximity.closest_point(h, V[::4])[1].mean()), 1) for k, h in hips.items()}
        near = min(dist_hip, key=dist_hip.get)
        lr = dict(name_side=side, centroid_x_mm=round(cx, 1), mean_distance_to_hip_mm=dist_hip)
        if side:
            want = "l" if side == "left" else "r"
            lr["x_sign_ok"] = bool((cx < 0) == (side == "left"))
            lr["nearest_hip_is_same_side"] = bool(near == want)
            lr["ok"] = bool(lr["x_sign_ok"] and lr["nearest_hip_is_same_side"])
        else:
            lr["midline_x_mm"] = round(cx, 1); lr["ok"] = bool(abs(cx) < 25)
        g["left_right"] = lr
        # ---- course
        co = {}
        ys = V[:, 1]
        lowq, highq = ys <= np.quantile(ys, 0.1), ys >= np.quantile(ys, 0.9)
        if grp == "uterine" and uterus_tree is not None:
            d = uterus_tree.query(V)[0]
            co["min_distance_to_uterus_mm"] = round(float(d.min()), 1)
            xs = V[:, 0] * (1 if side == "right" else -1)           # lateral = away from the midline on its own side
            lat, med = np.argsort(xs)[-len(V) // 10:], np.argsort(xs)[:len(V) // 10]
            co["medial_end_to_uterus_mm"] = round(float(d[med].mean()), 1); co["lateral_end_to_uterus_mm"] = round(float(d[lat].mean()), 1)
            co["ok"] = bool(co["min_distance_to_uterus_mm"] <= 8 and co["medial_end_to_uterus_mm"] < co["lateral_end_to_uterus_mm"])
        elif grp == "pudendal":
            k = "l" if side == "left" else "r"
            dt = cKDTree(ischium[k]).query(V[lowq])[0]
            co["inferior_end_to_ischial_tuberosity_mm"] = round(float(dt.mean()), 1)
            dbn = hip_tree[k].query(V)[0]
            co["fraction_within_10mm_of_same_side_hip_pct"] = round(100 * float((dbn <= 10).mean()), 1)
            co["inferior_end_y_mm"] = round(float(V[lowq, 1].mean()), 1); co["superior_end_y_mm"] = round(float(V[highq, 1].mean()), 1)
            co["ok"] = bool(co["fraction_within_10mm_of_same_side_hip_pct"] >= 50 and co["inferior_end_to_ischial_tuberosity_mm"] <= 45)
        elif grp == "iliac":
            ci = ev.get("common_iliac_v_" + ("l" if side == "left" else "r"))
            if ci is not None:
                t = cKDTree(trimesh.Trimesh(*ci, process=False).sample(20000))
                co["superior_end_to_common_iliac_vein_mm"] = round(float(t.query(V[highq])[0].mean()), 1)
                co["ok"] = bool(co["superior_end_to_common_iliac_vein_mm"] <= 40)
            else:
                co["ok"] = True
        elif grp in ("rectal_mid", "rectal_inf", "rectal_sup", "sacral"):
            co["centroid_y_mm"] = round(float(ys.mean()), 1)
        g["course"] = co
        # ---- gates
        soft = sum(deepin.get(k, 0) for k in ("urinary_bladder", "rectum", "sigmoid_colon", "uterus", "vagina", "ovary_l", "ovary_r"))
        g["soft_organ_deep_overlap_pct"] = round(soft, 1)
        g["pass"] = bool(g["bone_min_mm"] >= 1.0 - 1e-6 and g["skin_distance_min_mm"] >= 15 and g["max_move_out_of_bone_mm"] <= 6.0 and g["moved_fraction_pct"] <= 40
                         and lr["ok"] and co.get("ok", True) and (soft <= 10.0 or not soft_gate) and g["calibre_mm"] is not None)
        out[sid] = dict(V=V, F=F, gates=g)
    # order of the rectal veins along the rectum (superior > middle > inferior, both sides)
    cy = {s: float(out[s]["V"][:, 1].mean()) for s in out}
    order = dict(superior_rectal_v=round(cy["superior_rectal_v"], 1), superior_rectal_a=round(cy["superior_rectal_a"], 1),
                 middle_rectal_v_l=round(cy["middle_rectal_v_l"], 1), middle_rectal_v_r=round(cy["middle_rectal_v_r"], 1),
                 inferior_rectal_v_l=round(cy["inferior_rectal_v_l"], 1), inferior_rectal_v_r=round(cy["inferior_rectal_v_r"], 1))
    order["ok"] = bool(min(order["superior_rectal_v"], order["superior_rectal_a"]) > max(order["middle_rectal_v_l"], order["middle_rectal_v_r"])
                       and min(order["middle_rectal_v_l"], order["middle_rectal_v_r"]) > max(order["inferior_rectal_v_l"], order["inferior_rectal_v_r"]))
    return out, order
