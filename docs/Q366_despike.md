# Q366 — Base·F: body-wide guarded de-spike against the Base·M source mesh

Script: `scripts/anatomy/q366/despike_q366.py` · report: `data/derived/Q366_despike_report.json` · tests:
`tests/test_q366_despike.py`. Base·F only; Base·M (`viewer_zan_atlas`) is read, never written. Frozen pages untouched.

## Finding

Q364 measured registration SPIKES on Base·F: single vertices or small patches displaced 3–8.5 mm from where a clean fit of the
same Base·M mesh puts them (orbit muscles, lacrimal gland, optic nerve, temporal vessels). Q364 refitted only the globes. Q366
measures the whole body and repairs only those vertices.

## Method

For every Base·F structure with a same-topology twin on Base·M (same id, same vertex count, identical triangles) the vertex order
is a correspondence x_M → x_F.

* **Local map.** Per vertex i: its K = 64 nearest Base·M neighbours in the same structure (i and any coincident copy left out).
  The map from their Base·M positions to their Base·F positions is a similarity (Umeyama) plus an affine deviation ridge-regularised
  towards it (λ = 0.1 × neighbourhood variance / 3). It is fitted robustly: a 50 %-breakdown start (each neighbour's displacement
  against the component-wise median), two Cauchy reweightings (2.385 σ), then four Tukey-biweight reweightings (4.685 σ,
  redescending: a spike patch gets weight 0), with σ = 1.4826 × median residual, floor 0.15 mm. Each vertex has its own map, so a
  tube bent through 2.5 rad by the warp is followed (unit test: not one vertex flagged, while a single rigid fit puts > 30 % of
  it more than 3 mm off).
* **Residual.** p_i = x_M,i through its own map; r_i = |x_F,i − p_i|. Spread s_i = 1.4826 × median of the neighbours' r (floor
  0.05 mm, the page quantum is ~0.01 mm).
* **Flag (hysteresis).** Seed: r > **1.0 mm** AND r > **10 × s**. Grown over mesh edges into neighbours with r > 0.5 mm AND
  r > 4 × s (the shoulders of a spike go with its tip). Flagged vertices are then left out of every neighbourhood and the maps
  refitted (3 passes), so a spike never steers its own correction.
* **Patch checks.** A connected flagged patch is dropped (left as it is) if it has more than 12 vertices (a region that moved,
  not a spike: 80 patches), if any member keeps fewer than 32 unflagged neighbours, or if its refitted correction exceeds
  max(1.5 × r, r + 1 mm) of the first pass (unstable: 42 patches). A patch whose correction would put a vertex into a bone, or
  deeper into one, is dropped (246 patches / 598 vertices in 166 structures, mostly intervertebral discs against the refitted
  vertebrae, the nasolacrimal duct / sac against the lacrimal bone, subscapularis against the scapula).
* **Move.** A flagged vertex goes to p_i: its own Base·M position through the measured local warp of its unflagged neighbours.
  Nothing else moves (unflagged vertices of a changed structure differ only by the re-quantisation, ≤ 0.004 mm). No Laplacian
  or other smoothing, nothing invented.

## Thresholds and their evidence

First-pass residuals over the 1,193,394 binned vertices of the 2,374 examined structures (report `histograms`):

| r (mm) | 0–0.1 | 0.1–0.3 | 0.3–0.5 | 0.5–1 | 1–2 | 2–4 | 4–6 | 6–8 | 8–15 | > 15 |
|---|---|---|---|---|---|---|---|---|---|---|
| vertices | 563,920 | 276,199 | 110,741 | 117,170 | 73,317 | 36,579 | 9,233 | 4,082 | 1,959 | 194 |

Median 0.11 mm, p90 1.05, p99 4.5, p99.9 9.5 mm. Most large residuals sit in neighbourhoods that are noisy as a whole (the
registration's broad roughness); a spike is a residual far above its own neighbourhood. The ratio r / s for r > 1 mm:

| r/s from | < 2.2 | 2.2 | 2.9 | 3.7 | 4.7 | 6.1 | 7.8 | **10** | 12.8 | 16.5 | **21** | 27 | 35 | 45 | 57 | 74+ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vertices | 98,844 | 5,033 | 2,973 | 1,911 | 1,342 | 968 | 783 | **723** | 764 | 802 | **912** | 718 | 415 | 340 | 220 | 553 |

(log bins, lower edges.) The bulk decays to a trough at r/s ≈ 10–13 and a second population peaks at ≈ 21: the spikes.
K_HI = 10 sits at the trough. Among r/s > 10 the residuals are: 0.3–0.6 mm 8, 0.6–1 mm 188, 1–1.5 mm 1,238, 1.5–2 mm 1,002,
2–3 mm 997, 3–4 mm 395, 4–6 mm 569, 6–8 mm 1,042 (the 6.3 mm signature of the head spikes), 8–12 mm 97, > 12 mm 107: the
outlier population starts at 1 mm, hence T_HI = 1.0 mm.

## Guards (per structure; a failing structure is left exactly as it is and listed in `held`)

* (a) **bone** — Q357's test (generalised winding number > 0.5 against the page's bones, oriented by signed volume; depth by
  closest point): no moved vertex newly inside a bone, none deeper than before by > 0.1 mm. Applied to every bone, allowed
  passages of `data/anatomy/q357_in_bone_allow.json` included (a vertex already in a canal may not go deeper either).
  After the patch step: 0 structures fail it.
* (b) **size** — surface area and, for a closed mesh, enclosed volume: change ≤ 2 %, or else not more than 2 %-points further
  from the reference size (the Base·M mesh through the smooth local maps, which carries her anisotropic scale but not the spikes).
  Spikes inflate area: e.g. lacrimal artery −34 % area, from 56 % to 3 % off the reference.
* (c) **shared borders / contact** — EXCLUDED: the skin layer (230: slabs welded at load on identical border vertices, Q334),
  the bones (250: the reference layer of every contact round; measured, not moved) and every structure written by a geometry round
  since Q318 (194: found from the page's own `*.q318` backups — any structure whose geometry differs or that is new — plus any card
  with a later round's note; this covers Q333, Q336, Q340, Q349, Q353, Q357, Q358, Q360, Q364, Q365; Q350 changed records only).
  FROZEN (never moved): vertices within 1.0 mm of an excluded non-bone structure (contact made by those rounds) and vertices within
  0.02 mm of another structure's vertex (shared borders): 54,013 vertices, of which 789 were spike seeds — left, counted.
* (d) **flips** — faces whose normal opposes the Base·M face carried through the local maps may not increase.
* move cap 12 mm.

## Totals (dry run = write run on the private copy)

| | |
|---|---|
| structures on the page | 3,313 |
| skipped: no same-topology twin | 265 (79 no Base·M id — rule-based / female-only; 171 other vertex count; 15 other triangles) |
| excluded (skin 230, bone 250, later rounds 194) | 674 |
| examined | 2,374 |
| corrected | **649** structures, **3,421** vertices, 2,073 patches |
| held by a guard | 21 (size 16, flips 4, size + flips 1) |
| move | max 11.5 mm, p95 6.3 mm, mean 2.8 mm; 145 structures moved > 6 mm, 301 > 3 mm |

Corrected by layer: muscle 208 (1,108 vertices), vessel 131 (636), joint 68 (346), nerve 65 (443), cns 62 (290), bursa 54 (244),
cartilage 19 (97), fascia 13 (117), lymph 14 (59), viscera 14 (71), ligament 1 (10). Largest: superior gluteal arteries
11.5 mm (8 vertices each), intervertebral disc T1–T2 11.3 mm, C7–T1 9.4 mm, serratus anterior (L) 8.6 mm; the head's
extra-ocular muscles, levator palpebrae, lacrimal glands and arteries, straight gyri, pharyngeal constrictors ~6.3 mm.

Held (left as they are): adductor brevis L/R, coracobrachial bursa R, nucleus pulposus L5–S1 (flips); annular ligament R,
external anal sphincter, discs T5–T6 / T9–T10, zona orbicularis L/R, palmar interphalangeal ligaments L/R, several lymph-node
groups, quadrangular membrane L, sphenomandibular ligament L, median cubital vein L, superficial epigastric / deep external
pudendal arteries (size).

## Writing

Vertex / triangle counts and order unchanged; changed files kept beside themselves as `*.q366`; each changed card gets a
"Q366: …" note; a page already carrying it is refused. `--write` into `build/` needs `--allow-build`.
**Pose rig:** `data/anatomy/pose_rig_base_f.json` keys its per-vertex weights by structure order and vertex count only; both are
unchanged and no skin vertex moves, so it needs **no re-encode** (the script checks count and `nv` after writing). The search
index does not read geometry or card notes: no rebuild.

## What is left

* Broad registration roughness (residual high but not far above its neighbourhood: 99th percentile 4.5 mm overall). By design
  this is not a spike and is not touched; smoothing it would re-sculpt the body.
* Spikes on excluded structures: the skin layer (measured: up to ~40 mm on `zan_skin_anterior_region_of_arm_r` in the first-pass
  screen), the bones, and the 194 structures later rounds wrote (their own rounds own them).
* 789 spike seeds frozen by contact / shared borders, 80 over-sized patches, 42 unstable patches, 246 patches that would enter a
  bone, and the 21 held structures.
* Structures with no same-topology twin (265).

## Verification (private copy, regenerated page)

Applied with `--write` to a private copy of `build/q309`, regenerated with `regen_template_only.py all` (template with the Q372
skin weld) → `REGEN_TEMPLATE_ONLY_OK`. Before / after renders on the SAME regenerated template (the before page is the regen with the pre-Q366
geometry spliced back), same cameras, skin / bone / fat hidden:

| region | verdict |
|---|---|
| orbit R / L (skull and skin hidden; front, top, side) | spikes gone: levator palpebrae crown, lacrimal gland, superior ophthalmic vein blob, muscle slivers; a few thin slivers left (frozen at the globe contact) |
| temporal vessels R / L | spikes gone: the triangular "flags" on the superficial temporal / deep temporal branches |
| face muscles | unchanged to slightly cleaner (temporal fascia edges); the face's roughness is broad, not spikes |
| pharynx / neck front | spikes gone on the nasopharynx and two vessel flags at the angle of the mandible; rest unchanged |
| hand L / R, forearm L | small spikes gone on digital vessels / fingers; forearm unchanged |
| pelvic floor | unchanged to slightly cleaner muscle edges (external anal sphincter held by the size guard) |
| superior gluteal arteries (largest move, 11.5 mm, 8 vertices per side) | no visible change from back / top / side; the flattened 'fin' where the branches part is broad, not a spike, and stays; nothing worse |
| intervertebral discs C7–T1, T1–T2 (9.4 / 11.3 mm) | spikes gone: the lateral blade on T1–T2 and the slab edge on C7–T1 |
| serratus anterior L (8.6 mm, 1 vertex) | unchanged at render scale |
| knee R | infrapatellar bursa spikes gone |
| foot L | small dorsal-digital spikes gone |
| thoracic discs / spine | disc tips slightly reduced; paraspinal muscle roughness unchanged (broad) |
| whole body front / back | unchanged at body scale |

Nothing looked worse than before in any pair.
