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
    var cellAx = GL.speckle.cell_ax_wavelengths * lam, cellZ = GL.speckle.elev_mm, elev = o.elevMm || 0, frame = o.frame, nStats = {specCount: 0, lost: 0, texSamples: 0, archSamples: 0, sepSamples: 0};
    var latCell = new Float32Array(nS), ref = o.ref || null;
    for (k = 0; k < nS; k++) latCell[k] = Math.max(0.4, latFw(k * ds) * 0.8);
    function latCellAt(y) { return Math.max(0.4, latFw(y < 0 ? 0 : y) * 0.8); }
    var lastSid = -1, lastAxis = null, lastArch = null;
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
              var axs = null, arc = null;
              if (sid && pix >= 0) { var q = sid[pix]; if (q < 65534) { if (q !== lastSid) { lastSid = q; lastAxis = o.axisOf ? o.axisOf(q) : null; lastArch = o.archOf ? o.archOf(q) : null; } axs = lastAxis; arc = lastArch; } }
              if ((axs && axs.elong >= (AC.aMin[cls] || 2.5)) || arc) {               // Q289: a muscle with architecture data is textured even when its mesh is not elongated (deltoid)
                if (AC.aOn[cls] && bd && axs) { var ca = Math.abs(dot(bd, axs.a)), dev = Math.asin(Math.min(1, ca)), qq = dev / AC.aTh[cls]; m *= AC.aFl[cls] + (1 - AC.aFl[cls]) * Math.exp(-qq * qq); }
                if (tex && AC.tex[cls] && frame) {
                  var wx = frame.O[0] + frame.u[0] * X + frame.b[0] * Y, wy = frame.O[1] + frame.u[1] * X + frame.b[1] * Y, wz = frame.O[2] + frame.u[2] * X + frame.b[2] * Y;
                  var a = axs ? axs.a : arc.a;
                  if (arc && AC.tex[cls] === 1) { a = fibreAt(arc, wx, wy, wz); if (arc._sep > 0.01) { m *= 1 + arc.gain * arc._sep; nStats.sepSamples++; } nStats.archSamples++; }   // Q289: the local fibre direction (pennation) + documented septa
                  var e1 = Math.abs(a[1]) < 0.9 ? unit(cross(a, [0, 1, 0])) : unit(cross(a, [1, 0, 0])), e2 = cross(a, e1);
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

  /* ---- Q289: muscle architecture -----------------------------------------------------------------------------
   * The frame is the muscle mesh's OWN three principal axes (a = long axis / line of action, w = width, t = thickness, from the
   * vertex covariance); the pennation angle is the cited value of ultrasound_tissues.json "architecture"; documented septa are
   * sheets placed in that frame by the stated rule. fibreAt() gives the local fibre direction and the septum weight at a point. */
  function eigSym3(m) {                                                    // Jacobi rotations on a symmetric 3x3 -> eigenpairs, largest first
    var A = [m[0].slice(), m[1].slice(), m[2].slice()], V = [[1, 0, 0], [0, 1, 0], [0, 0, 1]], it, p, q, r;
    for (it = 0; it < 30; it++) {
      p = 0; q = 1; if (Math.abs(A[0][2]) > Math.abs(A[p][q])) { p = 0; q = 2; } if (Math.abs(A[1][2]) > Math.abs(A[p][q])) { p = 1; q = 2; }
      if (Math.abs(A[p][q]) < 1e-12) break;
      var th = 0.5 * Math.atan2(2 * A[p][q], A[q][q] - A[p][p]), c = Math.cos(th), s = Math.sin(th);
      for (r = 0; r < 3; r++) { var arp = A[r][p], arq = A[r][q]; A[r][p] = c * arp - s * arq; A[r][q] = s * arp + c * arq; }
      for (r = 0; r < 3; r++) { var apr = A[p][r], aqr = A[q][r]; A[p][r] = c * apr - s * aqr; A[q][r] = s * apr + c * aqr; }
      for (r = 0; r < 3; r++) { var vrp = V[r][p], vrq = V[r][q]; V[r][p] = c * vrp - s * vrq; V[r][q] = s * vrp + c * vrq; }
    }
    return [0, 1, 2].map(function (k) { return {val: A[k][k], vec: unit([V[0][k], V[1][k], V[2][k]])}; }).sort(function (x, y) { return y.val - x.val; });
  }
  function pca3(pos, v0, v1) {
    var nv = v1 - v0, st = Math.max(1, Math.floor(nv / 4000)), k, c = [0, 0, 0], m = 0;
    for (k = v0; k < v1; k += st) { c[0] += pos[3 * k]; c[1] += pos[3 * k + 1]; c[2] += pos[3 * k + 2]; m++; }
    if (m < 6) return null;
    c = [c[0] / m, c[1] / m, c[2] / m];
    var C3 = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], i, j;
    for (k = v0; k < v1; k += st) { var d = [pos[3 * k] - c[0], pos[3 * k + 1] - c[1], pos[3 * k + 2] - c[2]]; for (i = 0; i < 3; i++) for (j = 0; j < 3; j++) C3[i][j] += d[i] * d[j] / m; }
    var e = eigSym3(C3);
    return {c: c, a: e[0].vec, w: e[1].vec, t: e[2].vec, ev: e.map(function (x) { return x.val; }), step: st};
  }
  var KIND = {unipennate: 1, bipennate: 2, multipennate: 3, layered: 4};
  /* spec: one "architecture.muscles" row; o: {prox: a point nearer the proximal end, dirs: {anterior, medial, superior: unit vectors}, half, gain} */
  function archFrame(pos, v0, v1, spec, o) {
    var F = pca3(pos, v0, v1); if (!F) return null;
    var a = F.a, w = F.w, t = F.t, c = F.c, k, ext = function (ax) { var lo = 1e9, hi = -1e9; for (k = v0; k < v1; k += F.step) { var q = (pos[3 * k] - c[0]) * ax[0] + (pos[3 * k + 1] - c[1]) * ax[1] + (pos[3 * k + 2] - c[2]) * ax[2]; if (q < lo) lo = q; if (q > hi) hi = q; } return [lo, hi]; };
    var la = ext(a);
    if (o.prox && Math.hypot(c[0] + a[0] * la[1] - o.prox[0], c[1] + a[1] * la[1] - o.prox[1], c[2] + a[2] * la[1] - o.prox[2]) < Math.hypot(c[0] + a[0] * la[0] - o.prox[0], c[1] + a[1] * la[0] - o.prox[1], c[2] + a[2] * la[0] - o.prox[2])) { a = mul(a, -1); la = [-la[1], -la[0]]; }
    var toward = function (ax, name) { var d = o.dirs && o.dirs[name]; return d && dot(ax, d) < 0 ? mul(ax, -1) : ax; };
    if (spec.parts && spec.parts.toward) w = toward(w, spec.parts.toward);
    (spec.septa || []).forEach(function (s) { if (s.toward) { if (s.normal === "t") t = toward(t, s.toward); else w = toward(w, s.toward); } });
    var lw = ext(w), lt = ext(t), kind = KIND[spec.t] || 0, p = (spec.p || 0) * DEG;
    var ar = {a: a, w: w, t: t, c: c, la: la, lw: lw, lt: lt, kind: kind, p: p, p0: spec.p0 != null ? spec.p0 * DEG : null, p1: spec.p1 != null ? spec.p1 * DEG : null,
      half: o.half || 0.6, gain: o.gain || 6, sheets: [], bands: null, cOff: (lw[0] + lw[1]) / 2, _f: [0, 0, 0], _sep: 0, _band: -1};
    if (spec.parts && spec.parts.bands && !o.noParts) {
      ar.bands = spec.parts.bands.map(function (b) {
        var words = String(b[2]).toLowerCase().replace(/[()]/g, " ").split(/\s+/).filter(function (x) { return x && x !== "part" && x !== "head"; });
        var hit = (spec.c || []).filter(function (cp) { var n = String(cp[0]).toLowerCase(); return words.some(function (wd) { return n.indexOf(wd) >= 0; }); });
        var ws = 0, sp = 0; hit.forEach(function (cp) { var wt = Math.max(1, cp[2]); ws += wt; sp += cp[1] * wt; });
        return {f0: b[0], f1: b[1], name: b[2], p: (ws ? sp / ws : (spec.p || 0)) * DEG, n: hit.length};
      });
    }
    (spec.septa || []).forEach(function (s) {
      var axn = s.normal === "t" ? "t" : "w", L = axn === "t" ? lt : lw, cnt = s.count || 1, j;
      for (j = 0; j < cnt; j++) {
        var fr = s.count ? (j + 1) / (cnt + 1) : (s.at != null ? s.at : 0.5), span = s.span_alternate ? s.span_alternate[j % 2] : (s.span || [0, 1]);
        ar.sheets.push({ax: axn, off: L[0] + fr * (L[1] - L[0]), s0: span[0], s1: span[1], id: s.id, name: s.name});
      }
    });
    if (kind === 2 && ar.sheets.length && ar.sheets[0].ax === "w") ar.cOff = ar.sheets[0].off;
    ar.mOffs = ar.sheets.filter(function (s) { return s.ax === "w"; }).map(function (s) { return s.off; }).sort(function (x, y) { return x - y; });
    return ar;
  }
  function fibreAt(ar, x, y, z) {
    var dx = x - ar.c[0], dy = y - ar.c[1], dz = z - ar.c[2], a = ar.a, w = ar.w, t = ar.t;
    var da = dx * a[0] + dy * a[1] + dz * a[2], dw = dx * w[0] + dy * w[1] + dz * w[2], dt = dx * t[0] + dy * t[1] + dz * t[2];
    var ua = (da - ar.la[0]) / ((ar.la[1] - ar.la[0]) || 1); ua = ua < 0 ? 0 : ua > 1 ? 1 : ua;
    var th = ar.p0 != null ? ar.p0 + (ar.p1 - ar.p0) * ua : ar.p, i, sep = 0;
    ar._band = -1;
    if (ar.bands) { var fw = (dw - ar.lw[0]) / ((ar.lw[1] - ar.lw[0]) || 1); for (i = 0; i < ar.bands.length; i++) if (fw >= ar.bands[i].f0 && fw <= ar.bands[i].f1) { th = ar.bands[i].p; ar._band = i; break; } }
    for (i = 0; i < ar.sheets.length; i++) {
      var s = ar.sheets[i]; if (ua < s.s0 || ua > s.s1) continue;
      var q = ((s.ax === "t" ? dt : dw) - s.off) / ar.half, g = Math.exp(-q * q); if (g > sep) sep = g;
    }
    var ca = Math.cos(th), sa = Math.sin(th), sg = 1, ox = w;
    if (ar.kind === 1) ox = t;
    else if (ar.kind === 2) sg = dw - ar.cOff >= 0 ? -1 : 1;                              // converge distally on the central sheet
    else if (ar.kind === 3) { var j = 0; if (ar.mOffs.length) { while (j < ar.mOffs.length && ar.mOffs[j] < dw) j++; } else j = dw >= ar.cOff ? 1 : 0; sg = j % 2 ? 1 : -1; }
    else if (ar.kind === 4) { ox = t; var off4 = ar.sheets.length ? ar.sheets[0].off : (ar.lt[0] + ar.lt[1]) / 2; sg = dt - off4 >= 0 ? 1 : -1; }
    else { ca = 1; sa = 0; }
    var f = ar._f; f[0] = a[0] * ca + ox[0] * sa * sg; f[1] = a[1] * ca + ox[1] * sa * sg; f[2] = a[2] * ca + ox[2] * sa * sg;
    ar._sep = sep;
    return f;
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
    followRotation: followRotation, angleDeg: angleDeg, pca3: pca3, archFrame: archFrame, fibreAt: fibreAt, speckleE: speckleE, dot: dot, cross: cross, unit: unit, rodrigues: rodrigues, STAR_NAMES: STAR_NAMES, probeMismatch: probeMismatch};
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
  var FS_MARK = "סימולציה מהמשים – לא סריקה";                               // Q289: the tiny in-image watermark of the clean full-screen CINE view

  var CODE_SRC = (function () { try { var cs = document.currentScript; return cs && cs.src ? "file" : "inline"; } catch (e) { return "inline"; } })();   // Q239
  function attachUltrasound(api, sh) {
    var tableSrc = "", usErr = null;
    var US = null, AC = null, C = null, T = null, geo = null, loadErr = null, loadPromise = null;
    var S = {
      open: false, mode: "star", probe: "linear", widths: {linear: 44, convex: 65, sector: 22}, freq: 7.5, depthCm: 5, gain: 0, tgc: 0, focusCm: 2.5, dr: 60,
      refKey: "long", rot: 0, tilt: 15, mTilt: 0, mTiltDir: 0, n: 6, spacing: 10, byTotal: false, total: 50, centered: false, sign: 1, follow: false, followSid: -1, followName: "",
      speckle: true, textures: true, reverb: true, noise: false, hidden: false, P: null, N: null, sel: 0, view: "matrix", lay: "auto", tab: "image", placing: false,
      cine: false, fps: 3, cineMode: "step", sec: "probe", pick3d: false, seed: 11,
      /* Q267 (4): "US diagnostic" preset -- suspected-pathology pick-list (collapses Controls, defaults CINE to
         continuous for THIS session only, pre-sets depth/dynamic-range/frequency, centres on a landmark the
         wizard below picks from this page's own structure list). preset = null | "tear" | "entrap" | "tendon" | "joint". */
      preset: null,
      /* Q267 (5): A/B side-by-side compare -- two independent probe placements (P2/N2), sharing every other
         control (depth, freq, gain, rotation, tilt/direction) with the primary placement. placeSlot picks which
         placement "Place on skin" currently arms. */
      ab: false, P2: null, N2: null, skinStruct2: -1, placeSlot: "A", abSnapMm: null,   // Q273: how far B was snapped from A's mirror image to reach skin (null = not seated by mirroring)
      /* Q267 (6): opt-in, OFF by default, live tissue-thickness readout at the cursor/cross-hair -- a SEPARATE
         toggle from the Q256 source-reliability dots (different system, viewer/parts_ui/parts_ui.js), per the brief. */
      thickness: false,
      /* Q289: CINE motion types (null = the Q257 continuous behaviour of the current mode) and their playback; extAuto = the 3-D window and
         the "long" sweep span the whole body part (the nearest long bone's length), else extCm (a window length centred on the probe) */
      fibres3d: true, motion: null, mBack: true, mLoop: true, mRev: false, mSpeed: 3, mPlane: null, extAuto: true, extCm: 30
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
      var spec, more = true;
      if (S.motion) {                                                          // Q289: a CINE motion type drives the probe along its mesh-derived path; the two Q257 branches below are untouched
        if (!mPath) { contState.raf = reqFrame(contTick); return; }
        more = motionStep(motionSpeed() * dt); spec = motionSpec(contState.pos);
      } else if (S.mode === "star") {
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
        frames[S.sel] = fr; paintView(S.sel, fr); if (S.mode === "star" && !S.motion) drawSchematic(); overlayPaced(); updateContReadout();
        if (S.motion) { drawArrow(fr); if (!more) { motionDone(); return; } }
        contState.raf = reqFrame(contTick);
      }, function (err) { contState.busy = false; console.error("continuous cine:", err); contState.raf = reqFrame(contTick); });
    }
    /* Q289: during a CINE the image has priority; the 3-D probe / plane / fibre overlay follows at what the device can afford: no sooner
       than 3x its own last measured cost (a GPU redraw of ~10 ms -> every 40 ms; a software renderer taking seconds no longer stalls
       the re-slicing loop and the page's input handling behind it) */
    var ovPace = {last: 0, cost: 0};
    function overlayPaced() {
      var now = Date.now(); if (now - ovPace.last < Math.max(40, 3 * ovPace.cost)) return;
      ovPace.last = now; updateOverlay(); ovPace.cost = Date.now() - now;
    }
    function updateContReadout() { if (ui.contOut) ui.contOut.textContent = contState.active ? ("live ≈ " + contState.fpsActual + " fps (" + contState.measMs + " ms/frame)") : ""; }

    /* ---------- Q289: CINE MOTION TYPES -- an extension of the Q257 continuous cine above (same contTick loop, same live quality
     * tier, same wall-clock pacing), not a second cine. Each type is a path computed from THIS page's own meshes, never invented:
     *   long  = the probe slides along the body part: the nearest long bone's own PCA axis on a limb (its ends = the part's length),
     *           the body's cranio-caudal axis on the trunk; at every sample it is re-seated on the real skin, face at 90° to it;
     *   circ  = the probe goes round the body part at its own level: rays from the section centre outward meet the part's own skin,
     *           and the face stays at 90° to the smoothed skin normal there (Q228's 15 mm area-weighted normal);
     *   rot   = the probe turns about its own axis (the skin normal) on the placed point, 180° (a probe's plane repeats after 180°);
     *   tilt  = the probe fans heel <-> toe about its contact point by ± the Tilt slider;
     *   track = the probe follows a chosen structure: its centreline is the per-slice centroid of the structure's OWN mesh vertices
     *           along its principal axis (a course that doubles back on that axis is not represented), and at each centreline point
     *           the probe sits on the skin nearest above it, face at 90° to the skin.
     * Playback: one way or back and forth, optionally looped; speed in mm/s (deg/s for rot / tilt), advanced by measured time. */
    var MOTIONS = [["long", "אורכי"], ["circ", "היקפי"], ["rot", "סיבוב"], ["tilt", "הטיה"], ["track", "מעקב מבנה"]];
    var MOTION_TIP = {long: "סריקה רציפה לאורך חלק הגוף (ציר העצם הארוכה הקרובה / ציר הגוף), המתמר ב-90° לעור", circ: "סריקה היקפית סביב חלק הגוף בגובה המתמר, ב-90° לעור בכל נקודה",
      rot: "סיבוב המתמר סביב צירו במקום (180°)", tilt: "הטיית המתמר עקב ↔ בוהן סביב נקודת המגע (± זווית ההטיה)", track: "מעקב אחר מבנה נבחר לאורך קו המרכז של הרשת שלו"};
    var M_MM_S = [5, 10, 20, 40, 80], M_DEG_S = [10, 20, 40, 80, 160];
    var LONG_BONE = /^(humerus|radius|ulna|femur|tibia|fibula|clavicle)\b|metacarp|metatars|phalan/i;
    var mPath = null, mGen = 0, mBuilding = false, mInfo = null;
    function motionSpeed() { var i = Math.max(1, Math.min(5, S.mSpeed)) - 1; return mPath && mPath.unit === "deg" ? M_DEG_S[i] : M_MM_S[i]; }
    function trunkPoint() { var bb = geo.bodyBox; return [(bb.lo[0] + bb.hi[0]) / 2, bb.lo[1] + 0.72 * (bb.hi[1] - bb.lo[1]), (bb.lo[2] + bb.hi[2]) / 2]; }   // +Y is cranial on every page (REF.long)
    function dist3(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
    function perpTo(v, a) { return sub(v, mul(a, dot(v, a))); }
    /* the skin triangles whose centroid lies inside [lo, hi]: every path ray below tests only this subset, not the whole body's skin */
    function skinSub(lo, hi) {
      var out = [], pos = geo.pos, idx = geo.idx, si, t;
      for (si = 0; si < geo.skinList.length; si++) {
        var st = geo.skinList[si], b = st * 6;
        if (geo.bbox[b] > hi[0] || geo.bbox[b + 3] < lo[0] || geo.bbox[b + 1] > hi[1] || geo.bbox[b + 4] < lo[1] || geo.bbox[b + 2] > hi[2] || geo.bbox[b + 5] < lo[2]) continue;
        for (t = geo.tStart[st]; t < geo.tStart[st + 1]; t++) {
          var a = idx[3 * t] * 3, c = idx[3 * t + 1] * 3, e = idx[3 * t + 2] * 3;
          var x = (pos[a] + pos[c] + pos[e]) / 3; if (x < lo[0] || x > hi[0]) continue;
          var y = (pos[a + 1] + pos[c + 1] + pos[e + 1]) / 3; if (y < lo[1] || y > hi[1]) continue;
          var z = (pos[a + 2] + pos[c + 2] + pos[e + 2]) / 3; if (z < lo[2] || z > hi[2]) continue;
          out.push(t);
        }
      }
      return Uint32Array.from(out);
    }
    function boxAround(pts, pad) { var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30]; pts.forEach(function (p) { for (var a = 0; a < 3; a++) { lo[a] = Math.min(lo[a], p[a] - pad); hi[a] = Math.max(hi[a], p[a] + pad); } }); return [lo, hi]; }
    /* outward ray from inside the body -> the part's own skin: the first crossing, carried through any overlapping skin patches that
       follow within 6 mm (the Z pages' skin is a set of overlapping patches, see the Info panel) */
    function subHit(sub, o, d, maxT) {
      var pos = geo.pos, idx = geo.idx, hits = [], k;
      for (k = 0; k < sub.length; k++) {
        var t = sub[k], a = idx[3 * t] * 3, b = idx[3 * t + 1] * 3, c = idx[3 * t + 2] * 3;
        var e1x = pos[b] - pos[a], e1y = pos[b + 1] - pos[a + 1], e1z = pos[b + 2] - pos[a + 2], e2x = pos[c] - pos[a], e2y = pos[c + 1] - pos[a + 1], e2z = pos[c + 2] - pos[a + 2];
        var px_ = d[1] * e2z - d[2] * e2y, py_ = d[2] * e2x - d[0] * e2z, pz_ = d[0] * e2y - d[1] * e2x, det = e1x * px_ + e1y * py_ + e1z * pz_;
        if (Math.abs(det) < 1e-12) continue;
        var inv = 1 / det, tx = o[0] - pos[a], ty = o[1] - pos[a + 1], tz = o[2] - pos[a + 2], u = (tx * px_ + ty * py_ + tz * pz_) * inv;
        if (u < 0 || u > 1) continue;
        var qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x, v = (d[0] * qx + d[1] * qy + d[2] * qz) * inv;
        if (v < 0 || u + v > 1) continue;
        var tt = (e2x * qx + e2y * qy + e2z * qz) * inv;
        if (tt > 1e-6 && tt < maxT) hits.push(tt);
      }
      if (!hits.length) return null;
      hits.sort(function (x, y) { return x - y; });
      var tEnd = hits[0]; for (k = 1; k < hits.length && hits[k] - tEnd < 6; k++) tEnd = hits[k];
      return {t: tEnd, point: [o[0] + d[0] * tEnd, o[1] + d[1] * tEnd, o[2] + d[2] * tEnd]};
    }
    function subNormal(sub, P, radius, ref) {                                  // LIB.smoothNormal's area-weighted, linearly faded normal, over the subset
      var pos = geo.pos, idx = geo.idx, acc = [0, 0, 0], k, w = 0;
      for (k = 0; k < sub.length; k++) {
        var t = sub[k], a = idx[3 * t] * 3, b = idx[3 * t + 1] * 3, c = idx[3 * t + 2] * 3;
        var cx = (pos[a] + pos[b] + pos[c]) / 3 - P[0]; if (cx > radius || cx < -radius) continue;
        var cy = (pos[a + 1] + pos[b + 1] + pos[c + 1]) / 3 - P[1]; if (cy > radius || cy < -radius) continue;
        var cz = (pos[a + 2] + pos[b + 2] + pos[c + 2]) / 3 - P[2], dd = Math.hypot(cx, cy, cz); if (dd > radius) continue;
        var n = triNormal(geo, t), f = 1 - dd / radius; if (dot(n, ref) < 0) n = mul(n, -1);
        acc = add(acc, mul(n, f)); w += f;
      }
      return w > 0 && len(acc) > 1e-9 ? unit(acc) : unit(ref);
    }
    /* the body part under the probe: the nearest long bone (bone class + a long-bone name, elongated, within 150 mm) gives a limb
       segment -- axis = that bone's own PCA axis oriented proximal -> distal (the end nearer the trunk is proximal), length = the bone's
       own extent along it. Otherwise the trunk: the cranio-caudal axis through the middle of the body at the probe's level. */
    function bodyRegion(P, N) {
      var best = null, i, R = 150, T = trunkPoint();
      for (i = 0; i < geo.n; i++) {
        var cl = classOf(i) || "", nm = String(geo.names[i] || "").replace(/^(right|left)\s+/i, "");
        if (cl.indexOf("bone") !== 0 || !LONG_BONE.test(nm)) continue;
        var b = i * 6; if (P[0] < geo.bbox[b] - R || P[0] > geo.bbox[b + 3] + R || P[1] < geo.bbox[b + 1] - R || P[1] > geo.bbox[b + 4] + R || P[2] < geo.bbox[b + 2] - R || P[2] > geo.bbox[b + 5] + R) continue;
        var v0 = geo.vStart[i], v1 = geo.vStart[i + 1], st = Math.max(1, Math.floor((v1 - v0) / 600)), k, dmin = 1e9;
        for (k = v0; k < v1; k += st) { var dd = Math.hypot(geo.pos[3 * k] - P[0], geo.pos[3 * k + 1] - P[1], geo.pos[3 * k + 2] - P[2]); if (dd < dmin) dmin = dd; }
        if (dmin < R && (!best || dmin < best.d)) best = {sid: i, d: dmin};
      }
      if (best) {
        var ax = axisOf(best.sid);
        if (ax && ax.elong > 3) {
          var a = ax.a.slice(), t0 = 1e9, t1 = -1e9, w0 = geo.vStart[best.sid], w1 = geo.vStart[best.sid + 1], s2 = Math.max(1, Math.floor((w1 - w0) / 2000)), q;
          for (q = w0; q < w1; q += s2) { var tq = (geo.pos[3 * q] - ax.c[0]) * a[0] + (geo.pos[3 * q + 1] - ax.c[1]) * a[1] + (geo.pos[3 * q + 2] - ax.c[2]) * a[2]; if (tq < t0) t0 = tq; if (tq > t1) t1 = tq; }
          if (dist3(add(ax.c, mul(a, t1)), T) < dist3(add(ax.c, mul(a, t0)), T)) { a = mul(a, -1); var sw = t0; t0 = -t1; t1 = -sw; }
          return {kind: "limb", sid: best.sid, name: String(geo.names[best.sid] || ""), a: a, c: ax.c, t0: t0, t1: t1, len: t1 - t0};
        }
      }
      var c = sub(P, mul(N, 100)), o = sub(P, mul(N, 2)), back = mul(N, -1), h, guard = 0;   // the far side of the trunk along the inward normal (skipping overlapping patches)
      while (guard++ < 4 && (h = LIB.skinHit(geo, o, back, null))) { if (h.t > 20) { c = mul(add(P, h.point), 0.5); break; } o = add(h.point, mul(back, 1)); }
      var bb = geo.bodyBox;
      return {kind: "trunk", sid: -1, name: "", a: [0, -1, 0], c: c, t0: -(bb.hi[1] - c[1]), t1: c[1] - bb.lo[1], len: null};
    }
    /* the window shown in 3D and swept by "long": the whole part (auto, on a limb) or a set length centred on the probe */
    function regionWindow(reg, P) {
      var tP = dot(sub(P, reg.c), reg.a);
      if (S.extAuto && reg.kind === "limb") return [reg.t0, reg.t1];
      var half = S.extCm * 5; return [Math.max(reg.t0, tP - half), Math.min(reg.t1, tP + half)];
    }
    function trackSid() {
      if (S.followSid >= 0) return S.followSid;
      var id = null; try { id = api.selectedId ? api.selectedId() : null; } catch (e) {}
      if (id == null || !geo) return -1;
      if (typeof id === "number") return id >= 0 && id < geo.n ? id : -1;
      for (var i = 0; i < geo.n; i++) if (geo.recs[i] && geo.recs[i].id === id) return i;
      return -1;
    }
    function rotFor(N, u) { var u0 = tangentRef(unit(N), orientRef()); return Math.atan2(dot(cross(u0, u), unit(N)), dot(u0, u)) / DEG; }
    /* image-plane long axis per sample: "long" = along the part / structure (marker proximal = screen left), "trans" = across it (marker
       to the patient's right where that is defined, then kept continuous along the path) */
    function orientSamples(smp, plane) {
      var prev = null;
      smp.forEach(function (s) {
        var w = s.w, u;
        if (plane === "long") { u = perpTo(w, s.N); if (len(u) < 1e-3) u = perpTo(cross(s.N, [1, 0, 0]), s.N); u = unit(u); }
        else {
          u = cross(s.N, w); if (len(u) < 1e-3) u = perpTo([1, 0, 0], s.N); u = unit(u);
          if (prev) { if (dot(u, prev) < 0) u = mul(u, -1); } else if (Math.abs(u[0]) > 0.3 && u[0] > 0) u = mul(u, -1);
        }
        s.u = u; s.rot = rotFor(s.N, u); prev = u;
      });
      var steps = smp.slice(1).map(function (s, k) { return dist3(s.P, smp[k].P); }), med = steps.slice().sort(function (x, y) { return x - y; })[steps.length >> 1] || 1, acc = 0;
      smp.forEach(function (s, k) { if (k) acc += steps[k - 1] > 4 * med ? med : steps[k - 1]; s.s = acc; s.jump = !!(k && steps[k - 1] > 4 * med); });   // across a skipped stretch the probe jumps (one step), it is not dragged through the body
      return acc;
    }
    function motionKey() {
      var sid = S.motion === "track" ? trackSid() : -1;
      return [S.motion, S.P && S.P.map(function (x) { return x.toFixed(1); }).join(), S.N && S.N.map(function (x) { return x.toFixed(3); }).join(), S.extAuto, S.extCm, S.mPlane || "", sid, S.rot, S.tilt, S.refKey, S.follow ? S.followSid : -1].join("|");
    }
    function planeOf(kind) { return S.mPlane || (kind === "circ" ? "long" : "trans"); }
    function chunked(list, fn, done, my) {                                    // keeps the page responsive while a path is computed
      var k = 0; (function go() { if (my !== mGen) return; var t0 = Date.now(); while (k < list.length && Date.now() - t0 < 30) fn(list[k], k++); if (k < list.length) setTimeout(go, 0); else done(); })();
    }
    function buildMotion(kind) {                                              // -> Promise(path) for the current probe / settings
      var my = ++mGen, P = S.P.slice(), N = unit(S.N), reg = bodyRegion(P, N), win = regionWindow(reg, P), base = sweepRot(0, 0).rot;
      var path = {kind: kind, key: motionKey(), region: reg, win: win, unit: "mm", plane: planeOf(kind), samples: [], total: 0, baseRot: base, P0: P, N0: N, done: false};
      mBuilding = true; syncMotionUi(); setStatus("Computing the " + kind + " path from the meshes ...");
      return new Promise(function (resolve, reject) {
        function finish() {
          mBuilding = false;
          if (my !== mGen) return reject(new Error("superseded"));
          if (path.unit === "mm") {
            if (path.samples.length < 2) { syncMotionUi(); return reject(new Error(kind === "track" ? "no skin found above that structure" : "no skin found along the path")); }
            path.total = orientSamples(path.samples, path.plane);
          }
          resolve(path);
        }
        if (kind === "rot") { path.unit = "deg"; path.total = 180; return finish(); }
        if (kind === "tilt") { path.unit = "deg"; path.amp = Math.max(5, Math.min(30, S.tilt)); path.total = 2 * path.amp; return finish(); }
        var a = reg.a, c = reg.c, tP = dot(sub(P, c), a), A0 = add(c, mul(a, tP)), r0 = perpTo(sub(P, A0), a), list = [], sb, k;
        r0 = len(r0) > 1 ? unit(r0) : unit(perpTo(N, a));
        if (kind === "long") {
          var step = Math.max(3, (win[1] - win[0]) / 160), n = Math.max(2, Math.floor((win[1] - win[0]) / step) + 1);
          for (k = 0; k < n; k++) list.push(win[0] + k * step);
          var bx = boxAround([add(c, mul(a, win[0])), add(c, mul(a, win[1]))], 320); sb = skinSub(bx[0], bx[1]);
          chunked(list, function (t) {
            var O = add(c, mul(a, t)), h = subHit(sb, O, r0, 350);
            if (h) path.samples.push({t: t, P: h.point, N: subNormal(sb, h.point, 15, r0), w: a});
          }, function () {                                                     // keep the contiguous run of samples that contains the probe
            var s = path.samples, k0 = 0, i, gap = Math.max(25, step * 3);
            for (i = 1; i < s.length; i++) if (dist3(s[i].P, P) < dist3(s[k0].P, P)) k0 = i;
            var lo = k0, hi = k0; while (lo > 0 && dist3(s[lo - 1].P, s[lo].P) < gap) lo--; while (hi < s.length - 1 && dist3(s[hi + 1].P, s[hi].P) < gap) hi++;
            path.samples = s.slice(lo, hi + 1); finish();
          }, my);
        } else if (kind === "circ") {
          for (k = 0; k <= 120; k++) list.push(k * 3);
          var C = reg.kind === "limb" ? A0 : c, bx2 = boxAround([C], 320); sb = skinSub(bx2[0], bx2[1]); path.center = C;
          chunked(list, function (deg) {
            var r = unit(rodrigues(r0, a, deg * DEG)), h = subHit(sb, C, r, 350);
            if (h) path.samples.push({deg: deg, P: h.point, N: subNormal(sb, h.point, 15, r), w: a, t: h.t});
          }, function () {                                                     // where the part's skin is fused with a neighbour's (thighs at the groin, arm at the axilla) the ray
            var ts = path.samples.map(function (q) { return q.t; }).sort(function (x, y) { return x - y; }), med = ts[ts.length >> 1] || 0;   // runs on into the other part: those directions are skipped, not invented
            var n0 = path.samples.length; path.samples = path.samples.filter(function (q) { return q.t <= 1.6 * med; }); path.skipped = (n0 - path.samples.length) * 3; finish();
          }, my);
        } else if (kind === "track") {
          var sid = trackSid(); if (sid < 0) { mBuilding = false; return reject(new Error("no structure chosen")); }
          var cl = centreline(sid); path.sid = sid; path.name = String(geo.names[sid] || ""); path.centre = cl;
          if (!cl || cl.length < 2) { mBuilding = false; return reject(new Error("that structure is too small for a centreline")); }
          var bx3 = boxAround(cl, 260); sb = skinSub(bx3[0], bx3[1]);
          var h0 = nearestSkin(cl[0]), dPrev = h0 ? unit(sub(h0.point, cl[0])) : N;
          chunked(cl, function (Ck, i) {
            var Tk = unit(sub(cl[Math.min(cl.length - 1, i + 1)], cl[Math.max(0, i - 1)])), dp = perpTo(dPrev, Tk), bestH = null, bestD = null;
            dp = len(dp) > 1e-3 ? unit(dp) : unit(perpTo(N, Tk));
            [0, 20, -20, 40, -40].forEach(function (ang) { var d = unit(rodrigues(dp, Tk, ang * DEG)), h = subHit(sb, Ck, d, 300); if (h && (!bestH || h.t < bestH.t)) { bestH = h; bestD = d; } });
            if (bestH) { path.samples.push({i: i, P: bestH.point, N: subNormal(sb, bestH.point, 15, bestD), w: Tk, C: Ck, depth: bestH.t}); dPrev = bestD; }
          }, finish, my);
        } else { mBuilding = false; reject(new Error("unknown motion " + kind)); }
      });
    }
    /* centreline of a structure from its own mesh: vertices binned along the PCA axis (~5 mm slices), centroid per slice (>= 3 vertices),
       3-point smoothed, ordered proximal -> distal (the end nearer the trunk first) */
    function centreline(sid) {
      var ax = axisOf(sid); if (!ax) return null;
      var v0 = geo.vStart[sid], v1 = geo.vStart[sid + 1], st = Math.max(1, Math.floor((v1 - v0) / 8000)), k, t0 = 1e9, t1 = -1e9, ts = [];
      for (k = v0; k < v1; k += st) { var t = (geo.pos[3 * k] - ax.c[0]) * ax.a[0] + (geo.pos[3 * k + 1] - ax.c[1]) * ax.a[1] + (geo.pos[3 * k + 2] - ax.c[2]) * ax.a[2]; ts.push(t); if (t < t0) t0 = t; if (t > t1) t1 = t; }
      var L = t1 - t0, nb = Math.max(4, Math.min(160, Math.round(L / 5))), acc = [], j;
      for (j = 0; j < nb; j++) acc.push([0, 0, 0, 0]);
      for (k = v0, j = 0; k < v1; k += st, j++) { var bi = Math.min(nb - 1, Math.floor((ts[j] - t0) / (L || 1) * nb)), A = acc[bi]; A[0] += geo.pos[3 * k]; A[1] += geo.pos[3 * k + 1]; A[2] += geo.pos[3 * k + 2]; A[3]++; }
      var pts = acc.filter(function (A) { return A[3] >= 3; }).map(function (A) { return [A[0] / A[3], A[1] / A[3], A[2] / A[3]]; });
      if (pts.length < 2) return pts;
      var sm = pts.map(function (p, i) { if (!i || i === pts.length - 1) return p; return mul(add(add(pts[i - 1], mul(p, 2)), pts[i + 1]), 0.25); });
      var T = trunkPoint(); if (dist3(sm[sm.length - 1], T) < dist3(sm[0], T)) sm.reverse();
      return sm;
    }
    function lerp3(a, b, f) { return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f]; }
    function sampleAt(pos) {                                                 // linear interpolation between the two path samples around arc length pos
      var s = mPath.samples, lo = 0, hi = s.length - 1;
      if (pos <= s[0].s) return {P: s[0].P, N: s[0].N, u: s[0].u, k: 0, f: 0};
      if (pos >= s[hi].s) return {P: s[hi].P, N: s[hi].N, u: s[hi].u, k: hi, f: 0};
      while (hi - lo > 1) { var m = (lo + hi) >> 1; if (s[m].s <= pos) lo = m; else hi = m; }
      var f = (pos - s[lo].s) / Math.max(1e-9, s[hi].s - s[lo].s);
      if (s[hi].jump) { var j = f < 0.5 ? lo : hi; return {P: s[j].P, N: s[j].N, u: s[j].u, k: j, f: 0}; }
      var N =unit(lerp3(s[lo].N, s[hi].N, f)), u = unit(perpTo(lerp3(s[lo].u, s[hi].u, f), N));
      return {P: lerp3(s[lo].P, s[hi].P, f), N: N, u: u, k: lo, f: f};
    }
    function motionSpec(pos) {
      var m = mPath, round = function (x) { return Math.round(x); };
      if (m.unit === "deg") {
        if (m.kind === "rot") return {id: S.sel, P: m.P0, N: m.N0, tilt: 0, dir: 0, off: 0, rotOverride: m.baseRot + pos, label: "live rotate " + round(pos) + "° of 180°", short: "rot " + round(pos) + "°"};
        var ang = pos - m.amp;
        return {id: S.sel, P: m.P0, N: m.N0, tilt: Math.abs(ang), dir: ang >= 0 ? 90 : 270, off: 0, rotOverride: m.baseRot, label: "live fan " + (ang >= 0 ? "heel " : "toe ") + Math.abs(round(ang)) + "°", short: "fan " + round(ang) + "°"};
      }
      var q = sampleAt(pos);
      return {id: S.sel, P: q.P, N: q.N, tilt: 0, dir: 0, off: 0, rotOverride: rotFor(q.N, q.u), label: "live " + m.kind + " " + round(pos) + " / " + round(m.total) + " mm", short: m.kind + " " + round(pos) + " mm"};
    }
    function motionStart() { var d0 = S.mRev ? -1 : 1; contState.pos = d0 > 0 ? 0 : mPath.total; contState.dir = d0; mPath.done = false; }
    /* one wall-clock step along the path; false once a run that does not loop has reached its end */
    function motionStep(dist) {
      var T = mPath.total, d0 = S.mRev ? -1 : 1, p = contState.pos + contState.dir * dist;
      if (p > T || p < 0) {
        var edge = p > T ? T : 0, outbound = contState.dir === d0;
        if (outbound && S.mBack) { contState.dir = -contState.dir; contState.pos = edge; return true; }   // turn round at the far end
        if (S.mLoop) { contState.pos = d0 > 0 ? 0 : T; contState.dir = d0; return true; }                 // back at the start: go again
        contState.pos = edge; return false;
      }
      contState.pos = p; return true;
    }
    function motionDone() {                                                  // a one-way / one back-and-forth run finished: keep its last frame on screen
      if (mPath) mPath.done = true;
      contState.active = false; if (contState.raf) { cancelFrame(contState.raf); contState.raf = 0; }
      S.cine = false; updateOverlay(); updateContReadout(); syncUi(); setStatus("CINE run finished (" + (S.mBack ? "back and forth" : "one way") + ").");
      if (modeRefresh) modeRefresh();
    }
    function ensureMotion() {                                                // (re)build the path when the probe / settings changed, then (re)start the run
      var key = motionKey();
      if (mPath && mPath.key === key && mPath.kind === S.motion) { if (mPath.done || !mPath.started) { motionStart(); mPath.started = true; } frameFs(); return; }
      mPath = null; var kind = S.motion;
      buildMotion(kind).then(function (p) {
        if (S.motion !== kind) return;
        mPath = p; mPath.started = true; motionStart(); setStatus(); syncMotionUi(); frameFs();
      }, function (e) {
        if (String(e && e.message) === "superseded") return;
        setStatus("CINE " + kind + ": " + (e && e.message || e)); toastAll("לא ניתן לחשב מסלול: " + (e && e.message || e));
        if (S.motion === kind) { S.motion = null; setCine(false); }
        syncMotionUi();
      });
    }
    function chooseMotion(k) {
      if (!geo || !S.P) { loadTable().then(function () { if (geo && S.P) chooseMotion(k); }); return; }
      if (S.motion === k && S.cine) { setCine(false); S.motion = null; if (mPath) mPath.started = false; syncMotionUi(); return; }   // a second tap on the playing type stops it
      S.motion = k;
      if (k === "track" && trackSid() < 0) {                                 // nothing chosen yet: the next tap on a structure in the 3D view picks it
        setCine(false); S.pick3d = true; syncUi(); syncMotionUi(); setStatus("Tap the structure to track in the 3D view."); toastAll("הקש על המבנה למעקב במודל התלת-ממדי"); return;
      }
      if (S.ab) setAb(false);
      S.cineMode = "continuous"; setCine(false); setCine(true); syncMotionUi();
    }
    /* the direction arrow at the edge of the US image: the probe's travel projected into the 3-D view next to it (so it points the way
       the probe moves on screen), a curved arrow for a turn about the probe's own axis, and the anatomical name of the direction */
    function motionInfo(fr) {
      var m = mPath; if (!m || !fr) return null;
      var dirS = contState.dir, he = "", trav = null, curved = 0, pos = contState.pos, reg = m.region;
      if (m.kind === "rot") { curved = dirS > 0 ? -1 : 1; he = "סיבוב " + (dirS > 0 ? "נגד כיוון השעון" : "עם כיוון השעון") + " · " + Math.round(pos) + "°"; }
      else if (m.kind === "tilt") { var pf0 = LIB.probeFrame(m.N0, orientRef(), m.baseRot, 0, 0); trav = mul(pf0.e0, dirS); he = "הטיה לכיוון " + (dirS > 0 ? "העקב" : "הבוהן") + " · " + Math.round(pos - m.amp) + "°"; }
      else {
        var a = sampleAt(Math.max(0, pos - 3)).P, b = sampleAt(Math.min(m.total, pos + 3)).P; trav = mul(unit(sub(b, a)), dirS);
        if (m.kind === "circ") { var cw = dot(cross(sub(fr.O, m.center), trav), reg.a) > 0; he = "היקפי " + (cw ? "עם כיוון השעון" : "נגד כיוון השעון") + " (במבט מ" + (reg.kind === "limb" ? "פרוקסימלי" : "למעלה") + ") · " + Math.round(pos) + "/" + Math.round(m.total) + " מ\"מ" + (m.skipped ? " · דילוג " + m.skipped + "° (העור מחובר לחלק סמוך)" : ""); }
        else {
          var along = dot(trav, m.kind === "track" ? unit(sub(m.centre[m.centre.length - 1], m.centre[0])) : reg.a) >= 0, limb = m.kind === "track" ? !!(reg.kind === "limb") : reg.kind === "limb";
          he = (m.kind === "track" ? "מעקב " + m.name.replace(/_/g, " ") + " → " : "") + (along ? (limb ? "דיסטלי" : "קאודלי") : (limb ? "פרוקסימלי" : "קרניאלי")) + " · " + Math.round(pos) + "/" + Math.round(m.total) + " מ\"מ";
        }
      }
      var ang = null;
      if (trav) { try { var s0 = api.toScreen(fr.O), s1 = api.toScreen(add(fr.O, mul(trav, 30))); if (s0 && s1 && Math.hypot(s1[0] - s0[0], s1[1] - s0[1]) > 3) ang = Math.atan2(s1[1] - s0[1], s1[0] - s0[0]) / DEG; } catch (e) {} }
      return {kind: m.kind, he: he, ang: ang, curved: curved, toward: trav && ang == null ? (dot(trav, unit(sub(api.view().eye, fr.O))) > 0 ? "out" : "in") : null};
    }
    function drawArrow(fr) {
      if (!ui.arrow) return;
      var info = motionInfo(fr); mInfo = info; ui.arrowBox.hidden = !info; if (!info) return;
      var cv = ui.arrow, ctx = cv.getContext("2d"), W = cv.width, H = cv.height, cx = W / 2, cy = H / 2, R = W * 0.32;
      ctx.clearRect(0, 0, W, H); ctx.lineWidth = W * 0.07; ctx.strokeStyle = ctx.fillStyle = "#ffd37a"; ctx.lineCap = "round";
      function head(x, y, a) { var L = W * 0.2; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - L * Math.cos(a - 0.5), y - L * Math.sin(a - 0.5)); ctx.lineTo(x - L * Math.cos(a + 0.5), y - L * Math.sin(a + 0.5)); ctx.closePath(); ctx.fill(); }
      if (info.curved) {
        var a0 = -2.4, a1 = 1.3, cwise = info.curved > 0;
        ctx.beginPath(); ctx.arc(cx, cy, R, a0, a1); ctx.stroke();
        var ae = cwise ? a1 : a0, ex = cx + R * Math.cos(ae), ey = cy + R * Math.sin(ae);
        head(ex, ey, ae + (cwise ? Math.PI / 2 : -Math.PI / 2));
      } else if (info.ang != null) {
        var r = info.ang * DEG, x0 = cx - Math.cos(r) * R, y0 = cy - Math.sin(r) * R, x1 = cx + Math.cos(r) * R, y1 = cy + Math.sin(r) * R;
        ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1 - Math.cos(r) * W * 0.12, y1 - Math.sin(r) * W * 0.12); ctx.stroke(); head(x1, y1, r);
      } else {                                                               // travel straight toward / away from the 3-D camera
        ctx.beginPath(); ctx.arc(cx, cy, R, 0, 6.2832); ctx.stroke();
        if (info.toward === "out") { ctx.beginPath(); ctx.arc(cx, cy, W * 0.08, 0, 6.2832); ctx.fill(); }
        else { ctx.beginPath(); ctx.moveTo(cx - R * 0.6, cy - R * 0.6); ctx.lineTo(cx + R * 0.6, cy + R * 0.6); ctx.moveTo(cx + R * 0.6, cy - R * 0.6); ctx.lineTo(cx - R * 0.6, cy + R * 0.6); ctx.stroke(); }
      }
      ui.arrowTxt.textContent = info.he;
      ui.arrowBox.setAttribute("data-kind", info.kind); ui.arrowBox.setAttribute("data-ang", info.ang == null ? "" : String(Math.round(info.ang)));
    }

    /* ---------- Q289: the clean split full-screen CINE view: 3-D of the part | the live image (+ direction arrow, tiny watermark),
     * nothing else on screen. Exit: the small ✕ or Esc. The one secondary sheet (motion type, playback, speed, plane, window) opens
     * only from the small ⋯ handle. Inside the US workspace mode the mode's own docking does the placing; elsewhere a minimal copy. */
    var fs = {on: false, el: null, s3d: null, sUs: null, docks: [], cam: null, orbit: 0}, modeCtx = null, modeRedock = null, modeRefresh = null, FS_Z = 2147482000;
    function fsOn() { return fs.on; }
    function fsLayout() { return window.innerWidth >= window.innerHeight ? "row" : "col"; }   // phone portrait: 3-D above, image below; landscape / desktop: side by side
    function fsPlace(d) {
      var r = d.slot.getBoundingClientRect(), st = d.el.style, imp = {position: "fixed", left: r.left + "px", top: r.top + "px", width: r.width + "px", height: r.height + "px", right: "auto", bottom: "auto",
        margin: "0", "min-width": "0", "min-height": "0", "max-width": "none", "max-height": "none", "z-index": String(FS_Z + 1), overflow: "hidden", display: d.display || "", transform: "none", visibility: "visible"};
      Object.keys(imp).forEach(function (k) { if (imp[k] === "") st.removeProperty(k); else st.setProperty(k, imp[k], "important"); });
    }
    function modelEl() { return document.getElementById(api.kind === "webgl" ? "view" : "app"); }
    function fsDockAll() {
      if (modeCtx) { modeCtx.dock(root, fs.sUs, FS_Z + 1); modeCtx.modelDock([fs.s3d], FS_Z + 1); return; }
      if (!fs.docks.length) [[modelEl(), fs.s3d, ""], [root, fs.sUs, "flex"]].forEach(function (x) { if (x[0]) fs.docks.push({el: x[0], slot: x[1], style: x[0].getAttribute("style"), display: x[2]}); });
      fs.docks.forEach(fsPlace); fireResize();
    }
    function fsUndockAll() {
      if (modeCtx) { if (modeRedock) modeRedock(); return; }
      fs.docks.forEach(function (d) { if (d.style == null) d.el.removeAttribute("style"); else d.el.setAttribute("style", d.style); }); fs.docks = []; fireResize();
    }
    function fsRelayout() { if (!fs.on) return; fs.el.setAttribute("data-lay", fsLayout()); if (!modeCtx) fs.docks.forEach(fsPlace); fireResize(); relayoutViews(); frameFs(); }
    var fsIdleT = 0;
    function fsWake() { if (!fs.on) return; document.body.classList.remove("fs-idle"); clearTimeout(fsIdleT); fsIdleT = setTimeout(function () { if (fs.on && fs.sheet.hidden) document.body.classList.add("fs-idle"); }, 2600); }
    function buildFs() {
      if (fs.el) return;
      fs.s3d = el("div", {class: "fs-3d"}); fs.sUs = el("div", {class: "fs-us"});
      fs.x = el("button", {type: "button", class: "fs-x", "aria-label": "יציאה ממסך מלא (Esc)", title: "יציאה (Esc)", text: "✕", onclick: function () { setFs(false); }});
      fs.more = el("button", {type: "button", class: "fs-more", "aria-label": "אפשרויות", "aria-expanded": "false", title: "אפשרויות: סוג תנועה, השמעה, מהירות, טווח", text: "⋯", onclick: function () { fs.sheet.hidden = !fs.sheet.hidden; fs.more.setAttribute("aria-expanded", String(!fs.sheet.hidden)); fsWake(); }});
      fs.sheet = el("div", {class: "fs-sheet", hidden: true}, [motionSheet({open: true, inFs: true})]);
      fs.el = el("div", {id: "us-cinefs", role: "dialog", "aria-label": "CINE מסך מלא", "data-lay": fsLayout()}, [fs.s3d, fs.sUs]);
      ["pointermove", "pointerdown", "keydown"].forEach(function (ev) { document.addEventListener(ev, fsWake, true); });
      [fs.el, fs.x, fs.more, fs.sheet].forEach(function (x) { document.body.appendChild(x); });   // the buttons sit above the docked halves, so outside the backdrop's stacking context
      window.addEventListener("resize", function () { if (fs.on && !firing) fsRelayout(); });
      document.addEventListener("keydown", function (e) { if (fs.on && (e.key === "Escape" || e.key === "Esc")) { e.preventDefault(); setFs(false); } });
    }
    /* frame the 3-D half on the part's window (its whole length, or the set window around the probe), looking from the probe's side */
    function frameFs() {
      if (!fs.on || !mPath || !geo) return;
      var reg = mPath.region, win = mPath.win, c = reg.c, a = reg.a, mid = add(c, mul(a, (win[0] + win[1]) / 2)), Lw = Math.max(60, win[1] - win[0]);
      if (mPath.kind === "track" && mPath.centre) { var bxT = boxAround(mPath.centre, 0); mid = mul(add(bxT[0], bxT[1]), 0.5); Lw = Math.max(Lw, dist3(bxT[0], bxT[1])); }   // the tracked structure's whole course, at least the part's window
      var r = fs.s3d.getBoundingClientRect(), asp = r.width > 0 ? Math.max(1, r.height / r.width) : 1;
      try { api.focus(mid, Lw * 1.3 * asp + 120); } catch (e) {}
      var N = mPath.N0, h = Math.hypot(N[0], N[2]);
      if (h > 0.3 && api.orbit) {
        var azOf = function () { var v = api.view(); return Math.atan2(v.eye[0] - v.target[0], v.eye[2] - v.target[2]); };
        var want = Math.atan2(N[0], N[2]), wrap = function (x) { while (x > Math.PI) x -= 2 * Math.PI; while (x < -Math.PI) x += 2 * Math.PI; return x; };
        var d = wrap(want - azOf());
        if (Math.abs(d) > 0.05) { api.orbit(d); fs.orbit += d; if (Math.abs(wrap(want - azOf())) > Math.abs(d)) { api.orbit(-2 * d); fs.orbit -= 2 * d; } }
      }
      if (api.redraw) api.redraw();
    }
    function setFs(on) {
      on = !!on; if (on === fs.on) return;
      if (on) {
        if (!S.open) setOpen(true);
        buildFs(); fs.on = true; fs.orbit = 0;
        try { var v = api.view(); fs.cam = {t: v.target.slice(), d: dist3(v.eye, v.target)}; } catch (e) { fs.cam = null; }
        S.tab = "image"; document.body.classList.add("us-fs"); fs.el.hidden = false; fs.el.setAttribute("data-lay", fsLayout());
        if (S.view !== "single") { S.view = "single"; }
        fsDockAll(); relayoutViews(); fsWake();
        if (!S.motion) chooseMotion("long"); else if (!S.cine) { S.cineMode = "continuous"; setCine(true); } else frameFs();
      } else {
        fs.on = false; document.body.classList.remove("us-fs"); document.body.classList.remove("fs-idle"); fs.el.hidden = true; fs.sheet.hidden = true; fs.more.setAttribute("aria-expanded", "false");
        fsUndockAll();
        if (fs.cam) { try { if (fs.orbit && api.orbit) api.orbit(-fs.orbit); api.focus(fs.cam.t, fs.cam.d); } catch (e) {} }
        applyLayout(); relayoutViews();
      }
      syncMotionUi(); if (modeRefresh) modeRefresh();
    }
    /* one compact control group, built for the panel, the US mode popover and the full-screen sheet; every copy stays in sync */
    var moSheets = [];
    function motionSheet(opts) {
      opts = opts || {};
      function b(text, attr, title, fn) { var x = el("button", Object.assign({type: "button", text: text, title: title || "", "aria-pressed": "false"}, attr)); x.addEventListener("click", function (e) { e.stopPropagation(); fn(); syncMotionUi(); }); return x; }
      function rng(attr, min, max, step, label, fn) { var x = el("input", Object.assign({type: "range", min: String(min), max: String(max), step: String(step), "aria-label": label}, attr)); x.addEventListener("input", function () { fn(+x.value); syncMotionUi(); }); x.addEventListener("click", function (e) { e.stopPropagation(); }); return x; }
      function restart() { if (mPath) mPath.started = false; if (S.motion && S.cine) { setCine(false); setCine(true); } }
      var chips = el("div", {class: "mo-row mo-chips"}, MOTIONS.map(function (m) { return b(m[1], {"data-mo": m[0]}, MOTION_TIP[m[0]], function () { chooseMotion(m[0]); }); }));
      var more = el("div", {class: "mo-more"}, [
        el("div", {class: "mo-row"}, [b("חד-כיווני", {"data-mp": "once"}, "מתחילת המסלול לסופו", function () { S.mBack = false; }), b("הלוך ושוב", {"data-mp": "back"}, "לסוף המסלול וחזרה", function () { S.mBack = true; }),
          b("לולאה", {"data-ml": "1"}, "חזרה על הריצה ללא הפסקה", function () { S.mLoop = !S.mLoop; }), b("⇆ מהקצה השני", {"data-mr": "1"}, "להתחיל מהקצה השני של המסלול", function () { S.mRev = !S.mRev; restart(); })]),
        el("div", {class: "mo-row"}, [el("label", {text: "מהירות"}), rng({"data-ms": "1"}, 1, 5, 1, "מהירות", function (v) { S.mSpeed = v; }), el("output", {"data-mso": "1"})]),
        el("div", {class: "mo-row"}, [el("label", {text: "מישור"}), b("רוחבי", {"data-pl": "trans"}, "התמונה חוצה את חלק הגוף / המבנה", function () { S.mPlane = "trans"; restart(); }), b("אורכי", {"data-pl": "long"}, "התמונה לאורך חלק הגוף / המבנה", function () { S.mPlane = "long"; restart(); })]),
        el("div", {class: "mo-row"}, [el("label", {text: "טווח"}), b("כל חלק הגוף", {"data-ea": "1"}, "התלת-ממד והסריקה האורכית באורך העצם הארוכה של חלק הגוף", function () { S.extAuto = !S.extAuto; restart(); }),
          rng({"data-ex": "1"}, 10, 60, 2, "טווח בס\"מ סביב המתמר", function (v) { S.extCm = v; S.extAuto = false; clearTimeout(timers.ext); timers.ext = setTimeout(restart, 250); }), el("output", {"data-exo": "1"})])
      ]);
      var tail = el("div", {class: "mo-row mo-tail"});
      if (!opts.open) { var mb = el("button", {type: "button", class: "mo-morebtn", "data-mm": "1", "aria-expanded": "false", text: "⋯ עוד", title: "השמעה, מהירות, מישור, טווח"}); mb.addEventListener("click", function (e) { e.stopPropagation(); more.hidden = !more.hidden; mb.setAttribute("aria-expanded", String(!more.hidden)); }); tail.appendChild(mb); more.hidden = true; }
      if (!opts.inFs) tail.appendChild(b("⛶ מסך מלא", {"data-fs": "1", class: "mo-fs"}, "תצוגה נקייה מפוצלת: תלת-ממד | אולטרסאונד (יציאה: ✕ או Esc)", function () { setFs(true); }));
      tail.appendChild(el("output", {class: "mo-st", "data-mst": "1"}));
      var box = el("div", {class: "us-mo", dir: "rtl"}, [chips, tail, more]);
      moSheets.push(box); syncMotionUi(); return box;
    }
    function syncMotionUi() {
      moSheets.forEach(function (box) {
        Array.prototype.forEach.call(box.querySelectorAll("[data-mo]"), function (x) { x.setAttribute("aria-pressed", String(S.motion === x.getAttribute("data-mo"))); });
        Array.prototype.forEach.call(box.querySelectorAll("[data-mp]"), function (x) { x.setAttribute("aria-pressed", String((x.getAttribute("data-mp") === "back") === !!S.mBack)); });
        var q = function (s) { return box.querySelector(s); }, pl = S.motion ? planeOf(S.motion) : (S.mPlane || "");
        q("[data-ml]").setAttribute("aria-pressed", String(!!S.mLoop)); q("[data-mr]").setAttribute("aria-pressed", String(!!S.mRev));
        q("[data-ms]").value = String(S.mSpeed); q("[data-mso]").textContent = ["איטי מאוד", "איטי", "בינוני", "מהיר", "מהיר מאוד"][S.mSpeed - 1] + " (" + M_MM_S[S.mSpeed - 1] + " מ\"מ/ש')";
        Array.prototype.forEach.call(box.querySelectorAll("[data-pl]"), function (x) { x.setAttribute("aria-pressed", String(pl === x.getAttribute("data-pl"))); x.disabled = S.motion === "rot" || S.motion === "tilt"; });
        var reg = mPath && mPath.region, auto = !!(S.extAuto && reg && reg.kind === "limb");
        q("[data-ea]").setAttribute("aria-pressed", String(!!S.extAuto)); q("[data-ex]").value = String(auto ? Math.min(60, Math.round(reg.len / 10)) : S.extCm);
        q("[data-exo]").textContent = auto ? (Math.round(reg.len / 10) + " ס\"מ (" + reg.name + ")") : (S.extCm + " ס\"מ סביב המתמר");
        q("[data-mst]").textContent = mBuilding ? "מחשב מסלול…" : (S.motion && mPath && S.cine ? "▶" : "");
        var f = q("[data-fs]"); if (f) f.setAttribute("aria-pressed", String(fs.on));
      });
      if (ui.arrowBox && !S.motion) ui.arrowBox.hidden = true;
    }
    function toastAll(msg) { if (modeToast) modeToast(msg); else setStatus(msg); }
    var modeToast = null;

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
    function classOf(sid) { return geo && C && geo.cls ? C.T.classes[geo.cls[sid]].key : null; }
    /* Q267 (4): "US diagnostic" preset -- a short pick-list of suspected-pathology categories, each pre-setting depth / dynamic
       range ("tissue contrast") / frequency (all parameters this tool already exposes, not invented), tied to the imaging
       kernel's own tissue-class key (clinical/data/imaging_tissues.json) so the landmark search below only offers structures
       of the relevant kind that this page's OWN geometry actually has. Depth/DR/freq are starting points for that category on
       a typical adult body, not a cited clinical protocol -- framed as such in the button's own title. */
    var PRESETS = [
      {key: "tear", label: "קרע שריר", clsKey: "muscle", depthCm: 4, dr: 55, freq: 12, question: "איזה שריר?"},
      {key: "entrap", label: "entrapment עצבי", clsKey: "nerve", depthCm: 3, dr: 50, freq: 12, question: "איזה עצב?"},
      {key: "tendon", label: "גיד-רצועה", clsKey: "tendon_ligament", depthCm: 2.5, dr: 45, freq: 12, question: "איזה גיד / רצועה?"},
      {key: "joint", label: "מפרק-בורסה", clsKey: "synovial", depthCm: 5, dr: 60, freq: 7.5, question: "איזה מפרק?"}
    ];
    function candidatesForClass(clsKey) {
      var out = [], i; if (!geo) return out;
      for (i = 0; i < geo.n; i++) if (classOf(i) === clsKey) out.push({sid: i, name: geo.names[i]});
      out.sort(function (a, b) { return a.name < b.name ? -1 : a.name > b.name ? 1 : 0; });
      return out;
    }
    function applyPreset(key) {
      var d = null, i; for (i = 0; i < PRESETS.length; i++) if (PRESETS[i].key === key) d = PRESETS[i];
      if (!d || !geo) return;
      S.preset = key;
      root.classList.add("ctl-off"); ui.ctlBtn.setAttribute("aria-pressed", "false");   // Q267 (4): collapse the non-imaging controls, reusing the existing Controls toggle
      S.cineMode = "continuous";                                         // defaulted for THIS preset only, never globally (Q257's step cine stays the default elsewhere)
      S.depthCm = d.depthCm; S.dr = d.dr; S.freq = d.freq; S.focusCm = d.depthCm * 0.5;
      syncUi(); setStatus(d.label + ": depth " + d.depthCm + " cm, dynamic range " + d.dr + " dB, " + d.freq + " MHz (typical starting values, not a cited protocol).");
      var cands = candidatesForClass(d.clsKey);
      if (!cands.length) { setStatus(ui.status.textContent + " No " + d.label + " structure found on this body: probe position unchanged."); hideWizard(); refresh(true); return; }
      if (cands.length === 1) { placeAtStructure(cands[0].sid, "A"); setStatus("Centred near " + cands[0].name + "."); hideWizard(); refresh(true); setCine(true); return; }
      showWizard(d, cands);
    }
    /* Q267 (10): the inline wizard strip, only ever shown when there is a REAL question to ask (>=2 candidates). Dismissible;
       dismissing it leaves the depth / dynamic range / CINE already applied above untouched -- only the landmark is skipped. */
    var pendingCands = [];
    function showWizard(d, cands) {
      if (!ui.wizard) return;
      pendingCands = cands; ui.wizQ.textContent = d.question; ui.wizInput.value = ""; renderWizard(""); ui.wizard.hidden = false;
    }
    function hideWizard() { if (ui.wizard) ui.wizard.hidden = true; }
    function renderWizard(q) {
      var ql = String(q || "").trim().toLowerCase(), rows = pendingCands.filter(function (c) { return !ql || c.name.toLowerCase().indexOf(ql) >= 0; }).slice(0, 60);
      ui.wizRes.innerHTML = "";
      rows.forEach(function (c) {
        ui.wizRes.appendChild(btn(c.name.replace(/_/g, " "), "", function () {
          placeAtStructure(c.sid, "A"); setStatus("Centred near " + c.name + "."); hideWizard(); refresh(true); setCine(true);
        }));
      });
      if (!rows.length) ui.wizRes.appendChild(el("span", {class: "us-status", text: "No match."}));
    }
    /* Q289: the architecture frame of a muscle structure (cached): its id matched to ultrasound_tissues.json "architecture" (side
       suffix and page prefixes stripped; a separately meshed head falls back to its muscle, without the part bands) */
    var archCache = {};
    function archRow(sid) {
      var A = US && US.architecture; if (!A || !geo || sid < 0 || sid >= geo.n || classOf(sid) !== "muscle") return null;
      var id = String((geo.recs[sid] && geo.recs[sid].id) || "").toLowerCase().replace(/_zfill\d+$/, "").replace(/^zan_/, "").replace(/_(l|r)$/, ""), parts = id.split("_"), k;
      for (k = parts.length; k > 0; k--) { var key = parts.slice(0, k).join("_"); if (A.muscles[key]) return {key: key, row: A.muscles[key], exact: k === parts.length}; }
      return null;
    }
    function archOf(sid) {
      if (archCache[sid] !== undefined) return archCache[sid];
      var m = archRow(sid), ar = null;
      if (m) {
        var bb = geo.bodyBox, cc = structCentroid(sid) || [0, 0, 0], midx = (bb.lo[0] + bb.hi[0]) / 2, R = US.architecture.render || {};
        ar = LIB.archFrame(geo.pos, geo.vStart[sid], geo.vStart[sid + 1], m.row, {prox: trunkPoint(), dirs: {anterior: [0, 0, 1], superior: [0, 1, 0], medial: [midx >= cc[0] ? 1 : -1, 0, 0]},
          half: R.septum_half_mm, gain: R.septum_gain, noParts: !m.exact});
        if (ar) { ar.key = m.key; ar.row = m.row; }
      }
      archCache[sid] = ar; return ar;
    }
    function archLabel(sid) {                                                // the badge line for the structure under the cursor
      if (sid == null || sid < 0 || sid >= 65534 || !geo || classOf(sid) !== "muscle") return "";
      var ar = archOf(sid);
      if (!ar) return " | fibres: generic line of action (mesh long axis), no architecture data";
      var r = ar.row, A = US.architecture, src = (r.pr && r.pr.length ? r.pr.map(function (k) { var x = A.references[k]; return x ? x.cite.split(".")[0] + " PMID " + x.pmid : k; }) : (r.s || []).map(function (i) { return A.sources[i].split(" -- ")[0]; })).join("; ");
      var sep = ar.sheets.length ? "; septa: " + ar.row.septa.map(function (x) { return x.name + " (" + x.refs.map(function (k) { return (A.references[k] || {}).pmid ? "PMID " + A.references[k].pmid : k; }).join(", ") + ")"; }).join("; ") : "";
      return " | fibres: " + (r.t || "?") + " " + (r.p0 != null ? r.p0 + "→" + r.p1 : r.p) + "° (" + src + ")" + sep + " -- RULE-BASED layout in this mesh";
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
    /* Q267 (4/5): nearest skin point to an arbitrary 3-D point P -- NOT a single fixed-direction ray (abdomenPlacement /
       defaultPlacement already do that, from directly above or from the camera eye), but a small fixed set of candidate
       directions, each cast as a ray from far outside the body TOWARD P (same LIB.skinHit() every placement already
       uses), keeping whichever hit lands closest to P. Good enough to seat a probe near a landmark that is not
       necessarily visible from "straight down" or "from the camera" -- still a geometric approximation the clinician
       can move afterward with "Place on skin", never claimed as exact. */
    var NEAREST_DIRS = (function () {
      var out = [], ax = [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]], a, b, c;
      ax.forEach(function (d) { out.push(d); });
      for (a = -1; a <= 1; a += 2) for (b = -1; b <= 1; b += 2) for (c = -1; c <= 1; c += 2) out.push(LIB.unit([a, b, c]));
      return out;
    })();
    function nearestSkin(P) {
      if (!geo) return null;
      var best = null, i;
      for (i = 0; i < NEAREST_DIRS.length; i++) {
        var d = NEAREST_DIRS[i], o = [P[0] + d[0] * 700, P[1] + d[1] * 700, P[2] + d[2] * 700];
        var h = LIB.skinHit(geo, o, [-d[0], -d[1], -d[2]], null);
        if (h) { var dd = Math.hypot(h.point[0] - P[0], h.point[1] - P[1], h.point[2] - P[2]); h.out = d; h.dd = dd; if (!best || dd < best.dd) best = {h: h, dd: dd}; }   // Q273: h.out = the side the ray came from (outside the body), h.dd = how far the seat is from P
      }
      return best ? best.h : null;
    }
    /* Q273: seat slot B on the skin nearest to A's mirror image. The outward normal is taken from the ray that FOUND the skin
       (it always comes from outside the body) -- Q267 oriented it "away from the mirrored point", which inverted the probe
       whenever the mirror image itself lay outside the body (an arm hanging away from the trunk): B then started under the
       skin and the B-mode read NO SKIN CONTACT. Returns the snap distance (mm) or null when no skin was found at all. */
    function seatMirrorB() {
      if (!S.P) return null;
      var M = mirrorPoint(S.P), h = nearestSkin(M); if (!h) return null;
      var nrm = LIB.smoothNormal(geo, h.point, 15, null, h.struct);
      if (LIB.dot(nrm, h.out) < 0) nrm = [-nrm[0], -nrm[1], -nrm[2]];
      S.P2 = h.point; S.N2 = nrm; S.skinStruct2 = h.struct; S.abSnapMm = h.dd;
      return h.dd;
    }
    /* structure centroid, cheap (stride-sampled like LIB.pcaAxis) -- used only to pick a landmark point, not a measurement */
    function structCentroid(sid) {
      var v0 = geo.vStart[sid], v1 = geo.vStart[sid + 1], step = Math.max(1, Math.floor((v1 - v0) / 400)), k, cx = 0, cy = 0, cz = 0, m = 0;
      for (k = v0; k < v1; k += step) { cx += geo.pos[3 * k]; cy += geo.pos[3 * k + 1]; cz += geo.pos[3 * k + 2]; m++; }
      return m ? [cx / m, cy / m, cz / m] : null;
    }
    function placeAtStructure(sid, slot) {
      var c = structCentroid(sid); if (!c) return false;
      var h = nearestSkin(c); if (!h) return false;
      var nrm = LIB.smoothNormal(geo, h.point, 15, null, h.struct);
      var outward = sub(h.point, c); if (LIB.dot(nrm, outward) < 0) nrm = [-nrm[0], -nrm[1], -nrm[2]];
      if (slot === "B") { S.P2 = h.point; S.N2 = nrm; S.skinStruct2 = h.struct; } else { S.P = h.point; S.N = nrm; S.skinStruct = h.struct; }
      return true;
    }
    function defaultPlacement(fromView) {                                      // "Screen centre": the skin under the centre of the 3D view
      if (!fromView && abdomenPlacement()) return;
      var v = api.view(), o = v.eye, d = [v.target[0] - v.eye[0], v.target[1] - v.eye[1], v.target[2] - v.eye[2]];
      if (!placeRay(o, d, true)) abdomenPlacement();
    }
    var modeArm = false;                                                 // Q272: the US workspace mode keeps "place on skin" armed after every tap
    function onPlaceClick(e) {
      if (!S.open || (!S.placing && !S.pick3d) || !geo) return false;
      var r = api.ray(e);
      if (S.pick3d) {                                                         // choose the organ to follow
        S.pick3d = false; if (ui.pickBtn) ui.pickBtn.setAttribute("aria-pressed", "false");
        var h = api.pick(e);
        if (h && h.i != null) setFollow(h.i); else setStatus("Nothing picked.");
        return true;
      }
      var hit;
      if (S.ab && S.placeSlot === "B") {                                 // Q267 (5): "Place on skin" routes to whichever slot is currently armed
        hit = placeRay2(r.o, r.d, "B");
      } else hit = placeRay(r.o, r.d);
      S.placing = !!modeArm; syncUi();
      if (hit) { S.sel = 0; refresh(true); }
      return true;
    }
    function placeRay2(o, d, slot) {                                     // Q267 (5): same as placeRay(), but writes into the B slot instead of S.P/S.N
      if (!geo) return null;
      var h = LIB.skinHit(geo, o, LIB.unit(d), cutKeep());
      if (!h) { setStatus("No skin under that point (the ray misses the body, or the skin there is cut away)."); return null; }
      var nrm = LIB.smoothNormal(geo, h.point, 15, null, h.struct);
      if (LIB.dot(nrm, d) > 0) nrm = [-nrm[0], -nrm[1], -nrm[2]];
      S.P2 = h.point; S.N2 = nrm; S.skinStruct2 = h.struct;
      return h;
    }
    function setFollow(sid) {
      S.followSid = sid; S.followName = geo.names[sid] || ""; var a = LIB.pcaAxis(geo.pos, geo.vStart[sid], geo.vStart[sid + 1]);
      S.follow = !!a; if (!a) setStatus("That structure has too few vertices for a long axis."); else setStatus("Following " + S.followName + " (long axis from PCA, elongation " + a.elong.toFixed(1) + ")");
      syncUi(); refresh(true);
      if (S.motion === "track") { S.cineMode = "continuous"; setCine(false); setCine(true); }   // Q289: the structure to track was just picked
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
      if (S.ab) {                                                        // Q267 (5): two independent placements, EVERY other control shared (depth/freq/gain/rotation/tilt/direction -- the same S.rot/S.mTilt/S.mTiltDir sliders the sweep mode already exposes)
        return [{id: 0, tilt: S.mTilt, dir: S.mTiltDir, off: 0, P: S.P, N: S.N, label: "A", short: "A"},
          {id: 1, tilt: S.mTilt, dir: S.mTiltDir, off: 0, P: S.P2 || S.P, N: S.N2 || S.N, label: "B", short: "B"}];
      }
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
      var P0 = spec.P || S.P, N0 = spec.N || S.N;                        // Q267 (5): an A/B-slot spec carries its OWN placement; every other spec still falls back to the single shared S.P/S.N exactly as before
      var pf = LIB.probeFrame(N0, orientRef(), rot, spec.tilt, spec.dir);
      var O = [P0[0] + pf.e[0] * spec.off, P0[1] + pf.e[1] * spec.off, P0[2] + pf.e[2] * spec.off], shift = 0;
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
      if (S.ab) return {maxDim: 440, maxLines: 256};                     // Q267 (5): always exactly 2 slots, both full quality
      if (S.mode === "star") return idx === S.sel ? {maxDim: 480, maxLines: 256} : {maxDim: 320, maxLines: 192};
      return S.n <= 4 ? {maxDim: 440, maxLines: 256} : S.n <= 6 ? {maxDim: 380, maxLines: 224} : {maxDim: 320, maxLines: 192};
    }
    function refFrame(spec) {                                                   // fixed frame of the whole star / sweep: the centre (perpendicular) frame, or the sweep's own tilt
      var N0 = spec.N || S.N, P0 = spec.P || S.P;
      var rot = spec.rotOverride != null ? spec.rotOverride : S.rot, pf = LIB.probeFrame(N0, orientRef(), rot, S.mode === "star" && !S.ab ? 0 : spec.tilt, S.mode === "star" && !S.ab ? 0 : spec.dir);
      return {O: P0, u: pf.u, b: pf.b, e: pf.e};
    }
    function simOpts(fr, extra) {
      var p = US.probes[S.probe];
      return Object.assign({AC: AC, geom: fr.geom, plan: fr.plan, lab: fr.lab, sid: fr.sid, freq: S.freq, depthMm: S.depthCm * 10, gainDb: S.gain, tgcDb: S.tgc, focusMm: S.focusCm * 10,
        speckle: S.speckle, textures: S.textures, reverb: S.reverb, noise: S.noise, seed: S.seed,        // Q246: ONE seed for every frame: the speckle belongs to the body, not to the frame
        elevMm: S.mode === "star" ? 0 : fr.spec.off, frame: {O: fr.O, u: fr.pf.u, b: fr.pf.b, e: fr.pf.e, zoff: 0}, ref: refFrame(fr.spec), axisOf: axisOf, archOf: archOf}, extra || {});
    }
    function rasterKey(spec, q) { var P0 = spec.P || S.P, N0 = spec.N || S.N; return [S.probe, probeW(), S.depthCm, P0.map(function (x) { return x.toFixed(2); }).join(), N0.map(function (x) { return x.toFixed(4); }).join(), spec.tilt, spec.dir, spec.off, spec.rotOverride != null ? spec.rotOverride : S.rot, S.refKey, q.maxDim, q.maxLines, S.hidden ? 1 : 0].join("|"); }
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
      if (S.ab) {                                                        // Q267 (5): both probes are "live" at once, not just the selected slot
        frames.forEach(function (fr) { if (fr) { probeMesh(probeG, fr.O, fr.pf, fr.geom); markerMesh(markG, fr.O, fr.pf, fr.geom); } });
      } else { probeMesh(probeG, sel.O, sel.pf, sel.geom); markerMesh(markG, sel.O, sel.pf, sel.geom); }
      frames.forEach(function (fr, i) {
        if (!fr) return;
        var out = fanOutline(fr.geom, 14).map(function (p) { return toWorld(fr.O, fr.pf, p[0], p[1] + (fr.sim ? fr.sim.ysk : 0)); }), n = out.length, j;
        var isSel = S.ab || i === S.sel;                                 // Q267 (5): both A and B count as "selected" for the overlay (both are live at once)
        var target = isSel ? selLine : lineG;
        for (j = 0; j < n; j++) tube(target, out[j], out[(j + 1) % n], isSel ? r * 1.0 : r * 0.55);
        if (isSel || S.mode === "sweep") {
          var cen = [0, 0, 0]; out.forEach(function (p) { cen[0] += p[0] / n; cen[1] += p[1] / n; cen[2] += p[2] / n; });
          if (isSel) for (j = 0; j < n; j++) fillG.tri(cen, out[j], out[(j + 1) % n]);
        }
        if (isSel) tube(axisG, toWorld(fr.O, fr.pf, 0, -20 + (fr.sim ? fr.sim.ysk : 0)), toWorld(fr.O, fr.pf, 0, fr.geom.depth + (fr.sim ? fr.sim.ysk : 0)), r * 0.45);
      });
      var fibG = new Geo(), sepG = new Geo();
      if (S.fibres3d) { try { fibreGeo(sel, r, fibG, sepG); } catch (eF) { console.error("fibre overlay:", eF); } }   // Q289
      return [["probe", probeG, {color: 0x39424d, alpha: 1, pass: "opaque", lit: true}], ["marker", markG, {color: 0xff5a3c, alpha: 1, pass: "opaque", lit: false}],
        ["fill", fillG, {color: 0x6cb4ff, alpha: 0.28, pass: "trans", lit: false}], ["lines", lineG, {color: 0xffd37a, alpha: 0.8, pass: "xray", lit: false}],
        ["sel", selLine, {color: 0x7fe0a0, alpha: 1, pass: "xray", lit: false}], ["axis", axisG, {color: 0xff9d8a, alpha: 0.9, pass: "xray", lit: false}],
        ["fibres", fibG, {color: 0xffc4b8, alpha: 0.55, pass: "xray", lit: false}], ["septa", sepG, {color: 0xfff0c0, alpha: 0.35, pass: "xray", lit: false}]];
    }
    var OV_NAMES = ["probe", "marker", "fill", "lines", "sel", "axis", "fibres", "septa"];
    /* Q289: faint fibre lines (+ documented septa as thin sheets) of the muscles the selected image cuts, in the 3-D view: the same
       archFrame / fibreAt the B-mode uses, so both halves show one rule. A muscle without architecture data gets its line of action. */
    var genCache = {};
    function imageMuscles(fr, maxN) {
      if (!fr || !fr.sid) return [];
      var cnt = {}, k, n = fr.sid.length, st = Math.max(1, Math.floor(n / 6000));
      for (k = 0; k < n; k += st) { var q = fr.sid[k]; if (q < 65534 && classOf(q) === "muscle") cnt[q] = (cnt[q] || 0) + 1; }
      return Object.keys(cnt).map(Number).sort(function (x, y) { return cnt[y] - cnt[x]; }).slice(0, maxN);
    }
    function fibreGeo(fr, r, fibG, sepG) {
      imageMuscles(fr, 6).forEach(function (sid) {
        var ar = archOf(sid), generic = !ar;
        if (generic) { if (genCache[sid] === undefined) genCache[sid] = LIB.archFrame(geo.pos, geo.vStart[sid], geo.vStart[sid + 1], {t: "fusiform", p: 0}, {prox: trunkPoint()}); ar = genCache[sid]; }
        if (!ar) return;
        var A = ar.a, W = ar.w, T = ar.t, c = ar.c, P = function (da, dw, dt) { return [c[0] + A[0] * da + W[0] * dw + T[0] * dt, c[1] + A[1] * da + W[1] * dw + T[1] * dt, c[2] + A[2] * da + W[2] * dw + T[2] * dt]; };
        if (generic) { tube(fibG, P(ar.la[0] * 0.9, 0, 0), P(ar.la[1] * 0.9, 0, 0), r * 0.35); return; }
        var L = Math.max(6, Math.min(28, 0.22 * (ar.la[1] - ar.la[0]))), i, j, k2;
        for (i = 0; i < 5; i++) for (j = 0; j < 6; j++) {                      // a 5 x 6 grid over the mid-thickness section of the mesh frame
          var da = ar.la[0] + (ar.la[1] - ar.la[0]) * (0.12 + 0.76 * i / 4), dw = ar.lw[0] * 0.75 + (ar.lw[1] - ar.lw[0]) * 0.75 * (j + 0.5) / 6, dt = (ar.lt[0] + ar.lt[1]) / 2 + (j % 2 ? 0.25 : -0.25) * (ar.lt[1] - ar.lt[0]);
          var p0 = P(da, dw, dt), f = LIB.fibreAt(ar, p0[0], p0[1], p0[2]).slice();
          tube(fibG, [p0[0] - f[0] * L / 2, p0[1] - f[1] * L / 2, p0[2] - f[2] * L / 2], [p0[0] + f[0] * L / 2, p0[1] + f[1] * L / 2, p0[2] + f[2] * L / 2], r * 0.3);
        }
        ar.sheets.forEach(function (sh) {
          var a0 = ar.la[0] + sh.s0 * (ar.la[1] - ar.la[0]), a1 = ar.la[0] + sh.s1 * (ar.la[1] - ar.la[0]), o = ar.sheets && sh.ax === "t" ? ar.lw : ar.lt, q0 = o[0] * 0.8, q1 = o[1] * 0.8;
          var cn = sh.ax === "t" ? [P(a0, q0, sh.off), P(a1, q0, sh.off), P(a1, q1, sh.off), P(a0, q1, sh.off)] : [P(a0, sh.off, q0), P(a1, sh.off, q0), P(a1, sh.off, q1), P(a0, sh.off, q1)];
          sepG.tri(cn[0], cn[1], cn[2]); sepG.tri(cn[0], cn[2], cn[3]); sepG.tri(cn[0], cn[2], cn[1]); sepG.tri(cn[0], cn[3], cn[2]);
          for (k2 = 0; k2 < 4; k2++) tube(sepG, cn[k2], cn[(k2 + 1) % 4], r * 0.25);
        });
      });
    }
    function updateOverlay() {
      if (!overlay) overlay = makeOverlay(api);
      if (!overlay) return;
      var items = null; try { items = overlayItems(); } catch (e) { console.error("ultrasound overlay:", e); }
      OV_NAMES.forEach(function (nm) { overlay.remove(nm); });
      if (items) items.forEach(function (it) { overlay.set(it[0], [it[1]], it[2]); });
      if (api.redraw) api.redraw();
    }
    function clearOverlay() { if (!overlay) return; OV_NAMES.forEach(function (nm) { overlay.remove(nm); }); if (api.redraw) api.redraw(); }
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
      /* Q267 (10): a thin, dismissible inline bar -- never a modal */
      ".us-wizard{flex:0 0 auto;display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:6px 8px;background:#1b2a1f;border-bottom:1px solid #3a6a46}",
      ".us-wizard[hidden]{display:none}",
      ".us-wizard .wiz-q{font-weight:700;white-space:nowrap}",
      ".us-wizard input{min-width:120px;flex:0 1 160px}",
      ".us-wizard .wiz-res{display:flex;gap:4px;flex-wrap:wrap;max-height:4.6em;overflow:auto}",
      ".us-wizard .wiz-res button{min-height:26px;padding:2px 8px;font-size:12px}",
      ".us-wizard .wiz-x{margin-left:auto;min-height:26px;padding:1px 8px}",
      /* Q267 (6): opt-in tissue-thickness readout, a small non-intrusive strip near the view, separate from the Q256 dots */
      ".us-thick{flex:0 0 auto;padding:3px 8px;font:12px ui-monospace,Menlo,monospace;color:#cfe6ff;background:#10161f;border-bottom:1px solid var(--line)}",
      ".us-thick[hidden]{display:none}",
      "@media (max-width:520px),(max-height:520px){#us-root button{min-height:36px}#us-root select,#us-root input[type=number]{min-height:36px}}",
      /* Q289: CINE motion types + the clean split full-screen view */
      ".us-mo{display:grid;gap:6px;direction:rtl;font-family:Heebo,system-ui,sans-serif}",
      ".us-mo .mo-row{display:flex;gap:6px;flex-wrap:wrap;align-items:center}",
      ".us-mo .mo-more[hidden]{display:none}.us-mo .mo-more{display:grid;gap:6px}",
      ".us-mo button{min-height:34px;padding:4px 11px;border-radius:999px;font:600 13px Heebo,system-ui,sans-serif}",
      ".us-mo input[type=range]{flex:1 1 120px;min-width:110px;min-height:30px}",
      ".us-mo output{font-size:12px;opacity:.85}",
      ".us-mo .mo-st{margin-inline-start:auto}",
      ".us-arrow{position:absolute;left:8px;bottom:8px;z-index:6;display:flex;align-items:center;gap:6px;pointer-events:none;max-width:70%;direction:rtl}",
      ".us-arrow[hidden]{display:none}",
      ".us-arrow canvas{position:static;width:46px;height:46px;flex:0 0 auto;background:rgba(0,0,0,.45);border-radius:999px}",
      ".us-arrow span{font:700 12px Heebo,system-ui,sans-serif;color:#ffd37a;text-shadow:0 1px 2px #000,0 0 4px #000;line-height:1.25}",
      "#us-cinefs{position:fixed;inset:0;z-index:2147482000;background:#000;display:flex;flex-direction:row}",
      "#us-cinefs[hidden]{display:none}",
      "#us-cinefs[data-lay=col]{flex-direction:column}",
      "#us-cinefs .fs-3d,#us-cinefs .fs-us{flex:1 1 50%;min-width:0;min-height:0}",
      "#us-cinefs .fs-3d{background:#0b0f14}",
      ".fs-x,.fs-more{display:none;position:fixed;z-index:2147482003;top:calc(8px + env(safe-area-inset-top,0px));width:40px;height:40px;border-radius:999px;border:1px solid rgba(255,255,255,.28);background:rgba(10,14,20,.6);color:#fff;font:600 18px system-ui,sans-serif;cursor:pointer;transition:opacity .45s;align-items:center;justify-content:center;padding:0}",
      ".fs-x{left:8px}.fs-more{left:56px}",
      "body.us-fs .fs-x,body.us-fs .fs-more{display:flex}",
      "body.us-fs.fs-idle .fs-x,body.us-fs.fs-idle .fs-more{opacity:.22}",
      ".fs-sheet{display:none;position:fixed;z-index:2147482003;left:8px;top:calc(56px + env(safe-area-inset-top,0px));width:min(430px,calc(100vw - 16px));max-height:70vh;overflow:auto;background:rgba(14,19,26,.96);border:1px solid #2a3646;border-radius:12px;padding:10px;color:#e6edf5}",
      "body.us-fs .fs-sheet:not([hidden]){display:block}",
      ".fs-sheet button{background:#161d27;border:1px solid #2a3646;color:#e6edf5;cursor:pointer}",
      ".fs-sheet button[aria-pressed=true]{background:#1f3b5c;border-color:#6cb4ff;color:#fff}",
      ".fs-sheet input[type=range]{accent-color:#6cb4ff}",
      "body.us-fs #us-root>*:not(.us-views){display:none!important}",
      "body.us-fs #us-root{border:0!important;background:#000!important}",
      "body.us-fs #us-root .us-views{padding:0;gap:0}",
      "body.us-fs #us-root .us-view{border:0;cursor:default}",
      "body.us-fs #us-root .us-schem{display:none!important}",
      "body.us-fs #app>header,body.us-fs #app>aside,body.us-fs #inspector,body.us-fs .mob-bar,body.us-fs #tools,body.us-fs #hover,body.us-fs #frame-note,body.us-fs #axes,body.us-fs #scalebar,body.us-fs #brand,body.us-fs #topright,body.us-fs #rail,body.us-fs #info,body.us-fs #foot,body.us-fs #modal,body.us-fs #cut-panel,body.us-fs #lab-layer,body.us-fs #lab-panel,body.us-fs #pm-panel,body.us-fs #ng-panel,body.us-fs #pose-panel,body.us-fs #pose-banner,body.us-fs #sym-banner,body.us-fs #sym-panel,body.us-fs #nmsk-clinical-bar,body.us-fs #nmsk-clinical-toast,body.us-fs #us-tab3d{display:none!important}",
      "body.us-fs #app{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:minmax(0,1fr)!important;min-height:0!important}",
      "body.us-fs #app>#stage{grid-column:1!important;grid-row:1!important}"
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
        (ui.ctlBtn = el("button", {type: "button", id: "us-ctlbtn", title: "Show / hide the controls (more room for the images)", "aria-pressed": "true", onclick: function () { var off = root.classList.toggle("ctl-off"); ui.ctlBtn.setAttribute("aria-pressed", String(!off)); setTimeout(relayoutViews, 50); }, text: "Controls"})),
        el("button", {type: "button", title: "Assumptions, acoustic table, sources and limits of the simulation", onclick: function () { ui.info.classList.toggle("show"); }, text: "Info"}),
        el("button", {type: "button", title: "Save the selected image as PNG (with the badge)", onclick: savePng, text: "PNG"}),
        el("button", {type: "button", title: "Close ultrasound", "aria-label": "Close ultrasound", onclick: function () { setOpen(false); }, text: "✕"})
      ]);
      ui.info = el("div", {class: "us-info"});
      ui.diag = el("div", {class: "us-diag"}); ui.hint = el("div", {class: "us-hint", role: "note"}); ui.hint.style.display = "none";
      /* Q267 (10): the inline wizard strip -- a thin, dismissible bar, never a modal; shown only when applyPreset() finds a
         real question to ask (>=2 candidates for the chosen category). */
      ui.wizard = el("div", {class: "us-wizard", role: "note", hidden: true}, [
        (ui.wizQ = el("span", {class: "wiz-q"})),
        (ui.wizInput = el("input", {type: "search", placeholder: "type to filter…", "aria-label": "Search", oninput: function () { renderWizard(ui.wizInput.value); }})),
        (ui.wizRes = el("span", {class: "wiz-res"})),
        btn("✕", "Dismiss (the depth / dynamic range / CINE already set above stay as they are)", hideWizard, {class: "wiz-x"})
      ]);
      ui.views = el("div", {class: "us-views star"});
      ui.schem = el("canvas", {class: "us-schem", width: "84", height: "84", "aria-hidden": "true"}); ui.views.appendChild(ui.schem);
      /* Q289: the scan-direction arrow, at the edge of the image area (shown while a CINE motion type plays) */
      ui.arrowBox = el("div", {class: "us-arrow", hidden: true, role: "img", "aria-label": "כיוון הסריקה"}, [(ui.arrow = el("canvas", {width: "92", height: "92"})), (ui.arrowTxt = el("span", {text: ""}))]);
      ui.views.appendChild(ui.arrowBox);
      ui.views.addEventListener("click", function () { if (fs.on) { if (!fs.sheet.hidden) { fs.sheet.hidden = true; fs.more.setAttribute("aria-expanded", "false"); } else setCine(!S.cine); fsWake(); } });   // full screen: tap the image = pause / play
      ui.read = el("div", {class: "us-read", text: "Click the skin in the 3D view to place the probe; hover an image for tissue, structure, depth and echo level."});
      /* Q267 (6): opt-in, off by default (S.thickness) -- see tog("thickness", ...) in buildControls() */
      ui.thick = el("div", {class: "us-thick", hidden: true});
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
      [div, head, ui.diag, ui.hint, ui.wizard, ui.info, ui.views, ui.read, ui.thick, ui.ctl].forEach(function (x) { root.appendChild(x); });
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
      /* Q267 (4): "US diagnostic" preset pick-list */
      var rPreset = el("div", {class: "us-row"}, [el("label", {text: "US diagnostic:"})].concat(PRESETS.map(function (d) {
        return (ui["presetBtn_" + d.key] = btn(d.label, "Depth " + d.depthCm + " cm, dynamic range " + d.dr + " dB, " + d.freq + " MHz, continuous CINE, controls collapsed, centred on a " + d.clsKey.replace("_", "/") + " landmark if one can be found and picked", function () { applyPreset(d.key); }));
      })));
      ui.placeBtn = btn("Place on skin", "Arm, then click / tap the skin in the 3D view", function () { S.placing = !S.placing; syncUi(); setStatus(S.placing ? "Click or tap the skin in the 3D view." : ""); });
      var r4 = el("div", {class: "us-row"}, [ui.placeBtn, btn("Screen centre", "Put the probe on the skin at the centre of the 3D view", function () { defaultPlacement(true); S.sel = 0; refresh(true); }),
        (ui.orLong = btn("Longitudinal", "Long axis along the body / limb axis, marker cranial (screen left = cranial)", function () { S.refKey = "long"; S.rot = 0; syncUi(); refresh(); })),
        (ui.orTrans = btn("Transverse", "Long axis across, marker to the patient's right (screen left = patient right)", function () { S.refKey = "trans"; S.rot = 0; syncUi(); refresh(); })),
        btn("Zoom to probe", "Move the 3D camera close to the probe", function () { if (S.P) { api.focus(S.P, 420); } })]);
      /* Q267 (5): A/B side-by-side compare -- a toggle, not a 3rd mode: two independent probe placements that share every
         other control (depth, freq, gain, rotation, tilt/direction). "Place on skin" above arms whichever slot is picked here. */
      var rAB = el("div", {class: "us-row"}, [
        (ui.abBtn = btn("A / B compare", "Show two linked probe views at once (one per slot below); every slider except placement stays shared", function () { setAb(!S.ab); })),
        el("span", {class: "us-status", text: "placing:"}),
        (ui.slotABtn = btn("A", "“Place on skin” now arms slot A", function () { S.placeSlot = "A"; syncUi(); })),
        (ui.slotBBtn = btn("B", "“Place on skin” now arms slot B", function () { S.placeSlot = "B"; syncUi(); })),
        (ui.mirrorBtn = btn("mirror B ← A", "Put B at A's point reflected across the body midline, re-seated on the real skin there", mirrorBtoA))
      ]);
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
        (ui.moBox = motionSheet({})),                                     // Q289: CINE motion types (+ "⋯ עוד" for playback / speed / plane / window, ⛶ full screen)
        slider("Frame", 1, 9, 1, "frame", function (v) { return "#" + v; }, function (v) { selectFrame(v - 1); }, "Scroll through the frames (9 tilt directions in star mode, n planes in sweep mode); disabled while continuous cine plays")
      ]);
      /* image section */
      var im1 = slider("Gain", -25, 25, 1, "gain", function (v) { return (v > 0 ? "+" : "") + v + " dB"; }, function (v) { S.gain = v; repaintAll(); }, "Overall gain");
      var im2 = slider("TGC far", -15, 15, 1, "tgc", function (v) { return (v > 0 ? "+" : "") + v + " dB"; }, function (v) { S.tgc = v; refresh(); }, "Extra gain at the maximum depth (time-gain compensation)");
      var im3 = slider("Focus", 0.5, 15, 0.5, "focus", function (v) { return v.toFixed(1) + " cm"; }, function (v) { S.focusCm = v; refresh(); }, "Transmit focus depth");
      var im4 = slider("Dyn. range", 30, 90, 5, "dr", function (v) { return v + " dB"; }, function (v) { S.dr = v; repaintAll(); }, "Display dynamic range");
      ui.togs = {};
      function tog(key, text, title) { return (ui.togs[key] = btn(text, title, function () { S[key] = !S[key]; syncUi(); if (key === "hidden" || key === "speckle" || key === "textures" || key === "reverb" || key === "noise") refresh(true); if (key === "fibres3d") updateOverlay(); })); }
      var im5 = el("div", {class: "us-row"}, [tog("speckle", "speckle", "Synthetic seeded speckle (clearly synthetic; off = smooth tissue levels)"), tog("textures", "muscle / tendon texture", "Documented class textures: muscle septa, tendon fibrils and anisotropy"),
        tog("reverb", "reverberation", "A-line repeats behind air / lung"), tog("noise", "system noise", "Synthetic electronic noise floor (default off)"),
        tog("fibres3d", "fibre lines (3D)", "Q289: faint fibre lines (pennation from the cited architecture table, rule-based layout in the mesh) and documented septa / aponeuroses as thin sheets, for the muscles the selected image cuts"),
        tog("thickness", "tissue thickness", "Q267: opt-in, off by default -- a live readout of the contiguous tissue band under the cursor/cross-hair, measured from this tool's own per-pixel tissue classification (no reference range shown: not citable from this project's own sources). A separate toggle from the Q256 source-reliability dots in the main Parts panel.")]);
      var mo1 = el("div", {class: "us-row"}, [tog("hidden", "hidden structures", "Leave out the structures hidden in the 3D view (virtual dissection; skin always stays). Default: the whole body is imaged, as in a real patient."),
        btn("reset", "Back to defaults (probe stays)", function () { resetDefaults(); })]);
      ui.status = el("div", {class: "us-status", text: ""});
      function sec(name, kids) { var d = el("div", {class: "sec", "data-sec": name}, kids); ui.secs[name] = d; return d; }
      ui.secs = {};
      ui.sweepOnly = ui.sweepBox; ui.starOnly = ui.starBox;
      [mrow, sec("probe", [r1, r2, r3, rPreset, r4, rAB, r5]), sec("mode", [ui.starBox, ui.sweepBox, ui.playBox]), sec("image", [im1, im2, im3, im4, im5]), sec("more", [mo1]), ui.status].forEach(function (x) { ctl.appendChild(x); });
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
      /* Q267 (5) */
      if (ui.abBtn) {
        ui.abBtn.setAttribute("aria-pressed", String(S.ab));
        ui.slotABtn.setAttribute("aria-pressed", String(S.placeSlot === "A")); ui.slotBBtn.setAttribute("aria-pressed", String(S.placeSlot === "B"));
        ui.slotABtn.disabled = ui.slotBBtn.disabled = ui.mirrorBtn.disabled = !S.ab;
        if (ui.playBox) ui.playBox.style.display = S.ab ? "none" : "";    // cine / matrix-single don't apply to a fixed 2-up compare
      }
      /* Q267 (6) */
      if (ui.togs.thickness) ui.togs.thickness.setAttribute("aria-pressed", String(S.thickness));
      if (!S.thickness && ui.thick) ui.thick.hidden = true;
    }
    function setMode(m) { S.mode = m; S.sel = 0; setCine(false); axisCache = {}; syncUi(); updateLayoutUi(); relayoutViews(); frames = []; refresh(true); }
    function mirrorPoint(P) { var bb = geo.bodyBox, cx = (bb.lo[0] + bb.hi[0]) / 2; return [2 * cx - P[0], P[1], P[2]]; }
    function mirrorBtoA() {                                              // Q267 (5): B <- A's point reflected across the body midline (x), re-seated on the real skin there
      if (!S.P) { setStatus("Place A first."); return; }
      var dd = seatMirrorB();                                            // Q273
      if (dd == null) { setStatus("No skin found near the mirrored point; move B manually."); return; }
      setStatus(dd > 5 ? "B mirrored to the opposite side (snapped " + dd.toFixed(0) + " mm to the nearest skin)." : "B mirrored to the opposite side."); syncUi(); refresh(true);
    }
    function setAb(on) {                                                 // Q267 (5): side-by-side A/B compare -- two independent placements, every other control (depth/freq/gain/rotation/tilt/direction) shared
      on = !!on; if (on === S.ab) return;
      S.ab = on;
      if (on) {
        if (S.mode !== "sweep") S.mode = "sweep";                        // the sweep box carries both the Tilt AND Direction sliders this mode shares with both slots
        setCine(false);
        if (!S.P2 && S.P) {
          S.abSnapMm = null;
          if (seatMirrorB() == null) { S.P2 = S.P.slice(); S.N2 = S.N.slice(); }   // Q273 seat (nearest skin to the mirror image, outward by the finding ray); no skin at all: degrade to two adjustable probes at the same start point
        }
        S.placeSlot = "A"; S.sel = 0;
      }
      syncUi(); relayoutViews(); frames = []; refresh(true);
    }
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
        if (!S.motion) { contState.pos = S.mode === "star" ? ((frames[S.sel] && frames[S.sel].spec && frames[S.sel].spec.dir) || 0) : 0; contState.dir = 1; }
        contState.lastT = 0; contState.measMs = 0; contState.fpsActual = 0; contState.active = true; contState.raf = reqFrame(contTick);
        if (S.motion) ensureMotion();                                          // Q289: (re)build the motion path if needed, resume or restart the run
      } else if (S.cine) {
        timers.cine = setInterval(function () { if (!frames.length) return; var nF = S.mode === "star" ? 9 : S.n; S.sel = (S.sel + 1) % nF; relayoutViews(); syncUi(); updateOverlay(); }, 1000 / S.fps);
      }
      updateContReadout(); syncUi(); syncMotionUi(); if (!S.cine && S.motion && frames.length) updateOverlay();   // Q289: the paced 3-D overlay catches up on pause
    }
    function modeHe() { var b = document.body.classList; return b.contains("mode-us") || b.contains("mode-cmp"); }   // Q273: inside a workspace mode the image's UI labels are Hebrew (the watermark, scale and orientation letters are not translated)
    function setStatus(t) {
      if (!ui.status) return;
      if (t) ui.status.textContent = t;
      else { var p = perf.last; ui.status.textContent = p ? p.n + " frame" + (p.n > 1 ? "s" : "") + " in " + p.ms + " ms (" + p.per.join("/") + " ms each) · " + (frames[S.sel] && frames[S.sel].sim ? (frames[S.sel].sim.contact ? "skin contact ok" : "NO skin contact: move the probe onto the body") : "") : ""; }
    }

    /* ---------- views ---------- */
    var STAR_CELL = {0: [2, 3], 1: [1, 3], 2: [1, 2], 3: [1, 1], 4: [2, 1], 5: [3, 1], 6: [3, 2], 7: [3, 3]};          // dir index -> [row, col]
    function ensureViews(specs) {
      var want = specs.length;
      if (views.length === want && views.mode === S.mode && views.ab === S.ab) return relayoutViews();
      views.forEach(function (v) { if (v.wrap.parentNode) v.wrap.parentNode.removeChild(v.wrap); });
      views = []; views.mode = S.mode; views.ab = S.ab;
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
      if (S.ab) {                                                        // Q267 (5): a fixed 2-up grid, always both slots, never a cine matrix
        vw.className = "us-views"; vw.style.gridTemplateColumns = window.innerWidth >= window.innerHeight ? "1fr 1fr" : ""; vw.style.gridTemplateRows = window.innerWidth >= window.innerHeight ? "1fr" : "1fr 1fr";
        views.forEach(function (v) { v.wrap.style.gridRow = ""; v.wrap.style.gridColumn = ""; v.wrap.style.display = ""; });
      } else if (S.mode === "star" && S.view !== "single") {                         // Q253: star mode can now also show one big cine-able frame (S.view === "single")
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
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, cw, ch); try { ctx.direction = "ltr"; } catch (eD) {}   // Q273: a Hebrew word followed by numbers must not be reordered by an RTL host
      var box = boxOf(v, fr, cw, ch); v.box = box;
      v.img.style.left = box.x + "px"; v.img.style.top = box.y + "px"; v.img.style.width = box.w + "px"; v.img.style.height = box.h + "px";
      var tiny = box.w < 200, sim = fr.sim, pl = fr.plan, g = fr.geom, sc = box.s / pl.px;       // css px per mm
      function X(x) { return box.x + (x - pl.xo0) * sc; }
      function Y(y) { return box.y + (y - pl.yo0) * sc; }
      ctx.font = "600 " + (tiny ? 9.5 : 11.5) + "px system-ui,sans-serif"; ctx.textBaseline = "middle";
      function txt(s, x, y, al, col) { ctx.textAlign = al; ctx.fillStyle = "rgba(0,0,0,.7)"; ctx.fillText(s, x + 1, y + 1); ctx.fillStyle = col || "#e8eef5"; ctx.fillText(s, x, y); }
      function txtSeq(parts, x, y, col) { parts.forEach(function (pt) { txt(pt, x, y, "left", col); x += ctx.measureText(pt).width; }); }   // Q273: segments drawn left-to-right one by one, so two Hebrew words with numbers between them never get bidi-reordered
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
      var he = modeHe();                                                   // Q273: the UI labels drawn into the image follow the workspace mode's language
      var iso = function (x) { return he ? "\u2066" + x + "\u2069" : x; };   // numbers after a Hebrew word: an isolated LTR run (LRI...PDI), so no bidi reordering of signs / degree marks
      var t1 = (tiny ? "" : g.type + " " + g.w + " mm \u00B7 ") + S.freq + " MHz \u00B7 " + S.depthCm + " cm" + (tiny ? "" : " \u00B7 " + (he ? "\u05D4\u05D2\u05D1\u05E8 " : "gain ") + iso((S.gain >= 0 ? "+" : "") + S.gain + " dB"));
      if (fs.on) { /* Q289: clean full-screen view -- no header lines */ } else if (box.h > 150) { txt(t1, box.x + 6, box.y + 10, "left"); txt(fr.spec.label, box.x + 6, box.y + (tiny ? 21 : 24), "left", "#9fd0ff"); }
      else txt(fr.spec.short || fr.spec.label, box.x + 4, box.y + 8, "left", "#9fd0ff");
      if (!tiny) {
        var tiltS = (Math.round(fr.pf.tilt * 10) / 10) + "\u00B0", normS = fr.pf.N.map(function (x) { return x.toFixed(2); }).join(",");
        if (fs.on) { /* Q289 */ } else if (he) txtSeq(["\u05D4\u05D8\u05D9\u05D4 ", tiltS, " \u00B7 ", "\u05E0\u05D5\u05E8\u05DE\u05DC ", normS], box.x + 6, box.y + 38, "#b8c4d2");
        else txt("tilt " + tiltS + " \u00B7 normal " + normS, box.x + 6, box.y + 38, "left", "#b8c4d2");
        if (!fs.on && (S.speckle || S.noise || S.textures)) txt((he ? "\u200E\u05E1\u05D9\u05E0\u05EA\u05D8\u05D9: " : "synthetic: ") + [S.speckle ? (he ? "\u05E1\u05E4\u05E7\u05DC" : "speckle") : "", S.textures ? (he ? "\u05DE\u05E8\u05E7\u05DE\u05D9\u05DD" : "textures") : "", S.noise ? (he ? "\u05E8\u05E2\u05E9" : "noise") : ""].filter(Boolean).join(", "), box.x + 6, box.y + 52, "left", "#ff9d8a");
        if (!sim.contact) txt(he ? "\u05D0\u05D9\u05DF \u05DE\u05D2\u05E2 \u05E2\u05DD \u05D4\u05E2\u05D5\u05E8" : "NO SKIN CONTACT", box.x + box.w / 2, box.y + box.h / 2, "center", "#ff6a5a");
        if (v.idx === S.sel) {
          var mm = US && LIB.probeMismatch(S.freq, S.depthCm, US.global && US.global.tgc_alpha_ref_db_cm_mhz);
          if (mm) wrapTxt((he ? "\u05D0\u05D9-\u05D4\u05EA\u05D0\u05DE\u05D4 \u05DE\u05EA\u05DE\u05E8/\u05E2\u05D5\u05DE\u05E7: " : "PROBE/DEPTH MISMATCH: ") + mm.text, box.x + 6, box.y + 66, box.w - 12, "#ffb13c");
        }
      }
      /* Q289: the honesty watermark stays in the clean full-screen view too -- small, but always inside the image (a full-screen CINE is
         exactly what gets screen-recorded and passed on without the page around it) */
      if (fs.on) { ctx.font = "600 " + (box.w < 300 ? 9 : 10) + "px system-ui,sans-serif"; ctx.globalAlpha = 0.8; txt(FS_MARK, box.x + 6, box.y + 10, "left", "#ff9d8a"); ctx.globalAlpha = 1; }
      var bad = BADGE.toUpperCase(), bw2 = ctx.measureText(bad).width;
      if (fs.on) { /* the watermark above replaces the badge */ } else if (bw2 + 12 <= box.w) txt(bad, box.x + box.w - 6, box.y + box.h - 8, "right", "#ff9d8a");
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
      ui.read.textContent = cls + " | " + name + " | depth " + (y / 10).toFixed(1) + " cm, lateral " + x.toFixed(1) + " mm | echo " + (db > -150 ? (db >= 0 ? "+" : "") + db.toFixed(0) + " dB re liver" : "none") + " | atlas x " + P[0].toFixed(0) + " y " + P[1].toFixed(0) + " z " + P[2].toFixed(0) + " mm" + archLabel(sidv);   // Q289
      /* Q267 (6): live tissue-thickness readout, opt-in -- the contiguous run of the SAME per-pixel tissue-class id
         (fr.lab, the exact grid the simulation above and the imaging kernel already compute, nothing new) through the
         hovered lateral column, converted to mm by the raster's own px size. No "typical range" is shown: this project
         has no cited reference band for in-plane ultrasound tissue thickness to compare it against. */
      if (ui.thick) {
        if (S.thickness && rx >= 0 && rY >= 0 && rx < pl.W && rY < pl.H && fr.lab) {
          var labId = fr.lab[rY * pl.W + rx], top = rY, bot = rY;
          while (top > 0 && fr.lab[(top - 1) * pl.W + rx] === labId) top--;
          while (bot < pl.H - 1 && fr.lab[(bot + 1) * pl.W + rx] === labId) bot++;
          var mmThick = (bot - top + 1) * pl.px;
          ui.thick.textContent = "Tissue thickness at cursor: " + C.T.classes[labId].label + " ≈ " + mmThick.toFixed(1) + " mm (live measurement; no reference range shown)";
          ui.thick.hidden = false;
        } else ui.thick.hidden = true;
      }
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
        "CINE motion types (Q289, continuous re-slicing as above): 'long' slides the probe along the body part -- on a limb the axis and length of the nearest long bone (its own PCA axis and extent), on the trunk the cranio-caudal axis -- re-seated on the real skin at every sample; 'circ' goes round the part at the probe's level (rays from the section centre to the part's own skin); 'rot' turns the probe 180° about its own axis; 'tilt' fans it heel <-> toe by ± the Tilt angle; 'track' follows a chosen structure along its centreline (per-5-mm-slice centroids of its own mesh along its principal axis -- a course that doubles back on that axis is not represented), the probe on the skin straight above it. The face stays at 90° to the smoothed skin normal throughout. One way or back and forth, optionally looped; the full-screen view shows the part in 3-D beside the image, with the scan direction as an arrow.",
        "Muscle fibres (Q289): inside a muscle the perimysium texture now follows the LOCAL fibre direction -- the mesh's own long axis tilted by the cited pennation angle (unipennate: toward the thickness axis; bipennate: converging on a central sheet; multipennate: alternating between sheets), so a longitudinal plane shows the pennation pattern and a transverse plane cross-cut fascicles, live during CINE. Documented septa / aponeuroses are hyperechoic sheets. Layout inside the mesh is rule-based; see 'Muscle fibres and septa' below.",
        "Model artefacts handled: an air band thinner than " + US.global.air_pocket_fill_mm + " mm along a beam that tissue follows again is treated as fat (the Z pages' skin is a set of overlapping patches; the slice kernel then labels gaps between skin layers as air); thin fascia / septa meshes are drawn one pixel wide and can show as bright lines with a stair-step on oblique planes.",
        "Synthetic parts: speckle (seeded value noise with Rayleigh statistics, attached to the sweep volume), muscle septa / tendon fibril textures, optional system noise: all labelled on the image and switchable off. Not modelled: " + US.artefacts.not_modelled.join("; ") + "."];
      var ul = el("ul"); how.forEach(function (t) { ul.appendChild(el("li", {text: t})); }); box.appendChild(ul);
      box.appendChild(el("h3", {text: "Honest limits"}));
      var ul2 = el("ul"); US.honesty.forEach(function (t) { ul2.appendChild(el("li", {text: t})); }); box.appendChild(ul2);
      if (US.architecture) {                                                 // Q289: fibre direction + documented septa
        var AR = US.architecture;
        box.appendChild(el("h3", {text: "Muscle fibres and septa (Q289) -- RULE-BASED layout, cited angles"}));
        var ul3 = el("ul"); AR.honesty.forEach(function (t) { ul3.appendChild(el("li", {text: t})); });
        Object.keys(AR.muscles).filter(function (k) { return AR.muscles[k].septa && AR.muscles[k].septa.length; }).forEach(function (k) {
          AR.muscles[k].septa.forEach(function (sp) { ul3.appendChild(el("li", {text: k.replace(/_/g, " ") + ": " + sp.name + " -- " + sp.rule + " [" + sp.refs.map(function (r) { var x = AR.references[r]; return x ? x.cite + " PMID " + x.pmid + " doi:" + x.doi : r; }).join("; ") + "]"})); });
        });
        ul3.appendChild(el("li", {text: Object.keys(AR.muscles).length + " muscles carry a cited pennation (the per-muscle source line is shown with the hover readout); every other muscle shows its generic line of action."}));
        box.appendChild(ul3);
      }
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
        if (fs.on) setFs(false);                                           // Q289
        S.open = false; setCine(false); S.placing = false; S.pick3d = false; gen++; applyLayout(); clearOverlay();
        if (ui.btn) ui.btn.setAttribute("aria-pressed", "false");
      }
    }
    sh.addClickHandler(onPlaceClick);
    addButton();
    acousticTable().then(function () {}, function () {}); setDiag();           // the cheap table now (state in the button tooltip); the geometry only when the panel opens
    var poll = setInterval(function () {                                       // keep the overlay's tube radius in step with the camera distance
      /* Q267 (9): the generic, page-level layout toggle sets a body class, "lay-compare", never naming this
         (private) tool -- watching for it here (not the other way around) keeps the public template's own layout
         code tool-agnostic, per this project's existing architecture (clinical/* is the only place that may name
         itself). Entering AB here only when ultrasound is ALSO the open tool (the body's own "nmsk-us" class). */
      if (document.body.classList.contains("lay-compare") && document.body.classList.contains("nmsk-us") && S.open && !S.ab) setAb(true);
      if (!S.open || !frames.length) return;
      var vw; try { vw = api.view(); } catch (e) { return; }
      var d = Math.round(Math.hypot(vw.eye[0] - vw.target[0], vw.eye[1] - vw.target[1], vw.eye[2] - vw.target[2]) / 120);
      if (String(d) !== lastOverlayKey) { lastOverlayKey = String(d); updateOverlay(); }
    }, 400);
    /* ---------- Q272: the "US אבחנתי" WORKSPACE MODE -- a re-skin of this tool (preset, CINE, A/B, thickness), hosted by the
       page's generic mode layer (viewer/modes/, window.NMSKModes). The B-mode panel (#us-root) itself is docked into the hero slot,
       the 3-D canvas into the thumbnail slot; every control below calls the same functions this tool's own panel calls. ---------- */
    var usModeCss = [
      "body.mode-us #us-root .us-head,body.mode-us #us-root #us-div,body.mode-us #us-root .us-diag,body.mode-us #us-root .us-hint,body.mode-us #us-root .us-info,body.mode-us #us-root>.us-status,body.mode-us #us-root .us-read{display:none!important}",
      "body.mode-us #us-root{border:0!important;background:#0B0F14!important}",
      "body.mode-us #us-root .us-thick{position:absolute;left:14px;top:12px;z-index:5;height:30px;padding:0 12px;border-radius:999px;background:rgba(43,108,176,.9);color:#fff;border:0;font:700 13px Heebo,system-ui,sans-serif;display:flex;align-items:center;direction:rtl}",
      "body.mode-us #us-root .us-thick[hidden]{display:none}",
      "body.mode-us #us-root .us-wizard{direction:rtl;font-family:Heebo,system-ui,sans-serif}",
      "body.mode-us #us-root:not(.ctl-off) .us-ctl{max-height:55%}",
      "body.mode-us .mm-note{font:12px Heebo,system-ui,sans-serif;color:#4a5568;direction:rtl;margin-inline-start:auto;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      "body.mode-us .mm-note:empty{display:none}",
      ".mm-toast{position:fixed;left:50%;bottom:84px;transform:translateX(-50%);z-index:120;background:#1a202c;color:#fff;border-radius:10px;padding:9px 16px;font:600 13px Heebo,system-ui,sans-serif;direction:rtl;box-shadow:0 6px 24px rgba(0,0,0,.25)}",
      ".mm-toast[hidden]{display:none}",
      ".mm-mopop{margin-top:8px;padding:8px 10px;background:#fff;border:1px solid #E2E8F0;border-radius:12px}",
      ".mm-mopop[hidden]{display:none}",
      ".mm-mopop .us-mo button{background:#fff;border:1px solid #CBD5E0;color:#1A202C;cursor:pointer}",
      ".mm-mopop .us-mo button[aria-pressed=true]{background:#2B6CB0;border-color:#2B6CB0;color:#fff}",
      ".mm-mopop .us-mo button:disabled{opacity:.45}",
      ".mm-mopop .us-mo output,.mm-mopop .us-mo label{color:#4A5568}",
      "body.mode-cmp #us-root .us-head,body.mode-cmp #us-root #us-div,body.mode-cmp #us-root .us-ctl,body.mode-cmp #us-root .us-diag,body.mode-cmp #us-root .us-hint,body.mode-cmp #us-root .us-info,body.mode-cmp #us-root>.us-status,body.mode-cmp #us-root .us-wizard,body.mode-cmp #us-root .us-read{display:none!important}",
      "body.mode-cmp #us-root{border:0!important}"
    ].join("\n");
    function usMode() {
      var ctx = null, ui2 = {}, prev = null, FREQS = (US && US.freq_presets_mhz) || [3.5, 5, 7.5, 12];
      function h(tag, a, k) { return ctx.el(tag, a, k); }
      function svg(d, w) { var s = document.createElementNS("http://www.w3.org/2000/svg", "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("width", w || 18); s.setAttribute("height", w || 18); s.setAttribute("aria-hidden", "true"); s.innerHTML = d; return s; }
      function playIcon() { return svg('<path d="M7 5l12 7-12 7z" fill="currentColor"/>'); }
      function pauseIcon() { return svg('<path d="M7 5h4v14H7zM13 5h4v14h-4z" fill="currentColor"/>'); }
      function chipSet(container, mobile) {
        PRESETS.forEach(function (d) {
          var label = mobile ? {tear: "קרע שריר", entrap: "entrapment", tendon: "גיד / רצועה", joint: "מפרק"}[d.key] : {tear: "קרע שריר", entrap: "entrapment עצבי", tendon: "גיד / רצועה", joint: "מפרק / בורסה"}[d.key];
          var b = h("button", {type: "button", class: (mobile ? "mm-tog" : "mb-tog") + " mi", "data-preset": d.key, "aria-pressed": "false", text: label, onclick: function () { choosePreset(d.key); }});
          container.appendChild(b);
        });
      }
      function choosePreset(key) {
        if (!geo) { setStatus("Loading ..."); loadTable().then(function () { choosePreset(key); }); return; }
        applyPreset(key);
        /* as automatic as possible: when the page's selected structure is one of the wizard's real candidates, take it */
        if (ui.wizard && !ui.wizard.hidden) {
          var sid = ctx.selectedId(), c = sid ? pendingCands.filter(function (x) { return x.sid === sid; })[0] : null;
          if (c) { placeAtStructure(c.sid, "A"); setStatus("Centred near " + c.name + "."); hideWizard(); refresh(true); setCine(true); }
        }
        refreshUi();
      }
      function toast(msg, ms) {
        if (!ui2.toast) { ui2.toast = h("div", {class: "mm-toast", role: "status"}); document.body.appendChild(ui2.toast); }
        ui2.toast.textContent = msg; ui2.toast.hidden = false; clearTimeout(ui2.toastT); ui2.toastT = setTimeout(function () { ui2.toast.hidden = true; }, ms || 4000);
      }
      function embedded() { try { return window.self !== window.top; } catch (e) { return true; } }
      function savePng() {                                                 // Q273: the active frame as a PNG through canvas.toBlob + a download anchor (a normal tab saves it;
        var v = views[S.sel] || views[0], fr = frames[S.sel] || frames[0];   // inside the artifact viewer's frame the platform may block downloads, so the user is told instead of nothing happening)
        if (!v || !v.img || !fr || !fr.sim) { toast("\u05D0\u05D9\u05DF \u05E2\u05D3\u05D9\u05D9\u05DF \u05EA\u05DE\u05D5\u05E0\u05D4 \u05DC\u05E9\u05DE\u05D9\u05E8\u05D4"); return; }
        try {
          var r = v.wrap.getBoundingClientRect(), sc = window.devicePixelRatio || 1, out = document.createElement("canvas");
          out.width = Math.max(256, Math.round(r.width * sc)); out.height = Math.max(256, Math.round(r.height * sc));
          var c2 = out.getContext("2d"); c2.fillStyle = "#000"; c2.fillRect(0, 0, out.width, out.height);
          if (v.box) c2.drawImage(v.img, v.box.x * sc, v.box.y * sc, v.box.w * sc, v.box.h * sc); else c2.drawImage(v.img, 0, 0, out.width, out.height);
          if (v.ann) c2.drawImage(v.ann, 0, 0, out.width, out.height);
          out.toBlob(function (b) {
            if (!b) { toast("\u05D4\u05E9\u05DE\u05D9\u05E8\u05D4 \u05E0\u05DB\u05E9\u05DC\u05D4"); return; }
            var u = URL.createObjectURL(b), a = document.createElement("a"); a.href = u; a.download = "nmsk-us-simulation-" + (S.sel + 1) + ".png"; document.body.appendChild(a); a.click(); a.remove();
            setTimeout(function () { URL.revokeObjectURL(u); }, 3000);
            /* a sandboxed frame without allow-downloads drops the click silently (no event reaches the page): say so instead of nothing */
            toast(embedded() ? "\u05D0\u05DD \u05D4\u05EA\u05DE\u05D5\u05E0\u05D4 \u05DC\u05D0 \u05E0\u05E9\u05DE\u05E8\u05D4 \u2013 \u05DC\u05D0 \u05D6\u05DE\u05D9\u05DF \u05D1\u05EA\u05E6\u05D5\u05D2\u05D4 \u05D6\u05D5; \u05E4\u05EA\u05D7\u05D5 \u05D0\u05EA \u05D4\u05E2\u05DE\u05D5\u05D3 \u05D1\u05DC\u05E9\u05D5\u05E0\u05D9\u05EA \u05E0\u05E4\u05E8\u05D3\u05EA" : "\u05D4\u05EA\u05DE\u05D5\u05E0\u05D4 \u05E0\u05E9\u05DE\u05E8\u05D4 (PNG)", embedded() ? 6000 : 3000);
          });
        } catch (e) { toast("\u05D4\u05E9\u05DE\u05D9\u05E8\u05D4 \u05E0\u05DB\u05E9\u05DC\u05D4: " + e.message); }
      }
      function build(c) {
        ctx = c;
        if (!document.getElementById("us-mode-css")) { var st = document.createElement("style"); st.id = "us-mode-css"; st.textContent = usModeCss; document.head.appendChild(st); }
        c.bar.chips.appendChild(h("span", {class: "mb-dim", text: "חשד:"}));
        chipSet(c.bar.chips, false);
        ui2.mobText = h("div", {class: "mb-text mi", text: ""}); c.bar.chips.appendChild(ui2.mobText);
        c.bar.end.insertBefore(h("button", {type: "button", class: "mb-btn mi", text: "שמור תמונה", onclick: savePng}), c.bar.end.firstChild);
        /* main: hero + cine bar | side column */
        ui2.heroSlot = h("div", {class: "mslot"});
        ui2.chip = h("div", {class: "mm-chip", text: ""});
        ui2.thumbM = h("div", {class: "mm-thumb-m"}, [(ui2.thumbMSlot = h("div", {class: "mslot", style: "position:absolute;inset:0"}))]);
        var hero = h("div", {class: "mm-hero"}, [ui2.heroSlot, ui2.chip, h("div", {class: "mm-badge", text: "סימולציה מהמשים – לא אולטרסאונד"}), ui2.thumbM]);
        ui2.play = h("button", {type: "button", class: "mm-play", "aria-label": "הפעל/עצור", onclick: function () { setCine(!S.cine); refreshUi(); }}, [playIcon()]);
        ui2.scrub = h("input", {type: "range", min: "0", max: "8", step: "1", value: "0", "aria-label": "CINE", oninput: function () { G.NMSKUltrasound.set({sel: +this.value}); refreshUi(); }});
        ui2.frame = h("div", {class: "lb fr", text: ""});
        ui2.cont = h("button", {type: "button", class: "mm-tog", "aria-pressed": "false", text: "רציף", onclick: function () { if (S.cineMode !== "continuous") ui.cineModeBtn.click(); refreshUi(); }});
        ui2.step = h("button", {type: "button", class: "mm-tog m-hide", "aria-pressed": "false", text: "צעדים", onclick: function () { if (S.cineMode === "continuous") ui.cineModeBtn.click(); refreshUi(); }});
        ui2.thick = h("button", {type: "button", class: "mm-tog m-hide", "aria-pressed": "false", text: "עובי רקמה: כבוי", onclick: function () { if (ui.togs && ui.togs.thickness) ui.togs.thickness.click(); refreshUi(); }});
        ui2.note = h("div", {class: "mm-note", text: ""});
        /* Q289: CINE motion types -- one tap opens the short list, one tap on a type plays it; ⛶ = the clean split full screen */
        ui2.moPop = h("div", {class: "mm-mopop mi", hidden: true}, [motionSheet({open: false})]);
        ui2.moBtn = h("button", {type: "button", class: "mm-tog", "aria-expanded": "false", "aria-pressed": "false", text: "תנועה ▾", onclick: function () { ui2.moPop.hidden = !ui2.moPop.hidden; ui2.moBtn.setAttribute("aria-expanded", String(!ui2.moPop.hidden)); }});
        ui2.fsBtn = h("button", {type: "button", class: "mm-tog", title: "מסך מלא: תלת-ממד | אולטרסאונד (יציאה: ✕ או Esc)", "aria-label": "מסך מלא", text: "⛶", onclick: function () { setFs(true); }});
        var cine = h("div", {class: "mm-bar mi"}, [ui2.play, h("label", {class: "lb", text: "CINE"}), ui2.moBtn, ui2.fsBtn, ui2.scrub, ui2.frame, ui2.cont, ui2.step, ui2.thick, ui2.note]);
        ui2.chipsM = h("div", {class: "mm-chips-m"}); chipSet(ui2.chipsM, true);
        var col = h("div", {class: "mm-col"}, [hero, cine, ui2.moPop, ui2.chipsM]);
        /* side column */
        ui2.thumbSlot = h("div", {class: "mslot"});
        var thumb = h("div", {class: "mm-thumb"}, [ui2.thumbSlot, h("div", {class: "mm-cap mi", text: "הקש על העור כדי להזיז את המתמר"})]);
        function sl(label, min, max, step, fmtv, get, set) {
          var out = h("span", {text: ""}), inp = h("input", {type: "range", min: String(min), max: String(max), step: String(step), "aria-label": label, oninput: function () { set(+this.value); refreshUi(); }});
          var box = h("div", {class: "mm-sl"}, [h("div", {class: "hd"}, [h("label", {}, [h("b", {text: label})]), out]), inp]);
          box._sync = function () { var v = get(); inp.value = String(v); out.textContent = fmtv(v); };
          return box;
        }
        ui2.depth = sl("עומק", 2, 15, 0.5, function (v) { return v.toFixed(1) + " ס\"מ"; }, function () { return S.depthCm; }, function (v) { S.depthCm = v; if (S.focusCm > v) S.focusCm = v * 0.6; syncUi(); refresh(); });
        ui2.freq = sl("תדר", 0, FREQS.length - 1, 1, function (i) { return FREQS[i] + " MHz"; }, function () { var i = FREQS.indexOf(S.freq); return i < 0 ? FREQS.length - 1 : i; }, function (i) { S.freq = FREQS[i]; syncUi(); refresh(); });
        ui2.gain = sl("הגבר", -20, 20, 1, function (v) { return (v >= 0 ? "+" : "") + v + " dB"; }, function () { return S.gain; }, function (v) { S.gain = v; syncUi(); refresh(true); });
        ui2.gain.classList.add("m-hide");
        ui2.orL = h("button", {type: "button", class: "mm-sec", text: "אורכי", onclick: function () { ui.orLong.click(); refreshUi(); }});
        ui2.orT = h("button", {type: "button", class: "mm-sec", text: "רוחבי", onclick: function () { ui.orTrans.click(); refreshUi(); }});
        ui2.rot = h("button", {type: "button", class: "mm-sec", text: "סובב", onclick: function () { S.rot = (S.rot + 15) % 360; syncUi(); refresh(); refreshUi(); }});
        var orRow = h("div", {class: "mc-row m-hide"}, [ui2.orL, ui2.orT, ui2.rot]);
        ui2.ab = h("button", {type: "button", class: "mm-primary", "aria-pressed": "false", text: "השווה לצד הנגדי (A/B)", onclick: function () { setAb(!S.ab); refreshUi(); }});
        ui2.adv = h("button", {type: "button", class: "mm-sec", "aria-pressed": "false", text: "הגדרות מתקדמות (מתמר, סריקה, ניגודיות)…", onclick: function () { ui.ctlBtn.click(); refreshUi(); }});
        var row2 = h("div", {class: "mm-row2"}, [ui2.ab, ui2.adv]);
        var card = h("div", {class: "mm-card mi"}, [ui2.depth, ui2.freq, ui2.gain, orRow, row2]);
        var side = h("div", {class: "mm-side"}, [thumb, card]);
        c.main.appendChild(h("div", {class: "mm-fill"}, [col, side]));
        c.dock(root, ui2.heroSlot, 81);
        c.modelDock([ui2.thumbSlot, ui2.thumbMSlot], 85);   // above the docked B-mode panel: on the phone the thumbnail sits inside the hero
        modeRedock = function () { c.dock(root, ui2.heroSlot, 81); c.modelDock([ui2.thumbSlot, ui2.thumbMSlot], 85); };   // Q289: back from the full-screen CINE
        modeRefresh = refreshUi; modeToast = function (m) { toast(m); };
      }
      function refreshUi() {
        if (!ctx) return;
        var n = Math.max(1, frames.length), cont = S.cineMode === "continuous";
        ui2.play.innerHTML = ""; ui2.play.appendChild(S.cine ? pauseIcon() : playIcon());
        ui2.scrub.max = String(n - 1); ui2.scrub.value = String(Math.min(S.sel, n - 1)); ui2.scrub.disabled = !!(S.cine && cont);
        ui2.frame.textContent = "פריים " + (Math.min(S.sel, n - 1) + 1) + " / " + n;
        ui2.cont.setAttribute("aria-pressed", String(cont)); ui2.step.setAttribute("aria-pressed", String(!cont));
        ui2.thick.setAttribute("aria-pressed", String(!!S.thickness)); ui2.thick.textContent = "עובי רקמה: " + (S.thickness ? "פועל" : "כבוי");
        var mo = MOTIONS.filter(function (m) { return m[0] === S.motion; })[0];   // Q289
        ui2.moBtn.setAttribute("aria-pressed", String(!!mo)); ui2.moBtn.textContent = mo ? "תנועה: " + mo[1] + " ▾" : "תנועה ▾";
        var pr = {linear: "Linear", convex: "Convex", sector: "Sector"}[S.probe] || S.probe;
        ui2.chip.innerHTML = ""; ui2.chip.appendChild(document.createTextNode(pr + " " + S.freq + " MHz · " + S.depthCm + " ס\"מ · ")); ui2.chip.appendChild(h("b", {text: cont ? "רציף" : "צעדים"}));
        var pd = PRESETS.filter(function (d) { return d.key === S.preset; })[0];
        ui2.mobText.textContent = pd ? pd.label : "";
        Array.prototype.forEach.call(ctx.shell.querySelectorAll("[data-preset]"), function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-preset") === S.preset)); });
        [ui2.depth, ui2.freq, ui2.gain].forEach(function (b) { b._sync(); });
        ui2.orL.setAttribute("aria-pressed", String(S.refKey === "long")); ui2.orT.setAttribute("aria-pressed", String(S.refKey === "trans"));
        ui2.ab.setAttribute("aria-pressed", String(!!S.ab)); ui2.ab.textContent = S.ab ? "A/B פעיל – חזרה לתצוגה אחת" : "השווה לצד הנגדי (A/B)";
        ui2.note.textContent = S.ab && S.abSnapMm != null && S.abSnapMm > 5 ? "B הוצמד לעור הקרוב בצד הנגדי (" + Math.round(S.abSnapMm) + " מ\"מ מנקודת המראה)" : "";   // Q273
        var advOpen = root && !root.classList.contains("ctl-off");
        ui2.adv.setAttribute("aria-pressed", String(advOpen)); ui2.adv.textContent = advOpen ? "סגור הגדרות מתקדמות" : "הגדרות מתקדמות (מתמר, סריקה, ניגודיות)…";
      }
      function enter(c) {
        modeCtx = c;                                                     // Q289: the full-screen CINE docks through the mode while it is on
        prev = {open: S.open, lay: S.lay, tab: S.tab, placing: S.placing, ctlOff: !!(root && root.classList.contains("ctl-off"))};
        if (!S.open) setOpen(true);
        S.lay = "tab"; S.tab = "image"; applyLayout(); updateLayoutUi();
        if (root && !root.classList.contains("ctl-off")) ui.ctlBtn.click();
        modeArm = true; S.placing = true; syncUi();
        c.dock(root, ui2.heroSlot, 81);
        refreshUi();
      }
      function exit() {
        if (fs.on) setFs(false); modeCtx = null;                         // Q289
        modeArm = false; S.placing = false;
        if (!prev.open) { setCine(false); setOpen(false); }
        else { if (root && root.classList.contains("ctl-off") !== prev.ctlOff) ui.ctlBtn.click(); }
        S.lay = prev.lay; S.tab = prev.tab; if (S.open) { applyLayout(); updateLayoutUi(); }
        if (ui2.toast) ui2.toast.hidden = true;
        syncUi(); ctx = null;
      }
      return {title: "US אבחנתי", short: "US", build: build, enter: enter, exit: exit, refresh: refreshUi};
    }
    if (G.NMSKModes && G.NMSKModes.register) { try { G.NMSKModes.register("us", usMode()); } catch (eM) { console.error("US mode failed to register:", eM); } }
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
          else if (k === "cine") setCine(p.cine); else if (k === "followSid") { if (p.followSid >= 0) setFollow(p.followSid); else { S.followSid = -1; S.follow = false; S.followName = ""; } } else S[k] = p[k];
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
      overlayItems: function () { var it = overlayItems(); return it ? it.map(function (x) { return [x[0], x[1].count()]; }) : null; },
      /* Q267 test hooks */
      setAb: function (on) { return loadTable().then(function () { setAb(on); return S.ab; }); },
      mirrorB: function () { mirrorBtoA(); },
      setPlaceSlot: function (slot) { S.placeSlot = slot === "B" ? "B" : "A"; syncUi(); },
      applyPreset: function (key) { return loadTable().then(function () { applyPreset(key); return {preset: S.preset, wizard: ui.wizard && !ui.wizard.hidden, status: ui.status.textContent}; }); },
      wizardOptions: function () { return pendingCands.slice(0, 200).map(function (c) { return {sid: c.sid, name: c.name}; }); },
      pickWizard: function (sid) { var c = pendingCands.filter(function (x) { return x.sid === sid; })[0]; if (!c) return false; placeAtStructure(c.sid, "A"); hideWizard(); refresh(true); setCine(true); return true; },
      dismissWizard: function () { hideWizard(); },
      thicknessAt: function (vi) { var v = views[vi == null ? S.sel : vi]; return v && v.hover ? ui.thick.textContent : null; },
      classOf: function (sid) { return classOf(sid); },
      overlayLang: function () { return modeHe() ? "he" : "en"; },  // Q273 test hook: the language of the UI labels drawn into the B-mode image
      /* Q289 test hooks: CINE motion types + the clean full-screen view */
      motion: function (k) { return loadTable().then(function () { chooseMotion(k); return S.motion; }); },
      motionState: function () {
        var m = mPath;
        return {motion: S.motion, building: mBuilding, active: contState.active, cine: S.cine, pos: contState.pos, dir: contState.dir, done: !!(m && m.done), info: mInfo,
          opts: {back: S.mBack, loop: S.mLoop, rev: S.mRev, speed: S.mSpeed, plane: S.mPlane, extAuto: S.extAuto, extCm: S.extCm},
          path: m ? {kind: m.kind, unit: m.unit, total: m.total, n: m.samples.length, skipped: m.skipped || 0, plane: m.plane, win: m.win, sid: m.sid == null ? -1 : m.sid, name: m.name || "",
            region: {kind: m.region.kind, name: m.region.name, len: m.region.len, a: m.region.a}} : null};
      },
      pathSamples: function () { return mPath ? mPath.samples.map(function (q) { return {P: q.P, N: q.N, u: q.u, s: q.s, depth: q.depth == null ? null : q.depth}; }) : null; },
      fs: function (on) { setFs(on); return fs.on; },
      archInfo: function (sid) { var a = archOf(sid); return a ? {key: a.key, kind: a.kind, type: a.row.t, p: a.row.p, sheets: a.sheets.map(function (x) { return {ax: x.ax, off: x.off, s0: x.s0, s1: x.s1, id: x.id}; }), bands: a.bands, la: a.la, lw: a.lw, lt: a.lt, a: a.a, w: a.w, t: a.t, c: a.c, label: archLabel(sid)} : {generic: true, label: archLabel(sid)}; },
      fibreAt: function (sid, p) { var a = archOf(sid); return a ? {f: LIB.fibreAt(a, p[0], p[1], p[2]).slice(), sep: a._sep, band: a._band} : null; },
      imageMuscles: function () { return imageMuscles(frames[S.sel], 6).map(function (q) { return {sid: q, id: geo.recs[q] && geo.recs[q].id, arch: !!archOf(q)}; }); },
      fsState: function () { return {on: fs.on, lay: fs.el ? fs.el.getAttribute("data-lay") : null, idle: document.body.classList.contains("fs-idle"), sheet: !!(fs.sheet && !fs.sheet.hidden)}; }
    };
    return {};
  }

  G.NMSKUltrasoundAddon = {attach: function (api, shared) { return attachUltrasound(api, shared); }, VERSION: VERSION};
})(typeof window !== "undefined" ? window : globalThis);
