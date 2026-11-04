# Q300 — בנצ'מרק ממשק: איך האטלסים והאפליקציות המובילות פותרים את מה שאצלנו שבור

**מה נשאל (הבעלים, מילה במילה):** «i selected an organ, isolate its environment, and then had difficulty to redo it to see everything. it must be much easier. also, a button for reset the specific model.» · «in xray and in fade view - the skeleton should appear better than now that it can not be seen almost at all.» · «review other 3d atlases AND APPS AND LEARN THEIR INTERFACE, THEN IMPROVE OUR interface for the best.»

**מצב הרשת בסבב הזה — חשוב לקריאת המסמך.** `WebFetch` נחסם ב-DNS לכל אחד מאתרי המוצר שניסינו: `support.biodigital.com`, `help.cengage.com` (Visible Body), `cdn.completeanatomy.cn`, `www.mc3.edu` (מדריכי Anatomage). כלומר **לא נקרא אף דף מוצר ישירות**. מה שכן עבד הוא `WebSearch`, שמחזיר ציטוטים מתוך אותם דפים; כל קביעה בטבלאות שלהלן נשענת על ציטוט כזה, והיכן שלא נמצא ציטוט כתוב במפורש **"לא אומת"** ולא הושלם בניחוש. שני מוצרים נשארו בלי שום מידע אמין: **Horos / OsiriX** (כל התוצאות היו על מוצרים אחרים — Dragonfly, Carestream) ו-**הצופה של Radiopaedia** (אפס תוצאות רלוונטיות). אם הבעלים יפתח גישה ל-`support.biodigital.com`, ל-`help.cengage.com` ול-`3d4medical.com`, אפשר להעמיק — אבל המסקנות המרכזיות למטה אינן תלויות בזה, כי הן נשענות על ציטוטים מצולבים משני מקורות ומעלה.

**מה הסבב הזה גילה לפני כל השוואה — האבחנה הטכנית.** שתי התלונות הראשונות אינן "העדפת עיצוב": שתיהן באגים מדידים, וזוהו בקוד שלנו לפני שנכתבה שורה בטבלאות. ראו פרק 3.

---

## 1. הטבלה המרכזית — דפוס אחרי דפוס

| מוצר | דפוס | איך זה עובד שם (ציטוט/מקור) | מה כדאי לאמץ אצלנו | מאמץ | מתאים לאילוצים (עמודים סטטיים, שני מנועים, ללא backend)? |
|---|---|---|---|---|---|
| **BioDigital Human** | **כפתור Reset שמופיע רק כשצריך** | «The Reset button is hidden by default but appears when one of the Explore Tools (i.e., Hide, Isolate, or Fade) has been used» | **זה הדפוס החזק ביותר במסמך.** כל מסלול שמסתיר משהו מדליק פקד "החזר הכול" גלוי וקבוע. אין מצב שבו משהו מוסתר ואין יציאה על המסך | בינוני | **כן.** זה סטייט בדף, לא שרת. דורש מניית *כל* מסלולי ההסתרה (אצלנו 9, ראו פרק 2) |
| **BioDigital Human** | `scene.reset` / `resetScene()` כפעולה אטומית | ה-Web Viewer API מגדיר «Reset the scene to its original state»; ב-Android SDK ‏`resetScene()` = «Reset the camera and objects to the current scene/chapter's original state» | reset אחד שמחזיר **מצלמה + אובייקטים** ל"מצב ההתחלה של הסצנה" — בדיוק מה שהבעלים ביקש כ-"reset the specific model" | בינוני | **כן** |
| **BioDigital Human** | `isolate(ArrayList<String>)` — isolate של **רשימת** מבנים | ה-SDK מציע גם `isolate(boolean)` (מצב) וגם overload שמקבל מזהים | isolate צריך לעבוד על **בחירה מרובה**, לא על מבנה בודד | נמוך | **כן** (יש לנו כבר marks) |
| **Visible Body** | **Isolate הוא toggle שחוזר לאחור, ולא "מוחק את העולם"** | «you tap the Isolate button to show only the selected structure, and tapping it again returns you to the original view»; «Isolate Mode ... allows you to focus on a particular structure **without losing your original view**» | ה-isolate חייב לשמור את המצב הקודם במלואו ולהחזיר אותו בלחיצה אחת — לא "לשחזר בקירוב" | נמוך-בינוני | **כן** |
| **Visible Body** | **History button** = Undo / Redo / "refresh to original" במקום אחד | «you select the History button from the bottom menu bar, and from there you can undo or redo edits or refresh the model to its original state» | לאחד את Undo/Redo (יש לנו, Q294) עם ה-reset של הדגם **באותו פקד** — פחות כפתורים, לא יותר | נמוך | **כן** |
| **Visible Body** | הפרדה בין **Reset View** ל-**Reset All** | שני פקדים נפרדים בשתי גרסאות; בנוסף «pressing the Home key resets the camera view» | להבהיר אצלנו: ⟲ של המודול ≠ reset של המודל ≠ reset של המצלמה. שלושה דברים, ושמות שאומרים מה כל אחד נוגע בו | נמוך | **כן** |
| **Visible Body** | multi-select → isolate יחד | «if you use the multi-select tool, you can highlight multiple structures and bring them all into Isolate Mode at the same time» | כנ"ל לשורה של BioDigital | נמוך | **כן** |
| **Complete Anatomy** (3D4Medical) | **Hide Others / Fade Others** כשתי פעולות נפרדות מ-Isolate | קיצורי Mac: `⌘I` = Isolate ‏(Edit > Isolate), `⌘⇧K` = Hide Others, `⌘⇧J` = Fade Others | **"Fade others" עדיף על "Hide others" כברירת מחדל**: הסביבה נשארת כהקשר ואי אפשר "להיתקע בחושך". אצלנו שתיהן קיימות אבל חבויות באותה מידה | נמוך | **כן** |
| **Complete Anatomy** | **"Show Hidden" לפי מערכת** | במק: «selecting the system icon and then 'Show Hidden' restores hidden or faded structures within that system» | החזרה לא חייבת להיות הכול-או-כלום: "החזר את מה שהוסתר **בשכבה הזאת**" | בינוני | **כן** |
| **Complete Anatomy** | Reset גלובלי שכולל גם עריכות כלים | «The Reset button resets all structures (including Tool edits)» + reset למערכת שלמה מתוך תפריט Systems | ה-model reset שלנו צריך לכלול גם מידות, סימונים וחתכים — ולומר זאת מראש | בינוני | **כן** |
| **Complete Anatomy** | יציאה מ-Isolate בנייד = **Back** | «On mobile, tap the Back button to return to the main screen» | בנייד צריך מסלול חזרה אחד שהוא *תמיד* באותו מקום | נמוך | **כן** |
| **Essential Anatomy 5** | אזהרה: isolate שמוחק הכול מעצבן משתמשים | מבקר ב-App Store: isolate «removes every structure rather than just the obstructing ones», ומבקש דרך להסיר רק את מה שחוסם | **לממש "הסר את מה שחוסם" (fade/hide של מה שלפני המבנה) כברירת מחדל, ו-isolate מלא כבחירה** — זו תלונה מתועדת על בדיוק ההתנהגות שיש לנו | בינוני-גבוה | **כן**, אבל דורש חישוב "מי לפני מי" מהמצלמה |
| **Essential Anatomy 5** | Multiple Selection mode נפרד | «a separate Multiple Selection mode allows you to hide and/or fade multiple structures quickly» | יש לנו (Q232 marks) — אבל אצלנו הוא בתוך פאנל שצריך לפתוח | נמוך | **כן** |
| **Primal Pictures** (Anatomy.tv) | `HIDE` שהופך ל-`SHOW` — **אותו כפתור הוא היציאה** | «Click on the HIDE button to hide the structure(s). The HIDE button changes to SHOW» | כפתור שמחליף טקסט לפי המצב = אפס עומס מסך, יציאה ברורה | נמוך | **כן** |
| **Primal Pictures** | `CLEAR` נפרד ומסומן כ"מסתיר הכול" | «If you would like to hide everything, use the CLEAR button» | פעולה הרסנית צריכה שם מפורש, לא preset עמום | נמוך | **כן** |
| **Primal Pictures** | **`Home all`** — מרכוז + איפוס סיבוב של **הנראה** | «Press the Home all icon to reset the rotation and center all the visible structures» | reset מצלמה שמתחשב במה שנראה *עכשיו* (יש לנו דומה) | נמוך | **כן** |
| **Primal Pictures** | Layer up/down + **מספר השכבה על המסך** | «Move up and down through the layers using the Layer controls», עם תצוגת מספר שכבה | **אינדיקטור מצב גלוי**: המשתמש רואה באיזה עומק הוא, ולכן יודע שהוא לא ב"ברירת מחדל" | נמוך | **כן** |
| **Anatomage Table** | **צ'קבוקס אחד שמכבה/מדליק את כל המבנים** | «tap the small checkbox at the bottom-left to turn all structures off, and tap it again to turn all structures on»; מדריך אחר: «a single tap on the blue check mark ... removes or adds all structures at once» | "**הראה הכול**" כפקד יחיד, קבוע במקום אחד, דו-כיווני | נמוך | **כן** |
| **Anatomage Table** | **undo של תפריט התצוגה** — גלגל עם חץ נגד כיוון השעון | «to undo anything from this menu, tap the rainbow wheel with a counterclockwise arrow on the bottom of the visibility menu» | undo **מקומי לפאנל** ליד הפאנל עצמו — זה בדיוק ה-⟲ של Q294, ואישור שהכיוון נכון | — (קיים) | **כן** |
| **Anatomage Table** | reset גוף-שלם מוגדר **רשימתית** | «undo all flat color, transparency, BL, and O/Is for the entire body» | ה-reset שלנו צריך לפרט **מה הוא נוגע ומה לא**, בדיוק ככה | נמוך | **כן** |
| **Anatomage Table** | **"Restore from Dissection"** — החזרה מחיתוך היא פקד נפרד | מופיע כפקד עצמאי במדריך Table 12 | חיתוך/חתך הוא מסלול הסתרה בפני עצמו וצריך יציאה **משלו** בשם מפורש | נמוך | **כן** |
| **Anatomage Table** | שקיפות היררכית: מבנה / קטגוריה / מערכת | «Tapping the color wheel for a structure will affect that structure only»; לקטגוריה/מערכת — על כל מה שבתוכה. הסליידר נקרא **Surface** | שקיפות ברמת המערכת (יש לנו, `sysAlpha`) — אבל אצלנו היא לא מסומנת כ"מצב פעיל" | נמוך | **כן** |
| **Zygote Body** | **סליידר עומק אחד** שמפשיט שכבות בסדר אנטומי | «A slider tool ... allows users to control how far into the body they can see. Sliding the control down removes layers, beginning with the skin»; מקור אחר קורא לו **Opacity Slider** | פקד **אחד** ל-"כמה עמוק", במקום N סליידרים לפי שכבה. זה הדפוס שהכי מקטין עומס מסך | בינוני | **כן** — אבל נוגד את כלל "taps over sliders" שלנו, ולכן יְמוּמַש כ-**3–4 צעדים בלחיצה** |
| **Zygote Body** | toggle לשכבה בודדת **בנוסף** לסליידר | «there are toggle bars that hide single layers while showing any others» | יש לנו (שכבות) | — | **כן** |
| **3D Slicer** | **presets לפי רקמה + פקד "Shift" אחד לכיול** | «Several presets are available ... for displaying bones, soft tissues, air, fat»; Shift = «Move all the inner points ... of the current transfer functions to the right/left», שימושי «when a preset defines a ramp from 0 to 200 but your data requires a ramp from 1000 to 1200» | **הדפוס המדויק ל-"strength control" שהבעלים ביקש**: preset קבוע + פקד יחיד שמזיז את כולו ביחד. לא 14 סליידרים לפי שכבה | נמוך | **כן** — מצוין. ה-preset שלנו ב-Z כבר טבלת-שכבות; חסר רק ה-Shift |
| **Blender / Z-Anatomy** | `Alt+Z` = X-Ray toggle; `Numpad /` = Local View (isolate); `H` / `Shift+H` / **`Alt+H` = unhide all** | מתועד בקיצורי Blender; «Shift + H - Hide unselected (Isolate Selected)» | **קיצור מקלדת אחד שמחזיר הכול** — אצלנו אין. ‏`Esc` הוא המקבילה הנכונה בדפדפן | נמוך | **כן** |
| **Dragonfly / Carestream** (כתחליף למקורות Horos שלא נמצאו) | Clip box עם גרירת פאה + **Reset שמחזיר את הקופסה** | «A Reset button restores the Clip box to its initial state»; הקופסה מוצגת גם ב-3D וגם ב-MPR | לקופסת החיתוך שלנו צריך reset משלה, ושהיא תיראה גם בחתכים | נמוך | **כן** |
| **כללי (thumb zone)** | פקדים קריטיים בשליש התחתון | מקורות משניים: השליש התחתון הוא "easy zone"; תפריט hamburger בפינה שמאלית-עליונה הוא ההישג הגרוע ביותר ביד אחת; יעדי נגיעה 44–48 px | ה-chip של isolate וה-reset צריכים לשבת **למטה**, לא בסרגל העליון | נמוך | **כן** |
| **כללי (banners)** | באנר מתמשך חייב אפשרות סגירה | הנחיית Firefox: «always provide a dismissible 'x' affordance for user-triggered banners», ו-«don't hide the dismiss control if the banner isn't self-resolving»; מותר באנר אחד בכל רגע | ה-chip של isolate הוא בדיוק "באנר מופעל-משתמש": חייב `✕`, ואסור לערום כמה כאלה | נמוך | **כן** |
| **Complete Anatomy** (ביקורת) | עומס מסך הוא בעיה אמיתית אצל המתחרים | פוסטר AAA 2019 מונה את Complete Anatomy 2018 בין אפליקציות עם «lots on screen» שנהיה מציף; אגרגטור מדווח על «significant user criticism regarding search accuracy, interface usability» (לא אומת — מקור משני). מנגד, סקירת JMLA 2020 וסקירה אקדמית נוספת מתארות ממשק «user-friendly» | **לא להוסיף כפתורים.** כל מה שהסבב הזה מוסיף צריך להחליף או להתקפל — זה האילוץ, לא הערה | — | **כן** |

---

## 2. השיפוט הכנה: היכן אנחנו גרועים יותר

### 2.1 מספר מסלולי ההסתרה — כאן אנחנו הגרועים במסמך

מנינו בקוד של שני המנועים **תשעה מסלולים בלתי-תלויים** שיכולים להעלים מבנה מהמסך, לכל אחד יציאה אחרת ובמקום אחר:

| # | מסלול | מנוע | היציאה הקיימת היום | הבעיה |
|---|---|---|---|---|
| 1 | `iso` — כפתור **Isolate** | own | אותו כפתור ב-toolbar | הכפתור לא אומר *מה* מבודד; ב-toolbar שנגלל/נשבר לשורות בנייד הוא עלול לצאת מהשדה |
| 2 | `soloLayer` — **solo** לשכבה | Z | כפתור ה-solo שבתוך שורת השכבה | אם פאנל השכבות מקופל — **אין שום יציאה על המסך** |
| 3 | `sr === "hide"` — Marked/Others → **Hide** | שניהם | בתוך `#sel-sec`, פאנל שצריך לפתוח | אפשר להסתיר "את כל האחרים" ואז לסגור את הפאנל |
| 4 | `hideOverride[id]` — **hide** מכרטיס המבנה | own | רק מאותו כרטיס | אם הכרטיס נסגר והמבנה מוסתר — הוא לא ניתן למצוא |
| 5 | `preset(map)` — presets של Z | Z | preset `all` | **זה החמור**: `LK.forEach(... map[k]!==undefined?map[k]:0)` — כל שכבה שלא ברשימת ה-preset מקבלת אלפא **0**. כלומר `skeleton` / `nervous` / `vessels` / `organs` מעלימים את כל השאר לגמרי, וה"יציאה" נקראת `all` ולא "הראה הכול" |
| 6 | `sideFilter` — left / right | Z | כפתור `both` | מסתיר חצי גוף; ה-`both` הוא כפתור שקול לשני האחרים, לא "יציאה" |
| 7 | cut / cross-section / part slices | שניהם | בתוך פאנל ה-cut, ו-⟲ של Q294 | שלושה מנגנונים שונים שכולם "חותכים" |
| 8 | שכבות + `srcOn` (source facet) + `hidden_default` | שניהם | הפאנלים עצמם | שלושה פילטרים שנראים דומה ומתנהגים שונה |
| 9 | `sysAlpha` / `fadeOverride` / fade=0.15 | שניהם | הפאנל / הכרטיס | **אלפא נמוכה היא הסתרה למעשה** אבל לא נספרת כ"מוסתר" באף מקום |

**במוצרים שנבדקו אין דבר כזה.** BioDigital מציע שלושה כלים (Hide / Isolate / Fade) ו-Reset אחד שמופיע כשנגעת באחד מהם. Primal מציע HIDE↔SHOW ו-CLEAR. Anatomage מציע צ'קבוקס אחד שמחזיר את כל המבנים. אנחנו מציעים תשעה מסלולים ו**אפס** פקד שאומר "הראה הכול" — זאת בדיוק התלונה של הבעלים, והיא מוצדקת לחלוטין.

### 2.2 מה כן טוב אצלנו, ואין במתחרים

כדי שהשיפוט יהיה כנה לשני הכיוונים: ‏(א) **Undo/Redo של ≥10 צעדים עם snapshot providers** (Q294) — רק ל-Visible Body יש History דומה, ול-Anatomage יש undo מקומי לתפריט; לשאר אין בכלל. (ב) ‏`reveal(ids)` במנוע Z — «an explicit choice beats a switched-off layer / hide / fade / solo / side filter»: בחירה מפורשת מבטלת כל פילטר שמסתיר. זה דפוס שלא נמצא באף מוצר אחר, והוא **הבסיס הנכון** למה שצריך להיבנות. (ג) מדידה (Q294) ו-cross-section מרובת-חתכים (Q281) מעבר למה ש-Visible Body מציע ("series of sliced 3D models"). (ד) ‏`method` / `error_band_mm` קיימים בנתונים — אף מוצר מסחרי לא חושף provenance ברמה הזאת (אם כי אצלנו הם לא מוצגים; ראו Q297 §E).

### 2.3 X-ray ו-fade — למה השלד לא נראה

ראו פרק 3; בקצרה: במוצרים שנבדקו **העצם היא שכבת ההתמצאות** ונשארת אטומה (ה-preset של 3D Slicer ל-bone, Zygote שמפשיט מהעור פנימה, `btn-bones` שלנו). אצלנו העצם *מוגדרת* אטומה ואף על פי כן נעלמת — זה באג, לא העדפה.

---

## 3. האבחנה הטכנית של תלונת ה-X-ray / fade (נמצאה בקוד, לפני כל תיקון)

| # | מנוע | הממצא בקוד | המכניקה | התוצאה |
|---|---|---|---|---|
| א | **own** (three.js) | `var base = (s.cat === "muscle" && xr) ? 0.34 : (xr && s.cat !== "bone" ? 0.5 : 1)` | העצם אטומה (1) ומצוירת ב-pass האטום; **כל** רקמה רכה מקבלת 0.5 (שריר 0.34) ומצוירת מעליה. ההחלשה **מכפלתית**: מה שנשאר מהעצם = ‎∏(1−aᵢ) על כל מה שלפניה | עור·שומן·שריר·פאסיה ‎≈ 0.5·0.5·0.66·0.5 ≈ **0.08** — העצם תורמת ‎~8 % מהפיקסל. "can not be seen almost at all" |
| ב | **Z** (WebGL משלנו) | `btn-xray` → `{bone:1, muscle:.22, fascia:.15, fat:.05, skin:.06, viscera:.25, ...}` — טבלה מכויילת היטב כשלעצמה. אבל: `gl.disable(gl.CULL_FACE)` ו-`gl.depthMask(false)` ב-pass השקוף, בלי מיון | אין back-face culling ⇒ **כל קונכייה סגורה מתערבבת פעמיים** (פאה קדמית + אחורית). ההחלשה היא ‎∏(1−aᵢ)² | עם 4–6 שרירים חופפים: ‎0.78^(2·5) ≈ **0.085**. אותה תוצאה בדיוק, ממסלול אחר |
| ג | **שניהם** | `var fade = 0.15` ב-`viewer/selection/selection.js` — אלפא **אחת שטוחה לכל המבנים** | ב-"fade view" (Others → Fade) העצם יורדת ל-0.15 בדיוק כמו העור | השלד נעלם בדיוק כמו שהבעלים מתאר. אין שום רצפה לפי מחלקת רקמה |

**המסקנה שמכתיבה את התיקון:** בשני המנועים זה אותו כשל — האלפא לכל שכבה כוילה כאילו יש שכבה אחת לפני העצם, והחשבון האמיתי הוא מכפלה על N שכבות (ובמנוע Z — על 2N פאות). הורדת אלפא לכל שכבה בלבד לא תפתור את זה באופן יציב, כי N משתנה לפי אזור הגוף ולפי זווית המצלמה. התיקון היציב היחיד הוא **pass נוסף של עצם מעל הרקמה הרכה** (העצם מצוירת שוב, אחרי ה-pass השקוף, בעוצמה β מבוקרת) — כך תרומת העצם לפיקסל אינה תלויה כלל במספר השכבות שלפניה. β הוא ה-"strength control" שהבעלים ביקש, וב-3 צעדי לחיצה (לפי כלל הנייד: taps over sliders) ולא כסליידר. ב-Z זה pass נוסף על ה-BATCHES של `bone`; ב-own זה חומר שני עם `depthTest:false` ו-`renderOrder` גבוה. לשני המנועים — אפס שינוי גיאומטריה.

---

## 4. ההמלצות, מדורגות

1. **Reset / "הראה הכול" שמופיע ברגע שמשהו מוסתר** — הדפוס של BioDigital, מיושם על כל תשעת המסלולים בפרק 2.1. זה הדבר היחיד שפותר את התלונה בשורשה ולא רק במסלול אחד.
2. **chip "isolated: ‹שם› ✕"** קבוע, בשליש התחתון, עם `Esc` בדסקטופ ו-`✕` בנייד — Visible Body (toggle שחוזר) + הנחיית ה-dismiss של Firefox + thumb zone. חייב להחזיר את המצב **המדויק** שקדם, כצעד undo אחד.
3. **pass עצם מעל רקמה רכה ב-x-ray וב-fade + רצפת אלפא לעצם ב-fade**, עם 3 צעדי עוצמה — פרק 3. נמדד בניגודיות פיקסלים, לא בעין.
4. **model reset** = ‏`scene.reset` של BioDigital + הפירוט הרשימתי של Anatomage ("מה הוא נוגע ומה לא"), מאוחד עם Undo/Redo לפקד אחד בסגנון ה-History של Visible Body, וכצעד undo אחד.
5. **presets של Z שיפסיקו להעלים בשקט** — `map[k] ?? 0` הוא מלכודת; לכל preset צריך להיות ברור שהוא מצב פעיל, ו-`all` צריך להיקרא "הראה הכול" (Primal `CLEAR` לעומת Anatomage's checkbox).
6. **"הסתר רק את מה שחוסם"** במקום isolate מלא כברירת מחדל — התלונה המתועדת על Essential Anatomy. מאמץ גבוה יותר; מועמד לסבב הבא.
7. **פקד עומק אחד בצעדים** בנוסף לשכבות (Zygote + ה-Shift של Slicer) — מקטין את מספר הסליידרים על המסך יותר מכל שינוי אחר. מועמד לסבב הבא.
8. **הצגת `method` ו-`error_band_mm`** על הכרטיס — לא מהבנצ'מרק אלא מ-Q297 §E, אבל שייך לאותו עיקרון: מצב שלא מוצג על המסך הוא מצב שאפשר להסתיר בטעות.

---

## 5. מקורות

ציטוטים נקראו דרך `WebSearch` בלבד (כל `WebFetch` נחסם, ראו הכותרת).

- BioDigital — Human Viewer API ‏(`developer.biodigital.com/docs/widget/reference/namespaces/scene`), Android SDK index ‏(`developer.biodigital.com/pages/documentation/2/android-sdk-docs/`), ו-`support.biodigital.com/hc/en-us/articles/360052240974` (Explore Tools, כפתור Reset).
- Visible Body — `help.cengage.com/visible-body/student/visible-body/atlas-getting-started-ipad.html` ו-`...-mac.html`, `...atlas-cross-sections-windows.html`; מדריכי ספרייה (LSU, FAU, LJMU).
- Complete Anatomy / Essential Anatomy 5 — `cdn.completeanatomy.cn/.../mac_shortcuts.pdf`, `3d4medical.com/category/support/essential-anatomy-5/tutorials`, `apps.apple.com/app/id596684220`, מדריך Complete Anatomy Tutorials של אונ' אתונה, פוסטר AAA 2019, סקירת JMLA 2020.
- Primal Pictures — `statref.com/resources/Primal/Guides/Primal_Pictures_3D_Real-time_User_Guide.pdf`, מדריכי ספרייה (Wigan-Leigh, York).
- Anatomage — Anatomage Table 10.0 / 11.0 / 12.0 User Interface Guides (`hss.washington.edu`, `hsasf.hsa.washington.edu`), `mc3.edu/.../visibility-menu.pdf`, `guides.lib.uiowa.edu/anatomage`.
- Zygote Body — `experiments.withgoogle.com/body-browser`, `commonsense.org/education/reviews/zygote-body`, `educationworld.com/a_tech/site-review/zygote-body.shtml`, `research.dom.edu/PAS/anatomyandphysiology`.
- 3D Slicer — `slicer.readthedocs.io/en/5.8/user_guide/modules/volumerendering.html` (+ 5.2 / 4.11), `discourse.slicer.org`.
- Blender / Z-Anatomy — התייחסות לקיצורי Blender (`Alt+Z`, `Numpad /`, `Alt+H`); **לא נמצא תיעוד ל-keymap של Z-Anatomy עצמו**.
- קליפ-בוקס — `theobjects.com/dragonfly/dfhelp` (Clipping), `help.carestreamdental.com` — **כתחליף למקורות Horos/OsiriX שלא אותרו**.
- דפוסים כלליים — `acorn.firefox.com` (Banner), מקורות thumb-zone משניים.
- **ללא מקור אמין:** Horos / OsiriX; הצופה של Radiopaedia; מצב ה-x-ray של Complete Anatomy (לא אומת אם קיים סליידר עוצמה).
