/* Q303: the principal axes of a structure's own vertices -- shared, so "facing me" computes the same thing on both
   engines. Jacobi rotations on the 3x3 covariance: exact to machine precision for a symmetric matrix, no library, and
   the same code on both templates (the rule Q301 D3(7) set when it refused to ship physics that would have been
   computed differently in the two engines).
   The vertices are SAMPLED with a stride when there are many: a principal axis is a second moment, and a stride over a
   triangulated surface leaves it unchanged to well inside the precision this is used at (the camera is then pointed with
   it). The stride actually used is reported, so the number is never silently approximate.
     NMSKPCA.axes(pts, stride) -> {n, c:[3], e:[[3],[3],[3]], lam:[3], ext:[3], stride}
   pts is an array of flat xyz arrays (one per structure); lam is sorted descending and e[k] is lam[k]'s axis, so e[2] is
   the axis of LEAST spread. ext[k] is the structure's full extent along e[k], in the model's own millimetres. */
var NMSKPCA = (function(){
  "use strict";
  var MAXPTS = 6000;
  function axes(pts, stride){
    var all = [].concat(pts || []).filter(function(a){ return a && a.length >= 3; });
    if (!all.length) return null;
    var tot = 0;
    all.forEach(function(a){ tot += Math.floor(a.length / 3); });
    if (!tot) return null;
    var st = stride | 0;
    if (st < 1) st = Math.max(1, Math.ceil(tot / MAXPTS));
    var n = 0, cx = 0, cy = 0, cz = 0, i, a, k;
    for (i = 0; i < all.length; i++){
      a = all[i];
      for (k = 0; k + 2 < a.length; k += 3 * st){ cx += a[k]; cy += a[k + 1]; cz += a[k + 2]; n++; }
    }
    if (n < 3) return null;
    cx /= n; cy /= n; cz /= n;
    var m = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (i = 0; i < all.length; i++){
      a = all[i];
      for (k = 0; k + 2 < a.length; k += 3 * st){
        var x = a[k] - cx, y = a[k + 1] - cy, z = a[k + 2] - cz;
        m[0][0] += x * x; m[0][1] += x * y; m[0][2] += x * z;
        m[1][1] += y * y; m[1][2] += y * z; m[2][2] += z * z;
      }
    }
    m[0][0] /= n; m[0][1] /= n; m[0][2] /= n; m[1][1] /= n; m[1][2] /= n; m[2][2] /= n;
    m[1][0] = m[0][1]; m[2][0] = m[0][2]; m[2][1] = m[1][2];
    /* Jacobi: zero the largest off-diagonal element in turn; V accumulates the rotations */
    var V = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], sweep;
    for (sweep = 0; sweep < 32; sweep++){
      var p = 0, q = 1, best = Math.abs(m[0][1]);
      if (Math.abs(m[0][2]) > best){ best = Math.abs(m[0][2]); p = 0; q = 2; }
      if (Math.abs(m[1][2]) > best){ best = Math.abs(m[1][2]); p = 1; q = 2; }
      if (best < 1e-12) break;
      var th = 0.5 * Math.atan2(2 * m[p][q], m[q][q] - m[p][p]), c = Math.cos(th), s = Math.sin(th);
      var M = [[m[0][0], m[0][1], m[0][2]], [m[1][0], m[1][1], m[1][2]], [m[2][0], m[2][1], m[2][2]]];
      var R = [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
      R[p][p] = c; R[q][q] = c; R[p][q] = s; R[q][p] = -s;
      var T = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], r2, c2, k2;
      for (r2 = 0; r2 < 3; r2++) for (c2 = 0; c2 < 3; c2++){ var v = 0; for (k2 = 0; k2 < 3; k2++) v += R[k2][r2] * M[k2][c2]; T[r2][c2] = v; }
      for (r2 = 0; r2 < 3; r2++) for (c2 = 0; c2 < 3; c2++){ var v2 = 0; for (k2 = 0; k2 < 3; k2++) v2 += T[r2][k2] * R[k2][c2]; m[r2][c2] = v2; }
      var NV = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
      for (r2 = 0; r2 < 3; r2++) for (c2 = 0; c2 < 3; c2++){ var v3 = 0; for (k2 = 0; k2 < 3; k2++) v3 += V[r2][k2] * R[k2][c2]; NV[r2][c2] = v3; }
      V = NV;
    }
    var ev = [{l:m[0][0], v:[V[0][0], V[1][0], V[2][0]]},
              {l:m[1][1], v:[V[0][1], V[1][1], V[2][1]]},
              {l:m[2][2], v:[V[0][2], V[1][2], V[2][2]]}];
    ev.sort(function(x, y){ return y.l - x.l; });
    ev.forEach(function(e){ var L = Math.hypot(e.v[0], e.v[1], e.v[2]) || 1; e.v = [e.v[0] / L, e.v[1] / L, e.v[2] / L]; });
    /* the full extent along each axis, so the framing matches the picture rather than a bounding sphere */
    var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30];
    for (i = 0; i < all.length; i++){
      a = all[i];
      for (k = 0; k + 2 < a.length; k += 3 * st){
        var dx = a[k] - cx, dy = a[k + 1] - cy, dz = a[k + 2] - cz;
        for (var j = 0; j < 3; j++){
          var t = dx * ev[j].v[0] + dy * ev[j].v[1] + dz * ev[j].v[2];
          if (t < lo[j]) lo[j] = t; if (t > hi[j]) hi[j] = t;
        }
      }
    }
    return {n:n, stride:st, c:[cx, cy, cz], e:[ev[0].v, ev[1].v, ev[2].v],
            lam:[Math.max(0, ev[0].l), Math.max(0, ev[1].l), Math.max(0, ev[2].l)],
            ext:[hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]]};
  }
  return {axes:axes, maxPoints:function(){ return MAXPTS; }};
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKPCA;
