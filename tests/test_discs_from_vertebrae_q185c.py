"""Q185c: rule-based disc fill between two endplates (synthetic geometry, no CT needed)."""
import numpy as np

from scripts.discs_from_vertebrae_q185c import GRID, PAIRS, canal_anterior, fill_gap, frame, ref_check, run_len


def test_fill_gap_between_two_cylinders():
    n, nz = 80, 60
    x, y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    disk = (x - 40) ** 2 + (y - 40) ** 2 <= 30 ** 2                     # 30 mm diameter at 0.5 mm
    z = np.arange(nz)
    lo = disk[..., None] & (z < 20)[None, None, :]                       # lower body top at z index 19
    up = disk[..., None] & (z >= 30)[None, None, :]                      # upper body bottom at z index 30
    free = ~(lo | up)
    D, st = fill_gap(up, lo, free)
    assert not (D & (lo | up)).any()
    cols = D.sum(2)
    assert cols[40, 40] == 10 and abs(st["median_gap_mm"] - 11 * GRID) < 1e-6   # z 20..29 filled
    assert run_len(cols[40] > 0, 40) * GRID <= 30.0 + GRID and run_len(cols[40] > 0, 40) * GRID >= 27.0
    assert not D[:, :, :20].any() and not D[:, :, 30:].any()


def test_canal_and_frame_and_levels():
    # ring (posterior arch) behind a solid body: canal anterior border at e1 = 0
    pts = []
    for a in np.linspace(-25, 25, 101):
        for b in np.linspace(-20, 20, 81):
            r = np.hypot(a + 8, b)
            if (a > 0 and abs(b) < 18) or (a <= 0 and 8 <= r <= 13):
                pts.append((a, b, 0.0))
    a0, how = canal_anterior(np.array(pts), None)
    assert how == "foramen" and -1.5 <= a0 <= 1.5
    F = frame(np.array([0.0, 30.0, 5.0]), np.array([0.0, 0.0, 0.0]))
    assert np.allclose(F @ F.T, np.eye(3), atol=1e-9) and np.linalg.det(F) > 0 and F[0, 2] > 0.9
    assert PAIRS[0] == ("C2", "C3") and PAIRS[-1] == ("L5", "S1") and ("C1", "C2") not in PAIRS
    assert ref_check("L3", 45, 35, 10)["width"]["ok"] and not ref_check("L3", 80, 35, 10)["width"]["ok"]
