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

  return {decodeSkin:decodeSkin, rotM:rotM, mul3:mul3, tr3:tr3, mv3:mv3, prepare:prepare, jointR:jointR, elevation:elevation, defaultPose:defaultPose, anatomicalPose:anatomicalPose, fk:fk, sameM:sameM, rigid:rigid, skin:skin, clamp:clamp, levelRange:levelRange, levelTotal:levelTotal};
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
      var o = {i:si, kc:K, nc:nc, pal:Int16Array.from(pal), off:off, nv:nv, blob:blob, ready:false, k:3, idx:null, w:null, PM:new Float64Array(12 * pal.length)};
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
    var dirty = new Uint8Array(n);
    for (s = 0; s < n; s++) if (!C.sameM(st.M[s], st.last[s])) dirty[s] = 1;
    var changed = [];
    for (s = 0; s < n; s++){
      if (!dirty[s]) continue;
      var L = st.rigidBy[s];
      for (i = 0; i < L.length; i++){
        var si = L[i], r = E.rest(si), l = E.live(si);
        C.rigid(st.M[s], r.pos, r.nrm, l.pos, l.nrm); E.touch(si); changed.push(si);
      }
    }
    for (i = 0; i < st.skins.length; i++){
      var o = st.skins[i], any = false;
      for (q = 0; q < o.pal.length; q++) if (dirty[o.pal[q]]){ any = true; break; }
      if (!any) continue;
      for (q = 0; q < o.pal.length; q++) o.PM.set(st.M[o.pal[q]], 12 * q);
      if (!o.ready) C.decodeSkin(o, E.rest(o.i).pos);
      var r2 = E.rest(o.i), l2 = E.live(o.i);
      C.skin(o, o.PM, r2.pos, r2.nrm, l2.pos, l2.nrm); E.touch(o.i); changed.push(o.i);
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
    st.rig.joints.forEach(function(j){ if (j.driven) return; var v = d.j && d.j[j.id]; if (v && v.length === j.dof.length) P.j[j.id] = j.dof.map(function(x, i){ var n = +v[i]; return isFinite(n) ? C.clamp(n, x.lo, x.hi) : x.q0; }); });
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
    cells.push({j:j.id, x:x, rg:rg, nm:nm, lo:d.lo, hi:d.hi});
    return c;
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
          var rm = (rig.rom && d.rk && rig.rom[d.rk]) ? rig.rom[d.rk][3] : "";
          lab.title = (d.lo + " to " + d.hi + "°. " + rm + (j.note ? "  " + j.note : "")).trim();
          row.appendChild(lab);
          var cs = el("div", "pz-cells");
          if (jr) cs.appendChild(cell(jr, x, "r")); if (jl) cs.appendChild(cell(jl, x, "l"));
          row.appendChild(cs); rows.appendChild(row);
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
      r.dof.forEach(function(d, x){ var row = el("div", "pz-row"), lab = el("div", "pz-lab", d.l); var rm = rig.rom && d.rk && rig.rom[d.rk] ? rig.rom[d.rk][3] : ""; lab.title = (d.lo + " to " + d.hi + "°. " + rm + "  " + (r.note || "")).trim(); row.appendChild(lab); var cs = el("div", "pz-cells pz-one"); cs.appendChild(regCell(r, x)); row.appendChild(cs); rows.appendChild(row); });
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
    var help = el("details", "pz-help"), sm = el("summary", "", "Ranges of motion, method and limits");
    help.appendChild(sm);
    var p1 = el("p", "", "Hard bounds of every slider = the NORMAL range of motion (population averages, AAOS / AMA style, e.g. shoulder flexion 180, abduction 180, elbow flexion 150, hip flexion 120, knee flexion 135, ankle dorsiflexion 20 / plantarflexion 50; " +
      "values quoted from the standard references as remembered, several are assumptions; see docs/pose_rom_table.md). The shaded band on a slider is the normal range, the tick is the model's own pose, the faint line is 0. " +
      "An individual's range differs with age, sex and method. A model pose outside the normal range (e.g. a slightly hyperextended knee) is shown as it is and can only be moved into the range.");
    var p2 = el("p", "", "How it works: joint centres and axes are fitted to THIS page's own bones (hip and shoulder: femoral / humeral head spheres; elbow and knee: transepicondylar axis; ankle: malleoli; ...). Bones move rigidly with their segment; " +
      "muscles, vessels, nerves, ligaments, organs and skin follow by linear-blend skinning, weights from the distance to each segment's bones (smooth near joints), so a muscle stretches between its origin and insertion on the moving bones. " +
      "Clavicle and scapula follow the shoulder with a fixed 3:1 scapulohumeral rhythm. Pose preview: kinematic approximation, soft tissue not simulated (no collision, no volume preservation) - expect tissue to pass through bone and to stretch or crumple near extreme angles. " +
      "The clinical add-on tools (imaging, needle and the like) use the rest-pose meshes: reset the pose before using them.");
    help.appendChild(p1); help.appendChild(p2);
    if (rig.rom){ var tb = el("table", "pz-rom"); Object.keys(rig.rom).forEach(function(k){ var r = rig.rom[k], tr = el("tr"); tr.appendChild(el("td", "", r[2])); tr.appendChild(el("td", "", r[0] + " .. " + r[1] + "°")); tr.appendChild(el("td", "", r[3])); tb.appendChild(tr); }); help.appendChild(tb); }
    if (rig.notes){ var p3 = el("p", "", "Rig for this page: " + rig.notes); help.appendChild(p3); }
    body.appendChild(help);
    sync();
  }
  function open(on){
    st.open = on == null ? !st.open : !!on;
    if (panel){ panel.hidden = !st.open; panel.classList.toggle("pz-phone", !!(E.isPhone && E.isPhone())); }
    if (btn) btn.setAttribute("aria-expanded", String(st.open));
    if (st.open && !body.firstChild && st.ready) buildBody();
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
  var rg = {on:false, svg:null, jid:null, drag:null, raf:0, sig:""};
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
  function mmPerPx(c, u){
    var a = scr(c), b = scr([c[0] + u[0]*10, c[1] + u[1]*10, c[2] + u[2]*10]);
    if (!a || !b) return null;
    var d = Math.hypot(b[0] - a[0], b[1] - a[1]);
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
    rg.jid = null; rg.sig = "";
    if (rg.raf){ cancelAnimationFrame(rg.raf); rg.raf = 0; }
    if (rg.svg) rg.svg.textContent = "";
  }
  /* The joint the pointer is over: the nearest projected joint centre within reach of its own rings. The one
     already showing its rings KEEPS them while the pointer is anywhere inside them -- without that, reaching
     for a ring 84 px out from the shoulder handed the rings to the elbow on the way, and the drag then
     started on a joint that was no longer the one under the rings. */
  var REACH = RPX[RPX.length - 1] + 26;
  function jointNear(x, y){
    if (!st.ready || !E.toScreen) return null;
    var best = null, bd = 1e9, cur = rg.jid ? jointOf(rg.jid) : null;
    if (cur){
      var cf = jointFrame(cur), ca = cf ? scr(cf.c) : null;
      if (ca && Math.hypot(ca[0] - x, ca[1] - y) <= REACH) return cur;
    }
    st.rig.joints.forEach(function(j){
      if (j.driven || !j.dof || !j.dof.length) return;
      var f = jointFrame(j); if (!f) return;
      var a = scr(f.c); if (!a) return;
      var d = Math.hypot(a[0] - x, a[1] - y);
      if (d < bd){ bd = d; best = j; }
    });
    return bd <= REACH ? best : null;
  }
  function drawRings(){
    rg.raf = 0;
    var j = rg.jid ? jointOf(rg.jid) : null, f = j ? jointFrame(j) : null, c0 = f ? scr(f.c) : null;
    if (!rg.on || !c0){ if (rg.svg) rg.svg.textContent = ""; return; }
    var mpp = mmPerPx(f.c, f.ax[0].length ? basis(f.ax[0]).u : [1, 0, 0]);
    if (!mpp){ rg.svg.textContent = ""; return; }
    var q = st.pose.j[j.id];
    var sig = [Math.round(c0[0]), Math.round(c0[1]), Math.round(1000 * mpp), rg.jid].concat(q.map(function(v){ return Math.round(v * 10); })).join(",");
    if (sig === rg.sig) return;                   /* the camera has not moved and nothing has turned */
    rg.sig = sig;
    var svg = ringSvg();
    svg.textContent = "";
    var n = Math.min(3, j.dof.length), k, i;
    for (k = 0; k < n; k++){
      var d = j.dof[k], B = basis(f.ax[k]), r = RPX[k] * mpp, pts = [], arc = [];
      var at = function(deg){
        var t = deg * Math.PI / 180, w = [f.c[0] + r*(B.u[0]*Math.cos(t) + B.v[0]*Math.sin(t)),
                                          f.c[1] + r*(B.u[1]*Math.cos(t) + B.v[1]*Math.sin(t)),
                                          f.c[2] + r*(B.u[2]*Math.cos(t) + B.v[2]*Math.sin(t))];
        return scr(w);
      };
      for (i = 0; i <= 64; i++){ var pp = at(i * 360 / 64); if (pp) pts.push(pp[0].toFixed(1) + "," + pp[1].toFixed(1)); }
      var lo = d.lo - q[k], hi = d.hi - q[k], steps = Math.max(2, Math.round(Math.abs(hi - lo) / 4));
      for (i = 0; i <= steps; i++){ var ap = at(lo + (hi - lo) * i / steps); if (ap) arc.push(ap[0].toFixed(1) + "," + ap[1].toFixed(1)); }
      if (pts.length < 8) continue;
      svg.appendChild(svgEl("polyline", {points:pts.join(" "), class:"pz-ring", stroke:RCOL[k]}));
      if (arc.length > 1) svg.appendChild(svgEl("polyline", {points:arc.join(" "), class:"pz-rom", stroke:RCOL[k]}));
      /* the grab line is the allowed part only: you cannot start a turn from outside the range */
      var grab = svgEl("polyline", {points:(arc.length > 1 ? arc : pts).join(" "), class:"pz-grab", stroke:RCOL[k]});
      grab.dataset.k = k; grab.dataset.j = j.id;        /* the drag starts on the joint these rings were DRAWN for */
      grab.addEventListener("pointerdown", startDrag);
      svg.appendChild(grab);
      var now = at(0);
      if (now){
        svg.appendChild(svgEl("line", {x1:c0[0].toFixed(1), y1:c0[1].toFixed(1), x2:now[0].toFixed(1), y2:now[1].toFixed(1), class:"pz-spoke", stroke:RCOL[k]}));
        var tx = svgEl("text", {x:(now[0] + 6).toFixed(1), y:(now[1] - 4).toFixed(1), class:"pz-rlab", fill:RCOL[k]});
        tx.textContent = (d.l || d.k) + " " + Math.round(q[k]) + "°";
        svg.appendChild(tx);
      }
    }
    svg.appendChild(svgEl("circle", {cx:c0[0].toFixed(1), cy:c0[1].toFixed(1), r:3.2, class:"pz-hub"}));
    var nm = svgEl("text", {x:(c0[0] + 7).toFixed(1), y:(c0[1] + 14).toFixed(1), class:"pz-jlab"});
    nm.textContent = j.name + (j.side === "l" || j.side === "r" ? " (" + j.side.toUpperCase() + ")" : "");
    svg.appendChild(nm);
  }
  function needDraw(){ if (rg.on && rg.jid && !rg.raf) rg.raf = requestAnimationFrame(drawRings); }
  function startDrag(e){
    var jid = e.currentTarget.dataset.j || rg.jid;
    if (jid !== rg.jid){ rg.jid = jid; rg.sig = ""; }
    var j = jid ? jointOf(jid) : null, f = j ? jointFrame(j) : null;
    if (!f) return;
    var k = +e.currentTarget.dataset.k, d = j.dof[k];
    if (!d) return;
    e.preventDefault(); e.stopPropagation();
    var B = basis(f.ax[k]), mpp = mmPerPx(f.c, B.u);
    if (!mpp) return;
    var r = RPX[k] * mpp, a0 = plane(f.c, B, r, e.clientX, e.clientY);
    if (a0 == null) return;
    rg.drag = {id:j.id, k:k, key:d.k, c:f.c, B:B, r:r, a0:a0, q0:st.pose.j[j.id][k]};
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch (err){}
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
    if (e.target && e.target.closest && e.target.closest("#pose-panel,#q301-bar,#q301-sheet,.overlay,#tools,#topright")) return;
    var j = jointNear(e.clientX, e.clientY), id = j ? j.id : null;
    if (id !== rg.jid){ rg.jid = id; rg.sig = ""; if (!id) hideRings(); }
    needDraw();
  }, {passive:true});
  window.addEventListener("pointerup", endDrag);
  window.addEventListener("pointercancel", endDrag);
  setInterval(function(){ if (rg.on && rg.jid && !rg.drag) needDraw(); }, 120);   /* follow the camera and any pose change from elsewhere */

  function ui(){
    if (E.toolbar){
      btn = el("button", (E.toolClass || "") + " pz-btn-tool", "Pose"); btn.type = "button"; btn.id = "btn-pose"; btn.setAttribute("aria-expanded", "false"); btn.disabled = true;
      btn.title = "Joint pose controls (kinematic preview, normal range of motion)"; E.toolbar.appendChild(btn);
      btn.addEventListener("click", function(){ open(); });
    }
    var rb = $("pz-rings-btn");
    if (rb) rb.addEventListener("click", function(){ ringsOn(); });
    var x = $("pz-close"); if (x) x.addEventListener("click", function(){ open(false); });
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
      var j = rg.jid ? jointOf(rg.jid) : null, f = j ? jointFrame(j) : null;
      return {on:rg.on, joint:rg.jid, dragging:!!rg.drag, paths:rg.svg ? rg.svg.querySelectorAll(".pz-grab").length : 0,
              centre:f && E.toScreen ? scr(f.c) : null, axes:f ? f.ax.length : 0,
              range:j ? j.dof.map(function(d){ return [d.k, d.lo, d.hi]; }) : null};
    },
    ringHover:function(x, y){ var j = jointNear(x, y); rg.jid = j ? j.id : null; rg.sig = ""; if (rg.jid) drawRings(); else hideRings(); return rg.jid; },
    ringTurn:function(k, deg){        /* what a drag does, without a pointer: the same clamp, the same door */
      var j = rg.jid ? jointOf(rg.jid) : null; if (!j || !j.dof[k]) return false;
      var ok = setJoint(j.id, j.dof[k].k, st.pose.j[j.id][k] + deg);
      flush(); rg.sig = ""; drawRings(); return ok;
    }
  };
  load().then(function(ok){
    if (ok){ if (btn) btn.disabled = false; if (E.ready) E.ready(api); }
    else { if (btn){ btn.disabled = true; btn.title = st.failed || "No pose rig in this page"; if (!st.failed) btn.hidden = true; } if (st.failed) console.warn(st.failed); }
  }).catch(function(err){ st.failed = String(err && err.message || err); if (btn){ btn.disabled = true; btn.title = "Pose unavailable: " + st.failed; } console.warn("pose:", err); });
  return api;
}
