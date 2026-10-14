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
