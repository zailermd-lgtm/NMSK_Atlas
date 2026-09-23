"""Q148 regression: intervertebral discs must sit BETWEEN their two adjacent
vertebrae, not laid out front-to-back at one fixed height per region (the
owner-reported bug -- see PROJECT_STATE.md's Q148 entry and
scripts/generate_intervertebral_discs.py's own docstring for the root cause:
the cylinder's axis and the per-region center were both built assuming Z was
the craniocaudal axis, when this atlas's frame is +Y superior, +Z anterior).

Reads the actual shipped build/vh/<subject> geometry (source of truth for the
viewer bundles) rather than re-deriving anything, and skips cleanly when that
gitignored build output isn't present (matches this repo's existing pattern
for build-dependent tests, e.g. test_zanatomy_corrections.py deliberately not
touching build/zanatomy/).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.generate_intervertebral_discs import (  # noqa: E402
    ALL_LEVELS,
    CERVICAL_LEVELS,
    LUMBAR_LEVELS,
    THORACIC_LEVELS,
    compute_region_vertebra_pieces,
)

BUILD_DIR = REPO_ROOT / "build" / "vh"

# Bottom (most inferior lumbar level) to top (most superior cervical level):
# the reverse of ALL_LEVELS, which is ordered top-to-bottom. Y is this
# atlas's craniocaudal axis (+Y superior), so centroids must strictly
# increase in Y along this order.
FULL_COLUMN_BOTTOM_TO_TOP = list(reversed(ALL_LEVELS))

REGIONS = [
    ("cervical_vertebrae", CERVICAL_LEVELS),
    ("thoracic_vertebrae", THORACIC_LEVELS),
    ("lumbar_vertebrae", LUMBAR_LEVELS),
]


def _load_subject(subject: str):
    manifest_path = BUILD_DIR / subject / "manifest.json"
    if not manifest_path.exists():
        pytest.skip(f"build/vh/{subject} not present (gitignored build output)")
    manifest = json.loads(manifest_path.read_text())
    verts = np.fromfile(BUILD_DIR / subject / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(BUILD_DIR / subject / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return manifest, verts, faces


def _disc_centroid(manifest, atlas_id):
    for s in manifest["structures"]:
        if s["atlas_id"] == atlas_id:
            bmin, bmax = np.array(s["bbox_min_mm"]), np.array(s["bbox_max_mm"])
            return (bmin + bmax) / 2.0
    return None


@pytest.mark.parametrize("subject", ["ct_vhm", "ct_vhf"])
def test_disc_centroids_strictly_increase_in_y_bottom_to_top(subject):
    manifest, _verts, _faces = _load_subject(subject)
    ys = []
    for level in FULL_COLUMN_BOTTOM_TO_TOP:
        c = _disc_centroid(manifest, level.atlas_id)
        assert c is not None, f"{subject}: missing disc structure {level.atlas_id}"
        ys.append(c[1])
    ys = np.array(ys)
    diffs = np.diff(ys)
    assert np.all(diffs > 0), (
        f"{subject}: disc centroid Y is not strictly increasing bottom-to-top "
        f"(L4-L5 -> C1-C2); diffs={diffs.tolist()}"
    )


@pytest.mark.parametrize("subject", ["ct_vhm", "ct_vhf"])
def test_each_disc_lies_between_its_two_adjacent_vertebrae(subject):
    manifest, verts, faces = _load_subject(subject)
    problems = []
    for atlas_id, levels in REGIONS:
        pieces = compute_region_vertebra_pieces(manifest, verts, faces, atlas_id)
        piece_mean_y = [p[:, 1].mean() for p in pieces]
        assert len(levels) == len(pieces) - 1, (
            f"{subject}/{atlas_id}: {len(pieces)} vertebra pieces, "
            f"expected {len(levels) + 1} for {len(levels)} disc levels"
        )
        for i, level in enumerate(levels):
            c = _disc_centroid(manifest, level.atlas_id)
            assert c is not None, f"{subject}: missing disc structure {level.atlas_id}"
            y_upper, y_lower = piece_mean_y[i], piece_mean_y[i + 1]  # upper is more superior
            if not (y_lower <= c[1] <= y_upper):
                problems.append(
                    f"{subject}/{level.atlas_id}: disc y={c[1]:.1f} not between "
                    f"adjacent vertebrae ({y_lower:.1f}, {y_upper:.1f})"
                )
    assert not problems, "\n".join(problems)
