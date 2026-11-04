#!/usr/bin/env python3
"""Q289: merge the muscle-architecture table the simulated ultrasound uses into clinical/data/ultrasound_tissues.json ("architecture").

Inputs (both committed):
  data/anatomy/us_architecture_q289.json  hand-curated: documented septa / aponeuroses + part bands, each with citations and the
                                          rule that places it in a mesh; references; honesty lines
  data/muscles/*/*.json                   the project's per-muscle architecture records: overall_architecture_type and, per
                                          functional compartment, pennation_deg + PCSA + the compartment's source line

Output: ultrasound_tissues.json["architecture"] = {honesty, references, rules, sources[], muscles{base_id: {...}}} where base_id is the
muscle id without its side suffix (rectus_femoris_r -> rectus_femoris). Pennation = PCSA-weighted mean over the compartments that carry
a value (the right side's record when both exist). A curated entry may override type / pennation (with its own references).

    python3 scripts/clinical/q289_architecture.py           # write
    python3 scripts/clinical/q289_architecture.py --check   # exit 1 if the committed table is stale
"""
from __future__ import annotations
import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
US_PATH = REPO / "clinical" / "data" / "ultrasound_tissues.json"
CUR_PATH = REPO / "data" / "anatomy" / "us_architecture_q289.json"


def base_id(mid: str) -> str:
    for suf in ("_r", "_l"):
        if mid.endswith(suf):
            return mid[: -len(suf)]
    return mid


def build() -> dict:
    cur = json.loads(CUR_PATH.read_text(encoding="utf-8"))
    recs = {}
    for f in sorted(glob.glob(str(REPO / "data" / "muscles" / "*" / "*.json"))):
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        mid = d.get("id") or ""
        b = base_id(mid)
        if b in recs and not mid.endswith("_r"):
            continue                                                  # one record per muscle: the right side's when both exist
        recs[b] = d
    sources, src_ix, muscles = [], {}, {}
    for b in sorted(recs):
        d = recs[b]
        comps = []
        for c in d.get("functional_compartments") or []:
            fa = c.get("fiber_architecture") or {}
            p = fa.get("pennation_deg")
            if p is None:
                continue
            s = (c.get("source") or d.get("source") or "").strip()
            s = s[:240]
            if s not in src_ix:
                src_ix[s] = len(sources); sources.append(s)
            comps.append([c.get("name") or c.get("id"), float(p), float(fa.get("physiological_cross_section_area_mm2") or 0), src_ix[s]])
        if not comps:
            continue
        w = sum(max(1.0, c[2]) for c in comps)
        pen = sum(c[1] * max(1.0, c[2]) for c in comps) / w
        muscles[b] = {"t": d.get("overall_architecture_type") or "", "p": round(pen, 1), "c": [[c[0], c[1], c[2]] for c in comps], "s": sorted({c[3] for c in comps})}
    for b, e in cur["muscles"].items():
        m = muscles.setdefault(b, {"t": "", "p": 0.0, "c": [], "s": []})
        m["t"] = e.get("type") or m["t"]
        if e.get("pennation_deg") is not None:
            m["p"] = float(e["pennation_deg"])
        if e.get("pennation_proximal_deg") is not None:
            m["p0"] = float(e["pennation_proximal_deg"]); m["p1"] = float(e["pennation_distal_deg"])
        if e.get("pennation_refs"):
            m["pr"] = list(e["pennation_refs"])
        if e.get("parts"):
            m["parts"] = e["parts"]
        if e.get("septa"):
            m["septa"] = e["septa"]
        if e.get("aponeuroses_note"):
            m["apo"] = e["aponeuroses_note"]
        m["curated"] = True
    return {"schema": cur["schema"], "honesty": cur["honesty"], "references": cur["references"], "rules": cur["rules"], "render": cur["render"], "sources": sources, "muscles": muscles}


def main():
    check = "--check" in sys.argv
    us = json.loads(US_PATH.read_text(encoding="utf-8"))
    arch = build()
    if check:
        if us.get("architecture") != arch:
            print("q289_architecture: ultrasound_tissues.json['architecture'] is STALE -- run scripts/clinical/q289_architecture.py")
            sys.exit(1)
        print("q289_architecture: up to date (%d muscles, %d with documented septa)" % (len(arch["muscles"]), sum(1 for m in arch["muscles"].values() if m.get("septa"))))
        return
    # the acoustic table is hand-formatted: keep every other byte, (re)write only the trailing "architecture" member (one muscle per line)
    txt = US_PATH.read_text(encoding="utf-8")
    cut = txt.find(',\n  "architecture": ')
    head = (txt[:cut] if cut >= 0 else txt.rstrip()[:-1].rstrip()) + ',\n  "architecture": '
    body = {k: v for k, v in arch.items() if k != "muscles"}
    out = json.dumps(body, ensure_ascii=False)[:-1] + ', "muscles": {\n' + ",\n".join(
        "   " + json.dumps(k) + ": " + json.dumps(v, ensure_ascii=False) for k, v in arch["muscles"].items()) + "\n  }}\n}\n"
    US_PATH.write_text(head + out, encoding="utf-8")
    assert json.loads(US_PATH.read_text(encoding="utf-8"))["architecture"] == arch
    print("wrote %s: %d muscles, %d with documented septa, %d source lines" % (US_PATH.relative_to(REPO), len(arch["muscles"]), sum(1 for m in arch["muscles"].values() if m.get("septa")), len(arch["sources"])))


if __name__ == "__main__":
    main()
