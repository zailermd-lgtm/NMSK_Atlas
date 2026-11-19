#!/usr/bin/env python3
"""Q237 step 3 driver: candidates -> mirror + fit + guards -> data/derived/Q237_fill_<page>.json and the additions (pickle) the page builders read.
    python3 scripts/anatomy/q237/run_fill.py PAGE_KEY [--only canon1,canon2]
Candidates (never a structure that is validly measured):
  A  MISSING side: one side of a twin does not exist; the source side must be this body's own data (own pages: measured / rule-based) or a Z-Anatomy structure (Z pages) with no listed defect.
  B  LISTED DEFECT (Q198 / Q204 audit severity >= 2 on one side, 0 on the other, build/q225_raw*/Q204_regions_*.json): the defective side is replaced ONLY when it is not this body's own data
     (own pages: Z-filled or transferred; Z pages: Z-fitted estimates) and the opposite side is the clean one (own pages: measured / rule-based).
Everything else that would be an improvement is listed as a recommendation."""
from __future__ import annotations
import argparse, json, pickle, re, sys, datetime
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C, pairing as PR, fill as Fl  # noqa: E402
sys.path.insert(0, str(C.REPO))
from scripts import audit_q189_model_separation as AUD  # noqa: E402

REPO = C.REPO
AUDIT = {"own_m": "build/q225_raw_merged/Q204_regions_own_m.json", "own_f": "build/q225_raw_merged/Q204_regions_own_f.json", "comb_m": "build/q225_raw/Q204_regions_z_male_fit.json",
         "comb_f": "build/q225_raw/Q204_regions_z_female_fit.json", "base_m": "build/q225_raw/Q204_regions_z_male.json", "base_f": "build/q225_raw/Q204_regions_z_base_f.json"}
OWN_DATA = ("measured", "rule_based")            # this body's own data
SUBJECT = "mirror_q237"
NEVER = re.compile(r"skin|cranium|mandible|spinal_cord|brain", re.I)


def audit_rows(key):
    f = REPO / AUDIT[key]
    if not f.exists(): return {}, []
    d = json.loads(f.read_text())
    return {r["id"]: r for r in d["rows"]}, d["symmetry"]


def sev_of(row):
    return max([x.get("severity", 0) for x in (row or {}).get("defects", [])] or [0])


def src_class(P, i):
    x = P.S[i]
    if C.PAGES[P.key][2] == "own":
        return AUD.classify(x["src"], (x["rec"] or {}).get("procedural_badge"))[0]
    return "z_estimate"


def swap_side(sid, tgt):
    """new id for the mirrored structure: the side token swapped (or appended), piece suffixes dropped"""
    s = re.sub(r"_zfill\w*$", "", sid)
    s = re.sub(r"(_q\d+)+$", "", s)
    m = re.search(r"(^|_)(l|r)(_|$)", s)
    other = "l" if tgt == "l" else "r"
    if m:
        return re.sub(r"(^|_)(l|r)(_|$)", lambda mm: mm.group(1) + other + mm.group(3), s, count=1)
    return s + "_" + other


def swap_name(name, tgt):
    w = "left" if tgt == "l" else "right"; o = "right" if tgt == "l" else "left"
    n = re.sub(r"\((left|right)\)", "(" + w + ")", name or "", flags=re.I)
    n = re.sub(r"\b" + o + r"\b", w, n, flags=re.I) if re.search(r"\b" + o + r"\b", n, re.I) else n
    return n


def badge(P, r, own, name):
    """the card text of a mirrored structure: what it is, what it was made from, the numbers"""
    sd = {"l": "left", "r": "right"}
    fit, gd, cf = r["fit"], r["guards"], r["conform"]
    tilt = P.plane.tilt_deg()["total_deg"]
    q = P.q or {}
    cls = r.get("source_class") or []
    what = ("measured on this body" if cls == ["measured"] else "rule-based on this body's own data" if cls == ["rule_based"] else "derived from this body's own data") if own else "the Z-Anatomy structure of the opposite side, as fitted to this body"
    bones = ", ".join(sorted({b["bone"].replace("_", " ") for b in r["neighbour_bones"]}))
    kind = "MISSING on this side" if r["kind"] == "A" else "replaces a defective Z-fitted structure (" + r["why"] + ")"
    g = []
    g.append(f"inside the skin {gd['inside_skin_pct']} % of the vertices, {gd['skin_depth_min_mm']} mm from it at the shallowest")
    if r["sys"] in Fl.ATTACH_LIKE:
        g.append(f"inside bone {gd['in_bone_pct']} % of the vertices (deepest {gd['bone_deepest_mm']} mm; gates {Fl.BELLY_IN_BONE_MAX:g} % / {Fl.BONE_DEPTH_MAX_MM:g} mm)")
    else:
        g.append(f"{gd['bone_min_clear_mm']} mm from bone, none inside (gate {Fl.BONE_CLEAR_MM:g} mm)")
    if "overlap_other_muscles_pct" in gd:
        g.append(f"{gd['overlap_other_muscles_pct']} % of its volume inside other muscles (gate {Fl.OVERLAP_MAX:g} %)")
    rel = " " + r["relaxed_to_source"] + "." if r.get("relaxed_to_source") else ""
    vol_txt = (f"Volume {r['volume_new_cm3']} cm3 ({r['volume_basis']}; source side {r['volume_source_cm3']} cm3)." if r.get("volume_new_cm3") is not None else f"An open sheet: area {r['area_new_cm2']} cm2 (source side {r['area_source_cm2']} cm2), no volume.")
    return (f"MIRROR IMAGE of the opposite side, fitted to this side's bones; NOT measured on this side (Q237). {kind}: the {sd[r['source_side']]}-side {name} ({', '.join(r['source_ids'])}; {what}) was reflected about this "
            f"model's midsagittal plane (fitted to the axial skeleton: tilt {tilt:.1f} deg from the sagittal axis{', median reflection residual ' + format(q['refl_median_mm'], '.1f') + ' mm' if q else ''}), then fitted to this side's "
            f"{bones} by a rigid + uniform-scale registration of the mirrored bones onto this side's (scale {fit['scale']}, rotation {fit['rotation_deg']} deg, bone residual median {fit['bone_residual_median_mm']} mm / p90 "
            f"{fit['bone_residual_p90_mm']} mm) and a bounded conform step (mean {cf['conform_mean_mm']} mm, max {cf['conform_max_mm']} mm; out of the bones, inside the skin). Checked (signed distances): "
            f"{'; '.join(g)}.{rel} {vol_txt} Position and shape are the opposite side's, mirrored: an estimate; real left / right differences are not represented.")


def candidates(P, units, rows, symm):
    out = []
    # A: missing side
    for u in units:
        if u["cls"] == "unmatched" and u.get("kind") == "missing_side":
            sd = u["only_side"]; ids = u["ids_" + sd]
            out.append(dict(kind="A", unit=u, src_side=sd, tgt_side="l" if sd == "r" else "r", src_ids=ids, why="no counterpart on the " + ("left" if sd == "r" else "right")))
    # B: listed defect
    ur = {(u["sys"], re.sub(r"^zan_", "", u["canon"])): u for u in units if "ids_r" in u and "ids_l" in u and u["cls"] in ("paired", "unmatched")}
    for s in symm:
        sl, sr = s["sev_l_r"]
        if not (max(sl, sr) >= 2 and min(sl, sr) == 0): continue
        base = re.sub(r"^zan_", "", s["structure"]); u = ur.get((s["sys"], base))
        if u is None:
            cands = [v for k, v in ur.items() if k[1] == base]
            u = cands[0] if cands else None
        if u is None: continue
        bad = "l" if sl >= 2 else "r"; good = "r" if bad == "l" else "l"
        out.append(dict(kind="B", unit=u, src_side=good, tgt_side=bad, src_ids=u["ids_" + good], bad_ids=u["ids_" + bad], why="listed defect: " + s["why"], sev=[sl, sr]))
    return out


def run(key, only=None):
    P = Fl.Page(key)
    units, _ = PR.classify(P.S, P.plane)
    rows, symm = audit_rows(key)
    own = C.PAGES[key][2] == "own"
    idx_of = P.by_id
    rep, add, rec_only = [], [], []
    seen = set()
    for c in candidates(P, units, rows, symm):
        u = c["unit"]; sy = u["sys"]; cn = u["canon"]
        if only and cn not in only: continue
        if (sy, cn, c["tgt_side"]) in seen: continue
        seen.add((sy, cn, c["tgt_side"]))
        r = dict(kind=c["kind"], sys=sy, canon=cn, source_side=c["src_side"], target_side=c["tgt_side"], source_ids=c["src_ids"], why=c["why"])
        if c["kind"] == "B": r["target_ids_replaced"] = c["bad_ids"]; r["audit_severity_l_r"] = c["sev"]
        if NEVER.search(cn) or sy in ("skin",):
            r.update(decision="not_attempted", reasons=["skin / skull / brain: never mirrored"]); rep.append(r); continue
        src_i = [i for d in c["src_ids"] for i in idx_of[d]]
        scls = sorted({src_class(P, i) for i in src_i})
        r["source_class"] = scls
        # source must be good: own data (own pages), no listed defect of severity >= 2
        sev_src = max([sev_of(rows.get(d)) for d in c["src_ids"]] or [0])
        r["source_audit_severity"] = sev_src
        reasons = []
        if own and not all(k in OWN_DATA for k in scls):
            reasons.append("the opposite side is not this body's own data (" + "/".join(scls) + "): a mirror of an estimate would not be better than the estimate; use the Z-Anatomy counterpart (recommendation)")
        if sev_src >= 2: reasons.append(f"the source side has a listed defect (severity {sev_src})")
        if c["kind"] == "B":
            bcls = sorted({src_class(P, i) for d in c["bad_ids"] for i in idx_of[d]}); r["target_class"] = bcls
            if own and any(k in OWN_DATA for k in bcls):
                reasons.append("the defective side is this body's own data (" + "/".join(bcls) + "): a validly measured / rule-based structure is never replaced; mirror would be a recommendation only")
        if reasons:
            r.update(decision="recommendation" if c["kind"] == "B" or own else "held", reasons=reasons); rep.append(r); continue
        res = Fl.mirror_fit(P, [i for d in c["src_ids"] for i in idx_of[d]], c["src_side"], c["tgt_side"], sy, exclude_ids=[P.S[i]["id"] for d in c["src_ids"] for i in idx_of[d]] if c["kind"] == "A" else [P.S[i]["id"] for d in c["bad_ids"] for i in idx_of[d]] + c["src_ids"])
        r.update(res["report"])
        # the source side's own guards (Z pages: the mirror may not be worse than the clean side it copies)
        sv, sf = C.merge(P.S, [i for d in c["src_ids"] for i in idx_of[d]])
        g_src = Fl.guards(P, sv, sf, sy, exclude_ids=[P.S[i]["id"] for d in c["src_ids"] for i in idx_of[d]])
        r["source_guards"] = {k: v for k, v in g_src.items() if k not in ("fails", "pass")}
        if not own and sy == "muscle" and not res["ok"] and "guards" in res["report"]:
            g = res["report"]["guards"]; fl = []
            for f in res["report"]["fails"]:
                if f.startswith("overlap") and g["overlap_other_muscles_pct"] <= g_src["overlap_other_muscles_pct"] + 2.0: continue
                if f.startswith("bone: ") and g["in_bone_pct"] <= g_src["in_bone_pct"] + 2.0 and g["bone_deepest_mm"] <= max(Fl.BONE_DEPTH_MAX_MM, g_src["bone_deepest_mm"] + 0.5): continue
                fl.append(f)
            if len(fl) != len(res["report"]["fails"]):
                r["relaxed_to_source"] = "Z-Anatomy muscles overlap / embed by design: overlap and in-bone are accepted when no worse than the clean side copied (+2 points)"
            res["report"]["fails"] = fl; r["fails"] = fl; res["ok"] = not fl
        if res["ok"]:
            nid = swap_side(c["src_ids"][0], c["tgt_side"])
            nm = swap_name((P.S[idx_of[c["src_ids"][0]][0]]["rec"] or {}).get("name") or P.S[idx_of[c["src_ids"][0]][0]]["name"], c["tgt_side"])
            r.update(decision="shipped", new_id=nid, name=nm, badge=badge(P, r, own, nm))
            add.append(dict(report=r, V=res["V"], F=res["F"], sys=sy, canon=cn, src_ids=c["src_ids"], tgt_side=c["tgt_side"], replace_ids=c.get("bad_ids", []), new_id=nid))
        else:
            r.update(decision="held", reasons=res["report"].get("fails", ["fit failed"]))
        rep.append(r)
        print(key, c["kind"], sy, cn, c["src_side"], "->", c["tgt_side"], r["decision"], "; ".join(r.get("reasons", []))[:140], flush=True)
    summary = dict(page=key, plane=dict(n=[float(x) for x in P.plane.n], d=float(P.plane.d)), shipped=[r["new_id"] for r in rep if r["decision"] == "shipped"],
                   held=[r["canon"] for r in rep if r["decision"] == "held"], recommendations=[r["canon"] for r in rep if r["decision"] == "recommendation"])
    (REPO / f"data/derived/Q237_fill_{key}.json").write_text(json.dumps(dict(generated=datetime.date.today().isoformat(), summary=summary, structures=rep, gates=dict(
        skin_min_mm=Fl.SKIN_MIN_MM, belly_in_bone_max_pct=Fl.BELLY_IN_BONE_MAX, bone_depth_max_mm=Fl.BONE_DEPTH_MAX_MM, bone_clear_mm=Fl.BONE_CLEAR_MM, overlap_max_pct=Fl.OVERLAP_MAX,
        bone_registration_median_max_mm=Fl.BONE_REG_MEDIAN_MAX, bone_registration_p90_max_mm=Fl.BONE_REG_P90_MAX, scale_range=Fl.SCALE_RANGE, rotation_max_deg=Fl.ROT_MAX_DEG, conform_max_mm=Fl.CONFORM_MAX_MM)), indent=1, default=float) + "\n")
    out = Path("/tmp/claude-0/q237") / f"fill_{key}.pkl"
    pickle.dump(add, open(out, "wb"))
    print(key, "shipped", len(add), "held", len(summary["held"]), "recommendations", len(summary["recommendations"]), "->", out)
    return add, rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("key"); ap.add_argument("--only"); a = ap.parse_args()
    run(a.key, set(a.only.split(",")) if a.only else None)
