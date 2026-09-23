"""Q150/Q150b: refine Q147's per-bone Z-Anatomy limb transfer to each specimen's own segmented
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
    process_volume, partition_region, neighbour_region_and_candidates, validate_holdout,
    voxel_to_atlas, atlas_to_voxel,
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
    label 4 (voxel x 26-29): GROUND TRUTH for muscleE (atlas_id set) -- held out in one test;
                             touches label 3 (x 25/26 boundary) within NEIGHBOUR_DILATE_MM
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


def fake_target(vol_extent_ids):
    """A minimal `target` dict (as bundle_io.meshes_by_id would return) with a REAL mesh for
    each id, used only so score_holdout() finds a "real_subject" to compare against."""
    out = {}
    for aid, (lo, hi) in vol_extent_ids.items():
        v, f = box_mesh(lo, hi)
        out[aid] = {"v": v, "f": f, "subject": "ct_test_real", "cat": "muscle"}
    return out


def test_compartment_splits_by_nearest_transferred_seed(tmp_path):
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {
        "muscleA_r": box_mesh((-1, 5, 5), (2, 25, 25)),     # near x=0-6 half of label 1
        "muscleB_r": box_mesh((12, 5, 5), (16, 25, 25)),    # near x=8-14 half of label 1
    }
    assign, notes, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer)
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
    assign, notes, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer)
    assert "muscleC_r" not in assign or not assign["muscleC_r"].any()


def test_no_atlas_entity_single_candidate_gets_the_whole_label(tmp_path):
    """A genuine compartment (no_atlas_entity: the rule truly could not split further) with only
    one candidate IS handed the whole blob, regardless of its transferred seed's own position --
    the reviewer's own considered judgement, not read back out of held-out ground truth."""
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {"muscleD_r": box_mesh((100, 100, 100), (101, 101, 101))}  # far away, doesn't matter here
    assign, notes, *_ = process_volume(nii_path, labels_path, mapping_path, ORIGIN, xfer)
    lab = nib.load(str(nii_path)).get_fdata().astype(np.int32)
    assert int(assign["muscleD_r"].sum()) == int((lab == 3).sum())


def test_neighbour_region_is_never_just_the_held_out_labels_own_footprint(tmp_path):
    """Q150b regression: the region a held-out id competes within must be a STRICT superset of
    its own true label (at least one real neighbour's own voxels folded in too), and its own
    candidate list must name more than just itself -- otherwise partition_region degenerates
    back into "search for muscleE only inside muscleE's own true footprint", the exact leak a
    lead review caught in the first Q150 cut (it scored a fraudulent ~1mm median by doing this)."""
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    labelvol = nib.load(str(nii_path)).get_fdata().astype(np.int32)
    sampling = (1.0, 1.0, 1.0)
    entries = json.loads(mapping_path.read_text())["entries"]
    lab_h = 4  # muscleE_r's own ground-truth label
    region, cands, touching = neighbour_region_and_candidates(labelvol, entries, lab_h, sampling)
    own_footprint = int((labelvol == lab_h).sum())
    assert touching, "label 4 (x 26-29) sits within 5mm of label 3 (x 21-24) -- must be found"
    assert int(region.sum()) > own_footprint, "the competitive region must include more than muscleE's own true voxels"
    assert cands != ["muscleE_r"], "the candidate list must include at least one real neighbour, not just itself"
    assert "muscleE_r" in cands


def test_holdout_never_recovers_via_its_own_isolated_truth(tmp_path):
    """End-to-end: even when muscleE_r's own Q147 transferred seed is placed FAR from its true
    location (and also far from its neighbour's), the neighbor-mode holdout validator must not
    silently hand it the truth back -- it can only claim what nearest-seed competition (against
    a real neighbour candidate) inside the merged region actually supports."""
    nii_path, labels_path, mapping_path, affine = make_volume(tmp_path)
    xfer = {
        "muscleE_r": box_mesh((100, 100, 100), (101, 101, 101)),   # far from everything
        "muscleD_r": box_mesh((22, 5, 5), (25, 25, 25)),            # a real, present neighbour seed
    }
    target = fake_target({"muscleE_r": ((26, 5, 5), (30, 25, 25))})
    rows, notes = validate_holdout(nii_path, labels_path, mapping_path, ORIGIN, xfer, target,
                                    ["muscleE_r"], mode="neighbor")
    assert len(rows) == 1
    row = rows[0]
    # muscleE's own seed is nowhere near either label 3 or label 4 -- it must NOT win a claim
    # equal to (or suspiciously close to) its own full true volume via some back-door free pass.
    if "centroid_dist_mm" in row:
        assert row["centroid_dist_mm"] > 0.5, f"suspiciously perfect recovery with a far-away seed: {row}"


def test_voxel_atlas_roundtrip():
    affine = np.array([[0.5, 0, 0, 10], [0, 0.5, 0, -20], [0, 0, 1.0, 5], [0, 0, 0, 1]])
    origin = np.array([3.0, -400.0, 7.0])
    idx = np.array([[1.0, 2.0, 3.0], [10.0, 0.0, -4.0]])
    atlas = voxel_to_atlas(idx, affine, origin)
    back = atlas_to_voxel(atlas, affine, origin)
    assert np.allclose(idx, back, atol=1e-6)
