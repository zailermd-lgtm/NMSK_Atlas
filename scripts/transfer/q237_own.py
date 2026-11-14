#!/usr/bin/env python3
"""Q237 (own pages): the missing side of a paired structure as the MIRROR of the opposite side (this body's own measured / rule-based data), fitted to this side's bones and guarded by signed distances
(scripts/anatomy/q237/{fill,run_fill}.py). Source bundle -> new bundle; every entry that is not listed is byte for byte the source's (ship diff, 0 unlisted). Subject (= Source class) `mirror_q237`.
    python3 scripts/transfer/q237_own.py own_m|own_f [--src build/viewer_m_hr_q233] [--out build/viewer_m_hr_q237]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q237"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q233_own_f import keyed  # noqa: E402
import run_fill as RF  # noqa: E402

SUBJECT = RF.SUBJECT
CFG = {"own_m": dict(src="build/viewer_m_hr_q233", out="build/viewer_m_hr_q237", diff="Q237_vertex_diff_m.json"),
       "own_f": dict(src="build/viewer_f_hr_q235", out="build/viewer_f_hr_q237", diff="Q237_vertex_diff_f.json")}
ATTR = ("Q237 mirror fill (this atlas): the missing side of a paired structure is the mirror image of this body's own opposite-side structure about the model's midsagittal plane, fitted to this side's bones; "
        "no external data; badge on each card gives the source, the fit error and the guard numbers.")
DROP = ("origin_point_mm", "insertion_point_mm", "anchors")


def main(key, src=None, out=None):
    cfg = CFG[key]; src = src or str(REPO / cfg["src"]); out = out or str(REPO / cfg["out"])
    add, rep = RF.run(key)
    B, A0 = Bundle(src), Bundle(src)
    added = []
    for a in add:
        sid = a["new_id"]; r = a["report"]
        e0 = B.get(a["src_ids"][0])["e"]
        rec = {k: v for k, v in dict(e0["rec"]).items() if k not in DROP}
        rec.update(name=r["name"], source="Mirror image of this body's own opposite-side structure (Q237), fitted to this side's bones; not measured on this side", procedural_badge=r["badge"])
        B.add(sid, e0["cat"], "left" if a["tgt_side"] == "l" else "right", SUBJECT, rec, a["V"], a["F"])
        added.append(sid)
    B.write(out, new_subject_attribution={SUBJECT: ATTR}, copy_clinical=True)
    N = Bundle(out)
    Ak, Ao = keyed(A0); Nk, No = keyed(N)
    ident, unlisted = 0, []
    for k in Ao:
        if k in Nk and Ak[k]["raw"] == Nk[k]["raw"] and Ak[k]["e"] == Nk[k]["e"]: ident += 1
        else: unlisted.append(k[0])
    new = [k[0] for k in Nk if k not in Ak]
    diff = dict(source=src, new=str(Path(out).resolve().relative_to(REPO)), entries_old=len(A0.items), entries_new=len(N.items), identical=ident, added=new, added_expected=sorted(added), removed=[], card_only=[],
                unlisted_changes=unlisted + sorted(set(new) ^ set(added)), problems=[], triangles_old=A0.j["triangles"], triangles_new=N.j["triangles"])
    (REPO / "data/derived" / cfg["diff"]).write_text(json.dumps(diff, indent=1) + "\n")
    print("ship diff:", {k: (v if not isinstance(v, list) else len(v)) for k, v in diff.items() if k in ("entries_old", "entries_new", "identical", "added", "unlisted_changes")})
    sys.exit(1 if diff["unlisted_changes"] else 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=list(CFG)); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args(); main(a.key, a.src, a.out)
