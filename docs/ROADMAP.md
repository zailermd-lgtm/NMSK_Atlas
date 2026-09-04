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

## Milestone — ligaments and cartilage introduced (new categories, major structures)

Following the muscular system's completion, two entirely new entity
categories were added, per the user's explicit "complete all nerves,
muscles, tendons, ligaments, chondrus [cartilage], bones, fascia, etc."
directive: `schema/ligament.schema.json` and `schema/cartilage.schema.json`,
each modeled with the same "one-or-more functionally distinct
sub-pieces per named structure" convention used by muscle's
`functional_compartments` (ligaments get `bands[]`, e.g. the ACL's
anteromedial/posterolateral bundles or the deltoid ligament's 4 parts;
cartilage gets `parts[]`, e.g. a meniscus's anterior horn/body/posterior
horn or an intervertebral disc's anulus fibrosus/nucleus pulposus).

- **Ligaments** (`data/ligaments/*.json`, 57 entities): major named
  ligaments for the shoulder (15, incl. the glenohumeral ligament
  complex's 4 bands and the interclavicular ligament), elbow (6, incl.
  the UCL's 3 bands), wrist (2, incl. the wrist ligament complex's 5
  bands covering the scapholunate interosseous ligament), hip (2, incl.
  the hip capsular ligament complex's 5 bands), knee (10: ACL, PCL, MCL,
  LCL, patellar ligament, each with their documented bands), ankle (4:
  the lateral ligament complex's 3 bands + the deltoid ligament's 4
  bands), spine (6 midline structures: ALL, PLL, ligamentum flavum,
  interspinous, supraspinous, ligamentum nuchae), pelvis (10: SI joint
  ligaments, sacrotuberous/sacrospinous, pubic symphysis ligaments), and
  TMJ (2, incl. the accessory sphenomandibular/stylomandibular
  ligaments).
- **Cartilage** (`data/cartilage/*.json`, 32 entities): articular
  (hyaline) cartilage at 7 major joints/joint-pairs × 2 sides (shoulder,
  elbow, wrist, hip, knee, patellofemoral, ankle — 14 entities), the
  knee menisci (4, each with anterior horn/body/posterior horn parts),
  the TMJ disc (2, with anterior band/intermediate zone/posterior
  bilaminar-zone parts), the intervertebral discs (3, one grouped entity
  per spinal region matching the grouped-vertebrae bone convention,
  each with anulus fibrosus/nucleus pulposus parts), the glenoid and
  acetabular labra (4), the pubic symphysis's interpubic fibrocartilage
  disc (1), the wrist's TFCC articular disc (2), and the costal
  cartilages (2, with true/false/floating rib parts).
- **Deliberately out of scope for this pass**: elastic cartilage (ear,
  epiglottis) and the laryngeal cartilaginous skeleton (thyroid/cricoid/
  arytenoid) — the latter already flagged as a future extension in
  Stage 3 above, since the larynx isn't yet a skeletal element in this
  atlas's bone set.
- Adversarially fact-checked in 2 parallel passes (ligaments, cartilage)
  before commit — see docs/VERIFICATION.md finding #11.
## Milestone — tendon schema introduced, closing out the "nerves, muscles,
tendons, ligaments, cartilage, bones, fascia" list

`schema/tendon.schema.json` completes the last uncovered category from
the user's explicit directive. Like ligaments and cartilage, it is
deliberately NOT a duplicate of what `muscle.schema.json` already
covers: every muscle's ordinary tendinous insertion is already fully
described by `attachments.insertion_bone`/`insertion_landmark`, so
`data/tendons/*.json` (37 entities) is scoped to tendons with genuine
standalone identity beyond one simple muscle's insertion —
multi-muscle convergence (pes anserinus, the conjoint proximal
hamstring tendon, the abdominal wall's conjoint tendon), documented
internal layering (the quadriceps tendon's 3 fiber layers, the
Achilles tendon's spiraling gastrocnemius/soleus fibers), fibro-osseous
pulley/sheath systems (the finger flexor tendons' A1-A5/C1-C3 pulleys),
or a clinically-distinct named region (the rotator cuff's hypovascular
"critical zone," the common flexor/extensor tendon origins of
"golfer's"/"tennis" elbow):
- **Upper limb** (18): the rotator cuff tendon complex (4 parts), the
  biceps brachii tendon complex (long head's intra-articular course +
  short head + distal bicipital aponeurosis), the triceps tendon, the
  common flexor and common extensor tendons, the finger flexor tendon
  pulley system, the extensor hood, and 2 minor named tendons (palmaris
  longus, noted for its frequent congenital absence and use as a graft
  donor; extensor pollicis longus, noted for its Lister's-tubercle
  pulley mechanism and associated rupture risk).
- **Lower limb** (14): the Achilles tendon (2 parts, documented spiral
  fiber twist), the quadriceps tendon (3 layers), pes anserinus (3
  muscle contributions), the proximal hamstring conjoint tendon, the
  semimembranosus distal tendon (4 expansions), the iliopsoas tendon,
  and the adductor magnus distal tendon (noted for the adductor hiatus
  it creates for the femoral vessels).
- **Trunk** (3): the diaphragm's central tendon (midline, unpaired) and
  the conjoint tendon (inguinal falx) bilaterally.
- **Head & neck** (2): the temporalis tendon.
- Adversarially fact-checked before commit — see docs/VERIFICATION.md
  finding #12.

This completes first-class schema coverage for every category the user
named. Bones and fascia were already comprehensively covered from
earlier passes; nerves and vessels likewise cover the major named
trees. Remaining future extensions (per-tendon numeric
`position_local_mm` landmark coverage, additional minor
tendons/ligaments/cartilage structures if identified, Stage 4/5/6 below)
are incremental depth additions to an already-complete category set,
not new categories.

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

## Stage 5 — Sub-millimetre voxel geometry (revised)

**Superseded plan.** Earlier drafts of this stage listed BodyParts3D /
Z-Anatomy (CC BY-SA) alongside the Visible Human Project as interchangeable
options, and offered procedural lofting as a fallback. Both of those are now
ruled out, for reasons recorded in full in
[GEOMETRY_SOURCES.md](GEOMETRY_SOURCES.md):

- **CC BY-SA sources are excluded.** Share-alike forces every derivative
  open and forbids restricting third parties, which is incompatible with
  this project's proprietary intent. Editing the meshes does not escape it.
- **Procedural lofting is insufficient.** It cannot support the clinical
  targets — injection planning into a named muscle compartment, or
  correlation against a real ultrasound image, needs true tissue boundaries
  from a real body, not an extruded approximation.

**Target.** Below 1 mm³ per voxel. The Visible Human Female cryosections are
0.33 mm isotropic (0.036 mm³); the Male is 0.33 × 0.33 × 1.0 mm
(0.109 mm³). Both already clear the target, and both come with CT and MRI of
the *same* cadaver, which is what makes cross-modality correlation possible
against ground truth.

### 5a — Ingest the lower-extremity segmentation
Andreassen et al. (Univ. of Denver), *Sci Data* 10:34 (2023),
[doi:10.1038/s41597-022-01905-2](https://doi.org/10.1038/s41597-022-01905-2),
reported as CC BY 4.0 — **confirm at source before commercial release**.
260 geometries per subject: 76 muscles, 28 bones, 16 cartilages, 8
ligaments, 2 fat bodies, pelvis→feet, with aligned cryosection and CT
stacks, 3D Slicer masks, and STL at several processing levels. Map its
structure names onto this atlas's existing IDs; convert to the atlas frame.

The "Final 3D STL models" folder is 87.8 MB zipped, so this stage is a small
download rather than the bulk fetch the earlier draft implied. But those
models are remeshed to 1.5 mm (muscle) / 1.0 mm (bone) / 0.75 mm (cartilage,
ligament) edge lengths — **coarser than this project's sub-millimetre
target**. They are the right starting point for mapping and rigging; the raw
~0.33 mm STLs or the native-resolution segmentation masks are what a
sub-millimetre surface has to come from. See
[GEOMETRY_SOURCES.md](GEOMETRY_SOURCES.md) for the full folder table.

### 5b — Arbitrary-plane cross-section engine
Resample the voxel stack on any plane, with cryosection / CT / MRI shown
side by side against the segmented overlay.

Cheaper than first assumed: the aligned cryosection and CT DICOM folders are
about 765 MB together, not the hundreds of gigabytes this stage was drafted
against. The CT is already registered to the cryosections, and the transverse
offsets present in the original Visible Human sequences are already
corrected — so the cross-modality correlation arrives without a registration
step of our own.

### 5c — Nerves and vessels
Not present in the DU release, and the layer that injection safety depends
on. Segment from the cryosections ourselves — which also means this layer is
owned outright.

### 5d — Upper limb and trunk
The DU release stops at the pelvis. For post-stroke spasticity the upper
limb is the larger clinical need. Segment from VHP.

### 5e — Motor points / NMJ zones — 🔶 STARTED
**Not resolvable in cryosection at any resolution.** Botulinum dosing targets
endplate-rich zones, not muscle centroids, so this layer must come from the
Sihler-stain and electrophysiology literature and lands in the atlas data
layer, not the geometry layer.

Done so far: 152 `motor_endplate_zones` entries across 40 muscles — ten distal
lower-limb, nine proximal lower-limb, seven proximal upper-limb, eight anterior
forearm, five deep cervical, plus psoas, sternocleidomastoid and splenius
capitis — each as a percentage range along a named landmark line, in the
source's own terms. Ten of them are flagged
`recommended_as_injection_target: false`: real nerve-dense regions that a
cadaveric puncture simulation ruled out because the pleura, the lung apex, the
submandibular gland or the brachial plexus lies in the path. **Consumers
selecting injection targets must filter on that field, not on the presence of
a zone.** Every
`neuromuscular_junction_zone` declares whether its fascicle fraction is
`measured` or a `modelling_default`; all 534 are currently the latter.
`ultrasound_injection_approach` added for 35 muscles: 14 distal upper limb, 10
proximal upper limb, 11 proximal lower limb. All four published parts of the
Elias University Hospital series have been mined.

New in this stage: `injection_target_points`, 50 entries across 15 muscles —
the eight anterior forearm muscles, the five deep cervical muscles and the two
splenii. Where a zone gives only a level along the muscle, a target point fixes
the transverse position and the depth too — a point in the limb or neck, not a
level — which is the difference between choosing where to scan and planning a
needle path. All from primary cadaveric studies, not reviews. The cervical
entries add a measured needle angle and the tissue layers crossed: longus
capitis is entered at 58° rather than perpendicular, because the trachea and
oesophagus cover the target in front and the carotid lies lateral to it.

That study also supplies the evidence for a modelling choice made earlier on
judgement: only four of the eight anterior forearm muscles have their
nerve-dense region near mid-belly, and flexor carpi ulnaris's sits in the upper
fifth. The mid-belly default is a default, and is now labelled as one for a
documented reason rather than a cautious one.

Still open:
- **The hand has no endplate zones** — thenar group, adductor pollicis,
  lumbricals, interossei. They carry an ultrasound approach and nothing else.
  The forearm gap is closed.
- **Five muscles covered by the EUH series still carry no zone**, for three
  different reasons, all written up in `docs/SOURCES.md`: deltoid (the
  literature itself has no data — the source says so), subscapularis and
  biceps femoris (numbers lost to text extraction), gluteus maximus
  (percentages survive but their reference lines do not), pectoralis major's
  abdominal part (not mapped by the source). None was reconstructed by
  analogy with a neighbouring muscle.
- **The anterior/posterior surface of the Zhou et al. puncture points** is
  unresolved for one of eleven points, so `depth_measured_from` is omitted on
  all of them. Closing this needs the paper's CT figure read directly.
- Van Campenhout's 2011 lower-limb review is paywalled; its per-muscle
  figures are not entered.

The centerline and fibre-field work already built (1 mm-sampled fibre tracts,
nerve and vessel paths, anchor set) remains correct and is what the voxel
geometry gets registered *onto* — it is not superseded by this stage.

## Stage 6 — Physiologically-driven validation — 🔶 STARTED

`scripts/audit_geometry_vs_atlas.py` tests the atlas's hand-authored
`fiber_architecture` against the ingested Visible Human geometry. Until the
ingest landed, every one of those numbers had only ever been checked against
other literature; there is now a physical object to test them on.

Three checks, run on the 128-mesh bilateral VHM set:

- **Scale.** Femur 481.9 / 482.8 mm, tibia 412.3 / 408.2 mm — inside human
  ranges, so a unit or scale error is ruled out before anything else is
  concluded. This is what makes the volume result below trustworthy.
- **Fascicle length vs mesh extent** — a hard constraint, since a fascicle
  cannot exceed the muscle containing it. **No violations**, across every
  compartment with both a fascicle length and geometry.
- **Volume vs implied volume**, where PCSA = V·cosθ/L_f gives the atlas's own
  numbers an implied volume. Median ratio **4.67**, range 0.88–19.9, only
  3 of 69 muscles within a factor of two.

That last result is systematic and one-directional — this body has more
muscle than the architecture implies, almost everywhere — which is the
signature of a population difference rather than scattered data-entry errors.
The likely cause is donor age: the standard lower-limb architecture source
(Ward et al. 2009) has a mean donor age in the eighties, while the Visible
Human Male was 39 and large. Segmentation contributes too, since these meshes
include investing fascia and aponeurosis that architecture studies dissect
away.

**The operational conclusion is a prohibition, not a correction.** Atlas PCSA
and this geometry's volume describe *different bodies* and must not be
combined into a single force estimate without an explicit, recorded scaling
decision. Rescaling the literature averages onto one unrepresentative cadaver
would trade a documented average for an individual, and is not done here.

### Landmark and anchor audit — what the geometry found

`scripts/audit_landmarks_vs_geometry.py`. Bone frames are measured from the
geometry, not assumed: femoral head and acetabular sphere fits for the
origins, epicondylar and plateau spreads for the transverse axes. Only the
pelvis's superior axis remains a convention.

Corrected, 12 landmarks: linea aspera, soleal line, tibial tuberosity, both
epicondyles and the greater trochanter, bilaterally. Median landmark distance
from its bone surface fell **4.2 mm → 1.9 mm**, with none beyond 40 mm.
Anchor-to-bone median fell **10.9 mm → 2.5 mm** once the anchors were
regenerated, since they are derived copies and my landmark edits had left
them stale.

Two checks turned out to be measuring nothing, and both are now excluded:
a landmark AT the frame's own origin (the femoral head) and a landmark of
kind `foramen_or_canal` (the obturator foramen, a 35×45 mm hole whose centre
is correctly ~20 mm from bone). The foramen had been the second-worst
"error" in the set.

One real bug in `scripts/generate_anchors.py`: it matched **negations**.
"posterior tibia (medial, below soleal line)" names the soleal line in order
to exclude it, and the substring matcher anchored flexor digitorum longus
exactly there. Four bilateral pairs were affected — FDL, gluteus medius,
popliteus, rhomboid major. It now refuses such a match and reports it.

**Collapsed landmarks.** Some landmarks were broad attachment lines collapsed
to a single point, so no one value could serve the muscles hanging off them:

| Landmark | Muscles sharing one coordinate | Now |
|---|---|---|
| iliac crest | 6 — TFL, quadratus lumborum, longissimus, iliocostalis, both obliques | split into three measured points along the arc |
| ischial tuberosity | 8 — adductor magnus, biceps femoris, gemellus inferior, quadratus femoris, … | split into five measured facets |
| greater trochanter | 7 — both gemelli, gluteus medius/minimus, obturator internus, piriformis, … | split into facets earlier |
| phalanges (hand/foot) | 7 each — every intrinsic, all on digit III's proximal base | open |

The iliac crest measures as a **176 mm arc** from ASIS to PSIS on the Visible
Human pelvis, and its highest point sits 50 mm behind where the atlas's single
point was. It now carries an anterior point on the outer lip (tensor fasciae
latae, external oblique), a middle point on the intermediate line (internal
oblique, transversus) and a posterior point on the inner lip (quadratus
lumborum, erector spinae), each measured on both hip bones and averaged; the
two sides differ by 7–10 mm in X, the left ilium sitting further lateral of
its acetabulum. The ischial tuberosity carries the superolateral facet of the
upper area (semimembranosus), the inferomedial facet (the conjoint tendon of
semitendinosus and the long head of biceps), the lateral part of the lower
area (adductor magnus), the lateral border (quadratus femoris, gemellus
inferior) and the medial, perineal surface (ischiocavernosus, superficial
transverse perineal); those agree between sides within 1–4 mm. The gluteal
surface of the ilium gained a representative origin point each for gluteus
medius, minimus and maximus, and the fibula a proximal and a distal point on
the lateral surface of its shaft (fibularis longus, brevis), so fibularis
longus no longer originates at the frame origin inside the fibular head.
Each muscle's attachment prose was made to name the facet it takes, since
that is what the anchor generator reads. 114 landmarks are now measured
against geometry, median 1.2 mm from the bone surface.

The matcher needed two corrections to make this work: a word repeated in a
landmark name scored twice, and the parenthesised list of WHO attaches was
scored like the description of WHERE, so a muscle whose text names its
neighbour ("deep to fibularis longus") matched the neighbour's landmark. The
site is now scored first and the attachment list only breaks ties. One new
flag is honest: the long head of biceps femoris arises from the inferomedial
facet and its tendon wraps laterally round the tuberosity to reach its belly,
which the straight-line check reports as blocked by the hip bone. Origins
have no declared path yet; only insertions do.

The phalanges case is worse than a broad line — 14 separate bones are one
atlas entity, so abductor pollicis brevis and abductor digiti minimi both
resolve to digit III. Closing it needs the grouped bone entity split, which
is a data-model change, not a correction.

**Per-compartment anchors.** Flexor hallucis brevis's two heads insert on
opposite sides of the hallux, described in one shared `attachments.
insertion_landmark` string — "medial head ... via the medial sesamoid,
lateral head ... via the lateral sesamoid" — and the generator refused it
outright rather than guess which compartment the coordinate belonged to.
`generate_anchors.py` now recognises when a muscle's compartments each
supply their own distinguishing word (derived from the compartment's own
`name`: "Medial head" -> "medial", "Adductor part" -> "adductor") and
splits the ONE shared text into one clause per compartment at that word,
matching each clause independently and emitting one anchor per
compartment (`anchor_<compartment_id>_insertion`) instead of one anchor
for the whole muscle. Falls back to the original whole-muscle match
whenever the split can't be done cleanly (most muscles, which have one
compartment or several undifferentiable ones), so nothing regresses.

Fixed flexor hallucis brevis (medial/lateral heads) and adductor magnus
(adductor/hamstring parts) this way. Doing so exposed a third,
independent bug: femur_r had no standalone "linea aspera" landmark, only
the compound "gluteal tuberosity/linea aspera" entry, so
adductor_longus_r, adductor_brevis_r and vastus_medialis_r's insertions
had silently resolved to nothing at all on the right side while their
left counterparts worked — added, mirroring femur_l's entry. 226 -> 238
anchors. Still open, found in the process and not yet fixed:
vastus_lateralis_r's origin resolves to "greater trochanter lateral facet
(gluteus medius insertion)" -- a facet that belongs to a different muscle
-- because its own text names both linea aspera and greater trochanter
and the trochanter facet scores higher; a single-compartment muscle with
a genuinely multi-site origin, which the per-compartment mechanism above
cannot help since there is only one compartment to split into.

**Moment-arm cross-check — done for the regions modeled.**
`scripts/validate_moment_arms.py` computes each muscle's moment arm as the
classic rigid-body moment of a line-of-action force about an axis,
`r = (A - C) × normalize(B - A) · u`, for a straight line between the
origin and insertion anchors (both resolved through the same measured bone
frames the landmark audit uses) and a joint axis (point C, direction u).
Knee flexion uses the tibial plateau's fitted transverse axis — real
geometry, not a convention; hip and ankle flexion/extension use the atlas's
mediolateral convention, the same convention already used where no
cartilage mesh gives a transverse axis to fit.

Building this surfaced three landmark-matching gaps (below), fixing which
took the computable set from 6 pairs to all 12: gluteus maximus/hip
extension, the three hamstrings/knee flexion, and gastrocnemius and
soleus/ankle plantarflexion, all bilateral.

**10 of 12 land inside their published range**: Delp SL, PhD dissertation
(1990) and Arnold EM et al., Ann Biomed Eng 38:269 (2010) [OpenSim's
gait2392 lower-limb model] for the hip and knee; Herzog W, Read LJ, J Anat
182:213 (1993) for the knee flexors; Maganaris CN et al., J Physiol
510:977 (1998) and Rugg SG et al., J Biomech 23:495 (1990) for the ankle.

**Semitendinosus is the instructive exception, both sides.** It computes a
3–5 mm knee-flexion moment arm against a published 15–35 mm — not a data
error, but the straight-line method meeting its own stated limit. Biceps
femoris and semimembranosus insert POSTERIOR to the knee axis (fibular
head; posteromedial tibial condyle) throughout, so a straight chord from
the ischial tuberosity stays on the correct side of the axis and gives a
believable lever arm. Semitendinosus's real insertion, at the pes
anserinus, is well ANTERIOR on the tibial shaft — the actual tendon curves
around the medial tibial condyle to get there, and a straight chord to
that anterior point swings close to the knee axis instead of staying
behind it, which is exactly the wrap-dependent case the module docstring
already warns a bare two-point path cannot handle. Left as a documented
miss rather than adjusted to pass: the fix is a wrap surface or via point
at the condyle, not a different coordinate.

**The three gaps**, all in `data/skeleton/bones.json`, found because their
absence left an insertion anchor unresolved for a muscle this check
needed: femur_l had no "gluteal tuberosity" entry at all (only "linea
aspera", under a different name), so gluteus_maximus_l's insertion text
matched nothing even though the identical text matches femur_r — added as
a new entry, mirrored, rather than a rename, so the three other muscles
already resolving against femur_l's existing entry were undisturbed.
Tibia's pes anserinus landmark was named "...insertion (...)", and no
muscle's own attachment prose uses the word "insertion" to describe
itself, so sartorius, gracilis and semitendinosus all failed to match it
on both sides despite naming this exact structure — renamed to drop that
word. Neither tibia carried semimembranosus's real insertion site
(posteromedial tibial condyle) at all — added new. All three new/changed
coordinates were re-audited against the real geometry: 3.9–5.7 mm from
the bone surface, inside this atlas's existing tolerance.

This is a straight-line, no-wrap, single-pose method — it deliberately
does not model the posterior wrap of the Achilles tendon around the
calcaneus or of gastrocnemius around the femoral condyles, which is why
OpenSim gives those muscles wrap surfaces instead of a bare two-point
path. The result validates that this atlas's real, measured geometry
produces the right ORDER OF MAGNITUDE and SIGN of leverage at three
joints — a stronger check than topology alone — not that it reproduces
OpenSim's wrapped paths exactly.

Each stage is independently mergeable and independently verifiable with the
same `tests/` suite — there is no "big bang" full-body cutover required.
