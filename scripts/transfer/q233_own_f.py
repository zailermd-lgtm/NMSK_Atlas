#!/usr/bin/env python3
"""Q233 (own female): her Q224 bundle -> build/viewer_f_hr_q233.
 (1) REMOVES the male coccyx that Q44 transferred onto her (subject xfer_vhm2vhf, a second coccyx 13 mm below her own, which her CT sacrum label already contains: the HRA VH_F coccyx
     of the same donor coincides with the tail of her sacrum mesh within 2 mm) -- sex-specific wrong-sex structure.
 (2) ADDS her uterus (with cervix), both ovaries and both uterine tubes: the HuBMAP HRA 3D reference organs of the SAME DONOR (Visible Human female, CC BY 4.0), registered onto her own CT pelvis by
     rigid + uniform-scale ICP, closed envelopes (voxel fill), guarded (inside skin, out of bone, out of her bladder / rectum / sigmoid / levator ani). Her CT has no uterus / ovary / tube label.
 Every other entry is byte-identical (ship diff written to data/derived/Q233_vertex_diff_f.json, exit 1 on any unlisted change).
    python3 scripts/transfer/q233_own_f.py [--out build/viewer_f_hr_q233]"""
from __future__ import annotations
import argparse, json, sys, copy
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.anatomy.q233 import hra_register as H  # noqa: E402

SUBJECT = "xfer_hra2vhf_q233"
ATTR = ("HuBMAP Human Reference Atlas, 3D Reference Object Library v1.3 (CC BY 4.0), Kristen Browne and Heidi Schlehlein, created from the National Library of Medicine Visible Human FEMALE data "
        "(VH_F_Uterus, VH_F_Ovary_L/R, VH_F_Fallopian_Tube_L/R, VH_F_Pelvis; https://humanatlas.io/3d-reference-library, DOI 10.48539/HBM228.JBNJ.299): the same donor as this page. "
        "Registered onto her own CT pelvis by this atlas (Q233); derived data, CC BY 4.0 attribution kept (third_party/hra_vh_f/NOTICE.md).")
ORGANS = [  # id, HRA object, side, name, latin, voxel pitch mm, closing, target triangles
    ("uterus", "VH_F_Uterus", None, "Uterus (with cervix)", "Uterus", 0.6, 2, 9000),
    ("ovary_l", "VH_F_Ovary_L", "left", "Ovary (left)", "Ovarium sinistrum", 0.4, 1, 1400),
    ("ovary_r", "VH_F_Ovary_R", "right", "Ovary (right)", "Ovarium dextrum", 0.4, 1, 1400),
    ("uterine_tube_l", "VH_F_Fallopian_Tube_L", "left", "Uterine tube (left)", "Tuba uterina sinistra", 0.4, 1, 14000),
    ("uterine_tube_r", "VH_F_Fallopian_Tube_R", "right", "Uterine tube (right)", "Tuba uterina dextra", 0.4, 1, 14000),
]


def decimate(v, f, n):
    import fast_simplification as fs
    if len(f) <= n:
        return v, f
    v2, f2 = fs.simplify(np.asarray(v, np.float32), np.asarray(f, np.int32), target_count=n, agg=5)
    return np.asarray(v2, float), np.asarray(f2)


def mask_of(v, f, lo, shape, pitch):
    g = np.zeros(shape, bool)
    m = trimesh.Trimesh(v, f, process=False)
    pts = m.sample(int(m.area / (pitch * pitch * 0.15)) + 3000)
    idx = np.floor((pts - lo) / pitch).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(shape)), axis=1)
    g[tuple(idx[ok].T)] = True
    return ndi.binary_fill_holes(ndi.binary_closing(g, iterations=2))


def own_meshes(B, ids):
    out = {}
    for it in B.items:
        i = it["e"]["id"]
        if i in ids:
            v, f = B.mesh(it)
            out.setdefault(i, []).append((v, f))
    return out


def keyed(B):
    seen, out, order = {}, {}, []
    for it in B.items:
        i = it["e"]["id"]; k = (i, seen.get(i, 0)); seen[i] = seen.get(i, 0) + 1; out[k] = it; order.append(k)
    return out, order


def main(out_dir):
    src = REPO / "build/viewer_f_hr_q224"
    B = Bundle(src)
    A0 = Bundle(src)
    # ---- evidence: her bones as a surface point set
    bone_pts, bone_meshes = [], []
    for it in B.items:
        e = it["e"]
        if e["cat"] == "bone" and e["id"].split("#")[0] in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx") and "zfill" not in e["id"] and e["subject"] != "xfer_vhm2vhf":
            v, f = B.mesh(it)
            m = trimesh.Trimesh(v, f, process=False)
            m = max(m.split(only_watertight=False), key=lambda c: len(c.vertices))
            if len(m.vertices) < 1000:
                continue
            bone_pts.append(m.sample(40000))
    dst = np.vstack(bone_pts)
    pel = H.hra_mesh("VH_F_Pelvis")
    srcp = np.vstack([trimesh.Trimesh(v, f, process=False).sample(max(200, len(f) // 3)) for _, v, f in pel])
    tree = cKDTree(dst)
    s, R, t, d = H.icp(srcp, tree, dst)
    T = (s, R, t)
    reg = dict(scale=round(float(s), 5), rotation=R.round(6).tolist(), translation_mm=t.round(3).tolist(), n_source=int(len(srcp)), n_target=int(len(dst)),
               residual_mm=dict(median=round(float(np.median(d)), 2), p90=round(float(np.quantile(d, .9)), 2), rms=round(float(np.sqrt((d ** 2).mean())), 2), max=round(float(d.max()), 1)),
               det_R=round(float(np.linalg.det(R)), 4))
    # cross-check with the HRA pelvis' own parts: sacrum / coccyx / hip bones separately
    parts = {}
    for n_, v, f in pel:
        key = "coccyx" if "coccyx" in n_ else "sacrum" if "sacrum" in n_ else "hip_bone"
        dd = tree.query(H.apply(T, v))[0]
        parts.setdefault(key, []).append(dd)
    reg["residual_by_part_mm_median"] = {k: round(float(np.median(np.concatenate(v))), 2) for k, v in parts.items()}
    print("registration", reg["scale"], reg["residual_mm"], reg["residual_by_part_mm_median"], flush=True)
    # ---- evidence for the guards
    ev_ids = ("urinary_bladder", "rectum", "sigmoid_colon", "levator_ani_l", "levator_ani_r", "coccygeus_l", "coccygeus_r")
    ev = own_meshes(B, set(ev_ids) | {"skin"})
    skin = trimesh.Trimesh(*ev["skin"][0], process=False)
    bone_tree = cKDTree(dst)
    lo = np.array([-100, -80, -130.]); pitch = 1.0; shape = (200, 220, 240)
    evm = {i: mask_of(*ev[i][0], lo, shape, pitch) for i in ev_ids if i in ev}
    bonem = np.zeros(shape, bool)
    for it in B.items:
        e = it["e"]
        if e["cat"] == "bone" and e["id"].split("#")[0] in ("hip_bone_l", "hip_bone_r", "sacrum"):
            bonem |= mask_of(*B.mesh(it), lo, shape, pitch) & False  # placeholder (hollow bone shells are not filled reliably): bone is checked by surface distance below
    # ---- build the organs
    new, report = [], {}
    for sid, obj, side, name, latin, pitch_o, clo, ntri in ORGANS:
        V, F, info = H.closed_surface(H.parts_world(obj, T), pitch=pitch_o, close_it=clo)
        V, F = decimate(V, F, ntri)
        m = trimesh.Trimesh(V, F, process=True)
        trimesh.repair.fix_normals(m)
        V, F = np.asarray(m.vertices), np.asarray(m.faces)
        vol = float(abs(m.volume)) / 1000
        dmin, dmed = B._depth(V)
        db = bone_tree.query(V)[0]
        mk = mask_of(V, F, lo, shape, pitch)
        ov = {i: round(float((mk & g).sum()) * pitch ** 3 / 1000, 3) for i, g in evm.items() if (mk & g).sum()}
        inside_skin = bool(skin.contains(V[:: max(1, len(V) // 800)]).all())
        gates = dict(inside_skin=inside_skin, skin_depth_min_mm=dmin, bone_min_mm=round(float(db.min()), 2), vertices_within_1mm_of_bone=int((db < 1.0).sum()),
                     overlap_cm3=ov, overlap_total_pct=round(100 * sum(ov.values()) / max(vol, 1e-9), 2), watertight=bool(m.is_watertight), triangles=int(len(F)), volume_cm3=round(vol, 2))
        gates["pass"] = bool(inside_skin and gates["bone_min_mm"] >= 0.5 and gates["overlap_total_pct"] <= 5.0 and len(V) < 65000)
        report[sid] = dict(hra_object=obj, envelope=info, gates=gates)
        print(sid, gates, flush=True)
        if not gates["pass"]:
            report[sid]["held"] = True
            continue
        badge = (f"Reference organ of the SAME DONOR, NOT measured by this atlas: the HuBMAP Human Reference Atlas 3D reference object `{obj}` (v1.3, CC BY 4.0, Browne and Schlehlein, built from the National Library of "
                 f"Medicine Visible Human FEMALE data). Her own CT has no label for the uterus, ovaries or uterine tubes, so this is NOT a segmentation of her CT and NOT hand-drawn here. Placed on her by registering the HRA "
                 f"VH_F pelvis onto her own CT pelvis (hip bones, sacrum and coccyx): rigid + uniform scale x{reg['scale']}, {reg['n_target']} target samples, surface residual median {reg['residual_mm']['median']} mm "
                 f"(p90 {reg['residual_mm']['p90']}, rms {reg['residual_mm']['rms']}), a bone-based estimate: the position of a soft organ also depends on how HRA's source images were registered, "
                 f"and the same donor's bladder differs between the HRA mesh and her CT labels (HRA bladder 13 cm3 vs 44 cm3 on her CT). Shape: closed envelope of the HRA surfaces "
                 f"(voxel fill {info['pitch_mm']} mm, {len(F)} triangles after decimation, volume {gates['volume_cm3']} cm3; hollow structures are shown solid; surface within {info['closed_surface_to_source_mm']['p95']} mm (p95) "
                 f"of the HRA surfaces). Guards passed: inside her skin ({dmin} mm from it), {gates['bone_min_mm']} mm from her bones, overlap with her bladder / rectum / sigmoid / levator ani "
                 f"{gates['overlap_total_pct']} % of its volume. She was 59 y (postmenopausal): no published postmenopausal volume number was read in an abstract, so the size is not checked against a norm "
                 f"(the literature only shows that uterine and ovarian size fall after menopause). The vagina, vulva and ligaments of the uterus / ovary are NOT in the HRA set and not built.")
        rec = dict(name=name, latin=latin, folder="viscera", region="pelvis", source="HuBMAP HRA 3D Reference Object Library v1.3 (CC BY 4.0), Visible Human female; registered on her CT pelvis (Q233)",
                   procedural_badge=badge)
        new.append((sid, "organ", side, rec, V, F))
    # ---- apply
    removed = []
    for i, it in enumerate(list(B.items)):
        if it["e"]["id"] == "coccyx" and it["e"]["subject"] == "xfer_vhm2vhf":
            removed.append(dict(id="coccyx", subject=it["e"]["subject"], triangles=int(it["e"]["nf"])))
            B.items.remove(it)
    for sid, cat, side, rec, V, F in new:
        B.add(sid, cat, side, SUBJECT, rec, V, F)
    # card-only note on her sacrum (her CT sacrum label contains her own coccyx)
    card_only = []
    for it in B.items:
        e = it["e"]
        if e["id"] == "sacrum" and e["subject"] == "ct_vhf" and e["nf"] > 5000:
            e["rec"] = {**e["rec"], "procedural_badge": (e["rec"].get("procedural_badge", "") + " Q233: this mesh includes her own coccyx (the tail below the sacral apex; the HRA VH_F coccyx of the same donor lies within "
                        f"{reg['residual_by_part_mm_median'].get('coccyx')} mm of it). The separate `coccyx` entry that Q44 had transferred from the MALE body (a second, male-derived coccyx 13 mm lower) was removed in Q233.").strip()}
            card_only.append("sacrum")
            break
    n_bytes = B.write(out_dir, new_subject_attribution={SUBJECT: ATTR}, copy_clinical=True)
    # ---- ship diff
    N = Bundle(out_dir)
    Ak, Ao = keyed(A0); Nk, No = keyed(N)
    ident, unlisted, bad = 0, [], []
    for k in Ao:
        if k[0] == "coccyx" and Ak[k]["e"]["subject"] == "xfer_vhm2vhf":
            continue
        if k not in Nk:
            bad.append(f"{k} missing"); continue
        a, n = Ak[k], Nk[k]
        if a["raw"] == n["raw"] and a["e"] == n["e"]:
            ident += 1
        elif a["raw"] == n["raw"] and k[0] in card_only:
            pass
        else:
            unlisted.append(k[0])
    added = [k[0] for k in Nk if k not in Ak]
    diff = dict(source="build/viewer_f_hr_q224", new=str(Path(out_dir)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, removed=removed, added=added, card_only=card_only,
                unlisted_changes=unlisted, problems=bad, triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"])
    (REPO / "data/derived/Q233_vertex_diff_f.json").write_text(json.dumps(diff, indent=1) + "\n")
    rep = dict(registration=reg, organs=report, removed=removed, subject=SUBJECT, attribution=ATTR, hra_commit="b036a91aaf7234f462b1249d4a5f4fb0e982f412", hra_files="third_party/hra_vh_f")
    (REPO / "data/derived/Q233_report_own_f.json").write_text(json.dumps(rep, indent=1, default=float) + "\n")
    (REPO / "data/derived/Q233_hra_to_vhf_transform.json").write_text(json.dumps(reg, indent=1) + "\n")
    print("ship diff:", {k: (v if not isinstance(v, list) else len(v)) for k, v in diff.items() if k in ("entries_old", "entries_new", "identical", "removed", "added", "card_only", "unlisted_changes", "problems")})
    sys.exit(1 if (unlisted or bad) else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default=str(REPO / "build/viewer_f_hr_q233")); a = ap.parse_args()
    main(a.out)
