"""The pure trunk-wall rules (scripts/trunk_wall_from_ct.py) on synthetic label volumes whose answer is known by
construction: a lung sphere over a liver sphere must give a sheet at their interface of the requested thickness, and two
rib bars must give an intercostal band between them, no deeper than the ribs."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts import trunk_wall_from_ct as tw  # noqa: E402

SP = (1.0, 1.0, 1.0)


def _sphere(shape, c, r):
    g = np.indices(shape).astype(float)
    return ((g[0] - c[0]) ** 2 + (g[1] - c[1]) ** 2 + (g[2] - c[2]) ** 2) <= r * r


def test_sheet_between_lung_and_liver_spheres_has_the_requested_thickness():
    shape = (80, 80, 100)
    lung = _sphere(shape, (40, 40, 66), 20)          # bottom at z=46
    liver = _sphere(shape, (40, 40, 22), 20)         # top at z=42 -> 4 mm gap (z=43..45)
    sheet, parts = tw.diaphragm_dome(lung, liver, SP, thickness=4.0)
    assert not (sheet & (lung | liver)).any()
    col = sheet[40, 40, :]
    assert 3 <= col.sum() <= 5                         # the whole 4 mm gap, +-1 voxel of discretisation
    assert col[43:46].all()
    # continuous over the interface: every column within 12 mm of the axis holds sheet voxels
    yy, xx = np.mgrid[0:80, 0:80]
    near = (xx - 40) ** 2 + (yy - 40) ** 2 <= 12 ** 2
    assert sheet.any(axis=2)[near].all()
    assert parts["gap_fill"][40, 40, 44]


def test_wide_gap_hugs_the_liver_with_a_4mm_shell():
    shape = (80, 80, 120)
    lung = _sphere(shape, (40, 40, 88), 20)          # bottom at z=68
    liver = _sphere(shape, (40, 40, 30), 20)         # top at z=50 -> 18 mm gap: too wide to fill, within the 20 mm reach
    sheet, parts = tw.diaphragm_dome(lung, liver, SP, thickness=4.0)
    col = np.where(parts["apposition"][40, 40, :])[0]
    assert col.size and col.min() == 51 and 3 <= col.size <= 5      # 4 mm on the liver
    assert not parts["lung_base"][36:45, 36:45, :].any()               # a viscus within reach: no lung-base fallback there
    assert not sheet[40, 40, 56:68].any()                            # nothing floating mid-gap or under the lung
    assert not parts["apposition"][40, 40, :50].any()                # nothing on the liver's far side


def test_lung_with_no_viscus_in_reach_gets_a_4mm_base_shell():
    shape = (80, 80, 140)
    lung = _sphere(shape, (40, 40, 108), 20)         # bottom at z=88
    liver = _sphere(shape, (40, 40, 22), 18)         # top at z=40 -> 48 mm gap, beyond the 20 mm reach
    sheet, parts = tw.diaphragm_dome(lung, liver, SP, thickness=4.0)
    base = np.where(parts["lung_base"][40, 40, :])[0]
    assert base.size and base.max() == 87 and 3 <= base.size <= 5   # 4 mm under the lung
    assert not parts["lung_base"][40, 40, 110:].any()                # never over the lung's top
    assert not parts["apposition"].any() and not sheet[40, 40, 45:80].any()


def test_intercostal_band_lies_between_two_rib_bars_at_rib_depth():
    shape = (100, 40, 60)
    ribs = np.zeros(shape, bool)
    ribs[10:90, 16:24, 20:28] = True                  # rib n: 8 mm deep (y), 8 mm tall (z)
    ribs[10:90, 16:24, 42:50] = True                  # rib n+1, 14 mm space (z=28..41)
    band = tw.intercostal_band(ribs, SP, close_r=14.0)
    assert not (band & ribs).any()
    zs = np.where(band.any(axis=(0, 1)))[0]
    assert zs.min() >= 28 and zs.max() <= 41 and band[50, 20, 28:42].all()
    ys = np.where(band.any(axis=(0, 2)))[0]
    assert ys.min() >= 15 and ys.max() <= 24          # no deeper than the ribs (+-1 voxel)
    xs = np.where(band.any(axis=(1, 2)))[0]
    assert xs.min() >= 9 and xs.max() <= 90           # does not run past the rib ends
