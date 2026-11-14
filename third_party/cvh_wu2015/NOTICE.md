# NOTICE: Wu et al. 2015 pelvic-floor meshes (CC BY 4.0)

**Original work.** Yi Wu, Noshir F. Dabhoiwala, Jaco Hagoort, Jin-Lu Shan, Li-Wen Tan, Bin-Ji Fang, Shao-Xiang Zhang, Wouter H. Lamers.
"3D Topography of the Young Adult Anal Sphincter Complex Reconstructed from Undeformed Serial Anatomical Sections."
PLoS ONE 10(8): e0132226 (2015). DOI 10.1371/journal.pone.0132226.
Supplement: Figshare item 1519992, https://plos.figshare.com/articles/dataset/_3D_Topography_of_the_Young_Adult_Anal_Sphincter_Complex_Reconstructed_from_Undeformed_Serial_Anatomical_Sections_/1519992
(file `S3_Fig.pdf`, Figshare file id 2224397, 10,522,121 bytes, sha256 `7d0a71d5a57f12f37a66b256dd967ef793957d82e87ecc77431f494c63773f34`; embedded U3D stream sha256 `90a7bbae314e1276c62fd9a3b0144bb8a9bacafc1f34f1cf36c4f26ed8b0fc3e`).
Licence quoted from the Figshare API: `CC BY 4.0`, https://creativecommons.org/licenses/by/4.0/ .
Specimen: Chinese Visible Human (CVH), young adult female, cryosections; model group `CVH5_116`.

**What was changed (CC BY 4.0 s3(a)(1)(B) indication of changes).** The 47 named mesh resources (`RHAdobeMeshResource`, Right Hemisphere/Adobe compressed
meshes inside the U3D stream of the PDF) were decoded to vertex positions and triangles (normals discarded), and each one was written as a
binary little-endian PLY file in millimetres, named after the original structure name (`meshes/NN_<name>.ply`). No vertex was moved, smoothed, remeshed,
scaled or registered. `structures.json` adds computed values (bounding boxes, counts, checks); these are ours, not the authors'.
Not endorsed by the authors or PLOS. The 47 meshes are one specimen, not a population mean.

**How they were decoded.**
- Format: Adobe, "U3D Supported Elements" (Acrobat 8.1 SDK, 2007), chapter 2 and appendix A (archived:
  web.archive.org/web/20160621183205id_/http://www.adobe.com/content/dam/Adobe/en/devnet/acrobat/pdfs/U3DElements.pdf), plus the arithmetic coder of ECMA-363.
- Decoder: `soma/tools/register/rh_mesh.py` of https://github.com/twokidsCarl/world-sim (MIT licence, commit `ea50e54c59d5f0f752071521b757571675a828db`, file sha256
  `1485ad43c81ae40dffc14c0a41612b2142afbf39ce6aff1c7d0e9924185c6b23`). It was run unmodified in a scratch directory (`python3 -I rh_mesh.py S3.u3d OUT`) and is **not vendored** here.
  Its README credits experimental notes of github.com/peterdoubell/Primer for three format details.
- `tools/build_package.py` (own code) converts the decoder's OBJ + `structures.tsv` to PLY + JSON and computes the checks.

**Independent checks (ours, see README.md).** Every payload is consumed to the last byte; all indices in range; paired structures mirror about a common
midline (median nearest-neighbour distance 0.9-1.4 mm for paired structures); lumen and wall surfaces coincide (0.01 mm); anatomical order
anterior-posterior and superior-inferior is correct. Only 5 structures are closed manifolds; the rest are open sheets (the model is cropped).

**Q235 (derived use on the atlas pages).** Fourteen of the meshes (cavernous body of the clitoris, vestibular bulb, Bartholin's gland, bulbospongiosus, ischiocavernosus, superficial and deep transverse perineal muscle, urethral sphincter proper,
raphe of the urethral sphincter, urethral compressor, urethrovaginal sphincter, submucous layer of the urethra, perineal body, and the urethral part of the bladder + urethral lumen) are shown on the Imaging-based female and Combined female pages of the
atlas as separate structures. Changes made by the atlas (indicated on every structure card): rigid transformation + uniform scale (bone registration, scale about 1.11 into the page frame), triangle winding made consistent (vertex order only),
components below 100 triangles omitted, the lumen mesh cut at the bladder neck and closed by a flat cap, paired structures named left / right by the registration (the file carries no side labels). The coordinates of the shipped structures are
therefore NOT the authors' coordinates. Attribution string: `Yi Wu et al. 2015, PLoS ONE 10(8): e0132226, doi:10.1371/journal.pone.0132226, S3 Fig, CC BY 4.0`. Not endorsed by the authors or PLOS.
