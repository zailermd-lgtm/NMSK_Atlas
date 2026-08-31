"""Tests for the labelled-volume (CT/MRI) ingest.

No scan is vendored, so these build small synthetic NIfTI label maps whose
right answer is known by construction: a sphere of a stated radius at a
stated centre, and a shape whose left-right placement is known.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

nib = pytest.importorskip("nibabel")
pytest.importorskip("skimage")

from engine import volume_ingest as vol  # noqa: E402


def _write_nifti(path, volume, spacing=(1.0, 1.0, 1.0), flip_x=False):
    """A NIfTI whose affine is plain RAS at the given spacing.

    flip_x writes the volume with a POSITIVE-determinant affine, which is how
    a mirrored scan arrives.
    """
    affine = np.diag([spacing[0], spacing[1], spacing[2], 1.0])
    affine[0, 0] = -spacing[0] if flip_x else spacing[0]
    img = nib.Nifti1Image(volume.astype(np.int16), affine)
    nib.save(img, str(path))
    return affine


def _ball(volume, centre, radius, label):
    g = np.stack(np.meshgrid(*[np.arange(s) for s in volume.shape],
                             indexing="ij"), axis=-1)
    volume[np.linalg.norm(g - np.array(centre), axis=-1) <= radius] = label
    return volume


def test_label_surface_is_closed_even_at_the_volume_edge(tmp_path):
    """A structure touching the edge of the scan comes back as an open sheet
    without padding, and every inside/outside test downstream inverts on an
    open mesh."""
    volume = np.zeros((30, 30, 30), np.int16)
    volume[:12, :12, :12] = 7          # jammed into the corner
    verts, faces = vol.label_surface(volume, 7)
    assert len(verts) and len(faces)
    # Closed means every edge is shared by exactly two triangles.
    edges = {}
    for tri in faces:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges[(min(a, b), max(a, b))] = edges.get((min(a, b), max(a, b)), 0) + 1
    assert set(edges.values()) == {2}, "surface is not closed"


def test_voxels_to_atlas_puts_superior_on_y_and_anterior_on_z(tmp_path):
    """NIfTI world is RAS -- +y anterior, +z superior. The atlas is
    +Y superior, +Z anterior. Getting that swap wrong lays the body on its
    face and nothing downstream would notice."""
    affine = np.eye(4)
    pts = np.array([[1.0, 2.0, 3.0]])          # right 1, anterior 2, superior 3
    out = vol.voxels_to_atlas(pts, affine)
    np.testing.assert_allclose(out, [[1.0, 3.0, 2.0]])


def test_a_mirrored_scan_is_detected_and_not_corrected():
    """Mirroring a patient's scan without saying so is how the wrong knee
    gets operated on."""
    good = np.diag([1.0, 1.0, 1.0, 1.0])
    good[0, 0] = -1.0                      # LAS: a normal radiological affine
    assert vol.is_right_handed(good)       # flagged
    plain_ras = np.diag([1.0, 1.0, 1.0, 1.0])
    assert not vol.is_right_handed(plain_ras)


def _femur(volume, head_vox, label, lateral_sign):
    """A femur with a head AND a greater trochanter sitting higher than it.

    The trochanter is the point of the fixture: on many people it is the more
    superior of the two, so a rule that took the superior fraction of the
    bone would fit the trochanter and call it the hip joint centre.
    """
    hx, hy, hz = head_vox
    _ball(volume, head_vox, 12, label)                       # head, r=24 mm
    _ball(volume, (hx + 15 * lateral_sign, hy + 10, hz), 10, label)  # trochanter
    x0 = hx + 8 * lateral_sign
    lo, hi = sorted((x0 - 4, x0 + 4))
    volume[lo:hi, hy - 75:hy, hz - 4:hz + 4] = label         # shaft
    return volume


def test_femoral_head_is_fitted_to_its_known_radius_and_centre():
    """The head is isolated from a whole-femur label by DIRECTION, not
    height: the greater trochanter is the more superior of the two on many
    people, so a superior-fraction rule fits the trochanter instead."""
    volume = np.zeros((120, 120, 120), np.int16)
    _femur(volume, (40, 95, 60), 3, lateral_sign=-1)   # a LEFT femur (low x)
    verts, _faces = vol.label_surface(volume, 3)
    # 2 mm voxels, so a 12-voxel ball is a 24 mm femoral head -- the size the
    # plausibility gate in hip_joint_origin() is written for.
    pts = vol.voxels_to_atlas(verts, np.diag([2.0, 2.0, 2.0, 1.0]))
    centre, radius, rms = vol.femoral_head_centre(pts, "left")
    assert 21.0 <= radius <= 27.0, radius
    assert rms < 2.0, rms
    # voxel (40,95,60) at 2 mm -> RAS (80,190,120) -> atlas (80,120,190)
    np.testing.assert_allclose(centre, [80.0, 120.0, 190.0], atol=5.0)


def test_hip_origin_needs_both_sides():
    """The atlas origin is the MIDPOINT of the two hip joint centres, so one
    side alone cannot give it, and returning a single centre as if it were
    the midpoint would shift the whole atlas by half a pelvis."""
    volume = np.zeros((120, 120, 120), np.int16)
    _femur(volume, (40, 95, 60), 1, lateral_sign=-1)
    verts, _ = vol.label_surface(volume, 1)
    pts = vol.voxels_to_atlas(verts, np.diag([2.0, 2.0, 2.0, 1.0]))
    report = vol.hip_joint_origin({"femur_left": pts})
    assert report["sides"]["left"]["plausible"], report
    assert report["origin_mm"] is None
    assert "midpoint" in report["from"].lower()


def test_label_map_covers_every_id_it_claims():
    names = vol.load_label_names("totalsegmentator")
    assert len(names) == 117
    assert names[73] == "clavicula_left" and names[74] == "clavicula_right"
    assert names[69] == "humerus_left" and names[43] == "vertebrae_T1"


def test_a_probability_volume_is_refused(tmp_path):
    """Rounding a probability map would invent structures that are not there."""
    path = tmp_path / "probs.nii.gz"
    _write_nifti(path, np.zeros((4, 4, 4)))
    img = nib.Nifti1Image(np.full((4, 4, 4), 0.37, dtype=np.float32), np.eye(4))
    nib.save(img, str(path))
    with pytest.raises(ValueError, match="not a label map"):
        vol.load_labels(path)


def test_inspect_runs_end_to_end_and_recovers_the_origin(tmp_path):
    """The whole point of inspect: read a real file, say what is in it, and
    hand back an --origin the operator can paste into convert."""
    volume = np.zeros((140, 140, 140), np.int16)
    # left femur (label 75) at low x, right femur (76) at high x
    _femur(volume, (45, 100, 70), 75, lateral_sign=-1)
    _femur(volume, (95, 100, 70), 76, lateral_sign=+1)
    path = tmp_path / "seg.nii.gz"
    _write_nifti(path, volume, spacing=(2.0, 2.0, 2.0))

    out = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "ingest_volume_geometry.py"),
         "inspect", str(path), "--labels", "totalsegmentator"],
        capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr
    assert "femur_left" in out.stdout and "femur_right" in out.stdout
    assert "--origin" in out.stdout, out.stdout
    # midpoint of the two heads: voxel x 45 and 95, at 2 mm -> atlas x 140
    line = next(l for l in out.stdout.splitlines() if "--origin" in l)
    x = float(line.split("'")[1].split(",")[0])
    assert abs(x - 140.0) < 6.0, line


def test_merging_per_structure_masks_produces_the_ingest_s_label_map(tmp_path):
    """The released dataset gives one BINARY mask per structure, not the
    single label volume the ingest reads."""
    seg = tmp_path / "s0001" / "segmentations"
    seg.mkdir(parents=True)
    shape = (20, 20, 20)
    affine = np.diag([1.5, 1.5, 1.5, 1.0])
    for name, box in (("humerus_left", (slice(2, 6),) * 3),
                      ("clavicula_right", (slice(10, 14),) * 3),
                      ("liver", (slice(16, 19),) * 3)):
        m = np.zeros(shape, np.uint8)
        m[box] = 1
        nib.save(nib.Nifti1Image(m, affine), str(seg / f"{name}.nii.gz"))

    out = tmp_path / "merged.nii.gz"
    r = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "scripts" / "merge_totalsegmentator_masks.py"),
         str(tmp_path / "s0001"), "-o", str(out)],
        capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr

    volume, got_affine, _codes = vol.load_labels(out)
    names = vol.load_label_names("totalsegmentator")
    present = {names[i] for i in set(np.unique(volume).tolist()) - {0}}
    assert present == {"humerus_left", "clavicula_right"}, present
    assert "liver" in r.stdout and "not musculoskeletal" in r.stdout
    np.testing.assert_allclose(got_affine, affine)
    # the ids must be the ones the ingest will look up, not 1..n
    assert volume[3, 3, 3] == 69 and volume[11, 11, 11] == 74


def test_merging_refuses_masks_from_a_different_scan(tmp_path):
    """Two subjects' masks share no grid, and merging them would produce a
    body assembled from two people without saying so."""
    seg = tmp_path / "s0002" / "segmentations"
    seg.mkdir(parents=True)
    a = np.zeros((20, 20, 20), np.uint8); a[2:6, 2:6, 2:6] = 1
    b = np.zeros((24, 20, 20), np.uint8); b[2:6, 2:6, 2:6] = 1
    nib.save(nib.Nifti1Image(a, np.eye(4)), str(seg / "humerus_left.nii.gz"))
    nib.save(nib.Nifti1Image(b, np.eye(4)), str(seg / "scapula_left.nii.gz"))
    r = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "scripts" / "merge_totalsegmentator_masks.py"),
         str(tmp_path / "s0002"), "-o", str(tmp_path / "x.nii.gz")],
        capture_output=True, text=True, timeout=600)
    assert r.returncode != 0
    assert "different scans" in (r.stdout + r.stderr)


def test_overlapping_masks_are_counted_not_hidden(tmp_path):
    seg = tmp_path / "s0003" / "segmentations"
    seg.mkdir(parents=True)
    a = np.zeros((20, 20, 20), np.uint8); a[2:8, 2:8, 2:8] = 1
    b = np.zeros((20, 20, 20), np.uint8); b[6:12, 2:8, 2:8] = 1   # overlaps
    nib.save(nib.Nifti1Image(a, np.eye(4)), str(seg / "humerus_left.nii.gz"))
    nib.save(nib.Nifti1Image(b, np.eye(4)), str(seg / "scapula_left.nii.gz"))
    r = subprocess.run(
        [sys.executable,
         str(REPO_ROOT / "scripts" / "merge_totalsegmentator_masks.py"),
         str(tmp_path / "s0003"), "-o", str(tmp_path / "y.nii.gz")],
        capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr
    assert "claimed by more than" in r.stdout
    assert "That is a lot" in r.stdout
