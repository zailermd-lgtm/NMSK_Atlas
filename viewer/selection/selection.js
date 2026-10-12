/* Marked structures, "show only marked", saved selection sets (Q227). One controller for both viewers. The engine is reached only through the adaptor E:
   modelId() items() -> [{id,name}] (one per structure, in list order)   refresh() re-apply visibility   selected() select(id)   reveal(ids) (switch the layers /
   source classes / hide flags of these structures on)   listIds() (ids the search box shows)   pickId(ev) (cap-aware)   clearHover()   resetEngine() (the
   engine's own isolation / hide / fade / solo / box)   canvas   toolbar + toolClass   isPhone()   [frame(ids)].
   The engine asks rule(id): "" = as the layers say, "hide" = not drawn, "ghost" = drawn as a faint ghost and not pickable; isMarked(id) tints a marked
   structure. A selection composes with everything else because it only ADDS a veto: the layer toggles, the source facet, X-ray, the cut plane + slab and the
   parts markers all still apply to what it leaves.
   Persistence: localStorage (try/catch; keyed per model because structure ids differ between models) with an in-memory fallback, plus export / import as text
   and a link (#nmsksel=...). */
function NMSKSelect(E){
  "use strict";
  var $ = function(id){ return document.getElementById(id); };
  var MODEL = String(E.modelId()), KEY = "nmsk.sel.v1:" + MODEL, LP_MS = 520, MARKLIMIT = 400;
  var marks = [], set = {}, mode = "all", ghost = false, markMode = false, storageOK = true, suppress = false;
  var data = {v:1, model:MODEL, sets:{}, last:null, remember:true};
  var names = {}, order = [];
  E.items().forEach(function(it){ if (!(it.id in names)){ names[it.id] = it.name || it.id; order.push(it.id); } });
  var sec = $("sel-sec"), chipsEl = $("sel-chips"), cntEl = $("sel-count"), statusEl = $("sel-status"), nameEl = $("sel-name"), setsEl = $("sel-sets"),
      ioEl = $("sel-io"), storeEl = $("sel-store"), remEl = $("sel-remember");
  var tbMark = null, tbOnly = null;

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
  function pack(){ return {ids:marks.slice(), mode:mode, ghost:ghost}; }
  function persistLast(){
    data.remember = !remEl || !!remEl.checked;
    data.last = data.remember ? pack() : null;
    storeWrite();
  }
  /* ---- the selection itself ---- */
  function rule(id){
    if (mode === "all" || !marks.length) return "";
    var m = set[id] === 1, hideIt = mode === "only" ? !m : m;
    return hideIt ? (ghost ? "ghost" : "hide") : "";
  }
  function ghosting(){ return ghost && mode !== "all" && marks.length > 0; }
  function activeState(){ return marks.length > 0 || mode !== "all" || ghost; }
  function syncButtons(){
    var l = document.querySelectorAll(".ss-mk[data-id]");
    for (var i = 0; i < l.length; i++) l[i].setAttribute("aria-pressed", String(set[l[i].getAttribute("data-id")] === 1));
  }
  function renderChips(){
    if (chipsEl){
      var h = "", n = Math.min(marks.length, MARKLIMIT);
      for (var i = 0; i < n; i++) h += '<span class="ss-chip"><span class="t" title="' + esc(name(marks[i])) + '">' + esc(name(marks[i])) +
        '</span><button type="button" data-id="' + esc(marks[i]) + '" aria-label="Unmark ' + esc(name(marks[i])) + '" title="Unmark">&times;</button></span>';
      if (marks.length > n) h += '<span class="ss-chip"><span class="t">+' + (marks.length - n) + ' more</span></span>';
      chipsEl.innerHTML = h;
    }
    if (cntEl) cntEl.textContent = String(marks.length);
    if (sec && sec.classList) sec.classList.toggle("has-marks", marks.length > 0);
  }
  function ui(){
    var n = marks.length;
    function pr(id, v){ var e = $(id); if (e) e.setAttribute("aria-pressed", String(v)); }
    pr("sel-only", mode === "only"); pr("sel-hide", mode === "hide"); pr("sel-ghost", ghost); pr("sel-markmode", markMode);
    ["sel-only", "sel-hide", "sel-clear"].forEach(function(id){ var e = $(id); if (e) e.disabled = !n; });
    if (tbMark){ tbMark.setAttribute("aria-pressed", String(markMode)); tbMark.textContent = n ? "Mark · " + n : "Mark"; }
    if (tbOnly){ tbOnly.setAttribute("aria-pressed", String(mode === "only")); tbOnly.hidden = !n; tbOnly.textContent = mode === "only" ? "Show all" : "Only marked";
      tbOnly.title = mode === "only" ? "Show everything again (the marks stay)" : "Show only the marked structures"; }
    if (document.body && document.body.classList) document.body.classList.toggle("ss-marking", markMode);
  }
  function changed(){
    renderChips(); syncButtons(); ui(); persistLast(); E.refresh();
  }
  function mark(id, on){
    if (!has(id)) return false;
    var is = set[id] === 1;
    if (on === undefined) on = !is;
    if (on && !is){ set[id] = 1; marks.push(id); }
    else if (!on && is){ delete set[id]; marks.splice(marks.indexOf(id), 1); if (!marks.length && mode !== "all"){ mode = "all"; ghost = false; } }
    else return false;
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
    if (m !== "all" && !marks.length){ say("Mark at least one structure first."); mode = "all"; changed(); return; }
    mode = (mode === m) ? "all" : m;
    if (mode === "all") ghost = ghost && false;
    if (mode === "only" && E.reveal) E.reveal(marks);       // an explicit choice beats a switched-off layer
    say(mode === "only" ? "Showing only the " + marks.length + " marked." : mode === "hide" ? "Marked structures hidden." : "Showing everything again.");
    changed();
  }
  function setGhost(v){
    ghost = v === undefined ? !ghost : !!v;
    say(ghost ? "The rest is drawn as faint ghosts." : "Ghosting off.");
    changed();
  }
  function clearMarks(){ marks = []; set = {}; mode = "all"; ghost = false; say("Marks cleared."); changed(); }
  function resetAll(){
    marks = []; set = {}; mode = "all"; ghost = false; markMode = false;
    if (E.select) E.select(null);
    if (E.clearHover) E.clearHover();
    if (E.resetEngine) E.resetEngine();
    say("Selection reset: everything is shown again (layers, X-ray and the cut plane are unchanged).");
    changed();
  }
  function applyPack(p){
    var ids = (p && p.ids || []).filter(has), dropped = ((p && p.ids) || []).length - ids.length;
    marks = []; set = {};
    ids.forEach(function(id){ if (set[id] !== 1){ set[id] = 1; marks.push(id); } });
    mode = marks.length && (p && (p.mode === "only" || p.mode === "hide")) ? p.mode : "all";
    ghost = marks.length > 0 && mode !== "all" && !!(p && p.ghost);
    if (mode === "only" && E.reveal) E.reveal(marks);
    return dropped;
  }
  /* ---- saved sets ---- */
  function listSets(){
    if (!setsEl) return;
    var h = "", ks = Object.keys(data.sets).sort();
    ks.forEach(function(k){ h += '<option value="' + esc(k) + '">' + esc(k) + " (" + data.sets[k].ids.length + ")</option>"; });
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
    say((existed ? "Updated '" : "Saved '") + nm + "' (" + marks.length + " structures)" + (storageOK ? "." : ", for this session only: storage is blocked here, use Export to keep it."));
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
  function hashOf(p){ return "#nmsksel=" + [encodeURIComponent(MODEL), p.mode, p.ghost ? 1 : 0, p.ids.map(encodeURIComponent).join(",")].join("~"); }
  function parseHash(h){
    var m = /nmsksel=([^&]*)/.exec(h || ""); if (!m) return null;
    var f = m[1].split("~"); if (f.length < 4) return null;
    var ids = f[3] ? f[3].split(",").map(function(s){ try { return decodeURIComponent(s); } catch (err){ return s; } }) : [];
    var model; try { model = decodeURIComponent(f[0]); } catch (err){ model = f[0]; }
    return {model:model, pack:{ids:ids, mode:f[1], ghost:f[2] === "1"}};
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
      data.sets[nm] = {ids:ids, mode:s.mode === "only" || s.mode === "hide" ? s.mode : "all", ghost:!!s.ghost}; added++;
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
    if (b){ var id = b.getAttribute("data-id"); mark(id, false); say(name(id) + " unmarked."); changed(); }
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
  layout(); listSets(); renderChips(); ui();
  var restored = "";
  try {
    var ph = parseHash(location.hash);
    if (ph && (ph.model === MODEL)){ applyPack(ph.pack); restored = "Opened the selection from the link: " + marks.length + " marked."; }
    else if (data.remember && data.last && data.last.ids && data.last.ids.length){ applyPack(data.last); restored = "Restored your last selection: " + marks.length + " marked" + (mode === "all" ? "." : mode === "only" ? ", showing only those." : ", hidden."); }
  } catch (err){}
  if (restored){ say(restored); changed(); } else storeNote();
  return {
    rule:rule, isMarked:function(id){ return set[id] === 1; }, ghosting:ghosting, active:activeState, markButton:function(id){
      var b = document.createElement("button");
      b.type = "button"; b.className = "ss-mk"; b.textContent = "✓"; b.setAttribute("data-id", id);
      b.setAttribute("aria-pressed", String(set[id] === 1)); b.setAttribute("aria-label", "Mark " + name(id)); b.title = "Mark / unmark for the selection";
      b.addEventListener("click", function(e){ e.stopPropagation(); toggle(id, true); b.setAttribute("aria-pressed", String(set[id] === 1)); });
      return b;
    },
    consumeClick:consumeClick, layout:layout, toggle:toggle, mark:function(id, on){ var r = mark(id, on); changed(); return r; },
    setMode:setMode, setGhost:setGhost, clear:clearMarks, reset:resetAll, save:save, load:load, del:del, exportText:exportText, importText:importText,
    link:function(){ return hashOf(pack()); }, copyLink:copyLink, restored:restored,
    state:function(){ return {marks:marks.slice(), mode:mode, ghost:ghost, markMode:markMode, storageOK:storageOK, sets:Object.keys(data.sets).sort(), model:MODEL, remember:data.remember}; }
  };
}
