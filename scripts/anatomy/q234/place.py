"""Q234 shared placement of the HRA VH_F objects (vagina, ligaments, breasts) onto a page: pelvic structures with the page's Q233 pelvis registration, breasts with the thoracic registration + skin-envelope
fit (chestfit.py); gates, volumes, badge texts. The page scripts (scripts/transfer/q234_own_f.py, scripts/zanatomy/q234_z_female.py) supply the page evidence."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q233 import hra_register as H  # noqa: E402
from scripts.anatomy.q234 import chestfit as C, hra_q234 as Q  # noqa: E402
from scripts.transfer.q233_own_f import mask_of  # noqa: E402

CITE = ("HuBMAP Human Reference Atlas, 3D Reference Object Library (CC BY 4.0; https://humanatlas.io/3d-reference-library, https://github.com/hubmapconsortium/ccf-3d-reference-object-library, commit " + Q.COMMIT + "): "
        "VH_F_vagina and VH_F_Ligaments_Uterus_Ovaries (v1.2; library authors Kristen Browne, Heidi Schlehlein, Bruce W. Herr II, Ellen Quardokus, Andreas Bueckle, Katy Boerner; objects of the Visible Human FEMALE frame, "
        "construction not documented by the library) and VH_F_mammary_gland_L/R (v1.3; Heidi Schlehlein, reviewer Harikrishna Nakshatri; sculpted from scratch from textbook atlases, DOI 10.48539/HBM378.VWZG.633 / "
        "10.48539/HBM989.SNHP.535); VH_F_Vertebrae (v1.2) only as the thoracic registration anchor")
ABSENT = "The vulva, labia, clitoris and the female urethra are not in the HRA set and are not built."


def thorax_register(anchor, page_pts, s0=1.0):
    """HRA thoracic vertebrae (atlas axis, mm) -> page thoracic vertebrae: rigid + uniform scale ICP. -> (T=(s,R,t), residual dict)"""
    tree = cKDTree(page_pts)
    s, R, t, d = H.icp(anchor, tree, page_pts, s0=s0, iters=100, trim=0.8)
    res = dict(scale=round(float(s), 4), rotation=R.round(5).tolist(), translation_mm=t.round(2).tolist(), n_source=int(len(anchor)), n_target=int(len(page_pts)),
               residual_mm=dict(median=round(float(np.median(d)), 2), p90=round(float(np.quantile(d, .9)), 2), rms=round(float(np.sqrt((d ** 2).mean())), 2)), det_R=round(float(np.linalg.det(R)), 4))
    return (s, R, t), res


_KD = {}


def bone_signed(meshes, W, near=4.0):
    """signed distance (mm, negative inside) of the points W to the page's bone meshes (nearest surface, sign from its face normal) and the outward normal there. Points farther than `near` mm from every bone
    surface sample get their unsigned distance (they cannot be inside a bone shell of any thin structure) -- only the near ones are solved exactly."""
    best = np.full(len(W), np.inf); bn = np.zeros((len(W), 3))
    for m in meshes:
        kd = _KD.get(id(m))
        if kd is None:
            kd = _KD[id(m)] = cKDTree(m.sample(80000))
        d0 = kd.query(W)[0]
        far = d0 >= near
        u = far & (d0 < np.abs(best))
        best[u] = d0[u]
        idx = np.where(~far)[0]
        if len(idx):
            c, d, tri = trimesh.proximity.closest_point(m, W[idx])
            n = m.face_normals[tri]
            sd = d * np.where(((W[idx] - c) * n).sum(1) >= 0, 1.0, -1.0)
            upd = np.abs(sd) < np.abs(best[idx])
            best[idx[upd]] = sd[upd]; bn[idx[upd]] = n[upd]
    return best, bn


def rest_on_bone(V, meshes, margin=0.3, iters=4):
    """ligament / organ vertices that the registration error left inside a bone (attachment ends, <= about 1.5 mm) are moved out along the bone normal to rest on its surface. -> V', n moved, max move"""
    V = np.array(V, float); V0 = V.copy()
    for _ in range(iters):
        sd, n = bone_signed(meshes, V)
        v = sd < margin
        if not v.any():
            break
        V[v] += (margin - sd[v])[:, None] * n[v]
    d = np.linalg.norm(V - V0, axis=1)
    return V, int((d > 0.05).sum()), float(d.max())


def pelvic_place(M, info, T0, ev, bone_meshes, skin_depth_fn, gate_soft=True):
    """vagina + ligaments with the page's pelvis registration T0 (HRA -> page). ev = {organ id: (v, f)} of the page's own soft organs used for the overlap report; bone_meshes = trimesh meshes of the page's pelvic bones.
    -> {sid: (V, F, gates)}"""
    ids = [s for s in M if info[s]["region"] == "pelvis"]
    W = {s: H.apply(T0, M[s][0]) for s in ids}
    allv = np.vstack(list(W.values()))
    lo = allv.min(0) - 14; hi = allv.max(0) + 14
    pitch = 1.0; shape = tuple(np.ceil((hi - lo) / pitch).astype(int))
    masks = {i: mask_of(v, f, lo, shape, pitch) for i, (v, f) in ev.items()}
    out = {}
    for sid in ids:
        F = M[sid][1]
        V, n_moved, max_move = rest_on_bone(W[sid], bone_meshes)
        m = trimesh.Trimesh(V, F, process=False)
        solid = bool(info[sid]["mode"] == "closed envelope")
        db_s = bone_signed(bone_meshes, V)[0]
        db = np.abs(db_s)
        idx = np.floor((V - lo) / pitch).astype(int)
        ok = np.all((idx >= 0) & (idx < np.array(shape)), axis=1)
        inside = {}
        for i, g in masks.items():
            v = np.zeros(len(V), bool); v[ok] = g[tuple(idx[ok].T)]
            if v.any():
                inside[i] = round(100 * float(v.mean()), 1)
        gates = dict(bone_min_mm=round(float(db_s.min()), 2), vertices_within_1mm_of_bone=int((db < 1).sum()), vertices_moved_out_of_bone=n_moved, max_move_out_of_bone_mm=round(max_move, 2), vertices=int(len(V)), triangles=int(len(F)), skin_distance_min_mm=skin_depth_fn(V),
                     vertices_inside_page_organ_pct=inside, watertight=bool(m.is_watertight))
        if solid:
            mk = mask_of(V, F, lo, shape, pitch)
            ov = {i: round(float((mk & g).sum()) * pitch ** 3 / 1000, 3) for i, g in masks.items() if (mk & g).sum()}
            gates["volume_cm3"] = round(float(abs(m.volume)) / 1000, 2)
            gates["overlap_cm3"] = ov
            gates["overlap_pct_of_volume"] = {i: round(100 * x / max(gates["volume_cm3"], 1e-9), 1) for i, x in ov.items()}
        elif m.is_watertight:
            gates["volume_cm3"] = round(float(abs(m.volume)) / 1000, 3)
        gates["area_cm2"] = round(float(m.area) / 100, 2)
        lig = info[sid]["cat"] == "ligament"
        soft = [x for x in ("urinary_bladder", "rectum", "sigmoid_colon") if x in gates["vertices_inside_page_organ_pct"]]
        soft_pct = sum(gates["vertices_inside_page_organ_pct"][x] for x in soft)
        gates["bladder_rectum_sigmoid_pct_of_vertices"] = round(soft_pct, 1)
        gates["pass"] = bool(gates["skin_distance_min_mm"] >= (8 if lig else 15) and gates["bone_min_mm"] >= (0.25 if lig else 0.5) and (soft_pct <= 10.0 or not gate_soft))
        out[sid] = (V, F, gates)
    return out


MIN_VOLUME_RATIO = 0.25


def breast_place(M, info, anchor, page_vert_pts, skin, groups, gate_muscle=True):
    """both breasts. -> dict(thorax=(T, reg), sides={l: {sid: (V, F, gates)}, r: ...}, warp stats, push history)"""
    np.random.seed(0)
    T, reg = thorax_register(anchor, page_vert_pts)
    res = {}
    for side in ("l", "r"):
        ids = [s for s in M if info[s]["region"] == "breast" and s.endswith("_" + side)]
        X = {k: H.apply(T, M[k][0]) for k in ids}
        allv = np.vstack(list(X.values()))
        F = C.Fields(skin, groups, allv.min(0) - 20, allv.max(0) + 20)
        ref = np.vstack([trimesh.Trimesh(X[k], M[k][1], process=False).sample(60000 if k.startswith("breast_fat") else 4000) for k in ids if k.startswith(("breast_fat", "areola", "nipple"))])
        W = C.ColumnWarp(F, ref, m_skin=2.5, rest_gap=0.0)
        Y0 = {k: W(X[k]) for k in ids}
        rules = [("skin", 1.0, "inside"), ("pec", 0.5, "outside"), ("bone", 1.0, "outside"), ("muscle", 0.0, "outside")]
        Y, hist = C.push_field(F, Y0, rules, iters=30)
        # residual violations (columns where the page leaves less room than the margins ask for): a second phase with margins raised by 0.8 mm for the remaining vertices
        tight = [(n, m + 0.8, k) for n, m, k in rules]
        Y, hist2 = C.push_field(F, Y, tight, iters=30)
        hist = hist + [("phase2",)] + hist2
        out = {}
        for k in ids:
            m = trimesh.Trimesh(Y[k], M[k][1], process=False)
            m0 = trimesh.Trimesh(X[k], M[k][1], process=False)
            sd = {n: F.at(n, Y[k]) for n in ("skin", "pec", "bone", "muscle")}
            disp = np.linalg.norm(Y[k] - Y0[k], axis=1)
            col = np.linalg.norm(Y0[k] - X[k], axis=1)
            g = dict(triangles=int(len(M[k][1])), vertices=int(len(Y[k])), watertight=bool(m.is_watertight),
                     skin_inside_min_mm=round(float(-sd["skin"].max()), 2), pectoralis_major_min_mm=round(float(sd["pec"].min()), 2), bone_min_mm=round(float(sd["bone"].min()), 2),
                     other_muscle_min_mm=round(float(sd["muscle"].min()), 2),
                     skin_median_mm=round(float(-np.median(sd["skin"])), 1), vertices_moved_over_1mm_by_rim_push=int((disp > 1).sum()), rim_push_max_mm=round(float(disp.max()), 1),
                     column_fit_shift_median_mm=round(float(np.median(col)), 1), column_fit_shift_max_mm=round(float(col.max()), 1), area_cm2=round(float(m.area) / 100, 1))
            if m.is_watertight:
                g["volume_cm3"] = round(float(abs(m.volume)) / 1000, 2); g["volume_hra_cm3"] = round(float(abs(m0.volume)) / 1000, 2)
            # the fields are 1 mm grids: a vertex counts as inside the skin at >= 0 mm, anterior to the pectoralis major at >= -1 mm (one voxel), >= 1 mm from every bone; the other muscles are gated only when `gate_muscle`
            g["pass"] = bool(g["skin_inside_min_mm"] >= 0.0 and g["pectoralis_major_min_mm"] >= -1.0 and g["bone_min_mm"] >= 1.0 and (g["other_muscle_min_mm"] >= -1.5 or not gate_muscle))
            out[k] = (Y[k], M[k][1], g)
        # a breast is shipped whole or not at all: every structure passes and the fat pad keeps at least MIN_VOLUME_RATIO of its HRA volume (below that the page leaves no room for a breast: not a breast any more)
        fat = out["breast_fat_" + side][2]
        ratio = fat["volume_cm3"] / fat["volume_hra_cm3"]
        why = None
        if not all(v[2]["pass"] for v in out.values()):
            why = "a structure failed the signed-distance gates"
        elif ratio < MIN_VOLUME_RATIO:
            why = f"the page leaves room for only {100 * ratio:.0f} % of the library breast volume (minimum {100 * MIN_VOLUME_RATIO:.0f} %)"
        for v in out.values():
            v[2]["volume_ratio_fat_pad"] = round(ratio, 3)
            if why:
                v[2]["pass"] = False; v[2]["held_reason"] = why
        res[side] = dict(parts=out, warp=W.stats, push_history=hist, fat_volume_ratio=round(ratio, 3), held=why)
    return dict(thorax=(T, reg), sides=res)


def fmt_dev(info_s):
    d = info_s["decimation_deviation_mm"]
    return f"{info_s['triangles']} triangles after decimation (surface deviation from the full HRA mesh median {d['median']}, p95 {d['p95']}, max {d['max']} mm)"


def pelvic_badge(sid, info_s, g, reg_txt, who):
    obj = info_s["hra_file"].replace("v1.2_", "").replace("v1.3_", "")
    shape = (f"closed envelope of the HRA surfaces (voxel fill {info_s['voxel_pitch_mm']} mm, {fmt_dev(info_s)}, volume {g['volume_cm3']} cm3; the collapsed canal is shown solid)" if info_s["mode"] == "closed envelope"
             else f"the HRA surface as is ({fmt_dev(info_s)}" + (f", closed, volume {g['volume_cm3']} cm3" if g.get('volume_cm3') else ", an open sheet or cord surface: no volume") + ")")
    ov = ""
    if g.get("overlap_pct_of_volume"):
        ov = " Overlap with the page's own organs: " + ", ".join(f"{k} {v} % of the organ" for k, v in g["overlap_pct_of_volume"].items()) + "."
    elif g["vertices_inside_page_organ_pct"]:
        ov = " Vertices inside the page's own organ meshes: " + ", ".join(f"{k} {v} %" for k, v in g["vertices_inside_page_organ_pct"].items()) + "."
    att = ""
    if g["vertices_within_1mm_of_bone"]:
        att = (f" Its attachment end rests on the bone it attaches to ({g['vertices_within_1mm_of_bone']} vertices within 1 mm); "
               + (f"{g['vertices_moved_out_of_bone']} vertices that the registration error had left inside the bone were moved out along the bone normal by at most {g['max_move_out_of_bone_mm']} mm." if g["vertices_moved_out_of_bone"] else "none had to be moved."))
    return (f"Reference structure of the Visible Human FEMALE frame (HuBMAP HRA 3D reference object `{obj}`, v1.2, CC BY 4.0, HuBMAP CCF 3D Reference Object Library; the library gives no description of how this object was built, "
            f"whereas its uterus, ovary, tube and pelvis records say 'created using data from the Visible Human Female'; it lies in the frame of those objects and touches the uterus of this page), "
            f"NOT measured by this atlas and NOT a segmentation of {who} scan, not hand-drawn here. Placed with the SAME registration as the uterus, ovaries and tubes of this page: {reg_txt}. Shape: {shape}. "
            f"Guards: {g['skin_distance_min_mm']} mm from the skin, signed distance to the nearest bone {g['bone_min_mm']} mm (positive = outside the bone), vertices inside the page's bladder / rectum / sigmoid {g['bladder_rectum_sigmoid_pct_of_vertices']} %.{ov}{att} "
            f"The position of a soft structure also depends on how HRA's source images were registered, so it is a bone-based estimate. {ABSENT}")


def breast_badge(sid, info_s, g, reg, warp, hist, who, body, z=False):
    obj = info_s["hra_file"].replace("v1.3_", "")
    kind = (f"closed envelope of the HRA surface (voxel fill {info_s['voxel_pitch_mm']} mm, {fmt_dev(info_s)})" if info_s["mode"] == "closed envelope"
            else f"the HRA surface as is ({fmt_dev(info_s)})")
    vol = (f" Volume {g['volume_cm3']} cm3 after the fit (HRA original {g['volume_hra_cm3']} cm3)." if g.get("volume_cm3") else " Open surface: no volume.")
    n_push = g["vertices_moved_over_1mm_by_rim_push"]
    if z:
        what = (f"NOT part of Z-Anatomy (Z-Anatomy has no breast tissue: its skin only has a flat 'mammary region' patch), NOT measured by this atlas, and NOT a real breast of {who} body: "
                f"{who} chest skin is nearly flat, whereas the library breast projects up to 40 mm farther forward")
        chest = (f"{body} chest wall (Z-Anatomy ribs, costal cartilage, sternum, clavicle, scapula, pectoralis major and the other muscles, themselves fits to {body} skeleton) and {body} skin")
        vert = f"the Z-Anatomy thoracic vertebrae T1-T12 of {body} body"
        extra = (f" Distances to the Z-Anatomy muscles other than the pectoralis major are reported, not gated (they are fit estimates): {g['other_muscle_min_mm']} mm.")
        oth = ""
    else:
        what = (f"NOT measured by this atlas, NOT a segmentation of {who} scan and NOT {who} breast tissue: {who} chest has no breast label, and the skin over {who} pectoral muscle is nearly flat "
                f"(supine cadaver CT), whereas the library breast projects up to 40 mm farther forward")
        chest = f"{body} chest wall and {body} skin"
        vert = f"{body} thoracic vertebrae"
        extra = ""
        oth = f", other muscles {g['other_muscle_min_mm']} mm"
    return (f"REFERENCE MODEL, NOT donor data: HuBMAP HRA 3D reference object `{obj}` (v1.3, CC BY 4.0, Heidi Schlehlein), which the library describes as 'sculpted from scratch to include relevant anatomy for placement of registration blocks' "
            f"with textbook atlases as the reference (Krstic 1994, Thieme Atlas of Anatomy 2008); it is placed in the Visible Human female's frame but was NOT built from her images. It is {what}. FITTED INTO THE SKIN ENVELOPE in two steps. (1) Registration: the HRA thoracic vertebrae onto {vert} "
            f"(rigid + uniform scale x{reg['scale']}, residual median {reg['residual_mm']['median']} mm, p90 {reg['residual_mm']['p90']}). "
            f"(2) Skin-envelope fit: each anteroposterior column of the breast (all breast structures with the same map) was compressed, only as much as needed, between {chest} "
            f"(median column ratio {warp['ratio_median']:.2f}), then the rim that still overhung the skin or touched a muscle / bone was pushed in by a smooth field ({n_push} of {g['vertices']} vertices of this structure by more than 1 mm, max {g['rim_push_max_mm']} mm). "
            f"The shape is therefore the HRA breast flattened to the space this body leaves, not a measured breast. Shape: {kind}.{vol} Signed distances of every vertex: inside the skin by at least {g['skin_inside_min_mm']} mm "
            f"(median {g['skin_median_mm']} mm), pectoralis major {g['pectoralis_major_min_mm']} mm (positive = anterior to it), ribs / cartilage / sternum / clavicle / scapula at least {g['bone_min_mm']} mm away{oth}.{extra} "
            f"Registration error: bone-based, median {reg['residual_mm']['median']} mm; the fit error of the soft tissue is the compression itself (see volume). {ABSENT}")
