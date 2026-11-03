/* Q309: one plain ON / OFF button per SYSTEM, showing its state and its own structure count.
   Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button".
   The market pattern, quoted in docs/research/Q301_controls_and_render_styles.md 9: Complete Anatomy -- "Press and
   hold a system's icon to switch it fully on or off", "all 12 systems can be toggled incrementally from the menu";
   Visible Body -- "toggling the skeletal system off and back on restores the full skeleton". We take the plain tap
   (the project's taps-over-press-and-hold rule) and the printed count.
   It does NOT write the engines' per-category table. That table already has its own rows, with their own opacity
   sliders and solo buttons, and the whole-body depth peel writes it too -- a second writer would fight them. A system
   switched off here adds its structures to Q309's own veto set instead, which composes with the category rows, the
   presets, the solo, the cut and the whole-body peel exactly as a per-structure hide does.
   The engine supplies E: {off(ids), drawn(), drawnIn(cats), redraw()} and NMSKSysMap the systems.
     NMSKSysToggle.start(E, {map, history, showall, push})
     .systems()  .isOn(key)  .set(key, v)  .allOn()  .offKeys()  .ids()  .element()  .state() */
var NMSKSysToggle = (function(){
  "use strict";
  var E = null, M = null, hist = null, push = null, box = null, row = null, note = null, on = false;
  var OFF = {}, btns = {};
  function ids(){
    var out = [], seen = {};
    Object.keys(OFF).forEach(function(k){
      if (!OFF[k]) return;
      M.ids(k).forEach(function(i){ if (!seen[i]){ seen[i] = 1; out.push(i); } });
    });
    return out;
  }
  function offKeys(){ return Object.keys(OFF).filter(function(k){ return OFF[k]; }).sort(); }
  function ui(){
    M.systems().forEach(function(s){
      var b = btns[s.key]; if (!b) return;
      var up = !OFF[s.key];
      b.setAttribute("aria-pressed", String(up));
      b.classList.toggle("off", !up);
      b.querySelector(".sy-st").textContent = up ? "on" : "off";
    });
    if (note) note.textContent = offKeys().length
      ? offKeys().length + " system" + (offKeys().length === 1 ? "" : "s") + " switched off"
      : "every system is on";
  }
  function apply(){ if (push) push(); else { E.off(ids()); if (E.redraw) E.redraw(); } ui(); }
  function set(key, v, quiet){
    if (!M.get(key)) return false;
    var want = !v;                                        /* OFF[key] is "switched off" */
    if (!!OFF[key] === want){ ui(); return false; }
    OFF[key] = want;
    apply();
    if (!quiet){
      if (hist && hist.schedule) hist.schedule();
      if (window.NMSKShowAll && NMSKShowAll.refresh) NMSKShowAll.refresh();
      if (window.NMSKCombos && NMSKCombos.refresh) NMSKCombos.refresh();
    }
    return true;
  }
  var api = {
    start:function(eng, opt){
      opt = opt || {};
      if (on) return api;
      E = eng || null; M = opt.map || window.NMSKSysMap || null; push = opt.push || null;
      if (!E || !M || !M.ready()) return api;
      hist = opt.history || window.NMSKHistory || null;
      box = document.createElement("div");
      box.id = "sy-box"; box.className = "sy-box";
      box.setAttribute("role", "group"); box.setAttribute("aria-label", "Show or hide a whole system");
      var lab = document.createElement("span"); lab.className = "sy-l"; lab.textContent = "Systems";
      box.appendChild(lab);
      row = document.createElement("div"); row.className = "sy-row";
      M.systems().forEach(function(s){
        var b = document.createElement("button");
        b.type = "button"; b.className = "sy-b q301-b"; b.id = "sy-" + s.key;
        b.setAttribute("data-sys", s.key); b.setAttribute("aria-pressed", "true");
        b.title = s.label + " — " + s.n + " structures on this page; one tap switches the whole system off and on (one Undo step)";
        b.innerHTML = '<span class="sy-n"></span><span class="sy-c mono"></span><span class="sy-st"></span>';
        b.querySelector(".sy-n").textContent = s.label;
        b.querySelector(".sy-c").textContent = s.n;
        b.addEventListener("click", function(e){ e.stopPropagation(); set(s.key, !!OFF[s.key]); });
        row.appendChild(b); btns[s.key] = b;
      });
      box.appendChild(row);
      note = document.createElement("output"); note.id = "sy-state"; note.className = "sy-o";
      note.setAttribute("aria-live", "polite"); box.appendChild(note);
      var n = document.createElement("span"); n.className = "sy-note";
      n.innerHTML = '<p class="nmsk-tip">One <b>on / off</b> button per system, with the number of structures it holds on this page. ' +
        'A system is a set of this page’s own tissue categories (' +
        M.systems().map(function(s){ return "<b>" + s.label + "</b> = " + s.cats.join(" + "); }).join("; ") +
        '). Switching one off does <b>not</b> touch the tissue-layer table or its opacity sliders &mdash; it is a veto of its own, so it combines with them, with the presets and with every depth peel. One tap is <b>one Undo step</b>, and Show everything brings it back.</p>';
      box.appendChild(n);
      if (opt.toolbar) opt.toolbar.appendChild(box);
      on = true; ui();
      return api;
    },
    /* Q300's "Show everything": one path, named for what it did */
    source:function(){
      return {key:"q309sys",
        label:function(){ var k = offKeys(); return "systems off: " + k.map(function(x){ var s = M.get(x); return s ? s.label.toLowerCase() : x; }).join(", "); },
        active:function(){ return on && offKeys().length > 0; },
        clear:function(){ OFF = {}; apply(); },
        drive:function(){ var s = M.systems()[0]; if (s){ OFF[s.key] = true; apply(); } }};
    },
    systems:function(){ return M ? M.systems() : []; },
    isOn:function(k){ return !OFF[k]; },
    set:set,
    allOn:function(){ if (!offKeys().length) return false; OFF = {}; apply(); return true; },
    offKeys:offKeys, ids:ids, element:function(){ return box; }, refresh:ui,
    /* the history travels as the sorted list of switched-off systems: a string, so snapshots compare as strings */
    get:function(){ return offKeys().join(","); },
    put:function(v){ OFF = {}; String(v || "").split(",").forEach(function(k){ if (k) OFF[k] = true; }); apply(); },
    state:function(){ return {on:on, off:offKeys(), n:M ? M.systems().length : 0}; }
  };
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKSysToggle;
