# Project state — resume point

Read this first in a fresh session instead of the conversation. Keep it short (target < 200 lines):
it holds only what is true NOW. When a round closes, move its detail to `docs/PROJECT_HISTORY.md`
(the dated archive, Q1–Q320) and leave one line here. Last updated: 2026-11-14.

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
| Base · Male | `build/q309/viewer_zan_atlas` | Z | HdYCRuvGP8ESbggoRWCNBF | v88 (Q320) |
| Base · Female | `build/q309/viewer_base_female` | **Z** (not the own engine) | TiXsQe3eS5ehzN64Aozyth | v83 (Q320) |
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

## 7. In progress
- **Q321 click card: done (committed).** `viewer/quickcard` + `scripts/anatomy/q321/patch_q321.py`. Cause of
  "nothing opens": on desktop `body.lay-model` hid `#info`. Card: name · layer · side + Hide/Fade/Show only/
  Select/Zoom to/More…, beside the model with a leader line; on phone below the top bar / above the title.
  Verifier `Q321_QUICKCARD_OK`: Base·F 1400 (35), Base·M 1400, Base·M 390 (33). Toolbar sheets now
  content-width (Search 760→574, Dissection →336, Imaging →220, Page →220; Systems/Navigate/Favorites stay).
  Ships at the next regen.
- **Q321 abbreviation clash: done in source** (`abbrev.py` region split; 28 structures per Base page,
  e.g. `DI-L (hand)` / `DI-L (foot)`); reaches the pages at the next regen. Same structure from two
  sources on Base·F (urinary bladder, internal iliac / pudendal veins) keeps `.2` — decided: one
  structure, so `.2` fits the rule.

- **Q322 MUSCLE INNERVATION mode.** Source: Güvener et al., EUR J PRM 2026;62(5):441-59, DOI
  10.23736/S1973-9087.26.09497-9 (CC BY-NC-ND: facts only, PDF not in repo). Steps 1–2 DONE (committed):
  `data/anatomy/innervation_q322.json` (60 muscles, 94 IZ bands, 51 landmarks, 49 sources reviewed),
  private `clinical/data/innervation_injection_q322.json`, `docs/Q322_innervation_sources.md`, builders
  `scripts/anatomy/q322/build_q322.py` + `scripts/clinical/build_innervation_private_q322.py`, test (10).
  Step 3 (agent): mode `inn` in viewer/modes + new `viewer/innervation`, IZ rings placed from landmarks
  by `scripts/anatomy/q322/place_iz_q322.py` (rule-based, badged). Flagged repo data to check:
  triceps lateral/medial head IZ looks swapped (data/muscles/upper_limb/triceps_brachii_*), gastrocnemius
  75/80% likely from the wrong end; `median_n` trunk missing on Base pages.
- **Q323 insertions view: fixed (committed, verifier OK on both Base pages × both sizes).** Cause: the
  preset only changed layer opacities; 0 of 244 placed points were drawn. Now `btn-insert` → parts_ui
  attachments view: origin red / insertion blue, class checkboxes with counts, all / selected only.
  Template glue `scripts/anatomy/q323/patch_q323.py`; `parts_data.json` rows gain `sc` (class) at regen.
  Coverage gap: Base·M only 17/222 muscles, 22/174 ligaments placed → **Q324 agent placing the rest**
  (same `end_snap_bone` method; skip with a reason, never guess).

## 8. Open (Base pages)
- Injection clip: link needle tool → scan `setNeedle` + play control; needle tool still plans on rest
  geometry (scan already shows a needle placed in a posed state).
- Toolbar at phone width with the five new Measure buttons (covered by the Q321 size audit).
- Pre-existing test failures, not caused by recent work: `test_q255_us_rotation_thickness`,
  `test_q272_modes` ×2.
- Own-engine pose hooks (`viewer/pose/glue_own.js`) untested in a browser — only frozen pages use them.

## 9. Next action
When the Q321 agents report: check sync (`--check`), commit by filename, one regen of base_m base_f,
verify (Q318/Q319 verifiers + Q321 quickcard), publish both Base pages, log the stretch, update §3/§7
here and move Q321's detail to the history file.
