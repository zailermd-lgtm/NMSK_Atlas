# HuBMAP Human Reference Atlas (HRA) 3D Reference Object Library -- Visible Human FEMALE reference organs (excerpt)

Files here (`VH_F_Pelvis`, `VH_F_Uterus`, `VH_F_Ovary_L/R`, `VH_F_Fallopian_Tube_L/R`, `VH_F_Urinary_Bladder`, `.glb`) are copied unchanged from
https://github.com/hubmapconsortium/ccf-releases (commit b036a91aaf7234f462b1249d4a5f4fb0e982f412, directory `v1.3/models/`; the `*.md` files are the library's own
descriptions, `v1.3/markdown/ref-organs/`).

- Creators: Kristen Browne, Heidi Schlehlein (project lead Katy Boerner), HuBMAP, funded by NIH (OT2OD026671).
- Licence: Creative Commons Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/ -- compatible with the CC BY-SA 4.0 of the public atlas pages.
- Source data (library descriptions): the pelvis and ovary records say "created using data from the Visible Human Female, provided by the National Library of Medicine"; the uterus record
  says "Visible Human Male" (a copy error in the library text: the object is `VH_F_Uterus`, lies in the `VH_F_Pelvis` frame and sits correctly in the female pelvis).
- Cite: Kristen Browne; Heidi Schlehlein. 2022. 3D Reference Organ for Uterus v1.1, https://doi.org/10.48539/HBM228.JBNJ.299 ; HuBMAP CCF 3D Reference Object Library,
  https://humanatlas.io/3d-reference-library.
- Frame: metres, +x patient left, +y superior, +z anterior; the atlas uses mm, +X right, +Y superior, +Z anterior (scripts/anatomy/q233/hra_register.py converts and registers).
- Used by Q233 (PROJECT_STATE.md): uterus, ovaries, uterine tubes registered onto the Visible Human female's own CT pelvis.

## Q234 additions (vagina, ligaments of the uterus and ovaries, breasts) -- CC BY 4.0 attribution

Source: HuBMAP CCF 3D Reference Object Library, https://github.com/hubmapconsortium/ccf-3d-reference-object-library (commit f1a3a63f110e27ff0736047d52d04dba5d3087f9, Visible Human Female directory),
cite: Kristen Browne, Heidi Schlehlein, Bruce W. Herr II, Ellen Quardokus, Andreas Bueckle, Katy Boerner. 2022. HuBMAP CCF 3D Reference Object Library, https://humanatlas.io/3d-reference-library.
Licence: Creative Commons Attribution 4.0 International (CC BY 4.0), compatible with the CC BY-SA 4.0 of the public atlas pages. File list, URLs and sha256: `SOURCES_Q234.json`.

- `v1.2_VH_F_Vagina.glb` (VH_F_vagina, VH_F_cervicovaginal_junction) and `v1.2_VH_F_Ligaments_Uterus_Ovaries.glb` (round, uterosacral, cardinal, broad, ovarian and suspensory ligaments, mesosalpinx, mesovarium; the
  uterovesical pouch of the same file is not used), copied here unchanged. Objects of the Visible Human Female frame (same frame as the VH_F_Pelvis / Uterus / Ovary files above); the library has no description record
  that says how these two objects were built.
- `v1.3` `VH_F_mammary_gland_L.glb` / `_R.glb` (fat pad, mammary lobes, main lactiferous ducts and sinuses, areola, areolar tubercles, nipple, suspensory ligaments): not copied (38 MB), downloaded on demand and sha256-checked.
  Creator Heidi Schlehlein, reviewer Harikrishna Nakshatri, DOI 10.48539/HBM378.VWZG.633 (left) and 10.48539/HBM989.SNHP.535 (right); the library's own description (`mammary-gland-female-left.md` / `-right.md`, copied here):
  "The breast was sculpted from scratch to include relevant anatomy for placement of registration blocks. The atlas Human Microscopic Anatomy (R.V. Krstic, 1994) and Atlas of Anatomy (Thieme, 2008) was referenced."
  => a sculpted REFERENCE MODEL, NOT data from the Visible Human Female; the atlas pages say so (Source class "Reference model (sculpted, not donor data)").
- `v1.2` `VH_F_Vertebrae.glb`: downloaded on demand, used only as the registration anchor of the thorax (thoracic vertebrae T1-T12 of the same Visible Human female frame); not shipped.
- Derived data kept in the repo: `data/derived/Q234_hra_meshes.npz` (decimated meshes, HRA frame) and `.json` (volumes, decimation deviations). Shown on the pages: the vagina and the ligaments registered onto each page's pelvis
  (the same transform as the Q233 uterus), the breasts registered on each page's thoracic vertebrae and compressed into each page's skin envelope (Q234 badges state the fit); all with the CC BY 4.0 attribution on the pages.

## Q243 (2026-10-15): objects of the HRA 3D Reference Object Library v1.10 (CDN, CC BY 4.0) shown on the pages

Source: https://cdn.humanatlas.io/digital-objects/ref-organ/ (URLs + sha256 of every file: `data/derived/Q242_hra_manifest.json`; the GLBs stay OUT of the repo and are downloaded + sha256-checked on demand by `scripts/anatomy/q243/hra.py`).
Licence of every object used: Creative Commons Attribution 4.0 International, https://creativecommons.org/licenses/by/4.0/ (checked per object in Q242). Creators: Kristen Browne and Heidi Schlehlein (HuBMAP / HRA, funded by the National Institutes of Health); source data
the Visible Human Project, National Library of Medicine.
- `blood-vasculature-female` v1.3 (DOI 10.48539/HBM322.KKFC.394): the pelvic vessels (uterine a./v., internal iliac v., internal pudendal v., middle / inferior / superior rectal v., median sacral v., superior rectal a.), registered with the Q233 pelvis transform,
  open tube ends closed with flat discs. Library defects found and handled: the crosswalk label of the VEIN node `VH_F_superior_rectal_vein` reads 'superior rectal artery' (node name and geometry used); left / right of all 15 nodes verified (name = x position = nearer same-side hip bone).
- `united-female` v1.10 (DOI 10.48539/HBM637.DWBM.744; nodes `VH_F_nucleus_pulposus_of_intervertebral_disk_of_*`, `VH_F_*_spinal_cord_segment`, `VH_F_*_vertebra_*`, uterus and tube sub-part nodes), `spinal-cord-female` v1.1 (DOI 10.48539/HBM242.QQQB.777; the library says the model was prepared with
  Frostell et al. 2016 as reference and that 'The Visible Human Female has 6 lumbar vertebrae') and `intervertebral-disk-female` v1.0 (DOI 10.48539/HBM824.BNBP.227; modelled by Kristen Browne, fitted to the spine by Heidi Schlehlein): nucleus pulposus and spinal cord segments fitted per vertebra
  onto her CT vertebrae; the uterus / tube sub-part names, ontology ids and marker positions as parts of the shipped uterus and tubes.
- `united-male` v1.10 (DOI 10.48539/HBM833.WZWN.425) and `pelvis-male` v1.3 (DOI 10.48539/HBM384.SBWX.873): the prostate zones were registered and guarded but NOT shipped (the registered HRA prostate does not coincide with the page's prostate; `data/derived/Q243_report_own_m.json`).
Derived data kept in the repo: `data/derived/Q243_report_*.json`, `Q243_spine_fits_own_f.json`, `Q243_parts_hra.json`, `data/anatomy/structure_parts_hra_q243.json`.
