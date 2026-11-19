# Q363 — organ audit of the two Base pages (Base · Male, Base · Female)

Date 2026-11-17. Measured on the regenerated live pages (Base·M v97, Base·F v92; scratchpad `regen/q361/<dir>`), compared
with the page published before Q353–Q358 (v95 / v90). Frozen pages were read only, never changed.
Severity: **B** blocker (an organ a reader expects is absent or plainly broken), **S** should fix, **C** cosmetic / minor.
Source column for anything missing: **(a)** an un-exported object in the pinned Z-Anatomy source (the FBX files listed in
`data/derived/zanatomy_inventory.json`, clone `build/zanatomy`, not on disk now); **(b)** real geometry on the frozen
imaging pages `build/q309/viewer_m_hr` / `viewer_f_hr` (read-only source); **(c)** no real source: only a badged
rule-based structure from the books (like the existing Q259/Q261 nerve tubes) is possible.
Book references are to the owner's PDFs (PDF page numbers): Mannan = Noor MA, *Mannan's Regional Dissection and Surface
Anatomy*, 14th ed., Jaypee 2017; Sontakke = Sontakke YA, *Textbook of Human Anatomy* Vol. 5–6 (head–neck, brain), CBS 2023.

## 0. Phase 1 result (owner: "eyes are not intact, head nerves are missing")
- **Not a data, geometry or visibility regression.** Mesh ids are identical old vs new (3264 M; 3301 F + the Q358 perineal
  skin). Every eye, orbit, ear and cranial-nerve mesh has the same vertex count and bounding box. The eye parts' vertices
  are byte-identical. Q357 moved 47 (M) / 49 (F) head–neck vessels and nerves by ≤ 5.5 mm and removed nothing. Pick maps
  of the head (nerves shown, skin off, eye close-ups) draw the same set of nerves before and after.
- **What did change (Q354):** sclera, iris, vitreous body, zonular fibres, optic tract and spinal dura moved from the nerve
  layer to the cns layer. Colour is per layer in the Z engine, so the globe went from a yellow sclera with a lavender
  cornea to one lavender ball. The move is anatomically right, but the eye lost its only contrast → separate round (eye colours).
- **Real eye defects, all there before this week:** Base·F globes carry spikes up to 7–9 mm from the body registration.
  The right sclera is inside-out on both bodies. The eye parts are coloured as nervous tissue. Choroid, ciliary body and
  conjunctiva are absent. Detail: scratchpad `q363/eye_notes.md`.
- **Head nerves:** none were lost. The missing ones (§2) were never built: their registry records exist in `data/nerves/`,
  but the rule did not place them, or they were held.

## 1. Special senses

| organ / part | Base·M | Base·F | finding | sev | source / fix |
|---|---|---|---|---|---|
| Globe: sclera, cornea, iris, lens, retina, vitreous, chambers, zonule (`zan_*_l/_r`) | 12+10 parts, L+R | same | all on layer cns (colour of the brain); sclera open at the cornea (normal), right sclera inside-out (21 % faces outward) | S | eye colour round; flip `zan_sclera_r` winding |
| Globe shape | sound sphere | spikes: sclera +7.0 mm, posterior segment +6.8, retina +6.3–6.6, cornea +3.9, iris +5.5 (posterior pole and lateral limbus) | registration warp, present on the pre-Q353 page too | B (F) | smooth the outliers (vertex ids in eye_notes) |
| Suspensory ligament of eyeball | juts 11 mm medially and laterally | same | source shape (Lockwood's ligament hammock), but reads as "ears" on the globe | C | eye round |
| Choroid, ciliary body | absent | absent | Z has only `Ciliary body-curve.r` (a curve) | S | (c) |
| Conjunctiva, orbital septum, eyelid skin | absent | absent | lids = tarsi + orbicularis oculi + orbital-region skin | S | (c) |
| Extra-ocular muscles (4 recti, 2 obliques, levator palpebrae), common tendinous ring, trochlea | L+R | L+R | trochlea now cartilage (Q354, correct); superior/inferior tarsus filed as **muscle** (tarsal plates are dense connective tissue) | C | reclass tarsi → joint/ligament layer |
| Lacrimal gland, sac, canaliculi, ampulla, nasolacrimal duct | L+R | L+R | Q354 removed the lacrimal **bone** record that the gland used to show (correct) | — | — |
| Optic nerve, chiasm, tract | L+R (cns) | L+R | the chiasm is split into two halves `_l/_r` (source) | C | — |
| External ear | auricle = 10 skin regions/side | same | no auricular cartilage, no ear canal (external meatus) | S | (c); the meatus is a canal in the temporal bone |
| Tympanic membrane, auditory tube | L+R, now viscera (Q354) | same | correct | — | — |
| Ossicles | malleus, incus, stapes L+R | same | — | — | — |
| Inner ear | `oa_labyrinth`, `oa_spiral_lamina`, `oa_fenestra_cochleae`, `oa_stapedius` L+R (SPL Inner Ear Atlas, Q296) | same | the `_l` set is inside-out | C | flip winding. Z's own Cochlea / Vestibule are licence-blocked (CC-BY-NC-SA) |
| Nose | major alar cartilages (filed **bone**), nasal bones, inferior conchae, nasal mucosa, frontal + sphenoid sinuses | same | no septal / lateral nasal cartilage, no maxillary or ethmoidal sinus | S | (c); cartilage class: C |
| Tongue | one mesh + genio/hyo/styloglossus | same | no intrinsic tongue muscles | S | (c) |
| Salivary glands, soft palate, uvula, palatine tonsils, 28 teeth | present | present | — | — | — |

## 2. Cranial nerves and head–neck nerves (full checklist)

Display: every `nerve`-layer mesh is drawn at load (tissue row "Nerve structures"; Systems → "Nerves & CNS"; View →
nerve emphasis Clear/Strong, which widens sub-pixel nerves). The optic nerve, chiasm and tract are on the cns row
("Brain, cord & senses"). The skin is 30 % opaque at load, so the nerves are seen through it. "Z" = a real Z-Anatomy
mesh. "rule" = a Q259/Q261 rule-based tube (badged, cited), built from the registry `data/nerves/*.json` and the
scripts `scripts/anatomy/q259/rulenerve.py` and `q261/rule_cranial.py`.

| nerve / branch | Base·M | Base·F | sev | source if missing |
|---|---|---|---|---|
| CN I olfactory | `olfactory_n_l/_r` Z | same | — | olfactory bulb/tract absent: (c) |
| CN II optic, chiasm, tract | Z (cns) | Z | — | — |
| CN III oculomotor, CN IV trochlear, CN VI abducens | Z L+R | Z L+R | — | — |
| CN V trunk, sensory + motor roots | Z L+R | Z L+R | — | trigeminal ganglion absent: (c) |
| V1 ophthalmic | Z | Z | — | — |
| V1 frontal, supra-orbital, supratrochlear, lacrimal, nasociliary, anterior ethmoidal, infratrochlear | rule L+R | rule L+R | — | — |
| V1 long / short ciliary nerves | absent | absent | C | (c) |
| V2 maxillary | Z | Z | — | — |
| **V2 infra-orbital** | **absent** | **absent** | **B** | (c): registry `trigeminal_n_v2_infraorbital_branch` and its rule exist (`q261/rule_cranial.py` l.184, anchored to the real infra-orbital artery); never placed on any Z page — rerun dry to read the hold reason (Mannan PDF p. 41; Sontakke PDF p. 352–356) **Q365:** placed on both bodies as `trigeminal_n_v2_infraorbital_branch_l/_r`, Z-Anatomy geometry split from the maxillary nerve object where it enters the groove (not a rule tube; 61 mm M, 59 mm F). |
| V2 zygomatic, superior alveolar, palatine/nasopalatine | rule L+R | rule L+R | — | — |
| V2 meningeal branch (`zan_meningeal_branch_of_maxillary_nerve`) | Z, filed **cns** | same | C | reclass → nerve |
| V3 anterior/posterior divisions, buccal, lingual, inferior alveolar, mental, nerve to mylohyoid | Z L+R | Z L+R | — | `trigeminal_n_v3_mental_branch_r` inside-out: C |
| V3 masseteric, deep temporal, auriculotemporal | rule L+R | rule L+R | — | — |
| V3 medial / lateral pterygoid branches | absent | absent | C | (c) rule exists (registry); Combined·M has `trigeminal_n_v3_medial_pterygoid_branch_l` |
| CN VII trunk | Z L+R | Z L+R; R volume 0.54 × L | S (F) | check R trunk (pre-existing) **Q365:** diagnosed: same 624 vertices and the same extent as the left side; the right tube is thinner (registration), not truncated -- left as is. |
| **VII temporal branch** | rule L+R | **absent L+R** | **B (F)** | (c) same rule; present on Combined·F; the guard failed on Base·F **Q365:** placed on Base·F L+R (100 mm): Q261 path crossed the skull before Q353 and the arch outside the skin after it; the rule now follows the books (parotid upper border, across the arch in the subcutaneous plane). |
| VII zygomatic, buccal, marginal mandibular, posterior auricular, digastric | rule L+R | rule L+R | — | — |
| VII cervical branch | rule L+R | **L only** | S | (c) rerun rule (present on Combined·F) **Q365:** placed on Base·F R (2.4 mm, the rule as is). |
| VII chorda tympani | Z L+R | Z L+R | — | — |
| VII greater petrosal, nerve to stapedius | absent | absent | C | (c) held in Q261 (no anchor) **Q365:** still not placed (no ganglion or canal mesh to anchor to). |
| CN VIII vestibulocochlear | Z L+R | Z L+R | — | cochlear/vestibular divisions: (a) Z `Cochlear nerve(.l)`, `Vestibular nerve.l/.r` are licence-blocked; registry records exist → (c) |
| CN IX trunk | Z | Z | — | — |
| IX tympanic, carotid, stylopharyngeal, tonsillar, lingual | rule L+R | rule L+R | — | lesser petrosal: (c) held |
| CN X trunk | Z L+R; **left ends at the upper thorax** (y 484 vs 243 mm), L/R volume 0.50 | same (0.60) | S | source mesh; thoracic course of the left vagus: (c) **Q365:** diagnosed: not truncated -- the left source mesh ends at the arch level and the page continues it with the rule-based oesophageal / abdominal trunks and coeliac branch (continuous at y 485 mm); no change. |
| X superior laryngeal, recurrent laryngeal, pharyngeal + plexus, cardiac | rule L+R | rule L+R | — | — |
| CN XI trunk | Z L+R | Z L+R | — | — |
| XI branch to SCM | **L only** | **L only** | S | (c) rerun rule; Combined pages have R **Q365:** still held: the right accessory trunk already lies on sternocleidomastoid (< 2 mm), the rule finds no length for a separate branch. |
| XI branch to trapezius | rule L+R | rule L+R | — | — |
| CN XII trunk | Z L+R | Z L+R | — | — |
| XII lingual branches | **R only** | rule L+R | S (M) | (c) rerun rule; Combined·M has L **Q365:** still held on Base·M: the trunk point lies within 3 mm of genioglossus (no length for a separate branch). |
| Cervical plexus roots C1–C4, ansa cervicalis, phrenic | rule L+R | rule L+R | — | — |
| Lesser occipital, great auricular, transverse cervical, supraclavicular | rule L+R | rule L+R | — | — |
| **Greater occipital, third occipital, suboccipital** | **absent** | **absent** | **S** | (c) registry records exist (`data/nerves/dorsal_rami.json`), never built (Mannan PDF p. 106–108; Sontakke PDF p. 234–246) **Q365:** placed on both bodies (Q365 rule, Mannan pp. 14, 88-90; Sontakke pp. 215-216, 225-227): greater 150 / 143 mm, third 131 / 135 mm, suboccipital 22 / 20 mm (M / F). |
| Cervical sympathetic trunk + ganglia | Z (one trunk + one "ganglia" mesh per side) | same | C | named superior/middle cervical and stellate ganglia: registry only → (c) |
| Ciliary, pterygopalatine, otic, submandibular ganglia | absent | absent | S | (c) held in Q261 ("a ganglion is not a tube"); needs a rule-based ellipsoid shape decision (Mannan PDF p. 38, 488–504; Sontakke PDF p. 281–290) **Q365:** still not placed: Q261 held them as no tube shape fits a ganglion; the books give position and size only, the objection stands. |

Not on either frozen imaging page either: their head nerves are the same rule-based tubes (subjects `*_rule_nerve_q259/260/263`).
So (b) adds nothing for the head nerves.

## 3. Central nervous system

| organ | Base·M | Base·F | finding | sev | source / fix |
|---|---|---|---|---|---|
| Cerebral gyri/sulci, insula, lobes | 60+ parts L+R | same | `zan_parieto_occipital_sulcus` L/R volume 0.09; precentral gyrus 0.67 | C | source |
| Cerebellum, vermis, brainstem, diencephalon, basal nuclei, limbic parts | present | present | `zan_superior_semilunar_lobule_l` 4 pieces | C | — |
| Ventricles: lateral L+R, third, fourth, aqueduct | present | present | — | — | — |
| Meninges | falx cerebri, tentorium L+R, spinal dura (31 pieces) | same | no cranial dura / arachnoid / pia | C | (c) |
| Spinal cord | grey horns + white matter + central canal | same | — | — | — |
| Pituitary, pineal | present (viscera) | present | — | — | — |
| CNS tracts, nuclei (Q354 → cns) | 105 moved nerve → cns | same | correct; the brain's tracts lost their yellow (were drawn as nerves) | — | — |

## 4. Thorax

| organ | Base·M | Base·F | finding | sev | source / fix |
|---|---|---|---|---|---|
| Heart: atria, ventricles, papillary muscles, valve leaflets | present (vessel layer) | same | heart filed as **vessel**; the right ventricle shell has a negative volume | S | reclass is a viewer-wide decision |
| Pericardium | **absent** | **absent** | | S | (c); Z has none |
| Great vessels | present | present | — | — | — |
| Larynx: thyroid, cricoid, arytenoid, corniculate cartilages, epiglottis | present (cartilages filed **bone**; epiglottis viscera) | same | no vocal folds | C | Q309 convention; folds (c) |
| Trachea, bronchi to segmental, 5 lobes, pleura | present | present | — | — | — |
| Thymus | L+R lobes | same | — | — | — |

## 5. Abdomen and pelvis (digestive, urinary, endocrine, lymphoid)

| organ | Base·M | Base·F | finding | sev | source / fix |
|---|---|---|---|---|---|
| Pharynx, oesophagus, stomach, duodenum | present | present | — | — | — |
| Jejunum | one mesh, **inside-out** | same | | S **2026-11-18: not a visible defect** — the engine draws both sides and turns the normal by face orientation (template l. 11760); 185 (M) / 174 (F) closed meshes have a negative signed volume (lungs, frontal, mandible, limb vessels) and render correctly. No winding round. | flip winding |
| **Ileum** | **absent** | **absent** | the small bowel stops at the jejunum | **B** | (b) `small_bowel` (jejunum + ileum) from his/her CT on Imaging·M/F; Z has none |
| Caecum | absent | absent | appendix and colon are present | S | (b) inside Imaging `colon`? (c) otherwise |
| Colon (ascending, transverse, descending, sigmoid), appendix, taeniae, mesocolon, omenta | present | present (+ her own sigmoid, CT) | — | — | — |
| **Rectum** | **absent** | `rectum` (her CT) | known | **B (M)** | (b) Imaging·M `rectum` (ct_vhm_pelvis) — Q362 **Q362: resolved by relabel.** The Z mesh labelled "Sigmoid colon" lies wholly below S3 (top at 0.43 of the sacral height) and ends 26 mm below the coccyx tip inside the Z external anal sphincter: it is this body's rectum + anal canal, now shown as "Rectum and anal canal" with its source label (data/anatomy/relabels_q362.json; Mannan pp. 385, 563). The CT rectum is not shipped (thinner; would leave 7–16 mm and 32 mm gaps). |
| **Anal canal**, internal anal sphincter | **absent** | absent (external sphincter present, CT) | | **B (M)**, S (F) | (b) Imaging·M/F `external_anal_sphincter` + parts; canal itself (c) **Q362 (M): resolved by the same relabel** (the anal canal is the lowest part of the relabelled Z mesh, inside the Z sphincter, which stays). The VHM sphincter (deep ring only) is not shipped. |
| Liver (8 segments), gallbladder, bile duct, pancreas + ducts | present | present | `zan_pancreatic_duct` inside-out | C | flip |
| **Kidneys** | **absent** | **absent** | | **B** | (a) Z `Kidney.l/.r` is CC-BY-NC (licence-blocked, `nc_licensing_note`); (b) Imaging·F `kidney_l/_r` (her CT) for Base·F; Base·M: no real source on any page → (c) or a new real source |
| Ureters | L+R | L+R | lead to no kidney | (with kidneys) | — |
| Bladder, urethra | present | present (+ CVH urethra, sphincters) | — | — | — |
| Suprarenal glands | L+R | L+R | L/R volume 1.75 (M), 1.45 (F); L centroid 26 mm off the mirrored R | C | anatomically the left is larger; check position |
| Thyroid, parathyroids | present | present | — | — | — |
| Spleen | present (lymph) | present | — | — | — |
| Lymph node groups | 128 | 128 | — | — | — |

## 6. Reproductive and perineum

| organ | Base·M | Base·F | finding | sev | source / fix |
|---|---|---|---|---|---|
| Testis, epididymis, ductus deferens, seminal gland, ejaculatory duct, prostate | present | — | — | — | — |
| Penis (corpora, glans) | present | — | — | — | — |
| **Scrotum**, spermatic cord coverings | **absent** | — | no skin region named scrotum | S | (c); Imaging·M has none either |
| Ovaries, uterine tubes, uterus (+ cervix), vagina, broad/cardinal/uterosacral ligaments | — | present | uterosacral L/R 2.03 | C | — |
| Vulva: clitoris, vestibular bulbs, Bartholin glands, perineal body, vulvar skin | — | present | known: skin coarse; Bartholin L/R 0.55 (side assigned by registration) | S | Q358 / Q362 |
| Breast (gland, ducts, fat, suspensory ligaments, nipple, areola) | — | present | gland and ducts fragmented (19 / 44 pieces), L/R 0.65–0.70 | C | known (her CT) |
| **Perineal muscles** (bulbospongiosus, ischiocavernosus, transverse perinei, external anal sphincter) | **absent**; levator ani parts, coccygeus present | present (CT/CVH) | known | **B (M)** | (b) Imaging·M `bulbospongiosus_l/_r`, `ischiocavernosus_l/_r`, `external_anal_sphincter` + parts (ct_vhm_pfloor) — Q362 **Q362: nothing shipped.** Bulbospongiosus L/R place in the midline on the bulb but lie 22–24 mm from the Z external anal sphincter, so they fail the perineal-body check (Mannan p. 354) and are held; ischiocavernosus is 5.5 mm inside the ramus; deep transverse perineal is 10–11 mm inside the Z prostate, which sits about 15 mm low on this body.  |

## 7. Peripheral nerves (limbs, trunk) — summary

Brachial plexus (roots, trunks, cords) and the five arm nerves: L+R on both. Lumbar plexus: complete (F has one extra
left branch). Sacral plexus (sciatic, tibial, common fibular, gluteal, pudendal, posterior femoral cutaneous): L+R.
Missing compared with the Combined page of the same sex (rule-based branches whose guard failed on Base): **Q365:** rerun of the same rules on the current pages: all still held -- the parent trunk already lies on the target muscle (< 2 mm, no length for a branch); anococcygeal ends 37 mm outside the skin; dorsal nerve of the clitoris lies lateral to the pudendal vessel (textbook order violated).
Base·M — `femoral_n_branch_to_sartorius_l/_r`, `_to_iliacus_l`, `_to_pectineus_r`, `tibial_n_branch_to_popliteus_r`,
`anococcygeal_n_l`. Base·F — `femoral_n_branch_to_iliacus_l/_r`, `tibial_n_branch_to_popliteus_l`,
`dorsal_n_clitoris_l/_r`. Severity S; source (c), a rerun of the same rule. Inside-out: `saphenous_n_r`,
`zan_intercostal_nerves_r` (C).

## 8. Joints and skin

| item | Base·M | Base·F | finding | sev |
|---|---|---|---|---|
| Shoulder, hip, knee, ankle, elbow, wrist capsules / ligaments | L+R | L+R | ligament of head of femur L/R 0.33 (M) and 6.2 (F); `anterior_cruciate_ligament_r`, `zan_posterior_sacro_iliac_ligament_r`, `zan_radial_collateral_ligament_of_wrist_joint_l` inside-out | S (femoral head lig.), C |
| Sternoclavicular ligament | — | L/R 0.24 | known | S |
| Skin regions | 242 | 242 + rule-based perineum | known seams (face, Base·F chest, toes) | see PROJECT_STATE §9 |

## 9. Cards and names
- Raw names: none left (Q354).
- Individual bones show their GROUP record on the card ("Ribs, left (1–7 true…)", "Toe phalanges (14)", "Carpal bones (8…)");
  96 (M) / 102 (F) meshes. Severity C. Fix: an own record per bone, or label the card section "Group".
- Iliococcygeus and pubococcygeus show the "Levator ani" record (the parent). C.
- Base·F only: the record name of the three lateral-sulcus rami is still the raw label ("Lat_Fis-ant-Horizont" …), while the
  mesh name was fixed by Q354. C. Fix: apply `card_rules_q354.NAMES` to `rec.name` too.
- **Q365: fixed.** `test_q354_cards.py::test_no_raw_id_tris_or_provenance_in_card_text` fails on both pages (`medial_pectoral_n_l`,
  `superficial_fibular_n_r`: "abbreviated id ('n', 't1', 'main')"); `test_q357_in_bone.py::test_applied_page_keeps_counts`
  fails on Base·F (the Q358 mesh was added after Q357). Pre-existing, not changed here.

## 10. Counts

B: 8 — infra-orbital nerve (both); Base·F VII temporal branches; Base·F globe spikes; ileum (both); kidneys (both);
Base·M rectum; Base·M anal canal / perineal muscles (counted once each).
S: 22. C: 18 (table rows; one row can cover both bodies).

## 11. Not covered
Per-mode and pose behaviour of these organs; renders of every organ (only the head was rendered: shots in scratchpad
`q363/shots/`); the muscles organ by organ (only the special-sense and pelvic muscles); vessel completeness; teeth and
tooth roots; lymph node placement; card text content beyond names and records.
