# Q398 — finishing Q394: what still lay outside the skin (Base · Male / Base · Female)

Owner, 2026-11-25: "You must make sure that all the structures that should be under the skin ARE under the skin!!" Q394
(`docs/Q394_under_skin.md`) left open defects; Q398 works them, largest first. Base pages only; frozen pages untouched; no template
change. Work done on private copies of `build/q309` (which already carries Q394); `build/` not written.

Tools: `scripts/anatomy/q398/refit_q398.py` (rest: structure refit, skin offset, refit again; dry run / `--write`),
`scripts/anatomy/q398/rig_q398.py` (pose-rig weights from the skin over a structure). The census / verifier are Q394's
(`scripts/anatomy/q394/under_skin_q394.py`, `verify_under_skin_q394.py`), extended by one reported (not counted) class, below.
Test `tests/test_q398_refit.py`. Reports `data/derived/Q398_refit_<page>.json`; the verifier's open-defect list
`data/derived/Q394_open_defects_<page>.json` is replaced by the Q398 list (every (state, structure) left, its numbers, the Q394
numbers where it was on that list, and the reason).

## 1. Fat / soft-tissue compartments (Q295) and every other structure: depth-remap refit
Q394's envelope tuck moved a vertex by up to `amp - K d` and capped the move (12 mm) and the volume change (2 %); the thick thigh
compartments needed 20+ mm and thin shells lost more than 2 %. Q398 remaps depth instead (rule-based):
- depth `d` of a vertex = signed distance under the skin's inner sheet; each vertex outside (Q394 test, parity-confirmed) needs
  `e = GAP - d` (GAP 0.3 mm); `E(x)` = Lipschitz envelope of `e` (slopes 0.5, 0.3, 0.15 tried), direction = Gaussian mean of the inner
  normals. The column under `x` is remapped `[L, D] -> [GAP, D]` (`L = GAP - E`), a vertex moving by `E (D - d) / (D - L)`: monotone
  in depth, so the column keeps its order (no fold).
- **shell** (fat / unlabelled compartments): `D` = the compartment's own deepest depth within 8 mm — its deep face (on the muscle
  layer) stays, the part under the skin is rebuilt between the skin's inner sheet and that face, i.e. made **thinner** there. Cap
  25 mm, volume / area change recorded (sanity cap 30 %).
- **solid** (everything else): `D` = own deepest depth + 2E + 2 mm (close to a translation); for coarse thin tubes also a plain
  translation with slopes 0.1 / 0.05. Q394's guards: move <= 12 mm, volume (closed) / area (open) <= 2 %, flips <= 0.5 % of moved
  faces, no vertex newly in a bone (bone_yield). A structure that ends with fewer vertices outside and fails only "still outside" is
  kept as PARTIAL.
- In-slab vertices (not outside) are not requirements: tried first, a snug shell was crushed (-20..-30 % volume).

Compartments refitted (signed volume change for closed meshes; open meshes have no volume, area change given). **They are thinner
than the CT / cryosection compartments under the skin** — the remap puts their outer face 0.3 mm under the page skin's inner sheet
and keeps the deep face; nothing says the real fat there is that thin (the page skin is the Z-Anatomy fit, 2–3 mm thick):

| page | compartment (move max mm, volume %) |
|---|---|
| Base · M | subcut thigh L 19.7 / -11.3, R 17.8 / -8.2; unlabelled thigh L 21.2, R 20.0 (open, area < 1 %); subcut abdomen 4.1 / -12.4; subcut upper arm L 6.3 / -8.5, R 5.7 / -11.0; subcut forearm R 3.9 / -10.1 (L open); subcut hand L / R 3.8 / -26.2, -25.0; unlabelled hand L / R -12.9 / -16.1; subcut neck -8.6; subcut foot L / R -6.5 / -5.6; unlabelled foot L / R -9.1 / -5.5; deep foot L -1.9; subcut leg R -2.0; deep thigh L -0.1; subcut thorax, unlabelled forearm / leg / upper arm L (open, area 2.7–3.5 %) |
| Base · F | subcut thigh R 18.6 / -11.0 (L open, 13.4 mm); unlabelled thigh L 15.8 (open), R 19.0 / -5.2; subcut thorax 10.2 (open); subcut foot L 11.2 / -17.3, R 4.2 / -13.0; subcut hand L / R -22.8 / -18.7; unlabelled forearm L / R -9.5 / -10.6; unlabelled upper arm R -11.6; unlabelled hand L -8.8; unlabelled foot L / R -4.0 / -6.1; deep hand R -3.8; deep thorax -0.1; subcut forearm / leg / upper arm / pelvis / neck (open) |

Not fixed: fat_subcut_head, soft_unlabelled_head / neck (PARTIAL: a few vertices at the face / neck openings), fat_deep_abdomen
(flips), Base·F fat_deep_upper_arm_r (flips).

## 2. Skin offset outward (owner's delegate, main thread 2026-11-25)
Only where the page skin is demonstrably thinner / closer than the structures it must cover (toes, fingers, lips / philtrum,
perineal patch borders — `SKIN_REGIONS`), or anywhere the slab under the closest outer point is < 0.5 mm (Q394 cause class (d),
per vertex), and only for what step 1 left. Requirement `r = GAP + 0.3 - d`, total cap 4 mm. Every skin vertex (both sheets,
walls) moves OUTWARD along the skin's smoothed outer normal at its closest outer-sheet point `q`, oriented by the ray-parity test
(a swapped outer / inner patch has its "outer" normal pointing in: found on the thigh / forehead in a first run, now caught), by
`max_j (r_j - 0.2 |q - q_j|)+` over requirements whose normal agrees; the nail plates follow. Evaluating at `q` moves a slab's two
sheets together and coincident border vertices of neighbouring pieces together (the load-time weld is kept); the move fades to 0
over 3 mm towards skin pieces that may not move. Held (faded over 3 mm): a fold (outward offset of a concave cleft turning a face by
> 60° or shrinking it below 30 %), a moved outer vertex that would not lie outside the skin as it was (it would enter the next digit),
and points where neither side is clearly outside. Five rounds, the best kept.

**Per-group acceptance.** Moving the skin out changed what the outside test sees in the digits (next section): a structure can
read worse although nothing moved towards it. So each group (one hand's digits, one foot's toes, the mouth, each other piece) is
tried at scale 1, 1/2, 1/4 and kept at the first scale where the complete outside test gives a smaller total (count and depth) and
no structure more than 2 vertices / 0.75 mm worse (those within tolerance are listed in the report). Result:

| page | kept |
|---|---|
| Base · M | left hand digits ×0.5, right hand ×0.25, left toes ×0.25, mouth ×1, nasal region L / R, auricular L, temporal R, urogenital L / R; right toes not moved |
| Base · F | mouth ×0.25; arm R / elbow L R (anterior), posterior elbow L, buccal L / R, auricular L, submandibular R, lateral thorax R (all class (d) thin-skin patches); hands, toes, perineal patch and vulva not moved (every scale made a structure worse) |

Per piece (report `skin`): vertices moved, max move (<= 4 mm), added volume (outer-sheet sweep), slab thickness (median / 5th
percentile) before / after at the moved faces; each moved piece's card carries a "Q398:" badge with these. The thickness is kept
to within a few tenths of a mm in most pieces; where the slab was already thin (perionyx, philtrum, the urogenital patch on
Base·M: 5th percentile 2.7 -> 1.1 mm) it gets thinner — never below the page's own minimum (~0 mm: the page has zero-thickness
seams). Silhouette changes are small (0.1–7.8 cm³ per piece; max 4 mm).

## 3. A gap in the test (new, reported, not counted)
Q353's / Q394's outside test needs `s_in < 0` ("deeper than the inner sheet is under the skin whatever the outer sheet says").
Where the closest inner-sheet triangle belongs to ANOTHER part of the skin — the next toe, the far side of a thin digit, the rim of
an opening — a vertex outside the outer surface (`s_out > 0`, confirmed outside by the ray-parity test) is not counted. On Base·M
at rest that was 1422 vertices of 115 structures before Q398 (third toe phalanges 86 vertices up to 6 mm, plantar ligaments, toe
capsules and nerves 5–7 mm), plus opening-rim leaks (maxilla / nasal septum at the nostrils, orbicularis oris at the mouth,
lateral rectus at the eye) and single-vertex glitches (a rib "50 mm"). The census now reports this class as `__hidden__`; the
verifier prints it per state ("not counted ... outside by ray parity but deeper than the closest inner sheet of another skin
part") and keeps it out of OK / FAIL (it is not yet separable from the opening leaks). The skin-offset acceptance uses the complete
test. This is why moving the toe skin out made toe structures "newly outside": they were outside before and not counted.

## 4. Pose (rig weights)
`rig_q398.py`: a structure outside in a pose takes `s W_skin + (1 - s) W_knn` — `W_skin` the barycentric weights of the closest
inner-sheet triangle of the skin over it (its own skin: the arm's fat is under the arm's skin, never under the flank's), `W_knn`
Q394's KNN-4 donors (non-fat structures, never itself); `s` 1 at <= 6 mm depth, 0 at >= 20 mm (pass 1), 30 / 60 mm (pass 2, for what
pass 1 did not help). Kept only if no pose state got worse (count, depth + 0.05 mm) and one got better (census of every state,
the Q394 census states). Bones are never re-weighted (the skeleton carries the joints).

**Restricted to fat / fascia / lymph.** The rule first also improved muscles, vessels and nerves by the census (Base·M 151, Base·F
161 structures, incl. the lateral intermuscular septum R 84 -> 0 mm and the lateral pectoral n. L 71 -> 0.6 mm), but the browser
pose verifier (`scripts/anatomy/q384/verify_pose_q384.py`, on a regenerated page) then showed NEW failures on Base·M (22 '!!' vs 12
with the Q394 rig): kinks of biceps, brachial artery, ulnar n., basilic v., rectus femoris, gastrocnemius in hip / knee and shoulder
moves, and origins / insertions leaving their bones (biceps, semimembranosus, adductor longus). Skin weights deform a muscle or a
long tube that the rig had moving with its bones. So only fat compartments, fasciae (incl. septa) and lymph nodes keep the new
weights: **Base·M 36 structures, Base·F 45** (the same per-structure acceptance; each structure's pose geometry depends only on its
own weights, so the filtered set needs no new census). The septum's fix is kept (fascia); the lateral pectoral n. and the muscles
are left open with their numbers.

## Numbers (structures / vertices outside / deepest mm, Q394 test; "hidden" = §3, not counted)
Q394 after = `data/derived/Q394_under_skin_<page>.json` totals_after; Q398 refit = this round's rest geometry with the Q394 rig;
Q398 final = with the Q398 rig (fat / fascia / lymph only, §4).

Base · Male:

| state | Q394 after | Q398 refit (Q394 rig) | Q398 final | hidden (final) |
|---|---|---|---|---|
| rest | 103 / 9011 / 13.91 | 68 / 526 / 4.0 | 68 / 526 / 4.0 | 111 / 974 / 50.3 |
| sh_abd | 139 / 12426 / 83.8 | 112 / 4162 / 83.8 | 105 / 3222 / 70.6 | 118 / 1273 / 25.2 |
| sh_flex | 175 / 16363 / 83.8 | 146 / 8165 / 83.8 | 144 / 6101 / 29.6 | 160 / 3781 / 21.7 |
| arm_elbow | 148 / 12310 / 83.8 | 123 / 3814 / 83.8 | 119 / 3198 / 13.9 | 115 / 1073 / 18.7 |
| hipknee | 150 / 13689 / 382.01 | 128 / 5211 / 382.0 | 126 / 3199 / 46.6 | 147 / 1526 / 18.7 |
| neck_flex_rot | 121 / 9535 / 13.91 | 84 / 1076 / 9.6 | 83 / 940 / 6.5 | 112 / 1038 / 50.3 |
| neck_ext_lat | 113 / 9376 / 19.51 | 78 / 878 / 19.5 | 78 / 786 / 12.8 | 108 / 971 / 75.1 |
| trunk | 137 / 10157 / 58.01 | 108 / 2066 / 58.0 | 104 / 1530 / 18.9 | 103 / 966 / 18.7 |

Verifier: `Q394_UNDER_SKIN_FAIL viewer_zan_atlas: 827 (state, structure) residuals, undocumented 0, documented >= 0.5 mm 590` (Q394:
1086 / 885); at rest 68 structures, 41 of them >= 0.5 mm. (With the unrestricted rig of §4 it was 752 / 515.)

Base · Female:

| state | Q394 after | Q398 refit (Q394 rig) | Q398 final | hidden (final) |
|---|---|---|---|---|
| rest | 123 / 7714 / 13.82 | 93 / 680 / 8.4 | 93 / 680 / 8.4 | 175 / 1775 / 17.0 |
| sh_abd | 177 / 11684 / 261.29 | 151 / 4843 / 281.7 | 146 / 2996 / 55.7 | 209 / 2353 / 84.3 |
| sh_flex | 207 / 13982 / 398.47 | 186 / 7205 / 398.1 | 176 / 4743 / 39.3 | 230 / 3853 / 84.3 |
| arm_elbow | 178 / 11698 / 241.72 | 158 / 4724 / 195.6 | 156 / 3501 / 27.1 | 198 / 2022 / 84.3 |
| hipknee | 177 / 12607 / 32.16 | 157 / 5749 / 32.2 | 156 / 3985 / 18.0 | 189 / 1836 / 17.0 |
| neck_flex_rot | 154 / 8081 / 13.82 | 129 / 1085 / 6.4 | 128 / 996 / 6.4 | 169 / 1846 / 17.0 |
| neck_ext_lat | 140 / 8161 / 16.59 | 114 / 1142 / 16.6 | 113 / 1075 / 8.8 | 166 / 1700 / 20.3 |
| trunk | 164 / 9250 / 94.28 | 144 / 2433 / 94.3 | 141 / 1639 / 12.9 | 159 / 1783 / 84.3 |

Verifier: `Q394_UNDER_SKIN_FAIL viewer_base_female: 1109 (state, structure) residuals, undocumented 0, documented >= 0.5 mm 877`
(Q394: 1320 / 1107); at rest 93 structures, 74 of them >= 0.5 mm. (Unrestricted rig: 1032 / 798.) Rest: maxilla L / R 8.4 mm under the philtrum (bone; the mouth group's skin moved only ×0.25 = <= 1 mm) is the deepest.

## Open defects (the verifier's list)
Every (state, structure) left, with numbers and reason: `data/derived/Q394_open_defects_<page>.json`. By kind, at rest:
- **Toes / foot**: phalanges (bone: never moved), capsules, collateral / plantar ligaments, plantar digital nerves / vessels 0.5–5 mm.
  The toe skin of the source fit is 3 mm thick on the plantar side and the structures lie on the phalanges (no room: bone_yield);
  the skin offset of the toes could not be accepted (Base·M right toes, Base·F both: every scale made a neighbour worse — the toes
  touch, the test is ambiguous between them, §3).
- **Fingers / hand**: DIP / PIP capsules, dorsal / palmar digital vessels and nerves 0.5–2.8 mm (Base·F hands: skin offset not
  accepted; Base·M partly, ×0.25–0.5). Thin coarse tubes flip under any local move.
- **Face / head**: Base·F depressor anguli oris R 5.6 mm, depressor labii inferioris R 5.3 mm, inferior alveolar a. R 4.5 mm, mental
  branch 4.8 mm (buccal region R: the skin there is not class (d) and not a listed region, so no offset; the structure-side refit
  fails the 2 % volume / flip guards), orbicularis oris 1.6 mm, alar cartilages 1.1 mm (cartilage is not moved, like bone); Base·M
  orbicularis oris 3.9 mm newly counted (was in §3's class before the mouth's skin moved), alar cartilage R 0.7 mm.
- **Other thin tubes** (Base·F ulnar n. at the elbow, great saphenous v. at the malleolus, posterior auricular v., cutaneous
  nerves) 1.0–1.4 mm: lie on bone / fascia; the move flips their few long faces.
- **Pose**: what the rig rule did not improve without making another state worse (mostly fat compartments at contacts and the
  shoulder states), and every muscle / vessel / nerve (the rule is restricted to fat / fascia / lymph, §4) — e.g. Base·M lateral
  pectoral n. L in shoulder abduction (71 mm), Base·F latissimus dorsi L; see the list.
- **Worse than on the Q394 list at rest** (by the Q394 count): Base·M 13 entries — orbicularis oris L / R 3.9–4.0 mm (were in §3's
  uncounted class; the mouth skin moved and the Q394 test now sees them), dorsal digital veins of hand L 0.2 -> 1.1 mm, and ten
  entries < 0.5 mm at the digits (the skin offset's tolerance, §2); Base·F 6 — depressor anguli oris R 5.6 -> 6.4 mm, fat_deep_thorax
  1.9 -> 2.5 mm, brachial fascia R 0 -> 1.9 mm, masseteric fascia R 0.7, fat_deep_upper_arm L 0.55, fat_subcut_abdomen 0.36 mm.
  In the pose states Base·M 103 and Base·F 47 entries are new or deeper than on the Q394 list (the rest refit and the skin offset
  change what each pose moves), while the vertices outside per pose state fell by 63–92 % (table).

## Guards re-run
- Nerve verifier `scripts/anatomy/q388/verify_nerve_course_q388.py` on the patched pages: Base·M 8 FAIL checks, Base·F 5 — the same
  checks as on the source pages.
- Vertex / triangle counts and order unchanged (asserted on write); 16-bit round trip <= 0.007 mm.
- Pose browser verifier `scripts/anatomy/q384/verify_pose_q384.py` on pages regenerated (`regen_template_only.py`, to /dev/shm)
  from the patched pages with the Q394 rig and with the Q398 rig: Base·M 12 '!!' lines, identical (incl. the numbers) with both
  rigs (the 12th, the phone panel, fails with the Q394 rig too); Base·F the same 11 '!!' lines, plus the phone-panel check once
  (523 px), which passed on a re-run of that part with both rigs (flaky, not the rig).

## Limits (honest)
- Not OK: the verifier still prints `Q394_UNDER_SKIN_FAIL` on both pages; every residual is documented.
- The refitted compartments are thinner than the imaged fat under the skin (they are refitted to the Z-Anatomy skin, not measured).
- The skin offset is rule-based geometry (badged); its acceptance is by the census, not by an anatomical source.
- §3's class is not counted by the verifier; at the toes it is very likely real, at the nostrils / mouth / eyes it is mostly the
  test leaking through the opening.
- The pose census is the numpy port of the page's rig; the rig rule is a display rule.
