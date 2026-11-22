# Q319 — the muscles on the two BASE pages: the audit, the repairs made, and the give-up list

The owner's redirection (Q319.5, translated from the Hebrew): *if a repair is possible, do it; where it is not,
or where it still looks bad after attempts, give it up.* And: *at this first stage the most important part is the
BASE models, not the reconstructed ones; the reconstructed ones will be gone into more deeply later, and
mismatches will then also be used as a warning of possible problems in the specimen — but not now.*

So this document is about **Base · Male** and **Base · Female**, which had never been audited. The Combined
pages' audit stands as the record for that later round: `docs/Q319_reconstructed_muscles.md`.

**Nothing was deleted and nothing was published.** Files written or changed: this document,
`data/derived/Q319_reconstructed_muscle_audit.json` (the two Base pages added beside the two Combined ones, and
all four re-measured with the corrected metric of §2), `data/derived/Q319_repair_report.json`,
`scripts/anatomy/q319/repair_q319.py` and the audit script.

Sources, both read read-only:

| page | source | version | `index.html` sha256 |
|---|---|---|---|
| Base · Male | `build/q309/viewer_zan_atlas` (restored from the published artifact) | `claude.ai/artifact/HdYCRuvGP8ESbggoRWCNBF` v`1794346818-0116` | `8066206e…4309e1b8` |
| Base · Female | `build/q309/viewer_base_female` (fetched here) | `claude.ai/artifact/TiXsQe3eS5ehzN64Aozyth` v`1794346848-8189` | `b66b8b39…b26b447c` |

Both match their committed pose rigs exactly (3,262 and 3,298 meshes against `count` 3,262 and 3,298), so the
rig can be reasoned about from the repository without a rebuild.

**What this round did, in four lines.**

* **Audited** both Base pages for the first time: **4 muscles per page** fail two independent severity-3 checks,
  against 10 and 5 on the Combined pages. The Base pages are in good shape (§1).
* **Repaired** the Q213 split on both pages — `opponens_digiti_minimi` was holding a 120-vertex piece of the
  **foot** — and ran the Q213 in-bone conform on the worst 20 / 22 structures: 16 and 19 accepted, 0 deleted,
  2 added per page. Buckets moved **234 / 192 / 4 → 246 / 182 / 4** (Base · Male) and
  **219 / 217 / 4 → 229 / 209 / 4** (Base · Female) (§3).
* **Corrected one of this round's own metrics**, which had been inflating in-bone findings by 3–17× on all four
  pages, and re-ran all four so the figures stay comparable (§2).
* **Gave up on four structures per page**, the same four on both, each with its reason and the cost of dropping
  it (§6). The one repair the owner should *not* approve blanket is in §3.2: pushing muscles out of bone pushes
  them into their neighbours.

---

## 1. The short answer: the Base pages are in good shape, and markedly better than the Combined ones

Same script, same rule, same thresholds on all four pages, so the columns are comparable. **Four muscles per
Base page fail two independent severity-3 checks, against ten and five on the Combined pages.**

| metric | Base M | Base F | Combined M | Combined F |
|---|---|---|---|---|
| muscle meshes | 430 | 440 | 430 | 441 |
| **defensible** | **234** | **219** | **202** | **203** |
| **repairable** | **192** | **217** | **218** | **233** |
| **not defensible** | **4** | **4** | **10** | **5** |
| generated here (rule-based + mirror) | 6 | 7 | 6 | 9 |
| R/L volume outside 0.80–1.25 | 12 | 14 | 100 | 122 |
| overlap %, median | 30.2 | 32.0 | 29.8 | 34.7 |
| over the 60 % overlap gate | 50 | 56 | 61 | 71 |
| in bone > 8 % of vertices (the project's gate) | 94 | 86 | 83 | 61 |
| in bone > 20 % of vertices | 16 | 18 | 28 | 11 |
| applicable attachment gap > 10 mm | 14 | 14 | 27 | 20 |
| applicable attachment gap > 20 mm | 12 | 12 | 17 | 12 |
| a piece in the wrong part of the body | 2 | 2 | 2 | 0 |
| mean dihedral, median deg (CVH band 27.6–31.7) | 26.7 | 28.8 | 33.4 | 31.6 |
| meshes with a boundary edge | 20 | 20 | 19 | 21 |
| volume > 2× its architecture record | 105 | 84 | 128 | 93 |
| volume < 0.5× | 34 | 36 | 30 | 43 |
| attachment bone absent from the page | 104 | 114 | 104 | 115 |

Three readings, in order of importance to the owner's three words:

* **"Inconsistent" barely applies to the Base pages.** Left/right volume disagreement outside the project's own
  0.80–1.25 band affects **12 muscles on Base · Male and 14 on Base · Female**, against **100 and 122** on the
  Combined pages — an eight-fold difference. The reason is structural, not luck: Z-Anatomy's two sides are mirror
  copies, and the Base pages do not carry the per-bone similarity fit that the Combined pages use to put those
  muscles onto a real person's skeleton. **That fit is what broke the symmetry.** The same ordering shows in the
  attachment gaps (14 / 14 past 10 mm against 27 / 20) and in the surface's own character (median mean dihedral
  26.7° / 28.8°, inside the CVH reference band of 27.6–31.7°, against 33.4° / 31.6°).
* **"Not matching" is mostly fine, and the exception is one family.** Only 12 muscles per Base page have an
  applicable attachment gap past Q198's severity-3 line of 20 mm, and they are nearly all the
  rectus-capitis / obliquus-capitis group at the skull base, whose origin the record puts on `cervical_vertebrae`
  (the atlas) while the mesh sits 26–36 mm away. Everything else reaches the bone its record names.
* **"Slack" is where the Base pages are no better, and it is Z-Anatomy's own modelling.** Muscle-into-muscle
  overlap runs at a median of 30.2 % / 32.0 %, with 50 and 56 muscles past the 60 % gate — essentially the same
  as the Combined pages, because it is inherited from the source and not produced by anything this project did.
  This is the one thing genuinely left to decide about on these two pages (§5).

### Provenance: what the Base muscle layer actually is

| | Base · Male | Base · Female |
|---|---|---|
| muscle meshes | 430 | 440 |
| `z_raw_gap_closed` — the Z-Anatomy mesh, surface nudged outward along its normals toward its neighbours (Q162) | 408 | 408 |
| `z_raw` — a plain Z-Anatomy mesh, page-level attribution | 14 | 1 |
| `z_tps_female` — the Z mesh carried onto the female skeleton by the bone-anchored thin-plate spline (Q250) | 0 | 13 |
| `other_person_registered` — Chinese Visible Human female, Wu et al. 2015 | 0 | 9 |
| `third_party_import` — SPL Inner Ear Atlas (Q296) | 2 | 2 |
| **`rule_based`** — generated here from a documented rule | **4** | **5** |
| **`mirror_fill`** — generated here by mirroring the other side | **2** | **2** |
| measured on a body | 0 | 0 |

**Six muscles on Base · Male and seven on Base · Female were generated by this project. Everything else is
Z-Anatomy's own geometry**, and the Base pages are the closest thing in the atlas to it unaltered.

---

## 2. A correction to one of this round's own metrics, found by attempting the repair

This comes before the results because it changed them, and because it is exactly the kind of mismatch the owner
said he would later want used as a warning.

The audit first measured the in-bone share as the fraction of a muscle's own **2 mm voxel solid** falling inside
a bone's 2 mm voxel solid. When the in-bone repair was attempted, the project's existing tool reported something
very different for the same structures, because it measures the share of **vertices** inside bone by exact
containment (`scripts/transfer/q213_inbone.BoneField.inside`):

| structure (Base · Male) | 2 mm voxel solid share | exact vertex share | over-read |
|---|---|---|---|
| `nasalis_l` | 73.4 % | **15.6 %** | 4.7× |
| `zan_occipitalis_muscle_l` | 52.5 % | **3.1 %** | 17× |
| `levator_labii_superioris_r` | 45.6 % | **7.7 %** | 5.9× |
| `rectus_femoris_reflected_head_l` | 32.25 % | **0.0 %** | ∞ |
| `procerus` (Base · Female) | 58.1 % | **5.9 %** | 9.8× |

Traced to its cause on the clearest case: the reflected head's voxel solid intersects exactly one bone,
`hip_bone_l`, over 32.2 % of its 676 voxels — while **no vertex of it is inside that bone at all.** The solid is
built by dilating the surface shell by one voxel and eroding back, so two surfaces closer together than the
lattice can resolve produce overlapping solids even when neither penetrates the other. The reflected head of
rectus femoris lies flush on the acetabular rim, which is where it belongs.

**And the project had already settled which measure is right.** `scripts/anatomy/q237/fill.py` line 21:
`BELLY_IN_BONE_MAX = 8.0  # muscle: % of vertices inside any bone (Q216 gate)`, and `fill.guards()` computes it
over the vertices. The overlap gate in the same file *is* a volume share (`fill.overlap_pct`, 2 mm voxels, "as
the Q204 audit"). The two are measured differently on purpose, and this round had measured both the same way.

**What changed, and only this:** the in-bone severity is now read off the exact vertex share, as the project
defines it; the 2 mm voxel share is kept as the cheap pre-filter that decides which structures enter the exact
pass (175 / 185 / 166 / 168 of them per page). No threshold was moved and no other check was touched. All four
pages were re-run so the columns stay comparable:

| page | before the correction | after |
|---|---|---|
| Base · Male | 196 def / 228 rep / 6 not def | **234 / 192 / 4** |
| Base · Female | 185 / 248 / 7 | **219 / 217 / 4** |
| Combined · Male | 176 / 242 / 12 | **202 / 218 / 10** |
| Combined · Female | 182 / 251 / 8 | **203 / 233 / 5** |

A correction note pointing here has been added to the top of `docs/Q319_reconstructed_muscles.md`; its §4 bucket
tables are the uncorrected ones, and the JSON is authoritative. Nothing else in that document is affected — the
attachment gaps, the overlap figures, the asymmetry, the piece-in-the-wrong-place findings and the whole
deletion-cost analysis all stand.

The voxel measure was not discarded: it is the only one cheap enough to run on every muscle, and where the two
agree it was pointing at something real — `zan_adductor_minimus_l/r` reads **53.4 %** of its vertices inside
bone, the largest corroborated in-bone finding on either Base page.

---

## 3. The repairs that were made

### 3.1 Repair A — the Q213 split: `opponens_digiti_minimi` on both Base pages held a piece of the foot

Z-Anatomy ships **one** mesh under the id `opponens_digiti_minimi_<side>`, and it contains the hand muscle **and
a 120-vertex piece in the foot**. Q213 separated them on Combined · Female, where `opponens_digiti_minimi_foot_l`
and `_r` ship as their own structures (rig indices 2940 / 2939, rigid entries of segments `foot_l` / `foot_r`,
120 vertices each). **Neither Base page ever received that fix.** Both still carried the merged mesh.

`scripts/anatomy/q319/repair_q319.py` re-applies it, importing `q213_zfit.components` and `q213_zfit.split`
rather than re-deriving them. **No vertex moves and nothing is deleted:** the hand component keeps the id, the
foot component becomes a new structure, so each page gains two meshes and loses none.

Verified independently of the repair script, against the page's own bones:

| | hand component | foot component |
|---|---|---|
| vertices | 210 | 120 |
| nearest point of `zan_fifth_metacarpal_bone_r` — where opponens digiti minimi belongs | **0.2 mm** | 765.4 mm (Base M) / 796.5 mm (Base F) |
| nearest point of `zan_fifth_metatarsal_bone_r` | 761.1 / 792.9 mm | **0.2 mm** |
| nearest point of `calcaneus_r` | 748.4 / 777.3 mm | 24.2 / 23.4 mm |
| volume, Base · Male right side | 1.834 cm³ | 0.558 cm³ |
| the two together | **2.392 cm³ — exactly the original 2.392 cm³** | |
| volume, Base · Female right side | 1.647 cm³ | 0.526 cm³ (original 2.173 cm³) | |

The hand piece is on the hand to within 0.2 mm, the foot piece is on the foot to within 0.2 mm, they are three
quarters of a metre apart, and the volumes sum to the original with no residue. The measurement that moves:

| | before | after |
|---|---|---|
| `opponens_digiti_minimi_r` — connected pieces | 2, where its record allows 1 | **1** |
| — a piece away from the muscle | **800.5 mm, 14.43× its own diagonal** | **none** |
| `opponens_digiti_minimi_l` — connected pieces | 2 | **1** |
| — a piece away from the muscle | **800.5 mm, 14.71× its diagonal** | **none** |
| meshes on the page | 3,262 / 3,298 | 3,264 / 3,300 |
| structures deleted | — | **0** |

**The pose rig, which usually makes a change like this expensive, is cheap here.** The two new structures are
**appended** to the manifest, so every existing index keeps its value, no skinning weight is touched, and each
becomes a rigid entry of its own foot segment — exactly how Combined · Female already carries them. The splice is
`count` 3,262 → 3,264 (Base M) and 3,298 → 3,300 (Base F), two entries added to `rigid`, two values appended to
`nv`; `scripts/anatomy/q241/make_pose_rig.py --inject` then re-checks the structure and per-structure vertex
counts against the page before writing. The exact indices and segments are in
`data/derived/Q319_repair_report.json` under `pose_rig`.

### 3.2 Repair B — the Q213 in-bone conform, adjudicated by the tool itself

`scripts/transfer/q213_inbone.repair` pushes a muscle out of the bones it is buried in under its own guards
(bounded mean and maximum move, volume 0.88–1.20×, no folded or over-stretched triangles, no attachment end
moved off its bone, muscle overlap not allowed to rise). **It accepts or holds each case itself** — which is the
owner's instruction enforced by code rather than by judgement: attempt the fix, give up where the result is not
good.

**Scope, stated plainly because it is a choice.** The project's own in-bone gate is 8 % of vertices
(`q213_zfit.IN_BONE_MIN` = `fill.BELLY_IN_BONE_MAX`), and at that line **94 muscles on Base · Male and 86 on
Base · Female** would be repaired. That is a mass geometry change on the models the owner has just called the
most important, so it was not done unasked. What was done is a **reviewable demonstration at 20 %** — the top of
the distribution — plus everything in the not-defensible bucket whatever put it there: **20 structures on Base · Male and 22 on
Base · Female**. The full 8 % pass is listed as a proposal in §5, with the complete target list recorded in the
repair report under `in_bone_full_pass_would_be`.


**The result, and the catch that matters more than the result.** The conform works: 16 of 20 accepted on
Base · Male and 19 of 22 on Base · Female, with the largest corroborated in-bone finding on either page —
`zan_adductor_minimus` at **53.4 % / 53.6 %** of its vertices inside bone — brought down to **12.8–13.2 %** by a
mean move of about 2 mm at essentially unchanged volume (×0.98–1.00).

**But it pays for that in overlap.** Because the exact vertex-overlap measure was recorded before and after each
move, the trade is visible:

| structure | vertices in bone | vertices inside other muscles |
|---|---|---|
| `extensor_carpi_ulnaris_r` (Base M) | 22.8 % → **4.4 %** | 18.6 % → **36.0 %** |
| `zan_adductor_minimus_r` (Base M) | 53.4 % → **13.0 %** | 11.1 % → **28.4 %** |
| `zan_medial_head_of_triceps_brachii_l` (Base M) | 23.7 % → **10.3 %** | 13.8 % → **27.0 %** |
| `plantar_interossei_l` (Base M) | 23.0 % → **8.5 %** | 0.8 % → 4.8 % |
| `anconeus_l` (Base M) | 25.4 % → **10.8 %** | 26.4 % → 25.2 % *(the one that improved on both)* |

**Pushing a muscle out of bone pushes it into its neighbours.** The tool's guard permits a rise — it only
refuses when the overlap both exceeds its floor and rises past its limit — so every move above was legitimate by
the project's own rules. On a Z-Anatomy page where the bellies already share space at a median of 30 %, that is
not a clean win, and it is the single most important thing to put to the owner before the full pass on 94 + 86
structures is approved. The 18 + 21 structures changed in this demonstration sit in
`data/derived/Q319_repair_report.json`, where each one's before and after are recorded on both measures, so the
demonstration can be reversed or accepted structure by structure.


**Base M — attempted on 20, accepted 16, held 4**

| structure | vertices in bone, before → after | mean move mm | volume × | **vertices inside other muscles, before → after** |
|---|---|---|---|---|
| `abductor_digiti_minimi_foot_l` | **20.3 → 11.7 %** | 0.58 | 0.915 | 11.2 → 15.3 % |
| `abductor_digiti_minimi_foot_r` | **20.3 → 11.7 %** | 0.61 | 0.917 | 11.4 → 15.8 % |
| `anconeus_l` | **25.4 → 10.8 %** | 0.87 | 0.888 | 26.4 → 25.2 % |
| `anconeus_r` | **25.4 → 10.8 %** | 0.86 | 0.887 | 26.4 → 25.4 % |
| `extensor_carpi_ulnaris_l` | **22.8 → 4.4 %** | 2.73 | 1.012 | 18.2 → 34.9 % ⚠ |
| `extensor_carpi_ulnaris_r` | **22.8 → 4.4 %** | 2.74 | 1.011 | 18.6 → 36.0 % ⚠ |
| `extensor_hallucis_brevis_l` | **20.9 → 10.7 %** | 0.72 | 0.956 | 17.3 → 22.6 % ⚠ |
| `extensor_hallucis_brevis_r` | **20.9 → 10.7 %** | 0.71 | 0.958 | 16.9 → 21.6 % |
| `medial_pterygoid_l` | **22.1 → 5.6 %** | 0.39 | 0.978 | 10.0 → 10.4 % |
| `medial_pterygoid_r` | **28.1 → 16.1 %** | 1.71 | 0.894 | 10.0 → 10.8 % |
| `plantar_interossei_l` | **23.0 → 8.5 %** | 1.09 | 0.943 | 0.8 → 4.8 % |
| `plantar_interossei_r` | **23.0 → 8.5 %** | 0.98 | 0.952 | 0.6 → 3.5 % |
| `zan_adductor_minimus_l` | **53.4 → 12.8 %** | 1.95 | 0.982 | 10.1 → 26.9 % ⚠ |
| `zan_adductor_minimus_r` | **53.4 → 13.0 %** | 2.02 | 0.978 | 11.1 → 28.4 % ⚠ |
| `zan_medial_head_of_triceps_brachii_l` | **23.7 → 10.3 %** | 0.63 | 0.97 | 13.8 → 27.0 % ⚠ |
| `zan_medial_head_of_triceps_brachii_r` | **23.7 → 10.3 %** | 0.64 | 0.97 | 13.9 → 27.0 % ⚠ |

| held | vertices in bone | vertices inside other muscles | the tool's own reason |
|---|---|---|---|
| `rectus_femoris_reflected_head_l` | 0.0 % | **77.2 %** | no gain |
| `rectus_femoris_reflected_head_r` | 0.0 % | **78.5 %** | no gain |
| `zan_lateral_crico_arytenoid_muscle_l` | 7.5 % | **69.8 %** | no gain |
| `zan_lateral_crico_arytenoid_muscle_r` | 7.5 % | **69.7 %** | no gain |

Buckets on this page after both repairs: **234 / 192 / 4 → 246 / 182 / 4** (defensible / repairable / not defensible). Meshes 3262 → 3264, **0 deleted**, 2 added. Geometry changed on 18 structures.


**Base F — attempted on 22, accepted 19, held 3**

| structure | vertices in bone, before → after | mean move mm | volume × | **vertices inside other muscles, before → after** |
|---|---|---|---|---|
| `abductor_digiti_minimi_foot_l` | **20.2 → 11.7 %** | 0.58 | 0.913 | 10.9 → 15.0 % |
| `abductor_digiti_minimi_foot_r` | **20.2 → 11.7 %** | 0.6 | 0.914 | 11.2 → 15.5 % |
| `anconeus_l` | **25.4 → 10.8 %** | 0.85 | 0.892 | 26.7 → 25.7 % |
| `anconeus_r` | **25.4 → 10.8 %** | 0.84 | 0.894 | 26.7 → 25.6 % |
| `extensor_carpi_ulnaris_l` | **22.8 → 4.4 %** | 2.57 | 1.013 | 18.1 → 35.0 % ⚠ |
| `extensor_carpi_ulnaris_r` | **22.8 → 4.4 %** | 2.58 | 1.013 | 18.3 → 36.3 % ⚠ |
| `extensor_hallucis_brevis_l` | **20.5 → 10.7 %** | 0.73 | 0.953 | 17.1 → 22.5 % ⚠ |
| `extensor_hallucis_brevis_r` | **20.5 → 10.7 %** | 0.71 | 0.958 | 16.9 → 21.7 % |
| `medial_pterygoid_l` | **22.1 → 8.8 %** | 0.24 | 0.997 | 10.4 → 11.6 % |
| `medial_pterygoid_r` | **27.7 → 16.9 %** | 1.74 | 0.897 | 10.4 → 15.3 % |
| `plantar_interossei_l` | **22.6 → 8.6 %** | 1.06 | 0.936 | 0.8 → 5.3 % |
| `plantar_interossei_r` | **22.6 → 8.5 %** | 0.94 | 0.952 | 0.6 → 3.5 % |
| `rectus_femoris_reflected_head_l` | **0.3 → 0.0 %** | 0.01 | 1.0 | 65.7 → 65.9 % |
| `stylohyoid_l` | **20.6 → 9.2 %** | 0.35 | 1.016 | 21.8 → 24.1 % |
| `stylohyoid_r` | **20.6 → 9.2 %** | 0.35 | 1.013 | 19.8 → 23.2 % |
| `zan_adductor_minimus_l` | **53.6 → 13.0 %** | 1.92 | 0.996 | 12.2 → 24.6 % ⚠ |
| `zan_adductor_minimus_r` | **53.6 → 13.2 %** | 1.97 | 0.994 | 12.6 → 26.9 % ⚠ |
| `zan_medial_head_of_triceps_brachii_l` | **23.4 → 10.2 %** | 0.62 | 0.948 | 14.6 → 28.6 % ⚠ |
| `zan_medial_head_of_triceps_brachii_r` | **23.4 → 10.2 %** | 0.62 | 0.948 | 14.5 → 28.6 % ⚠ |

| held | vertices in bone | vertices inside other muscles | the tool's own reason |
|---|---|---|---|
| `rectus_femoris_reflected_head_r` | 0.0 % | **66.8 %** | no gain |
| `zan_lateral_crico_arytenoid_muscle_l` | 7.4 % | **70.6 %** | no gain |
| `zan_lateral_crico_arytenoid_muscle_r` | 7.4 % | **69.2 %** | no gain |

Buckets on this page after both repairs: **219 / 217 / 4 → 229 / 209 / 4** (defensible / repairable / not defensible). Meshes 3298 → 3300, **0 deleted**, 2 added. Geometry changed on 21 structures.



### 3.3 What was deliberately not repaired

Three things a less careful pass would have "fixed":

1. **Z-Anatomy's own overlap between neighbouring bellies** was left alone on both pages. The only existing tool
   pushes muscles out of each other, which on the Base pages would move a third party's geometry away from the
   shape its licence and provenance vouch for, with nothing better to move it *to*. See §5.
2. **The reflected head of rectus femoris was not pushed off the ilium.** The conform reported *no gain* on all
   four attempts, for the reason §2 gives: it is not in the ilium. Had this round trusted its own first metric,
   it would have moved a structure that was already in the right place.
3. **Nothing was re-sculpted and no mesh was smoothed.** The only geometry that changed is what the two named
   repairs changed, and the split changed none at all.

---

## 4. The audit in full, per page


### Base M — 234 defensible / 192 repairable / **4 not defensible** (of 430 muscle meshes)

**Not defensible — 4**

| structure id | made how | vol cm³ | the severity-3 / severity-2 checks | architecture (evidence only) |
|---|---|---|---|---|
| `zan_lateral_crico_arytenoid_muscle_l` | Z mesh, gap-closed (Q162) | 0.03 | overlap 97.3 %; R/L volume 1.889 (band 0.8-1.25) | — |
| `zan_lateral_crico_arytenoid_muscle_r` | Z mesh, gap-closed (Q162) | 0.05 | overlap 97.2 %; R/L volume 1.889 (band 0.8-1.25) | — |
| `rectus_femoris_reflected_head_r` | **rule-based (generated here)** | 2.17 | overlap 87.7 % | — |
| `rectus_femoris_reflected_head_l` | **rule-based (generated here)** | 2.27 | overlap 88.8 % | — |

**The 12 worst repairable**

| structure id | vol cm³ | origin gap mm | insertion gap mm | R/L vol | overlap % | in bone, vertices % | pieces | the checks |
|---|---|---|---|---|---|---|---|---|
| `opponens_digiti_minimi_r` | 2.39 | 0.30 (n/a) | 0.08 | 1.227 | 44.2 | 18.8 | 2 of 1 | a piece 800.5 mm away (14.43x its own diagonal); overlap 44.2 % |
| `opponens_digiti_minimi_l` | 1.95 | 0.17 (n/a) | 0.06 | 1.227 | 49.4 | 19.1 | 2 of 1 | a piece 800.5 mm away (14.71x its own diagonal); overlap 49.4 % |
| `longus_colli_r` | 4.19 | 0.05 | 0.05 | 0.353 | 31.5 | 6.3 | 3 of 1 | R/L volume 0.353 (band 0.8-1.25); 3 pieces, its record allows 1 |
| `longus_colli_l` | 11.86 | 0.05 | 0.05 | 0.353 | 30.3 | 6.5 | 3 of 1 | R/L volume 0.353 (band 0.8-1.25); 3 pieces, its record allows 1 |
| `internal_oblique_l` | 213.17 | 0.24 (n/a) | 0.03 (n/a) | 0.664 | 61.2 | — | 1 of 2 | overlap 61.2 %; R/L volume 0.664 (band 0.8-1.25) |
| `flexor_digitorum_superficialis_r` | 21.98 | 45.89 | 75.18 (n/a) | 1.024 | 41.4 | — | 1 of 4 | origin gap 45.89 mm; overlap 41.4 % |
| `flexor_digitorum_superficialis_l` | 21.47 | 45.74 | 75.69 (n/a) | 1.024 | 41.6 | — | 1 of 4 | origin gap 45.74 mm; overlap 41.6 % |
| `zan_internal_intercostal_muscles_r` | 64.08 | — (n/a) | — (n/a) | 0.714 | 55.3 | 10.3 | 11 of 1 | overlap 55.3 % |
| `zan_internal_intercostal_muscles_l` | 89.76 | — (n/a) | — (n/a) | 0.714 | 56.1 | 10.3 | 10 of 1 | overlap 56.1 % |
| `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_r` | 0.16 | — (n/a) | — (n/a) | 1.000 | 63.2 | 15.6 | 9 of 1 | overlap 63.2 % |
| `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_l` | 0.16 | — (n/a) | — (n/a) | 1.000 | 62.1 | 15.4 | 9 of 1 | overlap 62.1 % |
| `rectus_capitis_posterior_minor_l` | 1.59 | 29.74 | 0.21 | 1.000 | 31.4 | 13.6 | 1 of 1 | origin gap 29.74 mm |

**Every muscle this project generated itself on this page**

| structure id | made how | hidden at load | vol cm³ | overlap % | in bone, vertices % | R/L vol | bucket |
|---|---|---|---|---|---|---|---|
| `medial_pterygoid_l` | mirror fill | no | 3.47 | 26.0 | 22.1 | 1.076 | **repairable** |
| `psoas_minor_l` | rule based | **yes** | 1.62 | 23.5 | 9.1 | 1.000 | **defensible** |
| `psoas_minor_r` | rule based | **yes** | 1.62 | 29.9 | 9.1 | 1.000 | **defensible** |
| `rectus_femoris_reflected_head_l` | rule based | no | 2.27 | 88.8 | 0.0 | 0.955 | **not defensible** |
| `rectus_femoris_reflected_head_r` | rule based | no | 2.17 | 87.7 | — | 0.955 | **not defensible** |
| `zan_iliopectineal_arch_l` | mirror fill | no | 0.27 | 28.2 | — | 1.000 | **defensible** |

### Base F — 219 defensible / 217 repairable / **4 not defensible** (of 440 muscle meshes)

**Not defensible — 4**

| structure id | made how | vol cm³ | the severity-3 / severity-2 checks | architecture (evidence only) |
|---|---|---|---|---|
| `zan_lateral_crico_arytenoid_muscle_l` | Z mesh, gap-closed (Q162) | 0.02 | overlap 94.9 %; R/L volume 1.87 (band 0.8-1.25) | — |
| `zan_lateral_crico_arytenoid_muscle_r` | Z mesh, gap-closed (Q162) | 0.04 | overlap 94.9 %; R/L volume 1.87 (band 0.8-1.25) | — |
| `rectus_femoris_reflected_head_r` | **rule-based (generated here)** | 1.92 | overlap 85.5 % | — |
| `rectus_femoris_reflected_head_l` | **rule-based (generated here)** | 1.97 | overlap 85.4 % | — |

**The 12 worst repairable**

| structure id | vol cm³ | origin gap mm | insertion gap mm | R/L vol | overlap % | in bone, vertices % | pieces | the checks |
|---|---|---|---|---|---|---|---|---|
| `opponens_digiti_minimi_r` | 2.17 | 0.07 (n/a) | 0.10 | 1.229 | 45.0 | 18.8 | 2 of 1 | a piece 831.9 mm away (15.56x its own diagonal); overlap 45.0 % |
| `opponens_digiti_minimi_l` | 1.77 | 0.17 (n/a) | 0.11 | 1.229 | 49.6 | 18.8 | 2 of 1 | a piece 831.9 mm away (15.84x its own diagonal); overlap 49.6 % |
| `zan_internal_intercostal_muscles_r` | 40.22 | — (n/a) | — (n/a) | 0.683 | 67.2 | 11.4 | 11 of 1 | overlap 67.2 % |
| `zan_internal_intercostal_muscles_l` | 58.92 | — (n/a) | — (n/a) | 0.683 | 66.9 | 12.4 | 10 of 1 | overlap 66.9 % |
| `longus_colli_r` | 4.53 | 0.09 | 0.09 | 0.359 | 29.8 | 6.2 | 3 of 1 | R/L volume 0.359 (band 0.8-1.25); 3 pieces, its record allows 1 |
| `longus_colli_l` | 12.60 | 0.04 | 0.04 | 0.359 | 29.5 | 6.9 | 3 of 1 | R/L volume 0.359 (band 0.8-1.25); 3 pieces, its record allows 1 |
| `flexor_digitorum_superficialis_r` | 17.80 | 43.23 | 72.60 (n/a) | 1.023 | 44.9 | — | 1 of 4 | origin gap 43.23 mm; overlap 44.9 % |
| `flexor_digitorum_superficialis_l` | 17.39 | 42.37 | 73.01 (n/a) | 1.023 | 44.3 | — | 1 of 4 | origin gap 42.37 mm; overlap 44.3 % |
| `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_r` | 0.14 | — (n/a) | — (n/a) | 0.966 | 61.6 | 15.6 | 9 of 1 | overlap 61.6 % |
| `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_l` | 0.15 | — (n/a) | — (n/a) | 0.966 | 64.0 | 15.5 | 9 of 1 | overlap 64.0 % |
| `stylohyoid_r` | 1.32 | 0.26 | 0.19 | 1.095 | 44.0 | 20.6 | 1 of 1 | overlap 44.0 %; in bone 20.63 % of its vertices, deepest 3.46 mm (2 mm voxel solid share 11.25 %) |
| `stylohyoid_l` | 1.20 | 1.03 | 0.18 | 1.095 | 43.8 | 20.6 | 1 of 1 | overlap 43.8 %; in bone 20.63 % of its vertices, deepest 4.0 mm (2 mm voxel solid share 11.88 %) |

**Every muscle this project generated itself on this page**

| structure id | made how | hidden at load | vol cm³ | overlap % | in bone, vertices % | R/L vol | bucket |
|---|---|---|---|---|---|---|---|
| `external_anal_sphincter_ct_vhf` | rule based | no | 16.79 | 24.2 | — | — | **defensible** |
| `medial_pterygoid_l` | mirror fill | no | 3.86 | 28.7 | 22.1 | 1.073 | **repairable** |
| `psoas_minor_l` | rule based | **yes** | 1.77 | 25.1 | 7.5 | 1.000 | **defensible** |
| `psoas_minor_r` | rule based | **yes** | 1.77 | 32.2 | 7.5 | 1.000 | **defensible** |
| `rectus_femoris_reflected_head_l` | rule based | no | 1.97 | 85.4 | — | 0.976 | **not defensible** |
| `rectus_femoris_reflected_head_r` | rule based | no | 1.92 | 85.5 | 0.0 | 0.976 | **not defensible** |
| `zan_iliopectineal_arch_l` | mirror fill | no | 0.23 | 27.3 | — | 1.000 | **defensible** |

---

## 5. Proposals — repairs that need a decision, geometry, or a method this project does not have

Per the boundary set for this round, none of these was carried out.

| what | the numbers | the route, and why it was not taken here |
|---|---|---|
| **The full in-bone pass at the project's own 8 % gate** | 94 muscles on Base · Male, 86 on Base · Female; the demonstration at 20 % (§3.2) shows what the tool achieves on the worst of them | The tooling exists, the gate is the project's own, and the demonstration measures the outcome. It was not run across all 180 because it moves geometry on 1 in 5 muscles of the owner's most important models, and that is his call. **And the demonstration has changed what should be proposed:** the conform reduces bone penetration by converting it into muscle overlap (§3.2), roughly doubling the overlap of several structures on pages whose bellies already share space at a median of 30 %. **Proposal: do NOT approve a blanket 8 % pass. Approve it selectively — for the structures where in-bone is large and the overlap rise is small (`plantar_interossei`, `medial_pterygoid_l`, `anconeus`), and leave the rest.** The full target list is in the repair report under `in_bone_full_pass_would_be`, and each candidate's overlap cost can be measured before it is accepted. |
| **`zan_adductor_minimus_l` / `_r`: 53.4 % of their vertices inside bone on Base · Male, 53.6 % on Base · Female — the largest corroborated in-bone finding on either page** | both measures agree, so this is not the §2 artefact | **Repaired in the demonstration** (§3.2): down to 12.8 % / 13.0 % on Base · Male and 13.0 % / 13.2 % on Base · Female, mean move ~2 mm, volume ×0.98–1.00. Its overlap rose from ~10–12 % to ~25–28 % in the process, which is the trade §3.2 documents. **Proposal: accept this pair, or accept it as the test case for whether that trade is acceptable generally.** |
| **Muscle-into-muscle overlap: 50 muscles on Base · Male and 56 on Base · Female past the 60 % gate; median 30.2 % / 32.0 %** | `fill.OVERLAP_MAX = 60`, the project's own gate, on the volume share | The Q214 separation pass needs a *target* — either a measured subject (which is what the Imaging pages are for) or a decision about which belly yields. That is a method choice, not a fix. **Proposal: treat Base overlap as the known signature of Z-Anatomy's modelling and leave it, unless the owner wants the Base pages separated for cut-plane rendering.** |
| **The rectus-capitis / obliquus-capitis group: origin gaps of 26–36 mm to `cervical_vertebrae`, which is most of the 12 severity-3 gaps per page** | e.g. `rectus_capitis_posterior_minor_l` 29.04 mm, `rectus_capitis_anterior_r` 28.57 mm on Base · Female | Their record names `cervical_vertebrae` as a group, and the Z pages ship the individual vertebrae; the real origin is the atlas (C1), whose Z mesh is named `atlas`, not `zan_vertebra_c1`. **This may be a resolution failure of this round's bone-group map rather than a geometry defect, and it should be checked before anything else is concluded about the skull base.** One hour of work; it would also sharpen the gap figures for ~100 muscles per page whose attachment bone the page carries under another name. |
| **`zan_lateral_crico_arytenoid_muscle_l` / `_r`** | see §6 — this is a give-up item, not a proposal | |
| **`longus_colli`: the two sides differ in volume by 2.83× (11.86 vs 4.19 cm³ on Base · Male; 12.60 vs 4.53 on Base · Female), and each mesh is in 3 pieces where its record allows 1** | the largest left/right disagreement on either Base page | Its own record describes three fibre groups ("superior oblique, vertical, and inferior oblique"), so **the three pieces are right and this round's expectation of one was wrong** — the entity record should carry three `functional_compartments`, which is a data edit. The volume asymmetry is real and is in the Z-Anatomy source; Q237's mirror-fill from the larger side would fix it cheaply but would overwrite one side of a third party's mesh. **Proposal: (a) record the three fibre groups; (b) decide on the mirror-fill.** |

---

## 6. The give-up list

Four structures per page, and they are the same four on both. Per the owner's instruction, these are the ones
where a repair either failed or does not apply. **Nothing has been deleted; this is the list to decide from.**

| page | structure | made how | vol cm³ | what fails, on the better measure | repair attempted? | outcome |
|---|---|---|---|---|---|---|
| Base M | `rectus_femoris_reflected_head_l` | rule based | 2.27 | overlap 88.8 % | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 77.2 % of its vertices) |
| Base M | `rectus_femoris_reflected_head_r` | rule based | 2.17 | overlap 87.7 % | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 78.5 % of its vertices) |
| Base M | `zan_lateral_crico_arytenoid_muscle_l` | z raw gap closed | 0.03 | overlap 97.3 %; R/L volume 1.889 (band 0.8-1.25) | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 69.8 % of its vertices) |
| Base M | `zan_lateral_crico_arytenoid_muscle_r` | z raw gap closed | 0.05 | overlap 97.2 %; R/L volume 1.889 (band 0.8-1.25) | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 69.7 % of its vertices) |
| Base F | `rectus_femoris_reflected_head_l` | rule based | 1.97 | overlap 85.4 % | yes, the Q213 in-bone conform | nominally accepted but a **no-op**: mean move 0.01 mm, in-bone 0.3 → 0.0 % (exact overlap 65.7 %) |
| Base F | `rectus_femoris_reflected_head_r` | rule based | 1.92 | overlap 85.5 % | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 66.8 % of its vertices) |
| Base F | `zan_lateral_crico_arytenoid_muscle_l` | z raw gap closed | 0.02 | overlap 94.9 %; R/L volume 1.87 (band 0.8-1.25) | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 70.6 % of its vertices) |
| Base F | `zan_lateral_crico_arytenoid_muscle_r` | z raw gap closed | 0.04 | overlap 94.9 %; R/L volume 1.87 (band 0.8-1.25) | yes, the Q213 in-bone conform | **held** — no gain (exact overlap 69.2 % of its vertices) |


### 6.1 Per item, why repair failed or does not apply, and what dropping it would cost

**`zan_lateral_crico_arytenoid_muscle_l` / `_r` — both Base pages.** 97.3 % / 97.2 % of its volume lies inside
other muscles on Base · Male (94.9 % on Base · Female), and the two sides differ in volume by **1.889×** (1.87×
on Base · Female) at 0.02–0.05 cm³ — on a page whose two sides are mirror copies, which means the asymmetry is
in the Z-Anatomy source itself and not in anything this project did.

* *Why repair fails.* The in-bone conform does not apply: only 7.5 % (Base M) / 7.4 % (Base F) of its vertices
  are inside bone, below the project's own 8 % gate, and the tool reported *no gain* on all four attempts.
  Q237's mirror-fill needs one clean side to copy from, and here neither side is clean. No laryngeal source
  exists in this repository: `docs/MUSCLE_GAPS.md` lists the whole larynx as beyond the available imaging, and
  Q296's Open Anatomy survey found no laryngeal atlas in any of the seven catalogued.
* *The exact overlap measurement, taken for this one too.* **69.8 % / 69.7 %** of its vertices lie inside other
  muscles on Base · Male and **70.6 % / 69.2 %** on Base · Female. The 2 mm volume share badly over-read here
  (97.3 % / 97.2 % and 94.9 %), so the structure is not quite the extreme case the first figures made it look —
  but at ~70 % it is still above the 60 % gate on the better measure.
* *What dropping it would cost.* It is named in 6 shared data files and carries no parts rows and no clinical
  references. But it is one of the two laryngeal adductors, so the larynx would lose a named muscle, and the
  structure is **real third-party anatomy in a plausible place** — the complaint against it is that it is
  ~70 % inside its neighbours at a scale of 0.02–0.05 cm³. **Recommendation: keep it and accept the overlap, or
  get a laryngeal source. Deleting a real, licensed, correctly-placed laryngeal adductor because Z-Anatomy models
  the larynx as interpenetrating slabs would lose anatomy and fix nothing.**

**`rectus_femoris_reflected_head_l` / `_r` — both Base pages, and both Combined pages too.** The only muscle this
project generated by rule that fails a gate on all four pages: 88.8 % / 87.7 % of its volume inside other
muscles on Base · Male, 85.4 % / 85.5 % on Base · Female.

* *Why repair fails.* The in-bone half of the case against it **has been disproved** (§2: 0.0 % of its vertices
  are in the ilium), and the conform reported *no gain*. What remains is the overlap, and no tool this project
  has can reduce it without a target to move the structure toward.
* *The second measurement was taken, and it confirms the finding.* §2's lesson was applied here rather than
  left as a caveat: the exact vertex-based overlap (`q213_inbone.MuscleOverlap.pct`, ray parity) was recorded for
  this structure during the repair attempt. It reads **77.2 % / 78.5 %** of its vertices inside other muscles on
  Base · Male and **65.7 % / 66.8 %** on Base · Female. The 2 mm volume share did over-read (88.8 % / 87.7 % and
  85.4 % / 85.5 %), as §2 would predict — but the exact figure is still far above the project's 60 % gate. **So
  unlike the in-bone case, this finding survives the better measurement.** The reflected head genuinely does sit
  inside its neighbours; whether that is wrong depends on a judgement about the gate, since the reflected head
  anatomically runs along the superior acetabular rim **under** the hip capsule and against rectus femoris.
* *The repair was attempted and achieved nothing.* The conform reported *no gain* on Base · Male (both sides) and
  on Base · Female's right side; Base · Female's left side was nominally "repaired" by a mean move of **0.01 mm**
  from 0.3 % to 0.0 % in-bone, which is a no-op. There is nothing to push it out of.
* *What dropping it would cost.* Cheap mechanically: 0 parts rows, 0 clinical files, and it sits in the last ~65
  indices of the page so almost nothing renumbers. Expensive in substance: **Q293 built it because the owner
  asked for it** — "rectus femoris has only the straight head, the reflected head is missing" — so deleting it
  un-does an owner request, and it is named in 6 shared data files and asserted in 2 tests.

### 6.2 What is NOT on the give-up list, and why that is the useful part

The structures that the first, uncorrected metric would have put here — `nasalis`, `zan_occipitalis_muscle`,
`levator_labii_superioris`, `procerus` — are all fine, or were repaired. Had this round reported its first
numbers, it would have handed the owner a give-up list of a dozen facial muscles that are not in fact buried in
his skull. **The give-up list is four structures per page, and two of those four still deserve one more
measurement before anyone removes them.**

---

## 7. What deleting a Base structure would cost, mechanically

Re-measured on the Base rigs. **Nothing here has been deleted.**

| | Base · Male | Base · Female |
|---|---|---|
| page meshes | 3,262 | 3,298 |
| committed pose rig `count` | **3,262** | **3,298** |
| rig matches the page | yes | yes |
| skinned rig entries | 1,765 | 1,788 |
| rigid groups / segments | 106 | 106 |

`viewer/pose/pose.js:244` — `if (rig.count !== E.count())` — sets `st.failed` and returns false, so at
`pose.js:717-718` the Pose button stays `disabled` with that message as its tooltip. **One removed mesh with a
stale rig disables Pose for the whole page**, and `pose.js:247-255` then also fails the per-structure vertex-count
check for every index after the removed one. `scripts/anatomy/q297/pages_q297.py` is the one precedent for
removing a structure and renumbering the rig, and it refuses a skinned entry outright
(`assert not any(e[0] == i for e in R["skin"]), "... SKINNED rig entry -- weight surgery needed"`).

The repair in §3.1 is deliberately the opposite shape: it **adds** structures at the end of the manifest, so no
existing index moves, no skinning weight is touched, and the new entries are rigid members of their own segment.

Neither Base page's HTML was re-emitted and nothing was published: `scripts/zanatomy/q205_pages.save_page`
renders the page from `viewer/zan_atlas.template.html`, so a republish needs the whole round pipeline (every
injected module, then `scripts/regen_template_only.py`) to equal what is live. That is the owner's decision.

---

## 8. Reproducing this

```
python3 scripts/anatomy/q319/audit_reconstructed_muscles_q319.py \
    --pages base_m,base_f,comb_m,comb_f \
    --page-dir base_m=build/q309/viewer_zan_atlas \
    --page-dir base_f=build/q309/viewer_base_female \
    --page-dir comb_m=<dir> --page-dir comb_f=<dir> --cap 250000 --merge

python3 scripts/anatomy/q319/repair_q319.py \
    --page-dir base_m=build/q309/viewer_zan_atlas \
    --page-dir base_f=build/q309/viewer_base_female --gate 20
```

Needs `numpy`, `scipy`, and now `trimesh` + `rtree` for the exact in-bone test (both already in
`requirements.txt` as optional; without them the audit still runs and caps every un-corroborated in-bone finding
at severity 1 rather than guessing). The audit is ~2–5 minutes per page, most of it the exact pass. The repair is
~15 minutes per page at `--gate 20`.

Outputs: `data/derived/Q319_reconstructed_muscle_audit.json` (one record per muscle mesh on all four pages, each
with its `bucket`, `bucket_because` and both in-bone measures) and `data/derived/Q319_repair_report.json` (what
was repaired, what was held and the tool's own reason, the before/after numbers, and the pose-rig splice).
