# Q379 — Base · F rebuilt chest joined to its neighbours

Tool: `scripts/anatomy/q379/chest_borders_q379.py` (test `tests/test_q379_chest_borders.py`). Report:
`data/derived/Q379_chest_borders_report.json`. Base · F only; Base · M and the frozen pages untouched; no engine or template
change. Applied on a private copy of `build/q309` and judged on a regenerated page; `build/` itself not written.

## What was wrong (measured)
- Q360 locked every chest border vertex it shared with an unchanged region and then subdivided the chest. Census of the
  merged chest sheet (all 18 slabs, shared vertices as one node): **only one border runs free between two locks — the axilla,
  lateral thorax | posterior arm** (outer sheet L 28 / R 20 vertices). There the fitted chest edge overlaps the arm skin by up
  to 2.7 mm (0.04–1 mm above its surface), so the weld, the rim join and the Q375 T-junction attach found nothing. Every other
  chest border with an unchanged region (umbilical, lateral abdomen, scapular, infrascapular, lateral neck, …) is locked vertex
  for vertex.
- Q377's "unjoined" counts on pectoral | deltopectoral, epigastric | umbilical, infraclavicular | lateral neck, scapular,
  hypochondriac are chest vertices that the rim rule picks up because the sheet folds within 1.5 mm of the neighbour — not
  border vertices; nothing to join there. Engine census, chest border vertices (both sheets) facing an unchanged region
  and left open: **110 → 62** (posterior arm L 55 → 28, R 40 → 20; the rest are the inner sheet and the corners below).

## What was done
1. **Axilla, outer sheet** — each free border vertex put ON the arm's own border polyline (the shortest path along the arm
   slab's rim edges between the two lock vertices): the arm's interior border vertices each take one chest vertex (weld,
   8 vertices), every other one goes to its closest point inside an arm edge (T-junction attach, 40). 48 vertices on 2 slabs;
   move p50 1.67, p95 2.71, max 3.81 mm (cap 4); slab area +0.10 / +0.12 %; no sheet face turned > 35° (cos ≥ 0.82).
   16-bit round trip: each moved vertex takes the code (of the 27 around its target) whose decoded point lies nearest the arm
   edge — residual p50 0.0006, p95 0.0015, max 0.0020 mm (engine tolerance 0.03). Unmoved vertices keep their bytes.
   Engine borders (Q375 rule): lateral thorax L | posterior arm 8/23 → 36/36 joined, R 8/17 → 28/28; posterior arm side
   10/15 → 14/15 (L), 10/12 → 14/14 (R); no border of any slab lost a joined vertex.
2. **Chest-to-chest walls** (`--chest-walls`) — Q360 shipped no wall between two chest regions, so hiding one (or fading it)
   opened a slot onto the inside of the body (seen in every "hide one region" render on the chest). Added the side wall along
   every chest-to-chest border from the slabs' own outer and inner border vertices, cut on the same diagonal from both sides
   (Q360's own slab rule, no refit, no vertex moved): 3920 triangles on the 18 slabs. Engine (node): all 3920 are found as
   twins and hidden while both regions are drawn. Seam normals change only at chest seam vertices, most at the 76°
   deltopectoral | pectoral fold (up to 56° at 7 vertices), elsewhere ≤ 6°.

## Held / refused (with numbers)
- **Inner sheet in the axilla**: the chest and arm inner sheets diverge 2–5 mm at the axillary fold (chest inner partner to the
  arm's inner border p50 ≈ 3.2 mm), the arm's inner rim is not one chain across the anterior | posterior arm corner (gap 17–41
  mm), and the one candidate run would turn faces > 60°. Refused; its wall stays drawn there as before.
- **Deltoid | deltopectoral 3.6 mm pair**: on Base · F the deltoid corner vertex (L v301 / R v12) is welded to the
  infraclavicular fossa; the deltopectoral | infraclavicular border meets the deltoid border 3.6 mm away. The corner runs
  (2 L / 3 R vertices, a chest-to-chest corner among them, moved with both copies) need 4.7–5.1 mm > cap: refused.
- **Right anterior axillary fold**: not touched (the arm slab's 6 vertices wrap `breast_ct_r`). A guarded option would be a
  joint re-fit of the arm slab with the chest around the breast tail under the Q353 tuck guard — not a border move.
- **Under the skin**: no structure gains a vertex outside. Five vertices are newly *counted* outside with the same height as
  before (latissimus dorsi L/R 10.5 / 11.4 mm, triceps long head L 0.6, 1.0 / R 0.8 mm): they lay over the overlap the join
  removed, where Q353's `outside_count` "covered" test skipped them. Pre-existing; listed in the report.

## Sternal crease and lower-edge band: causes
- **Sternal crease** = geometry, not a join. Presternal L | R share all 53 midline vertices; the engine's seam normal there is
  the mean of both halves (0.9° p50 off it). The halves meet at a V of 30.6° p50 / 49.1° p95 (within a half 2.7°): the sternal
  furrow of the Z source (Base · M deeper: −46…−58° over 2–12 mm; Base · F −16…−25°, and the same before Q360). Not walls —
  re-running Q360 with `--chest-walls` would refit the whole chest from the current page and could not remove a V that is in
  its target. A smoother midline needs a re-fit (out of scope).
- **Lower-edge band** = the Q360 fitted surface. The lower border is locked vertex for vertex, its walls hidden, dihedral 7.2°
  (Base · M 7.1°), normal tilt step chest → abdomen 7.5° (M 7.6°). What differs: face-normal scatter 4.5° in the 2–15 mm band
  above the border (M 0.7°) — the ripple of the fit at 2.7 mm edges, ending against the 18.5 mm faces of the unchanged
  abdomen. Remedy is a re-fit (out of scope).

## Verification (regenerated private copy, `REGEN_TEMPLATE_ONLY_OK`)
- `--expect-changed` also needs `nmsk-cover`: the html in `build/q309` predates the Q389 cover block.
- q334 on Base · F, same template, original geometry → final: trunk solid 2.58 → 2.38, faded 2.93 → 2.92, default
  1.85 → 1.76; FAIL lines 4 → 2 (still failing: trunk default 1.76, knee default 2.12 unchanged). The border sample grew
  532 → 546 edges (the walls make the chest-to-chest borders count). The vertex moves alone left every q334 line identical:
  its sample is borders shared vertex for vertex, which the axillary T-junction border is not. Base · M: Q334_SEAMS_OK.
- Engine (node) on the final page: 3920/3920 new walls hidden. q358, q336, q318 rings, q367 plan, q325 (1400×900) OK;
  `tests/test_q360_chest_skin.py` + `tests/test_q379_chest_borders.py` 12 passed.
- Renders before/after (solid and default, each also with one neighbour hidden): axilla, posterior axilla and sides with the
  arm hidden — better (the chest edge ends on the arm border, no overlapping lip); every view with a chest region hidden —
  better (a wall at the slot edge instead of an open edge); all-drawn views of chest front, sternum, abdomen, neck base,
  sides, deltopectoral triangle and the posed pair (right arm abducted 126°) — unchanged. None worse.

## Apply (main thread, on the build page)
`python3 scripts/anatomy/q379/chest_borders_q379.py --page-dir build/q309/viewer_base_female --chest-walls --write --allow-build --json <scratch>/q379_apply.json`
(`--json` keeps this round's report, which also holds the verification; vertex counts unchanged: the pose rig needs no
re-encode; originals kept as `*.q379`). Expected: 2 runs / 48 vertices, 3920 wall faces, `Q379 WRITTEN`.
