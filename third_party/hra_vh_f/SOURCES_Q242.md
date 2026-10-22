# Q242 sources: HRA 3D Reference Object Library v1.10 (CDN, June 2026)

Fetched 2026-10-15 for the audit `data/derived/Q242_hra_v110_audit.md`. NOTHING from this fetch is copied into the repo and no page uses it yet; the files are in the session scratchpad
(`.../scratchpad/hra110/files/<object>/`), the URLs and sha256 of every file are in `data/derived/Q242_hra_manifest.json`.

- Catalog: https://cdn.humanatlas.io/digital-objects/ref-organ/ (88 objects). Per object: `https://cdn.humanatlas.io/digital-objects/ref-organ/<name>/<version>/assets/<file>.glb` + `assets/crosswalk.csv`
  + `<version>/graph.jsonld`; metadata (licence, creators, citation) from `.../<name>/latest/`. HRA collection v2.5 (2026-08-10). The GitHub repo ccf-3d-reference-object-library is stale (HEAD f1a3a63).
- Fetched: 87 GLB (1.21 GB; United Female v1.10 374.5 MB, United Male v1.10 241.6 MB, then skin, adipose, pelvis, intervertebral disk, knee, blood vasculature, spinal cord, sternum, manubrium, ovary,
  fallopian tube, uterus and the rest of the female/male organ set), 88 crosswalk CSV (87 per object + the master ASCT+B -> 3D crosswalk v1.10), 88 graph.jsonld. Total 1.24 GB.
- Licence: all 88 objects Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/ (checked per object, graph and object level; no exception).
  Compatible with the CC BY-SA 4.0 of the public atlas pages.
- Geometry check: the objects already used (pelvis, uterus, ovaries, tubes, bladder, vagina, ligaments, mammary gland) are geometrically identical to the files in this directory (same triangle counts and
  bounding boxes); the v1.10 versions only carry new DOIs/dates. No new geometry is shipped by Q242.

## Attribution lines to use if any v1.10 object is later shown (CC BY 4.0)

- "3D Reference Organ Set for Female / Male, v1.10", Kristen Browne and Heidi Schlehlein, HuBMAP / Human Reference Atlas 3D Reference Object Library, funded by the National Institutes of Health,
  CC BY 4.0. Female: https://doi.org/10.48539/HBM637.DWBM.744. Male: https://doi.org/10.48539/HBM833.WZWN.425. Source data: the Visible Human Project, National Library of Medicine (Spitzer and Whitlock 2002;
  Spitzer et al. 1996; Ackerman 1998).
- Single objects: the same two creators with the DOI of the object (manifest `doi`), except Heidi Schlehlein alone for adipose, intervertebral disk, sternum, manubrium, mouth, omentum, epiploic appendage and
  mammary gland (sculpted from scratch; Krstic 1991; Gilroy et al. 2008), Li Yao for lymph nodes, Kristen Browne for heart-male.
- Brain (Allen human reference atlas, Ding et al. 2016) and large intestine (not image-based) must keep their source note.
- ASCT+B -> 3D crosswalk v1.10: Ellen M. Quardokus, Heidi Schlehlein, Bruce W. Herr II, Katy Boerner; https://doi.org/10.48539/HBM626.BRWN.943.
- Frame: metres, y up, +x subject LEFT, +z anterior. Known defects to correct on import: swapped left/right round ligament (female), vas deferens / renal arteries (male), Allen brain sidedness, swapped
  inferior pulmonary vein labels (female).
