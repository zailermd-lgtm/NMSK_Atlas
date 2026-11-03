/* Q305: the boot. ONE table of boxes serves six pages and both engines -- a box whose element is not on this page is
   simply never mounted, which is how Q301's one group table already serves both engines.
   Nothing here touches the engines: a moved box is moved by its own `translate`, which composes with whatever
   `transform` and whatever `left` / `top` the stylesheets and the five earlier rounds' placement code set. That is why
   this round needs no `patch_engines` script and no per-engine glue, and why Q298's, Q299's, Q300's, Q301's and Q303's
   page blocks come out of the regen byte-identical.
   WHAT IS MOVABLE, AND WHAT IS DELIBERATELY NOT. Movable: a box that FLOATS over the 3-D view and can get in the way of
   it. Not movable, each for a stated reason:
     - the own engine's structure list (`aside`) and structure card (`#inspector`) on a desktop are GRID COLUMNS of
       `#app`, not floating boxes: the canvas is sized by the grid, so a moved column would leave an empty strip behind
       it and cover the model it had just made room for. They already collapse, and `#t-lay3` already cycles the
       layout. On a phone they are bottom sheets, i.e. already docked.
     - Q290's zoom chip (`.pz-chip`) reports the zoom OF THE SURFACE IT SITS ON and there is one per surface, so where
       it is IS what it means; one tap on it undoes the zoom anyway.
     - Q303's four-pane labels (`.q3-ch`) name the quadrant they are in. Moved out of their cell they would be wrong.
     - Q301's group sheet (`#q301-sheet`) is not a box of its own: it is the open group, and it travels with the bar.
     - the clinical imaging and probe roots are PANES, not boxes -- their rectangle is recomputed by the page's own
       layout cycle (Model only / Split / Compare), so a user's offset would be overwritten on the next pass; the
       reference window and the probe handles in that layer already carry their own drag (`.ref-head` is `cursor:move`).
       The public templates may not name that layer either, so a shared viewer module must not carry its ids; what this
       module leaves it is the `data-nmsk-move` opt-in below.
     - the labels panel and legend DO float, so they are in -- but they place themselves (and remember their own size),
       and our offset rides on top of that placement rather than replacing it.
     - the STRUCTURE SEARCH BOX is not a box of its own on either engine: it is a field inside the side panel (`#rail`
       on the Z pages, `aside` on the Imaging ones), so it travels with that panel and gets no handle of its own.
       Q298's expansion strip (`#q8-float`) IS its own floating box and is in.
     NMSKQ305.start()   .boxes()   .state() */
var NMSKQ305 = (function(){
  "use strict";
  var on = false, tries = 0, timer = 0;
  /* key -> the two engines' ids. Both are listed; the one that is not on this page is dropped. */
  var BOXES = [
    {key:"control",  el:"q301-bar",   into:"q301-hist", label:"the control bar",            "with":["q301-sheet"]},
    {key:"hidden",   el:"sa-bar",     at:"tl", label:"the “what is hidden” bar"},
    {key:"info",     el:"q301-info",  at:"tl", label:"the information drawer"},
    {key:"cut",      el:"cut-panel",  at:"tl", label:"the cut / cross-section panel"},
    {key:"card",     el:"info",       at:"tl", label:"the structure card",     light:true},
    {key:"rail",     el:"rail",       at:"tl", label:"the side panel",         light:true},
    {key:"pills",    el:"topright",   at:"bl", label:"the top row of buttons"},
    {key:"measure",  el:"ms-bar",     at:"tl", label:"the measurement bar"},
    {key:"slices",   el:"xsp-panel",  at:"tl", label:"the part-slices panel"},
    {key:"expand",   el:"q8-float",   at:"tl", label:"the structure-expansion strip"},
    {key:"labels",   el:"lab-panel",  at:"tl", label:"the labels panel",       light:true},
    {key:"legend",   el:"lab-legend", at:"tl", label:"the labels legend",      light:true}
  ];
  /* Controls that must stay reachable whatever the user does with the boxes. Everything Q301 lost to an overlap is
     here by name, plus every grip (a box whose handle is covered could never be moved back). */
  var PROTECT = [
    {id:"q301-undo",     label:"Undo"},
    {id:"q301-redo",     label:"Redo"},
    {id:"q301-reset",    label:"Reset module"},
    {id:"q301-mr-model", label:"Reset model"},
    {id:"q301-info-btn", label:"the circled i"},
    {id:"sa-all",        label:"Show everything"},
    {sel:"#q301-groups .qg-g:not([hidden])", label:"a group button on the control bar"},
    {sel:"#q301-sheet:not([hidden]) .qg-sbody button:not([hidden]):not([disabled])", label:"a control in the open group"},
    /* SOFT: a handle under another box is worth reporting, but it is not a control the page needs -- the layout can
       still be put back from the control bar or with the keyboard, and on a small screen two boxes genuinely do
       overlap whatever any round does. The verify asserts the HARD set is empty on every page and in both viewports,
       and that the SOFT set never grows because of a move. */
    {sel:".nm-grip", label:"a box’s own move handle", soft:true},
    {sel:"[data-nmsk-protect]", label:"a control another layer asked us to keep clear"}
  ];
  function pageKey(){
    /* the store is per page. Each page is its own artifact origin, so localStorage is already separate; the title is
       added so that two pages served from one origin (a local build, the test harness) still do not share a layout. */
    var t = "";
    try { t = String(document.title || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48); } catch (err){ t = ""; }
    return t || "page";
  }
  function info(){
    var I = window.NMSKInfo;
    if (!I || !I.add) return;
    I.add({key:"layout", title:"Moving the boxes on the screen", order:45, build:function(){
      var M = window.NMSKMove, st = M ? M.state() : null;
      if (!st) return "<p>(not available on this page)</p>";
      var mv = st.boxes.filter(function(b){ return b.present; });
      return "<p>Every box below carries a small <b>handle</b> &mdash; six dots. Drag the handle and the box goes where " +
        "you put it; it is still there when you come back to this page in this browser. The box <b>body</b> is never a " +
        "drag: the model is dragged to turn it, a pinch zooms any picture, the probe is dragged over the skin " +
        "and a long press on a list picks a range, and a box that moved when its body was dragged would take one of " +
        "those away. On this screen the handle moves a box <b>" + (st.phone ? "between a few fixed slots" : "anywhere you like") +
        "</b>.</p><p>On a keyboard: the arrow keys move the box the handle belongs to, and <b>Home</b> puts that one box back.</p>" +
        "<p><b>" + mv.length + " boxes on this page can be moved</b>: " + mv.map(function(b){ return b.label; }).join(", ") + ".</p>" +
        "<p><b>A drop that would cover a control is refused</b> and the box goes back, with a line saying which control " +
        "it was. The controls kept clear are: " + (window.NMSKGuard ? NMSKGuard.watched().join(", ") : "&mdash;") + ".</p>" +
        "<p><b>Restore layout</b> puts every box back where it started &mdash; one tap, and one Undo brings your " +
        "arrangement back. Reset model does it too, because the layout is part of what the page loaded in. It is in the " +
        "<b>View</b> group of the control bar, and here: " +
        "<button type=\"button\" id=\"q305-restore-i\" class=\"nm-rb\">Restore layout</button></p>" +
        "<p>What is <b>not</b> movable, and why: the zoom chip belongs to the picture it reports; a four-pane label names " +
        "its own quadrant; the imaging and probe views are panes the layout sizes, not boxes" +
        (document.getElementById("app") ? "; and the structure list and the structure card are columns of the page's own grid, which already has its own layouts" : "") + ".</p>";
    }});
  }
  function mount(){
    var M = window.NMSKMove, G = window.NMSKGroups, H = window.NMSKHistory, Gu = window.NMSKGuard;
    if (!M || !Gu) return false;
    if (!H || !H.active || !H.active()) return false;              /* the history must be running: the layout is one of its providers */
    if (!G || !G.state || !G.state().on) return false;             /* and the control bar must exist: Restore layout lives in it */
    PROTECT.forEach(function(p){ Gu.watch(p); });
    /* A box another layer wants movable asks for it IN THE MARKUP, so nothing private is named here -- the clinical
       layer can set `data-nmsk-move="the needle panel"` on its own floating panel and get a handle, and the public
       templates still carry none of its ids. Re-scanned on a slow timer, because that layer builds its DOM the first
       time its tool is opened, long after this. `M.add` ignores a key it already has. */
    function opted(){
      var n = 0;
      try {
        [].slice.call(document.querySelectorAll("[data-nmsk-move]")).forEach(function(e){
          if (!e.id) return;
          if (M.add({key:"x-" + e.id, el:e.id, at:e.getAttribute("data-nmsk-at") || "tl",
                     label:e.getAttribute("data-nmsk-move") || e.id})) n++;
        });
      } catch (err){}
      if (n) M.refresh();
      return n;
    }
    M.start({key:pageKey(), history:H, guard:Gu, boxes:BOXES});
    opted();
    setInterval(opted, 2000);
    G.addTo("view", {
      label:"Restore layout", id:"q305-restore",
      title:"Put every box back where it started -- one tap, and one Undo brings your arrangement back",
      run:function(){ M.restore(); },
      active:function(){ return M.moved().length > 0; },
      label2:"Boxes are moved by the small handle of six dots on each one. Reset model puts the layout back as well."
    });
    info();
    /* a second home for Restore layout, inside the i's own section. The View group's sheet SCROLLS (its body measured
       441 px against a 362 px window on a 1400x900 desktop), so a control added at the end of that group can be below
       the fold -- which is how the first real-page run could not press it at all. The i is never more than one tap
       away, and this costs no new top-level button. */
    document.addEventListener("click", function(e){
      var t = e.target && e.target.closest ? e.target.closest("#q305-restore-i") : null;
      if (t){ e.preventDefault(); e.stopPropagation(); M.restore(); }
    }, true);
    on = true;
    return true;
  }
  function boot(){
    if (on) return;
    if (mount()){ if (timer) clearInterval(timer); timer = 0; return; }
    if (++tries > 400 && timer){ clearInterval(timer); timer = 0; }     /* 400 x 200 ms: a page that never starts a history */
  }
  var api = {
    start:function(){
      if (on || timer) return api;
      boot();
      if (!on) timer = setInterval(boot, 200);
      return api;
    },
    ready:function(){ return on; },
    boxes:function(){ return BOXES.map(function(b){ return b.key; }); },
    protect:function(){ return PROTECT.slice(); },
    state:function(){ return {on:on, tries:tries, page:pageKey(), move:window.NMSKMove ? NMSKMove.state() : null, guard:window.NMSKGuard ? NMSKGuard.state() : null}; }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function(){ api.start(); });
  else api.start();
  return api;
})();
if (typeof module !== "undefined" && module.exports) module.exports = NMSKQ305;
