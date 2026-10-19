/* NMSK Atlas -- PRIVATE clinical layer (clinical/LICENSE_PRIVATE.md): ULTRASOUND mode, phase 2 of the imaging layer (Q228).
 *
 * Staged beside a viewer page as clinical_ultrasound_tool.js (+ clinical_ultrasound_tissues.json) by scripts/clinical/stage_clinical_files.py.
 * It is NOT referenced by the public templates: the imaging add-on (clinical_imaging_tool.js) loads it as an optional companion and hands it
 * the shared geometry package, worker, tissue mapping and the page API. Without it the pages are exactly as before.
 *
 * WHAT IT IS: a SIMULATION computed from the segmented anatomical MESHES, not a scan and not a wave solver. The image plane of a virtual
 * probe (linear / convex / sector, placed on the skin, tilted, optionally swept) is rasterised into tissue classes by the Q226 kernel;
 * a B-mode image is then built along straight beam lines: specular reflection at class interfaces ((Z2-Z1)/(Z2+Z1))^2 with an angle
 * dependence, transmission loss, frequency-dependent attenuation, class backscatter with seeded (clearly synthetic) speckle, nominal TGC,
 * lateral/axial resolution from frequency and focus, A-line reverberation behind air; shadowing and posterior enhancement emerge from
 * the physics above. Everything is listed in the Info panel. A test hook is exported on globalThis.NMSKUltrasoundLib (node). */
(function (G) {
  "use strict";
  var VERSION = "q228.3";                                                   // Q246: body-fixed speckle keeps the q228 line
  var DEG = Math.PI / 180;

  /* ========================================================================================================
   * 1. PURE LIBRARY (no DOM): vectors, probe frames, fan geometry, skin picking / normals, PCA, the B-mode simulation
   * ====================================================================================================== */
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
  function add(a, b) { return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]; }
  function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
  function mul(a, s) { return [a[0] * s, a[1] * s, a[2] * s]; }
  function len(a) { return Math.hypot(a[0], a[1], a[2]); }
  function unit(a) { var l = len(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
  function angleDeg(a, b) { var c = dot(unit(a), unit(b)); return Math.acos(Math.max(-1, Math.min(1, c))) / DEG; }
  function rodrigues(v, k, ang) {                                           // rotate v about the unit axis k by ang (rad)
    var c = Math.cos(ang), s = Math.sin(ang), kv = cross(k, v), kd = dot(k, v) * (1 - c);
    return [v[0] * c + kv[0] * s + k[0] * kd, v[1] * c + kv[1] * s + k[1] * kd, v[2] * c + kv[2] * s + k[2] * kd];
  }

  /* ---- probe frame --------------------------------------------------------------------------------------
   * N = outward skin normal; ref = preferred direction of the long axis (projected into the tangent plane): the marker end is where the
   * image starts (screen LEFT), u0 runs from the marker end to the other end (screen RIGHT). Rotation about N by rotDeg.
   * Tilt = the probe's handle leans by tiltDeg towards t = cos(dir) u0 + sin(dir) e0 (a rigid rotation of the whole probe about the contact
   * point, axis k = N x t), so the face normal becomes N' = cos(th) N + sin(th) t and the beam b = -N'. dir 0 = towards the far end (rocking in
   * the image plane), 180 = towards the marker end, 90 / 270 = heel / toe (fanning: the plane swings out sideways). */
  function tangentRef(N, ref) {
    var t = sub(ref, mul(N, dot(ref, N)));
    if (len(t) < 1e-3) { var alt = Math.abs(N[0]) < 0.9 ? [1, 0, 0] : [0, 0, 1]; t = sub(alt, mul(N, dot(alt, N))); }
    return unit(t);
  }
  function probeFrame(N, ref, rotDeg, tiltDeg, dirDeg) {
    N = unit(N);
    var u0 = tangentRef(N, ref);
    if (rotDeg) u0 = unit(rodrigues(u0, N, rotDeg * DEG));
    var e0 = cross(N, u0), th = (tiltDeg || 0) * DEG, ph = (dirDeg || 0) * DEG;
    var t = add(mul(u0, Math.cos(ph)), mul(e0, Math.sin(ph))), k = unit(cross(N, t));
    var Nn = rodrigues(N, k, th), u = rodrigues(u0, k, th), e = rodrigues(e0, k, th);
    return {N0: N, u0: u0, e0: e0, N: Nn, u: u, e: e, b: [-Nn[0], -Nn[1], -Nn[2]], k: k, tilt: tiltDeg || 0, dir: dirDeg || 0};
  }
  var REF = {long: [0, -1, 0], trans: [-1, 0, 0]};                          // longitudinal: marker cranial (u caudal); transverse: marker to the patient's right (u to the left)

  /* ---- tilt star: centre + 8 tilted frames ---- */
  var STAR_NAMES = ["away from marker (rock)", "away + heel", "heel (fan)", "toward marker + heel", "toward marker (rock)", "toward marker + toe", "toe (fan)", "away + toe"];
  var STAR_SHORT = ["away", "away+heel", "heel", "toward+heel", "toward", "toward+toe", "toe", "away+toe"];
  function starTilts(theta) {
    var out = [{id: 0, tilt: 0, dir: 0, name: "perpendicular (90°)", short: "90°"}], i;
    for (i = 0; i < 8; i++) out.push({id: i + 1, tilt: theta, dir: i * 45, name: STAR_NAMES[i], short: STAR_SHORT[i] + " " + theta + "°"});
    return out;
  }
  /* ---- sweep ---- */
  function sweepOffsets(n, spacing, centered, sign) {
    var out = [], k, s = sign < 0 ? -1 : 1;
    for (k = 0; k < n; k++) out.push(s * (centered ? (k - (n - 1) / 2) * spacing : k * spacing));
    return out;
  }
  var MATRIX = {3: [3, 1], 4: [2, 2], 5: [3, 2], 6: [3, 2], 7: [4, 2], 8: [4, 2], 9: [3, 3]};
  function matrixDims(n) { return MATRIX[Math.max(3, Math.min(9, n))]; }

  /* ---- fan geometry in plane coordinates: x lateral (screen right = u), y depth (down = beam b), origin = middle of the probe face ---- */
  function fanGeom(type, widthMm, radiusMm, fanDeg, depthMm) {
    var g = {type: type, w: widthMm, R: 0, alpha: 0, depth: depthMm, bx0: 0, bx1: 0, by0: 0, by1: depthMm};
    if (type === "linear") { g.bx0 = -widthMm / 2; g.bx1 = widthMm / 2; g.by0 = 0; }
    else if (type === "convex") {
      g.R = radiusMm; g.alpha = widthMm / (2 * radiusMm);
      g.bx0 = -(g.R + depthMm) * Math.sin(g.alpha); g.bx1 = -g.bx0; g.by0 = g.R * Math.cos(g.alpha) - g.R;
    } else {
      g.alpha = fanDeg / 2 * DEG; g.bx0 = -depthMm * Math.sin(g.alpha); g.bx1 = -g.bx0; g.by0 = 0;
    }
    return g;
  }
  function lineStart(g, i, nL) {                                            // -> [x0, y0, dx, dy]
    if (g.type === "linear") return [-g.w / 2 + (i + 0.5) * g.w / nL, 0, 0, 1];
    var th = -g.alpha + (i + 0.5) * 2 * g.alpha / nL, sn = Math.sin(th), cs = Math.cos(th);
    return [g.R * sn, g.R * cs - g.R, sn, cs];
  }
  /* raster plan: pixel size, raster window (margins for the skin seat), output window (what is displayed), line count and sample step */
  function planRaster(g, maxDim, opt) {
    opt = opt || {};
    var margin = opt.margin == null ? 18 : opt.margin, pad = opt.pad == null ? 7 : opt.pad;
    var xmin = g.bx0 - 2, xmax = g.bx1 + 2, ymin = g.by0 - margin, ymax = g.by1 + margin;
    var px = Math.max(opt.minPx || 0.08, Math.max(xmax - xmin, ymax - ymin) / maxDim);
    var W = Math.ceil((xmax - xmin) / px), H = Math.ceil((ymax - ymin) / px);
    var yo0 = g.by0 - pad, Wo = Math.ceil((g.bx1 - g.bx0) / px), Ho = Math.ceil((g.by1 - yo0) / px);
    var maxLines = opt.maxLines || 256, nL;
    if (g.type === "linear") nL = Math.round(g.w / px); else nL = Math.round(2 * g.alpha * (g.R + g.depth) / px);
    nL = Math.max(48, Math.min(maxLines, nL));
    return {px: px, W: W, H: H, xr0: xmin, yr0: ymin, xo0: g.bx0, yo0: yo0, Wo: Wo, Ho: Ho, nL: nL, ds: Math.max(0.08, px * 0.8), margin: margin, pad: pad};
  }

  /* ---- acoustic table -> typed arrays indexed by the imaging class id ---- */
  function compileAcoustics(US, C) {
    var n = 256, A = {
      z: new Float32Array(n), alpha: new Float32Array(n), bs: new Float32Array(n), speck: new Float32Array(n), sig: new Float32Array(n), diff: new Float32Array(n),
      tex: new Uint8Array(n), aOn: new Uint8Array(n), aTh: new Float32Array(n), aFl: new Float32Array(n), aMin: new Float32Array(n), logz: new Float32Array(n),
      gel: US.global.gel, g: US.global, missing: [], keys: [], tex_p: US.textures, art: US.artefacts
    };
    var bs0 = US.global.bs0, fb = US.classes.soft_unassigned;
    C.T.classes.forEach(function (cl, i) {
      var r = US.classes[cl.key]; if (!r) { r = fb; A.missing.push(cl.key); }
      A.keys[i] = cl.key; A.z[i] = r.z; A.alpha[i] = r.alpha; A.bs[i] = bs0 * Math.pow(10, r.bs_db / 10); A.speck[i] = r.speck;
      A.sig[i] = r.spec_sigma_deg * DEG; A.diff[i] = r.diffuse; A.logz[i] = Math.log(r.z);
      A.tex[i] = r.texture === "muscle" ? 1 : r.texture === "tendon" ? 2 : 0;
      if (r.aniso) { A.aOn[i] = 1; A.aTh[i] = r.aniso.theta_deg * DEG; A.aFl[i] = r.aniso.floor; A.aMin[i] = r.aniso.min_elong; }
    });
    A.airId = C.ids.air; A.fatId = C.ids.fat; A.gelZ = US.global.gel.z_mrayl; A.airFillMm = US.global.air_pocket_fill_mm || 12;
    return A;
  }

  /* ---- seeded hashing / value noise ---- */
  function hash3(a, b, c, s) {
    var h = Math.imul(a | 0, 0x27d4eb2d) ^ Math.imul(b | 0, 0x165667b1) ^ Math.imul(c | 0, 0x85ebca6b) ^ Math.imul(s | 0, 0xc2b2ae35);
    h ^= h >>> 15; h = Math.imul(h, 0x2c1b3c6d); h ^= h >>> 12; h = Math.imul(h, 0x297a2d39); h ^= h >>> 15;
    return h >>> 0;
  }
  function g4(h) { return (((h & 255) + ((h >>> 8) & 255) + ((h >>> 16) & 255) + (h >>> 24)) - 510) * 0.006766; }   // ~ N(0,1)
  /* exponential-distributed speckle intensity (mean 1) from a smooth complex gaussian field: trilinear smoothstep value noise, unit variance */
  function speckleE(x, y, z, seed) {
    var ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z), fx = x - ix, fy = y - iy, fz = z - iz;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy); fz = fz * fz * (3 - 2 * fz);
    var wx0 = 1 - fx, wy0 = 1 - fy, wz0 = 1 - fz, I = 0, Q = 0, a, b, c, w, h, h2;
    for (c = 0; c < 2; c++) for (b = 0; b < 2; b++) for (a = 0; a < 2; a++) {
      w = (a ? fx : wx0) * (b ? fy : wy0) * (c ? fz : wz0);
      h = hash3(ix + a, iy + b, iz + c, seed); h2 = Math.imul(h ^ (h >>> 16), 0x9e3779b1) ^ (h >>> 7);
      I += w * g4(h); Q += w * g4(h2);
    }
    var n2 = ((wx0 * wx0 + fx * fx) * (wy0 * wy0 + fy * fy) * (wz0 * wz0 + fz * fz)) || 1, nn = 1 / Math.sqrt(n2);
    I *= nn; Q *= nn;
    return (I * I + Q * Q) * 0.5;
  }
  var WF1 = 0, WF2 = 0;
  function worley(cx, cy, seed) {                                           // F1, F2 (cell units) of a jittered 2-D grid
    var ix = Math.floor(cx), iy = Math.floor(cy), f1 = 9, f2 = 9, i, j;
    for (j = -1; j <= 1; j++) for (i = -1; i <= 1; i++) {
      var h = hash3(ix + i, iy + j, 17, seed), fx = ix + i + (h & 1023) / 1023, fy = iy + j + ((h >>> 10) & 1023) / 1023, d = Math.hypot(cx - fx, cy - fy);
      if (d < f1) { f2 = f1; f1 = d; } else if (d < f2) f2 = d;
    }
    WF1 = f1; WF2 = f2;
  }

  /* ---- separable box blur x3 (~ gaussian) of a Float32 image, radius r px ---- */
  function boxPass(src, dst, W, H, r, horiz) {
    var x, y, i, acc, n = horiz ? W : H, m = horiz ? H : W, st = horiz ? 1 : W, ls = horiz ? W : 1, inv = 1 / (2 * r + 1);
    for (y = 0; y < m; y++) {
      var base = y * ls; acc = 0;
      for (i = -r; i <= r; i++) acc += src[base + Math.min(n - 1, Math.max(0, i)) * st];
      for (x = 0; x < n; x++) {
        dst[base + x * st] = acc * inv;
        acc += src[base + Math.min(n - 1, x + r + 1) * st] - src[base + Math.max(0, x - r) * st];
      }
    }
  }
  function blur3(a, W, H, r) {
    var t = new Float32Array(a.length), p;
    for (p = 0; p < 3; p++) { boxPass(a, t, W, H, r, true); boxPass(t, a, W, H, r, false); }
    return a;
  }

  /* ---- the B-mode simulation along beam lines ----------------------------------------------------------
   * o: {AC, geom, plan, lab(Uint8 W*H), sid(Uint16|null), freq, depthMm, gainDb, tgcDb, focusMm, speckle, textures, reverb, noise, seed, elevMm,
   *     frame:{O,u,b} (3-D plane frame at the probe face; world = O + u x + b y), axisOf(sid)->{a:[3],elong}|null}
   * -> {db(Float32 Wo*Ho, dB re liver, -200 outside the fan), W, H, ysk, contact, stats} */
  function simulate(o) {
    var t0 = Date.now(), AC = o.AC, GL = AC.g, g = o.geom, pl = o.plan, W = pl.W, H = pl.H, px = pl.px, lab = o.lab, sid = o.sid;
    var f = o.freq, depth = o.depthMm, lam = 1.54 / f, nL = pl.nL, ds = pl.ds, nS = Math.floor(depth / ds) + 1, i, k, L;
    var axFw = GL.axial_cycles * lam / 2, Dap = Math.min(0.6 * g.w, 25), Fc = Math.max(5, o.focusMm), wF = 1.2 * lam * Fc / Dap, dof = 7 * lam * (Fc / Dap) * (Fc / Dap), wmin = 2.5 * lam + 0.2;
    function latFw(s) { var q = (s - Fc) / (dof / 2); return Math.min(8, Math.max(wmin, wF * Math.sqrt(1 + q * q))); }
    var AIR = AC.airId, GEL = 255, Zgel = AC.gelZ, maxGap = AC.gel.max_gap_mm;
    var attStep = new Float32Array(256), c;
    for (c = 0; c < 256; c++) attStep[c] = Math.pow(10, -AC.alpha[c] * f * ds / 100);
    var tgcRef = GL.tgc_alpha_ref_db_cm_mhz, Gt = new Float32Array(nS);
    for (k = 0; k < nS; k++) { var s0 = k * ds; Gt[k] = Math.pow(10, (2 * tgcRef * f * (s0 / 10) + (o.tgcDb || 0) * (s0 / depth)) / 10); }
    /* smoothed log-impedance for the interface normals */
    var ZS = new Float32Array(W * H), N = W * H;
    for (i = 0; i < N; i++) ZS[i] = AC.logz[lab[i]];
    blur3(ZS, W, H, Math.max(1, Math.round(0.9 / px)));
    function zsAt(X, Y) {                                                     // bilinear smoothed log-impedance at a plane position
      var fx = (X - pl.xr0) / px - 0.5, fy = (Y - pl.yr0) / px - 0.5, x0 = Math.floor(fx), y0 = Math.floor(fy), tx = fx - x0, ty = fy - y0;
      if (x0 < 0) { x0 = 0; tx = 0; } if (y0 < 0) { y0 = 0; ty = 0; } if (x0 > W - 2) { x0 = W - 2; tx = 1; } if (y0 > H - 2) { y0 = H - 2; ty = 1; }
      var b = y0 * W + x0;
      return (ZS[b] * (1 - tx) + ZS[b + 1] * tx) * (1 - ty) + (ZS[b + W] * (1 - tx) + ZS[b + W + 1] * tx) * ty;
    }
    /* the seat: first non-air pixel on the centre line (x = 0) between the top of the raster and +margin */
    var ix0 = Math.round((0 - pl.xr0) / px), ysk = 0, contact = false, iy;
    if (ix0 >= 0 && ix0 < W) for (iy = 0; iy < H; iy++) { if (lab[iy * W + ix0] !== AIR) { ysk = pl.yr0 + (iy + 0.5) * px; contact = iy > 0 && ysk <= pl.margin + 1e-6; break; } }
    if (!contact) ysk = 0;
    ysk = Math.max(-pl.margin + 1, Math.min(pl.margin - 1, ysk));
    var P = new Float32Array(nS * nL), reverb = [], tex = !!o.textures, spk = !!o.speckle, seed = (o.seed | 0) || 1;
    var cellAx = GL.speckle.cell_ax_wavelengths * lam, cellZ = GL.speckle.elev_mm, elev = o.elevMm || 0, frame = o.frame, nStats = {specCount: 0, lost: 0, texSamples: 0};
    var latCell = new Float32Array(nS), ref = o.ref || null;
    for (k = 0; k < nS; k++) latCell[k] = Math.max(0.4, latFw(k * ds) * 0.8);
    function latCellAt(y) { return Math.max(0.4, latFw(y < 0 ? 0 : y) * 0.8); }
    var lastSid = -1, lastAxis = null;
    var tp = AC.tex_p;
    for (L = 0; L < nL; L++) {
      var ls = lineStart(g, L, nL), x0 = ls[0], y0 = ls[1], dx = ls[2], dy = ls[3];
      var T = 1, prevZ = Zgel, prevCls = GEL, body = false, gap = 0, firstRev = -1, revVal = 0, bd = null, airUntil = -1, airNext = 0, fillK = Math.ceil(AC.airFillMm / ds);
      if (frame) bd = [frame.u[0] * dx + frame.b[0] * dy, frame.u[1] * dx + frame.b[1] * dy, frame.u[2] * dx + frame.b[2] * dy];
      for (k = 0; k < nS; k++) {
        var s = k * ds, X = x0 + dx * s, Y = y0 + dy * s + ysk;
        var jx = Math.floor((X - pl.xr0) / px), jy = Math.floor((Y - pl.yr0) / px), cls, pix = -1;
        if (jx < 0 || jy < 0 || jx >= W || jy >= H) cls = prevCls === GEL ? AIR : prevCls; else { pix = jy * W + jx; cls = lab[pix]; }
        if (!body) {
          if (cls === AIR) { gap += ds; if (gap > maxGap) { nStats.lost++; break; } cls = GEL; } else body = true;
        } else if (cls === AIR) {                                            // an air band thinner than airFillMm that tissue follows is a model artefact (overlapping skin shells), not a gas pocket: fat
          if (k >= airNext) {
            var kk2 = k + 1, kmx = Math.min(nS - 1, k + fillK), found = -1;
            for (; kk2 <= kmx; kk2++) {
              var jx2 = Math.floor((x0 + dx * kk2 * ds - pl.xr0) / px), jy2 = Math.floor((y0 + dy * kk2 * ds + ysk - pl.yr0) / px);
              if (jx2 < 0 || jy2 < 0 || jx2 >= W || jy2 >= H) break;
              if (lab[jy2 * W + jx2] !== AIR) { found = kk2; break; }
            }
            airUntil = found; airNext = found >= 0 ? found : k + 6;
          }
          if (k < airUntil) cls = AC.fatId;
        }
        var Z2 = cls === GEL ? Zgel : AC.z[cls];
        if (cls !== prevCls) {
          var R = (Z2 - prevZ) / (Z2 + prevZ); R *= R;
          var fq = 1;
          if (k > 0 && prevCls !== GEL) {                                    // sub-sample position of the interface: where the smoothed log-impedance crosses the mid-level between the two classes
            var za = AC.logz[prevCls], zb = AC.logz[cls], mid = (za + zb) / 2, v0 = zsAt(X - dx * ds, Y - dy * ds), v1 = zsAt(X, Y);
            if (Math.abs(v1 - v0) > 1e-6) { fq = (mid - v0) / (v1 - v0); fq = fq < 0 ? 0 : fq > 1 ? 1 : fq; }
            T *= Math.pow(10, -(AC.alpha[cls] - AC.alpha[prevCls]) * f * (1 - fq) * ds / 100);   // the last step spent (1 - fq) of its length in the new class
          }
          if (R > 1e-5) {
            var ang = 1, sg = cls === GEL ? 0.4 : Math.max(AC.sig[cls === GEL ? prevCls : cls], prevCls === GEL ? 0 : AC.sig[prevCls]), df = cls === GEL ? 0.25 : Math.max(AC.diff[cls], prevCls === GEL ? 0 : AC.diff[prevCls]);
            if (pix >= 0 && jx > 0 && jy > 0 && jx < W - 1 && jy < H - 1) {
              var gx = ZS[pix + 1] - ZS[pix - 1], gy = ZS[pix + W] - ZS[pix - W], gl = Math.hypot(gx, gy);
              if (gl > 1e-7) {
                var cs = Math.abs(dx * gx + dy * gy) / gl, th = Math.acos(Math.min(1, cs));
                ang = df + (1 - df) * Math.exp(-th * th / (2 * sg * sg));
              }
            }
            var sp = T * T * R * ang;
            if (k > 0 && fq < 1) P[(k - 1) * nL + L] += sp * Gt[k - 1] * (1 - fq);
            P[k * nL + L] += sp * Gt[k] * fq; nStats.specCount++;
            if (o.reverb && firstRev < 0 && R >= AC.art.reverb.r_min && k > 3) { firstRev = k; revVal = sp; }
            T *= (1 - R);
          }
          prevZ = Z2; prevCls = cls;
        }
        if (cls !== GEL) {
          var bsl = AC.bs[cls];
          if (bsl > 0) {
            var m = 1;
            if (AC.aOn[cls] || (tex && AC.tex[cls])) {
              var axs = null;
              if (sid && pix >= 0) { var q = sid[pix]; if (q < 65534) { if (q !== lastSid) { lastSid = q; lastAxis = o.axisOf ? o.axisOf(q) : null; } axs = lastAxis; } }
              if (axs && axs.elong >= (AC.aMin[cls] || 2.5)) {
                if (AC.aOn[cls] && bd) { var ca = Math.abs(dot(bd, axs.a)), dev = Math.asin(Math.min(1, ca)), qq = dev / AC.aTh[cls]; m *= AC.aFl[cls] + (1 - AC.aFl[cls]) * Math.exp(-qq * qq); }
                if (tex && AC.tex[cls] && frame) {
                  var wx = frame.O[0] + frame.u[0] * X + frame.b[0] * Y, wy = frame.O[1] + frame.u[1] * X + frame.b[1] * Y, wz = frame.O[2] + frame.u[2] * X + frame.b[2] * Y;
                  var a = axs.a, e1 = Math.abs(a[1]) < 0.9 ? unit(cross(a, [0, 1, 0])) : unit(cross(a, [1, 0, 0])), e2 = cross(a, e1);
                  var tp1 = AC.tex[cls] === 1 ? tp.muscle : tp.tendon, cell = AC.tex[cls] === 1 ? tp1.cell_mm : tp1.fib_mm * 5, lw = AC.tex[cls] === 1 ? tp1.line_mm : tp1.fib_mm * 0.5;
                  worley((wx * e1[0] + wy * e1[1] + wz * e1[2]) / cell, (wx * e2[0] + wy * e2[1] + wz * e2[2]) / cell, 5);
                  var dd = (WF2 - WF1) * cell / lw; m *= 1 + tp1.gain * Math.exp(-dd * dd); nStats.texSamples++;
                }
              }
            }
            var sc = AC.speck[cls];
            if (spk && sc > 0.01) {
              if (ref && frame) {                                              // Q246: the speckle lattice is fixed in the body (reference frame of the star / sweep), so a tilted, slid or swept plane meets the same grain
                var qx = frame.O[0] + frame.u[0] * X + frame.b[0] * Y - ref.O[0], qy = frame.O[1] + frame.u[1] * X + frame.b[1] * Y - ref.O[1], qz = frame.O[2] + frame.u[2] * X + frame.b[2] * Y - ref.O[2];
                var rx = qx * ref.u[0] + qy * ref.u[1] + qz * ref.u[2], ry = qx * ref.b[0] + qy * ref.b[1] + qz * ref.b[2], rz = qx * ref.e[0] + qy * ref.e[1] + qz * ref.e[2];
                m *= 1 - sc + sc * speckleE(rx / latCellAt(ry), ry / cellAx, rz / cellZ, seed);
              } else m *= 1 - sc + sc * speckleE(X / latCell[k], Y / cellAx, (elev + (frame && frame.zoff || 0)) / cellZ, seed);
            }
            P[k * nL + L] += bsl * T * T * m * Gt[k];
          }
          T *= attStep[cls];
          if (T < 1e-13) break;
        }
      }
      if (firstRev > 0) reverb.push(L, firstRev, revVal);
    }
    if (reverb.length) {
      var lv = AC.art.reverb.levels_db;
      for (i = 0; i < reverb.length; i += 3) {
        for (var mm = 2; mm <= 3; mm++) {
          var km = reverb[i + 1] * mm; if (km >= nS - 1) break;
          var amp = reverb[i + 2] * Math.pow(10, lv[mm - 2] / 10) * Gt[km];
          P[km * nL + reverb[i]] += amp; P[(km + 1) * nL + reverb[i]] += amp * 0.5;
        }
      }
    }
    /* resolution: axial smoothing (rows) then lateral smoothing with the beam width at each depth */
    var sa = axFw / 2.355 / ds;
    if (sa > 0.45) {
      var ra = Math.min(6, Math.ceil(sa * 2.5)), ka = new Float32Array(2 * ra + 1), ss = 0, tmpR = new Float32Array(nL);
      for (i = -ra; i <= ra; i++) { ka[i + ra] = Math.exp(-i * i / (2 * sa * sa)); ss += ka[i + ra]; }
      for (i = 0; i < ka.length; i++) ka[i] /= ss;
      var Q = new Float32Array(P.length);
      for (k = 0; k < nS; k++) for (i = -ra; i <= ra; i++) { var kk = k + i; if (kk < 0 || kk >= nS) continue; var wgt = ka[i + ra], ob = k * nL, ib = kk * nL; for (L = 0; L < nL; L++) Q[ob + L] += wgt * P[ib + L]; }
      P = Q;
    }
    var rowT = new Float32Array(nL);
    for (k = 0; k < nS; k += 1) {
      var sdep = k * ds, dxl = g.type === "linear" ? g.w / nL : 2 * g.alpha * (g.R + sdep) / nL, sl = latFw(sdep) / 2.355 / Math.max(dxl, 1e-3);
      if (sl < 0.45) continue;
      var rl = Math.min(14, Math.ceil(sl * 2.5)), kl = new Float32Array(2 * rl + 1), sk = 0, rb = k * nL;
      for (i = -rl; i <= rl; i++) { kl[i + rl] = Math.exp(-i * i / (2 * sl * sl)); sk += kl[i + rl]; }
      for (i = 0; i < kl.length; i++) kl[i] /= sk;
      for (L = 0; L < nL; L++) { var acc = 0, wsum = 0; for (i = -rl; i <= rl; i++) { var l2 = L + i; if (l2 < 0 || l2 >= nL) continue; acc += kl[i + rl] * P[rb + l2]; wsum += kl[i + rl]; } rowT[L] = acc / wsum; }
      for (L = 0; L < nL; L++) P[rb + L] = rowT[L];
    }
    /* scan conversion to the output window + dB re liver */
    var Wo = pl.Wo, Ho = pl.Ho, db = new Float32Array(Wo * Ho), bs0 = GL.bs0, ox, oy, R0 = g.R, linear = g.type === "linear";
    var nzF = Math.pow(10, GL.noise_floor_db / 10) * bs0, nseed = seed * 7 + 3;
    for (oy = 0; oy < Ho; oy++) {
      var Yo = pl.yo0 + (oy + 0.5) * px - ysk;
      for (ox = 0; ox < Wo; ox++) {
        var Xo = pl.xo0 + (ox + 0.5) * px, fl, sr;
        if (linear) { fl = (Xo + g.w / 2) / g.w * nL - 0.5; sr = Yo; }
        else { var ddx = Xo, ddy = Yo + R0, r = Math.hypot(ddx, ddy), th2 = Math.atan2(ddx, ddy); fl = (th2 + g.alpha) / (2 * g.alpha) * nL - 0.5; sr = r - R0; }
        var idx = oy * Wo + ox;
        if (fl < -0.5 || fl > nL - 0.5 || sr < 0 || sr > depth || (sr < 0.01 && !contact)) { db[idx] = -200; continue; }
        var kf = sr / ds, k0 = Math.min(nS - 2, Math.floor(kf)), tk = kf - k0, l0 = Math.max(0, Math.min(nL - 2, Math.floor(fl))), tl = Math.min(1, Math.max(0, fl - l0));
        var b0 = k0 * nL + l0, v = (P[b0] * (1 - tl) + P[b0 + 1] * tl) * (1 - tk) + (P[b0 + nL] * (1 - tl) + P[b0 + nL + 1] * tl) * tk;
        if (o.noise) {
          var hh, u1;
          if (ref && frame) {                                                // Q246: system noise is seeded by the position in the body (cell = one output pixel), not by the screen pixel
            var wy = Yo + ysk, qx2 = frame.O[0] + frame.u[0] * Xo + frame.b[0] * wy - ref.O[0], qy2 = frame.O[1] + frame.u[1] * Xo + frame.b[1] * wy - ref.O[1], qz2 = frame.O[2] + frame.u[2] * Xo + frame.b[2] * wy - ref.O[2];
            var nc = Math.max(px, 0.25);
            hh = hash3(Math.floor((qx2 * ref.u[0] + qy2 * ref.u[1] + qz2 * ref.u[2]) / nc), Math.floor((qx2 * ref.b[0] + qy2 * ref.b[1] + qz2 * ref.b[2]) / nc), Math.floor((qx2 * ref.e[0] + qy2 * ref.e[1] + qz2 * ref.e[2]) / nc), nseed);
          } else hh = hash3(ox, oy, 91, nseed);
          u1 = ((hh >>> 8) + 0.5) / 16777216; v += nzF * -Math.log(u1);
        }
        db[idx] = v > 1e-30 ? 4.342945 * Math.log(v / bs0) : -200;
      }
    }
    return {db: db, Wo: Wo, Ho: Ho, W: W, H: H, ysk: ysk, contact: contact, nL: nL, nS: nS, ms: Date.now() - t0, stats: nStats, latFw: latFw, axFw: axFw};
  }
  /* display mapping: dB re liver -> 0..255 (gain in dB, dynamic range, liver level at displayRef of the range) */
  function toGray(db, ref, gainDb, drDb) {
    var out = new Uint8ClampedArray(db.length), lo = -ref * drDb - gainDb, sc = 255 / drDb, i;
    for (i = 0; i < db.length; i++) out[i] = (db[i] - lo) * sc;
    return out;
  }

  /* ---- skin: nearest ray hit and smoothed normal -------------------------------------------------------
   * geo: the imaging geometry package (pos, idx global, tStart, bbox, skinList); keep(point)->bool optional (cut plane) */
  function rayBox(o, d, bb, tmax) {
    var t0 = 0, t1 = tmax, a;
    for (a = 0; a < 3; a++) {
      var inv = 1 / (d[a] || 1e-30), ta = (bb[a] - o[a]) * inv, tb = (bb[a + 3] - o[a]) * inv;
      if (ta > tb) { var q = ta; ta = tb; tb = q; }
      if (ta > t0) t0 = ta; if (tb < t1) t1 = tb; if (t0 > t1) return false;
    }
    return true;
  }
  function skinHit(geo, o, d, keep) {
    var best = null, pos = geo.pos, idx = geo.idx, si, t;
    for (si = 0; si < geo.skinList.length; si++) {
      var st = geo.skinList[si], bb = [geo.bbox[st * 6], geo.bbox[st * 6 + 1], geo.bbox[st * 6 + 2], geo.bbox[st * 6 + 3], geo.bbox[st * 6 + 4], geo.bbox[st * 6 + 5]];
      if (!rayBox(o, d, bb, best ? best.t : 1e9)) continue;
      for (t = geo.tStart[st]; t < geo.tStart[st + 1]; t++) {
        var a = idx[3 * t] * 3, b = idx[3 * t + 1] * 3, c = idx[3 * t + 2] * 3;
        var e1x = pos[b] - pos[a], e1y = pos[b + 1] - pos[a + 1], e1z = pos[b + 2] - pos[a + 2], e2x = pos[c] - pos[a], e2y = pos[c + 1] - pos[a + 1], e2z = pos[c + 2] - pos[a + 2];
        var px_ = d[1] * e2z - d[2] * e2y, py_ = d[2] * e2x - d[0] * e2z, pz_ = d[0] * e2y - d[1] * e2x, det = e1x * px_ + e1y * py_ + e1z * pz_;
        if (Math.abs(det) < 1e-12) continue;
        var inv = 1 / det, tx = o[0] - pos[a], ty = o[1] - pos[a + 1], tz = o[2] - pos[a + 2], u = (tx * px_ + ty * py_ + tz * pz_) * inv;
        if (u < 0 || u > 1) continue;
        var qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x, v = (d[0] * qx + d[1] * qy + d[2] * qz) * inv;
        if (v < 0 || u + v > 1) continue;
        var tt = (e2x * qx + e2y * qy + e2z * qz) * inv;
        if (tt <= 1e-6 || (best && tt >= best.t)) continue;
        var pt = [o[0] + d[0] * tt, o[1] + d[1] * tt, o[2] + d[2] * tt];
        if (keep && !keep(pt)) continue;
        best = {t: tt, point: pt, tri: t, struct: st};
      }
    }
    return best;
  }
  /* area-weighted average of the skin triangle normals within `radius` mm of P (linear fall-off), oriented like the hit triangle (= towards the viewer) */
  function triNormal(geo, t) {
    var pos = geo.pos, idx = geo.idx, a = idx[3 * t] * 3, b = idx[3 * t + 1] * 3, c = idx[3 * t + 2] * 3;
    return cross([pos[b] - pos[a], pos[b + 1] - pos[a + 1], pos[b + 2] - pos[a + 2]], [pos[c] - pos[a], pos[c + 1] - pos[a + 1], pos[c + 2] - pos[a + 2]]);
  }
  function smoothNormal(geo, P, radius, refN, nearStruct) {
    var pos = geo.pos, idx = geo.idx, acc = [0, 0, 0], si, t, wsum = 0, ref = refN ? unit(refN) : null;
    for (si = 0; si < geo.skinList.length; si++) {
      var st = geo.skinList[si], bi = st * 6;
      if (P[0] < geo.bbox[bi] - radius || P[0] > geo.bbox[bi + 3] + radius || P[1] < geo.bbox[bi + 1] - radius || P[1] > geo.bbox[bi + 4] + radius || P[2] < geo.bbox[bi + 2] - radius || P[2] > geo.bbox[bi + 5] + radius) continue;
      for (t = geo.tStart[st]; t < geo.tStart[st + 1]; t++) {
        var a = idx[3 * t] * 3, b = idx[3 * t + 1] * 3, c = idx[3 * t + 2] * 3;
        var cx = (pos[a] + pos[b] + pos[c]) / 3 - P[0]; if (cx > radius || cx < -radius) continue;
        var cy = (pos[a + 1] + pos[b + 1] + pos[c + 1]) / 3 - P[1]; if (cy > radius || cy < -radius) continue;
        var cz = (pos[a + 2] + pos[b + 2] + pos[c + 2]) / 3 - P[2], dd = Math.hypot(cx, cy, cz); if (dd > radius) continue;
        var n = triNormal(geo, t);
        if (!ref) ref = unit(n);
        var w = 1 - dd / radius; if (dot(n, ref) < 0) n = [-n[0], -n[1], -n[2]];
        acc[0] += n[0] * w; acc[1] += n[1] * w; acc[2] += n[2] * w; wsum += w;
      }
    }
    return wsum > 0 && len(acc) > 1e-9 ? unit(acc) : (ref || [0, 0, 1]);
  }

  /* ---- PCA axis of a structure's vertices ---- */
  function pcaAxis(pos, v0, v1) {
    var nv = v1 - v0, step = Math.max(1, Math.floor(nv / 800)), k, cx = 0, cy = 0, cz = 0, m = 0;
    for (k = v0; k < v1; k += step) { cx += pos[3 * k]; cy += pos[3 * k + 1]; cz += pos[3 * k + 2]; m++; }
    if (m < 4) return null;
    cx /= m; cy /= m; cz /= m;
    var xx = 0, xy = 0, xz = 0, yy = 0, yz = 0, zz = 0;
    for (k = v0; k < v1; k += step) { var dx = pos[3 * k] - cx, dy = pos[3 * k + 1] - cy, dz = pos[3 * k + 2] - cz; xx += dx * dx; xy += dx * dy; xz += dx * dz; yy += dy * dy; yz += dy * dz; zz += dz * dz; }
    var a = [0.3, 1, 0.2], it, l;
    for (it = 0; it < 40; it++) {
      var nx = xx * a[0] + xy * a[1] + xz * a[2], ny = xy * a[0] + yy * a[1] + yz * a[2], nz = xz * a[0] + yz * a[1] + zz * a[2];
      l = Math.hypot(nx, ny, nz) || 1; a = [nx / l, ny / l, nz / l];
    }
    var lam1 = (xx * a[0] * a[0] + yy * a[1] * a[1] + zz * a[2] * a[2] + 2 * (xy * a[0] * a[1] + xz * a[0] * a[2] + yz * a[1] * a[2])) / m;
    var tr = (xx + yy + zz) / m, rest = Math.max(1e-9, (tr - lam1) / 2);
    return {a: a, c: [cx, cy, cz], elong: lam1 / rest};
  }
  /* "follow the organ": the rotation about N (given tilt) that puts the sweep direction e' closest to the organ axis; returns rotDeg and the sign */
  function followRotation(N, ref, tiltDeg, dirDeg, axis) {
    var best = null, r;
    for (r = 0; r < 360; r += 1) {
      var fr = probeFrame(N, ref, r, tiltDeg, dirDeg), c = Math.abs(dot(fr.e, axis));
      if (!best || c > best.c) best = {c: c, rot: r, sign: dot(fr.e, axis) >= 0 ? 1 : -1};
    }
    return best;
  }

  /* ---- Q253: probe-frequency / depth mismatch check -----------------------------------------------------
   * Honest heuristic, not a clinical rule. Two independent checks, both grounded in numbers this tool already
   * uses elsewhere (never invented here):
   *   (a) low frequency on a shallow/small target: axial & lateral resolution both scale with wavelength
   *       (this tool's own info panel: "axial ~ 1.25 wavelengths; lateral = 1.2 lambda F/D"), so a <=5 MHz
   *       probe on a <=3 cm target (hand / wrist / foot / tendon scale) will be coarse.
   *   (b) high frequency too deep: round-trip attenuation loss_dB = 2 x alphaRef x freq x depthCm, using
   *       alphaRef = ultrasound_tissues.json global.tgc_alpha_ref_db_cm_mhz (the SAME nominal soft-tissue
   *       attenuation this tool's own time-gain-compensation already assumes, 0.6 dB/cm/MHz, cited there as
   *       "scanners use 0.5-0.7"). Above ~90 dB round trip the far field sits below any realistic gain + the
   *       default 60 dB display range, so it will read as very dark / unreadable. */
  function probeMismatch(freq, depthCm, alphaRef) {
    var ar = alphaRef > 0 ? alphaRef : 0.6;
    if (freq <= 5 && depthCm <= 3) {
      return {kind: "shallow_lowfreq", text: freq + " MHz on a " + depthCm + " cm-deep target: a low-frequency probe gives coarse resolution here (wavelength ∝ 1/f) — prefer a 10–12 MHz probe for hand / wrist / foot / tendon."};
    }
    var loss = 2 * ar * freq * depthCm;
    if (loss > 90) {
      return {kind: "deep_highfreq", loss: loss, text: freq + " MHz to " + depthCm + " cm: round-trip attenuation ≈ " + Math.round(loss) + " dB (" + ar + " dB/cm/MHz, this tool's own TGC reference) — the far field will be very dark — prefer a 2–5 MHz probe for deep / abdominal targets."};
    }
    return null;
  }

  var LIB = {VERSION: VERSION, probeFrame: probeFrame, REF: REF, starTilts: starTilts, sweepOffsets: sweepOffsets, matrixDims: matrixDims, fanGeom: fanGeom, lineStart: lineStart,
    planRaster: planRaster, compileAcoustics: compileAcoustics, simulate: simulate, hash3: hash3, toGray: toGray, skinHit: skinHit, smoothNormal: smoothNormal, pcaAxis: pcaAxis,
    followRotation: followRotation, angleDeg: angleDeg, speckleE: speckleE, dot: dot, cross: cross, unit: unit, rodrigues: rodrigues, STAR_NAMES: STAR_NAMES, probeMismatch: probeMismatch};
  G.NMSKUltrasoundLib = LIB;
  if (typeof document === "undefined") return;

  /* ========================================================================================================
   * 2. ENGINE + UI (browser only)
   * ====================================================================================================== */
  var SCRIPT_BASE = (function () {
    try { var cs = document.currentScript; if (cs && cs.src) return cs.src.replace(/[^\/]*$/, ""); } catch (e) {}
    return "";
  })();
  var BADGE = "Simulated from meshes – not an ultrasound";

  var CODE_SRC = (function () { try { var cs = document.currentScript; return cs && cs.src ? "file" : "inline"; } catch (e) { return "inline"; } })();   // Q239
  function attachUltrasound(api, sh) {
    var tableSrc = "", usErr = null;
    var US = null, AC = null, C = null, T = null, geo = null, loadErr = null, loadPromise = null;
    var S = {
      open: false, mode: "star", probe: "linear", widths: {linear: 44, convex: 65, sector: 22}, freq: 7.5, depthCm: 5, gain: 0, tgc: 0, focusCm: 2.5, dr: 60,
      refKey: "long", rot: 0, tilt: 15, mTilt: 0, mTiltDir: 0, n: 6, spacing: 10, byTotal: false, total: 50, centered: false, sign: 1, follow: false, followSid: -1, followName: "",
      speckle: true, textures: true, reverb: true, noise: false, hidden: false, P: null, N: null, sel: 0, view: "matrix", lay: "auto", tab: "image", placing: false,
      cine: false, fps: 3, cineMode: "step", sec: "probe", pick3d: false, seed: 11
    };
    var frames = [], views = [], root = null, ui = {}, timers = {}, gen = 0, keySeq = 0, perf = {last: null, hist: []}, axisCache = {}, firing = false, busy = false, overlay = null, lastOverlayKey = "";
    /* Q257: CONTINUOUS cine -- genuinely re-slices at every displayed position (not a snap between the step-cine's N precomputed
     * planes), at a reduced "live" quality tier so it stays real-time (same idea as the CT/MRI imaging kernel's tier-0-while-dragging
     * fast path). sweep mode: the elevational offset slides continuously across the configured total range, ping-ponging at the ends.
     * star mode: the tilt direction rotates continuously at the fixed tilt angle (a continuous fan, the probe's own tilt ring made smooth).
     * The position advances by REAL measured wall-clock time between frames, never by a fixed frame count, so a slower device shows
     * honestly coarser steps instead of a faked constant speed. */
    var contState = {active: false, pos: 0, dir: 1, lastT: 0, busy: false, measMs: 0, fpsActual: 0, raf: 0};
    function contQuality() { return {maxDim: 320, maxLines: 192}; }          // Q257: real headless-Chromium timing (own female, linear 5 cm ~24 ms, convex 15 cm ~? ms -- see PROJECT_STATE Q257) comfortably clears every fps budget (<=125 ms at fps 8) at this tier, the same one already used for the star ring / 6-9 frame sweep matrix
    function reqFrame(fn) { return G.setTimeout(function () { fn(Date.now()); }, 16); }   // Q257: setTimeout, not requestAnimationFrame -- verified empirically that rAF/BeginFrame production on this
    function cancelFrame(id) { G.clearTimeout(id); }                                       // page's headless-Chromium test harness can stall for seconds at a time (scratchpad/q257/debug_rafonly.py), the same
                                                                                             // reason every other timed loop in this file (timers.cine, the overlay poll) already uses setInterval/setTimeout, never rAF
    function contRangeMm() { var half = spacing() * Math.max(1, S.n - 1) / 2; return half; }               // same physical extent as the discrete sweep's own step x (n-1)
    function contOneWaySec() { return 6 / Math.max(1, S.fps); }              // fps selector reused as a SPEED proxy in continuous mode (fps 1 -> 6 s one-way / one turn, fps 8 -> 0.75 s)
    function contSpecSweep(offMm) {
      var sr = sweepRot(S.mTilt, S.mTiltDir);
      return {id: S.sel, tilt: S.mTilt, dir: S.mTiltDir, off: offMm, rotOverride: sr.rot,
        label: "live sweep  " + (offMm >= 0 ? "+" : "−") + Math.abs(Math.round(offMm * 10) / 10) + " mm", short: "live " + (offMm >= 0 ? "+" : "−") + Math.abs(Math.round(offMm)) + " mm"};
    }
    function contSpecStar(dirDeg) {
      return {id: S.sel, tilt: S.tilt, dir: dirDeg, off: 0, label: "live tilt " + S.tilt + "° · dir " + Math.round(dirDeg) + "°", short: "live " + Math.round(dirDeg) + "°"};
    }
    function contTick(now) {
      if (!contState.active) return;
      if (contState.busy || !frames.length) { contState.raf = reqFrame(contTick); return; }
      var dt = contState.lastT ? Math.min(250, now - contState.lastT) / 1000 : 0; contState.lastT = now;
      var spec;
      if (S.mode === "star") {
        var degPerSec = 360 / contOneWaySec(); contState.pos = ((contState.pos + degPerSec * dt) % 360 + 360) % 360; spec = contSpecStar(contState.pos);
      } else {
        var half = contRangeMm(), mmPerSec = (half * 2) / Math.max(0.2, contOneWaySec());
        contState.pos += contState.dir * mmPerSec * dt;
        if (contState.pos > half) { contState.pos = half; contState.dir = -1; } else if (contState.pos < -half) { contState.pos = -half; contState.dir = 1; }
        spec = contSpecSweep(contState.pos);
      }
      contState.busy = true; var t0 = Date.now();
      computeFrame(spec, contQuality(), frames[S.sel]).then(function (fr) {
        contState.busy = false; if (!contState.active) return;
        contState.measMs = Date.now() - t0; contState.fpsActual = Math.round((1000 / Math.max(1, contState.measMs)) * 10) / 10;
        frames[S.sel] = fr; paintView(S.sel, fr); if (S.mode === "star") drawSchematic(); updateOverlay(); updateContReadout();
        contState.raf = reqFrame(contTick);
      }, function (err) { contState.busy = false; console.error("continuous cine:", err); contState.raf = reqFrame(contTick); });
    }
    function updateContReadout() { if (ui.contOut) ui.contOut.textContent = contState.active ? ("live ≈ " + contState.fpsActual + " fps (" + contState.measMs + " ms/frame)") : ""; }

    /* ---------- table + geometry ---------- */
    var acousticP = null;
    function acousticTable() {                                                 // Q239: the table pasted into the page first, the sibling file (fetch, then XHR) as a fallback
      if (acousticP) return acousticP;
      var inl = sh.inline("nmsk-ultrasound-tissues"), p = null;
      if (inl) { try { var tj = JSON.parse(inl); tableSrc = "inline"; p = Promise.resolve(tj); } catch (e) { p = null; } }
      if (!p) { tableSrc = "file"; p = sh.loadJson("clinical_ultrasound_tissues.json"); }
      acousticP = p.then(function (t) { US = t; usErr = null; setDiag(); return t; }, function (e) { usErr = String(e && e.message || e); setDiag(); throw e; });
      return acousticP;
    }
    function nClasses() { var c = US && US.classes; return !c ? 0 : Array.isArray(c) ? c.length : Object.keys(c).length; }
    function diagText() {
      if (usErr) return {ok: false, text: "Ultrasound tool: NOT ready – acoustic table: " + usErr};
      if (!US) return {ok: null, text: "Ultrasound tool: loading acoustic table …"};
      if (loadErr) return {ok: false, text: "Ultrasound tool: NOT ready – " + loadErr};
      return {ok: true, text: "Ultrasound tool: ready (v" + VERSION + ", tissues " + nClasses() + ", code " + CODE_SRC + ", table " + tableSrc + ")"};
    }
    function setDiag() {
      var d = diagText(); sh.setUsDiag(d.ok, d.text, {version: VERSION, tissues: US ? nClasses() : 0, code: CODE_SRC, table: tableSrc});
      if (ui.diag) { ui.diag.textContent = d.text; ui.diag.className = "us-diag" + (d.ok === false ? " bad" : ""); ui.diag.title = d.text; }
    }
    function loadTable() {
      if (loadPromise) return loadPromise;
      loadPromise = acousticTable()
        .then(function (t) { US = t; return sh.ensure(function (m) { setStatus(m); }); })
        .then(function (x) { geo = x.geo; C = x.C; T = x.T; AC = LIB.compileAcoustics(US, C); if (S.P == null) defaultPlacement(); })
        .catch(function (e) { loadErr = String(e && e.message || e); console.error("ultrasound:", e); })
        .then(function () { setDiag(); });
      return loadPromise;
    }
    function axisOf(sid) {
      if (sid < 0 || sid >= geo.n) return null;
      var a = axisCache[sid];
      if (a === undefined) { a = LIB.pcaAxis(geo.pos, geo.vStart[sid], geo.vStart[sid + 1]); axisCache[sid] = a; }
      return a;
    }

    /* ---------- probe placement on the skin ---------- */
    function cutKeep() {
      var c = api.cut(); if (!c) return null;
      var l = Math.hypot(c[0], c[1], c[2]) || 1, n = [c[0] / l, c[1] / l, c[2] / l], k = c[3] / l, th = api.cutSlab ? api.cutSlab() : 0;
      return function (p) { var d = n[0] * p[0] + n[1] * p[1] + n[2] * p[2] + k; return d >= -0.5 && (th <= 0 || d <= th + 0.5); };
    }
    function placeRay(o, d, quiet) {                                          // ray in root-local atlas mm -> sets P, N
      if (!geo) return null;
      var h = LIB.skinHit(geo, o, LIB.unit(d), cutKeep());
      if (!h) { if (!quiet) setStatus("No skin under that point (the ray misses the body, or the skin there is cut away)."); return null; }
      var nrm = LIB.smoothNormal(geo, h.point, 15, null, h.struct);
      if (LIB.dot(nrm, d) > 0) nrm = [-nrm[0], -nrm[1], -nrm[2]];             // outward = facing the viewer
      S.P = h.point; S.N = nrm; S.skinStruct = h.struct; axisCache.__follow = null;
      return h;
    }
    function abdomenPlacement() {                                              // first open: the anterior upper abdomen on the midline (62 % of the body height), a useful acoustic window on every page
      var bb = geo.bodyBox, cx = (bb.lo[0] + bb.hi[0]) / 2, cy = bb.lo[1] + 0.62 * (bb.hi[1] - bb.lo[1]), cz = (bb.lo[2] + bb.hi[2]) / 2;
      return placeRay([cx, cy, bb.hi[2] + 600], [0, 0, -1], true);
    }
    function defaultPlacement(fromView) {                                      // "Screen centre": the skin under the centre of the 3D view
      if (!fromView && abdomenPlacement()) return;
      var v = api.view(), o = v.eye, d = [v.target[0] - v.eye[0], v.target[1] - v.eye[1], v.target[2] - v.eye[2]];
      if (!placeRay(o, d, true)) abdomenPlacement();
    }
    function onPlaceClick(e) {
      if (!S.open || (!S.placing && !S.pick3d) || !geo) return false;
      var r = api.ray(e);
      if (S.pick3d) {                                                         // choose the organ to follow
        S.pick3d = false; if (ui.pickBtn) ui.pickBtn.setAttribute("aria-pressed", "false");
        var h = api.pick(e);
        if (h && h.i != null) setFollow(h.i); else setStatus("Nothing picked.");
        return true;
      }
      var hit = placeRay(r.o, r.d);
      S.placing = false; syncUi();
      if (hit) { S.sel = 0; refresh(true); }
      return true;
    }
    function setFollow(sid) {
      S.followSid = sid; S.followName = geo.names[sid] || ""; var a = LIB.pcaAxis(geo.pos, geo.vStart[sid], geo.vStart[sid + 1]);
      S.follow = !!a; if (!a) setStatus("That structure has too few vertices for a long axis."); else setStatus("Following " + S.followName + " (long axis from PCA, elongation " + a.elong.toFixed(1) + ")");
      syncUi(); refresh(true);
    }

    /* ---------- frames ---------- */
    function orientRef() { return LIB.REF[S.refKey] || LIB.REF.long; }
    function probeW() { return S.widths[S.probe]; }
    function curGeom() {
      var p = US.probes[S.probe];
      return LIB.fanGeom(S.probe, probeW(), p.radius_mm, p.fan_deg, S.depthCm * 10);
    }
    function sweepRot(tilt, dir) {                                            // follow-the-organ rotation (or the user's)
      if (S.follow && S.followSid >= 0) {
        var ax = LIB.pcaAxis(geo.pos, geo.vStart[S.followSid], geo.vStart[S.followSid + 1]);
        if (ax) { var b = LIB.followRotation(S.N, orientRef(), tilt, dir, ax.a); return {rot: b.rot - 0, sign: b.sign, axis: ax}; }
      }
      return {rot: S.rot, sign: S.sign, axis: null};
    }
    function frameSpecs() {
      var out = [], i;
      if (S.mode === "star") {
        LIB.starTilts(S.tilt).forEach(function (t) { out.push({id: t.id, tilt: t.tilt, dir: t.dir, off: 0, short: t.short, label: t.id === 0 ? "90° (perpendicular)" : "tilt " + S.tilt + "° " + t.name}); });
      } else {
        var sr = sweepRot(S.mTilt, S.mTiltDir), step = spacing(), offs = LIB.sweepOffsets(S.n, step, S.centered, sr.sign);
        for (i = 0; i < S.n; i++) out.push({id: i, tilt: S.mTilt, dir: S.mTiltDir, off: offs[i], rotOverride: sr.rot, label: "#" + (i + 1) + "  " + (offs[i] >= 0 ? "+" : "−") + Math.abs(Math.round(offs[i] * 10) / 10) + " mm", short: "#" + (i + 1) + " " + (offs[i] >= 0 ? "+" : "\u2212") + Math.abs(Math.round(offs[i])) + " mm"});
      }
      return out;
    }
    function spacing() { return S.byTotal ? (S.n > 1 ? S.total / (S.n - 1) : S.total) : S.spacing; }
    function poseOf(spec) {
      var rot = spec.rotOverride != null ? spec.rotOverride : S.rot;
      var pf = LIB.probeFrame(S.N, orientRef(), rot, spec.tilt, spec.dir);
      var O = [S.P[0] + pf.e[0] * spec.off, S.P[1] + pf.e[1] * spec.off, S.P[2] + pf.e[2] * spec.off], shift = 0;
      if (spec.off !== 0 && geo) {                                              // re-seat on the skin by sliding the face along the beam axis (stays in the same image plane, so planes stay parallel)
        var o2 = [O[0] + pf.N[0] * 60, O[1] + pf.N[1] * 60, O[2] + pf.N[2] * 60], h = LIB.skinHit(geo, o2, pf.b, null);
        if (h && h.t < 140) { shift = h.t - 60; O = h.point; }
      }
      return {pf: pf, O: O, shift: shift};
    }
    function visMask() {
      var m = new Uint8Array(geo.n), i; for (i = 0; i < geo.n; i++) { var v = true; try { v = !!api.visible(i); } catch (e) {} m[i] = v ? 1 : 0; } return m;
    }
    function quality(idx) {
      if (S.mode === "star") return idx === S.sel ? {maxDim: 480, maxLines: 256} : {maxDim: 320, maxLines: 192};
      return S.n <= 4 ? {maxDim: 440, maxLines: 256} : S.n <= 6 ? {maxDim: 380, maxLines: 224} : {maxDim: 320, maxLines: 192};
    }
    function refFrame(spec) {                                                   // fixed frame of the whole star / sweep: the centre (perpendicular) frame, or the sweep's own tilt
      var rot = spec.rotOverride != null ? spec.rotOverride : S.rot, pf = LIB.probeFrame(S.N, orientRef(), rot, S.mode === "star" ? 0 : spec.tilt, S.mode === "star" ? 0 : spec.dir);
      return {O: S.P, u: pf.u, b: pf.b, e: pf.e};
    }
    function simOpts(fr, extra) {
      var p = US.probes[S.probe];
      return Object.assign({AC: AC, geom: fr.geom, plan: fr.plan, lab: fr.lab, sid: fr.sid, freq: S.freq, depthMm: S.depthCm * 10, gainDb: S.gain, tgcDb: S.tgc, focusMm: S.focusCm * 10,
        speckle: S.speckle, textures: S.textures, reverb: S.reverb, noise: S.noise, seed: S.seed,        // Q246: ONE seed for every frame: the speckle belongs to the body, not to the frame
        elevMm: S.mode === "star" ? 0 : fr.spec.off, frame: {O: fr.O, u: fr.pf.u, b: fr.pf.b, e: fr.pf.e, zoff: 0}, ref: refFrame(fr.spec), axisOf: axisOf}, extra || {});
    }
    function rasterKey(spec, q) { return [S.probe, probeW(), S.depthCm, S.P.map(function (x) { return x.toFixed(2); }).join(), S.N.map(function (x) { return x.toFixed(4); }).join(), spec.tilt, spec.dir, spec.off, spec.rotOverride != null ? spec.rotOverride : S.rot, S.refKey, q.maxDim, q.maxLines, S.hidden ? 1 : 0].join("|"); }
    function computeFrame(spec, q, prev) {                                    // -> Promise(frame)
      var pose = poseOf(spec), geom = curGeom(), plan = LIB.planRaster(geom, q.maxDim, {maxLines: q.maxLines});
      var fr = {spec: spec, pf: pose.pf, O: pose.O, shift: pose.shift, geom: geom, plan: plan, lab: null, sid: null, rk: rasterKey(spec, q), sim: null, ms: 0, kms: 0};
      fr.sig = [S.freq, S.depthCm, S.tgc, S.focusCm, S.speckle, S.textures, S.reverb, S.noise, S.seed, S.mode].join("|");
      if (prev && prev.sim && prev.rk === fr.rk && prev.sig === fr.sig) return Promise.resolve(prev);
      var t0 = Date.now(), pr;
      if (prev && prev.rk === fr.rk && prev.lab) { fr.lab = prev.lab; fr.sid = prev.sid; pr = Promise.resolve(); }
      else {
        var u = pose.pf.u, v = pose.pf.N, n = LIB.cross(u, v);
        var R = {key: "us" + (++keySeq), W: plan.W, H: plan.H, O: pose.O, u: u, v: v, n: n, u0: plan.xr0, v0: -plan.yr0, px: plan.px, smin: 0, smax: 0, s: 0, wantSid: true,
          skinMm: T.bone_model.skin_thickness_mm, ids: C.ids, bone: sh.boneParams(), mask: S.hidden ? visMask() : null, extTop: true};
        pr = sh.runSlice(R).then(function (r) { fr.lab = r.lab; fr.sid = r.sid; fr.kms = r.ms; });
      }
      return pr.then(function () {
        var tS = Date.now();
        fr.sim = LIB.simulate(simOpts(fr)); fr.simMs = Date.now() - tS; fr.ms = Date.now() - t0;
        return fr;
      });
    }
    var pumpTimer = null, pumpPending = false;
    function refresh(immediate) {
      clearTimeout(pumpTimer); pumpPending = true;
      pumpTimer = setTimeout(pump, immediate ? 0 : 70);
    }
    function pump() {
      pumpPending = false;
      if (!S.open || !AC || !S.P || contState.active) return;                 // Q257: continuous cine owns frames[S.sel] directly; the step pipeline stays out of its way while it plays

      var my = ++gen, specs = frameSpecs(), order = [], i, tAll = Date.now();
      ensureViews(specs);
      for (i = 0; i < specs.length; i++) order.push(i);
      order.sort(function (a, b) { return (a === S.sel ? -1 : 0) - (b === S.sel ? -1 : 0); });
      if (S.mode === "sweep" && S.view === "single") { /* only the selected frame is shown; the rest is computed afterwards for the matrix / cine */ }
      busy = true; setStatus("Simulating " + specs.length + " frame" + (specs.length > 1 ? "s" : "") + " ...");
      var k = 0, newFrames = new Array(specs.length);
      (function next() {
        if (my !== gen) return;
        if (k >= order.length) {
          frames = newFrames; busy = false; perf.last = {n: specs.length, ms: Date.now() - tAll, per: newFrames.map(function (f) { return f.ms; })}; perf.hist.push(perf.last); if (perf.hist.length > 40) perf.hist.shift();
          setStatus(); updateOverlay(); return;
        }
        var idx = order[k++], prev = frames[idx];
        computeFrame(specs[idx], quality(idx), prev && prev.spec.id === specs[idx].id ? prev : null).then(function (fr) {
          if (my !== gen) return;
          newFrames[idx] = fr; paintView(idx, fr);
          setTimeout(next, 0);
        }, function (err) { busy = false; console.error("ultrasound frame:", err); setStatus("error: " + (err && err.message || err)); });
      })();
    }
    function repaintAll() { frames.forEach(function (fr, i) { if (fr) paintView(i, fr); }); }

    /* ---------- 3D overlay (probe, image plane(s)) ---------- */
    function Geo() { this.pos = []; this.nrm = []; this.idx = []; }
    Geo.prototype.count = function () { return this.idx.length; };
    Geo.prototype.tri = function (a, b, c) {
      var n = LIB.cross(sub3(b, a), sub3(c, a)), l = Math.hypot(n[0], n[1], n[2]) || 1, base = this.pos.length / 3;
      [a, b, c].forEach(function (p) { this.pos.push(p[0], p[1], p[2]); this.nrm.push(n[0] / l, n[1] / l, n[2] / l); }, this);
      this.idx.push(base, base + 1, base + 2);
    };
    function sub3(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
    function tube(g, a, b, r) {                                               // 4-sided prism along a-b
      var d = LIB.unit(sub3(b, a)), t = Math.abs(d[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0], e1 = LIB.unit(LIB.cross(d, t)), e2 = LIB.cross(d, e1), ring = [[1, 0], [0, 1], [-1, 0], [0, -1]], i;
      function pt(p, q) { return [p[0] + (e1[0] * ring[q][0] + e2[0] * ring[q][1]) * r, p[1] + (e1[1] * ring[q][0] + e2[1] * ring[q][1]) * r, p[2] + (e1[2] * ring[q][0] + e2[2] * ring[q][1]) * r]; }
      for (i = 0; i < 4; i++) { var j = (i + 1) % 4, a0 = pt(a, i), a1 = pt(a, j), b0 = pt(b, i), b1 = pt(b, j); g.tri(a0, a1, b0); g.tri(a1, b1, b0); }
    }
    function fanOutline(geom, nArc) {                                         // plane coordinates (x, y) of the image outline
      var pts = [], i, th;
      if (geom.type === "linear") return [[-geom.w / 2, 0], [geom.w / 2, 0], [geom.w / 2, geom.depth], [-geom.w / 2, geom.depth]];
      for (i = 0; i <= nArc; i++) { th = -geom.alpha + 2 * geom.alpha * i / nArc; pts.push([geom.R * Math.sin(th), geom.R * Math.cos(th) - geom.R]); }
      for (i = nArc; i >= 0; i--) { th = -geom.alpha + 2 * geom.alpha * i / nArc; pts.push([(geom.R + geom.depth) * Math.sin(th), (geom.R + geom.depth) * Math.cos(th) - geom.R]); }
      return pts;
    }
    function toWorld(O, pf, x, y, z) { return [O[0] + pf.u[0] * x + pf.b[0] * y + pf.e[0] * (z || 0), O[1] + pf.u[1] * x + pf.b[1] * y + pf.e[1] * (z || 0), O[2] + pf.u[2] * x + pf.b[2] * y + pf.e[2] * (z || 0)]; }
    function probeMesh(g, O, pf, geom) {                                      // profile in the image plane, extruded along the short axis
      var w = geom.w, thick = geom.type === "linear" ? 14 : geom.type === "convex" ? 22 : 16, h = 42, prof = [], i;
      if (geom.type === "convex") { for (i = 0; i <= 12; i++) { var th = -geom.alpha + 2 * geom.alpha * i / 12; prof.push([geom.R * Math.sin(th), geom.R * Math.cos(th) - geom.R]); } }
      else if (geom.type === "sector") { prof.push([-w / 2, 0], [w / 2, 0]); }
      else prof.push([-w / 2, 0], [w / 2, 0]);
      var bw = geom.type === "sector" ? w * 0.9 : w, top = [[bw / 2, -h], [-bw / 2, -h]];
      var poly = prof.concat([[prof[prof.length - 1][0] * 1.0, prof[prof.length - 1][1] - 3]], top, [[prof[0][0], prof[0][1] - 3]]);
      var n = poly.length, hz = thick / 2, A = [], B = [];
      for (i = 0; i < n; i++) { A.push(toWorld(O, pf, poly[i][0], poly[i][1], -hz)); B.push(toWorld(O, pf, poly[i][0], poly[i][1], hz)); }
      for (i = 0; i < n; i++) { var j = (i + 1) % n; g.tri(A[i], A[j], B[i]); g.tri(A[j], B[j], B[i]); }
      var cA = [0, 0, 0], cB = [0, 0, 0]; for (i = 0; i < n; i++) for (var q = 0; q < 3; q++) { cA[q] += A[i][q] / n; cB[q] += B[i][q] / n; }
      for (i = 0; i < n; i++) { var j2 = (i + 1) % n; g.tri(cA, A[i], A[j2]); g.tri(cB, B[j2], B[i]); }
    }
    function markerMesh(g, O, pf, geom) {
      var x = -geom.w / 2 + 2.5, c = toWorld(O, pf, x, -4, (geom.type === "linear" ? 14 : geom.type === "convex" ? 22 : 16) / 2 + 0.3), d = toWorld(O, pf, x, -9, (geom.type === "linear" ? 14 : 22) / 2 + 0.3);
      tube(g, c, d, 1.6);
    }
    function overlayItems() {
      if (!S.open || !S.P || !frames.length) return null;
      var vw = api.view(), dist = Math.hypot(vw.eye[0] - vw.target[0], vw.eye[1] - vw.target[1], vw.eye[2] - vw.target[2]), r = Math.max(0.5, Math.min(3, dist / 900));
      var sel = frames[S.sel] || frames[0]; if (!sel) return null;
      var probeG = new Geo(), markG = new Geo(), fillG = new Geo(), lineG = new Geo(), selLine = new Geo(), axisG = new Geo();
      probeMesh(probeG, sel.O, sel.pf, sel.geom); markerMesh(markG, sel.O, sel.pf, sel.geom);
      frames.forEach(function (fr, i) {
        if (!fr) return;
        var out = fanOutline(fr.geom, 14).map(function (p) { return toWorld(fr.O, fr.pf, p[0], p[1] + (fr.sim ? fr.sim.ysk : 0)); }), n = out.length, j;
        var target = i === S.sel ? selLine : lineG;
        for (j = 0; j < n; j++) tube(target, out[j], out[(j + 1) % n], i === S.sel ? r * 1.0 : r * 0.55);
        if (i === S.sel || S.mode === "sweep") {
          var cen = [0, 0, 0]; out.forEach(function (p) { cen[0] += p[0] / n; cen[1] += p[1] / n; cen[2] += p[2] / n; });
          if (i === S.sel) for (j = 0; j < n; j++) fillG.tri(cen, out[j], out[(j + 1) % n]);
        }
        if (i === S.sel) tube(axisG, toWorld(fr.O, fr.pf, 0, -20 + (fr.sim ? fr.sim.ysk : 0)), toWorld(fr.O, fr.pf, 0, fr.geom.depth + (fr.sim ? fr.sim.ysk : 0)), r * 0.45);
      });
      return [["probe", probeG, {color: 0x39424d, alpha: 1, pass: "opaque", lit: true}], ["marker", markG, {color: 0xff5a3c, alpha: 1, pass: "opaque", lit: false}],
        ["fill", fillG, {color: 0x6cb4ff, alpha: 0.28, pass: "trans", lit: false}], ["lines", lineG, {color: 0xffd37a, alpha: 0.8, pass: "xray", lit: false}],
        ["sel", selLine, {color: 0x7fe0a0, alpha: 1, pass: "xray", lit: false}], ["axis", axisG, {color: 0xff9d8a, alpha: 0.9, pass: "xray", lit: false}]];
    }
    function updateOverlay() {
      if (!overlay) overlay = makeOverlay(api);
      if (!overlay) return;
      var items = null; try { items = overlayItems(); } catch (e) { console.error("ultrasound overlay:", e); }
      ["probe", "marker", "fill", "lines", "sel", "axis"].forEach(function (nm) { overlay.remove(nm); });
      if (items) items.forEach(function (it) { overlay.set(it[0], [it[1]], it[2]); });
      if (api.redraw) api.redraw();
    }
    function clearOverlay() { if (!overlay) return; ["probe", "marker", "fill", "lines", "sel", "axis"].forEach(function (nm) { overlay.remove(nm); }); if (api.redraw) api.redraw(); }
    function makeOverlay(a) {
      if (a.three && a.three.THREE) return ThreeOverlay(a);
      if (a.webgl && a.webgl.gl) { try { return GLOverlay(a); } catch (e) { console.error("ultrasound GL overlay:", e); } }
      return null;
    }
    function ThreeOverlay(a) {
      var Th = a.three.THREE, rt = a.three.root, items = {};
      return {
        set: function (name, geos, spec) {
          this.remove(name);
          items[name] = geos.filter(function (g) { return g && g.count(); }).map(function (g) {
            var bg = new Th.BufferGeometry();
            bg.setAttribute("position", new Th.Float32BufferAttribute(g.pos, 3)); bg.setAttribute("normal", new Th.Float32BufferAttribute(g.nrm, 3));
            bg.setIndex(g.count() > 65535 ? new Th.Uint32BufferAttribute(g.idx, 1) : new Th.Uint16BufferAttribute(g.idx, 1)); bg.computeBoundingSphere();
            var col = new Th.Color(spec.color), m = spec.lit === false ? new Th.MeshBasicMaterial({color: col}) : new Th.MeshPhongMaterial({color: col, shininess: 40, specular: new Th.Color(0x555555)});
            m.side = Th.DoubleSide; m.opacity = spec.alpha == null ? 1 : spec.alpha; m.transparent = spec.pass !== "opaque" || m.opacity < 1; m.depthTest = spec.pass !== "xray"; m.depthWrite = spec.pass === "opaque";
            var mesh = new Th.Mesh(bg, m); mesh.renderOrder = spec.pass === "xray" ? 1000 : spec.pass === "trans" ? 900 : 0; mesh.frustumCulled = false; mesh.userData.overlay = true;
            rt.add(mesh); return mesh;
          });
        },
        remove: function (name) { (items[name] || []).forEach(function (m) { rt.remove(m); m.geometry.dispose(); m.material.dispose(); }); delete items[name]; }
      };
    }
    function GLOverlay(a) {
      var gl = a.webgl.gl, items = {}, U = {};
      var VS = "attribute vec3 aPos;attribute vec3 aNrm;uniform mat4 uMVP;varying vec3 vN;varying vec3 vP;void main(){vN=aNrm;vP=aPos;gl_Position=uMVP*vec4(aPos,1.0);}";
      var FS = "#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\nvarying vec3 vN;varying vec3 vP;uniform vec3 uColor;uniform vec3 uEye;uniform float uAlpha;uniform float uLit;" +
        "void main(){vec3 n=normalize(vN);vec3 v=normalize(uEye-vP);if(dot(n,v)<0.0)n=-n;vec3 l=normalize(v+vec3(0.3,0.55,0.2));float d=max(dot(n,l),0.0);" +
        "vec3 c=uLit>0.5?uColor*(0.30+0.72*d):uColor;gl_FragColor=vec4(c,uAlpha);}";
      function sh2(t, s) { var o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o); if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; }
      var prog = gl.createProgram(); gl.attachShader(prog, sh2(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh2(gl.FRAGMENT_SHADER, FS));
      gl.bindAttribLocation(prog, 0, "aPos"); gl.bindAttribLocation(prog, 1, "aNrm"); gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      ["uMVP", "uColor", "uEye", "uAlpha", "uLit"].forEach(function (nm) { U[nm] = gl.getUniformLocation(prog, nm); });
      function rgb(h) { return [((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255]; }
      function buf(type, data) { var b = gl.createBuffer(); gl.bindBuffer(type, b); gl.bufferData(type, data, gl.STATIC_DRAW); return b; }
      var self = {
        set: function (name, geos, spec) {
          this.remove(name);
          items[name] = geos.filter(function (g) { return g && g.count() && g.pos.length / 3 < 65535; }).map(function (g) {
            return {vb: buf(gl.ARRAY_BUFFER, new Float32Array(g.pos)), nb: buf(gl.ARRAY_BUFFER, new Float32Array(g.nrm)), ib: buf(gl.ELEMENT_ARRAY_BUFFER, new Uint16Array(g.idx)), count: g.idx.length, spec: spec, rgb: rgb(spec.color)};
          });
        },
        remove: function (name) { (items[name] || []).forEach(function (b) { gl.deleteBuffer(b.vb); gl.deleteBuffer(b.nb); gl.deleteBuffer(b.ib); }); delete items[name]; }
      };
      function drawItem(b) {
        gl.uniform3f(U.uColor, b.rgb[0], b.rgb[1], b.rgb[2]); gl.uniform1f(U.uAlpha, b.spec.alpha == null ? 1 : b.spec.alpha); gl.uniform1f(U.uLit, b.spec.lit === false ? 0 : 1);
        gl.bindBuffer(gl.ARRAY_BUFFER, b.vb); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0); gl.bindBuffer(gl.ARRAY_BUFFER, b.nb); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
        gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, b.ib); gl.drawElements(gl.TRIANGLES, b.count, gl.UNSIGNED_SHORT, 0);
      }
      a.webgl.onAfterDraw(function (ctx) {
        var all = []; Object.keys(items).forEach(function (k) { all = all.concat(items[k]); });
        if (!all.length) return;
        gl.useProgram(prog); gl.uniformMatrix4fv(U.uMVP, false, ctx.mvp); gl.uniform3f(U.uEye, ctx.eye[0], ctx.eye[1], ctx.eye[2]);
        gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1); gl.disable(gl.CULL_FACE); gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
        all.filter(function (b) { return b.spec.pass === "opaque"; }).forEach(drawItem);
        gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false);
        all.filter(function (b) { return b.spec.pass === "trans"; }).forEach(drawItem);
        gl.disable(gl.DEPTH_TEST);
        all.filter(function (b) { return b.spec.pass === "xray"; }).forEach(drawItem);
        gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
      });
      return self;
    }

    /* ====================================================================================================
     * UI
     * ================================================================================================== */
    var CSS = [
      "#us-root{--bg:#0e131a;--panel:#161d27;--line:#2a3646;--ink:#e6edf5;--dim:#98a6b8;--acc:#6cb4ff;--warn:#ff9d8a;position:fixed;z-index:81;background:var(--bg);color:var(--ink);font:13px/1.35 system-ui,-apple-system,Segoe UI,sans-serif;display:none;flex-direction:column;min-width:0;min-height:0;box-sizing:border-box;color-scheme:dark}",
      "#us-root *{box-sizing:border-box}",
      "body.nmsk-us #us-root{display:flex}",
      "body.nmsk-us.us-side #us-root{top:0;right:0;bottom:0;width:var(--us-w,50vw);border-left:1px solid var(--line)}",
      "body.nmsk-us.us-stack #us-root{left:0;right:0;bottom:0;height:var(--us-h,62vh);border-top:1px solid var(--line)}",
      "body.nmsk-us.us-tab #us-root{inset:0}",
      "body.nmsk-us.us-tab.us-t3d #us-root{display:none}",
      "body.nmsk-us.us-side #app{width:calc(100vw - var(--us-w,50vw))!important;grid-template-columns:minmax(0,1fr)!important;overflow:hidden}",
      "body.nmsk-us.us-side #app aside,body.nmsk-us.us-side #app #inspector,body.nmsk-us.us-stack #app:not(.phone) aside,body.nmsk-us.us-stack #app:not(.phone) #inspector{display:none!important}",
      "body.nmsk-us.us-stack #app:not(.phone){grid-template-columns:minmax(0,1fr)!important}",
      "body.nmsk-us.us-stack #app{height:calc(100vh - var(--us-h,62vh))!important;min-height:0}",
      "body.nmsk-us.us-side.us-z #view{width:calc(100vw - var(--us-w,50vw))!important;right:auto!important}",
      "body.nmsk-us.us-stack.us-z #view{height:calc(100vh - var(--us-h,62vh))!important;bottom:auto!important}",
      "body.nmsk-us.us-side.us-z #topright{right:calc(var(--us-w,50vw) + .9rem)!important}",
      "body.nmsk-us.us-side.us-z #cut-panel{right:calc(var(--us-w,50vw) + 12px)!important}",
      "@media (max-width:1300px){body.nmsk-us.us-side.us-z #topright{top:calc(2.7rem + var(--safe-t,0px))!important}}",
      "#us-div{position:absolute;z-index:3;background:transparent}",
      "body.us-side #us-div{left:-5px;top:0;bottom:0;width:10px;cursor:col-resize}",
      "body.us-stack #us-div{top:-5px;left:0;right:0;height:10px;cursor:row-resize}",
      "body.us-tab #us-div{display:none}",
      "#us-div:hover,#us-div.drag{background:rgba(108,180,255,.35)}",
      ".us-head{display:flex;align-items:center;gap:6px;padding:6px 8px;border-bottom:1px solid var(--line);flex:0 0 auto;flex-wrap:wrap}",
      ".us-head b{font-size:14px}",
      ".us-badge{background:#3a1f1a;color:var(--warn);border:1px solid #7a3a2f;border-radius:999px;padding:2px 9px;font-weight:700;font-size:11.5px;letter-spacing:.02em}",
      ".us-sp{flex:1 1 8px}",
      "#us-root button,#us-root select,#us-root input{font:inherit;color:inherit}",
      "#us-root button{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:5px 9px;cursor:pointer;min-height:30px}",
      "#us-root button:hover{border-color:var(--acc)}",
      "#us-root button[aria-pressed=true],#us-root button.on{background:#1f3b5c;border-color:var(--acc);color:#fff}",
      "#us-root button:disabled{opacity:.45;cursor:default}",
      "#us-root select,#us-root input[type=number]{background:var(--panel);border:1px solid var(--line);border-radius:7px;padding:4px 6px;min-height:30px}",
      "#us-root input[type=range]{width:100%;accent-color:var(--acc);min-height:24px}",
      ".us-views{flex:1 1 0;min-height:0;display:grid;gap:4px;padding:4px;background:#000;position:relative}",
      ".us-views.star{grid-template-columns:1fr 2fr 1fr;grid-template-rows:1fr 2fr 1fr}",
      ".us-views.single{grid-template-columns:1fr;grid-template-rows:1fr}",
      ".us-view{position:relative;min-width:0;min-height:0;overflow:hidden;background:#000;border:1px solid #1d2733;touch-action:manipulation;cursor:pointer}",
      ".us-view.us-act{border-color:var(--acc)}",
      ".us-view canvas{position:absolute;image-rendering:auto}",
      ".us-view .ann{pointer-events:none;left:0;top:0}",
      ".us-schem{position:absolute;left:6px;top:6px;width:84px;height:84px;background:rgba(10,14,20,.88);border:1px solid #2a3542;border-radius:7px;z-index:5;display:none;pointer-events:none}",
      "#us-root.ctl-off .us-ctl{display:none}",
      ".us-ctl .sec{display:contents}.us-ctl .sectabs{display:none;gap:4px;flex-wrap:wrap}.us-ctl .modrow{grid-column:1/-1}",
      "#us-root.ctl-tabs .us-ctl{grid-template-columns:1fr;max-height:36%}",
      "#us-root.ctl-tabs .sectabs{display:flex}",
      "#us-root.ctl-tabs .sec{display:grid;gap:6px}",
      "#us-root.ctl-tabs .sec:not(.us-act){display:none}",
      /* Q264: overscroll-behavior:contain -- a touch-drag that scrolls this panel to its own boundary must not chain
         into the page/canvas beneath it (see PROJECT_STATE.md Q264). */
      ".us-ctl{flex:0 0 auto;max-height:46%;overflow:auto;overscroll-behavior:contain;padding:6px 8px 8px;border-top:1px solid var(--line);display:grid;gap:6px 14px;background:var(--bg);grid-template-columns:repeat(auto-fit,minmax(380px,1fr));align-content:start}",
      ".us-ctl>.us-status{grid-column:1/-1}",
      "body.us-tab .us-ctl{max-height:40%}",
      ".us-row{display:flex;gap:5px;align-items:center;flex-wrap:wrap}",
      ".us-row label{color:var(--dim);font-size:12px}",
      ".us-row .grow{flex:1 1 120px;min-width:90px}",
      ".us-row output{min-width:3.4em;color:#cfe6ff;font:12px ui-monospace,Menlo,monospace}",
      ".us-read{font:12px/1.3 ui-monospace,Menlo,monospace;color:#cfe6ff;min-height:32px;padding:3px 8px;border-top:1px solid var(--line);flex:0 0 auto;word-break:break-word;max-height:3.9em;overflow:hidden}",
      ".us-status{color:var(--dim);font-size:11.5px}",
      ".us-info{position:absolute;inset:36px 0 0 0;background:var(--bg);z-index:5;overflow:auto;overscroll-behavior:contain;padding:10px 12px 40px;display:none}",
      ".us-info.show{display:block}",
      ".us-info h3{margin:14px 0 4px;font-size:14px}.us-info p,.us-info li{color:#c3cfdd}",
      ".us-info table{border-collapse:collapse;width:100%;font-size:11.5px;margin:4px 0}.us-info td,.us-info th{border:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}",
      ".us-info .st-verified_abstract{color:#7fe0a0}.us-info .st-secondary_checked{color:#d9e58a}.us-info .st-recalled_unverified{color:#ffb38a}.us-info .st-derived{color:#9fd0ff}.us-info .st-assumption{color:#c9b8ff}.us-info .st-owner_supplied{color:#ffe08a}",
      "#us-tab3d{position:fixed;z-index:91;right:8px;top:8px;display:none;gap:4px}",
      "body.nmsk-us.us-tab.us-t3d #us-tab3d{display:flex}",
      "#us-tab3d button{background:#161d27;color:#e6edf5;border:1px solid #2a3646;border-radius:999px;padding:6px 12px;min-height:34px;font:600 13px system-ui}",
      "#us-tab3d button[aria-pressed=true]{background:#1f3b5c;border-color:#6cb4ff}",
      ".us-diag{flex:0 0 auto;padding:2px 8px;font-size:11px;color:var(--dim);border-bottom:1px solid var(--line);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      ".us-diag.bad{color:var(--warn);white-space:normal}",
      ".us-hint{flex:0 0 auto;padding:6px 8px;font-size:12px;background:#12263b;border-bottom:1px solid var(--acc);color:var(--ink)}",
      ".us-hint button{min-height:24px!important;padding:1px 8px!important;margin-left:6px}",
      "@media (max-width:520px),(max-height:520px){#us-root button{min-height:36px}#us-root select,#us-root input[type=number]{min-height:36px}}"
    ].join("\n");
    function el(tag, attrs, kids) {
      var e = document.createElement(tag);
      if (attrs) Object.keys(attrs).forEach(function (k) {
        if (k === "text") e.textContent = attrs[k]; else if (k === "html") e.innerHTML = attrs[k];
        else if (k.slice(0, 2) === "on") e.addEventListener(k.slice(2), attrs[k]); else e.setAttribute(k, attrs[k]);
      });
      (function addk(list) { list.forEach(function (c) { if (Array.isArray(c)) addk(c); else if (c) e.appendChild(c); }); })(kids || []);
      return e;
    }
    function chooseLayout() {
      var w = window.innerWidth, h = window.innerHeight;
      if (S.lay !== "auto") return S.lay;
      if (Math.min(w, h) < 520) return "tab";
      return w >= h ? "side" : "stack";
    }
    function fireResize() { firing = true; try { window.dispatchEvent(new Event("resize")); } catch (e) {} firing = false; }
    function applyLayout() {
      var lay = chooseLayout(), b = document.body;
      ["us-side", "us-stack", "us-tab"].forEach(function (c) { b.classList.remove(c); });
      b.classList.toggle("nmsk-us", S.open);
      if (!S.open) { b.classList.remove("us-t3d"); b.classList.remove("us-z"); fireResize(); return; }
      b.classList.add("us-" + lay);
      b.classList.toggle("us-t3d", lay === "tab" && S.tab === "3d");
      b.classList.toggle("us-z", api.kind === "webgl");
      fireResize(); fitControls();
      setTimeout(function () { fitControls(); relayoutViews(); }, 60);
    }
    function fitControls() { if (!root) return; var h = root.getBoundingClientRect().height; root.classList.toggle("ctl-tabs", h > 0 && h < 1000); }

    function build() {
      if (root) return;
      var st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st);
      root = el("div", {id: "us-root", role: "region", "aria-label": "Ultrasound: simulated B-mode"});
      var head = el("div", {class: "us-head"}, [
        el("b", {text: "Ultrasound"}), el("span", {class: "us-badge", text: BADGE}), el("span", {class: "us-sp"}),
        (ui.layBtn = el("button", {type: "button", title: "Layout: auto / side by side / stacked / tabs", onclick: cycleLayout, text: "◫"})),
        (ui.ctlBtn = el("button", {type: "button", title: "Show / hide the controls (more room for the images)", "aria-pressed": "true", onclick: function () { var off = root.classList.toggle("ctl-off"); ui.ctlBtn.setAttribute("aria-pressed", String(!off)); setTimeout(relayoutViews, 50); }, text: "Controls"})),
        el("button", {type: "button", title: "Assumptions, acoustic table, sources and limits of the simulation", onclick: function () { ui.info.classList.toggle("show"); }, text: "Info"}),
        el("button", {type: "button", title: "Save the selected image as PNG (with the badge)", onclick: savePng, text: "PNG"}),
        el("button", {type: "button", title: "Close ultrasound", "aria-label": "Close ultrasound", onclick: function () { setOpen(false); }, text: "✕"})
      ]);
      ui.info = el("div", {class: "us-info"});
      ui.diag = el("div", {class: "us-diag"}); ui.hint = el("div", {class: "us-hint", role: "note"}); ui.hint.style.display = "none";
      ui.views = el("div", {class: "us-views star"});
      ui.schem = el("canvas", {class: "us-schem", width: "84", height: "84", "aria-hidden": "true"}); ui.views.appendChild(ui.schem);
      ui.read = el("div", {class: "us-read", text: "Click the skin in the 3D view to place the probe; hover an image for tissue, structure, depth and echo level."});
      ui.ctl = el("div", {class: "us-ctl"}); buildControls(ui.ctl);
      var div = el("div", {id: "us-div", title: "Drag to resize"});
      div.addEventListener("pointerdown", function (e) {
        div.setPointerCapture(e.pointerId); div.classList.add("drag");
        var mv = function (ev) {
          if (document.body.classList.contains("us-side")) document.documentElement.style.setProperty("--us-w", Math.max(300, Math.min(window.innerWidth - 280, window.innerWidth - ev.clientX)) + "px");
          else document.documentElement.style.setProperty("--us-h", Math.max(220, Math.min(window.innerHeight - 200, window.innerHeight - ev.clientY)) + "px");
          clearTimeout(timers.rs); timers.rs = setTimeout(function () { fireResize(); relayoutViews(); }, 60);
        };
        var up = function () { div.classList.remove("drag"); div.removeEventListener("pointermove", mv); div.removeEventListener("pointerup", up); };
        div.addEventListener("pointermove", mv); div.addEventListener("pointerup", up);
      });
      [div, head, ui.diag, ui.hint, ui.info, ui.views, ui.read, ui.ctl].forEach(function (x) { root.appendChild(x); });
      document.body.appendChild(root);
      var tabs = el("div", {id: "us-tab3d"}, [el("button", {type: "button", text: "3D", "aria-pressed": "true"}), el("button", {type: "button", text: "Place probe", onclick: function () { S.placing = true; syncUi(); setStatus("Tap the skin to place the probe."); }}),
        el("button", {type: "button", text: "Image ▸", onclick: function () { S.tab = "image"; applyLayout(); relayoutViews(); }})]);
      document.body.appendChild(tabs); ui.tabs = tabs;
      head.insertBefore(ui.to3d = el("button", {type: "button", text: "◂ 3D", title: "Back to the 3D model", onclick: function () { S.tab = "3d"; applyLayout(); }}), head.children[1]);
      window.addEventListener("resize", function () { if (S.open && !firing) { applyLayout(); updateLayoutUi(); } });
    }
    function cycleLayout() {
      var seq = ["auto", "side", "stack", "tab"]; S.lay = seq[(seq.indexOf(S.lay) + 1) % seq.length]; S.tab = "image"; applyLayout(); updateLayoutUi();
      ui.layBtn.title = "Layout: " + S.lay; setStatus("layout: " + S.lay);
    }
    function updateLayoutUi() { if (ui.to3d) ui.to3d.style.display = chooseLayout() === "tab" ? "" : "none"; }

    function slider(label, min, max, step, key, fmt, onchg, title) {
      var out = el("output", {text: ""}), inp = el("input", {type: "range", min: String(min), max: String(max), step: String(step), class: "grow", "aria-label": title || label});
      inp.addEventListener("input", function () { onchg(+inp.value); out.textContent = fmt(+inp.value); });
      ui[key] = inp; ui[key + "Out"] = out; ui[key + "Fmt"] = fmt;
      return el("div", {class: "us-row"}, [el("label", {text: label}), inp, out]);
    }
    function setSlider(key, v) { if (ui[key]) { ui[key].value = String(v); ui[key + "Out"].textContent = ui[key + "Fmt"](v); } }
    function btn(text, title, fn, extra) { return el("button", Object.assign({type: "button", text: text, title: title || "", onclick: fn}, extra || {})); }

    function buildControls(ctl) {
      var mrow = el("div", {class: "us-row modrow"}, [
        (ui.modeBtn1 = btn("1 · 90° + tilt star", "Mode 1: the probe perpendicular to the skin as the big central image, surrounded by images tilted in the main directions", function () { setMode("star"); })),
        (ui.modeBtn2 = btn("2 · tilt + sweep", "Mode 2: set position, tilt and rotation, then a series of parallel image planes along the sweep direction", function () { setMode("sweep"); })),
        el("span", {class: "us-sp"}),
        (ui.secTabs = el("div", {class: "sectabs"}, [["probe", "Probe"], ["mode", "Mode"], ["image", "Image"], ["more", "More"]].map(function (d) { return el("button", {type: "button", "data-sec": d[0], text: d[1], onclick: function () { setSec(d[0]); }}); })))
      ]);
      /* probe section */
      ui.probeBtns = {};
      var r1 = el("div", {class: "us-row"}, [
        ["linear", "convex", "sector"].map(function (k) { return (ui.probeBtns[k] = btn(k === "linear" ? "Linear" : k === "convex" ? "Convex" : "Sector", k === "linear" ? "Linear array, 38-50 mm footprint" : k === "convex" ? "Curvilinear, 60-70 mm footprint" : "Phased-array sector, 20-25 mm footprint", function () { setProbe(k); })); }),
        el("label", {text: "width"}), (ui.widthSel = el("select", {"aria-label": "Probe footprint width in mm", onchange: function () { S.widths[S.probe] = +ui.widthSel.value; refresh(); }}))
      ]);
      ui.freqBtns = {};
      var r2 = el("div", {class: "us-row"}, [el("label", {text: "MHz"}), [3.5, 5, 7.5, 12].map(function (f) { return (ui.freqBtns[f] = btn(String(f), "Frequency preset: higher = finer resolution, more attenuation, less depth", function () { S.freq = f; syncUi(); refresh(); })); })]);
      var r3 = slider("Depth", 2, 15, 0.5, "depth", function (v) { return v.toFixed(1) + " cm"; }, function (v) { S.depthCm = v; if (S.focusCm > v) { S.focusCm = v * 0.6; setSlider("focus", S.focusCm); } refresh(); }, "Depth in cm");
      ui.placeBtn = btn("Place on skin", "Arm, then click / tap the skin in the 3D view", function () { S.placing = !S.placing; syncUi(); setStatus(S.placing ? "Click or tap the skin in the 3D view." : ""); });
      var r4 = el("div", {class: "us-row"}, [ui.placeBtn, btn("Screen centre", "Put the probe on the skin at the centre of the 3D view", function () { defaultPlacement(true); S.sel = 0; refresh(true); }),
        (ui.orLong = btn("Longitudinal", "Long axis along the body / limb axis, marker cranial (screen left = cranial)", function () { S.refKey = "long"; S.rot = 0; syncUi(); refresh(); })),
        (ui.orTrans = btn("Transverse", "Long axis across, marker to the patient's right (screen left = patient right)", function () { S.refKey = "trans"; S.rot = 0; syncUi(); refresh(); })),
        btn("Zoom to probe", "Move the 3D camera close to the probe", function () { if (S.P) { api.focus(S.P, 420); } })]);
      var r5 = slider("Rotate", 0, 359, 1, "rot", function (v) { return Math.round(v) + "°"; }, function (v) { S.rot = v; refresh(); }, "Free rotation of the probe about the skin normal");
      /* Q255: CW/CCW nudge buttons beside the free-rotation slider -- "rotate the probe" reads as a relative turn (as when
         rotating from a short-axis to a long-axis view), not just an absolute 0-359 dial; this is the honest fix (unlike
         tilt direction, free rotation has no natural handful of discrete landmark positions to offer as preset buttons, so
         a nudge pair is the right idiom here, matching rotateBy()'s own wraparound rather than the plain slider's clamp).
         Sense verified against LIB.probeFrame/rodrigues: N is the OUTWARD skin normal, so by the right-hand rule increasing
         S.rot turns counter-clockwise as seen by the examiner looking down the normal at the probe on the skin. */
      r5.appendChild(btn("⟲ CCW", "Rotate the probe 5° counter-clockwise about the skin normal (as seen looking down at the probe on the skin)", function () { rotateBy(5); }));
      r5.appendChild(btn("CW ⟳", "Rotate the probe 5° clockwise about the skin normal (as seen looking down at the probe on the skin)", function () { rotateBy(-5); }));
      /* mode section */
      ui.starBox = el("div", {style: "display:grid;gap:6px"}, [slider("Tilt", 5, 30, 1, "tilt", function (v) { return v + "°"; }, function (v) { S.tilt = v; drawSchematic(); refresh(); }, "Tilt angle of the surrounding images"),
        el("div", {class: "us-status", text: "Centre = 90° to the skin. Ring = the handle leaning towards (clockwise from the right): away from marker (rock), away + heel, heel, toward + heel, toward marker (rock), toward + toe, toe, away + toe. Click a ring image to make it the main image."})]);
      ui.dirBtns = {};
      ui.sweepBox = el("div", {style: "display:grid;gap:6px"}, [
        slider("Tilt", 0, 45, 1, "mtilt", function (v) { return v + "°"; }, function (v) { S.mTilt = v; refresh(); }, "Tilt angle of the image plane"),
        slider("Direction", 0, 359, 5, "mdir", function (v) { return Math.round(v) + "°"; }, function (v) { S.mTiltDir = v; refresh(); }, "Direction in which the handle leans (0 = away from marker, 90 = heel, 180 = toward marker, 270 = toe)"),
        el("div", {class: "us-row"}, [[["away", 0], ["heel", 90], ["toward", 180], ["toe", 270]].map(function (d) { return (ui.dirBtns[d[1]] = btn(d[0], "Handle leans " + d[0] + (d[1] % 180 ? " (fan: the plane swings sideways)" : " the marker (rock: inside the image plane)"), function () { S.mTiltDir = d[1]; syncUi(); refresh(); })); })]),
        el("div", {class: "us-row"}, [el("label", {text: "Frames"}), (ui.nSel = el("select", {"aria-label": "Number of frames 3 to 9", onchange: function () { S.n = +ui.nSel.value; S.sel = Math.min(S.sel, S.n - 1); refresh(true); }}, [3, 4, 5, 6, 7, 8, 9].map(function (n) { var d = LIB.matrixDims(n); return el("option", {value: String(n), text: n + " (" + d[0] + "×" + d[1] + ")"}); }))),
          (ui.byBtn = btn("by step", "Switch between giving the step between frames and the total distance", function () { S.byTotal = !S.byTotal; syncUi(); refresh(); })),
          (ui.ctrBtn = btn("centred", "Centre the series on the placed position (default: first frame at the position, frame k at k x step)", function () { S.centered = !S.centered; syncUi(); refresh(); })),
          (ui.revBtn = btn("reverse", "Sweep in the opposite direction", function () { S.sign = -S.sign; syncUi(); refresh(); }))]),
        slider("Step", 3, 50, 1, "step", function (v) { return v + " mm"; }, function (v) { S.spacing = v; ui.totOut.textContent = totalText(); refresh(); }, "Distance between frames 3 mm to 5 cm"),
        slider("Total", 3, 50, 1, "total", function (v) { return v + " mm"; }, function (v) { S.total = v; ui.totOut.textContent = totalText(); refresh(); }, "Total sweep distance 3 mm to 5 cm"),
        el("div", {class: "us-row"}, [(ui.totOut = el("output", {text: ""})),
          (ui.followBtn = btn("follow organ", "The sweep follows the long axis (PCA of the mesh) of the chosen structure", function () { if (S.followSid < 0) { S.pick3d = true; setStatus("Click the organ in the 3D view."); syncUi(); } else { S.follow = !S.follow; syncUi(); refresh(true); } })),
          (ui.pickBtn = btn("pick organ", "Click a structure in the 3D view to follow", function () { S.pick3d = !S.pick3d; syncUi(); setStatus(S.pick3d ? "Click the organ in the 3D view." : ""); })),
          (ui.pickImgBtn = btn("organ under cursor", "Follow the structure last read under the cursor / tap in an image", function () { if (ui.lastSid != null && ui.lastSid >= 0 && ui.lastSid < 65534) setFollow(ui.lastSid); else setStatus("Hover or tap a structure in an image first."); })),
          (ui.followOut = el("output", {text: ""}))])
      ]);
      /* Q253 (3/4): view / cine / frame scrub -- shared by BOTH modes (previously sweep-only, so star/tilt mode had no cine at all) */
      ui.playBox = el("div", {style: "display:grid;gap:6px"}, [
        el("div", {class: "us-row"}, [(ui.viewBtn = btn("matrix", "Matrix of all frames / one big frame", function () { if (S.view === "single" && S.cine && S.cineMode === "continuous") setCine(false); S.view = S.view === "matrix" ? "single" : "matrix"; syncUi(); relayoutViews(); })),
          (ui.cineBtn = btn("▶ cine", "Play through the frames in place, as a movie (one big frame; use “matrix” / “single” above to switch views)", function () { setCine(!S.cine); })),
          el("label", {text: "fps"}), (ui.fpsSel = el("select", {"aria-label": "Cine frames per second / continuous speed", onchange: function () { S.fps = +ui.fpsSel.value; if (S.cine) { setCine(false); setCine(true); } }}, [1, 2, 3, 5, 8].map(function (f) { return el("option", {value: String(f), text: String(f)}); })))]),
        el("div", {class: "us-row"}, [(ui.cineModeBtn = btn("continuous", "Continuous: the probe genuinely slides / fans through a smooth range of positions, re-slicing a new frame at every step (at a reduced “live” resolution to stay real-time) instead of snapping between the step mode's precomputed frames", function () { if (S.cine) setCine(false); S.cineMode = S.cineMode === "continuous" ? "step" : "continuous"; syncUi(); })),
          (ui.contOut = el("output", {text: ""}))]),
        slider("Frame", 1, 9, 1, "frame", function (v) { return "#" + v; }, function (v) { selectFrame(v - 1); }, "Scroll through the frames (9 tilt directions in star mode, n planes in sweep mode); disabled while continuous cine plays")
      ]);
      /* image section */
      var im1 = slider("Gain", -25, 25, 1, "gain", function (v) { return (v > 0 ? "+" : "") + v + " dB"; }, function (v) { S.gain = v; repaintAll(); }, "Overall gain");
      var im2 = slider("TGC far", -15, 15, 1, "tgc", function (v) { return (v > 0 ? "+" : "") + v + " dB"; }, function (v) { S.tgc = v; refresh(); }, "Extra gain at the maximum depth (time-gain compensation)");
      var im3 = slider("Focus", 0.5, 15, 0.5, "focus", function (v) { return v.toFixed(1) + " cm"; }, function (v) { S.focusCm = v; refresh(); }, "Transmit focus depth");
      var im4 = slider("Dyn. range", 30, 90, 5, "dr", function (v) { return v + " dB"; }, function (v) { S.dr = v; repaintAll(); }, "Display dynamic range");
      ui.togs = {};
      function tog(key, text, title) { return (ui.togs[key] = btn(text, title, function () { S[key] = !S[key]; syncUi(); if (key === "hidden" || key === "speckle" || key === "textures" || key === "reverb" || key === "noise") refresh(true); })); }
      var im5 = el("div", {class: "us-row"}, [tog("speckle", "speckle", "Synthetic seeded speckle (clearly synthetic; off = smooth tissue levels)"), tog("textures", "muscle / tendon texture", "Documented class textures: muscle septa, tendon fibrils and anisotropy"),
        tog("reverb", "reverberation", "A-line repeats behind air / lung"), tog("noise", "system noise", "Synthetic electronic noise floor (default off)")]);
      var mo1 = el("div", {class: "us-row"}, [tog("hidden", "hidden structures", "Leave out the structures hidden in the 3D view (virtual dissection; skin always stays). Default: the whole body is imaged, as in a real patient."),
        btn("reset", "Back to defaults (probe stays)", function () { resetDefaults(); })]);
      ui.status = el("div", {class: "us-status", text: ""});
      function sec(name, kids) { var d = el("div", {class: "sec", "data-sec": name}, kids); ui.secs[name] = d; return d; }
      ui.secs = {};
      ui.sweepOnly = ui.sweepBox; ui.starOnly = ui.starBox;
      [mrow, sec("probe", [r1, r2, r3, r4, r5]), sec("mode", [ui.starBox, ui.sweepBox, ui.playBox]), sec("image", [im1, im2, im3, im4, im5]), sec("more", [mo1]), ui.status].forEach(function (x) { ctl.appendChild(x); });
      setSec(S.sec);
    }
    function setSec(name) {
      S.sec = name;
      Object.keys(ui.secs || {}).forEach(function (k) { ui.secs[k].classList.toggle("us-act", k === name); });
      Array.prototype.forEach.call(ui.secTabs.querySelectorAll("[data-sec]"), function (b) { b.setAttribute("aria-pressed", String(b.dataset.sec === name)); });
    }
    function totalText() { var sp = spacing(); return "step " + (Math.round(sp * 10) / 10) + " mm · total " + (Math.round(sp * (S.n - 1) * 10) / 10) + " mm"; }
    function syncUi() {
      if (!ui.modeBtn1) return;
      ui.modeBtn1.setAttribute("aria-pressed", String(S.mode === "star")); ui.modeBtn2.setAttribute("aria-pressed", String(S.mode === "sweep"));
      ["linear", "convex", "sector"].forEach(function (k) { ui.probeBtns[k].setAttribute("aria-pressed", String(S.probe === k)); });
      if (US) {
        ui.widthSel.innerHTML = ""; US.probes[S.probe].width_mm.forEach(function (w) { ui.widthSel.appendChild(el("option", {value: String(w), text: w + " mm"})); });
        ui.widthSel.value = String(S.widths[S.probe]);
      }
      Object.keys(ui.freqBtns).forEach(function (f) { ui.freqBtns[f].setAttribute("aria-pressed", String(+f === S.freq)); });
      setSlider("depth", S.depthCm); setSlider("rot", S.rot); setSlider("tilt", S.tilt); setSlider("mtilt", S.mTilt); setSlider("mdir", S.mTiltDir); setSlider("step", S.spacing); setSlider("total", S.total);
      setSlider("gain", S.gain); setSlider("tgc", S.tgc); setSlider("focus", S.focusCm); setSlider("dr", S.dr); setSlider("frame", S.sel + 1);
      if (ui.frame) ui.frame.max = String(S.mode === "star" ? 9 : S.n);
      ui.nSel.value = String(S.n); ui.fpsSel.value = String(S.fps);
      ui.placeBtn.setAttribute("aria-pressed", String(S.placing)); ui.orLong.setAttribute("aria-pressed", String(S.refKey === "long")); ui.orTrans.setAttribute("aria-pressed", String(S.refKey === "trans"));
      ui.starBox.style.display = S.mode === "star" ? "" : "none"; ui.sweepBox.style.display = S.mode === "sweep" ? "" : "none";
      Object.keys(ui.dirBtns).forEach(function (d) { ui.dirBtns[d].setAttribute("aria-pressed", String(+d === S.mTiltDir)); });
      ui.byBtn.textContent = S.byTotal ? "by total" : "by step"; ui.byBtn.setAttribute("aria-pressed", String(S.byTotal));
      ui.ctrBtn.setAttribute("aria-pressed", String(S.centered)); ui.revBtn.setAttribute("aria-pressed", String(S.sign < 0));
      ui.step.disabled = S.byTotal; ui.total.disabled = !S.byTotal; ui.totOut.textContent = totalText();
      ui.followBtn.setAttribute("aria-pressed", String(S.follow)); ui.pickBtn.setAttribute("aria-pressed", String(S.pick3d)); ui.followOut.textContent = S.followSid >= 0 ? (S.followName + (S.follow ? "" : " (off)")) : "no organ chosen";
      ui.viewBtn.textContent = S.view === "matrix" ? "matrix" : "single"; ui.viewBtn.setAttribute("aria-pressed", String(S.view === "matrix")); ui.cineBtn.setAttribute("aria-pressed", String(S.cine));
      ui.cineModeBtn.setAttribute("aria-pressed", String(S.cineMode === "continuous")); if (ui.frame) ui.frame.disabled = S.cine && S.cineMode === "continuous"; updateContReadout();
      Object.keys(ui.togs).forEach(function (k) { ui.togs[k].setAttribute("aria-pressed", String(!!S[k])); });
      if (ui.tabs) ui.tabs.children[1].setAttribute("aria-pressed", String(S.placing));
    }
    function setMode(m) { S.mode = m; S.sel = 0; setCine(false); axisCache = {}; syncUi(); updateLayoutUi(); relayoutViews(); frames = []; refresh(true); }
    function setProbe(k) {
      S.probe = k; var p = US.probes[k]; S.freq = p.freq_default; S.depthCm = p.depth_default_cm; S.focusCm = S.depthCm * 0.5; syncUi(); refresh(true);
    }
    function resetDefaults() { S.gain = 0; S.tgc = 0; S.dr = 60; S.focusCm = S.depthCm * 0.5; S.speckle = true; S.textures = true; S.reverb = true; S.noise = false; S.rot = 0; S.mTilt = 0; S.tilt = 15; syncUi(); refresh(true); }
    function rotateBy(deltaDeg) { S.rot = ((S.rot + deltaDeg) % 360 + 360) % 360; setSlider("rot", S.rot); refresh(); }   // Q255: CW/CCW nudge, wraps 359<->0 (the plain slider only clamps)
    function selectFrame(i) { S.sel = Math.max(0, Math.min(frames.length ? frames.length - 1 : 8, i)); relayoutViews(); syncUi(); updateOverlay(); if (S.mode === "star") refresh(true); }
    function setCine(on) {
      clearInterval(timers.cine); contState.active = false; contState.busy = false; if (contState.raf) { cancelFrame(contState.raf); contState.raf = 0; }
      S.cine = !!on;                                                           // Q253: cine plays in BOTH modes; Q257 adds a genuinely continuous re-slicing mode alongside the step-through one
      if (S.cine && S.cineMode === "continuous") {
        if (S.view !== "single") { S.view = "single"; relayoutViews(); }       // a continuously sliding plane is one image, not a matrix of stale neighbours
        contState.pos = S.mode === "star" ? ((frames[S.sel] && frames[S.sel].spec && frames[S.sel].spec.dir) || 0) : 0;
        contState.dir = 1; contState.lastT = 0; contState.measMs = 0; contState.fpsActual = 0; contState.active = true; contState.raf = reqFrame(contTick);
      } else if (S.cine) {
        timers.cine = setInterval(function () { if (!frames.length) return; var nF = S.mode === "star" ? 9 : S.n; S.sel = (S.sel + 1) % nF; relayoutViews(); syncUi(); updateOverlay(); }, 1000 / S.fps);
      }
      updateContReadout(); syncUi();
    }
    function setStatus(t) {
      if (!ui.status) return;
      if (t) ui.status.textContent = t;
      else { var p = perf.last; ui.status.textContent = p ? p.n + " frame" + (p.n > 1 ? "s" : "") + " in " + p.ms + " ms (" + p.per.join("/") + " ms each) · " + (frames[S.sel] && frames[S.sel].sim ? (frames[S.sel].sim.contact ? "skin contact ok" : "NO skin contact: move the probe onto the body") : "") : ""; }
    }

    /* ---------- views ---------- */
    var STAR_CELL = {0: [2, 3], 1: [1, 3], 2: [1, 2], 3: [1, 1], 4: [2, 1], 5: [3, 1], 6: [3, 2], 7: [3, 3]};          // dir index -> [row, col]
    function ensureViews(specs) {
      var want = specs.length;
      if (views.length === want && views.mode === S.mode) return relayoutViews();
      views.forEach(function (v) { if (v.wrap.parentNode) v.wrap.parentNode.removeChild(v.wrap); });
      views = []; views.mode = S.mode;
      specs.forEach(function (sp, i) {
        var v = {idx: i, img: el("canvas", {}), ann: el("canvas", {class: "ann"}), hover: null};
        v.ctx = v.img.getContext("2d"); v.actx = v.ann.getContext("2d");
        v.wrap = el("div", {class: "us-view", "data-i": String(i), tabindex: "0", "aria-label": "frame " + (i + 1)}, [v.img, v.ann]);
        v.wrap.addEventListener("click", function () { if (i !== S.sel) { S.sel = i; relayoutViews(); syncUi(); updateOverlay(); if (S.mode === "star") refresh(true); } });
        v.wrap.addEventListener("pointermove", function (e) { v.hover = hoverAt(v, e); });
        v.wrap.addEventListener("pointerdown", function (e) { v.hover = hoverAt(v, e); });
        ui.views.appendChild(v.wrap); views.push(v);
      });
      relayoutViews();
    }
    function relayoutViews() {
      if (!ui.views) return;
      var vw = ui.views;
      drawSchematic();
      if (S.mode === "star" && S.view !== "single") {                         // Q253: star mode can now also show one big cine-able frame (S.view === "single")
        vw.className = "us-views star";
        views.forEach(function (v, i) {
          var cell;
          if (i === S.sel) cell = [2, 2];
          else if (i === 0) cell = STAR_CELL[S.sel - 1];
          else cell = STAR_CELL[i - 1];
          v.wrap.style.gridRow = String(cell[0]); v.wrap.style.gridColumn = String(cell[1]); v.wrap.style.display = "";
        });
        vw.style.gridTemplateColumns = ""; vw.style.gridTemplateRows = "";
      } else if (S.view === "single") {
        vw.className = "us-views single"; vw.style.gridTemplateColumns = ""; vw.style.gridTemplateRows = "";
        views.forEach(function (v, i) { v.wrap.style.gridRow = ""; v.wrap.style.gridColumn = ""; v.wrap.style.display = i === S.sel ? "" : "none"; });
      } else {
        var d = LIB.matrixDims(S.n), cols = d[0], rows = d[1];
        if (window.innerHeight > window.innerWidth && Math.min(window.innerWidth, window.innerHeight) < 520 && S.n > 3) { var t = cols; cols = rows; rows = t; if (S.n === 9) { cols = 3; rows = 3; } }
        vw.className = "us-views"; vw.style.gridTemplateColumns = "repeat(" + cols + ",1fr)"; vw.style.gridTemplateRows = "repeat(" + rows + ",1fr)";
        views.forEach(function (v) { v.wrap.style.gridRow = ""; v.wrap.style.gridColumn = ""; v.wrap.style.display = ""; });
      }
      views.forEach(function (v, i) { v.wrap.classList.toggle("us-act", i === S.sel); });
      clearTimeout(timers.ann); timers.ann = setTimeout(function () { views.forEach(function (v, i) { if (frames[i] && frames[i].sim) annotate(v, frames[i]); }); }, 30);
    }
    /* Q253 (4): a small 2-D dial next to the acquired image, showing WHICH of the 8 tilt directions is on screen (centre = 90 deg
     * perpendicular). It reads only the already-computed spec for S.sel, so it tracks the slider AND cine automatically. */
    function drawSchematic() {
      if (!ui.schem) return;
      var show = S.mode === "star"; ui.schem.style.display = show ? "" : "none";
      if (!show || !frames.length) return;
      var ctx = ui.schem.getContext("2d"), w = ui.schem.width, h = ui.schem.height, cx = w / 2, cy = h / 2 - 4, R = 26;
      ctx.clearRect(0, 0, w, h); ctx.fillStyle = "#0a0e14"; ctx.fillRect(0, 0, w, h);
      var spec = (frames[S.sel] && frames[S.sel].spec) || frameSpecs()[S.sel] || {id: 0, tilt: 0};
      ctx.strokeStyle = "#3a4654"; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.stroke();
      ctx.strokeStyle = "#263140"; ctx.beginPath(); ctx.moveTo(cx - R - 4, cy); ctx.lineTo(cx + R + 4, cy); ctx.stroke();   // skin line (this dial's own frame, not the body's)
      var i;
      for (i = 0; i < 8; i++) {
        var a = i * Math.PI / 4 - Math.PI / 2, on = spec.id === i + 1;
        ctx.fillStyle = on ? "#ff9d4a" : "#45535f";
        ctx.beginPath(); ctx.arc(cx + Math.cos(a) * R, cy + Math.sin(a) * R, on ? 4 : 2.2, 0, 6.2832); ctx.fill();
      }
      if (spec.id > 0) {
        var a2 = (spec.id - 1) * Math.PI / 4 - Math.PI / 2;
        ctx.strokeStyle = "#ff9d4a"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(cx + Math.cos(a2) * R, cy + Math.sin(a2) * R); ctx.stroke();
      }
      ctx.fillStyle = spec.id === 0 ? "#ff9d4a" : "#5c6b7a"; ctx.beginPath(); ctx.arc(cx, cy, 4, 0, 6.2832); ctx.fill();
      ctx.fillStyle = "#cfe6ff"; ctx.font = "600 10px system-ui,sans-serif"; ctx.textAlign = "center";
      ctx.fillText(spec.id === 0 ? "90°" : spec.tilt + "°", cx, h - 15);
      ctx.font = "8.5px system-ui,sans-serif"; ctx.fillStyle = "#9fb0c2";
      ctx.fillText(spec.id === 0 ? "perpendicular" : (LIB.STAR_NAMES[spec.id - 1] || "").replace(/\s*\(.*\)$/, ""), cx, h - 5);
    }
    function paintView(i, fr) {
      var v = views[i]; if (!v || !fr || !fr.sim) return;
      var sim = fr.sim, cv = v.img;
      if (cv.width !== sim.Wo || cv.height !== sim.Ho) { cv.width = sim.Wo; cv.height = sim.Ho; v.imgData = null; }
      if (!v.imgData) v.imgData = v.ctx.createImageData(sim.Wo, sim.Ho);
      var gray = LIB.toGray(sim.db, US.global.display_ref_fraction, S.gain, S.dr), d = v.imgData.data, k, N = sim.Wo * sim.Ho;
      for (k = 0; k < N; k++) { var g = gray[k], o = k * 4; d[o] = d[o + 1] = d[o + 2] = g; d[o + 3] = 255; }
      v.ctx.putImageData(v.imgData, 0, 0);
      annotate(v, fr);
    }
    function boxOf(v, fr, cw, ch) {
      var s = Math.min(cw / fr.sim.Wo, ch / fr.sim.Ho);
      return {x: (cw - fr.sim.Wo * s) / 2, y: (ch - fr.sim.Ho * s) / 2, w: fr.sim.Wo * s, h: fr.sim.Ho * s, s: s};
    }
    function annotate(v, fr) {
      var a = v.ann, ctx = v.actx; if (!a || !fr || !fr.sim) return;
      var r = v.wrap.getBoundingClientRect(), dpr = Math.min(2, window.devicePixelRatio || 1), cw = Math.max(1, Math.round(r.width)), ch = Math.max(1, Math.round(r.height));
      if (a.width !== cw * dpr || a.height !== ch * dpr) { a.width = cw * dpr; a.height = ch * dpr; a.style.width = cw + "px"; a.style.height = ch + "px"; }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, cw, ch);
      var box = boxOf(v, fr, cw, ch); v.box = box;
      v.img.style.left = box.x + "px"; v.img.style.top = box.y + "px"; v.img.style.width = box.w + "px"; v.img.style.height = box.h + "px";
      var tiny = box.w < 200, sim = fr.sim, pl = fr.plan, g = fr.geom, sc = box.s / pl.px;       // css px per mm
      function X(x) { return box.x + (x - pl.xo0) * sc; }
      function Y(y) { return box.y + (y - pl.yo0) * sc; }
      ctx.font = "600 " + (tiny ? 9.5 : 11.5) + "px system-ui,sans-serif"; ctx.textBaseline = "middle";
      function txt(s, x, y, al, col) { ctx.textAlign = al; ctx.fillStyle = "rgba(0,0,0,.7)"; ctx.fillText(s, x + 1, y + 1); ctx.fillStyle = col || "#e8eef5"; ctx.fillText(s, x, y); }
      function wrapTxt(s, x, y, maxW, col) {                                   // Q253: word-wrap a warning line inside the box width
        var words = s.split(" "), line = "", lh = tiny ? 11 : 13, yy = y;
        for (var wi = 0; wi < words.length; wi++) {
          var test = line ? line + " " + words[wi] : words[wi];
          if (ctx.measureText(test).width > maxW && line) { txt(line, x, yy, "left", col); yy += lh; line = words[wi]; } else line = test;
        }
        if (line) txt(line, x, yy, "left", col);
      }
      /* probe footprint (top), marker dot on the LEFT */
      ctx.fillStyle = "#59636f"; ctx.strokeStyle = "#9aa7b4"; ctx.lineWidth = 1;
      if (g.type === "convex") {
        ctx.beginPath();
        for (var q = 0; q <= 20; q++) { var th = -g.alpha + 2 * g.alpha * q / 20, px_ = g.R * Math.sin(th), py_ = g.R * Math.cos(th) - g.R; if (q === 0) ctx.moveTo(X(px_), Y(py_)); else ctx.lineTo(X(px_), Y(py_)); }
        for (q = 20; q >= 0; q--) { var th2 = -g.alpha + 2 * g.alpha * q / 20; ctx.lineTo(X((g.R + 5) * Math.sin(th2)), Y((g.R + 5) * Math.cos(th2) - g.R - 5 - 0)); }
        ctx.closePath(); ctx.fill(); ctx.stroke();
      } else if (g.type === "sector") {
        ctx.beginPath(); ctx.moveTo(X(-g.w / 2), Y(-6)); ctx.lineTo(X(g.w / 2), Y(-6)); ctx.lineTo(X(g.w * 0.12), Y(0)); ctx.lineTo(X(-g.w * 0.12), Y(0)); ctx.closePath(); ctx.fill(); ctx.stroke();
      } else { ctx.fillRect(X(-g.w / 2), Y(-3), g.w * sc, 3 * sc); ctx.strokeRect(X(-g.w / 2), Y(-3), g.w * sc, 3 * sc); }
      var mx = g.type === "sector" ? -g.w / 2 + 2 : -g.w / 2 + 3;
      ctx.fillStyle = "#ff5a3c"; ctx.beginPath(); ctx.arc(X(mx), Y(g.type === "convex" ? g.R * Math.cos(mx / g.R) - g.R - 2 : -3), tiny ? 2.5 : 3.5, 0, 6.2832); ctx.fill();
      /* depth scale (right edge, cm) */
      var xs = box.x + box.w - 1, majorCm = g.depth > 80 ? 2 : 1, cm;
      ctx.strokeStyle = "rgba(255,255,255,.85)"; ctx.lineWidth = 1;
      for (cm = 0; cm * 10 <= g.depth + 0.01; cm += 0.5) {
        var yy = Y(cm * 10), major = Math.abs(cm - Math.round(cm)) < 1e-6 && Math.round(cm) % majorCm === 0;
        if (!major && (g.depth > 80 || tiny)) continue;
        if (Math.abs(cm - Math.round(cm)) > 1e-6 && !major && g.depth > 80) continue;
        ctx.beginPath(); ctx.moveTo(xs, yy); ctx.lineTo(xs - (major ? 9 : 5), yy); ctx.stroke();
        if (major && cm > 0 && !(tiny && cm % 2)) txt(String(Math.round(cm)), xs - 12, yy, "right", "#cfe6ff");
      }
      txt("cm", xs - 3, Y(-3), "right", "#cfe6ff");
      /* fan outline (faint) */
      ctx.strokeStyle = "rgba(108,180,255,.28)"; ctx.setLineDash([3, 4]); ctx.beginPath();
      fanOutline(g, 24).forEach(function (p, k2) { if (k2 === 0) ctx.moveTo(X(p[0]), Y(p[1])); else ctx.lineTo(X(p[0]), Y(p[1])); }); ctx.closePath(); ctx.stroke(); ctx.setLineDash([]);
      /* orientation letters: left = marker side */
      var midY = box.y + box.h * 0.45;
      txt(LIB_dirLabel(fr.pf.u, true), box.x + 6, midY, "left", "#ffd37a"); txt(LIB_dirLabel(fr.pf.u, false), box.x + box.w - 22, midY, "right", "#ffd37a");
      if (!tiny) txt(LIB_dirLabel(fr.pf.b, false) + " ↓", box.x + box.w / 2, box.y + box.h - 22, "center", "#ffd37a");
      /* header */
      var t1 = (tiny ? "" : g.type + " " + g.w + " mm \u00B7 ") + S.freq + " MHz \u00B7 " + S.depthCm + " cm" + (tiny ? "" : " \u00B7 gain " + (S.gain >= 0 ? "+" : "") + S.gain + " dB");
      if (box.h > 150) { txt(t1, box.x + 6, box.y + 10, "left"); txt(fr.spec.label, box.x + 6, box.y + (tiny ? 21 : 24), "left", "#9fd0ff"); }
      else txt(fr.spec.short || fr.spec.label, box.x + 4, box.y + 8, "left", "#9fd0ff");
      if (!tiny) {
        txt("tilt " + (Math.round(fr.pf.tilt * 10) / 10) + "\u00B0 \u00B7 normal " + fr.pf.N.map(function (x) { return x.toFixed(2); }).join(","), box.x + 6, box.y + 38, "left", "#b8c4d2");
        if (S.speckle || S.noise || S.textures) txt("synthetic: " + [S.speckle ? "speckle" : "", S.textures ? "textures" : "", S.noise ? "noise" : ""].filter(Boolean).join(", "), box.x + 6, box.y + 52, "left", "#ff9d8a");
        if (!sim.contact) txt("NO SKIN CONTACT", box.x + box.w / 2, box.y + box.h / 2, "center", "#ff6a5a");
        if (v.idx === S.sel) {
          var mm = US && LIB.probeMismatch(S.freq, S.depthCm, US.global && US.global.tgc_alpha_ref_db_cm_mhz);
          if (mm) wrapTxt("PROBE/DEPTH MISMATCH: " + mm.text, box.x + 6, box.y + 66, box.w - 12, "#ffb13c");
        }
      }
      var bad = BADGE.toUpperCase(), bw2 = ctx.measureText(bad).width;
      if (bw2 + 12 <= box.w) txt(bad, box.x + box.w - 6, box.y + box.h - 8, "right", "#ff9d8a");
      else { txt("SIMULATED \u2013", box.x + box.w - 4, box.y + box.h - 17, "right", "#ff9d8a"); txt("NOT AN ULTRASOUND", box.x + box.w - 4, box.y + box.h - 7, "right", "#ff9d8a"); }
      /* cursor */
      if (v.hover && v.hover.fr === fr) { ctx.strokeStyle = "rgba(255,80,60,.9)"; ctx.beginPath(); ctx.arc(v.hover.cx, v.hover.cy, 6, 0, 6.2832); ctx.stroke(); }
    }
    function LIB_dirLabel(d, neg) { var x = neg ? [-d[0], -d[1], -d[2]] : d; return sh.lib.dirLabel(x); }
    function hoverAt(v, e) {
      var fr = frames[v.idx]; if (!fr || !fr.sim || !v.box) return null;
      var r = v.wrap.getBoundingClientRect(), cx = e.clientX - r.left, cy = e.clientY - r.top, box = v.box;
      var ox = (cx - box.x) / box.w * fr.sim.Wo, oy = (cy - box.y) / box.h * fr.sim.Ho;
      if (ox < 0 || oy < 0 || ox >= fr.sim.Wo || oy >= fr.sim.Ho) return null;
      var pl = fr.plan, x = pl.xo0 + ox * pl.px, y = pl.yo0 + oy * pl.px, db = fr.sim.db[Math.floor(oy) * fr.sim.Wo + Math.floor(ox)];
      var ry = y + fr.sim.ysk, rx = Math.floor((x - pl.xr0) / pl.px), rY = Math.floor((ry - pl.yr0) / pl.px), cls = "", name = "", sidv = -1;
      if (rx >= 0 && rY >= 0 && rx < pl.W && rY < pl.H && fr.lab) {
        var k = rY * pl.W + rx; cls = C.T.classes[fr.lab[k]].label; sidv = fr.sid ? fr.sid[k] : 65535;
        name = sidv === 65535 ? "no structure (baseline fat / outside)" : sidv === 65534 ? "skin rim (modelled)" : geo.names[sidv] + (geo.recs[sidv] ? " [" + geo.recs[sidv].id + "]" : "");
      }
      var P = toWorld(fr.O, fr.pf, x, ry);
      ui.lastSid = sidv;
      ui.read.textContent = cls + " | " + name + " | depth " + (y / 10).toFixed(1) + " cm, lateral " + x.toFixed(1) + " mm | echo " + (db > -150 ? (db >= 0 ? "+" : "") + db.toFixed(0) + " dB re liver" : "none") + " | atlas x " + P[0].toFixed(0) + " y " + P[1].toFixed(0) + " z " + P[2].toFixed(0) + " mm";
      requestAnimationFrame(function () { annotate(v, fr); });
      return {fr: fr, cx: cx, cy: cy, sid: sidv};
    }
    function savePng() {
      var v = views[S.sel], fr = frames[S.sel]; if (!v || !fr || !fr.sim) return;
      var r = v.wrap.getBoundingClientRect(), s = window.devicePixelRatio || 1, out = document.createElement("canvas"); out.width = Math.max(256, Math.round(r.width * s)); out.height = Math.max(256, Math.round(r.height * s));
      var c = out.getContext("2d"); c.fillStyle = "#000"; c.fillRect(0, 0, out.width, out.height); c.imageSmoothingEnabled = true; c.imageSmoothingQuality = "high";
      c.drawImage(v.img, v.box.x * s, v.box.y * s, v.box.w * s, v.box.h * s); c.drawImage(v.ann, 0, 0, out.width, out.height);
      out.toBlob(function (b) { var u = URL.createObjectURL(b), l = document.createElement("a"); l.href = u; l.download = "simulated_ultrasound_" + S.mode + "_" + (S.sel + 1) + ".png"; document.body.appendChild(l); l.click(); l.remove(); setTimeout(function () { URL.revokeObjectURL(u); }, 3000); });
    }

    /* ---------- info panel ---------- */
    function renderInfo() {
      var box = ui.info; if (!box) return; box.innerHTML = "";
      if (!US) { box.appendChild(el("p", {text: loadErr ? "Acoustic table not loaded: " + loadErr : "Loading acoustic table ..."})); return; }
      box.appendChild(el("h3", {text: "What you are looking at"}));
      box.appendChild(el("p", {html: "<b>A simulation computed from this viewer's segmented anatomical meshes – not an ultrasound.</b> The image plane of the virtual probe is intersected with every mesh (the Imaging mode's kernel); each pixel gets a tissue class, and a B-mode image is built along straight beam lines from the acoustic table below. It teaches where structures lie and how the probe movements (tilt, rock, fan, sweep) change the view; it must never be used to judge a patient or a scan."}));
      var how = ["Per beam line: at every change of tissue class the reflected fraction is R = ((Z2 − Z1)/(Z2 + Z1))² times an angle factor exp(−θ²/2σ²) (θ = angle between the beam and the interface normal estimated from the smoothed impedance field; a diffuse floor for rough interfaces) and the transmitted intensity is multiplied by (1 − R).",
        "Inside a class: attenuation α f L (dB, α in dB/cm/MHz) and class backscatter (liver = 0 dB; relative echogenicity is qualitative) times two-way transmission; time-gain compensation assumes a nominal " + US.global.tgc_alpha_ref_db_cm_mhz + " dB/cm/MHz, so fluid (low attenuation) shows posterior enhancement and bone / lung / air show shadows – no separate switches.",
        "Resolution: axial ~ 1.25 wavelengths; lateral = 1.2 λ F/D at the focus and growing away from it. Frequency presets 3.5 / 5 / 7.5 / 12 MHz change attenuation, wavelength and therefore both.",
        "Geometry: linear = parallel lines; convex = fan from a centre 60 mm behind the face; sector = fan from the footprint (90°). The beam axis is the smoothed skin normal (area-weighted over 15 mm); the probe is seated on the skin at its centre; air between the face and the skin is coupling gel up to 12 mm.",
        "Orientation: the marker is on the screen LEFT (and the dot on the probe). Longitudinal: marker cranial (screen left = cranial). Transverse: marker to the patient's right (screen left = patient right, the CT convention). Depth scale in cm on the right edge, footprint at the top.",
        "Tilt = the probe handle leans by the stated angle (rigid rotation about the contact point). 'Away / toward marker' = rocking inside the image plane; 'heel / toe' = fanning (the plane swings sideways). Which heel/toe side faces the examiner depends on where the examiner stands.",
        "Sweep: parallel planes, frame k at k × step along the plane normal (perpendicular to the image plane); 'follow organ' rotates the probe about the skin normal so that this direction lies as close as possible to the PCA long axis of the chosen structure.",
        "Cine: 'step' plays back the already-computed set of frames (the 9 tilt directions / n sweep planes) in place, as a movie. 'continuous' instead genuinely RE-SLICES a new frame at every displayed position as it slides (sweep) or fans (star tilt direction) smoothly through the range -- a real re-slice of the meshes each time, not an interpolation between the step frames -- at a reduced resolution so it keeps up in real time; the fps selector sets the target sweep/fan speed, and the readout next to it shows the actually achieved re-slice rate on this device, which can fall behind the target on a slow machine (shown honestly, not hidden).",
        "Model artefacts handled: an air band thinner than " + US.global.air_pocket_fill_mm + " mm along a beam that tissue follows again is treated as fat (the Z pages' skin is a set of overlapping patches; the slice kernel then labels gaps between skin layers as air); thin fascia / septa meshes are drawn one pixel wide and can show as bright lines with a stair-step on oblique planes.",
        "Synthetic parts: speckle (seeded value noise with Rayleigh statistics, attached to the sweep volume), muscle septa / tendon fibril textures, optional system noise: all labelled on the image and switchable off. Not modelled: " + US.artefacts.not_modelled.join("; ") + "."];
      var ul = el("ul"); how.forEach(function (t) { ul.appendChild(el("li", {text: t})); }); box.appendChild(ul);
      box.appendChild(el("h3", {text: "Honest limits"}));
      var ul2 = el("ul"); US.honesty.forEach(function (t) { ul2.appendChild(el("li", {text: t})); }); box.appendChild(ul2);
      box.appendChild(el("h3", {text: "Acoustic table (" + Object.keys(US.classes).length + " classes) – colour: green verified in an abstract, yellow owner-supplied, orange recalled / UNVERIFIED, blue derived, purple assumption"}));
      var tb = el("table"); tb.appendChild(el("tr", {html: "<th>class</th><th>Z MRayl</th><th>c m/s</th><th>α dB/cm/MHz</th><th>echo dB re liver</th><th>status</th><th>sources / note</th>"}));
      Object.keys(US.classes).forEach(function (k) {
        var c = US.classes[k], srcs = (c.src || []).map(function (s) { var rf = US.references[s]; return rf ? (rf.pmid ? "PMID " + rf.pmid : s) : s; }).join(", ");
        tb.appendChild(el("tr", {html: "<td>" + k + "</td><td>" + c.z + "</td><td>" + c.c + "</td><td>" + c.alpha + "</td><td>" + c.bs_db + "</td><td class='st-" + c.status + "'>" + c.status + "</td><td>" + srcs + (c.note ? " – " + c.note : "") + "</td>"}));
      });
      box.appendChild(tb);
      box.appendChild(el("h3", {text: "References"}));
      var ol = el("ul"); Object.keys(US.references).forEach(function (k) { var r = US.references[k]; ol.appendChild(el("li", {text: r.cite + (r.pmid ? " [PMID " + r.pmid + "]" : " [not in PubMed]") + " – " + r.used_for})); }); box.appendChild(ol);
      box.appendChild(el("p", {text: "The structure → tissue-class mapping is the one of the Imaging mode (see its Info panel); the bone model (cortex, canal) is its modelled interior."}));
    }

    /* ---------- toolbar button, open / close, test API ---------- */
    function addButton() {
      var host = sh.toolbarHost();                                            // the page's toolbar, else the floating bar (Q239: the button is always there)
      var b = el("button", {type: "button", id: "t-ultrasound", title: "Ultrasound: simulated B-mode from the meshes (not a scan)", "aria-pressed": "false", text: "Ultrasound", onclick: function () { setOpen(!S.open); }});
      var im = document.getElementById("t-imaging"), cut = document.getElementById("t-cut"), ref = im && im.parentNode === host ? im : cut;
      if (ref && ref.parentNode === host) host.insertBefore(b, ref.nextSibling); else host.appendChild(b);
      b.className = ref && ref.parentNode === host ? ref.className : (api.kind === "webgl" ? "pill" : "tool");
      if (api.kind === "webgl") b.textContent = "ultrasound";
      ui.btn = b;
    }
    function showUsHint() {                                                    // first-use hint, once per browser
      var seen = false; try { seen = localStorage.getItem("nmsk-ultrasound-hint") === "1"; } catch (e) {}
      if (seen || !ui.hint) return;
      ui.hint.textContent = "Simulated B-mode from the meshes (not a scan). The probe was put on the skin automatically; use \u201CPlace probe\u201D and tap the skin to move it. Probe type, tilt and the sweep matrix (3 to 9 frames) are under the images. ";
      ui.hint.appendChild(el("button", {type: "button", text: "OK", onclick: function () { ui.hint.style.display = "none"; try { localStorage.setItem("nmsk-ultrasound-hint", "1"); } catch (e) {} }}));
      ui.hint.style.display = "";
    }
    function setOpen(on) {
      if (on === S.open) return;
      if (on) {
        try { if (sh.isOpen()) sh.close(); } catch (e) {}
        build(); S.open = true; S.tab = "image"; applyLayout(); updateLayoutUi();
        if (ui.btn) ui.btn.setAttribute("aria-pressed", "true");
        setDiag(); showUsHint();
        setStatus("Loading acoustic table and geometry ...");
        loadTable().then(function () {
          if (!S.open) return;
          renderInfo();
          if (loadErr || !AC) { setStatus("Ultrasound unavailable: " + (loadErr || "table missing")); return; }
          if (AC.missing.length) console.warn("ultrasound: classes without acoustic row:", AC.missing);
          if (!S.initDone) { S.initDone = true; S.focusCm = S.depthCm * 0.5; var small = Math.min(window.innerWidth, window.innerHeight) < 520; if (small) S.sec = "probe"; if (window.innerHeight < 500 && chooseLayout() === "tab") { root.classList.add("ctl-off"); ui.ctlBtn.setAttribute("aria-pressed", "false"); } var pp = US.probes[S.probe]; S.freq = pp.freq_default; S.depthCm = pp.depth_default_cm; S.focusCm = S.depthCm * 0.5; }
          syncUi(); applyLayout(); refresh(true);
        });
      } else {
        S.open = false; setCine(false); S.placing = false; S.pick3d = false; gen++; applyLayout(); clearOverlay();
        if (ui.btn) ui.btn.setAttribute("aria-pressed", "false");
      }
    }
    sh.addClickHandler(onPlaceClick);
    addButton();
    acousticTable().then(function () {}, function () {}); setDiag();           // the cheap table now (state in the button tooltip); the geometry only when the panel opens
    var poll = setInterval(function () {                                       // keep the overlay's tube radius in step with the camera distance
      if (!S.open || !frames.length) return;
      var vw; try { vw = api.view(); } catch (e) { return; }
      var d = Math.round(Math.hypot(vw.eye[0] - vw.target[0], vw.eye[1] - vw.target[1], vw.eye[2] - vw.target[2]) / 120);
      if (String(d) !== lastOverlayKey) { lastOverlayKey = String(d); updateOverlay(); }
    }, 400);
    G.NMSKUltrasound = {
      version: VERSION,
      open: function () { setOpen(true); }, close: function () { setOpen(false); }, isOpen: function () { return S.open; },
      ready: function () { return loadTable().then(function () { if (loadErr) throw new Error(loadErr); return true; }); },
      state: function () { return JSON.parse(JSON.stringify(S)); },
      set: function (p) {
        Object.keys(p).forEach(function (k) {
          if (k === "probe") { setProbe(p.probe); } else if (k === "mode") { setMode(p.mode); } else if (k === "sel") { S.sel = p.sel; relayoutViews(); updateOverlay(); }
          else if (k === "gain" || k === "dr") { S[k] = p[k]; repaintAll(); } else if (k === "P" || k === "N") S[k] = p[k].slice();
          else if (k === "widths") Object.assign(S.widths, p.widths); else if (k === "tab") { S.tab = p.tab; applyLayout(); } else if (k === "lay") { S.lay = p.lay; applyLayout(); updateLayoutUi(); }
          else if (k === "cine") setCine(p.cine); else if (k === "followSid") setFollow(p.followSid); else S[k] = p[k];
        });
        if (ui.modeBtn1) syncUi();
        refresh(true);
      },
      /* place the probe where a ray from `from` along `dir` first meets the skin (atlas mm); returns {P, N} or null */
      placeRay: function (from, dir) { var h = placeRay(from, dir, true); if (h) { S.sel = 0; if (ui.modeBtn1) syncUi(); refresh(true); } return h ? {P: S.P.slice(), N: S.N.slice(), struct: h.struct} : null; },
      geo: function () { return geo; }, C: function () { return C; }, table: function () { return US; }, AC: function () { return AC; },
      idle: function () { return new Promise(function (res) { var t0 = Date.now(), t = setInterval(function () { if (!busy && !pumpPending && frames.length && Date.now() - t0 > 150) { clearInterval(t); res(true); } if (Date.now() - t0 > 120000) { clearInterval(t); res(false); } }, 60); }); },
      frames: function () { return frames; }, views: function () { return views; }, perf: function () { return perf; },
      cineStatus: function () { return {active: contState.active, pos: contState.pos, dir: contState.dir, measMs: contState.measMs, fpsActual: contState.fpsActual}; },
      /* one-off frame for tests / timing: spec {tilt, dir, off, rot, maxDim} -> Promise(frame) */
      frameNow: function (spec, q) { return loadTable().then(function () { return computeFrame(Object.assign({id: 0, tilt: 0, dir: 0, off: 0, label: "test"}, spec), q || {maxDim: 480, maxLines: 256}, null); }); },
      screenOf: function (p) { return api.toScreen(p); }, focusOn: function (p, d) { api.focus(p, d); }, view: function () { return api.view(); },
      overlayItems: function () { var it = overlayItems(); return it ? it.map(function (x) { return [x[0], x[1].count()]; }) : null; }
    };
    return {};
  }

  G.NMSKUltrasoundAddon = {attach: function (api, shared) { return attachUltrasound(api, shared); }, VERSION: VERSION};
})(typeof window !== "undefined" ? window : globalThis);
