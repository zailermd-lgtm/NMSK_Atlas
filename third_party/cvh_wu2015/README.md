# CVH5_116 pelvic floor, Wu et al. 2015 (decoded)

47 structures of one young adult female (Chinese Visible Human), 341,454 vertices, 688,510 triangles, binary PLY (float32), 13 MB. Licence and attribution: `NOTICE.md`.
Not registered to any atlas page. Names, counts, volumes, bounding boxes, per-mesh checks: `structures.json`.

## Frame (inferred, not stated in the source)
- Units: millimetres. U3D unit-scale header 0.001; pelvic bone extent 234 x 107 x 112 mm, skin 357 x 217 x 186 mm; only plausible as mm.
- Origin: arbitrary section-stack origin (bone centroid about (174, 110, 100)). The common midline plane is x = 184 (+-1.5 mm, bilateral structures).
- Axes (from structure centroids): **x** lateral (left-right unknown, see below); **y increases posteriorly** (bladder 100, urethra 117-125, vagina 136, rectum 166, anococcygeal ligament 194, coccyx 204);
  **z increases inferiorly** (uterus/ovary 60-75, bladder 91, vagina 124, urethral sphincter 135, perineal body 157, clitoris 149, vestibular bulb 151, Bartholin 154).
- Left/right side is not labelled in the source file and was not determined; the meshes carry no L/R names. Do not assume a side from the sign of x.
- Rotation of the whole stack versus the page frame, and handedness, must be fixed by registration to landmarks (pubic symphysis, ischial spines, coccyx) when needed.

## Checks run (all by us)
| Check | Result |
|---|---|
| Payload of each mesh block consumed | 47/47 exact (decoder log) |
| Indices in range, no NaN | 47/47 |
| Mirror symmetry about x=184 (median NN, paired structures) | vestibular bulb 0.88, Bartholin 0.89, cavernous body 0.90, superficial transverse perineal 0.93, coccygeal 0.97, puborectal 0.98, pubovisceral 1.02, bulbospongiosus 1.05, ischiocavernosus 1.29, internal obturator 1.39, pelvic bone 1.89 mm, skin 2.65 |
| Lumen vs wall surface (median NN) | bladder lumen to bladder wall 0.01 mm; uterine/vaginal lumen to vaginal wall 0.01 mm |
| Anatomical order | correct (above); ovaries and tubes superior, perineal muscles/clitoris/bulbs/Bartholin inferior-anterior-posterior as expected |
| Closed manifold | only 5: ovary 19.8 cm3, round ligament 2.6, ureter 1.6, pubovesical ligament 0.2, sacrum+coccyx 17.8 |

**Caution on volumes.** 42 of 47 meshes are open or non-manifold sheets (the model is cropped at the block edge; walls are shells). Their `signed_volume_cm3` can be negative or meaningless;
`volume_cm3` is `null` for them. Skin (10,460 cm3 signed, 12 non-manifold edges, 4 components) is almost closed but is a cropped block, not a body.

## Reproduce
```
curl -L -o S3_Fig.pdf https://ndownloader.figshare.com/files/2224397        # extract the /U3D stream (Flate) -> s3.u3d
python3 -I rh_mesh.py s3.u3d OUT                                            # upstream MIT decoder, see NOTICE.md
python3 -I tools/build_package.py OUT .                                     # PLY + structures.json
```
Other Figshare files of the item (S1/S2/S5-S8 TIFF, S4 PDF with images only, S1_Table.docx) hold no meshes.

## Correction (Q235): most of the meshes are CLOSED solids
The "open sheet" count above (42 of 47) is an artefact of the check in `tools/build_package.py`: it counts a DIRECTED edge without an opposite edge, so a closed surface whose triangles are not wound consistently reads as open.
Counted per undirected edge on the unwelded triangles (every edge shared by exactly two triangles), the structures used by Q235 are closed: cavernous body of the clitoris, vestibular bulbs, Bartholin's glands, ischiocavernosus (both), bulbospongiosus,
urethral compressor, urethrovaginal sphincter, raphe, submucous layer of the urethra, bladder + urethral lumen; superficial / deep transverse perineal muscles, urethral sphincter proper and the perineal body are closed except for 1-3 edges
where two parts of the surface touch (4 triangles on one edge). Re-orienting the triangles (vertex order only, no vertex moves; `scripts/anatomy/q235/solid.py`) gives a defined volume, which an independent ray-parity Monte-Carlo
volume confirms (e.g. clitoris 1.92 vs 1.96 +- 0.04 cm3, vestibular bulbs 0.49 / 0.54, bulbospongiosus 2.83, perineal body 3.73 + 0.65 cm3). The `volume_cm3: null` and `signed_volume_cm3` fields of `structures.json` are therefore NOT the tissue volumes of
these structures; the Q235 values are in `data/derived/Q235_report_own_f.json`. Meshes that really stay open or non-manifold (rectum, mesorectum, veins, peritoneum, skin, vaginal wall with 7 touching edges ...) are unchanged in status.
The CVH volumes are of the CVH specimen (cm3 in its own frame); on an atlas page they are scaled by the registration scale cubed.
