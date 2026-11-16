# Q358 — Base · Female: the skin of the vulva and perineum

Owner, 2026-11-16: "fix the skin in the vulva and perineum region according to pictures from the anatomy atlases".
Script `scripts/anatomy/q358/perineum_skin_q358.py` (guards, `*.q358` backups, idempotent), report
`data/derived/Q358_perineum_report.json`, browser check `scripts/anatomy/q358/verify_q358.py`, tests `tests/test_q358_perineum.py`.

## 1. What was wrong (measured on the page)
- `skin_vulva_cvh` (Q336: the real CVH vulvar surface, registered, its border tucked 25 mm under the Z-Anatomy neighbours) crossed
  the neighbours' outer surface in many places: fragments and a flap showed through / in front of the thigh, inguinal and
  hypogastric skin; two loose pieces (10 triangles each).
- The skin ring was open: no skin piece between the free border of the medial thigh / anal-region skin and the vulva. Axial
  slices open at y −126…−98, −68…−57 and −39 mm; 20 % of rays aimed into the opening met no skin within 15 mm.
- 24 structures had vertices outside the skin in the region (gracilis, adductor longus, pectineus, external pudendal vessels,
  genitofemoral nerve, CVH perineal muscles, perineal body, clitoris, rule-based EAS).

## 2. Atlas facts used (owner's books, knowledge only — no text or figure copied; page images stayed in the scratchpad)
| fact | source |
|---|---|
| The perineum is, externally, the interval between the upper medial thighs and the lower buttocks, limited in front by the mons pubis | Mannan's Regional Dissection and Surface Anatomy, 14th ed. 2017, p. 343 |
| Diamond outlet: pubic arch in front, coccyx tip behind, ischiopubic rami and ischial tuberosities anterolaterally, sacrotuberous ligaments posterolaterally; palpable: symphysis, tuberosities, coccyx | Mannan pp. 343–344; Gray's Atlas of Anatomy p. 244 |
| The interischial line passes just in front of the anus (urogenital triangle in front, anal triangle behind) | Mannan pp. 344–345 |
| Labia majora: thick fat-filled folds running down and back from the mons, diminishing posteriorly, convex lateral surface; anterior and posterior commissures; median pudendal cleft, almost horizontal when erect | Mannan pp. 361–362 |
| Posterior commissure about an inch in front of the anus, over the perineal body | Mannan p. 361; Gray's Atlas p. 243 |
| Gynaecological perineum (posterior commissure → anus) about an inch | Mannan p. 362 |
| Mons pubis: fat-pad elevation over the symphysis | Mannan p. 361 |
| Labia minora, vestibule, urethral and vaginal openings within the cleft, medial to the labia majora | Mannan pp. 361–362; Gray's Atlas pp. 242–243 |

Gray's Atlas of Anatomy: the owner's scan has no title / copyright page (edition not known); pages are the printed page numbers.

## 3. The rule
1. **Clean the real surface (no vertex moves).** Loose pieces removed. A face of its outer sheet goes when one of its vertices lies
   past the free rim of the opening (the line through it along the local inward direction misses the Coons patch of the opening)
   and is not at least 0.3 mm under a neighbouring region's outer surface — the fragments and the flap. Pieces cut off from the main
   surface go. The 3 mm slab is rebuilt from its own outer and inner vertices.
2. **Close the ring with a rule-based surface** `skin_perineum_rule_q358` ("Perineal and labial closing skin (rule-based)"):
   - domain: rows between the two rails of the free rim (Q202 loop, 36 border vertices of the anterior-thigh, femoral-triangle,
     inguinal, hypogastric and anal-region skin), bottom row = the anal-region border, top = the mons apex; a Coons patch;
   - a height along each row's inward direction, harmonic (projected SOR) between: the rim (0, exact — outer and inner border
     vertices are the neighbours' own, so the load-time skin weld joins them), the real vulva (held 1 mm behind its outer layer, so
     the real mons / labia / vestibule stay on top), and the deeper structures (held skin-thickness + 0.3 mm under it; they win);
   - rows re-sampled by arc length on the walls, four blended rows at the posterior cap, Taubin smoothing of the interior;
   - a 3 mm closed slab like every Z skin region; appended (no index moves), rigid in the pelvis segment of the pose rig.
   Topographically it is the medial-thigh wall of the pudendal cleft on each side, the skin between the vulva and the anal
   region over the perineal body, and the fill of the real surface's gaps.
3. **Guarded tuck (Q353 rule)** of structures still outside the closed skin (cap 8 mm, flip / stretch / bone / volume / mirror-twin
   guards); a structure whose guard fails stays and is listed. Thigh structures (saphenous, lateral femoral cutaneous) are left to
   their own rounds.

## 4. Real vs rule-based (numbers: the report)
- **Real** (`skin_vulva_cvh`, CVH, registered in Q336): outer area 8,396 → 4,549 mm² kept; removed 2 loose pieces (10 + 10
  triangles, 11 + 81 mm²) and 1,075 outer triangles (3,847 mm²: 904 past the rim and not under a neighbour, the rest cut-off
  pieces); no vertex moved (max 0.001 mm after re-quantisation). Slab 1,784 vertices / 3,620 triangles (the source's 4
  non-manifold edges remain, so not watertight).
- **Rule-based** (`skin_perineum_rule_q358`): outer area 7,292 mm², of which ~4,675 mm² not under the real surface; 3 mm slab,
  4,294 vertices / 8,584 triangles, watertight, 21.7 cm³. Under the real surface on 6,539 of 8,427 samples; 268 samples where a
  deeper structure (gracilis, perineal body) lies in front of the real surface win, 110 vertices of the rule surface lie in front
  of the real one. 45 folded sliver faces (36 mm²) at the anal-region notch; longest edge 15.3 mm.
- **Ring**: open axial slices y −126…−98, −68…−57, −39 → none; rays into the opening meeting no skin 20.4 % → 0 %.
- **Tuck** (Q353 rule): adductor longus l/r, clitoris (cavernous body), genitofemoral n. l/r, perineal body, external pudendal
  veins (l), superficial external pudendal artery l/r — max 5.1 mm (cap 8). Kept (guards failed): gracilis l/r (6 / 14 vertices,
  ≤ 1.3 mm outside, at the anterior-thigh skin border). Region structures with vertices outside the skin: 21 → 2.
- **Atlas check**: anus skin point (external anal sphincter axis, straight down) z 7.8 mm vs the interischial line z 3.3 mm (atlas:
  just behind the line — here 4.5 mm in front); posterior margin of the vestibule's openings 38–40 mm from the anus (atlas: the
  posterior commissure ~25 mm, the fourchette a little in front of it).
Full numbers: `data/derived/Q358_perineum_report.json`.

## 5. Apply
    python3 scripts/anatomy/q358/perineum_skin_q358.py --page-dir build/q309/viewer_base_female --write
      -> atlas_viewer_base_female_geo_00..03.txt, atlas_viewer_base_female.html, index.html (*.q358 beside them)
      -> data/anatomy/pose_rig_base_f.json (skin_vulva_cvh vertex count; + skin_perineum_rule_q358 rigid in the pelvis segment)
      -> data/derived/Q358_perineum_report.json
    then the regen with the geo files 00..03, __ANATOMY_manifest, __ANATOMY_files, nmsk-pose-rig in --expect-changed.
Regen steps that pick the new structure up unchanged: pose rig inject (needs the spliced rig), symmetry sidecar (side m), groups
sidecar (manifest ids), card rules (Q354), the load-time skin weld (sys skin). The search index (Q306) lists it only after
`build_search_q306.py --src build/q309 base_m base_f` is re-run (committed data).

## 6. What still differs from the atlases
See the round report; in short: the Base body's crotch is Z-Anatomy's male-derived shape, so the cleft walls are long (the thighs
hang 20–37 mm below the vulva) and the labia majora are narrower than an atlas figure; the real surface keeps the CVH segmentation's
2–4 mm facets and its own introitus / meatus openings (closed behind by the rule surface); no pubic hair or pigmentation.
