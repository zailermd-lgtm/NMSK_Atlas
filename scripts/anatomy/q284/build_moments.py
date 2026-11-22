#!/usr/bin/env python3
"""Q284: moment arms of every muscle about every pose-rig joint it crosses, computed from each page's own meshes (scripts/anatomy/q284/moments.py),
checked against the cited textbook action of the muscle (data/anatomy/muscle_actions_q283.json, the Learn panel's own table) and against the
published moment-arm statements in data/anatomy/moment_arm_literature_q284.json (every statement quoted verbatim from its source).

    python3 scripts/anatomy/q284/build_moments.py [KEY...]       # KEY = own_m own_f comb_m comb_f base_m base_f (default all)
                                                                # -> data/anatomy/moment_arms_<KEY>.json + data/derived/Q284_moment_arms_<KEY>.json (report)
    python3 scripts/anatomy/q284/build_moments.py --inject DIR... # put the page's block into its html between the NMSK-MOMENTS markers

The page block {v, key, ang, s: {structure id: {j: {joint: [dofs, sweep dof, angles, {dof: [mm...]}]}, x: {joint: reason}, f: [flags],
w: {joint: wrap radius mm}, cv: [cited-action checks], lv: [literature checks]}}, lit: {ref: {...}}} is read by the Learn panel."""
from __future__ import annotations
import base64
import glob
import json
import re
import sys
import time
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "q241"))
import moments as MO  # noqa: E402
import model as MD  # noqa: E402
import rig as RG  # noqa: E402
from fk import default_pose  # noqa: E402

REPO = MD.REPO
DATA = REPO / "data/anatomy"
DIRKEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
BEGIN, END = "<!-- NMSK-MOMENTS begin -->", "<!-- NMSK-MOMENTS end -->"
SPINE = {"lumbar", "thoracic", "cervical"}
MAX_MM = 150
SECONDARY_FRAC = 0.2      # a secondary component is reported as such when |r| >= 20 % of the largest component of that joint at that angle


def jbase(jid):
    return re.sub(r"_(r|l)$", "", jid)


# ---------------------------------------------------------------- page structure -> data/muscles key (same rule as the Learn panel's resolve())
def load_learn():
    return json.loads((REPO / "viewer/learn/learn_data.json").read_text(encoding="utf-8"))["m"]


def resolve(sid, M):
    s = re.sub(r"^zan_", "", sid.lower())
    if s in M:
        return s, None
    cix = {}
    for b, m in M.items():
        for c in m.get("cp", []):
            cix.setdefault(c["c"], []).append((b, c["c"]))
    mm = re.match(r"^(.*?)_(r|l)(?:_(.+))?$", s)
    if not mm:
        return None, None
    b, rest = mm.group(1), mm.group(3)
    if b in M:
        if rest and any(c["c"] == rest for c in M[b].get("cp", [])):
            return b, rest
        return b, None
    for cand in (b, re.sub(r"_muscle$", "", b)):
        hit = cix.get(cand)
        if hit and len(hit) == 1:
            return hit[0]
    for key in sorted(M, key=len, reverse=True):      # e.g. 'lateral_head_of_triceps_brachii' -> triceps_brachii, part 'lateral_head' when it is one
        if len(key) > 5 and key in b:
            part = b.replace(key, "").strip("_").replace("_of", "").strip("_")
            return key, part if any(c["c"] == part for c in M[key].get("cp", [])) else None
    return None, None


# ---------------------------------------------------------------- checks
def cited_checks(rows, res):
    """computed sign vs the cited textbook action (Learn table rows of this muscle / part)"""
    out = []
    for row in rows:
        for mv in row["mv"]:
            js = mv[0] if isinstance(mv[0], list) else [mv[0]]
            for jn in js:
                hit = None
                for jid, v in res.items():
                    if jbase(jid) == jn or jid == jn:
                        hit = (jid, v)
                if not hit:
                    continue
                jid, v = hit
                if mv[1] not in v["r"]:
                    continue
                vals = v["r"][mv[1]]
                sgn = [np.sign(x) * mv[2] for x in vals]
                if jn in SPINE and len(mv) > 3:
                    sgn = [s * (1 if res.get("_side") != "l" else -1) for s in sgn]
                verdict = "agrees" if all(s > 0 for s in sgn) else "disagrees" if all(s < 0 for s in sgn) else "agrees at some angles"
                out.append([jid, mv[1], mv[2], verdict, row.get("q", "")[:120], row.get("src", "")])
    return out


def lit_checks(base, part, sid, res, L, extra):
    out = []
    for e in L["entries"]:
        if base not in e["muscles"] and not any(re.search(p, sid) for p in e.get("structure_re", [])):
            continue
        if e.get("parts") and part not in e["parts"] and not any(re.search(p, sid) for p in e.get("structure_re", [])):
            continue
        jid = next((j for j in res if not j.startswith("_") and jbase(j) == e["joint"]), None)
        if jid is None:
            continue
        v = res[jid]
        if e["dof"] not in v["r"]:
            continue
        r = dict(zip(v["angles"], v["r"][e["dof"]]))
        kind, verdict, shown = e["test"], "", ""
        if kind == "peak_range":
            sel = [x * e["sign"] for x in v["r"][e["dof"]]]
            pk = max(sel)
            lo, hi = e["range_mm"]
            verdict = "agrees" if lo <= pk <= hi else ("agrees in sign, larger" if pk > hi else "agrees in sign, smaller" if pk > 0 else "disagrees")
            shown = "peak %.0f mm over %s deg" % (pk, "/".join("%g" % a for a in v["angles"]))
        elif kind == "near_zero_at":
            a = e["angle"]
            if a not in r:
                continue
            ref = max(abs(x[v["angles"].index(a)]) for x in v["r"].values())
            frac = abs(r[a]) / ref if ref else 0
            verdict = "agrees" if frac < SECONDARY_FRAC else "disagrees"
            shown = "%+.1f mm at %g deg (%.0f %% of the largest component)" % (r[a], a, 100 * frac)
        elif kind == "sign_at":
            a = e["angle"]
            if a not in r:
                continue
            verdict = "agrees" if np.sign(r[a]) == e["sign"] and abs(r[a]) > 0.5 else "disagrees"
            shown = "%+.1f mm at %g deg" % (r[a], a)
        elif kind == "increases_with_sweep":
            vals = v["r"][e["dof"]]
            verdict = "agrees" if vals[-1] > vals[0] else "disagrees"
            shown = "%+.1f -> %+.1f mm (%g -> %g deg)" % (vals[0], vals[-1], v["angles"][0], v["angles"][-1])
        elif kind == "sign_all":
            vals = v["r"][e["dof"]]
            verdict = "agrees" if all(np.sign(x) == e["sign"] for x in vals) else "disagrees" if all(np.sign(x) == -e["sign"] for x in vals) else "agrees at some angles"
            shown = ", ".join("%+.0f" % x for x in vals) + " mm at " + "/".join("%g" % a for a in v["angles"]) + " deg"
        elif kind == "abs_range_at":
            a = e["angle"]
            if a not in r:
                continue
            lo, hi = e["range_mm"]
            verdict = "agrees" if lo <= abs(r[a]) <= hi else "outside the range"
            shown = "%+.1f mm at %g deg" % (r[a], a)
        elif kind == "liftoff":
            lf = extra.get("liftoff", {}).get(jid)
            if lf is None:
                continue
            tg = e["targets_deg"]
            near = min(tg, key=lambda k: abs(tg[k] - lf))
            verdict = "closest to the %s value (%g deg)" % (near, tg[near]) if abs(tg[near] - lf) <= 10 else "differs from both"
            shown = "path leaves the hip wrap at %g deg of flexion" % lf
        elif kind == "elbow90_gt_elbow0":
            pair = extra.get("sup_elbow")
            if not pair:
                continue
            verdict = "agrees" if pair[1] > pair[0] else "disagrees"
            shown = "supination moment arm %+.1f mm with the elbow at 0 deg, %+.1f mm at 90 deg" % tuple(pair)
        out.append([e["id"], jid, e["dof"], verdict, shown])
    return out


def liftoff(rig, path, jid):
    """first hip flexion angle (0..120 step 1 deg) at which the span across the joint no longer touches the wrap sphere"""
    w = path["wraps"].get(jid)
    if not w:
        return None
    pose0 = default_pose(rig)
    j = next(x for x in rig["joints"] if x["id"] == jid)
    pr = MO.crossing_pair(rig, path["seg"], jid)
    if pr is None:
        return None
    from fk import fk
    for a in range(0, 121):
        P = {"joints": dict(pose0["joints"]), "regions": dict(pose0["regions"])}
        q = [0.0] * len(j["dof"]); q[0] = float(a); P["joints"][jid] = q
        Mx = fk(rig, P)
        A = Mx[path["seg"][pr[0]]][:3, :3] @ path["p"][pr[0]] + Mx[path["seg"][pr[0]]][:3, 3]
        B = Mx[path["seg"][pr[1]]][:3, :3] @ path["p"][pr[1]] + Mx[path["seg"][pr[1]]][:3, 3]
        Mp = Mx[w["par"]]
        c = Mp[:3, :3] @ np.array(w["c"]) + Mp[:3, 3]
        straight = np.linalg.norm(B - A)
        n0 = Mp[:3, :3] @ np.array(w["n0"])
        L = MO.wrapped(A, B, c, w["R"], n0) if w.get("u") is None else MO.wrapped_cyl(A, B, c, Mp[:3, :3] @ np.array(w["u"]), w["R"], n0)
        if L - straight < 0.05:
            return a
    return None


# ---------------------------------------------------------------- one page
def stored_rig(key):
    p = json.loads((DATA / ("pose_rig_%s.json" % key)).read_text(encoding="utf-8"))["rig"]
    return p


def build(key, verbose=True):
    t0 = time.time()
    M = MD.Model(key)
    RB = RG.RigBuilder(M)
    rig = RB.build()
    st = stored_rig(key)
    for a, b in zip(rig["joints"], st["joints"]):     # the rig the page carries must be the one we compute on
        if a["id"] != b["id"] or np.abs(np.array(a["c"]) - np.array(b["c"])).max() > 0.01:
            raise SystemExit("%s: rebuilt rig differs from data/anatomy/pose_rig_%s.json at %s" % (key, key, a["id"]))
    B = MO.Bones(RB.K, RB)
    LM = load_learn()
    A = json.loads((DATA / "muscle_actions_q283.json").read_text(encoding="utf-8"))
    rows_by = {}
    for row in A["rows"]:
        rows_by.setdefault(row["m"], []).append(row)
    L = json.loads((DATA / "moment_arm_literature_q284.json").read_text(encoding="utf-8"))
    S = {}
    cov = {}
    totals = dict(muscles=0, with_joint=0, none=0)
    cited_tot = {"agrees": 0, "disagrees": 0, "agrees at some angles": 0}
    for x in M.S:
        if x["sys"] != "muscle":
            continue
        totals["muscles"] += 1
        tv = MO.tendon_for(M.S, x)
        v = x["v"] if tv is None else np.vstack([x["v"], tv])
        if len(v) < 30:
            continue
        path = MO.muscle_path(v, B, rig)
        flags = list(path["flags"])
        if tv is not None:
            flags.append("joined to its separately meshed tendon")
        for e, nm in zip(path["ends"], ("first", "second")):
            if e[0] == "free":
                flags.append("%s end touches no bone (attachment not on this mesh)" % nm)
        res, notc = {}, {}
        for kind, jid in MO.crossed(rig, path["seg"]):
            if kind == "j":
                n = MO.crossing_count(rig, path["seg"], jid)
                if n != 1:
                    notc[jid] = "the path crosses this joint %d times (several slips or interleaved segments in one mesh): not computable" % n
                    continue
            ang = [0.0, 45.0, 90.0] if kind == "j" and jbase(jid) in ("hip", "knee", "elbow", "shoulder") else None
            res[jid] = MO.moment_arms(rig, path, kind, jid, angles=ang)
        for jid in list(res):                              # no human moment arm reaches 150 mm: such a value is a path that does not reach its bones
            if max(abs(x) for v in res[jid]["r"].values() for x in v) > MAX_MM:
                notc[jid] = "implausible path (a moment arm above %d mm): the mesh does not reach its bones on this page, not computable" % MAX_MM
                del res[jid]
        digit = re.compile(r"^(f\d_|t\d_|thumb_)")
        if any(digit.match(j) for j in notc):            # one mesh for several digits: no digit joint of it is trustworthy
            for jid in [j for j in res if digit.match(j)]:
                notc[jid] = "one mesh for several digits (tendon slips not separated): the path re-crosses other digit joints, not computable"
                del res[jid]
        extra = {"liftoff": {}}
        for jid in res:
            if jbase(jid) == "hip" and jid in path["wraps"]:
                extra["liftoff"][jid] = liftoff(rig, path, jid)
        fa = next((j for j in res if jbase(j) == "forearm"), None)
        el = next((j for j in res if jbase(j) == "elbow"), None)
        if fa and el:
            vals = []
            for ea in (0.0, 90.0):
                base = default_pose(rig)
                ej = next(j for j in rig["joints"] if j["id"] == el)
                base["joints"] = dict(base["joints"]); base["joints"][el] = [ea]
                vals.append(MO.moment_arms(rig, path, "j", fa, base=base, angles=[0.0])["r"]["sup"][0])
            extra["sup_elbow"] = vals
        b, part = resolve(x["id"], LM)
        rows = [r for r in rows_by.get(b, []) if not r.get("c") or r["c"] == part or part is None and r.get("c") is None]
        res_side = dict(res); res_side["_side"] = x.get("side")
        cv = cited_checks(rows, res_side) if b else []
        for c in cv:
            cited_tot[c[3]] += 1
        lv = lit_checks(b or "", part, x["id"].lower(), res, L, extra)
        if res:
            totals["with_joint"] += 1
        else:
            totals["none"] += 1
        partial = bool(flags) or bool(notc)
        for jid in set(res) | set(notc):
            jb = jbase(jid)
            c = cov.setdefault(jb, {"computed": 0, "partial": 0, "not_computable": 0, "reasons": {}})
            if jid in notc:
                c["not_computable"] += 1
                k = reason_key(notc[jid])
                c["reasons"][k] = c["reasons"].get(k, 0) + 1
            elif partial:
                c["partial"] += 1
                for f in flags:
                    k = re.sub(r"^\w+_[rl]: ", "", f)
                    c["reasons"][k] = c["reasons"].get(k, 0) + 1
            else:
                c["computed"] += 1
        S[x["id"]] = dict(b=b, c=part, side=x.get("side"), j={k: [v["dofs"], v["sweep"], v["angles"], v["r"]] for k, v in res.items()},
                          x=notc, f=flags, w={k: round(w["R"], 1) for k, w in path["wraps"].items()}, cv=cv, lv=lv,
                          lo={k: v for k, v in extra["liftoff"].items() if v is not None}, se=extra.get("sup_elbow"),
                          n=int(len(path["p"])), d=int(path.get("dropped", 0)))
    payload = dict(v=1, key=key, label=MD.LABEL[key], round="Q284", method=L["method"], lit={e["id"]: {k: e[k] for k in ("cite", "doi", "pmid", "quote", "note") if e.get(k)} for e in L["entries"]},
                   s=S)
    report = dict(key=key, label=MD.LABEL[key], seconds=round(time.time() - t0, 1), totals=totals, coverage_by_joint=cov, cited_action_check=cited_tot)
    if verbose:
        print(key, totals, "cited", cited_tot, "%.0f s" % (time.time() - t0), flush=True)
    return payload, report


def reason_key(txt):
    return ("one mesh for several digits" if "several digits" in txt else "implausible path (mesh does not reach its bones)" if "implausible" in txt
            else "path re-crosses the joint")


def coverage_from(payload):
    """per-joint coverage from a committed moment_arms_<key>.json (same rules as build())"""
    cov = {}
    for sid, x in payload["s"].items():
        partial = bool(x["f"]) or bool(x["x"])
        for jid in set(x["j"]) | set(x["x"]):
            jb = jbase(jid)
            c = cov.setdefault(jb, {"computed": 0, "partial": 0, "not_computable": 0, "reasons": {}})
            if jid in x["x"]:
                c["not_computable"] += 1
                k = reason_key(x["x"][jid])
                c["reasons"][k] = c["reasons"].get(k, 0) + 1
            elif partial:
                c["partial"] += 1
                for f in x["f"]:
                    k = re.sub(r"^\w+_[rl]: ", "", f)
                    c["reasons"][k] = c["reasons"].get(k, 0) + 1
            else:
                c["computed"] += 1
    return cov


def write(key):
    payload, report = build(key)
    (DATA / ("moment_arms_%s.json" % key)).write_text(json.dumps(payload, separators=(",", ":"), ensure_ascii=False, default=float), encoding="utf-8")
    (REPO / "data/derived" / ("Q284_moment_arms_%s.json" % key)).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
    return report


def inject(d: Path):
    key = DIRKEY.get(d.name)
    if key is None:
        raise SystemExit("unknown page dir %s" % d)
    payload = json.loads((DATA / ("moment_arms_%s.json" % key)).read_text(encoding="utf-8"))
    j = zlib.compress(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)
    block = BEGIN + '<script type="application/json" id="nmsk-moments">' + json.dumps({"v": 1, "z": base64.b64encode(j).decode("ascii")}, separators=(",", ":")) + "</script>" + END
    n = 0
    for h in sorted(d.glob("*.html")):
        s = h.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            continue
        i, k = s.index(BEGIN), s.index(END) + len(END)
        h.write_text(s[:i] + block + s[k:], encoding="utf-8")
        print("moments:", h, "%.0f KB" % (len(block) / 1024)); n += 1
    if not n:
        raise SystemExit("no page with the NMSK-MOMENTS markers in %s" % d)


def main(argv):
    if argv and argv[0] == "--report":             # rebuild the per-joint coverage of the reports from the committed data, no recompute
        for k in (argv[1:] or MD.KEYS):
            p = json.loads((DATA / ("moment_arms_%s.json" % k)).read_text(encoding="utf-8"))
            rf = REPO / "data/derived" / ("Q284_moment_arms_%s.json" % k)
            rep = json.loads(rf.read_text(encoding="utf-8"))
            rep["coverage_by_joint"] = coverage_from(p)
            rf.write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=float), encoding="utf-8")
            print("report:", rf.name)
        return 0
    if argv and argv[0] == "--inject":
        for a in argv[1:]:
            inject(Path(a))
        return 0
    for k in (argv or MD.KEYS):
        write(k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
