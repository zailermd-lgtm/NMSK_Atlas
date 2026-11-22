#!/usr/bin/env python3
"""Q198: print the PROJECT_STATE.md section from data/derived/Q198_anatomy_audit.json (so the numbers there are the JSON's)."""
import json
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
a = json.loads((REPO / "data/derived/Q198_anatomy_audit.json").read_text())
L = {"own_m": "Own male", "own_f": "Own female", "z_male": "Z male base", "z_base_f": "Z generic body (female variant)", "z_male_fit": "Z fitted to his reconstruction", "z_female_fit": "Z fitted to her reconstruction"}
out = []
out.append("| model | continuous and in place? | elbow L | elbow R | major / moderate / minor | top 5 issues (grouped; severity 3 = major) |")
out.append("|---|---|---|---|---|---|")
for k, m in a["models"].items():
    iss = [g for g in m["issues"] if not (g["cause"] == "source_defect" and k in ("z_male_fit", "z_female_fit"))]
    top, seen = [], set()
    for g in iss:
        key = (g["region"], g["check"])
        if key in seen and len(top) < 4:
            continue
        seen.add(key); top.append(g)
        if len(top) == 5:
            break
    t = "<br>".join(f"{i+1}. [{g['severity']}] {g['region']}{'/'+g['side'] if g.get('side') else ''}: {g['headline'][:150].replace('|','/')} -- *{g['cause']}*" for i, g in enumerate(top))
    sc = m["severity_counts"]
    out.append(f"| {L[k]} | {m['verdict_continuous_and_in_place']} | {m['elbow']['l']['verdict']} | {m['elbow']['r']['verdict']} | {sc['major']} / {sc['moderate']} / {sc['minor']} | {t} |")
print("\n".join(out))
print()
for k, m in a["models"].items():
    for s in ("l", "r"):
        print(f"- **{L[k]}, {m['elbow'][s]['statement']}**")
