# Q302 — סקר שמונה מקורות גאומטריה (Phase 1)

תאריך: 2026-11-02. ענף: `claude/3d-human-anatomy-atlas-e0kbxe`.
כל הנתונים כאן נבדקו ישירות מול המקור (HTTP/‏git/‏S3) ולא מתוך זיכרון. העדויות המספריות
שמורות ב-`data/derived/Q302_source_survey.json`, והטסטים ב-`tests/test_q302.py` מאמתים
אותן מול המסמך הזה.

מונחי אנטומיה באנגלית במכוון; מינוח קליני לא מתורגם.

Q303 (שנחת לפני המסמך הזה) אימת מחדש את פער 1 מול טבלת הקליבר של הדפים עצמם וקבע
**0 התאמות fibular/peroneal בשני דפי ה-Imaging מול 24 בכל דף Z**, וכן ש-15 מהעצבים
ההיקפיים המרכזיים אינם קיימים כלל בדף Imaging. הסקר הזה משתמש במספרים של Q303.

---

## 1. שבעת הפערים (priority order) — לפי Q295/Q296/Q297/Q299

| # | הפער | מה חסר בפועל |
|---|---|---|
| 1 | lower-limb nerves | בדפי Imaging **0** meshes של fibular/peroneal nerve (מול **24** בכל דף Z — המספר אומת מחדש ב-Q303 מול טבלת ה-`calibre.json` של הדפים עצמם, והמספר 18 שהופיע בתדריך הסבב מוחלף בו); 71 עצבי גפה תחתונה חסרים בסך הכל — כל מערכת ה-fibular, femoral, obturator, saphenous, sural, plantar, וה-sciatic המחולק לצדדים |
| 2 | female perineal skin | אין בשום מקור שבידינו; Q297 הסיר משטח מיוצר והאזור מוצג פתוח |
| 3 | nails, nail beds, digital pulp | אין; קצות האצבעות נמדדים מתחת ל-1 מ"מ במקום 3–8 מ"מ |
| 4 | ovaries, uterine tubes, vagina, perineum, levator ani | כיום HRA reference / CVH |
| 5 | nipple + areola כצורות, Cooper's ligaments | אין |
| 6 | 5–10 ליטר לדף "unlabelled soft tissue" | מחליף Z organs/muscles שהותאמו קטן מדי או בהיסט |
| 7 | 16 vessels + 9 bursae בתוך עצם | פגם בגאומטריה של Z-Anatomy עצמה |

---

## 2. טבלת העל — שמונת המקורות

| # | מקור | תוכן | מין וסובייקט | כיצד נוצר | פורמט וגודל | רישיון + ציטוט נדרש | נגיש מכאן | סוגר פער | פסק דין |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **BodyParts3D** (DBCLS) `dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html` | release 4.0: 2,906 חלקים ב-IS-A tree + 1,369 ב-PART-OF tree, FMA-named | **Homo sapiens, גוף שלם אחד, גבר מבוגר** | סגמנטציה של מודל גוף שלם של גבר מבוגר אחד (DBCLS/Anatomography) | OBJ בתוך `isa_BP3D_4.0_obj_99.zip` (136 MB) + `partof_BP3D_4.0_obj_99.zip` (62 MB); **polygon reduction rate = 99%** | **CC BY 4.0 International** — שונה מ-CC BY-SA 2.1 Japan ב-**2025-02-27** (ראו §4). ייחוס מחויב מילה במילה: "BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International". DOI 10.18908/lsdba.nbdc00837-000; מאמר: Mitsuhashi N, Fujieda K, Tamura T, Kawamoto S, Takagi T, Okubo K. *BodyParts3D: 3D structure database for anatomical concepts.* Nucleic Acids Res. 2008 | **כן** (200) | **אף אחד** | **דחייה לייבוא גאומטריה** — 0 peripheral nerves, 0 nails, 0 nipple/areola. הדלתא היחידה מול ה-pin שלנו היא `mons pubis`/`perineum`/`anal part of perineum` — שלושתם מגוף **גברי**, וה-`perineum` נמדד כסמן אזור של 368 faces בגודל 2 ס"מ ולא כמשטח עור (§4a). **אבל שינוי הרישיון הוא ההישג האמיתי של הסקר** |
| 2 | **Z-Anatomy / Models-of-human-anatomy** (upstream) | HEAD `7b91976`, commit 2026-11-02 00:33 ("Mise à jour automatique depuis Export"). `Z-Anatomy.zip` 86.7 MB → `Startup.blend` 306.8 MB: **7,374 OB / 3,549 ME** datablocks. בנוסף `Z-Biomechanics.7z` 21.6 MB, `TA2.csv` 1.5 MB | נגזר מה-BodyParts3D הגברי + תוספות Z-Anatomy; **אין מודל נשי** | מודלינג ב-Blender על בסיס BP3D + מקורות נוספים | `.blend` בתוך `.zip` | **CC BY-SA 4.0**. ה-`License.txt` מחייב **שני** ייחוסים: "BodyParts3D - The Database Center for Life Science - CC-BY-SA 2.1 Japan" (‏**מיושן** — BP3D הוא CC BY 4.0 מאז 2025-02-27) ו-"Z-Anatomy - The libre 3D atlas of anatomy - CC-BY-SA 4.0". מצהיר גם על רכיבי **CC-BY-NC-SA 4.0** (inner ear, Dundee) ו-**CC-BY-NC 4.0** (kidney, Lissie Cowley) | **כן** — `github.com` חסום ב-HTTPS אך `git clone` דרך ה-proxy עובד | **אף אחד חדש** | **דחייה — אין שינוי; להשאיר את ה-pin `6c7f9016`.** הדלתא מול ה-pin: 244 שמות, וכולם רעש בינארי / muscle-insertion objects / helper collections. **0** אובייקטים חדשים ב-nerve / perineum-female / nail-pulp / breast / bursa. המילים `Mons pubis`, `Nipple`, `Areola`, `Nail bed`, `Clitoris`, `Labium`, `Vagina`, `Uterus`, `Ovary`, `Cooper` **מופיעות ב-blend כטקסט מינוח/הגדרות בלבד** — לאף אחת מהן אין datablock מסוג `OB`/`ME` (נבדק עם ה-prefix). ה-`TO DO List` עדיין רושם "CREATE A FEMALE HUMAN MODEL" תחת MIDTERM |
| 3 | **sparc.science** (הפורטל) | שכבת תצוגה מעל Pennsieve; קונסורציומים: SPARC, NIH PRECISION Human Pain, HEAL RE-JOIN, VITAL | רב-מיני | — | — | פר-dataset (ראו §3) | **כן** (200) | דרך dataset 692 בלבד | ראו §3 |
| 4 | **Pennsieve Discover / dataset 512** | 512 = *Human vagus nerve anatomical reconstruction using microCT and immunohistochemistry - f008*: 3.96 TB, microCT + IHC של **vagus nerve** | **Homo sapiens** | microCT + IHC של עצב וגאלי מגופה | zarr/tiff/czi | **CC BY**; DOI 10.26275/gpmp-nogs | **כן** | **אף אחד** | **דחייה** — vagus, לא גפה תחתונה ולא אגן. הקטלוג המלא נבדק בנפרד (§3) |
| 5 | **models.physiomeproject.org/e/d71** | *Generic human spinal nerves scaffold* — **אותו פריט** כמו SPARC dataset 445. workspace `d48`, changeset `39e222b0835b`. מכיל **רק** את קובץ ה-provenance של ה-mapping tool, לא גאומטריה | "average human", **לא subject-specific** | scaffold פרמטרי שנבנה ב-MAP Client (ABI), אוסף של DRG scaffolds | provenance JSON + `.proj`; הגאומטריה עצמה יורדת מ-SPARC | אין הצהרת רישיון בדף ה-workspace; העותק הקנוני ב-SPARC הוא CC BY; DOI 10.26275/s0po-usdk | **כן** (200) | **אף אחד** | **דחייה — כפילות של מקור 3/4, וללא גאומטריה**; וה-scaffold עצמו generic (ראו §3) |
| 6 | **bioRxiv** `10.64898/2026.03.18.712572v1` | לא ניתן לקבוע | — | — | — | — | **לא** | — | **לא אומת — אין ציטוט** (ראו §5) |
| 7 | **Zygote** `zygote.com/poly-models/3d-female-systems` | 15 מודלים נשיים. הרלוונטיים: Integumentary (128,380 tris, $690, כולל skin/nails/hair/eyes), Reproductive (134,444 tris, $1,050, כולל Mammary glands/Ducts/Vagina/Uterus/Ovaries/Fallopian tubes), Nervous (1,171,150 tris, $3,230) | "female" מסחרי, לא סובייקט מזוהה | **בלשון Zygote עצמה**: Integumentary — "generated from **laser scans of live models**"; Reproductive — "carefully developed from **photographic and illustrative atlases**"; Nervous — "**digitized from physical models**" | 3ds Max / Blender OBJ / C4D / generic OBJ / Maya; הורדה | **קנייני, כל הזכויות שמורות** ל-Zygote Media Group, Inc.; חומרי האתר מותרים "solely for your own informational, **non-commercial** use"; המוצר "governed exclusively by the license terms accompanying the file or product" — תנאים אלה **אינם מפורסמים** | **כן** (200) | תאורטית 2, 3, 4, 5 | **דחייה כפולה.** (א) רישיון: בתשלום, קנייני, תנאי המוצר לא פומביים → החלטת בעלים. (ב) **ופרובננס**: ה-Reproductive מפוסל מאטלסים וה-Nervous "digitized from physical models" — זה בדיוק מה ש-Q297 הסיר. גם אם ישולם, אסור להציגם כגאומטריה אמיתית. ה-Integumentary הוא היחיד מסריקה אמיתית, אך סריקת פני שטח של דוגמנית עומדת אינה מפענחת perineum |
| 8 | **BioDigital** `biodigital.com/product/developer-toolkits` | Viewer API, Content API, iOS SDK, Android SDK. "Embed immersive 3D experiences in your application with our Javascript API" | ~14,000 מבנים (מהערכת 2026-09-09) | — | **אין** מסירת קבצי mesh בשום שכבה | Terms of Service קנייני; viewer מתארח | **כן** (200) | **אף אחד** | **דחייה — ללא שינוי מ-2026-09-09.** נותר viewer/API מתארח; אין tier שמוסר גאומטריה ברת-החזקה |

---

## 3. SPARC / Pennsieve — הקטלוג נבדק במלואו

`api.pennsieve.io/discover/datasets` הוחזר בעימודים: **615 datasets מפורסמים** ב-22 ארגונים —
SPARC 217, SPARC Consortium 203, Penn CNT 119, NIH PRECISION Human Pain Network 17,
Publishing Collections 10, **IT'IS Foundation 10**, **RE-JOIN 6**, ועוד.
סינון לפי מילות מפתח של גפה תחתונה/אגן: **50 התאמות, מהן 5 אנושיות.**

| id | שם | מין | רישיון · DOI | גאומטריה? | סוגר פער? |
|---|---|---|---|---|---|
| **692** | Mapping the fascicular morphology and organization of the human sciatic nerve via high-resolution microCT imaging | **Homo sapiens** | CC-BY-4.0 · 10.26275/1jdc-qiiv | centerlines + segmentation masks (§3.1) | **חלקית — ראו §3.1** |
| 452 | Human pudendal nerve mapping dataset | Homo sapiens | CC BY · 10.26275/pc8r-r3iu | MRI/CT של אגן לפני ואחרי השתלה + EMG/לחצים; 100,497 קבצים, 23.6 GB. **אין meshes מסופקים** | לא |
| 529 | Mapping neurons in the human inferior hypogastric plexus using large volume imaging | Homo sapiens (גבר, צד ימין) | CC BY · 10.26275/kvbv-lbq7 | 2.44 PB image stacks של בלוקי רקמה (Tuj1/TH) | לא — מיקרוסקופיה, לא מבנה שלם |
| 481 | Ultra-high resolution multi-modal imaging dataset of human cadaveric lumbosacral spinal cord - MRI-CT-DTI | Homo sapiens | CC BY · 10.26275/z4o7-q22u | 27 קבצים, 2.2 GB, ex-vivo 9.4T | לא — חוט שדרה, לא עצבי גפה |
| 289 | Defining neuromechanical mechanisms of Achilles tendinopathy progression | Homo sapiens | CC BY · 10.26275/bcrr-uenq | HDsEMG בלבד | לא |

**REVA** (תוכנית ה-whole-body human nerve imaging): 30 datasets, **29 מהם vagus nerve**
ו-692 הוא היחיד של גפה תחתונה. שאר ההתאמות של גפה תחתונה/אגן בקטלוג הן **rat, mouse,
cat, pig, ferret** — נרשם במפורש כי "much of SPARC is rodent": כל 45 ההתאמות הלא-אנושיות
נפסלות בשער הראשון, *עצב של מכרסם אינו עצב אנושי*.

**RE-JOIN** (6): 5 מכרסם (ביניהם `673` 3D tissue cleared rat knee samples, ODbL) + אחד
transcriptomics אנושי. **NIH PRECISION Human Pain** (17): כולם מולקולריים (DRG proteomics /
snRNA / spatial transcriptomics) פרט לשלושה scaffolds generic. **IT'IS Foundation** (10):
כלי תוכנה ב-MIT, לא גאומטריה.

### 3.1 dataset 692 — הבדיקה המכרעת

| שדה | ערך |
|---|---|
| סובייקט | `sub-SC001` — **Homo sapiens, גבר, 41 שנים, גופה חנוטה (embalmed cadaver)**, Case Western Reserve University |
| רישיון | **CC-BY-4.0** (SPDX מתוך `dataset_description.xlsx`) |
| DOI | `10.26275/1jdc-qiiv` |
| ציטוט נדרש | ה-dataset עצמו + Zhang J, Lapierre-Landry M, Kalpatthi H, Jenkins MW, Wilson DL, Pelot NA, Shoffstall AJ (2026). *Automated 3D segmentation of human vagus nerve fascicles and epineurium from micro-computed tomography images using anatomy-aware neural networks.* J Neural Eng 23, 16010. doi:10.1088/1741-2552/ae33f6 |
| מימון | NIH SPARC OT2OD025349 / 75N98022C00018; VA 1I21RX005151; AFOSR FA9550-23-F-0014 |
| כיצד נוצר | חניטה → צביעת phosphotungstic acid → microCT ב-**11.4 µm isotropic** → סגמנטציה אוטומטית (nnU-Net v2) + tracing ידני של centerlines ו-levels |
| נפח | 116 קבצים, **369.7 GB**; `.zarr.zip` + `.ome.tiff` + `.graphml` + `.csv` |
| דגימות | 6 — `SCL2/3/4` (שמאל) ו-`SCR2/3/4` (ימין), **כל אחת מקטע sciatic nerve באורך ~9 ס"מ** |
| מה יש בגאומטריה | `SingleNerveSegmentation` (מסכות zarr, ~0.43–0.48 GB לדגימה), `NerveMorphology.csv` (area, perimeter, eq_diameter, center, major/minor axis, angle — **לכל slice**), `*-Annotations/*.csv` (centerline tracings), `sciatic_levels.csv` |
| levels אנטומיים | level of formation of sciatic nerve from sacral roots · level of lesser trochanter of femur · +7 ס"מ · +14 ס"מ · +21 ס"מ מתחת ל-lesser trochanter |
| branch points מתויגים | branch to **long head of biceps femoris**, to **semitendinosus** (A ו-B), to **semimembranosus**, to **adductor magnus** |
| **common fibular / peroneal nerve** | **אינו קיים בדאטהסט** — כל חמשת הענפים המתויגים הם ענפי ה-tibial division ל-hamstrings |

**והנתון שמכריע את הכל:** הדגימות הן מקטעי עצב **שנכרתו והונחו ישרים בסורק**.
מדידה ישירה של ה-centerline של `SCL2`: 7,465 נקודות, **מפתח צירי 84.8 מ"מ, אורך קשת
85.1 מ"מ, ונדידה רוחבית 1.0 × 1.3 מ"מ בלבד**. כלומר ה-centerline מתאר קו ישר בחלל
הסורק — **לא את מסלול העצב בגוף**. הקוטר האמיתי שנמדד: eq_diameter ממוצע ~6.8 מ"מ.

מכאן: 692 מספק **קליבר וחתך רוחב אמיתיים של sciatic nerve אנושי בגבהים אנטומיים
מוגדרים**, אך **אפס מידע על המסלול התלת-ממדי בגוף**. לרשום אותו על השלד של דף שלנו
היינו חייבים לחבר את המסלול בעצמנו מהשלד ומהספרות ולקחת מ-SPARC רק את העובי — כלומר
**צורת המבנה, הדבר שהאטלס מציג, הייתה שלנו ולא של SPARC**. זה בדיוק מחלקת הדברים
ש-Q297 הסיר. לכן: **לא מיובא כגאומטריה.**

### 3.2 SPARC scaffolds — למה כולם נפסלים

19 datasets "human scaffold/whole-body", כולם CC BY, וכולם מצהירים במפורש שאינם
subject-specific:

| dataset | DOI | מה מסופק | ציטוט הפרובננס שלו |
|---|---|---|---|
| **445** Generic human spinal nerves scaffold | 10.26275/s0po-usdk | 12.3 MB, **כולל `spinalNervesHuman_zinc_graphics.stl` 5.2 MB + `_root.vtk` 2.0 MB** — גאומטריה מיוצאת אמיתית | "The generic scaffold is **not subject/sample specific** but represents an **average** human spinal nerves" |
| **307** A 3D human whole-body model with integrated organs, vasculature, musculoskeletal and nervous systems | 10.26275/bbvg-gj86 | 381.7 MB, 416 קבצים | "The fiducials for the nerves are **placed by best guess** into the human body **using literature** to check and verify the location"; וה-vasculature "obtained from **Anatomography**" = BodyParts3D, **שכבר בידינו** |
| 134 / 156 / 182 Human whole-body (+organs) | 10.26275/qq9z-e96l ועוד | `.exf` (Zinc) | "The body scaffold is **not subject/sample-specific**" |

**פסק דין:** 445 הוא spinal nerves ברמת ה-roots/DRG, לא עצבי גפה, ובכל מקרה generic;
307 הוא נרתיק ה-worst case — עצבים ש"הונחו בניחוש מיטבי לפי ספרות". שניהם היו חייבים
תג **rule-based** ואינם סוגרים את פער 1. 307 גם היה מכניס עותק שני של BodyParts3D
תחת רישיון סותר.

---

## 4. ההישג האמיתי של הסקר: BodyParts3D עבר ל-CC BY 4.0

דף הרישיון הרשמי `dbarchive.biosciencedbc.jp/en/bodyparts3d/lic.html`
(עודכן לאחרונה **2025-02-27**) אומר מילה במילה:

> "The license for this database is specified in the **Creative Commons Attribution 4.0
> International**. If you use data from this database, please be sure attribute this database
> as follows: *BodyParts3D, © The Database Center for Life Science licensed under
> CC Attribution 4.0 International*."

ו-`update.html` מאשר את התאריך: **"2025/02/27 'License' is updated."** (העדכון הקודם של
הרישיון היה 2011/08/25, שהוא ה-CC BY-SA 2.1 Japan שכל התיעוד שלנו מתבסס עליו).
גם דף ה-description מצהיר "License: CC BY", DOI `10.18908/lsdba.nbdc00837-000`.

מה זה אומר:

1. **BodyParts3D עצמו אינו עוד share-alike.** מבנה שנלקח **ישירות** מ-BodyParts3D v4.0
   הוא CC BY 4.0 — תואם לחלוטין, ללא כפיית BY-SA על הנגזרת.
2. **אבל ה-meshes שבידינו לא משתנים.** הם הגיעו דרך Z-Anatomy, ו-Z-Anatomy היא
   CC BY-SA 4.0 על העיבוד שלה; כל התוספות שלה (וביניהן **כל מערכת העצבים ההיקפית**
   ו-`Nail plate`) הן יצירתה ונשארות BY-SA. הכלל ש-BY-SA לא מתמזג עם BY-NC-SA, ו-Option A
   ב-`docs/GEOMETRY_SOURCES.md`, נשארים בתוקף.
3. ה-`License.txt` של Z-Anatomy עצמה **מיושן** — הוא עדיין מייחס ל-BodyParts3D
   "CC-BY-SA 2.1 Japan". זו עובדה שראוי לרשום, לא לתקן בשמם.
4. **זו החלטת בעלים**: האם לגזור מחדש מבנים ממקור BodyParts3D **ישירות מ-v4.0 תחת
   CC BY 4.0** במקום דרך העיבוד ה-BY-SA של Z-Anatomy. זה היה מקטין את משטח ה-share-alike
   של הפרויקט, אך דורש עבודת גזירה מחדש ובדיקת איכות (ה-OBJ הזמינים הם
   "polygon reduction rate = 99%").

---

## 4a. BodyParts3D v4.0 — מה באמת יש בהורדה הפומבית (נמדד, לא הונח)

הורד `partof_BP3D_4.0_obj_99.zip` (64.9 MB, **1,258 קבצי OBJ**). חשוב: שמות הקבצים הם
מזהי **element part** (`FJxxxx`), לא `BPxxxx` ולא FMA — ומבנה בעל שם כמו `perineum` הוא
**הרכבה** של element parts, לפי `partof_element_parts.txt`. זו הפעם הראשונה בפרויקט
שה-mesh עצמו של BodyParts3D נמדד, ולא רק רשימת החלקים.

| מבנה | FMA | element parts | verts / faces | bbox (מ"מ) | מה זה אומר |
|---|---|---|---|---|---|
| `mons pubis` | FMA20218 | FJ2815 | **5,523 / 2,960** | 121.8 × 37.4 × 63.6 | mesh אמיתי ושמיש — אך מגוף **גברי** |
| `perineum` / `anal part of perineum` | FMA9579 / FMA20347 | FJ1450, FJ1450M, FJ2543, FJ2548 | **250 / 368** לכל אחד | **11.5 × 21.8 × 21.3** | **לא משטח perineum.** ארבעה גושים כמעט זהים בגודל ~2 ס"מ (ו-`FJ1450M` הוא שיקוף של `FJ1450`) — סמן אזור, לא עור. perineum אמיתי משתרע על ~10 ס"מ. **פוסל סופית את פער 2 מהמקור הזה** |
| `right femur` (להשוואת רזולוציה) | FMA24474 | FJ3365 | 1,574 / **3,102** | 118.2 × 62.7 × 466.1 | "polygon reduction rate = 99%" פירושו הפחתה **של** ~99%: femur ב-3,102 faces הוא גס מדי לדפים שלנו |
| `skin` (גוף שלם) | FMA7163 | FJ2810 | 102,467 / **203,382** | 666.9 × 292.0 × 1719.5 | היחיד שנשמר ברזולוציה מלאה — משטח עור גוף-שלם אמיתי, CC BY 4.0. לא סוגר פער (יש לנו עור), אך ראוי לרישום |

**מסקנה נוספת:** גם במקומות שבהם BodyParts3D כן מחזיק מבנה, ההורדה הפומבית היחידה היא
ב-99% polygon reduction, ולכן לא שמישה לרזולוציה של האטלס הזה — פרט ל-`skin`.

---

## 5. bioRxiv `10.64898/2026.03.18.712572v1` — מה הוסק, ולמה אין ציטוט

| בדיקה | תוצאה |
|---|---|
| `www.biorxiv.org/content/10.64898/2026.03.18.712572v1` | **429** בכל ארבעת הניסיונות, עם backoff |
| `WebFetch` לאותו URL | **DNS-blocked** — `getaddrinfo ENOTFOUND www.biorxiv.org` |
| `doi.org/10.64898/...` | CONNECT **403** דרך ה-proxy |
| `api.crossref.org/works/10.64898/...` ו-`/prefixes/10.64898` | CONNECT **403** |
| `api.biorxiv.org/details/biorxiv/...` | CONNECT **403** |
| WebSearch ×2 (על ה-DOI המלא ועל מזהה הכתבה) | לא מצא את הפריט |
| האם ה-prefix אמיתי | **כן.** `10.64898` הוא prefix של bioRxiv בפועל — חיפוש החזיר DOI אחֶר, חי, באותו prefix: `10.64898/2026.03.02.709006`. כלומר **ה-prefix אינו חשוד**, בניגוד להשערה הראשונית |
| PubMed / Europe PMC | PubMed אינו מאנדקס preprints של bioRxiv כשגרה, וללא כותרת אין על מה לחפש |

**מסקנה:** מזהה הכתבה הספציפי לא אושר ולא נשלל. ה-prefix תקין, אך הדף עצמו חסום
(429) או לא נפתר. **לא נקבעו כותרת, מחברים, תקציר, רישיון או הצהרת data availability,
ולכן לא נרשם שום ציטוט ושום טענה לא נשענת על המקור הזה.** נדרש או אישור רשת ל-
`www.biorxiv.org`/`doi.org`, או שהבעלים ימסור את הכותרת.

---

## 6. מיפוי פער → מקור: מה כל אחד מהשמונה עושה בפועל

| פער | המקור הטוב ביותר מבין השמונה | סוגר? | למה |
|---|---|---|---|
| **1** lower-limb nerves | SPARC **692** | **לא** | נותן קליבר וחתך אמיתיים של sciatic, אך הדגימות נכרתו והונחו ישרות (85.1 מ"מ קשת, נדידה 1.0×1.3 מ"מ) ⇒ **אפס מסלול בגוף**; ואין בו common fibular/peroneal nerve כלל. BodyParts3D: 55 רשומות "nerve" וכולן cranial/orbital — **אפס** עצבי גפה. SPARC 307/445: generic, ו-307 "best guess ... using literature" |
| **2** female perineal skin | BodyParts3D `perineum` BP10063 / `anal part of perineum` BP10062 / `mons pubis` BP9719 | **לא** | אלה הדלתא האמיתית מול Z-Anatomy, **ושתי סיבות עצמאיות פוסלות אותן**: (א) BodyParts3D הוא **גוף גברי בודד**, ו-perineum גברי אינו female perineal skin — החלפה כזו היא בדיוק הייחוס השגוי שהפרויקט אוסר; (ב) **נמדד**: ה-`perineum` של BodyParts3D הוא ארבעה גושים של **368 faces ו-bbox 11.5 × 21.8 × 21.3 מ"מ** — סמן אזור בגודל 2 ס"מ, לא משטח עור (§4a). Zygote Integumentary הוא סריקת פני שטח של דוגמנית עומדת (בתשלום, קנייני) |
| **3** nails / nail beds / digital pulp | — | **לא** | BodyParts3D: 0 רשומות nail (רק `skin appendage` כקטגוריה ריקה ו-40 phalanges). Z-Anatomy מחזיקה **4** meshes בלבד — `Nail plate.l/.r` ו-`Nail plate (foot).l/.r` (1,380 / 968 faces), שכבר shipped; אין בשום מקור **nail bed** או **digital pulp** |
| **4** ovaries, tubes, vagina, perineum, levator ani | — | **לא** | `levator ani` ו-`pubococcygeus`/`iliococcygeus`/`coccygeus`/`tendinous arch of levator ani` **כבר קיימים** ב-Z-Anatomy (הדלתא שחושבה מול BodyParts3D הייתה ארטיפקט של השם — BP3D כותב `pubococcygeus`, Z-Anatomy `Pubococcygeus muscle`). לשאר אין מקור אמיתי חדש; Zygote Reproductive מפוסל "from photographic and illustrative atlases" |
| **5** nipple, areola, Cooper's ligaments | — | **לא** | אין ב-BodyParts3D, ואין ב-Z-Anatomy HEAD: `Nipple`/`Areola`/`Cooper` מופיעים ב-blend **כטקסט מינוח בלבד**, ללא datablock `OB`/`ME`. היחיד הקיים הוא `Mammary region` (אזור עור, קונטור גברי) |
| **6** unlabelled soft tissue | — | **לא** | אף אחד מהשמונה אינו עוסק בזה |
| **7** vessels + bursae בתוך עצם | — | **לא** | פגם פנימי בגאומטריה של Z-Anatomy; ה-HEAD החדש לא תיקן אותו (0 אובייקטי bursa חדשים) |

---

## 7. דירוג ההמלצות

1. **(לא ייבוא — החלטת בעלים, הפריט הכי בעל ערך) BodyParts3D הוא CC BY 4.0 מאז 2025-02-27.**
   להחליט אם לגזור מחדש מבנים ממקור BodyParts3D ישירות מ-v4.0 תחת CC BY 4.0 במקום דרך
   העיבוד ה-CC BY-SA 4.0 של Z-Anatomy. זה מקטין את משטח ה-share-alike של הפרויקט. דורש
   סבב גזירה ובדיקת איכות בפני עצמו (ה-OBJ הפומביים ב-99% polygon reduction).
2. **(אופציונלי, לא גאומטריה) SPARC 692 כמקור מדידה.** קליבר אמיתי של human sciatic nerve
   בגבהים אנטומיים מוגדרים (level of formation from sacral roots; lesser trochanter; +7/+14/+21 ס"מ),
   משני הצדדים, CC BY 4.0. שימוש כשר: **אימות או כיול** הקליבר של ה-sciatic הקיים מ-Z-Anatomy,
   עם ציטוט ה-DOI. **לא** לבנייה של mesh חדש, כי המסלול יהיה שלנו.
3. **דחייה: BodyParts3D כגאומטריה לפערים** (אין עצבים היקפיים, אין ציפורניים, וה-perineum גברי).
4. **דחייה: Z-Anatomy upstream** — זהה מעשית ל-pin שלנו; להשאיר `6c7f9016`.
5. **דחייה: SPARC 307, 445 ו-Physiome d71** — generic scaffolds, ו-307 מודה ב-"best guess ... using literature".
6. **דחייה: SPARC 512** — vagus nerve, לא גפה תחתונה.
7. **דחייה: Zygote** — בתשלום + קנייני **וגם** מפוסל מאטלסים / "digitized from physical models".
8. **דחייה: BioDigital** — viewer/API מתארח, אין מסירת mesh.
9. **לא אומת: bioRxiv** — 429/403/DNS; אין ציטוט.

**שורה תחתונה: אף אחד משמונת המקורות אינו עומד בכלל "real sources only" **וגם** סוגר
אחד משבעת הפערים. לא יובא דבר, ולא פורסם דף. הסקר הוא התוצר.**

---

## 8. מה דורש פעולת בעלים

נרשם ב-`docs/OPEN_ITEMS_FOR_OWNER.md`:

1. **החלטה:** לגזור מחדש מבנים ממקור BodyParts3D ישירות מ-v4.0 תחת CC BY 4.0 (ראו §4)?
2. **החלטה:** להשתמש ב-SPARC 692 ככיול קליבר ל-sciatic nerve הקיים (ציטוט DOI, ללא mesh חדש)?
3. **אישור רשת:** `www.biorxiv.org` ו-`doi.org` (או מסירת כותרת הפריט) כדי לסגור את §5.
4. **רכישה:** Zygote — גם אם ישולם, ה-Reproductive וה-Nervous נפסלים על פרובננס; רק
   ה-Integumentary ($690) הוא מסריקה אמיתית, ואינו מפענח perineum. **ההמלצה: לא לרכוש.**
5. **הפערים 1–7 נשארים פתוחים.** לפער 1 הדרך המעשית היחידה שנראתה בסקר הזה אינה מקור
   חדש אלא **התאמה (fit) של 24 ה-meshes של fibular nerve מ-Z-Anatomy אל השלד של דפי
   Imaging** — אותו נתיב bone-point registration שכבר מתועד ב-`## Q292`/`## Q295`/`## Q296`.
   זה סבב בפני עצמו, וצריך את אישור הבעלים כי הוא מכניס גאומטריית Z לדפים "imaging-based".
