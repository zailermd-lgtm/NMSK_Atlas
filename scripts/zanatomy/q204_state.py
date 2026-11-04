#!/usr/bin/env python3
"""Q204: print the PROJECT_STATE.md section from data/derived/Q204_anatomy_audit.json (the numbers there are the JSON's)."""
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
A = json.loads((REPO / "data/derived/Q204_anatomy_audit.json").read_text())
P = A["pages"]
SHORT = {"own_m": "Own male", "own_f": "Own female", "z_male": "Z male base", "z_base_f": "Z generic (female variant)", "z_male_fit": "Z fitted to his", "z_female_fit": "Z fitted to hers"}
REG = A["meta"]["regions"]
mmm = lambda x: "/".join(str(v) for v in x)
o = []
o.append("| page (published dir) | Q198 verdict -> now | Q198 junction audit major/mod/minor: Q198 -> now | elbow L, R: Q198 -> now | whole-body structures major/mod/minor (Q204 regional) | worst regions (major+moderate structures) |")
o.append("|---|---|---|---|---|---|")
for k, p in P.items():
    q = p["q198_vs_now"]
    reg = sorted(((v["structures_major_moderate_minor"][0] + v["structures_major_moderate_minor"][1], r) for r, v in p["regions"].items()), reverse=True)[:3]
    sc = p["structure_severity_counts"]
    el = q["elbow_L_R"]
    o.append(f"| {SHORT[k]} (`{p['page']}`) | {q['verdict'][0]} -> {q['verdict'][1]} | {mmm(q['severity_major_moderate_minor'][0])} -> {mmm(q['severity_major_moderate_minor'][1])} | {'/'.join(el[0])} -> {'/'.join(el[1])} | {sc['major']}/{sc['moderate']}/{sc['minor']} (of {p['regional_rows']}) | "
             + ", ".join(f"{r} {n}" for n, r in reg) + " |")
o.append("")
o.append("Structures with a major or moderate finding, per region (Q204 regional pass; major+moderate / structures in region):")
o.append("")
o.append("| region | " + " | ".join(SHORT[k] for k in P) + " |")
o.append("|---|" + "---|" * len(P))
for r in REG:
    row = []
    for k, p in P.items():
        v = p["regions"][r]
        row.append(f"{v['structures_major_moderate_minor'][0] + v['structures_major_moderate_minor'][1]}/{v['n_structures']}")
    o.append(f"| {r} | " + " | ".join(row) + " |")
print("\n".join(o))
print()
for k, p in P.items():
    print(f"- **{SHORT[k]} worst 10**: " + "; ".join(f"{w['id']} ({w['region']}, {w['findings'][0][4:80]}{', also in unfitted base' if w['in_unfitted_base'] else ''})" for w in p["worst10"][:5]) + " ... (all 10 in the JSON)")
