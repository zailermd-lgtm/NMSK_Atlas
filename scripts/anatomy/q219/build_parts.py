#!/usr/bin/env python3
"""Q219: assemble data/anatomy/structure_parts.json (sourced parts model) + data/derived/Q219_parts_coverage.json.
    python3 scripts/anatomy/q219/build_parts.py
Anatomy layer, CC BY-SA 4.0 compatible (a table of facts with citations; no geometry, no clinical content)."""
from __future__ import annotations
import datetime as dt, glob, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
REPO = HERE.parents[2]
import rows_common
import rows_upper, rows_lower, rows_trunk_hand, rows_hand_passages  # noqa: F401  (import fills rows_common.ROWS / SETS)
from refs import REFS

BODIES = ["vhm", "vhf", "zan_m", "zan_f"]
OUT = REPO / "data/anatomy/structure_parts.json"
COV = REPO / "data/derived/Q219_parts_coverage.json"
IDX = REPO / "data/derived/Q219_structure_ids.json"
SIDE = re.compile(r"_(r|l)$")


def base(i: str) -> str:
    return SIDE.sub("", re.sub(r"_zfill.*$", "", i))


def entity_index():
    ent = {}
    for p in sorted(glob.glob(str(REPO / "data/*/**/*.json"), recursive=True)):
        top = p.split("/data/")[1].split("/")[0]
        if top in ("derived", "ct_sources", "corrections", "rig", "anatomy"):
            continue
        try:
            j = json.load(open(p))
        except Exception:
            continue
        recs = j if isinstance(j, list) else [j] if isinstance(j, dict) and "id" in j else (j.get("items") or j.get("structures") or [])
        for r in recs:
            if isinstance(r, dict) and "id" in r:
                ent.setdefault(top, set()).add(base(r["id"]))
    return ent


def short_cite(ref_id: str) -> str:
    r = REFS[ref_id]
    if r["kind"] != "journal":
        return r["citation"]
    au = r["citation"].split(".")[0].split(",")[0].replace(" ", " ")
    m = re.search(r"(\d{4});([^\s]+)$", r["citation"])
    jr = re.search(r"\.\s([^.]+?)\s\d{4};", r["citation"])
    doi = f" doi:{r['doi']}" if r["doi"] else ""
    return f"{au} et al. {m.group(1) if m else ''} {jr.group(1) if jr else ''} {m.group(2) if m else ''}{doi} PMID:{r['pmid']}"


def main():
    ids = json.loads(IDX.read_text())
    ent = entity_index()
    ent_all = set().union(*ent.values())
    own_base = {b: set(base(i) for i in ids[b]["ids"]) for b in BODIES}
    rows = rows_common.ROWS
    sets = rows_common.SETS
    errors = []
    used_refs = set()
    out_rows = []
    for r in rows:
        sid = r["structure_id"]
        # resolve structure id
        cands = {sid, "zan_" + sid}
        found_in = []
        if any(c in ent_all for c in cands):
            found_in.append("data")
        for b in BODIES:
            if any(c in own_base[b] for c in cands):
                found_in.append(b)
        if not found_in:
            errors.append(f"{r['id']}: structure_id '{sid}' resolves to no data record or body structure")
        for ref in r["refs"]:
            if ref not in REFS:
                errors.append(f"{r['id']}: unknown ref {ref}")
            used_refs.add(ref)
        if r["set_id"] and r["set_id"] not in sets:
            errors.append(f"{r['id']}: unknown set {r['set_id']}")
        if r["verification"] == "unverified" and not any(REFS[x]["kind"] != "journal" for x in r["refs"] if x in REFS):
            errors.append(f"{r['id']}: unverified row must cite a textbook/owner ref")
        if r["verification"] == "verified" and not any(REFS[x]["kind"] == "journal" for x in r["refs"] if x in REFS):
            errors.append(f"{r['id']}: verified row without a journal ref")
        # map to the bodies' structures
        whole, part = {}, {}
        for b in BODIES:
            have = set(ids[b]["ids"])
            w = []
            for c in (sid, "zan_" + sid):
                for s in ("r", "l"):
                    if f"{c}_{s}" in have:
                        w.append(f"{c}_{s}")
                if c in have:
                    w.append(c)
            whole[b] = sorted(set(w))
            pz = []
            for pat in r["z_part_ids"]:
                if "{s}" in pat:
                    pz += [pat.replace("{s}", s) for s in ("r", "l") if pat.replace("{s}", s) in have]
                elif pat in have:
                    pz.append(pat)
            part[b] = sorted(set(pz))
        rr = dict(r)
        rr["citation"] = "; ".join(short_cite(x) for x in r["refs"] if x in REFS)
        rr["maps_to"] = {"structure_ids": whole, "part_ids": part}
        rr["resolved_in"] = found_in
        rr["has_own_part_mesh"] = any(part[b] for b in ("vhm", "vhf"))
        rr["has_z_part_mesh"] = any(part[b] for b in ("zan_m", "zan_f"))
        rr["geometry_rule"] = (r["geometry"] or {}).get("rule")
        rr.pop("own_part_ids", None); rr.pop("z_part_ids", None); rr.pop("order", None)
        out_rows.append(rr)
    for sid_, st in sets.items():
        for c in st["reported_counts"]:
            if c["ref"] not in REFS:
                errors.append(f"set {sid_}: unknown ref {c['ref']}")
            used_refs.add(c["ref"])
    if errors:
        print("\n".join(errors)); sys.exit(1)
    # sets: members
    members = defaultdict(list)
    for r in out_rows:
        if r["set_id"]:
            members[r["set_id"]].append(r["id"])
    sets_out = []
    for k, st in sets.items():
        st = dict(st); st["member_part_ids"] = members.get(k, [])
        sets_out.append(st)
    refs_out = {k: REFS[k] for k in sorted(used_refs)}
    doc = {
        "schema": "nmsk.structure_parts.v1",
        "schema_doc": "data/anatomy/parts_schema.md",
        "generated": dt.date.today().isoformat(),
        "license": "Anatomy layer: CC BY-SA 4.0 compatible (facts with citations; no clinical content, no geometry).",
        "ambiguity_recorded": "Owner wrote 'ברקטום' (rectum or rectus). Both are covered: rectus abdominis tendinous intersections + rectus sheath + linea alba (abdominal wall) and rectum / anorectal passages (lateral ligament, Denonvilliers and rectosacral fascia, puborectalis sling, pudendal canal).",
        "part_types": rows_common.PART_TYPES,
        "references": refs_out,
        "part_sets": sets_out,
        "parts": out_rows,
        "counts": {
            "parts": len(out_rows),
            "by_part_type": dict(Counter(r["part_type"] for r in out_rows)),
            "by_verification": dict(Counter(r["verification"] for r in out_rows)),
            "structures": len({r["structure_id"] for r in out_rows}),
            "references": len(refs_out),
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(doc["counts"], indent=1))
    # ---------------- coverage vs the entity list
    have_parts = defaultdict(list)
    for r in out_rows:
        have_parts[r["structure_id"]].append(r["id"])
    cov_ent = {}
    for cls_, s in ent.items():
        if cls_ in ("muscles", "ligaments", "tendons", "fascia", "bursae", "cartilage"):
            with_ = sorted(x for x in s if x in have_parts or ("zan_" + x) in have_parts)
            without = sorted(x for x in s if x not in with_)
            cov_ent[cls_] = {"entities": len(s), "with_parts": len(with_), "without_parts": len(without), "with_parts_ids": with_, "without_parts_ids": without}
    cov_body = {}
    for b in BODIES:
        bb = defaultdict(lambda: {"structures": 0, "with_parts": 0})
        withp = set()
        for i, cat in ids[b]["ids"].items():
            bi = base(i)
            has = bi in have_parts or bi.replace("zan_", "", 1) in have_parts
            bb[cat]["structures"] += 1
            bb[cat]["with_parts"] += int(has)
        # explicit part meshes present
        pm = sorted({p for r in out_rows for p in r["maps_to"]["part_ids"][b]})
        cov_body[b] = {"by_category": {k: v for k, v in sorted(bb.items())}, "structures_total": len(ids[b]["ids"]),
                       "structures_with_parts": sum(v["with_parts"] for v in bb.values()), "dedicated_part_meshes_present": pm}
    cov = {
        "generated": dt.date.today().isoformat(),
        "note": "Coverage of the parts table over (a) the data/ entity list (side-agnostic ids) and (b) the structures of the four bodies. 'with_parts' = at least one sourced part row. Rows marked unverified count as covered but are flagged in the table.",
        "parts_total": len(out_rows), "structures_with_parts": len(have_parts),
        "by_part_type": doc["counts"]["by_part_type"], "by_verification": doc["counts"]["by_verification"],
        "entity_classes": cov_ent, "bodies": cov_body,
        "structures_by_part_count": {k: len(v) for k, v in sorted(have_parts.items(), key=lambda kv: -len(kv[1]))},
        "unverified_rows": [r["id"] for r in out_rows if r["verification"] == "unverified"],
    }
    COV.write_text(json.dumps(cov, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for k, v in cov_ent.items():
        print(k, v["entities"], "with", v["with_parts"])


if __name__ == "__main__":
    main()
