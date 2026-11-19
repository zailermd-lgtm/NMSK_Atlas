#!/usr/bin/env python3
"""Q217: scope check of the Q217 own-male bundle against the Q214 bundle: every entry that the report does not list (replaced / added / removed) must be IDENTICAL (id, subject, record, mesh bytes) and keep its order; every
listed replaced entry must differ; replaced entries keep their subject (= Source class), added ones carry xfer_zan2vhm_arm_q217.  Writes data/derived/Q217_vertex_diff.json; exits 1 on any violation."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402

A_DIR, N_DIR = "build/viewer_m_hr_q214", "build/viewer_m_hr_q217"


def main():
    A, N = Bundle(REPO / A_DIR), Bundle(REPO / N_DIR)
    rep = json.loads((REPO / "data/derived/Q217_own_report.json").read_text())
    rep_ids, add_ids, rem_ids = set(rep["replaced"]), set(rep["added"]), set(rep["removed"])
    kept = [it for it in A.items if it["e"]["id"] not in rem_ids]
    ident, unlisted, bad = 0, [], []
    order_ok = len(N.items) == len(kept) + len(add_ids)
    for k, it in enumerate(kept):
        if k >= len(N.items):
            break
        n = N.items[k]
        i = it["e"]["id"]
        if n["e"]["id"] != i:
            order_ok = False
            bad.append(f"position {k}: {i} vs {n['e']['id']}")
            continue
        same = it["raw"] == n["raw"] and it["e"] == n["e"]
        if i in rep_ids:
            if same:
                bad.append(f"{i} listed as replaced but unchanged")
            if it["e"]["subject"] != n["e"]["subject"]:
                bad.append(f"{i} subject changed")
        elif same:
            ident += 1
        else:
            unlisted.append(i)
    na = {it["e"]["id"]: (k, it) for k, it in enumerate(N.items[len(kept):], start=len(kept))}
    for i in add_ids:
        if i not in na or na[i][1]["e"]["subject"] != "xfer_zan2vhm_arm_q217":
            bad.append(f"{i} added entry missing / wrong subject")
    out = dict(source=A_DIR, new=N_DIR, entries_old=len(A.items), entries_new=len(N.items), identical=ident, replaced=sorted(rep_ids), added=sorted(add_ids), removed=sorted(rem_ids), unlisted_changes=unlisted,
               problems=bad, order_kept=bool(order_ok), triangles_old=A.j["triangles"], triangles_new=N.j["triangles"], quantum_same=A.j["quantum_mm"] == N.j["quantum_mm"])
    (REPO / "data/derived/Q217_vertex_diff.json").write_text(json.dumps(out, indent=1) + "\n")
    print("identical", ident, "| replaced", len(rep_ids), "| added", len(add_ids), "| removed", len(rem_ids), "| unlisted", unlisted, "| problems", bad, "| order kept", order_ok)
    sys.exit(1 if (unlisted or bad or not order_ok) else 0)


if __name__ == "__main__":
    main()
