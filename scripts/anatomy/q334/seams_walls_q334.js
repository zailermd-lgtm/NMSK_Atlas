    /* Q334: a piece's wall toward a neighbour is drawn only while that neighbour is not drawn (hidden, switched off, cut
       away, other side): then it is the piece's real boundary. Drawn with the piece's own colour and opacity, after the scene. */
    function q334Look(o){
      if (o === selected || o === hovered) return {a:1, hl:selected === o ? 1 : 0.6};
      if (faded.has(o)) return {a:Math.min(0.18, alphaFor[o.layer]), hl:0};
      var lk = selLook(o);
      if (lk === "") return {a:layerAlpha(o.layer), hl:0};
      if (lk === "hl") return {a:1, hl:0};
      return {a:selAlpha(lk, o.layer, lk === "ghost" ? alphaFor[o.layer] : layerAlpha(o.layer)), hl:0};
    }
    var q334Drawn = 0;
    addonDraw.push(function q334Walls(){
      if (q301.mode === "xray") return;
      var n = 0;
      BATCHES.forEach(function(B){
        if (!B.q334ib) return;
        var bound = false;
        B.objs.forEach(function(o){
          if (!o.q334w || !vis(o)) return;
          var lk = null;
          o.q334w.forEach(function(g){
            if (vis(g.nb)) return;
            if (!bound){
              gl.useProgram(prog); gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1);
              gl.bindBuffer(gl.ARRAY_BUFFER, B.pb); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
              gl.bindBuffer(gl.ARRAY_BUFFER, B.nb); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
              gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, B.q334ib); bound = true;
            }
            if (!lk){
              lk = q334Look(o); var c = colOf(o);
              gl.uniform3f(U.uColor, c[0], c[1], c[2]); gl.uniform1f(U.uAlpha, lk.a); gl.uniform1f(U.uHL, lk.hl);
              gl.uniform1f(U.uMu, q301.mu ? q301.mu(o) : 1);
              if (lk.a >= 0.999){ gl.disable(gl.BLEND); gl.depthMask(true); }
              else { gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA); gl.depthMask(false); }
            }
            gl.drawElements(gl.TRIANGLES, g.c, gl.UNSIGNED_SHORT, g.s * 2); n++;
          });
        });
      });
      q334Drawn = n;
      if (n){ gl.depthMask(true); gl.disable(gl.BLEND); }
    });
    /* Q334: a translucent class drawn in mesh order blends its far and near layers in a different order from one piece to
       the next (alpha blending is not commutative), so every piece came out a shade lighter or darker than its neighbour and
       the border between them drew a line. The pieces of these classes are drawn far to near instead, across all the class's
       batches at once (the female skin needs two), whatever pass asks: plain, faded, the selection's fade / x-ray / ghost. */
    var Q334_SORT = {skin:1, fascia:1}, q334Ord = {}, q334Cls = null, q334NoSort = false;
    function q334Sort(B, test){
      if (!Q334_SORT[B.layer] || q334NoSort || !lastEye || q301.mode === "xray") return false;      // the DRR paints one colour: order-free
      if (!q334Cls){ q334Cls = {}; BATCHES.forEach(function(b){ if (Q334_SORT[b.layer]) (q334Cls[b.layer] || (q334Cls[b.layer] = [])).push(b); }); }
      var cls = B.layer, st = q334Ord[cls], key = drawCount + (symPass ? 0.5 : 0);
      if (!st || st.key !== key){
        var e = lastEye, f = lastFwd, L = [];
        q334Cls[cls].forEach(function(b){ b.objs.forEach(function(o){ var c = o.center; L.push({o:o, b:b, d:(c[0]-e[0])*f[0] + (c[1]-e[1])*f[1] + (c[2]-e[2])*f[2]}); }); });
        L.sort(function(p, q){ return q.d - p.d; });
        st = q334Ord[cls] = {key:key, list:L, done:[]};
      }
      if (st.done.indexOf(test) >= 0) return true;      // this pass already drew the whole class from its first batch
      st.done.push(test);
      var bound = null, lc = null, lm = -2;
      for (var i = 0; i < st.list.length; i++){
        var it = st.list[i], o = it.o; if (!test(o)) continue;
        if (bound !== it.b){ bound = it.b;
          gl.bindBuffer(gl.ARRAY_BUFFER, bound.pb); gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ARRAY_BUFFER, bound.nb); gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 0, 0);
          gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, bound.ib); }
        var c2 = colOf(o), mu = q301.mu ? q301.mu(o) : -1;
        if (c2 !== lc){ gl.uniform3f(U.uColor, c2[0], c2[1], c2[2]); lc = c2; }
        if (mu !== lm && q301.mu){ gl.uniform1f(U.uMu, mu); lm = mu; }
        gl.drawElements(gl.TRIANGLES, o.iCount, gl.UNSIGNED_SHORT, o.iStart * 2);
      }
      return true;
    }
