#!/usr/bin/env python3
"""Combine one TotalSegmentator subject's per-structure masks into one label map.

The released dataset gives each subject a `segmentations/` folder holding one
BINARY mask per structure -- `humerus_left.nii.gz`, `clavicula_right.nii.gz`
and so on -- rather than the single integer label volume the ingest reads.
This merges them, using the id numbering in
`mappings/totalsegmentator_labels.json` so the result means the same thing
the ingest expects.

    python3 scripts/merge_totalsegmentator_masks.py s0011/ -o s0011_labels.nii.gz

Only what the atlas can use is merged by default. A whole-body CT carries
liver, bowel and lung; this atlas is musculoskeletal and neurovascular, and
surfacing forty structures it has nowhere to put wastes minutes per subject.
Pass --all to keep everything.

WHERE MASKS OVERLAP. They should not, but segmentations do sometimes disagree
by a voxel at a shared border, and one label has to win. The winner is the
LOWER id, chosen for no reason other than that it is deterministic -- and
every overlapping voxel is counted and reported, because a large overlap
means the two masks are not what they claim to be and no arbitrary rule
should hide that.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import volume_ingest as vol  # noqa: E402

# The same exclusion the ingest uses, kept in one place would be better but
# these two run independently and a scan can be merged without an atlas.
NOT_MUSCULOSKELETAL = (
    "spleen", "kidney", "gallbladder", "liver", "stomach", "pancreas",
    "adrenal", "lung", "esophagus", "trachea", "thyroid", "bowel", "duodenum",
    "colon", "bladder", "prostate", "heart", "atrial", "brain", "cyst",
)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subject", help="a subject folder, or its segmentations/ folder")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--labels", default="totalsegmentator")
    ap.add_argument("--all", action="store_true",
                    help="keep viscera and brain too, not just musculoskeletal")
    args = ap.parse_args()

    try:
        import nibabel as nib
    except ImportError:
        raise SystemExit("This needs nibabel:  py -m pip install nibabel")

    root = Path(args.subject).expanduser().resolve()
    seg = root / "segmentations" if (root / "segmentations").is_dir() else root
    masks = sorted(seg.glob("*.nii.gz"))
    if not masks:
        raise SystemExit(f"No *.nii.gz masks in {seg}")

    names = vol.load_label_names(args.labels)
    id_of = {name: i for i, name in names.items()}

    out = None
    affine = header = None
    used, skipped, missing, overlaps = [], [], [], 0
    for path in masks:
        name = path.name[:-len(".nii.gz")]
        label = id_of.get(name)
        if label is None:
            missing.append(name)
            continue
        if not args.all and any(k in name for k in NOT_MUSCULOSKELETAL):
            skipped.append(name)
            continue
        img = nib.load(str(path))
        data = np.asarray(img.dataobj)
        if out is None:
            out = np.zeros(data.shape, dtype=np.int16)
            affine, header = img.affine, img.header
        elif data.shape != out.shape:
            raise SystemExit(
                f"{name}: shape {data.shape} does not match {out.shape}. The "
                f"masks of one subject must share a grid; these are from "
                f"different scans.")
        elif not np.allclose(img.affine, affine, atol=1e-4):
            raise SystemExit(
                f"{name}: its affine differs from the others', so merging "
                f"would silently misregister it.")
        mask = data > 0
        if not mask.any():
            continue
        clash = mask & (out > 0)
        overlaps += int(clash.sum())
        out[mask & (out == 0)] = label     # lower id wins, deterministically
        used.append(name)

    if out is None:
        raise SystemExit("No mask matched the label map; nothing to write.")

    nib.save(nib.Nifti1Image(out, affine, header), args.out)
    print(f"merged {len(used)} structures into {args.out}")
    print(f"  {int((out > 0).sum()):,} labelled voxels, "
          f"{len(np.unique(out)) - 1} distinct labels")
    if skipped:
        # Named, not just counted. A structure dropped on purpose and one
        # lost by accident look identical in a bare number.
        print(f"  {len(skipped)} skipped as not musculoskeletal "
              f"(pass --all to keep them): {', '.join(skipped[:8])}"
              + (" ..." if len(skipped) > 8 else ""))
    if missing:
        print(f"  {len(missing)} mask(s) not in the {args.labels} label map: "
              f"{', '.join(missing[:8])}")
    if overlaps:
        pct = 100.0 * overlaps / max(int((out > 0).sum()), 1)
        print(f"  {overlaps:,} voxels ({pct:.2f}%) were claimed by more than "
              f"one mask; the lower label id kept them")
        if pct > 1.0:
            print("  That is a lot. Masks that overlap by more than about a "
                  "border voxel are not describing separate structures, and "
                  "anything measured from them inherits the disagreement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
