# NMSK Atlas — Roadmap to full whole-body, 1mm-verified coverage

This repo delivers, so far: the full architecture, whole-body breadth
data (skeleton, joints, nerve roots, muscle index), and **three** fully-
detailed, fully-verified flagship regions:
- **Upper limb** (shoulder→hand) — 13 muscles, brachial plexus (43 nodes),
  named arterial+venous trees (38 vessels), fascial/retinacular/pulley
  system (17 structures).
- **Lower limb** (pelvis→foot) — 14 muscles, lumbosacral plexus (31 nodes),
  named arterial+venous trees (37 vessels), fascial compartment system
  (21 structures).
- **Trunk** (spine, ribcage, abdominal/back wall, pelvic floor) — 14
  muscle groups, thoracic segmental nerves (59 nodes), the thoracic/
  abdominal aortic tree + azygos venous system (105 vessels), and the
  thoracolumbar fascia/rectus sheath system (10 structures).

All three regions were chosen/completed because together they exercise
every requirement richly: complex joints, pennate/parallel/multipennate/
fusiform/convergent muscles, documented intramuscular compartments (down
to opposite-action parts of one named muscle, e.g. internal intercostals),
full plexuses and segmental nerve maps down to motor points, full named
arterial/venous trees, and dense fascial/retinacular/pulley/aponeurotic
systems — all left/right mirrored, schema-validated, and adversarially
fact-checked (docs/VERIFICATION.md).

Extending to the rest of the body uses the **same schemas, same generator,
same validators** — it is bounded, well-scoped data-authoring work, staged
as follows:

## Stage 1 — Lower limb kinetic chain (pelvis → foot) — ✅ DONE
- Full depth delivered: `data/muscles/lower_limb/*.json` (14 muscles ×2
  sides), `data/nerves/lumbosacral_plexus.json`, `data/vascular/
  lower_limb_arterial.json` + `lower_limb_venous.json`, `data/fascia/
  lower_limb_fascia.json`. Remaining lower-limb muscles stay at breadth
  depth in `data/muscles/muscle_index.json` (gluteus minimus, TFL,
  piriformis, obturators, gemelli, quadratus femoris, sartorius, adductor
  longus/brevis, gracilis, pectineus, plantaris, popliteus, tibialis
  posterior, FDL, FHL, EDL, EHL, fibularis longus/brevis/tertius, and the
  intrinsic foot muscles) — same tradeoff as the upper limb's non-flagship
  muscles.

## Stage 2 — Trunk (spine, ribcage, abdominal & back wall, pelvic floor) — ✅ DONE
- Full depth delivered: `data/muscles/trunk/*.json` (14 muscle groups ×2
  sides, diaphragm midline/unpaired — the erector spinae trio each split
  by region, multifidus, quadratus lumborum, rectus abdominis's 4
  tendinous-intersection segments, the 3 flat abdominal wall layers, both
  intercostal layers, diaphragm's 3 parts, and the pelvic floor),
  `data/nerves/thoracic_segmental_nerves.json` (59 nodes: intercostal
  nerves T1-T6, thoracoabdominal nerves T7-T11, subcostal nerve T12),
  `data/vascular/trunk_arterial.json` + `trunk_venous.json` (thoracic/
  abdominal aorta through the iliac bifurcation; azygos system + IVC
  tributaries), `data/fascia/trunk_fascia.json` (the 3-layer
  thoracolumbar fascia, rectus sheath, linea alba, inguinal ligament,
  transversalis fascia, and more).
- Deliberately left at breadth depth in `data/muscles/muscle_index.json`
  (same tradeoff as the limbs' non-flagship muscles): the small deep
  segmental back muscles not yet catalogued at all (semispinalis,
  rotatores, interspinales, intertransversarii) and minor thoracic wall
  muscles (innermost intercostals, transversus thoracis, subcostales).
- Deliberately NOT done: per-vertebra joint splitting (C1-C7/T1-T12/L1-L5
  as individual bones with individual motion-segment joints, replacing
  the current composite regional spine joints) — this is a larger
  structural change to `bones.json` than any other stage has made (every
  other stage added numeric detail to existing grouped bones rather than
  splitting a group into per-level bones), and would need its own pass
  once the grouped-bone convention's limits are worth revisiting. The
  composite `cervical_spine`/`thoracic_spine`/`lumbar_spine` joints
  already document this explicitly as pending.
- Full-body organ-parenchyma detail (liver, spleen, stomach, kidneys,
  bowel, adrenal glands) was explicitly kept out of scope per Stage 4's
  boundary — the celiac trunk, SMA, IMA, and renal/gonadal/suprarenal
  vessels are modeled as far as their origin and are documented as
  stub/leaf nodes rather than fully branched into visceral parenchyma.

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
