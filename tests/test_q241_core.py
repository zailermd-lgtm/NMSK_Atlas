"""Q241: the pose maths of viewer/pose/pose.js (NMSKPoseCore) under node against the python reference (scripts/anatomy/q241/fk.py, make_pose_rig.py)."""
import base64
import copy
import json
import shutil
import subprocess
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
import fk as FK  # noqa: E402

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
const C = new Function(src + '; return NMSKPoseCore;')();
const job = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = {};
if (job.fk){
  const P = C.prepare(job.fk.rig); let maxerr = 0;
  job.fk.poses.forEach(function(pp, k){ const pose = {j: pp.joints, r: pp.regions}, M = []; C.fk(P, pose, M);
    M.forEach(function(m, i){ const e = job.fk.exp[k][i]; for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++) maxerr = Math.max(maxerr, Math.abs(m[r*4+c] - e[r][c])); }); });
  out.fk_maxerr = maxerr;
  const d0 = C.defaultPose(P), M0 = []; C.fk(P, d0, M0);
  out.rest_maxerr = Math.max.apply(null, M0.map(function(m){ const I = [1,0,0,0,0,1,0,0,0,0,1,0]; return Math.max.apply(null, Array.from(m).map(function(v, k){ return Math.abs(v - I[k]); })); }));
  const an = C.anatomicalPose(P); let bad = 0;
  job.fk.rig.joints.forEach(function(j){ if (j.driven) return; an.j[j.id].forEach(function(v, k){ if (v < j.dof[k].lo - 1e-9 || v > j.dof[k].hi + 1e-9) bad++; }); });
  out.anat_out_of_range = bad;
}
if (job.dec){
  out.dec = job.dec.map(function(t){
    const o = {nv: t.nv, nc: t.nc, kc: t.kc, pal: Int16Array.from(t.pal), off: 0, blob: Uint8Array.from(Buffer.from(t.blob, 'base64'))};
    C.decodeSkin(o, Float32Array.from(t.pos));
    let wd = 0, sgbad = 0;
    for (let v = 0; v < t.nv; v++){
      const w = [255 - o.w[0][v] - o.w[1][v], o.w[0][v], o.w[1][v]].map(function(x){ return x / 255; });
      for (let k = 0; k < 3; k++) wd = Math.max(wd, Math.abs(w[k] - (t.exp_w[v][k] || 0)));
      if (w[0] < 0.97 && t.pal[o.idx[0][v]] !== t.exp_sg[v][0] && Math.abs(w[0] - w[1]) > 0.02) sgbad++;
    }
    // skin kernel against numpy-style reference
    const PM = new Float64Array(12 * t.pal.length); for (let q = 0; q < t.pal.length; q++) PM.set(t.M[q], 12 * q);
    const rp = Float32Array.from(t.pos), rn = new Float32Array(rp.length); for (let v = 0; v < t.nv; v++) rn[3*v+1] = 1;
    const op = new Float32Array(rp.length), on = new Float32Array(rp.length); C.skin(o, PM, rp, rn, op, on);
    let perr = 0;
    for (let v = 0; v < t.nv; v++){ const w = [255 - o.w[0][v] - o.w[1][v], o.w[0][v], o.w[1][v]]; let e = [0, 0, 0];
      for (let k = 0; k < 3; k++){ const m = t.M[o.idx[k][v]], x = rp[3*v], y = rp[3*v+1], z = rp[3*v+2]; e[0] += w[k]/255*(m[0]*x + m[1]*y + m[2]*z + m[3]); e[1] += w[k]/255*(m[4]*x + m[5]*y + m[6]*z + m[7]); e[2] += w[k]/255*(m[8]*x + m[9]*y + m[10]*z + m[11]); }
      perr = Math.max(perr, Math.abs(e[0] - op[3*v]), Math.abs(e[1] - op[3*v+1]), Math.abs(e[2] - op[3*v+2])); }
    const rg = new Float32Array(rp.length), rgn = new Float32Array(rp.length); C.rigid(t.M[0], rp, rn, rg, rgn);
    let rerr = 0; const m0 = t.M[0]; for (let v = 0; v < t.nv; v++) rerr = Math.max(rerr, Math.abs(m0[0]*rp[3*v] + m0[1]*rp[3*v+1] + m0[2]*rp[3*v+2] + m0[3] - rg[3*v]));
    return {maxw: wd, sgbad: sgbad, skin_err: perr, rigid_err: rerr, nrm_unit: Math.abs(Math.hypot(on[0], on[1], on[2]) - 1) < 1e-4};
  });
}
console.log(JSON.stringify(out));
"""


def run(job):
    p = subprocess.run([NODE, "-e", HARNESS, str(REPO / "viewer/pose/pose.js")], input=json.dumps(job), capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def rig_of(key):
    return json.loads((REPO / ("data/anatomy/pose_rig_%s.json" % key)).read_text(encoding="utf-8"))


def poses_for(rig, n=5, seed=0):
    r = dict(segments=[dict(id=s[0], par=s[1], side=s[2]) for s in rig["segs"]], joints=rig["joints"], regions=rig["regions"])
    P = FK.default_pose(r)
    rng = np.random.default_rng(seed)
    poses = [P, FK.anatomical_pose(r)]
    for _ in range(n):
        Q = copy.deepcopy(P)
        for j in r["joints"]:
            if not j.get("driven"):
                Q["joints"][j["id"]] = [float(rng.uniform(d["lo"], d["hi"])) for d in j["dof"]]
        for g in r["regions"]:
            Q["regions"][g["id"]] = [float(rng.uniform(d["lo"], d["hi"])) for d in g["dof"]]
        poses.append(Q)
    return r, poses


@pytest.mark.parametrize("key", ["base_m", "comb_f", "own_m"])
def test_forward_kinematics_matches_python_and_rest_is_identity(key):
    rig = rig_of(key)["rig"]
    r, poses = poses_for(rig)
    exp = [[m.tolist() for m in FK.fk(r, p)] for p in poses]
    o = run({"fk": {"rig": rig, "poses": poses, "exp": exp}})
    assert o["fk_maxerr"] < 1e-8
    assert o["rest_maxerr"] < 1e-9                       # the model pose is reproduced exactly (every segment matrix = identity)
    assert o["anat_out_of_range"] == 0                   # the anatomical preset stays inside every range


def test_skin_decoder_and_kernels_match_python():
    sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
    import make_pose_rig as MR
    d = rig_of("base_m")
    rig = d["rig"]
    blob = zlib.decompress(base64.b64decode(d["weights_zlib_b64"]))
    import model as MD
    M = MD.Model("base_m")
    byid = {x["id"]: x["idx"] for x in M.S}
    sk = {s[0]: s for s in rig["skin"]}
    tests = []
    rng = np.random.default_rng(1)
    for name in ("biceps_brachii_r", "zan_skin_anterior_region_of_thigh_r", "flexor_digitorum_profundus_l"):
        i = byid[name]
        s = sk[i]
        nv, K, pal, off, nc = s[1], s[2], s[3], s[4], s[5]
        mb = (nv + 7) // 8
        b = blob[off:off + mb + nc * (2 * K - 1)]
        mask = np.unpackbits(np.frombuffer(b[:mb], np.uint8))[:nv].astype(bool)
        p = mb
        pi = np.zeros((nc, K), np.int64)
        q = np.zeros((nc, K))
        for k in range(K):
            pi[:, k] = np.frombuffer(b[p:p + nc], np.uint8); p += nc
        for k in range(1, K):
            q[:, k] = np.frombuffer(b[p:p + nc], np.uint8); p += nc
        q[:, 0] = 255 - q[:, 1:].sum(1)
        sg, w = MR.decode_weights(M.S[i]["v"], mask, pal, pi, q)
        mats = []
        for _ in pal:
            R = FK.rot(rng.normal(size=3), float(rng.uniform(-40, 40)))
            m = np.zeros((3, 4)); m[:, :3] = R; m[:, 3] = rng.normal(size=3) * 20
            mats.append(m.ravel().tolist())
        tests.append(dict(nv=nv, kc=K, pal=pal, nc=nc, blob=base64.b64encode(b).decode(), pos=M.S[i]["v"].astype(np.float32).ravel().tolist(), exp_sg=sg.tolist(), exp_w=w.tolist(), M=mats))
    o = run({"dec": tests})
    for r in o["dec"]:
        assert r["maxw"] <= 0.02, r                      # weights of the decoder = python decoder (1/255 quantisation, rare ties)
        assert r["sgbad"] <= 3, r
        assert r["skin_err"] < 5e-3 and r["rigid_err"] < 1e-3 and r["nrm_unit"], r
