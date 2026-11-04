#!/usr/bin/env python3
"""Q224 ship-diff / scope check of an own bundle (his Q217 -> Q224, her Q216 -> Q224): every entry the Q224 report does not list (replaced / removed) must be IDENTICAL (id, subject, record, mesh bytes) and keep its
position (ids are duplicated in the own bundles: entries are keyed by (id, occurrence)); every listed replaced entry must differ and keep its subject (= Source class); nothing is added.
Writes data/derived/Q224_vertex_diff_<body>.json; exits 1 on any violation.   python3 scripts/transfer/q224_vertex_diff.py m|f"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q224_common import BODIES  # noqa: E402


def keyed(B):
    seen, out, order = {}, {}, []
    for it in B.items:
        i = it["e"]["id"]
        k = (i, seen.get(i, 0))
        seen[i] = seen.get(i, 0) + 1
        out[k] = it
        order.append(k)
    return out, order


def main(body):
    cfg = BODIES[body]
    A, N = Bundle(cfg["src_bundle"]), Bundle(cfg["out_bundle"])
    rep = json.loads((REPO / f"data/derived/Q224_report_{body}.json").read_text())
    replaced = set(rep["replaced"]) | set(rep["muscles"]["changed"]) | set(rep["muscles"]["welded_zfill"])
    removed = {r["id"] for r in rep["removed"]}
    Ak, Ao = keyed(A)
    Nk, No = keyed(N)
    ident, unlisted, bad = 0, [], []
    kept_order = [k for k in Ao if k[0] not in removed]
    order_ok = [k for k in No] == kept_order
    for k in kept_order:
        if k not in Nk:
            bad.append(f"{k} missing in the new bundle")
            continue
        a, n = Ak[k], Nk[k]
        same = a["raw"] == n["raw"] and a["e"] == n["e"]
        if k[0] in replaced:
            if same:
                bad.append(f"{k[0]} listed as replaced but unchanged")
            if a["e"]["subject"] != n["e"]["subject"]:
                bad.append(f"{k[0]} subject changed")
        elif same:
            ident += 1
        else:
            unlisted.append(k[0])
    added = [k[0] for k in Nk if k not in Ak]
    out = dict(source=str(cfg["src_bundle"].relative_to(REPO)), new=str(cfg["out_bundle"].relative_to(REPO)), entries_old=len(A.items), entries_new=len(N.items), identical=ident, replaced=sorted(replaced),
               removed=sorted(removed), added=added, unlisted_changes=unlisted, problems=bad, order_kept=bool(order_ok), triangles_old=A.j["triangles"], triangles_new=N.j["triangles"],
               quantum_same=A.j["quantum_mm"] == N.j["quantum_mm"])
    (REPO / f"data/derived/Q224_vertex_diff_{body}.json").write_text(json.dumps(out, indent=1) + "\n")
    print(body, "identical", ident, "| replaced", len(replaced), "| removed", len(removed), "| added", added, "| unlisted", unlisted, "| problems", bad, "| order kept", order_ok)
    sys.exit(1 if (unlisted or bad or added or not order_ok) else 0)


if __name__ == "__main__":
    main(sys.argv[1])
