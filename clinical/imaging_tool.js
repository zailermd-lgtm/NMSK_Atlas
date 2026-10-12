/* NMSK Atlas -- PRIVATE clinical layer (clinical/LICENSE_PRIVATE.md): IMAGING mode, phase 1 = CT + MRI simulation (Q226).
 *
 * Staged beside a viewer page as clinical_imaging_tool.js (+ clinical_imaging_tissues.json) by
 * scripts/clinical/stage_clinical_files.py. The public pages only carry a generic <script> hook; without this file they are
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
  var VERSION = "q226.1";

  /* ========================================================================================================
   * 1. KERNEL -- self-contained (no outer references): its source text is evaluated inside a Worker.
   * ====================================================================================================== */
  function KERNEL_FACTORY() {
    var Gm = null, cacheKey = null, cand = [], VX = new Float32Array(0), VY = new Float32Array(0), VD = new Float32Array(0);
    var vOff = null, sdmin = null, sdmax = null, segs = new Float32Array(1 << 16), xs = new Float32Array(1 << 16);
    var rowCnt = new Int32Array(0), rowPtr = new Int32Array(0), axisInfo = null, M = new Uint8Array(0), DTb = new Uint16Array(0);
    var bx0 = 0, bx1 = -1, by0 = 0, by1 = -1, parityBad = 0, triCount = 0;
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
      var prevN = -1, prevRow = -2, sp;
      for (j = 0; j < H; j++) {
        var n = cur[j], base = rowPtr[j], e, i, v;
        if (n === 0) { prevN = 0; prevRow = j; continue; }
        for (i = 1; i < n; i++) { v = xs[base + i]; e = i - 1; while (e >= 0 && xs[base + e] > v) { xs[base + e + 1] = xs[base + e]; e--; } xs[base + e + 1] = v; }
        var npair;
        if (n & 1) {
          parityBad++;
          if (prevRow === j - 1 && prevN > 0) {                             // repeat the previous row's spans
            for (sp = 0; sp < prevN; sp += 2) paintSpan(prevSp[sp], prevSp[sp + 1], j, W, m);
          }
          prevRow = -2; prevN = -1;
          continue;
        }
        if (n > prevSp.length) prevSp = new Float64Array(n * 2);
        for (sp = 0; sp < n; sp += 2) { prevSp[sp] = xs[base + sp]; prevSp[sp + 1] = xs[base + sp + 1]; paintSpan(prevSp[sp], prevSp[sp + 1], j, W, m); }
        prevN = n; prevRow = j;
      }
    }
    function paintSpan(a, b, j, W, m) {
      var i0 = Math.ceil(a - 0.5), i1 = Math.ceil(b - 0.5) - 1;
      if (i0 < 0) i0 = 0; if (i1 > W - 1) i1 = W - 1;
      if (i1 < i0) return;
      m.fill(1, j * W + i0, j * W + i1 + 1);
      if (i0 < bx0) bx0 = i0; if (i1 > bx1) bx1 = i1; if (j < by0) by0 = j; if (j > by1) by1 = j;
    }
    function drawLabel(ns, W, H, lab, sid, cls, st) {
      for (var k = 0; k < ns; k++) {
        var x0 = segs[4 * k], y0 = segs[4 * k + 1], x1 = segs[4 * k + 2], y1 = segs[4 * k + 3];
        var len = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)), n = Math.ceil(len * 2) + 1, q;
        for (q = 0; q <= n; q++) {
          var f = n ? q / n : 0, xi = Math.floor(x0 + (x1 - x0) * f), yi = Math.floor(y0 + (y1 - y0) * f);
          if (xi >= 0 && xi < W && yi >= 0 && yi < H) { lab[yi * W + xi] = cls; if (sid) sid[yi * W + xi] = st; }
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
      var t0 = Date.now(), g = Gm, W = R.W, H = R.H, N = W * H, px = R.px, s = R.s, i, j, k;
      parityBad = 0; triCount = 0;
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
        M.fill(0, 0, N);
        fillMask(sk, W, H, M);
        for (k = 0; k < N; k++) body[k] = M[k];
        drawOutline(sk, W, H, body);
      }
      /* the other structures in paint order (sheets are drawn after the solids) */
      for (i = 0; i < cand.length; i++) {
        var st3 = cand[i];
        if (g.skin[st3] || (g.render && g.render[st3] === 1)) continue;
        if (s < sdmin[st3] || s >= sdmax[st3]) continue;
        var n3 = collect(st3, s); if (!n3) continue;
        nCand++; nSeg += n3;
        M.fill(0, 0, N);
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
      }
      for (i = 0; i < cand.length; i++) {                                   // thin sheets (fascia, septa, capsules, dura): a one-pixel line, never a filled volume
        var st4 = cand[i];
        if (!g.render || g.render[st4] !== 1 || g.skin[st4]) continue;
        if (s < sdmin[st4] || s >= sdmax[st4]) continue;
        var n4 = collect(st4, s); if (!n4) continue;
        nCand++; nSeg += n4;
        drawLabel(n4, W, H, lab, sid, g.cls[st4], st4);
      }
      /* body = skin fill + outline + everything painted; exterior = flood from the border over the rest */
      for (k = 0; k < N; k++) if (lab[k] !== 255) body[k] = 1;
      var ext = new Uint8Array(N), stack = new Int32Array(N), sp2 = 0;
      for (i = 0; i < W; i++) { if (!body[i]) { ext[i] = 1; stack[sp2++] = i; } var bi = (H - 1) * W + i; if (!body[bi] && !ext[bi]) { ext[bi] = 1; stack[sp2++] = bi; } }
      for (j = 1; j < H - 1; j++) { var l0 = j * W, r0 = j * W + W - 1; if (!body[l0] && !ext[l0]) { ext[l0] = 1; stack[sp2++] = l0; } if (!body[r0] && !ext[r0]) { ext[r0] = 1; stack[sp2++] = r0; } }
      while (sp2) {
        var p = stack[--sp2], xx = p % W, yy = (p - xx) / W, nb;
        if (xx > 0) { nb = p - 1; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
        if (xx < W - 1) { nb = p + 1; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
        if (yy > 0) { nb = p - W; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
        if (yy < H - 1) { nb = p + W; if (!body[nb] && !ext[nb]) { ext[nb] = 1; stack[sp2++] = nb; } }
      }
      for (k = 0; k < N; k++) if (lab[k] === 255) lab[k] = ext[k] ? ids.air : ids.fat;
      var bodyPx = 0;
      if (R.skinMm > 0 && sk) {                                             // thin skin rim = body pixels within skinMm of the exterior
        var D = DTb.length >= N ? DTb : (DTb = new Uint16Array(N));
        for (k = 0; k < N; k++) D[k] = ext[k] ? 0 : 65000;
        chamfer(D, W, H);
        var thr = Math.max(R.skinMm, px) / px * 3;
        for (k = 0; k < N; k++) if (!ext[k]) { bodyPx++; if (D[k] <= thr) { lab[k] = ids.skin; if (sid) sid[k] = 65534; } }
      }
      return {lab: lab, sid: sid, ms: Date.now() - t0, nCand: nCand, nSeg: nSeg, tris: triCount, parityBad: parityBad, bodyPx: bodyPx, badSt: badSt};
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
          if (dmm <= Math.max(tc, 0.5 * px)) c = ids.cort; else if (P.canal && w > 0.5) c = ids.marrow; else c = ids.canc;
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

  /* ---- node test hook ---- */
  if (typeof document === "undefined") {
    G.NMSKImagingLib = {KERNEL_FACTORY: KERNEL_FACTORY, compileTable: compileTable, classify: classify, mrTable: mrTable, ctTable: ctTable, basis: basis, dirLabel: dirLabel, VERSION: VERSION};
    return;
  }

  /* ========================================================================================================
   * 3 + 4 + 5. ENGINE, UI, ATTACH (browser only)
   * ====================================================================================================== */
  var SCRIPT_BASE = (function () {
    try { var cs = document.currentScript; if (cs && cs.src) return cs.src.replace(/[^\/]*$/, ""); } catch (e) {}
    return "";
  })();

  function attachImaging(api) {
    var C = null, T = null, tableErr = null;
    var geo = null, geoState = "idle", kernelLocal = null, worker = null, workerOk = true, jobCb = null, msgSeq = 0;
    var perf = {last: null, history: []};
    var S = {
      open: false, modality: "ct", ctWin: "soft", ctW: 400, ctL: 40, seq: "t1_se", sp: null, mrW: 1, mrL: 0.5, auto: true,
      thick: 5, slab: "avg", layout: "mpr", active: "cut", fov: {cut: 450, ax: 450, co: 700, sa: 700}, res: 320,
      P: null, noise: 0, blur: 0, cross: true, labels: true, tab: "image", lay: "auto", link: false
    };
    var views = {};
    var VIEWS = [["cut", "Cut plane"], ["ax", "Axial"], ["co", "Coronal"], ["sa", "Sagittal"]];
    var root = null, ui = {}, polling = null, lastPlaneKey = "", timers = {}, lastMark = 0, tablePromise = null;
    var lastCut = null, lastSlab = 0;

    /* ---------- table ---------- */
    function loadTable() {
      return fetch(SCRIPT_BASE + "clinical_imaging_tissues.json", {cache: "no-cache"}).then(function (r) { if (!r.ok) throw new Error("clinical_imaging_tissues.json: HTTP " + r.status); return r.json(); })
        .then(function (t) { T = t; C = compileTable(t); S.sp = JSON.parse(JSON.stringify(t.mr_sequences.filter(function (q) { return q.key === S.seq; })[0])); })
        .catch(function (e) { tableErr = String(e && e.message || e); });
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
        var payload = {n: g.n, pos: g.pos, idx: g.idx, vStart: g.vStart, tStart: g.tStart, bbox: g.bbox, cls: g.cls, kind: g.kind, skin: g.skin, render: g.render, order: g.order, skinList: g.skinList};
        function local() {
          workerOk = false; worker = null;
          kernelLocal = KERNEL_FACTORY()
          kernelLocal.setGeometry(payload);
          resolve();
        }
        try {
          var src = "var K=(" + KERNEL_FACTORY.toString() + ")();onmessage=function(e){var m=e.data;if(m.type==='init'){K.setGeometry(m.g);postMessage({type:'ready'});}else if(m.type==='slice'){var r;try{r=K.slice(m.R);}catch(err){postMessage({type:'error',id:m.id,msg:String(err&&err.stack||err)});return;}var tr=[r.lab.buffer];if(r.sid)tr.push(r.sid.buffer);postMessage({type:'slice',id:m.id,r:r},tr);}};";
          var url = URL.createObjectURL(new Blob([src], {type: "application/javascript"}));
          worker = new Worker(url);
          var t = setTimeout(function () { if (!worker) return; try { worker.terminate(); } catch (e) {} local(); }, 8000);
          worker.onmessage = function (e) {
            var m = e.data;
            if (m.type === "ready") { clearTimeout(t); resolve(); return; }
            if (jobCb) jobCb(m);
          };
          worker.onerror = function (e) { if (geoState === "loading") { clearTimeout(t); try { worker.terminate(); } catch (e2) {} local(); } else console.error("imaging worker:", e && e.message); };
          worker.postMessage({type: "init", g: payload});                    // copies (structured clone): the page keeps its own arrays
        } catch (e) { local(); }
      });
    }
    function runSlice(R) {                                                  // -> Promise(result)
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
      var maxN = tier === 0 ? 5 : (S.layout === "mpr" ? 25 : 49), n = Math.max(2, Math.min(maxN, Math.ceil(th / 1.0) + 1)), out = [], k;
      for (k = 0; k < n; k++) out.push(spec.lo + (spec.hi - spec.lo) * k / (n - 1));
      return out;
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
      var base = {key: key, W: W, H: H, O: spec.O, u: spec.u, v: spec.v, n: spec.n, u0: u0, v0: v0, px: px, smin: Math.min.apply(null, offs), smax: Math.max.apply(null, offs), skinMm: T.bone_model.skin_thickness_mm, ids: C.ids,
        bone: boneParams()};
      var mid = Math.floor((offs.length - 1) / 2), labels = [], t0 = Date.now(), sidMid = null, st = {nCand: 0, tris: 0, parityBad: 0, ms: 0}, k = 0;
      setStatus("Computing " + v.label + " ...");
      function next() {
        if (v.gen !== gen) return Promise.resolve("stale");                  // superseded: stop between sub-slices
        if (k >= offs.length) return Promise.resolve("done");
        var R = Object.assign({}, base, {s: offs[k], wantSid: k === mid});
        return runSlice(R).then(function (r) {
          labels.push(r.lab); if (k === mid) sidMid = r.sid;
          st.nCand = Math.max(st.nCand, r.nCand); st.tris += r.tris; st.parityBad += r.parityBad; st.ms += r.ms; k++;
          if (k === 1 || k === offs.length || tier === 0) { v.labels = labels.slice(); v.sid = sidMid; v.mid = Math.min(mid, labels.length - 1); v.W = W; v.H = H; v.spec = spec; v.offs = offs.slice(0, labels.length); v.px = px; v.cu = cu; v.cv = cv; v.partial = k < offs.length; renderView(v); }
          return next();
        });
      }
      return next().then(function (res2) {
        if (res2 === "done") {
          v.labels = labels; v.sid = sidMid; v.mid = mid; v.W = W; v.H = H; v.spec = spec; v.offs = offs; v.px = px; v.cu = cu; v.cv = cv; v.partial = false;
          v.dirty = v.gen !== gen; v.tierDone = tier; v.stats = {ms: Date.now() - t0, kernelMs: st.ms, sub: offs.length, cand: st.nCand, tris: st.tris, parityBad: st.parityBad, W: W, tier: tier};
          perf.last = {view: v.key, ms: v.stats.ms, sub: offs.length, W: W, tier: tier, cand: st.nCand, parityBad: st.parityBad}; perf.history.push(perf.last); if (perf.history.length > 60) perf.history.shift();
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
    function combine(v) {
      var lut = currentLut().lut, N = v.W * v.H, nS = v.labels.length, out = new Float32Array(N), s, k;
      if (nS === 1 || S.thick <= 0.01) { var L0 = v.labels[Math.min(v.mid, nS - 1)]; for (k = 0; k < N; k++) out[k] = lut[L0[k]]; return out; }
      if (S.slab === "avg") { for (s = 0; s < nS; s++) { var Ls = v.labels[s]; for (k = 0; k < N; k++) out[k] += lut[Ls[k]]; } var inv = 1 / nS; for (k = 0; k < N; k++) out[k] *= inv; }
      else if (S.slab === "mip") { out.fill(-1e9); for (s = 0; s < nS; s++) { var Lm = v.labels[s]; for (k = 0; k < N; k++) { var a = lut[Lm[k]]; if (a > out[k]) out[k] = a; } } }
      else { out.fill(1e9); for (s = 0; s < nS; s++) { var Ln = v.labels[s]; for (k = 0; k < N; k++) { var b = lut[Ln[k]]; if (b < out[k]) out[k] = b; } } }
      return out;
    }
    var seed = 12345;
    function rnd() { seed ^= seed << 13; seed ^= seed >>> 17; seed ^= seed << 5; return ((seed >>> 0) + 0.5) / 4294967296; }
    function gauss() { return Math.sqrt(-2 * Math.log(rnd())) * Math.cos(6.283185307 * rnd()); }
    function blurImg(a, W, H, sg) {
      var r = Math.max(1, Math.ceil(sg * 3)), ker = new Float32Array(2 * r + 1), s = 0, i, x, y;
      for (i = -r; i <= r; i++) { ker[i + r] = Math.exp(-i * i / (2 * sg * sg)); s += ker[i + r]; }
      for (i = 0; i < ker.length; i++) ker[i] /= s;
      var tmp = new Float32Array(a.length), out = new Float32Array(a.length);
      for (y = 0; y < H; y++) for (x = 0; x < W; x++) { var acc = 0; for (i = -r; i <= r; i++) { var xx = Math.min(W - 1, Math.max(0, x + i)); acc += a[y * W + xx] * ker[i + r]; } tmp[y * W + x] = acc; }
      for (y = 0; y < H; y++) for (x = 0; x < W; x++) { var ac = 0; for (i = -r; i <= r; i++) { var yy = Math.min(H - 1, Math.max(0, y + i)); ac += tmp[yy * W + x] * ker[i + r]; } out[y * W + x] = ac; }
      return out;
    }
    function renderView(v) {
      if (!v.img || !v.labels.length) return;
      var W = v.W, H = v.H, N = W * H, val = combine(v), k;
      if (S.blur > 0) val = blurImg(val, W, H, S.blur / v.px);
      if (S.noise > 0) {
        var sg = S.modality === "ct" ? S.noise : S.noise / 100;             // CT: HU; MR: fraction of the reference signal
        if (S.modality === "ct") for (k = 0; k < N; k++) val[k] += sg * gauss();
        else for (k = 0; k < N; k++) { var n1 = sg * gauss(), n2 = sg * gauss(); val[k] = Math.sqrt((val[k] + n1) * (val[k] + n1) + n2 * n2); }
      }
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
        if (S.noise > 0 || S.blur > 0) txt("synthetic " + (S.noise > 0 ? "noise " : "") + (S.blur > 0 ? "blur" : ""), box.x + 8, box.y + 52, "left", "#ff9d8a");
      }
      txt("SIMULATED – NOT A SCAN", box.x + box.s - 8, box.y + box.s - 10, "right", "#ff9d8a");
    }
    function imgBox(v, cw, ch) { var s = Math.min(cw, ch); return {x: (cw - s) / 2, y: (ch - s) / 2, s: s}; }
    function pixelOf(v, p) {                                                // 3D point -> pixel (float) of the view's image
      var sp = v.spec, rel = [p[0] - sp.O[0], p[1] - sp.O[1], p[2] - sp.O[2]];
      var uu = dot(sp.u, rel), vv = dot(sp.v, rel), u0 = v.cu - v.W * v.px / 2, v0 = v.cv + v.H * v.px / 2;
      return [(uu - u0) / v.px, (v0 - vv) / v.px];
    }
    function pointOf(v, ix, iy, along) {                                    // pixel -> 3D point on the plane (+ along n)
      var sp = v.spec, u0 = v.cu - v.W * v.px / 2, v0 = v.cv + v.H * v.px / 2, uu = u0 + ix * v.px, vv = v0 - iy * v.px;
      return [sp.O[0] + sp.u[0] * uu + sp.v[0] * vv + sp.n[0] * (along || 0), sp.O[1] + sp.u[1] * uu + sp.v[1] * vv + sp.n[1] * (along || 0), sp.O[2] + sp.u[2] * uu + sp.v[2] * vv + sp.n[2] * (along || 0)];
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
      ".img-view canvas{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%)}",
      ".img-view .ann{pointer-events:none}",
      "#img-root.ctl-off .img-ctl{display:none}",
      ".img-ctl .sec{display:contents}.img-ctl .sectabs{display:none;gap:4px}.img-ctl .modrow{grid-column:1/-1}",
      "#img-root.ctl-tabs .img-ctl{grid-template-columns:1fr;max-height:42%}",
      "#img-root.ctl-tabs .sectabs{display:flex}",
      "#img-root.ctl-tabs .sec{display:grid;gap:6px}",
      "#img-root.ctl-tabs .sec:not(.act){display:none}",
      ".img-ctl{flex:0 0 auto;max-height:46%;overflow:auto;padding:6px 8px 8px;border-top:1px solid var(--line);display:grid;gap:6px 14px;background:var(--bg);grid-template-columns:repeat(auto-fit,minmax(380px,1fr));align-content:start}",
      ".img-ctl>.img-status{grid-column:1/-1}",
      "body.img-tab .img-ctl{max-height:44%}",
      ".img-row{display:flex;gap:5px;align-items:center;flex-wrap:wrap}",
      ".img-row label{color:var(--dim);font-size:12px}",
      ".img-row .grow{flex:1 1 120px;min-width:90px}",
      ".img-read{font:12px/1.3 ui-monospace,Menlo,monospace;color:#cfe6ff;min-height:32px;padding:3px 8px;border-top:1px solid var(--line);flex:0 0 auto;word-break:break-word;max-height:3.9em;overflow:hidden}",
      ".img-status{color:var(--dim);font-size:11.5px}",
      ".img-info{position:absolute;inset:36px 0 0 0;background:var(--bg);z-index:5;overflow:auto;padding:10px 12px 40px;display:none}",
      ".img-info.show{display:block}",
      ".img-info h3{margin:14px 0 4px;font-size:14px}.img-info p,.img-info li{color:#c3cfdd}",
      ".img-info table{border-collapse:collapse;width:100%;font-size:11.5px;margin:4px 0}.img-info td,.img-info th{border:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}",
      ".img-info .st-verified_abstract{color:#7fe0a0}.img-info .st-secondary_checked{color:#d9e58a}.img-info .st-recalled_unverified{color:#ffb38a}.img-info .st-derived{color:#9fd0ff}.img-info .st-assumption{color:#c9b8ff}",
      "#img-tab3d{position:fixed;z-index:90;right:8px;top:8px;display:none;gap:4px}",
      "body.nmsk-img.img-tab.img-t3d #img-tab3d{display:flex}",
      "#img-tab3d button{background:#161d27;color:#e6edf5;border:1px solid #2a3646;border-radius:999px;padding:6px 12px;min-height:34px;font:600 13px system-ui}",
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
      root.appendChild(div); root.appendChild(head); root.appendChild(ui.info); root.appendChild(ui.views); root.appendChild(ui.read); root.appendChild(ctl);
      document.body.appendChild(root);
      var tabs = el("div", {id: "img-tab3d"}, [el("button", {type: "button", text: "3D", "aria-pressed": "true"}), el("button", {type: "button", text: "Image ▸", onclick: function () { S.tab = "image"; applyLayout(); pumpAfterShow(); }})]);
      document.body.appendChild(tabs); ui.tabs = tabs;
      /* in tab layout, the panel header gets a 3D button */
      head.insertBefore(ui.to3d = el("button", {type: "button", text: "◂ 3D", title: "Back to the 3D model", onclick: function () { S.tab = "3d"; applyLayout(); }}), head.children[1]);
      window.addEventListener("resize", function () { if (S.open && !firing) { applyLayout(); updateLayoutUI(); } });
      renderInfo();
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
      ui.optRow = el("div", {class: "img-row"}, [
        el("label", {text: "Noise"}), (ui.noise = el("input", {type: "range", min: "0", max: "10", step: "0.5", class: "grow", "aria-label": "Synthetic noise (default off)", oninput: function () { S.noise = +ui.noise.value * (S.modality === "ct" ? 5 : 1); ui.noiseOut.textContent = S.noise ? "synthetic noise" : "off"; rerenderAll(); }})), (ui.noiseOut = el("output", {text: "off"})),
        el("label", {text: "Blur"}), (ui.blur = el("input", {type: "range", min: "0", max: "4", step: "0.25", class: "grow", "aria-label": "Synthetic blur in mm (default off)", oninput: function () { S.blur = +ui.blur.value; ui.blurOut.textContent = S.blur ? S.blur + " mm" : "off"; rerenderAll(); }})), (ui.blurOut = el("output", {text: "off"})),
        (ui.crossBtn = el("button", {type: "button", text: "crosshair", "aria-pressed": "true", onclick: function () { S.cross = !S.cross; ui.crossBtn.setAttribute("aria-pressed", String(S.cross)); rerenderAll(); }})),
        (ui.lblBtn = el("button", {type: "button", text: "labels", "aria-pressed": "true", onclick: function () { S.labels = !S.labels; ui.lblBtn.setAttribute("aria-pressed", String(S.labels)); rerenderAll(); }}))
      ]);
      ui.status = el("div", {class: "img-status", text: ""});
      function sec(name, kids) { var d = el("div", {class: "sec", "data-sec": name}, kids); ui.secs[name] = d; return d; }
      ui.secs = {};
      [mrow, sec("contrast", [ui.ctBox, ui.mrBox]), sec("slab", [ui.slabRow]), sec("view", [r1, ui.fovRow]), sec("more", [ui.optRow]), ui.status].forEach(function (x) { ctl.appendChild(x); });
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
    function setStatus(t) {
      if (!ui.status) return;
      if (t) ui.status.textContent = t;
      else {
        var p = perf.last; ui.status.textContent = p ? (p.view + ": " + p.ms + " ms, " + p.sub + " sub-slice" + (p.sub > 1 ? "s" : "") + ", " + p.W + "²" + (p.parityBad ? ", " + p.parityBad + " open-mesh rows repaired" : "")) : "";
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
        drag = {mode: "cross", v: v}; if (inside) setAnchorFromView(v, q[0], q[1]);
        showReadout(v, q);
      } else if (kind === "move") {
        touches[e.pointerId] && (touches[e.pointerId] = [e.clientX, e.clientY]);
        if (drag && drag.mode === "pinch" && Object.keys(touches).length >= 2) { var f = drag.d0 / Math.max(10, pinchDist()); S.fov[drag.v.key] = Math.max(60, Math.min(2400, drag.f0 * f)); markDirty([drag.v.key], true); return; }
        if (drag && drag.mode === "pan") {
          var r = v.wrap.getBoundingClientRect(), s = Math.min(r.width, r.height), mm = S.fov[v.key] / s, dx = (e.clientX - drag.x) * mm, dy = (e.clientY - drag.y) * mm, sp = v.spec;
          v.CP = [drag.cp[0] - sp.u[0] * dx + sp.v[0] * dy, drag.cp[1] - sp.u[1] * dx + sp.v[1] * dy, drag.cp[2] - sp.u[2] * dx + sp.v[2] * dy];
          markDirty([v.key], true); return;
        }
        if (drag && drag.mode === "cross" && drag.v === v && inside) setAnchorFromView(v, q[0], q[1]);
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
    function setAnchorFromView(v, ix, iy) {
      var along = 0, p = pointOf(v, ix, iy, along);
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
      box.appendChild(el("p", {html: "<b>A simulation computed from this viewer's segmented anatomical meshes – not a scan.</b> The cut plane (and slab) is intersected with every mesh, each pixel gets the tissue class of the top-most structure, and CT numbers / MRI signal come from the table below. Reconstruction, noise, artefacts, motion, contrast kinetics and disease are not simulated unless a control says so (noise and blur are off by default and clearly synthetic)."}));
      var ul = el("ul"); T.honesty.forEach(function (h) { ul.appendChild(el("li", {text: h})); }); box.appendChild(ul);
      box.appendChild(el("h3", {text: "Geometry assumptions"}));
      var ul2 = el("ul");
      ["Only the outer surface of each structure exists. Cortical vs cancellous bone and the medullary canal are MODELLED from the slice (" + T.bone_model.note + ")",
       "Space inside the skin that no structure covers: " + T.baseline.note,
       "Thin skin rim: " + T.bone_model.skin_note + ". Meshes with open surfaces can leave a few mis-filled scan lines; they are repaired from the line above and counted in the status line.",
       "All structures are included whatever the visibility toggles of the 3D view say.",
       "Slab = sub-slices at <= 1 mm (adaptive for thick slabs and while dragging) combined as average (thick MPR), MIP or MinIP. Orthogonal views use a slab of the same thickness centred on the crosshair; the cut-plane view uses the kept slab behind the plane."].forEach(function (t) { ul2.appendChild(el("li", {text: t})); });
      box.appendChild(ul2);
      box.appendChild(el("h3", {text: "Tissue table (" + T.classes.length + " classes) - status colour: green verified in an abstract, yellow secondary source, orange recalled/UNVERIFIED, blue derived, purple assumption"}));
      var tb = el("table"); tb.appendChild(el("tr", {html: "<th>class</th><th>HU</th><th>CT status</th><th>MRI 1.5 T (PD, T1, T2 ms)</th><th>MRI status</th><th>sources</th>"}));
      T.classes.forEach(function (c) {
        var m = c.mri.pools.map(function (p) { return (c.mri.pools.length > 1 ? Math.round(p.frac * 100) + "%: " : "") + p.pd + ", " + p.t1 + ", " + p.t2; }).join(" + ");
        var srcs = (c.ct.src || []).concat(c.mri.src || []).filter(function (x, i, a) { return a.indexOf(x) === i; }).map(function (k) { var rf = T.references[k]; return rf ? (rf.pmid ? "PMID " + rf.pmid : k) : k; }).join(", ");
        tb.appendChild(el("tr", {html: "<td>" + c.label + "</td><td>" + c.ct.hu + " (" + c.ct.range[0] + ".." + c.ct.range[1] + ")</td><td class='st-" + c.ct.status + "'>" + c.ct.status + "</td><td>" + m + "</td><td class='st-" + c.mri.status + "'>" + c.mri.status + "</td><td>" + srcs + "</td>"}));
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
      var c = out.getContext("2d"); c.imageSmoothingEnabled = true; c.drawImage(v.img, 0, 0, out.width, out.height);
      var a = v.ann, box = v.box; if (a && box) c.drawImage(a, box.x * (a.width / parseFloat(a.style.width)), box.y * (a.height / parseFloat(a.style.height)), box.s * (a.width / parseFloat(a.style.width)), box.s * (a.height / parseFloat(a.style.height)), 0, 0, out.width, out.height);
      out.toBlob(function (b) { var u = URL.createObjectURL(b), l = document.createElement("a"); l.href = u; l.download = "simulated_" + S.modality + "_" + v.key + ".png"; document.body.appendChild(l); l.click(); l.remove(); setTimeout(function () { URL.revokeObjectURL(u); }, 3000); });
    }

    /* ---------- open / close ---------- */
    function setOpen(on) {
      if (on === S.open) return;
      if (on) {
        build(); S.open = true; S.tab = "image"; applyLayout();
        if (ui.btn) ui.btn.setAttribute("aria-pressed", "true");
        setStatus("Loading tissue table ...");
        tablePromise.then(function () { if (S.open) openContinue(); });
      } else {
        S.open = false; clearInterval(polling); polling = null; applyLayout();
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
        geoState = "ready"; mappingReport();
        ensureCut(); lastCut = null;
        var c = api.cut(); lastPlaneKey = c ? c.map(function (x) { return x.toFixed(4); }).join(",") : "off"; lastSlab = api.cutSlab ? api.cutSlab() : 0;
        if (!S.P) S.P = pickAnchor();
        movePointToPlane();
        if (lastSlab > 0.01) S.thick = Math.min(100, lastSlab);
        syncSlab();
        applyLayout();
        markDirty(null, true);
        clearInterval(polling); polling = setInterval(pollCut, 140);
        setStatus("");
      }, function (e) { setStatus("Imaging unavailable: " + (e && e.message || e)); console.error(e); });
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
    function addButton() {
      var host = api.toolbar; if (!host) return;
      var btn = el("button", {type: "button", id: "t-imaging", title: "Imaging: simulated CT and MRI of the cut plane (not a scan)", "aria-pressed": "false", text: "Imaging", onclick: function () { setOpen(!S.open); }});
      var cut = document.getElementById("t-cut");
      if (cut && cut.parentNode === host) host.insertBefore(btn, cut.nextSibling); else host.appendChild(btn);
      btn.className = cut ? cut.className : (api.kind === "webgl" ? "pill" : "tool");
      if (api.kind === "webgl") btn.textContent = "imaging";
      ui.btn = btn;
    }
    addButton();
    /* ---------- debug / test API ---------- */
    G.NMSKImaging = {
      version: VERSION,
      open: function () { setOpen(true); }, close: function () { setOpen(false); },
      ready: function () { return tablePromise.then(function () { return buildGeometry(); }).then(function () { return true; }); },
      state: function () { return JSON.parse(JSON.stringify({open: S.open, modality: S.modality, seq: S.seq, thick: S.thick, slab: S.slab, layout: S.layout, active: S.active, P: S.P, fov: S.fov, res: S.res, win: [S.ctW, S.ctL], lay: chooseLayout()})); },
      set: function (p) {
        Object.keys(p).forEach(function (k) {
          if (k === "thick") setThick(p.thick, true); else if (k === "seq") setSeq(p.seq); else if (k === "modality") setModality(p.modality);
          else if (k === "layout") setLayout(p.layout); else if (k === "slab") { S.slab = p.slab; syncSlab(); rerenderAll(); }
          else if (k === "ctWindow") { var w = T.ct_windows.filter(function (q) { return q.key === p.ctWindow; })[0]; if (w) { S.ctWin = w.key; S.ctW = w.width; S.ctL = w.level; syncCt(); rerenderAll(); } }
          else if (k === "P") { S.P = p.P.slice(); markDirty(null, false); } else if (k === "active") { S.active = p.active; syncAll(); markDirty(null, false); }
          else if (k === "fov") { Object.keys(p.fov).forEach(function (a) { S.fov[a] = p.fov[a]; }); syncAll(); markDirty(null, false); }
          else if (k === "res") { S.res = p.res; syncAll(); markDirty(null, false); }
          else if (k === "noise") { S.noise = p.noise; rerenderAll(); } else if (k === "blur") { S.blur = p.blur; rerenderAll(); }
          else if (k === "tab") { S.tab = p.tab; applyLayout(); } else if (k === "lay") { S.lay = p.lay; applyLayout(); updateLayoutUI(); }
          else if (k === "seqParams") { Object.assign(S.sp, p.seqParams); syncMr(); rerenderAll(); }
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
        var offs = spec.offsets || [0], key = "t" + (++msgSeq), out = {labels: [], sid: null}, k = 0;
        var base = {key: key, W: W, H: H, O: spec.O, u: b.u, v: b.v, n: b.n, u0: u0, v0: v0, px: px, smin: Math.min.apply(null, offs), smax: Math.max.apply(null, offs), skinMm: T.bone_model.skin_thickness_mm, ids: C.ids, bone: boneParams()};
        function nxt() {
          if (k >= offs.length) { out.px = px; out.basis = b; out.u0 = u0; out.v0 = v0; return out; }
          return runSlice(Object.assign({}, base, {s: offs[k], wantSid: true})).then(function (r) { out.labels.push(r.lab); out.sid = r.sid; out.stats = r; k++; return nxt(); });
        }
        return buildGeometry().then(nxt);
      },
      lut: function (mod, seqKey) { if (mod === "ct") return Array.from(ctTable(C)); var sp = JSON.parse(JSON.stringify(T.mr_sequences.filter(function (q) { return q.key === seqKey; })[0])); return Array.from(mrTable(C, sp).sig); }
    };
    tablePromise = loadTable();
    return {};
  }

  /* ========================================================================================================
   * 5. ATTACH -- chain onto the (optional) needle add-on
   * ====================================================================================================== */
  var prev = G.NMSKClinical, chained = Object.assign({}, prev || {});
  chained.attach = function (api) {
    var r = null;
    if (prev && typeof prev.attach === "function") { try { r = prev.attach(api); } catch (e) { console.error("needle add-on failed to start:", e); } }
    try { attachImaging(api); } catch (e2) { console.error("imaging add-on failed to start; anatomy viewer unaffected:", e2); }
    return r;
  };
  chained.imaging = VERSION;
  G.NMSKClinical = chained;
})(typeof window !== "undefined" ? window : globalThis);
