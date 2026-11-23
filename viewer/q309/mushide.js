/* Q391: hide gently, muscle by muscle, in the textbook layer order.
   Owner (translated from Hebrew, 2026-11-22): "The division into levels in one system does not necessarily match the levels
   of another system. For the muscles, for example, it is a MUST to work by the known layers. Also allow gently hiding
   muscle by muscle."
   The order is NMSKSysMap's regional layers (data/anatomy/system_layers_q309.json, `regions`): region by region in the
   table's order, each region outermost layer first, a layer's muscles by name. Next fades the next muscle out (~250 ms,
   no pop); Back brings the last one back; every hidden muscle is listed and can be brought back alone, or all at once.
   A picked muscle can be faded out from its quick card (an add-on), and joins the same list. The region and the side
   (both / right / left) narrow the walk. Logically a muscle is hidden the moment it is chosen -- the history, Show
   everything and the counts see it at once -- but it joins Q309's veto set only when its fade ends, so the engine
   draws it fading in between (E.fade). An engine without E.fade hides at once.
   Lives inside the Q309 depth control (no new top-level button) and travels in Q309's one history provider.
     NMSKMusHide.start(E, {map, push, history})
     .next()  .back()  .hideIds(ids)  .show(i)  .clear()  .setRegion(k)  .setSide(s)  .ids()  .hidden()  .get()  .put(v)
     .element()  .source()  .state() */
var NMSKMusHide = (function(){
  "use strict";
  var MS = 250, STEPS = 32, MINF = 6;      /* ~250 ms, but never fewer than 6 drawn frames: a slow GPU slows the fade, it never pops */
  var E = null, M = null, push = null, hist = null, on = false, sys = "";
  var REGS = [], UNITS = [], NAME = {}, ACT = [], HID = {}, FADE = {}, raf = 0, TR = null;
  var region = "all", side = "both";
  var box = null, body = null, openB = null, regSel = null, sideB = {}, nextB = null, backB = null, allB = null, outEl = null, listEl = null;
  function stem(id){ return String(id).replace(/_(?:l|r)$/, ""); }
  function sideOf(id){ var m = /_(l|r)$/.exec(String(id)); return m ? m[1] : ""; }
  function pick(ids){ return side === "both" ? ids.slice() : ids.filter(function(i){ var s = sideOf(i); return !s || s === side; }); }
  /* the walk: region by region, layer by layer, one unit per muscle (its left and right meshes together) */
  function build(){
    UNITS = [];
    REGS.forEach(function(R){
      R.layers.forEach(function(L){
        var by = {}, order = [];
        L.ids.forEach(function(i){ var k = stem(i); if (!by[k]){ by[k] = []; order.push(k); } by[k].push(i); });
        order.sort(function(a, b){ return nm(by[a][0]).localeCompare(nm(by[b][0])); });
        order.forEach(function(k){ UNITS.push({key:k, ids:by[k], region:R.key, regionLabel:R.label, layer:L.n, of:R.layers.length, layerLabel:L.label}); });
      });
    });
  }
  function nm(id){ var n = NAME[id] || id; return n.replace(/\s+--\s+.*$/, "").replace(/\s*\((?:left|right)\)\s*$/i, ""); }
  function walk(){ return UNITS.filter(function(u){ return region === "all" || u.region === region; }); }
  function upNext(){
    var W = walk();
    for (var i = 0; i < W.length; i++){ var p = pick(W[i].ids); if (p.length && p.some(function(x){ return !HID[x]; })) return W[i]; }
    return null;
  }
  /* what Q309's veto set gets: hidden and no longer fading */
  function ids(){ return Object.keys(HID).filter(function(i){ return HID[i] && !(i in FADE); }); }
  function hiddenIds(){ return Object.keys(HID).filter(function(i){ return HID[i]; }); }
  /* ---- the fade ---- */
  function frame(){
    raf = 0;
    var now = Date.now(), live = {}, ended = false, lo = 1 / STEPS;
    Object.keys(FADE).forEach(function(i){
      var f = FADE[i];
      f.p = Math.min(1, Math.max(f.p, Math.min((now - f.t0) / MS, f.p + 1 / MINF)));
      var t = f.p, e = t * t * (3 - 2 * t);                                                    /* smoothstep: no pop at either end */
      if (t >= 1){ delete FADE[i]; ended = true; return; }
      var v = Math.round((f.out ? 1 - e : e) * STEPS) / STEPS;                                  /* few distinct values = few draw passes */
      live[i] = Math.max(lo, Math.min(1 - lo, v));
    });
    if (ended && push) push();                      /* a finished fade-out joins the veto in the same tick it leaves the fade */
    if (E.fade) E.fade(live);
    if (TR) TR.push({t:now, live:live, vetoed:ids().length});          /* verification only: what each frame drew */
    if (Object.keys(FADE).length){ if (typeof requestAnimationFrame === "function") raf = requestAnimationFrame(frame); }
    else if (E.redraw) E.redraw();
  }
  function fadeIds(list, out){
    if (!list.length) return;
    if (!E.fade || typeof requestAnimationFrame !== "function"){ if (push) push(); return; }
    var t0 = Date.now();
    list.forEach(function(i){
      var f = FADE[i];
      /* reversing a fade half-way starts from where it is, so a quick Back never jumps */
      var p0 = f ? 1 - f.p : 0;
      FADE[i] = {out:out, t0:t0 - p0 * MS, p:p0};
    });
    if (raf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf);
    raf = 0;
    if (!out && push) push();                       /* it leaves the veto ... */
    frame();                                        /* ... and is drawn at its first fade value in the same tick: no pop */
  }
  function settle(){
    FADE = {}; if (raf && typeof cancelAnimationFrame === "function") cancelAnimationFrame(raf); raf = 0;
    if (E && E.fade) E.fade({});
  }
  /* ---- the actions ---- */
  function commit(){
    if (hist && hist.schedule) hist.schedule();
    if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
  }
  function hideList(list, unit){
    list = list.filter(function(i){ return !HID[i]; });
    if (!list.length) return false;
    list.forEach(function(i){ HID[i] = 1; });
    ACT.push({ids:list, unit:unit || null});
    fadeIds(list, true);
    ui(unit ? "Hidden: " + label(unit) : "");
    commit();
    return true;
  }
  function next(){ var u = upNext(); return u ? hideList(pick(u.ids), u) : false; }
  function showAct(k){
    var a = ACT[k]; if (!a) return false;
    ACT.splice(k, 1);
    a.ids.forEach(function(i){ delete HID[i]; });
    fadeIds(a.ids, false);
    ui(a.unit ? "Back: " + label(a.unit) : "");
    commit();
    return true;
  }
  function back(){ return showAct(ACT.length - 1); }
  function clear(quiet){
    if (!ACT.length) return false;
    var all = hiddenIds();
    ACT = []; HID = {};
    fadeIds(all, false);
    ui("");
    if (!quiet) commit();
    return true;
  }
  function unitOfIds(list){
    var k = list.length ? stem(list[0]) : "";
    for (var i = 0; i < UNITS.length; i++) if (UNITS[i].key === k) return UNITS[i];
    return null;
  }
  function label(u){
    var L = M.layerOf(u.ids[0]) || {};
    return nm(u.ids[0]) + " — " + u.regionLabel + " · layer " + u.layer + " of " + u.of + " (" + u.layerLabel + ")" +
      (L.basis === "convention" ? " · our convention" : "");
  }
  /* ---- the UI ---- */
  function btn(id, txt, title, fn){
    var b = document.createElement("button");
    b.type = "button"; b.className = "mh-b q301-b"; b.id = id; b.textContent = txt; b.title = title;
    b.addEventListener("click", function(e){ e.stopPropagation(); fn(); });
    return b;
  }
  function ui(msg){
    if (!box) return;
    var u = upNext();
    nextB.disabled = !u; backB.disabled = !ACT.length; allB.hidden = !ACT.length;
    ["both", "r", "l"].forEach(function(s){ if (sideB[s]) sideB[s].setAttribute("aria-pressed", String(side === s)); });
    if (regSel && regSel.value !== region) regSel.value = region;
    var n = hiddenIds().length;
    outEl.textContent = (msg ? msg + " · " : "") + (u ? "Next: " + label(u) : "nothing left to hide here") +
      " · " + n + " hidden";
    while (listEl.firstChild) listEl.removeChild(listEl.firstChild);
    listEl.hidden = !ACT.length;
    ACT.forEach(function(a, k){
      var u2 = a.unit || unitOfIds(a.ids);
      var c = document.createElement("button");
      c.type = "button"; c.className = "mh-chip"; c.setAttribute("data-k", String(k));
      var sd = a.ids.length === 1 && sideOf(a.ids[0]) ? " (" + (sideOf(a.ids[0]) === "r" ? "R" : "L") + ")" : "";
      c.textContent = (u2 ? nm(u2.ids[0]) : nm(a.ids[0])) + sd + " ×";
      c.title = "Bring it back" + (u2 ? " — " + label(u2) : "");
      c.addEventListener("click", function(e){ e.stopPropagation(); showAct(k); });
      listEl.appendChild(c);
    });
    box.setAttribute("data-hidden", String(n));
  }
  function make(){
    box = document.createElement("div");
    box.id = "mh-box"; box.className = "mh-box";
    box.setAttribute("role", "group"); box.setAttribute("aria-label", "Hide muscles one by one, outermost layer first");
    /* folded by default (progressive disclosure): the Systems sheet keeps its old size, which on a phone is what keeps
       Q300's Show-everything bar reachable; one tap opens it */
    body = document.createElement("div"); body.id = "mh-body"; body.className = "mh-body"; body.hidden = true;
    openB = btn("mh-open", "Muscle by muscle ▸", "Hide muscles one at a time, gently, in the textbook layers of each region", function(){ fold(!body.hidden); });
    openB.setAttribute("aria-expanded", "false"); openB.setAttribute("aria-controls", "mh-body");
    box.appendChild(openB); box.appendChild(body);
    var row = document.createElement("div"); row.className = "mh-row";
    regSel = document.createElement("select"); regSel.id = "mh-region"; regSel.className = "mh-sel";
    regSel.setAttribute("aria-label", "Which region to walk");
    var o0 = document.createElement("option"); o0.value = "all"; o0.textContent = "All regions, one after another"; regSel.appendChild(o0);
    REGS.forEach(function(R){
      var o = document.createElement("option"); o.value = R.key;
      o.textContent = R.label + " (" + R.layers.length + " layer" + (R.layers.length === 1 ? "" : "s") + ")";
      regSel.appendChild(o);
    });
    regSel.addEventListener("change", function(e){ e.stopPropagation(); setRegion(regSel.value); });
    regSel.addEventListener("click", function(e){ e.stopPropagation(); });
    row.appendChild(regSel);
    var sd = document.createElement("span"); sd.className = "mh-side"; sd.setAttribute("role", "group"); sd.setAttribute("aria-label", "Which side");
    [["both", "Both"], ["r", "R"], ["l", "L"]].forEach(function(p){
      var b = btn("mh-side-" + p[0], p[1], p[0] === "both" ? "Both sides at each step" : "Only the patient's " + (p[0] === "r" ? "right" : "left") + " side", function(){ setSide(p[0]); });
      b.setAttribute("aria-pressed", String(side === p[0])); sideB[p[0]] = b; sd.appendChild(b);
    });
    row.appendChild(sd);
    body.appendChild(row);
    var row2 = document.createElement("div"); row2.className = "mh-row";
    backB = btn("mh-back", "◀ Back", "Bring the last hidden muscle back, gently (one Undo step)", back);
    nextB = btn("mh-next", "Hide next ▶", "Fade out the next muscle, outermost layer of its region first (one Undo step)", next);
    allB = btn("mh-all", "Show all", "Bring every muscle hidden here back", function(){ clear(); });
    row2.appendChild(backB); row2.appendChild(nextB); row2.appendChild(allB);
    body.appendChild(row2);
    outEl = document.createElement("output"); outEl.id = "mh-state"; outEl.className = "mh-o"; outEl.setAttribute("aria-live", "polite");
    body.appendChild(outEl);
    listEl = document.createElement("div"); listEl.id = "mh-list"; listEl.className = "mh-list"; listEl.hidden = true;
    listEl.setAttribute("aria-label", "Hidden muscles; tap one to bring it back");
    body.appendChild(listEl);
    var n = document.createElement("span"); n.className = "mh-note";
    n.innerHTML = '<p class="nmsk-tip"><b>Muscle by muscle</b> fades one muscle out at a time, in the textbook layers of its own region ' +
      '(the back’s seven, the sole’s four, the forearm’s superficial / intermediate / deep…), outermost first, region after region. ' +
      'Every placement names its book and page in the Systems section of Info; the few that are ours say so. A muscle picked on the model can be faded out from its card too. One step is <b>one Undo step</b>.</p>';
    body.appendChild(n);
  }
  function fold(shut){
    if (!body) return;
    body.hidden = !!shut;
    openB.setAttribute("aria-expanded", String(!shut));
    openB.textContent = "Muscle by muscle " + (shut ? "▸" : "▾");
  }
  function setRegion(k, quiet){
    if (k !== "all" && !REGS.some(function(R){ return R.key === k; })) return false;
    region = k; ui(""); if (!quiet) commit(); return true;
  }
  function setSide(s, quiet){
    if (s !== "both" && s !== "r" && s !== "l") return false;
    side = s; ui(""); if (!quiet) commit(); return true;
  }
  /* the quick card: a picked muscle can be faded out with one press, and the card says which layer it is in */
  function cardAddon(){
    var Q = window.NMSKQuickCard;
    if (!Q || !Q.addon) return;
    Q.addon({key:"q391", order:8, render:function(id, host, card){
      if (M.of(id) !== sys) return;
      var L = M.layerOf(id) || {regionLabel:"No sourced layer", layer:0, of:0, layerLabel:"", basis:"none", cite:""};
      var row = document.createElement("div"); row.className = "mh-card";
      var t = document.createElement("span"); t.className = "mh-card-l";
      t.textContent = L.layer ? L.regionLabel + " · layer " + L.layer + " of " + L.of + (L.basis === "convention" ? " (our convention)" : "") : "no sourced layer";
      t.title = L.layerLabel + " — " + (L.cite || "") + (L.note ? " — " + L.note : "");
      var b = document.createElement("button"); b.type = "button"; b.className = "mh-card-b"; b.id = "mh-card-hide";
      b.textContent = "Fade out"; b.title = "Hide this muscle gently; it joins the Muscle-by-muscle list, where it can be brought back";
      b.addEventListener("click", function(ev){
        ev.stopPropagation();
        var sc = []; try { sc = card.scope ? card.scope() : []; } catch (err){ sc = []; }
        var list = (sc && sc.length ? sc : [id]).filter(function(i){ return M.of(i) === sys; });
        if (hist && hist.commit) { try { hist.commit(); } catch (e1){} }          /* Q378: seal the click's pending step first */
        hideList(list, list.length > 1 ? unitOfIds(list) : null);
        if (hist && hist.commit) { try { hist.commit(); } catch (e2){} }
      });
      row.appendChild(t); row.appendChild(b); host.appendChild(row);
    }});
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null; M = opt.map || window.NMSKSysMap || null; push = opt.push || null;
      hist = opt.history || window.NMSKHistory || null;
      if (!E || !M || !M.ready() || !M.regions) return api;
      var S = M.systems().filter(function(s){ return M.regions(s.key).length > 0; })[0];
      if (!S) return api;
      sys = S.key; REGS = M.regions(sys);
      try { (E.all() || []).forEach(function(x){ NAME[x.id] = x.name || x.id; }); } catch (err){}
      build();
      make();
      cardAddon();
      on = true; ui("");
      return api;
    },
    ready:function(){ return on; },
    next:next, back:back, clear:function(){ return clear(); },
    hideIds:function(list){ return hideList((list || []).slice(), null); },
    show:function(k){ return showAct(k | 0); },
    setRegion:setRegion, setSide:setSide,
    ids:ids, hidden:hiddenIds, element:function(){ return box; }, refresh:function(){ ui(""); },
    order:function(){ return walk().map(function(u){ return {key:u.key, ids:u.ids.slice(), region:u.region, layer:u.layer, name:nm(u.ids[0])}; }); },
    fading:function(){ return Object.keys(FADE).length; },
    /* verification only: trace(true) starts recording every fade frame {t, live:{id:factor}, vetoed}; trace() reads it */
    trace:function(start){ if (start){ TR = []; return true; } return TR ? TR.slice() : []; },
    /* history: region | side | the hidden steps in order, each its ids joined by '+'. No ';' (Q309's separator). */
    get:function(){ return region + "|" + side + "|" + ACT.map(function(a){ return a.ids.join("+"); }).join(","); },
    put:function(v){
      var p = String(v || "").split("|");
      settle();
      region = (p[0] && (p[0] === "all" || REGS.some(function(R){ return R.key === p[0]; }))) ? p[0] : "all";
      side = (p[1] === "r" || p[1] === "l") ? p[1] : "both";
      ACT = []; HID = {};
      (p[2] || "").split(",").forEach(function(s){
        if (!s) return;
        var list = s.split("+").filter(function(i){ return M.of(i) === sys; });
        if (!list.length) return;
        list.forEach(function(i){ HID[i] = 1; });
        ACT.push({ids:list, unit:null});
      });
      ACT.forEach(function(a){ var u = unitOfIds(a.ids); if (u && pick(u.ids).join("+") === a.ids.join("+")) a.unit = u; });
      if (push) push();
      ui("");
    },
    source:function(){
      return {key:"q391mus",
        label:function(){ var n = hiddenIds().length; return n + " muscle" + (n === 1 ? "" : "s") + " hidden one by one"; },
        active:function(){ return on && hiddenIds().length > 0; },
        clear:function(){ settle(); ACT = []; HID = {}; if (push) push(); ui(""); },
        drive:function(){ next(); settle(); if (push) push(); }};
    },
    state:function(){ var u = on ? upNext() : null;
      return {on:on, system:sys, region:region, side:side, regions:REGS.length, units:UNITS.length, steps:ACT.length,
        hidden:hiddenIds().length, vetoed:ids().length, fading:Object.keys(FADE).length, next:u ? u.key : null,
        nextLabel:u ? label(u) : ""}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKMusHide;
