#!/usr/bin/env python3
"""Q248: sections 5-9 of data/derived/Q248_ligament_audit.md (what was added per page, with errors / volumes; what was held and why; what has no source; literature checked), written to data/derived/Q248_audit_extra.md,
read by lig_audit.py.   python3 scripts/anatomy/q248/report_md.py"""
from __future__ import annotations
import collections, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO))
import collect as CO  # noqa: E402
import checklist as CL  # noqa: E402

D = REPO / "data/derived"
PAGES = [("own_f", "Imaging-based F"), ("comb_f", "Combined F"), ("base_f", "Base F"), ("own_m", "Imaging-based M"), ("comb_m", "Combined M"), ("base_m", "Base M")]
XSRC = {"own_f": "own_f", "own_m": "own_m"}


def load_json(n):
    p = D / n
    return json.loads(p.read_text()) if p.exists() else None


def main():
    L = []
    items = {k: CO.collect(k) for k, _ in PAGES}
    L.append("## 5. What Q248 added, per page\n")
    L.append("`transferred` = Z-Anatomy structure carried onto the own bones (own pages only; the Z pages already hold the Z structures), `rule-based` = built from the page's bones / organs (all six pages), `CVH` = Chinese Visible Human "
             "anococcygeal ligament (female own page). Ship diff: every other structure of the page is byte for byte the Q244 page (`data/derived/Q248_vertex_diff_<page>.json`, 0 unlisted).\n")
    L.append("| Page | transferred | rule-based | CVH | total added | triangles added |"); L.append("|---|---|---|---|---|---|")
    for k, lbl in PAGES:
        c = collections.Counter(i["kind"] for i in items[k]); tri = sum(len(i["F"]) for i in items[k])
        L.append(f"| {lbl} | {c.get('xfer', 0)} | {c.get('rule', 0)} | {c.get('cvh', 0)} | {len(items[k])} | {tri} |")
    L.append("")
    L.append("## 6. Rule-based ligaments: numbers per page\n")
    L.append("Length = path length; cross-section = width x thickness (mm; the calibre is a MODELLING CHOICE except where a card says otherwise); volume = closed mesh; attachment = signed distance of the two end-cap centres to the "
             "attachment surface (bone, 0 = on the surface); 'deeper than 1 mm' = vertices more than 1 mm inside a bone after the push-out (0 required); soft overlap = fraction of vertices deeper than 6 mm inside a closed muscle / "
             "3 mm inside an organ (gated on the Imaging-based pages, reported on the Z pages).\n")
    L.append("| Page | id | length mm | cross-section mm | volume cm3 | attachment a / b mm | deeper 1 mm | soft overlap muscle / organ | skin depth mm |"); L.append("|---|---|---|---|---|---|---|---|---|")
    for k, lbl in PAGES:
        for i in items[k]:
            if i["kind"] != "rule": continue
            r = i["report"]; a = r["attachments"]; so = r["soft_overlap"]
            cs = r["cross_section_mm"]
            L.append(f"| {lbl} | {i['id']} | {r['length_mm']} | {cs[0] if cs[0] == cs[1] else str(round(cs[0], 1)) + '-' + str(round(cs[1], 1))} x {cs[2]} | {r['volume_cm3']} | "
                     f"{a.get('end_a', {}).get('signed_distance_mm')} / {a.get('end_b', {}).get('signed_distance_mm', '-')} | {r['vertices_deeper_1mm']} | {so['muscle_fraction_deeper_6mm']} / {so['organ_fraction_deeper_3mm']} | {r['skin_min_depth_mm']} |")
    L.append("")
    L.append("## 7. Z-Anatomy transfers onto the Imaging-based pages: fit errors\n")
    for k in ("own_f", "own_m"):
        xs = [i for i in items[k] if i["kind"] == "xfer"]
        if not xs: continue
        med = sorted(max((f.get("median_mm", 0) for f in i["report"]["carriers"].values()), default=0) for i in xs)
        gap = sorted(i["report"].get("attachment_gap_before_snap_mm", {}).get("median", 0) for i in xs if i["report"].get("attachment_gap_before_snap_mm"))
        L.append(f"**{dict(PAGES)[k]}**: {len(xs)} structures shipped; worst carrier-bone local fit residual per structure: median {med[len(med) // 2]} mm, max {med[-1]} mm; attachment gap before the snap (median of each structure): "
                 f"median {gap[len(gap) // 2] if gap else '-'} mm, max {gap[-1] if gap else '-'} mm; after the snap 0 mm by construction. Per-structure numbers: `data/derived/Q248_xfer_{k}.json` (carriers, local residuals, attachment gaps, pushed vertices, "
                 f"edge stretch, length ratio, overlap, skin depth, sides).\n")
    L.append("## 8. Held (not shipped) and why\n")
    for k in ("own_f", "own_m"):
        x = load_json(f"Q248_xfer_{k}.json")
        if not x: continue
        c = collections.Counter(); n = 0
        for v in x["structures"].values():
            if v["status"] != "ship":
                n += 1
                for r in v.get("held_reasons", []) or [v.get("reason", "")]: c[r] += 1
        L.append(f"**{dict(PAGES)[k]}**: {n} of {len(x['structures'])} planned Z structures held. Reasons (a structure can have several): " + "; ".join(f"{r} x {m}" for r, m in c.most_common()) + ".\n")
    for k, lbl in PAGES:
        r = load_json(f"Q248_rule_{k}.json")
        if not r: continue
        h = {i: v["held"] for i, v in r["structures"].items() if v["status"] != "ship"}
        if h: L.append(f"**{lbl}, rule-based held**: " + "; ".join(f"`{i}` ({', '.join(x)})" for i, x in h.items()) + ".\n")
    for k in ("own_f", "comb_f"):
        c = load_json(f"Q248_cvh_{k}.json")
        if c: L.append(f"**{dict(PAGES)[k]}, CVH**: " + "; ".join(f"`{i}` {v['status']}" + (f" ({', '.join(v['held'])})" if v["held"] else "") for i, v in c.items()) + ".\n")
    L.append("## 9. Literature / sources checked (PubMed, web)\n")
    L.append("- Kearney R, Sawhney R, DeLancey JOL. Levator ani muscle anatomy evaluated by origin-insertion pairs. Obstet Gynecol 2004;104:168-73 (PMID 15229017, doi 10.1097/01.AOG.0000128906.61529.6b): origin / insertion pairs, no dimensions of the arch.\n"
             "- Stein TA, DeLancey JOL. Structure of the perineal membrane in females: gross and microscopic anatomy. Obstet Gynecol 2008;111:686-93 (PMID 18310372, doi 10.1097/AOG.0b013e318163a9a5): the membrane is continuous with the insertion of the arcus tendineus fasciae pelvis; "
             "a 3-D structure (dorsal / ventral part), no outline or thickness that could be built: perineal membrane NOT built.\n"
             "- DeLancey JOL. Anatomic aspects of vaginal eversion after hysterectomy. Am J Obstet Gynecol 1992;166:1717-28 (PMID 1615980): arcus tendineus fasciae pelvis from the pubic bone to the ischial spine.\n"
             "- Aithal Padur A et al. Morphometric analysis of patella and patellar ligament. Surg Radiol Anat 2021;43:2039-46 (PMID 34570285, doi 10.1007/s00276-021-02837-z): patellar ligament length 4.8 / 4.6 cm (right / left), range 3-6 cm; the table of widths / thickness is not in the retrievable text.\n"
             "- Basso O, Johnson DP, Amis AA. The anatomy of the patellar tendon. Knee Surg Sports Traumatol Arthrosc 2001;9:2-5 (PMID 11269580, doi 10.1007/s001670000133): fibres converge toward the tibial attachment; patellar apex 39 +- 6 % of the tendon width from the medial edge.\n"
             "- Occelli et al., Eur J Obstet Gynecol Reprod Biol 2001 (abstract only, via a web search): arcus tendineus fasciae pelvis about 10 cm in two fixed female pelves; used as a plausibility range only. A 2004 cadaver study (five female cadavers) found the structure absent / weak in 6 of 10 hemipelves: variable presence.\n"
             "- Sacrospinous ligament length 43.04 +- 6.58 mm (nine embalmed female hemipelves; 'Anatomical landmarks regarding sacrospinous colpopexy operations', web abstract, not verified against the paper): not used as input.\n"
             "- No PubMed / web source gave a width or thickness for the tendinous arch of levator ani, the arcus tendineus fasciae pelvis, the transverse perineal ligament, the anococcygeal ligament or the puboprostatic / pubovesical ligaments: their calibres are MODELLING CHOICES (stated on every card as such), "
             "which is why those cards say 'an estimate of position'.\n")
    (D / "Q248_audit_extra.md").write_text("\n".join(L))
    print("written", D / "Q248_audit_extra.md")


if __name__ == "__main__":
    main()
