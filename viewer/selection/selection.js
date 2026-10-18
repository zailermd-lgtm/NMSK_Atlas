/* Marked structures, "show only marked", saved selection sets (Q227). One controller for both viewers. The engine is reached only through the adaptor E:
   modelId() items() -> [{id,name}] (one per structure, in list order)   refresh() re-apply visibility   selected() select(id)   reveal(ids) (switch the layers /
   source classes / hide flags of these structures on)   listIds() (ids the search box shows)   pickId(ev) (cap-aware)   clearHover()   resetEngine() (the
   engine's own isolation / hide / fade / solo / box)   canvas   toolbar + toolClass   isPhone()   [frame(ids)].
   Q232 adds [eligible()] (ids shown by the layers / hidden flags / source facet / side filter, ignoring the selection itself), [categories()] +
   [idsOfCategory(key)] (cheap "mark a whole layer"), and look(id) = the display state of the group (marked = "selected", rest = "others") a structure belongs to:
   "" (as the layers say) | "fade" (opacity fadeAlpha()) | "hide" | "ghost" | "xray" | "hl" (solid colour hlHex(); selected group only). rule(id) is the
   Q227 view of it ("" | "hide" | "ghost") and stays valid. tinted(id) = the amber mark tint.
   The engine asks rule(id): "" = as the layers say, "hide" = not drawn, "ghost" = drawn as a faint ghost and not pickable; isMarked(id) tints a marked
   structure. A selection composes with everything else because it only ADDS a veto: the layer toggles, the source facet, X-ray, the cut plane + slab and the
   parts markers all still apply to what it leaves.
   Persistence: localStorage (try/catch; keyed per model because structure ids differ between models) with an in-memory fallback, plus export / import as text
   and a link (#nmsksel=...). */
function NMSKSelect(E){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var MODEL = String(E.modelId()), KEY = "nmsk.sel.v1:" + MODEL, LP_MS = 520, MARKLIMIT = 400;
  var marks = [], set = {}, ss = "show", os = "show", ghostPref = false, markMode = false, storageOK = true, suppress = false;
  var fade = 0.15, hl = "#ffb000", tintOn = true, inv = null;                   // Q232: fade opacity 0..1, highlight colour, amber tint of marked structures, inv = {id:1} ids left out by Invert (null = not inverted)
  var STATES = {show:1, fade:1, hide:1, ghost:1, xray:1, hl:1};
  var data = {v:1, model:MODEL, sets:{}, last:null, remember:true};
  var names = {}, order = [];
  E.items().forEach(function(it){ if (!(it.id in names)){ names[it.id] = it.name || it.id; order.push(it.id); } });
  var sec = $("sel-sec"), fadeEl = $("sel-fade"), fadeVEl = $("sel-fade-v"), hlEl = $("sel-hl"), tintEl = $("sel-tint"), invNoteEl = $("sel-invnote"), chipsEl = $("sel-chips"), cntEl = $("sel-count"), statusEl = $("sel-status"), nameEl = $("sel-name"), setsEl = $("sel-sets"),
      ioEl = $("sel-io"), storeEl = $("sel-store"), remEl = $("sel-remember");
  var tbMark = null, tbOnly = null, tbInv = null;

  function esc(s){ return String(s == null ? "" : s).replace(/[&<>"]/g, function(c){ return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]; }); }
  function has(id){ return Object.prototype.hasOwnProperty.call(names, id); }
  function name(id){ return has(id) ? names[id] : id; }
  function say(m){ if (statusEl) statusEl.textContent = m || ""; }
  /* ---- storage: always mirrored in memory; the browser store is a convenience that may be blocked (private window, artifact origin) ---- */
  function storeRead(){
    try { var r = localStorage.getItem(KEY); storageOK = true; return r ? JSON.parse(r) : null; }
    catch (err){ storageOK = false; return null; }
  }
  function storeWrite(){
    try { localStorage.setItem(KEY, JSON.stringify(data)); storageOK = true; }
    catch (err){ storageOK = false; }
    storeNote();
  }
  function storeNote(){
    if (!storeEl) return;
    storeEl.textContent = storageOK ? "Saved selections stay in this browser for this model (" + Object.keys(data.sets).length + " saved)."
      : "This browser blocks storage here: selections are kept only until you close the page. Use Export (copy the text) or Copy link to keep one.";
  }
  function modeOf(){
    if (!marks.length) return "all";
    if (ss === "show" && (os === "hide" || os === "ghost")) return "only";
    if ((ss === "hide" || ss === "ghost") && os === "show") return "hide";
    return "all";
  }
  function ghostOf(){ return ghostPref || ss === "ghost" || os === "ghost"; }
  function baseIds(){ return inv ? order.filter(function(id){ return inv[id] === 1; }) : marks.slice(); }
  /* the stored / exported / linked form: when inverted only the ids that were LEFT OUT are kept ("inverse of these"), so the set is small and is re-evaluated
     against whatever is eligible when it is loaded; the older fields (mode, ghost) stay for Q227 readers */
  function pack(){
    var p = {ids:baseIds(), mode:modeOf(), ghost:ghostOf(), ss:ss, os:os, fade:Math.round(fade * 100) / 100, hl:hl};
    if (inv) p.inv = true;
    return p;
  }
  function persistLast(){
    data.remember = !remEl || !!remEl.checked;
    data.last = data.remember ? pack() : null;
    data.tint = tintOn;
    storeWrite();
  }
  /* ---- the selection itself: two groups, "selected" (marked) and "others", each with its own display state ---- */
  function stateOf(id){
    if (!marks.length) return "";
    var s = set[id] === 1 ? ss : os;
    if (s === "fade" && fade <= 0.005) s = "hide";            // 0 % opacity = not drawn at all (no pick, no cap)
    return s === "show" ? "" : s;
  }
  function rule(id){ var s = stateOf(id); return s === "hide" ? "hide" : s === "ghost" ? "ghost" : ""; }
  function ghosting(){ return marks.length > 0 && (ss === "ghost" || os === "ghost"); }
  function translucent(){ return marks.length > 0 && [ss, os].some(function(s){ return s === "fade" || s === "ghost" || s === "xray"; }); }
  function activeState(){ return marks.length > 0 || ss !== "show" || os !== "show" || ghostPref; }
  function tinted(id){ return tintOn && !inv && ss === "show" && set[id] === 1; }          // no amber tint while inverted: the marked set is the whole rest of the body
  function hlHex(){ return parseInt(hl.slice(1), 16); }
  function fixStates(){
    if (!STATES[ss]) ss = "show";
    if (!STATES[os] || os === "hl") os = "show";
    if (!marks.length){ ss = os = "show"; ghostPref = false; inv = null; }
  }
  function syncButtons(){
    var l = document.querySelectorAll(".ss-mk[data-id]");
    for (var i = 0; i < l.length; i++) l[i].setAttribute("aria-pressed", String(set[l[i].getAttribute("data-id")] === 1));
  }
  function renderChips(){
    if (chipsEl){
      var h = "", n, i;
      if (inv){                                              // inverted: show what was LEFT OUT (the marked set is everything else eligible)
        var ex = baseIds(); n = Math.min(ex.length, MARKLIMIT);
        h += '<span class="ss-chip ss-all"><span class="t">Inverted: all other ' + marks.length + '</span></span>';
        for (i = 0; i < n; i++) h += '<span class="ss-chip ss-exc"><span class="t" title="Left out: ' + esc(name(ex[i])) + '">not ' + esc(name(ex[i])) +
          '</span><button type="button" data-exc="' + esc(ex[i]) + '" aria-label="Mark ' + esc(name(ex[i])) + ' too" title="Mark this one too">+</button></span>';
        if (ex.length > n) h += '<span class="ss-chip"><span class="t">+' + (ex.length - n) + ' more left out</span></span>';
      } else {
        n = Math.min(marks.length, MARKLIMIT);
        for (i = 0; i < n; i++) h += '<span class="ss-chip"><span class="t" title="' + esc(name(marks[i])) + '">' + esc(name(marks[i])) +
          '</span><button type="button" data-id="' + esc(marks[i]) + '" aria-label="Unmark ' + esc(name(marks[i])) + '" title="Unmark">&times;</button></span>';
        if (marks.length > n) h += '<span class="ss-chip"><span class="t">+' + (marks.length - n) + ' more</span></span>';
      }
      chipsEl.innerHTML = h;
    }
    if (cntEl) cntEl.textContent = String(marks.length);
    if (sec && sec.classList){ sec.classList.toggle("has-marks", marks.length > 0); sec.classList.toggle("is-inverted", !!inv); }
  }
  var PRESETS = {isolate:["show", "hide"], fadeoth:["show", "fade"], fadesel:["fade", "show"], hidesel:["hide", "show"], hlsel:["hl", "show"]};
  function ui(){
    var n = marks.length, md = modeOf();
    function pr(id, v){ var e = $(id); if (e) e.setAttribute("aria-pressed", String(v)); }
    pr("sel-only", md === "only"); pr("sel-hide", md === "hide"); pr("sel-ghost", ghostOf()); pr("sel-markmode", markMode); pr("sel-invert", !!inv);
    ["sel-only", "sel-hide", "sel-clear", "sel-ghost"].forEach(function(id){ var e = $(id); if (e) e.disabled = !n; });
    var gb = document.querySelectorAll(".ss-st[data-g]");
    for (var i = 0; i < gb.length; i++){ var g = gb[i].getAttribute("data-g"), st = gb[i].getAttribute("data-s");
      gb[i].setAttribute("aria-pressed", String((g === "sel" ? ss : os) === st)); gb[i].disabled = !n; }
    Object.keys(PRESETS).forEach(function(k){ var e = $("sel-p-" + k); if (!e) return; e.disabled = !n; e.setAttribute("aria-pressed", String(n > 0 && ss === PRESETS[k][0] && os === PRESETS[k][1])); });
    if (fadeEl){ fadeEl.value = String(Math.round(fade * 100)); } if (fadeVEl) fadeVEl.textContent = Math.round(fade * 100) + " %";
    if (hlEl && hlEl.value !== hl) hlEl.value = hl;
    if (tintEl) tintEl.checked = tintOn;
    if (invNoteEl) invNoteEl.hidden = !inv;
    if (tbMark){ tbMark.setAttribute("aria-pressed", String(markMode)); tbMark.textContent = n ? "Mark · " + n : "Mark"; }
    if (tbOnly){ tbOnly.setAttribute("aria-pressed", String(md === "only")); tbOnly.hidden = !n; tbOnly.textContent = md === "only" ? "Show all" : "Only marked";
      tbOnly.title = md === "only" ? "Show everything again (the marks stay)" : "Show only the marked structures"; }
    if (tbInv){ tbInv.setAttribute("aria-pressed", String(!!inv)); tbInv.hidden = !n; }
    if (document.body && document.body.classList) document.body.classList.toggle("ss-marking", markMode);
  }
  function changed(){
    fixStates(); renderChips(); syncButtons(); ui(); persistLast(); E.refresh();
  }
  function mark(id, on){
    if (!has(id)) return false;
    var is = set[id] === 1;
    if (on === undefined) on = !is;
    if (on && !is){ set[id] = 1; marks.push(id); if (inv) delete inv[id]; }
    else if (!on && is){ delete set[id]; marks.splice(marks.indexOf(id), 1); if (inv) inv[id] = 1; }
    else return false;
    if (!marks.length){ ss = os = "show"; ghostPref = false; inv = null; }
    return true;
  }
  function toggle(id, fromList){
    if (!has(id)) return false;
    var was = set[id] === 1;
    mark(id);
    if (!was && fromList && E.reveal) E.reveal([id]);
    say(name(id) + (was ? " unmarked." : " marked.") + " " + marks.length + " marked.");
    changed();
    return true;
  }
  function setMode(m){
    if (m !== "all" && !marks.length){ say("Mark at least one structure first."); ss = os = "show"; changed(); return; }
    var cur = modeOf();
    if (cur === m || m === "all"){ ss = os = "show"; ghostPref = false; }
    else if (m === "only"){ ss = "show"; os = ghostPref ? "ghost" : "hide"; }
    else if (m === "hide"){ ss = ghostPref ? "ghost" : "hide"; os = "show"; }
    if (modeOf() === "only" && E.reveal) E.reveal(marks);       // an explicit choice beats a switched-off layer
    var md = modeOf();
    say(md === "only" ? "Showing only the " + marks.length + " marked." : md === "hide" ? "Marked structures hidden." : "Showing everything again.");
    changed();
  }
  function setGhost(v){
    if (!marks.length){ say("Mark at least one structure first."); changed(); return; }
    ghostPref = v === undefined ? !ghostOf() : !!v;
    if (ghostPref){ if (ss === "hide") ss = "ghost"; if (os === "hide") os = "ghost"; }
    else { if (ss === "ghost") ss = "hide"; if (os === "ghost") os = "hide"; }
    say(ghostPref ? "The rest is drawn as faint ghosts." : "Ghosting off.");
    changed();
  }
  var WORD = {show:"shown normally", fade:"faded", hide:"hidden", ghost:"drawn as ghosts", xray:"drawn as X-ray", hl:"highlighted"};
  /* group = "sel" (the marked structures) or "oth" (everything else); clicking the active state again goes back to "show" */
  function setGroup(g, st, noToggle){
    if (!marks.length){ say("Mark at least one structure first."); changed(); return; }
    if (!STATES[st] || (g === "oth" && st === "hl")) return;
    var cur = g === "sel" ? ss : os;
    if (cur === st && !noToggle && st !== "show") st = "show";
    if (g === "sel") ss = st; else os = st;
    if (ss !== "ghost" && os !== "ghost") ghostPref = false;
    if (g === "oth" && st === "hide" && E.reveal && ss === "show") E.reveal(marks);
    say((g === "sel" ? "Selected (" + marks.length + ")" : "Others") + ": " + WORD[st] + (st === "fade" ? " at " + Math.round(fade * 100) + " %" : "") + ".");
    changed();
  }
  function preset(k){
    var p = PRESETS[k]; if (!p) return;
    if (!marks.length){ say("Mark at least one structure first."); changed(); return; }
    if (ss === p[0] && os === p[1]){ ss = os = "show"; ghostPref = false; say("Back to showing everything normally."); }
    else {
      ss = p[0]; os = p[1]; ghostPref = false;
      if (k === "isolate" && E.reveal) E.reveal(marks);
      say({isolate:"Isolated: only the " + marks.length + " selected are shown.", fadeoth:"Others faded to " + Math.round(fade * 100) + " %.", fadesel:"Selected faded to " + Math.round(fade * 100) + " %.",
        hidesel:"Selected hidden.", hlsel:"Selected highlighted."}[k]);
    }
    changed();
  }
  function setFade(v, quiet){
    v = Math.max(0, Math.min(1, +v)); if (!(v === v)) return;
    fade = v; if (!quiet) say("Fade opacity " + Math.round(v * 100) + " %" + (v <= 0.005 ? " (faded structures are not drawn)." : "."));
    changed();
  }
  function setHl(c){ if (/^#[0-9a-f]{6}$/i.test(c)){ hl = c.toLowerCase(); changed(); } }
  function setTint(v){ tintOn = !!v; changed(); }
  /* Invert: the marked set becomes everything else that is eligible (layers, hidden flags, source facet, side filter); Invert again swaps back */
  function eligibleIds(){
    var ids = E.eligible ? E.eligible() : order;
    return ids.filter(has);
  }
  function invert(){
    if (inv){                                              // back: the left-out ids are the marked set again
      var b = baseIds(); marks = []; set = {}; inv = null;
      b.forEach(function(id){ set[id] = 1; marks.push(id); });
      if (!marks.length){ ss = os = "show"; ghostPref = false; }
      say("Inverted back: " + marks.length + " marked."); changed(); return true;
    }
    var left = {}, elig = eligibleIds();
    marks.forEach(function(id){ left[id] = 1; });
    var nm = elig.filter(function(id){ return left[id] !== 1; });
    if (!nm.length){ say(marks.length ? "Everything that is shown is already marked: nothing to invert to." : "Nothing is shown, so there is nothing to mark."); return false; }
    marks = nm; set = {}; nm.forEach(function(id){ set[id] = 1; }); inv = left;
    say("Inverted: the other " + nm.length + " shown structures are marked now; " + Object.keys(left).length + " are left out."); changed(); return true;
  }
  function markVisible(){
    var ids = eligibleIds(), n = 0;
    ids.forEach(function(id){ if (set[id] !== 1 && mark(id, true)) n++; });
    say(n ? n + " visible structures marked." : "Every visible structure is already marked."); changed();
  }
  function markCategory(key, on){
    var ids = ((E.idsOfCategory && key) ? E.idsOfCategory(key) : []).filter(has), n = 0;
    ids.forEach(function(id){ if (mark(id, on)) n++; });
    if (on && n && E.reveal && modeOf() === "only") E.reveal(ids);
    say(n ? n + " structures " + (on ? "marked." : "unmarked.") : "Nothing to " + (on ? "mark" : "unmark") + " in that layer."); changed();
  }
  /* Q256: mark an arbitrary explicit list of ids at once (e.g. a plexus component's downstream nerves) -- same mechanism as
     markCategory, just not tied to a predefined layer category. replace = clear the existing marks first (the normal case for a
     fresh group pick); quiet = skip the status line (the caller reports its own, more specific message). Returns how many marked. */
  function markIds(ids, on, replace, quiet){
    if (replace){ marks = []; set = {}; ss = os = "show"; ghostPref = false; inv = null; }
    var list = (ids || []).filter(has), n = 0;
    list.forEach(function(id){ if (mark(id, on === undefined ? true : on)) n++; });
    if (n && E.reveal && modeOf() === "only") E.reveal(list);
    if (!quiet) say(n ? n + " structures " + (on === false ? "unmarked." : "marked.") : "None of those structures are on this page.");
    changed();
    return n;
  }
  function clearMarks(){ marks = []; set = {}; ss = os = "show"; ghostPref = false; inv = null; say("Marks cleared."); changed(); }
  function resetAll(){
    marks = []; set = {}; ss = os = "show"; ghostPref = false; markMode = false; inv = null;
    if (E.select) E.select(null);
    if (E.clearHover) E.clearHover();
    if (E.resetEngine) E.resetEngine();
    say("Selection reset: everything is shown again (layers, X-ray and the cut plane are unchanged).");
    changed();
  }
  function stOK(s, isOth){ return typeof s === "string" && STATES[s] === 1 && !(isOth && s === "hl"); }
  function applyPack(p){
    p = p || {};
    var src = p.ids || [], ids = src.filter(has), dropped = src.length - ids.length;
    marks = []; set = {}; inv = null;
    if (p.inv){
      var left = {}; ids.forEach(function(id){ left[id] = 1; });
      eligibleIds().forEach(function(id){ if (left[id] !== 1){ set[id] = 1; marks.push(id); } });
      if (marks.length) inv = left;
    } else ids.forEach(function(id){ if (set[id] !== 1){ set[id] = 1; marks.push(id); } });
    if (stOK(p.ss, false) || stOK(p.os, true)){ ss = stOK(p.ss, false) ? p.ss : "show"; os = stOK(p.os, true) ? p.os : "show"; ghostPref = false; }
    else {                                                  // a Q227 pack: mode + ghost
      var gh = !!p.ghost;
      ss = p.mode === "hide" ? (gh ? "ghost" : "hide") : "show";
      os = p.mode === "only" ? (gh ? "ghost" : "hide") : "show";
      ghostPref = false;
    }
    if (typeof p.fade === "number" && p.fade >= 0 && p.fade <= 1) fade = p.fade;
    if (typeof p.hl === "string" && /^#[0-9a-f]{6}$/i.test(p.hl)) hl = p.hl.toLowerCase();
    fixStates();
    if (modeOf() === "only" && E.reveal) E.reveal(marks);
    return dropped;
  }
  /* ---- saved sets ---- */
  function listSets(){
    if (!setsEl) return;
    var h = "", ks = Object.keys(data.sets).sort();
    ks.forEach(function(k){ h += '<option value="' + esc(k) + '">' + esc(k) + " (" + data.sets[k].ids.length + (data.sets[k].inv ? ", inverse" : "") + ")</option>"; });
    if (!ks.length) h = '<option value="">(none saved yet)</option>';
    setsEl.innerHTML = h;
    storeNote();
  }
  function save(nm){
    nm = String(nm == null ? (nameEl && nameEl.value) : nm).trim().slice(0, 40);
    if (!marks.length){ say("Nothing is marked, so there is nothing to save."); return false; }
    if (!nm) nm = "Selection " + (Object.keys(data.sets).length + 1);
    var existed = Object.prototype.hasOwnProperty.call(data.sets, nm);
    data.sets[nm] = pack();
    persistLast(); listSets();
    if (setsEl) setsEl.value = nm;
    say((existed ? "Updated '" : "Saved '") + nm + "' (" + (inv ? "inverse of " + baseIds().length + " left out; " : "") + marks.length + " structures)" + (storageOK ? "." : ", for this session only: storage is blocked here, use Export to keep it."));
    return true;
  }
  function load(nm){
    nm = nm == null ? (setsEl && setsEl.value) : nm;
    if (!nm || !Object.prototype.hasOwnProperty.call(data.sets, nm)){ say("Choose a saved selection first."); return false; }
    var dropped = applyPack(data.sets[nm]);
    say("Loaded '" + nm + "': " + marks.length + " marked" + (dropped ? " (" + dropped + " not in this model were skipped)" : "") + ".");
    changed();
    return true;
  }
  function del(nm){
    nm = nm == null ? (setsEl && setsEl.value) : nm;
    if (!nm || !Object.prototype.hasOwnProperty.call(data.sets, nm)){ say("Choose a saved selection first."); return false; }
    delete data.sets[nm]; persistLast(); listSets(); say("Deleted '" + nm + "'.");
    return true;
  }
  /* ---- export / import / link ---- */
  function exportText(){
    var o = {nmsk_selection:1, model:MODEL, sets:data.sets, current:pack()};
    var t = JSON.stringify(o, null, 1);
    if (ioEl) ioEl.value = t;
    return t;
  }
  function hashOf(p){      // #nmsksel=model~mode~ghost~ids[~selState.othState.fade%.inverse.highlight] (the last field is new in Q232; older links have four)
    return "#nmsksel=" + [encodeURIComponent(MODEL), p.mode, p.ghost ? 1 : 0, p.ids.map(encodeURIComponent).join(","),
      [p.ss || "show", p.os || "show", Math.round((p.fade == null ? 0.15 : p.fade) * 100), p.inv ? 1 : 0, String(p.hl || "#ffb000").replace("#", "")].join(".")].join("~");
  }
  function parseHash(h){
    var m = /nmsksel=([^&]*)/.exec(h || ""); if (!m) return null;
    var f = m[1].split("~"); if (f.length < 4) return null;
    var ids = f[3] ? f[3].split(",").map(function(s){ try { return decodeURIComponent(s); } catch (err){ return s; } }) : [];
    var model; try { model = decodeURIComponent(f[0]); } catch (err){ model = f[0]; }
    var pk = {ids:ids, mode:f[1], ghost:f[2] === "1"};
    if (f[4]){
      var q = f[4].split(".");
      if (q.length >= 4){ pk.ss = q[0]; pk.os = q[1]; pk.fade = Math.max(0, Math.min(100, parseFloat(q[2]))) / 100; pk.inv = q[3] === "1"; if (q[4]) pk.hl = "#" + q[4]; }
    }
    return {model:model, pack:pk};
  }
  function importText(t){
    t = String(t == null ? (ioEl && ioEl.value) : t).trim();
    if (!t){ say("Paste exported text (or a link) into the box first."); return false; }
    var added = 0, dropped = 0, o = null;
    if (t.indexOf("nmsksel=") >= 0){
      var ph = parseHash(t);
      if (!ph){ say("That link is not a selection link."); return false; }
      if (ph.model !== MODEL) say("This link is for another model (" + ph.model + "); only the ids that exist here are used.");
      dropped = applyPack(ph.pack); changed();
      say("Imported " + marks.length + " marked from the link" + (dropped ? " (" + dropped + " unknown here)" : "") + ".");
      return true;
    }
    try { o = JSON.parse(t); } catch (err){ say("That text is not valid JSON."); return false; }
    if (Array.isArray(o)) o = {sets:{"Imported":{ids:o, mode:"all", ghost:false}}};
    if (!o || typeof o !== "object" || (!o.sets && !o.current)){ say("That text is not an exported selection."); return false; }
    Object.keys(o.sets || {}).forEach(function(k){
      var s = o.sets[k]; if (!s || !Array.isArray(s.ids)) return;
      var ids = s.ids.filter(function(x){ return typeof x === "string" && has(x); }), nm = String(k).slice(0, 40);
      dropped += s.ids.length - ids.length;
      if (!ids.length) return;
      var one = {ids:ids, mode:s.mode === "only" || s.mode === "hide" ? s.mode : "all", ghost:!!s.ghost};
      if (stOK(s.ss, false)) one.ss = s.ss; if (stOK(s.os, true)) one.os = s.os;
      if (typeof s.fade === "number" && s.fade >= 0 && s.fade <= 1) one.fade = s.fade;
      if (typeof s.hl === "string" && /^#[0-9a-f]{6}$/i.test(s.hl)) one.hl = s.hl.toLowerCase();
      if (s.inv) one.inv = true;
      data.sets[nm] = one; added++;
    });
    persistLast(); listSets();
    say("Imported " + added + " saved selection" + (added === 1 ? "" : "s") + (dropped ? "; " + dropped + " ids are not in this model and were skipped" : "") +
        (o.model && o.model !== MODEL ? " (exported from " + o.model + ")" : "") + ".");
    return added > 0;
  }
  function copyLink(){
    if (!marks.length){ say("Nothing is marked."); return ""; }
    var base = ""; try { base = String(location.href).split("#")[0]; } catch (err){}
    var url = base + hashOf(pack());
    if (ioEl){ ioEl.value = url; }
    var done = function(){ say("Link copied (" + marks.length + " marked)."); }, fail = function(){ say("Copy the link from the box below."); var d = $("sel-share"); if (d) d.open = true; };
    try { if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, fail); else fail(); } catch (err){ fail(); }
    return url;
  }
  /* ---- clicks in 3D ---- */
  function consumeClick(e){
    if (suppress){ suppress = false; return true; }
    var multi = markMode || (e && (e.shiftKey || e.ctrlKey || e.metaKey));
    if (!multi) return false;
    var id = E.pickId ? E.pickId(e) : null;
    if (id) toggle(id, false);
    else say("Nothing under the pointer.");
    return true;
  }
  var lp = null;
  function lpCancel(){ if (lp){ clearTimeout(lp.t); lp = null; } }
  function lpDown(e){
    suppress = false;
    if (e.pointerType === "mouse"){ lpCancel(); return; }
    if (lp){ lpCancel(); return; }                          // a second finger: pinch / pan, not a long press
    var x = e.clientX, y = e.clientY;
    lp = {x:x, y:y, t:setTimeout(function(){
      lp = null;
      var id = E.pickId ? E.pickId({clientX:x, clientY:y}) : null;
      if (id){ suppress = true; toggle(id, false); try { if (navigator.vibrate) navigator.vibrate(18); } catch (err){} }
    }, LP_MS)};
  }
  function lpMove(e){ if (lp && Math.hypot(e.clientX - lp.x, e.clientY - lp.y) > 9) lpCancel(); }
  /* ---- wiring ---- */
  function bind(id, f){ var e = $(id); if (e) e.addEventListener("click", f); }
  bind("sel-markcur", function(){ var s = E.selected && E.selected(); if (s && has(s)){ if (set[s] !== 1) toggle(s, true); else say(name(s) + " is already marked."); } else say("Select a structure first (click it or pick it from the list)."); });
  bind("sel-markall", function(){
    var ids = (E.listIds ? E.listIds() : []).filter(has), n = 0;
    ids.forEach(function(id){ if (set[id] !== 1){ mark(id, true); n++; } });
    if (n && E.reveal) E.reveal(ids);
    say(n ? n + " structures from the list marked." : "No new structures in the list."); changed();
  });
  bind("sel-clear", clearMarks);
  bind("sel-only", function(){ setMode("only"); });
  bind("sel-hide", function(){ setMode("hide"); });
  bind("sel-ghost", function(){ setGhost(); });
  bind("sel-invert", invert);
  bind("sel-markvis", markVisible);
  bind("sel-markcat", function(){ markCategory(catEl && catEl.value, true); });
  bind("sel-unmarkcat", function(){ markCategory(catEl && catEl.value, false); });
  Array.prototype.forEach.call(document.querySelectorAll(".ss-st[data-g]"), function(b){ b.addEventListener("click", function(){ setGroup(b.getAttribute("data-g"), b.getAttribute("data-s")); }); });
  Object.keys(PRESETS).forEach(function(k){ bind("sel-p-" + k, function(){ preset(k); }); });
  if (fadeEl) fadeEl.addEventListener("input", function(){ setFade(parseFloat(fadeEl.value) / 100, true); });
  if (hlEl) hlEl.addEventListener("input", function(){ setHl(hlEl.value); });
  if (tintEl) tintEl.addEventListener("change", function(){ setTint(tintEl.checked); });
  bind("sel-markmode", function(){ markMode = !markMode; say(markMode ? "Click or tap structures on the model to mark / unmark them." : "Mark by clicking is off."); ui(); });
  bind("sel-reset", resetAll);
  bind("sel-save", function(){ save(); });
  bind("sel-load", function(){ load(); });
  bind("sel-del", function(){ del(); });
  bind("sel-export", function(){ exportText(); say("Copy this text to keep or move your saved selections."); var d = $("sel-share"); if (d) d.open = true; });
  bind("sel-import", function(){ importText(); });
  bind("sel-link", copyLink);
  if (remEl) remEl.addEventListener("change", function(){ persistLast(); say(remEl.checked ? "The last selection is remembered." : "The last selection is no longer remembered."); });
  if (chipsEl) chipsEl.addEventListener("click", function(e){
    var b = e.target && e.target.closest ? e.target.closest("button[data-id]") : null;
    if (b){ var id = b.getAttribute("data-id"); mark(id, false); say(name(id) + " unmarked."); changed(); return; }
    var x = e.target && e.target.closest ? e.target.closest("button[data-exc]") : null;
    if (x){ var xi = x.getAttribute("data-exc"); mark(xi, true); say(name(xi) + " marked too."); changed(); }
  });
  if (nameEl) nameEl.addEventListener("keydown", function(e){ if (e.key === "Enter"){ e.preventDefault(); save(); } });
  if (E.canvas){
    E.canvas.addEventListener("pointerdown", lpDown, true);
    E.canvas.addEventListener("pointermove", lpMove, true);
    E.canvas.addEventListener("pointerup", lpCancel, true);
    E.canvas.addEventListener("pointercancel", lpCancel, true);
  }
  function tb(id, label, title, f){
    if (!E.toolbar) return null;
    var b = document.createElement("button");
    b.type = "button"; b.id = id; b.className = (E.toolClass || "") + " ss-tb"; b.textContent = label; b.title = title; b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", f); E.toolbar.appendChild(b); return b;
  }
  tbMark = tb("t-mark", "Mark", "While on, a click or tap on the model marks / unmarks the structure under it (Shift/Ctrl-click or a long press does the same at any time)", function(){ markMode = !markMode; say(markMode ? "Click or tap structures on the model to mark / unmark them." : "Mark by clicking is off."); ui(); });
  tbOnly = tb("t-only", "Only marked", "Show only the marked structures", function(){ setMode("only"); });
  tbInv = tb("t-invert", "Invert", "Swap: mark everything else that is shown and unmark the marked ones (key I); press again to swap back", invert);
  if (tbInv) tbInv.hidden = true;
  var catEl = $("sel-cat");
  function fillCats(){
    if (!catEl || !E.categories) return;
    var h = ""; E.categories().forEach(function(c){ h += '<option value="' + esc(c.key) + '">' + esc(c.label) + (c.count != null ? " (" + c.count + ")" : "") + "</option>"; });
    catEl.innerHTML = h;
  }
  /* keys: I = invert, F = fade the others (Shift+F: fade the selected), H = hide the selected (Shift+H: hide the others = isolate). Only while something is
     marked (the Z page's own i / f / h keys, which act on the one open structure, keep working otherwise) and never while typing */
  function onKey(e){
    if (e.ctrlKey || e.metaKey || e.altKey || e.repeat || !marks.length) return;
    var t = e.target, tag = t && t.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || (t && t.isContentEditable)) return;
    var k = String(e.key || "").toLowerCase(), used = true;
    if (k === "i") invert();
    else if (k === "f") setGroup(e.shiftKey ? "sel" : "oth", "fade");
    else if (k === "h") setGroup(e.shiftKey ? "oth" : "sel", "hide");
    else used = false;
    if (used){ e.preventDefault(); e.stopImmediatePropagation(); }
  }
  window.addEventListener("keydown", onKey, true);
  function layout(){ var r = document.documentElement; if (r && r.classList) r.classList.toggle("ss-phone", !!(E.isPhone && E.isPhone())); }
  window.addEventListener("resize", layout);
  /* ---- start: stored sets, then (in this order of priority) a link in the address, the remembered last selection ---- */
  var stored = storeRead();
  if (stored && stored.v === 1){
    data.sets = stored.sets && typeof stored.sets === "object" ? stored.sets : {};
    data.last = stored.last || null; data.remember = stored.remember !== false;
    Object.keys(data.sets).forEach(function(k){ var s = data.sets[k]; if (!s || !Array.isArray(s.ids)) delete data.sets[k]; });
  }
  if (remEl) remEl.checked = data.remember;
  if (stored && stored.tint === false) tintOn = false;
  layout(); fillCats(); listSets(); renderChips(); ui();
  var restored = "";
  try {
    var ph = parseHash(location.hash);
    if (ph && (ph.model === MODEL)){ applyPack(ph.pack); restored = "Opened the selection from the link: " + marks.length + " marked."; }
    else if (data.remember && data.last && data.last.ids && (data.last.ids.length || data.last.inv)){ applyPack(data.last); restored = "Restored your last selection: " + marks.length + " marked" + (modeOf() === "all" ? "." : modeOf() === "only" ? ", showing only those." : ", hidden."); }
  } catch (err){}
  if (restored){ say(restored); changed(); } else storeNote();
  return {
    rule:rule, look:stateOf, isMarked:function(id){ return set[id] === 1; }, tinted:tinted, ghosting:ghosting, translucent:translucent, active:activeState,
    fadeAlpha:function(){ return fade; }, hlHex:hlHex, markButton:function(id){
      var b = document.createElement("button");
      b.type = "button"; b.className = "ss-mk"; b.textContent = "✓"; b.setAttribute("data-id", id);
      b.setAttribute("aria-pressed", String(set[id] === 1)); b.setAttribute("aria-label", "Mark " + name(id)); b.title = "Mark / unmark for the selection";
      b.addEventListener("click", function(e){ e.stopPropagation(); toggle(id, true); b.setAttribute("aria-pressed", String(set[id] === 1)); });
      return b;
    },
    consumeClick:consumeClick, layout:layout, toggle:toggle, mark:function(id, on){ var r = mark(id, on); changed(); return r; },
    setMode:setMode, setGhost:setGhost, setGroup:setGroup, preset:preset, setFade:setFade, setHl:setHl, setTint:setTint, invert:invert, markVisible:markVisible,
    markCategory:markCategory, markIds:markIds, onKey:onKey, clear:clearMarks, reset:resetAll, save:save, load:load, del:del, exportText:exportText, importText:importText,
    link:function(){ return hashOf(pack()); }, copyLink:copyLink, restored:restored,
    state:function(){ return {marks:marks.slice(), mode:modeOf(), ghost:ghostOf(), sel:ss, oth:os, fade:fade, hl:hl, inverted:!!inv, left:baseIds(), tint:tintOn, markMode:markMode, storageOK:storageOK, sets:Object.keys(data.sets).sort(), model:MODEL, remember:data.remember}; }
  };
}
