# NMSK Atlas — Roadmap to full whole-body, 1mm-verified coverage

This repo delivers, so far: the full architecture, whole-body breadth
data (skeleton, joints, nerve roots), and **four** fully-detailed,
fully-verified flagship regions:
- **Upper limb** (shoulder→hand) — 41 muscles, brachial plexus (43 nodes),
  named arterial+venous trees (38 vessels), fascial/retinacular/pulley
  system (17 structures).
- **Lower limb** (pelvis→foot) — 49 muscles, lumbosacral plexus (31 nodes),
  named arterial+venous trees (37 vessels), fascial compartment system
  (21 structures).
- **Trunk** (spine, ribcage, abdominal/back wall, pelvic floor) — 24
  muscle groups (incl. the unpaired diaphragm), thoracic segmental nerves
  (59 nodes), the thoracic/abdominal aortic tree + azygos venous system
  (105 vessels), and the thoracolumbar fascia/rectus sheath system
  (10 structures).
- **Head & neck** — 35 muscle groups (facial expression, mastication,
  extraocular, tongue/pharynx, neck), the cranial nerve motor trees +
  cervical plexus (42 nodes), the carotid/vertebral vascular trees (26
  vessels), and the cervical fascial system (5 structures).

## Milestone — whole-body muscular system complete (100% flagship depth)

Following the four flagship-region passes below, a fifth pass promoted
every remaining muscle still sitting at breadth-only depth in
`data/muscles/muscle_index.json` (73 muscles, spanning all three limb/
trunk regions — the deep hip rotators, adductor group, forearm/hand
intrinsics, deep posterior leg and intrinsic foot muscles, and the
scapulohumeral group) up to the same full flagship depth as every other
muscle in the atlas: `functional_compartments[]` with fiber architecture,
NMJ zones, and cited sources. `muscle_index.json` is now an **empty
array** — every previously-catalogued whole-body muscle name has a full
flagship JSON file. Total: **297 muscle files** across `upper_limb/` (82),
`lower_limb/` (98), `trunk/` (47), `head_and_neck/` (70). Adversarially
fact-checked in 3 parallel passes (see docs/VERIFICATION.md finding #10),
which caught and corrected one significant citation-mischaracterization
(trapezius / Johnson et al. 1994) and several smaller precision nuances —
the same recurring failure mode as every prior stage's fact-check.
`muscle_index.json` is retained (not deleted) as the empty holding list
any future newly-identified muscle would stage through before promotion.

All four regions were chosen/completed because together they exercise
every requirement richly: complex joints, pennate/parallel/multipennate/
fusiform/convergent muscles, documented intramuscular compartments (down
to opposite-action parts of one named muscle, e.g. internal intercostals
and lateral pterygoid), full plexuses and segmental/cranial nerve maps
down to motor points, full named arterial/venous trees, and dense
fascial/retinacular/pulley/aponeurotic systems — all left/right mirrored,
schema-validated, and adversarially fact-checked (docs/VERIFICATION.md).

Extending to the rest of the body uses the **same schemas, same generator,
same validators** — it is bounded, well-scoped data-authoring work, staged
as follows:

## Stage 1 — Lower limb kinetic chain (pelvis → foot) — ✅ DONE
- Full depth delivered: `data/muscles/lower_limb/*.json` (originally 14
  muscles ×2 sides; the remaining 35 lower-limb muscles — gluteus
  minimus, TFL, piriformis, obturators, gemelli, quadratus femoris,
  sartorius, adductor longus/brevis, gracilis, pectineus, plantaris,
  popliteus, tibialis posterior, FDL, FHL, EDL, EHL, fibularis
  longus/brevis/tertius, and the intrinsic foot muscles — were later
  promoted from breadth to the same flagship depth in the whole-body
  muscular-system completion pass below, bringing the region to 49
  muscles ×2 sides = 98 files), `data/nerves/lumbosacral_plexus.json`,
  `data/vascular/lower_limb_arterial.json` + `lower_limb_venous.json`,
  `data/fascia/lower_limb_fascia.json`.

## Stage 2 — Trunk (spine, ribcage, abdominal & back wall, pelvic floor) — ✅ DONE
- Full depth delivered: `data/muscles/trunk/*.json` (originally 13 muscle
  groups ×2 sides + diaphragm midline/unpaired = 27 files — the erector
  spinae trio each split by region, multifidus, quadratus lumborum,
  rectus abdominis's 4 tendinous-intersection segments, the 3 flat
  abdominal wall layers, both intercostal layers, diaphragm's 3 parts,
  and the pelvic floor; the remaining scapulohumeral group — trapezius,
  latissimus dorsi, both rhomboids, levator scapulae, serratus anterior/
  posterior superior/inferior, pectoralis minor, subclavius — was later
  promoted from breadth to the same flagship depth in the whole-body
  muscular-system completion pass below, bringing the region to 24
  muscle groups = 47 files), `data/nerves/thoracic_segmental_nerves.json`
  (59 nodes: intercostal nerves T1-T6, thoracoabdominal nerves T7-T11,
  subcostal nerve T12), `data/vascular/trunk_arterial.json` +
  `trunk_venous.json` (thoracic/abdominal aorta through the iliac
  bifurcation; azygos system + IVC tributaries), `data/fascia/
  trunk_fascia.json` (the 3-layer thoracolumbar fascia, rectus sheath,
  linea alba, inguinal ligament, transversalis fascia, and more).
- Deliberately left at breadth depth in `data/muscles/muscle_index.json`
  (not yet promoted; a smaller residual than the muscles handled above):
  the small deep segmental back muscles not yet catalogued at all
  (semispinalis, rotatores, interspinales, intertransversarii) and minor
  thoracic wall muscles (innermost intercostals, transversus thoracis,
  subcostales).
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

## Stage 3 — Head & neck — ✅ DONE
- Full depth delivered: `data/muscles/head_and_neck/*.json` (35 muscle
  groups × 2 sides — 9 facial-expression, 4 mastication, 6 extraocular, 3
  tongue + 2 pharynx, 11 neck), `data/nerves/cranial_and_cervical_nerves.json`
  (42 nodes: facial n., trigeminal V3, oculomotor/trochlear/abducens,
  hypoglossal n., glossopharyngeal n./vagal pharyngeal plexus, and the
  cervical plexus with ansa cervicalis + phrenic n. origin),
  `data/vascular/head_neck_arterial.json` + `head_neck_venous.json` (26
  vessels: carotid system + middle meningeal a.; jugular system), plus a
  `vertebral_a_r` branch added to the existing
  `data/vascular/upper_limb_arterial.json` (subclavian's other cervical
  branch), and `data/fascia/cervical_fascia.json` (the 3-layer deep
  cervical fascia, carotid sheath, buccopharyngeal fascia).
- **Schema-novelty resolved without a schema change**: the roadmap
  originally anticipated needing an `insertion_bone` → `insertion_dermis_
  region` extension for skin-inserting facial-expression muscles and
  sclera-inserting extraocular muscles. In practice the *original breadth
  pass* (Stage 0) had already solved this the same way `bones.json`
  solves multi-landmark bones: `origin_bone`/`insertion_bone` reference
  the nearest overlying skeletal bone frame (e.g. frontalis "inserts" on
  the frontal bone even though the true insertion is dermal), with the
  landmark string documenting the real soft-tissue structure and each
  muscle's `function_note` stating the approximation explicitly. No
  schema change was needed because this atlas's rig has no free-deforming
  skin/eyeball rigid-body layer yet for such a field to attach to (see
  Stage 4/5 below) — rigidly anchoring to the nearest bone is the
  correct-for-this-rig approximation, not a workaround.
- **Cross-file vascular/nerve seams, explicitly documented rather than
  silently left disconnected**: the aortic arch (giving rise to the
  brachiocephalic trunk/left common carotid/left subclavian) and the
  internal-jugular/subclavian confluence are real single structures that
  this atlas's per-region file split leaves as separate `tree_name`
  groups (the connectivity validator groups strictly by `tree_name`, so
  true cross-file parent/child edges aren't possible without a larger
  refactor touching every already-pushed vascular file). Each such seam —
  and the ansa cervicalis's genuine two-root loop, which the simple
  parent/child nerve-tree model also can't represent exactly — is
  resolved with a documented `notes` cross-reference rather than a
  broken or silently-omitted edge.
- Deliberately left at breadth depth in `data/muscles/muscle_index.json`:
  the individual extrinsic/intrinsic laryngeal muscles and intrinsic
  tongue muscles (no discrete bony attachments to anchor a rigid-body
  compartment on, since the cartilaginous larynx isn't yet a skeletal
  element in this atlas), the middle/inferior pharyngeal constrictors,
  and the small intraocular smooth muscles (pupillary sphincter/dilator,
  ciliary muscle — smooth muscle, out of this atlas's skeletal-muscle
  focus).
- Deliberately NOT done: the eyeball as its own rotating rigid body (a
  natural small future extension once a proper soft-tissue/organ layer
  exists — see Stage 4/5), and the cartilaginous larynx/hyoid-adjacent
  skeleton as individually-modeled elements (thyroid/cricoid/arytenoid
  cartilages are currently only referenced descriptively via the
  adjacent hyoid attachment region in sternothyroid/stylopharyngeus).

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
