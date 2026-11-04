#!/usr/bin/env python3
"""Q241: build the pose rig of a page (segments, joints, normal ranges, skinning weights) and put it into the page.

    python3 scripts/anatomy/q241/make_pose_rig.py KEY...            # KEY = own_m own_f comb_m comb_f base_m base_f (default all) -> data/anatomy/pose_rig_<KEY>.json (+ report in data/derived)
    python3 scripts/anatomy/q241/make_pose_rig.py --inject DIR...   # put the rig of each page dir into its html (and index.html) between the NMSK-POSE-RIG markers

The rig file holds one payload per page: {v, key, count, nv[], rig (json), w (weights)}; `--inject` writes {"v":1,"j":base64(zlib(rig json)),"w":base64(zlib(weights))} (decoded in the
browser with DecompressionStream).  Weights: for every skinned structure the segments it uses (palette) and, planar, k index planes + (k-1) weight planes (uint8; weight of influence 0 = 255 - sum),
deflate-compressed.  Rigid structures are listed per segment.  The geometry is checked against the page (structure count and per-structure vertex counts) when injecting."""
from __future__ import annotations
import base64, json, os, sys, time, zlib
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model as MD, rig as RG, skin as SK
from rom import ROM, rom_meta

REPO = MD.REPO
DATA = REPO / "data/anatomy"
DIRKEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}


def r3(x):
    return round(float(x), 3)


PRIOR = {}
MIX_STRIDE, PURE_STRIDE, MIX_THR, KNN = 6, 40, 0.97, 4


def dense_weights(o, nv, nseg):
    W = np.zeros((nv, nseg), np.float32)
    for j in range(o["idx"].shape[1]):
        np.add.at(W, (np.arange(nv), o["idx"][:, j]), o["w"][:, j])
    return W


def control_set(W):
    """control vertices whose weights are stored: every MIX_STRIDE-th vertex where the weights are mixed + every PURE_STRIDE-th vertex (anchors the pure zones); >= 4 (all of a tiny mesh)"""
    nv = len(W)
    idx = np.arange(nv)
    ctrl = ((W.max(1) < MIX_THR) & (idx % MIX_STRIDE == 0)) | (idx % PURE_STRIDE == 0)
    if nv <= 24 or ctrl.sum() < KNN:
        ctrl[:] = True if nv <= 24 else ctrl
        if ctrl.sum() < KNN:
            ctrl[:KNN] = True
    return ctrl


def decode_weights(v, ctrl, pal, ci_idx, ci_w, nseg_unused=None):
    """the viewer's reconstruction (pose.js buildSkin): every vertex takes the inverse-square-distance average of the weights of its KNN nearest control vertices (control vertices keep their own),
    then the 3 largest influences are renormalised.  -> (idx (nv,3) segment index, w (nv,3) uint8-quantised /255)"""
    from scipy.spatial import cKDTree
    nv = len(v)
    cv = np.where(ctrl)[0]
    npal = len(pal)
    Wc = np.zeros((len(cv), npal), np.float32)
    for k in range(ci_idx.shape[1]):
        np.add.at(Wc, (np.arange(len(cv)), ci_idx[:, k]), ci_w[:, k] / 255.0)
    tr = cKDTree(v[cv])
    k = min(KNN, len(cv))
    d, nn = tr.query(v, k=k)
    d = np.maximum(d.reshape(nv, k), 1e-3); nn = nn.reshape(nv, k)
    ww = 1.0 / (d * d); ww /= ww.sum(1, keepdims=True)
    R = (Wc[nn] * ww[:, :, None]).sum(1)
    R[cv] = Wc
    top = np.argsort(-R, axis=1, kind="stable")[:, :3]
    tw = np.take_along_axis(R, top, 1)
    tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
    q = np.round(tw * 255).astype(np.int32)
    q[:, 0] += 255 - q.sum(1)
    q = np.clip(q, 0, 255)
    sg = np.array(pal, np.int32)[top]
    return sg, q / 255.0


def encode_weights(M, out, RB):
    """-> (rigid list [[seg,[idx]]], skin list [[idx,nv,K,pal,off,nc]], blob bytes, decoded {idx: (seg (nv,3), w (nv,3))})
    blob per skinned structure: packbits(control mask) | K index planes (palette index of each control's influence k) | K-1 weight planes (uint8, weight of influence 0 = 255 - sum)"""
    rigid = {}
    skin, chunks, off = [], [], 0
    nseg = len(RB.segs)
    decoded = {}
    for x in M.S:
        i = x["idx"]; o = out[i]
        if o["kind"] == "rigid":
            rigid.setdefault(o["seg"], []).append(i)
            continue
        nv = len(o["idx"])
        W = dense_weights(o, nv, nseg)
        ctrl = control_set(W)
        cv = np.where(ctrl)[0]
        Wc = W[cv]
        top = np.argsort(-Wc, axis=1, kind="stable")[:, :3]
        tw = np.take_along_axis(Wc, top, 1)
        tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
        q = np.round(tw * 255).astype(np.int32)
        q[:, 0] += 255 - q.sum(1)
        q = np.clip(q, 0, 255)
        used = np.unique(top[q > 0])
        pal = sorted(int(s) for s in used)
        pm = {s: n_ for n_, s in enumerate(pal)}
        K = max(1, int((q > 0).any(0).nonzero()[0].max() + 1))
        pi = np.zeros((len(cv), K), np.uint8)
        for k in range(K):
            col = top[:, k]
            pi[:, k] = [pm.get(int(s), 0) for s in col]
            if k:
                pi[q[:, k] == 0, k] = pi[q[:, k] == 0, 0]
        b = np.packbits(ctrl).tobytes() + b"".join([pi[:, k].tobytes() for k in range(K)] + [q[:, k].astype(np.uint8).tobytes() for k in range(1, K)])
        skin.append([i, nv, K, pal, off, int(len(cv))]); chunks.append(b); off += len(b)
        ci_idx = pi.astype(np.int64); ci_w = np.zeros((len(cv), K)); ci_w[:] = q[:, :K]
        decoded[i] = decode_weights(M.S[i]["v"], ctrl, pal, ci_idx, ci_w)
    return [[s, v] for s, v in sorted(rigid.items())], skin, b"".join(chunks), decoded


def get_prior(key):
    """candidate segments per structure from the Base page of the same sex (limbs away from the trunk); None for the Base pages themselves"""
    if key.startswith("base"):
        return None
    pk = "base_f" if key.endswith("_f") else "base_m"
    if pk not in PRIOR:
        Mb = MD.Model(pk); RBb = RG.RigBuilder(Mb); RBb.build()
        PRIOR[pk] = SK.prior_from(Mb, RBb, SK.compute(Mb, RBb)[0])
    return PRIOR[pk]


def build(key, verbose=True):
    t0 = time.time()
    M = MD.Model(key)
    RB = RG.RigBuilder(M)
    rig = RB.build()
    prior = get_prior(key)
    out, st = SK.compute(M, RB, prior=prior)
    rigid, skin, blob, decoded = encode_weights(M, out, RB)
    # compact rig
    segs = [[s["id"], s["par"], s["side"], s["name"]] for s in rig["segments"]]

    def cj(j):
        d = dict(id=j["id"], name=j["name"], group=j["group"], side=j["side"], seg=j["seg"], par=j["par"], ref=j["ref"], c=[r3(v) for v in j["c"]],
                 dof=[dict(k=d_["k"], l=d_["l"], a=[round(float(v), 5) for v in d_["a"]], lo=d_["lo"], hi=d_["hi"], q0=round(d_["q0"], 2), rk=d_["rk"], **({"drv": d_["drv"]} if d_.get("drv") else {})) for d_ in j["dof"]])
        if j.get("driven"): d["driven"] = j["driven"]
        if j.get("down"): d["down"] = [round(v, 5) for v in j["down"]]
        if j.get("note"): d["note"] = j["note"]
        return d
    regions = [dict(id=r["id"], name=r["name"], group=r["name"], note=r.get("note", ""), levels=[dict(seg=L["seg"], par=L["par"], c=[r3(v) for v in L["c"]], label=L["label"]) for L in r["levels"]],
                    dof=[dict(k=d["k"], l=d["l"], a=[round(v, 5) for v in d["a"]], lo=d["lo"], hi=d["hi"], q0=0.0, rk=d["rk"], w=[round(v, 4) for v in d["w"]]) for d in r["dof"]]) for r in rig["regions"]]
    used = sorted({d["rk"] for j in rig["joints"] for d in j["dof"] if d.get("rk")} | {d["rk"] for r in rig["regions"] for d in r["dof"]})
    romt = {k: [ROM[k][0], ROM[k][1], ROM[k][2], ROM[k][3]] for k in used}
    nv = [len(x["v"]) for x in M.S]
    errs = {k: v["err"] for k, v in RB.K.notes.items() if v.get("err")}
    notes = "joint centres from the page's bones (hip / shoulder: head sphere fit RMS %s mm; ...); %d segments, %d joints, %d skinned structures of %d" % (
        "%.1f-%.1f" % (min(e["rms_mm"] for e in errs.values() if "rms_mm" in e), max(e["rms_mm"] for e in errs.values() if "rms_mm" in e)) if errs else "n/a", len(segs), len(rig["joints"]), len(skin), len(M.S))
    payload = dict(v=1, key=key, count=len(M.S), nv=nv, segs=segs, joints=[cj(j) for j in rig["joints"]], regions=regions, rom=romt, rom_meta=rom_meta(used), rigid=rigid, skin=skin, notes=notes)
    report = dict(key=key, label=MD.LABEL[key], seconds=round(time.time() - t0, 1), counts=dict(segments=len(segs), joints=len(rig["joints"]), regions=len(regions), structures=len(M.S), rigid=sum(len(g[1]) for g in rigid),
                  skinned=len(skin), rigid_vertices=int(sum(nv[i] for g in rigid for i in g[1])), skinned_vertices=int(sum(s[1] for s in skin))),
                  landmark_errors=errs, fit_rms={k: v for k, v in RB.info.items() if "rms" in k}, notes={k: v for k, v in RB.info.items() if "rms" not in k and not k.startswith("asis")},
                  rest_values_outside_range=[dict(joint=j["id"], dof=d["k"], q0=round(d["q0"], 1), lo=d["lo"], hi=d["hi"]) for j in rig["joints"] if not j.get("driven") for d in j["dof"] if not (d["lo"] <= d["q0"] <= d["hi"])])
    return payload, blob, report, (M, RB, rig, out, decoded)


def pack(payload, blob):
    j = zlib.compress(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)
    w = zlib.compress(blob, 9)
    return dict(v=1, j=base64.b64encode(j).decode("ascii"), w=base64.b64encode(w).decode("ascii")), len(j), len(w)


def write(key):
    payload, blob, report, _ = build(key)
    p, nj, nw = pack(payload, blob)
    DATA.mkdir(parents=True, exist_ok=True)
    f = DATA / ("pose_rig_%s.json" % key)
    f.write_text(json.dumps(dict(schema="nmsk.pose_rig/1", key=key, label=MD.LABEL[key], rig=payload, weights_zlib_b64=p["w"]), separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    report["embedded_kb"] = dict(rig_json_zlib=round(nj / 1024, 1), weights_zlib=round(nw / 1024, 1), total_base64=round((len(p["j"]) + len(p["w"])) / 1024, 1))
    report["weights_raw_kb"] = round(len(blob) / 1024, 1)
    (REPO / "data/derived" / ("Q241_rig_%s.json" % key)).write_text(json.dumps(report, indent=1, default=float), encoding="utf-8")
    print(key, "segments", report["counts"]["segments"], "skinned", report["counts"]["skinned"], "of", report["counts"]["structures"], "embedded KB", report["embedded_kb"], "seconds", report["seconds"], flush=True)
    return report


BEGIN, END = "<!-- NMSK-POSE-RIG begin -->", "<!-- NMSK-POSE-RIG end -->"


def inject(d: Path):
    key = DIRKEY.get(d.name)
    if key is None:
        raise SystemExit("unknown page dir %s (expected one of %s)" % (d.name, sorted(DIRKEY)))
    f = DATA / ("pose_rig_%s.json" % key)
    src = json.loads(f.read_text(encoding="utf-8"))
    payload = src["rig"]
    os.environ["Q241_SRC_" + key] = str(d.resolve())
    M = MD.Model(key)                       # the geometry of THIS page dir must be the one the rig was made for
    nv = [len(x["v"]) for x in M.S]
    if nv != payload["nv"]:
        raise SystemExit("%s: geometry differs from the rig's (structure / vertex counts): rebuild the rig with make_pose_rig.py %s" % (d, key))
    j = zlib.compress(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 9)
    block = BEGIN + '<script type="application/json" id="nmsk-pose-rig">' + json.dumps({"v": 1, "j": base64.b64encode(j).decode("ascii"), "w": src["weights_zlib_b64"]}, separators=(",", ":")) + "</script>" + END
    n = 0
    for h in sorted(d.glob("*.html")):
        s = h.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            continue
        i, k = s.index(BEGIN), s.index(END) + len(END)
        h.write_text(s[:i] + block + s[k:], encoding="utf-8")
        print("pose rig:", h, "%.0f KB" % (len(block) / 1024)); n += 1
    if not n:
        raise SystemExit("no page with the NMSK-POSE-RIG markers in %s" % d)


def main(argv):
    if argv and argv[0] == "--inject":
        for a in argv[1:]:
            inject(Path(a))
        return 0
    keys = argv or MD.KEYS
    for k in keys:
        write(k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
