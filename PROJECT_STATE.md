# Project state — resume point

Read this first in a fresh session instead of the conversation. Keep it short (target < 200 lines):
it holds only what is true NOW. When a round closes, move its detail to `docs/PROJECT_HISTORY.md`
(the dated archive, Q1–Q320) and leave one line here. Last updated: 2026-11-15 22:45 UTC (after the Q331–Q338 interim publish).

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
| Base · Male | `build/q309/viewer_zan_atlas` | Z | HdYCRuvGP8ESbggoRWCNBF | v94 (Q340–Q344) |
| Base · Female | `build/q309/viewer_base_female` | **Z** (not the own engine) | TiXsQe3eS5ehzN64Aozyth | v88 (Q334–Q339 + Q336) |
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

## 7. On the live Base pages (rounds Q321–Q346; detail in docs/PROJECT_HISTORY.md)
Name card on every click (docked top-left, draggable, ⋮ menu; Related structures ▾ with adjacent / related /
functional group / muscle parts / myofascial lines / innervation families) · Muscle innervation mode (60
muscles, IZ bands 178/188) · Insertions view (origins/insertions by tissue class; 140/222 muscles placed) ·
injection clip on the posed body, overlays and saved readouts follow the pose · true (non-mirrored) view
with R/L marker · seamless skin (Base·F trunk line remains) · hand rig re-weighted, palmar arch above the
flexor tendons · Base·F: chest wall fix, perineal skin, motor points · phone one-row toolbar.

## 8. Open (Base pages) — see also "Other open" in §9
- Pre-existing test failures, not caused by recent work: `test_q255_us_rotation_thickness`,
  `test_q272_modes` ×2, `test_q298::test_relations_exist…`.
- Own-engine pose hooks (`viewer/pose/glue_own.js`) untested in a browser — only frozen pages use them.

## 9. Next action
(Rewritten 2026-11-16 ~10:30 UTC. Detail of closed rounds Q325–Q346: docs/PROJECT_HISTORY.md.)

**Live:** Base·M **v94** (1794823698-de21) = regen /dev/shm/q346, all 17 verifier verdicts OK.
Base·F **v88** (q345) — q346 verifier run for Base·F still going (scratchpad `v346.txt`); publish
`pub6/viewer_base_female` (index.html, geo_01, geo_02, clinical tools x3, groups_q342.json) when it ends OK.
q346 = Q340 palmar arch conform, Q343 Related structures (parts chooser, myofascial lines, innervation
families), Q344-A/B readability and overlap fixes, move.js drop fix.

**Committed after q346 was built (needs the next regen):** Q348 reference pass from the owner's books
(`docs/Q348_reference_pass.md`): 151/214 root levels checked, 18 myofascial lines (3 trunk-rotation slings
added; "horizontal" stays disabled), 11 muscle parts `verified_book`, perineal checklist + 2 synonyms.

**In flight (agents, Opus 5.5 high, no browser, do not commit):**
- Q347 injection guide in the injection mode (Guide section, "Use site N", "Start scan here", at-risk
  highlight) — holds `clinical/needle_tool.js`, `scripts/regen_template_only.py`,
  `scripts/clinical/stage_clinical_files.py`, `scripts/anatomy/q347/`, `scripts/clinical/build_injection_guide_q347.py`,
  `tests/test_q347_injection_guide.py`. Its sibling file must be added to `--expect-changed`.
- Q349 hand: finger nerve/artery order (nerve palmar to artery in the fingers, dorsal in the palm, crossing
  at the finger root; Mannan pp. 166, 168) + superficial venous arch to the arterial arch depth. Delivers
  `scripts/anatomy/q349/conform_fingers_q349.py`; the MAIN THREAD applies it to build/q309 (originals `*.q349`).
- Q350: latissimus iliac IZ line ends at the posterior outer lip of the crest; `iliac_crest_top` level
  check vs L3/L4; record corrections (serratus posterior superior T2–T5, pectoralis minor both pectoral
  nerves, foot interossei exception).
**Then:** commit each agent's files by name → apply Q349 to build/q309 → one regen (worktree of HEAD if an
agent still holds files) → verifiers (q347, q338 hand, q322 innervation, q343 groups, q321 quickcard,
q344 clinical UI at least; full set if time) → publish both pages (cmp against /dev/shm/q346 or `pub6`).
**After that:** restart the Q337 whole-body QA sweep as a fresh read-only agent.

Regen --expect-changed (current): index.html,nmsk-ultrasound-inline,nmsk-ultrasound-tissues,
nmsk-imaging-inline,nmsk-q309-layers,nmsk-pose-rig,nmsk-abbrev,nmsk-q306,clinical_ultrasound_tissues.json,
clinical_ultrasound_tool.js,clinical_imaging_tool.js,clinical_needle_tool.js,clinical_motor_points.json,
parts_data.json,symmetry_q237.json,plexus_groups.json,innervation_q322.json,groups_q342.json,
__ANATOMY_manifest,__ANATOMY_files,atlas_viewer_base_female_geo_03.txt (+ the Q347 sibling).

**Owner's books** (Dropbox `/claude`, KNOWLEDGE ONLY: facts + page citations; no prose/figures copied; PDFs
never in the repo): nine PDFs in the scratchpad `refs/` (re-download with Dropbox `download_link` + curl
after a rebuild; network is unrestricted since 2026-11-16). Never touch other Dropbox folders.

**Decisions taken by the main thread (owner delegated):** vulva skin accepted as an overlapping real
surface; "horizontal" myofascial class shown disabled (no sourced line); rule-based muscle-part partitions
are NOT drawn (parts without a mesh are listed greyed); palmar conform approved; Q348 geometry findings
applied through guarded conform scripts (Q349/Q350), a structure whose guard fails is left as is.
**Owner's open calls:** scan-mode badge "סימולציה מהמשים" (typo? pinned by two tests); larger breast gap on
Base·F (`_r` pectoralis thin, R/L 0.76); Base·M perineal muscles / rectum (only real source is the frozen
Imaging·M page); unfreeze question for the mirrored frozen pages; the neonatal-procedures "Atlas" PDF
(uploaded by mistake?).
**Do not run** `sync_learn_q283.py` / `sync_hub_link_q251.py`: the template is ahead of their source (Q312
edits were made in the template); running them reverts Q312.
**Other open:** Base·F trunk seam (geometry build); deltoid middle-belly motor rule on Base·F; 82
muscles/body without attachment points; teres major IZ band (no rule); thumb CMC rest pose outside its
ROM; 63 muscles' root levels unchecked; `test_q298::test_relations_exist…` fails (derived relations lack
new foot ids); Q292 `lib292.push_dir` decay bug unfixed in the library.
