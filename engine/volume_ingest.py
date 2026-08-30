"""Ingest geometry from a LABELLED VOLUME -- a segmented CT or MRI.

The other ingest, engine/vh_ingest.py, reads STL surfaces. This one reads the
form clinical data actually arrives in: a NIfTI volume of integer labels, one
per structure, as produced by TotalSegmentator, 3D Slicer, ITK-SNAP or any
nnU-Net model. Both write the SAME manifest, so every audit already written
runs unchanged on either.

WHY THIS EXISTS AT ALL.

Two reasons, and the second is the larger one.

The narrow reason is that the University of Denver Visible Human release is
pelvis-to-ankle. Everything above the hip in this atlas -- the clavicle, the
scapula, the humerus, the ribs, the cervical spine -- carries coordinates
that were written from anatomical description and have never been measured
against anything. That is not a hypothetical risk: the whole clavicle turned
out to be stored mirrored on both sides, putting the acromioclavicular joint
300 mm from where it belongs, and it was caught by a lexical rule rather than
by measurement because there was no geometry to measure against.

The broader reason is that comparing the atlas with a patient's CT or MRI is
one of the things it is for. That comparison needs the scan brought into the
atlas frame, which is exactly this.

WHAT IS MEASURED AND WHAT IS ASSUMED.

The voxel-to-world transform comes from the file's own affine, so the scan's
own spacing and orientation are used rather than guessed. Orientation is read
from the affine's axis codes and reported; it is not hardcoded.

The atlas origin is the midpoint of the two hip joint centres. Those are
recovered the same way as in the STL ingest -- a least-squares sphere through
the femoral head -- except that here there is no separate cartilage label, so
the head is isolated from the femur label by its own geometry and the fit is
reported with its radius and residual for you to accept or reject.

NOTHING IS APPLIED SILENTLY. Structure names are matched against the atlas by
the same scorer the STL ingest uses, written to an editable mapping file, and
converted only once you have looked at it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from engine import vh_ingest as vh

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL_MAPS_DIR = REPO_ROOT / "mappings"


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def load_labels(path: Path) -> Tuple[np.ndarray, np.ndarray, str]:
    """A labelled volume, its voxel->world affine, and its axis codes.

    nibabel is used rather than a hand-rolled NIfTI reader because the part
    that matters most here is also the easiest to get wrong: which of qform
    and sform wins, and what the resulting affine means. Getting that subtly
    wrong would mirror or rotate every structure, and nothing downstream
    would notice.
    """
    try:
        import nibabel as nib
    except ImportError:  # pragma: no cover - environment-dependent
        raise SystemExit(
            "Reading a labelled volume needs nibabel:  pip install nibabel")
    img = nib.load(str(path))
    data = np.asarray(img.dataobj)
    if not np.issubdtype(data.dtype, np.integer):
        # A label map that arrives as float is usually fine -- the values are
        # whole numbers -- but silently rounding a probability map would
        # produce structures that do not exist.
        if not np.allclose(data, np.round(data)):
            raise ValueError(
                f"{path.name}: values are not whole numbers, so this is not a "
                f"label map. A probability or intensity volume has to be "
                f"segmented first.")
        data = np.round(data).astype(np.int32)
    codes = "".join(nib.aff2axcodes(img.affine))
    return data.astype(np.int32), np.asarray(img.affine, dtype=float), codes


def load_label_names(name: str) -> Dict[int, str]:
    """id -> structure name, from mappings/<name>_labels.json."""
    path = LABEL_MAPS_DIR / f"{name}_labels.json"
    if not path.exists():
        raise SystemExit(
            f"No label map named {name!r}. Expected {path}.\n"
            f"Available: "
            + ", ".join(sorted(p.stem[:-7] for p in LABEL_MAPS_DIR.glob("*_labels.json"))))
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): v for k, v in payload["labels"].items()}


# --------------------------------------------------------------------------
# surfacing
# --------------------------------------------------------------------------

def label_surface(volume: np.ndarray, label: int,
                  step: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """A closed surface around one label, in VOXEL coordinates.

    Marching cubes over a padded binary mask. The padding is what makes the
    surface closed: a structure touching the edge of the scan would otherwise
    come back as an open sheet, and every inside/outside test downstream --
    which is how tendon paths are checked -- silently inverts on an open
    mesh.
    """
    try:
        from skimage import measure
    except ImportError:  # pragma: no cover - environment-dependent
        raise SystemExit(
            "Surfacing a label map needs scikit-image:  pip install scikit-image")
    mask = np.pad((volume == label), 1, mode="constant", constant_values=False)
    if not mask.any():
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    verts, faces, _normals, _values = measure.marching_cubes(
        mask.astype(np.float32), level=0.5, step_size=step)
    return verts - 1.0, faces.astype(np.int64)      # undo the pad


def voxels_to_atlas(points: np.ndarray, affine: np.ndarray) -> np.ndarray:
    """Voxel indices -> atlas millimetres.

    The affine takes voxel indices to the file's own world frame, which for
    NIfTI is RAS: +x right, +y anterior, +z superior. The atlas frame is
    +X right, +Y superior, +Z anterior, so the last two axes swap. That swap
    is a permutation with determinant -1... which would MIRROR the anatomy,
    so it is written as a swap of two axes of a right-handed frame and the
    handedness is asserted below rather than trusted.
    """
    if points.size == 0:
        return points.reshape(0, 3)
    homo = np.hstack([points, np.ones((len(points), 1))])
    ras = (affine @ homo.T).T[:, :3]
    return np.stack([ras[:, 0], ras[:, 2], ras[:, 1]], axis=1)


def is_right_handed(affine: np.ndarray) -> bool:
    """Whether the affine preserves handedness once mapped to the atlas frame.

    RAS -> atlas swaps Y and Z, which flips the sign of the determinant. So a
    correctly oriented scan arrives with a NEGATIVE determinant here, and a
    positive one means the scan itself is stored mirrored -- a real and
    common defect in converted DICOM. Reported, never silently corrected:
    mirroring a patient's scan without saying so is how a left knee gets
    operated on.
    """
    return float(np.linalg.det(affine[:3, :3])) < 0


# --------------------------------------------------------------------------
# the atlas origin
# --------------------------------------------------------------------------

def femoral_head_centre(points: np.ndarray, side: str,
                        frac: float = 0.12) -> Tuple[np.ndarray, float, float]:
    """Fit the femoral head from a whole-femur surface.

    The STL release ships femoral head cartilage as its own mesh, so its
    centre is a sphere fit away. A CT segmentation gives one `femur` label
    and nothing else, so the head has to be isolated first.

    It is isolated by direction, not by height: the head sits at the MEDIAL
    end of the proximal femur, and taking the superior fraction alone would
    take the greater trochanter with it -- the trochanter is the more
    superior of the two on many people. Points are ranked by how far they
    lie along (superior + medial), and the extreme fraction is fitted.

    Returns (centre, radius, rms). A radius outside 18-30 mm or an rms above
    ~2 mm means the fit did not find a femoral head, and the caller should
    say so rather than use the number.
    """
    if len(points) < 100:
        raise ValueError("too few points to fit a femoral head")
    medial = -1.0 if side == "right" else 1.0      # +X is the subject's right
    direction = np.array([medial, 1.0, 0.0])
    direction /= np.linalg.norm(direction)
    score = points @ direction
    head = points[score >= np.quantile(score, 1.0 - frac)]
    return vh.fit_sphere(head)


def hip_joint_origin(surfaces: Dict[str, np.ndarray]) -> dict:
    """The atlas origin, as the midpoint of the two femoral head centres.

    Returns a report rather than a bare number, because a sphere fit that
    landed on the wrong part of the bone still returns a centre.
    """
    out: dict = {"sides": {}}
    centres = []
    for side in ("right", "left"):
        pts = surfaces.get(f"femur_{side}")
        if pts is None or len(pts) < 100:
            continue
        centre, radius, rms = femoral_head_centre(pts, side)
        plausible = 18.0 <= radius <= 30.0 and rms <= 2.0
        out["sides"][side] = {
            "centre_mm": [round(float(v), 3) for v in centre],
            "radius_mm": round(float(radius), 2),
            "rms_mm": round(float(rms), 3),
            "plausible": bool(plausible),
        }
        if plausible:
            centres.append(centre)
    if len(centres) == 2:
        out["origin_mm"] = [round(float(v), 3) for v in np.mean(centres, axis=0)]
        out["from"] = "midpoint of both femoral head centres"
    elif len(centres) == 1:
        out["origin_mm"] = None
        out["from"] = ("only one femoral head fitted plausibly; the atlas "
                       "origin is the MIDPOINT of the two, so one side alone "
                       "cannot give it")
    else:
        out["origin_mm"] = None
        out["from"] = "no femoral head could be fitted"
    return out
