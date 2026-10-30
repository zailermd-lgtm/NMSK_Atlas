# Z-Anatomy: layer split

This directory exists to hold the licence text and attribution for Z-Anatomy
(CC BY-SA 4.0) material used by this project, and to state, in one place, the
rule that keeps that ShareAlike obligation from spreading into the parts of
this project that must stay proprietary.

See `NOTICE` for the source, pinned commit and full attribution, and
`LICENSE` for the CC BY-SA 4.0 legal text (copied verbatim from the pinned
clone). See `../../docs/GEOMETRY_SOURCES.md` and `../../PROJECT_STATE.md`
(Q141, 2026-09-23) for the owner decision and the fuller reasoning.

## The rule

**The anatomy MODEL layer may be CC BY-SA 4.0 (or compatible).** That is:
raw and lightly-corrected Z-Anatomy/BodyParts3D geometry, and this project's
own corrections to that geometry when a correction is itself a modification
of the Z-Anatomy mesh (for example: fixing the Z-Anatomy radial nerve
pathway where it is anatomically wrong). This layer lives in files that are
either committed under this ShareAlike obligation or, for extracted meshes,
deliberately NOT committed at all (see below) and are always reproducible
from the pinned clone + commit.

**Everything built ON TOP of the anatomy layer stays under the owner's
private licence, in separate files.** This includes, without limit:

- registration of the anatomy to real imaging (CT/MRI/cryosection) of this
  project's own subjects,
- ultrasound guidance overlays and correlation logic,
- needling guidance -- blind or ultrasound-guided,
- any other clinical planning or injection-safety tooling.

A file in this second category may **reference** an entity id that happens
to carry Z-Anatomy-derived geometry (the same way it already references any
other entity id), but it must not **contain** Z-Anatomy geometry or a
derivative of it. If a clinical file needs to embed geometry, that geometry
must come from this project's own real-data sources (Visible Human,
TotalSegmentator CT, cryosection segmentation -- see
`../../docs/GEOMETRY_SOURCES.md`), never from the Z-Anatomy layer, so that
the clinical file itself carries no ShareAlike obligation.

**Real data always wins.** Where this project already has real-subject
geometry for an entity (Visible Human / CT / cryosection), that geometry is
authoritative and Z-Anatomy is not used for it. Z-Anatomy is only a source
for entities this project has NO geometry for yet (see
`../../data/derived/Q117_full_completeness_audit.json`'s "neither" lists and
`../../data/derived/zanatomy_name_map.json`'s coverage report). When
real-data geometry for such an entity is produced later, it replaces the
Z-Anatomy stand-in.

**Every Z-Anatomy-derived structure ships badged, never silently.** Per the
Q119 procedural_badge mechanism (phase 2 plan, not yet built as of this
writing), any structure whose mesh came from Z-Anatomy is labelled in the
viewer as "Z-Anatomy (CC BY-SA 4.0), generic model registered to this body"
-- the same way a second CT subject is already badged with which specimen it
came from (see `../../docs/GEOMETRY_SOURCES.md`, "Stage 2, first subject").

**Derivatives must remain CC BY-SA, never plain CC BY.** This is a common
misreading of "ShareAlike" worth stating outright: a work adapted from CC
BY-SA 4.0 material may only be shared under CC BY-SA 4.0 (or a licence
listed as BY-SA-compatible at creativecommons.org/compatiblelicenses), not
under plain CC BY, and not under a proprietary licence. This project can
sell access to a product that CONTAINS such a layer (ShareAlike does not
forbid commercial use), but it cannot claim exclusivity over that specific
layer's geometry, and any file carrying it must say so. That obligation is
exactly why the layer is kept separated as described above, rather than
applied to the whole repository.

**Non-commercial subcomponents are excluded outright**, independent of all
of the above -- see `NOTICE`.

## What is committed here vs. not

- `LICENSE`, `NOTICE`, this `README.md`: committed. Small, textual, no
  geometry.
- `../../data/derived/zanatomy_inventory.json`,
  `../../data/derived/zanatomy_name_map.json`: committed. Per-object
  metadata (name, system, side, vertex/face counts, bounding box, licence
  flag) and name-to-entity-id mapping -- no vertex/triangle data.
- Extracted per-object meshes (`build/zanatomy/<system>/<name>.npz`): **never
  committed**. `build/` is gitignored. They are reproducible at any time by
  rerunning `scripts/zanatomy/extract_fbx.py` against the pinned clone and
  commit recorded in `NOTICE`.
