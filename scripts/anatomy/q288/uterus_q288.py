#!/usr/bin/env python3
"""Q288: HER uterus (body + cervix) from her own colour cryosections -> checks, mesh, montage, render, report.

    python3 scripts/anatomy/q288/uterus_q288.py build --photos /dev/shm/q288/photos/pelvis --seg /dev/shm/q288/seg.npz \
        --reg /dev/shm/q288/reg.json --ct SCRATCH/vh_idc/nii/vhf_torso_0937.nii.gz

Input: data/ct_sources/task_outputs/vhf_pelvic_organs_cryo.nii.gz (label 1 = uterus; scripts/cryo/vhf_pelvic_organs_from_cryo.py
`volume`, on her CT grid). Output: build/vh/ct_vhf_uterus/{uterus_cryo_vhf.obj, items.json}, data/derived/Q288_uterus_report.json,
data/derived/Q288_uterus_montage.png, data/derived/Q288_uterus_render.png.

Gates (held, not shipped, if failed): one connected piece; mesh volume within 3 % of the voxels; volume inside the cited
postmenopausal range (RANGE_CM3); < 15 % of its voxels at fat HU (< -30) on her CT; < 25 % inside any one of her other organ
labels except `small_bowel` (which on her unenhanced CT is known to cover the uterus, Q287 -- reported, not gated).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts"))
from engine import volume_ingest as vol  # noqa: E402
from scripts.ribs_from_ct_labels import ORIGIN, TASK  # noqa: E402
from scripts.viscera_from_ct_labels_q193 import mesh_volume_preserving, drop_specks, closed_vol_vox  # noqa: E402

SUBJECT = "ct_vhf_uterus"
SID = "uterus_cryo_vhf"
LABELS = TASK / "vhf_pelvic_organs_cryo.nii.gz"
SIGMA = 1.0
BUDGET = 12000
# Jirapinyo et al. 1998: transvaginal US, healthy Thai women; uterine volume 60.1 ml <= 5 y after menopause, 37.1 ml > 5 y (mean
# age 57.3). Merz et al. 1996 (108 postmenopausal women): uterine size falls with years since menopause. No published SD/range in
# those abstracts -> the gate is the generous band 10-90 cm3 around those means; her value is reported against the means.
RANGE_CM3 = (10.0, 90.0)
REFS = [
    {"what": "uterine volume 60.1 ml in women <= 5 years after menopause and 37.1 ml > 5 years (mean age 57.3); transvaginal ultrasound",
     "cite": "Jirapinyo M, Theppisai U, Leelapatana P, Krasaesub S. Sonographic findings of uterus and ovaries in normal pre- and "
             "post-menopausal women. J Med Assoc Thai 1998;81:527-31", "pmid": "9676090"},
    {"what": "after the menopause uterine size and the corpus-cervix ratio fall, related to years since menopause (765 women, 108 "
             "postmenopausal without pathology)",
     "cite": "Merz E, Miric-Tesanic D, Bahlmann F, Weber G, Wellek S. Sonographic size of uterus and ovaries in pre- and "
             "postmenopausal women. Ultrasound Obstet Gynecol 1996;7:38-42", "doi": "10.1046/j.1469-0705.1996.07010038.x", "pmid": "8932630"},
    {"what": "random walker segmentation", "cite": "Grady L. Random walks for image segmentation. IEEE TPAMI 2006;28:1768-83",
     "doi": "10.1109/TPAMI.2006.233"},
]
TS = {18: "small_bowel", 19: "duodenum", 20: "colon", 21: "urinary_bladder", 25: "sacrum", 77: "hip_left", 78: "hip_right",
      65: "iliac_artery_left", 66: "iliac_artery_right", 67: "iliac_vena_left", 68: "iliac_vena_right"}
PFLOOR = {1: "levator_ani_right", 9: "levator_ani_left", 8: "perineal_other_right", 16: "perineal_other_left", 17: "external_anal_sphincter"}


def gates(r):
    bad = []
    if r["components"] != 1:
        bad.append(f"{r['components']} pieces")
    if abs(r["mesh_vs_voxels"] - 1) > 0.03:
        bad.append(f"mesh {r['mesh_vs_voxels']:.3f}x the voxels")
    if not RANGE_CM3[0] <= r["voxel_cm3"] <= RANGE_CM3[1]:
        bad.append(f"{r['voxel_cm3']} cm3 outside {RANGE_CM3}")
    if r["ct_hu"]["fat_frac"] > 0.15:
        bad.append(f"{100 * r['ct_hu']['fat_frac']:.0f} % fat HU")
    worst = max((v for k, v in r["inside_her_ct_labels_frac"].items() if k != "small_bowel"), default=0)
    if worst > 0.25:
        bad.append(f"{100 * worst:.0f} % inside one of her other organ labels")
    return bad


def pfloor_overlap(mask, A):
    """her Q62 pelvic-floor labels live on the old 1 mm frame (RAS x = 350 - i, y = 240 - j, z = z0 + k): sample them at the mask's RAS points"""
    import nibabel as nib
    pf = nib.load(str(TASK / "vhf_pelvic_floor_cryo.nii.gz")); P = np.asarray(pf.dataobj); B = np.linalg.inv(pf.affine)
    idx = np.argwhere(mask); ras = idx @ A[:3, :3].T + A[:3, 3]
    q = np.rint(ras @ B[:3, :3].T + B[:3, 3]).astype(int)
    ok = np.all((q >= 0) & (q < P.shape), axis=1)
    lab = np.zeros(len(q), int); lab[ok] = P[q[ok, 0], q[ok, 1], q[ok, 2]]
    return {n: round(float((lab == k).mean()), 4) for k, n in PFLOOR.items()}


def hra_uterus(page="build/q287/viewer_zan_female"):
    from scripts.zanatomy import q205_pages as P5
    import scripts.anatomy.q249.build_pages as BP
    man, blob = P5.load_page(REPO / page, BP.STEM["comb_f"])
    D = P5.decode(man, blob, only=lambda m: m["id"] == "uterus")
    return np.asarray(D["uterus"]["v"], float), np.asarray(D["uterus"]["f"], np.int64)


def compare_hra(vd, fd):
    import trimesh
    hv, hf = hra_uterus()
    H = trimesh.Trimesh(hv, hf, process=False); U = trimesh.Trimesh(vd, fd, process=False)
    rng = np.random.default_rng(288)
    lo = np.minimum(H.bounds[0], U.bounds[0]); hi = np.maximum(H.bounds[1], U.bounds[1])
    P = lo + rng.random((60000, 3)) * (hi - lo)
    from trimesh.proximity import signed_distance
    inH = signed_distance(H, P) > 0; inU = signed_distance(U, P) > 0
    return {"hra_volume_cm3": round(abs(float(H.volume)) / 1000, 1), "hra_watertight": bool(H.is_watertight),
            "centroid_distance_mm": round(float(np.linalg.norm(H.centroid - U.centroid)), 1),
            "hra_centroid_atlas_mm": [round(float(x), 1) for x in H.centroid],
            "dice": round(float(2 * (inH & inU).sum() / max(1, inH.sum() + inU.sum())), 3),
            "share_of_hra_inside_hers": round(float((inH & inU).sum() / max(1, inH.sum())), 3),
            "share_of_hers_inside_hra": round(float((inH & inU).sum() / max(1, inU.sum())), 3)}


def montage(photos, seg_npz, out, levels):
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    v = np.load(photos + ".npy", mmap_mode="r"); D = np.load(seg_npz)
    seg, zs, ks = D["seg"], list(D["zs"]), D["ks"]; r0, r1, c0, c1 = D["win"]; ds = int(D["ds"])
    box = (330, 560, 640, 980)
    tiles = []
    for z in levels:
        n = zs.index(z); im = np.asarray(v[ks[n], box[0]:box[1], box[2]:box[3]]).copy()
        m = np.kron(seg[n] == 1, np.ones((ds, ds), bool))[box[0] - r0:box[1] - r0, box[2] - c0:box[3] - c0]
        e = m & ~ndi.binary_erosion(m, iterations=2); im[e] = (0, 255, 0)
        t = Image.fromarray(im).resize((im.shape[1] * 2 // 3, im.shape[0] * 2 // 3))
        ImageDraw.Draw(t).text((4, 4), f"cryo z {z}", fill=(255, 255, 0)); tiles.append(t)
    w, h = tiles[0].size; nc = 4; nr = (len(tiles) + nc - 1) // nc
    S = Image.new("RGB", (w * nc, h * nr))
    for i, t in enumerate(tiles):
        S.paste(t, ((i % nc) * w, (i // nc) * h))
    S.save(out, optimize=True)


def render(vd, fd, A, tot, O, out):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    from skimage.measure import marching_cubes
    fig = plt.figure(figsize=(10, 5), dpi=110)
    sub = (slice(None), slice(None), slice(40, 240))
    for i, (el, az, ttl) in enumerate([(8, 90, "front"), (8, 0, "side")]):
        ax = fig.add_subplot(1, 2, i + 1, projection="3d")
        for lab_, col in ((77, (0.85, 0.85, 0.8, 0.12)), (78, (0.85, 0.85, 0.8, 0.12)), (25, (0.85, 0.85, 0.8, 0.12)), (21, (0.9, 0.85, 0.2, 0.35)), (20, (0.6, 0.4, 0.2, 0.2))):
            m = (tot[sub] == lab_)[::3, ::3, ::3]
            if m.sum() < 10:
                continue
            bv, bf, _, _ = marching_cubes(m.astype(np.float32), 0.5)
            bv = bv * 3 + np.array([0, 0, 40]); bv = (vol.voxels_to_atlas(bv, A) - O)[:, [0, 2, 1]]   # plot axes: x, anterior, superior
            ax.add_collection3d(Poly3DCollection(bv[bf], facecolor=col, edgecolor="none"))
        ax.add_collection3d(Poly3DCollection(vd[:, [0, 2, 1]][fd], facecolor=(0.75, 0.3, 0.45, 0.95), edgecolor="none"))
        c = vd[:, [0, 2, 1]].mean(0); r = 75
        ax.set_xlim(c[0] - r, c[0] + r); ax.set_ylim(c[1] - r, c[1] + r); ax.set_zlim(c[2] - r, c[2] + r)
        ax.view_init(elev=el, azim=az); ax.set_axis_off(); ax.set_title(f"Her uterus (cryosections), {ttl}", fontsize=9)
    fig.text(0.5, 0.02, "pink: uterus (body + cervix, Q288); grey: her hip bones / sacrum, yellow: bladder, brown: colon (her CT labels)",
             ha="center", fontsize=7)
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def build(a):
    import nibabel as nib
    import trimesh
    from scipy import ndimage as ndi
    from export_viewer_bundle import decimate_guarded
    img = nib.load(str(LABELS)); A = img.affine; lab = np.asarray(img.dataobj)
    mask = lab == 1
    vox_cm3 = float(abs(np.linalg.det(A[:3, :3]))) / 1000.0
    O = np.array([float(x) for x in ORIGIN["vhf"].split(",")])
    tot = np.asarray(nib.load(str(TASK / "vhf_total.nii.gz")).dataobj).astype(np.uint8)
    ct = np.asarray(nib.load(a.ct).dataobj).astype(np.float32)
    r = {"_README": ["Q288: her uterus (body + cervix) from her colour cryosections; scripts/cryo/vhf_pelvic_organs_from_cryo.py + "
                     "scripts/anatomy/q288/uterus_q288.py."], "references": REFS, "range_cm3_gate": RANGE_CM3}
    r["voxel_cm3"] = round(float(mask.sum()) * vox_cm3, 2)
    hu = ct[mask]
    r["ct_hu"] = {"median": float(np.median(hu)), "p10": float(np.percentile(hu, 10)), "p90": float(np.percentile(hu, 90)),
                  "fat_frac": round(float((hu < -30).mean()), 4), "note": "her unenhanced fresh CT at the cryosection-mapped voxels"}
    r["inside_her_ct_labels_frac"] = {n: round(float((tot[mask] == k).mean()), 4) for k, n in TS.items()}
    r["inside_her_any_ct_label_frac"] = round(float((tot[mask] > 0).mean()), 4)
    r["inside_her_pelvic_floor_labels_frac"] = pfloor_overlap(mask, A)
    idx = np.argwhere(mask); ras = idx @ A[:3, :3].T + A[:3, 3]
    r["extent_ras_mm"] = {"lr": round(float(np.ptp(ras[:, 0])), 1), "ap": round(float(np.ptp(ras[:, 1])), 1), "si": round(float(np.ptp(ras[:, 2])), 1)}
    lo, hi = idx.min(0), idx.max(0)
    crop = tuple(slice(max(x - 5, 0), y + 6) for x, y in zip(lo, hi))
    v, f, level, _ = mesh_volume_preserving(mask[crop], r["voxel_cm3"], vox_cm3, sigma=SIGMA)
    v, f, specks = drop_specks(v, f)
    v = v + np.array([s.start for s in crop])
    va = vol.voxels_to_atlas(v, A) - O
    dec = decimate_guarded(va, f, BUDGET)
    vd, fd = dec if dec is not None else (va, f)
    T = trimesh.Trimesh(vd, fd, process=False)
    r.update(iso_level=round(float(level), 3), mesh_specks_dropped=len(specks), triangles=int(len(fd)),
             mesh_vs_voxels=round(closed_vol_vox(vd, fd) / 1000.0 / r["voxel_cm3"], 4), components=int(T.body_count),
             watertight=bool(T.is_watertight), centroid_atlas_mm=[round(float(x), 1) for x in T.centroid])
    r["vs_hra_uterus_on_combined_f"] = compare_hra(vd, fd)
    r["held"] = gates(r)
    out = REPO / "build/vh" / SUBJECT; out.mkdir(parents=True, exist_ok=True)
    if not r["held"]:
        T.export(out / f"{SID}.obj")
        (out / "items.json").write_text(json.dumps([{"id": SID, "side": "midline", "name": "Uterus, with cervix (her own, from her cryosections)",
                                                    "latin": "Uterus (corpus et cervix)", "badge": badge(r), "obj": f"{SID}.obj"}], indent=1))
    lv = [-1816, -1819, -1822, -1825, -1828, -1831, -1834, -1837, -1840, -1843, -1846, -1849]
    montage(a.photos, a.seg, REPO / "data/derived/Q288_uterus_montage.png", lv)
    render(vd, fd, A, tot, O, REPO / "data/derived/Q288_uterus_render.png")
    r["montage"] = "data/derived/Q288_uterus_montage.png"; r["render"] = "data/derived/Q288_uterus_render.png"
    (REPO / "data/derived/Q288_uterus_report.json").write_text(json.dumps(r, indent=1))
    print(json.dumps({k: r[k] for k in ("voxel_cm3", "ct_hu", "inside_her_ct_labels_frac", "inside_her_pelvic_floor_labels_frac", "extent_ras_mm",
                                        "mesh_vs_voxels", "components", "vs_hra_uterus_on_combined_f", "held")}, indent=1))


def badge(r):
    h = r["vs_hra_uterus_on_combined_f"]; c = r["ct_hu"]
    return (f"Q288: HER OWN UTERUS, segmented on her own colour cryosections (NLM Visible Human Project female, public domain; 0.33 mm "
            f"photographs used every 1 mm), not a reference organ and not drawn from an atlas. Method: photo-segmented, operator-seeded: "
            f"small seed discs placed by eye INSIDE the organ at 18 levels (committed, data/derived/Q288_seeds.json), every boundary found by "
            f"a 3-D random walker on the photographs' colour (Grady 2006); fat, embedding gel, bowel content and her CT labels compete "
            f"automatically, and at 6 cervix levels competing seeds were also placed by eye in the paracervical tissue. Body and fundus have a clean serosa/fat edge; at the cervix (lowest ~12 mm) there is no colour edge against "
            f"the paracervical tissue and the bladder base, so that boundary is the walker's best split and may be 2-4 mm off. "
            f"Placed in her CT frame by re-registering these photographs to her CT (silhouette + fat/bone pattern; height rms 2.3 mm). "
            f"Volume {r['voxel_cm3']} cm3 (body + cervix): she was 59 and postmenopausal; published means 37.1 ml > 5 y and 60.1 ml <= 5 y "
            f"after menopause (Jirapinyo 1998, PMID 9676090), size falling with years since menopause (Merz 1996, doi:10.1046/j.1469-0705."
            f"1996.07010038.x). Extent {r['extent_ras_mm']['lr']} x {r['extent_ras_mm']['ap']} x {r['extent_ras_mm']['si']} mm (left-right x "
            f"front-back x up-down; the body lies forward over the bladder). Checked on her CT: median {c['median']:.0f} HU (soft tissue), "
            f"{100 * c['fat_frac']:.1f} % of voxels at fat HU; {100 * r['inside_her_ct_labels_frac']['small_bowel']:.0f} % lies in her "
            f"TotalSegmentator `small_bowel` label, which on her unenhanced CT covers the uterus (Q287), "
            f"{100 * r['inside_her_ct_labels_frac']['urinary_bladder']:.1f} % in her bladder label, {100 * r['inside_her_ct_labels_frac']['colon']:.1f} % "
            f"in her colon label. The HRA reference uterus (same donor, hidden by default where this is shown): centroid "
            f"{h['centroid_distance_mm']} mm away, Dice {h['dice']}, {h['hra_volume_cm3']} cm3.")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--photos", required=True); ap.add_argument("--seg", required=True); ap.add_argument("--reg", required=True); ap.add_argument("--ct", required=True)
    build(ap.parse_args())


if __name__ == "__main__":
    main()
