#!/usr/bin/env python3
"""Q249: update data/derived/Q247_nerve_coverage.md after the rule-based nerves: the checklist rows of section 3 that Q249 filled get a new cell (Z-family column / Imaging-based F / M columns), the section 1 'checklist covered'
and section 2 headline counts are recomputed from the table, section 4's counts line is restated, and a section 6 'Q249 update' lists before / after.  Idempotent (the section 6 block and the cells are rewritten from the shipped JSONs).
    python3 scripts/anatomy/q249/update_q247.py [--dry]"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
MD = REPO / "data/derived/Q247_nerve_coverage.md"
D = REPO / "data/derived"
ZPAGES = {"comb_m": "Combined M", "comb_f": "Combined F", "base_m": "Base M", "base_f": "Base F"}
OWN = {"own_f": "f_hr", "own_m": "m_hr"}
# (group, item prefix) -> (predicate on the id list of one page, own pages too?, note)
def has(ids, *pats):
    out = {}
    for s in "lr":
        out[s] = any(re.match(p + f"_{s}$", i) for p in pats for i in ids)
    return out
ROWS = [
    ("Lumbar plexus", "Lumbar dorsal rami", ("lumbar_medial_branch_l[1-4]", "l5_dorsal_ramus_medial_branch"), True, "medial branches L1-L4 + L5 dorsal ramus"),
    ("Lumbar plexus", "Iliohypogastric n.", ("iliohypogastric_n",), False, ""),
    ("Lumbar plexus", "Ilioinguinal n.", ("ilioinguinal_n",), True, "no ilioinguinal mesh exists on the four Z pages (Q247 listed Y)"),
    ("Lumbar plexus", "Genitofemoral n.", ("genitofemoral_n",), False, ""),
    ("Lumbar plexus", "Genitofemoral genital branch", ("genitofemoral_n",), False, "drawn as the genital course of genitofemoral_n"),
    ("Brachial plexus", "Median recurrent", ("recurrent_branch_of_median_n",), True, ""),
    ("Sacral plexus", "Lumbosacral trunk", ("s1_ventral_ramus", "lumbosacral_trunk"), True, "S1-S4 ventral rami + lumbosacral trunk"),
    ("Sacral plexus", "Inferior gluteal n.", ("inferior_gluteal_n",), True, ""),
    ("Sacral plexus", "N. to quadratus femoris", ("nerve_to_quadratus_femoris",), False, ""),
    ("Sacral plexus", "N. to obturator internus", ("nerve_to_obturator_internus",), True, ""),
    ("Sacral plexus", "Posterior femoral cutaneous n.", ("posterior_femoral_cutaneous_n",), False, ""),
    ("Sacral plexus", "Coccygeal plexus", ("coccygeal_plexus", "anococcygeal_n"), True, ""),
    ("Pelvic floor", "Pudendal n. (trunk)", ("pudendal_n",), False, ""),
    ("Pelvic floor", "Inferior rectal n.", ("inferior_rectal_n",), True, ""),
    ("Pelvic floor", "Perineal n.", ("perineal_n",), True, ""),
    ("Pelvic floor", "Dorsal n. of clitoris", ("dorsal_n_clitoris", "dorsal_n_penis"), True, "sex-specific: penis on the male pages, clitoris on the female pages"),
    ("Pelvic floor", "N. to levator ani", ("nerve_to_levator_ani", "nerve_to_coccygeus"), True, ""),
    ("Autonomic", "Superior hypogastric plexus", ("hypogastric_n",), True, "hypogastric nerves + superior hypogastric plexus"),
    ("Autonomic", "Inferior hypogastric", ("inferior_hypogastric_plexus", "pelvic_splanchnic_n_s[2-4]"), True, "inferior hypogastric plexus + pelvic splanchnic nerves S2-S4"),
]


def load():
    S = {}
    for k in list(ZPAGES) + list(OWN):
        j = json.loads((D / f"Q249_rule_{k}.json").read_text())
        S[k] = [i for i, v in j["structures"].items() if v["status"] == "ship"]
    return S


def side_txt(h):
    return "L+R" if h["l"] and h["r"] else ("L only" if h["l"] else ("R only" if h["r"] else "-"))


def classify(cell, z):
    c = cell.strip()
    if c == "-" or c == "":
        return "absent"
    if z:
        return "Y" if c.startswith("Y") else ("M" if c.startswith("M") else "absent")
    return "cov"


def count(lines, col, z):
    from collections import defaultdict
    g = defaultdict(lambda: defaultdict(int)); tot = defaultdict(int)
    for ln in lines:
        p = [x.strip() for x in ln.strip().strip("|").split(" | ")]
        if len(p) < 6 or p[0] in ("Group", "---"):
            continue
        c = classify(p[col], z); g[p[0]][c] += 1; tot[c] += 1
    return g, tot


def main(dry=False):
    S = load()
    md = MD.read_text(encoding="utf-8").split("\n")
    i3 = next(i for i, l in enumerate(md) if l.startswith("## 3.")); i4 = next(i for i, l in enumerate(md) if l.startswith("## 4."))
    rows = list(range(i3, i4))
    before = count([md[i] for i in rows if md[i].startswith("| ")], 3, True), count([md[i] for i in rows if md[i].startswith("| ")], 4, False), count([md[i] for i in rows if md[i].startswith("| ")], 5, False)
    changed = []
    for grp, pref, pats, both, note in ROWS:
        for i in rows:
            p = [x.strip() for x in md[i].strip().strip("|").split(" | ")] if md[i].startswith("| ") else None
            if not p or len(p) < 6 or p[0] != grp or not p[1].startswith(pref):
                continue
            # Z-family
            zdet = {k: side_txt(has(S[k], *pats)) for k in ZPAGES}
            zdet_ok = {k: v for k, v in zdet.items() if v != "-"}
            if not (p[3].startswith("Y") and not both):
                if zdet_ok:
                    pages = ", ".join(f"{ZPAGES[k]} {v}" for k, v in zdet_ok.items())
                    allp = len(zdet_ok) == 4 and all(v == "L+R" for v in zdet_ok.values())
                    was = "" if p[3] in ("-", "") else f"; Q247: {p[3]}"
                    p[3] = f"Y rule-based Q249 ({'all four pages L+R' if allp else pages}{('; ' + note) if note else ''}{was})"
            # own pages
            for ci, k in ((4, "own_f"), (5, "own_m")):
                h = has(S[k], *pats)
                if h["l"] or h["r"]:
                    old = p[ci]
                    p[ci] = f"rule L:{'Y' if h['l'] else '-'} R:{'Y' if h['r'] else '-'}" + (f" (Q247: {old})" if old not in ("-", "") else "")
            md[i] = "| " + " | ".join(p) + " |"
            changed.append((grp, pref))
    after = count([md[i] for i in rows if md[i].startswith("| ")], 3, True), count([md[i] for i in rows if md[i].startswith("| ")], 4, False), count([md[i] for i in rows if md[i].startswith("| ")], 5, False)
    # section 1 / 2 / 4 restated
    text = "\n".join(md)
    zb, za = before[0][1], after[0][1]
    text = text.replace("| 93 Y / 8 M / 45 absent |", f"| {za['Y']} Y / {za['M']} M / {za['absent']} absent (Q247: {zb['Y']} Y / {zb['M']} M / {zb['absent']} absent; Q249 rows rule-based) |")
    text = re.sub(r"\| 10 Y / 0 M / 136 absent \|", f"| {10 + after[1][1]['cov'] - before[1][1]['cov']} covered / {after[1][1]['absent']} absent (Q247: 10 Y; + {after[1][1]['cov'] - before[1][1]['cov']} checklist rows rule-based Q249) |", text)
    text = re.sub(r"\| 9 Y / 0 M / 137 absent \|", f"| {9 + after[2][1]['cov'] - before[2][1]['cov']} covered / {after[2][1]['absent']} absent (Q247: 9 Y; + {after[2][1]['cov'] - before[2][1]['cov']} checklist rows rule-based Q249) |", text)
    # section 2 headline table
    gb, ga = before[0][0], after[0][0]
    out = []
    for ln in text.split("\n"):
        m = re.match(r"\| (Cranial|Cervical plexus|Brachial plexus|Thoracic|Spinal|Lumbar plexus|Sacral plexus|Pelvic floor|Autonomic) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|$", ln)
        if m and m.group(1) in ga:
            g = m.group(1); out.append(f"| {g} | {m.group(2)} | {ga[g]['Y']} | {ga[g]['M']} | {ga[g]['absent']} |")
        elif re.match(r"\| \*\*Total\*\* \| 146 \| \d+ \| \d+ \| \d+ \|$", ln):
            out.append(f"| **Total** | 146 | {za['Y']} | {za['M']} | {za['absent']} |")
        else:
            out.append(ln)
    text = "\n".join(out)
    # section 4: counts line and the tier-1 absent list restated from the table
    absent = {1: [], 2: [], 3: []}; merged = 0
    j3 = next(i for i, l in enumerate(out) if l.startswith("## 3.")); j4 = next(i for i, l in enumerate(out) if l.startswith("## 4."))
    for ln in out[j3:j4]:
        pp = [x.strip() for x in ln.strip().strip("|").split(" | ")] if ln.startswith("| ") else None
        if not pp or len(pp) < 6 or pp[0] in ("Group", "---", "Page (build/q244/...)") or not pp[2].isdigit():
            continue
        if classify(pp[3], True) == "absent":
            absent[int(pp[2])].append((pp[0], pp[1]))
        elif classify(pp[3], True) == "M":
            merged += 1
    na = sum(len(v) for v in absent.values())
    text = re.sub(r"Counts: 45 items absent on every page \(tier 1: 18, tier 2: 19, tier 3: 8\); 8 items present only merged",
                  f"Counts (after Q249; Q247: 45 absent = tier 1: 18, tier 2: 19, tier 3: 8; 8 merged): {na} items absent on every Z page (tier 1: {len(absent[1])}, tier 2: {len(absent[2])}, tier 3: {len(absent[3])}); {merged} items present only merged", text)
    text = re.sub(r"(Tier-1 absent items \(checklist rows\):\n\n)(?:- [^\n]*\n)+", lambda m: m.group(1) + "".join(f"- {g}: {i}\n" for g, i in absent[1]), text)
    # section 6
    sec = ["", "## 6. Q249 update (rule-based nerves; nothing here is measured)", "",
           f"Rows of section 3 filled by the rule-based nerves of Q249 (courses from Gray's Anatomy 1918, calibres and variability from the cited papers; every nerve is badged RULE-BASED, its card lists waypoints, calibre source and error bound): {len(changed)} of the 19 mapped rows touched.", "",
           f"Z-family (4 pages): {zb['Y']} Y / {zb['M']} M / {zb['absent']} absent -> {za['Y']} Y / {za['M']} M / {za['absent']} absent of 146 (a 'Y rule-based' cell means at least one of the four pages carries the nerve; the cell lists which). "
           f"Imaging-based F: {before[1][1]['cov']} -> {after[1][1]['cov']} covered rows; Imaging-based M: {before[2][1]['cov']} -> {after[2][1]['cov']} (own-page columns count every non-'-' cell).", "",
           "Per page, nerves shipped (ids in `data/derived/Q249_shipped_<page>.json`, held and skipped nerves with reasons in `data/derived/Q249_rule_<page>.json`):", "",
           "| Page | shipped | held | skipped because the Z page already has the nerve |", "|---|---|---|---|"]
    for k, lab in (("own_f", "Imaging-based F"), ("own_m", "Imaging-based M"), ("comb_f", "Combined F"), ("comb_m", "Combined M"), ("base_f", "Base F"), ("base_m", "Base M")):
        j = json.loads((D / f"Q249_rule_{k}.json").read_text())
        held = [i for i, v in j["structures"].items() if v["status"] == "held"]
        sec.append(f"| {lab} | {sum(1 for v in j['structures'].values() if v['status'] == 'ship')} | {len(held)}: {', '.join(held) if held else '-'} | {len(j['skipped'])} |")
    sec += ["", "Still absent after Q249 (tier 1): phrenic n., cervical / thoracic dorsal-ramus medial branches, femoral / tibial muscular branches, calcaneal branches, nerve to hamstrings, perineal branch of the posterior femoral cutaneous n. (course not attempted: the mediastinal / cervical / limb "
            "structures needed as anchors were not validated in this task).", ""]
    text = re.sub(r"\n## 6\. Q249 update.*\Z", "", text, flags=re.S).rstrip("\n") + "\n" + "\n".join(sec)
    if dry:
        print("changed rows", changed); print("Z before", dict(zb), "after", dict(za)); print("own_f cov", before[1][1]['cov'], '->', after[1][1]['cov'], "own_m", before[2][1]['cov'], '->', after[2][1]['cov']); return
    MD.write_text(text, encoding="utf-8")
    print("updated", MD, "rows", len(changed), "Z", dict(zb), "->", dict(za))


if __name__ == "__main__":
    main("--dry" in sys.argv)
