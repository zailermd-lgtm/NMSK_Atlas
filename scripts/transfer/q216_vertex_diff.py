#!/usr/bin/env python3
"""Q216: scope check of the Q216 own-female bundle against the bundle it came from (Q215): every entry that the report does not list (as changed or as a welded Z-fill continuation) must be IDENTICAL (same
position, id, subject, structure record and mesh bytes); every listed entry must differ; no entry changes its subject (= Source class).  Writes data/derived/Q216_vertex_diff.json; exits 1 on any violation."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

A_DIR, N_DIR = "build/viewer_f_hr_q215", "build/viewer_f_hr_q216"


def main():
    A, N = Bundle(REPO / A_DIR), Bundle(REPO / N_DIR)
    rep = json.loads((REPO / "data/derived/Q216_report.json").read_text())
    welded = set(rep["welded"])
    listed = set(rep["ops"]) | welded
    ident, changed, unlisted, listed_but_same = 0, [], [], []
    assert len(A.items) == len(N.items), "entry count changed"
    subj_same = True
    for k, it in enumerate(A.items):
        n = N.items[k]
        assert it["e"]["id"] == n["e"]["id"], (k, it["e"]["id"], n["e"]["id"])
        same = it["raw"] == n["raw"] and it["e"] == n["e"]
        ident += int(same)
        subj_same &= it["e"]["subject"] == n["e"]["subject"]
        if not same:
            changed.append(it["e"]["id"])
            if it["e"]["id"] not in listed:
                unlisted.append(it["e"]["id"])
        elif it["e"]["id"] in listed:
            listed_but_same.append(it["e"]["id"])
    out = dict(source=A_DIR, new=N_DIR, entries=len(N.items), identical=ident, changed=len(changed), changed_ids=sorted(changed), unlisted_changes=unlisted, listed_but_unchanged=listed_but_same,
               subjects_unchanged=bool(subj_same), welded=sorted(welded), triangles_source=A.j["triangles"], triangles_new=N.j["triangles"], quantum_same=A.j["quantum_mm"] == N.j["quantum_mm"],
               subject_and_attribution_unchanged=bool(A.j["subject"] == N.j["subject"] and A.j["attribution"] == N.j["attribution"]))
    (REPO / "data/derived/Q216_vertex_diff.json").write_text(json.dumps(out, indent=1) + "\n")
    print("identical", ident, "/", len(A.items), "| changed", len(changed), "| unlisted", unlisted, "| listed but unchanged", listed_but_same, "| subjects unchanged", subj_same)
    sys.exit(1 if (unlisted or listed_but_same or not subj_same) else 0)


if __name__ == "__main__":
    main()
