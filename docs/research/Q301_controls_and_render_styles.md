# Q301 — פקד אחד, קבוצות שנפתחות, וסגנונות רינדור רדיוגרפיים

**מה נשאל (הבעלים, בתרגום מעברית).** (1) «חסר CONTROL ברור ופשוט, כולל UNDO ו-REDO». (2) «ה-IMAGING צריך לשבת תחת קופסה אחת שנפתחת לכמה אפשרויות. וכך גם לשאר החלקים». (3) «חומר אינפורמטיבי כללי — למשל המקורות של המודל — יכול להיות סתם ⓘ קטן בעיגול בצד, קטן ולא מפריע». (4) «פעולות שאפשר לשלב, כמו CUT ו-IMAGING, צריכות להיראות ניתנות לשילוב; ואלה שאי אפשר — להיראות בלתי ניתנות». (5) «המודל עצמו צריך להציע רינדור X-RAY / CT / MRI שדומה לשחזורים האמיתיים שלהם — מחליף את תמונת הצבע בסגנון שהמשתמש מבקש, ולחיצה אחת מחזירה». (6) «שומן סתמי במקומות שונים — להראות רק כשמבקשים במפורש, לא כברירת מחדל». (7) «הסליידרים של מבני הגוף צריכים לאפשר גם חשיפה הדרגתית לפי שכבות, לא רק לפי מערכות, ועוד מה שמקובל — לבדוק אתרים ואטלסים אחרים».

**המסמך הזה ממשיך את `docs/research/Q300_interface_benchmark.md`** ואינו חוזר עליו. Q300 קבע את הדפוסים של "יציאה מכל מסלול הסתרה", של model reset ושל ה-bone pass; כאן מורחב הבנצ'מרק לארבעה נושאים שלא נבדקו שם: **קיבוץ סרגל וחשיפה הדרגתית**, **היכן יושבים Undo/Redo**, **איך מוצגים סגנונות רינדור רדיוגרפיים**, ו-**פקדי חשיפה לפי שכבות**.

**מצב הרשת, שוב.** `WebFetch` נחסם ב-DNS גם בסבב הזה — נוסה `learn.microsoft.com` ונכשל ב-`getaddrinfo ENOTFOUND`, בנוסף לכל אתרי המוצר שנחסמו ב-Q300. **כל קביעה בטבלאות נשענת על ציטוט שחזר מ-`WebSearch`**, והיכן שלא נמצא ציטוט כתוב **"לא אומת"**. מה שלא נמצא לו מקור אמין מסומן כך במפורש ולא הושלם בניחוש.

---

## 1. קיבוץ הסרגל וחשיפה הדרגתית — מה עושים המוצרים

| מוצר | הדפוס | הציטוט | מה נלמד |
|---|---|---|---|
| **BioDigital Human** (נובמבר 2020) | **כל כלי החקירה לתוך תפריט אחד** | «The exploration tools were moved into a single menu with a universally recognizable menu icon»; «"Explore Tools" was renamed to "Explore"» | **זה בדיוק מה שהבעלים ביקש בסעיף 2.** מוצר מוביל עשה את המעבר הזה מרצון, אחרי שהתפריט שלו גדל |
| **BioDigital Human** (נובמבר 2020) | **Undo ו-Redo קיבלו סרגל נפרד משל עצמם** | «Undo and Redo moved to their own toolbar» | **הציטוט המכריע לסעיף 1.** לא "עוד שני כפתורים בתוך תפריט" — **סרגל משלהם**. אצלנו הם צפים (Q294) בלי שם ובלי טקסט; הבעלים לא מוצא אותם |
| **BioDigital Human** (נובמבר 2020) | פקדי הניווט ב-3D לתפריט נפרד, מקופל | «The 3D navigation controls were split into their own menu, collapsed under a location icon» | קיבוץ **לפי משפחה**, וכל משפחה מקופלת מאחורי אייקון אחד |
| **BioDigital Human** (נובמבר 2019) | הכלים נבנו מחדש לתפריט אחד, ו-**X-Ray בוטל ככלי** | «rebuilt the tools into one menu with Select (default), Hide, and Fade options, which replaced Dissect, Isolate, and X-Ray» | ממצא שלילי חשוב: BioDigital **הסירה** X-Ray מרשימת הכלים והשאירה Hide/Fade. כלומר "x-ray" כשקיפות הוא דפוס שמוצר מוביל זנח — מה שמחזק את הבחירה שלנו להפוך את ה-X-ray ל**סגנון רינדור** ולא ל"עוד שקיפות" |
| **BioDigital Human** (נובמבר 2019) | ה-Reset שמופיע לפי צורך | «a Reset button appears once a hide, isolate, or fade tool has been used» | אישור חוזר ל-Q300 §4.1, מגרסה אחרת של התיעוד |
| **Visible Body** | **History button אחד** בסרגל התחתון = undo + redo + חזרה למקור | «you select the History button from the bottom menu bar, and from there you can undo or redo edits or refresh the model to its original state» (צוטט ב-Q300); וכן «a Tools menu with History buttons for undoing hides» | שני הדפוסים ל-Undo/Redo בשוק: **סרגל משלהם** (BioDigital) או **כפתור History בסרגל התחתון** (Visible Body). שניהם **בסרגל התחתון** ושניהם **עם שם**, לא אייקון בודד צף |
| **Visible Body** | הסרגל התחתון הוא מקום הפקדים הראשי | «the gear icon in the bottom menu opens Settings on mobile»; «Dissect is in the bottom menu bar»; «Anatomy Search ... is located in the bottom menu bar»; «The Multi-select button also sits in that bar»; «select "Save View" from the bottom menu bar» | הסרגל התחתון מרכז **את כל המשפחות**: dissect, search, multi-select, save view, settings. מאשר את כלל thumb-zone של Q300 |
| **Visible Body Suite** | כניסה לתפריט הראשי דרך אייקון ארבעה ריבועים | «click the menu icon (four squares) in the bottom toolbar to go to the main menu» | אייקון אחד → תפריט. חשיפה הדרגתית בדרגה אחת, לא שתיים |
| **Complete Anatomy** | עומס מסך מתועד כביקורת | פוסטר AAA 2019 (צוטט ב-Q300): «lots on screen» | האילוץ: מה שמתווסף חייב להחליף או להתקפל |
| **הנחיות כלליות** | Undo ו-Redo יחד, ובתחילת הסרגל | מקור משני על פריסת סרגלים: undo ו-redo «are commonly kept together, since editing tends to move back and forth»; תיעוד עורך Cristal (XWiki) מציב undo ו-redo «at the start of its toolbar, separate from other editor functions, to emphasize them» | **לא אומת כנגד NN/g** — החיפוש לא החזיר אף דף של nngroup.com. מקורות משניים בלבד, ומסומנים כך |
| **הנחיות כלליות** | אל תסתיר תוצאות של פעולה הרסנית מאחורי חשיפה הדרגתית | מקור משני (מדריך נגישות): להימנע מהסתרת ההשלכות של פעולה הרסנית מאחורי progressive disclosure | **לא אומת** (משני). ובכל זאת מכתיב: "הראה הכול" ו-"reset המודל" **לא** ייכנסו לתוך קבוצה מקופלת — הם נשארים בשורה הגלויה |
| **Microsoft Win32 UX Guide** | — | **לא נקרא.** `learn.microsoft.com` נכשל ב-DNS (`ENOTFOUND`). הדף `ctrl-progressive-disclosure-controls` קיים בתוצאות החיפוש אבל תוכנו לא אומת | אם הבעלים יפתח את הדומיין, אפשר להעמיק |

**המסקנה לסעיפים 1–2.** שני הדפוסים שהשוק מסכים עליהם הם: (א) **תפריט אחד לכל משפחת כלים**, ו-(ב) **Undo/Redo בסרגל משל עצמם, בתחתית, עם שם**. שניהם נבנים כאן בפקד אחד.

---

## 2. סגנונות רינדור רדיוגרפיים — מה באמת קיים בשוק

| מוצר | מה נמצא | הציטוט | הערכה |
|---|---|---|---|
| **Visible Body** | **אין סגנון רינדור x-ray.** מה שיש הוא **תמונות אבחון אמיתיות** להשוואה לצד המודל | «the Images tray lets you compare 3D models to diagnostic images, and cadaver scans»; ה-Views כוללים «a series of sliced 3D models» | החיפוש **לא מצא** תיעוד של כפתור x-ray או של רינדור גווני-אפור ב-Visible Body. **לא אומת שקיים** |
| **Complete Anatomy** | **אין תיעוד לסגנון x-ray.** מה שיש הוא ספריית רדיולוגיה | «Interactive radiology - explore radiographs, CTs, and MRIs from a library of 100+ interconnected images» | **לא אומת שקיים** מצב x-ray. Q300 כבר רשם את זה כפריט "ללא מקור אמין" |
| **Anatomage Table** | שחזור נפחי אמיתי של סריקות שמייבאים, לא סגנון על המודל האנטומי | «designed for 3D visualization of CT and MRI data (DICOM), with volume rendering tools and a side-by-side view of 2D slices and the 3D rendering»; וגם: תמונות מיובאות «won't have full visualization and dissection capabilities like the built-in gross anatomy models» | Anatomage מפרידה בחדות: **המודל האנטומי** בצבע, **הסריקה** בגווני אפור. אין "המודל בסגנון CT" |
| **BioDigital** | הסירה X-Ray ככלי (ראו §1) | «...replaced Dissect, Isolate, and X-Ray» | ממצא שלילי |
| **3D Slicer** | **presets לפי רקמה**, בשמות שהם סוג-של-תקן בתחום | הדרכה: «select the CT-AAA preset to reveal the skull»; «select the MR-default preset for an MR render»; פורום Slicer מזכיר «US-Fetal/MR-Default/CT-Chest-Contrast-Enhanced» כברירות המחדל ל-dynamic range נמוך/בינוני/גבוה. Cornerstone.js (פרויקט אחר) מציג רשימה: «CT-AAA, CT-AAA2, CT-Bone, CT-Chest-Contrast-Enhanced, CT-Lung, CT-MIP, MR-Angio, MR-Default, MR-MIP, MR-T2-Brain, DTI-FA-Brain» | **הדפוס שאנחנו מאמצים לשמות ולמספר הצעדים**: preset בודד לכל אופן דימות, בשם שאומר "CT" או "MR". הרשימה המלאה של Slicer עצמו **לא אומתה** (רק CT-AAA ו-MR-Default אומתו ישירות) |
| **MIP** | קיים בשמות ה-presets כסגנון מוכר | «CT-MIP», «MR-MIP» ברשימת Cornerstone | מאשר ש"הטלה מצטברת לאורך הקרן" היא קטגוריית תצוגה מוכרת, לא המצאה שלנו |

**המסקנה לסעיף 5, והיא לא טריוויאלית.** **אף אטלס אנטומי מסחרי שנמצא לו תיעוד לא מציע את מה שהבעלים מבקש.** מי שמציג רדיולוגיה מציג **תמונות אמיתיות** לצד המודל (Visible Body, Complete Anatomy) או **שחזור נפחי של סריקה אמיתית** (Anatomage) — לא "המודל האנטומי מצויר בסגנון CT". הדפוס הקרוב ביותר שכן מתועד הוא **ה-presets של 3D Slicer / Cornerstone**: preset אחד לכל אופן דימות שמחליף את מיפוי הצבע כולו. **לכן הסגנונות שלנו נבנים כ-presets בסגנון Slicer, ולא כחיקוי של מוצר אטלס כלשהו** — ואין לנו על מי להישען בעיצוב, מה שמחייב שהפיזיקה עצמה תהיה אמיתית ומצוטטת. ראו §3.

---

## 3. איך כל סגנון מחושב, ומאיזה נתון אמיתי

הנתונים כבר נמצאים על **כל** עמוד: `clinical_imaging_tissues.json` (92,467 בתים) נשלח כקובץ-אחים בכל ששת העמודים מאז Q226, ובו 33 מחלקות רקמה עם **CT HU** ועם **בריכות MRI (PD / T1 / T2 / T2\*) ל-1.5 T**, לכל ערך **status** משלו (`verified` / `derived` / `secondary_checked` / `assumption` / `recalled_unverified`), וכן `ct_windows`, `mr_sequences` ו-`mapping_rules` שממפות מבנה → מחלקה. המודול החדש קורא את הקובץ הזה ב-`fetch`; **שום מספר אינו נכתב מחדש בקוד התצוגה**.

### 3.1 X-ray — DRR אמיתי, בחישוב שהמנועים שלנו כבר יודעים לעשות

הפיזיקה, מצוטטת: DRR הוא «an x-ray image that has been constructed by simulating the passage of x-rays through a CT volume», ובנוי על חוק Beer–Lambert, «which models radiographic imaging as an exponential attenuation process along rays», כלומר **I = I₀·exp(−∫μ dℓ)**; «CT scanners produce attenuation values in Hounsfield units, but we will assume that we have converted this to attenuation values in units of "fraction of x-ray absorbed per unit length", denoted μ».

ההמרה מ-HU ל-μ היא **הגדרת ה-HU עצמה**: μ/μ_water = 1 + HU/1000. אין כאן שום בחירה שלנו.

**התובנה שמאפשרת את זה בלי volume ובלי float render target:** ערבוב אלפא רגיל (`SRC_ALPHA, ONE_MINUS_SRC_ALPHA`) על רקע שחור מצטבר ל-‎1 − ∏(1 − aᵢ)‎. אם נציב **aᵢ = 1 − exp(−μᵢ·dᵢ)**, אז ‎∏(1 − aᵢ) = exp(−Σ μᵢdᵢ)‎ — **בדיוק** ה-transmission של Beer–Lambert — והפיקסל יוצא ‎1 − I/I₀‎, כלומר **ההחלשה המצטברת**, שבהסכמה הרדיוגרפית מוצגת בהיר (עצם לבנה). שלוש תכונות שהופכות את זה לנכון ולא רק לנוח:
1. **אי-תלות בסדר הציור.** ‎1 − ∏(1 − aᵢ)‎ הוא סימטרי, ולכן אין צורך במיון לפי עומק — הכשל שהציק לכל pass שקוף אצלנו עד כה.
2. **כל קונכייה סגורה נחצית פעמיים** (פאה קדמית ואחורית) — וזה **נכון פיזיקלית**: קרן אמיתית נכנסת ויוצאת. Q300 §3 זיהתה את הכפילות הזאת כ**באג** במסלול האלפא הישן, ובמסלול הזה היא **דרישה**. לכן ב-X-ray יש להשאיר `CULL_FACE` כבוי (מנוע Z) ו-`DoubleSide` (מנוע own), והמסמך הזה רושם במפורש שאין סתירה בין שתי הקביעות.
3. **אין תוספת pass ואין גיאומטריה חדשה.** המנועים כבר מציירים pass שקוף בלי depthMask; רק האלפא והצבע מוחלפים.

אורך המסלול לכל חציה הוא **d₀** — קבוע לכל חציה. **זו המוסכמה היחידה שלנו כאן.**

**מה נשקל ולא נשלח, ולמה.** גורם ה-obliquity ‎1/|cos θ|‎ (מסלול ארוך יותר דרך קונכייה שנחצית באלכסון) הוא פיזיקה אמיתית וניתן לחישוב לכל פרגמנט במנוע Z, שבו ה-shader שלנו מחזיק את הנורמל. **הוא לא נשלח**, כי במנוע own אותו גורם מחייב טלאי ב-shader של `MeshPhongMaterial` דרך `onBeforeCompile`, ושני המנועים היו מחשבים אז מתמטיקה שונה. כלל הפרויקט ("שני המנועים מתנהגים זהה") גובר על דיוק נוסף במנוע אחד; זה נרשם כאן כדי שלא ייראה כאילו נשכח.

**d₀ נבחר במדידה, לא בניחוש.** הורץ דפדפן אמיתי על עמוד Imaging M והוגדל d₀ בשמונה צעדים, עם מדידת הפיקסלים דרך ה-hook בתוך הדף (ראו §3.7):

| d₀ | luminance ממוצעת | sd (הניגודיות של התמונה) | החלק העליון של ההיסטוגרמה | החלק התחתון |
|---|---|---|---|---|
| 0.03 | 69.7 | 33.3 | 0.000 | 0.169 |
| **0.05** | 101.1 | 44.9 | 0.001 | 0.096 |
| 0.07 | 125.8 | 51.0 | 0.007 | 0.022 |
| **0.10** | 152.3 | **56.6** | 0.069 | 0.020 |
| 0.14 | 177.2 | 57.5 | 0.246 | 0.013 |
| **0.20** | 200.4 | 54.7 | 0.483 | 0.009 |
| 0.30 | 220.1 | 48.0 | 0.672 | 0.009 |
| 0.55 | 238.0 | 36.6 | 0.861 | 0.000 |

הניגודיות שיא סביב ‎0.10–0.14‎, והאורות מתחילים להישרף מעל ‎0.14‎ (רביע מהמודל בבין העליון). לכן שלושת הצעדים הם **0.05 / 0.10 / 0.20** בשמות `Soft / Normal / Hard` — דפוס ה-Shift של Slicer שצוטט ב-Q300 («Move all the inner points ... of the current transfer functions to the right/left»), בלחיצות ולא בסליידר.

**וברירת המחדל שונה בין המנועים, גם היא במדידה** (בדיוק כמו שעשתה Q300 ל-`boneRead`): עמודי Z נושאים **3,252** meshes מול ‎~950‎ בעמודי Imaging, כך שקרן חוצה פי ‎3–4‎ יותר קונכיות ואותו d₀ שורף את האורות (ב-0.10 יצאה luminance ‎206/255‎ וחצי מהמודל בבין העליון). לכן **Z מתחיל ב-Soft ו-own ב-Normal**.

### 3.2 CT — חלון HU אמיתי

הפיזיקה, מצוטטת: «the window level (WL), often also referred to as window center, is the midpoint of the range of the CT numbers displayed»; «uppergraylevel = windowlevel + windowwidth/2; lowergraylevel = windowlevel − windowwidth/2»; «A windowing operation involves selecting a range of intensities (the window width) around a central intensity value (the window level or center) and mapping this range to the displayable range of intensities (usually 0-255 for an 8-bit display). Intensities outside the selected range are either set to the minimum or maximum displayable value.»

לכן grey(HU) = clamp((HU − (L − W/2)) / W, 0, 1), והחלונות נלקחים מ-`ct_windows` של הקובץ עצמו. שלושה צעדים: **MSK** (W1000/L250 — הקובץ עצמו מצהיר `"owner convention for this simulation, not from a citation"`), **Soft tissue** (W400/L40, `"convention W400 / L40"`), **Bone** (W1800/L400, `"convention W1800 / L400"`). זה אינו חתך אלא **ה-look של preset נפחי** בסגנון `CT-Bone` של Slicer: כל מבנה נצבע באפור של ה-HU שלו, עם הצללה רגילה.

### 3.3 MRI — אות spin-echo אמיתי מ-PD/T1/T2

הפיזיקה, מצוטטת: «S = k ρ (1-exp(-TR/T1)) exp(-TE/T2)» (ספר הלימוד של RIT), ובצורה שקולה «S α PD {1-e–TR/T1}e–TE/T2». דיכוי שומן: «"Proton Density-weighted" MRI minimize T1 influences via long TR AND minimize T2 influences via short TE». (וריאנט עם ‎(TR−TE)‎ במונה קיים ב-magnetic-resonance.org ו**לא** אומץ; הצורה של RIT/UCSD היא «the more common teaching version».)

הסכימה עובדת על **בריכות** (`pools`) לכל מחלקה — `frac`, `pd`, `t1`, `t2`, `fat` — ומכפילה את חלקה של בריכת שומן ב-`mr_global.fat_suppression_residual = 0.05` כשה-sequence הוא `fatsat`. שלושה צעדים נלקחים מ-`mr_sequences` של הקובץ: **T1** (`t1_se`, TR 500 / TE 15), **T2** (`t2_se`, TR 4000 / TE 100), **PD-FS** (`pd_fs`, TR 2500 / TE 30, `"MSK workhorse"`).

### 3.4 הטבלה שיוצאת מהנתונים האמיתיים — זו ההוכחה שהסגנונות באמת שונים

מחושב מ-`clinical/data/imaging_tissues.json` בפועל (סקריפט בתיקיית ה-scratchpad של הסבב). `status(HU)` הוא ה-status שהקובץ עצמו נותן לערך ה-HU.

| class | HU | status(HU) | mu/mu_water | CT msk W1000/L250 | CT soft W400/L40 | T1 SE | T2 SE | PD FS |
|---|---|---|---|---|---|---|---|---|
| `skin` | 50.0 | recalled_unverified | 1.050 | 0.300 | 0.525 | 0.237 | 0.113 | 0.384 |
| `fat` | -106.0 | verified | 0.894 | 0.144 | 0.135 | 0.609 | 0.233 | 0.030 |
| `soft_unassigned` | 40.0 | assumption | 1.040 | 0.290 | 0.500 | 0.230 | 0.139 | 0.418 |
| `muscle` | 45.5 | verified | 1.046 | 0.295 | 0.514 | 0.220 | 0.080 | 0.366 |
| `tendon_ligament` | 70.0 | recalled_unverified | 1.070 | 0.320 | 0.575 | 0.028 | 0.000 | 0.004 |
| `cartilage` | 100.0 | recalled_unverified | 1.100 | 0.350 | 0.650 | 0.192 | 0.042 | 0.292 |
| `fibrocartilage` | 90.0 | recalled_unverified | 1.090 | 0.340 | 0.625 | 0.080 | 0.000 | 0.047 |
| `disc` | 90.0 | recalled_unverified | 1.090 | 0.340 | 0.625 | 0.272 | 0.282 | 0.566 |
| `nerve` | 30.0 | recalled_unverified | 1.030 | 0.280 | 0.475 | 0.203 | 0.145 | 0.394 |
| `blood_artery` | 44.9 | verified | 1.045 | 0.295 | 0.512 | 0.221 | 0.530 | 0.605 |
| `blood_vein` | 45.0 | verified | 1.045 | 0.295 | 0.512 | 0.216 | 0.452 | 0.577 |
| `fluid_free` | 6.2 | verified | 1.006 | 0.256 | 0.415 | 0.109 | 0.576 | 0.434 |
| `lymph_node` | 40.0 | recalled_unverified | 1.040 | 0.290 | 0.500 | 0.300 | 0.241 | 0.548 |
| `solid_organ` | 45.0 | recalled_unverified | 1.045 | 0.295 | 0.512 | 0.259 | 0.146 | 0.444 |
| `brain_gm` | 40.0 | verified | 1.040 | 0.290 | 0.500 | 0.259 | 0.282 | 0.543 |
| `brain_wm` | 33.0 | verified | 1.033 | 0.283 | 0.482 | 0.305 | 0.177 | 0.457 |
| `spinal_cord` | 32.0 | recalled_unverified | 1.032 | 0.282 | 0.480 | 0.286 | 0.187 | 0.464 |
| `lung` | -844.0 | verified | 0.156 | 0.000 | 0.000 | 0.051 | 0.008 | 0.076 |
| `bone_cancellous` | 190.0 | assumption | 1.190 | 0.440 | 0.875 | 0.256 | 0.111 | 0.137 |
| `marrow_yellow` | -50.0 | recalled_unverified | 0.950 | 0.200 | 0.275 | 0.593 | 0.313 | 0.031 |
| `bone_cortical` | 1300.0 | recalled_unverified | 2.300 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 |
| `tooth` | 1800.0 | recalled_unverified | 2.800 | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 |

**קריאת הטבלה — ושלוש בדיקות שפיות שעוברות:**
- **CT**: עצם קורטיקלית ‎1.000‎ (לבן) מול שומן ‎0.144‎ ואוויר-ריאה ‎0.000‎ — זה בדיוק מה שרואים ב-CT.
- **T1**: **שומן הוא הבהיר ביותר** (‎0.609‎) ומוח-עצם צהוב אחריו (‎0.593‎); נוזל כהה (‎0.109‎). זו ההתנהגות הנכונה של T1.
- **T2**: **נוזל הוא הבהיר ביותר** (‎0.576‎) ואחריו דם עורקי (‎0.530‎); שריר כהה (‎0.080‎), גיד ‎0.000‎. זו ההתנהגות הנכונה של T2.
- **PD-FS**: שומן מדוכא ל-‎0.030‎ מ-‎0.384‎ בלי הדיכוי — בדיוק מה שה-sequence אמור לעשות, והוא ה-workhorse של MSK.
- **X-ray**: ‎μ/μ_water‎ של עצם קורטיקלית (‎2.300‎) מול שומן (‎0.894‎) — יחס ‎2.57‎, ועם אורך מסלול הוא נעשה יחס אקספונציאלי. העצם תבלוט מעצמה, בלי שום pass מיוחד.

**דירוג העצמאות של הסגנונות**: הדירוג של המחלקות **שונה** בין הסגנונות (שומן תחתון ב-CT ועליון ב-T1; גיד בינוני ב-CT ואפס ב-T2), ולכן מדידת פיקסלים חייבת להראות שינוי אמיתי בכל מעבר — זו הדרישה המדידה של ה-verify.

### 3.5 עוד מוסכמה אחת שנדרשה כדי *לא* לשקר: השטחת ההצללה

ב-CT וב-MRI **האפור הוא הנתון** — הוא בא מה-HU או מאות ה-spin-echo של הרקמה. אבל שני המנועים מכפילים כל צבע בגורם הצללה דיפוזי (במנוע Z: ‎`c = uColor*(0.34+d*0.74+f)`‎), ולכן האפור שעל המסך אינו האפור שהטבלה אומרת. לכן נוסף uniform אחד, `uFlat`, שמְשטח את ההצללה לעבר 1:‏ ‎`mix(shade, 1.0, uFlat)`‎, עם ‎`uFlat = 0.6`‎ — כלומר **60 % מהאפור עובר כמו שהוא, ו-40 % נשארים להצללה ככְּלִי עומק**. מדוד: במנוע Z ה-luminance של תמונת ה-CT עלתה מ-‎53.6‎ ל-‎68.1‎ ושל ה-MRI מ-‎97.3‎ ל-‎124.4‎ עם אותם מספרי HU. ב-X-ray אין הצללה בכלל (‎`flat`‎) — ב-DRR אין משטחים, יש החלשה.

### 3.6 ההוכחה המדודה שהסגנון באמת החליף את התמונה

נמדד בדפדפן אמיתי, 1400×900, הסיבוב מוקפא, דרך ה-hook שבתוך הדף — לא בצילום מסך (ראו §3.7). «sat» היא הרוויה הממוצעת (max−min של RGB) ו-«grey» החלק של הפיקסלים שהם אפור טהור.

| עמוד | סגנון | luminance | sd | sat | grey | הרקע |
|---|---|---|---|---|---|---|
| Base M (מנוע Z, 3,252 meshes) | **Colour** | 105.8 | 32.6 | **57.3** | 0.005 | בהיר |
| | **X-ray** (Soft) | 162.0 | **57.6** | 2.1 | **1.000** | שחור |
| | **CT** (MSK) | 68.1 | 19.0 | 0.16 | **1.000** | שחור |
| | **MRI** (PD fat-sat) | 124.4 | 24.1 | 0.16 | **1.000** | שחור |
| Imaging M (מנוע own, ~950 meshes) | **Colour** | 109.9 | 48.2 | **107.9** | 0.003 | שקוף |
| | **X-ray** (Normal) | 152.6 | 56.1 | **0.0** | **1.000** | שחור |
| | **CT** (MSK) | 127.7 | 55.0 | **0.0** | **1.000** | שחור |
| | **MRI** (PD fat-sat) | 176.1 | 78.9 | **0.0** | **1.000** | שחור |

שתי קביעות שהטבלה מוכיחה: (א) **כל סגנון הוא גווני אפור** — הרוויה צונחת מ-57 / 108 לאפס, ומאה אחוז מהפיקסלים אפורים טהורים; (ב) **שלושת הסגנונות אינם אותה תמונה** — ה-luminance רחוקה זו מזו בעשרות דרגות אפור, וההיסטוגרמות שונות לגמרי. לחיצה אחת על **Colour** מחזירה בדיוק את התמונה שהיתה.

### 3.7 למה הפיקסלים נמדדים מתוך הדף ולא בצילום מסך

Q300 גילתה ש-`page.screenshot` מחזיר כאן frame מעופש (הצילום נשאר זהה בית-אחר-בית בזמן שהמצלמה זזה), ושעמודי Z מסתובבים מעצמם. לכן ה-verify: (א) **מקפיא את הסיבוב** דרך `#btn-spin` לפני כל מדידה; (ב) קורא את הפיקסלים דרך `NMSKQ301.pixels()`, שמאלץ frame בודד וקורא אותו ב-`gl.readPixels` **בתוך הדף**; (ג) **מנכה את הרקע** — מנוע אחד מנקה לשקוף והשני לאפור בהיר אטום, שהיה נמדד כ-90 % מתמונה בהירה, ולכן צבע הרקע נלקח מארבע הפינות וכל פיקסל בטווח ‎6/255‎ ממנו מושמט.

### 3.8 מה כאן מוסכמה שלנו, ולא מדידה — הרשימה המלאה

| # | הדבר | למה הוא מוסכמה | איפה זה נאמר למשתמש |
|---|---|---|---|
| 1 | **d₀**, אורך המסלול לכל חציה ב-X-ray | אין "אורך מסלול נכון" כשהגיאומטריה היא קונכיות ולא נפח; d₀ **נבחר במדידת הניגודיות** (§3.1), אבל הוא עדיין בחירה שלנו | ⓘ, וה-3 צעדים נקראים Soft/Normal/Hard ולא "mm" |
| 2 | **`uFlat = 0.6`**, השטחת ההצללה ב-CT/MRI | פשרה בין "האפור הוא הנתון" לבין כלי עומק (§3.5) | ⓘ |
| 2b | **נרמול האפורים של ה-MRI** על פני המחלקות שבעמוד | האות המוחלט ב-MRI הוא שרירותי בכל מקרה; בלי נרמול התמונה היתה כהה בלי סיבה | ⓘ |
| 3 | **חלון MSK (W1000/L250)** | הקובץ עצמו: `"owner convention for this simulation, not from a citation"` | ⓘ, ליד שם החלון |
| 4 | **מחלקות עם `status: recalled_unverified`** (עור, גיד/רצועה, סחוס, עצב, עצם קורטיקלית, ועוד) | הקובץ עצמו מצהיר שהערך לא אומת מול מקור נגיש | ⓘ מפרטת כמה מחלקות מכל status, וכרטיס המבנה אומר את ה-status של המחלקה שלו |
| 5 | **`bone_cancellous` = 190 HU** | הקובץ: `"assumption"` — «a young-adult choice inside that scale, NOT a reported mean» | כנ"ל |
| 6 | **`soft_unassigned` = 40 HU** | הקובץ: `"assumption"` | כנ"ל |
| 7 | **מודל קורטקס/מדולה אינו בשימוש כאן** | ה-`bone_model` של הקובץ מודד קורטקס מתוך החתך; רינדור משטחים אינו מבדיל קורטקס ממדולה, ולכן כל עצם מקבלת את ‎`bone_cortical`‎ | ⓘ: «העצם מצוירת כולה כקורטקס — למשטח אין פנים» |
| 8 | **1.5 T** | הקובץ: «MRI numbers are meant for 1.5 T» | ⓘ |
| 9 | **הסגנון אינו סריקה** | הקובץ: «This table drives a SIMULATION computed from segmented anatomical meshes. It is not a scan and it contains no patient data.» | ⓘ, במשפט הראשון |
| 10 | **סדר השכבות של ה-depth peel** | ראו §4 | ⓘ של פקד השכבות |

---

## 4. חשיפה לפי שכבות (depth peel) — מה עושים המוצרים, ומה הסדר שלנו

| מוצר | הדפוס | הציטוט | מה נלמד |
|---|---|---|---|
| **Zygote Body** | **סליידר עומק אחד** מהעור פנימה | «a slider to the left of the model allows users to control how far into the body they can see. Sliding the control down removes layers, beginning with the skin and continuing until all users see is a few nerves»; וה-Google Body Browser: «a single master slider can be used to strip away each one in turn, beginning at the skin and working inward towards the skeleton» | פקד **אחד** ל"כמה עמוק", **מהעור פנימה**. זה הסדר, והוא מצוטט |
| **Zygote Body** | אותו פקד נקרא גם Opacity Slider | «an Opacity Slider allows students to remove layers»; «a simple slider controls the opacity of each system, so you can fade from a surface view down to the skeleton in a smooth, single motion» | המקורות **חולקים** על השם ועל האם זו שקיפות או הסתרה. שתי התצוגות קיימות שם |
| **Zygote Body** | טוגל לשכבה בודדת **בנוסף** | «the sliding bar still removes one layer of organs, exposing underlying others but now there are toggle bars the hide single layers while showing any others»; «users can learn about layers by moving the slider or toggling layers on and off with the buttons» | **הפקד החדש אינו מחליף את פקדי המערכות — הוא נוסף להם.** בדיוק מה שהבעלים ביקש («בנוסף לפי מערכות») |
| **Primal Pictures** | **Layer up / Layer down + מספר השכבה + בחירת שכבה** | «a "Layer controls" set with "Layer up" and "Layer down" buttons, plus a layer number and a select-layer option, used to move through the layers of a model» | **לחיצות, לא סליידר** — מתיישב עם כלל ה-taps-over-sliders של הפרויקט. ו-**מספר שכבה גלוי** = אינדיקטור מצב |
| **Primal Pictures** | **חמש שכבות**, מעמוק לשטחי | «each scene is divided into five layers to provide greater control over the depth of anatomy shown»; «The Contents layer controls split each system into five layers – from deep to superficial» | מספר הצעדים שהשוק בחר הוא **5** (ואצל Zygote — רצף). אנחנו נבנה **7 צעדים**, ראו למטה |
| **Essential Anatomy 5** | **layering tool** (קודם "scalpel") | «Clever functionality found within the app allows the user to strip away layers of muscle via the 'layering' tool»; גרסה קודמת: «via the 'scalpel' tool» | **לא נמצא סליידר** ב-Essential Anatomy. קילוף שכבות שריר בכלי, לא בפקד רציף. מסומן: **לא אומת** שיש שם סליידר |
| **3D Slicer** | preset + פקד Shift יחיד | צוטט ב-Q300 | מאשר "preset + פקד אחד לכיול", שהוא המבנה של פקד השכבות שלנו |

### 4.1 סדר השכבות — מהנתונים שלנו, ומה בו מוסכמה

הבעלים ביקש: עור → שומן → פאסיה שטחית → שריר (לפי שכבה היכן שידוע) → פאסיה עמוקה → כלי דם ועצבים → עצם. **הסדר הזה נגזר מהנתונים שלנו היכן שאפשר, ובמקומות מסוימים הוא מוסכמה — וכך ייאמר.**

| צעד | מה מוסר | מאיזה נתון | מדידה או מוסכמה |
|---|---|---|---|
| 0 | שלם | — | — |
| 1 | `skin` | קטגוריית התצוגה `skin` קיימת בשני המנועים (`LK` במנוע Z) | **מהנתונים.** ההיררכיה "העור הוא המעטפת" מגובה ב-`skin_envelope: true` של מחלקת `skin` בקובץ הרקמות |
| 2 | `fat` (כולל "Fat and unlabelled soft tissue" של Q295) | קטגוריה `fat` | **מהנתונים.** ש"השומן מתחת לעור" נגזר מכך ש-Q295 בנתה אותו **מהדימות של הגוף עצמו** במרווח שבין העור למבנים |
| 3 | פאסיה **עמוקה** (`fascia`) + `bursa` | קטגוריה `fascia` | **מהנתונים.** נקראו **כל 61 שמות הפאסיה** בעמודי Z, אחד אחד: ‎`Fascia lata`‎, ‎`Brachial (deep) fascia`‎, ‎`Crural fascia`‎, שלוש שכבות ‎`Thoracolumbar fascia`‎, ‎`Plantar`‎ ו-‎`Palmar aponeurosis`‎, ‎`Linea alba`‎, ‎`Transversalis fascia`‎, ‎`Investing abdominal fascia`‎, והמחיצות הבין-שריריות — **כולם פאסיה עוטפת / עמוקה, מחיצה או אפונורוזה** |
| 4 | `muscle` + `tendon` + `insertion` | קטגוריות | **מהנתונים** |
| 5 | `ligament` + `joint` | קטגוריות | **מהנתונים** |
| 6 | `vessel` + `nerve` + `lymph` | קטגוריות | **מוסכמה שלנו, וזאת ההפשטה היחידה בפקד.** אנטומית כלי דם ועצבים חוצים שכבות — יש כלי תת-עורי ויש כלי עמוק. אין בנתונים דירוג עומק לכל כלי; לכן הם צעד אחד, **וה-ⓘ אומרת זאת במפורש** |
| 7 | `viscera` + `cns` | קטגוריות | **מהנתונים** |
| — | נשאר `bone` + `cartilage` | — | **מהנתונים**; שני המקורות של Zygote אומרים «working inward towards the skeleton» |

### 4.2 התיקון החשוב: צעד השומן **הוא** הפאסיה השטחית

בניסוח הראשון של המסמך נכתב שאין צעד "פאסיה שטחית" כי «לאטלס אין mesh של פאסיה שטחית». **בדיקה בנתונים עצמה הפריכה חצי מהקביעה הזאת, והבדיקה האוטומטית היא שתפסה אותה.** מה שנמצא בפועל בששת העמודים:

| מה נבדק | מה נמצא |
|---|---|
| כמה meshes של שומן יש בכל עמוד? | **51 בכל אחד מששת העמודים** (עמודי Z מסמנים ‎`"sys":"fat"`‎ ועמודי Imaging ‎`"cat":"fat"`‎ — הבדל שבגללו הספירה הראשונה שלנו טעתה וחשבה שעמודי Z נושאים אפס) |
| איך הנתונים קוראים לשכבה הזאת בלטינית? | **17 מהם נושאים ‎`Panniculus adiposus (tela subcutanea)`‎** — כלומר **הפאסיה השטחית במובן המודרני**, בשמה הלטיני שלה |
| האם קיימת שכבה **ממברנוזית** נפרדת (הפאסיה של Scarpa)? | **לא** — והנתונים של Q298 בעמוד עצמו אומרים זאת במילים מפורשות: «No page ships it as a mesh: the abdominal wall on these pages carries `Investing abdominal fascia` and the subcutaneous fat, not a separate membranous layer» |

**לכן הסדר שהבעלים ביקש מתקיים במלואו**: ‎`skin` → `fat / superficial fascia` → `deep fascia` → `muscle` → `ligament` → `vessels & nerves` → `organs`‎ → **עצם וסחוס**. צעד 2 נקרא על המסך **"Fat / superficial fascia"** בדיוק מהסיבה הזאת. מה שאין הוא רק **השכבה הממברנוזית**, וזה נאמר בפקד ובתוך ה-ⓘ, בציטוט מהנתונים עצמם ולא כקביעה שלנו.

**מספר הצעדים: 7 בעמודי Z ו-6 בעמודי Imaging** (אין בהם קטגוריית `skin`), ולא 5 כמו Primal, כי משפחות הרקמה שלנו ‎(`LK`, 14 קטגוריות)‎ מתקפלות לשבע חזיתות ולא לחמש; צעד שאין לו מה לקלף בעמוד נתון **אינו מוצע בכלל**. הפקד הוא **לחיצות** (Primal: Layer up / Layer down) עם **מספר שכבה ושם שכבה גלויים** (Primal) — ולא סליידר, לפי כלל הפרויקט ולפי Q300 §1.

---

## 5. מטריצת ההתאמה (סעיף 4 של הבעלים) — **נבדקה בדפדפן אמיתי, לא שוערה**

הכלל: **שתי פעולות תואמות אם כל אחת כותבת לנתון אחר ושתיהן נראות יחד; הן אינן תואמות אם הן כותבות לאותו נתון, או אם אחת מרוקנת את הקלט של השנייה.** המטריצה נאכפת במקום אחד (`viewer/q301/combos.js`) **ונבדקה בדפדפן אמיתי בשני המנועים**: ‏`cut` ו-`imaging` אושרו פעילים יחד (`['cut','imaging']`) עם השורה «+ Active together with Cut.» על המסך, ו-`sel-p-hlsel` אושר `disabled` + `aria-disabled="true"` עם הנימוק המלא מוצג מתחתיו. 14 זוגות בטבלה, מהם 6 תואמים, 7 לא תואמים ואחד «תואם, אחד מוביל».

| א | ב | הפסק | הנימוק שיוצג (שורה אחת) |
|---|---|---|---|
| **Cut** | **Imaging style** (X-ray/CT/MRI) | **תואם** — בקשת הבעלים המפורשת | — (מוצג כ-co-active) |
| **Cross-section fill** | **Imaging style** | **תואם** | פני החתך מתמלאים באפור של הסגנון, לא בצבע הרקמה |
| **Cut** | **Measure** | **תואם** | — |
| **Cut** | **Depth peel** | **תואם** | — |
| **Imaging style** | **Depth peel** | **תואם** | הקילוף מוריד שכבות, הסגנון קובע את האפור של מה שנשאר |
| **Imaging style** | **Fat on/off** | **תואם** | — |
| **Imaging style** | **Colour by source** | **לא תואם** | «הסגנון הרדיוגרפי מחליף את הצבע; צביעה לפי מקור אין לה מה לצבוע» |
| **Imaging style** | **Highlight marked / Tint** | **לא תואם** | «צבע הדגשה לא קיים בתצוגת גווני-אפור; השתמשו ב-Fade others» |
| **Imaging style** | **Bone strength (Q300)** | **תואם, אחד מוביל** | «סגנון רדיוגרפי קובע את בהירות העצם מההחלשה שלה עצמה, ולכן ה-pass הנוסף של Q300 מושהה כל זמן שסגנון דלוק — והוא חוזר עם הצבע». **זה הֶשֶׁג של הרגע האחרון, והוא חשוב:** Q300 שולחת את ה-pass שלה **דלוק** (`level:1`, Clear) בשני עמודי Imaging. אם הזוג היה מסומן "לא תואם", ה-probe היה פעיל כבר בטעינה, ו**כפתורי ה-X-ray / CT / MRI היו מושבתים לפני שהמשתמש נגע במשהו**. לכן נוסף סוג שורה שלישי, `ok:"over"`: שניהם מותרים, הסגנון מוביל, אף פקד לא מושבת, והפקד שנסוג מסומן בחץ למטה ובמילים של השורה עצמה |
| **X-ray style** | **CT style** / **MRI style** | **לא תואם** (one-of) | «אפשר סגנון דימות אחד בכל פעם» |
| **Depth peel** | **Layer preset** (x-ray/skeleton/nervous/...) | **לא תואם** | «שניהם כותבים את אותה טבלת שכבות; הפעלת אחד מכבה את השני» |
| **Depth peel** | **Solo layer** | **לא תואם** | כנ"ל |
| **Spin** (מנוע Z) | **Measure** / **Place cut on model** | **לא תואם** | «עצרו את הסיבוב כדי לסמן נקודה על המודל» |
| **Model only / Split / Compare** | ביניהם | **one-of** | מחזור פריסה |
| **Symmetric view** | **Cut** | **תואם** — נבדק, אין התנגשות | — (לא נרשם בטבלה: זוג שלא רשום הוא תואם ושקט) |
| **Isolate 3D box** | **Cut** | **תואם** — נבדק, אין התנגשות | — (כנ"ל) |
| **Mark by tapping** | **Place cut on model** | **לא תואם** | «שתי הפעולות תופסות את הנגיעה על המודל» |

**איך זה נראה על המסך.** בתוך גיליון הקבוצה: פריט **פעיל** מקבל נקודה; פריט **פעיל יחד עם פעיל אחר** מקבל `+` ואת שם השני ב-`title`; פריט **לא תואם** מקבל `disabled` + `aria-disabled` + שורת הנימוק **גלויה מתחתיו**, לא רק ב-tooltip (הבעלים לא רואה tooltip בנייד).

---

## 6. פריסת הפקד — מה שנבנה בפועל

### 6.1 דסקטופ 1400×900

```
┌──────────────────────────────────────── 3-D view ─────────────────────────────────────────┐
│ [hub]                                                                        ⓘ           │
│                                                                                           │
│                                     (המודל)                                               │
│                                                                                           │
│  ┌ sa-bar (Q300, רק כשמשהו מוסתר) ─────────────┐                                         │
│  │ isolated: Femur ✕   cut ✕   [Show everything]│                                         │
│  └───────────────────────────────────────────────┘                                        │
│  ╔══════════════ #q301-sheet — רק הקבוצה שנפתחה, ומעל הסרגל ═════════════════════════╗   │
│  ║ Imaging                                                                        ✕  ║   │
│  ║  ● X-ray  ○ CT  ○ MRI   │  Colour  │  Strength: Soft [Normal] Hard   │  ⓘ        ║   │
│  ║  Ultrasound (mode)   Reference image                                               ║   │
│  ║  ⊘ Colour by source — הסגנון הרדיוגרפי מחליף את הצבע                              ║   │
│  ╚════════════════════════════════════════════════════════════════════════════════════╝   │
│  ╔═══════════════════ #q301-bar — הפקד. שתי שורות, תמיד כאן ═════════════════════════╗   │
│  ║ View · Layers · Imaging● · Cut● · Mark · Learn · Measure                 ║   │
│  ║ ↶ Undo   ↷ Redo   ⟲ Module   ⟳ Model                  ⓘ                      ║   │
│  ╚════════════════════════════════════════════════════════════════════════════════════╝   │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

- **שורה תחתונה = ה-"CONTROL" שהבעלים לא מצא.** Undo ו-Redo **עם טקסט**, בסרגל משל עצמם, בשליש התחתון — הדפוס של BioDigital («Undo and Redo moved to their own toolbar») ושל Visible Body (History בסרגל התחתון). שני ה-reset לידם, שונים בשם ובאייקון. **אף אחד מהארבעה אינו מתקפל לתוך קבוצה** (ההנחיה על פעולות הרסניות).
- **שורה עליונה = שמונה קבוצות**, אקורדיון: אחת פתוחה בכל רגע. נקודה על הקבוצה = משהו במשפחה הזאת פעיל עכשיו.
- הגיליון **מאמץ את כפתורי המקור עצמם** (`appendChild` של ה-DOM הקיים) — אותם ids, אותם מאזינים, אפס לוגיקה כפולה.
- `#hist-bar` הצף של Q294 נסגר כשהסרגל קיים (אותם פקדים, מקום אחד).
- ⓘ אחת בפינה הימנית-עליונה (קטנה, בעיגול) ואחת בסרגל — שתיהן פותחות את אותו גיליון מידע.

### 6.2 טלפון 390×844

```
┌──── 390 px ────┐
│ [hub]       ⓘ  │  ← 16 px gutter משני הצדדים
│                │
│    (המודל)     │
│                │
│ isolated: ✕    │  ← sa-bar של Q300, רק כשצריך
│┌──────────────┐│
││ Imaging   ✕  ││  ← הגיליון, גובה ≤ 45 % מהמסך, נגלל בתוכו
││ X-ray CT MRI ││
││ Colour       ││
││ Soft Norm Hrd││
│└──────────────┘│
│┌──────────────┐│
││View Layers   ││  ← 7 קבוצות, גולשות ל-2–3 שורות (36–44 px גובה כל אחת)
││Imaging● Cut● ││
││Mark Learn    ││
││Measure       ││
│├──────────────┤│
││ ↶  ↷  ⟲  ⟳  ⓘ││  ← 5 × 60 px = 300 ≤ 358. אייקון + טקסט זעיר מתחת
│└──────────────┘│
└────────────────┘
```

- **רוחב שמיש: 390 − 2×16 = 358 px.** שורת ההיסטוריה: 4 פקדים × 52 px + ⓘ 44 px + רווחים ≈ 260 px — נכנסת בשורה אחת. שורות הקבוצות: `flex-wrap` מחליט לפי אורך השם, בפועל 2–3 פריטים לשורה. **נמדד בדפדפן ולא נאמד**: בדסקטופ הסרגל יוצא 760 px ויושב ב-top 799 מתוך 900 (השליש התחתון), ובטלפון הוא נכנס בתוך 358 px בלי גלילה אופקית של הדף — שתי הקביעות הן בדיקות ב-verify.
- **כל יעד נגיעה ≥ 44 px** (כלל ה-thumb zone של Q300).
- הסרגל יושב **בשליש התחתון** — האזור הנגיש לאגודל; ה-hub וה-ⓘ למעלה, כי הם לא פקדים שחוזרים עליהם.
- **"Show everything" של Q300 לא זז**: הוא נשאר ב-sa-bar מעל הסרגל, כי הוא מופיע רק כשצריך ואסור שיידחק לשורה קבועה.
- הגיליון **אינו** חוסם את המודל לגמרי: תקרה של 45 % מגובה המסך, וגלילה בתוכו.

### 6.3 מה נכנס לכל קבוצה

| קבוצה | חברים (כפתורים קיימים שמאומצים + חדשים) |
|---|---|
| **View** | front / side / back, move (pan), spin, Reset view, Model only / Split / Compare, Phone layout, Symmetric view |
| **Layers** | **Depth peel (חדש)**, **Fat on/off (חדש)**, הכפתור שפותח את טבלת השכבות והשקיפות (`btn-panel`) — **הטבלה עצמה לא נכנסת לגיליון**, לפי כלל התפריטים הקצרים; ה-presets (all / skeleton / nervous / vessels / organs / insertions); side (both/right/left); **Colour by source** |
| **Imaging** | **X-ray / CT / MRI style (חדש)**, Colour (חזרה), Strength, Bone strength (Q300), x-ray preset הישן, Ultrasound mode, Reference image |
| **Cut** | Cut, exit cut, הציר, Place on model, reset cut, flip side, Cross-section, Fill cut face, part slices |
| **Mark** | search, Mark by tapping, multi-select, expand (adjacent / related / group), Isolate, Isolate 3D, Only marked / Fade others / Hide marked, Clear marks |
| **Learn** | Learn, Labels, Quick view, Abbreviation list, nerve groups |
| **Measure** | Measure (Q294), scale bar |
| (needle / ultrasound) | אין להם קבוצה משלהם: הכניסה למצבי העבודה הקליניים היא כפתור אחד, `t-mode`, והוא יושב ב-**Imaging**. **קבוצה שאף אחד מחבריה אינו בעמוד אינה נוצרת בכלל**, ולכן אין בשום עמוד קבוצה ריקה |

---

## 7. סעיף 6 — השומן כברירת מחדל

| מה יש היום | איפה בקוד | מה משתנה |
|---|---|---|
| מנוע Z: כל השכבות דלוקות, השומן ב-α 0.12 | `on[k] = true` לכל `LK`; `alphaFor.fat = 0.12` ("Q295: faint in 3-D, solid in the cut face") | `on.fat = false` בטעינה. ה-α נשמר ל-**כשמדליקים** |
| מנוע own: השומן דלוק ב-α 0.12 | `on[c] = (c === "bone" || c === "muscle" || c === "fat")`; `sysAlpha[c] = c === "fat" ? 0.12 : 1` | להסיר את `fat` מהתנאי. `sysAlpha` נשמר |
| פני החתך ממלאים שומן רק אם α > 0.02 | `cut_cap.js`: `capA(it) = it.cat === "fat" && it.alpha > 0.02 ? Math.max(it.alpha, 0.9) : it.alpha`, ושער `capA(it) >= 0.2` | **השומן ממלא את פני החתך תמיד**, גם כשהוא כבוי ב-3-D. זו דרישת Q295 ("אין חורים"), והיא נאמרת ב-ⓘ: «השומן כבוי בתצוגה התלת-ממדית וממלא את פני החתך, כדי שחתך לא ייראה חלול» |
| המנועים מדלגים על מבנה לא-נראה לפני ה-cap | `items:` → `if (!vis(o)) return;` (Z), המקביל ב-own | חריג אחד: שכבת שומן שכבויה **כשכבה** (ולא הוסתרה פרטנית) כן נמסרת ל-cap עם α של ה-cap |

**51 ה-meshes של Q295 לא נוגעים**: לא נוסף ולא מוסר מבנה, רק ברירת המחדל של הנראות. ההדלקה היא **לחיצה אחת** בקבוצת Layers, היא **צעד undo אחד**, והיא נרשמת כמסלול ב-`NMSKShowAll` של Q300 כך שה-"Show everything" מחזיר אותה.

---

## 8. מקורות

ציטוטים נקראו דרך `WebSearch` בלבד; `WebFetch` נחסם ב-DNS גם הפעם (נוסה `learn.microsoft.com` → `ENOTFOUND`).

- **BioDigital** — `support.biodigital.com/hc/en-us/articles/360059954133` (November 2020: Streamlined navigation in the Human Viewer), `...360038311874` (November 2019).
- **Visible Body** — `help.cengage.com/visible-body/...` (getting started, settings, cross-sections), `comsupport.fau.edu/kb/articles/visible-body-getting-started`, `visiblebody.com/blog/6-tips-to-help-you-become-a-human-anatomy-atlas-super-user`, מדריכי ספרייה (LSU, LJMU, Goodwin).
- **Primal Pictures** — `devlibrary.nyp.edu.sg/.../UserGuide-HTML5-HAP-ATV.pdf` (Layer controls: layer up / layer down / layer number / select layer), דפי App Store של Primal's 3D (five layers, deep to superficial).
- **Zygote Body** — `educationworld.com/a_tech/site-review/zygote-body.shtml`, `commonsense.org/education/reviews/zygote-body`, `experiments.withgoogle.com/body-browser`, `cgchannel.com/2010/12/google-body-browser-gives-instant-anatomical-reference`, `research.dom.edu/PAS/anatomyandphysiology`.
- **Essential Anatomy 5 / 3D4Medical** — `3d4medical.com/support/essential-anatomy-5/turning-systems-onoff`, `imedicalapps.com` (2011, 2013).
- **Anatomage** — `guides.lib.uiowa.edu/anatomage/getting-started` ו-`/features`, `anatomage.com/faq/`, רישום 510(k) כפי שצוטט בתוצאות.
- **3D Slicer / Cornerstone** — `salcedoe.github.io/MtMdocs/slicer/CTMRExplore` (CT-AAA, MR-default), `discourse.slicer.org/t/how-to-set-volume-rendering-preset-using-python/3063`, `cornerstonejs.org/live-examples/volumeviewport3d` (רשימת presets — **פרויקט אחר**, לא Slicer).
- **DRR / Beer–Lambert** — `watkins.cs.queensu.ca/~jstewart/472/notes/28/28-drrs.html`, `arxiv.org/pdf/2208.12737`, `emergentmind.com/topics/digitally-reconstructed-radiographs-drrs`, `patents.google.com/patent/US7653226`.
- **חלונות CT** — `radiopaedia.org/articles/windowing-ct`, `kevalnagda.github.io/ct-windowing`, `radnotes.substack.com/p/ct-windows-and-levels`.
- **אות spin-echo** — `cis.rit.edu/htbooks/mri/chap-10/chap-10.htm`, `pages.ucsd.edu/~msereno/569/homework1.pdf`, `courses.lsa.umich.edu/fmri-training-course/.../3_MRI_Physics_DataAcq_Contrast.pdf`, `magnetic-resonance.org/ch/10-02.html` (וריאנט שלא אומץ).
- **נתוני הרקמות שלנו** — `clinical/data/imaging_tissues.json` (Q226 / Q229, נשלח בכל עמוד כ-`clinical_imaging_tissues.json`), `clinical/data/ultrasound_tissues.json`.
- **ללא מקור אמין (לא אומת):** סגנון רינדור x-ray ב-Visible Body או ב-Complete Anatomy; סליידר שכבות ב-Essential Anatomy; הרשימה המלאה של presets ב-3D Slicer עצמו; הנחיות NN/g על מקום ה-Undo/Redo (אף דף של nngroup.com לא חזר); `learn.microsoft.com` על progressive disclosure.
