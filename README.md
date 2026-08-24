# NMSK Atlas

A neuro-musculo-skeletal 3D human atlas engine — a data model and
procedural generator for nerves, muscles (fascicle-level, with
intramuscular functional compartments), bones/joints, blood vessels, and
fascia, built to drive an animatable, anatomically-constrained rig at a
1&nbsp;mm procedural resolution.

**Start here:** [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — what this
is, what it honestly isn't (yet), and how the pieces fit together.

## What's in this repo

- **Whole-body breadth**: all 206 bones, 37 joints (cited ROM), the full
  spinal + cranial nerve root map, and a 73-muscle whole-body index.
- **Four fully-detailed, fully-verified flagship regions**:
  - **Upper limb** (shoulder → hand) — 13 muscles at full fascicle-
    architecture depth (with documented intramuscular functional
    compartments, e.g. deltoid's 7 segments), the complete brachial plexus
    (43 nodes, root → motor point), the complete named arterial + venous
    trees (38 vessels), and the fascial/retinacular/pulley system
    (17 structures).
  - **Lower limb** (pelvis → foot) — 14 muscles at the same depth
    (gluteus medius's anterior/middle/posterior compartments, vastus
    medialis's VML/VMO subdivision, adductor magnus's dual-innervation
    adductor+hamstring parts, biceps femoris's dual-innervation heads),
    the complete lumbosacral plexus (31 nodes), the complete named
    arterial + venous trees (37 vessels), and the fascial compartment
    system (21 structures).
  - **Trunk** (spine, ribcage, abdominal/back wall, pelvic floor) — 14
    muscle groups at the same depth (rectus abdominis's 4 tendinous-
    intersection segments, multifidus's unusually short-fascicle/high-PCSA
    architecture, internal intercostals' two parts with *opposite*
    mechanical actions, levator ani's 3 parts, diaphragm's 3 parts), the
    complete thoracic segmental nerve map (59 nodes: intercostal,
    thoracoabdominal, subcostal), the thoracic/abdominal aortic tree and
    its azygos-system venous counterpart (105 vessels), and the
    thoracolumbar fascia/rectus sheath system (10 structures).
  - **Head & neck** — 35 muscle groups at the same depth (masseter's
    superficial/deep heads, temporalis's anterior/posterior parts,
    lateral pterygoid's two heads, digastric's dual-pharyngeal-arch-origin
    two bellies, orbicularis oculi's palpebral/orbital parts,
    sternocleidomastoid's two heads), the cranial nerve motor trees
    (facial, trigeminal V3, oculomotor/trochlear/abducens, hypoglossal,
    glossopharyngeal/vagal pharyngeal plexus) plus the cervical plexus
    with ansa cervicalis and phrenic nerve origin (42 nodes), the
    carotid/vertebral vascular trees (26 vessels), and the cervical
    fascial system (5 structures, including the carotid sheath).

  All four regions: all left/right mirrored (trunk's diaphragm is
  midline/unpaired), all schema-validated, all graph-connected.
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

Code: MIT (implied — no restrictions on the schemas/engine/scripts in this
repo). Data is authored from public-domain/standard-reference anatomical
knowledge (Terminologia Anatomica, Gray's Anatomy descriptions, published
peer-reviewed literature — see `docs/SOURCES.md`); no proprietary or
copyrighted dataset content is included. Third-party datasets referenced
for future scale-up (BodyParts3D, Visible Human Project, OpenSim) carry
their own licenses (CC BY-SA, public domain, BSD respectively) — attribute
per their terms if incorporated.
