"""Q169: the Visible Human FEMALE's own pelvic viscera -- urinary bladder, rectum and the pelvic part of the
sigmoid colon -- from her TotalSegmentator `total` labels (vhf_total.nii.gz: 21 urinary_bladder, 20 colon).

    python3 scripts/vhf_pelvic_viscera.py --origin '7.769,-885.229,14.137' [--png OUT.png]
    python3 scripts/vhf_pelvic_viscera.py --audit-bundle build/viewer_f_hr/bundle.json

Real data only; every surface is hers. Cut rules, all measured on HER own labels:
  * pelvic inlet plane: through the sacral promontory (anterior-superior edge of her S1 body, label 26, within
    5 mm of the midline) and the upper border of her pubic symphysis (highest hip-bone voxel within 6 mm of the
    midline, anterior half), containing the left-right axis. Colon voxels caudal to it, largest connected piece
    (the one holding the anal end) = rectum + pelvic sigmoid; smaller pieces < 1 % are dropped and reported.
    The sigmoid is taken to begin at the pelvic brim (Michael & Rabi 2015, doi:10.7860/JCDR/2015/13850.6364,
    measure it from the same landmark), so what is shipped is the sigmoid's PELVIC part, named as such.
  * rectum / sigmoid: the "sigmoid take-off" (D'Souza et al. 2019 Delphi consensus, doi:10.1097/SLA.0000000000003251):
    a centreline is traced from the anal end to where the bowel crosses the inlet, with a cost 1/(d+0.5)^2 on the
    distance d (mm) to the bowel wall, so it stays in the lumen and does not short-cut through the places where two
    loops touch (the label merges touching loops). The take-off is the first local maximum of height along it
    (after 60 mm, followed by a >= 5 mm descent): where the bowel stops ascending in the sacral hollow and sweeps
    forward. Voxels are split by a marker watershed on -d seeded by the two halves of the centreline, so the cut
    runs across the tube and touching loops separate at their contact neck.
Surfaces: engine.volume_ingest.mask_surface(step 1, smooth 1.0) -> voxels_to_atlas -> minus the same origin as
every other ct_vhf subject, i.e. exactly what `ingest_volume_geometry.py convert --smooth 1.0` does; this script
writes the subject itself only because these ids have no entity in data/ (the atlas index has no viscera
category, so convert refuses them) -- each structure carries its own category/name, which the exporter reads.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from engine import volume_ingest as vol  # noqa: E402
from engine import vh_ingest as vh  # noqa: E402

SRC = REPO / "data/ct_sources/task_outputs/vhf_total.nii.gz"
OUT_NII = REPO / "data/ct_sources/task_outputs/vhf_pelvic_viscera.nii.gz"
SUBJECT = "ct_vhf_pelvis"
SUBJ_DIR = REPO / "build/vh" / SUBJECT
REPORT = REPO / "data/derived/Q169_vhf_pelvic_viscera.json"
BONES = REPO / "build/vh/ct_vhf"

TS = {"colon": 20, "urinary_bladder": 21, "sacrum": 25, "vertebrae_S1": 26, "hip_left": 77, "hip_right": 78}
LABELS = {1: "urinary_bladder", 2: "rectum", 3: "sigmoid_colon"}
NAMES = {"urinary_bladder": "Urinary bladder", "rectum": "Rectum",
         "sigmoid_colon": "Sigmoid colon (pelvic part, below the pelvic inlet)"}
SPECK_FRAC = 0.01

# Reference ranges. Volumes of these organs depend on filling, so each gate is a plausibility window with its
# basis written out; the length checks are the sharper test of the cut rules.
REFERENCE = {
    "urinary_bladder": {
        "volume_cm3": [5.0, 600.0],
        "basis": "wall plus contents; lower bound a near-empty bladder, upper bound the top of normal adult female "
                 "functional bladder capacity (bladder-diary reference limits in 161 asymptomatic women: Amundsen "
                 "et al. 2007, Neurourol Urodyn 26:341, doi:10.1002/nau.20241). A post-mortem bladder is expected "
                 "near the low end.",
    },
    "rectum": {
        "volume_cm3": [40.0, 400.0],
        "length_mm": [100.0, 180.0],
        "basis": "length: rectum ~12-15 cm from the anorectal junction to the rectosigmoid (Gray's Anatomy, 42nd "
                 "ed.), upper end = sigmoid take-off (D'Souza et al. 2019, Ann Surg 270:955, "
                 "doi:10.1097/SLA.0000000000003251); volume window derived from that length and a 2.5-5.5 cm "
                 "lumen (NOT a published volume range -- no per-segment rectal volume norm was found).",
    },
    "sigmoid_colon": {
        "volume_cm3": [15.0, 300.0],
        "length_mm": [60.0, 280.0],
        "basis": "length of the sigmoid measured from the pelvic brim: 15.2 +- 4.4 cm (Michael & Rabi 2015, J Clin "
                 "Diagn Res 9:AC04, doi:10.7860/JCDR/2015/13850.6364); window = mean -2 SD .. whole-sigmoid "
                 "length (Alatise et al. 2013, Surg Radiol Anat 35:249, doi:10.1007/s00276-012-1037-5, 30.5-67.8 "
                 "cm whole sigmoid). Volume window is a plausibility bound for the pelvic part only.",
    },
    "colon_total": {
        "basis": "fasting MRI in 75 healthy volunteers: ascending 203+-75, transverse 198+-79, descending 160+-86 mL "
                 "(Pritchard et al. 2014, Neurogastroenterol Motil 26:124, doi:10.1111/nmo.12243); her colon above "
                 "the inlet is compared with the sum of those means.",
        "above_inlet_ml_sum_of_means": 561.0,
    },
}


def to_atlas(idx, affine, origin):
    return vol.voxels_to_atlas(np.asarray(idx, dtype=float), affine) - origin


def largest_component(mask):
    lab, n = ndi.label(mask)
    if n == 0:
        return mask, []
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    keep = sizes.argmax()
    dropped = [int(s) for i, s in enumerate(sizes) if i and i != keep and s]
    return lab == keep, dropped


def landmarks(V, A, O):
    s1 = to_atlas(np.argwhere(V == TS["vertebrae_S1"]), A, O)
    mid = s1[np.abs(s1[:, 0]) < 5]
    ant = mid[mid[:, 2] > np.median(mid[:, 2])]
    top = ant[ant[:, 1] > ant[:, 1].max() - 8]
    prom = top[top[:, 2].argmax()]
    hip = to_atlas(np.argwhere((V == TS["hip_left"]) | (V == TS["hip_right"])), A, O)
    near = hip[(np.abs(hip[:, 0]) < 6) & (hip[:, 2] > 0)]
    sym = near[near[:, 1].argmax()]
    d = sym - prom
    n = np.array([0.0, -d[2], d[1]])
    n /= np.linalg.norm(n)
    if n[1] < 0:
        n = -n                                     # normal points cranially
    sac, _ = largest_component((V == TS["sacrum"]) | (V == TS["vertebrae_S1"]))
    sac_pts = to_atlas(np.argwhere(sac), A, O)
    return prom, sym, n, float(sac_pts[:, 1].min())


def split_colon(V, A, O, prom, n, sp):
    import skimage.graph as sg
    from skimage.segmentation import watershed
    colon = V == TS["colon"]
    idx = np.argwhere(colon)
    below = (to_atlas(idx, A, O) - prom) @ n < 0
    mb = np.zeros_like(colon)
    mb[tuple(idx[below].T)] = True
    pelvic, dropped = largest_component(mb)
    pidx = np.argwhere(pelvic)
    lo = pidx.min(0) - 2
    hi = pidx.max(0) + 3
    sl = tuple(slice(a, b) for a, b in zip(lo, hi))
    sub = pelvic[sl]
    dt = ndi.distance_transform_edt(sub, sampling=sp)
    cost = np.where(sub, 1.0 / (dt + 0.5) ** 2, np.inf)
    sidx = np.argwhere(sub)
    Q = to_atlas(sidx + lo, A, O)
    anus = tuple(sidx[Q[:, 1].argmin()])
    mcp = sg.MCP_Geometric(cost, sampling=sp)
    G, _ = mcp.find_costs([anus])
    g = G[tuple(sidx.T)]
    near_plane = (Q - prom) @ n > -3.0
    exit_ = tuple(sidx[near_plane][g[near_plane].argmax()])
    path = np.array(mcp.traceback(exit_))                      # anus -> exit
    P = to_atlas(path + lo, A, O)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    if P[0, 1] > P[-1, 1]:                                     # make sure s runs from the anal end
        path, P = path[::-1], P[::-1]
        s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    Ys = ndi.uniform_filter1d(P[:, 1], 9)
    take = None
    for i in range(len(s)):
        if s[i] < 60:
            continue
        fall = np.nonzero(Ys[i:] < Ys[i] - 5)[0]
        if len(fall) and Ys[i] >= Ys[max(0, i - 5):i + fall[0]].max():
            take = i
            break
    if take is None:
        raise SystemExit("no sigmoid take-off found on the centreline -- the rule does not apply; not splitting")
    mk = np.zeros(sub.shape, np.int32)
    pp = path
    mk[tuple(pp[:take + 1].T)] = 1
    mk[tuple(pp[take + 1:].T)] = 2
    ws = watershed(-dt, mk, mask=sub)
    out = np.zeros(V.shape, np.uint8)
    out[sl][ws == 1] = 2
    out[sl][ws == 2] = 3
    info = {
        "pelvic_colon_specks_dropped_voxels": dropped,
        "anal_end_atlas_mm": P[0].round(1).tolist(),
        "inlet_crossing_atlas_mm": P[-1].round(1).tolist(),
        "centreline_length_mm": round(float(s[-1]), 1),
        "take_off_atlas_mm": P[take].round(1).tolist(),
        "rectum_length_mm": round(float(s[take]), 1),
        "sigmoid_pelvic_length_mm": round(float(s[-1] - s[take]), 1),
        "centreline_atlas_mm": P[::4].round(1).tolist(),
    }
    return out, info


def mesh_mask(mask, A, O, smooth=1.0):
    idx = np.argwhere(mask)
    lo = np.maximum(idx.min(0) - 8, 0)
    hi = np.minimum(idx.max(0) + 9, mask.shape)
    crop = mask[tuple(slice(a, b) for a, b in zip(lo, hi))]
    v, f = vol.mask_surface(crop, step=1, smooth=smooth)
    return to_atlas(v + lo, A, O), f


def mesh_stats(v, f):
    import trimesh
    m = trimesh.Trimesh(v, f, process=False)
    parts = m.split(only_watertight=False)
    return {"triangles": int(len(f)), "mesh_volume_cm3": round(abs(float(m.volume)) / 1000, 2),
            "mesh_components": int(len(parts)), "watertight": bool(m.is_watertight),
            "bbox_min_mm": v.min(0).round(2).tolist(), "bbox_max_mm": v.max(0).round(2).tolist()}


def load_bone(atlas_ids):
    man = json.loads((BONES / "manifest.json").read_text())
    V = np.fromfile(BONES / "vertices.f32", np.float32).reshape(-1, 3)
    F = np.fromfile(BONES / "faces.u32", np.uint32).reshape(-1, 3)
    vs, fs, base = [], [], 0
    for s in man["structures"]:
        if s["atlas_id"] in atlas_ids:
            v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(float)
            f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
            vs.append(v); fs.append(f + base); base += len(v)
    return np.concatenate(vs), np.concatenate(fs)


def containment(v, bones, prom, n):
    """Where a structure sits relative to HER hip bones and sacrum (mesh space, atlas mm)."""
    import trimesh
    from scipy.spatial import cKDTree
    hv = np.concatenate([bones["hip_bone_l"][0], bones["hip_bone_r"][0]])
    sv = bones["sacrum"][0]
    out = {}
    # pelvic box: hip bones laterally/inferiorly, sacrum posteriorly, symphysis anteriorly, inlet superiorly
    box_lo = np.array([hv[:, 0].min(), hv[:, 1].min(), sv[:, 2].min()])
    box_hi = np.array([hv[:, 0].max(), hv[:, 1].max(), hv[:, 2].max()])
    out["margin_to_pelvic_box_mm"] = {
        "right(+X)": round(float(box_hi[0] - v[:, 0].max()), 1), "left(-X)": round(float(v[:, 0].min() - box_lo[0]), 1),
        "superior(+Y, iliac crests)": round(float(box_hi[1] - v[:, 1].max()), 1),
        "inferior(-Y, ischial tuberosities)": round(float(v[:, 1].min() - box_lo[1]), 1),
        "anterior(+Z, pubis)": round(float(box_hi[2] - v[:, 2].max()), 1),
        "posterior(-Z, sacrum)": round(float(v[:, 2].min() - box_lo[2]), 1)}
    out["inside_pelvic_box"] = bool(all(x >= 0 for x in out["margin_to_pelvic_box_mm"].values()))
    sd = (v - prom) @ n
    out["fraction_of_vertices_below_inlet"] = round(float((sd < 0).mean()), 4)
    out["max_height_above_inlet_mm"] = round(float(max(0.0, sd.max())), 1)
    for name, (bv, bf) in bones.items():
        d, _ = cKDTree(bv).query(v)
        m = trimesh.Trimesh(bv, bf, process=False)
        inside = int(m.contains(v[::7]).sum()) if m.is_watertight else None
        out[f"min_surface_distance_to_{name}_mm"] = round(float(d.min()), 1)
        out[f"sampled_vertices_inside_{name}"] = inside
    return out


def render_png(path, meshes, bones):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    import fast_simplification as fs
    col = {"urinary_bladder": "#e0b030", "rectum": "#8b4a2b", "sigmoid_colon": "#3f8f4f"}
    fig = plt.figure(figsize=(16, 9))
    for k, (elev, azim, title) in enumerate(((0, 90, "front, from anterior (her right on the viewer's left)"), (0, 180, "from her left side (anterior to the left)"))):
        ax = fig.add_subplot(1, 2, k + 1, projection="3d")
        for name, (v, f) in list(bones.items()) + list(meshes.items()):
            if len(f) > 20000:
                v, f = fs.simplify(v.astype(np.float32), f.astype(np.int32), 1 - 20000 / len(f))
            # atlas (X right, Y up, Z anterior) -> plot (x, y=depth, z=up)
            P = np.c_[v[:, 0], v[:, 2], v[:, 1]]
            bone = name in bones
            pc = Poly3DCollection(P[f], facecolor="#d9d4c7" if bone else col[name], edgecolor="none",
                                  alpha=0.18 if bone else 0.95, linewidth=0)
            pc.set_zsort("average")
            ax.add_collection3d(pc)
        ax.set_xlim(-150, 150); ax.set_ylim(-150, 150); ax.set_zlim(-100, 200)
        ax.set_box_aspect((300, 300, 300)); ax.view_init(elev=elev, azim=azim)
        ax.set_xlabel("X right (mm)"); ax.set_ylabel("Z anterior"); ax.set_zlabel("Y superior")
        ax.set_title(title)
    fig.suptitle("Q169 VH female: urinary bladder (yellow), rectum (brown), pelvic sigmoid (green) with her hip bones + sacrum")
    plt.tight_layout(); plt.savefig(path, dpi=80); plt.close(fig)


def audit_bundle(bundle_path):
    import trimesh
    b = json.loads(Path(bundle_path).read_text())
    blob = (Path(bundle_path).parent / "bundle.bin").read_bytes()
    q = b.get("quantum_mm", 0.25)
    off, rows = 0, {}
    for e in b["structures"]:
        nv, nf = e["nv"], e["nf"]
        v = np.frombuffer(blob, np.int16, nv * 3, off).reshape(-1, 3) * q; off += nv * 6
        f = np.frombuffer(blob, np.uint16, nf * 3, off).reshape(-1, 3); off += nf * 6
        if e["id"] in LABELS.values():
            m = trimesh.Trimesh(v.astype(float), f.astype(np.int64), process=False)
            parts = m.split(only_watertight=False)
            rows[e["id"]] = {"cat": e["cat"], "subject": e["subject"], "triangles": nf,
                             "pieces": len(parts), "name": e.get("rec", {}).get("name")}
    rep = json.loads(REPORT.read_text())
    rep["bundle_audit"] = {"bundle": str(Path(bundle_path).resolve().relative_to(REPO)), "structures": rows,
                           "bundle_triangles": int(b.get("triangles", 0)), "bundle_structures": len(b["structures"])}
    REPORT.write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep["bundle_audit"], indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--origin")
    ap.add_argument("--png")
    ap.add_argument("--audit-bundle")
    args = ap.parse_args()
    if args.audit_bundle:
        return audit_bundle(args.audit_bundle)
    if not args.origin:
        raise SystemExit("--origin is required (the same value vhf_rebuild_bundle.sh passes every ct_vhf subject)")
    O = vh.parse_origin(args.origin)
    img = nib.load(str(SRC))
    V, A, _codes = vol.load_labels(SRC)
    sp = tuple(float(x) for x in np.sqrt((A[:3, :3] ** 2).sum(0)))
    vox_cm3 = float(abs(np.linalg.det(A[:3, :3]))) / 1000
    prom, sym, n, sac_apex_y = landmarks(V, A, O)

    lab = np.zeros(V.shape, np.uint8)
    bladder, bl_drop = largest_component(V == TS["urinary_bladder"])
    lab[bladder] = 1
    colon_parts, cinfo = split_colon(V, A, O, prom, n, sp)
    lab[colon_parts > 0] = colon_parts[colon_parts > 0]
    out = nib.Nifti1Image(lab, img.affine, header=img.header)
    out.set_data_dtype(np.uint8)
    nib.save(out, str(OUT_NII))

    bones = {"hip_bone_l": load_bone({"hip_bone_l"}), "hip_bone_r": load_bone({"hip_bone_r"}),
             "sacrum": load_bone({"sacrum"})}
    SUBJ_DIR.mkdir(parents=True, exist_ok=True)
    vb, fb, structs, meshes = [], [], [], {}
    vbase = fbase = 0
    per = {}
    for k, name in LABELS.items():
        m = lab == k
        comps = ndi.label(m)[1]
        v, f = mesh_mask(m, A, O)
        meshes[name] = (v, f)
        st = mesh_stats(v, f)
        vol_cm3 = round(float(m.sum()) * vox_cm3, 2)
        ref = REFERENCE[name]
        row = {"label": k, "voxel_volume_cm3": vol_cm3, "voxel_components": int(comps), **st,
               "reference_volume_cm3": ref["volume_cm3"],
               "volume_in_reference_range": bool(ref["volume_cm3"][0] <= vol_cm3 <= ref["volume_cm3"][1]),
               "reference_basis": ref["basis"]}
        if name == "urinary_bladder":
            row["specks_dropped_cm3"] = [round(x * vox_cm3, 3) for x in bl_drop]
        else:
            key = "rectum_length_mm" if name == "rectum" else "sigmoid_pelvic_length_mm"
            row["centreline_length_mm"] = cinfo[key]
            row["reference_length_mm"] = ref["length_mm"]
            row["length_in_reference_range"] = bool(ref["length_mm"][0] <= cinfo[key] <= ref["length_mm"][1])
        row["position"] = containment(v, bones, prom, n)
        per[name] = row
        structs.append({
            "atlas_id": name, "category": "organ", "name": NAMES[name], "region": "pelvis",
            "source_structure": {"urinary_bladder": "urinary_bladder"}.get(name, f"colon ({name} part)"),
            "side": None, "source_file": f"{OUT_NII.name}#{k}",
            "vertex_offset": vbase, "face_offset": fbase, "vertex_count": int(len(v)), "triangle_count": int(len(f)),
            "bbox_min_mm": st["bbox_min_mm"], "bbox_max_mm": st["bbox_max_mm"]})
        vb.append(v.astype(np.float32)); fb.append((f + vbase).astype(np.uint32))
        vbase += len(v); fbase += len(f)
    allv, allf = np.concatenate(vb), np.concatenate(fb)
    (SUBJ_DIR / "vertices.f32").write_bytes(allv.tobytes())
    (SUBJ_DIR / "faces.u32").write_bytes(allf.tobytes())
    (SUBJ_DIR / "manifest.json").write_text(json.dumps({
        "subject": SUBJECT, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
        "source_volume": str(OUT_NII.relative_to(REPO)), "source_kind": "labelled volume (NIfTI)",
        "label_map": "vhf_pelvic_viscera (labels 1 urinary_bladder, 2 rectum, 3 sigmoid_colon)",
        "marching_cubes_step": 1, "surface_smoothing_sigma_voxels": 1.0,
        "vertex_count": int(len(allv)), "triangle_count": int(len(allf)),
        "bbox_min_mm": allv.min(0).round(4).tolist(), "bbox_max_mm": allv.max(0).round(4).tolist(),
        "attribution": ["Visible Human female CT (U.S. National Library of Medicine, public domain, via the NCI "
                        "Imaging Data Commons); TotalSegmentator v2 `total` labels; rectum/sigmoid split and pelvic "
                        "cut by scripts/vhf_pelvic_viscera.py (Q169)."],
        "structures": structs}, indent=2))

    colon_all = float((V == TS["colon"]).sum()) * vox_cm3
    pelvic = per["rectum"]["voxel_volume_cm3"] + per["sigmoid_colon"]["voxel_volume_cm3"]
    report = {
        "source": "U.S. National Library of Medicine, The Visible Human Project (public domain), FEMALE CT via the "
                  "NCI Imaging Data Commons; TotalSegmentator v2 `total` task labels "
                  "(data/ct_sources/task_outputs/vhf_total.nii.gz: 21 urinary_bladder, 20 colon). References: "
                  "D'Souza 2019 doi:10.1097/SLA.0000000000003251; Michael & Rabi 2015 doi:10.7860/JCDR/2015/13850.6364; "
                  "Alatise 2013 doi:10.1007/s00276-012-1037-5; Pritchard 2014 doi:10.1111/nmo.12243; Amundsen 2007 "
                  "doi:10.1002/nau.20241.",
        "task": "Q169", "subject": SUBJECT, "script": "scripts/vhf_pelvic_viscera.py",
        "label_volume": str(OUT_NII.relative_to(REPO)), "origin_atlas_mm": O.tolist(),
        "cut_rules": {
            "pelvic_inlet_plane": "through her sacral promontory and the upper border of her pubic symphysis, "
                                  "containing the left-right axis; colon caudal to it = rectum + pelvic sigmoid",
            "rectum_sigmoid": "sigmoid take-off: first local height maximum along a lumen-seeking centreline from "
                              "the anal end (after 60 mm, then >= 5 mm descent); marker watershed on -distance",
        },
        "landmarks_atlas_mm": {"sacral_promontory": prom.round(1).tolist(), "symphysis_upper_border": sym.round(1).tolist(),
                               "inlet_normal": n.round(4).tolist(),
                               "inlet_angle_to_horizontal_deg": round(float(np.degrees(np.arctan2(abs(sym[1] - prom[1]), abs(sym[2] - prom[2])))), 1),
                               "obstetric_conjugate_mm": round(float(np.linalg.norm(sym - prom)), 1),
                               "sacral_apex_y_mm": round(sac_apex_y, 1),
                               "take_off_fraction_of_sacral_height_from_promontory":
                                   round(float((prom[1] - cinfo["take_off_atlas_mm"][1]) / (prom[1] - sac_apex_y)), 3)},
        "colon": {**{k: v for k, v in cinfo.items() if k != "pelvic_colon_specks_dropped_voxels"},
                  "pelvic_colon_specks_dropped_cm3": [round(x * vox_cm3, 3) for x in cinfo["pelvic_colon_specks_dropped_voxels"]],
                  "speck_rule": f"pieces < {SPECK_FRAC:.0%} of the structure dropped",
                  "whole_colon_label_cm3": round(colon_all, 1), "pelvic_colon_cm3": round(pelvic, 1),
                  "colon_above_inlet_cm3": round(colon_all - pelvic, 1),
                  "above_inlet_vs_reference_sum_of_means_ml": REFERENCE["colon_total"]["above_inlet_ml_sum_of_means"],
                  "reference_basis": REFERENCE["colon_total"]["basis"]},
        "structures": per,
    }
    for name, d in (("bladder", bl_drop), ("pelvic colon", cinfo["pelvic_colon_specks_dropped_voxels"])):
        big = [x for x in d if x * vox_cm3 >= SPECK_FRAC * (per["urinary_bladder"]["voxel_volume_cm3"] if name == "bladder" else pelvic)]
        if big:
            raise SystemExit(f"{name}: a dropped piece is >= 1% of the structure ({big}) -- not a speck; stop")
    if args.png:
        render_png(args.png, meshes, bones)
        report["check_png"] = "scratchpad (not committed)"
    REPORT.write_text(json.dumps(report, indent=1))
    for k, r in per.items():
        print(f"{k:16s} {r['voxel_volume_cm3']:7.1f} cm3  comps {r['voxel_components']}/{r['mesh_components']}  "
              f"tris {r['triangles']}  in_box {r['position']['inside_pelvic_box']}")
    print(f"wrote {SUBJ_DIR} {OUT_NII.relative_to(REPO)} {REPORT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
