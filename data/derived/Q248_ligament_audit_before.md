# Q248 ligament audit (six pages against a reference checklist)

Reference: Terminologia Anatomica (items named by TA / Latin terms), Gray's Anatomy 1918 (public domain) and standard anatomy; the checklist is `scripts/anatomy/q248/checklist.py` (135 items; sex-specific items count only on the matching sex). A structure counts when its id / name matches the item (regex in the checklist); an item whose structure stands for several items (one glenohumeral complex for SGHL/MGHL/IGHL, one coracoclavicular ligament for conoid + trapezoid, ...) is counted present for each and marked 'grouped'. BEFORE = the six page dirs of Q244 (`build/q244`); AFTER = the Q248 page dirs (`build/q248`).

## 1. Counts per page (present / one side only / missing; items that do not apply to the sex excluded)

| Page | present | one side | missing | applicable |
|---|---|---|---|---|
| Imaging-based F | 13 | 6 | 114 | 133 |
| Combined F | 99 | 0 | 34 | 133 |
| Base F | 99 | 0 | 34 | 133 |
| Imaging-based M | 6 | 5 | 118 | 129 |
| Combined M | 93 | 0 | 36 | 129 |
| Base M | 93 | 0 | 36 | 129 |

Ligament-like entries on the page (class ligament / joint / fascia / tendon): Imaging-based F 43, Combined F 403, Base F 401, Imaging-based M 22, Combined M 386, Base M 386.

### Per group (present / applicable; BEFORE)

| Group | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Pelvic floor and perineum | 6/16 | 7/16 | 7/16 | 0/12 | 1/12 | 1/12 |
| Pelvic girdle (bony ligaments) | 0/18 | 12/18 | 12/18 | 0/18 | 12/18 | 12/18 |
| Spine | 0/14 | 10/14 | 10/14 | 0/14 | 10/14 | 10/14 |
| Hip | 0/7 | 7/7 | 7/7 | 0/7 | 7/7 | 7/7 |
| Knee | 4/17 | 11/17 | 11/17 | 4/17 | 11/17 | 11/17 |
| Ankle and foot | 0/23 | 22/23 | 22/23 | 0/23 | 22/23 | 22/23 |
| Shoulder | 3/11 | 9/11 | 9/11 | 2/11 | 9/11 | 9/11 |
| Thorax | 0/5 | 2/5 | 2/5 | 0/5 | 2/5 | 2/5 |
| Elbow | 0/6 | 4/6 | 4/6 | 0/6 | 4/6 | 4/6 |
| Wrist and hand | 0/16 | 15/16 | 15/16 | 0/16 | 15/16 | 15/16 |

## 2. How the ligaments present on each page were derived (class ligament / joint entries)

| Page | derivation: count |
|---|---|
| Imaging-based F | HRA 17, transferred (VH m<->f) 8, measured/CT 3, mirrored 1 |
| Combined F | Z-fitted 342 |
| Base F | Z (Base) 340 |
| Imaging-based M | measured/CT 9, mirrored 1 |
| Combined M | Z-fitted 325 |
| Base M | Z (Base) 325 |

Legend: measured/CT = segmented / measured on the body (also the Visible Human DU lower-extremity release); Z-fitted = Z-Anatomy structure fitted to the Combined body (CC BY-SA 4.0); Z (Base) = Z-Anatomy structure of the Base model; Z-filled = Z-Anatomy structure carried onto the own bones one bone at a time (earlier passes) or, `(Q248)`, by the Q248 carrier-bone fit; HRA = HuBMAP reference object registered on the body (CC BY 4.0); CVH = Chinese Visible Human (Wu 2015) registered; rule-based = built from bone landmarks by a documented rule; mirrored = mirror of the opposite side; transferred = other Visible Human.

## 3. Checklist matrix (status / sides / derivation); rows in relevance order (pelvic floor first)

Status: `+` present, `1` one side only, `-` missing, `n/a` not for this sex.  Sides: l r m.

### Pelvic floor and perineum

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Tendinous arch of levator ani (arcus tendineus musculi levatoris ani) | - | - | - | - | - | - |
| Arcus tendineus fasciae pelvis (tendinous arch of pelvic fascia) | - | - | - | - | - | - |
| Perineal membrane (urogenital diaphragm, inferior fascia) | - | - | - | - | - | - |
| Transverse perineal ligament (of the pelvis) | - | - | - | - | - | - |
| Anococcygeal ligament / raphe | - | - | - | - | - | - |
| Pubococcygeal and puboperineal components (levator ani) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Pubovesical / puboprostatic / pubourethral ligaments | - | - | - | - | - | - |
| Uterosacral ligament | + lr HRA | + lr Z-fitted | + lr Z (Base) | n/a | n/a | n/a |
| Cardinal (transverse cervical, Mackenrodt) ligament | + lr HRA | + lr Z-fitted | + lr Z (Base) | n/a | n/a | n/a |
| Round ligament of the uterus | + lr HRA | + lr Z-fitted | + lr Z (Base) | n/a | n/a | n/a |
| Broad ligament of the uterus | + m HRA | + m Z-fitted | + m Z (Base) | n/a | n/a | n/a |
| Ligament of the ovary (proper ovarian) | + lr HRA | + lr Z-fitted | + lr Z (Base) | n/a | n/a | n/a |
| Suspensory ligament of the ovary | + lr HRA | + lr Z-fitted | + lr Z (Base) | n/a | n/a | n/a |
| Lateral vesical / lateral rectal ligaments | - | - | - | - | - | - |
| Lateral umbilical ligament (obliterated umbilical artery) | - | - | - | - | - | - |
| Median umbilical ligament (urachus) | - | - | - | - | - | - |
| Suspensory ligament of the penis | n/a | n/a | n/a | - | - | - |
| Fundiform ligament of the penis | n/a | n/a | n/a | - | - | - |

### Pelvic girdle (bony ligaments)

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Sacrospinous ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Sacrotuberous ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Falciform process of the sacrotuberous ligament | - | - | - | - | - | - |
| Iliolumbar ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Lumbosacral ligament (lateral lumbosacral, L5-sacral ala) | - | - | - | - | - | - |
| Anterior sacroiliac ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Posterior sacroiliac ligaments (short) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Interosseous sacroiliac ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Long dorsal sacroiliac ligament | - | - | - | - | - | - |
| Sacrococcygeal ligaments (anterior, posterior, lateral) | - | - | - | - | - | - |
| Sacrococcygeal symphysis (joint disc) | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Arcuate pubic (inferior / subpubic) ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Superior pubic ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Interpubic disc (symphyseal fibrocartilage) | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Inguinal ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Lacunar ligament (Gimbernat) | - | - | - | - | - | - |
| Pectineal ligament (Cooper) | - | - | - | - | - | - |
| Obturator membrane | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

### Spine

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Anterior longitudinal ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Posterior longitudinal ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Ligamenta flava | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Interspinous ligaments | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Supraspinous ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Nuchal ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Intertransverse ligaments | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Zygapophysial (facet) joint capsules | - | - | - | - | - | - |
| Alar ligaments (dens) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Transverse ligament of the atlas / cruciform ligament | - | - | - | - | - | - |
| Apical ligament of the dens | - | - | - | - | - | - |
| Tectorial membrane | - | - | - | - | - | - |
| Costotransverse ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Radiate ligament of the head of the rib (costovertebral) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

### Hip

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Iliofemoral ligament (Y-ligament) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Pubofemoral ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Ischiofemoral ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Ligament of the head of the femur (ligamentum teres) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Transverse acetabular ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Zona orbicularis | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Acetabular labrum | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

### Knee

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Anterior cruciate ligament | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Posterior cruciate ligament | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Tibial (medial) collateral ligament, superficial | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Medial collateral ligament, deep (meniscofemoral / meniscotibial) | - | - | - | - | - | - |
| Fibular (lateral) collateral ligament | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Posterior oblique ligament | - | - | - | - | - | - |
| Arcuate popliteal ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Popliteofibular ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Oblique popliteal ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Anterolateral ligament | - | - | - | - | - | - |
| Meniscofemoral ligaments (Humphry, Wrisberg) | - | - | - | - | - | - |
| Transverse ligament of the knee (transverse meniscal) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Coronary ligaments (meniscotibial) | - | - | - | - | - | - |
| Patellar ligament | - | - | - | - | - | - |
| Medial patellar retinaculum / patellofemoral ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Lateral patellar retinaculum / patellofemoral ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Medial and lateral menisci | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

### Ankle and foot

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Anterior talofibular ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Calcaneofibular ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Posterior talofibular ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Deltoid: tibionavicular part | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Deltoid: tibiocalcaneal part | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Deltoid: anterior tibiotalar part | - | - | - | - | - | - |
| Deltoid: posterior tibiotalar part | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Anterior tibiofibular ligament (AITFL) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Posterior tibiofibular ligament (PITFL) and transverse tibiofibular | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Interosseous membrane of the leg | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Spring ligament (plantar calcaneonavicular) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Bifurcate ligament (calcaneonavicular + calcaneocuboid) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Long plantar ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Short plantar ligament (plantar calcaneocuboid) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Plantar aponeurosis (plantar fascia) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Talocalcaneal interosseous / cervical ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Tarsometatarsal (Lisfranc) interosseous ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Intermetatarsal ligaments (interosseous, dorsal, deep transverse) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Collateral ligaments of MTP and IP joints (foot) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Plantar plates of MTP and IP joints (foot) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Extensor retinacula of the ankle (superior, inferior) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Flexor retinaculum of the ankle | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Fibular (peroneal) retinacula | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |

### Shoulder

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Coracoclavicular ligament: conoid | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) |
| Coracoclavicular ligament: trapezoid | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) |
| Acromioclavicular ligament | + lr measured/CT | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Coracoacromial ligament | - | - | - | - | - | - |
| Coracohumeral ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Glenohumeral: superior (SGHL) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Glenohumeral: middle (MGHL) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Glenohumeral: inferior (IGHL) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Transverse humeral ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Glenoid labrum | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Superior / inferior transverse scapular ligament | - | - | - | - | - | - |

### Thorax

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Sternoclavicular ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Costoclavicular ligament | - | - | - | - | - | - |
| Interclavicular ligament | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Radiate sternocostal ligaments | - | - | - | - | - | - |
| Costoxiphoid ligaments | - | - | - | - | - | - |

### Elbow

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Ulnar collateral ligament (anterior, posterior, transverse bands) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Radial collateral ligament (elbow) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Annular ligament of the radius | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Quadrate ligament | - | - | - | - | - | - |
| Interosseous membrane of the forearm | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Oblique cord | - | - | - | - | - | - |

### Wrist and hand

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Palmar (volar) radiocarpal ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Dorsal radiocarpal ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Ulnocarpal (ulnolunate, ulnotriquetral, ulnocapitate) ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Triangular fibrocartilage complex (articular disc of the distal radio-ulnar joint) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Scapholunate interosseous ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Lunotriquetral interosseous ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Intercarpal ligaments (dorsal, palmar, interosseous) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Flexor retinaculum (transverse carpal ligament) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Extensor retinaculum of the wrist | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Pisohamate ligament | - | - | - | - | - | - |
| Pisometacarpal ligament (and pisotriquetral) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Collateral ligaments of MCP and IP joints (hand) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Palmar (volar) plates of the MCP / IP joints | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Palmar carpometacarpal ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Dorsal carpometacarpal ligaments | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Deep transverse metacarpal ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

## 4. Missing items ranked by relevance (pelvic floor first, then pelvis, spine, hip, knee, ankle, shoulder, thorax, elbow, wrist/hand)

Rank = group order, then the number of pages that lack it (BEFORE). 'Source' says what Q248 can defend: a real source (Z-Anatomy structure of the Combined / Base page, CVH, HRA) or a rule from published attachments; `no source` = nothing shipped.

| # | Group | Item | missing on (pages) | Q248 route |
|---|---|---|---|---|
| 1 | Pelvic floor and perineum | Anococcygeal ligament / raphe | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | female Imaging-based / Combined: CVH ligament (Wu 2015) where it passes the guards, else rule-based; male and Base: RULE-BASED (coccyx tip to external anal sphincter) |
| 2 | Pelvic floor and perineum | Arcus tendineus fasciae pelvis (tendinous arch of pelvic fascia) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | RULE-BASED, all six pages (DeLancey 1992 / Stein & DeLancey 2008 attachments; calibre = modelling choice) |
| 3 | Pelvic floor and perineum | Lateral umbilical ligament (obliterated umbilical artery) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: obliterated umbilical artery, course from the internal iliac artery to the umbilicus not implemented in Q248 |
| 4 | Pelvic floor and perineum | Lateral vesical / lateral rectal ligaments | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: peritoneal / endopelvic condensations without a discrete attachment footprint in TA / Gray 1918; NOT built |
| 5 | Pelvic floor and perineum | Median umbilical ligament (urachus) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: umbilicus-to-bladder-apex course along the posterior rectus sheath not implemented in Q248 |
| 6 | Pelvic floor and perineum | Perineal membrane (urogenital diaphragm, inferior fascia) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source for a shape: the membrane is a 3-D structure embedded around urethra / vagina / perineal body (Stein & DeLancey 2008); no thickness or outline published in the cited papers; NOT built |
| 7 | Pelvic floor and perineum | Pubovesical / puboprostatic / pubourethral ligaments | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | RULE-BASED (puboprostatic male / pubovesical female); CVH pubovesical ligament tried: it lies in the vestibule after the Q235 registration (overlaps the vestibular bulb), held |
| 8 | Pelvic floor and perineum | Tendinous arch of levator ani (arcus tendineus musculi levatoris ani) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | RULE-BASED, all six pages (Gray 1918 / Kearney 2004 attachments; calibre = modelling choice) |
| 9 | Pelvic floor and perineum | Transverse perineal ligament (of the pelvis) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | RULE-BASED, all six pages (TA / Gray 1918; calibre = modelling choice) |
| 10 | Pelvic floor and perineum | Fundiform ligament of the penis | Imaging-based M, Combined M, Base M | no source built: attaches to the linea alba / Scarpa fascia (no bony footprint) |
| 11 | Pelvic floor and perineum | Suspensory ligament of the penis | Imaging-based M, Combined M, Base M | no source built: no landmark rule for the penile root attachment on the pubic symphysis in Q248 |
| 12 | Pelvic floor and perineum | Pubococcygeal and puboperineal components (levator ani) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 13 | Pelvic girdle (bony ligaments) | Lacunar ligament (Gimbernat) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: pubic tubercle / pectineal line not located reliably on all six bodies |
| 14 | Pelvic girdle (bony ligaments) | Lumbosacral ligament (lateral lumbosacral, L5-sacral ala) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built (L5 transverse process to the sacral ala): no Z-Anatomy object; landmark rule not implemented |
| 15 | Pelvic girdle (bony ligaments) | Pectineal ligament (Cooper) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: pectineal line not located reliably on all six bodies |
| 16 | Pelvic girdle (bony ligaments) | Sacrococcygeal ligaments (anterior, posterior, lateral) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: Z-Anatomy has only the sacrococcygeal symphysis (disc); ligament footprints (cornua, hiatus) not located |
| 17 | Pelvic girdle (bony ligaments) | Long dorsal sacroiliac ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built (PSIS to the lateral sacral crest S3-S4): landmark rule not implemented |
| 18 | Pelvic girdle (bony ligaments) | Falciform process of the sacrotuberous ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: the sickle-shaped extension along the ischial ramus has no landmark rule that works on all six bodies |
| 19 | Pelvic girdle (bony ligaments) | Arcuate pubic (inferior / subpubic) ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 20 | Pelvic girdle (bony ligaments) | Iliolumbar ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 21 | Pelvic girdle (bony ligaments) | Inguinal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 22 | Pelvic girdle (bony ligaments) | Obturator membrane | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 23 | Pelvic girdle (bony ligaments) | Interpubic disc (symphyseal fibrocartilage) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 24 | Pelvic girdle (bony ligaments) | Sacrococcygeal symphysis (joint disc) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 25 | Pelvic girdle (bony ligaments) | Anterior sacroiliac ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 26 | Pelvic girdle (bony ligaments) | Interosseous sacroiliac ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 27 | Pelvic girdle (bony ligaments) | Posterior sacroiliac ligaments (short) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 28 | Pelvic girdle (bony ligaments) | Sacrospinous ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 29 | Pelvic girdle (bony ligaments) | Sacrotuberous ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 30 | Pelvic girdle (bony ligaments) | Superior pubic ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 31 | Spine | Apical ligament of the dens | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object on the pages |
| 32 | Spine | Zygapophysial (facet) joint capsules | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object on the pages; nothing built |
| 33 | Spine | Tectorial membrane | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object on the pages |
| 34 | Spine | Transverse ligament of the atlas / cruciform ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source |
| 35 | Spine | Alar ligaments (dens) | Imaging-based F, Imaging-based M | Z-Anatomy transfer is not possible on the Imaging-based pages (dens / atlas carriers), nothing built |
| 36 | Spine | Anterior longitudinal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 37 | Spine | Costotransverse ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 38 | Spine | Ligamenta flava | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 39 | Spine | Interspinous ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 40 | Spine | Intertransverse ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 41 | Spine | Nuchal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 42 | Spine | Posterior longitudinal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 43 | Spine | Radiate ligament of the head of the rib (costovertebral) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 44 | Spine | Supraspinous ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 45 | Hip | Acetabular labrum | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 46 | Hip | Iliofemoral ligament (Y-ligament) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 47 | Hip | Ischiofemoral ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 48 | Hip | Pubofemoral ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 49 | Hip | Ligament of the head of the femur (ligamentum teres) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 50 | Hip | Transverse acetabular ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 51 | Hip | Zona orbicularis | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 52 | Knee | Anterolateral ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object (the ALL has contested attachments) |
| 53 | Knee | Coronary ligaments (meniscotibial) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object, no landmark rule |
| 54 | Knee | Medial collateral ligament, deep (meniscofemoral / meniscotibial) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object, no landmark rule |
| 55 | Knee | Meniscofemoral ligaments (Humphry, Wrisberg) | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object, no landmark rule |
| 56 | Knee | Patellar ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | RULE-BASED, all six pages (apex of the patella to the tibial tuberosity; length range Aithal Padur 2021; thickness = modelling choice) |
| 57 | Knee | Posterior oblique ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object, no landmark rule |
| 58 | Knee | Arcuate popliteal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 59 | Knee | Medial and lateral menisci | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 60 | Knee | Oblique popliteal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 61 | Knee | Lateral patellar retinaculum / patellofemoral ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 62 | Knee | Medial patellar retinaculum / patellofemoral ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 63 | Knee | Popliteofibular ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 64 | Knee | Transverse ligament of the knee (transverse meniscal) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 65 | Ankle and foot | Deltoid: anterior tibiotalar part | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 66 | Ankle and foot | Anterior tibiofibular ligament (AITFL) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 67 | Ankle and foot | Anterior talofibular ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 68 | Ankle and foot | Bifurcate ligament (calcaneonavicular + calcaneocuboid) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 69 | Ankle and foot | Calcaneofibular ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 70 | Ankle and foot | Collateral ligaments of MTP and IP joints (foot) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 71 | Ankle and foot | Deltoid: posterior tibiotalar part | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 72 | Ankle and foot | Deltoid: tibiocalcaneal part | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 73 | Ankle and foot | Deltoid: tibionavicular part | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 74 | Ankle and foot | Extensor retinacula of the ankle (superior, inferior) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 75 | Ankle and foot | Fibular (peroneal) retinacula | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 76 | Ankle and foot | Flexor retinaculum of the ankle | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 77 | Ankle and foot | Intermetatarsal ligaments (interosseous, dorsal, deep transverse) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 78 | Ankle and foot | Interosseous membrane of the leg | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 79 | Ankle and foot | Tarsometatarsal (Lisfranc) interosseous ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 80 | Ankle and foot | Long plantar ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 81 | Ankle and foot | Posterior tibiofibular ligament (PITFL) and transverse tibiofibular | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 82 | Ankle and foot | Plantar aponeurosis (plantar fascia) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 83 | Ankle and foot | Plantar plates of MTP and IP joints (foot) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 84 | Ankle and foot | Posterior talofibular ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 85 | Ankle and foot | Short plantar ligament (plantar calcaneocuboid) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 86 | Ankle and foot | Spring ligament (plantar calcaneonavicular) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 87 | Ankle and foot | Talocalcaneal interosseous / cervical ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 88 | Shoulder | Coracoacromial ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source built: the sub-facet of the acromion is not an authored landmark (Q122) |
| 89 | Shoulder | Superior / inferior transverse scapular ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 90 | Shoulder | Coracohumeral ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 91 | Shoulder | Glenoid labrum | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 92 | Shoulder | Glenohumeral: inferior (IGHL) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 93 | Shoulder | Glenohumeral: middle (MGHL) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 94 | Shoulder | Glenohumeral: superior (SGHL) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 95 | Shoulder | Transverse humeral ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 96 | Shoulder | Acromioclavicular ligament | Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 97 | Thorax | Costoclavicular ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 98 | Thorax | Costoxiphoid ligaments | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 99 | Thorax | Radiate sternocostal ligaments | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 100 | Thorax | Interclavicular ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 101 | Thorax | Sternoclavicular ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 102 | Elbow | Oblique cord | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 103 | Elbow | Quadrate ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 104 | Elbow | Annular ligament of the radius | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 105 | Elbow | Interosseous membrane of the forearm | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 106 | Elbow | Radial collateral ligament (elbow) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 107 | Elbow | Ulnar collateral ligament (anterior, posterior, transverse bands) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 108 | Wrist and hand | Pisohamate ligament | Imaging-based F, Combined F, Base F, Imaging-based M, Combined M, Base M | no source: no Z-Anatomy object |
| 109 | Wrist and hand | Dorsal carpometacarpal ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 110 | Wrist and hand | Palmar carpometacarpal ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 111 | Wrist and hand | Collateral ligaments of MCP and IP joints (hand) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 112 | Wrist and hand | Deep transverse metacarpal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 113 | Wrist and hand | Extensor retinaculum of the wrist | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 114 | Wrist and hand | Flexor retinaculum (transverse carpal ligament) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 115 | Wrist and hand | Intercarpal ligaments (dorsal, palmar, interosseous) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 116 | Wrist and hand | Lunotriquetral interosseous ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 117 | Wrist and hand | Pisometacarpal ligament (and pisotriquetral) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 118 | Wrist and hand | Dorsal radiocarpal ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 119 | Wrist and hand | Palmar (volar) radiocarpal ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 120 | Wrist and hand | Scapholunate interosseous ligament | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 121 | Wrist and hand | Triangular fibrocartilage complex (articular disc of the distal radio-ulnar joint) | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 122 | Wrist and hand | Ulnocarpal (ulnolunate, ulnotriquetral, ulnocapitate) ligaments | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
| 123 | Wrist and hand | Palmar (volar) plates of the MCP / IP joints | Imaging-based F, Imaging-based M | Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass |
