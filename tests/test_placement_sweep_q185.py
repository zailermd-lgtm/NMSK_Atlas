"""Q185: placement sweep core lookup (scripts/placement_sweep_q185.py)."""
import numpy as np

from scripts.placement_sweep_q185 import FLAG, depth_map, flags_of, label_at, sample_depth
from scripts.ribs_from_ct_labels import to_vox
from engine.volume_ingest import voxels_to_atlas

# the TS torso grid: 0.9375 mm in-plane, x/y flipped (LPS-stored RAS), 1 mm slices
A = np.array([[-0.9375, 0, 0, 240.0], [0, -0.9375, 0, 240.0], [0, 0, 1.0, -863.0], [0, 0, 0, 1]])
O = np.array([-6.035, -895.476, 4.787])


def _cube():
    vol = np.zeros((60, 60, 60), np.uint8)
    vol[20:40, 20:40, 20:40] = 7          # 20 voxels: 18.75 x 18.75 x 20 mm
    return vol


def test_atlas_voxel_round_trip():
    iv = np.array([[10.0, 20.0, 30.0], [33.0, 5.0, 59.0]])
    p = voxels_to_atlas(iv, A) - O
    assert np.allclose(to_vox(p, A, O), iv, atol=1e-6)


def test_depth_lookup_centre_edge_outside_and_fov():
    vol = _cube(); sp = np.sqrt((A[:3, :3] ** 2).sum(0))
    dm = depth_map(vol == 7, sp)
    centre = voxels_to_atlas(np.array([[29.5, 29.5, 29.5]]), A) - O
    face = voxels_to_atlas(np.array([[20.0, 29.5, 29.5]]), A) - O        # outermost voxel centre in x
    out = voxels_to_atlas(np.array([[10.0, 29.5, 29.5]]), A) - O
    far = voxels_to_atlas(np.array([[200.0, 29.5, 29.5]]), A) - O       # outside the field of view
    d = sample_depth(dm, A, O, np.vstack([centre, face, out, far]), vol.shape)
    assert 8.5 <= d[0] <= 10.5                 # ~half the 18.75 mm side
    assert d[1] <= 0.6                         # surface voxel: ~0 after the half-voxel offset
    assert d[2] == 0.0 and np.isnan(d[3])
    assert label_at(vol, A, O, np.vstack([centre, out, far])).tolist() == [7, 0, 0]


def test_flag_rules():
    ok = {"outside_skin_frac": 0.0, "in_bone_gt1mm_frac": 0.0, "in_lung_gt1mm_frac": 0.0, "in_organ_gt1mm_frac": 0.0,
          "own_label": {"kind": "curated", "mesh_to_label_median_mm": 1.0}}
    assert flags_of(ok) == []
    assert flags_of({**ok, "outside_skin_frac": FLAG["outside_skin_frac"] + 0.001}) == ["outside_skin_frac"]
    assert flags_of({**ok, "in_bone_gt1mm_frac": None}) == []                          # bones / excluded ids
    assert flags_of({**ok, "own_label": {"kind": "curated", "mesh_to_label_median_mm": 6.0}}) == ["own_label_median_mm"]
    assert flags_of({**ok, "own_label": {"kind": "fragment", "mesh_to_label_median_mm": 30.0}}) == []
