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
    own attachment text) found 3 more mismatches of the same shape as (9)
    above, all in `_match()` in `scripts/generate_anchors.py`. One is
    fixed; two are deliberately left open because every attempted general
    fix broke other, previously-correct anchors elsewhere in the corpus —
    recorded here in enough detail to fix properly later, rather than
    patched into a worse state under time pressure.
    - **Fixed**: `plantar_interossei_r/l`'s insertion matched a landmark
      reserved for dorsal interossei ("digits 2-4") because the ordinal
      check only required the two digit-sets to *overlap* (`3,4,5` and
      `2,3,4` share the 4), not that one contain the other. Changed to
      require a subset relationship. Verified against the full 808-endpoint
      corpus: exactly those 2 anchors removed, nothing else changed.
    - **Open**: `rhomboid_minor_r/l`'s insertion matches "spine of scapula
      (trapezius insertion, deltoid origin)" instead of "medial (vertebral)
      border (rhomboids, serratus anterior insertion)" — the correct
      landmark's own first two tokens are `('medial', 'vertebral')`, and no
      muscle's prose says "vertebral", so it never becomes a candidate.
      Gating on site-only tokens (stripping the parenthetical qualifier)
      fixes this but breaks `gluteus_medius_r/l`'s origin the same way in
      the other direction — its correct landmark's site-only gate becomes
      `('external', 'surface')`, and the text says "external ILIUM", never
      "surface". A gate based on "at least N site words match, not
      specifically the first two" fixes both of those but then admits
      `adductor_longus`, `iliopsoas` and `obturator_externus` as false
      candidates for gluteus medius/minimus's own landmarks, purely because
      their unrelated text happens to contain 2 of that landmark's 8 site
      words ("external", "surface"). No fix attempted so far survives the
      whole corpus.
    - **Open**: `extensor_carpi_ulnaris_r/l`'s origin matches "humeral head
      (glenohumeral joint)" — the shoulder — instead of "lateral epicondyle
      (common extensor origin)" — the elbow, ~330mm away. Both candidates
      tie exactly on site-hit count and purity; the final tiebreaker
      (fewer total tokens wins) picks the shorter name regardless of fit.
      Dropping that tiebreaker turns this specific case into a correct
      refusal, but also turns several previously-*correctly-resolved*
      ties (`brachialis`'s insertion among others) into refusals, because
      they relied on the same flawed tiebreaker for a right answer some of
      the time. A real fix needs the tiebreaker to know something about
      the muscle being anchored, not just the two candidate landmarks in
      isolation — e.g. does either candidate's own attachment-list name
      this muscle — which `_match()` does not currently receive.
    - `vastus_lateralis_r/l`'s origin (item 9 above) turns out to be the
      same class of problem as `extensor_carpi_ulnaris`: the correct
      landmark ("gluteal tuberosity/linea aspera ... vastus
      medialis/lateralis ...") explicitly names this muscle in its own
      attachment list, which is exactly the "own-name" signal that would
      fix it — reinforcing that a `_match()` signature change (passing the
      owning muscle's id/name in) is the right next step for all three
      open items at once, rather than three separate patches.

## Next action

Whatever is unblocked from the list above; otherwise wait on the CT ingest.
