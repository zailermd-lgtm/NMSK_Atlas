      /* ---- Q303: centring imaging on what was chosen, four panes, "facing me" + saved views, nerve emphasis ----
         Everything shareable is in viewer/q303/; this is only what this engine draws with, and it is the same shape as
         the own engine's glue so the two behave identically. Spliced by scripts/anatomy/q303/patch_engines_q303.py. */
      var q303byId = {};
      OBJ.forEach(function(o){ q303byId[o.id || o.name] = o; });
      function q303mmPerPx(){                       /* millimetres per CSS pixel at the camera's own target plane */
        var r = canvas.getBoundingClientRect();
        return 2 * cam.dist * Math.tan(0.425) / Math.max(1, r.height * q303ph());
      }
      function q303fit(rad){ return Math.max(HGT * 0.025, Math.min(HGT * 8, (Math.max(0.5, rad) / Math.tan(0.425)) * 1.35)); }
      function q303eye(){
        var ce = Math.cos(cam.el);
        return [cam.tgt[0] + cam.dist * ce * Math.sin(cam.az), cam.tgt[1] + cam.dist * Math.sin(cam.el),
                cam.tgt[2] + cam.dist * ce * Math.cos(cam.az)];
      }
      var q303ix = null;
      function q303pos(id){                         /* the structure's own vertices in the model frame, decoded on demand */
        if (!q303ix){ q303ix = {}; OBJ.forEach(function(o, i){ q303ix[o.id || o.name] = i; }); }
        var i = q303ix[id];
        if (i == null || !BIN) return null;
        var rec = MAN.meshes[i];
        if (!rec) return null;
        try {
          var vc = rec.vc, mn = rec.min, sp = rec.span;
          var qv = new Uint16Array(BIN.buffer, BIN.byteOffset + rec.vo, vc * 3), pos = new Float32Array(vc * 3);
          for (var v = 0; v < vc * 3; v += 3){
            pos[v] = mn[0] + qv[v] / 65535 * sp[0];
            pos[v + 1] = mn[1] + qv[v + 1] / 65535 * sp[1];
            pos[v + 2] = mn[2] + qv[v + 2] / 65535 * sp[2];
          }
          return pos;
        } catch (err){ return null; }
      }

      /* ---- the nerve-emphasis pass. A tiny program of its own, compiled from the SHARED GLSL
         (viewer/q303/nervepass.js -- byte-identical in both templates), hung on this engine's existing after-draw hook:
         the scene is already painted, the MVP and the eye are handed over, and the hook's caller restores the GL state
         afterwards. Q300's bone pass is the model: drawn after the translucent pass with the depth test off, so a
         nerve's share of the pixel does not depend on how many layers lie in front of it. ---- */
      var q303nv = (function(){
        var prog3 = null, U3 = {}, aPos = -1, spec = null, objs = [], fail = null, drew = 0, npts = 0;
        var I4 = new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
        function sh(type, src){
          var s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
          if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)){ fail = gl.getShaderInfoLog(s); return null; }
          return s;
        }
        function build(){
          if (prog3 || fail) return prog3;
          var vs = sh(gl.VERTEX_SHADER, NMSKNervePass.vs()), fs = sh(gl.FRAGMENT_SHADER, NMSKNervePass.fs());
          if (!vs || !fs) return null;
          prog3 = gl.createProgram(); gl.attachShader(prog3, vs); gl.attachShader(prog3, fs); gl.linkProgram(prog3);
          if (!gl.getProgramParameter(prog3, gl.LINK_STATUS)){ fail = gl.getProgramInfoLog(prog3); prog3 = null; return null; }
          ["projectionMatrix", "viewMatrix", "modelMatrix", "uC1", "uC2", "uCtr", "uFwd", "uPt", "uColor", "uAlpha"]
            .forEach(function(n){ U3[n] = gl.getUniformLocation(prog3, n); });
          aPos = gl.getAttribLocation(prog3, "position");
          return prog3;
        }
        function pass(ctx){
          drew = 0; npts = 0;
          if (!spec || !spec.on || !objs.length) return;
          if (!build()) return;
          var mm = q303mmPerPx();
          var cp = clip.on ? clipPlane() : null, cp2 = clip.on ? clipPlane2() : null;
          /* this engine's own shader DISCARDS where dot + w > 0; the shared pass KEEPS where dot + w >= 0, so the sign flips */
          var c1 = cp ? [-cp[0], -cp[1], -cp[2], -cp[3]] : [0, 0, 0, 1];
          var c2 = cp2 ? [-cp2[0], -cp2[1], -cp2[2], -cp2[3]] : [0, 0, 0, 1];
          var F = NMSKNervePass.frame(ctx.eye, cam.tgt, c1, c2), col = COL.nerve || [0.85, 0.71, 0.26];
          gl.useProgram(prog3);
          gl.uniformMatrix4fv(U3.projectionMatrix, false, ctx.mvp);
          gl.uniformMatrix4fv(U3.viewMatrix, false, I4);
          gl.uniformMatrix4fv(U3.modelMatrix, false, I4);
          gl.uniform4f(U3.uC1, F.c1[0], F.c1[1], F.c1[2], F.c1[3]);
          gl.uniform4f(U3.uC2, F.c2[0], F.c2[1], F.c2[2], F.c2[3]);
          gl.uniform3f(U3.uCtr, F.ctr[0], F.ctr[1], F.ctr[2]);
          gl.uniform3f(U3.uFwd, F.fwd[0], F.fwd[1], F.fwd[2]);
          gl.uniform3f(U3.uColor, col[0], col[1], col[2]);
          gl.uniform1f(U3.uAlpha, spec.alpha);
          gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
          gl.disable(gl.DEPTH_TEST); gl.depthMask(false);
          gl.enableVertexAttribArray(aPos);
          objs.forEach(function(o){
            if (!o.batch || !vis(o)) return;
            gl.uniform1f(U3.uPt, NMSKNervePass.width(spec.dia[o.id || o.name], mm, spec.wmin, dpr));
            gl.bindBuffer(gl.ARRAY_BUFFER, o.batch.pb);
            gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);
            gl.drawArrays(gl.POINTS, o.vOff, o.vc);
            drew++; npts += o.vc;
          });
          gl.enable(gl.DEPTH_TEST); gl.depthMask(true); gl.disable(gl.BLEND);
        }
        addonDraw.push(pass);
        return {
          apply:function(s){
            spec = s;
            objs = s ? (s.ids || []).map(function(id){ return q303byId[id]; }).filter(Boolean) : [];
            need = true;
          },
          stats:function(){ return {prog:!!prog3, fail:fail, structures:drew, points:npts, step:spec ? spec.step : 0,
                                    shader:NMSKNervePass.hash()}; }
        };
      })();
      window.__q303nv = q303nv.stats;

      NMSKQ303.start({
        anchor:canvas, history:NMSKHistory, modelreset:NMSKModelReset,
        target:{
          boxOf:function(id){ var o = q303byId[id]; return o ? {min:o.bmin, max:o.bmax} : null; },
          marks:function(){ try { return selCtl ? selCtl.state().marks : []; } catch (err){ return []; } },
          selectedId:function(){ return selected ? (selected.id || selected.name || null) : null; },
          name:function(id){ var o = q303byId[id]; return o ? (o.name || id) : id; },
          has:function(id){ return !!q303byId[id]; }
        },
        autofocus:{
          cam:{get:function(){ return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}; },
               set:function(c){ cam.az = c.az; cam.el = c.el; cam.dist = c.dist; cam.tgt = c.tgt.slice(); stopSpin(); need = true; },
               fit:q303fit, redraw:function(){ need = true; }},
          view:function(){ var e = q303eye(), t = cam.tgt; return {eye:e, dir:[t[0] - e[0], t[1] - e[1], t[2] - e[2]]}; },
          imaging:function(){ return window.NMSKImaging || null; },
          ultrasound:function(){ return window.NMSKUltrasound || null; },
          cut:function(){ return cutCtl; }, xsec:function(){ return xsecCtl; },
          style:function(){ return window.NMSKRenderStyle || null; }
        },
        fourup:{
          canvas:canvas,
          camGet:function(){ return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}; },
          camSet:function(c){ cam.az = c.az; cam.el = c.el; cam.dist = c.dist; cam.tgt = c.tgt.slice(); need = true; },
          setPanes:function(L){ q303setPanes(L); },
          redraw:function(){ need = true; }
        },
        views:{
          cam:{get:function(){ return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}; },
               set:function(c){ cam.az = c.az; cam.el = c.el; cam.dist = c.dist; cam.tgt = c.tgt.slice(); stopSpin(); need = true; },
               fit:q303fit, redraw:function(){ need = true; }},
          axesOf:function(ids){
            var P = [];
            (ids || []).forEach(function(id){ var p = q303pos(id); if (p) P.push(p); });
            return NMSKPCA.axes(P);
          },
          modelId:function(){ return (MAN.totals && MAN.totals.fit_to_vhf) ? "zan_f" : "zan_m"; }
        },
        nerves:{
          list:function(){ return OBJ.map(function(o){ return {id:o.id || o.name, cat:o.layer, name:o.name}; }); },
          apply:function(s){ q303nv.apply(s); },
          mmPerPx:q303mmPerPx,
          /* emphasis composes with the nerve system toggle rather than fighting it: it switches the nerve layers on,
             inside the same single undo step, and the control says so */
          show:function(){
            var any = false;
            ["nerve", "cns"].forEach(function(k){ if (k in on && !on[k]){ on[k] = true; if (alphaFor[k] <= 0.01) alphaFor[k] = 1; any = true; } });
            if (any){ sync(); need = true; }
            return any;
          },
          redraw:function(){ need = true; }
        }
      });
      /* Q303 verification hooks. The pixels are read back INSIDE the page right after a synchronous draw --
         page.screenshot returns a stale frame in this container (Q300's finding, re-confirmed by Q301). The arithmetic is in
         the shared NMSKPx, so the two engines measure the same thing; only the readPixels call is engine specific. */
      function q303buf(){
        draw();
        var w = canvas.width | 0, h = canvas.height | 0, buf = new Uint8Array(w * h * 4);
        gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, buf);
        return {buf:buf, w:w, h:h};
      }
      window.__q303px = function(step){ var f = q303buf(); return NMSKPx.stats(f.buf, f.w, f.h, step, COL.nerve || [0.85, 0.71, 0.26]); };
      window.__q303dbg = {
        cam:function(){ return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}; },
        view:function(){ var e = q303eye(), t = cam.tgt; return {eye:e, dir:[t[0] - e[0], t[1] - e[1], t[2] - e[2]]}; },
        list:function(){ return OBJ.map(function(o){ return {id:o.id || o.name, cat:o.layer, name:o.name}; }); },
        selectedId:function(){ return selected ? (selected.id || selected.name || null) : null; },
        deselect:function(){ select(null); return selected; },
        nudge:function(k){ k = k || 1; cam.az += 0.37 * k; cam.el += 0.11 * k; cam.dist *= (1 + 0.07 * k); stopSpin(); need = true; draw(); },
        nerveLayerOff:function(){ on.nerve = false; sync(); need = true; return true; },
        nerveLayerOn:function(){ return !!on.nerve; },
        cut:function(){ return cutCtl; }, xsec:function(){ return xsecCtl; },
        pixelsByPane:function(){ var f = q303buf(); return NMSKPx.quadrants(f.buf, f.w, f.h, 4); }
      };
