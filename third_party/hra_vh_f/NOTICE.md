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
