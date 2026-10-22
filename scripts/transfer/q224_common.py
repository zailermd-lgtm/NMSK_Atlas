"""Q224 shared helpers: the two OWN bundles (his Q217 / her Q216) and their outputs, the page context, report writing, small geometry helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))

BODIES = {
    "m": dict(label="own male", src_bundle=REPO / "build/viewer_m_hr_q217", out_bundle=REPO / "build/viewer_m_hr_q224", src_page=REPO / "build/q221/viewer_m_hr",
              page=REPO / "build/q224/viewer_m_hr", html="atlas_viewer_male.html", viewer="vhm", body="vhm", pagekey="own_m"),
    "f": dict(label="own female", src_bundle=REPO / "build/viewer_f_hr_q216", out_bundle=REPO / "build/viewer_f_hr_q224", src_page=REPO / "build/q222/viewer_f_hr",
              page=REPO / "build/q224/viewer_f_hr", html="atlas_viewer_female.html", viewer="vhf", body="vhf", pagekey="own_f"),
}
SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/q224")
SCRATCH.mkdir(parents=True, exist_ok=True)
DERIVED = REPO / "data/derived"


def jdump(obj, path):
    Path(path).write_text(json.dumps(obj, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)))


def tri_volume_cm3(v, f):
    v = np.asarray(v, float)
    f = np.asarray(f, np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0) / 1000.0


def n_pieces_welded(v, f, tol=0.02):
    from scripts.zanatomy.q198_core import weld, islands
    vw, fw = weld(np.asarray(v, float), np.asarray(f, np.int64), tol)
    isl = islands(vw, fw)
    return len(isl), isl, vw, fw
