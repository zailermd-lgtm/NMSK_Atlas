"""Q224 final phase: stage-1 bundle (veins, duplicate bones) + the accepted muscle operations (q224_muscles cache) -> build/viewer_<body>_hr_q224 + data/derived/Q224_report_<body>.json."""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q216_common as C  # noqa: E402
from scripts.transfer import q216_fix as X  # noqa: E402
from scripts.transfer import q224_muscles as M  # noqa: E402
from scripts.transfer.q224_common import BODIES, SCRATCH, jdump, DERIVED  # noqa: E402


def muscle_badge(name, res, vol0, vol1, mv, len0, len1, ov):
    parts = []
    for st in res["steps"]:
        k, inf = st["kind"], st["info"]
        if k == "reconnect":
            r = "; ".join(f"a detached piece {x['gap_mm']} mm from the belly ({100 * x['small_part_area_share']:.0f} % of the surface) joined by a loft of the two facing 3 mm sections (+{x['bridge_added_cm3']} cm3)" for x in inf["rounds"])
            parts.append(f"Reconnected: {r}.")
        elif k == "extend":
            pl = "; ".join(f"the {en} end was {p['audit_before_mm']} mm from any bone and was pulled {p['applied_mm']} mm along the muscle's course onto {p['bone']}" for en, p in inf["pulled"].items())
            parts.append(f"Extended through the missing CT block: {pl} (Q214 attachment pull, other end held, pushed out of bone / skin; length {len0} -> {len1} mm).")
        elif k == "dome":
            dm = "; ".join(f"{d['axis']}={d['plane_mm']} plane {d['area_mm2']} mm2" for d in inf["dome"])
            ref = " (the facet was first subdivided to <= 3.6 mm edges)" if inf.get("refined") else ""
            parts.append(f"Flat cut face(s) at the CT block edge ({dm}) replaced by a dome of {inf['amplitude_mm']} mm height{ref}.")
    return ("Q224 block-edge clean-up (Source class unchanged): " + " ".join(parts) +
            f" Volume {round(vol1, 1)} cm3 (Q217/Q216 mesh {round(vol0, 1)} cm3); surface moved from the old mesh median {mv['new_to_old_median_mm']} mm, p95 {mv['new_to_old_p95_mm']} mm, max {mv['max_mm']} mm "
            f"({ov[1]} % of its volume inside other muscles, was {ov[0]} %). Where the muscle was cut at a CT block edge the true continuation is NOT measured: only the bone-reach extension and the dome are estimates; "
            "a position and boundary estimate, not a segmentation.")


def final(body):
    cfg = BODIES[body]
    t0 = time.time()
    B = Bundle(SCRATCH / f"stage1_{body}")
    n_stage1 = len(B.items)
    env = X.Env(B)
    log = lambda *x: print(*x, flush=True)
    cache = SCRATCH / f"muscles_{body}"
    results = {}
    if cache.exists():
        for p in sorted(cache.glob("*.pkl")):
            r = pickle.loads(p.read_bytes())
            results[r["id"]] = r
    acc = {sid: r for sid, r in results.items() if r.get("accepted")}
    log(f"muscle results {len(results)}, accepted {len(acc)}")
    page = env.page
    accepted = dict(acc)
    kept_reasons = {sid: r["why"] for sid, r in results.items() if not r.get("accepted")}
    ov0 = page.overlap_state({})
    ov1 = ov0
    for rnd in range(4):
        ov1 = page.overlap_state({sid: (r["v"], r["f"]) for sid, r in accepted.items()})
        bad = []
        for sid in accepted:
            o0, o1 = ov0.get(sid, 0.0), ov1.get(sid, 0.0)
            if o1 > X.OVERLAP_MAX or (o1 > o0 + X.OVERLAP_RISE_MAX and o1 > 40.0):
                bad.append((sid, o0, o1))
        # neighbours (not candidates) that this set pushes across the 40 / 60 % lines
        for mid, o1 in ov1.items():
            if mid in accepted:
                continue
            o0 = ov0.get(mid, 0.0)
            if (o1 > 60.0 >= o0) or (o1 > 40.0 >= o0 and o1 > o0 + 5.0):
                bad.append((f"neighbour:{mid}", o0, o1))
        log(f"overlap round {rnd}: {len(accepted)} accepted, bad {bad}")
        if not bad:
            break
        for sid, o0, o1 in bad:
            if sid.startswith("neighbour:"):
                continue
            kept_reasons[sid] = [f"{o1} % of its volume inside the other muscles after all changes (before {o0} %; gate {X.OVERLAP_MAX:g}, rise <= {X.OVERLAP_RISE_MAX:g} above 40 %)"]
            accepted.pop(sid, None)
        nb = [b for b in bad if b[0].startswith("neighbour:")]
        if nb and rnd == 3:
            log("neighbours still across the lines:", nb)
    changed = {}
    for sid, r in accepted.items():
        k = B.find(sid)
        assert len(k) == 1, (sid, k)
        k = k[0]
        it = B.items[k]
        v0, f0 = B.mesh(it)
        vol0, vol1 = C.volume_cm3(v0, f0), C.volume_cm3(r["v"], r["f"])
        mv = X.surface_move(r["v"], r["f"], v0, f0)
        len0, len1 = r["before"]["length_mm"], r["after"]["length_mm"]
        ov = [ov0.get(sid), ov1.get(sid)]
        txt = muscle_badge(it["e"]["rec"].get("name", sid), r, vol0, vol1, mv, len0, len1, ov)
        B._set(it, r["v"], r["f"])
        old = it["e"]["rec"].get("procedural_badge")
        it["e"]["rec"] = {**it["e"]["rec"], "procedural_badge": ((old or "") + " " + txt).strip()}
        changed[sid] = dict(volume_cm3=[round(vol0, 2), round(vol1, 2)], length_mm=[len0, len1], triangles=[int(len(f0)), int(len(r["f"]))], move=mv, overlap_vol_pct=ov, steps=[s["kind"] for s in r["steps"]],
                            ends_pulled={en: p for s in r["steps"] if s["kind"] == "extend" for en, p in s["info"]["pulled"].items()}, caps_before=r["before"]["flat_caps"], caps_after=r["after"]["flat_caps"],
                            islands_before=len(r["before"]["islands"]), islands_after=len(r["after"]["islands"]), subject=it["e"]["subject"], cumulative_guards=r.get("cumulative_guards"), skipped_steps=r["skipped"], badge_added=txt)
    # Z-fill continuations re-welded to a muscle whose end was pulled
    welded = {}
    for sid, r in accepted.items():
        for zid, (zn, rinfo) in (r.get("zfill_new") or {}).items():
            k = B.find(zid)[0]
            zit = B.items[k]
            zf_ = B.mesh(zit)[1]
            txt = (f"Q224: re-welded to the muscle whose end was pulled onto its bone (the seam moved with it): seam gap p95 {rinfo['gap_before']['p95']} -> {rinfo['gap_after']['p95']} mm, the piece moved "
                   f"{rinfo['move_mean_mm']} mm on average (max {rinfo['move_max_mm']} mm), its far end held on its bone; unchanged otherwise.")
            B._set(zit, zn, zf_)
            zit["e"]["rec"] = {**zit["e"]["rec"], "procedural_badge": ((zit["e"]["rec"].get("procedural_badge") or "") + " " + txt).strip()}
            welded[zid] = dict(base=sid, info=rinfo, badge_added=txt)
    # vein badges are rebuilt here from the stage-1 report (subject-aware text, photograph check)
    from scripts.transfer import q224_fix as FX
    rep1 = json.loads((SCRATCH / f"stage1_{body}_report.json").read_text())
    for sid in rep1["replaced"]:
        if sid in rep1["veins"]:
            it = B.items[B.find(sid)[0]]
            old = it["e"]["rec"].get("procedural_badge") or ""
            tail_at = old.find("Rule-based interpolation, not a segmentation.")
            tail = old[tail_at + len("Rule-based interpolation, not a segmentation."):] if tail_at >= 0 else ""
            new_b = FX.vein_badge(it["e"]["rec"].get("name", sid), rep1["veins"][sid], it["e"]["subject"], FX.VEIN_EXTRA.get((body, sid), ""))
            it["e"]["rec"] = {**it["e"]["rec"], "procedural_badge": (new_b + tail).strip()}
    out = cfg["out_bundle"]
    nbytes = B.write(out)
    rep = json.loads((SCRATCH / f"stage1_{body}_report.json").read_text())
    rep.update(muscles=dict(candidates=len(results), accepted=len(accepted), changed=changed, kept={sid: why for sid, why in kept_reasons.items()}, welded_zfill=welded),
               bundle=dict(path=str(out.relative_to(REPO)), entries=[n_stage1, len(B.items)], triangles=int(sum(it["e"]["nf"] for it in B.items)), bytes=nbytes))
    jdump(rep, DERIVED / f"Q224_report_{body}.json")
    log(f"wrote {out}: {len(B.items)} entries, {rep['bundle']['triangles']} triangles, muscles changed {len(changed)} [{time.time() - t0:.0f} s]")
