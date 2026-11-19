#!/usr/bin/env python3
"""Q229: per-tissue verification report for clinical/data/imaging_tissues.json.

Reads the per-value 'ver' blocks of the table (status, sources, statistic, previous value, one-line detail) and writes
data/derived/Q229_tissue_verification.json: per tissue and per value the old and new number, the % change, the status and the
sources, plus the totals (verified / derived / secondary_checked / assumption / recalled_unverified, changed by more than 10 %).

    python3 scripts/clinical/q229_tissue_verification.py            # write the report
    python3 scripts/clinical/q229_tissue_verification.py --check    # exit 1 if the report on disk is stale
"""
import json, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TABLE = REPO / "clinical" / "data" / "imaging_tissues.json"
OUT = REPO / "data" / "derived" / "Q229_tissue_verification.json"
STATUSES = ("verified", "derived", "secondary_checked", "assumption", "recalled_unverified")
FIELDS = (("ct", "hu", "HU"), ("mri", "pd", "relative PD"), ("mri", "t1", "ms"), ("mri", "t2", "ms"), ("mri", "t2s", "ms"))


def pct(prev, new):
    if prev in (None, 0) or new is None:
        return None
    return round((new - prev) / abs(prev) * 100.0, 2)


def build():
    t = json.loads(TABLE.read_text())
    refs = t["references"]
    tissues, totals = [], {s: 0 for s in STATUSES}
    big = []
    for c in t["classes"]:
        vals = []
        for part, f, unit in FIELDS:
            e = c[part]["ver"][f]
            new = c["ct"]["hu"] if part == "ct" else c["mri"]["pools"][0][f]
            ch = pct(e.get("prev"), new)
            row = {"part": part, "field": f, "unit": unit, "previous": e.get("prev"), "value": new, "change_pct": ch,
                   "changed_gt_10pct": ch is not None and abs(ch) > 10.0, "status": e["s"], "statistic": e.get("stat"),
                   "range": e.get("range") if e.get("range") else (c["ct"]["range"] if part == "ct" else None),
                   "sources": [{"key": k, "pmid": refs[k].get("pmid"), "doi": refs[k].get("doi"), "pmcid": refs[k].get("pmcid"),
                                "opened": ("PubMed record" if refs[k].get("pubmed_checked") else refs[k].get("opened"))} for k in e["src"]],
                   "detail": e["d"]}
            totals[e["s"]] += 1
            if row["changed_gt_10pct"]:
                big.append({"tissue": c["key"], "part": part, "field": f, "previous": e.get("prev"), "value": new, "change_pct": ch})
            vals.append(row)
        tissues.append({"key": c["key"], "label": c["label"], "ct_status": c["ct"]["status"], "mri_status": c["mri"]["status"],
                        "counts": {s: sum(1 for v in vals if v["status"] == s) for s in STATUSES}, "values": vals})
    n = sum(totals.values())
    return {
        "schema": "nmsk.imaging_tissue_verification.v1", "task": "Q229", "date": t["verification_summary"]["date"],
        "table": "clinical/data/imaging_tissues.json",
        "method": ("Each numeric table value (CT HU; MRI PD, T1, T2, T2* at 1.5 T) was looked up in PubMed abstracts, open PMC full-text paragraphs and the Consensus "
                   "abstract index. 'verified' = the number (mean / median / range) is printed in an abstract or full-text paragraph that was read; the viewer uses the "
                   "statistic named in 'statistic'. Table cells of the key papers (Gold 2004, Stanisz 2005, Bottomley 1984, de Bazelaire 1.5 T, Lamba 2014, IT'IS database "
                   "reference PDFs) could not be opened (no egress to the publishers/PMC/IT'IS pages from the sandbox; the full-text tool drops tables), so those values stay unverified."),
        "definitions": t["verification_summary"]["definition"],
        "totals": {"numeric_values": n, **totals, "still_unverified": totals["secondary_checked"] + totals["assumption"] + totals["recalled_unverified"],
                   "verified_or_derived": totals["verified"] + totals["derived"], "changed_gt_10pct": len(big)},
        "changed_gt_10pct": big,
        "tissues": tissues,
    }


def main():
    rep = build()
    s = json.dumps(rep, indent=1, ensure_ascii=False) + "\n"
    if "--check" in sys.argv:
        ok = OUT.is_file() and OUT.read_text() == s
        print("fresh" if ok else "STALE")
        sys.exit(0 if ok else 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(s)
    tt = rep["totals"]
    print(f"{OUT.relative_to(REPO)}: {tt['numeric_values']} values, verified {tt['verified']}, derived {tt['derived']}, secondary {tt['secondary_checked']}, "
          f"assumption {tt['assumption']}, recalled_unverified {tt['recalled_unverified']}, changed>10% {tt['changed_gt_10pct']}")


if __name__ == "__main__":
    main()
