# Q296 — סקר אטלסי Open Anatomy: מה יש, מה הרישיון, ומה שימושי לנו

**מה נשאל:** הבעלים פתח גישת רשת ל-`www.openanatomy.org` ול-`download.slicer.org` וביקש לקטלג כל אטלס באתר, לבדוק את הרישיון של כל אחד בנפרד, ולהצליב מול מה שחסר בעמודים שלנו — במיוחד המבנים שמופיעים בשמם על כרטיסי "רקמה רכה לא מסווגת" של Q295 (liver, stomach, small bowel, gluteus maximus, vastus intermedius/lateralis, brain, skull) ומה שעוד חסר (ovaries, uterine tubes, vagina, perineum, levator ani, nipple/areola, Cooper's ligaments).

**מצב הרשת בסבב הזה:** `www.openanatomy.org` — 200. `www.slicer.org` — חסום (טקסט הרישיון נקרא מהעתק של Open Anatomy עצמו, `https://www.openanatomy.org/atlas-pages/slicer-license.html`, 200). `github.com` — 400 דרך הפרוקסי (ה-repo ‏`mhalle/spl-brain-atlas` לא נבדק), `raw.githubusercontent.com` — עובד.

**איך נקרא הקטלוג בלי להוריד גיגה-בייטים:** כל אטלס מגיש `atlasStructure.json` (JSON-LD של OABrowser) תחת `/atlases/<path>/atlasStructure.json`, ובו כל ה-Structures, ההיררכיה והנתיב של כל קובץ `.vtk`. כך נקרא הקטלוג המלא של שבעת האטלסים ב-‎~670 KB סך הכול, והורדו רק קבצי המודל הבודדים שנבדקו בפועל. ה-`.zip` המלא נדרש רק למי שרוצה גם את נפח ההדמיה המקורי ואת מפות התוויות.

---

## 1. הטבלה המרכזית — שבעת האטלסים

| אטלס | אזור גוף | מה יש בו (מספר מבנים) | איך נוצר (הדמיה / נבדק) | פורמטים | גודל הורדה | רישיון | ציטוט נדרש | שימושי? ולמה |
|---|---|---|---|---|---|---|---|---|
| **SPL Inner Ear Atlas** (2018-02) | אוזן תיכונה + פנימית, עצם הטמפורל | 14: Labyrinth, Osseous Spiral Lamina, Fenestra Rotunda, Tympanic Membrane, Malleus, Incus, Stapes, Stapedius, Tensor Tympani, Cochlear / Vestibular / Facial Nerve, Internal Carotid Artery, Internal Jugular Vein | flat-panel CT נסיוני, רזולוציית ניגוד גבוה ‎~140 מיקרון, דגימת עצם טמפורלית אחת (אוזן **ימין**). פרויקט משותף DKFZ ‏(Bartling) + SPL ‏(Jakab, Kikinis) | `.vtk` polydata (binary, big-endian) + `.nrrd` (נפח CT ומפת תוויות) | zip 181.3 MiB; המודלים הבודדים 41–628 KB | 3D Slicer License Part B | Gupta R, Bartling SH et al., *AJNR Am J Neuroradiol* 2004;25(8):1417-24 (PMID 15466345); וכן NIH P41 RR013218 / P41 EB015902 + Google Faculty Research Award | **כן — זה מה שיובא.** ארבעה מבנים שאין להם שום מקביל בפרויקט: bony labyrinth, osseous spiral lamina, round window, stapedius. ראו פרק 4 |
| **SPL Liver Atlas** (2014-02) | כבד + בטן עליונה | 23: Liver Segments I, II, III, IVa, IVb, V, VI, VII, VIII (Couinaud); Left / Intermediate / Right hepatic vein; Left / Right branch of portal vein; Caudate veins; Main portal vein; Aorta; IVC; Gallbladder; Stomach; Spleen; Left / Right kidney | CT קליני, פילוח חצי-אוטומטי. SPL + Boston Medical Center (Shaffer, Pujol, Jakab, Kikinis) | `.vtk` + `.nrrd` | zip 37.2 MiB; מודל סגמנט 0.3–1.6 MB | 3D Slicer License Part B | RSNA/AUR/APDR/SCARD Radiology Educational Research Development Award (Shaffer); NIH P41 RR013218 / P41 EB015902 | **כן בעיקרון, נדחה לסבב הבא.** ‏Couinaud segments ו-ורידי/פורטל תוך-כבדיים **אינם קיימים בשום עמוד אצלנו** (יש רק "Hepatic veins" ו-"Hepatic portal vein" כגזעים). מה שחוסם עכשיו: אין באטלס הזה אף עצם, ולכן אין נקודות עצם לרישום — הרישום צריך להיות משטח-כבד-אל-משטח-כבד, וזה מסלול אחר מזה שהסבב הזה בנה ומאומת. ראו פרק 5 |
| **SPL Abdominal Atlas** (2015-09) | בטן ואגן | 94: שלד (Ribs 6–12, Pelvis, Sacrum, T9–L5 + דיסקים), אברים (liver, stomach and duodenum, colon and ileum, gallbladder, pancreas, spleen, kidneys, ureters, renal pelves, adrenals), 19 שרירים (gluteus maximus / medius / minimus דו-צדדי, psoas, iliacus, erector spinae, quadratus lumborum, obliques, rectus abdominis), 34 כלי דם | CT קליני, פילוח חצי-אוטומטי. SPL (Talos, Jakab, Kikinis) | `.vtk` + `.nrrd` | zip 33.2 MiB | 3D Slicer License Part B | NIH P41 RR013218 / P41 EB015902 | **לא.** זה האטלס שהכי "מתאים" לרשימת היעדים (liver, stomach, colon and ileum, gluteus maximus) — ודווקא עליו התשובה שלילית, ראו פרק 3. בקצרה: כל אחד מהמבנים האלה כבר קיים אצלנו **מההדמיה של אותו נבדק** בעמוד ההדמיה שלו; החוסר הוא בעמודי Base/Combined והוא בעיית *התאמה* (fit) של רשתות Z, שהתיקון הנכון לה הוא העברה פנימית מעמוד ההדמיה — לא ייבוא של נבדק שלישי |
| **SPL Knee Atlas** (2015-09) | ברך | 48: 4 עצמות (femur, tibia, fibula, patella), 4 סחוסים, 2 מניסקים, 5 רצועות (ACL, PCL, MCL, LCL, patellar), 14 שרירים (כולל **vastus lateralis** ו-vastus medialis), 7 גידים, 7 כלי דם (כולל genicular arteries), 4 עצבים, Infrapatellar fat body | MRI, פילוח חצי-אוטומטי. SPL (Richolt, Jakab, Kikinis) | `.vtk` + `.nrrd` | zip 77.2 MiB | 3D Slicer License Part B | NIH P41 RR013218 / P41 EB015902 | **לא.** כל 48 המבנים קיימים אצלנו כבר (כולל infrapatellar fat pad, genicular arteries, medial sural cutaneous nerve). `vastus lateralis` כאן הוא רק החלק שבתוך שדה ה-MRI של הברך — קטוע באמצע הירך, ולכן גרוע מהרשת שיש לנו; `vastus intermedius` כלל לא באטלס |
| **SPL Head and Neck Atlas** (2015-09) | ראש וצוואר | 59: 23 עצמות (skull, mandible, hyoid, C1–C7, T1–T5, ribs 1–5, sternum, clavicles), 14 שרירים, 17 כלי דם, 2 סחוסי גרון, 3 בלוטות (parotid ×2, thyroid) | CT — **הנפח הוא ה-MANIX מה-OsiriX DICOM image library**, בהפחתת רזולוציה ל-256×256. מפות התוויות והמודלים: SPL (Jakab, Kikinis) | `.vtk` + `.nrrd` | zip 30.1 MiB | 3D Slicer License Part B — **אבל** ההדמיה היא נתון של צד שלישי, ו-Part B §3 אינו מעניק בה שום זכות | NIH P41 RR013218 / P41 EB015902; ובנוסף תנאי OsiriX / MANIX, שלא נבדקו | **לא — ובמיוחד לא בשביל skull.** גם אם היה מוסיף משהו, זה האטלס היחיד שבו `Part B §3` נוגע ישירות: הגיאומטריה נגזרת מסדרת CT שאינה של Brigham. לא הורד ולא נבדק מעבר לקטלוג |
| **SPL/NAC Brain Atlas** (2017-01) | מוח, ראש וצוואר | 331: המוח כולו לפי היררכיה (rhombencephalon / mesencephalon / prosencephalon, חלוקת היפותלמוס וצרבלום), skin, וכן 8 קבוצות שרירי ראש-צוואר (mastication, extraocular ×12, soft palate ×9, tongue, pharynx, 30 שרירי צוואר), eyeballs | MRI 3T Siemens במרטינוס, מתנדב בריא בן 42, MPRAGE + T2 בקול 0.75 מ"מ איזוטרופי (וגם גרסה 1 מ"מ); תוויות ב-FreeSurfer + פילוח ידני. SPL + MGH + CMA | `.vtk` + `.nrrd` | zip 188.7 MiB | 3D Slicer License Part B | Makris N et al. *Neuroimage* 2013 (היפותלמוס, PMID 23247186); *J Cogn Neurosci* 2003 (PMID 12803969) ו-*Neuroimage* 2005 (PMID 15850732) (צרבלום); NIH P41 RR013218 / P41 EB015902 | **לא בסבב הזה.** האטלס הזה הוא הנכס הגדול באמת (331 מבנים, 0.75 מ"מ) ואין לנו שום מקביל לרמת הפירוט שלו, אבל: (א) ל-Base/Combined אין בכלל `brain` כרשת שלמה — ההוספה היא פרויקט בפני עצמו, לא ייבוא של מבנה בודד; (ב) הרישום היחיד שאפשרי כאן הוא לקופסת הגולגולת, ולעמודי Z יש רק `Frontal bone`/`Parietal bone`/`Temporal bone` כרשתות גנריות מותאמות; (ג) תת-החלוקות של ההיפותלמוס והצרבלום הן עבודה של צד שלישי (CMA) עם ציטוטים נפרדים. מומלץ כסבב נפרד |
| **Mauritanian Anatomy Laboratory Thoracic Atlas** (2021-01) | בית חזה | 34: שלד בית החזה, מערכת נשימה (אונות ריאה), מערכת לב-כלי דם, esophagus | CT ‏Toshiba Prime 80, מטופל בן 38, במרכז הקרדיווסקולרי הלאומי בנואקשוט; פילוח ב-3D Slicer | `.vtk` + `.nrrd` (`Segmentation-flattened.seg.nrrd`) | **ה-zip שבור — 404.** הספרייה עצמה 403, אבל קבצי המודל הבודדים נגישים (למשל `models/aorta.vtk`, 789 KB) | העמוד מצהיר 3D Slicer License Part B | מחברים: Guermazi H, Idriss AM, Yahya T; מוסדות: Anatomy Lab, Faculty of Medicine, University of Nouakchott Al Aasriya; Cardiovascular National Centre, Nouakchott; MACBioIDi (ULPGC) | **לא.** שתי סיבות נפרדות: (1) **בעלות** — האטלס הוא של MAL/UNA ו-CNC, לא של Brigham. ‏Part B הוא רישיון *מ-Brigham בזכויות של Brigham*; ‏§3 אומר במפורש שהוא אינו מעניק זכויות בתוכנה/נתונים של צד שלישי. הצהרת הרישיון בעמוד אינה מחליפה הענקה כתובה מבעלי האטלס, ולכן זו שאלה פתוחה לבעלים אם בכלל רוצים אותו. (2) **תוכן** — כל 34 המבנים קיימים אצלנו |

### הערה חוצה-טבלה על בעלות

ששת אטלסי ה-SPL/NAC נוצרו ב-Surgical Planning Laboratory של Brigham and Women's Hospital ובשיתופי פעולה שלו (DKFZ, MGH, CMA, Boston Medical Center) — כלומר Brigham אכן בעל הזכויות ו-Part B חל עליהם. שני חריגים:

- **SPL Head and Neck** — ה**הדמיה** היא MANIX מספריית OsiriX (צד שלישי). המודלים הם של SPL, אבל הם נגזרת של נתון שאינו שלהם.
- **Mauritanian Thoracic** — האטלס כולו של קבוצה מאוריטנית; Brigham רק מפיץ אותו.

לשני אלה `Part B §3` חל במלוא עוצמתו, ולכן שניהם מסומנים "לא" גם אם התוכן היה מועיל.

---

## 2. הצלבה מול העמודים שלנו

נבדק בפועל על `build/q295` (ששת העמודים הפעילים), לפי שמות המבנים.

| מה שחסר לפי Q295 / הבקשה | מה יש אצלנו עכשיו | מה Open Anatomy מציע | החלטה |
|---|---|---|---|
| liver | `Liver` בכל ששת העמודים. ב-Imaging F/M — מה-CT/קריו של אותו נבדק. ב-Base/Combined — רשת Z (קטנה/מוזזת אחרי ההתאמה) | Abdominal Atlas (`liver`), Liver Atlas (9 סגמנטים) | **לא מחליפים.** החלפת ה-Z בכבד של נבדק CT שלישי גרועה מהעברת הכבד של אותו גוף מעמוד ההדמיה שלו |
| stomach | `Stomach` / `Stomach (wall and contents)` בכל העמודים | Abdominal (`stomach and duodenum`), Liver (`Stomach`) | **לא** — אותו נימוק |
| small bowel | `Jejunum` ב-Base/Combined; ב-Imaging — מההדמיה | Abdominal: `colon and ileum` (מאוחד, לא מפריד דק מגס) | **לא** — גם פחות מפורט ממה שיש |
| gluteus maximus | `Gluteus maximus` בכל העמודים | Abdominal: `left/right gluteus maximus muscle` | **לא** — אותו נימוק |
| vastus intermedius / lateralis | שניהם בכל העמודים | Knee: `vastus lateralis` (קטוע בגובה ה-MRI), אין intermedius | **לא** — גרוע ממה שיש |
| brain | Base/Combined: אין רשת מוח שלמה (יש Midbrain, Hypothalamus, Falx cerebri וכו'). Imaging: מההדמיה | SPL/NAC Brain Atlas, 331 מבנים | **נדחה לסבב נפרד** (פרק 1) |
| skull | Base/Combined: `Frontal bone`, `Parietal bone`, `Temporal bone`, `Occipital bone` וכו' בנפרד | Head and Neck: `skull` כרשת אחת | **לא** — ובפרט בגלל `Part B §3` (MANIX) |
| ovaries, uterine tubes, vagina | קיימים (`Ovary (l/r)`, `Uterine tube (l/r)`, `Vagina`) — ב-Base F / Combined F; המקור HRA | **אין בשום אטלס** של Open Anatomy | אין מה לייבא |
| perineum | `Perineal body (CVH)` ב-Base F / Combined F | **אין** | אין מה לייבא |
| levator ani | `Levator ani` + `Tendinous arch of levator ani` + `Nerve to levator ani` בכל ארבעת עמודי Z | **אין** | אין מה לייבא |
| nipple / areola | `Nipple (l/r)`, `Areola (l/r)` ב-Base F / Combined F | **אין** | אין מה לייבא |
| Cooper's ligaments | **אין בשום עמוד** | **אין בשום אטלס** של Open Anatomy | אין מה לייבא — Open Anatomy לא עוזר כאן |

**ממצא שלילי מרכזי, בפירוש:** באף אחד משבעת האטלסים אין אגן נשי רך (ovaries, uterine tubes, uterus, vagina), אין perineum, אין levator ani, ואין שד (nipple, areola, Cooper's ligaments / suspensory ligaments of the breast). ל-Open Anatomy אין שום אטלס של אגן, של רצפת אגן או של שד. הפערים האלה לא ייסגרו מהמקור הזה.

### ומה כן חסר לנו ו-Open Anatomy כן נותן

| מבנה | יש אצלנו? | מאיפה |
|---|---|---|
| Bony labyrinth (cochlea + vestibule + 3 semicircular canals) | **לא** (אין cochlea, אין semicircular canals, אין vestibule באף עמוד) | Inner Ear Atlas |
| Osseous spiral lamina | **לא** | Inner Ear Atlas |
| Round window (fenestra cochleae) | **לא** (גם oval window אין) | Inner Ear Atlas |
| Stapedius | **לא** | Inner Ear Atlas |
| Tensor tympani | **לא** | Inner Ear Atlas — נדחה, ראו פרק 4 |
| Couinaud liver segments I–VIII | **לא** | Liver Atlas — נדחה לסבב הבא, ראו פרק 5 |
| ורידי כבד וענפי פורטל תוך-כבדיים | רק הגזעים (`Hepatic veins`, `Hepatic portal vein`) | Liver Atlas — אותו דבר |
| Cochlear / vestibular nerve בנפרד | רק `Vestibulocochlear nerve (CN VIII)` כגזע אחד | Inner Ear Atlas — נדחה, ראו פרק 4 |

---

## 3. למה האטלס הבטני נדחה, בפירוט

זה ה"כן" הלא-אינטואיטיבי ביותר שהפך ל"לא", ולכן ההנמקה במלואה:

1. **הכלל של הבעלים:** "אל תחליפו מבנה שכבר בא מההדמיה של אותו נבדק." ב-Imaging F ו-Imaging M, ה-liver, ה-stomach וה-gluteus maximus הם **פילוח של ה-CT/הקריו של אותו גוף**. שם ייבוא אסור מראש.
2. **החוסר האמיתי הוא בעמודי Base/Combined**, ושם המבנים האלה *כן קיימים* — אלא שהם רשתות Z שאחרי ההתאמה יצאו קטנות או מוזזות (זה בדיוק מה ש-Q295 §B מצא: החללים של `soft_unlabelled_*` יושבים במקום שבו עמוד ההדמיה מפלח אותם).
3. **הדרך הזולה והטובה יותר קיימת כבר בפרויקט:** ‏Imaging ו-Combined חולקים את אותו פריים גוף (Q295 §C), ולעמודי Base יש רישום TPS אל ה-Combined של אותו גוף (‏`reg_base_{f,m}.pkl`, חציון ‎~2 מ"מ). כלומר אפשר להעביר את הכבד/הקיבה/הגלוטאוס של **אותה אישה / אותו גבר** לעמודי Base/Combined בלי שום מקור חיצוני.
4. לכן אטלס בטני של **נבדק רביעי** (CT קליני אנונימי) לא עובר את הרף "רק אם זה טוב ממה שאנחנו כבר שולחים": הוא מחליף גיאומטריה גנרית בגיאומטריה של אדם אחר, במקום בגיאומטריה של האדם שהעמוד מתיימר לתאר.

**המסקנה המעשית לסבב הבא:** התיקון ל-`soft_unlabelled_*` הוא refit/העברה פנימית (כפי ש-Q295 §I כבר כתב), לא ייבוא. הסבב הזה לא נגע בהם.

---

## 4. מה יובא בפועל — SPL Inner Ear Atlas

נבחן אחד-אחד, ברישום לעצמות השמע של כל עמוד (ראו `scripts/anatomy/q296/reg296.py` והדוח המלא ב-`data/derived/Q296_ear_report.json`).

| מבנה באטלס | יובא? | נימוק |
|---|---|---|
| Labyrinth | **כן** | אין מקביל. 0.204 סמ"ק, ‎9.8×16.3×18.7 מ"מ — טווח ספרותי של bony labyrinth |
| Osseous Spiral Lamina | **כן** | אין מקביל |
| Fenestra Rotunda | **כן** | אין מקביל |
| Stapedius Muscle | **כן** | אין מקביל |
| Malleus / Incus / Stapes Bone | לא — **נקודות הרישום** | קיימים בכל עמוד; הם מה שהרישום נסמך עליו |
| Tympanic Membrane | לא | קיים (`Tympanic membrane`) |
| Tensor Tympani Muscle | **לא — נכשל בבדיקת החדירה** | ‎51.5% מנפחו אחרי הרישום נופל בתוך ה-`Articular disc of temporomandibular joint` של העמוד, ועוד 19% בתוך ה-Mandible (מבחן קודקודים). מעל סף החפיפה שהפרויקט מקבל (‎~2% חציוני, ‎12% מקסימום ב-Q295) |
| Cochlear Nerve / Vestibular Nerve | **לא** | חפיפה אפס עם כל שכן (נקיים לגמרי), אבל ה-`Vestibulocochlear nerve (CN VIII)` של העמודים נעצר ‎13.5–22 מ"מ *מדיאלית* להם (הוא המקטע הציסטרנלי בלבד). להוסיף אותם היה מייצר שני גדמי עצב מרחפים במרחק 14 מ"מ מהגזע. ממתין לסבב שישלים את המקטע התוך-תעלתי |
| Facial Nerve | **לא** | קיים (`Facial nerve (VII)`); של האטלס מתמשך חוץ-גולגולתית וחודר 7.2% לתוך ה-Digastric |
| Internal Carotid Artery / Internal Jugular Vein | **לא** | קיימים |

### הערה על קנה המידה של האטלס

קואורדינטות המודלים של האטלס הן **גדולות פי ‎~3.15 מהחיים** באופן אחיד (מפות התוויות עברו meshing עם הרזולוציה הנומינלית של הסורק ולא עם הווֹקסל של ה-140 מיקרון). זה לא פוגם בכלום: איבר הסקלה של טרנספורם הדמיון מחזיר אותו, והראיה שזו סקלה גלובלית אחת ולא עיוות היא ששארית הרישום יצאה **זהה עד חמש ספרות אחרי הנקודה בכל עמוד ובכל צד** (0.31776), ושכל ארבעת הנפחים אחרי הסקלה נופלים בטווח האנטומי: labyrinth 204 ממ"ק (ספרות: ‎~190–230), malleus 13.1, incus 15.8, stapes 1.8 ממ"ק.

### Part B — מה אנחנו חייבים בגלל הייבוא

- **טקסט Part B במלואו**, עם ההקדמה המחויבת ("All or portions of this licensed product…"), ב-`third_party/openanatomy_spl/LICENSE` (כל ה-Agreement, Part A+B+C, כפי ש-Part B דורש).
- **שימור כל הייחוסים וההודעות**: `third_party/openanatomy_spl/NOTICE` (מחברים, מוסדות, ציטוט Gupta/Bartling 2004, מספרי המענקים).
- **סימון השינויים שלנו** כנדרש ב-Part B §1(d): `third_party/openanatomy_spl/README.md` מפרט את חמשת השינויים (רישום דמיון, תיקון הסקלה, decimation ל-40%, שיקוף לצד השמאלי, שמות חדשים), וכל כרטיס מבנה אומר אותו דבר בקצרה.
- **אי-שימוש בשמות כהמלצה** (Part B §6): השמות מופיעים רק כייחוס.
- **שימוש מחקרי בלבד** (Part B §4): תואם את תג "סימולציה, לא לשימוש קליני" שכבר על כל עמוד.
- **§3 — נתוני צד שלישי**: לאטלס האוזן אין מקור צד-שלישי (ההדמיה היא של DKFZ/SPL עצמם). נבדק פרטנית, ראו פרק 1.

---

## 5. למה ה-Couinaud segments נדחו לסבב הבא

הם עוברים את רף התוכן בבירור — אין בפרויקט שום חלוקת סגמנטים של הכבד ואין ורידים/פורטל תוך-כבדיים. מה שחוסם עכשיו הוא הרישום:

- ה-SPL Liver Atlas **לא מכיל אף עצם**. לכן "הרישום לנקודות העצם של העמוד" שהבריף מחייב לא ישים עליו ישירות.
- הרישום הנכון כאן הוא משטח-כבד-אל-משטח-כבד (הסגמנטים צריכים לרצף את הכבד הקיים בדיוק), ולא רק לייעד transform — צריך גם לחתוך/להתאים את הגבולות כך שסכום הסגמנטים = הכבד של העמוד. זה מסלול שונה ממה שנבנה ואומת בסבב הזה.
- ובעמודי ההדמיה הכבד הוא של אותו נבדק, כך שהסגמנטים יצטרכו להירשם אל **שלושה כבדים שונים** (שלה, שלו, ו-Z).

ההמלצה: סבב נפרד, עם רישום משטחי מאומת ובדיקת "סכום הסגמנטים = הכבד" כקריטריון. הרישיון זהה (Part B, Brigham-owned), כך שאין מכשול רישויי.

---

## 6. סיכום בשורה אחת

מתוך שבעה אטלסים: **אחד נוצל** (Inner Ear — ארבעה מבנים שלא היו לנו בכלל), **אחד מומלץ לסבב הבא** (Liver — Couinaud), **אחד מומלץ כפרויקט נפרד** (Brain), **שלושה נדחו כי כל תכולתם כבר קיימת אצלנו, ולרוב ממקור טוב יותר** (Abdominal, Knee, Thoracic), **ואחד נדחה גם מטעמי רישוי** (Head and Neck — נגזר מ-MANIX, `Part B §3`). הפערים שהבעלים ציין במפורש — אגן נשי, perineum, levator ani, שד ו-Cooper's ligaments — **אינם קיימים באף אטלס של Open Anatomy** ולא ייסגרו מהמקור הזה.
