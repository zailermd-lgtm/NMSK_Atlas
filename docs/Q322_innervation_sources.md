# Q322 — muscle innervation: sources, reconciliation and the MUSCLE INNERVATION mode design

Owner, 2026-11-14 (translated): *"1. Go through the attached paper. 2. Enrich the information with similar and
related papers, and relevant websites and atlases; then validate which are really relevant. Then analyse the
information and create enrichment and refinement of the data. 3. Build a MUSCLE INNERVATION mode using all of that."*
This note covers steps 1–2 and the design for step 3. Scope: **Base · Male / Base · Female only.**

Data: `data/anatomy/innervation_q322.json` (public, schema `nmsk.innervation.v1`) ·
`clinical/data/innervation_injection_q322.json` (private, `nmsk.innervation_injection.v1`) ·
test `tests/test_q322_innervation.py`.

## 1. The paper

Güvener O, İnce B, Keçeli C, Tok F, Ricci V, Mezian K, Jačisko J, Chang KV, Kara M, Kaymak B, Özçakar L.
*Dynamic limb sono-anatomy for botulinum toxin injections: EURO-MUSCULUS/USPRM Spasticity Guide.*
Eur J Phys Rehabil Med 2026;62(5):441-59. DOI 10.23736/S1973-9087.26.09497-9. CC BY-NC-ND 4.0 — only facts
(names, numbers, landmarks) were extracted, with table/page citations; no prose, figure or image is in the repo,
and the PDF is not stored.

What it contains, as extracted:
- **Table I (p.442)**, upper limb: 32 rows — reference line (two landmarks), number of injection points, IZ site
  as % "of the distal part" of the line (i.e. measured from the proximal landmark). Forearm muscles all use the
  interepicondylar → interstyloid line; thenar muscles hook of hamate → 1st MC head; lumbricals/interossei radial
  styloid → MCP / MC heads; arm muscles coracoid → medial epicondyle and acromion tip → olecranon.
- **Table II (p.443)**, lower limb: 24 rows, lines ASIS–MFE, ASIS–patella, pubic tubercle–MFE, ischial
  tuberosity–MFE, popliteal fold–IML, fibular head–LM/submalleolar point, sole–1st MTP, T12–mid-inguinal ligament.
- **Per-muscle text (pp.444–457)**: anatomy, scan start, neighbouring structures, passive manoeuvres, and the IZ
  restated. The guide does **not** state the innervating nerve per muscle, so nerve, branch and roots come from
  other sources (§2). Its IZ numbers are cited to its refs 6, 8, 9 (the same group's 2018 review and guides).
- Muscles covered: **33 upper-limb + 27 lower-limb = 60 records** (teres major, iliacus, piriformis and EDL come
  from the text only; iliacus, piriformis and EDL have no IZ in the guide; subscapularis has three qualitative
  portions without %). 94 IZ bands in total, 56 muscles with a numeric IZ.

Internal inconsistencies of the guide found while extracting (all listed per muscle in `conflicts[]`):
1. FDL and FHL: Table II says fibular head – **lateral** malleolus; the text (p.456) says fibular head – **medial**
   malleolus. The table footnote defines "MM" although no row uses it. Text adopted; table variant kept.
2. Gastrocnemius/soleus: Table II "popliteal fold – IML"; text "popliteal fold – inferior margin of the lateral
   malleolus". Text adopted (it names a point); table variant kept as line `popliteal_iml`.
3. Adductor longus: text "pubic tubercle – MFC", table "MFE". MFE adopted (table, and Kwon 2009 uses MFE).
4. Latissimus dorsi: table "axillary fossa", text "axillary fold". Fold adopted.
5. Vastus intermedius uses ASIS–MFE while the other three quadriceps heads use ASIS–patella (consistent in table
   and text, so kept as published).
6. Pectoralis minor IZ is cited to ref 5 (a biceps HD-sEMG trial) — weakly supported.
7. "Patella", "lateral malleolus" and "submalleolar point" are not specified points; the adopted point is stated
   in each landmark's definition (patella base; LM tip; submalleolar = LM-tip proxy, badged).

## 2. Enrichment — what was searched and what could be opened

- **PubMed** (search, citation lookup, metadata/abstracts; full text from PMC where offered — it returned empty
  bodies for the two PMC items tried), **Consensus** (one successful search; one rate-limited), WebSearch once.
- **Blocked**: `onlinelibrary.wiley.com` and `lirias.kuleuven.be` do not resolve from this session (outside the
  environment's allowed hosts). Per the session rule, no further sites were tried. Consequence: the guide's own
  predecessors (Kara 2018, Kaymak 2018) and the Van Campenhout 2011 review — the most likely origin of the
  lower-limb lines — were read at abstract level only; their numbers were **not** used. Reputable atlases/sites
  (Barbero *Atlas of Muscle Innervation Zones*, Radiopaedia, Kenhub, Gray's/Standring, Kendall, the MRC *Aids to
  the examination of the PNS*) could **not** be opened and contribute nothing; no value is quoted from memory.
- Search strategy: the guide's reference list (refs 3–9) → PubMed citation match; then title searches for
  `motor endplate / motor point / innervation zone / intramuscular nerve / motor entry` × each muscle group;
  then root-level evidence (EMG vs surgically proven single-root lesions; intraoperative root stimulation;
  ISNCSCI key muscles). about 85 abstracts screened, 49 entered in the sources table below.
- **Already in the repo** and reconciled, not duplicated: `data/muscles/*` (nerve, root_levels and
  `motor_endplate_zones` from ~20 papers), `data/nerves/*` (312-entity nerve registry), and the private
  `clinical/data/motor_points.json` (`nmsk.motor_points.v1`, 185–199 rule-based points per Z page from ~40
  papers). Several of its rules come from papers that turned out to use the **same line as the guide**
  (Lee 2009 biceps/brachialis, Kwon 2009 adductors, An 2010 hamstrings, Yi 2021 sartorius, Lee 2011 / Choi 2019
  fibularis, Yi 2016 tibialis anterior); each was re-checked against its PubMed abstract and is cited here directly
  (public paper, public fact) — no private point, coordinate or rule text was copied into the public file.

### Source table (verdicts)

Verdict rule: **relevant** = primary data on the same or a near-same landmark line (or root-level data), values
checkable from what was opened; **partly** = right question but different line, values not reachable, or not
independent of the guide; **not relevant** = no positional data; **not used** = could not be opened.

| id | source | method · n · population | landmark line vs the guide | verdict | why / access |
|---|---|---|---|---|---|
| `an2010` | An XC et al. 2010 — Anatomic localization of motor entry points and intramuscular nerve endings in the hamstri… DOI 10.1007/s00276-009-0609-5 · PMID 20063163 | cadaveric dissection: motor entry points + proximal/distal limits of terminal nerve endings · 50 lower limbs · adult cadavers (Korea) | same line (x): ischial tuberosity - medial femoral epicondyle | **relevant** | [abstract (PubMed)] Used for 3 muscle(s). |
| `choi2019` | Choi YJ et al. 2020 — Guideline for botulinum toxin injections in the effective treatment of fibular spasticity… DOI 10.1002/ca.23487 · PMID 31581308 | modified Sihler stain, nerve endings per quarter · 10 specimens / 5 cadavers · fixed cadavers | quarters of the leg from proximal (repo record: fibular head - lateral malleolus) | **relevant** | [abstract (PubMed)] Used for 2 muscle(s). |
| `guv2026` | Güvener O et al. 2026 — Dynamic limb sono-anatomy for botulinum toxin injections: EURO-MUSCULUS/USPRM Spasticity G… DOI 10.23736/S1973-9087.26.09497-9 | expert consensus guide (narrative); IZ values cite its refs 6, 8, 9 · n/a | primary (defines the adopted lines) | **relevant** | [full text (owner-supplied PDF)] Used for 57 muscle(s). |
| `isncsci2019` | Rupp R et al. 2019 — International Standards for Neurological Classification of Spinal Cord Injury: revised 201… DOI 10.46292/sci2702-1 · PMID 34108832 | consensus standard (key muscles per myotome) · n/a | n/a | **relevant** | One representative key muscle group per root (C5-T1, L2-S1); not a full root range. Full text not returned by the tool; the key-muscle list is the standard's published worksheet. [citation (PubMed); content = the standard key-muscle list] Used for 16 muscle(s). |
| `kim2005` | Kim MW et al. 2005 — Anatomic localization of motor points in gastrocnemius and soleus muscles… DOI 10.1097/01.phm.0000176341.85398.a9 · PMID 16141745 | cadaveric dissection, terminal motor points · 8 limbs / 4 cadavers · male adult cadavers | near-same: femoral intercondylar line - intermalleolar line (guide: popliteal fold - IML) | **relevant** | [abstract (PubMed)] Used for 2 muscle(s). |
| `koo2019` | Koo YJ et al. 2019 — Safe needle insertion locations for motor point injection of the triceps brachii muscle: a… DOI 10.5535/arm.2019.43.6.635 · PMID 31918526 | cadaveric dissection of motor endplate zones · 12 limbs / 6 cadavers · fresh adult cadavers (Korea) | near-same: posterior acromial angle - olecranon midpoint (guide: acromion tip - olecranon) | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `kwon2009` | Kwon JY et al. 2009 — Anatomic localization of motor points of hip adductors… DOI 10.1097/PHM.0b013e3181619435 · PMID 18174845 | cadaveric dissection, motor points · 19 limbs / 10 cadavers · adult cadavers (Korea) | same line: pubic tubercle - medial femoral epicondyle | **relevant** | [abstract (PubMed)] Used for 4 muscle(s). |
| `lee2009` | Lee JH et al. 2010 — Localization of motor entry points and terminal intramuscular nerve endings of the musculo… DOI 10.1007/s00276-009-0561-4 · PMID 19779662 | cadaveric dissection of terminal intramuscular nerve endings · 56 arms · fresh adult cadavers (Korea) | same line: coracoid process (0%) - medial epicondyle | **relevant** | [abstract (PubMed)] Used for 2 muscle(s). |
| `lee2011pl` | Lee JH et al. 2011 — Anatomic localization of motor entry point of superficial peroneal nerve to peroneus longu… DOI 10.1002/ca.21076 · PMID 21322046 | cadaveric dissection, motor entry points · 43 legs / 25 bodies · fresh adult | same line: most proximal fibular head - most distal lateral malleolus | **relevant** | [abstract (PubMed)] Used for 2 muscle(s). |
| `levin1996` | Levin KH et al. 1996 — Cervical radiculopathies: comparison of surgical and EMG localization of single-root lesio… DOI 10.1212/wnl.46.4.1022 · PMID 8780083 | needle EMG vs surgically proven single-root lesions · 50 patients · cervical radiculopathy | n/a (root levels) | **relevant** | [abstract (PubMed)] Used for 9 muscle(s). |
| `repo_textbook` | Repository registry (data/muscles/* et al. 1998 — (Drake, Vogl, Mitchell); Moore KL, Dalley AF, Agur AMR, Clinically Oriented Anatomy 8th ed…  | textbook · n/a | n/a | **relevant** | Nerve, branch and textbook root levels; not re-opened this round, reconciled as-is. [repo record] Used for 60 muscle(s). |
| `rha2016` | Rha DW et al. 2016 — Intramuscular nerve distribution of the hamstring muscles: application to treating spastic… DOI 10.1002/ca.22735 · PMID 27213466 | Sihler stain · adult cadavers (Korea) | near-same, reversed: tibial condyles line (0%) - ischial tuberosity (100%) | **relevant** | [abstract (PubMed)] Used for 3 muscle(s). |
| `tsao2003` | Tsao BE et al. 2003 — Comparison of surgical and electrodiagnostic findings in single root lumbosacral radiculop… DOI 10.1002/mus.10291 · PMID 12508296 | needle EMG vs surgically confirmed single-level lesions · 45 patients · lumbosacral radiculopathy | n/a (root levels) | **relevant** | [abstract (PubMed)] Used for 3 muscle(s). |
| `vancamp2010` | Van Campenhout A et al. 2010 — Localization of motor nerve branches of the human psoas muscle… DOI 10.1002/mus.21660 · PMID 20544927 | cadaveric microdissection of nerve branches to terminal ramifications · 24 psoas muscles · adult cadavers | near-same: T12 to where psoas passes under the inguinal ligament | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2016ta` | Yi KH et al. 2017 — Neuromuscular structure of the tibialis anterior muscle for functional electrical stimulat… DOI 10.1007/s00276-016-1698-6 · PMID 27206542 | dissection + modified Sihler stain · 110 legs (10 stained) · Korean and Thai cadavers | same line, reversed: lateral malleolus (0%) - fibular head | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2021sar` | Yi KH et al. 2021 — Anatomical locations of the motor endplates of sartorius muscle for botulinum toxin inject… DOI 10.1007/s00276-021-02813-7 · PMID 34378107 | modified Sihler stain · 15 specimens · adult cadavers | same line: ASIS (0%) - medial femoral epicondyle | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2023tm` | Yi KH et al. 2024 — A practical guide to botulinum neurotoxin treatment of teres major muscle in shoulder spas… DOI 10.1002/pmrj.13048 · PMID 37526565 | Sihler stain · 18 cadavers · adult cadavers | muscle-relative (middle 20% of the muscle) | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2023tri` | Yi KH et al. 2023 — Distribution of the intramuscular innervation of the triceps brachii: clinical importance … DOI 10.1002/ca.24004 · PMID 36606364 | modified Sihler stain · 15 specimens · adult cadavers (Korea) | near-same, reversed: olecranon (0%) - anteroinferior acromion (100%) | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2024vm` | Yi KH et al. 2024 — Intramuscular neural distribution of the vastus medialis for botulinum neurotoxin injectio… DOI 10.1007/s00276-024-03482-y · PMID 39400571 | modified Sihler stain · 20 specimens · adult cadavers | same line: ASIS - base of patella (areas 1-10) | **relevant** | [abstract (PubMed)] Used for 1 muscle(s). |
| `amirali2007` | Amirali A et al. 2007 — Anatomical localization of motor endplate bands in the human biceps brachii… DOI 10.1097/CND.0b013e31815c13a7 · PMID 18090684 | Sihler stain (3) + whole-mount acetylcholinesterase (2) · 5 muscles · autopsy | different line: olecranon - acromion | **partly** | Different line and tiny sample; qualitatively consistent (distal half). [abstract (PubMed)] Used for 1 muscle(s). |
| `beretta2014` | Beretta Piccoli M et al. 2014 — Innervation zone locations in 43 superficial muscles: toward a standardization of electrod… DOI 10.1002/mus.23934 · PMID 24741685 | multichannel surface EMG · 40 subjects · healthy adults | landmark lines in the full text (not reachable) | **partly** | The best in-vivo IZ map of superficial muscles, but its values could not be opened; candidate for the next round. [abstract (PubMed)] |
| `diaconu` | Diaconu S et al et al.  — Visual-guide review series on image-guided botulinum toxin injection in spasticity, parts … PMID 40423325 | secondary synthesis (review series) · n/a | mixed; already in data/muscles | **partly** | Secondary source; at least two of its records in data/muscles carry a reversed counting direction (gastrocnemius) or swapped heads (triceps) relative to the primary papers - see conflicts. [repo record] Used for 13 muscle(s). |
| `garg2026` | Garg et al et al. 2026 — Localization of the motor entry point of the adductor pollicis muscle using surface landma… DOI 10.1016/j.aanat.2026.152881 · PMID 42413630 | cadaveric dissection · 21 hands · formalin-fixed adult | different: mm from 1st MCP joint (13.7 +/- 6.6) and radial styloid (48.5 +/- 8.2) | **partly** | Motor entry point, mm not %; consistent with a distal (near-MCP) target. [abstract (PubMed)] Used for 1 muscle(s). |
| `kara2018` | Kara M et al. 2018 — Sonographic guide for botulinum toxin injections of the upper limb: EUROMUSCULUS/USPRM spa… DOI 10.23736/S1973-9087.17.04664-0 · PMID 28264546 | narrative guide (predecessor; the guide cites it for every upper-limb IZ) · n/a | same lines (the guide reuses them) | **partly** | Same author group and same numbers: not an independent check. Full text not reachable from this session (publisher host blocked); abstract only. [abstract (PubMed)] |
| `kaymak2018iz` | Kaymak B et al. 2018 — Innervation zone targeted botulinum toxin injections… DOI 10.23736/S1973-9087.17.04663-9 · PMID 28264545 | narrative review of IZ localisation and toxin spread · n/a | n/a | **partly** | Background for the IZ concept; no per-muscle values in the abstract. [abstract (PubMed)] |
| `kaymak2018ll` | Kaymak B et al. 2018 — Sonographic guide for botulinum toxin injections of the lower limb: EUROMUSCULUS/USPRM spa… DOI 10.23736/S1973-9087.17.04667-6 · PMID 28382814 | narrative guide (predecessor; cited for every lower-limb IZ) · n/a | same lines | **partly** | Same group, same numbers; abstract only. [abstract (PubMed)] |
| `kurtys2023` | Kurtys K et al. 2023 — Localization of the gracilis muscle motor points - key considerations for botulinum neurot… DOI 10.1016/j.aanat.2023.152072 · PMID 36863619 | cadaveric dissection (multiple motor points, median 12) · 93 muscles · formalin-fixed | reference line not defined in the abstract | **partly** | Motor points 15-40% of its line; line unverified. [abstract (PubMed)] Used for 1 muscle(s). |
| `lepage2005` | Lepage D et al. 2005 — Extra- and intramuscular nerve supply of the muscles of the anterior antebrachial compartm… DOI 10.1007/s00276-005-0012-9 · PMID 16308665 | macro + microdissection · 30 forearms · adult cadavers (France) | surface topographic landmarks (not given in abstract) | **partly** | Relevant by design; no numbers reachable. [abstract (PubMed)] |
| `li2021` | Li Y et al. 2021 — Localization of nerve entry points and the center of intramuscular nerve-dense regions in … DOI 10.1111/joa.13493 · PMID 34176122 | Sihler stain + barium + CT · formalin-fixed adult cadavers | different: acromion - jugular notch (H) and jugular notch - xiphisternal joint (L) surface lines | **partly** | Two nerve-dense regions in pectoralis major and one in pectoralis minor (agrees with the guide's 2+1 count); positions on different lines. [abstract (PubMed)] Used for 2 muscle(s). |
| `page2019` | Page BJ et al. 2019 — The relative location of the major femoral nerve motor branches in the thigh… DOI 10.7759/cureus.3882 · PMID 30899633 | dissection, motor branch entry ratios · 16 specimens · embalmed | different: femoral nerve at inguinal ligament - (distal end per repo record: superior patellar margin) | **partly** | Branch entry points, not IZ. [abstract (PubMed)] Used for 4 muscle(s). |
| `park2007` | Park BK et al. 2007 — Anatomic motor point localization of the biceps brachii and brachialis muscles… DOI 10.3346/jkms.2007.22.3.459 · PMID 17596654 | cadaveric dissection, motor points · 23 limbs / 12 cadavers · adult cadavers (Korea) | line starts at the coracoid process; distal end not stated in the abstract | **partly** | Distal landmark of the line not verifiable from what could be opened. [abstract (PubMed)] Used for 2 muscle(s). |
| `parratte2002` | Parratte B et al. 2002 — Intramuscular distribution of nerves in the human triceps surae muscle: anatomical bases f… DOI 10.1007/s00276-002-0022-9 · PMID 12197026 | macro + stereoscopic microdissection · 40 legs · adult cadavers (France) | % of a standard leg length (values not in abstract) | **partly** | Relevant by design; values not reachable. [abstract (PubMed)] |
| `repo` | This repository's own data/muscles record (motor_endplate_zones) for the muscle; see that file for its source et al.  — …  | repo record · n/a | as stated per entry | **partly** | Prior repo value shown for reconciliation. [repo record] Used for 2 muscle(s). |
| `saitou2000` | Saitou K et al. 2000 — Innervation zones of the upper and lower limb muscles estimated by using multichannel surf… PMID 12696320 | multichannel surface EMG · 3 subjects · healthy | qualitative | **partly** | Confirms narrow bands in parallel-fibred muscles (biceps, VL, VM, TA, soleus, peronei) and scattered IZs in pennate/complex ones (forearm, RF, sartorius, hamstrings, gastrocnemius); no % lines in the abstract. [abstract (PubMed)] |
| `schirmer2011` | Schirmer CM et al. 2011 — Heuristic map of myotomal innervation in humans using direct intraoperative nerve root sti… DOI 10.3171/2011.2.SPINE1068 · PMID 21476796 | intraoperative root stimulation + EMG · 129 patients / 1589 stimulations · spinal surgery | n/a | **partly** | Shows roots supply a broader set of muscles than textbooks; per-muscle map not in the abstract. [abstract (PubMed)] |
| `tang2018` | Tang Y et al. 2018 — Localization of center of intramuscular nerve dense regions in adult anterior brachial mus… PMID 29736215 | Sihler stain + barium marking + spiral CT · 12 cadavers · adult cadavers (China) | body-surface H and L lines whose landmarks are not given in the abstract; PMC full text returned empty | **partly** | Biceps 56.6/67.6% and brachialis 71.3/81.6% on its longitudinal line agree in shape, but the line could not be verified, so not compared numerically. [abstract (PubMed)] Used for 2 muscle(s). |
| `vancamp2011` | Van Campenhout A et al. 2011 — Localization of the motor endplate zone in human skeletal muscles of the lower limb: anato… DOI 10.1111/j.1469-8749.2010.03816.x · PMID 20964675 | review of histological + dissection MEP studies, proposes external-landmark sites · adult + child data pooled from older studies | probably the origin of the lower-limb lines (gastrocnemius, soleus, TP, ST, SM, gracilis, BF, RF, adductors, psoas listed) | **partly** | Highly relevant by design, but the full text (values) could not be opened (publisher host blocked); not used for numbers. [abstract (PubMed)] |
| `wang2020` | Wang et al et al. 2020 — Localization of the center of the intramuscular nerve dense region of the medial femoral m… DOI 10.1016/j.aanat.2020.151529 · PMID 32437866 | Sihler + barium + CT · 12 cadavers · adult (China) | different: greater trochanter - pubic tubercle (H) and a lateral femoral epicondyle line (L) | **partly** | One nerve-dense region each for gracilis, AL, AB and two for adductor magnus (agrees with the guide's AM 2 bands); positions on different lines. [abstract (PubMed)] Used for 1 muscle(s). |
| `xie2013` | Xie P et al. 2012 — The study of intramuscular nerve distribution patterns and relative spindle abundance of t… PMID 23251569 | Sihler + histology · adult cadavers | different: origin-insertion thirds | **partly** | Already in the repo (data/muscles); not comparable with hamate-MC1 line. [repo record] Used for 2 muscle(s). |
| `yi2023gas` | Yi KH et al. 2023 — Intramuscular neural distribution of the gastrocnemius for botulinum neurotoxin injection:… DOI 10.3349/ymj.2023.0124 · PMID 37488703 | modified Sihler stain · 16 specimens · adult cadavers | different: fibular head line - superior margin of calcaneal tuberosity; counting direction not stated in the abstract | **partly** | 7/10-8/10 (medial) and 7.5/10-8.5/10 (lateral) only make anatomical sense counted from the calcaneal end (= 20-30% / 15-25% below the fibular head), which agrees with the guide. [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2025sol` | Yi KH et al. 2026 — Intramuscular neural distribution of the soleus for botulinum neurotoxin injection: applic… DOI 10.1038/s41598-025-07508-2 · PMID 41444715 | modified Sihler stain · 20 specimens · adult cadavers | different: fibular head line - calcaneal tuberosity line, zones 1-10, direction not stated in the abstract | **partly** | Zone 5 (lateral, medial) and zone 3 (middle); not converted because the counting direction is not stated. [abstract (PubMed)] Used for 1 muscle(s). |
| `yi2026vl` | Yi KH et al. 2026 — Intramuscular neural distribution of the vastus lateralis informs effective and safe botul… DOI 10.1038/s41598-026-37960-7 · PMID 41644588 | modified Sihler stain · 12 cadavers · fresh cadavers | different (repo record: greater trochanter - base of patella; not stated in the abstract) | **partly** | [abstract (PubMed)] Used for 1 muscle(s). |
| `zhang2017` | Zhang C et al. 2017 — Imaging three-dimensional innervation zone distribution in muscles from M-wave recordings… DOI 10.1088/1741-2552/aa65dd · PMID 28358718 | high-density surface EMG, 3-D IZ source reconstruction · 6 subjects · healthy adults | different: absolute distance from the medial-epicondyle plane | **partly** | Absolute cm, not a % of a line. [abstract (PubMed)] Used for 1 muscle(s). |
| `zhou2023` | Zhou J et al. 2024 — Localisation of the centre of the highest region of muscle spindle abundance of anterior f… DOI 10.1111/joa.14000 · PMID 38155435 | modified Sihler + histology + CT · 24 cadavers · adult cadavers (China) | different: medial epicondyle - ulnar styloid (L) and epicondylar (H) lines | **partly** | Same forearm, different line (ulnar-side axis vs the guide's epicondylar-to-styloid levels); shown for comparison, never averaged. [abstract (PubMed)] Used for 6 muscle(s). |
| `gracies2009` | Gracies JM et al. 2009 — Botulinum toxin dilution and endplate targeting in spasticity: a double-blind controlled s… PMID 19154823 | RCT · spasticity | n/a | **not relevant** | Efficacy only; no positions. [citation only (PubMed match)] |
| `lapatki2011` | Lapatki BG et al. 2011 — Botulinum toxin has an increased effect when targeted toward the muscle's endplate zone: a… DOI 10.1016/j.clinph.2010.11.018 · PMID 21195024 | HD-sEMG, toxin efficacy vs distance from endplate zone · 8 volunteers · healthy | n/a (extensor digitorum brevis) | **not relevant** | Efficacy evidence only (1 cm away = 46% less effect); no limb-muscle positions. [abstract (PubMed)] |
| `zhang2021` | Zhang C et al. 2021 — Improving botulinum toxin efficiency in treating post-stroke spasticity using 3D innervati… DOI 10.1142/S0129065721500076 · PMID 33438529 | randomised trial, IZ-guided vs standard injection (biceps) · stroke | n/a | **not relevant** | Supports IZ targeting; gives no IZ position (the guide cites it, oddly, for pectoralis minor). [abstract (PubMed)] |
| `barbero2012` | Barbero M et al. 2012 — Atlas of Muscle Innervation Zones…  | surface EMG atlas (book) · healthy | landmark-based lines per muscle (book not opened) | **not used** | Book; not reachable from this session. Do not quote values from memory. [not opened] |
| `christensen1959` | Christensen E et al. 1959 — Topography of terminal motor innervation in striated muscles from stillborn infants… PMID 13637190 | histology · stillborn infants | not available | **not used** | No abstract; infant material; the historical base of later reviews. [citation only] |

### Per-muscle consolidated summary

Full per-field detail (parts, per-source roots, notes, citations) is in the JSON.

| muscle | nerve (registry id) | roots adopted · range | adopted IZ bands (line: %) | other sources on the same / near line |
|---|---|---|---|---|
| Subscapularis | upper_subscapular_n, lower_subscapular_n | C5-C6 · C5-C6 | superior subscapular_guide: qualitative; middle subscapular_guide: qualitative; inferior subscapular_guide: qualitative | — |
| Pectoralis major | lateral_pectoral_n, medial_pectoral_n | C5-T1 · C5-T1 | clavicular_head fascicle: 50; sternal_head fascicle: 50 | diaconu (near) |
| Pectoralis minor | medial_pectoral_n | C8-T1 · C8-T1 | superior_part fascicle: 50; inferior_part fascicle: 50 | diaconu (conflict) |
| Latissimus dorsi | thoracodorsal_n | C6-C8 · C6-C8 | t12_line ld_t12: 50; l4_line ld_l4: 50; iliac_line ld_iliac: 50 | — |
| Teres major | lower_subscapular_n | C5-C7 · C5-C7 | main tm_guide: 50 | yi2023tm (agree) |
| Biceps brachii | musculocutaneous_n | C5-C6 · C5-C6 | short_head coracoid_me: 65; long_head coracoid_me: 65 | lee2009 (agree) |
| Brachialis | musculocutaneous_n | C5-C6 · C5-C6 | medial_part coracoid_me: 75; lateral_part coracoid_me: 75 | lee2009 (agree) |
| Brachioradialis | radial_n | C5-C6 · C5-C6 | main forearm: 20 | — |
| Triceps brachii | radial_n | C6-C8 · C6-C8 | lateral_head acromion_olecranon: 50; long_head acromion_olecranon: 60; medial_head acromion_olecranon: 60 | koo2019 (agree), koo2019 (conflict), yi2023tri (agree), yi2023tri (second_zone) |
| Pronator teres | median_n | C6-C7 · C6-C7 | main forearm: 20 | — |
| Pronator quadratus | anterior_interosseous_n | C8-T1 · C8-T1 | main forearm: 90 | — |
| Flexor carpi radialis | median_n | C6-C7 · C6-C7 | main forearm: 35 | — |
| Palmaris longus | median_n | C7-C8 · C7-C8 | main forearm: 25 | — |
| Flexor carpi ulnaris | ulnar_n | C7-T1 · C7-T1 | ventral_deep_part forearm: 30; dorsal_superficial_part forearm: 50 | — |
| Flexor digitorum superficialis | median_n | C7-T1 · C7-T1 | humeroulnar_head forearm: 30; radial_head forearm: 50 | — |
| Flexor digitorum profundus | anterior_interosseous_n, ulnar_n | C8-T1 · C8-T1 | medial_part forearm: 40; lateral_part forearm: 60 | — |
| Flexor pollicis longus | anterior_interosseous_n | C8-T1 · C8-T1 | band_1 forearm: 50; band_2 forearm: 65 | — |
| Extensor carpi radialis longus | radial_n | C6-C7 · C6-C7 | main forearm: 20 | — |
| Extensor carpi radialis brevis | posterior_interosseous_n | C7-C8 · C6-C8 | main forearm: 40 | — |
| Extensor carpi ulnaris | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 40 | — |
| Extensor digitorum | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 40 | — |
| Extensor digiti minimi | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 60 | — |
| Abductor pollicis longus | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 60 | — |
| Extensor pollicis brevis | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 75 | — |
| Extensor indicis | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 85 | — |
| Extensor pollicis longus | posterior_interosseous_n | C7-C8 · C7-C8 | main forearm: 70 | — |
| Abductor pollicis brevis | median_n_recurrent_thenar_branch | C8-T1 · C8-T1 | main hamate_mc1: 40 | — |
| Opponens pollicis | median_n_recurrent_thenar_branch | C8-T1 · C8-T1 | main hamate_mc1: 60 | — |
| Flexor pollicis brevis | median_n_recurrent_thenar_branch, ulnar_n_deep_branch | C8-T1 · C8-T1 | main hamate_mc1: 60 | — |
| Adductor pollicis | ulnar_n_deep_branch | C8-T1 · C8-T1 | oblique_head hamate_mc1: 50; transverse_head hamate_mc1: 50 | — |
| Lumbricals (hand) | median_n_palmar_digital_nn, ulnar_n_lumbrical_branches | C8-T1 · C8-T1 | main radstyloid_mcheads: 75 | — |
| Palmar interossei | ulnar_n_deep_branch | C8-T1 · C8-T1 | main radstyloid_mcheads: 75 | — |
| Dorsal interossei (hand) | ulnar_n_deep_branch | C8-T1 · C8-T1 | main radstyloid_mcheads: 75; first_dorsal_interosseous fascicle: 50 | — |
| Psoas major | lumbar_root_L1, lumbar_root_L2, lumbar_root_L3 | L1-L3 · L1-L3 | main t12_inguinal: 50 | vancamp2010 (agree) |
| Iliacus | femoral_n_branch_to_iliacus | L2-L4 · L2-L4 | — (guide gives none) | — |
| Piriformis | nerve_to_piriformis | S1-S2 · S1-S2 | — (guide gives none) | — |
| Sartorius | femoral_n | L2-L3 · L2-L3 | band_1 asis_mfe: 25; band_2 asis_mfe: 50; band_3 asis_mfe: 75 | yi2021sar (agree) |
| Adductor longus | obturator_n_anterior_division | L2-L4 · L2-L4 | lateral_portion pubic_mfe: 20; medial_portion pubic_mfe: 35 | kwon2009 (agree) |
| Adductor brevis | obturator_n_anterior_division | L2-L4 · L2-L4 | main pubic_mfe: 20 | kwon2009 (agree) |
| Adductor magnus | obturator_n, obturator_n_branch_to_adductor_magnus_adductor_part, sciatic_n, sciatic_n_branch_to_adductor_magnus_hamstring_part | L2-L4 · L2-L4 | adductor_part pubic_mfe: 20; adductor_part pubic_mfe: 40 | kwon2009 (agree) |
| Gracilis | obturator_n_anterior_division | L2-L3 · L2-L3 | band_1 pubic_mfe: 30; band_2 pubic_mfe: 60 | kwon2009 (agree) |
| Semitendinosus | sciatic_n | L5-S2 · L5-S2 | upper_lateral_compartment it_mfe: 30; lower_medial_compartment it_mfe: 70 | an2010 (agree), rha2016 (agree) |
| Semimembranosus | sciatic_n | L5-S2 · L5-S2 | main it_mfe: 75 | an2010 (agree), rha2016 (agree) |
| Biceps femoris | sciatic_n, sciatic_n_branch_to_biceps_femoris_long_head, sciatic_n_branch_to_biceps_femoris_short_head | L5-S2 · L5-S2 | long_head it_mfe: 50; short_head it_mfe: 80 | an2010 (agree), rha2016 (agree) |
| Rectus femoris | femoral_n | L2-L4 · L2-L4 | proximal asis_patella: 40; distal asis_patella: 60 | diaconu (agree) |
| Vastus intermedius | femoral_n | L2-L4 · L2-L4 | band_1 asis_mfe: 50; band_2 asis_mfe: 65 | — |
| Vastus medialis | femoral_n | L2-L4 · L2-L4 | proximal_lateral asis_patella: 75; distal_medial asis_patella: 85 | yi2024vm (agree) |
| Vastus lateralis | femoral_n | L2-L4 · L2-L4 | proximal_medial asis_patella: 50; distal_lateral asis_patella: 65 | — |
| Gastrocnemius | tibial_n | S1-S2 · S1-S2 | lateral_head popliteal_lm: 20; lateral_head popliteal_lm: 30; medial_head popliteal_lm: 25; medial_head popliteal_lm: 35 | kim2005 (agree) |
| Soleus | tibial_n | S1-S2 · S1-S2 | posterior_part_medial popliteal_lm: 35; posterior_part_medial popliteal_lm: 45; posterior_part_lateral popliteal_lm: 35; posterior_part_lateral popliteal_lm: 45; anterior_part_medial popliteal_lm: 45; anterior_part_lateral popliteal_lm: 45 | kim2005 (agree) |
| Tibialis posterior | tibial_n | L4-L5 · L4-L5 | band_1 fh_lm: 25; band_2 fh_lm: 40 | — |
| Flexor digitorum longus | tibial_n | L5-S1 · L5-S1 | main fh_mm: 65 | diaconu (conflict) |
| Flexor hallucis longus | tibial_n | L5-S2 · L5-S2 | main fh_mm: 65 | diaconu (agree) |
| Tibialis anterior | deep_fibular_n | L4-L5 · L4-L5 | main fh_lm: 35 | yi2016ta (near) |
| Extensor digitorum longus | deep_fibular_n | L5-S1 · L5-S1 | — (guide gives none) | — |
| Extensor hallucis longus | deep_fibular_n | L5-S1 · L5-S1 | main fh_submalleolar: 65 | — |
| Fibularis (peroneus) longus | superficial_fibular_n | L5-S1 · L5-S1 | main fh_lm: 35 | choi2019 (agree), lee2011pl (agree) |
| Fibularis (peroneus) brevis | superficial_fibular_n | L5-S1 · L5-S1 | main fh_lm: 65 | choi2019 (agree), lee2011pl (near) |
| Flexor digitorum brevis | medial_plantar_n | S1-S3 · S1-S3 | main sole_mtp1: 50 | — |
| Flexor hallucis brevis | medial_plantar_n | S1-S3 · S1-S3 | medial_head sole_mtp1: 70; lateral_head sole_mtp1: 70 | — |

## 3. Analysis — how each field was decided

- **Nerve and branch**: the repo registry (`data/muscles/*` innervation + `data/nerves/*`, cited to Gray's for
  Students / Moore / TA). The guide states none. Where a muscle has parts with different nerves the record says so
  per part (FDP medial = ulnar n., lateral = anterior interosseous n.; biceps femoris long head = tibial division,
  short head = common fibular division; adductor magnus adductor part = obturator, hamstring part = sciatic;
  FPB superficial/deep head; lumbricals 1–2 / 3–4).
- **Roots**: adopted = the textbook range from the registry. Clinical sources (ISNCSCI key muscles, Levin 1996,
  Tsao 2003) name the *dominant* root only; they are listed per source and never merged into the adopted range.
  Only one falls outside the textbook range: **ECRB** — registry C7–C8 vs ISNCSCI C6 (wrist extensors) → range
  C6–C8, flagged. Tsao 2003 found biceps femoris *exclusively* S1 in L5/S1 radiculopathy (registry L5–S2):
  inside the range, noted.
- **IZ**: the guide's value is adopted (it is the round's primary source and defines the lines the mode draws).
  Other sources are attached with `same_line` and `agreement`; values on a different line are shown, never
  averaged. Where a reversed line was used (0% at the distal landmark) the converted value is given in the note
  only.

### Agreement found (same or near-same line)

| muscle | guide | independent primary source on the same/near line | verdict |
|---|---|---|---|
| Biceps brachii | 65% coracoid–ME | Lee 2009: densest endings 64.6–70.3% (n=56 arms) | agree |
| Brachialis | 75% | Lee 2009: 75.4% | agree |
| Triceps lateral / medial | 50% / 60% acromion–olecranon | Koo 2019: 54.8 / 60.4%; Yi 2023: 40–70 / 60–70% from acromion | agree |
| Psoas | 50% T12–mid-inguinal | Van Campenhout 2010: 30–70% (n=24) | agree |
| Adductor longus / brevis / magnus / gracilis | 20+35 / 20 / 20+40 / 30+60% | Kwon 2009 motor points 26.0 / 21.0 / 30.4 / 32.1% (n=19) | agree (gracilis 60% guide-only) |
| Semitendinosus / SM / BF long / BF short | 30+70 / 75 / 50 / 80% IT–MFE | An 2010 nerve-ending limits 18.6–36.8 & 56.6–79.1 / 55.9–89.1 / 39.7–72.9 / 58.9–80.2% (n=50) | agree |
| Sartorius | 25 / 50 / 75% ASIS–MFE | Yi 2021: 20–40 & 60–80% | 25, 75 agree; 50 guide-only |
| Vastus medialis | 75 / 85% ASIS–patella | Yi 2024: 50–90% | agree |
| Gastrocnemius / soleus | 20–35% / 35–45% popliteal fold–LM | Kim 2005: 9.6–37.9% / 20.5–46.7% intercondylar–IML (n=8) | agree |
| Fibularis longus / brevis | 35 / 65% FH–LM | Lee 2011 entry points 20–40 / 40–60%; Choi 2019 densest quarter 25–50 / 50–75% | agree |
| Teres major | midpoint | Yi 2023: middle 20% of the muscle | agree |

### Conflicts and how they were resolved

| muscle | conflict | resolution |
|---|---|---|
| Triceps long head | guide 60% vs Koo 2019 43.8% (near-same line); Yi 2023 finds two long-head zones (50–70% and 30–40% from the acromion) | guide adopted; Yi's proximal zone shown as an "other source" band |
| Tibialis anterior | guide 35% vs Yi 2016 densest arborisation 20–30% from the fibular head (same line) | guide adopted, Yi shown; ~5% of leg length apart |
| Pectoralis minor | guide mid-fascicle vs repo record 75% origin→insertion (secondary) | guide adopted; both weakly sourced |
| Sartorius middle band, gracilis distal band | guide-only (not found by same-line cadaver studies) | kept, marked guide-only in `conflicts[]` |
| FDL / FHL line | table FH–LM vs text FH–MM | text adopted |
| Gastrocnemius / soleus line | table "IML" vs text "inferior margin of the LM" | text adopted; `popliteal_iml` kept |
| ECRB roots | registry C7–C8 vs ISNCSCI C6 | range C6–C8 shown, adopted unchanged |

### Problems found in the repo's own data (reported, not edited — out of this round's scope)

1. `data/muscles/upper_limb/triceps_brachii_{l,r}.json`: lateral head 30–40% and medial head 30–60%
   (via the Diaconu review). The primary paper (Yi 2023 abstract) gives **medial 30–40%, lateral 30–60%** —
   the heads look swapped. (The private motor-points layer has them the right way round.)
2. `data/muscles/lower_limb/gastrocnemius_{l,r}.json`: 75% (medial) / 80% (lateral) "intercondylar →
   intermalleolar line" contradicts the guide, Kim 2005 and Yi 2023; almost certainly counted from the
   calcaneal end (Yi's 7/10–8/10 sections) and stored with the wrong direction.
3. The median nerve **trunk** (`median_n`) is not a structure on either Base page (only `median_n_lateral_root`
   and `zan_muscular_branches_of_median_nerve`), so "click a nerve → its muscles" for the median nerve has to
   start from its branches. Likewise `radial_n_deep_branch` is not in the registry (the page has
   `posterior_interosseous_n` / `zan_posterior_interosseous_nerve_of_forearm`).
4. Registry id `median_n_recurrent_thenar_branch` ≠ page id `recurrent_branch_of_median_n`; the JSON records
   both (`nerve[]` = registry, `nerve_structures_on_page` = page).

## 4. Coverage

- 60 muscle records (33 upper, 27 lower), all mapped to structure ids on **both** Base pages (0 unmapped).
  Page-id mapping notes: pectoralis major → the three `zan_*_pectoralis_major_muscle` parts (no whole-muscle id);
  triceps → the three `zan_*_head_of_triceps_brachii`; FDS → `flexor_digitorum_superficialis` +
  `zan_humero_ulnar_head_of_flexor_digitorum_superficialis`; palmaris longus, EPL, lumbricals, psoas, iliacus,
  tibialis posterior → their `zan_*` ids; the 1st dorsal interosseous is part of `dorsal_interossei_hand`;
  biceps femoris is one structure carrying both heads.
- 94 IZ bands; 56 muscles with a numeric IZ; 21 muscles have at least one independent source on the same or a
  near-same line; 38 comparisons agree, 4 near, 4 conflict, 1 second zone, 33 not comparable (different line).
- 49 sources in the table: 19 relevant, 25 partly, 3 not relevant, 2 not used. About 85 PubMed abstracts screened.
- 51 landmarks declared (38 needed for the guide's own bands, the rest for comparison lines).

## 5. Public / private split

| goes to | what |
|---|---|
| `data/anatomy/innervation_q322.json` (public) | nerve, branch, part-nerves, roots (with per-source evidence), IZ position as % along a named landmark line, number of IZ bands, heads/compartments, landmarks, lines, sources, conflicts |
| `clinical/data/innervation_injection_q322.json` (private, owner's licence, same keys) | number of injection points and per-site counts (Tables I–II "Number"), scan start, positioning / passive manoeuvres, structures at risk, the guide's "seeding" technique note |

The public file contains none of the terms the public templates must not carry (tested), and no injection
vocabulary in its muscle records (tested). The one source whose title contains such a term is cited by PMID with
the title withheld.

## 6. Design proposal — MUSCLE INNERVATION mode (for the next agent)

**What the user sees**
- A fourth workspace mode (key e.g. `inn`) in the mode switcher. Bones + muscles of the limbs shown; trunk and
  skin faded.
- A colour-by control: **by nerve** (one hue per nerve trunk; branches inherit the trunk's hue — use
  `nerve[].parent` up to the trunk) or **by root level** (C5…T1, L1…S2 ramp; a muscle with several roots shows
  its *adopted* range as a striped/two-tone legend chip in the card, the mesh coloured by the middle root, with
  the rule stated in the legend). Muscles without a record stay neutral grey.
- **Click a nerve** (or a legend chip) → mark all its muscles (and its page nerve structures), others faded.
- **Click a muscle** → card: nerve › branch, part-nerves, roots (adopted + range + per-source chips), IZ bands
  listed per part with line ("ASIS → patella, 40%"), agreement badges, conflicts, citations. "Show IZ" draws the
  bands on the muscle.
- IZ bands are drawn as **rule-based markers**: a thin ring (band) where the plane at the stated level cuts the
  muscle, plus a small dot at the section centroid; "other source" bands dashed, only on request. Every marker
  carries the badge "Rule-based: % of <line> from <guide/cite>; landmarks measured on this body's bones".
  Qualitative sites (subscapularis) are shown as labelled thirds of the line, no dot.

**Modules to reuse**
- `viewer/modes/modes.js` — register a provider `NMSKModes.register('inn', {title, short, build, enter, exit})`;
  add `inn` to `MODES` and the hash regex; the controller already snapshots/restores the anatomy screen.
  It must stay generic and name nothing private (the public mode reads only the public JSON).
- `viewer/selection` — marking, show-only, fade, `hl` colour for nerve/muscle groups.
- `viewer/q303` (nerves.js, nervepass.js) — the nerve emphasis pass so thin branches stay visible when a nerve
  is selected.
- `viewer/quickcard` — the click card; the innervation card is a section of it / its "More…" panel.
- `data/anatomy/relations_q298.json` — could gain a "same nerve" related-kind from this file.
- Placement code: the landmark finders already exist in the private `scripts/clinical/motor_points_q187.py`
  (`Body.lm_*`: acromion, coracoid, epicondyles, olecranon, ulnar styloid, ASIS, pubic tubercle, ischial
  tuberosity, mid-inguinal, femoral epicondyles, patella base, fibular head, malleoli, T12…) and its `section()`
  level-placement. Bony landmarks are anatomy, not clinical: the proposal is to **move the landmark finders
  (not the clinical rules) into a public build script** that writes per-page landmark coordinates, and add the
  missing ones (radial styloid, hook of hamate, MC1/MC2/MC5 heads, MTP1, sole posteroinferior point, scapular
  inferior angle and spine root, T12/L4 spinous, iliac crest top, posterior axillary fold proxy, popliteal fold
  proxy).

**How an IZ point is placed on each Base body (build time, not in the browser)**
1. For each landmark in `landmarks_needed_for_guide_iz`, measure it on that page's own bone mesh (extreme
   vertex along an anatomical axis, as `motor_points_q187.py` does); `derived` = midpoint of its two `of`
   points; `soft_tissue` = the proxy written in its definition (badge says "proxy"); `muscle_derived` = the
   muscle mesh's ends along its principal axis.
2. P = from + pct/100 × (to − from), on the side's own landmarks (left and right separately).
3. `mode: level` → plane through P perpendicular to the line; intersect the muscle (or the part's structure)
   → the band = cross-section outline, the dot = its centroid; if the plane misses the muscle by > 5 mm record
   FAILED and draw nothing (as Q187 does). `mode: point` → P snapped to the nearest point inside the muscle.
4. Store per page: `{muscle, part, band_index, side, centroid, outline (decimated), line_len_mm, status}` in a
   public derived JSON (e.g. `data/derived/Q322_iz_bands_<page>.json`), inlined at regen like other layers.
   The mode draws from it; nothing is computed from clinical files.
5. Test: every placed dot inside its muscle mesh (winding number, as `tests/test_motor_points_q187.py`), band
   level within 1 mm of the stated %, both sides placed.

**Badge text (card and marker)**: "Innervation zone — rule-based. Level = <pct>% of <from> → <to> (Güvener et
al. 2026, Table I/II), measured on this body's own bones. Other sources: <agree/conflict chips>."

**Do not**: show injection counts, needle or probe information in the public mode; average sources with different
lines; place markers on frozen pages.

## 7. Open items

- Open the full texts that were blocked (Van Campenhout 2011; Kara 2018 / Kaymak 2018; Beretta-Piccoli 2014;
  Barbero atlas) if the owner allows those hosts — they would add independent values for the forearm and hand,
  where only differently-lined studies were reachable.
- Fix the two repo records (§3) in a separate round, with the owner's go-ahead.
