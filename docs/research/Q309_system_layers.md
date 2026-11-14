# Q309 — מערכות (systems) ושכבות עומק בתוך מערכת (per-system depth strata)

בקשת הבעלים: «תן גם תצוגה לפי מערכות עם כפתור הדלקה/כיבוי, וגם לפי שכבות — לכל הגוף, לפי מערכת, ורק למערכות המוצגות.»

המסמך הזה מתעד **רק את ההחלטה האנטומית**: מהי "מערכת" בעמודים שלנו, מהי "שכבה" בתוך מערכת אחת, מאיפה הסדר
מגיע, ומה בו **המצאה שלנו ולא אנטומיה**. התיאור של הבקרה עצמה נמצא ב-`docs/VIEWER_README.md`, והטבלה המחייבת —
זו שהצפיין קורא — היא `data/anatomy/system_layers_q309.json`. **אין מספר אחד במסמך הזה שלא נמדד על העמודים
עצמם**; הצפיין פותר את הטבלה מול המבנים של כל עמוד בזמן טעינה, ושכבה שאין לה אף מבנה בעמוד מסוים פשוט לא
מוצעת שם.

## 1. מה זו "מערכת" כאן

המנועים שלנו לא מכירים "מערכות" — הם מכירים **קטגוריות רקמה** (`layer` במנוע Z, `cat` במנוע שלנו). מערכת היא
לכן **קבוצה של קטגוריות של העמוד עצמו**, ולא רשימה שהמצאנו:

| מערכת | key | קטגוריות | עמודי Z (Base / Combined) | עמודי Imaging |
|---|---|---|---|---|
| שלד ומפרקים — skeletal | `skeletal` | bone, cartilage, joint, ligament | 646 | 202 |
| שרירים — muscular | `muscular` | muscle, tendon, insertion | 434 | 374 |
| פאסציות וכיסים — fascial | `fascial` | fascia, bursa | 175 | 6 |
| עצבים ומערכת העצבים המרכזית — nervous | `nervous` | nerve, cns | 759 | 337 |
| כלי דם — vascular | `vascular` | vessel | 661 | 48 |
| מערכת הלימפה — lymphatic | `lymphatic` | lymph | 162 | — |
| איברים — visceral | `visceral` | viscera, organ | 124 | 30 |
| עור — integument | `integument` | skin | 250 | — |
| שומן — adipose | `adipose` | fat | 51 | 51 |

(המספרים הם של `base_m` ו-`own_m`; לכל עמוד המספרים שלו, והכפתור מדפיס את המספר של העמוד שעליו הוא יושב.)

כך יוצא ש**עמודי Z מקבלים 9 מערכות ועמודי Imaging 7** — העור והלימפה אינם קיימים שם כרשת כלל, ולכן הכפתור
שלהם לא נבנה. שתי הערות הכרחיות:

* **רצועות ומפרקים נכללים ב-skeletal** ולא במערכת נפרדת, כפי ששלד בספרות הוא עצם + סחוס + מפרקים + הרצועות
  שלהם. זה גם מה שמחזיר בדיוק את רשימת המערכות שהבעלים מנה.
* **`fat` היא מערכת בפני עצמה** ולא חלק מה-fascial, למרות ש-17 מ-51 רשתות השומן נושאות את השם
  `Panniculus adiposus (tela subcutanea)` — כלומר ה-superficial fascia במובן המודרני (מצאנו את זה ב-Q301).
  הסיבה מעשית: הבעלים ביקש ב-Q301 ששומן יוצג רק כשמבקשים, והכפתור של `fat` חייב להישאר נפרד מזה.

## 2. מה זו "שכבה" בתוך מערכת אחת

הסדר הגלובלי של Q301 (`skin → fat → deep fascia → muscle → ligament → vessels/nerves → organs`) הוא **חוצה
מערכות** — הוא לא עונה על "קלף את השרירים שכבה-שכבה". בתוך מערכת אחת הגדרנו שכבות כך, מהחוץ פנימה, וכל שכבה
נושאת את ה-**basis** שלה: `literature` (ספר לימוד קובע), `data` (הנתונים שלנו או שמות המבנים עצמם קובעים),
`mixed` (ספרות + קבוצות העומק של הפרויקט עצמו), או `none` — **השארית, שאין לה עומק ממוקר, והמסך אומר זאת
במילים**.

### 2.1 skeletal — 3 שכבות
`Joint capsules & ligaments` (337) → `Cartilage` (53) → `Bone` (256).
ה-basis: קופסית המפרק והרצועות חיצוניות לחלל המפרק, והסחוס הארטיקולרי מכסה את קצות העצם (Standring 42nd ed.;
Gray's for Students 4th ed.). **המצאה שלנו:** עבור הסחוסים שאינם ארטיקולריים בעמודים האלה — costal, laryngeal,
tracheal — "סחוס לפני עצם" הוא קונבנציה שלנו; הם שוכנים ליד עצם ולא עליה.

### 2.2 muscular — 4 שכבות
`Superficial layer of its region` (160) → `Intermediate layer` (98) → `Deep layer` (176) → `No sourced stratum` (0).
כאן נמצא העיקר, ויש בו שני דברים שחייבים להיאמר בפירוש:

1. **"שטחי / בינוני / עמוק" הם של האזור של השריר, לא של הגוף כולו.** כך גם שני המוצרים היחידים שמצאנו שמשלבים
   בקרת שכבות בתוך מערכת מתארים את שלהם (ראה §4). לכן ה-trapezius וה-superficial perineal pouch נמצאים באותה
   שכבה ראשונה — שניהם השכבה השטחית *של האזור שלהם*.
2. **איפה הנתונים שלנו קובעים, הם קובעים.** `data/anatomy/muscle_groups_q283.json` נושא את הזוג
   `gluteal` ("Gluteal group (superficial)") מול `deep_gluteal` ("Deep gluteal group (short lateral rotators)"),
   ו-`data/anatomy/muscle_groups_q306.json` נושא `leg_posterior_superficial` מול `leg_posterior_deep`
   ו-`erector_spinae` מול `transversospinalis` / `multifidus_group`. שלושת הזוגות האלה הם הציר של השכבות, ויש
   טסט שמוודא שכל חבר בכל אחת מהקבוצות האלה אכן נופל בצד שהקבוצה אומרת.

איפה הנתונים שלנו שותקים — האמה, הצוואר, דופן הבטן, כף היד וכף הרגל — הספרות קובעת, ואנחנו מצטטים אותה:

| אזור | שטחי | בינוני | עמוק | מקור |
|---|---|---|---|---|
| anterior forearm | pronator teres, flexor carpi radialis, palmaris longus, flexor carpi ulnaris | flexor digitorum superficialis | flexor digitorum profundus, flexor pollicis longus, pronator quadratus | Gray's for Students 4th ed. |
| posterior forearm | brachioradialis, ECRL, ECRB, extensor digitorum, extensor digiti minimi, ECU, anconeus | — | supinator, abductor pollicis longus, EPL, EPB, extensor indicis | Gray's for Students 4th ed. |
| back | trapezius, latissimus dorsi, levator scapulae, rhomboids, serratus posterior | erector spinae (iliocostalis, longissimus, spinalis) | transversospinalis (semispinalis, multifidus, rotatores), interspinales, intertransversarii | Gray's / Standring + הקבוצות של הפרויקט |
| neck | platysma, sternocleidomastoid, infrahyoid, suprahyoid | — | scalenes, longus capitis, longus colli, rectus capitis | Gray's for Students 4th ed. |
| posterior leg | gastrocnemius, soleus, plantaris | — | popliteus, tibialis posterior, FDL, FHL | הקבוצות של הפרויקט (`leg_posterior_*`) |
| gluteal | gluteus maximus / medius / minimus, TFL | — | piriformis, gemelli, obturator internus/externus, quadratus femoris | הקבוצות של הפרויקט (`gluteal` / `deep_gluteal`) |
| abdominal wall | external oblique, rectus abdominis | internal oblique | transversus abdominis | Gray's for Students 4th ed. |
| perineum | superficial transverse perineal, bulbospongiosus, ischiocavernosus, sphincter ani externus | — | deep transverse perineal, urethral sphincter, compressor urethrae, urethrovaginal sphincter, levator ani, coccygeus | Gray's for Students 4th ed. (superficial / deep perineal pouch) |

**הכיסוי נמדד על ששת העמודים:** **100%** ב-`base_m` וב-`comb_m` (434 מתוך 434), ו-**99.7% ומעלה** בארבעת האחרים — מבנה **אחד** בכל אחד מהם נשאר ללא שכבה ממוקרת. השארית — אם יש —
מופיעה כשכבה רביעית שכתוב עליה **"No sourced stratum"** עם המספר שלה, כדי שקילוף מלא של המערכת באמת יוריד את
כל השרירים ולא ישאיר "חור" בלי הסבר.

### 2.3 fascial — 5 שכבות
`Subcutaneous bursae` (16) → `Investing deep fascia & aponeuroses` (40) → `Intermuscular septa` (13) →
`Subfascial / subtendinous / submuscular bursae & tendon sheaths` (68) → `No sourced stratum` (38).
ה-basis: ה-Terminologia Anatomica מסווגת כיסים ל-subcutaneous / subfascial / subtendinous / submuscular, וזהו
הסיווג שהשמות בעמודים נושאים ממש (`Subcutaneous prepatellar bursa`, `Subfacial prepatellar bursa`,
`Subtendinous bursa of sartorius muscle`); ה-deep fascia יוצרת מעטפת עוטפת שממנה נכנסות פנימה המחיצות
הבין-שריריות אל העצם (Gray's / Standring), ולכן מעטפת לפני מחיצה. **המצאה שלנו:** מיקום הכיסים
התת-עוריים *לפני* הפאסציה העוטפת נגזר מהמחלקה שלהם ב-TA ולא ממדידה. השארית (38) היא פאסציה ויסצרלית ופריאטלית
(`Clavipectoral`, `Diaphragmatic`, `Iliopsoas`, `Piriformis`, `Transversalis`) ו-15 כיסים ששמם לא נושא אף מילת
עומק — והיא מסומנת כך.

**בעמודי Imaging אין קילוף פאסציה בכלל**, ובכוונה: 5 מתוך 6 מבני ה-fascia שם הם retinacula, interosseous
membrane ו-`Integumentum commune` — הסיווג לא מגיע אליהם, הכיסוי יורד מתחת לחצי, והכלל (§3) שולל את הקילוף.

### 2.4 nervous — 3 שכבות
`Cutaneous nerves` (40) → `Nerves deep to the deep fascia` (516) → `Central nervous system` (203).
ה-basis: עצבים עוריים חודרים את הפאסציה העמוקה ורצים ב-superficial fascia, בשונה מהעצבים העמוקים
(Gray's / Standring); מערכת העצבים המרכזית שוכנת בתוך הגולגולת והתעלה החוליתית ולכן היא העמוקה. **מה לא
הצענו:** סדר בין plexus, שורש וגזע — אין לנו דירוג עומק לכל מבנה בנפרד, ולכן אין שכבה כזו. בעמודי Imaging
אין קטגוריית `cns`, ולכן שם הקילוף הוא בן 2 שלבים.

### 2.5 vascular — 2 שכבות
`Superficial vessels` (41) → `Deep vessels` (620).
ה-basis: השמות עצמם — `Great / Small saphenous vein`, `Cephalic vein`, `Basilic vein`, `Median cubital vein`,
`Median antebrachial vein`, `Dorsal venous arch of foot`, `Dorsal venous network of hand`,
`External / Anterior jugular vein`, וכל מבנה ששמו פותח ב-`Superficial`. **מה כאן הסקה ולא נתון:** שלב 2 הוא
"כל השאר", כלומר אנחנו *מסיקים* עומק מהיעדר מילה בשם. Gray's תומך בכך לוורידים (שטחיים או עמוקים, והעמוקים
מלווים את העורקים), אבל זו עדיין הסקה ולא רשומה פר-מבנה — וזה כתוב ב-`conventions` של הטבלה.

### 2.6 adipose — 4 שכבות
`Subcutaneous fat / superficial fascia` (17) → `Intermuscular fat` (8) → `Deep & visceral fat` (8) →
`No sourced stratum` (18).
ה-basis: שמות המבנים עצמם (`Subcutaneous fat, thigh`, `Intermuscular fat of the forearm`,
`Deep pelvic fat (ischioanal fossa, pelvic visceral, gluteal)`), והזיהוי של השכבה הראשונה כ-superficial fascia
הוא המצאי של Q301 (ה-`Panniculus adiposus (tela subcutanea)`). השארית (18) היא `Unlabelled soft tissue, *` —
המילוי שה-Q295 הוסיף כדי שחתך לא ייראה חלול; אין לו עומק ממוקר ולכן הוא השלב המסומן כך.

### 2.7 lymphatic, visceral, integument — **אין קילוף, רק on/off**
זו התשובה הכנה ולא כישלון:
* **lymphatic**: רק 21 מ-162 המבנים נושאים `superficial` או `deep` בשם (13 ו-8). פחות ממחצית — ולכן אין קילוף.
* **visceral**: לאיברים אין מילת עומק בשם כלל, וסדר לפי חלל גוף הוא לא עומק.
* **integument**: 250 רשתות `(skin)` הן מעטפות של אזורי גוף; epidermis / dermis אינם מקוטעים כרשת נפרדת.
הבקרה מדפיסה על המסך, לכל אחת מהן: «this system has no depth ordering we can source, so it offers on / off only».

## 3. הכלל שמחליט אם מערכת מקבלת קילוף

**מערכת מקבלת קילוף רק אם לפחות מחצית מהמבנים שלה *באותו עמוד* נופלים בשכבה שה-basis שלה אינו `none`.** הכלל
נמדד פר עמוד בזמן טעינה, לא נרשם מראש. זו הסיבה שעמודי Imaging לא מקבלים קילוף פאסציה ועמודי Z כן
(137 מ-175), וזו הסיבה שאם Q308 או סבב אחר יוסיף מבנים — למשל Scarpa's layer לדופן הבטן — התשובה תשתנה
מעצמה, בלי לגעת בקוד.

## 4. מה השוק עושה (ציטוטים; הרחבה ל-`Q301_controls_and_render_styles.md` §9)

`WebFetch` חסום ב-DNS לכל מחשבי המוצרים — נבדק שוב בסבב הזה: `3d4medical.com` ו-`www.visiblebody.com` שניהם
`ENOTFOUND` — ולכן **כל טענה כאן נשענת על ציטוט מ-WebSearch**, ומה שאין לו ציטוט מסומן «לא אומת».

* **Complete Anatomy (3D4Medical / Elsevier)** עושה בדיוק את שלוש הבקשות: «Press and hold a system's icon to
  switch it fully on or off»; «Tapping an icon reveals plus and minus buttons for adding or removing layers
  **within that system**»; «Plus adds deeper layers first, and minus strips the superficial layers first»;
  «all 12 systems can be toggled incrementally from the menu»; ולחזרה: «select the system icon and choose
  'Show Hidden' to make all of its structures fully visible again». אימצנו: הכפתור פר מערכת, והשכבות **בתוך**
  מערכת. לא אימצנו את ה-press-and-hold — חוק הפרויקט הוא הקשה, לא לחיצה ארוכה.
* **Visible Body (VB Suite 2.5 / Atlas 2026)**: «The muscular system is split into four layers that can be added
  or removed»; «Pressing and holding a system icon for about two seconds isolates that system, and the Undo arrow
  restores the previous view»; ובהערות הגרסה: ה-Systems Tray «now has plus and minus icons to add or remove
  layers **across all body systems**» — זה בדיוק ה-scope השלישי של הבעלים. וגם האישור שההחזרה חייבת להיות
  טריוויאלית: «toggling the skeletal system off and back on restores the full skeleton».
* **Primal Pictures**: «The Contents layer controls split **each system** into five layers – from deep to
  superficial»; והבקרות «enable users to quickly build up different systems to their desired depth of view»;
  ובמדריך של ה-3D Atlas: «Up layer» / «Down layer» ואפשרות choose-layer. אימצנו את ההקשות ואת מספר השכבה על
  המסך (כבר מ-Q301).
* **BioDigital**: «the viewer can control the visibility of not just the many top level systems but also
  individual muscles, organs, and nerves» (בלוג ספרייה, לא תיעוד רשמי — **לא אומת** מול דף של BioDigital עצמה);
  ומ-Q300: «The Reset button is hidden by default but appears when one of the Explore Tools ... has been used».

**מה שלא מצאנו באף מוצר:** scope מפורש של "רק המערכות המוצגות" **כבחירה של המשתמש** לצד "מערכת אחת" ולצד "כל
הגוף" — Visible Body מקלפת across all body systems כברירת מחדל יחידה, ו-Complete Anatomy מקלפת פר מערכת בלבד.
שלושת ה-scopes כבחירה אחת הם **שלנו**, והם מה שהבעלים ביקש.

## 5. מה לא עשינו, ולמה

1. **אין דירוג עומק פר-כלי-דם ופר-עצב בודד** מעבר למה ששמו אומר. זה אותו פער ש-Q301 כבר רשם ("the data holds
   no depth rank for a single vessel"), ולסגור אותו משמעו לכתוב רשומת עומק ל-661 כלי דם ול-556 עצבים — סבב
   בפני עצמו. פתוח לבעלים.
2. **lymphatic לא מקבל קילוף** למרות ש-21 מבנים כן נושאים את המילה. אפשר להשלים את ה-141 הנותרים מספרות
   (כל קבוצת קשריות לימפה מסווגת superficial/deep בספרות), וזה סבב של כתיבת נתונים. פתוח לבעלים.
3. **אין שכבה ממברנוזית (Scarpa's)** בשומן — Q301 כבר רשם זאת, ואם סבב אחר יוסיף אותה הטבלה תיתן לה שלב
   משלה אוטומטית ברגע שתהיה לה רשת בעמוד.
4. **הסחוסים הלא-ארטיקולריים** מקוטלגים בשכבת הסחוס של skeletal למרות שאינם מכסים עצם; לפצל אותם דורש רשומה
   פר-סחוס. מסומן כקונבנציה שלנו, לא תוקן בשקט.
