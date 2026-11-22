# Q295 — שומן וחללים בחתכים: ביקורת, מקורות ומה נשלח

**בקשת הבעלים (תרגום):** "השומן צריך להיות במקומות הרלוונטיים. בחתכים חייבים לראות מילוי — בלי חורים. חורים אומרים שכנראה חסרות רקמות רלוונטיות, או שפילחנו אותן לא נכון."

## 1. שיטה

- **חתכים צירִיים על הרשתות עצמן (Python):** 30 מפלסים בכל אזור, 12 אזורים לכל עמוד (ראש, צוואר, בית חזה, בטן, אגן, ירך, ברך, שוק, כף רגל, זרוע, אמה, כף יד), פיקסל 1 מ"מ. כל מבנה ממולא לפי כלל ה-winding (רשת סגורה = מילוי מדויק, קליפה חלולה = טבעת); רשת פתוחה — מתאר + מילוי חורים; יריעות (פסציה, קופסית מפרק, בורסה) — מתאר בלבד; מבנים מוסתרים כברירת מחדל לא נספרים. גבול הגוף = עור העמוד פחות שכבת העור עצמה (1.5 מ"מ).
- **חלל (void)** = שטח בתוך העור שאף מבנה לא מכסה. **תת-עורי** = מחוץ ל"מעטפת" של המבנים (סגירה 5 מ"מ), **עמוק** = בתוכה; החללים העמוקים קיבלו שם לפי המבנים שסביבם (רטרופריטוניאלי, מזנטרי, חלל איסכיו-אנאלי, ארובה, בוקאלי, פופליטאלי, בית שחי, Hoffa ועוד).
- **מה יש בחלל באמת — מההדמיה של אותו גוף:** אישה — ה-CT הטרי שלה (גוש הגו + גוש הירך-אצבעות, אותו רישום ששימש את כל מבני ct_vhf), שומן = HU ‎−190…−30 (חלון השומן המקובל בכימות רקמות ב-CT; ראו אימות ה-CT מול גופות למדידת שומן תת-עורי ובין-שרירי: Mitsiopoulos 1998, ‏PMID 9655763; המספרים עצמם לא נקראו בתקציר), רקמה רכה = ‎−29…+200; גבר — ה-CT הקפוא שלו לא מפריד שומן משריר (ידוע מסבבים קודמים), לכן **צילומי החתכים הצבעוניים שלו** (1 מ"מ, scripts/cryo/cryo_classes.py: שומן = צהוב-שמנת) ברישום הקיים לפריים שלו. Combined = אותו פריים (בלי העברה). Base = גוף Z גנרי: רישום thin-plate-spline ל-Combined של אותו גוף מכל זוגות הקודקודים של המבנים המשותפים (ראו טבלה 4). לכל חלק גוף בחתך — הזזה במישור (עד 12 מ"מ) שמיישרת את צללית ההדמיה על עור העמוד.
- **החלטה לכל חלל:** (א) שומן בהדמיה → נשלחת רשת שומן; (ב) רקמה רכה בהדמיה (לא שומן) → רקמה חסרה/לא מפולחת — נשלחת כ"רקמה רכה לא מסווגת" ושמה בכרטיס אומר מה עמוד ההדמיה של אותו גוף מפלח שם; (ג) פלח דק/מוזז — רצועות של עד ~4 מ"מ בין מבנים נשארות כפי שהן (גבולות פילוח), ונמדדו בתלת-ממד (טבלה 5).

## 2. איזה שומן היה בעמודים לפני הסבב

| עמוד | מבני שומן קיימים |
|---|---|
| Imaging F (הדמיה, אישה) | Breast: fat pad (left) (מוסתר); Breast: fat pad (right) (מוסתר) |
| Imaging M (הדמיה, גבר) | אין |
| Base F | Greater omentum; Infrapatellar fat pad; Infrapatellar fat pad; Lesser omentum; Breast: fat pad (left) (מוסתר); Breast: fat pad (right) (מוסתר) |
| Base M | Greater omentum; Infrapatellar fat pad; Infrapatellar fat pad; Lesser omentum |
| Combined F | Greater omentum; Infrapatellar fat pad; Infrapatellar fat pad; Lesser omentum; Breast: fat pad (left) (מוסתר); Breast: fat pad (right) (מוסתר) |
| Combined M | Greater omentum; Infrapatellar fat pad; Infrapatellar fat pad; Lesser omentum |

אין בשום עמוד שומן תת-עורי, שומן ויסצרלי/רטרופריטוניאלי, שומן בין-שרירי, שומן הארובה, הכרית הבוקאלית או שומן החלל האיסכיו-אנאלי. שומן מח העצם מיוצג רק במודל העצם של כלי ההדמיה (לא כרשת).

## 3. חללים לפני / אחרי, לכל עמוד ואזור

חלק החתך שבתוך העור שאינו מכוסה (ממוצע על 30 מפלסים). "אחרי" = עם רשתות Q295. "שומן בחלל" / "רקמה רכה בחלל" = מה ההדמיה מראה בחללים העמוקים לפני.

### Imaging F (הדמיה, אישה)

| אזור | חלל לפני | (תת-עורי / עמוק) | חלל אחרי | חור מרבי לפני → אחרי (מ"מ, דו-ממד) | שומן בחלל העמוק | רקמה רכה בחלל העמוק | מרחבים עמוקים עיקריים (סמ"ר, לפני) |
|---|---|---|---|---|---|---|---|
| ראש | 55% | 47% / 8% | **24%** | 68 → 27 | 11% | 75% | head, other 383.5; orbital 135.7; buccal / masticator 46.8 |
| צוואר | 64% | 56% / 8% | **22%** | 83 → 44 | 20% | 77% | neck, other 440.6; posterior triangle / posterior neck 439.8; carotid sheath / parapharyngeal 296.8 |
| בית חזה | 36% | 21% / 15% | **14%** | 98 → 98 | 44% | 50% | mediastinal / pleural 2350.2; chest wall 409.5; breast 148.6 |
| בטן | 52% | 42% / 10% | **15%** | 101 → 101 | 44% | 54% | retroperitoneal / perirenal 1189.3; intraperitoneal (mesenteric / omental) 451.5; abdominal wall / paravertebral 258.0 |
| אגן | 61% | 54% / 7% | **11%** | 94 → 22 | 49% | 49% | pelvic visceral (perivesical / perirectal) 395.3; pelvis, other 310.0; gluteal intermuscular 292.8 |
| ירך | 60% | 56% / 4% | **9%** | 74 → 24 | 38% | 60% | thigh, deep 485.1; small slivers (< 4 mm2) 38.4 |
| ברך | 67% | 58% / 9% | **21%** | 42 → 28 | 10% | 87% | knee, other 296.4; popliteal 274.2; infrapatellar (Hoffa) / suprapatellar 51.2 |
| שוק | 45% | 40% / 5% | **15%** | 34 → 29 | 12% | 85% | intermuscular (leg) 188.7; small slivers (< 4 mm2) 15.5; pre-Achilles (Kager) 13.0 |
| כף רגל | 62% | 53% / 9% | **37%** | 42 → 22 | 5% | 86% | plantar / heel pad 194.5; foot, other 50.9; small slivers (< 4 mm2) 15.4 |
| זרוע | 67% | 63% / 4% | **23%** | 58 → 27 | 18% | 70% | intermuscular (arm) 177.3; axillary 54.7; small slivers (< 4 mm2) 11.7 |
| אמה | 68% | 61% / 7% | **23%** | 51 → 30 | 12% | 41% | intermuscular (forearm) 337.9; small slivers (< 4 mm2) 19.8 |
| כף יד ואצבעות | 85% | 80% / 5% | **24%** | 42 → 24 | 14% | 63% | palmar / digital 112.6; small slivers (< 4 mm2) 8.4 |

### Imaging M (הדמיה, גבר)

| אזור | חלל לפני | (תת-עורי / עמוק) | חלל אחרי | חור מרבי לפני → אחרי (מ"מ, דו-ממד) | שומן בחלל העמוק | רקמה רכה בחלל העמוק | מרחבים עמוקים עיקריים (סמ"ר, לפני) |
|---|---|---|---|---|---|---|---|
| ראש | 58% | 53% / 5% | **33%** | 52 → 34 | 45% | 47% | head, other 327.4; buccal / masticator 38.8; orbital 35.3 |
| צוואר | 59% | 54% / 5% | **34%** | 57 → 34 | 23% | 73% | neck, other 452.1; posterior triangle / posterior neck 284.3; small slivers (< 4 mm2) 46.7 |
| בית חזה | 43% | 29% / 14% | **21%** | 69 → 64 | 24% | 56% | mediastinal / pleural 2560.6; chest wall 700.5; axillary 168.7 |
| בטן | 60% | 50% / 10% | **22%** | 96 → 69 | 26% | 58% | intraperitoneal (mesenteric / omental) 1138.0; abdominal wall / paravertebral 649.1; retroperitoneal / perirenal 256.8 |
| אגן | 48% | 38% / 10% | **13%** | 90 → 26 | 55% | 39% | pelvic visceral (perivesical / perirectal) 1096.6; pelvis, other 282.2; gluteal intermuscular 210.8 |
| ירך | 38% | 34% / 4% | **12%** | 66 → 54 | 33% | 59% | thigh, deep 681.2; small slivers (< 4 mm2) 44.1 |
| ברך | 56% | 51% / 5% | **19%** | 53 → 50 | 51% | 42% | popliteal 329.9; knee, other 75.0; infrapatellar (Hoffa) / suprapatellar 42.6 |
| שוק | 31% | 28% / 3% | **21%** | 38 → 38 | 19% | 68% | intermuscular (leg) 134.8; small slivers (< 4 mm2) 25.4; pre-Achilles (Kager) 16.7 |
| כף רגל | 63% | 55% / 7% | **26%** | 44 → 18 | 68% | 27% | plantar / heel pad 244.4; foot, other 66.8; small slivers (< 4 mm2) 10.2 |
| זרוע | 59% | 52% / 7% | **25%** | 52 → 37 | 14% | 66% | intermuscular (arm) 297.4; axillary 121.2; small slivers (< 4 mm2) 16.0 |
| אמה | 64% | 58% / 6% | **24%** | 53 → 26 | 18% | 82% | intermuscular (forearm) 362.9; small slivers (< 4 mm2) 23.8 |
| כף יד ואצבעות | 86% | 81% / 4% | **40%** | 40 → 26 | 63% | 32% | palmar / digital 93.8; small slivers (< 4 mm2) 9.5 |

### Base F

| אזור | חלל לפני | (תת-עורי / עמוק) | חלל אחרי | חור מרבי לפני → אחרי (מ"מ, דו-ממד) | שומן בחלל העמוק | רקמה רכה בחלל העמוק | מרחבים עמוקים עיקריים (סמ"ר, לפני) |
|---|---|---|---|---|---|---|---|
| ראש | 37% | 10% / 27% | **24%** | 39 → 19 | 5% | 77% | orbital 666.0; head, other 452.8; buccal / masticator 132.3 |
| צוואר | 50% | 29% / 21% | **25%** | 78 → 21 | 21% | 71% | carotid sheath / parapharyngeal 839.6; posterior triangle / posterior neck 544.3; neck, other 244.5 |
| בית חזה | 31% | 14% / 17% | **14%** | 38 → 26 | 38% | 52% | mediastinal / pleural 1410.0; axillary 703.5; chest wall 601.1 |
| בטן | 48% | 14% / 34% | **19%** | 53 → 18 | 30% | 65% | retroperitoneal / perirenal 2929.0; abdominal wall / paravertebral 509.1; intraperitoneal (mesenteric / omental) 226.3 |
| אגן | 53% | 27% / 27% | **11%** | 64 → 18 | 49% | 46% | pelvic visceral (perivesical / perirectal) 1932.1; ischioanal fossa 1074.7; pelvis, other 674.6 |
| ירך | 37% | 31% / 6% | **8%** | 46 → 24 | 45% | 53% | thigh, deep 534.2; small slivers (< 4 mm2) 52.6 |
| ברך | 39% | 29% / 10% | **17%** | 28 → 12 | 28% | 55% | popliteal 416.0; infrapatellar (Hoffa) / suprapatellar 120.9; knee, other 72.7 |
| שוק | 33% | 28% / 5% | **12%** | 23 → 9 | 24% | 68% | intermuscular (leg) 176.2; pre-Achilles (Kager) 37.6; small slivers (< 4 mm2) 23.2 |
| כף רגל | 44% | 25% / 18% | **28%** | 30 → 18 | 18% | 56% | plantar / heel pad 796.7; foot, other 222.7; small slivers (< 4 mm2) 25.3 |
| זרוע | 30% | 23% / 7% | **17%** | 19 → 18 | 30% | 62% | intermuscular (arm) 113.7; axillary 75.9; small slivers (< 4 mm2) 26.0 |
| אמה | 26% | 16% / 10% | **18%** | 11 → 10 | 19% | 64% | intermuscular (forearm) 199.3; small slivers (< 4 mm2) 27.7 |
| כף יד ואצבעות | 34% | 19% / 14% | **30%** | 10 → 9 | 21% | 57% | palmar / digital 146.7; small slivers (< 4 mm2) 14.0 |

### Base M

| אזור | חלל לפני | (תת-עורי / עמוק) | חלל אחרי | חור מרבי לפני → אחרי (מ"מ, דו-ממד) | שומן בחלל העמוק | רקמה רכה בחלל העמוק | מרחבים עמוקים עיקריים (סמ"ר, לפני) |
|---|---|---|---|---|---|---|---|
| ראש | 38% | 11% / 27% | **29%** | 42 → 16 | 47% | 44% | orbital 629.2; head, other 500.8; buccal / masticator 187.8 |
| צוואר | 52% | 31% / 21% | **30%** | 52 → 21 | 17% | 73% | carotid sheath / parapharyngeal 883.9; posterior triangle / posterior neck 469.4; neck, other 162.0 |
| בית חזה | 27% | 10% / 17% | **15%** | 37 → 32 | 21% | 65% | mediastinal / pleural 1665.9; axillary 903.4; chest wall 747.1 |
| בטן | 40% | 12% / 28% | **20%** | 75 → 52 | 29% | 50% | retroperitoneal / perirenal 3243.1; abdominal wall / paravertebral 1039.6; intraperitoneal (mesenteric / omental) 528.7 |
| אגן | 53% | 27% / 26% | **17%** | 65 → 30 | 42% | 43% | pelvic visceral (perivesical / perirectal) 1812.3; ischioanal fossa 743.5; pelvis, other 720.2 |
| ירך | 39% | 34% / 6% | **12%** | 47 → 28 | 25% | 70% | thigh, deep 618.0; small slivers (< 4 mm2) 56.4 |
| ברך | 40% | 29% / 10% | **15%** | 34 → 13 | 61% | 28% | popliteal 448.0; infrapatellar (Hoffa) / suprapatellar 145.1; knee, other 88.4 |
| שוק | 33% | 28% / 5% | **20%** | 23 → 20 | 16% | 68% | intermuscular (leg) 181.3; pre-Achilles (Kager) 40.6; small slivers (< 4 mm2) 24.5 |
| כף רגל | 44% | 25% / 19% | **27%** | 32 → 17 | 60% | 35% | plantar / heel pad 853.8; foot, other 246.5; small slivers (< 4 mm2) 26.1 |
| זרוע | 30% | 22% / 7% | **15%** | 22 → 14 | 20% | 70% | intermuscular (arm) 155.1; axillary 121.2; small slivers (< 4 mm2) 28.6 |
| אמה | 27% | 17% / 10% | **18%** | 12 → 11 | 17% | 82% | intermuscular (forearm) 237.2; small slivers (< 4 mm2) 28.3 |
| כף יד ואצבעות | 35% | 20% / 15% | **31%** | 11 → 9 | 48% | 50% | palmar / digital 163.0; small slivers (< 4 mm2) 13.8 |

### Combined F

| אזור | חלל לפני | (תת-עורי / עמוק) | חלל אחרי | חור מרבי לפני → אחרי (מ"מ, דו-ממד) | שומן בחלל העמוק | רקמה רכה בחלל העמוק | מרחבים עמוקים עיקריים (סמ"ר, לפני) |
|---|---|---|---|---|---|---|---|
| ראש | 57% | 36% / 21% | **23%** | 64 → 23 | 6% | 78% | orbital 749.4; head, other 483.8; buccal / masticator 314.6 |
| צוואר | 67% | 47% / 20% | **18%** | 101 → 20 | 22% | 70% | carotid sheath / parapharyngeal 2098.8; posterior triangle / posterior neck 484.3; neck, other 475.4 |
| בית חזה | 36% | 19% / 18% | **13%** | 52 → 26 | 40% | 52% | mediastinal / pleural 2328.3; axillary 674.4; chest wall 563.1 |
| בטן | 53% | 20% / 33% | **15%** | 72 → 16 | 34% | 61% | retroperitoneal / perirenal 4784.7; abdominal wall / paravertebral 1240.2; intraperitoneal (mesenteric / omental) 210.8 |
| אגן | 63% | 31% / 32% | **12%** | 84 → 14 | 54% | 40% | pelvic visceral (perivesical / perirectal) 3030.1; gluteal intermuscular 1267.8; ischioanal fossa 871.2 |
| ירך | 52% | 45% / 7% | **8%** | 65 → 10 | 43% | 55% | thigh, deep 895.4; small slivers (< 4 mm2) 41.0 |
| ברך | 50% | 41% / 9% | **14%** | 39 → 17 | 28% | 57% | popliteal 383.4; infrapatellar (Hoffa) / suprapatellar 194.9; knee, other 51.2 |
| שוק | 30% | 24% / 6% | **13%** | 18 → 9 | 20% | 70% | intermuscular (leg) 194.9; pre-Achilles (Kager) 38.8; small slivers (< 4 mm2) 28.1 |
| כף רגל | 46% | 26% / 20% | **24%** | 46 → 12 | 16% | 48% | plantar / heel pad 530.0; foot, other 66.8; small slivers (< 4 mm2) 9.2 |
| זרוע | 57% | 49% / 8% | **20%** | 42 → 25 | 26% | 59% | intermuscular (arm) 352.6; axillary 173.8; small slivers (< 4 mm2) 16.7 |
| אמה | 70% | 62% / 8% | **21%** | 51 → 24 | 19% | 49% | intermuscular (forearm) 375.4; small slivers (< 4 mm2) 22.1 |
| כף יד ואצבעות | 72% | 64% / 8% | **18%** | 39 → 22 | 30% | 44% | palmar / digital 189.4; small slivers (< 4 mm2) 14.8 |

### Combined M

| אזור | חלל לפני | (תת-עורי / עמוק) | חלל אחרי | חור מרבי לפני → אחרי (מ"מ, דו-ממד) | שומן בחלל העמוק | רקמה רכה בחלל העמוק | מרחבים עמוקים עיקריים (סמ"ר, לפני) |
|---|---|---|---|---|---|---|---|
| ראש | 42% | 13% / 29% | **30%** | 34 → 24 | 42% | 50% | orbital 754.5; head, other 456.4; buccal / masticator 264.0 |
| צוואר | 49% | 22% / 27% | **25%** | 82 → 21 | 16% | 78% | carotid sheath / parapharyngeal 1820.6; posterior triangle / posterior neck 851.1; neck, other 833.7 |
| בית חזה | 34% | 14% / 20% | **15%** | 47 → 33 | 22% | 68% | mediastinal / pleural 3253.3; chest wall 548.3; axillary 373.2 |
| בטן | 55% | 19% / 36% | **24%** | 67 → 59 | 33% | 45% | retroperitoneal / perirenal 5465.8; abdominal wall / paravertebral 1389.0; intraperitoneal (mesenteric / omental) 817.3 |
| אגן | 55% | 26% / 29% | **18%** | 81 → 31 | 42% | 45% | pelvic visceral (perivesical / perirectal) 1680.6; gluteal intermuscular 1435.2; ischioanal fossa 995.4 |
| ירך | 50% | 37% / 12% | **14%** | 48 → 46 | 18% | 74% | thigh, deep 2103.0; small slivers (< 4 mm2) 40.9 |
| ברך | 45% | 30% / 15% | **18%** | 26 → 17 | 64% | 27% | popliteal 807.8; infrapatellar (Hoffa) / suprapatellar 339.4; knee, other 83.2 |
| שוק | 32% | 21% / 11% | **24%** | 20 → 15 | 14% | 68% | intermuscular (leg) 556.5; pre-Achilles (Kager) 30.9; small slivers (< 4 mm2) 23.2 |
| כף רגל | 40% | 19% / 21% | **21%** | 22 → 12 | 78% | 17% | plantar / heel pad 635.7; foot, other 147.2; small slivers (< 4 mm2) 15.2 |
| זרוע | 45% | 34% / 11% | **17%** | 34 → 18 | 23% | 64% | intermuscular (arm) 424.6; axillary 186.8; small slivers (< 4 mm2) 17.3 |
| אמה | 57% | 46% / 11% | **21%** | 41 → 14 | 17% | 81% | intermuscular (forearm) 545.6; small slivers (< 4 mm2) 25.7 |
| כף יד ואצבעות | 58% | 47% / 12% | **31%** | 34 → 15 | 48% | 49% | palmar / digital 177.5; small slivers (< 4 mm2) 17.6 |

**הערה על "חור מרבי" בדו-ממד:** חלק מהחורים הגדולים שנותרו (למשל ~10 ס"מ מתחת לכיפת הסרעפת ב-Imaging F) הם רצועה דקה (2–4 מ"מ) שהמישור הצירי חותך בזווית משיקית; בתלת-ממד עובייה קטן (טבלה 5).

## 4. מה נשלח (מערכת חדשה: "Fat & unlabelled soft tissue")

לכל עמוד 51 רשתות: שומן תת-עורי ושומן עמוק לכל אחד מ-17 חלקי גוף (ראש, צוואר, בית חזה, בטן, אגן, ולכל צד: זרוע, אמה, כף יד, ירך, שוק, כף רגל), ו"רקמה רכה לא מסווגת" לכל חלק. מערכת נפרדת עם מתג, **דלילה כברירת מחדל (12% אטימות)** כדי לא להסתיר — אבל **במילוי פני החתך (Fill cross-section, חתכים מרובים) היא נצבעת אטומה**. בכלי ההדמיה (CT/MRI/US): השומן ממופה למחלקת fat, הרקמה הרכה הלא מסווגת ל-soft_unassigned.

| עמוד | שומן תת-עורי (סמ"ק) | שומן עמוק (סמ"ק) | רקמה רכה לא מסווגת (סמ"ק) | משולשים | זווית דו-שטחית ממוצעת (°) | שיעור קצוות פגומים | רישום |
|---|---|---|---|---|---|---|---|
| Imaging F (הדמיה, אישה) | 31928 | 1934 | 4114 | 584,521 | 32.0 / 30.0 / 28.2 | 0.0051 | ללא העברה (אותו פריים) |
| Imaging M (הדמיה, גבר) | 19538 | 1985 | 8660 | 604,201 | 35.0 / 31.3 / 37.0 | 0.0102 | ללא העברה (אותו פריים) |
| Base F | 9303 | 2285 | 5044 | 575,528 | 22.2 / 29.2 / 27.1 | 0.0009 | TPS ל-Combined |
| Base M | 6568 | 2344 | 5797 | 629,954 | 20.8 / 30.1 / 28.9 | 0.0020 | TPS ל-Combined |
| Combined F | 19184 | 4905 | 8432 | 605,313 | 26.3 / 30.2 / 32.1 | 0.0050 | ללא העברה (אותו פריים) |
| Combined M | 13595 | 4085 | 10356 | 603,699 | 27.4 / 33.1 / 36.3 | 0.0031 | ללא העברה (אותו פריים) |

אמיתיות הרשת: זווית דו-שטחית ממוצעת מול רשתות CVH (‏31.7°, 27.6°, 29.5°). הרשתות נבנו ב-marching cubes מצעד 4–5 מ"מ כדי לעמוד בתקציב המשולשים בלי דצימציה ככל האפשר (דצימציה משאירה קצוות לא-מניפולדיים שמילוי פני החתך צריך לתקן).

**חדירה:** השומן חתוך לחלל שהעמוד משאיר ריק, ולכן אינו נכנס לשרירים/עצמות/איברים; נמדד בחתכים כחלק משטח השומן שמבנה אחר (לא שומן) מכסה גם הוא:

| עמוד | ראש | צוואר | בית חזה | בטן | אגן | ירך | ברך | שוק | כף רגל | זרוע | אמה | כף יד ואצבעות |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Imaging F (הדמיה, אישה) | 2% | 1% | 4% | 1% | 1% | 0% | 1% | 1% | 1% | 1% | 1% | 1% |
| Imaging M (הדמיה, גבר) | 5% | 12% | 4% | 2% | 2% | 1% | 2% | 0% | 6% | 1% | 7% | 2% |
| Base F | 6% | 2% | 2% | 3% | 2% | 2% | 2% | 2% | 3% | 2% | 2% | 4% |
| Base M | 4% | 2% | 3% | 2% | 1% | 1% | 2% | 1% | 4% | 2% | 4% | 7% |
| Combined F | 3% | 1% | 3% | 4% | 2% | 1% | 1% | 2% | 3% | 1% | 1% | 2% |
| Combined M | 5% | 3% | 3% | 3% | 3% | 2% | 3% | 2% | 7% | 2% | 2% | 2% |

## 5. מה נשאר ריק, ולמה (תלת-ממד, על ווקסלים של 1 מ"מ)

| עמוד | נפח גוף (ל') | חלל לפני (ל') | שומן בהדמיה (ל') | רקמה רכה בהדמיה (ל') | הושאר: רצועות שומן דקות (ל') | הושאר: רצועות רקמה רכה דקות (ל') | עובי ≤4 מ"מ | 4–6 | >6 | גז/לומן (ל') | מחוץ להדמיה (ל') |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Imaging F (הדמיה, אישה) | 85.4 | 50.4 | 35.4 | 14.4 | 3.2 | 9.4 | 12.1 | 0.45 | 0.04 | 0.14 | 0.46 |
| Imaging M (הדמיה, גבר) | 103.9 | 56.0 | 27.7 | 25.7 | 4.0 | 13.8 | 17.2 | 0.64 | 0.03 | 2.48 | 0.21 |
| Base F | 59.3 | 24.9 | 14.4 | 10.4 | 1.8 | 4.4 | 6.1 | 0.19 | 0.02 | 0.00 | 0.07 |
| Base M | 72.0 | 28.2 | 12.9 | 13.4 | 2.0 | 5.8 | 7.6 | 0.20 | 0.01 | 1.89 | 0.06 |
| Combined F | 86.1 | 47.1 | 30.1 | 16.4 | 2.4 | 6.3 | 8.4 | 0.28 | 0.02 | 0.12 | 0.51 |
| Combined M | 94.3 | 45.6 | 21.8 | 20.8 | 2.4 | 7.9 | 10.0 | 0.28 | 0.01 | 2.89 | 0.19 |

"גז/לומן": אישה — HU < ‎−400 בתוך הגוף (ריאה/מעי); גבר — פיקסלים כהים בתוך הצללית בצילום (דם, כליה, ג'לטין כחול במעי) — לא שומן. "מחוץ להדמיה" — מחוץ לשדה הראייה של ה-CT שלה (בעיקר הזרוע השמאלית) או מעבר ל-20 מ"מ מהרקמה המצולמת הקרובה.

## 6. רקמה חסרה / פילוח שגוי — מה עמוד ההדמיה של אותו גוף מפלח בחללים של עמודי Z

בחללי "רקמה רכה" של עמודי Combined/Base, הנקודה המקבילה בעמוד ההדמיה של אותו גוף (הפילוחים שלו מה-CT/צילומים) — 5 הראשונים לכל חלק (סמ"ק):

**Combined F:**

- pelvis: (nothing segmented there either) 576.7; Gluteus maximus [muscle] 471.3; Small bowel (jejunum and ileum) [organ] 377.5; Hip bone [bone] 149.8; Sacrum [bone] 75.0
- foot_r: (nothing segmented there either) 182.4; Calcaneus (heel bone) [bone] 28.9; Metatarsals (5) [bone] 24.1; Talus (ankle bone) [bone] 8.2; Cuboid [bone] 7.5
- foot_l: (nothing segmented there either) 152.3; Calcaneus (heel bone) [bone] 28.5; Metatarsals (5) [bone] 22.3; Talus (ankle bone) [bone] 8.6; Cuboid [bone] 6.3
- leg_r: (nothing segmented there either) 115.9; Soleus [muscle] 35.4; Tibia (shin bone) [bone] 18.5; Fibularis (peroneus) longus [muscle] 17.9; Flexor hallucis longus [muscle] 17.8
- leg_l: (nothing segmented there either) 118.2; Soleus [muscle] 24.3; Tibia (shin bone) [bone] 23.0; Flexor hallucis longus [muscle] 19.0; Tibialis posterior [muscle] 13.8
- thigh_r: (nothing segmented there either) 391.3; Biceps femoris [muscle] 116.3; Vastus lateralis [muscle] 99.6; Semitendinosus [muscle] 95.3; Semimembranosus [muscle] 92.5
- thigh_l: (nothing segmented there either) 333.6; Semimembranosus [muscle] 97.1; Semitendinosus [muscle] 95.6; Biceps femoris [muscle] 91.5; Gluteus maximus [muscle] 74.8
- hand_r: (nothing segmented there either) 95.3; Finger/thumb phalanges (14: thumb x2, fingers x3 each) [bone] 7.8; Tensor fasciae latae [muscle] 6.6; Carpal bones (8, proximal+distal row) [bone] 4.5; Adductor pollicis [muscle] 3.6
- hand_l: (nothing segmented there either) 144.7; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 4.5; Palmaris longus [muscle] 3.0; Small bowel (jejunum and ileum) [organ] 2.1; Carpal bones (8, proximal+distal row) [bone] 1.3
- forearm_r: (nothing segmented there either) 289.6; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 70.0; Antebrachial (deep) fascia of the forearm [fascia] 39.2; Flexor carpi radialis [muscle] 17.5; Internal oblique [muscle] 14.3
- forearm_l: (nothing segmented there either) 334.3; External oblique [muscle] 19.4; Flexor carpi ulnaris [muscle] 17.2; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 16.5; Flexor digitorum superficialis [muscle] 11.1
- abdomen: (nothing segmented there either) 958.8; Liver [organ] 754.0; Stomach (wall and contents) [organ] 498.4; Small bowel (jejunum and ileum) [organ] 290.1; Left kidney [organ] 184.0
- upper_arm_r: (nothing segmented there either) 485.1; Deltoid [muscle] 38.8; Biceps brachii [muscle] 32.9; Brachialis [muscle] 25.0; Humerus [bone] 21.2
- upper_arm_l: (nothing segmented there either) 520.9; Triceps brachii [muscle] 65.6; Deltoid [muscle] 43.7; Brachialis [muscle] 32.0; Humerus [bone] 30.6
- thorax: (nothing segmented there either) 323.1; Heart (four chambers and myocardium, blood-filled) [organ] 171.6; Pectoralis major [muscle] 107.3; External intercostals [muscle] 80.9; Latissimus dorsi [muscle] 57.7
- neck: (nothing segmented there either) 605.8; Trapezius [muscle] 124.9; Subscapularis [muscle] 87.8; Infraspinatus [muscle] 43.0; Supraspinatus [muscle] 28.8
- head: (nothing segmented there either) 970.5; Skull without the mandible -- composite of the individual cranial and facial bones, which remain separate entities [bone] 318.8; Brain [organ] 164.8; Semispinalis capitis [muscle] 34.3; Cervical vertebrae [bone] 30.1

**Combined M:**

- foot_r: (nothing segmented there either) 95.5; Plantar aponeurosis (fascia) [fascia] 10.0; Abductor hallucis [muscle] 4.7; Flexor digitorum brevis [muscle] 4.6; (Superior + inferior) fibular (peroneal) retinaculum [fascia] 4.3
- foot_l: (nothing segmented there either) 116.0; Flexor digitorum brevis [muscle] 8.0; Metatarsals (5) [bone] 7.1; Abductor hallucis [muscle] 3.9; Adductor hallucis [muscle] 2.7
- pelvis: (nothing segmented there either) 815.4; Gluteus maximus [muscle] 345.7; Iliopsoas (iliacus + psoas major) [muscle] 107.4; Hip bone [bone] 90.9; Obturator internus [muscle] 78.7
- leg_r: (nothing segmented there either) 379.9; Soleus [muscle] 72.9; Gastrocnemius [muscle] 37.5; Tibialis posterior [muscle] 37.3; Fibularis (peroneus) longus [muscle] 34.0
- leg_l: (nothing segmented there either) 432.2; Soleus [muscle] 113.5; Gastrocnemius [muscle] 59.3; Tibialis posterior [muscle] 52.3; Fibularis (peroneus) longus [muscle] 35.2
- thigh_r: (nothing segmented there either) 591.9; Vastus intermedius [muscle] 312.4; Vastus lateralis [muscle] 238.1; Gluteus maximus [muscle] 194.2; Vastus medialis [muscle] 152.4
- thigh_l: (nothing segmented there either) 729.2; Vastus lateralis [muscle] 355.5; Vastus intermedius [muscle] 277.1; Gluteus maximus [muscle] 184.2; Vastus medialis [muscle] 174.1
- hand_l: (nothing segmented there either) 98.9; Sartorius [muscle] 10.0; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 8.0; External oblique (continuation beyond the data-block cut, filled from Z-Anatomy) [muscle] 6.4; Rectus abdominis [muscle] 6.2
- hand_r: (nothing segmented there either) 154.0; Rectus abdominis [muscle] 11.8; Rectus abdominis (continuation beyond the data-block cut, filled from Z-Anatomy) [muscle] 8.3; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 6.6; Sartorius [muscle] 3.2
- forearm_r: (nothing segmented there either) 588.0; Brachioradialis [muscle] 40.6; External oblique [muscle] 38.8; Flexor digitorum superficialis [muscle] 12.1; Flexor digitorum profundus [muscle] 9.8
- forearm_l: (nothing segmented there either) 457.9; Transversus abdominis [muscle] 30.6; Internal oblique [muscle] 30.2; External oblique [muscle] 28.2; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 9.2
- abdomen: (nothing segmented there either) 2164.3; Small bowel (jejunum and ileum) [organ] 187.3; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 163.9; External intercostals [muscle] 122.2; Latissimus dorsi [muscle] 117.5
- upper_arm_r: (nothing segmented there either) 585.2; Triceps brachii [muscle] 105.1; Biceps brachii [muscle] 87.9; Deltoid [muscle] 53.5; Brachialis [muscle] 31.7
- upper_arm_l: (nothing segmented there either) 500.9; Triceps brachii [muscle] 116.1; Biceps brachii [muscle] 76.0; Deltoid [muscle] 32.6; Brachialis [muscle] 28.3
- thorax: (nothing segmented there either) 907.7; External intercostals [muscle] 186.8; Triceps brachii [muscle] 123.3; Serratus anterior [muscle] 100.2; Subscapularis [muscle] 75.8
- neck: (nothing segmented there either) 1105.7; Trapezius [muscle] 146.5; Subscapularis [muscle] 99.5; External intercostals [muscle] 67.4; Rhomboid minor [muscle] 51.6
- head: (nothing segmented there either) 394.0; Skull without the mandible -- composite of the individual cranial and facial bones, which remain separate entities [bone] 86.4; Temporalis [muscle] 21.8; Masseter [muscle] 18.2; Cervical vertebrae [bone] 16.5

**Base F:**

- pelvis: (nothing segmented there either) 460.3; Gluteus maximus [muscle] 336.5; Small bowel (jejunum and ileum) [organ] 323.6; Hip bone [bone] 78.0; Sacrum [bone] 75.1
- foot_r: (nothing segmented there either) 122.3; Calcaneus (heel bone) [bone] 23.3; Metatarsals (5) [bone] 21.7; Talus (ankle bone) [bone] 5.7; Cuboid [bone] 3.9
- foot_l: (nothing segmented there either) 143.7; Calcaneus (heel bone) [bone] 27.7; Metatarsals (5) [bone] 22.4; Talus (ankle bone) [bone] 6.9; Cuboid [bone] 4.8
- leg_r: (nothing segmented there either) 115.9; Soleus [muscle] 32.2; Fibularis (peroneus) longus [muscle] 29.6; Flexor hallucis longus [muscle] 16.0; Tibia (shin bone) [bone] 12.9
- leg_l: (nothing segmented there either) 153.8; Soleus [muscle] 24.1; Fibularis (peroneus) longus [muscle] 17.0; Flexor hallucis longus [muscle] 16.5; Tibia (shin bone) [bone] 14.1
- thigh_r: (nothing segmented there either) 270.6; Biceps femoris [muscle] 87.4; Semitendinosus [muscle] 76.5; Adductor magnus [muscle] 68.2; Vastus lateralis [muscle] 55.3
- thigh_l: (nothing segmented there either) 258.1; Vastus lateralis [muscle] 94.9; Semitendinosus [muscle] 74.9; Semimembranosus [muscle] 71.4; Biceps femoris [muscle] 67.4
- hand_r: (nothing segmented there either) 31.8; Adductor pollicis [muscle] 4.8; Finger/thumb phalanges (14: thumb x2, fingers x3 each) [bone] 4.0; Opponens digiti minimi [muscle] 2.9; Abductor digiti minimi (hand) [muscle] 2.4
- hand_l: (nothing segmented there either) 32.8; Carpal bones (8, proximal+distal row) [bone] 2.5; Adductor pollicis [muscle] 2.0; Palmaris longus [muscle] 1.8; Finger/thumb phalanges (14: thumb x2, fingers x3 each) [bone] 1.1
- forearm_l: (nothing segmented there either) 84.4; External oblique [muscle] 18.3; Transversus abdominis [muscle] 14.7; Internal oblique [muscle] 14.3; Flexor carpi ulnaris [muscle] 6.4
- forearm_r: (nothing segmented there either) 73.5; Antebrachial (deep) fascia of the forearm [fascia] 32.1; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 16.3; External oblique [muscle] 10.4; Flexor carpi radialis [muscle] 8.4
- abdomen: (nothing segmented there either) 641.1; Liver [organ] 414.5; Stomach (wall and contents) [organ] 343.4; Small bowel (jejunum and ileum) [organ] 198.6; Left kidney [organ] 153.9
- upper_arm_r: (nothing segmented there either) 148.6; Biceps brachii [muscle] 14.7; Brachialis [muscle] 14.7; Triceps brachii [muscle] 12.5; Deltoid [muscle] 11.0
- upper_arm_l: (nothing segmented there either) 124.2; Triceps brachii [muscle] 29.7; Brachialis [muscle] 23.3; Deltoid [muscle] 18.3; Biceps brachii [muscle] 9.9
- thorax: (nothing segmented there either) 236.0; Heart (four chambers and myocardium, blood-filled) [organ] 131.9; Pectoralis major [muscle] 80.1; External intercostals [muscle] 42.0; Thoracic vertebrae [bone] 37.9
- neck: (nothing segmented there either) 329.6; Trapezius [muscle] 114.9; Subscapularis [muscle] 46.7; Cervical vertebrae [bone] 28.5; Clavicle [bone] 21.9
- head: (nothing segmented there either) 298.9; Skull without the mandible -- composite of the individual cranial and facial bones, which remain separate entities [bone] 266.5; Brain [organ] 144.9; Cervical vertebrae [bone] 27.7; Temporalis [muscle] 19.8

**Base M:**

- pelvis: (nothing segmented there either) 812.0; Gluteus maximus [muscle] 237.7; Iliopsoas (iliacus + psoas major) [muscle] 98.0; Obturator internus [muscle] 70.0; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 65.1
- foot_r: (nothing segmented there either) 116.8; Plantar aponeurosis (fascia) [fascia] 9.9; Abductor hallucis [muscle] 6.5; Flexor digitorum brevis [muscle] 5.6; Abductor digiti minimi (foot) [muscle] 2.7
- foot_l: (nothing segmented there either) 132.7; Flexor digitorum brevis [muscle] 8.4; Metatarsals (5) [bone] 6.2; Abductor hallucis [muscle] 5.4; Adductor hallucis [muscle] 2.3
- leg_r: (nothing segmented there either) 484.7; Soleus [muscle] 55.5; Fibularis (peroneus) longus [muscle] 34.4; Extensor digitorum longus [muscle] 20.0; Gastrocnemius [muscle] 18.0
- leg_l: (nothing segmented there either) 451.8; Soleus [muscle] 75.0; Gastrocnemius [muscle] 35.3; Fibularis (peroneus) longus [muscle] 31.7; Extensor digitorum longus [muscle] 16.1
- thigh_r: (nothing segmented there either) 418.4; Vastus lateralis [muscle] 296.4; Rectus femoris [muscle] 159.2; Gluteus maximus [muscle] 96.1; Biceps femoris [muscle] 92.5
- thigh_l: (nothing segmented there either) 466.3; Vastus lateralis [muscle] 276.1; Rectus femoris [muscle] 143.6; Vastus intermedius [muscle] 141.3; Gluteus maximus [muscle] 108.9
- hand_l: (nothing segmented there either) 43.6; Metacarpals (5) [bone] 5.1; Adductor pollicis [muscle] 1.4; Palmaris longus [muscle] 1.1; Finger/thumb phalanges (14: thumb x2, fingers x3 each) [bone] 1.0
- hand_r: (nothing segmented there either) 48.9; Adductor pollicis [muscle] 1.2; Finger/thumb phalanges (14: thumb x2, fingers x3 each) [bone] 1.1; Metacarpals (5) [bone] 0.9; Rectus femoris [muscle] 0.5
- forearm_r: (nothing segmented there either) 150.8; Radius [bone] 13.7; Brachioradialis [muscle] 11.9; Flexor pollicis longus [muscle] 6.0; Ulna [bone] 5.7
- forearm_l: (nothing segmented there either) 116.0; Brachioradialis [muscle] 12.3; Flexor digitorum profundus [muscle] 10.8; Flexor digitorum superficialis [muscle] 10.7; Pronator teres [muscle] 9.5
- abdomen: (nothing segmented there either) 1380.7; Liver [organ] 137.6; Colon above the pelvic inlet (the pelvic sigmoid and rectum are separate structures) [organ] 95.4; Latissimus dorsi [muscle] 90.8; Small bowel (jejunum and ileum) [organ] 90.0
- upper_arm_r: (nothing segmented there either) 229.1; Biceps brachii [muscle] 35.1; Triceps brachii [muscle] 34.8; Deltoid [muscle] 16.4; Brachialis (continuation beyond the data-block seam, filled from Z-Anatomy) [muscle] 15.1
- upper_arm_l: (nothing segmented there either) 249.3; Biceps brachii [muscle] 33.0; Triceps brachii [muscle] 27.0; Brachialis [muscle] 16.8; Deltoid [muscle] 10.7
- thorax: (nothing segmented there either) 835.6; Triceps brachii [muscle] 95.1; External intercostals [muscle] 93.6; Left lung [organ] 88.4; Heart (four chambers and myocardium, blood-filled) [organ] 85.8
- neck: (nothing segmented there either) 467.7; Trapezius [muscle] 177.6; Sternocleidomastoid [muscle] 20.8; Subscapularis [muscle] 20.7; Levator scapulae [muscle] 19.5
- head: (nothing segmented there either) 305.9; Skull without the mandible -- composite of the individual cranial and facial bones, which remain separate entities [bone] 80.2; Temporalis [muscle] 23.8; Masseter [muscle] 18.2; Brain [organ] 16.3

פירוש: כשהמבנה המופיע הוא שריר/איבר (למשל המעי הדק בבטן של Combined F, המוח בראש, gluteus maximus באגן) — זו **רקמה חסרה או מוזזת בגוף ה-Z** (ב/ג); כשמופיעה עצם — עצם ה-Z לא יושבת בדיוק על עצם ה-CT (ג); "nothing segmented there either" — גם עמוד ההדמיה לא מפלח שם דבר (פסציה, כלי דם קטנים, בלוטות לימפה, דרמיס).

## 7. מונטאז'ים

לכל עמוד: לפני / אחרי — `data/derived/Q295_montages/<page>_before.jpg`, `<page>_after.jpg` (תכלת = חלל תת-עורי, ורוד = חלל עמוק, אדום = מבנה, זהב = חפיפה, שמנת = שומן Q295, סגול-לילך = רקמה רכה לא מסווגת).

## 8. מה עדיין חסר

- רצועות של 2–4 מ"מ בין מבנים (גבולות פילוח לא תואמים בין המבנים להדמיה) לא מולאו — מכוון, כדי לא לייצר אלפי שבבים.
- "רקמה רכה לא מסווגת" אינה מבנה אנטומי: היא מסמנת רקמה שחסרה בעמוד. החלפתה במבנים אמיתיים (למשל המעי הדק של ה-CT שלה ב-Combined F, שרירים קטנים בכף היד והרגל, פסציות) — לסבבים הבאים.
- Base: הגוף הגנרי אינו האדם; השומן שלו הוא דפוס השומן של האדם המצולם שהועבר ברישום (שארית חציונית ~2 מ"מ).
- הגבר: ה-CT הקפוא לא מפריד שומן; השתמשנו בצבע. העור הלבן בצילום מסווג "עצם" ומוחלף בשכן הקרוב.
- שומן מח העצם לא נשלח כרשת (אופציונלי); הוא מיוצג במודל העצם של כלי ההדמיה.

## 9. עמודים

- Imaging F (הדמיה, אישה): https://claude.ai/artifact/1nFD1WUQ7jyovz9vx9pn77
- Imaging M (הדמיה, גבר): https://claude.ai/artifact/RRkf5ELjmk6E8iHdgfbTtq
- Base M: https://claude.ai/artifact/HdYCRuvGP8ESbggoRWCNBF
- Base F: https://claude.ai/artifact/TiXsQe3eS5ehzN64Aozyth
- Combined M: https://claude.ai/artifact/FeFFPVVTEnPkDm2r7TyDFz
- Combined F: https://claude.ai/artifact/1GEpFSCZexGZ1GnM1pXxuP
