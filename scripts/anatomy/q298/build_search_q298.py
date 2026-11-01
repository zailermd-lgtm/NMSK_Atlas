#!/usr/bin/env python3
"""Q298: compile the per-page search layer and inject it into the page.

The owner searched the iliotibial tract as "ITB" and as "iliotibial band" and found nothing. Both engines matched the query as
ONE contiguous substring of ONE field, so neither an abbreviation nor a second name nor a different word order could ever hit.
data/anatomy/synonyms_q298.json is the data layer of the fix; this script RESOLVES it against each page's own structure list at
build time -- nothing is guessed in the browser -- and writes, per page:

    data/derived/Q298_search_<key>.json    {ids, alias[], groups[], not_shipped[], unresolved[], counts}

`--inject DIR` then builds the page's `nmsk-q298` block from that file plus the committed
data/derived/Q298_adjacency_<key>.json and Q298_relations_<key>.json (both zlib+base64 inside the block, like the Q284
moment-arm block) and splices it between the `<!-- NMSK-Q298 begin/end -->` markers. --inject recomputes nothing.

    python3 scripts/anatomy/q298/build_search_q298.py [KEY...]      # resolve + write data/derived/Q298_search_<key>.json
    python3 scripts/anatomy/q298/build_search_q298.py --inject DIR  # fill the page block from the committed data
"""
from __future__ import annotations

import base64
import json
import re
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pagedata as P  # noqa: E402

REPO = P.REPO
SYN = REPO / "data/anatomy/synonyms_q298.json"
GROUPS = REPO / "data/anatomy/muscle_groups_q283.json"
DERIVED = REPO / "data/derived"
BEGIN, END = "<!-- NMSK-Q298 begin -->", "<!-- NMSK-Q298 end -->"
ROMAN = ["", "i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii"]


def _index(key, src):
    """{comparison key -> [structure index]} over both keys of every page name, plus a 'sub-part' weight per structure."""
    ss = P.structures(key, src)
    ix = {}
    sub = []
    for i, s in enumerate(ss):
        for k in P.keys_of(s["name"]):
            ix.setdefault(k, []).append(i)
        nm = P.fold(s["name"])
        sub.append(1 if (s["part_of_id"] or s["part_of"] or "continuation beyond" in nm
                         or re.search(r"\b(head|part) of \b", nm)) else 0)
    return ss, ix, sub


def _hit_targets(ix, targets):
    """Resolve a synonym entry's `targets` against the page's own names, by three explicit rules (no fuzzy matching here):
         R1  the target equals one of the page name's two comparison keys (whole name / name without its parentheses);
         R2  the page name is the target plus the Z-Anatomy " muscle" suffix, or the target is the page name plus it
             (Z-Anatomy calls it "Temporalis muscle", Terminologia and the own pages call it "Temporalis");
         R3  the page name is "<something> head of <target>" / "<something> part of <target>" -- the heads and parts of a
             muscle that this page ships INSTEAD of one whole-muscle mesh (Z-Anatomy splits the deltoid, pectoralis major
             and triceps brachii this way). These resolve, and the page report marks them as sub-parts so the search ranks
             a whole structure above them."""
    out = []
    for t in targets or []:
        t = P.fold(t)
        if not t:
            continue
        cands = list(ix.get(t, [])) + list(ix.get(t + " muscle", []))
        if t.endswith(" muscle"):
            cands += list(ix.get(t[:-7], []))
        rx = re.compile(r"(^|\b)(head|part) of " + re.escape(t) + r"( muscle)?$")
        for k, v in ix.items():
            if rx.search(k):
                cands += v
        for i in cands:
            if i not in out:
                out.append(i)
    return out


def _hit_re(ss, pat):
    rx = re.compile(pat)
    return [i for i, s in enumerate(ss) if rx.search(P.fold(s["name"]))]


def _forms(e, kind_default):
    """[(query form, display form, kind)] for one entry: its abbreviations, synonyms, Hebrew names and its own canon."""
    out = [(P.fold(e["canon"]), e["canon"], "name")]
    for a in e.get("abbr") or []:
        out.append((P.fold(a), a, "abbr"))
    for s in e.get("syn") or []:
        out.append((P.fold(s), s, e.get("kind_hint") or kind_default))
    for h in e.get("he") or []:
        out.append((P.fold(h), h, "he"))
    return [(q, d, k) for q, d, k in out if q]


def compile_page(key, src):
    ss, ix, sub = _index(key, src)
    pos = {s["id"]: i for i, s in enumerate(ss)}
    syn = json.loads(SYN.read_text(encoding="utf-8"))
    mg = {g["id"]: g for g in json.loads(GROUPS.read_text(encoding="utf-8"))["groups"]}
    ids, idx_of = [], {}

    def slot(i):
        sid = ss[i]["id"]
        if sid not in idx_of:
            idx_of[sid] = len(ids)
            ids.append(sid)
        return idx_of[sid]

    alias, unresolved = [], []

    def add(forms, hits, canon, srck, note, extra=None):
        if not hits:
            return False
        slots = sorted(slot(i) for i in hits)
        for q, d, k in forms:
            a = {"q": q, "d": d, "k": k, "c": canon, "i": slots, "s": srck}
            if note:
                a["n"] = note
            if extra:
                a.update(extra)
            alias.append(a)
        return True

    for e in syn["entries"]:
        hits = _hit_targets(ix, e.get("targets") or [e["canon"]])
        if e.get("re"):
            hits += [i for i in _hit_re(ss, e["re"]) if i not in hits]
        extra = {"amb": 1} if e.get("ambiguous") else None
        if not add(_forms(e, "syn"), hits, e["canon"], e.get("src", ""), e.get("note"), extra):
            unresolved.append({"canon": e["canon"], "targets": e.get("targets") or [e["canon"]],
                               "abbr": e.get("abbr") or [], "reason": "no structure with this name on this page"})

    for r in syn["cn"]["rows"]:
        hits = _hit_re(ss, r["re"])
        rom = ROMAN[r["n"]]
        forms = _forms({"canon": r["canon"], "syn": r.get("syn"), "he": r.get("he")}, "syn")
        forms += [(f"cn {rom}", f"CN {rom.upper()}", "abbr"), (f"cn {r['n']}", f"CN {r['n']}", "abbr"),
                  (f"cranial nerve {rom}", f"cranial nerve {rom.upper()}", "syn"),
                  (f"cranial nerve {r['n']}", f"cranial nerve {r['n']}", "syn")]
        if not add(forms, hits, r["canon"], syn["cn"]["src"], None):
            unresolved.append({"canon": r["canon"], "targets": [r["re"]], "abbr": [f"CN {rom.upper()}"],
                               "reason": "this cranial nerve is not a mesh on this page"})

    fam = []
    for f in syn["families"]:
        hits = _hit_re(ss, f["re"])
        if add(_forms(f, "syn"), hits, f["canon"], f.get("src", ""), f.get("note")):
            if f.get("group_like"):
                fam.append({"id": "fam_" + P.fold(f["canon"]).replace(" ", "_"), "name": f["canon"],
                            "src": f.get("src", ""), "i": sorted(slot(i) for i in hits),
                            "al": sorted({q for q, _, _ in _forms(f, "syn")}), "inferred": 0,
                            "why": f.get("note") or ""})
        else:
            unresolved.append({"canon": f["canon"], "targets": [f["re"]], "abbr": f.get("abbr") or [],
                               "reason": "no member of this family is a mesh on this page"})

    groups = []
    for g in syn["groups"]:
        src_g = mg.get(g["group"])
        if not src_g:
            continue
        hits = []
        mt = g.get("member_targets") or {}
        for base in src_g["members"]:
            tg = mt.get(base) or [base.replace("_", " ")]
            hits += [i for i in _hit_targets(ix, tg) if i not in hits]
        forms = [(P.fold(src_g["name"]), src_g["name"], "name")]
        if src_g.get("ta"):
            forms.append((P.fold(src_g["ta"]), src_g["ta"], "syn"))
        forms += [(P.fold(x), x, "abbr") for x in (g.get("abbr") or [])]
        forms += [(P.fold(x), x, "syn") for x in (g.get("syn") or [])]
        forms += [(P.fold(x), x, "he") for x in (g.get("he") or [])]
        forms = [(q, d, k) for q, d, k in forms if q]
        if hits:
            groups.append({"id": g["group"], "name": src_g["name"], "src": g.get("src", ""),
                           "i": sorted(slot(i) for i in hits), "al": sorted({q for q, _, _ in forms}),
                           "inferred": 0,
                           "why": "Named textbook group; membership verbatim from data/anatomy/muscle_groups_q283.json "
                                  "(" + json.loads(GROUPS.read_text(encoding="utf-8"))["source"] + ")"})
            add(forms, hits, src_g["name"], g.get("src", ""), None, {"g": g["group"]})
        else:
            unresolved.append({"canon": src_g["name"], "targets": src_g["members"], "abbr": g.get("abbr") or [],
                               "reason": "no member of this named group is a mesh on this page"})
    groups += fam

    ns = []
    for e in syn["cited_but_not_shipped"]:
        forms = sorted({P.fold(x) for x in ([e["name"], e["canon"]] + (e.get("syn") or []) + (e.get("he") or [])) if P.fold(x)})
        ns.append({"q": forms, "name": e["name"], "canon": e["canon"], "why": e["why"], "s": e.get("src", "")})

    out = {"schema": "nmsk.search.v1", "round": "Q298", "key": key, "src": str(src),
           "doc": "Resolved at build time by scripts/anatomy/q298/build_search_q298.py from data/anatomy/synonyms_q298.json "
                  "against this page's own structure list. `alias[].i` and `groups[].i` index `ids`.",
           "ids": ids, "sub": [sub[pos[sid]] for sid in ids],
           "alias": alias, "groups": groups, "not_shipped": ns, "unresolved": unresolved,
           "counts": {"structures": len(ss), "alias_forms": len(alias), "aliased_structures": len(ids),
                      "abbr_forms": sum(1 for a in alias if a["k"] == "abbr"),
                      "he_forms": sum(1 for a in alias if a["k"] == "he"),
                      "syn_forms": sum(1 for a in alias if a["k"] in ("syn", "eponym")),
                      "groups": len(groups), "unresolved": len(unresolved)}}
    return out


def _z(obj):
    return base64.b64encode(zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)).decode("ascii")


def block_for(key):
    s = json.loads((DERIVED / f"Q298_search_{key}.json").read_text(encoding="utf-8"))
    payload = {"v": 1, "key": key, "ids": s["ids"], "sub": s["sub"], "alias": s["alias"], "groups": s["groups"],
               "ns": s["not_shipped"]}
    ap = DERIVED / f"Q298_adjacency_{key}.json"
    if ap.exists():
        a = json.loads(ap.read_text(encoding="utf-8"))
        payload["adj"] = {"th": a["threshold_mm"], "cell": a["cell_mm"], "n": a["pairs"], "how": a["how"],
                          "z": _z({"ids": a["ids"], "adj": a["adj"]})}
    rp = DERIVED / f"Q298_relations_{key}.json"
    if rp.exists():
        r = json.loads(rp.read_text(encoding="utf-8"))
        payload["rel"] = {"kinds": r["kinds"], "n": r["counts"]["links"], "g": r["counts"]["fgroups"],
                          "z": _z({"ids": r["ids"], "rel": r["rel"], "fgroups": r["fgroups"], "fg": r["fg"]})}
    return BEGIN + '<script type="application/json" id="nmsk-q298">' + \
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
        print(f"q298: {h} {len(block) / 1024:.0f} KB")
        n += 1
    if not n:
        raise SystemExit(f"no page with the NMSK-Q298 markers in {d}")


def main(argv):
    if argv and argv[0] == "--inject":
        for a in argv[1:]:
            inject(Path(a))
        return 0
    src = "build/q297"
    if "--src" in argv:
        i = argv.index("--src")
        src = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    DERIVED.mkdir(parents=True, exist_ok=True)
    for key in (argv or P.KEYS):
        out = compile_page(key, src)
        p = DERIVED / f"Q298_search_{key}.json"
        p.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
        c = out["counts"]
        print(f"{key}: {c['alias_forms']} alias forms ({c['abbr_forms']} abbr, {c['syn_forms']} syn, {c['he_forms']} he) "
              f"-> {c['aliased_structures']} structures, {c['groups']} groups, {c['unresolved']} unresolved -> {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
