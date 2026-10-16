#!/usr/bin/env python3
"""Q237 (Z pages): missing / listed-defect side as the MIRROR of the opposite side, fitted to this side's bones, guarded by signed distances (scripts/anatomy/q237/{fill,run_fill}.py), as an in-process patch of
the page (untouched structures byte for byte, ship diff 0 unlisted). A defective Z-fitted structure is REPLACED only when the mirror passes every guard (the card says what it replaced); a missing side is ADDED.
    python3 scripts/zanatomy/q237_z.py comb_m|comb_f|base_m|base_f [--src PAGE_DIR] [--out PRE_PAGE_DIR]
The pre-page is rendered from the template named by $Q233_ZAN_TEMPLATE (a committed revision) so that scripts/verify_regen_q218.py can find it in git."""
from __future__ import annotations
import argparse, json, os, shutil, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q237"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402
import core as C  # noqa: E402
import run_fill as RF  # noqa: E402

ATTR = ("Q237 mirror fill (this atlas): a missing or defective side of a paired Z-Anatomy structure is the mirror image of the opposite side about the model's midsagittal plane, fitted to this side's bones; "
        "badge on each card gives the source, the fit error and the guard numbers.")


def run(key, src=None, out=None):
    d, html, kind, label, dname = C.PAGES[key]
    stem = html[:-5]
    src = Path(src or REPO / d); out = Path(out or REPO / "build/q237_pre" / dname)
    if os.environ.get("Q233_ZAN_TEMPLATE"):
        P5.B.TEMPLATE_PATH = Path(os.environ["Q233_ZAN_TEMPLATE"])
    os.environ["Q237_SRC_" + key] = str(src)
    add, rep = RF.run(key)
    man, blob = P5.load_page(src, stem)
    byid = {m["id"]: m for m in man["meshes"]}
    new, replace, expected_add, expected_geo, skipped = [], {}, [], [], []
    for a in add:
        r = a["report"]
        src0 = byid[a["src_ids"][0]]
        rec = {k: v for k, v in dict(src0.get("rec") or {}).items() if k not in ("origin_point_mm", "insertion_point_mm", "anchors", "part_of_id")}
        rec.update(source="Mirror image of the opposite side's Z-Anatomy structure (Q237), fitted to this side's bones; not measured on this side", procedural_badge=r["badge"])
        if r["kind"] == "A":
            new.append(({"name": r["name"], "id": a["new_id"], "side": a["tgt_side"], "sys": a["sys"], "rec": rec}, a["V"], a["F"]))
            expected_add.append(a["new_id"])
        else:
            if len(a["replace_ids"]) != 1:
                r["decision"] = "held"; r["reasons"] = ["the defective side has several pieces: not replaced"]; skipped.append(r["canon"]); continue
            rid = a["replace_ids"][0]
            old = byid[rid].get("rec") or {}
            rec2 = dict(old); rec2.update(source=rec["source"], procedural_badge=r["badge"] + f" Replaces the Z-fitted `{rid}` of this page, which had a listed defect (Q198 / Q204 audit: {r['why']}).")
            replace[rid] = (a["V"], a["F"], rec2); expected_geo.append(rid); r["new_id"] = rid
    man2 = dict(man); man2["attribution"] = (man.get("attribution") or "").rstrip() + " " + ATTR
    P5.save_page(out, stem, man2, blob, replace=replace, add=new)
    for f in src.glob("clinical_*"):
        shutil.copy2(f, out / f.name)
    r_ = SD.diff(src, out, stem, expected_geo)
    rel = lambda p: str(Path(p).resolve().relative_to(REPO)) if str(Path(p).resolve()).startswith(str(REPO)) else str(p)  # noqa: E731
    diff = dict(source=rel(src), new=rel(out), added=r_["added"], added_expected=sorted(expected_add), removed=r_["removed"], geometry_changed=sorted(r_["geometry_changed"]), geometry_changed_expected=sorted(expected_geo),
                card_only=sorted(r_["card_only"]), unchanged=r_["unchanged"], held=[x["canon"] for x in rep if x["decision"] == "held"] + skipped,
                unlisted=sorted(set(r_["added"]) ^ set(expected_add)) + sorted(set(r_["geometry_changed"]) ^ set(expected_geo)) + sorted(r_["card_only"]) + sorted(r_["removed"]))
    (REPO / f"data/derived/Q237_vertex_diff_{key}.json").write_text(json.dumps(diff, indent=1) + "\n")
    print(key, "ship diff: added", len(diff["added"]), "geometry replaced", len(diff["geometry_changed"]), "card_only", len(diff["card_only"]), "removed", len(diff["removed"]), "unlisted", diff["unlisted"], "unchanged", diff["unchanged"])
    return 1 if diff["unlisted"] else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key", choices=["comb_m", "comb_f", "base_m", "base_f"]); ap.add_argument("--src"); ap.add_argument("--out"); a = ap.parse_args()
    sys.exit(run(a.key, a.src, a.out))
