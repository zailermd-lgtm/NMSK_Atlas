"""Femoral bundle rules on synthetic sections (scripts/cryo/vhf_femoral_track.py, Q55)."""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_femoral_track as ft  # noqa: E402
from scripts.cryo.vhf_nerve_track import Crops, PX  # noqa: E402

H = W = 240


def _disk(img, r, c, rad_mm, rgb):
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    m = (yy - r) ** 2 + (xx - c) ** 2 <= (rad_mm / PX) ** 2
    img[m] = rgb
    return m


def _section(vessels=(), muscle=True):
    """Pale connective background, an optional striated dark-red muscle belly, and round black lumina."""
    im = np.zeros((H, W, 3), np.uint8)
    im[..., 0] = 170; im[..., 1] = 140; im[..., 2] = 100          # fat / connective tissue
    if muscle:
        blk = np.zeros((H, W), bool); blk[20:100, 20:110] = True
        im[blk] = (85, 45, 35)
        stripes = np.zeros((H, W), bool); stripes[20:100:4, 20:110] = True
        im[stripes & blk] = (46, 26, 20)                          # striations dip to 46: not a lumen
    for (r, c, rad) in vessels:
        _disk(im, r, c, rad, (28, 18, 14))
    return im


def test_outside_gel_keeps_interior_blue():
    blue = np.zeros((H, W), bool)
    blue[:, :6] = True                                            # embedding gel at the crop edge
    blue[120:140, 120:140] = True                                 # blue-black clot deep inside the limb
    gel = ft.outside_gel(blue)
    assert gel[:, :6].all()
    assert not gel[120:140, 120:140].any()


def test_blob_stats_diameter_of_a_known_disk():
    im = _section(vessels=[(150, 150, 4.0)], muscle=False)
    mask = im[..., 0] < 60
    s = ft.blob_stats(mask)
    assert abs(s["diam_mm"] - 8.0) < 0.5                          # radius 4 mm -> 8 mm across
    assert abs(s["inscribed_mm"] - 8.0) < 1.0
    assert s["solidity"] > 0.9 and s["aspect"] < 1.2


def test_vessel_candidates_take_lumina_and_reject_muscle():
    im = _section(vessels=[(150, 150, 4.0), (150, 185, 3.0)])
    cor = np.ones((H, W), bool)
    cands, lab = ft.vessel_candidates(im, cor, ft.FEMORAL)
    assert len(cands) == 2, [c["diam_mm"] for c in cands]
    assert all(c["rc"][0] > 110 for c in cands)                   # nothing from the striated belly
    ds = sorted(c["diam_mm"] for c in cands)
    assert abs(ds[0] - 6.0) < 1.0 and abs(ds[1] - 8.0) < 1.0


def test_vessel_candidates_reject_a_blob_without_a_pale_wall():
    im = _section(muscle=False)
    im[...] = (70, 40, 30)                                        # dark all over: no wall contrast
    _disk(im, 150, 150, 4.0, (28, 18, 14))
    cands, _ = ft.vessel_candidates(im, np.ones((H, W), bool), ft.FEMORAL)
    assert cands == []


def test_seed_pair_puts_the_artery_lateral_on_both_sides():
    mid = {"x": 70.0, "z": 35.0}
    lat = {"x": 80.0, "z": 34.0, "area_mm2": 40.0, "diam_mm": 7.1}
    med = {"x": 70.0, "z": 36.0, "area_mm2": 90.0, "diam_mm": 10.7}
    far = {"x": 150.0, "z": 30.0, "area_mm2": 200.0, "diam_mm": 16.0}
    a, v = ft.seed_pair([lat, med, far], mid, "right")
    assert a is lat and v is med                                  # right: lateral = larger x
    lat_l = dict(lat, x=-80.0); med_l = dict(med, x=-70.0)
    a, v = ft.seed_pair([lat_l, med_l], {"x": -70.0, "z": 35.0}, "left")
    assert a is lat_l and v is med_l                              # left: lateral = smaller x


def _crops(tmp_path, ys, images):
    levels = {str(y): {"zi": 10, "dcm": "x", "RS": -7.0, "CS": -120.0, "z_ras": y - 885.229, "z_src": y - 800,
                       "windows": {"right": [60, 60 + H, 36, 36 + W]}} for y in ys}
    json.dump({"y_atlas": ys, "levels": levels, "box_atlas": {"right": [0, 200, -150, 60]},
               "origin": [7.769, -885.229, 14.137], "H": 405, "sc": 0.99, "note": ""},
              open(tmp_path / "t_bbox.json", "w"))
    a = np.lib.format.open_memmap(tmp_path / "t_right.npy", mode="w+", dtype=np.uint8, shape=(len(ys), H, W, 3))
    for i, im in enumerate(images):
        a[i] = im
    a.flush()
    return Crops(str(tmp_path / "t"), "right")


def test_walk_vessel_follows_a_drifting_lumen_and_stops_when_it_ends(tmp_path):
    ys = list(range(0, -8, -1))
    ims, masks = [], []
    for i, _ in enumerate(ys):
        im = _section(vessels=[(150 + 3 * i, 150 + 3 * i, 4.0)] if i < 6 else [], muscle=False)
        ims.append(im); masks.append(im[..., 0] < 60)
    crops = _crops(tmp_path, ys, ims)
    rows, got = ft.walk_vessel(crops, ys, ys[0], masks[0])
    tracked = [r for r in rows if not r["gap"]]
    assert [r["y"] for r in tracked] == ys[:6]                    # follows 6 levels, then the lumen is gone
    assert all(abs(r["diam_mm"] - 8.0) < 1.0 for r in tracked)
    assert rows[-1]["y"] == -5                                    # trailing gaps trimmed


def test_walk_vessel_will_not_jump_to_a_second_lumen(tmp_path):
    """The vein must not be captured by the artery's walk: a blob 20 mm away is out of reach."""
    ys = [0, -1]
    im0 = _section(vessels=[(150, 150, 4.0)], muscle=False)
    im1 = _section(vessels=[(150, 210, 4.0)], muscle=False)       # only a far blob on the next level
    crops = _crops(tmp_path, ys, [im0, im1])
    rows, _ = ft.walk_vessel(crops, ys, 0, im0[..., 0] < 60)
    assert len([r for r in rows if not r["gap"]]) == 1


def test_hiatus_and_report_expectations_are_documented():
    assert ft.EXPECTED_MM["artery"] == (5.0, 9.0) and ft.EXPECTED_MM["vein"] == (7.0, 13.0)
    assert ft.LAB_OF == {"artery": 1, "vein": 2, "nerve": 3}


def test_walk_pair_keeps_the_two_in_one_sheath(tmp_path):
    """A branch that leaves its partner behind (profunda / great saphenous) must not capture the walk."""
    ys = list(range(0, -6, -1))
    ims, first = [], None
    for i, _ in enumerate(ys):
        # the true pair drifts slowly together; a decoy runs away 9 px (3 mm) per level from the artery
        v = [(150 + i, 150 + i, 3.5), (150 + i, 176 + i, 4.5)]
        if i:
            v.append((150 + 9 * i, 150 - 9 * i, 3.5))
        im = _section(vessels=v, muscle=False)
        ims.append(im)
        if i == 0:
            first = im
    crops = _crops(tmp_path, ys, ims)
    dark = first[..., 0] < 60
    lab, _ = __import__("scipy.ndimage", fromlist=["x"]).label(dark)
    a0 = lab == lab[150, 150]; v0 = lab == lab[150, 176]
    out = ft.walk_pair(crops, ys, 0, a0, v0)
    art = [r for r in out["artery"][0] if not r["gap"]]
    assert len(art) == len(ys)
    assert abs(art[-1]["x"] - art[0]["x"]) < 4.0                  # stayed with the vein, not with the decoy
    assert len([r for r in out["vein"][0] if not r["gap"]]) == len(ys)


def test_walk_pair_refuses_a_mask_that_has_eaten_into_muscle(tmp_path):
    """A lumen wider than ~1.2x the textbook maximum is a leak, not a vessel: the level becomes a gap."""
    ys = [0, -1]
    im0 = _section(vessels=[(150, 140, 3.5), (150, 180, 4.5)], muscle=False)
    im1 = _section(vessels=[(150, 140, 3.5), (150, 186, 8.0)], muscle=False)   # vein blown up to 16 mm
    crops = _crops(tmp_path, ys, [im0, im1])
    ndi = __import__("scipy.ndimage", fromlist=["x"])
    lab, _ = ndi.label(im0[..., 0] < 60)
    out = ft.walk_pair(crops, ys, 0, lab == lab[150, 140], lab == lab[150, 180], pair_mm=25.0)
    assert out["vein"][0][-1]["gap"] or out["vein"][0][-1]["y"] == 0
    assert [r["y"] for r in out["artery"][0] if not r["gap"]] == ys


def test_clean_rows_drops_ragged_and_oversized_levels():
    rows = [{"y": 0, "gap": False, "x": 1, "z": 1, "diam_mm": 7.0, "solidity": 0.95},
            {"y": -1, "gap": False, "x": 1, "z": 1, "diam_mm": 7.0, "solidity": 0.70},   # ragged
            {"y": -2, "gap": False, "x": 1, "z": 1, "diam_mm": 16.0, "solidity": 0.95},  # too wide
            {"y": -3, "gap": False, "x": 1, "z": 1, "diam_mm": 6.0, "solidity": 0.90},
            {"y": -4, "gap": False, "x": 1, "z": 1, "diam_mm": 2.0, "solidity": 0.99}]   # too thin, trailing
    out, dropped = ft.clean_rows(rows, "artery")
    assert dropped == 3
    assert [r["y"] for r in out if not r["gap"]] == [0, -3]
    assert out[-1]["y"] == -3                                     # trailing gaps trimmed
