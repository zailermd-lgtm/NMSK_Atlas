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
| Dataset (1228 segmented CTs) | **NOT VERIFIED.** Reported as CC BY 4.0 by several secondary sources; `zenodo.org` is unreachable from the machine this was written on, so the licence line has never been read at its source |
| Would give | clavicula, scapula, humerus, ribs, sternum, vertebrae C1–L5, sacrum, hip, femur — most of what has no geometry here |
| Would **not** give | any individual upper-limb muscle. It carries ten muscles in total: the three glutei, iliopsoas and autochthon. There is no deltoid, no biceps, no forearm compartment |

Two things follow, and neither should be skipped.

**The licence must be read at the Zenodo record before any geometry derived
from it ships.** This is the same discipline the Denver licence got: that one
was also "reported as CC BY" for a long time and was only settled by reading
the page. A search summary is not a licence, and one of them has already been
wrong about this dataset's contents.

**A second subject is not the Visible Human.** Denver geometry and CT
geometry are two different bodies, and combining them into one skeleton is
the same error as combining measured fascicle lengths with measured mesh
volumes — already prohibited elsewhere in this project. Upper-body geometry
from a CT is for **checking** authored coordinates, where a second body is
if anything a stronger test, not for shipping as one continuous skeleton.

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
