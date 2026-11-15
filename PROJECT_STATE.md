# Project state — resume point

Read this first in a fresh session instead of the conversation. Keep it short (target < 200 lines):
it holds only what is true NOW. When a round closes, move its detail to `docs/PROJECT_HISTORY.md`
(the dated archive, Q1–Q320) and leave one line here. Last updated: 2026-11-15 (after the Q328–Q329 publish).

## 1. Standing rules (owner)
- Real sources only; never present fabricated or sculpted geometry as real. Anything fitted from the
  literature is badged rule-based, with its volume recorded and its citations on its card.
- Reply to the owner in Hebrew. Follow `CLAUDE.md` (targeted reads, delegate verbose work, terse).
- Branch `claude/3d-human-anatomy-atlas-e0kbxe` only; no pull request unless asked. Commit by explicit
  filename (a broad `git add` has twice swept agents' drafts in).
- No model identifier in any repo file except `docs/MODEL_GUIDANCE.md`.
- Nothing in `build/` is deleted without the owner's approval, per deletion.
- Public templates never contain: ultrasound, hounsfield, t1_se, imaging_tissues, tissue table,
  nmskultrasound, acoustic, mrayl, b-mode (tests q226/q228). Private logic lives in `clinical/*.js`.
- Model choice per task: `docs/MODEL_GUIDANCE.md`; log every stretch with `scripts/model_log.py`.

## 2. Scope now (owner, 2026-11-13)
Only **Base · Male** and **Base · Female** move. Combined and Imaging-based are FROZEN "without
changing anything": Combined·M v88, Combined·F v101, Imaging·M v166, Imaging·F v156 — never
republish. `regen_template_only.py all` builds only `base_m base_f`; frozen pages need `--allow-frozen`.

## 3. Pages
| page | build dir | engine | artifact | live version |
|---|---|---|---|---|
| Base · Male | `build/q309/viewer_zan_atlas` | Z | HdYCRuvGP8ESbggoRWCNBF | v91 (Q328–Q329) |
| Base · Female | `build/q309/viewer_base_female` | **Z** (not the own engine) | TiXsQe3eS5ehzN64Aozyth | v86 (Q328–Q329) |
| Combined · M / F (frozen) | viewer_zan_vhm / viewer_zan_female | Z | FeFFPVVTEnPkDm2r7TyDFz / 1GEpFSCZexGZ1GnM1pXxuP | v88 / v101 |
| Imaging · M / F (frozen) | viewer_m_hr / viewer_f_hr | own | RRkf5ELjmk6E8iHdgfbTtq / 1nFD1WUQ7jyovz9vx9pn77 | v166 / v156 |
Hub: LyQVpCZcYWXQT5Ek8M984T. All artifact URLs are `https://claude.ai/artifact/<id>`.

## 4. How things are done
- **Single source → sync:** edit `viewer/<module>/*` (or `clinical/*.js`), run its `scripts/sync_*.py`
  (`--check` to verify); never edit a synced block in a template by hand. Engine-only code goes in both
  templates (`viewer/zan_atlas.template.html` Z, `viewer/atlas_viewer.template.html` own). Concurrent
  agents run syncs as `flock /tmp/nmsk_sync.lock python3 scripts/sync_X.py`.
- **build/ is gitignored and vanishes on a container rebuild.** Restore a page from its artifact:
  `Artifact read paths=[...] out_dir=build/q309/<dir>` then `python3 scripts/restore_built_page.py
  build/q309/<dir>`. Python deps may be missing too: `python3 -m pip install trimesh` (etc.).
- **Regen (once per batch):** `python3 scripts/regen_template_only.py all --src build/q309 --out
  /dev/shm/<tag> --ref build/q309 --expect-changed index.html,nmsk-ultrasound-inline,nmsk-ultrasound-tissues,nmsk-imaging-inline,nmsk-q309-layers,nmsk-pose-rig,nmsk-abbrev,clinical_ultrasound_tissues.json,clinical_ultrasound_tool.js,clinical_imaging_tool.js,parts_data.json,symmetry_q237.json,plexus_groups.json`
  → must end `REGEN_TEMPLATE_ONLY_OK`.
- **Verify** on `/dev/shm/<tag>/<dir>` (background, grep verdict lines only):
  `scripts/anatomy/q318/verify_toprow_q318.py`, `q319/verify_{spine_pose,search,nerves}_q319.py`;
  toolbar buttons are parked — press them with DOM `el.click()`.
- **Publish:** stage only changed files (cmp against `build/q309/<dir>`) in the scratchpad, publish
  `index.html` + `files` map to the artifact `url`. `Artifact list scope:files` gives paths; never read
  a whole page to republish.

## 5. Module map (where to look)
`viewer/selection` marking/show-only/fade/colour · `viewer/q301` toolbar groups (adoptAll, adoptSel,
focus) · `viewer/pose` pose rig, rings, spine levels, `__poseLive`/`__poseRev` · `viewer/q294/measure.js`
dist/angles/Cobb/circ/area/surf/vol/pix · `viewer/q303` nerve casing · `viewer/cut_cap` cut + band ·
`viewer/quickcard` click card (Q321, in progress) · `clinical/ultrasound_tool.js`, `imaging_tool.js`
(private; inlined at regen) · `scripts/anatomy/q236/abbrev.py` abbreviations · `scripts/model_log.py`.

## 6. Decisions on record
- 2026-11-13 freeze (§2). Base priority over reconstructed models; reconstructions revisited later.
- Measure: volume only for a closed manifold mesh; expected value only from a verified/derived/checked
  reference entry, else "No sourced value".
- Scan tool follows Pose (rest reproduces byte-identically); CT/MR stay on rest geometry.
- 2026-11-14, owner delegated these three to me:
  1. **Contraction bulging: not now.** No measured contraction shapes exist for these bodies; a bulge
     would be sculpted geometry. Revisit only as a badged rule-based model (volume conserved from
     published muscle architecture), and only after the Base work below.
  2. **The four give-up muscles per Base page: keep** as they are (repair attempts harmed neighbours).
  3. **Abbreviation clash (hand vs foot / forearm vs leg names → "X-L.2"): fix** — a ".2" must mean a
     second piece of one structure, never a different structure in another region.

## 7. Shipped 2026-11-14 (Base·M v89, Base·F v84) — detail in the history file when archived
- **Q321** click card on every pick (name + Hide/Fade/Show only/Select/Zoom to/More…), beside the model;
  toolbar sheets content-width; abbreviations `X-L (hand)` / `X-L (foot)` instead of `.2`.
- **Q322** Muscle innervation mode (`inn`): data `data/anatomy/innervation_q322.json` (60 muscles, 49 sources
  reviewed), IZ rings from landmarks (174/188 bands; 8 latissimus/teres unplaced), sidecar
  `innervation_q322.json`.
- **Q323** insertions view draws origins (red) / insertions (blue) by tissue class, all / selected only.
- **Q324** attachment points placed for 140/222 muscles (was 17), stricter checks on ligaments/fasciae.
- All verifiers OK on /dev/shm/q325 (Q318 toprow, Q319 spine/search/nerves, Q321, Q322, Q323; both pages,
  desktop + phone for Q321/Q322/Q323).
- Regen `--expect-changed` list now also needs `innervation_q322.json`, `clinical_needle_tool.js` (while the
  needle tool changes) and `__ANATOMY_manifest` (record-link patch, Q327).
- Shipped 2026-11-15 (Base·M v90, Base·F v85): **Q325** injection clip (needle plans on the posed body,
  "Show in scan" in/out of plane, play control; verifier `scripts/anatomy/q325/verify_needle_clip_q325.py`);
  **Q326** latissimus IZ projected from the skin line (178/188 bands); **Q327** `#pl-box #rs-box #sa-bar`
  hidden in every mode; 10 borrowed records removed (ligament/fascia never take a muscle's or bone's
  record; `scripts/zanatomy/patch_manifest_records_q327.py` runs in regen). 18 verifier verdicts OK.

## 8. Open (Base pages)
- Injection clip: link needle tool → scan `setNeedle` + play control; needle tool still plans on rest
  geometry (scan already shows a needle placed in a posed state).
- Toolbar at phone width with the five new Measure buttons (covered by the Q321 size audit).
- Pre-existing test failures, not caused by recent work: `test_q255_us_rotation_thickness`,
  `test_q272_modes` ×2.
- Own-engine pose hooks (`viewer/pose/glue_own.js`) untested in a browser — only frozen pages use them.

## 9. Next action
Published 2026-11-15: Base·M v91, Base·F v86 — Q328 saved injection points + motor points follow Pose
(halos already did; verifier `scripts/anatomy/q328/verify_overlays_pose_q328.py`), Q329 mode display
state kept out of Undo (`setModeColours`, NMSKHistory beginScope/endScope; verifier
`scripts/anatomy/q329/verify_mode_undo_q329.py`). 22 verifier verdicts OK on /dev/shm/q330.
Done, committed, not yet published: **Q331** Base·F motor points (193, key `base_f`; builder
`motor_points_q187.py --viewers base_f --merge`); audit found 0 points outside their muscle on either Base
body (the old "1–11 mm outside" was an unsigned depth — closed). Regen now copies
`clinical/data/motor_points.json` → `clinical_motor_points.json` (add it to --expect-changed).
**Q332** saved points' vessel/nerve readouts re-measured on the posed body (verifier
`scripts/anatomy/q332/verify_saved_readouts_q332.py`); risk region cache keyed by pose.
Owner feedback 2026-11-15 (three more agents, all Base only):
- **Q333** something is wrong in the LEFT ANTERIOR CHEST of Base·Female — diagnose (screenshots, left/right
  and male comparison, Q319 repairs as suspects, `*.q318` backups) and fix at the source; script under
  `scripts/anatomy/q333/`, applied to build/ only by the main thread.
- **Q334** no imaginary seam lines between skin regions (and other split classes): find the cause, fix in
  the engine or normals; `scripts/anatomy/q334/verify_skin_seams_q334.py`.
- **Q335** click card: default docked top-left, draggable, position remembered; leader line only when the
  structure is not marked in colour (setting); a ⋮ menu beside every window's drag grip; groups /
  adjacent / related chips open under the name or at the very bottom, width = content, never a full row.
  Added by the owner: the leader line must never cross the body; More… expands the SAME window in place
  (today it swaps to another window elsewhere).
- **Q336** genital / perineal region "not covered correctly" on the Base bodies — diagnose skin coverage
  and structures per sex, checklist from Gray's (1918 public-domain edition where reachable) + vetted
  sources, complete with real geometry only; `scripts/anatomy/q336/`, `docs/Q336_genital_region.md`.
- **Q337** read-only whole-body QA sweep of both Base bodies → ranked defect list
  (scratchpad `q337_defects.md`); fixes are dispatched from it.
- **Q338** hand / fingers: palmar vessels out of place "and more" — check at rest and posed (rig weights),
  fix rig / records; misplaced source meshes are reported with options, not redrawn;
  `scripts/anatomy/q338/verify_hand_q338.py`.
Owner 2026-11-15: finish to a PUBLISHABLE level soon, work on everything in parallel. Geometry fixes come
as `--page-dir` scripts; the main thread applies them to build/q309 in order (Q333, Q336, Q338), then one
regen, all verifiers, publish.
Open: deltoid middle-belly motor rule fails on Base·F (axillary-level landmark proxy too low); triceps /
gastrocnemius IZ values in data/muscles/* still suspicious (not displayed); 82 muscles/body without attachment points; teres major /
latissimus iliac-line IZ bands unplaced.
