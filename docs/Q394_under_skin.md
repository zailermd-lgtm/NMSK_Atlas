# Q394 — everything that belongs under the skin, under the skin (Base · Male / Base · Female)

Owner, 2026-11-25: "You must make sure that all the structures that should be under the skin ARE under the skin!!"

Tools (`scripts/anatomy/q394/`): `under_skin_q394.py` (census library), `tuck_under_skin_q394.py` (rule-based tuck, dry run /
`--write`), `causes_q394.py` (cause class per entry), `verify_under_skin_q394.py` (the verifier). Test `tests/test_q394_under_skin.py`.
Reports: `data/derived/Q394_under_skin_<page>.json` (census before / after, causes, tuck), open defects
`data/derived/Q394_open_defects_<page>.json` (read by the verifier). Base pages only; frozen pages untouched; no template change.
Work done on private copies of `build/q309`; `build/` not written.

## The test
- **Skin** = every `sys: skin` piece except the nail plates. Each slab's faces are split into outer sheet / inner sheet / walls by
  Q353 `Geo.sheets`.
- **Outside** (Q353 `outside_count`, unchanged in meaning): a vertex lies on the outer side of the closest outer-sheet triangle,
  not deeper than the inner sheet, and over the skin (tangential offset < 2 mm, not beyond the border of an opening).
- Three corrections were needed to make the count complete and true (each measured on the pages):
  1. Q353 tested only vertices within 12 mm of a skin vertex. Every vertex is now tested (exact point–triangle distance over the
     24 nearest triangles).
  2. Q353's outer / inner label is decided per face from the direction away from the nearest bone vertices. Next to a bone of
     another segment it is the wrong way round: on Base · F the lateral thoracic skin beside the humerus carried a 1020-face
     patch of its inner sheet labelled outer (and the outer sheet above it labelled inner). With the 12 mm limit removed that
     made ribs "55 mm outside"; inside the limit it is what produced the long-standing "latissimus dorsi 10.5 / 11.4 mm out".
     Q394 keeps Q353's vote but takes it once per connected sheet patch (`sheet_vote`), and keeps the new labels for a piece
     only when they agree better with the slab (a sheet face's partner across the slab must carry the other label).
  3. Every vertex the test counts outside is confirmed by an independent ray-parity test against the outer-labelled sheet
     (five axis rays, majority): a ray from inside the body crosses it an odd number of times. This needs only that one of a
     slab's two sheets is labelled outer, so it is immune to swapped patches.
- **Poses**: the page's own rig (`data/anatomy/pose_rig_base_{m,f}.json`), forward kinematics incl. the spine regions exactly as
  `viewer/pose/pose.js fk`, dual-quaternion blend (`scripts/anatomy/q384/pose_replica_q384.py`); skin and structures posed by the
  same rig, then the same test. States (`STATES`): rest; shoulders abducted 120°; shoulders flexed 120°; right shoulder abd 90° +
  flex 30° with both elbows at 120°; both hips and knees 90°/90°; neck flexed 45° + rotated 40°; neck extended 45° + lateral bend
  30°; trunk (lumbar flexion 45°, thoracic flexion 20° + rotation 20°).

## The set, and what is excluded (with the reason)
Every structure of the page that is not skin, minus (`under_skin_q394.EXCLUDE`):

| excluded | reason |
|---|---|
| eyeball parts (cornea, sclera, iris, lens, chambers, segments, retina, choroid, conjunctiva) | the front of the eye is the body surface in the palpebral fissure |
| tarsal plates, lid margins, caruncle, plica, puncta | the free lid margin and the caruncle are surface |
| teeth, gingiva | the crowns lie in the open mouth |
| tongue, oral / lip / buccal mucosa, palate, uvula | the mouth opening |
| nasal vestibule / cavity mucosa | the nostrils |
| external acoustic meatus, tympanic membrane, auricular cartilage | the ear's skin side and canal open to the surface |
| glans, prepuce, urethral / vaginal orifices, labia, clitoris, vestibule, vulva, anal canal / anus, scrotum, penis, corpora | perineal openings and external genital surface parts |
| hair, nails (bed, matrix, lunula) | surface |
| (skin pieces themselves, incl. nail plates) | they are the surface |

Breast tissue is **in** the set (Q353 tucked it to 0 outside; Q285's gate allows none > 1 mm).

## Census before (source = `build/q309` as of 2026-11-25, Base·M v111 / Base·F v108)
Structures of the set / vertices outside / deepest (mm). Poses include everything outside at rest.

| state | Base · M before | Base · M after | Base · F before | Base · F after |
|---|---|---|---|---|
| rest | 159 / 12193 / 13.9 | 103 / 9011 / 13.9 | 205 / 12009 / 13.8 | 123 / 7714 / 13.8 |
| shoulders abd 120 | 179 / 15953 / 195 | 139 / 12426 / 84 | 235 / 16459 / 283 | 177 / 11684 / 261 |
| shoulders flex 120 | 213 / 19674 / 440 | 175 / 16363 / 84 | 262 / 18806 / 398 | 207 / 13982 / 398 |
| arm + elbows 120 | 188 / 15580 / 84 | 148 / 12310 / 84 | 237 / 16363 / 326 | 178 / 11698 / 242 |
| hips / knees 90 | 187 / 17969 / 383 | 150 / 13689 / 382 | 232 / 17617 / 369 | 177 / 12607 / 32 |
| neck flex + rot | 168 / 12739 / 13.9 | 121 / 9535 / 13.9 | 215 / 12381 / 13.8 | 154 / 8081 / 13.8 |
| neck ext + lat | 164 / 12634 / 21.8 | 113 / 9376 / 19.5 | 205 / 12430 / 16.6 | 140 / 8161 / 16.6 |
| trunk | 171 / 13605 / 63.0 | 137 / 10157 / 58.0 | 210 / 14318 / 94.3 | 164 / 9250 / 94.3 |

What the old count said and was not true: the long-standing "latissimus dorsi 10.5 / 11.4 mm out, triceps long head up to
1.0 mm" (Q377 / Q379 guard) and, with the 12 mm limit removed, ribs / intercostals / serratus "40–55 mm out" and biceps
"15 mm out" on Base·F were the swapped outer / inner patch (point 2 above). Corrected, what is really outside there is small:
Base·F latissimus dorsi R 1 vertex 0.42 mm, triceps long head L 12 vertices 1.0 mm / R 5 vertices 0.37 mm, biceps 0.03 mm;
Base·M triceps long head 0.5 / 0.7 mm; ribs / intercostals / serratus none. All of these were tucked except Base·F triceps long
head L (open, reason in the list). The Q353-positive vertices the parity test rejected (fingers' dorsal
vessels and nerves, upper teeth, the nasal septum) are counted per state by the verifier ("parity-rejected").

### Cause class (rest, before the tuck; `causes_q394.py`, in the report)
- **(a) already outside in the oldest kept page** (`*.q318` backups): Base·M 158 of 159, Base·F 188 of 205 — the Z-Anatomy source
  as fitted to these bodies (Base·F incl. its Q250 body deformation) and the Q295 fat / soft-tissue compartments (marching cubes
  from her CT / his cryosections, TPS-registered with a 9–11 mm p95 error; built before Q318).
- **(b) our own later edits**: Base·M 1 (saphenous n. R, Q357 in-bone conform moved it 6 mm), Base·F 17: Q357 in-bone conform
  (great saphenous v. L, saphenous n. R, dorsal digital aa. of hand R, facial vv., inferior labial aa.), Q366 (SCM L/R, dorsal
  digital branches of the ulnar n. with the Q377 hand skin), Q358 / Q336 perineum (perineal body, external pudendal v., deep
  pelvic / thigh fat), breast_ct_r (Q333/Q353/Q360/Q379 chest). 12 of the 17 were tucked; Q357's were **not undone**: undoing
  puts the vessel / nerve back inside the bone (the defect Q357 fixed); the tuck was refused for 5 (flipped faces on the thin
  tubes, no room) — listed open.
- **(d) thin skin / skin hole** (flag on (a)/(b)): the slab under the closest outer point is < 0.5 mm thick or has no inner sheet
  — Base·M 46, Base·F 80 (toes, finger tips, lips, eyelids, perineal patch borders).
- **(c) pose only**: Base·M 448, Base·F 616 (state, structure) entries outside in a pose and not at rest.

## What was done
1. **Rule-based tuck** (`tuck_under_skin_q394.py`, Q353's tuck rule completed): outside vertices to 0.3 mm under the inner
   sheet along its normal, Lipschitz envelope from the most local slope (0.5) to Q353's (0.15), a vertex that would enter a bone
   held and the move faded in around it (3 mm), bones and skin never moved. Guards per structure: move ≤ 12 mm, 0 outside
   after, volume change ≤ 2 % (closed mesh; open mesh: area ≤ 2 %), flipped ≤ 0.5 % of moved faces, no vertex newly in bone.
   **Base·M 56 structures fixed (3182 vertices; max move 8.4 mm, volume ≤ 1.95 %), Base·F 84 (4297 vertices; max move 5.7 mm,
   volume ≤ 1.56 %).** Each card: "Q394: rule-based tuck under the skin …" with counts, moves and the volume / area change.
   Vertex / triangle counts and order unchanged; 16-bit round trip ≤ 0.008 mm. Two Base·F compartments keep one vertex each at
   0.003 / 0.13 mm (a seam where the parity test is unstable), documented.
2. **Pose rig, fat compartments** (`rig_fat_q394.py`): measured, reproducible — the hand / forearm subcutaneous fat is weighted
   to the pelvis and T12 (Base·F fat_subcut_hand_l: 308 vertices led by the pelvis), so with the arm raised it stays by the hip
   (up to 440 mm "outside"). Compartments that come out in a pose take the weights of the nearest non-fat structures (KNN 4); a
   compartment is kept only if no state got worse (two passes): **Base·M 15, Base·F 18 compartments re-weighted**; deepest pose
   residual Base·M 440 → 84 mm (shoulder flexion), Base·F hips/knees 369 → 32 mm. The other 22 / 21 compartments got worse in
   some state (contact: arm against the flank gives arm donors to flank fat) and keep their weights. Rest pose unchanged
   (weights only). No other structure's weights changed.
3. Nothing else: no skin moved, no bone moved, no Q357 undo.

Guards re-run: `scripts/anatomy/q388/verify_nerve_course_q388.py` on both patched pages — 13 FAIL checks, the same 13 (same
verdict lines) as on the source; no structure newly outside at rest.

## Open defects (the verifier's list: `data/derived/Q394_open_defects_<page>.json`, every (state, structure) with numbers)
At rest Base·M 103 structures (83 deeper than 0.5 mm), Base·F 123 (102). By kind:
- **Fat / soft-tissue compartments (Q295)**, Base·M 31, Base·F 29: subcutaneous / unlabelled thigh 10–14 mm (moves of 20–27 mm
  needed, cap 12; volume 4–8 %), thorax / abdomen / limbs < 3 mm but volume or area change > 2 % (a thin shell under the skin
  shrinks when its outer face is pushed in). Real fix: rebuild the compartments against the page skin, not a tuck.
- **Toes / foot** (Base·M 33, Base·F 26) and **fingers / hand** (28 / 29): phalanges, capsules, collateral ligaments, digital
  nerves and vessels 0.5–9.5 mm out on the plantar / dorsal toe skin and the finger skin. Bones are not moved; the soft structures
  have no room between skin and bone (held by the bone guard) or flip their thin faces. Cause: the toe / finger skin of the
  source fit is too thin / too close (most flagged (d)); the right foot of Base·M is worse than the left.
- **Face / head** (Base·M 4, Base·F 20): Base·F maxilla 8.4 mm under the philtrum (bone), depressor anguli oris / labii inferioris
  5–6 mm, inferior alveolar / mental vessels and V3 mental branch 2.5–4.8 mm (buccal region R), orbicularis oris 3.6–3.8 mm;
  temporoparietalis / superficial cervical fascia / superficial temporal a. behind the ear on Base·M fixed or < 1.2 mm.
- **Pose (c)**: after the tuck and the rig fix Base·M 439, Base·F 602 pose-only entries (most fat compartments; also lateral
  intermuscular septum R 84 / 64 mm with the arm moved, lateral pectoral n. L 71 mm in shoulder abduction on Base·M,
  latissimus dorsi L 45 mm on Base·F in abduction). Their rig weights were not changed (no rule passed the no-worse test).

Verifier on the patched pages (with the new rig): see `docs` section "Verifier" below; it prints `Q394_UNDER_SKIN_FAIL` because the
open defects deeper than 0.5 mm are documented, not fixed. Nothing outside is undocumented.

## Verifier
`python3 scripts/anatomy/q394/verify_under_skin_q394.py --page-dir build/q309/<dir>` (or a regenerated page; `--rig` for an
unapplied rig, `--quiet` for the state lines only). One `OK` / `FAIL` line per state, then `Q394_UNDER_SKIN_OK` /
`Q394_UNDER_SKIN_FAIL <page>: residuals, undocumented, documented >= 0.5 mm`. `OK` needs every structure of the set at 0 vertices
outside in every state, or only documented residuals each < 0.5 mm. Runtime ≈ 8–11 min per page (4 CPUs).

## Limits (honest)
- The pose census uses the numpy port of the page's rig (checked against the page by Q384's verifier), not the browser.
- The parity test and the 2 mm "over the skin" test can still mis-call single vertices at seams (two such at 0.003 / 0.13 mm).
- The skin's own defects (toes, finger tips, philtrum, perineal patch borders) are the cause of most remaining rest entries;
  per the rule the skin was not moved to hide them.
- Ear skin pieces are single sheets (no outer / inner): they close the surface for the parity test only.
