/* NMSK Atlas -- PRIVATE clinical layer (clinical/LICENSE_PRIVATE.md): IMAGING mode, phase 1 = CT + MRI simulation (Q226).
 *
 * Staged beside a viewer page as clinical_imaging_tool.js (+ clinical_imaging_tissues.json) by
 * scripts/clinical/stage_clinical_files.py. The public pages only carry a generic script-tag hook; without this file they are
 * plain atlases. The tool chains onto window.NMSKClinical.attach (the needle add-on, if present, still gets the same API).
 *
 * WHAT IT IS: a SIMULATION computed from the segmented anatomical MESHES of the viewer. The cut plane (and its slab) is
 * intersected with every mesh (signed vertex distance, triangle-plane segments, even-odd scan-line fill per structure, painter
 * order by tissue priority); each pixel gets a tissue class from the mapping table (clinical/data/imaging_tissues.json);
 * CT = literature HU per class, MRI = standard sequence equations on literature T1/T2/PD per class (1.5 T).
 * IT IS NOT A SCAN: no patient data, no physics of acquisition or reconstruction beyond the stated equations.
 *
 * Layout: 1 kernel (serialised into a Web Worker), 2 pure helpers (classification, signal), 3 engine (geometry package,
 * worker queue, MPR planes), 4 UI (split screen, views, controls, info), 5 attach. A test hook is exported on
 * globalThis.NMSKImagingLib in node. */
(function (G) {
  "use strict";
  if (G.NMSKClinical && G.NMSKClinical.imaging) return;                   // Q239: the code is pasted into the page AND the file beside it may load too: the first one wins
  var VERSION = "q226.3";                                                   // Q246: continuity (partial volume, hole fill, 3-D coherent noise) keeps the q226 line

  /* ========================================================================================================
   * 1. KERNEL -- self-contained (no outer references): its source text is evaluated inside a Worker.
   * ====================================================================================================== */
  function KERNEL_FACTORY() {
    var Gm = null, cacheKey = null, cand = [], VX = new Float32Array(0), VY = new Float32Array(0), VD = new Float32Array(0);
    var vOff = null, sdmin = null, sdmax = null, segs = new Float32Array(1 << 16), xs = new Float32Array(1 << 16);
    var rowCnt = new Int32Array(0), rowPtr = new Int32Array(0), axisInfo = null, M = new Uint8Array(0), DTb = new Uint16Array(0);
    var bx0 = 0, bx1 = -1, by0 = 0, by1 = -1, parityBad = 0, repaired = 0, triCount = 0;
    var prevSp = new Float64Array(2048), curBuf = new Int32Array(0);

    function setGeometry(g) {
      Gm = g; cacheKey = null;
      var n = g.n, maxNV = 0, i;
      for (i = 0; i < n; i++) maxNV = Math.max(maxNV, g.vStart[i + 1] - g.vStart[i]);
      axisInfo = new Float32Array(n * 7);
      for (i = 0; i < n; i++) if (g.kind[i] === 1) pcaAxis(i);          // long bones: centroid, axis, length
      return {n: n, maxNV: maxNV};
    }
    function pcaAxis(s) {
      var p = Gm.pos, a = Gm.vStart[s], b = Gm.vStart[s + 1], nv = b - a, step = Math.max(1, Math.floor(nv / 4000)), k, cx = 0, cy = 0, cz = 0, m = 0;
      for (k = a; k < b; k += step) { cx += p[3 * k]; cy += p[3 * k + 1]; cz += p[3 * k + 2]; m++; }
      if (m < 3) return;
      cx /= m; cy /= m; cz /= m;
      var xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
      for (k = a; k < b; k += step) { var dx = p[3 * k] - cx, dy = p[3 * k + 1] - cy, dz = p[3 * k + 2] - cz; xx += dx * dx; xy += dx * dy; xz += dx * dz; yy += dy * dy; yz += dy * dz; zz += dz * dz; }
      var ax = 0.3, ay = 1, az = 0.2, it, l;
      for (it = 0; it < 40; it++) {
        var nx = xx * ax + xy * ay + xz * az, ny = xy * ax + yy * ay + yz * az, nz = xz * ax + yz * ay + zz * az;
        l = Math.hypot(nx, ny, nz) || 1; ax = nx / l; ay = ny / l; az = nz / l;
      }
      var lo = 1e30, hi = -1e30;
      for (k = a; k < b; k++) { var d = (p[3 * k] - cx) * ax + (p[3 * k + 1] - cy) * ay + (p[3 * k + 2] - cz) * az; if (d < lo) lo = d; if (d > hi) hi = d; }
      var mid = (lo + hi) / 2;                                              // centre the axis on the extent, not the vertex mean
      axisInfo.set([cx + ax * mid, cy + ay * mid, cz + az * mid, ax, ay, az, Math.max(hi - lo, 1e-3)], s * 7);
    }

    /* ---- segments of one structure at plane offset s (pixel coordinates); returns the count ---- */
    function collect(st, s) {
      var g = Gm, idx = g.idx, t0 = g.tStart[st], t1 = g.tStart[st + 1], vo = vOff[st] - g.vStart[st], ns = 0, t;
      for (t = t0; t < t1; t++) {
        var a = idx[3 * t] + vo, b = idx[3 * t + 1] + vo, c = idx[3 * t + 2] + vo;
        var m = (VD[a] > s ? 1 : 0) | (VD[b] > s ? 2 : 0) | (VD[c] > s ? 4 : 0);
        if (m === 0 || m === 7) continue;
        var p, q, r;                                                        // p = the lone vertex, q and r the others
        if (m === 1 || m === 6) { p = a; q = b; r = c; } else if (m === 2 || m === 5) { p = b; q = c; r = a; } else { p = c; q = a; r = b; }
        var dp = VD[p] - s, t1_ = dp / (dp - (VD[q] - s)), t2_ = dp / (dp - (VD[r] - s));
        if (ns * 4 + 4 > segs.length) { var ng = new Float32Array(segs.length * 2); ng.set(segs); segs = ng; }
        var o = ns * 4;
        segs[o] = VX[p] + t1_ * (VX[q] - VX[p]); segs[o + 1] = VY[p] + t1_ * (VY[q] - VY[p]);
        segs[o + 2] = VX[p] + t2_ * (VX[r] - VX[p]); segs[o + 3] = VY[p] + t2_ * (VY[r] - VY[p]);
        ns++;
      }
      triCount += t1 - t0;
      return ns;
    }
    /* ---- even-odd scan-line fill of `ns` segments into mask m (1 = inside); sets the bbox globals ---- */
    function fillMask(ns, W, H, m) {
      var j, k, o, y0, y1, x0, x1, ya, yb, j0, j1;
      if (rowCnt.length < H + 2) { rowCnt = new Int32Array(H + 2); rowPtr = new Int32Array(H + 2); }
      rowCnt.fill(0, 0, H + 1);
      bx0 = W; bx1 = -1; by0 = H; by1 = -1;
      for (k = 0; k < ns; k++) {
        y0 = segs[4 * k + 1]; y1 = segs[4 * k + 3];
        if (y0 === y1) continue;
        if (y0 < y1) { ya = y0; yb = y1; } else { ya = y1; yb = y0; }
        j0 = Math.ceil(ya - 0.5); j1 = Math.ceil(yb - 0.5) - 1;
        if (j0 < 0) j0 = 0; if (j1 > H - 1) j1 = H - 1;
        for (j = j0; j <= j1; j++) rowCnt[j]++;
      }
      var tot = 0;
      for (j = 0; j < H; j++) { rowPtr[j] = tot; tot += rowCnt[j]; }
      rowPtr[H] = tot;
      if (xs.length < tot + 1) xs = new Float32Array(Math.max(tot + 1, xs.length * 2));
      if (curBuf.length < H + 2) curBuf = new Int32Array(H + 2);
      var cur = curBuf; cur.fill(0, 0, H + 1);
      for (k = 0; k < ns; k++) {
        o = 4 * k; x0 = segs[o]; y0 = segs[o + 1]; x1 = segs[o + 2]; y1 = segs[o + 3];
        if (y0 === y1) continue;
        if (y0 > y1) { var tx = x0, ty = y0; x0 = x1; y0 = y1; x1 = tx; y1 = ty; }
        j0 = Math.ceil(y0 - 0.5); j1 = Math.ceil(y1 - 0.5) - 1;
        if (j0 < 0) j0 = 0; if (j1 > H - 1) j1 = H - 1;
        var sl = (x1 - x0) / (y1 - y0);
        for (j = j0; j <= j1; j++) xs[rowPtr[j] + cur[j]++] = x0 + (j + 0.5 - y0) * sl;
      }
      var sp, nOdd = 0;
      for (j = 0; j < H; j++) {                                               // pass 1: sort every row, paint the even ones
        var n = cur[j], base = rowPtr[j], e, i, v;
        if (n === 0) continue;
        for (i = 1; i < n; i++) { v = xs[base + i]; e = i - 1; while (e >= 0 && xs[base + e] > v) { xs[base + e + 1] = xs[base + e]; e--; } xs[base + e + 1] = v; }
        if (n & 1) { parityBad++; nOdd++; continue; }
        for (sp = 0; sp < n; sp += 2) paintSpan(xs[base + sp], xs[base + sp + 1], j, W, m);
      }
      if (nOdd) for (j = 0; j < H; j++) if (cur[j] & 1) repairRow(j, cur, W, H, m);
    }
    /* Q246: an odd crossing count = an open seam, a self-intersection or a non-manifold edge of the mesh on that scan line.  The row is repaired with the rule "the span set of the row must
       agree best with the rows above and below" (smallest total length of the symmetric difference): candidates = drop one crossing, or add one partner at a boundary of the neighbour rows.
       No new tissue is invented: a repaired row is the same structure's own crossings plus at most one partner on the neighbours' outline; with no even neighbour the row is left empty. */
    var cA = new Float64Array(256), cBest = new Float64Array(256);
    function xorLen(a, na, b, nb) {
      var i = 0, j = 0, fa = 0, fb = 0, pos = 0, len = 0, x;
      while (i < na || j < nb) {
        if (j >= nb || (i < na && a[i] <= b[j])) { x = a[i++]; if (fa !== fb) len += x - pos; fa ^= 1; } else { x = b[j++]; if (fa !== fb) len += x - pos; fb ^= 1; }
        pos = x;
      }
      return len;
    }
    function repairRow(j, cur, W, H, m) {
      var n = cur[j], base = rowPtr[j], i, q, refs = [], wts = [], c, dU = 0, dL = 0, r;
      if (n >= 120) return;
      for (r = j - 1; r >= 0 && j - r <= 80; r--) if (cur[r] > 0 && !(cur[r] & 1)) { refs.push(r); dU = j - r; break; }          // nearest consistent row above and below (a run of odd rows is repaired from its ends)
      for (r = j + 1; r < H && r - j <= 80; r++) if (cur[r] > 0 && !(cur[r] & 1)) { refs.push(r); dL = r - j; break; }
      if (!refs.length) return;
      if (refs.length === 2) { wts = [dL / (dU + dL), dU / (dU + dL)]; } else wts = [1];
      var best = 1e30, nb = 0;
      function score(arr, na) { var t = 0; for (var k = 0; k < refs.length; k++) t += wts[k] * xorLen(arr, na, xs.subarray(rowPtr[refs[k]], rowPtr[refs[k]] + cur[refs[k]]), cur[refs[k]]); return t; }
      for (i = 0; i < n; i++) {                                               // drop crossing i
        var na = 0; for (q = 0; q < n; q++) if (q !== i) cA[na++] = xs[base + q];
        var sc = score(cA, na); if (sc < best) { best = sc; nb = na; cBest.set(cA.subarray(0, na)); }
      }
      for (r = 0; r < refs.length; r++) {                                     // add one partner at a boundary of a neighbour row
        var rb = rowPtr[refs[r]], rn = cur[refs[r]];
        for (c = 0; c < rn; c++) {
          var p = xs[rb + c], na2 = 0, put = false;
          for (q = 0; q < n; q++) { if (!put && p < xs[base + q]) { cA[na2++] = p; put = true; } cA[na2++] = xs[base + q]; }
          if (!put) cA[na2++] = p;
          var sc2 = score(cA, na2); if (sc2 < best) { best = sc2; nb = na2; cBest.set(cA.subarray(0, na2)); }
        }
      }
      for (i = 0; i + 1 < nb; i += 2) paintSpan(cBest[i], cBest[i + 1], j, W, m);
      repaired++;
    }
    function clearBox(W) { for (var j = by0; j <= by1; j++) M.fill(0, j * W + bx0, j * W + bx1 + 1); }
    function paintSpan(a, b, j, W, m) {
      var i0 = Math.ceil(a - 0.5), i1 = Math.ceil(b - 0.5) - 1;
      if (i0 < 0) i0 = 0; if (i1 > W - 1) i1 = W - 1;
      if (i1 < i0) return;
      m.fill(1, j * W + i0, j * W + i1 + 1);
      if (i0 < bx0) bx0 = i0; if (i1 > bx1) bx1 = i1; if (j < by0) by0 = j; if (j > by1) by1 = j;
    }
    function drawLabel(ns, W, H, lab, sid, cls, st, ss) {                   // a sheet is drawn one IMAGE pixel wide (ss x ss sub-pixels per point), positioned to 1/ss pixel
      var h = ss >> 1;
      for (var k = 0; k < ns; k++) {
        var x0 = segs[4 * k], y0 = segs[4 * k + 1], x1 = segs[4 * k + 2], y1 = segs[4 * k + 3];
        var len = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)), n = Math.ceil(len * 2 / ss) + 1, q, a, b;
        for (q = 0; q <= n; q++) {
          var f = n ? q / n : 0, xi = Math.floor(x0 + (x1 - x0) * f) - h, yi = Math.floor(y0 + (y1 - y0) * f) - h;
          for (b = 0; b < ss; b++) for (a = 0; a < ss; a++) { var xx = xi + a, yy = yi + b; if (xx >= 0 && xx < W && yy >= 0 && yy < H) { lab[yy * W + xx] = cls; if (sid) sid[yy * W + xx] = st; } }
        }
      }
    }
    function drawOutline(ns, W, H, m) {                                     // 8-connected raster of every segment (skin contour)
      for (var k = 0; k < ns; k++) {
        var x0 = segs[4 * k], y0 = segs[4 * k + 1], x1 = segs[4 * k + 2], y1 = segs[4 * k + 3];
        var len = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)), n = Math.ceil(len * 2) + 1, q;
        for (q = 0; q <= n; q++) {
          var f = n ? q / n : 0, xi = Math.floor(x0 + (x1 - x0) * f), yi = Math.floor(y0 + (y1 - y0) * f);
          if (xi >= 0 && xi < W && yi >= 0 && yi < H) m[yi * W + xi] = 1;
        }
      }
    }

    /* ---- chamfer 3-4 distance to the nearest 0 pixel inside a (rw x rh) window; INF = 65535 for inside initial ---- */
    function chamfer(D, rw, rh) {
      var x, y, INF = 65000, v, w = rw;
      for (y = 0; y < rh; y++) for (x = 0; x < rw; x++) {
        var i = y * w + x; if (D[i] === 0) continue;
        v = INF;
        if (x > 0) v = Math.min(v, D[i - 1] + 3);
        if (y > 0) { v = Math.min(v, D[i - w] + 3); if (x > 0) v = Math.min(v, D[i - w - 1] + 4); if (x < rw - 1) v = Math.min(v, D[i - w + 1] + 4); }
        D[i] = v;
      }
      for (y = rh - 1; y >= 0; y--) for (x = rw - 1; x >= 0; x--) {
        var j = y * w + x; if (D[j] === 0) continue;
        v = D[j];
        if (x < rw - 1) v = Math.min(v, D[j + 1] + 3);
        if (y < rh - 1) { v = Math.min(v, D[j + w] + 3); if (x < rw - 1) v = Math.min(v, D[j + w + 1] + 4); if (x > 0) v = Math.min(v, D[j + w - 1] + 4); }
        D[j] = v;
      }
    }

    /* ---- exact Euclidean distance (Felzenszwalb-Huttenlocher) to the nearest 0 pixel; D in/out as Float32 squared distance ---- */
    var eF = new Float64Array(0), eD = new Float64Array(0), eV = new Int32Array(0), eZ = new Float64Array(0);
    function dt1(n) {
      var k = 0, q, r, s;
      eV[0] = 0; eZ[0] = -1e30; eZ[1] = 1e30;
      for (q = 1; q < n; q++) {
        for (;;) { r = eV[k]; s = ((eF[q] + q * q) - (eF[r] + r * r)) / (2 * q - 2 * r); if (s <= eZ[k]) k--; else break; if (k < 0) { k = 0; break; } }
        k++; eV[k] = q; eZ[k] = s; eZ[k + 1] = 1e30;
      }
      k = 0;
      for (q = 0; q < n; q++) { while (eZ[k + 1] < q) k++; r = eV[k]; eD[q] = (q - r) * (q - r) + eF[r]; }
    }
    function edt(D, rw, rh) {                                             // D: Float32Array(rw*rh), 0 = background, else INF; result: squared distance in pixels
      var m = Math.max(rw, rh) + 2, x, y;
      if (eF.length < m) { eF = new Float64Array(m); eD = new Float64Array(m); eV = new Int32Array(m); eZ = new Float64Array(m + 1); }
      for (x = 0; x < rw; x++) { for (y = 0; y < rh; y++) eF[y] = D[y * rw + x]; dt1(rh); for (y = 0; y < rh; y++) D[y * rw + x] = eD[y]; }
      for (y = 0; y < rh; y++) { for (x = 0; x < rw; x++) eF[x] = D[y * rw + x]; dt1(rw); for (x = 0; x < rw; x++) D[y * rw + x] = eD[x]; }
    }

    /* ---- the slice ----
     * R: {key, W, H, O[3], u[3], v[3], n[3], u0, v0, px, s (offset), wantSid, skinMm, ids{air,fat,skin,cort,canc,marrow}, bone{kind->params}} */
    function slice(R) {
      /* Q246: R.ss > 1 rasterises at ss x the pixel resolution (same plane, same window): `fine` = that label image (area coverage = partial volume), `lab` / `sid` = its centre samples */
      var t0 = Date.now(), g = Gm, ss = R.ss > 1 ? Math.min(4, R.ss | 0) : 1, Wc = R.W, Hc = R.H, W = Wc * ss, H = Hc * ss, N = W * H, px = R.px / ss, s = R.s, i, j, k;
      parityBad = 0; repaired = 0; triCount = 0;
      if (R.key !== cacheKey) {                                             // vertex pass once per plane / window
        cacheKey = R.key; cand.length = 0;
        var Ox = R.O[0], Oy = R.O[1], Oz = R.O[2], ux = R.u[0], uy = R.u[1], uz = R.u[2], vx = R.v[0], vy = R.v[1], vz = R.v[2], nx = R.n[0], ny = R.n[1], nz = R.n[2];
        var smin = R.smin, smax = R.smax, tot = 0, c, bb;
        var order = g.order, skinL = g.skinList, all = [];
        for (i = 0; i < skinL.length; i++) all.push(skinL[i]);
        for (i = 0; i < order.length; i++) all.push(order[i]);
        var keep = [];
        for (i = 0; i < all.length; i++) {
          var st = all[i]; bb = st * 6;
          if (R.mask && !g.skin[st] && !R.mask[st]) continue;                 // Q228: optional exclusion list (hidden structures); skin is never excluded
          var dmn = 1e30, dmx = -1e30, xmn = 1e30, xmx = -1e30, ymn = 1e30, ymx = -1e30;
          for (c = 0; c < 8; c++) {
            var X = g.bbox[bb + ((c & 1) ? 3 : 0)] - Ox, Y = g.bbox[bb + 1 + ((c & 2) ? 3 : 0)] - Oy, Z = g.bbox[bb + 2 + ((c & 4) ? 3 : 0)] - Oz;
            var d = nx * X + ny * Y + nz * Z, uu = (ux * X + uy * Y + uz * Z - R.u0) / px, vv = (R.v0 - (vx * X + vy * Y + vz * Z)) / px;
            if (d < dmn) dmn = d; if (d > dmx) dmx = d; if (uu < xmn) xmn = uu; if (uu > xmx) xmx = uu; if (vv < ymn) ymn = vv; if (vv > ymx) ymx = vv;
          }
          if (dmx <= smin || dmn > smax || xmx < 0 || xmn > W || ymx < 0 || ymn > H) continue;
          keep.push(st); tot += g.vStart[st + 1] - g.vStart[st];
        }
        if (VX.length < tot) { VX = new Float32Array(tot); VY = new Float32Array(tot); VD = new Float32Array(tot); }
        if (!vOff || vOff.length < g.n) { vOff = new Int32Array(g.n); sdmin = new Float32Array(g.n); sdmax = new Float32Array(g.n); }
        var o = 0, pos = g.pos;
        for (i = 0; i < keep.length; i++) {
          var st2 = keep[i], a = g.vStart[st2], b = g.vStart[st2 + 1], lo = 1e30, hi = -1e30;
          vOff[st2] = o;
          for (k = a; k < b; k++, o++) {
            var X2 = pos[3 * k] - Ox, Y2 = pos[3 * k + 1] - Oy, Z2 = pos[3 * k + 2] - Oz;
            var dd = nx * X2 + ny * Y2 + nz * Z2;
            VD[o] = dd; VX[o] = (ux * X2 + uy * Y2 + uz * Z2 - R.u0) / px; VY[o] = (R.v0 - (vx * X2 + vy * Y2 + vz * Z2)) / px;
            if (dd < lo) lo = dd; if (dd > hi) hi = dd;
          }
          sdmin[st2] = lo; sdmax[st2] = hi; cand.push(st2);
        }
      }
      var lab = new Uint8Array(N); lab.fill(255);
      var sid = R.wantSid ? new Uint16Array(N) : null; if (sid) sid.fill(65535);
      if (M.length < N) M = new Uint8Array(N);
      M.fill(0, 0, N);                                                       // M stays clean between structures: only the bounding box of what was painted is cleared again
      var body = new Uint8Array(N), ids = R.ids, nSeg = 0, nCand = 0, badSt = [];
      /* skin: union of all skin structures' segments -> one even-odd fill + outline */
      var sk = 0, skSegs = null;
      for (i = 0; i < cand.length; i++) {
        var q = cand[i];
        if (!g.skin[q]) continue;
        if (s < sdmin[q] || s >= sdmax[q]) continue;
        var ns = collect(q, s); if (!ns) continue;
        if (!skSegs) skSegs = [];
        skSegs.push(segs.slice(0, ns * 4)); sk += ns;
      }
      if (sk) {
        if (segs.length < sk * 4) segs = new Float32Array(sk * 4);
        var off = 0;
        for (i = 0; i < skSegs.length; i++) { segs.set(skSegs[i], off); off += skSegs[i].length; }
        fillMask(sk, W, H, M);
        for (k = 0; k < N; k++) body[k] = M[k];
        clearBox(W);
        drawOutline(sk, W, H, body);
      }
      /* the other structures in paint order (sheets are drawn after the solids) */
      for (i = 0; i < cand.length; i++) {
        var st3 = cand[i];
        if (g.skin[st3] || (g.render && g.render[st3] === 1)) continue;
        if (s < sdmin[st3] || s >= sdmax[st3]) continue;
        var n3 = collect(st3, s); if (!n3) continue;
        nCand++; nSeg += n3;
        var pb0 = parityBad;
        fillMask(n3, W, H, M);
        if (parityBad > pb0) badSt.push([st3, parityBad - pb0]);
        if (bx1 < bx0) continue;
        var cls = g.cls[st3], kd = g.kind[st3];
        if (kd === 0 || kd === 5) {
          for (j = by0; j <= by1; j++) {
            var rb = j * W;
            for (k = bx0; k <= bx1; k++) if (M[rb + k]) { lab[rb + k] = cls; if (sid) sid[rb + k] = st3; }
          }
        } else boneFill(st3, kd, R, lab, sid, W, H, px, s);
        clearBox(W);
      }
      for (i = 0; i < cand.length; i++) {                                   // thin sheets (fascia, septa, capsules, dura): a one-pixel line, never a filled volume
        var st4 = cand[i];
        if (!g.render || g.render[st4] !== 1 || g.skin[st4]) continue;
        if (s < sdmin[st4] || s >= sdmax[st4]) continue;
        var n4 = collect(st4, s); if (!n4) continue;
        nCand++; nSeg += n4;
        drawLabel(n4, W, H, lab, sid, g.cls[st4], st4, ss);
      }
      /* body = skin fill + outline + everything painted; exterior = flood from the border over the rest */
      for (k = 0; k < N; k++) if (lab[k] !== 255) body[k] = 1;
      var ext = new Uint8Array(N), stack = new Int32Array(N), sp2 = 0;
      for (i = 0; i < W; i++) { if (!body[i]) { ext[i] = 1; stack[sp2++] = i; } var bi = (H - 1) * W + i; if (!R.extTop && !body[bi] && !ext[bi]) { ext[bi] = 1; stack[sp2++] = bi; } }
      if (!R.extTop) for (j = 1; j < H - 1; j++) { var l0 = j * W, r0 = j * W + W - 1; if (!body[l0] && !ext[l0]) { ext[l0] = 1; stack[sp2++] = l0; } if (!body[r0] && !ext[r0]) { ext[r0] = 1; stack[sp2++] = r0; } }   // Q246 R.extTop (ultrasound window: the image top is the outside): only the top edge seeds the exterior, the body that runs out of the window at the sides / bottom is not mistaken for air
      while (sp2) {
        var p = stack[--sp2], xx = p % W, yy = (p - xx) / W, nb;
        if (xx > 0) { nb = p - 1; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
        if (xx < W - 1) { nb = p + 1; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
        if (yy > 0) { nb = p - W; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
        if (yy < H - 1) { nb = p + W; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
      }
      var holes = ss * ss * (R.holeMax == null ? 1.5 : R.holeMax) > 0 ? fillHoles(lab, sid, ext, W, H, Math.floor(ss * ss * (R.holeMax == null ? 1.5 : R.holeMax)), stack) / (ss * ss) : 0;
      for (k = 0; k < N; k++) if (lab[k] === 255) lab[k] = ext[k] ? ids.air : ids.fat;
      var bodyPx = 0;
      if (R.skinMm > 0 && sk) {                                             // thin skin rim = body pixels within skinMm of the exterior
        var D = DTb.length >= N ? DTb : (DTb = new Uint16Array(N));
        for (k = 0; k < N; k++) D[k] = ext[k] ? 0 : 65000;
        chamfer(D, W, H);
        var thr = Math.max(R.skinMm, px) / px * 3;
        for (k = 0; k < N; k++) if (!ext[k]) { bodyPx++; if (D[k] <= thr) { lab[k] = ids.skin; if (sid) sid[k] = 65534; } }
      }
      var out = {lab: lab, sid: sid, ms: 0, nCand: nCand, nSeg: nSeg, tris: triCount, parityBad: parityBad, repairedRows: repaired, holesFilled: holes, bodyPx: bodyPx / (ss * ss), badSt: badSt, ss: ss};
      if (ss > 1) {                                                          // centre samples as the pixel-resolution label / structure images; `fine` carries the coverage
        var labC = new Uint8Array(Wc * Hc), sidC = sid ? new Uint16Array(Wc * Hc) : null, c0 = ss >> 1, y, x;
        for (y = 0; y < Hc; y++) for (x = 0; x < Wc; x++) { var fi = (y * ss + c0) * W + x * ss + c0; labC[y * Wc + x] = lab[fi]; if (sidC) sidC[y * Wc + x] = sid[fi]; }
        out.fine = lab; out.lab = labC; out.sid = sidC;
      }
      out.ms = Date.now() - t0;
      return out;
    }
    /* Q246: small enclosed uncovered pixels inside the body (a crack where two shells do not meet, the hole of an open seam) take the class that surrounds them most (4-neighbour contacts);
       components larger than maxPx sub-pixels, and ones touching the exterior, stay as the documented baseline (fat).  Returns the number of sub-pixels filled. */
    var tally = new Int32Array(256);
    function fillHoles(lab, sid, ext, W, H, maxPx, stack) {
      var filled = 0, N = W * H, p, q, top, cnt, best, bc, c, touched = [], comp = [], k, nb, xx, yy, seen = new Uint8Array(N);
      for (p = 0; p < N; p++) {
        if (lab[p] !== 255 || ext[p] || seen[p]) continue;
        top = 0; stack[top++] = p; seen[p] = 1; comp.length = 0; touched.length = 0; cnt = 0;
        while (top) {
          q = stack[--top]; cnt++; if (cnt <= maxPx) comp.push(q);
          xx = q % W; yy = (q - xx) / W;
          for (k = 0; k < 4; k++) {
            if (k === 0) { if (xx === 0) continue; nb = q - 1; } else if (k === 1) { if (xx === W - 1) continue; nb = q + 1; } else if (k === 2) { if (yy === 0) continue; nb = q - W; } else { if (yy === H - 1) continue; nb = q + W; }
            c = lab[nb];
            if (c === 255) { if (!ext[nb] && !seen[nb]) { seen[nb] = 1; stack[top++] = nb; } else if (ext[nb]) cnt = 1e9; }
            else { if (!tally[c]) touched.push(c); tally[c]++; }
          }
        }
        if (cnt <= maxPx) {
          best = -1; bc = 0; for (k = 0; k < touched.length; k++) if (tally[touched[k]] > bc) { bc = tally[touched[k]]; best = touched[k]; }
          if (best >= 0) { for (k = 0; k < comp.length; k++) { lab[comp[k]] = best; } filled += comp.length; }
        }
        for (k = 0; k < touched.length; k++) tally[touched[k]] = 0;
      }
      return filled;
    }

    function boneFill(st, kd, R, lab, sid, W, H, px, s) {
      var P = R.bone[kd], ids = R.ids;
      var rw = bx1 - bx0 + 3, rh = by1 - by0 + 3, D = new Float32Array(rw * rh), x, y;
      for (y = 0; y < rh; y++) {
        var sy = Math.min(H - 1, Math.max(0, by0 - 1 + y));
        for (x = 0; x < rw; x++) {
          var sx = Math.min(W - 1, Math.max(0, bx0 - 1 + x));
          D[y * rw + x] = M[sy * W + sx] ? 1e9 : 0;
        }
      }
      edt(D, rw, rh);
      var rmax = 0;
      for (y = 1; y < rh - 1; y++) for (x = 1; x < rw - 1; x++) { var dv = D[y * rw + x]; if (dv > rmax && dv < 1e8) rmax = dv; }
      var Rmm = (Math.sqrt(rmax) - 0.5) * px, tmaxEff = Math.min(P.tmax, Math.max(P.tthin, P.frac * Rmm));
      var ax = 0, ay = 0, az = 0, cxm = 0, len = 1, haveAx = P.axial && axisInfo[st * 7 + 6] > 0, a0 = 0, au = 0, av = 0, an = 0;
      if (haveAx) {
        var ai = st * 7; cxm = axisInfo[ai]; var cym = axisInfo[ai + 1], czm = axisInfo[ai + 2]; ax = axisInfo[ai + 3]; ay = axisInfo[ai + 4]; az = axisInfo[ai + 5]; len = axisInfo[ai + 6];
        a0 = ax * (R.O[0] - cxm) + ay * (R.O[1] - cym) + az * (R.O[2] - czm) + (ax * R.n[0] + ay * R.n[1] + az * R.n[2]) * s;
        au = ax * R.u[0] + ay * R.u[1] + az * R.u[2]; av = ax * R.v[0] + ay * R.v[1] + az * R.v[2];
      }
      for (y = by0; y <= by1; y++) {
        for (x = bx0; x <= bx1; x++) {
          var p = y * W + x;
          if (!M[p]) continue;
          var d = D[(y - by0 + 1) * rw + (x - bx0 + 1)], dmm = (Math.sqrt(d) - 0.5) * px, w = 0;   // distance from the pixel centre to the mesh edge
          if (haveAx) {
            var z = (a0 + au * (R.u0 + (x + 0.5) * px) + av * (R.v0 - (y + 0.5) * px)) / len + 0.5;
            if (z >= P.z0 && z <= P.z1) w = 1; else if (z < P.z0) w = Math.max(0, 1 - (P.z0 - z) / P.ramp); else w = Math.max(0, 1 - (z - P.z1) / P.ramp);
          }
          var tc = P.tthin + w * (tmaxEff - P.tthin); if (tc < P.tthin) tc = P.tthin;
          var c;
          if (dmm <= Math.max(tc, 0.5 * px)) c = ids.cort; else if (P.canal && w > 0 && dmm > tc + (1 - w) * Rmm) c = ids.marrow; else c = ids.canc;   // Q246: the canal grows continuously over the ramp (radius ~ w) instead of switching on at w = 0.5
          lab[p] = c; if (sid) sid[p] = st;
        }
      }
    }
    return {setGeometry: setGeometry, slice: slice};
  }

  /* ========================================================================================================
   * 2. PURE HELPERS
   * ====================================================================================================== */
  function compileTable(T) {
    var by = {}, i;
    T.classes.forEach(function (c, ix) { c._i = ix; by[c.key] = c; });
    var rules = T.mapping_rules.rules.map(function (r, ix) {
      if (!by[r.cls]) throw new Error("mapping rule " + ix + ": unknown class " + r.cls);
      return {cat: r.cat || null, re: r.re ? new RegExp(r.re, "i") : null, vt: r.vt || null, cls: by[r.cls]._i, kind: r.kind || null, render: r.render || null, why: r.why, ix: ix};
    });
    var fb = by[T.mapping_rules.fallback.cls]._i;
    var kinds = {};
    Object.keys(T.bone_model.kinds).forEach(function (k) { kinds[k] = T.bone_model.kinds[k]; });
    return {T: T, by: by, rules: rules, fallback: fb, kinds: kinds, ids: {air: by.air._i, fat: by.fat._i, skin: by.skin._i, cort: by.bone_cortical._i, canc: by.bone_cancellous._i, marrow: by.marrow_yellow._i}};
  }
  function classify(C, rec) {
    var text = (String(rec.id || "") + " " + String(rec.name || "")).toLowerCase().replace(/_/g, " ");
    for (var i = 0; i < C.rules.length; i++) {
      var r = C.rules[i];
      if (r.cat && r.cat.indexOf(rec.cat) < 0) continue;
      if (r.vt && rec.vt !== r.vt) continue;
      if (r.re && !r.re.test(text)) continue;
      return {cls: r.cls, kind: r.kind, render: r.render, rule: r.ix, why: r.why};
    }
    return {cls: C.fallback, kind: null, render: null, rule: -1, why: C.T.mapping_rules.fallback.why};
  }
  function poolSignal(pool, cls, q, P, T) {
    var t1 = pool.t1, t2 = pool.t2, t2s = pool.t2s;
    if (P.gd && cls.mri.t1_gd) t1 = cls.mri.t1_gd;
    var f;
    if (P.kind === "se") f = (1 - Math.exp(-P.tr / t1)) * Math.exp(-P.te / t2);
    else if (P.kind === "ir") f = Math.abs(1 - 2 * Math.exp(-P.ti / t1) + Math.exp(-P.tr / t1)) * Math.exp(-P.te / t2);
    else { var a = P.fa * Math.PI / 180, E1 = Math.exp(-P.tr / t1); f = Math.sin(a) * (1 - E1) / (1 - E1 * Math.cos(a)) * Math.exp(-P.te / t2s); }
    var v = pool.frac * pool.pd * f;
    if (P.fatsat && pool.fat) v *= T.mr_global.fat_suppression_residual;
    return v;
  }
  /* per-class relative signal for sequence parameters P ({kind,tr,te,ti,fa,fatsat,gd,flow}); returns Float32Array(256) + norm */
  function mrTable(C, P) {
    var T = C.T, out = new Float32Array(256), mx = 1e-9, i;
    for (i = 0; i < T.classes.length; i++) {
      var cls = T.classes[i], s = 0;
      for (var q = 0; q < cls.mri.pools.length; q++) s += poolSignal(cls.mri.pools[q], cls, q, P, T);
      if (cls.flow) {
        if (P.flow === "void") s *= Math.max(0, 1 - cls.flow * T.mr_global.flow_void_gain);
        else if (P.flow === "inflow") s *= 1 + T.mr_global.inflow_gain * cls.flow;
      }
      out[i] = s;
      if (!cls.norm_exclude && cls.mri.pools[0].pd > 0.3 && !cls.flow && s > mx) mx = s;
    }
    for (i = 0; i < out.length; i++) out[i] = out[i] / mx;
    return {sig: out, norm: mx};
  }
  function ctTable(C) {
    var out = new Float32Array(256).fill(-1000);
    C.T.classes.forEach(function (c, i) { out[i] = c.ct.hu; });
    return out;
  }
  function basis(nrm) {                                                     // image normal pointing at the viewer + radiological axes
    var n = nrm.slice(), l = Math.hypot(n[0], n[1], n[2]) || 1, ax = [Math.abs(n[0]), Math.abs(n[1]), Math.abs(n[2])];
    n = [n[0] / l, n[1] / l, n[2] / l];
    var dom = ax[1] >= ax[0] && ax[1] >= ax[2] ? 1 : (ax[2] >= ax[0] ? 2 : 0), canon = [[-1, 0, 0], [0, -1, 0], [0, 0, 1]][dom];
    if (n[0] * canon[0] + n[1] * canon[1] + n[2] * canon[2] < 0) n = [-n[0], -n[1], -n[2]];
    var v0 = Math.abs(n[1]) > 0.7 ? [0, 0, 1] : [0, 1, 0], d = v0[0] * n[0] + v0[1] * n[1] + v0[2] * n[2];
    var v = [v0[0] - d * n[0], v0[1] - d * n[1], v0[2] - d * n[2]], vl = Math.hypot(v[0], v[1], v[2]); v = [v[0] / vl, v[1] / vl, v[2] / vl];
    var u = [n[1] * v[2] - n[2] * v[1], n[2] * v[0] - n[0] * v[2], n[0] * v[1] - n[1] * v[0]];
    return {n: n, u: u, v: v};
  }
  function dirLabel(d) {                                                    // atlas +X right, +Y superior, +Z anterior
    var parts = [[d[0], "R", "L"], [d[1], "S", "I"], [d[2], "A", "P"]].filter(function (p) { return Math.abs(p[0]) > 0.3; })
      .sort(function (a, b) { return Math.abs(b[0]) - Math.abs(a[0]); }).map(function (p) { return p[0] > 0 ? p[1] : p[2]; });
    return parts.join("") || "?";
  }

  /* ---- Q246: label stacks -> value images (area-weighted partial volume, slab combination, 3-D coherent noise and coil bias) ---------------------------------------------
   * A view = a stack of sub-slice label images (the slab) at ss x ss samples per pixel.  The value of a pixel is the AREA-weighted mean of the class values of its ss x ss samples
   * (partial volume: a boundary pixel is a mix of both tissues, a thin structure a faint line, and an edge moves continuously with the plane); a slab then averages the sub-slices
   * (midpoint rule, so thickness and plane position change the image continuously) or takes the max / min of their area-weighted values (MIP / MinIP). */
  var DEFAULTS = {ssFinal: 3, ssBudget: 64, noiseCorrCT: 1.2, noiseCorrMR: 1.5, biasWavelengthMm: 650, seed: 20246};
  function chooseSS(nSub, tier, cap) {                                      // quality tier 0 (while the plane is dragged) = 1; the full pass spends a fixed budget of ss^2 x sub-slices
    if (tier === 0) return 1;
    var m = Math.floor(Math.sqrt(DEFAULTS.ssBudget / Math.max(1, nSub))); return Math.max(1, Math.min(cap || DEFAULTS.ssFinal, m));
  }
  function slabOffsets(lo, hi, th, maxN) {                                  // midpoint rule: n cells of thickness th/n <= 1 mm (capped), one sample at the centre of each
    if (!(th > 0.01)) return [(lo + hi) / 2];
    var n = Math.max(1, Math.min(maxN || 25, Math.ceil(th / 1.0))), out = [], k;
    for (k = 0; k < n; k++) out.push(lo + (hi - lo) * (k + 0.5) / n);
    return out;
  }
  function areaValues(lab, fine, ss, W, H, lut, dst, acc) {                  // dst[k] (+)= area-weighted mean of lut over the ss x ss samples of pixel k
    var N = W * H, x, y, a, b, k;
    if (!fine || ss <= 1) { var L0 = fine || lab; if (acc) for (k = 0; k < N; k++) dst[k] += lut[L0[k]]; else for (k = 0; k < N; k++) dst[k] = lut[L0[k]]; return; }
    var Wf = W * ss, inv = 1 / (ss * ss);
    for (y = 0; y < H; y++) for (x = 0; x < W; x++) {
      var sum = 0, o = y * ss * Wf + x * ss;
      for (b = 0; b < ss; b++, o += Wf) for (a = 0; a < ss; a++) sum += lut[fine[o + a]];
      if (acc) dst[y * W + x] += sum * inv; else dst[y * W + x] = sum * inv;
    }
  }
  function combineSlab(res, lut, slab, thick) {                              // res: {W, H, ss, labels[], fine[]|null, mid}
    var W = res.W, H = res.H, N = W * H, nS = res.labels.length, out = new Float32Array(N), ss = res.ss || 1, s, k, tmp;
    if (nS === 1 || thick <= 0.01) { var m = Math.min(res.mid || 0, nS - 1); areaValues(res.labels[m], res.fine && res.fine[m], ss, W, H, lut, out, false); return out; }
    if (slab === "avg") { for (s = 0; s < nS; s++) areaValues(res.labels[s], res.fine && res.fine[s], ss, W, H, lut, out, true); var inv = 1 / nS; for (k = 0; k < N; k++) out[k] *= inv; return out; }
    tmp = new Float32Array(N);
    if (slab === "mip") out.fill(-1e9); else out.fill(1e9);
    for (s = 0; s < nS; s++) {
      areaValues(res.labels[s], res.fine && res.fine[s], ss, W, H, lut, tmp, false);
      if (slab === "mip") { for (k = 0; k < N; k++) if (tmp[k] > out[k]) out[k] = tmp[k]; } else { for (k = 0; k < N; k++) if (tmp[k] < out[k]) out[k] = tmp[k]; }
    }
    return out;
  }
  function gaussBlur(a, W, H, sg) {
    var r = Math.max(1, Math.ceil(sg * 3)), ker = new Float32Array(2 * r + 1), s = 0, i, x, y;
    for (i = -r; i <= r; i++) { ker[i + r] = Math.exp(-i * i / (2 * sg * sg)); s += ker[i + r]; }
    for (i = 0; i < ker.length; i++) ker[i] /= s;
    var tmp = new Float32Array(a.length), out = new Float32Array(a.length);
    for (y = 0; y < H; y++) for (x = 0; x < W; x++) { var acc = 0; for (i = -r; i <= r; i++) { var xx = Math.min(W - 1, Math.max(0, x + i)); acc += a[y * W + xx] * ker[i + r]; } tmp[y * W + x] = acc; }
    for (y = 0; y < H; y++) for (x = 0; x < W; x++) { var ac = 0; for (i = -r; i <= r; i++) { var yy = Math.min(H - 1, Math.max(0, y + i)); ac += tmp[yy * W + x] * ker[i + r]; } out[y * W + x] = ac; }
    return out;
  }
  /* seeded lattice noise in ATLAS (world) coordinates: the value at a point of the body does not depend on the plane that is cut through it, so a moving, tilted or zoomed plane sees the
     same noise pattern attached to the tissue (a pan shifts it, a 1 mm step changes it only as far as the lattice cell does).  Unit variance at every position. */
  function hash3(a, b, c, sd) {
    var h = Math.imul(a | 0, 0x27d4eb2d) ^ Math.imul(b | 0, 0x165667b1) ^ Math.imul(c | 0, 0x85ebca6b) ^ Math.imul(sd | 0, 0xc2b2ae35);
    h ^= h >>> 15; h = Math.imul(h, 0x2c1b3c6d); h ^= h >>> 12; h = Math.imul(h, 0x297a2d39); h ^= h >>> 15;
    return h >>> 0;
  }
  function g4(h) { return (((h & 255) + ((h >>> 8) & 255) + ((h >>> 16) & 255) + (h >>> 24)) - 510) * 0.006766; }          // ~ N(0,1)
  function gnoise(x, y, z, sd) {
    var ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z), fx = x - ix, fy = y - iy, fz = z - iz;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
    var wx0 = 1 - fx, wy0 = 1 - fy, wz0 = 1 - fz, acc = 0, a, b, c;
    for (c = 0; c < 2; c++) for (b = 0; b < 2; b++) for (a = 0; a < 2; a++) acc += (a ? fx : wx0) * (b ? fy : wy0) * (c ? fz : wz0) * g4(hash3(ix + a, iy + b, iz + c, sd));
    return acc / Math.sqrt((wx0 * wx0 + fx * fx) * (wy0 * wy0 + fy * fy) * (wz0 * wz0 + fz * fz));
  }
  /* smooth multiplicative receive-coil sensitivity of an MRI (1 + A F, F a sum of three low-order plane waves of wavelength ~ 0.5-1 m, |F| <= 1): continuous in 3-D by construction */
  var BIAS_WAVES = [[0.6, 0.55, 0.3, 0.5, 0.9, 0.0], [0.3, -0.5, 0.7, 0.45, 2.1, 1.3], [0.1, 0.3, -0.6, 0.8, 4.0, 2.2]];
  function biasField(X, Y, Z, amp, wl) {
    var f = 0, i, k = 2 * Math.PI / (wl || DEFAULTS.biasWavelengthMm);
    for (i = 0; i < 3; i++) { var w = BIAS_WAVES[i], q = Math.hypot(w[0], w[1], w[2]); f += w[3] * Math.sin(k * (w[0] * X + w[1] * Y + w[2] * Z) / q * (1 + 0.35 * i) + w[4]); }
    return 1 + amp * f / 1.8;
  }
  /* res + view geometry -> final Float32 values.  o: {modality, slab, thick, blur (mm), noise (CT: HU; MR: % of the reference signal), bias (MR: fraction), seed, px, plane:{O,u,v,n,u0,v0}, offs[], mid} */
  function renderValues(res, lut, o) {
    var W = res.W, H = res.H, N = W * H, mr = o.modality !== "ct", val = combineSlab(res, lut, o.slab || "avg", o.thick || 0), k, x, y, px = o.px || res.px, pl = o.plane || res.plane;
    if (o.blur > 0) val = gaussBlur(val, W, H, o.blur / px);
    var useN = o.noise > 0, useB = mr && o.bias > 0;
    if (!(useN || useB) || !pl) return val;
    var offs = o.offs || res.offs || [0], sm = offs.length ? (offs[0] + offs[offs.length - 1]) / 2 : 0, th = Math.max(o.thick || 0, 0), sd = (o.seed | 0) || DEFAULTS.seed;
    var corr = mr ? DEFAULTS.noiseCorrMR : DEFAULTS.noiseCorrCT, inv = 1 / corr, sg = mr ? o.noise / 100 : o.noise;
    if (o.slab === "avg" && th > corr) sg /= Math.sqrt(th / corr);          // an average over a slab of several correlation cells has proportionally less noise
    var Ox = pl.O[0] + pl.n[0] * sm, Oy = pl.O[1] + pl.n[1] * sm, Oz = pl.O[2] + pl.n[2] * sm;
    for (y = 0; y < H; y++) {
      var vv = pl.v0 - (y + 0.5) * px;
      for (x = 0; x < W; x++) {
        var uu = pl.u0 + (x + 0.5) * px, X = Ox + pl.u[0] * uu + pl.v[0] * vv, Y = Oy + pl.u[1] * uu + pl.v[1] * vv, Z = Oz + pl.u[2] * uu + pl.v[2] * vv, i = y * W + x;
        if (useB) val[i] *= biasField(X, Y, Z, o.bias);
        if (useN) {
          if (!mr) val[i] += sg * gnoise(X * inv, Y * inv, Z * inv, sd);
          else { var n1 = sg * gnoise(X * inv, Y * inv, Z * inv, sd), n2 = sg * gnoise(X * inv, Y * inv, Z * inv, sd + 7919), a = val[i] + n1; val[i] = Math.sqrt(a * a + n2 * n2); }
        }
      }
    }
    return val;
  }

  /* ---- node test hook (also exported in the browser since Q228: companions such as the ultrasound add-on reuse the kernel and the mapping) ---- */
  var LIB = {KERNEL_FACTORY: KERNEL_FACTORY, compileTable: compileTable, classify: classify, mrTable: mrTable, ctTable: ctTable, basis: basis, dirLabel: dirLabel, VERSION: VERSION,
    DEFAULTS: DEFAULTS, chooseSS: chooseSS, slabOffsets: slabOffsets, areaValues: areaValues, combineSlab: combineSlab, gaussBlur: gaussBlur, gnoise: gnoise, hash3: hash3, biasField: biasField, renderValues: renderValues};
  G.NMSKImagingLib = LIB;
  if (typeof document === "undefined") return;

  /* ========================================================================================================
   * 3 + 4 + 5. ENGINE, UI, ATTACH (browser only)
   * ====================================================================================================== */
  var SCRIPT_BASE = (function () {
    try { var cs = document.currentScript; if (cs && cs.src) return cs.src.replace(/[^\/]*$/, ""); } catch (e) {}
    return "";
  })();
  /* Q239: where this code came from ("inline" = pasted into the page by scripts/clinical/stage_clinical_files.py, "file" = clinical_imaging_tool.js beside it) */
  var CODE_SRC = (function () { try { var cs = document.currentScript; return cs && cs.src ? "file" : "inline"; } catch (e) { return "inline"; } })();
  var DIAG = G.NMSKClinicalDiag = G.NMSKClinicalDiag || {};          // {imaging: {ok, text}, ultrasound: {ok, text}} for support / tests
  function inlineText(id) { try { var e = document.getElementById(id); return e ? e.textContent : null; } catch (e2) { return null; } }
  /* text of a sibling file, robust against hosting differences: fetch, then XMLHttpRequest, for the script-relative URL and the document-relative one;
     rejects with ONE message that names every attempt (HTTP status, network error, "host answered with a page") */
  function fetchText(name) {
    var urls = [SCRIPT_BASE + name]; if (urls.indexOf(name) < 0) urls.push(name);
    var why = [];
    function xhr(u) {
      return new Promise(function (res, rej) {
        try {
          var x = new XMLHttpRequest(); x.open("GET", u);
          x.onload = function () { if (x.status >= 200 && x.status < 300 && x.responseText) res(x.responseText); else rej(new Error("xhr HTTP " + x.status)); };
          x.onerror = function () { rej(new Error("xhr network error")); };
          x.send();
        } catch (e) { rej(e); }
      });
    }
    function one(i) {
      if (i >= urls.length) return Promise.reject(new Error(name + " not loadable (" + why.join("; ") + ")"));
      var u = urls[i], f;
      try { f = fetch(u, {cache: "no-cache"}).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.text(); }); } catch (e) { f = Promise.reject(e); }
      return f.catch(function (e) { why.push("fetch " + (e && e.message || e)); return xhr(u); })
        .catch(function (e) { why.push(String(e && e.message || e)); return one(i + 1); });
    }
    return one(0);
  }
  function fetchJson(name) {
    return fetchText(name).then(function (t) {
      if (/^\s*</.test(t)) throw new Error(name + ": the host answered with a web page instead of the file");
      try { return JSON.parse(t); } catch (e) { throw new Error(name + ": not valid JSON (" + e.message + ")"); }
    });
  }
  /* a one-line notice that fades by itself (role=status), used for the first-use hints and "tool not available" answers */
  function toast(msg, ms) {
    try {
      var t = document.getElementById("nmsk-clinical-toast");
      if (!t) {
        t = document.createElement("div"); t.id = "nmsk-clinical-toast"; t.setAttribute("role", "status");
        t.style.cssText = "position:fixed;left:50%;bottom:72px;transform:translateX(-50%);max-width:min(560px,92vw);z-index:200;background:#161d27;color:#e6edf5;border:1px solid #6cb4ff;border-radius:10px;padding:9px 14px;font:13px/1.4 system-ui,sans-serif;box-shadow:0 6px 24px rgba(0,0,0,.45);display:none";
        document.body.appendChild(t);
      }
      t.textContent = msg; t.style.display = "block"; clearTimeout(t._h); t._h = setTimeout(function () { t.style.display = "none"; }, ms || 9000);
    } catch (e) {}
  }
  /* the toolbar of the page; when a page has none (or it is clipped / hidden on a small screen) the buttons live in a small floating bar instead */
  function floatBar() {
    var b = document.getElementById("nmsk-clinical-bar");
    if (!b) { b = document.createElement("div"); b.id = "nmsk-clinical-bar"; b.style.cssText = "position:fixed;top:8px;right:8px;z-index:70;display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end"; document.body.appendChild(b); }
    return b;
  }
  function visibleOnScreen(el) {
    if (!el || !el.isConnected) return false;
    var r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || r.width < 8 || r.height < 8) return false;
    var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    return cx > 0 && cy > 0 && cx < window.innerWidth && cy < window.innerHeight;
  }
  function rescueButtons() {                                         // a button that cannot be seen is moved to the floating bar
    ["t-imaging", "t-ultrasound"].forEach(function (id) {
      var b = document.getElementById(id);
      if (b && !visibleOnScreen(b) && !(document.body.classList.contains("nmsk-img") || document.body.classList.contains("nmsk-us"))) floatBar().appendChild(b);
    });
  }
  function setBtnTip(btn, base, ok, text) {
    if (!btn) return;
    btn.title = base + " | " + text; btn.setAttribute("data-diag", ok ? "ok" : "bad");
    btn.style.opacity = ok === false ? "0.7" : "";
  }

  function attachImaging(api) {
    var C = null, T = null, tableErr = null, tableSrc = "", geoErr = "", shared = null;
    var geo = null, geoState = "idle", kernelLocal = null, worker = null, workerOk = true, jobCb = null, msgSeq = 0;
    var perf = {last: null, history: []};
    var S = {
      open: false, modality: "ct", ctWin: "soft", ctW: 400, ctL: 40, seq: "t1_se", sp: null, mrW: 1, mrL: 0.5, auto: true,
      thick: 5, slab: "avg", layout: "mpr", active: "cut", fov: {cut: 450, ax: 450, co: 700, sa: 700}, res: 320,
      P: null, noise: 0, blur: 0, bias: 0, ssCap: 0, cross: true, labels: true, tab: "image", lay: "auto", link: false,
      obl: {base: "ax", tilt: 0, dir: 0},                                     // Q254: oblique Cut-plane dial (item 6)
      cine: false, fps: 3                                                     // Q254: slice-position cine (item 7)
    };
    var views = {};
    var VIEWS = [["cut", "Cut plane"], ["ax", "Axial"], ["co", "Coronal"], ["sa", "Sagittal"]];
    var root = null, ui = {}, polling = null, lastPlaneKey = "", timers = {}, lastMark = 0, tablePromise = null;
    var lastCut = null, lastSlab = 0;

    /* ---------- table ---------- */
    function loadTable() {
      var inl = inlineText("nmsk-imaging-tissues"), p = null;                 // Q239: the table pasted into the page first, the sibling file only as a fallback
      if (inl) { try { var tj = JSON.parse(inl); tableSrc = "inline"; p = Promise.resolve(tj); } catch (e) { p = null; } }
      if (!p) { tableSrc = "file"; p = fetchJson("clinical_imaging_tissues.json"); }
      return p.then(function (t) { T = t; C = compileTable(t); S.sp = JSON.parse(JSON.stringify(t.mr_sequences.filter(function (q) { return q.key === S.seq; })[0])); })
        .catch(function (e) { tableErr = String(e && e.message || e); })
        .then(function () { setDiag(); });
    }

    /* ---------- geometry package ---------- */
    function buildGeometry(progress) {
      return new Promise(function (resolve, reject) {
        if (geo) return resolve(geo);
        var recs = api.list(), n = recs.length, i = 0, nv = 0, nt = 0, geoms = new Array(n), none = 0, tm = {t0: Date.now()};
        function chunk() {
          var t0 = Date.now();
          while (i < n && Date.now() - t0 < 40) {
            var g = null; try { g = api.geometry(i); } catch (e) { g = null; }
            if (!g || !g.pos || !g.idx) { none++; geoms[i] = null; } else { geoms[i] = g; nv += g.pos.length / 3; nt += g.idx.length / 3; }
            i++;
          }
          if (progress) progress("Reading geometry " + i + " / " + n);
          if (i < n) return setTimeout(chunk, 0);
          if (none === n) return reject(new Error("this page does not expose its geometry to add-ons (no clinical hook data)"));
          tm.read = Date.now() - tm.t0; pack();
        }
        function pack() {
          var pos = new Float32Array(nv * 3), idx = new Uint32Array(nt * 3), vStart = new Uint32Array(n + 1), tStart = new Uint32Array(n + 1);
          var bbox = new Float32Array(n * 6), cls = new Uint8Array(n), kind = new Uint8Array(n), skin = new Uint8Array(n), render = new Uint8Array(n), names = new Array(n);
          var vo = 0, to = 0, k, order = [], skinList = [], kindIds = {};
          Object.keys(C.kinds).forEach(function (kk) { kindIds[kk] = C.kinds[kk].id; });
          for (k = 0; k < n; k++) {
            var g = geoms[k], rec = recs[k], cl = classify(C, rec);
            vStart[k] = vo; tStart[k] = to; cls[k] = cl.cls; kind[k] = cl.kind ? kindIds[cl.kind] : 0; render[k] = cl.render === "sheet" ? 1 : 0; names[k] = rec.name || rec.id;
            if (g) {
              var p = g.pos, ix = g.idx, nvk = p.length / 3, ntk = ix.length / 3, mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30], q;
              pos.set(p, vo * 3);
              for (q = 0; q < p.length; q += 3) { for (var a = 0; a < 3; a++) { var v = p[q + a]; if (v < mn[a]) mn[a] = v; if (v > mx[a]) mx[a] = v; } }
              for (q = 0; q < ix.length; q++) idx[to * 3 + q] = ix[q] + vo;
              bbox.set([mn[0], mn[1], mn[2], mx[0], mx[1], mx[2]], k * 6);
              vo += nvk; to += ntk;
            } else bbox.set([1e9, 1e9, 1e9, 1e9, 1e9, 1e9], k * 6);
            if (C.T.classes[cl.cls].skin_envelope) skin[k] = 1;
          }
          vStart[n] = vo; tStart[n] = to;
          for (k = 0; k < n; k++) { if (!geoms[k]) continue; if (skin[k]) skinList.push(k); else order.push(k); }
          order.sort(function (a, b) { return (C.T.classes[cls[a]].priority - C.T.classes[cls[b]].priority) || (a - b); });
          geo = {n: n, pos: pos, idx: idx, vStart: vStart, tStart: tStart, bbox: bbox, cls: cls, kind: kind, skin: skin, render: render, order: Uint32Array.from(order), skinList: Uint32Array.from(skinList), names: names, recs: recs, nv: nv, nt: nt};
          var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30], src = skinList.length ? skinList : order;
          src.forEach(function (s) { for (var a = 0; a < 3; a++) { lo[a] = Math.min(lo[a], bbox[s * 6 + a]); hi[a] = Math.max(hi[a], bbox[s * 6 + 3 + a]); } });
          geo.bodyBox = {lo: lo, hi: hi};
          geoms = null; tm.pack = Date.now() - tm.t0 - tm.read; geo.timing = tm;
          startKernel(geo).then(function () { tm.worker = Date.now() - tm.t0 - tm.read - tm.pack; resolve(geo); }, reject);
        }
        chunk();
      });
    }
    function startKernel(g) {
      return new Promise(function (resolve) {
        var starting = true;                                                  // Q239: a worker that cannot start (CSP, sandbox) falls back to the main-thread kernel at once, not after 8 s
        var payload = {n: g.n, pos: g.pos, idx: g.idx, vStart: g.vStart, tStart: g.tStart, bbox: g.bbox, cls: g.cls, kind: g.kind, skin: g.skin, render: g.render, order: g.order, skinList: g.skinList};
        function local() {
          workerOk = false; worker = null;
          kernelLocal = KERNEL_FACTORY()
          kernelLocal.setGeometry(payload);
          resolve();
        }
        try {
          var src = "var K=(" + KERNEL_FACTORY.toString() + ")();onmessage=function(e){var m=e.data;if(m.type==='init'){K.setGeometry(m.g);postMessage({type:'ready'});}else if(m.type==='slice'){var r;try{r=K.slice(m.R);}catch(err){postMessage({type:'error',id:m.id,msg:String(err&&err.stack||err)});return;}var tr=[r.lab.buffer];if(r.sid)tr.push(r.sid.buffer);if(r.fine)tr.push(r.fine.buffer);postMessage({type:'slice',id:m.id,r:r},tr);}};";
          var url = URL.createObjectURL(new Blob([src], {type: "application/javascript"}));
          worker = new Worker(url);
          var t = setTimeout(function () { if (!worker) return; try { worker.terminate(); } catch (e) {} local(); }, 8000);
          worker.onmessage = function (e) {
            var m = e.data;
            if (m.type === "ready") { starting = false; clearTimeout(t); resolve(); return; }
            if (jobCb) jobCb(m);
          };
          worker.onerror = function (e) { if (starting) { starting = false; clearTimeout(t); try { worker.terminate(); } catch (e2) {} local(); } else console.error("imaging worker:", e && e.message); };
          worker.postMessage({type: "init", g: payload});                    // copies (structured clone): the page keeps its own arrays
        } catch (e) { local(); }
      });
    }
    var sliceChain = Promise.resolve();
    function runSlice(R) {                                                  // -> Promise(result); serialised (the worker has one job slot; Q228 companions share it)
      var p = sliceChain.then(function () { return runSliceRaw(R); });
      sliceChain = p.then(function () {}, function () {});
      return p;
    }
    function runSliceRaw(R) {
      return new Promise(function (resolve, reject) {
        var id = ++msgSeq;
        if (worker && workerOk) {
          jobCb = function (m) { if (m.id !== id) return; jobCb = null; if (m.type === "error") reject(new Error(m.msg)); else resolve(m.r); };
          worker.postMessage({type: "slice", id: id, R: R});
        } else {
          setTimeout(function () { try { resolve(kernelLocal.slice(R)); } catch (e) { reject(e); } }, 0);
        }
      });
    }

    /* ---------- planes ---------- */
    function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
    function cutPlane() {                                                   // {kn, c} (kept half kn.p + c >= 0) or null
      var c = api.cut(); if (!c) return null;
      var l = Math.hypot(c[0], c[1], c[2]) || 1; return {kn: [c[0] / l, c[1] / l, c[2] / l], c: c[3] / l};
    }
    /* ---------- Q254 item 6: a direct, discoverable oblique-plane dial for the Cut view -----------------------
     * Before this, the only way to get a genuinely oblique CT/MRI plane was the 3-D view's Cut-mode "facing me"
     * button, which snaps the plane to whatever direction the camera happens to be orbited to -- real, but a
     * one-shot trick with no live angle control and nothing telling the user it exists. This dials a tilt
     * (0-60 deg off a chosen base plane) and a direction (0-359 deg, which way the plane tilts) straight onto
     * api.setCut(), the exact mechanism the Cut view already consumes -- same rotation pattern as the ultrasound
     * tool's own Tilt/Direction sliders (clinical/ultrasound_tool.js probeFrame): rotate the base normal by `tilt`
     * about the axis perpendicular to both it and the in-plane direction `dir` picks. */
    var OBL_BASE = {ax: [0, -1, 0], co: [0, 0, 1], sa: [-1, 0, 0]};
    function obliqueNormal(baseKey, tiltDeg, dirDeg) {
      var b = basis(OBL_BASE[baseKey] || OBL_BASE.ax), th = (tiltDeg || 0) * Math.PI / 180, ph = (dirDeg || 0) * Math.PI / 180;
      var ct = Math.cos(ph), st = Math.sin(ph), t = [b.u[0] * ct + b.v[0] * st, b.u[1] * ct + b.v[1] * st, b.u[2] * ct + b.v[2] * st];
      var k = [b.n[1] * t[2] - b.n[2] * t[1], b.n[2] * t[0] - b.n[0] * t[2], b.n[0] * t[1] - b.n[1] * t[0]], kl = Math.hypot(k[0], k[1], k[2]) || 1;
      k = [k[0] / kl, k[1] / kl, k[2] / kl];
      var c = Math.cos(th), s = Math.sin(th), n = b.n, kv = [k[1] * n[2] - k[2] * n[1], k[2] * n[0] - k[0] * n[2], k[0] * n[1] - k[1] * n[0]], kd = (k[0] * n[0] + k[1] * n[1] + k[2] * n[2]) * (1 - c);
      return [n[0] * c + kv[0] * s + k[0] * kd, n[1] * c + kv[1] * s + k[1] * kd, n[2] * c + kv[2] * s + k[2] * kd];
    }
    function applyOblique() {                                                // pushes S.obl onto the live Cut plane; pollCut() (140 ms) picks it up and redraws
      if (!S.P) return;
      try { api.setCut({normal: obliqueNormal(S.obl.base, S.obl.tilt, S.obl.dir), point: S.P}); } catch (e) {}
    }
    /* ---------- Q254 item 7: slice-position cine, with a speed control --------------------------------------
     * Steps S.P along the ACTIVE view's own plane normal (so it plays through whatever is on screen -- axial,
     * coronal, sagittal, or an oblique Cut plane alike), N mm per tick, fps selector modelled directly on the
     * ultrasound tool's own cineBtn / fps <select> (1 / 2 / 3 / 5 / 8), now that Q253 made that shared UI row
     * (ultrasound's ui.playBox). Bounces back and forth at the body's own bounding box rather than wrapping or
     * running off; built on top of item 5's drag fix, not before it, per the brief. */
    var CINE_STEP_MM = 2, cineDir = 1;
    function cineTick() {
      if (!S.open || !geo || !S.P) { setCine(false); return; }
      var spec = viewSpec(S.active);
      if (!spec) return;                                                    // e.g. the Cut view with no cut plane set yet -- just wait, don't stop
      var step = CINE_STEP_MM * cineDir, np = [S.P[0] + spec.n[0] * step, S.P[1] + spec.n[1] * step, S.P[2] + spec.n[2] * step];
      var lo = geo.bodyBox.lo, hi = geo.bodyBox.hi, margin = 15;
      if (np[0] < lo[0] - margin || np[0] > hi[0] + margin || np[1] < lo[1] - margin || np[1] > hi[1] + margin || np[2] < lo[2] - margin || np[2] > hi[2] + margin) { cineDir = -cineDir; return; }
      S.P = np; markDirty(null, true);
    }
    function setCine(on) {
      clearInterval(timers.cine); S.cine = !!on;
      if (S.cine) timers.cine = setInterval(cineTick, 1000 / Math.max(1, S.fps));
      if (ui.cineBtn) ui.cineBtn.setAttribute("aria-pressed", String(S.cine));
    }
    function viewSpec(key) {                                                // plane definition of one view
      var P = S.P, th = S.thick, spec;
      if (key === "cut") {
        var cp = cutPlane(); if (!cp) return null;
        var b = basis(cp.kn), dist = dot(cp.kn, P) + cp.c, O = [P[0] - dist * cp.kn[0], P[1] - dist * cp.kn[1], P[2] - dist * cp.kn[2]];
        var sgn = dot(b.n, cp.kn) >= 0 ? 1 : -1;                          // kept slab = kn.p + c in [0, th]
        spec = {O: O, u: b.u, v: b.v, n: b.n, lo: 0, hi: th * sgn, oneSided: true};
        if (sgn < 0) { spec.lo = -th; spec.hi = 0; }
      } else {
        var nn = key === "ax" ? [0, -1, 0] : key === "co" ? [0, 0, 1] : [-1, 0, 0], bb = basis(nn);
        spec = {O: P.slice(), u: bb.u, v: bb.v, n: bb.n, lo: -th / 2, hi: th / 2, oneSided: false};
      }
      return spec;
    }
    function offsetsFor(spec, tier) {
      var th = S.thick;
      if (th <= 0.01) return [0];
      return slabOffsets(spec.lo, spec.hi, th, tier === 0 ? 5 : (S.layout === "mpr" ? 25 : 49));       // Q246: midpoint rule, <= 1 mm cells
    }

    /* ---------- view objects ---------- */
    function makeView(key, label) {
      var v = {key: key, label: label, el: null, img: null, ann: null, ctx: null, actx: null, W: 0, H: 0, labels: [], sid: null, mid: 0, spec: null, offs: [], px: 1, gen: 0, dirty: true, tier: -1, cu: 0, cv: 0, CP: null, stats: null, offsetsDone: 0, imgData: null, comb: null};
      return v;
    }
    function pxFor(v) { return S.fov[v.key] / (v.W || S.res); }

    /* ---------- scheduling ---------- */
    var pumping = false, genSeq = 0;
    function markDirty(keys, quickFirst) {
      lastMark = Date.now();
      (keys || Object.keys(views)).forEach(function (k) { var v = views[k]; if (!v) return; v.dirty = true; v.gen = ++genSeq; v.tier = quickFirst ? 0 : 1; });
      clearTimeout(timers.pump); timers.pump = setTimeout(pump, 40);
      clearTimeout(timers.refine);
    }
    function visibleViews() {
      if (!S.open) return [];
      if (S.layout === "mpr") return ["cut", "ax", "co", "sa"];
      return [S.active];
    }
    function refineSoon() {                                                 // after the quick pass: the full-resolution / full-slab pass once the input is idle
      clearTimeout(timers.refine);
      timers.refine = setTimeout(function () {
        var any = false;
        visibleViews().forEach(function (k) { var v = views[k]; if (v && v.tierDone === 0 && !v.dirty) { v.dirty = true; v.tier = 1; v.gen = ++genSeq; any = true; } });
        if (any) pump();
      }, 350);
    }
    function pump() {
      if (pumping || !S.open || !geo || !C) return;
      var vis = visibleViews(), pick = null, i;
      var order = [S.active].concat(vis.filter(function (k) { return k !== S.active; }));
      for (i = 0; i < order.length; i++) { var v = views[order[i]]; if (v && vis.indexOf(v.key) >= 0 && v.dirty) { pick = v; break; } }
      if (!pick) { setStatus(); refineSoon(); return; }
      pumping = true;
      doView(pick).then(function () { pumping = false; pump(); }, function (err) { pumping = false; console.error("imaging:", err); setStatus("error: " + (err && err.message || err)); });
    }
    function doView(v) {
      var spec = viewSpec(v.key);
      if (!spec) { v.dirty = false; return Promise.resolve(); }
      var gen = v.gen, tier = v.tier, res = tier === 0 ? Math.min(S.res, 224) : S.res;
      var W = res, H = res, fov = S.fov[v.key], px = fov / W, cp = v.CP || S.P;
      var rel = [cp[0] - spec.O[0], cp[1] - spec.O[1], cp[2] - spec.O[2]], cu = dot(spec.u, rel), cv = dot(spec.v, rel);
      var u0 = cu - W * px / 2, v0 = cv + H * px / 2, offs = offsetsFor(spec, tier);
      var key = [spec.O.map(function (x) { return x.toFixed(3); }).join(","), spec.n.map(function (x) { return x.toFixed(5); }).join(","), u0.toFixed(2), v0.toFixed(2), px.toFixed(4), W, offs[0].toFixed(3), offs[offs.length - 1].toFixed(3), ++msgSeq].join("|");
      var ssN = chooseSS(offs.length, tier, S.ssCap || 0);                       // Q246: 1 while dragging, then area-coverage supersampling within a fixed budget
      var base = {key: key, ss: ssN, W: W, H: H, O: spec.O, u: spec.u, v: spec.v, n: spec.n, u0: u0, v0: v0, px: px, smin: Math.min.apply(null, offs), smax: Math.max.apply(null, offs), skinMm: T.bone_model.skin_thickness_mm, ids: C.ids,
        bone: boneParams()};
      var mid = Math.floor((offs.length - 1) / 2), labels = [], fines = [], t0 = Date.now(), sidMid = null, st = {nCand: 0, tris: 0, parityBad: 0, holes: 0, rep: 0, ms: 0}, k = 0;
      setStatus("Computing " + v.label + " ...");
      function next() {
        if (v.gen !== gen) return Promise.resolve("stale");                  // superseded: stop between sub-slices
        if (k >= offs.length) return Promise.resolve("done");
        var R = Object.assign({}, base, {s: offs[k], wantSid: k === mid});
        return runSlice(R).then(function (r) {
          labels.push(r.lab); fines.push(r.fine || null); if (k === mid) sidMid = r.sid;
          st.nCand = Math.max(st.nCand, r.nCand); st.tris += r.tris; st.parityBad += r.parityBad; st.holes += r.holesFilled || 0; st.rep += r.repairedRows || 0; st.ms += r.ms; k++;
          if (k === 1 || k === offs.length || tier === 0) { v.labels = labels.slice(); v.fine = fines.slice(); v.ss = ssN; v.sid = sidMid; v.mid = Math.min(mid, labels.length - 1); v.W = W; v.H = H; v.spec = spec; v.offs = offs.slice(0, labels.length); v.px = px; v.cu = cu; v.cv = cv; v.partial = k < offs.length; renderView(v); }
          return next();
        });
      }
      return next().then(function (res2) {
        if (res2 === "done") {
          v.labels = labels; v.fine = fines; v.ss = ssN; v.sid = sidMid; v.mid = mid; v.W = W; v.H = H; v.spec = spec; v.offs = offs; v.px = px; v.cu = cu; v.cv = cv; v.partial = false;
          v.dirty = v.gen !== gen; v.tierDone = tier; v.stats = {ms: Date.now() - t0, kernelMs: st.ms, sub: offs.length, cand: st.nCand, tris: st.tris, parityBad: st.parityBad, holes: Math.round(st.holes), repaired: st.rep, ss: ssN, W: W, tier: tier};
          perf.last = {view: v.key, ms: v.stats.ms, sub: offs.length, W: W, tier: tier, ss: ssN, cand: st.nCand, parityBad: st.parityBad, holes: Math.round(st.holes)}; perf.history.push(perf.last); if (perf.history.length > 60) perf.history.shift();
          renderView(v);
        }
      });
    }
    function boneParams() {
      var out = {};
      Object.keys(C.kinds).forEach(function (k) { var p = C.kinds[k]; out[p.id] = {axial: !!p.axial, tthin: p.tthin, tmax: p.tmax, frac: p.frac, canal: !!p.canal, z0: p.z0 || 0.2, z1: p.z1 || 0.8, ramp: p.ramp || 0.08}; });
      return out;
    }

    /* ---------- value tables + rendering ---------- */
    var lutCache = {key: "", lut: null, norm: 1};
    function currentLut() {
      if (S.modality === "ct") { if (lutCache.key !== "ct") lutCache = {key: "ct", lut: ctTable(C), norm: 1}; return lutCache; }
      var P = S.sp, key = ["mr", P.kind, P.tr, P.te, P.ti, P.fa, P.fatsat, P.gd, P.flow].join("|");
      if (lutCache.key !== key) { var m = mrTable(C, P); lutCache = {key: key, lut: m.sig, norm: m.norm}; }
      return lutCache;
    }
    function renderView(v) {
      if (!v.img || !v.labels.length) return;
      var W = v.W, H = v.H, N = W * H, k;
      var sp = v.spec, mid = Math.min(v.mid, v.labels.length - 1), plane = sp ? {O: sp.O, u: sp.u, v: sp.v, n: sp.n, u0: v.cu - W * v.px / 2, v0: v.cv + H * v.px / 2} : null;
      var val = renderValues({W: W, H: H, ss: v.ss || 1, labels: v.labels, fine: v.fine || null, mid: mid}, currentLut().lut,
        {modality: S.modality, slab: S.slab, thick: S.thick, blur: S.blur, noise: S.noise, bias: S.bias, px: v.px, plane: plane, offs: v.offs, seed: DEFAULTS.seed});   // Q246: area-weighted, noise attached to the 3-D position
      v.val = val;
      var cv = v.img, ctx = v.ctx;
      if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; v.imgData = null; }
      if (!v.imgData) v.imgData = ctx.createImageData(W, H);
      var d = v.imgData.data, lo, sc;
      if (S.modality === "ct") { lo = S.ctL - S.ctW / 2; sc = 255 / S.ctW; } else { lo = S.mrL - S.mrW / 2; sc = 255 / S.mrW; }
      for (k = 0; k < N; k++) { var g = (val[k] - lo) * sc; g = g < 0 ? 0 : g > 255 ? 255 : g; var o = k * 4; d[o] = d[o + 1] = d[o + 2] = g; d[o + 3] = 255; }
      ctx.putImageData(v.imgData, 0, 0);
      annotate(v);
      updateReadouts(v);
    }
    function rerenderAll() { Object.keys(views).forEach(function (k) { if (views[k].labels.length) renderView(views[k]); }); }

    /* ---------- annotations: orientation, crosshair, scale bar, badge ---------- */
    function annotate(v) {
      var a = v.ann, ctx = v.actx; if (!a) return;
      var r = v.wrap.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1), cw = Math.max(1, Math.round(r.width)), ch = Math.max(1, Math.round(r.height));
      if (a.width !== cw * dpr || a.height !== ch * dpr) { a.width = cw * dpr; a.height = ch * dpr; a.style.width = cw + "px"; a.style.height = ch + "px"; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, cw, ch);
      var box = imgBox(v, cw, ch);
      v.box = box; v.img.style.width = box.s + "px"; v.img.style.height = box.s + "px";
      var tiny = box.s < 280;
      ctx.font = "600 " + (tiny ? 10 : 12) + "px system-ui,sans-serif"; ctx.textBaseline = "middle";
      function txt(s, x, y, al, col) { ctx.textAlign = al; ctx.fillStyle = "rgba(0,0,0,.65)"; ctx.fillText(s, x + 1, y + 1); ctx.fillStyle = col || "#e8eef5"; ctx.fillText(s, x, y); }
      if (v.spec && S.labels) {
        var sp = v.spec;
        txt(dirLabel(sp.u), box.x + box.s - 8, box.y + box.s / 2, "right", "#ffd37a"); txt(dirLabel([-sp.u[0], -sp.u[1], -sp.u[2]]), box.x + 8, box.y + box.s / 2, "left", "#ffd37a");
        var hw = Math.max(ctx.measureText(v.label + " | " + (S.thick > 0.01 ? S.thick + " mm " + S.slab : "single slice")).width, 90) + 16;
        txt(dirLabel(sp.v), box.x + box.s / 2, box.y + (box.s / 2 - 12 > hw + 40 ? 10 : 40), "center", "#ffd37a"); txt(dirLabel([-sp.v[0], -sp.v[1], -sp.v[2]]), box.x + box.s / 2, box.y + box.s - 26, "center", "#ffd37a");
      }
      /* crosshair = anchor P in this view's plane */
      if (v.spec && S.cross && S.P) {
        var pp = pixelOf(v, S.P);
        if (pp) {
          var cx = box.x + (pp[0] / v.W) * box.s, cy = box.y + (pp[1] / v.H) * box.s, gap = 7;
          ctx.strokeStyle = "rgba(255,80,60,.9)"; ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(box.x, cy); ctx.lineTo(cx - gap, cy); ctx.moveTo(cx + gap, cy); ctx.lineTo(box.x + box.s, cy);
          ctx.moveTo(cx, box.y); ctx.lineTo(cx, cy - gap); ctx.moveTo(cx, cy + gap); ctx.lineTo(cx, box.y + box.s);
          ctx.stroke();
        }
      }
      /* scale bar */
      if (v.spec) {
        var pxCss = box.s / v.W, mmPerCss = v.px / pxCss, target = box.s * 0.22 * mmPerCss, nice = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000], len = nice[0];
        nice.forEach(function (q) { if (q <= target) len = q; });
        var wCss = len / mmPerCss, bx = box.x + 10, by = box.y + box.s - 26;
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx + wCss, by); ctx.moveTo(bx, by - 4); ctx.lineTo(bx, by + 4); ctx.moveTo(bx + wCss, by - 4); ctx.lineTo(bx + wCss, by + 4); ctx.stroke();
        txt(len + " mm", bx + wCss / 2, by - 10, "center");
      }
      /* header lines */
      var th = S.thick > 0.01 ? S.thick + " mm " + S.slab : "single slice";
      var t1 = v.label + " | " + th + (v.partial ? " | refining ..." : "");
      var t2 = S.modality === "ct" ? "CT W" + Math.round(S.ctW) + " L" + Math.round(S.ctL) : "MR " + (S.sp ? S.sp.label : "");
      txt(t1, box.x + 8, box.y + 10, "left"); if (!tiny) txt(t2, box.x + 8, box.y + 24, "left", "#9fd0ff");
      if (v.spec && !tiny) {
        txt("FOV " + Math.round(v.px * v.W) + " mm \u00B7 " + v.px.toFixed(2) + " mm/px", box.x + 8, box.y + 38, "left", "#b8c4d2");
        if (S.noise > 0 || S.blur > 0 || (S.bias > 0 && S.modality !== "ct")) txt("synthetic " + (S.noise > 0 ? "noise " : "") + (S.blur > 0 ? "blur " : "") + (S.bias > 0 && S.modality !== "ct" ? "coil bias" : ""), box.x + 8, box.y + 52, "left", "#ff9d8a");
      }
      txt("SIMULATED – NOT A SCAN", box.x + box.s - 8, box.y + box.s - 10, "right", "#ff9d8a");
    }
    function imgBox(v, cw, ch) { var s = Math.min(cw, ch); return {x: (cw - s) / 2, y: (ch - s) / 2, s: s}; }
    function pixelOf(v, p) {                                                // 3D point -> pixel (float) of the view's image
      var sp = v.spec, rel = [p[0] - sp.O[0], p[1] - sp.O[1], p[2] - sp.O[2]];
      var uu = dot(sp.u, rel), vv = dot(sp.v, rel), u0 = v.cu - v.W * v.px / 2, v0 = v.cv + v.H * v.px / 2;
      return [(uu - u0) / v.px, (v0 - vv) / v.px];
    }
    function pointOf(v, ix, iy, along, frame) {                              // pixel -> 3D point on the plane (+ along n)
      var f = frame || {O: v.spec.O, u: v.spec.u, v: v.spec.v, n: v.spec.n, u0: v.cu - v.W * v.px / 2, v0: v.cv + v.H * v.px / 2, px: v.px};
      var uu = f.u0 + ix * f.px, vv = f.v0 - iy * f.px;
      return [f.O[0] + f.u[0] * uu + f.v[0] * vv + f.n[0] * (along || 0), f.O[1] + f.u[1] * uu + f.v[1] * vv + f.n[1] * (along || 0), f.O[2] + f.u[2] * uu + f.v[2] * vv + f.n[2] * (along || 0)];
    }
    function freezeFrame(v) {                                                // Q254: a snapshot of the view's current pixel->3D mapping, held fixed for one
      var sp = v.spec;                                                      // whole drag gesture -- see setAnchorFromView for why (feedback-loop drift fix)
      return {O: sp.O.slice(), u: sp.u, v: sp.v, n: sp.n, u0: v.cu - v.W * v.px / 2, v0: v.cv + v.H * v.px / 2, px: v.px};
    }

    /* ---------- readout ---------- */
    function readoutAt(v, ix, iy) {
      if (!v.labels.length || ix < 0 || iy < 0 || ix >= v.W || iy >= v.H) return null;
      var k = Math.floor(iy) * v.W + Math.floor(ix), cl = v.labels[v.mid][k], c = C.T.classes[cl], sid = v.sid ? v.sid[k] : 65535;
      var name = sid === 65535 ? (cl === C.ids.air ? "outside the body" : "baseline fat / connective (no structure)") : sid === 65534 ? "skin rim (modelled)" : (geo.names[sid] + (geo.recs[sid] ? " [" + geo.recs[sid].id + "]" : ""));
      var p = pointOf(v, ix, iy, v.offs.length ? v.offs[v.mid] : 0), valTxt;
      var val = v.val ? v.val[k] : null;
      if (S.modality === "ct") valTxt = "HU " + Math.round(val) + " (class " + Math.round(c.ct.hu) + ")"; else valTxt = "signal " + (val * 100).toFixed(0) + " % of ref";
      return {cls: c, name: name, p: p, text: c.label + " | " + name + " | " + valTxt + " | x " + p[0].toFixed(0) + " y " + p[1].toFixed(0) + " z " + p[2].toFixed(0) + " mm", val: val, clsKey: c.key, sid: sid};
    }
    function updateReadouts(v) { if (ui.readout && v.hover) { var r = readoutAt(v, v.hover[0], v.hover[1]); if (r) ui.readout.textContent = r.text; } }

    /* ====================================================================================================
     * UI
     * ================================================================================================== */
    var CSS = [
      "#img-root{--bg:#0e131a;--panel:#161d27;--line:#2a3646;--ink:#e6edf5;--dim:#98a6b8;--acc:#6cb4ff;--warn:#ff9d8a;position:fixed;z-index:80;background:var(--bg);color:var(--ink);font:13px/1.35 system-ui,-apple-system,Segoe UI,sans-serif;display:none;flex-direction:column;min-width:0;min-height:0;box-sizing:border-box;color-scheme:dark}",
      "#img-root *{box-sizing:border-box}",
      "body.nmsk-img #img-root{display:flex}",
      "body.nmsk-img.img-side #img-root{top:0;right:0;bottom:0;width:var(--img-w,50vw);border-left:1px solid var(--line)}",
      "body.nmsk-img.img-stack #img-root{left:0;right:0;bottom:0;height:var(--img-h,62vh);border-top:1px solid var(--line)}",
      "body.nmsk-img.img-tab #img-root{inset:0}",
      "body.nmsk-img.img-tab.img-t3d #img-root{display:none}",
      "body.nmsk-img.img-side #app{width:calc(100vw - var(--img-w,50vw))!important;grid-template-columns:minmax(0,1fr)!important;overflow:hidden}",
      "body.nmsk-img.img-side #app aside,body.nmsk-img.img-side #app #inspector,body.nmsk-img.img-stack #app:not(.phone) aside,body.nmsk-img.img-stack #app:not(.phone) #inspector{display:none!important}",
      "body.nmsk-img.img-stack #app:not(.phone){grid-template-columns:minmax(0,1fr)!important}",
      "body.nmsk-img.img-stack #app{height:calc(100vh - var(--img-h,62vh))!important;min-height:0}",
      "body.nmsk-img.img-side.img-z #view{width:calc(100vw - var(--img-w,50vw))!important;right:auto!important}",
      "body.nmsk-img.img-stack.img-z #view{height:calc(100vh - var(--img-h,62vh))!important;bottom:auto!important}",
      "body.nmsk-img.img-side.img-z #topright{right:calc(var(--img-w,50vw) + .9rem)!important}",
      "body.nmsk-img.img-side.img-z #cut-panel{right:calc(var(--img-w,50vw) + 12px)!important}",
      "@media (max-width:1300px){body.nmsk-img.img-side.img-z #topright{top:calc(2.7rem + var(--safe-t,0px))!important}}",
      "#img-div{position:absolute;z-index:3;background:transparent}",
      "body.img-side #img-div{left:-5px;top:0;bottom:0;width:10px;cursor:col-resize}",
      "body.img-stack #img-div{top:-5px;left:0;right:0;height:10px;cursor:row-resize}",
      "body.img-tab #img-div{display:none}",
      "#img-div:hover,#img-div.drag{background:rgba(108,180,255,.35)}",
      ".img-head{display:flex;align-items:center;gap:6px;padding:6px 8px;border-bottom:1px solid var(--line);flex:0 0 auto;flex-wrap:wrap}",
      ".img-head b{font-size:14px}",
      ".img-badge{background:#3a1f1a;color:var(--warn);border:1px solid #7a3a2f;border-radius:999px;padding:2px 9px;font-weight:700;font-size:11.5px;letter-spacing:.02em}",
      ".img-sp{flex:1 1 8px}",
      "#img-root button,#img-root select,#img-root input{font:inherit;color:inherit}",
      "#img-root button{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:5px 9px;cursor:pointer;min-height:30px}",
      "#img-root button:hover{border-color:var(--acc)}",
      "#img-root button[aria-pressed=true],#img-root button.on{background:#1f3b5c;border-color:var(--acc);color:#fff}",
      "#img-root select,#img-root input[type=number]{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:4px 6px;min-height:30px}",
      "#img-root input[type=number]{width:70px}",
      "#img-root input[type=range]{width:100%;accent-color:var(--acc);min-height:24px}",
      ".img-views{flex:1 1 0;min-height:0;display:grid;gap:4px;padding:4px;background:#000;position:relative}",
      ".img-views.mpr{grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr}",
      ".img-views.single{grid-template-columns:1fr;grid-template-rows:1fr}",
      ".img-view{position:relative;min-width:0;min-height:0;overflow:hidden;background:#000;border:1px solid #1d2733;touch-action:none}",
      ".img-view.act{border-color:var(--acc)}",
      ".img-view canvas{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);image-rendering:auto}",       /* Q246: always smooth (bilinear) resampling when the view is scaled */
      ".img-view .ann{pointer-events:none}",
      "#img-root.ctl-off .img-ctl{display:none}",
      ".img-ctl .sec{display:contents}.img-ctl .sectabs{display:none;gap:4px}.img-ctl .modrow{grid-column:1/-1}",
      "#img-root.ctl-tabs .img-ctl{grid-template-columns:1fr;max-height:42%}",
      "#img-root.ctl-tabs .sectabs{display:flex}",
      "#img-root.ctl-tabs .sec{display:grid;gap:6px}",
      "#img-root.ctl-tabs .sec:not(.act){display:none}",
      /* Q264: overscroll-behavior:contain -- a touch-drag that scrolls this panel to its own boundary must not chain
         into the page/canvas beneath it (see PROJECT_STATE.md Q264). */
      ".img-ctl{flex:0 0 auto;max-height:46%;overflow:auto;overscroll-behavior:contain;padding:6px 8px 8px;border-top:1px solid var(--line);display:grid;gap:6px 14px;background:var(--bg);grid-template-columns:repeat(auto-fit,minmax(380px,1fr));align-content:start}",
      ".img-ctl>.img-status{grid-column:1/-1}",
      "body.img-tab .img-ctl{max-height:44%}",
      ".img-row{display:flex;gap:5px;align-items:center;flex-wrap:wrap}",
      ".img-row label{color:var(--dim);font-size:12px}",
      ".img-row .grow{flex:1 1 120px;min-width:90px}",
      ".img-read{font:12px/1.3 ui-monospace,Menlo,monospace;color:#cfe6ff;min-height:32px;padding:3px 8px;border-top:1px solid var(--line);flex:0 0 auto;word-break:break-word;max-height:3.9em;overflow:hidden}",
      ".img-status{color:var(--dim);font-size:11.5px}",
      ".img-info{position:absolute;inset:36px 0 0 0;background:var(--bg);z-index:5;overflow:auto;overscroll-behavior:contain;padding:10px 12px 40px;display:none}",
      ".img-info.show{display:block}",
      ".img-info h3{margin:14px 0 4px;font-size:14px}.img-info p,.img-info li{color:#c3cfdd}",
      ".img-info table{border-collapse:collapse;width:100%;font-size:11.5px;margin:4px 0}.img-info td,.img-info th{border:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}",
      ".img-info .st-verified,.img-info .st-verified_abstract{color:#7fe0a0}.img-info .st-secondary_checked{color:#d9e58a}.img-info .st-recalled_unverified{color:#ffb38a}.img-info .st-derived{color:#9fd0ff}.img-info .st-assumption{color:#c9b8ff}",
      "#img-tab3d{position:fixed;z-index:90;right:8px;top:8px;display:none;gap:4px}",
      "body.nmsk-img.img-tab.img-t3d #img-tab3d{display:flex}",
      "#img-tab3d button{background:#161d27;color:#e6edf5;border:1px solid #2a3646;border-radius:999px;padding:6px 12px;min-height:34px;font:600 13px system-ui}",
      ".img-diag{flex:0 0 auto;padding:2px 8px;font-size:11px;color:var(--dim);border-bottom:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      ".img-diag.bad{color:var(--warn);white-space:normal}",
      ".img-hint{flex:0 0 auto;padding:6px 8px;font-size:12px;background:#12263b;border-bottom:1px solid var(--acc);color:var(--ink)}",
      ".img-hint button{min-height:24px!important;padding:1px 8px!important;margin-left:6px}",
      "@media (max-width:520px),(max-height:520px){#img-root button{min-height:36px}#img-root select,#img-root input[type=number]{min-height:36px}}"
    ].join("\n");
    function el(tag, attrs, kids) {
      var e = document.createElement(tag);
      if (attrs) Object.keys(attrs).forEach(function (k) {
        if (k === "text") e.textContent = attrs[k]; else if (k === "html") e.innerHTML = attrs[k];
        else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]); else e.setAttribute(k, attrs[k]);
      });
      (function add(list) { list.forEach(function (c) { if (Array.isArray(c)) add(c); else if (c) e.appendChild(c); }); })(kids || []);
      return e;
    }
    function chooseLayout() {
      var w = window.innerWidth, h = window.innerHeight;
      if (S.lay !== "auto") return S.lay;
      if (Math.min(w, h) < 520) return "tab";
      return w >= h ? "side" : "stack";
    }
    function applyLayout() {
      var lay = chooseLayout(), b = document.body;
      ["img-side", "img-stack", "img-tab"].forEach(function (c) { b.classList.remove(c); });
      b.classList.toggle("nmsk-img", S.open);
      if (!S.open) { b.classList.remove("img-t3d"); fireResize(); return; }
      b.classList.add("img-" + lay);
      b.classList.toggle("img-t3d", lay === "tab" && S.tab === "3d");
      b.classList.toggle("img-z", api.kind === "webgl");
      fireResize(); fitControls();
      setTimeout(function () { fitControls(); Object.keys(views).forEach(function (k) { if (views[k].labels.length) annotate(views[k]); }); }, 60);
    }
    var firing = false;
    function fireResize() { firing = true; try { window.dispatchEvent(new Event("resize")); } catch (e) {} firing = false; }

    function build() {
      if (root) return;
      var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
      root = el("div", {id: "img-root", role: "region", "aria-label": "Imaging: simulated CT and MRI"});
      var head = el("div", {class: "img-head"}, [
        el("b", {text: "Imaging"}), el("span", {class: "img-badge", text: "Simulated from meshes – not a scan"}), el("span", {class: "img-sp"}),
        (ui.layBtn = el("button", {type: "button", title: "Layout: auto / side by side / stacked / tabs", onclick: cycleLayout, text: "◫"})),
        (ui.ctlBtn = el("button", {type: "button", title: "Show / hide the controls (more room for the image)", "aria-pressed": "true", onclick: function () { var off = root.classList.toggle("ctl-off"); ui.ctlBtn.setAttribute("aria-pressed", String(!off)); setTimeout(function () { Object.keys(views).forEach(function (k) { if (views[k].labels.length) annotate(views[k]); }); }, 50); }, text: "Controls"})),
        el("button", {type: "button", title: "Assumptions, sources and limits of the simulation", onclick: function () { ui.info.classList.toggle("show"); }, text: "Info"}),
        el("button", {type: "button", title: "Save the active view as PNG (with the badge)", onclick: savePng, text: "PNG"}),
        el("button", {type: "button", title: "Close imaging", "aria-label": "Close imaging", onclick: function () { setOpen(false); }, text: "✕"})
      ]);
      ui.info = el("div", {class: "img-info"});
      ui.diag = el("div", {class: "img-diag"}); ui.hint = el("div", {class: "img-hint", role: "note"}); ui.hint.style.display = "none";
      ui.views = el("div", {class: "img-views mpr"});
      VIEWS.forEach(function (d) {
        var v = views[d[0]] = makeView(d[0], d[1]);
        v.img = el("canvas", {}); v.ctx = v.img.getContext("2d");
        v.ann = el("canvas", {class: "ann"}); v.actx = v.ann.getContext("2d");
        v.wrap = el("div", {class: "img-view", "data-view": d[0]}, [v.img, v.ann]);
        v.wrap.addEventListener("pointerdown", function (e) { onPointer(v, e, "down"); });
        v.wrap.addEventListener("pointermove", function (e) { onPointer(v, e, "move"); });
        v.wrap.addEventListener("pointerup", function (e) { onPointer(v, e, "up"); });
        v.wrap.addEventListener("pointercancel", function (e) { onPointer(v, e, "up"); });
        v.wrap.addEventListener("contextmenu", function (e) { e.preventDefault(); });
        v.wrap.addEventListener("wheel", function (e) { e.preventDefault(); zoom(v, e.deltaY < 0 ? 0.85 : 1 / 0.85); }, {passive: false});
        ui.views.appendChild(v.wrap);
      });
      ui.read = ui.readout = el("div", {class: "img-read", text: "Move over an image: tissue class, structure, HU / signal, atlas position."});
      var ctl = ui.ctl = el("div", {class: "img-ctl"});
      buildControls(ctl);
      var div = el("div", {id: "img-div", title: "Drag to resize"});
      div.addEventListener("pointerdown", function (e) {
        div.setPointerCapture(e.pointerId); div.classList.add("drag");
        var mv = function (ev) {
          if (document.body.classList.contains("img-side")) document.documentElement.style.setProperty("--img-w", Math.max(300, Math.min(window.innerWidth - 280, window.innerWidth - ev.clientX)) + "px");
          else document.documentElement.style.setProperty("--img-h", Math.max(220, Math.min(window.innerHeight - 200, window.innerHeight - ev.clientY)) + "px");
          clearTimeout(timers.rs); timers.rs = setTimeout(function () { fireResize(); Object.keys(views).forEach(function (k) { if (views[k].labels.length) annotate(views[k]); }); }, 60);
        };
        var up = function () { div.classList.remove("drag"); div.removeEventListener("pointermove", mv); div.removeEventListener("pointerup", up); };
        div.addEventListener("pointermove", mv); div.addEventListener("pointerup", up);
      });
      root.appendChild(div); root.appendChild(head); root.appendChild(ui.diag); root.appendChild(ui.hint); root.appendChild(ui.info); root.appendChild(ui.views); root.appendChild(ui.read); root.appendChild(ctl);
      document.body.appendChild(root);
      var tabs = el("div", {id: "img-tab3d"}, [el("button", {type: "button", text: "3D", "aria-pressed": "true"}), el("button", {type: "button", text: "Image ▸", onclick: function () { S.tab = "image"; applyLayout(); pumpAfterShow(); }})]);
      document.body.appendChild(tabs); ui.tabs = tabs;
      /* in tab layout, the panel header gets a 3D button */
      head.insertBefore(ui.to3d = el("button", {type: "button", text: "◂ 3D", title: "Back to the 3D model", onclick: function () { S.tab = "3d"; applyLayout(); }}), head.children[1]);
      window.addEventListener("resize", function () { if (S.open && !firing) { applyLayout(); updateLayoutUI(); } });
      renderInfo(); setDiag();
    }
    function pumpAfterShow() { Object.keys(views).forEach(function (k) { if (views[k].labels.length) annotate(views[k]); }); markDirty(null, false); }
    function cycleLayout() {
      var seq = ["auto", "side", "stack", "tab"]; S.lay = seq[(seq.indexOf(S.lay) + 1) % seq.length]; S.tab = "image"; applyLayout(); updateLayoutUI();
      ui.layBtn.title = "Layout: " + S.lay; setStatus("layout: " + S.lay);
    }
    function updateLayoutUI() {
      var lay = chooseLayout();
      if (ui.to3d) ui.to3d.style.display = lay === "tab" ? "" : "none";
      var vv = ui.views; vv.className = "img-views " + (S.layout === "mpr" ? "mpr" : "single");
      VIEWS.forEach(function (d) { var v = views[d[0]]; var show = S.layout === "mpr" || S.active === d[0]; v.wrap.style.display = show ? "" : "none"; v.wrap.classList.toggle("act", S.active === d[0]); });
      if (S.layout === "mpr" && lay === "tab" && window.innerHeight > window.innerWidth) vv.style.gridTemplateColumns = "1fr 1fr"; else vv.style.gridTemplateColumns = "";
    }

    function buildControls(ctl) {
      /* modality + view layout */
      ui.modBtns = {};
      var mrow = el("div", {class: "img-row modrow"}, [
        (ui.modBtns.ct = el("button", {type: "button", text: "CT", onclick: function () { setModality("ct"); }})),
        (ui.modBtns.mr = el("button", {type: "button", text: "MRI", onclick: function () { setModality("mr"); }})),
        el("span", {class: "img-sp"}),
        (ui.secTabs = el("div", {class: "sectabs"}, [["contrast", "Contrast"], ["slab", "Slab"], ["view", "View"], ["more", "More"]].map(function (d) {
          return el("button", {type: "button", "data-sec": d[0], text: d[1], onclick: function () { setSec(d[0]); }});
        })))
      ]);
      var r1 = el("div", {class: "img-row"}, [
        (ui.lay1 = el("button", {type: "button", text: "MPR 2\u00D72", onclick: function () { setLayout("mpr"); }})),
        VIEWS.map(function (d) { return el("button", {type: "button", "data-v": d[0], text: d[1] === "Cut plane" ? "Cut" : d[1].slice(0, 3), title: d[1] + " only", onclick: function () { S.active = d[0]; setLayout("single"); }}); })
      ]);
      /* CT controls */
      ui.ctBox = el("div", {class: "img-row"}, [
        el("label", {text: "Window"}),
        (ui.winSel = el("select", {onchange: function () { var w = T.ct_windows.filter(function (q) { return q.key === ui.winSel.value; })[0]; if (w) { S.ctWin = w.key; S.ctW = w.width; S.ctL = w.level; syncCt(); rerenderAll(); } }})),
        el("label", {text: "W"}), (ui.ctW = el("input", {type: "number", step: "10", min: "1", oninput: function () { S.ctW = Math.max(1, +ui.ctW.value || 1); S.ctWin = "custom"; ui.winSel.value = "custom"; rerenderAll(); }})),
        el("label", {text: "L"}), (ui.ctL = el("input", {type: "number", step: "10", oninput: function () { S.ctL = +ui.ctL.value || 0; S.ctWin = "custom"; ui.winSel.value = "custom"; rerenderAll(); }}))
      ]);
      /* MRI controls */
      ui.mrBox = el("div", {class: "mrbox", style: "display:grid;gap:6px"}, [
        el("div", {class: "img-row"}, [el("label", {text: "Sequence"}), (ui.seqSel = el("select", {class: "grow", onchange: function () { setSeq(ui.seqSel.value); }}))]),
        el("div", {class: "img-row"}, [
          el("label", {text: "TR"}), (ui.tr = el("input", {type: "number", step: "10", min: "1", oninput: onSeqEdit})),
          el("label", {text: "TE"}), (ui.te = el("input", {type: "number", step: "1", min: "0.1", oninput: onSeqEdit})),
          el("label", {text: "TI"}), (ui.ti = el("input", {type: "number", step: "10", min: "0", oninput: onSeqEdit})),
          el("label", {text: "FA°"}), (ui.fa = el("input", {type: "number", step: "5", min: "1", max: "90", oninput: onSeqEdit}))
        ]),
        el("div", {class: "img-row"}, [
          (ui.fs = el("button", {type: "button", text: "fat-sat", onclick: function () { S.sp.fatsat = !S.sp.fatsat; syncMr(); rerenderAll(); }})),
          (ui.gd = el("button", {type: "button", text: "post-Gd", onclick: function () { S.sp.gd = !S.sp.gd; syncMr(); rerenderAll(); }})),
          (ui.auto = el("button", {type: "button", text: "auto level", onclick: function () { S.mrW = 1; S.mrL = 0.5; syncMr(); rerenderAll(); }})),
          el("label", {text: "W"}), (ui.mrW = el("input", {type: "range", min: "0.1", max: "2", step: "0.02", class: "grow", oninput: function () { S.mrW = +ui.mrW.value; rerenderAll(); }})),
          el("label", {text: "L"}), (ui.mrL = el("input", {type: "range", min: "-0.2", max: "1.2", step: "0.02", class: "grow", oninput: function () { S.mrL = +ui.mrL.value; rerenderAll(); }}))
        ])
      ]);
      /* slab */
      ui.slabRow = el("div", {class: "img-row"}, [
        el("label", {text: "Slab"}),
        (ui.thSl = el("input", {type: "range", min: "0", max: "100", step: "1", class: "grow", "aria-label": "Slice thickness in millimetres (0 = single slice)", oninput: function () { setThick(+ui.thSl.value, true); }})),
        (ui.thOut = el("output", {text: ""})),
        [0, 1, 3, 5, 10, 25, 50].map(function (t) { return el("button", {type: "button", "data-th": String(t), text: String(t), onclick: function () { setThick(t, true); }}); }),
        (ui.linkBtn = el("button", {type: "button", text: "3D slab", "aria-pressed": "false", title: "Also show this slab thickness in the 3D view (off: the 3D view keeps the slab set in its Cut panel, default = the whole rest of the body)", onclick: function () { S.link = !S.link; ui.linkBtn.setAttribute("aria-pressed", String(S.link)); if (S.link) pushSlabToCut(); }})),
        el("span", {class: "img-sp"}),
        ["avg", "mip", "minip"].map(function (m) { return el("button", {type: "button", "data-slab": m, text: m === "avg" ? "Avg" : m === "mip" ? "MIP" : "MinIP", title: m === "avg" ? "Average intensity projection (thick MPR)" : m === "mip" ? "Maximum intensity projection" : "Minimum intensity projection", onclick: function () { S.slab = m; syncSlab(); rerenderAll(); }}); })
      ].reduce(function (a, x) { return a.concat(x); }, []));
      /* field of view / quality */
      ui.fovRow = el("div", {class: "img-row"}, [
        el("label", {text: "FOV"}),
        [150, 300, 450, 700, 1000, 1800].map(function (f) { return el("button", {type: "button", "data-fov": String(f), text: String(f), onclick: function () { setFov(f); }}); }),
        el("button", {type: "button", text: "center", title: "Center the image on the crosshair", onclick: function () { centerViews(); }}),
        el("label", {text: "px"}), (ui.resSel = el("select", {onchange: function () { S.res = +ui.resSel.value; markDirty(null, false); }}, [256, 320, 384, 512].map(function (r) { return el("option", {value: String(r), text: r + "²"}); })))
      ]);
      /* Q254 item 6: oblique Cut-plane dial -- a genuinely oblique CT/MRI plane without orbiting the 3-D view */
      function setObl(k, v) { S.obl[k] = v; applyOblique(); }
      ui.oblRow = el("div", {class: "img-row"}, [
        el("label", {text: "Oblique", title: "Tilt the Cut plane directly, off a chosen base plane -- no camera orbiting needed. (The 3-D view's Cut → \"facing me\" button still also sets an oblique Cut plane, from the current camera angle; this dial is the other way to get one.)"}),
        [["ax", "Axial"], ["co", "Coronal"], ["sa", "Sagittal"]].map(function (d) {
          return el("button", {type: "button", "data-ob": d[0], text: d[1], "aria-pressed": String(S.obl.base === d[0]), title: "Tilt away from the " + d[1].toLowerCase() + " plane",
            onclick: function () { S.obl.base = d[0]; Array.prototype.forEach.call(ui.oblRow.querySelectorAll("[data-ob]"), function (b) { b.setAttribute("aria-pressed", String(b.dataset.ob === d[0])); }); setObl("base", d[0]); }});
        }),
        el("label", {text: "Tilt"}), (ui.oblTilt = el("input", {type: "range", min: "0", max: "60", step: "1", class: "grow", "aria-label": "Oblique tilt angle in degrees, off the base plane", oninput: function () { ui.oblTiltOut.textContent = ui.oblTilt.value + "°"; setObl("tilt", +ui.oblTilt.value); }})),
        (ui.oblTiltOut = el("output", {text: "0°"})),
        el("label", {text: "Direction"}), (ui.oblDir = el("input", {type: "range", min: "0", max: "359", step: "1", class: "grow", "aria-label": "Which way the oblique plane tilts, in degrees", oninput: function () { ui.oblDirOut.textContent = ui.oblDir.value + "°"; setObl("dir", +ui.oblDir.value); }})),
        (ui.oblDirOut = el("output", {text: "0°"})),
        el("button", {type: "button", text: "reset", title: "Back to a plain (non-oblique) base plane", onclick: function () { S.obl.tilt = 0; S.obl.dir = 0; ui.oblTilt.value = "0"; ui.oblDir.value = "0"; ui.oblTiltOut.textContent = "0°"; ui.oblDirOut.textContent = "0°"; applyOblique(); }}),
        el("div", {class: "img-status", text: "Drives the Cut view directly (switch to Cut / MPR to see it) -- the same oblique-plane mechanism as the 3-D view's Cut → \"facing me\" camera trick, without needing to orbit the camera."})
      ]);
      /* Q254 item 7: slice-position cine (fps selector modelled on the ultrasound tool's cineBtn / fps row) */
      ui.cineRow = el("div", {class: "img-row"}, [
        (ui.cineBtn = el("button", {type: "button", text: "▶ cine", "aria-pressed": "false", title: "Step the active view's slice position through the body, as a movie", onclick: function () { setCine(!S.cine); }})),
        el("label", {text: "fps"}), (ui.cineFps = el("select", {"aria-label": "Cine frames per second", onchange: function () { S.fps = +ui.cineFps.value; if (S.cine) { setCine(false); setCine(true); } }}, [1, 2, 3, 5, 8].map(function (f) { return el("option", {value: String(f), text: String(f)}); })))
      ]);
      ui.cineFps.value = String(S.fps);
      ui.optRow = el("div", {class: "img-row"}, [
        el("label", {text: "Noise"}), (ui.noise = el("input", {type: "range", min: "0", max: "10", step: "0.5", class: "grow", "aria-label": "Synthetic noise (default off)", oninput: function () { S.noise = +ui.noise.value * (S.modality === "ct" ? 5 : 1); ui.noiseOut.textContent = S.noise ? "synthetic noise" : "off"; rerenderAll(); }})), (ui.noiseOut = el("output", {text: "off"})),
        el("label", {text: "Blur"}), (ui.blur = el("input", {type: "range", min: "0", max: "4", step: "0.25", class: "grow", "aria-label": "Synthetic blur in mm (default off)", oninput: function () { S.blur = +ui.blur.value; ui.blurOut.textContent = S.blur ? S.blur + " mm" : "off"; rerenderAll(); }})), (ui.blurOut = el("output", {text: "off"})),
        el("label", {text: "Coil bias"}), (ui.bias = el("input", {type: "range", min: "0", max: "30", step: "5", class: "grow", "aria-label": "Synthetic MRI coil sensitivity bias, smooth in 3-D (default off)", oninput: function () { S.bias = +ui.bias.value / 100; ui.biasOut.textContent = S.bias ? "±" + ui.bias.value + " %" : "off"; rerenderAll(); }})), (ui.biasOut = el("output", {text: "off"})),
        (ui.crossBtn = el("button", {type: "button", text: "crosshair", "aria-pressed": "true", onclick: function () { S.cross = !S.cross; ui.crossBtn.setAttribute("aria-pressed", String(S.cross)); rerenderAll(); }})),
        (ui.lblBtn = el("button", {type: "button", text: "labels", "aria-pressed": "true", onclick: function () { S.labels = !S.labels; ui.lblBtn.setAttribute("aria-pressed", String(S.labels)); rerenderAll(); }}))
      ]);
      ui.status = el("div", {class: "img-status", text: ""});
      function sec(name, kids) { var d = el("div", {class: "sec", "data-sec": name}, kids); ui.secs[name] = d; return d; }
      ui.secs = {};
      [mrow, sec("contrast", [ui.ctBox, ui.mrBox]), sec("slab", [ui.slabRow]), sec("view", [r1, ui.fovRow, ui.oblRow, ui.cineRow]), sec("more", [ui.optRow]), ui.status].forEach(function (x) { ctl.appendChild(x); });
      setSec(S.sec || "contrast");
    }
    function setSec(name) {
      S.sec = name;
      Object.keys(ui.secs || {}).forEach(function (k) { ui.secs[k].classList.toggle("act", k === name); });
      Array.prototype.forEach.call(ui.secTabs.querySelectorAll("[data-sec]"), function (b) { b.setAttribute("aria-pressed", String(b.dataset.sec === name)); });
    }
    function fitControls() {                                                // short panels: one section of the controls at a time
      if (!root) return;
      var h = root.getBoundingClientRect().height;
      root.classList.toggle("ctl-tabs", h > 0 && h < 860);
    }
    var BTN_TIP = "CT / MRI: simulated CT and MRI of the cut plane (not a scan)";
    function diagText() {                                                  // Q239: the one-line state of the tool, shown in the panel and in the button's tooltip
      if (tableErr) return {ok: false, text: "Imaging tool: NOT ready – tissue table: " + tableErr};
      if (!T) return {ok: null, text: "Imaging tool: loading tissue table …"};
      if (geoErr) return {ok: false, text: "Imaging tool: NOT ready – " + geoErr + " (v" + VERSION + ")"};
      return {ok: true, text: "Imaging tool: ready (v" + VERSION + ", tissues " + T.classes.length + ", code " + CODE_SRC + ", table " + tableSrc + ")"};
    }
    function setDiag() {
      var d = diagText(); DIAG.imaging = {ok: d.ok, text: d.text, version: VERSION, tissues: T ? T.classes.length : 0, code: CODE_SRC, table: tableSrc};
      if (ui.diag) { ui.diag.textContent = d.text; ui.diag.className = "img-diag" + (d.ok === false ? " bad" : ""); ui.diag.title = d.text; }
      setBtnTip(ui.btn, BTN_TIP, d.ok, d.text);
    }
    function showHint(text, always) {                                       // first-use hint (once per browser) or an always-shown note
      var seen = false; try { seen = localStorage.getItem("nmsk-imaging-hint") === "1"; } catch (e) {}
      if (!ui.hint || (seen && !always)) return;
      ui.hint.textContent = ""; ui.hint.appendChild(document.createTextNode(text + " "));
      ui.hint.appendChild(el("button", {type: "button", text: "OK", onclick: function () { ui.hint.style.display = "none"; try { localStorage.setItem("nmsk-imaging-hint", "1"); } catch (e) {} }}));
      ui.hint.style.display = "";
    }
    function setStatus(t) {
      if (!ui.status) return;
      if (t) ui.status.textContent = t;
      else {
        var p = perf.last; ui.status.textContent = p ? (p.view + ": " + p.ms + " ms, " + p.sub + " sub-slice" + (p.sub > 1 ? "s" : "") + ", " + p.W + "²" + (p.ss > 1 ? " x" + p.ss + "²" : "") + (p.parityBad ? ", " + p.parityBad + " open-mesh rows repaired" : "") + (p.holes ? ", " + p.holes + " px of small gaps filled with the surrounding tissue" : "")) : "";
      }
    }
    function syncCt() {
      ui.winSel.innerHTML = ""; T.ct_windows.concat([{key: "custom", label: "Custom"}]).forEach(function (w) { ui.winSel.appendChild(el("option", {value: w.key, text: w.label + (w.width ? " (W" + w.width + "/L" + w.level + ")" : "")})); });
      ui.winSel.value = S.ctWin; ui.ctW.value = Math.round(S.ctW); ui.ctL.value = Math.round(S.ctL);
    }
    function syncMr() {
      if (!ui.seqSel.options.length) T.mr_sequences.forEach(function (q) { ui.seqSel.appendChild(el("option", {value: q.key, text: q.label})); });
      ui.seqSel.value = S.seq; ui.tr.value = S.sp.tr; ui.te.value = S.sp.te; ui.ti.value = S.sp.ti; ui.fa.value = S.sp.fa;
      ui.ti.disabled = S.sp.kind !== "ir"; ui.fa.disabled = S.sp.kind !== "gre";
      ui.fs.setAttribute("aria-pressed", String(!!S.sp.fatsat)); ui.gd.setAttribute("aria-pressed", String(!!S.sp.gd));
      ui.mrW.value = S.mrW; ui.mrL.value = S.mrL;
    }
    function syncSlab() {
      ui.thSl.value = S.thick; ui.thOut.textContent = S.thick > 0.01 ? S.thick + " mm" : "single";
      Array.prototype.forEach.call(ui.slabRow.querySelectorAll("[data-th]"), function (b) { b.setAttribute("aria-pressed", String(+b.dataset.th === Math.round(S.thick))); });
      Array.prototype.forEach.call(ui.slabRow.querySelectorAll("[data-slab]"), function (b) { b.setAttribute("aria-pressed", String(b.dataset.slab === S.slab)); b.disabled = S.thick <= 0.01; });
    }
    function syncAll() {
      ui.modBtns.ct.setAttribute("aria-pressed", String(S.modality === "ct")); ui.modBtns.mr.setAttribute("aria-pressed", String(S.modality === "mr"));
      ui.ctBox.style.display = S.modality === "ct" ? "" : "none"; ui.mrBox.style.display = S.modality === "mr" ? "" : "none";
      syncCt(); syncMr(); syncSlab();
      ui.lay1.setAttribute("aria-pressed", String(S.layout === "mpr"));
      Array.prototype.forEach.call(ui.ctl.querySelectorAll("[data-v]"), function (b) { b.setAttribute("aria-pressed", String(S.layout === "single" && S.active === b.dataset.v)); });
      Array.prototype.forEach.call(ui.fovRow.querySelectorAll("[data-fov]"), function (b) { b.setAttribute("aria-pressed", String(+b.dataset.fov === S.fov[S.active])); });
      ui.resSel.value = String(S.res);
      updateLayoutUI();
    }
    function setModality(m) { S.modality = m; syncAll(); rerenderAll(); }
    function setSeq(k) { S.seq = k; S.sp = JSON.parse(JSON.stringify(T.mr_sequences.filter(function (q) { return q.key === k; })[0])); S.mrW = 1; S.mrL = 0.5; syncMr(); rerenderAll(); }
    function onSeqEdit() { S.sp.tr = Math.max(1, +ui.tr.value || 1); S.sp.te = Math.max(0.1, +ui.te.value || 0.1); S.sp.ti = Math.max(0, +ui.ti.value || 0); S.sp.fa = Math.min(90, Math.max(1, +ui.fa.value || 1)); rerenderAll(); }
    function setLayout(l) { S.layout = l; if (l === "single") { S.res = Math.max(S.res, 384); } syncAll(); markDirty(null, true); }
    function setFov(f) { VIEWS.forEach(function (d) { if (S.layout === "mpr" || d[0] === S.active) S.fov[d[0]] = f; }); syncAll(); markDirty(null, true); }
    function zoom(v, f) { S.fov[v.key] = Math.max(60, Math.min(2400, S.fov[v.key] * f)); markDirty([v.key], true); syncAll(); }
    function centerViews() { Object.keys(views).forEach(function (k) { views[k].CP = null; }); markDirty(null, true); }
    function setThick(t, push) {
      S.thick = Math.max(0, Math.min(100, t)); syncSlab();
      if (push && S.link) pushSlabToCut();
      markDirty(null, true); rerenderAll();
    }

    /* ---------- the 3D side: the existing Cut mode, driven through its own panel ---------- */
    function pushSlabToCut() {
      var sl = document.getElementById("cut-thsl"); if (!sl) return;
      var v = S.thick > 0.01 ? Math.max(1, Math.min(99, S.thick)) : 1;
      sl.value = String(v); sl.dispatchEvent(new Event("input", {bubbles: true}));
      lastSlab = api.cutSlab ? api.cutSlab() : 0;
    }
    function ensureCut() {
      if (cutPlane()) return true;
      var btn = document.getElementById("t-cut"), ax = document.querySelector('#cut-axis button[data-axis="y"]');
      if (btn) btn.click();
      if (ax) ax.click();                                                    // the page's own axial preset: plane through the model centre, upper part removed
      var c0 = cutPlane(), pos = document.getElementById("cut-pos"), bb0 = geo && geo.bodyBox;
      if (c0 && pos && bb0 && Math.abs(c0.kn[1] + 1) < 1e-6) {               // start at the upper abdomen (about 68 % of the body height) instead of the mid-thigh
        var yT = bb0.lo[1] + 0.68 * (bb0.hi[1] - bb0.lo[1]);
        pos.value = String(yT - c0.c); pos.dispatchEvent(new Event("input", {bubbles: true}));
      }
      if (cutPlane()) return true;
      var bb = geo && geo.bodyBox, tgt = bb ? [(bb.lo[0] + bb.hi[0]) / 2, (bb.lo[1] + bb.hi[1]) / 2, (bb.lo[2] + bb.hi[2]) / 2] : api.view().target;
      try { api.setCut({normal: [0, -1, 0], point: tgt}); } catch (e) {}
      return !!cutPlane();
    }
    /* move the page's cut plane (same orientation, same side, same slab) through P using its own position slider; false if that is not possible */
    function movePlaneThrough(P) {
      var pos = document.getElementById("cut-pos"), cp = cutPlane();
      if (!pos || !cp) return false;
      var d = dot(cp.kn, P) + cp.c;
      if (Math.abs(d) < 0.3) return true;
      var v0 = parseFloat(pos.value) || 0;
      function tryDelta(delta) {
        pos.value = String(v0 + delta); pos.dispatchEvent(new Event("input", {bubbles: true}));
        var c2 = cutPlane(); return c2 ? Math.abs(dot(c2.kn, P) + c2.c) : 1e9;
      }
      var e1 = tryDelta(d);
      if (e1 > 0.6) { var e2 = tryDelta(-d); if (e2 > e1) { e1 = tryDelta(d); } else e1 = e2; }
      return e1 < 1.2;
    }
    function movePointToPlane() {
      var cp = cutPlane(); if (!cp || !S.P) return;
      var d = dot(cp.kn, S.P) + cp.c; S.P = [S.P[0] - d * cp.kn[0], S.P[1] - d * cp.kn[1], S.P[2] - d * cp.kn[2]];
    }
    function pollCut() {
      if (!S.open) return;
      var c = api.cut(), sl = api.cutSlab ? api.cutSlab() : 0, key = c ? c.map(function (x) { return x.toFixed(4); }).join(",") : "off";
      var changed = false;
      if (key !== lastPlaneKey) {
        lastPlaneKey = key;
        if (c) { if (!S.P) S.P = api.view().target.slice(); movePointToPlane(); changed = true; setStatus(""); }
        else setStatus("Cut mode is off: the cut-plane view needs it (press Cut). The axial / coronal / sagittal views still work.");
      }
      if (Math.abs(sl - lastSlab) > 0.01) {
        lastSlab = sl;
        if (sl > 0 && Math.abs(sl - S.thick) > 0.01) { S.thick = Math.min(100, sl); syncSlab(); changed = true; }
      }
      if (changed) { markDirty(null, true); }
    }

    /* ---------- pointer interaction: crosshair, wheel zoom, pan ---------- */
    var drag = null, touches = {};
    function localPx(v, e) {
      var r = v.wrap.getBoundingClientRect(), box = v.box || imgBox(v, r.width, r.height);
      var cx = e.clientX - r.left, cy = e.clientY - r.top;
      return [(cx - box.x) / box.s * v.W, (cy - box.y) / box.s * v.H, (cx - box.x) / box.s, (cy - box.y) / box.s];
    }
    function onPointer(v, e, kind) {
      if (!v.labels.length || !v.spec) return;
      var q = localPx(v, e), inside = q[2] >= 0 && q[2] <= 1 && q[3] >= 0 && q[3] <= 1;
      if (kind === "down") {
        S.active = v.key; Array.prototype.forEach.call(ui.views.children, function (c) { c.classList.toggle("act", c === v.wrap); });
        v.wrap.setPointerCapture(e.pointerId);
        touches[e.pointerId] = [e.clientX, e.clientY];
        var ids = Object.keys(touches);
        if (ids.length >= 2) { drag = {mode: "pinch", v: v, d0: pinchDist(), f0: S.fov[v.key]}; return; }
        if (e.button === 2 || e.shiftKey || e.button === 1) { drag = {mode: "pan", v: v, x: e.clientX, y: e.clientY, cp: (v.CP || S.P).slice()}; return; }
        drag = {mode: "cross", v: v, frame0: freezeFrame(v)}; if (inside) setAnchorFromView(v, q[0], q[1], drag.frame0);
        showReadout(v, q);
      } else if (kind === "move") {
        touches[e.pointerId] && (touches[e.pointerId] = [e.clientX, e.clientY]);
        if (drag && drag.mode === "pinch" && Object.keys(touches).length >= 2) { var f = drag.d0 / Math.max(10, pinchDist()); S.fov[drag.v.key] = Math.max(60, Math.min(2400, drag.f0 * f)); markDirty([drag.v.key], true); return; }
        if (drag && drag.mode === "pan") {
          var r = v.wrap.getBoundingClientRect(), s = Math.min(r.width, r.height), mm = S.fov[v.key] / s, dx = (e.clientX - drag.x) * mm, dy = (e.clientY - drag.y) * mm, sp = v.spec;
          v.CP = [drag.cp[0] - sp.u[0] * dx + sp.v[0] * dy, drag.cp[1] - sp.u[1] * dx + sp.v[1] * dy, drag.cp[2] - sp.u[2] * dx + sp.v[2] * dy];
          markDirty([v.key], true); return;
        }
        // Q254: a frozen frame (captured on pointer-down) maps pixel -> 3D for the WHOLE gesture. Without it, since
        // each render re-centres the view on the just-set S.P (spec.O = S.P for ax/co/sa), a redraw that lands
        // mid-drag (common once events arrive faster than the 30 ms debounce) makes the next move's point add its
        // pixel offset on top of the already-shifted centre -- a feedback loop that can run the point kilometres
        // outside the body within a handful of frames, after which every view is blank (and stays blank: nothing
        // ever pulls S.P back into range). Using the gesture's own start frame throughout removes the loop.
        if (drag && drag.mode === "cross" && drag.v === v && inside) setAnchorFromView(v, q[0], q[1], drag.frame0);
        showReadout(v, q);
      } else {
        delete touches[e.pointerId]; if (!Object.keys(touches).length) drag = null;
      }
    }
    function pinchDist() { var k = Object.keys(touches), a = touches[k[0]], b = touches[k[1]]; return Math.hypot(a[0] - b[0], a[1] - b[1]); }
    function showReadout(v, q) {
      v.hover = [q[0], q[1]];
      var r = readoutAt(v, q[0], q[1]); if (r && ui.readout) ui.readout.textContent = r.text;
    }
    function setAnchorFromView(v, ix, iy, frame) {
      var along = 0, p = pointOf(v, ix, iy, along, frame);
      S.P = p;
      if (v.key !== "cut") {                                               // the clicked point leaves the cut plane: move the cut plane through it
        if (!movePlaneThrough(p)) {
          var cp = cutPlane();
          if (cp) { try { api.setCut({normal: cp.kn, point: p}); } catch (e) {} setTimeout(function () { if (S.link) pushSlabToCut(); }, 0); }
        }
      }
      clearTimeout(timers.anchor);
      Object.keys(views).forEach(function (k) { if (views[k].labels.length) annotate(views[k]); });
      timers.anchor = setTimeout(function () { markDirty(null, true); }, 30);
    }

    /* ---------- info panel (assumptions, sources) ---------- */
    function renderInfo() {
      var box = ui.info; box.innerHTML = "";
      if (!T) { box.appendChild(el("p", {text: tableErr ? "Tissue table not loaded: " + tableErr : "Loading tissue table ..."})); return; }
      box.appendChild(el("h3", {text: "What you are looking at"}));
      box.appendChild(el("p", {html: "<b>A simulation computed from this viewer's segmented anatomical meshes – not a scan.</b> The cut plane (and slab) is intersected with every mesh, each pixel gets the AREA-weighted mean of the tissue values of the structures that cover it (partial volume, painter order = tissue priority of the table), and CT numbers / MRI signal come from the table below. Reconstruction, artefacts, motion, contrast kinetics and disease are not simulated unless a control says so (noise, blur and coil bias are off by default and clearly synthetic; noise and bias are attached to the position in the body, so they stay with the tissue when the plane moves)."}));
      var ul = el("ul"); T.honesty.forEach(function (h) { ul.appendChild(el("li", {text: h})); }); box.appendChild(ul);
      box.appendChild(el("h3", {text: "Geometry assumptions"}));
      var ul2 = el("ul");
      ["Only the outer surface of each structure exists. Cortical vs cancellous bone and the medullary canal are MODELLED from the slice (" + T.bone_model.note + ")",
       "Space inside the skin that no structure covers: " + T.baseline.note,
       "Thin skin rim: " + T.bone_model.skin_note + ". Meshes with open surfaces can leave a few mis-filled scan lines; they are repaired from the lines above and below (best agreement of the span sets) and counted in the status line.",
       "All structures are included whatever the visibility toggles of the 3D view say.",
       "Slab = sub-slices at <= 1 mm (midpoint rule; fewer for thick slabs and while dragging) combined as average (thick MPR), MIP or MinIP. Orthogonal views use a slab of the same thickness centred on the crosshair; the cut-plane view uses the kept slab behind the plane.",
       "Continuity (Q246): while the plane is dragged a quick one-sample-per-pixel preview is drawn; when it rests the image is recomputed with up to 3 x 3 samples per pixel (edges are anti-aliased, a boundary pixel is a mix of both tissues). Small enclosed gaps (smaller than ~1.5 pixels) inside the body are given the tissue around them instead of the fat baseline and counted in the status line; scan lines the mesh leaves open are repaired from the lines above and below. Nothing else is invented."].forEach(function (t) { ul2.appendChild(el("li", {text: t})); });
      box.appendChild(ul2);
      box.appendChild(el("h3", {text: "Tissue table (" + T.classes.length + " classes) - status colour: green verified (abstract / open full text), yellow secondary source, orange recalled/UNVERIFIED, blue derived, purple assumption; the weakest value of a row sets its colour"}));
      var tb = el("table"); tb.appendChild(el("tr", {html: "<th>class</th><th>HU</th><th>CT status</th><th>MRI 1.5 T (PD, T1, T2 ms)</th><th>MRI status</th><th>sources</th>"}));
      T.classes.forEach(function (c) {
        var m = c.mri.pools.map(function (p) { return (c.mri.pools.length > 1 ? Math.round(p.frac * 100) + "%: " : "") + p.pd + ", " + p.t1 + ", " + p.t2; }).join(" + ");
        var srcs = (c.ct.src || []).concat(c.mri.src || []).filter(function (x, i, a) { return a.indexOf(x) === i; }).map(function (k) { var rf = T.references[k]; return rf ? (rf.pmid ? "PMID " + rf.pmid : k) : k; }).join(", ");
        tb.appendChild(el("tr", {html: "<td>" + c.label + "</td><td>" + c.ct.hu + " (" + c.ct.range[0] + ".." + c.ct.range[1] + ")</td><td class='st-" + c.ct.status + "'>" + c.ct.status + (c.ct.vsum ? " (" + c.ct.vsum + ")" : "") + "</td><td>" + m + "</td><td class='st-" + c.mri.status + "'>" + c.mri.status + (c.mri.vsum ? " (" + c.mri.vsum + ")" : "") + "</td><td>" + srcs + "</td>"}));
      });
      box.appendChild(tb);
      box.appendChild(el("h3", {text: "References (PubMed-checked unless marked)"}));
      var ol = el("ul"); Object.keys(T.references).forEach(function (k) { var r = T.references[k]; ol.appendChild(el("li", {text: r.cite + (r.pmid ? " [PMID " + r.pmid + "]" : " [not in PubMed]") + " - " + r.used_for})); }); box.appendChild(ol);
      box.appendChild(el("h3", {text: "Sequence equations"}));
      box.appendChild(el("p", {text: "Spin echo: S = PD (1 - e^(-TR/T1)) e^(-TE/T2). Inversion recovery (STIR, FLAIR; magnitude): S = PD |1 - 2 e^(-TI/T1) + e^(-TR/T1)| e^(-TE/T2). Spoiled gradient echo: S = PD sin(a) (1 - E1) / (1 - E1 cos a) e^(-TE/T2*), E1 = e^(-TR/T1). Fat-sat multiplies the fat pools by " + T.mr_global.fat_suppression_residual + ". Flowing blood: signal x (1 - flow) on spin-echo sequences (flow void), x (1 + " + T.mr_global.inflow_gain + " flow) on gradient echo (inflow). Post-gadolinium uses the schematic 't1_gd' column. All values are relative signal; the image is auto-levelled."}));
      var rep = el("div", {class: "img-status", id: "img-map-report"}); box.appendChild(el("h3", {text: "Structure → tissue mapping on this page"})); box.appendChild(rep); ui.mapReport = rep;
    }
    function mappingReport() {
      if (!geo || !ui.mapReport) return null;
      var counts = {}, un = [], i;
      for (i = 0; i < geo.n; i++) { var k = C.T.classes[geo.cls[i]].key; counts[k] = (counts[k] || 0) + 1; if (C.T.classes[geo.cls[i]].unassigned) un.push(geo.recs[i].id); }
      var rep = {structures: geo.n, byClass: counts, unassigned: un.length, unassignedIds: un.slice(0, 80)};
      ui.mapReport.textContent = geo.n + " structures mapped; " + un.length + " unassigned (soft tissue, unassigned)" + (un.length ? ": " + un.slice(0, 12).join(", ") + (un.length > 12 ? " ..." : "") : "") + ". By class: " + Object.keys(counts).sort().map(function (k) { return k + " " + counts[k]; }).join(", ") + ".";
      return rep;
    }
    function savePng() {
      var v = views[S.active]; if (!v || !v.labels.length) return;
      var r = v.wrap.getBoundingClientRect(), s = Math.round(Math.min(r.width, r.height) * (window.devicePixelRatio || 1)), out = document.createElement("canvas"); out.width = out.height = Math.max(256, s);
      var c = out.getContext("2d"); c.imageSmoothingEnabled = true; c.imageSmoothingQuality = "high"; c.drawImage(v.img, 0, 0, out.width, out.height);
      var a = v.ann, box = v.box; if (a && box) c.drawImage(a, box.x * (a.width / parseFloat(a.style.width)), box.y * (a.height / parseFloat(a.style.height)), box.s * (a.width / parseFloat(a.style.width)), box.s * (a.height / parseFloat(a.style.height)), 0, 0, out.width, out.height);
      out.toBlob(function (b) { var u = URL.createObjectURL(b), l = document.createElement("a"); l.href = u; l.download = "simulated_" + S.modality + "_" + v.key + ".png"; document.body.appendChild(l); l.click(); l.remove(); setTimeout(function () { URL.revokeObjectURL(u); }, 3000); });
    }

    /* ---------- open / close ---------- */
    function setOpen(on) {
      if (on === S.open) return;
      if (on) {
        try { if (G.NMSKUltrasound && G.NMSKUltrasound.isOpen()) G.NMSKUltrasound.close(); } catch (e) {}   // Q228: one split screen at a time
        build(); S.open = true; S.tab = "image"; applyLayout();
        if (ui.btn) ui.btn.setAttribute("aria-pressed", "true");
        setStatus("Loading tissue table ...");
        tablePromise.then(function () { if (S.open) openContinue(); });
      } else {
        S.open = false; clearInterval(polling); polling = null; setCine(false); applyLayout();
        if (ui.btn) ui.btn.setAttribute("aria-pressed", "false");
      }
    }
    var built2 = false;
    function build2() { if (built2 || !T) return; built2 = true; syncAll(); }
    function openContinue() {
      if (!T) { renderInfo(); setStatus(tableErr ? "tissue table missing: " + tableErr : "loading"); return; }
      build2(); renderInfo();
      if (!S.layoutTouched) { var small = Math.min(window.innerWidth, window.innerHeight) < 520 || window.innerHeight < 700; S.layout = small ? "single" : "mpr"; S.res = small ? 320 : 320; S.layoutTouched = true; root.classList.toggle("ctl-off", window.innerHeight < 500 && chooseLayout() === "tab"); ui.ctlBtn.setAttribute("aria-pressed", String(!root.classList.contains("ctl-off"))); }
      applyLayout(); syncAll();
      setStatus("Preparing geometry ...");
      buildGeometry(function (m) { setStatus(m); }).then(function () {
        geoState = "ready"; geoErr = ""; mappingReport(); setDiag();
        var hadCut = !!cutPlane();
        ensureCut(); lastCut = null;
        if (!hadCut && cutPlane()) { showHint("No cut was set, so an axial cut through the upper abdomen was created for you. Click or drag in any image to move it, or use the Cut panel of the 3D view, or the View → Oblique dial below for a tilted plane without orbiting the camera.", true); toast("CT / MRI: no cut was set – an axial cut through the upper abdomen was created.", 7000); }
        else showHint("Simulated CT / MRI of the cut plane (not a scan). Click or drag in an image to move the cut; Contrast, Slab (MIP / MinIP / thickness) and View (MPR / single / split, an Oblique tilt dial, and a cine ▶ with an fps speed control) are under the image.", false);
        var c = api.cut(); lastPlaneKey = c ? c.map(function (x) { return x.toFixed(4); }).join(",") : "off"; lastSlab = api.cutSlab ? api.cutSlab() : 0;
        if (!S.P) S.P = pickAnchor();
        movePointToPlane();
        if (lastSlab > 0.01) S.thick = Math.min(100, lastSlab);
        syncSlab();
        applyLayout();
        markDirty(null, true);
        clearInterval(polling); polling = setInterval(pollCut, 140);
        setStatus("");
      }, function (e) { geoErr = "geometry: " + (e && e.message || e); geoState = "error"; setDiag(); setStatus("Imaging unavailable: " + (e && e.message || e)); console.error(e); });
    }
    function pickAnchor() {
      var cp = cutPlane(), t = api.view().target.slice();
      if (geo && geo.bodyBox) {
        var lo = geo.bodyBox.lo, hi = geo.bodyBox.hi, inBox = [0, 1, 2].every(function (a) { return t[a] >= lo[a] && t[a] <= hi[a]; });
        if (!inBox) t = [(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2];
      }
      return t;
    }

    /* ---------- toolbar button ---------- */
    function addButton() {                                                   // always present: in the page's toolbar, else in the floating bar (Q239)
      var host = api.toolbar || floatBar();
      var btn = el("button", {type: "button", id: "t-imaging", title: BTN_TIP, "aria-pressed": "false", text: "CT / MRI", onclick: function () { setOpen(!S.open); }});
      var cut = document.getElementById("t-cut");
      if (cut && cut.parentNode === host) host.insertBefore(btn, cut.nextSibling); else host.appendChild(btn);
      btn.className = cut && host === api.toolbar ? cut.className : (api.kind === "webgl" ? "pill" : "tool");
      if (api.kind === "webgl") btn.textContent = "ct / mri";
      ui.btn = btn; setDiag();
    }
    addButton();
    /* ---------- debug / test API ---------- */
    G.NMSKImaging = {
      version: VERSION,
      open: function () { setOpen(true); }, close: function () { setOpen(false); },
      ready: function () { return tablePromise.then(function () { return buildGeometry(); }).then(function () { return true; }); },
      state: function () { return JSON.parse(JSON.stringify({open: S.open, modality: S.modality, seq: S.seq, thick: S.thick, slab: S.slab, layout: S.layout, active: S.active, P: S.P, fov: S.fov, res: S.res, win: [S.ctW, S.ctL], lay: chooseLayout(), oblique: S.obl, cine: S.cine, fps: S.fps})); },
      set: function (p) {
        Object.keys(p).forEach(function (k) {
          if (k === "thick") setThick(p.thick, true); else if (k === "seq") setSeq(p.seq); else if (k === "modality") setModality(p.modality);
          else if (k === "layout") setLayout(p.layout); else if (k === "slab") { S.slab = p.slab; syncSlab(); rerenderAll(); }
          else if (k === "ctWindow") { var w = T.ct_windows.filter(function (q) { return q.key === p.ctWindow; })[0]; if (w) { S.ctWin = w.key; S.ctW = w.width; S.ctL = w.level; syncCt(); rerenderAll(); } }
          else if (k === "P") { S.P = p.P.slice(); markDirty(null, false); } else if (k === "active") { S.active = p.active; syncAll(); markDirty(null, false); }
          else if (k === "fov") { Object.keys(p.fov).forEach(function (a) { S.fov[a] = p.fov[a]; }); syncAll(); markDirty(null, false); }
          else if (k === "res") { S.res = p.res; syncAll(); markDirty(null, false); }
          else if (k === "noise") { S.noise = p.noise; rerenderAll(); } else if (k === "blur") { S.blur = p.blur; rerenderAll(); } else if (k === "bias") { S.bias = p.bias; rerenderAll(); }
          else if (k === "ssCap") { S.ssCap = p.ssCap; markDirty(null, false); }
          else if (k === "tab") { S.tab = p.tab; applyLayout(); } else if (k === "lay") { S.lay = p.lay; applyLayout(); updateLayoutUI(); }
          else if (k === "seqParams") { Object.assign(S.sp, p.seqParams); syncMr(); rerenderAll(); }
          else if (k === "oblique") { Object.assign(S.obl, p.oblique); applyOblique(); }
          else if (k === "cine") { setCine(!!p.cine); } else if (k === "fps") { S.fps = p.fps; if (ui.cineFps) ui.cineFps.value = String(S.fps); if (S.cine) { setCine(false); setCine(true); } }
        });
      },
      idle: function () { return new Promise(function (res) { var t = setInterval(function () { var busy = pumping || Object.keys(views).some(function (k) { var v = views[k]; return v.dirty && visibleViews().indexOf(k) >= 0; }); if (!busy && Date.now() - lastMark > 900) { clearInterval(t); res(true); } }, 100); }); },
      views: function () { return views; },
      classOf: function (i) { return geo ? C.T.classes[geo.cls[i]].key : null; },
      geo: function () { return geo; }, table: function () { return T; }, C: function () { return C; },
      perf: function () { return perf; }, mapping: mappingReport,
      /* direct slice for tests: spec {O,n,offsets[],W,H,fov,center?} -> {labels:[Uint8Array], sid, px, cls names} */
      sliceNow: function (spec) {
        var b = basis(spec.n), W = spec.W || 256, H = spec.H || W, px = (spec.fov || 400) / W, cen = spec.center || spec.O;
        var rel = [cen[0] - spec.O[0], cen[1] - spec.O[1], cen[2] - spec.O[2]], cu = dot(b.u, rel), cv = dot(b.v, rel), u0 = cu - W * px / 2, v0 = cv + H * px / 2;
        var offs = spec.offsets || [0], key = "t" + (++msgSeq), out = {labels: [], fine: [], sid: null, ss: spec.ss > 1 ? spec.ss : 1}, k = 0;
        var ss = spec.ss > 1 ? spec.ss : 1, base = {key: key, ss: ss, W: W, H: H, O: spec.O, u: b.u, v: b.v, n: b.n, u0: u0, v0: v0, px: px, smin: Math.min.apply(null, offs), smax: Math.max.apply(null, offs), skinMm: T.bone_model.skin_thickness_mm, ids: C.ids, bone: boneParams()};
        function nxt() {
          if (k >= offs.length) { out.px = px; out.basis = b; out.u0 = u0; out.v0 = v0; return out; }
          return runSlice(Object.assign({}, base, {s: offs[k], wantSid: true})).then(function (r) { out.labels.push(r.lab); out.fine.push(r.fine || null); out.sid = r.sid; out.stats = r; k++; return nxt(); });
        }
        return buildGeometry().then(nxt);
      },
      lut: function (mod, seqKey) { if (mod === "ct") return Array.from(ctTable(C)); var sp = JSON.parse(JSON.stringify(T.mr_sequences.filter(function (q) { return q.key === seqKey; })[0])); return Array.from(mrTable(C, sp).sig); }
    };
    tablePromise = loadTable();
    /* Q228: services handed to companion add-ons (the ultrasound tool): the shared geometry package + worker, table, kernel parameters */
    shared = {
      lib: LIB, version: VERSION,
      loadJson: fetchJson, inline: inlineText, toast: toast, toolbarHost: function () { return api.toolbar || floatBar(); }, kind: api.kind,
      setUsDiag: function (ok, text, extra) { DIAG.ultrasound = Object.assign({ok: ok, text: text}, extra || {}); setBtnTip(document.getElementById("t-ultrasound"), US_TIP, ok, text); },
      ensure: function (progress) { return tablePromise.then(function () { if (tableErr || !C) throw new Error(tableErr || "tissue table missing"); return buildGeometry(progress); }).then(function () { return {geo: geo, C: C, T: T}; }); },
      runSlice: runSlice, boneParams: boneParams,
      isOpen: function () { return S.open; }, close: function () { setOpen(false); }
    };
    setTimeout(rescueButtons, 1500); setTimeout(rescueButtons, 5000);
    return shared;
  }
  var US_TIP = "Ultrasound: simulated B-mode from the meshes (not a scan)";

  /* companion add-ons (the ultrasound tool): the code pasted into the page (Q239) or the file beside it, loaded by a script tag, then by fetch + inline script
     (a host that refuses the file as a script still serves it as text); when none works the Ultrasound button is STILL there and says why (the public templates carry no extra line) */
  function loadCompanions(api, shared) {
    if (!shared) return;
    var name = "clinical_ultrasound_tool.js", done = false;
    function start(how) {
      if (done) return true;
      if (!(G.NMSKUltrasoundAddon && typeof G.NMSKUltrasoundAddon.attach === "function")) return false;
      done = true;
      try { G.NMSKUltrasoundAddon.attach(api, shared); } catch (e) { console.error("ultrasound add-on failed to start; imaging unaffected:", e); fail("start-up error: " + (e && e.message || e)); }
      return true;
    }
    function fail(reason) {
      done = true;
      var text = "Ultrasound tool: NOT available – " + reason;
      shared.setUsDiag(false, text);
      if (document.getElementById("t-ultrasound")) return;
      var host = shared.toolbarHost(), cut = document.getElementById("t-imaging") || document.getElementById("t-cut"), b = document.createElement("button");
      b.type = "button"; b.id = "t-ultrasound"; b.textContent = shared.kind === "webgl" ? "ultrasound" : "Ultrasound"; b.title = text;
      b.className = cut && cut.parentNode === host ? cut.className : (shared.kind === "webgl" ? "pill" : "tool");
      if (cut && cut.parentNode === host) host.insertBefore(b, cut.nextSibling); else host.appendChild(b);
      b.style.opacity = "0.7"; b.setAttribute("data-diag", "bad");
      b.addEventListener("click", function () { shared.toast(text, 12000); });
    }
    if (start("inline")) return;
    function viaText(why) {
      fetchText(name).then(function (src) {
        if (/^\s*</.test(src)) throw new Error("the host answered with a web page instead of the file");
        var sc = document.createElement("script"); sc.text = src; document.head.appendChild(sc);
        if (!start("text")) fail("file loaded but it defines no ultrasound tool (placeholder or wrong file?)");
      }).catch(function (e) { fail(name + ": " + why + "; " + (e && e.message || e)); });
    }
    try {
      var sc = document.createElement("script");
      sc.src = SCRIPT_BASE + name; sc.async = true;
      sc.onload = function () { try { if (!start("file")) viaText("script loaded but defines no ultrasound tool"); } catch (e) { fail(String(e && e.message || e)); } };
      sc.onerror = function () { viaText("script tag refused or not found"); };
      document.head.appendChild(sc);
    } catch (e) { viaText("could not add a script tag: " + (e && e.message || e)); }
  }
  /* one click handler slot in the page API: keep the needle add-on's handler and let companions go first while they are armed */
  var clickers = [], legacyClick = null, dispatcherOn = false;
  function installClickDispatcher(api) {
    if (dispatcherOn || typeof api.setClickHandler !== "function") return;
    var orig = api.setClickHandler;
    api.setClickHandler = function (fn) { legacyClick = fn || null; };
    orig.call(api, function (e) {
      for (var i = 0; i < clickers.length; i++) { var r = false; try { r = clickers[i](e); } catch (err) { console.error(err); } if (r) return true; }
      return legacyClick ? legacyClick(e) : false;
    });
    dispatcherOn = true;
  }

  /* ========================================================================================================
   * 5. ATTACH -- chain onto the (optional) needle add-on
   * ====================================================================================================== */
  var prev = G.NMSKClinical, chained = Object.assign({}, prev || {});
  chained.attach = function (api) {
    var r = null, sh = null;
    installClickDispatcher(api);
    if (prev && typeof prev.attach === "function") { try { r = prev.attach(api); } catch (e) { console.error("needle add-on failed to start:", e); } }
    try { sh = attachImaging(api); } catch (e2) {
      console.error("imaging add-on failed to start; anatomy viewer unaffected:", e2);
      var msg = "Imaging tool: NOT ready – start-up error: " + (e2 && e2.message || e2); DIAG.imaging = {ok: false, text: msg};
      try { var fb = document.createElement("button"); fb.type = "button"; fb.id = "t-imaging"; fb.textContent = "CT / MRI"; fb.title = msg; fb.className = api.kind === "webgl" ? "pill" : "tool"; fb.style.opacity = "0.7"; (api.toolbar || floatBar()).appendChild(fb); fb.addEventListener("click", function () { toast(msg, 12000); }); } catch (e3) {}
    }
    if (sh) { sh.addClickHandler = function (fn) { clickers.push(fn); }; sh.api = api; }
    loadCompanions(api, sh);
    return r;
  };
  chained.imaging = VERSION;
  G.NMSKClinical = chained;
})(typeof window !== "undefined" ? window : globalThis);
