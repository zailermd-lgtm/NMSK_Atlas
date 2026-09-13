"""Refine the transferred lower-limb muscles to the female's OWN intermuscular septa.

    python3 scripts/transfer/refine_transfer_to_septa.py --frame SCRATCH/vh_cryo_f --xfer build/vh/xfer_vhm2vhf \
        --report data/derived/transfer_report_vhm2vhf.json --origin '7.769,-885.229,14.137' \
        --out data/ct_sources/task_outputs/vhf_xfer_lowerlimb_septa.nii.gz

The transfer (cross_subject_transfer.py) puts the male's thigh and leg muscles at the right place and
size on her, but the boundaries between neighbouring muscles are his. Her photographs show her own
septa as bright fascial lines between dark muscle bellies. Per 1 mm slice of her registered frame:
the transferred meshes are voxelised into the frame grid; markers = each transferred muscle's mask
eroded by 3 mm (its whole mask where the erosion empties); region = her muscle class (closed, filled)
within 6 mm of the union of transferred masks; a marker watershed on the white top-hat of the
brightness (fascial lines are ridges) reassigns the region to the markers, each muscle allowed to
move at most 8 mm from its transferred mask. Output: a label volume in her frame (torso RAS) for
`ingest_volume_geometry.py convert` (label key mappings/vhf_xfer_septa_labels.json), a report with
the volume before/after per muscle, and overlays. Still a transfer (the muscle set, its attachments
and its rough shape are his); only the boundaries between adjacent bellies are now hers. Badged.
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
from skimage.morphology import white_tophat, disk
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

ERODE_PX, DILATE_PX, MAX_MOVE_PX = 3, 6, 8
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections via the NCI Imaging "
          "Data Commons; the transferred muscle set from the male's DU lower-limb release (Andreassen et al. 2023, Sci Data 10:34, "
          "doi:10.1038/s41597-022-01905-2, CC BY 4.0). Derived data (scripts/transfer/refine_transfer_to_septa.py).")


def load_xfer(d: Path, ids):
    man = json.loads((d / "manifest.json").read_text())
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3); F = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    out = {}
    for s in man["structures"]:
        if s["atlas_id"] in ids:
            v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
            f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
            out[s["atlas_id"]] = (v, f)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frame", required=True); ap.add_argument("--xfer", default="build/vh/xfer_vhm2vhf")
    ap.add_argument("--report", default="data/derived/transfer_report_vhm2vhf.json")
    ap.add_argument("--origin", default="7.769,-885.229,14.137")
    ap.add_argument("--out", default="data/ct_sources/task_outputs/vhf_xfer_lowerlimb_septa.nii.gz")
    ap.add_argument("--labels-out", default="mappings/vhf_xfer_septa_labels.json")
    ap.add_argument("--mapping-out", default="mappings/subjects/xfer_vhm2vhf_sep_volume_mapping.json")
    ap.add_argument("--overlay", default=None)
    a = ap.parse_args()
    D = Path(a.frame); cls = np.load(D / "cryo_frame_cls.npy", mmap_mode="r"); rgb = np.load(D / "cryo_frame_rgb.npy", mmap_mode="r")
    z0 = json.load(open(D / "frame.json"))["z0"]; n, H, W = cls.shape
    ox, oy, oz = [float(t) for t in a.origin.split(",")]
    rep = json.load(open(a.report))
    ids = [r["atlas_id"] for r in rep["rows"] if r["category"] == "muscle" and r.get("lean_envelope")]
    meshes = load_xfer(Path(a.xfer), ids)
    lab_of = {aid: i + 1 for i, aid in enumerate(sorted(meshes))}
    # voxelise into the frame grid: atlas (x,y,z) -> RAS (x+ox, z+oz, y+oy) -> col = 350 - RASx, row = 240 - RASy, k = RASz - z0
    lab = np.zeros((n, H, W), np.uint8)
    for aid, (v, f) in meshes.items():
        tm = trimesh.Trimesh(v, f, process=False)
        vox = tm.voxelized(pitch=1.0).fill()
        p = vox.points
        col = np.rint(350.0 - (p[:, 0] + ox)).astype(int); row = np.rint(240.0 - (p[:, 2] + oz)).astype(int); k = np.rint(p[:, 1] + oy - z0).astype(int)
        ok = (col >= 0) & (col < W) & (row >= 0) & (row < H) & (k >= 0) & (k < n)
        lab[k[ok], row[ok], col[ok]] = lab_of[aid]
    before = {aid: int((lab == l).sum()) for aid, l in lab_of.items()}
    ks = np.where(lab.any(axis=(1, 2)))[0]
    out = np.zeros_like(lab); moved_px = []
    for k in ks:
        L = lab[k]; c = np.asarray(cls[k]); im = np.asarray(rgb[k])
        union = L > 0
        region = ndi.binary_fill_holes(ndi.binary_closing(c == 3, iterations=2)) & ndi.binary_dilation(union, iterations=DILATE_PX)
        if not region.any():
            continue
        markers = np.zeros_like(L)
        for l in np.unique(L[L > 0]):
            m = L == l; e = ndi.binary_erosion(m, iterations=ERODE_PX) & region
            markers[e if e.any() else (m & region)] = l
        th = white_tophat(im.max(-1).astype(np.float32), disk(4))
        ws = watershed(th, markers, mask=region)
        # a muscle may not move more than MAX_MOVE_PX from its transferred mask
        res = np.zeros_like(L)
        for l in np.unique(ws[ws > 0]):
            near = ndi.binary_dilation(L == l, iterations=MAX_MOVE_PX)
            res[(ws == l) & near] = l
        # transferred pixels the watershed left unassigned (outside her muscle class) keep their label if inside tissue
        keep = (res == 0) & union & (c > 0)
        res[keep] = L[keep]
        out[k] = res; moved_px.append(int((res != L).sum()))
    after = {aid: int((out == l).sum()) for aid, l in lab_of.items()}
    k0, k1 = int(ks.min()), int(ks.max()) + 1
    aff = np.array([[-1, 0, 0, 350], [0, -1, 0, 240], [0, 0, 1, z0 + k0], [0, 0, 0, 1]], float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(out[k0:k1].transpose(2, 1, 0)), aff), a.out)
    labels = {"_README": ["Label id -> transferred muscle whose boundaries were refined to the female's own septa "
                          "(scripts/transfer/refine_transfer_to_septa.py). A KEY, not data."], "source": SOURCE,
              "labels": {str(l): aid for aid, l in lab_of.items()}}
    Path(a.labels_out).write_text(json.dumps(labels, indent=1))
    entries = [{"label": l, "source_structure": aid, "side": "right" if aid.endswith("_r") else "left", "status": "curated",
                "atlas_id": aid, "relationship": "part_of",
                "note": "Transferred from the male (xfer_vhm2vhf), boundaries between neighbouring bellies refined to her septa.",
                "candidates": []} for aid, l in sorted(lab_of.items(), key=lambda kv: kv[1])]
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.",
                                                            "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                               "subject": "xfer_vhm2vhf_sep", "source_volume": str(Path(a.out).resolve()),
                                               "label_map": Path(a.labels_out).stem.replace("_labels", ""), "entries": entries}, indent=1))
    rows = [{"atlas_id": aid, "label": l, "transferred_cm3": round(before[aid] / 1000, 1), "refined_cm3": round(after[aid] / 1000, 1),
             "ratio": round(after[aid] / max(before[aid], 1), 3)} for aid, l in sorted(lab_of.items(), key=lambda kv: kv[1])]
    report = {"source": SOURCE, "slices": int(len(ks)), "pixels_reassigned_per_slice_mean": round(float(np.mean(moved_px)), 1),
              "rows": rows}
    Path(a.out.replace(".nii.gz", "_report.json")).write_text(json.dumps(report, indent=1))
    print(f"{len(ks)} slices, mean {np.mean(moved_px):.0f} px reassigned per slice")
    for r in rows:
        print(f"  {r['atlas_id']:28s} {r['transferred_cm3']:7.1f} -> {r['refined_cm3']:7.1f}  x{r['ratio']:.2f}")
    if a.overlay:
        from PIL import Image
        rng = np.random.default_rng(3); colors = rng.integers(60, 255, (len(lab_of) + 1, 3)); tiles = []
        for y in (-150, -250, -350, -500, -600):
            k = int(round(y + oy - z0))
            if not (k0 <= k < k1):
                continue
            pic = np.asarray(rgb[k]).copy(); L = out[k]
            for l in np.unique(L[L > 0]):
                m = L == l; edge = m & ~ndi.binary_erosion(m, iterations=1); pic[edge] = colors[l]
            ys, xs = np.where(L > 0)
            if len(ys):
                pic = pic[max(0, ys.min() - 10):ys.max() + 10, max(0, xs.min() - 10):xs.max() + 10]
            tiles.append(pic)
        h = max(t.shape[0] for t in tiles); w = max(t.shape[1] for t in tiles)
        canvas = np.zeros((h * len(tiles), w, 3), np.uint8)
        for i, t in enumerate(tiles):
            canvas[i * h:i * h + t.shape[0], :t.shape[1]] = t
        Image.fromarray(canvas).save(a.overlay); print("overlay", a.overlay)


if __name__ == "__main__":
    main()
