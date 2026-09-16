"""Popliteal fossa rules on synthetic sections (scripts/cryo/vhf_popliteal_track.py, Q56).

The rules that are specific to this tracker, and that the Visible Human data cannot test on its own:
the DEPTH order of the seed (artery deepest, on the femur's popliteal surface), the fossa-context rule
that keeps the paired walk out of the dark striations inside a muscle belly, the plausibility gate, and
the numeric depth-order check that is run on the shipped label volume.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_popliteal_track as pt  # noqa: E402
from scripts.cryo.vhf_nerve_track import Crops, PX  # noqa: E402

H = W = 240


def _disk(img, r, c, rad_mm, rgb):
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    m = (yy - r) ** 2 + (xx - c) ** 2 <= (rad_mm / PX) ** 2
    img[m] = rgb
    return m


def _section(vessels=(), muscle_box=None):
    """Fossa fat (cream) with an optional striated dark-red belly and round black lumina."""
    im = np.zeros((H, W, 3), np.uint8)
    im[..., 0] = 170
    im[..., 1] = 140
    im[..., 2] = 100
    if muscle_box:
        r0, r1, c0, c1 = muscle_box
        im[r0:r1, c0:c1] = (85, 45, 35)
        im[r0:r1:4, c0:c1] = (46, 26, 20)                          # striations: dark, but inside the belly
    for (r, c, rad) in vessels:
        _disk(im, r, c, rad, (28, 18, 14))
    return im


def _crops(tmp_path, ys, images):
    levels = {str(y): {"zi": 10, "dcm": "x", "RS": -7.0, "CS": -120.0, "z_ras": y - 885.229, "z_src": y - 800,
                       "windows": {"right": [60, 60 + H, 36, 36 + W]}} for y in ys}
    json.dump({"y_atlas": ys, "levels": levels, "box_atlas": {"right": [0, 200, -150, 60]},
               "origin": [7.769, -885.229, 14.137], "H": 405, "sc": 0.99, "note": ""},
              open(tmp_path / "t_bbox.json", "w"))
    a = np.lib.format.open_memmap(tmp_path / "t_right.npy", mode="w+", dtype=np.uint8,
                                  shape=(len(ys), H, W, 3))
    for i, im in enumerate(images):
        a[i] = im
    a.flush()
    return Crops(str(tmp_path / "t"), "right")


# ---------------------------------------------------------------- the seed is a depth rule
def test_seed_pair_calls_the_anterior_member_the_artery():
    """+Z is anterior: the artery lies on the femur's popliteal surface, the vein behind it."""
    fem = {"x": 85.0, "z_post": -30.0, "z_mid": -12.0}
    deep = {"x": 82.0, "z": -42.0, "area_mm2": 30.0, "diam_mm": 6.2}
    superf = {"x": 85.0, "z": -50.0, "area_mm2": 50.0, "diam_mm": 8.0}
    a, v = pt.seed_pair([superf, deep], fem)
    assert a is deep and v is superf


def test_seed_pair_refuses_a_pair_in_front_of_the_femur():
    """Anything anterior to the popliteal surface is in the knee or the quadriceps, not in the fossa."""
    fem = {"x": 85.0, "z_post": -30.0, "z_mid": -12.0}
    front = [{"x": 84.0, "z": 5.0, "area_mm2": 30.0, "diam_mm": 6.2},
             {"x": 86.0, "z": -3.0, "area_mm2": 40.0, "diam_mm": 7.1}]
    assert pt.seed_pair(front, fem) == (None, None)


def test_seed_pair_refuses_members_too_far_apart_across():
    fem = {"x": 85.0, "z_post": -30.0, "z_mid": -12.0}
    wide = [{"x": 60.0, "z": -42.0, "area_mm2": 30.0, "diam_mm": 6.2},
            {"x": 100.0, "z": -50.0, "area_mm2": 40.0, "diam_mm": 7.1}]
    assert pt.seed_pair(wide, fem) == (None, None)


# ---------------------------------------------------------------- the fossa-context rule
def test_walk_pair_fossa_follows_a_pair_lying_in_fat(tmp_path):
    ys = list(range(-347, -353, -1))
    ims = [_section(vessels=[(120 + 2 * i, 120 + 2 * i, 3.0), (120 + 2 * i, 145 + 2 * i, 4.0)])
           for i in range(len(ys))]
    crops = _crops(tmp_path, ys, ims)
    lab, _ = ndi.label(ims[0][..., 0] < 60)
    out = pt.walk_pair_fossa(crops, ys, ys[0], lab == lab[120, 120], lab == lab[120, 145])
    for nm in ("artery", "vein"):
        assert [r["y"] for r in out[nm][0] if not r["gap"]] == ys, nm


def test_walk_pair_fossa_refuses_a_dark_stripe_inside_a_muscle_belly(tmp_path):
    """The walk's one failure mode: below the knee it follows the dark striations of gastrocnemius. A lumen
    sits in the fossa's FAT, so a candidate whose surroundings are muscle-red is refused."""
    ys = [-380, -381]
    im0 = _section(vessels=[(120, 120, 3.0), (120, 145, 4.0)])
    # next level: both true lumina gone, only a dark round patch deep inside a muscle belly nearby
    im1 = _section(muscle_box=(90, 200, 90, 200))
    _disk(im1, 124, 124, 3.0, (28, 18, 14))
    _disk(im1, 124, 149, 4.0, (28, 18, 14))
    crops = _crops(tmp_path, ys, [im0, im1])
    lab, _ = ndi.label(im0[..., 0] < 60)
    out = pt.walk_pair_fossa(crops, ys, ys[0], lab == lab[120, 120], lab == lab[120, 145])
    for nm in ("artery", "vein"):
        rows = out[nm][0]
        assert [r["y"] for r in rows if not r["gap"]] == [-380], (nm, rows)


def test_walk_pair_fossa_keeps_the_two_in_one_sheath(tmp_path):
    """A branch that runs away from its partner must not capture the walk (one popliteal sheath)."""
    ys = list(range(-347, -352, -1))
    ims = []
    for i in range(len(ys)):
        v = [(120 + i, 120 + i, 3.0), (120 + i, 145 + i, 4.0)]
        if i:
            v.append((120 + 9 * i, 120 - 9 * i, 3.0))
        ims.append(_section(vessels=v))
    crops = _crops(tmp_path, ys, ims)
    lab, _ = ndi.label(ims[0][..., 0] < 60)
    out = pt.walk_pair_fossa(crops, ys, ys[0], lab == lab[120, 120], lab == lab[120, 145])
    art = [r for r in out["artery"][0] if not r["gap"]]
    assert len(art) == len(ys)
    assert abs(art[-1]["x"] - art[0]["x"]) < 4.0


# ---------------------------------------------------------------- gate, cleaning, bookkeeping
def test_gate_nulls_the_implausible_and_the_short():
    assert pt.gate("artery", 6.5, 120, 120.0) is None
    assert "twice" in pt.gate("artery", 17.0, 120, 120.0)
    assert "far under" in pt.gate("artery", 2.0, 120, 120.0)
    assert "too short" in pt.gate("vein", 8.0, 5, 120.0)           # too few levels
    assert "too short" in pt.gate("vein", 8.0, 60, 12.0)           # too short a span


def test_cleaning_band_lets_a_collapsed_cadaveric_vein_through():
    """A cadaver vein has no pressure in it: under the textbook 7-11 mm is plausible and is kept."""
    assert pt.CLEAN_MM["vein"][0] < pt.EXPECTED_MM["vein"][0]
    rows = [{"y": -350, "gap": False, "x": 1, "z": 1, "diam_mm": 4.0, "solidity": 0.95},
            {"y": -351, "gap": False, "x": 1, "z": 1, "diam_mm": 20.0, "solidity": 0.95}]
    out, dropped = pt.clean_rows(rows, "vein", expected=pt.CLEAN_MM)
    assert dropped == 1 and [r["y"] for r in out if not r["gap"]] == [-350]


def test_labels_and_expectations_are_documented():
    assert pt.LAB_OF == {"artery": 1, "vein": 2, "tibial_n": 3, "common_fibular_n": 4}
    assert pt.EXPECTED_MM["artery"] == (5.0, 8.0) and pt.EXPECTED_MM["vein"] == (7.0, 11.0)


# ---------------------------------------------------------------- the numeric depth check
def test_depth_order_reads_the_shipped_volume(tmp_path):
    """depth_order() must report the mean atlas z per label per 10 mm band off the volume itself, with +Z
    anterior: artery deepest (largest z), then vein, then tibial nerve."""
    import nibabel as nib
    vol = np.zeros((40, 60, 30), np.uint8)
    vol[10:14, 40:44, :] = 1          # artery: most anterior (largest axis-1 index)
    vol[10:14, 30:34, :] = 2          # vein
    vol[10:14, 14:18, :] = 3          # tibial nerve: most posterior
    aff = np.diag([0.5, 0.5, 1.0, 1.0])
    aff[:3, 3] = [60.0, -80.0, -400.0]
    nib.save(nib.Nifti1Image(vol, aff), tmp_path / "v.nii.gz")
    (tmp_path / "labels.json").write_text(json.dumps(
        {"labels": {"1": "popliteal_a_r", "2": "popliteal_v_r", "3": "tibial_n"}}))
    bands = pt.depth_order(str(tmp_path / "v.nii.gz"), str(tmp_path / "labels.json"))
    assert bands
    for band in bands.values():
        assert band["popliteal_a_r"] > band["popliteal_v_r"] > band["tibial_n"]
