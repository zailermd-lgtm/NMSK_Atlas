# Geometry sources and licensing

This document records **where the 3D geometry in this project comes from, why
each source was chosen or rejected, and what obligations travel with it.**

The project's goal is a sub-millimetre anatomical model usable as a reference
atlas, as a correlate for ultrasound / CT / MRI, as a source of arbitrary
cross-sections, and as a substrate for musculoskeletal injection planning
(PRP, botulinum toxin for spasticity). That goal is commercial and
proprietary: the owner intends to sell derived content and to restrict
third-party reuse.

**That intent is the constraint that decides everything below.** A geometry
source whose license forces derivatives open cannot be used, no matter how
good the meshes are.

---

## The decision in one table

| Source | Resolution | License | Verdict |
|---|---|---|---|
| **Visible Human Project** (NLM) | 0.33 mm (F) / 1 mm (M) axial | US public domain; attribution requested | **Adopted** — substrate |
| **VH lower-extremity geometry** (Univ. of Denver) | segmented from the above | CC BY 4.0 *(verify — see below)* | **Adopted** — stage 1 |
| **TotalSegmentator v2.0.1** (Wasserthal et al., Univ. Hospital Basel) | clinical CT, 1.5 mm isotropic (this subject) | CC BY 4.0 | **Adopted** — stage 2, upper body/trunk |
| **SPARC / SCKAN** (NIH Common Fund) | connectivity statements, no geometry | CC BY 4.0 | **Deferred** — wrong domain; see below |
| **IT'IS Virtual Population** (Yoon-sun, Jeduk) | segmented nerve trajectories | commercial, paid | **Open question** — see below |
| **Z-Anatomy** / BodyParts3D | ~3.65 M polygons, unstated scale | CC BY-SA 4.0 | **Rejected** — share-alike |
| Parametric generation from atlas data | n/a | ours outright | **Rejected** — insufficient fidelity |

---

## Why Z-Anatomy was rejected

Z-Anatomy is a genuinely good atlas, and an earlier preview viewer in this
project was built on it. It is released under **CC BY-SA 4.0**.

The `SA` (share-alike) term requires that any derivative work be distributed
under the same license, which in turn grants every recipient the right to
use, modify, and commercialise it, and forbids adding restrictions. That is
directly incompatible with a proprietary product.

Two clarifications worth recording, because both are common misconceptions:

- **Modifying the meshes does not help.** Triangulation, decimation, axis
  conversion, quantisation, and batching change the *representation*, not the
  shape. The protected expression in a 3D anatomical model is the geometry
  itself. A modified mesh is a derivative work — which is precisely what
  share-alike is written to capture. There is no threshold of edits that
  escapes it, and a mesh changed enough to no longer be derivative would no
  longer be correct anatomy.
- **Share-alike does not forbid selling.** CC BY-SA permits commercial use.
  What it forbids is *exclusivity* — you cannot stop anyone else from doing
  the same with your derivative. That, not the commercial question, is what
  rules it out here.

No Z-Anatomy-derived geometry has ever been committed to this repository.

## Why parametric generation was rejected

Generating meshes from this atlas's own landmark, origin/insertion, and fibre
data would be unencumbered by construction. It was considered and rejected:
extruded or lofted geometry cannot support the clinical targets. Planning an
injection into a named compartment of a specific muscle, or correlating a
model against a real ultrasound image, requires true tissue boundaries taken
from a real body. Parametric geometry remains useful for the kinematic rig
(see `scripts/export_3d_scene.py`), not as the anatomical substrate.

---

## Visible Human Project (adopted — substrate)

Axial cryosection photographs, CT, and MRI of one male and one female
cadaver, from the U.S. National Library of Medicine.

| | Cryosection spacing | In-plane | Voxel volume |
|---|---|---|---|
| Visible Human **Female** | 0.33 mm | 0.33 mm | **0.036 mm³** (isotropic) |
| Visible Human **Male** | 1.0 mm | 0.33 mm | **0.109 mm³** |

Both are already below the 1 mm³/voxel target. The female dataset is
isotropic, which is what makes arbitrary-plane resampling clean.

The project also includes **CT and MRI of the same two cadavers**, which is
what makes cross-modality correlation possible against ground truth rather
than against a different body.

**Obtaining it.** NLM has moved the entry point more than once, and the old
`data.lhncbc.nlm.nih.gov/public/Visible-Human/` directory listing no longer
resolves reliably. Current routes, best first:

| Route | Where |
|---|---|
| **Imaging Data Commons (NCI)** — DICOM-converted, cloud-hosted, browsable, with download manifests | <https://portal.imaging.datacommons.cancer.gov/collections/nlm_visible_human_project> |
| NLM Data Discovery — the current official landing page | <https://datadiscovery.nlm.nih.gov/Images/Visible-Human-Project/ux2j-9i9a/about_data> |
| Zenodo — manifests for the IDC collection | <https://zenodo.org/records/12690050> |
| data.gov catalog entry | <https://catalog-beta.data.gov/dataset/visible-human-project> |
| Project overview and terms | <https://www.nlm.nih.gov/research/visible/visible_human.html> |

The IDC route is worth preferring: the imagery is already in DICOM and can be
pulled selectively by manifest rather than as a bulk directory fetch.

None of these could be checked from the machine this was written on — the
environment's network policy denies those hosts outright — so treat them as
starting points rather than verified endpoints.

**Licensing.** Before July 2019 the NLM required a signed license agreement.
That requirement was removed; access is now governed by NLM's Terms and
Conditions, with no registration, no fee, and no royalty. As a work of the
U.S. federal government the imagery is not subject to US copyright. The
surviving obligation is acknowledgement:

> Courtesy of the U.S. National Library of Medicine

There is no share-alike term and no restriction on commercial use, so
segmentations we derive from these images are ours outright and may be
licensed on any terms.

**Caveats to carry forward.** Two cadavers, not a population: a 39-year-old
male (BMI 27.8) and a 59-year-old female (BMI 36). Fixed post-mortem tissue
does not look like living tissue under ultrasound, and muscle tone, blood
volume, and fascial planes all differ. Any clinical overlay must be stated
as literature-derived, not measured from these two bodies.

## University of Denver lower-extremity geometry (adopted — stage 1)

Segmented from the VHP cryosections by the Center for Orthopaedic
Biomechanics, University of Denver.

> Andreassen TE, Hume DR, Hamilton LD, Walker KE, Higinbotham SE,
> Shelburne KB. "Three Dimensional Lower Extremity Musculoskeletal Geometry
> of the Visible Human Female and Male." *Scientific Data* 10(1):34 (2023).
> [doi:10.1038/s41597-022-01905-2](https://doi.org/10.1038/s41597-022-01905-2)
> · PMID 36653365 · Data: [doi:10.56902/COB.vh.2022.0](https://doi.org/10.56902/COB.vh.2022.0)
> · Mirror: <https://simtk.org/projects/3d-vh-geometry>
> (Author list retrieved from PubMed.)

Contents — **260 geometries**, per subject: 76 muscles, 28 bones, 16
cartilages, 8 ligaments, 2 fat bodies. Distributed as aligned cryosection and
CT image stacks, 3D Slicer segmentation masks, and raw plus post-processed
STL meshes.

### Download folders and their real sizes

The 211 GB / 144 GB figures quoted in the paper describe the complete
release. The download page splits it into folders that are individually far
smaller, and the one this project needs first is under 100 MB:

Two listings are recorded below because they do not agree, and the difference
matters when telling someone what to download.

**As observed after download** (zip sizes, reported by the repository owner
2026-08-28). Note these folder names carry no Right/Left split:

| Folder | Zip |
|---|---|
| **Final 3D STL Models-stl** | **133 MB** |
| Smoothed 3D STL Models-stl | 244 MB |
| Original 3D STL Models-stl | 1.27 GB |
| MetaData | **58 KB** |
| Aligned Cryosection-DICOM | 579 MB |
| Aligned CT-DICOM | 278 MB |
| Aligned Scan Images-mat_tif | 1.94 GB |
| Final Segmentation Masks and Aligned Scans-Slicer | 2.71 GB |
| Smoothed Segmentation Masks and Aligned Scans-Slicer | 2.71 GB |
| Original Segmentation Masks and Aligned Scans-Slicer | 3.18 GB |
| Original Segmentation Labelmaps-mat_tif | 3.79 GB |
| Original Segmentation Masks and Aligned Scans-MHD | 1.49 GB (extracts to ~129 GB) |

**As listed on the download page** consulted earlier, which splits the STL
folders by side:

| Folder | Zip | Extracted |
|---|---|---|
| Final 3D STL models (Right *or* Left) | 87.8 MB | 117 MB |
| Smoothed 3D STL models (Right or Left) | 173 MB | 601 MB |
| Original (raw) 3D STL models | 506 MB | 5.66 GB |

The likeliest explanation is that the two describe different subjects, or that
the observed folders hold both sides where the page offered them separately.
Either way, **the folder to start from is the Final STL folder**, and
`MetaData` at 58 KB is worth taking as well — it is the smallest thing in the
release and the most likely place to find the naming convention and the
coordinate frame written down.

The `.mhd` folder is the only one that explodes on extraction -- 1.3 GB
compressed to 129 GB on disk. Take the 3D Slicer variant instead unless that
exact format is needed.

### ⚠️ The final models are NOT sub-millimetre

This matters for a project whose stated target is under 1 mm³ per voxel. The
smoothed models -- and the final models derived from them -- were **remeshed
to target edge lengths of 1.5 mm for muscle, 1.0 mm for bone, and 0.75 mm for
cartilage and ligament**. That is the surface sampling density, and it is
coarser than the target.

Sub-millimetre surface detail has to come from one of:

- the **raw STL models**, written at ScanIP's default ~0.33 mm edge length,
  matching the cryosection resolution -- but carrying, in the authors' words,
  "issues resulting from segmentation";
- the **segmentation masks** at their native voxel resolution, re-meshed
  here rather than accepting the published remesh.

Use the final models for rigging, display and the first ingest -- they are
clean, gap-corrected and immediately usable. Reach for the raw models or the
masks when surface fidelity, rather than topology, is what is being measured.

### The cross-section stage is much cheaper than expected

The aligned cryosection and CT DICOM folders together are about **765 MB**,
not the hundreds of gigabytes assumed when stage 5b was drafted. The CT is
already registered to the cryosections and the transverse offsets in the
original sequences are already corrected -- so the cross-modality correlation
this project wants arrives without a registration step of our own.

The overclosure-correction MATLAB code the authors used is public at
<https://github.com/thor-andreassen/femors>.

Quality notes recorded by the authors:

- Left and right were segmented **independently, never mirrored**, so genuine
  bilateral asymmetry is preserved. 70 % of muscles are within 10 % volume of
  their contralateral partner.
- Reviewed against Netter, Fleckenstein, Radiopaedia, and Primal Pictures.
- All inter-structure overclosures removed to a uniform 0.05 mm gap, which
  makes the set finite-element-ready.
- Post-processing changed volume by less than 15 % for 95 % of structures.

Known gaps, stated by the authors: the **patellar tendon and the complete
Achilles tendon are absent**; some Visible Human Female left knee extensor
anatomy was disrupted pre- or post-mortem and was segmented to a
representative rather than observed form; some inter-structure borders in the
cryosections were hard to resolve.

### Obtaining it

| What | Where |
|---|---|
| Digital Commons @ DU collection | <https://digitalcommons.du.edu/visiblehuman/> |
| — Visible Human Female | <https://digitalcommons.du.edu/visiblehuman/1/> |
| — Visible Human Male | <https://digitalcommons.du.edu/visiblehuman/2/> |
| SimTK mirror (usually needs a free account) | <https://simtk.org/projects/3d-vh-geometry> |
| Data DOI | <https://doi.org/10.56902/COB.vh.2022.0> |

**Do not download the full package for stage 1.** The 211 GB and 144 GB
figures are the complete releases including the cryosection and CT image
stacks. `scripts/ingest_vh_geometry.py` reads only the **processed STL
geometry** — 260 meshes, orders of magnitude smaller. The authors split the
release into separate folders precisely so that subset can be taken alone.
The image stacks are needed later, for the cross-section engine (stage 5b),
not for the geometry ingest.

Then:

```bash
python3 scripts/ingest_vh_geometry.py inspect <folder> --subject vhm
```

which reports the structure names, bounding box, inferred units, up-axis and
the hip joint centre, without writing anything. `propose` and `convert`
follow from there.

### Do not read the folder off the filename

Every mesh in the **Final** folder is named `..._smooth.stl`. That suffix is
part of the Final release's own naming and does **not** mean the file came
from the Smoothed folder. Confirmed by the repository owner, who downloaded
both from under the Final heading. The consequence matters: everything
ingested so far is Final, so the remesh target edge lengths — 1.5 mm muscle,
1.0 mm bone, 0.75 mm cartilage and ligament — apply to it, and it is coarser
than this project's sub-millimetre goal.

### The frame, as measured against the VHM Final set, both sides

Run 2026-08-28 on 128 meshes (63 right, 63 left, 2 midline), 3,077,884
triangles, 1,539,203 welded vertices, no read failures. The
coordinate frame is **not** inferred from the bounding box — that can only
say which axis is longest, never which way is up. Each axis was fixed by an
anatomical test on the geometry itself:

| Atlas axis | Source | How it was established |
|---|---|---|
| +X (right) | −x | Lateral-minus-medial on five independent pairs: gastrocnemius heads, vastus lateralis/medialis, lateral/medial cuneiform, LCL/MCL, tibial plateau cartilages. Unanimous. |
| +Y (superior) | −z | Pelvis centroid minus calcaneus centroid, dominant component −935 mm. |
| +Z (anterior) | +y | Tibialis anterior minus soleus, +50 mm; cross-checked by patella minus femur, +43 mm. |

So `--axes '-x,-z,+y' --units mm`.

**The two sides are not spelled consistently with each other**, which only
became visible once the left side arrived. Six structures differ:
`BicepsFemorisLong`/`Longus`, `ExtensorHallucisLongus`/`Hallicus`,
`FlexorHallucisLongus`/`Hallicus`, `QuadratisFemoris`/`Quadratus`,
`Semitendinosus`/`Semitendonosus`, `TibialMedial`/`TibiaMedial`. Note that
neither side is consistently the correct one — right has `Quadratis`, left has
`Hallicus`. Four are normalised to the correct form; `Long`/`Longus` and the
`Tibial`/`Tibia` pair get separate override keys instead, because "longus" is
a real anatomical word and mapping it to "long" would corrupt adductor longus
and every other longus in the atlas.

One of these was a near miss rather than a clean failure: `ExtensorHallicusLongus`
scored **0.50 against extensor digitorum longus**, just under the 0.55
threshold. A slightly more permissive threshold would have silently mapped
extensor hallucis longus onto a different muscle.

**The left folder also carries the midline bones.** `VHM_Left_Bone_Sacrum` and
`VHM_Left_Bone_Coccyx` are not left-sided; they are in the folder someone put
them in. Taking the filename's word for it stamped `side="left"` on a midline
bone. `resolve_side()` now drops the side for known midline structures, and
the sacrum's converted geometry straddles X = 0 as it should.

**The origin needed solving separately, and originally did not exist.** The
atlas puts (0,0,0) at the midpoint of the hip joint centres
(`docs/ARCHITECTURE.md`); `convert` applied rotation and scale only, so
geometry landed on the scanner's volume corner and would have missed every
anchor in `data/rig/anchors.json`. `inspect` now measures the hip joint
centre by least-squares sphere fit to the femoral head cartilage, and
`convert` takes `--origin`.

The fit is the check on itself: **radius 24.73 mm right and 25.05 mm left,
rms residual 0.87 and 1.10 mm**. A femoral head is a sphere to well under a
millimetre, and a mesh that is not one will not fit like this.

With **one side only**, the midline has to be estimated — the medial face of
the hemipelvis, i.e. the pubic symphyseal surface. With **both sides**, it is
measured: `inspect` fits both heads and prints their midpoint, which is
exactly the atlas's definition of the origin, and no estimate is involved.

The right-side-only run is therefore also a test of that estimate, and it
passed well: the symphysis-based midline was **0.78 mm** from the true
midpoint later measured from both femoral heads. The inter-hip-centre
distance came out 177.8 mm estimated against **179.42 mm measured**.

Final bilateral frame: hip centres land at ±89.66, ∓0.93, ∓2.94 mm — exactly
symmetric, midpoint (0, 0, 0). Extents X −205 → +214 mm, Y −993 → +303 mm
(heel to iliac crest), Z −123 → +127 mm. The residual left/right differences
in Y and Z are this cadaver's own asymmetry, not registration error.

### What the mapping needed a human for

Of 128 meshes, 84 matched on name alone and 44 did not — and the 22 are not
matcher failures. They are recorded in `mappings/du_vh_overrides.json`, which
is version-controlled precisely because `build/` is not, and every entry
states its reason.

- **Cartilage is decomposed differently by the two datasets.** The release
  names it by the bone surface it covers (`FemurDistal`, `PelvisAcetabulum`,
  `TibiaLateral`); this atlas names it by the joint. `femur distal` and
  `knee articular cartilage` share no token, so no name-similarity method can
  bridge it at any threshold.
- **Seven tarsals to one `tarsals_r`**, two biceps femoris heads, two
  gastrocnemius heads, and iliacus + psoas major to `iliopsoas_r`. Real
  many-to-one relationships, and for the muscles they land on functional
  compartments the atlas already models.
- **`Phalanges` ties exactly** between foot and hand on name. Resolved by the
  fact that this is a lower-extremity release; the tie itself was correct.

One override is deliberately imprecise and says so: `Cartilage_FemurDistal`
covers both the tibiofemoral condyles and the trochlea, which this atlas
splits between two entities. Separating them needs geometric segmentation,
not a name mapping.

> ✅ **License confirmed at source.** The Digital Commons @ DU record states:
> *"This work is licensed under a Creative Commons Attribution 4.0
> International License."* Confirmed by the repository owner reading the
> record directly, 2026-08-28. **CC BY 4.0 — attribution only, no
> share-alike.** A proprietary derivative is permitted, which is the whole
> reason this dataset was chosen over Z-Anatomy. Attribution obligations are
> listed under *Attribution* below and must be honoured in any release.
>
> This was the last unverified claim in the licence analysis. Everything the
> project's commercial position depends on is now checked at the source.

---

## SPARC / SCKAN (evaluated — deferred, and worth revisiting for viscera)

The NIH Common Fund's SPARC program (*Stimulating Peripheral Activity to
Relieve Conditions*) and its knowledge base SCKAN were evaluated as a source
for the missing peripheral nerve layer.

**The licensing is ideal.** Public SPARC datasets are CC BY 4.0 — attribution
only, commercial use permitted, derivatives may be proprietary. One
exception: **embargoed** datasets sit under a Data Use Agreement that forbids
commercial use without a separate licence from the data owner. Filter on
embargo status before touching anything.

**The content is for a different problem.** SPARC exists to serve
bioelectronic medicine — vagus nerve stimulation, autonomic neuromodulation
of viscera. Per the SCKAN paper
([doi:10.3389/fninf.2025.1541184](https://doi.org/10.3389/fninf.2025.1541184)),
the knowledge base's neuron populations break down by circuit role as:

| Circuit role / phenotype | Populations |
|---|---|
| Sympathetic | 131 |
| Parasympathetic | 77 |
| Sensory | 40 |
| **Motor** | **9** |
| Enteric | 1 |

Nine motor populations in the whole knowledge base. The words "somatic" and
"skeletal muscle" do not appear in the paper at all. Its authors state they
are "in the process of extending the content with peripheral sensory and
motor pathways" — that is future work, not present content.

Three further disqualifiers for this project:

- **No geometry.** SCKAN holds semantic statements of the form *"neurons with
  somas in structure A project to structure B via nerve C"*. "Coordinate" and
  "geometry" appear zero times in the paper. This is the same *shape* of data
  the atlas already has in `data/nerves/` — topology without coordinates. It
  would not close the gap, it would duplicate it.
- **Predominantly rodent.** Models are described as "observed predominantly
  in rodents."
- **The program is winding down**, per the same paper.

**Revisit it for one thing.** If the atlas ever wants organ innervation —
which nerve supplies which viscus — SPARC is the best freely licensed source
that exists, and CC BY 4.0 makes it usable here. That is a later layer, not
the musculoskeletal one.

## IT'IS Virtual Population (open question — the only segmented human nerves found)

SPARC-funded work at the IT'IS Foundation produced the **Yoon-sun** and
**Jeduk** models (Virtual Population V4.0): whole-body human models with
segmented, anatomically extracted **peripheral nerve trajectories**. That is
precisely the geometry missing everywhere else.

Two problems, neither resolved:

- These are a **commercial product** of IT'IS / Zurich MedTech, licensed
  through the Sim4Life sales team. Not CC BY, not free. The actual licence
  terms could not be retrieved — itis.swiss was unreachable from the machine
  this was written on — so whether a proprietary derivative is permitted at
  any price is **unknown**.
- They derive from the **Visible Korean Human**, which carries its own access
  restrictions distinct from the NLM Visible Human's public-domain status.

If buying geometry is on the table, this is the most promising lead found.
It requires a direct conversation with IT'IS before it can be costed or
relied on.

## What this dataset does **not** contain

These are not footnotes — they are the clinically load-bearing layers, and
every one of them has to be built here, which is also why every one of them
will be owned outright.

| Missing | Why it matters | Where it must come from |
|---|---|---|
| **Upper limb and trunk** | The DU set is pelvis→feet only. For post-stroke spasticity the upper limb is the larger clinical need | Segment from VHP ourselves |
| **Peripheral nerves** | Without them there is no injection safety — the neurovascular bundle to avoid is invisible | Segment from cryosections (SPARC does not cover somatic nerves — see above) |
| **Blood vessels** | Same | Segment from cryosections |
| **Motor points / NMJ zones** | **Not resolvable in cryosection at any resolution.** Botulinum dosing targets endplate-rich zones, not muscle centroids | Literature (Sihler-stain studies) → atlas data layer |
| Patellar and full Achilles tendon | Excluded from the DU release | Segment from cryosections |

---

## Everything above the hip has no geometry (open — stage 2)

The Denver release is **pelvis to ankle**. That was checked at source rather
than assumed, because a web search summary claimed it covered "lower-limb,
torso and upper limbs"; the paper and the repository both say lower
extremity, 260 geometries, pelvis to ankle.

So the clavicle, scapula, humerus, radius, ulna, carpals, ribs, sternum and
the whole spine carry coordinates written from anatomical description that
have never been measured against anything. **That is not a hypothetical
risk.** The clavicle turned out to be stored mirrored on *both* sides,
putting the acromioclavicular joint 300 mm from where it belongs with the
scapula, humerus and the entire flagship upper-limb chain hanging off it. It
was caught by a lexical rule about the words "medial" and "lateral", not by
measurement, because there was nothing to measure against. A landmark that
does not happen to state a side in its own name would not have been caught
at all.

### The ingest for it is built and the source is not settled

`scripts/ingest_volume_geometry.py` reads a **segmented CT or MRI** — a
NIfTI label map, as produced by TotalSegmentator, 3D Slicer, ITK-SNAP or any
nnU-Net model — and writes the same manifest the STL ingest does, so every
audit already written runs on it unchanged. It recovers the atlas origin the
same way too, by fitting both femoral heads, except that a CT gives one
`femur` label with no separate cartilage, so the head is isolated from the
shaft by direction and the fit is reported with its radius and residual to
be accepted or rejected.

This is worth having on its own terms: comparing the atlas against a
patient's CT or MRI is one of the things it is for, and that comparison needs
the scan in the atlas frame.

**TotalSegmentator** is the obvious candidate to fill the gap.

| | |
|---|---|
| Code | Apache-2.0 — the class map in `mappings/totalsegmentator_labels.json` is transcribed from it |
| Dataset (1228 segmented CTs) | **CC BY 4.0**, 23.6 GB. Read at the Zenodo record by the repository owner, because `zenodo.org` is unreachable from the machine this was written on |
| Would give | clavicula, scapula, humerus, ribs, sternum, vertebrae C1–L5, sacrum, hip, femur — most of what has no geometry here |
| Would **not** give | any individual upper-limb muscle. It carries ten muscles in total: the three glutei, iliopsoas and autochthon. There is no deltoid, no biceps, no forearm compartment |

Every one of its 117 labels has a reviewed decision in the `atlas` section
of `mappings/totalsegmentator_labels.json`: mapped one-to-one, mapped
`part_of` a coarser atlas entity (each rib into `ribs_r`, each vertebra into
its region), refused with a reason (viscera, brain, cord, skull; autochthon
because the atlas is finer than the mask), or **split**. Two labels hold
several atlas entities and are cut geometrically at convert time, at levels
measured from the scan itself rather than from any fixed millimetre: the
aorta at the T4/T5 and T12/L1 discs into arch, descending thoracic and
abdominal (the ascending aorta between the cuts is the anterior of the two
columns and has no atlas entity, so it is dropped by name), and the costal
cartilages at the subject's midline as measured from the sternum. A scan
missing a level is told so and that part is left empty, never guessed.

Two things follow, and neither should be skipped.

**The licence was read at the Zenodo record**, not taken from a search
summary — the same discipline the Denver licence got, and for the same
reason: a search summary is not a licence, and one of them had already been
wrong about the Denver dataset's contents in this very investigation.
Attribution under CC BY 4.0 is required and is emitted into the manifest of
anything converted from it.

**A CT gives something the Visible Human cannot: more than one body.**
For the lower limb there is exactly one subject, so the only cross-check
available was bilateral consistency -- an error that mirrors is systematic,
an error that does not is noise. With 1228 segmented subjects the same
question can be asked across people, which separates "this atlas coordinate
is wrong" from "this one cadaver is unusual" in a way one body never can.
That is worth more than the extra resolution.

**A second subject is not the Visible Human.** Denver geometry and CT
geometry are two different bodies, and combining them into one skeleton is
the same error as combining measured fascicle lengths with measured mesh
volumes — already prohibited elsewhere in this project. Upper-body geometry
from a CT is for **checking** authored coordinates, where a second body is
if anything a stronger test, not for shipping as one continuous skeleton.

### Stage 2, first subject (2026-09-08): real, but bones/vessels only

`data/ct_sources/totalsegmentator_v201_s1371_labels.nii.gz` (911 KB, checked
in — small enough, unlike the ~355 GB VH source or the ~23.6 GB full
TotalSegmentator release, neither of which belongs in git) is one real,
pathology-free, whole-body CT case (Zenodo record 10047292, case `s1371`)
run through the ingest above. It gives real geometry, for the first time,
for: cervical/thoracic/lumbar vertebrae, all 24 ribs, sternum, costal
cartilage, clavicle, scapula, humerus — plus, unplanned, several great
vessels whose TotalSegmentator masks matched existing
`data/vascular/*.json` entity ids (aorta, venae cavae, subclavian/carotid/
brachiocephalic vessels). It does **not** give a unified skull (this atlas
only carries mandible and occipital as separate bones — no cranial-vault
entity exists to receive TotalSegmentator's `skull` mask, flagged by the
mapping step rather than silently dropped), forearm/hand bones
(TotalSegmentator doesn't segment radius, ulna, carpals, metacarpals, or
phalanges at all), or any upper-limb/trunk/neck **muscle** — TotalSegmentator
carries ten muscles total (three glutei, iliopsoas, autochthon), all of
which the atlas already had real geometry for from the DU release.

**The "not one continuous skeleton" rule above is still in force.** The
viewer bundle can now be built from a second subject at once with `vhm_both`
(`export_viewer_bundle.py --subject vhm_both --subject ct_s0913`, earlier
subjects win on any id collision so the already-verified VH data is never
overwritten) — but every structure from the second subject is tagged with
which specimen it came from, and the viewer inspector shows a visible badge
on it precisely so nobody mistakes the two for one cadaver. This is shown,
not fused: a second real body at the same anatomical scale, for comparison
and for checking authored anchor coordinates against, exactly as prescribed
above — running `scripts/audit_landmarks_vs_geometry.py --subject ct_s1371`
surfaced real errors in anchors that had never had geometry to check
against before (see PROJECT_STATE.md), specifically a clavicle landmark
axis-convention bug fixed in `data/skeleton/bones.json`.

### Stage 2, second subject (2026-09-09): s0913 adopted as primary

A second whole-body case, `s0913` (same Zenodo record, same CC BY 4.0
TotalSegmentator release), was ingested through the identical pipeline:
`data/ct_sources/totalsegmentator_v201_s0913_labels.nii.gz` (769 KB, merged
83-structure label volume; 810 overlapping voxels between masks, 0.04%,
resolved by the merge script's fixed structure-priority order). 78 of 83
structures auto-mapped to atlas ids; conversion produced 773,672 vertices /
1,547,480 triangles, with correct splits for the aorta (into its named
segments) and the costal cartilages.

Diffing s1371's and s0913's atlas-id coverage (`set(s1371 structures) ==
set(s0913 structures)`, verified directly) showed the two cases are
**fully redundant** with each other for this atlas's purposes — no
structure exists in one that is missing from the other. Since only one
was worth keeping in the default combined bundle, s0913 was chosen because
it is the better specimen on every measure that differs:

| | s1371 | s0913 |
|---|---|---|
| cervical spine | C6-C7 only | full C1-C7 |
| clavicle length | 101-114 mm | 138-143 mm (closer to the ~150 mm the hand-authored landmarks assume) |
| femoral-head sphere fit (rms) | 0.8-1.8 mm | 0.6 mm, both sides |
| post-clavicle-fix landmark audit | residual 10-60 mm | 7-19 mm |

The default combined bundle is now `--subject vhm_both --subject ct_s0913`
(197 structures; ct_s0913 contributes 241,432 of the kept triangles).
`ct_s1371`'s label volume stays committed for provenance and is still a
valid `--subject` argument on its own — it is simply not part of the
bundle the viewer ships by default. Femur/humerus landmarks in both cases
show expected CT-field-of-view cutoff artifacts near the joint away from
the scan centre, not placement bugs — the audit script's "reaches PAST the
end of this bone" note is the tell.

### Stage 2, muscles above the hip (2026-09-10): the model is a tool, the CT is the source

The geometry gap above the hip was never a shortage of CT: it was that the
TotalSegmentator *release* ships only the `total` task's masks (bones,
viscera, ten muscles). The TotalSegmentator *software* (Apache-2.0) has
further tasks that its README lists as "Openly available for any usage":
`abdominal_muscles`, `headneck_muscles`, `headneck_bones_vessels`,
`head_muscles`, `craniofacial_structures`, `oculomotor_muscles`. Run on a
case's own raw CT (in the same CC BY 4.0 release), they yield trunk-wall,
neck, jaw and extraocular muscles, a whole skull, laryngeal cartilages and
the neck vessels, on the **same specimen** whose bones are already here.
No new licence enters the repository: the CT is CC BY 4.0, the model is a
tool, and its output is ours to derive. (The `appendicular_bones` and
`thigh_shoulder_muscles` tasks -- forearm/hand bones, rotator cuff, deltoid,
triceps, thigh compartments -- are **licensed**: free only for
non-commercial use, commercial licence from University Hospital Basel. Not
run.)

Label maps: `mappings/totalsegmentator_<task>_labels.json`, one per task,
each with a reviewed `atlas` section. Where the mask is coarser than the
atlas (erector spinae vs. iliocostalis/longissimus/spinalis; prevertebral
vs. longus colli/capitis; tongue vs. its named muscles) the label is
deliberately not mapped, exactly as `autochthon` is not. The one new entity
is `cranium`, a composite for the whole skull minus the mandible, because
1.5 mm CT cannot separate the cranial bones at their sutures; the
individual bone entries remain the record.

Subjects now: **s0913** (29 m, C7 to mid-thigh) -- bones, vessels, and the
16 bilateral trunk-wall muscles of `abdominal_muscles`; its scan has no
head (the release's `skull.nii.gz` for it is an all-zero file). **s1159**
(47 f, `ct polytrauma`, `no_pathology`, vertex to hip in one body) --
chosen by probing the release's small masks for field of view before
downloading, since the release crops images unpredictably; origin fitted on
its own femoral heads (rms 0.49/0.53 mm) even though only the top ~24 mm of
each head is in the scan. The head, neck, orbit and trunk tasks are run on
it. Data files: `data/ct_sources/totalsegmentator_v201_s1159_labels.nii.gz`
(merged `total` masks); the raw CTs and task outputs live in `build/` and
the session scratchpad, reproducible from the Zenodo record by case id.

Running the tasks on a 4-core, 15 GB machine needed
`scripts/run_totalsegmentator_chunked.py`: the 0.75 mm task models hold a
softmax over every class for the whole crop and are OOM-killed on a trunk,
after which the parent waits forever on a futex. Chunks of 96 slices with
16 overlap, stitched by voxel index, keep the peak near 5 GB; seams were
checked slice by slice on s0913 and are continuous. Head tasks are run as a
single chunk because they locate the head with a rough model first.

**The "not one continuous skeleton" rule still holds.** The viewer badges
each structure with its body and task. As of the end of 2026-09-10 s1159's own muscles are in: the shipped bundle is
the VH lower limb plus s1159 alone, one consistent body from vertex to hip;
s0913 is retired from the bundle and kept for comparison.

### Stage 2, the Visible Human male's own CT (2026-09-10, night): head to pelvis, arms included, same body as the lower limb

The lower limb in this atlas is the Visible Human male (DU release). The
same cadaver's CT is public domain (NLM Visible Human Project) and is
served, DICOM by DICOM, from the Imaging Data Commons mirror bucket
`gs://idc-open-data` (anonymous HTTPS; manifest from Zenodo record 12690050,
`nlm_visible_human_project-idc_v15-gcs.s5cmd`; the `public-datasets-idc`
bucket named in the manifest does not resolve, the same UUID prefixes do on
`idc-open-data`). Series used, all VHP-M, study "Frozen", 1 mm slices:

| series UUID | slices | in-plane | covers |
|---|---|---|---|
| `5d409385-d3e7-48a9-ae50-150b39e834da` | 844 | 0.527 mm (head, 231 slices), 0.781 mm (24), 0.9375 mm (589) | vertex to proximal femur, both arms in the field of view |
| `145c2668-7d2f-4d7e-b1c7-2cf2462bef60` | 809 | 0.9375 mm | pelvis to ankle |
| `94755b62-0f88-4aa8-82ec-2d6d5cb8dbc7` | 224 | 0.9375 mm | ankle to toes |

The head-to-pelvis series mixes three reconstruction fields of view, so a
converter that trusts one pixel spacing draws the head 1.8x too large.
`stack.py` (session scratchpad; to be moved under `scripts/`) stacks the
slices by their own ImagePositionPatient/PixelSpacing onto one 0.9375 x
0.9375 x 1 mm grid (finest group wins where they overlap; one missing slice
at z = -274 mm filled from its neighbours) and a second 0.527 mm grid of the
head and neck for the 0.5 mm head tasks. The three series were scanned in
separate table sessions and their z origins do not agree. They also do
not overlap: the torso block's bottom slice IS the legs block's top slice
(image correlation 0.945 between torso z=0 and legs z=808, and no legs
slice matches torso z=15), so the blocks are contiguous and the offset is
fixed, not fitted: legs->torso = (+2.72, -0.89, -693.0) mm RAS, the
in-plane part from sub-voxel phase correlation of that shared slice
(+-1 mm in z if the two slices are adjacent rather than identical). The
atlas origin is the femoral-head rule applied to the legs block
(`total` on its pelvis slab: right head r=25.9 mm rms 0.74, left r=25.7
rms 0.71) carried over by that offset:
`--origin '-6.035,-895.476,4.787'` for every torso-block subject. A
pelvis-overlap registration was tried first and is kept as
`scripts/register_vhm_blocks_by_pelvis.py`; it cannot work here (best
coverage 0.31) precisely because there is no overlap.

Provenance: NLM Visible Human Project, public domain with attribution
("Courtesy of the U.S. National Library of Medicine"); IDC citation
Fedorov A et al., "National Cancer Institute Imaging Data Commons",
Radiographics 2023, doi:10.1148/rg.230180. Segmentations are produced here
with TotalSegmentator's Apache-2.0 tasks (`total`, `headneck_muscles`,
`headneck_bones_vessels`, `abdominal_muscles`, `craniofacial_structures`,
`head_muscles`, `oculomotor_muscles`); nothing from the licensed tasks.
Frozen-cadaver CT is not what those models were trained on; every label
is checked against the CT before it ships (see PROJECT_STATE for the
per-task verdicts).

Why this matters more than another Zenodo case: it is the SAME body as
the lower limb, so the hip is one specimen from both sides of the
pelvis-thigh boundary, and the arms are in the scan -- which no case in
the TotalSegmentator release above the hip had. Forearm and hand BONES are
taken from it by `scripts/segment_arm_bones_vhm.py` (HU threshold,
marker-controlled watershed on the smoothed CT; key
`mappings/vhm_arm_labels.json`), but the 480 mm reconstruction field of
view clips both arms around the elbow, so the humerus lacks its distal
end and the radius/ulna their proximal ends (about 85% / 65% of their
length is in the scan); the hand ships as one composite mesh per side
(`hand_r`/`hand_l`). Upper-limb MUSCLES still cannot come from it, without
the licensed `thigh_shoulder_muscles` task or a segmentation of the
cryosections (which do hold the whole arms, at 0.33 mm, in colour).

### The cryosections (2026-09-11): registration, the hybrid CT, and what they gave

The same cadaver's colour cryosections (IDC series 4aaf9181, 1878 slices,
0.33 mm, public domain) are streamed into a 1 mm volume and registered to
the CT (`scripts/cryo/README.md`: rows flipped, in-plane by silhouette,
z by mutual information, cryo index = -16 - z_RAS +-4 mm, verified by
overlaying the `total` outlines on the photographs at five levels). Two
things came out of them:

1. **The arms to the elbow.** `scripts/cryo/complete_arm_bones_from_cryo.py`
   walks each CT-clipped bone through the photographs (local per-slice
   registration of the arm; the cortical ring closed and filled because
   marrow photographs red-brown; the elbow split by a luminance watershed
   between the bones plus a joint line estimated from the humeral head).
   Humeri to the elbow, ulnae to the olecranon, left radius to its head;
   the right radial head is partly labelled ulna. Elbow surfaces +-10 mm.
2. **The hybrid CT** (`scripts/cryo/hybrid_ct_from_cryo.py`): the frozen
   CT with muscle/fat HU replaced from the photograph classes. On it the
   `abdominal_muscles` task finds pectoralis major, serratus anterior,
   latissimus dorsi and the trunk part of trapezius on the right muscles
   (overlay checked); rectus abdominis and the obliques still fail. The
   bundle takes those four from the Visible Human (`ct_vhm_abd`, trapezius
   unioned into `ct_vhm_neck`) and only rectus, obliques and quadratus
   lumborum from s1159.

3. **Hands and named arm muscles** (later the same day). The fingers lie
   in the legs CT block (the torso block ends at the palm; `total` labels
   them "skull" there); both blocks are unioned and each hand cut by
   planes along its axis into carpal, metacarpal and phalangeal groups
   (`scripts/cryo/hands_from_both_blocks.py`). The arm compartments are
   turned into biceps, brachialis, coracobrachialis and triceps by
   depth-and-level rules from standard anatomy
   (`scripts/cryo/name_arm_muscles_from_cryo.py`, key
   `mappings/vhm_arm_muscles_labels.json`); the biceps/brachialis boundary
   is a rule, not a traced fascia, and the viewer badge says so.

4. **Rule-based muscles** (same day, later): deltoid (superficial to the
   proximal humerus), the rotator cuff (by which scapular surface is
   nearest), the erector spinae columns (by distance from the midline).
   Every one of these is a textbook rule applied to the muscle mass the
   photographs or the hybrid CT delineate; the viewer badge and the label
   map say so, and the volumes are recorded in PROJECT_STATE so a reviewer
   can judge them.

Not from the photographs, deliberately: individual forearm muscles (the
arm lies pronated on the thigh and an image-frame split does not follow
the forearm septa), separated carpal bones (tried at 0.33 mm: fragments
only), teres major, tendons (tried: cream like the fat around them at
1 mm), ligaments, nerves. The sciatic nerve was tried
(`scripts/cryo/sciatic_from_cryo.py`): at 1 mm it is not separable from
the fat plane it lies in, and on the 0.33 mm photograph it is not
identifiable without expert reading. Each of those needs slice-by-slice
review, not thresholds.

What the frozen scan is and is not good for, measured (2026-09-11):
`total` bones are all there and in place; `headneck_muscles`, the head
muscles and craniofacial bones are plausible for a large male; the
`abdominal_muscles` task fails on it (superficial trunk muscles come out
as fragments, erector spinae leaks into fat), and there is no vascular
contrast. So the shipped bundle (viewer Version 22, 299 structures) is:
the DU lower limb; the VH male CT and cryosections for every bone from the skull to the
fingertips (arms complete; hands as carpal/metacarpal/phalangeal groups),
the arm muscles by compartment rules (biceps, brachialis,
coracobrachialis, triceps), the deltoid by superficial-proximity rules, pectoralis minor and the
rhomboids by position, the rotator cuff
(supraspinatus, infraspinatus with teres minor, subscapularis) by
scapular-surface rules, the erector spinae columns (spinalis,
longissimus, iliocostalis) by distance from the midline, the
transversospinalis mass under multifidus, the anterolateral abdominal
wall (rectus, external and internal oblique, transversus) by position and
depth fraction, and the body surface (`skin`), the head/neck/orbit muscles, pectoralis
major, serratus anterior, latissimus dorsi, trapezius, the gluteals and
iliopsoas (subjects `ct_vhm`, `ct_vhm_arm`, `ct_vhm_armm`, `ct_vhm_delt`, `ct_vhm_cuff`, `ct_vhm_es`, `ct_vhm_head`,
`ct_vhm_headm`, `ct_vhm_neck`, `ct_vhm_neckbv`, `ct_vhm_orbit`,
`ct_vhm_abd`); and, badged
as a second specimen, s1159's quadratus lumborum (`ct_s1159_abd`) and
vessels (`ct_s1159`, its bones dropped on collision). The VH pelvis was cross-checked against
the DU release of the same body: iliac crest tops agree within 0.1 mm.

### The Visible Human FEMALE (2026-09-11, evening): a second, model-segmented body

Series `b9cf8e7a-2505-4137-9ae3-f8d0cf756c13` (VHP-F, study "Normal",
fresh cadaver, non-contrast, 985 slices at 1 mm, in-plane 0.488 mm over
the head and 0.9375 mm over the trunk, vertex to mid-thigh), stacked by
`scripts/stack_dicom_series.py` like the male, segmented with the same
free TotalSegmentator tasks. Because the cadaver was not frozen, the
soft-tissue contrast is clinical and the models behave: the femoral
heads fit at r = 24.4 mm with rms 0.65 / 0.69 mm, the aorta is labelled
along its whole course (185 cm3), and the trunk-muscle task is expected
to find the muscles the frozen male defeated. She is ingested as
`ct_vhf_*` subjects with her own femoral-head origin
(`--origin '7.769,-885.229,14.137'`) and exported as a SECOND viewer
bundle (`build/viewer_f`): the two bodies are never mixed in one scene,
and the viewer badge names the body on every structure. Her role: a
second complete specimen for injection planning, and a model-segmented
reference against which the male's rule-based muscles can be compared
(same model, same tasks, unfrozen tissue).

#### Her lower limb (2026-09-11, night): the femur-to-toes block

Series `af18f5e4-f010-4b23-9be7-7c9f1aaa21a5` ("1X1 AXIAL FEMUR-TOES NCE",
749 slices at 1 mm, in-plane 0.9375 mm over the top 128 slices and 0.7227
mm below, stacked on the 0.7227 mm grid). The block starts at mid-thigh, so
it shares no femoral head with her torso block; the two are registered by
continuity across the junction (`scripts/vhf_lower_limb_bones.py`): a
quadratic fitted through the inter-femur distance of the torso's bottom
24 slices and the block's top 24 slices under candidate shifts (rms 0.15
mm at z = -943.0), agreeing with the body-area and fat-area fits of a
first run (-943.5, -942.5); the shift used is (+6.0, -3.6, -943.5) mm,
+-4 mm in height. No free TotalSegmentator task labels bones below the
femur, so the bones are HU >= 200 split at the joints by a
distance-transform watershed (medullary canals tube-filled, 3.5 mm
bone-core markers, fragments re-united where their common boundary is
thick bone). The femur ships as one label united from the torso block's
TotalSegmentator femur (head to mid-thigh) and this block's component
(mid-thigh to condyles). The foot bones are grouped by planes along the
foot axis (tarsals / metatarsals / phalanges), not separated: the same
limitation as the male CT feet. Volumes are recorded in
`data/ct_sources/task_outputs/vhf_lower_limb_bones_report.json`. The female
bundle (viewer Version 12, 2026-09-12) is 191 meshes from fourteen subjects,
`ct_vhf_legs` listed before `ct_vhf` so the united femur wins over the torso
block's stub; her body surface spans both blocks. Her cryosections (registered
to the CT, female colour classes) add the deltoid, the rotator cuff, the
upper-arm muscles and pectoralis minor by the male's rules; her model labels add
the erector spinae columns and multifidus.

### Rule-based structures: what the rule is, and how the volume compares (2026-09-11)

Textbook ranges are adult male values from Holzbaur et al. 2005 (upper limb
model volumes), Standring 2021 and the cadaveric literature they cite,
scaled up for a 90-kg subject; they are orientation, not tests. Volumes are
right / left in cm3 as measured on the Visible Human male.

| structure | rule | VH volume | textbook (large male) | verdict |
|---|---|---|---|---|
| biceps brachii | anterior compartment minus brachialis/coracobrachialis; boundary from full-res fascial lines | 526 / 513 | 300-400 | over (takes part of brachialis) |
| brachialis | anterior, within 22 mm of the humerus, distal 65 % | 152 / 214 | 200-280 | under on the right |
| coracobrachialis | anterior, proximal 35 %, medial, within 15 mm of the humerus | 44 / 50 | 40-70 | plausible |
| triceps brachii | whole posterior compartment | 713 / 789 | 550-750 | plausible / slightly over |
| biceps / brachialis / triceps, FEMALE (`ct_vhf_armm`, 2026-09-12) | the same compartment rules around her CT humerus on her cryosections (female colour classes); coracobrachialis rule finds nothing on her (not shipped) | 394 / 456, 111 / 74, 295 / 315 | female: 150-250, 100-180, 250-400 | biceps over (takes brachialis and the anterior fat plane), brachialis under on the left, triceps plausible |
| deltoid | superficial to the proximal humerus, lateral to the scapula (+ spine third) | 282 / 215 | 350-500 | under (deep part missed) |
| deltoid, FEMALE (`ct_vhf_delt`, 2026-09-12) | the same rule on her cryosections registered to her fresh CT (piecewise in-plane, z +-9 mm; her CT humerus/scapula as anchors, shifted 11 / 15 px onto the photographs) | 225 / 213 (female colour classes; 164 / 153 with the male's) | 200-300 (female) | plausible (the male's colour class missed 40-60 % of her darker muscle; `cryo_classes_f.py`) |
| supraspinatus | dorsal scapula above the spine level, medial to the glenoid | 68 / 69 | 45-80 | plausible |
| infraspinatus (+teres minor) | dorsal scapula below the spine level | 353 / 340 | 200-300 (+40) | over (teres major slips) |
| subscapularis | ventral scapula, <=18 mm, not nearer the ribs | 321 / 321 | 200-300 | over |
| rotator cuff, FEMALE (`ct_vhf_cuff`, 2026-09-12) | the same three rules on her cryosections registered to her fresh CT (z +-9 mm; her scapula label shifted 11 / 15 px onto the photographs) | supraspinatus 45 / 50, infraspinatus (+teres minor) 235 / 216, subscapularis 230 / 210 (female colour classes) | female: 35-60 / 130-200 / 120-180 | supraspinatus plausible; infraspinatus and subscapularis over, as on the male |
| pectoralis minor | sheet <=10 mm deep to pec major, >=8 mm from ribs | 77 / 51 | 30-60 | over |
| rhomboids (major+minor) | scapula medial border to midline, deep to trapezius, C7-T6 | 124 / 135 | 100-160 | plausible |
| pectoralis minor, FEMALE (`ct_vhf_pmr`, 2026-09-12) | sheet <= 10 mm deep to her model pec major, 8-30 mm from the ribs, rib 5 to clavicle, outside the cage's convex hull (female colour classes) | 42 / 31 | 20-40 (female) | plausible; a sliver at liver level remains |
| rhomboids, FEMALE | the same rule on her | 49 / 32 | 70-110 (female) | NOT shipped: patches beside the spine, not the sheet |
| rectus abdominis | <=70 mm of midline, <=45 mm behind the anterior skin, xiphoid to iliac crest | 181 / 189 | 120-200 (whole) | plausible for the part present |
| external oblique | lateral wall, outer 40 % of depth | 176 / 322 | 150-250 | left over |
| internal oblique | middle 35 % | 44 / 116 | 100-180 | right under |
| transversus abdominis | inner 25 % | 82 / 227 | 80-150 | left over |
| spinalis / longissimus / iliocostalis | erector mass by distance from midline (20 / 50 mm) | 67 / 71, 473 / 514, 260 / 211 | 40-80, 350-550, 200-320 | plausible |
| multifidus (transversospinalis group) | hybrid-CT label | 214 / 205 | 150-250 (group) | plausible |
| spinalis / longissimus / iliocostalis, FEMALE (`ct_vhf_es`, 2026-09-12) | the same 20 / 50 mm rule on her MODEL erector-spinae + autochthon labels (unfrozen CT; no photographs needed) | 44 / 64, 310 / 304, 157 / 126 | female: 30-60, 250-400, 150-250 | plausible; spinalis asymmetric (midline rule) |
| multifidus, FEMALE (`ct_vhf_abd`) | model transversospinalis label, mapped as on the male | 185 / 173 | 120-200 (group) | plausible |
| hand groups | planes along the hand axis (45 / 115 mm) | carpals 24 / 33, metacarpals 11 / 24, phalanges 14 / 16 | 15-20, 20-30, 12-18 | carpals over (metacarpal bases) |

Everything in this table is badged in the viewer; a slice-by-slice review
against the photographs (all renders are in the session scratchpad and
reproducible from `scripts/cryo/`) is the way to turn "plausible" into
"verified".

### Derived: depth below the skin (2026-09-11)

`data/derived/skin_depth_vhm.json` lists, for every shipped structure of
the Visible Human male, the minimum, median and maximum distance of its
surface from the body surface mesh (mm). It is computed from the meshes
in `build/vh` and is the first product of the atlas that answers an
injection-planning question directly ("how deep is the shallowest point
of the subscapularis on this body?"). Regenerate it after any bundle
change; it is derived data, not a measurement on a patient.

See `docs/VIEWER_README.md` for what the viewer badges mean and where the two bodies are published.

## Resulting architecture

```
Layer 4 · Clinical overlays   motor points, injection corridors,      OURS
                              danger zones, volume-based dosing
Layer 3 · Atlas data          PCSA, functional compartments,          OURS  (built)
                              ROM, innervation, fibre direction
Layer 2 · Segmentation        upper limb, trunk, nerves, vessels      OURS  (to build)
                              lower limb                              CC BY 4.0 (DU)
Layer 1 · Voxel substrate     VHP cryosection + CT + MRI              Public domain (NLM)
```

**Net licensing position:** attribution to NLM and to the University of
Denver team. Everything above that line is proprietary, sellable, and
restrictable — which is the requirement this whole analysis was built to
satisfy.

The layer that turns an atlas into an injection-planning tool — motor points,
functional compartments, safe corridors — is precisely the layer that cannot
be photographed, and therefore precisely the layer that is already ours.

---

## Attribution block to ship

Any product built on the above must carry, visibly:

```
Anatomical imagery courtesy of the U.S. National Library of Medicine
(Visible Human Project).

Lower-extremity musculoskeletal geometry derived from Andreassen TE, Hume DR,
Hamilton LD, Walker KE, Higinbotham SE, Shelburne KB, "Three Dimensional
Lower Extremity Musculoskeletal Geometry of the Visible Human Female and
Male", Scientific Data 10:34 (2023), doi:10.1038/s41597-022-01905-2,
used under CC BY 4.0.
```

The CC BY 4.0 line in this block is confirmed at the Digital Commons @ DU
record (2026-08-28). CC BY 4.0 requires attribution, a link to the licence,
and an indication of whether changes were made — this project makes extensive
changes, so say so. It does **not** require the derivative to be licensed
alike, which is what makes the proprietary licence on this repository
possible.

---

*This document records engineering and licensing analysis, not legal advice.
The share-alike incompatibility is a plain reading of the CC BY-SA 4.0 text
and is not in doubt; the specific status of individual datasets should be
confirmed with counsel before commercial release.*
