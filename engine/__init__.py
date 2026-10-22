"""NMSK Atlas procedural engine.

Turns the parametric data model in `data/` (bones, joints, muscle
architecture, nerve/vessel trees, fascia, rig anchors) into concrete,
1mm-resolution geometry, and validates the whole model for structural and
anatomical self-consistency.

See docs/ARCHITECTURE.md for the design and docs/DATA_MODEL.md for a
worked example of the full pipeline for a single muscle.
"""

RESOLUTION_MM = 1.0
