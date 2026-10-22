# NMSK Atlas — Architecture

## What this is, honestly

A true, medically-certified, whole-body 3D atlas at 1 mm resolution — every nerve twig
down to its terminal branch, every muscle fascicle, every capillary, hand-verified
against cadaver dissection — is a multi-year, multi-terabyte undertaking normally
carried out by teams of anatomists and imaging engineers with access to segmented
cryosection/MRI/CT datasets (e.g. the NIH Visible Human Project, ~15GB of 1mm axial
cryosections, or AIST's BodyParts3D). That cannot be fabricated from nothing in a
single engineering session without either lying about precision or silently
inventing numbers that look plausible but aren't real anatomy.

So NMSK Atlas is built as what can be made **genuinely correct end-to-end**:

1. **A complete, whole-body data model** (schema/) capable of representing every
   subsystem the task asked for — skeleton, muscle (down to individual functional
   fiber compartments and their fiber-direction fields), nerve trees, vascular
   trees, fascia, and a rigging layer — at arbitrary resolution, with 1 mm as the
   procedural sampling target.
2. **Whole-body breadth data**: every one of the 206 bones, the major joints with
   cited ROM, the full spinal/cranial nerve root map, and a whole-body muscle
   index — populated from real, cited literature (`docs/SOURCES.md`).
3. **One fully-detailed, fully-verified flagship kinetic chain** — the upper limb,
   shoulder to fingertip — modeled at full depth: real fascicle architecture and
   pennation per muscle, documented intramuscular functional compartments (e.g.
   deltoid's ~7 independently-innervated segments), the complete brachial plexus
   tree down to motor points, the complete named arterial/venous trees, and the
   fascial compartments/retinacula/pulley system, all cross-referenced and
   validated. This proves the model is real and correct on a representative,
   maximally-complex region (it exercises every requirement: bone, joint, muscle,
   pennation/compartments, nerve, vessel, fascia, rig anchor) rather than being
   asserted correct in the abstract.
4. **A procedural generation engine** (engine/) that turns the parametric
   descriptions above into 1mm-resolution geometry (fiber centerlines, nerve/vessel
   centerlines) on demand — this is how "1mm resolution" is actually achievable:
   nobody hand-authors millions of fiber curves; they are generated from origin/
   insertion surfaces + architecture parameters, exactly as OpenSim/AnyBody/SIMM
   musculoskeletal software does it.
5. **A verification suite** (tests/) that checks the model computationally: schema
   validity, graph connectivity (no orphan nerve/vessel branches, every leaf
   resolves to the aorta/spinal cord), attachment existence (every muscle O/I
   references a landmark that actually exists on that bone), ROM literature
   bounds, left/right symmetry, and — the rigging requirement — that anchors stay
   correctly (rigidly, or correctly blended) attached to their bone through
   arbitrary rotation, including compound/rotational end-of-range poses.
6. **A scale-up roadmap** (docs/ROADMAP.md) that extends the same pipeline,
   region by region, to full-body coverage — with the honest cost/time estimate
   for what real completion requires (licensed segmented imaging data, more
   research passes, mesh authoring).

## Coordinate & unit conventions

- All lengths in millimetres. `resolution_mm = 1.0` is the target sampling
  interval for procedurally generated centerlines/point clouds.
- **Global frame**: subject in standard anatomical position, origin at the
  midpoint of the hip joint centers, +X = subject's anatomical right,
  +Y = superior, +Z = anterior (right-handed). See `schema/common.schema.json`.
- **Local frames**: every bone owns a rigid local frame (ISB/Wu et al.
  convention where a published standard exists — shoulder 2005, elbow/wrist
  2005, hip/knee/ankle 2002). Every attachment point (muscle origin/insertion,
  tendon via-point, fascial enthesis, nerve/vessel via-point, NMJ zone) is
  stored **only** in its parent bone's local frame as a `RigAnchor`
  (`schema/rig.schema.json`) — never as a pre-baked global coordinate. This is
  what makes the model animation-safe: an anchor's global position is always
  *derived* by walking the current kinematic pose, so it is correct by
  construction at any joint angle, including rotation, and never needs
  re-fitting.

## Layered data model

```
Bone (schema/bone.schema.json)
 └─ local_frame, landmarks[]              ← attachment surface for everything below

Joint (schema/joint.schema.json)
 └─ parent_bone, child_bone, DOF[min,max,cited]   ← kinematic edges between bones

Muscle (schema/muscle.schema.json)
 └─ attachments (origin/insertion bone+landmark, via_points[])
 └─ functional_compartments[]             ← independently-innervated fiber groups
     └─ fiber_architecture (type, pennation, fascicle length, PCSA, force)
     └─ fiber_field_seed_region           ← origin-surface polygon fed to the generator
     └─ neuromuscular_junction_zone       ← motor endplate band position

NerveBranch (schema/nerve_branch.schema.json)     — tree: root → trunk → division → cord → branch → twig
VesselBranch (schema/vessel_branch.schema.json)   — tree: heart → ... → named terminal branches (+ anastomotic edges)
FasciaCompartment (schema/fascia.schema.json)     — sheets/septa/retinacula + what they attach to and enclose

Ligament (schema/ligament.schema.json)
 └─ attachments (bone_a/bone_b + landmarks)       ← overall span
 └─ bands[]                                        ← mechanically distinct bundles (ACL's AM/PL, deltoid lig.'s 4 parts, ...)
     └─ tension_pattern                            ← when in the joint's ROM this band is taut vs. slack

Cartilage (schema/cartilage.schema.json)          — articular (per-joint), fibrocartilage (menisci/discs/labra/TFCC/symphysis), costal
 └─ parts[]                                        ← distinct sub-regions (a disc's anulus/nucleus, a meniscus's horns+body, ...)

Tendon (schema/tendon.schema.json)                — the fibrous continuation of one or more muscles onto bone
 └─ parent_muscles[]                                ← which muscle(s) this tendon belongs to (>1 for conjoined tendons)
 └─ parts[]                                         ← distinct components (quadriceps tendon's 3 layers, pes anserinus's 3 muscle contributions, ...)

RigAnchor (schema/rig.schema.json)                — the single unifying "stays attached to bone X at local point P" primitive
```

Every quantitative/topological field that isn't pure geometry-construction
metadata carries a `source` citation (`schema/common.schema.json#citation`).
Fabricating a plausible-looking number without a citation is treated as a
defect — `tests/test_source_coverage.py` enforces this mechanically.

## Engine (engine/)

- `geometry.py` — coordinate frame math, curve/surface sampling utilities,
  1mm point-cloud generation from parametric primitives.
- `fiber_field.py` — the procedural muscle-fiber generator. Given a
  compartment's `fiber_architecture` + origin/insertion attachment + seed
  region, generates a set of fascicle centerlines (parallel, fusiform,
  uni/bi/multipennate, circular, or convergent, per the documented
  architecture type), each tagged with its compartment id (this is how
  "multiple functional groups of fibers within the same muscle" is realized
  computationally) and its NMJ-zone position.
- `rig.py` — kinematic tree, forward kinematics with ROM clamping, anchor
  resolution (rigid or linear-blend-skinned), and muscle-tendon path
  wrapping through via-points so paths stay geometrically plausible (no
  bone penetration) through the joint's full documented range, including
  compound rotation.
- `nerve_tree.py` / `vascular_tree.py` — graph construction + connectivity
  validation for the branching trees.
- `validators.py` — the full anatomical-consistency + structural-integrity
  checker, used by both `tests/` and `engine/build_atlas.py`.
- `build_atlas.py` — CLI that loads `data/`, runs the generators for a
  requested region, emits 1mm-sampled geometry, and prints a validation
  report.

## Why this design scales without redesign

Because every subsystem reduces to the same primitives (bones + local
frames, joints + ROM, anchors, and parametric fields sampled at 1 mm),
adding the rest of the body is a **data-authoring problem, not an
architecture problem**: the same schemas, the same generator, and the same
validators apply unchanged to the trunk, head/neck, and lower limb. See
`docs/ROADMAP.md` for the staged plan and effort estimate.
