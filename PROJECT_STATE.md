# Project state — resume point

Read this first in a fresh session instead of the conversation. Keep it short (target < 200 lines):
it holds only what is true NOW. When a round closes, move its detail to `docs/PROJECT_HISTORY.md`
(the dated archive, Q1–Q320) and leave one line here. Last updated: 2026-11-17 ~00:30 UTC (after the Q357/Q358 publish).

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
| Base · Male | `build/q309/viewer_zan_atlas` | Z | HdYCRuvGP8ESbggoRWCNBF | v97 (Q353–Q358) |
| Base · Female | `build/q309/viewer_base_female` | **Z** (not the own engine) | TiXsQe3eS5ehzN64Aozyth | v92 (Q353–Q358) |
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
  `test_q272_modes` ×2, `test_q298::test_relations_exist…`, `test_cut_mode_q197::test_slice_thickness_in_both_engines`,
  `test_q309::test_the_measured_counts…` (build/q309 has 436 muscular, pin says 434), `test_symmetry::test_every_reference…`.
- Own-engine pose hooks (`viewer/pose/glue_own.js`) untested in a browser — only frozen pages use them.

## 9. Next action
(Rewritten 2026-11-16 ~14:40 UTC. Detail of closed rounds Q325–Q346: docs/PROJECT_HISTORY.md.)

**Live:** Base·M **v97** (1794874374-d46c), Base·F **v92** (1794874383-8ea0) = regen of build/q309 at HEAD
0c66cf5 (scratchpad `pub9/<dir>` holds the files sent; regen output on DISK: scratchpad `regen/q361`). They
carry the Q337 sweep fixes below plus:
- **Q357** vessels/nerves out of bone, both pages (`scripts/anatomy/q357/conform_in_bone_q357.py`, allow-list
  `data/anatomy/q357_in_bone_allow.json` of 25 true canals/foramina with book+page; originals `*.q357`):
  266 → 151 structures (M), 268 → 153 (F). Left on guards: testicular veins, posterior circumflex humeral
  vessels, calcaneal branches of the fibular artery, cortical arteries (skull meshes not watertight).
- **Q358** Base·F perineal skin (`scripts/anatomy/q358/perineum_skin_q358.py`, `docs/Q358_perineum_skin.md`,
  originals `*.q358`; owner asked for it 2026-11-16): real `skin_vulva_cvh` cleaned + smoothed (cap 1 mm), ring
  closed by the separate rule-based `skin_perineum_rule_q358` (last mesh; badge + citations on its card),
  deep structures tucked. Still: the real patch is coarse and jagged (source mesh ≈ 5 mm edges), thin
  gracilis slivers at its sides, labia narrower than the atlases.
- **Q354** name cards show only a structure's own record (`scripts/zanatomy/card_rules_q354.py`,
  `patch_manifest_cards_q354.py` runs twice in regen): 137 borrowed records/body → 0, sided nerves list
  same-side targets, brain/eye/ear parts off the nerve layer, raw ids and build notes off the card, serratus
  posterior inferior T9–T12, phone card capped at 60%. Left: search + q298 relations keep the old names of
  44 renamed meshes; one sulcus name is a mechanical expansion (marked in data).
- **Q355** UI: Anatomy panels parked when a mode is entered and restored on exit, one tool panel at a time
  on a phone, injection closest-structures names wrap, only placed landmarks offered, insertion rings scale
  with zoom, measure close button sticky, round ids out of visible text. The hidden-chip naming was reverted
  (its grip covered the text). Not browser-checked: scan-mode "Nothing to centre" fix, skin-hidden prompt.
- **Q353** Base·F skin, applied steps `chest_tuck,head` only (`scripts/anatomy/q353/conform_skin_q353.py`,
  originals `*.q353` in build/): breast fat / ducts / gland / suspensory ligaments, frontalis and platysma
  under the skin. **Held, do not apply:** `back` and `chest_seams` (leave seam lines on a regenerated page;
  cause of the back lines not found) and `perineum`.
Verified on q356 (code) + q358 (Base·F geometry): scratchpad `v356a.txt`, `v356b.txt`, `v358.txt` — all OK
(q321 1400/390, q344 ui 1400/390 + clinical, q347 390, q322, q343, q323, q329, q319 search/nerves, q336,
q325). q334 seams: the same 4 FAILs with identical numbers before and after Q353 (trunk ×3, knee) — the
known trunk seam. Load-sensitive, pass on a quiet rerun: q344 "Labels (compact)" on Base·M 390, q321
"Undo brings it back" on Base·F 1400.
**Rules learnt this round:** judge skin/geometry only on a REGENERATED page (build/ pages carry no weld
block); at most two browser queues at once; a queue dies at 2 h; agents report as text (they cannot write
report files).

**Still wrong on the live pages (from the sweep), in priority order:**
1. Base·F chest: outlines between skin regions (mammary, presternal, inframammary) still visible with
   opaque skin; purple sliver in the right inframammary fold (see "Chest" below).
2. Base·F vulva/perineum: ragged fragments and flap; skin ring open 20–30 mm with no source skin piece.
   **Owner, 2026-11-16: fix it according to the atlas figures** → round Q358 (running): real surface kept
   and cleaned, the missing part added as a separate rule-based (badged, cited) skin structure.
3. Face skin seams around mouth / nose / eyes (both bodies); temporoparietalis, orbicularis oris through skin.
4. Vessels/nerves inside bone: done for what passes guards (Q357); the three worst cases remain.
5. Skin tears in large poses; seams on toes / finger bases / thumb / natal cleft; two small triangles at
   the scapulae; small poke-throughs (saphenous veins, supraclavicular n.); Base·F sternoclavicular
   ligament R/L 4.16; thick white retinacula, floating transverse metatarsal ligament, block pubic disc.
6. Not covered by the sweep: Base·F per-mode run, pose run, desktop UI walk-through.
**The container restarted twice on 2026-11-16 evening** (three agents + queues; /dev/shm is wiped each
time, build/, the repo and the scratchpad survive). Since then: regen goes to DISK (`--allow-disk --out
<scratchpad>/regen/<tag>`), agents keep working copies in the scratchpad, an agent's unfinished script is
committed as "work in progress" at each checkpoint, and at most one heavy geometry agent runs at a time.
**Chest (item 1) — cause known (Q356):** the chest regions were refitted one at a time, so their borders
share no vertices, rims are rounded and neighbours do not meet; the load-time weld has nothing to join.
Capped conforms (Q353 `chest_seams`, Q356 shingle `scripts/anatomy/q356/zip_skin_q356.py`) leave outlines
and add dark steps at the clavicles — HELD, do not apply. **Running: Q360** joint refit / re-cut from one
surface (`scripts/anatomy/q360/chest_skin_q360.py`, work in progress).
**Next (one heavy geometry agent at a time):** apply Q360 when it proves itself on a regenerated page; then
**Q362 — owner, 2026-11-17: yes, bring real geometry from the frozen imaging-based pages into the Base
pages** ("interesting solution, may be synergistic with the atlases"): perineal muscles + rectum from
Imaging·M (`build/q309/viewer_m_hr`, read-only source — the frozen page itself is not changed or
republished) into Base·M, registered on the Base·M pelvis and checked against the atlases; and check
whether Imaging·F (`viewer_f_hr`) has a better real vulva/perineal skin than the coarse `skin_vulva_cvh`
before building any rule-based external-genital surface. Then items 3 and 5.
**Owner, 2026-11-17: "eyes are not intact, head nerves are missing; review all organs of the 2 models."**
→ Q363 audit done: `docs/Q363_organ_audit.md` (8 blockers, 22 should-fix, 18 cosmetic; every missing item has
a source column: un-exported Z object / frozen imaging page / none → rule-based). No data was lost this week;
the one regression is from Q354: eye parts moved to the CNS layer, so the globe drew as one lavender ball.
Running: **Q364** eyes (per-structure colours via `data/anatomy/structure_colours_q364.json` → `nmsk-colours`
block read by `colOf`; Base·F globes re-placed rigidly from Base·M; right sclera winding) and **Q365** nerves
(infra-orbital, Base·F facial temporal branches, occipital nerves, one-sided branches — all rule-based,
badged). **Q362 must also bring from the imaging pages:** ileum (both), kidneys (Imaging·F → Base·F; Base·M
has no real source — Z kidneys are licence-blocked), Base·M rectum / anal canal / perineal muscles.
Other audit items not yet assigned: pericardium, scrotum, choroid, conjunctiva, ear cartilage, sinuses,
tongue intrinsic muscles (no real source), jejunum inside-out, ligament of the head of femur L/R.
**UI redesign (owner, 2026-11-17):** he asked for a dashboard to decide the title tree of all buttons and
texts, the stage at which each appears and where on screen. **Published: "NMSK Atlas UI Map"**
https://claude.ai/artifact/ACxx8vDbimhPWdgDJ98gT8 (private; `db` store). His decisions are documents in
collection `decisions` (id = node id; fields path, text, stage, verdict keep|rename|move|merge|remove|unsure,
label, labelHe, parentPath, parentId, appears, mode, placeD, placeP, note) and groups he adds are in
`groups` — **read both with ArtifactData before any UI rework**; this session is NOT woken when he saves.
Source: `scripts/uimap/` (generator + page template); inventory + shots: scratchpad `uimap/` (1793 items,
139 stages, Base·M; phone walk of the clinical-mode interiors and the Base·F diff were not captured).

**Owner, 2026-11-17 (three requests):**
1. "Complete the mapping of everything" → UI inventory completion agent running (append-only over
   scratchpad `uimap/inventory.json`: phone deep crawl, click-dependent states, code-only strings, Base·F
   diff); then rebuild with `scripts/uimap/build_dashboard.py` and republish the dashboard (same URL).
2. Name card: (a) a small swatch button beside the name showing the colour the structure is marked in;
   pressing it changes the colour; (b) next to it an "ADD / הוסף" button offering: functional group,
   ANTAGONIST functional group, adjacent tissues (added to the marked set). → **Q368, not started** (needs
   an antagonist-group table with sources; owns `viewer/quickcard/*`). Start when Q360 reports.
3. Injection mode can start from a plan, in the user's order: tip target = structure ± origin / insertion /
   nerve–muscle junction / PLANE (plane block), skin passage, plus sensible additions; tip and skin entry as
   two clearly different coloured points; a "בטיחות" panel with the user's own distance rules for nerves
   large/medium/small, arteries large/medium/small, veins large/medium, drawn as halos and checked against
   the path. → **Q367 running** (private: `clinical/needle_tool.js`; no invented thresholds — fields start
   empty; verifier `scripts/anatomy/q367/verify_plan_q367.py`).
**Applied to build/q309, verification queue running on scratchpad `regen/q366` (v366_f.txt, v366_m.txt), not
yet published:** Q364 eyes (both pages) and Q365 head nerves (both pages; pose rigs spliced, search rebuilt).
**Found by Q364, not yet assigned (Q366):** 198 of 778 Base·F head structures carry registration spikes
> 3 mm against a clean fit from Base·M (orbit muscles, lacrimal gland, optic nerve, orbital skin, temporal
vessels up to 8.5 mm) — a body-wide guarded de-spike of Base·F, after Q360 and Q362 are applied.

Regen --expect-changed (current): index.html,nmsk-ultrasound-inline,nmsk-ultrasound-tissues,
nmsk-imaging-inline,nmsk-q309-layers,nmsk-pose-rig,nmsk-abbrev,nmsk-q306,clinical_ultrasound_tissues.json,
clinical_ultrasound_tool.js,clinical_imaging_tool.js,clinical_needle_tool.js,clinical_motor_points.json,
parts_data.json,symmetry_q237.json,plexus_groups.json,innervation_q322.json,groups_q342.json,
__ANATOMY_manifest,__ANATOMY_files,atlas_viewer_base_female_geo_03.txt clinical_injection_guide.json.

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
muscles/body without attachment points; teres major IZ band (no rule); Base·F latissimus iliac IZ bands (7.5 mm from the muscle); 7/10 (M) and 9/10 (F) finger sides keep the nerve dorsal to the artery; superficial venous palmar arch ~9 mm too deep; no median nerve trunk mesh (at-risk rows say so); thumb CMC rest pose outside its
ROM; 63 muscles' root levels unchecked; `test_q298::test_relations_exist…` fails (derived relations lack
new foot ids); Q292 `lib292.push_dir` decay bug unfixed in the library.
