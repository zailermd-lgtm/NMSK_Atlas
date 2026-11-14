"""Q185k relabel (two bodies under one TS label -> L1 + L1B) and Q185a FOV planes."""
import numpy as np

from scripts.vhf_vertebra_relabel_q185k import L1, L1B, L2, T12, split_merged
from scripts.placement_sweep_q185 import fov_cut


def _vol():
    v = np.zeros((120, 120, 140), np.uint8)
    v[45:75, 45:75, 100:125] = T12            # z = slices (affine identity: z up)
    v[45:75, 45:75, 70:95] = L1               # upper body under T12
    v[45:75, 45:75, 40:65] = L1               # lower body, same label, a 5-slice disc gap
    v[45:75, 45:75, 10:35] = L2
    v[50:55, 50:55, 65:68] = L2               # L2 fragment touching only the lower L1 body
    v[50:54, 50:54, 95:97] = T12              # T12 fragment touching only the upper one
    v[110:115, 110:115, 12:15] = L2           # stray far off the column
    return v


def test_split_and_fragments():
    v = _vol(); log = split_merged(v, np.eye(4))
    assert (v[60, 60, 80] == L1) and (v[60, 60, 50] == L1B)
    assert (v[52, 52, 66] == L1B) and (v[52, 52, 96] == L1)
    assert v[112, 112, 13] == 0 and v[60, 60, 20] == L2 and v[60, 60, 110] == T12
    assert log["L1_upper_voxels"] == log["L1B_lower_voxels"] == 30 * 30 * 25


def test_fov_cut_planes():
    sk = np.array([[-233.4, 0, 0], [246.6, 0, 0], [0, 10, 5]])
    assert fov_cut(sk) == (-232.4, 245.6)
