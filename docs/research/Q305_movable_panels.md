# Q305 — האם ואיך אטלסים ותוכנות קיימות מאפשרים להזיז את ה-panels על המסך

בקשת הבעלים (במקור בעברית): **"אפשר לנייד את המשבצות השונות על המסך"** — שהמשתמש יוכל להזיז בעצמו את התיבות
(panels / bars / cards) במקום לחיות עם המקום שבו שמנו אותן.

**מתודולוגיה והגבלה שחייבת להיאמר מראש.** כמו ב-Q300, Q301 ו-Q303: `WebFetch` חסום ב-DNS לכל ה-product hosts
(`support.biodigital.com`, `www.visiblebody.com`, `3dprimalpictures.com`, `www.anatomage.com`) וגם ל-`www.w3.org`.
לכן **כל טענה כאן נשענת על ציטוט ש-`WebSearch` החזיר**, וכל מה שאין לו ציטוט מסומן **"לא מאומת"**. ציטוטים
מופיעים בין « ».

---

## 1. מה עושים האטלסים הקליניים עצמם — והתשובה הקצרה היא: כמעט כלום

| מוצר | מה מצאנו | מסקנה לגבינו |
|---|---|---|
| **BioDigital Human** | ה-panel של המידע **קובע את התוכן שלו מראש, לא המשתמש**: «The secondary Chapter List has been removed from its fixed position in the information panel and is now available on demand in any tour in which it is enabled». ה-toolbar של Undo/Redo/Reset נדלק **בזמן פרסום המודל או דרך URL parameter**, לא על ידי המשתמש: «To enable the new Undo/Redo/Reset toolbar in new models you publish, select Undo under Display Options when you publish your model, or add the URL parameter &ui-undo=true». | ה-layout הוא החלטה של מי שפרסם, לא של הלומד. **אין עדות ל-panel שהמשתמש מזיז.** |
| **Visible Body** | **לא נמצא שום מקור** על הזזת panels או windows. המקור היחיד שעלה הוא דף IT של אוניברסיטה, והוא מתאר הזזת **המודל** ולא של ה-UI: two-finger drag מזיז את המודל, ו-spacebar + drag עושה pan. | **לא מאומת** אם קיים שם layout שהמשתמש מזיז. |
| **Complete Anatomy** | **0 תוצאות** על panel layout. | **לא מאומת.** |
| **3D Slicer** | היחיד שיש לו תיעוד מפורש, והוא ה-precedent שאימצנו. ה-wiki של 4.8 כותב שה-module panel ניתן ל-**undock על ידי גרירה של ה"panel chrome"** או דרך undock icon, ו-**redock בדאבל-קליק** על אותו chrome; המונח «panel chrome» תוקן אחר כך ל-«window title bar and frame». בפורום שלו מראים שאפשר להוסיף dock widget משלך ולקבוע אותו «closable, floatable, and movable» (זה Qt, כלומר התנהגות של ה-toolkit ולא feature של Slicer). | **ה-affordance המתועד הוא title bar / panel chrome.** זה המקור לכך שאנחנו לא עושים את גוף התיבה bar של גרירה. |
| **Anatomage** | לא נמצא דבר על layout שהמשתמש מזיז (ב-Q303 כבר נמצא שה-layouts שלו קבועים: `3D Only`, `3D/2D`, `3D/2D Splitscreen`). | **אין layout חופשי.** |

**המסקנה שמנחה את העיגול:** בשוק האטלסים **אין דבר כזה**, ובכלי המחקר (Slicer, שהוא Qt) יש — והוא **title bar**.
לכן ה-affordance שלנו הוא **ידית קטנה (handle)** על כל תיבה, לא גוף התיבה; ואנחנו **לא** מעתיקים את ה-undock/redock
של Qt, כי אין לנו windows של מערכת הפעלה.

---

## 2. למה ידית ולא ה-title bar עצמו, ולמה לא גוף התיבה

שני שיקולים, שניהם מבוססים:

1. **מה שמסמן גרירה בצורה הטובה ביותר הוא drag handle.** מחקר 2019 על signifiers למחוות מגע מדד זאת:
   «drag handles and drop shadows helped users discover dragging more than temporal cues did for double-tapping»,
   וה-«drag handle was the most effective at signifying its affordance». זה המקור היחיד כאן שהוא primary source.
2. **ידית שמופיעה רק ב-hover פוסלת מגע ומקלדת.** הנחיה שעלתה: ידית בלתי-נראית שמופיעה רק ב-hover
   «excludes touch-screen and keyboard users and increases discovery friction for everyone else», ולכן ההמלצה היא
   **persistent handles**. אצלנו הידית תמיד על המסך (opacity 0.78 במנוחה), ולא רק ב-hover.

**ולמה לא ה-title bar של התיבות שלנו, אף על פי ש-Slicer כן?** כי ה-heads של התיבות האלה **מלאים בכפתורים** —
ל-`#cut-panel` יש `cut-min` ו-`cut-exit` ב-head, ל-`#q301-sheet` יש כפתור סגירה ב-head, ול-`#info` יש `.info-min`
ו-`.info-close`. גרירה של ה-head הייתה מתנגשת בהם. (ה-precedent הפנימי שלנו דווקא כן עושה title bar: ל-reference
window של שכבת ה-imaging יש `.ref-head{cursor:move}` עם גרירה משלה מאז Q246 — ושם ה-head כמעט ריק.)

---

## 3. מה שתקן הנגישות דורש, וזה שינה את העיצוב

**WCAG 2.2, SC 2.5.7 "Dragging Movements" (Level AA)** דורש שלכל פעולה שתלויה בגרירה תהיה דרך נוספת
**בלי** גרירה: «The intent of this success criterion is to ensure functionality that uses a dragging movement has
another single pointer mode of operation». רק נקודת ההתחלה והסוף נחשבות; מחוות path-based שייכות ל-SC 2.5.1.
חשוב: W3C אומר שמקלדת **לא** מספיקה בפני עצמה — «the two requirements are evaluated independently».

**מה עשינו בעקבות זאת:** (א) מקלדת — מקשי החצים מזיזים את התיבה שהידית שלה ב-focus, ו-`Home` מחזיר אותה;
(ב) single pointer בלי גרירה — **"Restore layout"** בקבוצת View של ה-control bar הוא single tap שמחזיר את הכול,
ובטלפון כל נחיתה היא **snap לאחד מכמה slots**, כך שאין צורך בדיוק של גרירה. **מה שעוד חסר, ונאמר בגילוי לב:**
אין לנו "tap-to-place" מלא (tap על הידית ואחר כך tap על המקום) — זה open item ל-Q306 ולא נטען שה-SC מכוסה במלואו.

**גודל יעד המגע.** WCAG 2.2 SC 2.5.8 "Target Size (Minimum)" (AA) הוא **24×24 CSS px**; ההמלצה הרחבה יותר
(secondary, לא תקן) היא **44×44** לידית, כאשר «the visible graphic possibly smaller than the hit area». אצלנו:
26px מצוירים ב-desktop ו-34px ב-`pointer:coarse`, ושטח הפגיעה מורחב ל-44px — **אבל רק פנימה, לתוך התיבה**.
הסיבה היא מדידה ולא טעם: הגרסה הראשונה הרחיבה 9px לכל הכיוונים, השטח בלט מהתיבה אל ה-canvas,
ו-touch adjustment של Chromium "תפס" אצבע שנחתה 7px מחוץ ל-panel אל הידית — וה-orbit של המודל הפסיק לעבוד.

---

## 4. טלפון: floating או docking

**מה שמצאנו:** ל-bottom sheet יש תיעוד מפורש — הוא «anchored to the bottom of the screen» ומיועד ל-secondary
content, עם variant מודאלי ואחד שאינו מודאלי; ה-non-modal מתאים כאשר רוצים «to present additional content to the
main UI». SAP Fiori מוסיף שה-modal «must be dismissed to interact with the underlying content» ושלא כדאי לשים בו
«complex information». **מה שלא מצאנו:** אף מקור שמשווה ישירות floating panel מול docked sheet במסך קטן —
**לא מאומת**, ולכן ההחלטה שלנו נשענת על **מדידה על הדף שלנו** ולא על מקור.

**המדידה (390×844, free travel = ויוופורט פחות 24px gutter פחות מידות התיבה):** ל-control bar יש
`freeX = -8px` — כלומר **אין בכלל חופש אופקי**; ל-structure card `freeX = 54px`; ל-rail (כ-bottom sheet)
`freeX = -24px`, `freeY = 298px`; ולתיבות הקטנות (measure, slices, expand, pills) 232–265px. גרירה חופשית של
תיבה שיש לה 8 פיקסלים של חופש היא לא feature. **לכן הכלל הוא מדיד ולא טעם: ציר שה-free travel בו קטן מ-48px
(אגודל אחד) מקבל slots במקום גרירה חופשית** — תיבה רחבה מקבלת שלוש רצועות (top / middle / bottom) ותיבה קטנה
את ארבע הפינות; וזה מה שגם משאיר את התיבה "מעוגנת" כמו bottom sheet במקום לצוף באלכסון.

---

## 5. מה אומץ, ממה, ומה נדחה

| אומץ | מהיכן | הערה |
|---|---|---|
| ידית גרירה נפרדת, תמיד נראית | מחקר ה-signifiers 2019 + ההנחיה נגד hover-only | לא ה-title bar, כי ה-heads שלנו מלאים בכפתורים |
| גרירה **של title bar** נדחתה לטובת ידית | 3D Slicer («panel chrome» / «window title bar and frame») הוא ה-precedent, אבל לא ה-implementation שלנו | ה-precedent הפנימי `.ref-head{cursor:move}` נשאר כפי שהוא |
| חלופה בלי גרירה: tap אחד ל-Restore layout + חצים במקלדת | WCAG 2.2 SC 2.5.7 | לא מכסה את ה-SC במלואו — open item |
| 44px שטח פגיעה, גרפיקה קטנה יותר | WCAG 2.2 SC 2.5.8 (24px מינימום) + המלצה משנית ל-44px | מורחב **פנימה בלבד**, מסיבה שנמדדה |
| slots בטלפון, לא גרירה חופשית | ה-bottom sheet «anchored to the bottom» + **המדידה שלנו** | הגבול 48px הוא שלנו |
| **נדחה:** undock ל-window נפרד + redock בדאבל-קליק | 3D Slicer / Qt | אין לנו windows של OS; ובמסך של טלפון זה חסר משמעות |
| **נדחה:** layout שנקבע בזמן פרסום ולא על ידי המשתמש | BioDigital | זו בדיוק הבקשה שהבעלים ביקש להפוך |

---

## 6. מה נשאר לא מאומת

1. האם ל-Visible Body או ל-Complete Anatomy יש layout שהמשתמש מזיז — **לא מאומת** (אין תיעוד שנמצא).
2. האם ההתנהגות של Slicer (גרירה של ה-chrome, דאבל-קליק ל-redock) עדיין נכונה ב-2025–2026 — המקורות הם wiki
   של 4.8 ו-tracker items מ-2011–2014, ולא נמצא תיעוד עדכני. **לא מאומת לגרסה הנוכחית.**
3. הנחיית NN/g עצמה על drag handles או על touch targets — **לא נמצאה**; אגרגטור אחד ייחס ל-NN/g נתון
   ("22% more time on flat designs", 2015) שלא הצלחנו לאמת, ולכן הוא **לא בשימוש כאן**.
4. השוואה מתועדת floating מול docked במסך קטן — **לא מאומת**; ההחלטה שלנו נשענת על המדידה בסעיף 4.

---

## 7. פגם ה-`#foot` — specificity, לא אדריכלות

הפגם שהסבב הזה מצא אינו שלו. בקבוצת **View** של הפקד של Q301 נאמצת (`qg-adopted`) שורת הכפתורים התחתונה של
מנוע ה-Z, `#foot`. Q301 מעצב אבר מאומץ ב-`.qg-sbody .qg-adopted` — **שתי מחלקות, specificity 0,0,2,0** — ולכן
ההצהרה הזו **מפסידה** ל-`#foot{position:fixed}` של המנוע עצמו — **מזהה אחד, 0,1,0,0**. התוצאה: השורה המאומצת
נשארה `fixed` בתחתית ה-viewport, מחוץ לזרימה של הגיליון ומעליו, והצטיירה מעל **כל אבר שרשום אחריה** בגיליון.

**המכשיר** הוא זה שמצא גם את שתי ההתנגשויות הקודמות (ה-info drawer של Q301 מעל Undo, ושורת ה-chips של Q300 מעל
Redo): `document.elementFromPoint` במרכז הפקד. **הנמדד בעמוד Base, לפני התיקון:** הכפתור `Restore layout` **אינו**
האבר שבמרכז שלו עצמו ב-**4 מתוך 4** מצבי הגלילה ב-1400×900, וב-**2 מתוך 4** ב-390×844 — ‏`DIV#foot` עצמו בשניים
מהם בכל viewport, ובשניים הנותרים בדסקטופ אחת מה-**pills של `#foot` עצמו** (`BUTTON.pill`), כלומר אותו פגם שכבה
אחת פנימה: השורה עדיין מעל. **אחרי התיקון:** הכפתור עצמו ב-4 מתוך 4, בשני ה-viewports.
‏(תיקון לדיוק מפאזה 1, שדיווחה "‎4 מתוך 4 בשני ה-viewports": בטלפון זה 2 מתוך 4.)

**התיקון** הוא הצהרה אחת, `.qg-sbody #foot{position:static}` (0,1,1,0 — ספציפי מספיק), והיא יושבת ב-CSS של
**Q305 עצמו** ולא ב-block של Q301. זה לא פרט סטייל: הברית של הסבב הזה היא שה-block של כל סבב קודם יוצא
מה-regen **זהה בייט-לבייט**, וזה נבדק (`assert_blocks_q303.py --round q305`). ההצהרה **מוגדרת רק בתוך הגיליון**,
ולכן `#foot` במקומו הטבעי לא נוגע: רצועת הכפתורים בתחתית המסך נשארת `position:fixed`, ובטלפון היא נשארת בתוך
הרצועה `calc(3.3rem + safe-b)` שQ270 שומרת לה מתחת ל-`#rail` — שני אלה נמדדו.

**מה שלא נוגע נשאר לא נוגע, נמדד.** ‏`#foot` במקום שהדף שם אותו: `position:fixed`, נראה, ‏14px מהתחתית ו-14px
מהשמאל ב-1400×900, ו-12px / 11px ב-390×844 — ובטלפון רצועה של 43px בתוך ה-52.8px ש-`#rail` שומרת לה. נמדד **לפני**
שקבוצת View אימצה את השורה, כי Q301 מחנה אבר מאומץ בצומת מוסתר כשהגיליון נסגר — זה התכנון שלו, הקבוצה **מחליפה**
את השורה ולא שואלת אותה.

**הוכחה.** `scripts/anatomy/q305/prove_foot_q305.py` מודד את שני המצבים על **אותו דף בנוי**, בריצה אחת:
ל-pass של "לפני" הוא מוציא את ההצהרה מה-stylesheet של הדף עצמו (`deleteRule`), ול-pass של "אחרי" מחזיר אותה
לאותו index (`insertRule`). כך שני ה-passes נבדלים **רק** בהצהרה הזו — בלי build שני ובלי עותק מעודכן של הדף.

**תיקון לדיוק מפאזה 1.** `#foot` קיים רק ב-template של Z — עמודי Base ו-Combined, 4 מתוך 6. בשני עמודי
ה-Imaging אין `#foot` כלל, ולכן האמירה "בשני המנועים" הייתה שגויה; במנוע העצמי התיקון הוא **no-op שנמדד**.
