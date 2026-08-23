# NMSK Atlas — Roadmap to full whole-body, 1mm-verified coverage

This repo delivers, in this pass: the full architecture, whole-body breadth
data (skeleton, joints, nerve roots, muscle index), and one fully-detailed,
fully-verified flagship region (upper limb, shoulder→hand — chosen because
it is the single region that exercises every requirement richly: complex
joints, pennate + parallel + multipennate muscles, documented intramuscular
compartments, a full plexus, full named arterial/venous trees, and a dense
fascial/retinacular/pulley system).

Extending to the rest of the body uses the **same schemas, same generator,
same validators** — it is bounded, well-scoped data-authoring work, staged
as follows:

## Stage 1 — Lower limb kinetic chain (pelvis → foot)
- Mirror the upper-limb methodology: hip/knee/ankle/foot joints + ROM,
  ~40 muscles with real architecture (Ward et al. 2009 is the standard
  cadaver source), lumbosacral plexus full tree (already researched in this
  pass — see `data/nerves/lumbosacral_plexus.json`), femoral/popliteal/
  tibial arterial+venous trees (already researched — see `data/vascular/
  lower_limb_*.json`), thigh/leg/foot fascial compartments (already
  researched — see `data/fascia/lower_limb_fascia.json`).
- Estimated effort: comparable to the upper limb pass already completed —
  1 focused research+authoring+verification cycle.

## Stage 2 — Trunk (spine, ribcage, abdominal & back wall, pelvic floor)
- Vertebral column segment-by-segment joint modeling (already have ISB/
  literature ROM per level from this pass), paraspinal muscles by layer
  (superficial/intermediate/deep per Gray's compartmentalization),
  intercostals, abdominal wall (rectus abdominis' documented tendinous
  intersections are themselves a textbook example of intramuscular
  compartmentalization), diaphragm, pelvic floor.
- Needs: thoracic/abdominal aortic branching tree, intercostal/lumbar
  spinal nerve segmental distribution (already have the root map),
  thoracolumbar fascia (a 3-layer structure — good stress-test for the
  fascia schema's `adjacent_fascia` continuity model).

## Stage 3 — Head & neck
- Cranial nerve courses through skull foramina (root map already
  researched), muscles of facial expression (architecturally unusual —
  skin-inserting, not bone-to-bone, which will require a small schema
  extension: `insertion_bone` → `insertion_dermis_region`), muscles of
  mastication, extraocular muscles, cervical plexus, carotid/vertebral
  arterial trees, cervical fascial layers.
- This stage is the most schema-novel (skin insertions, cranial foramina
  as via-points) — do it once cores 1–2 have validated the general
  approach.

## Stage 4 — Skin, viscera, capillary-bed aggregation
- Below the 1mm resolution target, individual capillaries are not
  individually meaningful entities — `schema/vessel_branch.schema.json`
  already handles this via `approx_diameter_mm` gating: vessels ≥1mm are
  modeled explicitly, sub-1mm beds are represented as aggregate supply
  regions on the organ/muscle entity they perfuse. Full organ-level detail
  (viscera parenchyma) is out of scope for a "neuro-musculo-skeletal" atlas
  as named and was not part of the requested emphasis; a thin visceral
  layer (organ bounding surfaces + their neurovascular pedicles only) could
  be added in this stage if needed.

## Stage 5 — True 1mm surface mesh geometry
- What's built in this pass generates 1mm-sampled **centerlines/point
  fields** (fiber tracts, nerve/vessel paths) — the geometrically and
  computationally hard, genuinely novel part for animation-safe rigging.
  Turning bones/muscle bellies into 1mm-resolution watertight **surface
  meshes** additionally requires either (a) a licensed segmented volumetric
  source — the NIH Visible Human Project (public domain, ~15GB) or AIST's
  BodyParts3D/Anatomography (CC BY-SA, https://lifesciencedb.jp/bp3d/) are
  the legitimate options — imported and re-topologized onto this rig's
  anchor set, or (b) procedural lofting from the `landmarks[]`/cross-section
  data already in `bones.json`, which `engine/geometry.py` supports for
  bones today and would need a soft-tissue (muscle belly / fat / skin
  offset-surface) extension. This is primarily a data-acquisition and mesh
  pipeline task rather than a modeling-design task — the anchors and fiber
  fields it would be built around are already correct.

## Stage 6 — Physiologically-driven validation
- Cross-check generated moment arms against published values (e.g.
  OpenSim's Delp/Holzbaur models, BSD-licensed, https://opensim.stanford.edu)
  for the regions modeled — this is the strongest possible correctness
  check because it validates the *functional consequence* of the geometry,
  not just its topology.

Each stage is independently mergeable and independently verifiable with the
same `tests/` suite — there is no "big bang" full-body cutover required.
