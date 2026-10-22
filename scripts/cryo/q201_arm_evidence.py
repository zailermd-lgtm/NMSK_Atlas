"""Q201: bone evidence of HIS two arms (VH male) for the elbow chain -> data/derived/Q201_vhm_arm_evidence.npz

Source = `data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz` (his CT bone labels, completed through his colour cryosection photographs where the CT field of view clips
the arms: scripts/cryo/complete_arm_bones_from_cryo.py, registered per slice onto the CT bones; mapping/README in mappings/vhm_arm_labels.json).  Label ids: humerus 1 / 5, radius 2 / 6, ulna 3 / 7
(right / left).  Measured: the label voxels ARE the surfaces of the shipped own bones (build/vh/ct_vhm_arm, 1.0-1.6 mm median) with the world -> atlas shift (+6.0, +895.4 along z, -4.8 along y).

What is evidence and what is not (measured on the label volume, see PROJECT_STATE Q201):
  * the elbow zone (atlas y 236 .. 335): the labels of the three bones are ONE cream bone mass in his photographs (humeral epicondyles + olecranon + coronoid + radial head); the split into
    humerus / radius / ulna is a joint-line plane the completion drew (the "humerus" label there is 1100-2060 mm2 per slice = humerus + olecranon; the left "ulna" label at y 254-260 holds the
    radial head too; right radial head partly labelled as ulna).  So the zone is used as ONE UNION solid, never per bone.
  * outside the zone each bone label is its own measurement (CT): humerus y > 335, radius / ulna y < 236 (wrist included).
Output (per side l / r; atlas mm): union_<s> = the solid union voxels of the zone (int16), shaft_<b>_<s> = surface voxels of each bone label outside the zone (int16).
    python3 scripts/cryo/q201_arm_evidence.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
NII = REPO / "data" / "ct_sources" / "task_outputs" / "vhm_arm_bones_cryo_completed.nii.gz"
OUT = REPO / "data" / "derived" / "Q201_vhm_arm_evidence.npz"
WORLD_TO_ATLAS = np.array([6.0, 895.4, -4.8])         # atlas = (x, z, y) of the label world + this (measured, Q201)
ZONE = (236.0, 335.0)                                  # atlas y of the elbow union
LABELS = {"r": {"humerus": 1, "radius": 2, "ulna": 3}, "l": {"humerus": 5, "radius": 6, "ulna": 7}}


def to_atlas(ii, affine):
    w = ii @ affine[:3, :3].T + affine[:3, 3]
    return np.c_[w[:, 0], w[:, 2], w[:, 1]] + WORLD_TO_ATLAS


def extract(a, affine, zone=ZONE):
    out = {}
    for s, labs in LABELS.items():
        m_all = np.isin(a, list(labs.values()))
        ii = np.argwhere(m_all)
        P = to_atlas(ii, affine)
        inz = (P[:, 1] >= zone[0]) & (P[:, 1] <= zone[1])
        out[f"union_{s}"] = np.round(P[inz]).astype(np.int16)
        for b, l in labs.items():
            m = a == l
            surf = m & ~ndi.binary_erosion(m)
            P = to_atlas(np.argwhere(surf), affine)
            ok = P[:, 1] > zone[1] if b == "humerus" else P[:, 1] < zone[0]
            out[f"shaft_{b}_{s}"] = np.round(P[ok]).astype(np.int16)
    return out


def load(path: Path = OUT) -> dict:
    z = np.load(path)
    return {k: z[k].astype(float) for k in z.files if k != "note"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    import nibabel as nib
    im = nib.load(NII)
    arr = np.asarray(im.dataobj)
    out = extract(arr, im.affine)
    np.savez_compressed(a.out, note=np.array("Q201: his arm bone evidence (completed labels, atlas mm); scripts/cryo/q201_arm_evidence.py"), **out)
    print("wrote", a.out, {k: len(v) for k, v in out.items()})


if __name__ == "__main__":
    main()
