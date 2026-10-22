/* The sourced PARTS of a structure (Q220, on the Q219 parts model): a Parts list in the structure card and point markers on the model.
   Data = the page's sidecar parts_data.json (public anatomy layer), fetched with a graceful fallback: absent or invalid = no Parts section,
   no toggle, nothing else changes. Engine adaptor E: url, canvasRect(), project(p)->[x,y,z,w] clip coords, cut()->null|{kn,c,th} (the kept
   part is 0 <= kn.p + c <= th, th = 0 = no far face), meshVisible(id), focusAt(p), redraw(), setDots(list) (engine-drawn, depth-tested
   dots), toolbar + toolClass (host of the "Parts markers" toggle), onLoaded().
   A marker is a position derived by a stated rule on THIS model (rule-based) or the place of a Z-Anatomy mesh (Z-fill): always shown
   with its source class and error bound, never as measured. Q256: these dots are what the project elsewhere calls "not valid / needs
   checking" indicators, so the whole marker layer is OFF by default (opt-in only, same convention as Labels Q236) and is never drawn
   in the normal, unopened-panel display; turning it on (the "Parts markers" toolbar button -> panel) is what makes markers appear for
   the selected structure, or for every placed part. When on, they follow Cut mode (incl. the slice thickness), the layer / hide / isolate
   state of their structure, and x-ray (the solid dot is depth-tested by the engine: hidden behind opaque tissue, seen through x-ray; the
   hollow ring + label stay).
   Q240 view-dependent culling (optional adaptor members idImage(all,w) -> {w,h,ids}, depthImage(w) -> {w,h,z} (linear view depth in mm, 0 = empty, row 0 = top),
   idOf(meshId) -> index+1 as in idImage, marked(), and the hover(meshId) / dirty() calls from the engine): Markers = Off (default) / Visible + near / Selected only / All.
   In "Visible + near" a marker is drawn only when (1) its 3D point is not hidden by other opaque tissue (depth image: its view depth within a tolerance of the
   nearest surface at its pixel, or the surface there is one of its own structures), (2) it lies within the depth band (front N % of the visible model depth, slider) and
   (3) the Cut mode keeps it. Markers of selected / marked / hovered structures are exempt (drawn see-through, dashed ring + halo, when hidden or far) unless
   "Show hidden ones of selected muscles" is off. The depth / ID images are low resolution and throttled (camera settle + a low rate while orbiting). */
function NMSKParts(E){
  "use strict";
  var D = null, M = [], sel = null, focusI = -1, hoverI = -1, pinI = -1, hoverMesh = null;
  var btn = null, layer = null, card = null, errEl = null, panel = null, panelBuilt = false;
  var KEY = "nmsk.parts.v1", MODES = {off:1, near:1, sel:1, all:1}, CARRIER_ALLOW = 45;
  var canCull = !!(E.depthImage && E.idOf);
  var P = {mode:"off", band:55, hid:true};              // Q256: opt-in, not seen in the normal display until the user turns it on
  try { var rs = JSON.parse(localStorage.getItem(KEY) || "null");
    if (rs && typeof rs === "object"){ if (MODES[rs.mode] && (canCull || rs.mode !== "near")) P.mode = rs.mode; var bn = Number(rs.band); if (isFinite(bn)) P.band = Math.max(10, Math.min(100, Math.round(bn))); if (typeof rs.hid === "boolean") P.hid = rs.hid; } } catch (err){}
  function persist(){ try { localStorage.setItem(KEY, JSON.stringify(P)); } catch (err){} }
  var cull = {fails:0, cand:-1, sig:"", last:0, ms:0, n:0, avg:0, timer:0, dirty:true, img:null, near:0, far:0, cnt:{shown:0, occ:0, far:0, behind:0}};
  var DOT = {rule_based:[0.91, 0.63, 0.09], z_fill:[0.18, 0.56, 0.88]};
  var CLS = {rule_based:"Rule-based", z_fill:"Z-Anatomy fill"};
  var TYPES = {head_belly:"head", origin_part:"origin", insertion_point:"insertion", ligament_component:"ligament component",
               muscle_tendon_junction:"MTJ", fascial_passage:"fascial passage"};
  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  function mmTxt(v){ return Number(v).toFixed(1).replace(/\.0$/, ""); }

  /* ---------- data ---------- */
  function refsHtml(keys){
    return (keys || []).map(function(k){
      var r = D.refs[k]; if (!r) return "";
      var s = '<span class="pm-ref">' + esc(r.t);
      if (r.pmid) s += ' <a href="https://pubmed.ncbi.nlm.nih.gov/' + esc(r.pmid) + '/" target="_blank" rel="noopener">PMID ' + esc(r.pmid) + '</a>';
      if (r.doi) s += ' <a href="https://doi.org/' + esc(encodeURI(r.doi)) + '" target="_blank" rel="noopener">DOI</a>';
      return s + '</span>';
    }).join("");
  }
  function setsHtml(list){
    var seen = {}, out = "";
    list.forEach(function(pi){
      var sid = D.parts[pi].set, st = sid && D.sets[sid];
      if (!st || seen[sid] || st.counts.length < 2) return;
      seen[sid] = 1;
      out += '<p class="pm-set"><b>Sources disagree on the count.</b> ' + esc(st.n) + ': ' +
        st.counts.map(function(c){ return '<b>' + esc(c.n) + '</b> (' + esc(c.by.join(", ")) + ')'; }).join(" / ") + '.' +
        (st.note ? '<details><summary>about this count</summary>' + esc(st.note) + '</details>' : "") + '</p>';
    });
    return out;
  }
  function reasonFor(pi){
    var id = D.parts[pi].id;
    return (D.text_only && D.text_only[id]) || (D.partial && D.partial[id]) || "";
  }
  function placedFor(pi){
    return M.filter(function(mk){ return mk.pi === pi && (!sel || sel.s === "m" || mk.s === sel.s); });
  }

  /* ---------- selection and the card section ---------- */
  function select(meshId){
    sel = null; focusI = -1; closeCard(); cull.dirty = true;
    var e = D && meshId && D.mesh_parts[meshId];
    if (e){ var set = {}; e.p.forEach(function(i){ set[i] = true; }); sel = {mesh:meshId, s:e.s, list:e.p.slice(), set:set}; }
  }
  function cardHtml(){
    if (!D || !sel) return "";
    var n = sel.list.length, unv = sel.list.filter(function(i){ return D.parts[i].u; }).length;
    var h = '<div class="pm-sec" data-pm-mesh="' + esc(sel.mesh) + '"><details open><summary><span class="pm-eb">Parts</span><span class="pm-n">' + n + (n === 1 ? " part" : " parts") +
      (unv ? " &middot; " + unv + " unverified" : "") + '</span></summary>' +
      '<p class="pm-top">Each row cites its source. Click a row to find its marker on the model; markers are positions derived on this model (rule-based or Z-Anatomy fill), shown with their error bound &mdash; not measurements.</p>' +
      setsHtml(sel.list) + '<div class="pm-list">';
    sel.list.forEach(function(pi){
      var p = D.parts[pi], pl = placedFor(pi).length > 0;
      h += '<div class="pm-row" data-pi="' + pi + '" tabindex="0" role="button" aria-label="' + esc(p.n) + (pl ? ", has a marker on the model" : ", text only") + '">' +
        '<div class="pm-r1"><span class="pm-ty pm-ty-' + esc(p.ty) + '">' + esc(TYPES[p.ty] || p.ty) + '</span><span class="pm-nm">' + esc(p.n) + '</span>' +
        (p.u ? '<span class="pm-unv" title="Textbook or owner statement only; the page was not checked against a primary source">unverified</span>' : "") +
        (pl ? '<span class="pm-pl" title="This part has a placed marker on this model">marker</span>' : "") + '</div>' +
        (p.d ? '<div class="pm-d">' + esc(p.d) + '</div>' : "");
      var meta = [];
      if (p.an) meta.push("Anchor: " + esc(p.an.bone || "") + (p.an.landmark ? ", " + esc(p.an.landmark) : ""));
      if (p.var) meta.push("Reported in: " + esc(p.var));
      if (p.ev) meta.push("Evidence: " + esc(p.ev));
      if (p.pass) meta.push("Passes: " + esc(p.pass.traversing_text || p.pass.kind || "") + (p.pass.through ? " through " + esc(p.pass.through) : ""));
      if (meta.length) h += '<div class="pm-meta">' + meta.join(" &middot; ") + '</div>';
      h += '<div class="pm-c">' + refsHtml(p.r) + '</div>';
      if (p.u && p.note) h += '<div class="pm-un">' + esc(p.note) + '</div>';
      h += '<div class="pm-msg" aria-live="polite"></div></div>';
    });
    return h + '</div></details></div>';
  }
  function bind(root){
    var sec = root && root.querySelector(".pm-sec");
    if (!sec) return;
    sec.addEventListener("click", function(e){
      if (e.target.closest("a, summary")) return;
      var row = e.target.closest(".pm-row"); if (row) rowClick(+row.getAttribute("data-pi"), row);
    });
    sec.addEventListener("keydown", function(e){
      if (e.key !== "Enter" && e.key !== " ") return;
      var row = e.target.closest(".pm-row"); if (row && e.target === row){ e.preventDefault(); rowClick(+row.getAttribute("data-pi"), row); }
    });
  }
  function rowClick(pi, row){
    var msg = row.querySelector(".pm-msg");
    Array.prototype.forEach.call(row.parentNode.querySelectorAll(".pm-row"), function(r){ r.classList.toggle("pm-on", r === row); });
    var ms = placedFor(pi);
    if (!ms.length){
      focusI = -1; closeCard();
      var why = reasonFor(pi);
      msg.className = "pm-msg pm-t";
      msg.textContent = "text only (no placement)" + (why ? " — " + why : "");
      E.redraw(); return;
    }
    var mk = ms[0];
    focusI = mk.j; update();
    if (!mk.vis){
      msg.className = "pm-msg pm-t";
      msg.textContent = mk.why === "cut" ? "Marker placed, but cut away at the moment (move or reset the cut)." : "Marker placed, but its structure is hidden at the moment.";
      E.redraw(); return;
    }
    msg.className = "pm-msg"; msg.textContent = "";
    E.focusAt(mk.xyz); openCard(mk.j, true); E.redraw();
  }

  /* ---------- markers ---------- */
  function kept(p){
    var c = E.cut(); if (!c) return true;
    var d = c.kn[0] * p[0] + c.kn[1] * p[1] + c.kn[2] * p[2] + c.c;
    return d >= -1e-6 && (!(c.th > 0) || d <= c.th + 1e-6);
  }
  function inSel(mk){ return !!sel && sel.set[mk.pi] === true && (sel.s === "m" || mk.s === sel.s); }
  function carriersVisible(mk){
    for (var i = 0; i < mk.car.length; i++) if (E.meshVisible(mk.car[i])) return true;
    return false;
  }
  /* the structures whose markers are always shown: selected, marked (Selection layer), hovered. Key = part index + side. */
  var fSig = "", fKeys = {};
  function forcedMap(){
    if (!D) return fKeys;
    var marks = E.marked ? (E.marked() || []) : [];
    var sig = (sel ? sel.mesh : "") + "|" + (hoverMesh || "") + "|" + marks.length + ":" + (marks.length ? marks[0] + "," + marks[marks.length - 1] : "");
    if (sig === fSig) return fKeys;
    fSig = sig; fKeys = {};
    var ids = []; if (sel) ids.push(sel.mesh); if (hoverMesh) ids.push(hoverMesh); marks.forEach(function(m){ ids.push(m); });
    ids.forEach(function(id){
      var e = D.mesh_parts[id]; if (!e) return;
      e.p.forEach(function(pi){ if (e.s === "m"){ fKeys[pi + "|r"] = fKeys[pi + "|l"] = fKeys[pi + "|m"] = 1; } else fKeys[pi + "|" + e.s] = 1; });
    });
    return fKeys;
  }
  /* called by the engine before it renders: decides which markers are drawn and hands the solid dots over */
  function update(){
    if (!D || !M.length) return;
    var dots = [], fk = forcedMap(), cn = {shown:0, occ:0, far:0, behind:0}, culling = canCull && P.mode !== "off", cand = 0;
    M.forEach(function(mk){
      var why = "", pinned = mk.j === focusI || mk.j === pinI, byTissue = fk[mk.pi + "|" + mk.s] === 1, c = culling ? mk.cull | 0 : 0;
      var want = P.mode === "near" || P.mode === "all" || pinned || (P.mode === "sel" && byTissue);
      mk.behind = false;
      if (!want) why = "off";
      else if (!kept(mk.xyz)) why = "cut";
      else if (!carriersVisible(mk)) why = "hidden";
      else { cand++; }
      if (why === "" && c){
        if (pinned || (byTissue && P.hid)) mk.behind = (c & 1) === 1;
        else if (P.mode === "all") mk.behind = (c & 1) === 1;
        else why = (c & 1) ? "occ" : "far";
      }
      mk.vis = why === ""; mk.why = why; mk.forced = byTissue || pinned;
      if (mk.vis){ cn.shown++; if (mk.behind) cn.behind++; dots.push({p:mk.xyz, c:DOT[mk.c] || DOT.rule_based, big:mk.j === focusI || mk.j === hoverI || mk.j === pinI}); }
      else if (why === "occ") cn.occ++; else if (why === "far") cn.far++;
    });
    cull.cnt = cn; cull.cand = cand;
    E.setDots(dots);
  }
  /* ---------- view-dependent culling (Q240) ---------- */
  function nowMs(){ return (typeof performance !== "undefined" && performance.now) ? performance.now() : Date.now(); }
  function viewSig(){
    var r = E.canvasRect(), s = Math.round(r.width) + "," + Math.round(r.height);
    [[0,0,0],[1000,0,0],[0,1000,0],[0,0,1000]].forEach(function(p){ var q = E.project(p); s += "|" + q[0].toFixed(3) + "," + q[1].toFixed(3) + "," + q[2].toFixed(3) + "," + q[3].toFixed(2); });
    var c = E.cut(); if (c) s += "|c" + c.kn.map(function(v){ return v.toFixed(4); }).join(",") + "," + c.c.toFixed(2) + "," + (c.th || 0);
    return s;
  }
  function needCull(){ return canCull && !!D && M.length > 0 && P.mode !== "off" && !(P.mode === "sel" && !P.hid) && cull.cand !== 0; }        // no marker passes the cut / layer checks: no image needed
  function capture(sig){
    var t0 = nowMs(), r = E.canvasRect(), bw = Math.max(240, Math.min(560, Math.round(r.width * 0.5)));
    var zb = null;
    try { zb = E.depthImage(bw); } catch (err){ zb = null; }
    cull.img = zb && zb.z ? {w:zb.w, h:zb.h, z:zb.z, ids:null} : null;
    if (!cull.img && ++cull.fails >= 2){ canCull = false; if (P.mode === "near") P.mode = "sel"; syncPanel(); }        // this GPU gives no depth pass (the Z engine needs highp): behave as before Q240
    if (cull.img){
      var z = cull.img.z, lo = Infinity, hi = 0;
      for (var i = 0; i < z.length; i++){ var v = z[i]; if (v > 0){ if (v < lo) lo = v; if (v > hi) hi = v; } }
      cull.near = lo === Infinity ? 0 : lo; cull.far = hi;
      decide();
      /* the ID image (a second pass) only when a marker sits just behind a surface (within CARRIER_ALLOW), where "that surface is the marker's own muscle / tendon" can save it */
      if (E.idImage && M.some(function(mk){ return mk.rescue; })){
        var ib = null;
        try { ib = E.idImage(false, bw); } catch (err){ ib = null; }
        if (ib && ib.ids && ib.w === zb.w && ib.h === zb.h){ cull.img.ids = ib.ids; cull.idPass = (cull.idPass | 0) + 1; decide(); }
      }
    }
    cull.sig = sig; cull.dirty = false; cull.last = nowMs(); cull.ms = cull.last - t0; cull.n++; cull.avg += (cull.ms - cull.avg) / Math.min(cull.n, 8);
  }
  function visKey(){ var k = ""; M.forEach(function(mk){ k += mk.vis ? (mk.behind ? "b" : "v") : "-"; }); return k; }
  /* per marker: 1 = hidden behind other tissue, 2 = outside the depth band (farther than front N % of the visible model depth), 3 = both */
  function decide(){
    var im = cull.img, changed = false, bandFar = (P.band < 100 && cull.far > cull.near) ? cull.near + (cull.far - cull.near) * P.band / 100 : Infinity;
    M.forEach(function(mk){
      var c = 0;
      if (im){
        var q = E.project(mk.xyz), dm = q[3];
        if (dm > 0){
          var u = Math.floor((q[0] / dm * 0.5 + 0.5) * im.w), v = Math.floor((0.5 - 0.5 * q[1] / dm) * im.h);
          if (u >= 0 && v >= 0 && u < im.w && v < im.h){
            if (!mk.cid) mk.cid = (mk.car || []).map(function(id){ return E.idOf(id); }).filter(function(k){ return k > 0; });
            var zmin = Infinity, zc = Infinity, x0 = Math.max(0, u - 1), x1 = Math.min(im.w - 1, u + 1), y0 = Math.max(0, v - 1), y1 = Math.min(im.h - 1, v + 1);
            for (var yy = y0; yy <= y1; yy++) for (var xx = x0; xx <= x1; xx++){
              var o = yy * im.w + xx, zz = im.z[o];
              if (zz > 0){ if (zz < zmin) zmin = zz; if (im.ids && zz < zc && mk.cid.indexOf(im.ids[o]) >= 0) zc = zz; }
            }
            mk.dm = dm; mk.zmin = zmin;
            mk.rescue = false;
            if (zmin < Infinity){
              var ok = dm <= zmin + Math.max(6, 0.012 * dm);
              if (!ok && zc < Infinity) ok = dm <= zc + CARRIER_ALLOW;        // the marker lies under the surface of its own muscle / tendon (centre of a part mesh, bone under an insertion)
              if (!ok){ c |= 1; mk.rescue = !im.ids && mk.cid.length > 0 && dm <= zmin + CARRIER_ALLOW; }
            }
          }
          if (dm > bandFar) c |= 2;
        } else c |= 2;
      }
      if ((mk.cull | 0) !== c){ mk.cull = c; changed = true; }
    });
    return changed;
  }
  function cullStep(){        /* in overlay(), after the engine rendered: take a new depth / ID image when the view changed (throttled) */
    if (!needCull()) return;
    var sig = viewSig();
    if (sig === cull.sig && !cull.dirty) return;
    var t = nowMs(), gap = Math.max(170, Math.min(6000, cull.avg * 6));          // like the labels' ID pass: about 1/7 of the time at most, 0.17 - 6 s
    if (t - cull.last < gap){
      if (!cull.timer) cull.timer = setTimeout(function(){ cull.timer = 0; E.redraw(); }, gap - (t - cull.last) + 5);
      return;
    }
    var before = visKey();
    capture(sig); update();
    if (visKey() !== before) E.redraw();          // the solid dots are drawn by the engine: only a changed set needs another frame
  }
  function setBand(v){ P.band = Math.max(10, Math.min(100, Math.round(Number(v) || 55))); persist(); if (cull.img) decide(); syncPanel(); E.redraw(); }

  /* called by the engine after it rendered: positions of the rings / labels / card */
  function overlay(){
    if (!D || !layer || !M.length) return;
    cullStep();
    var r = E.canvasRect();
    layer.style.clipPath = "inset(" + Math.max(0, r.top) + "px " + Math.max(0, document.documentElement.clientWidth - r.right) + "px " +
      Math.max(0, document.documentElement.clientHeight - r.bottom) + "px " + Math.max(0, r.left) + "px)";
    var act = pinI >= 0 ? pinI : (hoverI >= 0 ? hoverI : focusI);
    M.forEach(function(mk){
      var q = mk.vis ? E.project(mk.xyz) : null;
      var ok = !!q && q[3] > 0;
      if (ok){
        mk.sx = r.left + (q[0] / q[3] * 0.5 + 0.5) * r.width; mk.sy = r.top + (0.5 - 0.5 * q[1] / q[3]) * r.height;
        ok = mk.sx > r.left - 20 && mk.sx < r.right + 20 && mk.sy > r.top - 20 && mk.sy < r.bottom + 20;
      }
      if (!ok){ if (!mk.el.hidden) mk.el.hidden = true; return; }
      if (mk.el.hidden) mk.el.hidden = false;
      mk.el.style.transform = "translate(" + mk.sx.toFixed(1) + "px," + mk.sy.toFixed(1) + "px)";
      mk.el.classList.toggle("pm-sel", inSel(mk));
      mk.el.classList.toggle("pm-behind", !!mk.behind);
      mk.el.classList.toggle("pm-focus", mk.j === focusI || mk.j === pinI);
      mk.el.classList.toggle("pm-lab-on", inSel(mk) || mk.j === act);
    });
    var a = act >= 0 ? M[act] : null;
    if (a && a.vis && !a.el.hidden && a.e != null){
      var s = scalePx(a), rad = Math.min(220, a.e * s);
      if (rad >= 4){
        errEl.hidden = false; errEl.className = "pm-err" + (a.c === "z_fill" ? " pm-z" : "");
        errEl.style.width = errEl.style.height = (2 * rad).toFixed(1) + "px";
        errEl.style.transform = "translate(" + (a.sx - rad).toFixed(1) + "px," + (a.sy - rad).toFixed(1) + "px)";
      } else errEl.hidden = true;
    } else errEl.hidden = true;
    if (pinI >= 0 || hoverI >= 0){
      var c = M[pinI >= 0 ? pinI : hoverI];
      if (c && c.vis && !c.el.hidden) placeCard(c); else if (pinI < 0) closeCard();
    }
  }
  /* pixels per mm at a marker (the projected lengths of three orthogonal 10 mm steps carry sqrt(2) times the scale) */
  function scalePx(mk){
    var r = E.canvasRect(), p = mk.xyz, q0 = E.project(p), sum = 0;
    if (!(q0[3] > 0)) return 0;
    [[10,0,0],[0,10,0],[0,0,10]].forEach(function(d){
      var q = E.project([p[0] + d[0], p[1] + d[1], p[2] + d[2]]);
      if (!(q[3] > 0)) return;
      var dx = (q[0] / q[3] - q0[0] / q0[3]) * 0.5 * r.width, dy = (q[1] / q[3] - q0[1] / q0[3]) * 0.5 * r.height;
      sum += dx * dx + dy * dy;
    });
    return Math.sqrt(sum / 2) / 10;
  }

  /* ---------- the marker card (hover on desktop, tap on touch) ---------- */
  function renderCard(j){
    var mk = M[j], p = D.parts[mk.pi];
    var err = mk.e != null ? "&plusmn; " + mmTxt(mk.e) + " mm" :
      "not stated" + (mk.ext ? " <small>(centre of a Z-Anatomy part mesh that spans about " + mk.ext + " mm; no fit to a person)</small>" : "");
    card.innerHTML = '<div class="pm-ch"><b>' + esc(p.n) + '</b><button type="button" class="pm-x" aria-label="Close">&times;</button></div>' +
      '<div class="pm-cs"><span class="pm-cls pm-cls-' + esc(mk.c) + '">' + esc(CLS[mk.c] || mk.c) + '</span> ' + esc(TYPES[p.ty] || p.ty) +
      (p.u ? ' &middot; <span style="color:var(--pm-warn);font-weight:700">unverified</span>' : "") +
      ' &middot; ' + (mk.s === "r" ? "right" : mk.s === "l" ? "left" : "midline") + '</div>' +
      '<dl><dt>Error bound</dt><dd>' + err + (mk.eb ? '<br><small>' + esc(mk.eb) + '</small>' : "") + '</dd>' +
      '<dt>Method</dt><dd>' + esc(mk.mt) + '</dd>' +
      '<dt>Position</dt><dd class="mono">' + mk.xyz.map(mmTxt).join(", ") + ' mm <small>(atlas frame)</small></dd></dl>' +
      '<p class="pm-not">A model position derived on this body by the rule above, not a measurement; the part itself is described by the citation below.</p>' +
      '<div class="pm-c" style="margin-top:6px;font-size:10.5px;color:var(--pm-dim)">' + refsHtml(p.r) + '</div>';
    card.querySelector(".pm-x").addEventListener("click", function(){ closeCard(); E.redraw(); });
  }
  function openCard(j, pinned){
    if (pinned) pinI = j;
    hoverI = j; renderCard(j); card.hidden = false;
    if (M[j].sx != null) placeCard(M[j]);
    E.redraw();
  }
  function placeCard(mk){
    if (card.hidden || mk.sx == null) return;
    var w = card.offsetWidth, h = card.offsetHeight, vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
    var x = mk.sx + 18, y = mk.sy + 14;
    if (x + w > vw - 8) x = Math.max(8, mk.sx - w - 18);
    if (y + h > vh - 8) y = Math.max(8, vh - h - 8);
    card.style.transform = "translate(" + Math.round(x) + "px," + Math.round(y) + "px)";
  }
  function closeCard(){
    var was = pinI >= 0 || hoverI >= 0 || (card && !card.hidden);
    pinI = -1; hoverI = -1; if (card) card.hidden = true;
    return was;
  }

  /* ---------- build ---------- */
  function build(){
    layer = document.getElementById("pm-layer"); card = document.getElementById("pm-card");
    layer.innerHTML = ""; M = [];
    errEl = document.createElement("div"); errEl.className = "pm-err"; errEl.hidden = true; layer.appendChild(errEl);
    D.placed.forEach(function(g, j){
      var p = D.parts[g.p];
      var el = document.createElement("div"); el.className = "pm" + (g.c === "z_fill" ? " pm-z" : ""); el.hidden = true;
      el.innerHTML = '<span class="pm-ring" role="button" tabindex="0" aria-label="Part marker: ' + esc(p.n) + '"></span><span class="pm-lab">' + esc(p.n) + '</span>';
      var ring = el.firstChild;
      ring.addEventListener("mouseenter", function(){ if (pinI < 0 && window.matchMedia && matchMedia("(hover:hover)").matches) openCard(j, false); });
      ring.addEventListener("mouseleave", function(){ if (pinI < 0){ hoverI = -1; card.hidden = true; E.redraw(); } });
      ring.addEventListener("click", function(e){
        e.stopPropagation();
        if (pinI === j){ closeCard(); E.redraw(); return; }
        focusI = j; openCard(j, true);
      });
      ring.addEventListener("keydown", function(e){ if (e.key === "Enter" || e.key === " "){ e.preventDefault(); ring.click(); } });
      layer.appendChild(el);
      M.push({j:j, pi:g.p, s:g.s, xyz:g.xyz, c:g.c, e:g.e, ext:g.ext, rule:g.rule, mt:g.mt, eb:g.eb, car:g.car, el:el, vis:false, why:"off", sx:null, sy:null});
    });
    if (M.length && E.toolbar && !btn){
      btn = document.createElement("button");
      btn.type = "button"; btn.id = "t-parts"; btn.className = E.toolClass || ""; btn.setAttribute("aria-pressed", "false"); btn.setAttribute("aria-haspopup", "true");
      btn.innerHTML = 'Parts<span class="pm-more"> markers</span>';
      btn.title = "Part markers (off by default): opt in to see which origins / insertions / heads are marked on the model, colour-coded rule-based / Z-Anatomy fill (visible + near, selected only, all), depth band";
      btn.addEventListener("click", function(){ openPanel(!panelOpen()); });
      E.toolbar.appendChild(btn);
    }
    buildPanel();
  }
  /* ---------- the Parts markers panel (Q240) ---------- */
  function panelOpen(){ return !!panel && !panel.hidden; }
  function $p(sel){ return panel ? panel.querySelector(sel) : null; }
  function buildPanel(){
    if (panelBuilt) return;
    panel = document.getElementById("pm-panel"); if (!panel) return;
    panelBuilt = true;
    panel.innerHTML = '<div class="pp-h"><b>Part markers</b><span class="pp-st" aria-live="polite"></span><button type="button" class="pp-x" aria-label="Close the part markers panel" title="Close">&times;</button></div>' +
      '<div class="pp-l">Markers</div>' +
      '<div class="pp-seg" role="group" aria-label="Which markers to show">' +
        '<button type="button" data-v="off" title="No part markers (default: not shown until you choose one of the other options here)">Off</button>' +
        '<button type="button" data-v="near" title="Markers that are not hidden behind other tissue and lie in the near part of the model">Visible + near</button>' +
        '<button type="button" data-v="sel" title="Only the markers of the selected, marked and hovered structures">Selected only</button>' +
        '<button type="button" data-v="all" title="Every placed marker (hidden ones are dashed)">All</button></div>' +
      '<div class="pp-l">Depth band <output class="pp-bv"></output></div>' +
      '<input class="pp-band" type="range" min="10" max="100" step="5" aria-label="Depth band: markers farther than this share of the visible model depth are left out">' +
      '<div class="pp-sc"><span>near</span><span>all</span></div>' +
      '<label class="pp-c"><input class="pp-hid" type="checkbox"> Show hidden ones of selected muscles</label>' +
      '<p class="pp-hint"></p>' +
      '<p class="pp-help">Off by default: these dots mark positions that are NOT measured on this body (orange = rule-based estimate, blue = Z-Anatomy fill) &mdash; this panel is how you choose to see them. ' +
      '<b>Visible + near</b> shows a marker only when its point is not hidden behind other tissue and lies within the depth band (the front part of the visible model, measured from the viewer). ' +
      'Markers of selected, marked or hovered structures are always shown, drawn dashed with a halo when they are behind tissue; switch the box off to cull them like the rest. Cut mode: markers on the removed side are hidden.</p>';
    panel.querySelector(".pp-x").addEventListener("click", function(){ openPanel(false); });
    panel.querySelector(".pp-seg").addEventListener("click", function(e){
      var b = e.target && e.target.closest ? e.target.closest("button") : null; if (!b) return;
      setMode(b.getAttribute("data-v"));
    });
    panel.querySelector(".pp-band").addEventListener("input", function(){ setBand(this.value); });
    panel.querySelector(".pp-hid").addEventListener("change", function(){ P.hid = !!this.checked; persist(); syncPanel(); E.redraw(); });
    syncPanel();
  }
  function syncPanel(){
    if (!panel) return;
    Array.prototype.forEach.call(panel.querySelectorAll(".pp-seg button"), function(b){
      var v = b.getAttribute("data-v"); b.setAttribute("aria-pressed", String(v === P.mode)); if (v === "near") b.hidden = !canCull;
    });
    var bd = $p(".pp-band"), bv = $p(".pp-bv"), hd = $p(".pp-hid"), ht = $p(".pp-hint"), st = $p(".pp-st");
    if (bd){ bd.value = P.band; bd.disabled = !canCull || P.mode !== "near"; }
    if (bv) bv.textContent = P.band >= 100 ? "all depths" : "front " + P.band + " %";
    if (hd) hd.checked = P.hid;
    var c = cull.cnt;
    if (st) st.textContent = P.mode === "off" ? "off" : c.shown + " shown";
    if (ht) ht.textContent = !canCull ? "This page cannot test what is hidden: markers follow the selection or the All switch." :
      (P.mode === "near" ? c.shown + " shown" + (c.occ ? ", " + c.occ + " hidden behind tissue" : "") + (c.far ? ", " + c.far + " beyond the depth band" : "") + (c.behind ? ", " + c.behind + " seen through (selected)" : "") + "." : "");
    if (btn) btn.setAttribute("aria-pressed", String(panelOpen()));
  }
  function placePanel(){
    if (!panel || panel.hidden) return;
    var vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight, w = panel.offsetWidth || 290, h = panel.offsetHeight || 260;
    var br = btn && btn.getBoundingClientRect ? btn.getBoundingClientRect() : {left:12, bottom:50, top:12};
    if (vw < 560){ panel.style.left = "8px"; panel.style.top = Math.max(8, Math.min(vh - h - 8, br.bottom + 6)) + "px"; return; }
    var x = Math.max(8, Math.min(vw - w - 8, br.left)), y = br.bottom + 6; if (y + h > vh - 8) y = Math.max(8, vh - h - 8);
    panel.style.left = Math.round(x) + "px"; panel.style.top = Math.round(y) + "px";
  }
  function openPanel(on){
    if (!panel) return;
    panel.hidden = !on; if (on){ syncPanel(); placePanel(); } syncPanel();
  }
  function setMode(m){
    if (!MODES[m] || (m === "near" && !canCull)) return;
    P.mode = m; persist(); cull.dirty = true;
    if (m === "off" && !sel){ focusI = -1; closeCard(); }
    syncPanel(); E.redraw();
  }
  function setShowAll(v){ setMode(v ? "all" : "sel"); }
  function hover(meshId){
    var h = meshId || null; if (h === hoverMesh) return;
    var had = !!(D && hoverMesh && D.mesh_parts[hoverMesh]), has = !!(D && h && D.mesh_parts[h]);
    hoverMesh = h;
    if (had || has) cull.dirty = true;
    if (M.length && P.mode !== "off" && (had || has)) E.redraw();          // only a structure with parts changes what is shown
  }
  function dirty(){ cull.dirty = true; }
  document.addEventListener("pointerdown", function(e){
    if (!card || card.hidden || pinI < 0) return;
    if (card.contains(e.target) || (e.target.closest && e.target.closest(".pm-ring, .pm-row"))) return;
    closeCard(); E.redraw();
  }, true);
  document.addEventListener("keydown", function(e){
    if (e.key === "Escape" && card && !card.hidden && pinI >= 0){ closeCard(); E.redraw(); e.stopImmediatePropagation(); }
    else if (e.key === "Escape" && panelOpen() && panel.contains(document.activeElement)){ openPanel(false); }
  }, true);

  function load(){
    if (!E.url || !window.fetch) return;
    fetch(E.url).then(function(r){ if (!r.ok) throw new Error("no parts_data.json"); return r.json(); }).then(function(d){
      if (!d || String(d.schema).indexOf("nmsk.parts_sidecar") !== 0 || !d.parts || !d.mesh_parts) throw new Error("not a parts sidecar");
      D = d; build();
      if (E.onLoaded) E.onLoaded();
      E.redraw();
    }).catch(function(){ D = null; });
  }
  return {
    load:load, select:select, cardHtml:cardHtml, bind:bind, update:update, overlay:overlay, setShowAll:setShowAll,
    hover:hover, dirty:dirty, setMode:setMode, setBand:setBand, openPanel:openPanel, settings:function(){ return JSON.parse(JSON.stringify(P)); },
    cullNow:function(){ if (needCull()){ capture(viewSig()); E.redraw(); } },
    /* read-only view for tests / debugging */
    state:function(){
      return {loaded:!!D, parts:D ? D.parts.length : 0, placements:M.length, showAll:P.mode === "all", mode:P.mode, band:P.band, hid:P.hid, canCull:canCull, panel:panelOpen(), cull:{n:cull.n, ms:Math.round(cull.ms * 10) / 10, avgMs:Math.round(cull.avg * 10) / 10, near:Math.round(cull.near), far:Math.round(cull.far), img:cull.img ? cull.img.w + "x" + cull.img.h : null, cnt:cull.cnt}, focus:focusI, pinned:pinI,
              sel:sel ? {mesh:sel.mesh, side:sel.s, n:sel.list.length} : null,
              markers:M.map(function(mk){ return {j:mk.j, part:D.parts[mk.pi].id, side:mk.s, xyz:mk.xyz, cls:mk.c, e:mk.e, vis:mk.vis, why:mk.why, sx:mk.sx, sy:mk.sy, shown:!mk.el.hidden, cull:mk.cull | 0, behind:!!mk.behind, forced:!!mk.forced, dm:mk.dm == null ? null : Math.round(mk.dm), z:mk.zmin == null || mk.zmin === Infinity ? null : Math.round(mk.zmin)}; })};
    }
  };
}
