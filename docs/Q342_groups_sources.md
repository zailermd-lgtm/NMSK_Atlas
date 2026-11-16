# Q342 — data for muscle parts, myofascial lines and innervation groups (Base pages only)

Owner request (2026-11-15): select fibre groups / heads instead of the whole muscle; add a group family
"Anatomy Trains" with sub-choices (vertical, horizontal, diagonal …); add an innervation family with the
sub-menu root / peripheral / central (e.g. flexor posture). This round is the **data**; the UI is Q343.

Files (all `data/anatomy/`): `muscle_parts_q342.json` (nmsk.muscle_parts.v1), `myofascial_lines_q342.json`
(nmsk.myofascial_lines.v1), `innervation_groups_q342.json` (nmsk.innervation_groups.v1). Test:
`tests/test_q342_groups.py`. Generators were scratchpad scripts; the JSON files are the product, and each
file documents its schema in its `doc` block. Structure ids come from the page manifests of
`build/q309/viewer_zan_atlas/index.html` (base_m, 3264 meshes) and `build/q309/viewer_base_female/index.html`
(base_f, 3300 meshes); ids are listed per body and per side, so body-specific ids are explicit.

## 1. Coverage

| file | content |
|---|---|
| muscle_parts | 32 muscles (31 with named parts), 81 parts. Per body (identical on M and F): **22 separate meshes**, 2 separate rule-based meshes (rectus femoris reflected head, psoas minor), **19 need a rule** (trapezius ×3, latissimus ×4, biceps brachii ×2, adductor magnus ×2, gastrocnemius ×2, rectus abdominis ×4, sternocleidomastoid ×2), **38 not delimitable honestly**, 0 missing. |
| myofascial_lines | 15 lines: Myers' 12 (SBL, SFL, LL, SL, DFL, 4 arm lines, BFL, FFL, ipsilateral FL) + the 3 arm chains of Wilke & Krause 2019. 149 stations, 148 on the pages (no patellar-ligament mesh). |
| innervation_groups | 214 muscles (60 from innervation_q322 with their reviewed root ranges, 154 from the repo muscle records), 188 on the Base pages; root family 30 spinal levels + 9 cranial-nerve groups (7 muscles have no level in their source text, e.g. "segmental dorsal rami"); peripheral family 142 nerve nodes (109 with direct members), cranial nerves included; central family 23 patterns, 22 usable (LL flexion synergy unsourced this round), 202 rule-derived memberships. ISNCSCI key muscles flagged at C5–T1, L2–S1. |

Separate part meshes on both pages: pectoralis major (clavicular, sternocostal, abdominal), deltoid
(clavicular, acromial, spinal), triceps (long, lateral, medial), FDS (humero-ulnar head; plus a generic
"Flexor digitorum superficialis" mesh lying along the radius — *probably* the radial head, name not
confirmed), erector spinae columns (iliocostalis, longissimus, spinalis, with Z colli/capitis pieces —
iliocostalis colli exists on the left only), iliopsoas (psoas major, iliacus), adductor minimus, levator ani
(pubococcygeus, pubo-analis, iliococcygeus + a remaining "levator ani" mesh).

## 2. Sources

**Opened this round (PubMed abstract unless stated):** Wilke 2016 Arch Phys Med Rehabil (PMID 26281953,
doi 10.1016/j.apmr.2015.07.023 — abstract only); Krause 2016 J Anat (27001027; PMC full text came back
empty); Wilke & Krause 2019 Clin Anat (31226229); Hefter 2012 Int J Rehabil Res (22555318); Filippetti 2024
J Rehabil Med (39185546, **PMC full text**); EURO-MUSCULUS/USPRM spasticity guide, Güvener 2026 Eur J Phys
Rehabil Med (doi 10.23736/S1973-9087.26.09497-9, **full text**, owner-supplied PDF, already used in Q322);
Mayer 1997 Muscle Nerve Suppl (9826981) and Esquenazi 2004 J Head Trauma Rehabil (15247822) — abstracts
only, no pattern-to-muscle lists in them, not used; Bhatt 2013 (24403744); Urquhart 2005 (15698694); Grimaldi
2009 (19121974); Ramirez 1984 (6505096); Gottschalk 1989 (2621137); Beck 2000 (10813169); Agur 2003 (12794910);
Godat 2004 (15220562); Cho 2023 (37430018); one knee trial describing deep-front-line tissues (40092708, full
text; not cited in the data). Via the Consensus search tool (abstracts): Kalichman 2025, Petrov 2026, Moore
2023, McPherson 2019, Avni 2024, Sheffler 2015.
**Reused from the repo (verified by earlier rounds on PubMed):** the references of
`data/anatomy/structure_parts.json` (rispoli2009, sakoma2011, fung2009, castanov2019, maguchi2026, takizawa2014,
kearney2004, …), the Q322 sources (isncsci2019, tsao2003, levin1996), `muscle_heads_q293.json`, the muscle
records' compartment nerve branches, `muscle_actions_q283.json`, the nerve registry `data/nerves/*.json`.

**Not opened (named only, flagged in the data):** Myers, *Anatomy Trains* (book) — the station lists are the
standard published routes recorded without the book, every Myers line has `verify_against_book: true`;
Wilke 2016 full text and its per-transition table (archives-pmr.org, pmc.ncbi.nlm.nih.gov and the PDF mirrors
are not reachable from this session); Schultz & Feitis 1996 *The Endless Web* (only its table of contents was
seen in a web search); Brunnstrom 1970; Hefter 2012 full text; Gray's Anatomy 42nd ed. (repo rows marked
`unverified_textbook`).

## 3. Contested or missing — needs the owner's decision

1. **"Horizontal" lines do not exist** in Myers' system or in any review opened. The only sourced horizontal
   concept is Schultz & Feitis' "body retinacula (bands/straps)" (chest band, inguinal band …), known here only
   from a table of contents, without members. The sub-choice is in the data as `not_offered` with its reason.
   Options: (a) leave it disabled; (b) obtain the book / a source listing the bands' structures; (c) rename the
   owner's "horizontal" to "arm lines" (Myers draws them with the arm abducted) — not recommended without a source.
2. **Evidence labels** (Wilke 2016 abstract): strong — SBL (3/3 transitions, 14 studies), BFL (3/3, 8), FFL
   (2/2, 6); moderate — Spiral Line (5/9, 21), Lateral Line (2/5, 10); none — SFL (0 verified, 7 studies);
   not examined — DFL, ipsilateral FL, Myers' four arm lines. Wilke & Krause 2019 found three *different* arm
   chains with "good evidence". Continuity ≠ force transmission (Krause 2016: moderate for SBL, partial BFL,
   negligible FFL); Petrov 2026 (one cadaver) found superficial lines only with added fascia and the DFL
   inseparable from viscera. Which transitions are verified is in the Wilke 2016 table, **not extracted**.
3. **Ipsilateral Functional Line** route is recorded with lower confidence (later edition of the book).
4. **Part rules are proposals.** The project rejected a deltoid sector rule after validation (Q219). The
   fan-projection rule can be validated on pectoralis major (three real part meshes) before any rule-based
   part is drawn; the others have no validation mesh and can only be shown as explicitly rule-based overlays.
5. **Hefter patterns II and V** are incomplete in the opened sources (only "extended wrist" / "extended
   elbow"); pattern IV is taken from Filippetti's "similar" MS pattern. The Hefter 2012 table would settle it.
6. **Lower-limb flexion synergy** and **decorticate / decerebrate postures**: no muscle-level source opened —
   not offered. "Striatal toe" is not used (the guide says hitchhiker's great toe / great-toe hyperextension).
7. **Pattern membership is rule-based** (sourced posture × sourced muscle action), tiered by how directly the
   guide supports it; members whose actions oppose another component are marked `opposes`.
8. FDS "radial head" = the generic FDS mesh by position only; vastus medialis VMO/VML and gluteus medius
   parts are contested in their own literature (recorded in `contested`).

## 4. UI data contract ("Related structures" menu)

- **Side handling (all three):** every structure list is `{base_m|base_f: {r:[], l:[], mid:[]}}`. Default to
  the side of the clicked structure; if that list is empty for the body (one-sided or mis-suffixed midline
  meshes) fall back to `mid`, then to both sides. Never borrow ids across bodies.
- **Parts:** on a muscle card, if `muscle_id` (or a part id) matches an entry with parts → "Parts" chooser:
  whole muscle (`whole_muscle_structures`, or the union of separate parts when null) + each part.
  `separate_mesh` → select; `separate_mesh_rule_based` → select with badge; `rule` → disabled
  "rule-based, not validated" until an implementation passes `rules[name].validation_plan`; `not_delimitable`
  → text row (name, nerve, source), no geometry.
- **Myofascial lines:** family → `sub_choices` (vertical / diagonal_spiral / functional / arm; horizontal
  disabled with `why`) → lines containing the clicked structure (match any station's ids) with the
  `evidence.label` badge and `label_text` always visible → selecting marks station structures; station `side`
  S = clicked side, O = other side, mid/B = both. Default view: stations whose `kind` contains "muscle".
- **Innervation:** family → root | peripheral | central.
  Root: `muscles[clicked].motor_levels` → choose level → `families.root.levels[L].members` (flag
  `isncsci_key_muscle`); cranial-nerve muscles use `families.root.cranial`.
  Peripheral: `muscles[clicked].nerves` + parent chain (`families.peripheral.nerves[n].parent`) → choose
  nerve → `all_members` (`via` tells which branch).
  Central: patterns with `status == "ok"` whose `members` include the clicked muscle → choose pattern → mark
  members of tiers `named_in_guide` + `guide_section_and_action` by default, others on "show all"; always show
  the rule-based badge and `components` (with source). Central patterns are one-sided (clicked side).
- Map a clicked mesh to a muscle id through `muscles[*].structures` (innervation) or the parts/whole lists
  (parts file); several muscles can share a mesh (e.g. iliopsoas parts).
