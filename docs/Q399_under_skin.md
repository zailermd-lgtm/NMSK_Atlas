# Q399 — the last under-the-skin defects: a test that was blind in places, and Q398's regressions (Base · Male / Base · Female)

Owner, 2026-11-26: continue "everything that belongs under the skin must be under the skin". Base pages only; frozen pages
untouched; no template change; no rig change. Work on private copies of `build/q309` (Q394 + Q398 state); `build/` not written.

Tools (`scripts/anatomy/q399/`): `eval_q399.py` (per-structure census in all eight states for candidate geometry),
`fix_q399.py` (structure candidates), `skin_q399.py` (Q398 skin groups undone / per-digit and mouth offset), `open_list_q399.py`
(the verifier's open-defect list). The test itself is extended in `scripts/anatomy/q394/under_skin_q394.py` (below); the verifier
`verify_under_skin_q394.py` is unchanged and uses it. Test `tests/test_q399_census.py`. Reports `data/derived/Q399_*_<page>.json`.

## 1. Why Q398 "made things worse": the test was blind where the skin is a single sheet
Q353's sheet split labels a skin face outer / inner only when the slab's other sheet lies 0.8–6 mm behind it; every other face is a
wall (0) and is in neither the distance test nor the parity surface. Measured:
- whole skin areas are single sheets or thin pairs: Base·F dorsal toe skin R 88 % of its area walls, perionyx of the toes 61–67 %,
  mental region 25–33 %; Base·M dorsal toe skin R is a single sheet wound INWARD (219 of 233 faces in the toe tube);
- a skin offset changes the slab thickness, so faces leave the 0.8–6 mm window and drop out of the test. Most of Q398's "worse than
  Q394" entries were structures Q398 never moved: e.g. Base·F depressor anguli oris R vertex 37 — its closest outer face became a
  cheek face 6.4 mm away once the nearer one was relabelled a wall (5.6 → 6.4 mm "outside"). With the faces labelled as the moved
  skin has them, Q398's skin offset made most groups worse, not better (section 3).

**Q399 completion** (`single_sheet`, `confirm_single`): wall faces are grouped into patches (normals within 60°), the patch's
area-weighted vote of Q353's direction (away from the nearest bone vertices) decides its side: a face of an outward-voting patch that
faces out is `+2` (joins the outer sheet, and flipped the inner sheet: thickness 0 where there is no inner sheet); an inward-facing
face is `-2` (inner side of a thin pair, when the other sheet lies right outside it) or `+3` (the only sheet there, wound inward:
joins the outer sheet flipped). A `+2 / +3` face is kept only where the parity test agrees which side is out (0.4 mm either side);
inside a cavity both sides read alike and the face goes back to a wall. Not completed: the auricle pieces (Q394 treatment kept) and
the skin round the palpebral fissure (`orbital_region`, lid pieces: its fornix faces face the excluded eyeball through the opening —
completing them made the medial rectus read "5.5 mm outside").

## 2. Per-digit test (toes touch; fingers)
`Digits`: a vertex whose nearest digit axis (segment through the digit's phalanges) is within 14 mm and that lies distal of 40 % of
the proximal phalanx (beyond the web) is judged against THAT digit's skin only — the outward-facing faces (`+1/+2/+3`, radial
component > −0.3) whose nearest digit axis is the same — by eight rays perpendicular to the digit axis (a digit is a tube; a ray along
it would leave through the open base); outside needs 7 of 8 (a hole — the web, a coarse face — can only make a vertex read outside);
depth = distance to that digit's skin. Between two touching digits the boundary is the plane midway between their axes, so a
neighbour's skin no longer hides or fakes anything. The nail plates are not used (they lie under the digit skin's outer sheet here:
116 of 206 doubled faces on a finger). Hidden class (Q398 §3) no longer applies to digit vertices.

Sanity (Base·M, rest: outer faces' centroids pushed along the radial direction; fraction read outside, among points still in the same
digit): fingers +0.5 mm 54–84 %, +1.5 mm 65–91 %; toes +0.5 mm 22–79 %, +1.5 mm 26–87 % (toes 2–3 worst: the toe meshes are coarse,
1–5 faces per 30° per 3 mm slice); −0.5 / −1.5 mm (inside) read outside 0–10 %. **So the per-digit test under-counts at the toes:**
a toe residual can be larger than reported; it does not invent outside vertices on the phalanges as the whole-body test did (e.g.
a proximal phalanx "14 mm outside" with a leaky tube, 0 with the corrected one).

## 3. What was done (rule-based; judged with the completed test in all eight states)
"Worse than Q394" = more vertices outside, or deeper by > 0.005 mm, than the page as it was after Q394, under the SAME (Q399) test.
1. **Structures** (`fix_q399.py`): for every structure outside in some state, candidates `cur` (Q398), `q394` (Q398's refit undone),
   `refit` / `refit394` (Q398's depth remap with its guards — move, volume / area ≤ 2 %, flips, no vertex into bone — applied to
   each); the first by (states worse than Q394, Σ depth + 0.02 × count) is kept. Two passes (before and after step 2).
2. **Skin** (`skin_q399.py`): (a) each Q398 skin-offset group undone where that leaves fewer (state, structure) entries worse than
   Q394; (b) the outward offset (Q398's rule, ≤ 4 mm total per vertex including Q398's) per DIGIT — requirements from one digit move
   only that digit's skin, fading to 0 over 3 mm — and for the mouth, kept at scale 1 / ½ / ¼ only when no structure near it ends
   worse than max(Q394 value, its value now) in any state and the total falls. The moved pieces are re-labelled exactly as the
   verifier will label them (labels are never carried over: that was Q398's trap).

What moved (reports `data/derived/Q399_fix_<page>.json`, `Q399_skin_<page>.json`; every changed card has a "Q399:" badge, an
undone refit / offset takes back its Q394 card record):

| page | structures (pass 1 + pass 2) | Q398 skin groups undone | Q399 outward offsets kept (per digit / mouth) |
|---|---|---|---|
| Base · M | 42 + 12 (Q398 refit undone 3; refit 37; refit of the Q394 geometry 14) | left toes, left hand digits, right hand digits, mouth, urogenital L / R | toe 5 L / R ×¼, toe 1 L ×1 / R ×¼, several fingers ×½–1, mouth ×1 |
| Base · F | 58 + 26 (undone 4; refit 56; refit of Q394 geometry 24) | mouth, anterior arm R, anterior elbow L / R, buccal L / R, lateral thorax R, submandibular R | toe 5 L / R ×¼, toe 4 L ×1, most fingers ×½–1; mouth refused at every scale |

Refused: the offsets of toes 2–4 (both pages) and of the Base·F mouth (inferior labial vessels / orbicularis oris worse in the
neck and trunk states at every scale); the nose / auricular pieces of Base·M (undoing them adds more than it removes).
Total skin offset per vertex (Q398's + Q399's) ≤ 4 mm, asserted on write; vertex / triangle counts and order unchanged.

## 4. Numbers (structures / vertices outside / deepest mm; the Q399 test throughout, `data/derived/Q399_census_<page>.json`)

Base · Male:

| state | after Q394 | after Q398 | after Q399 | worse than Q394: Q398 → Q399 |
|---|---|---|---|---|
| rest | 113 / 8920 / 13.9 | 94 / 523 / 10.6 | 65 / 690 / 10.6 | 16 → 2 |
| sh_abd | 138 / 12316 / 83.8 | 121 / 3258 / 70.6 | 101 / 3449 / 70.6 | 20 → 3 |
| sh_flex | 178 / 16181 / 83.8 | 159 / 6051 / 29.6 | 140 / 6213 / 29.6 | 16 → 2 |
| arm_elbow | 154 / 12222 / 83.8 | 142 / 3246 / 13.9 | 120 / 3437 / 13.9 | 15 → 2 |
| hipknee | 162 / 13542 / 382.0 | 150 / 3216 / 46.6 | 126 / 3210 / 47.3 | 25 → 2 |
| neck_flex_rot | 121 / 9407 / 13.9 | 102 / 899 / 10.6 | 82 / 1081 / 10.6 | 14 → 2 |
| neck_ext_lat | 116 / 9266 / 17.8 | 97 / 770 / 12.8 | 76 / 950 / 12.8 | 15 → 3 |
| trunk | 128 / 10101 / 58.0 | 116 / 1546 / 18.9 | 103 / 1727 / 18.9 | 18 → 3 |

Base · Female:

| state | after Q394 | after Q398 | after Q399 | worse than Q394: Q398 → Q399 |
|---|---|---|---|---|
| rest | 140 / 7771 / 13.8 | 128 / 828 / 8.4 | 71 / 607 / 8.4 | 9 → 0 |
| sh_abd | 178 / 11710 / 261.3 | 164 / 3112 / 55.7 | 124 / 2874 / 55.7 | 9 → 0 |
| sh_flex | 207 / 13934 / 398.5 | 190 / 4845 / 39.3 | 146 / 4650 / 39.3 | 9 → 0 |
| arm_elbow | 186 / 11759 / 241.7 | 179 / 3658 / 27.1 | 133 / 3425 / 27.1 | 12 → 0 |
| hipknee | 182 / 12649 / 32.2 | 168 / 4136 / 18.0 | 131 / 3909 / 18.0 | 15 → 2 |
| neck_flex_rot | 160 / 8139 / 13.8 | 150 / 1154 / 6.4 | 107 / 967 / 6.0 | 13 → 1 |
| neck_ext_lat | 143 / 8133 / 16.1 | 134 / 1181 / 7.5 | 88 / 980 / 7.5 | 12 → 0 |
| trunk | 163 / 9193 / 94.3 | 155 / 1714 / 12.9 | 116 / 1510 / 12.9 | 8 → 1 |

Structures outside fell in every state; vertices outside at rest rose on Base·M (523 → 690) because undoing Q398's toe / hand
offsets brings back vertices it had covered while it pushed others out further (every such entry is at or below its Q394 value).

**Still worse than Q394 (the same test)** — Base·M: major alar cartilage R (1.24 → 1.31 mm; cartilage is not moved, the nasal skin
offset of Q398 is kept: undoing it adds 15 entries), lateral process of the nasal septal cartilage / septal cartilage in two head
states (0.37 / 0.42 mm), middle phalanx of toe 3 R (bone, 1 vertex 0.76 mm; no skin under it moved — a sheet label of the toe skin
changed with the global parity confirmation), soft_unlabelled_abdomen in shoulder abduction (+0.025 mm). Base·F: genitofemoral n. L / R
in hips/knees 90° (perineal skin: 7 single-sheet faces confirmed once the hand / arm skin changed — the parity rays from the perineum
cross the thigh and the hand; nerve and perineal skin unchanged, inside at rest), fat_deep_abdomen in the trunk state (2.7 → 7.4 mm:
the price of undoing Q398's lateral-thorax offset, which removed four other entries; its refit fails the flip guard),
fat_subcut_neck in neck flexion (+0.05 mm).

Verifier (`verify_under_skin_q394.py`, Q399 test, Q399 open list): `Q394_UNDER_SKIN_FAIL viewer_zan_atlas: 813 (state, structure)
residuals, undocumented 0, documented >= 0.5 mm 606`; `Q394_UNDER_SKIN_FAIL viewer_base_female: 916 ..., undocumented 0, documented >= 0.5 mm
757` (at rest M 65 structures, 42 >= 0.5 mm; F 71, 58 >= 0.5 mm). Not comparable with Q398's 827 / 1109: the test now sees more skin.

## 5. The brief's items
1. **Q398 regressions**: mostly a test artefact (section 1) plus real ones from Q398's skin offsets; under a test that labels the
   moved skin as it is, worse-than-Q394 entries fell from M 139 / F 87 (all states) to M 19 / F 4 (listed above, with causes).
2. **Digits**: the census is now per digit (section 2) and the toe skin is in the test where it is a single sheet. Real residuals
   remain on the toes (plantar digital nerves / vessels, dorsal digital vessels / nerves 2–6 mm; a few single vertices 10 mm, also
   at Q394) and some on the fingers (≤ 1.7 mm, mostly < 1 mm): the toe offsets 2–4 were refused (a neighbour got worse), the soft structures lie on
   the phalanges (bone guard), and the per-digit test under-counts on coarse toes (section 2).
3. **Base·F face**: maxilla 8.4 mm under the philtrum (3 vertices at the midline, 8.6 mm from the nearest skin vertex: a spike of the
   bone mesh; bone not moved) — the mouth group's outward offset was tried (≤ 4 mm cap) and refused at scale 1 / ½ / ¼ (lower-lip
   vessels and orbicularis oris read further outside in the neck / trunk states), so 8.4 mm remains. Depressor anguli oris R
   (was 5.6 / 6.4 mm: largely the cheek-face artefact of section 1) and depressor labii inferioris, the mental vessels and the
   V3 mental branch are no longer outside at rest; inferior alveolar a. R 0.31 mm; orbicularis oris L / R 3.6 / 3.8 mm (17–18
   vertices, under the philtrum: open). Base·M orbicularis oris: no longer outside at rest.
4. **Thin tubes / pose-only**: ulnar n., great saphenous v., cutaneous nerves stay ~1.0–1.4 mm (refit fails the flip / volume
   guards on their few long faces); Base·F triceps long head L 1.0 mm; the pose-only lateral pectoral n. L (M) and latissimus L (F)
   are unchanged (M lateral pectoral n. L 70.6 mm in shoulder abduction; F latissimus dorsi L 45.3 mm): no rig change this round (skin weights kinked muscles / nerves in the browser verifier, Q398 §4).
5. **Goal**: not reached — the verifier prints `Q394_UNDER_SKIN_FAIL` on both pages; every residual is on the list with its numbers,
   its Q394 value under the same test, whether it is worse, and the reason. The exclusion list is unchanged.

## Guards
- Nerve verifier `scripts/anatomy/q388/verify_nerve_course_q388.py` on the patched pages: Base·M 8 FAIL checks, Base·F 5 — the same
  checks as before.
- Pose browser verifier `scripts/anatomy/q384/verify_pose_q384.py` on the regenerated pages (`/dev/shm`): Base·M and
  Base·F each the same 11 '!!' lines as on the Q398 pages (the flaky phone-panel line passed this time).
- No rig change; the exclusion list unchanged; no template change.

## Limits (honest)
- The test changed (sections 1–2); numbers here are not comparable with the Q394 / Q398 tables, so the Q394 and Q398 pages were
  re-measured with it (the "after Q394 / Q398" columns).
- The per-digit test misses part of what is outside on the toes (sensitivity 22–87 % at 0.5–1.5 mm); the parity-based label
  confirmation is global, so a change in one place can flip a single-sheet face elsewhere (the genitofemoral entries).
- Refitted structures and offsets are rule-based geometry (badged), judged by the census, not by an anatomical source.
