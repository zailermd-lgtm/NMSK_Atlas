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

`vhm_hybrid_abdominal_muscles`: the same task on the HYBRID CT
(`scripts/cryo/hybrid_ct_from_cryo.py`: frozen CT with muscle/fat HU
restored from the registered cryosection photographs). Pectoralis major,
serratus anterior and latissimus dorsi ship from it; rectus abdominis,
the obliques and quadratus lumborum do not (see PROJECT_STATE
2026-09-11). `vhm_headneck_muscles_merged`: the neck run with the hybrid
run's T4-L4 trapezius unioned in.

## Visible Human female fresh-cadaver CT (`vhf_*`, 2026-09-11)

The same seven TotalSegmentator tasks on the NLM Visible Human female
"Normal" CT (IDC series `b9cf8e7a-2505-4137-9ae3-f8d0cf756c13`, vertex to
mid-thigh, stacked by `scripts/stack_dicom_series.py`; head tasks on the
0.488 mm head-and-neck grid). Unfrozen tissue: every task, including
`abdominal_muscles`, gives symmetric textbook-range volumes. Ingested as
`ct_vhf_*` with her own femoral-head origin and shipped as a SECOND viewer
bundle (`scripts/cryo/vhf_ingest.sh`).

## Visible Human female cryosection-derived volumes (`vhf_*_cryo`, 2026-09-12)

`vhf_lower_limb_bones` (2026-09-11) is from her femur-to-toes CT (`scripts/vhf_lower_limb_bones.py`, see
its report JSON). `vhf_deltoid_cryo`: the male's deltoid rule applied to her colour cryosections (IDC series
`56f8119f-5940-48c1-96ee-8d445dc0b5fd`, every 3rd slice at 1 mm, `scripts/cryo/stream_cryosections.py`),
registered to her CT by `scripts/cryo/vhf_register_cryo.py` + `vhf_resample_cryo.py` (piecewise in-plane,
linear z, +-9 mm) and cut by `scripts/cryo/vhf_deltoid_from_cryo.py` with her TotalSegmentator humerus and
scapula labels as anchors (key `mappings/vhf_deltoid_labels.json`). `vhf_rotator_cuff_cryo`: the male's scapular-surface rules
(`scripts/cryo/vhf_rotator_cuff_from_cryo.py`, key `mappings/vhf_rotator_cuff_labels.json`) on the same
registered photographs. `vhf_erector_columns`: the male's distance-from-midline rule on her model erector-spinae
and autochthon labels (`scripts/cryo/vhf_erector_columns.py`, key `mappings/vhf_erector_labels.json`), no
photographs involved. `vhf_arm_muscles_cryo`: the male's compartment rules around her humerus
(`scripts/cryo/vhf_arm_muscles_from_cryo.py`, key `mappings/vhf_arm_muscles_labels.json`). Her photographs are
classified with `scripts/cryo/cryo_classes_f.py` (female thresholds: her frozen muscle is darker and browner
than the male's). Rule-based; volumes in the report JSONs.
