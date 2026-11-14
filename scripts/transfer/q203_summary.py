#!/usr/bin/env python3
"""Q203: combine the Q198-metric comparisons of both own models (Q200 pages -> Q203 pages) into data/derived/Q203_before_after.json and print the report numbers
(source-facet counts from the separation audit, triangle totals from the bundles)."""
import json
import subprocess
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
D = REPO / "data/derived"
out = {}
for key in ("own_m", "own_f"):
    tmp = D / f"_cmp_{key}.json"
    subprocess.run([sys.executable, str(REPO / "scripts/transfer/q203_compare.py"), key, "base200", "after", "--json", str(tmp)], check=True, stdout=subprocess.DEVNULL)
    c = json.loads(tmp.read_text()); tmp.unlink()
    out[key] = {}
    for k, v in c.items():
        out[key][k] = v
(D / "Q203_before_after.json").write_text(json.dumps(out, indent=1))
gc = json.loads((D / "Q203_global_caps.json").read_text())
sep = json.loads((D / "Q203_model_separation_audit.json").read_text())
for key, body, sk in (("own_m", "vhm", "own_male"), ("own_f", "vhf", "own_female")):
    bj = json.loads((REPO / f"build/viewer_{'m' if body == 'vhm' else 'f'}_hr_q203/bundle.json").read_text())
    s = sep[sk]
    print(key, "entries", s["entries"], "triangles", bj["triangles"], "classes(ids/entries)", {c: (v["ids"], v["entries"]) for c, v in s["by_class"].items()})
    g = gc[body]
    print("   whole-body flat caps", g["before_q200"]["caps"], "->", g["after_q203"]["caps"], "area", g["before_q200"]["area_mm2"], "->", g["after_q203"]["area_mm2"],
          "| muscle cap area", g["before_q200"]["by_cat"]["muscle"]["area_mm2"], "->", g["after_q203"]["by_cat"]["muscle"]["area_mm2"])
    for side in "lr":
        k = f"shoulder_{side}"
        print("  ", k, {m: (out[key][k]["before"][m], out[key][k]["after"][m]) for m in ("flat_caps", "flat_cap_area_mm2", "bone_flat_caps", "muscle_ends_gt5mm_from_bone", "islands_gt5mm")})
