"""Q185f2: her TA = muscle-density band deep to her IO label (synthetic ring wall, no CT needed); Q185c2 disc entities."""
import json
from pathlib import Path

import numpy as np

from scripts.transversus_from_ct_q185f2 import deep_band, ring_centres

REPO = Path(__file__).resolve().parents[1]


def test_deep_band_takes_the_free_muscle_layer_inside_the_ring_only():
    n, nz = 120, 6
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    r = np.hypot(x - 60, y - 60)
    io = np.repeat(((r >= 40) & (r < 45))[..., None], nz, 2)                # IO ring, 5 voxels
    muscle = np.repeat(((r >= 36) & (r < 50))[..., None], nz, 2)            # muscle density 4 vox deep + 5 superficial
    occ = io.copy(); occ[:, :, :] |= np.repeat((r < 20)[..., None], nz, 2)  # an "organ" in the middle
    c = ring_centres(io)
    assert np.allclose(c, 60, atol=0.5)
    ta = deep_band(io, occ, muscle, c, (1.0, 1.0, 1.0), shell=6.0, seed=1.5)
    rr = np.repeat(r[..., None], nz, 2)
    assert ta.any() and not (ta & io).any() and not (ta & occ).any()
    assert rr[ta].min() >= 36 and rr[ta].max() < 40                          # deep side only, never the superficial muscle


def test_deep_band_drops_muscle_not_reaching_the_seed_layer():
    n, nz = 120, 6
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    r = np.hypot(x - 60, y - 60)
    io = np.repeat(((r >= 40) & (r < 45))[..., None], nz, 2)
    muscle = np.repeat(((r >= 34) & (r < 37))[..., None], nz, 2)            # separated from IO by a 3 mm fat gap
    ta = deep_band(io, io.copy(), muscle, ring_centres(io), (1.0, 1.0, 1.0), shell=6.0, seed=1.5)
    assert not ta.any()


def test_q185c2_disc_entities_exist_in_order():
    ids = [e["id"] for e in json.loads((REPO / "data" / "cartilage" / "intervertebral_disc_levels.json").read_text())]
    for a, after in (("intervertebral_disc_c7_t1", "intervertebral_disc_c6_c7"),
                     ("intervertebral_disc_t12_l1", "intervertebral_disc_t11_t12"),
                     ("intervertebral_disc_l5_s1", "intervertebral_disc_l4_l5")):
        assert ids.index(a) == ids.index(after) + 1
