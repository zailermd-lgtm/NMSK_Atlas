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

**Obtaining it.** Project page:
<https://www.nlm.nih.gov/research/visible/visible_human.html>. Terms and
access: <https://www.nlm.nih.gov/research/visible/getting_data.html>. Data
directory: <https://data.lhncbc.nlm.nih.gov/public/Visible-Human/>.

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
STL meshes. 211 GB (male) and 144 GB (female).

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

which reports the structure names, bounding box, inferred units and up-axis
without writing anything. `propose` and `convert` follow from there.

> ⚠️ **Verify the license before commercial release.** The dataset is
> reported as **CC BY 4.0** (attribution only, no share-alike — compatible
> with a proprietary derivative). This has *not* yet been confirmed directly
> from the Digital Commons @ DU record, because that host was unreachable
> from the environment where this document was written. Confirm at the source
> and record the result here before shipping anything built on it.

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

The license line in this block is the one item still to be confirmed at the
source — see the warning above.

---

*This document records engineering and licensing analysis, not legal advice.
The share-alike incompatibility is a plain reading of the CC BY-SA 4.0 text
and is not in doubt; the specific status of individual datasets should be
confirmed with counsel before commercial release.*
