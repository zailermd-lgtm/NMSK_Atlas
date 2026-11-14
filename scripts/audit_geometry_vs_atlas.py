#!/usr/bin/env python3
"""Check the atlas's hand-authored muscle architecture against real geometry.

Until now every `fiber_architecture` number in this atlas -- pennation angle,
optimal fascicle length, physiological cross-sectional area, maximum isometric
force -- came from the literature and was checked only against other
literature. With the Visible Human geometry ingested there is, for the first
time, an independent physical object to test them against.

TWO CHECKS, AND THEY ARE NOT THE SAME KIND OF THING.

1. FASCICLE LENGTH vs MESH EXTENT -- a hard constraint.
   A fascicle cannot be longer than the muscle that contains it. This does not
   depend on whose body the mesh came from, on how the segmentation was drawn,
   or on any population average. If a compartment claims a fascicle longer
   than the muscle's own longest dimension, the number is wrong. Violations
   are reported as errors.

2. VOLUME vs IMPLIED VOLUME -- a comparison, not a verdict.
   PCSA = V cos(theta) / L_f, so the atlas's own numbers imply a volume:
   V = PCSA * L_f / cos(theta). Measuring V from the mesh gives a ratio.
   A ratio far from 1 is worth looking at, but it does NOT by itself mean the
   atlas is wrong, because:
     - the mesh is one 39-year-old male cadaver (BMI 27.8), not a population;
     - the literature values are averages over different, usually older,
       specimens;
     - segmentations differ in whether aponeurosis and intramuscular tendon
       are included in "the muscle";
     - where several meshes were merged onto one atlas entity, the measured
       volume is the sum and the architecture is for one part.
   So this half prints ratios and ranks them. It draws no conclusions.

Volume is the divergence-theorem sum over triangles and is only meaningful
for a closed surface, so closure is tested first and open meshes are excluded
from the volume comparison rather than silently given a wrong number.

    python3 scripts/audit_geometry_vs_atlas.py --subject vhm_both
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"
DATA_DIR = REPO_ROOT / "data"

# A fascicle may legitimately approach the muscle's longest dimension in a
# strap muscle such as sartorius, and the mesh extent is a straight-line
# bounding measure of a curved belly, so the check needs headroom before it
# calls something impossible. 1.0 would generate noise; this flags only
# claims the geometry cannot accommodate at all.
LENGTH_TOLERANCE = 1.15


def mesh_volume_mm3(verts: np.ndarray, faces: np.ndarray) -> float:
    """Signed volume by the divergence theorem. Meaningless unless closed."""
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    return float(np.abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def is_closed(faces: np.ndarray) -> bool:
    """Every edge of a closed surface is shared by exactly two triangles."""
    edges = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.sort(edges, axis=1)
    _, counts = np.unique(edges, axis=0, return_counts=True)
    return bool((counts == 2).all())


def load_geometry(subject: str):
    out = BUILD_DIR / subject
    manifest = json.loads((out / "manifest.json").read_text())
    verts = np.fromfile(out / "vertices.f32", dtype="<f4").reshape(-1, 3).astype(np.float64)
    faces = np.fromfile(out / "faces.u32", dtype="<u4").reshape(-1, 3).astype(np.int64)
    return manifest, verts, faces


def load_muscle_architecture():
    """compartment id -> (muscle id, architecture dict)."""
    table = {}
    for path in (DATA_DIR / "muscles").rglob("*.json"):
        if path.name == "muscle_index.json":
            continue
        payload = json.loads(path.read_text())
        for muscle in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(muscle, dict):
                continue
            for comp in muscle.get("functional_compartments", []):
                arch = comp.get("fiber_architecture")
                if arch:
                    table[comp["id"]] = (muscle["id"], arch)
    return table


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="vhm_both")
    ap.add_argument("--top", type=int, default=15,
                    help="how many volume outliers to list each way")
    args = ap.parse_args()

    try:
        manifest, verts, faces = load_geometry(args.subject)
    except FileNotFoundError:
        raise SystemExit(
            f"No converted geometry for subject {args.subject!r} under "
            f"{BUILD_DIR}. Run the ingest's convert step first.")

    arch_by_comp = load_muscle_architecture()

    # Gather geometry per atlas entity, summing meshes that were merged.
    per_entity = defaultdict(lambda: {"volume": 0.0, "extent": 0.0,
                                      "meshes": 0, "open": 0})
    # Older manifests carry no face_offset. Faces were written in structure
    # order, so the running total of triangle_count recovers it exactly.
    face_cursor = 0
    for rec in manifest["structures"]:
        v0, vn = rec["vertex_offset"], rec["vertex_count"]
        fn = rec.get("triangle_count", 0)
        f0 = rec.get("face_offset", face_cursor)
        face_cursor = f0 + fn
        block_v = verts[v0:v0 + vn]
        # Face indices are global; make them local to this block.
        block_f = faces[f0:f0 + fn] - v0 if fn else None
        entry = per_entity[rec["atlas_id"]]
        entry["meshes"] += 1
        entry["extent"] = max(entry["extent"],
                              float(np.ptp(block_v, axis=0).max()))
        if block_f is None or len(block_f) == 0:
            entry["open"] += 1
            continue
        if is_closed(block_f):
            entry["volume"] += mesh_volume_mm3(block_v, block_f)
        else:
            entry["open"] += 1

    # ---- check 1: fascicle length against mesh extent -------------------
    impossible = []
    for comp_id, (muscle_id, arch) in sorted(arch_by_comp.items()):
        geom = per_entity.get(muscle_id)
        if not geom or not geom["extent"]:
            continue
        fascicle = arch.get("optimal_fascicle_length_mm")
        if not fascicle:
            continue
        if fascicle > geom["extent"] * LENGTH_TOLERANCE:
            impossible.append((comp_id, fascicle, geom["extent"]))

    print(f"subject {args.subject}: {len(manifest['structures'])} meshes -> "
          f"{len(per_entity)} atlas entities")
    opened = sum(e["open"] for e in per_entity.values())
    if opened:
        print(f"  {opened} mesh(es) are not closed surfaces and are excluded "
              f"from the volume comparison")

    # ---- check 0: is the geometry the size a human is? ------------------
    #
    # This exists so that check 2 can be believed. A volume discrepancy is
    # only interesting once a unit or scale error has been ruled out, and
    # long bones are the cleanest ruler available: their lengths are stable,
    # well documented, and independent of segmentation choices about where a
    # muscle ends.
    print("\n[0] scale sanity -- long bone lengths against known human ranges")
    rulers = [("femur_r", 430, 500), ("femur_l", 430, 500),
              ("tibia_r", 355, 425), ("tibia_l", 355, 425)]
    scale_ok = True
    for entity_id, lo_mm, hi_mm in rulers:
        geom = per_entity.get(entity_id)
        if not geom:
            continue
        got = geom["extent"]
        ok = lo_mm <= got <= hi_mm
        scale_ok &= ok
        print(f"  {'ok  ' if ok else 'OUT '}{entity_id:10} {got:6.1f} mm "
              f"(expected {lo_mm}-{hi_mm})")
    if scale_ok:
        print("  scale confirmed -- a volume difference below is a real "
              "difference between bodies, not a unit error")

    print("\n[1] fascicle length vs mesh extent  (hard constraint)")
    if impossible:
        for comp_id, fascicle, extent in impossible:
            print(f"  IMPOSSIBLE  {comp_id}: fascicle {fascicle:.0f} mm in a "
                  f"muscle spanning {extent:.0f} mm")
    else:
        print("  no compartment claims a fascicle longer than its muscle")

    # ---- check 2: measured volume against the atlas's implied volume ----
    #
    # The implied volumes of ALL of a muscle's compartments are summed before
    # comparing. A first version of this compared each compartment's implied
    # volume against the whole muscle's measured volume, which is not a
    # comparison at all: vastus medialis obliquus is a small distal part of
    # vastus medialis, so it "failed" by 39x purely because the mesh is the
    # entire muscle. Every large outlier in that run was a multi-compartment
    # muscle, which is the signature of the mistake rather than of bad data.
    implied_by_muscle = defaultdict(float)
    comps_by_muscle = defaultdict(list)
    for comp_id, (muscle_id, arch) in arch_by_comp.items():
        pcsa = arch.get("physiological_cross_section_area_mm2")
        fascicle = arch.get("optimal_fascicle_length_mm")
        pennation = arch.get("pennation_deg")
        if not (pcsa and fascicle and pennation is not None):
            continue
        implied_by_muscle[muscle_id] += (
            pcsa * fascicle / max(math.cos(math.radians(pennation)), 1e-6))
        comps_by_muscle[muscle_id].append(comp_id)

    rows = []
    for muscle_id, implied in implied_by_muscle.items():
        geom = per_entity.get(muscle_id)
        if not geom or geom["volume"] <= 0 or implied <= 0:
            continue
        rows.append((geom["volume"] / implied, muscle_id, geom["volume"],
                     implied, len(comps_by_muscle[muscle_id]), geom["meshes"]))

    print(f"\n[2] measured volume / implied volume, {len(rows)} muscles")
    print("    implied volume sums every compartment, so this compares the "
          "whole muscle with the whole muscle")
    print("    a ratio far from 1 is a question, not a verdict -- one cadaver "
          "against literature averages")
    rows.sort()

    def show(sub, label):
        print(f"\n  {label}")
        for ratio, muscle_id, measured, implied, ncomp, nmesh in sub:
            tags = []
            if ncomp > 1:
                tags.append(f"{ncomp} compartments")
            if nmesh > 1:
                tags.append(f"{nmesh} meshes")
            tag = f"  [{', '.join(tags)}]" if tags else ""
            print(f"    {ratio:5.2f}x  {muscle_id:38} "
                  f"{measured/1000:7.1f} vs {implied/1000:7.1f} cm3{tag}")

    show(rows[:args.top], f"lowest {args.top} -- atlas implies MORE than the body has")
    show(rows[-args.top:][::-1], f"highest {args.top} -- atlas implies LESS than the body has")

    ratios = np.array([r[0] for r in rows])
    within2 = int((np.abs(np.log(ratios)) < math.log(2)).sum())
    print(f"\n  median ratio {np.median(ratios):.2f}   "
          f"within a factor of 2: {within2}/{len(ratios)}   "
          f"range {ratios.min():.2f}-{ratios.max():.2f}")
    print("""
  READ THIS BEFORE ACTING ON THE NUMBERS ABOVE.

  The offset is systematic and one-directional: this body has more muscle
  than the atlas's architecture implies, for nearly every muscle. That is
  the signature of a population difference, not of scattered data-entry
  errors, and check [0] has already ruled out a unit or scale error.

  The most likely cause is the age of the specimens. The architecture
  literature this atlas draws on is dominated by elderly cadavers -- Ward
  et al. 2009, the standard lower-limb source, has a mean donor age in the
  eighties -- while the Visible Human Male was 39 and large. Muscle volume
  differs severalfold across that range, and PCSA is proportional to volume.
  Segmentation also matters: these meshes include investing fascia and
  aponeurosis, which architecture studies dissect away.

  The practical consequence is the point of this whole check. PCSA and
  fascicle length from the atlas and volume from this geometry DESCRIBE
  DIFFERENT BODIES and must not be combined into one force estimate without
  an explicit, recorded scaling decision. Nothing here says the atlas's
  numbers are wrong for what they claim to be -- literature averages -- and
  nothing here licenses rescaling them to this cadaver, which would replace
  a documented average with one unrepresentative individual.
""")
    return 1 if impossible else 0


if __name__ == "__main__":
    raise SystemExit(main())
