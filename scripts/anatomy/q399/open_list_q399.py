#!/usr/bin/env python3
"""Q399: the verifier's open-defect list after Q399 (data/derived/Q394_open_defects_<page>.json, read by
scripts/anatomy/q394/verify_under_skin_q394.py).

    python3 scripts/anatomy/q399/open_list_q399.py --final FINAL.json --ref REF.json --fix FIX.json [--skin SKIN.json] --out OUT.json

FINAL.json: the verifier's --json of the patched page (Q399 test); REF.json: the same test on the page as it was after Q394 (the
values nothing may exceed); FIX.json / SKIN.json: fix_q399.py / skin_q399.py reports. Every (state, structure) of FINAL is listed
with its numbers, its Q394 value under the same test, whether it is worse than that, and the reason it is left.
"""
from __future__ import annotations

import argparse, json, re, time
from pathlib import Path

DIGIT_RE = re.compile(r"digits_of_(hand|foot)|perionyx|phalan|interphalangeal|digital|of_foot_[lr]$|_of_hand_[lr]$")
FACE_RE = re.compile(r"philtrum|oral|labial|mental|buccal|nasal|orbital|parotid|auricular|temporal|occipital")


def reason(k, e, ref, fix, state, rest_has):
    if state != "rest" and rest_has:
        return "outside at rest too (see the rest entry)"
    f = fix.get(k)
    why = []
    if e["max_mm"] < 0.5:
        why.append("residual < 0.5 mm")
    if f is None:
        why.append("not outside in the census before Q399's fix (newly counted after the skin step) -- not refitted")
    else:
        b = f["best"]
        fits = f.get("fits") or {}
        if b != "cur":
            why.append(f"Q399 kept candidate '{b}' (best over the eight states)")
        if not fits:
            why.append("no rule-based refit candidate (a bone / cartilage is never moved, or the Q398 depth-remap refit failed its "
                       "guards: move, volume / area, flips, bone)")
        else:
            st = {n: (x.get("status"), x.get("reason")) for n, x in fits.items()}
            why.append("refit tried: " + "; ".join(f"{n} {s[0]}{(' (' + s[1] + ')') if s[1] else ''}" for n, s in st.items()))
    reg = e.get("region", "")
    if DIGIT_RE.search(k) or DIGIT_RE.search(reg.replace(" ", "_")):
        why.append("digit: judged by the per-digit test; the soft structures lie on the phalanges under a thin / close source-fit "
                   "skin, and the per-digit outward skin offset was not accepted (it made a structure worse in some state)")
    elif FACE_RE.search(reg.replace(" ", "_")):
        why.append("face: the mouth group's outward skin offset was not accepted (it made a structure worse in some state); bone / "
                   "cartilage is not moved")
    if state != "rest":
        why.append("pose only: the rig was not changed in Q399 (fat / fascia / lymph weights are Q398's; muscles, vessels and nerves "
                   "keep theirs -- skin weights kinked them in the browser pose verifier, Q398 section 4)")
    return "; ".join(w for w in why if w)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", required=True)
    ap.add_argument("--ref", required=True)
    ap.add_argument("--fix", required=True)
    ap.add_argument("--skin")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    fin = json.loads(Path(a.final).read_text())
    ref = json.loads(Path(a.ref).read_text())["states"]
    fix = json.loads(Path(a.fix).read_text())["structures"]
    out = []
    for s, c in fin["states"].items():
        for k, e in sorted(c.items(), key=lambda kv: -kv[1]["max_mm"]):
            r = ref.get(s, {}).get(k)
            rv = {"n": r["n"], "max_mm": r["max_mm"]} if r else {"n": 0, "max_mm": 0.0}
            worse = e["n"] > rv["n"] or e["max_mm"] > rv["max_mm"] + 0.005
            out.append(dict(state=s, id=k, n=e["n"], nv=e["nv"], max_mm=e["max_mm"], p95_mm=e["p95_mm"], region=e["region"],
                            q394_same_test=rv, worse_than_q394=worse,
                            reason=reason(k, e, ref, fix, s, k in fin["states"].get("rest", {}))))
    doc = dict(schema="nmsk.q394.open_defects.v3", page=fin["page"], generated=time.strftime("%Y-%m-%d"),
               note=("Q394 open-defect list, updated by Q399 (completed outside test: single-sheet skin and per-digit test; structure "
                     "candidates judged in all eight states; Q398 skin groups undone where they made structures worse). Every (state, "
                     "structure) still outside the skin, its numbers, its Q394 value under the same test, and the reason. Read by "
                     "scripts/anatomy/q394/verify_under_skin_q394.py."),
               open=out)
    Path(a.out).write_text(json.dumps(doc, indent=0) + "\n", encoding="utf-8")
    print(f"Q399 open list {fin['page']}: {len(out)} entries, worse than Q394 {sum(e['worse_than_q394'] for e in out)} -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
