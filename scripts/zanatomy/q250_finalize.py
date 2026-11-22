#!/usr/bin/env python3
"""Q250 finalize a pre-page: (base_f) correct the card sentences of the earlier patch scripts that were true for the male-derived pelvis but are stale on the deformed pelvis, carry the structures the Q248
agent added (optional), and write the ship diff against the Q244 page (data/derived/Q250_vertex_diff_<page>.json: every changed / added / removed id classified; `unlisted` must be empty).
    python3 scripts/zanatomy/q250_finalize.py base_f|comb_f [--q248]"""
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402
from scripts.zanatomy import q205_shipdiff as SD  # noqa: E402

CFG = {"base_f": dict(dir="viewer_base_female", stem="atlas_viewer_base_female"), "comb_f": dict(dir="viewer_zan_female", stem="atlas_viewer_zan_female")}
SUBS = [
    (r"the residual mostly measures that the Z-Anatomy pelvis is MALE-derived and the donor's is female, the same transform as the uterus of this page",
     "the residual is small because since Q250 this page's pelvis is the Z-Anatomy pelvis deformed onto a female pelvis, the same transform as the uterus of this page"),
    (r"the residual mostly measures that the Z-Anatomy pelvis is MALE-derived and the donor's is female, so the organs' position relative to these bones is approximate",
     "the residual is small because since Q250 this page's pelvis is the Z-Anatomy pelvis deformed onto a female pelvis; the position relative to these bones is still approximate"),
    (r"The Z-Anatomy structures around it are the male-derived body fitted to the page's bones, so contact with them is approximate",
     "The Z-Anatomy structures around it are the male-derived Z-Anatomy body deformed onto this page's female skeleton (Q250), so contact with them is approximate"),
]
Q233_NOTE = re.compile(r"\s*(\|\| )?Q233 sex audit: this Z-Anatomy pelvic bone derives from the single male body[^|]*?\(subpubic angle, sciatic notch, ischiopubic index\)\.")


def run(which, with_q248=False):
    c = CFG[which]; stem = c["stem"]; pre = REPO / "build/q250_pre" / c["dir"]; q244 = REPO / "build/q244" / c["dir"]
    carried = []
    if with_q248 and (REPO / "build/q248" / c["dir"]).exists():
        from scripts.zanatomy import q250_carry_q248 as CQ
        carried = sorted(CQ.run(which, f"build/q248/{c['dir']}", f"build/q244/{c['dir']}", f"build/q250_pre/{c['dir']}", str(REPO / "build/q250_work" / ("warp_field_her.npz" if which == "base_f" else "warp_field_comb_f.npz"))))
    man, blob = P5.load_page(pre, stem)
    meta, nfix = {}, 0
    SUBS_ = SUBS if which == "base_f" else []
    for m in man["meshes"]:
        rec = m.get("rec")
        if not isinstance(rec, dict) or not rec.get("procedural_badge"):
            continue
        t = rec["procedural_badge"]; t2 = Q233_NOTE.sub("", t)
        for a, b in SUBS_:
            t2 = re.sub(a, b, t2)
        if t2 != t:
            r2 = dict(rec); r2["procedural_badge"] = t2.strip(); meta[m["id"]] = (m["name"], r2); nfix += 1
    if meta:
        P5.save_page(pre, stem, man, blob, meta=meta)
    d = SD.diff(q244, pre, stem, [])
    q = json.loads((REPO / ("data/derived/Q250_base_f_warp_report_her.json" if which == "base_f" else "data/derived/Q250_comb_f_warp_report.json")).read_text())
    if which == "base_f":
        hra = set(q["dropped_hra_structures"]); zids = set(q["structures"])
        for n in ("Q233", "Q234", "Q235", "Q243"):                              # ids that the re-run HRA / CVH patch scripts shipped on this page (their own ship diffs, 0 unlisted each)
            f = REPO / f"data/derived/Q250_chain_{n}_vertex_diff_base_f.json"
            if f.exists():
                hra |= set(json.loads(f.read_text())["added"])
        unlisted = sorted(set(d["added"]) - set(carried) - hra) + sorted(set(d["removed"]) - hra) + sorted(set(d["geometry_changed"]) - zids - hra)
        listed = dict(z_structures_deformed=len(zids), hra_structures_reregistered=sorted(hra), q248_carried=carried)
    else:
        moved = set(q["moved"])
        unlisted = sorted(set(d["added"]) - set(carried)) + sorted(set(d["removed"])) + sorted(set(d["geometry_changed"]) - moved) + sorted(set(d["card_only"]) - moved)
        listed = dict(moved=sorted(moved), exempt_not_moved=len(q["exempt"]), q248_carried=carried)
    out = dict(page=which, source=f"build/q244/{c['dir']}", new=f"build/q250_pre/{c['dir']}", added=d["added"], removed=d["removed"], geometry_changed_count=len(d["geometry_changed"]),
               geometry_changed_max_vertex_change_mm_p100=max([v["max_vertex_change_mm"] or 0 for v in d["geometry_changed"].values()] or [0]), card_only=sorted(d["card_only"]), unchanged=d["unchanged"], listed=listed,
               stale_card_sentences_corrected=nfix, unlisted=unlisted)
    (REPO / f"data/derived/Q250_vertex_diff_{which}.json").write_text(json.dumps(out, indent=1) + "\n")
    print(which, "ship diff: added", len(out["added"]), "removed", len(out["removed"]), "geometry_changed", out["geometry_changed_count"], "card_only", len(out["card_only"]), "unchanged", out["unchanged"], "unlisted", out["unlisted"], "cards corrected", nfix)
    return 1 if unlisted else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("which", choices=list(CFG)); ap.add_argument("--q248", action="store_true"); a = ap.parse_args()
    sys.exit(run(a.which, a.q248))
