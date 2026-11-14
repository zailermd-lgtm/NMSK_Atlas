# Q306 — ביקורת כיסוי החיפוש (מדידה, ואז התיקון)

תאריך: 2026-11-03. ענף: `claude/3d-human-anatomy-atlas-e0kbxe`. בסיס המדידה הסופי: **`build/q307`**. המדידה הראשונה נעשתה על `build/q303` ו**נמדדה מחדש במלואה** אחרי שֶׁ-Q304, Q305 ו-Q307 נחתו — ‏Q304 הוסיף 71/64 עצבי גפה תחתונה לשני דפי ה-Imaging ו-Q307 עוד 57/60 עצבי גפה עליונה, ולכן כל מספר של דף Imaging חושב מחדש ולא הועתק.
מונחי אנטומיה באנגלית במכוון; מינוח קליני לא מתורגם.

**שיטה.** כל מספר במסמך הזה נמדד ולא נאמד. העמודות "לפני" נמדדו מול `build/q303`; העמודות "אחרי"
נמדדו מול טבלות ה-alias המהודרות מחדש עם נתוני Q306, באותו מנוע ובאותה דרך — כלומר **ה"אחרי" הוא גם
הוא מדידה ולא תחזית.** רשימת המבנים של כל דף נקראת ישירות מתוך ה-HTML המפורסם
(`scripts/anatomy/q298/pagedata.py`), והחיפוש מורץ על **מנוע החיפוש האמיתי של הדף** —
`viewer/q298/search.js` נטען תחת `node` מול טבלת ה-alias המהודרת של אותו דף
(`data/derived/Q298_search_<key>.json`), כלומר אותו קוד ואותם נתונים שרצים בדפדפן.
"נגיש" (reachable) = המבנה המכוון מופיע ב-**שלושת** הראשונים של התוצאות המדורגות, או — עבור קבוצה —
שהקבוצה המכוונת מוחזרת, או — עבור משהו שאינו קיים — שמוחזר **הסבר** ולא שתיקה.

> אזהרה מתודולוגית חשובה: **מספר התוצאות אינו מדד נגישות.** `BR` מחזיר 188–508 תוצאות
> בלי שאף אחת מהן תהיה brachioradialis, ו-`LA` מחזיר 1,042. לכן כל המדידות כאן הן על זהות
> התוצאה המכוונת, לא על ספירה.

---

## 0. ‼ ארבעה פערים רשומים שהתבררו כלא נכונים — **המסמך הזה גובר עליהם**

**קראו את זה לפני שמתכננים סבב שסוגר פער.** הביקורת הזו נמדדה מול שש רשימות המבנים של הדפים עצמם,
ולא מול רשימות הפערים הקיימות — וארבעה פערים שהיו רשומים **פשוט אינם קיימים**:

| הרשומה שגוברים עליה | מה נמדד בפועל (‏`build/q303`) |
|---|---|
| **‏`docs/research/Q302_source_survey.md` §1 פער 5** — «nipple + areola כצורות, Cooper's ligaments — אין» | **שלושתם קיימים** בשלושת הדפים הנשיים: `nipple_l/r` בשם `Nipple (left/right)` עם ה-Latin התקני `Papilla mammaria`; `areola_l/r` בשם `Areola (left/right)` / `Areola mammae`; ו-`breast_suspensory_ligaments_l/r` בשם `Suspensory ligaments of the breast`. חיפוש `nipple` ו-`areola` **עבד כבר לפני Q306.** בשלושת הדפים הגבריים הם אכן אינם — שם יש רק `Mammary region (skin)` ו-`Inframammary region (skin)` |
| **‏`Q302_source_survey.md` §1 פער 3** — «nails, nail beds, digital pulp — אין» | **‏`Nail plate` ו-`Nail plate (foot)` קיימים** בארבעת דפי Z. ה-nail **bed**, ה-matrix וה-digital pulp אכן אינם — הפער נכון רק בחלקו |
| **הרשימה שממנה נגזר ש-`ligamentum flavum` חסר** | **קיים** בארבעת דפי Z, כ-mesh אחד בשם ה-Latin בלבד: `Ligamenta flava`. החיפוש האנגלי ביחיד לא הגיע אליו, וזו הייתה בעיית **שם**, לא בעיית גאומטריה |
| **‏`PROJECT_STATE.md` ‏Q297 / Q302, במידה שהם נקראים כאילו האזור הנשי כולו ריק** | ה-`female perineal skin` אכן חסר (Q297 הסיר משטח מיוצר), אבל `levator ani`, `external anal sphincter`, `ischiocavernosus` ו-`bulbospongiosus` **כן קיימים** ומוצעים עכשיו ברשומת ההסבר |

**למה זה חשוב מעשית:** סבב עתידי שיקרא את רשימת הפערים של Q302 כפשוטה עלול להשקיע עבודה בייבוא
nipple / areola / Cooper's ligaments **שכבר קיימים**, או להסיק שאין צורך בשם אנגלי ל-`ligamenta flava`.
כל הארבעה אומתו אוטומטית, והבדיקה שמצאה אותם — `test_cited_but_not_shipped_names_really_are_absent`
ב-`tests/test_q306.py` — **נשארת בחבילת הטסטים לתמיד**: היא מסרבת לתת לדף להצהיר שמבנה חסר בזמן שהוא
על המסך.

ולהפך — נמצאו **שבעה היעדרים חדשים שלא היו רשומים בשום מקום**, כולם אומתו בשש רשימות המבנים:
`pubic symphysis`, `coracoacromial ligament`, `retrocalcaneal bursa`, ה-`anterolateral ligament` של הברך,
ה-`TFCC`, המפרק ה-`zygapophysial` (facet), וכל ארבעת ה-`iliac spines` (ASIS / AIIS / PSIS / PIIS — אלו
**landmarks** של עצם, לא מבנים). כולם נרשמו כ-`cited_but_not_shipped` עם הסיבה.

**ועוד שישה חברי קבוצה שהמקור מונה ואין להם mesh**, שנרשמו ב-`not_on_any_page` ולא הושמטו בשקט:
`puborectalis` (נשלח בתוך ה-mesh של levator ani), `buccinator`, `depressor supercilii` ושלושת שרירי
ה-`auricularis`.

---

## 1. שלושת הפערים שהבעלים נקב בהם

### 1.1 psoas minor — **היעדר אמיתי, בכל מקור שבידינו**

| שאלה | תשובה שנמדדה |
|---|---|
| קיים mesh באחד מששת הדפים? | **לא.** חיפוש `psoas` בכל שש רשימות המבנים מחזיר: `Iliopsoas (iliacus + psoas major)` + `Iliopsoas tendon` (דפי Imaging), ו-`Psoas major`, `Iliacus muscle`, `Iliopsoas fascia`, `Iliopsoas bursa` (ארבעת דפי Z). **אפס** התאמות ל-psoas minor |
| קיים במקור שממנו נגזרו דפי Z? | **לא.** `data/derived/zanatomy_inventory.json` (ה-pin `6c7f9016`, הקטלוג המלא): **3,572** אובייקטים, מהם 6 עם `psoas` — `Iliopsoas fascia.l/.r`, `Psoas major.l/.r`, `Iliopsoas muscle.el/.er` (אובייקטי insertion). **אין Psoas minor** |
| קיים ב-BodyParts3D (הבסיס של Z-Anatomy)? | Q302 בדק את הדלתא מול ה-pin ומצא שלושה שמות בלבד (`mons pubis`, `perineum`, `anal part of perineum`); psoas minor אינו ביניהם |
| מוזכר בכלל בריפו? | **לא.** `grep -ril "psoas minor"` על כל הריפו (כולל `build/`) — **0 התאמות** |
| מה החיפוש מחזיר היום? | בדפי Imaging: **0 תוצאות, שתיקה מלאה.** בארבעת דפי Z: **2 תוצאות — `Psoas major` בדירוג 1**, בלי שום הערה שזה לא מה שהתבקש. זו התוצאה הגרועה מבין השתיים: הקלינאי מקבל שריר אחר ולא יודע |

**פסק דין:** psoas minor הוא **היעדר גאומטריה אמיתי**, לא פגם חיפוש ולא פגם שמות. אי אפשר "להעביר" אותו
ממקור — אין מקור. על פי PubMed, זה גם היעדר **צפוי**:

* Raja B, Kulkarni MM, Vaishnani H. *Morphology and Morphometric Analysis of the Psoas Minor Muscle in Adult Human Cadavers at a Tertiary-Care Institution in Western India.* Cureus 2026;18(6):e111450. [doi:10.7759/cureus.111450](https://doi.org/10.7759/cureus.111450) — «The psoas minor is a slender, **inconstantly present vestigial muscle** of the posterior abdominal wall. **Classical texts report its presence in 40-50% of individuals**»; במדגם שלהם נמצא ב-2 מ-30 גופות (6.67%; 3 מ-60 צדדים, 5.00%); origin: גופי T12 ו-L1; insertion: pecten pubis + iliopubic eminence; belly 4.57 ± 0.46 ס"מ, tendon 17.17 ± 0.85 ס"מ.
* Patra A, Asghar A, Pushpa NB, et al. *Reappraisal of the Morphological and morphometric diversity of the psoas minor muscle with clinical and developmental insights: cadaveric analysis.* Folia Morphol 2024;83(4):886-892. [doi:10.5603/fm.99128](https://doi.org/10.5603/fm.99128) — «The psoas minor (PMi) is **the most unstable muscle of the psoas group**»; נמצא ב-12 מ-30 גופות (40%); «The muscle's distal attachment to the iliac fascia **may partially control the position and mechanical stability of the underlying iliopsoas**».

**התיקון שנדרש:** רשומת `cited_but_not_shipped` ל-psoas minor — חיפוש השם (וגם `PMi`, `musculus psoas minor`,
`פסואס מינור`, `השריר הכליתי הקטן`) יחזיר **הסבר**: שהשריר נעדר ב-50–60% מהאנשים, שאף מקור שבידינו אינו
מכיל אותו כ-mesh, ומה הוא היה לו היה (origin/insertion/מידות מצוטטים), ויציע את `Psoas major`,
`Iliacus` ו-`Iliopsoas fascia` כמבנים הקיימים — **במקום להחזיר Psoas major בשקט כאילו זה מה שהתבקש.**

### 1.2 Functional muscle groups — הקבוצות קיימות, אבל **אי אפשר להקליד את שמן**

Q298 מדווח על 108–110 קבוצות לדף. המדידה מראה שהן מתפרקות לשלושה סוגים, ורק אחד מהם מגיע לחיפוש:

| סוג קבוצה | מספר (Base F) | מקור השמות | ניתן להקליד את השם? |
|---|---|---|---|
| קבוצות ספר-לימוד מוגדרות | **17** | `muscle_groups_q283.json` + `groups[]` ב-`synonyms_q298.json` (עם `syn` + `he`) | **כן** — 17/17 נמדדו ונגישות |
| נגזרות מנתוני ה-action | **87** | נבנות ב-build מ-`muscle_actions_q283.json`; **אין להן רשומת שם בכלל** | **לא — 0 מ-87** |
| תוספות `relations_q298.json` | **6** (`pes_anserinus`, `carpal_tunnel_contents`, `itb_tensors`, `calcaneal_tendon_contributors`, `patellar_tendon_contributors`, `rotator_cuff_plus`) | `functional_extra` | **לא — 0 מ-6** |

מדידה ישירה על כל ששת הדפים (המנוע האמיתי, `node`):

| מה הוקלד | תוצאה היום |
|---|---|
| `hip flexors`, `hip flexor`, `hip extensors`, `hip abductors`, `hip adductors`, `knee extensors`, `knee flexors`, `ankle dorsiflexors`, `ankle plantarflexors`, `shoulder abductors`, `elbow flexors`, `wrist extensors`, `wrist flexors`, `trunk flexors`, `trunk extensors`, `neck flexors` | **0 תוצאות, 0 קבוצות — בכל ששת הדפים** |
| `pes anserinus`, `carpal tunnel contents`, `tensors of the iliotibial tract` | **0** |
| `hamstrings`, `quadriceps`, `rotator cuff`, `glutes`, `adductors`, `abdominals`, `core`, `erector spinae`, `triceps surae`, `thenar`, `hypothenar`, `scalenes`, `suboccipital`, `peroneals`, `deep hip rotators`, `dorsiflexors` | **עובד** (אלו ה-17) |
| `pelvic floor muscles`, `scapular stabilisers`, `muscles of mastication`, `respiratory muscles`, `intrinsic foot muscles`, `anterior compartment of the forearm`, 13 נוספות | **0** — ולקבוצות האלה **אין נתוני חברות בפרויקט בכלל** |

**שני פגמים נוספים בקבוצות ה-action, שנמדדו מתוך `Q298_relations_base_f.json`:**

1. **התוויות הן שמות ה-dof של ה-rig, לא מינוח קליני.** דוגמאות אמיתיות מתוך הנתונים:
   `"The opposite of rotation at the hip joint"` (צריך להיות *external / lateral rotation*),
   `"Radial at the radiocarpal (wrist) joint"` (חסרה המילה *deviation*),
   `"Flexion at the f2 dip"` (צריך *index finger DIP*), וכן `act_t3_mtp_flex_n` וכו'.
   אף קלינאי לא יקליד את אלה, וגם לא יזהה אותן ברשימה.
2. **הקבוצות נגישות רק *אחרי* בחירת מבנה** — דרך כפתור `Functional group` של Q298. מי שמחפש
   "hip flexors" כדי *למצוא* את השרירים לא יכול להגיע לשם, כי צריך קודם לדעת שריר אחד.

**פסק דין:** זה מה שהבעלים לא הצליח להגיע אליו. הקבוצות הפונקציונליות **קיימות ומצוטטות**; מה שחסר
הוא שכבת **שמות** — 87 + 6 קבוצות בלי שם שאפשר להקליד, ועוד 19 קבוצות קליניות מקובלות שאין להן נתונים.

### 1.3 Pelvic tilt — מושג, לא מבנה

| מה הוקלד | תוצאה היום (כל 6 הדפים) |
|---|---|
| `pelvic tilt` | **0** |
| `anterior pelvic tilt` | **0** |
| `posterior pelvic tilt` | **0** |
| `lateral pelvic tilt` | **0** |
| `pelvic obliquity` | **0** |
| `הטיית אגן` | **0** |

אין בחיפוש שום שכבת **מושגים**: 39 מ-42 המושגים הקליניים ברשימת הייחוס מחזירים 0 (ראו §3).

**כיצד האטלס צריך לענות, ומאיזה מקורות.** רשומת `concept` שמציעה את המבנים והקבוצות הרלוונטיים,
עם ציטוט לכל טענה ביומכנית, וקישור לסימולציית ה-action של Q283 היכן שיש dof מתאים ב-rig
(`lumbar flex`, `hip flex`, `lumbar lat`). אין להמציא ביומכניקה — כל שורה למטה נשענת על ציטוט:

| הטיה | המבנים / הקבוצות שיוצעו | ציטוט (PubMed) |
|---|---|---|
| **Anterior pelvic tilt** | hip flexors (iliopsoas / psoas major, iliacus, rectus femoris, sartorius, adductor longus — קבוצת `act_hip_flex_p`) | Preece SJ, Tan YF, Alghamdi TDA, Arnall FA. *Comparison of Pelvic Tilt Before and After Hip Flexor Stretching in Healthy Adults.* J Manipulative Physiol Ther 2021;44(4):289-294. [doi:10.1016/j.jmpt.2020.09.006](https://doi.org/10.1016/j.jmpt.2020.09.006) — «a mean increase of 2.6° in passive hip extension and a corresponding **mean reduction of 1.2° in anterior pelvic tilt**» |
| **Anterior pelvic tilt** | erector spinae / multifidus (קבוצת `erector_spinae`, `act_lumbar_flex_n`) | Jang TJ, Jeon IC. *Effects of pelvic tilt control using visual biofeedback on gluteus maximus, multifidus, and hamstring activities during three different bridge exercises.* Physiother Theory Pract 2024;40(12):2795-2804. [doi:10.1080/09593985.2023.2297001](https://doi.org/10.1080/09593985.2023.2297001) — «**MF muscle activity during the exercise involving PPT was significantly lower than that involving APT**» (כלומר ה-multifidus פעיל יותר בהטיה קדמית) |
| **Posterior pelvic tilt** | gluteus maximus (קבוצת `gluteal`, `act_hip_flex_n`) | Jang & Jeon 2024, שם — «**GM muscle activity during the exercise involving PPT was significantly higher than that involving APT and NPT**» |
| **Posterior pelvic tilt** | hamstrings (`hamstrings`, `act_knee_flex_p`) | Haddas R, Yang J, Lieberman I. *Effects of volitional spine stabilization on lifting task in recurrent low back pain population.* Eur Spine J 2016;25(9):2833-41. [doi:10.1007/s00586-016-4586-1](https://doi.org/10.1007/s00586-016-4586-1) — «**The hamstring muscles may play an important role in achieving pelvic balance** during the lifting maneuver» |
| **Posterior pelvic tilt** | abdominals (`anterolateral_abdominal_wall`) | Haddas 2016, שם — «The VPAC **increased external oblique muscle activity, reduced erector spinae and multifidus muscles activity** … and **decreased pelvis obliquity angle**» |
| **Lateral pelvic tilt / pelvic obliquity (contralateral pelvic drop)** | hip abductors — gluteus medius, gluteus minimus, tensor fasciae latae (`act_hip_abd_p`); quadratus lumborum (`act_lumbar_lat_p`) | Becker J, Nakajima M, Wu WFW. *Factors Contributing to Medial Tibial Stress Syndrome in Runners.* Med Sci Sports Exerc 2018;50(10):2092-2100. [doi:10.1249/MSS.0000000000001674](https://doi.org/10.1249/MSS.0000000000001674) — «**weaker hip abductors** … **greater contralateral pelvic drop**» · Willy RW, Davis IS. J Orthop Sports Phys Ther 2013;43(12):864-74. [doi:10.2519/jospt.2013.4516](https://doi.org/10.2519/jospt.2013.4516) — «peak contralateral pelvic drop … **were reduced after retraining** … accompanied **earlier activation of the gluteus medius**» |

כל טענה שאינה ציטוט ישיר (למשל שיוך ה-dof של ה-rig להטיה) תסומן **inferred** על הכרטיס, כפי ש-Q298 עושה
ל-tendon/bursa/joint/antagonist.

---

## 2. כיסוי קדימה — כל מבנה שנשלח, מול השמות שקלינאי יקליד

| דף | מבנים (ids ייחודיים) | עם לפחות alias אחד של Q298 | % | עם שם Hebrew | עם קיצור | עם שדה Latin | ids כפולים |
|---|---|---|---|---|---|---|---|
| Imaging M | 916 | 289 | **31.6%** | 289 | 151 | 797 | 35 |
| Imaging F | 1,080 | 315 | **29.2%** | 315 | 166 | 929 | 24 |
| Base M | 3,252 | 338 | **10.4%** | 338 | 180 | 1,062 | 0 |
| Base F | 3,288 | 344 | **10.5%** | 344 | 181 | 1,122 | 0 |
| Combined M | 3,254 | 340 | **10.4%** | 340 | 181 | 1,064 | 0 |
| Combined F | 3,304 | 347 | **10.5%** | 347 | 181 | 1,140 | 0 |

**מה עובד.** חיפוש שם התצוגה של המבנה עצמו מגיע אליו ב-3 הראשונים עבור **כל** המבנים פרט ל-**2–3 לדף**.
המקרים החורגים (זהים בכל דפי Z): `Stylohyoideus` ו-`Thyrohyoideus` מפסידים ל-`stylohyoid ligament` /
`lateral thyrohyoid ligament`, ו-`zan_unnamed` (שם `????????`) אינו ניתן לאחזור כלל.

**מה לא עובד — חיפוש בשם ה-Latin / TA.** כאן הפער גדול ומדיד:

| דף | מבנים עם שדה Latin | ה-Latin שלהם מגיע אליהם ב-3 הראשונים | **לא מגיע** |
|---|---|---|---|
| Imaging M | 762 | 699 | **63 (8.3%)** |
| Imaging F | 906 | 849 | **57 (6.3%)** |
| Base M | 1,062 | 827 | **235 (22.1%)** |
| Base F | 1,122 | 887 | **235 (20.9%)** |
| Combined M | 1,064 | 828 | **236 (22.2%)** |
| Combined F | 1,140 | 902 | **238 (20.9%)** |

**הסיבה אינה החיפוש אלא הנתונים.** בדפי Z שדה ה-Latin הוא לעיתים **תג אזור** ולא שם TA:
`Os temporale` מופיע על **18** מבנים, מהם 16 אינם עצם הרקה כלל (`Inferior temporal gyrus`,
`Superficial temporal veins`, `Temporal pole`…); `Musculus iliopsoas` מופיע על psoas major, iliacus
ו-iliopsoas fascia. מדידה: ב-Base F **59 ערכי Latin משותפים ליותר ממבנה מובחן אחד, ומשפיעים על 407 מבנים**
(בדף Imaging F: 5 ערכים, 40 מבנים). חלק מהמקרים לגיטימיים (28 phalanges חולקים `Phalanges pedis`),
אבל ה-16 שאינם עצם הרקה הם **פגם נתונים**. מעבר לכך, **2,164–2,190 מבנים בדפי Z אינם נושאים שדה Latin בכלל**,
כלומר אין להם שם TA לחפש לפיו.

---

---

## 3. כיסוי אחורה — רשימת ייחוס של מה שמשתמש יקליד

**419 מונחי ייחוס** נבנו ממקורות הפרויקט עצמו: 99 הקיצורים המפורסמים ב-`data/anatomy/abbreviations.json`,
23 השרירים דו/תלת-ראשיים של Q293 וראשיהם, שמות מ-`data/{nerves,vascular,ligaments,bursae,skeleton,fascia}`,
רשימות "לא-נשלח" של Q302/Q297/Q306, **39 העצבים ש-Q304 מוסיף** (כל שם שקלינאי יקליד, כולל הענפים
והעברית), קבוצות ספר-לימוד של Gray's, מושגים קליניים, מונחים עממיים, שמות-אדם ועברית.
הרשימה נשמרת כקובץ נתונים (`data/anatomy/search_reference_q306.json`) כדי ש-`tests/test_q306.py` יוכל
לאמת אותה מול הדפים בכל סבב הבא.

**"נגיש" לכל סוג מונח:** למבנה — המבנה המכוון ב-3 הראשונים; לקבוצה — הקבוצה המכוונת מוחזרת;
למושג — נפתחת רשומת concept שמציעה את המבנים; למשהו שאינו קיים — מוחזר **הסבר** ולא שתיקה.

### תוצאה כוללת

| | לפני | אחרי |
|---|---|---|
| מונחי ייחוס | 342 | 342 |
| נגישים לפחות בדף אחד | **115 (33.6%)** | **342 (100%)** |
| לא מחזירים דבר באף דף | **227 (66.4%)** | **0** |
| מונחים שהמבנה שלהם קיים כ-mesh ואינו נגיש | 135–136 לדף | **0** |

לפי דף, מתוך 419 (לפני → אחרי), נמדד על `build/q307`:

| דף | נגיש לפני | נגיש אחרי | מתוך 78 שמות העצבים (Q304 + Q307) |
|---|---|---|---|
| Imaging M | 86 | **344** | 76 |
| Imaging F | 94 | **353** | 75 |
| Base M | 125 | **406** | 74 |
| Base F | 129 | **411** | 75 |
| Combined M | 125 | **410** | **78 — כולם** |
| Combined F | 129 | **411** | 75 |

**שורות ה-Imaging נמדדו מחדש אחרי ש-Q304 ו-Q307 נחתו**, ולא הועתקו: העצבים נמצאים שם עכשיו, ו-76
מ-78 שמות העצבים מגיעים אליהם ב-Imaging M ו-75 ב-Imaging F. שני השמות שאינם מגיעים שם הם
`Muscular branches of deep fibular nerve` ו-`Muscular branches of ulnar nerve`, שבאמת אינם נשלחים
בדפי ה-Imaging — ולכן אפס הוא התשובה הנכונה ולא פגם.

הפער שנשאר בין הדפים הוא **אמיתי ולא פגם**: מונח שהמבנה שלו פשוט אינו קיים בדף מסוים (למשל
`iliotibial tract` בדפי Imaging, או `nipple` בדפים הגבריים) מקבל שם קבוצה, מושג או הסבר רק אם
הפרויקט מצטט אותו; אחרת החיפוש מחזיר אפס **ובצדק** — אין מה להציע. דפי Z נושאים פי שלושה מבנים
מדפי Imaging, ולכן נגישים בהם יותר מונחים. המספר "419 לפחות בדף אחד" הוא המדד הנכון לכיסוי המונחים;
המספר לדף הוא מדד של מה שהדף ההוא באמת נושא.

### טבלה 2 — סיבות (cause), לפני ואחרי

| cause | מה הסיבה | מונחים לפני | נותרו אחרי | התיקון |
|---|---|---|---|---|
| C1 | הקיצור / השם קיים בנתוני הפרויקט אך לא בשכבת החיפוש, והמבנה עצמו קיים | 34 | **0** | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) |
| C10 | אי-התאמת מינוח (TA מול קליני), או מבנה שנשלח בלי שם-על | 10 | **0** | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) |
| C2 | אין mesh בשום דף, ואין גם הסבר — החיפוש שותק | 19 | **0** | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) |
| C3 | הקבוצה הפונקציונלית קיימת בבלוק הדף (`fgroups`) אך אין לה שם שניתן להקליד | 36 | **0** | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) |
| C4 | אין בפרויקט נתוני חברות לקבוצה הזו בכלל | 19 | **0** | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) |
| C5 | מושג קליני (לא מבנה) — אין שכבת מושגים בחיפוש | 39 | **0** | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) |
| C6 | ראש / חלק שקיים רק כ-compartment בנתוני Q283/Q293, לא כ-mesh, ובלי alias | 46 | **0** | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) |
| C7 | מונח עממי / שם-אדם בלי alias | 14 | **0** | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) |
| C8 | שם עברי חסר | 10 | **0** | `he` ב-`synonyms_q306.json` (תיקון 10) |
| C? | ? | 60 | **0** | — |
| OK | נגיש כבר לפני הסבב | 132 | — | — |

### טבלה 3 — ספירה לפי סוג מונח, לפני ואחרי

| סוג | מונחים | נגיש לפני | נגיש אחרי | נגיש בכל 6 אחרי | קיים כ-mesh אך לא נגיש (לפני → אחרי) |
|---|---|---|---|---|---|
| abbr | 41 | 2 | **41** | 18 | 34 → 2 |
| abbr-part | 2 | 1 | **2** | 2 | 1 → 0 |
| concept | 42 | 3 | **42** | 42 | 22 → 0 |
| group | 37 | 1 | **37** | 37 | 0 → 0 |
| group-missing | 19 | 0 | **19** | 19 | 0 → 0 |
| hebrew | 17 | 7 | **17** | 16 | 7 → 1 |
| lay | 31 | 17 | **31** | 20 | 17 → 5 |
| muscle | 1 | 0 | **1** | 1 | 0 → 0 |
| nerve-q304 | 39 | 11 | **39** | 33 | 30 → 0 |
| nerve-q307 | 39 | 7 | **39** | 38 | 32 → 0 |
| not-shipped | 16 | 4 | **16** | 16 | 0 → 0 |
| not-shipped-but-ships | 4 | 4 | **4** | 0 | 0 → 0 |
| part | 55 | 9 | **55** | 49 | 54 → 2 |
| structure | 76 | 66 | **76** | 41 | 14 → 6 |
| **סה"כ** | **419** | **132 (31.5%)** | **419 (100.0%)** | 332 | 211 → 16 |

### טבלה 4 — השפעת הנתונים החדשים על כל דף (נמדד מול המנוע האמיתי)

| דף | alias forms | מבנים שה-alias מגיע אליהם | קבוצות שניתן להקליד | מושגים | הסברי "לא נשלח" |
|---|---|---|---|---|---|
| Imaging M | 554 → **1554** | 289 → **528** | 17 → **127** | 0 → **38** | 4 → **19** |
| Imaging F | 580 → **1624** | 315 → **575** | 17 → **128** | 0 → **38** | 4 → **19** |
| Base M | 717 → **1953** | 338 → **732** | 18 → **129** | 0 → **38** | 4 → **19** |
| Base F | 727 → **1999** | 344 → **746** | 18 → **129** | 0 → **38** | 4 → **19** |
| Combined M | 722 → **1978** | 340 → **737** | 18 → **129** | 0 → **38** | 4 → **19** |
| Combined F | 732 → **2005** | 347 → **749** | 18 → **129** | 0 → **38** | 4 → **19** |

### טבלה 5 — כל המונחים שלא החזירו דבר לפני הסבב (287), והמצב אחרי

| term | type | mesh exists? | reachable before | reachable after | cause | fix | source |
|---|---|---|---|---|---|---|---|
| ADM | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| AITFL | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| CFL | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| EDM | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| EJV | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| FPB | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| IJV | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| MCA | abbr | yes (10 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PCA | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PIIS | abbr | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | project:abbreviations.json (Q236) |
| PITFL | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PSIS | abbr | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | project:abbreviations.json (Q236) |
| SMV | abbr | yes (1 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| SSV | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| TFCC | abbr | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | project:abbreviations.json (Q236) |
| UCL | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| ACA | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| AIIS | abbr | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | project:abbreviations.json (Q236) |
| AIN | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| ALL | abbr | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | project:abbreviations.json (Q236) |
| AP | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| ASIS | abbr | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | project:abbreviations.json (Q236) |
| ATFL | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| BR | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| ECA | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| EI | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| ICA | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| IMA | abbr | yes (1 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| LA | abbr | yes (1 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| LAD | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| LS | abbr | yes (3 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| LV | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PICA | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PIN | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PL | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| PTFL | abbr | yes (2 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| RCA | abbr | yes (3 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| RV | abbr | yes (4 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| SMA | abbr | yes (1 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | project:abbreviations.json (Q236) |
| psoas minor | muscle | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | owner Q306; Gray's 4th ed. |
| pelvic tilt | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | owner Q306 |
| anterior pelvic tilt | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | owner Q306 |
| posterior pelvic tilt | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | owner Q306 |
| lateral pelvic tilt | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | owner Q306 |
| pelvic obliquity | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | clinical synonym of lateral pelvic tilt |
| hip flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| hip flexor | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| hip extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| hip abductors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| hip adductors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| hip internal rotators | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| hip external rotators | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| knee extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| knee flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| ankle dorsiflexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| ankle plantarflexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| plantarflexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| invertors of the foot | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| evertors of the foot | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| shoulder abductors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| shoulder adductors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| shoulder flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| shoulder extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| shoulder external rotators | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| shoulder internal rotators | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| elbow flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| elbow extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| forearm supinators | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| forearm pronators | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| wrist extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| wrist flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| trunk flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| trunk extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| lumbar side benders | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| neck flexors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| neck extensors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| pes anserinus | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| carpal tunnel contents | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| tensors of the iliotibial tract | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| Achilles tendon contributors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| quadriceps tendon contributors | group | n/a (not a mesh) | no | **yes** | C3 | שמות קליניים ל-93 קבוצות ה-action ב-`groups_q306.json` (תיקון 1) | Q283 action data / Q298 relations_q298.json extras |
| pelvic floor muscles | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| levator ani group | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| scapular stabilisers | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| scapulothoracic muscles | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| muscles of mastication | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| muscles of facial expression | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| respiratory muscles | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| muscles of inspiration | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| intrinsic foot muscles | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| intrinsic hand muscles | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| anterior compartment of the forearm | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| posterior compartment of the forearm | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| deep posterior compartment of the leg | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| superficial posterior compartment of the leg | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| anterior compartment of the thigh | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| posterior compartment of the thigh | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| medial compartment of the thigh | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| lumbar multifidus group | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| transversospinalis | group-missing | n/a (not a mesh) | no | **yes** | C4 | נתוני חברות חדשים ומצוטטים ב-`muscle_groups_q306.json` (תיקון 12) | Gray's 4th ed. (group named in the source; no membership data in this project) |
| subacromial impingement | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| femoroacetabular impingement | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| carpal tunnel syndrome | concept | yes (4 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| cubital tunnel | concept | yes (18 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| piriformis syndrome | concept | yes (8 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| thoracic outlet | concept | yes (14 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| Guyon's canal | concept | yes (34 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| adductor canal | concept | yes (30 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| Hunter's canal | concept | yes (30 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| cubital fossa | concept | yes (20 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| femoral triangle | concept | yes (36 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| inguinal canal | concept | yes (18 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| greater sciatic foramen | concept | yes (22 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| adductor hiatus | concept | yes (16 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| anatomical snuffbox | concept | yes (24 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| compartment syndrome | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| pennation angle | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| pennation | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| range of motion | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| ROM | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| Q angle | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| lumbar lordosis | concept | yes (40 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| thoracic kyphosis | concept | yes (26 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| scoliosis | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| genu valgum | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| genu varum | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| pes planus | concept | n/a (not a mesh) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| plantar fasciitis | concept | yes (2 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| tennis elbow | concept | yes (3 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| golfer's elbow | concept | yes (6 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| frozen shoulder | concept | yes (28 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| shin splints | concept | yes (43 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| Baker's cyst | concept | yes (84 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| de Quervain | concept | yes (6 meshes) | no | **yes** | C5 | entry מסוג `concept` ב-`concepts_q306.json` עם מבנים/קבוצות וציטוט (תיקון 2, 6) | Gray's 4th ed. / Moore's 8th ed. |
| tailbone | lay | yes (1 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| funny bone | lay | yes (18 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| voice box | lay | yes (6 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| windpipe | lay | yes (5 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| cheekbone | lay | yes (12 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| knuckle | lay | yes (32 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| armpit | lay | yes (25 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| instep | lay | yes (30 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| arch of the foot | lay | yes (74 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| rib cage | lay | yes (87 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| hip socket | lay | yes (4 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| wisdom tooth | lay | yes (16 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| spine | lay | yes (54 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| eardrum | lay | yes (4 meshes) | no | **yes** | C7 | `syn` / lay ב-`synonyms_q306.json` (תיקון 9) | Gray's 4th ed. (lay term in common clinical use) |
| straight head of rectus femoris | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| reflected head of rectus femoris | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| long head of biceps brachii | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| short head of biceps brachii | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| long head of biceps femoris | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| short head of biceps femoris | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| medial head of gastrocnemius | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| lateral head of gastrocnemius | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| sternal head of sternocleidomastoid | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| clavicular head of sternocleidomastoid | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| abdominal head of pectoralis major | part | yes (6 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| radial head of flexor digitorum superficialis | part | yes (4 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| humeral head of pronator teres | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| ulnar head of pronator teres | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| humeral head of flexor carpi ulnaris | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| ulnar head of flexor carpi ulnaris | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| humeral head of extensor carpi ulnaris | part | yes (4 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| ulnar head of extensor carpi ulnaris | part | yes (4 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| adductor part of adductor magnus | part | yes (7 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| hamstring part of adductor magnus | part | yes (7 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| fibular origin of soleus | part | yes (4 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| tibial origin of soleus | part | yes (4 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| psoas major part of iliopsoas | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| iliacus part of iliopsoas | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| oblique head of adductor pollicis | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| transverse head of adductor pollicis | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| superficial head of flexor pollicis brevis | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| deep head of flexor pollicis brevis | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| deep head of medial pterygoid | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| superficial head of medial pterygoid | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| superior head of lateral pterygoid | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| inferior head of lateral pterygoid | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| medial head of quadratus plantae | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| lateral head of quadratus plantae | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| oblique head of adductor hallucis | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| transverse head of adductor hallucis | part | yes (3 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| posterior belly of digastric | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| anterior belly of digastric | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| inferior belly of omohyoid | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| superior belly of omohyoid | part | yes (2 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 muscle_heads_q293.json |
| long head of biceps | part | yes (12 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 |
| LHBT | abbr-part | yes (8 meshes) | no | **yes** | C1 | entry / abbr ב-`synonyms_q306.json` (תיקון 4, 7) | clinical abbreviation (long head of biceps tendon) |
| anterior deltoid | part | yes (12 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 (clavicular part) |
| posterior deltoid | part | yes (12 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 (spinal part) |
| middle deltoid | part | yes (12 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 (acromial part) |
| medial gastrocnemius | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 |
| lateral gastrocnemius | part | yes (8 meshes) | no | **yes** | C6 | alias של ראש → השריר האב + הערה איזה ראש (תיקון 5) | Q293 |
| nail bed | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| digital pulp | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| female perineal skin | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| Camper's fascia | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| pubic symphysis | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| coracoacromial ligament | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| retrocalcaneal bursa | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| anterolateral ligament of the knee | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| triangular fibrocartilage complex | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| facet joint | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| anterior superior iliac spine | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| posterior superior iliac spine | not-shipped | n/a (not a mesh) | no | **yes** | C2 | `cited_but_not_shipped` — הסבר כתוב במקום שתיקה (תיקון 7) | Q297 / Q302 / Q298 / Q306 |
| deep peroneal nerve | structure | yes (58 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| superficial peroneal nerve | structure | yes (58 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| peroneal artery | structure | yes (4 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| profunda femoris | structure | yes (4 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| deltoid ligament | structure | yes (2 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| spring ligament | structure | yes (2 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| subacromial bursa | structure | yes (2 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| subtalar joint | structure | yes (10 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| talocrural joint | structure | yes (18 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| first metatarsophalangeal joint | structure | yes (6 meshes) | no | **yes** | C10 | `syn` (peroneal↔fibular וכו') או entry חדש (תיקון 8) | Gray's 4th ed. / Moore's 8th ed. / the project's own data/{nerves,vascular,ligaments,bursae,skeleton} |
| DPN | nerve-q304 | yes (6 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| SPN | nerve-q304 | yes (4 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| העצב הפיבולרי העמוק | nerve-q304 | yes (6 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| posterior tibial nerve | nerve-q304 | yes (12 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| medial popliteal nerve | nerve-q304 | yes (12 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| lateral popliteal nerve | nerve-q304 | yes (4 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to iliacus | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to sartorius | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to rectus femoris | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to pectineus | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to vastus lateralis | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to vastus intermedius | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to semitendinosus | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to semimembranosus | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to adductor magnus | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to gastrocnemius | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to soleus | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| nerve to popliteus | nerve-q304 | yes (1 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| medial crural cutaneous nerves | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| lateral sural cutaneous nerve | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| anterior femoral cutaneous nerves | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| common plantar digital nerves | nerve-q304 | yes (6 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| proper plantar digital nerves | nerve-q304 | yes (6 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| dorsal digital nerves of the foot | nerve-q304 | yes (8 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| muscular branches of deep peroneal nerve | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| lumboinguinal nerve | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| ענף עצב השת לסמיטנדינוזוס | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| העצב הסורלי | nerve-q304 | yes (2 meshes) | no | **yes** | C? | ? | Q304 data/derived/Q304_nerve_transfer.json + Gray's / TA |
| lateral cutaneous nerve of the forearm | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| LABCN | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| LACN | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| LCNF | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| nervus cutaneus antebrachii lateralis | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| העצב העורי הלטרלי של האמה | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| medial cutaneous nerve of the forearm | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| MACN | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| medial cutaneous nerve of the arm | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| upper lateral cutaneous nerve of the arm | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| lower lateral cutaneous nerve of the arm | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| circumflex nerve | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| SSN | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| nerve to the rhomboids | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| nerve to serratus anterior | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| nerve of Bell | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| LTN | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| nerve to latissimus dorsi | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| upper subscapular nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| lower subscapular nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| nerve to subclavius | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| dorsal cutaneous branch of the ulnar nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| recurrent branch of the median nerve | nerve-q307 | yes (8 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| thenar motor branch | nerve-q307 | yes (8 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| superficial radial nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| Wartenberg nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| deep branch of the radial nerve | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| common palmar digital nerves of the median nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| proper palmar digital nerves of the ulnar nerve | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| העצב המוסקולוקוטני | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| העצב האקסילרי | nerve-q307 | yes (6 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| העצב התורקלי הארוך | nerve-q307 | yes (2 meshes) | no | **yes** | C? | ? | Q307 data/derived/Q307_nerve_transfer.json + Gray's / TA / Qawasmi 2024 |
| שריר הירך האחורי | hebrew | yes (16 meshes) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| שכמה | hebrew | yes (34 meshes) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| שריר הכתף | hebrew | yes (12 meshes) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| כף הרגל | hebrew | yes (169 meshes) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| אגן | hebrew | yes (20 meshes) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| הטיית אגן | hebrew | n/a (not a mesh) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| שרירי כופפי הירך | hebrew | n/a (not a mesh) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| רצפת האגן | hebrew | n/a (not a mesh) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| פסואס מינור | hebrew | n/a (not a mesh) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |
| השריר הכליתי הקטן | hebrew | n/a (not a mesh) | no | **yes** | C8 | `he` ב-`synonyms_q306.json` (תיקון 10) | project-supplied translation (Q298 sources.he) |

---

## 4. חלקים, ראשים ובטנים — האם ניתן לחפש אותם בשמם?

Q293 מטבל **23 שרירים דו/תלת-ראשיים** (`data/anatomy/muscle_heads_q293.json`).

| | לפני | אחרי |
|---|---|---|
| ראשים/חלקים/בטנים שנבדקו (55 מונחים) | נגישים: **9** | נגישים: **55** |
| נגישים בכל ששת הדפים | **1** | **49** |

**הסיבה לפער.** רק **24** מבנים בדף Z נושאים בשמם `head of` / `part of`, ומתוכם **9 בלבד הם ראשי שריר**:
triceps brachii ×3, pectoralis major ×3 (ה-abdominal part נכתב כולו בסוגריים), deltoid ×3 ובנוסף
`Humero-ulnar head of flexor digitorum superficialis`. כל 20 השרירים האחרים ברשימת Q293 —
biceps brachii, biceps femoris, gastrocnemius, SCM, pronator teres, FCU, ECU, adductor magnus, soleus,
iliopsoas, adductor pollicis, FPB, medial/lateral pterygoid, quadratus plantae, adductor hallucis,
digastric, omohyoid — **אינם נשלחים כראשים נפרדים**: הראש הוא `compartment` בנתוני ה-action של Q283
ושורה ב-`muscle_heads_q293.json`, ומוצג בכרטיס ה-Learn, אבל אין לו mesh ואין לו alias.

**התיקון.** alias של ראש → **השריר האב**, עם הערה שאומרת איזה ראש זה ומאיפה. כך
`long head of biceps brachii` מגיע ל-`Biceps brachii` (ולא ל-triceps), `medial gastrocnemius`
ל-`Gastrocnemius`, `anterior deltoid` ל-`Clavicular part of deltoid muscle`, ו-`LHBT` לביצפס.
Q293 בנתה את ה-**reflected head של rectus femoris** כ-mesh נפרד מבוסס-כלל בששת הדפים, והוא נגיש בשמו.

---

## 5. הדברים שנרשמו כלא-נשלחים — האם מוחזר הסבר כנה?

Q298 בנה את התבנית (`cited_but_not_shipped`) עבור **4** שמות. המדידה על 20 המונחים:

| term | mesh exists? | לפני | אחרי |
|---|---|---|---|
| `Scarpa's fascia`, `Colles' fascia`, `Gerdy's tubercle`, `pectineal ligament` | no | **הסבר** (Q298) | הסבר |
| `nipple`, `areola`, `Cooper's ligaments` | **כן** — שלושת הדפים הנשיים | **המבנה עצמו** (עבד כבר) | המבנה + הערה שבדפים הגבריים אין אותו |
| `nail plate` | **כן** — ארבעת דפי Z | המבנה | המבנה + הערה שה-nail bed אינו קיים |
| `nail bed`, `digital pulp`, `female perineal skin`, `Camper's fascia` | no | **שתיקה** | **הסבר מצוטט** |
| `pubic symphysis` | no | **תשובה שגויה** (`Sacrococcygeal symphysis`) | **הסבר** |
| `coracoacromial ligament`, `retrocalcaneal bursa`, `anterolateral ligament`, `TFCC`, `facet joint` | no | **שתיקה** | **הסבר** |
| `ASIS`, `AIIS`, `PSIS`, `PIIS` | no (landmarks) | **שתיקה** | **הסבר** + מה נקשר שם |
| `psoas minor` | no, **בשום מקור** | **`Psoas major` בדירוג 1** | **הסבר מצוטט ראשון** |

**15 רשומות `cited_but_not_shipped` חדשות**, כל אחת עם הסיבה, המקור, והמבנים שכן קיימים שהיא מציעה
במקומה. כל 15 אומתו: אף אחת מהן אינה קיימת בשום דף (אומת אוטומטית), וכל ה-`offer` שלהן כן קיימים.

---

## 6. מה ש-Q304 מוסיף (71 עצבי גפה תחתונה בדפי Imaging) — **המקרה שחייב להיות מושלם**

התלונה המקורית של הבעלים, זו שפתחה את כל הסדרה הזו, הייתה **שהוא לא מצא את העצב הפרונאלי**. לכן כל
אחד מ-**39 העצבים המובחנים** ש-Q304 מעביר (71 meshes לדף) מקבל כאן טיפול מלא, ולא רק הגזעים:

| | לפני | אחרי |
|---|---|---|
| שמות עצבים ברשימת הייחוס | 39 | 39 |
| נגישים לפחות בדף אחד | **11** | **39** |
| קיצורים | `CPN` בלבד | **13**: CPN, CFN, DPN, DFN, SPN, SFN, MPN, LPN, SGN, ON, TN, SN, FN |
| שמות אנגליים / לטיניים | — | **105** |
| שמות עבריים | **0** | **49** |
| הענפים הנקובים (מתוך 39) | 0 | **27 — כולם** |

**הליבה: ‏`peroneal` מול `fibular`.** ‏Terminologia Anatomica אומר `fibular`; הקלינאי מקליד `peroneal`.
שמות הדף נושאים את שניהם (`Common fibular (peroneal) nerve (left)`), אבל **צירוף** כמו
`deep peroneal nerve` אינו רצף אחד בשם הזה, ולכן החזיר **0 בכל ששת הדפים**. נמדד אחרי התיקון:

| מה הוקלד | מגיע ל |
|---|---|
| `peroneal nerve`, `fibular nerve`, `common peroneal nerve`, `CPN`, `CFN`, `lateral popliteal nerve` | `Common fibular (peroneal) nerve` |
| `deep peroneal nerve`, `DPN`, `DFN`, `anterior tibial nerve`, `העצב הפיבולרי העמוק` | `Deep fibular (peroneal) nerve` |
| `superficial peroneal nerve`, `SPN`, `SFN` | `Superficial fibular (peroneal) nerve` |
| `העצב הפרונאלי` | `Common fibular (peroneal) nerve` |

**והענפים, שאיש לא היה מגיע אליהם בשמם הקליני:** `nerve to iliacus`, `nerve to sartorius`,
`nerve to rectus femoris`, `nerve to pectineus`, `nerve to vastus lateralis`,
`nerve to vastus intermedius`, `nerve to semitendinosus`, `nerve to semimembranosus`,
`nerve to adductor magnus`, `nerve to gastrocnemius`, `nerve to soleus`, `nerve to popliteus`,
`infrapatellar branch`, `medial crural cutaneous nerves`, `intermediate dorsal cutaneous nerve`,
`medial dorsal cutaneous nerve`, `medial sural cutaneous nerve`, `sural communicating branch`,
`lateral sural cutaneous nerve`, `anterior femoral cutaneous nerves`,
`common plantar digital nerves`, `proper plantar digital nerves`, `dorsal digital nerves of the foot`,
`muscular branches of deep peroneal nerve`, `femoral branch of genitofemoral nerve`,
`lumboinguinal nerve` — כולם מגיעים עכשיו, ולכל אחד גם שם עברי.

**מצב הבנייה.** שכבת ה-alias מוכנה ונמדדה, אבל ה-meshes מגיעים לדפי ה-Imaging רק עם Q304: היום
העצבים נגישים ב-**39/39 בדף Combined M** ו-36 ב-Combined F, אך רק 5 ו-8 בדפי ה-Imaging. לכן **Q306
חייב להריץ מחדש את `build_search_q298.py` מעל ה-build של Q304** ולמדוד מחדש את שתי שורות ה-Imaging
לפני הפרסום. דף Imaging מקבל את אותם מזהים כמו דף ה-Combined של אותו גוף, ולכן הציפייה היא 39 ו-36 —
**ציפייה שתימדד, לא תוצג כעובדה.**


---

## 7. סדר הביצוע של התיקונים, ומה כל אחד סגר

הסדר כאן הוא **סדר הביצוע שאושר**, לא סדר הגודל: תיקון הכנות (fuzzy) ראשון, כי הוא קטן והוא הופך כל
פער אחר לכנה בזמן שעובדים עליו; נתוני הקבוצות החסרות אחרונים, כי הם העבודה היקרה ביותר.

| סדר | התיקון | קובץ הנתונים | מונחים שנסגרו |
|---|---|---|---|
| **1** | **לומר כשההתאמה היא מקורבת בלבד** (`approx`), ולהעלות הסבר מדויק מעל שורות מבנה שלא התאימו (`note_first`) | `viewer/q298/search.js` (‏+14 שורות) | מונע 2 מחלקות של **תשובה שגויה** |
| **2** | **שמות קליניים ל-93 הקבוצות הפונקציונליות** (87 action-derived + 6 extras), + עברית, + תיקון 62 תוויות פגומות | `data/anatomy/groups_q306.json` | 36 |
| **3** | **רשומת `concept` ל-pelvic tilt** ×4, מצוטטת מ-5 מאמרי PubMed | `data/anatomy/concepts_q306.json` | 6 |
| **4** | **`cited_but_not_shipped` ל-psoas minor** עם שיעור ההיעדר, origin/insertion ומידות מצוטטים | `data/anatomy/synonyms_q306.json` | 3 |
| **5** | **32 הקיצורים של הפרויקט עצמו** שהמבנה שלהם קיים | `synonyms_q306.json` | 32 |
| **6** | **46 שמות ראשים / חלקים / בטנים** → השריר האב + הערה | `synonyms_q306.json` | 46 |
| **7** | **שכבת מושגים ואזורים** — 38 רשומות (13 אזורים, 10 אבחנות, 6 תיאורי יציבה, 5 מדדים, 4 מושגים) | `concepts_q306.json` | 36 |
| **8** | **הסברים כנים ל-11 ההיעדרים השותקים** + alias ל-4 שכן קיימים | `synonyms_q306.json` | 20 |
| **9** | **13 אי-התאמות מינוח** | `synonyms_q306.json` | 13 |
| **9א** | **כל 39 העצבים של Q304** — 12 גזעים + **27 ענפים נקובים**, 13 קיצורים, 105 שמות אנגליים/לטיניים, 49 שמות עבריים, `peroneal`↔`fibular` | `synonyms_q306.json` (נבנה ב-`mknerves.py`) | 39 |
| **10** | **15 מונחים עממיים** | `synonyms_q306.json` | 15 |
| **11** | **שמות עברית חסרים** | `synonyms_q306.json` | 10 |
| **12** | **18 קבוצות קליניות חדשות עם חברות מצוטטת** (129 חברים), **7 מהן מסומנות `contested`** עם מה שחלוק | `data/anatomy/muscle_groups_q306.json` | 19 |
| **13** | **תיקון נלווה:** הריפוד שמחזיר את סופה של רשימת התוצאות בטלפון (ראו §9) | `viewer/q306/q306.css` (20 שורות) | — |

### מה נוסף בסך הכל

| | |
|---|---|
| רשומות synonym חדשות | **132** (‏61 קיצורים, 465 שמות שניים באנגלית/לטינית/עממית, 220 שמות עברית) |
| משפחות (`re`) | **3** — intervertebral discs, metatarsals, ribs |
| רשומות `cited_but_not_shipped` | **15** |
| שמות לקבוצות פונקציונליות | **93** (‏87 action + 6 extras), **62 תוויות תוקנו** |
| קבוצות חדשות עם חברות מצוטטת | **18**, ‏129 חברים, **7 contested** |
| רשומות מושג | **38**, ‏**44 טענות מצוטטות**, ‏243 מבנים מוצעים, 52 קבוצות מוצעות |
| מתוכן, עצבי Q304 | **39 רשומות** — 13 קיצורים, 105 שמות אנגליים/לטיניים, 49 עבריים |
| צורות חיפוש חדשות בסך הכל | **665** |

### בדיקות שכל קובץ נתונים עבר לפני שנכתב

* כל 132 הרשומות נפתרות לפחות בדף אחד — **0 רשומות ריקות**.
* כל **61 הקיצורים** מגיעים למבנה שקיים באמת — **0 יתומים** (הכלל של Q298, נשמר).
* כל **39 שמות העצבים** של Q304 נפתרים (היום על דפי Z/Combined; על דפי Imaging עם Q304).
* כל **15** רשומות ה-`cited_but_not_shipped` אומתו כבאמת חסרות בכל ששת הדפים, וכל ה-`offer` שלהן נפתרים.
* כל **243** המבנים שרשומות המושג מציעות נפתרים, וכל **52** הקבוצות שהן מציעות קיימות.
* כל **129** חברי הקבוצות החדשות נפתרים; **6** חברים שנקבעו מהמקור אך אינם קיימים בשום דף נרשמו
  ב-`not_on_any_page` במקום להיעלם: `puborectalis` (נשלח בתוך ה-mesh של levator ani), `buccinator`,
  `depressor supercilii` ושלושת ה-`auricularis`.

### מה נותר, ומדוע

| מה | מדוע |
|---|---|
| **2,164–2,190 מבנים בדפי Z בלי שדה Latin** | פגם נתונים במקור Z-Anatomy. דורש מקור TA שאין לנו → **החלטת בעלים** (`docs/OPEN_ITEMS_FOR_OWNER.md`) |
| **59 ערכי Latin המשותפים ל-407 מבנים**, מהם 16 נושאים `Os temporale` בשגגה | אותו דבר — תג אזור ולא שם TA. לא תוקן; מתועד |
| **6 חברי קבוצה שאין להם mesh** | היעדר גאומטריה, לא היעדר חיפוש. מתועד ב-`not_on_any_page` |
| **7 היעדרים חדשים** (pubic symphysis, coracoacromial ligament, retrocalcaneal bursa, ALL, TFCC, facet joint, iliac spines) | אין מקור שבידינו. עונים בהסבר, לא בשתיקה |
| **psoas minor** | אין בשום מקור. עונה בהסבר מצוטט |

**הערה על ה-fuzzy:** החוק של Q298 ש-fuzzy רץ רק כשדבר אחר לא התאים **לא שונה** (הוא מה ששומר על
1.3 מילישניות להקשה). מה שהשתנה הוא שעכשיו הדף **אומר** שזו התאמה מקורבת. נמדד:
`gastrocnemus` ו-`iliotibal band` (שגיאות כתיב) מסומנות `approx=1` ומוצאות את המבנה;
`hamstrings` ו-`long head of biceps brachii` (התאמות אמיתיות) **אינן** מסומנות; `psoas minor` מקבלת
`note_first=1` וההסבר עולה מעל השורות.

---

## 8. העברית — הצהרה, לא מינוח

**חוזר על ההצהרה של Q298 מילה במילה, כי היא עדיין נכונה ועדיין פתוחה.** ל-Terminologia Anatomica
**אין מהדורה עברית**. כל השמות העבריים בפרויקט — 151 ב-Q298 ועוד **220** בסבב הזה (מבנים, 93 הקבוצות
הפונקציונליות, 18 הקבוצות החדשות, 38 המושגים, 39 העצבים של Q304) — הם **תרגום שנכתב עבור הפרויקט הזה
לבקשת הבעלים, ואינם מינוח מוסמך**. הם עזר חיפוש בלבד; כל עובדה אנטומית וכל טקסט כרטיס נשארים באנגלית /
לטינית המצוטטת של המקורות.

ההצהרה הזו מופיעה בכל ארבעת קבצי הנתונים החדשים (`synonyms_q306.json` ב-`sources.he`,
ו-`he_note` ב-`groups_q306.json`, `concepts_q306.json` ו-`muscle_groups_q306.json`), ו-
`tests/test_q306.py::test_hebrew_is_declared_a_project_translation_everywhere` מקבע אותה כדי שסבב עתידי
לא ישמיט אותה בשקט.

**הבעלים נשאל על כך ב-Q298 ועדיין לא ענה.** אין לפרש את השתיקה כאישור: הבקשה חוזרת ב-
`docs/OPEN_ITEMS_FOR_OWNER.md` תחת Q306, עם רשימה ממוקדת של מה שכדאי שיבדוק — שמות ההטיות
(`הטיית אגן קדמית` / `אחורית` / `צידית`), שמות הקבוצות (`כופפי הירך`, `פושטי הברך`, `מסובבי חוצה הירך`,
`מטי שורש כף היד רדיאלית`), `השריר הכליתי הקטן` כשם העברי של psoas minor, ושמות 39 העצבים. אם יבקש
להסיר — נסיר.

---

## 9. תיקון נלווה: רשימת תוצאות החיפוש שלא ניתן להקיש על סופה ב-390 פיקסל

Q304 מצא את זה בריצת הטלפון שלו והשאיר אותו להחלטת הבעלים, כי הוא פגם של שכבת Q301 ולא שלו. הוא מתוקן
**כאן**, כי הרשימה שלא ניתן להקיש על סופה היא רשימת תוצאות החיפוש — התכונה שהסבב הזה מספק.

**הפגם.** בטלפון שני המנועים שמים את רשימת המבנים **אחרונה** בתוך פאנל מסוג bottom-sheet, וסרגל הבקרה
הקבוע של Q301 (`#q301-bar`) צף מעל אותה רצועה תחתונה ב-z-index גבוה בהרבה. הפאנל כבר גלול עד סופו, ולכן
השורות האחרונות של תוצאה **קצרה** אינן נגישות בגלילה ואינן ניתנות להקשה כלל. הפתרון העוקף של המשתמש היה
להקליד פחות אותיות, כדי שהרשימה תתארך דייה כדי לגלול את השורה הרצויה למעלה.

**התיקון** (`viewer/q306/q306.css`, 20 שורות) הוא בדיוק התבנית ששני המנועים כבר משתמשים בה לאותה מטרה:
Q270 שומר את רצועת ה-`#foot` מתחת לאזור הגלילה של ה-rail ב-`padding-bottom`, והמנוע שלנו שומר כך את
סרגל המובייל שלו. כאן הרצועה הנשמרת היא `--q301-bar-h`, ש-`groups.js` של Q301 כבר מחשב לגובה
ה**מוסתר כולו** (הסרגל + 4 פיקסל + גיליון קבוצה פתוח) ומעדכן בכל פתיחה וסגירה — כך שהריפוד עוקב אחרי
החסימה האמיתית ולא אחרי מספר שניחשנו.

**למה זה לא יכול לדחוף את הסרגל של Q301 או את סרגל השבבים של Q300**, שהתנגשו זה בזה פעם אחת כבר: הכלל
מוסיף ריפוד **בתוך** הפאנל הנגלל. הוא אינו משנה מיקום, transform או z-index של שום אלמנט, ואינו נוגע
ב-`#q301-bar`, ב-`#sa-bar` או ב-`#hist-msg` — אלה מורמים על ידי ה-`transform` של Q301 עצמו, שנשאר כפי
שהיה. הריפוד **מצטרף** לריפוד הקיים של כל מנוע ולא מחליף אותו, ולכן רצועת ה-`#foot` של Q270 ורצועת
המובייל של המנוע שלנו שורדות שתיהן. אין צורך ב-`!important`: הסלקטור שלנו ספציפי יותר מהקיים
(`body.q301-on #rail` מול `#rail`).

שני המנועים מגדרים את פריסת הטלפון שלהם **שונה**, ולכן גם הכללים: כללי ה-bottom-sheet של ה-rail יושבים
בתוך `@media (max-width:900px)`, ואלה של המנוע שלנו מופעלים על ידי המחלקה `.phone` שקוד הפריסה שלו
מוסיף (ללא media query). התאמה לגדר של כל מנוע היא מה שמונע מהכלל לפעול על שולחן עבודה, שם אין חסימה.

**האימות הנדרש** (‏`scripts/anatomy/q306/verify_q306.py`, בשיטת Q300/Q303 — ‏`document.elementFromPoint`
נקרא בתוך הדף, לא `page.screenshot`): הפגם משוחזר **לפני** התיקון, ואחריו `elementFromPoint` במרכז
השורה האחרונה חייב להחזיר **את השורה**, בשני המנועים; ובמקביל Undo, Redo, כל כפתור בגיליון קבוצה פתוח
וסרגל השבבים של Q300 חייבים להמשיך להחזיר את עצמם, ובשולחן העבודה הריפוד אינו פועל כלל.

---

## 10. שתי תוצאות נלוות בנתוני ההרחבות של Q298

### 10א. הפער ש-Q307 מצא — נסגר

Q307 גילה ש-**טבלות ה-adjacency וה-relations של Q298 מעולם לא הורצו מחדש** אחרי העברות העצבים של
Q304 ו-Q307: הן נתונים מקובעים ש-`--inject` רק מעתיק, ולכן כל עצב חדש בדפי ה-Imaging הגיע בלי
`Adjacent`, בלי `Related` ובלי קבוצה. הורצו מחדש כאן, **רק לשני דפי ה-Imaging** — הגאומטריה של ארבעת
דפי ה-Z לא השתנתה כלל ב-Q304/Q307, ולכן אין מה להריץ עליהם, וזה גם מה שמאפשר לבלוק של Q298 להישאר
זהה-בייט בארבעתם.

| | Imaging M | Imaging F |
|---|---|---|
| מבנים | 951 → **1,079** | 1,104 → **1,228** |
| זוגות adjacent | 10,190 → **11,975** | 11,688 → **13,740** |
| שכנים למבנה (חציון / מקס') | 15 / 238 → **16 / 256** | 15 / 265 → **16 / 281** |
| מבנים מבודדים | 0 → **0** | 0 → **0** |
| קישורי relation | 10,396 → **12,084** | 11,416 → **12,946** |
| מבנים עם קישורים | 487 → **575** | 539 → **623** |
| **העצבים שנוספו** | 129 | 126 |
| מהם עם `Adjacent` | **129 / 129** | **126 / 126** |
| מהם עם `Related` | **89** | **86** |
| מהם בקבוצה פונקציונלית | 0 | 0 |

**שתי השורות האחרונות אינן פגם.** ‏`Related` נבנה מהשדות המצוטטים של הכרטיסים עצמם, ולכן עצב מקבל
קישור רק אם שריר כלשהו מצהיר עליו כעצב שלו — 89 ו-86 כאלה, והשאר ענפים שאף כרטיס אינו נוקב בהם.
הקבוצות הפונקציונליות הן קבוצות **שרירים** (נגזרות מנתוני התנועה), ולכן עצב איננו חבר בהן מעצם הגדרתן.
העלות התבררה כזולה: **56 שניות לדף**, ‏122 ו-145 ק"ב.

### 10ב. ‼ טענת הדיוק של Q298 נמדדה מחדש, והיא מגדילה את הדיוק שבפועל

הטסט של Q298 שמודד מחדש זוגות adjacent אמיתיים נפל על הטבלה החדשה, וזה התברר כ**ממצא** ולא כתקלה.
`threshold_mm` בקובץ הנתונים הוא **3.46 מ"מ = sqrt(3) × cell**, וזה **אינו החסם הנכון**: שתי נקודות
דגימה שמדדי ה-voxel שלהן נבדלים בלא יותר מ-1 בכל ציר נמצאות בתוך תיבה שצלעה `2 × cell`, ולכן החסם
ההדוק על המרחק ביניהן הוא **sqrt(3) × 2 × cell = 6.93 מ"מ**. ה-3.46 הוא החסם על **מרכזי ה-voxel**, לא
על נקודות המשטח. הטסט המקורי עבר רק מפני שה-seed הקבוע שלו הגריל 25 זוגות שכולם נפלו מתחת ל-3.46;
על הטבלה החדשה (11,975 זוגות במקום 10,190) אותו seed מגריל זוגות אחרים, ושניים מהם נמדדים 3.67 ו-3.95.

נמדד כאן על **120 זוגות adjacent מוגרלים** ב-Imaging M (`data/derived/Q306_adjacency_threshold.json`):

| | מ"מ |
|---|---|
| חציון | **0.18** |
| ממוצע | **0.97** |
| אחוזון 95 | **3.64** |
| מקסימום | **4.45** |
| מעל 3.46 שנרשם | **10 מ-120 (8.3 %)** |
| החסם ההדוק הגאומטרי | **6.93** |

כלומר הזוג האופייני **קרוב בהרבה** ממה שהדף מצהיר, והזנב חורג ממנו — בדיוק כפי שהגאומטריה מחייבת.
‏`tests/test_q298.py::test_adjacency_is_within_the_stated_threshold_on_a_real_sample` **מקבע עכשיו את
החסם ההדוק** (שאי אפשר לחרוג ממנו) **ובמקביל שהחציון נשאר בתוך המספר שהדף מדפיס** — כך שהטענה נשארת
כנה בשני הכיוונים ורגרסיה בכל אחד מהם תיתפס. **הטסט לא רופף; הוא מקבע את המספר הנכון.**

**מה שלא נעשה, במכוון:** תיקון המספר ש**הדף מדפיס**. ‏`threshold_mm` רוכב בתוך הבלוק של Q298 בכל ששת
הדפים, וסבב Q306 שומר על הבלוק הזה זהה-בייט בארבעת דפי ה-Z. תיקון המספר דורש הרצה מחדש של ה-adjacency
בששת הדפים ופרסום הבלוק של Q298 מחדש בכולם — סבב בפני עצמו. מובא לבעלים ב-
`docs/OPEN_ITEMS_FOR_OWNER.md` תחת Q306 כהחלטה שלישית.
