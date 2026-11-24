/* Q382: what the owner asked for after testing the live page --
     "the dimensions window (the zoom chip) should be visible on every size change for 10 seconds and then disappear; in Settings it
      can be changed to permanent, or the delay changed"  and
     "allow moving the different boxes on the screen by dragging -- drag and save the state -- and also in SETTINGS".
   Moving boxes already exists (Q305 / Q335, viewer/q305/move.js: the six-dot handle, the three-dots menu, a per-page store). This module
   adds to it from the outside, by selector, and does not restructure any panel:
     - the floating cards the planning mode builds into its shell (#mode-main .mc-right / .mc-left / .mc-pick / .mc-safe) and its bottom
       dock (#mode-pills) become movable boxes: dragged by their title row (the dock: by its empty edge, mouse only), never by a button;
     - the title row of the boxes that already have a handle (name card, labels, legend, pose, slices, attachments) drags too;
     - a Settings section in the circled-i drawer (and a "Settings" button in the View group): zoom chip mode (seconds / always),
       "Lock panels" (dragging off), "Reset layout", "Show zoom chip", "Zoom 1:1".
   Positions are saved by NMSKMove per box and per screen class (desktop offsets / phone slots) in localStorage, in try / catch;
   moving a box is not an undo step. Docked sheets on a phone (the planning cards are bottom sheets there) stay where the page puts them.
     NMSKLayout.state()  .open()  .reset() */
var NMSKLayout = (function(){
  "use strict";
  var tries = 0, timer = 0, ready = false, sec = null;
  function q(sel){ return function(){ return document.querySelector(sel); }; }
  function ph(){ return !!(window.NMSKMove && NMSKMove.phone()); }
  var SPEC = [
    {key:"m-plan", label:"the planning panel",    el:q("#mode-main .mc-right"), nogrip:true, head:true, band:46, skip:ph},
    {key:"m-dist", label:"the distance card",     el:q("#mode-main .mc-left"),  nogrip:true, head:".mc-title", skip:ph},
    {key:"m-pick", label:"the structure picker",  el:q("#mode-main .mc-pick"),  nogrip:true, head:".mc-title", skip:ph},
    {key:"m-safe", label:"the safety card",       el:q("#mode-main .mc-safe"),  nogrip:true, head:".mc-title", skip:ph},
    {key:"m-dock", label:"the bottom dock",       el:q("#mode-pills"),          nogrip:true, head:function(e){ return e; }, mouseOnly:true}
  ];
  /* boxes that have their own handle already: their title row drags as well */
  var HEADS = {qcard:".qc-head", labels:".lb-head", legend:".lg-head", pose:".pz-head", slices:".xsp-head", attach:".pp-h", cut:".cp-head"};

  function mount(){
    var M = window.NMSKMove;
    if (!M || !M.state || !M.state().on) return false;
    SPEC.forEach(function(s){ M.add(s); });
    Object.keys(HEADS).forEach(function(k){ var b = M.box(k); if (b && !b.head) b.head = HEADS[k]; });
    var I = window.NMSKInfo;
    /* the circled i and the control bar are hidden while a mode is on, so the settings live in their own small panel; the i's section
       and the View group only open it, and the mode bar gets a gear (Hebrew label: that bar is Hebrew) */
    if (I && I.add){
      var st = document.createElement("div"); st.className = "q382-set";
      st.innerHTML = '<p>Every setting of the page, by topic, and a search for a setting by name.</p><div class="q382-row"><button type="button" id="q382-open">Settings tree</button><button type="button" id="q393-open-find">Search settings</button></div>';
      st.querySelector("#q382-open").addEventListener("click", function(){ api.open(); });
      st.querySelector("#q393-open-find").addEventListener("click", function(){ api.find(); });
      I.add({key:"settings", title:"Settings", order:44, el:st});
    }
    gear();
    var G = window.NMSKGroups;
    if (G && G.addTo){
      G.addTo("view", {label:"Settings", id:"q382-settings", title:"All the settings, by topic (a tree)",
        run:function(){ api.open(); }, label2:"All the settings, by topic: open a topic, tap a setting to go to it."});
      G.addTo("view", {label:"Search settings", id:"q393-settings-find", title:"Find a setting by name (not a structure: that is Search)",
        run:function(){ api.find(); }});
    }
    setInterval(gear, 1500);
    fitStart();                                  /* the mode bar is built by the modes module, maybe later or again */
    ready = true; return true;
  }
  function gear(){
    var end = document.getElementById("mb-end"), old = document.getElementById("q382-gear");
    /* on a phone the mode bar has no room (the gear measurably cut the header name short): Settings are reached from the anatomy view there */
    if (window.innerWidth <= 560){ if (old && old.parentNode) old.parentNode.removeChild(old); return; }
    if (!end || old) return;
    var g = document.createElement("button"); g.type = "button"; g.id = "q382-gear"; g.className = "mb-x q382-gear";
    g.title = "הגדרות: פריסה וזום (Settings)"; g.setAttribute("aria-label", "הגדרות");
    g.innerHTML = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/></svg>';
    g.addEventListener("click", function(e){ e.stopPropagation(); if (pan && !pan.hidden) api.close(); else api.open(); });
    end.insertBefore(g, end.firstChild);
  }
  var pan = null;
  function panel(){
    if (pan) return pan;
    pan = document.createElement("div"); pan.id = "q382-panel"; pan.className = "q382-panel"; pan.hidden = true;
    pan.setAttribute("role", "dialog"); pan.setAttribute("aria-label", "Settings");
    var h = document.createElement("div"); h.className = "q382-ph";
    h.innerHTML = '<b>Settings</b><button type="button" id="q382-x" aria-label="Close" title="Close">&times;</button>';
    h.querySelector("button").addEventListener("click", function(){ api.close(); });
    pan.appendChild(h); pan.appendChild(finder());
    var lz = document.createElement("details"); lz.className = "q393-lz"; lz.id = "q393-lz";
    lz.open = true; lz.innerHTML = '<summary>Layout, zoom chip and text size</summary>'; lz.appendChild(section());
    pan.appendChild(lz);
    document.body.appendChild(pan);
    window.addEventListener("keydown", function(e){ if (e.key === "Escape" && !pan.hidden){ api.close(); e.stopPropagation(); } }, true);
    return pan;
  }
  function section(){
    if (sec) return sec;
    sec = document.createElement("div"); sec.className = "q382-set"; sec.id = "q382-set";
    sec.innerHTML =
      '<h4>Zoom chip (the &ldquo;2.4&times; | 1:1&rdquo; label)</h4>' +
      '<label><input type="radio" name="q382-chip" value="timed" id="q382-timed"> Show it after each zoom for <input type="number" id="q382-secs" min="1" max="600" step="1" aria-label="seconds"> seconds</label>' +
      '<label><input type="radio" name="q382-chip" value="always" id="q382-always"> Always visible while zoomed</label>' +
      '<p>Hovering or touching the chip keeps it. Double-tap empty space (touch) or use <b>Zoom 1:1</b> below to return to 1:1 while it is hidden.</p>' +
      '<h4>Text size</h4>' +
      '<label>All boxes <select id="q386-g" aria-label="Text size of all boxes"></select></label>' +
      '<div class="q386-rows" id="q386-rows" role="group" aria-label="Text size of one box"></div>' +
      '<p>Each box can also have its own: the A&minus; / A+ buttons at its lower-right corner while the pointer is over it, or its three-dots menu. Text never goes under 10 px.</p>' +
      '<h4>Boxes</h4>' +
      '<label><input type="checkbox" id="q382-lock"> Lock panels (no dragging or resizing)</label>' +
      '<label><input type="checkbox" id="q393-fit"> Keep the figure in the free part of the screen (open panels push it aside)</label>' +
      '<div class="q382-row"><button type="button" id="q382-reset">Reset layout</button><button type="button" id="q382-show">Show zoom chip</button><button type="button" id="q382-one">Zoom 1:1</button></div>' +
      '<p>Boxes move by their handle or by their title row, and change size by the grip at their lower-right corner (double-click it: back to the box&rsquo;s own size). Positions and sizes are kept in this browser, separately for a desktop-width and a phone-width window.</p>';
    function $(id){ return sec.querySelector("#" + id); }
    function paint(){
      var P = window.NMSKPinch ? NMSKPinch.prefs() : {always:false, secs:10};
      $("q382-always").checked = !!P.always; $("q382-timed").checked = !P.always; $("q382-secs").value = P.secs;
      $("q382-lock").checked = !!(window.NMSKMove && NMSKMove.locked());
      $("q393-fit").checked = fitOn();
      fonts();
    }
    /* Q386: the all-boxes text size and one row per box that is on the screen now (a row's value "" = the all-boxes size) */
    function opts(sel, withDefault, cur){
      var R = window.NMSKResize, h = withDefault ? '<option value="">Default</option>' : "";
      (R ? R.steps() : [100]).forEach(function(p){ h += '<option value="' + p + '"' + (cur === p ? " selected" : "") + ">" + p + " %</option>"; });
      return h;
    }
    function fonts(){
      var R = window.NMSKResize, g = $("q386-g"), rows = $("q386-rows"); if (!R || !g || !rows) return;
      if (document.activeElement !== g) g.innerHTML = opts(g, false, R.global());
      var bs = R.boxes().filter(function(b){ return b.present; }), sig = bs.map(function(b){ return b.key + ":" + (b.own ? b.pct : ""); }).join(",") + "|" + R.global();
      if (rows.getAttribute("data-sig") === sig) return;
      if (rows.contains(document.activeElement) && rows.getAttribute("data-sig") != null) return;
      rows.setAttribute("data-sig", sig);
      rows.innerHTML = "";
      bs.forEach(function(b){
        var l = document.createElement("label"), s = document.createElement("select");
        l.appendChild(document.createTextNode(b.label)); s.setAttribute("data-k", b.key); s.setAttribute("aria-label", "Text size of " + b.label);
        s.innerHTML = opts(s, true, b.own ? b.pct : -1); l.appendChild(s); rows.appendChild(l);
      });
    }
    sec.addEventListener("change", function(e){
      var P = window.NMSKPinch, t = e.target;
      if (t.id === "q382-lock"){ if (window.NMSKMove) NMSKMove.lock(t.checked); }
      else if (t.id === "q393-fit"){ fitSet(t.checked); }
      else if (t.id === "q386-g"){ if (window.NMSKResize) NMSKResize.setGlobal(+t.value); }
      else if (t.getAttribute && t.getAttribute("data-k")){ if (window.NMSKResize) NMSKResize.setBox(t.getAttribute("data-k"), t.value === "" ? null : +t.value); }
      else if (P){
        if (t.name === "q382-chip") P.setPrefs({always:$("q382-always").checked});
        if (t.id === "q382-secs"){ var v = Math.round(+t.value); if (v > 0) P.setPrefs({secs:v, always:false}); }
      }
      paint();
    });
    sec.addEventListener("click", function(e){
      var t = e.target && e.target.closest ? e.target.closest("button") : null; if (!t) return;
      if (t.id === "q382-reset") api.reset();
      else if (t.id === "q382-show" && window.NMSKPinch) NMSKPinch.reveal();
      else if (t.id === "q382-one" && window.NMSKPinch) NMSKPinch.resetAll();
    });
    sec.addEventListener("pointerenter", paint); sec.addEventListener("focusin", paint);
    sec.paint = paint; paint();
    return sec;
  }
  /* ---- Q393, owner: "SETTINGS needs an option to open a SETTINGS TREE, and an option to open a SETTINGS search [different from the
     structure search]". One registry of the settings that EXIST on the page -- each row names a real control by its id (or a class the
     add-ons put on theirs) and where it lives; a row whose control is not on this page is simply not listed. The tree groups them by
     topic; the search filters the same rows by name, topic and synonyms (English, and the Hebrew words the mode bar already uses).
     A leaf goes to the real control: it opens the panel or group that holds it, scrolls it into view and marks it for a moment. */
  var SELF = "self";
  var TOPICS = [
    ["display", "Display", "תצוגה"], ["labels", "Labels", "תוויות"], ["layout", "Layout and windows", "פריסה וחלונות"],
    ["text", "Text size", "גודל טקסט"], ["pose", "Pose", "תנוחה"], ["imaging", "Imaging / scan", "הדמיה"],
    ["needle", "Needle / planning", "מחט / תכנון"], ["cover", "Cover", "כיסוי"], ["colour", "Selection colour", "צבע הבחירה"],
    ["safety", "Safety", "בטיחות"]];
  var REG0 = [
    {t:"display", l:"Zoom chip: shown for some seconds, or always", s:"#q382-timed", h:SELF, k:"zoom chip delay seconds timer scale magnification", he:"זום"},
    {t:"display", l:"Show the zoom chip now", s:"#q382-show", h:SELF, k:"zoom chip reveal", he:"זום"},
    {t:"display", l:"Zoom 1:1", s:"#q382-one", h:SELF, k:"zoom reset actual size one to one", he:"זום"},
    {t:"display", l:"Colour by source", s:"#src-colour", h:"systems", k:"source colours provenance facet"},
    {t:"display", l:"Model only / split / compare", s:"#t-lay3", h:"view", k:"layout panes split compare model only"},
    {t:"display", l:"Spin the model", s:"#btn-spin", h:"view", k:"rotate turntable auto rotate"},
    {t:"labels", l:"Labels on / off (Off, Selected, Visible, All)", s:"#lab-show", h:"labels", k:"names callouts show hide", he:"תוויות שמות"},
    {t:"labels", l:"Full name or abbreviation", s:"#lab-text", h:"labels", k:"abbreviation short code name", he:"קיצור"},
    {t:"labels", l:"Callouts: auto, outside, inline", s:"#lab-callout", h:"labels", k:"leader lines callout"},
    {t:"labels", l:"Maximum number of labels", s:"#lab-dens", h:"labels", k:"density count how many max"},
    {t:"labels", l:"Label font size", s:"#lab-font", h:"labels", k:"text size font bigger smaller", he:"גודל"},
    {t:"labels", l:"Label colour", s:"#lab-colour", h:"labels", k:"colour color neutral"},
    {t:"labels", l:"Vessel and nerve labels", s:"#lab-groups", h:"labels", k:"arteries veins nerves vessels hide", he:"עצבים כלי דם"},
    {t:"labels", l:"Artery / vein level", s:"#lab-lva", h:"labels", k:"artery vein level calibre diameter"},
    {t:"labels", l:"Nerve level", s:"#lab-lvn", h:"labels", k:"nerve level branches calibre", he:"עצבים"},
    {t:"labels", l:"R / L marks on names", s:"#lab-side", h:"labels", k:"right left side"},
    {t:"labels", l:"Hide labels of hidden-behind structures", s:"#lab-occl", h:"labels", k:"occluded behind hidden"},
    {t:"labels", l:"Abbreviation list", s:"#lab-legend-btn", h:"labels", k:"legend abbreviations list", he:"קיצורים"},
    {t:"layout", l:"Lock panels (no dragging or resizing)", s:"#q382-lock", h:SELF, k:"lock drag move freeze boxes windows panels"},
    {t:"layout", l:"Keep the figure in the free part of the screen", s:"#q393-fit", h:SELF, k:"figure room centre center free space push aside"},
    {t:"layout", l:"Reset layout (positions and sizes)", s:"#q382-reset", h:SELF, k:"reset restore positions sizes boxes windows"},
    {t:"text", l:"Text size of all boxes", s:"#q386-g", h:SELF, k:"text font size bigger smaller all boxes", he:"גודל טקסט"},
    {t:"text", l:"Text size of one box", s:"#q386-rows", h:SELF, k:"text font size one box per box"},
    {t:"pose", l:"Pose panel (joints and their ranges)", s:"#pose-panel", h:"pose", k:"joints range of motion rom pose posture", he:"תנוחה"},
    {t:"pose", l:"Rings on the model", s:"#pz-rings-btn", h:"pose", k:"rotation rings joints drag"},
    {t:"pose", l:"This joint only", s:"#pz-solo", h:"pose", k:"one joint solo sliders"},
    {t:"imaging", l:"How the model is drawn (radiographic styles)", s:"#rs-box", h:"imaging", k:"render style x-ray ct mri film grey radiograph", he:"הדמיה"},
    {t:"imaging", l:"Bone reading", s:"#br-box", h:"imaging", k:"bone density reading"},
    {t:"imaging", l:"See-through (older x-ray preset)", s:"#t-xray", h:"imaging", k:"transparent see through xray"},
    {t:"imaging", dyn:".q301-scan", h:"imaging", k:"scan image simulation probe", he:"הדמיה סריקה"},
    {t:"needle", l:"Needle panel (plan a path)", s:"#needle-panel", h:"needle", k:"needle injection path entry target plan", he:"מחט הזרקה"},
    {t:"needle", l:"Workspaces (planning, scan, compare)", s:"#t-mode", h:"page", k:"mode workspace planning injection", he:"מצב תכנון"},
    {t:"cover", l:"Underwear display cover", s:"#cv-box", h:"systems", k:"cover underwear garment modesty", he:"כיסוי"},
    {t:"colour", l:"Colour of the selected", s:"#ss-col", h:"mark", k:"colour color selected marked tint", he:"צבע"},
    {t:"colour", l:"Highlight the selected", s:"#sel-p-hlsel", h:"mark", k:"highlight selected"},
    {t:"colour", l:"Fade the others", s:"#sel-p-fadeoth", h:"mark", k:"fade others ghost"},
    {t:"safety", l:"Risk halos and safer pathways (needle)", s:"#ncl-risk", h:"needle", k:"risk halo safety margin vessels nerves safer", he:"בטיחות סיכון"}];
  function REG(){
    var out = [];
    REG0.forEach(function(r){
      if (!r.dyn){ out.push(r); return; }
      Array.prototype.forEach.call(document.querySelectorAll(r.dyn), function(b, i){
        var txt = (b.textContent || "").replace(/\s+/g, " ").trim(); if (!txt) return;
        if (!b.id) b.id = "q393-dyn-" + i;
        out.push({t:r.t, l:"Open " + txt, s:"#" + b.id, h:r.h, k:r.k + " " + txt.toLowerCase(), he:r.he, press:true});
      });
    });
    return out;
  }
  function resolve(r){ try { return document.querySelector(r.s); } catch (e){ return null; } }
  function shownEl(e){ if (!e || e.hidden) return false; var s = getComputedStyle(e); return s.display !== "none" && s.visibility !== "hidden" && e.getClientRects().length > 0; }
  function host(r){
    var G = window.NMSKGroups;
    if (r.h === SELF){ var lz = document.getElementById("q393-lz"); if (lz) lz.open = true; return; }
    api.close();
    if (r.h === "labels"){ var lc = window.__labCtl, lp = document.getElementById("lab-panel"); if (lp && lp.hidden){ if (lc && lc.openPanel) lc.openPanel(true); else { var tb = document.getElementById("t-labels"); if (tb) tb.click(); } } return; }
    if (r.h === "pose"){ var pp = document.getElementById("pose-panel"), bp = document.getElementById("btn-pose"); if (pp && !shownEl(pp) && bp) bp.click(); return; }
    if (r.h === "needle"){ var np = document.getElementById("needle-panel"), bn = document.getElementById("t-needle"); if (np && np.hidden && bn) bn.click(); return; }
    if (G && G.open && G.isOpen() !== r.h) G.open(r.h);
  }
  function go(r){
    var e = resolve(r); if (!e) return false;
    if (r.press){ api.close(); e.click(); return true; }
    host(r);
    setTimeout(function(){
      var x = resolve(r); if (!x) return;
      for (var d = x.parentNode; d && d !== document.body; d = d.parentNode) if (d.tagName === "DETAILS" && !d.open) d.open = true;
      try { x.scrollIntoView({block:"nearest", inline:"nearest"}); } catch (e1){}
      x.classList.add("q393-flash"); setTimeout(function(){ x.classList.remove("q393-flash"); }, 1800);
      var f = /^(INPUT|SELECT|BUTTON|TEXTAREA)$/.test(x.tagName) ? x : x.querySelector("input,select,button");
      if (f){ try { f.focus({preventScroll:true}); } catch (e2){} }
    }, 160);
    return true;
  }
  var fnd = null;
  function finder(){
    if (fnd) return fnd;
    fnd = document.createElement("div"); fnd.className = "q393-find"; fnd.id = "q393-find";
    fnd.innerHTML = '<input type="search" id="q393-sq" placeholder="Search settings (not structures)" autocomplete="off" aria-label="Search the settings by name">' +
      '<div class="q393-tb"><button type="button" id="q393-all">Open all</button><button type="button" id="q393-none-b">Close all</button><span id="q393-n" class="q393-n"></span></div>' +
      '<div class="q393-tree" id="q393-tree" role="tree" aria-label="Settings by topic"></div><p class="q393-empty" id="q393-empty" hidden>No setting with that name. The structure search is under Search.</p>';
    fnd.querySelector("#q393-sq").addEventListener("input", function(){ filter(this.value); });
    fnd.querySelector("#q393-sq").addEventListener("keydown", function(e){
      if (e.key === "Enter"){ var b = fnd.querySelector(".q393-leaf:not([hidden])"); if (b){ e.preventDefault(); b.click(); } }
    });
    fnd.querySelector("#q393-all").addEventListener("click", function(){ fnd.querySelectorAll(".q393-t").forEach(function(d){ d.open = true; }); });
    fnd.querySelector("#q393-none-b").addEventListener("click", function(){ fnd.querySelectorAll(".q393-t").forEach(function(d){ d.open = false; }); });
    fnd.addEventListener("click", function(e){
      var b = e.target.closest ? e.target.closest(".q393-leaf") : null; if (!b) return;
      var R = REG(), r = R[+b.getAttribute("data-i")]; if (r) go(r);
    });
    return fnd;
  }
  function norm(s){ return String(s || "").toLowerCase().replace(/[\u0591-\u05C7]/g, "").replace(/[^a-z0-9\u05d0-\u05ea]+/g, " ").trim(); }
  var treeSig = "";
  function buildTree(){
    var tree = fnd && fnd.querySelector("#q393-tree"); if (!tree) return [];
    var R = REG(), live = R.map(function(r, i){ return resolve(r) ? i : -1; }).filter(function(i){ return i >= 0; });
    var sig = live.map(function(i){ return R[i].s + R[i].l; }).join("|");
    if (sig === treeSig) return R;
    var open = {}; tree.querySelectorAll(".q393-t").forEach(function(d){ open[d.getAttribute("data-t")] = d.open; });
    treeSig = sig; tree.innerHTML = "";
    TOPICS.forEach(function(T){
      var mine = live.filter(function(i){ return R[i].t === T[0]; }); if (!mine.length) return;
      var d = document.createElement("details"); d.className = "q393-t"; d.setAttribute("data-t", T[0]); d.setAttribute("role", "treeitem"); d.open = !!open[T[0]];
      var s = document.createElement("summary"); s.innerHTML = "<b></b> <span class=\"q393-he\" dir=\"rtl\"></span> <span class=\"q393-c\"></span>";
      s.querySelector("b").textContent = T[1]; s.querySelector(".q393-he").textContent = T[2]; s.querySelector(".q393-c").textContent = mine.length;
      d.appendChild(s);
      var ul = document.createElement("ul"); ul.setAttribute("role", "group");
      mine.forEach(function(i){
        var li = document.createElement("li"), b = document.createElement("button"); b.type = "button"; b.className = "q393-leaf"; b.setAttribute("data-i", i);
        b.setAttribute("data-key", norm([R[i].l, T[1], T[2], R[i].k, R[i].he].join(" "))); b.textContent = R[i].l; b.title = "Go to: " + R[i].l;
        li.appendChild(b); ul.appendChild(li);
      });
      d.appendChild(ul); tree.appendChild(d);
    });
    return R;
  }
  function filter(q){
    if (!fnd) return 0;
    buildTree();
    var words = norm(q).split(" ").filter(Boolean), n = 0;
    fnd.querySelectorAll(".q393-t").forEach(function(d){
      var k = 0;
      d.querySelectorAll(".q393-leaf").forEach(function(b){
        var key = b.getAttribute("data-key"), hit = words.every(function(w){ return key.indexOf(w) >= 0; });
        b.parentNode.hidden = !hit; if (hit) k++;
      });
      d.hidden = k === 0; if (words.length) d.open = k > 0;
      n += k;
    });
    var em = fnd.querySelector("#q393-empty"); if (em) em.hidden = n > 0;
    var c = fnd.querySelector("#q393-n"); if (c) c.textContent = words.length ? n + " found" : n + " settings";
    return n;
  }

  /* ---- Q393, owner: "also when menus and the like are open, the main part of the screen must always be the figure". The panels that open
     beside the model (the group sheet, labels, legend, pose, settings, cut, measure) are measured; the 3-D canvas is then laid over the
     part of the screen they leave free, so the figure is drawn centred in that part instead of behind a panel. Desktop: panels count by
     the side they sit on (left / right); phone: the bottom sheet's height. With nothing open the canvas is the whole screen, as before.
     Only in the Model-only / Split layouts without an image pane, and outside the workspace modes (those dock the canvas themselves). Can be switched off in Settings. */
  var FIT_KEY = "nmsk.q393.fit", fitPref = null, lastRoom = null, fitT = 0, applied = false;
  var ROOM = ["#q301-sheet", "#lab-panel", "#lab-legend", "#pose-panel", "#q382-panel", "#needle-panel", "#cut-panel", "#ms-bar", "#rail"];
  function fitOn(){ if (fitPref == null){ try { fitPref = localStorage.getItem(FIT_KEY) !== "0"; } catch (e){ fitPref = true; } } return fitPref; }
  function fitSet(on){ fitPref = !!on; try { localStorage.setItem(FIT_KEY, on ? "1" : "0"); } catch (e){} fitNow(); }
  function fitSoon(){ clearTimeout(fitT); fitT = setTimeout(fitNow, 60); }
  function room(){
    var vw = window.innerWidth, vh = window.innerHeight, phone = vw <= 560, L = 0, R = 0, T = 0, B = 0, who = [];
    ROOM.forEach(function(sel){
      var e = document.querySelector(sel); if (!shownEl(e)) return;
      var r = e.getBoundingClientRect(); if (r.width < 40 || r.height < 40 || r.right < 0 || r.left > vw || r.bottom < 0 || r.top > vh) return;
      if (phone){
        if (r.width < vw * 0.6) return;                            /* a small box at a side does not take the figure's height */
        if ((r.top + r.bottom) / 2 > vh * 0.5){ B = Math.max(B, vh - r.top + 4); who.push(sel + ":b"); }
        /* a box at the top of a phone (the measure bar under the control bar) is left alone: moving the canvas down would carry the
           control bar (anchored to it) down over that box */
        return;
      }
      if (r.height < vh * 0.18) return;                          /* a short bar along an edge does not take the figure's room */
      var c = (r.left + r.right) / 2;
      if (r.left < vw * 0.3 && r.right > vw * 0.7) return;        /* a panel across the middle: nothing to push aside */
      if (c < vw / 2){ L = Math.max(L, r.right + 6); who.push(sel + ":l"); } else { R = Math.max(R, vw - r.left + 6); who.push(sel + ":r"); }
    });
    if (L + R > vw * 0.6){ var k = vw * 0.6 / (L + R); L *= k; R *= k; }
    if (T + B > vh * 0.62){ var k2 = vh * 0.62 / (T + B); T *= k2; B *= k2; }
    return {l:Math.round(L), r:Math.round(R), t:Math.round(T), b:Math.round(B), who:who, vw:vw, vh:vh};
  }
  var PROPS = ["left", "top", "width", "height", "right", "bottom"];
  function fitNow(){
    var cv = document.getElementById("view"), b = document.body; if (!cv || !b) return null;
    /* the Model-only layout, or Split while no image pane is docked (the image panes size the canvas themselves); never in a workspace mode */
    var can = fitOn() && cv.tagName === "CANVAS" && !b.classList.contains("mode-on") && !b.classList.contains("nmsk-us") && !b.classList.contains("nmsk-img") &&
      (b.classList.contains("lay-model") || b.classList.contains("lay-split"));
    var rm = can ? room() : null, any = !!(rm && (rm.l || rm.r || rm.t || rm.b));
    lastRoom = rm;
    if (!any){
      if (applied){ PROPS.forEach(function(p){ cv.style.removeProperty(p); }); applied = false; cv.removeAttribute("data-q393"); engineResize(); }
      return rm;
    }
    var sig = [rm.l, rm.r, rm.t, rm.b, rm.vw, rm.vh].join(",");
    if (applied && cv.getAttribute("data-q393") === sig) return rm;
    cv.style.setProperty("left", rm.l + "px"); cv.style.setProperty("top", rm.t + "px");
    cv.style.setProperty("width", (rm.vw - rm.l - rm.r) + "px"); cv.style.setProperty("height", (rm.vh - rm.t - rm.b) + "px");
    cv.style.setProperty("right", "auto"); cv.style.setProperty("bottom", "auto");
    applied = true; cv.setAttribute("data-q393", sig);
    engineResize();
    return rm;
  }
  /* the engine is told directly: a window "resize" event would also make every box re-place and re-size itself (Q386 / Q305) */
  function engineResize(){
    var M = window.NMSKModes;
    if (M && M.resized){ M.resized(); return; }
    try { window.dispatchEvent(new Event("resize")); } catch (e){}
  }
  function fitStart(){
    setInterval(fitNow, 400);
    document.addEventListener("click", function(){ setTimeout(fitNow, 80); setTimeout(fitNow, 400); }, true);
  }
  /* ---- Q393, owner: "the imaging simulations too need less explanatory text, and their options under clear headings, collapsed and
     opening by topic as needed". Two generic helpers the add-on panels call on their own nodes (this public file names none of them):
       accordion(root, {key, wrap:[{title, nodes:[...], id}], sel})  the titled sections of a panel open one at a time; the open one is
         remembered per panel (localStorage, in try / catch); `wrap` first gathers loose rows under a new title; nothing is removed;
       terse(root, sel, max, more)  a long note becomes its first sentence (or the sentence that states a limit or a safety point, which is
         never folded away) with the whole text one tap away under "More". */
  var SAFE = /not (a |an )?(validated|clinical|a scan|patient)|not clinical|safety|limit|education aid|simulat|heuristic|assum|בטיחות|לא ממקור|לא המלצה|מוסכמה|לעולם לא/i;
  function accStore(k, v){ try { if (v === undefined) return localStorage.getItem("nmsk.q393.acc." + k); localStorage.setItem("nmsk.q393.acc." + k, v); } catch (e){ return null; } return null; }
  function accordion(root, opt){
    if (!root) return null; opt = opt || {};
    (opt.wrap || []).forEach(function(w){
      var ns = (w.nodes || []).filter(function(n){ return n && n.parentNode; }); if (!ns.length) return;
      var d = document.createElement("details"); d.className = "q393-acc"; if (w.id) d.id = w.id;
      var s = document.createElement("summary"); s.textContent = w.title; d.appendChild(s);
      ns[0].parentNode.insertBefore(d, ns[0]);
      ns.forEach(function(n){ d.appendChild(n); });
    });
    var list = Array.prototype.filter.call(root.querySelectorAll(opt.sel || "details"), function(d){
      var p = d.parentNode; while (p && p !== root){ if (p.tagName === "DETAILS") return false; p = p.parentNode; } return true;   /* top level only */
    });
    function name(d){ return d.id || (d.querySelector("summary") ? d.querySelector("summary").textContent.trim() : ""); }
    list.forEach(function(d){
      d.classList.add("q393-acc"); d.open = false;
      d.addEventListener("toggle", function(){
        if (!d.open) { if (accStore(opt.key || "x") === name(d)) accStore(opt.key || "x", ""); return; }
        list.forEach(function(o){ if (o !== d && o.open) o.open = false; });
        accStore(opt.key || "x", name(d));
      });
    });
    var keep = accStore(opt.key || "x");
    list.forEach(function(d){ if (keep && name(d) === keep) d.open = true; });
    root.classList.add("q393-acc-root");
    return list;
  }
  function terse(root, sel, max, more){
    if (!root) return 0; max = max || 110; var n = 0;
    Array.prototype.forEach.call(root.querySelectorAll(sel), function(p){
      if (p.id || p.getAttribute("data-q393t") || (p.parentNode && p.parentNode.classList && p.parentNode.classList.contains("q393-more"))) return;   /* a live message (it has an id) is never folded */
      var t = (p.textContent || "").replace(/\s+/g, " ").trim(); if (t.length <= max) return;
      var ss = t.match(/[^.!?]+[.!?]+/g) || [t], keep = ss.filter(function(s){ return SAFE.test(s); })[0] || ss[0];
      if (keep.length > 160) keep = keep.slice(0, 150).replace(/\s+\S*$/, "") + " ...";
      var one = document.createElement(p.tagName === "P" ? "p" : "div"); one.className = "q393-one"; one.textContent = keep.trim();
      var d = document.createElement("details"); d.className = "q393-more"; var s = document.createElement("summary"); s.textContent = more || "More"; d.appendChild(s);
      p.parentNode.insertBefore(one, p); p.parentNode.insertBefore(d, p); d.appendChild(p);
      p.setAttribute("data-q393t", "1"); n++;
    });
    return n;
  }
  function boot(){
    if (ready) return;
    if (mount()){ clearInterval(timer); timer = 0; return; }
    if (++tries > 400){ clearInterval(timer); timer = 0; }
  }
  var api = {
    start:function(){ if (ready || timer) return api; boot(); if (!ready) timer = setInterval(boot, 250); return api; },
    open:function(){ var p = panel(); p.hidden = false; if (window.NMSKInfo && NMSKInfo.close) NMSKInfo.close(); var s = section(); if (s.paint) s.paint(); filter(""); fitSoon(); },
    /* Q393: the settings search -- the same panel, the cursor in its own search field (never the structure search) */
    find:function(q){ api.open(); var f = document.getElementById("q393-sq"); if (f){ if (q != null){ f.value = q; filter(q); } try { f.focus(); } catch (e){} } },
    registry:function(){ return REG().map(function(r){ return {topic:r.t, label:r.l, on:!!resolve(r)}; }); },
    go:function(i){ var R = REG(); return R[i] ? go(R[i]) : false; },
    fit:function(){ return fitNow(); },
    accordion:accordion, terse:terse,
    close:function(){ if (pan) pan.hidden = true; fitSoon(); },
    reset:function(){
      var a = window.NMSKMove ? NMSKMove.restore() : false, b = window.NMSKResize ? NMSKResize.reset() : false;
      if (sec && sec.paint) sec.paint();
      return !!(a || b);
    },
    ready:function(){ return ready; },
    state:function(){ return {ready:ready, fit:fitOn(), room:lastRoom, locked:!!(window.NMSKMove && NMSKMove.locked()), chip:window.NMSKPinch ? NMSKPinch.prefs() : null, boxes:SPEC.map(function(s){ return s.key; })}; }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function(){ api.start(); }); else api.start();
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKLayout;
