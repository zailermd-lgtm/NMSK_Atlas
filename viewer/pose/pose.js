/* Joint POSE controls (Q241): per joint sliders with the normal range of motion as hard bounds, a kinematic skeleton, linear-blend skinning of the soft tissue. One controller for both viewers.
   POSE PREVIEW: a kinematic approximation. The bones move rigidly with their segment (joint centres / axes fitted to this page's own bones, see data/anatomy/pose_rig.json and
   docs/pose_rom_table.md); soft tissue follows by skinning weights from the distance to each segment's bones; no collision, no volume preservation, no soft tissue simulation.
   The ranges of motion are population AVERAGES (AAOS / AMA style) and some are assumptions (docs/pose_rom_table.md).
   The engine is reached only through the adaptor E:
     page()        -> string (localStorage key suffix)         count() -> number of structures (page order)        nverts(i) -> vertex count of structure i
     rest(i)       -> {pos:Float32Array, nrm:Float32Array}  the REST geometry (read only; made lazily and cached by the adaptor)
     live(i)       -> {pos, nrm}  the arrays this controller writes the posed geometry into (three.js: the geometry's own attributes; WebGL: a private copy)
     touch(i)      -> called after structure i was written (upload to the GPU)      commit(ids) -> after a batch: bounding boxes, caches, labels, redraw (ids = changed structure indices)
     toolbar + toolClass (where the Pose button goes)   isPhone()   afterRest() optional hook when the pose returned to the model pose
   Nothing here edits the data: the pose is a display state (saved per page in localStorage, guarded). */
var NMSKPoseCore = (function(){
  "use strict";
  var D2R = Math.PI / 180;
  function rotM(a, deg){
    var l = Math.hypot(a[0], a[1], a[2]) || 1, x = a[0] / l, y = a[1] / l, z = a[2] / l, t = deg * D2R, c = Math.cos(t), s = Math.sin(t), u = 1 - c;
    return [c + x*x*u, x*y*u - z*s, x*z*u + y*s,  y*x*u + z*s, c + y*y*u, y*z*u - x*s,  z*x*u - y*s, z*y*u + x*s, c + z*z*u];
  }
  function mul3(A, B){
    return [A[0]*B[0] + A[1]*B[3] + A[2]*B[6], A[0]*B[1] + A[1]*B[4] + A[2]*B[7], A[0]*B[2] + A[1]*B[5] + A[2]*B[8],
            A[3]*B[0] + A[4]*B[3] + A[5]*B[6], A[3]*B[1] + A[4]*B[4] + A[5]*B[7], A[3]*B[2] + A[4]*B[5] + A[5]*B[8],
            A[6]*B[0] + A[7]*B[3] + A[8]*B[6], A[6]*B[1] + A[7]*B[4] + A[8]*B[7], A[6]*B[2] + A[7]*B[5] + A[8]*B[8]];
  }
  function tr3(A){ return [A[0], A[3], A[6], A[1], A[4], A[7], A[2], A[5], A[8]]; }
  function mv3(A, v){ return [A[0]*v[0] + A[1]*v[1] + A[2]*v[2], A[3]*v[0] + A[4]*v[1] + A[5]*v[2], A[6]*v[0] + A[7]*v[1] + A[8]*v[2]]; }
  var I3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];
  /* a rig dict (see rig.py) -> lookup tables */
  function prepare(rig){
    var P = {rig:rig, byseg:{}, lev:{}, jid:{}, nseg:rig.segs.length};
    rig.joints.forEach(function(j, i){ P.byseg[j.seg] = i; P.jid[j.id] = j; });
    rig.regions.forEach(function(r, ri){ r.levels.forEach(function(L, k){ P.lev[L.seg] = [ri, k]; }); });
    return P;
  }
  function jointR(j, q){
    var R = I3, k;
    for (k = 0; k < j.dof.length; k++) R = mul3(R, rotM(j.dof[k].a, q[k]));
    return R;
  }
  function elevation(j, q){
    var v = mv3(jointR(j, q), j.down), d = j.down;
    return Math.acos(Math.max(-1, Math.min(1, v[0]*d[0] + v[1]*d[1] + v[2]*d[2]))) / D2R;
  }
  /* Q319: `l` is the per-LEVEL offset. Owner: "in POSE the spine also needs movement in the relevant
     regions. Bear in mind this is sometimes more challenging, because one joint's movement is usually
     small and the movement is made of several vertebrae moving together. Allow moving either a specific
     joint or a segment."
     The segment half already existed: `r` is the regional angle, which fk shares out over the levels by
     the documented weights. This adds the other half -- a single vertebra -- as an offset ON TOP of its
     share, so the two compose instead of fighting: move the segment and every vertebra follows its share;
     move one vertebra and only it leaves that share. Zero everywhere = the spine as built. */
  function defaultPose(P){
    var o = {j:{}, r:{}, l:{}};
    P.rig.joints.forEach(function(j){ o.j[j.id] = j.dof.map(function(d){ return d.q0; }); });
    P.rig.regions.forEach(function(r){
      o.r[r.id] = r.dof.map(function(){ return 0; });
      o.l[r.id] = r.levels.map(function(){ return r.dof.map(function(){ return 0; }); });
    });
    return o;
  }
  /* What ONE level may do: its share of the regional range, which is the meaning the weights already
     carry -- so no range is invented here. The share is of the whole arc, lo..hi, and the level's total
     (its share of the regional angle, plus its own offset) is held inside it. */
  function levelRange(r, lv, d){
    var w = r.dof[d].w && r.dof[d].w[lv] != null ? r.dof[d].w[lv] : 1 / Math.max(1, r.levels.length);
    return [r.dof[d].lo * w, r.dof[d].hi * w, w];
  }
  function levelTotal(pose, r, lv, d){
    var off = pose.l && pose.l[r.id] && pose.l[r.id][lv] ? (pose.l[r.id][lv][d] || 0) : 0;
    return pose.r[r.id][d] * levelRange(r, lv, d)[2] + off;
  }
  function clamp(v, lo, hi){ return v < lo ? lo : v > hi ? hi : v; }
  function anatomicalPose(P){
    var o = defaultPose(P);
    P.rig.joints.forEach(function(j){
      if (j.driven) return;
      o.j[j.id] = j.dof.map(function(d){ return d.k === "sup" ? d.hi : clamp(0, d.lo, d.hi); });          // anatomical position: forearm supinated (palms forward), everything else 0 (clamped to its range)
    });
    return o;
  }
  /* segment matrices: M[s] = Float64Array(12) row-major 3x4 */
  function fk(P, pose, M){
    var rig = P.rig, n = P.nseg, i;
    for (i = 0; i < n; i++){
      if (!M[i]) M[i] = new Float64Array(12);
      var m = M[i], par = rig.segs[i][1];
      if (par < 0){ m.set([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]); continue; }
      var pm = M[par], Rp = [pm[0], pm[1], pm[2], pm[4], pm[5], pm[6], pm[8], pm[9], pm[10]], tp = [pm[3], pm[7], pm[11]];
      var lv = P.lev[i], c, dR, R, t;
      if (lv){
        var reg = rig.regions[lv[0]], L = reg.levels[lv[1]], th = pose.r[reg.id];
        var lof = pose.l && pose.l[reg.id] && pose.l[reg.id][lv[1]] ? pose.l[reg.id][lv[1]] : null;
        dR = I3;
        /* Q319: the level's share of the regional angle, plus whatever that one vertebra was moved by. */
        for (var d = 0; d < reg.dof.length; d++) dR = mul3(dR, rotM(reg.dof[d].a, th[d] * reg.dof[d].w[lv[1]] + (lof ? (lof[d] || 0) : 0)));
        c = L.c;
      } else {
        var ji = P.byseg[i];
        if (ji === undefined){ m.set(pm); continue; }
        var j = rig.joints[ji], q = pose.j[j.id];
        c = j.c;
        if (j.driven){
          var d0 = j.dof[0], src = P.jid[d0.drv.src], sq = pose.j[src.id], ang;
          if (src.down) ang = d0.drv.k * (elevation(src, sq) - elevation(src, src.dof.map(function(x){ return x.q0; })));
          else ang = d0.drv.k * (sq[0] - src.dof[0].q0);
          dR = rotM(d0.a, ang);
        } else {
          dR = mul3(jointR(j, q), tr3(jointR(j, j.dof.map(function(x){ return x.q0; }))));
        }
        if (j.ref >= 0){
          var rm = M[j.ref], Rr = [rm[0], rm[1], rm[2], rm[4], rm[5], rm[6], rm[8], rm[9], rm[10]];
          R = mul3(Rr, dR);
          var pos = [Rp[0]*c[0] + Rp[1]*c[1] + Rp[2]*c[2] + tp[0], Rp[3]*c[0] + Rp[4]*c[1] + Rp[5]*c[2] + tp[1], Rp[6]*c[0] + Rp[7]*c[1] + Rp[8]*c[2] + tp[2]], rc = mv3(R, c);
          m.set([R[0], R[1], R[2], pos[0] - rc[0], R[3], R[4], R[5], pos[1] - rc[1], R[6], R[7], R[8], pos[2] - rc[2]]);
          continue;
        }
      }
      // M = M_par * about(dR, c):  R = Rp dR ; t = Rp (c - dR c) + tp
      var dc = mv3(dR, c), e = [c[0] - dc[0], c[1] - dc[1], c[2] - dc[2]];
      R = mul3(Rp, dR);
      t = [Rp[0]*e[0] + Rp[1]*e[1] + Rp[2]*e[2] + tp[0], Rp[3]*e[0] + Rp[4]*e[1] + Rp[5]*e[2] + tp[1], Rp[6]*e[0] + Rp[7]*e[1] + Rp[8]*e[2] + tp[2]];
      m.set([R[0], R[1], R[2], t[0], R[3], R[4], R[5], t[1], R[6], R[7], R[8], t[2]]);
    }
    return M;
  }
  function sameM(a, b){ for (var k = 0; k < 12; k++) if (Math.abs(a[k] - b[k]) > 1e-9) return false; return true; }
  /* write the rigid transform of m into out (positions and normals) */
  function rigid(m, rp, rn, op, on){
    var n = rp.length, k, x, y, z;
    var a = m[0], b = m[1], c = m[2], d = m[3], e = m[4], f = m[5], g = m[6], h = m[7], i = m[8], j = m[9], l = m[10], o = m[11];
    for (k = 0; k < n; k += 3){
      x = rp[k]; y = rp[k+1]; z = rp[k+2];
      op[k] = a*x + b*y + c*z + d; op[k+1] = e*x + f*y + g*z + h; op[k+2] = i*x + j*y + l*z + o;
      if (rn){ x = rn[k]; y = rn[k+1]; z = rn[k+2]; on[k] = a*x + b*y + c*z; on[k+1] = e*x + f*y + g*z; on[k+2] = i*x + j*y + l*z; }
    }
  }
  /* linear blend skinning: sk = {k, pal:Int16Array, idx:[Uint8Array..k], w:[Uint8Array..k-1]} (weight of influence 0 = 255 - sum of the others) ; PM = Float64Array(12*pal.length) palette matrices */
  function skin(sk, PM, rp, rn, op, on){
    var nv = rp.length / 3, K = sk.k, v, q, x, y, z, s, w, px, py, pz, nx, ny, nz, mo, wsum, l;
    var I0 = sk.idx[0], I1 = K > 1 ? sk.idx[1] : null, I2 = K > 2 ? sk.idx[2] : null, I3_ = K > 3 ? sk.idx[3] : null, W1 = K > 1 ? sk.w[0] : null, W2 = K > 2 ? sk.w[1] : null, W3 = K > 3 ? sk.w[2] : null;
    for (v = 0; v < nv; v++){
      x = rp[3*v]; y = rp[3*v+1]; z = rp[3*v+2];
      var w1 = W1 ? W1[v] : 0, w2 = W2 ? W2[v] : 0, w3 = W3 ? W3[v] : 0, w0 = 255 - w1 - w2 - w3;
      px = py = pz = nx = ny = nz = 0;
      for (q = 0; q < K; q++){
        w = q === 0 ? w0 : q === 1 ? w1 : q === 2 ? w2 : w3;
        if (w <= 0) continue;
        s = (q === 0 ? I0 : q === 1 ? I1 : q === 2 ? I2 : I3_)[v] * 12; w /= 255;
        px += w * (PM[s]*x + PM[s+1]*y + PM[s+2]*z + PM[s+3]); py += w * (PM[s+4]*x + PM[s+5]*y + PM[s+6]*z + PM[s+7]); pz += w * (PM[s+8]*x + PM[s+9]*y + PM[s+10]*z + PM[s+11]);
        if (rn){ var ax = rn[3*v], ay = rn[3*v+1], az = rn[3*v+2]; nx += w * (PM[s]*ax + PM[s+1]*ay + PM[s+2]*az); ny += w * (PM[s+4]*ax + PM[s+5]*ay + PM[s+6]*az); nz += w * (PM[s+8]*ax + PM[s+9]*ay + PM[s+10]*az); }
      }
      op[3*v] = px; op[3*v+1] = py; op[3*v+2] = pz;
      if (rn){ l = Math.hypot(nx, ny, nz) || 1; on[3*v] = nx / l; on[3*v+1] = ny / l; on[3*v+2] = nz / l; }
    }
  }
  /* Q384: the same weights, blended as DUAL QUATERNIONS. Owner: "make sure that when a joint's position changes the tissues
     glide over one another and give a rounder and straighter look". The linear blend above puts a vertex on the straight
     line between its two rotated copies: half way through a 90 degree bend it has moved 29% towards the joint axis, half
     way through a 180 degree twist it is ON the axis -- a tube loses its width exactly where it bends. Here each segment's
     motion is a unit dual quaternion (rotation + translation), the weighted sum is normalised, and the vertex gets that one
     rigid motion: for two segments hinged at a joint it is a rotation part of the way about the SAME joint centre, so
     tissue at the surface goes round the outside of the bend at its own radius. Used when the rig says blend:"dq" (the rigs
     re-weighted by scripts/anatomy/q384/smooth_rig_q384.py); other rigs keep the linear blend they were made for. A display
     rule: still no collision, no volume preservation, no soft tissue simulation.
     dqPalette: PM (12 per segment, row-major 3x4, rigid) -> DQ (8 per segment: w x y z of the rotation, then the dual part) */
  function dqPalette(PM, n, DQ){
    for (var q = 0; q < n; q++){
      var a = 12 * q, o = 8 * q, r00 = PM[a], r01 = PM[a+1], r02 = PM[a+2], r10 = PM[a+4], r11 = PM[a+5], r12 = PM[a+6], r20 = PM[a+8], r21 = PM[a+9], r22 = PM[a+10];
      var tx = PM[a+3], ty = PM[a+7], tz = PM[a+11], tr = r00 + r11 + r22, s, w, x, y, z;
      if (tr > 0){ s = Math.sqrt(tr + 1) * 2; w = 0.25 * s; x = (r21 - r12) / s; y = (r02 - r20) / s; z = (r10 - r01) / s; }
      else if (r00 > r11 && r00 > r22){ s = Math.sqrt(1 + r00 - r11 - r22) * 2; w = (r21 - r12) / s; x = 0.25 * s; y = (r01 + r10) / s; z = (r02 + r20) / s; }
      else if (r11 > r22){ s = Math.sqrt(1 + r11 - r00 - r22) * 2; w = (r02 - r20) / s; x = (r01 + r10) / s; y = 0.25 * s; z = (r12 + r21) / s; }
      else { s = Math.sqrt(1 + r22 - r00 - r11) * 2; w = (r10 - r01) / s; x = (r02 + r20) / s; y = (r12 + r21) / s; z = 0.25 * s; }
      DQ[o] = w; DQ[o+1] = x; DQ[o+2] = y; DQ[o+3] = z;
      DQ[o+4] = 0.5 * (-tx*x - ty*y - tz*z); DQ[o+5] = 0.5 * (tx*w + ty*z - tz*y); DQ[o+6] = 0.5 * (-tx*z + ty*w + tz*x); DQ[o+7] = 0.5 * (tx*y - ty*x + tz*w);
    }
  }
  function skinDQ(sk, DQ, rp, rn, op, on){
    var nv = rp.length / 3, K = sk.k, v, q, s, s0, w, f;
    var I0 = sk.idx[0], I1 = K > 1 ? sk.idx[1] : null, I2 = K > 2 ? sk.idx[2] : null, I3_ = K > 3 ? sk.idx[3] : null, W1 = K > 1 ? sk.w[0] : null, W2 = K > 2 ? sk.w[1] : null, W3 = K > 3 ? sk.w[2] : null;
    for (v = 0; v < nv; v++){
      var w1 = W1 ? W1[v] : 0, w2 = W2 ? W2[v] : 0, w3 = W3 ? W3[v] : 0, w0 = 255 - w1 - w2 - w3;
      s0 = I0[v] * 8;
      var b0 = w0 * DQ[s0], b1 = w0 * DQ[s0+1], b2 = w0 * DQ[s0+2], b3 = w0 * DQ[s0+3], b4 = w0 * DQ[s0+4], b5 = w0 * DQ[s0+5], b6 = w0 * DQ[s0+6], b7 = w0 * DQ[s0+7];
      for (q = 1; q < K; q++){
        w = q === 1 ? w1 : q === 2 ? w2 : w3;
        if (w <= 0) continue;
        s = (q === 1 ? I1 : q === 2 ? I2 : I3_)[v] * 8;
        f = DQ[s]*DQ[s0] + DQ[s+1]*DQ[s0+1] + DQ[s+2]*DQ[s0+2] + DQ[s+3]*DQ[s0+3] < 0 ? -w : w;      /* q and -q are the same rotation: take the one on the first influence's side */
        b0 += f * DQ[s]; b1 += f * DQ[s+1]; b2 += f * DQ[s+2]; b3 += f * DQ[s+3]; b4 += f * DQ[s+4]; b5 += f * DQ[s+5]; b6 += f * DQ[s+6]; b7 += f * DQ[s+7];
      }
      var n = Math.sqrt(b0*b0 + b1*b1 + b2*b2 + b3*b3) || 1;
      var qw = b0 / n, qx = b1 / n, qy = b2 / n, qz = b3 / n, dw = b4 / n, dx = b5 / n, dy = b6 / n, dz = b7 / n;
      var tx = 2 * (-dw*qx + dx*qw - dy*qz + dz*qy), ty = 2 * (-dw*qy + dx*qz + dy*qw - dz*qx), tz = 2 * (-dw*qz - dx*qy + dy*qx + dz*qw);
      var m00 = 1 - 2*(qy*qy + qz*qz), m01 = 2*(qx*qy - qw*qz), m02 = 2*(qx*qz + qw*qy), m10 = 2*(qx*qy + qw*qz), m11 = 1 - 2*(qx*qx + qz*qz), m12 = 2*(qy*qz - qw*qx), m20 = 2*(qx*qz - qw*qy), m21 = 2*(qy*qz + qw*qx), m22 = 1 - 2*(qx*qx + qy*qy);
      var x = rp[3*v], y = rp[3*v+1], z = rp[3*v+2];
      op[3*v] = m00*x + m01*y + m02*z + tx; op[3*v+1] = m10*x + m11*y + m12*z + ty; op[3*v+2] = m20*x + m21*y + m22*z + tz;
      if (rn){ x = rn[3*v]; y = rn[3*v+1]; z = rn[3*v+2]; on[3*v] = m00*x + m01*y + m02*z; on[3*v+1] = m10*x + m11*y + m12*z; on[3*v+2] = m20*x + m21*y + m22*z; }
    }
  }
  /* (decodeSkin below) */
  /* control vertices -> per-vertex weights: inverse-square-distance average of the KNN=4 nearest control vertices (control vertices keep their own), 3 largest influences renormalised.
     Same maths as scripts/anatomy/q241/make_pose_rig.py decode_weights (tests/test_q241_rig.py compares them). Done lazily, the first time a structure has to be skinned. */
  function decodeSkin(o, rp){
    var nv = o.nv, nc = o.nc, K = o.kc, npal = o.pal.length, b = o.blob, p = o.off, i, k, c, v, q;
    var mb = (nv + 7) >> 3, cv = new Int32Array(nc), n = 0;
    for (v = 0; v < nv && n < nc; v++) if (b[p + (v >> 3)] & (128 >> (v & 7))) cv[n++] = v;
    p += mb;
    var pl = [], wl = [];
    for (k = 0; k < K; k++){ pl.push(b.subarray(p, p + nc)); p += nc; }
    for (k = 1; k < K; k++){ wl.push(b.subarray(p, p + nc)); p += nc; }
    var Wc = new Float32Array(nc * npal);
    for (c = 0; c < nc; c++){
      var sw = 0;
      for (k = 1; k < K; k++){ var wv = wl[k - 1][c]; sw += wv; Wc[c * npal + pl[k][c]] += wv / 255; }
      Wc[c * npal + pl[0][c]] += (255 - sw) / 255;
    }
    var cx = new Float32Array(nc * 3);
    var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30];
    for (c = 0; c < nc; c++) for (q = 0; q < 3; q++){ var x = rp[3 * cv[c] + q]; cx[3 * c + q] = x; if (x < lo[q]) lo[q] = x; if (x > hi[q]) hi[q] = x; }
    var ext = [hi[0] - lo[0] + 1e-3, hi[1] - lo[1] + 1e-3, hi[2] - lo[2] + 1e-3];
    var h = Math.max(1e-3, Math.cbrt(ext[0] * ext[1] * ext[2] / nc) * 1.3), dims = [Math.max(1, Math.min(64, Math.ceil(ext[0] / h))), Math.max(1, Math.min(64, Math.ceil(ext[1] / h))), Math.max(1, Math.min(64, Math.ceil(ext[2] / h)))];
    var hh = [ext[0] / dims[0], ext[1] / dims[1], ext[2] / dims[2]], hmin = Math.min(hh[0], hh[1], hh[2]);
    var head = new Int32Array(dims[0] * dims[1] * dims[2]).fill(-1), next = new Int32Array(nc);
    function cell(x, d){ var t = Math.floor((x - lo[d]) / hh[d]); return t < 0 ? 0 : t >= dims[d] ? dims[d] - 1 : t; }
    for (c = 0; c < nc; c++){ var g = (cell(cx[3*c+2], 2) * dims[1] + cell(cx[3*c+1], 1)) * dims[0] + cell(cx[3*c], 0); next[c] = head[g]; head[g] = c; }
    var KN = Math.min(4, nc), bd = new Float64Array(KN), bi = new Int32Array(KN), R = new Float64Array(npal);
    var I = [new Uint8Array(nv), new Uint8Array(nv), new Uint8Array(nv)], Wb = [new Uint8Array(nv), new Uint8Array(nv)];
    var isCtrl = new Int32Array(nv).fill(-1); for (c = 0; c < nc; c++) isCtrl[cv[c]] = c;
    for (v = 0; v < nv; v++){
      var px = rp[3*v], py = rp[3*v+1], pz = rp[3*v+2], cxg = cell(px, 0), cyg = cell(py, 1), czg = cell(pz, 2), cnt = 0, r;
      for (r = 0; r < 200; r++){
        var x0 = cxg - r, x1 = cxg + r, y0 = cyg - r, y1 = cyg + r, z0 = czg - r, z1 = czg + r;
        for (var gz = Math.max(0, z0); gz <= Math.min(dims[2] - 1, z1); gz++) for (var gy = Math.max(0, y0); gy <= Math.min(dims[1] - 1, y1); gy++){
          var edge = (gz === z0 || gz === z1 || gy === y0 || gy === y1), step = edge ? 1 : (x1 - x0);
          for (var gx = x0; gx <= x1; gx += step){
            if (gx < 0 || gx >= dims[0]) continue;
            for (c = head[(gz * dims[1] + gy) * dims[0] + gx]; c >= 0; c = next[c]){
              var dx = cx[3*c] - px, dy = cx[3*c+1] - py, dz = cx[3*c+2] - pz, d2 = dx*dx + dy*dy + dz*dz;
              if (cnt < KN){ var m = cnt++; while (m > 0 && bd[m - 1] > d2){ bd[m] = bd[m - 1]; bi[m] = bi[m - 1]; m--; } bd[m] = d2; bi[m] = c; }
              else if (d2 < bd[KN - 1]){ var m2 = KN - 1; while (m2 > 0 && bd[m2 - 1] > d2){ bd[m2] = bd[m2 - 1]; bi[m2] = bi[m2 - 1]; m2--; } bd[m2] = d2; bi[m2] = c; }
            }
          }
        }
        if (cnt === KN && Math.sqrt(bd[KN - 1]) <= r * hmin) break;
        if (x0 <= 0 && y0 <= 0 && z0 <= 0 && x1 >= dims[0] - 1 && y1 >= dims[1] - 1 && z1 >= dims[2] - 1) break;
      }
      for (q = 0; q < npal; q++) R[q] = 0;
      if (isCtrl[v] >= 0){ for (q = 0; q < npal; q++) R[q] = Wc[isCtrl[v] * npal + q]; }
      else {
        var sw2 = 0, ws = [0, 0, 0, 0];
        for (k = 0; k < cnt; k++){ var d = Math.max(1e-3, Math.sqrt(bd[k])); ws[k] = 1 / (d * d); sw2 += ws[k]; }
        for (k = 0; k < cnt; k++){ var wk = ws[k] / sw2, base = bi[k] * npal; for (q = 0; q < npal; q++) R[q] += wk * Wc[base + q]; }
      }
      var t0 = -1, t1 = -1, t2 = -1, w0 = -1, w1 = -1, w2 = -1;
      for (q = 0; q < npal; q++){ var rv = R[q]; if (rv > w0){ t2 = t1; w2 = w1; t1 = t0; w1 = w0; t0 = q; w0 = rv; } else if (rv > w1){ t2 = t1; w2 = w1; t1 = q; w1 = rv; } else if (rv > w2){ t2 = q; w2 = rv; } }
      var sw3 = Math.max(1e-9, (w0 > 0 ? w0 : 0) + (w1 > 0 ? w1 : 0) + (w2 > 0 ? w2 : 0)), q1 = w1 > 0 ? Math.round(w1 / sw3 * 255) : 0, q2 = w2 > 0 ? Math.round(w2 / sw3 * 255) : 0;
      if (q1 < 0) q1 = 0; if (q2 < 0) q2 = 0;
      I[0][v] = t0 < 0 ? 0 : t0; I[1][v] = q1 > 0 ? t1 : (t0 < 0 ? 0 : t0); I[2][v] = q2 > 0 ? t2 : (t0 < 0 ? 0 : t0); Wb[0][v] = q1; Wb[1][v] = q2;
    }
    o.idx = I; o.w = Wb; o.k = 3; o.ready = true; o.blob = null;
  }

  return {decodeSkin:decodeSkin, dqPalette:dqPalette, skinDQ:skinDQ, rotM:rotM, mul3:mul3, tr3:tr3, mv3:mv3, prepare:prepare, jointR:jointR, elevation:elevation, defaultPose:defaultPose, anatomicalPose:anatomicalPose, fk:fk, sameM:sameM, rigid:rigid, skin:skin, clamp:clamp, levelRange:levelRange, levelTotal:levelTotal};
})();

/* Q316, owner: "RENDER and other panels should be movable on screen too". Left alone on a narrow screen, where the
   panel is a full-width sheet the stylesheet owns, and never started from a control inside the head. */
function nmskDrag(elm, handle){
  var sx = 0, sy = 0, ox = 0, oy = 0, dragging = false;
  handle.addEventListener("pointerdown", function(e){
    if (window.innerWidth <= 460) return;
    if (e.target.closest && e.target.closest("button,input,select,label,a")) return;
    dragging = true; sx = e.clientX; sy = e.clientY;
    var r = elm.getBoundingClientRect(); ox = r.left; oy = r.top;
    try { handle.setPointerCapture(e.pointerId); } catch (err){}
    e.preventDefault();
  });
  handle.addEventListener("pointermove", function(e){
    if (!dragging) return;
    var nx = Math.max(0, Math.min(window.innerWidth - 40, ox + e.clientX - sx));
    var ny = Math.max(0, Math.min(window.innerHeight - 40, oy + e.clientY - sy));
    elm.style.left = nx + "px"; elm.style.top = ny + "px"; elm.style.right = "auto"; elm.style.bottom = "auto";
  });
  function end(){ dragging = false; }
  handle.addEventListener("pointerup", end); handle.addEventListener("pointercancel", end);
}
function NMSKPose(E){
  "use strict";
  var C = NMSKPoseCore, $ = function(id){ return document.getElementById(id); };
  var KEY = "nmsk.pose.v1:" + (E.page ? E.page() : "page");
  var st = {ready:false, failed:"", open:false, rig:null, P:null, pose:null, rest:null, M:[], last:[], rigidBy:[], skins:[], skinOf:{}, link:false, ms:0, lastChanged:0, updates:0, raf:0, vtx:0, verts:{rigid:0, skin:0}};
  var panel = $("pose-panel"), banner = $("pose-banner"), body = $("pz-body"), btn = null, statusEl = $("pz-status"), cells = [];
  var GROUP_ORDER = ["Shoulder", "Elbow / forearm", "Wrist / hand", "Thumb", "Fingers", "Hip", "Knee", "Ankle / foot", "Toes", "Lumbar spine", "Thoracic spine", "Head / neck (cervical spine + atlanto-occipital)"];

  /* ---------------------------------------------------------------- data */
  function b64(s){ var bin = atob(s), u = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  function inflate(u8){
    if (typeof DecompressionStream === "undefined") return Promise.reject(new Error("this browser has no DecompressionStream"));
    var ds = new DecompressionStream("deflate");
    return new Response(new Blob([u8]).stream().pipeThrough(ds)).arrayBuffer().then(function(b){ return new Uint8Array(b); });
  }
  function load(){
    var el = $("nmsk-pose-rig"), d = null;
    try { d = el ? JSON.parse(el.textContent) : null; } catch (err){ d = null; }
    if (!d || !d.j) return Promise.resolve(false);
    return Promise.all([inflate(b64(d.j)), d.w ? inflate(b64(d.w)) : Promise.resolve(new Uint8Array(0))]).then(function(r){
      var rig = JSON.parse(new TextDecoder().decode(r[0])), blob = r[1];
      return setup(rig, blob);
    });
  }
  function setup(rig, blob){
    st.rig = rig; st.P = C.prepare(rig);
    if (rig.count !== E.count()){ st.failed = "The pose rig was made for " + rig.count + " structures, this page has " + E.count() + ". Pose is off."; return false; }
    var n = rig.segs.length, i, k;
    st.rigidBy = []; for (i = 0; i < n; i++) st.rigidBy.push([]);
    var bad = 0;
    rig.rigid.forEach(function(g){ g[1].forEach(function(si){ if (E.nverts(si) !== rig.nv[si]) bad++; st.rigidBy[g[0]].push(si); st.verts.rigid += rig.nv[si]; }); });
    st.skins = []; st.skinOf = {};
    rig.skin.forEach(function(s){
      var si = s[0], nv = s[1], K = s[2], pal = s[3], off = s[4], nc = s[5];
      if (E.nverts(si) !== nv) bad++;
      var o = {i:si, kc:K, nc:nc, pal:Int16Array.from(pal), off:off, nv:nv, blob:blob, ready:false, k:3, idx:null, w:null, PM:new Float64Array(12 * pal.length), DQ:rig.blend === "dq" ? new Float64Array(8 * pal.length) : null};
      st.skins.push(o); st.skinOf[si] = o; st.verts.skin += nv;
    });
    if (bad){ st.failed = "The pose rig does not match this page's geometry (" + bad + " structures differ). Pose is off."; return false; }
    st.rest = C.defaultPose(st.P);
    st.pose = JSON.parse(JSON.stringify(st.rest));
    for (i = 0; i < n; i++){ st.M[i] = new Float64Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]); st.last[i] = new Float64Array(st.M[i]); }
    st.ready = true;
    return true;
  }


  /* ---------------------------------------------------------------- pose application */
  function isRest(){
    var rj = st.rest.j, pj = st.pose.j, k, x;
    for (k in rj){ for (x = 0; x < rj[k].length; x++) if (Math.abs(rj[k][x] - pj[k][x]) > 1e-6) return false; }
    for (k in st.rest.r){ for (x = 0; x < st.rest.r[k].length; x++) if (Math.abs(st.rest.r[k][x] - st.pose.r[k][x]) > 1e-6) return false; }
    var rl = st.rest.l || {}, pl = st.pose.l || {}, v;
    for (k in rl){ for (v = 0; v < rl[k].length; v++) for (x = 0; x < rl[k][v].length; x++) if (Math.abs(rl[k][v][x] - ((pl[k] && pl[k][v]) ? pl[k][v][x] : 0)) > 1e-6) return false; }
    return true;
  }
  function update(){
    if (!st.ready) return;
    var t0 = performance.now(), n = st.rig.segs.length, s, i, q;
    C.fk(st.P, st.pose, st.M);
    /* Q384: a segment that has not moved is the identity EXACTLY, not the identity plus the 1e-16 a product of rotations
       leaves behind -- so a limb put back while another joint stays posed is the built geometry again, bit for bit */
    for (s = 0; s < n; s++){
      var ms = st.M[s];
      if (Math.abs(ms[0] - 1) < 1e-11 && Math.abs(ms[5] - 1) < 1e-11 && Math.abs(ms[10] - 1) < 1e-11 && Math.abs(ms[1]) < 1e-11 && Math.abs(ms[2]) < 1e-11 && Math.abs(ms[4]) < 1e-11 &&
          Math.abs(ms[6]) < 1e-11 && Math.abs(ms[8]) < 1e-11 && Math.abs(ms[9]) < 1e-11 && Math.abs(ms[3]) < 1e-9 && Math.abs(ms[7]) < 1e-9 && Math.abs(ms[11]) < 1e-9)
        ms.set([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0]);
    }
    var dirty = new Uint8Array(n);
    for (s = 0; s < n; s++) if (!C.sameM(st.M[s], st.last[s])) dirty[s] = 1;
    var changed = [], home = isRest();      /* Q384: back at the model pose a structure gets its REST arrays back, copied, so the model pose is the built geometry bit for bit whatever the blend */
    for (s = 0; s < n; s++){
      if (!dirty[s]) continue;
      var L = st.rigidBy[s];
      for (i = 0; i < L.length; i++){
        var si = L[i], r = E.rest(si), l = E.live(si);
        if (home){ l.pos.set(r.pos); l.nrm.set(r.nrm); } else C.rigid(st.M[s], r.pos, r.nrm, l.pos, l.nrm);
        E.touch(si); changed.push(si);
      }
    }
    for (i = 0; i < st.skins.length; i++){
      var o = st.skins[i], any = false;
      for (q = 0; q < o.pal.length; q++) if (dirty[o.pal[q]]){ any = true; break; }
      if (!any) continue;
      for (q = 0; q < o.pal.length; q++) o.PM.set(st.M[o.pal[q]], 12 * q);
      if (!o.ready) C.decodeSkin(o, E.rest(o.i).pos);
      var r2 = E.rest(o.i), l2 = E.live(o.i);
      if (home){ l2.pos.set(r2.pos); l2.nrm.set(r2.nrm); }
      else if (o.DQ){ C.dqPalette(o.PM, o.pal.length, o.DQ); C.skinDQ(o, o.DQ, r2.pos, r2.nrm, l2.pos, l2.nrm); }
      else C.skin(o, o.PM, r2.pos, r2.nrm, l2.pos, l2.nrm);
      E.touch(o.i); changed.push(o.i);
    }
    for (s = 0; s < n; s++) if (dirty[s]) st.last[s].set(st.M[s]);
    st.ms = performance.now() - t0; st.lastChanged = changed.length; st.updates++;
    if (changed.length){
      var atRest = isRest();
      E.commit(changed, atRest);
      /* Q320: a neutral pose revision for optional add-ons that read the posed vertices (window.__poseLive / __poseRestPos): bumped on every
         geometry change, with the changed structure indices and whether the pose is the model pose again */
      window.__poseRev = (window.__poseRev || 0) + 1; window.__poseAtRest = atRest;
      try { window.dispatchEvent(new CustomEvent("nmsk-pose-rev", {detail:{rev:window.__poseRev, ids:changed.slice(), rest:atRest}})); } catch (e) {}
    }
    chrome();
  }
  function schedule(){
    if (st.raf) return;
    st.raf = requestAnimationFrame(function(){ st.raf = 0; update(); });
  }
  function flush(){ if (st.raf){ cancelAnimationFrame(st.raf); st.raf = 0; } update(); }

  /* ---------------------------------------------------------------- setting values */
  function jointOf(id){ return st.P.jid[id]; }
  function twin(id){ return id.slice(-2) === "_r" ? id.slice(0, -2) + "_l" : id.slice(-2) === "_l" ? id.slice(0, -2) + "_r" : null; }
  function setJoint(id, k, v, nolink){
    var j = jointOf(id); if (!j || j.driven) return false;
    for (var x = 0; x < j.dof.length; x++) if (j.dof[x].k === k){
      st.pose.j[id][x] = C.clamp(+v, j.dof[x].lo, j.dof[x].hi);
      if (st.link && !nolink){ var t = twin(id); if (t && jointOf(t)) setJoint(t, k, v, true); }
      sync(); schedule(); return true;
    }
    return false;
  }
  /* Q384 / E5: a COUPLED control -- one value that sets several axes of one joint together (thumb opposition = CMC flexion +
     palmar abduction + axial rotation, each from one end of its own range to the other). The rig names the parts and their
     ends; that they run in step is a display convention and the panel says so. */
  function coupleOf(id, cid){ var j = jointOf(id), L = j && j.couple ? j.couple.filter(function(c){ return c.id === cid; }) : []; return L[0] || null; }
  function coupleValue(id, cid){
    var j = jointOf(id), c = coupleOf(id, cid); if (!c) return null;
    var s = 0, n = 0;
    c.parts.forEach(function(p){
      for (var x = 0; x < j.dof.length; x++) if (j.dof[x].k === p[0]){ s += C.clamp((st.pose.j[id][x] - p[1]) / Math.max(1e-9, p[2] - p[1]), 0, 1); n++; }
    });
    return n ? c.lo + (c.hi - c.lo) * s / n : null;
  }
  function setCouple(id, cid, v){
    var c = coupleOf(id, cid); if (!c) return false;
    var u = C.clamp((+v - c.lo) / Math.max(1e-9, c.hi - c.lo), 0, 1);
    c.parts.forEach(function(p){ setJoint(id, p[0], p[1] + (p[2] - p[1]) * u); });
    return true;
  }
  function setRegion(id, k, v){
    var r = st.P.rig.regions.filter(function(g){ return g.id === id; })[0]; if (!r) return false;
    for (var x = 0; x < r.dof.length; x++) if (r.dof[x].k === k){ st.pose.r[id][x] = C.clamp(+v, r.dof[x].lo, r.dof[x].hi); sync(); schedule(); return true; }
    return false;
  }
  function regionOf(id){ return st.P.rig.regions.filter(function(g){ return g.id === id; })[0] || null; }
  /* Q319: ONE vertebra. `v` is the angle that level should end up at in total, not the offset -- the
     caller should not have to know how the regional angle is shared out. It is held inside that level's
     own share of the regional range, so a vertebra can never be driven past what the region allows it. */
  function setLevel(id, lv, k, v){
    var r = regionOf(id); if (!r || !r.levels[lv] || !st.pose.l[id]) return false;
    for (var x = 0; x < r.dof.length; x++) if (r.dof[x].k === k){
      var R = C.levelRange(r, lv, x);
      st.pose.l[id][lv][x] = C.clamp(+v, R[0], R[1]) - st.pose.r[id][x] * R[2];
      sync(); schedule(); return true;
    }
    return false;
  }
  /* what the UI and the browser check both read: per level, its label and, per dof, where it stands,
     what its own share permits, and how much of that is the segment's doing rather than its own */
  function levelsOf(id){
    var r = regionOf(id); if (!r) return null;
    return r.levels.map(function(L, lv){
      return {label:L.label, seg:L.seg, dof:r.dof.map(function(d, x){
        var R = C.levelRange(r, lv, x);
        return {k:d.k, l:d.l, value:C.levelTotal(st.pose, r, lv, x), lo:R[0], hi:R[1], share:R[2],
                fromSegment:st.pose.r[id][x] * R[2], own:st.pose.l[id][lv][x]};
      })};
    });
  }
  function copySide(from){
    var to = from === "r" ? "l" : "r";
    st.rig.joints.forEach(function(j){
      if (j.side !== to || j.driven) return;
      var t = jointOf(twin(j.id)); if (!t) return;
      st.pose.j[j.id] = t.dof.map(function(d, x){ return C.clamp(st.pose.j[t.id][x], j.dof[x].lo, j.dof[x].hi); });
    });
  }
  function copyGroup(group, from){
    var to = from === "r" ? "l" : "r";
    st.rig.joints.forEach(function(j){
      if (j.group !== group || j.side !== to || j.driven) return;
      var t = jointOf(twin(j.id)); if (!t) return;
      st.pose.j[j.id] = j.dof.map(function(d, x){ return C.clamp(st.pose.j[t.id][x], d.lo, d.hi); });
    });
    sync(); schedule();
  }
  function symmetric(from){
    copySide(from);
    st.rig.regions.forEach(function(r){ r.dof.forEach(function(d, x){ if (d.k !== "flex") st.pose.r[r.id][x] = 0; }); });      // midline: no lateral bend / rotation
    sync(); schedule();
  }
  function reset(){ st.pose = JSON.parse(JSON.stringify(st.rest)); sync(); schedule(); }
  function anatomical(){ st.pose = C.anatomicalPose(st.P); sync(); schedule(); }
  function save(){
    try { localStorage.setItem(KEY, JSON.stringify({v:1, j:st.pose.j, r:st.pose.r, l:st.pose.l, t:Date.now()})); status("Pose saved in this browser."); return true; } catch (err){ status("Could not save (browser storage is blocked)."); return false; }
  }
  function loadSaved(){
    var d = null;
    try { d = JSON.parse(localStorage.getItem(KEY) || "null"); } catch (err){ d = null; }
    if (!d || d.v !== 1){ status("No saved pose for this page."); return false; }
    apply(d); status("Saved pose loaded."); return true;
  }
  function apply(d){
    var P = JSON.parse(JSON.stringify(st.rest));
    st.rig.joints.forEach(function(j){ if (j.driven) return; var v = d.j && d.j[j.id]; if (v && v.length && v.length <= j.dof.length) P.j[j.id] = j.dof.map(function(x, i){ var n = i < v.length ? +v[i] : NaN; return !isFinite(n) || Math.abs(n - x.q0) < 1e-6 ? x.q0 : C.clamp(n, x.lo, x.hi); }); });      /* E5: a pose saved before a joint got another axis (finger abduction, thumb rotation) keeps the axes it has */      /* Q384: the model's own angle is kept as it is even where it lies outside the normal range (a knee built 3 degrees hyperextended), so Undo of a turn returns to the model pose */
    st.rig.regions.forEach(function(r){
      var v = d.r && d.r[r.id];
      if (v && v.length === r.dof.length) P.r[r.id] = r.dof.map(function(x, i){ var n = +v[i]; return isFinite(n) ? C.clamp(n, x.lo, x.hi) : 0; });
      /* Q319: a pose saved before the per-vertebra offsets existed simply has none -- it stays at its
         regional shares, which is exactly what it meant when it was saved. */
      var L = d.l && d.l[r.id];
      if (L && L.length === r.levels.length) P.l[r.id] = r.levels.map(function(_, lv){
        return r.dof.map(function(_d, i){
          var n = +((L[lv] || [])[i]); if (!isFinite(n)) return 0;
          var R = C.levelRange(r, lv, i), tot = C.clamp(P.r[r.id][i] * R[2] + n, R[0], R[1]);
          return tot - P.r[r.id][i] * R[2];
        });
      });
    });
    st.pose = P; sync(); schedule();
  }

  /* ---------------------------------------------------------------- UI */
  function status(t){ if (statusEl) statusEl.textContent = t || ""; }
  function chrome(){
    var rest = isRest();
    document.documentElement.classList.toggle("pose-on", !rest);           // part markers sit at rest-pose positions: hidden while posed (see pose.css)
    var pc = E.parts && E.parts();
    if (pc && pc.state && pc.setShowAll){ try { var sa = pc.state().showAll; if (!rest && sa){ st.sa = true; pc.setShowAll(false); } else if (rest && st.sa){ st.sa = false; pc.setShowAll(true); } } catch (err){} }
    if (banner) banner.hidden = rest;
    if (btn) btn.classList.toggle("pz-on", !rest);
    if (statusEl && st.ready && !statusEl.dataset.msg) statusEl.textContent = rest ? "Model pose (as built)." : "Posed: " + st.lastChanged + " structures moved in " + st.ms.toFixed(1) + " ms.";
  }
  function el(tag, cls, txt){ var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function pct(v, a, b){ return (100 * (v - a) / Math.max(1e-9, b - a)).toFixed(2) + "%"; }
  function cell(j, x, side){
    var d = j.dof[x], a = Math.min(d.lo, d.q0), b = Math.max(d.hi, d.q0), pad = Math.max(1, (b - a) * 0.0);
    var c = el("div", "pz-cell"), tag = el("span", "pz-sd", side === "m" ? "" : side.toUpperCase()), w = el("div", "pz-sl"), band = el("i", "pz-band"), mk = el("i", "pz-q0"), zero = el("i", "pz-zero");
    band.style.left = pct(d.lo, a - pad, b + pad); band.style.width = (100 * (d.hi - d.lo) / Math.max(1e-9, (b + pad) - (a - pad))).toFixed(2) + "%";
    mk.style.left = pct(d.q0, a - pad, b + pad); mk.title = "model pose " + d.q0.toFixed(0) + "°";
    zero.style.left = pct(0, a - pad, b + pad); if (0 < a - pad || 0 > b + pad) zero.style.display = "none";
    var rg = el("input"); rg.type = "range"; rg.min = a - pad; rg.max = b + pad; rg.step = 1; rg.value = d.q0; rg.setAttribute("aria-label", j.name + " " + d.l + (side === "m" ? "" : " " + side));
    var nm = el("input", "pz-num"); nm.type = "number"; nm.min = d.lo; nm.max = d.hi; nm.step = 1; nm.value = Math.round(d.q0); nm.setAttribute("aria-label", "value in degrees");
    w.appendChild(band); w.appendChild(zero); w.appendChild(mk); w.appendChild(rg);
    c.appendChild(tag); c.appendChild(w); c.appendChild(nm); c.appendChild(el("span", "pz-deg", "°"));
    rg.addEventListener("input", function(){ setJoint(j.id, d.k, rg.value); });
    nm.addEventListener("change", function(){ setJoint(j.id, d.k, nm.value); });
    cells.push({j:j.id, x:x, rg:rg, nm:nm, lo:d.lo, hi:d.hi, el:c});
    return c;
  }
  function cplCell(j, c, side){
    var e = el("div", "pz-cell pz-cpl"), tag = el("span", "pz-sd", side === "m" ? "" : side.toUpperCase()), w = el("div", "pz-sl"), band = el("i", "pz-band");
    band.style.left = "0%"; band.style.width = "100%";
    var rg_ = el("input"); rg_.type = "range"; rg_.min = c.lo; rg_.max = c.hi; rg_.step = 1; rg_.setAttribute("aria-label", j.name + " " + c.l + (side === "m" ? "" : " " + side));
    var nm = el("input", "pz-num"); nm.type = "number"; nm.min = c.lo; nm.max = c.hi; nm.step = 1; nm.setAttribute("aria-label", "value in " + (c.unit === "%" ? "percent" : "degrees"));
    w.appendChild(band); w.appendChild(rg_);
    e.appendChild(tag); e.appendChild(w); e.appendChild(nm); e.appendChild(el("span", "pz-deg", c.unit || "°"));
    rg_.addEventListener("input", function(){ setCouple(j.id, c.id, rg_.value); });
    nm.addEventListener("change", function(){ setCouple(j.id, c.id, nm.value); });
    cells.push({j:j.id, cpl:c.id, rg:rg_, nm:nm, lo:c.lo, hi:c.hi, el:e});
    return e;
  }
  /* Q319: one vertebra, one degree of freedom. The slider's ends ARE the level's share of the region's
     range -- the same numbers levelRange() gives setLevel -- so the control cannot ask for a motion the
     region does not allow that level, and the band drawn behind it is that share rather than a guess. */
  function levCell(r, lv, x){
    var d = r.dof[x], R = C.levelRange(r, lv, x);
    var c = el("div", "pz-cell"), w = el("div", "pz-sl"), band = el("i", "pz-band"), mk = el("i", "pz-q0");
    band.style.left = "0%"; band.style.width = "100%";
    mk.style.left = pct(0, R[0], R[1]); mk.title = "the spine as built";
    var rg = el("input"); rg.type = "range"; rg.min = R[0]; rg.max = R[1]; rg.step = 0.5;
    rg.value = C.levelTotal(st.pose, r, lv, x);
    rg.setAttribute("aria-label", r.levels[lv].label + " " + d.l);
    var nm = el("input", "pz-num"); nm.type = "number"; nm.min = R[0]; nm.max = R[1]; nm.step = 0.5;
    nm.value = Math.round(rg.value);
    w.appendChild(band); w.appendChild(mk); w.appendChild(rg);
    c.appendChild(el("span", "pz-sd", "")); c.appendChild(w); c.appendChild(nm); c.appendChild(el("span", "pz-deg", "\u00b0"));
    rg.addEventListener("input", function(){ setLevel(r.id, lv, d.k, rg.value); });
    nm.addEventListener("change", function(){ setLevel(r.id, lv, d.k, nm.value); });
    cells.push({reg:r, lv:lv, x:x, rg:rg, nm:nm, lo:R[0], hi:R[1]});
    return c;
  }
  function regCell(r, x){
    var d = r.dof[x], a = d.lo, b = d.hi, c = el("div", "pz-cell"), w = el("div", "pz-sl"), band = el("i", "pz-band"), mk = el("i", "pz-q0");
    band.style.left = "0%"; band.style.width = "100%"; mk.style.left = pct(0, a, b); mk.title = "model pose (as built) = 0";
    var rg = el("input"); rg.type = "range"; rg.min = a; rg.max = b; rg.step = 1; rg.value = 0; rg.setAttribute("aria-label", r.name + " " + d.l);
    var nm = el("input", "pz-num"); nm.type = "number"; nm.min = a; nm.max = b; nm.step = 1; nm.value = 0;
    w.appendChild(band); w.appendChild(mk); w.appendChild(rg); c.appendChild(el("span", "pz-sd", "")); c.appendChild(w); c.appendChild(nm); c.appendChild(el("span", "pz-deg", "°"));
    rg.addEventListener("input", function(){ setRegion(r.id, d.k, rg.value); });
    nm.addEventListener("change", function(){ setRegion(r.id, d.k, nm.value); });
    cells.push({r:r.id, x:x, rg:rg, nm:nm, lo:a, hi:b});
    return c;
  }
  function sync(){
    cells.forEach(function(c){
      /* Q319: a per-vertebra cell shows the level's TOTAL -- its share of the segment plus its own
         offset -- because that is the angle the vertebra is actually at, and the only number a reader
         can check against the model. Moving the segment therefore moves all of these too. */
      var v = c.reg ? C.levelTotal(st.pose, c.reg, c.lv, c.x)
                    : c.cpl ? coupleValue(c.j, c.cpl)
                    : c.j ? st.pose.j[c.j][c.x] : st.pose.r[c.r][c.x];
      c.rg.value = v; c.nm.value = Math.round(v);
    });
    chrome();
  }
  function buildBody(){
    body.textContent = "";
    cells = [];
    var rig = st.rig, groups = {}, order = [];
    rig.joints.forEach(function(j){ if (j.driven) return; (groups[j.group] || (groups[j.group] = [])).push(j); if (order.indexOf(j.group) < 0) order.push(j.group); });
    // presets
    var pr = el("div", "pz-presets");
    [["Reset to model pose", reset, "Back to the pose as built (the model's own posture)."], ["Anatomical position", anatomical, "All joints 0 within their range, forearms supinated (palms forward); spine as built."],
     ["Symmetric pose R→L", function(){ symmetric("r"); }, "The left side takes the right side's joint angles (equal numbers = mirrored posture); spine lateral bend / rotation 0."],
     ["Symmetric pose L→R", function(){ symmetric("l"); }, "The right side takes the left side's joint angles."]].forEach(function(p){
      var b = el("button", "pz-btn", p[0]); b.type = "button"; b.title = p[2]; b.addEventListener("click", p[1]); pr.appendChild(b);
    });
    var lk = el("label", "pz-link"), ck = el("input"); ck.type = "checkbox"; ck.checked = st.link; ck.addEventListener("change", function(){ st.link = ck.checked; });
    lk.appendChild(ck); lk.appendChild(document.createTextNode(" Link left and right (a change on one side is applied to the other)")); pr.appendChild(lk);
    var sv = el("div", "pz-save");
    [["Save pose", save], ["Load pose", loadSaved]].forEach(function(p){ var b = el("button", "pz-btn", p[0]); b.type = "button"; b.addEventListener("click", p[1]); sv.appendChild(b); });
    pr.appendChild(sv);
    body.appendChild(el("p", "pz-solo-hint", "Point at a joint on the model, or click it to hold it: its sliders appear here. The spine, the presets and the whole list are in the full view (press \u201cThis joint only\u201d again)."));
    body.appendChild(pr);
    var ord = GROUP_ORDER.filter(function(g){ return order.indexOf(g) >= 0 }).concat(order.filter(function(g){ return GROUP_ORDER.indexOf(g) < 0; }));
    var first = true;
    ord.forEach(function(g){
      var sec = el("section", "pz-g"), h = el("h4"), hb = el("button", "pz-gh", g); hb.type = "button"; hb.setAttribute("aria-expanded", first ? "true" : "false");
      var rows = el("div", "pz-rows"); rows.hidden = !first; first = false;
      hb.addEventListener("click", function(){ var o = rows.hidden; rows.hidden = !o; hb.setAttribute("aria-expanded", String(o)); });
      h.appendChild(hb);
      var gb = el("span", "pz-gb"), r2l = el("button", "pz-mini", "R→L"), l2r = el("button", "pz-mini", "L→R");
      r2l.type = l2r.type = "button"; r2l.title = "Mirror to other side: the left joints of this group take the right side's values"; l2r.title = "Mirror to other side: the right joints of this group take the left side's values";
      r2l.addEventListener("click", function(){ copyGroup(g, "r"); }); l2r.addEventListener("click", function(){ copyGroup(g, "l"); });
      gb.appendChild(r2l); gb.appendChild(l2r); h.appendChild(gb); sec.appendChild(h);
      // rows: one per (joint-without-side, dof)
      var seen = {};
      groups[g].forEach(function(j){
        var base = j.id.slice(0, -2);
        j.dof.forEach(function(d, x){
          var key = base + "|" + d.k; if (seen[key]) return; seen[key] = 1;
          var jr = jointOf(base + "_r"), jl = jointOf(base + "_l");
          var row = el("div", "pz-row"), lab = el("div", "pz-lab", j.name + " – " + d.l);
          var rm = (rig.rom && d.rk && rig.rom[d.rk]) ? rig.rom[d.rk][3] : "", hu = window.NMSKHuman ? NMSKHuman.text : String;      // Q344
          lab.title = (d.lo + " to " + d.hi + "°. " + hu(rm) + (j.note ? "  " + hu(j.note) : "")).trim();
          row.appendChild(lab);
          var cs = el("div", "pz-cells");
          if (jr){ cs.appendChild(cell(jr, x, "r")); cells[cells.length - 1].row = row; cells[cells.length - 1].sec = sec; }
          if (jl){ cs.appendChild(cell(jl, x, "l")); cells[cells.length - 1].row = row; cells[cells.length - 1].sec = sec; }
          row.appendChild(cs); rows.appendChild(row);
        });
        (j.couple || []).forEach(function(c){
          var key = base + "|cpl|" + c.id; if (seen[key]) return; seen[key] = 1;
          var jr = jointOf(base + "_r"), jl = jointOf(base + "_l"), hu = window.NMSKHuman ? NMSKHuman.text : String;
          var row = el("div", "pz-row"), lab = el("div", "pz-lab", j.name + " – " + c.l + (c.convention ? " *" : ""));
          lab.title = hu(c.note || "");
          row.appendChild(lab);
          var cs = el("div", "pz-cells");
          [[jr, "r"], [jl, "l"]].forEach(function(p){ if (p[0] && p[0].couple){ cs.appendChild(cplCell(p[0], c, p[1])); cells[cells.length - 1].row = row; cells[cells.length - 1].sec = sec; } });
          row.appendChild(cs); rows.appendChild(row);
          if (c.convention){ var nt = el("div", "pz-lab pz-cnote", "* " + hu(c.note || "display convention")); row.appendChild(nt); }
        });
      });
      sec.appendChild(rows); body.appendChild(sec);
    });
    rig.regions.forEach(function(r){ var g = r.group; });
    var regOrd = GROUP_ORDER.filter(function(g){ return rig.regions.some(function(r){ return r.group === g; }); });
    rig.regions.slice().sort(function(a, b){ return GROUP_ORDER.indexOf(a.group) - GROUP_ORDER.indexOf(b.group); }).forEach(function(r){
      var sec = el("section", "pz-g"), h = el("h4"), hb = el("button", "pz-gh", r.name); hb.type = "button"; hb.setAttribute("aria-expanded", "false");
      var rows = el("div", "pz-rows"); rows.hidden = true; hb.addEventListener("click", function(){ var o = rows.hidden; rows.hidden = !o; hb.setAttribute("aria-expanded", String(o)); });
      h.appendChild(hb); sec.appendChild(h);
      r.dof.forEach(function(d, x){ var row = el("div", "pz-row"), lab = el("div", "pz-lab", d.l); var rm = rig.rom && d.rk && rig.rom[d.rk] ? rig.rom[d.rk][3] : ""; var hu2 = window.NMSKHuman ? NMSKHuman.text : String; lab.title = (d.lo + " to " + d.hi + "°. " + hu2(rm) + "  " + hu2(r.note || "")).trim(); row.appendChild(lab); var cs = el("div", "pz-cells pz-one");   /* Q344 */ cs.appendChild(regCell(r, x)); row.appendChild(cs); rows.appendChild(row); });
      /* Q319, owner: "allow performing a movement either of a specific joint or of a segment." The
         sliders above are the segment -- one angle shared over the levels by the documented weights.
         This is the same region one vertebra at a time, folded away because it is the longer way round
         and most poses do not need it. Each row shows where that vertebra stands in total, so moving the
         segment above moves every row here with it. */
      if (r.levels && r.levels.length > 1){
        var det = el("details", "pz-help"), sum = el("summary", null, "One vertebra at a time (" + r.levels.length + ")");
        det.appendChild(sum);
        var note = el("p", "pz-lab", "Each vertebra may move through its own share of the range above -- " +
          r.levels.map(function(L, i){ var w = r.dof[0].w && r.dof[0].w[i] != null ? r.dof[0].w[i] : 1 / r.levels.length;
                                       return L.label + " " + Math.round(w * 100) + "%"; }).join(", ") +
          " of it for " + (r.dof[0].l || "the first") + ". " + (r.note || ""));
        det.appendChild(note);
        r.levels.forEach(function(L, lv){
          var lrow = el("div", "pz-row"), llab = el("div", "pz-lab", L.label);
          lrow.appendChild(llab);
          var lcs = el("div", "pz-cells" + (r.dof.length === 1 ? " pz-one" : ""));
          r.dof.forEach(function(d2, x2){ lcs.appendChild(levCell(r, lv, x2)); });
          lrow.appendChild(lcs); det.appendChild(lrow);
        });
        rows.appendChild(det);
      }
      sec.appendChild(rows); body.appendChild(sec);
    });
    function hum(t){ return window.NMSKHuman ? NMSKHuman.text(t) : String(t == null ? "" : t); }      /* Q344: the rig data carries round numbers and file names; the panel prints plain wording and keeps the citation */
    var help = el("details", "pz-help"), sm = el("summary", "", "Ranges of motion, method and limits");
    help.appendChild(sm);
    var p1 = el("p", "", "Hard bounds of every slider = the NORMAL range of motion (population averages, AAOS / AMA style, e.g. shoulder flexion 180, abduction 180, elbow flexion 150, hip flexion 120, knee flexion 135, ankle dorsiflexion 20 / plantarflexion 50; " +
      "values quoted from the standard references as remembered, several are assumptions). The shaded band on a slider is the normal range, the tick is the model's own pose, the faint line is 0. " +
      "An individual's range differs with age, sex and method. A model pose outside the normal range (e.g. a slightly hyperextended knee) is shown as it is and can only be moved into the range.");
    var p2 = el("p", "", "How it works: joint centres and axes are fitted to THIS page's own bones (hip and shoulder: femoral / humeral head spheres; elbow and knee: transepicondylar axis; ankle: malleoli; ...). Bones move rigidly with their segment; " +
      "muscles, vessels, nerves, ligaments, organs and skin follow by skinning weights (from the distance to each segment's bones), so a muscle stretches between its origin and insertion on the moving bones. " +
      (rig.blend === "dq" ? "Around the hip, knee, shoulder and elbow the skin, vessels and nerves follow a blend zone along the limb through the joint centre, and the skin is treated as one surface: where the zone lies and how long it is are display conventions of this viewer, not anatomy - a posed vein or nerve is not where it would lie in a living flexed limb. " : "") +
      "Clavicle and scapula follow the shoulder with a fixed 3:1 scapulohumeral rhythm. Pose preview: kinematic approximation, soft tissue not simulated (no collision, no volume preservation) - expect tissue to pass through bone and to stretch or crumple near extreme angles. " +
      "The clinical add-on tools (imaging, needle and the like) use the rest-pose meshes: reset the pose before using them.");
    help.appendChild(p1); help.appendChild(p2);
    if (rig.rom){ var tb = el("table", "pz-rom"); Object.keys(rig.rom).forEach(function(k){ var r = rig.rom[k], tr = el("tr"); tr.appendChild(el("td", "", r[2])); tr.appendChild(el("td", "", r[0] + " .. " + r[1] + "°")); tr.appendChild(el("td", "", hum(r[3]))); tb.appendChild(tr); }); help.appendChild(tb); }
    if (rig.notes){ var p3 = el("p", "", "Rig for this page: " + hum(rig.notes)); help.appendChild(p3); }
    body.appendChild(help);
    sync();
    view.key = ""; viewSync();
  }
  /* Q384 / E4: two ways to make the panel small without closing Pose. "This joint only": the list is cut down to the joint
     under the pointer / the held joint (the last one pointed at stays while the pointer is elsewhere). The tile: only the
     title row, with the joint's name. Both are remembered in this browser (their own key: the layout module keeps a box's
     place, it has no store for what a box shows). Neither touches the pose or the rings. */
  var view = {solo:false, mini:false, last:null, key:""}, VKEY = "nmsk.pose.panel.v1";
  try { var vd = JSON.parse(localStorage.getItem(VKEY) || "null"); if (vd){ view.solo = !!vd.solo; view.mini = !!vd.mini; } } catch (err){}
  function viewSet(o){
    if (o && o.solo != null) view.solo = !!o.solo;
    if (o && o.mini != null) view.mini = !!o.mini;
    if (o && o.forget) view.last = null;
    try { localStorage.setItem(VKEY, JSON.stringify({solo:view.solo, mini:view.mini})); } catch (err){}
    view.key = ""; viewSync();
    return {solo:view.solo, mini:view.mini};
  }
  function viewSync(){
    if (!panel || !st.ready) return;
    if (rg.held || rg.jid) view.last = rg.held || rg.jid;
    var fid = rg.held || rg.jid || view.last, J = fid ? jointOf(fid) : null, k = [view.solo, view.mini, fid, rg.held].join("|");
    if (k === view.key) return;
    view.key = k;
    panel.classList.toggle("pz-solo", view.solo); panel.classList.toggle("pz-tile", view.mini); panel.classList.toggle("pz-focus", !!J);
    var sb = $("pz-solo"), mb = $("pz-min"), tn = $("pz-tile-name");
    if (sb) sb.setAttribute("aria-pressed", String(view.solo));
    if (mb){ mb.setAttribute("aria-expanded", String(!view.mini)); mb.textContent = view.mini ? "\u25a2" : "\u2013"; mb.setAttribute("aria-label", view.mini ? "Open the pose panel again" : "Shrink the pose panel to a small tile; Pose stays on"); }
    if (tn) tn.textContent = J ? handleName(J) + (rg.held ? " \u2013 held" : "") : "no joint chosen";
    var ids = J ? mates(J).map(function(o){ return o.id; }) : [], rows = [], secs = [];
    cells.forEach(function(c){
      if (!c.el || !c.j) return;
      var on = ids.indexOf(c.j) >= 0;
      c.el.classList.toggle("pz-on", on);
      if (c.row){ if (rows.indexOf(c.row) < 0){ rows.push(c.row); c.row.classList.remove("pz-on"); } if (on) c.row.classList.add("pz-on"); }
      if (c.sec){ if (secs.indexOf(c.sec) < 0){ secs.push(c.sec); c.sec.classList.remove("pz-has"); } if (on) c.sec.classList.add("pz-has"); }
    });
  }
  function open(on){
    st.open = on == null ? !st.open : !!on;
    if (panel){ panel.hidden = !st.open; panel.classList.toggle("pz-phone", !!(E.isPhone && E.isPhone())); }
    if (btn) btn.setAttribute("aria-expanded", String(st.open));
    if (st.open && !body.firstChild && st.ready) buildBody();
    if (st.open) viewSync();
    /* Q318: pressing Pose is what "marking POSE" means, so the rings come on with it -- and STAY on when the
       panel is closed again, which is the owner's "with or without the detailed window". */
    if (st.open && st.ready) ringsOn(true);
  }
  /* ---------------------------------------------------------------- Q318: the rings, on the model itself */
  /* Owner: "if I have marked POSE then moving over a joint should mark the 3 axis rings on that joint, and if I
     click on them, allow changing it graphically on the model itself, with or without the detailed window."
     One SVG over the canvas; nothing is added to either engine's 3D scene, so neither shader, picking pass nor
     draw order is touched. A joint's centre and the world direction of each of its axes are read from the SAME
     forward kinematics that moved the geometry (st.M), so a ring cannot point somewhere the bone is not.
     Each axis is drawn twice: the whole circle faint, and the part of it this joint is ALLOWED to turn through
     solid -- the normal range becomes something you can see rather than a number to read -- with a tick where
     it stands now. Dragging a ring turns that one axis through setJoint(), the same door the slider uses, so
     the clamp to the range and the left/right link apply identically and the panel cannot disagree with it. */
  var RCOL = ["#d6453c", "#2f9e44", "#2f7fd1"], RPX = [52, 68, 84], I3R = [1, 0, 0, 0, 1, 0, 0, 0, 1];
  var rg = {on:false, svg:null, jid:null, drag:null, raf:0, sig:"", held:null, peek:null, touch:false};
  /* Q384, owner: "the elbow lacks extension-flexion". It did not lack it in the rig or in the panel (Elbow - Flexion (+) /
     extension (0), 0 to 150 degrees, docs/pose_rom_table.md `elbow_flex`, Zwerus 2019): the RINGS could not reach it. The
     elbow hinge and the forearm rotation are two joints whose centres lie ~3 cm apart, the pointer met whichever was nearer
     first and that one then kept the rings -- from the hand side that is the forearm, whose only ring is supination. The
     same held for the ankle and the subtalar joint (9 mm apart). So: the joints of one group and side that together have at
     most three axes and lie within 60 mm are ONE handle, drawn as one ring set (each ring about its own joint's centre and
     axis) and picked at the first joint's centre. Every other joint is a handle of its own, as before. */
  var MATES = {};
  function mates(j){
    var L = MATES[j.id];
    if (L) return L;
    L = st.rig.joints.filter(function(o){ return !o.driven && o.dof && o.dof.length && o.group === j.group && o.side === j.side; });
    var n = 0, far = false;
    L.forEach(function(o){ n += o.dof.length; if (Math.hypot(o.c[0] - L[0].c[0], o.c[1] - L[0].c[1], o.c[2] - L[0].c[2]) > 60) far = true; });
    if (L.length < 2 || n > 3 || far || L.indexOf(j) < 0) L = [j];
    L.forEach(function(o){ MATES[o.id] = L; });
    return L;
  }
  function lead(j){ return mates(j)[0]; }
  function ringSet(j){ var out = []; mates(j).forEach(function(o){ o.dof.forEach(function(d, x){ out.push({j:o, x:x, d:d}); }); }); return out; }
  function handleName(j){ return (mates(j).length > 1 ? j.group : j.name) + (j.side === "l" || j.side === "r" ? " (" + j.side.toUpperCase() + ")" : ""); }
  function m12p(m, v){ return [m[0]*v[0] + m[1]*v[1] + m[2]*v[2] + m[3], m[4]*v[0] + m[5]*v[1] + m[6]*v[2] + m[7], m[8]*v[0] + m[9]*v[1] + m[10]*v[2] + m[11]]; }
  function m12r(m, v){ return [m[0]*v[0] + m[1]*v[1] + m[2]*v[2], m[4]*v[0] + m[5]*v[1] + m[6]*v[2], m[8]*v[0] + m[9]*v[1] + m[10]*v[2]]; }
  function unit(a){ var n = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0]/n, a[1]/n, a[2]/n]; }
  function cross(a, b){ return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]; }
  /* the joint in the world the geometry is in: its centre, and the instantaneous axis of each of its dofs
     (dof k turns about its own axis carried by the dofs before it, which is how fk composes them) */
  function jointFrame(j){
    if (!st.ready || !j || j.driven || !j.dof || !j.dof.length) return null;
    var par = st.rig.segs[j.seg][1];
    if (par < 0 || !st.M[par]) return null;
    var fm = j.ref >= 0 && st.M[j.ref] ? st.M[j.ref] : st.M[par];
    var q = st.pose.j[j.id], R = I3R, ax = [], k;
    for (k = 0; k < j.dof.length; k++){
      ax.push(unit(m12r(fm, C.mv3(R, j.dof[k].a))));
      R = C.mul3(R, C.rotM(j.dof[k].a, q[k]));
    }
    return {c:m12p(st.M[par], j.c), ax:ax};
  }
  /* a basis of the ring's plane. u is the direction the current value is drawn at, so a value v sits at the
     plane angle (v - now) degrees and the allowed band needs no second convention. */
  function basis(z){
    var t = Math.abs(z[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0], u = unit(cross(z, t));
    return {z:z, u:u, v:cross(z, u)};
  }
  function scr(p){ try { return E.toScreen ? E.toScreen(p) : null; } catch (e){ return null; } }
  /* Q384 / E2: the scale of the picture AT the joint, whichever way anything points. It used to be read along one in-plane
     direction of the ring: when that direction pointed at the eye, 10 mm of it covered almost no pixels, the "scale" came
     out many times too large and so did the ring (the elbow's, seen from behind: 150-460 px out instead of 52) -- or there
     was no ring at all. The three world axes together always cover the screen plane twice. */
  function mmPerPx(c){
    var a = scr(c), s = 0, k, p, b;
    if (!a) return null;
    for (k = 0; k < 3; k++){
      p = [c[0], c[1], c[2]]; p[k] += 10; b = scr(p);
      if (!b) return null;
      s += (b[0] - a[0]) * (b[0] - a[0]) + (b[1] - a[1]) * (b[1] - a[1]);
    }
    var d = Math.sqrt(s / 2);
    return d > 0.05 ? 10 / d : null;
  }
  function svgEl(tag, at){
    var e = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in at) if (at[k] != null) e.setAttribute(k, at[k]);
    return e;
  }
  function ringSvg(){
    if (rg.svg) return rg.svg;
    rg.svg = svgEl("svg", {id:"pz-rings", "aria-hidden":"true"});
    document.body.appendChild(rg.svg);
    return rg.svg;
  }
  function hideRings(){
    var was = rg.held;
    if (was && statusEl) statusEl.dataset.msg = "";
    rg.jid = null; rg.sig = ""; rg.held = null; rg.peek = null;
    if (was) chrome();      /* the status line says "Holding ..." no longer */
    viewSync();
    if (rg.raf){ cancelAnimationFrame(rg.raf); rg.raf = 0; }
    if (rg.svg) rg.svg.textContent = "";
  }
  /* The joint the pointer is over: the nearest projected joint centre within reach of its own rings. The one
     already showing its rings KEEPS them while the pointer is anywhere inside them -- without that, reaching
     for a ring 84 px out from the shoulder handed the rings to the elbow on the way, and the drag then
     started on a joint that was no longer the one under the rings. */
  var REACH = RPX[RPX.length - 1] + 26, PEEK = 30, HUB = 13;
  /* Q384 / E2, owner: "at the shoulder the rings are very far away and, to reach them, the pointer passes over other
     joints' rings, and the shoulder rings disappear ... it must be possible, in every pose, to rotate on the permitted axes."
     The rings were 52 / 68 / 84 px whatever the zoom: with the whole figure on the screen that is further than the next
     joint. Now the inner ring is 0.42 of the distance on the screen to the nearest other joint handle, between 20 and 52 px
     (the old size, reached when zoomed in), the others in the old proportion -- so the way from a joint's hub to its own
     rings does not cross another joint. And a ring seen edge-on (the knee's from the front) has no angle to read: it is
     drawn as a straight BAR through the hub instead, dragged along its length, so every permitted axis can be turned from
     every direction of view. */
  var EDGE = 0.18;
  function ringPx(J, c0){
    var near = 1e9;
    handles().forEach(function(h){ if (h.j !== J){ var d = Math.hypot(h.a[0] - c0[0], h.a[1] - c0[1]); if (d > 1 && d < near) near = d; } });
    var b = Math.max(20, Math.min(RPX[0], 0.42 * near));
    return [b, b * RPX[1] / RPX[0], b * RPX[2] / RPX[0]];
  }
  function reachOf(J, c0){ return ringPx(J, c0)[2] + 26; }
  function handles(){      /* every handle with where it is on the screen now */
    var out = [];
    st.rig.joints.forEach(function(j){
      if (j.driven || !j.dof || !j.dof.length || lead(j) !== j) return;
      var f = jointFrame(j); if (!f) return;
      var a = scr(f.c); if (a) out.push({j:j, a:a});
    });
    return out;
  }
  function nearest(x, y, reach){
    var best = null, bd = 1e9;
    var bw = 0;
    handles().forEach(function(h){      /* two joints that project onto (almost) the same spot -- left and right seen from the side: the one nearer the eye */
      var d = Math.hypot(h.a[0] - x, h.a[1] - y), w = h.a[2] || 0;
      if (d < bd - 10 || (Math.abs(d - bd) <= 10 && (w && bw ? w < bw : d < bd))){ bd = d; best = h.j; bw = w; }
    });
    return bd <= reach ? best : null;
  }
  function jointNear(x, y){
    if (!st.ready || !E.toScreen) return null;
    var cur = rg.jid ? jointOf(rg.jid) : null;
    if (cur){
      var cf = jointFrame(cur), ca = cf ? scr(cf.c) : null, REACH = ca ? reachOf(cur, ca) : 0;      /* E2: as far as this joint's own rings reach on the screen now */
      if (ca && Math.hypot(ca[0] - x, ca[1] - y) <= REACH) return cur;      /* inside its own rings the joint keeps them */
    }
    var j = nearest(x, y, RPX[2] + 26), jf = j ? jointFrame(j) : null, ja = jf ? scr(jf.c) : null;
    return ja && Math.hypot(ja[0] - x, ja[1] - y) <= reachOf(j, ja) ? j : null;
  }
  /* Q384, owner: "when a joint is chosen for moving -- stay moving its parts until another click on the joint, then it lets
     go." A click on a joint's hub (or the start of a turn on one of its rings) HOLDS that joint: its rings stay wherever the
     pointer goes, so a drag that wanders over the neighbouring joint still turns the one that was chosen. A second click
     on the hub lets go, a click on another joint's dot takes that one instead, Escape lets go. The hub and the dots are
     SVG targets of their own: the click never reaches the canvas, so it neither selects a structure nor turns the camera,
     and nothing here stops an event on its way down (the page history listens in the capture phase). */
  function hold(id){
    var j = id ? jointOf(id) : null;
    rg.held = j ? lead(j).id : null; rg.peek = null; rg.sig = "";
    if (rg.held){
      rg.jid = rg.held;
      holdMsg();
      showGroup(jointOf(rg.held).group);
    } else { if (statusEl) statusEl.dataset.msg = ""; if (rg.touch) rg.jid = null; chrome(); }
    if (rg.on){ if (rg.raf){ cancelAnimationFrame(rg.raf); rg.raf = 0; } drawRings(); }
    return rg.held;
  }
  function showGroup(g){      /* the held joint's own sliders are opened in the panel, when the panel has been built */
    if (!body) return;
    Array.prototype.forEach.call(body.querySelectorAll(".pz-g"), function(sec){
      var hb = sec.querySelector(".pz-gh"), rows = sec.querySelector(".pz-rows");
      if (hb && rows && hb.textContent === g && rows.hidden){ rows.hidden = false; hb.setAttribute("aria-expanded", "true"); }
    });
  }
  function hubClick(e){
    var id = e.currentTarget.dataset.j;
    e.preventDefault(); e.stopPropagation();
    hold(rg.held === id ? null : id);
  }
  function dotList(skip){      /* the joints offered as a dot to click: on a touch screen (no hover) every handle that has room, with a mouse only the one the pointer is near while another is held */
    var out = [];
    if (rg.touch){
      handles().sort(function(p, q){ return (p.a[2] || 0) - (q.a[2] || 0); }).forEach(function(h){      /* nearest the eye first: it keeps its dot where two coincide */
        if (h.j.id === skip) return;
        for (var i = 0; i < out.length; i++) if (Math.hypot(out[i].a[0] - h.a[0], out[i].a[1] - h.a[1]) < 30) return;
        out.push(h);
      });
    } else if (rg.peek && rg.peek !== skip){
      var pj = jointOf(rg.peek), pf = pj ? jointFrame(pj) : null, pa = pf ? scr(pf.c) : null;
      if (pa) out.push({j:pj, a:pa});
    }
    return out;
  }
  /* how open a ring looks from here: the two in-plane directions on the screen, the ratio of the ellipse's axes (0 = edge-on)
     and the direction of its long axis */
  function openness(c, B, r){
    var o = scr(c), pu = scr([c[0] + B.u[0]*r, c[1] + B.u[1]*r, c[2] + B.u[2]*r]), pv = scr([c[0] + B.v[0]*r, c[1] + B.v[1]*r, c[2] + B.v[2]*r]);
    if (!o || !pu || !pv) return null;
    var a = pu[0] - o[0], b = pv[0] - o[0], cc = pu[1] - o[1], d = pv[1] - o[1];
    var s1 = a*a + b*b + cc*cc + d*d, det = a*d - b*cc, disc = Math.sqrt(Math.max(0, s1*s1 - 4*det*det));
    var big = Math.sqrt((s1 + disc) / 2), small = Math.sqrt(Math.max(0, (s1 - disc) / 2));
    /* the long axis: the eigenvector of M M^T for the larger eigenvalue */
    var m00 = a*a + b*b, m01 = a*cc + b*d, m11 = cc*cc + d*d, l = (s1 + disc) / 2, ex = m01, ey = l - m00;
    if (Math.abs(ex) + Math.abs(ey) < 1e-9){ ex = l - m11; ey = m01; }
    if (Math.abs(ex) + Math.abs(ey) < 1e-9){ ex = 1; ey = 0; }
    var n = Math.hypot(ex, ey);
    return {ratio:big > 1e-9 ? small / big : 0, dir:[ex / n, ey / n]};
  }
  /* which way along the bar is "more": the way the part beyond the joint moves on the screen when the angle grows */
  function barSign(R, dir){
    var j = R.j, f = jointFrame(j), kids = st.rig.joints.filter(function(o){ return st.rig.segs[o.seg][1] === j.seg && !o.driven; });
    var kf = kids.length ? jointFrame(kids[0]) : null;
    if (!f || !kf) return 1;
    var p = [kf.c[0] - f.c[0], kf.c[1] - f.c[1], kf.c[2] - f.c[2]], a = f.ax[R.x], v = cross(a, p);
    var s0 = scr(kf.c), s1 = scr([kf.c[0] + v[0] * 0.2, kf.c[1] + v[1] * 0.2, kf.c[2] + v[2] * 0.2]);
    if (!s0 || !s1) return 1;
    return (s1[0] - s0[0]) * dir[0] + (s1[1] - s0[1]) * dir[1] < 0 ? -1 : 1;
  }
  function drawBar(svg, R, k, jc, open, px, qv){
    var d = R.d, sg = barSign(R, open.dir), dx = open.dir[0] * sg, dy = open.dir[1] * sg, off = (k - 1) * 9, nx = -dy * off, ny = dx * off;
    var L = Math.max(px, 34), x0 = jc[0] - dx * L + nx, y0 = jc[1] - dy * L + ny, x1 = jc[0] + dx * L + nx, y1 = jc[1] + dy * L + ny;
    var tt = (qv - d.lo) / Math.max(1e-9, d.hi - d.lo); tt = tt < 0 ? 0 : tt > 1 ? 1 : tt;
    var kx = x0 + (x1 - x0) * tt, ky = y0 + (y1 - y0) * tt;
    svg.appendChild(svgEl("line", {x1:x0.toFixed(1), y1:y0.toFixed(1), x2:x1.toFixed(1), y2:y1.toFixed(1), class:"pz-rom pz-bar", stroke:RCOL[k]}));
    svg.appendChild(svgEl("circle", {cx:kx.toFixed(1), cy:ky.toFixed(1), r:5, class:"pz-knob", fill:RCOL[k]}));
    var tx = svgEl("text", {x:(x1 + 6).toFixed(1), y:(y1 - 4).toFixed(1), class:"pz-rlab", fill:RCOL[k]});
    tx.textContent = (d.l || d.k) + " " + Math.round(qv) + "°";
    svg.appendChild(tx);
    var grab = svgEl("line", {x1:x0.toFixed(1), y1:y0.toFixed(1), x2:x1.toFixed(1), y2:y1.toFixed(1), class:"pz-grab pz-bargrab", stroke:RCOL[k]});
    grab.dataset.k = k; grab.dataset.x = R.x; grab.dataset.j = R.j.id; grab.dataset.bar = [dx, dy, 2 * L].join(",");
    grab.addEventListener("pointerdown", startDrag);
    svg.appendChild(grab);
  }
  function drawRings(){
    rg.raf = 0;
    viewSync();
    var J = rg.jid ? jointOf(rg.jid) : null, F = J ? jointFrame(J) : null, c0 = F ? scr(F.c) : null;
    if (!rg.on){ if (rg.svg) rg.svg.textContent = ""; return; }
    var svg = ringSvg(), dots = dotList(c0 ? J.id : null);
    if (!c0 && !dots.length){ svg.textContent = ""; rg.sig = ""; return; }
    var set = c0 ? ringSet(J) : [], mpp0 = c0 ? mmPerPx(F.c, F.ax[0].length ? basis(F.ax[0]).u : [1, 0, 0]) : 1;
    if (c0 && !mpp0){ svg.textContent = ""; rg.sig = ""; return; }
    var sig = (c0 ? [Math.round(c0[0]), Math.round(c0[1]), Math.round(1000 * mpp0), rg.jid, rg.held || "", Math.round(ringPx(J, c0)[0]), lastMvpSig()].concat(set.map(function(R){ return Math.round(st.pose.j[R.j.id][R.x] * 10); })) : ["-"])
      .concat(dots.map(function(h){ return h.j.id + ":" + Math.round(h.a[0]) + ":" + Math.round(h.a[1]); })).join(",");
    if (sig === rg.sig) return;                   /* the camera has not moved and nothing has turned */
    rg.sig = sig;
    /* The handle a finger is ON stays in the page while it is being dragged: the rings are redrawn at every step of a turn,
       and when that took the touched element away the browser let go of the gesture (its "no panning here" went with the
       element) and cancelled the drag as soon as the finger crossed a joint's dot. Found by the touch check of
       scripts/anatomy/q384/verify_pose_q384.py; the old, wider rings never led the finger over a dot. */
    var keep = rg.drag && rg.drag.el && rg.drag.el.parentNode === svg ? rg.drag.el : null;
    while (svg.lastChild && svg.lastChild !== keep) svg.removeChild(svg.lastChild);
    while (svg.firstChild && svg.firstChild !== keep) svg.removeChild(svg.firstChild);
    svg.setAttribute("class", rg.held ? "pz-holding" : "");
    var PX = c0 ? ringPx(J, c0) : RPX;
    rg.px = PX;
    set.slice(0, 3).forEach(function(R, k){
      var j = R.j, d = R.d, f = j === J ? F : jointFrame(j), q = st.pose.j[j.id], i;
      if (!f) return;
      var jc = scr(f.c), B = basis(f.ax[R.x]), mpp = j === J ? mpp0 : mmPerPx(f.c, B.u);
      if (!jc || !mpp) return;
      var r = PX[k] * mpp, pts = [], arc = [];
      var open = openness(f.c, B, r);
      if (open && open.ratio < EDGE){ drawBar(svg, R, k, jc, open, PX[k], q[R.x]); return; }
      var at = function(deg){
        var t = deg * Math.PI / 180, w = [f.c[0] + r*(B.u[0]*Math.cos(t) + B.v[0]*Math.sin(t)),
                                          f.c[1] + r*(B.u[1]*Math.cos(t) + B.v[1]*Math.sin(t)),
                                          f.c[2] + r*(B.u[2]*Math.cos(t) + B.v[2]*Math.sin(t))];
        return scr(w);
      };
      for (i = 0; i <= 64; i++){ var pp = at(i * 360 / 64); if (pp) pts.push(pp[0].toFixed(1) + "," + pp[1].toFixed(1)); }
      var lo = d.lo - q[R.x], hi = d.hi - q[R.x], steps = Math.max(2, Math.round(Math.abs(hi - lo) / 4));
      for (i = 0; i <= steps; i++){ var ap = at(lo + (hi - lo) * i / steps); if (ap) arc.push(ap[0].toFixed(1) + "," + ap[1].toFixed(1)); }
      if (pts.length < 8) return;
      svg.appendChild(svgEl("polyline", {points:pts.join(" "), class:"pz-ring", stroke:RCOL[k]}));
      if (arc.length > 1) svg.appendChild(svgEl("polyline", {points:arc.join(" "), class:"pz-rom", stroke:RCOL[k]}));
      /* the grab line is the allowed part only: you cannot start a turn from outside the range */
      var grab = svgEl("polyline", {points:(arc.length > 1 ? arc : pts).join(" "), class:"pz-grab", stroke:RCOL[k]});
      grab.dataset.k = k; grab.dataset.x = R.x; grab.dataset.r = PX[k];
      grab.dataset.j = j.id;        /* the drag starts on the joint these rings were DRAWN for */
      grab.addEventListener("pointerdown", startDrag);
      svg.appendChild(grab);
      var now = at(0);
      if (now){
        svg.appendChild(svgEl("line", {x1:jc[0].toFixed(1), y1:jc[1].toFixed(1), x2:now[0].toFixed(1), y2:now[1].toFixed(1), class:"pz-spoke", stroke:RCOL[k]}));
        var tx = svgEl("text", {x:(now[0] + 6).toFixed(1), y:(now[1] - 4).toFixed(1), class:"pz-rlab", fill:RCOL[k]});
        tx.textContent = (d.l || d.k) + " " + Math.round(q[R.x]) + "°";
        svg.appendChild(tx);
      }
    });
    dots.forEach(function(h){
      var g = svgEl("circle", {cx:h.a[0].toFixed(1), cy:h.a[1].toFixed(1), r:5, class:"pz-dot"});
      svg.appendChild(g);
      if (!rg.touch){ var dl = svgEl("text", {x:(h.a[0] + 9).toFixed(1), y:(h.a[1] + 4).toFixed(1), class:"pz-jlab pz-dlab"}); dl.textContent = handleName(h.j) + " – click to take"; svg.appendChild(dl); }
      var hit = svgEl("circle", {cx:h.a[0].toFixed(1), cy:h.a[1].toFixed(1), r:rg.touch ? 15 : HUB, class:"pz-hit"});
      hit.dataset.j = h.j.id; hit.addEventListener("click", hubClick); hit.addEventListener("pointerdown", function(e){ e.stopPropagation(); });
      svg.appendChild(hit);
    });
    if (!c0) return;
    var held = rg.held === J.id;
    if (held) svg.appendChild(svgEl("circle", {cx:c0[0].toFixed(1), cy:c0[1].toFixed(1), r:10, class:"pz-halo"}));
    svg.appendChild(svgEl("circle", {cx:c0[0].toFixed(1), cy:c0[1].toFixed(1), r:held ? 5.5 : 3.2, class:"pz-hub" + (held ? " pz-hub-held" : "")}));
    var nm = svgEl("text", {x:(c0[0] + (held ? 14 : 7)).toFixed(1), y:(c0[1] + 14).toFixed(1), class:"pz-jlab" + (held ? " pz-jheld" : "")});
    nm.textContent = handleName(J) + (held ? " – held" : "");
    svg.appendChild(nm);
    var hh = svgEl("circle", {cx:c0[0].toFixed(1), cy:c0[1].toFixed(1), r:rg.touch ? 15 : HUB, class:"pz-hit"});
    hh.dataset.j = J.id; hh.addEventListener("click", hubClick); hh.addEventListener("pointerdown", function(e){ e.stopPropagation(); });
    var tt = svgEl("title", {}); tt.textContent = held ? "Click to let go of this joint (Esc)" : "Click to hold this joint: its rings stay until you click it again";
    hh.appendChild(tt); svg.appendChild(hh);
  }
  function lastMvpSig(){      /* the direction of view, coarsely: a ring turns into a bar (and back) without its centre moving */
    var a = scr([0, 0, 0]), b = scr([0, 100, 0]), c = scr([100, 0, 0]);
    return a && b && c ? [Math.round(b[0] - a[0]), Math.round(b[1] - a[1]), Math.round(c[0] - a[0]), Math.round(c[1] - a[1])].join("/") : "";
  }
  function needDraw(){ if (rg.on && (rg.jid || rg.touch) && !rg.raf) rg.raf = requestAnimationFrame(drawRings); }
  function startDrag(e){
    var jid = e.currentTarget.dataset.j || rg.jid;
    var j = jid ? jointOf(jid) : null, f = j ? jointFrame(j) : null;
    if (!f) return;
    var hid = lead(j).id;
    if (hid !== rg.jid){ rg.jid = hid; rg.sig = ""; }
    var k = +e.currentTarget.dataset.k, x = e.currentTarget.dataset.x == null ? k : +e.currentTarget.dataset.x, d = j.dof[x];
    if (!d) return;
    e.preventDefault(); e.stopPropagation();
    var bar = e.currentTarget.dataset.bar;
    if (bar){      /* a ring seen edge-on: the drag runs along the bar, its whole length = the whole allowed range */
      var bb = bar.split(",").map(Number);
      rg.drag = {id:j.id, k:x, key:d.k, bar:[bb[0], bb[1]], len:bb[2], x0:e.clientX, y0:e.clientY, span:d.hi - d.lo, q0:st.pose.j[j.id][x], el:e.currentTarget};
    } else {
      var B = basis(f.ax[x]), mpp = mmPerPx(f.c, B.u);
      if (!mpp) return;
      var r = (+e.currentTarget.dataset.r || RPX[k]) * mpp, a0 = plane(f.c, B, r, e.clientX, e.clientY);
      if (a0 == null) return;
      rg.drag = {id:j.id, k:x, key:d.k, c:f.c, B:B, r:r, a0:a0, q0:st.pose.j[j.id][x], el:e.currentTarget};
    }
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err){}
    if (rg.held !== hid){ rg.held = hid; rg.peek = null; rg.sig = ""; showGroup(j.group); }      /* Q384: a turn takes hold of the joint, as a click on its hub does */
    if (statusEl) statusEl.dataset.msg = "1";
    status("Turning " + (d.l || d.k) + " of " + j.name + " on the model. " + d.lo + "° to " + d.hi + "°.");
  }
  /* where the pointer is, as an angle in the ring's own plane: the two in-plane directions are projected and
     the screen offset is solved in that 2x2 basis, so it reads correctly however the ring is foreshortened */
  function plane(c, B, r, x, y){
    var o = scr(c), pu = scr([c[0] + B.u[0]*r, c[1] + B.u[1]*r, c[2] + B.u[2]*r]), pv = scr([c[0] + B.v[0]*r, c[1] + B.v[1]*r, c[2] + B.v[2]*r]);
    if (!o || !pu || !pv) return null;
    var e1x = pu[0] - o[0], e1y = pu[1] - o[1], e2x = pv[0] - o[0], e2y = pv[1] - o[1];
    var det = e1x * e2y - e1y * e2x;
    if (Math.abs(det) < 1e-6) return null;        /* the ring is edge-on: there is no angle to read */
    var dx = x - o[0], dy = y - o[1];
    return Math.atan2((-dx * e1y + dy * e1x) / det, (dx * e2y - dy * e2x) / det) * 180 / Math.PI;
  }
  function moveDrag(e){
    var D = rg.drag; if (!D) return;
    if (D.bar){
      setJoint(D.id, D.key, D.q0 + ((e.clientX - D.x0) * D.bar[0] + (e.clientY - D.y0) * D.bar[1]) / D.len * D.span);
      rg.sig = ""; needDraw(); return;
    }
    var a = plane(D.c, D.B, D.r, e.clientX, e.clientY);
    if (a == null) return;
    var dd = a - D.a0;
    while (dd > 180) dd -= 360;
    while (dd < -180) dd += 360;
    setJoint(D.id, D.key, D.q0 + dd);
    rg.sig = "";
    needDraw();
  }
  function endDrag(){
    if (!rg.drag) return;
    rg.drag = null; flush();
    if (statusEl) statusEl.dataset.msg = "";
    chrome();
    if (rg.held){ holdMsg(); rg.sig = ""; needDraw(); }
  }
  function holdMsg(){
    if (!statusEl || !rg.held) return;
    statusEl.dataset.msg = "1";
    status("Holding " + handleName(jointOf(rg.held)) + ": drag a ring to turn it. Click the joint again, or press Esc, to let go.");
  }
  function ringsOn(on){
    rg.on = on == null ? !rg.on : !!on;
    var b = $("pz-rings-btn");
    if (b) b.setAttribute("aria-pressed", String(rg.on));
    if (!rg.on) hideRings(); else needDraw();
    return rg.on;
  }
  window.addEventListener("pointermove", function(e){
    if (rg.drag){ moveDrag(e); return; }
    if (!rg.on || !st.ready) return;
    if (e.target && e.target.closest && e.target.closest("#pz-rings")) return;      /* reaching for a ring must not hand the rings to a neighbour */
    var ui = e.target && e.target.closest && e.target.closest("#pose-panel,#q301-bar,#q301-sheet,.overlay,#tools,#topright");
    if (rg.held){      /* Q384: a held joint keeps its rings wherever the pointer goes; another joint under the pointer only offers its dot */
      var pk = ui || e.pointerType === "touch" ? null : nearest(e.clientX, e.clientY, PEEK);
      pk = pk && pk.id !== rg.held ? pk.id : null;
      if (pk !== rg.peek){ rg.peek = pk; rg.sig = ""; }
      needDraw(); return;
    }
    if (ui || rg.touch) return;      /* on a touch screen there is no pointer to be "over" a joint: the dots are tapped instead */
    var j = jointNear(e.clientX, e.clientY), id = j ? j.id : null;
    if (id !== rg.jid){ rg.jid = id; rg.sig = ""; if (!id) hideRings(); }
    needDraw();
  }, {passive:true});
  window.addEventListener("pointerup", endDrag);
  window.addEventListener("pointercancel", endDrag);
  /* which kind of pointer is in use decides how a joint is offered (hover with a mouse, dots under a finger); read in the
     capture phase and passively, so nothing is taken from the listeners that come after */
  try { rg.touch = !window.matchMedia("(hover:hover)").matches; } catch (err){}
  window.addEventListener("pointerdown", function(e){
    var t = e.pointerType === "touch";
    if (t !== rg.touch && (t || e.pointerType === "mouse")){ rg.touch = t; rg.sig = ""; if (!rg.held) rg.jid = null; if (rg.on && !rg.raf) rg.raf = requestAnimationFrame(drawRings); }
  }, {capture:true, passive:true});
  window.addEventListener("keydown", function(e){ if (e.key === "Escape" && rg.held && !rg.drag) hold(null); }, true);      /* capture: seen before a handler further in can end the event; it stops nothing itself */
  setInterval(function(){ if (rg.on && (rg.jid || rg.touch) && !rg.drag) needDraw(); }, 120);   /* follow the camera and any pose change from elsewhere */

  function ui(){
    if (E.toolbar){
      btn = el("button", (E.toolClass || "") + " pz-btn-tool", "Pose"); btn.type = "button"; btn.id = "btn-pose"; btn.setAttribute("aria-expanded", "false"); btn.disabled = true;
      btn.title = "Joint pose controls (kinematic preview, normal range of motion)"; E.toolbar.appendChild(btn);
      btn.addEventListener("click", function(){ open(); });
    }
    var rb = $("pz-rings-btn");
    if (rb) rb.addEventListener("click", function(){ ringsOn(); });
    var x = $("pz-close"); if (x) x.addEventListener("click", function(){ open(false); });
    var sb = $("pz-solo"); if (sb) sb.addEventListener("click", function(){ viewSet({solo:!view.solo}); });
    var mb = $("pz-min"); if (mb) mb.addEventListener("click", function(e){ e.stopPropagation(); viewSet({mini:!view.mini}); });
    if (panel){      /* the tile opens on a press of itself -- not at the end of dragging it somewhere */
      var px0 = 0, py0 = 0;
      panel.addEventListener("pointerdown", function(e){ px0 = e.clientX; py0 = e.clientY; });
      panel.addEventListener("click", function(e){
        if (!view.mini || (e.target.closest && e.target.closest("button"))) return;
        if (Math.hypot(e.clientX - px0, e.clientY - py0) < 6) viewSet({mini:false});
      });
    }
    var ph = panel && panel.querySelector(".pz-head"); if (ph && window.nmskDrag) nmskDrag(panel, ph);
    var bo = $("pose-banner-reset"); if (bo) bo.addEventListener("click", reset);
    var bp = $("pose-banner-open"); if (bp) bp.addEventListener("click", function(){ open(true); });
  }
  ui();
  var api = {
    ready:function(){ return st.ready; }, failed:function(){ return st.failed; }, open:open, update:flush, reset:reset, anatomical:anatomical, symmetric:symmetric, save:save, load:loadSaved, apply:apply,
    set:function(id, k, v){ var ok = setJoint(id, k, v); flush(); return ok; }, setRegion:function(id, k, v){ var ok = setRegion(id, k, v); flush(); return ok; },
    /* Q319: the spine, one vertebra at a time -- the other half of "either a specific joint or a segment" */
    setLevel:function(id, lv, k, v){ var ok = setLevel(id, lv, k, v); flush(); return ok; }, levels:levelsOf,
    pose:function(){ return JSON.parse(JSON.stringify(st.pose)); }, restPose:function(){ return JSON.parse(JSON.stringify(st.rest)); }, isRest:function(){ return st.ready ? isRest() : true; },
    rig:function(){ return st.rig; }, matrices:function(){ return st.M.map(function(m){ return Array.prototype.slice.call(m); }); },
    stats:function(){ return {ready:st.ready, ms:st.ms, changed:st.lastChanged, updates:st.updates, rigidVerts:st.verts.rigid, skinVerts:st.verts.skin, skinned:st.skins.length, failed:st.failed}; },
    setLink:function(on){ st.link = !!on; },
    /* Q318, for the browser check as much as for the page: the rings' own state, and the two steps a drag is */
    rings:ringsOn, screen:function(p){ return scr(p); },
    ringState:function(){
      var j = rg.jid ? jointOf(rg.jid) : null, f = j ? jointFrame(j) : null, set = j ? ringSet(j) : [];
      return {on:rg.on, joint:rg.jid, dragging:!!rg.drag, paths:rg.svg ? rg.svg.querySelectorAll(".pz-grab").length : 0,
              centre:f && E.toScreen ? scr(f.c) : null, axes:set.length,
              range:j ? set.map(function(R){ return [R.d.k, R.d.lo, R.d.hi]; }) : null,
              held:rg.held, peek:rg.peek, touch:rg.touch, rings:set.map(function(R){ return [R.j.id, R.d.k]; }), px:rg.px || null,
              handles:rg.svg ? Array.prototype.map.call(rg.svg.querySelectorAll(".pz-grab"), function(g){ return {j:g.dataset.j, k:+g.dataset.k, x:+g.dataset.x, bar:!!g.dataset.bar}; }) : [],
              dots:rg.svg ? Array.prototype.map.call(rg.svg.querySelectorAll(".pz-hit"), function(h){ return [h.dataset.j, +h.getAttribute("cx"), +h.getAttribute("cy")]; }) : []};
    },
    /* the pointer over a joint, without a pointer. A held joint is not let go by it (Q384). */
    ringHover:function(x, y){ if (rg.held){ drawRings(); return rg.jid; } var j = jointNear(x, y); rg.jid = j ? j.id : null; rg.sig = ""; if (rg.jid) drawRings(); else hideRings(); return rg.jid; },
    ringHold:function(id){ return hold(id || null); },
    setCouple:function(id, cid, v){ var ok = setCouple(id, cid, v); flush(); return ok; }, coupleValue:coupleValue,
    panelView:function(o){ return o ? viewSet(o) : {solo:view.solo, mini:view.mini, focus:rg.held || rg.jid || view.last || null}; },
    ringTurn:function(k, deg){        /* what a drag does, without a pointer: the same clamp, the same door */
      var j = rg.jid ? jointOf(rg.jid) : null, R = j ? ringSet(j)[k] : null; if (!R) return false;
      var ok = setJoint(R.j.id, R.d.k, st.pose.j[R.j.id][R.x] + deg);
      flush(); rg.sig = ""; drawRings(); return ok;
    }
  };
  load().then(function(ok){
    if (ok){ if (btn) btn.disabled = false; if (E.ready) E.ready(api); }
    else { if (btn){ btn.disabled = true; btn.title = st.failed || "No pose rig in this page"; if (!st.failed) btn.hidden = true; } if (st.failed) console.warn(st.failed); }
  }).catch(function(err){ st.failed = String(err && err.message || err); if (btn){ btn.disabled = true; btn.title = "Pose unavailable: " + st.failed; } console.warn("pose:", err); });
  return api;
}
