#!/usr/bin/env python3
"""Q249: summary tables of the shipped / held / skipped nerves of the six pages (markdown) for PROJECT_STATE.md and the final report.   python3 scripts/anatomy/q249/report_md.py > /tmp/q249_tables.md"""
import json, re
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[3]; D = REPO / "data/derived"
PAGES = [("own_f", "Imaging-based F"), ("own_m", "Imaging-based M"), ("comb_f", "Combined F"), ("comb_m", "Combined M"), ("base_f", "Base F"), ("base_m", "Base M")]
GROUPS = [("sacral rami S1-S4 + lumbosacral trunk", r"^(s[1-4]_ventral_ramus|lumbosacral_trunk)"), ("pudendal trunk", r"^pudendal_n_"), ("inferior rectal", r"^inferior_rectal"), ("perineal", r"^perineal_n"),
          ("dorsal n. penis / clitoris", r"^dorsal_n_"), ("inferior gluteal", r"^inferior_gluteal"), ("n. obturator internus", r"^nerve_to_obturator"), ("n. quadratus femoris", r"^nerve_to_quadratus"),
          ("posterior femoral cutaneous", r"^posterior_femoral"), ("n. levator ani / coccygeus", r"^nerve_to_(levator|coccy)"), ("coccygeal plexus / anococcygeal", r"^(coccygeal_plexus|anococcygeal)"),
          ("hypogastric / plexuses / splanchnic", r"(hypogastric_|splanchnic)"), ("iliohypogastric / ilioinguinal / genitofemoral", r"^(iliohypogastric|ilioinguinal|genitofemoral)"),
          ("lumbar medial branches (+ L5 dorsal ramus)", r"(medial_branch|dorsal_ramus)"), ("median recurrent branch", r"^recurrent")]
print("| Page | shipped | total length m | volume cm3 | assumption / cited calibre | error bound mm (min / median / max) | held | skipped (Z has it) |\n|---|---|---|---|---|---|---|---|")
for k, lab in PAGES:
    j = json.loads((D / f"Q249_rule_{k}.json").read_text()); sh = {i: v for i, v in j["structures"].items() if v["status"] == "ship"}
    held = [i for i, v in j["structures"].items() if v["status"] == "held"]
    eb = [v["report"]["waypoint_error_bound_mm"] for v in sh.values()]; ca = sum(1 for v in sh.values() if v["calibre_kind"] == "assumption")
    print(f"| {lab} | {len(sh)} | {sum(v['report']['length_mm'] for v in sh.values()) / 1000:.2f} | {sum(v['report']['volume_cm3'] for v in sh.values()):.1f} | {ca} / {len(sh) - ca} | {min(eb):.1f} / {np.median(eb):.1f} / {max(eb):.1f} | {len(held)} | {len(j['skipped'])} |")
print("\n| group | " + " | ".join(l for _, l in PAGES) + " |\n|---|" + "---|" * len(PAGES))
J = {k: json.loads((D / f"Q249_rule_{k}.json").read_text()) for k, _ in PAGES}
for g, pat in GROUPS:
    row = []
    for k, _ in PAGES:
        sh = {i: v for i, v in J[k]["structures"].items() if v["status"] == "ship" and re.search(pat, i)}
        row.append(f"{len(sh)} ({sum(v['report']['length_mm'] for v in sh.values()):.0f} mm)" if sh else "-")
    print(f"| {g} | " + " | ".join(row) + " |")
print("\nHeld:")
for k, lab in PAGES:
    for i, v in J[k]["structures"].items():
        if v["status"] == "held":
            print(f"- {lab} `{i}`: {'; '.join(v['held'])}")
