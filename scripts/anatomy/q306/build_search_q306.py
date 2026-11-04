#!/usr/bin/env python3
"""Q306: compile the search COVERAGE layer on top of Q298's, per page, and inject it as its own block.

Q298 gave the search its synonym layer. Q306 measured what that layer still could not reach
(docs/research/Q306_search_coverage_audit.md): of 419 terms a clinician would type, 132 returned
something. The three the owner named were all in the 287 that did not -- `psoas minor` returned
`Psoas major` at rank 1 with no note, `hip flexors` returned nothing on every page although the page
carried the group, and `pelvic tilt` had no concept layer to answer from at all.

This script resolves Q306's four data files against each page's own structure list at BUILD time -- the
same discipline as Q298, nothing guessed in the browser -- and writes

    data/derived/Q306_search_<key>.json   {ids, sub, alias[], groups[], concepts[], not_shipped[], ...}

a SUPERSET of Q298's table for that page. `--inject DIR` writes it between the `<!-- NMSK-Q306 -->`
markers as its own block, so Q298's block comes out of the regen byte-identical and the round it stands
on is unchanged.

THE CORE FIX is in `groups`: Q298 put the 17 named textbook groups in the search table but left the 87
action-derived groups and the 6 extras only in the RELATIONS block, which the search never reads -- so no
typed name could ever reach them. Every group the page really carries is brought into the search table
here, with the clinical names and the corrected labels of data/anatomy/groups_q306.json.

    python3 scripts/anatomy/q306/build_search_q306.py [--src DIR] [KEY...]
    python3 scripts/anatomy/q306/build_search_q306.py --inject DIR
"""
from __future__ import annotations

import base64
import json
import re
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q298"))
import pagedata as P                      # noqa: E402
import build_search_q298 as Q8            # noqa: E402

DATA = REPO / "data/anatomy"
DERIVED = REPO / "data/derived"
BEGIN, END = "<!-- NMSK-Q306 begin -->", "<!-- NMSK-Q306 end -->"
SYN6 = DATA / "synonyms_q306.json"
GRP6 = DATA / "groups_q306.json"
CON6 = DATA / "concepts_q306.json"
MG6 = DATA / "muscle_groups_q306.json"


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def compile_page(key: str, src=None) -> dict:
    src = src or P._baseline()   # Q310: resolve HERE too, so the recorded provenance names the real build
    """Q298's compiled table for this page, extended with Q306's data."""
    base = Q8.compile_page(key, src)
    ss = P.structures(key, src)
    ix = Q8._index(key, src)[1]
    by_id = {s["id"]: i for i, s in enumerate(ss)}

    ids = list(base["ids"])
    sub = list(base["sub"])
    pos = {sid: n for n, sid in enumerate(ids)}
    subof = {}
    for i, s in enumerate(ss):
        nm = P.fold(s["name"])
        subof[s["id"]] = 1 if (s["part_of_id"] or s["part_of"] or "continuation beyond" in nm
                               or re.search(r"\b(head|part) of \b", nm)) else 0

    def slots(idxs):
        out = []
        for i in idxs:
            sid = ss[i]["id"]
            if sid not in pos:
                pos[sid] = len(ids)
                ids.append(sid)
                sub.append(subof[sid])
            out.append(pos[sid])
        return sorted(set(out))

    alias = list(base["alias"])
    groups = list(base["groups"])
    nshp = list(base["not_shipped"])
    unresolved = []
    syn = _load(SYN6)
    gnm = _load(GRP6)
    con = _load(CON6)
    newg = _load(MG6)

    # ---------------------------------------------------------------- synonym entries and families
    for e in syn["entries"]:
        hits = Q8._hit_targets(ix, e.get("targets") or [e["canon"]])
        if not hits:
            unresolved.append({"canon": e["canon"], "reason": "no structure with this name on this page"})
            continue
        ii = slots(hits)
        for q, d, k in Q8._forms(e, "syn"):
            a = {"q": q, "d": d, "k": k, "c": e["canon"], "i": ii, "s": e.get("src", ""), "r": "Q306"}
            if e.get("note"):
                a["n"] = e["note"]
            if e.get("ambiguous"):
                a["amb"] = 1
            if e.get("multi_part"):
                a["mp"] = 1
            alias.append(a)
    for f in syn.get("families") or []:
        hits = Q8._hit_re(ss, f["re"])
        if not hits:
            unresolved.append({"canon": f["canon"], "reason": "no member of this family is on this page"})
            continue
        ii = slots(hits)
        for q, d, k in Q8._forms(f, "syn"):
            a = {"q": q, "d": d, "k": k, "c": f["canon"], "i": ii, "s": f.get("src", ""),
                 "r": "Q306", "fam": 1}
            if f.get("note"):
                a["n"] = f["note"]
            alias.append(a)
        if f.get("group_like"):
            groups.append({"id": "fam6_" + P.fold(f["canon"]).replace(" ", "_"), "name": f["canon"],
                           "src": f.get("src", ""), "i": ii,
                           "al": sorted({q for q, _, _ in Q8._forms(f, "syn")}),
                           "inferred": 0, "why": f.get("note") or "", "from": "synonyms_q306"})

    # ---------------------------------------------------------------- THE CORE FIX: every group the page carries
    have = {g["id"] for g in groups}
    rel = DERIVED / f"Q298_relations_{key}.json"
    if rel.exists():
        r = _load(rel)
        for fg in r["fgroups"]:
            if fg["id"] in have:
                continue
            idxs = [by_id[r["ids"][i]] for i in fg.get("i", []) if r["ids"][i] in by_id]
            if not idxs:
                continue
            groups.append({"id": fg["id"], "name": fg["name"], "src": fg["src"], "i": slots(idxs),
                           "al": [], "inferred": fg.get("inferred", 0), "why": fg.get("why", ""),
                           "from": "relations_q298"})
            have.add(fg["id"])
    # ---------------------------------------------------------------- the 18 NEW cited groups
    for ng in newg["groups"]:
        if ng["id"] in have:
            continue
        hits = Q8._hit_targets(ix, ng["members"])
        if not hits:
            unresolved.append({"canon": ng["id"], "reason": "no member of this new group is on this page"})
            continue
        groups.append({"id": ng["id"], "name": ng["name"], "src": ng["src"], "i": slots(hits),
                       "al": sorted({P.fold(x) for x in ng["syn"] + ng["he"] + [ng["name"], ng["he_name"]]
                                     if P.fold(x)}),
                       "inferred": 0, "why": ng["note"], "contested": ng["contested"],
                       "contested_why": ng["contested_why"], "off_page": ng["not_on_any_page"],
                       "from": "muscle_groups_q306"})
        have.add(ng["id"])
    # ---------------------------------------------------------------- the group NAMES (87 + 6)
    named = {x["id"]: x for x in gnm["action_groups"] + gnm["extra_groups"]}
    for g in groups:
        nr = named.get(g["id"])
        if not nr:
            continue
        al = set(g.get("al") or [])
        for x in nr["syn"] + nr["he"]:
            q = P.fold(x)
            if q:
                al.add(q)
        g["al"] = sorted(al)
        if nr["label"] != g.get("name"):
            g["name_was"] = g.get("name")
            g["name"] = nr["label"]
        g["names_src"] = "Q306"
        g["name_inferred"] = nr["inferred"]
        if nr.get("note"):
            g["name_note"] = nr["note"]

    # ---------------------------------------------------------------- the concept layer
    concepts = []
    gids = {g["id"] for g in groups}
    for c in con["concepts"]:
        hits = Q8._hit_targets(ix, c["offer_structures"])
        og = [x for x in c["offer_groups"] if x in gids]
        if not hits and not og:
            unresolved.append({"canon": c["id"], "reason": "this concept offers nothing on this page"})
            continue
        ii = slots(hits)
        row = {"id": c["id"], "label": c["label"], "he": c["he_label"], "kind": c["kind"],
               "body": c["body"], "i": ii, "g": og, "sim": c["sim"], "note": c["note"],
               "inferred": c["inferred"],
               "claims": [{"t": x["text"], "s": con["sources"].get(x["src"], x["src"])} for x in c["claims"]],
               "al": sorted({P.fold(x) for x in c["syn"] + c["he"] + [c["label"], c["he_label"]] if P.fold(x)})}
        concepts.append(row)
        for d in c["syn"] + c["he"] + [c["label"]]:
            q = P.fold(d)
            if q:
                alias.append({"q": q, "d": d, "k": "concept", "c": c["label"], "i": ii,
                              "s": "Q306", "r": "Q306", "cc": c["id"]})

    # ---------------------------------------------------------------- honest explanations
    for e in syn["cited_but_not_shipped"]:
        hits = Q8._hit_targets(ix, [e["name"]] + (e.get("syn") or []) + (e.get("shipped_as") or []))
        if hits:
            # Q311: the structure DOES ship on this page — add its aliases so it is searchable
            ii = slots(hits)
            for q, d, k in Q8._forms(e, "syn"):
                alias.append({"q": q, "d": d, "k": k, "c": e.get("canon", e["name"]),
                               "i": ii, "s": e.get("src", ""), "r": "Q311"})
            continue
        offer = slots(Q8._hit_targets(ix, e.get("offer") or []))
        nshp.append({"q": sorted({P.fold(x) for x in [e["name"], e["canon"]] + (e.get("syn") or [])
                                  + (e.get("he") or []) if P.fold(x)}),
                     "name": e["name"], "canon": e["canon"], "why": e["why"], "s": e.get("src", ""),
                     "offer": offer, "r": "Q306"})

    aliased = {ids[i] for a in alias for i in a.get("i", [])}
    he = {ids[i] for a in alias if a.get("k") == "he" for i in a.get("i", [])}
    out = dict(base)
    out.update({"schema": "nmsk.search.v2", "round": "Q306", "key": key, "src": str(src),
                "doc": "Q298's table for this page, extended by scripts/anatomy/q306/build_search_q306.py "
                       "from data/anatomy/{synonyms,groups,concepts,muscle_groups}_q306.json. A superset: "
                       "every Q298 row is still here, unchanged. `alias[].i`, `groups[].i` and "
                       "`concepts[].i` index `ids`.",
                "ids": ids, "sub": sub, "alias": alias, "groups": groups, "concepts": concepts,
                "not_shipped": nshp, "unresolved_q306": unresolved,
                "counts": {"structures": len(ss), "alias_forms": len(alias),
                           "aliased_structures": len(aliased), "he_structures": len(he),
                           "abbr_forms": sum(1 for a in alias if a["k"] == "abbr"),
                           "he_forms": sum(1 for a in alias if a["k"] == "he"),
                           "concept_forms": sum(1 for a in alias if a["k"] == "concept"),
                           "groups": len(groups), "concepts": len(concepts),
                           "not_shipped": len(nshp), "unresolved": len(unresolved)}})
    return out


def _z(obj):
    return base64.b64encode(zlib.compress(
        json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)).decode("ascii")


def block_for(key: str) -> str:
    s = _load(DERIVED / f"Q306_search_{key}.json")
    payload = {"v": 1, "key": key, "ids": s["ids"], "sub": s["sub"], "alias": s["alias"],
               "groups": s["groups"], "ns": s["not_shipped"], "concepts": s["concepts"]}
    return BEGIN + '<script type="application/json" id="nmsk-q306">' + \
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "</script>" + END


def inject(d: Path):
    key = P.DIRKEY.get(d.name)
    if key is None:
        raise SystemExit(f"unknown page dir {d}")
    block = block_for(key)
    n = 0
    for h in sorted(d.glob("*.html")):
        s = h.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            continue
        i, k = s.index(BEGIN), s.index(END) + len(END)
        h.write_text(s[:i] + block + s[k:], encoding="utf-8")
        print(f"q306: {h} {len(block) / 1024:.0f} KB")
        n += 1
    if not n:
        raise SystemExit(f"no page with the NMSK-Q306 markers in {d}")


def main(argv):
    if argv and argv[0] == "--inject":
        for a in argv[1:]:
            inject(Path(a))
        return 0
    src = P._baseline()
    if "--src" in argv:
        i = argv.index("--src")
        src = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    DERIVED.mkdir(parents=True, exist_ok=True)
    for key in (argv or P.KEYS):
        out = compile_page(key, src)
        (DERIVED / f"Q306_search_{key}.json").write_text(
            json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        c = out["counts"]
        print("%-8s alias %5d  structures reached %4d  Hebrew %4d  groups %4d  concepts %3d  "
              "explanations %3d  unresolved %3d"
              % (key, c["alias_forms"], c["aliased_structures"], c["he_structures"], c["groups"],
                 c["concepts"], c["not_shipped"], c["unresolved"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
