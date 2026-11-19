#!/usr/bin/env python3
"""Q248 PART 1 -- ligament audit of the six pages against the reference checklist (scripts/anatomy/q248/checklist.py).
    python3 scripts/anatomy/q248/lig_audit.py --before build/q244 [--after build/q248] -o data/derived/Q248_ligament_audit.md [--json data/derived/Q248_ligament_audit.json]
A page's structure counts as a ligament-like structure if its class is not bone / vessel / nerve / cns / lymph / bursa / skin / viscera-of-other-kind and its "<id> | <name>" matches an item's regex.
Derivation (how the geometry was obtained) comes from the source subject of the entry: measured (CT / cryo / DU release), Z-fitted (Z-Anatomy model fitted to the page body: Combined pages), Z-Anatomy (Base pages),
Z-filled (xfer_zan2*), HRA (xfer_hra*), CVH Q235, transferred (VH male <-> female), rule-based (Q248 and earlier rule subjects), mirrored (mirror_q237)."""
from __future__ import annotations
import argparse, collections, json, os, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts" / "anatomy")); sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import checklist as CL  # noqa: E402

PAGES = [("own_f", "viewer_f_hr", "Imaging-based F"), ("comb_f", "viewer_zan_female", "Combined F"), ("base_f", "viewer_base_female", "Base F"),
         ("own_m", "viewer_m_hr", "Imaging-based M"), ("comb_m", "viewer_zan_vhm", "Combined M"), ("base_m", "viewer_zan_atlas", "Base M")]
SKIP_SYS = {"bone", "vessel", "nerve", "cns", "lymph", "bursa", "skin"}
FEMALE = {"own_f", "comb_f", "base_f"}


def derive(src: str, key: str, badge: str = "") -> str:
    b = (badge or "").lstrip()
    if b.startswith("RULE-BASED (Q248)"): return "rule-based (Q248)"
    if b.startswith("FILLED from Z-Anatomy (Q248)"): return "Z-filled (Q248)"
    if b.startswith("REGISTERED OTHER PERSON (Q248)"): return "CVH (Q248)"
    if src.startswith("mirror"): return "mirrored"
    if src.startswith("xfer_hra"): return "HRA"
    if src.startswith("xfer_cvh"): return "CVH Q235"
    if src.startswith("xfer_zan"): return "Z-filled"
    if src.startswith("xfer_vh"): return "transferred (VH m<->f)"
    if "q248" in src and "rule" in src: return "rule-based (Q248)"
    if "q248" in src and "zan" in src: return "Z-filled (Q248)"
    if "q248" in src and "cvh" in src: return "CVH (Q248)"
    if "rule" in src: return "rule-based"
    if src == "zan": return "Z-fitted" if key.startswith("comb") else "Z (Base)"
    if src.startswith("ct_") or src.startswith("vhm_"): return "measured/CT"
    return src


def load_page(key, root):
    os.environ.setdefault("Q233_SRC_" + key, "")
    import q233_load as Q
    d = dict(own_m="viewer_m_hr", own_f="viewer_f_hr", base_m="viewer_zan_atlas", base_f="viewer_base_female", comb_m="viewer_zan_vhm", comb_f="viewer_zan_female")[key]
    os.environ["Q233_SRC_" + key] = f"{root}/{d}"
    return Q.load(key)


def structs(key, root):
    S = load_page(key, root)
    out = []
    for s in S:
        if s["sys"] in SKIP_SYS: continue
        out.append(dict(id=s["id"], name=s["name"], sys=s["sys"], side=s["side"], src=s["src"], nv=len(s["v"]), derived=derive(s["src"], key, (s.get("rec") or {}).get("procedural_badge", "")), text=(s["id"] + " | " + s["name"]).lower()))
    return out


def match(items, S, key):
    res = {}
    female = key in FEMALE
    for g, k, label, sex, sided, inc, exc in items:
        applies = sex == "b" or (sex == "f") == female
        rx, rxe = re.compile(inc), (re.compile(exc) if exc else None)
        hits = [s for s in S if rx.search(s["text"]) and not (rxe and rxe.search(s["text"]))]
        sides = sorted({h["side"] for h in hits})
        if not applies: status = "n/a"
        elif not hits: status = "missing"
        elif sided == "p" and not ({"l", "r"} <= set(sides) or ("m" in sides)): status = "one side"
        else: status = "present"
        res[k] = dict(status=status, hits=[h["id"] for h in hits], sides="".join(sorted(set(sides))), derived=sorted({h["derived"] for h in hits}), nv=sum(h["nv"] for h in hits))
    return res


def run(root):
    out = {}
    for key, d, label in PAGES:
        S = structs(key, root)
        out[key] = dict(label=label, dir=f"{root}/{d}", n_ligament_like=len([s for s in S if s["sys"] in ("joint", "ligament", "fascia", "tendon")]), items=match(CL.ITEMS, S, key),
                        classes=collections.Counter(s["derived"] for s in S if s["sys"] in ("joint", "ligament")))
    return out


def counts(res):
    c = {}
    for key, r in res.items():
        by = collections.defaultdict(lambda: collections.Counter())
        tot = collections.Counter()
        for g, k, label, sex, sided, inc, exc in CL.ITEMS:
            st = r["items"][k]["status"]
            by[g][st] += 1; tot[st] += 1
        c[key] = dict(total=dict(tot), by_group={g: dict(v) for g, v in by.items()})
    return c


def md(before, after, notes):
    L = []
    cb = counts(before); ca = counts(after) if after else None
    L.append("# Q248 ligament audit (six pages against a reference checklist)\n")
    L.append("Reference: Terminologia Anatomica (items named by TA / Latin terms), Gray's Anatomy 1918 (public domain) and standard anatomy; the checklist is `scripts/anatomy/q248/checklist.py` ("
             f"{len(CL.ITEMS)} items; sex-specific items count only on the matching sex). A structure counts when its id / name matches the item (regex in the checklist); an item whose structure stands for several "
             "items (one glenohumeral complex for SGHL/MGHL/IGHL, one coracoclavicular ligament for conoid + trapezoid, ...) is counted present for each and marked 'grouped'. "
             "BEFORE = the six page dirs of Q244 (`build/q244`); AFTER = the Q248 page dirs (`build/q248`).\n")
    L.append("## 1. Counts per page (present / one side only / missing; items that do not apply to the sex excluded)\n")
    hdr = "| Page | present | one side | missing | applicable |" + (" present after | one side after | missing after |" if ca else "")
    L.append(hdr); L.append("|---|---|---|---|---|" + ("---|---|---|" if ca else ""))
    for key, d, label in PAGES:
        t = cb[key]["total"]; app = t.get("present", 0) + t.get("one side", 0) + t.get("missing", 0)
        row = f"| {label} | {t.get('present', 0)} | {t.get('one side', 0)} | {t.get('missing', 0)} | {app} |"
        if ca:
            u = ca[key]["total"]; row += f" {u.get('present', 0)} | {u.get('one side', 0)} | {u.get('missing', 0)} |"
        L.append(row)
    L.append("")
    L.append("Ligament-like entries on the page (class ligament / joint / fascia / tendon): " + ", ".join(f"{lbl} {before[k]['n_ligament_like']}" + (f" -> {after[k]['n_ligament_like']}" if after else "") for k, d, lbl in PAGES) + ".\n")
    L.append("### Per group (present / applicable; BEFORE" + (" -> AFTER" if ca else "") + ")\n")
    L.append("| Group | " + " | ".join(l for _, _, l in PAGES) + " |"); L.append("|---|" + "---|" * len(PAGES))
    for g in CL.GROUPS:
        cells = []
        for key, d, label in PAGES:
            def f(c):
                x = c[key]["by_group"].get(g, {}); a = x.get("present", 0) + x.get("one side", 0) + x.get("missing", 0)
                return f"{x.get('present', 0)}/{a}"
            cells.append(f(cb) + (" -> " + f(ca) if ca else ""))
        L.append(f"| {CL.GROUP_LABEL[g]} | " + " | ".join(cells) + " |")
    L.append("")
    L.append("## 2. How the ligaments present on each page were derived (class ligament / joint entries)\n")
    L.append("| Page | " + " | ".join(["derivation: count"]) + " |"); L.append("|---|---|")
    for key, d, label in PAGES:
        L.append(f"| {label} | " + ", ".join(f"{a} {b}" for a, b in sorted(before[key]["classes"].items(), key=lambda x: -x[1])) + (" || AFTER: " + ", ".join(f"{a} {b}" for a, b in sorted(after[key]["classes"].items(), key=lambda x: -x[1])) if after else "") + " |")
    L.append("\nLegend: measured/CT = segmented / measured on the body (also the Visible Human DU lower-extremity release); Z-fitted = Z-Anatomy structure fitted to the Combined body (CC BY-SA 4.0); Z (Base) = Z-Anatomy structure "
             "of the Base model; Z-filled = Z-Anatomy structure carried onto the own bones one bone at a time (earlier passes) or, `(Q248)`, by the Q248 carrier-bone fit; HRA = HuBMAP reference object registered on the body (CC BY 4.0); "
             "CVH = Chinese Visible Human (Wu 2015) registered; rule-based = built from bone landmarks by a documented rule; mirrored = mirror of the opposite side; transferred = other Visible Human.\n")
    L.append("## 3. Checklist matrix (status / sides / derivation); rows in relevance order (pelvic floor first)\n")
    L.append("Status: `+` present, `1` one side only, `-` missing, `n/a` not for this sex.  Sides: l r m.\n")
    for g in CL.GROUPS:
        L.append(f"### {CL.GROUP_LABEL[g]}\n")
        L.append("| Item | " + " | ".join(l for _, _, l in PAGES) + " |"); L.append("|---|" + "---|" * len(PAGES))
        for gg, k, label, sex, sided, inc, exc in CL.ITEMS:
            if gg != g: continue
            cells = []
            for key, d, lbl in PAGES:
                def cell(res):
                    r = res[key]["items"][k]; st = r["status"]
                    if st == "n/a": return "n/a"
                    if st == "missing": return "-"
                    sym = "+" if st == "present" else "1"
                    return f"{sym} {r['sides']} {'/'.join(r['derived'])}" + (" (grouped)" if len(r["hits"]) == 1 and k in ("sghl", "mghl", "ighl", "conoid", "trapezoid") else "")
                c0 = cell(before)
                cells.append(c0 if not after else (c0 if cell(after) == c0 else f"{c0} -> **{cell(after)}**"))
            L.append(f"| {label} | " + " | ".join(cells) + " |")
        L.append("")
    L.append("## 4. Missing items ranked by relevance (pelvic floor first, then pelvis, spine, hip, knee, ankle, shoulder, thorax, elbow, wrist/hand)\n")
    L.append("Rank = group order, then the number of pages that lack it (BEFORE). 'Source' says what Q248 can defend: a real source (Z-Anatomy structure of the Combined / Base page, CVH, HRA) or a rule from published attachments; `no source` = nothing shipped.\n")
    L.append("| # | Group | Item | missing on (pages) | Q248 route |"); L.append("|---|---|---|---|---|")
    rank = []
    for gi, g in enumerate(CL.GROUPS):
        for gg, k, label, sex, sided, inc, exc in CL.ITEMS:
            if gg != g: continue
            miss = [lbl for key, d, lbl in PAGES if before[key]["items"][k]["status"] in ("missing", "one side")]
            if miss: rank.append((gi, -len(miss), k, label, miss, g))
    rank.sort()
    for n, (gi, nm, k, label, miss, g) in enumerate(rank, 1):
        zsrc = any(before[kk]["items"][k]["status"] == "present" for kk in ("comb_f", "comb_m", "base_f", "base_m"))
        route = notes.get(k) or ("Z-Anatomy structure exists on the Combined page: carried onto the Imaging-based page when the guards pass" if zsrc else "no source")
        L.append(f"| {n} | {CL.GROUP_LABEL[g]} | {label} | {', '.join(miss)} | {route} |")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--before", default="build/q244"); ap.add_argument("--after"); ap.add_argument("-o", dest="o", required=True); ap.add_argument("--json")
    ap.add_argument("--notes", default=str(REPO / "data/derived/Q248_route_notes.json"))
    a = ap.parse_args()
    before = run(a.before); after = run(a.after) if a.after else None
    notes = json.loads(Path(a.notes).read_text()) if Path(a.notes).exists() else {}
    text = md(before, after, notes)
    extra = REPO / "data/derived/Q248_audit_extra.md"
    if extra.exists(): text += "\n" + extra.read_text()
    Path(a.o).write_text(text)
    if a.json:
        Path(a.json).write_text(json.dumps(dict(before=before, after=after, counts_before=counts(before), counts_after=counts(after) if after else None), indent=1, default=list) + "\n")
    print("audit written", a.o)
    for key, d, lbl in PAGES: print(lbl, counts(before)[key]["total"])


if __name__ == "__main__":
    main()
