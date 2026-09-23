"""Q150: refine Q147's per-bone Z-Anatomy limb transfer to each specimen's own segmented
forearm/hand tissue -- scripts/transfer/refine_limb_transfer.py.

Synthetic geometry only (a tiny NIfTI label volume + box meshes under tmp_path), no
build/vh/ or data/ct_sources/ needed, so this stays fast and runs anywhere."""
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.transfer.refine_limb_transfer import (  # noqa: E402
    process_volume, voxel_to_atlas, atlas_to_voxel, MAX_MOVE_MM,
)

ORIGIN = np.zeros(3)  # identity origin: atlas (x,y,z) = RAS (x,z,y) exactly


def box_mesh(lo, hi):
    m = trimesh.creation.box(extents=np.array(hi) - np.array(lo))
    m.apply_translation((np.array(lo) + np.array(hi)) / 2)
    return m.vertices.astype(np.float64), m.faces.astype(np.int64)


def make_volume(tmp_path):
    """A 30x30x30, 1mm identity-affine label volume:
    label 1 (voxel x 0-14): a real compartment, candidates muscleA (x 0-6) / muscleB (x 8-14)
    label 2 (voxel x 16-19): a "review"-flagged single-candidate region (muscleC), its own
                             transferred seed placed FAR away (never reaches it)
    label 3 (voxel x 21-24): a "no_atlas_entity" single-candidate region (muscleD), same far seed
    label 4 (voxel x 26-29): GROUND TRUTH for muscleE (atlas_id set) -- held out in one test
    """
    lab = np.zeros((30, 30, 30), np.int32)
    lab[0:15, 5:25, 5:25] = 1
    lab[16:20, 5:25, 5:25] = 2
    lab[21:25, 5:25, 5:25] = 3
    lab[26:30, 5:25, 5:25] = 4
    affine = np.eye(4)
    nii_path = tmp_path / "vol.nii.gz"
    nib.save(nib.Nifti1Image(lab, affine), nii_path)

    labels_path = tmp_path / "labels.json"
    labels_path.write_text(json.dumps({"labels": {"1": "compA_B", "2": "compC", "3": "compD", "4": "muscleE"}}))

    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps({"entries": [
        {"label": 1, "source_structure": "compA_B", "atlas_id": None, "status": "no_atlas_entity",
         "candidates": ["muscleA_r", "muscleB_r"]},
        {"label": 2, "source_structure": "compC", "atlas_id": None, "status": "review",
         "candidates": ["muscleC_r"]},
        {"label": 3, "source_structure": "compD", "atlas_id": None, "status": "no_atlas_entity",
         "candidates": ["muscleD_r"]},
        {"label": 4, "source_structure": "muscleE", "atlas_id": "muscleE_r"},
    ]}))
    return nii_path, labels_path, mapping_path, affine


def test_compartment_splits_by_nearest_transferred_seed(tmp_path):
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {
        "muscleA_r": box_mesh((-1, 5, 5), (2, 25, 25)),     # near x=0-6 half of label 1
        "muscleB_r": box_mesh((12, 5, 5), (16, 25, 25)),    # near x=8-14 half of label 1
    }
    assign, notes, held, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer, set())
    a_idx = np.argwhere(assign["muscleA_r"])
    b_idx = np.argwhere(assign["muscleB_r"])
    assert a_idx[:, 0].max() < b_idx[:, 0].min(), "each candidate should win the half nearest its own seed"
    # the whole compartment's real tissue is claimed by ONE of the two, nothing left over
    lab = nib.load(str(nii_path)).get_fdata().astype(np.int32)
    assert len(a_idx) + len(b_idx) == int((lab == 1).sum())


def test_review_status_does_not_get_a_free_pass(tmp_path):
    """A single-candidate label under active review (a known rule-artifact rejection, e.g.
    male pronator_quadratus's own oversized label) must NOT be handed over just because it is
    the only name on the list -- only within reach of its own Q147 transferred seed."""
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {"muscleC_r": box_mesh((100, 100, 100), (101, 101, 101))}  # far away: never reaches label 2
    assign, notes, held, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer, set())
    assert "muscleC_r" not in assign or not assign["muscleC_r"].any()


def test_no_atlas_entity_single_candidate_gets_the_whole_label(tmp_path):
    """A genuine compartment (no_atlas_entity: the rule truly could not split further) with only
    one candidate IS handed the whole blob, regardless of its transferred seed's own position --
    the reviewer's own considered judgement, not read back out of held-out ground truth."""
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {"muscleD_r": box_mesh((100, 100, 100), (101, 101, 101))}  # far away, doesn't matter here
    assign, notes, held, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer, set())
    lab = nib.load(str(nii_path)).get_fdata().astype(np.int32)
    assert int(assign["muscleD_r"].sum()) == int((lab == 3).sum())


def test_holdout_never_uses_the_free_pass_shortcut(tmp_path):
    """The leave-one-out validation design: a held-out real muscle (its own single-candidate
    ground-truth label) must go through the SAME seed-constrained competition as any other open
    label -- never the unconditional hand-over -- or the 'test' just reads its own answer back."""
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {"muscleE_r": box_mesh((100, 100, 100), (101, 101, 101))}  # far from label 4's real footprint
    assign, notes, held, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer, {"muscleE_r"})
    lab = nib.load(str(nii_path)).get_fdata().astype(np.int32)
    assert int(held["muscleE_r"].sum()) == int((lab == 4).sum())  # the true footprint was recorded
    # a seed this far away recovers nothing -- proof the shortcut did not fire
    assert "muscleE_r" not in assign or not assign["muscleE_r"].any()


def test_voxel_atlas_roundtrip():
    affine = np.array([[0.5, 0, 0, 10], [0, 0.5, 0, -20], [0, 0, 1.0, 5], [0, 0, 0, 1]])
    origin = np.array([3.0, -400.0, 7.0])
    idx = np.array([[1.0, 2.0, 3.0], [10.0, 0.0, -4.0]])
    atlas = voxel_to_atlas(idx, affine, origin)
    back = atlas_to_voxel(atlas, affine, origin)
    assert np.allclose(idx, back, atol=1e-6)
