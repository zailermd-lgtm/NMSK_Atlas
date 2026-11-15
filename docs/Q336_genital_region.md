# Q336 — the genital / perineal region of the two Base pages

Owner (translated): "The genital area is also still not covered correctly. Use Gray's Anatomy and whatever else is needed to
complete it … this must be finished to a publishable level soon." Scope: Base · Male and Base · Female only (frozen pages untouched).

## 1. Diagnosis (measured on the pages as published; build/q309 = same geometry)

Screenshots: `scripts/anatomy/q336/render_q336.py` (Playwright, deviceScaleFactor 1, six views: front, inferior/perineal, both
laterals, anterior oblique, posterior-inferior; modes default / skin only / skin off / each system). Kept renders:
renders made by `scripts/anatomy/q336/render_q336.py` (`Q336_render_base_f_skin_{before,after}.png`, `Q336_render_cvh_skin_block.png`; not kept in the repo).

**Base · Female**
- **The skin does not cover the urogenital triangle.** Z-Anatomy's only perineal skin is the male `Urogenital region` l/r (penile +
  scrotal + urogenital-triangle skin), removed for the female body (Q196); the generated closure was removed in Q297. What remains is
  a keyhole-shaped opening bounded by 10 Z patches (anal region, femoral triangle, gluteal fold, hypogastric, inguinal, l/r) and
  the anterior/posterior thigh patches: a 36-vertex free rim (`data/derived/Q202_perineal_loop.json`), perimeter 379 mm, from the
  mons (y −35, z 99) down between the thighs to the anal-region patch (y −132). Rays cast through it from outside: **74 % meet no
  skin at all** (see-through into the pelvis). The ten neighbouring cards said the hole was honest because "no source holds female
  perineal skin" — **that was wrong**: the CVH skin block (mesh 46 of the same CVH set as the perineal muscles) carries the real
  mons, labia majora / minora and vestibule surface (`Q336_render_cvh_skin_block.png`; Q235 had written "skin (cropped block, no
  labia surface)").
- **Male leftovers: none.** No id or name on the page matches penis / penile / scrotal / testis / prostate / seminal / deferens /
  epididymis / spermatic / cremaster / dartos / bulbourethral / ejaculatory / male urethra. The only consequence of the removal is
  the opening above, plus `gonadal_a_l/r` and the testicular veins being absent → **no ovarian artery / vein** on Base · Female.
- **Female organs present:** uterus (two meshes: her cryosection `uterus_cryo_vhf` shown, HRA `uterus` hidden), uterine tubes, ovaries
  (HRA), vagina (HRA), broad / cardinal / uterosacral / round / ovarian / suspensory ligaments, mesovarium, uterine a/v; CVH:
  clitoris cavernous body (body + crura), vestibular bulbs, Bartholin glands, bulbospongiosus, ischiocavernosus l/r, superficial and
  deep transverse perineal, external urethral sphincter + compressor urethrae + urethrovaginal sphincter + raphe, female urethra
  (submucous layer + lumen), perineal body, anococcygeal ligament; her CT bladder / rectum / sigmoid; rule-based EAS (`external_anal_sphincter_ct_vhf`).
- **Female missing:** vulvar skin (before Q336), labia as separate objects, glans / prepuce of the clitoris (not separate in CVH),
  paraurethral glands, hymen, perineal membrane, ovarian vessels, dorsal nerve of the clitoris / perineal nerve / inferior rectal nerve
  (Q252 held them: rule courses outside the Z skin), and — unlike Base · Male — the Q248 rule-based `transverse_perineal_ligament` and
  `tendinous_arch_levator_ani_l/r`.
- Containment (Q299 body mask incl. fat layers): only `adductor_longus_l` (1 vertex, 2.3 mm) and `clitoris_cavernous_body`
  (1 vertex, 1.1 mm) outside.

**Base · Male**
- Skin: closed (Urogenital region l/r carries penis + scrotum). Containment: `gonadal_a_l` 4 vertices ≤ 1.6 mm, `zan_left_testicular_vein`
  12 ≤ 1.3 mm, `zan_superficial_external_pudendal_artery_r` 1 ≤ 0.3 mm outside — nothing else in the region.
- Present: corpora cavernosa / spongiosum, glans, urethra (one Z object), testes, epididymides, ductus deferentes, seminal glands,
  ejaculatory ducts, prostate, puboprostatic ligaments, penile / external / internal pudendal vessels, pudendal nerve, dorsal nerve of
  the penis (Q249 rule-based), levator ani + pubococcygeus + iliococcygeus + pubo-analis, coccygeus, EAS, transverse perineal ligament,
  tendinous arch, anococcygeal ligament (Q248 rule-based), sacrotuberous / sacrospinous ligaments.
- **Missing (Z-Anatomy has none):** bulbospongiosus, ischiocavernosus, superficial / deep transverse perineal, external urethral
  sphincter, perineal body, perineal membrane, bulbourethral glands, spermatic-cord coverings / cremaster / dartos / tunica vaginalis,
  **rectum and anal canal** (no rectum mesh at all), perineal and inferior rectal nerves (held, Q252).
- **Wrong place:** the Z-Anatomy `external_anal_sphincter` ends **25 mm above** the anal-region skin (lowest y −61 vs skin −77…−122;
  same mesh, hidden, on Base · Female). Source geometry; not moved (nothing to anchor it to without an anal canal).
- Both pages: `inguinal_ligament_r` is named "Inguinal ligament (Poupart's ligament)", its twin `zan_inguinal_ligament_l` "Inguinal
  ligament" (naming only; sides correct).

## 2. Reference checklist (what a correct atlas shows here)

Sources actually opened this session: PubMed records of Wu 2015 (PMID 26305117, doi:10.1371/journal.pone.0132226), O'Connell 2005
(PMID 16145367), Stein & DeLancey 2008 (PMID 18310372), Lloyd 2005 (PMID 15842291) — abstracts only. **Gray's Anatomy 1918 could not
be opened**: en.wikisource.org, www.bartleby.com, archive.org and www.theodora.com are outside this session's network (proxy 403 /
DNS refusal); the section names below are the ones the project's existing records already cite (`data/nerves`, `data/muscles`,
Q248 / Q249 cards), not re-read. Standing / current-edition atlases: not reachable.

| Group (Gray 1918 section) | Both sexes | Female | Male |
|---|---|---|---|
| Pelvic diaphragm ("The Fascia and Muscles of the Pelvis") | levator ani (pubococcygeus, puborectalis, iliococcygeus), coccygeus, tendinous arch | | |
| Perineum ("The Muscles and Fasciae of the Perineum") | EAS, perineal body, superficial / deep transverse perineal, ischiocavernosus, bulbospongiosus, external urethral sphincter, perineal membrane, superficial perineal (Colles') fascia, ischioanal fossa, anococcygeal ligament | compressor urethrae, urethrovaginal sphincter | |
| External genitalia ("The External Organs" / "The Male Genital Organs") | | mons pubis, labia majora / minora, clitoris (glans, body, crura), vestibule, bulbs of the vestibule, greater vestibular glands, paraurethral glands, urethral orifice, hymen | penis (corpora, glans), scrotum (dartos), testis, epididymis, tunica vaginalis, spermatic cord (ductus deferens, vessels, cremaster), bulbourethral glands |
| Internal genitalia | | uterus, tubes, ovaries, vagina; broad, round, ovarian, suspensory ligaments | prostate, seminal vesicles, ejaculatory ducts, urethra (prostatic / membranous / spongy) |
| Nerves ("The Pudendal Nerve") | pudendal n., inferior rectal n., perineal n., dorsal n. of penis / clitoris, posterior femoral cutaneous (perineal br.), ilioinguinal, genitofemoral (genital br.) | | |
| Vessels | internal pudendal a/v, external pudendal a/v, inferior rectal vessels | uterine a/v, ovarian a/v | testicular a/v, deep / dorsal a. of penis, dorsal veins |
| Viscera | rectum, anal canal, bladder | | |

Coverage after Q336 (✓ real geometry, R rule-based, + added this round, T text-only explanation added this round, – missing):

| | Base · Female | Base · Male |
|---|---|---|
| Pelvic diaphragm | ✓ (Z) ; tendinous arch – | ✓ (Z) ; tendinous arch R |
| EAS / perineal body | R (her rules) / ✓ CVH | ✓ Z (25 mm too high) / – |
| Transverse perineals, BS, IC, ext. urethral sphincter | ✓ CVH | – (T: "External urethral sphincter") |
| Perineal membrane | T | T |
| Colles' fascia | T (Q298) | T (Q298) |
| Ischioanal fossa | ✓ in deep pelvic fat (T alias) | ✓ in deep pelvic fat (T alias) |
| Vulva skin: mons, labia, vestibule | **+ `skin_vulva_cvh` (CVH, registered)** ; T aliases | T |
| Clitoris / bulbs / Bartholin | ✓ CVH (T alias "clitoris") | — |
| Paraurethral glands, hymen | T / – | — |
| Penis, testis, epididymis, ductus, seminal, prostate | — | ✓ Z |
| Bulbourethral gl., spermatic cord, cremaster, dartos, tunica vaginalis | — | T |
| Pudendal n. / internal pudendal a/v | ✓ | ✓ |
| Inferior rectal n., perineal n. | – / T | – / T |
| Dorsal n. of clitoris / penis | – (held Q252) | R |
| Ovarian / testicular vessels | – | ✓ Z |
| Rectum / anal canal | ✓ CT rectum / T | – / T |

## 3. What changed

**(a) Skin — Base · Female** (`scripts/anatomy/q336/vulva_skin_q336.py`): new structure `skin_vulva_cvh`, "Vulva and perineal skin
(CVH, registered)", sys skin, appended as the last mesh. Source: Chinese Visible Human female skin (Wu et al. 2015, CC BY 4.0,
`third_party/cvh_wu2015` mesh 46). Placement: CVH bones onto this page's hip bones / sacrum / coccyx (rigid + uniform scale ×1.133,
residual median 4.11 / p90 7.78 mm — the transform the CVH perineal structures follow), then ONE similarity transform (×0.835, 8.1°,
shape unchanged) onto the page's skin in a 70 mm band around the opening (band distance median 5.0 / p90 14.7 mm). The surface sits
median 9.5 / max 24.3 mm from the organ-consistent (bone-only) placement. Cut to the opening dilated 25 mm, border tucked **under** the
neighbouring patches (faces standing > 3 mm in front of a neighbour removed), 3 mm closed slab like every Z patch (2,976 vertices,
6,020 triangles, 24.1 cm³; 4 non-manifold edges inherited from the CVH source). **Not welded and not deformed** — an attempt with a
smooth non-rigid fit + harmonic border weld (first version of the script) folded the labia into the male-shaped slot (edge-length
ratio p10–p90 0.43–1.75, border moves up to 56 mm) and was dropped. See-through rays: 74 % → 12 % (source's own introitus / meatus
openings capped for the count; 17 % uncapped). L/R mirror distance of the surface median 2.6 / p90 8.0 mm (a real vulva; the Z
neighbours are exact mirrors, 0.01 mm), centroid x = 1.35 mm. Its card carries source, method, numbers and limits; the 10 neighbouring
skin cards' Q297 "honest hole" note and 17 CVH cards' "no vulvar skin" sentences get a Q336 correction.
Remaining: a recessed strip between the posterior commissure and the anal-region patch (the CVH perineum lies 20–30 mm deeper than this
body's Z thigh / anal skin), and the vestibule lies ~5–9 mm from the HRA vagina / CVH urethra ends (surface features, not channels).

**(c) Text-only records** (`scripts/anatomy/q336/records_q336.py` → `data/anatomy/synonyms_q306.json`, compiled per page by
`build_search_q306.py`): labia minora, labia majora, mons pubis, vestibule, clitoris (aliases onto the shipped meshes on Base · F),
paraurethral gland, perineal membrane, external urethral sphincter, bulbourethral gland, spermatic cord, cremaster, dartos, tunica
vaginalis, ischioanal fossa (alias onto the deep pelvic fat), pudendal canal, anal canal, perineal nerve; "Female perineal skin"
corrected (ships on Base · F). Entries that ship somewhere carry `corrected_by: Q336` + "SHIPS" (the Q308 presence guard in
`tests/test_q308.py` now accepts that declaration).

**(b) Real geometry not added**: no vetted source holds male perineal muscles except the rule-based segmentation of the Visible Human
male on the frozen Imaging·Male page; carrying it onto Base · Male needs a Combined·M → Base·M bone TPS (owner decision).

## 4. Apply (order matters; nothing to do before step 1 lands on the page)

    python3 scripts/anatomy/q336/apply_q336.py --root build/q309
      1. vulva_skin_q336.py --page-dir build/q309/viewer_base_female --write
            -> atlas_viewer_base_female_geo_03.txt, atlas_viewer_base_female.html, index.html (+ *.q336 backups)
            -> data/anatomy/pose_rig_base_f.json  (one rigid entry appended in the pelvis segment, every other entry kept)
            -> data/derived/Q336_vulva_skin_report.json
      2. records_q336.py --write --require-page build/q309/viewer_base_female   -> data/anatomy/synonyms_q306.json
      3. build_search_q306.py --src build/q309 base_m base_f                    -> data/derived/Q306_search_base_{m,f}.json
    then the regen with, in addition to the usual list: atlas_viewer_base_female_geo_03.txt, __ANATOMY_manifest, __ANATOMY_files,
    nmsk-pose-rig, nmsk-q306.

Verification on a private copy (isolated clone, /dev/shm/q336w → regen /dev/shm/q336r): REGEN_TEMPLATE_ONLY_OK (2 pages);
`scripts/anatomy/q336/verify_q336.py` 20/20 OK, 0 page errors; `verify_search_q319.py` Q319_SEARCH_OK on Base · F;
`tests/test_q336.py`, `test_q306.py`, `test_q308.py` pass (`test_q298::test_relations_exist…` fails before and after: pre-existing).
