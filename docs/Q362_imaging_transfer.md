# Q362 — real organ geometry from the frozen Imaging pages onto the Base pages

Owner, 2026-11-17: yes ("interesting solution, may be synergistic with the atlases"). Script `scripts/anatomy/q362/transfer_organs_q362.py`
(registration `register_q362.py`, read-only source access `srcpage_q362.py`, offline renders `render_q362.py`, browser card check
`verify_cards_q362.py`), test `tests/test_q362_transfer.py`, report `data/derived/Q362_transfer_report.json`.
The frozen pages `build/q309/viewer_m_hr` / `viewer_f_hr` were only read (own-engine `bundle-json` + `BIN_FILES`: per structure nv×3
int16 × quantum_mm, then nf×3 uint16).

## 1. Sources and licences

| organ (target) | source mesh (page, subject) | how it was made | licence |
|---|---|---|---|
| rectum (Base·M) | `rectum`, viewer_m_hr, ct_vhm_pelvis (Q170) | VH male frozen CT, TotalSegmentator `total` colon label cut at the pelvic inlet and the sigmoid take-off | NLM Visible Human: US public domain ("Courtesy of the U.S. National Library of Medicine"); TotalSegmentator `total` task: Apache-2.0 tool, output ours (docs/GEOMETRY_SOURCES.md) |
| external anal sphincter, bulbospongiosus L/R, ischiocavernosus L/R, deep transverse perineal L/R (Base·M) | viewer_m_hr, ct_vhm_pfloor (Q172) | his 1 mm cryosection photographs, outlined by this project's position rules + marker watershed (badged RULE-BASED in Q172) | public domain images, own segmentation |
| small bowel (Base·M / Base·F) | `small_bowel`, ct_vhm_viscera / ct_vhf_viscera (Q193) | TotalSegmentator `total` small-bowel label (jejunum + ileum in one label) | as the rectum |
| kidneys (Base·F; Base·M only as `kidneys_m`) | `kidney_l/_r`, ct_vhf_viscera (Q193) | TotalSegmentator `total` kidney labels of HER CT (his are empty / 0.10×: no male source) | as the rectum |

The Z-Anatomy kidney stays excluded (CC-BY-NC, `zanatomy_inventory.json` nc_licensing_note). Source gaps: he has no superficial
transverse perineal muscle (< 1 cm³, not shipped by Q172), no internal sphincter and no anal canal of its own (inside the colon label);
his sphincter ring is only the deep part (10 mm tall, 77 mm above his own skin: the lower canal sits in Q172's unshipped "perineal_other").

## 2. Registration (bones both bodies have; similarity only)

Trimmed symmetric ICP on paired bones, Umeyama per round (40 rounds, 10 % trim per bone; ribs one-sided). Residual = surface distance
of the transformed source bone to the Base bone, both ways.

| set | bones | scale | rotation | residual median / p90 mm |
|---|---|---|---|---|
| VHM → Base·M pelvis | hip bones, sacrum, coccyx, femora (top 100 mm) | 0.884 | 6.7° | 3.5 / 9.2 (coccyx 8.1, femora 4.8–5.3, hips 3.5, sacrum 2.7) |
| VHM → Base·M abdomen | L1–L5, hips, sacrum, ribs 10–12 | 0.895 | 1.6° | 3.1 / 8.5 |
| VHF → Base·F abdomen | L1–L5, hips, sacrum (her ribs left out: rib 10 L broken into pieces in her segmentation; with them 5.6 / 15.6) | 0.938 | 1.4° | 4.3 / 12.1 |
| VHF → Base·F kidney | T11–L4, ribs 11–12 | 1.077 | 4.3° | 4.3 / 13.3 |
| VHF → Base·M kidney (`kidneys_m`) | T11–L4, ribs 11–12 | 0.955 | 4.2° | 3.0 / 8.4 |

No warp: a bone-driven thin-plate spline (40/80 controls, smoothing 10/100) lowered the bone residual by only 0.4–1.7 mm but moved the
organs by a median 4–21 mm (kidneys up to 50 mm) — extrapolation, not correction. Her vertebrae: 12 thoracic + 6 lumbar-labelled
segments; levels are counted from T1 (rib heads 1–12 confirm T12), the lowest lumbar-labelled one is not used.

## 3. Guards and how each organ ended

Guards: no vertex > 1 mm in bone; none outside the skin (Q357 voxel body + ray fallback); one rigid nudge ≤ 5 mm per source group
(never reshaping); solid neighbours (viscera / muscle / cns): held when > 3 % of the organ's vertices lie > 3 mm inside one, or > 3 % of the
neighbour's vertices lie > 3 mm inside the organ; fat volumes, open fascial sheets and vessel / nerve tubes are listed only; any book
check that differs (except a size) holds the organ.

RESULTS_TABLE

## 4. Checks against the owner's books (knowledge only)

Mannan = Noor MA, *Mannan's Regional Dissection and Surface Anatomy*, 14th ed., Jaypee 2017 (printed page, PDF page);
Gray's Atlas = Drake et al., *Gray's Atlas of Anatomy* (edition not in the scan).
- Kidney: T11–L3 (Mannan p. 333); hilum ~2 in from the midline opposite L1, right a little lower (pp. 528–529); ribs XI–XII behind
  (Gray's Atlas p. 177). Her kidneys lie L1/L2 → L4/L5 against her OWN vertebrae (left lower than right): after registration the upper
  poles are at L1 and the lower at L4–L5 on both Base bodies, 20–50 mm below the Z suprarenal glands → **differs; held**.
- Rectum: begins at S3 (Mannan p. 385, p. 563), in the sacral concavity, bends ~3 cm in front of the coccyx (p. 385), behind the
  bladder / prostate (p. 351; Gray's Atlas p. 216). Measured: upper end 0.43 of the sacral height (S3 band 0.40–0.60) pass; posterior
  wall median 11 mm in front of the sacrum pass; centre 35 mm in front of the coccyx tip pass; behind the prostate pass; Z bladder see §3.
- Perineum: ischiocavernosus on the ischial ramus, bulbospongiosus from the raphe / perineal body over the bulb (Mannan p. 355), deep
  transverse perineal from the ischial ramus to the raphe (p. 359), perineal body ½ in in front of the anus (p. 354), deep pouch below the
  prostate (pp. 360, 379). Attachment distances pass (0–2.4 mm); the Base·M Z prostate violates the "deep pouch below the prostate"
  relation (§5).
- Small bowel: ileum between the large-gut frame and the pelvis (Mannan p. 380); ends at the ileocaecal junction (Gray's Atlas pp. 155,
  158). Infracolic share, frame share and distance to the caecal end of the Z ascending colon are in the report.

## 5. What blocks the rest (for the owner)

- **Base·M Z prostate sits ~15 mm lower than the VH male's relative to the same bones** (apex 9 mm below the symphysis' lower border;
  every pelvic registration variant puts his prostate at y −36…−2 vs Z −52…−29). His perineal muscles and sphincter, placed by the bones,
  therefore lie 5–11 mm deep inside it. Options: carry his prostate too (and hide the Z one — but the Z urethra / seminal glands /
  ejaculatory ducts are built round it), or a separate round on the Z prostate.
- **Ischiocavernosus** L/R: 179 / 255 vertices up to 5.5 mm in the ischiopubic ramus (registration residual at the pubic arch); no
  translation ≤ 5 mm clears it (it wraps the ramus edge).
- **Kidneys**: her real kidneys are low-lying; no source of a textbook-level real kidney is available (§1).
- **Small bowel, Base·M**: his upper loops lie up to 31 mm inside the Z stomach.
- **Small bowel, Base·F**: her CT small-bowel label holds part of her uterus (in her own body 35 % of her cryosection uterus' vertices
  lie inside it, up to 12 mm): the mesh would engulf the Base·F uterus.

## 6. `skin_vulva_cvh` (report only)

It is NOT from the Imaging·F subject: it is the Chinese Visible Human female skin block (Wu et al. 2015, CC BY 4.0,
`third_party/cvh_wu2015` mesh 46), registered in Q336. Its source density is the limit: median edge 5.2 mm (p90 10.2) in the raw
8,985-vertex block. The Imaging·F page has no better surface: her CT skin (`skin`, ct_vhf_skin) is decimated 1.23 M → 75 k triangles for
the whole body (median edge 5.6–6.5 mm around the vulva) and, with the thighs closed in the scan, bridges the perineum: in the midline
its lowest point is the inner-thigh contact at y −180…−199 mm, 43 mm from the clitoris and 60 mm from the perineal body. No vulvar
surface exists on that page. Recommendation: keep `skin_vulva_cvh`; a finer real surface would need the full-resolution CVH sections
(not in the repo), not the Imaging·F page.

## 7. Apply

APPLY_BLOCK
