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


def load_atlas_mapping(name: str) -> Dict[str, dict]:
    """Reviewed structure-name -> atlas-entity decisions for a label map.

    The override table the STL ingest uses keys on a tissue-class token
    ('bone|talus'), which CT structure names do not carry, so these live
    beside the label numbering instead. Without them 63 of the 90
    musculoskeletal and vascular structures in this release map to nothing:
    'rib_left_7' scores 0.17 against an atlas that carries one 'ribs_l'.
    """
    path = LABEL_MAPS_DIR / f"{name}_labels.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("atlas", {})


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

def mask_surface(mask: np.ndarray, step: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """A closed surface around a binary mask, in VOXEL coordinates.

    Marching cubes over a padded mask. The padding is what makes the surface
    closed: a structure touching the edge of the scan would otherwise come
    back as an open sheet, and every inside/outside test downstream -- which
    is how tendon paths are checked -- silently inverts on an open mesh.
    """
    try:
        from skimage import measure
    except ImportError:  # pragma: no cover - environment-dependent
        raise SystemExit(
            "Surfacing a label map needs scikit-image:  pip install scikit-image")
    padded = np.pad(mask.astype(bool), 1, mode="constant", constant_values=False)
    if not padded.any():
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    verts, faces, _normals, _values = measure.marching_cubes(
        padded.astype(np.float32), level=0.5, step_size=step)
    return verts - 1.0, faces.astype(np.int64)      # undo the pad


def label_surface(volume: np.ndarray, label: int,
                  step: int = 1) -> Tuple[np.ndarray, np.ndarray]:
    """A closed surface around one label, in VOXEL coordinates."""
    return mask_surface(volume == label, step=step)


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
# splitting one label into several atlas entities
# --------------------------------------------------------------------------
#
# Two labels in the TotalSegmentator release each hold what the atlas keeps
# as separate entities: `aorta` is one label from the root to the
# bifurcation, where the atlas has the arch, the descending thoracic and the
# abdominal aorta; `costal_cartilages` is one label over both sides, where
# the atlas has a right and a left. Mapping either to any one entity would
# be wrong for most of its extent, so both were refused until the split was
# written. The splits below are measured from the scan itself -- from the
# vertebrae it labels and from its own midline -- never from a fixed
# millimetre value, because every scan is a different body.
#
# A splitter takes the whole volume (it needs the OTHER labels to locate its
# cuts), the label to split, the affine, and name -> id for the label map.
# It returns {part name: boolean mask} plus notes on where the cuts fell,
# for the operator to read. Missing context is a ValueError with the reason.

_THORACIC_VERTEBRAE = tuple(f"vertebrae_T{i}" for i in range(1, 13))


def atlas_points_of(mask: np.ndarray, affine: np.ndarray
                    ) -> Tuple[np.ndarray, np.ndarray]:
    """(voxel indices, atlas-frame mm) of every set voxel."""
    idx = np.argwhere(mask)
    return idx, voxels_to_atlas(idx.astype(float), affine)


def _centroid_y(volume, affine, label_ids, name) -> Optional[float]:
    lid = label_ids.get(name)
    if lid is None:
        return None
    mask = volume == lid
    if not mask.any():
        return None
    return float(atlas_points_of(mask, affine)[1][:, 1].mean())


def disc_level(volume: np.ndarray, affine: np.ndarray, label_ids: Dict[str, int],
               upper: str, lower: str) -> Optional[float]:
    """Superior (atlas Y) coordinate of the disc between two named vertebrae.

    Taken as the midpoint of the two vertebrae's centroids. A vertebra label
    includes its spinous process, which slopes below the body's inferior
    endplate, so the centroid sits a few millimetres below the body's own
    centre -- on both vertebrae alike, so the midpoint is barely moved.
    None when either vertebra is not in the scan; the caller decides what
    that means for its cut.
    """
    ys = [_centroid_y(volume, affine, label_ids, n) for n in (upper, lower)]
    if ys[0] is None or ys[1] is None:
        return None
    if ys[0] <= ys[1]:
        raise ValueError(
            f"{upper} (Y={ys[0]:.1f}) is not above {lower} (Y={ys[1]:.1f}): the "
            f"scan's superior axis is not where its affine says it is")
    return float(np.mean(ys))


def split_aorta(volume: np.ndarray, label: int, affine: np.ndarray,
                label_ids: Dict[str, int]) -> Tuple[Dict[str, np.ndarray], List[str]]:
    """aorta -> arch / ascending / descending_thoracic / abdominal.

    Two horizontal cuts, each located from the vertebrae the same scan
    labels: the arch ends at the lower border of T4, so everything above the
    T4/T5 disc is arch; the aortic hiatus is at T12, so everything below the
    T12/L1 disc is abdominal. Between the two cuts the label has TWO columns
    -- the ascending aorta in front of the heart and the descending aorta on
    the vertebral bodies -- which no horizontal plane separates and which
    connected components do: the posterior column is the descending aorta.

    A scan that stops above T12 has no abdominal part, and one that starts
    below T4 has no arch; each missing level is reported and that part is
    left empty rather than guessed at. A scan with neither pair of vertebrae
    cannot be split and says so.
    """
    from scipy import ndimage

    mask = volume == label
    if not mask.any():
        raise ValueError("the aorta label is empty")
    idx, pts = atlas_points_of(mask, affine)
    y, z = pts[:, 1], pts[:, 2]
    notes: List[str] = []

    arch_level = disc_level(volume, affine, label_ids, "vertebrae_T4", "vertebrae_T5")
    hiatus_level = disc_level(volume, affine, label_ids, "vertebrae_T12", "vertebrae_L1")
    if arch_level is None and hiatus_level is None:
        raise ValueError("neither T4/T5 nor T12/L1 is in this scan, so no cut "
                         "in the aorta can be located")
    if arch_level is None:
        notes.append("T4/T5 not in the scan: no arch part; the whole label is "
                     "treated as below the arch")
        arch_level = np.inf
    else:
        notes.append(f"arch ends at the T4/T5 disc, Y={arch_level:.1f} mm")
    if hiatus_level is None:
        notes.append("T12/L1 not in the scan: no abdominal part")
        hiatus_level = -np.inf
    else:
        notes.append(f"aortic hiatus at the T12/L1 disc, Y={hiatus_level:.1f} mm")

    def blank():
        return np.zeros(mask.shape, dtype=bool)

    parts = {k: blank() for k in ("arch", "ascending", "descending_thoracic",
                                  "abdominal")}
    above = y > arch_level
    parts["arch"][tuple(idx[above].T)] = True

    below = blank()
    below[tuple(idx[~above].T)] = True
    comp, n = ndimage.label(below)
    if n == 0:
        notes.append("nothing below the arch level")
        return parts, notes
    sizes = ndimage.sum(below, comp, index=range(1, n + 1))
    by_size = [int(c) for c in np.argsort(sizes)[::-1] + 1]
    comp_of = comp[tuple(idx[~above].T)]
    z_below = z[~above]
    mean_z = {c: float(z_below[comp_of == c].mean()) for c in by_size}

    if n == 1:
        descending, ascending = {by_size[0]}, set()
        notes.append("one column below the arch level: taken as the "
                     "descending aorta (no ascending aorta in the scan)")
    else:
        a, b = by_size[0], by_size[1]
        desc_c, asc_c = (a, b) if mean_z[a] < mean_z[b] else (b, a)
        descending, ascending = {desc_c}, {asc_c}
        for c in by_size[2:]:
            near_desc = abs(mean_z[c] - mean_z[desc_c]) <= abs(mean_z[c] - mean_z[asc_c])
            (descending if near_desc else ascending).add(c)
        notes.append(f"below the arch: descending column at Z={mean_z[desc_c]:.1f} mm "
                     f"(posterior), ascending at Z={mean_z[asc_c]:.1f} mm; "
                     f"{n} components")

    sel = np.isin(comp_of, list(ascending))
    parts["ascending"][tuple(idx[~above][sel].T)] = True
    sel = np.isin(comp_of, list(descending))
    desc_idx, desc_y = idx[~above][sel], y[~above][sel]
    parts["descending_thoracic"][tuple(desc_idx[desc_y > hiatus_level].T)] = True
    parts["abdominal"][tuple(desc_idx[desc_y <= hiatus_level].T)] = True
    return parts, notes


def midline_x(volume: np.ndarray, affine: np.ndarray,
              label_ids: Dict[str, int]) -> Tuple[float, str]:
    """The body's median plane, as an atlas X, measured from the scan.

    The sternum is the midline structure a thoracic label map is most likely
    to carry; failing that, the thoracic vertebral bodies. Either is the
    subject's own midline, which is not the scanner's X=0.
    """
    lid = label_ids.get("sternum")
    if lid is not None and (volume == lid).any():
        return float(atlas_points_of(volume == lid, affine)[1][:, 0].mean()), "sternum"
    xs = []
    for name in _THORACIC_VERTEBRAE:
        lid = label_ids.get(name)
        if lid is not None and (volume == lid).any():
            xs.append(atlas_points_of(volume == lid, affine)[1][:, 0].mean())
    if xs:
        return float(np.mean(xs)), f"{len(xs)} thoracic vertebrae"
    raise ValueError("no sternum and no thoracic vertebra in this scan, so the "
                     "midline cannot be measured")


def split_at_midline(volume: np.ndarray, label: int, affine: np.ndarray,
                     label_ids: Dict[str, int]) -> Tuple[Dict[str, np.ndarray], List[str]]:
    """One bilateral label -> right / left, cut at the measured midline."""
    mask = volume == label
    if not mask.any():
        raise ValueError("the label is empty")
    mid, source = midline_x(volume, affine, label_ids)
    idx, pts = atlas_points_of(mask, affine)
    right = np.zeros(mask.shape, dtype=bool)
    left = np.zeros(mask.shape, dtype=bool)
    on_right = pts[:, 0] > mid                    # +X is the subject's right
    right[tuple(idx[on_right].T)] = True
    left[tuple(idx[~on_right].T)] = True
    notes = [f"midline at X={mid:.1f} mm from the {source}; "
             f"{int(on_right.sum())} voxels right, {int((~on_right).sum())} left"]
    return {"right": right, "left": left}, notes


LABEL_SPLITTERS = {
    "aorta_by_vertebral_level": split_aorta,
    "midline": split_at_midline,
}


# --------------------------------------------------------------------------
# the atlas origin
# --------------------------------------------------------------------------

def proximal_head_centre(points: np.ndarray, side: str,
                         frac: float = 0.12) -> Tuple[np.ndarray, float, float]:
    """Fit the ball head at the proximal end of a long bone.

    The STL release ships femoral head cartilage as its own mesh, so its
    centre is a sphere fit away. A CT segmentation gives one `femur` label,
    or one `humerus` label, and nothing else -- so the head has to be
    isolated from the rest of the bone first.

    It is isolated by DIRECTION, not by height. Both heads sit at the
    superior-MEDIAL corner of their bone and both have a lateral prominence
    beside them -- the greater trochanter, the greater tubercle -- that on
    many people reaches HIGHER than the head does. Taking the superior
    fraction alone therefore fits the prominence and calls it the joint
    centre. Points are ranked along (superior + medial) instead, and the
    extreme fraction is fitted.

    Returns (centre, radius, rms). The caller judges plausibility, because
    what counts as a plausible radius differs by joint.
    """
    if len(points) < 100:
        raise ValueError("too few points to fit a joint head")
    medial = -1.0 if side == "right" else 1.0      # +X is the subject's right
    direction = np.array([medial, 1.0, 0.0])
    direction /= np.linalg.norm(direction)
    score = points @ direction
    head = points[score >= np.quantile(score, 1.0 - frac)]
    return vh.fit_sphere(head)


# Kept as a name because it says which joint is meant at the call site.
femoral_head_centre = proximal_head_centre
humeral_head_centre = proximal_head_centre

# Plausible radii, in millimetres. A fit that lands on the wrong part of the
# bone still returns a centre, so the radius is what catches it: a femoral
# head is 20-28 mm across the adult range and a humeral head 20-27, while a
# trochanter or tubercle fitted as a sphere comes back far off either.
HEAD_RADIUS_MM = {"femur": (18.0, 30.0), "humerus": (16.0, 30.0)}


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
        centre, radius, rms = proximal_head_centre(pts, side)
        lo, hi = HEAD_RADIUS_MM["femur"]
        plausible = lo <= radius <= hi and rms <= 2.0
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
