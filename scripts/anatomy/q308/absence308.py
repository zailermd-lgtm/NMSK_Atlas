#!/usr/bin/env python3
"""Q308: does a `cited_but_not_shipped` term really not ship? Checked by PRESENCE on the page, not by searchability.

Q306's guard (`test_cited_but_not_shipped_names_really_are_absent`) asked whether the term RESOLVES through the
compiled alias table. That cannot see a structure that ships under a name the alias table does not connect to the
query -- which is exactly how `pubic symphysis`, `retrocalcaneal bursa` and the `TFCC` came to be DENIED on the
cards while their meshes were on screen (the `ligamenta flava` failure mode of Q306 S0, three more times).

This module checks the page's own structure list -- name, Latin AND id, each normalised -- so a mesh shipping
under its TA synonym is found. It is the function `tests/test_q308.py` and `tests/test_q306.py` both call.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q298"))
import pagedata as pd  # noqa: E402

DEFAULT_SRC = "build/q307"

# TA / clinical synonym -> the name a mesh may ship under. Every pair is a SYNONYMY claim with a source, not a guess.
TA_EQUIV = {
    "pubic symphysis": ["interpubic fibrocartilaginous disc", "discus interpubicus", "interpubic disc",
                        "pubic symphysis", "symphysis pubica"],
    "retrocalcaneal bursa": ["subtendinous calcaneal bursa", "bursa subtendinea calcanei", "bursa tendinis calcanei"],
    "triangular fibrocartilage complex": ["articular disc of distal radio-ulnar joint", "discus articularis",
                                          "dorsal ulnocarpal ligament"],
    "zygapophysial joint": ["zygapophysial joint", "facet joint"],
    "coracoacromial ligament": ["coracoacromial ligament", "ligamentum coracoacromiale"],
    "anterolateral ligament": ["anterolateral ligament"],
    "psoas minor": ["psoas minor", "musculus psoas minor"],
    "nail bed": ["nail bed", "nail matrix", "matrix unguis"],
    "digital pulp": ["digital pulp", "pulpa digiti"],
    "female perineal skin": ["female perineal skin"],
    "fatty layer of the subcutaneous tissue of the abdomen": ["camper's fascia", "fascia of camper"],
    "anterior superior iliac spine": ["anterior superior iliac spine", "spina iliaca anterior superior"],
    "anterior inferior iliac spine": ["anterior inferior iliac spine", "spina iliaca anterior inferior"],
    "posterior superior iliac spine": ["posterior superior iliac spine", "spina iliaca posterior superior"],
    "posterior inferior iliac spine": ["posterior inferior iliac spine", "spina iliaca posterior inferior"],
}


def page_name_index(key: str, src=DEFAULT_SRC) -> dict:
    """{folded name/latin/id -> [structure ids]} for one page. The id is folded too: `zan_dorsal_ulnocarpal_ligament_l`
    folds to the same token string as its name, which is how an id-only mesh is still found."""
    idx: dict = {}
    for s in pd.structures(key, src):
        for tok in (s.get("name") or "", s.get("latin") or "", (s.get("id") or "").replace("_", " ")):
            f = pd.fold(tok)
            if f:
                idx.setdefault(f, []).append(s["id"])
    return idx


def present(term: str, idx: dict) -> list:
    """Structure ids on this page whose name / Latin / id CONTAINS the folded term as a whole-token run."""
    f = pd.fold(term)
    if not f:
        return []
    out = []
    for k, ids in idx.items():
        if f == k or re.search(r"(?:^| )" + re.escape(f) + r"(?:$| )", k):
            out.extend(ids)
    return sorted(set(out))


def audit(src=DEFAULT_SRC) -> dict:
    syn = json.loads((REPO / "data/anatomy/synonyms_q306.json").read_text(encoding="utf-8"))
    idxs = {k: page_name_index(k, src) for k in pd.KEYS}
    rows = []
    for e in syn["cited_but_not_shipped"]:
        terms = [e["name"]] + list(e.get("syn") or [])
        extra = []
        for probe, equivs in TA_EQUIV.items():
            if pd.fold(probe) in pd.fold(e["name"]) or any(pd.fold(probe) == pd.fold(t) for t in terms):
                extra = equivs
                break
        hits = {}
        for k in pd.KEYS:
            h = []
            for t in terms + extra:
                h.extend(present(t, idxs[k]))
            if h:
                hits[k] = sorted(set(h))
        rows.append({"name": e["name"], "terms": terms, "ta_equiv": extra,
                     "present_on": hits, "really_absent": not hits})
    return {"src": str(src), "n": len(rows), "rows": rows,
            "n_wrong": sum(0 if r["really_absent"] else 1 for r in rows)}


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC
    a = audit(src)
    for r in a["rows"]:
        mark = "ABSENT " if r["really_absent"] else "ON PAGE"
        print(f'{mark}  {r["name"]}')
        for k, ids in r["present_on"].items():
            print(f'            {k}: {", ".join(ids)}')
    print(f'\n{a["n_wrong"]} of {a["n"]} cited_but_not_shipped entries are DENYING a structure that ships.')
