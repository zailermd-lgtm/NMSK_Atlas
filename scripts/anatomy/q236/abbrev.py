#!/usr/bin/env python3
"""Q236: deterministic, collision-free, human-readable abbreviations for the structures of one page.

Convention (also printed in the legend window):
  * BASE[-R|-L]   side suffix from the structure's side (midline / unsided structures have none): 'RF-R' = rectus femoris, right.
  * Established anatomical abbreviations are used ONLY from the KNOWN table below (each entry is a standard, widely published one:
    SCM, ECRL, FDS, ACL, PCL, BF, IVC, ...). Anything that is not in the table is GENERATED and flagged g=1 (shown in italics):
      - several content words: the initials, upper case ('TSEPL' = tendon sheath of extensor pollicis longus), numbers kept ('T2/3');
      - a single content word: its first three letters, capitalised ('Coc' = coccyx).
  * Collisions (same base for two different names, or a base that is a KNOWN abbreviation of something else, or a reserved clinical abbreviation
    such as RA / LV): every generated member of the group is lengthened (two letters of each of the first four words: 'BiFe'; one more
    letter for single words), up to level 3; what is still equal gets a numeric suffix by sorted id. Known entries never change.
  * Ids with the same cleaned name and side (several meshes of one entity) share their abbreviation; different ids with the same cleaned name
    and side get the numeric suffix.
Output of build(structs): {id: [abbr, generated(0|1), short_name]}.
"""
from __future__ import annotations

import re
from collections import defaultdict

# cleaned lower-case base name -> established abbreviation. Every entry is a standard abbreviation of exactly this structure.
KNOWN: dict[str, str] = {
    # head / neck / trunk muscles
    "sternocleidomastoid": "SCM", "rectus abdominis": None, "external oblique": "EO", "internal oblique": "IO",
    "transversus abdominis": "TrA", "erector spinae": "ES", "quadratus lumborum": "QL", "latissimus dorsi": "LD", "levator scapulae": "LS",
    "gluteus maximus": "GMax", "gluteus medius": "GMed", "gluteus minimus": "GMin", "tensor fasciae latae": "TFL",
    # shoulder / arm / forearm / hand muscles
    "supraspinatus": "SSP", "infraspinatus": "ISP", "subscapularis": "SSC", "biceps brachii": "BB", "triceps brachii": "TB",
    "brachioradialis": "BR", "pronator teres": "PT", "pronator quadratus": "PQ",
    "extensor carpi radialis longus": "ECRL", "extensor carpi radialis brevis": "ECRB", "extensor carpi ulnaris": "ECU",
    "flexor carpi radialis": "FCR", "flexor carpi ulnaris": "FCU", "flexor digitorum superficialis": "FDS", "flexor digitorum profundus": "FDP",
    "flexor pollicis longus": "FPL", "flexor pollicis brevis": "FPB", "extensor pollicis longus": "EPL", "extensor pollicis brevis": "EPB",
    "abductor pollicis longus": "APL", "abductor pollicis brevis": "APB", "adductor pollicis": "AP", "opponens pollicis": "OP",
    "extensor digitorum": "ED", "extensor digiti minimi": "EDM", "extensor indicis": "EI", "abductor digiti minimi": "ADM", "palmaris longus": "PL",
    # thigh / leg / foot muscles
    "biceps femoris": "BF", "semitendinosus": "ST", "semimembranosus": "SM", "rectus femoris": "RF", "vastus lateralis": "VL",
    "vastus medialis": "VM", "vastus intermedius": "VI", "tibialis anterior": "TA", "tibialis posterior": "TP", "soleus": "SOL",
    "extensor hallucis longus": "EHL", "extensor digitorum longus": "EDL", "flexor hallucis longus": "FHL", "flexor digitorum longus": "FDL",
    # ligaments / fibrous
    "anterior cruciate ligament": "ACL", "posterior cruciate ligament": "PCL", "medial collateral ligament": "MCL", "tibial collateral ligament": "MCL",
    "lateral collateral ligament": "LCL", "fibular collateral ligament": "LCL", "ulnar collateral ligament": "UCL",
    "anterior talofibular ligament": "ATFL", "posterior talofibular ligament": "PTFL", "calcaneofibular ligament": "CFL",
    "anterior inferior tibiofibular ligament": "AITFL", "posterior inferior tibiofibular ligament": "PITFL", "anterolateral ligament": "ALL",
    "iliotibial tract": "ITB", "iliotibial band": "ITB", "triangular fibrocartilage complex": "TFCC",
    # bone landmarks
    "anterior superior iliac spine": "ASIS", "posterior superior iliac spine": "PSIS", "anterior inferior iliac spine": "AIIS",
    "posterior inferior iliac spine": "PIIS",
    # vessels / heart
    "inferior vena cava": "IVC", "superior vena cava": "SVC", "common carotid artery": "CCA", "internal carotid artery": "ICA",
    "external carotid artery": "ECA", "internal jugular vein": "IJV", "external jugular vein": "EJV", "great saphenous vein": "GSV",
    "small saphenous vein": "SSV", "superior mesenteric artery": "SMA", "inferior mesenteric artery": "IMA", "superior mesenteric vein": "SMV",
    "middle cerebral artery": "MCA", "anterior cerebral artery": "ACA", "posterior cerebral artery": "PCA",
    "posterior inferior cerebellar artery": "PICA", "anterior interventricular artery": "LAD", "right coronary artery": "RCA",
    "right atrium": "RA", "left atrium": "LA", "right ventricle": "RV", "left ventricle": "LV",
    # nerves
    "anterior interosseous nerve": "AIN", "posterior interosseous nerve": "PIN", "lateral femoral cutaneous nerve": "LFCN",
}
KNOWN = {k: v for k, v in KNOWN.items() if v}          # (rectus abdominis: RA is the heart chamber here, see RESERVED)

# clinical abbreviations a generated one must never take unless the name really is that structure (every KNOWN value is reserved as well)
RESERVED = {"RA", "LA", "RV", "LV", "RCA", "LCA", "CNS", "PNS", "CSF", "MRI", "CT", "MR", "US", "BP", "HR", "ECG", "EMG", "PRP", "RF", "DVT", "PE", "MI"}

STOP = {"of", "the", "and", "to", "for", "in", "on", "with", "from", "a", "an", "at", "by", "or", "its", "into", "between", "without", "via"}
SIDE_WORDS = re.compile(r"\b(left|right)\b", re.I)


def side_letter(side) -> str:
    s = (side or "").strip().lower()
    return "R" if s in ("r", "right") else "L" if s in ("l", "left") else ""


def _initials_subseq(abbr: str, text: str) -> bool:
    """abbr's letters are, in order, among the initials of the words of text ('LCL' in 'Fibular (lateral) collateral ligament')."""
    ini = "".join(w[0].upper() for w in re.findall(r"[A-Za-z]+", text))
    it = iter(ini)
    return all(ch in it for ch in abbr)


def clean(name: str, side) -> tuple[str, str | None, bool]:
    """-> (display base name, embedded established abbreviation or None, has a qualifier in parentheses that is neither a side nor an abbreviation)."""
    s = (name or "").strip()
    s = re.split(r"\s+--\s+|:\s", s, maxsplit=1)[0]                          # 'X -- composite of ...' / 'X: ...'
    s = re.sub(r"\.[lr]$", "", s)                                             # 'Radial nerve.r'
    s = re.sub(r"\(\s*(?:continuation|side assigned|filled|CVH[;,]?)[^)]*\)", "", s, flags=re.I)
    emb, qual = None, False
    for m in re.finditer(r"\(([^)]*)\)", s):
        inner = m.group(1).strip()
        if re.fullmatch(r"[A-Z]{2,6}", inner):
            if _initials_subseq(inner, s):
                emb = inner                                                   # 'Anterior cruciate ligament (ACL)': the atlas name itself carries it
        elif re.fullmatch(r"(?i)left|right|l|r|lt|rt|bilateral", inner) or re.fullmatch(r"[\d\W]*", inner):
            pass
        elif re.search(r"[A-Za-z]{3}", inner):
            qual = True
    s = re.sub(r"\([^)]*\)", " ", s)                                          # alternative names, counts
    s = s.replace("*", " ")
    sl = side_letter(side)
    if sl:
        s = re.sub(r",\s*(left|right)\b.*$", "", s, flags=re.I)
        s = SIDE_WORDS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;-")
    s = re.sub(r"\s+muscle$", "", s, flags=re.I)
    return s, emb, qual


def content_words(base: str) -> tuple[list[str], list[str]]:
    toks = [t for t in re.findall(r"[A-Za-z]+\d*|\d+", base.replace("-", " ").replace("/", " "))]
    alpha, num = [], []
    for t in toks:
        if t.lower() in STOP:
            continue
        (num if t.isdigit() else alpha).append(t)
    return alpha, num


VERT = re.compile(r"^(?:vertebra\s+)?([CTLS]\d{1,2})$", re.I)
DISC = re.compile(r"^(?:(?P<a>[CTLS]\d{1,2})\s*-\s*(?P<b>[CTLS]\d{1,2})\s+intervertebral disc|intervertebral disc\s+(?P<c>[CTLS]\d{1,2})\s*-\s*(?P<d>[CTLS]\d{1,2}))$", re.I)


def _disc(a: str, b: str) -> str:
    a, b = a.upper(), b.upper()
    return a + "/" + (b[1:] if b[0] == a[0] else b)


def known_for(base: str, emb: str | None, qual: bool = False) -> str | None:
    key = base.lower()
    m = VERT.match(base)
    if m:
        return m.group(1).upper()
    m = DISC.match(base)
    if m:
        return _disc(m.group("a") or m.group("c"), m.group("b") or m.group("d"))
    if key in KNOWN and not qual:
        return KNOWN[key]
    if emb:
        return emb                                                            # the atlas name itself carries it: 'Anterior cruciate ligament (ACL)'
    return None


def generate(base: str, level: int) -> str:
    alpha, num = content_words(base)
    if not alpha:
        return (re.sub(r"[^A-Za-z0-9]", "", base)[:4] or "X").capitalize()
    nums = "".join(num)
    if len(alpha) == 1:
        w = alpha[0]
        return w[: 3 + level].capitalize() + nums if not re.search(r"\d", w) else w.upper() + nums
    if level == 0:
        return "".join(w[0].upper() for w in alpha[:5]) + nums
    return "".join(w[: 1 + level].capitalize() for w in alpha[:4]) + nums


def build(structs: list[dict]) -> dict[str, list]:
    """structs: [{id, name, side}]. Deterministic (depends only on the names / sides / ids)."""
    # 1) entities = (cleaned base, side letter); ids of one entity share an abbreviation
    ent: dict[tuple, list] = defaultdict(list)
    info: dict[str, tuple] = {}
    for s in structs:
        base, emb, qual = clean(s.get("name") or s["id"], s.get("side"))
        if not base:
            base = s["id"]
        k = (base.lower(), side_letter(s.get("side")))
        if s["id"] not in info:
            ent[k].append(s["id"]); info[s["id"]] = (base, emb, k, qual)
    # 2) bases: one per cleaned name (both sides share it)
    bases: dict[str, dict] = {}
    for sid, (base, emb, k, qual) in sorted(info.items()):
        b = bases.setdefault(k[0], {"base": base, "emb": emb, "qual": qual, "fixed": None, "level": 0})
        if emb and not b["emb"]:
            b["emb"] = emb
        b["qual"] = b["qual"] and qual           # a qualifier counts only when every id of this name has it
    for b in bases.values():
        b["fixed"] = known_for(b["base"], b["emb"], b["qual"])
    res: dict[str, str] = {}
    for rnd in range(6):
        cur = {key: (b["fixed"] if b["fixed"] else generate(b["base"], b["level"])) for key, b in bases.items()}
        groups: dict[str, list] = defaultdict(list)
        for key, a in cur.items():
            groups[a.lower()].append(key)
        bumped = False
        for a, keys in groups.items():
            movable = [k for k in keys if not bases[k]["fixed"]]
            clash = len(keys) > 1 or (a.upper() in RESERVED | {v.upper() for v in KNOWN.values()} and movable)
            if not clash:
                continue
            for k in movable:
                if bases[k]["level"] < 3:
                    bases[k]["level"] += 1; bumped = True
        if not bumped:
            break
    cur = {key: (b["fixed"] if b["fixed"] else generate(b["base"], b["level"])) for key, b in bases.items()}
    # 3) numeric suffix for what is still equal (sorted by name key), then the side suffix
    seen: dict[str, int] = {}
    final_base: dict[str, str] = {}
    for key in sorted(cur):
        a = cur[key]; n = seen.get(a.lower(), 0) + 1; seen[a.lower()] = n
        final_base[key] = a if n == 1 else f"{a}{n}"
    out: dict[str, list] = {}
    for k, ids in sorted(ent.items()):
        b = bases[k[0]]
        a = final_base[k[0]] + ("-" + k[1] if k[1] else "")
        for i, sid in enumerate(sorted(ids)):
            out[sid] = [a if i == 0 else f"{a}.{i + 1}", 0 if b["fixed"] else 1, b["base"]]
    return out
