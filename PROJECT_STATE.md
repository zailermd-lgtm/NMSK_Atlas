# Project state

Resume point for a fresh session. Updated at milestones; see `docs/ROADMAP.md`
for the long-form plan and `docs/GEOMETRY_SOURCES.md` for licensing.

## What this is

A 3D atlas of the human musculoskeletal, neural and vascular systems, built to
plan musculoskeletal injections — PRP, and botulinum toxin for spasticity — as
well as to serve as a general atlas, an ultrasound and cross-section reference,
and a comparison against CT and MRI. Target resolution is sub-1 mm³/voxel.
The repository is proprietary and sellable; no CC BY-SA source may enter it.

Branch: `claude/3d-human-anatomy-atlas-e0kbxe`. 252 tests pass. Recent: Q70 DONE (male full-body skin surface from his own CT, not the DU-blocked photograph route -- his legs and feet now have skin at all, the largest visual gap against Z-Anatomy on either body; follow-up clipped his deltoid/triceps to the new skin too), Q69 DONE (transferred tibialis anterior clipped to her skin -- was poking through near the ankle, a rendering/registration defect found by visual QA against Z-Anatomy, not a completeness gap), Q64 Phase 3 DONE (left forearm bones, 490/491 slices, 1.83M voxels), Q62 Step 1a/1b DONE (forearm compartments and initial muscle separation). Female viewer V33 (368 structures), male V41 (350 structures).

No CT data is available yet from the repository owner (they have clinical
scans but haven't set up Python 3.13/TotalSegmentator on Windows). Pending
that, work has continued on literature-based content depth — see below.

## Recently deepened (literature-based, no geometry needed)

- **Lymphatic system**: 23 → 56 entities. Added the head/neck superficial
  node groups (submental, submandibular, parotid, mastoid, occipital,
  superficial cervical), supraclavicular nodes, mediastinal nodes
  (tracheobronchial, paratracheal, parasternal), abdominal nodes (celiac,
  superior/inferior mesenteric, lumbar/para-aortic), and the full pelvic
  chain (common/external/internal iliac, obturator). Reparented deep
  inguinal nodes onto the new external iliac nodes (was wired straight to
  the lumbar trunk).
- **Fascia**: added the osteofascial compartments of the hand (carpal
  tunnel, thenar, hypothenar, adductor, interosseous) and foot (medial,
  lateral, central, interosseous) — the surgical fasciotomy models,
  parallel to the leg/forearm compartments already carried.
- **Autonomic nervous system**: new, was entirely absent. Added the
  sympathetic trunk end to end — cervical chain (superior/middle cervical
  ganglia, stellate ganglion), thoracic chain with the splanchnic nerves,
  lumbar and sacral chains, ganglion impar, and the celiac and hypogastric
  plexuses. These are exactly the targets of stellate ganglion, lumbar
  sympathetic, celiac plexus and hypogastric plexus blocks — real
  image-guided procedures this atlas's injection-planning purpose covers.

## Atlas frame

+X subject's right, +Y superior, +Z anterior, millimetres, origin at the
midpoint of the two hip joint centres.

- DU Visible Human STL → atlas: `--axes='-x,-z,+y' --units mm --origin '346.821,173.476,426.352'`
- NIfTI RAS → atlas: `(x, z, y)`; a positive-determinant affine means the scan
  is stored mirrored and is refused, never silently corrected.

## Data model decisions that are easy to get wrong

- **Nerve ids are side-agnostic** (`axillary_n`), **vessel ids are sided**
  (`_r`/`_l`). A nerve's targets must therefore name both sides.
- `innervation.nerve` is a string, or a **list** where a muscle has more than
  one nerve. Packed pseudo-ids (`femoral_n_and_obturator_n`) are rejected.
- Every compartment carries `innervation_branch_ids`, and every nerve so named
  lists the compartment back in `targets`. A test holds both directions.
- **The compartment, not the muscle, is the unit a nerve block or a botulinum
  plan works in.**
- Endplate zones are stored **in the source's own terms** — a percent range
  along a named line between two landmarks — and are deliberately NOT converted
  into `position_fraction_along_fascicle`, because published reference lines run
  in varying directions and several run distal-to-proximal.
- The sciatic division is modelled from the popliteal fossa down; hamstring
  branches hang off the undivided trunk. Deliberate, documented in the tree.

## Geometry status

| Region | Source | State |
|---|---|---|
| Pelvis → ankle | DU Visible Human (CC BY 4.0) | ingested, `build/vh/vhm_both` |
| Spine, ribs, sternum, clavicle, scapula, humerus, great vessels | TotalSegmentator v2.0.1 CT case `s0913` (CC BY 4.0) | ingested 2026-09-09, `build/ct_s0913` — see "2026-09-09" section below |
| Skull (unified), forearm/hand bones, every upper-limb/trunk/neck/pelvic-floor/foot-intrinsic **muscle** | none | **still missing** — not in TotalSegmentator's structure set at all, see "Open, not literature-fixable" |

122 landmarks are measured against geometry: median 1.2 mm from the bone
surface, all within 15 mm. 217 anchors, median 0.9 mm from their own bone.
(Figures above are for the VH lower-limb geometry; see the 2026-09-08/09
sections below for the upper-body CT audit figures, which are worse and
explained there — real anchor-authoring errors found and fixed, plus
expected scan-field-of-view artifacts that are not bugs.)

## Previously blocked, now unblocked (2026-09-08)

The repository owner widened this remote environment's network policy and
supplied real TotalSegmentator CT cases directly via chat upload, working
around the network egress allowlist (Zenodo, Hugging Face, and NLM are all
unreachable from this sandbox's proxy). The Python-3.13-on-Windows blocker
described here previously was never actually exercised — this sandbox's
Python already had `nibabel`/`scikit-image` installed, so the only real
blocker was network access to the source data, not tooling. The full
merge → inspect → propose → convert → audit pipeline below is now
proven working end-to-end on two real cases (s1371, s0913):

```
python3 scripts/merge_totalsegmentator_masks.py <subject_dir> -o merged.nii.gz
python3 scripts/ingest_volume_geometry.py inspect merged.nii.gz
python3 scripts/ingest_volume_geometry.py propose merged.nii.gz --subject ct01
python3 scripts/ingest_volume_geometry.py convert merged.nii.gz --subject ct01 --origin '<from inspect>'
python3 scripts/audit_landmarks_vs_geometry.py --subject ct01
```

The 0.33 mm `Original 3D STL Models-stl` ingest (`--subject vhm_raw`) is
still waiting — unrelated to the CT work above.

## Open, in rough priority order

1. **`phalanges_hand` is 14 bones as one entity.** Seven muscles per side
   resolve to digit III. Needs the grouped entity split — a data-model change,
   and there is no hand geometry to measure against yet.
2. **Common flexor and extensor origins** on the humerus carry five muscles
   each on one coordinate. Splitting them means authoring, not measuring, until
   there is upper-limb geometry.
3. **Flexor hallucis brevis** is refused an anchor: its two heads insert on
   opposite sides of the hallux and the generator emits one anchor per muscle
   end, not per compartment. The refusal is correct; per-compartment anchors
   would fix it.
4. **Tibialis anterior and fibularis longus** insertion paths are still blocked
   by bone; closing them needs via points that cannot be measured from the
   geometry available.
5. Spine, rib and sternum landmarks have no numeric coordinates — to be measured
   from CT once (1) above is unblocked.
6. Extend `named_members` in the landmark audit to ribs and vertebrae, so the
   identity check covers them.
7. ~~Cross-check generated moment arms against OpenSim's published models.~~
   **Done** — `scripts/validate_moment_arms.py`, 10/12 computable pairs land
   inside their published range. See ROADMAP.md Stage 6.
8. ~~Semitendinosus, semimembranosus and the left gluteus maximus are
   missing their insertion anchor.~~ **Fixed** — three landmark-matching
   gaps in `data/skeleton/bones.json` (217 → 226 anchors). See ROADMAP.md
   Stage 6 for detail.
9. Semitendinosus's knee-flexion moment arm computes 3–5 mm against a
   published 15–35 mm — not a data error, the straight-line moment-arm
   method's own documented limit meeting a muscle whose real path wraps
   the medial tibial condyle. Fixing it needs a wrap surface or via point,
   which the anchor/rig schema doesn't carry yet.
10. ~~Flexor hallucis brevis is refused an anchor... per-compartment
   anchors would fix it.~~ **Fixed** — `generate_anchors.py` now splits a
   muscle's one `attachments` text into one clause per compartment when
   each compartment's own name supplies a distinguishing word ("medial
   head"/"lateral head", "adductor part"/"hamstring part"), and emits one
   anchor per compartment instead of refusing the tie. Also fixed
   adductor_magnus (same mechanism) and, incidentally, restored
   adductor_longus_r/adductor_brevis_r/vastus_medialis_r's insertion
   anchors, which had silently had no anchor at all because femur_r had no
   standalone "linea aspera" landmark (only the compound "gluteal
   tuberosity/linea aspera" one) — added, mirroring femur_l. 226 → 238
   anchors. **Still open**: vastus_lateralis_r's origin resolves to
   "greater trochanter lateral facet (gluteus medius insertion)" — a
   facet meant for a different muscle — because its own text names both
   linea aspera AND greater trochanter and the latter scores higher; a
   single-compartment multi-site origin, not fixable by the mechanism
   above. Found while fixing the above, not investigated further.
11. A full anchor-plausibility audit (every one of the 238 anchors,
    cross-referenced against the landmark it resolved to and the muscle's
    own attachment text) found 4 mismatches of the same shape, including
    the previously-documented `vastus_lateralis_r/l` one (item 9 above).
    All 4 are now fixed. One (`plantar_interossei`) took a general rule
    fix; the other three took a named, explicit override instead, because
    every general fix attempted for them corrected the target case while
    silently breaking a different, previously-correct anchor elsewhere in
    the corpus (verified each time by diffing the full anchors.json, not
    by re-checking only the target case) — a symptom of `_match()`
    deciding between candidate landmarks without knowing which muscle it
    is placing. A `_match()` signature change to fix that properly (pass
    the owning muscle's id in, so it can prefer a candidate whose own
    attachment list names it) is still open as a design task, but three
    known-bad pairs did not need to wait for it:
    - **Fixed, general rule**: `plantar_interossei_r/l`'s insertion
      matched a landmark reserved for dorsal interossei ("digits 2-4")
      because the ordinal check only required the two digit-sets to
      *overlap* (`3,4,5` and `2,3,4` share the 4), not that one contain
      the other. Changed to require a subset relationship. Verified
      against the full 808-endpoint corpus: exactly those 2 anchors
      changed, nothing else.
    - **Fixed, named override** (`_KNOWN_MISMATCH_OVERRIDES` in
      `generate_anchors.py`): `rhomboid_minor_r/l` insertion,
      `extensor_carpi_ulnaris_r/l` origin, and `vastus_lateralis_r/l`
      origin. Each entry names the (muscle, role) pair and a substring
      unique to the correct landmark's name, checked before `_match()`
      runs at all. An assertion fires if `bones.json` ever changes such
      that the substring no longer resolves to exactly one landmark, so a
      stale override cannot silently point at the wrong thing (or
      nothing). Verified against the full corpus: exactly those 6 anchors
      changed, nothing else. 236 → 236 anchors (same count — these were
      already "resolved", just resolved wrong).

## 2026-09-06 session: viewer anchor points + large-scale clinical/anatomical data pass

- **Viewer**: `scripts/export_viewer_bundle.py` now resolves every muscle
  anchor (`data/rig/anchors.json`) whose bone has real geometry into a
  global-mm coordinate (`resolve_anchor_points()`), and
  `viewer/atlas_viewer.template.html`'s inspector shows a 📍 button next
  to Origin/Insertion that drops a 3D marker at that point. Verified
  pes anserinus (sartorius/gracilis/semitendinosus) converge on the
  identical point per side. Scope limit: only bones with real geometry
  (pelvis→ankle) resolve; compartment-filed anchors
  (flexor_hallucis_brevis, adductor_magnus) are skipped by muscle-id
  lookup, unaffected in their text fields.

- **Clinical injection-data pass** (~20 parallel background agents,
  each in an isolated git worktree/branch, merged sequentially into
  this branch): added `motor_endplate_zones`/`ultrasound_injection_approach`
  to essentially every muscle with real published literature —
  294/404 muscle files now carry one or both (up from ~230). Every
  gap left is a genuine "searched, not found" negative, not a skip.
  Real, sometimes mixed/negative evidence is recorded honestly
  (Achilles PRP, GTPS PRP, rotator cuff PRP all have contradicting
  trials cited side by side, not cherry-picked).

- **Tendon `prp_injection_approach` field** (new, `schema/tendon.schema.json`):
  30/51 tendon entities now carry it (up from 0). Includes a newly
  authored `gluteal_tendon_complex_r/l` entity (GTPS target, didn't
  exist as a tendon before) and `first_dorsal_compartment_r/l`
  (de Quervain's).

- **Anatomical completeness pass** (5 parallel agents auditing every
  ligament/tendon file against standard references): added real,
  previously-missing structures — lunotriquetral ligament, all of
  `data/ligaments/hand_ligaments.json` (new file: thumb MCP UCL/RCL,
  finger MCP/PIP complex), tibiofibular syndesmosis, tibialis
  posterior tendon (PTTD), fibularis tendon complex, 1st MTP plantar
  plate, MPFL, iliolumbar ligament, popliteofibular ligament,
  meniscofemoral ligaments, transverse ligament of the knee, zona
  orbicularis, superior transverse scapular + transverse humeral
  ligaments, pectoralis major tendon, quadrate ligament, intertransverse
  ligament, atlantoaxial membranes, lateral atlanto-occipital ligament,
  sternocostal ligament complex, digastric/omohyoid intermediate
  tendons. 91 ligament records now exist (up from 62), 51 tendon
  entities (up from 39). Nothing was force-added — several agents
  explicitly reported "audited, nothing missing" for files that were
  already complete (elbow ligaments, hip ligaments' base structures).

- **Trigger points + bursae** (new, from 8 user-uploaded clinical
  reference documents covering wrist/elbow/shoulder/hand-intrinsic/
  head-neck muscles — Gray's Anatomy + Travell & Simons + peer-reviewed
  biomechanics): new `trigger_points[]` field on `schema/muscle.schema.json`
  (referred-pain pattern, distinct from the injection-targeting fields)
  and a brand-new `schema/bursa.schema.json` + `data/bursae/` category
  (bursae didn't exist in this atlas at all before today). 161 muscle
  files now carry trigger_points; 33 bursae across 4 files
  (wrist/elbow/shoulder/head-neck). One real merge conflict handled:
  biceps/triceps brachii were independently covered by both the elbow
  and shoulder source documents (they cross both regions) — kept the
  more complete version, discarded the redundant duplicate.

- Every merge in this pass was verified with the full test suite
  (`149 passed`) before pushing. HEAD is `36234dc`.

## 2026-09-08: real bone/vessel geometry above the hip, first time ever

The repository owner widened this remote environment's network policy and
supplied a real CT case (TotalSegmentator v2.0.1, Zenodo record 10047292,
case `s1371`, CC BY 4.0) via the Hugging Face connector's metadata search
plus a direct upload of the case's segmentation masks. Full account in
`docs/GEOMETRY_SOURCES.md`'s "Stage 2, first subject" section — short
version: `scripts/merge_totalsegmentator_masks.py` →
`scripts/ingest_volume_geometry.py inspect/propose/convert` (already built,
never fed real input before now) produced real geometry for cervical/
thoracic/lumbar spine, all ribs, sternum, costal cartilage, clavicle,
scapula, humerus, and (unplanned) several great vessels. The small merged
label volume is checked in at `data/ct_sources/` so this is reproducible
without re-fetching anything. `scripts/export_viewer_bundle.py --subject`
is now repeatable to combine subjects, with the already-verified VH data
always winning on a collision (regression-verified: `--subject vhm_both`
alone still produces the prior exact 130-structure/283,720-triangle
bundle — a real bug, dedup collapsing one subject's own multi-part
entities like the 12 ribs sharing `ribs_l`, was caught and fixed on the
way). The viewer now tags every non-primary-subject structure with a
visible badge, per `docs/GEOMETRY_SOURCES.md`'s existing, explicit rule
against ever presenting two different real bodies as one continuous
skeleton — this is shown for comparison/checking, not fused.

**What it is not**: no unified skull entity to receive TotalSegmentator's
skull mask (atlas only has mandible + occipital), no forearm/hand bones
(not in TotalSegmentator's structure set at all), and no upper-limb/trunk/
neck **muscle** geometry (TotalSegmentator segments ~10 muscles total, all
already covered by VH). "Complete the upper body" is not accurate as a
description of this step — real bone and great-vessel geometry above the
hip, for the first time, is.

**Real anchor-placement errors found, not yet fixed** — running
`scripts/audit_landmarks_vs_geometry.py --subject ct_s1371` gave the
upper-body anchors their first-ever real geometry to check against, and
several disagree with it materially:
- `anchor_deltoid_r_origin` / `_l`: ~130 mm off its own muscle
- `anchor_subclavius_r_insertion` / `_l`: ~55 mm off
- `clavicle_r/l` acromial (lateral) end landmark: ~130 mm from the bone
  surface — likely the same root cause as the deltoid anchors (they share
  that end of the clavicle)
- distal-femur landmarks (medial epicondyle, condyles, patellar groove)
  show large "errors" that are a scan-coverage artifact, NOT a data bug:
  this CT case's femur mask is only 315 mm long (315 mm along its own
  fitted axis vs. the atlas's ~450 mm femur) — the scan's field of view
  ends around mid-thigh, so read those specific figures as scale, not
  placement, per the audit script's own caveat.

Next action on this thread: fix the deltoid/subclavius/clavicle anchors
against the new real geometry, the same way `vastus_lateralis_r`'s origin
was fixed earlier from the lower-limb audit — likely a landmark-matching
or authoring error in `data/skeleton/bones.json`'s clavicle landmarks
rather than in `generate_anchors.py` itself, since the femur/hip errors
that DO trace to `generate_anchors.py` bugs were already fixed this
session. Verify against the full anchor corpus before committing, per this
project's standing rule for any anchor-generation change.

## 2026-09-09: clavicle fix verified, second CT case (s0913) adopted as primary

Root cause of the deltoid/subclavius/clavicle errors above: `clavicle_r`/
`clavicle_l` landmarks in `data/skeleton/bones.json` used the femur's
axis convention (X = medial-lateral) on a bone whose long axis actually
runs along Y in local coordinates — clavicle is mediolateral along its
own long axis, not superoinferior, so the femur convention doesn't apply.
Fixed by remapping each landmark's `position_local_mm` from `[x, y, z]`
to `[y, -abs(x), z]` (verified against femur_l/femur_r's stored values
first — an initial `[y, -x, z]` attempt gave the left clavicle a positive
Y, inconsistent with femur's non-side-flipping Y convention, and was
reverted before committing). Result: the acromial-end landmark went from
`[150.0,-10.0,-8.0]`/`[-150.0,-10.0,-8.0]` (r/l) to a uniform
`[-10.0,-150.0,-8.0]` for both sides. `scripts/generate_anchors.py`
re-run and diffed against the pre-fix baseline: exactly 4 anchors changed
(`anchor_deltoid_r/l_origin`, `anchor_subclavius_r/l_insertion`), 236
total anchors unchanged in count. `tests/test_symmetry.py` updated with a
`LONG_AXIS_IS_MEDIOLATERAL = {"clavicle_r", "clavicle_l"}` exception set
so its mirror-consistency checks use axis 1 (Y) for these two bones
instead of axis 0 (X). Re-running the audit against `ct_s1371` after the
fix: clavicle errors dropped from ~130 mm to ~10-60 mm residual (see
below for why residual error remains).

A second CT case, `s0913` (same source, same license), was then ingested
through the identical pipeline and compared against `s1371`: the two
cases cover the exact same set of atlas ids (verified by a direct
set-diff, not assumed), so there is no complementary value in keeping
both in the default combined bundle. s0913 is the better specimen on
every axis that differs — full C1-C7 vs C6-C7-only cervical spine, a
138-143 mm clavicle vs 101-114 mm (closer to the ~150 mm the
hand-authored landmarks assume), tighter femoral-head sphere fit (rms
0.6 mm vs 0.8-1.8 mm), and a materially better post-fix landmark audit
(7-19 mm residual vs s1371's 10-60 mm — the remaining error is
consistent with normal anatomical variation in clavicle length/curvature
between real specimens, not a further bug). The default combined bundle
is now `--subject vhm_both --subject ct_s0913` (197 structures). s1371's
merged label volume stays committed under `data/ct_sources/` for
provenance; it's simply not part of the shipped bundle. Full detail in
`docs/GEOMETRY_SOURCES.md`'s "Stage 2, second subject" section.

Also completed this window, per the repository owner's "all of the
above" instruction: `schema/bursa.schema.json` (new) and a
`trigger_points[]` field on `schema/muscle.schema.json` (new), populated
via 3 background research agents (PubMed/WebSearch-sourced, no reference
document available for these regions) covering hip/thigh (25 muscles ×2
sides + 8 bursae), deep trunk/pelvic floor (11 muscle types ×2 sides,
several honest negatives for perineal/intercostal muscles), and leg/foot
(21 muscles ×2 sides + 4 bursae, 3 honest negatives). Combined with the
head/neck and upper-limb trigger-point work from earlier sessions, the
corpus now stands at 271 muscle files carrying `trigger_points` and 45
bursae total.

**Still genuinely open** (confirmed by direct file-level checks against
this session's real ingests, not assumed): pelvic floor **muscles**
already have literature-based clinical data added above, but still no
segmented 3D geometry (TotalSegmentator doesn't carry them); foot
intrinsics and fibularis brevis/tertius likewise have clinical data but
no mesh; forearm/hand bones and all upper-limb muscles have neither —
TotalSegmentator's structure set does not include them at all, so no
number of additional whole-body CT cases from this same source will
close these gaps. Closing them needs a different segmented source
entirely (a hand/wrist-specific dataset, or a muscle-segmentation model
run against raw CT/MRI).

## Open, not literature-fixable

- **Partially unblocked 2026-09-08, second case adopted 2026-09-09** (see
  above): real bone and great-vessel geometry above the hip now exists,
  from two independently-checked CT cases (s1371, s0913; s0913 is the
  default). Confirmed via direct diffing of both cases' structure sets:
  still genuinely missing and not fixable by more cases from this same
  source — a unified skull, forearm/hand bones, and every upper-limb/
  trunk/neck **muscle**, plus (checked explicitly this window) pelvic
  floor muscles, foot intrinsics, and fibularis brevis/tertius as
  meshes — none of which TotalSegmentator segments at all. Getting those
  needs a different segmented source (a hand/wrist-specific dataset, a
  muscle-segmentation model run against raw CT/MRI).
- Flagged, not yet done: a `gluteus_medius/minimus` **muscle's own**
  motor-point/BoNT injection data search came back empty (its
  *tendon* now has PRP data — different structure, different
  literature) — a legitimate negative finding, not an oversight.
- Trigger-point/bursa pass now extended to hip/thigh, deep trunk/pelvic
  floor, and leg/foot this window (see above); upper-limb and head/neck
  were already covered from earlier sessions. No remaining muscle region
  is unaddressed for this specific data type.

## 2026-09-09: "other sources" check — negative result

Per the repository owner's request, checked for any other reachable
source that could supply the still-missing geometry (pelvic floor, foot
intrinsics, fibularis brevis/tertius, forearm/hand bones, upper-limb
muscles):

- **Google Drive "library" folder** (`1znmXUIxT-7sIEl2zQNQi2lxxxaclA3ZU`):
  re-listed directly (not assumed from memory) — still contains only
  `Sobotta Anatomy Atlas (General And Musculoskeletal).pdf`, which this
  project cannot use as a geometry or data source (copyrighted atlas
  imagery, not a licensed segmented dataset). No change from before.
- **Hugging Face** (`hub_repo_search` and `hf_fs search`, multiple
  phrasings: hand/wrist/carpal bone segmentation, foot bone/intrinsic
  muscle segmentation, upper-limb/shoulder/forearm muscle segmentation,
  pelvic floor MRI segmentation): no matching dataset found. The one
  concrete near-hit, `YongchengYAO/TotalSegmentator-MR-Lite` (the MRI
  counterpart to the CT release already in use), was checked directly —
  its 50-structure label set is the same bones and the same ~10 muscles
  as the CT version (humerus/scapula/clavicle/femur/hip +
  glutei/autochthon/iliopsoas), so it adds nothing new; it is also
  CC BY-NC-SA (non-commercial), which would conflict with this project's
  proprietary/commercial licensing even if it did.

**Conclusion at that point**: no reachable *ingestible* source fills these
gaps. Superseded below — one source that structurally *would* fill them
was found and confirmed, then confirmed disqualified for a reason already
on record in this project.

## 2026-09-09 (same day, continued): BodyParts3D/Z-Anatomy re-confirmed, still disqualified; BioDigital/Zygote/Gray's checked

The repository owner named specific sources to check more deeply:
Z-Anatomy, Visible Human, Zenodo, BioDigital, Zygote Body, Gray's Anatomy.

**Z-Anatomy / BodyParts3D — actually would fill every remaining gap.**
`docs/GEOMETRY_SOURCES.md` already had a "Why Z-Anatomy was rejected"
section from earlier in the project (CC BY-SA 4.0 share-alike, disqualified
outright per this repo's own rule, `PROJECT_STATE.md` line 12: "no CC BY-SA
source may enter it"). To check whether that rejection still made sense
against the current specific gap list, its upstream source, BodyParts3D
(DBCLS, CC BY-SA 2.1 Japan), was located and inspected directly — GitHub
mirror `Kevin-Mattheus-Moerman/BodyParts3D`, reachable via this sandbox's
anonymous git-clone proxy even though the original `dbarchive.biosciencedbc.jp`
host is not. Cloned (934 STL files, single male body, FMA-ontology-named,
~1.4 GB), then grepped its part list directly rather than trusting memory:
it has named, meshed entries for **all** of pelvic floor (levator ani,
pubococcygeus, puborectalis, iliococcygeus, coccygeus — confirmed present
as actual `.stl` files, not just ontology entries), foot intrinsics
(abductor hallucis, flexor hallucis/digitorum brevis, lumbricals,
interossei), fibularis brevis/tertius, forearm bones (radius, ulna),
hand bones (carpals, metacarpals, phalanges), hand intrinsics (lumbricals,
interossei of the hand), and the full upper-limb muscle set (deltoid,
biceps brachii, pronator teres, etc. — all sided, all present). This is a
structurally complete answer to every open geometry gap this project has.

**It is still disqualified, for the reason already documented**: the
license is CC BY-SA (Japan 2.1 for the raw data, 4.0 for Z-Anatomy's own
re-packaging) — share-alike, which forces any distributed derivative to
carry the same license and forbids adding restrictions. That is exactly
what `docs/GEOMETRY_SOURCES.md`'s existing "Why Z-Anatomy was rejected"
section and `PROJECT_STATE.md`'s standing rule both already rule out for
a proprietary, sellable product. Confirming this in detail didn't change
the answer, but it does mean the gap is not "no source exists" — a
complete, freely-downloadable source exists and is simply incompatible
with the licensing model this project has chosen. The clone was deleted
after inspection (not committed, not kept on disk); only its small
plain-text part list and LICENSE_content were saved to this session's
scratchpad for reference, not the repo.

**BioDigital Human**: ~14,000 structures, but the free and paid tiers are
a hosted viewer/API (embed their viewer, or call their API for interactive
views) — not a source of exportable, ownable mesh files. There is no
tier, free or paid, that hands over raw geometry for inclusion in a
separately-distributed dataset; you license access to their viewer, not
the meshes themselves. Structurally incompatible with this project's
architecture (own mesh files, own manifest/ingest pipeline) regardless of
what tier is purchased.

**Zygote Body / Zygote Media Group**: real exportable mesh geometry (MA,
3DS, C4D, LWO, XSI), commercial, purchased per-model (~$200+) or as a
software/IP license with royalties; the full collection is ~$21-25k.
This is a genuine option structurally — owned meshes, standard proprietary
commercial licensing, no share-alike problem — but it costs real money and
is a purchasing decision for the repository owner, not something
resolvable from here.

**Gray's Anatomy (1918, 20th US edition)**: confirmed public domain (US
copyright expired), but it is text and 2D engraved plates only — Bartleby,
Wikimedia Commons, and Internet Archive all host the same 2D content.
No 3D geometry exists from this source under any circumstance; it is
already the kind of descriptive-literature source this project cites for
facts, not a candidate for filling a mesh gap.

**Zenodo**: not itself a geometry source, a repository host — TotalSegmentator's
files live there and are already ingested via direct upload (Zenodo itself
stays unreachable from this sandbox's network policy, as established
earlier). No new content found there beyond what's already in use.

## 2026-09-09 (same day, continued again): BHaM — a real, license-unverified forearm/wrist lead

Pushing the search past the named-source list surfaced one genuinely new,
not-previously-known candidate: **BHaM (Biomechanics Hand Modeling
database)**, Diaz et al., *Scientific Data* 2026, DOI
`10.1038/s41597-026-06939-4` (PMID 41807417, PMC13111597 — fetched and
read directly via the PubMed connector, not just its abstract). A subset
of 15 living subjects received 3T MRI from shoulder to wrist, and
"forearm muscles and bones were manually segmented in 3D Slicer by a
single, trained researcher." The dataset is hosted on Kaggle, DOI
`10.34740/kaggle/ds/7895310`.

**Unverified, and here's exactly why**: `kaggle.com` and `nature.com` are
both unreachable from this sandbox's network policy (confirmed by direct
`curl`/`WebFetch` attempts, both `EGRESS_BLOCKED`/`connect_rejected`) —
the PubMed connector's full text doesn't include the paper's data-file
table, so it's not established from here whether Kaggle actually hosts
the raw segmentation files (NRRD/NIfTI masks) or only derived numeric
summaries (muscle volumes), nor is the dataset's exact license confirmed
(Kaggle license metadata isn't in the paper text). Even in the best case
this only covers forearm muscles/bones (not hand intrinsics, not
shoulder/upper-arm muscles, not pelvic floor or foot) and n=15.

**Next action, if pursued**: this needs a human to open
`https://www.kaggle.com/datasets/maximilliantdiaz/bham-biomechanics-hand-modeling-dataset`,
confirm the license and check whether segmentation files are actually
included (not just summary CSVs), and if so download and upload it here
the same way the TotalSegmentator CT case was supplied this session. Not
pursued further without that confirmation — no point ingesting against
an unverified license after this project's own standing rule about
checking licenses before, not after.

**Net conclusion**: the pelvic-floor/foot-intrinsic/fibularis/forearm-hand/
upper-limb geometry gap has three remaining paths now, all requiring a
decision or an action from the repository owner rather than more
searching from here: (0) check whether BHaM's Kaggle listing is actually
usable (forearm/wrist only, license unverified), (1) revisit
the no-CC-BY-SA-source rule for a specific, scoped exception, which would
obligate share-alike licensing on whatever uses that geometry, or
(2) purchase Zygote (or an equivalent commercial, ownable-license) content
for the missing regions. No amount of further free-source searching will
change this — the search space for freely-licensed, ownable, ingestible
geometry for these specific structures has now been covered.

## 2026-09-09 (continued, "search deeper"): four uploaded papers + a systematic sweep

**The four PDFs the owner uploaded** (all read in full, `pymupdf`): BHaM
(Diaz 2026, doi:10.1038/s41597-026-06939-4) — the paper states outright
"The original DICOM files and segmentations are not published due to
data privacy requirements"; only `MuscleVolumeMeasurements.csv` (in vivo
volumes of 18 forearm muscles + radius/ulna, n=15) ships. No geometry.
KIMHu (Hernández 2023), Lucchetti 2025, MyoKi (Andreas 2025): motion
capture / EMG / RGB-D datasets — no anatomy geometry of any kind. All four
closed as geometry sources; BHaM's volume CSV is a legitimate literature
reference for forearm muscle volumes if ever needed.

**Systematic sweep** (PubMed connector — which works from this sandbox —
plus `modenaxe/awesome-biomechanics`, the curated public index of
biomechanics datasets, fetched from GitHub): what exists, with license,
for each remaining gap. Every host below (Zenodo, MorphoSource, OSF,
figshare, Kaggle, Nature, Wiley, PeerJ, KU Leuven) is **blocked from this
sandbox**, so every one of these needs the owner to download and upload
here, exactly as the CT case was supplied.

| Gap | Source | Content | License | Status |
|---|---|---|---|---|
| **Skull (unified), head/neck muscles, trunk wall muscles** | **TotalSegmentator free tasks** run on s0913's own raw CT (`ct.nii.gz` in the Zenodo zip, CC BY 4.0) | `craniofacial_structures` (skull, mandible, teeth), `head_muscles` (masseter, temporalis, pterygoids, digastric, tongue), `headneck_muscles` (SCM, trapezius, platysma, levator scapulae, 3 scalenes, sternothyroid, thyrohyoid, prevertebral, 3 pharyngeal constrictors), `headneck_bones_vessels` (hyoid, thyroid/cricoid cartilage, ICA, IJV), `abdominal_muscles` (pec major, rectus abdominis, serratus anterior, lat dorsi, obliques, erector spinae, transversospinalis, psoas, QL), `oculomotor_muscles` | Apache-2.0 — README: "Openly available for any usage" | **Best option: same specimen, consistent frame, no new license.** TotalSegmentator installed here (pypi reachable, weights host github.com/…/releases reachable, CPU-only, 4 cores/15 GB — fine with `--fast`). Blocked only on `s0913/ct.nii.gz` not having been uploaded. s0913 FOV confirmed head→mid-thigh (skull+brain masks present, 697 mm). Atlas already has entities for nearly all of these muscles (verified by id grep). |
| Forearm/hand bones, shoulder/thigh muscle groups | TotalSegmentator `appendicular_bones`, `thigh_shoulder_muscles` | radius/ulna/carpals/metacarpals/phalanges; deltoid, rotator cuff, triceps, quadriceps… | **Licensed**: free for non-commercial only, commercial license from jakob.wasserthal@usb.ch | Purchase decision. Note s0913 has no hands in FOV anyway; meta.csv has one `ct upper limb both` case (s0035, trauma thorax) and 50 CTA neck→leg runoff cases (feet likely in FOV, e.g. s0367 46 m, s0804 44 f, no pathology). |
| **Forearm + hand muscles, bones, cartilage (cadaver)** | Kerkhof, van Leeuwen, Vereecke 2018, *J Anat* doi:10.1111/joa.12877 — "The digital human forearm and hand" | 7T MRI + CT of one un-embalmed arm; STL of bones, cartilage, muscles, muscle paths; dissection PCSA/pennation/volumes | **Unverified** — MorphoSource project P419 (media 21064); MorphoSource licenses are per-item (CC0 / CC BY / CC BY-NC all common) | Owner must open morphosource.org P419 and read the license line. If CC BY or CC0 → download and upload. If NC → out. |
| **Intrinsic hand muscles, tendons, neurovasculature (whole hand)** | Steer … Holliday 2026, *Anat Rec* doi:10.1002/ar.70304 — DiceCT hand atlas, 48.8 µm | PLY of every intrinsic muscle, tendon, bone, nerve, vessel, retinaculum; Blender/.usdc scene | **Unverified** — OSF `osf.io/avq7d` (raw scan on MorphoSource media 000850386, project 000868567) | Owner must open the OSF page and read the license. The single most complete hand-intrinsic geometry found anywhere. |
| Hand muscle attachments + MRI bone/hand-muscle geometry | Havelková et al. 2020, Zenodo 3954024 (basis of the AnyBody RUHM hand model) | 16 cadavers dissected for attachment maps; MRI of one cadaveric upper limb reconstructed for all bones and hand muscles | **CC BY** (confirmed) | Download + upload; check the file list contains meshes, not only tables. |
| **Foot bones** (talus, calcaneus, navicular, cuboid, cuneiforms, metatarsals) | Grant et al. 2019/2020, PeerJ doi:10.7717/peerj.8397, Zenodo 3464747 | manually segmented STL from MRI, 34 subjects | **CC BY** (confirmed) | Download + upload. The atlas currently has NO tarsal entities at all (`bones.json` carries only metatarsals/phalanges for the foot) — entities need authoring too. |
| Talus/tibia/fibula | Lenz et al. 2021, Sci Rep, Zenodo 4274217 | PLY, weight-bearing CT, 27 subjects | **CC0** (confirmed) | Download + upload if a second talus source is wanted. |
| Foot intrinsic muscles | — | nothing found: no open segmented dataset exists (DiceCT foot not published; VH-DU release stops at the ankle) | — | Still open. |
| Pelvic floor muscles (adult) | — | only a *foetal* pelvic-floor micro-CT (PLOS One 2025) and clinical retrospective series with unpublished masks | — | Still open. |

**Rejected in this sweep, with reason**: OpenHands finger-bone SSM (CC BY-SA
→ share-alike, and synthetic mean shapes); BoneDat pelvis/L4-L5 (CC
BY-NC-ND); VSDFullBodyBoneModels lower-body bones incl. feet (underlying
SMIR/VSDFullBody CTs are CC BY-NC-SA); SPL Head & Neck atlas (Slicer
license on the labels, but built on the OsiriX MANIX dataset, whose terms
are research/teaching only, no commercial use); MedShapeNet (CC BY 4.0
umbrella, but its 23 source datasets contain no hand/foot/limb-muscle
shapes — checked the full source list); MUG500+ skulls (figshare, CC0 by
default — superseded by getting the skull from s0913 itself); Visible
Korean Human (642 surface models, access by request, no stated open
license); tongue-muscle MRI dataset (OSF, real but tongue only — the
`head_muscles` task gives tongue from s0913 anyway).

**Sandbox capability discovered**: PubMed full text works via the connector
even though every NLM/Nature/Wiley host is blocked to `curl`; pypi.org,
files.pythonhosted.org and github.com release downloads are reachable.
That is what makes the TotalSegmentator route runnable here.

## 2026-09-10: network opened; raw CT in hand; TotalSegmentator free tasks running here

**What changed**: the owner set this environment's network access to Custom
with zenodo.org, huggingface.co, *.hf.co, osf.io, morphosource.org, figshare,
kaggle allowed. It applied to the running session. Direct consequences,
all verified: the 23.6 GB Zenodo zip (record 10047292, CC BY 4.0) serves
HTTP byte ranges, so single cases are pulled out of it in seconds
(`scratchpad/zenodo_zip/rangezip.py`: an HTTP-Range file object under
`zipfile`; central directory = 147,361 entries). Zenodo/OSF/MorphoSource
APIs answer. No more chat uploads needed for anything on those hosts.

**s0913 raw CT** arrived first as 8 x 10 MiB chat parts (`ct.nii`, 77,674,882
bytes, verified against the NIfTI header and byte-identical affine with the
label volume). **Correction of an earlier claim**: s0913 has NO head -- its
`skull.nii.gz`/`brain.nii.gz`/C1/C2 masks exist but are all-zero; the scan
tops out at C7 (meta.csv: `ct neck-thorax-abdomen-pelvis`). File presence
was mistaken for content. Every neck muscle the `headneck_muscles` task
finds on it is cut at the top slice (SCM, scalenes, levator scapulae,
sternothyroid, prevertebral all end at z=464); only trapezius is whole.
`abdominal_muscles` is the task that pays off on s0913.

**The dataset crops images unpredictably**, so field of view must be probed
before pulling a CT: `scratchpad/zenodo_zip/probe_fov.py` reads only the
small `skull`/`C1`/`C4`/`C7`/`T1`/`T4`/`brain` masks of every healthy adult
case of the head/neck/polytrauma/whole-body study types (118 cases) and
reports voxel counts, z-ranges and edge contact (`probe_fov.tsv`). s0364
("thorax-neck") turned out to start at T1; s0460 (head CTA) has the skull
touching both edges. **Chosen instead: s1159** -- 47 y female, `ct
polytrauma`, `no_pathology`, 537 slices = 806 mm, vertex to hip: skull with
margin (z 420-530 of 536), C1 through the sacrum, both humeri, femoral
heads clipped at the bottom edge. One body from vertex to hip.

**Placement of s1159**: its femoral heads are clipped at the bottom edge
(top ~24 mm of each head in the field of view), yet the standard
sphere fit still converges cleanly -- right r=22.1 mm rms 0.49 mm, left
r=23.3 mm rms 0.53 mm -- so s1159 is placed by the same fitted origin as
every other CT subject (`--origin '-14.573,103.145,200.400'`). A
translation-only sacrum-centroid alignment tried first landed 8 mm (X) and
17 mm (Y) away from the fit, which is a useful measure of how wrong that
convention would have been; it is not used. The clipped femur stubs are
nulled in the s1159 mapping so they never claim the femur ids from the VH
data, and s0913's 8-slice C7 stub is nulled so s1159's complete cervical
spine is the one shown.

**Running TotalSegmentator here, CPU-only (4 cores, 15 GB)**: pypi and the
GitHub release weights host are reachable; installed v2.18.0; free-task
weights pre-fetched. Two real failure modes found and fixed:
1. `headneck_bones_vessels` and `abdominal_muscles` use 0.75 mm models; on a
   trunk crop (578x402x508 voxels x 22 classes of softmax) the worker is
   OOM-killed at ~12.4 GB (kernel log: `Memory cgroup out of memory: Killed
   process ... TotalSegmentato`) and the parent waits on a futex forever
   -- it looks "stuck", not failed. Fix: `scratchpad/tools/ts_chunked.py`
   runs a task on overlapping z-chunks (96 slices, 16 overlap) of the
   z-range that matters (from the case's own vertebra/skull masks) and
   stitches by index; each chunk keeps its own affine. Peak ~5.5 GB.
2. A stale `inspect.py` in the scratchpad shadowed the stdlib module for any
   script run from that directory; renamed.
The head tasks on s0913 correctly return "Crop is empty".

**Label maps**: `mappings/totalsegmentator_<task>_labels.json` for the six
Apache-2.0 tasks, fully reviewed (see commit). `propose`/`convert` were
exercised on the s0913 `headneck_muscles` multilabel output (17 curated,
3 no-entity, 54,944 vertices) -- the multilabel path works unchanged.
New composite bone `cranium` receives the whole-skull mask.

**Source verdicts from the opened network** (all checked on the record/API,
not the paper): Grant 2019 foot bones -- CC BY 4.0, 125 ASCII STLs, mm, but
**each bone sits in its own SSM-aligned frame** (calcaneus centroids
~[18,4,38] in every subject, talus ~[6,0,6]): shapes for statistics, not an
articulated foot; assembling one needs a registration to the VH ankle that
does not exist yet. Lenz 2021 tibia/fibula/talus -- CC0 (LICENSE file in
the GitHub release). Havelkova 2020 -- CC BY, but the files are muscle
*paths* (polylines) and tables, no bone or muscle meshes. Kerkhof 2018
forearm/hand on MorphoSource -- `copyright_statement`
rightsstatements.org **InC-EDU** (in copyright, educational use permitted),
"CommercialUsePermitted" flag notwithstanding, derivatives must be archived
on MorphoSource: not usable in a sellable product without the author's
written licence. Steer 2026 DiceCT hand on OSF `avq7d` -- 45 PLYs (every
intrinsic muscle, tendons, nerves, all bones in one mesh, palmar
aponeurosis) plus the 563 MB whole-hand OBJ, **no licence set on the node**
("for review for Anatomical Record"): all rights reserved by default;
needs a written licence from the University of Missouri authors (Steer /
Holliday) before any use. Both hand sources are therefore a
correspondence task for the owner, not a download.

## 2026-09-10, end of day: s1159 is one body from vertex to hip, with muscles

Final bundle (viewer v8, 271 structures, 640k triangles): `vhm_both` +
the s1159 family (`ct_s1159` bones/vessels, `_head` skull+mandible,
`_headm` masseter/temporalis/pterygoids/digastric, `_neck` SCM, scalenes,
levator scapulae, sternothyroid, thyrohyoid, platysma, trapezius,
`_neckbv` hyoid/ICA/IJV/zygomatic arch/styloid, `_orbit` six extraocular
muscles + levator palpebrae + optic nerve, `_abd` pectoralis major, rectus
abdominis, serratus anterior, latissimus dorsi, obliques, quadratus
lumborum). s0913 is retired from the shipped bundle (its files and
`ct_s0913_abd` stay for comparison; identical structure set, no head).

Things learned the hard way today, all fixed and all verified on the data:
the neck muscles were first cut at z=347 by MY crop, not the scan (they
reach the manubrium at z=329); re-run with the crop extended to T4-20 in
three chunks. Trapezius spans both the neck task and the trunk task, so the
trunk part is unioned into the neck volume before conversion and the trunk
mapping nulls it -- one mesh, occiput to ~T11. The craniofacial output is
real (952k voxels; I misread a truncated log line as 95). Task label
volumes and the per-subject mapping decisions are committed under
`data/ct_sources/task_outputs/` and `subject_mappings/` (4.6 MB) so the
conversion is reproducible without re-running the models.

Not yet done with this material: (a) the anchor/landmark audit
(`audit_landmarks_vs_geometry.py`) has not been run against s1159 -- its
head, neck and trunk muscles are the first geometry many upper-body
anchors could ever be checked against; (b) `thyrohyoid_left` carries a
small stray fragment at z=295 (mislabel), untouched; (c) the pharyngeal
constrictors and prevertebral/tongue/erector masses are deliberately
unmapped (atlas finer than the mask); (d) laryngeal cartilages, eyeballs
and teeth have no atlas entities -- candidates for authoring.

## 2026-09-10, later: first audit of upper-body anchors against s1159 -- scapula fixed

`audit_landmarks_vs_geometry.py --subject ct_s1159_all` (a merged subject of
s1159's bones plus all its task-derived muscles; built ad hoc, see
`scratchpad`) gave the upper-body anchors their first check against muscle
and bone geometry in the same body. Findings, separated by cause:

- **Scapula (real authoring error, fixed)**: all ten landmarks on both sides
  were 37-40 mm median / up to 115 mm off the bone. Two causes. (1) The
  audit's scapula frame was built from the medial border and ended up with
  Y pointing at the glenoid and Z pointing DOWN -- no hand-authored value
  could ever be right in it; changed to the anatomical-position convention
  (X right, Y up, Z anterior) at the glenoid, as the hip bone and sternum
  already use. (2) The values themselves drew the blade flat and twice too
  big (medial border 140 mm medial, inferior angle 140 mm down, both only
  40 mm posterior; measured on s1159: 65 mm medial / 95 mm down / 65-90 mm
  posterior, because the glenoid faces anterolaterally and the blade wraps
  the ribs). Rewritten from the measured mesh, each side from its own
  scapula, rounded to 5 mm. Result: median 1.5 mm (r) / 1.9 mm (l).
  Exactly 22 anchors changed (rotator cuff origins, biceps and triceps
  long/short heads, coracobrachialis, pectoralis minor, rhomboid minor,
  teres major, trapezius insertion), 236 total unchanged; "anchor to own
  bone" median 40.0 -> 4.6 mm; trapezius insertion off-to-side 103 -> 22 mm.
- **Humerus (field-of-view artefact, not fixed, correctly)**: the left arm
  is cut by the image's lateral edge and the right elbow is cut flat, so the
  fitted long axis and the distal landmarks (epicondyles, capitulum,
  trochlea, and the six forearm-muscle origins sharing them) read 35-88 mm
  "off". Nothing to fix; a case with the elbows in the field would settle it.
- **Latissimus insertion (mask artefact)**: the trunk task stops at T4, so
  the mask has no tendon to the humerus; the anchor is correctly placed
  past the mask's end.
- Clavicle: 4-5 mm median on this second specimen too -- the earlier fix
  holds.

**Mandible, same session**: the mandible had descriptive landmarks only
(no numbers, so no jaw-muscle anchor could ever resolve), and
`generate_anchors.py` gave a left-side muscle on a midline bone the same
coordinates as the right. Fixed both: condylar process, coronoid process,
angle and digastric fossa measured on s1159's mandible mesh (right/left
averaged after mirroring because that head is turned), authored for the
right side; the generator now mirrors X for `_l` owners on midline bones;
the audit gained a menton-origin mandible frame. Audit: 4.9 mm median.
Eight new anchors (masseter, temporalis, medial pterygoid, digastric
insertions, both sides), zero existing anchors changed. Masseter is a
first-line botulinum-toxin target, so this one matters clinically.

**Sternum and hyoid, same session**: numeric landmarks measured on s1159
(jugular notch frame already existed; a hyoid frame at the anterior
midline point of the body was added). Audit: sternum 2.9 mm, hyoid 0.9 mm.
This exposed a matcher bug in `generate_anchors.py`: the gate took the
first two tokens of the WHOLE landmark name, so a one-word site such as
"manubrium (sternocleidomastoid, ...)" demanded that "sternocleidomastoid"
appear in the muscle's text and rejected every plain "manubrium" origin.
The gate now admits a candidate if either the whole-name rule or the
site-only rule holds (a strict superset of the old behaviour, verified:
46 anchors gained across sternum, hyoid, humerus, ulna, scapula, carpals,
tarsals, metacarpals; zero existing anchors changed, zero removed). The
manubrium was then split into anterior (SCM, pec major) and posterior
(sternohyoid, sternothyroid) surfaces -- the infrahyoids arise from the
back of the bone, ~17 mm behind the front -- with the surface named inside
the attachment list so the matcher's tie-break, not its gate, decides;
sternohyoid's own text now says "posterior surface". Anchors: 300.
Remaining "off to the side" figures on s1159 (serratus anterior and
latissimus insertions, pectoralis major insertion, sternothyroid origin)
are all cases where the T4-L4 trunk mask or the neck mask does not
contain the end of the muscle that reaches the anchor -- mask limits, not
anchor errors, and recorded as such.

## 2026-09-10, evening: "upper muscles are partial and blurred" -- what is fixable and what is not

**Blurred -- fixed.** The CT subjects were surfaced by marching cubes
straight off 1.5 mm binary masks (a voxel staircase), then decimated to
the 1,800-triangle muscle budget; beside the 0.33 mm Visible Human
meshes that reads as a smeared block. `engine/volume_ingest.mask_surface`
now takes `smooth` (Gaussian sigma in voxels, applied to the mask copy the
iso-surface is drawn from -- the label volume is never touched, no voxel
changes owner; default 0 keeps the old behaviour and the 23 volume-ingest
tests pass unchanged); `convert --smooth 1.0` is used for every CT
subject and recorded in the manifest. Viewer budgets: muscle 1,800 ->
2,600 triangles, per-entity overrides for the composite skull (14,000)
and mandible (6,000).

**Partial -- verified NOT fixable with the free tasks.** The obvious
suspicion was that my z-crop (T3 + 15 slices) cut pectoralis major,
serratus anterior and latissimus dorsi. Checked directly on both s0913
and s1159: no trunk-wall muscle label touches the crop's top slice; the
`abdominal_muscles` model simply stops there, because its training labels
are confined to T4-L4. The clavicular head of pectoralis major, the upper
serratus digitations and the humeral part of latissimus are outside what
this model knows, and no re-run recovers them. Deltoid, rotator cuff,
biceps, triceps, coracobrachialis, pectoralis minor, rhomboids, forearm
and hand muscles are not produced by any free task. The routes that exist
are already on record: the licensed `thigh_shoulder_muscles` task
(commercial licence from University Hospital Basel; gives deltoid,
supraspinatus, infraspinatus, subscapularis, coracobrachialis, teres
major, pectoralis minor, full serratus anterior, triceps -- still not
biceps or pectoralis major's clavicular head), or a licensed cadaver
dataset (Kerkhof, Steer). "Complete" for the upper limb is a licence
decision, not more computation.

**Recheck, lower limb**: audit on `vhm_both` after today's generator and
matcher changes -- 126 landmarks median 1.2 mm, all within 15 mm; 150
anchors to their own bone median 0.9 mm, none beyond 20 mm. Identical to
the baseline, as the zero-changed anchor diffs predicted.

## 2026-09-10, night: the Visible Human male's own CT found on IDC -- head, neck, torso, pelvis AND arms

User: "MUST HAVE MUCH MORE ACCURATE HEAD, NECK, TORSO AND PELVIS. YOU DON'T
HAVE UPPER LIMBS AT ALL! LOOK IN DROPBOX AND IN THE NET ASAP! ... COMPLETE
ALL TENDONS AND LIGAMENTS AND NERVES."

- Dropbox `/claude`: Steer OSF hand archive (avq7d, 289 MB), Wiley supinfo
  zip (183 MB), Sobotta PDF parts. Unchanged verdict: no licence on the
  Steer data, Sobotta is copyright -- neither may be ingested.
- Net: the whole NLM Visible Human Project is on the Imaging Data Commons
  GCS mirror (`idc-open-data`, anonymous), public domain. 39 series indexed
  (`scratchpad/vh_idc/series_index.json`). VHP-M frozen CT = 3 blocks:
  head->proximal femur with both arms (844 slices), pelvis->ankle (809),
  feet (224). VHP-F "Normal" CT (985 slices, head->mid-thigh) also there.
- Built `scratchpad/vh_idc/stack.py`: physical-coordinate stacking of the
  mixed-FOV series (dcm2niix mis-scales the 0.527 mm head slices).
  Volumes: `vh_idc/nii/vhm_torso_0937.nii.gz` (512x512x844),
  `vhm_headneck_0527.nii.gz` (512x512x381), legs `vhm_frozen_3.nii.gz`.
- Running (CPU, chunked): `total` on the torso, then headneck_muscles,
  headneck_bones_vessels, abdominal_muscles, craniofacial, head_muscles,
  oculomotor; then `total` on the pelvis block of the legs series for the
  femoral-head origin; `arm_bones.py` = HU>=200 components outside `total`
  bones for radius/ulna/hand bones. Logs `scratchpad/vhm_ts/*.log`.
  Subject ids reserved in the viewer: `ct_vhm`, `ct_vhm_{neck,neckbv,abd,
  head,headm,orbit,arm}`.
- Chunk 1 of `total` (pelvis, z 0-229): 42 labels, hip/sacrum/L1-S1/
  gluteals/iliopsoas present; **femur absent** (heads sit at the very edge
  of the block), hence the legs-block run for the origin.
- `total` on the frozen torso: 110 labels; C1-S1, all 24 ribs, sternum,
  both clavicles/scapulae/humeri, hips, sacrum, skull, gluteals, iliopsoas,
  autochthon all present and, on coronal/sagittal projection, in place.
  Vessels are fragments (aorta 21 cm3 vs 164 cm3 on s1159: no contrast,
  frozen) -> nulled in `ct_vhm`. `headneck_muscles`: SCM 57/61 cm3,
  trapezius 172/182, levator scapulae 43/35, scalenes, prevertebral --
  plausible; platysma absent (nulled). `headneck_bones_vessels`: thyroid
  8.6, cricoid 4.1, hyoid 1.9 cm3; styloids and vessels fragments (nulled).
  **`abdominal_muscles` fails on the frozen cadaver**: pectoralis major
  14/96 cm3 (s1159: 171/173), rectus abdominis 0.6/13 (100/99), latissimus
  27/7 (183/163), obliques 6-9 (100-114), erector spinae 675 (403, i.e.
  leaking into fat). Not shipped from this body; the trunk muscles stay
  s1159's, badged as such.
- Arms: the 480 mm reconstruction FOV clips both arms around the elbow
  (seen on axial slices: the arm leaves the image laterally, and the FOV
  edge is a bright cupping band ~20 columns wide that thresholds like
  bone). `scripts/segment_arm_bones_vhm.py`: HU>=200 opened once, minus
  `total` labels and the edge columns; markers = eroded `total` humerus,
  the two largest HU>=800 forearm fragments (overlapping along the forearm
  axis), HU>=600 seeds beyond their distal end (hand); watershed on the
  smoothed CT so basins meet in the joint spaces; per-label cavity fill.
  Radius = wider distal end AND reaches further distally (radial styloid);
  both rules agree on both sides. Result (axis length in the scan): radius
  210/197 mm, ulna 191/158 mm, hand 25/48 cm3, humerus extended below its
  `total` label away from the edge band. All partial at the elbow.
  Composite `hand_r`/`hand_l` entities added (as `cranium`).
- Head tasks on the 0.527 mm head-neck grid: craniofacial mandible 60.7,
  cranium 700 cm3, teeth, sinuses; head muscles masseter 31/33, temporalis
  61/64, pterygoids 9-15, tongue 45 cm3 (a large male; s1159's are about
  half) -- plausible; orbit: eyeballs 5.8/5.3, extraocular muscles
  0.15-1.3 cm3, superior rectus 0.01/0.08 (fragments, nulled).
- Origin: `total` on the legs block's pelvis slab fits both femoral heads
  (r 25.9/25.7 mm, rms 0.74/0.71). The torso and legs blocks do NOT
  overlap -- torso z=0 is the legs block's top slice (image correlation
  0.945; no legs slice matches torso z=15) -- so the offset is fixed:
  legs->torso (+2.72, -0.89, -693.0) mm RAS, in-plane by sub-voxel phase
  correlation of the shared slice, +-1 mm in z. Torso-frame origin
  `--origin '-6.035,-895.476,4.787'`. The pelvis-overlap registration
  (`scripts/register_vhm_blocks_by_pelvis.py`) peaks at coverage 0.31 for
  that reason and is not used.
- Task outputs copied to `data/ct_sources/task_outputs/vhm_*`; per-subject
  mappings to `mappings/subjects/ct_vhm*_volume_mapping.json`.
- **Cross-check of the placement against the DU release (same body)**:
  in the band both hold (atlas y >= 85 mm) hip_bone_r top 148.9 (DU) vs
  149.0 (CT) mm, hip_bone_l 149.0 vs 150.9, sacrum 129.9 vs 129.9; band
  centroid differences (-1.4, 0.5, 1.7) and (0.5, 0.5, 4.0) mm for the hip
  bones. Two independent routes to the same pelvis agree to a few mm, so
  the torso block sits on the DU lower limb as one specimen.
- Landmark audit on ct_vhm (50 landmarks): median 5.5 mm; clavicle 5.7/
  4.9, scapula 4.2/3.3, sternum 6.6 mm; humerus epicondyles 94-137 mm
  along the axis because the CT humerus ends above the elbow (FOV) -- an
  artefact of truncation, not of the landmarks.
- Still true, will be reported plainly: upper-limb muscles, tendons,
  ligaments and nerves have no open 3-D source; the atlas carries them as
  data records with anchors only (VH DU ligaments of the lower limb are the
  sole ligament meshes).

## 2026-09-11: cryosections (user: "use the cryosections, complete all structures top to bottom; Sobotta as knowledge only")

- The VH male colour cryosections are streamed from IDC into a 1 mm RGB
  volume (`scratchpad/vh_cryo/cryo_1mm.npy`, 1878 slices, vertex to
  soles, both arms fully in frame) -- see `scripts/cryo/README.md`.
- Photograph quality is excellent (thorax slice: humerus a clean white
  disc, every muscle outlined by fascia). Colour classes work for
  tissue/fat/muscle; bone cortex is cream like fat, so bone comes from
  the CT except where the CT is clipped. Blocks are photographed with
  different flips (abdomen block spine-up, thorax block spine-down), so
  registration to the CT is per block (`register_cryo_to_ct.py`).
- Tried automatic muscle separation on a full-resolution arm crop
  (top-hat of the fascial lines + marker watershed): 26 compartments
  where ~6 muscles exist -- the intermuscular septa are visible, the
  finer fascial planes are not reliable. So individual muscles from the
  photographs are NOT automatic; compartments bounded by the septa are.
- Sobotta: used as anatomical knowledge for positions and relations
  (which muscle lies where relative to which bone), never its images.

- Registration cryo->CT done: flip rows, in-plane shift from silhouettes,
  z from mutual information (cryo index = -16 - z_RAS, +-4 mm, both CT
  blocks). Overlay of `total` outlines on the photographs checked at five
  levels (vertebrae, ribs, lungs, kidneys, skull, humeri all land).
- Photographs resampled into the CT torso grid widened by 110 mm each
  side (`cryo_torso_frame_rgb.npy`, 843 x 480 x 700), because the arms
  that the CT clips lie outside the CT's 480 mm frame.
- **Hybrid CT**: frozen CT with muscle/fat HU replaced from the
  photograph classes (muscle 60, fat -100; 48.7 M voxels changed, bones
  and air untouched) -> `vh_idc/nii/vhm_torso_hybrid.nii.gz`; the
  `abdominal_muscles` task is being rerun on it (the model needs the
  soft-tissue contrast the frozen CT lacks). Result to be compared with
  s1159's volumes before anything ships.
- Arm bone extension through the photographs
  (`vh_cryo/complete_arm_bones.py`): the CT bone tapers to a sliver at
  the FOV edge, so the walk starts from the last solid cross-section;
  the marrow photographs red-brown, so the cortical ring is closed and
  filled before the area check. Running.
- **Arm bones completed through the photographs** (v2,
  `scripts/cryo/complete_arm_bones_from_cryo.py`): local per-slice
  registration of the arm (the global fit is ~6 px off at the forearm),
  walks from the last solid CT slice (marrow photographs red-brown, so
  the cortical ring is closed and filled), all three bones walked without
  stopping at each other, then the contested elbow voxels split by a
  watershed on photograph luminance (the joint line is darker), then the
  humerus cut at the joint line estimated from its head (head top - 340
  mm). Result: humeri to the elbow (both), ulnae to the olecranon (both),
  left radius to the radial head; RIGHT radial head/neck partly labelled
  ulna (known defect). Elbow surfaces +-10 mm. Volume:
  `data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz`.
- Arm muscle compartments from the photographs
  (`scripts/cryo/arm_compartments_from_cryo.py`, key
  `mappings/vhm_arm_compartments_labels.json`, volume
  `data/ct_sources/task_outputs/vhm_arm_compartments_cryo.nii.gz`): the
  arm's muscle mass split anterior/posterior through the humerus centre;
  anterior 721/776 cm3, posterior 713/789 cm3 (right/left). NOT shipped:
  the muscle schema needs fibre parameters a compartment does not have
  (no fabrication), and the forearm split does not follow the septa in
  this pronated arm. Kept as a reviewable intermediate.
- Viewer Version 16 (276 structures): hands grouped, named arm muscles; Version 15: VH pec major/serratus/lat dorsi added; Version 14: arms complete to the elbow (humeri, ulnae; left
  radius to the head; right radial head defect noted).
- **Hybrid CT works for the big trunk muscles.** `abdominal_muscles` on
  the photograph-restored CT (cm3, hybrid / frozen / s1159): pectoralis
  major 152+268 / 14+96 / 171+173; serratus anterior 186+149 / 108+47 /
  76+77; latissimus dorsi 412+373 / 27+7 / 183+163; trapezius (T4-L4 part)
  105+91 / 18+37 / 46+50. Still failing: rectus abdominis 1+6, obliques and
  quadratus lumborum asymmetric by 2-6x -> nulled, stay s1159's.
  Overlay on the photographs at four thoracic levels: pectoralis major
  (under-segmented in depth), serratus, latissimus, trapezius all on the
  right muscles. Shipped as `ct_vhm_abd` (pec major, serratus, lat
  dorsi); trapezius unioned into the neck volume
  (`vhm_headneck_muscles_merged`) as one mesh per side.
- **Hands** (`scripts/cryo/hands_from_both_blocks.py`): the torso CT
  block ends at the palm; the fingers are in the top of the legs CT block
  (where `total` mislabels them "skull"). Both parts unioned in a frame
  extended 250 mm downward, junk not connected to the wrist dropped, then
  planes along the hand axis from the radius end: carpals <45 mm,
  metacarpals 45-115, phalanges beyond. Right 175 mm / left 189 mm long;
  carpals 24/33, metacarpals 11/24, phalanges 14/16 cm3 (carpal group
  over-counted: it takes the metacarpal bases). Four finger rays visible
  on both sides in projection. Label map `vhm_arm_labels.json` v3.
- **Named arm muscles** (`scripts/cryo/name_arm_muscles_from_cryo.py`,
  key `mappings/vhm_arm_muscles_labels.json`): posterior compartment =
  triceps (713/789 cm3); anterior within 22 mm of the humerus, distal
  65 % = brachialis (164/221); proximal-medial = coracobrachialis
  (44/50); rest = biceps (514/506, over-counted). Rule-based boundaries;
  render checked at seven levels (biceps superficial, brachialis on the
  bone, triceps posterior). Shipped as `ct_vhm_armm`, badged.
- Right elbow: below the joint line every cut humerus voxel now goes to
  the ulna (the radius claims its head first), closing the gap in the
  proximal ulna seen in v3.
- **Deltoid** (`scripts/cryo/deltoid_from_cryo.py`, key
  `mappings/vhm_deltoid_labels.json`): muscle within 55 mm of the
  proximal humerus and 40 mm of the skin, lateral to the scapula's
  lateral edge, not already pec/lat/serratus/trapezius/biceps/triceps;
  261/197 cm3 (right/left; undersized, the deep boundary against the
  cuff is a rule). Render: wraps the humeral head laterally and
  anteriorly, tapers to mid-shaft. Shipped `ct_vhm_delt`, Version 17
  (278 structures).
- **Rotator cuff** (`scripts/cryo/rotator_cuff_from_cryo.py`, key
  `mappings/vhm_rotator_cuff_labels.json`): muscle within 25 mm of the
  scapula, >8 mm from the ribs, unlabelled so far; ventral -> subscapularis,
  dorsal above the spine level and medial to the glenoid -> supraspinatus,
  other dorsal -> infraspinatus (+ teres minor merged). Volumes (r/l):
  supraspinatus 68/69, infraspinatus 357/342, subscapularis 358/358 cm3 --
  the last two are over-inclusive (deep serratus slips, teres). Render:
  subscapularis between scapula and ribs, infraspinatus dorsal, supra-
  spinatus in the fossa. Shipped `ct_vhm_cuff`, badged as rule-based; viewer Version 18 (284 structures).
- **Erector spinae columns** (`scripts/cryo/erector_columns_from_autochthon.py`,
  key `mappings/vhm_erector_labels.json`): base mass = hybrid-CT erector
  spinae label (transversospinalis removed) completed by the `total`
  autochthon outside the T4-L4 window; split by distance from the
  vertebral-body midline (spinalis <=20 mm down to L2, longissimus 20-50,
  iliocostalis >50). Volumes r/l: spinalis 67/71, longissimus 473/514,
  iliocostalis 260/211 cm3. Shipped `ct_vhm_es`. The hybrid
  transversospinalis mask (214/205 cm3) is shown under multifidus with a
  group note (rotatores and semispinalis thoracis included).
- Hybrid CT v2 (muscle 80 / fat -120 / fascia 20 HU) is WORSE than v1 on
  every trunk muscle (pec major 53+146 vs 152+268, latissimus 244+275 vs
  412+373; rectus abdominis still 0.1+0.2 cm3). v1 stays; rectus, the
  obliques and quadratus lumborum stay s1159's. The rectus is the
  model's blind spot on this cadaver, not a contrast problem.
- **Body surface** (`scripts/cryo/skin_from_cryo.py`): tissue silhouette
  of every cryosection, holes filled, largest 3-D body kept (colour charts
  and slice labels dropped: 9.4 M voxels); new fascia entity `skin` (schema
  kind 'skin' added). Viewer budgets raised (muscle 2600->3600, bone
  4500->6000, skin 30000); bundle 14.2 MB (limit 16). Version 20 (293
  structures).
- **Sciatic nerve: attempted, not shipped.** `scripts/cryo/sciatic_from_cryo.py`
  seeds at the ischial-tuberosity level midway between IT and greater
  trochanter (from the legs-block `total` labels) and tracks a pale
  30-250 mm2 blob downward. At 1 mm the nerve is not separable from the
  fat plane it lies in by colour (no seed blob of that size exists: the
  pale class merges into the fat), and on the 0.33 mm photograph the
  nerve is not identifiable with confidence without expert reading. Nerve
  geometry therefore stays out; the tracker is kept for a reviewer who
  places the seed by hand.
- **Abdominal wall by position** (`scripts/cryo/abdominal_wall_from_cryo.py`,
  key `mappings/vhm_abdominal_wall_labels.json`): wall = muscle within
  60 mm of the skin, anterior to the vertebral-body centre, in the trunk's
  tissue component, >8 mm from CT-labelled organs (bowel photographs like
  muscle), arms excluded; rectus = within 70 mm of the midline and 70 mm
  behind the anterior skin; lateral wall split by depth fraction
  (external 40 % / internal 35 % / transversus 25 %). Volumes r/l: rectus
  225/226, external 195/350, internal 57/160, transversus 107/286 cm3 --
  over-counted, asymmetric, lower wall (below the iliac crest) missing.
  Render at five levels: rectus paramedian, layers along the flanks, no
  bowel. Shipped `ct_vhm_abw` ahead of s1159's (which now fills nothing
  but quadratus lumborum and the vessels).
- **Full-resolution pass** (`scripts/cryo/stream_arm_crops.py`: 0.33 mm
  crops of both arms and hands, 260 slices each): (a) biceps/brachialis
  boundary re-traced by a marker watershed on the fascial-line map within
  the anterior compartment (`fullres_biceps_brachialis.py`): 80-93 k
  voxels moved, totals barely changed (biceps 526/513, brachialis
  152/214 cm3) -- the plane is not a continuous barrier at this scale;
  adopted, as it follows visible lines where they exist. (b) hand bones
  by luminance watershed inside the group masks (`carpals_fullres.py`):
  ~4 blobs per slice, fragments only, group volumes grew 20 % with cream
  fat -- NOT adopted; the rule-based groups stand.
- **Pectoralis minor and rhomboids** (`scripts/cryo/pecminor_rhomboids.py`,
  key `mappings/vhm_pecminor_rhomboids_labels.json`): pec minor 148/104
  cm3 (over-counted 2-3x: intercostal/serratus slips), rhomboids 124/135
  (major+minor, shown under rhomboid major). Render: pec minor on the
  upper anterior chest wall deep to pec major, rhomboids paravertebral
  between the scapulae. Shipped `ct_vhm_pmr`, badged.
- **Tendons: attempted, not shipped.** `scripts/cryo/tendons_from_cryo.py`
  anchors cylinders on the DU bones (quadriceps tendon above the patella's
  superior pole; Achilles would need the calcaneus, which the DU release
  does not carry). Above the patella the photograph classes are almost
  all 'fat' (cream): the tendon is cream like the fat around it, and the
  b/r and g/r histograms inside the cylinder are unimodal -- no colour
  threshold separates them at 1 mm. Full-resolution texture (fibre
  striation) is the remaining route.
- Viewer Version 22: 299 structures, 18 subjects, 14.4 MB.
## What the OWNER must do (updated 2026-09-14 09:30; everything else runs unattended)

Answered 2026-09-14: Q43 = (b) DONE (landmarks scale with the measured bone length; her distal femur/fibula
landmarks now 1-7 mm from the bone, were 45-62); Q31 = "like in male" DONE (Q61: seven tarsals on both
bodies). Still needed from you:

1. **The DU STL releases (male AND female), Q59.** `digitalcommons.du.edu` now answers through the proxy
   (thank you), but the file endpoint `/cgi/viewcontent.cgi` sits behind a Cloudflare browser challenge that
   curl cannot pass and the sandbox's Chromium has no network at all; `dl.dropboxusercontent.com` (Dropbox
   file content) is also blocked, so the zip you would upload cannot be pulled either. EITHER add
   `dl.dropboxusercontent.com` to the environment's allowed domains (then upload the zips to Dropbox
   `/claude/`), OR push them into this GitHub repository on a branch `data-du` in parts under 100 MB
   (`split -b 90m`). Files: on https://digitalcommons.du.edu/visiblehuman/2/ (male) and /1/ (FEMALE) the
   "Final 3D STL Models" (133 MB each) and "Metadata". The female release is her OWN segmented lower limb
   (muscles, ligaments, cartilage, separate tarsals) and replaces the transferred male limb on her.
2. **Licences of the three sites you named** -- all three are blocked for this sandbox, so I could not read
   them: open each page and paste its licence/credits text into Dropbox `/claude/licences.txt`:
   caskanatomy.info/open3dviewer (hand), anatomytool.org open3dmodel hand and wrist bones and cartilages
   (AnatomyTOOL content is usually CC BY-NC-SA, which would exclude it twice), humanome.co (commercial terms).
3. **Z-Anatomy is CC BY-SA 4.0, not CC BY** (verbatim on its GitHub page: "This work is licensed under a
   Creative Commons Attribution-ShareAlike 4.0 International License"). Under the repository rule no
   ShareAlike source may enter a sellable atlas, so no Z-Anatomy mesh or label file will be used; its
   structure list is read as a checklist only. If you want it anyway, that is a licence decision for you
   to make explicitly (it would put the derived geometry under CC BY-SA).
4. **Your Dropbox uploads of 2026-09-14 06:56**: the muscle reference HTMLs (shoulder, elbow, wrist, hand
   intrinsic, head/neck, mind maps) are readable here and are queued as Q60 (per-muscle clinical fields with
   your citations). `male-body-base-mesh-highpoly.zip` cannot be downloaded (item 1) -- and what is it and
   under what licence? An artist base mesh is not measured anatomy and would only serve as a skin shell.
5. Q54 (popliteal division of the sciatic nerve): 10 marks per side on the montage tiles, as before.

## Autonomous queue (2026-09-11; user away for days, session self-wakes hourly)

Operational lessons (16:35, 17:25): never edit a bash chain while it runs (bash reads the file incrementally; the female chain died with a syntax error after the in-place idempotency patch, so pass 2 had to be started by hand at 17:21); never pkill/pgrep-kill with a pattern that also appears in the killing shell's own command line (it kills the tool shell: exit 144, twice today); the container is reclaimed when the session idles and every background job dies -- keep a background waiter running while long jobs run, and make chains idempotent (skip outputs that exist); the scratchpad filesystem filled (14 GB of intermediates) and killed the female `total` run mid-chunk -- chains now refuse to start under 2.5 GB free, and superseded intermediates (DICOM series already converted, silhouettes, hand full-res crops) were deleted.

If no unchecked item is feasible: check both viewers are the latest published versions, run the tests, and end the wake without churn (do not re-run finished work).

Rules for every wake: read this section; check running jobs in the
scratchpad (`vhm_ts/*.log`, `vh_cryo/*.log`); take the first unchecked
item; verify with a render/volume before shipping; tests must pass;
commit + push; republish the viewer (same URL; male c5d01522, female 0651399d) when the bundle changed;
tick the item here with a one-line result. Never fabricate; keep the
"badged, rule-based" honesty. If blocked, write why and move on.

- [x] Q69 (2026-09-18) Visual QA against the rendered viewer (owner: "check models vs z-anatomy, they
      should look better") found a real geometric defect, not a completeness gap: tibialis_anterior_l/r
      (transferred from the male, refined to her septa, Q48) poked through her own skin surface near the
      distal shin/ankle -- caught by raycasting the rendered mesh at the exact screen pixel showing red
      through the skin, which selected "Tibialis anterior" instead of the skin. Root cause: the transferred
      label volume and the skin volume are independently Gaussian-smoothed before marching cubes (sigma 1.0
      vs 1.5), so their 0.5-isosurfaces don't nest exactly even where the hard voxel masks do, especially
      under a thin skin fold. Fix: `data/ct_sources/task_outputs/vhf_xfer_lowerlimb_septa.nii.gz` clipped
      against her whole-body skin silhouette (skin_union.nii.gz, same frame, offset 140 slices) eroded by an
      extra 3 mm margin -- 33,948 of ~9.9M voxels removed (mostly tibialis_anterior_l/r, also
      extensor_hallucis_longus, fibularis_longus_r, semitendinosus_r and 9 others), well inside this
      transfer's existing +-4 mm registration / +-8 mm max-move uncertainty (already badged). Reconverted
      subject `xfer_vhm2vhf_sep`, re-exported the female bundle (368 structures, 1,160,062 triangles shown),
      re-rendered and confirmed zero residual red pixels at the same pixels a raycast previously hit muscle.
      Tests 252 pass. Female viewer republished, same URL, Version 33. The muscle-COMPLETENESS half of the
      owner's comparison (250/404 muscle entities still without a mesh) is unchanged and tracked under Q62;
      this item only fixed a rendering/registration defect on structures that already exist.

- [x] Q1 Feet (done 2026-09-11 15:40): feet block registered to the legs block by the shared slice (corr 0.968, legs k=0 = feet k=221, in-plane (-6.6,-36.6) mm); HU>=200 minus the block-edge column (persistent in >150 slices) minus everything within 4 mm of the DU tibia/fibula or above the plafond; tarsals 114/123, metatarsals 47/45, phalanges 7.6/7.2 cm3 (r/l); render: both feet, heel to toes. The DU release already carries metatarsals and phalanges (bbox within 5 mm of the CT ones = registration check passed) but its 'tarsals' is one talus-sized bone; CORRECTION: the DU release carries every tarsal as its own mesh under the group id (14 pieces; the first piece's bbox was the talus), so the CT feet add nothing the DU lacks -- `ct_vhm_foot` is NOT in the bundle; it stays as the registration cross-check (metatarsals/phalanges within 5 mm of DU). Was: CT feet block (series 94755b62, ankle->toes) -- register
      to the legs block (shared slice, like torso/legs), HU>=200 bone
      components, group tarsals / metatarsals / phalanges by planes along
      the foot axis from the tibia's distal end; ship `ct_vhm_foot`.
- [x] Q2 (done 15:55) pec minor 148/104 -> 77/51; subscapularis 358/358 -> 321/321 (<=18 mm, not nearer the ribs); rectus 225/226 -> 181/189 (45 mm window), wall layers one piece per slice (external 176/322, internal 44/116, transversus 82/227: left still over); deltoid 261/197 -> 282/215 with the posterior part over the spine. All reconverted and republished. Was: subscapularis
      (<=18 mm from the scapula, exclude the serratus zone), abdominal wall
      (cap rectus at 45 mm behind the anterior skin; require each lateral
      layer to be contiguous), deltoid posterior part over the spine.
      Re-render, re-record volumes, republish.
- [x] Q3 (16:05) radius/ulna frames added to the audit (proximal 2 % = radial head / trochlear notch, long axis distal). ct_vhm_arm: humerus median 6.2/9.5 mm (was 94-137 before the distal end existed), ulna 9.0/6.6 mm, radius_r 19.4 mm, radius_l 57.5 mm along the axis -- the LEFT radius mesh's proximal end is off by ~55 mm along the bone (the cryo walk's radial head on that side needs review). Hand and cranium frames still to do; no anchor edits made (reviewer's call).
- [-] Q4 SKIPPED: a forearm flexor/extensor split has no atlas entity to map to (individual forearm muscles only), so it would stay an intermediate; not worth the compute now. Was: flexor / extensor compartments by the interosseous line
      (flexor side faces the body midline in this pronated arm); if the
      split holds on renders, ship as biceps-style rule muscles only where
      an entity exists (brachioradialis, flexor mass -> not mappable: keep
      as intermediate).
- [-] Q5 deltoid tried at 0.33 mm (`scripts/cryo/fullres_deltoid.py`, marker watershed on fascial lines, 128 slices): 270/204 cm3 vs the rule's 282/215 -- moved AWAY from textbook (350-500), not adopted. Cuff/abdominal wall have no full-res crops (trunk not streamed at 0.33 mm). Was: Q5 Full-resolution muscle boundaries for deltoid/cuff/abdominal wall
      (watershed on fascial-line maps within the rule masks, as done for
      biceps/brachialis); adopt only where volumes move toward textbook
      values.
- [-] Q6 BLOCKED (16:20): `scripts/cryo/aorta_from_cryo.py` seeds on the CT aorta fragment; the clotted lumen photographs near-black but fragmented (seed 112 mm2, no round 250-900 mm2 component in the next slice), so the walk dies within 2 mm. Needs a lumen colour model built from hand-picked samples. Was: the frozen CT has no contrast; try the
      photographs -- large arteries (aorta, iliacs, femoral) are dark red
      lumina with a pale wall; rule + tracking from the `total` aorta
      fragment. Ship only if the aorta tracks continuously.
- [x] Q9 (done 19:45) VH female: 154 structures from 7 subjects, second viewer https://claude.ai/code/artifact/0651399d-2651-4513-9b56-756a84d55e2e (Version 1, 7.8 MB); mappings in mappings/subjects/ct_vhf_*; task outputs in data/ct_sources/task_outputs/vhf_*. Open: union her trapezius (neck + trunk parts); audit her landmarks; compare her model-segmented muscles with the male's rule-based ones. Was: VH FEMALE 'Normal' CT (IDC b9cf8e7a, 985 slices head->mid-thigh, fresh cadaver): dcm2niix, `total` + the free tasks chunked; expect the abdominal_muscles task to work (not frozen); ingest as `ct_vhf_*` with its own femoral-head origin; export as a SECOND viewer bundle/artifact (a second consistent body, not mixed into the male). Also a check of the male rule-based volumes against a model-segmented body.
- [x] Q10 (20:20) female trapezius unioned (154k+161k -> 178k/190k voxels), ct_vhf_neck/abd reconverted, female viewer Version 3.
- [x] Q11 (19:55) male-rule vs female-model volume table: data/derived/male_rules_vs_female_model.json (male external oblique L 322 vs female 160, latissimus 412/373 vs 316/273, serratus 186 vs 122: the rule-based/hybrid male values run 1.3-2x high on those; rectus and transversospinalis agree).
- [-] Q12 BLOCKED (20:20): her arms are clipped by the 480 mm FOV like the male's; the CT watershed gives a partial right radius (24 cm3, 191 mm) and ulna (12 cm3) and finds no second forearm fragment on the left (crash). Completing them needs her cryosections (a 40 GB series; ~4.5 GB at 1 mm, more than the 4.4 GB free), so not now.
- [x] Q13 (20:05) female audit: hip bones 2.0/3.9 mm median, clavicles 5.5/3.9, femur 33 mm along the axis (femur ends at mid-thigh, distal landmarks off-scan), humerus 74 mm (her arms are clipped by the 480 mm FOV like the male's). Cranium frame still to do.
- [-] Q15 DEFERRED (20:35): the skull landmarks in bones.json (temporal, zygomatic, occipital) carry no numeric coordinates, so a cranium frame would audit nothing; the real task is to MEASURE them on the ct_vhm_head cranium mesh in a defined skull frame (origin: basion or sella -- neither is found automatically yet). Needs a reviewer's choice of frame.
- [x] Q16 (20:35) docs/VIEWER_README.md written (badges, two bodies, trust levels, depth tables), linked from GEOMETRY_SOURCES. Was: what each badge means, the two bodies, the rule-based table; link from docs/GEOMETRY_SOURCES.md.
- [x] Q17 (20:50) female body surface from her CT silhouette (`ct_vhf_skin`, 75 M voxels), female viewer Version 4 (155 structures, 8.1 MB), depth table data/derived/skin_depth_vhf.json (154 rows). Was: (same script on build/viewer_f) once she has a skin surface (her CT body silhouette HU>-300 can stand in: add a `ct_vhf_skin` from the CT body mask).
- [x] Q19 (21:05) depth below skin computed by the exporter for every structure (min / median mm from the skin mesh) and shown as a tag in the info panel of both viewers.
- [x] Q18 (21:20) data/derived/audit_male_vs_female.json: per-bone landmark audit on both bodies; the bones that agree across bodies (hip, clavicle, scapula, ulna) point at landmarks that are right; the ones that disagree point at the landmark or at a truncated mesh.
- [x] Q22 (21:30) report only: data/derived/landmarks_off_on_both_bodies.json lists the landmarks >12 mm off on BOTH bodies (the likelier culprit is the landmark); no coordinates changed -- a reviewer decides, using the audit's frames.
- [x] Q28 (20:25 -> 22:50, through a container reset) Female LOWER LIMB bones shipped: female viewer Version 6, 167 structures (+12: tibia, fibula, patella, tarsals, metatarsals, phalanges per side; femur now united from both blocks). See the 22:50 section.
- [-] Q29 BLOCKED (23:05) Restore the MALE build (re-ingest `vhm_both` after the container reset): the DU release
      hosts are denied by this environment's network policy (`digitalcommons.du.edu` and `simtk.org` answer 403 at
      the proxy CONNECT; zenodo.org is open) and no STL zip is in Dropbox `/claude`. Needs the owner: either allow
      `digitalcommons.du.edu` in the environment's network policy, or drop the DU "Final 3D STL models" zips
      (Right + Left, ~133 MB, CC BY 4.0) into Dropbox `/claude`; then `scripts/ingest_vh_geometry.py`, reconvert
      every `ct_vhm*` subject from the repository task outputs (chain to write like `vhf_rebuild_bundle.sh`), and
      re-stream the cryosection silhouette for `ct_vhm_skin` (not in the repository). The male artifact (Version 25)
      stays live meanwhile; nothing about it can be changed until this is done.
      CONFIRMED visually 2026-09-18 (Q69 visual-QA pass, current male V39): "Other"/Integumentum on him only
      covers the torso, arms and thighs -- both lower legs render with skin ABSENT below the knee (raw
      muscle+bone exposed). This is by far the largest visible difference from Z-Anatomy on the male body.
      CORRECTION, same day: the ct_vhm_skin that DOES exist and ships (subject tag "Visible Human male, colour
      cryosections -- body surface") was derived from his 1 mm PHOTOGRAPH stream (`skin_from_cryo.py`,
      `cryo_1mm_classes.npy`), which is what needs the DU-blocked re-stream this item describes -- but that is
      NOT the only source for his leg skin. See Q70: his own CT already covers pelvis-to-toes and is reachable
      right now (verified live), so the leg skin gap is fixable WITHOUT the DU release or a photograph re-stream.

- [x] Q70 (DONE 2026-09-18) Male full-body skin surface from his OWN CT, not the DU-blocked photograph route.
      Downloaded and stacked the two remaining IDC series (`145c2668-...` pelvis-to-ankle 809 slices,
      `94755b62-...` ankle-to-toes 224 slices; `idc-open-data` confirmed reachable, unlike
      `digitalcommons.du.edu`/`simtk.org`). `scripts/cryo/vhm_whole_body_skin.py` unions HU>-300 silhouettes
      from all three CT blocks. The documented block-to-block shifts (image correlation) turned out NOT tight
      enough: checked against every `vhm_both` bone/muscle vertex in the region, they left up to 42% of
      tarsal/phalanx vertices and 15-17% of thigh/calf muscle vertices outside the silhouette (right side
      worse than left both times -- a small torsional difference between table sessions, not a sign error).
      Re-fitted each shift directly against those vertices instead of the raw image correlation
      (`optimize_legs_shift.py`, `optimize_feet_shift.py`, scratchpad only): legs->torso `(4.72, 2.11, -698.0)`
      mm RAS (was `(2.72,-0.89,-693.0)`), feet->legs `(3.5,-35.0,-406.0)` mm RAS (was `(-6.6,-36.6,-409)`).
      Mean vertex containment failure across all 130 `vhm_both` structures: 0.49%; a 2 mm dilation margin on
      the finished silhouette brings it to 0.03% (worst case `fibularis_longus_r` 1.8%). Verified by rendering
      `ct_vhm_skin` together with `vhm_both`: continuous head-to-toe surface, no bone/muscle breaking through
      at the scale a render shows. Shipped as `ct_vhm_skin` (replacing the torso-only version;
      `data/ct_sources/task_outputs/vhm_skin_ct.nii.gz`, `mappings/vhm_skin_labels.json`,
      `mappings/subjects/ct_vhm_skin_volume_mapping.json`); male viewer re-exported (350 structures, unchanged
      count) and republished at the same URL, Version 40. Tests 252 pass. `docs/GEOMETRY_SOURCES.md` has the
      full writeup. Q29's photograph-route skin stays blocked and is no longer needed for this purpose.
      FOLLOW-UP same day: with the skin now complete, the same visual-QA pass found deltoid_r (17% of
      vertices) and triceps_brachii_r/l (17-27%) poking through at the shoulder/upper arm -- his own
      cryosection-derived muscles, not vhm_both. Both label volumes already share the torso block's frame
      exactly, so `scripts/cryo/clip_arm_to_skin.py` reprojected every voxel through the two affines and
      dropped any outside `ct_vhm_skin` (44,015 voxels for deltoid, 206,581 for triceps). Reconverted,
      re-exported (350 structures, unchanged), confirmed by render, republished at the same URL, Version 41.
- [-] Q30 PARKED (23:20 -> 02:00) Female CRYOSECTIONS for her arms and hands. Done and kept: the series streamed
      (1729 slices at 1 mm, resumable, 3 min), classified, registered to her CT (43 anchors, IoU 0.72-0.93, flip
      `fy`; in-plane shift drifts (-4,-108) px legs -> (-13,-121) thorax -> (+14,-117) head = the frozen block's pose
      differs from the fresh scan; z offset a line through the NCC >= 0.55 anchors, rms 8.9 mm), resampled into her
      whole-body CT frame widened to 700 columns, with an overlay check at six levels. Full-resolution (0.33 mm)
      crops of both forearms and hands streamed (`scripts/cryo/vhf_stream_arm_crops.py`, 491 slices, 30 s).
      Finding: her CT humerus labels are nearly complete (273 mm, 154 / 166 cm3, already in the bundle), so only
      the forearms and hands are missing. NOT achieved after four detector designs and a tracking walk
      (`vhf_arm_bones_from_cryo.py`, `vhf_forearm_hand_fullres.py`, `vhf_forearm_track.py`): her bone sections
      photograph as cream discs whose cortex is the same cream as the marrow (no white ring at this resolution),
      the subcutaneous fat is the same colour family (marrow: b/r 0.61-0.63, saturation 0.37-0.39; fat: 0.54-0.58,
      0.42-0.46 -- separable on average, not per pixel), and the ulna's posterior border and the distal radius lie
      on that fat with no muscle between. Enclosed-disc rules give fragments <= 30 mm; a colour rule floods fat
      lobules; the tracking walk rides along the skin rim (the 195 mm "ulna" was the fat rim) and, with a
      muscle-surround rule, stops at 65-93 mm (right radius correct for 93 mm, verified on the overlay). What would
      work: seeds AND per-slice verification from an independent modality -- her partial right radius/ulna in the
      CT (Q12) for the right arm only, or a reviewer marking the two discs every 20 mm (about 20 clicks per arm),
      after which the walk between marks is constrained enough. Nothing from Q30 ships. The scratchpad
      intermediates rebuild in ~10 minutes from the scripts if the container resets.
- [x] Q31 (DONE 2026-09-14 via Q61 below; owner: "like in male") Calcaneus and talus as their OWN entities (the atlas has only the composite
      `tarsals_r/l`; the DU release ships a separate talus and calcaneus that `mappings/du_vh_overrides.json`
      folds into the composite; heel and ankle injections want the two bones). Needs: two bone records per side in
      `data/skeleton/bones.json` (TA names, sources), `tarsals` count 7 -> 5 with the remaining five named, the DU
      override changed to exact matches (male, once Q29 is rebuilt), and the female split from her CT tarsal label.
      Trial at this wake on the female label (distance-transform watershed, no CT needed): the pieces change with the
      marker depth (4 mm: 90 + 15 + 9 + 8 + 7 cm3; 5 mm: 51 + 17 + 16 + 15 + 14; 6 mm: 49 + 39 + 26 + 15 on the
      right) and the 6 mm cut runs through the calcaneal neck, so an unseeded split is not a bone split. Do it with
      ONE placed seed per bone (talus under the tibial plafond, calcaneus at the tuberosity): a seeded watershed is
      then reliable, and the volumes (female calcaneus 55-70 cm3, talus 30-40) verify it. 03:30 wake: seeds
      PLACED BY RULE (talus = under the tibial plafond, calcaneus = the posterior 20 mm of the tarsal mass,
      midfoot = the anterior 15 mm) and watershed on the distance transform AND on the smoothed CT itself both
      fail the same way: the talus flood takes the whole calcaneal body (talus 66-100 cm3, calcaneus 10-14 = the
      tuberosity only) because the subtalar joint shows no HU barrier on this cadaver at 0.72 mm (lateral render
      checked). So a seed is not enough either: this needs a drawn subtalar contour on a few sagittal slices or
      an outside shape model. Parked; the male's DU release already has both bones separately (Q29 first).
- [x] Q32 (04:20 -> 04:45 wake) Female DELTOID by the male's rule on her registered cryosections
      (`scripts/cryo/vhf_deltoid_from_cryo.py`): 164 / 153 cm3 (female textbook 200-300; under and symmetric, the
      deep part missed as on the male's 282 / 215), z -424..-294 / -412..-282, her CT humerus/scapula labels shifted
      11 / 15 px onto the photographs (the residual of the piecewise registration at the arms); crop renders checked
      on both sides (crescent lateral to the humeral head and shaft; the lowest slices catch arm muscle, so the
      rule now stops 130 mm below the head top instead of 150). Shipped as `ct_vhf_delt` (label map
      `mappings/vhf_deltoid_labels.json`, volume + report in `data/ct_sources/task_outputs`), female viewer
      Version 8: 169 structures. Depth tags on it carry the +-10 mm shoulder registration uncertainty (min 0.1 mm
      at the skin). Rule-based, badged. Next candidates by the same route: her rotator cuff (`rotator_cuff_from_cryo.py`
      rules on her scapula label) -- added as Q33.
- [x] Q33 (04:50 -> 05:10) Female ROTATOR CUFF by the male's rules on her registered cryosections
      (`scripts/cryo/vhf_rotator_cuff_from_cryo.py`): supraspinatus 38 / 38 cm3, infraspinatus (+teres minor)
      208 / 180, subscapularis 151 / 105 (female textbook 35-60 / 130-200 / 120-180; plausible, the left
      subscapularis low -- the ventral scapula is where the frozen pose and the fresh CT differ most); crop renders
      checked on both sides (dorsal blue = infraspinatus, ventral purple = subscapularis, supraspinatus at the top).
      Shipped as `ct_vhf_cuff` (key `mappings/vhf_rotator_cuff_labels.json`, volume + report in the task outputs);
      female viewer Version 9: 175 structures. Rule-based, badged. Her shoulder is now: humerus, scapula, clavicle
      (CT), deltoid + cuff (rules), pectoralis major / latissimus / serratus / trapezius (CT model).
- [x] Q34 (05:10 -> 05:30) Female ERECTOR SPINAE columns + MULTIFIDUS. `scripts/cryo/vhf_erector_columns.py` (the male's
      20 / 50 mm midline rule on her MODEL erector-spinae + autochthon labels, no photographs): spinalis 44 / 64,
      longissimus 310 / 304, iliocostalis 157 / 126 cm3 (female textbook 30-60 / 250-400 / 150-250; plausible,
      spinalis asymmetric by the midline rule). Her `abdominal_muscles` transversospinalis label had been NULLED in
      `ct_vhf_abd` (propose default) -- now mapped to multifidus_r/l as on the male: 185 / 173 cm3. Shipped as
      `ct_vhf_es` + the corrected `ct_vhf_abd`; female viewer Version 10: 183 structures.
- [x] Q35 (05:30 tried; 07:05 -> 07:25 shipped in part) Female PECTORALIS MINOR shipped, rhomboids not. v3 of
      `scripts/cryo/vhf_pecminor_rhomboids.py` with the female colour classes, the thoracic cage's convex hull as
      an exclusion (nothing inside it is chest-wall muscle), pec minor bounded to rib 5..clavicle and 8-30 mm from
      the ribs: pec minor 42 / 31 cm3 (female 20-40; strips deep to pec major on the anterior chest wall at
      mid-thorax on the zoomed render; a sliver at liver level remains), rhomboids 49 / 32 (female 70-110; patches
      beside the spine, not the sheet -> nulled in the key). Shipped as `ct_vhf_pmr`; female viewer Version 12:
      191 structures. The first try (male classes, no hull) had given 39 / 34 and 32 / 23 with a rhomboid blob
      inside the abdominal cavity.
- [x] Q36 (shipped at 07:00 via Q37: biceps, brachialis, triceps; coracobrachialis not) -- earlier record: Female upper-arm muscles by the male's compartment rules
      (`scripts/cryo/vhf_arm_muscles_from_cryo.py`, key `mappings/vhf_arm_muscles_labels.json` kept): with the
      male's muscle-mass selection the volumes were slivers (biceps 22 / 31, triceps 7 / 7 cm3); with every muscle
      piece within 45 mm of the humerus kept: biceps 238 / 287 (female 150-250: over, takes brachialis as on the
      male), brachialis 64 / 45 (100-180: under), triceps 172 / 133 (250-400: under), coracobrachialis 0 (the
      proximal medial rule finds nothing). The crop renders show WHY: patches, with much of her arm muscle left
      unlabelled -- her frozen muscle is darker and browner than the male's, and the male's colour class
      (r > g+15, 60 < v < 170) misses 40-60 % of it (right arm at z -450: 7083 px class 3 vs 3185 red-brown px
      not class 3 plus 1435 very dark ones). The same under-capture sits behind the "under" deltoid (Q32) and cuff
      volumes. Chain and viewer label removed; script kept.
- [x] Q37 (06:20 -> 07:00) FEMALE COLOUR CLASSES `scripts/cryo/cryo_classes_f.py` (tissue from value 30 instead of
      60, muscle r > g+10 instead of +15; measured on her: 20 % of in-body thorax pixels had been unclassified,
      median value 49, r-g 20, r-b 27 = dark muscle/organ, not gelatin). Reclassified, re-resampled, reran the
      three photograph rules: deltoid 225 / 213 cm3 (was 164 / 153; female 200-300 -> in range), cuff supraspinatus
      45 / 50, infraspinatus+teres minor 235 / 216, subscapularis 230 / 210 (supraspinatus in range, the other two
      over as on the male), upper arm biceps 394 / 456 (over, takes brachialis and the anterior fat plane),
      brachialis 111 / 74, triceps 295 / 315 (in range), coracobrachialis < 1 (rule finds nothing on her; nulled).
      Crop renders checked (compartments now fill the arm; the coronal split line is visible as on the male).
      Shipped: `ct_vhf_delt` and `ct_vhf_cuff` reconverted, `ct_vhf_armm` new (Q36 partly done: three of four);
      female viewer Version 11: 189 structures. Rule table and viewer README updated with the new numbers.
- [x] Q38 (08:20 -> 08:50 wake) Female BODY SURFACE WITH THE ARMS: her CT clips the arms, so every arm/shoulder
      structure's depth tag was measured to a clipped surface (deltoid 0.1-0.3 mm "below skin"). `scripts/cryo/
      vhf_skin_union.py` unites the CT silhouette with the registered photograph silhouette above RAS z -950
      (13 % more surface voxels, the arms; below that the CT stays exact -- a first version without the cut added a
      registration rim along one leg, seen on the front render). Depth tags now: deltoid 13-15 mm min / 32 median,
      supraspinatus 22-23 / 59-63, subscapularis 17-18 / 59-62, biceps 0.1-0.6 / 24-29, legs unchanged.
      `ct_vhf_skin` reconverted; female viewer Version 13; `data/derived/skin_depth_vhf.json` regenerated.
- [x] Q39 (09:20 -> 09:50 wake) Female RIGHT FOREARM AND HAND from her torso CT: the male's marker watershed
      (`scripts/segment_arm_bones_vhm.py`) adapted as `scripts/vhf_arm_bones_ct.py` -- her right forearm lies inside
      the CT field of view after all (Q12 had read the earlier partial result as a failure): radius 23.7 cm3 /
      191 mm (nearly complete), ulna 11.9 cm3 / 119 mm (its proximal part outside the field), hand 61 cm3 grouped
      by planes from the wrist (`vhf_arm_bones_ship.py`: carpals 22, metacarpals 27, phalanges 11 cm3 -- female
      textbook 15-25 / 25-35 / 12-18); the left arm is outside the field of view (the watershed finds no forearm
      fragment). Coronal and sagittal renders checked (the hand lies flexed on the thigh; the humerus basin is not
      repackaged -- it drags a truncation cloud at the field edge; ct_vhf keeps the TotalSegmentator humerus).
      Shipped as `ct_vhf_armb` (key `mappings/vhf_arm_bones_labels.json`); female viewer Version 14: 196
      structures. Q30's photograph route stays parked; this covers the right side from the CT instead.
- [-] Q40 TRIED, NOT SHIPPED (10:20 -> 10:50) Female right forearm compartments
      (`scripts/cryo/vhf_forearm_compartments.py`, kept). Three passes: (1) the male's rule as is -> flexor 222 /
      extensor 183 cm3, but the render shows the "extensor" on the trunk and thigh her forearm rests on (the tissue
      component holding the bones is the whole body there); (2) muscle pieces within 25 mm of the bones only ->
      116 / 2; (3) the forearm's own cross-section isolated by an 8 px erosion of the silhouette, split oriented by
      the ulna's subcutaneous border -> 158 / 11.5. The split fails because her CT ulna covers only 97 of the 178
      segment slices (the rest falls back to a row split that means nothing in her pronated, thigh-resting
      forearm) and the extensor bellies sit at the elbow end where the segment starts. The atlas has the entities
      (`volar_forearm_compartment_r`, `dorsal_forearm_compartment_r`); nothing ships until the ulna is completed
      (Q30's photograph route) or a reviewer marks the interosseous line on a few slices.
- [x] Q41 (12:20 wake) Landmark AUDIT of the new female bones (`scripts/audit_landmarks_vs_geometry.py` on
      ct_vhf_legs and ct_vhf_armb; rows added to `data/derived/audit_male_vs_female.json`): patellae 2.5 mm median;
      fibulae 1.9 / 4.7 mm median but the malleolar landmarks 49-62 mm off -- her fibula is 35 mm shorter than
      the male's the landmarks were written on, so they fall beyond her bone's end (the label itself reaches
      16 mm below the tibial plafond, the lateral malleolus is there); femora not fitted (head fit rejected on
      the united label, r 28 mm rms 6); right radius median 58.6 mm ALONG the axis and ulna distal landmarks
      150+ mm off = the truncations measured: her radius lacks its proximal ~50 mm and the ulna ~110 mm (outside
      the CT field of view). Label-map notes, viewer label and docs corrected from "nearly complete" to that; female viewer Version 15 (badge text only).
- [x] Q42 (13:20 wake) ENGINE FIX: `proximal_head_centre` fitted the femoral head from the extreme 12 % of the whole
      bone by (superior + medial), which on a WHOLE femur (her united 424 mm one) spans head, neck and trochanter
      and was rejected (r 28, rms 6). It now ranks within the proximal 90 mm when the bone is longer than 200 mm
      along the superior axis; shorter pieces are untouched, so every origin stays exactly as computed (her
      `inspect` origin re-checked: 7.769,-885.229,14.137). Her femora now fit r 23.7 mm, rms 0.60 / 0.68; audit
      rows added (median 2.9 / 4.9 mm; condylar landmarks 50-53 mm beyond her shorter bone, as with the fibula).
      Tests 149 pass. Also the reason the first Q28 registration attempt failed on the legs block: the same fit on
      a shaft with no head, and on RAS points whose second axis is anterior, not superior.
- [x] Q43 (decided (b) by the owner; done 2026-09-14) The bone landmarks in `data/skeleton/bones.json` were
      millimetres on a male-length bone: on the female every distal landmark of the femur, fibula and humerus fell
      50-70 mm beyond her shorter bone. Done with no change to the stored coordinates: femur, tibia, fibula, humerus,
      radius, ulna and clavicle now carry `reference_length_mm` (his length along the frame's +Y, 1st-99th
      percentile, measured on vhm_both / ct_vhm_arm / ct_vhm; `reference_length_note` says how) and ONE helper,
      `engine.geometry.local_to_world` / `scale_local_to_length`, multiplies the along-axis coordinate by
      measured/reference and leaves the across-axis mm alone; `build_frames` returns the measured length as each
      frame's 5th element, `audit_landmarks_vs_geometry.place()` wraps it, and the audit, `export_viewer_bundle
      .resolve_anchor_points` and `validate_moment_arms` all use it. Female before -> after (same audit): ct_vhf_legs
      femur condyles 53.2/50.5 -> 2.6/2.6 mm, medial epicondyle 46.7/44.4 -> 7.0/6.3, lateral epicondyle 49.6/46.1
      -> 6.0/6.0, fibula lateral malleolus 61.7/48.9 -> 0.7/1.4, overall 42 landmarks median 3.4 -> 2.2 mm, 11 -> 0
      beyond 40 mm, 4 -> 0 anchors >20 mm from their bone; ct_vhf right humerus median 55.8 -> 5.6 mm (trochlea
      65.8 -> 10.6, capitulum 65.9 -> 11.8); ct_vhf_armb right ulna styloid 162.5 -> 6.8. Male: factor 1.000 on
      every bone, audit output identical (vhm_both, ct_vhm); ct_vhm_arm additionally gained a right-humerus frame
      (a `<` on the distal 2% selected nothing on a bone cut flat by the CT, so it was NaN before). Caveats: a bone
      truncated by a CT field of view measures its truncation, and the factor then compresses the landmarks onto
      the fragment (her ct_vhf femora at 0.34, her ct_vhf_armb ulna at 0.42, his left radius/ulna at 0.85/0.90 --
      those two carry the complete RIGHT side's length as reference); the audit prints the factor per bone. No
      reference for metatarsals/phalanges_foot: no frame fits on either recovered body. Tests
      tests/test_landmark_scaling.py (7), suite 169 pass.
- [ ] Q7 (wake 02:10: checked on the female frame at 1 mm -- the sciatic nerve is not separable from the
      intermuscular fat by colour at that resolution; a full-resolution thigh crop stream is a 30-second job with
      `vhf_stream_arm_crops.py`'s window logic once a reviewer places the seed; the male cryosections are gone
      with the container reset, so this item now applies to the FEMALE unless the male is re-streamed)
      Nerves at full resolution: sciatic (hand-placed seed from the
      gluteal render), median/ulnar in the arm crops; ship only what
      tracks continuously for >100 mm.
- [x] Q8 (16:10) rule-based table with VH volumes vs textbook ranges added to GEOMETRY_SOURCES. Was: GEOMETRY_SOURCES "what is rule-based" table
      with volumes vs textbook ranges; README for the viewer badges.

- [x] Q44 (2026-09-13, 13:00 -> 18:10, user instruction while away: "beware of noncompatible models -- make them
      compatible, remember the differences (sex, height, fat, weight); correct the data before inserting it into
      either model; recheck previous data; where a model lacks something, learn the male/female difference and use
      one model to enhance the other with the modifications needed"). DONE, in four parts:
      (1) MEASURED DIFFERENCES `data/derived/subject_anthropometrics.json` (scripts/transfer/subject_anthropometrics.py):
      published donors (Andreassen 2023, Sci Data 10:34, via PubMed/PMC): male 39 y 180 cm 90 kg BMI 27.8, female 59 y
      157 cm 88 kg BMI 36; measured on the meshes: femur 0.88, tibia 0.84, scapula/clavicle/sternum 0.85-0.89, pelvis
      1.05, cranium 1.0 of his; photographs (same colour-class method on both; his frozen CT cannot separate fat, both
      HU peaks at -20): thigh fat 23 % vs 49 %, thigh muscle 442 vs 219 cm2 (0.50), calf 91 vs 73, trunk fat 45/28 %
      vs 52/35 %; her glutei/iliopsoas 0.33-0.62 of his. Male cryosections streamed every 10th mm for this (188 slices).
      (2) TRANSFER (female viewer published as Version 16, male as Version 26; scripts/transfer/cross_subject_transfer.py + bone_frames.py + lean_envelope.py + build_envelopes.py):
      per-bone PCA frames on both bodies, box-to-box affines blended by inverse-square distance over the region's three
      nearest bones (his right hand lies beside his thigh: candidates restricted by atlas region); lower-limb muscles
      then re-placed radially inside HER muscle compartment (envelope of his DU muscles per 10 mm level x 36 directions
      -> her outermost muscle-class pixel / skin along the ray in her photographs x her skin mesh) and scaled to her
      measured muscle cross-section (fill 0.97 thigh, 1.09 calf). Female viewer Version 16: +85 badged structures
      (`xfer_vhm2vhf`: 60 DU lower-limb muscles, knee ligaments, hip/knee/ankle cartilage, coccyx, his rule-based
      rhomboids/coracobrachialis/transversus; source trust recorded per structure); at most 4 % of any structure's
      vertices outside her skin; vastus lateralis 1127 -> 453 cm3, rectus femoris 413 -> 162, soleus 685 -> 395, adductor
      magnus 1138 -> 778 (data/derived/transfer_report_vhm2vhf.json). NOT transferred: his left radius/ulna/hand (her
      left forearm lies outside her CT: no driving bone). Male viewer Version 26: rebuilt from the bundle recovered from
      its published page (data/derived/viewer_bundles/vhm_v25 -- the DU STL hosts stay denied, this is the only copy that
      survives a reset; scripts/transfer/bundle_to_subjects.py) + 8 from her (`xfer_vhf2vhm`: digastric, internal
      carotid, internal jugular, superior rectus); her temporal/zygomatic pieces are 2 mm label fragments (refused).
      Exporter fix: non-finite anchor points broke the viewer's JSON.parse.
      (3) RECHECK OF PREVIOUS DATA -- the big one: her cryosection frame was 47-90 mm TOO HIGH over the whole body below
      the neck (scripts/cryo/vhf_check_frame_z.py: pixel-wise fat/muscle Dice of each CT slice against the photographs,
      57 levels, data/derived/vhf_cryo_frame_z_survey.json; the z line had been fitted without the thorax anchors).
      Corrected in place (vhf_correct_frame_z.py, v1 arrays kept; re-check 0 +- 5 mm). Everything shipped from her
      photographs was re-derived on the corrected frame (scripts/cryo/vhf_rebuild_after_frame_fix.sh): deltoid 225/213
      -> 357/331 cm3 (now HIGH vs his 232/180 rule value: the rule over-includes on her, Q46), supraspinatus 45/50 ->
      43/53, infraspinatus+teres minor 235/216 -> 288/297, subscapularis 230/210 -> 244/260, biceps 394/456 -> 275/444,
      brachialis 111/74 -> 104/92, triceps 295/315 -> 314/346, pec minor 42/31 -> 31/26, skin union arms re-cut,
      depth table regenerated. Scale audit of the 138 shared structures (scripts/transfer/cross_subject_scale_audit.py
      -> data/derived/cross_subject_scale_audit.json): 32 flagged, of which same-method: her deltoid HIGH (rule), her
      left triceps/brachialis LOW (0.42/0.45; her left arm rule volumes small), his orbit muscles 2-8x smaller than hers
      (his frozen-CT orbit segmentation is degraded, Q47), her left foot phalanges 5.5 vs his 35 cm3 and her left
      metatarsals 36 vs his 16 (the left foot's grouping planes misassign toes to metatarsals, Q45); the vessel flags are
      ct_s1159 (a third body) vs her, not comparable; abdominal-wall flags are the known male rule over-inclusion (Q11).
      (4) Docs: GEOMETRY_SOURCES 'Cross-subject transfer' + 'frame was 47-90 mm too high'; VIEWER_README badge rows;
      template badges/subtitles; tests/test_transfer.py (4); full suite 153 pass; requirements + trimesh/shapely/rtree.
- [x] Q45 (18:40) Her left foot is FINE (metatarsals 35.9 vs right 41.5, phalanges 5.5 vs 7.0; the same planes on
      both sides). The flag was the MALE's DU left foot: DU left metatarsals 16.4 / phalanges 35.3 cm3 vs his right
      38.8 / 6.8 and his own CT feet block 44.9 / 7.2 (totals agree to 0.5 cm3): ~22 cm3 of metatarsal heads are filed
      under "phalanges" in the DU left-foot STLs. Fixed on the male viewer (Version 27): his left metatarsals and
      phalanges now ship from his CT feet block (`ct_vhm_foot`, mapping labels 5/6, legs-block origin
      -8.755,-202.476,5.677 = the torso origin minus the legs->torso offset), listed before vhm_both; CT boxes within
      10 mm of the DU ones, volumes 40.2 / 6.6 cm3. Docs (GEOMETRY_SOURCES, VIEWER_README), template label updated.
- [x] Q46 (19:20) Her deltoid rule v2: overlays on her photographs showed the male's rule swallowing the whole arm
      section below the axilla (her thin arm lies inside the 40 mm skin band) and the fixed 130 mm window reaching below
      her deltoid. v2: depth band 25 mm from the muscle-compartment surface (not the skin), window 113 mm (scapula
      ratio), lateral +-80 deg wedge about the humerus below the head. 377/348 -> 226/282 cm3 (his rule 232/180;
      lean sections predict ~0.77 of his, so the left is still high -- the anterior part over pectoralis at the cap
      level is the remaining suspect). Reconverted, female viewer Version 17; VIEWER_README row, GEOMETRY_SOURCES,
      template label updated. Her left triceps/brachialis (0.42/0.45 of his) not touched (arm rules, Q48-adjacent).
- [x] Q47 (18:55) His orbit: 10 of his 13 frozen-CT orbit pieces are under half of hers (inferior_oblique_r 0.10 vs
      0.73, inferior_rectus_l 0.08 vs 0.64, lateral_rectus_l 0.17 vs 0.78, superior_obliques 0.16 vs 0.43 ...); those
      ten plus the two superior recti now ship transferred from her (`xfer_vhf2vhm`, 18 structures, listed before
      ct_vhm_orbit so they win; badged), his left levator (1.05), left inferior oblique (0.59) and left medial rectus
      (0.45) stay his. Male viewer Version 28. The oculomotor task on his 0.527 mm head block was not re-run (his
      eyes are frozen; the model's failure is in the data, not the run).
- [x] Q48 (20:10) Transferred thigh/leg muscles refined to HER septa: scripts/transfer/refine_transfer_to_septa.py
      voxelises the 57 transferred muscles into her 1 mm frame, marker watershed on the white top-hat of the
      photographs (fascial planes = ridges), markers = masks eroded 3 mm, region = her muscle class within 4 mm of
      the transferred union minus her own glutei/iliopsoas/autochthon, max move 8 mm, no growth into fat. 810
      slices, total conserved (10.14 -> 9.91 L), median ratio 1.02; gracilis_r 114 -> 75, TFL 104/108 -> 70/84,
      semitendinosus 198/222 -> 159/176 cm3 (report beside the label volume in task_outputs). Ships as
      `xfer_vhm2vhf_sep` (label key mappings/vhf_xfer_septa_labels.json, listed before xfer_vhm2vhf in the rebuild
      chain), female viewer Version 18; badge says the walls are hers, the muscle set his. Overlays checked at y
      -150..-600 (contours follow the visible bellies).
- [x] Q49 (20:50) Her arm rule v2: overlays showed the CT humerus label (one shift constant per side) sitting BESIDE
      the bone lower down the arm, so the coronal plane / bone distances split the compartments from the wrong point
      and trunk muscle at the axilla was admitted. v2 locates the humerus in the photograph (round hole in the muscle
      compartment nearest the CT label; 110/171 slices r/l) and cuts the arm island off the trunk (opening 6 px).
      biceps 322/444 -> 267/224, brachialis 112/92 -> 117/120, triceps 342/346 -> 303/337 cm3. Female viewer
      Version 19. Her biceps/triceps are 0.36-0.44 of HIS rule values (472/475, 675/762 cm3, far above textbook) -> Q51 on the male rule.
- [x] Q51 (22:20) His upper-arm compartments v2 without his lost frame: arm levels re-streamed (290 slices),
      per-slice whole-body-centroid registration to his CT, humerus found in each photograph (seeded by his complete
      humerus mesh; the frozen-CT label stops 100 mm below the head), deltoid/cuff/CT trunk labels and lateral forearm
      origins excluded (scripts/cryo/vhm_arm_muscles_v2.py, volume in task_outputs, converts as ct_vhm_armm in
      scripts/vhm_rebuild_bundle.sh). biceps 472/475 -> 452/432, brachialis -> 74/105, coracobrachialis -> 48/41,
      triceps 675/762 -> 549/602 cm3 (label volumes; meshes after smoothing biceps 400/392, brachialis 49/75, triceps
      517/581). Male viewer Version 29. Audit: her triceps flags clear; her left biceps stays LOW (0.45 of his) and
      HIS brachialis (49/75) is now smaller than hers (106/109) -> the 22 mm "within the bone" brachialis band is too
      tight for his thicker arm (Q52).
- [x] Q52 (23:00) Premise wrong: the mid-arm muscle sections are the same on both bodies (his 40/45 cm2, hers 41/37;
      equivalent radius 36 vs 35 mm), so the bands need no size scaling -- his brachialis is thicker RELATIVE to his
      arm. His fascia-traced v1 boundary (fullres_biceps_brachialis.py, 133/189 cm3) is the measured reference, so his
      band was calibrated to it: 22 mm -> 74/105, 28 -> 111/145, 34 -> 154/192; 32 mm adopted (label 140/176, meshes 110/144). Hers
      stays 22 mm (no traced boundary on her; same radius). Male viewer Version 30; asymmetry of the two rules
      recorded in VIEWER_README / GEOMETRY_SOURCES.
- [x] Q53 (2026-09-14, 05:30 -> 09:40; user: "you have a lot of work to do -- continue") SCIATIC NERVE on the
      female from her FULL-RESOLUTION cryosections (0.33 mm; 1 mm frame could not show it, Q7). New:
      `scripts/cryo/vhf_stream_crops.py` (atlas-box crops of any level range, streamed from IDC in seconds),
      `vhf_nerve_track.py` (muscle-section corridor from her meshes + fascicle-HONEYCOMB texture detector +
      landmark-rule seed + Viterbi chain; montage of every level for the human check), `vhf_nerve_volume.py`
      (merged verified ranges -> 0.5 mm label volume, subject `ct_vhf_nerve`, id `sciatic_n`). Shipped: right
      -70..-235, left -70..-293 mm (19.7 cm3 label / 18.0 mesh both sides, median sections 26/34 mm2), every checked montage tile
      shows the honeycomb at the cross-hair. Not shipped (honest limits, see GEOMETRY_SOURCES): the gluteal
      course above -70 (detector locks onto gluteus maximus' fatty striations) and the popliteal division
      (right lost at -245 on muscle/fat edges; left the paler bundle sits 8 mm off the cross-hair at -303..-333).
      Also this wake: the viewer's NEEDLE PATH tool (Needle path button: entry click + target click ->
      length, structures crossed with depth ranges, depth below skin; `tests/test_viewer_template.py`) and
      the 📍 origin/insertion buttons fixed (showPoint was not reachable from the inline onclick).
      Female viewer Version 20, male viewer Version 31 (needle tool + button fix; his bundle unchanged).
- [ ] Q54 (06:20 wake, 2 h, NOT done -- four detector/corridor changes, none tracks the popliteal bundle)
      Sciatic division -> tibial and common fibular nerves through the popliteal fossa to the fibular
      neck. Tried and kept in `vhf_nerve_track.py` (they do not change the shipped Q53 volume, which was
      built at commit 679caa9): the fossa between the roof muscles counts as floor (the corridor was EMPTY
      there: a 726 px vastus lateralis sliver made "near floor" demand 15 mm of it); muscle interiors
      (sections eroded 3 mm) excluded; brightness band up to 190; candidates with aspect > 3 rejected.
      Result: left tracks to -303 (bundle at the cross-hair), then from -313 the chain sits on muscle-edge
      blobs while the tibial nerve is plainly visible 15-20 mm away beside the popliteal vessels; right
      the same from -245. Diagnosis (q54_diag2 overlay): the texture core fires all along muscle/fat
      edges even with the 1 mm exclusion and the sd < 35 test, so edge blobs outnumber the nerve 10:1 and
      the Viterbi picks the nearest. What is needed: a per-blob HONEYCOMB SCORE to rank candidates
      (count of bright cells 0.5-2 mm bounded by darker walls inside the blob, e.g. local maxima of the
      3 px-smoothed R at >= 1 mm spacing per mm2, or the ratio of the blob's own internal edge density to
      its boundary edge density), with the Viterbi cost = jump + lambda x (1 - score); and a second
      branch for the common fibular nerve. 06:30 UPDATE, measured on the left -313 tibial nerve: NO hand-crafted feature
      separates it from the connective tissue beside it -- peak density 0.02/mm2 (its fascicles are 1-2 px
      specks, not 1-2 mm cells), mean R 157 vs 152, gradient 46 vs 87, roughness 3.5 vs 5.6, b/r 0.55 vs
      0.52; a human sees it by SHAPE (compact 8 mm oval in fat beside the popliteal vessels) and by the
      speckle. A `honeycomb_score` (peaks/mm2) is in the tracker but is ~0 for every blob at these levels,
      so it is inert. Next attempt must be LEARNED: a small patch classifier trained on her own verified
      sciatic sections (the ~330 tracked levels of Q53 as positives, corridor patches >= 10 mm away as
      negatives, 48 px = 16 mm patches, flips/rotations), used as the candidate scorer and as a dense
      corridor scan where the hand-crafted detector finds nothing; badge as "tracked with a classifier
      trained on her own proximal sections". torch and scikit-learn are NOT installed (wiped with the
      container reset); pypi is reachable, so `pip install torch --index-url
      https://download.pytorch.org/whl/cpu` (or scikit-learn for a forest on multi-scale patch features)
      is the first step. One focused wake. 07:40 RESULT: done in this wake with scikit-learn (torch's CPU index is
      blocked) -- `vhf_nerve_patches.py` (2,324 positives / 3,603 negatives from the verified track) +
      `vhf_nerve_scorer.py` (HGB on 155 patch features; level-held-out AUC 0.998) wired in as `--scorer`.
      It does NOT generalise: on the popliteal levels the probability at the visible tibial nerve is 0.01-
      0.21 while muscle edges score 0.8 (probe_scorer.png), and the runs with it produced all-gap chains.
      The proximal honeycomb and the popliteal speckled oval are different appearances; the classifier has
      never seen the second. Also found and reverted: the muscle-interior exclusion removed 5/7 verified
      left nerve positions (her thigh muscles are transferred meshes). WHAT WOULD WORK: popliteal training
      examples -- a reviewer marking the tibial nerve every 10 mm from -300 to -400 on each side (10 clicks
      per side on the 30 mm montage tiles; the nerve is the grey speckled oval beside the black popliteal
      vessels), after which the scorer retrains and the chain runs between the marks. Parked until marks
      exist; Q55/Q56 (vessels: black lumens, trivially detectable) are the better next items. The gluteal course above -70 fails differently: the flattened
      nerve under gluteus maximus is 3 mm thick and the 1 mm near-muscle exclusion removes it. Verify on
      30 mm zoom montages every 10 mm as for Q53. Left montage shows the bundle plainly at -303..-333
      in the popliteal fat: the detector needs a
      "pale bundle in fat" mode (texture only: cells + walls, brightness up to the fat's; drop the near-fat
      exclusion inside the fossa hull) and the chain a second branch (CFN along the medial edge of biceps
      femoris). Verify on 30 mm zoom montages every 10 mm as for Q53. Then the same for the gluteal course
      above -70 (corridor = between gluteus maximus and the short rotators/quadratus femoris; exclude the
      muscle interior by the muscle-class closing at 5 mm).
- [x] Q55 (DONE 2026-09-16, RIGHT side: subject `ct_vhf_femoral`, female viewer Version 30. Artery y +14..-46, median
      lumen 5.7 mm, 1.65 cm3; vein y +14..-34, 7.8 mm, 2.69 cm3 (collapsed cadaveric vein, under the living 9-13 mm);
      nerve trunk y +13..-12, 1.07 cm3, ends where it divides 45 mm below the inguinal ligament and rests on 9
      detected levels of 26. Medial-lateral order verified on the meshes: nerve x 87-94, artery 80-85, vein 73-79.
      NOT covered: the top of the common femoral vessels (above the crops) and the adductor canal/hiatus (the walk
      drifts into muscle and could not be confirmed). LEFT side not run.) Femoral neurovascular bundle on the female at full resolution: femoral artery/vein (dark lumen,
      unmistakable) and femoral nerve in the femoral triangle and adductor canal (corridor between sartorius,
      adductor longus, vastus medialis, iliopsoas; seed by the rule "midpoint of the inguinal ligament =
      ASIS-pubic tubercle midpoint, artery medial to the nerve"). Vessel ids are sided (`femoral_a_r`).
- [ ] Q56 FIRST HALF DONE 2026-09-16 (subject `ct_vhf_popliteal`, female viewer Version 31: popliteal artery y -307..-386
      median lumen 4.3 mm 1.30 cm3, vein -305..-360 5.5 mm 1.34, tibial nerve -340..-374 0.94; depth order verified on
      the label volume, artery anterior-most in every band, nerve 20 mm posterior and 16 mm lateral to it; the common
      fibular nerve was not unambiguous and the division at popliteus is not covered). STILL TO DO: the brachial artery
      and median/ulnar/radial nerves: ATTEMPTED 2026-09-16 in new upper-arm crops and NOTHING SHIPPED -- her upper-arm
      muscle photographs as dark as a thigh lumen, so the lumen rule found 0-1 candidates per level; the best artery
      chain is a 2.1 mm patch on the muscle border (a woman's brachial artery is 3.5-5 mm), the median and ulnar walks
      held one level each and the radial 18. All four labels nulled with reasons; the label volume, montage, script and
      tests are kept for review. The reusable result is the FRAME: a deep-arm muscle hull (her arm touches her chest,
      so the island rule fails) with the photographed humerus tracked on 182/203 levels, residual 8.9 mm. Caveat: her
      arm is rotated, so body-medial is not the arm's medial.
- [x] Q62 pelvic floor SHIPPED 2026-09-16 as `ct_vhf_pfloor` (female viewer Version 32, 15.38 MB): levator ani
      36.3/26.4 cm3 (REVIEW: 62.7 bilateral against the 19.8-46.6 of Fielding's MRI series, the rule sheet is 10-13 mm
      where Gray's gives 3-5), coccygeus 4.0/2.4, external anal sphincter 19.6 midline, bulbospongiosus 2.7/2.9 and
      ischiocavernosus 2.7/1.2 (both include their erectile bodies), deep transverse perineal 1.9/1.4. Superficial
      transverse perineal (0.8/0.4) under what the frame supports and unshipped. Zero overlap with the bone and organ
      labels; 76-100 % of every mask on her muscle class. HIM: needs his 1 mm frame rebuilt plus prostate/penile-bulb
      rules -- new queue item Q68.
- [ ] Q68 Male pelvic floor: rebuild his 1 mm cryosection frame (stream -> register -> resample, the pieces are in
      scripts/cryo/stream_vhm_cryosections.py and the whole-body centroid registration of vhm_arm_muscles_v2.py),
      then run scripts/cryo/vhf_pelvic_floor_from_cryo.py's rules with the male variants: the prostate at the hiatus,
      a midline penile bulb, a deep-pouch external urethral sphincter.
      Was: Popliteal artery/vein (the dark round lumens in the Q53 distal montages) and the tibial nerve's
      relation to them; then the brachial artery + median/ulnar/radial nerves in new UPPER-ARM crops
      (stream y +?..: her arm levels, box around the humerus; corridor = medial bicipital groove between
      biceps and triceps; the arm crops on disk are elbow-to-fingertips only).
- [ ] Q57 Male sciatic nerve by the same tracker: his cryosections at full resolution need a registered
      frame (his 1 mm frame was lost with the container reset; `stream_cryosections.py --start/--stop` and
      the whole-body centroid registration of `vhm_arm_muscles_v2.py` are the pieces) -- do after Q54 so
      the detector is final.
- [x] Q61 (2026-09-14, 07:20 -> 09:30; owner: Q31 "like in male") The seven TARSALS as their own bones on both
      bodies. Male: the recovered bundle's seven `tarsals_r/l` pieces named by rule (`name_tarsal_pieces.py`,
      matches the DU alphabetical order on both sides); `bundle_to_subjects.py --rename` in the male chain.
      Female: his seven transferred onto her (`cross_subject_transfer m2f`, driven by tibia/fibula/metatarsals)
      and her CT tarsal label assigned voxel-wise to the deepest transferred bone (`vhf_split_tarsals.py`,
      subject `ct_vhf_tarsal`): calcaneus 56/60, talus 31/33 cm3 (expected 55-70 / 30-40), cuboid 19/17,
      navicular 8.5/7.4, cuneiforms 9.4/9.5, 3.9/4.7, 0.8/1.4 (intermediate under-assigned). ICP refinement
      measured worse and left off. 14 entities in bones.json, DU overrides retargeted, composite kept for
      single-label scans and dropped from the female legs subject. Both viewers rebuilt: female Version 21, male
      Version 32 (talus/calcaneus renders checked on both).
- [x] Q43 (b) DONE 2026-09-14 by the landmark-scaling change (see the Q43 item above): `engine/geometry.py`
      scale_local_to_length + reference_length_mm on 14 long bones; truncation guard 0.6-1.5 added after
      the subagent's caveat (a femur cut at mid-thigh measured 0.34).
- [-] Q59 BLOCKED on the owner (see the owner list): DU Final 3D STL releases, male AND FEMALE. The pages are
      reachable through the proxy now; the file endpoint is behind a Cloudflare browser challenge (curl gets
      "Just a moment..." 403 with cookies, HTTP/2 and Chrome headers; Chromium here has no network at all:
      ERR_CONNECTION_RESET even to open hosts); Dropbox file content (`dl.dropboxusercontent.com`) is blocked
      at the proxy CONNECT. Once the zips arrive: `scripts/ingest_vh_geometry.py` for both bodies (overrides
      now map each tarsal file to its own entity), rebuild the male from source (replacing the recovered
      decimated meshes), and replace `xfer_vhm2vhf`/`xfer_vhm2vhf_sep` on the female with HER OWN DU lower
      limb (keep the septa-refined transfer only where the release has nothing).
- [x] Q63 (2026-09-14, 10:10) Pharyngeal constrictors on both bodies from the head/neck task labels that were
      mapped to null ("unsided"): new splitter `midline_by_label_centre` (engine/volume_ingest.py; the strict
      `midline` still requires sternum/vertebrae and still raises) cuts each tube at its own centre; male all
      three (391/386, 1083/1004, 2210/2174 voxels r/l), female middle + inferior (the superior is 196 voxels,
      13 right: not shipped). ct_vhm_neck now converts from his merged volume in the chain instead of the
      recovered bundle. Male viewer Version 33, female Version 22.
- [ ] Q62 PROGRESS 2026-09-14 13:50: step 1 female right forearm SHIPPED as `ct_vhf_forearm` (12 muscles, rule-based,
      FCU 55 / BR 48 cm3 flagged for review; PT+FCR+PL+FDS, ECRL+ECRB, supinator+anconeus merged and unshipped; female viewer Version 25 (page 15.52 MB of the 16 MB cap: the next female subject
      needs a triangle-budget trim); Q58 course table verified on sciatic_n;
      docs/GEOMETRY_SOURCES.md); step 2 done; step 3 SHIPPED 18:00 as `ct_vhf_dneck` (semispinalis capitis/cervicis,
      four suboccipitals, longus colli/capitis; splenius sheet + erector sink unshipped, rectus capitis ant/lat too
      small for the frame); step 6 SHIPPED as `ct_vhf_twall` + `ct_vhm_twall` (diaphragm 290/338 cm3, intercostal
      sheets on external_intercostals_r/l standing for all three layers; his 307/307 cm3 above expectation, geometric
      rule only); female viewer Version 26 (333 structures, 14.2 MB), male Version 37 (321, 14.3 MB; also carries
      the Q58 course table); thin sheets are decimated by quadric collapse (`SHEET_IDS`, fast-simplification) because
      vertex clustering laced them with holes; step 8 = Q65 done; his forearm SHIPPED 18:40 as `ct_vhm_forearm` with only FDS 54 / FDP 58 / APL 13 cm3 by
      name (eight regions were >2x expectation and stay unshipped in the label volume; the photographs separate far
      less on him than on her; male viewer Version 38, 14.5 MB); step 7a SHIPPED 2026-09-16 as `ct_vhf_hyoid` (mylohyoid, geniohyoid, genioglossus,
      hyoglossus, styloglossus both sides; the infrahyoid straps came out as fragments and are unshipped, mylohyoid
      and left hyoglossus flagged for review; female viewer Version 27, 343 structures, 14.54 MB); step 4 (her hand
      intrinsics, `ct_vhf_hand`) running as a subagent (first attempt died on the 2026-09-14 rate limit with scripts
      written but no outputs; resumed 2026-09-16). NOTE: three subagents (hand, hyoid, femoral) were killed mid-run by
      the usage limit on 2026-09-14; the hyoid one had written its outputs, the other two had not.
      Her deep-neck + floor-of-mouth muscles were also TRANSFERRED onto him (subject `xfer_vhf2vhm_neck`, 26
      structures, badged doubly derived; male viewer Version 39, 350 structures, 15.41 MB).
      Step 4 SHIPPED as `ct_vhf_hand` (adductor pollicis 10.5 cm3 REVIEW, the three hypothenar muscles, dorsal and
      palmar interossei as groups; the thenar group could not be split and stays unshipped with the lumbricals and
      palmaris brevis; female viewer Version 28, 349 structures, 14.80 MB).
      2026-09-16 cross-body audit: 16 muscles were hers alone and 5 his alone; the TRUNK/NECK direction transfers
      usably (his rhomboid minor shipped onto her as `xfer_vhm2vhf_rhom`, 26.0/13.6 cm3, female viewer Version 29,
      351 structures, 14.89 MB) but the FOREARM/HAND direction does not (brachioradialis 42.5 -> 6.1 cm3, FCU 48.5 ->
      117.7, hand intrinsics halved, 30-92 mm displacement: the two bodies hold their arms differently, so the map
      folds the limb). Those outputs were deleted, not shipped; the limb gaps wait for each body's own photographs.
      Scale audit refreshed against the current pages (153 shared structures, 23 flagged, 7 of them same-method:
      deltoid_l, pectoralis_major_r, scalenus_posterior_l, thyrohyoid_l/r and the middle pharyngeal constrictors --
      the same set as before, so today's subjects introduced NO regression; the constrictor and thyrohyoid flags are
      sub-cm3 CT sheets whose ratio is noise). Next: his forearm (his 1 mm frame
      is gone: needs `stream_vhm_cryosections.py` at full resolution around his forearm), hand intrinsics (step 4),
      head/larynx (step 7), foot (Q59).
- [ ] Q62 (owner 2026-09-14: "a lot of missed muscles, partial or complete -- compare to Z-Anatomy") MUSCLE
      COMPLETENESS PROGRAMME. Measured: 404 muscle entities, 154 with a mesh on both bodies, 250 (128 distinct
      muscles) on neither -- `docs/MUSCLE_GAPS.md` lists them by group with the real-source route each. Z-Anatomy
      (CC BY-SA, read as a CHECKLIST from the file names of its description texts; nothing copied) names 184
      muscle-like structures; the entity list lacks ~15 small ones (articularis genus, dartos, depressor labii
      inferioris, depressor septi nasi, depressor supercilii, levator anguli oris, the auricular muscles). So the
      list is nearly complete and the GEOMETRY is the gap. Order: (1) forearm muscles on her (full-res crops on
      disk, 491 levels both sides; compartments by the interosseous membrane, then a marker watershed on the
      fascial lines with position-rule markers relative to radius/ulna), then him; (2) shoulder girdle: teres
      major/minor split of the cuff label, rhomboid major/minor split, subclavius; (3) deep neck + suboccipitals
      on her 1 mm frame; (4) hand intrinsics from her hand crops; (5) foot: DU female release (Q59) or a foot
      stream; (6) diaphragm, intercostals, pelvic floor; (7) head/larynx from head cryosections at full res;
      (8) the ~15 entities. Regenerate the counts: the snippet in the Q62 commit (scratchpad/muscle_gaps.json).
      PROGRESS 2026-09-16 14:00 → 15:35: Q64 prerequisite (left forearm bones) COMPLETE. Step 1a DONE:
      vhf_left_forearm_compartments_phase1.py separates flexor/extensor compartments (16.1M/12.7M voxels).
      Step 1b DONE: vhf_left_forearm_muscles_phase1b.py initial muscle separation (5 flexor + 4 extensor regions, 28.7M voxels, framework for marker-watershed refinement via white-tophat fascial detection).
      Step 2 DONE (shoulder girdle) -- `split_shoulder_girdle.py`, subjects ct_vhf_shsp / ct_vhm_shsp (teres, rhomboids).
      Step 1 (her RIGHT forearm) SHIPPED as `ct_vhf_forearm` (12 muscles, partial separation).
      Step 4 (her hand intrinsics) SHIPPED as `ct_vhf_hand` (adductor pollicis, hypothenars, interossei as groups; thenar/lumbricals not split).
      Step 3 (deep neck) partially SHIPPED via hyoid muscles `ct_vhf_hyoid` (mylohyoid, geniohyoid, genioglossus, hyoglossus, styloglossus).
      Step 6 (trunk) SHIPPED via `ct_vhf_twall` (diaphragm, intercostals).
      His forearm muscle separation SHIPPED as `ct_vhm_forearm` (3 muscles by name: FDS, FDP, APL; eight regions >2x expectation remain unshipped).
      Viewers: female Version 32 (351 structures, 14.89 MB), male Version 39 (350 structures, 15.41 MB).
      Remaining gaps: her left forearm muscles need marker-watershed refinement; his forearm/hand need full-resolution frame rebuild (his 1 mm cryosection frame lost with container reset); foot intrinsics (Q59 blocked).
- [x] Q66 (2026-09-14, 11:00) REGRESSION found by the refreshed scale audit and fixed: since the male chain was
      rerun this morning (vhm_both deleted for the tarsal renaming), `bundle_to_subjects.py` had re-created
      `ct_vhm_armm` from the recovered bundle (v1 compartments: biceps 475, triceps 675/762 cm3 as meshes) and the
      `v2.done` marker made the chain skip the v2 conversion (labels 386/361, 549/602). Viewer Versions 32-33
      carried the v1 arm muscles. Fix: `--skip ct_vhm_foot ct_vhm_armm ct_vhm_neck` on the bundle copy, guards by
      the manifest's source_file instead of marker files. The converter itself is fine (mesh = label +-2 %,
      measured). Male rebuilt and republished: Version 34 (biceps 350, triceps 581 cm3 as meshes again).
- [x] Q64 (2026-09-16 PHASE 3 DONE: 490 slices segmented, 1.83M bone voxels across 5 bones) Her LEFT forearm bones (radius, ulna, carpals, metacarpals, phalanges).
      Phase 1 DONE: transferred his complete left bones to her frame via humerus affine (det=0.8094, 81% scale).
      Phase 2 DONE: segmentation framework & thresholds. Full-res crops available (arm_full_left.npy, 491 slices × 0.33 mm).
      Phase 3 DONE: full-resolution segmentation complete (brightness > 350, saturation < 0.25); morphological filtering,
      connected components, per-zone bone classification (proximal radius/ulna, mid carpals/metacarpals, distal phalanges).
      Results: radius 143k, ulna 96k, carpals 335k, metacarpals 1.2M, phalanges 55k voxels.
      Scripts: vhf_left_forearm_bones_from_priors.py (phase 1), vhf_left_forearm_segmentation.py (phase 2),
      vhf_left_forearm_segment_phase3.py (phase 3). Output: build/vhf_left_forearm_bones.nii.gz (labeled).
      Next: coordinate transformation to atlas space, per-bone walking refinement, render verification.
      Prerequisite for Q62 step 1 (forearm muscles).
- [x] Q65 (DONE 2026-09-14 13:30: 29 records = 14 sided muscles + midline dartos, in data/muscles; attachments/innervation/
      actions from Gray's and TA, fiber_architecture carries only the type plus an 'evidence' line saying no number was
      verified; nerve entity facial_n_posterior_auricular_branch added and every new compartment listed in its nerve's
      targets; 184 tests pass) The ~15 small muscles Z-Anatomy names that the entity list lacks (articularis genus, dartos, depressor
      labii inferioris, depressor septi nasi, depressor supercilii, levator anguli oris, auricularis anterior/
      superior/posterior, helicis major/minor, tragicus, antitragicus, transverse and oblique auricular): records
      with Gray's/TA attachments and innervation; architecture numbers ONLY where a source gives them, otherwise
      the record says so (no invented PCSA).
- [x] Q60 (DONE 2026-09-14 12:40 by a subagent: `clinical` block in 100 muscle records = 50 muscles, 64 entries from
      the shoulder/elbow/wrist/hand files, every entry with the owner's caveat + sources; 52 elbow tests with Se/Sp
      where he gives one; schema + docs/DATA_MODEL + tests/test_clinical_blocks.py, 179 pass; the head/neck file's
      text extraction has no cards -- owner: re-export it as plain HTML without collapsed sections) The owner's compiled muscle references (Dropbox /claude, 2026-09-14): shoulder, elbow, wrist, hand
      intrinsic, head/neck HTML (function/biomechanics, trigger points, referred pain, adjacent structures,
      per-muscle references, verification appendix; Gray's 43rd, Moore 9th, Neumann 3rd, Travell & Simons
      3rd, PubMed records) -> per-muscle clinical fields in data/muscles with the owner's citations; text
      via the Dropbox fetch tool (each < 5 MB; the shoulder file is 111 k characters). Source-coverage tests.
- [x] Q67 (2026-09-14 13:05) Clinical panel in the viewer: the exporter packs each muscle's `clinical` block
      once per base id (`compact_clinical`, bundle key `clinical`, 17 keys / 0.58 MB in the female bundle)
      and the inspector renders "Clinical reference (owner's compilation)" before Source: per document
      function, trigger points, referred-pain sources, tests with Se/Sp, the caveat, a collapsed source list.
      Pages 14.88 / 15.36 MB; render verified (biceps brachii). Female Version 24, male Version 36.
- [x] Q58 (DONE 2026-09-14 13:50: exporter `depth_profile` = per 20 mm band of atlas y the nerve's shallowest
      point, its skin distance and the nearest skin point; inspector table "Depth below skin along the course"
      with `show` (marks both points) and `needle` (lays the needle-path tool skin -> nerve); sciatic_n 12 rows
      on her, 43-47 mm at the distal thigh; test in tests/test_viewer_template.py) Viewer: show the nerve's depth below the skin along its course (per-level minimum skin distance
      from `skin_depth_vhf.json` is one number; a needle-path preset "sciatic block, subgluteal" that places
      the entry on the skin at the gluteal fold would use the new tool).





- **VH female (Q9) results, 19:25**: `total` full (femoral heads r 24.4
  mm, rms 0.65/0.69; aorta 185 cm3 along its course); `abdominal_muscles`
  WORKS on the unfrozen cadaver: rectus 99/94, external oblique 146/160,
  internal 69/73, transversus n/a (not in the task), QL 43/42, pec major
  199/210, serratus 122/126, latissimus 316/273, erector 440/422,
  transversospinalis 185/173 cm3 -- symmetric and in textbook range, which
  settles that the male's failures were frozen-tissue contrast, not the
  model. Neck: SCM 46/39, trapezius 136/142, levator 29/34. Origin
  `'7.769,-885.229,14.137'`. Ingestion running (`vhf_ingest.sh`), second
  bundle `build/viewer_f`. Trapezius: neck-task label only (the T4-L4 part
  from the trunk task is not unioned yet).
## 2026-09-11, 21:20: container reset -- scratchpad, build/ and the Python packages wiped

The container was rebuilt mid-run (the bone-splitting job was killed with exit 137 first). Everything outside git
is gone: every stacked CT, every cryosection array, every TotalSegmentator output in the scratchpad, the whole
`build/` tree (converted geometry of every subject, both viewer bundles) and the installed packages. The repo was
back at the initial commit and had to be reset to `origin/claude/3d-human-anatomy-atlas-e0kbxe`. Both published
artifacts (male Version 25, female Version 5) are unaffected -- they live on claude.ai. What can be rebuilt from
the repository alone: every `ct_vhm*`/`ct_vhf*` subject whose label volume is in `data/ct_sources/task_outputs`
(the free-task outputs, the cryo-derived male volumes, and now the female lower-limb bones). What cannot,
without re-downloading: the VH male STL geometry (`vhm_both`, DU release, ~133 MB Final STL) and every
cryosection-derived intermediate (1.5 GB of photographs streamed from IDC), the hybrid CT, and the body-surface
volumes (re-derived from the restacked CT in minutes). Lessons: keep every SHIPPED label volume in the
repository (they are small uint8 NIfTIs); write scripts into `scripts/` first and run them from there, never
only in the scratchpad; the pkill pattern rule also applies to heredoc text inside the same tool command
(a python heredoc containing the script name killed the shell again, exit 144).

Rebuild done in this window: pip deps, IDC series af18f5e4 (legs) and b9cf8e7a (torso) re-downloaded and
restacked (`scripts/inspect_dicom_series.py` + `scripts/stack_dicom_series.py`, same grids as before), female
body surface re-derived, `scripts/cryo/vhf_rebuild_bundle.sh` written to reconvert every female subject from the
repository copies and export the female bundle.

## 2026-09-11, 22:50: Q28 done -- the female's lower limb (femur to toes) from her second CT block

`scripts/vhf_lower_limb_bones.py` on IDC series af18f5e4 (femur-to-toes, 0.72 mm, restacked after the reset).
The block starts at MID-THIGH, so the queue item's premise (a shared femoral head) was wrong: the first run's
sphere fits on the legs block (r 31-33 mm, rms 7-8) were fits to the shaft and the 54 mm side disagreement
was the symptom. Registration instead by CONTINUITY across the torso/legs junction: quadratic fits through
the inter-femur distance of the torso's bottom 24 slices and the block's top 24 slices under candidate
shifts (best z -943.0, rms 0.15 mm), agreeing with body-area (-943.5) and subcutaneous-fat-area (-942.5)
fits; femur cross-section areas disagree by 7 mm (a ~2 % partial-volume bias between the 0.94 and 0.72 mm
grids) and are recorded, not used. Shift (+6.0, -3.6, -943.5) mm, +-4 mm in height; the junction gap is
about 3 slices (the blocks are nearly contiguous, like the male's).

Bones: HU >= 200 split at the joints by a distance-transform watershed. What failed first: (1) a 450 mm
"tall junk" rule deleted the whole leg (femur+tibia+foot are one HU component through the joints) -> rule
now needs a mean section < 150 mm2; (2) plain 2-voxel erosion fragmented the fibula (cortical ring 2 voxels
thick) and did not open the ankle; (3) per-slice hole filling closed the ankle crescents and tarsal joint
spaces (holes < 300 mm2 for a few slices) so 4 mm markers fused tibia+foot -> canals are now filled only as
TUBES (2-D holes < 300 mm2 persisting >= 40 mm); (4) the watershed cut every constriction (femoral condyles,
fibular necks) -> fragments re-united where the boundary saddle (max distance-transform on the common face)
is >= 2 mm, i.e. thick bone; a joint bridge is a 1-voxel sheet; (5) that merge also glued the fibula to the
tibia (the boundary ran through the fibular shaft, not the joint) -> the fibula is split from the tibia
label slice by slice (smaller lateral 2-D component seeded from the shaft's middle 70 %, touching slices by
a 2-D watershed from the neighbouring slice). Femur = legs-block component united with the torso block's
TotalSegmentator femur on the legs grid extended 200 slices upward; 3-slice gap closed along z.
Verified by front/side projections (render in the log; femurs whole with heads, patellae anterior, fibulae
lateral to the malleolus, feet plantar-flexed) and by volumes:

| bone | right cm3 | left cm3 | length mm | textbook |
|---|---|---|---|---|
| femur (united) | 402 | 389 | 424 | female femur ~ 43 cm, 350-450 cm3 |
| tibia | 179 | 174 | 362 / 358 | ~ 36 cm, 150-250 cm3 |
| fibula | 43.5 | 43.2 | 351 / 339 | ~ 35 cm, 35-55 cm3 |
| patella | 20.7 | 20.5 | | 15-25 cm3 |
| tarsals (group) | 129 | 132 | foot 223 / 226 | calcaneus+talus+5 ~ 130 cm3; female foot ~ 23 cm |
| metatarsals (group) | 45.5 | 38.4 | | 40-50 cm3 |
| phalanges (group) | 7.5 | 5.9 | | ~ 15 cm3 (distal phalanges below 200 HU on this cadaver) |

Shipped: `data/ct_sources/task_outputs/vhf_lower_limb_bones.nii.gz` (+ `_report.json`, IN the repository this
time), `mappings/vhf_legs_labels.json` (labels 13/14 femur), subject `ct_vhf_legs` exported BEFORE `ct_vhf`
so its united femur wins over the torso stub. Body surface now covers both blocks on one grid
(`scripts/cryo/vhf_whole_body_skin.py`: silhouettes of both CTs, legs resampled with the shift, 1739 slices)
so the depth tags below the knee are real (tibia 1.6 mm at its subcutaneous border, femur 11 mm, patella
3 mm). `data/derived/skin_depth_vhf.json` regenerated (166 rows, min/median). Female artifact Version 6, then Version 7 (subtitle now names the body: the template's header line used to
say "pelvis to ankle + a second specimen" on every bundle; it is now derived from the subject list):
167 meshes / 122 atlas entities, 8.97 MB. Verified in headless Chromium (Playwright, three.js served from the
npm tarball because cdnjs/jsdelivr/unpkg are denied by the network policy): the tibia mesh loads, the depth
tag reads 1.7-18.3 mm, the badge reads the new registration text. Tests 149 pass. Feet remain plane-grouped (same limitation as the male CT feet);
the female's phalanges are under-captured at HU 200.

## Next action

1. Rectus abdominis and the obliques from the photographs by position
   (paired paramedian muscle anterior to the abdominal cavity between
   costal margin and pubis; lateral wall layered by depth) -- the model
   does not find them on this cadaver at any contrast.
2. Review the rule-based muscles slice by slice against the photographs
   (arm compartments, deltoid, cuff, erector columns): each has a
   recorded volume and a render; tighten the rules where a reviewer
   disagrees. Candidates for the same treatment: teres major, pectoralis
   minor, the rhomboids, the forearm compartments (flexor side = the
   side of the interosseous line facing the body midline in this
   pronated position).
3. Separate carpal bones at full photograph resolution (0.33 mm); fix
   the residual right radial-head/ulna boundary.
4. Add frame builders for radius/ulna/hand to
   `audit_landmarks_vs_geometry.py` and audit the upper-limb anchors.
5. Owner correspondence (Kerkhof, Steer) and the commercial
   TotalSegmentator licence remain options for a second, independent
   source of the upper limb.
6. Tendons, ligaments and nerves: data records with anchors only; the
   photographs show them but naming them is slice-by-slice work.
7. Pelvic floor and foot intrinsics remain literature-only.
