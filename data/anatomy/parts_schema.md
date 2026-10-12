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
Rules: `z_part_mesh` (Z bodies only; the dedicated Z-Anatomy part mesh), `end_snap_bone` (the mesh end of the muscle touches the bone within a tolerance; point = nearest bone-surface point to the contact-patch centroid; error = patch radius), `cc_ligament_ratio` (Rios 2007 ratios along the clavicle), `mtj_by_distance_from_origin` (Miller 2007: 99 +/- 15 mm from the ischial tuberosity), `mtj_interface` (muscle meets tendon mesh), `passage_contact` (nerve mesh meets fascia/muscle mesh within 3 mm).
`source_class`: `rule_based` (rule applied to the person's own mesh), `z_fill` (Z-Anatomy part mesh as fitted; error from the structure's own fit badge), `transferred` (unused in phase 1). **Never `measured`.** The deltoid sector rule (azimuth about the humeral head) was validated against the Z parts and rejected (6-40 mm centroid error): deltoid heads are text-only on the two own bodies.

## Ambiguity recorded
The owner's word for the "rectum / rectus" passages is ambiguous. Both are covered: rectus abdominis tendinous intersections, rectus sheath (anterior / posterior layers, arcuate line), linea alba and the umbilical ring; and rectum / anorectum (lateral ligament, Denonvilliers and rectosacral fascia, puborectalis sling, pudendal canal).

## Q222 extension
`added_in` (`"Q219"` | `"Q222"`) on every row says which pass added it. Q222 rows live in `scripts/anatomy/q219/rows_q222_*.py` (auto-imported by `build_parts.py` and `build_geometry.py`) and use references from `scripts/anatomy/q219/refs_q222.py` (`verified: "pubmed-2026-10-12"`; every entry's `basis` begins `abstract:` = what the PubMed abstract supports; one registry entry per PMID; the builder refuses duplicate keys / PMIDs). All Q222 rows are `verified` (a journal record whose abstract/title holds the claim); where the evidence is a single case report the row says `case report` in `variability`, where a prevalence is quoted from a review the row note says the primary studies were not retrieved. Disputed values are recorded, never merged: `part_sets` (77 now), and as ranges in `variability` (e.g. Gantzer's muscle 20.3 % imaging vs 48 % cadaver meta-analysis; palmaris longus absence 37.2 % vs 59.75 %).
