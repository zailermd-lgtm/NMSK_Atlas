# Q307 — ביקורת מקום של העצבים בכל ששת הדפים (nerve placement audit)

**התאריך:** 2026-11-03. **הבסיס:** `build/q304`. **הפלט:** `build/q307`, שישה דפים שפורסמו.
**הדיווח של הבעלים (מצוטט):** «lateral antebrachial cutaneous nerve — לא במקום!! הכל חייב להיות קיים ובמקום הנכון».

כל המספרים כאן נמדדו על הגיאומטריה של הדפים עצמם. מרחקים הם **surface-to-surface** על דגימות משולשים משוקללות-שטח
(לפחות נקודה אחת לכל mm², קודקודים תמיד בפנים) ולא vertex-to-vertex: Q298 מדד ש‑69.3 % מהמשולשים בדף Z הם בעלי צלע
ארוכה מעל 3 mm, ו‑Q304 רשם שמספר vertex-to-vertex בין רשתות בצפיפות שונה הוא מחמיא ושגוי.

---

## 0. התשובה בשורה אחת

העצב **נמצא** בקומפרטמנט הנכון, בצד הנכון, בעומק הנכון ומחובר להורה הנכון — אבל **רק שני השלישים הפרוקסימליים שלו
קיימים**: הוא נעצר 53.8–73.5 mm לפני שורש כף היד, בלי חלוקה ל‑anterior ו‑posterior branch; ובשני דפי ה‑Imaging הוא
**לא היה קיים בכלל**, יחד עם עוד 95 עצבים. Q307 העביר אותו (ועוד 57 / 60 עצבי גפה עליונה) מדף ה‑Combined של **אותו
גוף**, תיקן שלושה עצבי גפה תחתונה ש‑Q304 השאיר כגדם בצד אחד, ורשם את הקיצור שנשאר על הכרטיס עצמו עם שני המקורות.

---

## 1. הממצא השגוי שכמעט דווח, והמדידה שהרגה אותו

בדיקת inside/outside לא-מכוילת על voxel solid אמרה ש‑**48–65 % מהעצב "בתוך ה‑brachioradialis"** — כלומר קבור בבטן
השריר. **זה לא נכון.** ה‑voxel solid **מנופח**: על `brachioradialis_l` בדף base_m המסכה היא 116.7 cm³ מול 93.8 cm³
של הרשת עצמה, וקובייה של 20 mm יוצאת 9.26 cm³ מול 8.0 אמיתיים.

`place307.py` מודד עכשיו את **הניפוח של כל מסכה מהגבול שלה עצמה** מול דגימות פני השטח שלה (`offset_mm`, 1.28–1.35 mm
על השרירים האלה) וסופר דגימה כ"בפנים" רק מעבר ל‑offset + 2 mm. תחת הכלל הזה העומק המקסימלי של העצב בתוך
ה‑brachioradialis הוא **1.75–2.67 mm מול offset של 1.28–1.35 mm** — חדירה אמיתית של ~0.4–1.3 mm. העצב **נצמד**
לשריר, לא קבור בו. זה בדיוק סוג ה‑false offender ש‑Q299 בנה per-bone masks כדי להימנע ממנו, ולכן הוא לא חוזר כאן.

**וזה גם מה שהספרות אומרת שצריך לקרות:** Khadanovich 2023 (93 אמות גוויה) — «The medial border of the
brachioradialis muscle was observed less than 1.8 mm from the LACN», ושהעצב נשאר קרוב «within the whole length of
the brachioradialis muscle». Qawasmi 2024 (28 גפיים טריות) — «It was deep to the forearm superficial fascia in all
cadavers», באותו מישור deep fascia כמו ה‑antebrachial vein. לכן גם העובדה שהעצב **אינו** בשומן התת-עורי היא
**נכונה** ואינה פגם.

---

## 2. המקורות שנקראו בסבב הזה (PubMed MCP)

| מקור | n | מה נלקח ממנו |
|---|---|---|
| Qawasmi F, MacLeod J, AbuHamdia A, Grindel SI, Yassin M. *Anatomy of the Lateral Antebrachial Cutaneous Nerve: Landmarks for Procedures in the Cubital Fossa.* J Hand Surg Am 2024;50(7):882.e1-882.e5. PMID **38934998**, doi **10.1016/j.jhsa.2024.04.018** | 28 גפיים עליונות טריות | יוצא **lateral** ל‑biceps tendon בכל הגוויות; **deep to the forearm superficial fascia** בכל הגוויות; LE→עצב בקו הבין-אפיקונדילרי **24.5 ± 7.2 mm**; 6.3 ± 3.1 mm מדיאלית ל‑BR בגובה ה‑LE; מתיישר עם הגבול המדיאלי של ה‑BR ‑68 mm דיסטלית ל‑IEL; באותו מישור fascia כמו ה‑antebrachial vein, 47.6 ± 5 mm (37–55) מה‑LE; שני ענפים ב‑82.1 % |
| Khadanovich A, Benes M, Kaiser R, Herma T, Kachlik D. *Clinical anatomy of the lateral antebrachial cutaneous nerve: Is there any safe zone for interventional approach?* Ann Anat 2023;252:152202. PMID **38128746**, doi **10.1016/j.aanat.2023.152202** | 93 אמות גוויה | **פחות מ‑1.8 mm** מהגבול המדיאלי של ה‑BR, לכל אורך ה‑BR; מתחלק ל‑anterior + posterior ב‑**76/93 (81.7 %)**, במרחק ממוצע **47.8 ± 34.2 mm** דיסטלית ל‑IEL; נקודת היציאה נמצאה דיסטלית, פרוקסימלית **או** בגובה ה‑IEL; חוצה את ה‑SBRN ב‑86 % מהגפיים, מתחבר אליו ב‑71 %; מספק את גב כף היד ב‑39.8 % |
| Tagliafico AS, Michaud J, Marchetti A, Garello I, Padua L, Martinoli C. *US imaging of the musculocutaneous nerve.* Skeletal Radiol 2010;40(5):609-16. PMID **20931188**, doi **10.1007/s00256-010-1046-6** | 3 גפיים גוויה + 15 נבדקים | ההורה: ה‑MCN «can be reliably identified from the axilla through the elbow, **including the lateral antebrachial cutaneous (LAbC) nerve**» |

ההורה הזה **לא היה** ברג'יסטרי העצבים של הפרויקט (`data/nerves/*.json`, 312 ישויות עם `parent_id`), ולכן בדיקת
הרציפות של Q307 לא היה לה הורה בדיוק לעצב שהבעלים דיווח עליו. הוא נוסף ב‑`data/anatomy/nerve_parents_q307.json`
עם המקור, ביחד עם שני הענפים שאינם קיימים כרשת באף דף — כדי שהחֶסֶר יהיה רשום ולא מרומז.

---

## 3. הכלים, ומה כל אחד מודד

| כלי | מה הוא מודד | למה דווקא ככה |
|---|---|---|
| `scripts/anatomy/q307/place307.py` | עומק בתוך שריר (מכויל), רציפות עם ההורה, צד | עומק ולא דגל inside/outside, מהסיבה בסעיף 1 |
| `scripts/anatomy/q307/asym307.py` | אי-התאמה צד/מקור בדפי ה‑Imaging | אורך נמדד על הציר הראשי של הרשת עצמה, כי bbox מגזים כשהגפה אלכסונית |
| `scripts/anatomy/q307/xfer307.py` | ההעברה מדף ה‑Combined | identity + thin-plate-spline, **שדה אחד לכל אזור** |
| `scripts/anatomy/q307/val307.py` | אימות על הדף המוחלף, לפני שנבנה דף | מסכת הגוף ומסכות העצם המאומתות של Q299 |
| `scripts/anatomy/q307/rig307.py` | ה‑pose rig | הטלאה של Q304, מורחבת גם לאינדקסים שהוחלפו |
| Q299 `contain299.py` / Q298 adjacency | הכלה בגוף, חדירה לעצם, מגע | כלים שאומתו בסבב שלהם; לא נבנו מחדש כאן |

**שתי טעויות שלי שהמדידה תפסה, ושתיהן רשומות במקום שבו קרו.** (1) `offset_mm` חושב בגרסה הראשונה כעומק של דגימות
פני השטח עצמן — שהוא 0 בהגדרה, כי השכן הקרוב שלהן הוא הן עצמן; נתפס כשקובייה של 20 mm דיווחה offset 0.0 למרות מסכה
של 9.26 cm³. (2) ההעברה הורכבה בהתחלה עם **שדה הגפה העליונה בלבד**, גם לתיקון הגפה התחתונה — אקסטרפולציה: העצב
הטיביאלי הימני ב‑Imaging M נחת אז **53.5 mm** מהעצבים הפלנטריים שלו וה‑Imaging F השמאלי **89.8 mm**, מול 0.0 mm
בצדדים ש‑Q304 עשה עם השדה התחתון שלו. נתפס על ידי `val307`, לא על ידי קריסה.

---

## 4. העצב שהבעלים דיווח עליו — כל המספרים

### A. LACN per page/side

| page | side | t span (0=radial head, 1=distal radius) | short of the wrist (mm) | radial coord p50 (mm) | ulna axis (mm) | d brachioradialis p50 (mm) | d musculocutaneous (mm) | prox end distal to the IEL (mm) |
|---|---|---|---|---|---|---|---|---|
| base_m | L | +0.005 .. +0.691 | 73.5 | 18.2 | -23.4 | 1.05 | 0.02 | 14.6 |
| base_m | R | +0.005 .. +0.691 | 73.5 | 18.1 | -23.4 | 1.03 | 0.05 | 14.6 |
| base_f | L | +0.009 .. +0.684 | 70.2 | 15.9 | -21.9 | 0.99 | 0.02 | 14.5 |
| base_f | R | +0.009 .. +0.684 | 70.2 | 15.9 | -21.9 | 0.95 | 0.04 | 14.4 |
| comb_m | L | -0.026 .. +0.678 | 53.8 | 12.8 | -28.6 | 1.15 | 0.57 | 25.1 |
| comb_m | R | -0.041 .. +0.685 | 56.9 | 13.6 | -25.1 | 1.48 | 0.69 | 27.0 |
| comb_f | L | +0.079 .. +0.680 | 59.6 | 13.3 | -22.2 | 2.08 | 1.41 | 16.5 |
| comb_f | R | +0.064 .. +0.644 | 63.8 | 9.0 | -22.4 | 1.47 | 0.31 | 27.4 |
| own_m | L | -0.124 .. +0.695 | — | 15.0 | -27.4 | 1.89 | 21.68 | — |
| own_m | R | -0.030 .. +0.738 | — | 11.5 | -26.4 | 4.31 | 0.56 | — |
| own_f | L | +0.029 .. +0.715 | — | 11.5 | -25.1 | 1.82 | 14.57 | — |
| own_f | R | -0.068 .. +0.640 | — | 9.5 | -27.0 | 7.61 | 15.84 | — |

### B. cutaneous nerves inside a muscle belly, ranked

| # | page | nerve | total frac in muscle | worst muscle | frac | p95 depth (mm) | max depth (mm) | mask offset (mm) | calibre (mm) |

**הקריאה:** `t` הוא המקום על הציר הראשי של ה‑radius של הדף עצמו — 0 = ראש הרדיוס (המרפק), 1 = הרדיוס הדיסטלי
(שורש כף היד). `radial coord` חיובי = רדיאלי (לטרלי) מציר הרדיוס; ציר האולנה רשום לידו כקנה מידה.

**מה נכון, בכל שמונה הגפיים:** הצד (radial coord +9.0 עד +18.2 mm כשציר האולנה ב‑−21.9 עד −28.6); הרציפות עם
ה‑MCN על ארבעת דפי ה‑Z (0.02–1.41 mm); העומק מול ה‑brachioradialis (חציון 0.95–2.08 mm על דפי ה‑Z, בתוך
ה‑«less than 1.8 mm» של Khadanovich); רכיב מחובר אחד, בלי מקטע מרחף.

**מה שגוי, בכל שמונה הגפיים:**

1. **הוא נעצר באמצע האמה.** `t_max` = 0.640–0.738, כלומר **53.8–73.5 mm לפני** הרדיוס הדיסטלי של הדף עצמו
   (base_m 73.5, base_f 70.2, comb_m 53.8 / 56.9, comb_f 59.6 / 63.8). השליש הדיסטלי של המהלך, הטריטוריה של שורש
   כף היד וה‑thenar — אינם קיימים.
2. **אין לו anterior branch ואין posterior branch** באף דף, מול 81.7 % ב‑93 אמות אצל Khadanovich. הדפים כן נושאים
   את ה‑anterior **וה**‑posterior branch של ה‑**medial** antebrachial cutaneous nerve, ואף אחד מהם ללטרלי. גם
   ה‑superficial branch of the radial nerve, שחוצה אותו ב‑86 % מהגפיים, **כן קיים** — ‏**Q308 מדד זאת והטענה הזאת כאן שגויה**: הוא נשלח בששת הדפים כ‑`radial_n_superficial_branch_l/r` (ראו `docs/research/Q308_built_structures_and_validation.md` §9). ושני הענפים של ה‑LACN **נבנו ב‑Q308** rule-based, ולכן גם המשפט «אין לו anterior branch ואין posterior branch באף דף» נכון לגרסה שלפני Q308 בלבד.
3. **הקצה הפרוקסימלי לא מגיע לקו הבין-אפיקונדילרי:** הוא מתחיל **14.4–27.4 mm דיסטלית** למישור ה‑IEL שנבנה
   מהקונדילים של הדף עצמו. Khadanovich מצא נקודת יציאה «distally, proximally or at the level of the IEL», ולכן
   **זה בתוך השוני המדווח** ונרשם כנתון, לא כשגיאה. המספר שלנו ל‑LE→עצב (33.7–47.9 mm מול 24.5 ± 7.2) נמדד
   בנקודת ההתקרבות המקסימלית למישור שהעצב **אינו חוצה**, ולכן **אינו נושא פסק דין** — אותה משמעת ש‑Q299 החזיק בה
   כשסירב להסיק קוטר אצטבולרי מכלל שמודד יותר מהסוקט.
4. **בשני דפי ה‑Imaging הוא לא היה קיים כלל** — 0 מתוך 272 (M) / 308 (F) המבנים שטבלת הקליבר של הדף עצמו רושמת
   כעצבים. ולא רק הוא: כל דף Imaging היה חסר **96 עצבים** שדף ה‑Combined של **אותו גוף** נושא, **33 מהם בגפה
   העליונה ובחגורת הכתף**.

**למה הקיצור לא פוסל והושאר:** אין בפרויקט גיאומטריה אמיתית לשליש החסר. סקר Q247 על 23 מקורות אפשריים קבע
ש‑Z-Anatomy היא התקרה לגיאומטריית עצבים בעלת רישיון תואם, והמהדורה שלה אינה נושאת שום ענף של העצב הזה. לכתוב את
השליש החסר בעצמנו זה **פיסול**, ו‑Q297 הסיר משטח מיוצר בדיוק מהסיבה הזאת. לכן הוא **כתוב על הכרטיס** עם שני
המקורות ועם המספרים, ומובא לבעלים כהחלטה.

---

## 5. העבֵרה הכללית: עצב עורי בתוך בטן שריר

הכלל: שם שמכיל `cutaneous` הוא, ב‑Terminologia Anatomica, עצב שחודר את ה‑deep fascia ומספק עור — ולכן אינו אמור
לשכב **בתוך** בטן שריר. 95 שורות על ששת הדפים (base_m 14, base_f 12, comb_m 24, comb_f 18, own_m 12, own_f 15);
57 מהן עוברות את הרף לכרטיס (לפחות 5 % מהדגימות ועומק p95 של 5 mm ומעלה).

|---|---|---|---|---|---|---|---|---|---|
| 1 | own_m | `tibial_n_medial_sural_cutaneous_n_r` | 0.847 | `gastrocnemius_r` | 0.3188 | 17.71 | 18.05 | 1.29 | 0.9 |
| 2 | own_m | `tibial_n_medial_sural_cutaneous_n_l` | 0.834 | `gastrocnemius_l` | 0.3457 | 17.79 | 18.32 | 1.29 | 0.93 |
| 3 | own_m | `femoral_n_anterior_cutaneous_branches_r` | 0.724 | `vastus_medialis_r` | 0.5073 | 12.94 | 13.8 | 1.27 | 1.01 |
| 4 | own_m | `femoral_n_anterior_cutaneous_branches_l` | 0.658 | `vastus_medialis_l` | 0.5011 | 12.47 | 13.13 | 1.26 | 1.0 |
| 5 | base_m | `zan_medial_antebrachial_cutaneous_nerve_r` | 0.567 | `biceps_brachii_r` | 0.5672 | 10.2 | 10.9 | 1.33 | 0.99 |
| 6 | base_m | `zan_medial_antebrachial_cutaneous_nerve_l` | 0.568 | `biceps_brachii_l` | 0.5675 | 10.17 | 10.83 | 1.33 | 0.98 |
| 7 | comb_f | `zan_inferior_lateral_brachial_cutaneous_nerve_r` | 0.777 | `biceps_brachii_r` | 0.4555 | 7.42 | 7.51 | 1.41 | 0.61 |
| 8 | own_m | `posterior_femoral_cutaneous_n_l` | 0.454 | `gluteus_maximus_l` | 0.2485 | 12.53 | 13.34 | 1.33 | 2.5 |
| 9 | comb_m | `tibial_n_medial_sural_cutaneous_n_r` | 0.491 | `semimembranosus_r` | 0.4688 | 10.89 | 11.26 | 1.42 | 1.04 |
| 10 | comb_m | `tibial_n_medial_sural_cutaneous_n_l` | 0.438 | `semimembranosus_l` | 0.4175 | 10.24 | 10.97 | 1.35 | 1.06 |
| 11 | own_f | `tibial_n_medial_sural_cutaneous_n_l` | 0.399 | `gastrocnemius_l` | 0.2751 | 10.75 | 11.17 | 1.54 | 0.9 |
| 12 | own_m | `posterior_femoral_cutaneous_n_perineal_branch_l` | 0.545 | `obturator_internus_l` | 0.3243 | 7.78 | 8.22 | 1.31 | 0.99 |
| 13 | comb_f | `zan_inferior_lateral_brachial_cutaneous_nerve_l` | 0.477 | `zan_lateral_head_of_triceps_brachii_l` | 0.4772 | 8.42 | 8.87 | 1.33 | 0.27 |
| 14 | base_f | `zan_medial_antebrachial_cutaneous_nerve_l` | 0.534 | `biceps_brachii_l` | 0.5344 | 7.39 | 7.78 | 1.34 | 0.95 |
| 15 | base_f | `zan_medial_antebrachial_cutaneous_nerve_r` | 0.503 | `biceps_brachii_r` | 0.5028 | 7.3 | 7.69 | 1.34 | 0.95 |
| 16 | comb_m | `posterior_femoral_cutaneous_n_l` | 0.176 | `gluteus_maximus_l` | 0.0872 | 18.52 | 18.96 | 1.39 | 1.8 |
| 17 | comb_m | `femoral_n_anterior_cutaneous_branches_r` | 0.311 | `vastus_medialis_r` | 0.3101 | 10.42 | 10.84 | 1.35 | 1.06 |
| 18 | comb_m | `posterior_femoral_cutaneous_n_r` | 0.182 | `gluteus_maximus_r` | 0.1001 | 17.49 | 18.23 | 1.44 | 1.4 |
| 19 | comb_m | `femoral_n_anterior_cutaneous_branches_l` | 0.348 | `vastus_medialis_l` | 0.3078 | 8.9 | 9.45 | 1.36 | 1.05 |
| 20 | own_f | `tibial_n_medial_sural_cutaneous_n_r` | 0.317 | `gastrocnemius_r` | 0.189 | 8.29 | 8.65 | 1.65 | 0.94 |
| 21 | own_m | `subcostal_n_anterior_cutaneous_r` | 0.403 | `longissimus_r` | 0.4033 | 6.37 | 6.51 | 1.3 | 0.98 |
| 22 | own_m | `subcostal_n_lateral_cutaneous_r` | 0.401 | `longissimus_r` | 0.4014 | 6.37 | 6.51 | 1.3 | 0.98 |
| 23 | own_f | `perforating_cutaneous_n_l` | 0.234 | `piriformis_l` | 0.1802 | 9.94 | 10.31 | 1.32 | 1.03 |
| 24 | comb_f | `zan_medial_antebrachial_cutaneous_nerve_l` | 0.349 | `biceps_brachii_l` | 0.2257 | 6.3 | 6.44 | 1.35 | 1.13 |
| 25 | comb_m | `perforating_cutaneous_n_l` | 0.128 | `gluteus_maximus_l` | 0.1279 | 17.13 | 17.92 | 1.39 | 1.0 |

Total rows: 95 over six pages; per page base_m=14, base_f=12, comb_m=24, comb_f=18, own_m=12, own_f=15.

### C. side / source mismatch on the Imaging pages (before the fix)

**לא הוזזו.** על דפי ה‑Z זו הגיאומטריה של Z-Anatomy עצמה, ועל דפי ה‑Imaging זו צינורית rule-based או מועברת, ואין
כיוון אחד מוצדק לנתב מחדש 57 עצבים בלי להחליט מחדש את המהלך שלהם ממקור — שאין לסבב הזה. מדווח ולא מטויח, אותה
מדיניות שנקט Q299 ל‑16 כלי הדם ו‑9 הבורסות שנמצאות בעיקר בתוך עצם.

**הקבוצה הגרועה ביותר היא `tibial_n_medial_sural_cutaneous_n`** — על Imaging M 32–35 % מהדגימות בתוך
ה‑gastrocnemius בעומק p95 של 17.7–17.8 mm, ועל Combined M 42–47 % בתוך ה‑semimembranosus בעומק 10.2–10.9 mm. ה‑sural
cutaneous nerve אמור לרדת **על** הראש המדיאלי של ה‑gastrocnemius ולא בתוכו.

---

## 6. הפגם שהביקורת מצאה בעבודת Q304, והתיקון

`asym307.py` סורק את שני דפי ה‑Imaging ומחפש עצב ששני צדדיו אינם מאותו מקור או אינם באותו אורך.


| page | nerve | why | member | side | length (mm) | source |
|---|---|---|---|---|---|---|
| own_m | `tibial_n` | sources differ; length ratio 13.1x | `tibial_n` | l | 40.0 | `ct_vhm_popliteal` |
|  |  |  | `tibial_n_l` | l | 524.1 | `xfer_zan2vhm_nerves_q304` |
|  |  |  | `tibial_n_r` | r | 40.0 | `mirror_q237` |
| own_m | `sciatic_n_branch_to_semitendinosus` | sources differ; length ratio 3.6x | `sciatic_n_branch_to_semitendinosus_l` | l | 7.4 | `ct_vhm_rule_nerve_q260` |
|  |  |  | `sciatic_n_branch_to_semitendinosus_r` | r | 26.8 | `ct_vhm_rule_nerve_q304` |
| own_m | `femoral_n_branch_to_sartorius` | length ratio 2.1x | `femoral_n_branch_to_sartorius_l` | l | 6.7 | `ct_vhm_rule_nerve_q304` |
|  |  |  | `femoral_n_branch_to_sartorius_r` | r | 14.0 | `ct_vhm_rule_nerve_q304` |
| own_m | `sciatic_n` | sources differ; an unsided mesh coexists with sided ones | `sciatic_n` | m | 255.2 | `ct_vhm_sciatic` |
|  |  |  | `sciatic_n_l` | l | 475.5 | `xfer_zan2vhm_nerves_q304` |
|  |  |  | `sciatic_n_r` | r | 479.8 | `xfer_zan2vhm_nerves_q304` |
| own_f | `femoral_n` | sources differ; length ratio 17.3x | `femoral_n` | r | 29.3 | `ct_vhf_femoral` |
|  |  |  | `femoral_n_l` | l | 29.0 | `mirror_q237` |
|  |  |  | `femoral_n_r` | r | 500.4 | `xfer_zan2vhf_nerves_q304` |
| own_f | `tibial_n` | sources differ; length ratio 12.1x | `tibial_n` | r | 37.6 | `ct_vhf_popliteal` |
|  |  |  | `tibial_n_l` | l | 37.2 | `mirror_q237` |
|  |  |  | `tibial_n_r` | r | 451.4 | `xfer_zan2vhf_nerves_q304` |
| own_f | `vagus_n_oesophageal_trunk` | length ratio 2.9x | `vagus_n_oesophageal_trunk_l` | l | 94.6 | `ct_vhf_rule_nerve_q265` |
|  |  |  | `vagus_n_oesophageal_trunk_r` | r | 32.2 | `ct_vhf_rule_nerve_q265` |
| own_f | `lumbar_root_l4` | length ratio 2.7x | `lumbar_root_L4_l` | l | 6.5 | `ct_vhf_rule_nerve_q260` |
|  |  |  | `lumbar_root_L4_r` | r | 17.5 | `ct_vhf_rule_nerve_q260` |
| own_f | `sciatic_n_branch_to_semimembranosus` | sources differ | `sciatic_n_branch_to_semimembranosus_l` | l | 3.7 | `ct_vhf_rule_nerve_q260` |
|  |  |  | `sciatic_n_branch_to_semimembranosus_r` | r | 6.9 | `ct_vhf_rule_nerve_q304` |
| own_f | `sciatic_n` | sources differ; an unsided mesh coexists with sided ones | `sciatic_n` | m | 260.3 | `ct_vhf_nerve` |
|  |  |  | `sciatic_n_l` | l | 429.0 | `xfer_zan2vhf_nerves_q304` |
|  |  |  | `sciatic_n_r` | r | 429.1 | `xfer_zan2vhf_nerves_q304` |

### D. the transfer

**הסיבה, מצוטטת מהקוד של Q304:** הסלקטור שלו קורא `and x["id"] not in oS` — הוא **דילג על כל id שדף ה‑Imaging כבר
נשא**. איפה שהדף במקרה החזיק את ה‑id של צד אחד, ההעברה הוסיפה רק את הצד השני, והדף נשאר נושא **עצב באורך מלא בצד
אחד וגדם של 29–40 mm בצד השני, תחת אותו שם תצוגה** — ובצד הגדם, הענפים של העצב עצמו נשארו תלויים במרחק של מאות
מילימטרים ממנו.

**מה מותר להחליף ומה אסור:** רק רשת שהמקור שלה הוא `mirror_q237` — **שיקוף** של המקטע המשורטט בצד השני, כך שדבר
שנמדד על הדימות של אותו צד אינו נאבד. מבנה שמשורטט על הדימות של הגוף עצמו (`ct_vh?_popliteal`, `ct_vhf_femoral`)
**לא נוגעים בו**: הוא שומר את הגיאומטריה שלו ואת התג «Measured on this body», ורק הכרטיס שלו מתקן לומר איזה מקטע
הוא בפועל. שלוש רשתות הוחלפו בסך הכול: `tibial_n_r` (Imaging M), `tibial_n_l` ו‑`femoral_n_l` (Imaging F).

---

## 7. ההעברה: 57 / 60 עצבי גפה עליונה, עם שלושה שערים


| page | region | bone-point pairs | residual median / p95 / max (mm) | before (median / p95) |
|---|---|---|---|---|
| own_m | upper | 130089 | 0.95 / 15.56 / 69.68 | 1.56 / 20.84 |
| own_m | lower_fix | 99180 | 0.79 / 3.03 / 13.95 | 1.6 / 7.63 |
| own_f | upper | 123211 | 0.91 / 4.62 / 46.54 | 1.69 / 12.58 |
| own_f | lower_fix | 86398 | 0.86 / 3.54 / 20.66 | 1.58 / 7.67 |

| page | candidates | transferred | added | replaced | refused | triangles | volume (cm3, absolute) | inverted winding |
|---|---|---|---|---|---|---|---|---|
| own_m | 70 | 58 | 57 | 1 | 12 | 66600 | 15.31 | 28 |
| own_f | 68 | 62 | 60 | 2 | 6 | 72213 | 13.22 | 29 |

### E. validation after the transfer

| page | substituted | body mask validates | leaves the body | over 5 % in bone | mostly in bone | dihedral min / median / max (deg) |
|---|---|---|---|---|---|---|
| own_m | 58 | True | 0 | 16 | 0 | 11.7 / 18.8 / 50.6 |
| own_f | 62 | True | 2 | 14 | 0 | 11.4 / 17.4 / 59.4 |


**המכשיר הוא של Q304, במתכוון:** identity + שדה תיקון thin-plate-spline (`reg304.py`, `RBFInterpolator`,
`kernel='thin_plate_spline'`, `degree=1`, `smoothing=10`, 3 מעברים, trim 8 mm, 3,500 נקודות בקרה על סריג 8 mm
אחיד-מרחבית) — **ולא** ICP של נקודה קרובה, ש‑Q304 רשם שהחליק עצב **22.7 mm** במורד רגל, כי העתקים של נקודה קרובה
על עצם ארוכה נורמליים לפני השטח ואינם נושאים מידע לאורכו.

**הנחת היסוד נבדקה לפני שנבנה משהו, בדיוק כמו ב‑Q304, והיא יצאה גרועה יותר.** `xfer307.py probe` מודד שההתאמה בגפה
העליונה היא **0.14–10.29 mm** חציון לקבוצת עצם, מול **0.79–2.79 mm** שמדד Q304 בגפה התחתונה. הקבוצות הגרועות
נקראות בשם ולא ממוצעות: `metacarpals_r` של Imaging M בחציון **10.29**, p95 **54.87**, max **63.86 mm**, ועצמות
האצבעות שלו ב‑p95 46–58 mm — הממצא של Q293 (עצמות היד שלו הושבו במרחק זה מזה) ושל Q304 (הרגליים שלו נסרקו בתנוחות
שונות) חוזר. לאחר שדה התיקון: חציון כולל 0.95 mm (M) ו‑0.91 mm (F).

**שלושה שערים, וכל סירוב נקרא בשמו עם המספר שלו** (`data/derived/Q307_nerve_transfer.json`):

1. **שארית מקומית** — החציון של שאריות העצם ב‑40 mm סביב הקודקודים של המבנה **עצמו** חייב להיות ≤ 4.0 mm וה‑p95
   ≤ 20.0 mm. העברת עצב אצבע דרך התאמה של 50–70 mm הייתה מניחה אותו סנטימטרים משם.
2. **הוספת חדירה לעצם** — לאחר ה‑bone guard של Q299, מבנה שהרוויח יותר מ‑25 % מהנפח שלו בתוך עצם מעל מה שכבר היה לו
   על דף ה‑Combined **נדחה**. הכלל של Q304: רשת שנמצאת בתוך עצם בדף **המקור** היא הגיאומטריה של המקור, מדווחת ולא
   מנותבת — «what this round may not do is add penetration of its own». ה‑guard הוריד אותם (0.78 → 0.69,
   1.00 → 0.90) ולא הצליח לנקות אותם, כי אלו עצבי יד שחוצים את העצמות הגרועות ביותר בדף.
3. **שני הצדדים או אף אחד** — סבב שנקרא לתקן עצב שקיים בצד אחד בלבד אסור לו ליצור עוד אחד. בלי הכלל הזה שער (1)
   היה מפיל בדיוק את העצב של הבעלים בצד אחד בכל דף (own_m שמאל ב‑p95 10.82 mm, own_f ימין ב‑16.73) ומשלח
   lateral antebrachial cutaneous nerve חד-צדדי לשני דפי ה‑Imaging.

**באג שנתפס בשער (1) עצמו:** הביטוי `axillary_n` התאים ל‑**maxillary_nerve** (אין גבול מילה לפני ה‑a), וההרצה
הראשונה העבירה את עצב ה‑maxillary של שני הצדדים לשני הדפים — דרך התאמת גולגולת שהסבב הזה אינו בונה בכלל — והוא נחת
32–39 % בתוך עצם מול 2.6 % על דף ה‑Combined. מתוקן עם look-behind, והסיבה רשומה ליד הביטוי.

---

## 8. אימות, על הדף המוחלף, לפני שנבנה דף

| page | parent / branch pair | before (mm) | after (mm) |
|---|---|---|---|
| own_m | `femoral_n_anterior_cutaneous_branches_l -> femoral_n_l` | — | 0.26 |
| own_m | `femoral_n_anterior_cutaneous_branches_r -> femoral_n_r` | — | 0.15 |
| own_m | `lateral_plantar_n_l -> tibial_n_l` | — | 0.0 |
| own_m | `lateral_plantar_n_r -> tibial_n_r` | 436.6 | 0.08 |
| own_m | `medial_plantar_n_l -> tibial_n_l` | — | 0.35 |
| own_m | `medial_plantar_n_r -> tibial_n_r` | 436.6 | 0.08 |
| own_m | `saphenous_n_l -> femoral_n_l` | — | 0.1 |
| own_m | `saphenous_n_r -> femoral_n_r` | — | 0.12 |
| own_f | `femoral_n_anterior_cutaneous_branches_l -> femoral_n_l` | 13.24 | 0.08 |
| own_f | `femoral_n_anterior_cutaneous_branches_r -> femoral_n_r` | — | 0.24 |
| own_f | `lateral_plantar_n_l -> tibial_n_l` | 370.39 | 0.06 |
| own_f | `lateral_plantar_n_r -> tibial_n_r` | — | 0.0 |
| own_f | `medial_plantar_n_l -> tibial_n_l` | 370.46 | 0.19 |
| own_f | `medial_plantar_n_r -> tibial_n_r` | — | 0.0 |
| own_f | `saphenous_n_l -> femoral_n_l` | 7.36 | 0.36 |
| own_f | `saphenous_n_r -> femoral_n_r` | — | 0.27 |

**אחרי התיקון: 0 מבנים נמצאים בעיקר בתוך עצם** על שני הדפים (היו 2 בכל דף לפני שער 2). על Imaging M **אף קודקוד
אינו יוצא מהגוף**; על Imaging F שני מבנים, 2 ו‑4 קודקודים, הגרוע 0.82 ו‑1.35 mm — טוב יותר ממה ש‑Q304 שלח (5 יוצאים,
אחד מעל 5 mm, הגרוע 9.29 mm). Dihedral ממוצע 11.4–59.4°, חציון 17.4–18.8°, מול ההפניות של CVH 31.7 / 27.6 / 29.5°.

**מה שנשאר פגום ומובא לבעלים:** המרחק מה‑lateral antebrachial cutaneous nerve ל‑musculocutaneous nerve של הדף
עצמו הוא **14.57–21.68 mm** בשלוש מארבע הגפיים של דפי ה‑Imaging (own_m ימין 0.56 mm). הסיבה נמדדת: ה‑MCN של דפי
ה‑Imaging הוא העברה של Q200 עם שגיאת ההתאמה שלה, והעצב החדש הוא העברה של Q307 עם שלה — שתי רגיסטרציות עצמאיות של
אותה אנטומיה אינן נפגשות. זה כתוב על הכרטיס. התיקון יהיה להחליף גם את ה‑MCN בגרסת השדה של Q307, וזו החלטה של
הבעלים כי היא מחליפה מבנה שחי על הדף 107 סבבים.

---

## 9. אימות בדפדפן

`scripts/anatomy/q307/verify_q307.py`, Chromium אמיתי, שישה דפים × שני viewport (קליקים אמיתיים ב‑1400×900, מגע
אמיתי ב‑390×844). הלקחים המצטברים מיושמים על ידי **שימוש חוזר בקוד** של `verify_q304.py` שמקודד אותם: קריאת פיקסלים
דרך hook בדף ולא `page.screenshot`; הקפאת הסחרור של דפי ה‑Z; סילוק באנר הפתיחה בתוך הדף; `wait_for_function` רק
כ‑keyword; `#q` בדפי הדימות מול `#search` בדפי ה‑Z; דפדפן אחד לכל viewport ולא אחד לכל ההרצה; ושיטת הלחיצה
הזהירה של Q304 במקום `force=True`.

**הטעות היחידה שההרצה מצאה הייתה בהרנס עצמו**, והיא רשומה שם: הבדיקה של מרחק הורה/ענף דגמה כל קודקוד חמישי מול כל
שביעי, ועל צינורית של 600 קודקודים במרווח ~1 mm זה הגזים את הפער ל‑5.15 ו‑7.69 mm מול 0.36 ו‑0.27 mm במדידה הצפופה
של `val307` — ארבע ה‑FAIL היחידות בהרצה של 392 טענות. הדגימה חייבת להיות צפופה מהרף שהיא נמדדת מולו (3.46 mm של
Q298), ולכן היא עכשיו כל קודקוד מול כל קודקוד.

---

## 10. מה שלא נעשה, ומה מובא לבעלים להחלטה

1. **השליש הדיסטלי של ה‑lateral antebrachial cutaneous nerve ושני הענפים שלו** אינם קיימים באף דף. אין מקור
   גיאומטרי אמיתי להם בפרויקט; לא פוסלו. **החלטה לבעלים:** להשאיר כמו שזה, עם ההצהרה על הכרטיס, או לאשר בנייה
   rule-based מהמורפומטריה המצוטטת (47.8 ± 34.2 mm דיסטלית ל‑IEL לנקודת החלוקה) עם תג rule-based ונפח רשום.
2. **הפער של 14.57–21.68 mm בין העצב וה‑MCN** על דפי ה‑Imaging — החלטה לבעלים (סעיף 8).
3. **57 עצבים עוריים נמצאים חלקית בתוך בטן שריר** על ששת הדפים, הגרוע ב‑17.8 mm עומק. מדווח על הכרטיסים, לא הוזז.
4. **12 / 6 עצבים נדחו** מההעברה; שישה מהם הם עצבי כף היד שהתאמת העצמות של Imaging M אינה תומכת בהם. כדי להביא
   אותם יש לתקן קודם את התאמת עצמות היד — העבודה ש‑Q293 עשה על דפי ה‑Combined, שלא נעשתה על דפי ה‑Imaging.
5. **הטבלאות של Q298 (adjacency / related / functional group) לא גדלו** עבור העצבים החדשים: הן נתונים מחויבים
   ש‑`--inject` רק מעתיק. 57 / 60 העצבים נמצאים בחיפוש לפי שם, אבל «Adjacent / Related / Functional group»
   לא יציעו להם כלום. **זה פגם מורש מ‑Q304**, שהוסיף 71 / 64 עצבים באותו תנאי, ולא חדש כאן; נתפס על ידי
   `assert_blocks_q303.py --round q307` עצמו. העלות של התיקון היא הרצה מחדש של `adjacency_q298.py` על שני הדפים.
6. **העצב הטיביאלי והפמורלי שהוחלפו משאירים את המקטע המשורטט של הגוף עצמו על הדף** תחת ה‑id הלא-מצודד שלו
   (`tibial_n`, `femoral_n`). הכרטיס שלו אומר עכשיו איזה מקטע הוא, אבל שם התצוגה עדיין «Tibial nerve». שינוי שם
   תצוגה נוגע בחיפוש, ב‑adjacency וב‑relations, ולכן הוא החלטה נפרדת.

---

## 11. קבצי הנתונים של הסבב

| קובץ | מה בו |
|---|---|
| `data/derived/Q307_placement_<key>.json` | הביקורת לכל ששת הדפים: עומק בשריר, רציפות, צד, לכל עצב |
| `data/derived/Q307_lacn_measurements.json` | כל המספרים של העצב שהבעלים דיווח עליו + המספרים של שני המאמרים |
| `data/derived/Q307_side_source_mismatch.json` | אי-ההתאמה צד/מקור בדפי ה‑Imaging, לפני התיקון |
| `data/derived/Q307_frame_probe.json` | התאמת עצמות הגפה העליונה בין הדפים, לפני השדה |
| `data/derived/Q307_nerve_transfer.json` | ההעברה: רגיסטרציה, מועבר, הוחלף, נדחה ולמה |
| `data/derived/Q307_nerve_validation.json` | האימות על הדף המוחלף |
| `data/derived/Q307_in_muscle_cards.json` | 57 העצבים שקיבלו הצהרת עומק על הכרטיס |
| `data/derived/Q307_page_report.json` | מה נוסף / הוחלף / קיבל כרטיס בכל דף |
| `data/derived/Q307_browser_report.json` / `.log` | ההרצה בדפדפן |
| `data/anatomy/nerve_parents_q307.json` | ההורה המצוטט של העצב ושני הענפים שאינם קיימים |
