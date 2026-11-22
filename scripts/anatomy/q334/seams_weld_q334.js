    /* Q334: NO IMAGINARY LINES BETWEEN THE PIECES OF ONE CONTINUOUS STRUCTURE. The skin comes as ~250 region meshes, each
       a closed slab ~2.7 mm thick (outer surface, inner surface and a side WALL along its border). Two neighbouring regions
       share their outer border vertices exactly, and their walls lie face to face inside the skin. Two things drew a line
       there that is not anatomy: (1) each mesh's vertex normals were averaged over its own faces only, and at the border
       those include the wall, which stands at ~90 degrees to the surface -- the normal bends ~45 degrees and the shading
       breaks along every border; (2) the two walls are drawn too, and with the skin translucent (0.3 by default) every
       border collects extra layers of colour. Fix, at load, per class: the vertices are welded across the pieces of the
       class (positions within WELD_MM), a seam vertex takes the normal of its dominant smooth group of faces over ALL
       pieces (the wall is not part of it), and a wall face that lies face to face with the neighbour's wall is drawn only
       while that neighbour is not drawn (hidden, off, cut away) -- then the region's real boundary shows. Picking, the ID
       and depth passes, the cut face and the pose use the surface as before; the pose takes the welded rest geometry. */
    /* Which pieces are ONE continuous structure (a key per piece; only pieces with the same key are joined): the skin regions
       (not the nail plate, which meets the skin at a real boundary), the cerebral and cerebellar cortex cut into gyri, sulci
       and lobules (closed slabs ~2.4 mm thick, built like the skin), and a fascia's own left and right halves (same name).
       Everything else stays as it is: the other shared borders on these pages are between different structures. */
    var Q334_CORTEX = /gyr|sulc|lobul|pole|cune|operc|insula|uncus/i;
    var Q334_GROUPS = {
      skin:function(o){ return /^nail plate/i.test(o.name || "") ? null : "skin"; },
      cns:function(o){ return Q334_CORTEX.test(o.name || "") ? "cortex" : null; },
      fascia:function(o){ return o.name || null; }
    };
    /* the cortex is drawn opaque (and fascia sheets have no walls): normals and walls only there, no crack closing */
    var Q334_LIGHT = {cns:1, fascia:1};
    var Q334_WELD = 0.03, Q334_COS = 0.6, Q334_WALL = 1.5, Q334_SNAP = 1.5, Q334_TJ = 0.8, Q334_RIM = 1.0, Q334_SLANT = 0.8, Q334_LIE = 0.75, Q334_TWIN = 0.9, q334W = {}, q334Stat = {ms:0, cls:{}};
    (function(){
      var t0 = performance.now();
      Object.keys(Q334_GROUPS).forEach(function(cls){
        var GR = {};
        OBJ.forEach(function(o){ if (o.layer !== cls || !o.idx || !o.idx.length) return; var g = Q334_GROUPS[cls](o); if (g != null) (GR[g] || (GR[g] = [])).push(o); });
        Object.keys(GR).forEach(function(gk){ var L = GR[gk]; if (L.length >= 2) q334Group(cls, L); });
      });
      q334Stat.ms = Math.round((performance.now() - t0) * 10) / 10;
    })();
    function q334Group(cls, L){
      {
        var N = 0, FN = 0, base = [], fbase = [];
        L.forEach(function(o){ base.push(N); fbase.push(FN); N += o.vc; FN += o.idx.length / 3; });
        var P = new Float32Array(N * 3), OW = new Int32Array(N), par = new Int32Array(N), i, j, k, m;
        L.forEach(function(o, mi){ P.set(o.pos, base[mi] * 3); for (var v = 0; v < o.vc; v++) OW[base[mi] + v] = mi; });
        for (i = 0; i < N; i++) par[i] = i;
        function root(a){ while (par[a] !== a){ par[a] = par[par[a]]; a = par[a]; } return a; }
        /* 1. weld across pieces: every vertex against the vertices of other pieces within WELD_MM (a sweep along x) */
        var seamPairs = 0, tol2 = Q334_WELD * Q334_WELD, all = new Int32Array(N);
        for (i = 0; i < N; i++) all[i] = i;
        q334Sweep(P, all, Q334_WELD, function(a, b){
          if (OW[a] === OW[b]) return;
          var ex = P[3*a] - P[3*b], ey = P[3*a+1] - P[3*b+1], ez = P[3*a+2] - P[3*b+2];
          if (ex*ex + ey*ey + ez*ez <= tol2){ var ra = root(a), rb = root(b); if (ra !== rb) par[ra] = rb; seamPairs++; }
        });
        all = null;
        var O = 32768, S = 65536;
        function key(a, b, c){ return (a + O) + S * ((b + O) + S * (c + O)); }
        var R = new Int32Array(N), seam = new Uint8Array(N);
        for (i = 0; i < N; i++) R[i] = root(i);
        var firstOw = new Int32Array(N).fill(-1);
        for (i = 0; i < N; i++){ var r0 = R[i]; if (firstOw[r0] < 0) firstOw[r0] = OW[i]; else if (firstOw[r0] !== OW[i]) seam[r0] = 1; }
        /* 2. face normals (area weighted, from the welded positions P) and the faces round every seam vertex (CSR over the roots) */
        var FA = new Float32Array(FN * 3), FU = new Float32Array(FN * 3), FV = new Int32Array(FN * 3), FO = new Int32Array(FN);
        L.forEach(function(o, mi){
          var ix = o.idx, b = base[mi], fb = fbase[mi];
          for (var t = 0; t < ix.length / 3; t++){ var f = fb + t; FV[3*f] = b + ix[3*t]; FV[3*f+1] = b + ix[3*t+1]; FV[3*f+2] = b + ix[3*t+2]; FO[f] = mi; }
        });
        var q372 = !Q334_LIGHT[cls], cnt, INC, TW = new Int32Array(FN).fill(-1), GN = new Float32Array(N * 3), GOK = new Uint8Array(N), FL = null, FAR = new Float32Array(FN);      // FL: the faces near a border (all of them until 1b)
        function faceNormals(){
          for (var q = 0, nq = FL ? FL.length : FN; q < nq; q++){ var f = FL ? FL[q] : q;
            var a = 3*FV[3*f], bb = 3*FV[3*f+1], cc = 3*FV[3*f+2];
            var e1x = P[bb] - P[a], e1y = P[bb+1] - P[a+1], e1z = P[bb+2] - P[a+2], e2x = P[cc] - P[a], e2y = P[cc+1] - P[a+1], e2z = P[cc+2] - P[a+2];
            var nx = e1y*e2z - e1z*e2y, ny = e1z*e2x - e1x*e2z, nz = e1x*e2y - e1y*e2x, l = Math.hypot(nx, ny, nz) || 1;
            FA[3*f] = nx; FA[3*f+1] = ny; FA[3*f+2] = nz; FAR[f] = l; FU[3*f] = nx / l; FU[3*f+1] = ny / l; FU[3*f+2] = nz / l;
          }
        }
        function incidence(){
          var i;
          cnt = new Int32Array(N + 1);
          var nq = FL ? FL.length : FN, q, c3;
          for (q = 0; q < nq; q++) for (c3 = 0; c3 < 3; c3++){ i = 3 * (FL ? FL[q] : q) + c3; if (seam[R[FV[i]]]) cnt[R[FV[i]] + 1]++; }
          for (i = 0; i < N; i++) cnt[i + 1] += cnt[i];
          var fill = cnt.slice(0, N); INC = new Int32Array(cnt[N]);
          for (q = 0; q < nq; q++) for (c3 = 0; c3 < 3; c3++){ i = 3 * (FL ? FL[q] : q) + c3; var rr = R[FV[i]]; if (seam[rr]) INC[fill[rr]++] = (i / 3) | 0; }
        }
        /* 3. a seam vertex's normal: the dominant smooth group of the faces round it, over all pieces (orientation-free:
              the shader lights both faces, so a piece wound the other way still agrees once its sign is matched) */
        function seamNormals(){
          for (var i = 0; i < N; i++){
            GOK[i] = 0;
            if (!seam[i] || R[i] !== i) continue;
            var s0 = cnt[i], s1 = cnt[i + 1], best = -1, bs = -1, a1, a2, ex = 0;
            for (a1 = s0; a1 < s1; a1++) if (TW[INC[a1]] < 0){ ex = 1; break; }      // twinned faces (walls face to face) out of the vote, unless all are
            for (a1 = s0; a1 < s1; a1++){
              var f1 = INC[a1], sc = 0; if (ex && TW[f1] >= 0) continue;
              for (a2 = s0; a2 < s1; a2++){ var f2 = INC[a2], d = FU[3*f1]*FU[3*f2] + FU[3*f1+1]*FU[3*f2+1] + FU[3*f1+2]*FU[3*f2+2]; if (ex && TW[f2] >= 0) continue;
                if (d > Q334_COS || d < -Q334_COS) sc += FAR[f2]; }
              if (sc > bs){ bs = sc; best = f1; }
            }
            var gx = 0, gy = 0, gz = 0;
            for (a2 = s0; a2 < s1; a2++){ var g = INC[a2]; if (ex && TW[g] >= 0) continue; var dd = FU[3*best]*FU[3*g] + FU[3*best+1]*FU[3*g+1] + FU[3*best+2]*FU[3*g+2];
              if (dd > Q334_COS){ gx += FA[3*g]; gy += FA[3*g+1]; gz += FA[3*g+2]; } else if (dd < -Q334_COS){ gx -= FA[3*g]; gy -= FA[3*g+1]; gz -= FA[3*g+2]; } }
            var gl2 = Math.hypot(gx, gy, gz); if (!(gl2 > 0)) continue;
            GN[3*i] = gx / gl2; GN[3*i+1] = gy / gl2; GN[3*i+2] = gz / gl2; GOK[i] = 1;
          }
          if (!TJ.length) return;
          var MC = new Int32Array(N); for (var i3 = 0; i3 < N; i3++) MC[R[i3]]++;
          for (var z7 = 0; z7 < TJ.length; z7 += 4){ var u7 = TJ[z7], r7 = R[u7], r0 = R[TJ[z7+1]], r1 = R[TJ[z7+2]], t7 = TJ[z7+3];
            if (MC[r7] !== 1 || !GOK[r0] || !GOK[r1]) continue;      // joined to a vertex of its own meanwhile: its own seam normal stands
            var sg7 = GN[3*r0]*GN[3*r1] + GN[3*r0+1]*GN[3*r1+1] + GN[3*r0+2]*GN[3*r1+2] < 0 ? -1 : 1;
            var nx7 = (1 - t7)*GN[3*r0] + t7*sg7*GN[3*r1], ny7 = (1 - t7)*GN[3*r0+1] + t7*sg7*GN[3*r1+1], nz7 = (1 - t7)*GN[3*r0+2] + t7*sg7*GN[3*r1+2], l7 = Math.hypot(nx7, ny7, nz7);
            if (!(l7 > 0)) continue; GN[3*r7] = nx7 / l7; GN[3*r7+1] = ny7 / l7; GN[3*r7+2] = nz7 / l7; GOK[r7] = 1; }
        }
        faceNormals();
        /* 1b. borders cut at different vertices: pieces re-meshed on their own (the deformed female trunk) meet their
               neighbour 0.03-1 mm apart, not vertex for vertex. A RIM vertex (where the piece's own surface turns into its
               wall: an incident face more than ~45 degrees off the vertex normal) is joined to the mutually nearest rim
               vertex of another piece within RIM_MM, and never by more than a third of its shortest edge. */
        var rim = new Uint8Array(N), MEr = new Float64Array(N).fill(1e9), ONr = new Float32Array(N * 3), nRim = 0;
        L.forEach(function(o, mi){ ONr.set(o.nrm, base[mi] * 3); });
        for (var fr = 0; fr < FN; fr++) for (k = 0; k < 3; k++){
          var vr0 = FV[3*fr+k], vr1 = FV[3*fr+(k+1)%3];
          if (FU[3*fr]*ONr[3*vr0] + FU[3*fr+1]*ONr[3*vr0+1] + FU[3*fr+2]*ONr[3*vr0+2] < 0.7) rim[vr0] = 1;
          var le = Math.hypot(P[3*vr0] - P[3*vr1], P[3*vr0+1] - P[3*vr1+1], P[3*vr0+2] - P[3*vr1+2]); if (le < MEr[vr0]) MEr[vr0] = le; if (le < MEr[vr1]) MEr[vr1] = le;
        }
        var RL = []; if (!Q334_LIGHT[cls]) for (i = 0; i < N; i++) if (rim[i] && !seam[R[i]]) RL.push(i);
        if (RL.length){
          RL = Int32Array.from(RL);
          var rb2 = Q334_RIM * Q334_RIM, NBr = new Int32Array(N).fill(-1), BDr = new Float64Array(N).fill(rb2);
          q334Sweep(P, RL, Q334_RIM, function(u, v){
            if (OW[u] === OW[v]) return;
            var ex = P[3*u] - P[3*v], ey = P[3*u+1] - P[3*v+1], ez = P[3*u+2] - P[3*v+2], dd = ex*ex + ey*ey + ez*ez;
            if (dd >= rb2 || dd > 0.45 * MEr[u] * MEr[u] || dd > 0.45 * MEr[v] * MEr[v]) return;
            if (ONr[3*u]*ONr[3*v] + ONr[3*u+1]*ONr[3*v+1] + ONr[3*u+2]*ONr[3*v+2] < 0) return;      // not outer to inner
            if (dd < BDr[u]){ BDr[u] = dd; NBr[u] = v; }
            if (dd < BDr[v]){ BDr[v] = dd; NBr[v] = u; }
          });
          for (k = 0; k < RL.length; k++){ var ur = RL[k], vrr = NBr[ur]; if (vrr < 0 || NBr[vrr] !== ur || vrr < ur) continue; var ra1 = root(ur), rb1 = root(vrr); if (ra1 !== rb1){ par[ra1] = rb1; nRim++; } }
          if (nRim){
            for (i = 0; i < N; i++) R[i] = root(i);
            firstOw.fill(-1); seam.fill(0);
            for (i = 0; i < N; i++){ var r3 = R[i]; if (firstOw[r3] < 0) firstOw[r3] = OW[i]; else if (firstOw[r3] !== OW[i]) seam[r3] = 1; }
            var SXr = new Float64Array(N * 4);
            for (i = 0; i < N; i++){ var r4 = R[i]; if (!seam[r4]) continue; SXr[4*r4] += P[3*i]; SXr[4*r4+1] += P[3*i+1]; SXr[4*r4+2] += P[3*i+2]; SXr[4*r4+3]++; }
            for (i = 0; i < N; i++){ var r5 = R[i]; if (!seam[r5]) continue; P[3*i] = SXr[4*r5] / SXr[4*r5+3]; P[3*i+1] = SXr[4*r5+1] / SXr[4*r5+3]; P[3*i+2] = SXr[4*r5+2] / SXr[4*r5+3]; }
            faceNormals();
          }
        }
        /* 1c (Q375). T-junctions: the finger and toe slabs carry about twice the border vertices of the palm, the dorsum of the hand
               and the arches of the foot, and every other one of theirs lies ON the neighbour's border edge (within WELD_MM), not on a
               vertex: nothing to weld, its walls had no seam vertex to be judged by (drawn), and it kept its own normal, bent by its
               wall -- the light line at the base of the fingers and toes. Such a border vertex (a rim vertex, or one on the open border
               of a sheet) is ATTACHED to that edge: it counts as a seam vertex, takes the edge's interpolated seam normal (3), and its
               wall finds its twin among the faces round the edge's ends (4). Nothing is merged; the move onto the edge is < WELD_MM.
               The T-junctions closed in 4b take the edge's normal too. Skin only (not the light classes). */
        var TJ = [], TJI = new Int32Array(N).fill(-1);
        if (!Q334_LIGHT[cls]){
          var EHt = new Map(), ict = 0.5, ft, ta, tb, sI2;
          var OB = new Uint8Array(N), ECt = new Map();      // the open border of a piece that is a sheet, not a closed slab (the dorsum of the toes): an edge of one face only
          for (ft = 0; ft < FN; ft++) for (k = 0; k < 3; k++){ ta = FV[3*ft+k]; tb = FV[3*ft+(k+1)%3]; var ke = ta < tb ? ta * N + tb : tb * N + ta; ECt.set(ke, (ECt.get(ke) || 0) + 1); }
          ECt.forEach(function(c, ke){ if (c === 1){ var ea = Math.floor(ke / N); OB[ea] = 1; OB[ke - ea * N] = 1; } }); ECt = null;
          for (ft = 0; ft < FN; ft++) for (k = 0; k < 3; k++){
            ta = FV[3*ft+k]; tb = FV[3*ft+(k+1)%3]; if (ta > tb || !rim[ta] || !rim[tb]) continue;
            if (ONr[3*ta]*ONr[3*tb] + ONr[3*ta+1]*ONr[3*tb+1] + ONr[3*ta+2]*ONr[3*tb+2] < 0.5) continue;      // along the border, not across the wall
            var lnt = Math.hypot(P[3*tb] - P[3*ta], P[3*tb+1] - P[3*ta+1], P[3*tb+2] - P[3*ta+2]), nst = Math.min(64, Math.ceil(lnt)), lk = -1;
            for (sI2 = 0; sI2 <= nst; sI2++){ var tq = nst ? sI2 / nst : 0;
              var kt = key(Math.floor((P[3*ta] + tq*(P[3*tb] - P[3*ta])) * ict), Math.floor((P[3*ta+1] + tq*(P[3*tb+1] - P[3*ta+1])) * ict), Math.floor((P[3*ta+2] + tq*(P[3*tb+2] - P[3*ta+2])) * ict));
              if (kt === lk) continue; lk = kt; var at2 = EHt.get(kt); if (at2) at2.push(ta, tb); else EHt.set(kt, [ta, tb]); }
          }
          for (var u1 = 0; u1 < N; u1++){
            if (!(rim[u1] || OB[u1]) || seam[R[u1]]) continue;
            var ux = P[3*u1], uy = P[3*u1+1], uz = P[3*u1+2], bdt = Q334_WELD * Q334_WELD, bt = null;
            for (var cx = Math.floor((ux - 0.1) * ict); cx <= Math.floor((ux + 0.1) * ict); cx++) for (var cy = Math.floor((uy - 0.1) * ict); cy <= Math.floor((uy + 0.1) * ict); cy++)
              for (var cz = Math.floor((uz - 0.1) * ict); cz <= Math.floor((uz + 0.1) * ict); cz++){
                var ce = EHt.get(key(cx, cy, cz)); if (!ce) continue;
                for (var q6 = 0; q6 < ce.length; q6 += 2){ var ea0 = ce[q6], eb0 = ce[q6+1]; if (OW[ea0] === OW[u1]) continue;
                  var ex6 = P[3*eb0] - P[3*ea0], ey6 = P[3*eb0+1] - P[3*ea0+1], ez6 = P[3*eb0+2] - P[3*ea0+2], l6 = ex6*ex6 + ey6*ey6 + ez6*ez6; if (!(l6 > 0)) continue;
                  var t6 = ((ux - P[3*ea0])*ex6 + (uy - P[3*ea0+1])*ey6 + (uz - P[3*ea0+2])*ez6) / l6; if (t6 <= 0.02 || t6 >= 0.98) continue;
                  var qx6 = P[3*ea0] + t6*ex6 - ux, qy6 = P[3*ea0+1] + t6*ey6 - uy, qz6 = P[3*ea0+2] + t6*ez6 - uz, d6 = qx6*qx6 + qy6*qy6 + qz6*qz6;
                  if (d6 <= bdt){ bdt = d6; bt = [ea0, eb0, t6]; } }
              }
            if (!bt) continue;
            TJI[u1] = TJ.length; TJ.push(u1, bt[0], bt[1], bt[2]); seam[R[u1]] = 1;
            P[3*u1] = P[3*bt[0]] + bt[2]*(P[3*bt[1]] - P[3*bt[0]]); P[3*u1+1] = P[3*bt[0]+1] + bt[2]*(P[3*bt[1]+1] - P[3*bt[0]+1]); P[3*u1+2] = P[3*bt[0]+2] + bt[2]*(P[3*bt[1]+2] - P[3*bt[0]+2]);
          }
          EHt = null;
          if (TJ.length) faceNormals();
        }
        /* from here on only the faces near a border are looked at: those touching a rim or a welded vertex (the rest of a
           piece -- most of it -- keeps its own normals and is never a wall) */
        var BFn = 0, BFa = new Int32Array(FN);
        for (var fb2 = 0; fb2 < FN; fb2++){ var v0 = FV[3*fb2], v1 = FV[3*fb2+1], v2 = FV[3*fb2+2];
          if (rim[v0] || rim[v1] || rim[v2] || seam[R[v0]] || seam[R[v1]] || seam[R[v2]]) BFa[BFn++] = fb2; }
        FL = BFa.subarray(0, BFn);
        rim = MEr = ONr = null;
        incidence(); twins(); seamNormals();
        var a1;
        /* 4. walls: a face touching a seam vertex, standing across that vertex's surface normal, with a face of the
              neighbouring piece parallel to it and within WALL_MM of its centre (the neighbour's wall). A real crease
              between two pieces has no such twin, so it is never taken for a wall. Q372: (a) a wall standing at a slant
              (WALL_SLANT, the thin slabs of the fingers and toes) whose twin is a clear wall is one of a PAIR of walls and is
              hidden with it -- before, only the steeper of the two was, and the other drew a line along the border; (b) a
              face whose twin is IDENTICAL (the same three welded vertices) but which is not a clear wall (two regions carry
              the same piece of surface) is drawn ONCE: only the face of the higher-numbered piece is hidden, so nothing
              opens; (c) the twinned faces stay out of the seam normal's vote (seamNormals), where two coincident walls used
              to out-vote the surface and bend the normal into the wall (the walls were then taken for surface and drawn, and
              the seam was shaded with the wall's normal: the dotted light / dark line); (d) a face that lies in the surface at
              one of its seam vertices (|cos| >= WALL_LIE) over a twin at an angle (|cos| < WALL_TWIN) is the surface folding
              over a neighbour's wall at a thin tip (toes): never hidden, so no hole opens. (a)-(d) on the skin only (q372);
              the opaque cortex and the fascia keep the rule as it was. */
        var wall = new Int32Array(FN).fill(-1), nWall = 0, nCand = 0, nPair = 0, nDup = 0, f;
        function twinOf(f, skip){      // the nearest twin of f (-1: none); skip: leave out faces already hidden for a third piece
          var mi0 = FO[f], cxm = 0, cym = 0, czm = 0, bestD = Q334_WALL, nb = -1, k, a1;
          for (k = 0; k < 3; k++){ cxm += P[3*FV[3*f+k]] / 3; cym += P[3*FV[3*f+k]+1] / 3; czm += P[3*FV[3*f+k]+2] / 3; }
          for (k = 0; k < 3; k++){
            var vk2 = FV[3*f+k], vr3 = R[vk2]; if (!seam[vr3]) continue;
            var hs2 = TJI[vk2] >= 0 ? [vr3, R[TJ[TJI[vk2]+1]], R[TJ[TJI[vk2]+2]]] : [vr3];
            for (var hq2 = 0; hq2 < hs2.length; hq2++){ var vr2 = hs2[hq2]; if (!seam[vr2]) continue;
            for (a1 = cnt[vr2]; a1 < cnt[vr2 + 1]; a1++){
              var h = INC[a1]; if (FO[h] === mi0 || skip && wall[h] >= 0 && wall[h] !== mi0) continue;
              var pd = FU[3*f]*FU[3*h] + FU[3*f+1]*FU[3*h+1] + FU[3*f+2]*FU[3*h+2]; if (pd < 0.6 && pd > -0.6) continue;
              var dist = q334PtTri(cxm, cym, czm, P, FV[3*h], FV[3*h+1], FV[3*h+2]);
              if (dist < bestD && (q334In || q334Over(f, h))){ bestD = dist; nb = h; }      // face to face: over the twin, not beside it
            }
            }
          }
          return nb;
        }
        function twins(){ if (q372) for (var q = 0; q < FL.length; q++) TW[FL[q]] = twinOf(FL[q], false); }      // TW: each border face's nearest twin (-1: none)
        var acrossMax = 0;
        function across(f){      // |cos| between f and the surface normal, least over f's seam vertices (2: no seam normal there); acrossMax: the most
          var m = 2; acrossMax = 0;
          for (var k = 0; k < 3; k++){ var vr = R[FV[3*f+k]]; if (seam[vr] && GOK[vr]){ var c = Math.abs(FU[3*f]*GN[3*vr] + FU[3*f+1]*GN[3*vr+1] + FU[3*f+2]*GN[3*vr+2]); m = Math.min(m, c); acrossMax = Math.max(acrossMax, c); } }
          return m;
        }
        function same(f, h){ var a = R[FV[3*f]], b = R[FV[3*f+1]], c = R[FV[3*f+2]], x = R[FV[3*h]], y = R[FV[3*h+1]], z = R[FV[3*h+2]];
          return a !== b && b !== c && a !== c && (a === x || a === y || a === z) && (b === x || b === y || b === z) && (c === x || c === y || c === z); }
        function walls(count){      // run again once the borders are closed (4b): a wall at a corner of three pieces finds its twin then
          for (var q = 0; q < FL.length; q++){ var f = FL[q];
            if (wall[f] >= 0) continue;
            var af = across(f), am = acrossMax; if (af > 1) continue;
            if (af < 0.5 && count) nCand++;
            if (q372 && TW[f] < 0) continue;      // twins() ran on this geometry: no twin at all, so none for twinOf(f, true) either
            var h = twinOf(f, true); if (h < 0) continue;
            var pdh = Math.abs(FU[3*f]*FU[3*h] + FU[3*f+1]*FU[3*h+1] + FU[3*f+2]*FU[3*h+2]);
            if (q372 && am >= Q334_LIE && pdh < Q334_TWIN) continue;      // (d)
            if (af < 0.5){ wall[f] = FO[h]; nWall++; continue; }
            if (!q372) continue;
            var ah = across(h);
            if (af < Q334_SLANT && ah < 0.5){ wall[f] = FO[h]; nWall++; nPair++; continue; }      // (a)
            if (FO[f] > FO[h] && wall[h] < 0 && same(f, h)){ wall[f] = FO[h]; nWall++; nDup++; }      // (b)
          }
        }
        function q334Over(f, h){      // f and h share an edge and lie on the SAME side of it: they overlap (a twin wall), not continue each other
          var sa = -1, sb = -1, fo = -1, ho = -1, a, b;
          for (a = 0; a < 3; a++) for (b = 0; b < 3; b++) if (R[FV[3*f+a]] === R[FV[3*h+b]]){ if (sa < 0) sa = a; else if (sb < 0) sb = a; }
          if (sb < 0) return false;
          fo = FV[3*f + (3 - sa - sb)];
          var e0 = R[FV[3*f+sa]], e1 = R[FV[3*f+sb]];
          for (b = 0; b < 3; b++){ var rb = R[FV[3*h+b]]; if (rb !== e0 && rb !== e1) ho = FV[3*h+b]; }
          if (ho < 0) return false;
          var ex = P[3*e1] - P[3*e0], ey = P[3*e1+1] - P[3*e0+1], ez = P[3*e1+2] - P[3*e0+2], el = ex*ex + ey*ey + ez*ez; if (!(el > 0)) return false;
          function perp(v){ var wx = P[3*v] - P[3*e0], wy = P[3*v+1] - P[3*e0+1], wz = P[3*v+2] - P[3*e0+2], t = (wx*ex + wy*ey + wz*ez) / el; return [wx - t*ex, wy - t*ey, wz - t*ez]; }
          var pf = perp(fo), ph = perp(ho);
          return pf[0]*ph[0] + pf[1]*ph[1] + pf[2]*ph[2] > 0;
        }
        walls(true);
        /* 4b. close the drawn surface. With the walls left out, the border of each piece is an open edge of the drawn surface.
               Most borders meet the neighbour's vertex for vertex (welded above), but not all: the inner border is cut at
               other vertices than the neighbour's (the trunk's left and right halves leave up to ~1.2 mm between them), and
               some outer border vertices miss by tenths of a millimetre or end on the middle of the neighbour's edge -- a
               crack the background shows through. Every open border vertex is (a) joined to the mutually nearest open border
               vertex of another piece on the same face of the skin (their normals agree, so never outer to inner, which lie a
               skin thickness apart) within SNAP_MM, both to their mean; or else (b) moved onto the nearest open edge of
               another piece within TJ_MM (a T-junction, closed). */
        var nSnap = 0, nTJ = 0;
        function openEdges(){      // edges of the drawn (non-wall) faces that no other drawn face shares, as [root a, root b, piece]
          var KS = new Float64Array(FN * 3), n = 0, f2, k2, ea, eb;
          for (var q2 = 0; q2 < FL.length; q2++){ f2 = FL[q2]; if (wall[f2] >= 0) continue;
            for (k2 = 0; k2 < 3; k2++){ ea = R[FV[3*f2+k2]]; eb = R[FV[3*f2+(k2+1)%3]]; if (ea !== eb) KS[n++] = ea < eb ? ea * N + eb : eb * N + ea; } }
          KS = KS.subarray(0, n).sort();
          var U = new Set(), RB = new Uint8Array(N);
          for (var z = 0; z < n; z++) if ((z === 0 || KS[z] !== KS[z-1]) && (z === n - 1 || KS[z] !== KS[z+1])){ U.add(KS[z]); ea = Math.floor(KS[z] / N); RB[ea] = 1; RB[KS[z] - ea * N] = 1; }
          var out = [];
          for (var q2 = 0; q2 < FL.length; q2++){ f2 = FL[q2]; if (wall[f2] >= 0) continue;
            for (k2 = 0; k2 < 3; k2++){ ea = R[FV[3*f2+k2]]; eb = R[FV[3*f2+(k2+1)%3]]; if (ea === eb || !RB[ea] || !RB[eb]) continue;
              if (U.has(ea < eb ? ea * N + eb : eb * N + ea)) out.push(ea, eb, FO[f2]); } }
          return out;
        }
        function average(){
          var SX = new Float64Array(N * 4), i2, r2;
          for (i2 = 0; i2 < N; i2++){ r2 = R[i2]; if (!seam[r2]) continue; SX[4*r2] += P[3*i2]; SX[4*r2+1] += P[3*i2+1]; SX[4*r2+2] += P[3*i2+2]; SX[4*r2+3]++; }
          for (i2 = 0; i2 < N; i2++){ r2 = R[i2]; if (!seam[r2]) continue; P[3*i2] = SX[4*r2] / SX[4*r2+3]; P[3*i2+1] = SX[4*r2+1] / SX[4*r2+3]; P[3*i2+2] = SX[4*r2+2] / SX[4*r2+3]; }
        }
        average();      // the "same" border vertex of two pieces differs by micrometres (each piece quantised over its own box)
        function closeBorders(){
        var OE = openEdges(), RN = new Float32Array(N * 3), OWN = new Int32Array(N * 4).fill(-1), isOpen = new Uint8Array(N), OR = [];
        for (var q3 = 0; q3 < FL.length; q3++){ f = FL[q3]; if (wall[f] >= 0) continue;      // a wall-free normal per border vertex, each piece in its own winding
          for (k = 0; k < 3; k++){ var rn = R[FV[3*f+k]]; RN[3*rn] += FA[3*f]; RN[3*rn+1] += FA[3*f+1]; RN[3*rn+2] += FA[3*f+2]; } }
        for (i = 0; i < OE.length; i += 3) for (k = 0; k < 2; k++){      // the pieces whose open edges meet at each open root (up to 4)
          var ro = OE[i+k], pc = OE[i+2]; if (!isOpen[ro]){ isOpen[ro] = 1; OR.push(ro); }
          for (var z = 0; z < 4; z++){ if (OWN[4*ro+z] === pc) break; if (OWN[4*ro+z] < 0){ OWN[4*ro+z] = pc; break; } } }
        function owns(a, pc){ for (var z = 0; z < 4; z++) if (OWN[4*a+z] === pc) return true; return false; }
        function apart(a, b){ for (var z = 0; z < 4; z++){ var pc = OWN[4*a+z]; if (pc < 0) break; if (owns(b, pc)) return false; } return true; }
        for (k = 0; k < N; k++){ var lr = Math.hypot(RN[3*k], RN[3*k+1], RN[3*k+2]); if (lr > 0){ RN[3*k] /= lr; RN[3*k+1] /= lr; RN[3*k+2] /= lr; } }
        function sameFace(a, b){ return (RN[3*a]*RN[3*b] + RN[3*a+1]*RN[3*b+1] + RN[3*a+2]*RN[3*b+2]) > 0.3; }
        OR = Int32Array.from(OR);
        /* never move a vertex by more than a third of its shortest drawn edge: a join or a T-junction may close a crack, it
           must not fold a triangle (the lips, nostrils and ear folds are cut into pieces a millimetre or two across) */
        var ME = new Float64Array(N).fill(1e9);
        for (var q4 = 0; q4 < FL.length; q4++){ f = FL[q4]; if (wall[f] >= 0) continue;
          for (k = 0; k < 3; k++){ var ma = R[FV[3*f+k]], mb = R[FV[3*f+(k+1)%3]]; if (ma === mb) continue;
            var me = Math.hypot(P[3*ma] - P[3*mb], P[3*ma+1] - P[3*mb+1], P[3*ma+2] - P[3*mb+2]); if (me < ME[ma]) ME[ma] = me; if (me < ME[mb]) ME[mb] = me; } }
        var s2 = Q334_SNAP * Q334_SNAP, NB = new Int32Array(N).fill(-1), BD = new Float64Array(N).fill(s2), joined = new Uint8Array(N);
        q334Sweep(P, OR, Q334_SNAP, function(u, v){
          var ex = P[3*u] - P[3*v], ey = P[3*u+1] - P[3*v+1], ez = P[3*u+2] - P[3*v+2], dd = ex*ex + ey*ey + ez*ez;
          if (dd >= s2 || (dd >= BD[u] && dd >= BD[v]) || dd > 0.45 * ME[u] * ME[u] || dd > 0.45 * ME[v] * ME[v] || !apart(u, v) || !sameFace(u, v)) return;
          if (dd < BD[u]){ BD[u] = dd; NB[u] = v; }
          if (dd < BD[v]){ BD[v] = dd; NB[v] = u; }
        });
        for (k = 0; k < OR.length; k++){ var u0 = OR[k], v0 = NB[u0]; if (v0 < 0 || NB[v0] !== u0 || v0 < u0) continue;
          var ra = root(u0), rb = root(v0); if (ra !== rb){ par[ra] = rb; nSnap++; } joined[u0] = joined[v0] = 1; }
        for (i = 0; i < N; i++) R[i] = root(i);
        for (k = 0; k < OR.length; k++) if (joined[OR[k]]) seam[R[OR[k]]] = 1;
        average();
        /* (b) T-junctions: an open border vertex still without a partner, onto the nearest open edge of another piece
               (edges registered in 4 mm cells every 1 mm along them; a vertex looks in the cells within 1 mm of it) */
        var EH = new Map(), ic = 1 / 4, tj2 = Q334_TJ * Q334_TJ, moved = [];
        for (i = 0; i < OE.length; i += 3){
          var e0 = R[OE[i]], e1 = R[OE[i+1]]; if (e0 === e1) continue;
          var ln = Math.hypot(P[3*e1] - P[3*e0], P[3*e1+1] - P[3*e0+1], P[3*e1+2] - P[3*e0+2]), ns = Math.ceil(ln), lastK = -1;
          if (ns > 128) continue;
          for (var sI = 0; sI <= ns; sI++){ var tt = ns ? sI / ns : 0;
            var kk2 = key(Math.floor((P[3*e0] + tt*(P[3*e1] - P[3*e0])) * ic), Math.floor((P[3*e0+1] + tt*(P[3*e1+1] - P[3*e0+1])) * ic), Math.floor((P[3*e0+2] + tt*(P[3*e1+2] - P[3*e0+2])) * ic));
            if (kk2 === lastK) continue; lastK = kk2; var a2 = EH.get(kk2); if (a2){ if (a2[a2.length - 1] !== i) a2.push(i); } else EH.set(kk2, [i]); }
        }
        for (k = 0; k < OR.length; k++){
          var u = OR[k]; if (joined[u]) continue;
          var ru = R[u], px = P[3*ru], py = P[3*ru+1], pz = P[3*ru+2], bd = tj2, bq = null;
          var x0 = Math.floor((px - 1) * ic), x1 = Math.floor((px + 1) * ic), y0 = Math.floor((py - 1) * ic), y1 = Math.floor((py + 1) * ic), z0 = Math.floor((pz - 1) * ic), z1 = Math.floor((pz + 1) * ic);
          for (var dx = x0; dx <= x1; dx++) for (var dy = y0; dy <= y1; dy++) for (var dz = z0; dz <= z1; dz++){
            var c = EH.get(key(dx, dy, dz)); if (!c) continue;
            for (var q = 0; q < c.length; q++){
              var e = c[q], a = R[OE[e]], b = R[OE[e+1]]; if (a === ru || b === ru || owns(u, OE[e+2]) || !sameFace(u, OE[e])) continue;
              var abx = P[3*b] - P[3*a], aby = P[3*b+1] - P[3*a+1], abz = P[3*b+2] - P[3*a+2], ll = abx*abx + aby*aby + abz*abz; if (!(ll > 0)) continue;
              var t = ((px - P[3*a])*abx + (py - P[3*a+1])*aby + (pz - P[3*a+2])*abz) / ll; if (t <= 0.1 || t >= 0.9) continue;
              var qx = P[3*a] + t*abx, qy = P[3*a+1] + t*aby, qz = P[3*a+2] + t*abz, dd = (px-qx)*(px-qx) + (py-qy)*(py-qy) + (pz-qz)*(pz-qz);
              if (dd < bd && dd < 0.1 * ME[ru] * ME[ru] && dd < 0.05 * ll){ bd = dd; bq = [qx, qy, qz, a, b, t]; }
            }
          }
          if (bq) moved.push(ru, bq[0], bq[1], bq[2]);
          if (bq && !Q334_LIGHT[cls]){ if (TJI[ru] < 0) TJI[ru] = TJ.length; TJ.push(ru, bq[3], bq[4], bq[5]); }      // Q375: its normal from the edge too (1c)
        }
        if (moved.length){
          var MV = new Float64Array(N * 3), mf = new Uint8Array(N);
          for (k = 0; k < moved.length; k += 4){ var mr = moved[k]; mf[mr] = 1; seam[mr] = 1; MV[3*mr] = moved[k+1]; MV[3*mr+1] = moved[k+2]; MV[3*mr+2] = moved[k+3]; nTJ++; }
          for (i = 0; i < N; i++){ var qr = R[i]; if (mf[qr]){ P[3*i] = MV[3*qr]; P[3*i+1] = MV[3*qr+1]; P[3*i+2] = MV[3*qr+2]; } }
        }
        OE = EH = NB = BD = OWN = null;
        }
        if (!Q334_LIGHT[cls]) closeBorders();
        if (nSnap || nTJ){ faceNormals(); incidence(); twins(); seamNormals();
          var w0 = nWall; walls(false);
          if (nWall > w0){ closeBorders(); faceNormals(); incidence(); twins(); seamNormals(); }      // walls found only now leave borders of their own to close
        }
        if (window.__q334dbgE){      // diagnostics only: edges of the drawn surface that no other drawn face closes
          var EM = new Map();
          for (f = 0; f < FN; f++){ if (wall[f] >= 0) continue;
            for (k = 0; k < 3; k++){ var ea = R[FV[3*f+k]], eb = R[FV[3*f+(k+1)%3]], ek = ea < eb ? ea * N + eb : eb * N + ea; EM.set(ek, (EM.get(ek) || 0) + 1); } }
          EM.forEach(function(c, ek){ if (c !== 1) return; var ea = Math.floor(ek / N), eb = ek - ea * N;
            window.__q334dbgE.push([P[3*ea], P[3*ea+1], P[3*ea+2], P[3*eb], P[3*eb+1], P[3*eb+2], !!seam[ea], !!seam[eb]]); });
        }
        /* 5. write back: welded normals into the piece's own normals (the batch buffer is built from them next), the
              wall faces moved out of the drawn index range into per-neighbour groups (uploaded after the batching) */
        var nSeamV = 0, VN = new Float32Array(N * 3);      // each vertex's own drawn faces, in its piece's winding: the sign of its normal
        for (var q5 = 0; q5 < FL.length; q5++){ f = FL[q5]; if (wall[f] >= 0) continue; for (k = 0; k < 3; k++){ var vv = FV[3*f+k]; VN[3*vv] += FA[3*f]; VN[3*vv+1] += FA[3*f+1]; VN[3*vv+2] += FA[3*f+2]; } }
        L.forEach(function(o, mi){
          var b = base[mi], fb = fbase[mi], nt = o.idx.length / 3, v, t;
          for (v = 0; v < o.vc; v++){
            var r1 = R[b + v]; if (!seam[r1]) continue;
            o.pos[3*v] = P[3*(b + v)]; o.pos[3*v+1] = P[3*(b + v)+1]; o.pos[3*v+2] = P[3*(b + v)+2];
            if (!GOK[r1]) continue;
            var sx = GN[3*r1], sy = GN[3*r1+1], sz = GN[3*r1+2];
            var gv = 3*(b + v), sg = sx*VN[gv] + sy*VN[gv+1] + sz*VN[gv+2];
            if (sg === 0) sg = sx*o.nrm[3*v] + sy*o.nrm[3*v+1] + sz*o.nrm[3*v+2];
            if (sg < 0){ sx = -sx; sy = -sy; sz = -sz; }      // the piece's own winding
            o.nrm[3*v] = sx; o.nrm[3*v+1] = sy; o.nrm[3*v+2] = sz; nSeamV++;
          }
          var nk = 0, byNb = null;
          for (t = 0; t < nt; t++){ var w = wall[fb + t]; if (w < 0) nk++; else (byNb || (byNb = {}))[w] = ((byNb || {})[w] || 0) + 1; }
          if (byNb){
            var keep = new Uint16Array(nk * 3), at = 0, gi = {};
            var groups = Object.keys(byNb).map(function(w){ var g = {nb:L[+w], idx:new Uint16Array(byNb[w] * 3), n:0}; gi[w] = g; return g; });
            for (t = 0; t < nt; t++){
              var w2 = wall[fb + t], dst = w2 < 0 ? null : gi[w2];
              if (!dst){ keep[at++] = o.idx[3*t]; keep[at++] = o.idx[3*t+1]; keep[at++] = o.idx[3*t+2]; }
              else { dst.idx[dst.n++] = o.idx[3*t]; dst.idx[dst.n++] = o.idx[3*t+1]; dst.idx[dst.n++] = o.idx[3*t+2]; }
            }
            o.idx = keep; o.q334w = groups;
          }
          q334W[OBJ.indexOf(o)] = {pos:new Float32Array(o.pos), nrm:new Float32Array(o.nrm), walls:o.q334w ? o.q334w.length : 0};
        });
        var st = q334Stat.cls[cls] || (q334Stat.cls[cls] = {groups:0, pieces:0, verts:0, faces:0, seamPairs:0, seamVerts:0, wallFaces:0, wallCandidates:0, wallPairs:0, wallDoubled:0, borderJoins:0, tJunctions:0, rimJoins:0});
        st.groups++; st.pieces += L.length; st.verts += N; st.faces += FN; st.seamPairs += seamPairs; st.seamVerts += nSeamV;
        st.wallFaces += nWall; st.wallCandidates += nCand; st.wallPairs += nPair; st.wallDoubled += nDup; st.borderJoins += nSnap; st.tJunctions += nTJ; st.rimJoins += nRim;
      }
    }
    function q334Sweep(P, list, tol, fn){      // every pair of the listed vertices closer than tol along one axis (then fn tests the rest)
      var n = list.length, K = new Float64Array(n), z, a, b;
      for (z = 0; z < n; z++){ var pz = 3*list[z];      // along a skew axis (the models are mirrored: thousands of vertices sit at x = 0 exactly)
        K[z] = Math.round((0.5345 * P[pz] + 0.6682 * P[pz+1] + 0.5175 * P[pz+2]) * 1000 + 2e6) * 262144 + z; }      // micrometres, then the slot
      K.sort();
      var X = new Float64Array(n), I = new Int32Array(n), lim = tol * 1000 + 1;
      for (z = 0; z < n; z++){ var sl = K[z] % 262144; I[z] = list[sl]; X[z] = Math.floor(K[z] / 262144); }
      for (a = 0; a < n; a++) for (b = a + 1; b < n && X[b] - X[a] <= lim; b++) fn(I[a], I[b]);
    }
    var q334In = false;      // set by q334PtTri: the closest point lies inside the triangle (not on an edge or a corner)
    function q334PtTri(px, py, pz, P, ia, ib, ic){      // distance from a point to a triangle (Ericson, closest point)
      var ax = P[3*ia], ay = P[3*ia+1], az = P[3*ia+2], bx = P[3*ib], by = P[3*ib+1], bz = P[3*ib+2], cx = P[3*ic], cy = P[3*ic+1], cz = P[3*ic+2];
      var abx = bx-ax, aby = by-ay, abz = bz-az, acx = cx-ax, acy = cy-ay, acz = cz-az, apx = px-ax, apy = py-ay, apz = pz-az;
      var d1 = abx*apx+aby*apy+abz*apz, d2 = acx*apx+acy*apy+acz*apz, qx, qy, qz; q334In = false;
      if (d1 <= 0 && d2 <= 0){ qx = ax; qy = ay; qz = az; }
      else {
        var bpx = px-bx, bpy = py-by, bpz = pz-bz, d3 = abx*bpx+aby*bpy+abz*bpz, d4 = acx*bpx+acy*bpy+acz*bpz;
        var cpx = px-cx, cpy = py-cy, cpz = pz-cz, d5 = abx*cpx+aby*cpy+abz*cpz, d6 = acx*cpx+acy*cpy+acz*cpz;
        var vc = d1*d4 - d3*d2, vb = d5*d2 - d1*d6, va = d3*d6 - d5*d4, t;
        if (d3 >= 0 && d4 <= d3){ qx = bx; qy = by; qz = bz; }
        else if (d6 >= 0 && d5 <= d6){ qx = cx; qy = cy; qz = cz; }
        else if (vc <= 0 && d1 >= 0 && d3 <= 0){ t = d1 / (d1 - d3); qx = ax + t*abx; qy = ay + t*aby; qz = az + t*abz; }
        else if (vb <= 0 && d2 >= 0 && d6 <= 0){ t = d2 / (d2 - d6); qx = ax + t*acx; qy = ay + t*acy; qz = az + t*acz; }
        else if (va <= 0 && (d4 - d3) >= 0 && (d5 - d6) >= 0){ t = (d4 - d3) / ((d4 - d3) + (d5 - d6)); qx = bx + t*(cx-bx); qy = by + t*(cy-by); qz = bz + t*(cz-bz); }
        else { q334In = true; var den = 1 / (va + vb + vc), v2 = vb * den, w2 = vc * den; qx = ax + abx*v2 + acx*w2; qy = ay + aby*v2 + acy*w2; qz = az + abz*v2 + acz*w2; }
      }
      return Math.hypot(px-qx, py-qy, pz-qz);
    }
    /* the pose decodes its rest geometry itself: hand it the welded rest normals of these pieces */
    poseRestOfZ = (function(orig){ return function(i){ var r = orig(i), w = q334W[i]; if (w && !r.q334){ r.pos.set(w.pos); r.nrm.set(w.nrm); r.q334 = 1; } return r; }; })(poseRestOfZ);
