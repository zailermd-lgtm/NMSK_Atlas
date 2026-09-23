"""Q144: apply declarative, cited corrections to specific Z-Anatomy nerve pathways,
at bundle-build time only -- the raw extraction (build/zanatomy/) is never touched,
so every correction stays traceable to a small JSON file under
data/corrections/zanatomy/ plus this one small applier, per the owner's own
"CC BY-SA anatomy layer stays pristine, our corrections are separate and
declarative" rule (PROJECT_STATE.md licensing rule, updated Q141).

Each correction file names the atlas_id(s) (this project's OWN ids, i.e. AFTER
zan_source.py's own side-split -- see that module's Q144 addition) it applies to,
the landmark(s) measured live on this same Z-Anatomy geometry (never assumed --
see data/derived/Q144_radial_nerve_audit.json for the full measurement method),
the literature target for whichever landmark(s) audited outside the cited range,
and the citation. See data/corrections/zanatomy/radial_n.json for the first one.

METHOD: a bounded, smooth (C1, cubic-smoothstep) 1-D warp of mesh vertex Y (this
project's atlas +Y = superior) around a short list of named anchors, each an
(offset_mm_from_lateral_epicondyle, shift_mm) pair. A landmark that already
audited WITHIN its cited range is anchored at shift=0 (so the correction never
moves a part of the nerve that was already right); only the landmark(s) that
audited outside range get a non-zero shift, moving that point to its cited
target. Between anchors the shift is smoothstep-interpolated (C1 continuous, no
kinks, so the corrected mesh stays a smooth deformation of the original with no
tears); outside the outermost anchors it is clamped to that anchor's own shift
(0 at both ends here) -- so only the mesh between the named anchors is ever
touched. No topology change: same vertex/face count and connectivity, only the
Y-coordinate moves.

The lateral epicondyle itself is FIT LIVE from this build's own Humerus.r/.l
mesh (never a fixed number baked into the correction file), so this still
applies correctly if the base Z-Anatomy extraction is ever regenerated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

DEFAULT_CORRECTIONS_DIR = REPO / "data" / "corrections" / "zanatomy"


def lateral_epicondyle_y(humerus_v: np.ndarray, side: str) -> float:
    """This model's own lateral epicondyle Y, fit the same way this project's
    other Z-Anatomy landmarks are (build_zan_reference.py's own femoral-head-cap
    convention): the distal-most 15mm-by-atlas-Y slab of the humerus, most-lateral
    vertex by signed X (lateral is +X on the right arm, -X on the left -- see
    zan_source.py's own axis derivation and its exact mirror check)."""
    y = humerus_v[:, 1]
    slab = humerus_v[y < y.min() + 15.0]
    idx = int(np.argmax(slab[:, 0])) if side == "r" else int(np.argmin(slab[:, 0]))
    return float(slab[idx, 1])


def _smoothstep(t: np.ndarray) -> np.ndarray:
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def bump_warp_y(y: np.ndarray, anchors: list[tuple[float, float]]) -> np.ndarray:
    """`anchors`: [(y_value, shift_mm), ...], any order. Returns the shift to ADD
    to each input y (same shape), smoothstep-interpolated between consecutive
    anchors (sorted ascending by y_value) and clamped to the nearest anchor's own
    shift outside the anchored range."""
    anchors = sorted(anchors, key=lambda a: a[0])
    ys = np.array([a[0] for a in anchors])
    shifts = np.array([a[1] for a in anchors])
    out = np.full(y.shape, shifts[0], dtype=np.float64)
    out[y >= ys[-1]] = shifts[-1]
    for i in range(len(ys) - 1):
        lo, hi = ys[i], ys[i + 1]
        # inclusive both ends: a y sitting exactly on a shared boundary between
        # two segments is set by whichever segment runs last, but smoothstep is
        # continuous at t=0/t=1 so both segments agree there anyway.
        m = (y >= lo) & (y <= hi)
        if not m.any():
            continue
        t = (y[m] - lo) / (hi - lo)
        out[m] = shifts[i] + (shifts[i + 1] - shifts[i]) * _smoothstep(t)
    return out


def load_corrections(directory: Path = DEFAULT_CORRECTIONS_DIR) -> dict:
    """atlas_id -> its correction file's own dict, one entry per id named in that
    file's `correction.applies_to_ids`. Safe to call with an empty/missing
    directory (returns {}) -- corrections are opt-in, never required."""
    out = {}
    directory = Path(directory)
    if not directory.exists():
        return out
    for path in sorted(directory.glob("*.json")):
        rec = json.loads(path.read_text())
        for aid in rec["correction"]["applies_to_ids"]:
            out[aid] = rec
    return out


def _push_off_bones(points: np.ndarray, zan_dir: Path, side: str, bone_names: list[str],
                     clearance_mm: float = 1.0):
    """A pure Y-shift can move a vertex that used to clear a bone's surface into
    a DIFFERENT part of that bone's own cross-section (the bone's outline is not
    constant along Y), which the naive warp alone cannot see. Checked for
    empirically (Q144: the radial_n.json correction, unguarded, put ~11% of the
    corrected posterior interosseous nerve's own vertices inside the Z-Anatomy
    Radius mesh -- the PIN wraps tightly around the radial neck in real anatomy,
    so this is exactly where a Y-only warp is most likely to clip it).

    For every point trimesh finds INSIDE one of `bone_names`' own (side-matched)
    Skeletal mesh, projects it to that mesh's nearest surface point, then a
    further `clearance_mm` beyond it along the RAY FROM the original (interior)
    point THROUGH that surface point -- not the surface's own face normal:
    checked empirically (Q144) that this mesh's face normals point inward, so
    "nearest surface + normal*clearance" moved the point deeper in, not out;
    the point-to-surface ray direction has no such orientation dependency (it
    only assumes the interior point's straight line to its nearest surface
    point actually crosses out of the solid once continued, true for a locally
    convex bone shaft). Never touches a point already outside every named bone.
    Import is local (trimesh is only needed here, not by every
    apply_correction() caller)."""
    import trimesh  # noqa: E402
    from scripts.zanatomy.zan_source import safe_filename, to_atlas_frame  # noqa: E402

    out = points.copy()
    for bone in bone_names:
        path = Path(zan_dir) / "Skeletal" / f"{safe_filename(f'{bone}.{side}')}.npz"
        if not path.exists():
            continue
        d = np.load(path)
        mesh = trimesh.Trimesh(vertices=to_atlas_frame(d["vertices_mm"]),
                                faces=d["faces"].astype(np.int64), process=False)
        inside = mesh.contains(out)
        if not inside.any():
            continue
        interior_pts = out[inside]
        closest, _, _ = mesh.nearest.on_surface(interior_pts)
        direction = closest - interior_pts
        length = np.linalg.norm(direction, axis=1, keepdims=True)
        length[length == 0] = 1.0
        pushed = closest + (direction / length) * clearance_mm
        # belt-and-braces: fall back to a slightly larger push for the rare
        # point still inside afterwards (e.g. clearance_mm undershoots at a
        # sharp concavity) rather than silently leaving it penetrating.
        still_in = mesh.contains(pushed)
        if still_in.any():
            pushed[still_in] = closest[still_in] + (direction[still_in] / length[still_in]) * (clearance_mm * 4)
        out[inside] = pushed
    return out


def apply_correction(aid: str, v: np.ndarray, zan_dir: Path, corrections: dict):
    """`v`: this id's OWN mesh vertices, atlas frame, mm, NOT yet origin-shifted
    (must be the same frame `lateral_epicondyle_y` measures the humerus in --
    i.e. called on `zan_source.to_atlas_frame()` output before
    build_zan_reference.py's own hip-origin subtraction).

    Returns (v, None) unchanged if `aid` carries no correction. Otherwise returns
    (warped v (a copy; the input is never mutated), the correction's
    `procedural_badge_note` string).
    """
    rec = corrections.get(aid)
    if rec is None:
        return v, None
    from scripts.zanatomy.zan_source import safe_filename, to_atlas_frame  # noqa: E402

    side = "r" if aid.endswith("_r") else "l"
    humerus_path = Path(zan_dir) / "Skeletal" / f"{safe_filename(f'Humerus.{side}')}.npz"
    humerus_v = to_atlas_frame(np.load(humerus_path)["vertices_mm"])
    le_y = lateral_epicondyle_y(humerus_v, side)
    anchors_y = [(le_y + off, shift) for off, shift in rec["correction"]["anchors_offset_from_LE_mm"]]
    shift = bump_warp_y(v[:, 1], anchors_y)
    out = v.copy()
    out[:, 1] = v[:, 1] + shift
    avoid = rec["correction"].get("avoid_penetration_of")
    if avoid:
        out = _push_off_bones(out, zan_dir, side, avoid)
    return out, rec["correction"].get("procedural_badge_note")
