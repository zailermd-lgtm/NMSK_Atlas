# NMSK Atlas — Data Model Reference

Canonical definitions live in `schema/*.schema.json` (JSON Schema draft-07,
validated by `tests/test_schema_validation.py`). This is a human-readable
walkthrough with a worked example per entity.

## File layout of `data/`

```
data/
  skeleton/
    bones.json            # all 206 bones (schema/bone.schema.json)
    joints.json            # joint hierarchy + ROM (schema/joint.schema.json)
  muscles/
    muscle_index.json      # whole-body muscle list (name/O/I/nerve/action) — breadth
    upper_limb/*.json       # flagship depth: full functional_compartments per muscle
  nerves/
    spinal_and_cranial_nerve_roots.json
    brachial_plexus.json
    lumbosacral_plexus.json
  vascular/
    upper_limb_arterial.json
    upper_limb_venous.json
    lower_limb_arterial.json
    lower_limb_venous.json
  fascia/
    upper_limb_fascia.json
    lower_limb_fascia.json
  rig/
    skeleton_hierarchy.json  # kinematic parent/child + root
    anchors.json              # generated: every RigAnchor across all above data
```

## Naming note: nerve/vessel trees are side-generic

`data/nerves/brachial_plexus.json` and `data/vascular/upper_limb_*.json`
model *one* plexus/tree (e.g. `median_n`, `axillary_n`), applicable to
either side by the same bilateral-symmetry convention used everywhere else
in the atlas — they are not duplicated as `_r`/`_l`. A muscle's top-level
`innervation.nerve` field is a free-text descriptive summary (e.g.
`"median_n_r"`, or a compound string like
`"median_n_r_anterior_interosseous_branch_and_ulnar_n_r"` for a
dual-innervated muscle) and is not schema-constrained to literally equal a
`nerve_branch` id — the precise, individually-verifiable link is each
`functional_compartments[i].innervation_branch` free-text field, cross-
checked against `data/nerves/brachial_plexus.json`'s actual branch nodes
during this pass's adversarial fact-check (see docs/VERIFICATION.md).

## Worked example: how one muscle becomes 1mm fiber geometry

`data/muscles/upper_limb/deltoid.json` (excerpt, illustrative):

```json
{
  "id": "deltoid_r",
  "name_ta": "Musculus deltoideus",
  "side": "right",
  "overall_architecture_type": "multipennate",
  "attachments": {
    "origin_bone": "clavicle_r", "origin_landmark": "lateral third, anterior border",
    "insertion_bone": "humerus_r", "insertion_landmark": "deltoid tuberosity"
  },
  "innervation": { "nerve": "axillary_n_r", "root_levels": "C5-C6" },
  "functional_compartments": [
    {
      "id": "deltoid_r_clavicular_anterior",
      "name": "Anterior (clavicular) fibers",
      "innervation_branch": "axillary n., anterior branch",
      "fiber_architecture": { "architecture_type": "parallel_strap", "pennation_deg": 0, ... },
      "neuromuscular_junction_zone": { "position_fraction_along_fascicle": 0.5 },
      "source": "..."
    },
    { "id": "deltoid_r_acromial_middle_1", "...": "multipennate, ~7 segments per Brown et al." }
  ]
}
```

`engine/build_atlas.py deltoid_r` then:

1. Loads `bone[origin_bone].local_frame`/`landmarks` and the same for
   `insertion_bone` → resolves the origin/insertion **anchors** to global
   coordinates at the current rig pose (`rig.py:forward_kinematics`).
2. For each `functional_compartments[i]`, calls
   `fiber_field.generate(architecture, seed_region, origin_anchor,
   insertion_anchor, resolution_mm=1.0)`, which:
   - seeds fascicle start points 1mm apart along the compartment's origin
     polygon,
   - for `parallel_strap`/`fusiform`: straight-line or gently-bowed
     centerlines to the matched insertion point;
   - for `unipennate`/`bipennate`/`multipennate`: routes fibers onto the
     internal aponeurosis surface at the documented pennation angle, then
     to the tendon, split per-compartment so e.g. deltoid's 7 documented
     segments come out as 7 distinct, correctly-angled fiber groups sharing
     one muscle belly;
   - places the NMJ marker at `position_fraction_along_fascicle` on every
     generated fascicle.
3. Tags every generated point/segment with `compartment_id`, so downstream
   consumers (animation, EMG-simulation, visualization) can select "just the
   posterior deltoid fibers" as a first-class query.

## Worked example: rig anchors survive rotation

`data/rig/anchors.json` never stores a global XYZ. An anchor like the
deltoid insertion is:

```json
{ "id": "anchor_deltoid_r_insertion", "anchor_type": "muscle_insertion",
  "owner_entity": "deltoid_r", "parent_bone_frame": "humerus_r",
  "local_position_mm": [12.4, -145.2, 8.1] }
```

At any glenohumeral pose, `rig.py:resolve_anchor("anchor_deltoid_r_insertion",
pose)` = `global_transform(humerus_r, pose) @ [12.4,-145.2,8.1,1]`. Rotating
the shoulder 90° abducted, or the full documented ROM including axial
rotation, moves the anchor exactly with the humerus — because it is
mathematically defined relative to the humerus, not fit to a snapshot.
`tests/test_rig_preserves_anchors.py` samples the joint's full ROM (from
`joints.json`, including combined-axis end-of-range poses) and asserts this
holds for every anchor.
