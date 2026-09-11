# TotalSegmentator task outputs used for geometry

Integer label volumes produced on 2026-09-10 by running TotalSegmentator
v2.18.0 (Apache-2.0) tasks on the raw CT of the named case from the
TotalSegmentator v2.0.1 release (Zenodo 10047292, CC BY 4.0). Label ids
follow `mappings/totalsegmentator_<task>_labels.json`. Runs were made with
`scripts/run_totalsegmentator_chunked.py` on CPU; `headneck_muscles_merged`
is the extended-crop neck run with the trunk run's trapezius unioned in.
`mappings/subjects/` holds the per-subject `propose`
files actually used by `convert`, including the hand-made decisions
(clipped femur stubs and s0913's C7 stub nulled; trapezius taken from the
neck volume only). The raw CTs are not stored: fetch by case id from the
Zenodo record.

## Visible Human male frozen CT (`vhm_*`, 2026-09-11)

`vhm_total`, `vhm_headneck_muscles`, `vhm_headneck_bones_vessels`,
`vhm_abdominal_muscles`, `vhm_craniofacial_structures`, `vhm_head_muscles`,
`vhm_oculomotor_muscles`: the same TotalSegmentator v2.18.0 tasks run on
the NLM Visible Human Project male frozen CT (public domain), IDC series
`5d409385-d3e7-48a9-ae50-150b39e834da` stacked by
`scripts/stack_dicom_series.py` (torso grid 0.9375 x 0.9375 x 1 mm; the
head tasks on the 0.527 mm head-and-neck grid). `vhm_legs_total` is the
`total` task on the pelvis slab (slices 540-808) of series
`145c2668-7d2f-4d7e-b1c7-2cf2462bef60`, used only for the femoral-head
origin. `vhm_arm_bones_labels` is not a TotalSegmentator output: it is the
upper-limb bone volume from `scripts/segment_arm_bones_vhm.py` (key
`mappings/vhm_arm_labels.json`). `vhm_abdominal_muscles` is kept for the
record and NOT shipped: on the frozen cadaver that model finds fragments
(see PROJECT_STATE, 2026-09-10 night). The raw DICOMs are not stored:
`scripts/download_idc_series.py <uuid>` fetches them.
