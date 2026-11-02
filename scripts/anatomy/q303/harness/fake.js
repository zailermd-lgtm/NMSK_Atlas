/* Q303 Phase 1 harness: a FAKE host with fake providers, so every shared module is exercised in a real browser before
   either template is touched -- the method Q300 used ("that harness is what first proved the round"). Nothing here ships. */
(function(){
  "use strict";
  var R = Math.random;
  function rod(axis, len, rad, n, c){           /* a tube: points on a cylinder about `axis` */
    var out = new Float32Array(n * 3), u = axis === "y" ? [0,1,0] : axis === "x" ? [1,0,0] : [0,0,1];
    var p = axis === "y" ? [1,0,0] : [0,1,0], q = [u[1]*p[2]-u[2]*p[1], u[2]*p[0]-u[0]*p[2], u[0]*p[1]-u[1]*p[0]];
    for (var i = 0; i < n; i++){
      var t = (i / (n - 1) - 0.5) * len, a = (i * 2.399963) % (Math.PI * 2);
      for (var k = 0; k < 3; k++) out[i*3+k] = c[k] + u[k]*t + (p[k]*Math.cos(a) + q[k]*Math.sin(a)) * rad;
    }
    return out;
  }
  function sheet(nx, ny, w, h, th, c){          /* a flat plate in the XY plane: its minor axis is +Z = its normal */
    var out = new Float32Array(nx * ny * 2 * 3), i = 0;
    for (var a = 0; a < nx; a++) for (var b = 0; b < ny; b++) for (var s = 0; s < 2; s++){
      out[i++] = c[0] + (a/(nx-1) - 0.5) * w;
      out[i++] = c[1] + (b/(ny-1) - 0.5) * h;
      out[i++] = c[2] + (s ? th/2 : -th/2);
    }
    return out;
  }
  function blob(n, rad, c){
    var out = new Float32Array(n * 3);
    for (var i = 0; i < n; i++){
      var z = 2*((i*0.618033)%1) - 1, ph = i * 2.399963, r = Math.sqrt(Math.max(0, 1 - z*z));
      out[i*3] = c[0] + rad*r*Math.cos(ph); out[i*3+1] = c[1] + rad*0.8*z; out[i*3+2] = c[2] + rad*r*Math.sin(ph);
    }
    return out;
  }
  var S = [
    {id:"sciatic_n_r", name:"Sciatic nerve (right)", cat:"nerve", pos:rod("y", 420, 3.9, 900, [55, 620, -10])},
    {id:"tibial_n_r", name:"Tibial nerve (right)", cat:"nerve", pos:rod("y", 300, 1.0, 600, [52, 330, -14])},
    {id:"sural_n_r", name:"Sural nerve (right)", cat:"nerve", pos:rod("y", 180, 0.25, 300, [62, 250, -30])},
    {id:"median_n_r", name:"Median nerve (right)", cat:"nerve", pos:rod("y", 360, 1.4, 500, [170, 980, 10])},
    {id:"accessory_n_r", name:"Accessory nerve (right)", cat:"nerve", pos:rod("y", 120, 0.7, 200, [40, 1420, -5])},
    {id:"spinal_cord", name:"Spinal cord", cat:"cns", pos:rod("y", 500, 7, 700, [0, 1050, -35])},
    {id:"fascia_lata_r", name:"Fascia lata (right)", cat:"fascia", pos:sheet(22, 30, 140, 380, 1.0, [78, 640, 40])},
    {id:"femur_r", name:"Femur (right)", cat:"bone", pos:rod("y", 430, 14, 800, [60, 620, 0])},
    {id:"gluteus_maximus_r", name:"Gluteus maximus (right)", cat:"muscle", pos:blob(700, 85, [70, 880, -45])},
    {id:"tibia_r", name:"Tibia (right)", cat:"bone", pos:rod("y", 390, 11, 700, [55, 250, 0])},
    {id:"skin", name:"Skin", cat:"skin", pos:blob(900, 250, [0, 850, 0])},
    {id:"iliac_a_r", name:"External iliac artery (right)", cat:"vessel", pos:rod("y", 120, 4, 200, [48, 1010, 25])}
  ];
  var byId = {};
  S.forEach(function(s){
    var lo = [1e30,1e30,1e30], hi = [-1e30,-1e30,-1e30];
    for (var i = 0; i + 2 < s.pos.length; i += 3) for (var k = 0; k < 3; k++){
      var v = s.pos[i+k]; if (v < lo[k]) lo[k] = v; if (v > hi[k]) hi[k] = v;
    }
    s.bmin = lo; s.bmax = hi; byId[s.id] = s;
  });

  /* ---- the fake engine ---- */
  var cam = {az:0.38, el:0.12, dist:1800, tgt:[0, 850, 0]};
  var marks = [], selected = null, panes = null, draws = 0, nerveSpec = null, nerveShown = 0;
  var catOn = {nerve:true, cns:true, bone:true, muscle:true, fascia:true, skin:true, vessel:true};
  function eye(){ var ce = Math.cos(cam.el); return [cam.tgt[0] + cam.dist*ce*Math.sin(cam.az), cam.tgt[1] + cam.dist*Math.sin(cam.el), cam.tgt[2] + cam.dist*ce*Math.cos(cam.az)]; }
  function fit(rad){ return Math.max(40, Math.min(14000, (Math.max(0.5, rad) / Math.tan(0.425)) * 1.35)); }
  function ph(){ var p = panes && panes.length ? panes[0] : null; return p ? p.h : 1; }
  function mmPerPx(){ var r = document.getElementById("cv").getBoundingClientRect(); return 2*cam.dist*Math.tan(0.425)/Math.max(1, r.height*ph()); }

  /* fake CT / MR panes */
  var IMG = {open:false, P:[0, 900, 0], CP:{ax:{CP:[1,1,1]}, co:{CP:[2,2,2]}, sa:{CP:null}, cut:{CP:null}}};
  window.NMSKImaging = {
    open:function(){ IMG.open = true; }, close:function(){ IMG.open = false; },
    state:function(){ return {open:IMG.open, P:IMG.P.slice()}; },
    set:function(p){ if (p.P) IMG.P = p.P.slice(); },
    views:function(){ return IMG.CP; }
  };
  /* fake ultrasound: the skin is the sphere of the "skin" structure */
  var US = {open:false, P:[0, 900, 250], N:[0, 0, 1]};
  /* the skin is a body-shaped envelope, not a ball: a vertical cylinder of radius 250 from y = 60 to y = 1740, so a ray
     through ANY structure of this fake body really meets it -- a ball centred on the trunk missed the leg entirely,
     which is how this harness found the probe-placement fallback the first draft got wrong. */
  var SKIN = {r:250, y0:60, y1:1740};
  function skinHit(o, d){
    var best = null;
    var a = d[0]*d[0] + d[2]*d[2], b = o[0]*d[0] + o[2]*d[2], c = o[0]*o[0] + o[2]*o[2] - SKIN.r*SKIN.r;
    if (a > 1e-9){
      var disc = b*b - a*c;
      if (disc >= 0){
        var sd = Math.sqrt(disc);
        [(-b - sd)/a, (-b + sd)/a].forEach(function(t){
          if (t < 0) return;
          var y = o[1] + d[1]*t;
          if (y < SKIN.y0 || y > SKIN.y1) return;
          if (best == null || t < best) best = t;
        });
      }
    }
    [SKIN.y0, SKIN.y1].forEach(function(yc){            /* the flat caps */
      if (Math.abs(d[1]) < 1e-9) return;
      var t = (yc - o[1]) / d[1];
      if (t < 0) return;
      var x = o[0] + d[0]*t, z = o[2] + d[2]*t;
      if (x*x + z*z > SKIN.r*SKIN.r) return;
      if (best == null || t < best) best = t;
    });
    if (best == null) return null;
    return [o[0]+d[0]*best, o[1]+d[1]*best, o[2]+d[2]*best];
  }
  window.__skin = SKIN;
  window.NMSKUltrasound = {
    open:function(){ US.open = true; }, close:function(){ US.open = false; },
    isOpen:function(){ return US.open; },
    state:function(){ return {open:US.open, P:US.P.slice(), N:US.N.slice()}; },
    set:function(p){ if (p.P) US.P = p.P.slice(); if (p.N) US.N = p.N.slice(); },
    placeRay:function(o, d){
      var l = Math.hypot(d[0], d[1], d[2]) || 1, u = [d[0]/l, d[1]/l, d[2]/l], h = skinHit(o, u);
      if (!h) return null;
      var rr = Math.hypot(h[0], h[2]) || 1;
      US.P = h; US.N = [h[0]/rr, 0, h[2]/rr];
      return {P:US.P.slice(), N:US.N.slice(), struct:"skin"};
    }
  };
  /* fake cut plane: n0 = +X, a = the offset along it */
  var CUT = {on:false, ori:"x", n0:[1,0,0], a:0, a0:0, th:0, lo:-400, hi:400};
  window.__fakeCut = {
    enter:function(){ CUT.on = true; }, exit:function(){ CUT.on = false; },
    snapshot:function(){ return {on:CUT.on, ori:CUT.ori, n0:CUT.n0.slice(), a:CUT.a, a0:CUT.a0, th:CUT.th}; },
    restore:function(o){ CUT.on = !!o.on; CUT.ori = o.ori; CUT.n0 = o.n0.slice(); CUT.a0 = o.a0;
      CUT.a = Math.max(CUT.lo, Math.min(CUT.hi, +o.a || 0)); CUT.th = o.th || 0; },
    state:function(){ return {on:CUT.on, ori:CUT.ori, n0:CUT.n0.slice(), a:CUT.a, a0:CUT.a0, offset:CUT.a - CUT.a0, th:CUT.th}; }
  };
  /* fake cross-section stack */
  var XS = {on:false, mode:"plane", part:null};
  window.__fakeXsec = {
    isOn:function(){ return XS.on; }, set:function(v){ XS.on = !!v; },
    setMode:function(m){ XS.mode = m; }, setPart:function(ids){ XS.part = (ids || []).slice(); },
    state:function(){ return {on:XS.on, mode:XS.mode, part:XS.part ? XS.part.slice() : null}; }
  };
  /* fake render style */
  var RS = {mode:"colour"};
  window.NMSKRenderStyle = {
    state:function(){ return {on:true, mode:RS.mode}; }, mode:function(){ return RS.mode; },
    set:function(m){ RS.mode = m; }
  };

  /* ---- the list, so the Q298 "picked a search result" path is real ---- */
  var listBox = document.getElementById("list");
  S.forEach(function(s){
    var r = document.createElement("div");
    r.className = "row"; r.setAttribute("data-id", s.id); r.textContent = s.name;
    r.addEventListener("click", function(){ selected = s.id; });
    listBox.appendChild(r);
  });

  var cv = document.getElementById("cv");
  window.__h = {
    structures:function(){ return S.map(function(s){ return {id:s.id, cat:s.cat, name:s.name, bmin:s.bmin, bmax:s.bmax, nv:s.pos.length/3}; }); },
    cam:function(){ return JSON.parse(JSON.stringify(cam)); },
    setCam:function(c){ cam = JSON.parse(JSON.stringify(c)); },
    eye:eye,
    mark:function(ids){ marks = (ids || []).slice(); },
    marks:function(){ return marks.slice(); },
    select:function(id){ selected = id; },
    selected:function(){ return selected; },
    panes:function(){ return panes ? JSON.parse(JSON.stringify(panes)) : null; },
    draws:function(){ return draws; },
    img:function(){ return {open:IMG.open, P:IMG.P.slice(), CP:Object.keys(IMG.CP).map(function(k){ return [k, IMG.CP[k].CP]; })}; },
    us:function(){ return {open:US.open, P:US.P.slice(), N:US.N.slice()}; },
    cut:function(){ return window.__fakeCut.state(); },
    xsec:function(){ return window.__fakeXsec.state(); },
    style:function(){ return RS.mode; },
    nerveSpec:function(){ return nerveSpec ? JSON.parse(JSON.stringify({on:nerveSpec.on, wmin:nerveSpec.wmin, alpha:nerveSpec.alpha, step:nerveSpec.step, n:nerveSpec.ids.length, formula:nerveSpec.formula})) : null; },
    nerveShown:function(){ return nerveShown; },
    catOn:function(){ return JSON.parse(JSON.stringify(catOn)); },
    setCatOn:function(k, v){ catOn[k] = !!v; },
    mmPerPx:mmPerPx,
    canvasRect:function(){ var r = cv.getBoundingClientRect(); return {left:r.left, top:r.top, width:r.width, height:r.height}; }
  };

  /* ---- boot the real modules exactly as a template's glue does ---- */
  NMSKTips.start ? NMSKTips.start() : null;
  NMSKHistory.start({anchor:cv, resetView:function(){ cam = {az:0.38, el:0.12, dist:1800, tgt:[0, 850, 0]}; }});
  NMSKShowAll.start({sources:[]});
  NMSKModelReset.start({history:NMSKHistory, resetView:function(){ cam = {az:0.38, el:0.12, dist:1800, tgt:[0, 850, 0]}; }});
  NMSKCombos.start({probes:[
    {key:"measure", label:"Measure", active:function(){ return !!window.__fakeMeasure; }},
    {key:"imaging", label:"Imaging style", active:function(){ return RS.mode !== "colour"; }},
    {key:"cut", label:"Cut", active:function(){ return CUT.on; }},
    {key:"peel", label:"Depth peel", active:function(){ return false; }},
    {key:"spin", label:"Spin", active:function(){ return false; }}
  ]});
  NMSKInfo.start({anchor:cv});
  NMSKGroups.start({anchor:cv, history:NMSKHistory, combos:NMSKCombos, info:NMSKInfo, modelreset:NMSKModelReset,
    groups:[{key:"view", label:"View", members:[{adopt:"t-reset"}]},
            {key:"imaging", label:"Imaging", members:[{adopt:"t-mode"}]}]});

  NMSKQ303.start({
    anchor:cv, history:NMSKHistory, modelreset:NMSKModelReset,
    target:{
      boxOf:function(id){ var s = byId[id]; return s ? {min:s.bmin, max:s.bmax} : null; },
      marks:function(){ return marks.slice(); },
      selectedId:function(){ return selected; },
      name:function(id){ return byId[id] ? byId[id].name : id; },
      has:function(id){ return !!byId[id]; }
    },
    autofocus:{
      cam:{get:function(){ return JSON.parse(JSON.stringify(cam)); },
           set:function(c){ cam = {az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice()}; },
           fit:fit, redraw:function(){ draws++; }},
      view:function(){ var e = eye(), t = cam.tgt; return {eye:e, dir:[t[0]-e[0], t[1]-e[1], t[2]-e[2]]}; },
      imaging:function(){ return window.NMSKImaging; },
      ultrasound:function(){ return window.NMSKUltrasound; },
      cut:function(){ return window.__fakeCut; }, xsec:function(){ return window.__fakeXsec; },
      style:function(){ return window.NMSKRenderStyle; }
    },
    fourup:{
      canvas:cv,
      camGet:function(){ return JSON.parse(JSON.stringify(cam)); },
      camSet:function(c){ cam = {az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice()}; },
      setPanes:function(L){ panes = L ? JSON.parse(JSON.stringify(L)) : null; },
      redraw:function(){ draws++; }
    },
    views:{
      cam:{get:function(){ return JSON.parse(JSON.stringify(cam)); },
           set:function(c){ cam = {az:c.az, el:c.el, dist:c.dist, tgt:c.tgt.slice()}; },
           fit:fit, redraw:function(){ draws++; }},
      axesOf:function(ids){ var P = []; (ids || []).forEach(function(id){ if (byId[id]) P.push(byId[id].pos); }); return NMSKPCA.axes(P); },
      modelId:function(){ return "harness"; }
    },
    nerves:{
      list:function(){ return S.map(function(s){ return {id:s.id, cat:s.cat, name:s.name}; }); },
      apply:function(sp){ nerveSpec = sp; nerveShown = sp ? sp.ids.length : 0; },
      mmPerPx:mmPerPx,
      show:function(){ var any = false; ["nerve", "cns"].forEach(function(k){ if (!catOn[k]){ catOn[k] = true; any = true; } }); return any; },
      redraw:function(){ draws++; }
    }
  });
  window.__ready = true;
})();
