"""Q151: shape-based (signed-distance) Z interpolation for a real, photograph-derived label
volume whose slice spacing is coarser than its own in-plane resolution -- e.g. the committed
forearm/hand cryosection masks (data/ct_sources/task_outputs/vh{f,m}_forearm_muscles_cryo.nii.gz,
vhf_hand_muscles_cryo.nii.gz), all built one REAL cryosection per z-mm (voxel_mm 0.5 x 0.5 x 1.0)
even where the specimen's native photograph spacing is finer (the female was actually sectioned
every 0.33 mm; only every ~3rd was ever classified into these volumes).

METHOD, per label independently (never across labels, so one structure's interpolation cannot
bleed into a neighbour): a real slice is a z-index that already has that label ANYWHERE in it.
Between two consecutive real slices for a label, its 2-D signed distance transform (positive
outside, negative inside, `scipy.ndimage.distance_transform_edt` on the mask and its complement)
is computed on each of the two real slices, linearly interpolated in z at the intermediate
target-spacing positions, and thresholded at 0 (SDF < 0 -> inside) -- the standard shape-based
slice interpolation (Raya & Udupa 1990). Never run before the label's first real slice or after
its last (NO EXTRAPOLATION): those target slices get nothing for this label, whatever else is
present in the volume. Where two consecutive real slices already sit at (or under) the target
spacing, or when a label's gap is a single missing slice pair, that gap is just linear SDF
interpolation the same way -- there is no separate "no interpolation needed" fast path other
than skipping when the two real slices are already adjacent in the OUTPUT index.

Returns the upsampled label volume, the new affine (z scale rewritten to target_spacing, same
x/y), and a per-label report: n_real_slices, source_spacing_mm, target_spacing_mm, and
interpolated_fraction (of this label's own final voxel count that came from an interpolated
z-slice rather than resampling exactly onto a real one).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def _sdf(mask: np.ndarray) -> np.ndarray:
    """Signed distance transform of a 2-D boolean mask: negative inside, positive outside,
    zero exactly at the boundary (edt of the outside minus edt of the inside)."""
    if not mask.any():
        return np.full(mask.shape, np.inf, dtype=np.float64)
    if mask.all():
        return np.full(mask.shape, -np.inf, dtype=np.float64)
    out = ndi.distance_transform_edt(~mask)
    inn = ndi.distance_transform_edt(mask)
    return out - inn


def interpolate_labels_z(labelvol: np.ndarray, source_spacing_mm: float, target_spacing_mm: float,
                          labels: list[int] | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    """labelvol: (Z, Y, X) int array, one real photograph-derived slice per z index, spaced
    `source_spacing_mm` apart. Returns (new_labelvol (Z', Y, X), z_positions (mm, length Z',
    the original z-index units so 0 == labelvol[0]), report {label: {...}}).

    `target_spacing_mm` must be <= source_spacing_mm (this only ever adds resolution the
    photographs' own in-plane pixels already have -- it never invents slices beyond the
    original stack's own extent or coarsens it)."""
    if target_spacing_mm <= 0 or target_spacing_mm > source_spacing_mm:
        raise ValueError(f"target_spacing_mm ({target_spacing_mm}) must be in (0, source_spacing_mm={source_spacing_mm}]")
    Z, Y, X = labelvol.shape
    if labels is None:
        labels = sorted(int(v) for v in np.unique(labelvol) if v != 0)
    # output z positions, in units of the ORIGINAL z index (so real slice k sits at z = k
    # exactly, guaranteeing the first/last real slice of every label reappears unchanged)
    n_out = int(round((Z - 1) * source_spacing_mm / target_spacing_mm)) + 1
    z_positions = np.arange(n_out) * (target_spacing_mm / source_spacing_mm)
    out = np.zeros((n_out, Y, X), np.int32)
    report: dict[str, dict] = {}
    for lab in labels:
        real_z = [k for k in range(Z) if (labelvol[k] == lab).any()]
        if not real_z:
            continue
        z0, z1 = real_z[0], real_z[-1]
        sdf_cache: dict[int, np.ndarray] = {}

        def sdf_at(k: int) -> np.ndarray:
            if k not in sdf_cache:
                sdf_cache[k] = _sdf(labelvol[k] == lab)
            return sdf_cache[k]

        placed_from_real = 0
        placed_interp = 0
        for oi, zp in enumerate(z_positions):
            if zp < z0 - 1e-9 or zp > z1 + 1e-9:
                continue  # strictly no extrapolation beyond this label's own first/last real slice
            lo = max(k for k in real_z if k <= zp + 1e-9)
            hi = min((k for k in real_z if k >= zp - 1e-9), default=lo)
            if lo == hi or abs(zp - lo) < 1e-9:
                mask = labelvol[lo] == lab
                placed_from_real += int(mask.sum())
            else:
                t = (zp - lo) / (hi - lo)
                sdf = (1 - t) * sdf_at(lo) + t * sdf_at(hi)
                mask = sdf < 0
                placed_interp += int(mask.sum())
            out[oi][mask] = lab
        total = placed_from_real + placed_interp
        report[str(lab)] = {
            "n_real_slices": len(real_z),
            "source_spacing_mm": source_spacing_mm,
            "target_spacing_mm": target_spacing_mm,
            "first_real_z_index": z0,
            "last_real_z_index": z1,
            "interpolated_fraction": (placed_interp / total) if total else 0.0,
        }
    return out, z_positions, report
