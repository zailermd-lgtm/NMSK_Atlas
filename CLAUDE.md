# NMSK Atlas — Claude Code instructions

## What this is
A data model + procedural generation engine for a neuro-musculo-skeletal 3D
human atlas (mm-resolution): bones/joints, muscles (fascicle-level with
functional compartments), nerve/vascular trees, fascia, ligaments, tendons,
and a kinematic rig. Full design in `docs/ARCHITECTURE.md` — read it before
guessing at structure; don't re-derive it from the data files.

## Build & test
```
pip install -r requirements.txt
pytest tests/ -v                                            # full verification suite
python -m engine.build_atlas --muscle <id>                  # generate + validate one entity
python scripts/generate_anchors.py                          # rebuild data/rig/anchors.json
python scripts/mirror_side.py data/muscles/<region>/*_r.json # mirror right -> left
python scripts/audit_geometry_vs_atlas.py
python scripts/audit_landmarks_vs_geometry.py
```

## Hard rules (enforced by tests/validators — never bypass, never work around)
- All lengths in mm. `resolution_mm = 1.0` is the procedural sampling target.
- A `RigAnchor` lives **only** in its parent bone's local frame — never a
  pre-baked global coordinate. Global position is always derived via forward
  kinematics (`engine/rig.py`).
- Every quantitative or topological field needs a `source` citation
  (`schema/common.schema.json#citation`). A plausible-looking number with no
  citation is a defect, not a shortcut — `tests/test_source_coverage.py`
  enforces this mechanically. Never invent a citation or a number without one;
  if a source isn't available, say so instead of filling it in.
- No third-party mesh/voxel geometry goes in this repo — see
  `docs/GEOMETRY_SOURCES.md` before adding any geometry. Visible Human Project
  (public domain) is the intended substrate; the University of Denver
  lower-extremity segmentation (CC BY 4.0) is the first geometry layer;
  CC BY-SA sources (Z-Anatomy, BodyParts3D) are excluded as license-incompatible
  with this proprietary repo.
- A new or edited entity isn't "done" until: schema-valid, mirrored (if
  paired), and `pytest tests/ -v` passes — not just the file you touched.

## Where things live
- `schema/` — one JSON Schema per entity type
- `data/<region>/` — entity JSON authored against those schemas: muscles,
  nerves, vascular, skeleton, ligaments, tendons, cartilage, fascia, rig.
  Muscle regions: upper_limb, lower_limb, trunk, head_and_neck.
- `engine/` — `geometry.py`, `fiber_field.py` (procedural fascicle generator),
  `rig.py` (FK + anchor resolution), `nerve_tree.py`, `vascular_tree.py`,
  `validators.py` (the anatomical-consistency checker), `build_atlas.py` (CLI)
- `scripts/` — ingestion (`ingest_vh_geometry.py`, `vh_ingest.py`), audits
  (`audit_geometry_vs_atlas.py`, `audit_landmarks_vs_geometry.py`), export
  (`export_3d_scene.py`, `generate_point_cloud.py`), `mirror_side.py`
- `docs/` — ARCHITECTURE, DATA_MODEL, SOURCES, VERIFICATION, ROADMAP,
  GEOMETRY_SOURCES. Check the relevant one before asking the user or guessing.
- `mappings/du_vh_overrides.json`, `build/vh/` — geometry build artifacts

## Compact instructions
When compacting, keep: failing test names with their assertion messages, the
specific entity IDs (muscle/nerve/vessel) currently being worked on, and any
citation gaps found. Drop full JSON dumps of data files and full passing
pytest/audit output.
