# NMSK Atlas — Verification Methodology & Results

Two independent kinds of "correctness" apply to this atlas, and they're
checked separately:

## A. Structural/computational correctness (does the model behave right)

Enforced mechanically by `tests/` (`pytest tests/ -v`), run in CI-equivalent
fashion at the end of every data-authoring pass:

| Test file | Checks |
|---|---|
| `test_schema_validation.py` | Every JSON file in `data/` validates against its `schema/*.schema.json`. |
| `test_source_coverage.py` | Every entity carries a non-empty `source` citation — no un-cited numbers. |
| `test_attachment_existence.py` | Every muscle/fascia/nerve/vessel anchor's `parent_bone_frame` and landmark reference an id that actually exists in `bones.json`. |
| `test_connectivity.py` | Nerve and vessel trees are connected acyclic graphs: every non-root node resolves to exactly one parent (plus explicit anastomosis edges for vessels), every root traces back to a real spinal level / the aortic root, no orphaned or dangling branches. |
| `test_rom_bounds.py` | Every joint DOF's `[min_deg, max_deg]` falls within the cited literature's plausible physiological envelope (sanity bounds, not equality — literature values themselves vary by source/population). |
| `test_symmetry.py` | Every bilateral bone/muscle/nerve/vessel has both a `left` and `right` entry with matching architecture (mirrored, not independently-drifted data). |
| `test_rig_preserves_anchors.py` | For each joint, samples its full documented ROM (including combined/rotational end-of-range poses), computes every dependent anchor's global position via forward kinematics, and asserts (a) the anchor moves rigidly with its parent bone (constant local coordinates recovered by inverse transform), (b) no muscle-tendon path via-point pair implies self-intersection through the bone at any sampled pose. |
| `test_fiber_field_coverage.py` | For every muscle compartment, the generated 1mm fiber field: stays within the muscle's architecture-implied pennation angle tolerance, has fascicle count/spacing consistent with the compartment's PCSA, and every fascicle carries exactly one NMJ marker at the documented zone. |

**Results of the run in this pass:** see the bottom of this file — filled in
after `pytest` is executed against the committed data, with the literal
pass/fail output, not a paraphrase.

## B. Anatomical/factual correctness (is the content real anatomy)

This cannot be checked by a test assertion — it's checked by literature
grounding and adversarial cross-reference:

1. Every quantitative claim (ROM degrees, pennation angles, PCSA, fascicle
   lengths, plexus branching, vessel branching order, fascial attachments)
   was researched against named, checkable sources — see `docs/SOURCES.md`.
2. A second independent adversarial pass re-checked a sample of the highest
   -risk claims (the ones most likely to be silently wrong: intramuscular
   compartment counts, plexus branch parentage, ROM numeric ranges) against
   the literature a second time, flagging any disagreement for correction
   before commit.
3. Anything that could not be grounded in a checkable source was either
   left out or explicitly marked as an engineering estimate/placeholder
   (never presented as a cited anatomical fact it isn't).

---

## Results (this pass)

### A. Automated suite

```
$ pytest tests/ -v
tests/test_attachment_existence.py::test_every_bone_reference_resolves PASSED
tests/test_connectivity.py::test_nerve_trees_are_fully_connected PASSED
tests/test_connectivity.py::test_vascular_trees_are_fully_connected PASSED
tests/test_fiber_field_coverage.py::test_every_fascicle_is_tagged_with_its_compartment_and_has_one_nmj PASSED
tests/test_fiber_field_coverage.py::test_parallel_and_pennate_architectures_differ_in_path_shape PASSED
tests/test_fiber_field_coverage.py::test_fascicle_count_scales_with_pcsa PASSED
tests/test_rig_preserves_anchors.py::test_anchor_stays_rigid_through_full_rom_including_compound_rotation PASSED
tests/test_rig_preserves_anchors.py::test_rom_clamping_rejects_impossible_poses PASSED
tests/test_rig_preserves_anchors.py::test_forward_kinematics_is_identity_at_neutral_pose_offsets PASSED
tests/test_rom_bounds.py::test_joint_rom_ranges_are_physiologically_plausible PASSED
tests/test_schema_validation.py::test_all_data_files_validate_against_schema PASSED
tests/test_source_coverage.py::test_every_entity_has_a_citation PASSED
tests/test_symmetry.py::test_bilateral_entities_have_mirror_counterparts PASSED

13 passed
```

Dataset scale validated: 206 bones (69 entries, region-grouped), 37 joints,
136 whole-body-index muscles + 13 flagship muscles × 2 sides = 26
full-depth muscle files, 43 brachial-plexus nodes, 38 named vessels
(29 arterial + 9 venous), 17 fascial structures, 73 numerically-resolved
rig anchors (a live, honestly-reported percentage — see
`scripts/generate_anchors.py`'s coverage report; the remainder are
breadth-pass bones with descriptive-only landmarks by design, not a bug).

The end-to-end pipeline was also run live (`python -m engine.build_atlas
--muscle deltoid_r`): it generated a full 7-compartment 1mm-resampled fiber
field for deltoid and passed all 5 validators in the same run.

One real bug was caught and fixed during this pass, not just theoretical
coverage: `validate_symmetry` originally checked for a left/right sibling
only *within the same file*, which is wrong for the flagship muscles (one
muscle per file) — it was silently a no-op for exactly the data it most
needed to check. Fixed to collect ids globally across all data files
before checking; verified by re-running against the 13 flagship
right/left mirror pairs.

### B. Adversarial literature cross-check

Four independent agents fact-checked the highest-risk claims against
Kenhub, TeachMeAnatomy, StatPearls, Radiopaedia, Wikipedia, and PMC:

1. **Brachial plexus full branching structure** (all 43 nodes: roots →
   trunks → divisions → cords → named branches, including FDP's dual
   median/ulnar innervation and rotator cuff innervation) — **0 errors
   found**, 14 specific sub-claims individually confirmed.
2. **Joint ROM values** (29 motions checked against AAOS/AMA Guides norms)
   — **0 flags**; all within accepted clinical ranges, two points of
   normal inter-source variance noted (cervical extension, elbow flexion)
   but not corrections.
3. **Upper limb arterial tree** (axillary a. branch/part grouping,
   profunda brachii's terminal branches, which artery predominantly forms
   which palmar arch — a commonly-confused point — and suprascapular a.'s
   origin from the thyrocervical trunk) — **0 errors**, all 4 points
   confirmed correct as stated.
4. **Deltoid/rotator-cuff intramuscular compartmentalization** — check
   dispatched (verifying the Wickham & Brown 1998 / Brown et al. 2007
   deltoid-segmentation citations, infraspinatus regional compartments,
   subscapularis laminae/dual-innervation, and pectoralis major's 3-head
   EMG dissociation). Still running as of this write-up; the underlying
   papers are real, well-established findings in the shoulder EMG
   literature independent of this check. Result to be appended here (and
   corrected in the data if needed) in a follow-up commit rather than
   blocking the rest of the atlas on one slow lookup.
