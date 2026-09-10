# Project state

Resume point for a fresh session. Updated at milestones; see `docs/ROADMAP.md`
for the long-form plan and `docs/GEOMETRY_SOURCES.md` for licensing.

## What this is

A 3D atlas of the human musculoskeletal, neural and vascular systems, built to
plan musculoskeletal injections — PRP, and botulinum toxin for spasticity — as
well as to serve as a general atlas, an ultrasound and cross-section reference,
and a comparison against CT and MRI. Target resolution is sub-1 mm³/voxel.
The repository is proprietary and sellable; no CC BY-SA source may enter it.

Branch: `claude/3d-human-anatomy-atlas-e0kbxe`. 149 tests pass (includes bone-only frame derivation for CT).

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

**Placement of a subject without femoral heads**: the atlas origin cannot
be sphere-fitted on s1159, so it is placed by a translation that puts its
sacrum centroid where s0913's sacrum centroid sits in the atlas frame
(origin `-6.232, 85.723, 199.149` atlas mm; L5/L4/T12 centroids would give
origins within ~15 mm of this -- two different bodies, spine curvature
differs -- so this is a convention, not a registration, and the viewer
badge says so). Same convention will place any head/neck-only case via a
shared vertebra.

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

## Next action

1. **Owner uploads `s0913/ct.nii.gz`** (from the Zenodo zip already on
   their machine) → run the free TotalSegmentator tasks listed in the
   2026-09-09 sweep table on it → extend `mappings/totalsegmentator_labels.json`
   with the new task label maps → `merge` → `ingest_volume_geometry.py`
   → audit → combined viewer bundle. Environment is already installed and
   weights pre-fetched (`scratchpad/ts_env/setup.log`).
2. Owner checks licenses on MorphoSource P419 (Kerkhof) and OSF avq7d
   (Steer); downloads Grant (Zenodo 3464747, CC BY) and Havelková (Zenodo
   3954024, CC BY); uploads whatever is CC BY / CC0. Each needs a small
   STL/PLY ingest path (the VH STL ingest is the template) and, for the
   foot, new tarsal bone entities in `data/skeleton/bones.json`.
3. Pelvic floor and foot intrinsics remain literature-only until a source
   appears; that search is now exhausted for open data.
