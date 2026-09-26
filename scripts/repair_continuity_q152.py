#!/usr/bin/env python3
"""Q152: diagnose + repair fragmented/severe-break MUSCLES on both specimens.

Reuses Q115's own source-resolution machinery (scripts/triage_continuity_q115.py:
resolve_source / resolve_split_mask / load_volume_cached) so every muscle here is
measured against the exact same raw voxel mask Q113/Q114/Q115 used, not a fresh
re-derivation that could quietly disagree with their own numbers.

For every (id, side, body) muscle group below main_frac 0.99, classifies the cause
per the Q112/Q152 diagnostic:

  PIPELINE_ARTIFACT  -- source is (near-)one piece (source_main_frac >= 0.90) but
                        shipped is fragmented (gap >= 0.15): decimation/clustering
                        destroyed real continuity. Reuses Q115's own classification
                        where available (identical thresholds) rather than
                        recomputing; new muscles Q115 never triaged get the same
                        test run fresh here.
  GAP_BRIDGE         -- source itself has >1 component, but two components are
                        separated ONLY by a run of completely label-empty Z-slices
                        (the true "slice-gap" case): a run of z-indices, strictly
                        between the two components' own z-extents, where this
                        label has zero voxels anywhere in the volume. Bridged if
                        the run's physical length <= 10mm; left alone (reported)
                        if longer.
  DROP_ISLAND        -- a component < 2% of the label's total voxel count AND
                        > 15mm (centroid-to-centroid) from the main component:
                        a stray speck, not real anatomy connecting to anything.
  ANATOMICAL         -- what's left: components not explained by a bridgeable
                        gap or a droppable island. Includes both genuinely
                        separate anatomical bellies (interossei, adductor
                        hallucis 2 heads) and previously fully investigated,
                        declined, non-fixable source defects (Q113/Q114's own
                        pectoralis_minor/longus_colli/geniohyoid_l/hyoglossus_r/
                        internal_oblique_r/transversus_abdominis_r) -- distinguished
                        in the 'reason' field, never silently merged.

Read-only diagnosis (writes only the report JSON) unless --apply is given, which
then (a) for PIPELINE_ARTIFACT ids, writes a small per-source '_contfix' subject
at --smooth 0.0 (Q116's own pattern) and (b) for GAP_BRIDGE ids, writes a bridged
copy of the source volume (fill only, never touching another label's voxels) and
converts JUST that id from it into the same contfix subject family.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from engine import volume_ingest as vol  # noqa: E402
import triage_continuity_q115 as triage  # noqa: E402
from transfer.shape_interp import interpolate_labels_z  # noqa: E402

AUDIT_JSON = REPO_ROOT / "data" / "derived" / "Q112_full_continuity_audit.json"
Q115_JSON = REPO_ROOT / "data" / "derived" / "Q115_triage.json"
BUILD = REPO_ROOT / "build" / "vh"
BRIDGED_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs" / "q152_bridged"

MAX_GAP_MM = 10.0
ISLAND_MAX_VOL_FRAC = 0.02
ISLAND_MIN_DIST_MM = 15.0

# Muscles Q113/Q114 already fully, independently investigated to a final,
# documented disposition. Reused verbatim (see PROJECT_STATE.md Q113/Q114
# entries) rather than re-measured, since re-measuring would just reproduce
# their own numbers.
ALREADY_RESOLVED = {
    "external_intercostals_l": ("PIPELINE_ARTIFACT", "Q114: FIXED (BUDGET_OVERRIDE 8000->16000, "
        "--smooth 0.0 on ct_v{h,f}m_twall). Shipped main_frac now 0.75(F)/0.96(M), improved but "
        "short of 0.99 -- accepted, not re-attempted here."),
    "external_intercostals_r": ("PIPELINE_ARTIFACT", "Q114: FIXED, same as _l. Shipped 0.94(F)/0.96(M)."),
    "longus_colli_l": ("ANATOMICAL", "Q114: DECLINED. Raw source already severely fragmented "
        "(l 6 comp/0.31) from ct_vhf_dneck's own rule-based marker/watershed construction -- a "
        "genuine source-level defect, not decimation and not a fillable slice gap (the fragments "
        "are scattered in 3-D, not separated by an empty Z-run). No fix available in this task's "
        "remedy set; not multi-belly anatomy either, disclosed as a known limitation."),
    "longus_colli_r": ("ANATOMICAL", "Q114: DECLINED, same cause as longus_colli_l (source r 4 comp/0.37)."),
    "pectoralis_minor_l": ("ANATOMICAL", "Q114: DECLINED. Independent per-body rule-based "
        "reconstruction, self-documented 'over-inclusive', already severely fragmented at the "
        "source (M 10 comp/0.47, F 12 comp/0.50) before any decimation. Known algorithmic "
        "limitation, not real anatomy and not a bridgeable gap."),
    "pectoralis_minor_r": ("ANATOMICAL", "Q114: DECLINED, same cause (M 11 comp/0.37, F 6 comp/0.52)."),
    "geniohyoid_l": ("ANATOMICAL", "Q114: DECLINED. A THIRD failure mode found and fully "
        "investigated: raw voxel mask is well connected (0.93) but marching-cubes surfacing itself "
        "renders a sub-voxel-thin bridge as two touching-but-unjoined shells; --smooth 0.0 on the "
        "pre-decimation mesh does not recover it either (0.478). Not a decimation/clustering "
        "budget issue, not a Z-slice gap (the mask IS connected pre-surfacing), and not multi-belly "
        "anatomy. No fix in this task's remedy set."),
    "hyoglossus_r": ("ANATOMICAL", "Q114: DECLINED, same third failure mode (raw 0.52, "
        "smooth=0.0 pre-decim 0.457)."),
    "internal_oblique_r": ("ANATOMICAL", "Q114: DECLINED (male). ct_vhm_abw raw voxel 20 comp/0.53, "
        "IDENTICAL component count to shipped -- decimation only reweights, never adds fragments. "
        "Own mapping note: 'lower wall below the iliac crest missing' -- a real segmentation "
        "incompleteness (missing anatomy, not a fillable gap between two present slices)."),
    "transversus_abdominis_r": ("ANATOMICAL", "Q114: DECLINED (female, transferred from the male's "
        "ct_vhm_abw label 4, same root cause as internal_oblique_r: 17 comp/0.54 at the raw source)."),
}


def classify_component(vol_frac: float, dist_mm: float, has_z_gap: bool, gap_mm: float | None,
                        max_gap_mm: float = MAX_GAP_MM,
                        island_max_vol_frac: float = ISLAND_MAX_VOL_FRAC,
                        island_min_dist_mm: float = ISLAND_MIN_DIST_MM) -> str:
    """Pure decision rule for one secondary component vs. the muscle's main
    component, per the Q152 diagnostic (task categories b/c/d). Island check
    is applied FIRST: a tiny far-away speck is dropped even if it happens to
    also sit across an empty Z-run from the main body, since dropping it is
    strictly less invasive than bridging a gap into it.

    Returns one of: 'DROP_ISLAND', 'GAP_BRIDGE', 'GAP_TOO_LARGE', 'NOT_Z_ALIGNED'.
    """
    if vol_frac < island_max_vol_frac and dist_mm > island_min_dist_mm:
        return "DROP_ISLAND"
    if has_z_gap and gap_mm is not None:
        return "GAP_BRIDGE" if gap_mm <= max_gap_mm else "GAP_TOO_LARGE"
    return "NOT_Z_ALIGNED"


def find_z_gap(main_zmin: int, main_zmax: int, other_zmin: int, other_zmax: int,
               z_spacing_mm: float) -> tuple[bool, float | None, int, int]:
    """Whether `other`'s z-extent is disjoint from `main`'s with a run of
    z-indices strictly between them (a candidate slice gap), the physical
    length of that run in mm, and its [lo, hi] z-index bounds (inclusive).
    Does NOT check the run is actually label-empty -- callers must confirm
    that against the real mask (two components can be Z-disjoint yet still
    have another part of the SAME label occupying an intermediate slice,
    which is not a gap at all)."""
    # int(): the z-extents passed in are frequently numpy int64 (from
    # np.argwhere/find_objects upstream) -- plain Python ints here keep the
    # JSON report's own numbers as real numbers, never silently coerced to
    # strings by a `default=str` json.dumps fallback that only numpy's
    # non-native ints would ever need.
    gz_lo = int(min(main_zmax, other_zmax) + 1)
    gz_hi = int(max(main_zmin, other_zmin) - 1)
    disjoint = main_zmax < other_zmin or other_zmax < main_zmin
    has_gap = disjoint and gz_hi >= gz_lo
    gap_mm = float((gz_hi - gz_lo + 1) * z_spacing_mm) if has_gap else None
    return has_gap, gap_mm, gz_lo, gz_hi


def zaxis_index(codes: str) -> int:
    for i, c in enumerate(codes):
        if c in ("S", "I"):
            return i
    raise ValueError(f"no S/I axis in codes {codes!r}")


def component_stats(mask: np.ndarray):
    """26-connected components of `mask`, cropped to its bounding box (+1
    voxel pad) for speed. Returns (n_components, cropped comp label array,
    the crop's lo offset into the full array)."""
    from scipy import ndimage
    coords_all = np.argwhere(mask)
    lo = np.maximum(coords_all.min(axis=0) - 1, 0)
    hi = np.minimum(coords_all.max(axis=0) + 2, mask.shape)
    cropped = mask[lo[0]:hi[0], lo[1]:hi[1], lo[2]:hi[2]]
    comp, n = ndimage.label(cropped, structure=np.ones((3, 3, 3), dtype=int))
    return n, comp, lo


def mesh_components(verts: np.ndarray, faces: np.ndarray) -> list[np.ndarray]:
    """Connected components of a triangle mesh by shared VERTEX (union-find
    over face edges). Operates entirely in whatever frame `verts` is already
    in (atlas mm for anything already in build/vh) -- no affine/origin needed
    at all, which is exactly why island-dropping is done this way rather
    than by reconverting from the raw volume: it cannot introduce a
    placement error, only ever remove already-correctly-placed triangles.
    Returns a list of boolean face masks, one per component, largest first.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(verts)
    i = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    j = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    data = np.ones(len(i), dtype=bool)
    adj = coo_matrix((data, (i, j)), shape=(n, n))
    n_comp, labels = connected_components(adj, directed=False)
    face_comp = labels[faces[:, 0]]  # a face's 3 verts always share one component
    order = sorted(range(n_comp), key=lambda c: -(face_comp == c).sum())
    return [face_comp == c for c in order]


def drop_mesh_islands(subject: str, atlas_id: str, side: str | None) -> dict:
    """Load `subject`'s already-atlas-frame mesh for (atlas_id, side), find
    its own connected components, and drop ONLY the ones that independently
    pass the same island rule used at diagnosis time (classify_component:
    < 2% of faces AND > 15mm centroid-to-main-centroid) -- never just "every
    component but the largest". A MIXED_ISLAND_AND_ANATOMICAL id can have a
    genuine secondary belly alongside a stray speck; dropping indiscriminately
    would silently delete real anatomy along with the defect. Never touches
    any other structure's geometry in the subject."""
    manifest = json.loads((BUILD / subject / "manifest.json").read_text())
    verts_all = np.frombuffer((BUILD / subject / "vertices.f32").read_bytes(),
                               dtype=np.float32).reshape(-1, 3)
    faces_all = np.frombuffer((BUILD / subject / "faces.u32").read_bytes(),
                               dtype=np.uint32).reshape(-1, 3)
    side_norm = None if side in (None, "none") else side
    recs = [s for s in manifest["structures"]
            if s["atlas_id"] == atlas_id and s.get("side") == side_norm]
    if not recs:
        raise SystemExit(f"{atlas_id}/{side} not found in {subject}'s manifest")
    all_v, all_f, offset = [], [], 0
    for rec in recs:
        v = verts_all[rec["vertex_offset"]:rec["vertex_offset"] + rec["vertex_count"]]
        f = (faces_all[rec["face_offset"]:rec["face_offset"] + rec["triangle_count"]]
             .astype(np.int64) - rec["vertex_offset"] + offset)
        all_v.append(v); all_f.append(f); offset += len(v)
    v = np.concatenate(all_v).astype(np.float64)
    f = np.concatenate(all_f)
    comps = mesh_components(v, f)  # largest first
    if len(comps) <= 1:
        return {"dropped": False, "reason": "mesh has only 1 component "
                "(the fragmentation this atlas_id shows is a decimation "
                "artifact or genuinely sub-voxel, not separable mesh islands)"}
    main_mask = comps[0]
    main_centroid = v[np.unique(f[main_mask])].mean(axis=0)
    main_faces_n = int(main_mask.sum())
    total_faces = len(f)

    drop_masks, keep_masks, dropped_info = [], [main_mask], []
    for m in comps[1:]:
        verts_here = v[np.unique(f[m])]
        vol_frac = m.sum() / total_faces
        dist_mm = float(np.linalg.norm(verts_here.mean(axis=0) - main_centroid))
        disposition = classify_component(vol_frac, dist_mm, has_z_gap=False, gap_mm=None)
        if disposition == "DROP_ISLAND":
            drop_masks.append(m)
            dropped_info.append({"min": v[f[m]].min(axis=0).tolist(),
                                  "max": v[f[m]].max(axis=0).tolist(),
                                  "face_frac": round(float(vol_frac), 4),
                                  "centroid_dist_mm": round(dist_mm, 2)})
        else:
            keep_masks.append(m)  # not an island by the same rule -- leave it (anatomical/unresolved)

    if not drop_masks:
        return {"dropped": False, "reason": "no component independently qualifies as a "
                "droppable island on the built mesh (< 2% of faces AND > 15mm from the "
                "main body) -- the diagnosis's source-level island call did not carry "
                "over to this decimated mesh; left untouched rather than over-dropping"}

    keep_mask = np.zeros(total_faces, dtype=bool)
    for m in keep_masks:
        keep_mask |= m
    kept_faces_raw = f[keep_mask]
    used_verts = np.unique(kept_faces_raw)
    remap = -np.ones(len(v), dtype=np.int64)
    remap[used_verts] = np.arange(len(used_verts))
    kept_v = v[used_verts]
    kept_f = remap[kept_faces_raw]
    dropped_face_frac = sum(m.sum() for m in drop_masks) / total_faces
    return {"dropped": True, "kept_verts": kept_v, "kept_faces": kept_f,
            "n_components": len(comps), "n_dropped": len(drop_masks),
            "dropped_face_frac": round(float(dropped_face_frac), 4),
            "dropped_bbox": dropped_info}


def bridge_label_in_volume(volume: np.ndarray, label: int, z_ax: int,
                            z_spacing_mm: float,
                            approved_ranges: list[tuple[int, int]] | None = None
                            ) -> tuple[np.ndarray, int]:
    """Fill empty-slice gaps for ONE label, by shape-based (signed-distance)
    interpolation between its own two nearest real slices, reusing
    scripts/transfer/shape_interp.py verbatim.

    Never extrapolates past the label's own first/last real slice (that
    function's own guarantee) and never overwrites another structure's
    voxels: a filled voxel is only written where `volume` was background
    (0) beforehand. `source_spacing_mm == target_spacing_mm` (no
    resampling) means every already-real slice is reproduced exactly and
    ONLY the genuinely empty slices in between change.

    `approved_ranges`, when given, is a list of inclusive [lo, hi] z-index
    ranges (the SAME z-index space as `volume`) -- the fill is restricted to
    those ranges only. This matters because a label can have several gaps at
    once (this project's cryo-derived muscles often do): interpolate_labels_z
    itself fills EVERY gap between a label's first and last real slice with
    no distance limit, so a muscle with one 9mm (bridgeable) gap and another
    40mm (not bridgeable, per this task's 10mm cap) gap would otherwise get
    the 40mm one silently bridged too. Passing None fills every gap (used by
    tests that construct a single, already-known-short gap directly).

    Returns (new_volume, n_voxels_added).
    """
    labelvol = np.moveaxis(volume, z_ax, 0)
    bridged, _zpos, _report = interpolate_labels_z(
        labelvol, source_spacing_mm=z_spacing_mm, target_spacing_mm=z_spacing_mm,
        labels=[label])
    bridged = np.moveaxis(bridged, 0, z_ax)
    fillable = (bridged == label) & (volume == 0)
    if approved_ranges is not None:
        zone = np.zeros(volume.shape[z_ax], dtype=bool)
        for lo, hi in approved_ranges:
            zone[lo:hi + 1] = True
        mask3d = np.zeros_like(fillable)
        idx = [slice(None)] * volume.ndim
        for zi in np.nonzero(zone)[0]:
            idx[z_ax] = zi
            mask3d[tuple(idx)] = True
        fillable &= mask3d
    new_volume = volume.copy()
    new_volume[fillable] = label
    return new_volume, int(fillable.sum())


def drop_volume_islands(volume: np.ndarray, label: int, z_ax: int, spacing: np.ndarray,
                         island_max_vol_frac: float = ISLAND_MAX_VOL_FRAC,
                         island_min_dist_mm: float = ISLAND_MIN_DIST_MM
                         ) -> tuple[np.ndarray, int, list[dict]]:
    """Voxel-space analogue of drop_mesh_islands (Q156), meant to run AFTER
    bridge_label_in_volume on the SAME volume/label: drops any REMAINING
    connected component of this label that independently qualifies as a
    stray island by the exact same rule diagnosis used (classify_component's
    island test: < island_max_vol_frac of the label's own total voxels AND
    > island_min_dist_mm centroid-to-centroid from the main component) --
    never a component that fails that test, even a small one, since it could
    be a genuinely thin part of the same structure.

    Why this exists: diagnose_one's own cause selection picks GAP_BRIDGE
    whenever there is at least one bridgeable gap, even when the SAME label
    also carries many separate droppable islands (found to be the common
    case for this project's cryo-derived limb muscles: a single real
    slice-gap plus dozens of unrelated segmentation-noise flecks). Before
    this fix, apply_voxel_fixes only ever bridged the approved gap for a
    GAP_BRIDGE id and left every one of those islands in the reconverted
    mesh, which is why bridging alone measurably improved
    source_main_frac (voxel-level) but left shipped main_frac essentially
    unchanged after decimation -- every one of Q156's 22 female GAP_BRIDGE
    ids had this exact shape. Re-testing components fresh here (rather than
    trusting the diagnosis JSON's own stored island list, which only has
    aggregate stats, not voxel coordinates) guarantees this uses the exact
    same live rule and never drops a component the diagnosis didn't also
    call an island.

    Never touches another label's voxels (only ever clears voxels that are
    already this exact label) and never extends the label into new territory
    -- purely a removal, exactly like drop_mesh_islands's own mesh-space
    guarantee. Returns (new_volume, n_voxels_dropped, dropped_component_info).
    """
    from scipy import ndimage
    mask = volume == label
    if not mask.any():
        return volume, 0, []
    n, comp_arr, crop_lo = component_stats(mask)
    if n <= 1:
        return volume, 0, []
    sizes = sorted(((int((comp_arr == i).sum()), i) for i in range(1, n + 1)), reverse=True)
    total = sum(s for s, _i in sizes)
    main_size, main_i = sizes[0]
    main_centroid = np.array(ndimage.center_of_mass(comp_arr == main_i)) + crop_lo

    new_volume = volume
    n_dropped = 0
    dropped_info = []
    hi = crop_lo + np.array(comp_arr.shape)
    region = new_volume[crop_lo[0]:hi[0], crop_lo[1]:hi[1], crop_lo[2]:hi[2]]
    for size, i in sizes[1:]:
        vol_frac = size / total
        centroid = np.array(ndimage.center_of_mass(comp_arr == i)) + crop_lo
        dist_mm = float(np.linalg.norm((centroid - main_centroid) * spacing))
        if vol_frac < island_max_vol_frac and dist_mm > island_min_dist_mm:
            if new_volume is volume:
                new_volume = volume.copy()
                region = new_volume[crop_lo[0]:hi[0], crop_lo[1]:hi[1], crop_lo[2]:hi[2]]
            region[comp_arr == i] = 0
            n_dropped += size
            dropped_info.append({"size": size, "vol_frac": round(vol_frac, 4),
                                  "centroid_dist_mm": round(dist_mm, 2)})
    return new_volume, n_dropped, dropped_info


def derive_origin(subject: str) -> tuple[np.ndarray, float]:
    """The rigid translation `ingest_volume_geometry.py convert --origin` needs
    to place a FRESH reconversion of `subject`'s own raw source volume back
    into exact alignment with its ALREADY-BUILT (and already atlas-frame)
    build/vh/<subject> mesh.

    Never guessed and never taken from another subject's own origin
    constant (subjects converted from different source blocks legitimately
    use different origins -- ct_vhm_foot's is not ct_vhm's). Instead measured
    directly, the only way that's actually correct: for every OTHER label
    this exact volume already contributes to the subject (i.e. every
    structure whose placement is already known-correct), the raw voxel
    surface is re-extracted at the SAME smoothing the subject was originally
    converted with, converted to world mm via the volume's own affine
    (voxels_to_atlas, no origin subtracted yet), and its centroid compared
    to the ALREADY-BUILT mesh's own centroid for that same atlas_id -- their
    difference IS the origin. Averaging (median) this over every label in
    the subject cancels most of the sub-mm noise a single label's
    decimation/quantization could introduce; the spread across labels is
    returned too so a caller can refuse to trust a noisy estimate rather
    than silently applying it.
    """
    mapping_path = BUILD / f"{subject}_volume_mapping.json"
    if not mapping_path.exists():
        mapping_path = REPO_ROOT / "mappings" / "subjects" / f"{subject}_volume_mapping.json"
    mapping = json.loads(mapping_path.read_text())
    manifest = json.loads((BUILD / subject / "manifest.json").read_text())
    verts_all = np.frombuffer((BUILD / subject / "vertices.f32").read_bytes(),
                               dtype=np.float32).reshape(-1, 3)
    smooth = manifest.get("surface_smoothing_sigma_voxels", 1.0)
    # The per-subject manifest's OWN 'source_volume' (written fresh by the last real
    # `convert` run) is preferred over the separate `<subject>_volume_mapping.json`
    # copy, which can go stale (seen for ct_vhm_armm: its mapping copy still pointed
    # at a since-cleaned scratchpad path from whenever `propose` first ran, while the
    # manifest's own record already carried the real, current file).
    source_volume = manifest.get("source_volume") or mapping["source_volume"]
    volume, affine, _codes = vol.load_labels(Path(source_volume))

    by_id = {}
    for s in manifest["structures"]:
        by_id.setdefault((s["atlas_id"], s.get("side")), []).append(s)

    estimates = []
    for entry in mapping["entries"]:
        if not entry.get("atlas_id") or entry.get("split_parts"):
            continue  # split labels need the splitter re-run; skip for this estimate
        key = (entry["atlas_id"], entry.get("side"))
        recs = by_id.get(key)
        if not recs or not (volume == entry["label"]).any():
            continue
        v_raw, _f_raw = vol.label_surface(volume, entry["label"], step=1, smooth=smooth)
        if len(v_raw) == 0:
            continue
        world = vol.voxels_to_atlas(v_raw, affine)
        built = np.concatenate([
            verts_all[r["vertex_offset"]:r["vertex_offset"] + r["vertex_count"]] for r in recs
        ]).astype(np.float64)
        estimates.append(world.mean(axis=0) - built.mean(axis=0))
    if not estimates:
        raise SystemExit(f"{subject}: no label gave a usable origin estimate")
    estimates = np.array(estimates)
    origin = np.median(estimates, axis=0)
    spread = float(np.max(np.linalg.norm(estimates - origin, axis=1)))
    return origin, spread


def diagnose_one(body: str, rec: dict, existing_cls: dict | None) -> dict:
    atlas_id, side = rec["id"], rec["side"]
    side_norm = None if side in (None, "none") else side
    subjects = rec.get("subjects") or []
    uniq_subjects = list(dict.fromkeys(s for s in subjects if s))
    if not uniq_subjects:
        return {"cause": "UNRESOLVED", "reason": "no subject recorded in audit"}

    # Use the first resolvable volume source (matches Q115's own convention;
    # nearly every muscle here has exactly one).
    src = None
    resolved_subject = None
    unclear_reasons = []
    for subj in uniq_subjects:
        s = triage.resolve_source(subj, atlas_id, side_norm)
        if s["kind"] == "volume":
            src, resolved_subject = s, subj
            break
        unclear_reasons.append(s.get("reason", ""))
    if src is None:
        # Q152b bug fix: this used to also match on the bare substring "viewer
        # bundle", which resolve_source's OWN generic message contains for
        # EVERY non-numeric-suffix label, not only real Z-Anatomy transfers --
        # a totally different, unrelated case (a muscle recovered as decimated
        # mesh-only geometry from the male's own PUBLISHED CT/cryo viewer
        # bundle, e.g. vhm_both's biceps_femoris_l/gastrocnemius_r/iliopsoas_r)
        # was silently mislabeled OUT_OF_SCOPE_TRANSFER with this branch's own
        # hardcoded "Z-Anatomy reference-mesh transfer... 25.4mm error" text --
        # false for those ids, which are real segmented CT/cryo anatomy with
        # no error estimate like that at all. Never triggered in the first
        # 110-id pass (its zanatomy-only ids happened to fall in that pass's
        # own NOT_YET_DIAGNOSED remainder instead, per PROJECT_STATE Q152),
        # only surfaced now that this batch actually contains recovered-
        # bundle ids. Matched narrowly now: "zanatomy" only appears in
        # resolve_source's reason when it actually chased a transfer's own
        # 'from' field to that literal subject folder (build/vh/zanatomy/...),
        # the real signature of a per-bone Z-Anatomy transfer.
        if any("zanatomy" in r for r in unclear_reasons) or \
           any("zan2vh" in s for s in uniq_subjects):
            return {"cause": "OUT_OF_SCOPE_TRANSFER",
                    "reason": ("Sourced from a per-bone Z-Anatomy reference-mesh transfer "
                               "(scripts/transfer/limb_per_bone_transfer.py), not a segmented "
                               "CT/cryo label volume -- there is no raw voxel mask to run "
                               "scipy.ndimage.label on, no real Z-slices to interpolate between, "
                               "and nothing to reconvert with a decimation budget. Already a "
                               "disclosed, out-of-scope limitation of that transfer (Q147/Q150/"
                               "Q150b/Q151: median centroid error 25.4mm(M)/well above the ship "
                               "bar), not a Q152-class defect. Several of these (interossei, "
                               "adductor_hallucis) are also genuinely multi-bellied anatomy on top "
                               "of that -- left untouched either way.")}
        # The OTHER, distinct non-numeric-suffix case this branch used to
        # conflate with the one above: real CT/cryo-segmented anatomy whose
        # only surviving geometry in this container is the DECIMATED mesh
        # recovered from the male's own published viewer bundle (Version 25)
        # -- his DU lower-limb/torso source files are not re-downloadable
        # (see scripts/vhm_rebuild_bundle.sh's own header), so there is no
        # raw voxel mask left to measure at all, exactly like the zanatomy
        # case's own missing-mask limitation, but NOT a Z-Anatomy transfer
        # and NOT carrying its 25.4mm error figure -- a real muscle,
        # genuinely fragmented in this decimated recovery, with nothing left
        # to reconvert or interpolate. Named separately so it is never
        # confused with the transfer case above.
        if any("published viewer" in r or "published male viewer" in r
               for r in unclear_reasons):
            return {"cause": "NO_RAW_SOURCE_RECOVERED_BUNDLE",
                    "reason": ("Only a decimated mesh recovered from the male's own published "
                               "viewer bundle (Version 25) survives in this container for this "
                               "muscle -- his original raw source files are not re-downloadable "
                               "(see scripts/vhm_rebuild_bundle.sh), so there is no raw voxel mask "
                               "to run scipy.ndimage.label on, no real Z-slices to interpolate "
                               "between, and nothing to reconvert with a decimation budget. This is "
                               "real, genuinely-segmented CT/cryo anatomy (unlike the Z-Anatomy "
                               "per-bone transfer case), just with its own raw mask permanently "
                               "unavailable -- a disclosed data-availability limitation, not a "
                               "Q152-class defect and not fabricated.")}
        return {"cause": "UNRESOLVED", "reason": "no raw source volume resolvable: "
                + "; ".join(unclear_reasons)}

    volume, affine, codes = triage.load_volume_cached(src["path"])
    if src.get("split_from"):
        mask = triage.resolve_split_mask(src)
        if mask is None:
            return {"cause": "UNRESOLVED", "reason": "could not reproduce split submask"}
    else:
        mask = volume == src["label"]
    if not mask.any():
        return {"cause": "UNRESOLVED", "reason": "label absent from its own source volume"}

    # voxel spacing per axis = norm of the affine's corresponding COLUMN
    # (each column is the world-space displacement for a unit step along
    # that voxel axis), not the row -- using the row would silently give
    # the wrong number for any non-diagonal (rotated) affine.
    spacing = np.array([np.linalg.norm(affine[:3, k]) for k in range(3)])
    z_ax = zaxis_index(codes)

    n, comp_arr, crop_lo = component_stats(mask)
    sizes = sorted((int((comp_arr == i).sum()) for i in range(1, n + 1)), reverse=True)
    total = sum(sizes)
    source_main_frac = sizes[0] / total if total else 0.0

    base = {
        "resolved_subject": resolved_subject, "source_path": src["path"],
        "label": src["label"], "n_components_source": n,
        "source_main_frac": round(source_main_frac, 4),
        "shipped_main_frac": rec["main_frac"], "shipped_status": rec["status"],
    }

    if n <= 1:
        # Source is one piece; the fragmentation is entirely a shipped-mesh
        # artifact (decimation/clustering or smoothing). Confirm against the
        # existing Q115/new-triage classification when we have one.
        base["cause"] = "PIPELINE_ARTIFACT"
        base["reason"] = ("Raw source label is a single connected component "
                           f"(main_frac {source_main_frac:.3f}); shipped mesh main_frac "
                           f"{rec['main_frac']:.3f} -- decimation/clustering severed it.")
        return base

    if existing_cls and existing_cls.get("classification") == "LIKELY_PIPELINE_ARTIFACT":
        base["cause"] = "PIPELINE_ARTIFACT"
        base["reason"] = ("Q115 triage: source_main_frac "
                           f"{existing_cls.get('source_main_frac')} vs shipped "
                           f"{existing_cls.get('shipped_main_frac')}, gap {existing_cls.get('gap_ratio')} "
                           ">= 0.15 with source >= 0.90 -- reused verbatim.")
        return base

    # Source itself is genuinely fragmented (n>1, not near-single-piece).
    # Get real per-component z-extents (world voxel index along the S/I
    # axis) and centroids, to test the gap-bridge and island rules.
    # scipy.ndimage.find_objects/center_of_mass give every component's bbox
    # and centroid in ONE pass each; a per-component np.argwhere (as an
    # earlier version of this function did) instead re-scans the whole
    # cropped array once per component, which is fine for the handful of
    # components a typical muscle has but became the dominant cost for the
    # ~100+ noise-fleck components some cryo-derived arm labels turned out
    # to carry (see PROJECT_STATE Q152).
    from scipy import ndimage
    slices = ndimage.find_objects(comp_arr)
    centroids = ndimage.center_of_mass(np.ones_like(comp_arr), comp_arr, index=range(1, n + 1))
    full_info = []
    for i, sl, cen in zip(range(1, n + 1), slices, centroids):
        size = int((comp_arr[sl] == i).sum())
        zmin = int(sl[z_ax].start) + crop_lo[z_ax]
        zmax = int(sl[z_ax].stop) - 1 + crop_lo[z_ax]
        centroid_vox = np.array(cen) + crop_lo
        full_info.append({"size": size, "zmin": zmin, "zmax": zmax, "centroid_vox": centroid_vox})
    full_info.sort(key=lambda d: -d["size"])
    main = full_info[0]
    others = full_info[1:]

    z_spacing_mm = spacing[z_ax]
    # Per-z occupancy of this label, computed ONCE for the whole mask (Q152b):
    # a per-candidate-gap loop of `np.take(mask, zi, axis=z_ax).any()` calls
    # was the actual compute-budget blocker behind the male shoulder-girdle/
    # trunk/hand NOT_YET_DIAGNOSED remainder -- for a volume stored with the
    # Z axis as the LARGEST-stride axis (e.g. this source's 'LPS' codes,
    # z_ax=2 with stride 262144 on a 512x512x844 array), a single such take
    # is a maximally-scattered gather over the whole mask and measured
    # ~1.5s EACH; a several-hundred-slice gap (routine on these heavily-
    # fragmented cryo labels) made confirming just one candidate gap take
    # minutes. `mask.any()` reduced over the other two axes is one
    # vectorized pass over the whole array (~0.02s total here) and gives the
    # exact same per-z emptiness answer this loop needs for every candidate
    # gap at once -- no result changes, only how it's computed.
    other_axes = tuple(ax for ax in range(mask.ndim) if ax != z_ax)
    z_profile = mask.any(axis=other_axes)
    bridges, islands, unresolved = [], [], []
    for c in others:
        vol_frac = c["size"] / total
        dist_mm = float(np.linalg.norm((c["centroid_vox"] - main["centroid_vox"]) * spacing))
        has_z_gap, gap_mm, gz_lo, gz_hi = find_z_gap(
            main["zmin"], main["zmax"], c["zmin"], c["zmax"], z_spacing_mm)
        # confirm the candidate gap band is truly label-empty (every slice
        # in it has zero voxels for this label anywhere in the volume) --
        # find_z_gap only checks the two components' own z-extents are
        # disjoint, not that nothing else of this label sits between them.
        if has_z_gap and z_profile[gz_lo:gz_hi + 1].any():
            has_z_gap, gap_mm = False, None
        disposition = classify_component(vol_frac, dist_mm, has_z_gap, gap_mm)
        entry = {"size": c["size"], "vol_frac": round(vol_frac, 4),
                 "centroid_dist_mm": round(dist_mm, 2),
                 "gap_mm": round(gap_mm, 2) if gap_mm else None,
                 "disposition": disposition}
        if disposition == "DROP_ISLAND":
            islands.append(entry)
        elif disposition == "GAP_BRIDGE":
            entry["gap_zmin"], entry["gap_zmax"] = gz_lo, gz_hi
            bridges.append(entry)
        else:
            unresolved.append(entry)

    base["z_axis"] = z_ax
    base["main_component"] = {"size": main["size"], "zmin": main["zmin"], "zmax": main["zmax"]}
    base["other_components"] = [
        {"size": c["size"], "zmin": c["zmin"], "zmax": c["zmax"]} for c in others]
    base["bridges"] = bridges
    base["islands"] = islands
    base["unresolved_components"] = unresolved

    if bridges:
        base["cause"] = "GAP_BRIDGE"
        base["reason"] = (f"{len(bridges)} of {len(others)} secondary component(s) separated from "
                           f"the main body only by a label-empty Z-run <= {MAX_GAP_MM}mm; bridge "
                           "with shape-based SDF interpolation between the two nearest real slices.")
    elif islands and not unresolved:
        base["cause"] = "DROP_ISLAND"
        base["reason"] = (f"{len(islands)} stray component(s), each < {ISLAND_MAX_VOL_FRAC*100:.0f}% "
                           f"of total volume and > {ISLAND_MIN_DIST_MM}mm from the main body -- "
                           "not real anatomy, drop.")
    elif islands and unresolved:
        base["cause"] = "MIXED_ISLAND_AND_ANATOMICAL"
        base["reason"] = (f"{len(islands)} droppable island(s) plus {len(unresolved)} component(s) "
                           "not explained by island or gap rules (see unresolved_components).")
    else:
        base["cause"] = "ANATOMICAL"
        base["reason"] = (f"{len(others)} secondary component(s), none a bridgeable slice-gap "
                           "(either not Z-aligned or gap exceeds 10mm) nor a droppable stray island "
                           "-- treated as genuine anatomical separation (e.g. a multi-bellied "
                           "muscle) unless flagged otherwise; see unresolved_components for detail.")
    return base


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(REPO_ROOT / "data" / "derived" / "Q152_continuity_repair.json"))
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    audit = json.loads(AUDIT_JSON.read_text())
    q115 = json.loads(Q115_JSON.read_text())
    q115_by_key = {(r["body"], r["id"], r["side"]): r for r in q115["results"].values()}

    targets = []
    for body in ("male", "female"):
        for key, rec in audit["bodies"][body]["structures"].items():
            if rec["cat"] != "muscle" or rec["main_frac"] >= 0.99:
                continue
            if args.only and rec["id"] not in args.only:
                continue
            targets.append((body, key, rec))

    def sort_key(t):
        body, _key, rec = t
        subj = (rec.get("subjects") or [""])[0]
        side_norm = None if rec["side"] in (None, "none") else rec["side"]
        try:
            s = triage.resolve_source(subj, rec["id"], side_norm)
            return s.get("path", "") if s["kind"] == "volume" else "zzz"
        except Exception:
            return "zzz"
    targets.sort(key=sort_key)

    print(f"{len(targets)} fragmented/severe muscle (id,side,body) groups to diagnose")
    results = {}
    counts = {}
    for i, (body, key, rec) in enumerate(targets, 1):
        atlas_id = rec["id"]
        print(f"[{i}/{len(targets)}] {body} {key} (shipped {rec['main_frac']:.3f}) ...", flush=True)
        if atlas_id in ALREADY_RESOLVED:
            cause, reason = ALREADY_RESOLVED[atlas_id]
            r = {"cause": cause, "reason": reason, "shipped_main_frac": rec["main_frac"],
                 "shipped_status": rec["status"], "source": "Q113/Q114 (reused verbatim)"}
        else:
            existing = q115_by_key.get((body, atlas_id, rec["side"]))
            try:
                r = diagnose_one(body, rec, existing)
            except Exception as exc:
                r = {"cause": "UNRESOLVED", "reason": f"diagnosis error: {exc}"}
        r["body"], r["id"], r["side"], r["name"] = body, atlas_id, rec["side"], rec.get("name")
        results[f"{body}|{key}"] = r
        counts[r["cause"]] = counts.get(r["cause"], 0) + 1
        print(f"    -> {r['cause']}")
        Path(args.out).write_text(json.dumps({"results": results, "summary": counts}, indent=2, default=str))

    print("\nSUMMARY:", counts)
    Path(args.out).write_text(json.dumps({
        "source": "scripts/repair_continuity_q152.py",
        "max_gap_mm": MAX_GAP_MM, "island_max_vol_frac": ISLAND_MAX_VOL_FRAC,
        "island_min_dist_mm": ISLAND_MIN_DIST_MM,
        "n_targets": len(targets), "summary": counts, "results": results,
    }, indent=2, default=str))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
