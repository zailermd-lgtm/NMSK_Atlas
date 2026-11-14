# Q248 ligament audit (six pages against a reference checklist)

Reference: Terminologia Anatomica (items named by TA / Latin terms), Gray's Anatomy 1918 (public domain) and standard anatomy; the checklist is `scripts/anatomy/q248/checklist.py` (135 items; sex-specific items count only on the matching sex). A structure counts when its id / name matches the item (regex in the checklist); an item whose structure stands for several items (one glenohumeral complex for SGHL/MGHL/IGHL, one coracoclavicular ligament for conoid + trapezoid, ...) is counted present for each and marked 'grouped'. BEFORE = the six page dirs of Q244 (`build/q244`); AFTER = the Q248 page dirs (`build/q248`).

## 1. Counts per page (present / one side only / missing; items that do not apply to the sex excluded)

| Page | present | one side | missing | applicable | present after | one side after | missing after |
|---|---|---|---|---|---|---|---|
| Imaging-based F | 13 | 6 | 114 | 133 | 55 | 22 | 56 |
| Combined F | 99 | 0 | 34 | 133 | 105 | 0 | 28 |
| Base F | 99 | 0 | 34 | 133 | 104 | 0 | 29 |
| Imaging-based M | 6 | 5 | 118 | 129 | 49 | 19 | 61 |
| Combined M | 93 | 0 | 36 | 129 | 98 | 1 | 30 |
| Base M | 93 | 0 | 36 | 129 | 98 | 0 | 31 |

Ligament-like entries on the page (class ligament / joint / fascia / tendon): Imaging-based F 43 -> 133, Combined F 403 -> 413, Base F 401 -> 409, Imaging-based M 22 -> 111, Combined M 386 -> 395, Base M 386 -> 394.

### Per group (present / applicable; BEFORE -> AFTER)

| Group | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Pelvic floor and perineum | 6/16 -> 9/16 | 7/16 -> 12/16 | 7/16 -> 12/16 | 0/12 -> 5/12 | 1/12 -> 6/12 | 1/12 -> 6/12 |
| Pelvic girdle (bony ligaments) | 0/18 -> 8/18 | 12/18 -> 12/18 | 12/18 -> 12/18 | 0/18 -> 8/18 | 12/18 -> 12/18 | 12/18 -> 12/18 |
| Spine | 0/14 -> 2/14 | 10/14 -> 10/14 | 10/14 -> 10/14 | 0/14 -> 1/14 | 10/14 -> 10/14 | 10/14 -> 10/14 |
| Hip | 0/7 -> 6/7 | 7/7 -> 7/7 | 7/7 -> 7/7 | 0/7 -> 5/7 | 7/7 -> 7/7 | 7/7 -> 7/7 |
| Knee | 4/17 -> 8/17 | 11/17 -> 12/17 | 11/17 -> 11/17 | 4/17 -> 11/17 | 11/17 -> 11/17 | 11/17 -> 11/17 |
| Ankle and foot | 0/23 -> 10/23 | 22/23 -> 22/23 | 22/23 -> 22/23 | 0/23 -> 8/23 | 22/23 -> 22/23 | 22/23 -> 22/23 |
| Shoulder | 3/11 -> 9/11 | 9/11 -> 9/11 | 9/11 -> 9/11 | 2/11 -> 9/11 | 9/11 -> 9/11 | 9/11 -> 9/11 |
| Thorax | 0/5 -> 1/5 | 2/5 -> 2/5 | 2/5 -> 2/5 | 0/5 -> 2/5 | 2/5 -> 2/5 | 2/5 -> 2/5 |
| Elbow | 0/6 -> 0/6 | 4/6 -> 4/6 | 4/6 -> 4/6 | 0/6 -> 0/6 | 4/6 -> 4/6 | 4/6 -> 4/6 |
| Wrist and hand | 0/16 -> 2/16 | 15/16 -> 15/16 | 15/16 -> 15/16 | 0/16 -> 0/16 | 15/16 -> 15/16 | 15/16 -> 15/16 |

## 2. How the ligaments present on each page were derived (class ligament / joint entries)

| Page | derivation: count |
|---|---|
| Imaging-based F | HRA 17, transferred (VH m<->f) 8, measured/CT 3, mirrored 1 || AFTER: Z-filled (Q248) 82, HRA 17, transferred (VH m<->f) 8, rule-based (Q248) 7, measured/CT 3, mirrored 1, CVH (Q248) 1 |
| Combined F | Z-fitted 342 || AFTER: Z-fitted 342, rule-based (Q248) 10 |
| Base F | Z (Base) 340 || AFTER: Z (Base) 340, rule-based (Q248) 8 |
| Imaging-based M | measured/CT 9, mirrored 1 || AFTER: Z-filled (Q248) 75, rule-based (Q248) 14, measured/CT 9, mirrored 1 |
| Combined M | Z-fitted 325 || AFTER: Z-fitted 325, rule-based (Q248) 9 |
| Base M | Z (Base) 325 || AFTER: Z (Base) 325, rule-based (Q248) 8 |

Legend: measured/CT = segmented / measured on the body (also the Visible Human DU lower-extremity release); Z-fitted = Z-Anatomy structure fitted to the Combined body (CC BY-SA 4.0); Z (Base) = Z-Anatomy structure of the Base model; Z-filled = Z-Anatomy structure carried onto the own bones one bone at a time (earlier passes) or, `(Q248)`, by the Q248 carrier-bone fit; HRA = HuBMAP reference object registered on the body (CC BY 4.0); CVH = Chinese Visible Human (Wu 2015) registered; rule-based = built from bone landmarks by a documented rule; mirrored = mirror of the opposite side; transferred = other Visible Human.

## 3. Checklist matrix (status / sides / derivation); rows in relevance order (pelvic floor first)

Status: `+` present, `1` one side only, `-` missing, `n/a` not for this sex.  Sides: l r m.

### Pelvic floor and perineum

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Tendinous arch of levator ani (arcus tendineus musculi levatoris ani) | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** |
| Arcus tendineus fasciae pelvis (tendinous arch of pelvic fascia) | - -> **1 r rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** |
| Perineal membrane (urogenital diaphragm, inferior fascia) | - | - | - | - | - | - |
| Transverse perineal ligament (of the pelvis) | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** |
| Anococcygeal ligament / raphe | - -> **+ m CVH (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** | - -> **+ m rule-based (Q248)** |
| Pubococcygeal and puboperineal components (levator ani) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Pubovesical / puboprostatic / pubourethral ligaments | - | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - -> **+ lr rule-based (Q248)** |
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
| Sacrospinous ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr rule-based (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Sacrotuberous ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr rule-based (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Falciform process of the sacrotuberous ligament | - | - | - | - | - | - |
| Iliolumbar ligament | - -> **+ lr rule-based (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr rule-based (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Lumbosacral ligament (lateral lumbosacral, L5-sacral ala) | - | - | - | - | - | - |
| Anterior sacroiliac ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Posterior sacroiliac ligaments (short) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Interosseous sacroiliac ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Long dorsal sacroiliac ligament | - | - | - | - | - | - |
| Sacrococcygeal ligaments (anterior, posterior, lateral) | - | - | - | - | - | - |
| Sacrococcygeal symphysis (joint disc) | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Arcuate pubic (inferior / subpubic) ligament | - -> **+ m Z-filled (Q248)** | + m Z-fitted | + m Z (Base) | - -> **+ m Z-filled (Q248)** | + m Z-fitted | + m Z (Base) |
| Superior pubic ligament | - -> **+ m Z-filled (Q248)** | + m Z-fitted | + m Z (Base) | - -> **+ m Z-filled (Q248)** | + m Z-fitted | + m Z (Base) |
| Interpubic disc (symphyseal fibrocartilage) | - | + m Z-fitted | + m Z (Base) | - | + m Z-fitted | + m Z (Base) |
| Inguinal ligament | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Lacunar ligament (Gimbernat) | - | - | - | - | - | - |
| Pectineal ligament (Cooper) | - | - | - | - | - | - |
| Obturator membrane | - | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |

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
| Alar ligaments (dens) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Transverse ligament of the atlas / cruciform ligament | - | - | - | - | - | - |
| Apical ligament of the dens | - | - | - | - | - | - |
| Tectorial membrane | - | - | - | - | - | - |
| Costotransverse ligaments | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Radiate ligament of the head of the rib (costovertebral) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

### Hip

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Iliofemoral ligament (Y-ligament) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Pubofemoral ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Ischiofemoral ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Ligament of the head of the femur (ligamentum teres) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Transverse acetabular ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Zona orbicularis | - | + lr Z-fitted | + lr Z (Base) | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Acetabular labrum | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |

### Knee

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Anterior cruciate ligament | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Posterior cruciate ligament | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Tibial (medial) collateral ligament, superficial | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Medial collateral ligament, deep (meniscofemoral / meniscotibial) | - | - | - | - | - | - |
| Fibular (lateral) collateral ligament | + lr transferred (VH m<->f) | + lr Z-fitted | + lr Z (Base) | + lr measured/CT | + lr Z-fitted | + lr Z (Base) |
| Posterior oblique ligament | - | - | - | - | - | - |
| Arcuate popliteal ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Popliteofibular ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Oblique popliteal ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Anterolateral ligament | - | - | - | - | - | - |
| Meniscofemoral ligaments (Humphry, Wrisberg) | - | - | - | - | - | - |
| Transverse ligament of the knee (transverse meniscal) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Coronary ligaments (meniscotibial) | - | - | - | - | - | - |
| Patellar ligament | - -> **1 r Z-filled (Q248)/rule-based (Q248)** | - -> **+ lr rule-based (Q248)** | - | - -> **+ lr Z-filled (Q248)** | - -> **1 r rule-based (Q248)** | - |
| Medial patellar retinaculum / patellofemoral ligament | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Lateral patellar retinaculum / patellofemoral ligament | - | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Medial and lateral menisci | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |

### Ankle and foot

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Anterior talofibular ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Calcaneofibular ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Posterior talofibular ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Deltoid: tibionavicular part | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Deltoid: tibiocalcaneal part | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Deltoid: anterior tibiotalar part | - | - | - | - | - | - |
| Deltoid: posterior tibiotalar part | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Anterior tibiofibular ligament (AITFL) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Posterior tibiofibular ligament (PITFL) and transverse tibiofibular | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Interosseous membrane of the leg | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Spring ligament (plantar calcaneonavicular) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Bifurcate ligament (calcaneonavicular + calcaneocuboid) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Long plantar ligament | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Short plantar ligament (plantar calcaneocuboid) | - | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Plantar aponeurosis (plantar fascia) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Talocalcaneal interosseous / cervical ligament | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Tarsometatarsal (Lisfranc) interosseous ligaments | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Intermetatarsal ligaments (interosseous, dorsal, deep transverse) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Collateral ligaments of MTP and IP joints (foot) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Plantar plates of MTP and IP joints (foot) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Extensor retinacula of the ankle (superior, inferior) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Flexor retinaculum of the ankle | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Fibular (peroneal) retinacula | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |

### Shoulder

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Coracoclavicular ligament: conoid | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) |
| Coracoclavicular ligament: trapezoid | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) | + lr measured/CT/mirrored | + lr Z-fitted | + lr Z (Base) |
| Acromioclavicular ligament | + lr measured/CT | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Coracoacromial ligament | - | - | - | - | - | - |
| Coracohumeral ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Glenohumeral: superior (SGHL) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Glenohumeral: middle (MGHL) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Glenohumeral: inferior (IGHL) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Transverse humeral ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Glenoid labrum | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Superior / inferior transverse scapular ligament | - | - | - | - | - | - |

### Thorax

| Item | Imaging-based F | Combined F | Base F | Imaging-based M | Combined M | Base M |
|---|---|---|---|---|---|---|
| Sternoclavicular ligaments | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Costoclavicular ligament | - | - | - | - | - | - |
| Interclavicular ligament | - -> **+ m Z-filled (Q248)** | + m Z-fitted | + m Z (Base) | - -> **+ m Z-filled (Q248)** | + m Z-fitted | + m Z (Base) |
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
| Palmar (volar) radiocarpal ligaments | - -> **1 l Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Dorsal radiocarpal ligament | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Ulnocarpal (ulnolunate, ulnotriquetral, ulnocapitate) ligaments | - | + lr Z-fitted | + lr Z (Base) | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Triangular fibrocartilage complex (articular disc of the distal radio-ulnar joint) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Scapholunate interosseous ligament | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Lunotriquetral interosseous ligament | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Intercarpal ligaments (dorsal, palmar, interosseous) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Flexor retinaculum (transverse carpal ligament) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Extensor retinaculum of the wrist | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) | 1 r Z-filled | + lr Z-fitted | + lr Z (Base) |
| Pisohamate ligament | - | - | - | - | - | - |
| Pisometacarpal ligament (and pisotriquetral) | - -> **+ lr Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |
| Collateral ligaments of MCP and IP joints (hand) | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Palmar (volar) plates of the MCP / IP joints | - | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Palmar carpometacarpal ligaments | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Dorsal carpometacarpal ligaments | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - | + lr Z-fitted | + lr Z (Base) |
| Deep transverse metacarpal ligament | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) | - -> **1 r Z-filled (Q248)** | + lr Z-fitted | + lr Z (Base) |

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

## 5. What Q248 added, per page

`transferred` = Z-Anatomy structure carried onto the own bones (own pages only; the Z pages already hold the Z structures), `rule-based` = built from the page's bones / organs (all six pages), `CVH` = Chinese Visible Human anococcygeal ligament (female own page). Ship diff: every other structure of the page is byte for byte the Q244 page (`data/derived/Q248_vertex_diff_<page>.json`, 0 unlisted).

| Page | transferred | rule-based | CVH | total added | triangles added |
|---|---|---|---|---|---|
| Imaging-based F | 86 | 7 | 1 | 94 | 43802 |
| Combined F | 0 | 10 | 0 | 10 | 6720 |
| Base F | 0 | 8 | 0 | 8 | 5568 |
| Imaging-based M | 79 | 14 | 0 | 93 | 39170 |
| Combined M | 0 | 9 | 0 | 9 | 6144 |
| Base M | 0 | 8 | 0 | 8 | 5568 |

## 6. Rule-based ligaments: numbers per page

Length = path length; cross-section = width x thickness (mm; the calibre is a MODELLING CHOICE except where a card says otherwise); volume = closed mesh; attachment = signed distance of the two end-cap centres to the attachment surface (bone, 0 = on the surface); 'deeper than 1 mm' = vertices more than 1 mm inside a bone after the push-out (0 required); soft overlap = fraction of vertices deeper than 6 mm inside a closed muscle / 3 mm inside an organ (gated on the Imaging-based pages, reported on the Z pages).

| Page | id | length mm | cross-section mm | volume cm3 | attachment a / b mm | deeper 1 mm | soft overlap muscle / organ | skin depth mm |
|---|---|---|---|---|---|---|---|---|
| Imaging-based F | tendinous_arch_levator_ani_l | 67.9 | 5.0 x 1.5 | 0.3813 | 0.0 / -0.0 | 0 | 0.025 / 0.0 | 64.3 |
| Imaging-based F | tendinous_arch_levator_ani_r | 72.0 | 5.0 x 1.5 | 0.405 | 0.0 / 0.0 | 0 | 0.075 / 0.0 | 64.5 |
| Imaging-based F | arcus_tendineus_fasciae_pelvis_r | 76.8 | 5.0 x 1.5 | 0.4322 | 0.0 / -0.0 | 0 | 0.12 / 0.0 | 61.3 |
| Imaging-based F | transverse_perineal_ligament | 16.4 | 8.0 x 2.0 | 0.1627 | 0.0 / -0.0 | 0 | 0.01 / 0.0 | 33.8 |
| Imaging-based F | patellar_ligament_r | 34.2 | 24.0-30.0 x 5.0 | 3.4631 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 2.9 |
| Imaging-based F | iliolumbar_ligament_l | 13.4 | 12.0 x 3.0 | 0.3613 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 66.9 |
| Imaging-based F | iliolumbar_ligament_r | 14.3 | 12.0 x 3.0 | 0.3848 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 70.5 |
| Combined F | tendinous_arch_levator_ani_l | 75.1 | 5.0 x 1.5 | 0.4204 | 0.0 / 0.0 | 0 | 0.185 / 0.0 | 45.6 |
| Combined F | arcus_tendineus_fasciae_pelvis_l | 77.6 | 5.0 x 1.5 | 0.4363 | 0.0 / 0.0 | 0 | 0.21 / 0.083 | 40.3 |
| Combined F | tendinous_arch_levator_ani_r | 75.6 | 5.0 x 1.5 | 0.4224 | 0.0 / 0.0 | 0 | 0.241 / 1.0 | 48.4 |
| Combined F | arcus_tendineus_fasciae_pelvis_r | 86.3 | 5.0 x 1.5 | 0.4824 | 0.0 / -0.0 | 0 | 0.293 / 0.936 | 37.3 |
| Combined F | transverse_perineal_ligament | 42.0 | 8.0 x 2.0 | 0.475 | 0.0 / 0.0 | 0 | 0.526 / 0.0 | 19.1 |
| Combined F | anococcygeal_ligament | 47.4 | 10.0 x 3.0 | 1.0671 | 0.0 / - | 0 | 0.0 / 0.031 | 15.7 |
| Combined F | pubovesical_ligament_l | 11.2 | 8.0 x 3.0 | 0.201 | 0.0 / - | 0 | 0.041 / 0.0 | 37.6 |
| Combined F | pubovesical_ligament_r | 7.9 | 8.0 x 3.0 | 0.1431 | 0.0 / - | 0 | 0.021 / 0.0 | 38.0 |
| Combined F | patellar_ligament_l | 42.1 | 24.0-30.0 x 5.0 | 4.246 | 0.0 / 0.0 | 0 | 0.1 / 0.0 | 0.7 |
| Combined F | patellar_ligament_r | 54.0 | 24.0-30.0 x 5.0 | 5.206 | 0.0 / -0.0 | 0 | 0.483 / 0.0 | 0.8 |
| Base F | tendinous_arch_levator_ani_l | 75.5 | 5.0 x 1.5 | 0.4248 | 0.0 / 0.0 | 0 | 0.085 / 0.037 | 37.4 |
| Base F | arcus_tendineus_fasciae_pelvis_l | 76.2 | 5.0 x 1.5 | 0.4287 | 0.0 / -0.0 | 0 | 0.062 / 0.212 | 32.2 |
| Base F | tendinous_arch_levator_ani_r | 75.6 | 5.0 x 1.5 | 0.4252 | 0.0 / 0.0 | 0 | 0.39 / 0.0 | 37.3 |
| Base F | arcus_tendineus_fasciae_pelvis_r | 76.1 | 5.0 x 1.5 | 0.428 | 0.0 / 0.0 | 0 | 0.272 / 0.112 | 32.1 |
| Base F | transverse_perineal_ligament | 22.6 | 8.0 x 2.0 | 0.2506 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 11.0 |
| Base F | anococcygeal_ligament | 8.7 | 10.0 x 3.0 | 0.196 | 0.0 / - | 0 | 0.497 / 0.0 | 36.4 |
| Base F | pubovesical_ligament_l | 8.6 | 8.0 x 3.0 | 0.1552 | 0.0 / - | 0 | 0.546 / 0.0 | 28.3 |
| Base F | pubovesical_ligament_r | 8.2 | 8.0 x 3.0 | 0.1467 | 0.0 / - | 0 | 0.005 / 0.0 | 28.5 |
| Imaging-based M | tendinous_arch_levator_ani_l | 90.7 | 5.0 x 1.5 | 0.5093 | 0.0 / -0.0 | 0 | 0.0 / 0.0 | 71.8 |
| Imaging-based M | arcus_tendineus_fasciae_pelvis_l | 82.3 | 5.0 x 1.5 | 0.463 | 0.0 / 0.0 | 0 | 0.052 / 0.0 | 71.5 |
| Imaging-based M | tendinous_arch_levator_ani_r | 81.0 | 5.0 x 1.5 | 0.4547 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 75.4 |
| Imaging-based M | arcus_tendineus_fasciae_pelvis_r | 78.4 | 5.0 x 1.5 | 0.4412 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 77.2 |
| Imaging-based M | transverse_perineal_ligament | 17.0 | 8.0 x 2.0 | 0.1734 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 59.0 |
| Imaging-based M | anococcygeal_ligament | 50.0 | 10.0 x 3.0 | 1.125 | 0.0 / - | 0 | 0.0 / 0.0 | 27.7 |
| Imaging-based M | puboprostatic_ligament_l | 26.9 | 8.0 x 3.0 | 0.4847 | 0.0 / - | 0 | 0.0 / 0.0 | 80.9 |
| Imaging-based M | puboprostatic_ligament_r | 22.6 | 8.0 x 3.0 | 0.1679 | 0.0 / - | 0 | 0.0 / 0.0 | 79.1 |
| Imaging-based M | sacrospinous_ligament_l | 54.9 | 7.0-12.0 x 2.5 | 0.978 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 32.5 |
| Imaging-based M | sacrotuberous_ligament_l | 104.1 | 10.0-14.0 x 3.5 | 3.1847 | 0.0 / -0.0 | 0 | 0.064 / 0.0 | 27.8 |
| Imaging-based M | iliolumbar_ligament_l | 19.3 | 12.0 x 3.0 | 0.5203 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 76.5 |
| Imaging-based M | sacrospinous_ligament_r | 52.8 | 7.0-12.0 x 2.5 | 0.932 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 40.9 |
| Imaging-based M | sacrotuberous_ligament_r | 100.0 | 10.0-14.0 x 3.5 | 3.1309 | 0.0 / -0.0 | 0 | 0.0 / 0.0 | 27.6 |
| Imaging-based M | iliolumbar_ligament_r | 17.7 | 12.0 x 3.0 | 0.4728 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 77.1 |
| Combined M | tendinous_arch_levator_ani_l | 78.2 | 5.0 x 1.5 | 0.4399 | 0.0 / 0.0 | 0 | 0.201 / 0.344 | 57.1 |
| Combined M | arcus_tendineus_fasciae_pelvis_l | 88.5 | 5.0 x 1.5 | 0.4965 | 0.0 / -0.0 | 0 | 0.162 / 0.336 | 51.1 |
| Combined M | tendinous_arch_levator_ani_r | 75.9 | 5.0 x 1.5 | 0.427 | 0.0 / -0.0 | 0 | 0.768 / 0.344 | 56.6 |
| Combined M | arcus_tendineus_fasciae_pelvis_r | 85.9 | 5.0 x 1.5 | 0.4835 | 0.0 / -0.0 | 0 | 0.517 / 0.39 | 50.1 |
| Combined M | transverse_perineal_ligament | 22.0 | 8.0 x 2.0 | 0.2454 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 32.3 |
| Combined M | anococcygeal_ligament | 21.9 | 10.0 x 3.0 | 0.4918 | 0.0 / - | 0 | 0.01 / 0.0 | 29.6 |
| Combined M | puboprostatic_ligament_l | 26.8 | 8.0 x 3.0 | 0.4679 | 0.0 / - | 0 | 0.16 / 0.0 | 51.1 |
| Combined M | puboprostatic_ligament_r | 26.1 | 8.0 x 3.0 | 0.4579 | 0.0 / - | 0 | 0.392 / 0.0 | 50.3 |
| Combined M | patellar_ligament_r | 55.9 | 24.0-30.0 x 5.0 | 5.6226 | 0.0 / 0.0 | 0 | 0.397 / 0.0 | 0.8 |
| Base M | tendinous_arch_levator_ani_l | 75.5 | 5.0 x 1.5 | 0.4248 | 0.0 / 0.0 | 0 | 0.085 / 0.037 | 37.5 |
| Base M | arcus_tendineus_fasciae_pelvis_l | 76.2 | 5.0 x 1.5 | 0.4287 | 0.0 / -0.0 | 0 | 0.376 / 0.212 | 32.2 |
| Base M | tendinous_arch_levator_ani_r | 75.6 | 5.0 x 1.5 | 0.4252 | 0.0 / 0.0 | 0 | 0.34 / 0.0 | 37.3 |
| Base M | arcus_tendineus_fasciae_pelvis_r | 76.1 | 5.0 x 1.5 | 0.428 | 0.0 / 0.0 | 0 | 0.272 / 0.272 | 32.1 |
| Base M | transverse_perineal_ligament | 22.6 | 8.0 x 2.0 | 0.2506 | 0.0 / 0.0 | 0 | 0.0 / 0.149 | 11.8 |
| Base M | anococcygeal_ligament | 8.7 | 10.0 x 3.0 | 0.196 | 0.0 / - | 0 | 0.497 / 0.0 | 36.4 |
| Base M | puboprostatic_ligament_l | 17.8 | 8.0 x 3.0 | 0.3042 | 0.0 / - | 0 | 0.701 / 0.0 | 28.1 |
| Base M | puboprostatic_ligament_r | 18.2 | 8.0 x 3.0 | 0.3127 | 0.0 / - | 0 | 0.211 / 0.0 | 27.9 |

## 7. Z-Anatomy transfers onto the Imaging-based pages: fit errors

**Imaging-based F**: 86 structures shipped; worst carrier-bone local fit residual per structure: median 1.56 mm, max 2.46 mm; attachment gap before the snap (median of each structure): median 1.16 mm, max 3.0 mm; after the snap 0 mm by construction. Per-structure numbers: `data/derived/Q248_xfer_own_f.json` (carriers, local residuals, attachment gaps, pushed vertices, edge stretch, length ratio, overlap, skin depth, sides).

**Imaging-based M**: 79 structures shipped; worst carrier-bone local fit residual per structure: median 1.52 mm, max 2.4 mm; attachment gap before the snap (median of each structure): median 1.31 mm, max 5.09 mm; after the snap 0 mm by construction. Per-structure numbers: `data/derived/Q248_xfer_own_m.json` (carriers, local residuals, attachment gaps, pushed vertices, edge stretch, length ratio, overlap, skin depth, sides).

## 8. Held (not shipped) and why

**Imaging-based F**: 94 of 172 planned Z structures held. Reasons (a structure can have several): > 25 % of the vertices deeper than 6 mm inside a muscle x 65; mesh distorted (edge stretch) x 31; outside / within 1 mm of the skin x 28; attachment vertices not snappable x 10; length ratio outside 0.6-1.6 x 9; vertices still > 1 mm in bone x 8; too much of the mesh pushed out of bone x 6; carrier local fit median > 2.5 mm x 2.

**Imaging-based M**: 106 of 175 planned Z structures held. Reasons (a structure can have several): > 25 % of the vertices deeper than 6 mm inside a muscle x 78; mesh distorted (edge stretch) x 25; outside / within 1 mm of the skin x 17; attachment vertices not snappable x 13; too much of the mesh pushed out of bone x 13; length ratio outside 0.6-1.6 x 10; vertices still > 1 mm in bone x 8; carrier local fit median > 2.5 mm x 5.

**Imaging-based F, rule-based held**: `arcus_tendineus_fasciae_pelvis_l` (> 10 % of the vertices deeper than 3 mm inside an organ); `anococcygeal_ligament` (> 10 % of the vertices deeper than 3 mm inside an organ); `pubovesical_ligament_l` (> 10 % of the vertices deeper than 3 mm inside an organ); `pubovesical_ligament_r` (> 10 % of the vertices deeper than 3 mm inside an organ); `patellar_ligament_l` (closer than 0.5 mm to / outside the skin).

**Base F, rule-based held**: `patellar_ligament_l` (length 25.3 mm outside the published range 30-60 mm (Aithal Padur 2021)); `patellar_ligament_r` (length 25.4 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Imaging-based M, rule-based held**: `patellar_ligament_l` (length 76.1 mm outside the published range 30-60 mm (Aithal Padur 2021)); `patellar_ligament_r` (closer than 0.5 mm to / outside the skin, length 60.2 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Combined M, rule-based held**: `patellar_ligament_l` (length 61.4 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Base M, rule-based held**: `patellar_ligament_l` (length 25.3 mm outside the published range 30-60 mm (Aithal Padur 2021)); `patellar_ligament_r` (length 25.4 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Imaging-based F, CVH**: `anococcygeal_ligament_cvh` ship; `pubovesical_ligament_cvh` held (> 25 % of the vertices deeper than 6 mm inside a muscle, > 10 % of the vertices deeper than 3 mm inside an organ).

**Combined F, CVH**: `anococcygeal_ligament_cvh` held (> 10 % of the vertices deeper than 3 mm inside an organ, closer than 3 mm to / outside the skin, bone penetration after registration: > 15 % of the vertices or > 4 mm); `pubovesical_ligament_cvh` held (does not reach the pubic bone (14 mm away after the registration; the pubovesical ligament attaches to the pubis)).

## 9. Literature / sources checked (PubMed, web)

- Kearney R, Sawhney R, DeLancey JOL. Levator ani muscle anatomy evaluated by origin-insertion pairs. Obstet Gynecol 2004;104:168-73 (PMID 15229017, doi 10.1097/01.AOG.0000128906.61529.6b): origin / insertion pairs, no dimensions of the arch.
- Stein TA, DeLancey JOL. Structure of the perineal membrane in females: gross and microscopic anatomy. Obstet Gynecol 2008;111:686-93 (PMID 18310372, doi 10.1097/AOG.0b013e318163a9a5): the membrane is continuous with the insertion of the arcus tendineus fasciae pelvis; a 3-D structure (dorsal / ventral part), no outline or thickness that could be built: perineal membrane NOT built.
- DeLancey JOL. Anatomic aspects of vaginal eversion after hysterectomy. Am J Obstet Gynecol 1992;166:1717-28 (PMID 1615980): arcus tendineus fasciae pelvis from the pubic bone to the ischial spine.
- Aithal Padur A et al. Morphometric analysis of patella and patellar ligament. Surg Radiol Anat 2021;43:2039-46 (PMID 34570285, doi 10.1007/s00276-021-02837-z): patellar ligament length 4.8 / 4.6 cm (right / left), range 3-6 cm; the table of widths / thickness is not in the retrievable text.
- Basso O, Johnson DP, Amis AA. The anatomy of the patellar tendon. Knee Surg Sports Traumatol Arthrosc 2001;9:2-5 (PMID 11269580, doi 10.1007/s001670000133): fibres converge toward the tibial attachment; patellar apex 39 +- 6 % of the tendon width from the medial edge.
- Occelli et al., Eur J Obstet Gynecol Reprod Biol 2001 (abstract only, via a web search): arcus tendineus fasciae pelvis about 10 cm in two fixed female pelves; used as a plausibility range only. A 2004 cadaver study (five female cadavers) found the structure absent / weak in 6 of 10 hemipelves: variable presence.
- Sacrospinous ligament length 43.04 +- 6.58 mm (nine embalmed female hemipelves; 'Anatomical landmarks regarding sacrospinous colpopexy operations', web abstract, not verified against the paper): not used as input.
- No PubMed / web source gave a width or thickness for the tendinous arch of levator ani, the arcus tendineus fasciae pelvis, the transverse perineal ligament, the anococcygeal ligament or the puboprostatic / pubovesical ligaments: their calibres are MODELLING CHOICES (stated on every card as such), which is why those cards say 'an estimate of position'.
