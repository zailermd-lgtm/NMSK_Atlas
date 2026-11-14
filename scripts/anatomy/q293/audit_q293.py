#!/usr/bin/env python3
"""Q293 audit of the muscle data behind the Learn panel: origins / insertions / innervation / cited actions vs standard references,
and the action table's movement signs vs this project's own computed moment arms (Q284).

    python3 scripts/anatomy/q293/audit_q293.py apply     # write the corrections (muscle files, both sides; action rows; cites) -- idempotent
    python3 scripts/anatomy/q293/audit_q293.py check     # exit 1 unless every correction is in place
    python3 scripts/anatomy/q293/audit_q293.py signs     # -> data/derived/Q293_action_signs.json (every row x page x structure vs its moment arm)

Every correction is one row of data/anatomy/muscle_audit_q293.json (muscle, field, old, new, source) -- the table the Hebrew report
(docs/research/Q293_muscle_attachment_action_audit.md) prints. Textbook references: Gray's Anatomy for Students 4th ed. (Drake, Vogl,
Mitchell) -- the source the muscle files already cite -- and Moore's Clinically Oriented Anatomy 8th ed. (tables of the limb muscles);
thumb actions from a moment-arm study (Smutz 1998, PubMed-verified quote below)."""
from __future__ import annotations
import glob, json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
AUDIT = REPO / "data/anatomy/muscle_audit_q293.json"
ACT = REPO / "data/anatomy/muscle_actions_q283.json"
GS, MO = "Gray's Anatomy for Students 4th ed. (Drake, Vogl, Mitchell)", "Moore's Clinically Oriented Anatomy 8th ed."
SMUTZ = {"citation": "Smutz WP, Kongsayreepong A, Hughes RE, Niebur G, Cooney WP, An KN. Mechanical advantage of the thumb muscles. J Biomech 1998;31(6):565-70",
         "doi": "10.1016/s0021-9290(98)00043-8", "pmid": "9755041",
         "note": "Cadaveric tendon-excursion moment arms of the thumb muscles at the IP, MCP and CMC joints (seven hands). The abstract gives each muscle's overall role; the joints a muscle crosses are those of its course (Gray's / Moore).",
         "quote": "It was found that the flexor pollicis longus was a pure flexor while flexor pollicis brevis was an adductor as well as a flexor, the extensor pollicis longus was an extensor and an adductor, extensor pollicis brevis was an extensor and a mild abductor, the abductor pollicis longus was an extensor as well as an abductor, the abductor pollicis brevis was mainly an abductor, the adductor pollicis was a major flexor as well as an adductor, and the opponents pollicis was a flexor and an abductor."}

# (muscle, field path, old, new, source); "{s}" = side letter in bone ids
FILE_FIXES = [
    ("gastrocnemius", "attachments.origin_landmark", "lateral head: posterior surface above lateral condyle",
     "lateral head: lateral surface of the lateral femoral condyle", f"{MO} (lateral head: lateral aspect of the lateral condyle of the femur); {GS}"),
    ("biceps_femoris", "attachments.origin_landmark", "short head: linea aspera of femur (femur_{s})",
     "short head: lateral lip of the linea aspera and the lateral supracondylar line of the femur (femur_{s})", f"{MO}; {GS}"),
    ("flexor_carpi_ulnaris", "attachments.origin_landmark", "ulnar head: olecranon",
     "ulnar head: medial margin of the olecranon and the posterior border of the ulna (via an aponeurosis)", f"{MO}; {GS}"),
    ("supinator", "attachments.origin_landmark", "lateral epicondyle, supinator crest of ulna",
     "lateral epicondyle, radial collateral and annular ligaments, supinator fossa and crest of ulna", f"{MO}; {GS}"),
    ("pectoralis_major", "attachments.origin_landmark", "abdominal head: anterior rectus sheath (hip_bone_{s} region approximation)",
     "abdominal head: aponeurosis of the external oblique (anterior layer of the rectus sheath; hip_bone_{s} region approximation)", f"{GS}; {MO}"),
    ("abductor_pollicis_longus", "attachments.origin_landmark", "posterior radius, interosseous membrane",
     "posterior surfaces of the ulna and radius (proximal halves) and the interosseous membrane", f"{MO}; {GS}"),
    ("trapezius", "attachments.origin_landmark", "external occipital protuberance, nuchal ligament, spinous processes C7-T12",
     "medial third of the superior nuchal line, external occipital protuberance, nuchal ligament, spinous processes C7-T12", f"{MO}; {GS}"),
    ("teres_major", "innervation.root_levels", "C6-C7", "C5-C7", f"{GS} (lower subscapular nerve C5, C6, C7); {MO} (C5, C6)"),
    ("extensor_pollicis_longus", "actions", None, "extends thumb MCP and CMC joints (crosses all three thumb joints)", f"{MO} (extends distal phalanx at the IP joint, extends MCP and CMC joints); Smutz 1998"),
    ("extensor_pollicis_brevis", "actions", None, "extends thumb CMC joint", f"{MO} (extends proximal phalanx at the MCP joint, extends CMC joint); Smutz 1998"),
    ("flexor_pollicis_longus", "actions", None, "flexes thumb MCP and CMC joints (crosses all three thumb joints)", f"{MO} (flexes phalanges of the thumb); Smutz 1998"),
    ("flexor_pollicis_brevis", "actions", None, "flexes thumb CMC joint", f"{MO} (flexes the thumb); Smutz 1998 (flexor and adductor)"),
    ("adductor_pollicis", "actions", None, "flexes thumb CMC and MCP joints", "Smutz 1998 (adductor pollicis: a major flexor as well as an adductor)"),
]
# new action rows (verbatim quote from the muscle's actions or the cite) and their joint mapping
NEW_ROWS = [
    {"m": "extensor_pollicis_longus", "c": None, "q": "extends thumb MCP and CMC joints", "src": "actions", "mv": [["thumb_mcp", "flex", -1], ["thumb_cmc", "flex", -1]]},
    {"m": "extensor_pollicis_longus", "c": None, "q": "the extensor pollicis longus was an extensor and an adductor", "src": "cite:smutz1998", "mv": [["thumb_cmc", "abd", -1]],
     "note": "Q293: adduction at the CMC joint (the rig's CMC 'abduction' is palmar abduction)"},
    {"m": "extensor_pollicis_brevis", "c": None, "q": "extends thumb CMC joint", "src": "actions", "mv": [["thumb_cmc", "flex", -1]]},
    {"m": "flexor_pollicis_longus", "c": None, "q": "flexes thumb MCP and CMC joints", "src": "actions", "mv": [["thumb_mcp", "flex", 1], ["thumb_cmc", "flex", 1]]},
    {"m": "flexor_pollicis_brevis", "c": None, "q": "flexes thumb CMC joint", "src": "actions", "mv": [["thumb_cmc", "flex", 1]]},
    {"m": "flexor_pollicis_brevis", "c": None, "q": "flexor pollicis brevis was an adductor as well as a flexor", "src": "cite:smutz1998", "mv": [["thumb_cmc", "abd", -1]],
     "note": "Q293: adduction at the CMC joint (the rig's CMC 'abduction' is palmar abduction)"},
    {"m": "adductor_pollicis", "c": None, "q": "flexes thumb CMC and MCP joints", "src": "actions", "mv": [["thumb_cmc", "flex", 1], ["thumb_mcp", "flex", 1]]},
    {"m": "extensor_digitorum", "c": None, "q": "contributes to IP extension via the extensor expansion", "src": "actions",
     "mv": [[["f2_pip", "f3_pip", "f4_pip", "f5_pip"], "flex", -1], [["f2_dip", "f3_dip", "f4_dip", "f5_dip"], "flex", -1]],
     "note": "Q293: the cited IP extension was listed but not animated before; animated at the PIP and DIP joints of digits 2-5 together"},
]
NEW_NOT_ANIMATED = [
    {"m": "tensor_fasciae_latae", "c": None, "what": "knee (through the iliotibial tract)",
     "why": "The cited knee action is a stabilisation ('tenses the IT band to stabilize the knee in extension'), not a movement: the iliotibial "
            "tract passes in front of the knee's flexion axis near extension and behind it in deeper flexion, so no single knee direction "
            "is animated. Its hip actions (flexion, abduction, internal rotation) are."},
]


def dump_like(path, d):
    """write JSON with the file's own indentation / ascii escaping / final newline (keeps the diff to the changed values)"""
    t = Path(path).read_text(encoding="utf-8"); ln = t.split("\n")[1] if "\n" in t else ""
    ind = len(ln) - len(ln.lstrip(" ")) or None
    out = json.dumps(d, indent=ind, ensure_ascii=("\\u" in t)) + ("\n" if t.endswith("\n") else "")
    Path(path).write_text(out, encoding="utf-8")


def mfiles(m):
    return sorted(glob.glob(str(REPO / f"data/muscles/*/{m}_r.json")) + glob.glob(str(REPO / f"data/muscles/*/{m}_l.json")))


def getp(d, path):
    for k in path.split("."):
        d = d[k]
    return d


def setp(d, path, v):
    ks = path.split(".")
    for k in ks[:-1]:
        d = d[k]
    d[ks[-1]] = v


def apply(write=True):
    errs, rows = [], []
    for (m, path, old, new, src) in FILE_FIXES:
        fs = mfiles(m)
        if not fs:
            errs.append(f"{m}: no muscle file"); continue
        for f in fs:
            s = "r" if f.endswith("_r.json") else "l"
            d = json.loads(Path(f).read_text(encoding="utf-8")); cur = getp(d, path)
            o, n = (old or "").replace("{s}", s), new.replace("{s}", s)
            if path == "actions":
                if n not in cur:
                    if not write:
                        errs.append(f"{f}: action missing {n!r}"); continue
                    cur.append(n)
            elif isinstance(cur, str):
                if n in cur:
                    pass
                elif o in cur:
                    if not write:
                        errs.append(f"{f}: {path} not corrected"); continue
                    setp(d, path, cur.replace(o, n))
                else:
                    errs.append(f"{f}: {path}: neither old nor new text present"); continue
            if write:
                dump_like(f, d)
        rows.append({"muscle": m, "field": path, "old": (old or "(not listed)").replace("{s}", "r"), "new": new.replace("{s}", "r"), "source": src})
    A = json.loads(ACT.read_text(encoding="utf-8"))
    if "smutz1998" not in A["cites"]:
        if write: A["cites"]["smutz1998"] = SMUTZ
        else: errs.append("cite smutz1998 missing")
    key = lambda r: (r["m"], r.get("c"), r["q"])
    have = {key(r) for r in A["rows"]}
    for r in NEW_ROWS:
        if key(r) not in have:
            if write: A["rows"].append(r)
            else: errs.append(f"row missing: {r['m']} {r['q']}")
        rows.append({"muscle": r["m"], "field": "action row (simulation)", "old": "(not animated)", "new": f"{r['q']} -> {r['mv']}",
                     "source": "the muscle file's cited action" if r["src"] == "actions" else SMUTZ["citation"] + ", doi:" + SMUTZ["doi"]})
    hv = {(x["m"], x.get("c"), x["what"]) for x in A.get("not_animated", [])}
    for x in NEW_NOT_ANIMATED:
        if (x["m"], x.get("c"), x["what"]) not in hv:
            if write: A["not_animated"].append(x)
            else: errs.append(f"not_animated missing: {x['m']}")
        rows.append({"muscle": x["m"], "field": "not_animated", "old": "(silently not animated)", "new": "stated: " + x["what"], "source": "the muscle file's cited action (stabilisation, not a movement)"})
    if write:
        dump_like(ACT, A)
        AUDIT.write_text(json.dumps({"_README": ["Q293 corrections to the muscle data, one row each; applied by scripts/anatomy/q293/audit_q293.py apply",
                                                 "geometry_vs_textbook: cited movement signs the Q284 computed moment arms contradict on (nearly) every page, with why the citation is kept"],
                                     "references": {"gray": GS, "moore": MO, "smutz1998": SMUTZ}, "rows": rows, "geometry_vs_textbook": GEO_VS_TEXT}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return errs


KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
_THUMB = ("The rig's thumb CMC directions were checked by forward kinematics on Base · Male and Combined · Female: +20 deg CMC flexion "
          "brings the thumb tip 19-22 mm closer to the 5th metacarpal (flexion across the palm), +20 deg palmar abduction lifts it off the "
          "palm -- the labels and the simulation are right. The computed CMC moment arms of EVERY thumb muscle come out with the opposite "
          "sign (flexors negative, extensors positive), i.e. a systematic artefact of the Q284 path model at the thumb CMC, not of the "
          "cited actions. Kept: the cited action (Smutz 1998 tendon-excursion moment arms; Moore; Gray's).")
GEO_VS_TEXT = {
    "abductor_pollicis_longus|thumb_cmc|abd|+1": {"kept": "cited (Gray's; Smutz 1998: 'an extensor as well as an abductor')", "reason": _THUMB},
    "adductor_pollicis|thumb_cmc|abd|-1": {"kept": "cited (Gray's; Smutz 1998: 'a major flexor as well as an adductor')", "reason": _THUMB},
    "adductor_pollicis|thumb_cmc|flex|+1": {"kept": "cited (Smutz 1998)", "reason": _THUMB},
    "flexor_pollicis_brevis|thumb_cmc|flex|+1": {"kept": "cited (Moore; Smutz 1998)", "reason": _THUMB},
    "flexor_pollicis_brevis|thumb_cmc|abd|-1": {"kept": "cited (Smutz 1998: 'an adductor as well as a flexor')", "reason": _THUMB},
    "extensor_pollicis_longus|thumb_cmc|flex|-1": {"kept": "cited (Moore; Smutz 1998: 'an extensor and an adductor')", "reason": _THUMB},
    "tibialis_posterior|ankle|dp|-1": {"kept": "cited (Gray's; Moore: plantarflexes the ankle)",
                                       "reason": "Its tendon runs in the groove behind the medial malleolus, close to the rig's malleolar-tip axis; the Q284 wrap puts the computed path on the wrong side of that axis on every page (dorsiflexion sign). Plantarflexion is the textbook action of tibialis posterior; kept."},
    "external_oblique|thoracic|rot|-1": {"kept": "cited (Gray's; Moore: contralateral rotation of the trunk)",
                                         "reason": "A broad sheet: the centre line of its mesh (the Q284 path) does not follow the fibres from the ribs down and forward to the linea alba, so the computed thoracic rotation sign is unreliable (agrees on 1 of 11 structures). Textbook kept."},
    "obliquus_capitis_inferior|cervical|rot|+1": {"kept": "cited (Gray's: rotates the atlas and the head to the same side)",
                                                  "reason": "The rig lumps the head and the whole neck in one cervical region; a muscle from C2 to C1 acts at the atlanto-axial joint only (agrees on 4 of 12 structures). Textbook kept."},
}


def signs():
    """every action row x page x structure: the row's sign vs the sign of this body's computed moment arm (Q284 cv checks)"""
    A = json.loads(ACT.read_text(encoding="utf-8"))
    out = {"_README": ["Q293: cited movement signs (data/anatomy/muscle_actions_q283.json) vs the Q284 moment arms computed on each page; agrees / disagrees / agrees at some angles"], "rows": {}}
    for key in KEYS:
        S = json.loads((REPO / f"data/anatomy/moment_arms_{key}.json").read_text(encoding="utf-8"))["s"]
        for sid, x in S.items():
            for c in x.get("cv") or []:
                k = f"{x['b']}|{x.get('c') or ''}|{c[0].rsplit('_', 1)[0]}|{c[1]}|{c[2]:+d}|{c[4]}"
                e = out["rows"].setdefault(k, {"agrees": 0, "disagrees": 0, "agrees at some angles": 0, "where": []})
                e[c[3]] += 1
                if c[3] != "agrees":
                    e["where"].append(f"{key}:{sid}")
    (REPO / "data/derived/Q293_action_signs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    n = len(out["rows"]); dis = {k: v for k, v in out["rows"].items() if v["disagrees"] > v["agrees"] + v["agrees at some angles"]}
    print(n, "row x joint checks;", len(dis), "where the computed sign disagrees on most structures:")
    for k, v in dis.items():
        print("  ", k, {a: b for a, b in v.items() if a != "where"})


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "apply":
        e = apply(True); print("\n".join(e) or "applied")
        return 1 if e else 0
    if cmd == "check":
        e = apply(False); print("\n".join(e) or "all Q293 corrections in place")
        return 1 if e else 0
    signs(); return 0


if __name__ == "__main__":
    raise SystemExit(main())
