# Q250 - female / male indicators, before and after

Measures: the Q233 landmark rules (`scripts/anatomy/q233/dimorphism.py`) on the meshes of each page, body measures (`body_measures.py`). Reference: **women, n = 47 CT cases of the TotalSegmentator dataset v2.0.1 (CC BY 4.0) measured with the SAME rules** (mean +- SD), plus PubMed-verified numbers where one exists. Verdict column: Q250 page vs the women range.

| indicator | Base M | Base F (before Q250) | Base F (Q250) | Combined F (before Q250) | Combined F (Q250) | Imaging-based F (her own CT) | Imaging-based M (his own CT) | women (CT, n=47) mean +- SD | literature |
|---|---|---|---|---|---|---|---|---|---|
| Subpubic angle (angle between the ischiopubic rami) [deg] | 57.2 | 57.2 | 85.1 | 62.7 | 83.9 | 87.3 | 70.7 | 83.4 +- 9.8 | CT, 50 M / 50 F: male 68.6 +- 7.6, female 87.4 +- 6.5, cut-off 78.6 deg (Mohd Ali et al. 2020, PMID 32274246, verified abstract) |
| Pelvic inlet index (AP conjugate / transverse diameter x 100) [%] | 60.7 | 60.6 | 83.3 | 67.0 | 81.0 | 76.0 | 66.9 | 93.2 +- 9.8 | direction only: male pelvic inlet shorter (PMID 21136101); no number read |
| Pelvic outlet width (intertuberous distance) [mm] | 86.5 | 86.5 | 127.1 | 112.3 | 119.5 | 119.5 | 103.5 | 106.3 +- 13.4 | direction only: transverse outlet among the most dimorphic measures (PMID 24789357, 42793678) |
| Greater sciatic notch, hull-defect angle on dense surface samples [deg] | 97.8 | 97.8 | 93.2 | 96.2 | 90.5 | 93.2 | 98.5 | 99.3 +- 5.5 | direction only (wider in women: PMID 39623825, 34554326); NOT diagnostic by this method (male donor 98.5, female donor 93.2, women 98 +- 6) |
| Sacral index (breadth of upper half / straight length x 100) [%] | 107.1 | 107.1 | 113.3 | 112.1 | 110.9 | 105.8 | 91.0 | 106.0 +- 10.8 | direction only: higher in women (PMID 37284374; caveat PMID 35385483: weakly dimorphic) |
| Bi-iliac breadth of the hip bones [mm] | 269.8 | 269.8 | 299.7 | 290.4 | 296.7 | 296.2 | 280.2 | 280.8 +- 17.4 | women have the wider pelvis relative to the shoulders (PMID 36628541); no number read |
| Pelvic breadth / height of the hip bones [%] | 125.7 | 125.7 | 141.8 | 133.1 | 138.7 | 138.6 | 130.2 | 134.7 +- 7.3 |  |
| Distance between the femoral head centres [mm] | 171.0 | 171.0 | 197.0 | 208.8 | 208.8 | 195.7 | 181.4 | 176.0 +- 8.9 |  |
| Biacromial / bi-iliac ratio (scapula + clavicle extent over hip-bone breadth) | 1.287 | 1.287 | 1.054 | 1.09 | 1.067 | 1.106 | 1.37 | - | males have broader shoulders and narrower hips than females (PMID 36628541); no number read |
| Clavicle length [mm] | 160.3 | 160.3 | 151.5 | 140.4 | 140.4 | 142.1 | 165.1 | - | male clavicles larger: dry bone, 60 M / 60 F, max length significant (PMID 41960515); no number read |
| Rib-cage width [mm] | 283.0 | 283.0 | 270.0 | 275.0 | 275.0 | None | None | - | thoracic bones dimorphic: rib width, sternum, clavicle (CT, 240 adults; PMID 39382593); no number read |
| Femoral head diameter [mm] | 51.3 | 51.3 | 46.9 | 45.8 | 45.8 | 47.2 | 48.7 | 44.4 +- 2.6 | smaller in women (PMID 37803256, 40547822); population-dependent absolute values |
| Femoral bicondylar breadth [mm] | 84.5 | 84.5 | 78.4 | 78.7 | 78.7 | 81.7 | 91.4 | 71.8 +- 6.8 | direction only |
| Femur length / stature [%] | 26.69 | 26.69 | 25.75 | 24.53 | 24.53 | None | None | - | UNVERIFIED: no number read |
| Head height / stature [%] | 12.23 | 12.23 | 12.29 | 12.0 | 12.0 | None | None | - | UNVERIFIED: no number read |
| Stature (skin extent) [mm] | 1710.0 | 1710.0 | 1644.0 | 1733.0 | 1733.0 | None | None | - | UNVERIFIED: adult women about 1.6-1.65 m in most populations (no number read here) |
| Waist / hip skin breadth ratio | 0.842 | 0.842 | 0.83 | 0.774 | 0.776 | None | None | - | UNVERIFIED as a body-breadth ratio; waist-hip CIRCUMFERENCE ratio thresholds women 0.85 / men 0.90 are screening cut-offs, not means (PMID 36235677) |
| Q angle proxy (bone landmarks, supine / standing pose dependent) [deg] | 0.7 | 0.7 | 0.3 | 37.2 | 37.0 | 36.0 | 7.8 | - | female 13.7 +- 1.9 vs male 11.1 +- 1.9 (PMID 36713821); NOT measurable from skeleton meshes in a non-weight-bearing pose (Q233) |

## Verdicts of the Q250 pages

**Base F (Q250)**
- Subpubic angle (angle between the ischiopubic rami) [deg]: 85.1 -> female (>= 78.6 cut-off)
- Pelvic inlet index (AP conjugate / transverse diameter x 100) [%]: 83.3 -> within women mean +- 2 SD
- Pelvic outlet width (intertuberous distance) [mm]: 127.1 -> within women mean +- 2 SD
- Greater sciatic notch, hull-defect angle on dense surface samples [deg]: 93.2 -> within women mean +- 2 SD
- Sacral index (breadth of upper half / straight length x 100) [%]: 113.3 -> within women mean +- 2 SD
- Bi-iliac breadth of the hip bones [mm]: 299.7 -> within women mean +- 2 SD
- Pelvic breadth / height of the hip bones [%]: 141.8 -> within women mean +- 2 SD
- Distance between the femoral head centres [mm]: 197.0 -> above women range
- Femoral head diameter [mm]: 46.9 -> within women mean +- 2 SD
- Femoral bicondylar breadth [mm]: 78.4 -> within women mean +- 2 SD

**Combined F (Q250)**
- Subpubic angle (angle between the ischiopubic rami) [deg]: 83.9 -> female (>= 78.6 cut-off)
- Pelvic inlet index (AP conjugate / transverse diameter x 100) [%]: 81.0 -> within women mean +- 2 SD
- Pelvic outlet width (intertuberous distance) [mm]: 119.5 -> within women mean +- 2 SD
- Greater sciatic notch, hull-defect angle on dense surface samples [deg]: 90.5 -> within women mean +- 2 SD
- Sacral index (breadth of upper half / straight length x 100) [%]: 110.9 -> within women mean +- 2 SD
- Bi-iliac breadth of the hip bones [mm]: 296.7 -> within women mean +- 2 SD
- Pelvic breadth / height of the hip bones [%]: 138.7 -> within women mean +- 2 SD
- Distance between the femoral head centres [mm]: 208.8 -> above women range
- Femoral head diameter [mm]: 45.8 -> within women mean +- 2 SD
- Femoral bicondylar breadth [mm]: 78.7 -> within women mean +- 2 SD

**Base F (before Q250)**
- Subpubic angle (angle between the ischiopubic rami) [deg]: 57.2 -> male range (< 78.6 cut-off)
- Pelvic inlet index (AP conjugate / transverse diameter x 100) [%]: 60.6 -> below women range
- Pelvic outlet width (intertuberous distance) [mm]: 86.5 -> within women mean +- 2 SD
- Greater sciatic notch, hull-defect angle on dense surface samples [deg]: 97.8 -> within women mean +- 2 SD
- Sacral index (breadth of upper half / straight length x 100) [%]: 107.1 -> within women mean +- 2 SD
- Bi-iliac breadth of the hip bones [mm]: 269.8 -> within women mean +- 2 SD
- Pelvic breadth / height of the hip bones [%]: 125.7 -> within women mean +- 2 SD
- Distance between the femoral head centres [mm]: 171.0 -> within women mean +- 2 SD
- Femoral head diameter [mm]: 51.3 -> above women range
- Femoral bicondylar breadth [mm]: 84.5 -> within women mean +- 2 SD

**Combined F (before Q250)**
- Subpubic angle (angle between the ischiopubic rami) [deg]: 62.7 -> male range (< 78.6 cut-off)
- Pelvic inlet index (AP conjugate / transverse diameter x 100) [%]: 67.0 -> below women range
- Pelvic outlet width (intertuberous distance) [mm]: 112.3 -> within women mean +- 2 SD
- Greater sciatic notch, hull-defect angle on dense surface samples [deg]: 96.2 -> within women mean +- 2 SD
- Sacral index (breadth of upper half / straight length x 100) [%]: 112.1 -> within women mean +- 2 SD
- Bi-iliac breadth of the hip bones [mm]: 290.4 -> within women mean +- 2 SD
- Pelvic breadth / height of the hip bones [%]: 133.1 -> within women mean +- 2 SD
- Distance between the femoral head centres [mm]: 208.8 -> above women range
- Femoral head diameter [mm]: 45.8 -> within women mean +- 2 SD
- Femoral bicondylar breadth [mm]: 78.7 -> within women mean +- 2 SD

