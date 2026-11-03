/* Q298: the one row of controls under the search box. Progressive disclosure, phone first: nothing is shown until it has
   something to do. It carries, in this order, only when relevant:
     the result count and "Mark all N"                 (a search is running and matched something)
     a group chip per matching group, "Mark the group" (the query named a textbook group: "hamstrings", "rotator cuff")
     the three expansions of the selected structure    (a structure is selected)
     "Add by tapping the model"                        (always; it drives the engine's existing Mark-mode button)
     a note row                                        (the query named something the project cites but ships no mesh for)
   It is created in JS and inserted after the engine's own search box, so neither engine's layout had to be rebuilt. */
function NMSKQ298Bar(E, D, H){
  "use strict";
  var esc = H.esc, say = H.say;
  var root = document.createElement("div");
  root.className = "q8-bar";
  root.id = "q8-bar";
  root.innerHTML =
    '<div class="q8-row" id="q8-res" hidden>' +
      '<span class="q8-n" id="q8-count"></span>' +
      '<button type="button" class="q8-b" id="q8-all">Mark all</button>' +
      '<button type="button" class="q8-b" id="q8-range" aria-pressed="false" title="Mark a run of rows: tap the first, then the last (Shift-click on a desktop does the same)">Range</button>' +
      '<button type="button" class="q8-b" id="q8-onmodel" aria-pressed="false" title="While on, a tap or click on the model adds that structure to the marked set (Shift / Ctrl-click and a long press already do this at any time)">On model</button>' +
    '</div>' +
    '<div class="q8-row" id="q8-groups" hidden></div>' +
    '<div class="q8-row" id="q8-exp" hidden>' +
      '<span class="q8-n" id="q8-selname"></span>' +
      '<button type="button" class="q8-b" id="q8-adj">Adjacent</button>' +
      '<button type="button" class="q8-b" id="q8-rel">Related</button>' +
      '<button type="button" class="q8-b" id="q8-grp">Functional group</button>' +
    '</div>' +
    '<div class="q8-menu" id="q8-menu" hidden></div>' +
    '<div class="q8-q306" id="q8-q306" hidden></div>' +      /* Q306: the approximate-match line and the concept rows */
    '<p class="q8-note" id="q8-notes" hidden></p>' +
    '<p class="q8-status" id="q8-status" aria-live="polite"></p>';
  var box = E.box();
  if (box && box.parentNode) box.parentNode.insertBefore(root, box.nextSibling);
  else document.body.appendChild(root);
  /* On a phone both engines CLOSE the panel that holds the search box as soon as you pick a structure (the Z engine's
     closeSheet(), the own engine's own panel), so the three expansions would sit inside a hidden panel exactly when you
     want them. The expansion row, its menu and its status line therefore move to a floating strip at the bottom of the
     screen whenever the bar's own container is not on screen, and move back when it is. */
  var floatBox = document.createElement("div");
  floatBox.className = "q8-float";
  floatBox.id = "q8-float";
  floatBox.hidden = true;
  document.body.appendChild(floatBox);

  var $ = function(id){ return document.getElementById(id); };
  var MULTI = null, EXP = null, lastRes = null, shown = [];

  function wire(m, x){
    MULTI = m; EXP = x;
    $("q8-all").addEventListener("click", function(){ MULTI.markAllResults(lastRes); });
    $("q8-range").addEventListener("click", function(){ MULTI.toggleRange(); });
    $("q8-onmodel").addEventListener("click", function(){ MULTI.toggleOnModel(); });
    $("q8-adj").addEventListener("click", function(){ EXP.run("adj"); });
    $("q8-rel").addEventListener("click", function(){ EXP.run("rel"); });
    $("q8-grp").addEventListener("click", function(){ EXP.run("grp"); });
    setInterval(function(){ selRow(); }, 700);          // the card can be opened from the model, not only from the list
  }

  function update(res, shownIds){
    lastRes = res; shown = shownIds || [];
    var n = res ? res.ids.length : 0, q = res ? res.q : "";
    var rb = $("q8-res");
    rb.hidden = !(q && n);
    if (!rb.hidden){
      $("q8-count").textContent = n === 1 ? "1 match" : n + " matches";
      $("q8-all").textContent = "Mark all " + n;
      $("q8-all").disabled = !E.sel();
    }
    var gb = $("q8-groups");
    var gs = res ? res.groups : [];
    gb.hidden = !gs.length;
    if (gs.length){
      gb.innerHTML = gs.map(function(g, i){
        return '<button type="button" class="q8-g" data-g="' + i + '" title="' + esc(g.why + (g.src ? " — " + g.src : "")) +
               '">' + esc(g.name) + ' <span class="q8-n">' + g.ids.length + '</span>' +
               (g.inferred ? ' <span class="q8-inf">inferred</span>' : "") + "</button>";
      }).join("");
      Array.prototype.forEach.call(gb.querySelectorAll("[data-g]"), function(b){
        b.addEventListener("click", function(){
          var g = gs[+b.getAttribute("data-g")];
          MULTI.markIds(g.ids, "the group " + g.name, g.src, g.inferred, g.why);
        });
      });
    }
    var nb = $("q8-notes");
    var ns = res ? res.notes : [];
    nb.hidden = !ns.length;
    if (ns.length){
      nb.innerHTML = ns.map(function(x){
        return "<b>" + esc(x.name) + "</b> — no mesh on this page. " + esc(x.why) +
               " This project's name for it: <i>" + esc(x.canon) + "</i>." +
               (x.offer && x.offer.length
                 ? " It offers " + x.offer.length + " structure" + (x.offer.length === 1 ? "" : "s")
                   + " this page does carry."
                 : "");
      }).join("<br>");
    }
    /* Q306 says the two things the matcher cannot: that a result set is only an approximate match, and
       that a query was a CONCEPT rather than a structure. Guarded, so a page built without the Q306
       module or its block behaves exactly as it did before. */
    if (window.NMSKQ306){
      NMSKQ306.render(res, $("q8-q306"), {data:function(){ return D; },
                                           markIds:function(ids, what, src, inf, why){
        if (MULTI) MULTI.markIds(ids, what, src, inf, why); }});
    }
    reparent();
    selRow();
  }

  /* "off screen" means display:none somewhere up the tree OR scrolled/laid out outside the viewport: on a phone the
     panel that holds the search box is sometimes hidden and sometimes just pushed off, and either way the expansion
     row has to come to the user. */
  function hidden(){
    if (!root.offsetParent && !root.getClientRects().length) return true;
    var r = root.getBoundingClientRect();
    if (!r.width || !r.height) return true;
    var w = window.innerWidth || 0, h = window.innerHeight || 0;
    return r.bottom <= 8 || r.top >= h - 8 || r.right <= 8 || r.left >= w - 8;
  }
  function reparent(){
    var eb = $("q8-exp"), mn = $("q8-menu"), st = $("q8-status"), to = hidden() ? floatBox : root;
    if (eb && mn && st && eb.parentNode !== to){ to.appendChild(eb); to.appendChild(mn); to.appendChild(st); }
    /* Q306's lines go with them, and for the same reason: on a phone both engines close the panel that
       holds the search box, so a concept card left in `root` would sit inside a hidden panel exactly when
       the user wants it -- which is the trap Q298 recorded for its own expansion row, and which Q306's
       first browser run fell into (the card's button was never visible and the press timed out). */
    var q6 = $("q8-q306");
    if (q6 && q6.parentNode !== to) to.insertBefore(q6, eb && eb.parentNode === to ? eb : null);
    floatBox.hidden = to !== floatBox || ((!eb || eb.hidden) && (!q6 || q6.hidden));
  }
  function selRow(){
    var eb = $("q8-exp"), id = E.selected();
    if (!id || !EXP){ eb.hidden = true; reparent(); closeMenu(); return; }
    var c = EXP.counts(id);
    eb.hidden = false;
    $("q8-selname").textContent = EXP.nameOf(id);
    [["q8-adj", c.adj, "Adjacent"], ["q8-rel", c.rel, "Related"], ["q8-grp", c.grp, "Functional group"]]
      .forEach(function(t){
        var b = $(t[0]);
        b.textContent = t[2] + (t[1] ? " · " + t[1] : "");
        b.disabled = !t[1] || !E.sel();
      });
    reparent();
  }

  function menu(html, bind){
    var m = $("q8-menu");
    m.innerHTML = html; m.hidden = false;
    reparent();
    if (bind) bind(m);
  }
  function closeMenu(){ var m = $("q8-menu"); if (m){ m.hidden = true; m.innerHTML = ""; } }

  function pressed(id, v){ var b = $(id); if (b) b.setAttribute("aria-pressed", String(!!v)); }

  return {wire:wire, update:update, menu:menu, closeMenu:closeMenu, pressed:pressed, refresh:selRow,
          shown:function(){ return shown.slice(); }, root:root};
}
