/* The sourced PARTS of a structure (Q220, on the Q219 parts model): a Parts list in the structure card and point markers on the model.
   Data = the page's sidecar parts_data.json (public anatomy layer), fetched with a graceful fallback: absent or invalid = no Parts section,
   no toggle, nothing else changes. Engine adaptor E: url, canvasRect(), project(p)->[x,y,z,w] clip coords, cut()->null|{kn,c,th} (the kept
   part is 0 <= kn.p + c <= th, th = 0 = no far face), meshVisible(id), focusAt(p), redraw(), setDots(list) (engine-drawn, depth-tested
   dots), toolbar + toolClass (host of the "Parts markers" toggle), onLoaded().
   A marker is a position derived by a stated rule on THIS model (rule-based) or the place of a Z-Anatomy mesh (Z-fill): always shown
   with its source class and error bound, never as measured. Markers appear for the selected structure, or for every placed part with the
   toggle; they follow Cut mode (incl. the slice thickness), the layer / hide / isolate state of their structure, and x-ray (the solid dot is
   depth-tested by the engine: hidden behind opaque tissue, seen through x-ray; the hollow ring + label stay). */
function NMSKParts(E){
  "use strict";
  var D = null, M = [], sel = null, showAll = false, focusI = -1, hoverI = -1, pinI = -1;
  var btn = null, layer = null, card = null, errEl = null;
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
    sel = null; focusI = -1; closeCard();
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
  /* called by the engine before it renders: decides which markers are drawn and hands the solid dots over */
  function update(){
    if (!D || !M.length) return;
    var dots = [];
    M.forEach(function(mk){
      var why = "";
      if (!(showAll || inSel(mk))) why = "off";
      else if (!kept(mk.xyz)) why = "cut";
      else if (!carriersVisible(mk)) why = "hidden";
      mk.vis = why === ""; mk.why = why;
      if (mk.vis) dots.push({p:mk.xyz, c:DOT[mk.c] || DOT.rule_based, big:mk.j === focusI || mk.j === hoverI || mk.j === pinI});
    });
    E.setDots(dots);
  }
  /* called by the engine after it rendered: positions of the rings / labels / card */
  function overlay(){
    if (!D || !layer || !M.length) return;
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
      btn.type = "button"; btn.id = "t-parts"; btn.className = E.toolClass || ""; btn.setAttribute("aria-pressed", "false");
      btn.textContent = "Parts markers";
      btn.title = "Show the point markers of every placed part (otherwise only those of the selected structure)";
      btn.addEventListener("click", function(){ setShowAll(!showAll); });
      E.toolbar.appendChild(btn);
    }
  }
  function setShowAll(v){
    showAll = !!v; if (btn) btn.setAttribute("aria-pressed", String(showAll));
    if (!showAll && !sel){ focusI = -1; closeCard(); }
    E.redraw();
  }
  document.addEventListener("pointerdown", function(e){
    if (!card || card.hidden || pinI < 0) return;
    if (card.contains(e.target) || (e.target.closest && e.target.closest(".pm-ring, .pm-row"))) return;
    closeCard(); E.redraw();
  }, true);
  document.addEventListener("keydown", function(e){
    if (e.key === "Escape" && card && !card.hidden && pinI >= 0){ closeCard(); E.redraw(); e.stopImmediatePropagation(); }
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
    /* read-only view for tests / debugging */
    state:function(){
      return {loaded:!!D, parts:D ? D.parts.length : 0, placements:M.length, showAll:showAll, focus:focusI, pinned:pinI,
              sel:sel ? {mesh:sel.mesh, side:sel.s, n:sel.list.length} : null,
              markers:M.map(function(mk){ return {j:mk.j, part:D.parts[mk.pi].id, side:mk.s, xyz:mk.xyz, cls:mk.c, e:mk.e, vis:mk.vis, why:mk.why, sx:mk.sx, sy:mk.sy, shown:!mk.el.hidden}; })};
    }
  };
}
