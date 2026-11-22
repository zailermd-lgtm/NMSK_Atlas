import numpy as np
import pytest

from scripts.transfer.shape_interp import interpolate_labels_z, _sdf


def _disc(shape, center, radius):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return ((yy - center[0]) ** 2 + (xx - center[1]) ** 2) <= radius ** 2


def test_sdf_sign_and_zero_crossing():
    m = _disc((40, 40), (20, 20), 8)
    sdf = _sdf(m)
    assert sdf[20, 20] < 0          # centre: inside, negative
    assert sdf[0, 0] > 0            # far corner: outside, positive
    assert np.isclose(sdf[20, 28], 0, atol=1.5)  # near the boundary


def test_sdf_all_or_nothing():
    empty = np.zeros((10, 10), bool)
    full = np.ones((10, 10), bool)
    assert np.all(np.isinf(_sdf(empty)) & (_sdf(empty) > 0))
    assert np.all(np.isinf(_sdf(full)) & (_sdf(full) < 0))


def test_interpolated_midslice_recovers_growing_disc():
    """Two real slices (z=0 radius 5, z=1 radius 9) of one label; a target spacing of 1/3
    should place an extra two slices between them whose radius grows monotonically."""
    Z, Y, X = 2, 40, 40
    vol = np.zeros((Z, Y, X), np.int32)
    vol[0][_disc((Y, X), (20, 20), 5)] = 1
    vol[1][_disc((Y, X), (20, 20), 9)] = 1
    out, zpos, report = interpolate_labels_z(vol, source_spacing_mm=1.0, target_spacing_mm=1 / 3)
    assert out.shape[0] == 4  # z index 0, 1/3, 2/3, 1 -> n_out = (2-1)*1/(1/3)+1 = 4
    areas = [(out[k] == 1).sum() for k in range(4)]
    assert areas == sorted(areas)  # strictly grows (or ties) slice to slice
    assert areas[0] == int((vol[0] == 1).sum())
    assert areas[-1] == int((vol[1] == 1).sum())
    # the two interpolated middle slices must be strictly between the two real areas
    assert areas[0] < areas[1] <= areas[2] < areas[-1]


def test_never_extrapolates_beyond_first_last_real_slice():
    """A label real only at z=2..4 of a 7-slice volume must contribute nothing to output
    z-positions below 2 or above 4, however fine the target spacing."""
    Z, Y, X = 7, 30, 30
    vol = np.zeros((Z, Y, X), np.int32)
    for k in (2, 3, 4):
        vol[k][_disc((Y, X), (15, 15), 6)] = 5
    out, zpos, report = interpolate_labels_z(vol, source_spacing_mm=1.0, target_spacing_mm=0.5)
    lab_present = (out == 5).any(axis=(1, 2))
    present_z = zpos[lab_present]
    assert present_z.min() >= 2 - 1e-9
    assert present_z.max() <= 4 + 1e-9
    # the real end slices themselves must be exactly recovered (unchanged) in the output
    z0_out = np.argmin(np.abs(zpos - 2)); z4_out = np.argmin(np.abs(zpos - 4))
    assert (out[z0_out] == 5).sum() == (vol[2] == 5).sum()
    assert (out[z4_out] == 5).sum() == (vol[4] == 5).sum()


def test_report_records_spacing_and_interpolated_fraction():
    Z, Y, X = 3, 20, 20
    vol = np.zeros((Z, Y, X), np.int32)
    vol[0][_disc((Y, X), (10, 10), 4)] = 7
    vol[2][_disc((Y, X), (10, 10), 4)] = 7
    out, zpos, report = interpolate_labels_z(vol, source_spacing_mm=1.0, target_spacing_mm=0.5)
    r = report["7"]
    assert r["source_spacing_mm"] == 1.0 and r["target_spacing_mm"] == 0.5
    assert r["n_real_slices"] == 2
    assert 0.0 < r["interpolated_fraction"] < 1.0  # some but not all voxels came from interpolation


def test_independent_labels_do_not_bleed():
    """Two disjoint labels, each real at different z's; interpolating must never let one
    label's shape leak into the other's slot."""
    Z, Y, X = 3, 20, 20
    vol = np.zeros((Z, Y, X), np.int32)
    vol[0][_disc((Y, X), (5, 5), 3)] = 1
    vol[2][_disc((Y, X), (5, 5), 3)] = 1
    vol[0][_disc((Y, X), (15, 15), 3)] = 2
    vol[2][_disc((Y, X), (15, 15), 3)] = 2
    out, zpos, report = interpolate_labels_z(vol, source_spacing_mm=1.0, target_spacing_mm=0.5)
    mid = np.argmin(np.abs(zpos - 1.0))
    assert set(np.unique(out[mid])) <= {0, 1, 2}
    assert (out[mid] == 1).sum() > 0 and (out[mid] == 2).sum() > 0


def test_rejects_coarser_target_than_source():
    vol = np.zeros((2, 5, 5), np.int32)
    with pytest.raises(ValueError):
        interpolate_labels_z(vol, source_spacing_mm=1.0, target_spacing_mm=2.0)
