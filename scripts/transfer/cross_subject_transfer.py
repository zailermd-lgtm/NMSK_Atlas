"""Carry structures one Visible Human body has onto the other, driven by bones.

    python3 scripts/transfer/cross_subject_transfer.py --direction m2f \
        --male-html MALE_VIEWER.html --female-bundle build/viewer_f \
        --anthro data/derived/subject_anthropometrics.json \
        --skin-nii SKIN_LABEL.nii.gz --skin-origin 'x,y,z' \
        -o build/vh/xfer_vhm2vhf

The two donors are not the same size or build (see subject_anthropometrics),
so a structure is never copied across at its own coordinates. Every vertex
is moved by a blend of per-bone affines: each bone shared by both bodies has
a frame (principal axes, extents, centre) on each body, and the affine that
takes the source bone's box onto the target's is applied to the soft tissue
near it, weighted by inverse-square distance to the three nearest bones of
the same side. Bones, cartilage and ligaments get that and nothing else.
Muscles additionally get a transverse bulk factor (measured lean-tissue
cross-section of the target over the source, after the bone scaling), so
the female's thigh muscles are not the male's simply shrunk to her femur.

What comes out is an ESTIMATE of where the structure lies on the target
body, badged as such in the viewer (subject `xfer_...`), never fused with
her own measured structures. Write-up in docs/GEOMETRY_SOURCES.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_html, read_bundle_dir, meshes_by_id, mesh_volume_cm3  # noqa: E402
from scripts.transfer.bone_frames import bone_frame, bone_affine, apply  # noqa: E402
from scripts.transfer import lean_envelope as le  # noqa: E402

# bones whose distal end lies outside one of the CT fields of view: mapped by a
# similarity fitted to the proximal 200 mm, so the missing end does not scale the arm
TRUNCATED = {"humerus_r", "humerus_l", "radius_r", "ulna_r", "radius_l", "ulna_l"}
K_NEAREST = 3
SOFTEN_MM = 8.0
MIN_VERTICES = 64      # smaller source pieces are label fragments (the female's 'temporal'/'zygomatic' are 2 mm boxes)
SKIP_IDS = {"skin"}

# which bones may drive a structure, by the atlas region of the structure: the
# male's right hand lies beside his thigh, and must not carry thigh muscles
LOWER = {"hip_bone_r", "hip_bone_l", "sacrum", "coccyx", "lumbar_vertebrae", "femur_r", "femur_l", "patella_r",
         "patella_l", "tibia_r", "tibia_l", "fibula_r", "fibula_l", "tarsals_r", "tarsals_l", "metatarsals_r",
         "metatarsals_l", "phalanges_foot_r", "phalanges_foot_l"}
UPPER = {"humerus_r", "humerus_l", "radius_r", "radius_l", "ulna_r", "ulna_l", "carpals_r", "carpals_l",
         "metacarpals_r", "metacarpals_l", "phalanges_hand_r", "phalanges_hand_l", "scapula_r", "scapula_l",
         "clavicle_r", "clavicle_l"}
AXIAL = {"cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae", "sacrum", "coccyx", "ribs_r", "ribs_l",
         "sternum", "hip_bone_r", "hip_bone_l", "scapula_r", "scapula_l", "clavicle_r", "clavicle_l",
         "cranium", "mandible", "hyoid"}
HEADNECK = {"cranium", "mandible", "hyoid", "cervical_vertebrae", "thoracic_vertebrae", "clavicle_r", "clavicle_l",
            "sternum", "ribs_r", "ribs_l", "scapula_r", "scapula_l"}
REGION_BONES = {"lower_limb": LOWER, "knee": LOWER, "hip": LOWER, "ankle": LOWER, "pelvic_girdle": LOWER,
                "upper_limb": UPPER | {"ribs_r", "ribs_l"}, "pectoral_girdle": UPPER | AXIAL,
                "trunk": AXIAL, "vertebral_column": AXIAL, "thoracic_cage": AXIAL,
                "head": HEADNECK, "neck": HEADNECK, "cranium_face": HEADNECK, "hyoid": HEADNECK, None: HEADNECK}
BULK_GROUP = {"lower_limb": "lower_limb", "knee": "lower_limb", "hip": "lower_limb", "ankle": "lower_limb"}

# structures with no driving bone on the target body
NOT_TRANSFERABLE = {
    "m2f": {k: "the female's left forearm and hand lie outside her CT field of view; no bone on that side to drive them"
            for k in ("carpals_l", "metacarpals_l", "phalanges_hand_l", "radius_l", "ulna_l")},
    "f2m": {},
}
SOURCE_TRUST = {"vhm_both": "manual segmentation of his cryosections (DU release)",
                "ct_vhm_pmr": "RULE-BASED on the male (position rules on his photographs)",
                "ct_vhm_armm": "RULE-BASED on the male (compartment rules on his photographs)",
                "ct_vhm_abw": "RULE-BASED on the male (depth-fraction rules on his photographs)",
                "ct_vhm_delt": "RULE-BASED on the male", "ct_vhm_cuff": "RULE-BASED on the male",
                "ct_vhm_es": "RULE-BASED on the male", "ct_vhm_arm": "CT + photograph watershed on the male"}


def side_of(aid, m):
    s = m.get("side")
    if s in ("right", "left"):
        return s
    return "right" if aid.endswith("_r") else "left" if aid.endswith("_l") else None


def build_bone_maps(src, dst):
    maps = {}
    for aid, m in src.items():
        if m["cat"] != "bone" or aid not in dst or dst[aid]["cat"] != "bone":
            continue
        clip = 200.0 if aid in TRUNCATED else None
        fs, fd = bone_frame(m["v"], clip), bone_frame(dst[aid]["v"], clip)
        A, t = bone_affine(fs, fd, uniform=aid in TRUNCATED)
        maps[aid] = {"A": A, "t": t, "side": side_of(aid, m), "tree": cKDTree(m["v"]),
                     "det": float(np.linalg.det(A)), "src": fs, "dst": fd}
    return maps


def blend_transfer(v, maps, side, region=None):
    allowed = REGION_BONES.get(region, set(maps))
    cands = [b for b, mp in maps.items()
             if b in allowed and (mp["side"] is None or side is None or mp["side"] == side)]
    if not cands:
        cands = list(maps)
    D = np.stack([maps[b]["tree"].query(v)[0] for b in cands], axis=1)          # (n, nb)
    order = np.argsort(D, axis=1)[:, :K_NEAREST]
    w = 1.0 / (np.take_along_axis(D, order, 1) + SOFTEN_MM) ** 2
    w /= w.sum(axis=1, keepdims=True)
    out = np.zeros_like(v, dtype=np.float64)
    used = {}
    for j in range(order.shape[1]):
        for bi in np.unique(order[:, j]):
            sel = order[:, j] == bi
            b = cands[bi]
            out[sel] += w[sel, j:j + 1] * apply(maps[b]["A"], maps[b]["t"], v[sel])
            used[b] = used.get(b, 0.0) + float(w[sel, j].sum())
    tot = sum(used.values())
    return out, {b: round(x / tot, 3) for b, x in sorted(used.items(), key=lambda kv: -kv[1])[:4]}


def transverse_scale(v, f):
    """Scale a mesh about its own long axis (through the centroid) by f."""
    c = v.mean(axis=0); X = v - c
    w, R = np.linalg.eigh(X.T @ X)
    ax = R[:, -1]
    along = X @ ax
    perp = X - np.outer(along, ax)
    return c + np.outer(along, ax) + f * perp


def section_area_cm2(v, f, y):
    import trimesh
    tm = trimesh.Trimesh(v, f, process=False)
    s = tm.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return 0.0
    p2, _ = s.to_2D()
    return float(sum(p.area for p in p2.polygons_full)) / 100.0


def fill_correction(entries, anthro, dst_name, knee_y):
    """After the envelope step the transferred muscles fill the target's muscle compartment the way the
    donor's fill his. The target's photographs say how much of that compartment is muscle tissue (the
    rest is fat between and inside the bellies), so each muscle is scaled about its own axis by
    sqrt(measured muscle area / transferred muscle area) at matched levels: thigh and calf separately."""
    who = "female" if dst_name == "vhf" else "male"
    cc = (anthro.get("measured", {}).get(who, {}).get("cryo_classes") or {})
    lv = anthro.get("limb_levels_y_mm", {}).get(who) or {}
    groups = {"thigh": ["thigh_45pct_femur", "thigh_70pct_femur"], "calf": ["calf_mid_tibia"]}
    factors, detail = {}, {}
    for g, names in groups.items():
        meas, got = [], []
        for n in names:
            if n not in cc or n not in lv:
                continue
            y = lv[n]
            a = sum(section_area_cm2(e["v"], e["f"], y) for e in entries)
            meas.append(cc[n]["muscle_area_cm2"]); got.append(a)
            detail[n] = {"y": round(y, 1), "measured_muscle_cm2": cc[n]["muscle_area_cm2"], "transferred_cm2": round(a, 1)}
        if meas and sum(got) > 0:
            factors[g] = float(np.sqrt(sum(meas) / sum(got)))
    return factors, detail


def skin_lookup(path, origin):
    import nibabel as nib
    im = nib.load(path); vol = np.asanyarray(im.dataobj) > 0
    inv = np.linalg.inv(im.affine); o = np.array([float(t) for t in origin.split(",")])

    def inside(pts):
        ras = np.stack([pts[:, 0] + o[0], pts[:, 2] + o[2], pts[:, 1] + o[1]], axis=1)
        ijk = np.rint((inv[:3, :3] @ ras.T).T + inv[:3, 3]).astype(int)
        ok = np.all((ijk >= 0) & (ijk < np.array(vol.shape)), axis=1)
        res = np.zeros(len(pts), bool)
        res[ok] = vol[ijk[ok, 0], ijk[ok, 1], ijk[ok, 2]]
        return res, ok
    return inside


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--direction", choices=["m2f", "f2m"], required=True)
    ap.add_argument("--male-html", required=True)
    ap.add_argument("--female-bundle", default="build/viewer_f")
    ap.add_argument("--anthro", default="data/derived/subject_anthropometrics.json")
    ap.add_argument("--bulk", type=float, default=None,
                    help="transverse bulk factor for lower-limb muscles (default: the anthropometrics file's "
                         "muscle_bulk_transverse[direction]['lower_limb']; 1.0 if absent). Trunk, neck and "
                         "upper-limb muscles use ['default'] (1.0 unless the file says otherwise).")
    ap.add_argument("--ids", nargs="*", help="restrict to these atlas ids (default: every id the target lacks)")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--skin-nii"); ap.add_argument("--skin-origin")
    ap.add_argument("--envelope-src"); ap.add_argument("--envelope-dst",
                    help="lean-envelope tables (scripts/transfer/build_envelopes.py); with both given, lower-limb "
                         "muscles are re-placed radially inside the target's muscle compartment instead of the bulk factor")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    mp = Path(a.male_html); bm, blob = read_bundle_dir(mp) if mp.is_dir() else read_bundle_html(mp); M = meshes_by_id(bm, blob)
    bf, blobf = read_bundle_dir(a.female_bundle); F = meshes_by_id(bf, blobf)
    src, dst = (M, F) if a.direction == "m2f" else (F, M)
    src_name, dst_name = ("vhm", "vhf") if a.direction == "m2f" else ("vhf", "vhm")
    anthro = json.loads(Path(a.anthro).read_text()) if Path(a.anthro).exists() else {}
    bulk_cfg = anthro.get("muscle_bulk_transverse", {}).get(a.direction, {})
    bulk = {"lower_limb": a.bulk if a.bulk is not None else float(bulk_cfg.get("lower_limb", 1.0)),
            "default": float(bulk_cfg.get("default", 1.0))}

    maps = build_bone_maps(src, dst)
    ids = a.ids or sorted(k for k in src if k not in dst and k not in SKIP_IDS)
    blocked = dict(NOT_TRANSFERABLE[a.direction]); blocked.update({i: "excluded on the command line" for i in a.exclude})
    skipped = {i: blocked[i] for i in ids if i in blocked}
    ids = [i for i in ids if i not in blocked]
    inside = skin_lookup(a.skin_nii, a.skin_origin) if a.skin_nii else None
    env_src = le.load(a.envelope_src) if a.envelope_src else None
    env_dst = le.load(a.envelope_dst) if a.envelope_dst else None
    if env_src and env_dst:
        bulk["lower_limb"] = 1.0

    verts, faces, structures, report = [], [], [], []
    voff = 0
    staged = []
    for aid in ids:
        m = src[aid]
        v = m["v"].astype(np.float64); f = m["f"]
        if len(v) < MIN_VERTICES:
            skipped[aid] = f"degenerate on the source body ({len(v)} vertices, {mesh_volume_cm3(v, f):.2f} cm3): a fragment, not a structure"
            continue
        side = side_of(aid, m)
        region = (m.get("rec") or {}).get("region")
        nv, used = blend_transfer(v, maps, side, region)
        factor = bulk[BULK_GROUP.get(region, "default")] if m["cat"] == "muscle" else 1.0
        if factor != 1.0:
            nv = transverse_scale(nv, factor)
        env_frac = None
        if env_src and env_dst and m["cat"] == "muscle" and BULK_GROUP.get(region) == "lower_limb" and side:
            nv, env_frac = le.apply_envelope(v, nv, env_src[side], env_dst[side])
        staged.append([aid, m, v, f, nv, used, factor, env_frac, side, region])
    # fill correction on the envelope-mapped lower-limb muscles (needs them all first)
    fill, fill_detail = {}, {}
    if env_src and env_dst:
        knee = None
        ents = [{"v": st[4], "f": st[3]} for st in staged if st[7] is not None]
        fill, fill_detail = fill_correction(ents, anthro, dst_name, knee)
        kn = float(np.mean([dst[f"femur_{s}"]["v"][:, 1].min() for s in "rl"])) if "femur_r" in dst else -400.0
        for st in staged:
            if st[7] is None:
                continue
            g = "thigh" if st[4][:, 1].mean() > kn else "calf"
            if g in fill:
                st[4] = transverse_scale(st[4], fill[g]); st[6] = round(fill[g], 3)
    for aid, m, v, f, nv, used, factor, env_frac, side, region in staged:
        disp = np.linalg.norm(nv - v, axis=1)
        row = {"atlas_id": aid, "category": m["cat"], "side": side, "source_subject": m["subject"],
               "source_trust": SOURCE_TRUST.get(m["subject"], "model segmentation of the source CT"),
               "region": region, "driving_bones": used, "bulk_transverse": factor,
               "lean_envelope": env_frac is not None, "mean_radial_fraction_src": None if env_frac is None else round(env_frac, 3),
               "volume_src_cm3": round(mesh_volume_cm3(v, f), 1), "volume_out_cm3": round(mesh_volume_cm3(nv, f), 1),
               "displacement_mm_median": round(float(np.median(disp)), 1)}
        if inside is not None:
            ins, ok = inside(nv)
            row["outside_target_skin_fraction"] = round(float((~ins & ok).sum() / max(ok.sum(), 1)), 3)
        report.append(row)
        nv32 = nv.astype(np.float32)
        structures.append({"atlas_id": aid, "source_structure": aid, "side": side,
                           "source_file": f"{src_name} viewer bundle#{aid}",
                           "vertex_offset": voff, "face_offset": sum(len(x) for x in faces),
                           "vertex_count": int(len(nv32)), "triangle_count": int(len(f)),
                           "bbox_min_mm": [round(float(x), 4) for x in nv32.min(axis=0)],
                           "bbox_max_mm": [round(float(x), 4) for x in nv32.max(axis=0)],
                           "transfer": {"from": m["subject"], "source_trust": SOURCE_TRUST.get(m["subject"], "model segmentation of the source CT"),
                                        "driving_bones": used, "bulk_transverse": factor,
                                        "lean_envelope": env_frac is not None}})
        verts.append(nv32); faces.append((f + voff).astype(np.uint32)); voff += len(nv32)

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    V = np.concatenate(verts) if verts else np.zeros((0, 3), np.float32)
    Fc = np.concatenate(faces) if faces else np.zeros((0, 3), np.uint32)
    V.astype(np.float32).tofile(out / "vertices.f32"); Fc.astype(np.uint32).tofile(out / "faces.u32")
    subject = out.name
    attribution = [
        f"TRANSFERRED, NOT MEASURED ON THIS BODY: geometry from the Visible Human {'male' if a.direction == 'm2f' else 'female'} "
        f"carried onto the {'female' if a.direction == 'm2f' else 'male'} by bone-driven piecewise affine maps "
        f"(scripts/transfer/cross_subject_transfer.py); lower-limb muscles "
        + ("re-placed radially inside this body's measured muscle compartment (lean envelope from her cryosections)"
           if env_src and env_dst else f"scaled transversely by {bulk['lower_limb']:.2f}")
        + f"; other muscles scaled by {bulk['default']:.2f}. An estimate of position and size on this body; the "
        "boundaries between neighbouring muscles are the other donor's.",
        "Anatomical imagery courtesy of the U.S. National Library of Medicine (Visible Human Project).",
    ]
    if a.direction == "m2f":
        attribution.append(
            "Lower-extremity musculoskeletal geometry derived from Andreassen TE, Hume DR, Hamilton LD, Walker KE, "
            "Higinbotham SE, Shelburne KB, 'Three Dimensional Lower Extremity Musculoskeletal Geometry of the Visible "
            "Human Female and Male', Scientific Data 10:34 (2023), doi:10.1038/s41597-022-01905-2, used under CC BY 4.0.")
    manifest = {"subject": subject, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
                "source_volume": None, "source_kind": f"cross-subject transfer {src_name} -> {dst_name}",
                "vertex_count": int(len(V)), "triangle_count": int(len(Fc)),
                "bbox_min_mm": [round(float(x), 4) for x in V.min(axis=0)] if len(V) else None,
                "bbox_max_mm": [round(float(x), 4) for x in V.max(axis=0)] if len(V) else None,
                "attribution": attribution,
                "bone_maps": {b: {"det": round(mp["det"], 3), "side": mp["side"],
                                  "src_extent_mm": [round(float(x), 1) for x in mp["src"]["ext"]],
                                  "dst_extent_mm": [round(float(x), 1) for x in mp["dst"]["ext"]]}
                              for b, mp in maps.items()},
                "muscle_bulk_transverse": bulk, "fill_correction": {k: round(x, 3) for k, x in fill.items()},
                "fill_detail": fill_detail,
                "structures": structures}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    rep = {"source": attribution[1] + (" " + attribution[2] if len(attribution) > 2 else "") + " Derived data (scripts/transfer/cross_subject_transfer.py).",
           "direction": a.direction, "bulk_transverse": bulk, "fill_correction": {k: round(x, 3) for k, x in fill.items()},
           "fill_detail": fill_detail, "n": len(report), "not_transferred": skipped, "rows": report}
    rp = Path(a.report) if a.report else out / "transfer_report.json"
    rp.write_text(json.dumps(rep, indent=1))
    print(f"{subject}: {len(structures)} structures, {len(V)} vertices, {len(Fc)} triangles; bulk {bulk}; "
          f"fill {fill} {fill_detail}; not transferred: {sorted(skipped)}")
    for r in report:
        print(f"  {r['atlas_id']:36s} {r['category']:9s} {r['volume_src_cm3']:7.1f} -> {r['volume_out_cm3']:7.1f} cm3 "
              f"disp {r['displacement_mm_median']:6.1f} mm  out-of-skin {r.get('outside_target_skin_fraction', '-')}  "
              f"{list(r['driving_bones'])[:3]}")


if __name__ == "__main__":
    main()
