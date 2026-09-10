# TotalSegmentator task outputs used for geometry

Integer label volumes produced on 2026-09-10 by running TotalSegmentator
v2.18.0 (Apache-2.0) tasks on the raw CT of the named case from the
TotalSegmentator v2.0.1 release (Zenodo 10047292, CC BY 4.0). Label ids
follow `mappings/totalsegmentator_<task>_labels.json`. Runs were made with
`scripts/run_totalsegmentator_chunked.py` on CPU; `headneck_muscles_merged`
is the extended-crop neck run with the trunk run's trapezius unioned in.
The subject_mappings/ folder next to this holds the per-subject `propose`
files actually used by `convert`, including the hand-made decisions
(clipped femur stubs and s0913's C7 stub nulled; trapezius taken from the
neck volume only). The raw CTs are not stored: fetch by case id from the
Zenodo record.
