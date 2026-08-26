# NMSK Atlas

A neuro-musculo-skeletal 3D human atlas engine — a data model and
procedural generator for nerves, muscles (fascicle-level, with
intramuscular functional compartments), bones/joints, blood vessels, and
fascia, built to drive an animatable, anatomically-constrained rig at a
1&nbsp;mm procedural resolution.

**Start here:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — what this
is, what it honestly isn't (yet), and how the pieces fit together.

## What's in this repo

- **Whole-body breadth**: all 206 bones, 37 joints (cited ROM), and the
  full spinal + cranial nerve root map.
- **The entire whole-body muscular system at full flagship depth** — 297
  muscle files across four regions, every one with fascicle-level
  architecture, documented intramuscular functional compartments, NMJ
  zones, and cited sources (no muscle remains at breadth-only depth —
  `data/muscles/muscle_index.json` is now an empty holding list):
  - **Upper limb** (shoulder → hand) — 41 muscles (with documented
    intramuscular functional compartments, e.g. deltoid's 7 segments,
    flexor pollicis brevis's dual-innervation heads), the complete
    brachial plexus (43 nodes, root → motor point), the complete named
    arterial + venous trees (38 vessels), and the fascial/retinacular/
    pulley system (17 structures).
  - **Lower limb** (pelvis → foot) — 49 muscles (gluteus medius's
    anterior/middle/posterior compartments, vastus medialis's VML/VMO
    subdivision, adductor magnus's dual-innervation adductor+hamstring
    parts, biceps femoris's dual-innervation heads, adductor hallucis's
    oblique/transverse heads), the complete lumbosacral plexus (31
    nodes), the complete named arterial + venous trees (37 vessels), and
    the fascial compartment system (21 structures).
  - **Trunk** (spine, ribcage, abdominal/back wall, pelvic floor) — 24
    muscle groups incl. the unpaired diaphragm (rectus abdominis's 4
    tendinous-intersection segments, multifidus's unusually short-
    fascicle/high-PCSA architecture, internal intercostals' two parts
    with *opposite* mechanical actions, levator ani's 3 parts,
    diaphragm's 3 parts, trapezius's 3 fiber-direction functional parts),
    the complete thoracic segmental nerve map (59 nodes: intercostal,
    thoracoabdominal, subcostal), the thoracic/abdominal aortic tree and
    its azygos-system venous counterpart (105 vessels), and the
    thoracolumbar fascia/rectus sheath system (10 structures).
  - **Head & neck** — 35 muscle groups (masseter's superficial/deep
    heads, temporalis's anterior/posterior parts, lateral pterygoid's two
    heads, digastric's dual-pharyngeal-arch-origin two bellies,
    orbicularis oculi's palpebral/orbital parts, sternocleidomastoid's
    two heads), the cranial nerve motor trees (facial, trigeminal V3,
    oculomotor/trochlear/abducens, hypoglossal, glossopharyngeal/vagal
    pharyngeal plexus) plus the cervical plexus with ansa cervicalis and
    phrenic nerve origin (42 nodes), the carotid/vertebral vascular
    trees (26 vessels), and the cervical fascial system (5 structures,
    including the carotid sheath).

  All four regions: all left/right mirrored (trunk's diaphragm is
  midline/unpaired), all schema-validated, all graph-connected, all
  adversarially fact-checked (docs/VERIFICATION.md).
- **Ligaments and cartilage** (`data/ligaments/`, `data/cartilage/`, 57 +
  32 entities): major named ligaments and cartilage structures for every
  significant joint — shoulder, elbow, wrist, hip, knee, ankle, spine,
  pelvis, TMJ. Multi-band/multi-part structures are modeled explicitly
  (the ACL's anteromedial/posterolateral bundles, the deltoid ligament's
  4 parts, a meniscus's horns+body, an intervertebral disc's anulus
  fibrosus/nucleus pulposus), the same "functionally distinct sub-groups
  within one named structure" idea used throughout the muscle data.
- **Tendons** (`data/tendons/`, 37 entities): major and minor named
  tendons with standalone identity beyond a single muscle's ordinary
  insertion — multi-muscle convergence (the rotator cuff and pes
  anserinus), documented internal layering (the quadriceps tendon's 3
  layers, the Achilles tendon's spiraling fibers), pulley/sheath
  systems (the finger flexors' A1-A5/C1-C3 pulleys), and
  clinically-named regions (the rotator cuff's hypovascular "critical
  zone").
- **A procedural engine** (`engine/`) that generates 1mm-resolution muscle
  fiber fields from architecture parameters, and a kinematic rig
  (`engine/rig.py`) that keeps every attachment point correctly anchored to
  its bone through arbitrary — including compound rotational — motion
  within cited anatomical ROM limits.
- **A verification suite** (`tests/`, `engine/validators.py`) checking
  schema validity, citation coverage, bone-reference integrity, nerve/
  vessel graph connectivity, ROM plausibility, left/right symmetry, and
  anchor rigidity under posing.
- **A roadmap** (`docs/ROADMAP.md`) for extending the same pipeline to full
  body coverage, staged and independently verifiable.

## Quick start

```bash
pip install -r requirements.txt
pytest tests/ -v                          # run the full verification suite
python -m engine.build_atlas --muscle deltoid_r   # generate + validate
python scripts/generate_anchors.py        # rebuild data/rig/anchors.json
python scripts/mirror_side.py data/muscles/upper_limb/*_r.json data/muscles/lower_limb/*_r.json data/muscles/trunk/*_r.json data/muscles/head_and_neck/*_r.json  # mirror right->left
```

## Documentation map

| Doc | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, honest scope statement, coordinate conventions |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Schema reference with worked examples |
| [docs/SOURCES.md](docs/SOURCES.md) | Full citation list + citation policy |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | Test methodology + actual results |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Staged plan to full-body coverage |

## License

**Proprietary — all rights reserved.** See [LICENSE](LICENSE).

Everything in this repository is original work: the schemas, the engine and
scripts, and the anatomical records themselves, which were authored from
Terminologia Anatomica, standard reference descriptions, and the
peer-reviewed literature cited in [docs/SOURCES.md](docs/SOURCES.md). No
third-party dataset content is included.

Anatomical facts are not owned by anyone and the license does not claim them.
What it covers is the expression built on top of them — the schema design,
the functional-compartment decomposition, the identifier scheme, the written
qualifications, and the arrangement of the corpus.

**On 3D geometry.** This repository contains no mesh or voxel data from any
external atlas. Geometry sourcing is a deliberate, licence-driven decision
recorded in **[docs/GEOMETRY_SOURCES.md](docs/GEOMETRY_SOURCES.md)**: the
Visible Human Project (US public domain) is the intended substrate, the
University of Denver lower-extremity segmentation (CC BY 4.0) the first
geometry layer, and CC BY-SA sources such as Z-Anatomy and BodyParts3D are
excluded because share-alike is incompatible with a proprietary derivative.
Read that document before adding any geometry to this repository.

**Not a medical device.** This is an anatomical reference dataset. It has not
been reviewed or cleared by any regulatory authority and is not validated for
diagnosis or treatment planning. See section 4 of [LICENSE](LICENSE).
