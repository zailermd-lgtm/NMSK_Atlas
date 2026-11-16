#!/usr/bin/env python3
"""Q343: the per-page sidecar `groups_q342.json` for the name card's "Related structures" families (Myofascial lines,
Innervation) and its Parts chooser -- public anatomy layer, committed data only, nothing recomputed.

Reads the three Q342 data files (data/anatomy/myofascial_lines_q342.json, innervation_groups_q342.json,
muscle_parts_q342.json; contract in docs/Q342_groups_sources.md) and keeps only what the page needs: structure ids that
exist on THIS page (read from the page's own embedded manifest), short labels, and sources as a short label + DOI / PMID
(no titles). The private clinical layer is never read. The page fetches the file lazily on the first name-card open
(viewer/groups342/groups342.js).

    python3 scripts/anatomy/q342/build_sidecar_q342.py base_m build/q309/viewer_zan_atlas    # writes <dir>/groups_q342.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DA = REPO / "data" / "anatomy"
LINES, INN, PARTS = DA / "myofascial_lines_q342.json", DA / "innervation_groups_q342.json", DA / "muscle_parts_q342.json"
Q322 = DA / "innervation_q322.json"
NAME = "groups_q342.json"
PAGES = ("base_m", "base_f")
MAN_RE = re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)
# never in the public layer: the public-template ban list + treatment vocabulary (as the Q322 sidecar)
BAN = re.compile(r"ultrasound|hounsfield|t1_se|imaging_tissues|tissue table|nmskultrasound|acoustic|mrayl|b-mode|inject|botul|toxin|needle|"
                 r"bont|\bdose|motor.point|sonograph|scripts/", re.I)
BOOK = {"myers_at": "Myers, Anatomy Trains (book; route recorded without opening it)",
        "schultz1996": "Schultz & Feitis 1996, The Endless Web (book; contents page only)",
        "brunnstrom1970": "Brunnstrom 1970 (book; not opened)",
        "gray42": "Gray's Anatomy, 42nd ed. (textbook; page not checked)"}
REPO_LABEL = "This project's anatomy records (textbook-based)"
EV = {"strong": "strong evidence", "moderate": "moderate evidence", "none": "no evidence", "not_examined": "not examined by any review"}
TIER = {"named_in_guide": "named by the source", "guide_section_and_action": "in the source's section + matching action",
        "action_only": "matching action only (not named by the source)", "guide_section_only": "in the source's section, no recorded action"}
PART_WHY = {"rule": "no separate mesh on this body", "not_delimitable": "not delimitable from the sources",
            "missing_on_page": "not on this page"}


def page_html(d: Path) -> Path:
    hs = sorted(p for p in d.glob("atlas_viewer*.html"))
    if not hs:
        raise SystemExit(f"{d}: no atlas_viewer*.html")
    return hs[0]


def page_ids(d: Path) -> set[str]:
    m = MAN_RE.search(page_html(d).read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"{d}: no embedded manifest")
    return {x["id"] for x in json.loads(m.group(1))["meshes"]}


def short_label(key: str, ref: dict) -> str:
    if key in BOOK:
        return BOOK[key]
    if key.startswith(("repo", "q2", "q3")):
        return REPO_LABEL
    c = ref.get("citation") or ""
    first = re.split(r",| et al|\.", c, maxsplit=1)[0].strip()
    first = re.sub(r"\s+[A-Z]{1,3}$", "", first)
    yr = re.search(r"(19|20)\d{2}", key) or re.search(r"\b(19|20)\d{2}\b", c)
    return f"{first} et al." + (f" {yr.group(0)}" if yr else "")


class Ctx:
    def __init__(self, page: str, ids: set[str]):
        self.page, self.ids, self.used = page, ids, set()

    def sides(self, s) -> dict:
        """{r,l,mid} of a {base_m|base_f: {r,l,mid}} block, page ids only; empty lists dropped."""
        blk = (s or {}).get(self.page) or {}
        out = {}
        for k in ("r", "l", "mid"):
            v = [i for i in blk.get(k, []) if i in self.ids]
            if v:
                out[k] = v
        return out

    def refs(self, keys):
        keys = [k for k in (keys or []) if k]
        self.used.update(keys)
        return keys


def build_lines(C: Ctx) -> dict:
    d = json.loads(LINES.read_text(encoding="utf-8"))
    cls = []
    for k in ("vertical", "diagonal_spiral", "arm", "functional", "horizontal"):
        sc = d["sub_choices"][k]
        e = {"k": k, "label": {"vertical": "Vertical (longitudinal)", "diagonal_spiral": "Diagonal / spiral", "arm": "Arm lines",
                               "functional": "Functional lines", "horizontal": "Horizontal"}[k]}
        if sc.get("status") == "not_offered":
            e["off"] = True
            e["why"] = ("No horizontal line exists among Myers' lines or in the dissection reviews opened. The only sourced "
                        "horizontal idea (Schultz & Feitis' body bands) comes without a list of structures, so nothing can be shown.")
            e["refs"] = C.refs(sc.get("refs"))
        cls.append(e)
    items = []
    for ln in d["lines"]:
        st = []
        for s in ln["stations"]:
            x = {"n": s["station"], "k": s["kind"], "s": s["side"]}
            x.update(C.sides(s.get("structures")))
            st.append(x)
        ev = ln["evidence"]
        w = ev.get("wilke2016") or {}
        how = []
        if isinstance(w, dict) and w.get("examined"):
            how.append(f"Wilke et al. 2016 systematic review: {w.get('transitions_verified')} of {w.get('transitions_total')} transitions "
                       f"verified in dissection ({w.get('studies')} studies).")
        elif isinstance(w, dict) and w:
            how.append("Wilke et al. 2016 systematic review: not examined.")
        if ev.get("krause2016"):
            how.append("Krause et al. 2016 (force transfer): " + str(ev["krause2016"]) + ".")
        items.append({"id": ln["id"], "abbr": ln.get("abbr"), "name": ln["name"] if not ln["id"].startswith("wilke2019") or "Wilke" in ln["name"] else
                      ln["name"] + " (Wilke & Krause 2019)", "cls": ln["sub_choices"], "ev": ev["label"], "evt": ev.get("label_text"),
                      "how": " ".join(how), "refs": C.refs(ev.get("refs", []) + ln.get("composition_refs", [])),
                      "book": bool(ln.get("verify_against_book")), "x": bool(ln.get("crosses_midline")), "st": st})
    return {"contested": d["doc"]["contested"], "ev": EV, "cls": cls, "items": items}


def build_inn(C: Ctx):
    d = json.loads(INN.read_text(encoding="utf-8"))
    q = json.loads(Q322.read_text(encoding="utf-8"))
    M = {}
    for mid, m in d["muscles"].items():
        sd = C.sides(m.get("structures"))
        if not sd:
            continue
        M[mid] = {"n": m["name"], **sd, "lv": m.get("motor_levels") or [], "cn": m.get("cranial_nerves") or [],
                  "nv": m.get("nerves") or [], "rt": m.get("roots_text"), "src": C.refs(m.get("sources"))}
    F = d["families"]
    levels = []
    for lv, v in F["root"]["levels"].items():
        mem = [x["muscle_id"] for x in v["members"] if x["muscle_id"] in M]
        if not mem:
            continue
        e = {"lv": lv, "m": mem}
        k = v.get("isncsci_key_muscles")
        if k:
            e["key"] = {"f": k["function"], "m": [x for x in k["members"] if x in M]}
            C.refs(["isncsci2019"])
        levels.append(e)
    cranial = []
    for lv, v in F["root"]["cranial"].items():
        mem = [x["muscle_id"] for x in v if x["muscle_id"] in M]
        if mem:
            cranial.append({"lv": lv, "m": mem})
    cranial.sort(key=lambda e: ["CN III", "CN IV", "CN V", "CN VI", "CN VII", "CN IX", "CN X", "CN XI", "CN XII"].index(e["lv"])
                 if e["lv"] in ("CN III", "CN IV", "CN V", "CN VI", "CN VII", "CN IX", "CN X", "CN XI", "CN XII") else 99)
    # nerve -> its meshes on this page: the registry id itself (+ _r / _l), and the nerve meshes the reviewed Q322 record lists
    # for a muscle that this one nerve alone supplies (e.g. the median nerve's muscular branches)
    nmesh: dict[str, set] = {}
    for nid in F["peripheral"]["nerves"]:
        nmesh[nid] = {x for x in (nid, nid + "_r", nid + "_l") if x in C.ids}
    for qm in q["muscles"].values():
        nv = [n["id"] for n in qm.get("nerve", [])]
        if len(nv) == 1 and nv[0] in nmesh:
            nmesh[nv[0]].update(x for x in qm.get("nerve_structures_on_page", {}).get(C.page, []) if x in C.ids)
    nerves = {}
    for nid, n in F["peripheral"]["nerves"].items():
        mem = [[x["muscle_id"], x.get("via")] for x in n.get("all_members", []) if x["muscle_id"] in M]
        ids = sorted(nmesh.get(nid, ()))
        e = {"n": n["name"], "p": n.get("parent"), "rt": n.get("roots"), "m": mem}
        for k in ("r", "l"):
            v = [i for i in ids if i.endswith("_" + k)]
            if v:
                e[k] = v
        v = [i for i in ids if not i.endswith(("_r", "_l"))]
        if v:
            e["mid"] = v
        if mem or ids:
            nerves[nid] = e
    C.refs(["repo_registry"])
    pats = []
    for p in F["central"]["patterns"]:
        if p.get("status") != "ok":
            continue
        mem, seen = [], set()
        for x in p["members"]:
            if x["muscle_id"] not in M or x["muscle_id"] in seen:
                continue
            seen.add(x["muscle_id"])
            e = [x["muscle_id"], x["tier"]]
            if x.get("opposes"):
                e.append(1)
            mem.append(e)
        if not mem:
            continue
        pats.append({"id": p["id"], "n": p["name"], "limb": p["limb"],
                     "comp": [[c["label"], c.get("source")] for c in p["components"]],
                     "miss": p.get("components_not_in_opened_sources") or [], "refs": C.refs(p.get("refs", []) + ["q283_actions"]),
                     "m": mem})
        C.refs([c.get("source") for c in p["components"]])
    rules = {"root": "A muscle is listed under every level of its textbook root range (not only the dominant root).",
             "nerve": "Members of a nerve: muscles whose record names that nerve or one of its branches.",
             "central": "Rule-based from a sourced posture + the muscles' sourced actions: a muscle is a member when one of its "
                        "recorded actions produces one of the posture's joint positions. Tiers say how directly the source supports it."}
    return M, {"levels": levels, "cranial": cranial, "nerves": nerves, "pats": pats, "tiers": TIER, "rules": rules,
               "excluded": F["central"].get("excluded")}


def build_parts(C: Ctx) -> list:
    d = json.loads(PARTS.read_text(encoding="utf-8"))
    out = []
    for m in d["muscles"]:
        if not m["parts"]:
            continue
        whole = C.sides(m.get("whole_muscle_structures")) if m.get("whole_muscle_structures") else {}
        ps = []
        for p in m["parts"]:
            b = p["body"]
            st = b["status"]
            e = {"id": p["id"], "n": p["name"], "st": st}
            if st in ("separate_mesh", "separate_mesh_rule_based"):
                e.update(C.sides(b.get("structures")))
                if not any(k in e for k in ("r", "l", "mid")):
                    e["st"], st = "missing_on_page", "missing_on_page"
            if st not in ("separate_mesh", "separate_mesh_rule_based"):
                e["why"] = PART_WHY.get(st, "no separate mesh on this body")
                if b.get("reason"):
                    e["why2"] = b["reason"]
            if st == "separate_mesh_rule_based":
                e["why"] = "rule-based mesh (built from published measurements, not segmented)"
            if p.get("nerve_supply"):
                e["nerve"] = p["nerve_supply"]
            e["refs"] = C.refs(p.get("refs"))
            ps.append(e)
        if not whole and not any(x["st"].startswith("separate") for x in ps):
            continue
        out.append({"id": m["muscle_id"], "n": m["name"], "whole": whole, "p": ps})
    return out


def build(page: str, page_dir: Path) -> dict:
    C = Ctx(page, page_ids(page_dir))
    lines = build_lines(C)
    M, inn = build_inn(C)
    parts = build_parts(C)
    srcs = {}
    for f in (LINES, INN, PARTS):
        for k, r in json.loads(f.read_text(encoding="utf-8"))["references"].items():
            if k in C.used and k not in srcs:
                e = {"l": short_label(k, r)}
                if r.get("doi"):
                    e["doi"] = r["doi"]
                if r.get("pmid"):
                    e["pmid"] = str(r["pmid"])
                srcs[k] = e
    res = {"schema": "nmsk.groups.page.v1", "round": "Q343", "data": "Q342", "page": page,
           "src": srcs, "m": M, "lines": lines, "inn": inn, "parts": parts}
    txt = json.dumps(res, ensure_ascii=False)
    hit = BAN.search(txt)
    if hit:
        i = hit.start()
        raise SystemExit(f"{page}: public sidecar would carry a banned term {hit.group(0)!r}: ...{txt[max(0, i - 80):i + 40]}...")
    return res


def main() -> int:
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if len(a) != 2 or a[0] not in PAGES:
        print(__doc__)
        return 2
    d = Path(a[1])
    res = build(a[0], d)
    out = d / NAME
    if out.is_symlink():
        out.unlink()
    out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{a[0]}: {out} ({out.stat().st_size // 1024} KB, {len(res['m'])} muscles, {len(res['lines']['items'])} lines, "
          f"{len(res['inn']['nerves'])} nerves, {len(res['inn']['pats'])} patterns, {len(res['parts'])} muscles with parts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
