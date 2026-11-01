#!/usr/bin/env python3
"""Q298 "Related" and "Functional group": build both from the data this project already holds, per page.

Sources are the project's own cited data -- the page's nmsk-learn block (Q283 actions, origin / insertion bone ids, nerves,
heads), data/anatomy/muscle_heads_q293.json, each structure's own card record (`nerve`, `supplies`, `part_of_id`),
data/anatomy/muscle_groups_q283.json and data/derived/Q256_plexus_groups.json. The mapping rules -- what counts as a joint
structure, which naming patterns mark a tendon or a bursa, and the few functional groups the textbook table does not carry --
are in data/anatomy/relations_q298.json, each with its own `inferred` flag. Nothing here invents an anatomical fact: a link is
either read out of a cited field (inferred 0, and the UI shows that field's source) or produced by a stated rule
(inferred 1, and the UI says "inferred").

    python3 scripts/anatomy/q298/relations_q298.py [KEY...] [--src build/q297]
-> data/derived/Q298_relations_<key>.json {ids, kinds, rel, fgroups, fg, counts}
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pagedata as P  # noqa: E402

REPO = P.REPO
RULES = REPO / "data/anatomy/relations_q298.json"
GROUPS = REPO / "data/anatomy/muscle_groups_q283.json"
HEADS = REPO / "data/anatomy/muscle_heads_q293.json"
SYN = REPO / "data/anatomy/synonyms_q298.json"
DERIVED = REPO / "data/derived"


def build(key, src):
    R = json.loads(RULES.read_text(encoding="utf-8"))
    MG = json.loads(GROUPS.read_text(encoding="utf-8"))
    HD = json.loads(HEADS.read_text(encoding="utf-8"))
    SY = json.loads(SYN.read_text(encoding="utf-8"))
    ss = P.structures(key, src)
    ids = [s["id"] for s in ss]
    n = len(ss)
    nm = [P.fold(s["name"]) for s in ss]
    bare = [P.fold(P.strip_parens(s["name"])) for s in ss]
    cat = [s["cat"] for s in ss]
    side = [s["side"] for s in ss]
    byname = {}
    for i, s in enumerate(ss):
        for k in P.keys_of(s["name"]):
            byname.setdefault(k, []).append(i)
    byid = {}                                        # the page's OWN ids, and the id without its side suffix
    for i, s in enumerate(ss):
        sid = s["id"]
        for k in {sid, re.sub(r"_(r|l)$", "", sid), re.sub(r"^zan_", "", sid),
                  re.sub(r"_(r|l)$", "", re.sub(r"^zan_", "", sid))}:
            byid.setdefault(k, []).append(i)
    L = P.learn(key, src) or {"m": {}}
    M = L.get("m") or {}

    rel = {}

    def link(a, b, kind):
        if a == b or not (0 <= a < n) or not (0 <= b < n):
            return
        if side[a] and side[b] and side[a] != side[b] and side[a] in "lr" and side[b] in "lr":
            return                                    # a left structure's relations are the left ones
        rel.setdefault(a, {}).setdefault(kind, set()).add(b)

    # ---- which page structures carry each learn muscle (base id -> indices), by name, per side
    mindex = {}
    for b, m in M.items():
        hits = []
        for t in (m.get("n") or b.replace("_", " "), b.replace("_", " ")):
            for i in byname.get(P.fold(t), []) + byname.get(P.fold(t) + " muscle", []):
                if i not in hits:
                    hits.append(i)
        for i in byid.get(b, []):
            if i not in hits:
                hits.append(i)
        rx = re.compile(r"\b(head|part) of " + re.escape(P.fold(m.get("n") or b.replace("_", " "))) + r"( muscle)?$")
        for i in range(n):
            if rx.search(nm[i]) or rx.search(bare[i]):
                if i not in hits:
                    hits.append(i)
        if hits:
            mindex[b] = hits

    # ---- (1) head / part: what the page itself declares, plus the "<x> head of <muscle>" meshes of one muscle
    for i, s in enumerate(ss):
        pid = s["part_of_id"]
        if pid:
            for j in byname.get(P.fold(pid.replace("_", " ")), []):
                link(i, j, "head"); link(j, i, "head")
        if s["part_of"]:
            for j in byname.get(P.fold(s["part_of"]), []) + byname.get(P.fold(s["part_of"]) + " muscle", []):
                link(i, j, "head"); link(j, i, "head")
    for b, hits in mindex.items():
        parts = [i for i in hits if re.search(r"\b(head|part) of \b", nm[i]) or ss[i]["part_of_id"] or ss[i]["part_of"]]
        whole = [i for i in hits if i not in parts]
        fam = parts + whole
        if b in HD.get("m", {}) or len(parts) > 1:
            for a in fam:
                for c in fam:
                    link(a, c, "head")

    # ---- (2) tendon / aponeurosis / sheath and (3) bursa, by this project's own naming
    TEND = ("tendon", "aponeurosis", "sheath")
    for b, hits in mindex.items():
        base = P.fold(M[b].get("n") or b.replace("_", " "))
        for i in range(n):
            t = nm[i]
            if base and base in t and i not in hits:
                if any(w in t for w in TEND):
                    for j in hits:
                        link(j, i, "tendon"); link(i, j, "tendon")
                elif "bursa" in t or cat[i] == "bursa":
                    for j in hits:
                        link(j, i, "bursa"); link(i, j, "bursa")

    # ---- (4) nerve supply: the muscle's own cited nerve names -> this page's nerve meshes
    nerves = [i for i in range(n) if cat[i] == "nerve"]
    for b, hits in mindex.items():
        want = set()
        for x in (M[b].get("nv") or []):
            want.add(P.fold(x).replace(" n ", " nerve ").strip())
            want.add(P.fold(x))
        for i in hits:
            for x in (ss[i]["rec"].get("nerve") or []):
                want.add(P.fold(x))
        want = {w for w in want if len(w) > 3}
        for i in nerves:
            t = nm[i].replace(" n ", " nerve ")
            for w in want:
                w2 = w.replace(" n ", " nerve ")
                if w2 and (w2 in t or t.startswith(w2)):
                    for j in hits:
                        link(j, i, "nerve"); link(i, j, "nerve")
                    break

    # ---- (5) artery: read from the ARTERY's own cited `supplies` field
    for i, s in enumerate(ss):
        sup = s["rec"].get("supplies") or []
        if not sup:
            continue
        for x in sup:
            for j in byname.get(P.fold(x), []) + byname.get(P.fold(x) + " muscle", []):
                link(j, i, "artery"); link(i, j, "artery")

    # ---- (6) attachment bones, from the cited origin / insertion bone ids
    for b, hits in mindex.items():
        for fld in ("o", "in"):
            for x in (M[b].get(fld) or []):
                if not isinstance(x, str) or " " in x.strip() and not x.endswith(("_r", "_l")):
                    pass
                cands = byid.get(x, []) + byname.get(P.fold(x.replace("_", " ")), [])
                for j in cands:
                    if cat[j] in ("bone", "skeleton", "cartilage", "joint"):
                        for i in hits:
                            link(i, j, "attach"); link(j, i, "attach")

    # ---- (7) joints the muscle crosses (cited) -> that joint's page structures (a rule of this file)
    JS = R["joint_structures"]
    FJ = R["finger_joint_re"]
    jcache = {}

    def joint_hits(jkey):
        if jkey in jcache:
            return jcache[jkey]
        pats = []
        if jkey in JS:
            pats = JS[jkey]["re"]
        else:
            for suf, ps in FJ.items():
                if suf != "doc" and jkey.endswith("_" + suf):
                    pats = ps
                    break
        out = []
        for p in pats:
            rx = re.compile(p)
            out += [i for i in range(n) if rx.search(nm[i]) and i not in out]
        jcache[jkey] = out
        return out

    for b, hits in mindex.items():
        js = set()
        for row in (M[b].get("mv") or []):
            for mv in row["mv"]:
                for j in (mv[0] if isinstance(mv[0], list) else [mv[0]]):
                    js.add(j)
        for j in js:
            for k in joint_hits(j):
                for i in hits:
                    link(i, k, "joint"); link(k, i, "joint")

    # ---- (8) antagonists: opposite sign at the same joint and degree of freedom (a stated rule over cited actions)
    mot = {}
    for b, m in M.items():
        for row in (m.get("mv") or []):
            for mv in row["mv"]:
                for j in (mv[0] if isinstance(mv[0], list) else [mv[0]]):
                    mot.setdefault((j, mv[1], int(mv[2]) > 0), set()).add(b)
    for (j, dof, pos), bs in mot.items():
        other = mot.get((j, dof, not pos)) or set()
        for b in bs:
            for c in other:
                if b == c:
                    continue
                for i in mindex.get(b, []):
                    for k in mindex.get(c, []):
                        link(i, k, "antagonist")

    # ---- (9) explicit cited links for the fasciae / tendons / retinacula the muscle table does not cover
    for ex in R.get("related_extra") or []:
        srcs = []
        for t in ex["for"]:
            srcs += [i for i in byname.get(P.fold(t), []) + byname.get(P.fold(t) + " muscle", []) if i not in srcs]
        tgts = []
        for t in ex["targets"]:
            tgts += [i for i in byname.get(P.fold(t), []) + byname.get(P.fold(t) + " muscle", []) if i not in tgts]
        for i in srcs:
            for j in tgts:
                link(i, j, ex["kind"]); link(j, i, ex["kind"])

    # ---- functional groups: the named textbook groups, the action groups, and this file's extensions
    fgroups, fg = [], {}

    def addgroup(gid, name, srck, inferred, why, hits):
        hits = sorted(set(hits))
        if len(hits) < 2:
            return None
        gi = len(fgroups)
        fgroups.append({"id": gid, "name": name, "src": srck, "inferred": inferred, "why": why, "i": hits})
        for i in hits:
            fg.setdefault(i, []).append(gi)
        return gi

    mt = {g["group"]: (g.get("member_targets") or {}) for g in SY["groups"]}
    for g in MG["groups"]:
        hits = []
        for base in g["members"]:
            tg = (mt.get(g["id"]) or {}).get(base) or [base.replace("_", " ")]
            for t in tg:
                hits += [i for i in byname.get(P.fold(t), []) + byname.get(P.fold(t) + " muscle", []) if i not in hits]
            for i in mindex.get(base, []):
                if i not in hits:
                    hits.append(i)
        addgroup(g["id"], g["name"], MG["source"], 0,
                 "Named textbook group; membership verbatim from data/anatomy/muscle_groups_q283.json.", hits)

    DOF = R["dof_names"]
    for (j, dof, pos), bs in sorted(mot.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        hits = [i for b in bs for i in mindex.get(b, [])]
        jn = (JS.get(j) or {}).get("name") or j.replace("_", " ")
        d = DOF.get(dof, dof)
        word = d.split(" / ")[0] if pos else (d.split(" / ")[1] if " / " in d else "the opposite of " + d)
        addgroup(f"act_{j}_{dof}_{'p' if pos else 'n'}",
                 f"{word.strip().capitalize()} at the {jn}", MG.get("source", ""), 0,
                 "Every muscle on this page whose own cited action record includes this motion at this joint "
                 "(data/anatomy/muscle_actions_q283.json; the action text is quoted verbatim from the muscle's own record).",
                 hits)

    for fe in R["functional_extra"]:
        hits = []
        for t in fe["members"]:
            hits += [i for i in byname.get(P.fold(t), []) + byname.get(P.fold(t) + " muscle", []) if i not in hits]
        gi = addgroup(fe["id"], fe["name"], fe["src"], fe["inferred"], fe["why"], hits)
        if gi is not None:
            for t in fe["for"]:
                for i in byname.get(P.fold(t), []):
                    if gi not in fg.setdefault(i, []):
                        fg[i].append(gi)

    out_rel = {}
    links = 0
    for i, d in rel.items():
        rows = []
        for kind, s in d.items():
            for j in sorted(s):
                rows.append([j, kind])
        if rows:
            out_rel[str(i)] = sorted(rows, key=lambda r: (r[1], r[0]))
            links += len(rows)
    by_kind = {}
    for rows in out_rel.values():
        for _, k in rows:
            by_kind[k] = by_kind.get(k, 0) + 1
    return {"schema": "nmsk.relations.v1", "round": "Q298", "key": key, "src": str(src),
            "doc": "Per-page related structures and functional groups, built by scripts/anatomy/q298/relations_q298.py "
                   "from this project's own cited data and the rules in data/anatomy/relations_q298.json. "
                   "`rel` maps a structure index to [[target index, kind]]; `fg` maps it to indices into `fgroups`.",
            "ids": ids, "kinds": R["kinds"], "rel": out_rel, "fgroups": fgroups,
            "fg": {str(k): v for k, v in sorted(fg.items())},
            "counts": {"structures": n, "with_relations": len(out_rel), "links": links, "by_kind": by_kind,
                       "fgroups": len(fgroups), "structures_with_a_group": len(fg)}}


def main(argv):
    src = "build/q297"
    if "--src" in argv:
        i = argv.index("--src"); src = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    DERIVED.mkdir(parents=True, exist_ok=True)
    for key in (argv or P.KEYS):
        out = build(key, src)
        p = DERIVED / f"Q298_relations_{key}.json"
        p.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
        c = out["counts"]
        print(f"{key}: {c['links']:,} links on {c['with_relations']} structures {c['by_kind']}; "
              f"{c['fgroups']} functional groups covering {c['structures_with_a_group']} structures "
              f"-> {p.name} ({p.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
