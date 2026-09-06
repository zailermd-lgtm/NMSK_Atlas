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
| Above the hip | none yet | **blocked** — see below |

122 landmarks are measured against geometry: median 1.2 mm from the bone
surface, all within 15 mm. 217 anchors, median 0.9 mm from their own bone.

## Blocked on the repository owner

Python 3.13 is needed on the Windows machine — the installed 3.14 free-threaded
build has no pip, so `nibabel` and `scikit-image` cannot be installed:

```
py -3.13 -m pip install nibabel scikit-image
```

Then, for a TotalSegmentator subject that includes the pelvis:

```
python3 scripts/merge_totalsegmentator_masks.py <subject_dir> -o merged.nii.gz
python3 scripts/ingest_volume_geometry.py inspect merged.nii.gz
python3 scripts/ingest_volume_geometry.py propose merged.nii.gz --subject ct01
python3 scripts/ingest_volume_geometry.py convert merged.nii.gz --subject ct01 --origin '<from inspect>'
python3 scripts/audit_landmarks_vs_geometry.py --subject ct01
```

The 0.33 mm `Original 3D STL Models-stl` ingest (`--subject vhm_raw`) is also
waiting. TotalSegmentator's dataset licence (CC BY 4.0) was verified at Zenodo
by the owner, because Zenodo is unreachable from the build machine.

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

## Open, not literature-fixable

- **Real 3D geometry above the hip is still blocked on the repository
  owner's local machine** (Python 3.13 needed for `nibabel`/
  `scikit-image`, see "Blocked on the repository owner" above) — no
  amount of research fixes this, it needs that local CT/TotalSegmentator
  ingest step run.
- Flagged, not yet done: a `gluteus_medius/minimus` **muscle's own**
  motor-point/BoNT injection data search came back empty (its
  *tendon* now has PRP data — different structure, different
  literature) — a legitimate negative finding, not an oversight.
- Not yet covered by the trigger-point/bursa pass: lower limb and deep
  trunk muscles (no reference documents uploaded for those regions
  yet) — same treatment could be extended if more documents arrive.

## Next action

Whatever is unblocked from the list above; otherwise wait on the CT ingest.
