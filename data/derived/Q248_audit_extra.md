## 5. What Q248 added, per page

`transferred` = Z-Anatomy structure carried onto the own bones (own pages only; the Z pages already hold the Z structures), `rule-based` = built from the page's bones / organs (all six pages), `CVH` = Chinese Visible Human anococcygeal ligament (female own page). Ship diff: every other structure of the page is byte for byte the Q244 page (`data/derived/Q248_vertex_diff_<page>.json`, 0 unlisted).

| Page | transferred | rule-based | CVH | total added | triangles added |
|---|---|---|---|---|---|
| Imaging-based F | 86 | 7 | 1 | 94 | 43802 |
| Combined F | 0 | 10 | 0 | 10 | 6720 |
| Base F | 0 | 8 | 0 | 8 | 5568 |
| Imaging-based M | 79 | 14 | 0 | 93 | 39170 |
| Combined M | 0 | 9 | 0 | 9 | 6144 |
| Base M | 0 | 8 | 0 | 8 | 5568 |

## 6. Rule-based ligaments: numbers per page

Length = path length; cross-section = width x thickness (mm; the calibre is a MODELLING CHOICE except where a card says otherwise); volume = closed mesh; attachment = signed distance of the two end-cap centres to the attachment surface (bone, 0 = on the surface); 'deeper than 1 mm' = vertices more than 1 mm inside a bone after the push-out (0 required); soft overlap = fraction of vertices deeper than 6 mm inside a closed muscle / 3 mm inside an organ (gated on the Imaging-based pages, reported on the Z pages).

| Page | id | length mm | cross-section mm | volume cm3 | attachment a / b mm | deeper 1 mm | soft overlap muscle / organ | skin depth mm |
|---|---|---|---|---|---|---|---|---|
| Imaging-based F | tendinous_arch_levator_ani_l | 67.9 | 5.0 x 1.5 | 0.3813 | 0.0 / -0.0 | 0 | 0.025 / 0.0 | 64.3 |
| Imaging-based F | tendinous_arch_levator_ani_r | 72.0 | 5.0 x 1.5 | 0.405 | 0.0 / 0.0 | 0 | 0.075 / 0.0 | 64.5 |
| Imaging-based F | arcus_tendineus_fasciae_pelvis_r | 76.8 | 5.0 x 1.5 | 0.4322 | 0.0 / -0.0 | 0 | 0.12 / 0.0 | 61.3 |
| Imaging-based F | transverse_perineal_ligament | 16.4 | 8.0 x 2.0 | 0.1627 | 0.0 / -0.0 | 0 | 0.01 / 0.0 | 33.8 |
| Imaging-based F | patellar_ligament_r | 34.2 | 24.0-30.0 x 5.0 | 3.4631 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 2.9 |
| Imaging-based F | iliolumbar_ligament_l | 13.4 | 12.0 x 3.0 | 0.3613 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 66.9 |
| Imaging-based F | iliolumbar_ligament_r | 14.3 | 12.0 x 3.0 | 0.3848 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 70.5 |
| Combined F | tendinous_arch_levator_ani_l | 75.1 | 5.0 x 1.5 | 0.4204 | 0.0 / 0.0 | 0 | 0.185 / 0.0 | 45.6 |
| Combined F | arcus_tendineus_fasciae_pelvis_l | 77.6 | 5.0 x 1.5 | 0.4363 | 0.0 / 0.0 | 0 | 0.21 / 0.083 | 40.3 |
| Combined F | tendinous_arch_levator_ani_r | 75.6 | 5.0 x 1.5 | 0.4224 | 0.0 / 0.0 | 0 | 0.241 / 1.0 | 48.4 |
| Combined F | arcus_tendineus_fasciae_pelvis_r | 86.3 | 5.0 x 1.5 | 0.4824 | 0.0 / -0.0 | 0 | 0.293 / 0.936 | 37.3 |
| Combined F | transverse_perineal_ligament | 42.0 | 8.0 x 2.0 | 0.475 | 0.0 / 0.0 | 0 | 0.526 / 0.0 | 19.1 |
| Combined F | anococcygeal_ligament | 47.4 | 10.0 x 3.0 | 1.0671 | 0.0 / - | 0 | 0.0 / 0.031 | 15.7 |
| Combined F | pubovesical_ligament_l | 11.2 | 8.0 x 3.0 | 0.201 | 0.0 / - | 0 | 0.041 / 0.0 | 37.6 |
| Combined F | pubovesical_ligament_r | 7.9 | 8.0 x 3.0 | 0.1431 | 0.0 / - | 0 | 0.021 / 0.0 | 38.0 |
| Combined F | patellar_ligament_l | 42.1 | 24.0-30.0 x 5.0 | 4.246 | 0.0 / 0.0 | 0 | 0.1 / 0.0 | 0.7 |
| Combined F | patellar_ligament_r | 54.0 | 24.0-30.0 x 5.0 | 5.206 | 0.0 / -0.0 | 0 | 0.483 / 0.0 | 0.8 |
| Base F | tendinous_arch_levator_ani_l | 75.5 | 5.0 x 1.5 | 0.4248 | 0.0 / 0.0 | 0 | 0.085 / 0.037 | 37.4 |
| Base F | arcus_tendineus_fasciae_pelvis_l | 76.2 | 5.0 x 1.5 | 0.4287 | 0.0 / -0.0 | 0 | 0.062 / 0.212 | 32.2 |
| Base F | tendinous_arch_levator_ani_r | 75.6 | 5.0 x 1.5 | 0.4252 | 0.0 / 0.0 | 0 | 0.39 / 0.0 | 37.3 |
| Base F | arcus_tendineus_fasciae_pelvis_r | 76.1 | 5.0 x 1.5 | 0.428 | 0.0 / 0.0 | 0 | 0.272 / 0.112 | 32.1 |
| Base F | transverse_perineal_ligament | 22.6 | 8.0 x 2.0 | 0.2506 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 11.0 |
| Base F | anococcygeal_ligament | 8.7 | 10.0 x 3.0 | 0.196 | 0.0 / - | 0 | 0.497 / 0.0 | 36.4 |
| Base F | pubovesical_ligament_l | 8.6 | 8.0 x 3.0 | 0.1552 | 0.0 / - | 0 | 0.546 / 0.0 | 28.3 |
| Base F | pubovesical_ligament_r | 8.2 | 8.0 x 3.0 | 0.1467 | 0.0 / - | 0 | 0.005 / 0.0 | 28.5 |
| Imaging-based M | tendinous_arch_levator_ani_l | 90.7 | 5.0 x 1.5 | 0.5093 | 0.0 / -0.0 | 0 | 0.0 / 0.0 | 71.8 |
| Imaging-based M | arcus_tendineus_fasciae_pelvis_l | 82.3 | 5.0 x 1.5 | 0.463 | 0.0 / 0.0 | 0 | 0.052 / 0.0 | 71.5 |
| Imaging-based M | tendinous_arch_levator_ani_r | 81.0 | 5.0 x 1.5 | 0.4547 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 75.4 |
| Imaging-based M | arcus_tendineus_fasciae_pelvis_r | 78.4 | 5.0 x 1.5 | 0.4412 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 77.2 |
| Imaging-based M | transverse_perineal_ligament | 17.0 | 8.0 x 2.0 | 0.1734 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 59.0 |
| Imaging-based M | anococcygeal_ligament | 50.0 | 10.0 x 3.0 | 1.125 | 0.0 / - | 0 | 0.0 / 0.0 | 27.7 |
| Imaging-based M | puboprostatic_ligament_l | 26.9 | 8.0 x 3.0 | 0.4847 | 0.0 / - | 0 | 0.0 / 0.0 | 80.9 |
| Imaging-based M | puboprostatic_ligament_r | 22.6 | 8.0 x 3.0 | 0.1679 | 0.0 / - | 0 | 0.0 / 0.0 | 79.1 |
| Imaging-based M | sacrospinous_ligament_l | 54.9 | 7.0-12.0 x 2.5 | 0.978 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 32.5 |
| Imaging-based M | sacrotuberous_ligament_l | 104.1 | 10.0-14.0 x 3.5 | 3.1847 | 0.0 / -0.0 | 0 | 0.064 / 0.0 | 27.8 |
| Imaging-based M | iliolumbar_ligament_l | 19.3 | 12.0 x 3.0 | 0.5203 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 76.5 |
| Imaging-based M | sacrospinous_ligament_r | 52.8 | 7.0-12.0 x 2.5 | 0.932 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 40.9 |
| Imaging-based M | sacrotuberous_ligament_r | 100.0 | 10.0-14.0 x 3.5 | 3.1309 | 0.0 / -0.0 | 0 | 0.0 / 0.0 | 27.6 |
| Imaging-based M | iliolumbar_ligament_r | 17.7 | 12.0 x 3.0 | 0.4728 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 77.1 |
| Combined M | tendinous_arch_levator_ani_l | 78.2 | 5.0 x 1.5 | 0.4399 | 0.0 / 0.0 | 0 | 0.201 / 0.344 | 57.1 |
| Combined M | arcus_tendineus_fasciae_pelvis_l | 88.5 | 5.0 x 1.5 | 0.4965 | 0.0 / -0.0 | 0 | 0.162 / 0.336 | 51.1 |
| Combined M | tendinous_arch_levator_ani_r | 75.9 | 5.0 x 1.5 | 0.427 | 0.0 / -0.0 | 0 | 0.768 / 0.344 | 56.6 |
| Combined M | arcus_tendineus_fasciae_pelvis_r | 85.9 | 5.0 x 1.5 | 0.4835 | 0.0 / -0.0 | 0 | 0.517 / 0.39 | 50.1 |
| Combined M | transverse_perineal_ligament | 22.0 | 8.0 x 2.0 | 0.2454 | 0.0 / 0.0 | 0 | 0.0 / 0.0 | 32.3 |
| Combined M | anococcygeal_ligament | 21.9 | 10.0 x 3.0 | 0.4918 | 0.0 / - | 0 | 0.01 / 0.0 | 29.6 |
| Combined M | puboprostatic_ligament_l | 26.8 | 8.0 x 3.0 | 0.4679 | 0.0 / - | 0 | 0.16 / 0.0 | 51.1 |
| Combined M | puboprostatic_ligament_r | 26.1 | 8.0 x 3.0 | 0.4579 | 0.0 / - | 0 | 0.392 / 0.0 | 50.3 |
| Combined M | patellar_ligament_r | 55.9 | 24.0-30.0 x 5.0 | 5.6226 | 0.0 / 0.0 | 0 | 0.397 / 0.0 | 0.8 |
| Base M | tendinous_arch_levator_ani_l | 75.5 | 5.0 x 1.5 | 0.4248 | 0.0 / 0.0 | 0 | 0.085 / 0.037 | 37.5 |
| Base M | arcus_tendineus_fasciae_pelvis_l | 76.2 | 5.0 x 1.5 | 0.4287 | 0.0 / -0.0 | 0 | 0.376 / 0.212 | 32.2 |
| Base M | tendinous_arch_levator_ani_r | 75.6 | 5.0 x 1.5 | 0.4252 | 0.0 / 0.0 | 0 | 0.34 / 0.0 | 37.3 |
| Base M | arcus_tendineus_fasciae_pelvis_r | 76.1 | 5.0 x 1.5 | 0.428 | 0.0 / 0.0 | 0 | 0.272 / 0.272 | 32.1 |
| Base M | transverse_perineal_ligament | 22.6 | 8.0 x 2.0 | 0.2506 | 0.0 / 0.0 | 0 | 0.0 / 0.149 | 11.8 |
| Base M | anococcygeal_ligament | 8.7 | 10.0 x 3.0 | 0.196 | 0.0 / - | 0 | 0.497 / 0.0 | 36.4 |
| Base M | puboprostatic_ligament_l | 17.8 | 8.0 x 3.0 | 0.3042 | 0.0 / - | 0 | 0.701 / 0.0 | 28.1 |
| Base M | puboprostatic_ligament_r | 18.2 | 8.0 x 3.0 | 0.3127 | 0.0 / - | 0 | 0.211 / 0.0 | 27.9 |

## 7. Z-Anatomy transfers onto the Imaging-based pages: fit errors

**Imaging-based F**: 86 structures shipped; worst carrier-bone local fit residual per structure: median 1.56 mm, max 2.46 mm; attachment gap before the snap (median of each structure): median 1.16 mm, max 3.0 mm; after the snap 0 mm by construction. Per-structure numbers: `data/derived/Q248_xfer_own_f.json` (carriers, local residuals, attachment gaps, pushed vertices, edge stretch, length ratio, overlap, skin depth, sides).

**Imaging-based M**: 79 structures shipped; worst carrier-bone local fit residual per structure: median 1.52 mm, max 2.4 mm; attachment gap before the snap (median of each structure): median 1.31 mm, max 5.09 mm; after the snap 0 mm by construction. Per-structure numbers: `data/derived/Q248_xfer_own_m.json` (carriers, local residuals, attachment gaps, pushed vertices, edge stretch, length ratio, overlap, skin depth, sides).

## 8. Held (not shipped) and why

**Imaging-based F**: 94 of 172 planned Z structures held. Reasons (a structure can have several): > 25 % of the vertices deeper than 6 mm inside a muscle x 65; mesh distorted (edge stretch) x 31; outside / within 1 mm of the skin x 28; attachment vertices not snappable x 10; length ratio outside 0.6-1.6 x 9; vertices still > 1 mm in bone x 8; too much of the mesh pushed out of bone x 6; carrier local fit median > 2.5 mm x 2.

**Imaging-based M**: 106 of 175 planned Z structures held. Reasons (a structure can have several): > 25 % of the vertices deeper than 6 mm inside a muscle x 78; mesh distorted (edge stretch) x 25; outside / within 1 mm of the skin x 17; attachment vertices not snappable x 13; too much of the mesh pushed out of bone x 13; length ratio outside 0.6-1.6 x 10; vertices still > 1 mm in bone x 8; carrier local fit median > 2.5 mm x 5.

**Imaging-based F, rule-based held**: `arcus_tendineus_fasciae_pelvis_l` (> 10 % of the vertices deeper than 3 mm inside an organ); `anococcygeal_ligament` (> 10 % of the vertices deeper than 3 mm inside an organ); `pubovesical_ligament_l` (> 10 % of the vertices deeper than 3 mm inside an organ); `pubovesical_ligament_r` (> 10 % of the vertices deeper than 3 mm inside an organ); `patellar_ligament_l` (closer than 0.5 mm to / outside the skin).

**Base F, rule-based held**: `patellar_ligament_l` (length 25.3 mm outside the published range 30-60 mm (Aithal Padur 2021)); `patellar_ligament_r` (length 25.4 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Imaging-based M, rule-based held**: `patellar_ligament_l` (length 76.1 mm outside the published range 30-60 mm (Aithal Padur 2021)); `patellar_ligament_r` (closer than 0.5 mm to / outside the skin, length 60.2 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Combined M, rule-based held**: `patellar_ligament_l` (length 61.4 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Base M, rule-based held**: `patellar_ligament_l` (length 25.3 mm outside the published range 30-60 mm (Aithal Padur 2021)); `patellar_ligament_r` (length 25.4 mm outside the published range 30-60 mm (Aithal Padur 2021)).

**Imaging-based F, CVH**: `anococcygeal_ligament_cvh` ship; `pubovesical_ligament_cvh` held (> 25 % of the vertices deeper than 6 mm inside a muscle, > 10 % of the vertices deeper than 3 mm inside an organ).

**Combined F, CVH**: `anococcygeal_ligament_cvh` held (> 10 % of the vertices deeper than 3 mm inside an organ, closer than 3 mm to / outside the skin, bone penetration after registration: > 15 % of the vertices or > 4 mm); `pubovesical_ligament_cvh` held (does not reach the pubic bone (14 mm away after the registration; the pubovesical ligament attaches to the pubis)).

## 9. Literature / sources checked (PubMed, web)

- Kearney R, Sawhney R, DeLancey JOL. Levator ani muscle anatomy evaluated by origin-insertion pairs. Obstet Gynecol 2004;104:168-73 (PMID 15229017, doi 10.1097/01.AOG.0000128906.61529.6b): origin / insertion pairs, no dimensions of the arch.
- Stein TA, DeLancey JOL. Structure of the perineal membrane in females: gross and microscopic anatomy. Obstet Gynecol 2008;111:686-93 (PMID 18310372, doi 10.1097/AOG.0b013e318163a9a5): the membrane is continuous with the insertion of the arcus tendineus fasciae pelvis; a 3-D structure (dorsal / ventral part), no outline or thickness that could be built: perineal membrane NOT built.
- DeLancey JOL. Anatomic aspects of vaginal eversion after hysterectomy. Am J Obstet Gynecol 1992;166:1717-28 (PMID 1615980): arcus tendineus fasciae pelvis from the pubic bone to the ischial spine.
- Aithal Padur A et al. Morphometric analysis of patella and patellar ligament. Surg Radiol Anat 2021;43:2039-46 (PMID 34570285, doi 10.1007/s00276-021-02837-z): patellar ligament length 4.8 / 4.6 cm (right / left), range 3-6 cm; the table of widths / thickness is not in the retrievable text.
- Basso O, Johnson DP, Amis AA. The anatomy of the patellar tendon. Knee Surg Sports Traumatol Arthrosc 2001;9:2-5 (PMID 11269580, doi 10.1007/s001670000133): fibres converge toward the tibial attachment; patellar apex 39 +- 6 % of the tendon width from the medial edge.
- Occelli et al., Eur J Obstet Gynecol Reprod Biol 2001 (abstract only, via a web search): arcus tendineus fasciae pelvis about 10 cm in two fixed female pelves; used as a plausibility range only. A 2004 cadaver study (five female cadavers) found the structure absent / weak in 6 of 10 hemipelves: variable presence.
- Sacrospinous ligament length 43.04 +- 6.58 mm (nine embalmed female hemipelves; 'Anatomical landmarks regarding sacrospinous colpopexy operations', web abstract, not verified against the paper): not used as input.
- No PubMed / web source gave a width or thickness for the tendinous arch of levator ani, the arcus tendineus fasciae pelvis, the transverse perineal ligament, the anococcygeal ligament or the puboprostatic / pubovesical ligaments: their calibres are MODELLING CHOICES (stated on every card as such), which is why those cards say 'an estimate of position'.
