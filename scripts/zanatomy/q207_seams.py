"""Q207 seam / contact stage: contacts of the skin slabs (a vertex of one patch on the surface of another in the Z source, q202_contact) whose TRUE distance in the fitted state (vertex to the surface of the
other patch, not to its source partner point -- two patches that slide along each other still touch) is above a gate are closed by the sparse least-squares solve of q207_weld; contacts that
still touch are left alone (reported as sliding contacts)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_contact as K  # noqa: E402
from scripts.zanatomy import q207_weld as WD  # noqa: E402


def classify(ids, V, faces, raw, gate_partner=2.0, log=print):
    """-> list of dict(contact, partner_gap, true_gap) for the contacts with partner gap > gate_partner"""
    rd = {i: {"v": raw[i], "f": faces[i]} for i in ids}
    by = {i: {"v": V[i], "f": faces[i]} for i in ids}
    cons = K.contacts(rd, ids)
    g = K.gaps(by, ids, cons)
    pq = {}
    out = []
    for c, gg in zip(cons, g):
        if gg <= gate_partner:
            continue
        pi, a, pj, vi, w, d0 = c
        B = ids[pj]
        if B not in pq:
            pq[B] = trimesh.Trimesh(V[B], faces[B], process=False)
        cl, dist, tid = trimesh.proximity.closest_point(pq[B], V[ids[pi]][a:a + 1])
        out.append({"c": c, "partner_gap": float(gg), "true_gap": float(dist[0]), "closest": cl[0], "tid": int(tid[0]), "A": ids[pi], "B": B})
    return out, cons, g


def true_gap_constraints(items, ids, faces, V, min_true=1.5):
    """constraints (pa, a, [(pb, vertex, weight)]) pulling the vertex onto the nearest point of the other patch's surface"""
    cons = []
    sel = []
    for it in items:
        if it["true_gap"] <= min_true:
            continue
        pi, a, pj, vi, w, d0 = it["c"]
        B = it["B"]
        tri = faces[B][it["tid"]]
        T = V[B][tri]
        bc = trimesh.triangles.points_to_barycentric(T[None], it["closest"][None])[0]
        bc = np.clip(bc, 0, 1)
        bc /= bc.sum()
        cons.append((pi, int(a), [(ids.index(B), int(q), float(wq)) for q, wq in zip(tri, bc) if wq > 1e-6]))
        sel.append(it)
    return cons, sel


def weld_true_gaps(ids, V, faces, raw, min_true=1.5, ring=True, log=print, **kw):
    items, cons_all, g = classify(ids, V, faces, raw, log=log)
    tc, sel = true_gap_constraints(items, ids, faces, V, min_true)
    log(f"   contacts with partner gap > 2 mm: {len(items)}; true gap > {min_true} mm: {len(tc)}")
    if not tc:
        return V, {"closed": 0, "items": items}
    # free patches: those in a constraint and their border neighbours
    inv = {i: k for k, i in enumerate(ids)}
    free = {ids[pa] for pa, a, ps in tc} | {ids[p] for pa, a, ps in tc for p, q, w in ps}
    bp = WD.border_pairs({i: raw[i] for i in ids}, ids)
    if ring:
        free |= {ids[pa] for pa, a, ps in bp if ids[pa] in free for p, q, w in ps} | {ids[p] for pa, a, ps in bp for p, q, w in ps if ids[pa] in free}
        free |= {ids[pa] for pa, a, ps in bp if any(ids[p] in free for p, q, w in ps)}
    cons = bp + tc
    new = WD.solve(V, faces, ids, cons, free, gate_gap=0.8, log=log, **kw)
    V2 = dict(V)
    V2.update(new)
    return V2, {"closed": len(tc), "items": items, "free": sorted(free)}
