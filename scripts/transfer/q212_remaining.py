#!/usr/bin/env python3
"""Q212: why each flat muscle / tendon cap still left on the two own pages (census of q212_global_caps.py, after) was not completed: category table with counts and areas.
    python3 scripts/transfer/q212_remaining.py -> data/derived/Q212_remaining_caps.json"""
import json, re
from collections import defaultdict
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
D = REPO / "data/derived"
caps = json.loads((D / "Q212_global_caps.json").read_text())
out = {}
for body in ("vhm", "vhf"):
    r12 = [x for x in json.loads((D / f"Q212_rows_{body}.json").read_text()) if x.get("stage") == "muscle"]
    r03 = [x for x in json.loads((D / f"Q203_rows_{body}.json").read_text()) if x.get("stage") == "muscle"]
    def find(i, ax, pos):
        for rows in (r12, r03):
            c = [x for x in rows if x["id"] == i and x["axis"] == ax and abs(x["pos"] - pos) < 1.6]
            if c:
                return c[0]
        return None
    cat = defaultdict(lambda: dict(caps=0, area_mm2=0, examples=[]))
    for c in caps[body]["after_q212"]["rows"]:
        if c["cat"] not in ("muscle", "tendon"):
            continue
        x = find(c["id"], c["axis"], c["pos"])
        st = (x or {}).get("status", "")
        if x is None:
            k = "flat face of a Z continuation piece itself (its planar closure or the Z-Anatomy mesh own flat end), not a measured cut"
        elif st.startswith("continued"):
            k = "continued in Q203 / Q212 in local mode: the Z section covers part of the face, the rest is where the measured mass is wider than the Z structure"
        elif st.startswith("skipped: cap"):
            k = "facet < 100 mm2"
        elif "body surface" in st:
            k = "cap lies on the body surface (skin within 3 mm): table / skin contact, not a data-block seam"
        elif "already continued" in st or "covered" in st:
            k = "already continued (Q200 / Q203 continuation covers the face)"
        elif "no Z-Anatomy counterpart" in st:
            k = "no Z-Anatomy counterpart mesh (not in Z-Anatomy under any name)"
        elif "does not land" in st:
            k = "Z end does not land on the person's bone"
        elif "balloon" in st:
            k = "Z section many times the measured face"
        else:
            nums = [float(v) for v in re.findall(r"ends (-?[\d.]+) mm beyond", st)]
            sh = re.findall(r"section (\d+) mm off", st)
            if nums and max(nums) <= -6.0:
                k = "measured mass larger: the Z structure ends >= 6 mm BEFORE the cut"
            elif nums and max(nums) < 6.0 and not sh:
                k = "the cut plane coincides with the end of the Z structure (Z ends within -6 .. +6 mm of it; gate 6 mm = the fit error scale)"
            elif sh:
                k = "Z section lies > 30 mm off the cap face (not the same structure position)"
            elif "fit median" in st:
                k = "Z fit > 25 mm (and the two-sided gate fails)"
            else:
                k = "other held: " + st[:60]
        d = cat[k]; d["caps"] += 1; d["area_mm2"] += c["area"]
        if len(d["examples"]) < 6:
            d["examples"].append(f"{c['id']} {c['axis']}={c['pos']} ({c['area']:.0f} mm2)")
    out[body] = {k: dict(caps=v["caps"], area_mm2=round(v["area_mm2"]), examples=v["examples"]) for k, v in sorted(cat.items(), key=lambda kv: -kv[1]["area_mm2"])}
    print(body)
    for k, v in out[body].items():
        print(f"  {v['caps']:3d} caps {v['area_mm2']:6d} mm2  {k}")
(D / "Q212_remaining_caps.json").write_text(json.dumps(out, indent=1))
