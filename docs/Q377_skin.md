# Q377 — Base · Female skin: census against Base · Male, causes of the seam FAILs, guarded de-spike

Script: `scripts/anatomy/q377/skin_q377.py` (dry run by default; `--write` refuses `build/` without `--allow-build`;
originals kept as `*.q377`; report `data/derived/Q377_skin_report.json`). Engine weld outside a browser:
`scripts/anatomy/q377/weld_roots_q377.js` (runs the unchanged `scripts/anatomy/q334/seams_weld_q334.js` in node).
Tests: `tests/test_q377_skin.py`. Base · Male is read only; the engine and the templates are not touched.

## Census (Base · F, 246 skin slabs)

- 226 slabs have a same-topology twin on Base · M; 20 have none (the 18 Q360 chest slabs, `skin_perineum_rule_q358`,
  `skin_vulva_cvh`).
- **Map.** Q366's robust local map, imported, fitted over all 226 twin slabs as ONE surface (49 648 vertices). Over one slab
  alone it is not local: a slab has a few hundred vertices, so its 64 neighbours span the whole slab and the residuals are the
  warp's curvature (2–6 mm spread), not noise. Residual over the whole skin: p50 0.12, p95 2.06, max 43.7 mm.
- **Spikes.** 100 vertices in 48 patches on 27 slabs, all 2.6–6.7 mm, all in the head and on two finger slabs: frontal,
  eyebrow, orbital, parietal (scalp), nasal, mental, mentolabial, submental, submandibular, buccal, parotideomasseteric,
  auricular, posterior auricular groove, dorsal surfaces of the digits of the hand. Most are single outer-sheet vertices
  pushed out 4–6 mm (sheet distance 7–10 mm against Base · M's 3–5 mm) or in 6 mm (the outer sheet crossing the inner one,
  forehead). Elsewhere on the body (trunk, limbs) no spike passes Q366's seed test.
- **Shared borders.** 5 011 vertex pairs that coincide on Base · M (the engine welds them, 0.03 mm): all but 2 still
  coincide on Base · F — nasal L|R, 0.84 mm. 2 910 rim-join pairs (0.03–1 mm apart on Base · M, joined by the engine's rim
  rule): 47 are beyond 1 mm on Base · F, on 33 borders, all because one side carries a spike (worst: mental|submental 6.8,
  eyebrow|frontal 6.6, mental|oral 4.7, buccal|mental 3.1 mm). The engine's own weld (node, both pages) joins the same share on
  every twin|twin border of the trunk and the knees as on Base · M (e.g. knee: 36/36, 40/40, 32/32 shared on both bodies).
- **Q360 chest against its unchanged neighbours.** The coincident pairs survive (Q360 kept them), but the chest slabs
  carry 2–4× the neighbour's border vertices and the extra ones join nothing: lateral thorax|posterior arm 15 of 23 (L) /
  9 of 17 (R) unjoined, pectoral|deltopectoral triangle 14/21, 12/19, epigastric|umbilical 6/20, infraclavicular fossa|lateral
  neck 5/17, mammary|pectoral 6/14; deltoid|deltopectoral triangle has one pair 3.6 mm apart. Engine (node): chest borders 154
  open border vertices on Base · F against 15 on Base · M.

## Causes of the four q334 FAILs and of the axillary step (per border, `perborder` breakdown of the q334 metric)

| check | ratio | what makes it |
|---|---|---|
| trunk solid | 2.58 | the hands are in the trunk frame on Base · F (not on Base · M): the L finger dorsal\|palmar border (35 points, 18× the control) alone adds 0.62; without the hand and wrist borders 1.70; without them and the Q360 chest borders 0.99 |
| trunk faded | 2.93 | the same finger border adds 1.03; without hands 1.55; without hands and chest 1.20 |
| trunk default | 1.84 | the finger borders (L 0.66, R 0.10); without hands 0.98 |
| knee default | 2.12 | the side line of the right knee and leg in the layered view: anterior\|posterior region of knee R (9 points, 6.9×, adds 0.64) and of leg R (5 points, 5.1×, adds 0.39); without them 1.09. Fully welded on both bodies (40/40, 36/36); the line is the translucent skin's edge seen tangentially at the leg's side with the layers behind it, not a gap |

- The finger dorsal|palmar border is the same topology on both bodies (engine: 161 of 502 border vertices unjoined on both,
  the Q375 T-junction class); Base · M's trunk camera just does not see the hands.
- The Q360 chest borders (seam 4.1 against the control 2.3 in solid) are the rest of the trunk excess: the unjoined chest
  border vertices above, plus the soft sternal crease (presternal L|R, both Q360 slabs).
- **Axillary step (right anterior axillary fold).** `zan_skin_anterior_region_of_arm_r` v0, v3, v50, v68, v66, v58 lie
  16–44 mm in front of where the local map puts them (left: 3 vertices, 12–16 mm). They are not noise: they wrap the axillary
  tail of `breast_ct_r` (2.0 mm under the current skin; 6.8 mm from the map position) and `fat_subcut_thorax`. Correcting
  them needs moves of up to 44 mm (cap 12 mm) and would uncover the breast: a re-fit of the axillary fold with the Q360 chest,
  not done.

## What was corrected

Guards per slab (a failing slab is left exactly as it is, with every vertex tied to it across a border): move ≤ 12 mm;
area by Q366's size rule (change ≤ 2 %, or towards the source size); sheet distance after within 0.5 mm of Base · M's
(scaled) or nearer to it than before; every border's share as joined by the engine itself (node) not lower; no structure under
the skin gains a vertex outside it (Q353's `outside_count`).

- **Corrected: 10 slabs, 27 vertices** — frontal L/R (6/7), eyebrow L/R (2/2), orbital L/R (2/2), parietal L/R (1/1),
  dorsal surfaces of the digits of the hand L/R (2/2). Move max 6.38, p95 6.35 mm. Sheet distance after within 0.16 mm of
  Base · M's (before up to 6.2 mm off). Area: digits −0.19 %, parietal −0.18 %, frontal −1.9 / −2.1 %, orbital −3.9 %,
  eyebrow −19.2 % — each ends within 1.2 % of the source size (eyebrow was 22 % over it: two spikes on a small slab).
  These three exceed a plain "≤ 2 %" and pass Q366's size rule; `--strict-area` applies the plain rule and corrects only
  5 slabs / 13 vertices (frontal R, parietal L/R, digits L/R). Structures outside the skin in the tested boxes 2 287 →
  2 189, none gained.
- Engine weld (node, whole skin): +28 shared border vertices, −14 open; eyebrow|frontal 18→22 of 22, orbital|frontal and
  eyebrow|orbital gain; no border loses. Rim joins broken 47 → 43, borders separated 33 → 31.
- Vertex and triangle counts unchanged: the pose rig still matches, no re-encode.

## Held, and why (17 slabs)

- Lower face (mental, mentolabial, submental, submandibular, buccal L/R, parotideomasseteric L): the 4–6 mm "bumps" carry
  the female mandible, mental nerve, lower premolars and labial vessels — taken back to the map, the mental branch of V3
  would come out through the skin (4 → 171 vertices), the mandible 10 → 21. Not noise; the lower-lip midline line is there.
- Nasal L/R (3.2 mm, and the 0.84 mm separated midline pair): the lateral nasal cartilage would come out (15 → 18).
- Auricular region and posterior auricular groove L/R: under-skin (infra-auricular nodes, superficial temporal veins) and the
  engine's share on their common border would drop by 1–3.

## Left open

1. Q360 chest borders (unjoined chest border vertices, sternal crease, the dark band at the chest's lower border): new border
   topology or a joint re-cut of the chest with its neighbours — not a vertex move.
2. Axillary fold R (and L, smaller): a re-fit of the arm slab with the chest around `breast_ct`.
3. q334's trunk camera on Base · F frames the hands; the finger dorsal|palmar border (T-junction class, same on Base · M)
   dominates the trunk ratio. A hand zone, or a trunk frame without the hands, would measure the trunk itself.
4. Knee R side line in the default view: no geometric defect found (borders fully shared); a render/metric matter.

## Verification (regenerated private copy; before = the same regen with the original geometry)

- q334 on Base · F: trunk solid 2.58 → 2.58, trunk faded 2.93 → 2.93, trunk default 1.84 → 1.84, knee default 2.12 → 2.12
  (none worse, none fixed: none of the four is caused by the spikes this round could move); Base · M `Q334_SEAMS_OK`.
- Renders (same template and cameras, solid skin and default view; trunk front / back / both sides, both axillae, sternum,
  both knees front and side, face, mouth, brow, back of the head, both ears, both hands; posed pair): forehead and brow
  better (the two streaks at the temples and the notch in the brow outline are gone); every other region pixel-identical
  apart from the on-screen chips (trunk, axillae, sternum, knees, mouth: unchanged); posed pair unchanged (≤ 34 px differ,
  at the forehead). Nothing worse.
- Verifiers on the regenerated Base · F: q358, q336, q318, q367, q325 OK.
- q321 (quick card, 1400): FAIL on the corrected page ("Undo brings it back … the card stays", then Fade / Show only /
  Select / More, then a TypeError), OK on the same regen with the original geometry. Not caused by the skin: the corrected
  forehead changes the model's screen box by ~0.02 px, the verifier's nerve scan then misses the 'Tuber of vermis' sliver it
  used to hit first and clicks on to another nerve. Forcing that one extra step on the ORIGINAL page (scan skips 'Tuber of
  vermis', finds 'Abducens nerve (right)') gives the identical FAIL. A pre-existing card / Undo path the scan order hides;
  for the UI owner, not this round.
