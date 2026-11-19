#!/usr/bin/env python3
"""Q214: scope check of the two Q214 own bundles against the bundles they came from (male Q212, female Q213): every entry of the source must be IDENTICAL in the new bundle (same position, id,
subject, structure record and mesh bytes -- the bundle.bin of the source is a byte prefix of the new one); the only differences are the entries Q214 ADDS.  Writes data/derived/Q214_vertex_diff.json
({body: {unlisted_changes: [] ...}}); exits 1 if anything outside the added list changed."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

PAIRS = (("vhm", "build/viewer_m_hr_q212", "build/viewer_m_hr_q214"), ("vhf", "build/viewer_f_hr_q213", "build/viewer_f_hr_q214"))


def main():
    out, bad_total = {}, 0
    for body, a, b in PAIRS:
        A, N = Bundle(REPO / a), Bundle(REPO / b)
        ident, unlisted = 0, []
        for k, it in enumerate(A.items):
            n = N.items[k]
            same = it["raw"] == n["raw"] and it["e"] == n["e"]
            ident += int(same)
            if not same:
                unlisted.append(it["e"]["id"])
        added = [dict(id=n["e"]["id"], subject=n["e"]["subject"], cat=n["e"]["cat"], nv=n["e"]["nv"], nf=n["e"]["nf"]) for n in N.items[len(A.items):]]
        binA = (REPO / a / "bundle.bin").read_bytes()
        binN = (REPO / b / "bundle.bin").read_bytes()
        prefix = binN[: len(binA)] == binA
        rep = json.loads((REPO / f"data/derived/Q214_{body}_report.json").read_text())
        listed = sorted(rep["added"])
        out[body] = dict(source=a, new=b, entries_source=len(A.items), entries_new=len(N.items), identical=ident, unlisted_changes=unlisted, bin_prefix_identical=bool(prefix),
                         added=added, added_equals_report=sorted(x["id"] for x in added) == listed,
                         triangles_source=A.j["triangles"], triangles_new=N.j["triangles"], quantum_same=A.j["quantum_mm"] == N.j["quantum_mm"])
        bad_total += len(unlisted) + int(not prefix) + int(not out[body]["added_equals_report"])
        print(body, "identical", ident, "/", len(A.items), "| unlisted changes", unlisted, "| bin prefix identical", prefix, "| added", [x["id"] for x in added])
    (REPO / "data/derived/Q214_vertex_diff.json").write_text(json.dumps(out, indent=1) + "\n")
    sys.exit(1 if bad_total else 0)


if __name__ == "__main__":
    main()
