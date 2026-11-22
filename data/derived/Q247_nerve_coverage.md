# Q247 Part 1 - Peripheral and cranial nerve coverage audit of the six pages

Generated 2026-10-15 from the shipped pages `build/q244/*` (bundle / manifest read directly from each HTML), `data/anatomy/calibre.json` (Q240), `data/derived/Q186_zan_inventory.json` and the registry `data/nerves/*.json`. Nothing was built or modified. Reference checklist: Terminologia Anatomica / Gray's Anatomy (public domain) nomenclature as given in the Q247 brief; 146 items, each tier-rated for MSK / pelvic-floor / needling relevance (tier 1 = highest). Counting rule: one checklist item = one nameable nerve or branch group; a side counts when the page ships a mesh for it.

Legend. Z pages: `Y` own mesh (both sides L+R everywhere), `M` present only merged into a parent mesh (not separately addressable), `-` absent. Own pages: derivation per side - `meas` = traced / segmented on this person's own CT or cryosections (rule-assisted detector, partial course, see badge); `Z-xfer` = Z-Anatomy (CC BY-SA) mesh carried by per-bone transform, badge says "position estimate (generic course), not a dissection"; `mirror` = reflected from the other side (Q237), not measured; `xfer` = transferred from the other Visible Human subject.

## 1. Per-page summary

| Page (build/q244/...) | Title | nerve-category structures | peripheral / cranial nerve objects | checklist covered (Y / M / absent of 146) | calibre levels L1 trunk / L2 branch / L3 small / L4 fine | how derived |
|---|---|---|---|---|---|---|
| viewer_f_hr | Imaging-based Female | 43 | 19 (optic x2, femoral x2, tibial x2, sciatic x1, arm x12) + 24 spinal-cord segments (CNS, HRA transfer, not nerves) | 29 covered / 117 absent (Q247: 10 Y; + 19 checklist rows rule-based Q249) | 14 / 0 / 0 / 4 (18 nerves) | measured on her (optic, femoral R, tibial R, sciatic), mirror (femoral L, tibial L), Z-xfer (12 arm nerves) |
| viewer_m_hr | Imaging-based Male | 14 | 14 (optic L only, sciatic x1, tibial x2, arm x10) | 28 covered / 118 absent (Q247: 9 Y; + 19 checklist rows rule-based Q249) | 11 / 0 / 2 / 1 (14 nerves) | measured on him (sciatic about 1/3 of course, tibial L), mirror (tibial R), xfer from female (optic L), Z-xfer (10 arm nerves) |
| viewer_zan_female | Combined Female | 337 mesh objects in the nerve layer (109 of them are CNS tracts / nuclei / ocular parts mis-binned as nerve) | 228 (114 names x L+R) + optic II x2, meningeal branch V2 x2, cauda equina (CNS layer) | 105 Y / 7 M / 34 absent (Q247: 93 Y / 8 M / 45 absent; Q249 rows rule-based) | 50 / 9 / 67 / 102 (228 nerves) | all 337 = Z-Anatomy fitted onto her skeleton (Q168 per-bone similarity fits, trunk refit Q186c/Q190): estimate, not measured |
| viewer_zan_vhm | Combined Male | 337 (same set) | 228 + same CNS-layer extras | 105 Y / 7 M / 34 absent (Q247: 93 Y / 8 M / 45 absent; Q249 rows rule-based) | 49 / 17 / 85 / 77 | 335 Z-fitted onto his skeleton + 2 mirror fills (`lateral_femoral_cutaneous_n_l`, `superior_gluteal_n_l`, Q237) |
| viewer_zan_atlas | Base Male | 337 (same set) | 228 + same CNS-layer extras | 105 Y / 7 M / 34 absent (Q247: 93 Y / 8 M / 45 absent; Q249 rows rule-based) | 50 / 20 / 76 / 82 | native Z-Anatomy reference body, unfitted; PIN course corrected from literature (badge: Aggarwal et al., Hazani et al.) |
| viewer_base_female | Base Female (male-derived body) | 337 (same set) | 228 + same CNS-layer extras | 105 Y / 7 M / 34 absent (Q247: 93 Y / 8 M / 45 absent; Q249 rows rule-based) | 50 / 20 / 76 / 82 | as Base Male |

The four Z-family pages carry the identical 337 nerve-layer object ids (verified by set comparison); they differ only in geometry. Therefore one Z column serves all four in the checklist. Calibre figures are the page-embedded `nmsk-calibre` blocks of q244 (identical nerve counts to `data/anatomy/calibre.json`; calibre levels are by mesh diameter: trunk >= 4 mm, branch >= 2, small >= 1, fine < 1, with named main trunks promoted to level 1).

Own-page nerve inventory (exact):

- viewer_f_hr: `optic_n` L+R (CT segmentation, subject ct_vhf_orbit); `femoral_n` R (her cryosections, Q55, only y +13..-12 mm i.e. about 25 mm, ends at its division) and L (mirror); `tibial_n` R (Q56 popliteal) and L (mirror); `sciatic_n` L+R in one mesh (cryosection-tracked Q53: right -70..-235 mm, left -70..-293 mm; gluteal course above -70 and popliteal division not shipped); arm L and R: median (lateral root id), ulnar, radial, musculocutaneous, posterior interosseous, anterior interosseous (Z-xfer, Q200); 24 spinal-cord segments C1-T9, L3-S4 (HRA same-donor transfer Q243; T10-L2 absent).
- viewer_m_hr: `optic_n` L only (transferred from the female, re-seated 7.3 mm, Q185); `sciatic_n` (his 0.33 mm cryosections Q57, about a third of the course: right 126 / left 84 verified levels, gluteal and distal thirds missing); `tibial_n` L (rule-based tracking Q174, y -393..-429 only, not joined to sciatic, about 170 mm untracked) and R (mirror); arm: L median, ulnar, radial, musculocutaneous, AIN; R median, ulnar, radial, PIN, AIN (Z-xfer; asymmetric: no PIN on L, no musculocutaneous on R, no axillary / suprascapular etc. on either).
- Z-family (peripheral part, 114 names x L+R): see section 3 table, `Y` rows.

## 2. Headline numbers (Z-family pages, the best-covered)

| Group | items | Y | M | absent |
|---|---|---|---|---|
| Cranial | 31 | 21 | 0 | 10 |
| Cervical plexus | 5 | 0 | 0 | 5 |
| Brachial plexus | 45 | 38 | 4 | 3 |
| Thoracic | 4 | 0 | 1 | 3 |
| Spinal | 3 | 3 | 0 | 0 |
| Lumbar plexus | 16 | 11 | 2 | 3 |
| Sacral plexus | 27 | 22 | 0 | 5 |
| Pelvic floor | 6 | 5 | 0 | 1 |
| Autonomic | 9 | 5 | 0 | 4 |
| **Total** | 146 | 105 | 7 | 34 |

Own pages cover far less: viewer_f_hr 10 and viewer_m_hr 9 of 146 items, none of them below branch level except the Z-transferred AIN / PIN; every fine branch (digital, cutaneous, muscular, plantar) exists only on the four Z-family pages.

Z-Anatomy is the ceiling: its release (845 NervousSystem objects, Q186 inventory) ships every object with real geometry (538 shipped + 30 merged); the rest are 133 empty group nodes, 120 label pins, 14 non-commercial-licence items, 10 placeholders / curves. A scan of the 2023 `Startup.blend` of the current Z-Anatomy distribution (models-of-human-anatomy, commit e214005, 2026-10-13) found no additional nerve object names versus the Q186 inventory. The Z hierarchy does name about 100 nerve / plexus / ganglion groups that hold no mesh (e.g. Phrenic nerve, Perineal nerve, Deep branch of perineal nerve, Recurrent laryngeal nerve, Superior laryngeal nerve, Greater / Lesser petrosal nerve, Auriculotemporal nerve, Frontal nerve, Infra-orbital nerve, Ansa cervicalis, Subcostal nerve, Coccygeal plexus, Inferior hypogastric plexus, Lesser thoracic splanchnic nerve, Pharyngeal branch of vagus, Anterior / Posterior vagal trunk, Cardiac / Coeliac / Pelvic plexuses; string scan of the .blend, absence of a same-named object, so "no mesh" is inferred). Closing the gaps therefore needs a source other than Z-Anatomy.

Muscle records cite 120 distinct nerve ids in `innervation.nerve` (`data/muscles/*/*.json`, 677 muscle-nerve citations); 88 of those ids have no mesh on any Z page under that id (about 83 after allowing 5 alias spellings such as `median_n`, `ilioinguinal_n`, `upper_subscapular_n`); they serve about 480 citations. Most frequent: facial temporal branch (19 muscles), cervical-plexus rami to scalenes / prevertebrals (14), intercostal T1-T6 and thoracoabdominal T7-T11 branches (14 each), pharyngeal plexus (13), dorsal-ramus medial branches (10), facial zygomatic / buccal (10), suboccipital (8), subcostal, recurrent laryngeal, inferior gluteal, nerve to obturator internus, phrenic, sacral roots S3-S4.

## 3. Checklist against Terminologia Anatomica / Gray's

Tier: 1 = pelvic-floor / needling hazard or target / common MSK entrapment; 2 = moderate; 3 = low. `f_hr` / `m_hr` = Imaging-based Female / Male.

| Group | Item | Tier | Z-family (4 pages) | f_hr | m_hr |
|---|---|---|---|---|---|
| Cranial | I olfactory n. | 3 | Y | - | - |
| Cranial | II optic n. | 3 | Y (CNS layer) | L:meas R:meas | L:xfer |
| Cranial | III oculomotor n. | 3 | Y | - | - |
| Cranial | IV trochlear n. | 3 | Y | - | - |
| Cranial | V trigeminal trunk + sensory/motor roots | 2 | Y | - | - |
| Cranial | V1 ophthalmic n. | 3 | Y | - | - |
| Cranial | V1 branches (frontal/supraorbital/supratrochlear, lacrimal, nasociliary) | 2 | - | - | - |
| Cranial | V2 maxillary n. | 3 | Y | - | - |
| Cranial | V2 branches (infraorbital, zygomatic, pterygopalatine/greater palatine) | 2 | - | - | - |
| Cranial | V2 meningeal branch | 3 | Y (CNS layer) | - | - |
| Cranial | V3 anterior/posterior divisions | 3 | Y | - | - |
| Cranial | V3 buccal n. | 3 | Y | - | - |
| Cranial | V3 inferior alveolar n. (+ mental n.) | 2 | Y | - | - |
| Cranial | V3 lingual n. | 3 | Y | - | - |
| Cranial | V3 n. to mylohyoid | 3 | Y | - | - |
| Cranial | V3 masseteric / deep temporal / pterygoid nn. (masticatory motor) | 2 | - | - | - |
| Cranial | V3 auriculotemporal n. | 2 | - | - | - |
| Cranial | VI abducens n. | 3 | Y | - | - |
| Cranial | VII facial n. trunk | 2 | Y | - | - |
| Cranial | VII chorda tympani | 3 | Y | - | - |
| Cranial | VII terminal branches (temporal, zygomatic, buccal, marginal mandibular, cervical), post. auricular | 2 | - | - | - |
| Cranial | VII greater petrosal n. | 3 | - | - | - |
| Cranial | VIII vestibulocochlear n. | 3 | Y | - | - |
| Cranial | IX glossopharyngeal n. (trunk) | 3 | Y | - | - |
| Cranial | IX branches (tympanic, carotid sinus, pharyngeal, stylopharyngeal) | 3 | - | - | - |
| Cranial | X vagus n. (cervical trunk) | 2 | Y | - | - |
| Cranial | X branches: recurrent + superior laryngeal, pharyngeal, cardiac | 2 | - | - | - |
| Cranial | X thoracic/abdominal: oesophageal plexus, anterior/posterior vagal trunks, pulmonary plexus | 2 | - | - | - |
| Cranial | XI accessory n. (spinal root) | 1 | Y | - | - |
| Cranial | XI cranial root / distal course to trapezius | 2 | - | - | - |
| Cranial | XII hypoglossal n. | 3 | Y | - | - |
| Cervical plexus | C1-C4 ventral rami / ansa cervicalis | 2 | - | - | - |
| Cervical plexus | Phrenic n. | 1 | - | - | - |
| Cervical plexus | Lesser occipital, great auricular, transverse cervical, supraclavicular nn. | 2 | - | - | - |
| Cervical plexus | Cervical dorsal rami: greater occipital (C2), third occipital, medial branches (facet) | 1 | - | - | - |
| Cervical plexus | Suboccipital n. (C1 dorsal ramus) | 2 | - | - | - |
| Brachial plexus | Roots C5-C8/T1 (one combined mesh, not separable by level) | 2 | Y | - | - |
| Brachial plexus | Trunks (superior, middle, inferior) | 2 | Y | - | - |
| Brachial plexus | Divisions (6: ant/post x 3 trunks) | 2 | Y | - | - |
| Brachial plexus | Posterior cord | 2 | Y | - | - |
| Brachial plexus | Lateral cord | 2 | - | - | - |
| Brachial plexus | Medial cord | 2 | - | - | - |
| Brachial plexus | Dorsal scapular n. | 1 | Y | - | - |
| Brachial plexus | Suprascapular n. | 1 | Y | - | - |
| Brachial plexus | N. to subclavius | 3 | Y | - | - |
| Brachial plexus | Long thoracic n. | 1 | Y | - | - |
| Brachial plexus | Lateral pectoral n. | 2 | Y | - | - |
| Brachial plexus | Medial pectoral n. | 2 | Y | - | - |
| Brachial plexus | Upper subscapular n. | 2 | Y | - | - |
| Brachial plexus | Lower subscapular n. | 2 | Y | - | - |
| Brachial plexus | Thoracodorsal n. | 2 | Y | - | - |
| Brachial plexus | Musculocutaneous n. | 1 | Y | L:Z-xfer R:Z-xfer | L:Z-xfer |
| Brachial plexus | Lateral antebrachial cutaneous n. | 2 | Y | - | - |
| Brachial plexus | Axillary n. | 1 | Y | - | - |
| Brachial plexus | Axillary muscular branches (deltoid, teres minor) | 1 | M in axillary_n | - | - |
| Brachial plexus | Superior lateral brachial cutaneous n. | 2 | Y | - | - |
| Brachial plexus | Radial n. (trunk) | 1 | Y | L:Z-xfer R:Z-xfer | L:Z-xfer R:Z-xfer |
| Brachial plexus | Radial muscular branches (triceps, brachioradialis, ECRL) | 1 | M in radial_n | - | - |
| Brachial plexus | Radial superficial branch | 1 | Y | - | - |
| Brachial plexus | Radial posterior interosseous n. (deep branch) | 1 | Y | L:Z-xfer R:Z-xfer | R:Z-xfer |
| Brachial plexus | Radial posterior cutaneous n. of arm / forearm | 2 | M in posterior_femoral_cutaneous_n (Z 'Posterior antebrachial cutaneous', suspect id) | - | - |
| Brachial plexus | Radial inferior lateral brachial cutaneous n. | 2 | Y | - | - |
| Brachial plexus | Radial dorsal digital branches | 3 | Y | - | - |
| Brachial plexus | Median n. (trunk; Z carries one mesh, no medial/lateral root split) | 1 | Y | L:Z-xfer R:Z-xfer | L:Z-xfer R:Z-xfer |
| Brachial plexus | Median anterior interosseous n. | 1 | Y | L:Z-xfer R:Z-xfer | L:Z-xfer R:Z-xfer |
| Brachial plexus | Median muscular branches (pronator, FCR, PL, FDS) | 1 | Y | - | - |
| Brachial plexus | Median palmar cutaneous branch | 2 | Y | - | - |
| Brachial plexus | Median recurrent (thenar) branch | 1 | Y rule-based Q249 (all four pages L+R) | rule L:Y R:Y | rule L:Y R:- |
| Brachial plexus | Median common + proper palmar digital nn. | 2 | Y | - | - |
| Brachial plexus | Median-ulnar communicating branch (Berrettini) | 3 | Y | - | - |
| Brachial plexus | Ulnar n. (trunk) | 1 | Y | L:Z-xfer R:Z-xfer | L:Z-xfer R:Z-xfer |
| Brachial plexus | Ulnar muscular branches (FCU, FDP) | 2 | Y | - | - |
| Brachial plexus | Ulnar palmar cutaneous branch | 3 | M in ulnar_n | - | - |
| Brachial plexus | Ulnar dorsal branch | 2 | Y | - | - |
| Brachial plexus | Ulnar superficial branch | 2 | Y | - | - |
| Brachial plexus | Ulnar deep branch | 1 | Y | - | - |
| Brachial plexus | Ulnar common + proper palmar digital nn. | 2 | Y | - | - |
| Brachial plexus | Ulnar dorsal digital nn. | 3 | Y | - | - |
| Brachial plexus | Medial brachial cutaneous n. | 2 | Y | - | - |
| Brachial plexus | Medial antebrachial cutaneous n. (+ ant./post. branches) | 2 | Y | - | - |
| Brachial plexus | Intercostobrachial n. | 3 | - | - | - |
| Thoracic | Thoracic spinal nn. T1-T12 individually (ventral rami / intercostal) | 1 | M in zan_intercostal_nerves (one mesh per side, not separable) | - | - |
| Thoracic | Subcostal n. (T12) | 2 | - | - | - |
| Thoracic | Thoracic dorsal rami (medial branches; multifidus / facet) | 1 | - | - | - |
| Thoracic | Lateral + anterior cutaneous branches of intercostals | 3 | - | - | - |
| Spinal | Generic spinal nerve anterior + posterior root | 3 | Y | - | - |
| Spinal | Spinal (dorsal root) ganglion (generic, one object) | 3 | Y | - | - |
| Spinal | Cauda equina / filum terminale (CNS layer) | 2 | Y (CNS layer) | - | - |
| Lumbar plexus | L1-L4 ventral rami / plexus within psoas | 2 | - | - | - |
| Lumbar plexus | Lumbar dorsal rami (medial branch, facet RF; multifidus) | 1 | Y rule-based Q249 (all four pages L+R; medial branches L1-L4 + L5 dorsal ramus) | rule L:Y R:Y | rule L:Y R:Y |
| Lumbar plexus | Iliohypogastric n. | 1 | Y | rule L:Y R:Y | rule L:Y R:Y |
| Lumbar plexus | Ilioinguinal n. | 1 | Y rule-based Q249 (all four pages L+R; no ilioinguinal mesh exists on the four Z pages (Q247 listed Y); Q247: Y) | rule L:Y R:Y | rule L:Y R:- |
| Lumbar plexus | Genitofemoral n. | 2 | Y | rule L:Y R:Y | rule L:Y R:Y |
| Lumbar plexus | Genitofemoral femoral branch | 3 | Y | - | - |
| Lumbar plexus | Genitofemoral genital branch | 2 | M in genitofemoral_n | rule L:Y R:Y | rule L:Y R:Y |
| Lumbar plexus | Lateral femoral cutaneous n. | 1 | Y | - | - |
| Lumbar plexus | Femoral n. (trunk) | 1 | Y | L:mirror R:meas | - |
| Lumbar plexus | Femoral anterior cutaneous branches | 2 | Y | - | - |
| Lumbar plexus | Femoral muscular branches (quadriceps, sartorius, pectineus), n. to iliacus/psoas | 1 | - | - | - |
| Lumbar plexus | Saphenous n. | 1 | Y | - | - |
| Lumbar plexus | Saphenous infrapatellar + medial crural branches | 2 | Y | - | - |
| Lumbar plexus | Obturator n. (trunk) | 1 | Y | - | - |
| Lumbar plexus | Obturator anterior + posterior branches | 1 | M in obturator_n | - | - |
| Lumbar plexus | Accessory obturator n. | 3 | - | - | - |
| Sacral plexus | Lumbosacral trunk; S1-S4 ventral rami (plexus roots) | 1 | Y rule-based Q249 (all four pages L+R; S1-S4 ventral rami + lumbosacral trunk; Q247: M in posterior_femoral_cutaneous_n (Z 'anterior/posterior root of PFCN' only)) | rule L:Y R:Y | rule L:Y R:Y |
| Sacral plexus | Sciatic n. | 1 | Y | L+R:meas | L+R:meas |
| Sacral plexus | Tibial n. | 1 | Y | L:mirror R:meas | L:meas R:mirror |
| Sacral plexus | Tibial muscular branches (gastrocnemius, soleus, popliteus, tib. post.) | 1 | - | - | - |
| Sacral plexus | Medial sural cutaneous n. | 2 | Y | - | - |
| Sacral plexus | Medial + lateral calcaneal branches (tarsal tunnel) | 1 | - | - | - |
| Sacral plexus | Medial plantar n. | 1 | Y | - | - |
| Sacral plexus | Lateral plantar n. | 1 | Y | - | - |
| Sacral plexus | Plantar common + proper digital nn. | 2 | Y | - | - |
| Sacral plexus | Common fibular (peroneal) n. | 1 | Y | - | - |
| Sacral plexus | Lateral sural cutaneous n. | 2 | - | - | - |
| Sacral plexus | Sural communicating branch | 3 | Y | - | - |
| Sacral plexus | Sural n. | 2 | Y | - | - |
| Sacral plexus | Superficial fibular n. | 1 | Y | - | - |
| Sacral plexus | Superficial fibular medial + intermediate dorsal cutaneous nn. | 2 | Y | - | - |
| Sacral plexus | Deep fibular n. | 1 | Y | - | - |
| Sacral plexus | Deep fibular muscular branches | 2 | Y | - | - |
| Sacral plexus | Dorsal digital nn. of foot (superficial + deep fibular) | 3 | Y | - | - |
| Sacral plexus | Nerve to hamstrings / sciatic muscular branches | 1 | - | - | - |
| Sacral plexus | Superior gluteal n. | 1 | Y | - | - |
| Sacral plexus | Inferior gluteal n. | 1 | Y rule-based Q249 (all four pages L+R) | rule L:Y R:Y | rule L:Y R:Y |
| Sacral plexus | N. to piriformis | 1 | Y | - | - |
| Sacral plexus | N. to quadratus femoris (+ inferior gemellus) | 2 | Y | rule L:Y R:Y | rule L:Y R:Y |
| Sacral plexus | N. to obturator internus (+ superior gemellus) | 1 | Y rule-based Q249 (all four pages L+R) | rule L:Y R:Y | rule L:Y R:Y |
| Sacral plexus | Posterior femoral cutaneous n. | 1 | Y | rule L:Y R:Y | rule L:Y R:- |
| Sacral plexus | Perforating cutaneous n. (S2-S3) | 3 | - | - | - |
| Sacral plexus | Coccygeal plexus / anococcygeal nn. | 1 | Y rule-based Q249 (all four pages L+R) | rule L:Y R:Y | rule L:Y R:Y |
| Pelvic floor | Pudendal n. (trunk) | 1 | Y | rule L:Y R:Y | rule L:Y R:Y |
| Pelvic floor | Inferior rectal n. | 1 | Y rule-based Q249 (Combined M L+R, Combined F R only, Base M L+R, Base F L+R) | rule L:Y R:Y | rule L:Y R:Y |
| Pelvic floor | Perineal n. (posterior scrotal/labial, muscular) | 1 | Y rule-based Q249 (Combined M L only, Combined F L+R, Base M L+R, Base F R only) | rule L:- R:Y | rule L:Y R:Y |
| Pelvic floor | Dorsal n. of clitoris / penis | 1 | Y rule-based Q249 (Combined M L+R, Combined F L+R, Base M L+R; sex-specific: penis on the male pages, clitoris on the female pages) | rule L:Y R:Y | rule L:Y R:Y |
| Pelvic floor | N. to levator ani (S3-S5 direct) / coccygeus | 1 | Y rule-based Q249 (all four pages L+R) | rule L:Y R:Y | rule L:Y R:Y |
| Pelvic floor | Perineal branch of posterior femoral cutaneous n. | 2 | - | - | - |
| Autonomic | Sympathetic trunk (one mesh per side) | 2 | Y | - | - |
| Autonomic | Sympathetic chain ganglia (one combined object) | 2 | Y | - | - |
| Autonomic | Generic 'sympathetic nerves' object | 3 | Y | - | - |
| Autonomic | Stellate / cervical ganglia; rami communicantes (grey/white) | 2 | - | - | - |
| Autonomic | Greater/lesser/least splanchnic nn.; lumbar + sacral splanchnic nn. | 2 | - | - | - |
| Autonomic | Coeliac / mesenteric ganglia, aorticorenal, abdominal plexuses | 3 | - | - | - |
| Autonomic | Superior hypogastric plexus / hypogastric nn. | 1 | Y rule-based Q249 (all four pages L+R; hypogastric nerves + superior hypogastric plexus) | rule L:Y R:Y | rule L:Y R:Y |
| Autonomic | Inferior hypogastric (pelvic) plexus; pelvic splanchnic nn. S2-S4 | 1 | Y rule-based Q249 (all four pages L+R; inferior hypogastric plexus + pelvic splanchnic nerves S2-S4) | rule L:Y R:Y | rule L:Y R:Y |
| Autonomic | Cardiac + pulmonary plexuses | 3 | - | - | - |

## 4. Missing list ranked by clinical relevance (MSK / pelvic floor / needling)

Ranked groups (items in brackets are the checklist rows; absent on all six pages unless stated):

- **1. Pudendal branches and pelvic-floor motor nerves**: Inferior rectal n.; perineal n. (posterior scrotal / labial); dorsal n. of clitoris / penis; n. to levator ani (S3-S5) and coccygeus; coccygeal plexus / anococcygeal nn.; perineal branch of the posterior femoral cutaneous n. The pages ship only the pudendal trunk. Relevant to pudendal block, levator ani / coccygeus / external anal sphincter needling and botulinum targets, and the Alcock-canal entrapment picture. Highest priority.
- **2. Sacral plexus roots and deep-gluteal nerves**: S1-S4 ventral rami / lumbosacral trunk (only Z 'anterior / posterior root of PFCN' merged under the PFCN id); inferior gluteal n.; n. to obturator internus (+ superior gemellus); sciatic muscular branches to hamstrings. Deep gluteal / piriformis syndrome, hip and gluteal needling, sciatic injury avoidance.
- **3. Pelvic autonomics**: Superior / inferior hypogastric plexus, hypogastric nn., pelvic splanchnic nn. (S2-S4), lumbar / sacral splanchnics, stellate / cervical ganglia, rami communicantes, greater / lesser / least splanchnics. Pelvic pain and sympathetic blocks; the pages show only an undifferentiated sympathetic trunk + one ganglia object.
- **4. Dorsal rami (medial branches)**: Cervical (greater occipital C2, third occipital, medial branches), thoracic and lumbar dorsal rami with medial branches, suboccipital n. Radiofrequency denervation targets, multifidus / paraspinal needling, headache; none exist as geometry although `data/nerves/dorsal_rami.json` defines them.
- **5. Cervical plexus**: Phrenic n. (needling hazard in neck / scalene, interscalene block spread), C1-C4 rami, ansa cervicalis, lesser occipital, great auricular, transverse cervical, supraclavicular nn.; spinal accessory distal course to trapezius (only the spinal root is shipped).
- **6. Lower-limb motor and tarsal-tunnel branches**: Femoral muscular branches (quadriceps, sartorius, pectineus, iliacus), obturator anterior / posterior branches (merged in one mesh), tibial muscular branches (gastrocnemius, soleus, popliteus, tibialis posterior), medial / lateral calcaneal branches, lateral sural cutaneous n.. Motor-point / nerve-block planning, tarsal tunnel.
- **7. Upper-limb gaps**: Median recurrent (thenar) branch; lateral and medial cords (+ medial root of median); radial muscular branches (supinator / ECRB, radial-tunnel level) and posterior cutaneous nn. of arm / forearm (merged or absent); axillary muscular branches (merged); ulnar palmar cutaneous (merged); intercostobrachial. Carpal-tunnel / radial-tunnel / quadrilateral-space needling.
- **8. Thoracic**: Individual T1-T12 intercostal nerves (one combined `intercostal nerves` object), subcostal n., thoracic dorsal rami, lateral and anterior cutaneous branches. Intercostal / paravertebral block planning.
- **9. Head and neck**: Facial terminal branches (temporal, zygomatic, buccal, marginal mandibular, cervical, posterior auricular), V1 branches (supraorbital, supratrochlear, lacrimal), V2 infraorbital / zygomatic, V3 masseteric / deep temporal / pterygoid / auriculotemporal, vagus branches (recurrent and superior laryngeal, pharyngeal, cardiac, oesophageal, vagal trunks), glossopharyngeal branches. Relevant to TMD / masseter and facial needling, thyroid / laryngeal procedures; lowest MSK weight but 19 muscle records cite the facial temporal branch.

Counts (after Q249; Q247: 45 absent = tier 1: 18, tier 2: 19, tier 3: 8; 8 merged): 34 items absent on every Z page (tier 1: 7, tier 2: 19, tier 3: 8); 7 items present only merged into a parent mesh (obturator branches, genitofemoral genital branch, axillary and radial muscular branches, ulnar palmar cutaneous, posterior antebrachial cutaneous, thoracic intercostals, sacral roots).

Tier-1 absent items (checklist rows):

- Cervical plexus: Phrenic n.
- Cervical plexus: Cervical dorsal rami: greater occipital (C2), third occipital, medial branches (facet)
- Thoracic: Thoracic dorsal rami (medial branches; multifidus / facet)
- Lumbar plexus: Femoral muscular branches (quadriceps, sartorius, pectineus), n. to iliacus/psoas
- Sacral plexus: Tibial muscular branches (gastrocnemius, soleus, popliteus, tib. post.)
- Sacral plexus: Medial + lateral calcaneal branches (tarsal tunnel)
- Sacral plexus: Nerve to hamstrings / sciatic muscular branches

## 5. Data-quality observations (for follow-up, nothing changed)

- 109 of the 337 Z-family nerve-layer objects are not peripheral nerves (spinal-cord tracts, brain nuclei, cerebellar vermis parts, iris, sclera, tympanic membrane, spinal dura ...), so the layer count 337 overstates nerves; `calibre.json` correctly lists 228.
- Z-Anatomy object "Posterior antebrachial cutaneous nerve" (a radial branch) is merged under the `posterior_femoral_cutaneous_n` id in the Q186 inventory; likely an id mis-merge - verify before using that mesh for the forearm.
- Both posterior interosseous objects ship (`posterior_interosseous_n` = Z "Deep branch of radial nerve", and `zan_posterior_interosseous_nerve_of_forearm`) - a duplicate pair.
- The Z `median_n_lateral_root` id actually holds the single Z "Median nerve" object; the medial root of the median is absent.
- Left / right: every peripheral Z nerve exists on both sides (no one-sided id). Own-page arm nerves are asymmetric (viewer_m_hr lacks L PIN and R musculocutaneous; viewer_f_hr has all six on both sides).
- Reference registry: `data/nerves/*.json` defines 303 nerve entities (cranial / cervical 85, brachial 43, lumbosacral 83, autonomic 25, dorsal rami 8, plus root and thoracic-segmental files) with Gray's-derived targets; it is the natural rule source for any rule-based construction.

## 6. Q249 update (rule-based nerves; nothing here is measured)

Rows of section 3 filled by the rule-based nerves of Q249 (courses from Gray's Anatomy 1918, calibres and variability from the cited papers; every nerve is badged RULE-BASED, its card lists waypoints, calibre source and error bound): 19 of the 19 mapped rows touched.

Z-family (4 pages): 93 Y / 8 M / 45 absent -> 105 Y / 7 M / 34 absent of 146 (a 'Y rule-based' cell means at least one of the four pages carries the nerve; the cell lists which). Imaging-based F: 10 -> 29 covered rows; Imaging-based M: 9 -> 28 (own-page columns count every non-'-' cell).

Per page, nerves shipped (ids in `data/derived/Q249_shipped_<page>.json`, held and skipped nerves with reasons in `data/derived/Q249_rule_<page>.json`):

| Page | shipped | held | skipped because the Z page already has the nerve |
|---|---|---|---|
| Imaging-based F | 62 | 1: perineal_n_l | 0 |
| Imaging-based M | 60 | 3: posterior_femoral_cutaneous_n_r, ilioinguinal_n_r, recurrent_branch_of_median_n_r | 0 |
| Combined F | 52 | 1: inferior_rectal_n_l | 10 |
| Combined M | 51 | 2: perineal_n_r, superior_hypogastric_plexus | 10 |
| Base F | 50 | 3: dorsal_n_clitoris_l, perineal_n_l, dorsal_n_clitoris_r | 10 |
| Base M | 53 | 0: - | 10 |

Still absent after Q249 (tier 1): phrenic n., cervical / thoracic dorsal-ramus medial branches, femoral / tibial muscular branches, calcaneal branches, nerve to hamstrings, perineal branch of the posterior femoral cutaneous n. (course not attempted: the mediastinal / cervical / limb structures needed as anchors were not validated in this task).
