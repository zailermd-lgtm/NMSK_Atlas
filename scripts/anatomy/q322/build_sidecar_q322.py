#!/usr/bin/env python3
"""Q322: the MUSCLE INNERVATION mode's per-page sidecar `innervation_q322.json` (public anatomy layer, committed data only).

Merges the public record `data/anatomy/innervation_q322.json` (nerve, branch, part-nerves, roots with per-source evidence,
IZ bands as % along named lines, conflicts) with this page's rule-based band placement `data/derived/Q322_iz_bands_<page>.json`
(scripts/anatomy/q322/place_iz_q322.py), plus the colour keys the mode draws with (nerve trunks, root levels). No geometry is
recomputed. Source titles are not copied (short labels + DOI / PMID only); the private clinical layer is never read.

    python3 scripts/anatomy/q322/build_sidecar_q322.py base_m build/q309/viewer_zan_atlas      # writes <dir>/innervation_q322.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data" / "anatomy" / "innervation_q322.json"
BANDS = REPO / "data" / "derived" / "Q322_iz_bands_{page}.json"
REGISTRY = [REPO / "data" / "nerves" / "brachial_plexus.json", REPO / "data" / "nerves" / "lumbosacral_plexus.json"]
NAME = "innervation_q322.json"
PAGES = ("base_m", "base_f")

# One hue per nerve TRUNK (the named peripheral nerve below the plexus); a branch takes its trunk's hue (walk up the registry's
# parent_id). Tibial and common fibular count as trunks of their own (the sciatic nerve is their common sheath); nerves that
# leave the plexus directly as a muscle's only supply are grouped (pectoral, subscapular), the psoas rami form "lumbar plexus".
TRUNKS = [
    ("musculocutaneous", "Musculocutaneous n.", ["musculocutaneous_n"], "#2a9d8f"),
    ("radial", "Radial n.", ["radial_n"], "#3f7fd6"),
    ("median", "Median n.", ["median_n", "median_n_lateral_root"], "#e8892b"),
    ("ulnar", "Ulnar n.", ["ulnar_n"], "#8e5bc9"),
    ("pectoral", "Pectoral nn.", ["lateral_pectoral_n", "medial_pectoral_n"], "#e36fa6"),
    ("subscapular", "Subscapular nn.", ["upper_subscapular_n", "lower_subscapular_n"], "#b5651d"),
    ("thoracodorsal", "Thoracodorsal n.", ["thoracodorsal_n"], "#5b8c2a"),
    ("femoral", "Femoral n.", ["femoral_n"], "#d64545"),
    ("obturator", "Obturator n.", ["obturator_n"], "#2bb0d8"),
    ("sciatic", "Sciatic n.", ["sciatic_n"], "#6b4f2a"),
    ("tibial", "Tibial n.", ["tibial_n"], "#1f9e5a"),
    ("fibular", "Common fibular n.", ["common_fibular_n"], "#c9a227"),
    ("piriformis", "Nerve to piriformis", ["nerve_to_piriformis"], "#7a7ad6"),
    ("lumbar", "Lumbar plexus (direct)", ["lumbar_root_T12", "lumbar_root_L1", "lumbar_root_L2", "lumbar_root_L3", "lumbar_root_L4"], "#a0522d"),
]
ROOT_ORDER = ["C4", "C5", "C6", "C7", "C8", "T1", "T12", "L1", "L2", "L3", "L4", "L5", "S1", "S2", "S3", "S4"]
ROOT_COL = {"C4": "#5b6bbf", "C5": "#3366cc", "C6": "#2a9d8f", "C7": "#7cb342", "C8": "#e0b030", "T1": "#e76f51",
            "T12": "#4b3f8f", "L1": "#6a4c93", "L2": "#8e5bc9", "L3": "#c06cc7", "L4": "#e36fa6", "L5": "#f08a5d",
            "S1": "#d64545", "S2": "#9c2f2f", "S3": "#6b1f1f", "S4": "#4a1515"}
KIND = {"iz": "innervation zone", "terminal_nerve_endings": "terminal nerve endings", "endplate_band": "endplate band",
        "endplate_zone": "endplate zone", "motor_point": "nerve entry point", "motor_points": "nerve entry points",
        "motor_entry_point": "nerve entry point", "motor_entry_points": "nerve entry points", "motor_branch_entry": "branch entry"}
# never in the public layer: the public-template ban list + injection vocabulary
BAN = re.compile(r"ultrasound|hounsfield|t1_se|imaging_tissues|tissue table|nmskultrasound|acoustic|mrayl|b-mode|inject|botul|toxin|needle|"
                 r"bont|\bdose|motor.point|sonograph", re.I)


def plain(o):
    """Free text in the public layer says "nerve entry point" where a source says "motor point" (the private layer's term)."""
    if isinstance(o, str):
        return re.sub(r"\b([Mm])otor point", lambda m: ("N" if m.group(1) == "M" else "n") + "erve entry point", o)
    if isinstance(o, list):
        return [plain(x) for x in o]
    if isinstance(o, dict):
        return {k: plain(v) for k, v in o.items()}
    return o


def registry():
    R = {}
    for f in REGISTRY:
        for e in json.loads(f.read_text(encoding="utf-8")):
            R[e["id"]] = e.get("parent_id")
    return R


def chain(nid, R):
    out, seen = [], set()
    while nid and nid not in seen:
        out.append(nid); seen.add(nid)
        nid = R.get(nid)
    return out


def trunk_of(nid, R):
    for x in chain(nid, R):
        for key, _l, members, _c in TRUNKS:
            if x in members:
                return key
    return None


def short_label(key, s):
    c = s.get("citation") or ""
    if key == "repo_textbook":
        return "Textbook registry (this repository's nerve / muscle records)"
    if key == "repo":
        return "This repository's muscle record"
    first = re.split(r",| et al", c, maxsplit=1)[0].strip()
    first = re.sub(r"\s+[A-Z]{1,3}$", "", first)            # drop the initials
    yr = re.search(r"(19|20)\d{2}", key) or re.search(r"\b(19|20)\d{2}\b", c)
    return f"{first} et al." + (f" {yr.group(0)}" if yr else "")


def build(page: str) -> dict:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    bands = json.loads(Path(str(BANDS).format(page=page)).read_text(encoding="utf-8"))
    R = registry()
    used_src = set()
    muscles = {}
    for mk, m in d["muscles"].items():
        nerves = [{"id": n["id"], "label": n["label"], "parent": n.get("parent")} for n in m["nerve"]]
        part_nerves = [p["nerve"] for p in m.get("parts", []) if p.get("nerve")]
        ids = [n["id"] for n in m["nerve"]] + part_nerves
        ch = sorted({x for i in ids for x in chain(i, R)})
        trunks = []
        for i in ids:
            t = trunk_of(i, R)
            if t and t not in trunks:
                trunks.append(t)
        roots = m["roots"]
        per = [{"src": p["src"], "levels": p["levels"], "note": p.get("note", "")} for p in roots.get("per_source", [])]
        used_src.update(p["src"] for p in per)
        iz = []
        for b in m.get("iz", []):
            iz.append({k: b[k] for k in ("part", "line", "pct", "src", "cite", "note") if k in b})
            used_src.update(b.get("src", []))
        other = []
        for o in m.get("iz_other_sources", []):
            other.append({"src": o["src"], "line": o.get("line"), "pct": o.get("pct"), "kind": KIND.get(o.get("kind"), (o.get("kind") or "").replace("_", " ")),
                          "same_line": o.get("same_line"), "agreement": o.get("agreement"), "part": o.get("part"), "note": o.get("note", "")})
            used_src.add(o["src"])
        muscles[mk] = {
            "name": m["name"], "region": m["region"], "structures": m["structures"].get(page, []),
            "parts": [{k: p[k] for k in ("id", "structures", "nerve", "note") if p.get(k)} for p in m.get("parts", [])],
            "nerve": nerves, "branch": m.get("branch"), "chain": ch, "trunks": trunks,
            "nerve_structures": m.get("nerve_structures_on_page", {}).get(page, []),
            "roots": {"adopted": roots.get("adopted", []), "text": roots.get("adopted_text"), "range": roots.get("range_across_sources"),
                      "per_source": per, "conflict": roots.get("conflict", []), "rule": roots.get("rule")},
            "iz": iz, "iz_other": other, "iz_decision": m.get("iz_decision"), "conflicts": m.get("conflicts", []), "guide_cite": m.get("guide_cite"),
        }
    srcs = {k: {"label": short_label(k, s), "doi": s.get("doi"), "pmid": s.get("pmid")} for k, s in d["sources"].items() if k in used_src}
    lines = {k: {"label": v["label"], "from": v["from"], "to": v["to"], "mode": v["mode"]} for k, v in d["lines"].items()}
    lms = {k: {"label": v.get("label"), "kind": v.get("kind"), **({"proxy": v.get("definition")} if v.get("kind") == "soft_tissue" else {})}
           for k, v in d["landmarks"].items()}
    out_bands = []
    for b in bands["bands"]:
        o = {"m": b["muscle"], "iz": b["iz"], "part": b["part"], "s": b["side"], "st": b["status"]}
        for k in ("dot", "rings", "level_pct", "snap_mm", "shifted_mm", "note", "reason", "same_as", "proxy", "line_len_mm"):
            if k in b:
                o[k] = b[k]
        if b["status"] == "qualitative":
            o["from_pt"], o["to_pt"] = b["from_pt"], b["to_pt"]
        out_bands.append(o)
    roots_present = sorted({r for m in muscles.values() for r in m["roots"]["adopted"]}, key=lambda r: ROOT_ORDER.index(r) if r in ROOT_ORDER else 99)
    res = {
        "schema": "nmsk.innervation.page.v1", "round": "Q322", "page": page,
        "primary": {"label": short_label("guv2026", d["sources"]["guv2026"]), "doi": d["sources"]["guv2026"].get("doi"),
                    "journal": "Eur J Phys Rehabil Med 2026;62(5):441-59", "licence": "CC BY-NC-ND 4.0 (facts only)"},
        "rule": bands["rule"], "fail_mm": bands["fail_mm"],
        "colour_rules": {
            "nerve": "One colour per nerve trunk; a branch takes its trunk's colour. A muscle with two nerves is coloured by the first listed and lists both.",
            "root": "A muscle is coloured by the middle level of its adopted root range (for an even count, the more cranial of the two middle levels); its card shows the whole range.",
        },
        "trunks": [{"key": k, "label": l, "colour": c, "nerves": mem} for k, l, mem, c in TRUNKS],
        "roots": [{"level": r, "colour": ROOT_COL.get(r, "#888888")} for r in roots_present],
        "muscles": muscles, "lines": lines, "landmarks": lms, "sources": srcs,
        "bands": out_bands, "counts": bands["counts"], "landmark_failures": bands["landmark_failures"],
    }
    res = plain(res)
    txt = json.dumps(res, ensure_ascii=False)
    hit = BAN.search(txt)
    if hit:
        i = hit.start()
        raise SystemExit(f"{page}: public sidecar would carry a banned term {hit.group(0)!r}: ...{txt[max(0, i - 80):i + 40]}...")
    return res


def main() -> int:
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 2 or a[0] not in PAGES:
        print(__doc__); return 2
    res = build(a[0])
    out = Path(a[1]) / NAME
    out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{a[0]}: {out} ({out.stat().st_size // 1024} KB, {len(res['muscles'])} muscles, {sum(1 for b in res['bands'] if b['st'] == 'placed')} placed bands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
