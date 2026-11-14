# Parts model schema (Q219, phase 1)

Anatomy layer, CC BY-SA 4.0 compatible: facts with citations and, separately, positions derived from the bodies' own meshes.
**No clinical content** (no motor points, no trigger points, no needle/risk data -- those stay in the private `clinical/` layer, Q187/Q188), and the owner's compiled muscle references (Q60 `clinical` blocks) are not copied here.

Files
- `data/anatomy/structure_parts.json` -- the table (built by `scripts/anatomy/q219/build_parts.py` from `scripts/anatomy/q219/rows_*.py` + `refs.py`).
- `data/derived/Q219_structure_ids.json` -- snapshot of the structure ids of the four bodies (so tests run without `build/`).
- `data/derived/Q219_parts_coverage.json` -- which structures of the entity list have parts, which not.
- `data/derived/Q219_parts_<vhm|vhf|zan_m|zan_f>.json` -- per-body positions (atlas mm) + the text-only list; `data/derived/Q219_rule_validation.json` -- how the rules were checked.

## Part types
| `part_type` | meaning | examples |
|---|---|---|
| `head_belly` | a head, belly, compartment or segment of a muscle | deltoid clavicular / acromial / spinal; biceps long / short head; pronator quadratus superficial / deep |
| `origin_part` | one origin site or head of origin | semimembranosus ischial origin; rectus femoris direct / reflected head; long head of biceps on the supraglenoid tubercle |
| `insertion_point` | one insertion arm / slip / footprint | semimembranosus arms (3, 5 or 6 depending on the source); tibialis posterior bands, with prevalence; fibularis longus slips |
| `ligament_component` | a proper / accessory / band / bundle / layer of a ligament, tendon or fascia | finger proper vs accessory collateral ligament + volar plate; ACL bundles; deltoid ligament bands; flexor pulleys; rectus sheath layers; linea alba regions |
| `muscle_tendon_junction` | a located MTJ zone, an intramuscular-tendon system or a tendinous intersection | rectus abdominis tendinous intersections; deltoid intramuscular tendons; hamstring proximal MTJ |
| `fascial_passage` | where a nerve / vessel / tendon / organ crosses, pierces or runs under a fascia, retinaculum, ligament or aponeurosis | superficial fibular nerve through the crural fascia; carpal tunnel; arcade of Frohse; rectosacral fascia; pudendal canal |

## Row fields (`parts[]`)
`id` (`<structure_id>.<slug>`, unique) - `structure_id` (side-agnostic; resolves to a `data/` record base id or a body structure id, `zan_` prefix optional) - `structure_class` - `part_type` - `name` - `description` - `anchor` (bone/landmark where the source gives one) - `passes` (fascial passages: kind, traversing ids/text, through) - `related_structure_ids` - `set_id` (a count that the literature disputes) - `variability` (prevalence) - `evidence` (specimen type and n) - `refs` (keys into `references`) - `citation` (generated human-readable string with DOI and PMID) - `verification` - `note` - `geometry` (rule request, see below) - `maps_to` (`structure_ids` and dedicated `part_ids` present in each of the 4 bodies) - `resolved_in`.

- `verification = "verified"`: the claim is in the abstract/title of the cited PubMed record (title, authors, journal, year, volume, pages, DOI and PMID were taken from the PubMed record). `"unverified"`: textbook (Gray's 42nd, Moore 9th; edition only, **page not checked**) or owner-statement; such rows say so in `note`/`evidence`.
- `references{}`: `kind` journal (with `pmid`, `doi`, `basis` = what the abstract says) or textbook/owner.
- `part_sets[]`: when sources disagree on a count (e.g. semimembranosus insertions 3 / 5 / 6; deltoid parts 3 / 7; ACL bundles 1 / 2 / 3), the counts are listed with their source -- the viewer must not hard-code one number.
- Side-agnostic ids: the table has one row for `deltoid`, never `deltoid_r`; `maps_to` lists the `_r`/`_l` meshes per body.

## Geometry (separate files, `Q219_parts_<body>.json`)
Only parts with a documented rule on the body's own meshes get coordinates; every other part is listed under `text_only` with the reason.
Rules: `z_part_mesh` (Z bodies only; the dedicated Z-Anatomy part mesh), `end_snap_bone` (the mesh end of the muscle touches the bone within a tolerance; point = nearest bone-surface point to the contact-patch centroid; error = patch radius), `cc_ligament_ratio` (Rios 2007 ratios along the clavicle), `mtj_by_distance_from_origin` (Miller 2007: 99 +/- 15 mm from the ischial tuberosity), `mtj_interface` (muscle meets tendon mesh), `passage_contact` (nerve mesh meets fascia/muscle mesh within 3 mm), `collateral_layer_split` (Q319: a joint's collateral band split into its DORSAL proper and VOLAR accessory layer at the published dorso-volar level of the proper footprint -- Carlson 2012 for the thumb MCP -- on a joint frame built from the body's own bones; the point is a vertex of the body's own band, the error is dorso-volar: sqrt(reference distance^2 + half the published footprint height^2 + half the layer's own thickness^2 + 1 mm grid^2)).
`source_class`: `rule_based` (rule applied to the person's own mesh), `z_fill` (Z-Anatomy part mesh as fitted; error from the structure's own fit badge), `transferred` (unused in phase 1). **Never `measured`.** The deltoid sector rule (azimuth about the humeral head) was validated against the Z parts and rejected (6-40 mm centroid error): deltoid heads are text-only on the two own bodies.

A ligament the literature divides into sub-ligaments (owner, Q319.4.iii: "proper + accessory in the ulnar collateral ligament of MCP1") is recorded as one `ligament_component` row per sub-ligament, grouped by a `part_set` that carries the reported count. Recording is not marking: a sub-ligament is only placed where Z-Anatomy ships a dedicated mesh for it (`z_part_mesh`) or a rule separates it out of a pooled mesh (`cc_ligament_ratio` for the conoid and trapezoid, `collateral_layer_split` for the thumb MCP collaterals). Where neither holds -- the finger MCP and the interphalangeal collaterals of the hand, whose pooled Z mesh has no published dorso-volar footprint to split it by -- the sub-ligaments stay `text_only`, with their reason, rather than being placed by eye.

## Ambiguity recorded
The owner's word for the "rectum / rectus" passages is ambiguous. Both are covered: rectus abdominis tendinous intersections, rectus sheath (anterior / posterior layers, arcuate line), linea alba and the umbilical ring; and rectum / anorectum (lateral ligament, Denonvilliers and rectosacral fascia, puborectalis sling, pudendal canal).

## Q222 extension
`added_in` (`"Q219"` | `"Q222"`) on every row says which pass added it. Q222 rows live in `scripts/anatomy/q219/rows_q222_*.py` (auto-imported by `build_parts.py` and `build_geometry.py`) and use references from `scripts/anatomy/q219/refs_q222.py` (`verified: "pubmed-2026-10-12"`; every entry's `basis` begins `abstract:` = what the PubMed abstract supports; one registry entry per PMID; the builder refuses duplicate keys / PMIDs). All Q222 rows are `verified` (a journal record whose abstract/title holds the claim); where the evidence is a single case report the row says `case report` in `variability`, where a prevalence is quoted from a review the row note says the primary studies were not retrieved. Disputed values are recorded, never merged: `part_sets` (77 now), and as ranges in `variability` (e.g. Gantzer's muscle 20.3 % imaging vs 48 % cadaver meta-analysis; palmaris longus absence 37.2 % vs 59.75 %).

## Q256 extension: origin / insertion for tendons, ligaments and fascia
`scripts/anatomy/q219/rows_q256_attachments.py` extends the `origin_part` / `insertion_point` / `muscle_tendon_junction` part types (previously
muscles only) to every record in `data/tendons/*.json` (51), `data/ligaments/*.json` (91) and the subset of `data/fascia/*.json` (31 of 104)
that lists exactly two bony attachments, generated programmatically from those files' own already-authored `attachments`/`bony_attachments`
fields and citing their own `source` string verbatim in each row's `note`. Convention used (stated in every such row, not an anatomical fact):
a ligament's or fascia's `bone_a`/first-listed attachment is called "origin", `bone_b`/second "insertion" purely for consistency with the
muscle markers -- ligaments and fascia have no contractile pull direction. A tendon's proximal (muscular) end is a `muscle_tendon_junction`,
its distal (bony) end an `insertion_point`. Geometry reuses `end_snap_bone` (generalised: it was already generic to any one mesh + one named
bone, the "muscle" in its old method string was cosmetic) and `mtj_interface`, unchanged. Deliberately NOT given an origin/insertion pair:
73 of 104 fascia records (0 or 1 or >2 listed bony attachments: see `data/derived/Q256_attachment_coverage.json` for the exact list and
reason per id -- most commonly "blends into adjacent fascia / skin only" or "a free margin at the other end"); per-band sub-attachments
within a multi-band ligament (e.g. the ACL's separate anteromedial/posterolateral footprints) -- only the ligament-complex-level attachment
is covered this round. Midline records (no left/right mesh at all, e.g. `ligamentum_flavum`, `linea_alba`, `central_tendon_diaphragm`) get
the catalogue row (visible as text) but no `geom` key: `build_geometry.py`'s per-side resolver only ever tries sides `"r"`/`"l"`, so giving a
midline structure a geometry rule would silently duplicate one real point under both a spurious "r" and "l" tag instead of placing it once.

## Q243 extension: HRA organ parts
`data/anatomy/structure_parts_hra_q243.json` (same row fields; `part_type` = `organ part`: a named sub-part / region of an organ taken from a reference atlas, e.g. the fundus, walls, cervical os of the uterus or the ampulla / isthmus / infundibulum / fimbriae of the uterine tube; `references` = the HRA 3D Reference Object Library object with DOI, kind `database`; `verification` `verified` = read from the library itself, no PubMed record involved).
Rows are NOT in `structure_parts.json` (that table is literature-based and `build_parts.py` / `tests/test_q219.py` keep their meaning). The parts are only offered for structures that ARE the HRA geometry on a page (the uterus and tubes of Q233): markers per body in `data/derived/Q243_parts_hra.json` (class `hra_reference`, error bound = the p90 of the bone registration, checked against the shipped mesh) and added to a page's `parts_data.json` by `python3 scripts/anatomy/q243/parts_hra.py --inject PAGE_DIR --body vhf|zan_f|zbase_f` (rows tagged `q: "q243"`, idempotent). The bladder sub-parts of the HRA are not offered: no page carries the HRA bladder.

## Q323 extension: muscle-level origin / insertion, two-bone end assignment
`scripts/anatomy/q219/rows_q323_muscle_attachments.py` (imported last by `build_parts.py` / `build_geometry.py`) adds one `origin_part` and one `insertion_point` per `data/muscles/*/*.json` record (`attachments.origin_bone|insertion_bone` + landmark text, the record's `source` quoted verbatim in `note`, `unverified`/textbook), unless a curated row of that type with a geometry rule already exists for the structure. Report: `data/derived/Q323_muscle_attachment_rows.json`.
Geometry is `end_snap_bone` with `other_bone` (`build_geometry._two_bone_end`): the two mesh ends (axis PCA, 12 % cap) are assigned to the two named bones by the lower total gap, and the assignment must win by >= 3 mm (else "ambiguous", text-only); the same bone at both ends is always text-only. Bounds: end-to-bone gap <= `tol_mm` (muscles 8, ligaments 10, fascia 12), snapped point <= `tol_mm` + 2 mm from the structure's own end vertices, error bound (max(patch radius, median gap) + 1 mm) <= `max_err_mm` (40 for the muscle rows). One point per named bone field, at the footprint centre; a bone group (`ribs`, `carpals`, `phalanges_hand`, `cervical_vertebrae` ... `BONE_GROUPS`) resolves to its member meshes and the point lands on the member touched. Q256 ligament and retinaculum rows use the same two-bone assignment; Q256 fascia sheets and tendons pass `other_bone: None` (each bone takes the nearest end, ambiguity-checked: a sheet may meet both its bones along one margin). No proximal/distal convention is used by this branch. Rows without geometry carry `geometry.why` (placeholder bone, midline record, record split over several Z part meshes). Computed on the two Base bodies only (`Q220_parts_zbase_*.json`); the frozen bodies' `Q219_parts_*.json` list the Q323 rows as text-only with that reason.
