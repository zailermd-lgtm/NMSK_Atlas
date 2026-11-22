# Private licence -- owner's clinical layer

Everything under `clinical/` (data, scripts' outputs and tools) is the repository owner's
PRIVATE clinical layer: motor points, injection / needling targets and other clinical planning
material. It is NOT licensed under CC BY-SA and is not for redistribution.

These files only REFERENCE the anatomy model layer (structure ids and coordinates in the
viewers' frame); they do not contain its geometry. See PROJECT_STATE.md (licensing rule, Q141)
and docs/GEOMETRY_SOURCES.md for the layer split.

This includes the simulated-imaging add-ons (Q226 `imaging_tool.js`, `data/imaging_tissues.json`; Q228
`ultrasound_tool.js`, `data/ultrasound_tissues.json`): they are staged BESIDE a viewer page as separate
`clinical_*` files by `scripts/clinical/stage_clinical_files.py` and are never inlined in the public
templates. Their tissue tables are literature-derived teaching values (each row carries its verification
status) and the images they draw are simulations from meshes, not scans.
