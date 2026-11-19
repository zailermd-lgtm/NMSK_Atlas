"""print the before -> after table of a q206_carry dump"""
import json, sys
import numpy as np
z = np.load(sys.argv[1], allow_pickle=False)
rep = json.loads(str(z["report"]))
for sd, r in rep.items():
    rows = []
    for i, x in r["structures"].items():
        b, a = x["before"], x.get("after", x["before"])
        rows.append((i, x["cat"], x["ladder"][:22], x.get("mean_move_mm"), x.get("max_move_mm"), b["outside_skin_pct"], a["outside_skin_pct"], b["inside_bone_pct"], a["inside_bone_pct"], b["stretched_pct"], a["stretched_pct"], b["folded_pct"], a["folded_pct"]))
    print(sd, "zone", r["n_zone"], "moved", len(rows), r["continuity"]["summary"])
    print("id cat ladder mean max | out% b>a | in% b>a | stretch b>a | fold b>a")
    for x in sorted(rows, key=lambda t: -(t[5] + t[7])):
        print(f"{x[0][:52]:52s} {x[1][:6]:6s} {x[2]:22s} {x[3]:5.1f} {x[4]:5.1f} | {x[5]:5.1f}>{x[6]:5.1f} | {x[7]:5.1f}>{x[8]:5.1f} | {x[9]:4.0f}>{x[10]:4.0f} | {x[11]:4.1f}>{x[12]:4.1f}")
