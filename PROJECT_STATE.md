# Project state — resume point

Read this first in a fresh session instead of the conversation. Keep it short (target < 200 lines):
it holds only what is true NOW. When a round closes, move its detail to `docs/PROJECT_HISTORY.md`
(the dated archive, Q1–Q320) and leave one line here. Last updated: 2026-11-18 ~01:40 UTC (after the Q360/Q367/Q368 publish).

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
| Base · Male | `build/q309/viewer_zan_atlas` | Z | HdYCRuvGP8ESbggoRWCNBF | v101 (… Q368, Q362 relabel, Q372 weld) |
| Base · Female | `build/q309/viewer_base_female` | **Z** (not the own engine) | TiXsQe3eS5ehzN64Aozyth | v97 (… Q362 relabel, Q372 weld, Q366 de-spike) |
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
(Rewritten 2026-11-18 ~07:10 UTC. Detail of rounds Q353–Q365: docs/PROJECT_HISTORY.md, last section.)

**Live:** Base·M **v101** (1794991161-ef8e) = scratchpad `regen/q373` (commit 6cbcaf2; `pub13`); Base·F **v97**
(1794994587-6db4) = scratchpad `regen/q374` (commit d91c795, = v96 + the Q366 de-spike; `pub14`: index.html, the
four geo files, clinical_vessel_calibre.json; its Base·M index is byte-identical to q373). Q366 verdicts on
q374 / the agent's identical `q366/regen_3` (`v374.txt`, `q366/ver`): q334 4 known FAILs none worse, q358, q336,
q329, q325, q367 (1400 + 390), q321, q347 390, q322, q323, q338, q343, q344 390, q368 — all OK.
Before a publish with supporting files, `Artifact list scope=files` on the page (the tool refuses otherwise). v101/v96 =
v99/v94 + the Q362 relabel + the Q372 skin wall pass. Checked on q373 (`v373_part1.txt`, `v373.txt`, `v373/`,
and the agent's logs `q372/v_*.log` on a byte-identical regen): q334 M **Q334_SEAMS_OK**, q334 F its 4 known
FAILs none worse (trunk 2.58 / 2.94 / 1.84, knee 2.21; face solid 1.26 → 0.81), q358, q318 rings ×2, q336,
q367 plan (M 1400, F 390), q321 F (198 OK on a quiet rerun; the first run failed under load right after a
container restart), q344 ui F, q329 F, q325 M, q319 spine M; posed montages read (known pose tears remain).
Earlier full sets: v99/v94 on regen `q370`, the relabel on `q371`.
On the live pages since v95/v90: Q354 cards, Q355 UI, Q353 `chest_tuck,head`, Q357 in-bone conform, Q358
perineal skin, Q364 eye colours + rigid Base·F globes, Q365 head nerves, Q360 seamless Base·F chest skin,
Q367 plan-first injection mode (tip/entry markers, safety halos), Q368 name-card colour swatch + ADD menu,
**Q362** the Z mesh labelled "Sigmoid colon" shown as "Rectum and anal canal" (source label on the card),
**Q372** skin wall pass (twin walls, slanted pairs, duplicated surface): face / thumb / neck lines gone.

**How work runs now (learnt the hard way):**
- Judge geometry/skin only on a REGENERATED page. Regen to DISK: `--allow-disk --out <scratchpad>/regen/<tag>`
  (/dev/shm is wiped by container restarts — three this week); `--expect-changed` also needs
  `nmsk-colours,nmsk-calibre` and all geo files of both pages.
- One browser lock (`flock /tmp/nmsk_browser.lock`), 4 CPUs: keep my own queue short (≈10 runs), agents
  batch their runs; a second lock was refused by the permission system — do not work around it.
- Agents: at most 2–3 at once (four exhaust the 5-hour limit); resume a stopped agent with SendMessage.
  Checkpoint their files as "work in progress" commits, but NOT data/ files while an agent's regen runs
  (regen aborts on "tracked data/ files changed"). Agents kill their own jobs by PID only.
- Load-sensitive verifier checks pass on a quiet rerun: q344 "Labels (compact)" 390, q347 "FHL scan start".

**Running / queued (owner's requests of 2026-11-17 are marked ★):**
- ★ **UI map: complete** (scratchpad `uimap/inventory.json`, FINAL, append-only over `inventory_v1.json`: 3115
  items, 260 stages — phone crawl, interaction states, typed search, the Q367/Q368 UI, 187 code-only strings,
  Base·F diff of 398 lines with no control on only one page). Dashboard v2 republished with every old node
  id kept: https://claude.ai/artifact/ACxx8vDbimhPWdgDJ98gT8 (source `scripts/uimap/`). The owner's decisions
  are db documents in collections `decisions` and `groups` — none saved yet on 2026-11-18;
  **read them with ArtifactData before any UI rework** (this session is not woken when he saves).
  Not in the map: adopted entry candidates / clip view / step sheet, the Learn search box, a loaded patient
  file, phone passes of the cut / four-view / measure / pose interaction states.
- **Q362 — closed 2026-11-18, nothing transferred** (`docs/Q362_imaging_transfer.md`, report
  `data/derived/Q362_transfer_report.json`): every organ taken from the frozen imaging pages failed its guard
  or its book check (CT rectum / sphincter ring / perineal muscles / ileum / kidneys); the Z "Sigmoid colon"
  tube IS the rectum + anal canal (below S3, ends in the external sphincter) → relabelled by data
  (`data/anatomy/relabels_q362.json`, `scripts/zanatomy/patch_manifest_relabel_q362.py`, a regen step). The
  transfer steps stay in `scripts/anatomy/q362/transfer_organs_q362.py` as non-default steps. Base·M
  bulbospongiosus / ischiocavernosus / deep transverse perineal are held (Z prostate ~15 mm low).
- **Q366 — live on Base·F (v97).** `scripts/anatomy/q366/despike_q366.py`, `docs/Q366_despike.md`, report
  `data/derived/Q366_despike_report.json`: 649 structures / 3,421 vertices moved to their Base·M position
  through the local warp (max 11.5 mm, p95 6.3), 21 held by guards; originals beside the build files as
  `*.q366`. Left by design: broad registration roughness (face, paraspinal, fingers), spikes on excluded
  structures (skin — up to ~40 mm on `zan_skin_anterior_region_of_arm_r` —, bones, the 194 later-round
  structures), 789 frozen seeds. The agent also noted the build/ page (no weld block) rendering mirrored
  against the regen page in a side view — unchecked.
- **Q375 (agent running since 2026-11-18 ~09:10 UTC):** finger-base and toe-base skin borders are only half
  welded (0.8–0.9 mm apart) → cause per border, then a guarded sub-mm conform or the smallest engine change;
  private copy in scratchpad `q375/`, hands back the apply commands for both pages.
- **Q372 — live.** Source `scripts/anatomy/q334/seams_weld_q334.js` (patched into the Z template by
  `patch_seams_q334.py`); skin only, cortex / fascia keep the old rule; weld +150–195 ms at load. NOT cured:
  toe-base and finger-base lines (those borders are half welded in the GEOMETRY: 8/16 and 22/49 border
  vertices, the rest 0.8–0.9 mm apart — needs a geometry round), faint Base·F philtrum / lower-lip / sternum
  lines. Follow-up worth doing: re-apply Base·F chest WITH walls (`chest_skin_q360.py --chest-walls`, now
  seamless; hiding a chest region then shows a real edge) — after Q366 is applied, with a rig re-encode.
  At most one more geometry agent beside Q366 (one browser lock).
- Small UI leftovers: the ADD button reads "ADD" only (owner wrote "הוסף / ADD"); the adjacent list (82
  rows for biceps) fills a phone screen; joint-space tip target picks the largest bone interface (radiocarpal
  → lunate/hamate); clip-view markers ≈ 7 px; Safety size classes are a stated convention (books give none).

**Still wrong on the live pages:** Base·F chest: soft sternal crease, a step at the right anterior axillary
fold; Base·F vulva patch coarse and jagged, thin
gracilis slivers; seam lines at toe / finger bases (half-welded borders); pupil has no mesh (lens made clear instead); third occipital
nerves nearly cross at the nape; nerves held by their rules (XI→SCM R, XII lingual L on M, femoral/tibial
muscular branches, anococcygeal, dorsal n. of clitoris, cranial ganglia); in-bone leftovers (testicular
veins, posterior circumflex humeral, calcaneal branches); skin tears in large poses; seams on toes /
finger bases; kidneys (both bodies) and small bowel have no usable real source (owner's call, below); the rest of
`docs/Q363_organ_audit.md` (pericardium, scrotum, choroid, conjunctiva, sinuses, tongue intrinsics,
jejunum inside-out); 96–102 single bones show their group record on the card.

Regen --expect-changed (current): index.html,nmsk-ultrasound-inline,nmsk-ultrasound-tissues,
nmsk-imaging-inline,nmsk-q309-layers,nmsk-pose-rig,nmsk-abbrev,nmsk-q306,nmsk-colours,nmsk-calibre,
clinical_ultrasound_tissues.json,clinical_ultrasound_tool.js,clinical_imaging_tool.js,clinical_needle_tool.js,
clinical_motor_points.json,clinical_injection_guide.json,clinical_vessel_calibre.json,parts_data.json,
symmetry_q237.json,plexus_groups.json,innervation_q322.json,groups_q342.json,__ANATOMY_manifest,
__ANATOMY_files, and the four `atlas_viewer_<page>_geo_0{0..3}.txt` of both pages.

**Owner's books** (Dropbox `/claude`, KNOWLEDGE ONLY: facts + page citations; no prose/figures copied; PDFs
never in the repo): nine PDFs in the scratchpad `refs/` (re-download with Dropbox `download_link` + curl
after a rebuild; network is unrestricted since 2026-11-16). Never touch other Dropbox folders.

**Decisions taken by the main thread (owner delegated):** vulva skin accepted as an overlapping real
surface; "horizontal" myofascial class shown disabled (no sourced line); rule-based muscle-part partitions
are NOT drawn (parts without a mesh are listed greyed); palmar conform approved; Q348 geometry findings
applied through guarded conform scripts (Q349/Q350), a structure whose guard fails is left as is.
**Owner's open calls:** scan-mode badge "סימולציה מהמשים" (typo? pinned by two tests); larger breast gap on
Base·F (`_r` pectoralis thin, R/L 0.76); **kidneys, both bodies** (asked 2026-11-18): rule-based from the
books, or the real CT kidneys moved to the book level T11–L3 with the shift recorded (my recommendation), or
none; small bowel: rule-based or none; a second browser lock (refused by the permission system); unfreeze question for the mirrored frozen pages; the neonatal-procedures "Atlas" PDF
(uploaded by mistake?).
**Do not run** `sync_learn_q283.py` / `sync_hub_link_q251.py`: the template is ahead of their source (Q312
edits were made in the template); running them reverts Q312.
**Other open:** Base·F trunk seam (geometry build); deltoid middle-belly motor rule on Base·F; 82
muscles/body without attachment points; teres major IZ band (no rule); Base·F latissimus iliac IZ bands (7.5 mm from the muscle); 7/10 (M) and 9/10 (F) finger sides keep the nerve dorsal to the artery; superficial venous palmar arch ~9 mm too deep; no median nerve trunk mesh (at-risk rows say so); thumb CMC rest pose outside its
ROM; 63 muscles' root levels unchecked; `test_q298::test_relations_exist…` fails (derived relations lack
new foot ids); Q292 `lib292.push_dir` decay bug unfixed in the library.
