"""Q195: the Z-Anatomy whole body fitted onto the Visible Human MALE's OWN skeleton (his CT / DU release bones).

Thin parameterisation of the Q168 module (scripts/transfer/zan_to_vhf_whole_body.py, `--target vhm`): same per-bone similarity
fits (best of Q147's per-bone fit and a centroid start, trimmed symmetric ICP, per-piece / chain refinement), same soft tissue rule
(tapered inverse-square blend of the nearby bones' similarities), with the male differences:
  * his skeleton comes from build/viewer_m_hr_q193/bundle.json (the published own male, incl. the Q193 organs);
  * his metacarpals are ONE composite mesh per hand (`metacarpals_r/l`), so the five Z-Anatomy metacarpals are one unit
    refined piece by piece (the female bundle has five separate ones);
  * male-only Z-Anatomy structures are kept (his body has them);
  * his radius/ulna have CT: no forearm proxy;
  * the report goes to data/derived/Q195_zan_to_vhm.json (Q168_zan_to_vhm.json, used by the Q62 step 7b transfers, is untouched).

    python3 scripts/transfer/zan_to_vhm_whole_body.py [--items-cache F.pkl] [--report FILE]
    from scripts.transfer.zan_to_vhm_whole_body import apply_male_units, REPORT, BUNDLE
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.transfer import zan_to_vhf_whole_body as Q  # noqa: E402

BUNDLE = REPO / "build" / "viewer_m_hr_q193" / "bundle.json"
REPORT = REPO / "data" / "derived" / "Q195_zan_to_vhm.json"


def apply_male_units() -> None:
    """In-place (same dict objects, so fit_units' default argument sees it): one composite metacarpal unit per hand."""
    for s in "rl":
        z = [f"zan_{o}_metacarpal_bone_{s}" for o in Q._ORD[:5]]
        for k in range(1, 6):
            Q.UNITS.pop(f"metacarpal_{k}_{s}", None)
        Q.UNITS[f"metacarpals_{s}"] = z
        Q.REFINE_PIECES.add(f"metacarpals_{s}")
    Q.REGION_OF_UNIT_BASE["forearm_hand"].add("metacarpals")


def main(argv=None) -> int:
    apply_male_units()
    Q.TARGETS["vhm"] = (BUNDLE, REPORT)
    rest = list(sys.argv[1:] if argv is None else argv)
    args = ["--target", "vhm"] + rest
    rc = Q.main(args)
    rep_path = Path(rest[rest.index("--report") + 1]) if "--report" in rest else REPORT
    rep = json.loads(rep_path.read_text())
    rep["body_scale"] = round(Q.body_scale(Q.fits_from_json(rep["bone_fits"])), 4)   # median scale of the reference bones (his size vs Z-Anatomy's)
    rep["metacarpals"] = "one composite unit per hand (his metacarpals are one mesh)"
    rep_path.write_text(json.dumps(rep, indent=1))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
