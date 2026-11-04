"""Split the female's CT tarsal label into the seven tarsal bones, using the male's separately segmented tarsals
transferred onto her as the shapes that decide where one bone ends and the next begins.

    python3 scripts/vhf_split_tarsals.py --legs data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz \
        --xfer SCRATCH/xfer_tarsals --origin '7.769,-885.229,14.137' \
        --out data/ct_sources/task_outputs/vhf_tarsals_split.nii.gz

Her CT (0.72 mm) shows no HU barrier at the subtalar joint (Q31: seeded and unseeded watersheds floods the
talus into the calcaneal body), so the joint lines come from an outside shape: the DU release's talus,
calcaneus, cuboid, navicular and three cuneiforms of the male (`name_tarsal_pieces.py`), carried onto her by
the bone-driven transfer (`cross_subject_transfer.py --direction m2f`, driven by her tibia, fibula and
metatarsals; an optional rigid ICP refinement of the set onto her tarsal mass measured WORSE and is off). Every voxel
of HER tarsal label (TotalSegmentator `tarsals_right/left`, labels 4 / 10 of the
legs volume) is given to the transferred bone it lies deepest inside (largest signed distance, from the
distance transforms of each transferred bone voxelised on her grid; a voxel outside all seven goes to the
nearest). So the outer surface of every bone is hers (the CT),
the surfaces BETWEEN the bones are his shapes placed on her. Output: a label volume on her legs grid for
`ingest_volume_geometry.py convert` (label key mappings/vhf_tarsals_labels.json), a report with her volume per
bone against his, and the mapping for subject `ct_vhf_tarsal`. Rule-based; badged; volumes recorded.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
import trimesh
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

BONES = ("calcaneus", "talus", "cuboid", "navicular", "cuneiform_medial", "cuneiform_intermediate", "cuneiform_lateral")
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): the female's CT tarsal label "
          "(TotalSegmentator, free task) split by the male's separately segmented tarsals (Andreassen et al. 2023, Sci Data "
          "10:34, doi:10.1038/s41597-022-01905-2, CC BY 4.0) transferred onto her. Derived data (scripts/vhf_split_tarsals.py).")


def load_subject(d):
    man = json.loads((Path(d) / "manifest.json").read_text())
    V = np.fromfile(Path(d) / "vertices.f32", np.float32).reshape(-1, 3); F = np.fromfile(Path(d) / "faces.u32", np.uint32).reshape(-1, 3)
    out = {}
    for s in man["structures"]:
        v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
        f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        out[s["atlas_id"]] = trimesh.Trimesh(v, f, process=False)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--legs", default="data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz")
    ap.add_argument("--labels", default="4,10", help="her tarsal label ids: right,left")
    ap.add_argument("--xfer", required=True, help="subject folder of the transferred male tarsals")
    ap.add_argument("--origin", default="7.769,-885.229,14.137")
    ap.add_argument("--out", default="data/ct_sources/task_outputs/vhf_tarsals_split.nii.gz")
    ap.add_argument("--labels-out", default="mappings/vhf_tarsals_labels.json")
    ap.add_argument("--mapping-out", default="mappings/subjects/ct_vhf_tarsal_volume_mapping.json")
    ap.add_argument("--icp", action="store_true", help="rigid ICP of the seven transferred bones onto her tarsal mass first (measured worse; see code)")
    a = ap.parse_args()
    img = nib.load(a.legs); vol = np.asanyarray(img.dataobj); aff = img.affine; ox, oy, oz = [float(t) for t in a.origin.split(",")]
    meshes = load_subject(a.xfer); lab_r, lab_l = [int(t) for t in a.labels.split(",")]
    out = np.zeros(vol.shape, np.uint8); lab_of = {}; rows = []
    vox_mm3 = float(abs(np.linalg.det(aff[:3, :3])))
    inv = np.linalg.inv(aff)
    for side, lab in (("r", lab_r), ("l", lab_l)):
        ijk = np.argwhere(vol == lab)
        if not len(ijk):
            print(side, "no tarsal voxels"); continue
        lo = ijk.min(0) - 6; hi = ijk.max(0) + 7
        sub = np.zeros(hi - lo, bool); sub[tuple((ijk - lo).T)] = True
        names = [f"{b}_{side}" for b in BONES]; score = []
        to_vox = lambda v: (np.column_stack([v[:, 0] + ox, v[:, 2] + oz, v[:, 1] + oy]) @ inv[:3, :3].T + inv[:3, 3]) - lo
        # the transfer places the seven bones to +-5 mm; one RIGID fit of the whole set onto her tarsal mass (ICP, no
        # scaling, surface points of her label) removes that offset before the voxels are assigned
        T = np.eye(4)
        if a.icp:   # measured 2026-09-14: the fit slides the set 15-17 mm with a 9-12 mm residual (the union's INNER joint
                    # surfaces pull it) and shrinks her calcaneus to 36 cm3; off by default, the transfer's placement is better
            src = np.concatenate([to_vox(meshes[nm].vertices) for nm in names]); src = src[::max(1, len(src) // 6000)]
            edge = sub & ~ndi.binary_erosion(sub); tgt = np.argwhere(edge).astype(float); tgt = tgt[::max(1, len(tgt) // 8000)]
            T, _, cost = trimesh.registration.icp(src, tgt, scale=False, max_iterations=60, threshold=1e-6)
            shift = np.linalg.norm(T[:3, 3]); rot = np.degrees(np.arccos(np.clip((np.trace(T[:3, :3]) - 1) / 2, -1, 1)))
            print(f"{side}: rigid refinement shift {shift * 0.72:.1f} mm, rotation {rot:.1f} deg, mean residual {cost * 0.72:.2f} mm", flush=True)
        for nm in names:
            m = meshes[nm].copy()
            # transferred bone (atlas mm) -> RAS -> voxel index of her legs grid (+ the rigid refinement); voxelise on that grid
            m.vertices = trimesh.transform_points(to_vox(m.vertices), T)
            g = m.voxelized(pitch=1.0).fill(); inside = np.zeros(sub.shape, bool)
            pts = np.rint(g.points).astype(int); ok = np.all((pts >= 0) & (pts < np.array(sub.shape)), axis=1); inside[tuple(pts[ok].T)] = True
            # signed distance in voxels: + inside the transferred bone, - outside
            score.append(ndi.distance_transform_edt(inside) - ndi.distance_transform_edt(~inside))
        score = np.stack(score, axis=-1); best = score.argmax(axis=-1)
        inside_any = float((score.max(axis=-1)[sub] > 0).mean())
        for k, nm in enumerate(names):
            l = len(lab_of) + 1; lab_of[nm] = l; sel = sub & (best == k)
            idx = np.argwhere(sel) + lo; out[idx[:, 0], idx[:, 1], idx[:, 2]] = l
            rows.append({"atlas_id": nm, "label": l, "female_cm3": round(float(sel.sum() * vox_mm3 / 1000), 1),
                         "male_transferred_cm3": round(float(meshes[nm].volume / 1000), 1)})
        print(f"{side}: {len(ijk)} voxels, {inside_any:.2f} inside a transferred bone; " +
              ", ".join(f"{r['atlas_id']} {r['female_cm3']}" for r in rows if r["atlas_id"].endswith("_" + side)), flush=True)
    nib.save(nib.Nifti1Image(out, aff), a.out)
    Path(a.labels_out).write_text(json.dumps({"_README": ["Label id -> tarsal bone of the female, split by the male's transferred bones "
                                                           "(scripts/vhf_split_tarsals.py). A KEY, not data."], "source": SOURCE,
                                              "labels": {str(l): nm for nm, l in lab_of.items()}}, indent=1))
    entries = [{"label": l, "source_structure": nm, "side": "right" if nm.endswith("_r") else "left", "status": "curated", "atlas_id": nm,
                "relationship": "part_of", "note": "Her CT tarsal label; the joint surfaces between the bones are the male's transferred shapes.",
                "candidates": []} for nm, l in lab_of.items()]
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                               "subject": "ct_vhf_tarsal", "source_volume": str(Path(a.out).resolve()),
                                               "label_map": Path(a.labels_out).stem.replace("_labels", ""), "entries": entries}, indent=1))
    Path(a.out.replace(".nii.gz", "_report.json")).write_text(json.dumps({"source": SOURCE, "rows": rows}, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
