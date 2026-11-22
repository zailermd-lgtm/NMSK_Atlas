# Q348 — reference pass over the open questions with the owner's anatomy books

Owner (2026-11-16): new anatomy files in Dropbox, to be used for the completions and corrections that are needed; the books
are his. Use rule (same as for Sobotta): **knowledge only** — the books are read to establish facts, each fact is cited with
book and page; no prose or figures are copied into the repo, data or pages; no figure is traced into geometry. The PDFs and
every text/OCR dump stay in the session scratchpad, outside the repo. Scope: the two Base pages only; no regen, no publish.

Generators changed (the JSONs stay reproducible): `scripts/anatomy/q342/books_q348.py` (new: the book facts, per muscle /
part / variation, with printed pages), `gen_lines.py`, `gen_innervation.py`, `gen_parts.py`, `scripts/anatomy/q336/records_q336.py`.
The generator inputs `ids.json` and `rec2mesh.json` (page-manifest id lists that were only in the scratchpad) now sit beside the
generators, so `python3 gen_*.py` in `scripts/anatomy/q342/` reproduces the committed files byte for byte before this round's edits.

## 1. The nine files

| file | title | authors / editors | edition, year, publisher | ISBN | pages | layer | use here |
|---|---|---|---|---|---|---|---|
| grays_atlas_of_anatomy.pdf | Gray's Atlas of Anatomy | Drake, Vogl, Mitchell et al. (series authors; not printed in the scan) | Churchill Livingstone / Elsevier; edition and year **not in the scan** (no title or copyright page); printed pages reach 414+ in a 403-page scan, so it is a partial copy | — | 403 | scanned (OCR'd in the scratchpad) | labelled plates: perineum (deep pouch p. 245, perineal vessels and nerves p. 252), palm (superficial arteries and nerves p. 414); clinically important nerve roots (p. 34) |
| lumley_surface_anatomy.pdf | Surface Anatomy: The Anatomical Basis of Clinical Examination | Lumley JSP | 4th ed., Churchill Livingstone / Elsevier; year not legible in the scan | — | 136 | scanned (OCR) | surface landmarks: axillary walls p. 39, midinguinal point p. 45 / 49, supracristal plane p. 46 |
| mannan_regional_dissection_surface_anatomy.pdf | Mannan's Regional Dissection and Surface Anatomy | Noor MA | 14th ed., 2017 (1st ed. 1959), Jaypee Brothers, New Delhi | 978-93-86322-11-1 | 648 | text | per-muscle origin, insertion and nerve supply **with root values** (whole body); perineum; palm layers; surface marking |
| yogesh_anatomy_vol5_6.pdf | Textbook of Human Anatomy with Color Atlas and Clinical Integration, Vol. 5 Head, Neck and Face (+ Vol. 6 Brain) | Sontakke YA | 1st e-book ed. 2023, CBS Publishers, New Delhi (several tables cite Gray's Anatomy 42nd ed.) | e-ISBN not printed ("xxxx") | 635 | text | muscle tables with nerve supply and root values for neck, back, suboccipital, prevertebral, scalene, infrahyoid, mastication, pharynx, middle ear |
| fascia_in_sport_and_movement.pdf | Fascia in Sport and Movement | Schleip R, Baker A (eds); ch. 6 by Myers T; ch. 7 by Richter P | 1st ed. 2015, Handspring Publishing, Pencaitland | 978-1-909141-07-0 (eISBN 978-1-909141-42-1) | 474 | text (calibre e-book: **no printed page numbers** — cited by PDF page) | myofascial lines (Myers' chapter), Tittel / Busquet muscle chains (Table 7.1) |
| peripheral_nerve_injury_anatomical.pdf | Peripheral Nerve Injury: An Anatomical and Physiological Approach for Physical Therapy Intervention | Carp SJ | 2015, F. A. Davis, Philadelphia (LCCN 2015935849) | not printed in the front matter | 384 | text | pathology / rehabilitation; **no muscle root tables** — not cited per muscle |
| pns_interrelationships_variations.pdf | Peripheral Nervous System: Interrelationships and Variations | Haviarová Z, Matejčík V, Kuruc R | 2024, Springer Nature Switzerland | 978-3-031-73743-5 (eBook 978-3-031-73744-2), doi 10.1007/978-3-031-73744-2 | 181 | text | plexus variations from a 50-cadaver dissection series (prefixed / postfixed plexus, terminal-branch variants) |
| peripheral_nerves.pdf | Musculoskeletal Ultrasound Examination, Part III: Peripheral Nerves | Wang T-G, Chen W-S (eds), Wu C-H (exec. ed.) | edition, year, publisher and ISBN not in the scan | — | 185 | scanned (OCR) | a scanning-technique handbook; no fact was taken from it (the anatomy it gives is covered by the text books). Not cited in any public data file |
| atlas_untitled.pdf | Atlas of Practical Neonatal and Pediatric Procedures | Jain P, Pant D, Sood J | 1st ed. 2013, Jaypee Brothers | 978-93-5025-772-2 | 173 | text | **not relevant** to this adult musculoskeletal atlas — catalogued, not read |

## 2. Findings

### 2.1 Myofascial lines (`myofascial_lines_q342.json`)
| topic | repo before | book | page | action |
|---|---|---|---|---|
| number of lines | 12 Myers lines recorded from recall | 12 meridians "of at least three muscles each" | Myers 2015, PDF p. 93 | confirmed; set kept |
| SBL | route from recall | course toes → face (Fig. 6.1); hamstrings → superficial sacrotuberous ligament → thoracolumbar back myofascia | PDF pp. 94, 108 | `book_check` partly_confirmed |
| SFL | route from recall | anterior surface; trunk flexion with leg extension (caption only) | PDF p. 95 | course_only |
| Lateral Line | IT tract station = TFL + gluteus maximus | fibularis longus → over the fibular head → central IT tract → **gluteus medius aponeurosis** → iliac crest; LCL lies deep to the line | PDF pp. 96, 106 | **gluteus medius added** to the station |
| Spiral Line | sides S/O "part of the book description (verify)" | tibialis anterior → anterior IT tract → TFL → ASIS; ASIS → internal oblique → contralateral external oblique + serratus anterior → contralateral scapula → head on the ASIS side | PDF pp. 101-102, 106 | side scheme confirmed; lower posterior half not described |
| Deep Front Line | no medial-knee station | DFL tissues on the inside of the knee: pes anserinus down to the medial collateral ligament; course inner arch → underside of the skull | PDF pp. 100, 109 | **tibial (medial) collateral ligament station added** (pes anserinus tendons not added — not assigned to a line) |
| 4 arm lines, BFL, FFL | from recall | figures only (unlabelled) | PDF pp. 98-99 | course_only |
| Ipsilateral FL | "lower confidence, later edition" | three functional lines, one ipsilateral, exist (2015) | PDF p. 99 | existence confirmed; stations still unchecked |
| verify_against_book flag | true on all 12 | the chapter lists **no station list** for any line | — | **flag kept on all 12** (cleared on none); `book_check` records what is confirmed |
| "horizontal" | not offered | no horizontal line in Myers' chapter or Richter's chapter; limb retinacula mentioned only as obliquely running fascial bands rich in sensory endings, not as a set | PDF pp. 75, 93, 127 | **stays disabled**; `why` updated with this evidence |
| Tittel slings (new) | — | three slings "in side bending and rotation": rhomboids–serratus anterior–external oblique–opposite adductors–biceps femoris short head–fibulars; pectoralis major–internal oblique–TFL–tibialis anterior (opposite leg); latissimus–gluteus maximus–IT tract–tibialis anterior (opposite leg) | Richter 2015, Table 7.1, PDF p. 127 | **added as 3 lines** (class diagonal/spiral, family `tittel`, evidence "not examined"; the side of the trunk muscle at the crossing is not stated → both sides). Tittel's static shoulder slings not added: the table and the text list them differently (PDF pp. 127-128) |

### 2.2 Innervation (`innervation_groups_q342.json`)
Each muscle the books describe now has `book_check_q348` {status, entries[] (book, printed page, nerve, levels)}; where the
books differ the range is written into `roots_range_across_sources` (adopted range unchanged, so root-family membership is
unchanged except the one correction below). 151 of 214 muscles checked: **105 agree, 33 differ, 13 nerve named without levels**.
Of the 154 "repo textbook only" muscles: 91 checked (60 agree, 22 differ, 9 nerve only); 63 unchecked (listed in
`counts.repo_only_unchecked`: mostly face, tongue, eye, larynx and the deep back muscles, for which the books give the cranial
nerve or "dorsal rami" only, or which were not reached).

| topic | repo | book | page | action |
|---|---|---|---|---|
| serratus posterior superior | T1-T4 | 2nd-5th intercostal nerves | Mannan p. 407 | **corrected to T2-T5** (`corrected_q348`) |
| pectoralis minor | medial pectoral n., C8-T1 | lateral **and** medial pectoral nn., C6-C8 | Mannan p. 106 | range C6-T1 recorded; nerve variance reported |
| supinator | C6-C7 (mainly C6) | C5-C6 | Mannan p. 157 | range recorded |
| supraspinatus | C5-C6 | C4-C6 | Mannan p. 193 | range recorded |
| anconeus / brachioradialis / FCU / teres major | C7-C8 / C5-C6 / C7-T1 / C5-C7 | C7-T1 / C5-C7 / C7-C8 / C6-C7 | Mannan pp. 155, 140, 143, 111 | ranges recorded |
| long toe flexors, foot intrinsics | L5-S1/L5-S2; S1-S3 | S2-S3 (FDL, FHL and every intrinsic foot muscle) | Mannan pp. 265-291 | ranges recorded — a textbook tradition difference, not an error |
| gluteus medius / minimus, gemelli, obturator internus, quadratus femoris, plantaris, iliacus | L4-S1 etc. | L5-S1 etc. | Mannan pp. 212, 235-236, 264 | ranges recorded |
| splenius capitis | C3-C4 | C4-C6 (Mannan) vs C2-C3 (Sontakke) — the two books disagree | Mannan p. 86; Sontakke p. 219 | range C2-C6 recorded |
| levatores costarum | C8-T11 dorsal rami | T1-T12 posterior rami | Sontakke p. 222 | range recorded |
| rectus capitis anterior | C1-C2 | C1 | Sontakke p. 207 | range recorded |
| quadratus lumborum / rectus abdominis | T12-L3 / T7-T12 | T12-L4 / lower six or seven thoracic | Mannan pp. 338, 310 | ranges recorded |
| foot interossei | deep branch of the lateral plantar n. only | 3rd plantar and 4th dorsal interosseous by its **superficial** branch | Mannan pp. 291, 295 | recorded in the entries; nerve list not changed (proposal) |
| intertransversarii | dorsal rami (anterior cervical set ventral) | anterior rami (as tabulated for colli and lumborum) | Sontakke p. 222 | recorded as nerve-only |

Variations (`variations_q348`, Haviarová 2024, each linked to nerves and affected muscles): prefixed brachial plexus 2/50 (4 %;
C4 contributes to suprascapular / axillary nerves; a C5 root injury then also weakens brachioradialis, supinator, pronator teres;
pp. 15, 24); postfixed 1/50 (2 %; T1 carries C8's usual fibres, T1 partly supplies triceps; p. 15, 25); musculocutaneous–median
fusion / communication and absent musculocutaneous nerve (8 cases) (Table 7.1, pp. 42, 44); median nerve formed by cord
contributions or only in the lower arm (pp. 42, 44); radial→ulnar communication and cord branches to the ulnar nerve (Table 7.2,
p. 42); prefixed / postfixed lumbosacral plexus and the pudendal root shift (pp. 15, 56, 69); accessory ilioinguinal / femoral /
obturator nerves (pp. 56, 64); high sciatic division in the pelvis 2/50 (p. 69). The book has no Martin-Gruber / Riche-Cannieu
section by name.

Central patterns (Hefter II and V, lower-limb flexion synergy): **no muscle-level source in any of these books** — unchanged.

### 2.3 Hand (palm and fingers)
| fact | source |
|---|---|
| Superficial palmar arch — anterior (superficial) to it: skin, superficial fascia, palmaris brevis, central palmar aponeurosis, palmar cutaneous branches of the median and ulnar nerves; posterior (deep) to it: flexor and opponens digiti minimi, the branches of the median nerve, the FDS and FDP tendons, the lumbricals. It is accompanied by venae comitantes. | Mannan p. 166; Gray's Atlas p. 414 (arch drawn over the common palmar digital nerves and the flexor tendons) |
| Common palmar digital arteries run between the flexor tendons, superficial to the digital nerves and the 2nd-4th lumbricals. | Mannan p. 166 |
| In the palm the digital nerves lie deep to the digital arteries; on the sides of the fingers the nerves lie superficial (palmar) to the arteries; they cross at the roots of the fingers. The digital nerves divide slightly proximal to the arteries. | Mannan pp. 166, 168 |
| Toes: the plantar digital arteries lie dorsal to the nerves. | Mannan p. 291 |
| Palmar venous network drains to the median antebrachial vein (no superficial palmar venous "arch" with its own layer is described). | Mannan pp. 137, 182 |

Q340 (arch and common digital arteries above the flexor tendons) agrees with the book. **Honest rule for the Base bodies** (not
applied): distal to the finger roots (web / MCP level) the proper palmar digital nerve lies palmar to the proper palmar digital
artery; proximal to it, in the palm, the common digital nerve lies dorsal to the common digital artery; the crossing is at the
finger root. The venous arch beside the superficial palmar arterial arch is its venae comitantes, i.e. it belongs at the arterial
arch's depth (superficial to the median-nerve branches and the flexor tendons).

### 2.4 Perineum (`docs/Q336_genital_region.md` §2, `records_q336.py`)
Checklist verified per sex — male (Mannan pp. 353-358; Gray's Atlas p. 245): superficial pouch = ischiocavernosus,
bulbospongiosus, superficial transverse perineal, posterior scrotal vessels and nerves, perineal branch of the posterior femoral
cutaneous nerve, root of the penis (bulb, crura); perineal membrane = inferior fascia of the urogenital diaphragm, pierced by the
urethra, bulb vessels and nerves, bulbourethral ducts, deep / dorsal arteries and dorsal nerves of the penis, perineal artery;
deep pouch = sphincter urethrae, deep transverse perineal, membranous urethra, artery of the penis, dorsal nerves, bulbourethral
glands, venous plexus. Female (Mannan pp. 364-368; Gray's Atlas pp. 245, 252): superficial pouch = crura of the clitoris, bulbs of
the vestibule, greater vestibular glands, the three superficial muscles, posterior labial vessels and nerves, perineal branch of
the posterior femoral cutaneous nerve; deep pouch = sphincter urethrae (Gray's Atlas: external urethral sphincter, **compressor
urethrae, sphincter urethrovaginalis**), deep transverse perineal, lower vagina and urethra, arteries of the clitoris, nerves and
arteries of the bulbs, dorsal nerves of the clitoris. Perineal body: external anal sphincter, bulbospongiosus, superficial and deep
transverse perineals, sphincter urethrae fibres, anterior levator ani fibres meet there (Mannan pp. 354-355). Pudendal canal =
tunnel between the obturator fascia and the lunate fascia; contents internal pudendal vessels and the pudendal nerve dividing
into the perineal nerve and the dorsal nerve of the penis / clitoris (Mannan pp. 347-348). Perineal nerve = larger terminal branch,
giving posterior scrotal / labial and muscular branches (p. 348). The checklist's rows are confirmed; nothing in it is wrong.

Records corrected (records_q336.py → `synonyms_q306.json`): **Perineal membrane** — "urogenital diaphragm" is searchable there but
is not a synonym (the membrane is its inferior fascia; Mannan pp. 357-358); **Perineal nerve** — "posterior scrotal / labial nerve"
are its superficial branches, not other names (p. 348); **Cremaster** — nerve root values L1-L2 added (p. 321). Sources
`mannan2017`, `grays_atlas` added.

### 2.5 Surface landmarks (innervation_q322 `landmarks`) — report only
| landmark | repo definition | book | page |
|---|---|---|---|
| posterior axillary fold | skin fold over the lower border of latissimus dorsi / teres major | formed by the folded lower border of latissimus dorsi and the underlying teres major (anterior fold = lower border of pectoralis major); latissimus lies behind teres major and curves round its lower border | Mannan p. 122; Lumley p. 39 |
| inguinal_ligament_mid | midpoint ASIS – pubic tubercle | "middle of the inguinal ligament" (deep ring ~1 cm above it) is distinct from the **midinguinal point** = midway ASIS – pubic symphysis (femoral artery) | Lumley pp. 45, 49 |
| iliac_crest_top | highest point of the crest | the line joining the crests passes between the L3 and L4 spines, often across L4 — a level check for the point | Lumley p. 46 |
| lateral malleolus tip / "inferior margin" | most distal point | the tip lies about ¼ inch below the medial malleolus tip; the fibular (peroneal) tubercle about ¾ inch below the lateral malleolus tip | Mannan p. 542 |
| popliteal fold / crease | proxy at the knee-joint level | **not defined** in Lumley or Mannan (the fossa is described, not the crease) | — |
| latissimus iliac line | axillary fold → highest point of the crest | latissimus arises from the **posterior part of the outer lip** of the iliac crest | Mannan p. 121 |

### 2.6 Muscle parts (`muscle_parts_q342.json`)
15 parts gain `book_q348`; 11 move from `unverified_textbook` to **`verified_book`** (attachment and/or nerve read): trapezius
×3 (insertions per fibre group, Mannan p. 92 — the rule's insertion boundaries agree; its origin split at C7 / T3-T4 is **not** in
the book), sternocleidomastoid heads (pp. 76-77), soleus heads (p. 263), pronator teres heads (p. 140), FDP halves by nerve (p. 146).
Serratus anterior: the book groups the insertions 1 / 2-4 / lower 4-5 digitations, **different** from the recorded parts
(1-2 / 2-3 / 4-9) — noted, status unchanged. Latissimus iliac part: origin = posterior outer lip of the crest (p. 121). **No body
status changed**: no book gives a boundary on the muscle body that is not already in a rule; the 38 "not delimitable" parts stay so
and the 19 "rule" parts stay unvalidated.

### 2.7 Contradictions with displayed facts
1. Serratus posterior superior roots T1-T4 → book T2-T5 (corrected in innervation groups). **The muscle record**
   `data/muscles/trunk/serratus_posterior_superior_{r,l}.json` still says T1-T4 and lists intercostal nerves T1-T11 (T7-T11 belong
   to the inferior muscle) — not edited (records carry private fields; proposal for the main thread).
2. Pectoralis minor nerve: record = medial pectoral only; Mannan = both pectoral nerves (C6-C8).
3. Foot interossei: record nerve = deep branch of the lateral plantar nerve only; Mannan gives one plantar and one dorsal
   interosseous to its superficial branch.
4. Perineal membrane / perineal nerve synonyms (corrected).
5. Lateral Line missing gluteus medius; DFL missing the medial knee (corrected).
6. Serratus anterior part grouping differs from the book (noted).
7. Book errors seen and not used: Mannan adductor magnus root values printed as sacral (p. 223); Fascia in Sport and Movement
   PDF p. 75 calls the lacertus fibrosus an extension of "biceps femoris" (biceps brachii meant).

## 3. Findings that would change geometry or placements (not applied — for the main thread)
1. Finger nerve/artery order (§2.3): proper palmar digital nerve palmar to the artery distal to the finger root; common digital
   nerve dorsal to the common digital artery in the palm; crossing at the finger root.
2. Superficial palmar venous arch = venae comitantes of the arterial arch → same depth as the arch (Q340 left it unlifted).
3. Latissimus iliac IZ line: end at the latissimus origin on the posterior outer lip of the crest, not the highest crest point.
4. iliac_crest_top: check its level against the L3/L4 interspinous level (Lumley p. 46).
5. DFL station "tibial collateral ligament" and LL station "gluteus medius" change what a line marks on the page (data only).
6. Three new Tittel lines appear in the Myofascial lines menu at the next regen (sidecar count 15 → 18; test updated).

## 4. What the books could not answer
- Station lists of the 12 Myers lines (the chapter gives course, end points and a few transitions only) → `verify_against_book` stays.
- A sourced set of horizontal bands with named structures → "horizontal" stays disabled.
- Hefter patterns II and V, lower-limb flexion synergy: no muscle-level source.
- Root values for the facial, tongue, eye, laryngeal muscles beyond the cranial nerve; segmental levels of the transversospinal muscles.
- A definition of the popliteal crease; the teres major IZ band still has only the fold definition (no new placement rule).
- Boundaries for the 38 non-delimitable parts (layers, compartments, VMO/VML, gluteus medius thirds, masseter / temporalis layers).
- Edition / year of the two scanned Elsevier books and of the imaging handbook (front matter missing in the scans).
