# Q319 — the muscles on the Combined pages: what is reconstructed, how bad it is in numbers, and what deleting one would cost

Owner's request (Q319.4.v), verbatim:

> דיברנו על המודלים המשוחזרים והמעורבים [COMBINED] בהם בוצעה עבודה גרועה מאוד והשרירים רופפים, לא עקביים ולא מתאימים או תואמים. צריך לייצר שחזורים הגיוניים, ואם לא ניתן - מעדיף כרגע למחוק ונתקן בהמשך.

— on the reconstructed and Combined models the muscle work is very poor: the muscles are **slack**, **inconsistent**, and **do not fit or match**. Defensible reconstructions are needed; where that is not possible he would rather delete them for now and repair later.

**This round is read-only. No mesh, page, build directory or data file was changed or deleted.** The two files it
produced are `data/derived/Q319_reconstructed_muscle_audit.json` and this document.

---

## 0. Where the numbers come from, and the one thing that was missing

`build/` is in `.gitignore` and **does not exist in this checkout** (`build/q309/viewer_zan_vhm`,
`build/q309/viewer_zan_female` and every other `build/...` path are absent; the container was rebuilt). So was the
Z-Anatomy geometry itself: `third_party/z-anatomy/` holds only `LICENSE`, `NOTICE` and `README.md`. **Nothing in
git carries a per-page muscle mesh, and nothing in git carries the per-page structure list either.** That matters
on its own, and the owner should know it before approving any deletion: the list of what each page contains exists
only inside the built/published page.

Rather than substitute a weaker metric, the geometry was taken from the place where it does still exist in full —
**the live published pages**, read read-only through the artifact service and decoded off disk:

| page | artifact | version read | `index.html` sha256 | muscle meshes / meshes |
|---|---|---|---|---|
| Combined · Male | `https://claude.ai/artifact/FeFFPVVTEnPkDm2r7TyDFz` | `1794346874-3a8a` | `a5f148a5…311807` | **430 / 3,262** |
| Combined · Female | `https://claude.ai/artifact/1GEpFSCZexGZ1GnM1pXxuP` | `1794346898-c3a5` | `f951a215…4a2b08` | **441 / 3,310** |

Two independent checks say these are the pages the project believes it shipped, not something stale:

* the **committed** pose rigs `data/anatomy/pose_rig_comb_m.json` / `pose_rig_comb_f.json` declare
  `count` = **3,262** and **3,310** — exactly the mesh counts decoded from the two live pages. The rig and the
  live page are in sync, so the rig can be reasoned about here without a build directory.
* `data/derived/Q297_provenance_audit.json` (regenerated against `build/q308`) records 3,262 and 3,310 meshes for
  the same two pages.

Geometry was decoded with the project's own format reader (`scripts/zanatomy/q202_pages.py`: manifest in the HTML
plus a base64 uint16 blob split across `*_geo_0N.txt`). Volume uses
`scripts/anatomy/q297/volumes297.enclosed_cm3` verbatim; the voxel solid and the muscle–muscle overlap use
`scripts/anatomy/q237/fill._vox` / `lattice_solid` / `_paste` / `overlap_pct` verbatim in method (2 mm lattice,
"as the Q204 audit"); the provenance class per structure is `scripts/anatomy/q297/audit297.classify`, imported, not
re-derived. Script: **`scripts/anatomy/q319/audit_reconstructed_muscles_q319.py`**, which takes `--src build/q309`
when a build directory exists and `--page-dir KEY=PATH` otherwise.

### What could not be computed, and why

* **Nothing was compared against a previous build.** Q198's recorded per-structure defect list for these two pages
  (`data/derived/Q198_anatomy_audit.json`, models `z_male_fit` / `z_female_fit`: 2,966 structures, 417 defects,
  70 major, verdict `continuous_and_in_place = "no"`) is from the Q197 build. It is used below only for its
  **thresholds**, never for its values.
* **Outside-skin containment was not measured.** Q297 ran that test and *discarded* it, with the reason recorded:
  Z skin is ~250 open patches with no closed envelope, so containment on it is invalid. Repeating it would have
  produced a number that looks like evidence and is not.
* **No render was inspected.** Chromium was not run; every statement below is a measurement on the mesh.

---

## 1. Inventory — what on the Combined pages is reconstructed rather than measured

### 1.1 The answer the owner's phrasing needs first

**Almost no muscle on either Combined page was ever measured on that body, and almost none of it was invented
here either.** Per `scripts/anatomy/q297/audit297.classify`, run on the live manifests:

| | Combined · Male | Combined · Female |
|---|---|---|
| muscle meshes | 430 | 441 |
| `z_fitted` — a Z-Anatomy / BodyParts3D mesh (a **real** third person's anatomy) fitted onto this body's own skeleton | **423** | **420** |
| `other_person_registered` — Chinese Visible Human female, Wu et al. 2015, registered on | 0 | 9 |
| `third_party_import` — Open Anatomy / SPL inner-ear import (Q296) | 2 | 2 |
| `z_split` — a Z mesh separated into two named structures (Q213) | 0 | 2 |
| `mirror_fill` — **generated here**: the opposite side mirrored and refitted (Q237) | **1** | **4** |
| `rule_based` — **generated here**: built from a documented rule | **4** | **4** |
| measured on this body (`a_measured`) | **0** | **0** |

The Q297 three-class totals for the whole page agree: Combined M 3,262 meshes = 48 measured / 2,979 third-party /
235 rule-based; Combined F 3,310 = 51 / 3,022 / 237. **None of those 48 / 51 measured structures is a muscle** —
they are her CT breasts, her cryosection uterus, skin and the like.

So the honest description of the muscle layer on both Combined pages is: *Z-Anatomy's muscles, which are a real
cadaveric-derived model of a different (male-derived) body, carried onto this subject's own bones by a per-bone
similarity fit.* `docs/GEOMETRY_SOURCES.md:1737` states exactly that. The badge on every one of those 423 / 420
cards states it too, with a recorded error band.

### 1.2 The error band the project already records for that fit, read off the cards

| region | Combined · Male, n / median / worst max | Combined · Female, n / median / worst max |
|---|---|---|
| upper limb | 75 · 5.8–9.4 mm · 29.6 mm | 57 · 6.3–11.7 mm · 27.7 mm |
| head | 44 · 6.6 mm · 28.8 mm | 42 · 3.8 mm · 26.6 mm |
| neck | 32 · 6.6–8.7 mm · 29.6 mm | 12 · 3.8–10.6 mm · 27.7 mm |
| trunk | 30 · 6.6–8.7 mm · 29.6 mm | 35 · 3.8–10.6 mm · 27.7 mm |
| lower limb | 32 · 1.0–8.7 mm · 29.6 mm | 85 · 1.6–10.6 mm · 27.7 mm |

That is a surface error of roughly **0.6–1.2 cm typical and up to 3 cm worst** on a muscle layer. It is the
project's own figure, printed on the page. The owner is not describing an impression; he is describing this number.

### 1.3 The muscles this project generated itself — the whole list, both pages

These are the only muscles on either Combined page that are "reconstructions" in the strict sense.

**Combined · Male (5)** — `rectus_femoris_reflected_head_l`, `rectus_femoris_reflected_head_r` (rule-based,
Q293), `psoas_minor_l`, `psoas_minor_r` (rule-based, Q308, both hidden at load, badge "NOT DEMONSTRATED ON THIS
BODY"), `zan_ventral_parts_of_lateral_intertransversarii_lumborum_muscles_l` (mirror fill, Q237).

**Combined · Female (8)** — the same four rule-based ones, plus four mirror fills (Q237): `soleus_l`,
`obturator_internus_l`, `gemellus_superior_l`, `zan_lumbrical_muscles_of_foot_r`.

Their measurements and buckets are in §4.3. Everything else in `data/derived/Q297_rule_based_volumes.json` for
these two pages — 235 and 237 rule-based structures — is a **nerve, ligament, fascia, tendon or disc**, not a
muscle. Cross-checked against all 433 muscle entity ids in `data/muscles/**/*.json`: **zero** of those rule-based
entries is a muscle entity.

---

## 2. The metrics, and why each one measures one of the owner's three words

Each metric is one line. Each threshold is **the project's own**, cited; none was invented for this round.

| the owner's word | metric | what it is | threshold, and where it comes from |
|---|---|---|---|
| **slack** (רופפים) | `vol_ratio_lit` | shipped volume ÷ the volume the muscle's *own cited architecture record* implies, `V = Σ PCSA · Lf / cos(pennation)` over its `functional_compartments` | **no project threshold exists.** Reported raw; this round reads <0.5 and >2 as worth looking at, and says so as an assumption |
| **slack** | `acsa_ratio_lit` | (volume ÷ belly length along the mesh's own first principal axis) ÷ `Σ PCSA · cos(pennation)` — catches a long thin strap whose total volume still looks plausible | same: no project threshold, reported raw |
| **inconsistent** (לא עקביים) | `lr_vol_ratio_r_over_l` | right-side volume ÷ left-side volume of the same muscle on the same body | **0.80–1.25**, `data/derived/Q241_pose_asymmetry.md` §2, "the Q237 flags" |
| **inconsistent** | pieces vs the record | connected components of the mesh, against the number its record entitles it to (one per named functional compartment, +1 for a midline muscle Z ships as two mirror halves), plus the spread of the pieces' centroids ÷ the largest piece's own diagonal | more pieces than the record allows is unexplained; a piece more than **2×** the largest piece's diagonal away is in the wrong part of the body. `largest_component_frac` is reported for continuity with `docs/MUSCLE_GAPS.md` (the ECRL ship, "94.6 % in one component") but is no longer flagged alone, because a two-headed muscle legitimately sits near 0.5 |
| **inconsistent** | `open_edge_frac`, `degenerate_tri_frac`, `mean_dihedral_deg` | boundary edges, zero-area triangles, mean angle between adjacent face normals — the "hand-pulled blob vs scan" signature | dihedral reference band **27.6–31.7°**, the CVH references quoted in `docs/GEOMETRY_SOURCES.md` |
| **not matching** (לא מתאימים / תואמים) | `origin_gap_mm`, `insertion_gap_mm` | surface-to-surface distance from the muscle to the **origin** and **insertion** bone its own entity record names, measured on **this page's own bones** | **6 / 10 / 20 mm** = severity 1 / 2 / 3, `data/derived/Q198_anatomy_audit.json` `meta.thresholds.attachment_distance_mm` |
| **not matching** | `in_bone_pct`, `bone_deepest_mm` | share of the muscle's own 2 mm solid lying inside any bone's solid, and how deep | **8 / 20 / 40 %** with >3 mm depth (Q198 `inside_bone_pct_with_>3mm_depth`; `scripts/anatomy/q237/fill.BELLY_IN_BONE_MAX = 8`) and **5 mm** depth (`fill.BONE_DEPTH_MAX_MM`, "Q204 counts > 5 mm as a defect") |
| **not matching** | `overlap_muscle_pct` | share of the muscle's own volume lying inside **other** muscles, 2 mm lattice | **40 %** = Q198 `muscle_overlap_pct` severity 1; **60 %** = `scripts/anatomy/q237/fill.OVERLAP_MAX`, the hard gate at which Q237 *holds* a candidate rather than shipping it |

### 2.1 The qualifiers that keep these from inventing defects

Four of these can read as a defect when the record itself says otherwise. Each is still **measured** and reported;
it is only the *flag* that is withheld, with the reason stored per structure in the JSON.

1. **An attachment made by tendon, aponeurosis, fascia, skin, ligament, cartilage or retinaculum** is not a defect
   when the belly does not touch the bone. Example: `flexor_digitorum_superficialis_r` sits **74.1 mm** from
   `phalanges_hand_r`, and its record says the insertion is "middle phalanges … (splits to allow FDP tendon to
   pass through)". Not flagged. Its **origin** gap of 31.97 mm to the medial epicondyle of `humerus_r` **is**
   flagged, because its record names bone. Likewise `external_anal_sphincter`'s 47.1 mm "origin gap" is suppressed:
   its own record says "anococcygeal ligament and the tip of the coccyx", and that the hip bone "is named only
   because the schema takes one bone".
2. **A serially repeating or grouped mesh** (levatores costarum, interspinales, intertransversarii, multifidus,
   the intercostals, the lumbricals and interossei, the digital fibrous sheaths — 54 meshes per page) is *meant*
   to be in many pieces spread along the body, and its architecture record is measured on **one unit** while the
   mesh is the whole group. Neither the piece count, the piece spread, nor the literature ratio is applied to it.
3. **A voxel estimate on a structure whose 2 mm solid is under 200 voxels is coarse** and is not flagged
   (38 meshes on Combined M, 42 on Combined F). This is why `oa_stapedius_l/r`, which measures 100 % inside bone
   — correctly, it lives inside the petrous temporal bone — raises nothing.
4. **The architecture ratios are an assumption, not a measurement.** `V = PCSA · Lf / cos θ` is the standard PCSA
   definition applied to the muscle's own cited record (Ward et al. 2009 and the sources each record names). It is
   a literature-architecture *implication*, never a measured cadaver volume, and the JSON says so in
   `literature_volume_note`. `acsa_ratio_lit` additionally under-reads for a long tapering muscle, because a
   uniform-CSA proxy cannot represent a taper — `soleus_l` on Combined F reads 0.257 while its volume is fine.
   **No structure is bucketed on an architecture ratio alone.**

### 2.2 One validation, so the attachment metric is not taken on trust

`soleus_r` → `tibia_r` on Combined M measures **0.17 mm**: a muscle that does touch its bone reads ~0. The large
gaps below are therefore real separations, not a systematic offset. The two headline gaps were re-measured
independently of the audit script, with the bone's own extent printed beside them:

* `rectus_abdominis_r` → `hip_bone_r`: nearest point **65.49 mm** (audit: 66.24 mm from a different sample draw).
  The muscle's inferior end is at y = 36.4; the hip bone reaches down to y = −64.7. The muscle stops ~6.5 cm above
  the pubic crest it originates from.
* `sternocleidomastoid_r`: **22.85 mm** from the sternum (top of sternum y = 528.0, muscle's lower end y = 538.9)
  and **17.42 mm** from `temporal_r`. Detached at both ends.

---

## 3. The headline numbers, page by page

| | Combined · Male (430 muscles) | Combined · Female (441) |
|---|---|---|
| muscle–muscle overlap, median / p90 / max | **29.8 % / 67.6 % / 97.1 %** | **34.7 % / 68.7 % / 95.5 %** |
| over the Q237 hard gate of 60 % | **61** | **71** |
| inside bone, median / p90 / max (non-coarse) | 7.05 % / 30.1 % / 72.7 % | 8.04 % / 27.9 % / 80.8 % |
| deeper than the 5 mm Q237 gate | **168** | **148** |
| R/L volume ratio outside 0.80–1.25 | **100 of 426** with a twin | **122 of 430** |
| volume > 2× its own architecture record | 128 of 292 | 93 of 292 |
| volume < 0.5× | 30 of 292 | 43 of 292 |
| cross-section < 0.5× | 107 of 292 | 132 of 292 |
| mean dihedral, median (CVH band 27.6–31.7°) | 33.4° | 31.6° |
| meshes with any boundary edge | 19 | 21 |

Two readings follow, and they point in opposite directions, which is the useful part:

* **The surfaces themselves are not hand-pulled blobs.** Median dihedral 31.6–33.4° sits in or just above the
  project's own CVH reference band; boundary edges on 19–21 meshes of 430–441; degenerate triangles essentially
  absent. These *are* real meshes of real anatomy, as their licence and provenance say.
* **Where they sit is wrong, often.** More than half of every muscle's neighbourhood relationships fail: overlap
  past 60 % on 61–71 muscles, past the 5 mm bone-depth gate on 148–168, and a quarter of all twinned muscles
  disagree left-to-right past the band the project itself flags.

### 3.1 The defect is concentrated, and the project already said where

| region | Combined M: muscles / not-defensible-or-repairable / severity-3 hits | Combined F |
|---|---|---|
| **upper limb** | 94 / 60 (**64 %**) / 33 | 96 / 66 (**69 %**) / 35 |
| **head** | 72 / 51 (**71 %**) / 21 | 72 / 55 (**76 %**) / 26 |
| neck | 44 / 28 (64 %) / 15 | 44 / 23 (52 %) / 15 |
| trunk | 67 / 45 (67 %) / 14 | 76 / 52 (68 %) / 14 |
| **lower limb** | 100 / 40 (**40 %**) / 10 | 100 / 31 (**31 %**) / 10 |

The lower limb is twice as good as the upper limb on both pages. That is exactly the caveat Q195 recorded for its
own fit when it shipped — "forearm/hand not refined" — and the caveat Q198 attached to its own defects as the cause
`held_unrefined`: "carried rigidly by a coarse transform, forearm/hand not refined". **This is a known, recorded,
never-closed limitation that the owner is now seeing on screen.**

---

## 4. The three buckets

Bucketing uses **geometric** severities only — the ones with a project threshold. The architecture ratios are
reported as supporting evidence and never decide a bucket.

* **defensible** — no geometric check above severity 1.
* **repairable** — one or more severity-2/3 geometric checks, but not two severity-3 ones, and an existing route in
  this repository can fix it (§4.2).
* **not defensible** — two or more independent severity-3 geometric checks; **or** the mesh was generated here
  (rule-based / mirror fill) and fails even one severity-3 check, because then there is no real source behind it to
  fall back on.

| | defensible | repairable | **not defensible** |
|---|---|---|---|
| **Combined · Male** (430) | **176** | **242** | **12** |
| **Combined · Female** (441) | **182** | **251** | **8** |

Per-muscle numbers for all 871 muscle meshes are in `data/derived/Q319_reconstructed_muscle_audit.json`.

### 4.1 Not defensible — the deletion candidates


**Combined · Male — 12 not defensible**

| structure id | made how | vol cm³ | the numbers that put it here | architecture (evidence only) |
|---|---|---|---|---|
| `opponens_digiti_minimi_r` | z_fitted | 1.50 | overlap 63.5 %; in bone 54.07 % / 6.32 mm; a piece 1013.5 mm away (18.83x its diagonal) | cross-section 0.035x architecture |
| `pronator_quadratus_r` | z_fitted | 5.33 | overlap 74.0 %; in bone 25.32 % / 6.63 mm; R/L volume 0.414 | volume 2.371x architecture |
| `opponens_digiti_minimi_l` | z_fitted | 1.61 | overlap 53.3 %; in bone 44.67 % / 6.32 mm; a piece 1005.2 mm away (18.37x its diagonal) | cross-section 0.039x architecture |
| `flexor_pollicis_longus_r` | z_fitted | 4.85 | overlap 60.7 %; in bone 38.48 % / 7.21 mm; R/L volume 0.336 | cross-section 0.116x architecture |
| `flexor_digitorum_superficialis_r` | z_fitted | 12.91 | origin gap 31.97 mm; overlap 81.7 %; R/L volume 0.608 | — |
| `abductor_pollicis_brevis_l` | z_fitted | 1.43 | insertion gap 24.26 mm; in bone 58.97 % / 8.94 mm | cross-section 0.411x architecture |
| `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_l` | z_fitted | 0.14 | in bone 68.46 % / 6.0 mm; R/L volume 0.345 | — |
| `rectus_femoris_reflected_head_l` | rule_based | 1.84 | overlap 73.8 %; in bone 40.33 % / 4.0 mm | — |
| `procerus` | z_fitted | 0.77 | overlap 72.7 %; in bone 59.48 % / 3.46 mm | volume 3.832x architecture |
| `flexor_pollicis_longus_l` | z_fitted | 14.45 | in bone 53.23 % / 7.21 mm; R/L volume 0.336 | cross-section 0.352x architecture |
| `flexor_digiti_minimi_brevis_hand_l` | z_fitted | 0.80 | overlap 76.2 %; in bone 65.93 % / 6.93 mm | — |
| `rectus_femoris_reflected_head_r` | rule_based | 1.57 | overlap 64.4 %; in bone 38.93 % / 3.46 mm | — |

**Combined · Female — 8 not defensible**

| structure id | made how | vol cm³ | the numbers that put it here | architecture (evidence only) |
|---|---|---|---|---|
| `flexor_carpi_ulnaris_r` | z_fitted | 49.90 | overlap 64.7 %; in bone 27.98 % / 8.25 mm; R/L volume 1.769; 2 pieces, record allows 1 | volume 2.958x architecture |
| `rectus_femoris_reflected_head_l` | rule_based | 1.47 | overlap 79.5 %; in bone 46.48 % / 4.47 mm; R/L volume 2.045 | — |
| `supinator_l` | z_fitted | 6.49 | overlap 69.7 %; in bone 26.74 % / 7.21 mm; R/L volume 1.717 | cross-section 0.223x architecture |
| `rectus_femoris_reflected_head_r` | rule_based | 3.02 | overlap 79.4 %; in bone 25.71 % / 4.0 mm; R/L volume 2.045 | — |
| `opponens_digiti_minimi_r` | z_fitted | 1.69 | overlap 75.5 %; in bone 40.99 % / 6.0 mm | — |
| `flexor_digitorum_superficialis_r` | z_fitted | 13.29 | origin gap 32.14 mm; overlap 68.7 % | — |
| `extensor_indicis_l` | z_fitted | 1.96 | overlap 61.7 %; in bone 47.46 % / 6.0 mm | cross-section 0.301x architecture |
| `procerus` | z_fitted | 0.72 | overlap 79.9 %; in bone 58.52 % / 4.0 mm | volume 3.578x architecture |

#### The four worst, in words

1. **`opponens_digiti_minimi_r` / `_l` on Combined · Male — the mesh contains a piece of the foot.** The mesh
   decomposes into two connected components whose centroids are **1,013.5 mm** and **1,005.2 mm** apart
   (**18.8×** and **18.4×** the larger piece's own diagonal). Measured per component on `_r`: one piece of
   1,230 mm² at centre (112.8, 47.1, 126.5) — the right hand, beside the hip in this A-pose — and one of 770 mm²
   at centre (199.2, **−954.0**, −5.9), i.e. at the right foot. On top of that: 63.5 % of its volume inside other
   muscles, 54.1 % inside bone at 6.3 mm, and an equivalent cross-section 0.035× its own architecture record.
   **This is not an opinion about shape: a hand muscle on this page is partly in the foot.**
   The fix already exists and was already applied to the *other* page: Q213 separated this exact Z mesh, and
   Combined · Female carries `opponens_digiti_minimi_foot_l` and `_r` as their own structures. Combined · Male
   never received that split. *So this is a one-page regression with a known, shipped remedy — and it is the single
   strongest argument for repairing rather than deleting.*
2. **`rectus_femoris_reflected_head_l` / `_r` — on both pages, the only muscle this project built from a rule, and
   it fails that rule's own gate.** Combined M: **73.8 %** / **64.4 %** of its volume inside other muscles against
   `fill.OVERLAP_MAX = 60`, and **40.3 %** / **38.9 %** inside bone at 4.0 / 3.5 mm against the 8 % / 5 mm gate.
   Combined F: **79.5 %** / **79.4 %** overlap, **46.5 %** / **25.7 %** in bone, and the two sides differ in
   volume by **2.045×** (1.47 vs 3.02 cm³) — the same structure, twice on one body, one twice the size of the
   other. Q237 would have *held* a candidate with these numbers instead of shipping it.
3. **`flexor_pollicis_longus` — the owner's own worked example.** Q282 records his request verbatim: "5 mm-spaced
   axial cross-sections of the right hand, abbreviated labels, highlighting FPL … including its motor point", and
   that sentence is still in `viewer/zan_atlas.template.html:13824`. On Combined M, FPL's two sides differ in
   volume by **2.98×** (left 14.45 cm³, right 4.85 cm³ — one thumb's long flexor three times the other's),
   **38.5 %** / **53.2 %** of each lies inside bone at 7.2 mm, and the right one is **60.7 %** inside other
   muscles. On Combined F the same pair reads R/L **2.111** with 35.2 % / 29.2 % in bone. The structure he picked
   to demonstrate the atlas is one of its worst.
4. **`rectus_abdominis` and `sternocleidomastoid` on Combined · Male — muscles detached from their own bones.**
   Rectus abdominis's nearest point to the hip bone it originates from is **66.24 mm** (right) and **58.23 mm**
   (left), against Q198's severity-3 line of 20 mm — independently re-measured at 65.49 / 57.27 mm, with the
   muscle's inferior end at y = 36.4 while the hip bone reaches y = −64.7. Sternocleidomastoid is **22.87 mm**
   from the sternum and **17.51 mm** from the temporal bone — detached at both ends — and carries 0.419× the
   volume and 0.257× the cross-section its own architecture record implies. These two land in *repairable*, not
   *not-defensible*, because each fails one severity-3 check rather than two; they are named here because they are
   the most visible thing on the page and the most likely source of the word "slack".

**One more, worth the owner's attention because of what it implies about the whole pelvic floor:** `levator_ani`
ships at **1.72 / 2.44 cm³** on Combined M and **0.94 / 0.73 cm³** on Combined F, against **57.5 cm³** implied by
its own cited architecture record — a ratio of **0.013–0.042**. Z-Anatomy draws levator ani as a thin membrane,
not as the muscle sling it is, and its insertion end sits 22.4–45.1 mm from the coccyx. It passes the geometric
gates (it overlaps nothing, it is not in bone) and so sits in *repairable*, but no re-fit will make a membrane
into a muscle. It needs a different source, and `docs/MUSCLE_GAPS.md` already names one (the Chinese Visible
Human pelvic-floor set that Combined · Female carries for the perineum).

### 4.2 Repairable — 242 on Combined · Male, 251 on Combined · Female, and the five routes

Each failing check has exactly one existing route in this repository. None needs new science; all need
`build/` back, because they are rebuild operations.

| what fails | the fix | the machinery that already exists | effort |
|---|---|---|---|
| **R/L volume outside 0.80–1.25**, one side clean (100 on M, 122 on F; of these the extreme band, ratio <0.6 or >1.67: the ones listed in §4.1) | mirror the good side about the page's midsagittal plane and refit it to this side's own bones | `scripts/anatomy/q237/run_fill.py` + `fill.py` — written for exactly this, with the guards already set at the thresholds used here. Q237 shipped 7 and 9 such fills on these two pages and **held 8 on each** | per muscle: minutes of compute, one build + one republish per page. The expensive part is the page rebuild, which is per page, not per muscle |
| **attachment gap >10 mm** (20 origin + 20 insertion on M, 14 + 12 on F) | re-register the structure bone-driven and snap its origin/insertion to the bone footprint | the fix Q198 itself prescribes for cause `registration_mismatch`: "re-register the structure bone-driven (per-bone similarity + non-rigid refinement, Q194 method) and snap origins/insertions to the bone footprints". The attachment sites exist as data: `data/anatomy/structure_parts.json` carries 122 `origin_part` and 231 `insertion_point` rows with `maps_to.part_ids` for `zan_m` / `zan_f` | this is the big one: a forearm/hand chain refit is the work Q195 deferred and never did. Days, not hours, and it is the same job for ~60 upper-limb muscles at once |
| **inside bone >8 % or deeper than 5 mm** (168 on M, 148 on F) | the bounded conform step that pushes vertices out of bone and keeps them inside the skin | `scripts/anatomy/q237/fill.py` conform + guards (`BELLY_IN_BONE_MAX`, `BONE_DEPTH_MAX_MM`, `CONFORM_MAX_MM = 6`); Q248/Q249 ran the same step on their own additions and recorded `pushed_out_of_bone` per structure | cheap per muscle, and it is a post-process: it can run over all of them in one pass |
| **overlap with other muscles >40 / 60 %** (96 / 61 on M, 109 / 71 on F) | the Q214 separation pass, which is what `fill.OVERLAP_MAX` gates against | same module | cheap, but it must run *after* the re-registration, or it will push muscles out of each other into the wrong places |
| **more pieces than the record allows** (e.g. `flexor_digitorum_profundus_r` 4 pieces where the record names 2; `pronator_teres` 2 where it names 1) | either accept the extra piece by recording it in the entity's `functional_compartments`, or split it into its own named structure | Q213's split is the precedent; `data/anatomy/muscle_heads_q293.json` is where a head gets recorded | per muscle, and it is a data edit plus a card, not geometry |

### 4.3 The muscles generated here, with their buckets

| page | structure id | made how | hidden at load | vol cm³ | overlap % | in bone % / mm | R/L vol | vol ÷ architecture | bucket |
|---|---|---|---|---|---|---|---|---|---|
| Combined · Male | `psoas_minor_l` | rule based | **yes** | 1.73 | 5.3 | 30.4 / 6.0 | 0.998 | n/a | **repairable** |
| Combined · Male | `psoas_minor_r` | rule based | **yes** | 1.73 | 25.4 | 22.5 / 6.3 | 0.998 | n/a | **repairable** |
| Combined · Male | `rectus_femoris_reflected_head_l` | rule based | no | 1.84 | 73.8 | 40.3 / 4.0 | 0.850 | n/a | **not defensible** |
| Combined · Male | `rectus_femoris_reflected_head_r` | rule based | no | 1.57 | 64.4 | 38.9 / 3.5 | 0.850 | n/a | **not defensible** |
| Combined · Male | `zan_ventral_parts_of_lateral_intertransversarii_lumborum_muscles_l` | mirror fill | no | 4.17 | 24.8 | 6.2 / 2.8 | 1.022 | n/a | **defensible** |
| Combined · Female | `gemellus_superior_l` | mirror fill | no | 8.76 | 28.7 | 6.6 / 3.5 | 1.042 | 7.005 | **defensible** |
| Combined · Female | `obturator_internus_l` | mirror fill | no | 18.83 | 13.9 | 9.6 / 3.5 | 1.271 | 1.374 | **defensible** |
| Combined · Female | `psoas_minor_l` | rule based | **yes** | 1.77 | 7.6 | 31.0 / 6.3 | 1.001 | n/a | **repairable** |
| Combined · Female | `psoas_minor_r` | rule based | **yes** | 1.77 | 24.3 | 19.3 / 6.0 | 1.001 | n/a | **defensible** |
| Combined · Female | `rectus_femoris_reflected_head_l` | rule based | no | 1.47 | 79.5 | 46.5 / 4.5 | 2.045 | n/a | **not defensible** |
| Combined · Female | `rectus_femoris_reflected_head_r` | rule based | no | 3.02 | 79.4 | 25.7 / 4.0 | 2.045 | n/a | **not defensible** |
| Combined · Female | `soleus_l` | mirror fill | no | 318.05 | 19.7 | 0.6 / 2.8 | 1.045 | 1.615 | **defensible** |
| Combined · Female | `zan_lumbrical_muscles_of_foot_r` | mirror fill | no | 1.44 | 59.0 | 6.3 / 2.8 | 1.383 | n/a | **repairable** |

---

## 5. What deleting one of these would actually mean

### 5.1 The blocker that comes first

**A deletion cannot be performed in this checkout at all.** The mesh exists in exactly one place — inside the
built page — and `build/` is gone. Removing a structure means re-emitting the page's
`window.__ANATOMY_MANIFEST__` and its slice of the uint16 blob, which is what
`scripts/zanatomy/q205_pages.save_page` does and what `scripts/anatomy/q297/pages_q297.py` did for the one mesh
Q297 removed. That needs the baseline build directory (or, failing that, the downloaded published page files as a
substitute source, which has never been done and is not sanctioned by any existing script). **So the first thing
the owner's approval buys is a baseline rebuild, not a deletion.** Everything in §5.2–5.6 describes the cost once
that exists.

### 5.2 Which files change

| | what changes |
|---|---|
| the page | `build/<baseline>/viewer_zan_vhm/atlas_viewer_zan_male_fitted.html` + `atlas_viewer_zan_male_fitted_geo_0{0..3}.txt` (and `viewer_zan_female/atlas_viewer_zan_female*` for the female page). Published as `index.html` + the four `*_geo_0N.txt` siblings, so **the geo blobs re-pack and every published sibling after the removed mesh changes bytes** — Q297 saw exactly this and had to declare `geo_02.txt` / `geo_03.txt` as expected diffs |
| the rig | `data/anatomy/pose_rig_comb_m.json` / `pose_rig_comb_f.json` — see §5.5 |
| the per-page sidecars | `parts_data.json` (keyed by structure id), and `plexus_groups.json`, `symmetry_q237.json`, `clinical_motor_points.json`, `clinical_risk.json` must each be checked for the id, as Q297 did (it found 0 occurrences for its structure; for a muscle it will not be 0) |
| the shared data | `data/anatomy/search_reference_q306.json`, `abbreviations.json`, `synonyms_q306.json`, `muscle_groups_q306.json`, `concepts_q306.json`, `moment_arms_comb_{m,f}.json`, `muscle_actions_q283.json`, `muscle_heads_q293.json`, `structure_parts.json` — all keyed by muscle id and **shared across all six pages**, so none of them can simply have the id removed |
| the tests | `tests/test_q287.py`, `test_q288.py`, `test_q293.py`, `test_q296.py`, `test_q297.py` all assert per-page mesh and rig counts. Q297's single removal moved five of them |
| the hub | `viewer/atlas_hub.html` prints a structure count chip per page |
| **not** deleted | nothing in `data/` holds the mesh, so **no source geometry is lost** — and nothing can be recovered from `data/` either, because Z-Anatomy's meshes are not in this repository. The structure comes back only by rebuilding from the Z-Anatomy source the owner holds outside git |

### 5.3 What the viewer shows in its place

**Nothing.** There is no placeholder mechanism. The structure disappears from the mesh list; it is not hidden and
not faded; the neighbours simply show through. Q297's own wording for its removal was "region shown open", and the
precedent it set was to put a note on the **neighbouring** structures' cards explaining why the region is empty —
which is the only honest substitute and should be part of any deletion here.

### 5.4 Search, labels and the parts table

* **Search breaks in a way the owner has already complained about twice.** Q298 and Q311 were both rounds about
  search completeness, and Q311's request was verbatim: "כל האיברים צריכים להופיע בתוצאות חיפוש" — every structure
  must appear in search results. The Q306 search layer reads the page's own structure list, so a deleted muscle
  stops appearing; but the shared tables above still name it (6–14 files per muscle, see §5.6), so the search
  *reference* and the *abbreviations* keep an entry for a structure the page no longer has. Unless those are
  filtered per page, deleting a muscle produces exactly the failure mode Q311 existed to fix.
* **Labels** come from the manifest `name`, so they go with the mesh. Nothing else needed.
* **The parts table** is keyed by structure id, and the rows are already built:
  `data/anatomy/structure_parts.json` carries 743 parts over 226 structures, including 122 `origin_part` and 231
  `insertion_point` rows with `maps_to.structure_ids.zan_m` / `zan_f` and `maps_to.part_ids` pointing at these two
  pages. `parts_data.json` on the live Combined · Male page mentions `flexor_digitorum_superficialis` **12** times,
  `supinator` **28**, `opponens_digiti_minimi` **5**, `pronator_quadratus` **11**. Deleting one of those leaves
  those rows pointing at a structure that is not there. `rectus_femoris_reflected_head` and `psoas_minor` have
  **0** parts rows on either page, so they are the clean cases.

### 5.5 The pose rig — and the exact reason it is the hard part

`viewer/pose/pose.js:244`:

```js
if (rig.count !== E.count()){ st.failed = "The pose rig was made for " + rig.count + " structures, this page has " + E.count() + ". Pose is off."; return false; }
```

`setup()` returns false, so at `pose.js:717-718` the Pose button is left `disabled` with that string as its
tooltip. **One deleted mesh with a stale rig disables Pose entirely on that page** — not the muscle's joint, the
whole module. And fixing `count` alone is not enough: `pose.js:247-255` also checks
`E.nverts(si) !== rig.nv[si]` for every rigid and skinned entry, so every index after the deleted one shifts and
the per-structure check fails en masse ("The pose rig does not match this page's geometry (N structures differ).
Pose is off."). Measured on the committed rigs, which match the live pages exactly (3,262 and 3,310):

| | Combined · Male | Combined · Female |
|---|---|---|
| rig `count` | 3,262 | 3,310 |
| skinned entries | 1,786 | 1,785 |
| rigid groups | 106 | 106 |
| **muscle indices that are skinned** | **340 of 430** | **339 of 441** |
| muscle indices that are rigid | 90 | 102 |

The precedent, `scripts/anatomy/q297/pages_q297.py` `rig()`, drops the index and renumbers the later ones — but it
refuses a skinned one outright:

```python
assert not any(e[0] == i for e in R["skin"]), f"{key}: index {i} is a SKINNED rig entry -- weight surgery needed"
```

Q297's removed structure was rigid. **Eighteen of the twenty deletion candidates here are skinned.** Per
candidate, with the number of later indices that would have to be renumbered and the other references that would
be left dangling:

| page | structure id | rig index | rig entry | later indices to renumber | parts_data rows | shared data files naming it | clinical files | tests |
|---|---|---|---|---|---|---|---|---|
| Combined · Male | `abductor_pollicis_brevis_l` | 9 | **skinned** | 3252 | 5 | 9 | 2 | 2 |
| Combined · Male | `flexor_digiti_minimi_brevis_hand_l` | 186 | **skinned** | 3075 | 8 | 11 | 2 | 2 |
| Combined · Male | `flexor_digitorum_superficialis_r` | 195 | **skinned** | 3066 | 12 | 10 | 2 | 3 |
| Combined · Male | `flexor_pollicis_longus_l` | 202 | **skinned** | 3059 | 5 | 11 | 2 | 3 |
| Combined · Male | `flexor_pollicis_longus_r` | 203 | **skinned** | 3058 | 5 | 11 | 2 | 3 |
| Combined · Male | `opponens_digiti_minimi_l` | 406 | **skinned** | 2855 | 5 | 10 | 2 | 2 |
| Combined · Male | `opponens_digiti_minimi_r` | 407 | **skinned** | 2854 | 5 | 10 | 2 | 2 |
| Combined · Male | `procerus` | 456 | **rigid** | 2805 | 0 | 8 | 1 | 0 |
| Combined · Male | `pronator_quadratus_r` | 458 | **skinned** | 2803 | 11 | 9 | 1 | 4 |
| Combined · Male | `rectus_femoris_reflected_head_l` | 3194 | **skinned** | 67 | 0 | 6 | 0 | 2 |
| Combined · Male | `rectus_femoris_reflected_head_r` | 3193 | **skinned** | 68 | 0 | 6 | 0 | 2 |
| Combined · Male | `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_l` | 978 | **skinned** | 2283 | 2 | 6 | 0 | 0 |
| Combined · Female | `extensor_indicis_l` | 155 | **skinned** | 3154 | 0 | 8 | 1 | 2 |
| Combined · Female | `flexor_carpi_ulnaris_r` | 183 | **skinned** | 3126 | 5 | 11 | 2 | 3 |
| Combined · Female | `flexor_digitorum_superficialis_r` | 195 | **skinned** | 3114 | 12 | 10 | 2 | 3 |
| Combined · Female | `opponens_digiti_minimi_r` | 405 | **skinned** | 2904 | 5 | 10 | 2 | 2 |
| Combined · Female | `procerus` | 454 | **rigid** | 2855 | 0 | 8 | 1 | 0 |
| Combined · Female | `rectus_femoris_reflected_head_l` | 3244 | **rigid** | 65 | 0 | 6 | 0 | 2 |
| Combined · Female | `rectus_femoris_reflected_head_r` | 3243 | **skinned** | 66 | 0 | 6 | 0 | 2 |
| Combined · Female | `supinator_l` | 583 | **skinned** | 2726 | 28 | 14 | 2 | 3 |

**One finding that makes this cheaper than Q297's assert implies, and it must be verified before anyone relies on
it.** The weight blob is addressed by **absolute byte offsets**, not by position in the list:
`make_pose_rig.py:111` writes each skin entry as `[i, nv, K, pal, off, nc]` with `off` an absolute offset into the
concatenated blob, and `pose.js:135` reads from `o.off`. So removing a *skinned* entry does **not** require
rewriting the weight blob — remove the entry, decrement every later `si` in both `skin` and `rigid`, drop the `nv`
element, decrement `count`, and the orphaned slab in the blob is simply never addressed again (the page grows by a
few KB of dead bytes and nothing else). That would turn Q297's "weight surgery needed" from a blocker into a
bookkeeping change. **It is untested: no browser was run this round.** It must be confirmed in real Chromium on a
rebuilt page before any skinned structure is removed — and if it holds, it should be written into
`make_pose_rig.py` as a supported operation rather than re-derived each time.

The alternative, which is certain and more expensive: rebuild the rig from the page with
`scripts/anatomy/q241/make_pose_rig.py` — which needs the build directory and re-derives the skinning weights.

### 5.6 The cheap deletions and the expensive ones

| structure | why it is cheap or expensive |
|---|---|
| `rectus_femoris_reflected_head_l` / `_r`, **both pages** | **cheapest of all.** 0 parts rows, 0 clinical files, and they sit at indices 3,193–3,194 and 3,243–3,244 — the last 65–68 indices of the page, so almost nothing renumbers. `_l` on Combined · Female is **rigid**, i.e. exactly the case Q297's tooling already handles. The cost is: 6 shared data files that name it, 2 tests, and the fact that Q293 shipped it *because the owner asked for it* ("rectus femoris has only the straight head, the reflected head is missing"). **Deleting it un-does an owner request.** |
| `psoas_minor_l` / `_r`, both pages | last two indices on each page, 0 parts rows, 0 clinical files, nothing renumbers — but they are already **hidden at load** and badged "NOT DEMONSTRATED ON THIS BODY", and Q306/Q311 shipped them *because the owner twice reported psoas minor missing from search*. Deleting them un-does two owner requests. They fail only the in-bone gate (19–31 % at 6.0–6.3 mm), which §4.2's conform pass fixes. **Repair, do not delete.** |
| `procerus`, both pages | **rigid** on both pages (indices 456 / 454), 0 parts rows. The only candidate that is both rigid and genuinely broken. 2,805–2,855 later indices to renumber. |
| every hand / forearm candidate (`opponens_digiti_minimi`, `flexor_pollicis_longus`, `abductor_pollicis_brevis`, `flexor_digiti_minimi_brevis_hand`, `flexor_digitorum_superficialis`, `flexor_carpi_ulnaris`, `supinator`, `extensor_indicis`, `pronator_quadratus`) | **the expensive and the wrong ones to delete.** Each is skinned, sits at a low index so 2,700–3,250 later indices renumber, is named in 8–14 shared data files and 1–2 clinical files, carries 5–28 parts rows, and is asserted in 2–4 tests. More importantly, each is a **real** mesh of real anatomy that is merely in the wrong place, and the thing that put it there — the unrefined forearm/hand fit — is a single recorded job that would fix all of them at once. Deleting them would strip the hand out of the atlas and leave the owner's own Q282 worked example (FPL) pointing at nothing. |

---

## 6. The decision only the owner can make

**Nothing on the Combined pages' muscle layer is invented anatomy. It is a real body's muscles in the wrong
place.** That is the finding, and it changes which of his two options applies.

So the single question is:

> **Repair the per-bone fit of the Combined pages' muscle layer — above all the forearm and hand, which Q195
> recorded as "not refined" when it shipped and which no round since has refined — or delete the 20 structures
> that fail two independent severity-3 checks and accept gaps where real anatomy used to be?**

What the numbers say about the choice:

* **Deletion removes 20 of 871 muscle meshes (2.3 %) and does not touch the complaint.** The owner's "slack,
  inconsistent, not matching" is the *median*: overlap 29.8 % / 34.7 %, a quarter of all twinned muscles outside
  the project's own 0.80–1.25 band, 148–168 muscles past the 5 mm bone-depth gate. Deleting the worst 20 leaves
  242 and 251 muscles still failing a gate.
* **Repair is one job, not 500.** 64–69 % of upper-limb and 71–76 % of head muscles fail something, against
  31–40 % in the lower limb, and the project's own records name the cause (`held_unrefined`, "forearm/hand not
  refined") and the fix ("re-register bone-driven … snap origins/insertions to the bone footprints", Q198's own
  `fix_approach`). The attachment data to snap to already exists: 122 origin and 231 insertion rows in
  `structure_parts.json`, mapped to `zan_m` / `zan_f`.
* **Four of the deletion candidates were shipped because he asked for them** (`rectus_femoris_reflected_head`,
  Q293; `psoas_minor`, Q306/Q311), and one of the worst (`flexor_pollicis_longus`) is the structure he chose as
  the atlas's worked example in Q282.
* **`opponens_digiti_minimi` on Combined · Male is the exception that should be fixed this week, not deleted**: the
  foot lump in the hand mesh is the Q213 split that Combined · Female already has and Combined · Male never
  received. That is a one-structure, one-page gap with a shipped remedy.

**The recommendation, for him to accept or overrule:** approve a baseline rebuild and the forearm/hand chain
refit; delete nothing yet; and if he wants something off the page immediately, the two honest candidates are
`rectus_femoris_reflected_head_l` / `_r` on both pages — the only muscles here that this project generated, that
fail their own gate, that carry no parts rows and no clinical references, and that renumber almost nothing. Even
those should be removed only together with a note on the neighbouring rectus femoris card saying why the reflected
head is absent, as Q297 did.

### Secondary items the owner may as well decide at the same time

1. **`levator_ani` needs a different source, not a re-fit** (0.013–0.042× its own architecture record on both
   pages). `docs/MUSCLE_GAPS.md` names the Chinese Visible Human pelvic-floor set, which Combined · Female already
   carries for the perineum.
2. **`zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_l/r` is classed `sys: "muscle"` on both pages.** It is
   a fibrous digital sheath, not a muscle. That is a one-line classification fix, and it would also remove it from
   this audit's population.
3. **The per-page structure list exists only inside the built page.** Nothing in git records which structures each
   page ships. Every count in this document had to be read out of a published artifact. A committed per-page
   manifest (ids, systems, provenance class) would make every future audit — and every future deletion review —
   possible from a clean clone.

---

## 7. Reproducing this

```
python3 scripts/anatomy/q319/audit_reconstructed_muscles_q319.py --src build/q309        # once build/ exists again
python3 scripts/anatomy/q319/audit_reconstructed_muscles_q319.py \
    --pages comb_m,comb_f \
    --page-dir comb_m=<dir with index.html + its geo blobs> \
    --page-dir comb_f=<dir> --cap 250000                                                 # what was run here
```

Needs `numpy` and `scipy` (`scipy.ndimage`, `scipy.spatial.cKDTree`); no `trimesh`, no build artefacts beyond the
page itself. Runtime ~60 s per page. Output: `data/derived/Q319_reconstructed_muscle_audit.json` (one record per
muscle mesh, with every number above plus the per-structure reason whenever a metric was measured but **not**
flagged) and a summary table on stdout.

**Housekeeping note.** This round committed nothing. While it was running, another session committed on this same
branch (`claude/3d-human-anatomy-atlas-e0kbxe`, the "Nerves: …" commits at 2026-11-11 11:22) and swept
`scripts/anatomy/q319/audit_reconstructed_muscles_q319.py` into its commit mid-edit. The working tree holds the
finished version; the committed copy is an earlier draft of it (`git diff HEAD` on that path shows the
difference). Nothing else in the working tree was touched by this round.

---

## Appendix — the 15 worst *repairable* muscles per page

Ordered by total severity. `(n/a)` on a gap means the structure's own record says that end attaches by tendon,
fascia, ligament, cartilage, skin or retinaculum, so the distance is reported but not counted against it (§2.1).
`pieces: a of b` is connected components against the number its record entitles it to.


### Combined · Male

| structure id | vol cm³ | origin gap mm | insertion gap mm | R/L vol | overlap % | in bone % / mm | pieces | architecture (evidence only) |
|---|---|---|---|---|---|---|---|---|
| `flexor_pollicis_brevis_l` | 2.81 | 0.06 (n/a) | 28.95 | 1.417 | 47.8 | 31.4 / 6.9 | 2 of 2 | — |
| `obliquus_capitis_superior_l` | 1.31 | 29.47 | 0.08 | 1.053 | 40.7 | 29.9 / 4.0 | 1 of 1 | cross-section 0.35x architecture |
| `flexor_digitorum_profundus_r` | 46.82 | 0.09 | 0.04 | 0.726 | 51.2 | 23.5 / 6.9 | 4 of 2 | cross-section 0.22x architecture |
| `zan_internal_intercostal_muscles_r` | 52.20 | — (n/a) | — (n/a) | 0.646 | 58.9 | 23.7 / 6.9 | 11 of 1 | — |
| `zan_internal_intercostal_muscles_l` | 80.84 | — (n/a) | — (n/a) | 0.646 | 47.9 | 21.6 / 7.2 | 10 of 1 | — |
| `sternocleidomastoid_r` | 23.92 | 22.87 | 17.51 | 0.733 | 15.1 | 0.0 / 0.0 | 1 of 2 | volume 0.419x architecture; cross-section 0.257x architecture |
| `longus_colli_r` | 6.22 | 0.03 | 0.03 | 0.405 | 33.0 | 16.6 / 4.5 | 3 of 1 | — |
| `longus_colli_l` | 15.36 | 0.09 | 0.09 | 0.405 | 29.4 | 16.6 / 4.5 | 3 of 1 | volume 3.2x architecture |
| `zan_lumbrical_muscles_of_hand_r` | 2.31 | — (n/a) | — (n/a) | 1.388 | 46.3 | 20.1 / 3.5 | 4 of 1 | — |
| `zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand_r` | 0.05 | — (n/a) | — (n/a) | 0.345 | 12.3 | 38.2 / 4.5 | 9 of 1 | — |
| `sternothyroid_l` | 6.47 | 10.75 | 19.42 (n/a) | 1.111 | 42.3 | 11.3 / 5.7 | 1 of 1 | volume 2.053x architecture |
| `rectus_capitis_posterior_minor_r` | 1.66 | 35.65 | 0.22 | 0.921 | 10.4 | 28.4 / 4.0 | 1 of 1 | — |
| `rectus_capitis_posterior_minor_l` | 1.80 | 34.91 | 0.10 | 0.921 | 17.6 | 26.3 / 3.5 | 1 of 1 | — |
| `rectus_capitis_lateralis_r` | 0.80 | 33.34 | 0.29 | 0.916 | 8.5 | 31.1 / 4.5 | 1 of 1 | — |
| `rectus_capitis_lateralis_l` | 0.87 | 29.46 | 0.23 | 0.916 | 12.4 | 27.2 / 3.5 | 1 of 1 | — |

### Combined · Female

| structure id | vol cm³ | origin gap mm | insertion gap mm | R/L vol | overlap % | in bone % / mm | pieces | architecture (evidence only) |
|---|---|---|---|---|---|---|---|---|
| `pronator_teres_r` | 9.82 | 0.18 | 0.12 | 0.531 | 45.9 | 30.6 / 8.7 | 2 of 1 | volume 0.45x architecture; cross-section 0.153x architecture |
| `pronator_teres_l` | 18.49 | 0.07 | 0.63 | 0.531 | 43.0 | 20.8 / 9.4 | 2 of 1 | cross-section 0.321x architecture |
| `extensor_digiti_minimi_l` | 5.00 | 7.95 | 0.39 | 1.542 | 61.3 | 25.1 / 6.6 | 1 of 1 | volume 4.168x architecture |
| `flexor_pollicis_longus_r` | 7.37 | 0.05 | 0.78 | 2.111 | 47.0 | 35.1 / 6.0 | 1 of 1 | cross-section 0.163x architecture |
| `flexor_pollicis_longus_l` | 3.49 | 0.08 | 0.07 | 2.111 | 47.2 | 29.1 / 4.5 | 1 of 1 | volume 0.478x architecture; cross-section 0.077x architecture |
| `flexor_digitorum_profundus_r` | 41.66 | 0.06 | 0.12 | 0.973 | 74.9 | 37.8 / 8.2 | 4 of 2 | cross-section 0.212x architecture |
| `zan_dorsal_parts_of_lateral_intertransversarii_lumborum_muscles_l` | 7.75 | — (n/a) | — (n/a) | 1.790 | 59.0 | 12.0 / 4.5 | 5 of 1 | — |
| `supinator_r` | 11.14 | 0.97 (n/a) | 0.10 | 1.717 | 49.8 | 19.2 / 6.6 | 1 of 1 | cross-section 0.467x architecture |
| `rectus_capitis_posterior_minor_l` | 1.39 | 29.21 | 0.14 | 1.341 | 52.7 | 21.5 / 2.8 | 1 of 1 | — |
| `rectus_capitis_lateralis_l` | 1.47 | 26.53 | 0.09 | 0.655 | 11.0 | 16.8 / 3.5 | 1 of 1 | volume 2.044x architecture |
| `rectus_capitis_anterior_r` | 0.73 | 28.39 | 1.09 | 0.723 | 16.8 | 22.9 / 4.0 | 1 of 1 | cross-section 0.485x architecture |
| `rectus_capitis_anterior_l` | 1.01 | 27.33 | 0.49 | 0.723 | 20.0 | 21.0 / 3.5 | 1 of 1 | — |
| `pronator_quadratus_r` | 5.21 | 0.08 | 0.08 | 1.408 | 68.5 | 20.5 / 4.5 | 1 of 1 | volume 2.316x architecture |
| `longus_colli_r` | 7.36 | 0.14 | 0.14 | 0.561 | 27.4 | 10.9 / 4.0 | 3 of 1 | — |
| `flexor_digitorum_superficialis_l` | 16.96 | 29.32 | 70.56 (n/a) | 0.784 | 42.8 | 2.5 / 2.8 | 1 of 4 | — |
