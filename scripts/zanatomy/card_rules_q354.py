#!/usr/bin/env python3
"""Q354: the name-card rules shared by the Z-Anatomy builder (build_zan_atlas_viewer.py) and the page patch
(patch_manifest_cards_q354.py). Pure functions over names / ids / record dicts; no page or geometry I/O.

1. part_link_ok    a "part of" link may lend the parent's record only to a piece OF that parent: same class (a gyrus never takes a
                   bone's record, a bursa never takes its muscle's), and the child's own name names the parent (the parent itself,
                   "<x> part / head / branches of <parent>", "<parent> <qualifier>", a qualified "<adjective> <parent>") or one of
                   the parent record's own named constituents ("Iliopsoas (iliacus + psoas major)", compartment ids). Bones under a
                   bone group (carpals, ribs, vertebrae, phalanges) keep their group record. The old matcher took any name SUBSTRING
                   ("Middle temporal gyrus" -> temporal bone, "Lacrimal gland" -> lacrimal bone, "Ilio-inguinal nerve" -> inguinal
                   ligament).
2. layer_fix       Z-Anatomy files brain parts, the eye and the middle ear under its Nervous system; the builder's CNS name hints
                   missed nuclei, fasciculi, cerebellar lobules, the lateral-sulcus rami ("Lat_Fis-...") and more, so they drew
                   (and were labelled) as peripheral NERVE.
3. display_name    readable names for raw Z-Anatomy labels (sourced where a source exists, else a mechanical expansion, said so).
4. card text       nerve / target ids -> display names, same-side targets only on a sided structure, build-provenance notes moved
                   out of the card text into rec.build_note (kept in the page data, never rendered).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- 1. part-of links
# child layer (manifest "sys") -> parent atlas categories it may borrow from
SYS_COMPAT = {"bone": {"bone"}, "cartilage": {"cartilage"}, "muscle": {"muscle"}, "nerve": {"nerve"}, "vessel": {"vessel"},
              "lymph": {"lymph"}, "joint": {"ligament", "fascia"}, "fascia": {"fascia", "ligament"}, "ligament": {"ligament"},
              "insertion": {"tendon"}, "bursa": {"bursa"}}
PART_WORDS = {"part", "head", "belly", "portion", "branch", "fibre", "fiber", "division", "segment", "lamina", "layer", "slip"}
_DROP = {"muscle", "musculus", "the", "bone", "nerve", "n", "lymph", "its"}


def _sing(w: str) -> str:
    if len(w) > 4 and w.endswith(("ches", "shes", "xes")):
        return w[:-2]                                                # "branches" -> "branch"
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def words(s: str) -> list[str]:
    s = s.lower()
    s = re.sub(r"\bnerve to\b", " ", s)                       # "Nerve to mylohyoid muscle" == "Mylohyoid nerve"
    s = re.sub(r"\((?:cn\s*)?[ivx]+\)", " ", s)              # "(XI)", "(CN X)"
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return [_sing(w) for w in s.split() if w not in _DROP and _sing(w) not in _DROP]


def _variants(name: str, pid: str) -> list[list[str]]:
    base = name.split(",")[0]
    out = []
    out.append(words(re.sub(r"\([^)]*\)", " ", base)))
    # "Achilles (calcaneal) tendon" -> "calcaneal tendon"; "Deep fibular (peroneal) nerve" -> "deep peroneal nerve"
    for m in re.finditer(r"(\w+)\s*\((\w+)\)", base):
        out.append(words(re.sub(r"\([^)]*\)", " ", base.replace(m.group(0), m.group(2)))))
    stem = re.sub(r"_(?:l|r)$", "", pid)
    out.append(words(stem.replace("_", " ")))
    return [v for v in out if v]


def _constituents(name: str, comp_ids: list[str], pid: str) -> list[list[str]]:
    out = []
    for m in re.finditer(r"\(([^)]*\+[^)]*)\)", name):                 # "Iliopsoas (iliacus + psoas major)"
        out += [words(x) for x in m.group(1).split("+")]
    stem = re.sub(r"_(?:l|r)$", "", pid)
    for c in comp_ids or []:
        suf = re.sub(rf"^{re.escape(stem)}_(?:[lr]_)?", "", c)
        if suf != c and suf not in ("main",):
            out.append(words(suf.replace("_", " ")))
    return [v for v in out if v]


def _find(sub: list[str], seq: list[str]) -> int:
    for i in range(len(seq) - len(sub) + 1):
        if seq[i:i + len(sub)] == sub:
            return i
    return -1


def name_ok(child: str, parent_name: str, pid: str, comp_ids=()) -> bool:
    C = words(child)
    if not C:
        return False
    for P in _variants(parent_name, pid):
        if C == P:
            return True
        i = _find(P, C)
        if i == 0:
            return True                                              # "Longissimus capitis", "Costal cartilage of first rib"
        if i > 0:
            head = C[:i]
            if head[-1] == "of":
                if len(head) >= 2 and head[-2] in PART_WORDS:
                    return True                                      # "Abdominal part of ...", "Muscular branches of ..."
                continue                                             # "Trochlea of ...", "Node of arch of ..." -- not a piece
            return True                                              # "Inferior fibular retinaculum", "Central superior mesenteric nodes"
        if _find(C, P) == 0:
            return True                                              # "Radial collateral ligament" -> "... complex of elbow"
    return any(C == K or C[-len(K):] == K for K in _constituents(parent_name, comp_ids, pid))


def part_link_ok(child_name: str, child_sys: str, parent_id: str, parent_name: str, parent_cat: str | None,
                 comp_ids=()) -> bool:
    pcat = "lymph" if "lymph" in parent_id else parent_cat
    if pcat not in SYS_COMPAT.get(child_sys, set()):
        return False
    if child_sys in ("bone", "cartilage") and pcat == child_sys:
        return True                                                  # a bone under its bone group (carpals, ribs, vertebrae ...)
    return name_ok(child_name, parent_name, parent_id, comp_ids)


@lru_cache(maxsize=1)
def atlas_categories() -> dict:
    import sys
    sys.path[:0] = [str(REPO / "scripts"), str(REPO / "scripts/zanatomy")]
    import map_names  # noqa: E402
    return {e.entity_id: e.category for e in map_names.load_full_atlas()}


# ---------------------------------------------------------------- 2. layer (class)
_NERVE_WORDS = re.compile(r"nerve|\bn\.|\bnn\b|branch|plexus|\bram(?:us|i)\b|ganglion|\broot\b|trunk|\bcord\b|division|ansa|chorda|"
                          r"splanchnic|sympathetic|cutaneous", re.I)
_SENSE = re.compile(r"\b(?:tympanic membrane|auditory tube)\b", re.I)                         # middle ear: not nervous tissue
_EYE = re.compile(r"\b(?:iris|sclera|vitreous body|zonular fibres)\b", re.I)                  # with cornea / lens / retina (cns)
_CNS = re.compile(r"nucle|fasciculus|commissure|colliculus|geniculate|vermis|flocculus|culmen|declive|fornix|putamen|pallidus|"
                  r"habenula|\bolive\b|peduncle|mamillary|cuneus|septum pellucidum|\bstria\b|white matter|central canal|"
                  r"intermediate substance|reticular|interpeduncular|amygdal|\bdura\b|\btract\b|lat_fis|fissure|sulc|gyr|caudate|"
                  r"lentiform|lemniscus|substantia|tegment|claustrum|\binsula\b|lobule|\bpole\b|\buvula\b|\bnodule\b|folium|pyramis|"
                  r"\btuber\b", re.I)


def layer_fix(name: str, sys_: str) -> str | None:
    """New layer for a mesh drawn as `nerve` that is not a peripheral nerve (or a muscle's pulley drawn as muscle), else None."""
    if sys_ == "muscle" and re.match(r"trochlea of\b", name, re.I):
        return "cartilage"                                           # the superior oblique's fibrocartilaginous pulley
    if sys_ != "nerve" or _NERVE_WORDS.search(name):
        return None
    if _SENSE.search(name):
        return "viscera"
    if _EYE.search(name) or _CNS.search(name):
        return "cns"
    return None


# ---------------------------------------------------------------- 3. names
SONTAKKE = "Sontakke YA (2023) Textbook of Human Anatomy, Vol. 6 Brain, 1st e-book ed., CBS Publishers, New Delhi, p. 103 (lateral sulcus: anterior, anterior ascending and posterior rami)"
MANNAN_493 = "Noor MA (2017) Mannan's Regional Dissection and Surface Anatomy, 14th ed., Jaypee, New Delhi, p. 493 (irregular H-shaped orbital sulci)"
# stable id stem (the id gets _l / _r) -> (display name, source; "mechanical" = only the abbreviation expanded, no source found)
NAMES = {
    "zan_lat_fis_ant_horizont": ("Anterior ramus of lateral sulcus", SONTAKKE),
    "zan_lat_fis_ant_vertical": ("Anterior ascending ramus of lateral sulcus", SONTAKKE),
    "zan_lat_fis_post": ("Posterior ramus of lateral sulcus", SONTAKKE),
    "zan_orbital_sulci_h_shaped_orbital_sulci": ("Orbital sulci (H-shaped)", MANNAN_493),
    "zan_sulcus_interm_prim_jensen": ("Primary intermediate sulcus (of Jensen)", "mechanical"),
}


def display_name(mesh_id: str, name: str) -> str:
    stem = re.sub(r"_(?:l|r)$", "", mesh_id)
    if stem in NAMES:
        return NAMES[stem][0]
    n = name.replace("*", "")                                        # Z-Anatomy's mark of a non-TA term
    n = re.sub(r"\(\s*//\s*([^)']*?)\s*'*\s*\)", lambda m: "(" + m.group(1).strip().lower() + ")", n)   # "(//Posterior '')"
    n = re.sub(r"'+$", "", n.strip())                                # "Central canal'" (a second piece)
    return re.sub(r"\s{2,}", " ", n).strip()


# ---------------------------------------------------------------- 4. card text
_SIDE_ID = re.compile(r"(?:^|_)(r|l)(?:_|$)")
_SIDE_TXT = re.compile(r"\((right|left)\)\s*$", re.I)
_DEVW = (r"tree simplification|tree-parent|see docs|docs/|\.py\b|\.json\b|\bQ\d{3}\b|outside NMSK scope|not literally|"
         r"already-shipped|this atlas' own|module docstring|this round|registry target|near-duplicate stub|is approximated here|"
         r"is matched here to|shipped centreline|real centreline")
_DEV_PAREN = re.compile(r"\s*\((?=[^()]*(?:" + _DEVW + r"))[^()]*\)")
_DEV_SENT = re.compile(_DEVW, re.I)
_BUILD_SENT = [
    re.compile(r"(?:(?:muscular |cutaneous )?branch of (?:its parent branch|[\w ]+?)|[\w ]+?): leaves (?:the trunk )?at the point of its own "
               r"(?:real|shipped) centreline (?:closest to|nearest) [^,]+, runs [\d.]+ mm to (?:that structure's own|the) real surface(?: of \S+?)?\.\s*"),
    re.compile(r"\s*Waypoints?:.*?(?:\.(?=\s+[A-Z(])|\.?$)", re.S),
]
_Q250 = re.compile(r"\s*Q250 female skeleton:.*?(?:not re-modelled\.|symmetrised\.)")


def token_side(tok: str) -> str | None:
    m = _SIDE_TXT.search(tok)
    if m:
        return m.group(1)[0].lower()
    if re.fullmatch(r"[A-Za-z0-9_]+", tok):
        m = _SIDE_ID.search(tok)
        if m:
            return m.group(1)
    return None


@lru_cache(maxsize=1)
def nerve_names() -> dict:
    out = {}
    for p in sorted((REPO / "data/nerves").glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if isinstance(e, dict) and e.get("id") and e.get("name"):
                out[e["id"]] = e["name"]
    par = REPO / "data/anatomy/nerve_parents_q307.json"
    if par.exists():
        for e in json.loads(par.read_text(encoding="utf-8")).get("parents", []):
            out.setdefault(e["id"], e["name"])
    return out


@lru_cache(maxsize=1)
def muscle_names() -> dict:
    out = {}
    for p in (REPO / "data/muscles").rglob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(r, dict) and r.get("id"):
            out[re.sub(r"_(?:l|r)$", "", r["id"])] = r.get("name_common") or r.get("name_ta") or r["id"]
    return out


def _nerve_words(s: str) -> str:
    s = re.sub(r"\bnn\.?(?=\s|$)", "nerves", s)
    return re.sub(r"\bn\.?(?=\s|,|$)", "nerve", s)


def token_name(tok: str, mesh_names: dict) -> str:
    """One nerve / target token as the card shows it: a display name, never an id."""
    t = _DEV_PAREN.sub("", tok).strip()
    side = token_side(t)
    sw = {"r": " (right)", "l": " (left)"}.get(side, "")
    if t in mesh_names and mesh_names[t]:                            # the page's own name, as the card's table would print it
        n = mesh_names[t]
        return n + ("" if _SIDE_TXT.search(n) or not sw else sw)
    if t in nerve_names():
        return _nerve_words(nerve_names()[t]) + ("" if _SIDE_TXT.search(nerve_names()[t]) else sw)
    if re.fullmatch(r"[a-z0-9_]+(?:_[CTLS]\d{1,2})?", t) and "_" in t:
        m = re.fullmatch(r"(.+?)_(r|l)_(.+)", t)                     # a muscle compartment id: gluteus_medius_r_anterior
        if m and m.group(1) in muscle_names():
            part = m.group(3).replace("_", " ")
            return muscle_names()[m.group(1)] + ("" if part == "main" else ", " + part) + sw
        m = re.fullmatch(r"(.+?)_([CTLS]\d{1,2})", t)                # lumbar_plexus_L1, lateral_hip_and_gluteal_skin_T12
        if m:
            return m.group(1).replace("_", " ").capitalize() + " (" + m.group(2) + ")"
        base = re.sub(r"_(?:r|l)(?=_|$)", "", t)
        return _nerve_words(base.replace("_", " ")).capitalize() + sw
    return t


def clean_list(toks, side: str, mesh_names: dict) -> list[str]:
    out = []
    for tok in toks or []:
        ts = token_side(tok)
        if side in ("l", "r") and ts in ("l", "r") and ts != side:
            continue                                                 # a sided structure lists its own side only
        n = token_name(tok, mesh_names)
        if n and n not in out:
            out.append(n)
    return out


def tidy_text(t: str) -> str:
    """Mechanical: "subcostal n" -> "subcostal nerve", "lumbar_root_T12" -> "lumbar root T12" (ids the page's table cannot name)."""
    t = re.sub(r"\b(?:lumbar|sacral|cervical|thoracic)_root_([CTLS]\d{1,2})\b", r"\1", t, flags=re.I)   # lumbar_root_T12 = the T12 ramus
    def nid(m):                                                      # a nerve-tree id the page has no mesh for
        k = m.group(0)
        if k in nerve_names():
            return _nerve_words(nerve_names()[k]).lower()
        return k[:-2].replace("_", " ") + " nerve" if k.endswith("_n") else k
    t = re.sub(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)*_n(?:_[a-z0-9]+)*\b", nid, t)
    t = re.sub(r"\b([a-z]+) nn\b(?![.=\d])", r"\1 nerves", t)
    t = re.sub(r"\b([a-z]+) n\b(?!\s*[=\d.])", r"\1 nerve", t)
    t = re.sub(r"\b([A-Za-z]+(?:_[A-Za-z]+)*)_([CTLSctls]\d{1,2})(?:_([lr]))?\b",
               lambda m: m.group(1).replace("_", " ").lower() + " " + m.group(2).upper(), t)
    return t


def split_build_text(s: str) -> tuple[str, str]:
    """(card text, build-provenance text) of one note."""
    if not s:
        return s, ""
    moved = []

    def take(m):
        moved.append(m.group(0).strip())
        return " " if m.group(0).startswith(" ") else ""
    t = _DEV_PAREN.sub(take, s)
    for rx in _BUILD_SENT:
        t = rx.sub(take, t)
    keep = []
    for sent in re.split(r"(?<=[.;])\s+(?=[A-Z(])", t):            # a whole sentence about how the page was built
        (moved if _DEV_SENT.search(sent) else keep).append(sent)
    t = tidy_text(" ".join(keep))
    t = re.sub(r"\s+([.,;:])", r"\1", re.sub(r"\s{2,}", " ", t)).strip()
    return t, " ".join(moved)


_Q357 = re.compile(r"Q357: moved out of the (?P<b>.+?), where the source registration left (?P<n>\d+) of its vertices up to "
                   r"(?P<d>[\d.]+) mm inside the bone \(the (?P<w>nerve|vessel) does not pass through the bone there\); ")


def q357_lead(s: str) -> str:
    """Q365: a Q357 note opens with ONE short sentence. The card shows a badge's first sentence when it is 40-140 characters long,
    else its first 120 characters -- the Q357 opening sentence ran to 170-260 characters, so the card cut it mid-word
    ("... inside the bone (the n"). The facts are unchanged, only reordered."""
    return _Q357.sub(lambda m: (f"Q357: moved out of bone ({m['d']} mm deep: a registration error, not a passage). "
                                f"Bones: the {m['b']}; the source registration had left {m['n']} of its vertices inside; "), s)


def split_badge(s: str) -> tuple[str, str]:
    """(card badge, build-provenance text): the Q250 per-structure deformation numbers are page-wide build provenance."""
    if not s:
        return s, ""
    s = q357_lead(s)
    moved = [m.group(0).strip() for m in _Q250.finditer(s)]
    return re.sub(r"\s{2,}", " ", _Q250.sub(" ", s)).strip(), " ".join(moved)


# ---------------------------------------------------------------- 5. sweep (what a card would print; a Python reading of NMSKHuman)
def _render(s, names: dict) -> str:
    s = str(s)
    s = re.sub(r"\(verbatim,?\s*from\s*[^)]*\)", "(verbatim)", s)
    s = re.sub(r"\b(?:data|scripts|viewer|clinical|build|docs)/[\w./*{}-]+", "", s)
    s = re.sub(r"\b[\w-]+\.(?:json|html|py|js|csv|txt)\b", "", s)
    s = re.sub(r"\(\s*Q\d{2,3}[a-z]?[^)]*\)", "", s)
    s = re.sub(r"\b(?:in|by|from|see)\s+Q\d{2,3}[a-z]?\b", "", s, flags=re.I)
    s = re.sub(r"\bQ\d{2,3}[a-z]?\b:?\s*", "", s)

    def idn(m):
        t = m.group(0)
        if t in names:
            sd = re.search(r"_(r|l)$", t)
            return names[t] + ({"r": " (right)", "l": " (left)"}[sd.group(1)] if sd else "")
        return re.sub(r"_(?:r|l)(?=_|$)", "", t).replace("_", " ")
    return re.sub(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", idn, s)


def card_text(rec: dict, names: dict) -> str:
    """The fact text a structure's card prints from its record (template select(), Q344 wording), one line per field."""
    if not rec:
        return ""
    out = []
    for k in ("part_of", "latin", "region", "origin", "insertion", "method", "source", "notes"):
        if rec.get(k):
            out.append(("NOTE: " if k == "notes" else "") + _render(rec[k], names))
    for k in ("nerve", "targets", "supplies"):
        if rec.get(k):
            out.append(", ".join(_render(x, names) for x in rec[k]))
    b = rec.get("procedural_badge")
    if b:
        full = _render(b, names)
        m = re.match(r"^(.{40,140}?[.;])(\s|$)", full)
        out.append(full if len(full) <= 150 else (m.group(1) if m else full[:120]))
    return "\n".join(out)


RAW_MARKERS = {
    "raw id (underscore)": re.compile(r"(?<![`\w])[A-Za-z0-9]+_\w+\b(?!`)"),
    "abbreviated id ('n', 't1', 'main')": re.compile(r"\b[a-z]+ nn?\b(?![.(])|\b[tcls]\d{1,2} muscular\b|\bmain \((?:left|right)\)"),
    "build provenance": re.compile(r"centreline|Waypoints?:|tree simplification|tree-parent|already-shipped|"
                                   r"carried with the deformation of the bones|outside NMSK scope|\bsee\)", re.I),
    "truncated note": re.compile(r"^NOTE:.*(?:\([^()]{0,200}$|[;,]$)"),
}


def raw_hits(text: str) -> list[str]:
    text = re.sub(r"\bdoi:\S+|\bPMID\s*\d+", "", text)                # citation identifiers are not ids
    return [k for k, rx in RAW_MARKERS.items() for line in text.splitlines() if rx.search(line)]
