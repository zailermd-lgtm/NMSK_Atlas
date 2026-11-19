"""Measure how the two Visible Human bodies differ, from the data itself.

    python3 scripts/transfer/subject_anthropometrics.py --male-html PATH \
        [--female-bundle build/viewer_f] [--ct-male X.nii.gz --ct-female Y.nii.gz \
         --origin-male 'x,y,z' --origin-female 'x,y,z'] -o data/derived/subject_anthropometrics.json

Everything under "measured" is read off the shipped meshes (both viewer
bundles) or the CTs; nothing is assumed. "published" is what the DU
release paper states for the two donors. The numbers feed the cross-subject
transfer (scripts/transfer/cross_subject_transfer.py): bone frames give the
geometric map, the soft-tissue ratios give the bulk correction, and the fat
fractions say why the two bodies cannot simply be overlaid.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_html, read_bundle_dir, meshes_by_id, mesh_volume_cm3, own_only  # noqa: E402
from scripts.transfer.bone_frames import bone_frame  # noqa: E402

PUBLISHED = {
    "source": "Andreassen TE, Hume DR, Hamilton LD, Walker KE, Higinbotham SE, Shelburne KB (2023) "
              "'Three Dimensional Lower Extremity Musculoskeletal Geometry of the Visible Human Female and Male', "
              "Scientific Data 10:34, doi:10.1038/s41597-022-01905-2 (Methods: donor data as supplied by NLM); "
              "retrieved via PubMed/PMC (PMC9849470)",
    "male": {"age_y": 39, "stature_in": 71, "stature_cm": round(71 * 2.54, 1), "mass_kg": 90, "bmi": 27.8},
    "female": {"age_y": 59, "stature_in": 62, "stature_cm": round(62 * 2.54, 1), "mass_kg": 88, "bmi": 36.0},
}

LONG_BONES = ["femur_r", "femur_l", "tibia_r", "tibia_l", "fibula_r", "fibula_l", "humerus_r", "humerus_l",
              "radius_r", "ulna_r", "hip_bone_r", "hip_bone_l", "sacrum", "scapula_r", "scapula_l",
              "clavicle_r", "clavicle_l", "sternum", "lumbar_vertebrae", "thoracic_vertebrae",
              "cervical_vertebrae", "cranium", "mandible"]
TRUNCATED_FEMALE = {"humerus_r", "humerus_l", "radius_r", "ulna_r"}
SHARED_MUSCLES = ["gluteus_maximus", "gluteus_medius", "gluteus_minimus", "iliopsoas", "deltoid",
                  "supraspinatus", "infraspinatus", "subscapularis", "biceps_brachii", "triceps_brachii",
                  "brachialis", "pectoralis_major", "latissimus_dorsi", "trapezius", "serratus_anterior",
                  "rectus_abdominis", "external_oblique", "internal_oblique", "erector_spinae",
                  "longissimus", "iliocostalis", "spinalis", "multifidus", "pectoralis_minor",
                  "sternocleidomastoid", "masseter", "temporalis"]


def skin_width(v, y, z=None, band=5.0):
    sel = np.abs(v[:, 1] - y) < band
    if z is not None:
        sel &= np.abs(v[:, 2] - z) < 15
    if sel.sum() < 20:
        return None
    return round(float(v[sel, 0].max() - v[sel, 0].min()), 1)


def skin_depth(v, y, band=5.0):
    sel = np.abs(v[:, 1] - y) < band
    if sel.sum() < 20:
        return None
    return round(float(v[sel, 2].max() - v[sel, 2].min()), 1)


def measure_body(D: dict) -> dict:
    out = {"bones": {}, "muscles": {}, "skin": {}}
    for b in LONG_BONES:
        for cand in (b,):
            if cand in D:
                m = D[cand]; fr = bone_frame(m["v"])
                out["bones"][b] = {"length_mm": round(float(fr["ext"][0]), 1),
                                   "width_mm": round(float(fr["ext"][1]), 1),
                                   "depth_mm": round(float(fr["ext"][2]), 1),
                                   "centre_mm": [round(float(x), 1) for x in fr["centre"]],
                                   "volume_cm3": round(mesh_volume_cm3(m["v"], m["f"]), 1),
                                   "subject": m["subject"]}
    for mus in SHARED_MUSCLES:
        for side in ("r", "l"):
            k = f"{mus}_{side}"
            if k in D:
                out["muscles"][k] = {"volume_cm3": round(mesh_volume_cm3(D[k]["v"], D[k]["f"]), 1),
                                     "subject": D[k]["subject"]}
    # stature proxy: cranium vertex to the lowest foot point (both bodies supine)
    top = D["cranium"]["v"][:, 1].max() if "cranium" in D else None
    feet = [D[k]["v"][:, 1].min() for k in D if k.startswith(("tarsals", "metatarsals", "phalanges_foot"))]
    if top is not None and feet:
        out["stature_proxy_mm"] = round(float(top - min(feet)), 1)
        out["stature_proxy_note"] = ("top of the cranium mesh to the lowest foot-bone vertex along the table axis; "
                                     "the feet are plantar-flexed on both cadavers so this overstates standing height "
                                     "by the foot's plantar flexion, equally on both")
    if "hip_bone_r" in D and "hip_bone_l" in D:
        hv = np.concatenate([D["hip_bone_r"]["v"], D["hip_bone_l"]["v"]])
        out["bi_iliac_width_mm"] = round(float(hv[:, 0].max() - hv[:, 0].min()), 1)
    if "clavicle_r" in D and "clavicle_l" in D:
        cv = np.concatenate([D["clavicle_r"]["v"], D["clavicle_l"]["v"]])
        out["biclavicular_span_mm"] = round(float(cv[:, 0].max() - cv[:, 0].min()), 1)
    if "ribs_r" in D and "ribs_l" in D:
        rv = np.concatenate([D["ribs_r"]["v"], D["ribs_l"]["v"]])
        out["rib_cage_width_mm"] = round(float(rv[:, 0].max() - rv[:, 0].min()), 1)
        out["rib_cage_depth_mm"] = round(float(rv[:, 2].max() - rv[:, 2].min()), 1)
    if "skin" in D:
        sv = D["skin"]["v"]; sf = D["skin"]["f"]
        out["skin"]["y_range_mm"] = [round(float(sv[:, 1].min()), 1), round(float(sv[:, 1].max()), 1)]
        out["skin"]["volume_L_whole_mesh"] = round(mesh_volume_cm3(sv, sf) / 1000.0, 1)
        for name, y in (("chest_y350", 350), ("waist_y150", 150), ("hips_y0", 0), ("mid_thigh_y-200", -200),
                        ("knee_y-420", -420), ("calf_y-600", -600)):
            w = skin_width(sv, y); d = skin_depth(sv, y)
            if w is not None:
                out["skin"][f"width_{name}_mm"] = w
                out["skin"][f"ap_depth_{name}_mm"] = d
    return out


def ct_fat(path: str, origin: str, y_ranges) -> dict:
    """Fat and lean fractions of the body cross-section from a CT, with the
    HU split chosen from the body's own histogram (frozen tissue does not sit
    at textbook HU), per atlas-y range."""
    import nibabel as nib
    from scipy import ndimage as ndi
    ox, oy, oz = [float(t) for t in origin.split(",")]
    im = nib.load(path); A = im.affine; vol = np.asanyarray(im.dataobj)
    vox_mm3 = float(abs(np.linalg.det(A[:3, :3])))
    out = {"path": Path(path).name, "shape": list(vol.shape)}
    ys = A[2, 3] + np.arange(vol.shape[2]) * A[2, 2] - oy   # atlas y of each slice (RAS z - origin_y)
    # histogram of soft tissue inside the body over the full block
    body_all = vol > -500
    soft = vol[body_all & (vol < 150)]
    h, e = np.histogram(soft, bins=np.arange(-300, 151, 5))
    c = (e[:-1] + e[1:]) / 2
    fat_pk = float(c[(c < -20)][np.argmax(h[c < -20])])
    lean_pk = float(c[(c > -20)][np.argmax(h[c > -20])])
    lo, hi = int(np.searchsorted(c, fat_pk)), int(np.searchsorted(c, lean_pk))
    split = float(c[lo + int(np.argmin(h[lo:hi + 1]))]) if hi > lo else (fat_pk + lean_pk) / 2
    out.update({"fat_peak_hu": fat_pk, "lean_peak_hu": lean_pk, "split_hu": split,
                "note": "body = HU>-500 filled per slice, largest component; fat = HU in [fat peak-80, split]; "
                        "lean soft tissue = (split, 150]; bone = >150. Fractions of the body cross-section volume."})
    for name, (y0, y1) in y_ranges.items():
        ks = np.where((ys >= y0) & (ys < y1))[0]
        if len(ks) == 0:
            continue
        body = fat = lean = bone = 0
        for k in ks:
            sl = vol[:, :, k]
            m = ndi.binary_fill_holes(sl > -500)
            lab, n = ndi.label(m)
            if n == 0:
                continue
            m = lab == (np.bincount(lab.ravel())[1:].argmax() + 1)
            s = sl[m]; body += m.sum()
            fat += int(((s >= fat_pk - 80) & (s <= split)).sum()); lean += int(((s > split) & (s <= 150)).sum())
            bone += int((s > 150).sum())
        out[name] = {"slices": int(len(ks)), "body_volume_L": round(body * vox_mm3 / 1e6, 2),
                     "fat_fraction": round(fat / max(body, 1), 3), "lean_fraction": round(lean / max(body, 1), 3),
                     "bone_fraction": round(bone / max(body, 1), 3),
                     "mean_section_cm2": round(body * vox_mm3 / len(ks) / abs(A[2, 2]) / 100, 1)}
    return out


def cryo_fractions(get_slice, levels, classify=None, px_mm=0.99):
    """Fat / muscle fractions of the filled body silhouette in colour-class slices. get_slice(k) -> class
    image (or RGB when classify is given). levels: {name: [k, ...]}. The silhouette is the filled tissue
    mask, so dark muscle the colour rule leaves unclassified still counts as body (not as fat)."""
    from scipy import ndimage as ndi
    out = {}
    for name, ks in levels.items():
        body = fat = muscle = 0
        for k in ks:
            c = get_slice(k)
            if classify is not None:
                c = classify(np.asarray(c))
            c = np.asarray(c)
            t = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=2))
            lab, n = ndi.label(t)
            if n == 0:
                continue
            sizes = np.bincount(lab.ravel())[1:]
            keep = np.isin(lab, np.where(sizes >= 0.05 * sizes.max())[0] + 1)   # both legs, not specks
            body += int(keep.sum()); fat += int(((c == 2) & keep).sum()); muscle += int(((c == 3) & keep).sum())
        if body:
            a = px_mm * px_mm / 100.0 / len(ks)      # cm2 per slice
            out[name] = {"slices": len(ks), "fat_fraction": round(fat / body, 3), "muscle_fraction": round(muscle / body, 3),
                         "body_area_cm2": round(body * a, 1), "fat_area_cm2": round(fat * a, 1),
                         "muscle_area_cm2": round(muscle * a, 1)}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--male-html", required=True)
    ap.add_argument("--female-bundle", default="build/viewer_f")
    ap.add_argument("--ct-male"); ap.add_argument("--ct-female")
    ap.add_argument("--origin-male"); ap.add_argument("--origin-female")
    ap.add_argument("--male-cryo-dir", help="stream_cryosections.py output of his series at --step 10 (every 10th mm)")
    ap.add_argument("--female-cryo-cls", help="her registered class frame (cryo_frame_cls.npy) + frame.json beside it")
    ap.add_argument("-o", "--out", default="data/derived/subject_anthropometrics.json")
    a = ap.parse_args()
    mp = Path(a.male_html); bm, blob = read_bundle_dir(mp) if mp.is_dir() else read_bundle_html(mp); M = own_only(meshes_by_id(bm, blob))
    bf, blobf = read_bundle_dir(a.female_bundle); F = own_only(meshes_by_id(bf, blobf))
    res = {"_README": ["Differences between the two Visible Human bodies, measured on the shipped meshes and CTs. "
                       "Atlas frame: +X right, +Y superior, +Z anterior, mm, origin at the hip joint centres. "
                       "Used by scripts/transfer/cross_subject_transfer.py; see docs/GEOMETRY_SOURCES.md "
                       "'Cross-subject transfer'."],
           "source": PUBLISHED["source"] + "; measurements: NLM Visible Human Project male and female CT and cryosections "
                     "via the NCI Imaging Data Commons (public domain), derived by this script",
           "published": PUBLISHED,
           "measured": {"male": measure_body(M), "female": measure_body(F)}}
    ratios = {}
    mb, fb = res["measured"]["male"]["bones"], res["measured"]["female"]["bones"]
    for b in mb:
        if b in fb and b not in TRUNCATED_FEMALE:
            ratios[b] = {k: round(fb[b][k] / mb[b][k], 3) for k in ("length_mm", "width_mm", "depth_mm", "volume_cm3")}
    mm, fm = res["measured"]["male"]["muscles"], res["measured"]["female"]["muscles"]
    for k in mm:
        if k in fm:
            ratios[k] = {"volume_cm3": round(fm[k]["volume_cm3"] / mm[k]["volume_cm3"], 3),
                         "male_subject": mm[k]["subject"], "female_subject": fm[k]["subject"]}
    res["female_over_male"] = ratios
    y_ranges = {"pelvis_abdomen_y40_250": (40, 250), "thorax_y250_450": (250, 450)}
    if a.ct_male and a.origin_male:
        res["measured"]["male"]["ct"] = ct_fat(a.ct_male, a.origin_male, y_ranges)
    if a.ct_female and a.origin_female:
        res["measured"]["female"]["ct"] = ct_fat(a.ct_female, a.origin_female, y_ranges)
    # photograph colour classes: the same measurement on both bodies (his frozen CT cannot separate fat from
    # lean tissue: both peaks sit at -20 HU), at matched trunk ranges and at matched fractions of the limb bones
    fem_m = np.mean([mb[f"femur_{s}"]["length_mm"] for s in "rl"]); fem_f = np.mean([fb[f"femur_{s}"]["length_mm"] for s in "rl"])
    tib_m = np.mean([mb[f"tibia_{s}"]["length_mm"] for s in "rl"]); tib_f = np.mean([fb[f"tibia_{s}"]["length_mm"] for s in "rl"])
    def limb_levels(fem, tib, knee_y):
        return {"thigh_45pct_femur": [-0.45 * fem], "thigh_70pct_femur": [-0.70 * fem],
                "calf_mid_tibia": [knee_y - 0.5 * tib]}
    knee_m = min(M["femur_r"]["v"][:, 1].min(), M["femur_l"]["v"][:, 1].min()) if "femur_r" in M else -450
    knee_f = min(F["femur_r"]["v"][:, 1].min(), F["femur_l"]["v"][:, 1].min()) if "femur_r" in F else -400
    res["limb_levels_y_mm"] = {"male": {k: v[0] for k, v in limb_levels(fem_m, tib_m, knee_m).items()},
                               "female": {k: v[0] for k, v in limb_levels(fem_f, tib_f, knee_f).items()},
                               "note": "matched fractions of each body's own femur / tibia length below the hip centre / knee"}
    if a.male_cryo_dir:
        sys.path.insert(0, str(REPO / "scripts" / "cryo"))
        from cryo_classes import classify as clm
        vol = np.load(Path(a.male_cryo_dir) / "cryo_1mm.npy", mmap_mode="r")
        idx = json.load(open(Path(a.male_cryo_dir) / "cryo_index.json"))
        inst = np.array([r[1] for r in idx])           # instance 1001 = vertex; cryo index i = instance - 1001
        def j_of_y(y):                                  # cryo index i = -16 - z_RAS; y = z_RAS + 895.476
            i = 879.476 - y; return int(np.argmin(np.abs(inst - 1001 - i)))
        lv = {"pelvis_abdomen_y40_250": [j for j in range(len(inst)) if 40 <= 879.476 - (inst[j] - 1001) < 250],
              "thorax_y250_450": [j for j in range(len(inst)) if 250 <= 879.476 - (inst[j] - 1001) < 450]}
        lv.update({k: [j_of_y(y) for y in ys] for k, ys in limb_levels(fem_m, tib_m, knee_m).items()})
        res["measured"]["male"]["cryo_classes"] = cryo_fractions(lambda j: vol[j], lv, classify=clm, px_mm=0.33 * 3)
        res["measured"]["male"]["cryo_classes"]["note"] = ("male cryosections streamed every 10th mm; classes "
            "scripts/cryo/cryo_classes.py; fractions of the filled body silhouette (trunk ranges: whole section incl. arms)")
    if a.female_cryo_cls:
        cls = np.load(a.female_cryo_cls, mmap_mode="r"); fr = json.load(open(Path(a.female_cryo_cls).parent / "frame.json"))
        oy = float(a.origin_female.split(",")[1]) if a.origin_female else -885.229
        from scripts.transfer import lean_envelope as le
        cpath = REPO / "data" / "derived" / "vhf_cryo_frame_y_correction.json"
        corr = json.load(open(cpath)) if cpath.exists() else None
        k_of_y = lambda y: le.photo_slice_of(y, fr, oy, corr)
        lv = {"pelvis_abdomen_y40_250": list(range(k_of_y(40), k_of_y(250), 10)),
              "thorax_y250_450": list(range(k_of_y(250), k_of_y(450), 10))}
        lv.update({k: [k_of_y(y) for y in ys] for k, ys in limb_levels(fem_f, tib_f, knee_f).items()})
        res["measured"]["female"]["cryo_classes"] = cryo_fractions(lambda k: cls[k], lv, px_mm=fr.get("scale", 0.99))
        res["measured"]["female"]["cryo_classes"]["note"] = ("female cryosections at 1 mm registered to her CT; classes "
            "scripts/cryo/cryo_classes_f.py; fractions of the filled body silhouette")
    Path(a.out).write_text(json.dumps(res, indent=1))
    print("wrote", a.out)
    for b, r in ratios.items():
        print(f"  {b:28s} {r}")
    for who in ("male", "female"):
        m = res["measured"][who]
        print(who, "stature proxy", m.get("stature_proxy_mm"), "bi-iliac", m.get("bi_iliac_width_mm"),
              "biclavicular", m.get("biclavicular_span_mm"), "ribs", m.get("rib_cage_width_mm"), m.get("rib_cage_depth_mm"),
              "skin", m["skin"])
        if "ct" in m:
            print("   ct", {k: v for k, v in m["ct"].items() if k != "note"})
        if "cryo_classes" in m:
            print("   cryo classes", {k: v for k, v in m["cryo_classes"].items() if k != "note"})


if __name__ == "__main__":
    main()
