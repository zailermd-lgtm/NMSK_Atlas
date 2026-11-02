  /* ---- Q303: centring imaging on what was chosen, four panes, "facing me" + saved views, nerve emphasis ----
     Everything shareable is in viewer/q303/; this is only what this engine draws with, and it is the same shape as the
     Z engine's glue so the two behave identically. Spliced by scripts/anatomy/q303/patch_engines_q303.py.
     ONE FRAME THROUGHOUT. Every coordinate Q303 passes around is in the ENGINE'S MODEL FRAME -- which on this engine is
     root-local, the frame the clinical tools, the cut module and anatomyApi().view() already use. The camera's own
     target is a WORLD position here (frameOn() adds root.position to it), so the camera adaptor converts in both
     directions and nothing else has to think about it. */
  function q303loc(){ return root.position; }
  function q303mmPerPx(){
    var r = renderer.domElement.getBoundingClientRect();
    return 2 * dist * Math.tan(camera.fov * Math.PI / 360) / Math.max(1, r.height * q303ph());
  }
  function q303fit(rad){
    return Math.max(radius * 0.06, Math.min(radius * 12, (Math.max(0.5, rad) / Math.tan(camera.fov * Math.PI / 360)) * 1.35));
  }
  function q303box(id){
    var g = groups[id];
    if (g && g.meshes && g.meshes.length){
      var lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30];
      g.meshes.forEach(function(m){
        var b = m.geometry.boundingBox;
        if (!b){ m.geometry.computeBoundingBox(); b = m.geometry.boundingBox; }
        lo[0] = Math.min(lo[0], b.min.x); lo[1] = Math.min(lo[1], b.min.y); lo[2] = Math.min(lo[2], b.min.z);
        hi[0] = Math.max(hi[0], b.max.x); hi[1] = Math.max(hi[1], b.max.y); hi[2] = Math.max(hi[2], b.max.z);
      });
      return {min:lo, max:hi};
    }
    var m2 = byId[id];
    if (!m2) return null;
    var b2 = m2.geometry.boundingBox;
    if (!b2){ m2.geometry.computeBoundingBox(); b2 = m2.geometry.boundingBox; }
    return {min:b2.min.toArray(), max:b2.max.toArray()};
  }
  function q303cam(){
    return {az:az, el:el, dist:dist, tgt:[target.x - root.position.x, target.y - root.position.y, target.z - root.position.z]};
  }
  function q303setCam(c){
    az = c.az; el = c.el; dist = c.dist;
    target.set(c.tgt[0] + root.position.x, c.tgt[1] + root.position.y, c.tgt[2] + root.position.z);
    place();
  }
  function q303verts(id){
    var g = groups[id], out = [];
    (g && g.meshes && g.meshes.length ? g.meshes : (byId[id] ? [byId[id]] : [])).forEach(function(m){
      var p = m.geometry && m.geometry.attributes ? m.geometry.attributes.position : null;
      if (p && p.array) out.push(p.array);
    });
    return out;
  }

  /* ---- the nerve-emphasis pass. One THREE.Points twin per nerve mesh, SHARING its geometry (the pose writes into
     geometry.attributes.position in place, so the twin follows a posed body for free -- Q300's bone-pass trick), drawn
     after everything with the depth test off, from the SHARED GLSL in viewer/q303/nervepass.js. A RawShaderMaterial is
     used rather than a patch to three.js's own shader precisely so that this engine and the Z engine run the same
     arithmetic, which is the rule Q301 D3(7) set. ---- */
  var q303nv = (function(){
    var twins = [], spec = null, raf = 0, built = false, drew = 0, npts = 0;
    function mat(){
      return new THREE.RawShaderMaterial({
        vertexShader:NMSKNervePass.vs(), fragmentShader:NMSKNervePass.fs(),
        uniforms:{uC1:{value:new THREE.Vector4(0, 0, 0, 1)}, uC2:{value:new THREE.Vector4(0, 0, 0, 1)},
                  uCtr:{value:new THREE.Vector3(0, 0, 0)}, uFwd:{value:new THREE.Vector3(0, 0, -1)},
                  uPt:{value:0}, uColor:{value:new THREE.Vector3(0.85, 0.71, 0.26)}, uAlpha:{value:0}},
        transparent:true, depthTest:false, depthWrite:false
      });
    }
    function build(ids){
      if (built) return;
      built = true;
      var S = {}; (ids || []).forEach(function(i){ S[i] = 1; });
      meshes.forEach(function(m){
        var s = m.userData;
        if (!S[s.id]) return;
        var o = new THREE.Points(m.geometry, mat());
        o.frustumCulled = false; o.renderOrder = 998; o.visible = false;
        o.userData = {of:m};                      /* no `id`, so the label / pick ID passes skip it exactly as they skip Q300's bone twins */
        root.add(o); twins.push({pt:o, of:m, id:s.id});
      });
    }
    function tick(){
      raf = 0;
      if (!spec || !spec.on){ twins.forEach(function(t){ t.pt.visible = false; }); return; }
      var mm = q303mmPerPx(), d = renderer.getPixelRatio();
      var c1 = cut.on ? [cutWorld.normal.x, cutWorld.normal.y, cutWorld.normal.z, cutWorld.constant] : null;
      var c2 = cut.on ? [cutWorld2.normal.x, cutWorld2.normal.y, cutWorld2.normal.z, cutWorld2.constant] : null;
      var F = NMSKNervePass.frame(camera.position.toArray(), target.toArray(), c1, c2);
      drew = 0; npts = 0;
      twins.forEach(function(t){
        var u = t.pt.material.uniforms, live = !!t.of.visible;
        t.pt.visible = live;
        if (!live) return;
        u.uC1.value.set(F.c1[0], F.c1[1], F.c1[2], F.c1[3]);
        u.uC2.value.set(F.c2[0], F.c2[1], F.c2[2], F.c2[3]);
        u.uCtr.value.set(F.ctr[0], F.ctr[1], F.ctr[2]);
        u.uFwd.value.set(F.fwd[0], F.fwd[1], F.fwd[2]);
        u.uAlpha.value = spec.alpha;
        var col = t.of.material && t.of.material.color ? t.of.material.color : null;
        if (col) u.uColor.value.set(col.r, col.g, col.b);
        u.uPt.value = NMSKNervePass.width(spec.dia[t.id], mm, spec.wmin, d);
        drew++; npts += (t.of.geometry.attributes.position.count || 0);
      });
      draw();
      if (spec && spec.on) raf = requestAnimationFrame(tick);
    }
    return {
      apply:function(s){
        if (s && s.on) build(s.ids);
        spec = s;
        if (spec && spec.on){ if (!raf) raf = requestAnimationFrame(tick); }
        else { if (raf){ cancelAnimationFrame(raf); raf = 0; } tick(); }
      },
      stats:function(){ return {twins:twins.length, structures:drew, points:npts, step:spec ? spec.step : 0,
                                shader:NMSKNervePass.hash()}; }
    };
  })();
  window.__q303nv = q303nv.stats;

  NMSKQ303.start({
    anchor:A.canvas, history:NMSKHistory, modelreset:NMSKModelReset,
    target:{
      boxOf:q303box,
      marks:function(){ try { return selCtl ? selCtl.state().marks : []; } catch (err){ return []; } },
      selectedId:function(){ return selected || null; },
      name:function(id){ var g = groups[id]; return (g && g.name) || (byId[id] && byId[id].userData.name) || id; },
      has:function(id){ return !!(groups[id] || byId[id]); }
    },
    autofocus:{
      cam:{get:q303cam, set:function(c){ q303setCam(c); draw(); }, fit:q303fit, redraw:draw},
      view:function(){
        var e = [camera.position.x - root.position.x, camera.position.y - root.position.y, camera.position.z - root.position.z];
        var t = q303cam().tgt;
        return {eye:e, dir:[t[0] - e[0], t[1] - e[1], t[2] - e[2]]};
      },
      imaging:function(){ return window.NMSKImaging || null; },
      ultrasound:function(){ return window.NMSKUltrasound || null; },
      cut:function(){ return cutCtl; }, xsec:function(){ return xsecCtl; },
      style:function(){ return window.NMSKRenderStyle || null; }
    },
    fourup:{
      canvas:renderer.domElement,
      camGet:q303cam, camSet:function(c){ q303setCam(c); },
      setPanes:function(L){ q303setPanes(L); },
      redraw:draw
    },
    views:{
      cam:{get:q303cam, set:function(c){ q303setCam(c); draw(); }, fit:q303fit, redraw:draw},
      axesOf:function(ids){
        var P = [];
        (ids || []).forEach(function(id){ q303verts(id).forEach(function(a){ P.push(a); }); });
        return NMSKPCA.axes(P);
      },
      modelId:function(){ return A.viewerGuess || "own"; }
    },
    nerves:{
      list:function(){
        var seen = {}, out = [];
        meshes.forEach(function(m){
          var s = m.userData;
          if (seen[s.id]) return;
          seen[s.id] = 1;
          out.push({id:s.id, cat:s.cat, name:s.name || s.id});
        });
        return out;
      },
      apply:function(s){ q303nv.apply(s); },
      mmPerPx:q303mmPerPx,
      /* emphasis composes with the nerve system toggle rather than fighting it: it switches the nerve layers on,
         inside the same single undo step, and the control says so */
      show:function(){
        var any = false;
        ["nerve", "cns"].forEach(function(k){
          if (k in on && !on[k]){ on[k] = true; any = true; }
          if (sysAlpha && sysAlpha[k] != null && sysAlpha[k] <= 0.01){ sysAlpha[k] = 1; any = true; }
        });
        if (any) apply();
        return any;
      },
      redraw:draw
    }
  });
  /* Q303 verification hooks. The pixels are read back INSIDE the page right after a synchronous draw --
     page.screenshot returns a stale frame in this container (Q300's finding, re-confirmed by Q301). The arithmetic is in
     the shared NMSKPx, so the two engines measure the same thing; only the readPixels call is engine specific. */
  function q303buf(){
    draw();
    var g3 = renderer.getContext(), c3 = renderer.domElement, w = c3.width | 0, h = c3.height | 0;
    var buf = new Uint8Array(w * h * 4);
    g3.readPixels(0, 0, w, h, g3.RGBA, g3.UNSIGNED_BYTE, buf);
    return {buf:buf, w:w, h:h};
  }
  function q303nerveCol(){
    var nm = null;
    meshes.forEach(function(m){ if (!nm && m.userData.cat === "nerve") nm = m; });
    var c = nm && nm.material && nm.material.color ? nm.material.color : {r:0.85, g:0.71, b:0.26};
    return [c.r, c.g, c.b];
  }
  window.__q303px = function(step){ var f = q303buf(); return NMSKPx.stats(f.buf, f.w, f.h, step, q303nerveCol()); };
  window.__q303dbg = {
    cam:q303cam,
    view:function(){
      var e = [camera.position.x - root.position.x, camera.position.y - root.position.y, camera.position.z - root.position.z];
      var t = q303cam().tgt;
      return {eye:e, dir:[t[0] - e[0], t[1] - e[1], t[2] - e[2]]};
    },
    list:function(){
      var seen = {}, out = [];
      meshes.forEach(function(m){ var s = m.userData; if (seen[s.id]) return; seen[s.id] = 1; out.push({id:s.id, cat:s.cat, name:s.name || s.id}); });
      return out;
    },
    selectedId:function(){ return selected || null; },
    deselect:function(){ select(null); return selected; },
    nudge:function(k){ k = k || 1; az += 0.37 * k; el += 0.11 * k; dist *= (1 + 0.07 * k); place(); draw(); },
    nerveLayerOff:function(){ on.nerve = false; apply(); return true; },
    nerveLayerOn:function(){ return !!on.nerve; },
    cut:function(){ return cutCtl; }, xsec:function(){ return xsecCtl; },
    pixelsByPane:function(){ var f = q303buf(); return NMSKPx.quadrants(f.buf, f.w, f.h, 4); }
  };
