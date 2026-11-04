#!/usr/bin/env python3
"""Q283: build the Learn panel's data block from the project's own cited data, and check the derivations.

Inputs (all already in the repo, nothing invented here):
  data/muscles/<region>/<muscle>_r.json (+ midline files without a side)  names, attachments, innervation, actions, compartments
  data/anatomy/muscle_actions_q283.json   derivation table: quoted action -> pose-rig degrees of freedom
  data/anatomy/muscle_groups_q283.json    named textbook groups
  data/anatomy/pose_rig_*.json            the joints / dofs that exist on the six pages

Checks (exit 1 on any failure): every action-table quote occurs verbatim in its source (the muscle's own 'actions', or the
cited quote); every muscle / compartment / group member exists in data/muscles; every joint / dof exists in at least one
page rig. Output: viewer/learn/learn_data.json (compact; synced into both templates by scripts/sync_learn_q283.py).

    python3 scripts/anatomy/q283/build_learn.py          # write
    python3 scripts/anatomy/q283/build_learn.py --check  # exit 1 if the output is stale or a check fails
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = REPO / "viewer/learn/learn_data.json"
SPINE = {"lumbar", "thoracic", "cervical"}
HEADS = {"m": {}}


def base_of(mid: str) -> str:
    return re.sub(r"_(r|l)$", "", mid)


def pretty_ids(ids):
    return [re.sub(r"_+", " ", str(i)).replace(" n ", " n. ").strip() for i in ids]


def load_muscles():
    out = {}
    for f in sorted(glob.glob(str(REPO / "data/muscles/*/*.json"))):
        p = Path(f)
        if p.name == "muscle_index.json" or p.stem.endswith("_l"):
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict) or "id" not in d:
            continue
        out[base_of(d["id"])] = d
    return out


def rig_vocab():
    v = set()
    for f in glob.glob(str(REPO / "data/anatomy/pose_rig_*.json")):
        rig = json.loads(Path(f).read_text(encoding="utf-8"))["rig"]
        for j in rig["joints"]:
            if j.get("driven"):
                continue
            for x in j["dof"]:
                v.add((base_of(j["id"]), x["k"]))
        for r in rig["regions"]:
            for x in r["dof"]:
                v.add((r["id"], x["k"]))
    return v


def build():
    errs = []
    M = load_muscles()
    A = json.loads((REPO / "data/anatomy/muscle_actions_q283.json").read_text(encoding="utf-8"))
    G = json.loads((REPO / "data/anatomy/muscle_groups_q283.json").read_text(encoding="utf-8"))
    global HEADS
    HEADS = json.loads((REPO / "data/anatomy/muscle_heads_q293.json").read_text(encoding="utf-8"))
    for hm in HEADS["m"]:
        if hm not in M:
            errs.append(f"heads: {hm} not in data/muscles")
    vocab = rig_vocab()
    rows_by = {}
    for i, row in enumerate(A["rows"]):
        m = row["m"]
        if m not in M:
            errs.append(f"row {i}: muscle {m} not in data/muscles"); continue
        d = M[m]
        comps = {c["id"].split(d["id"] + "_", 1)[-1]: c for c in d.get("functional_compartments", [])}
        if row.get("c") and row["c"] not in comps:
            errs.append(f"row {i}: compartment {row['c']} not in {m}")
        src = row["src"]
        if src == "actions":
            if not any(row["q"] in a for a in d.get("actions", [])):
                errs.append(f"row {i}: quote not verbatim in {m} actions: {row['q']!r}")
        elif src.startswith("cite:"):
            c = A["cites"].get(src[5:])
            if not c or row["q"] not in c["quote"]:
                errs.append(f"row {i}: quote not in cite {src}")
        else:
            errs.append(f"row {i}: unknown src {src}")
        for mv in row["mv"]:
            js = mv[0] if isinstance(mv[0], list) else [mv[0]]
            for j in js:
                if (j, mv[1]) not in vocab:
                    errs.append(f"row {i}: {j}.{mv[1]} is in no page rig")
            if mv[2] not in (1, -1):
                errs.append(f"row {i}: sign must be +-1")
            if len(mv) > 3 and js[0] not in SPINE:
                errs.append(f"row {i}: mirror flag only for spine regions")
        rows_by.setdefault(m, []).append({k: row[k] for k in ("c", "q", "src", "mv", "note", "back") if row.get(k) is not None})
    na = {}
    for x in A.get("not_animated", []):
        if x["m"] not in M:
            errs.append(f"not_animated: {x['m']} not in data/muscles")
        na.setdefault(x["m"], []).append({k: x[k] for k in ("c", "what", "why") if x.get(k)})
    nl = {}
    for reason, ms in A.get("none_lists", {}).items():
        if reason not in A["none_reasons"]:
            errs.append(f"none_lists: unknown reason {reason}")
        for mm in ms:
            if mm not in M:
                errs.append(f"none_lists: {mm} not in data/muscles")
            nl[mm] = reason
    for g in G["groups"]:
        for mem in g["members"]:
            if mem not in M:
                errs.append(f"group {g['id']}: member {mem} not in data/muscles")

    muscles = {}
    for b, d in sorted(M.items()):
        at = d.get("attachments", {})
        inn = d.get("innervation", {}) or {}
        comps = []
        for c in d.get("functional_compartments", []):
            suf = c["id"].split(d["id"] + "_", 1)[-1]
            if suf == "main" and len(d.get("functional_compartments", [])) == 1:
                continue
            comps.append({"c": suf, "n": c.get("name", suf), "f": c.get("function_note", ""), "i": c.get("innervation_branch", "")})
        muscles[b] = {
            "n": d.get("name_common") or b.replace("_", " "), "ta": d.get("name_ta", ""), "rg": d.get("region", ""),
            "o": [at.get("origin_bone", ""), at.get("origin_landmark", "")], "in": [at.get("insertion_bone", ""), at.get("insertion_landmark", "")],
            "nv": pretty_ids(inn.get("nerve", []) if isinstance(inn.get("nerve"), list) else [inn.get("nerve")] if inn.get("nerve") else []),
            "rt": inn.get("root_levels", ""), "a": d.get("actions", []), "cp": comps, "s": d.get("source", ""),
            "mv": rows_by.get(b, []),
        }
        if b in na:
            muscles[b]["na"] = na[b]
        if b in HEADS["m"]:                                   # Q293: every head / origin (data/anatomy/muscle_heads_q293.json)
            muscles[b]["hd"] = [{"c": x["c"], "n": x["n"], "o": x["o"], "src": x["src"]} for x in HEADS["m"][b]]
        if b in HEADS.get("variants", {}):
            muscles[b]["hv"] = HEADS["variants"][b]
        if not rows_by.get(b):
            muscles[b]["nr"] = nl.get(b, "unrigged")
    data = {"schema": "nmsk.learn.v1", "round": "Q283",
            "src_doc": "built by scripts/anatomy/q283/build_learn.py from data/muscles, data/anatomy/muscle_actions_q283.json, data/anatomy/muscle_groups_q283.json",
            "cites": A["cites"], "none_reasons": A["none_reasons"], "groups_source": G["source"], "groups": G["groups"], "m": muscles}
    return data, errs


def main() -> int:
    data, errs = build()
    for e in errs:
        print("ERROR:", e)
    if errs:
        return 1
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n"
    n_mv = sum(1 for m in data["m"].values() if m["mv"])
    msg = f"{len(data['m'])} muscles, {n_mv} with a mapped action, {len(data['groups'])} groups, {len(text) // 1024} KB"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print("out of date:", OUT.relative_to(REPO)); return 1
        print("up to date:", msg); return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print("wrote", OUT.relative_to(REPO), msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
