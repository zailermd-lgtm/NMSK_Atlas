#!/usr/bin/env python3
"""Q215: scope check of the Q215 own-female bundle against the bundle it came from (Q214): every entry that the report does not list as replaced must be IDENTICAL (same position, id, subject,
structure record and mesh bytes); the replaced entries must carry the Q215 subject.  Writes data/derived/Q215_vertex_diff.json ({unlisted_changes: [] ...}); exits 1 if anything outside the list changed."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

A_DIR, N_DIR = "build/viewer_f_hr_q214", "build/viewer_f_hr_q215"


def main():
    A, N = Bundle(REPO / A_DIR), Bundle(REPO / N_DIR)
    rep = json.loads((REPO / "data/derived/Q215_report.json").read_text())
    listed = set(rep["replaced"])
    ident, changed, unlisted, listed_but_same = 0, [], [], []
    assert len(A.items) == len(N.items), "entry count changed"
    for k, it in enumerate(A.items):
        n = N.items[k]
        assert it["e"]["id"] == n["e"]["id"], (k, it["e"]["id"], n["e"]["id"])
        same = it["raw"] == n["raw"] and it["e"] == n["e"]
        ident += int(same)
        if not same:
            changed.append(it["e"]["id"])
            if it["e"]["id"] not in listed:
                unlisted.append(it["e"]["id"])
        elif it["e"]["id"] in listed:
            listed_but_same.append(it["e"]["id"])
    subj_ok = all(N.items[N.find(i)[0]]["e"]["subject"] == "xfer_vhm2vhf_sep_q215" for i in listed)
    out = dict(source=A_DIR, new=N_DIR, entries=len(N.items), identical=ident, changed=len(changed), changed_ids=sorted(changed), unlisted_changes=unlisted, listed_but_unchanged=listed_but_same,
               replaced_carry_q215_subject=bool(subj_ok), triangles_source=A.j["triangles"], triangles_new=N.j["triangles"], quantum_same=A.j["quantum_mm"] == N.j["quantum_mm"])
    (REPO / "data/derived/Q215_vertex_diff.json").write_text(json.dumps(out, indent=1) + "\n")
    print("identical", ident, "/", len(A.items), "| changed", len(changed), "| unlisted", unlisted, "| listed but unchanged", listed_but_same, "| subject ok", subj_ok)
    sys.exit(1 if (unlisted or listed_but_same or not subj_ok) else 0)


if __name__ == "__main__":
    main()
