"""Q205: full-resolution state -> shipped mesh, exactly what build_zan_atlas_viewer.finish() does (quadric decimation at the Hi-res category budgets, outward winding; skin patches are not decimated)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
sys.path.insert(0, str(REPO))
import build_zan_atlas_viewer as B  # noqa: E402


def ship_mesh(v, f, mesh_id, cat):
    v, f = np.asarray(v, float), np.asarray(f, np.int64)
    if cat == "skin":
        dv, df = v, f
    else:
        dv, df = B.decimate(v, f, mesh_id, cat, B.HIRES_CATEGORY_SCALE.get(cat, 1.0), prepped=True)
    return dv, B.outward_if_closed(dv, df)
